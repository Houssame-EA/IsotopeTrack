# `sandbox.py`

Running the Python the model writes, safely enough for a local tool.

The code runs with a reduced set of builtins and a namespace holding the
particle table, the analysis functions and a figure factory. Before it runs,
an AST screen rejects the known ways out of such a namespace: underscore
attributes (``__class__``, frame and closure walking), file access through
numpy, pandas or matplotlib, and the dangerous builtins. This is a guard
against mistakes by a locally run model, not a security boundary.

Results come back as an :class:`ExecResult`: printed text, tables, figures,
recorded findings, and every number produced, which the no-fabrication check
compares the model's prose against.

---

## Constants

| Name | Value |
|------|-------|
| `CODE_EXEC_TIMEOUT` | `None` |
| `MAX_STDOUT_CHARS` | `20000` |
| `MAX_TABLE_ROWS` | `2000` |
| `SAFE_BUILTINS` | `{'abs': abs, 'all': all, 'any': any, 'bool': bool, 'dict'…` |
| `_BLOCKED_NAMES` | `frozenset({'open', 'eval', 'exec', 'compile', '__import__…` |
| `_BLOCKED_ATTRS` | `frozenset({'save', 'savez', 'savez_compressed', 'load', '…` |
| `_BLOCKED_ATTR_RE` | `re.compile('^(_.*\|read_.*\|print_.*\|to_(csv\|excel\|pickle\|p…` |
| `_IMPORT_RE` | `re.compile('^[ \\t]*(?:import\\s+[\\w.]+(?:\\s+as\\s+\\w+…` |
| `_DROP_LINE_RE` | `re.compile('^[ \\t]*(?:plt\|fig)\\.(?:show\|savefig\|close)\…` |
| `_ANYNUM_RE` | `re.compile('[-+]?(?:\\d[\\d,]*\\.?\\d*\|\\.\\d+)(?:[eE][-+…` |
| `_DECIMAL_RE` | `re.compile('[-+]?(?:\\d[\\d,]*\\.\\d+\|\\.\\d+)(?:[eE][-+]…` |
| `STATS_SHORTCUTS` | `('mannwhitneyu', 'kruskal', 'chi2_contingency', 'fisher_e…` |

## Classes

### `ExecResult`

What one run of generated code produced.

Attributes:
    text (str): Printed output.
    tables (list): Table dicts with ``title``, ``headers``, ``rows``, ``note``.
    figures (list): Figure dicts with ``figure``, ``png``, ``description``.
    findings (list): Findings recorded with ``record_finding``.
    error (str): Error message, empty when the code ran cleanly.
    warnings (list): Problems worth telling the model, e.g. empty panels.
    notes (list): Things the model should know that need no fix, e.g. a
        figure left out because nothing was drawn on it.
    numbers (list): Every number produced, for the fabrication check.

| Method | Signature | Description |
|--------|-----------|-------------|
| `produced` | `(self)` | Whether the code produced anything to show. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `sanitize_code` | `(code)` | Remove imports and display calls the sandbox provides or forbids. |
| `screen_code` | `(code)` | Statically check generated code before it runs. |
| `to_float` | `(tok)` | Parse a number written with optional thousands separators. |
| `floats_in_text` | `(s)` | All numbers in a string. |
| `_close` | `(a, b, rel=0.006)` | Whether two numbers agree to within rounding. |
| `_variants` | `(v)` | A computed value and the forms prose commonly restates it in. |
| `unverified_numbers` | `(prose, allowed)` | Decimal figures in prose that no computed output backs up. |
| `format_cell` | `(v)` | Format one table value for display. |
| `_table_from` | `(data, rows=None, title='')` | Normalise the many shapes ``show_table`` accepts into one table dict. |
| `_numbers_in_table` | `(tbl, cap=20000)` | Numbers held by a table, raw values first so no precision is lost. |
| `format_exec_error` | `(exc, code)` | Error text with the offending line of the generated code. |
| `_frames_in` | `(ns, skip=('df', 'runs'))` | DataFrames the generated code created, by variable name. |
| `error_hint` | `(exc, ns, ds)` | Advice that turns a common mistake into a one-step fix. |
| `_bind` | `(fn, ds)` | Close an analysis function over the dataset, keeping its docstring. |
| `build_namespace` | `(ds, collector, tables, findings)` | Assemble what generated code can see. |
| `_has_content` | `(fig)` | Whether any panel of a figure has something drawn on it. |
| `_axis_has_content` | `(ax)` | Whether one panel has something drawn on it; panel letters alone do not count. |
| `_hide_empty_panels` | `(fig)` | Hide the unused panels of a grid, e.g. the sixth of a 2 x 3 grid holding five plots. |
| `_finish_figures` | `(collector, result)` | Style, render and describe the figures, collecting any drawing errors. |
| `execute` | `(code, ds, timeout=CODE_EXEC_TIMEOUT, stop_event=None)` | Run generated code against a dataset. |
| `compact_table` | `(tbl, max_rows=15)` | Plain-text rendering of a result table for the model. |
| `result_digest` | `(result, max_rows=15, max_text=2500)` | Everything a result tells the model, compacted for its context window. |
