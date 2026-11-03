"""Mass-bias correction of isotope ratios drawn in Figure Builder panels.

A panel whose correction is the exponential law (Russell et al., 1978) has
every isotope ratio it plots, written ``A / B`` on an axis or as the value,
multiplied by

    K = (m_A / m_B) ** p,   p = ln(R_certified / R_measured) / ln(m_ref_num / m_ref_den)

where the reference pair (for example 205Tl / 203Tl, or 206Pb / 207Pb in NIST
SRM 981) has a certified ratio and a ratio measured on the instrument. This
is the correction of the Isotopic Ratio node, with the same masses.

The measured reference ratio can be

* measured in each sample from its ionic (time-series mean) signal, for a
  dissolved spike such as Tl added to the sample;
* measured in each sample from its particles, as the ratio of summed counts
  over particles carrying both reference isotopes; or
* one value typed for every sample.

Only a ratio of counts is corrected. A ratio of masses or moles is already
normalised to the calibration standard by each isotope's own slope, so
correcting it again would count the bias twice; such a ratio is left alone
with a note.

When a sample has no measured value of its own, the typed value is used and
the figure's notes say so. The reference itself is typed on the panel or read
from an Isotopic Ratio node on the canvas.

:func:`prepare` rewrites a panel's ratio ``A / B`` as ``(A / B) * mb_…``, a
per-particle factor column installed on the table, so every chart draws the
corrected ratio with no change of its own. Tools that need the measured
ratio, such as the counting-statistics band, read the plain ratio with
:func:`results.figure_builder.core.isotopes.split_factor` and the factor of
each group with :func:`group_factor`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re

import numpy as np

METHODS = {"none": "None", "exponential": "Exponential law"}
"""Corrections a panel can apply."""

SOURCES = {"node": "Isotopic Ratio node", "manual": "Typed here"}
"""Where the reference pair and its certified ratio come from."""

MEASURED = {"ionic": "Ionic signal", "particles": "Particles", "value": "One value"}
"""How the reference ratio measured on the instrument is obtained: in each sample from its
ionic signal, in each sample from its particles, or one value for all samples."""

EXPONENTIAL_LAW = "Exponential Law (instrumental mass fractionation)"
"""The Isotopic Ratio node's name for the exponential law."""

RATIO_KEYS = ("x", "y", "value", "y2")
"""Panel expressions that are corrected when they are an isotope ratio."""

FACTOR_PREFIX = "mb_"
"""Start of the name of a factor column installed on the table."""

MIN_REFERENCE_PARTICLES = 10
"""Particles carrying both reference isotopes a sample needs to measure its own ratio."""

CORRECTED = re.compile(r"^\(\s*(.+?)\s*\)\s*\*\s*(" + FACTOR_PREFIX + r"[A-Za-z0-9_]+)$")
"""A ratio rewritten by :func:`prepare`: ``(A / B) * mb_…``."""


def node_reference(scene) -> dict | None:
    """The exponential-law reference set up in an Isotopic Ratio node on the canvas.

    The first node whose correction is the exponential law with a complete
    reference (two isotopes, a certified and a measured ratio) is used.

    Args:
        scene: The canvas scene.

    Returns:
        ``{ref_num, ref_den, certified, measured}``, or ``None`` when no node
        has one.
    """
    for node in getattr(scene, "workflow_nodes", []) or []:
        if getattr(node, "node_type", "") != "isotopic_ratio_plot":
            continue
        cfg = getattr(node, "config", None) or {}
        if cfg.get("correction_method") != EXPONENTIAL_LAW:
            continue
        ref = {"ref_num": str(cfg.get("ref_isotope_num") or ""),
               "ref_den": str(cfg.get("ref_isotope_den") or "")}
        try:
            ref["certified"] = float(cfg.get("ref_certified_ratio"))
            ref["measured"] = float(cfg.get("ref_measured_ratio"))
        except (TypeError, ValueError):
            continue
        if ref["ref_num"] and ref["ref_den"] and ref["certified"] > 0 and ref["measured"] > 0 \
                and abs(ref["certified"] - ref["measured"]) > 1e-12:
            return ref
    return None


def _label_keys(window) -> dict[str, float]:
    """Isotope label to its mass key in the window's time series, e.g. ``205Tl`` → 204.97."""
    out = {}
    for el, isos in (getattr(window, "selected_isotopes", None) or {}).items():
        for iso in isos:
            key = f"{el}-{iso:.4f}"
            try:
                label = window.get_formatted_label(key)
            except Exception:
                label = f"{round(iso)}{el}"
            out[str(label)] = iso
    return out


