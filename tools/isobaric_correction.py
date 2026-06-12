"""
Isobaric correction engine for spICP-ToF-MS.

This module is pure logic. It does NOT own any element/abundance data and does
NOT import the GUI. All element data is read through accessors that are passed
in (the same ones MainWindow already uses), so abundances live in exactly one
place: PeriodicTableWidget.

Design decisions (agreed in discussion):
  - Correction is applied UPSTREAM, on the raw signal trace, before particle
    detection. Everything downstream (detection, counts, mass, size) then reads
    already-clean data.
  - Overlaps come exclusively from the known interference list in
    data/interference_corrections.json (published ICP-MS correction equations),
    NOT from an automatic abundance scan.
  - The default factor R and monitor are the table's published values. The user
    can override both per correction; overrides persist in
    data/isobaric_overrides.json and the defaults are always kept for Reset.
  - When the user picks a non-default monitor, R is recomputed as the
    natural-abundance ratio:
    R = abundance(interferent @ overlap mass) / abundance(interferent @ monitor mass).
  - Corrected signal is clamped at zero.
  - A correction is only *applicable* when the monitor isotope is actually
    measured (present as a data channel).

The arithmetic:
    corrected_analyte(t) = max( raw_analyte(t) - R * monitor(t), 0 )

Example (Pb measured at 204, Hg interfering, 202Hg as monitor):
    R = abundance(204Hg) / abundance(202Hg) = 6.87 / 29.86 = 0.2301
    corrected_204(t) = max( raw_204(t) - 0.2301 * signal_202Hg(t), 0 )

Reused from the rest of the app (passed in, never duplicated here):
    get_element_by_symbol(symbol) -> element dict with 'isotopes':
        [{'mass': float, 'abundance': float (percent), 'label': str}, ...]
    get_elements()                -> list of those element dicts
    find_closest_isotope(mass)    -> nearest available data-channel mass (float)
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.isobaric_correction")

def _nominal(mass: float) -> int:
    """Return the nominal (integer) mass by rounding to the nearest integer."""
    return int(round(mass))


@dataclass
class IsobaricCorrection:
    """One TERM of a correction equation for an analyte channel.

    The full equation for an analyte is the sum of all its terms:

        corrected(analyte) = max( raw(analyte)
                                  + sign1*R1*chanA1 [op chanB1]
                                  + sign2*R2*chanA2 [op chanB2]
                                  + ..., 0 )

    A plain table term is sign=-1, op="" (i.e. "subtract R x monitor").
    A ratio/product term uses op="/" or "*" with a second channel:
        sign * R * (chanA / chanB)   or   sign * R * (chanA * chanB)

    Masses are exact isotope masses (matching the periodic-table data and the
    mass-keyed signal channels). Symbols are element symbols.
    """
    analyte_symbol: str
    analyte_mass: float
    interferent_symbol: str
    interferent_overlap_mass: float
    monitor_mass: float         
    factor: float               
    enabled: bool = True

    analyte_label: str = ""
    interferent_overlap_label: str = ""
    monitor_label: str = ""
    note: str = ""
    source: str = "table"        

    sign: int = -1             
    op: str = ""                
    channel_b_mass: float = 0.0
    channel_b_label: str = ""

  
    default_factor: float = 0.0
    default_monitor_label: str = ""
    default_monitor_mass: float = 0.0

    def override_key(self) -> str:
        """Key identifying this analyte's custom equation in the overrides file."""
        return f"eq::{self.analyte_label}"

    def is_customized(self) -> bool:
        """True when this term differs from its table default (or is user-added)."""
        if self.source == "custom":
            return True
        return (abs(self.factor - self.default_factor) > 1e-9
                or _nominal(self.monitor_mass) != _nominal(self.default_monitor_mass)
                or self.sign != -1 or bool(self.op))

    def term_text(self) -> str:
        """Human-readable text for this single term, e.g. '− 0.2301 × Hg 202'."""
        s = "−" if self.sign < 0 else "+"
        a = self.monitor_label or f"m/z {_nominal(self.monitor_mass)}"
        if self.op in ("*", "/"):
            b = self.channel_b_label or f"m/z {_nominal(self.channel_b_mass)}"
            opc = "×" if self.op == "*" else "÷"
            return f"{s} {self.factor:.6g} × ({a} {opc} {b})"
        return f"{s} {self.factor:.6g} × {a}"

    def equation_text(self) -> str:
        """Human-readable single-term equation with the real numbers filled in."""
        a = self.analyte_label or f"{_nominal(self.analyte_mass)}{self.analyte_symbol}"
        return (f"corrected({a}) = max( raw({_nominal(self.analyte_mass)}) "
                f"{self.term_text()}, 0 )")


