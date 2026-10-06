"""Per-particle table and safe vectorised expressions for the Figure Builder.

Every panel of a Figure Builder figure is described by short text
expressions such as ``Fe``, ``Fe/Cu``, ``log(mass:Ag)`` or
``sample == "Blank"``. This module turns the particle list carried on a
canvas link into a lazily-built column table and evaluates those
expressions over it with NumPy, one whole column at a time.

Naming rules understood by :func:`evaluate`:

* A bare isotope label (``107Ag``, ``Ag107``) or, when unambiguous, its
  bare symbol (``Ag``) reads the figure's default quantity.
* ``<quantity>:<label>`` reads another quantity for the same isotope,
  where quantity is one of :data:`QUANTITY_PREFIXES`.
* ``total`` is the sum of the default quantity over every isotope of the
  particle, ``n_elements`` the number of detected isotopes, ``sample`` the
  source sample name, ``class`` the Particle Classifier bucket, ``time`` the
  particle start time and ``index`` its row number.
* Any other column can be written between backticks.

Expressions are parsed with :mod:`ast` and only a small whitelist of nodes
and functions is accepted, so a typo can never execute arbitrary code.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

import numpy as np

QUANTITY_PREFIXES: dict[str, tuple[str, str, str]] = {
    'counts': ('elements', '', 'counts'),
    'mass': ('element_mass_fg', 'mass', 'fg'),
    'moles': ('element_moles_fmol', 'moles', 'fmol'),
    'pmass': ('particle_mass_fg', 'particle mass', 'fg'),
    'pmoles': ('particle_moles_fmol', 'particle moles', 'fmol'),
    'd': ('element_diameter_nm', 'diameter', 'nm'),
    'pd': ('particle_diameter_nm', 'particle diameter', 'nm'),
}
"""Prefix → (particle dict key, human name, unit)."""

DATA_TYPES: dict[str, str] = {
    'Counts': 'counts',
    'Element Mass (fg)': 'mass',
    'Element Moles (fmol)': 'moles',
    'Particle Mass (fg)': 'pmass',
    'Particle Moles (fmol)': 'pmoles',
    'Element Diameter (nm)': 'd',
    'Particle Diameter (nm)': 'pd',
}
"""Default-quantity choices offered in the UI, mapped to their prefix."""

SPECIAL_NAMES = ('total', 'n_elements', 'sample', 'class', 'time', 'index', 'per_ml', 'max_counts')

UNCLASSIFIED = 'Unclassified'

_IDENT_CHARS = r'A-Za-z0-9_'


class ExpressionError(ValueError):
    """Raised when an expression cannot be parsed or evaluated."""


def _agg(fn):
    """Wrap a NumPy reducer so it ignores non-finite values."""

    def inner(values, *args):
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return np.nan
        return fn(arr, *args)

    return inner


FUNCTIONS = {
    'log': np.log10,
    'log10': np.log10,
    'ln': np.log,
    'log2': np.log2,
    'exp': np.exp,
    'sqrt': np.sqrt,
    'abs': np.abs,
    'round': np.round,
    'min': np.minimum,
    'max': np.maximum,
    'clip': np.clip,
    'where': np.where,
    'mean': _agg(np.mean),
    'median': _agg(np.median),
    'std': _agg(np.std),
    'sum': _agg(np.sum),
    'percentile': _agg(np.percentile),
    'count': lambda v: float(np.count_nonzero(np.asarray(v))),
}
"""Functions an expression may call."""

CONSTANTS = {'pi': np.pi, 'e': np.e, 'nan': np.nan, 'inf': np.inf,
             'True': True, 'False': False}


def split_symbol(label: str) -> tuple[str, str | None]:
    """Split ``107Ag`` / ``Ag107`` / ``Ag`` into ``(symbol, mass)``."""
    text = str(label or '').strip()
    m = re.match(r'^(\d+)\s*([A-Z][a-z]?)$', text)
    if m:
        return m.group(2), m.group(1)
    m = re.match(r'^([A-Z][a-z]?)\s*-?\s*(\d+)$', text)
    if m:
        return m.group(1), m.group(2)
    return text, None


def _bucket_and_composition():
    """Import the classifier helpers lazily so this module stays importable."""
    try:
        from results.classifier_view import (
            bucket_of, composition, is_classifier_stream, bucket_registry)
        return bucket_of, composition, is_classifier_stream, bucket_registry
    except Exception:
        return (lambda p: None,
                lambda p, k: p.get(k) or {},
                lambda d: False,
                lambda d: {})


@dataclass
class ParticleTable:
    """Column view of a canvas particle stream.

    Columns are built on first access and cached, so a figure that only
    reads two isotopes never pays for the other quantities.

    Attributes:
        particles: The particle dicts from the upstream node.
        default_prefix: Quantity read by bare isotope names.
        labels: Isotope labels present in the stream, in display order.
        sample_order: Sample names in the order the upstream node lists them.
        class_order: Classifier bucket labels in registry order.
        class_colors: Classifier bucket colours chosen by the user.
    """

    particles: list
    default_prefix: str = 'counts'
    labels: list = field(default_factory=list)
    sample_order: list = field(default_factory=list)
    class_order: list = field(default_factory=list)
    class_colors: dict = field(default_factory=dict)
    variables: dict = field(default_factory=dict)
    _cache: dict = field(default_factory=dict, repr=False)
    _busy: set = field(default_factory=set, repr=False)

    @classmethod
    def from_input(cls, input_data: dict | None, data_type: str = 'Counts'):
        """Build a table from the ``input_data`` dict a viz node receives.

        Args:
            input_data: The upstream stream (``sample_data`` or
                ``multiple_sample_data``), classifier streams included.
            data_type: One of :data:`DATA_TYPES`.

        Returns:
            ParticleTable: Possibly empty when there is no data.
        """
        bucket_of, composition, is_clf, registry = _bucket_and_composition()
        prefix = DATA_TYPES.get(data_type, data_type if data_type in QUANTITY_PREFIXES else 'counts')
        if not isinstance(input_data, dict):
            return cls([], prefix)
        particles = list(input_data.get('particle_data') or [])
        iso = (input_data.get('_raw_selected_isotopes')
               or input_data.get('selected_isotopes') or [])
        labels = []
        for item in iso:
            lab = item.get('label') if isinstance(item, dict) else item
            if lab and lab not in labels:
                labels.append(str(lab))
        key = QUANTITY_PREFIXES[prefix][0]
        seen = set(labels)
        for p in particles:
            for lab in composition(p, key):
                if lab not in seen:
                    seen.add(lab)
                    labels.append(str(lab))
        sample_order = list(input_data.get('sample_names') or [])
        if not sample_order and input_data.get('sample_name'):
            sample_order = [input_data['sample_name']]
        class_order, class_colors = [], {}
        if is_clf(input_data):
            for lab, entry in registry(input_data).items():
                class_order.append(lab)
                if isinstance(entry, dict) and entry.get('color'):
                    class_colors[lab] = entry['color']
        table = cls(particles, prefix, labels, sample_order, class_order, class_colors)
        table._single_sample = input_data.get('sample_name')
        meta = input_data.get('concentration_meta')
        table.concentration_meta = dict(meta) if isinstance(meta, dict) else {}
        return table

    def has_per_ml(self) -> bool:
        """Whether particles per mL can be computed (dilution and analysed volume are known)."""
        return bool(len(self)) and bool(np.any(self.column('per_ml') > 0))

    def __len__(self) -> int:
        return len(self.particles)

    def view(self, data_type: str | None) -> 'ParticleTable':
        """The same particles read in another default quantity.

        Views share the column cache and variables with this table, so a
        panel using mass while the rest of the figure uses counts costs
        nothing extra beyond its own columns.

        Args:
            data_type: A :data:`DATA_TYPES` key or a quantity prefix; empty
                or unknown returns this table itself.
        """
        if not data_type:
            return self
        prefix = DATA_TYPES.get(data_type, data_type if data_type in QUANTITY_PREFIXES else None)
        if prefix is None or prefix == self.default_prefix:
            return self
        import copy as _copy
        other = _copy.copy(self)
        other.default_prefix = prefix
        return other

    def set_variables(self, variables) -> dict:
        """Install user-defined variables and return ``{name: error}`` for bad ones.

        Args:
            variables: list of ``{'name': str, 'expr': str}`` dicts (or a dict).

        Returns:
            dict: Problems keyed by variable name; empty when all are valid.
        """
        items = variables.items() if isinstance(variables, dict) else (
            (v.get('name', ''), v.get('expr', '')) for v in (variables or []))
        for key in [k for k in self._cache if isinstance(k, tuple) and k and k[0] == 'var']:
            self._cache.pop(key, None)
        self.variables = {}
        problems = {}
        reserved = set(self.labels) | set(SPECIAL_NAMES) | set(FUNCTIONS) | set(CONSTANTS)
        for name, expr in items:
            name = (name or '').strip()
            expr = (expr or '').strip()
            if not name and not expr:
                continue
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
                problems[name or '?'] = 'Names must start with a letter and use letters, digits or _'
                continue
            if name in reserved or name in self.symbol_aliases():
                problems[name] = f"'{name}' is already an isotope, function or built-in name"
                continue
            if not expr:
                problems[name] = 'Empty expression'
                continue
            self.variables[name] = expr
        for name in list(self.variables):
            try:
                self.column(name)
            except ExpressionError as exc:
                problems[name] = str(exc)
                self.variables.pop(name, None)
        return problems

    def _quantity(self, prefix: str, label: str) -> np.ndarray:
        """Return one quantity column, building it on first use."""
        ck = (prefix, label)
        if ck not in self._cache:
            _, composition, _, _ = _bucket_and_composition()
            key = QUANTITY_PREFIXES[prefix][0]
            out = np.zeros(len(self.particles), dtype=float)
            for i, p in enumerate(self.particles):
                v = composition(p, key).get(label, 0)
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    v = 0.0
                out[i] = v if (np.isfinite(v) and v > 0) else 0.0
            self._cache[ck] = out
        return self._cache[ck]

    def column(self, name: str) -> np.ndarray:
        """Return a column by its canonical name (see :meth:`names`)."""
        if name != 'total' and name in self._cache:
            return self._cache[name]
        if name == 'total' and ('total', self.default_prefix) in self._cache:
            return self._cache[('total', self.default_prefix)]
        if name in self.variables:
            key = ('var', name, self.default_prefix)
            if key not in self._cache:
                if name in self._busy:
                    raise ExpressionError(f"Variable '{name}' refers to itself")
                self._busy.add(name)
                try:
                    self._cache[key] = np.asarray(evaluate(self.variables[name], self))
                finally:
                    self._busy.discard(name)
            return self._cache[key]
        n = len(self.particles)
        if name == 'sample':
            single = getattr(self, '_single_sample', None)
            col = np.array([p.get('source_sample') or single or 'Sample'
                            for p in self.particles], dtype=object)
        elif name == 'class':
            bucket_of = _bucket_and_composition()[0]
            col = np.array([bucket_of(p) or UNCLASSIFIED for p in self.particles],
                           dtype=object)
        elif name == 'time':
            col = np.array([_as_float(p.get('start_time')) for p in self.particles])
        elif name == 'index':
            col = np.arange(n, dtype=float)
        elif name == 'per_ml':
            meta = getattr(self, 'concentration_meta', None) or {}
            factors = {}
            for s in set(self.column('sample').tolist()):
                entry = meta.get(s) or (next(iter(meta.values())) if len(meta) == 1 else None)
                vol = _as_float((entry or {}).get('volume_ml'))
                dil = _as_float((entry or {}).get('dilution_factor', 1.0))
                factors[s] = dil / vol if (np.isfinite(vol) and vol > 0 and np.isfinite(dil)) else 0.0
            col = np.array([factors.get(s, 0.0) for s in self.column('sample').tolist()], dtype=float)
        elif name == 'max_counts':
            col = np.zeros(n, dtype=float)
            for lab in self.labels:
                col = np.maximum(col, self._quantity('counts', lab))
        elif name == 'total':
            col = np.zeros(n, dtype=float)
            for lab in self.labels:
                col = col + self._quantity(self.default_prefix, lab)
        elif name == 'n_elements':
            col = np.zeros(n, dtype=float)
            for lab in self.labels:
                col = col + (self._quantity('counts', lab) > 0)
        elif ':' in name:
            prefix, lab = name.split(':', 1)
            if prefix not in QUANTITY_PREFIXES:
                raise ExpressionError(f"Unknown quantity '{prefix}'")
            return self._quantity(prefix, self.resolve_label(lab))
        else:
            return self._quantity(self.default_prefix, self.resolve_label(name))
        self._cache[('total', self.default_prefix) if name == 'total' else name] = col
        return col

    def symbol_aliases(self) -> dict[str, str]:
        """Bare symbols that map to exactly one isotope label."""
        by_symbol: dict[str, list[str]] = {}
        for lab in self.labels:
            sym, _ = split_symbol(lab)
            by_symbol.setdefault(sym, []).append(lab)
        return {s: labs[0] for s, labs in by_symbol.items()
                if len(labs) == 1 and s not in self.labels}

    def resolve_label(self, name: str) -> str:
        """Map a written name (label or unique symbol) to an isotope label."""
        if name in self.labels:
            return name
        alias = self.symbol_aliases().get(name)
        if alias:
            return alias
        raise ExpressionError(f"Unknown isotope or column '{name}'")

    def names(self) -> list[str]:
        """Every name an expression may use, for completion and parsing."""
        base = list(self.labels) + list(self.symbol_aliases())
        out = list(base)
        for prefix in QUANTITY_PREFIXES:
            out.extend(f'{prefix}:{b}' for b in base)
        out.extend(SPECIAL_NAMES)
        out.extend(self.variables)
        return out

    def samples(self) -> list[str]:
        """Sample names present, in upstream order."""
        present = list(dict.fromkeys(self.column('sample').tolist())) if len(self) else []
        ordered = [s for s in self.sample_order if s in present]
        return ordered + [s for s in present if s not in ordered]

    def classes(self) -> list[str]:
        """Classifier buckets present, in registry order."""
        present = list(dict.fromkeys(self.column('class').tolist())) if len(self) else []
        ordered = [c for c in self.class_order if c in present]
        return ordered + [c for c in present if c not in ordered]

    def dataframe(self):
        """Default-quantity columns plus ``sample`` and ``class`` as a DataFrame."""
        import pandas as pd
        data = {lab: self._quantity(self.default_prefix, lab) for lab in self.labels}
        data['total'] = self.column('total')
        for name in self.variables:
            try:
                data[name] = self.column(name)
            except ExpressionError:
                pass
        data['sample'] = self.column('sample')
        data['class'] = self.column('class')
        return pd.DataFrame(data)


def _as_float(v) -> float:
    """Convert to float, NaN when impossible."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


