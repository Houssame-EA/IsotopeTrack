"""Detectors that search particle data for findings worth a plot node.

Each detector takes an :class:`~results.insights.engine.AnalysisContext` and
returns :class:`~results.insights.engine.Suggestion` cards. Detectors that look
*inside* a material (interferences, stoichiometry, co-occurrence, rare
particles, composition shape) are run once per replicate group by the engine
in :mod:`results.insights.engine`; detectors that look *across* samples handle
the groups themselves.

The statistics favour being quiet over being wrong. Every detector applies an
effect-size floor on top of any significance test, families of tests are
corrected for false discovery, and replicate groups are compared as groups so
that two replicates of one material are never reported as different samples.
"""

from __future__ import annotations

import json
import math
import re
from fractions import Fraction

import numpy as np
from scipy import stats as _stats

MIN_GROUP_PARTICLES = 20
"""Particles a sample needs before it counts as a replicate in a comparison."""

INTERFERENCE_MIN_OVERLAP = 15
"""Particles that must carry both masses before an interference is considered."""

INTERFERENCE_MIN_SHARE = 0.70
"""Share of the suspect mass's detections that must arrive with its parent."""

INTERFERENCE_MAX_RATIO = 0.20
"""Largest suspect-to-parent signal ratio still typical of an oxide or M²⁺."""

INTERFERENCE_MAX_SPREAD = 0.30
"""Largest robust spread of the log10 ratio for a ratio to count as constant."""

STOICHIOMETRY_MIN_OVERLAP = 30
"""Particles carrying both elements before their ratio is judged."""

STOICHIOMETRY_MAX_SPREAD = 0.20
"""Largest robust spread of the log10 ratio, about a factor of 1.6."""

STOICHIOMETRY_MAX_COUPLING = 0.40
"""Ratio spread as a share of the spread expected if the elements were independent."""

COOCCURRENCE_MIN_CONFIDENCE = 0.80
"""Share of the rarer element's particles that must also carry the other."""

COOCCURRENCE_MIN_LIFT = 1.5
"""How much more often than chance two elements must appear together."""

COOCCURRENCE_AVOID_RATIO = 0.25
"""Observed-to-expected ratio below which two elements are said to avoid each other."""

RARE_MAX_COUNT = 25
"""Most particles an element can appear in and still be reported as a rare find."""

RARE_MIN_COUNT = 3
"""Fewest particles needed before a rare element is worth a card."""

DETECTION_LIMIT_MIN_SHARE = 0.15
"""Share of particles in the lowest 5 % of the log range that signals a cut-off."""

SIZE_TREND_MIN_RHO = 0.30
"""Rank correlation between composition and size needed for a size trend card."""

TIME_MIN_PARTICLES = 200
"""Particles a sample needs before its acquisition is checked over time."""

TIME_DRIFT_MIN_FOLD = 1.25
"""Signal change from start to end of a run that counts as drift."""

REPLICATE_FOLD = 1.5
"""Fold difference between replicates that counts as a disagreement."""

REPLICATE_RATE_GAP = 0.15
"""Detection-rate gap between replicates that counts as a disagreement."""

REPLICATE_MARGIN = 2.0
"""How many times the replicate spread a group difference must exceed."""

_SUPERSCRIPT_PLUS = "⁺"
_SUPERSCRIPT_TWO_PLUS = "²⁺"


def _rr():
    """Return :mod:`results.insights.engine`, imported on first use.

    The engine module imports this one, so importing it back at module level
    would be circular.
    """
    from results.insights import engine
    return engine


def mass_symbol(label: str) -> tuple[int | None, str | None]:
    """Split an isotope label into mass number and symbol.

    Accepts ``"56Fe"`` and ``"Fe56"``.

    Args:
        label: Isotope label.

    Returns:
        ``(mass, symbol)``, or ``(None, None)`` for a label without a mass.
    """
    text = str(label).strip()
    m = re.match(r"^(\d+)([A-Za-z]{1,3})$", text) or re.match(r"^([A-Za-z]{1,3})(\d+)$", text)
    if not m:
        return None, None
    a, b = m.groups()
    if a.isdigit():
        return int(a), b
    return int(b), a


def same_element(a: str, b: str) -> bool:
    """Return whether two labels are isotopes of one element.

    Isotopes of one element always rise and fall together, so a pair like
    ²⁰⁶Pb and ²⁰⁸Pb is never reported as a correlation, a co-occurrence or a
    fixed ratio. It is an isotope ratio, handled by
    :func:`analyse_isotope_ratios`.
    """
    sa, sb = mass_symbol(a)[1], mass_symbol(b)[1]
    return sa is not None and sa == sb


_same_symbol = same_element


def mass_related(a: str, b: str) -> bool:
    """Return whether two masses could be an oxide, hydroxide or M²⁺ of each other.

    Pairs related this way are left to the interference detector, so they are
    not reported a second time as a fixed ratio or a co-occurrence.
    """
    ma, mb = mass_symbol(a)[0], mass_symbol(b)[0]
    if not ma or not mb:
        return False
    return abs(ma - mb) in (16, 17) or ma == 2 * mb or mb == 2 * ma


def _robust_sd(values: np.ndarray) -> float:
    """Spread of *values* from the median absolute deviation, scaled to a standard deviation."""
    if len(values) == 0:
        return 0.0
    med = float(np.median(values))
    return 1.4826 * float(np.median(np.abs(values - med)))


def _config_key(config: dict) -> str:
    """Stable text form of a node config, used to tell findings apart."""
    try:
        return json.dumps(config, sort_keys=True, default=str)
    except Exception:
        return repr(sorted(config.items()))


def _n_elements(ctx) -> np.ndarray:
    """Number of elements detected in each particle, cached on the context."""
    cached = ctx.cache.get("n_elements")
    if cached is None:
        cached = np.zeros(ctx.n, dtype=np.int32)
        for mask in ctx.det_mask.values():
            cached += mask
        ctx.cache["n_elements"] = cached
    return cached


def _times(ctx) -> np.ndarray:
    """Particle start times in seconds, ``nan`` where missing, cached on the context."""
    cached = ctx.cache.get("start_time")
    if cached is None:
        cached = np.full(ctx.n, np.nan)
        for i, p in enumerate(ctx.particles):
            try:
                cached[i] = float(p.get("start_time"))
            except (TypeError, ValueError):
                continue
        ctx.cache["start_time"] = cached
    return cached


def _figure_spec(data_type: str, **panel) -> dict:
    """Build a one-panel Figure Builder design.

    Args:
        data_type: Default quantity of the figure, e.g. ``"Counts"``.
        **panel: Panel settings overriding the defaults.

    Returns:
        A full, normalised Figure Builder spec.
    """
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    spec = default_spec()
    spec["data_type"] = data_type
    spec["panels"] = [make_panel(rect=[0.0, 0.0, 1.0, 1.0], **panel)]
    return normalise_spec(spec)


def _simple_ratio(value: float, max_term: int = 4, tolerance: float = 0.08) -> str | None:
    """Name the small whole-number ratio closest to *value*, if one is close.

    Args:
        value: A molar ratio, at least 1.
        max_term: Largest numerator or denominator to consider.
        tolerance: Relative distance accepted.

    Returns:
        Text such as ``"2:1"``, or ``None``.
    """
    if not (0.2 <= value <= 5.0):
        return None
    frac = Fraction(value).limit_denominator(max_term)
    if frac.numerator > max_term or frac.numerator == 0:
        return None
    if abs(float(frac) - value) / value > tolerance:
        return None
    return f"{frac.numerator}:{frac.denominator}"


