"""Natural isotope abundances, read from the app's periodic table data."""

from __future__ import annotations

import re

_ABUNDANCE: dict[str, float] | None = None

ELEMENT_SYMBOLS = (
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl',
    'Ar', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As',
    'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In',
    'Sn', 'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb',
    'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl',
    'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk',
    'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds', 'Rg', 'Cn', 'Nh',
    'Fl', 'Mc', 'Lv', 'Ts', 'Og')
"""Element symbols in atomic-number order (index + 1 is the atomic number)."""

_ATOMIC_NUMBER = {sym: i + 1 for i, sym in enumerate(ELEMENT_SYMBOLS)}


def atomic_number(symbol: str) -> int | None:
    """Atomic number of an element symbol such as ``Ag``, or None when unknown."""
    return _ATOMIC_NUMBER.get(str(symbol).strip().capitalize())


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


_RATIO = re.compile(r'\(?\s*(?:([a-z]+):)?`?([A-Za-z0-9]+)`?\s*\)?\s*/\s*\(?\s*(?:([a-z]+):)?`?([A-Za-z0-9]+)`?\s*\)?')


def ratio_prefixes(expr: str) -> tuple[str | None, str | None] | None:
    """The quantity prefixes written on each side of ``A / B``, ``None`` where none is written.

    ``"mass:206Pb / 207Pb"`` → ``("mass", None)``; ``None`` when the
    expression is not a ratio of two names.
    """
    m = _RATIO.fullmatch((expr or '').strip())
    if not m:
        return None
    return m.group(1), m.group(3)


def is_count_ratio(expr: str, table=None) -> bool:
    """Whether ``expr`` is one isotope divided by another, both read in counts.

    A side with no prefix is read in the table's default quantity, so it
    counts only when that quantity is counts.
    """
    prefixes = ratio_prefixes(split_factor(expr)[0])
    if prefixes is None:
        return False
    default = getattr(table, 'default_prefix', 'counts') if table is not None else 'counts'
    return all((p or default) == 'counts' for p in prefixes)


def same_element(a: str, b: str) -> bool:
    """Whether two isotope labels belong to one element, e.g. ``206Pb`` and ``207Pb``."""
    sa = re.sub(r'\d', '', canonical(a))
    sb = re.sub(r'\d', '', canonical(b))
    return bool(sa) and sa == sb


RATIO_KEYS = ('x', 'y', 'value', 'y2')
"""Panel expressions that can hold an isotope ratio."""


def counts_for_isotope_ratios(panel: dict, table) -> dict:
    """The panel with every isotope ratio read in counts, whatever the figure's quantity.

    An isotope ratio is a ratio of counted ions. In mass, moles or size each
    isotope is converted with its own calibration slope, which already holds
    that isotope's abundance in the standard, so a ratio of two converted
    isotopes is the measured ratio divided by the standard's and no longer
    the isotope ratio. A ratio of two isotopes of one element with no prefix
    written is therefore read in counts; a prefix written on purpose, such as
    ``mass:206Pb / mass:207Pb``, is kept. Axes that are not ratios keep the
    figure's quantity, so X can still be the mass or size of the particle.

    Returns:
        The panel itself when nothing changes, otherwise a corrected copy.
    """
    if getattr(table, 'default_prefix', 'counts') == 'counts':
        return panel
    out = None
    for key in RATIO_KEYS:
        expr = (panel.get(key) or '').strip()
        if not expr:
            continue
        base, k = split_factor(expr)
        prefixes = ratio_prefixes(base)
        if prefixes is None or any(prefixes):
            continue
        parts = ratio_parts(base, table)
        if parts is None or not same_element(*parts):
            continue
        new = f'counts:{parts[0]} / counts:{parts[1]}'
        if base != expr:
            new = f'({new}){expr[expr.rindex(")") + 1:]}'
        if out is None:
            out = dict(panel)
        out[key] = new
    return out if out is not None else panel


PROPORTIONAL_TOLERANCE = 1.02
"""Largest spread of N / X, as a factor, still read as X proportional to N."""


def counting_envelope(x, counts, ratio: float, k: float = 2.0, log_x: bool = False,
                      points: int = 200):
    """The ± kσ counting-statistics envelope of a ratio, along any X axis.

    For a ratio R of two Poisson counts, σ = √(R(1 + R) / N) with N the
    denominator's counts in the particle. N is each particle's own count, so
    the envelope is exact whatever X shows when X is proportional to N: the
    denominator's counts themselves, or its mass or moles in one sample,
    which are its counts divided by one calibration slope. Otherwise N is
    followed along X with a power-law fit of the particles' counts against
    X, the typical N at each X.

    Args:
        x: Each particle's X value.
        counts: Each particle's denominator counts, aligned with *x*.
        ratio: The measured ratio the envelope is centred on.
        k: Half-width in σ.
        log_x: Whether the X axis is logarithmic.
        points: Points along the curve.

    Returns:
        ``(xs, lower, upper)``, or ``None`` with fewer than three usable particles.
    """
    import numpy as np
    x = np.asarray(x, dtype=float)
    n = np.asarray(counts, dtype=float)
    ok = np.isfinite(x) & np.isfinite(n) & (n > 0)
    if log_x:
        ok &= x > 0
    if ok.sum() < 3 or not np.isfinite(ratio) or ratio <= 0:
        return None
    x, n = x[ok], n[ok]
    lo, hi = float(x.min()), float(x.max())
    xs = np.logspace(np.log10(lo), np.log10(hi), points) if log_x and lo > 0 else \
        np.linspace(lo, hi, points)
    per = n / np.where(x != 0, x, np.nan)
    per = per[np.isfinite(per) & (per > 0)]
    if per.size and np.nanmax(per) <= np.nanmin(per) * PROPORTIONAL_TOLERANCE:
        nn = xs * float(np.median(per))
    else:
        use = x > 0
        if use.sum() >= 3 and np.ptp(np.log10(x[use])) > 0:
            slope, intercept = np.polyfit(np.log10(x[use]), np.log10(n[use]), 1)
            nn = 10 ** (intercept + slope * np.log10(np.maximum(xs, x[use].min() * 1e-3)))
        else:
            nn = np.full_like(xs, float(np.median(n)))
    sigma = np.sqrt(ratio * (1 + ratio) / np.maximum(nn, 1.0))
    return xs, np.maximum(ratio - k * sigma, 0.0), ratio + k * sigma


def particle_sigma(counts, ratio: float):
    """Counting σ of a ratio in each particle, from its own denominator counts."""
    import numpy as np
    return np.sqrt(max(ratio, 0) * (1 + max(ratio, 0)) / np.maximum(np.asarray(counts, float), 1.0))


_FACTOR = re.compile(r'^\(\s*(.+?)\s*\)\s*\*\s*([0-9.]+(?:[eE][-+]?\d+)?|mb_[A-Za-z0-9_]+)$')


def split_factor(expr: str) -> tuple[str, float]:
    """Split ``(A / B) * k`` into ``('A / B', k)``; any other expression gets ``k = 1``.

    Insights writes a mass-bias corrected ratio this way, so tools that need
    the plain ratio (the counting band, the natural line) can still read it.
    A ratio corrected per sample, ``(A / B) * mb_…`` (see
    :mod:`results.figure_builder.core.massbias`), splits into ``('A / B', 1.0)``;
    its factors are read per group with
    :func:`results.figure_builder.core.massbias.group_factor`.
    """
    text = (expr or '').strip()
    m = _FACTOR.match(text)
    if not m:
        return text, 1.0
    if m.group(2).startswith('mb_'):
        return m.group(1), 1.0
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