def ionic_ratio(window, sample: str, num: str, den: str) -> float | None:
    """Ratio of the mean time-series signals of two isotopes in one sample.

    This is how the Isotopic Ratio node measures a dissolved reference such
    as a Tl spike; the whole acquisition of the sample is averaged.

    Returns:
        The ratio, or ``None`` when the sample or either isotope has no signal.
    """
    data = (getattr(window, "data_by_sample", None) or {}).get(sample)
    if not data:
        return None
    keys = _label_keys(window)
    if num not in keys or den not in keys:
        return None

    def mean_of(mass):
        try:
            key = window.find_closest_isotope(mass, data)
        except TypeError:
            key = window.find_closest_isotope(mass)
        except Exception:
            key = None
        if key is None or key not in data:
            return None
        values = np.asarray(data[key], dtype=float)
        return float(np.mean(values)) if values.size else None

    a, b = mean_of(keys[num]), mean_of(keys[den])
    if a is None or b is None or b <= 0 or a <= 0:
        return None
    return a / b


def attach(table, window, scene) -> None:
    """Give a particle table what mass-bias correction needs from the app.

    Sets ``table.node_reference`` from an Isotopic Ratio node on the canvas
    and ``table.ionic_ratio``, a callable ``(sample, num, den) -> ratio``
    reading each sample's time series from the main window.
    """
    try:
        table.node_reference = node_reference(scene) if scene is not None else None
    except Exception:
        table.node_reference = None
    if window is not None:
        table.ionic_ratio = lambda sample, num, den: ionic_ratio(window, sample, num, den)


def parse_pair(text: str) -> tuple[str, str] | None:
    """``"205Tl / 203Tl"`` → ``("205Tl", "203Tl")``; ``None`` when it is not two names."""
    parts = [p.strip() for p in str(text or "").replace(":", "/").split("/")]
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]


def _float(value) -> float | None:
    """A positive float, or ``None``."""
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def reference(panel: dict, table) -> tuple[dict | None, str]:
    """The reference a panel corrects with.

    Returns:
        ``(ref, problem)``: ``{ref_num, ref_den, certified, measured}`` (the
        measured value may be ``None`` when each sample measures its own), or
        ``None`` with the reason it is incomplete.
    """
    if panel.get("mb_source", "manual") == "node":
        ref = getattr(table, "node_reference", None)
        if not ref:
            return None, "no Isotopic Ratio node with the exponential law on the canvas"
        ref = dict(ref)
        typed = _float(panel.get("mb_measured"))
        if typed is not None:
            ref["measured"] = typed
        return ref, ""
    pair = parse_pair(panel.get("mb_ref"))
    if pair is None:
        return None, "write the reference pair, e.g. 205Tl / 203Tl"
    certified = _float(panel.get("mb_certified"))
    if certified is None:
        return None, "enter the certified ratio of the reference pair"
    measured = _float(panel.get("mb_measured"))
    if panel.get("mb_measured_mode", "value") == "value" and measured is None:
        return None, "enter the measured reference ratio, or measure it in each sample"
    return {"ref_num": pair[0], "ref_den": pair[1], "certified": certified,
            "measured": measured}, ""


def _resolve(table, label: str) -> str | None:
    """A label as the table spells it, or ``None`` when the table does not carry it."""
    try:
        return table.resolve_label(label)
    except Exception:
        return None


def measured_by_sample(panel: dict, table, ref: dict) -> tuple[dict, list[str]]:
    """The measured reference ratio of every sample (replicate) in the table.

    Returns:
        ``(ratios, notes)``: replicate name to measured ratio, and sentences
        naming samples that fell back to the typed value or were left
        uncorrected.
    """
    mode = panel.get("mb_measured_mode", "value")
    reps = list(dict.fromkeys(table.column("replicate").tolist())) if len(table) else []
    typed = ref.get("measured")
    ratios, fallback, missing = {}, [], []
    num, den = ref["ref_num"], ref["ref_den"]
    if mode == "particles":
        a_lab, b_lab = _resolve(table, num), _resolve(table, den)
        col = table.column("replicate")
        a = table.column(f"counts:{a_lab}") if a_lab else None
        b = table.column(f"counts:{b_lab}") if b_lab else None
        for r in reps:
            value = None
            if a is not None and b is not None:
                both = (col == r) & (a > 0) & (b > 0)
                if int(both.sum()) >= MIN_REFERENCE_PARTICLES and b[both].sum() > 0:
                    value = float(a[both].sum() / b[both].sum())
            ratios[r] = value
    elif mode == "ionic":
        fn = getattr(table, "ionic_ratio", None)
        for r in reps:
            try:
                ratios[r] = fn(r, num, den) if fn is not None else None
            except Exception:
                ratios[r] = None
    else:
        ratios = {r: typed for r in reps}
    for r in reps:
        if ratios.get(r) is None:
            if typed is not None:
                ratios[r] = typed
                if mode != "value":
                    fallback.append(str(r))
            else:
                missing.append(str(r))
    notes = []
    how = {"particles": "from its particles", "ionic": "from its ionic signal"}.get(mode, "")
    if fallback:
        notes.append(f"no {num}/{den} measured {how} in {', '.join(fallback)}; the typed "
                     f"value {typed:.6g} is used there")
    if missing:
        notes.append(f"{', '.join(missing)} left uncorrected: no {num}/{den} measured "
                     f"{how} and no value typed")
    return {r: v for r, v in ratios.items() if v is not None}, notes


