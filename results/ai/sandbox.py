"""Running the Python the model writes, safely enough for a local tool.

The code runs with a reduced set of builtins and a namespace holding the
particle table, the analysis functions and a figure factory. Before it runs,
an AST screen rejects the known ways out of such a namespace: underscore
attributes (``__class__``, frame and closure walking), file access through
numpy, pandas or matplotlib, and the dangerous builtins. This is a guard
against mistakes by a locally run model, not a security boundary.

Results come back as an :class:`ExecResult`: printed text, tables, figures,
recorded findings, and every number produced, which the no-fabrication check
compares the model's prose against.
"""
from __future__ import annotations

import ast
import io
import logging
import math
import re
import sys
import threading
import time
import traceback
import warnings
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from results.ai import analysis
from results.ai.figures import (
    NAMESPACE as FIGURE_NAMESPACE, STYLE, FigureCollector, PyplotShim, describe_figure,
    render_png, style_figure,
)

_itk_log = logging.getLogger("IsotopeTrack.results.ai.sandbox")

CODE_EXEC_TIMEOUT = None
MAX_STDOUT_CHARS = 20000
MAX_TABLE_ROWS = 2000

SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bool': bool, 'dict': dict, 'enumerate': enumerate,
    'filter': filter, 'float': float, 'format': format, 'int': int, 'isinstance': isinstance,
    'len': len, 'list': list, 'map': map, 'max': max, 'min': min, 'print': print, 'range': range,
    'round': round, 'set': set, 'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
    'type': type, 'zip': zip, 'reversed': reversed, 'divmod': divmod, 'pow': pow, 'iter': iter,
    'next': next, 'slice': slice, 'frozenset': frozenset, 'repr': repr, 'callable': callable,
    'hasattr': hasattr, 'chr': chr, 'ord': ord, 'complex': complex,
    'True': True, 'False': False, 'None': None,
    'ValueError': ValueError, 'TypeError': TypeError, 'KeyError': KeyError,
    'IndexError': IndexError, 'ZeroDivisionError': ZeroDivisionError,
    'AttributeError': AttributeError, 'RuntimeError': RuntimeError, 'Exception': Exception,
    'StopIteration': StopIteration, 'ArithmeticError': ArithmeticError,
}

_BLOCKED_NAMES = frozenset({
    'open', 'eval', 'exec', 'compile', '__import__', 'input', 'breakpoint', 'help',
    'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars', 'memoryview', 'dir',
    'os', 'sys', 'subprocess', 'shutil', 'builtins', 'importlib', 'socket', 'pathlib',
})

_BLOCKED_ATTRS = frozenset({
    'save', 'savez', 'savez_compressed', 'load', 'loadtxt', 'savetxt', 'genfromtxt',
    'fromfile', 'tofile', 'memmap', 'fromregex', 'DataSource', 'open', 'system', 'popen',
    'remove', 'unlink', 'rename', 'rmdir', 'makedirs', 'mkdir', 'write_text', 'write_bytes',
    'read_text', 'read_bytes', 'savefig', 'imsave', 'imread', 'eval', 'os', 'sys',
    'subprocess', 'shutil', 'builtins', 'importlib', 'ctypes', 'socket', 'pathlib', 'pickle',
    'marshal', 'codecs', 'glob', 'gi_frame', 'gi_code', 'cr_frame', 'ag_frame', 'f_back',
    'f_globals', 'f_locals', 'f_builtins', 'tb_frame', 'tb_next', 'func_globals',
    'canvas', 'parent_window',
})

_BLOCKED_ATTR_RE = re.compile(
    r'^(_.*|read_.*|print_.*|to_(csv|excel|pickle|parquet|json|hdf|feather|sql|html|latex|'
    r'markdown|stata|clipboard|orc|xml|gbq))$')

_IMPORT_RE = re.compile(r'^[ \t]*(?:import\s+[\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*'
                        r'|from\s+[\w.]+\s+import\s+.+)[ \t]*$', re.MULTILINE)
_DROP_LINE_RE = re.compile(r'^[ \t]*(?:plt|fig)\.(?:show|savefig|close)\(.*\)[ \t]*$', re.MULTILINE)