def analyse_interference(ctx, progress=None) -> list:
    """Find masses that behave like an oxide, hydroxide or doubly charged ion.

    For each measured mass *m*, the masses *m + 16*, *m + 17* and *m / 2* are
    checked. A suspect mass is flagged when almost all of its detections
    arrive in the same particles as the parent, at a small and nearly constant
    ratio that scales one-to-one with the parent. A genuine second element
    would vary independently and would also turn up without the parent.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to three correlation-plot suggestions, parent on x and suspect on y.
    """
    rr = _rr()
    rr._say(progress, "Checking for oxide and doubly charged interferences…")
    floor = max(10, int(0.002 * ctx.n))
    labels = [el for el in ctx.elements_by_abundance() if ctx.det_counts[el] >= floor]
    parsed = {el: mass_symbol(el) for el in labels}
    by_mass: dict[int, list[str]] = {}
    for el, (mass, _sym) in parsed.items():
        if mass:
            by_mass.setdefault(mass, []).append(el)

    found = []
    for parent in labels:
        mass, symbol = parsed[parent]
        if not mass:
            continue
        targets = [(mass + 16, "oxide", f"{symbol}O{_SUPERSCRIPT_PLUS}"),
                   (mass + 17, "hydroxide", f"{symbol}OH{_SUPERSCRIPT_PLUS}")]
        if mass % 2 == 0:
            targets.append((mass // 2, "doubly charged ion", f"{symbol}{_SUPERSCRIPT_TWO_PLUS}"))
        for target_mass, kind, species in targets:
            for child in by_mass.get(target_mass, []):
                if child == parent or parsed[child][1] == symbol:
                    continue
                stats = _interference_stats(ctx, parent, child)
                if stats is not None:
                    found.append((parent, child, kind, species, stats))

    out = []
    found.sort(key=lambda f: -f[4]["score"])
    seen_children: set[str] = set()
    for parent, child, kind, species, st in found:
        if child in seen_children or len(out) >= 3:
            continue
        seen_children.add(child)
        slope = f", slope {st['slope']:.2f} on log axes" if st["slope"] is not None else ""
        out.append(rr.Suggestion(
            title=f"{child} looks like {species} from {parent}",
            reasoning=(
                f"{st['share']:.0%} of {child} detections ({st['n']:,} particles) arrive with "
                f"{parent}, at a near-constant {child}/{parent} of {st['ratio'] * 100:.2g}% "
                f"(spread ×{10 ** st['spread']:.2f}{slope}). That is the pattern of "
                f"{'an' if kind[0] in 'aeiou' else 'a'} {kind} "
                f"interference rather than a second element, so {child} in these particles "
                "should be treated with caution."
            ),
            category="interference",
            confidence=min(st["score"], 0.95),
            explain_key="interference",
            details=[("Suspect mass", child), ("Parent", parent), ("Likely species", species),
                     ("Particles with both", f"{st['n']:,}"),
                     ("Share of suspect detections with parent", f"{st['share']:.0%}"),
                     ("Median suspect/parent", f"{st['ratio'] * 100:.3g} %"),
                     ("Spread of the ratio", f"×{10 ** st['spread']:.2f}"),
                     ("Slope on log axes", "n/a" if st["slope"] is None else f"{st['slope']:.2f}")],
            node_type="correlation_plot",
            config={"x_element": parent, "y_element": child, "log_x": True, "log_y": True},
            elements=(parent, child),
        ))
    return out


def interference_pair(ctx, a: str, b: str) -> bool:
    """Return whether one of two masses behaves like an interference from the other.

    Args:
        ctx: Analysis context.
        a: One isotope label.
        b: The other.

    Returns:
        True when the heavier mass sits at +16 or +17, or the lighter at half
        the mass, and passes every test in :func:`analyse_interference`.
    """
    ma, mb = mass_symbol(a)[0], mass_symbol(b)[0]
    if not ma or not mb or not mass_related(a, b):
        return False
    if mb - ma in (16, 17) or ma == 2 * mb:
        parent, child = a, b
    else:
        parent, child = b, a
    return _interference_stats(ctx, parent, child) is not None


def _interference_stats(ctx, parent: str, child: str) -> dict | None:
    """Measure how much *child* behaves like an interference from *parent*.

    Returns:
        A dict with ``n``, ``share``, ``ratio``, ``spread``, ``slope`` and
        ``score``, or ``None`` when the pair fails any of the tests.
    """
    det_p, det_c = ctx.det_mask[parent], ctx.det_mask[child]
    co = det_p & det_c
    n_co = int(co.sum())
    n_child = int(det_c.sum())
    if n_co < INTERFERENCE_MIN_OVERLAP or n_child == 0:
        return None
    share = n_co / n_child
    if share < INTERFERENCE_MIN_SHARE:
        return None

    a = np.log10(ctx.matrix[parent][co])
    b = np.log10(ctx.matrix[child][co])
    lr = b - a
    med = float(np.median(lr))
    ratio = 10 ** med
    spread = _robust_sd(lr)
    if ratio > INTERFERENCE_MAX_RATIO or spread > INTERFERENCE_MAX_SPREAD:
        return None

    slope = None
    if a.std() >= 0.1:
        slope = float(np.polyfit(a, b, 1)[0])
        if not (0.6 <= slope <= 1.4):
            return None
        rho = _stats.spearmanr(a, b)[0]
        if not np.isfinite(rho) or rho < 0.5:
            return None

    score = 0.55 + 0.35 * share * (1.0 - 0.5 * min(spread / INTERFERENCE_MAX_SPREAD, 1.0))
    return {"n": n_co, "share": share, "ratio": ratio, "spread": spread,
            "slope": slope, "score": score}


def analyse_stoichiometry(ctx, progress=None) -> list:
    """Find element pairs held at a fixed ratio, the mark of one defined phase.

    Two elements in the same particles always correlate to some degree, simply
    because bigger particles hold more of everything. What sets a single phase
    apart is that the *ratio* stays put while the amounts vary. The robust
    spread of the log ratio is compared with the spread expected if the two
    elements varied independently, and only pairs far tighter than that are
    reported.

    Molar amounts are used when the data has been calibrated, so the ratio can
    be read as a formula; otherwise raw counts are used and the card says so.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to three suggestions, as molar ratio plots when moles are available.
    """
    rr = _rr()
    rr._say(progress, "Looking for fixed element ratios…")
    molar = "element_moles_fmol" in ctx.available_data_keys()
    data_key = "element_moles_fmol" if molar else "elements"
    matrix, det = ctx.matrix_for(data_key)
    els = [e for e in ctx.frequent_elements() if e in matrix][:25]

    found = []
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            a, b = els[i], els[j]
            if _same_symbol(a, b) or mass_related(a, b):
                continue
            co = det[a] & det[b]
            n = int(co.sum())
            if n < STOICHIOMETRY_MIN_OVERLAP:
                continue
            la, lb = np.log10(matrix[a][co]), np.log10(matrix[b][co])
            sa, sb = _robust_sd(la), _robust_sd(lb)
            independent = math.hypot(sa, sb)
            if independent < 0.15:
                continue
            lr = la - lb
            spread = _robust_sd(lr)
            coupling = spread / independent
            if spread > STOICHIOMETRY_MAX_SPREAD or coupling > STOICHIOMETRY_MAX_COUPLING:
                continue
            med = float(np.median(lr))
            if med < 0:
                a, b, med = b, a, -med
            found.append((coupling, a, b, 10 ** med, spread, independent, n))

    found.sort(key=lambda f: f[0])
    out = []
    used: set[str] = set()
    for coupling, a, b, ratio, spread, independent, n in found:
        if len(out) >= 3 or (a in used and b in used):
            continue
        used.update((a, b))
        unit = "molar" if molar else "count"
        simple = _simple_ratio(ratio) if molar else None
        tail = (f" That is close to {simple}, which suggests one phase of fixed composition."
                if simple else " A ratio this steady suggests one phase of fixed composition.")
        if not molar:
            tail += " Calibrate to moles to read it as a formula."
        if molar:
            node_type = "molar_ratio_plot"
            config = {"numerator_element": a, "denominator_element": b,
                      "data_type_display": "Element Moles (fmol)"}
        else:
            node_type = "correlation_plot"
            config = {"x_element": b, "y_element": a, "log_x": True, "log_y": True}
        out.append(rr.Suggestion(
            title=f"Fixed {a}/{b} ratio",
            reasoning=(
                f"In {n:,} particles carrying both, the {unit} ratio {a}/{b} stays near "
                f"{ratio:.3g} (spread ×{10 ** spread:.2f}, against ×{10 ** independent:.2f} "
                f"if the two varied independently).{tail}"
            ),
            category="stoichiometry",
            confidence=min(0.6 + (STOICHIOMETRY_MAX_COUPLING - coupling) * 0.75, 0.92),
            explain_key="stoichiometry",
            details=[("Ratio", f"{a}/{b} = {ratio:.3g} ({unit})"),
                     ("Closest simple ratio", simple or "none within 8 %"),
                     ("Particles with both", f"{n:,}"),
                     ("Spread of the ratio", f"×{10 ** spread:.2f}"),
                     ("Spread if independent", f"×{10 ** independent:.2f}")],
            node_type=node_type,
            config=config,
            elements=(a, b),
        ))
    return out


def analyse_cooccurrence(ctx, progress=None) -> list:
    """Find elements that turn up together, or avoid each other, more than chance allows.

    This looks at presence alone. Correlation only sees particles carrying
    both elements, so it is blind to an element that is *always* accompanied
    by another, or to two elements that are never found in the same particle.

    Each pair gets a Fisher exact test on its two-by-two presence table, and
    the family is corrected for false discovery. A rule must also clear an
    effect-size floor: the rarer element must come with the other in at least
    :data:`COOCCURRENCE_MIN_CONFIDENCE` of its particles, at a lift of at least
    :data:`COOCCURRENCE_MIN_LIFT`.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to three heatmap suggestions focused on the rarer element.
    """
    rr = _rr()
    rr._say(progress, "Checking which elements travel together…")
    total = ctx.n
    floor = max(10, int(0.02 * total))
    els = [e for e in ctx.elements_by_abundance() if ctx.det_counts[e] >= floor][:25]

    tests = []
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            a, b = els[i], els[j]
            if _same_symbol(a, b) or mass_related(a, b):
                continue
            na, nb = ctx.det_counts[a], ctx.det_counts[b]
            nab = int((ctx.det_mask[a] & ctx.det_mask[b]).sum())
            expected = na * nb / total
            rare, common = (a, b) if na <= nb else (b, a)
            n_rare = min(na, nb)
            confidence = nab / n_rare if n_rare else 0.0
            lift = nab / expected if expected > 0 else 0.0
            table = [[nab, na - nab], [nb - nab, total - na - nb + nab]]
            if confidence >= COOCCURRENCE_MIN_CONFIDENCE and lift >= COOCCURRENCE_MIN_LIFT and nab >= 10:
                kind, alternative = "with", "greater"
            elif expected >= 10 and nab <= COOCCURRENCE_AVOID_RATIO * expected:
                kind, alternative = "avoid", "less"
            else:
                continue
            try:
                p = float(_stats.fisher_exact(table, alternative=alternative)[1])
            except Exception:
                continue
            tests.append((kind, rare, common, nab, n_rare, expected, confidence, lift, p))

    if not tests:
        return []
    significant, adjusted = rr._benjamini_hochberg([t[-1] for t in tests])
    kept = [(t, float(adjusted[k])) for k, t in enumerate(tests) if significant[k]]
    together = sorted((k for k in kept if k[0][0] == "with"),
                      key=lambda x: -(x[0][7] * x[0][6]))
    apart = sorted((k for k in kept if k[0][0] == "avoid"),
                   key=lambda x: x[0][3] / x[0][5])
    chosen = together[:2] + apart[:1]
    chosen += [k for k in together[2:] + apart[1:]][: 3 - len(chosen)]

    out = []
    for (kind, rare, common, nab, n_rare, expected, confidence, lift, _p), q in chosen:
        if kind == "with":
            title = f"{common} comes with {rare}"
            reasoning = (
                f"{confidence:.0%} of particles with {rare} also carry {common} "
                f"({nab:,} of {n_rare:,}), {lift:.1f}× more often than chance would give. "
                f"Fisher {rr._fmt_q(q)}."
            )
            conf = min(0.55 + 0.1 * min(lift, 4.0), 0.9)
        else:
            title = f"{rare} and {common} avoid each other"
            reasoning = (
                f"Only {nab:,} particles carry both, against {expected:.0f} expected by chance. "
                "They most likely belong to different particle populations. "
                f"Fisher {rr._fmt_q(q)}."
            )
            conf = min(0.55 + 0.3 * (1.0 - nab / expected), 0.85)
        out.append(rr.Suggestion(
            title=title,
            reasoning=reasoning,
            category="cooccurrence",
            confidence=conf,
            explain_key=f"cooccurrence_{kind}",
            details=[("Particles with both", f"{nab:,}"),
                     (f"Particles with {rare}", f"{n_rare:,}"),
                     ("Expected by chance", f"{expected:.1f}"),
                     ("Lift over chance", f"{lift:.2f}×"),
                     ("Fisher q", rr._fmt_q(q).replace("q ", "", 1).lstrip("= "))],
            node_type="heatmap_plot",
            config={"search_element": rare, "highlight_matches": True},
            elements=(rare, common),
        ))
    return out


def analyse_rare(ctx, progress=None) -> list:
    """Point out elements found in only a handful of particles.

    These never reach the other detectors, which ignore rarely detected
    elements to keep their statistics sound. A few particles carrying an
    element nothing else carries are often a real minor phase or a
    contamination event, so they are listed with the elements they come with.

    Isotopes of an element that is itself common are skipped, since a minor
    isotope of a major element is rare only because it is minor.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to three heatmap suggestions.
    """
    rr = _rr()
    rr._say(progress, "Looking for rare particles…")
    frequent = set(ctx.frequent_elements())
    frequent_symbols = {mass_symbol(e)[1] for e in frequent}
    ceiling = max(RARE_MAX_COUNT, int(0.005 * ctx.n))

    found = []
    for el, count in ctx.det_counts.items():
        if el in frequent or not (RARE_MIN_COUNT <= count <= ceiling):
            continue
        if mass_symbol(el)[1] in frequent_symbols:
            continue
        mask = ctx.det_mask[el]
        companions = []
        for other, other_mask in ctx.det_mask.items():
            if other == el:
                continue
            shared = int((mask & other_mask).sum())
            background = ctx.det_counts[other] / ctx.n
            if shared >= max(2, math.ceil(0.5 * count)) and shared / count >= 2.0 * background:
                companions.append((shared, other))
        companions.sort(reverse=True)
        consistency = companions[0][0] / count if companions else 0.0
        found.append((consistency, count, el, companions[:3]))

    found.sort(key=lambda f: (-f[0], -f[1]))
    out = []
    covered: set[str] = set()
    for consistency, count, el, companions in found:
        if len(out) >= 3:
            break
        if el in covered:
            continue
        covered.update([el] + [c for _, c in companions])
        if companions:
            names = " + ".join(c for _, c in companions)
            detail = f", {companions[0][0]} of them with {names}"
        else:
            detail = ", each with a different set of elements"
        out.append(rr.Suggestion(
            title=f"Rare: {count} particle{'s' if count != 1 else ''} with {el}",
            reasoning=(
                f"{el} appears in only {count} of {ctx.n:,} particles{detail}. Too few for "
                "statistics, but a handful of distinct particles is often a real minor phase "
                "or a contamination event."
            ),
            category="rare",
            confidence=min(0.45 + 0.25 * consistency, 0.72),
            explain_key="rare",
            details=[("Particles", f"{count} of {ctx.n:,}")]
            + [(f"With {c}", f"{k} of {count}") for k, c in companions],
            node_type="heatmap_plot",
            config={"search_element": el, "highlight_matches": True},
            elements=tuple([el] + [c for _, c in companions]),
        ))
    return out


def analyse_network(ctx, progress=None) -> list:
    """Find a connected group of four or more mutually correlated elements.

    Pairwise correlations are tested and corrected for false discovery as in
    the correlation detector, then linked into a graph. A connected group this
    size usually traces one source or one particle type, which a single pair
    cannot show.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        At most one network diagram suggestion.
    """
    rr = _rr()
    els = ctx.frequent_elements()[:20]
    if len(els) < 4:
        return []
    rr._say(progress, "Linking correlated elements…")
    pairs = [(a, b, res) for a, b, res in rr.correlated_pairs(ctx, els)
             if not _same_symbol(a, b)]
    if not pairs:
        return []
    significant, _adj = rr._benjamini_hochberg([p[2]["pearson_p"] for p in pairs])
    edges = [(a, b) for k, (a, b, res) in enumerate(pairs)
             if significant[k] and abs(res["spearman"]) >= rr.MIN_ABS_CORRELATION]
    if len(edges) < 3:
        return []

    parent = {e: e for e in els}

    def find(x):
        """Return the representative of *x*'s component."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    components: dict[str, list[str]] = {}
    for e in els:
        components.setdefault(find(e), []).append(e)
    best = max(components.values(), key=len)
    if len(best) < 4:
        return []
    members = [e for e in els if e in best]
    n_edges = sum(1 for a, b in edges if a in best and b in best)
    shown = ", ".join(members[:5]) + (f" +{len(members) - 5}" if len(members) > 5 else "")
    return [rr.Suggestion(
        title=f"{len(members)} elements move together: {shown}",
        reasoning=(
            f"{n_edges} significant correlations (|ρ| ≥ {rr.MIN_ABS_CORRELATION:.1f}) link "
            f"{', '.join(members)}. A connected group like this usually traces one source "
            "or one particle type."
        ),
        category="correlation",
        confidence=min(0.6 + 0.05 * len(members), 0.88),
        explain_key="network",
        details=[("Elements", ", ".join(members)), ("Significant links", str(n_edges))],
        node_type="network_diagram",
        config={"r_threshold": rr.MIN_ABS_CORRELATION},
        elements=tuple(members[:10]),
    )]


def analyse_ternary(ctx, progress=None) -> list:
    """Suggest a ternary plot for the most common three-element particles.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        At most one ternary suggestion, when at least 30 particles and 3 % of
        the group carry the same three elements.
    """
    rr = _rr()
    els = ctx.frequent_elements()[:12]
    if len(els) < 3:
        return []
    rr._say(progress, "Looking for three-element particles…")
    best = None
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            ij = ctx.det_mask[els[i]] & ctx.det_mask[els[j]]
            if ij.sum() < 30:
                continue
            for k in range(j + 1, len(els)):
                trio = (els[i], els[j], els[k])
                if len({mass_symbol(e)[1] for e in trio}) < 3:
                    continue
                n = int((ij & ctx.det_mask[els[k]]).sum())
                if best is None or n > best[0]:
                    best = (n, trio)
    if best is None or best[0] < max(30, 0.03 * ctx.n):
        return []
    n, (a, b, c) = best
    mask = ctx.det_mask[a] & ctx.det_mask[b] & ctx.det_mask[c]
    stack = np.vstack([ctx.matrix[e][mask] for e in (a, b, c)])
    shares = stack / stack.sum(axis=0)
    spread = float(shares.std(axis=1).max())
    shape = ("their proportions vary widely" if spread >= 0.1
             else "their proportions stay close together")
    return [rr.Suggestion(
        title=f"{a}–{b}–{c} particles",
        reasoning=(
            f"{n:,} particles ({n / ctx.n:.0%}) carry all three of {a}, {b} and {c}, and "
            f"{shape}. A ternary plot shows whether they form one composition or a mixing line."
        ),
        category="composition",
        confidence=min(0.5 + n / ctx.n, 0.8),
        explain_key="composition",
        details=[("Particles with all three", f"{n:,} ({n / ctx.n:.0%})"),
                 ("Largest spread of a share", f"{spread:.2f}")],
        node_type="triangle_plot",
        config={"element_a": a, "element_b": b, "element_c": c},
        elements=(a, b, c),
    )]


def analyse_single_multi(ctx, progress=None) -> list:
    """Contrast elements found alone with elements found in mixtures.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        At most one single-versus-multiple suggestion, when one element is
        mostly alone and another mostly in multi-element particles.
    """
    rr = _rr()
    els = [e for e in ctx.frequent_elements() if ctx.det_counts[e] >= 20]
    if len(els) < 2:
        return []
    rr._say(progress, "Comparing single- and multi-element particles…")
    n_el = _n_elements(ctx)
    shares = [(float(np.mean(n_el[ctx.det_mask[e]] == 1)), e) for e in els]
    shares.sort()
    low, low_el = shares[0]
    high, high_el = shares[-1]
    if high < 0.8 or low > 0.3:
        return []
    return [rr.Suggestion(
        title=f"{high_el} mostly alone, {low_el} mostly mixed",
        reasoning=(
            f"{high:.0%} of {high_el} particles carry no other element, while {1 - low:.0%} of "
            f"{low_el} particles carry at least one more. They point to different particle "
            "types, or to one element dissolved and the other in composite particles."
        ),
        category="composition",
        confidence=min(0.5 + (high - low) * 0.4, 0.85),
        explain_key="composition",
        details=[(f"{high_el} alone", f"{high:.0%} of its particles"),
                 (f"{low_el} with others", f"{1 - low:.0%} of its particles")],
        node_type="single_multiple_element_plot",
        config={},
        elements=(high_el, low_el),
    )]


def analyse_detection_limit(ctx, progress=None) -> list:
    """Flag distributions cut off by the detection limit.

    A population that sits fully above the detection limit rises from its
    lowest values to a peak. One that is truncated peaks right at its lowest
    values, with a large share of particles piled into the bottom of the
    range, and its mean and median are then biased upward.

    Size is checked first, then mass, then counts.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to two histogram suggestions.
    """
    rr = _rr()
    rr._say(progress, "Checking for detection-limit cut-offs…")
    keys = ctx.available_data_keys()
    data_key = next((k for k in ("element_diameter_nm", "element_mass_fg") if k in keys),
                    "elements")
    matrix, det = ctx.matrix_for(data_key)
    found = []
    for el in ctx.frequent_elements():
        if el not in matrix:
            continue
        values = matrix[el][det[el]]
        if len(values) < 100:
            continue
        logged = np.log10(values)
        lo, hi = float(logged.min()), float(logged.max())
        if hi - lo < 0.3:
            continue
        hist, _ = np.histogram(logged, bins=40, range=(lo, hi))
        bottom = float(np.mean(logged <= lo + 0.05 * (hi - lo)))
        if int(np.argmax(hist)) <= 1 and bottom >= DETECTION_LIMIT_MIN_SHARE:
            found.append((bottom, el, 10 ** lo, len(values)))

    found.sort(reverse=True)
    noun = rr._DATA_KEY_NOUNS.get(data_key, "value")
    unit = rr._DATA_KEY_UNITS.get(data_key, "")
    label = rr._DATA_KEY_LABELS.get(data_key, "Counts")
    out = []
    for bottom, el, low_value, n in found[:2]:
        out.append(rr.Suggestion(
            title=f"{el} {noun} cut off at the detection limit",
            reasoning=(
                f"The {el} {noun} distribution peaks right at its lowest values "
                f"(about {low_value:.3g} {unit}): {bottom:.0%} of {n:,} particles sit in the "
                "bottom 5 % of the range. The real population likely continues below the "
                "detection limit, so its mean and median here are biased upward."
            ),
            category="quality",
            confidence=min(0.5 + bottom, 0.85),
            explain_key="quality",
            details=[("Measured as", noun), ("Lowest value", f"{low_value:.3g} {unit}"),
                     ("Particles in the bottom 5 % of the range", f"{bottom:.0%}"),
                     ("Particles", f"{n:,}")],
            node_type="histogram_plot",
            config={"element": el, "data_type_display": label, "show_det_limit": True},
            elements=(el,),
        ))
    return out


def analyse_size_composition(ctx, progress=None) -> list:
    """Find elements whose share of a particle changes with particle size.

    In multi-element particles, the mass fraction of each element is ranked
    against total particle mass. A falling share fits a coating, a shell or a
    surface-bound element, which thins out as particles grow; a rising share
    fits a core. The family is corrected for false discovery.

    Needs mass-calibrated data. The suggested figure leaves every element in,
    because the total has to include all of them.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Up to two Figure Builder suggestions plotting fraction against size.
    """
    rr = _rr()
    if "element_mass_fg" not in ctx.available_data_keys():
        return []
    rr._say(progress, "Checking how composition changes with size…")
    matrix, det = ctx.matrix_for("element_mass_fg")
    total = np.zeros(ctx.n)
    for arr in matrix.values():
        total += arr
    count = np.zeros(ctx.n, dtype=np.int32)
    for mask in det.values():
        count += mask
    multi = count >= 2

    tests = []
    for el in ctx.frequent_elements():
        if el not in matrix:
            continue
        m = det[el] & multi & (total > 0)
        n = int(m.sum())
        if n < 50:
            continue
        frac = matrix[el][m] / total[m]
        size = np.log10(total[m])
        if frac.std() < 1e-6 or size.std() < 1e-6:
            continue
        rho, p = _stats.spearmanr(size, frac)
        if np.isfinite(rho) and np.isfinite(p):
            tests.append((el, float(rho), float(p), n))
    if not tests:
        return []
    significant, adjusted = rr._benjamini_hochberg([t[2] for t in tests])
    kept = [(t, float(adjusted[k])) for k, t in enumerate(tests)
            if significant[k] and abs(t[1]) >= SIZE_TREND_MIN_RHO]
    kept.sort(key=lambda x: -abs(x[0][1]))

    out = []
    for (el, rho, _p, n), q in kept[:2]:
        falls = rho < 0
        spec = _figure_spec(
            "Element Mass (fg)", kind="scatter", x="total", y=f"mass:{el} / total",
            log_x=True, filter="n_elements >= 2", trend="median",
            x_label="Particle mass (fg)", y_label=f"{el} mass fraction",
            title=f"{el} share vs particle size",
        )
        out.append(rr.Suggestion(
            title=f"{el} share {'falls' if falls else 'rises'} with particle size",
            reasoning=(
                f"In {n:,} multi-element particles the {el} mass fraction "
                f"{'drops' if falls else 'grows'} as particles get bigger (ρ = {rho:+.2f}, "
                f"{rr._fmt_q(q)}). "
                + ("A coating, shell or surface-bound element thins out like this in larger "
                   "particles." if falls else
                   "A core element, or one that grows with the particle, behaves like this.")
            ),
            category="composition",
            confidence=min(0.5 + abs(rho) * 0.5, 0.88),
            explain_key="size",
            details=[("Element", el), ("Rank correlation with size", f"{rho:+.2f}"),
                     ("Multi-element particles", f"{n:,}"), ("False discovery", rr._fmt_q(q))],
            node_type="figure_builder",
            config=spec,
            elements=(),
        ))
    return out


def analyse_time(ctx, progress=None) -> list:
    """Check each sample's acquisition for drift and bursts.

    Particle arrival counts in 20 equal time bins are tested against a steady
    Poisson process. A trend in those counts points to a change in transport,
    such as a clogging nebuliser; scatter without a trend points to bursts of
    particles. The median signal of the main elements is also followed over
    time, where a steady trend in several elements at once points to drifting
    sensitivity.

    Each sample is checked on its own, since every acquisition has its own
    clock.

    Args:
        ctx: Analysis context over every sample in scope.
        progress: Optional callable receiving status strings.

    Returns:
        Figure Builder timeline suggestions, at most two per sample and four
        in all.
    """
    rr = _rr()
    t_all = _times(ctx)
    if not np.isfinite(t_all).any():
        return []
    rr._say(progress, "Checking acquisitions over time…")
    out = []
    for index, name in enumerate(ctx.sample_names):
        in_sample = (ctx.sample_idx == index) & np.isfinite(t_all)
        if int(in_sample.sum()) < TIME_MIN_PARTICLES:
            continue
        t = t_all[in_sample]
        if np.ptp(t) <= 0:
            continue
        rate = _rate_finding(name, t)
        if rate is not None:
            out.append(rate)
        drift = _signal_drift(ctx, name, in_sample, t_all)
        if drift is not None:
            out.append(drift)
    out.sort(key=lambda s: -s.confidence)
    return out[:4]


def _rate_finding(name: str, t: np.ndarray):
    """Test one sample's particle arrival rate for drift or bursts."""
    rr = _rr()
    bins = 20
    counts, _ = np.histogram(t, bins=bins)
    mean = float(counts.mean())
    if mean <= 0:
        return None
    chi2 = float(np.sum((counts - mean) ** 2) / mean)
    p = float(_stats.chi2.sf(chi2, bins - 1))
    dispersion = float(counts.var() / mean)
    if p >= 1e-4 or dispersion < 3.0:
        return None
    rho = float(_stats.spearmanr(np.arange(bins), counts)[0])
    first, last = float(counts[:3].mean()), float(counts[-3:].mean())
    fold = (last / first) if first > 0 else float("inf")
    sample_cfg = {"samples": (name,), "sample_groups": {name: ""}}
    if abs(rho) >= 0.7 and (fold >= 1.3 or fold <= 1 / 1.3):
        direction = "rises" if fold > 1 else "falls"
        size = fold if fold > 1 else (1 / fold if fold > 0 else float("inf"))
        title = f"Particle rate {direction} through {name}"
        reasoning = (
            f"The particle arrival rate {direction} about {size:.1f}× from the start to the end "
            f"of {name} (ρ = {rho:+.2f} over 20 time bins, χ² p = {p:.1g}). That usually means "
            "transport changed during the run, for example a nebuliser clogging or the uptake "
            "drifting, so particle concentrations from this sample deserve a check."
        )
        conf = min(0.6 + abs(rho) * 0.3, 0.9)
    else:
        title = f"Particles arrive in bursts in {name}"
        reasoning = (
            f"Arrivals in {name} scatter {dispersion:.1f}× more than a steady stream would "
            f"(χ² p = {p:.1g}), without a steady trend. Bursts like this come from "
            "agglomerates breaking up, a droplet or a contamination event."
        )
        conf = min(0.5 + 0.05 * dispersion, 0.8)
    spec = _figure_spec("Counts", kind="timeline", time_mode="rate", bins=40,
                        title=f"Particle rate, {name}", group_by="sample")
    return rr.Suggestion(title=title, reasoning=reasoning, category="time", confidence=conf,
                         node_type="figure_builder", config=spec, elements=(),
                         explain_key="time_rate",
                         details=[("Sample", name), ("Particles", f"{len(t):,}"),
                                  ("Dispersion (variance / mean)", f"{dispersion:.1f}"),
                                  ("Trend over time (ρ)", f"{rho:+.2f}"),
                                  ("Last / first bins", f"{fold:.2f}×"),
                                  ("χ² p", f"{p:.1g}")],
                         **sample_cfg)


def _signal_drift(ctx, name: str, in_sample: np.ndarray, t_all: np.ndarray):
    """Follow the median signal of the main elements in one sample over time."""
    rr = _rr()
    ranked = sorted(ctx.det_mask, key=lambda e: -int((ctx.det_mask[e] & in_sample).sum()))
    drifting = []
    for el in ranked[:6]:
        m = ctx.det_mask[el] & in_sample
        if int(m.sum()) < 100:
            continue
        v = np.log10(ctx.matrix[el][m])
        t = t_all[m]
        edges = np.linspace(t.min(), t.max(), 11)
        which = np.clip(np.digitize(t, edges) - 1, 0, 9)
        medians, centres = [], []
        for b in range(10):
            sel = which == b
            if sel.sum() >= 10:
                medians.append(float(np.median(v[sel])))
                centres.append(b)
        if len(medians) < 6:
            continue
        rho, p = _stats.spearmanr(centres, medians)
        if not np.isfinite(rho):
            continue
        fold = 10 ** (np.mean(medians[-2:]) - np.mean(medians[:2]))
        if abs(rho) >= 0.8 and p < 0.01 and (fold >= TIME_DRIFT_MIN_FOLD or fold <= 1 / TIME_DRIFT_MIN_FOLD):
            drifting.append((abs(rho), el, float(fold), float(rho)))
    if not drifting:
        return None
    drifting.sort(reverse=True)
    directions = {d[2] > 1 for d in drifting}
    lead = drifting[0][1]
    spec = _figure_spec("Counts", kind="timeline", time_mode="signal", value=lead, log_y=True,
                        title=f"{lead} signal over time, {name}")
    sample_cfg = {"samples": (name,), "sample_groups": {name: ""}}
    if len(drifting) >= 2 and len(directions) == 1:
        up = drifting[0][2] > 1
        els = ", ".join(d[1] for d in drifting[:4])
        change = np.mean([abs(math.log10(d[2])) for d in drifting])
        return rr.Suggestion(
            title=f"Signals drift {'up' if up else 'down'} through {name}",
            reasoning=(
                f"The median signal of {els} {'rises' if up else 'falls'} steadily over the run "
                f"(about {10 ** change:.2f}× from start to end). Several elements moving together "
                "points to a change in instrument sensitivity rather than in the sample."
            ),
            category="time",
            confidence=min(0.6 + 0.05 * len(drifting), 0.88),
            explain_key="time_signal",
            details=[("Sample", name)] + [(f"{d[1]} change", f"{d[2]:.2f}× (ρ = {d[3]:+.2f})")
                                          for d in drifting[:5]],
            node_type="figure_builder",
            config=spec,
            elements=(),
            **sample_cfg,
        )
    rho_abs, el, fold, rho = drifting[0]
    return rr.Suggestion(
        title=f"{el} signal drifts through {name}",
        reasoning=(
            f"The median {el} signal {'rises' if fold > 1 else 'falls'} about "
            f"{max(fold, 1 / fold):.2f}× from the start to the end of {name} (ρ = {rho:+.2f}). "
            "Only this element moves, so the particles themselves may change during the run."
        ),
        category="time",
        confidence=min(0.5 + rho_abs * 0.3, 0.8),
        explain_key="time_signal",
        details=[("Sample", name), ("Element", el), ("Change start to end", f"{fold:.2f}×"),
                 ("Trend (ρ)", f"{rho:+.2f}")],
        node_type="figure_builder",
        config=spec,
        elements=(),
        **sample_cfg,
    )


def _replicate_metrics(ctx, indices: list[int], elements: list[str]) -> dict:
    """Summarise each replicate on the measures used to judge agreement.

    Args:
        ctx: Analysis context over every sample in scope.
        indices: Sample indices of the replicates.
        elements: Elements to summarise.

    Returns:
        Metric name to ``(kind, values)``, where *values* holds one entry per
        replicate (``nan`` when that replicate has too little data) and *kind*
        is ``"log"`` for log10 medians and rates, ``"share"`` for detection
        rates.
    """
    metrics: dict[str, tuple[str, list[float]]] = {}
    t_all = _times(ctx)
    rates = []
    for i in indices:
        m = (ctx.sample_idx == i) & np.isfinite(t_all)
        span = float(np.ptp(t_all[m])) if m.sum() >= 2 else 0.0
        rates.append(math.log10(m.sum() / span) if span > 0 else float("nan"))
    if sum(np.isfinite(rates)) >= 2:
        metrics["particle rate"] = ("log", rates)
    for el in elements:
        medians, shares = [], []
        for i in indices:
            in_sample = ctx.sample_idx == i
            size = int(in_sample.sum())
            hit = ctx.det_mask[el] & in_sample
            n_hit = int(hit.sum())
            shares.append(n_hit / size if size else float("nan"))
            medians.append(float(np.log10(np.median(ctx.matrix[el][hit]))) if n_hit >= 10
                           else float("nan"))
        metrics[f"{el} signal"] = ("log", medians)
        metrics[f"{el} detection rate"] = ("share", shares)
    return metrics


def _disagreement(kind: str, values: list[float]) -> tuple[int | None, float, float] | None:
    """Find a replicate that disagrees with its siblings on one measure.

    With two replicates the gap between them is all there is, and the odd one
    out cannot be named. With three or more, a replicate is flagged only when
    it sits clearly away from the others *and* the others agree among
    themselves, so a measure that is simply noisy flags nothing.

    Args:
        kind: ``"log"`` or ``"share"``, as from :func:`_replicate_metrics`.
        values: One value per replicate, ``nan`` where unavailable.

    Returns:
        ``(odd_index, gap, threshold)`` where *odd_index* is ``None`` for a
        two-replicate disagreement, or ``None`` when the replicates agree.
    """
    vals = np.asarray(values, dtype=float)
    ok = np.isfinite(vals)
    if ok.sum() < 2:
        return None
    threshold = math.log10(REPLICATE_FOLD) if kind == "log" else REPLICATE_RATE_GAP
    idx = np.flatnonzero(ok)
    if len(idx) == 2:
        gap = abs(vals[idx[0]] - vals[idx[1]])
        return (None, gap, threshold) if gap > threshold else None
    best = None
    for i in idx:
        others = vals[[j for j in idx if j != i]]
        gap = abs(vals[i] - float(np.median(others)))
        spread = float(others.max() - others.min())
        if gap > threshold and gap > 3.0 * spread:
            if best is None or gap > best[1]:
                best = (int(i), gap, threshold)
    return best


def analyse_replicates(ctx, progress=None) -> list:
    """Check that replicates of one material agree, and say which one does not.

    Each replicate is summarised by its particle arrival rate, and by the
    median signal and detection rate of the group's main elements. A
    replicate that sits well away from siblings that agree with each other is
    flagged; with only two replicates the disagreement is reported without
    guessing which one is off. Groups whose replicates agree on everything get
    a short card saying so, since that agreement is what makes the group's
    comparisons trustworthy.

    Args:
        ctx: Analysis context over every sample in scope.
        progress: Optional callable receiving status strings.

    Returns:
        One suggestion per replicate group with at least two usable replicates.
    """
    rr = _rr()
    groups = [g for g in ctx.scope.groups if g.is_replicated]
    if not groups:
        return []
    rr._say(progress, "Checking replicate agreement…")
    names = list(ctx.sample_names)
    out = []
    for group in groups:
        indices = [names.index(m) for m in group.members if m in names]
        indices = [i for i in indices if int((ctx.sample_idx == i).sum()) >= MIN_GROUP_PARTICLES]
        if len(indices) < 2:
            continue
        in_group = np.isin(ctx.sample_idx, indices)
        n_group = int(in_group.sum())
        elements = [e for e in ctx.elements_by_abundance()
                    if int((ctx.det_mask[e] & in_group).sum()) >= max(10, 0.05 * n_group)][:8]
        metrics = _replicate_metrics(ctx, indices, elements)
        members = tuple(names[i] for i in indices)
        flags = []
        for metric, (kind, values) in metrics.items():
            result = _disagreement(kind, values)
            if result is not None:
                flags.append((result[1] / result[2], metric, kind, result, values))
        flags.sort(key=lambda f: -f[0])
        sample_cfg = {"samples": members, "sample_groups": {m: "" for m in members}}
        flagged_elements = [f[1].rsplit(" ", 2)[0] for f in flags
                            if f[1] != "particle rate"]
        flagged_elements = list(dict.fromkeys(e for e in flagged_elements if e in ctx.det_mask))

        if flags:
            out.append(_replicate_flag_card(rr, group, members, flags, flagged_elements,
                                            sample_cfg))
        else:
            out.append(_replicate_agree_card(rr, group, members, metrics, elements, sample_cfg))
    return out


def _describe_gap(kind: str, gap: float) -> str:
    """Word a replicate gap as a fold or a percentage-point difference."""
    if kind == "log":
        return f"{10 ** gap:.2f}×"
    return f"{gap * 100:.0f} points"


def _replicate_flag_card(rr, group, members, flags, flagged_elements, sample_cfg):
    """Build the card for a replicate group with a disagreement."""
    _score, metric, kind, (odd, gap, _thr), _values = flags[0]
    listed = "; ".join(f"{f[1]} ({_describe_gap(f[2], f[3][1])})" for f in flags[:3])
    if odd is not None:
        odd_name = members[odd] if odd < len(members) else "one replicate"
        others = ", ".join(m for k, m in enumerate(members) if k != odd)
        title = f"Replicate {odd_name} disagrees with {others}"
        reasoning = (
            f"In group {group.name}, {odd_name} is off from its siblings, which agree with each "
            f"other: {listed}. Check it for contamination, a blocked nebuliser or a "
            "preparation error before pooling it with the rest."
        )
    else:
        title = f"Replicates of {group.name} disagree"
        reasoning = (
            f"{members[0]} and {members[1]} differ on {listed}. With two replicates it is not "
            "possible to tell which one is off; a third would settle it."
        )
    if flagged_elements:
        node_type = "concentration_comparison"
        config = {"element": flagged_elements[0]}
        elements = tuple(flagged_elements[:4])
    else:
        node_type = "figure_builder"
        config = _figure_spec("Counts", kind="timeline", time_mode="cumulative",
                              group_by="sample", title=f"Particle arrivals, {group.name}")
        elements = ()
    return rr.Suggestion(
        title=title,
        reasoning=reasoning,
        category="replicate",
        confidence=min(0.6 + 0.08 * len(flags), 0.92),
        explain_key="replicate_flag",
        details=[(f[1], _describe_gap(f[2], f[3][1])) for f in flags[:6]],
        node_type=node_type,
        config=config,
        elements=elements,
        **sample_cfg,
    )


def _replicate_agree_card(rr, group, members, metrics, elements, sample_cfg):
    """Build the card for a replicate group whose replicates agree."""
    fold_gaps, share_gaps = [], []
    for kind, values in metrics.values():
        vals = np.asarray(values, dtype=float)
        vals = vals[np.isfinite(vals)]
        if len(vals) < 2:
            continue
        (fold_gaps if kind == "log" else share_gaps).append(float(vals.max() - vals.min()))
    worst_fold = 10 ** max(fold_gaps) if fold_gaps else 1.0
    worst_share = max(share_gaps) if share_gaps else 0.0
    return rr.Suggestion(
        title=f"Replicates of {group.name} agree",
        reasoning=(
            f"{len(members)} replicates ({', '.join(members)}) match on {len(elements)} "
            f"element{'s' if len(elements) != 1 else ''}: median signals within "
            f"{worst_fold:.2f}× and detection rates within {worst_share * 100:.0f} points. "
            "Differences between this group and others can be trusted at that level."
        ),
        category="replicate",
        confidence=0.5,
        explain_key="replicate_agree",
        details=[("Replicates", ", ".join(members)),
                 ("Largest gap in median signal", f"{worst_fold:.2f}×"),
                 ("Largest gap in detection rate", f"{worst_share * 100:.0f} points")],
        node_type="box_plot",
        config={"elements": list(elements[:4])},
        elements=tuple(elements[:4]),
        **sample_cfg,
    )


def merge_group_findings(items, scope_order, n_groups: int) -> list:
    """Merge the same finding reported by several replicate groups into one card.

    Two findings are the same when they would build the same node, for the same
    elements and settings. The merged card keeps the strongest version's
    wording, covers every sample where the finding held, and says where it was
    seen when more than one group was searched.

    Args:
        items: ``(suggestion, group)`` pairs from a within-group detector.
        scope_order: Sample names in scope order, used to order the merged
            sample list.
        n_groups: How many groups were searched.

    Returns:
        The merged suggestions.
    """
    buckets: dict[tuple, list] = {}
    order: list[tuple] = []
    for s, group in items:
        key = (s.node_type, s.category, tuple(sorted(s.elements)), _config_key(s.config))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((s, group))

    rank = {name: i for i, name in enumerate(scope_order)}
    merged = []
    for key in order:
        entries = buckets[key]
        best, _ = max(entries, key=lambda e: e[0].confidence)
        groups = []
        for _s, g in entries:
            if g is not None and g not in groups:
                groups.append(g)
        samples: list[str] = []
        sample_groups: dict[str, str] = {}
        for g in groups:
            for member in g.members:
                if member not in sample_groups:
                    samples.append(member)
                    sample_groups[member] = g.name if g.is_replicated else ""
        samples.sort(key=lambda m: rank.get(m, len(rank)))
        reasoning = best.reasoning
        if n_groups > 1 and groups:
            if len(groups) == n_groups:
                reasoning += " Seen in every group."
            elif len(groups) == 1:
                reasoning += f" Only in {groups[0].name}."
            else:
                reasoning += f" Seen in {', '.join(g.name for g in groups)}."
        merged.append(_rr().Suggestion(
            title=best.title,
            reasoning=reasoning,
            category=best.category,
            confidence=best.confidence,
            node_type=best.node_type,
            config=best.config,
            elements=best.elements,
            samples=tuple(samples) if groups else best.samples,
            sample_groups=sample_groups if groups else dict(best.sample_groups),
            explain_key=best.explain_key,
            details=list(best.details) + ([("Seen in", ", ".join(g.name for g in groups))]
                                          if n_groups > 1 and groups else []),
        ))
    return merged


CONVENTIONAL_RATIOS: dict[str, tuple[tuple[str, str], ...]] = {
    "Pb": (("206Pb", "207Pb"), ("208Pb", "206Pb"), ("206Pb", "204Pb")),
    "Sr": (("87Sr", "86Sr"),),
    "Nd": (("143Nd", "144Nd"),),
    "U": (("235U", "238U"),),
    "Os": (("187Os", "188Os"),),
    "Hf": (("176Hf", "177Hf"),),
    "B": (("11B", "10B"),),
    "Li": (("7Li", "6Li"),),
    "Cu": (("65Cu", "63Cu"),),
    "Zn": (("66Zn", "64Zn"),),
    "Ag": (("107Ag", "109Ag"),),
    "Hg": (("202Hg", "200Hg"),),
}
"""Ratios written the way the literature writes them, used when both isotopes are measured."""

ISOTOPE_MIN_PARTICLES = 20
"""Particles carrying both isotopes before a ratio is worth reporting."""

ISOTOPE_ABUNDANCE_GAP = 0.25
"""Relative gap from the natural ratio that earns an abundance card."""

ISOTOPE_GROUP_MIN_GAP = 0.02
"""Smallest relative difference in a ratio between groups worth a card."""

ISOTOPE_MODE_SEPARATION = 0.01
"""Smallest gap between two ratio populations, in log10 units (about 2.3 %)."""

ISOTOPE_TRACK_MIN_RHO = 0.40
"""Rank correlation between a ratio and another element needed for a card."""


def isotope_pairs(ctx, max_per_element: int = 3) -> list[tuple[str, str, str]]:
    """List the isotope ratios to examine: two isotopes of the same element.

    A ratio between two different elements is never listed here; that is a
    fixed or molar ratio, not an isotope ratio. Conventional ratios are used
    where both isotopes are measured (²⁰⁶Pb/²⁰⁷Pb, ⁸⁷Sr/⁸⁶Sr…); otherwise each
    isotope is put over the element's most often detected isotope.

    Args:
        ctx: Analysis context.
        max_per_element: Most ratios per element.

    Returns:
        ``(symbol, numerator, denominator)`` triples.
    """
    by_symbol: dict[str, list[str]] = {}
    for label in ctx.elements_by_abundance():
        mass, symbol = mass_symbol(label)
        if mass and ctx.det_counts.get(label, 0) >= ISOTOPE_MIN_PARTICLES:
            by_symbol.setdefault(symbol, []).append(label)
    pairs = []
    for symbol, labels in by_symbol.items():
        if len(labels) < 2:
            continue
        present = set(labels)
        chosen = [(n, d) for n, d in CONVENTIONAL_RATIOS.get(symbol, ())
                  if n in present and d in present]
        if not chosen:
            reference = labels[0]
            ordered = sorted(labels[1:], key=lambda x: mass_symbol(x)[0])
            chosen = [(other, reference) for other in ordered]
        pairs.extend((symbol, n, d) for n, d in chosen[:max_per_element])
    return pairs


def ratio_values(ctx, num: str, den: str) -> tuple[np.ndarray, np.ndarray]:
    """Return the particles usable for a ratio, and the ratio in each.

    Only particles carrying both isotopes count, and of those only the ones in
    the upper half of the more abundant isotope's signal. Near the detection
    limit the minor isotope is only seen when it happens to read high, which
    would bias the ratio upward.

    Args:
        ctx: Analysis context.
        num: Numerator isotope.
        den: Denominator isotope.

    Returns:
        ``(mask, ratios)``: a boolean mask over the context's particles, and
        the ratio for the particles it selects.
    """
    joint = ctx.det_mask[num] & ctx.det_mask[den]
    major = num if ctx.det_counts[num] >= ctx.det_counts[den] else den
    if int(joint.sum()) < 2:
        return joint, np.zeros(0)
    cut = float(np.median(ctx.matrix[major][joint]))
    use = joint & (ctx.matrix[major] >= cut)
    return use, ctx.matrix[num][use] / ctx.matrix[den][use]


def _natural_ratio(num: str, den: str) -> float | None:
    """Natural abundance ratio of two isotopes, or ``None`` when unknown."""
    try:
        from results.figure_builder.core.isotopes import natural_ratio
        return natural_ratio(num, den)
    except Exception:
        return None


def _ratio_config(num: str, den: str, x_axis: str) -> dict:
    """Isotopic ratio plot settings for one ratio."""
    return {"element1": num, "element2": den, "x_axis_element": x_axis,
            "show_natural_line": _natural_ratio(num, den) is not None}


def analyse_isotope_ratios(ctx, progress=None) -> list:
    """Examine every isotope ratio within one material.

    Four questions are asked of each ratio between two isotopes of the same
    element:

    * what the ratio is, and how many particles it rests on;
    * whether it sits far from natural abundance, which points to an
      interference on one mass or a real isotopic difference;
    * whether the particles split into two ratio populations, the mark of two
      sources mixed in one sample;
    * whether the ratio tracks a *different* element, which points to mixing
      between sources with different signatures. Isotopes of the same element
      are never used for this comparison, and the family of tests is corrected
      for false discovery.

    Args:
        ctx: Analysis context for one replicate group.
        progress: Optional callable receiving status strings.

    Returns:
        Ratio suggestions, at most three per element.
    """
    rr = _rr()
    pairs = isotope_pairs(ctx)
    if not pairs:
        return []
    rr._say(progress, "Examining isotope ratios…")
    out = []
    tracking_tests = []
    for symbol, num, den in pairs:
        use, ratios = ratio_values(ctx, num, den)
        n = len(ratios)
        if n < ISOTOPE_MIN_PARTICLES:
            continue
        median = float(np.median(ratios))
        natural = _natural_ratio(num, den)
        natural_text = f", against {natural:.4g} for natural {symbol}" if natural else ""
        out.append(rr.Suggestion(
            title=f"{num}/{den} isotope ratio",
            reasoning=(
                f"Both are {symbol} isotopes. The median {num}/{den} is {median:.4g} over "
                f"{n:,} particles with a strong signal{natural_text}."
            ),
            category="isotope",
            confidence=0.4,
            explain_key="isotope",
            details=[("Element", symbol), ("Ratio", f"{num}/{den}"), ("Median", f"{median:.4g}"),
                     ("Natural", f"{natural:.4g}" if natural else "unknown"),
                     ("Particles used", f"{n:,}")],
            node_type="isotopic_ratio_plot",
            config=_ratio_config(num, den, den),
            elements=(num, den),
        ))
        if natural:
            gap = median / natural - 1.0
            if abs(gap) >= ISOTOPE_ABUNDANCE_GAP:
                out.append(rr.Suggestion(
                    title=f"{num}/{den} is {gap:+.0%} off natural {symbol}",
                    reasoning=(
                        f"The median {num}/{den} is {median:.4g} against {natural:.4g} for "
                        f"natural abundance, from {n:,} particles. Mass bias moves this by a "
                        "few percent; a gap this large points to an interference on one mass, "
                        "a detection threshold cutting one isotope, or a real isotopic "
                        "difference."
                    ),
                    category="isotope",
                    confidence=min(0.6 + min(abs(gap), 1.0) * 0.3, 0.9),
                    explain_key="isotope_abundance",
                    details=[("Measured median", f"{median:.4g}"), ("Natural", f"{natural:.4g}"),
                             ("Difference", f"{gap:+.1%}"), ("Particles used", f"{n:,}")],
                    node_type="isotopic_ratio_plot",
                    config=_ratio_config(num, den, den),
                    elements=(num, den),
                ))
        split = (rr._detect_bimodality(ratios, ISOTOPE_MODE_SEPARATION)
                 if n >= rr.MIN_BIMODALITY_PARTICLES else None)
        if split is not None:
            low, high = split["modes"]
            out.append(rr.Suggestion(
                title=f"Two {num}/{den} ratio populations",
                reasoning=(
                    f"The {symbol} isotope ratio splits into groups near {low:.4g} and "
                    f"{high:.4g}; the smaller holds {split['minor_share']:.0%} of {n:,} "
                    "particles. Two ratios in one sample usually means two sources of "
                    f"{symbol}."
                ),
                category="isotope",
                confidence=min(0.6 + split["valley_depth"] * 0.3, 0.9),
                explain_key="isotope_two",
                details=[("Lower population", f"{low:.4g}"), ("Upper population", f"{high:.4g}"),
                         ("Smaller group", f"{split['minor_share']:.0%}"),
                         ("Particles used", f"{n:,}")],
                node_type="isotopic_ratio_plot",
                config=_ratio_config(num, den, den),
                elements=(num, den),
            ))
        log_ratio_all = np.full(ctx.n, np.nan)
        log_ratio_all[use] = np.log10(ratios)
        for other in ctx.frequent_elements():
            if mass_symbol(other)[1] == symbol:
                continue
            both = use & ctx.det_mask[other]
            if int(both.sum()) < rr.MIN_CORR_OVERLAP:
                continue
            x = np.log10(ctx.matrix[other][both])
            y = log_ratio_all[both]
            if x.std() < 1e-9 or y.std() < 1e-9:
                continue
            rho, p = _stats.spearmanr(x, y)
            if np.isfinite(rho) and np.isfinite(p):
                tracking_tests.append((symbol, num, den, other, float(rho), float(p),
                                       int(both.sum())))

    if tracking_tests:
        significant, adjusted = rr._benjamini_hochberg([t[5] for t in tracking_tests])
        best: dict[tuple, tuple] = {}
        for k, test in enumerate(tracking_tests):
            if not significant[k] or abs(test[4]) < ISOTOPE_TRACK_MIN_RHO:
                continue
            key = (test[1], test[2])
            if key not in best or abs(test[4]) > abs(best[key][0][4]):
                best[key] = (test, float(adjusted[k]))
        for (symbol, num, den, other, rho, _p, n), q in best.values():
            direction = "rises" if rho > 0 else "falls"
            out.append(rr.Suggestion(
                title=f"{num}/{den} ratio {direction} with {other}",
                reasoning=(
                    f"The {symbol} isotope ratio {num}/{den} {direction} as {other} increases "
                    f"(ρ = {rho:+.2f}, {rr._fmt_q(q)}, {n:,} particles). {other} is a different "
                    f"element, so this points to mixing between sources whose {symbol} carries "
                    f"different isotope signatures, one of them rich in {other}."
                ),
                category="isotope",
                confidence=min(0.55 + abs(rho) * 0.4, 0.92),
                explain_key="isotope_track",
                details=[("Ratio", f"{num}/{den}"), ("Compared with", other),
                         ("Rank correlation (ρ)", f"{rho:+.2f}"), ("Particles", f"{n:,}"),
                         ("False discovery", rr._fmt_q(q))],
                node_type="isotopic_ratio_plot",
                config=_ratio_config(num, den, other),
                elements=(num, den, other),
            ))
    return out


def analyse_isotope_groups(ctx, progress=None) -> list:
    """Compare each isotope ratio between replicate groups.

    Two materials can carry the same amount of an element with different
    isotope signatures, which a concentration comparison cannot see. Each
    replicate's median ratio is one observation; with every group replicated
    the groups are compared with a one-way ANOVA on those medians, otherwise
    with a Kruskal-Wallis test on particle ratios. A difference must be at
    least :data:`ISOTOPE_GROUP_MIN_GAP` relative, and more than
    :data:`REPLICATE_MARGIN` times the spread between replicates.

    Args:
        ctx: Analysis context over every sample in scope.
        progress: Optional callable receiving status strings.

    Returns:
        Up to three suggestions, or nothing with fewer than two groups.
    """
    rr = _rr()
    groups = rr._comparison_groups(ctx)
    pairs = isotope_pairs(ctx)
    if len(groups) < 2 or not pairs:
        return []
    rr._say(progress, "Comparing isotope ratios between groups…")
    tests = []
    for symbol, num, den in pairs:
        use, _ratios = ratio_values(ctx, num, den)
        log_ratio = np.full(ctx.n, np.nan)
        log_ratio[use] = np.log10(ctx.matrix[num][use] / ctx.matrix[den][use])
        summaries = []
        for group, indices in groups:
            medians, pooled = [], []
            for i in indices:
                values = log_ratio[use & (ctx.sample_idx == i)]
                if len(values) >= 10:
                    medians.append(float(np.median(values)))
                    pooled.append(values)
            if pooled:
                summaries.append((group, medians, np.concatenate(pooled)))
        if len(summaries) < 2:
            continue
        replicated = all(len(m) >= 2 for _g, m, _p in summaries)
        try:
            if replicated:
                p = float(_stats.f_oneway(*[m for _g, m, _p in summaries])[1])
                method = "ANOVA on replicate medians"
            else:
                p = float(_stats.kruskal(*[pl for _g, _m, pl in summaries])[1])
                method = "Kruskal-Wallis on particles"
        except Exception:
            continue
        if not np.isfinite(p):
            continue
        centres = sorted(((float(np.median(m)) if m else float(np.median(pl)), g)
                          for g, m, pl in summaries), key=lambda c: c[0])
        (lo_c, lo_g), (hi_c, hi_g) = centres[0], centres[-1]
        spreads = [max(m) - min(m) for _g, m, _p in summaries if len(m) >= 2]
        tests.append((symbol, num, den, p, hi_c - lo_c, max(spreads) if spreads else 0.0,
                      hi_g, lo_g, 10 ** hi_c, 10 ** lo_c, method))
    if not tests:
        return []
    significant, adjusted = rr._benjamini_hochberg([t[3] for t in tests])
    kept = [(t, float(adjusted[k])) for k, t in enumerate(tests)
            if significant[k] and 10 ** t[4] - 1 >= ISOTOPE_GROUP_MIN_GAP
            and t[4] > REPLICATE_MARGIN * t[5]]
    kept.sort(key=lambda x: -x[0][4])
    out = []
    for (symbol, num, den, _p, gap, spread, hi_g, lo_g, hi_v, lo_v, method), q in kept[:3]:
        rep = (f", more than the {10 ** spread - 1:.1%} spread between replicates"
               if spread > 0 else "")
        out.append(rr.Suggestion(
            title=f"{num}/{den}: {hi_g.name} vs {lo_g.name}",
            reasoning=(
                f"The median {num}/{den} is {hi_v:.4g} in {hi_g.name} and {lo_v:.4g} in "
                f"{lo_g.name}, {10 ** gap - 1:.1%} apart{rep}. Both are {symbol} isotopes, so "
                f"this is a difference in isotope signature, not in how much {symbol} there "
                f"is. {method}, {rr._fmt_q(q)}."
            ),
            category="isotope",
            confidence=min(0.6 + (10 ** gap - 1) * 3.0, 0.93),
            explain_key="isotope_groups",
            details=[(f"Median in {hi_g.name}", f"{hi_v:.4g}"),
                     (f"Median in {lo_g.name}", f"{lo_v:.4g}"),
                     ("Difference", f"{10 ** gap - 1:.2%}"),
                     ("Spread between replicates", f"{10 ** spread - 1:.2%}" if spread else "no replicates"),
                     ("Test", method), ("False discovery", rr._fmt_q(q))],
            node_type="isotopic_ratio_plot",
            config=_ratio_config(num, den, den),
            elements=(num, den),
            **rr._group_selection([hi_g, lo_g]),
        ))
    return out
