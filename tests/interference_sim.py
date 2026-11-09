"""Synthetic single-particle runs with known interferences, for testing the Insights check.

Particles are placed at random times in a run of time bins, each spread over
three bins, with Poisson noise. Every mass is detected against a 10.6-count
threshold and overlapping detections are merged into one particle, the way
the app builds multi-element particles. Masses that were not selected can be
kept per particle under ``run_masses``, as if read from the run files.
"""

import zlib

import numpy as np

THRESHOLD = 10.6
SHAPE = np.array([0.2, 0.55, 0.25])

TYPES = {
    "oxide": (lambda m: m + 16, 0.020, 1.0),
    "hydroxide": (lambda m: m + 17, 0.004, 1.0),
    "hydride/tail +1": (lambda m: m + 1, 0.003, 1.4),
    "tail -1": (lambda m: m - 1, 0.001, 1.4),
    "doubly charged": (lambda m: m // 2 if m % 2 == 0 else None, 0.020, 1.0),
}
"""Interference type: (child mass from parent mass, rate at 100 ions, growth power)."""

SKIP = {"Ar", "Ne", "Kr", "Xe", "He", "Rn", "Tc", "Np", "Pu", "Pm",
        "H", "Li", "Be", "B", "C", "N", "O", "F"}
"""Gases and elements without stable isotopes in the measured range."""

N_PARTICLES, N_BINS, MEDIAN = 2500, 200000, 1500
MUST_FLAG = 30
"""Detections a suspect mass needs before the check must find it."""


def abundances():
    """``{symbol: {mass number: fraction}}`` of the elements tested, from the app's table."""
    from results.insights.discovery import isotope_abundances
    out = {s: dict(a) for s, a in isotope_abundances().items() if s not in SKIP and a}
    return {s: a for s, a in out.items() if min(a) >= 19 and max(a) <= 240}


def owner(abund, mass, not_symbol):
    """The element with most of a nominal mass, other than *not_symbol*."""
    best = max(((a, s) for s, iso in abund.items() if s != not_symbol
                for n, a in iso.items() if n == mass), default=None)
    return best[1] if best else None


def population(rng, abund, n, element, median, sigma=1.0, extra=None):
    """Ions per particle of each mass for *n* particles of *element*.

    Args:
        rng: Random generator.
        abund: Isotope abundances.
        n: Number of particles.
        element: Main element.
        median: Median ions of the element per particle.
        sigma: Log-normal width.
        extra: ``{element: share of the main element's ions}`` carried as well.
    """
    out = []
    for total in rng.lognormal(np.log(median), sigma, n):
        ions = {}
        for el, f in [(element, 1.0)] + list((extra or {}).items()):
            for m, a in abund[el].items():
                ions[m] = ions.get(m, 0.0) + total * f * a
        out.append(ions)
    return out


def interfere(ions, rules):
    """Add ``(parent mass, child mass, rate, power)`` interferences to one particle."""
    out = dict(ions)
    for p, c, rate, power in rules:
        if p in ions:
            out[c] = out.get(c, 0.0) + rate * ions[p] * (ions[p] / 100.0) ** (power - 1.0)
    return out


def simulate(rng, abund, particles, labels, n_bins=N_BINS, saturate=None, run_masses=False):
    """Place, count and detect particles; return them as the app's particle dicts.

    Args:
        rng: Random generator.
        abund: Isotope abundances, used to name masses read from the run.
        particles: ``{mass: expected ions}`` per particle.
        labels: ``{mass: label}`` of the selected masses.
        n_bins: Length of the run.
        saturate: Ions above which the detector under-counts, or None.
        run_masses: Keep every other mass of the particles under ``run_masses``.
    """
    labels = dict(labels)
    hidden = set()
    if run_masses:
        hidden = {m for ions in particles for m in ions} - set(labels)
        labels.update({m: str(m) for m in hidden})
    masses = sorted(labels)
    sig = np.zeros((len(masses), n_bins))
    starts = rng.integers(0, n_bins - 3, len(particles))
    for s, ions in zip(starts, particles):
        for i, m in enumerate(masses):
            v = ions.get(m, 0.0)
            if v and saturate:
                v = v / (1.0 + v / saturate)
            if v:
                sig[i, s:s + 3] += v * SHAPE
    counts = rng.poisson(sig + 0.02).astype(float)
    above = counts > THRESHOLD
    for i, m in enumerate(masses):
        if m in hidden:
            above[i] = False
    seen = above.any(axis=0)
    grown = seen | np.r_[False, seen[:-1]] | np.r_[seen[1:], False]
    edges = np.diff(np.r_[0, grown.astype(np.int8), 0])
    out = []
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        elements, run = {}, {}
        for i, m in enumerate(masses):
            if m in hidden:
                run[m] = float(counts[i, a:b].sum())
            elif above[i, a:b].any():
                elements[labels[m]] = float(counts[i, a:b].sum())
        if elements:
            out.append({"elements": elements, **({"run_masses": run} if hidden else {})})
    return out


def case(abund, element, type_name, situation, seed=0):
    """Build one synthetic run of *element* making one interference type.

    Situations: ``"A"`` interference only; ``"B"`` no interference but real
    independent particles of the elements at the suspect masses; ``"C"`` those
    elements really inside the particles (10 %) on top of the interference;
    ``"D"`` like A, with the parent element not selected but read from the run.

    Returns:
        ``(particles, children, counts, real_share)``: the particle dicts, the
        suspect labels by mass, how many particles detected each suspect, and
        for situation C the share of each suspect's signal that is real.
        ``None`` when no other element sits at the suspect masses.
    """
    target, rate, power = TYPES[type_name]
    rules, children = [], {}
    for m in abund[element]:
        t = target(m)
        if not t:
            continue
        own = owner(abund, t, element)
        if own and t not in abund[element]:
            rules.append((m, t, rate, power))
            children[t] = f"{t}{own}"
    if not children:
        return None
    rng = np.random.default_rng(zlib.crc32(f"{element}{type_name}{situation}".encode()) + seed)
    parent_labels = {m: f"{m}{element}" for m in abund[element]}

    def own_particles(rules_, real=None):
        return [interfere(p, rules_) for p in population(rng, abund, N_PARTICLES, element, MEDIAN,
                                                          extra=real)]

    real_share = {}
    if situation == "A":
        parts, labels = own_particles(rules), {**parent_labels, **children}
    elif situation == "D":
        parts, labels = own_particles(rules), dict(children)
    elif situation == "B":
        parts = own_particles([])
        for sym in {lab[len(str(t)):] for t, lab in children.items()}:
            parts += population(rng, abund, 1500, sym, MEDIAN / 3)
        labels = {**parent_labels, **children}
    else:
        real = {lab[len(str(t)):]: 0.10 for t, lab in children.items()}
        parts, labels = own_particles(rules, real), {**parent_labels, **children}
        for m, t, r, _p in rules:
            lab = children[t]
            amount = 0.10 * abund[lab[len(str(t)):]].get(t, 0.0)
            real_share[lab] = amount / (amount + r * abund[element][m])
    particles = simulate(rng, abund, parts, labels, run_masses=True)
    counts = {lab: sum(lab in p["elements"] for p in particles) for lab in children.values()}
    return particles, list(children.values()), counts, real_share
