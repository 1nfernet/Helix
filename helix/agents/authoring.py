"""Natural-language -> Helix spec authoring agent.

The agent drafts Helix source from a plain-English request. Crucially, its output
is *validated by the deterministic parser* before it is returned: if the model
emits invalid Helix, the parse error is fed back and it retries (self-repair),
and after N failures the agent raises rather than returning garbage. So the LLM
proposes reviewable ``.hx`` text; the trusted parser is the gatekeeper. A human
reviews the source before it is ever compiled.
"""

from __future__ import annotations

from helix.agents.llm import LLMClient
from helix.frontend.helix_lang import HelixSyntaxError, parse_helix
from helix.ir.spec import ExperimentSpec

# Compact grammar taught to the model. Kept in sync with GRAMMAR.md by example.
_GRAMMAR_GUIDE = """\
Helix is a declarative DSL for one gene-editing experiment. Output MUST be valid
Helix source and nothing else (no prose, no markdown fences).

Structure:

helix "<name>" {
  organism: <name>(<genome_build>)        # e.g. human(GRCh38)
  cell_line: <name>                        # optional
  target: gene(<SYMBOL>) {
    goal: knockout
    region: exon(<a>..<b>)                 # optional hint (resolves to exon coords)
    edit: "A>G @ 12"                        # ONLY for prime editing (REF>ALT @ 1-based pos)
    # Provide `sequence: "ACGT..."` ONLY if the user gives one; otherwise omit it
    # and set simulate.sequence_provider to fetch it.
  }
  strategy {
    modality: crispr_ko                    # crispr_ko | base_edit | prime_edit
    enzyme: auto                           # auto | SpCas9 | SaCas9 | Cas12a
    editor: CBE                            # base_edit only: CBE (C>T) or ABE (A>G)
  }
  constraints {
    on_target.min_efficiency: <0..1>
    off_target.max_cfd: <0..1>
    guides.count: <int>
    avoid: [ homopolymer(>=4), restriction_site(BsaI) ]
  }
  simulate {
    sequence_provider: ensembl             # inline | ensembl | ncbi | fallback
    on_target: rule_set_1                  # or heuristic_gc
    off_target: mock_seed                  # or cas_offinder_cfd
    repair_outcome: mock_indel             # or indelphi
    base_edit_model: window_heuristic      # base_edit only; or behive
    prime_edit_model: pe_heuristic         # prime_edit only; or pridict
  }
  deliver: rnp                             # rnp | plasmid | lnp | aav
  validate: amplicon_seq
}

Rules: never invent a DNA sequence; if none is given, omit `sequence` and use
`sequence_provider: ensembl`. Include `strategy.editor` only for `base_edit`, and
`target.edit` only for `prime_edit`. Base/prime editing use SpCas9. Choose sensible
constraints if unspecified."""

_SYSTEM = (
    "You translate a natural-language gene-editing request into a Helix spec. "
    "You only author a reviewable spec; a deterministic compiler does the design.\n\n"
    + _GRAMMAR_GUIDE
)


class SpecAuthoringError(RuntimeError):
    """Raised when the agent cannot produce parseable Helix within the retry budget."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip()


class SpecAuthor:
    """Draft (and self-repair) a Helix spec from natural language."""

    def __init__(self, client: LLMClient, max_attempts: int = 3):
        self._client = client
        self.max_attempts = max_attempts

    def draft(self, request: str) -> str:
        """Return validated Helix source for ``request`` (raises on repeated failure)."""
        last_error = ""
        for attempt in range(self.max_attempts):
            user = request
            if last_error:
                user += (
                    f"\n\nYour previous attempt did not parse:\n{last_error}\n"
                    "Return corrected Helix source only."
                )
            source = _strip_fences(self._client.complete(_SYSTEM, user, max_tokens=1500))
            try:
                parse_helix(source)  # deterministic gatekeeper
                return source
            except HelixSyntaxError as exc:
                last_error = str(exc)
        raise SpecAuthoringError(
            f"No valid Helix after {self.max_attempts} attempts. Last error: {last_error}"
        )

    def draft_spec(self, request: str) -> ExperimentSpec:
        """Draft and return the parsed spec object."""
        return parse_helix(self.draft(request))
