"""Figures that tell the story behind a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to f and a legend underneath. The panels
tell the finding's story in order: the pattern itself, the evidence behind
it, what it means, and the limits to keep in mind. Amounts are shown in one
unit only: element mass (fg), or counts when the samples carry no mass
calibration. Findings about the ion signal itself, isotope ratios,
interferences and signal drift, stay in counts, where they arise. Each axis
marks the element's own detection limit from the calibration (MDL in fg,
LOD in net counts), so it is plain how much of a pattern sits near the
detection limit, and the legend quotes the values. Panels comparing samples
carry a significance test, run on replicate medians when the samples are
replicated.

When the figure's particles are known (:attr:`FigureContext.table`), the
legend reports what the panels show, measured on those same particles with
:mod:`results.insights.evidence`. The legend opens with the conclusion and
a list of the checks the figure ran, each passed, failed or undecided, before
it describes the panels. Legends sit below their plot and reference lines are named
there, so no writing covers the data.

:func:`figure_for` builds the design; the panel adds it to the canvas as a
Figure Builder node fed by a selector holding the finding's samples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from results.insights import evidence as ev

QUANTITY_NAMES = {"counts": "counts", "mass": "mass (fg)", "d": "size (nm)"}
"""Readable names for the quantities a panel can show."""

SHARE_NOTE = " Each bar is labelled with its share and carries its 95% Wilson interval."
"""Sentence closing the caption of a panel of shares."""

DENSE_PARTICLES = 1500
"""Particles per group from which a density map of counts per cell is worth drawing."""

WITH_COLOR = "#c2410c"
WITHOUT_COLOR = "#64748b"


@dataclass
class FigureContext:
    """What the data offers the figure.

    Attributes:
        quantities: Quantity prefixes present: ``counts``, ``mass``, ``d``.
        limits: ``(prefix, label)`` to ``{sample: value}``, each element's
            detection limit per sample from the calibration: net LOD in
            counts, MDL in fg and SDL in nm.
        smallest: ``(prefix, label)`` to the smallest detected value, used
            only where no calibrated limit is available.
        multi_sample: Whether the figure covers more than one sample.
        groups: How many samples or replicate groups the figure compares.
        used: ``(prefix, label)`` pairs whose limit a panel drew, filled while
            the story is built so the legend can quote their values.
        main: The element detected in most of the figure's particles.
        present: Isotopes detected in enough particles to plot.
        table: The particle table the figure will draw from, when known;
            the legend's measured numbers and checks need it.
        mass_bias: The exponential-law reference set up in an Isotopic Ratio
            node, ``{ref_num, ref_den, certified, measured}``, when there is
            one; isotope ratios are then corrected for mass bias.
        checks: The checks run while the story is built, closing the legend.
    """

    quantities: set = field(default_factory=lambda: {"counts"})
    limits: dict = field(default_factory=dict)
    smallest: dict = field(default_factory=dict)
    multi_sample: bool = False
    groups: int = 1
    used: set = field(default_factory=set)
    main: str = ""
    present: set = field(default_factory=set)
    table: object = None
    mass_bias: dict | None = None
    checks: ev.Checks = field(default_factory=ev.Checks)


def _panel(kind: str, title: str, **settings) -> dict:
    """One panel's settings, before it is given a place on the page.

    Legends go below the plot and reference lines are named in them, so
    nothing is written over the data. Combination charts slant their long
    labels so they do not run into each other.
    """
    if kind == "combinations" and not settings.get("horizontal"):
        settings.setdefault("xtick_rotation", 45)
    return {"kind": kind, "title": title, "legend_loc": "below", "marks_in_legend": True,
            **settings}


def _expr(prefix: str, label: str) -> str:
    """Expression reading *label* in quantity *prefix*."""
    return label if prefix == "counts" else f"{prefix}:{label}"


LIMIT_NAMES = {"counts": "LOD", "mass": "MDL", "d": "SDL"}
"""What each quantity's detection limit is called in the calibration table."""

LIMIT_UNITS = {"counts": "net counts", "mass": "fg", "d": "nm"}

KINDS = {"mass": "mass", "d": "diameter"}
"""Unit kind of each quantity prefix that has one."""


def _qname(prefix: str) -> str:
    """Readable name of quantity *prefix*, in the app's chosen units."""
    from utils.unit import units
    return units.relabel(QUANTITY_NAMES[prefix])


def _shown(prefix: str, value):
    """*value* of quantity *prefix*, measured in the base unit, in the app's chosen unit.

    Figures made from a card draw the canvas's particles, which arrive in the
    chosen units, so their limit lines must be in those units too.
    """
    from utils.unit import units
    kind = KINDS.get(prefix)
    return units.convert(value, kind) if kind and value is not None else value

LIMIT_SPREAD = 1.10
"""Largest ratio between samples' limits that still reads as one shared value."""


def _limit(ctx: FigureContext, prefix: str, label: str) -> dict:
    """Detection-limit line settings for a panel showing *label* in *prefix*.

    The line sits at the element's calibrated limit. When the samples in the
    figure share it within :data:`LIMIT_SPREAD` the mean is drawn; otherwise
    the highest, the level above which every sample detects the element.
    Without a calibrated limit, mass and size axes fall back to the
    smallest particle detected.
    """
    values = [_shown(prefix, v) for v in (ctx.limits.get((prefix, label)) or {}).values()]
    if values:
        ctx.used.add((prefix, label))
        lo, hi = min(values), max(values)
        name = LIMIT_NAMES.get(prefix, "Detection limit")
        if hi <= lo * LIMIT_SPREAD:
            return {"dl_value": f"{sum(values) / len(values):.4g}", "dl_label": name}
        return {"dl_value": f"{hi:.4g}", "dl_label": f"{name} (highest sample)"}
    value = _shown(prefix, ctx.smallest.get((prefix, label)))
    if value:
        ctx.used.add((prefix, label))
        return {"dl_value": f"{value:.4g}", "dl_label": "Smallest detected"}
    return {}


def limits_sentence(ctx: FigureContext) -> str:
    """Legend sentence quoting the detection limits drawn in the figure.

    Each element's limits are listed per quantity, as one value when the
    samples share it and as a range across samples otherwise.
    """
    by_label: dict[str, list[str]] = {}
    fallback = False
    for prefix in ("counts", "mass", "d"):
        for p, label in sorted(ctx.used):
            if p != prefix:
                continue
            values = [_shown(prefix, v) for v in (ctx.limits.get((prefix, label)) or {}).values()]
            if not values:
                fallback = True
                continue
            lo, hi = min(values), max(values)
            from utils.unit import units
            unit = units.relabel(LIMIT_UNITS[prefix])
            amount = (f"{_fmt(sum(values) / len(values))} {unit}" if hi <= lo * LIMIT_SPREAD
                      else f"{_fmt(lo)}–{_fmt(hi)} {unit} across samples, line at the highest")
            by_label.setdefault(label, []).append(f"{LIMIT_NAMES[prefix]} {amount}")
    parts = []
    if by_label:
        listed = "; ".join(f"{label}: {'; '.join(items)}" for label, items in by_label.items())
        parts.append("Dashed lines mark each element's detection limit from the calibration "
                     f"({listed}). LOD is the net-count limit from peak detection, MDL that "
                     "limit converted to mass with the calibration sensitivity and transport "
                     "rate, and SDL the matching diameter of a sphere of the pure element.")
    if fallback:
        parts.append("Where no calibrated limit was available, the dashed line marks the "
                     "smallest particle detected instead.")
    return " ".join(parts)


def _fmt(value: float) -> str:
    """Short number for a legend."""
    return f"{value:.3g}"


def _histogram(ctx: FigureContext, prefix: str, label: str, title: str = "", **extra) -> dict:
    """Histogram of one element in one quantity, with its detection limit marked.

    All particles are pooled; pass ``group_by`` in *extra* to split them.
    """
    name = _qname(prefix)
    return _panel("histogram", title or f"{label} {name}", value=_expr(prefix, label),
                  log_x=True, bins=40, x_label=f"{label} {name}",
                  **_limit(ctx, prefix, label), **extra)


def _unit(ctx: FigureContext) -> str:
    """The one quantity amount panels use: mass when calibrated, counts otherwise."""
    return "mass" if "mass" in ctx.quantities else "counts"


def _amount(ctx: FigureContext, label: str) -> str:
    """Expression reading *label* in the figure's amount unit."""
    return _expr(_unit(ctx), label)


def _amount_name(ctx: FigureContext, label: str) -> str:
    """Axis name for *label* in the figure's amount unit, e.g. ``"Pb mass (fg)"``."""
    return f"{label} {_qname(_unit(ctx))}"


def _with_without(label: str, other: str) -> dict:
    """Grouping rules splitting particles by whether they carry *other*."""
    return {"group_by": "rules", "show_other": False, "rules": [
        {"name": f"with {other}", "when": f"{other} > 0", "color": WITH_COLOR},
        {"name": f"without {other}", "when": f"{other} == 0", "color": WITHOUT_COLOR},
    ]}


def _by_sample(ctx: FigureContext) -> dict:
    """Group by sample when there is more than one."""
    return {"group_by": "sample"} if ctx.multi_sample else {}


def _detail(s, label: str, default: str = "") -> str:
    """Return one of a finding's numbers by its label, or *default*."""
    for key, value in s.details or ():
        if str(key) == label:
            return str(value)
    return default


def _ratio_lines(natural, axis: str) -> dict:
    """A reference line at the natural ratio on the given axis (``"x"`` or ``"y"``)."""
    if not natural:
        return {}
    return {"vlines" if axis == "x" else "hlines": f"{natural:.6g}"}


def _test(groups: int, log_values: bool = True) -> dict:
    """Significance test settings for a panel comparing *groups* groups.

    Two groups get Welch's t-test, the form of Student's t-test that does not
    assume equal variances, with the p-value printed. Three or four groups get
    Welch's t-test on every pair with Holm's correction, shown as stars. More
    groups get a one-way ANOVA, so the panel is not buried in brackets. With
    *log_values* the test runs on log10 values, because particle signals,
    masses and sizes are close to log-normal. Each replicate's median is
    marked, and when every group is replicated the test runs on those
    medians, one value per replicate, instead of on every particle.
    """
    if groups < 2:
        return {}
    base = {"test_log": bool(log_values), "rep_medians": True, "test_unit": "replicates"}
    if groups == 2:
        return {**base, "test": "welch", "pairs": "all", "p_format": "p"}
    if groups <= 4:
        return {**base, "test": "welch", "pairs": "all", "correction": "holm",
                "p_format": "stars"}
    return {**base, "test": "anova"}


def _test_sentence(groups: int, what: str, log_values: bool = True) -> str:
    """One sentence naming the test a panel shows and how to read it."""
    if groups < 2:
        return ""
    on = f"log10 {what}" if log_values else what
    if groups == 2:
        test = f"Welch's t-test on {on} gives the p-value shown"
    elif groups <= 4:
        test = (f"Brackets give Welch's t-test on {on} for each pair, Holm-corrected "
                "(* p < 0.05, ** p < 0.01, *** p < 0.001, ns not significant)")
    else:
        test = f"The p-value is a one-way ANOVA on {on}"
    return (f" {test}. White diamonds mark each replicate's median; when every group has two "
            "or more replicates the test uses those medians, one value per replicate, otherwise "
            "it counts every particle, and then with thousands of particles even a small shift "
            "is significant, so the size of the difference matters as much as p.")


def _crust_known(minor: str, major: str) -> bool:
    """Whether the upper crust gives a ratio for *minor* to *major*."""
    from results.figure_builder.core.references import crust_ratio
    try:
        crust_ratio(minor, major)
    except ValueError:
        return False
    return True


def _can_check(ctx: FigureContext, major: str, minor: str) -> bool:
    """Whether a detectability check of *minor* in *major* particles can be drawn.

    It needs element masses, a calibrated mass detection limit for the minor
    element and an upper-crust value for both elements.
    """
    return ("mass" in ctx.quantities and ("mass", minor) in ctx.limits and bool(major)
            and major != minor and _crust_known(minor, major))


def _detect_box(ctx: FigureContext, major: str, minor: str, title: str, **grouping) -> dict:
    """Box plot of the major element's mass with the mass needed to see *minor*."""
    return _panel("box", title, value=f"mass:{major}", log_y=True, ptl_minor=minor,
                  y_label=f"{major} mass (fg)", **grouping)


def _detect_caption(major: str, minor: str) -> str:
    """Sentence explaining a detectability panel."""
    return (f"The dashed line is the {major} mass a particle needs before {minor}, present at the "
            f"upper-crust {minor}:{major} ratio, would clear its detection limit. Particles below "
            f"it may hold {minor} unseen, so a missing {minor} there says nothing.")


def _strip(ctx: FigureContext, el: str, title: str, by: str = "sample") -> dict:
    """Every particle as a dot per sample, coloured by its element combination."""
    prefix = "mass" if "mass" in ctx.quantities else "counts"
    return _panel("strip", title, value=_expr(prefix, el), group_by=by, log_y=True,
                  strip_horizontal=True, strip_color="combination", strip_size="n_elements",
                  strip_summary="median_iqr", top_n=5, marker_size=10, alpha=0.6,
                  x_label=f"{el} {_qname(prefix)}")


def _strip_caption(el: str) -> str:
    """Sentence explaining a bubble dot plot."""
    return (f"Every {el} particle as a dot, coloured by the elements found with it and larger "
            "when it carries more elements; the bar marks the median and quartiles.")


def _minerals_for(elements) -> list[str]:
    """Reference minerals holding at least two of *elements*, for a ternary."""
    from results.figure_builder.core import references as R
    try:
        symbols = [R.symbol_of(e) for e in elements]
    except ValueError:
        return []
    out = []
    for name, formula in R.minerals().items():
        try:
            atoms = R.parse_formula(formula)
        except ValueError:
            continue
        if sum(1 for sym in symbols if atoms.get(sym)) >= 2:
            out.append(name)
    return out[:6]


def _used(s, num: str, den: str, extra: str = "") -> str:
    """Filter keeping the particles the finding's ratio was measured on.

    Both isotopes must be detected and, when the finding records it, the
    more abundant isotope must sit at or above the signal cut the card's
    median used. *extra* is joined on with ``and``.
    """
    rule = f"{num} > 0 and {den} > 0"
    cut = (getattr(s, "facts", None) or {}).get("ratio_cut")
    if cut:
        rule += f" and {cut[0]} >= {cut[1]:.6g}"
    return f"{rule} and {extra}" if extra else rule


def _cut_sentence(s) -> str:
    """Sentence saying which particles a ratio panel keeps, or nothing."""
    cut = (getattr(s, "facts", None) or {}).get("ratio_cut")
    if not cut:
        return ""
    return (f" Only particles with {cut[0]} at or above {cut[1]:.4g} counts, the upper half of its "
            "signal, are used, as for the card's numbers: near the detection limit the minor "
            "isotope is seen only when it happens to read high.")


def _cut_line(s, den: str) -> dict:
    """A vertical line at the signal cut, when the cut is on the denominator."""
    cut = (getattr(s, "facts", None) or {}).get("ratio_cut")
    return {"vlines": f"{cut[1]:.6g}"} if cut and cut[0] == den else {}


def _cut_line_sentence(s, den: str) -> str:
    """Sentence explaining the signal-cut line, when the panel draws one."""
    if not _cut_line(s, den):
        return ""
    return (" The vertical dashed line is the signal cut used for the card's numbers; below "
            "it the ratio is pulled up by the threshold.")


