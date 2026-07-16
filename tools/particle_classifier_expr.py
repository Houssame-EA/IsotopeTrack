# -*- coding: utf-8 -*-
"""Core expression-logic engine for the Particle Classifier node.

Implements the strict composition-logic grammar from
``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §8: a tokenizer, a recursive-descent
parser producing an AST, an evaluator (exact/partial semantics), and two
structural (particle-data-independent) analyses used by the UI layer to warn
users about overlapping or self-contradictory definitions — confound
detection (§5) and contradiction/tautology classification (§9.3).

Grammar (§8), `+` is the only bare infix operator (n-ary AND); everything
else is bracket-delimited so there is never a precedence conflict::

    expression := term ( '+' term )*                     # AND, n-ary
    term       := isotope | or_group | xor_group | not_group | '(' expression ')'
    or_group   := '[' expression (',' expression)* ']'    # inclusive OR
    xor_group  := '{' expression (';' expression)* '}'    # ONE-HOT (not parity)
    not_group  := '!' '(' expression ')'                  # negation
    isotope    := mass number then correctly-cased symbol, e.g. 60Ni, 208Pb

This module is pure Python: no Qt, no particle data model, no canvas
registration. Those are later implementation stages.
"""

from __future__ import annotations

import itertools
import logging
import re
from dataclasses import dataclass
from typing import Literal

_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_expr")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ExpressionSyntaxError(Exception):
    """Raised for any malformed classifier expression.

    Args:
        message (str): What was expected, what was found, and where.
        position (int | None): Character offset into the source string, if
            known, for caret-style error display in the UI layer.
    """

    def __init__(self, message: str, position: int | None = None):
        self.position = position
        if position is not None:
            message = f"{message} (at position {position})"
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
_STRUCTURAL_CHARS = set("+,;[]{}!()")

# Mass number first, then a correctly-cased 1-2 letter element symbol,
# concatenated with no separator (e.g. "60Ni", "57Fe", "208Pb").
_ISOTOPE_TOKEN_RE = re.compile(r'\d+[A-Za-z]{1,2}')
_ISOTOPE_STRICT_RE = re.compile(r'^\d+[A-Z][a-z]?$')


@dataclass(frozen=True)
class Token:
    """One lexical token.

    Attributes:
        kind (str): One of 'ISOTOPE' or the literal structural character
            itself ('+', ',', ';', '[', ']', '{', '}', '!', '(', ')').
        value (str): The raw token text.
        position (int): Character offset in the source string where the
            token starts.
    """

    kind: str
    value: str
    position: int


def tokenize(text: str) -> list[Token]:
    """Tokenize a classifier expression string.

    Whitespace is tolerated only immediately around structural characters
    (``+ , ; [ ] { } ! ( )``) — never inside or adjacent to an isotope token
    itself. ``!`` is treated as a structural character for whitespace
    purposes; a ``(`` must still immediately follow it once whitespace (if
    any) is skipped, but that adjacency requirement is enforced by the
    parser, not the tokenizer (see module docstring / design §8).

    Args:
        text (str): Raw expression text.

    Returns:
        list[Token]: Tokens in source order (whitespace dropped).

    Raises:
        ExpressionSyntaxError: On any character that is neither whitespace,
            a structural character, nor part of a validly-formed isotope
            token (including incorrectly-cased symbols like "NI"/"ni").
    """
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _STRUCTURAL_CHARS:
            tokens.append(Token(ch, ch, i))
            i += 1
            continue
        if ch.isdigit():
            m = _ISOTOPE_TOKEN_RE.match(text, i)
            if not m:
                raise ExpressionSyntaxError(
                    f"Malformed isotope token starting with digit "
                    f"{text[i]!r}", i)
            raw = m.group(0)
            if not _ISOTOPE_STRICT_RE.match(raw):
                raise ExpressionSyntaxError(
                    f"Isotope symbol must be correctly cased "
                    f"(e.g. 'Ni', not 'NI'/'ni'); got {raw!r}", i)
            # Reject a token immediately followed by more isotope-token-like
            # characters glued on with no separator, e.g. "60Ni107Ag".
            end = m.end()
            if end < n and (text[end].isalnum()):
                raise ExpressionSyntaxError(
                    f"Isotope token {raw!r} is not separated from the "
                    f"following characters by a structural character", i)
            tokens.append(Token('ISOTOPE', raw, i))
            i = end
            continue
        raise ExpressionSyntaxError(f"Unexpected character {ch!r}", i)
    _itk_log.debug("tokenize: %r -> %d tokens", text, len(tokens))
    return tokens


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #
class Isotope:
    """AST leaf: a single isotope label (raw 'Mass+Symbol' form, e.g. '107Ag').

    Attributes:
        label (str): The isotope token text.
    """

    __slots__ = ('label',)

    def __init__(self, label: str):
        self.label = label

    def __repr__(self):
        return f"Isotope({self.label!r})"

    def __eq__(self, other):
        return isinstance(other, Isotope) and self.label == other.label


