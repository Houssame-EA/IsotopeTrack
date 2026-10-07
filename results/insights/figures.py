"""Figures that tell the story behind a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to f and a legend underneath. The panels
tell the finding's story in order: the pattern itself, the evidence behind
it, what it means, and the limits to keep in mind. Wherever it helps, the
panels show the element in counts, mass and size, with the element's own
detection limit from the calibration marked on each axis (LOD in net counts,
MDL in fg, SDL in nm), so it is plain how much of a pattern sits near the
detection limit, and the legend quotes the values. Panels comparing samples
carry a significance test.

:func:`figure_for` builds the design; the panel adds it to the canvas as a
Figure Builder node fed by a selector holding the finding's samples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

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
    """

    quantities: set = field(default_factory=lambda: {"counts"})
    limits: dict = field(default_factory=dict)
    smallest: dict = field(default_factory=dict)
    multi_sample: bool = False
    groups: int = 1
    used: set = field(default_factory=set)


def _panel(kind: str, title: str, **settings) -> dict:
    """One panel's settings, before it is given a place on the page."""
    return {"kind": kind, "title": title, **settings}


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


def _quantity_panels(ctx: FigureContext, label: str) -> list[dict]:
    """Histograms of one element in every quantity the data carries."""
    return [_histogram(ctx, q, label) for q in ("counts", "mass", "d") if q in ctx.quantities]


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
    masses and sizes are close to log-normal.
    """
    if groups < 2:
        return {}
    base = {"test_log": bool(log_values)}
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
    return (f" {test}; it counts every particle, so with thousands of particles even a "
            "small shift can be significant, and the size of the difference matters as "
            "much as p.")


def _interference(s, ctx):
    parent, child = s.elements[0], s.elements[1]
    species = _detail(s, "Likely species", f"an ion of {parent}")
    ratio = _detail(s, "Median suspect/parent")
    spread = _detail(s, "Spread of the ratio")
    slope = _detail(s, "Slope on log axes")
    return [
        (_panel("scatter", f"{child} against {parent}", x=parent, y=child, log_x=True,
                log_y=True, show_fit=True, show_r=True),
         f"Every particle with {child} also carries {parent}, and the two rise together"
         + (f" with a slope of {slope} on log axes" if slope and slope != "n/a" else "")
         + f", as expected when the {child} signal is made from {parent} in the plasma."),
        (_panel("histogram", f"{child}/{parent} in each particle", value=f"{child} / {parent}",
                bins=40, x_label=f"{child}/{parent}"),
         f"The {child}/{parent} ratio of each particle stays near {ratio or 'one value'}"
         + (f" (spread {spread})" if spread else "")
         + "; a separate element would vary from particle to particle instead of keeping "
           "a fixed share."),
        (_panel("histogram", f"{parent} with and without {child}", value=parent, log_x=True,
                bins=40, x_label=f"{parent} counts", **_with_without(parent, child)),
         f"Particles with {child} (orange) are the ones with the largest {parent} signal. "
         f"{species} is a small fraction of {parent}, so it only clears the detection "
         f"threshold when there is a lot of {parent}."),
        (_histogram(ctx, "counts", child, f"{child} counts and detection limit"),
         f"The {child} counts sit just above the detection limit (dashed line); in these "
         f"particles {child} is best read as {species}, not as a separate element."),
    ]


def _isotope_pair(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    median = _detail(s, "Median") or _detail(s, "Measured median")
    found = (f"The {num}/{den} ratio of each particle; its median is {median}"
             + (f", against {natural:.4g} for natural abundance (line)" if natural else "")
             + ".")
    if s.explain_key == "isotope_two":
        found = (f"The {num}/{den} ratio of each particle falls into two groups, near "
                 f"{_detail(s, 'Lower population')} and {_detail(s, 'Upper population')}, "
                 "so the sample holds two kinds of particles with different isotope "
                 "signatures.")
    story = [
        (_panel("histogram", f"{num}/{den} in each particle", value=ratio, bins=50,
                x_label=f"{num}/{den}", **_ratio_lines(natural, "x")), found),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), poisson_band=2.0),
         f"Each point is one particle carrying both isotopes of the same element"
         + ("; the line is the natural ratio and the band the scatter counting statistics "
            "alone would produce, so points outside the band differ for real." if natural
            else ".")),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                x_label=f"{den} counts", y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
         "Small particles scatter more because they produce fewer ions; the running median "
         "shows whether the ratio itself changes with particle size."),
        (_histogram(ctx, "counts", den, f"{den} counts and detection limit"),
         f"{den} counts against the detection limit (dashed line). Near the threshold the "
         "minor isotope reads high, so the median above was taken from the upper half of the "
         "signal only."),
    ]
    if ctx.multi_sample:
        story.append((_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                             y_label=f"{num}/{den}", **_ratio_lines(natural, "y"),
                             **_test(ctx.groups, log_values=False)),
                      f"The same ratio in each sample; a sample far from the others should be "
                      "looked at before the samples are pooled."
                      + _test_sentence(ctx.groups, "ratios", log_values=False)))
    return story


def _isotope_track(s, ctx, natural=None):
    num, den, other = s.elements[0], s.elements[1], s.elements[2]
    ratio = f"{num} / {den}"
    rho = _detail(s, "Rank correlation (ρ)")
    return [
        (_panel("scatter", f"{num}/{den} against {other}", x=other, y=ratio, log_x=True,
                trend="median", x_label=f"{other} counts", y_label=f"{num}/{den}",
                **_ratio_lines(natural, "y")),
         f"The {num}/{den} isotope ratio changes with the amount of {other}, a different "
         f"element, in the same particle" + (f" (ρ = {rho})" if rho else "") + "."),
        (_panel("box", f"{num}/{den} with and without {other}", value=ratio,
                y_label=f"{num}/{den}", **_with_without(num, other),
                **_ratio_lines(natural, "y"), **_test(2, log_values=False)),
         f"Particles carrying {other} have a different ratio from those without it."
         + _test_sentence(2, "ratios", log_values=False)),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), **_with_without(num, other)),
         f"The sample mixes two kinds of particles with different isotope signatures, one "
         f"of them rich in {other}."),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                x_label=f"{den} counts", y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
         f"If the ratio also drifts with signal, part of the trend comes from counting "
         f"statistics in small particles rather than from {other}."),
        (_histogram(ctx, "counts", other, f"{other} counts and detection limit"),
         f"Particles whose {other} is below its detection limit (dashed line) are counted "
         "as without it, so the two groups overlap a little."),
    ]


def _isotope_groups(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    diff = _detail(s, "Difference")
    spread = _detail(s, "Spread between replicates")
    return [
        (_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                y_label=f"{num}/{den}", **_ratio_lines(natural, "y"),
                **_test(ctx.groups, log_values=False)),
         f"The samples differ in their {num}/{den} isotope ratio"
         + (f" by {diff}" if diff else "")
         + (f", while the replicates of each agree within {spread}" if spread and "%" in spread
            else "") + "." + _test_sentence(ctx.groups, "ratios", log_values=False)),
        (_panel("ecdf", f"{num}/{den} distribution by sample", value=ratio, group_by="sample",
                x_label=f"{num}/{den}"),
         "The whole distribution of the ratio in each sample; curves shifted sideways mean "
         "the difference is shared by most particles, not a few."),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), group_by="sample"),
         "Both masses are isotopes of one element, so the samples differ in isotope "
         "signature, not in how much of the element they carry."),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                group_by="sample", x_label=f"{den} counts", y_label=f"{num}/{den}"),
         "The difference holds across signal levels when the running medians stay apart from "
         "small to large particles, rather than only among small, noisy ones."),
        (_histogram(ctx, "counts", den, f"{den} counts by sample", group_by="sample"),
         "Samples with very different signal ranges have different counting noise, which "
         "matters when comparing their ratios."),
    ]


def _comparison(s, ctx):
    el = s.elements[0]
    fold = _detail(s, "Fold difference in median")
    tests = _test(ctx.groups)
    story = [
        (_panel("box", f"{el} counts by sample", value=el, group_by="sample", log_y=True,
                **_limit(ctx, "counts", el), **tests),
         f"The median {el} per particle differs between the samples"
         + (f" by {fold}" if fold else "")
         + ", more than the replicates of each differ from one another."
         + _test_sentence(ctx.groups, "counts")),
        (_histogram(ctx, "counts", el, f"{el} counts by sample", group_by="sample"),
         f"The full {el} distributions; a whole shift means the particles differ in size or "
         "composition, a change on one side only means one population was added or lost."),
    ]
    for prefix in ("mass", "d"):
        if prefix in ctx.quantities:
            name = QUANTITY_NAMES[prefix]
            story.append((_panel("box", f"{el} {name} by sample",
                                 value=_expr(prefix, el), group_by="sample", log_y=True,
                                 **_limit(ctx, prefix, el), **tests),
                          (f"The same comparison in {name}, which no longer depends on the "
                           "instrument's sensitivity on the day." if prefix == "mass" else
                           f"And as equivalent particle size (nm).")
))
    story.append((_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                         group_by="sample", y_label="Particles with it (%)", error="none"),
                  f"How often {el} is detected at all in each sample; a sample can carry more "
                  f"{el} per particle and still have fewer particles with it."))
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
    return [
        (_panel("box", f"{el} counts by replicate", value=el, group_by="sample", log_y=True,
                **_limit(ctx, "counts", el)),
         f"{s.title}: the {el} signal per particle in each replicate."),
        (_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                group_by="sample", y_label="Particles with it (%)", error="none"),
         f"How often each replicate detects {el}; replicates of one sample should agree."),
        (_panel("timeline", "Particles arriving over the run", time_mode="cumulative",
                group_by="sample"),
         "Each line's slope is that replicate's particle rate; a different slope points to "
         "transport or dilution rather than to the particles."),
        (_histogram(ctx, "counts", el, f"{el} counts by replicate", group_by="sample"),
         "Replicates should share the shape of the distribution, not only its middle."),
    ]


def _signature(s, ctx):
    el = s.elements[0]
    story = [
        (_panel("bar", f"Share of particles with {el}", value=el, agg="detect_pct",
                group_by="sample", y_label="Particles with it (%)", error="none"),
         f"{el} is found in a much larger share of one sample's particles; Fisher's exact "
         "test on these shares, with the replicates kept apart, made it stand out."),
        (_panel("combinations", "Most common element combinations", top_n=12,
                group_by="sample"),
         f"The particle types in each sample, showing which combinations carry {el}."),
    ]
    for prefix in ("counts", "d"):
        if prefix in ctx.quantities:
            story.append((_histogram(ctx, prefix, el,
                                     f"{el} {QUANTITY_NAMES[prefix]} and detection limit"),
                          f"{el} particles against the detection limit (dashed line); if most "
                          "sit close to it, the sample with fewer may simply have smaller "
                          f"{el} particles that fall below it."))
    return story


def _stoichiometry(s, ctx):
    a, b = s.elements[0], s.elements[1]
    prefix = "moles" if "moles" in ctx.quantities else "counts"
    ratio = f"{_expr(prefix, a)} / {_expr(prefix, b)}"
    total = f"{_expr(prefix, a)} + {_expr(prefix, b)}"
    unit = "moles" if prefix == "moles" else "counts"
    value = _detail(s, "Ratio")
    simple = _detail(s, "Closest simple ratio")
    story = [
        (_panel("scatter", f"{a} against {b} ({unit})", x=_expr(prefix, b), y=_expr(prefix, a),
                log_x=True, log_y=True, show_fit=True, show_r=True),
         f"{a} and {b} keep a fixed ratio in every particle that carries both"
         + (f", {value}" if value else "") + "."),
        (_panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True, bins=40,
                x_label=f"{a}/{b} ({unit})"),
         "The ratio forms one narrow peak, far narrower than if the two elements varied "
         "independently."),
        (_panel("scatter", "Ratio against particle amount", x=total, y=ratio, log_x=True,
                log_y=True, trend="median", x_label=f"{a} + {b} ({unit})", y_label=f"{a}/{b}"),
         "The ratio holds from small to large particles, which points to one compound"
         + (f", close to {simple}" if simple and simple.startswith(("1", "2", "3", "4"))
            else "") + "."),
    ]
    size = "d" if "d" in ctx.quantities else "counts"
    story.append((_histogram(ctx, size, a),
                  f"{a} particles against the detection limit (dashed line); ratios of particles "
                  "close to it are the least precise."))
    return story


def _correlation(s, ctx):
    a, b = s.elements[0], s.elements[1]
    rho = _detail(s, "Rank correlation (ρ)")
    rho_p = _detail(s, "Proportionality (ρp)")
    return [
        (_panel("scatter", f"{a} against {b}", x=b, y=a, log_x=True, log_y=True, show_fit=True,
                show_r=True),
         f"In particles carrying both, {a} rises with {b}" + (f" (ρ = {rho})" if rho else "")
         + "."),
        (_panel("hexbin", "Where most particles sit", x=b, y=a, log_x=True, log_y=True),
         "The same particles as a density map, showing where most of them sit rather than "
         "the few at the edges."),
        (_panel("scatter", "Ratio against particle size", x=f"{a} + {b}", y=f"{a} / {b}",
                log_x=True, log_y=True, trend="median", x_label=f"{a} + {b} counts",
                y_label=f"{a}/{b}"),
         "A flat ratio means a fixed composition; a ratio that changes with size means the "
         "two only grow together"
         + (f" (proportionality ρp = {rho_p})" if rho_p and rho_p != "n/a" else "") + "."),
        (_panel("histogram", f"{a}/{b} in each particle", value=f"{a} / {b}", log_x=True,
                bins=40),
         "One tight peak supports a single particle type; a broad or split ratio suggests "
         "several."),
    ]


def _cooccurrence(s, ctx):
    rare, common = s.elements[0], s.elements[1]
    together = s.explain_key == "cooccurrence_with"
    return [
        (_panel("combinations", f"Combinations in particles with {rare}", top_n=12,
                filter=f"{rare} > 0"),
         f"{rare} and {common} "
         + ("share particles far more often than chance would give."
            if together else "are found in separate particles far more often than chance "
                             "would give.")),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="conditional"),
         "Each cell is the share of the row element's particles that also carry the column "
         "element; only presence counts here, not amount."),
        (_panel("histogram", f"{rare} with and without {common}", value=rare, log_x=True,
                bins=40, **_with_without(rare, common)),
         f"{rare} particles with and without {common}, by signal."),
        (_histogram(ctx, "counts", rare, f"{rare} counts and detection limit"),
         f"If {rare} is only detectable in large particles, it will seem to avoid elements "
         "found in small ones; the dashed line shows how close it sits to its threshold."),
    ]


def _rare(s, ctx):
    el = s.elements[0]
    story = [
        (_panel("combinations", f"Particles with {el}", top_n=12, filter=f"{el} > 0"),
         f"Only a few particles carry {el}; these are the element combinations they come in."),
        (_panel("strip", f"{el} in each particle", value=el, log_y=True,
                **_limit(ctx, "counts", el)),
         f"Each dot is one {el} particle; the dashed line is the detection limit."),
        (_panel("timeline", f"When {el} particles arrive", time_mode="signal", value=el,
                log_y=True, filter=f"{el} > 0"),
         "Particles arriving together in time point to one contamination event; spread "
         "evenly, they belong to the sample."),
    ]
    if len(s.elements) > 1:
        story.insert(2, (_panel("scatter", f"{el} against {s.elements[1]}", x=s.elements[1],
                                y=el, log_x=True, log_y=True, filter=f"{el} > 0"),
                         f"{el} with {s.elements[1]}, the element it usually comes with."))
    return story


def _distribution(s, ctx):
    el = s.elements[0]
    story = []
    lead = {
        "quality": f"The {el} distribution piles up at its lowest values, so part of the "
                   "population likely continues below the detection limit (dashed line).",
        "distribution_two": f"The {el} signal splits into two populations of particles.",
    }.get(s.explain_key, f"{el} varies widely from particle to particle.")
    for i, prefix in enumerate(q for q in ("counts", "mass", "d") if q in ctx.quantities):
        name = QUANTITY_NAMES[prefix]
        caption = lead if i == 0 else (
            f"The same particles in {name}, with the detection limit as a dashed line.")
        story.append((_histogram(ctx, prefix, el), caption))
    story.append((_panel("ecdf", f"{el} cumulative distribution", value=el, log_x=True,
                         **_limit(ctx, "counts", el)),
                  "The cumulative curve shows what share of particles sits close to the "
                  "detection limit; a curve that starts steeply at the threshold means "
                  "the population continues below it."))
    if ctx.multi_sample:
        story.append((_histogram(ctx, "counts", el, f"{el} counts by sample", group_by="sample"),
                      "Each sample on its own, to see whether they share the same shape."))
    return story


def _size_trend(s, ctx):
    figure_panels = s.config.get("panels") or []
    y = figure_panels[0].get("y", "") if figure_panels else ""
    el = y.split(":", 1)[-1].split("/")[0].strip() if y else ""
    story = [
        (_panel("scatter", f"{el} share against particle mass", x="total", y=y, log_x=True,
                trend="median", filter="n_elements >= 2", x_label="Particle mass (fg)",
                y_label=f"{el} mass fraction"),
         f"The {el} share of each multi-element particle changes with the particle's mass."),
        (_panel("histogram", f"{el} mass fraction", value=y, bins=40, filter="n_elements >= 2",
                x_label=f"{el} mass fraction"),
         f"The spread of the {el} share across those particles."),
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
    story = [
        (_panel("timeline", "Particle rate over the run", time_mode="rate"),
         "The particle arrival rate or signal changes during the run instead of staying "
         "steady."),
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
    story = [
        (_panel("combinations", "Most common element combinations", top_n=12),
         "The particle types that dominate, each defined by the set of elements detected in "
         "it."),
        (_panel("composition", "Average composition", **picked),
         "The average make-up of the particles."),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="joint",
                **picked),
         "Elements that often share particles belong to the same particle type."),
    ]
    if len(els) == 3:
        story.append((_panel("ternary", f"{els[0]}–{els[1]}–{els[2]}", a=els[0], b=els[1],
                             c=els[2]),
                      "One tight cluster means one composition; points along a line between "
                      "corners mean mixing."))
    story.append((_panel("pie", "Particle types", pie_mode="combinations", top_n=8),
                  "Which elements are detected depends on each element's detection limit, so "
                  "small particles may appear to lack their minor elements."))
    return story


def _network(s, ctx):
    els = ", ".join(s.elements)
    return [
        (_panel("network", "Correlated elements", isotopes=els, net_r_min=0.5),
         "These elements form one connected group; each link is a significant correlation "
         "with |ρ| of at least 0.5."),
        (_panel("corr_matrix", "Correlation matrix", isotopes=els, corr_method="spearman",
                log_values=True),
         "The rank correlation of every pair."),
        (_panel("cooccurrence", "How often they share particles", isotopes=els),
         "Elements that also share particles likely come from one source."),
        (_panel("combinations", "Most common combinations", top_n=12),
         "Links are pairwise, so two elements in the group need not correlate directly."),
    ]


def _outlier(s, ctx):
    els = list(s.elements) or [str(s.config.get("highlight_element", ""))]
    el = els[0]
    story = [
        (_panel("strip", f"{el} in each particle", value=el, log_y=True,
                **_limit(ctx, "counts", el)),
         f"A few particles carry far more {el} than the rest."),
        (_histogram(ctx, "counts", el),
         "On log values, these particles sit far above the upper quartile of the "
         "distribution."),
    ]
    if len(els) > 1:
        story.append((_panel("scatter", f"{els[0]} against {els[1]}", x=els[1], y=els[0],
                             log_x=True, log_y=True),
                      "Being extreme in two elements at once is unlikely to be chance."))
    story.append((_panel("timeline", f"When large {el} particles arrive", time_mode="signal",
                         value=el, log_y=True),
                  "Two particles arriving together can look like one large particle."))
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
}
"""Figure stories keyed by a finding's explain key.