def _bias_factor(ctx: FigureContext, num: str, den: str) -> float | None:
    """Mass-bias correction factor for *num*/*den*, when a reference is set up."""
    ref = ctx.mass_bias or {}
    if not ref:
        return None
    from results.figure_builder.core.isotopes import exponential_factor
    k = exponential_factor(num, den, ref.get("ref_num", ""), ref.get("ref_den", ""),
                           ref.get("certified"), ref.get("measured"))
    return k if k and abs(k - 1.0) > 1e-9 else None


def _ratio(ctx: FigureContext, num: str, den: str) -> str:
    """The ratio expression the figure plots, corrected for mass bias when it can be."""
    k = _bias_factor(ctx, num, den)
    return f"({num} / {den}) * {k:.6g}" if k else f"{num} / {den}"


def _ratio_name(ctx: FigureContext, num: str, den: str) -> str:
    """Axis name of a ratio, saying when it is corrected."""
    return f"{num}/{den}" + (" (corrected)" if _bias_factor(ctx, num, den) else "")


def _bias_sentence(ctx: FigureContext, num: str, den: str, natural) -> str:
    """Sentence saying how mass bias was handled."""
    k = _bias_factor(ctx, num, den)
    from results.figure_builder.core.isotopes import is_radiogenic
    out = ""
    if k:
        ref = ctx.mass_bias
        out = (f" Ratios are corrected for mass bias with the exponential law (Russell et al., "
               f"1978), factor {k:.5g}, from the {ref['ref_num']}/{ref['ref_den']} reference "
               f"set up in the Isotopic Ratio node ({ref['measured']:.5g} measured against "
               f"{ref['certified']:.5g} certified).")
    elif natural:
        out = (" Ratios are not corrected for mass bias: no exponential-law reference is set up "
               "in an Isotopic Ratio node, so a few percent between the measured and the natural "
               "ratio can come from mass bias alone.")
    if natural and is_radiogenic(num):
        out += (" The isotope composition of this element varies in nature, so the tabulated "
                "natural ratio is a representative value, not an expectation.")
    return out


def _ratio_signal(ctx: FigureContext, num: str, den: str, title: str, natural, **extra) -> dict:
    """The ratio of each particle against its denominator counts, with the counting band."""
    return _panel("scatter", title, x=den, y=_ratio(ctx, num, den), log_x=True, trend="median",
                  poisson_band=2.0, natural_line=bool(natural), x_label=f"{den} counts",
                  y_label=_ratio_name(ctx, num, den), marker_size=10, **extra)


def _band_sentence(den: str, natural, grouped: bool = False) -> str:
    """Sentence explaining the counting band on a ratio-against-signal panel."""
    whose = "Each colour's shaded band is its" if grouped else "The shaded band is the"
    return (f" {whose} mean ratio ± 2σ that counting statistics alone would give "
            f"(σ = √(R(1 + R)/N), N the {den} counts), so it narrows as the signal grows; the solid "
            "line is the running median"
            + (" and the dash-dot line the natural abundance ratio" if natural else "")
            + ". A ToF detector spreads the signal a little more than pure counting does, so a "
              "few more than 5% of points outside the band is expected; a median that leaves "
              "the band is not.")


def _spread_sentence(ctx: FigureContext, s, num: str, den: str, grouped: bool = False) -> str:
    """Measured share inside the band and excess scatter, per sample when *grouped*."""
    table = ctx.table
    if table is None:
        return ""
    k = _bias_factor(ctx, num, den) or 1.0
    rule = _used(s, num, den)
    parts = []
    worst = None
    units = ([(name, table.column("sample") == name) for name in table.samples()]
             if grouped else [("", None)])
    for name, m in units:
        st = ev.ratio_spread(table, num, den, rule, k, m)
        if st is None:
            continue
        parts.append((f"{name}: " if name else "")
                     + f"{ev.pct(st['inside'])} inside the band, excess scatter {st['excess']:.2f}")
        worst = st["excess"] if worst is None else max(worst, st["excess"])
    if not parts:
        return ""
    if worst is not None and worst < ev.EXCESS_LOW:
        ctx.checks.add(None, f"ratio scatter is only {worst:.2f} of counting statistics, so these "
                             "counts are not raw ion counts and the band overstates the noise")
    elif worst is not None:
        ctx.checks.add(worst <= ev.EXCESS_OK,
                       f"ratio scatter {'matches' if worst <= ev.EXCESS_OK else 'exceeds'} counting "
                       f"statistics (excess scatter {worst:.2f}"
                       + ("; above 1.3 means isotopically different particles)" if worst > ev.EXCESS_OK
                          else ")"))
    return (" Measured: " + "; ".join(parts) + ". Excess scatter is the spread of the ratios in "
            "units of their counting σ: about 1 for one isotopic population, well above 1 when "
            "the particles differ.")


def _drift_check(ctx: FigureContext, s, num: str, den: str) -> str:
    """Check, above the signal cut, whether the ratio still changes with signal."""
    if ctx.table is None:
        return ""
    rho, p, n = ev.ratio_drift(ctx.table, num, den, _used(s, num, den))
    if not math.isfinite(rho):
        return ""
    steady = abs(rho) < ev.DRIFT_RHO or p >= 0.05
    ctx.checks.add(steady, f"above the signal cut the ratio {'stays steady' if steady else 'still drifts'} "
                           f"with signal (ρ = {rho:+.2f}, {ev.p_text(p)}, {n:,} particles)")
    return ""


def _natural_check(ctx: FigureContext, s, num: str, den: str, natural) -> None:
    """Check how far the (corrected) median ratio sits from the natural ratio."""
    if ctx.table is None or not natural:
        return
    k = _bias_factor(ctx, num, den) or 1.0
    st = ev.ratio_spread(ctx.table, num, den, _used(s, num, den), k)
    if st is None:
        return
    gap = st["median"] / natural - 1.0
    from results.figure_builder.core.isotopes import is_radiogenic
    if is_radiogenic(num):
        ctx.checks.add(None, f"median {st['median']:.4g} is {gap:+.1%} from the tabulated natural "
                             "ratio, which this element need not follow")
        return
    ok = abs(gap) <= (0.02 if k != 1.0 else 0.05)
    ctx.checks.add(ok, f"median {'corrected ' if k != 1.0 else ''}ratio {st['median']:.4g} is "
                       f"{gap:+.1%} from natural"
                       + ("" if ok else (" — more than mass bias explains" if k != 1.0
                                         else " — more than uncorrected mass bias usually explains")))


def _three_isotope(ctx: FigureContext, s, num: str, den: str, **extra):
    """The ²⁰⁸Pb/²⁰⁶Pb against ²⁰⁷Pb/²⁰⁶Pb plot with source references, when Pb allows it."""
    from results.figure_builder.core.references import symbol_of
    try:
        if symbol_of(num) != "Pb":
            return None
    except ValueError:
        return None
    labels = {lab for lab in ctx.present if lab.endswith("Pb") or lab.startswith("Pb")}
    from results.figure_builder.core.isotopes import canonical
    have = {canonical(lab): lab for lab in labels}
    if not all(k in have for k in ("206Pb", "207Pb", "208Pb")):
        return None
    p6, p7, p8 = have["206Pb"], have["207Pb"], have["208Pb"]
    rule = f"{p6} > 0 and {p7} > 0 and {p8} > 0"
    cut = (getattr(s, "facts", None) or {}).get("ratio_cut")
    if cut:
        rule += f" and {cut[0]} >= {cut[1]:.6g}"
    rx, ry = _ratio(ctx, p7, p6), _ratio(ctx, p8, p6)
    from results.figure_builder.core.references import isotope_sources, source_ratio
    sources = [(source_ratio(n, p7, p6), source_ratio(n, p8, p6)) for n in isotope_sources()]
    sources = [(x, y) for x, y in sources if x is not None and y is not None]
    panel = _panel("scatter", "Three-isotope plot", x=rx, y=ry,
                   filter=rule, iso_refs="all", iso_ref_line=len(sources) == 2,
                   ellipse="mean95", x_label=_ratio_name(ctx, p7, p6),
                   y_label=_ratio_name(ctx, p8, p6), marker_size=6, alpha=0.15, **extra)
    grouped = extra.get("group_by") == "sample"
    whose = "each sample's" if grouped else "the sample's"
    caption = ("²⁰⁸Pb/²⁰⁶Pb against ²⁰⁷Pb/²⁰⁶Pb, the standard plot for tracing lead to its "
               f"source. The filled dot is {whose} own value, the ratio of its summed counts, "
               "and the ellipse around it the 95% region of that value; the faint points are "
               "the particles, whose scatter is mostly counting noise. Open symbols are "
               "reference sources (average crust after Stacey and Kramers 1975, Broken Hill "
               "ore, and any added under Reference values)"
               + (", joined by a dotted mixing line" if len(sources) == 2 else "")
               + "; a value on the line between two sources is a mixture of them, and an "
                 "ellipse clear of a source rules that source out on its own. Add local "
                 "sources, such as a smelter's ore, under Reference values.")
    if ctx.table is not None:
        try:
            xs, ys = dict(ev.pooled(ctx.table, rx, rule)), dict(ev.pooled(ctx.table, ry, rule))
        except Exception:
            xs, ys = {}, {}
        rows = [(n, xs[n], ys[n]) for n in xs if n in ys]
        if rows:
            from results.figure_builder.core.estimates import fmt_pm
            caption += (" Measured: " + "; ".join(
                (f"{n}: " if grouped or len(rows) > 1 else "")
                + f"²⁰⁷Pb/²⁰⁶Pb {fmt_pm(ex.value, ex.half)}, ²⁰⁸Pb/²⁰⁶Pb {fmt_pm(ey.value, ey.half)} "
                  f"({ex.n:,} particles)" for n, ex, ey in rows) + ".")
            window = _zoom([(ex.value, ex.half, ey.value, ey.half) for _n, ex, ey in rows], sources)
            if window:
                panel.update(window)
                caption += (" The axes are zoomed to the sample values and the sources; "
                            "particles further out are not shown.")
    return panel, caption


ZOOM_PAD = 0.3
"""Margin left around the values and sources of a zoomed plot, as a share of their span."""


def _zoom(values, sources) -> dict:
    """Axis limits framing group values, their intervals and the reference sources.

    Args:
        values: ``(x, x_half, y, y_half)`` per group.
        sources: ``(x, y)`` per reference source.

    Returns:
        ``x_min``, ``x_max``, ``y_min`` and ``y_max`` as panel settings, or
        an empty dict when there is nothing to frame.
    """
    xs = [v for x, hx, _y, _hy in values for v in (x - 1.6 * hx, x + 1.6 * hx)] + [s[0] for s in sources]
    ys = [v for _x, _hx, y, hy in values for v in (y - 1.6 * hy, y + 1.6 * hy)] + [s[1] for s in sources]
    if len(xs) < 2 or not all(math.isfinite(v) for v in xs + ys):
        return {}
    out = {}
    for axis, vals in (("x", xs), ("y", ys)):
        lo, hi = min(vals), max(vals)
        pad = max(hi - lo, abs(hi) * 0.01, 1e-9) * ZOOM_PAD
        out[f"{axis}_min"], out[f"{axis}_max"] = f"{lo - pad:.5g}", f"{hi + pad:.5g}"
    return out


def _estimate(ctx: FigureContext, s, num: str, den: str, natural, check: bool = False):
    """The ratio of each sample as one value with its 95% interval, and its caption.

    Args:
        check: Whether a difference between the samples is the finding, so
            the largest difference is added to the figure's checks.
    """
    ratio = _ratio(ctx, num, den)
    used = _used(s, num, den)
    panel = _panel("estimate", f"{num}/{den} by sample", value=ratio, group_by="sample",
                   filter=used, x_label=_ratio_name(ctx, num, den), **_ratio_lines(natural, "x"))
    caption = (f"Each sample's {num}/{den} as the ratio of its summed counts, with its 95% "
               "interval. Large, well-counted particles decide this value, so it is steadier "
               "than the median of the particles' own ratios (open diamond), which many small, "
               "noisy particles pull. Open circles are the replicates of a sample, each on its "
               "own. Samples whose intervals stand clear of each other differ"
               + (", and the dashed line is the natural abundance ratio." if natural else "."))
    if ctx.table is None:
        return panel, caption
    try:
        rows = ev.pooled(ctx.table, ratio, used)
    except Exception:
        rows = []
    if not rows:
        return panel, caption
    from results.figure_builder.core.estimates import difference, fmt_pm
    caption += (" Measured: " + "; ".join(f"{n} {fmt_pm(e.value, e.half)} ({e.n:,} particles)"
                                           for n, e in rows) + ".")
    if len(rows) >= 2:
        (na, ea), (nb, eb) = max(((a, b) for i, a in enumerate(rows) for b in rows[i + 1:]),
                                 key=lambda pair: abs(pair[0][1].value - pair[1][1].value))
        z, p = difference(ea, eb)
        if math.isfinite(z):
            gap = ea.value / eb.value - 1 if eb.value else math.nan
            caption += (f" The largest difference, {na} against {nb}, is {gap:+.1%} "
                        f"(z = {z:.2f}, {ev.p_text(p)}).")
            if check:
                ctx.checks.add(p < 0.05, f"the samples' pooled ratios "
                               + ("differ" if p < 0.05 else "do not differ")
                               + f": {na} {fmt_pm(ea.value, ea.half)} against {nb} "
                                 f"{fmt_pm(eb.value, eb.half)} ({ev.p_text(p)})")
    return panel, caption


