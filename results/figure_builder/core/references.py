"""Reference compositions: the upper continental crust and mineral formulas.

Single-particle papers judge particles against natural references: a Ti:Fe
ratio against the crust, a particle's Al–Si–Fe composition against kaolinite
or illite. This module holds those references so figures can draw them.

* :data:`UPPER_CRUST` is the recommended upper continental crust of Rudnick
  and Gao (2014), Treatise on Geochemistry 2nd ed., vol. 4, ch. 4.1, Table 3:
  major elements as oxides in wt% and trace elements in µg/g.
* :data:`MINERALS` maps common mineral names to ideal formulas. Real minerals
  vary (illite, smectite and biotite especially), so the formulas are end
  members or idealised compositions, good for orientation, not for
  quantification.

Both tables are built in and editable: :func:`load_user` and :func:`save_user`
keep the user's own values (changed crust abundances, extra minerals) in the
application settings, and every lookup prefers them.
"""

from __future__ import annotations

import json
import re

ATOMIC_WEIGHTS: dict[str, float] = {
    'H': 1.008, 'He': 4.0026, 'Li': 6.94, 'Be': 9.0122, 'B': 10.81, 'C': 12.011, 'N': 14.007,
    'O': 15.999, 'F': 18.998, 'Ne': 20.180, 'Na': 22.990, 'Mg': 24.305, 'Al': 26.982,
    'Si': 28.085, 'P': 30.974, 'S': 32.06, 'Cl': 35.45, 'Ar': 39.948, 'K': 39.098,
    'Ca': 40.078, 'Sc': 44.956, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Mn': 54.938,
    'Fe': 55.845, 'Co': 58.933, 'Ni': 58.693, 'Cu': 63.546, 'Zn': 65.38, 'Ga': 69.723,
    'Ge': 72.630, 'As': 74.922, 'Se': 78.971, 'Br': 79.904, 'Kr': 83.798, 'Rb': 85.468,
    'Sr': 87.62, 'Y': 88.906, 'Zr': 91.224, 'Nb': 92.906, 'Mo': 95.95, 'Ru': 101.07,
    'Rh': 102.91, 'Pd': 106.42, 'Ag': 107.87, 'Cd': 112.41, 'In': 114.82, 'Sn': 118.71,
    'Sb': 121.76, 'Te': 127.60, 'I': 126.90, 'Xe': 131.29, 'Cs': 132.91, 'Ba': 137.33,
    'La': 138.91, 'Ce': 140.12, 'Pr': 140.91, 'Nd': 144.24, 'Sm': 150.36, 'Eu': 151.96,
    'Gd': 157.25, 'Tb': 158.93, 'Dy': 162.50, 'Ho': 164.93, 'Er': 167.26, 'Tm': 168.93,
    'Yb': 173.05, 'Lu': 174.97, 'Hf': 178.49, 'Ta': 180.95, 'W': 183.84, 'Re': 186.21,
    'Os': 190.23, 'Ir': 192.22, 'Pt': 195.08, 'Au': 196.97, 'Hg': 200.59, 'Tl': 204.38,
    'Pb': 207.2, 'Bi': 208.98, 'Th': 232.04, 'U': 238.03,
}
"""Standard atomic weights (IUPAC, abridged), g/mol."""

CRUST_SOURCE = ('Rudnick, R. L. & Gao, S. (2014). Composition of the continental crust. '
                'Treatise on Geochemistry, 2nd ed., vol. 4, pp. 1–51. Upper continental crust, '
                'Table 3.')
"""Citation for :data:`UPPER_CRUST`."""

UPPER_CRUST_OXIDES: dict[str, float] = {
    'SiO2': 66.6, 'TiO2': 0.64, 'Al2O3': 15.4, 'FeO': 5.04, 'MnO': 0.10, 'MgO': 2.48,
    'CaO': 3.59, 'Na2O': 3.27, 'K2O': 2.80, 'P2O5': 0.15,
}
"""Major elements of the upper crust as oxides, wt% (iron as total FeO)."""

UPPER_CRUST_TRACE: dict[str, float] = {
    'Li': 24, 'Be': 2.1, 'B': 17, 'Sc': 14.0, 'V': 97, 'Cr': 92, 'Co': 17.3, 'Ni': 47,
    'Cu': 28, 'Zn': 67, 'Ga': 17.5, 'Ge': 1.4, 'As': 4.8, 'Rb': 84, 'Sr': 320, 'Y': 21,
    'Zr': 193, 'Nb': 12, 'Mo': 1.1, 'Ag': 0.053, 'Cd': 0.09, 'In': 0.056, 'Sn': 2.1,
    'Sb': 0.4, 'Cs': 4.9, 'Ba': 628, 'La': 31, 'Ce': 63, 'Pr': 7.1, 'Nd': 27, 'Sm': 4.7,
    'Eu': 1.0, 'Gd': 4.0, 'Tb': 0.7, 'Dy': 3.9, 'Ho': 0.83, 'Er': 2.3, 'Tm': 0.30,
    'Yb': 1.96, 'Lu': 0.31, 'Hf': 5.3, 'Ta': 0.9, 'W': 1.9, 'Pt': 0.0005, 'Au': 0.0015,
    'Tl': 0.9, 'Pb': 17, 'Bi': 0.16, 'Th': 10.5, 'U': 2.7,
}
"""Trace elements of the upper crust, µg/g."""

