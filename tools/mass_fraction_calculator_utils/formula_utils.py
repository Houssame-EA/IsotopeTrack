"""
Formula parsing – supports parentheses, e.g. Ca(OH)2, Al2(SO4)3
"""

import re
from functools import reduce
from math import gcd

_TOKEN_RE = re.compile(r'([A-Z][a-z]?|\(|\))(\d*(?:\.\d+)?)')


def parse_formula_to_counts(formula: str) -> dict:
    """Parse a chemical formula string into {element: integer_count}.

    Handles parenthesised groups such as Ca(OH)2 → {'Ca': 1, 'O': 2, 'H': 2}.
    Nested parentheses are supported.

    Args:
        formula: Chemical formula string.

    Returns:
        dict mapping element symbols to positive integer counts.
    """
    if not formula or not isinstance(formula, str):
        return {}

    stack: list[dict] = [{}]

    for token, num_str in _TOKEN_RE.findall(formula):
        if token == '(':
            stack.append({})
        elif token == ')':
            if len(stack) < 2:
                continue
            multiplier = _safe_int(num_str, default=1)
            top = stack.pop()
            for el, cnt in top.items():
                stack[-1][el] = stack[-1].get(el, 0) + cnt * multiplier
        else:
            n = _safe_int(num_str, default=1)
            stack[-1][token] = stack[-1].get(token, 0) + n

    while len(stack) > 1:
        top = stack.pop()
        for el, cnt in top.items():
            stack[-1][el] = stack[-1].get(el, 0) + cnt

    return {k: v for k, v in stack[0].items() if v > 0}


def _safe_int(s: str, *, default: int = 1) -> int:
    """Convert a numeric string to a positive int, rounding floats.
    Args:
        s (str): The s.
        default (int): The default.
    Returns:
        int: Result of the operation.
    """
    if not s:
        return default
    try:
        return max(int(round(float(s))), 0) or default
    except (ValueError, TypeError):
        return default


_ELEMENT_ORDER_RE = re.compile(r'([A-Z][a-z]?)')


def _element_order_in_formula(formula: str) -> list[str]:
    """Return elements in the order they first appear in *formula*.
    Args:
        formula (str): The formula.
    Returns:
        list[str]: Result of the operation.
    """
    seen: set[str] = set()
    order: list[str] = []
    for el in _ELEMENT_ORDER_RE.findall(str(formula)):
        if el not in seen:
            seen.add(el)
            order.append(el)
    return order


def reduce_counts(counts: dict) -> dict:
    """Divide all counts by their GCD to get the empirical formula.
    Args:
        counts (dict): The counts.
    Returns:
        dict: Result of the operation.
    """
    if not counts:
        return counts
    nums = [abs(int(v)) for v in counts.values() if int(v) != 0]
    if not nums:
        return counts
    g = reduce(gcd, nums)
    if g <= 1:
        return counts
    return {k: v // g for k, v in counts.items()}


def signature_from_counts(counts: dict) -> str:
    """Order-independent canonical key for matching equivalent formulas.
    Args:
        counts (dict): The counts.
    Returns:
        str: Result of the operation.
    """
    if not counts:
        return ''
    return '|'.join(f'{el}{n}' for el, n in sorted(counts.items()))


def _join_formula_from_counts(counts: dict, prefer_order: list[str] | None = None) -> str:
    """Build a human-readable formula string from counts.
    Args:
        counts (dict): The counts.
        prefer_order (list[str] | None): The prefer order.
    Returns:
        str: Result of the operation.
    """
    if not counts:
        return ''
    if prefer_order:
        rest = sorted(e for e in counts if e not in prefer_order)
        ordered = list(dict.fromkeys(list(prefer_order) + rest))
    else:
        ordered = sorted(counts)
    parts = []
    for el in ordered:
        n = counts.get(el, 0)
        if n <= 0:
            continue
        parts.append(el if n == 1 else f'{el}{n}')
    return ''.join(parts)


def canonicalize_preserve_user_order(formula: str) -> str:
    """Reduce stoichiometry but preserve the user's element order.
    Args:
        formula (str): The formula.
    Returns:
        str: Result of the operation.
    """
    counts = reduce_counts(parse_formula_to_counts(formula))
    order = _element_order_in_formula(formula)
    return _join_formula_from_counts(counts, prefer_order=order)