_STRING_RE = re.compile(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')')


def _substitute(expr: str, names: list[str]) -> tuple[str, dict[str, str]]:
    """Replace column names with safe identifiers outside string literals."""
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}

    def ident(name: str) -> str:
        if name not in reverse:
            vid = f'_v{len(reverse)}'
            reverse[name] = vid
            mapping[vid] = name
        return reverse[name]

    ordered = sorted(set(names), key=len, reverse=True)
    pattern = None
    if ordered:
        alt = '|'.join(re.escape(n) for n in ordered)
        pattern = re.compile(rf'(?<![{_IDENT_CHARS}:.])(?:{alt})(?![{_IDENT_CHARS}])')
    pieces = _STRING_RE.split(expr)
    out = []
    for i, piece in enumerate(pieces):
        if i % 2 == 1:
            out.append(piece)
            continue
        piece = re.sub(r'`([^`]+)`', lambda m: ident(m.group(1)), piece)
        if pattern is not None:
            piece = pattern.sub(lambda m: ident(m.group(0)), piece)
        out.append(piece)
    return ''.join(out), mapping


_BINOPS = {
    ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply,
    ast.Div: np.true_divide, ast.Pow: np.power, ast.Mod: np.mod,
    ast.FloorDiv: np.floor_divide,
}
_CMPOPS = {
    ast.Lt: np.less, ast.LtE: np.less_equal, ast.Gt: np.greater,
    ast.GtE: np.greater_equal, ast.Eq: np.equal, ast.NotEq: np.not_equal,
}


