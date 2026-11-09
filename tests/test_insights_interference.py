"""The Insights particle interference check, tested on synthetic runs with known truth.

Every element of the app's periodic table between m/z 19 and 240 is made to
produce each interference type (MO⁺, MOH⁺, MH⁺ or tail +1, tail −1, M²⁺) in
four situations: the interference alone (must be flagged), real independent
particles at the suspect masses (must not be flagged), the suspect element
really inside the particles (must not be called only an interference), and
the parent element not selected but read from the run (must be flagged).

A quick set runs by default. Set ``ITK_FULL_INTERFERENCE_SWEEP=1`` to run
every element with every type and situation (about 1,200 runs).
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from results.insights import engine as rr
from results.insights import discovery as disc
from tests import interference_sim as sim


class FakeScene:
    """Canvas scene without nodes."""

    def items(self):
        return []

    def selectedItems(self):
        return []


class FakeWindow:
    """Main window holding one synthetic sample."""

    def __init__(self, pool):
        self.sample_particle_data = pool


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test from contexts cached by its neighbours."""
    rr.invalidate_context_cache()
    yield
    rr.invalidate_context_cache()


@pytest.fixture(scope="module")
def abund():
    """Isotope abundances of the tested elements."""
    return sim.abundances()


def context(particles, name="S_1"):
    """Analysis context over one synthetic sample."""
    rr.invalidate_context_cache()
    return rr.build_context(FakeScene(), FakeWindow({name: particles}))


def judge(situation, flags, children, counts, real_share):
    """Return the problems with the check's verdict, empty when it is right."""
    status = {f["child"]: f["status"] for f in flags}
    flagged = {c for c, s in status.items() if s in ("interference", "partial")}
    must = {c for c, n in counts.items() if n >= sim.MUST_FLAG}
    problems = []
    if situation in ("A", "D"):
        problems += [f"missed {c}" for c in sorted(must - flagged)]
        problems += [f"flagged {c}, not a suspect" for c in sorted(flagged - set(children))]
    elif situation == "B":
        problems += [f"flagged real {c}" for c in sorted(flagged)]
    else:
        undecidable = {f["child"] for f in flags if f.get("sibling", 0) is None}
        mostly_real = {c for c, sh in real_share.items() if sh >= 0.8}
        problems += [f"called real {c} an interference" for c in sorted(flagged & must & mostly_real)
                     if c not in undecidable]
    return problems


QUICK = [(el, t, s) for el in ("Ti", "Ce", "Ba", "Mo", "Pt", "La", "V", "Gd", "Zn", "Pb")
         for t in sim.TYPES for s in "ABCD"]


def _cases():
    if os.environ.get("ITK_FULL_INTERFERENCE_SWEEP"):
        return [(el, t, s) for el in sorted(sim.abundances()) for t in sim.TYPES for s in "ABCD"]
    return QUICK


@pytest.mark.parametrize("element,type_name,situation", _cases())
def test_every_element_and_interference(abund, element, type_name, situation):
    """Each element, interference type and situation gets the right verdict."""
    built = sim.case(abund, element, type_name, situation)
    if built is None:
        pytest.skip("no other element at the suspect masses")
    particles, children, counts, real_share = built
    flags = disc.interference_flags(context(particles))
    assert judge(situation, flags, children, counts, real_share) == []


@pytest.mark.parametrize("situation", "ABCD")
def test_oxide_of_every_element(abund, situation):
    """MO⁺ of every element is judged right in every situation."""
    wrong = {}
    for element in sorted(abund):
        built = sim.case(abund, element, "oxide", situation)
        if built is None:
            continue
        particles, children, counts, real_share = built
        problems = judge(situation, disc.interference_flags(context(particles)), children, counts,
                         real_share)
        if problems:
            wrong[element] = problems
    assert wrong == {}


def tio2(rng, abund, n=3000, rate=0.026, median=700, extra=None, saturate=None, labels=None):
    """TiO₂ particles making TiO⁺ on every Ti isotope, detected as the app would."""
    rules = [(m, m + 16, rate, 1.0) for m in abund["Ti"]]
    parts = [sim.interfere(p, rules)
             for p in sim.population(rng, abund, n, "Ti", median, sigma=1.1, extra=extra)]
    labels = labels or {46: "46Ti", 47: "47Ti", 48: "48Ti", 49: "49Ti", 50: "50Ti",
                        62: "62Ni", 63: "63Cu", 64: "64Zn", 65: "65Cu", 66: "66Zn"}
    return sim.simulate(rng, abund, parts, labels, saturate=saturate, run_masses=True)


def statuses(particles):
    """``{suspect: status}`` of the check on one sample."""
    return {f["child"]: f["status"] for f in disc.interference_flags(context(particles))}


def test_tio2_flags_every_ti_oxide(abund):
    """TiO⁺ on Ni, Cu and Zn masses is flagged, in one Ti card per element."""
    parts = tio2(np.random.default_rng(1), abund)
    st = statuses(parts)
    assert {st.get(c) for c in ("63Cu", "64Zn", "65Cu", "66Zn")} == {"interference"}
    titles = [c.title for c in disc.analyse_interference(context(parts))]
    assert "64Zn and 66Zn particles may be Ti interferences" in titles


def test_saturating_parent_is_checked_on_a_minor_isotope(abund):
    """When ⁴⁸Ti saturates, the slope is checked on a less abundant Ti isotope."""
    parts = tio2(np.random.default_rng(2), abund, median=900, saturate=4000)
    flags = {f["child"]: f for f in disc.interference_flags(context(parts))}
    assert flags["64Zn"]["status"] == "interference"


