# `particle_classifier_expr.py`

Core expression-logic engine for the Particle Classifier node.

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

---

## Constants

| Name | Value |
|------|-------|
| `_STRUCTURAL_CHARS` | `set('+,;[]{}!()')` |
| `_ISOTOPE_TOKEN_RE` | `re.compile('\\d+[A-Za-z]{1,2}')` |
| `_ISOTOPE_STRICT_RE` | `re.compile('^\\d+[A-Z][a-z]?$')` |

## Classes

### `ExpressionSyntaxError` *(extends `Exception`)*

Raised for any malformed classifier expression.

Args:
    message (str): What was expected, what was found, and where.
    position (int | None): Character offset into the source string, if
        known, for caret-style error display in the UI layer.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, message: str, position: int \| None=None)` |  |

### `Token`

One lexical token.

Attributes:
    kind (str): One of 'ISOTOPE' or the literal structural character
        itself ('+', ',', ';', '[', ']', '{', '}', '!', '(', ')').
    value (str): The raw token text.
    position (int): Character offset in the source string where the
        token starts.

### `Isotope`

AST leaf: a single isotope label (raw 'Mass+Symbol' form, e.g. '107Ag').

Attributes:
    label (str): The isotope token text.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label: str)` |  |
| `__repr__` | `(self)` |  |
| `__eq__` | `(self, other)` |  |

### `And`

AST node: n-ary AND of sub-expressions (bare '+' operator).

Attributes:
    terms (list): Sub-expression nodes, all of which must hold.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, terms: list)` |  |
| `__repr__` | `(self)` |  |

### `Or`

AST node: inclusive OR across branches (``[a, b, c]``).

Attributes:
    branches (list): Sub-expression nodes; at least one must hold.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, branches: list)` |  |
| `__repr__` | `(self)` |  |

### `Xor`

AST node: one-hot XOR across branches (``{a; b; c}``).

Exactly one branch must hold — this is one-hot semantics, not classic
parity XOR, which matters once there are 3+ branches (design §8).

Attributes:
    branches (list): Sub-expression nodes; exactly one must hold.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, branches: list)` |  |
| `__repr__` | `(self)` |  |

### `Not`

AST node: negation of a bracketed sub-expression (``!(expr)``).

Attributes:
    inner: The negated sub-expression node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, inner)` |  |
| `__repr__` | `(self)` |  |

### `_Parser`

Recursive-descent parser over a token list. Internal to this module.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, tokens: list[Token], source: str)` |  |
| `_peek` | `(self) → Token \| None` |  |
| `_advance` | `(self) → Token` |  |
| `_expect` | `(self, kind: str) → Token` |  |
| `parse` | `(self) → AstNode` |  |
| `_parse_expression` | `(self) → AstNode` |  |
| `_parse_term` | `(self) → AstNode` |  |
| `_parse_or_group` | `(self) → Or` |  |
| `_parse_xor_group` | `(self) → Xor` |  |
| `_parse_not_group` | `(self) → Not` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `tokenize` | `(text: str) → list[Token]` | Tokenize a classifier expression string. |
| `parse` | `(text: str) → AstNode` | Tokenize and parse a classifier expression into an AST. |
| `referenced_isotopes` | `(ast: AstNode) → set[str]` | Collect every isotope label referenced anywhere in an AST. |
| `_eval_partial` | `(ast: AstNode, present: set[str]) → bool` |  |
| `evaluate` | `(ast: AstNode, present: set[str], mode: Literal['exact', 'partial']) →` | Evaluate a parsed expression against a particle's present isotopes. |
| `find_confound` | `(ast_a: AstNode, ast_b: AstNode, mode_a: Literal['exact', 'partial']='` | Check whether two formulas can both be satisfied by the same particle. |
| `classify_formula` | `(ast: AstNode) → Literal['contradiction', 'tautology', 'normal']` | Classify a single formula as a contradiction, tautology, or normal. |