class _Evaluator:
    """Walk a whitelisted AST and compute its value with NumPy."""

    def __init__(self, table: ParticleTable, mapping: dict[str, str]):
        self.table = table
        self.mapping = mapping
        self.used: set[str] = set()

    def visit(self, node):
        method = getattr(self, f'_{type(node).__name__}', None)
        if method is None:
            raise ExpressionError(f"'{type(node).__name__}' is not allowed in an expression")
        return method(node)

    def _Expression(self, node):
        return self.visit(node.body)

    def _Constant(self, node):
        if isinstance(node.value, (int, float, str, bool)):
            return node.value
        raise ExpressionError('Unsupported constant')

    def _Name(self, node):
        if node.id in self.mapping:
            name = self.mapping[node.id]
            self.used.add(name)
            return self.table.column(name)
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise ExpressionError(f"Unknown isotope or name '{node.id}'")

    def _BinOp(self, node):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ExpressionError('Unsupported operator')
        a, b = self.visit(node.left), self.visit(node.right)
        return op(_num(a), _num(b))

    def _UnaryOp(self, node):
        v = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return np.negative(_num(v))
        if isinstance(node.op, ast.UAdd):
            return _num(v)
        if isinstance(node.op, ast.Not):
            return np.logical_not(v)
        raise ExpressionError('Unsupported unary operator')

    def _BoolOp(self, node):
        fn = np.logical_and if isinstance(node.op, ast.And) else np.logical_or
        values = [self.visit(v) for v in node.values]
        out = values[0]
        for v in values[1:]:
            out = fn(out, v)
        return out

    def _Compare(self, node):
        left = self.visit(node.left)
        result = None
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                if not isinstance(comp, (ast.List, ast.Tuple, ast.Set)):
                    raise ExpressionError("'in' needs a list, e.g. sample in [\"A\", \"B\"]")
                items = [self.visit(e) for e in comp.elts]
                part = np.isin(np.asarray(left, dtype=object), np.asarray(items, dtype=object))
                if isinstance(op, ast.NotIn):
                    part = np.logical_not(part)
                right = left
            else:
                fn = _CMPOPS.get(type(op))
                if fn is None:
                    raise ExpressionError('Unsupported comparison')
                right = self.visit(comp)
                if _is_text(left) or _is_text(right):
                    part = fn(np.asarray(left, dtype=object), np.asarray(right, dtype=object))
                else:
                    part = fn(_num(left), _num(right))
            result = part if result is None else np.logical_and(result, part)
            left = right
        return result

    def _Call(self, node):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            name = getattr(node.func, 'id', '?')
            raise ExpressionError(f"Unknown function '{name}'")
        if node.keywords:
            raise ExpressionError('Keyword arguments are not supported')
        args = [self.visit(a) for a in node.args]
        return FUNCTIONS[node.func.id](*args)

    def _IfExp(self, node):
        return np.where(self.visit(node.test), self.visit(node.body), self.visit(node.orelse))


