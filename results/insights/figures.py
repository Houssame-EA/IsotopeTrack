"""Four-panel figures that explain a finding.

Besides the single plot a card proposes, every finding can be opened as a
Figure Builder figure with panels a to d, chosen to show the evidence behind
it. Wherever it helps, the panels show the element in counts, mass and size,
with the detection threshold marked on count axes and the smallest detected
particle marked on mass and size axes, so it is plain how much of a pattern
sits near the detection limit.

:func:`figure_for` builds the design; the panel adds it to the canvas as a
Figure Builder node fed by a selector holding the finding's samples.
"""

from __future__ import annotations

from dataclasses import dataclass, field

QUANTITY_NAMES = {"counts": "counts", "mass": "mass (fg)", "d": "size (nm)"}
"""Readable names for the quantities a panel can show."""

GRID = ([0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 0.5, 0.5], [0.0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5])
"""Rectangles of panels a, b, c and d."""

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


def _interference(s, ctx):
    parent, child = s.elements[0], s.elements[1]
    return [
        _panel("scatter", f"{child} against {parent}", x=parent, y=child, log_x=True,
               log_y=True, show_fit=True, show_r=True),
        _panel("histogram", f"{child}/{parent} in each particle", value=f"{child} / {parent}",
               bins=40, x_label=f"{child}/{parent}"),
        _panel("histogram", f"{parent} with and without {child}", value=parent, log_x=True,
               bins=40, x_label=f"{parent} counts", **_with_without(parent, child)),
        _histogram(ctx, "counts", child, f"{child} counts and detection threshold"),
    ]


def _isotope_pair(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    lines = {"vlines": f"{natural:.6g}"} if natural else {}
    hlines = {"hlines": f"{natural:.6g}"} if natural else {}
    panels = [
        _panel("scatter", f"{num} against {den}", x=den, y=num, log_x=True, log_y=True,
               natural_line=bool(natural), poisson_band=2.0, **_by_sample(ctx)),
        _panel("histogram", f"{num}/{den} in each particle", value=ratio, bins=50,
               x_label=f"{num}/{den}", **lines, **_by_sample(ctx)),
        _panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
               x_label=f"{den} counts", y_label=f"{num}/{den}", **hlines),
    ]
    if ctx.multi_sample:
        panels.append(_panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
                             y_label=f"{num}/{den}", **hlines))
    else:
        panels.append(_histogram(ctx, "counts", den, f"{den} counts and detection threshold"))
    return panels


def _isotope_track(s, ctx, natural=None):
    num, den, other = s.elements[0], s.elements[1], s.elements[2]
    ratio = f"{num} / {den}"
    hlines = {"hlines": f"{natural:.6g}"} if natural else {}
    return [
        _panel("scatter", f"{num}/{den} against {other}", x=other, y=ratio, log_x=True,
               trend="median", x_label=f"{other} counts", y_label=f"{num}/{den}", **hlines),
        _panel("box", f"{num}/{den} with and without {other}", value=ratio,
               y_label=f"{num}/{den}", **_with_without(num, other), **hlines),
        _panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
               x_label=f"{den} counts", y_label=f"{num}/{den}", **hlines),
        _histogram(ctx, "counts", other, f"{other} counts and detection threshold"),
    ]


def _isotope_groups(s, ctx, natural=None):
    num, den = s.elements[0], s.elements[1]
    ratio = f"{num} / {den}"
    hlines = {"hlines": f"{natural:.6g}"} if natural else {}
    return [
        _panel("box", f"{num}/{den} by sample", value=ratio, group_by="sample",
               y_label=f"{num}/{den}", show_points=False, **hlines),
        _panel("ecdf", f"{num}/{den} distribution by sample", value=ratio, group_by="sample",
               x_label=f"{num}/{den}"),
        _panel("scatter", "Ratio against signal", x=den, y=ratio, log_x=True, trend="median",
               group_by="sample", x_label=f"{den} counts", y_label=f"{num}/{den}"),
        _histogram(ctx, "counts", den, f"{den} counts and detection threshold"),
    ]


def _comparison(s, ctx):
    el = s.elements[0]
    panels = [
        _panel("box", f"{el} counts by sample", value=el, group_by="sample", log_y=True,
               **_limit(ctx, "counts", el)),
        _panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
               group_by="sample", y_label="Share of particles", error="none"),
    ]
    for prefix in ("mass", "d"):
        if prefix in ctx.quantities:
            panels.append(_panel("box", f"{el} {QUANTITY_NAMES[prefix]} by sample",
                                 value=_expr(prefix, el), group_by="sample", log_y=True,
                                 **_limit(ctx, prefix, el)))
    panels.append(_histogram(ctx, "counts", el, f"{el} counts by sample", group_by="sample"))
    return panels[:4]


