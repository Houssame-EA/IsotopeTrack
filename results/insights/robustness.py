"""How well each Insights finding holds up: effect, evidence, replicates, coincidence.

Detectors find patterns on the particles of a whole replicate group, where
thousands of particles make almost any trend significant. This module asks
the follow-up questions a reader would ask of a card:

* **Effect**: how large the pattern is, measured on the finding's particles.
* **Evidence**: the corrected significance the detector reported.
* **Reproducible**: whether the pattern is seen in each replicate on its own.
  The replicate, not the particle, is what was repeated, so a pattern carried
  by one replicate is flagged even when the pooled test is overwhelming.
* **Coincidence**: for two elements found in the same particles, how many such
  particles two particles arriving within one event would give by chance.

:func:`attach` stores the result on each finding as :class:`Evidence` and
lowers the ranking score of findings that do not hold in every replicate,
so the panel lists reproducible findings first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats as _stats

MIN_REPLICATE_PARTICLES = 25
"""Particles a replicate needs before its own check is run."""

MIN_REPLICATE_CORRELATION = 0.50
"""Rank correlation a replicate must reach, with the pooled sign, to pass."""

RATIO_TOLERANCE = 1.25
"""Largest factor between a replicate's median ratio and the pooled one."""

ISOTOPE_TOLERANCE = 0.03
"""Largest relative gap between a replicate's isotope ratio and the pooled one."""

COINCIDENCE_MIN_FOLD = 2.0
"""Co-detections must exceed chance coincidence by this factor to pass."""

PAIR_KEYS = {"correlation", "stoichiometry", "cooccurrence_with"}
"""Findings about two elements sharing particles, which coincidence can mimic."""


@dataclass
class ReplicateCheck:
    """One replicate's result for a finding.

    Attributes:
        label: Short replicate name shown on the card, such as ``"r2"``.
        ok: Whether the pattern holds in this replicate.
        value: The replicate's own number, such as ``"ρ +0.71"``.
    """

    label: str
    ok: bool
    value: str


@dataclass
class Evidence:
    """What the card's evidence strip shows.

    Attributes:
        effect: Size of the pattern, e.g. ``"ρ +0.61"`` or ``"3.3×"``.
        evidence: Corrected significance, e.g. ``"q = 3.1e-187"``; empty when
            the detector reported none.
        replicates: One check per replicate; empty when the finding's samples
            are not replicated.
        coincidence: ``(observed, expected)`` co-detections, or ``None``.
    """

    effect: str = ""
    evidence: str = ""
    replicates: list = field(default_factory=list)
    coincidence: tuple | None = None

    @property
    def n_ok(self) -> int:
        """Replicates where the pattern holds."""
        return sum(1 for c in self.replicates if c.ok)

    @property
    def reproducible(self) -> bool | None:
        """Whether every replicate passes, or ``None`` when none were checked."""
        if not self.replicates:
            return None
        return self.n_ok == len(self.replicates)

    @property
    def coincidence_fold(self) -> float | None:
        """Observed co-detections over those expected by chance."""
        if self.coincidence is None:
            return None
        observed, expected = self.coincidence
        return observed / max(expected, 1e-9)

    @property
    def failed(self) -> list:
        """The replicates where the pattern is not seen."""
        return [c for c in self.replicates if not c.ok]


def _short(member: str, group_name: str) -> str:
    """Replicate label without its group name, e.g. ``"r2"`` for ``"Influent_r2"``."""
    rest = member[len(group_name):] if member.startswith(group_name) else member
    return rest.strip("_- ") or member


def _replicate_units(ctx, s) -> list[tuple[object, list[tuple[str, int]]]]:
    """Replicated groups among a finding's samples, with each member's sample index.

    Returns:
        ``(group, [(member, index), ...])`` for every group holding two or more
        of the finding's samples.
    """
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    wanted = set(s.samples or ctx.sample_names)
    out = []
    for group in ctx.scope.groups:
        members = [(m, index[m]) for m in group.members if m in wanted and m in index]
        if len(members) >= 2:
            out.append((group, members))
    return out


def _labels(units) -> dict[str, str]:
    """Short card label for every replicate, prefixed by its group when several are shown."""
    several = len(units) > 1
    out = {}
    for group, members in units:
        for m, _i in members:
            short = _short(m, group.name)
            out[m] = f"{group.name[:3]} {short}" if several else short
    return out