def sanitize_code(code):
    """Remove imports and display calls the sandbox provides or forbids.

    Everything the code may import is already loaded, so import lines are
    dropped rather than failed on, which saves a correction round.

    Args:
        code (str): Generated code.

    Returns:
        str: Code ready for screening.
    """
    code = _IMPORT_RE.sub('', code or '')
    code = _DROP_LINE_RE.sub('', code)
    return code.strip('\n')


def screen_code(code):
    """Statically check generated code before it runs.

    Args:
        code (str): Sanitised code.

    Returns:
        str | None: Why the code was refused, or ``None`` when it may run.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.attr, str):
            if node.attr.startswith('__') and node.attr.endswith('__'):
                return f"Blocked: dunder attribute access ('{node.attr}') is not allowed in the sandbox."
            if node.attr in _BLOCKED_ATTRS or _BLOCKED_ATTR_RE.match(node.attr):
                return (f"Blocked: '.{node.attr}' is not allowed in the sandbox "
                        "(no private attributes and no file access).")
        if isinstance(node, ast.Name) and isinstance(node.id, str):
            if node.id.startswith('__') and node.id.endswith('__'):
                return f"Blocked: '{node.id}' is not allowed in the sandbox."
            if node.id in _BLOCKED_NAMES:
                return f"Blocked: '{node.id}' is not allowed in the sandbox."
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "Blocked: imports are not allowed; everything needed is pre-loaded."
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return "Blocked: global and nonlocal statements are not allowed."
    return None


_ANYNUM_RE = re.compile(r'[-+]?(?:\d[\d,]*\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_DECIMAL_RE = re.compile(r'[-+]?(?:\d[\d,]*\.\d+|\.\d+)(?:[eE][-+]?\d+)?|[-+]?\d+[eE][-+]?\d+')


def to_float(tok):
    """Parse a number written with optional thousands separators.

    Args:
        tok: Text or number.

    Returns:
        float | None: The value, or ``None`` when it is not a number.
    """
    try:
        return float(str(tok).replace(',', ''))
    except (ValueError, TypeError):
        return None


def floats_in_text(s):
    """All numbers in a string.

    Args:
        s (str): Text.

    Returns:
        list: Floats in order of appearance.
    """
    out = []
    for tok in _ANYNUM_RE.findall(str(s)):
        if tok in ('.', ',', '+', '-'):
            continue
        v = to_float(tok)
        if v is not None:
            out.append(v)
    return out


def _close(a, b, rel=0.006):
    """Whether two numbers agree to within rounding."""
    return abs(a - b) <= max(1e-12, rel * max(abs(a), abs(b)))


def _variants(v):
    """A computed value and the forms prose commonly restates it in."""
    out = [v]
    if 0 < abs(v) <= 1.5:
        out.append(v * 100.0)
    if abs(v) >= 1.5:
        out.append(v / 100.0)
    return out


def unverified_numbers(prose, allowed):
    """Decimal figures in prose that no computed output backs up.

    Only decimals are checked, since counts, years and indices in prose are
    too easily matched by accident. A value also matches its percentage form.

    Args:
        prose (str): The model's text, code removed.
        allowed (list): Every number the executed code produced.

    Returns:
        list: The unbacked figures as written.
    """
    pool = []
    for a in allowed:
        if a is None or not math.isfinite(a):
            continue
        pool.extend(_variants(float(a)))
    bad, seen = [], set()
    for tok in _DECIMAL_RE.findall(str(prose)):
        if tok in seen:
            continue
        seen.add(tok)
        v = to_float(tok)
        if v is None or not math.isfinite(v):
            continue
        if not any(_close(v, a) for a in pool):
            bad.append(tok)
    return bad


def format_cell(v):
    """Format one table value for display.

    Args:
        v: Any value.

    Returns:
        str: Integers as integers, small p-values in scientific notation,
        other floats to four significant digits.
    """
    if v is None:
        return ''
    if isinstance(v, (bool, np.bool_)):
        return 'yes' if v else 'no'
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if not math.isfinite(f):
            return '—'
        if f == int(f) and abs(f) < 1e12:
            return str(int(f))
        if abs(f) < 1e-3 or abs(f) >= 1e7:
            return f"{f:.3g}"
        return f"{f:.4g}"
    return str(v)


def _table_from(data, rows=None, title=''):
    """Normalise the many shapes ``show_table`` accepts into one table dict."""
    note = ''
    if isinstance(data, pd.Series):
        data = data.to_frame(name=data.name or 'value')
        data = data.reset_index()
    if isinstance(data, pd.DataFrame):
        note = str(data.attrs.get('note', '') or '')
        frame = data
        if not isinstance(frame.index, pd.RangeIndex):
            frame = frame.reset_index()
        headers = [str(c) for c in frame.columns]
        body = frame.head(MAX_TABLE_ROWS).itertuples(index=False, name=None)
        total = len(frame)
        cells = [[format_cell(v) for v in r] for r in body]
        raw = [list(r) for r in frame.head(MAX_TABLE_ROWS).itertuples(index=False, name=None)]
    elif isinstance(data, dict) and rows is None:
        headers = ['key', 'value']
        cells = [[str(k), format_cell(v)] for k, v in data.items()]
        raw = [[k, v] for k, v in data.items()]
        total = len(cells)
    elif rows is None and isinstance(data, (list, tuple)) and data and isinstance(data[0], dict):
        headers = list(dict.fromkeys(k for r in data for k in r))
        raw = [[r.get(h) for h in headers] for r in data]
        cells = [[format_cell(v) for v in r] for r in raw]
        total = len(cells)
    else:
        headers = [str(h) for h in (data or [])]
        raw = [list(r) for r in (rows or [])]
        total = len(raw)
        raw = raw[:MAX_TABLE_ROWS]
        cells = [[format_cell(v) for v in r] for r in raw]
    if total > len(cells):
        note = (note + f"  Showing the first {len(cells)} of {total} rows.").strip()
    return {'title': str(title or 'Result'), 'headers': headers, 'rows': cells,
            'raw': raw, 'note': note, 'total_rows': total}


def _numbers_in_table(tbl, cap=20000):
    """Numbers held by a table, raw values first so no precision is lost."""
    out = []
    for r in tbl.get('raw') or []:
        for v in r:
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                f = float(v)
                if math.isfinite(f):
                    out.append(f)
            else:
                out.extend(floats_in_text(v))
            if len(out) >= cap:
                return out
    for r in tbl.get('rows') or []:
        for c in r:
            out.extend(floats_in_text(c))
            if len(out) >= cap * 2:
                return out
    out.extend(floats_in_text(tbl.get('note', '')))
    out.extend(floats_in_text(tbl.get('title', '')))
    return out


@dataclass
class ExecResult:
    """What one run of generated code produced.

    Attributes:
        text (str): Printed output.
        tables (list): Table dicts with ``title``, ``headers``, ``rows``, ``note``.
        figures (list): Figure dicts with ``figure``, ``png``, ``description``.
        findings (list): Findings recorded with ``record_finding``.
        error (str): Error message, empty when the code ran cleanly.
        warnings (list): Problems worth telling the model, e.g. empty panels.
        numbers (list): Every number produced, for the fabrication check.
    """

    text: str = ''
    tables: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    error: str = ''
    warnings: list = field(default_factory=list)
    numbers: list = field(default_factory=list)

    @property
    def produced(self):
        """Whether the code produced anything to show."""
        return bool(self.text or self.tables or self.figures or self.findings)


def format_exec_error(exc, code):
    """Error text with the offending line of the generated code.

    Args:
        exc (BaseException): The exception.
        code (str): The code that raised it.

    Returns:
        str: ``Type: message`` plus the failing line when known.
    """
    msg = f"{type(exc).__name__}: {exc}"
    try:
        tb = traceback.extract_tb(exc.__traceback__)
        lineno = next((fr.lineno for fr in reversed(tb) if fr.filename == '<generated>'), None)
        src = code.split('\n')
        if lineno and 1 <= lineno <= len(src):
            msg += f"\n  → line {lineno}: {src[lineno - 1].strip()}"
    except Exception:
        _itk_log.exception("Handled exception in format_exec_error")
    return msg


def _bind(fn, ds):
    """Close an analysis function over the dataset, keeping its docstring."""
    def bound(*args, **kwargs):
        """Analysis function with the dataset already supplied."""
        return fn(ds, *args, **kwargs)
    bound.__doc__ = fn.__doc__
    bound.__name__ = fn.__name__
    return bound


def build_namespace(ds, collector, tables, findings):
    """Assemble what generated code can see.

    Args:
        ds (Dataset): The dataset.
        collector (FigureCollector): Receives the figures.
        tables (list): Receives ``show_table`` output.
        findings (list): Receives ``record_finding`` output.

    Returns:
        dict: The exec namespace.
    """
    def show_table(data, rows=None, title=''):
        """Show a DataFrame, a dict, a list of dicts or headers and rows as a table."""
        if isinstance(rows, str) and not title:
            title, rows = rows, None
        tables.append(_table_from(data, rows, title))

    def record_finding(claim, n=None, p=None, effect=None, evidence=''):
        """Record one finding for the exploration summary."""
        findings.append({'claim': str(claim), 'n': n, 'p': p, 'effect': effect,
                         'evidence': str(evidence or '')})

    def lod(element, quantity='mass_fg', sample=None):
        """Calibrated detection limit of an element, ``None`` when unknown."""
        return ds.lod(element, quantity, sample)

    def col(quantity, element):
        """Column name of a quantity for an element, e.g. ``col('mass', 'Fe')``."""
        return ds.column(quantity, element)

    def signal(sample, element, t0=None, t1=None):
        """Raw trace of one element in one run: a DataFrame of ``time_s`` and ``counts``."""
        if ds.acquisition is None:
            raise RuntimeError("The raw signal is not available for this data")
        return ds.acquisition.signal(sample, element, t0, t1)

    def sample_summary():
        """Per-sample results, one row per run and element (particles/mL, ug/L, background, limits)."""
        if ds.acquisition is None:
            raise RuntimeError("Per-sample results are not available for this data")
        return ds.acquisition.summary()

    plt = PyplotShim(collector)
    ns = {
        '__builtins__': SAFE_BUILTINS,
        'np': np, 'pd': pd, 'math': math, 'Counter': Counter, 'defaultdict': defaultdict,
        'df': ds.df, 'particles': ds.particles, 'elements': ds.elements,
        'samples': ds.samples, 'sample_names': ds.samples,
        'sample_name': ds.default_sample, 'runs': ds.runs(),
        'limits': ds.limits(), 'per_ml_factor': ds.per_ml_factor(),
        'data_context': ds.safe_context(),
        'show_table': show_table, 'record_finding': record_finding,
        'lod': lod, 'col': col, 'element': ds.resolve_element,
        'new_figure': collector.new_figure, 'plt': plt,
        'signal': signal, 'sample_summary': sample_summary,
    }
    ns.update(FIGURE_NAMESPACE)
    for name, fn in analysis.FUNCTIONS.items():
        ns[name] = _bind(fn, ds)
    try:
        from scipy import stats
        ns['stats'] = stats
    except Exception:
        _itk_log.exception("scipy.stats is not available to the sandbox")
    return ns


def _has_content(fig):
    """Whether any panel of a figure has something drawn on it."""
    for ax in fig.axes:
        if ax.lines or ax.patches or ax.images or ax.texts or ax.collections:
            return True
    return False


def _finish_figures(collector, result):
    """Style, render and describe the figures, collecting any drawing errors."""
    for i, fig in enumerate(collector.figures, start=1):
        try:
            style_figure(fig)
            png = render_png(fig)
            desc, warns = describe_figure(fig, i)
        except Exception as e:
            _itk_log.exception("Figure %d failed to draw", i)
            result.error = result.error or f"Figure {i} could not be drawn — {type(e).__name__}: {e}"
            continue
        title = fig._suptitle.get_text() if getattr(fig, '_suptitle', None) else ''
        if not title:
            titles = [ax.get_title() for ax in fig.axes if ax.get_title()]
            title = titles[0] if titles else f'Figure {i}'
        result.figures.append({'figure': fig, 'png': png, 'description': desc, 'title': title})
        result.warnings.extend(warns)


def execute(code, ds, timeout=CODE_EXEC_TIMEOUT, stop_event=None):
    """Run generated code against a dataset.

    The code runs until it finishes or *stop_event* is set, as the Stop
    button does; there is no time limit unless *timeout* is given.

    Args:
        code (str): Python written by the model.
        ds (Dataset): The dataset it works on.
        timeout (float): Seconds before the run is abandoned, ``None`` for no
            limit.
        stop_event (threading.Event): Set it from another thread to stop the
            code at its next line, as the Stop button does.

    Returns:
        ExecResult: Everything the code produced.
    """
    import matplotlib
    result = ExecResult()
    code = sanitize_code(code)
    refused = screen_code(code)
    if refused:
        result.error = refused
        return result
    collector = FigureCollector()
    tables, findings = [], []
    try:
        ns = build_namespace(ds, collector, tables, findings)
    except Exception as e:
        _itk_log.exception("Could not prepare the sandbox")
        result.error = f"The data could not be prepared — {type(e).__name__}: {e}"
        return result
    out = io.StringIO()
    err = [None]
    stop = stop_event if stop_event is not None else threading.Event()

    def on_line(frame, event, arg):
        """Abort the generated code at its next line once a stop is requested."""
        if stop.is_set():
            raise TimeoutError("stopped")
        return on_line

    def on_call(frame, event, arg):
        """Trace only frames of the generated code, so library calls run at full speed."""
        if frame.f_code.co_filename == '<generated>':
            return on_line
        return None

    def run():
        """Execute the code with the house figure style active."""
        sys.settrace(on_call)
        try:
            compiled = compile(code, '<generated>', 'exec')
            with redirect_stdout(out), matplotlib.rc_context(STYLE), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                exec(compiled, ns)
        except BaseException as e:
            err[0] = format_exec_error(e, code)
        finally:
            sys.settrace(None)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    deadline = None if timeout is None else time.monotonic() + timeout
    while worker.is_alive() and not stop.is_set() and (deadline is None or time.monotonic() < deadline):
        worker.join(timeout=0.05)
    if worker.is_alive() or stop.is_set():
        stopped_by_user = stop.is_set()
        stop.set()
        worker.join(timeout=2.0)
        if stopped_by_user:
            result.error = "Stopped by the user."
        else:
            result.error = (f"Code execution timed out after {timeout:g}s — simplify the query, "
                            "use vectorised pandas instead of Python loops, or work on fewer particles.")
        return result
    text = out.getvalue().strip()
    if len(text) > MAX_STDOUT_CHARS:
        text = text[:MAX_STDOUT_CHARS] + "\n... [output truncated]"
    result.text = text
    result.tables = tables
    result.findings = findings
    if err[0]:
        result.error = err[0]
        collector.figures = [f for f in collector.figures if _has_content(f)]
    _finish_figures(collector, result)
    nums = floats_in_text(text)
    for t in tables:
        nums.extend(_numbers_in_table(t))
    for f in findings:
        for k in ('n', 'p', 'effect'):
            v = to_float(f.get(k))
            if v is not None:
                nums.append(v)
        nums.extend(floats_in_text(f.get('claim', '')))
        nums.extend(floats_in_text(f.get('evidence', '')))
    result.numbers = nums
    return result


def compact_table(tbl, max_rows=15):
    """Plain-text rendering of a result table for the model.

    Args:
        tbl (dict): Table dict.
        max_rows (int): Rows to include.

    Returns:
        str: Header, rows and a count of the rows left out.
    """
    lines = [f"TABLE: {tbl.get('title', '')}"]
    if tbl.get('note'):
        lines.append(f"NOTE: {tbl['note']}")
    lines.append(" | ".join(str(h) for h in tbl.get('headers', [])))
    rows = tbl.get('rows', [])
    for r in rows[:max_rows]:
        lines.append(" | ".join(str(c) for c in r))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def result_digest(result, max_rows=15, max_text=2500):
    """Everything a result tells the model, compacted for its context window.

    Args:
        result (ExecResult): The result.
        max_rows (int): Rows per table.
        max_text (int): Characters of printed output.

    Returns:
        str: Text digest.
    """
    parts = []
    if result.error:
        parts.append(f"ERROR: {result.error}")
    if result.text:
        t = result.text if len(result.text) <= max_text else result.text[:max_text] + "\n... [truncated]"
        parts.append("PRINTED:\n" + t)
    for tbl in result.tables:
        parts.append(compact_table(tbl, max_rows))
    for fig in result.figures:
        parts.append("FIGURE SHOWN TO THE USER:\n" + fig['description'])
    if result.warnings:
        parts.append("FIGURE CHECKS:\n" + "\n".join(f"- {w}" for w in result.warnings))
    for f in result.findings:
        parts.append(f"FINDING RECORDED: {f['claim']}")
    if not parts:
        parts.append("(The code ran but produced nothing. Use show_table(), print() or a figure.)")
    return "\n\n".join(parts)
