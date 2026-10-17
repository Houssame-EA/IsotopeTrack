"""Synthetic spICP-ToF-MS particle streams with known ground truth.

Used by the tests and by :mod:`results.ai.benchmark`. Each element's
particles arrive as an independent Poisson process with a log-normal size
distribution; events that overlap in time merge into one multi-element
event, exactly as two particles hitting the plasma together would. Anything
planted on top, a real Ce+La association, an Ag+Au alloy population, a
contamination burst, a sample whose Ce-La particles have another
composition, or a sample with non-natural Pb isotopes, is listed in
:class:`Truth`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DENSITY = {'48Ti': 4.23, '56Fe': 5.24, '140Ce': 7.22, '139La': 6.51,
           '107Ag': 10.49, '197Au': 19.3, '27Al': 3.95, '206Pb': 11.34, '207Pb': 11.34}
MOLAR = {'48Ti': 47.95, '56Fe': 55.93, '140Ce': 139.9, '139La': 138.9,
         '107Ag': 106.9, '197Au': 196.97, '27Al': 26.98, '206Pb': 205.97, '207Pb': 206.98}
SENSITIVITY = {'48Ti': 60.0, '56Fe': 45.0, '140Ce': 900.0, '139La': 850.0,
               '107Ag': 500.0, '197Au': 700.0, '27Al': 30.0, '206Pb': 1500.0, '207Pb': 1500.0}
PB_NATURAL = 1.0934
"""Natural 206Pb/207Pb atom ratio."""
PB_SHIFTED = 0.93
"""206Pb/207Pb of the planted non-natural lead, like ore or smelter lead."""
LA_CE_SHIFTED = 1.0
"""La/Ce mass ratio of the planted Ce-La particles of another composition (0.5 elsewhere)."""
LA_CE_SLOPE_SHIFTED = 0.7
"""How La scales with Ce in those particles (1.0 elsewhere)."""


@dataclass
class Truth:
    """What was planted in a synthetic stream.

    Attributes:
        samples (list): Sample names in order.
        span_s (float): Acquisition time of each run.
        ti_median_nm (dict): Median Ti diameter used per sample.
        burst (tuple): ``(sample, t_from, t_to)`` of the Fe contamination burst.
        alloy_sample (str): The only sample holding Ag+Au particles.
        lod_mass_fg (dict): Mass detection limit per element.
        associated (tuple): The element pair planted as one particle type.
        chance_pair (tuple): A pair that only meets by coincidence.
        cela_shift_sample (str): Sample whose Ce-La particles have another
            La/Ce ratio and La growing more slowly than Ce.
        pb_sample (str): Sample whose lead has a non-natural 206Pb/207Pb ratio.
    """

    samples: list = field(default_factory=list)
    span_s: float = 60.0
    ti_median_nm: dict = field(default_factory=dict)
    burst: tuple = ()
    alloy_sample: str = ''
    lod_mass_fg: dict = field(default_factory=dict)
    associated: tuple = ('140Ce', '139La')
    chance_pair: tuple = ('48Ti', '56Fe')
    cela_shift_sample: str = ''
    pb_sample: str = ''


def planted_defaults(samples, alloy_sample):
    """Which samples get the shifted Ce-La particles and the non-natural lead.

    The Ce-La shift goes to the second sample that has Ce-La particles, so
    there is always another one to compare with; the lead goes to the last
    sample, or the first when the last already has the Ce-La shift.

    Args:
        samples (list): Sample names.
        alloy_sample (str): The sample with Ag-Au instead of Ce-La particles.

    Returns:
        tuple: ``(cela_shift_sample, pb_sample)``.
    """
    with_cela = [s for s in samples if s != alloy_sample]
    shift = with_cela[1] if len(with_cela) > 1 else ''
    pb = samples[-1] if samples[-1] != shift else samples[0]
    return shift, pb


LOD_MASS_FG = {'48Ti': 0.12, '56Fe': 0.15, '140Ce': 0.02, '139La': 0.02,
               '107Ag': 0.05, '197Au': 0.05, '27Al': 0.6, '206Pb': 0.01, '207Pb': 0.01}


def _mass_fg(d_nm, rho):
    """Mass in fg of a sphere of diameter *d_nm* and density *rho*."""
    return rho * math.pi / 6.0 * d_nm ** 3 * 1e-6


def _diameter_nm(mass_fg, rho):
    """Diameter in nm of a sphere of mass *mass_fg* and density *rho*."""
    return (mass_fg / (rho * math.pi / 6.0 * 1e-6)) ** (1.0 / 3.0)


def _arrivals(rng, rate, span, start=0.0):
    """Poisson arrival times over ``[start, start + span)``."""
    n = rng.poisson(rate * span)
    return np.sort(rng.uniform(start, start + span, n))


def _events(rng, sample, truth, scale):
    """Draw the single-particle events of one sample before merging."""
    span = truth.span_s
    events = []

    def add(times, comp_fn):
        """Add one event per arrival time with the composition from *comp_fn*."""
        for t in times:
            events.append((float(t), float(rng.uniform(0.35e-3, 0.65e-3)), comp_fn()))

    ti_med = truth.ti_median_nm[sample]
    add(_arrivals(rng, 40 * scale, span),
        lambda: {'48Ti': _mass_fg(rng.lognormal(math.log(ti_med), 0.35), DENSITY['48Ti'])})
    add(_arrivals(rng, 25 * scale, span),
        lambda: {'56Fe': _mass_fg(rng.lognormal(math.log(55), 0.4), DENSITY['56Fe'])})
    if sample != truth.alloy_sample:
        shifted = sample == truth.cela_shift_sample
        m_ref = _mass_fg(45, DENSITY['140Ce'])

        def cela():
            """A Ce-La particle: La/Ce 0.5 at every size, or 1.0 with La growing more slowly in the shifted sample."""
            m = _mass_fg(rng.lognormal(math.log(45), 0.3), DENSITY['140Ce'])
            if shifted:
                la = m * LA_CE_SHIFTED * (m / m_ref) ** (LA_CE_SLOPE_SHIFTED - 1.0) * rng.normal(1.0, 0.08)
            else:
                la = m * rng.normal(0.5, 0.05)
            return {'140Ce': m, '139La': la}
        add(_arrivals(rng, 6 * scale, span), cela)
    else:
        def agau():
            """An Ag-Au alloy particle."""
            m = _mass_fg(rng.lognormal(math.log(60), 0.15), 14.0)
            f = rng.normal(0.6, 0.03)
            return {'107Ag': m * f, '197Au': m * (1 - f)}
        add(_arrivals(rng, 8 * scale, span), agau)
    if truth.burst and truth.burst[0] == sample:
        _, t0, t1 = truth.burst
        add(_arrivals(rng, 400 * scale, t1 - t0, t0),
            lambda: {'56Fe': _mass_fg(rng.lognormal(math.log(55), 0.4), DENSITY['56Fe'])})
    add(_arrivals(rng, 3 * scale, span),
        lambda: {'27Al': _mass_fg(rng.lognormal(math.log(120), 0.5), DENSITY['27Al'])})
    pb_atoms = PB_SHIFTED if sample == truth.pb_sample else PB_NATURAL
    f206 = pb_atoms * MOLAR['206Pb'] / (pb_atoms * MOLAR['206Pb'] + MOLAR['207Pb'])

    def lead():
        """A Pb particle split into its 206 and 207 isotopes."""
        m = _mass_fg(rng.lognormal(math.log(38), 0.35), DENSITY['206Pb'])
        return {'206Pb': m * f206, '207Pb': m * (1 - f206)}
    add(_arrivals(rng, 5 * scale, span), lead)
    events.sort(key=lambda e: e[0])
    return events


def _merge(events):
    """Merge events whose time windows overlap into multi-element events."""
    merged = []
    for t, w, comp in events:
        if merged and t < merged[-1][1]:
            last = merged[-1]
            last[1] = max(last[1], t + w)
            for el, m in comp.items():
                last[2][el] = last[2].get(el, 0.0) + m
        else:
            merged.append([t, t + w, dict(comp)])
    return merged


def _particle(sample, t0, t1, comp, rng, lod):
    """Build a particle dictionary shaped like the app's, or ``None`` below LOD."""
    comp = {el: m for el, m in comp.items() if m >= lod.get(el, 0.0)}
    if not comp:
        return None
    counts, mass, moles, diam = {}, {}, {}, {}
    for el, m in comp.items():
        counts[el] = max(1.0, rng.poisson(m * SENSITIVITY[el]))
        mass[el] = m
        moles[el] = m / MOLAR[el]
        diam[el] = _diameter_nm(m, DENSITY[el])
    tm = sum(mass.values())
    tmol = sum(moles.values())
    return {
        'start_time': t0, 'end_time': t1, 'source_sample': sample,
        'elements': counts, 'element_mass_fg': mass, 'element_moles_fmol': moles,
        'element_diameter_nm': diam, 'particle_mass_fg': dict(mass),
        'particle_diameter_nm': dict(diam),
        'mass_percentages': {el: 100.0 * v / tm for el, v in mass.items()},
        'mole_percentages': {el: 100.0 * v / tmol for el, v in moles.items()},
        'totals': {'total_element_mass_fg': tm, 'total_element_moles_fmol': tmol,
                   'total_particle_mass_fg': tm, 'total_particle_moles_fmol': tmol},
    }


