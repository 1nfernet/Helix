"""Tests for the Phase-2 LLM agents.

All offline: a fake LLM client returns canned text, so we test the agent logic
(prompting, validation, self-repair, the trust boundary) without a network or key.
"""

import pytest

from helix.agents.authoring import SpecAuthor, SpecAuthoringError
from helix.agents.llm import AnthropicClient, LLMNotConfigured, extract_json_object
from helix.agents.strategy import DeterministicStrategyResolver, LLMStrategyResolver
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec
from helix.ir.enums import Enzyme

VALID_HX = 'helix "x" {\n  target: gene(TP53) { goal: knockout }\n}'
INVALID_HX = 'helix "x" {\n  target: gene(TP53) { goal knockout }\n}'  # missing ':'


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, system, user, *, max_tokens=1024):
        self.calls.append((system, user))
        return self._responses.pop(0)


def _auto_spec():
    return parse_spec({"name": "s", "target": {"gene": "TP53", "sequence": "ACGT" * 8},
                       "strategy": {"enzyme": "auto"}})


# --- strategy resolver --------------------------------------------------


def test_llm_resolver_returns_validated_enzyme():
    llm = FakeLLM(['{"enzyme": "SpCas9", "rationale": "well characterised"}'])
    assert LLMStrategyResolver(llm).resolve_enzyme(_auto_spec()) is Enzyme.SPCAS9
    assert len(llm.calls) == 1


def test_llm_resolver_skips_llm_when_enzyme_explicit():
    llm = FakeLLM([])  # would IndexError if called
    spec = parse_spec({"name": "s", "target": {"gene": "X", "sequence": "ACGT" * 8},
                       "strategy": {"enzyme": "SpCas9"}})
    assert LLMStrategyResolver(llm).resolve_enzyme(spec) is Enzyme.SPCAS9
    assert llm.calls == []


def test_llm_resolver_rejects_hallucinated_enzyme_with_fallback():
    llm = FakeLLM(['{"enzyme": "MadeUpCas99"}'])
    resolver = LLMStrategyResolver(llm, fallback=DeterministicStrategyResolver())
    assert resolver.resolve_enzyme(_auto_spec()) is Enzyme.SPCAS9  # fell back


def test_llm_resolver_raises_without_fallback_on_bad_output():
    llm = FakeLLM(["not json at all"])
    with pytest.raises(ValueError):
        LLMStrategyResolver(llm).resolve_enzyme(_auto_spec())


def test_pipeline_with_llm_strategy():
    llm = FakeLLM(['{"enzyme": "SpCas9"}'])
    design = compile_spec(_auto_spec(), strategy=LLMStrategyResolver(llm))
    assert design.resolved_enzyme is Enzyme.SPCAS9


# --- authoring agent ----------------------------------------------------


def test_author_strips_fences_and_validates():
    author = SpecAuthor(FakeLLM(["```hx\n" + VALID_HX + "\n```"]))
    src = author.draft("knock out TP53")
    assert "helix" in src and "```" not in src


def test_author_self_repairs_on_parse_error():
    llm = FakeLLM([INVALID_HX, VALID_HX])
    author = SpecAuthor(llm, max_attempts=3)
    src = author.draft("knock out TP53")
    assert src.strip() == VALID_HX
    assert len(llm.calls) == 2
    assert "did not parse" in llm.calls[1][1]  # error fed back to the model


def test_author_gives_up_after_max_attempts():
    author = SpecAuthor(FakeLLM([INVALID_HX, INVALID_HX]), max_attempts=2)
    with pytest.raises(SpecAuthoringError):
        author.draft("knock out TP53")


def test_draft_spec_parses_to_expected_target():
    spec = SpecAuthor(FakeLLM([VALID_HX])).draft_spec("knock out TP53")
    assert spec.target.gene == "TP53"


# --- default client not configured --------------------------------------


def test_anthropic_client_errors_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMNotConfigured):
        AnthropicClient(api_key=None).complete("sys", "user")


# --- json extraction ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ['{"enzyme": "SpCas9"}', 'here: {"enzyme": "SpCas9"} ok', '```json\n{"enzyme": "SpCas9"}\n```'],
)
def test_extract_json_object(text):
    assert extract_json_object(text)["enzyme"] == "SpCas9"


def test_extract_json_object_raises_on_junk():
    with pytest.raises(ValueError):
        extract_json_object("no braces here")
