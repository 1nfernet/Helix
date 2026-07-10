"""LLM-backed agents — the *only* place non-determinism is allowed.

Agents resolve ambiguity the declarative spec left open (e.g. ``enzyme: auto``),
reason over literature, and explain results. Each agent implements a narrow,
typed interface with a deterministic default so the whole pipeline runs offline
today; an LLM implementation is a drop-in that satisfies the same interface.

Crucially, an agent may only *emit or edit a spec* (or annotate a design). It
never computes the design itself — that is the deterministic compiler's job.
This keeps the trust boundary auditable.
"""

from helix.agents.authoring import SpecAuthor, SpecAuthoringError
from helix.agents.critic import Critique, CritiqueFinding, DesignCritic, apply_constraint_edits
from helix.agents.knowledge import InMemoryRetriever, Passage, Retriever, default_retriever
from helix.agents.llm import AnthropicClient, LLMClient, LLMNotConfigured
from helix.agents.refine import RefineLoop, RefineResult, RefineStep
from helix.agents.strategy import (
    DeliveryAwareStrategyResolver,
    DeterministicStrategyResolver,
    LLMStrategyResolver,
    RAGStrategyResolver,
    StrategyResolver,
)

__all__ = [
    "StrategyResolver",
    "DeterministicStrategyResolver",
    "DeliveryAwareStrategyResolver",
    "LLMStrategyResolver",
    "RAGStrategyResolver",
    "Retriever",
    "InMemoryRetriever",
    "Passage",
    "default_retriever",
    "SpecAuthor",
    "SpecAuthoringError",
    "DesignCritic",
    "Critique",
    "CritiqueFinding",
    "apply_constraint_edits",
    "RefineLoop",
    "RefineResult",
    "RefineStep",
    "LLMClient",
    "AnthropicClient",
    "LLMNotConfigured",
]
