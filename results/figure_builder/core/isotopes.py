"""Natural isotope abundances, read from the app's periodic table data."""

from __future__ import annotations

import re

_ABUNDANCE: dict[str, float] | None = None


def _load() -> dict[str, float]:
    """``{'107Ag': 51.839, ...}`` in percent (empty when the table is unavailable)."""
    global _ABUNDANCE
    if _ABUNDANCE is None:
        out: dict[str, float] = {}
        try:
            from widget.periodic_table_widget import PeriodicTableWidget
            for element in PeriodicTableWidget.create_elements_data():
                for iso in element.get('isotopes') or []:
                    if isinstance(iso, dict) and iso.get('label'):
                        out[str(iso['label'])] = float(iso.get('abundance') or 0.0)
        except Exception:
            out = {}
        _ABUNDANCE = out
    return _ABUNDANCE


def canonical(label: str) -> str:
    """``Ag107``, ``107Ag`` or ``107 Ag`` → ``107Ag``."""
    text = str(label).strip().strip('`')
    m = re.fullmatch(r'(\d+)\s*([A-Za-z]{1,2})', text) or None
    if m:
        return f'{m.group(1)}{m.group(2).capitalize()}'
    m = re.fullmatch(r'([A-Za-z]{1,2})\s*-?\s*(\d+)', text)
    if m:
        return f'{m.group(2)}{m.group(1).capitalize()}'
    return text


def abundance(label: str) -> float | None:
    """Natural abundance of an isotope in percent, or None when unknown."""
    value = _load().get(canonical(label))
    return value if value else None


def natural_ratio(numerator: str, denominator: str) -> float | None:
    """Natural abundance ratio of two isotopes, or None when either is unknown."""
    a, b = abundance(numerator), abundance(denominator)
    if a is None or b is None or b == 0:
        return None
    return a / b


def ratio_parts(expr: str, table=None) -> tuple[str, str] | None:
    """The two isotope labels of an expression written as ``A / B`` (prefixes allowed).

    Bare symbols are resolved through ``table`` when given, so ``Ag/Ag`` style
    aliases still find their isotope labels.
    """
    text = (expr or '').strip()
    m = re.fullmatch(r'\(?\s*(?:[a-z]+:)?`?([A-Za-z0-9]+)`?\s*\)?\s*/\s*\(?\s*(?:[a-z]+:)?`?([A-Za-z0-9]+)`?\s*\)?',
                     text)
    if not m:
        return None
    parts = []
    for name in (m.group(1), m.group(2)):
        if table is not None:
            try:
                name = table.resolve_label(name)
            except Exception:
                pass
        parts.append(name)
    return parts[0], parts[1]


_FACTOR = re.compile(r'^\(\s*(.+?)\s*\)\s*\*\s*([0-9.]+(?:[eE][-+]?\d+)?)$')


def split_factor(expr: str) -> tuple[str, float]:
    """Split ``(A / B) * k`` into ``('A / B', k)``; any other expression gets ``k = 1``.

    Insights writes a mass-bias corrected ratio this way, so tools that need
    the plain ratio (the counting band, the natural line) can still read it.
    """
    text = (expr or '').strip()
    m = _FACTOR.match(text)
    if not m:
        return text, 1.0
    try:
        return m.group(1), float(m.group(2))
    except ValueError:
        return text, 1.0


def mass_number(label: str) -> float | None:
    """Mass number of an isotope label: ``206Pb`` or ``Pb206`` → ``206.0``."""
    m = re.search(r'(\d+)', canonical(label))
    return float(m.group(1)) if m else None


def exponential_factor(numerator: str, denominator: str, ref_num: str, ref_den: str,
                       certified: float, measured: float) -> float | None:
    """Mass-bias correction factor of the exponential law (Russell et al., 1978).

    The fractionation exponent comes from a reference ratio of known value,
    ``f = ln(certified / measured) / ln(m_ref_num / m_ref_den)``, and the
    measured ratio of *numerator* to *denominator* is multiplied by
    ``(m_num / m_den) ** f``.

    Returns:
        The factor, or ``None`` when a mass or a reference value is missing.
    """
    masses = [mass_number(x) for x in (numerator, denominator, ref_num, ref_den)]
    if any(m is None or m <= 0 for m in masses):
        return None
    m_num, m_den, m_rn, m_rd = masses
    try:
        certified, measured = float(certified), float(measured)
    except (TypeError, ValueError):
        return None
    if certified <= 0 or measured <= 0 or m_rn == m_rd:
        return None
    import math
    f = math.log(certified / measured) / math.log(m_rn / m_rd)
    return (m_num / m_den) ** f


RADIOGENIC = {'Pb', 'Sr', 'Nd', 'Hf', 'Os', 'Ca', 'Ar', 'He', 'U', 'Th'}
"""Elements whose isotope abundances vary in nature through radioactive decay."""


def is_radiogenic(label: str) -> bool:
    """Whether the element of *label* has a naturally variable isotope composition."""
    m = re.search(r'([A-Z][a-z]?)', canonical(label))
    return bool(m) and m.group(1) in RADIOGENIC