def _scope_mask(ctx, s) -> np.ndarray:
    """Particles belonging to the finding's samples."""
    if not s.samples:
        return np.ones(ctx.n, dtype=bool)
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    keep = [index[m] for m in s.samples if m in index]
    return np.isin(ctx.sample_idx, keep)


def _detail(s, *names) -> str:
    """First detail value whose label matches one of *names*."""
    for label, value in s.details or ():
        if label in names:
            return str(value)
    return ""


def _evidence_text(s) -> str:
    """The corrected significance the detector wrote into its details."""
    for name in ("False discovery", "Fisher q", "q "):
        value = _detail(s, name)
        if value:
            value = value.strip()
            if value.startswith(("q", "<", "=", ">")):
                return value if value.startswith("q") else f"q {value}"
            return f"q = {value}"
    return ""


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    """Rank correlation of two arrays, or ``None`` when it cannot be computed."""
    if len(a) < MIN_REPLICATE_PARTICLES or np.std(a) == 0 or np.std(b) == 0:
        return None
    rho = _stats.spearmanr(a, b).statistic
    return float(rho) if np.isfinite(rho) else None


def _correlation(ctx, s, units, labels, mask) -> Evidence:
    """Rank correlation of the two elements in each replicate."""
    a, b = s.elements[0], s.elements[1]
    both = ctx.det_mask[a] & ctx.det_mask[b]
    pooled = _spearman(ctx.matrix[a][both & mask], ctx.matrix[b][both & mask])
    ev = Evidence(effect=f"ρ {pooled:+.2f}" if pooled is not None else "")
    sign = 1.0 if pooled is None or pooled >= 0 else -1.0
    for _group, members in units:
        for m, i in members:
            rows = both & (ctx.sample_idx == i)
            rho = _spearman(ctx.matrix[a][rows], ctx.matrix[b][rows])
            if rho is None:
                continue
            ok = rho * sign >= MIN_REPLICATE_CORRELATION
            ev.replicates.append(ReplicateCheck(labels[m], ok, f"ρ {rho:+.2f}"))
    return ev


def _stoichiometry(ctx, s, units, labels, mask) -> Evidence:
    """Median ratio of the two elements in each replicate, against the pooled one."""
    a, b = s.elements[0], s.elements[1]
    molar = "element_moles_fmol" in ctx.available_data_keys()
    matrix, det = ctx.matrix_for("element_moles_fmol" if molar else "elements")
    both = det[a] & det[b]
    rows = both & mask
    if rows.sum() < MIN_REPLICATE_PARTICLES:
        return Evidence()
    pooled = float(np.median(np.log10(matrix[a][rows] / matrix[b][rows])))
    ev = Evidence(effect=f"ratio {10 ** pooled:.3g}")
    limit = math.log10(RATIO_TOLERANCE)
    for _group, members in units:
        for m, i in members:
            sel = both & (ctx.sample_idx == i)
            if sel.sum() < MIN_REPLICATE_PARTICLES:
                continue
            med = float(np.median(np.log10(matrix[a][sel] / matrix[b][sel])))
            ev.replicates.append(ReplicateCheck(labels[m], abs(med - pooled) <= limit,
                                                f"{10 ** med:.3g}"))
    return ev


def _lift(ctx, rows, a, b) -> tuple[float, float, int] | None:
    """Co-detections of *a* and *b* in *rows*, against independence.

    Returns:
        ``(lift, expected, observed)``, or ``None`` with too few particles.
    """
    n = int(rows.sum())
    if n < MIN_REPLICATE_PARTICLES:
        return None
    na = int((ctx.det_mask[a] & rows).sum())
    nb = int((ctx.det_mask[b] & rows).sum())
    nab = int((ctx.det_mask[a] & ctx.det_mask[b] & rows).sum())
    expected = na * nb / n
    if expected <= 0:
        return None
    return nab / expected, expected, nab


def _cooccurrence(ctx, s, units, labels, mask) -> Evidence:
    """How much more, or less, often the two elements share particles in each replicate."""
    from results.insights import discovery as disc
    a, b = s.elements[0], s.elements[1]
    together = s.explain_key == "cooccurrence_with"
    pooled = _lift(ctx, mask, a, b)
    if pooled is None:
        effect = ""
    else:
        effect = f"{pooled[0]:.1f}× chance" if together else f"{pooled[0]:.2f}× chance"
    ev = Evidence(effect=effect)
    for _group, members in units:
        for m, i in members:
            found = _lift(ctx, ctx.sample_idx == i, a, b)
            if found is None:
                continue
            lift = found[0]
            ok = lift >= disc.COOCCURRENCE_MIN_LIFT if together else lift <= 2 * disc.COOCCURRENCE_AVOID_RATIO
            ev.replicates.append(ReplicateCheck(labels[m], ok, f"{lift:.1f}×"))
    return ev