def _is_text(v) -> bool:
    """Whether a value is a string or an object (text) column."""
    if isinstance(v, str):
        return True
    return isinstance(v, np.ndarray) and v.dtype == object


def _num(v):
    """Coerce booleans and scalars to float arrays for arithmetic."""
    if isinstance(v, str) or (isinstance(v, np.ndarray) and v.dtype == object):
        raise ExpressionError('Text values can only be compared, e.g. sample == "A"')
    return np.asarray(v, dtype=float) if isinstance(v, (np.ndarray, list)) else float(v)


def evaluate(expr: str, table: ParticleTable, as_mask: bool = False) -> np.ndarray:
    """Evaluate ``expr`` for every particle of ``table``.

    Args:
        expr: The expression text.
        table: Column source.
        as_mask: Return a boolean mask (NaN counts as False).

    Returns:
        numpy.ndarray: One value per particle. Scalars are broadcast.

    Raises:
        ExpressionError: On any syntax or name problem.
    """
    text = (expr or '').strip()
    if not text:
        raise ExpressionError('Empty expression')
    code, mapping = _substitute(text, table.names())
    try:
        tree = ast.parse(code, mode='eval')
    except SyntaxError as exc:
        raise ExpressionError(f'Syntax error in "{text}": {exc.msg}') from None
    with np.errstate(all='ignore'):
        try:
            value = _Evaluator(table, mapping).visit(tree)
        except ExpressionError:
            raise
        except Exception as exc:
            raise ExpressionError(f'Could not evaluate "{text}": {exc}') from None
    n = len(table)
    if as_mask:
        arr = np.asarray(value)
        if arr.dtype == object:
            arr = arr.astype(bool)
        elif arr.dtype != bool:
            arr = np.nan_to_num(arr.astype(float), nan=0.0) != 0
        return np.broadcast_to(arr, (n,)).copy()
    arr = np.asarray(value)
    if arr.dtype == bool:
        arr = arr.astype(float)
    return np.broadcast_to(arr, (n,)).copy()