MINERALS: dict[str, str] = {
    'quartz': 'SiO2',
    'kaolinite': 'Al2Si2O5(OH)4',
    'illite': 'K0.65Al2.65Si3.35O10(OH)2',
    'muscovite': 'KAl3Si3O10(OH)2',
    'montmorillonite': 'Na0.33Al1.67Mg0.33Si4O10(OH)2',
    'chlorite (clinochlore)': 'Mg5Al2Si3O10(OH)8',
    'biotite (annite)': 'KFe3AlSi3O10(OH)2',
    'phlogopite': 'KMg3AlSi3O10(OH)2',
    'albite': 'NaAlSi3O8',
    'anorthite': 'CaAl2Si2O8',
    'orthoclase': 'KAlSi3O8',
    'forsterite': 'Mg2SiO4',
    'fayalite': 'Fe2SiO4',
    'gibbsite': 'Al(OH)3',
    'hematite': 'Fe2O3',
    'magnetite': 'Fe3O4',
    'goethite': 'FeO(OH)',
    'ilmenite': 'FeTiO3',
    'rutile': 'TiO2',
    'spinel': 'MgAl2O4',
    'calcite': 'CaCO3',
    'dolomite': 'CaMg(CO3)2',
    'zircon': 'ZrSiO4',
    'monazite (Ce)': 'CePO4',
    'bastnaesite (Ce)': 'CeCO3F',
    'barite': 'BaSO4',
    'galena': 'PbS',
    'sphalerite': 'ZnS',
    'pyrite': 'FeS2',
    'chalcopyrite': 'CuFeS2',
}
"""Common minerals and their ideal formulas."""

SETTINGS_KEY = 'figure_builder/references'
"""Application-settings key holding the user's own reference values."""


def parse_formula(formula: str) -> dict[str, float]:
    """Atoms per formula unit, e.g. ``Al2Si2O5(OH)4`` → ``{Al: 2, Si: 2, O: 9, H: 4}``.

    Parentheses nest, counts may be decimals, and a hydrate written with a
    dot (``CaSO4·2H2O``) is added on.

    Raises:
        ValueError: When the formula holds an unknown element or is malformed.
    """
    text = str(formula or '').replace(' ', '')
    if not text:
        raise ValueError('Empty formula')
    total: dict[str, float] = {}
    for part in re.split(r'[·•*](?=\d*[A-Z(])', text):
        lead = re.match(r'^(\d+(?:\.\d+)?)', part)
        mult = float(lead.group(1)) if lead else 1.0
        body = part[lead.end():] if lead else part
        for el, n in _parse_group(body).items():
            total[el] = total.get(el, 0.0) + n * mult
    return total


def _parse_group(text: str) -> dict[str, float]:
    """Parse one formula without hydrate dots, handling nested parentheses."""
    stack: list[dict[str, float]] = [{}]
    i = 0
    token = re.compile(r'([A-Z][a-z]?)(\d+(?:\.\d+)?)?')
    count = re.compile(r'\d+(?:\.\d+)?')
    while i < len(text):
        ch = text[i]
        if ch in '([':
            stack.append({})
            i += 1
        elif ch in ')]':
            if len(stack) < 2:
                raise ValueError(f'Unbalanced parenthesis in {text!r}')
            i += 1
            m = count.match(text, i)
            mult = float(m.group(0)) if m else 1.0
            if m:
                i = m.end()
            inner = stack.pop()
            for el, n in inner.items():
                stack[-1][el] = stack[-1].get(el, 0.0) + n * mult
        else:
            m = token.match(text, i)
            if not m or m.group(1) not in ATOMIC_WEIGHTS:
                raise ValueError(f'Unknown element at {text[i:]!r}')
            stack[-1][m.group(1)] = stack[-1].get(m.group(1), 0.0) + float(m.group(2) or 1)
            i = m.end()
    if len(stack) != 1:
        raise ValueError(f'Unbalanced parenthesis in {text!r}')
    return stack[0]


def builtin_crust() -> dict[str, float]:
    """Upper-crust abundance of every listed element, as a mass fraction (g/g).

    Oxides are converted to their element using the atomic weights.
    """
    out: dict[str, float] = {}
    for oxide, wt in UPPER_CRUST_OXIDES.items():
        atoms = parse_formula(oxide)
        metal = next(el for el in atoms if el != 'O')
        oxide_mass = sum(ATOMIC_WEIGHTS[el] * n for el, n in atoms.items())
        out[metal] = wt / 100.0 * atoms[metal] * ATOMIC_WEIGHTS[metal] / oxide_mass
    for el, ppm in UPPER_CRUST_TRACE.items():
        out[el] = ppm * 1e-6
    return out