def _separated(values: dict[str, float], groups: dict[str, list[str]], labels,
               fmt) -> tuple[list, str, str]:
    """Check that every replicate of the top group sits above every replicate of the bottom one.

    Args:
        values: Replicate name to its value.
        groups: Group name to its replicate names, among those in *values*.
        labels: Replicate name to card label.
        fmt: Callable writing a value for the card.

    Returns:
        ``(checks, top, bottom)``: one check per replicate of the two extreme
        groups, and the names of those groups.
    """
    centres = {g: float(np.median([values[m] for m in ms])) for g, ms in groups.items() if ms}
    if len(centres) < 2:
        return [], "", ""
    top = max(centres, key=centres.get)
    bottom = min(centres, key=centres.get)
    low_max = max(values[m] for m in groups[bottom])
    high_min = min(values[m] for m in groups[top])
    checks = [ReplicateCheck(labels[m], values[m] > low_max, fmt(values[m])) for m in groups[top]]
    checks += [ReplicateCheck(labels[m], values[m] < high_min, fmt(values[m]))
               for m in groups[bottom]]
    return checks, top, bottom


def _group_labels(ctx, s) -> tuple[dict, dict]:
    """Every compared sample's group, and card labels prefixed by group."""
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    wanted = set(s.samples or ctx.sample_names)
    groups, labels = {}, {}
    for group in ctx.scope.groups:
        members = [m for m in group.members if m in wanted and m in index]
        if members:
            groups[group.name] = members
            for m in members:
                labels[m] = f"{group.name[:3]} {_short(m, group.name)}"
    return groups, labels


def _comparison(ctx, s, units, labels, mask) -> Evidence:
    """Median signal in each replicate, checked for a clean gap between the groups."""
    el = s.elements[0]
    groups, labels = _group_labels(ctx, s)
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    values = {}
    for ms in groups.values():
        for m in ms:
            v = ctx.matrix[el][ctx.det_mask[el] & (ctx.sample_idx == index[m])]
            if len(v) >= 5:
                values[m] = float(np.median(v))
    groups = {g: [m for m in ms if m in values] for g, ms in groups.items()}
    if not all(len(ms) >= 2 for ms in groups.values() if ms):
        return Evidence(effect=_detail(s, "Fold difference in median"))
    checks, top, bottom = _separated(values, groups, labels, lambda v: f"{v:.3g}")
    fold = (np.median([values[m] for m in groups[top]])
            / max(np.median([values[m] for m in groups[bottom]]), 1e-12)) if top else 0
    return Evidence(effect=f"{fold:.2f}×" if fold else "", replicates=checks)


def _signature(ctx, s, units, labels, mask) -> Evidence:
    """Detection rate in each replicate, checked for a clean gap between the groups."""
    el = s.elements[0]
    groups, labels = _group_labels(ctx, s)
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    values = {}
    for ms in groups.values():
        for m in ms:
            rows = ctx.sample_idx == index[m]
            if rows.sum() >= MIN_REPLICATE_PARTICLES:
                values[m] = float(ctx.det_mask[el][rows].mean())
    groups = {g: [m for m in ms if m in values] for g, ms in groups.items()}
    if not all(len(ms) >= 2 for ms in groups.values() if ms):
        return Evidence()
    checks, top, bottom = _separated(values, groups, labels, lambda v: f"{v:.0%}")
    if not top:
        return Evidence()
    hi = np.median([values[m] for m in groups[top]])
    lo = np.median([values[m] for m in groups[bottom]])
    return Evidence(effect=f"{hi:.0%} vs {lo:.0%}", replicates=checks)


