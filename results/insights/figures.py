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
:mod:`results.insights.evidence`, and closes with a line of checks, each
passed or failed. Legends sit below their plot and reference lines are named
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
    values = list((ctx.limits.get((prefix, label)) or {}).values())
    if values:
        ctx.used.add((prefix, label))
        lo, hi = min(values), max(values)
        name = LIMIT_NAMES.get(prefix, "Detection limit")
        if hi <= lo * LIMIT_SPREAD:
            return {"dl_value": f"{sum(values) / len(values):.4g}", "dl_label": name}
        return {"dl_value": f"{hi:.4g}", "dl_label": f"{name} (highest sample)"}
    value = ctx.smallest.get((prefix, label))
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
            values = list((ctx.limits.get((prefix, label)) or {}).values())
            if not values:
                fallback = True
                continue
            lo, hi = min(values), max(values)
            unit = LIMIT_UNITS[prefix]
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
    name = QUANTITY_NAMES[prefix]
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
    return f"{label} {QUANTITY_NAMES[_unit(ctx)]}"


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
                  x_label=f"{el} {QUANTITY_NAMES[prefix]}")


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
    panel = _panel("scatter", "Three-isotope plot", x=_ratio(ctx, p7, p6), y=_ratio(ctx, p8, p6),
                   filter=rule, iso_refs="all", x_label=_ratio_name(ctx, p7, p6),
                   y_label=_ratio_name(ctx, p8, p6), marker_size=10, alpha=0.6, **extra)
    caption = ("Each particle's ²⁰⁸Pb/²⁰⁶Pb against its ²⁰⁷Pb/²⁰⁶Pb, the standard plot for "
               "tracing lead to its source. Open symbols are reference sources (average crust "
               "after Stacey and Kramers 1975, Broken Hill ore, and any added under Reference "
               "values); particles falling on a line between two sources are mixtures of them. "
               "Add local sources, such as a smelter's ore, under Reference values.")
    if ctx.table is not None:
        x = ev.values(ctx.table, _ratio(ctx, p7, p6), rule)
        y = ev.values(ctx.table, _ratio(ctx, p8, p6), rule)
        if x.size >= 10:
            caption += (f" Measured: median ²⁰⁷Pb/²⁰⁶Pb {np.median(x):.4g}, ²⁰⁸Pb/²⁰⁶Pb "
                        f"{np.median(y):.4g}, over {x.size:,} particles carrying all three isotopes.")
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
    three = _three_isotope(ctx, s, num, den)
    if three:
        story.append(three)
    story.append((_histogram(ctx, "counts", den, f"{den} counts and detection limit"),
                  f"{den} counts against the detection limit (dashed line): the closer most "
                  "particles sit to it, the wider their ratios scatter."))
    if ctx.multi_sample:
        story.append((_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                             filter=used, y_label=name, **_ratio_lines(natural, "y"),
                             **_test(ctx.groups, log_values=False)),
                      f"The same ratio in each sample; a sample far from the others should be "
                      "looked at before the samples are pooled."
                      + _test_sentence(ctx.groups, "ratios", log_values=False)))
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
                    f"{other} {QUANTITY_NAMES[_unit(ctx)]} and detection limit"),
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
    story = [
        (_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample", filter=used,
                y_label=name, **_ratio_lines(natural, "y"),
                **_test(ctx.groups, log_values=False)),
         f"The samples differ in their {num}/{den} isotope ratio"
         + (f" by {diff}" if diff else "")
         + (f", while the replicates of each agree within {spread}" if spread and "%" in spread
            else "") + "." + _test_sentence(ctx.groups, "ratios", log_values=False)
         + measured + _cut_sentence(s) + _bias_sentence(ctx, num, den, natural)),
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