class And:
    """AST node: n-ary AND of sub-expressions (bare '+' operator).

    Attributes:
        terms (list): Sub-expression nodes, all of which must hold.
    """

    __slots__ = ('terms',)

    def __init__(self, terms: list):
        self.terms = terms

    def __repr__(self):
        return f"And({self.terms!r})"


class Or:
    """AST node: inclusive OR across branches (``[a, b, c]``).

    Attributes:
        branches (list): Sub-expression nodes; at least one must hold.
    """

    __slots__ = ('branches',)

    def __init__(self, branches: list):
        self.branches = branches

    def __repr__(self):
        return f"Or({self.branches!r})"


class Xor:
    """AST node: one-hot XOR across branches (``{a; b; c}``).

    Exactly one branch must hold — this is one-hot semantics, not classic
    parity XOR, which matters once there are 3+ branches (design §8).

    Attributes:
        branches (list): Sub-expression nodes; exactly one must hold.
    """

    __slots__ = ('branches',)

    def __init__(self, branches: list):
        self.branches = branches

    def __repr__(self):
        return f"Xor({self.branches!r})"


class Not:
    """AST node: negation of a bracketed sub-expression (``!(expr)``).

    Attributes:
        inner: The negated sub-expression node.
    """

    __slots__ = ('inner',)

    def __init__(self, inner):
        self.inner = inner

    def __repr__(self):
        return f"Not({self.inner!r})"


AstNode = Isotope | And | Or | Xor | Not


# --------------------------------------------------------------------------- #
# Parser (recursive descent)
# --------------------------------------------------------------------------- #
class _Parser:
    """Recursive-descent parser over a token list. Internal to this module."""

    def __init__(self, tokens: list[Token], source: str):
        self._toks = tokens
        self._source = source
        self._i = 0

    def _peek(self) -> Token | None:
        return self._toks[self._i] if self._i < len(self._toks) else None

    def _advance(self) -> Token:
        tok = self._peek()
        if tok is None:
            raise ExpressionSyntaxError(
                "Unexpected end of expression", len(self._source))
        self._i += 1
        return tok

    def _expect(self, kind: str) -> Token:
        tok = self._peek()
        if tok is None:
            raise ExpressionSyntaxError(
                f"Expected {kind!r} but reached end of expression",
                len(self._source))
        if tok.kind != kind:
            raise ExpressionSyntaxError(
                f"Expected {kind!r} but found {tok.value!r}", tok.position)
        self._i += 1
        return tok

    def parse(self) -> AstNode:
        if not self._toks:
            raise ExpressionSyntaxError("Empty expression", 0)
        node = self._parse_expression()
        if self._i != len(self._toks):
            tok = self._peek()
            raise ExpressionSyntaxError(
                f"Unexpected trailing token {tok.value!r}", tok.position)
        return node

    def _parse_expression(self) -> AstNode:
        terms = [self._parse_term()]
        while self._peek() is not None and self._peek().kind == '+':
            self._advance()
            terms.append(self._parse_term())
        return terms[0] if len(terms) == 1 else And(terms)

    def _parse_term(self) -> AstNode:
        tok = self._peek()
        if tok is None:
            raise ExpressionSyntaxError(
                "Expected a term but reached end of expression",
                len(self._source))
        if tok.kind == 'ISOTOPE':
            self._advance()
            return Isotope(tok.value)
        if tok.kind == '[':
            return self._parse_or_group()
        if tok.kind == '{':
            return self._parse_xor_group()
        if tok.kind == '!':
            return self._parse_not_group()
        if tok.kind == '(':
            self._advance()
            inner = self._parse_expression()
            self._expect(')')
            return inner
        raise ExpressionSyntaxError(
            f"Expected an isotope, '[', '{{', '!' or '(' but found "
            f"{tok.value!r}", tok.position)

    def _parse_or_group(self) -> Or:
        self._expect('[')
        branches = [self._parse_expression()]
        while self._peek() is not None and self._peek().kind == ',':
            self._advance()
            branches.append(self._parse_expression())
        self._expect(']')
        return Or(branches)

    def _parse_xor_group(self) -> Xor:
        self._expect('{')
        branches = [self._parse_expression()]
        while self._peek() is not None and self._peek().kind == ';':
            self._advance()
            branches.append(self._parse_expression())
        self._expect('}')
        return Xor(branches)

    def _parse_not_group(self) -> Not:
        bang = self._expect('!')
        tok = self._peek()
        if tok is None or tok.kind != '(':
            pos = tok.position if tok is not None else len(self._source)
            raise ExpressionSyntaxError(
                "'!' must be immediately followed by '(' "
                "(whitespace before '(' is allowed, but nothing else)", pos)
        self._advance()
        inner = self._parse_expression()
        self._expect(')')
        return Not(inner)