def equation_text_for(analyte_label: str,
                      analyte_mass: float,
                      terms: List["IsobaricCorrection"]) -> str:
    """Full multi-term equation text for one analyte channel.

    Args:
        analyte_label: Display label of the analyte isotope (e.g. 'Pb 204').
        analyte_mass: Analyte isotope mass.
        terms: All terms targeting this analyte (enabled or not).

    Returns:
        e.g. 'corrected(Pb 204) = max( raw(204) − 0.2301 × Hg 202, 0 )'
    """
    body = " ".join(t.term_text() for t in terms) or "− 0"
    return f"corrected({analyte_label}) = max( raw({_nominal(analyte_mass)}) {body}, 0 )"


def term_to_dict(c: "IsobaricCorrection") -> dict:
    """Serialize one term for the overrides file."""
    return {
        'sign': c.sign,
        'factor': c.factor,
        'a_label': c.monitor_label,
        'a_nominal': _nominal(c.monitor_mass),
        'op': c.op,
        'b_label': c.channel_b_label,
        'b_nominal': _nominal(c.channel_b_mass) if c.op else 0,
    }


def term_from_dict(analyte_symbol: str, analyte_mass: float,
                   analyte_label: str, d: dict) -> "IsobaricCorrection":
    """Deserialize one term from the overrides file."""
    a_label = d.get('a_label', '')
    return IsobaricCorrection(
        analyte_symbol=analyte_symbol,
        analyte_mass=analyte_mass,
        interferent_symbol=a_label.split()[0] if ' ' in a_label else a_label,
        interferent_overlap_mass=float(analyte_mass),
        monitor_mass=float(d.get('a_nominal', 0)),
        factor=float(d.get('factor', 0.0)),
        analyte_label=analyte_label,
        monitor_label=a_label,
        source="custom",
        sign=int(d.get('sign', -1)),
        op=str(d.get('op', '') or ''),
        channel_b_mass=float(d.get('b_nominal', 0) or 0),
        channel_b_label=str(d.get('b_label', '') or ''),
    )


_CHANNEL_NAME_RE = re.compile(r'^(?:[A-Za-z]{1,3})(\d{1,3})$')

_ALLOWED_FUNCTIONS: Dict[str, Callable] = {
    'log': np.log,
    'log10': np.log10,
    'sqrt': np.sqrt,
    'exp': np.exp,
    'abs': np.abs,
}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.USub, ast.UAdd)


@dataclass
class EquationCorrection:
    """A free-text correction equation for one analyte channel.

    The expression is calculator-style and is evaluated element-wise on the
    signal arrays. 'raw' refers to the analyte channel; any token of the form
    Element+mass (e.g. Hg202, Ar38, Cr54) refers to the measured channel at
    that nominal mass. Supported: + - * / ** parentheses and the functions
    log, log10, sqrt, exp, abs.

    Example:
        raw - 0.230074*Hg202 + 2*(Ar38/K39)
    """
    analyte_symbol: str
    analyte_mass: float
    analyte_label: str
    expression: str
    enabled: bool = True
    note: str = ""
    source: str = "custom"

    def override_key(self) -> str:
        """Key identifying this analyte's custom equation in the overrides file."""
        return f"eq::{self.analyte_label}"

    def is_customized(self) -> bool:
        """Free-text equations are by definition user customizations."""
        return True

    def equation_text(self) -> str:
        """Human-readable equation with the clamp made explicit."""
        return f"corrected({self.analyte_label}) = max( {self.expression}, 0 )"


def _channel_nominal_from_name(name: str) -> Optional[int]:
    """Nominal mass encoded in a channel token, or None if not a channel token.

    Args:
        name: Identifier from the expression, e.g. 'Hg202' or 'Ar38'.

    Returns:
        The integer nominal mass, or None when the token is not a channel
        reference (e.g. 'raw' or a function name).
    """
    m = _CHANNEL_NAME_RE.match(name)
    return int(m.group(1)) if m else None


