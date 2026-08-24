"""Regression tests for the two export failures reported from a Chinese
Windows install (see the ``gbk`` / ``numpy.ndarray.__format__`` bug report).

1. ``'gbk' codec can't encode character '\\xb5'`` — the export writers opened
   files without an explicit encoding, so Python used the OS ANSI code page.
   Every unit label the exporter writes ('µL/s', 'g/cm³') is outside cp936.

2. ``unsupported format string passed to numpy.ndarray.__format__`` — a value
   that is normally a scalar arrived as a numpy array (moving-window
   thresholds and backgrounds are arrays), and NumPy refuses a format spec on
   anything with ``ndim >= 1``.

These tests exercise the pure helpers, so they run without PySide6 data or a
live MainWindow.
"""
import ast
import pathlib
import re

import numpy as np
import pytest

from utils.numeric_format import as_scalar as _as_scalar, fmt as _fmt

REPO = pathlib.Path(__file__).resolve().parents[1]
EXPORT_UTILS = REPO / "save_export" / "export_utils.py"


def test_every_text_open_in_export_utils_declares_an_encoding():
    """No ``open(..., 'w')`` may fall back to the OS default code page.

    Walks the export module's AST and flags every text-mode ``open`` call
    without an ``encoding`` keyword. Binary modes are exempt because they
    never touch a codec.
    """
    tree = ast.parse(EXPORT_UTILS.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"):
            continue
        mode = ""
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value or ""
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value or ""
        if "b" in mode:
            continue
        if not any(kw.arg == "encoding" for kw in node.keywords):
            offenders.append(node.lineno)
    assert not offenders, (
        f"open() without encoding= at {EXPORT_UTILS.name}:{offenders} — "
        "this fails on non-UTF-8 systems (cp936, cp1252) as soon as a unit "
        "label such as 'µ' or '³' is written."
    )


def test_unit_labels_survive_a_utf8_round_trip(tmp_path):
    """The exact characters that blew up on cp936 must write and read back."""
    path = tmp_path / "sample_results.csv"
    payload = "Transport Rate: 1.2345 µL/s\nElement Density (g/cm³)\nÅngström\n"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(payload)
    assert path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize("char", ["µ", "³", "²", "Å"])
def test_characters_the_exporter_writes_are_not_representable_in_gbk(char):
    """Documents *why* the explicit encoding is required, not optional.

    Each of these appears in a header or unit label the exporter writes, and
    none of them has a cp936 mapping.
    """
    with pytest.raises(UnicodeEncodeError):
        char.encode("gbk")


def test_numpy_arrays_break_plain_format_specs():
    """The exact upstream failure, pinned so it can't be misdiagnosed again."""
    with pytest.raises(TypeError, match="unsupported format string"):
        format(np.array([1.0, 2.0]), ".4f")


@pytest.mark.parametrize("value,expected", [
    (1.5, "1.5000"),
    (np.float64(1.5), "1.5000"),
    (np.array(1.5), "1.5000"),
    (np.array([1.5]), "1.5000"),
    (np.array([[1.5]]), "1.5000"),
    (np.array([1.0, 2.0]), "1.5000"),
])
def test_fmt_handles_every_numpy_shape(value, expected):
    """Every shape a scalar-valued quantity can arrive in must format.

    The cases are, in order: a plain float; a numpy scalar; a 0-d array, which
    NumPy already accepts; a size-1 array and a size-1 2-d array, which are the
    shapes that used to raise; and a multi-element array, which collapses to
    its mean (1.5).
    """
    assert _fmt(value, ".4f") == expected


def test_fmt_degrades_instead_of_aborting_the_file():
    """A bad cell must not cost the user the whole sample file.

    ``None`` stands for a missing dict key and the string for a sentinel such
    as the old ``method_data.get('slope', 'N/A')`` default; both now yield the
    fallback. An empty array is a real zero measurement, so it formats.
    """
    assert _fmt(None, ".2f") == "N/A"
    assert _fmt("not a number", ".2f") == "N/A"
    assert _fmt(np.array([], dtype=float), ".2f") == "0.00"


def test_as_scalar_returns_plain_python_floats():
    """Unwrapping must fully leave numpy, not hand back another numpy type."""
    assert isinstance(_as_scalar(np.float64(2.0)), float)
    assert isinstance(_as_scalar(np.array([2.0])), float)
    assert not isinstance(_as_scalar(np.array([2.0])), np.ndarray)


def test_no_raw_format_spec_remains_on_a_lookup_in_export_utils():
    """Values pulled from result dicts must go through ``fmt``.

    ``f"{d.get('slope'):.2e}"`` is the shape of the original bug: whatever the
    dict happens to hold is formatted directly, so an array or a string
    sentinel takes the whole file down.
    """
    src = EXPORT_UTILS.read_text(encoding="utf-8")
    bad = re.findall(r"\{[^{}]*\.get\([^{}]*\)\s*:\s*\.\d+[fed]\}", src)
    assert not bad, f"raw format spec applied to a dict lookup: {bad}"