def _isotope(ctx, s, units, labels, mask) -> Evidence:
    """Median isotope ratio in each replicate, against the pooled one."""
    from results.insights import discovery as disc
    num, den = s.elements[0], s.elements[1]
    use, _ratios = disc.ratio_values(ctx, num, den)
    rows = use & mask
    if rows.sum() < MIN_REPLICATE_PARTICLES:
        return Evidence()
    pooled = float(np.median(ctx.matrix[num][rows] / ctx.matrix[den][rows]))
    natural = disc._natural_ratio(num, den)
    tail = f" (natural {natural:.4g})" if natural else ""
    ev = Evidence(effect=f"{pooled:.4g}{tail}")
    medians = []
    for _group, members in units:
        for m, i in members:
            sel = use & (ctx.sample_idx == i)
            if sel.sum() < MIN_REPLICATE_PARTICLES:
                continue
            med = float(np.median(ctx.matrix[num][sel] / ctx.matrix[den][sel]))
            medians.append(med)
            ok = abs(med - pooled) / pooled <= ISOTOPE_TOLERANCE
            ev.replicates.append(ReplicateCheck(labels[m], ok, f"{med:.4g}"))
    if len(medians) >= 2:
        ev.effect = f"{min(medians):.4g}–{max(medians):.4g}{tail}"
    return ev


def _isotope_groups(ctx, s, units, labels, mask) -> Evidence:
    """Median isotope ratio in each replicate, checked for a clean gap between the groups."""
    from results.insights import discovery as disc
    num, den = s.elements[0], s.elements[1]
    use, _ratios = disc.ratio_values(ctx, num, den)
    groups, labels = _group_labels(ctx, s)
    index = {name: i for i, name in enumerate(ctx.sample_names)}
    values = {}
    for ms in groups.values():
        for m in ms:
            sel = use & (ctx.sample_idx == index[m])
            if sel.sum() >= MIN_REPLICATE_PARTICLES:
                values[m] = float(np.median(ctx.matrix[num][sel] / ctx.matrix[den][sel]))
    groups = {g: [m for m in ms if m in values] for g, ms in groups.items()}
    if not all(len(ms) >= 2 for ms in groups.values() if ms):
        return Evidence(effect=_detail(s, "Difference"))
    checks, top, bottom = _separated(values, groups, labels, lambda v: f"{v:.4g}")
    if not top:
        return Evidence()
    hi = np.median([values[m] for m in groups[top]])
    lo = np.median([values[m] for m in groups[bottom]])
    return Evidence(effect=f"{hi:.4g} vs {lo:.4g}", replicates=checks)


def _ratio_split(ctx, s, units, labels, mask) -> Evidence:
    """The two populations' ratios in each replicate, checked for the same split."""
    from results.insights import discovery as disc
    a, b, c = s.elements[0], s.elements[1], s.elements[2]
    co = ctx.det_mask[a] & ctx.det_mask[b]
    lr = np.full(ctx.n, np.nan)
    lr[co] = np.log10(ctx.matrix[a][co] / ctx.matrix[b][co])
    has_c = ctx.det_mask[c]

    def medians(rows):
        w, wo = rows & co & has_c, rows & co & ~has_c
        if min(int(w.sum()), int(wo.sum())) < 10:
            return None
        return 10 ** float(np.median(lr[w])), 10 ** float(np.median(lr[wo]))

    pooled = medians(mask)
    if pooled is None:
        return Evidence()
    r_w, r_wo = pooled
    ev = Evidence(effect=f"{r_wo:.3g} vs {r_w:.3g}")
    for _group, members in units:
        for m, i in members:
            found = medians(ctx.sample_idx == i)
            if found is None:
                continue
            w, wo = found
            fold = max(w, wo) / max(min(w, wo), 1e-12)
            ok = (wo > w) == (r_wo > r_w) and fold >= disc.RATIO_SPLIT_MIN_FOLD
            ev.replicates.append(ReplicateCheck(labels[m], ok, f"{wo:.3g}/{w:.3g}"))
    return ev


ASSESSORS = {
    "correlation": _correlation,
    "stoichiometry": _stoichiometry,
    "cooccurrence_with": _cooccurrence,
    "cooccurrence_avoid": _cooccurrence,
    "comparison": _comparison,
    "signature": _signature,
    "isotope": _isotope,
    "isotope_abundance": _isotope,
    "isotope_two": _isotope,
    "isotope_groups": _isotope_groups,
    "ratio_split": _ratio_split,
}
"""Explain key to the function measuring that kind of finding."""

ELEMENTS_NEEDED = {
    "correlation": 2, "stoichiometry": 2, "cooccurrence_with": 2, "cooccurrence_avoid": 2,
    "comparison": 1, "signature": 1, "isotope": 2, "isotope_abundance": 2, "isotope_two": 2,
    "isotope_groups": 2, "ratio_split": 3,
}
"""How many elements each kind of finding must name to be measured."""