def _walk_expression(expr: str) -> Tuple[ast.Expression, List[str]]:
    """Parse an expression and verify every node is whitelisted.

    Args:
        expr: The calculator-style expression text.

    Returns:
        (parsed AST, list of channel tokens referenced).

    Raises:
        ValueError: On syntax errors, disallowed constructs, or unknown names.
    """
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"syntax error: {e.msg}")

    channels: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Constant)):
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                raise ValueError("only numeric constants are allowed")
        elif isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOPS):
                raise ValueError("only + - * / ** operators are allowed")
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARYOPS):
                raise ValueError("only unary + and - are allowed")
        elif isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name)
                    or node.func.id not in _ALLOWED_FUNCTIONS
                    or node.keywords or len(node.args) != 1):
                raise ValueError(
                    f"only these functions are allowed: {', '.join(sorted(_ALLOWED_FUNCTIONS))}")
        elif isinstance(node, ast.Name):
            if node.id == 'raw' or node.id in _ALLOWED_FUNCTIONS:
                continue
            if _channel_nominal_from_name(node.id) is None:
                raise ValueError(
                    f"unknown name '{node.id}' — use 'raw' or Element+mass like Hg202")
            channels.append(node.id)
        elif isinstance(node, (ast.Load, ast.operator, ast.unaryop, ast.expr_context)):
            continue
        else:
            raise ValueError(f"'{type(node).__name__}' is not allowed in equations")
    return tree, channels


def validate_expression(expr: str,
                        available_nominals: Optional[set] = None
                        ) -> Tuple[bool, str, List[int]]:
    """Check an equation expression for syntax and channel availability.

    Args:
        expr: The calculator-style expression text.
        available_nominals: Set of measured nominal masses. When given, every
            referenced channel must be in it.

    Returns:
        (ok, error_message, referenced nominal masses). error_message is empty
        when ok is True.
    """
    expr = (expr or "").strip()
    if not expr:
        return False, "equation is empty", []
    try:
        _, names = _walk_expression(expr)
    except ValueError as e:
        _itk_log.exception("Handled exception in validate_expression")
        return False, str(e), []
    nominals = sorted({_channel_nominal_from_name(n) for n in names})
    if available_nominals is not None:
        missing = [n for n in nominals if n not in available_nominals]
        if missing:
            return False, (
                "channel(s) not measured: " + ", ".join(f"m/z {n}" for n in missing)
            ), nominals
    return True, "", nominals


def _eval_node(node, env: Dict[str, np.ndarray]):
    """Recursively evaluate a whitelisted AST node against the channel env.

    Args:
        node: AST node (already validated by _walk_expression).
        env: Maps 'raw' and channel tokens to signal arrays.

    Returns:
        ndarray or scalar result of the subexpression.
    """
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else +value
    if isinstance(node, ast.Call):
        return _ALLOWED_FUNCTIONS[node.func.id](_eval_node(node.args[0], env))
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Pow):
            return left ** right
        return np.divide(left, right,
                         out=np.zeros_like(np.asarray(left, dtype=float)
                                           * np.ones_like(np.asarray(right, dtype=float))),
                         where=np.asarray(right) != 0)
    raise ValueError(f"unexpected node {type(node).__name__}")


def evaluate_equation(eq: EquationCorrection,
                      sample_data: Dict[float, np.ndarray],
                      find_closest_isotope: Callable[[float], float],
                      clamp: bool = True) -> Optional[np.ndarray]:
    """Evaluate a free-text equation for one sample.

    Args:
        eq: The equation correction to evaluate.
        sample_data: Mass-keyed channel dict for one sample.
        find_closest_isotope: Maps a nominal mass to the measured channel key.
        clamp: Clamp the result at zero when True.

    Returns:
        The corrected analyte array, or None when a referenced channel is
        missing from this sample.
    """
    tree, names = _walk_expression(eq.expression)
    analyte_key = find_closest_isotope(eq.analyte_mass)
    if analyte_key is None or analyte_key not in sample_data:
        return None

    env: Dict[str, np.ndarray] = {
        'raw': np.asarray(sample_data[analyte_key], dtype=float)}
    for name in names:
        nominal = _channel_nominal_from_name(name)
        key = find_closest_isotope(float(nominal))
        if key is None or key not in sample_data:
            return None
        env[name] = np.asarray(sample_data[key], dtype=float)

    with np.errstate(divide='ignore', invalid='ignore'):
        result = _eval_node(tree, env)
    result = np.nan_to_num(np.asarray(result, dtype=float),
                           nan=0.0, posinf=0.0, neginf=0.0)
    if clamp:
        result = np.clip(result, 0.0, None)
    return result