def _isotope_pair(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = _ratio(ctx, num, den)
    name = _ratio_name(ctx, num, den)
    used = _used(s, num, den)
    median = _detail(s, "Median") or _detail(s, "Measured median")
    found = (f"The {num}/{den} ratio of each particle; the card's median is {median}"
             + (f", against {natural:.4g} for natural abundance (line)" if natural else "")
             + ".")
    if s.explain_key == "isotope_two":
        found = (f"The {num}/{den} ratio of each particle falls into two groups, near "
                 f"{_detail(s, 'Lower population')} and {_detail(s, 'Upper population')}, "
                 "so the sample holds two kinds of particles with different isotope "
                 "signatures.")
    if ctx.table is not None:
        k = _bias_factor(ctx, num, den) or 1.0
        st = ev.ratio_spread(ctx.table, num, den, used, k)
        if st is not None:
            v = ev.values(ctx.table, ratio, used)
            m, lo, hi = ev.median_ci(v)
            found += (f" Measured on the {st['n']:,} particles shown: median {m:.4g} "
                      f"(95% CI {ev.fmt(lo, 4)}–{ev.fmt(hi, 4)}).")
            try:
                from results.figure_builder.charts.estimate import group_estimate
                from results.figure_builder.core.estimates import fmt_pm
                keep = ev.mask(ctx.table, used) & (ev._eval(ctx.table, ratio) > 0)
                whole = group_estimate(ctx.table, ratio, keep)
            except Exception:
                whole = None
            if whole is not None:
                found += (f" The ratio of the summed counts, which large particles decide, is "
                          f"{fmt_pm(whole.value, whole.half)} (95% interval).")
    story = [
        (_panel("histogram", f"{num}/{den} in each particle", value=ratio, bins=50,
                filter=used, x_label=name, **_ratio_lines(natural, "x")),
         found + _cut_sentence(s) + _bias_sentence(ctx, num, den, natural)),
        (_ratio_signal(ctx, num, den, f"{num}/{den} against {den} signal", natural,
                       filter=f"{num} > 0 and {den} > 0", **_cut_line(s, den)),
         f"Every particle carrying both isotopes, its {num}/{den} ratio against its {den} counts."
         + _band_sentence(den, natural) + _cut_line_sentence(s, den)
         + _spread_sentence(ctx, s, num, den) + _drift_check(ctx, s, num, den)),
    ]
    three = _three_isotope(ctx, s, num, den, **({"group_by": "sample"} if ctx.multi_sample else {}))
    if three:
        story.append(three)
    story.append((_histogram(ctx, "counts", den, f"{den} counts and detection limit"),
                  f"{den} counts against the detection limit (dashed line): the closer most "
                  "particles sit to it, the wider their ratios scatter."))
    if ctx.multi_sample:
        panel, caption = _estimate(ctx, s, num, den, natural)
        story.insert(1, (panel, caption + " A sample far from the others should be looked at "
                                          "before the samples are pooled."))
    _natural_check(ctx, s, num, den, natural)
    return story


def _isotope_track(s, ctx, natural=None):
    num, den, other = s.elements[0], s.elements[1], s.elements[2]
    ratio = _ratio(ctx, num, den)
    name = _ratio_name(ctx, num, den)
    rho = _detail(s, "Rank correlation (ρ)")
    split = _with_without(num, other)
    with_text = ""
    if ctx.table is not None:
        a = ev.values(ctx.table, ratio, _used(s, num, den, f"{other} > 0"))
        b = ev.values(ctx.table, ratio, _used(s, num, den, f"{other} == 0"))
        if a.size >= 5 and b.size >= 5:
            fold, lo, hi = ev.fold_ci(a, b)
            with_text = (f" Measured: median {np.median(a):.4g} with {other} ({a.size:,} particles) "
                         f"against {np.median(b):.4g} without ({b.size:,}), a {fold - 1:+.1%} "
                         f"difference (95% CI {ev.fmt((lo - 1) * 100, 2)}% to "
                         f"{ev.fmt((hi - 1) * 100, 2)}%).")
            ctx.checks.add(bool(np.isfinite(lo) and (lo > 1 or hi < 1)),
                           f"ratio with and without {other} "
                           + ("differs beyond its 95% interval" if np.isfinite(lo) and (lo > 1 or hi < 1)
                              else "overlaps within its 95% interval"))
            sig_a = ev.values(ctx.table, den, _used(s, num, den, f"{other} > 0"))
            sig_b = ev.values(ctx.table, den, _used(s, num, den, f"{other} == 0"))
            if sig_a.size and sig_b.size:
                size_ratio = float(np.median(sig_a) / np.median(sig_b))
                same = 0.67 <= size_ratio <= 1.5
                ctx.checks.add(same, f"particles with {other} carry "
                                     + (f"a similar {den} signal ({size_ratio:.2f}×)" if same else
                                        f"{size_ratio:.2f}× the {den} signal, so counting noise "
                                        "differs between the two groups"))
    return [
        (_panel("scatter", f"{num}/{den} against {other}", x=_amount(ctx, other), y=ratio,
                log_x=True, trend="median", natural_line=bool(natural),
                filter=_used(s, num, den, f"{other} > 0"), marker_size=10,
                x_label=_amount_name(ctx, other), y_label=name),
         f"In particles carrying {other}, a different element, the {num}/{den} isotope ratio "
         f"changes with the amount of {other}" + (f" (ρ = {rho})" if rho else "")
         + "; the solid line is the running median"
         + (" and the dash-dot line the natural ratio." if natural else ".")
         + _cut_sentence(s) + _bias_sentence(ctx, num, den, natural)),
        (_panel("box", f"{num}/{den} with and without {other}", value=ratio,
                filter=_used(s, num, den), y_label=name, **split,
                **_ratio_lines(natural, "y"), **_test(2, log_values=False)),
         f"The ratio in particles with and without {other}."
         + _test_sentence(2, "ratios", log_values=False) + with_text),
        (_ratio_signal(ctx, num, den, f"{num}/{den} against {den} signal, with and without {other}",
                       natural, filter=f"{num} > 0 and {den} > 0", **split),
         f"The same ratio against the {den} signal, coloured by whether the particle carries "
         f"{other}." + _band_sentence(den, natural, grouped=True)
         + f" Medians that run apart at the same signal mean the two kinds of particles differ "
           f"in isotope signature; if the {other} particles only sit at a different signal "
           "inside one shared band, the trend comes from particle size and counting statistics "
           f"rather than from {other}."),
        (_histogram(ctx, _unit(ctx), other,
                    f"{other} {_qname(_unit(ctx))} and detection limit"),
         f"Particles whose {other} is below its detection limit (dashed line) are counted "
         "as without it, so the two groups overlap a little."),
    ]


def _isotope_groups(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = _ratio(ctx, num, den)
    name = _ratio_name(ctx, num, den)
    used = _used(s, num, den)
    diff = _detail(s, "Difference")
    spread = _detail(s, "Spread between replicates")
    measured = ""
    if ctx.table is not None:
        meds = ev.replicate_medians(ctx.table, ratio, used)
        listed = [f"{smp}: {np.median(m):.4g}" + (f" ({len(m)} replicates, {min(m):.4g}–{max(m):.4g})"
                                                   if len(m) > 1 else "")
                  for smp, m in meds.items() if m]
        if listed:
            measured = " Measured medians: " + "; ".join(listed) + "."
        p, method = ev.replicate_test(meds, log=False)
        if p is not None:
            ctx.checks.add(p < 0.05, f"{method}: {ev.p_text(p)}")
        else:
            ctx.checks.add(None, "samples not replicated, so the test counts particles")
    est_panel, est_caption = _estimate(ctx, s, num, den, natural, check=True)
    story = [
        (est_panel,
         f"The samples differ in their {num}/{den} isotope ratio"
         + (f" by {diff}" if diff else "")
         + (f", while the replicates of each agree within {spread}" if spread and "%" in spread
            else "") + ". " + est_caption
         + measured.replace(" Measured medians:", " Medians of the particles' ratios:")
         + _cut_sentence(s) + _bias_sentence(ctx, num, den, natural)),
        (_panel("ecdf", f"{num}/{den} distribution by sample", value=ratio, group_by="sample",
                filter=used, x_label=name, **_ratio_lines(natural, "x")),
         "The whole distribution of the ratio in each sample; curves shifted sideways mean "
         "the difference is shared by most particles, not a few."),
        (_ratio_signal(ctx, num, den, f"{num}/{den} against {den} signal, by sample", natural,
                       group_by="sample", filter=f"{num} > 0 and {den} > 0", **_cut_line(s, den)),
         f"Every particle's ratio against its {den} counts, by sample."
         + _band_sentence(den, natural, grouped=True) + _cut_line_sentence(s, den)
         + " The difference is in isotope signature when the medians stay apart from small to "
           "large particles, not only among small, noisy ones."
         + _spread_sentence(ctx, s, num, den, grouped=True)),
    ]
    three = _three_isotope(ctx, s, num, den, group_by="sample")
    if three:
        story.append(three)
    story.append((_histogram(ctx, "counts", den, f"{den} counts by sample", group_by="sample"),
                  "Samples with very different signal ranges have different counting noise, which "
                  "matters when comparing their ratios."))
    return story


def _limit_value(ctx: FigureContext, prefix: str, label: str) -> float | None:
    """The detection-limit value a panel draws for *label*, or ``None``."""
    found = _limit(FigureContext(limits=ctx.limits, smallest=ctx.smallest), prefix, label)
    try:
        return float(found["dl_value"]) if found else None
    except (KeyError, ValueError):
        return None


def _size_box(ctx: FigureContext, value: str, title: str, y_label: str, rule: str = "",
              log_y: bool = True) -> dict:
    """Box plot of *value* in small, medium and large particles."""
    return _panel("box", title, value=value, group_by="size", log_y=log_y, filter=rule,
                  y_label=y_label, show_other=False)


def _size_sentence(ctx: FigureContext, value: str, what: str, rule: str = "") -> str:
    """Measured medians by size class and whether they differ, adding a check."""
    if ctx.table is None:
        return ""
    rows = [r for r in ev.by_size(ctx.table, value, rule) if r[2] >= 5]
    if len(rows) < 2:
        return ""
    import warnings
    from scipy import stats
    v = ev._eval(ctx.table, value)
    samples = [v[m & np.isfinite(v) & (v > 0)] for _n, m in ev.size_classes(ctx.table, rule)]
    samples = [x for x in samples if x.size >= 5]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            p = float(stats.kruskal(*samples).pvalue) if len(samples) >= 2 else math.nan
        except ValueError:
            p = math.nan
    lo, hi = min(r[1] for r in rows), max(r[1] for r in rows)
    spread = hi / lo - 1 if lo > 0 else math.nan
    steady = not (p < 0.05 and spread > 0.10)
    ctx.checks.add(steady, f"{what} {'holds' if steady else 'changes'} across particle sizes "
                           f"(medians {', '.join(ev.fmt(r[1]) for r in rows)} from small to large, "
                           f"Kruskal-Wallis {ev.p_text(p)})")
    return (" Measured medians: " + "; ".join(f"{n} {ev.fmt(m)} ({k:,})" for n, m, k in rows) + ".")


def _size_caption(what: str) -> str:
    """Sentence explaining a size-class panel."""
    return (f"{what} in small, medium and large particles, each a third of the particles by total "
            "mass. A value that holds across the three is a property of the particles; one that "
            "changes with size points to a coating or core, or to minor elements falling below "
            "their detection limit in small particles.")


def _count(value: float) -> str:
    """A number of particles as it is read: ``1,440`` or ``28.7``, never ``1.44e+03``."""
    return f"{value:,.0f}" if value >= 100 else f"{value:.3g}"


def _coincidence_sentence(ctx: FigureContext, a: str, b: str) -> str:
    """Co-detections against chance coincidence of two particles, adding a check."""
    if ctx.table is None:
        return ""
    c = ev.coincidence(ctx.table, a, b)
    if c is None or c["observed"] == 0:
        return ""
    share = c["expected"] / c["observed"]
    ok = share <= ev.COINCIDENCE_SHARE
    expected = _count(c["expected"])
    ctx.checks.add(ok, f"{c['observed']:,} particles carry both {a} and {b}, against "
                       f"{expected} expected from two particles arriving together by chance"
                       + ("" if ok else
                          f", so up to {min(share, 1.0):.0%} of the pairings may be coincidences"))
    return (f" From the particle rate and event duration, chance coincidence of a {a} and a {b} "
            f"particle would give {expected} co-detections; {c['observed']:,} are seen.")


def _interference(s, ctx):
    parent, child = s.elements[0], s.elements[1]
    species = _detail(s, "Likely species", f"an ion of {parent}")
    ratio = _detail(s, "Median suspect/parent")
    spread = _detail(s, "Spread of the ratio")
    slope = _detail(s, "Slope on log axes")
    measured = ""
    if ctx.table is not None:
        r = ev.values(ctx.table, f"{child} / {parent}", f"{child} > 0 and {parent} > 0")
        n_parent = ev.values(ctx.table, parent).size
        if r.size >= 10:
            q1, med, q3 = np.percentile(r, [25, 50, 75])
            rcv = (q3 - q1) / (1.349 * med) if med > 0 else math.nan
            measured = (f" Measured: median {med:.3g}, interquartile range {q1:.3g}–{q3:.3g}, over "
                        f"{r.size:,} particles ({r.size / max(n_parent, 1):.0%} of the {parent} "
                        "particles).")
            ctx.checks.add(bool(rcv < 0.5), f"the {child}/{parent} share is "
                                            + ("fixed" if rcv < 0.5 else "variable")
                                            + f" (robust spread {rcv:.0%})"
                                            + (", as an interference gives" if rcv < 0.5 else
                                               ", more like a separate element"))
    return [
        (_panel("scatter", f"{child} against {parent}", x=parent, y=child, log_x=True,
                log_y=True, show_fit=True, marker_size=10),
         f"Every particle with {child} also carries {parent}, and the two rise together"
         + (f" with a slope of {slope} on log axes" if slope and slope != "n/a" else "")
         + f", as expected when the {child} signal is made from {parent} in the plasma."),
        (_panel("histogram", f"{child}/{parent} in each particle", value=f"{child} / {parent}",
                bins=40, x_label=f"{child}/{parent}"),
         f"The {child}/{parent} ratio of each particle stays near {ratio or 'one value'}"
         + (f" (spread {spread})" if spread else "")
         + "; a separate element would vary from particle to particle instead of keeping "
           "a fixed share." + measured),
        (_panel("histogram", f"{parent} with and without {child}", value=parent, log_x=True,
                bins=40, x_label=f"{parent} counts", **_with_without(parent, child)),
         f"{species} is a small fraction of {parent}, so it only clears the detection threshold "
         f"when there is a lot of {parent}: the particles with {child} should be those with the "
         f"largest {parent} signal."),
        (_histogram(ctx, "counts", child, f"{child} counts and detection limit"),
         f"The {child} counts against the detection limit (dashed line); in these "
         f"particles {child} is best read as {species}, not as a separate element."),
    ]


def _comparison(s, ctx):
    el = s.elements[0]
    fold = _detail(s, "Fold difference in median")
    tests = _test(ctx.groups)
    unit = _unit(ctx)
    name = _qname(unit)
    value = _amount(ctx, el)
    measured = ""
    if ctx.table is not None:
        groups = [(smp, v) for smp, v in ev.by_sample(ctx.table, value) if v.size >= 5]
        if len(groups) >= 2:
            groups.sort(key=lambda g: -np.median(g[1]))
            (hi_name, hi_v), (lo_name, lo_v) = groups[0], groups[-1]
            f, lo, hi = ev.fold_ci(hi_v, lo_v)
            measured = (f" Measured: median {np.median(hi_v):.3g} in {hi_name} against "
                        f"{np.median(lo_v):.3g} in {lo_name}, {f:.2f}× (95% CI "
                        f"{ev.fmt(lo)}–{ev.fmt(hi)}).")
            ctx.checks.add(bool(np.isfinite(lo) and lo > 1), f"{hi_name} against {lo_name}: "
                           + ("the fold difference stays above 1 across its 95% interval"
                              if np.isfinite(lo) and lo > 1 else "the 95% interval of the fold "
                              "difference reaches 1"))
            meds = ev.replicate_medians(ctx.table, value)
            p, method = ev.replicate_test(meds)
            if p is not None:
                ctx.checks.add(p < 0.05, f"{method}: {ev.p_text(p)}")
            else:
                ctx.checks.add(None, "samples not replicated, so the test counts particles")
            limit = _limit_value(ctx, unit, el)
            if limit:
                rule = f"{value} >= {limit:.6g}"
                above = [(smp, v) for smp, v in ev.by_sample(ctx.table, value, rule) if v.size >= 5]
                if len(above) >= 2:
                    d = {smp: v for smp, v in above}
                    if hi_name in d and lo_name in d:
                        f2 = float(np.median(d[hi_name]) / np.median(d[lo_name]))
                        ctx.checks.add(f2 > 1.05, f"above the common detection limit "
                                                  f"({limit:.3g}) the difference is {f2:.2f}×")
    story = [
        (_panel("box", f"{el} {name} by sample", value=value, group_by="sample",
                log_y=True, y_label=_amount_name(ctx, el), **_limit(ctx, unit, el), **tests),
         f"The median {el} per particle differs between the samples"
         + (f" by {fold}" if fold else "") + "." + _test_sentence(ctx.groups, name) + measured),
        (_histogram(ctx, unit, el, f"{el} {name} by sample", group_by="sample"),
         f"The full {el} distributions; a whole shift means the particles differ in size or "
         "composition, a change on one side only means one population was added or lost."),
        (_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                group_by="sample", y_label="Particles with it (%)", error="ci95", bar_values=True),
         f"How often {el} is detected at all in each sample; a sample can carry more "
         f"{el} per particle and still have fewer particles with it." + SHARE_NOTE),
        (_strip(ctx, el, f"Every {el} particle by sample"), _strip_caption(el)
         + " A shift carried by one colour points to one particle type changing."),
    ]
    return story


def _replicates(s, ctx):
    el = s.elements[0] if s.elements else ""
    if not el:
        return [
            (_panel("timeline", "Particles arriving over the run", time_mode="cumulative",
                     group_by="sample"),
             "The replicates collect particles at different rates; each line's slope is that "
             "replicate's particle rate."),
            (_panel("timeline", "Particle rate over the run", time_mode="rate", group_by="sample"),
             "A rate that changes during one run points to sample transport, such as a "
             "nebuliser slowly clogging."),
        ]
    unit = _unit(ctx)
    name = _qname(unit)
    measured = ""
    if ctx.table is not None:
        groups = [(smp, v) for smp, v in ev.by_sample(ctx.table, _amount(ctx, el)) if v.size >= 5]
        if len(groups) >= 2:
            meds = [np.median(v) for _s, v in groups]
            spread = max(meds) / min(meds) - 1 if min(meds) > 0 else math.nan
            measured = (" Measured medians: " + "; ".join(f"{smp} {np.median(v):.3g}"
                                                           for smp, v in groups)
                        + f", {spread:.0%} apart.")
            ctx.checks.add(bool(spread <= 0.15), f"replicate medians agree within {spread:.0%}"
                           if spread <= 0.15 else f"replicate medians differ by {spread:.0%}")
    return [
        (_panel("box", f"{el} {name} by replicate", value=_amount(ctx, el), group_by="sample",
                log_y=True, y_label=_amount_name(ctx, el), **_limit(ctx, unit, el)),
         f"{s.title}: the {el} {name} per particle in each replicate." + measured),
        (_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                group_by="sample", y_label="Particles with it (%)", error="ci95", bar_values=True),
         f"How often each replicate detects {el}; replicates of one sample should agree."
         + SHARE_NOTE),
        (_panel("timeline", "Particles arriving over the run", time_mode="cumulative",
                group_by="sample"),
         "Each line's slope is that replicate's particle rate; a different slope points to "
         "transport or dilution rather than to the particles."),
        (_histogram(ctx, unit, el, f"{el} {name} by replicate", group_by="sample"),
         "Replicates should share the shape of the distribution, not only its middle."),
        (_strip(ctx, el, f"Every {el} particle by replicate"), _strip_caption(el)
         + " Replicates should show the same mix of colours."),
    ]


