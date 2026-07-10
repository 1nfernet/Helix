"""Tokenizer for the Helix language.

Hand-written scanner tracking (line, col) on every token so the parser and
transform can produce precise error messages. Whitespace, newlines, and ``#``
comments are insignificant; ``;`` is an optional, ignored separator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from helix.frontend.helix_lang.errors import HelixSyntaxError

# Token types (plain string constants keep tracebacks readable).
STRING = "STRING"
NUMBER = "NUMBER"
IDENT = "IDENT"
LBRACE, RBRACE = "LBRACE", "RBRACE"
LBRACK, RBRACK = "LBRACK", "RBRACK"
LPAREN, RPAREN = "LPAREN", "RPAREN"
COLON, COMMA, DOT, SEMI = "COLON", "COMMA", "DOT", "SEMI"
RANGE = "RANGE"  # ..
CMP = "CMP"  # >= <= > < =
EOF = "EOF"

_SINGLE = {
    "{": LBRACE,
    "}": RBRACE,
    "[": LBRACK,
    "]": RBRACK,
    "(": LPAREN,
    ")": RPAREN,
    ":": COLON,
    ",": COMMA,
    ";": SEMI,
}


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    line: int
    col: int


def _is_ident_start(c: str) -> bool:
    return c.isalpha() or c == "_"


def _is_ident_part(c: str) -> bool:
    return c.isalnum() or c == "_"


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i, line, col = 0, 1, 1
    n = len(source)

    def advance(k: int = 1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        c = source[i]

        # whitespace
        if c in " \t\r\n":
            advance()
            continue
        # comment to end of line
        if c == "#":
            while i < n and source[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col

        # two-char tokens first
        two = source[i : i + 2]
        if two == "..":
            tokens.append(Token(RANGE, "..", start_line, start_col))
            advance(2)
            continue
        if two in (">=", "<="):
            tokens.append(Token(CMP, two, start_line, start_col))
            advance(2)
            continue

        if c in _SINGLE:
            tokens.append(Token(_SINGLE[c], c, start_line, start_col))
            advance()
            continue
        if c == ".":
            tokens.append(Token(DOT, ".", start_line, start_col))
            advance()
            continue
        if c in "<>=":
            tokens.append(Token(CMP, c, start_line, start_col))
            advance()
            continue

        if c == '"':
            advance()  # opening quote
            chars = []
            while i < n and source[i] != '"':
                if source[i] == "\\" and i + 1 < n:
                    advance()
                chars.append(source[i])
                advance()
            if i >= n:
                raise HelixSyntaxError("unterminated string", start_line, start_col, source)
            advance()  # closing quote
            tokens.append(Token(STRING, "".join(chars), start_line, start_col))
            continue

        if c.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            # decimal only if a single '.' not part of '..'
            if j < n and source[j] == "." and not (j + 1 < n and source[j + 1] == "."):
                j += 1
                while j < n and source[j].isdigit():
                    j += 1
            text = source[i:j]
            advance(j - i)
            tokens.append(Token(NUMBER, text, start_line, start_col))
            continue

        if _is_ident_start(c):
            j = i
            while j < n and _is_ident_part(source[j]):
                j += 1
            text = source[i:j]
            advance(j - i)
            tokens.append(Token(IDENT, text, start_line, start_col))
            continue

        raise HelixSyntaxError(f"unexpected character {c!r}", start_line, start_col, source)

    tokens.append(Token(EOF, "", line, col))
    return tokens