def expression_from_terms(terms: List[IsobaricCorrection]) -> str:
    """Render a list of term objects as an editable expression string.

    Args:
        terms: Term objects of one analyte's equation.

    Returns:
        e.g. 'raw - 1575.954114*Ar38 - 0.000125*K39'.
    """
    def token(label: str, mass: float) -> str:
        compact = (label or "").replace(" ", "")
        if _CHANNEL_NAME_RE.match(compact):
            return compact
        return f"ch{_nominal(mass)}"

    parts = ["raw"]
    for t in terms:
        a = token(t.monitor_label, t.monitor_mass)
        if t.op in ("*", "/"):
            b = token(t.channel_b_label, t.channel_b_mass)
            core = f"{t.factor:.12g}*({a}{'*' if t.op == '*' else '/'}{b})"
        else:
            core = f"{t.factor:.12g}*{a}"
        parts.append(("- " if t.sign < 0 else "+ ") + core)
    return " ".join(parts)


def _isotopes(element_data: dict) -> List[dict]:
    """Return the list of isotope dicts for an element, or an empty list if unavailable."""
    if not element_data:
        return []
    return [iso for iso in element_data.get('isotopes', []) if isinstance(iso, dict)]


def _abundance_at(element_data: dict, mass: float, tol: float = 0.3) -> float:
    """Abundance (percent) of the isotope nearest `mass`, by nominal mass."""
    target = _nominal(mass)
    for iso in _isotopes(element_data):
        if _nominal(iso.get('mass', 0.0)) == target:
            return float(iso.get('abundance', 0.0) or 0.0)
    return 0.0


def _isotope_dict_at(element_data: dict, mass: float) -> Optional[dict]:
    """Return the isotope dict whose nominal mass matches *mass*, or None if not found."""
    target = _nominal(mass)
    for iso in _isotopes(element_data):
        if _nominal(iso.get('mass', 0.0)) == target:
            return iso
    return None



def correction_factor(interferent_symbol: str,
                      overlap_mass: float,
                      monitor_mass: float,
                      get_element_by_symbol: Callable[[str], Optional[dict]]
                      ) -> float:
    """R = abundance(interferent @ overlap) / abundance(interferent @ monitor).

    Both abundances read from the periodic table. Returns 0.0 if the monitor
    abundance is unavailable (correction then has no effect, fail-safe).
    """
    element_data = get_element_by_symbol(interferent_symbol)
    ab_overlap = _abundance_at(element_data, overlap_mass)
    ab_monitor = _abundance_at(element_data, monitor_mass)
    if ab_monitor <= 0.0:
        return 0.0
    return ab_overlap / ab_monitor


def apply_to_signal(analyte_signal: np.ndarray,
                    monitor_signal: np.ndarray,
                    factor: float,
                    clamp: bool = True) -> np.ndarray:
    """corrected = analyte - factor * monitor, clamped at 0.

    Returns a new array; inputs are not modified. Shapes must match (both
    channels are acquired on the same ToF time base).
    """
    analyte = np.asarray(analyte_signal, dtype=float)
    monitor = np.asarray(monitor_signal, dtype=float)
    if analyte.shape != monitor.shape:
        raise ValueError(
            f"analyte/monitor length mismatch: {analyte.shape} vs {monitor.shape}")
    corrected = analyte - factor * monitor
    if clamp:
        np.clip(corrected, 0.0, None, out=corrected)
    return corrected