def validate(expr: str, table: ParticleTable) -> str | None:
    """Return an error message for ``expr`` or None when it is valid."""
    try:
        evaluate(expr, table)
    except ExpressionError as exc:
        return str(exc)
    return None


def split_list(text: str) -> list[str]:
    """Split a comma separated list of expressions, ignoring commas inside brackets or quotes."""
    parts, depth, cur, quote = [], 0, [], None
    for ch in text or '':
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in '"\'':
            quote = ch
        elif ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        elif ch in ',;' and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append(''.join(cur).strip())
    return [p for p in parts if p]


def _format_label(label: str, style: str) -> str:
    """Format one isotope label for an axis title."""
    sym, mass = split_symbol(label)
    if style == 'raw' or not sym:
        return label
    if style == 'symbol' or not mass:
        return sym
    return rf'$^{{{mass}}}$' + sym


def plain(text: str) -> str:
    """Strip matplotlib mathtext from a label for plain-text reports."""
    return re.sub(r'\$\^\{(\d+)\}\$', r'\1', text or '').replace('$', '')


def pretty(expr: str, table: ParticleTable, style: str = 'isotope', with_unit: bool = True) -> str:
    """Turn an expression into a readable axis or legend title.

    A single column gets its quantity and unit (``$^{56}$Fe mass (fg)``);
    a formula keeps its operators with each isotope nicely formatted.
    """
    text = (expr or '').strip()
    if not text:
        return ''
    names = table.names()
    code, mapping = _substitute(text, names)
    single = re.fullmatch(r'_v\d+', code.strip())

    def render(name: str, with_unit: bool) -> str:
        if name in table.variables:
            return name
        if name in SPECIAL_NAMES:
            if name == 'total' and with_unit:
                q = QUANTITY_PREFIXES[table.default_prefix]
                return f'total {q[1]} ({q[2]})'.replace('  ', ' ')
            return name.replace('_', ' ')
        if ':' in name:
            prefix, lab = name.split(':', 1)
        else:
            prefix, lab = table.default_prefix, name
        try:
            lab = table.resolve_label(lab)
        except ExpressionError:
            pass
        out = _format_label(lab, style)
        if ':' in name or with_unit:
            _, human, unit = QUANTITY_PREFIXES.get(prefix, ('', prefix, ''))
            out = (f'{out} {human}' if human else out) + (f' ({unit})' if with_unit and unit else '')
        return out

    if single:
        return render(mapping[code.strip()], with_unit)
    out = re.sub(r'_v\d+', lambda m: render(mapping[m.group(0)], False), code)
    return out.replace('**', '^').replace('*', '×')