def _replicates(s, ctx):
    el = s.elements[0] if s.elements else ""
    panels = [
        _panel("timeline", "Particles arriving over the run", time_mode="cumulative",
               group_by="sample"),
    ]
    if el:
        panels += [
            _panel("box", f"{el} counts by replicate", value=el, group_by="sample", log_y=True,
                   **_limit(ctx, "counts", el)),
            _panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
                   group_by="sample", y_label="Share of particles", error="none"),
            _histogram(ctx, "counts", el, f"{el} counts by replicate", group_by="sample"),
        ]
    else:
        panels += [_panel("timeline", "Particle rate over the run", time_mode="rate",
                          group_by="sample")]
    return panels


def _signature(s, ctx):
    el = s.elements[0]
    panels = [
        _panel("bar", f"Share of particles with {el}", value=f"{el} > 0", agg="mean",
               group_by="sample", y_label="Share of particles", error="none"),
        _panel("combinations", "Most common element combinations", top_n=12,
               group_by="sample"),
    ]
    panels += _quantity_panels(ctx, el)[:2]
    return panels


def _stoichiometry(s, ctx):
    a, b = s.elements[0], s.elements[1]
    prefix = "moles" if "moles" in ctx.quantities else "counts"
    ratio = f"{_expr(prefix, a)} / {_expr(prefix, b)}"
    total = f"{_expr(prefix, a)} + {_expr(prefix, b)}"
    unit = "moles" if prefix == "moles" else "counts"
    return [
        _panel("scatter", f"{a} against {b} ({unit})", x=_expr(prefix, b), y=_expr(prefix, a),
               log_x=True, log_y=True, show_fit=True, show_r=True),
        _panel("histogram", f"{a}/{b} in each particle", value=ratio, log_x=True, bins=40,
               x_label=f"{a}/{b} ({unit})"),
        _panel("scatter", "Ratio against particle amount", x=total, y=ratio, log_x=True,
               log_y=True, trend="median", x_label=f"{a} + {b} ({unit})",
               y_label=f"{a}/{b}"),
        _histogram(ctx, "d" if "d" in ctx.quantities else "counts", a),
    ]


def _correlation(s, ctx):
    a, b = s.elements[0], s.elements[1]
    return [
        _panel("scatter", f"{a} against {b}", x=b, y=a, log_x=True, log_y=True, show_fit=True,
               show_r=True, **_by_sample(ctx)),
        _panel("hexbin", "Where most particles sit", x=b, y=a, log_x=True, log_y=True),
        _panel("histogram", f"{a}/{b} in each particle", value=f"{a} / {b}", log_x=True,
               bins=40),
        _panel("scatter", "Ratio against particle size", x=f"{a} + {b}", y=f"{a} / {b}",
               log_x=True, log_y=True, trend="median", x_label=f"{a} + {b} counts",
               y_label=f"{a}/{b}"),
    ]


def _cooccurrence(s, ctx):
    rare, common = s.elements[0], s.elements[1]
    return [
        _panel("cooccurrence", "How often elements share particles", cooc_mode="conditional"),
        _panel("combinations", f"Combinations in particles with {rare}", top_n=12,
               filter=f"{rare} > 0"),
        _panel("histogram", f"{rare} with and without {common}", value=rare, log_x=True,
               bins=40, **_with_without(rare, common)),
        _histogram(ctx, "counts", rare, f"{rare} counts and detection threshold"),
    ]


def _rare(s, ctx):
    el = s.elements[0]
    panels = [
        _panel("combinations", f"Particles with {el}", top_n=12, filter=f"{el} > 0"),
        _panel("strip", f"{el} in each particle", value=el, log_y=True,
               **_limit(ctx, "counts", el)),
        _panel("timeline", f"When {el} particles arrive", time_mode="signal", value=el,
               log_y=True, filter=f"{el} > 0"),
    ]
    if len(s.elements) > 1:
        panels.append(_panel("scatter", f"{el} against {s.elements[1]}", x=s.elements[1], y=el,
                             log_x=True, log_y=True, filter=f"{el} > 0"))
    else:
        panels.append(_histogram(ctx, "counts", el))
    return panels


def _distribution(s, ctx):
    el = s.elements[0]
    panels = _quantity_panels(ctx, el)
    panels.append(_panel("ecdf", f"{el} cumulative distribution", value=el, log_x=True,
                         **_by_sample(ctx), **_limit(ctx, "counts", el)))
    if len(panels) < 4:
        panels.append(_panel("strip", f"{el} in each particle", value=el, log_y=True,
                             **_by_sample(ctx)))
    return panels[:4]


