"""A small retrieval layer for RAG-backed strategy.

A ``Retriever`` returns passages relevant to a query. The default
``InMemoryRetriever`` ranks a bundled, curated corpus by TF-IDF — deterministic,
dependency-free, offline. An embedding-based retriever is a drop-in behind the
same Protocol. Passages carry real citations so the agent can attribute its choice.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass
class Passage:
    id: str
    text: str
    source: str  # citation


@runtime_checkable
class Retriever(Protocol):
    def search(self, query: str, k: int = 3) -> List[Passage]:
        ...


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


class InMemoryRetriever:
    """TF-IDF retriever over a fixed corpus."""

    def __init__(self, passages: List[Passage]):
        self._passages = passages
        self._tf = [Counter(_tokens(p.text)) for p in passages]
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = max(1, len(passages))
        self._idf = {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}

    def search(self, query: str, k: int = 3) -> List[Passage]:
        q_terms = set(_tokens(query))
        scored = []
        for passage, tf in zip(self._passages, self._tf):
            total = sum(tf.values()) or 1
            score = sum((tf[t] / total) * self._idf.get(t, 0.0) for t in q_terms)
            scored.append((score, passage))
        # Stable, deterministic ordering: score desc, then id.
        scored.sort(key=lambda s: (-s[0], s[1].id))
        return [p for score, p in scored[:k] if score > 0]


# Curated corpus: landmark references on enzyme/modality selection.
DEFAULT_CORPUS: List[Passage] = [
    Passage("spcas9", "SpCas9 is the general-purpose Streptococcus pyogenes nuclease with an NGG PAM "
            "and a 20 nt spacer, the default choice for gene knockout via NHEJ frameshift.",
            "Jinek et al., Science 2012"),
    Passage("sacas9", "SaCas9 is a smaller nuclease with an NNGRRT PAM; its compact size enables "
            "single-AAV delivery for in vivo knockout.",
            "Ran et al., Nature 2015"),
    Passage("cas12a", "Cas12a (Cpf1) recognizes a T-rich TTTV PAM 5' of the spacer and makes a "
            "staggered cut, useful for AT-rich targets and multiplexing.",
            "Zetsche et al., Cell 2015"),
    Passage("base_edit", "Base editors install point mutations (C>T for CBE, A>G for ABE) within a "
            "small activity window without a double-strand break, ideal for precise single-base changes.",
            "Komor et al., Nature 2016"),
    Passage("prime_edit", "Prime editing writes substitutions, small insertions, and deletions via a "
            "pegRNA without a double-strand break or donor DNA, offering versatile precise edits.",
            "Anzalone et al., Nature 2019"),
    Passage("offtarget", "Off-target risk depends on PAM-proximal mismatches and can be reduced by "
            "high-specificity variants and empirical off-target profiling (e.g. GUIDE-seq).",
            "Tsai et al., Nat Biotechnol 2015"),
]


def default_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(DEFAULT_CORPUS)