def make_dataset(seed=11, scale=1.0):
    """Generate a three-sample stream and the truth behind it.

    Args:
        seed (int): Random seed; the same seed gives the same data.
        scale (float): Multiplies every arrival rate.

    Returns:
        tuple: ``(data_context, truth, limits)`` where ``data_context`` is
        shaped like a canvas multi-sample stream and ``limits`` like
        :meth:`results.ai.data.Dataset.limits`.
    """
    rng = np.random.default_rng(seed)
    samples = ['River_A', 'River_B', 'Spiked_C']
    shift, pb = planted_defaults(samples, 'Spiked_C')
    truth = Truth(samples=samples, span_s=60.0,
                  ti_median_nm={'River_A': 60.0, 'River_B': 62.0, 'Spiked_C': 95.0},
                  burst=('River_B', 20.0, 22.0), alloy_sample='Spiked_C',
                  lod_mass_fg=dict(LOD_MASS_FG), cela_shift_sample=shift, pb_sample=pb)
    particles = []
    for sample in truth.samples:
        for t0, t1, comp in _merge(_events(rng, sample, truth, scale)):
            p = _particle(sample, t0, t1, comp, rng, truth.lod_mass_fg)
            if p is not None:
                particles.append(p)
    dc = {'type': 'multiple_sample_data', 'sample_names': list(truth.samples),
          'particle_data': particles,
          'concentration_meta': {s: {'volume_ml': 0.5, 'dilution_factor': 10.0,
                                     'te_available': True} for s in truth.samples}}
    limits = {}
    for el, lod in truth.lod_mass_fg.items():
        limits[el] = {'mass_fg': {s: lod for s in truth.samples},
                      'diameter_nm': {s: _diameter_nm(lod, DENSITY[el]) for s in truth.samples},
                      'counts': {s: lod * SENSITIVITY[el] for s in truth.samples}}
    return dc, truth, limits
