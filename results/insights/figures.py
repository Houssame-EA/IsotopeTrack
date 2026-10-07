"""Figures that tell the story behind a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to f and a legend underneath. The panels
follow the finding's explanation in order: what Insights found, how it was
found, how to read it, and what to check before relying on it. Wherever it helps, the panels show the element in counts, mass and size,
with the detection threshold marked on count axes and the smallest detected
particle marked on mass and size axes, so it is plain how much of a pattern
sits near the detection limit.

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
        thresholds: Isotope label to its detection threshold in counts, where
            the processing recorded one.
        smallest: ``(prefix, label)`` to the smallest detected value, used to
            mark the practical detection limit on mass and size axes.
        multi_sample: Whether the figure covers more than one sample.
    """

    quantities: set = field(default_factory=lambda: {"counts"})
    thresholds: dict = field(default_factory=dict)
    smallest: dict = field(default_factory=dict)
    multi_sample: bool = False


def _panel(kind: str, title: str, **settings) -> dict:
    """One panel's settings, before it is given a place on the page."""
    return {"kind": kind, "title": title, **settings}


def _expr(prefix: str, label: str) -> str:
    """Expression reading *label* in quantity *prefix*."""
    return label if prefix == "counts" else f"{prefix}:{label}"


def _limit(ctx: FigureContext, prefix: str, label: str) -> dict:
    """Detection-limit line settings for a panel showing *label* in *prefix*."""
    if prefix == "counts" and label in ctx.thresholds:
        return {"dl_value": f"{ctx.thresholds[label]:.4g}", "dl_label": "Detection threshold"}
    value = ctx.smallest.get((prefix, label))
    if value:
        return {"dl_value": f"{value:.4g}", "dl_label": "Smallest detected"}
    return {}


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


def _interference(s, ctx):
    parent, child = s.elements[0], s.elements[1]
    species = _detail(s, "Likely species", f"an ion of {parent}")
    ratio = _detail(s, "Median suspect/parent")
    spread = _detail(s, "Spread of the ratio")
    slope = _detail(s, "Slope on log axes")
    return [
        (_panel("scatter", f"{child} against {parent}", x=parent, y=child, log_x=True,
                log_y=True, show_fit=True, show_r=True),
         f"What Insights found: {child} rises in step with {parent}"
         + (f", with a slope of {slope} on log axes" if slope and slope != "n/a" else "")
         + ", as a signal made from it would."),
        (_panel("histogram", f"{child}/{parent} in each particle", value=f"{child} / {parent}",
                bins=40, x_label=f"{child}/{parent}"),
         f"How it was found: the {child}/{parent} ratio stays near {ratio or 'one value'}"
         + (f" (spread {spread})" if spread else "")
         + " in every particle; a second element would not hold a fixed ratio."),
        (_panel("histogram", f"{parent} with and without {child}", value=parent, log_x=True,
                bins=40, x_label=f"{parent} counts", **_with_without(parent, child)),
         f"How to read it: {child} appears only in particles with a large {parent} signal. "
         f"{species} is a small fraction of {parent}, so it only clears the detection "
         f"threshold in the largest {parent} particles."),
        (_histogram(ctx, "counts", child, f"{child} counts and detection threshold"),
         f"Check: {child} values close to the detection threshold (dashed line) are the "
         f"ones most affected; treat {child} in these particles as {species}."),
    ]


def _isotope_pair(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    median = _detail(s, "Median") or _detail(s, "Measured median")
    found = (f"What Insights found: the median {num}/{den} is {median}"
             + (f", against {natural:.4g} for natural abundance (line)" if natural else "")
             + ".")
    if s.explain_key == "isotope_two":
        found = (f"What Insights found: the {num}/{den} ratio falls into two groups, near "
                 f"{_detail(s, 'Lower population')} and {_detail(s, 'Upper population')}.")
    story = [
        (_panel("histogram", f"{num}/{den} in each particle", value=ratio, bins=50,
                x_label=f"{num}/{den}", **_ratio_lines(natural, "x")), found),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), poisson_band=2.0),
         "How it was found: each point is one particle carrying both isotopes"
         + ("; the line is the natural ratio and the band the scatter expected from "
            "counting statistics alone." if natural else ".")),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                x_label=f"{den} counts", y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
         "How to read it: the ratio scatters more at low signal, as counting statistics "
         "predict; the running median shows whether it changes with particle size."),
        (_histogram(ctx, "counts", den, f"{den} counts and detection threshold"),
         f"Check: the median uses only particles in the upper half of the signal, away from "
         f"the detection threshold (dashed line), where the minor isotope would read high."),
    ]
    if ctx.multi_sample:
        story.append((_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                             y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
                      "Check: the ratio in each sample; one far from the others deserves a "
                      "look before pooling."))
    return story


