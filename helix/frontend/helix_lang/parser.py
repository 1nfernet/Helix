"""Recursive-descent parser: tokens -> AST.

Grammar (informal EBNF; see GRAMMAR.md):

    program    = "helix" STRING block
    block      = "{" statement* "}"
    statement  = key ( ":" value block? | block )        ";"?
    key        = IDENT ( "." IDENT )*
    value      = STRING | NUMBER | BOOL | call | list | IDENT
    call       = IDENT "(" ( arg ( "," arg )* )? ")"
    arg        = CMP NUMBER | value ( ".." NUMBER )?
    list       = "[" ( value ( "," value )* )? "]"

A single token of lookahead disambiguates every production, so the parser is a
straight recursive descent with no backtracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

from helix.frontend.helix_lang import lexer as L
from helix.frontend.helix_lang.errors import HelixSyntaxError
from helix.frontend.helix_lang.lexer import Token

# --- AST value nodes ----------------------------------------------------


@dataclass
class Str:
    value: str


@dataclass
class Num:
    value: Union[int, float]


@dataclass
class Bool:
    value: bool


@dataclass
class Ident:
    name: str


@dataclass
class Call:
    name: str
    args: List["Node"] = field(default_factory=list)


@dataclass
class ListNode:
    items: List["Node"] = field(default_factory=list)


@dataclass
class Compare:
    op: str
    value: Num


@dataclass
class Range:
    lo: int
    hi: int


Node = Union[Str, Num, Bool, Ident, Call, ListNode, Compare, Range]


# --- AST statement nodes ------------------------------------------------


@dataclass
class Assign:
    key: List[str]
    value: Node
    line: int
    col: int


@dataclass
class Block:
    key: List[str]
    head: Optional[Call]
    body: List["Stmt"]
    line: int
    col: int


Stmt = Union[Assign, Block]


@dataclass
class Experiment:
    name: str
    body: List[Stmt]


# --- parser -------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: List[Token], source: Optional[str] = None):
        self.tokens = tokens
        self.pos = 0
        self.source = source

    # token helpers
    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _at(self, ttype: str) -> bool:
        return self._peek().type == ttype

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, ttype: str) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            self._error(f"expected {ttype} but found {tok.type} {tok.value!r}", tok)
        return self._advance()

    def _error(self, message: str, tok: Optional[Token] = None):
        tok = tok or self._peek()
        raise HelixSyntaxError(message, tok.line, tok.col, self.source)

    # grammar
    def parse_program(self) -> Experiment:
        head = self._expect(L.IDENT)
        if head.value != "helix":
            self._error(f"expected 'helix' at top level, got {head.value!r}", head)
        name = self._expect(L.STRING).value
        body = self._parse_block()
        self._expect(L.EOF)
        return Experiment(name=name, body=body)

    def _parse_block(self) -> List[Stmt]:
        self._expect(L.LBRACE)
        stmts: List[Stmt] = []
        while not self._at(L.RBRACE):
            if self._at(L.SEMI):
                self._advance()
                continue
            if self._at(L.EOF):
                self._error("unexpected end of input: missing '}'")
            stmts.append(self._parse_statement())
        self._expect(L.RBRACE)
        return stmts

    def _parse_statement(self) -> Stmt:
        first = self._peek()
        key = self._parse_key()
        if self._at(L.COLON):
            self._advance()
            value = self._parse_value()
            if self._at(L.LBRACE):
                if not isinstance(value, Call):
                    self._error("a block header must be a call like gene(TP53)", first)
                body = self._parse_block()
                return Block(key=key, head=value, body=body, line=first.line, col=first.col)
            return Assign(key=key, value=value, line=first.line, col=first.col)
        if self._at(L.LBRACE):
            body = self._parse_block()
            return Block(key=key, head=None, body=body, line=first.line, col=first.col)
        self._error("expected ':' or '{' after key")

    def _parse_key(self) -> List[str]:
        names = [self._expect(L.IDENT).value]
        while self._at(L.DOT):
            self._advance()
            names.append(self._expect(L.IDENT).value)
        return names

    def _parse_value(self) -> Node:
        tok = self._peek()
        if tok.type == L.STRING:
            self._advance()
            return Str(tok.value)
        if tok.type == L.NUMBER:
            self._advance()
            return Num(_to_number(tok.value))
        if tok.type == L.IDENT:
            self._advance()
            if tok.value in ("true", "false"):
                return Bool(tok.value == "true")
            if self._at(L.LPAREN):
                return self._parse_call(tok.value)
            return Ident(tok.value)
        if tok.type == L.LBRACK:
            return self._parse_list()
        self._error(f"expected a value but found {tok.type} {tok.value!r}", tok)

    def _parse_call(self, name: str) -> Call:
        self._expect(L.LPAREN)
        args: List[Node] = []
        if not self._at(L.RPAREN):
            args.append(self._parse_arg())
            while self._at(L.COMMA):
                self._advance()
                if self._at(L.RPAREN):  # tolerate trailing comma
                    break
                args.append(self._parse_arg())
        self._expect(L.RPAREN)
        return Call(name=name, args=args)

    def _parse_arg(self) -> Node:
        if self._at(L.CMP):
            op = self._advance().value
            num = self._expect(L.NUMBER)
            return Compare(op=op, value=Num(_to_number(num.value)))
        value = self._parse_value()
        if self._at(L.RANGE):
            self._advance()
            hi = self._expect(L.NUMBER)
            if not isinstance(value, Num):
                self._error("range bounds must be numbers")
            return Range(lo=int(value.value), hi=_to_number(hi.value))
        return value

    def _parse_list(self) -> ListNode:
        self._expect(L.LBRACK)
        items: List[Node] = []
        if not self._at(L.RBRACK):
            items.append(self._parse_value())
            while self._at(L.COMMA):
                self._advance()
                if self._at(L.RBRACK):
                    break
                items.append(self._parse_value())
        self._expect(L.RBRACK)
        return ListNode(items=items)


def _to_number(text: str) -> Union[int, float]:
    return float(text) if "." in text else int(text)


def parse(tokens: List[Token], source: Optional[str] = None) -> Experiment:
    return _Parser(tokens, source=source).parse_program()