def _times(ctx) -> tuple[np.ndarray, np.ndarray]:
    """Arrival time and event duration of every particle, cached on the context."""
    found = ctx.cache.get("robustness_times")
    if found is None:
        starts = np.array([_num(p.get("start_time")) for p in ctx.particles])
        ends = np.array([_num(p.get("end_time")) for p in ctx.particles])
        duration = np.where(np.isfinite(ends) & (ends >= starts), ends - starts, np.nan)
        found = (starts, duration)
        ctx.cache["robustness_times"] = found
    return found


def _num(x) -> float:
    """A float, or NaN for anything that is not a number."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def coincidence(ctx, a: str, b: str, mask: np.ndarray) -> tuple[int, float] | None:
    """Co-detections of two elements against those chance coincidence would give.

    With particles arriving at random, an *a* particle meets a *b* particle
    within one event with probability ``1 − exp(−λ_b (τ_a + τ_b))``, where λ_b
    is the rate of *b* particles and τ the median event duration, worked out
    sample by sample (see :func:`results.insights.evidence.coincidence`).

    Returns:
        ``(observed, expected)``, or ``None`` when the particles carry no times.
    """
    starts, duration = _times(ctx)
    if not np.isfinite(starts[mask]).any():
        return None
    da, db = ctx.det_mask[a], ctx.det_mask[b]
    observed = int((da & db & mask).sum())
    expected = 0.0
    for i in np.unique(ctx.sample_idx[mask]):
        rows = mask & (ctx.sample_idx == i)
        t = starts[rows]
        t = t[np.isfinite(t)]
        if t.size < 2:
            continue
        span = float(t.max() - t.min())
        if span <= 0:
            continue
        has_a, has_b = rows & da, rows & db
        if not has_a.any() or not has_b.any():
            continue
        tau_a = np.nanmedian(duration[has_a])
        tau_b = np.nanmedian(duration[has_b])
        if not (np.isfinite(tau_a) and np.isfinite(tau_b)):
            continue
        rate_b = float(has_b.sum()) / span
        expected += float(has_a.sum()) * (1 - math.exp(-rate_b * (tau_a + tau_b)))
    return observed, expected


def assess(ctx, s) -> Evidence | None:
    """Measure how well one finding holds up.

    Args:
        ctx: Context over the whole scope.
        s: The finding (:class:`~results.insights.engine.Suggestion`).

    Returns:
        The finding's :class:`Evidence`, or ``None`` for kinds of finding this
        module does not measure.
    """
    key = s.explain_key or s.category
    fn = ASSESSORS.get(key)
    if fn is None or len(s.elements) < ELEMENTS_NEEDED[key]:
        return None
    if any(el not in ctx.matrix for el in s.elements[:ELEMENTS_NEEDED[key]]):
        return None
    units = _replicate_units(ctx, s)
    mask = _scope_mask(ctx, s)
    ev = fn(ctx, s, units, _labels(units), mask)
    ev.evidence = ev.evidence or _evidence_text(s)
    if key in PAIR_KEYS:
        ev.coincidence = coincidence(ctx, s.elements[0], s.elements[1], mask)
    return ev


def rank_weight(ev: Evidence | None) -> float:
    """Factor applied to a finding's ranking score from its evidence.

    A finding seen in every replicate keeps its score; one seen in only some
    loses it with the square of the share that fail, so a pattern carried by
    one replicate of three drops well down the list. Pairs that chance
    coincidence explains are pushed to the bottom.
    """
    if ev is None:
        return 1.0
    weight = 1.0
    if ev.replicates:
        weight *= (ev.n_ok / len(ev.replicates)) ** 2
    fold = ev.coincidence_fold
    if fold is not None and fold < COINCIDENCE_MIN_FOLD:
        weight *= 0.2
    return weight


def attach(ctx, suggestions: list) -> list:
    """Store each finding's evidence on it and re-weight its ranking score.

    Args:
        ctx: Context over the whole scope.
        suggestions: Findings from one detector.

    Returns:
        The same findings, each with :attr:`evidence` set where it applies.
    """
    for s in suggestions:
        if getattr(s, "evidence", None) is not None:
            continue
        try:
            ev = assess(ctx, s)
        except Exception:
            import logging
            logging.getLogger("IsotopeTrack.results.insights").exception(
                "[Insights] could not check how %s holds up", s.title)
            ev = None
        if ev is None:
            continue
        s.evidence = ev
        s.confidence = s.confidence * rank_weight(ev)
    return suggestions