def _isotope_track(s, ctx, natural=None):
    num, den, other = s.elements[0], s.elements[1], s.elements[2]
    ratio = f"{num} / {den}"
    rho = _detail(s, "Rank correlation (ρ)")
    return [
        (_panel("scatter", f"{num}/{den} against {other}", x=other, y=ratio, log_x=True,
                trend="median", x_label=f"{other} counts", y_label=f"{num}/{den}",
                **_ratio_lines(natural, "y")),
         f"What Insights found: the {num}/{den} ratio changes with {other}"
         + (f" (ρ = {rho})" if rho else "") + f"; {other} is a different element."),
        (_panel("box", f"{num}/{den} with and without {other}", value=ratio,
                y_label=f"{num}/{den}", **_with_without(num, other), **_ratio_lines(natural, "y")),
         f"How it was found: particles carrying {other} have a different ratio from those "
         f"without it."),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), **_with_without(num, other)),
         f"How to read it: two populations of particles with different isotope signatures, "
         f"one of them rich in {other}, mixed in the sample."),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                x_label=f"{den} counts", y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
         f"Check: if the ratio also drifts with signal, part of the trend can come from "
         f"counting statistics in small particles rather than from {other}."),
        (_histogram(ctx, "counts", other, f"{other} counts and detection threshold"),
         f"Check: particles with {other} below its detection threshold count as without it."),
    ]


def _isotope_groups(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    diff = _detail(s, "Difference")
    spread = _detail(s, "Spread between replicates")
    return [
        (_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                y_label=f"{num}/{den}", **_ratio_lines(natural, "y")),
         f"What Insights found: the groups differ in {num}/{den}"
         + (f" by {diff}" if diff else "") + "."),
        (_panel("ecdf", f"{num}/{den} distribution by sample", value=ratio, group_by="sample",
                x_label=f"{num}/{den}"),
         "How it was found: each replicate's median ratio was compared between groups"
         + (f"; the replicates of a group agree within {spread}." if spread and "%" in spread
            else ".")),
        (_panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
                natural_line=bool(natural), group_by="sample"),
         "How to read it: both masses are isotopes of one element, so the samples differ in "
         "isotope signature, not in amount."),
        (_panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
                group_by="sample", x_label=f"{den} counts", y_label=f"{num}/{den}"),
         "Check: the difference should hold at every signal level, not only among small, "
         "noisy particles."),
        (_histogram(ctx, "counts", den, f"{den} counts by sample", group_by="sample"),
         "Check: samples with very different signal ranges have different counting noise; "
         "compare like with like."),
    ]


def _comparison(s, ctx):
    el = s.elements[0]
    fold = _detail(s, "Fold difference in median")
    story = [
        (_panel("box", f"{el} counts by sample", value=el, group_by="sample", log_y=True,
                **_limit(ctx, "counts", el)),
         f"What Insights found: the median {el} per particle differs between groups"
         + (f" by {fold}" if fold else "") + "."),
        (_histogram(ctx, "counts", el, f"{el} counts by sample", group_by="sample"),
         "How it was found: groups were compared on their replicates' medians, and the "
         "difference had to exceed the spread between replicates."),
    ]
    for prefix in ("mass", "d"):
        if prefix in ctx.quantities:
            story.append((_panel("box", f"{el} {QUANTITY_NAMES[prefix]} by sample",
                                 value=_expr(prefix, el), group_by="sample", log_y=True,
                                 **_limit(ctx, prefix, el)),
                          f"How to read it: the same comparison in {QUANTITY_NAMES[prefix]}, "
                          "which does not depend on instrument sensitivity."))
    story.append((_panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
                         group_by="sample", y_label="Share of particles", error="none"),
                  f"Check: how often {el} is detected at all in each sample; a group can carry "
                  "more per particle and still have fewer particles with it."))
    return story