def _factor_name(num: str, den: str, ref: dict, ratios: dict) -> str:
    """A stable column name for one ratio under one reference."""
    key = json.dumps([num, den, ref, sorted((str(k), v) for k, v in ratios.items())],
                     sort_keys=True, default=str)
    digest = hashlib.md5(key.encode()).hexdigest()[:6]
    clean = re.sub(r"[^A-Za-z0-9]", "", f"{num}_{den}")
    return f"{FACTOR_PREFIX}{digest}_{clean}"


def factor_column(table, num: str, den: str, ref: dict, ratios: dict) -> tuple[np.ndarray, dict]:
    """Exponential-law factor of ``num / den`` for every particle, from its sample's reference.

    Returns:
        ``(factors, per_sample)``: one factor per particle (1 where the sample
        has no reference), and replicate name to its factor.
    """
    from results.figure_builder.core.isotopes import exponential_factor
    col = table.column("replicate")
    out = np.ones(len(table), dtype=float)
    per = {}
    for r, measured in ratios.items():
        k = exponential_factor(num, den, ref["ref_num"], ref["ref_den"], ref["certified"], measured)
        if k is None:
            continue
        per[r] = k
        out[col == r] = k
    return out, per


def prepare(panel: dict, table, report=None) -> dict:
    """The panel with its isotope ratios mass-bias corrected, ready to draw.

    The panel itself is never changed; a corrected copy is returned. Notes
    on what was done go to ``report.stats``.
    """
    if panel.get("mb_method", "none") != "exponential" or panel.get("_mb_done"):
        return panel
    from results.figure_builder.core.isotopes import (
        exponential_factor, is_count_ratio, ratio_parts, split_factor)
    out = copy.copy(panel)
    out["_mb_done"] = True
    notes = []
    ref, problem = reference(panel, table)
    if ref is None:
        if report is not None:
            report.stats.append(f"Mass-bias correction not applied: {problem}")
        return out
    ratios, more = measured_by_sample(panel, table, ref)
    notes.extend(more)
    done = []
    for key in RATIO_KEYS:
        expr = (panel.get(key) or "").strip()
        if not expr:
            continue
        base, k = split_factor(expr)
        if k != 1.0 or CORRECTED.match(expr):
            continue
        parts = ratio_parts(base, table)
        if parts is None:
            continue
        num, den = parts
        if not is_count_ratio(base, table):
            notes.append(f"{num}/{den} left uncorrected: mass-bias correction applies to a ratio "
                         "of counts, and this one is read in another quantity")
            continue
        if exponential_factor(num, den, ref["ref_num"], ref["ref_den"], ref["certified"],
                              ref.get("measured") or ref["certified"]) is None:
            notes.append(f"{num}/{den} left uncorrected: an isotope mass could not be read")
            continue
        factors, per = factor_column(table, num, den, ref, ratios)
        name = _factor_name(num, den, ref, ratios)
        table.factors[name] = factors
        out[key] = f"({base}) * {name}"
        done.append((num, den, per))
    if report is not None and done:
        head = (f"Mass-bias correction, exponential law: {ref['ref_num']}/{ref['ref_den']} "
                f"certified {ref['certified']:.6g}, measured "
                + {"particles": "in each sample from its particles",
                   "ionic": "in each sample from its ionic signal"}.get(
                    panel.get("mb_measured_mode", "value"),
                    f"{ref.get('measured'):.6g}" if ref.get("measured") else "per sample"))
        report.stats.append(head)
        for num, den, per in done:
            shown = "; ".join(f"{r} ×{v:.5f} (measured {ratios[r]:.6g})" for r, v in per.items())
            report.stats.append(f"  {num}/{den}: {shown}")
    for n in notes:
        if report is not None:
            report.stats.append(f"Mass-bias correction: {n}")
    return out


def group_factor(panel: dict, table, mask, key: str = "y") -> float:
    """The correction factor of the particles in *mask* for the ratio on *key*.

    1 for an uncorrected ratio, the written factor for ``(A / B) * k``, and
    the mean factor of the masked particles for a ratio corrected per sample.
    """
    from results.figure_builder.core.isotopes import split_factor
    expr = (panel.get(key) or "").strip()
    m = CORRECTED.match(expr)
    if m and m.group(2) in getattr(table, "factors", {}):
        f = np.asarray(table.factors[m.group(2)], dtype=float)
        sel = f[np.asarray(mask, dtype=bool)] if mask is not None else f
        sel = sel[np.isfinite(sel) & (sel > 0)]
        return float(sel.mean()) if sel.size else 1.0
    return split_factor(expr)[1]
