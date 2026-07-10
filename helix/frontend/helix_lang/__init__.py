"""The Helix language frontend: source text -> ``ExperimentSpec``.

A small, hand-written lexer + recursive-descent parser (zero third-party deps, so
Helix keeps running out of the box) turns ``.hx`` source into an AST, which
:mod:`helix.frontend.helix_lang.transform` maps onto the same IR the YAML
frontend produces. The grammar is documented in ``helix/frontend/helix_lang/GRAMMAR.md``.
"""

from __future__ import annotations

from helix.frontend.helix_lang.errors import HelixSyntaxError
from helix.frontend.helix_lang.lexer import tokenize
from helix.frontend.helix_lang.parser import parse
from helix.frontend.helix_lang.transform import to_spec_dict


def parse_helix(source: str):
    """Compile Helix source text into a validated ``ExperimentSpec``."""
    from helix.frontend.loader import spec_from_dict  # local: avoid import cycle

    ast = parse(tokenize(source), source=source)
    return spec_from_dict(to_spec_dict(ast))


__all__ = ["parse_helix", "tokenize", "parse", "to_spec_dict", "HelixSyntaxError"]