def _signature(s, ctx):
    el = s.elements[0]
    measured = ""
    if ctx.table is not None:
        col = ev._eval(ctx.table, el)
        samples = ctx.table.column("sample")
        shares = [(smp, float(np.mean(col[samples == smp] > 0)), int(np.sum(samples == smp)))
                  for smp in ctx.table.samples()]
        shares = [x for x in shares if x[2]]
        if shares:
            measured = " Measured: " + "; ".join(f"{smp} {sh:.1%} of {n:,}" for smp, sh, n in shares) + "."
    story = [
        (_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                group_by="sample", y_label="Particles with it (%)", error="ci95", bar_values=True),
         f"{el} is found in a much larger share of one sample's particles; Fisher's exact "
         "test on these shares, with the replicates kept apart, made it stand out." + SHARE_NOTE
         + measured),
        (_panel("combinations", "Most common element combinations", top_n=10,
                group_by="sample"),
         f"The particle types in each sample, showing which combinations carry {el}."),
    ]
    unit = _unit(ctx)
    limit = _limit_value(ctx, unit, el)
    near = ""
    if ctx.table is not None and limit:
        share = ev.near_limit(ev.values(ctx.table, _amount(ctx, el)), limit)
        if share is not None:
            near = f" Measured: {share:.0%} of the {el} particles sit within twice the limit."
            ctx.checks.add(share < 0.5, f"{share:.0%} of {el} particles sit within twice the "
                                        "detection limit"
                                        + ("" if share < 0.5 else ", so a sample with smaller "
                                           f"{el} particles may simply detect fewer"))
    story.append((_histogram(ctx, unit, el, f"{el} {_qname(unit)} and detection limit"),
                  f"{el} particles against the detection limit (dashed line); if most "
                  "sit close to it, the sample with fewer may simply have smaller "
                  f"{el} particles that fall below it." + near))
    host = ctx.main
    if _can_check(ctx, host, el):
        story.append((_detect_box(ctx, host, el, f"Could {el} be seen in {host} particles?",
                                  group_by="sample"),
                      _detect_caption(host, el) + f" A sample whose {host} particles mostly sit "
                      f"below the line cannot show whether they carry {el}."))
    story.append((_panel("bar", f"Share with {el} by particle size", value=el, agg="detect_pct",
                         group_by="size", y_label="Particles with it (%)", error="ci95", bar_values=True),
                  _size_caption(f"How often {el} is detected") + SHARE_NOTE
                  + _share_size_sentence(ctx, el)))
    return story


def _share_size_sentence(ctx: FigureContext, el: str, rule: str = "") -> str:
    """Measured detected share by size class, adding a check on its trend."""
    if ctx.table is None:
        return ""
    rows = [r for r in ev.detected_share_by_size(ctx.table, el, rule) if r[2] >= 10]
    if len(rows) < 3:
        return ""
    rising = rows[-1][1] > 2 * max(rows[0][1], 1e-9) and rows[-1][1] - rows[0][1] > 0.05
    ctx.checks.add(not rising, f"{el} is detected in {', '.join(f'{r[1]:.0%}' for r in rows)} of "
                               "small, medium and large particles"
                               + (", so detection depends on particle size" if rising else ""))
    return (" Measured: " + "; ".join(f"{n} {sh:.0%} of {k:,}" for n, sh, k in rows) + ".")


def _stoichiometry(s, ctx):
    a, b = s.elements[0], s.elements[1]
    prefix = "moles" if "moles" in ctx.quantities else "counts"
    ratio = f"{_expr(prefix, a)} / {_expr(prefix, b)}"
    total = f"{_expr(prefix, a)} + {_expr(prefix, b)}"
    unit = "moles" if prefix == "moles" else "counts"
    value = _detail(s, "Ratio")
    simple = _detail(s, "Closest simple ratio")
    both = f"{a} > 0 and {b} > 0"
    measured = ""
    if ctx.table is not None:
        r = ev.values(ctx.table, ratio, both)
        if r.size >= 10:
            q1, med, q3 = np.percentile(r, [25, 50, 75])
            measured = (f" Measured: median {a}/{b} {med:.3g}, interquartile range "
                        f"{q1:.3g}–{q3:.3g}, over {r.size:,} particles.")
    story = [
        (_panel("scatter", f"{a} against {b} ({unit})", x=_expr(prefix, b), y=_expr(prefix, a),
                log_x=True, log_y=True, show_fit=True, marker_size=10),
         f"{a} and {b} keep a fixed ratio in every particle that carries both"
         + (f", {value}" if value else "") + "." + measured + _coincidence_sentence(ctx, a, b)),
        (_panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True, bins=60,
                filter=both, trim_pct=99.5, x_label=f"{a}/{b} ({unit})"),
         "The ratio of each particle; one narrow peak means a fixed composition, far narrower "
         "than if the two elements varied independently."),
        (_panel("scatter", "Ratio against particle amount", x=total, y=ratio, log_x=True,
                log_y=True, trend="median", x_label=f"{a} + {b} ({unit})", y_label=f"{a}/{b}",
                marker_size=10),
         "A flat running median means one compound from small to large particles"
         + (f", close to {simple}" if simple and simple.startswith(("1", "2", "3", "4"))
            else "") + "."),
        (_size_box(ctx, ratio, f"{a}/{b} by particle size", f"{a}/{b} ({unit})", both),
         _size_caption(f"The {a}/{b} ratio") + _size_sentence(ctx, ratio, f"the {a}/{b} ratio", both)),
        (_histogram(ctx, _unit(ctx), a),
         f"{a} particles against the detection limit (dashed line); ratios of particles "
         "close to it are the least precise."),
    ]
    return story


SAME_RATIO = 1.5
"""Largest factor between two samples' ratios for them to count as the same ratio."""


def _ratio_split(s, ctx):
    from results.insights.discovery import (
        RATIO_SPLIT_MIN_FOLD, ratio_split_panel, ratio_split_rules,
    )
    a, b, c = s.elements[0], s.elements[1], s.elements[2]
    ratio = f"{a} / {b}"
    both = f"{a} > 0 and {b} > 0"
    with_c, without_c = f"{both} and {c} > 0", f"{both} and {c} == 0"
    split = ratio_split_rules(c)
    first = shape = meaning = size = ""
    if ctx.table is not None:
        rw, rwo = ev.values(ctx.table, ratio, with_c), ev.values(ctx.table, ratio, without_c)
        if rw.size >= 5 and rwo.size >= 5:
            mw, mwo = float(np.median(rw)), float(np.median(rwo))
            fold = max(mw, mwo) / max(min(mw, mwo), 1e-12)
            pooled = float(np.mean(np.concatenate([rw, rwo])))
            nb_w, nb_wo = ev.values(ctx.table, b, with_c), ev.values(ctx.table, b, without_c)
            inside = []
            for r, nb, centre in ((rwo, nb_wo, mwo), (rw, nb_w, mw)):
                n = min(r.size, nb.size)
                sigma = np.sqrt(centre * (1 + centre) / np.maximum(nb[:n], 1.0))
                inside.append(float(np.mean(np.abs(r[:n] - centre) <= 2 * sigma)))
            first = (f" Measured: {ev.pct(inside[0])} of particles without {c} and "
                     f"{ev.pct(inside[1])} of those with it fall inside their own envelope; a "
                     f"single mean over all particles ({pooled:.3g}) sits between the two.")
            try:
                from scipy import stats as _st
                p = float(_st.mannwhitneyu(rw, rwo).pvalue)
            except ValueError:
                p = float("nan")
            shape = (f" Measured: median {a}/{b} {mwo:.3g} without {c} ({rwo.size:,} particles) "
                     f"against {mw:.3g} with it ({rw.size:,}), {fold:.2f}× apart, "
                     f"Mann–Whitney {ev.p_text(p)}.")
            ctx.checks.add(fold >= RATIO_SPLIT_MIN_FOLD,
                           f"the two populations' ratios differ {fold:.2f}×")
            rows = []
            for name, vals in ev.by_sample(ctx.table, ratio, with_c):
                other = dict(ev.by_sample(ctx.table, ratio, without_c)).get(name)
                if vals.size >= 5 and other is not None and other.size >= 5:
                    rows.append((name, float(np.median(other)), float(np.median(vals))))
            if len(rows) >= 2:
                splits = all((r_wo > r_w) == (mwo > mw)
                            and max(r_w, r_wo) / max(min(r_w, r_wo), 1e-12) >= RATIO_SPLIT_MIN_FOLD
                            for _n, r_wo, r_w in rows)
                agree = all(max(col) / max(min(col), 1e-12) <= SAME_RATIO
                            for col in ([r[1] for r in rows], [r[2] for r in rows]))
                listed = "; ".join(f"{n}: {r_wo:.3g} and {r_w:.3g}" for n, r_wo, r_w in rows)
                if splits and agree:
                    ctx.checks.add(True, f"every sample shows the same two ratios ({listed})")
                elif splits:
                    ctx.checks.add(False, "every sample splits the same way, but the two ratios "
                                          f"are not the same from sample to sample ({listed})")
                else:
                    ctx.checks.add(False, f"the split is not seen in every sample ({listed})")
            cw = ev.values(ctx.table, c, with_c)
            if cw.size >= 10 and cw.size == rw.size:
                rho, _pp, k = ev.spearman(cw, rw)
                if k >= 10 and np.isfinite(rho):
                    meaning = f" Measured: ρ = {rho:+.2f} over {k:,} particles."
            if nb_w.size >= 5 and nb_wo.size >= 5:
                bw, bwo = float(np.median(nb_w)), float(np.median(nb_wo))
                small = bw < 0.5 * bwo
                ctx.checks.add(not small, f"particles with {c} are not much smaller in {b} "
                               f"(median {_count(bw)} against {_count(bwo)} counts)")
                size = (f" Measured: median {b} {_count(bw)} counts with {c} against "
                        f"{_count(bwo)} without it.")
    shares = ""
    if ctx.table is not None:
        rows = [r for r in ev.detected_share_by_size(ctx.table, c, both) if r[2] >= 10]
        if rows:
            shares = (" Measured: " + "; ".join(f"{n} {ev.pct(v)}" for n, v, _k in rows) + ".")
    return [
        (_panel(**{**ratio_split_panel(a, b, c), "title": f"{a}/{b} against {b}, coloured by {c}"}),
         f"Each particle's {a}/{b} against its {b} signal. Grey particles carry no {c}; the "
         f"others are coloured by their {c} signal. Dashed lines are each population's ±2σ "
         f"counting-statistics envelope, σ = √(R(1 + R)/N), the spread counting alone gives "
         f"around its ratio; two populations in separate envelopes are not counting noise."
         + first),
        (_panel("histogram", f"{a}/{b} with and without {c}", value=ratio, log_x=True, bins=50,
                filter=both, x_label=f"{a}/{b} (counts)", hist_percent=True, **split),
         f"The ratio of the particles with and without {c}, each as a share of its own "
         "population so the smaller one stays visible. Two separate peaks point to two "
         "phases; one broad peak shifting with the third element would point to one phase of "
         "variable composition." + shape),
        (_panel("scatter", f"{a}/{b} against {c}", x=c, y=ratio, log_x=True, log_y=True,
                filter=with_c, show_fit=True, x_label=f"{c} (counts)", y_label=f"{a}/{b}",
                color=split["rules"][0]["color"], marker_size=12),
         f"Within the particles carrying {c}, {a}/{b} against the {c} signal. A ratio that "
         f"moves with {c} points to {c} substituting in one structure; a flat ratio points to "
         f"a separate {c}-bearing phase." + meaning),
        (_panel("bar", f"Particles carrying {c}, by size", value=c, agg="detect_pct",
                group_by="size", filter=both, y_label=f"With {c} (%)", error="ci95", bar_values=True,
                xtick_rotation=15),
         _size_caption(f"How often particles carrying {a} and {b} also carry {c}") + SHARE_NOTE
         + shares),
        (_panel("histogram", f"{b} signal with and without {c}", value=b, log_x=True, bins=40,
                filter=both, x_label=f"{b} (counts)", hist_percent=True, **split),
         f"The {b} signal of the two populations. If the particles with {c} sit much lower, "
         f"{c} may go undetected in small particles of the same phase, which would mix them "
         f"into the grey population." + size
         + " Ratios are in counts; calibrate both elements to moles before comparing them with "
           "a formula."),
    ]