def correct_sample_channels(sample_data: Dict[float, np.ndarray],
                            corrections: List[IsobaricCorrection],
                            find_closest_isotope: Callable[[float], float],
                            clamp: bool = True
                            ) -> Dict[float, np.ndarray]:
    """Return corrected copies of the analyte channels for one sample.

    `sample_data` is the mass-keyed channel dict (like data_by_sample[sample]).
    Only enabled corrections whose monitor channel exists are applied.

    All enabled terms targeting the same analyte channel are accumulated and
    the result is clamped once at the end:
        corrected = max( raw + sign1*R1*chanA1[op chanB1] + sign2*R2*chanA2 ... , 0 )

    Ratio terms (op='/') treat division-by-zero samples as a zero contribution.

    The returned dict contains ONLY the analyte channels that changed, so the
    caller can show in/out and apply on commit while keeping the raw aside.

    The list may mix term objects (IsobaricCorrection) and free-text equations
    (EquationCorrection); equations take precedence for their analyte channel.
    """
    equations = [c for c in corrections if isinstance(c, EquationCorrection)]
    term_list = [c for c in corrections if not isinstance(c, EquationCorrection)]

    by_analyte: Dict[float, list] = {}
    for corr in term_list:
        if not corr.enabled or corr.factor <= 0.0:
            continue
        analyte_key = find_closest_isotope(corr.analyte_mass)
        a_key = find_closest_isotope(corr.monitor_mass)
        if analyte_key not in sample_data or a_key not in sample_data:
            continue
        if _nominal(a_key) == _nominal(analyte_key):
            continue
        b_key = None
        if corr.op in ("*", "/"):
            b_key = find_closest_isotope(corr.channel_b_mass)
            if b_key is None or b_key not in sample_data:
                continue
        by_analyte.setdefault(analyte_key, []).append(
            (a_key, corr.factor, corr.sign, corr.op, b_key))

    out: Dict[float, np.ndarray] = {}
    for analyte_key, terms in by_analyte.items():
        corrected = np.asarray(sample_data[analyte_key], dtype=float).copy()
        for a_key, factor, sign, op, b_key in terms:
            chan_a = np.asarray(sample_data[a_key], dtype=float)
            if chan_a.shape != corrected.shape:
                raise ValueError(
                    f"channel length mismatch at analyte {analyte_key}: "
                    f"{corrected.shape} vs channel {a_key} {chan_a.shape}")
            value = chan_a
            if op in ("*", "/"):
                chan_b = np.asarray(sample_data[b_key], dtype=float)
                if chan_b.shape != corrected.shape:
                    raise ValueError(
                        f"channel length mismatch at analyte {analyte_key}: "
                        f"{corrected.shape} vs channel {b_key} {chan_b.shape}")
                if op == "*":
                    value = chan_a * chan_b
                else:
                    value = np.divide(chan_a, chan_b,
                                      out=np.zeros_like(chan_a),
                                      where=chan_b != 0)
            corrected += sign * factor * value
        if clamp:
            np.clip(corrected, 0.0, None, out=corrected)
        out[analyte_key] = corrected

    for eq in equations:
        if not eq.enabled:
            continue
        result = evaluate_equation(eq, sample_data, find_closest_isotope, clamp=clamp)
        if result is not None:
            out[find_closest_isotope(eq.analyte_mass)] = result

    return out


# ---------------------------------------------------------------------------
# Reference interference table (ICP-MS empirical correction equations)
# ---------------------------------------------------------------------------

_TABLE_CACHE: Optional[List[dict]] = None


def _find_table_path() -> str:
    """Locate the bundled interference table (read-only app data).

    Checks, in order: the PyInstaller bundle dir, the repo-root data/
    folder, a data/ folder next to this module, and the CWD.
    """
    import sys
    candidates = []
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, 'data'))
        candidates.append(sys._MEIPASS)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(os.path.dirname(here), 'data'))  # repo root/data
    candidates.append(os.path.join(here, 'data'))
    candidates.append(os.path.join(os.getcwd(), 'data'))
    for base in candidates:
        p = os.path.join(base, 'interference_corrections.json')
        if os.path.isfile(p):
            return p
    return os.path.join(candidates[0] if candidates else '', 'interference_corrections.json')


def _user_overrides_path() -> str:
    """Writable location for user-saved overrides (mirrors the log-dir logic)."""
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        if sys.platform == 'darwin':
            base = Path.home() / 'Library' / 'Application Support' / 'IsotopeTrack'
        elif sys.platform == 'win32':
            base = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'IsotopeTrack'
        else:
            base = Path(os.environ.get('XDG_DATA_HOME',
                        str(Path.home() / '.local' / 'share'))) / 'IsotopeTrack'
    else:
        base = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'data'
    return str(base / 'isobaric_overrides.json')


_TABLE_PATH = _find_table_path()
_OVERRIDES_PATH = _user_overrides_path()


# ---------------------------------------------------------------------------
# User overrides (persisted custom R factors / monitor choices)
# ---------------------------------------------------------------------------

