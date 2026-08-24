# `formula_utils.py`

The functions of this module are there to help with formula manipulations
and stoichiometry.

---

## Constants

| Name | Value |
|------|-------|
| `_TOKEN_RE` | `re.compile('([A-Z][a-z]?\|\\(\|\\))(\\d*(?:\\.\\d+)?)')` |
| `_ELEMENT_ORDER_RE` | `re.compile('([A-Z][a-z]?)')` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `parse_formula_to_counts` | `(formula: Optional[str]) → dict` | Parse a chemical formula string into {element: integer_count}. |
| `_safe_int` | `(s: str, *, default: int=1) → int` | Convert a numeric string to a positive int, rounding floats. |
| `_element_order_in_formula` | `(formula: str) → list[str]` | Return elements in the order they first appear in *formula*. |
| `reduce_counts` | `(counts: dict) → dict` | Divide all counts by their GCD to get the empirical formula. |
| `reduced_counts_from_formula` | `(formula: str) → dict` | Prases the formula and returns it's reduced counts. |
| `signature_from_counts` | `(counts: dict) → str` | Order-independent canonical key for matching equivalent formulas. |
| `signature_from_formula` | `(formula: str) → str` | Order-independent canonical key for matching equivalent formulas. |
| `elements_with_count_from_formula` | `(formula: str) → list[str]` | Transforms a formula in a list of element-count strings. |
| `_join_formula_from_counts` | `(counts: dict, prefer_order: list[str] \| None=None) → str` | Build a human-readable formula string from counts. |
| `canonicalize_preserve_user_order` | `(formula: str) → str` | Reduce stoichiometry but preserve the user's element order. |