def _where_most(ctx: FigureContext, x: str, y: str, rule: str, x_label: str, y_label: str):
    """The panel showing where most particles of an X–Y cloud sit, with its caption.

    With :data:`DENSE_PARTICLES` particles per group or more, a map of
    particles per cell. With fewer, most cells would hold one or two
    particles and the map would only repeat the scatter, so the particles
    are drawn with the contours of their density instead.
    """
    n = None
    if ctx.table is not None:
        try:
            n = int(ev.mask(ctx.table, rule).sum()) / max(1, ctx.groups)
        except Exception:
            n = None
    if n is not None and n < DENSE_PARTICLES:
        return (_panel("contour", "Where most particles sit", x=x, y=y, log_x=True, log_y=True,
                       filter=rule, show_points=True, levels=5, points_size=9,
                       points_alpha=0.7, points_zorder=4,
                       x_label=x_label, y_label=y_label),
                "The same particles with the contours of their density: each contour encloses "
                "a denser part of the cloud, so the innermost one is where most particles sit, "
                "rather than the few at the edges.")
    return (_panel("hexbin", "Where most particles sit", x=x, y=y, log_x=True, log_y=True,
                   x_label=x_label, y_label=y_label),
            "The same particles as a density map, showing where most of them sit rather than "
            "the few at the edges.")


CIRCULAR_SHARE = 0.5
"""Share of a particle's amount two elements hold above which size classes slice along them."""


def _size_is_circular(ctx: FigureContext, xa: str, xb: str, rule: str) -> float | None:
    """Median share of the particle amount that two plotted elements make up, when it is large.

    Size classes are thirds of each particle's total amount. When the two
    elements of a plot are most of that amount, a size class is a band across
    the plot itself, and a fit inside the band is flat whatever the relation.

    Returns:
        The median share when it reaches :data:`CIRCULAR_SHARE`, else ``None``.
    """
    try:
        total, _unit_name = ev.amount(ctx.table)
        part = ev._eval(ctx.table, xa) + ev._eval(ctx.table, xb)
        m = ev.mask(ctx.table, rule) & np.isfinite(total) & (total > 0) & np.isfinite(part)
        if int(m.sum()) < 10:
            return None
        share = float(np.median(np.clip(part[m] / total[m], 0, 1)))
    except Exception:
        return None
    return share if share >= CIRCULAR_SHARE else None


def _correlation(s, ctx):
    a, b = s.elements[0], s.elements[1]
    rho = _detail(s, "Rank correlation (ρ)")
    rho_p = _detail(s, "Proportionality (ρp)")
    xa, xb = _amount(ctx, a), _amount(ctx, b)
    name = _qname(_unit(ctx))
    both = f"{a} > 0 and {b} > 0"
    ratio = f"{xa} / {xb}"
    holds = slope = peaks_text = spread = ""
    lines = "median"
    marks = {}
    peaks = None
    if ctx.table is not None:
        bounds = ev.slope_bounds(ctx.table, xb, xa, both)
        if bounds is not None:
            lo, hi, _n = bounds
            slope = (f" Measured: the slope lies between {lo:.2f} and {hi:.2f}; "
                     + ("1 lies inside, so a fixed ratio is not ruled out." if lo <= 1 <= hi else
                        f"1 lies outside, so {a} is not simply proportional to {b}."))
        peaks = ev.ratio_peaks(ev.values(ctx.table, ratio, both))
        if peaks is not None:
            r1, r2 = peaks["centres"]
            if peaks["two"]:
                lines = f"{r1:.4g}, {r2:.4g}"
                marks = {"vlines": lines}
                peaks_text = (f" Measured: two populations, near {a}/{b} = {r1:.3g} "
                              f"({ev.pct(peaks['shares'][0])} of the particles) and {r2:.3g} "
                              f"({ev.pct(peaks['shares'][1])}), marked by the dashed lines.")
                ctx.checks.add(False, f"the {a}/{b} ratio falls into two populations, near "
                                      f"{r1:.3g} and {r2:.3g}, so one line and one ρ over all "
                                      "particles describe neither")
            else:
                med = float(np.median(ev.values(ctx.table, ratio, both)))
                peaks_text = f" Measured: one population, median {a}/{b} = {med:.3g}."
                ctx.checks.add(True, f"the {a}/{b} ratio forms one population (median {med:.3g})")
        if bounds is not None and peaks is not None and peaks["two"]:
            slope = (f" Measured over all particles: the slope lies between {bounds[0]:.2f} and "
                     f"{bounds[1]:.2f}, but with two populations in the cloud that range "
                     "describes neither; each population follows its own dashed line.")
        circular = _size_is_circular(ctx, xa, xb, both)
        rows = [r for r in ev.size_holds(ctx.table, xb, xa, both) if r[2] >= 10]
        if rows:
            holds = (" Measured within each size class: "
                     + "; ".join(f"{n} ρ = {r:+.2f} ({k:,})" for n, r, k in rows) + ".")
            if circular is not None:
                holds += (f" {a} and {b} make up most of each particle's amount (median "
                          f"{circular:.0%}), so a size class is a band across this plot and its "
                          "fit is flattened by the slicing itself; it is not used as a check.")
            else:
                same_sign = all(np.sign(r) == np.sign(rows[0][1]) and abs(r) >= 0.2
                                for _n, r, _k in rows)
                ctx.checks.add(same_sign, "the correlation "
                               + ("holds within every size class" if same_sign else
                                  "weakens within size classes, so particle size may drive it"))
        if "counts" in ctx.quantities and not (peaks and peaks["two"]):
            st = ev.ratio_spread(ctx.table, a, b, both)
            if st is not None:
                spread = (f" Measured: {ev.pct(st['inside'])} of particles inside the band, "
                          f"excess scatter {st['excess']:.2f}: "
                          + ("the spread is what counting alone gives, so the particles share "
                             "one composition." if st["excess"] <= ev.EXCESS_OK else
                             "more than counting alone gives, so the composition itself "
                             "varies from particle to particle."))
    two = bool(peaks and peaks["two"])
    story = [
        (_panel("scatter", f"{a} against {b}", x=xb, y=xa, log_x=True, log_y=True,
                fit_range=True, ratio_lines=lines, ratio_lines_label=f"{a}/{b}",
                x_label=_amount_name(ctx, b), y_label=_amount_name(ctx, a), marker_size=10,
                alpha=0.5),
         f"In particles carrying both, {a} rises with {b}" + (f" (ρ = {rho})" if rho else "")
         + ". The shaded wedge is the range the slope can lie in: its flatter edge is the "
           f"usual fit, which noise in {b} flattens, and its steeper edge the fit the other "
           "way round. Each dashed line is a fixed ratio, a slope of 1 on these axes."
         + slope + _coincidence_sentence(ctx, a, b)),
        (_panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True,
                bins=60, filter=both, x_label=f"{a}/{b} ({name})", **marks),
         "The ratio of each particle. One peak means one kind of particle; two peaks mean two "
         "kinds, each with its own ratio, which a single fit line would run between."
         + peaks_text),
    ]
    if spread:
        story.append((
            _panel("scatter", f"{a}/{b} against {b} signal", x=b, y=f"{a} / {b}", log_x=True,
                   log_y=True, trend="median", poisson_band=2.0, filter=both,
                   x_label=f"{b} counts", y_label=f"{a}/{b} (counts)", marker_size=10),
            f"Each particle's {a}/{b} in counts against its {b} counts. The shaded band is the "
            "mean ratio ± 2σ that counting statistics alone would give, so it narrows as the "
            "signal grows; the solid line is the running median." + spread))
    story += [
        _where_most(ctx, xb, xa, both, _amount_name(ctx, b), _amount_name(ctx, a)),
        (_panel("scatter", f"{a} against {b} by particle size", x=xb, y=xa, log_x=True,
                log_y=True, group_by="size", show_other=False, show_fit=True, fit_band=False,
                filter=both, x_label=_amount_name(ctx, b), y_label=_amount_name(ctx, a),
                marker_size=10),
         "The same particles split into small, medium and large thirds by total mass, each "
         "with its own fit; elements that only grow together with particle size correlate "
         "overall but not within a size class." + holds),
        (_panel("scatter", "Ratio against particle size", x=f"{xa} + {xb}", y=ratio,
                log_x=True, log_y=True, trend="median", x_label=f"{a} + {b} {name}",
                y_label=f"{a}/{b}", marker_size=10),
         "A flat ratio means a fixed composition; a ratio that changes with size means the "
         "two only grow together"
         + (f" (proportionality ρp = {rho_p})" if rho_p and rho_p != "n/a" else "") + "."),
    ]
    if two:
        story.insert(2, story.pop(-1))
    return story


MATRIX_ELEMENTS = 8
"""Most elements shown in a matrix about two elements: the two and their closest company."""


def _company(ctx: FigureContext, focus, limit: int = MATRIX_ELEMENTS) -> str:
    """The elements most often found in the particles carrying the *focus* elements.

    A matrix of every measured isotope is unreadable and mostly empty; the
    ones that matter to a finding about two elements are those two and what
    travels with them.

    Returns:
        A comma-separated list for a panel's ``isotopes``, the focus elements
        first, or an empty string (every isotope) when the particles are
        unknown or there are no more than *limit* isotopes anyway.
    """
    table = ctx.table
    labels = list(getattr(table, "labels", None) or ())
    if table is None or len(labels) <= limit:
        return ""
    focus = [f for f in focus if f in labels]
    if not focus:
        return ""
    held = np.zeros(len(table), dtype=bool)
    for f in focus:
        held |= ev._eval(table, f) > 0
    counts = {lab: int(np.sum(held & (ev._eval(table, lab) > 0))) for lab in labels
              if lab not in focus}
    ranked = sorted((lab for lab, n in counts.items() if n > 0), key=lambda lab: -counts[lab])
    return ", ".join(focus + ranked[:max(0, limit - len(focus))])


def _cooccurrence(s, ctx):
    rare, common = s.elements[0], s.elements[1]
    together = s.explain_key == "cooccurrence_with"
    company = _company(ctx, (rare, common))
    measured = ""
    if ctx.table is not None:
        ind = ev.independence(ctx.table, rare, common)
        if ind is not None:
            measured = (f" Measured: {ind['observed']:,} particles carry both, against "
                        f"{_count(ind['expected'])} if the two were found independently.")
    story = [
        (_panel("combinations", f"Combinations in particles with {rare}", top_n=10,
                filter=f"{rare} > 0"),
         f"{rare} and {common} "
         + ("share particles far more often than chance would give."
            if together else "are found in separate particles far more often than chance "
                             "would give.") + measured
         + (_coincidence_sentence(ctx, rare, common) if together else "")),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="conditional",
                **({"isotopes": company} if company else {})),
         "Each cell is the share of the row element's particles that also carry the column "
         "element; only presence counts here, not amount."
         + (f" Shown for {rare}, {common} and the elements most often found with them."
            if company else "")),
        (_panel("histogram", f"{rare} with and without {common}", value=_amount(ctx, rare),
                log_x=True, bins=40, x_label=_amount_name(ctx, rare), hist_percent=True,
                **_with_without(rare, common)),
         f"{rare} particles with and without {common}, by {_qname(_unit(ctx))}, each as a "
         "share of its own group."),
        (_panel("bar", f"{rare} particles carrying {common}, by size", value=common,
                agg="detect_pct", group_by="size", filter=f"{rare} > 0",
                y_label=f"With {common} (%)", error="ci95", bar_values=True),
         _size_caption(f"How often {rare} particles carry {common}") + SHARE_NOTE
         + _share_size_sentence(ctx, common, f"{rare} > 0")),
        (_histogram(ctx, _unit(ctx), rare,
                    f"{rare} {_qname(_unit(ctx))} and detection limit"),
         f"If {rare} is only detectable in large particles, it will seem to avoid elements "
         "found in small ones; the dashed line shows how close it sits to its threshold."),
    ]
    if not together and _can_check(ctx, common, rare):
        story.insert(4, (_detect_box(ctx, common, rare, f"Could {rare} be seen in {common} particles?",
                                     **_with_without(common, rare)),
                         _detect_caption(common, rare) + f" If the {common} particles without "
                         f"{rare} sit mostly below the line, the two may not truly avoid each other."))
    if not together:
        by_size = next(i for i, (p, _c) in enumerate(story) if p.get("agg") == "detect_pct")
        story.insert(1, story.pop(by_size))
    return story


def _rare(s, ctx):
    el = s.elements[0]
    measured = ""
    if ctx.table is not None:
        t = ev._eval(ctx.table, "time")
        has = ev._eval(ctx.table, el) > 0
        samples = ctx.table.column("replicate")
        spans = []
        for r in dict.fromkeys(samples.tolist()):
            m = samples == r
            tt = t[m & np.isfinite(t)]
            ht = t[m & has & np.isfinite(t)]
            if tt.size >= 2 and ht.size >= 3 and np.ptp(tt) > 0:
                spans.append(float(np.ptp(ht) / np.ptp(tt)))
        n = int(has.sum())
        if n:
            measured = f" Measured: {n:,} particles carry {el}."
        if spans:
            spread = float(np.median(spans))
            ctx.checks.add(spread >= 0.5, f"{el} particles arrive over {spread:.0%} of the run"
                           + ("" if spread >= 0.5 else ", bunched in time, which points to "
                              "one contamination event"))
    story = [
        (_panel("combinations", f"Particles with {el}", top_n=10, filter=f"{el} > 0"),
         f"Only a few particles carry {el}; these are the element combinations they come in."
         + measured),
        (_panel("strip", f"{el} in each particle", value=_amount(ctx, el), log_y=True,
                y_label=_amount_name(ctx, el), **_limit(ctx, _unit(ctx), el)),
         f"Each dot is one {el} particle; the dashed line is the detection limit."),
        (_panel("timeline", f"When {el} particles arrive", time_mode="signal",
                value=_amount(ctx, el), log_y=True, filter=f"{el} > 0"),
         "Particles arriving together in time point to one contamination event; spread "
         "evenly, they belong to the sample."),
    ]
    if len(s.elements) > 1:
        other = s.elements[1]
        story.insert(2, (_panel("scatter", f"{el} against {other}", x=_amount(ctx, other),
                                y=_amount(ctx, el), log_x=True, log_y=True, filter=f"{el} > 0",
                                x_label=_amount_name(ctx, other), y_label=_amount_name(ctx, el)),
                         f"{el} with {s.elements[1]}, the element it usually comes with."
                         + _coincidence_sentence(ctx, el, other)))
    return story


def _distribution(s, ctx):
    el = s.elements[0]
    story = []
    lead = {
        "quality": f"The {el} distribution piles up at its lowest values, so part of the "
                   "population likely continues below the detection limit (dashed line).",
        "distribution_two": f"The {el} signal splits into two populations of particles.",
    }.get(s.explain_key, f"{el} varies widely from particle to particle.")
    unit = _unit(ctx)
    limit = _limit_value(ctx, unit, el)
    if ctx.table is not None:
        v = ev.values(ctx.table, _amount(ctx, el))
        if v.size >= 10:
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            lead += (f" Measured: median {med:.3g}, interquartile range {q1:.3g}–{q3:.3g} "
                     f"{_qname(unit).split(' ')[-1].strip('()')}, {v.size:,} particles.")
            share = ev.near_limit(v, limit)
            if share is not None:
                ctx.checks.add(share < 0.25, f"{share:.0%} of particles sit within twice the "
                                             "detection limit"
                                             + ("" if share < 0.25 else ", so the distribution is "
                                                "cut by the limit"))
    story.append((_histogram(ctx, unit, el), lead))
    story.append((_panel("ecdf", f"{el} cumulative distribution", value=_amount(ctx, el),
                         log_x=True, x_label=_amount_name(ctx, el), **_limit(ctx, unit, el)),
                  "The cumulative curve shows what share of particles sits close to the "
                  "detection limit; a curve that starts steeply at the threshold means "
                  "the population continues below it."))
    if ctx.multi_sample:
        story.append((_histogram(ctx, unit, el, f"{el} {_qname(unit)} by sample",
                                 group_by="sample"),
                      "Each sample on its own, to see whether they share the same shape."))
    return story