def parse(text: str) -> AstNode:
    """Tokenize and parse a classifier expression into an AST.

    Args:
        text (str): Raw expression text, per design §8 grammar.

    Returns:
        AstNode: Root of the parsed expression tree.

    Raises:
        ExpressionSyntaxError: On any malformed input — bad isotope token,
            mismatched/missing/wrong brackets, stray structural characters,
            empty expression, etc. No error recovery is attempted.
    """
    try:
        tokens = tokenize(text)
        ast = _Parser(tokens, text).parse()
    except ExpressionSyntaxError as exc:
        _itk_log.warning("parse failed for %r: %s", text, exc)
        raise
    _itk_log.debug("parse: %r -> %r", text, ast)
    return ast


# --------------------------------------------------------------------------- #
# Evaluator
# --------------------------------------------------------------------------- #
def referenced_isotopes(ast: AstNode) -> set[str]:
    """Collect every isotope label referenced anywhere in an AST.

    Args:
        ast (AstNode): A parsed expression tree.

    Returns:
        set[str]: All isotope labels appearing in the tree.
    """
    if isinstance(ast, Isotope):
        return {ast.label}
    if isinstance(ast, And):
        out: set[str] = set()
        for t in ast.terms:
            out |= referenced_isotopes(t)
        return out
    if isinstance(ast, (Or, Xor)):
        out = set()
        for b in ast.branches:
            out |= referenced_isotopes(b)
        return out
    if isinstance(ast, Not):
        return referenced_isotopes(ast.inner)
    raise TypeError(f"Unknown AST node type: {type(ast)!r}")


def _eval_partial(ast: AstNode, present: set[str]) -> bool:
    if isinstance(ast, Isotope):
        return ast.label in present
    if isinstance(ast, And):
        return all(_eval_partial(t, present) for t in ast.terms)
    if isinstance(ast, Or):
        return any(_eval_partial(b, present) for b in ast.branches)
    if isinstance(ast, Xor):
        return sum(1 for b in ast.branches if _eval_partial(b, present)) == 1
    if isinstance(ast, Not):
        return not _eval_partial(ast.inner, present)
    raise TypeError(f"Unknown AST node type: {type(ast)!r}")