def _size_trend(s, ctx):
    figure_panels = s.config.get("panels") or []
    y = figure_panels[0].get("y", "") if figure_panels else ""
    el = y.split(":", 1)[-1].split("/")[0].strip() if y else ""
    panels = [
        _panel("scatter", f"{el} share against particle mass", x="total", y=y, log_x=True,
               trend="median", filter="n_elements >= 2", x_label="Particle mass (fg)",
               y_label=f"{el} mass fraction"),
        _panel("histogram", "Particle mass", value="total", log_x=True, bins=40,
               x_label="Particle mass (fg)"),
        _panel("histogram", f"{el} mass fraction", value=y, bins=40, filter="n_elements >= 2",
               x_label=f"{el} mass fraction"),
    ]
    if el:
        panels.append(_histogram(ctx, "mass" if "mass" in ctx.quantities else "counts", el))
    return panels


def _time(s, ctx):
    lead = ""
    for p in s.config.get("panels") or []:
        lead = p.get("value") or lead
    panels = [
        _panel("timeline", "Particle rate over the run", time_mode="rate"),
        _panel("timeline", "Particles arriving over the run", time_mode="cumulative"),
    ]
    if lead:
        panels += [
            _panel("timeline", f"{lead} signal over the run", time_mode="signal", value=lead,
                   log_y=True),
            _histogram(ctx, "counts", lead, f"{lead} counts and detection threshold"),
        ]
    return panels


def _composition(s, ctx):
    els = list(s.elements)
    panels = [
        _panel("combinations", "Most common element combinations", top_n=12, **_by_sample(ctx)),
        _panel("composition", "Average composition", **({"isotopes": ", ".join(els)} if els else {})),
        _panel("cooccurrence", "How often elements share particles", cooc_mode="joint",
               **({"isotopes": ", ".join(els)} if els else {})),
    ]
    if len(els) == 3:
        panels.append(_panel("ternary", f"{els[0]}–{els[1]}–{els[2]}", a=els[0], b=els[1],
                             c=els[2]))
    else:
        panels.append(_panel("pie", "Particle types", pie_mode="combinations", top_n=8))
    return panels


def _network(s, ctx):
    els = ", ".join(s.elements)
    return [
        _panel("network", "Correlated elements", isotopes=els, net_r_min=0.5),
        _panel("corr_matrix", "Correlation matrix", isotopes=els, corr_method="spearman",
               log_values=True),
        _panel("cooccurrence", "How often they share particles", isotopes=els),
        _panel("combinations", "Most common combinations", top_n=12),
    ]


def _outlier(s, ctx):
    els = list(s.elements) or [str(s.config.get("highlight_element", ""))]
    el = els[0]
    panels = [
        _panel("strip", f"{el} in each particle", value=el, log_y=True,
               **_limit(ctx, "counts", el)),
        _histogram(ctx, "counts", el),
        _panel("timeline", f"When large {el} particles arrive", time_mode="signal", value=el,
               log_y=True),
    ]
    if len(els) > 1:
        panels.append(_panel("scatter", f"{els[0]} against {els[1]}", x=els[1], y=els[0],
                             log_x=True, log_y=True))
    else:
        panels.append(_panel("combinations", f"Combinations with {el}", top_n=12,
                             filter=f"{el} > 0"))
    return panels


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
"""Panel designs keyed by a finding's explain key."""

ISOTOPE_DESIGNS = {_isotope_pair, _isotope_track, _isotope_groups}


def _needs_elements(s) -> bool:
    """Whether the design for *s* needs the elements it names to exist."""
    return bool(s.elements)


def figure_for(s, ctx: FigureContext) -> dict | None:
    """Build the four-panel figure explaining a finding.

    Args:
        s: The finding (:class:`~results.insights.engine.Suggestion`).
        ctx: What the data offers the figure.

    Returns:
        A full Figure Builder spec with panels a to d, or ``None`` when the
        finding has no design or lacks the elements its design needs.
    """
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec

    key = s.explain_key or s.category
    design = DESIGNS.get(key) or DESIGNS.get(s.category)
    if design is None:
        return None
    if design is _correlation and len(s.elements) < 2:
        design = _composition
    elif design not in (_composition, _time, _size_trend, _network) and not _needs_elements(s):
        return None
    try:
        if design in ISOTOPE_DESIGNS:
            from results.figure_builder.core.isotopes import natural_ratio
            panels = design(s, ctx, natural_ratio(s.elements[0], s.elements[1]))
        else:
            panels = design(s, ctx)
    except (IndexError, KeyError):
        return None
    panels = [p for p in panels if p][:4]
    if not panels:
        return None
    spec = default_spec()
    spec["figure"].update({"width": 11.0, "height": 8.5, "panel_letters": True})
    spec["data_type"] = "Counts"
    spec["panels"] = [make_panel(rect=list(GRID[i]), **p) for i, p in enumerate(panels)]
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