def _size_trend(s, ctx):
    figure_panels = s.config.get("panels") or []
    y = figure_panels[0].get("y", "") if figure_panels else ""
    el = y.split(":", 1)[-1].split("/")[0].strip() if y else ""
    story = [
        (_panel("scatter", f"{el} share against particle mass", x="total", y=y, log_x=True,
                trend="median", filter="n_elements >= 2", x_label="Particle mass (fg)",
                y_label=f"{el} mass fraction", marker_size=10),
         f"The {el} share of each multi-element particle changes with the particle's mass."),
        (_size_box(ctx, y, f"{el} mass fraction by particle size", f"{el} mass fraction",
                   "n_elements >= 2", log_y=False),
         _size_caption(f"The {el} share")
         + (_size_sentence(ctx, y, f"the {el} share", "n_elements >= 2") if y else "")),
        (_panel("histogram", "Particle mass", value="total", log_x=True, bins=40,
                x_label="Particle mass (fg)"),
         "The range of particle masses; a share falling with size fits a coating or shell, "
         "a rising share fits a core."),
    ]
    if el:
        story.append((_histogram(ctx, "mass" if "mass" in ctx.quantities else "counts", el),
                      "Small particles near the detection limit (dashed line) lose their minor "
                      "elements first, which can mimic the same trend."))
    return story


def _time(s, ctx):
    lead = ""
    for p in s.config.get("panels") or []:
        lead = p.get("value") or lead
    measured = ""
    if ctx.table is not None:
        t = ev._eval(ctx.table, "time")
        reps = ctx.table.column("replicate")
        changes = []
        for r in dict.fromkeys(reps.tolist()):
            tt = np.sort(t[(reps == r) & np.isfinite(t)])
            if tt.size >= 30 and np.ptp(tt) > 0:
                edges = np.linspace(tt[0], tt[-1], 4)
                first = np.sum(tt < edges[1]) / (edges[1] - edges[0])
                last = np.sum(tt >= edges[2]) / (edges[3] - edges[2])
                if first > 0:
                    changes.append((r, round(last / first - 1, 2) + 0.0))
        if changes:
            measured = (" Measured change in rate from the first to the last third of the run: "
                        + "; ".join(f"{r} {c:+.0%}" for r, c in changes) + ".")
            worst = max(abs(c) for _r, c in changes)
            ctx.checks.add(worst <= 0.2, f"particle rate changes by up to {worst:.0%} during a run")
    story = [
        (_panel("timeline", "Particle rate over the run", time_mode="rate"),
         "The particle arrival rate or signal changes during the run instead of staying "
         "steady." + measured),
        (_panel("timeline", "Particles arriving over the run", time_mode="cumulative"),
         "Particles counted as they arrive; a straight line would mean a steady rate, so a "
         "bend shows when it changed."),
    ]
    if lead:
        story += [
            (_panel("timeline", f"{lead} signal over the run", time_mode="signal", value=lead,
                    log_y=True),
             "A steady trend in several elements points to instrument sensitivity; in one "
             "element only, to the particles themselves."),
            (_histogram(ctx, "counts", lead, f"{lead} counts and detection limit"),
             "A falling signal pushes more particles below the detection limit (dashed "
             "line), which also lowers the rate."),
        ]
    return story


def _composition(s, ctx):
    els = list(s.elements)
    picked = {"isotopes": ", ".join(els)} if els else {}
    measured = ""
    if ctx.table is not None and len(ctx.table) and ctx.table.labels:
        labels = list(ctx.table.labels)
        detected = np.column_stack([ev._eval(ctx.table, lab) > 0 for lab in labels])
        rows, counts = np.unique(detected, axis=0, return_counts=True)
        n = len(ctx.table)
        order = np.argsort(-counts)[:3]
        keys = [(" + ".join(lab for lab, on in zip(labels, rows[i]) if on), int(counts[i]))
                for i in order]
        if keys:
            measured = (" Measured: the three most common are "
                        + "; ".join(f"{k or 'none'} {v / n:.0%}" for k, v in keys) + ".")
    story = [
        (_panel("combinations", "Most common element combinations", top_n=10),
         "The particle types that dominate, each defined by the set of elements detected in "
         "it." + measured),
        (_panel("composition", "Average composition", other_pct=1.0, **picked),
         "The average make-up of the particles; elements holding under 1% are stacked "
         "together as Others."),
        (_panel("combinations", "Element combinations by particle size", top_n=6,
                group_by="size", show_other=False),
         _size_caption("The particle types")),
    ]
    if len(els) == 3:
        refs = _minerals_for(els) if "moles" in ctx.quantities else []
        if refs:
            story.append((_panel("ternary", f"{els[0]}–{els[1]}–{els[2]} (moles)",
                                 a=f"moles:{els[0]}", b=f"moles:{els[1]}", c=f"moles:{els[2]}",
                                 tern_refs=", ".join(refs + ["upper crust"]), legend_loc="ternary"),
                          "One tight cluster means one composition; points along a line between "
                          "corners mean mixing. Open symbols mark ideal mineral formulas and the "
                          "upper crust, for orientation: real minerals vary."))
        else:
            story.append((_panel("ternary", f"{els[0]}–{els[1]}–{els[2]}", a=els[0], b=els[1],
                                 c=els[2], legend_loc="ternary"),
                          "One tight cluster means one composition; points along a line between "
                          "corners mean mixing."))
    else:
        story.append((_panel("cooccurrence", "How often elements share particles",
                             cooc_mode="joint", **picked),
                      "Elements that often share particles belong to the same particle type."))
    if "mass" in ctx.quantities:
        story.append((_panel("pie", "Main element and its companions", pie_mode="sunburst",
                             top_n=6, sun_outer=4),
                      "Inside: each particle's main element by mass; outside: what it comes with. "
                      "Which elements are detected depends on each element's detection limit, so "
                      "small particles may appear to lack their minor elements."))
    else:
        story.append((_panel("pie", "Particle types", pie_mode="combinations", top_n=8),
                      "Which elements are detected depends on each element's detection limit, so "
                      "small particles may appear to lack their minor elements."))
    return story


def _network(s, ctx):
    els = ", ".join(s.elements)
    quantity = {"data_type": "Element Mass (fg)"} if _unit(ctx) == "mass" else {}
    return [
        (_panel("network", "Correlated elements", isotopes=els, net_r_min=0.5, log_values=True,
                net_method="spearman", **quantity),
         "These elements form one connected group; each link is a significant correlation "
         "with |ρ| of at least 0.5."),
        (_panel("corr_matrix", "Correlation matrix", isotopes=els, corr_method="spearman",
                log_values=True, **quantity),
         "The rank correlation of every pair"
         + (", on element mass." if quantity else ", on counts.")),
        (_panel("cooccurrence", "How often they share particles", isotopes=els),
         "Elements that also share particles likely come from one source."),
        (_panel("combinations", "Most common combinations", top_n=10, isotopes=els),
         "The particle types these elements form. Links are pairwise, so two elements in the "
         "group need not correlate directly."),
    ]


LINKED = 0.5
"""Rank correlation from which two elements are called linked."""


def _matrix_elements(s) -> list[str]:
    """The elements of a correlation-matrix finding, from the finding itself or its details."""
    if len(s.elements) >= 2:
        return list(s.elements)
    listed = _detail(s, "Elements")
    return [e.strip() for e in listed.split(",") if e.strip()]


def _pair_correlations(ctx: FigureContext, els, quantity: str) -> list[tuple[str, str, float, int]]:
    """Rank correlation of every pair of *els* among the particles carrying both.

    Returns:
        ``(a, b, rho, n)`` for each pair with ten particles or more, strongest first.
    """
    rows = []
    for i, a in enumerate(els):
        for b in els[i + 1:]:
            x, y = ev._eval(ctx.table, _expr(quantity, a)), ev._eval(ctx.table, _expr(quantity, b))
            m = (x > 0) & (y > 0)
            rho, _p, n = ev.spearman(np.log10(x[m]), np.log10(y[m])) if m.sum() else (math.nan, 0, 0)
            if n >= 10 and math.isfinite(rho):
                rows.append((a, b, float(rho), int(n)))
    return sorted(rows, key=lambda r: -abs(r[2]))


def _matrix(s, ctx):
    els = _matrix_elements(s)
    if len(els) < 2:
        return _composition(s, ctx)
    listed = ", ".join(els)
    unit = _unit(ctx)
    quantity = {"data_type": "Element Mass (fg)"} if unit == "mass" else {}
    measured = ""
    if ctx.table is not None:
        try:
            pairs = _pair_correlations(ctx, els, unit)
        except Exception:
            pairs = []
        if pairs:
            linked = [p for p in pairs if abs(p[2]) >= LINKED]
            (a, b, rho, n), (wa, wb, wrho, wn) = pairs[0], pairs[-1]
            measured = (f" Measured over all particles: {len(linked)} of {len(pairs)} pairs "
                        f"reach |ρ| ≥ {LINKED:g}; the strongest is {a} with {b} (ρ = {rho:+.2f}, "
                        f"{n:,} particles) and the weakest {wa} with {wb} (ρ = {wrho:+.2f}, "
                        f"{wn:,}).")
            ctx.checks.add(len(linked) == len(pairs),
                           (f"every pair of the {len(els)} elements is linked (|ρ| ≥ {LINKED:g})"
                            if len(linked) == len(pairs) else
                            f"{len(pairs) - len(linked)} of {len(pairs)} pairs stay below "
                            f"|ρ| = {LINKED:g}, so the elements do not all move as one block"))
            few = [p for p in pairs if p[3] < 100]
            ctx.checks.add(not few,
                           ("every correlation rests on 100 particles or more" if not few else
                            "; ".join(f"{x} with {y} rests on {k} particles" for x, y, _r, k in few[:3])
                            + ", so those correlations are loosely known"))
    return [
        (_panel("corr_matrix", "Correlation matrix", isotopes=listed, corr_method="spearman",
                log_values=True, **quantity),
         "The rank correlation of every pair, among the particles carrying both"
         + (", on element mass." if quantity else ", on counts.")
         + " A block of high values is a set of elements that rise and fall together."
         + measured),
        (_panel("network", "Which elements are linked", isotopes=listed, net_r_min=LINKED,
                log_values=True, net_method="spearman", **quantity),
         f"The same correlations as links: a line joins two elements whose |ρ| reaches {LINKED:g}, "
         "thicker for a stronger link, and a node grows with the element's summed amount."),
        (_panel("cooccurrence", "How often they share particles", isotopes=listed),
         "The share of all particles carrying both elements of a pair. A high correlation "
         "between two elements that rarely share particles rests on few particles."),
        (_panel("composition", "Average composition", isotopes=listed, other_pct=1.0, **quantity),
         "The average make-up of the particles, counting only these elements."),
        (_panel("combinations", "Most common combinations", top_n=10, isotopes=listed),
         "The particle types these elements form, each defined by which of them are detected."),
    ]


def _outlier(s, ctx):
    els = list(s.elements) or [str(s.config.get("highlight_element", ""))]
    el = els[0]
    unit = _unit(ctx)
    measured = ""
    if ctx.table is not None:
        v = ev.values(ctx.table, _amount(ctx, el))
        if v.size >= 20:
            lv = np.log10(v)
            q1, q3 = np.percentile(lv, [25, 75])
            far = int(np.sum(lv > q3 + 3 * (q3 - q1)))
            measured = (f" Measured: {far:,} of {v.size:,} particles lie more than three "
                        "interquartile ranges above the upper quartile on log values.")
    story = [
        (_panel("strip", f"{el} in each particle", value=_amount(ctx, el), log_y=True,
                y_label=_amount_name(ctx, el), **_limit(ctx, unit, el)),
         f"A few particles carry far more {el} than the rest." + measured),
        (_histogram(ctx, unit, el),
         "On log values, these particles sit far above the upper quartile of the "
         "distribution."),
    ]
    if len(els) > 1:
        story.append((_panel("scatter", f"{els[0]} against {els[1]}", x=_amount(ctx, els[1]),
                             y=_amount(ctx, els[0]), log_x=True, log_y=True,
                             x_label=_amount_name(ctx, els[1]),
                             y_label=_amount_name(ctx, els[0]), marker_size=10),
                      "Being extreme in two elements at once is unlikely to be chance."))
    story.append((_panel("timeline", f"When large {el} particles arrive", time_mode="signal",
                         value=_amount(ctx, el), log_y=True),
                  "Two particles arriving together can look like one large particle."))
    return story


def _type_definition(s) -> dict:
    """The particle-type definition carried by a types card."""
    for panel in (s.config or {}).get("panels") or []:
        if (panel.get("types") or {}).get("types"):
            return panel["types"]
    return {}


def _type_panels(s, definition, title):
    """The card's own PCA panel, retitled for the story."""
    base = dict(((s.config or {}).get("panels") or [{}])[0])
    for k in ("id", "rect"):
        base.pop(k, None)
    base["title"] = title
    return base


def _types_overview(s, ctx):
    definition = _type_definition(s)
    if not definition:
        return []
    basis = "mass" if definition.get("prefix") == "mass" else "counts"
    els = ", ".join(f"{definition['prefix']}:{e}" for e in definition["elements"])
    common = {"group_by": "types", "types": definition, "show_other": False}
    return [
        (_type_panels(s, definition, "Compositions on two principal components"),
         "Each dot is a particle with two or more elements, placed by its composition as centred "
         "log-ratios, so its size does not matter; arrows show which elements pull particles "
         "apart. Colours are the types that passed every check."),
        (_panel("composition", "Average make-up of each type", isotopes=els, horizontal=True,
                **common),
         f"The average share of each element in a particle of each type, by {basis}."),
        (_panel("strip", "Particle size by type, coloured by sample", value="total",
                strip_horizontal=True, strip_color="sample", log_y=True, strip_summary="median_iqr",
                marker_size=8, alpha=0.55, filter="n_elements >= 2", **common),
         f"The total {basis} of every typed particle, coloured by the sample it came from: which "
         "samples hold each type, and whether its particles are large or small."),
        (_panel("pie", "Share of each type", pie_mode="groups", pie_labels="name_pct",
                filter="n_elements >= 2", **common),
         "How the typed particles split between the types; particles too far from every type "
         "are left out."),
    ]