def evaluate(ast: AstNode, present: set[str],
             mode: Literal["exact", "partial"]) -> bool:
    """Evaluate a parsed expression against a particle's present isotopes.

    Args:
        ast (AstNode): A parsed expression tree.
        present (set[str]): The particle's present isotope labels.
        mode ("exact" | "partial"): "partial" evaluates the AST against
            ``present`` using standard AND/OR/one-hot-XOR/NOT semantics,
            ignoring any isotopes in ``present`` outside the AST's own
            referenced vocabulary. "exact" additionally requires that
            ``present`` contains no isotopes outside that vocabulary at all.

    Returns:
        bool: Whether the particle matches.

    Raises:
        ValueError: If ``mode`` is not "exact" or "partial".
    """
    if mode not in ("exact", "partial"):
        raise ValueError(f"mode must be 'exact' or 'partial', got {mode!r}")
    result = _eval_partial(ast, present)
    if mode == "exact":
        vocab = referenced_isotopes(ast)
        if present - vocab:
            result = False
    return result


# --------------------------------------------------------------------------- #
# Structural analyses — confound detection, contradiction/tautology
# --------------------------------------------------------------------------- #
def find_confound(ast_a: AstNode, ast_b: AstNode,
                  mode_a: Literal["exact", "partial"] = "partial",
                  mode_b: Literal["exact", "partial"] = "partial",
                  ) -> frozenset[str] | None:
    """Check whether two formulas can both be satisfied by the same particle.

    Purely structural (design §5): enumerates every present/absent
    combination over the union of isotopes referenced by both ASTs — no
    particle data involved — and returns the first combination (as the set
    of isotopes marked "present") that satisfies both formulas
    simultaneously under each formula's own configured match mode, or None
    if no such combination exists. Bounded by referenced-isotope count, so
    it stays cheap enough to re-run on every edit.

    Each definition's own Exact/Partial setting (design §9.1) matters here:
    partial-match ignores isotopes outside a formula's own vocabulary, but
    exact-match additionally requires the particle to carry *no* isotopes
    outside that vocabulary. Two exact-match definitions with disjoint
    vocabularies can therefore never actually confound in practice — a real
    particle satisfying one exactly cannot simultaneously satisfy the
    other's "nothing outside my own vocabulary" constraint unless the
    vocabularies overlap enough to share a witness. Passing each side's
    real mode (rather than always assuming partial) avoids flagging that
    kind of false positive.

    Args:
        ast_a (AstNode): First definition's parsed expression.
        ast_b (AstNode): Second definition's parsed expression.
        mode_a ("exact" | "partial"): First definition's own match mode.
        mode_b ("exact" | "partial"): Second definition's own match mode.

    Returns:
        frozenset[str] | None: A witnessing present-isotope assignment that
            satisfies both formulas under their own modes, or None if they
            never overlap.
    """
    vocab = sorted(referenced_isotopes(ast_a) | referenced_isotopes(ast_b))
    for combo in itertools.product([False, True], repeat=len(vocab)):
        present = {label for label, on in zip(vocab, combo) if on}
        if evaluate(ast_a, present, mode_a) and evaluate(ast_b, present, mode_b):
            return frozenset(present)
    return None


def classify_formula(ast: AstNode) -> Literal["contradiction", "tautology", "normal"]:
    """Classify a single formula as a contradiction, tautology, or normal.

    Purely structural (design §9.3): enumerates every present/absent
    combination over the formula's own referenced isotopes under
    partial-match semantics.

    Args:
        ast (AstNode): A parsed expression tree.

    Returns:
        "contradiction": No combination satisfies the formula (it can never
            match any particle).
        "tautology": Every combination satisfies the formula.
        "normal": Neither of the above.
    """
    vocab = sorted(referenced_isotopes(ast))
    total = 0
    satisfied = 0
    for combo in itertools.product([False, True], repeat=len(vocab)):
        present = {label for label, on in zip(vocab, combo) if on}
        total += 1
        if _eval_partial(ast, present):
            satisfied += 1
    if satisfied == 0:
        result = "contradiction"
    elif satisfied == total:
        result = "tautology"
    else:
        result = "normal"
    _itk_log.info("classify_formula: %r -> %s (%d/%d rows satisfied)",
                   ast, result, satisfied, total)
    return result