def _coincidence_sentence(ctx: FigureContext, a: str, b: str) -> str:
    """Co-detections against chance coincidence of two particles, adding a check."""
    if ctx.table is None:
        return ""
    c = ev.coincidence(ctx.table, a, b)
    if c is None or c["observed"] == 0:
        return ""
    share = c["expected"] / c["observed"]
    ok = share <= ev.COINCIDENCE_SHARE
    ctx.checks.add(ok, f"{c['observed']:,} particles carry both {a} and {b}, against "
                       f"{c['expected']:.3g} expected from two particles arriving together by chance"
                       + ("" if ok else ", so many pairings may be coincidences"))
    return (f" From the particle rate and event duration, chance coincidence of a {a} and a {b} "
            f"particle would give {c['expected']:.3g} co-detections; {c['observed']:,} are seen.")


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
    name = QUANTITY_NAMES[unit]
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
                group_by="sample", y_label="Particles with it (%)", error="none"),
         f"How often {el} is detected at all in each sample; a sample can carry more "
         f"{el} per particle and still have fewer particles with it."),
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
    name = QUANTITY_NAMES[unit]
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
                group_by="sample", y_label="Particles with it (%)", error="none"),
         f"How often each replicate detects {el}; replicates of one sample should agree."),
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
                group_by="sample", y_label="Particles with it (%)", error="none"),
         f"{el} is found in a much larger share of one sample's particles; Fisher's exact "
         "test on these shares, with the replicates kept apart, made it stand out." + measured),
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
    story.append((_histogram(ctx, unit, el, f"{el} {QUANTITY_NAMES[unit]} and detection limit"),
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
                         group_by="size", y_label="Particles with it (%)", error="none"),
                  _size_caption(f"How often {el} is detected")
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
        (_panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True, bins=40,
                x_label=f"{a}/{b} ({unit})"),
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


def _correlation(s, ctx):
    a, b = s.elements[0], s.elements[1]
    rho = _detail(s, "Rank correlation (ρ)")
    rho_p = _detail(s, "Proportionality (ρp)")
    xa, xb = _amount(ctx, a), _amount(ctx, b)
    name = QUANTITY_NAMES[_unit(ctx)]
    both = f"{a} > 0 and {b} > 0"
    holds = ""
    if ctx.table is not None:
        rows = [r for r in ev.size_holds(ctx.table, xb, xa, both) if r[2] >= 10]
        if rows:
            holds = (" Measured within each size class: "
                     + "; ".join(f"{n} ρ = {r:+.2f} ({k:,})" for n, r, k in rows) + ".")
            same_sign = all(np.sign(r) == np.sign(rows[0][1]) and abs(r) >= 0.2 for _n, r, _k in rows)
            ctx.checks.add(same_sign, "the correlation "
                           + ("holds within every size class" if same_sign else
                              "weakens within size classes, so particle size may drive it"))
    return [
        (_panel("scatter", f"{a} against {b}", x=xb, y=xa, log_x=True, log_y=True, show_fit=True,
                x_label=_amount_name(ctx, b), y_label=_amount_name(ctx, a),
                marker_size=10),
         f"In particles carrying both, {a} rises with {b}" + (f" (ρ = {rho})" if rho else "")
         + "." + _coincidence_sentence(ctx, a, b)),
        (_panel("hexbin", "Where most particles sit", x=xb, y=xa, log_x=True, log_y=True,
                x_label=_amount_name(ctx, b), y_label=_amount_name(ctx, a)),
         "The same particles as a density map, showing where most of them sit rather than "
         "the few at the edges."),
        (_panel("scatter", f"{a} against {b} by particle size", x=xb, y=xa, log_x=True,
                log_y=True, group_by="size", show_other=False, show_fit=True, fit_band=False,
                filter=both, x_label=_amount_name(ctx, b), y_label=_amount_name(ctx, a),
                marker_size=10),
         "The same particles split into small, medium and large thirds by total mass, each "
         "with its own fit; elements that only grow together with particle size correlate "
         "overall but not within a size class." + holds),
        (_panel("scatter", "Ratio against particle size", x=f"{xa} + {xb}", y=f"{xa} / {xb}",
                log_x=True, log_y=True, trend="median", x_label=f"{a} + {b} {name}",
                y_label=f"{a}/{b}", marker_size=10),
         "A flat ratio means a fixed composition; a ratio that changes with size means the "
         "two only grow together"
         + (f" (proportionality ρp = {rho_p})" if rho_p and rho_p != "n/a" else "") + "."),
        (_panel("histogram", f"{a}/{b} in each particle", value=f"{xa} / {xb}", log_x=True,
                bins=40, x_label=f"{a}/{b} ({name})"),
         "One tight peak supports a single particle type; a broad or split ratio suggests "
         "several."),
    ]


def _cooccurrence(s, ctx):
    rare, common = s.elements[0], s.elements[1]
    together = s.explain_key == "cooccurrence_with"
    measured = ""
    if ctx.table is not None:
        ind = ev.independence(ctx.table, rare, common)
        if ind is not None:
            measured = (f" Measured: {ind['observed']:,} particles carry both, against "
                        f"{ind['expected']:.3g} if the two were found independently.")
    story = [
        (_panel("combinations", f"Combinations in particles with {rare}", top_n=10,
                filter=f"{rare} > 0"),
         f"{rare} and {common} "
         + ("share particles far more often than chance would give."
            if together else "are found in separate particles far more often than chance "
                             "would give.") + measured
         + (_coincidence_sentence(ctx, rare, common) if together else "")),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="conditional"),
         "Each cell is the share of the row element's particles that also carry the column "
         "element; only presence counts here, not amount."),
        (_panel("histogram", f"{rare} with and without {common}", value=_amount(ctx, rare),
                log_x=True, bins=40, x_label=_amount_name(ctx, rare),
                **_with_without(rare, common)),
         f"{rare} particles with and without {common}, by {QUANTITY_NAMES[_unit(ctx)]}."),
        (_panel("bar", f"{rare} particles carrying {common}, by size", value=common,
                agg="detect_pct", group_by="size", filter=f"{rare} > 0",
                y_label=f"With {common} (%)", error="none"),
         _size_caption(f"How often {rare} particles carry {common}")
         + _share_size_sentence(ctx, common, f"{rare} > 0")),
        (_histogram(ctx, _unit(ctx), rare,
                    f"{rare} {QUANTITY_NAMES[_unit(ctx)]} and detection limit"),
         f"If {rare} is only detectable in large particles, it will seem to avoid elements "
         "found in small ones; the dashed line shows how close it sits to its threshold."),
    ]
    if not together and _can_check(ctx, common, rare):
        story.insert(4, (_detect_box(ctx, common, rare, f"Could {rare} be seen in {common} particles?",
                                     **_with_without(common, rare)),
                         _detect_caption(common, rare) + f" If the {common} particles without "
                         f"{rare} sit mostly below the line, the two may not truly avoid each other."))
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
                     f"{QUANTITY_NAMES[unit].split(' ')[-1].strip('()')}, {v.size:,} particles.")
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
        story.append((_histogram(ctx, unit, el, f"{el} {QUANTITY_NAMES[unit]} by sample",
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
        (_panel("composition", "Average composition", **picked),
         "The average make-up of the particles."),
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
    els = ", ".join(_amount(ctx, e) for e in s.elements)
    return [
        (_panel("network", "Correlated elements", isotopes=els, net_r_min=0.5),
         "These elements form one connected group; each link is a significant correlation "
         "with |ρ| of at least 0.5."),
        (_panel("corr_matrix", "Correlation matrix", isotopes=els, corr_method="spearman",
                log_values=True),
         "The rank correlation of every pair."),
        (_panel("cooccurrence", "How often they share particles", isotopes=els),
         "Elements that also share particles likely come from one source."),
        (_panel("combinations", "Most common combinations", top_n=10),
         "Links are pairwise, so two elements in the group need not correlate directly."),
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


def story_layout(n: int, caption: str = "") -> tuple[list[list[float]], list[float], float, float]:
    """Place *n* panels above a caption sized to its text.

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
    chars_per_line = max(40, int(width * 15))
    lines = max(1, math.ceil(len(caption) / chars_per_line))
    caption_height = 0.35 + 0.19 * lines
    height = plot_height + caption_height
    top = plot_height / height
    rects = [[(i % cols) / cols, (i // cols) * top / rows, 1.0 / cols, top / rows]
             for i in range(n)]
    return rects, [0.0, top, 1.0, 1.0 - top], width, height


def caption_text(title: str, captions: list[str]) -> str:
    """Write the figure legend: the title, then one sentence per panel letter."""
    from results.figure_builder.core.spec import panel_letter
    parts = [f"{title}."] + [f"({panel_letter(i, 'a')}) {c}" for i, c in enumerate(captions)]
    return " ".join(parts)


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


def same_ranges(ctx: FigureContext, panels: list[dict]) -> list[dict]:
    """Give the per-group copies of an X–Y panel the same axis ranges.

    Each copy would otherwise fit its own group, and two panels side by side
    on different scales cannot be compared by eye. The range covers every
    group's particles that the panels draw.
    """
    if ctx.table is None or not panels or panels[0].get("kind") not in XY_KINDS:
        return panels
    first = panels[0]
    out = [dict(p) for p in panels]
    for axis in ("x", "y"):
        expr = first.get(axis)
        if not expr:
            continue
        try:
            v = ev._eval(ctx.table, expr)
            m = np.zeros(len(ctx.table), dtype=bool)
            for p in panels:
                m |= ev.mask(ctx.table, p.get("filter") or "")
        except Exception:
            continue
        found = _axis_range(v[m], bool(first.get(f"log_{axis}")))
        if found is None:
            continue
        for p in out:
            p[f"{axis}_min"], p[f"{axis}_max"] = f"{found[0]:.6g}", f"{found[1]:.6g}"
    return out


def by_groups(story: list, names: list[str], ctx: FigureContext | None = None
              ) -> list[tuple[list[dict], str, str]]:
    """Lay a story out to compare groups.

    A panel that can show the groups together (histograms, cumulative curves,
    box, bar and dot plots, timelines) colours them, one colour per group. A
    panel that cannot without becoming unreadable (scatters, density maps,
    ternaries, pies, combinations, matrices), or one already split another
    way (with and without an element, by size), is drawn once per group,
    side by side. A panel already comparing samples is kept as it is.

    Args:
        story: ``(panel, caption)`` pairs.
        names: The groups, at least two.

    Returns:
        Rows of ``(panels, caption, kind)``; *kind* is ``"wide"`` for one
        panel across the row and ``"split"`` for one panel per group.
    """
    rows = []
    split_ok = len(names) <= MAX_SPLIT_GROUPS
    for panel, caption in story:
        kind = panel.get("kind")
        grouping = panel.get("group_by") or "none"
        if grouping == "sample":
            rows.append(([panel], caption, "wide"))
        elif kind in OVERLAY_KINDS and grouping == "none":
            rows.append(([dict(panel, group_by="sample")], caption + " Each colour is one group.",
                          "wide"))
        elif split_ok:
            copies = [_for_group(panel, n) for n in names]
            if ctx is not None:
                copies = same_ranges(ctx, copies)
            shared = " The panels share their axis ranges." if kind in XY_KINDS else ""
            rows.append((copies, caption + shared, "split"))
        elif kind in OVERLAY_KINDS or kind in ("scatter", "combinations"):
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


def rows_layout(rows, n_groups: int, caption: str = ""):
    """Place grouped rows above the legend: a wide panel spans its row, the others share it equally.

    Returns:
        ``(panel_rects, caption_rect, width, height)`` as :func:`story_layout`.
    """
    cells = [len(panels) for panels, _c, kind in rows if kind != "wide"]
    cols = max(2, min(max(cells) if cells else n_groups, max(MAX_SPLIT_GROUPS, GROUP_ROW_VIEWS)))
    width = 5.4 * cols
    plot_height = 3.9 * len(rows)
    chars_per_line = max(40, int(width * 15))
    lines = max(1, math.ceil(len(caption) / chars_per_line))
    caption_height = 0.35 + 0.19 * lines
    height = plot_height + caption_height
    top = plot_height / height
    row_h = top / len(rows)
    rects = []
    for r, (panels, _caption, kind) in enumerate(rows):
        if kind == "wide":
            rects.append([0.0, r * row_h, 1.0, row_h])
        else:
            w = 1.0 / len(panels)
            rects.extend([k * w, r * row_h, w, row_h] for k in range(len(panels)))
    return rects, [0.0, top, 1.0, 1.0 - top], width, height


def rows_caption(title: str, rows, names: list[str], views=None) -> str:
    """The legend of a grouped figure, naming the panel of each group.

    Args:
        title: The finding's title.
        rows: The rows drawn.
        names: The groups.
        views: For a figure laid out one row per group, the split views in
            order, as ``(panels, caption, kind)``; each gets one sentence
            listing its panel in every group.
    """
    from results.figure_builder.core.spec import panel_letter
    parts = [f"{title}."]
    i = 0
    if views is not None:
        for panels, caption, kind in rows:
            if kind == "wide":
                parts.append(f"({panel_letter(i, 'a')}) {caption}")
                i += 1
        first_group_row = i
        per_row = len(views)
        for v, (_panels, caption, _kind) in enumerate(views):
            letters = [panel_letter(first_group_row + g * per_row + v, 'a') for g in range(len(names))]
            which = ", ".join(f"({x}) {n}" for x, n in zip(letters, names))
            parts.append(f"({', '.join(letters)}) {caption} One panel per group: {which}.")
        parts.append("Each row is one group: " + "; ".join(
            f"{n} {panel_letter(first_group_row + g * per_row, 'a')}–"
            f"{panel_letter(first_group_row + g * per_row + per_row - 1, 'a')}"
            for g, n in enumerate(names)) + ".")
        return " ".join(parts)
    for panels, caption, kind in rows:
        if kind == "wide":
            parts.append(f"({panel_letter(i, 'a')}) {caption}")
            i += 1
            continue
        letters = [panel_letter(i + k, 'a') for k in range(len(panels))]
        which = ", ".join(f"({x}) {n}" for x, n in zip(letters, names))
        parts.append(f"({letters[0]}–{letters[-1]}) {caption} One panel per group: {which}.")
        i += len(panels)
    return " ".join(parts)


def _group_values(ctx: FigureContext, expr: str, rule: str, names: list[str]):
    """``(group, values)`` of *expr* among the particles passing *rule*, per group."""
    v = ev._eval(ctx.table, expr)
    m = ev.mask(ctx.table, rule) & np.isfinite(v) & (v > 0)
    col = ctx.table.column("sample")
    return [(n, v[m & (col == n)]) for n in names]


def _medians_between(ctx: FigureContext, expr: str, rule: str, what: str, names: list[str],
                     tolerance: float = 0.10) -> str:
    """Compare a value's median between groups, adding a check; return the sentence."""
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
    ctx.checks.add(same, f"{what} {'is alike in every group' if same else 'differs between groups'} "
                         f"({', '.join(f'{n} {m:.3g}' for n, m, _k in meds)}; Kruskal-Wallis "
                         f"{ev.p_text(p)})")
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
                                    f"{els[0]}/{els[1]} ratio", names, tolerance=0.01)
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
    evidence, the meaning, then the limits. A caption panel
    under them, written like a journal figure legend, says what each panel
    shows, with the finding's own numbers. When the figure's particles fall
    into two or more groups, every view compares them (see
    :func:`by_groups`) and the legend says whether the finding holds in
    each group.

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
        design = _composition
    elif design not in (_composition, _time, _size_trend, _network) and not s.elements:
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
        legend = rows_caption(s.title, rows, names, views if mode == "groups" else None)
        between = between_groups(s, ctx, design, names)
        if between:
            legend = f"{legend} {between}"
        flat = [panel for panels, _c, _k in rows for panel in panels]
    else:
        legend = caption_text(s.title, [c for _p, c in story])
        flat = [panel for panel, _c in story]
    note = limits_sentence(ctx)
    if note:
        legend = f"{legend} {note}"
    verdict = ctx.checks.line()
    if verdict:
        legend = f"{legend} {verdict}"
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
                             text_size=9.5, panel_bg="#ffffff"))
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