def _particle_type(s, ctx):
    definition = _type_definition(s)
    name = _detail(s, "Type")
    if not definition or not name:
        return []
    prefix = definition.get("prefix") or "mass"
    basis = "mass" if prefix == "mass" else "counts"
    main = s.elements[0]
    only = {"types": definition, "type_only": name}
    entry = next((t for t in definition["types"] if t.get("name") == name), {})
    present = entry.get("present") or {}
    inside = [e for e in definition["elements"] if present.get(e, 1.0) >= 0.1]
    els = ", ".join(f"{prefix}:{e}" for e in definition["elements"])
    story = [
        (_type_panels(s, definition, f"{name} among all particle types"),
         f"The {name} particles (coloured) against the other types (grey) on the first two "
         "principal components of composition."),
        (_panel("composition", "Average make-up of each type", isotopes=els, horizontal=True,
                group_by="types", types=definition, show_other=False),
         f"The make-up of {name} next to the other types, by {basis}."),
        (_panel("corr_matrix", f"Which elements move together in {name}",
                isotopes=", ".join(f"{prefix}:{e}" for e in inside),
                corr_method="spearman", log_values=True, **only),
         f"Rank correlations inside this type only. Elements that rise together here belong to "
         "the same phase; inside a type, correlations are no longer driven by mixing different "
         "kinds of particles."),
    ]
    if ctx.multi_sample:
        tests = _test(ctx.groups)
        story.append((_panel("box", f"{main} per particle of {name}, by sample",
                             value=f"{prefix}:{main}", group_by="sample", log_y=True, **only,
                             **tests),
                      f"How much {main} a {name} particle holds in each sample."
                      + _test_sentence(ctx.groups, f"{main} {basis}")))
    else:
        story.append((_panel("histogram", f"{main} per particle of {name}", value=f"{prefix}:{main}",
                             log_x=True, bins=40, **only),
                      f"How much {main} a {name} particle holds."))
    partial = sorted((e for e in inside if e != main and 0.1 <= present.get(e, 1.0) < 0.95),
                     key=lambda e: present[e])
    minor = next((m for m in partial if _can_check(ctx, main, m)), None)
    if minor:
        story.append((_detect_box(ctx, main, minor, f"Could {minor} be seen in {name}?",
                                  **_with_without(main, minor), **only),
                      f"Only {100 * present[minor]:.0f}% of {name} particles show {minor}. "
                      + _detect_caption(main, minor)
                      + f" If the {name} particles without {minor} sit below the line, they are "
                        f"probably the same type with {minor} too small to detect."))
    if len(s.elements) >= 3:
        a, b, c = s.elements[:3]
        molar = "moles" in ctx.quantities
        refs = _minerals_for([a, b, c]) if molar else []
        corner = (lambda e: f"moles:{e}") if molar else (lambda e: e)
        story.append((_panel("ternary", f"{a}–{b}–{c} in {name}" + (" (moles)" if molar else ""),
                             a=corner(a), b=corner(b), c=corner(c),
                             tern_refs=", ".join(refs + ["upper crust"]) if refs else "", **only),
                      f"The {a}–{b}–{c} make-up of each {name} particle"
                      + ("; diamonds mark ideal mineral formulas and the upper crust, for "
                         "orientation." if refs else ".")))
    return story


DESIGNS = {
    "interference": _interference,
    "isotope": _isotope_pair,
    "isotope_abundance": _isotope_pair,
    "isotope_two": _isotope_pair,
    "isotope_track": _isotope_track,
    "isotope_groups": _isotope_groups,
    "comparison": _comparison,
    "replicate_flag": _replicates,
    "replicate_agree": _replicates,
    "signature": _signature,
    "stoichiometry": _stoichiometry,
    "ratio_split": _ratio_split,
    "correlation": _correlation,
    "cooccurrence_with": _cooccurrence,
    "cooccurrence_avoid": _cooccurrence,
    "rare": _rare,
    "quality": _distribution,
    "distribution_two": _distribution,
    "distribution_spread": _distribution,
    "size": _size_trend,
    "time_rate": _time,
    "time_signal": _time,
    "composition": _composition,
    "network": _network,
    "outlier": _outlier,
    "types_overview": _types_overview,
    "particle_type": _particle_type,
}
"""Figure stories keyed by a finding's explain key.

Each design returns ``(panel, caption)`` pairs in story order: the pattern,
the evidence, the meaning, then the limits. The captions become the
figure's legend.
"""

ISOTOPE_DESIGNS = {_isotope_pair, _isotope_track, _isotope_groups}

BETWEEN_DESIGNS = frozenset({_comparison, _replicates, _signature, _isotope_groups, _time})
"""Stories whose finding is a difference between groups, laid out one row per view."""

MAX_PANELS = 6
"""Most panels a story uses, a to f."""


CAPTION_SIZE = 9.5
"""Font size of the legend under a story, in points."""

CAPTION_MARGIN = 0.3
"""Width a text panel keeps clear on its two sides together, in inches."""


def caption_height(caption: str, width: float) -> float:
    """Height in inches the legend needs under a figure *width* inches wide.

    The legend is wrapped exactly as the text panel will draw it, with the
    figure's default font, so the room set aside is the room it fills.
    """
    from results.figure_builder.core import richtext
    from results.figure_builder.core.spec import FIGURE_DEFAULTS
    from results.figure_builder.core.styles import font_stack
    fonts, _math = font_stack(FIGURE_DEFAULTS.get("font_family"))
    return 0.4 + richtext.height_in(caption, width - CAPTION_MARGIN, CAPTION_SIZE, fonts,
                                    isotopes=True)


def story_layout(n: int, caption: str = "") -> tuple[list[list[float]], list[float], float, float]:
    """Place *n* panels above a caption sized to its text.

    A last row holding fewer panels than the others is centred under them.

    Args:
        n: Number of panels, at most :data:`MAX_PANELS`.
        caption: The legend text, used to size the caption area.

    Returns:
        ``(panel_rects, caption_rect, width, height)``: rectangles in figure
        fractions with the origin top-left, and the figure size in inches.
    """
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    width = 5.4 * cols
    plot_height = 3.9 * rows
    height = plot_height + caption_height(caption, width)
    top = plot_height / height
    rects = []
    for i in range(n):
        row = i // cols
        in_row = min(cols, n - row * cols)
        offset = (cols - in_row) / (2 * cols)
        rects.append([offset + (i % cols) / cols, row * top / rows, 1.0 / cols, top / rows])
    return rects, [0.0, top, 1.0, 1.0 - top], width, height


def caption_text(captions: list[str]) -> str:
    """Write the panels' part of the legend: one paragraph per panel, its letter in bold."""
    from results.figure_builder.core.spec import panel_letter
    return "\n".join(f"**({panel_letter(i, 'a')})** {c}" for i, c in enumerate(captions))


def conclusion(s) -> str:
    """The legend's opening paragraph: the finding's title in bold, then what was found."""
    title = (s.title or "").strip().rstrip(".")
    found = " ".join((getattr(s, "reasoning", "") or "").split())
    head = f"**{title}.**" if title else ""
    return f"{head} {found}".strip()


def legend_text(s, panels: str, notes: list[str], checks) -> str:
    """Put the legend together: the conclusion, the checks, then the panels.

    Args:
        s: The finding.
        panels: The panels' paragraphs from :func:`caption_text` or
            :func:`rows_caption`.
        notes: Sentences that apply to the whole figure, such as the
            comparison between groups and the detection limits.
        checks: The figure's :class:`~results.insights.evidence.Checks`.

    Returns:
        The legend in the markup of
        :mod:`results.figure_builder.core.richtext`.
    """
    parts = [conclusion(s), checks.block() if checks is not None else "", panels]
    notes = [n.strip() for n in notes if n and n.strip()]
    if notes:
        parts.append("**Notes.** " + " ".join(notes))
    return "\n".join(p for p in parts if p)


OVERLAY_KINDS = frozenset({"histogram", "ecdf", "box", "violin", "bar", "strip", "timeline",
                           "ridgeline", "line"})
"""Panels that show several groups at once, one colour each, and stay readable."""

MAX_SPLIT_GROUPS = 3
"""Most groups that get a panel each; more groups are shown in colour only."""

MAX_GROUP_ROWS = 4
"""Most rows of a figure comparing groups, each row one view of the finding."""


def group_names(ctx: FigureContext) -> list[str]:
    """The groups the figure compares: the samples of its table, when there are two or more."""
    if ctx.table is None or not len(ctx.table):
        return []
    names = [str(n) for n in ctx.table.samples()]
    return names if len(names) >= 2 else []


def _for_group(panel: dict, name: str) -> dict:
    """A copy of *panel* showing only the particles of group *name*."""
    import json
    rule = f"sample == {json.dumps(name)}"
    old = (panel.get("filter") or "").strip()
    out = dict(panel)
    out["filter"] = f"({old}) and {rule}" if old else rule
    out["title"] = f"{panel.get('title') or ''} — {name}".strip(" —")
    return out


XY_KINDS = frozenset({"scatter", "hexbin", "density", "contour"})
"""Split panels whose X and Y ranges are made the same across the groups."""


def _axis_range(values: np.ndarray, log: bool) -> tuple[float, float] | None:
    """A padded range covering *values*, in log or linear terms."""
    v = values[np.isfinite(values)]
    if log:
        v = v[v > 0]
    if v.size < 2:
        return None
    if log:
        lo, hi = np.log10(v.min()), np.log10(v.max())
        pad = max(hi - lo, 0.1) * 0.05
        return 10 ** (lo - pad), 10 ** (hi + pad)
    lo, hi = float(v.min()), float(v.max())
    pad = max(hi - lo, abs(hi) * 0.01, 1e-12) * 0.05
    return lo - pad, hi + pad


RANGE_AXES = {"histogram": (("value", "x"),), "ecdf": (("value", "x"),),
              "box": (("value", "y"),), "violin": (("value", "y"),)}
"""For panels of one value, which setting holds it and the axis it is drawn along."""


def same_ranges(ctx: FigureContext, panels: list[dict]) -> list[dict]:
    """Give the per-group copies of a panel the same axis ranges.

    Each copy would otherwise fit its own group, and two panels side by side
    on different scales cannot be compared by eye. The range covers every
    group's particles that the panels draw. X–Y panels share both axes;
    histograms, cumulative curves, boxes and violins share the axis their
    value runs along.
    """
    if ctx.table is None or not panels:
        return panels
    first = panels[0]
    kind = first.get("kind")
    if kind in XY_KINDS:
        axes = (("x", "x"), ("y", "y"))
    elif kind in RANGE_AXES:
        axes = RANGE_AXES[kind]
    else:
        return panels
    out = [dict(p) for p in panels]
    for key, axis in axes:
        expr = first.get(key)
        if not expr or "," in str(expr):
            continue
        try:
            v = ev._eval(ctx.table, expr)
            m = np.zeros(len(ctx.table), dtype=bool)
            for p in panels:
                m |= ev.mask(ctx.table, p.get("filter") or "")
        except Exception:
            continue
        log = bool(first.get(f"log_{axis}"))
        values = v[m]
        if kind not in XY_KINDS:
            values = values[np.isfinite(values) & (values > 0)]
            if values.size >= 20:
                lo, hi = np.percentile(values, [0.1, 99.9])
                values = values[(values >= lo) & (values <= hi)]
        found = _axis_range(values, log)
        if found is None:
            continue
        for p in out:
            p[f"{axis}_min"], p[f"{axis}_max"] = f"{found[0]:.6g}", f"{found[1]:.6g}"
    return out


MANY_GROUPS = 4
"""Groups beyond which overlaid histograms are drawn as ridges instead."""


def _ridges(panel: dict) -> dict:
    """A histogram panel redrawn as one ridge per group.

    Ten filled histograms on one axis hide each other; a ridgeline gives
    every group its own baseline on a shared value axis.
    """
    out = {k: v for k, v in panel.items() if k not in ("bins", "hist_percent")}
    out.update(kind="ridgeline", group_by="sample", mark_stats="median", overlap=0.5)
    return out


def by_groups(story: list, names: list[str], ctx: FigureContext | None = None
              ) -> list[tuple[list[dict], str, str]]:
    """Lay a story out to compare groups.

    A panel that can show the groups together (histograms, cumulative curves,
    box, bar and dot plots, timelines) colours them, one colour per group. A
    panel that cannot without becoming unreadable (scatters, density maps,
    ternaries, pies, combinations, matrices), or one already split another
    way (with and without an element, by size), is drawn once per group,
    side by side. A panel already comparing samples is kept as it is. With
    too many groups for side-by-side panels, a panel split another way is
    drawn once for all groups together, never recoloured by group, since
    its own split is what it is there to show; and overlaid histograms
    become ridges (see :func:`_ridges`).

    Args:
        story: ``(panel, caption)`` pairs.
        names: The groups, at least two.

    Returns:
        Rows of ``(panels, caption, kind)``; *kind* is ``"wide"`` for one
        panel across the row and ``"split"`` for one panel per group.
    """
    rows = []
    split_ok = len(names) <= MAX_SPLIT_GROUPS
    many = len(names) > MANY_GROUPS
    for panel, caption in story:
        kind = panel.get("kind")
        grouping = panel.get("group_by") or "none"
        if kind == "histogram" and grouping in ("none", "sample") and many:
            rows.append(([_ridges(panel)],
                         caption.replace(" Each colour is one group.", "")
                         + " Each ridge is one group's distribution, scaled to its own peak, "
                           "with a tick at its median, so many groups stay apart.", "wide"))
        elif kind == "histogram" and grouping == "sample":
            rows.append(([dict(panel, hist_percent=True)],
                         caption + " Each group is drawn as a share of its own particles, so "
                                   "groups of different size compare by shape.", "wide"))
        elif grouping == "sample":
            rows.append(([panel], caption, "wide"))
        elif kind == "histogram" and grouping == "none":
            rows.append(([dict(panel, group_by="sample", hist_percent=True)],
                         caption + " Each colour is one group, drawn as a share of its own "
                                   "particles so groups of different size compare by shape.",
                         "wide"))
        elif kind in OVERLAY_KINDS and grouping == "none":
            rows.append(([dict(panel, group_by="sample")], caption + " Each colour is one group.",
                          "wide"))
        elif split_ok:
            copies = [_for_group(panel, n) for n in names]
            if ctx is not None:
                copies = same_ranges(ctx, copies)
            shared = (" The panels share their axis ranges." if kind in XY_KINDS
                      or kind in RANGE_AXES else "")
            rows.append((copies, caption + shared, "split"))
        elif grouping == "none" and (kind in OVERLAY_KINDS or kind == "combinations"):
            rows.append(([dict(panel, group_by="sample")], caption + " Each colour is one group.",
                          "wide"))
        else:
            rows.append(([panel], caption + " All groups together.", "wide"))
    return rows[:MAX_GROUP_ROWS]


GROUP_ROW_VIEWS = 3
"""Most views on one group's row when the groups are laid out in rows."""


def arrange(rows, names: list[str], between: bool):
    """Choose how a grouped figure is laid out, from what the finding is about.

    A finding that is a difference between groups keeps one row per view with
    the groups side by side (1 2 / 1 2), so each row compares the same view.
    A finding about a pattern inside the material, shown in two or more
    split views, gets one row per group (1 1 1 / 2 2 2): each group's story
    reads along its row and every view lines up down its column. Panels
    overlaying the groups in colour stay across the top.

    Args:
        rows: Rows from :func:`by_groups`.
        names: The groups.
        between: Whether the finding is a difference between groups.

    Returns:
        ``(rows, mode)``: the rows to draw, each ``(panels, caption, kind)``
        where *kind* is ``"wide"``, ``"split"`` (views in rows) or
        ``"group"`` (one group's views), and *mode* ``"views"`` or ``"groups"``.
    """
    splits = [r for r in rows if r[2] == "split"]
    if between or len(splits) < 2:
        return rows, "views"
    wide = [r for r in rows if r[2] == "wide"]
    views = splits[:GROUP_ROW_VIEWS]
    room = max(0, MAX_GROUP_ROWS - len(names))
    out = wide[:room]
    for g, name in enumerate(names):
        out.append(([panels[g] for panels, _c, _k in views], name, "group"))
    return out, "groups"


PAIR_GROUPS = 4
"""Most groups for which two full-width panels are set side by side."""


