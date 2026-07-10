"""Strategy resolution: turn ``enzyme: auto`` into a concrete choice.

The MVP ships a deterministic resolver so the pipeline is fully offline and
testable. In Phase 2 an ``LLMStrategyResolver`` implements the same
:class:`StrategyResolver` protocol, choosing enzyme/modality from the edit goal,
constraints, and retrieved literature — but it still only *fills in the spec*,
handing a concrete enzyme back to the deterministic compiler.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from helix.agents.knowledge import Retriever, default_retriever
from helix.agents.llm import LLMClient, extract_json_object
from helix.ir.enums import DeliveryMethod, Enzyme, Modality
from helix.ir.spec import ExperimentSpec


@runtime_checkable
class StrategyResolver(Protocol):
    def resolve_enzyme(self, spec: ExperimentSpec) -> Enzyme:
        ...


class DeterministicStrategyResolver:
    """Rule-based default. Honours an explicit enzyme; otherwise picks a sane one."""

    name = "deterministic"
    version = "0.1.0"

    def resolve_enzyme(self, spec: ExperimentSpec) -> Enzyme:
        chosen = spec.strategy.enzyme
        if chosen is not Enzyme.AUTO:
            return chosen
        # Knockout -> SpCas9; base/prime editors are SpCas9-derived.
        if spec.strategy.modality in (
            Modality.CRISPR_KO,
            Modality.BASE_EDIT,
            Modality.PRIME_EDIT,
        ):
            return Enzyme.SPCAS9
        raise ValueError(
            f"Cannot auto-select an enzyme for modality {spec.strategy.modality}."
        )


class DeliveryAwareStrategyResolver:
    """Delivery-aware default: pick the enzyme that fits the intended delivery.

    AAV has a ~4.7 kb single-vector packaging limit; SpCas9 (4.1 kb CDS) is tight
    once a promoter, polyA and the sgRNA are added, so for an AAV knockout the
    compact SaCas9 (3.2 kb) is the better fit. Everything else defaults to SpCas9
    (best-characterised). Honours an explicit enzyme. Base/prime editing stay on
    SpCas9 (the only enzyme those designers support).
    """

    name = "delivery_aware"
    version = "0.1.0"

    def resolve_enzyme(self, spec: ExperimentSpec) -> Enzyme:
        chosen = spec.strategy.enzyme
        if chosen is not Enzyme.AUTO:
            return chosen
        if spec.strategy.modality is Modality.CRISPR_KO and spec.deliver is DeliveryMethod.AAV:
            return Enzyme.SACAS9  # compact enough for single-AAV packaging
        return Enzyme.SPCAS9


# Enzymes the compiler can actually design for today. The LLM may only choose
# from this set — its output is validated, never trusted blindly.
_SELECTABLE = [Enzyme.SPCAS9]

_SYSTEM = (
    "You are a CRISPR strategy advisor inside a deterministic design compiler. "
    "Given an editing goal, pick exactly one enzyme from the allowed list. "
    "You are NOT designing the experiment — you only fill in this one choice, "
    "which a compiler then acts on. Reply with a JSON object: "
    '{"enzyme": "<one of the allowed values>", "rationale": "<one sentence>"}.'
)


class LLMStrategyResolver:
    """Resolve ``enzyme: auto`` with an LLM; validate the choice deterministically.

    Implements the same :class:`StrategyResolver` protocol as the deterministic
    resolver. The LLM's answer is checked against :data:`_SELECTABLE`; anything
    else is a hard error (optionally softened by a deterministic fallback), so a
    hallucinated enzyme can never reach the compiler.
    """

    name = "llm"

    def __init__(
        self,
        client: LLMClient,
        model_label: str = "llm",
        fallback: Optional[StrategyResolver] = None,
    ):
        self._client = client
        self.version = model_label
        self._fallback = fallback

    def resolve_enzyme(self, spec: ExperimentSpec) -> Enzyme:
        if spec.strategy.enzyme is not Enzyme.AUTO:
            return spec.strategy.enzyme

        allowed = [e.value for e in _SELECTABLE]
        user = (
            f"Goal: {spec.target.goal.value}\n"
            f"Modality: {spec.strategy.modality.value}\n"
            f"Organism: {spec.organism} ({spec.genome_build})\n"
            f"Allowed enzymes: {allowed}\n"
            "Choose one."
        )
        try:
            data = extract_json_object(self._client.complete(_SYSTEM, user, max_tokens=300))
            choice = Enzyme(str(data["enzyme"]))
            if choice not in _SELECTABLE:
                raise ValueError(f"enzyme {choice} is not selectable")
            return choice
        except Exception as exc:
            if self._fallback is not None:
                return self._fallback.resolve_enzyme(spec)
            raise ValueError(f"LLM strategy resolution failed: {exc}") from exc


_RAG_SYSTEM = (
    "You are a CRISPR strategy advisor inside a deterministic compiler. Use ONLY the "
    "retrieved literature passages to choose exactly one enzyme from the allowed list, "
    "and cite the supporting passage id(s). You only fill in this one choice. Reply with "
    'JSON: {"enzyme": "<allowed value>", "rationale": "<one sentence>", "citations": ["<id>"]}.'
)


class RAGStrategyResolver:
    """Resolve ``enzyme: auto`` using retrieved literature (RAG), with citations.

    Retrieves relevant passages, hands them to the LLM as grounding, validates the
    enzyme against the selectable set, and records the cited sources on
    ``last_citations`` for surfacing to the user.
    """

    name = "rag"

    def __init__(
        self,
        client: LLMClient,
        retriever: Optional[Retriever] = None,
        model_label: str = "rag",
        fallback: Optional[StrategyResolver] = None,
    ):
        self._client = client
        self._retriever = retriever or default_retriever()
        self.version = model_label
        self._fallback = fallback
        self.last_citations: list = []

    def resolve_enzyme(self, spec: ExperimentSpec) -> Enzyme:
        if spec.strategy.enzyme is not Enzyme.AUTO:
            return spec.strategy.enzyme

        query = (
            f"{spec.strategy.modality.value} {spec.target.goal.value} {spec.organism} "
            "enzyme choice nuclease knockout PAM"
        )
        passages = self._retriever.search(query, k=3)
        id_to_source = {p.id: p.source for p in passages}
        context = "\n".join(f"[{p.id}] {p.text} (source: {p.source})" for p in passages) or "(none)"
        allowed = [e.value for e in _SELECTABLE]
        user = (
            f"Retrieved literature:\n{context}\n\n"
            f"Goal: {spec.target.goal.value}\nModality: {spec.strategy.modality.value}\n"
            f"Organism: {spec.organism}\nAllowed enzymes: {allowed}\n"
            "Choose one enzyme and cite the passage id(s) supporting it."
        )
        try:
            data = extract_json_object(self._client.complete(_RAG_SYSTEM, user, max_tokens=400))
            choice = Enzyme(str(data["enzyme"]))
            if choice not in _SELECTABLE:
                raise ValueError(f"enzyme {choice} is not selectable")
            cited = data.get("citations", []) or []
            self.last_citations = [id_to_source.get(c, c) for c in cited] or [p.source for p in passages]
            return choice
        except Exception as exc:
            self.last_citations = [p.source for p in passages]
            if self._fallback is not None:
                return self._fallback.resolve_enzyme(spec)
            raise ValueError(f"RAG strategy resolution failed: {exc}") from exc