def _replicates(s, ctx):
    el = s.elements[0] if s.elements else ""
    if not el:
        return [
            (_panel("timeline", "Particles arriving over the run", time_mode="cumulative",
                    group_by="sample"),
             "What Insights found: the replicates collect particles at different rates."),
            (_panel("timeline", "Particle rate over the run", time_mode="rate", group_by="sample"),
             "Check: a rate that changes during one run points to transport, such as a "
             "nebuliser clogging."),
        ]
    return [
        (_panel("box", f"{el} counts by replicate", value=el, group_by="sample", log_y=True,
                **_limit(ctx, "counts", el)),
         f"What Insights found: {s.title.lower()} on {el}."),
        (_panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
                group_by="sample", y_label="Share of particles", error="none"),
         "How it was found: each replicate's median signal and detection rate were compared "
         "with its siblings."),
        (_panel("timeline", "Particles arriving over the run", time_mode="cumulative",
                group_by="sample"),
         "How to read it: the slope of each line is that replicate's particle rate; a "
         "different slope points to transport or dilution."),
        (_histogram(ctx, "counts", el, f"{el} counts by replicate", group_by="sample"),
         "Check: replicates should share the shape of the distribution, not only its middle."),
    ]


def _signature(s, ctx):
    el = s.elements[0]
    story = [
        (_panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
                group_by="sample", y_label="Share of particles", error="none"),
         f"What Insights found: {el} is far more common in one group's particles."),
        (_panel("combinations", "Most common element combinations", top_n=12,
                group_by="sample"),
         "How it was found: presence only, compared between groups with Fisher's exact test."),
    ]
    for prefix in ("counts", "d"):
        if prefix in ctx.quantities:
            story.append((_histogram(ctx, prefix, el,
                                     f"{el} {QUANTITY_NAMES[prefix]} and detection limit"),
                          f"Check: an element can look absent when its particles sit below the "
                          f"detection limit (dashed line) in one group."))
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
         f"What Insights found: {a} and {b} keep a fixed ratio"
         + (f", {value}" if value else "") + "."),
        (_panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True, bins=40,
                x_label=f"{a}/{b} ({unit})"),
         "How it was found: the ratio's spread is far smaller than if the two varied "
         "independently."),
        (_panel("scatter", "Ratio against particle amount", x=total, y=ratio, log_x=True,
                log_y=True, trend="median", x_label=f"{a} + {b} ({unit})", y_label=f"{a}/{b}"),
         "How to read it: a ratio that holds from small to large particles points to one "
         "phase" + (f", close to {simple}" if simple and simple.startswith(("1", "2", "3", "4"))
                    else "") + "."),
    ]
    size = "d" if "d" in ctx.quantities else "counts"
    story.append((_histogram(ctx, size, a),
                  "Check: the ratio of particles near the detection limit (dashed line) is the "
                  "least precise."))
    return story


def _correlation(s, ctx):
    a, b = s.elements[0], s.elements[1]
    rho = _detail(s, "Rank correlation (ρ)")
    rho_p = _detail(s, "Proportionality (ρp)")
    return [
        (_panel("scatter", f"{a} against {b}", x=b, y=a, log_x=True, log_y=True, show_fit=True,
                show_r=True),
         f"What Insights found: {a} and {b} rise together" + (f" (ρ = {rho})" if rho else "")
         + "."),
        (_panel("hexbin", "Where most particles sit", x=b, y=a, log_x=True, log_y=True),
         "How it was found: a rank correlation over particles carrying both; this panel shows "
         "where most of them sit."),
        (_panel("scatter", "Ratio against particle size", x=f"{a} + {b}", y=f"{a} / {b}",
                log_x=True, log_y=True, trend="median", x_label=f"{a} + {b} counts",
                y_label=f"{a}/{b}"),
         "How to read it: a flat ratio means a fixed composition; a ratio that changes with "
         "size means the two only grow together"
         + (f" (proportionality ρp = {rho_p})" if rho_p and rho_p != "n/a" else "") + "."),
        (_panel("histogram", f"{a}/{b} in each particle", value=f"{a} / {b}", log_x=True,
                bins=40),
         "Check: one tight peak supports a single phase; a broad or split ratio suggests "
         "several particle types."),
    ]


