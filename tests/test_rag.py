"""Tests for RAG-backed strategy: retriever ranking + grounded resolution (offline)."""

import json

import pytest

from helix.agents.knowledge import InMemoryRetriever, Passage, default_retriever
from helix.agents.strategy import DeterministicStrategyResolver, RAGStrategyResolver
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec
from helix.ir.enums import Enzyme


class FakeLLM:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def complete(self, system, user, *, max_tokens=1024):
        self.calls.append((system, user))
        return self._response


def _auto_spec(**over):
    data = {"name": "s", "target": {"gene": "TP53", "sequence": "ACGT" * 8},
            "strategy": {"enzyme": "auto"}}
    data.update(over)
    return parse_spec(data)


# --- retriever ----------------------------------------------------------


def test_retriever_ranks_relevant_passage_first():
    r = default_retriever()
    assert r.search("TTTV AT-rich staggered cut multiplexing", k=1)[0].id == "cas12a"
    assert r.search("install a point mutation without a double-strand break", k=1)[0].id == "base_edit"


def test_retriever_returns_only_positive_matches():
    r = InMemoryRetriever([Passage("a", "nuclease knockout", "src")])
    assert r.search("completely unrelated xyzzy", k=3) == []


# --- RAG resolver -------------------------------------------------------


def test_rag_resolver_returns_enzyme_and_maps_citations():
    llm = FakeLLM(json.dumps({"enzyme": "SpCas9", "rationale": "default nuclease",
                              "citations": ["spcas9"]}))
    resolver = RAGStrategyResolver(llm)
    assert resolver.resolve_enzyme(_auto_spec()) is Enzyme.SPCAS9
    assert resolver.last_citations == ["Jinek et al., Science 2012"]
    # the retrieved passages were injected into the prompt (grounding)
    assert "PAM" in resolver._client.calls[0][1]


def test_rag_resolver_skips_when_enzyme_explicit():
    llm = FakeLLM("{}")
    spec = parse_spec({"name": "s", "target": {"gene": "X", "sequence": "ACGT" * 8},
                       "strategy": {"enzyme": "SpCas9"}})
    assert RAGStrategyResolver(llm).resolve_enzyme(spec) is Enzyme.SPCAS9
    assert llm.calls == []


def test_rag_resolver_falls_back_on_bad_output():
    resolver = RAGStrategyResolver(FakeLLM("not json"), fallback=DeterministicStrategyResolver())
    assert resolver.resolve_enzyme(_auto_spec()) is Enzyme.SPCAS9
    assert resolver.last_citations  # citations still recorded from retrieval


def test_pipeline_with_rag_strategy():
    llm = FakeLLM(json.dumps({"enzyme": "SpCas9", "citations": ["spcas9"]}))
    design = compile_spec(_auto_spec(), strategy=RAGStrategyResolver(llm))
    assert design.resolved_enzyme is Enzyme.SPCAS9
    assert design.provenance.adapters["strategy"].startswith("rag@")
