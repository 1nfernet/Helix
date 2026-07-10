"""Syntax errors with source location and a caret snippet."""

from __future__ import annotations

from typing import Optional


class HelixSyntaxError(SyntaxError):
    """Raised for lexing/parsing/transform errors in Helix source."""

    def __init__(self, message: str, line: int, col: int, source: Optional[str] = None):
        self.line = line
        self.col = col
        detail = f"{message} (line {line}, col {col})"
        if source:
            detail += "\n" + _snippet(source, line, col)
        super().__init__(detail)


def _snippet(source: str, line: int, col: int) -> str:
    lines = source.splitlines()
    if not (1 <= line <= len(lines)):
        return ""
    text = lines[line - 1]
    caret = " " * (max(col, 1) - 1) + "^"
    return f"  {text}\n  {caret}"