def _cooccurrence(s, ctx):
    rare, common = s.elements[0], s.elements[1]
    together = s.explain_key == "cooccurrence_with"
    return [
        (_panel("combinations", f"Combinations in particles with {rare}", top_n=12,
                filter=f"{rare} > 0"),
         f"What Insights found: {rare} and {common} "
         + ("share particles far more often than chance." if together
            else "are found in separate particles.")),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="conditional"),
         "How it was found: presence only; each cell is the share of the row element's "
         "particles that also carry the column element."),
        (_panel("histogram", f"{rare} with and without {common}", value=rare, log_x=True,
                bins=40, **_with_without(rare, common)),
         f"How to read it: {rare} particles with and without {common}, by signal."),
        (_histogram(ctx, "counts", rare, f"{rare} counts and detection threshold"),
         f"Check: if {rare} is only detectable in large particles, it will seem to avoid "
         "elements found in small ones."),
    ]


def _rare(s, ctx):
    el = s.elements[0]
    story = [
        (_panel("combinations", f"Particles with {el}", top_n=12, filter=f"{el} > 0"),
         f"What Insights found: only a few particles carry {el}, and these are their "
         "element combinations."),
        (_panel("strip", f"{el} in each particle", value=el, log_y=True,
                **_limit(ctx, "counts", el)),
         f"How it was found: each dot is one {el} particle; the dashed line is the detection "
         "threshold."),
        (_panel("timeline", f"When {el} particles arrive", time_mode="signal", value=el,
                log_y=True, filter=f"{el} > 0"),
         "Check: particles arriving together in time point to one contamination event."),
    ]
    if len(s.elements) > 1:
        story.insert(2, (_panel("scatter", f"{el} against {s.elements[1]}", x=s.elements[1],
                                y=el, log_x=True, log_y=True, filter=f"{el} > 0"),
                         f"How to read it: {el} with {s.elements[1]}, its usual companion."))
    return story


def _distribution(s, ctx):
    el = s.elements[0]
    story = []
    lead = {
        "quality": f"What Insights found: the {el} distribution piles up at its lowest values.",
        "distribution_two": f"What Insights found: {el} splits into two populations.",
    }.get(s.explain_key, f"What Insights found: {el} varies widely from particle to particle.")
    for i, prefix in enumerate(q for q in ("counts", "mass", "d") if q in ctx.quantities):
        name = QUANTITY_NAMES[prefix]
        caption = lead if i == 0 else (
            f"How to read it: the same particles in {name}; the dashed line is the smallest "
            "particle detected.")
        story.append((_histogram(ctx, prefix, el), caption))
    story.append((_panel("ecdf", f"{el} cumulative distribution", value=el, log_x=True,
                         **_limit(ctx, "counts", el)),
                  "Check: the share of particles close to the detection threshold; a curve "
                  "that starts steeply at the threshold means the population continues below "
                  "it."))
    if ctx.multi_sample:
        story.append((_histogram(ctx, "counts", el, f"{el} counts by sample", group_by="sample"),
                      "Check: whether every sample shows the same shape."))
    return story


def _size_trend(s, ctx):
    figure_panels = s.config.get("panels") or []
    y = figure_panels[0].get("y", "") if figure_panels else ""
    el = y.split(":", 1)[-1].split("/")[0].strip() if y else ""
    story = [
        (_panel("scatter", f"{el} share against particle mass", x="total", y=y, log_x=True,
                trend="median", filter="n_elements >= 2", x_label="Particle mass (fg)",
                y_label=f"{el} mass fraction"),
         f"What Insights found: the {el} share of each particle changes with its mass."),
        (_panel("histogram", f"{el} mass fraction", value=y, bins=40, filter="n_elements >= 2",
                x_label=f"{el} mass fraction"),
         "How it was found: a rank correlation between share and total mass in "
         "multi-element particles."),
        (_panel("histogram", "Particle mass", value="total", log_x=True, bins=40,
                x_label="Particle mass (fg)"),
         "How to read it: a share falling with size fits a coating or shell; rising fits a "
         "core."),
    ]
    if el:
        story.append((_histogram(ctx, "mass" if "mass" in ctx.quantities else "counts", el),
                      "Check: small particles near the detection limit lose minor elements "
                      "first, which can mimic the same trend."))
    return story