def _lines(rows, n_groups: int) -> list[list[int]]:
    """Which rows share a line of the page, as lists of row indices.

    Two panels that each span the figure are set side by side while there
    are few enough groups for each to stay readable at half the width;
    this keeps a story of four such panels to two lines instead of four.
    With more groups, only panels that do not draw the groups apart, such
    as a matrix or a network of all particles, are paired. A row holding
    one panel per group keeps a line of its own.
    """
    def pairs(i: int) -> bool:
        panels, _caption, kind = rows[i]
        if kind != "wide":
            return False
        return n_groups <= PAIR_GROUPS or (panels[0].get("group_by") or "none") != "sample"

    lines: list[list[int]] = []
    for i in range(len(rows)):
        if pairs(i) and lines and len(lines[-1]) == 1 and pairs(lines[-1][0]):
            lines[-1].append(i)
        else:
            lines.append([i])
    return lines


TALL_GROUPS = 6
"""Groups beyond which a panel giving each group a row of its own gets a taller line."""

TALL_KINDS = frozenset({"strip", "ridgeline", "estimate"})
"""Panels that give every group its own row."""


def _line_height(rows, members, n_groups: int) -> float:
    """Height in inches of one line of the page."""
    tall = any(rows[i][0][0].get("kind") in TALL_KINDS
               and (rows[i][0][0].get("group_by") or "none") == "sample" for i in members)
    if tall and n_groups > TALL_GROUPS:
        return 3.9 * min(2.0, 1.0 + (n_groups - TALL_GROUPS) * 0.12)
    return 3.9


def rows_layout(rows, n_groups: int, caption: str = ""):
    """Place grouped rows above the legend.

    A row with one panel per group shares its line equally between them. A
    panel spanning the figure takes a whole line, or half of one beside the
    next such panel (see :func:`_lines`).

    Returns:
        ``(panel_rects, caption_rect, width, height)`` as :func:`story_layout`.
    """
    cells = [len(panels) for panels, _c, kind in rows if kind != "wide"]
    cols = max(2, min(max(cells) if cells else n_groups, max(MAX_SPLIT_GROUPS, GROUP_ROW_VIEWS)))
    width = 5.4 * cols
    lines = _lines(rows, n_groups)
    heights = [_line_height(rows, members, n_groups) for members in lines]
    plot_height = sum(heights)
    height = plot_height + caption_height(caption, width)
    top = plot_height / height
    rects = []
    y = 0.0
    for members, inches in zip(lines, heights):
        row_h = inches / height
        if len(members) == 2:
            rects.extend([k * 0.5, y, 0.5, row_h] for k in range(2))
        else:
            panels, _caption, kind = rows[members[0]]
            if kind == "wide":
                rects.append([0.0, y, 1.0, row_h])
            else:
                w = 1.0 / len(panels)
                rects.extend([k * w, y, w, row_h] for k in range(len(panels)))
        y += row_h
    return rects, [0.0, top, 1.0, 1.0 - top], width, height


def rows_caption(rows, names: list[str], views=None) -> str:
    """The panels' part of a grouped figure's legend, naming the panel of each group.

    Args:
        rows: The rows drawn.
        names: The groups.
        views: For a figure laid out one row per group, the split views in
            order, as ``(panels, caption, kind)``; each gets one paragraph
            listing its panel in every group.

    Returns:
        One paragraph per view, its panel letters in bold.
    """
    from results.figure_builder.core.spec import panel_letter
    parts = []
    i = 0
    if views is not None:
        for panels, caption, kind in rows:
            if kind == "wide":
                parts.append(f"**({panel_letter(i, 'a')})** {caption}")
                i += 1
        first_group_row = i
        per_row = len(views)
        for v, (_panels, caption, _kind) in enumerate(views):
            letters = [panel_letter(first_group_row + g * per_row + v, 'a') for g in range(len(names))]
            which = ", ".join(f"({x}) {n}" for x, n in zip(letters, names))
            parts.append(f"**({', '.join(letters)})** {caption} One panel per group: {which}.")
        parts.append("Each row is one group: " + "; ".join(
            f"{n} {panel_letter(first_group_row + g * per_row, 'a')}–"
            f"{panel_letter(first_group_row + g * per_row + per_row - 1, 'a')}"
            for g, n in enumerate(names)) + ".")
        return "\n".join(parts)
    for panels, caption, kind in rows:
        if kind == "wide":
            parts.append(f"**({panel_letter(i, 'a')})** {caption}")
            i += 1
            continue
        letters = [panel_letter(i + k, 'a') for k in range(len(panels))]
        which = ", ".join(f"({x}) {n}" for x, n in zip(letters, names))
        parts.append(f"**({letters[0]}–{letters[-1]})** {caption} One panel per group: {which}.")
        i += len(panels)
    return "\n".join(parts)


def _group_values(ctx: FigureContext, expr: str, rule: str, names: list[str]):
    """``(group, values)`` of *expr* among the particles passing *rule*, per group."""
    v = ev._eval(ctx.table, expr)
    m = ev.mask(ctx.table, rule) & np.isfinite(v) & (v > 0)
    col = ctx.table.column("sample")
    return [(n, v[m & (col == n)]) for n in names]


def _medians_between(ctx: FigureContext, expr: str, rule: str, what: str, names: list[str],
                     tolerance: float = 0.10, finding: bool = False) -> str:
    """Compare a value's median between groups, adding a check; return the sentence.

    Args:
        finding: Whether a difference between the groups is what the figure
            reports. The check then passes when the groups differ, instead
            of when they agree.
    """
    import warnings
    from scipy import stats
    groups = [(n, v) for n, v in _group_values(ctx, expr, rule, names) if v.size >= 5]
    if len(groups) < 2:
        return ""
    meds = [(n, float(np.median(v)), v.size) for n, v in groups]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            p = float(stats.kruskal(*[v for _n, v in groups]).pvalue)
        except ValueError:
            p = math.nan
    lo, hi = min(m for _n, m, _k in meds), max(m for _n, m, _k in meds)
    gap = hi / lo - 1 if lo > 0 else math.nan
    same = not (p < 0.05 and gap > tolerance)
    numbers = (f"({', '.join(f'{n} {m:.3g}' for n, m, _k in meds)}; Kruskal-Wallis "
               f"{ev.p_text(p)})")
    if finding:
        ctx.checks.add(not same, f"{what} "
                       + ("is alike in every group, so the particles' medians do not show the "
                          "difference" if same else "differs between groups, as the finding says")
                       + f" {numbers}")
    else:
        ctx.checks.add(same, f"{what} {'is alike in every group' if same else 'differs between groups'} "
                             f"{numbers}")
    return (f"Between groups, median {what}: "
            + "; ".join(f"{n} {m:.3g} ({k:,} particles)" for n, m, k in meds)
            + (f", {gap:.0%} apart" if math.isfinite(gap) else "") + ".")


def _correlation_between(ctx: FigureContext, a: str, b: str, names: list[str]) -> str:
    """Rank correlation of two elements in each group, adding a check; return the sentence."""
    xa, xb = _amount(ctx, a), _amount(ctx, b)
    rule = f"{a} > 0 and {b} > 0"
    xs = dict(_group_values(ctx, xb, rule, names))
    col = ctx.table.column("sample")
    va, vb = ev._eval(ctx.table, xa), ev._eval(ctx.table, xb)
    m = ev.mask(ctx.table, rule) & (va > 0) & (vb > 0)
    rows = []
    for n in names:
        g = m & (col == n)
        rho, _p, k = ev.spearman(np.log10(vb[g]), np.log10(va[g])) if g.sum() else (math.nan, 0, 0)
        if math.isfinite(rho):
            rows.append((n, rho, k))
    if len(rows) < 2:
        return ""
    holds = all(np.sign(r) == np.sign(rows[0][1]) and abs(r) >= 0.2 for _n, r, _k in rows)
    ctx.checks.add(holds, f"the correlation {'holds in every group' if holds else 'differs between groups'} "
                          f"({', '.join(f'{n} ρ = {r:+.2f}' for n, r, _k in rows)})")
    return ("Between groups: " + "; ".join(f"{n} ρ = {r:+.2f} ({k:,} particles)" for n, r, k in rows)
            + ".")


def between_groups(s, ctx: FigureContext, design, names: list[str]) -> str:
    """The legend sentence comparing the finding between groups, with its check."""
    if not names or ctx.table is None or not s.elements:
        return ""
    els = list(s.elements)
    try:
        if design is _correlation and len(els) >= 2:
            return _correlation_between(ctx, els[0], els[1], names)
        if design is _stoichiometry and len(els) >= 2:
            prefix = "moles" if "moles" in ctx.quantities else "counts"
            ratio = f"{_expr(prefix, els[0])} / {_expr(prefix, els[1])}"
            return _medians_between(ctx, ratio, f"{els[0]} > 0 and {els[1]} > 0",
                                    f"{els[0]}/{els[1]} ratio", names)
        if design is _interference and len(els) >= 2:
            return _medians_between(ctx, f"{els[1]} / {els[0]}", f"{els[1]} > 0 and {els[0]} > 0",
                                    f"{els[1]}/{els[0]} share", names, tolerance=0.2)
        if design in ISOTOPE_DESIGNS and len(els) >= 2:
            return _medians_between(ctx, _ratio(ctx, els[0], els[1]), _used(s, els[0], els[1]),
                                    f"{els[0]}/{els[1]} ratio", names, tolerance=0.01,
                                    finding=design is _isotope_groups)
        if design is _cooccurrence and len(els) >= 2:
            col = ctx.table.column("sample")
            rare, common = ev._eval(ctx.table, els[0]) > 0, ev._eval(ctx.table, els[1]) > 0
            rows = [(n, float(np.mean(common[rare & (col == n)])), int((rare & (col == n)).sum()))
                    for n in names if (rare & (col == n)).sum() >= 10]
            if len(rows) < 2:
                return ""
            spread = max(r for _n, r, _k in rows) - min(r for _n, r, _k in rows)
            ctx.checks.add(spread <= 0.15, f"{els[0]} particles carry {els[1]} "
                                           + ", ".join(f"{n} {r:.0%}" for n, r, _k in rows))
            return ("Between groups, share of " + els[0] + " particles carrying " + els[1] + ": "
                    + "; ".join(f"{n} {r:.0%} of {k:,}" for n, r, k in rows) + ".")
        if design in (_distribution, _outlier, _rare, _signature, _size_trend):
            return _medians_between(ctx, _amount(ctx, els[0]), "", f"{els[0]} per particle", names)
    except Exception:
        return ""
    return ""


def figure_for(s, ctx: FigureContext) -> dict | None:
    """Build the figure that tells a finding's story, panels a to f with a legend.

    The panels follow the finding's story in order: the pattern, the
    evidence, the meaning, then the limits. A caption panel under them
    opens with the conclusion, the finding's title and what was found,
    lists the checks the figure ran, each passed, failed or undecided, and
    then says what each panel shows, with the finding's own numbers (see
    :func:`legend_text`). When the figure's particles fall into two or
    more groups, every view compares them (see :func:`by_groups`) and the
    legend says whether the finding holds in each group.

    Args:
        s: The finding (:class:`~results.insights.engine.Suggestion`).
        ctx: What the data offers the figure.

    Returns:
        A full Figure Builder spec, or ``None`` when the finding has no
        design or lacks the elements its design needs.
    """
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec

    key = s.explain_key or s.category
    design = DESIGNS.get(key) or DESIGNS.get(s.category)
    if design is None:
        return None
    ctx.checks = ev.Checks()
    if design is _correlation and len(s.elements) < 2:
        design = _matrix
    elif design not in (_composition, _time, _size_trend, _network, _matrix) and not s.elements:
        return None
    try:
        if design in ISOTOPE_DESIGNS:
            from results.figure_builder.core.isotopes import natural_ratio
            story = design(s, ctx, natural_ratio(s.elements[0], s.elements[1]))
        else:
            story = design(s, ctx)
    except (IndexError, KeyError):
        return None
    story = [(panel, caption) for panel, caption in story if panel][:MAX_PANELS]
    if not story:
        return None
    names = group_names(ctx) if design not in (_types_overview, _particle_type) else []
    if names:
        rows = by_groups(story, names, ctx)
        views = [r for r in rows if r[2] == "split"][:GROUP_ROW_VIEWS]
        rows, mode = arrange(rows, names, design in BETWEEN_DESIGNS)
        body = rows_caption(rows, names, views if mode == "groups" else None)
        notes = [between_groups(s, ctx, design, names)]
        flat = [panel for panels, _c, _k in rows for panel in panels]
    else:
        body = caption_text([c for _p, c in story])
        notes = []
        flat = [panel for panel, _c in story]
    notes.append(limits_sentence(ctx))
    legend = legend_text(s, body, notes, ctx.checks)
    if names:
        rects, caption_rect, width, height = rows_layout(rows, len(names), legend)
    else:
        rects, caption_rect, width, height = story_layout(len(story), legend)
    spec = default_spec()
    spec["figure"].update({"width": width, "height": height, "panel_letters": True})
    spec["data_type"] = ((s.config or {}).get("data_type") or "Counts"
                         if design in (_types_overview, _particle_type) else "Counts")
    panels = [make_panel(rect=list(rects[i]), **panel) for i, panel in enumerate(flat)]
    panels.append(make_panel(rect=list(caption_rect), kind="text", caption=True,
                             text=legend,
                             text_size=CAPTION_SIZE, panel_bg="#ffffff"))
    spec["panels"] = panels
    return normalise_spec(spec)


def context_from(particles: list[dict], labels, limits: dict | None = None,
                 multi_sample: bool = False, groups: int | None = None, table=None,
                 mass_bias: dict | None = None) -> FigureContext:
    """Work out what a figure can show from the particles it will draw.

    Args:
        particles: The particles of the finding's samples.
        labels: The isotopes the finding is about.
        limits: ``{label: {"counts" | "mass" | "d": {sample: value}}}``, the
            calibrated detection limits from
            :func:`results.insights.panel.detection_limits`.
        multi_sample: Whether more than one sample is involved.
        groups: How many samples or replicate groups are compared; defaults
            to two when *multi_sample* is set and one otherwise.
        table: The particle table the figure will draw from (see
            :func:`results.insights.evidence.table_from`); the legend's
            measured numbers and checks are left out without it.
        mass_bias: The exponential-law reference from an Isotopic Ratio node,
            when one is set up.

    Returns:
        The :class:`FigureContext`.
    """
    keys = {"elements": "counts", "element_mass_fg": "mass", "element_diameter_nm": "d",
            "element_moles_fmol": "moles"}
    quantities = set()
    smallest: dict = {}
    wanted = set(labels or ())
    for p in particles:
        for key, prefix in keys.items():
            values = p.get(key)
            if not values:
                continue
            quantities.add(prefix)
            for label in wanted:
                v = values.get(label)
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                if v > 0 and (smallest.get((prefix, label)) is None or v < smallest[(prefix, label)]):
                    smallest[(prefix, label)] = v
    seen_count: dict = {}
    for p in particles:
        for label, v in (p.get("elements") or {}).items():
            try:
                if float(v) > 0:
                    seen_count[label] = seen_count.get(label, 0) + 1
            except (TypeError, ValueError):
                continue
    main = max(seen_count, key=seen_count.get) if seen_count else ""
    present = {label for label, n in seen_count.items() if n >= 10}
    flat = {(prefix, label): dict(per_sample)
            for label, by_prefix in (limits or {}).items()
            for prefix, per_sample in (by_prefix or {}).items() if per_sample}
    if groups is None:
        groups = 2 if multi_sample else 1
    return FigureContext(quantities or {"counts"}, flat, smallest, multi_sample, groups, main=main,
                         present=present, table=table, mass_bias=mass_bias)