def test_real_zno_particles_leave_a_partial_flag(abund):
    """TiO⁺ plus separate real ZnO particles gives a partial flag on ⁶⁴Zn."""
    rng = np.random.default_rng(3)
    labels = {m: f"{m}Ti" for m in abund["Ti"]} | {64: "64Zn"}
    rules = [(m, m + 16, 0.026, 1.0) for m in abund["Ti"]]
    parts = [sim.interfere(p, rules) for p in sim.population(rng, abund, 3000, "Ti", 700, sigma=1.1)]
    parts += sim.population(rng, abund, 2500, "Zn", 120)
    particles = sim.simulate(rng, abund, parts, labels, run_masses=True)
    st = statuses(particles)
    assert st["64Zn"] == "partial"
    card = next(c for c in disc.analyse_interference(context(particles)) if "64Zn" in c.title)
    assert "look like real Zn" in card.reasoning


def test_real_zn_inside_ti_particles_is_not_an_interference(abund):
    """Zn really inside Ti particles is seen on ⁶⁸Zn, which TiO⁺ cannot reach."""
    rng = np.random.default_rng(4)
    parts = tio2(rng, abund, extra={"Zn": 0.10})
    assert statuses(parts)["64Zn"] in ("excess", "real")
    assert statuses(parts)["63Cu"] == "interference"


def test_parent_read_from_the_run(abund):
    """With no Ti selected, ⁴⁸Ti read from the run still explains ⁶⁴Zn."""
    rng = np.random.default_rng(5)
    parts = tio2(rng, abund, labels={63: "63Cu", 64: "64Zn", 65: "65Cu", 66: "66Zn"})
    flags = {f["child"]: f for f in disc.interference_flags(context(parts))}
    assert flags["64Zn"]["status"] == "interference" and flags["64Zn"]["parent"] == "48Ti"
    assert flags["64Zn"]["from_run"]
    card = next(c for c in disc.analyse_interference(context(parts)) if "64Zn" in c.title)
    assert "48Ti was not selected" in card.reasoning


def test_a_flagged_mass_is_never_a_parent(abund):
    """¹⁵⁷Gd is CeOH⁺ from ¹⁴⁰Ce, not an oxide of ¹⁴¹Pr, which is itself the Ce tail."""
    rng = np.random.default_rng(6)
    rules = [(140, 156, 0.045, 1.0), (142, 158, 0.045, 1.0), (140, 157, 0.003, 1.0),
             (140, 141, 0.0025, 1.5), (140, 139, 0.0008, 1.5)]
    parts = [sim.interfere(p, rules) for p in sim.population(rng, abund, 10000, "Ce", 500)]
    labels = {139: "139La", 140: "140Ce", 141: "141Pr", 142: "142Ce",
              156: "156Gd", 157: "157Gd", 158: "158Gd"}
    flags = {f["child"]: f for f in disc.interference_flags(context(sim.simulate(rng, abund, parts, labels)))}
    assert flags["157Gd"]["parent"] == "140Ce"
    assert {flags[c]["status"] for c in ("141Pr", "156Gd", "157Gd", "158Gd")} == {"interference"}


@pytest.mark.parametrize("label", ["Ti and independent Zn, dense run", "brass", "Ce and real Gd"])
def test_real_elements_are_not_flagged(abund, label):
    """Chance overlaps, fixed-ratio alloys and separate particles give no flag."""
    rng = np.random.default_rng(7)
    if label.startswith("Ti"):
        parts = sim.population(rng, abund, 3000, "Ti", 700) + sim.population(rng, abund, 3000, "Zn", 150)
        particles = sim.simulate(rng, abund, parts, {48: "48Ti", 64: "64Zn", 66: "66Zn"}, n_bins=40000)
    elif label == "brass":
        parts = sim.population(rng, abund, 3000, "Cu", 300, extra={"Zn": 0.6})
        particles = sim.simulate(rng, abund, parts, {63: "63Cu", 64: "64Zn", 65: "65Cu", 66: "66Zn"})
    else:
        parts = sim.population(rng, abund, 3000, "Ce", 500) + sim.population(rng, abund, 1500, "Gd", 200)
        particles = sim.simulate(rng, abund, parts, {140: "140Ce", 156: "156Gd", 157: "157Gd"})
    flagged = [c for c, s in statuses(particles).items() if s in ("interference", "partial")]
    assert flagged == []


def test_too_few_particles_give_no_card(abund):
    """A few small Ti particles are not enough to judge."""
    parts = tio2(np.random.default_rng(8), abund, n=300, median=80)
    assert disc.analyse_interference(context(parts)) == []


def test_interference_entry_gathers_particle_and_spectrum_cards(abund):
    """The list's Interference entry holds the particle cards and the spectrum cards."""
    assert rr.NODE_TYPE_META["interference"] == "Interference"
    assert "spectrum_view" not in rr.NODE_TYPE_META
    particle = disc.analyse_interference(context(tio2(np.random.default_rng(9), abund)))[0]
    spectrum = rr.Suggestion("t", "r", "spectrum", 0.8, "interference")
    other = rr.Suggestion("t", "r", "correlation", 0.8, "correlation_plot")
    assert rr.shows_in(particle, "interference") and rr.shows_in(spectrum, "interference")
    assert not rr.shows_in(other, "interference")
    assert set(rr.analysers_for({"interference"})) == {"interference", "spectrum"}