def load_overrides(path: str = _OVERRIDES_PATH) -> Dict[str, dict]:
    """Load persisted user overrides.

    Maps override_key -> {'factor': float, 'monitor_label': str,
    'monitor_nominal': int}. Empty dict if no file yet.
    """
    try:
        with open(path, "r") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        # Normal on first run — no overrides saved yet.
        return {}
    except json.JSONDecodeError:
        _itk_log.exception("Corrupt isobaric overrides file: %s", path)
        return {}


def save_overrides(overrides: Dict[str, dict], path: str = _OVERRIDES_PATH) -> None:
    """Persist user overrides to disk (atomic-ish write)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(overrides, fh, indent=1)
    os.replace(tmp, path)


def monitor_candidates(interferent_symbol: str,
                       analyte_mass: float,
                       get_element_by_symbol: Callable[[str], Optional[dict]],
                       ) -> List[dict]:
    """All isotopes of the interfering element usable as a monitor.

    Excludes the isotope sitting on the analyte mass itself. Sorted by
    abundance (most abundant first). Each entry:
        {'label', 'mass', 'nominal', 'abundance'}
    """
    element_data = get_element_by_symbol(interferent_symbol)
    overlap_nominal = _nominal(analyte_mass)
    out = []
    for iso in _isotopes(element_data or {}):
        mass = float(iso.get('mass', 0.0))
        if _nominal(mass) == overlap_nominal:
            continue
        out.append({
            'label': iso.get('label', f"{interferent_symbol} {_nominal(mass)}"),
            'mass': mass,
            'nominal': _nominal(mass),
            'abundance': float(iso.get('abundance', 0.0) or 0.0),
        })
    out.sort(key=lambda c: c['abundance'], reverse=True)
    return out


def load_table_corrections(path: str = _TABLE_PATH) -> List[dict]:
    """Load the empirical interference correction table from a JSON file.

    The table is cached after the first load so repeated calls are free.
    Each record has the keys: element, isotope_label, mass, abundance,
    interferences, and optionally correction_terms — a list of
    {'monitor_label', 'monitor_nominal', 'factor'} dicts derived from the
    published ICP-MS interference correction equations.

    Args:
        path: Path to the JSON file. Defaults to data/interference_corrections.json
              next to this module.

    Returns:
        List of isotope records. Empty list if the file is not found.
    """
    global _TABLE_CACHE
    if _TABLE_CACHE is not None:
        return _TABLE_CACHE
    try:
        with open(path, "r") as fh:
            _TABLE_CACHE = json.load(fh)
    except FileNotFoundError:
        _itk_log.error("Interference correction table not found: %s — "
                       "isobaric corrections will be unavailable", path)
        _TABLE_CACHE = []
    except json.JSONDecodeError:
        _itk_log.exception("Corrupt interference correction table: %s", path)
        _TABLE_CACHE = []
    return _TABLE_CACHE


def lookup_table_entry(analyte_nominal: int,
                       element_symbol: Optional[str] = None,
                       path: str = _TABLE_PATH) -> Optional[dict]:
    """Return the table record for *analyte_nominal* mass, or None.

    Matches by nominal (integer) mass. When *element_symbol* is given, only
    records of that element match — several elements can share a nominal mass
    (e.g. K 40 and Ca 40), so matching on mass alone can return the wrong
    isotope's corrections.

    Args:
        analyte_nominal: Integer nominal mass of the analyte isotope.
        element_symbol: Element symbol to disambiguate isobars (recommended).
        path: Path forwarded to load_table_corrections if not yet loaded.

    Returns:
        The matching record dict, or None if not found.
    """
    for rec in load_table_corrections(path):
        if int(round(rec['mass'])) != analyte_nominal:
            continue
        if element_symbol and rec.get('element') != element_symbol:
            continue
        return rec
    return None


def build_table_corrections(selected_isotopes: Dict[str, List[float]],
                             available_masses: Optional[List[float]] = None,
                             path: str = _TABLE_PATH,
                             overrides: Optional[Dict[str, dict]] = None,
                             ) -> List[IsobaricCorrection]:
    """Build IsobaricCorrection objects from the empirical reference table.

    For every selected isotope that has an entry in the interference table, one
    IsobaricCorrection is created per correction term (one term = one monitor
    channel). Corrections are marked enabled when the monitor mass is present
    in *available_masses*; disabled with an actionable note otherwise.

    These table-sourced corrections carry source='table' so the dialog can
    display them as recommended and show the empirical factor alongside the
    abundance-ratio baseline.

    Args:
        selected_isotopes: Maps element symbol -> list of selected masses
            (same structure as MainWindow.selected_isotopes).
        available_masses: Channel masses actually present in the loaded data.
            If None, all corrections are marked disabled.
        path: Path forwarded to load_table_corrections.
        overrides: Persisted user overrides (load_overrides()). Keyed
            'eq::<analyte_label>'. A value with 'expr' carries a free-text
            equation that fully replaces the table equation for that analyte.
            A value with 'terms' (legacy format) is converted to an
            expression. The pristine table terms remain available through
            default_table_terms so Reset always works.

    Returns:
        List of correction objects ordered by analyte mass (ascending):
        IsobaricCorrection term objects for table-default analytes, and
        EquationCorrection objects for analytes with a custom equation.
    """
    pool = set(_nominal(m) for m in (available_masses or []))
    overrides = overrides or {}
    out: list = []

    pairs = sorted(
        ((symbol, mass)
         for symbol, masses in selected_isotopes.items()
         for mass in masses),
        key=lambda p: p[1])

    for symbol, analyte_mass in pairs:
        rec = lookup_table_entry(_nominal(analyte_mass), symbol, path)
        if not rec or not rec.get('correction_terms'):
            continue

        analyte_label = rec['isotope_label']
        ov = overrides.get(f"eq::{analyte_label}") or {}

        expr = ov.get('expr')
        if not expr and isinstance(ov.get('terms'), list):
            legacy = [term_from_dict(symbol, analyte_mass, analyte_label, d)
                      for d in ov['terms']]
            expr = expression_from_terms(legacy)

        if expr:
            eq = EquationCorrection(
                analyte_symbol=symbol,
                analyte_mass=analyte_mass,
                analyte_label=analyte_label,
                expression=expr,
            )
            ok, msg, _ = validate_expression(expr, pool or None)
            eq.enabled = ok
            eq.note = "" if ok else f"⚠ {msg}"
            out.append(eq)
            continue

        for term in rec['correction_terms']:
            mon_nominal = term['monitor_nominal']
            mon_label   = term['monitor_label']
            factor      = term['factor']
            corr = IsobaricCorrection(
                analyte_symbol=symbol,
                analyte_mass=analyte_mass,
                interferent_symbol=mon_label.split()[0] if ' ' in mon_label else mon_label,
                interferent_overlap_mass=float(analyte_mass),
                monitor_mass=float(mon_nominal),
                factor=factor,
                enabled=True,
                analyte_label=analyte_label,
                interferent_overlap_label="",
                monitor_label=mon_label,
                source="table",
                default_factor=factor,
                default_monitor_label=mon_label,
                default_monitor_mass=float(mon_nominal),
            )
            available = _nominal(corr.monitor_mass) in pool
            corr.enabled = available and corr.factor > 0.0
            corr.note = (
                f"⚠ Channel m/z {_nominal(corr.monitor_mass)} not measured — "
                f"this term is skipped until the channel is available."
                if not available else "")
            out.append(corr)

    return out


def default_table_terms(analyte_symbol: str,
                        analyte_mass: float,
                        path: str = _TABLE_PATH) -> List[IsobaricCorrection]:
    """The pristine table terms for one analyte (used by 'Reset to default').

    Args:
        analyte_symbol: Element symbol of the analyte.
        analyte_mass: Analyte isotope mass.
        path: Path forwarded to lookup_table_entry.

    Returns:
        List of term objects exactly as published in the reference table
        (empty if the analyte has no table entry).
    """
    rec = lookup_table_entry(_nominal(analyte_mass), analyte_symbol, path)
    if not rec or not rec.get('correction_terms'):
        return []
    analyte_label = rec['isotope_label']
    terms = []
    for term in rec['correction_terms']:
        mon_nominal = term['monitor_nominal']
        mon_label   = term['monitor_label']
        factor      = term['factor']
        terms.append(IsobaricCorrection(
            analyte_symbol=analyte_symbol,
            analyte_mass=analyte_mass,
            interferent_symbol=mon_label.split()[0] if ' ' in mon_label else mon_label,
            interferent_overlap_mass=float(analyte_mass),
            monitor_mass=float(mon_nominal),
            factor=factor,
            analyte_label=analyte_label,
            monitor_label=mon_label,
            source="table",
            default_factor=factor,
            default_monitor_label=mon_label,
            default_monitor_mass=float(mon_nominal),
        ))
    return terms