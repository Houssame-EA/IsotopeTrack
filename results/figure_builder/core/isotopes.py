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