def _time(s, ctx):
    lead = ""
    for p in s.config.get("panels") or []:
        lead = p.get("value") or lead
    story = [
        (_panel("timeline", "Particle rate over the run", time_mode="rate"),
         "What Insights found: the particle arrival rate or signal changes during the run."),
        (_panel("timeline", "Particles arriving over the run", time_mode="cumulative"),
         "How it was found: arrivals counted in equal time bins and compared with a steady "
         "stream; a straight line here means a steady rate."),
    ]
    if lead:
        story += [
            (_panel("timeline", f"{lead} signal over the run", time_mode="signal", value=lead,
                    log_y=True),
             "How to read it: a steady trend in several elements points to instrument "
             "sensitivity; in one element, to the particles themselves."),
            (_histogram(ctx, "counts", lead, f"{lead} counts and detection threshold"),
             "Check: a falling signal pushes more particles below the detection threshold "
             "(dashed line), which also lowers the rate."),
        ]
    return story


def _composition(s, ctx):
    els = list(s.elements)
    picked = {"isotopes": ", ".join(els)} if els else {}
    story = [
        (_panel("combinations", "Most common element combinations", top_n=12),
         "What Insights found: which particle types dominate."),
        (_panel("composition", "Average composition", **picked),
         "How it was found: particles counted by the set of elements detected in them."),
        (_panel("cooccurrence", "How often elements share particles", cooc_mode="joint",
                **picked),
         "How to read it: elements that share particles belong to the same particle type."),
    ]
    if len(els) == 3:
        story.append((_panel("ternary", f"{els[0]}–{els[1]}–{els[2]}", a=els[0], b=els[1],
                             c=els[2]),
                      "How to read it: one tight cluster means one composition; a line "
                      "between corners means mixing."))
    story.append((_panel("pie", "Particle types", pie_mode="combinations", top_n=8),
                  "Check: which elements are detected depends on each element's detection "
                  "limit; small particles may lose their minor elements."))
    return story


def _network(s, ctx):
    els = ", ".join(s.elements)
    return [
        (_panel("network", "Correlated elements", isotopes=els, net_r_min=0.5),
         "What Insights found: these elements form one connected group of correlations."),
        (_panel("corr_matrix", "Correlation matrix", isotopes=els, corr_method="spearman",
                log_values=True),
         "How it was found: every pair was correlated; links are significant pairs with "
         "|ρ| of at least 0.5."),
        (_panel("cooccurrence", "How often they share particles", isotopes=els),
         "How to read it: elements that also share particles likely come from one source."),
        (_panel("combinations", "Most common combinations", top_n=12),
         "Check: links are pairwise; two elements in the group need not correlate directly."),
    ]


def _outlier(s, ctx):
    els = list(s.elements) or [str(s.config.get("highlight_element", ""))]
    el = els[0]
    story = [
        (_panel("strip", f"{el} in each particle", value=el, log_y=True,
                **_limit(ctx, "counts", el)),
         f"What Insights found: a few particles carry far more {el} than the rest."),
        (_histogram(ctx, "counts", el),
         "How it was found: on log values, particles far above the upper quartile."),
    ]
    if len(els) > 1:
        story.append((_panel("scatter", f"{els[0]} against {els[1]}", x=els[1], y=els[0],
                             log_x=True, log_y=True),
                      "How to read it: being extreme in two elements at once is unlikely to "
                      "be chance."))
    story.append((_panel("timeline", f"When large {el} particles arrive", time_mode="signal",
                         value=el, log_y=True),
                  "Check: two particles arriving together can look like one large particle."))
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

Each design returns ``(panel, caption)`` pairs in the order of the finding's
explanation: what Insights found, how it was found, how to read it, then the
checks. The captions become the figure's legend.
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

    The panels follow the finding's explanation in order: what Insights
    found, how it was found, how to read it, then the checks. A caption panel
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


def context_from(particles: list[dict], labels, thresholds: dict | None = None,
                 multi_sample: bool = False) -> FigureContext:
    """Work out what a figure can show from the particles it will draw.

    Args:
        particles: The particles of the finding's samples.
        labels: The isotopes the finding is about.
        thresholds: Isotope label to detection threshold in counts.
        multi_sample: Whether more than one sample is involved.

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
    return FigureContext(quantities or {"counts"}, dict(thresholds or {}), smallest, multi_sample)
