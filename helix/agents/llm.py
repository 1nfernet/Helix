"""LLM client abstraction for Helix agents.

Every agent talks to an :class:`LLMClient` — a one-method interface. The default
implementation calls the Anthropic API (lazy import, key from ``ANTHROPIC_API_KEY``);
tests inject a fake client, so agent logic is covered offline with no network,
no key, and no dependency. This mirrors how the external *tools* are wired
(injectable transports), applied to the external *model*.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional, Protocol, runtime_checkable

# Cheap, fast default that is plenty for structured spec authoring; override via
# HELIX_LLM_MODEL or per-request (e.g. "claude-sonnet-5" for harder requests).
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Approximate USD per 1M tokens (input, output). List prices change — see
# console.anthropic.com/settings/billing; used only for a rough cost readout.
MODEL_PRICING = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
}


def estimate_cost(model: str, usage: Optional[dict]) -> Optional[float]:
    """Rough USD estimate for one call from its token usage (None if unknown)."""
    if not usage:
        return None
    price = next((p for k, p in MODEL_PRICING.items() if (model or "").startswith(k)), None)
    if not price:
        return None
    pin, pout = price
    fresh = usage.get("input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cost = (fresh + cache_read * 0.1 + cache_write * 1.25) * pin / 1e6 + out * pout / 1e6
    return round(cost, 5)


def llm_configured() -> bool:
    """True if an LLM backend could run (offline demo, or package + key present)."""
    if os.environ.get("HELIX_FAKE_LLM"):
        return True
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return the model's text response to a system+user prompt."""
        ...


class LLMNotConfigured(RuntimeError):
    """Raised when no usable LLM backend is available (missing package or key)."""


class AnthropicClient:
    """Default client backed by the Anthropic API."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.environ.get("HELIX_LLM_MODEL", DEFAULT_MODEL)
        self._api_key = api_key
        self._client = None
        self.last_usage: Optional[dict] = None  # token usage of the most recent call

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise LLMNotConfigured(
                "The 'anthropic' package is not installed. `pip install anthropic` "
                "or inject a custom LLMClient."
            ) from exc
        key = self._api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMNotConfigured("Set ANTHROPIC_API_KEY to use the Anthropic client.")
        self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        client = self._ensure_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            # Cache the (static, sizeable) system prompt so repeated calls — critique/
            # refine loops, several drafts — pay ~10% for it on a cache hit.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        u = getattr(message, "usage", None)
        self.last_usage = {
            "input_tokens": getattr(u, "input_tokens", 0),
            "output_tokens": getattr(u, "output_tokens", 0),
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        } if u else None
        return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")


def extract_json_object(text: str) -> dict:
    """Best-effort parse of a single JSON object from an LLM reply.

    Tolerates code fences and surrounding prose by grabbing the outermost braces.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object found in LLM reply: {text!r}")
    return json.loads(candidate[start : end + 1])