_USER: dict | None = None


def load_user() -> dict:
    """The user's own reference values: ``{'crust': {el: µg/g}, 'minerals': {name: formula}}``.

    Read once from the application settings; an empty dict when Qt or the
    settings are unavailable.
    """
    global _USER
    if _USER is not None:
        return _USER
    data: dict = {}
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(SETTINGS_KEY, '')
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}
    _USER = {'crust': dict(data.get('crust') or {}), 'minerals': dict(data.get('minerals') or {})}
    return _USER


def save_user(user: dict) -> None:
    """Keep the user's reference values in the application settings and use them."""
    global _USER
    _USER = {'crust': {k: float(v) for k, v in (user.get('crust') or {}).items()},
             'minerals': {str(k): str(v) for k, v in (user.get('minerals') or {}).items()}}
    try:
        from PySide6.QtCore import QSettings
        QSettings().setValue(SETTINGS_KEY, json.dumps(_USER))
    except Exception:
        pass


def set_user(user: dict | None) -> None:
    """Replace the user's values in memory only, for tests and previews."""
    global _USER
    _USER = None if user is None else {'crust': dict(user.get('crust') or {}),
                                       'minerals': dict(user.get('minerals') or {})}


def crust() -> dict[str, float]:
    """Upper-crust mass fractions, with the user's changed values (µg/g) applied."""
    out = builtin_crust()
    for el, ppm in load_user()['crust'].items():
        if el in ATOMIC_WEIGHTS and ppm and float(ppm) > 0:
            out[el] = float(ppm) * 1e-6
    return out


def minerals() -> dict[str, str]:
    """Built-in minerals plus the user's own, the user's taking precedence."""
    return {**MINERALS, **load_user()['minerals']}


def symbol_of(label: str) -> str:
    """Element symbol of an isotope label or symbol: ``56Fe`` / ``Fe56`` / ``Fe`` → ``Fe``."""
    text = str(label or '').strip()
    for prefix in ('mass:', 'moles:', 'pmass:', 'pmoles:', 'counts:', 'd:', 'pd:'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    m = re.match(r'^\d*\s*([A-Z][a-z]?)\s*-?\s*\d*$', text)
    if not m or m.group(1) not in ATOMIC_WEIGHTS:
        raise ValueError(f"'{label}' is not a single element")
    return m.group(1)


def crust_ratio(num: str, den: str, basis: str = 'mass') -> float:
    """Upper-crust ratio of two elements, by mass or by moles.

    Args:
        num: Numerator element (symbol or isotope label).
        den: Denominator element.
        basis: ``'mass'`` or ``'moles'``.

    Raises:
        ValueError: When either element has no crust value.
    """
    a, b = symbol_of(num), symbol_of(den)
    table = crust()
    if a not in table or b not in table:
        missing = a if a not in table else b
        raise ValueError(f'No upper-crust value for {missing}')
    ratio = table[a] / table[b]
    if basis == 'moles':
        ratio *= ATOMIC_WEIGHTS[b] / ATOMIC_WEIGHTS[a]
    return ratio


def composition(name_or_formula: str, elements: list[str], basis: str = 'moles') -> list[float]:
    """Amounts of *elements* in a mineral or the crust, normalised to sum to one.

    Args:
        name_or_formula: A mineral name from :func:`minerals`, ``'upper crust'``,
            or a formula.
        elements: Element symbols, in corner order.
        basis: ``'moles'`` or ``'mass'``.

    Raises:
        ValueError: When the reference is unknown or holds none of the elements.
    """
    key = str(name_or_formula or '').strip()
    if key.lower() in ('upper crust', 'crust', 'ucc'):
        table = crust()
        amounts = [table.get(el, 0.0) for el in elements]
        if basis == 'moles':
            amounts = [a / ATOMIC_WEIGHTS[el] for a, el in zip(amounts, elements)]
    else:
        known = {k.lower(): v for k, v in minerals().items()}
        atoms = parse_formula(known.get(key.lower(), key))
        amounts = [atoms.get(el, 0.0) for el in elements]
        if basis == 'mass':
            amounts = [a * ATOMIC_WEIGHTS[el] for a, el in zip(amounts, elements)]
    total = sum(amounts)
    if total <= 0:
        raise ValueError(f'{key} holds none of {", ".join(elements)}')
    return [a / total for a in amounts]


def split_entries(text: str) -> list[tuple[str, str]]:
    """Parse a reference list such as ``kaolinite, illite, my clay: K0.6Al2.3Si3.4O10(OH)2``.

    Returns:
        ``(label, name_or_formula)`` pairs; a ``label: formula`` entry keeps
        its own label.
    """
    out = []
    for item in re.split(r'[,;\n]', str(text or '')):
        item = item.strip()
        if not item:
            continue
        if ':' in item:
            label, formula = item.split(':', 1)
            out.append((label.strip(), formula.strip()))
        else:
            out.append((item, item))
    return out