Each design returns ``(panel, caption)`` pairs in story order: the pattern,
the evidence, the meaning, then the limits. The captions become the
figure's legend.
"""

ISOTOPE_DESIGNS = {_isotope_pair, _isotope_track, _isotope_groups}

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


def figure_for(s, ctx: FigureContext) -> dict | None:
    """Build the figure that tells a finding's story, panels a to f with a legend.

    The panels follow the finding's story in order: the pattern, the
    evidence, the meaning, then the limits. A caption panel
    under them, written like a journal figure legend, says what each panel
    shows, with the finding's own numbers.

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
    legend = caption_text(s.title, [c for _p, c in story])
    note = limits_sentence(ctx)
    if note:
        legend = f"{legend} {note}"
    rects, caption_rect, width, height = story_layout(len(story), legend)
    spec = default_spec()
    spec["figure"].update({"width": width, "height": height, "panel_letters": True})
    spec["data_type"] = "Counts"
    panels = [make_panel(rect=list(rects[i]), **panel) for i, (panel, _c) in enumerate(story)]
    panels.append(make_panel(rect=list(caption_rect), kind="text", caption=True,
                             text=legend,
                             text_size=9.5, panel_bg="#ffffff"))
    spec["panels"] = panels
    return normalise_spec(spec)


def context_from(particles: list[dict], labels, limits: dict | None = None,
                 multi_sample: bool = False, groups: int | None = None) -> FigureContext:
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
    flat = {(prefix, label): dict(per_sample)
            for label, by_prefix in (limits or {}).items()
            for prefix, per_sample in (by_prefix or {}).items() if per_sample}
    if groups is None:
        groups = 2 if multi_sample else 1
    return FigureContext(quantities or {"counts"}, flat, smallest, multi_sample, groups)
