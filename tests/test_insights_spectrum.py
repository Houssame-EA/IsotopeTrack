"""Tests for the Insights spectrum checks on resolved Nu spectra."""

from __future__ import annotations

import math

import numpy as np
import pytest

from results.insights import engine as rr
from results.insights import figures as F
from results.insights import spectrum as SP
from tests.figure_checks import render_problems, table_for

RATE = 2.0
"""Digitizer rate of the synthetic run, GS/s."""

A, B = 4.4, 3.5e-5
"""Mass calibration of the synthetic run: sqrt(m/z) = A + B·t."""

N_POINTS = 200_000

AREA = 50.0
"""Single ion area of the synthetic run."""

RESOLUTION = 2500


def flight_time(mz: float) -> float:
    """Flight time of an m/z in the synthetic run, in ns."""
    return (math.sqrt(mz) - A) / B


def run_info(masses) -> dict:
    """A Nu run.info with one integration region per mass, ±0.06 Da."""
    regions = []
    for m in masses:
        regions.append({"Start": flight_time(m - 0.06), "End": flight_time(m + 0.06),
                        "Baseline1Start": flight_time(m - 0.3), "Baseline1End": flight_time(m - 0.2),
                        "Baseline2Start": flight_time(m + 0.2), "Baseline2End": flight_time(m + 0.3)})
    return {"MassCalCoefficients": [A, B], "SampleRateGsSec": RATE,
            "SegmentInfo": [{"AcquisitionTriggerDelayNs": 0.0}],
            "IntegrationRegions": regions, "AverageSingleIonArea": AREA}


def spectrum(peaks) -> dict:
    """A summed spectrum with Gaussian peaks ``(m/z, ions)`` at the run's resolution."""
    mz = (A + B * np.arange(N_POINTS) / RATE) ** 2
    y = np.zeros(N_POINTS)
    for centre, ions in peaks:
        sigma = centre / RESOLUTION / 2.3548
        step = 2 * math.sqrt(centre) * B / RATE
        y += ions * AREA * step / (sigma * math.sqrt(2 * math.pi)) * np.exp(
            -0.5 * ((mz - centre) / sigma) ** 2)
    return {"spectrum": y.astype(np.float32), "n_snapshots": 60}


ISOTOPES = [("24Mg", 23.9850), ("27Al", 26.9815), ("28Si", 27.9769), ("56Fe", 55.9349),
            ("63Cu", 62.9296)]


def source(name, peaks, offset=0.0) -> SP.SpectrumSource:
    """A sample whose spectrum holds *peaks*, all moved by a calibration *offset*."""
    return SP.SpectrumSource(name, run_info([m for _l, m in ISOTOPES]),
                             entry=spectrum([(m + offset, n) for m, n in peaks]))


def clean_peaks(ions=5000):
    """Every isotope at its exact mass."""
    return [(m, ions) for _l, m in ISOTOPES]


class Ctx:
    """The parts of an analysis context the spectrum detector reads."""

    def __init__(self, sources, labels=()):
        self.cache = {SP.SOURCES_KEY: {"samples": sources, "isotopes": ISOTOPES}}
        self.matrix = {label: np.ones(3) for label, _m in ISOTOPES}
        self.scope = type("Scope", (), {"labels": tuple(labels)})()
        self.sample_names = [s.sample for s in sources]
        self.focus = ""

    def involves(self, *labels):
        return True

    def cap(self, n):
        return n


def test_clean_spectrum_has_nothing_to_report():
    """Peaks at their exact masses give no card."""
    assert SP.analyse(Ctx([source("S1", clean_peaks())])) == []


def test_calibration_offset_alone_is_not_an_interference():
    """Every peak moved by the same amount is the mass calibration, not an interference."""
    assert SP.analyse(Ctx([source("S1", clean_peaks(), offset=0.012)])) == []


def test_peak_pulled_toward_arO_is_flagged_on_56Fe():
    """An unresolved ArO⁺ pulls the 56Fe peak up, and the card names it."""
    peaks = [p for p in clean_peaks() if abs(p[0] - 55.9349) > 0.1]
    peaks += [(55.9349, 1500), (55.957, 4000)]
    found = SP.analyse(Ctx([source("S1", peaks, offset=0.004), source("S2", clean_peaks())]))
    shift = [s for s in found if s.explain_key == "spectrum_shift"]
    assert len(shift) == 1
    s = shift[0]
    assert s.category == "interference" and s.elements == ("56Fe",)
    assert s.node_type == "interference"
    assert s.samples == ("S1",)
    assert "⁴⁰Ar¹⁶O⁺" in s.title and "above" in s.title
    assert "1 of 2 samples" in s.reasoning
    assert s.facts["spectrum"]["marks"][0]["label"] == "⁴⁰Ar¹⁶O⁺"
    assert s.evidence is not None and s.evidence.effect.startswith("+")


def test_second_peak_inside_the_window_is_flagged():
    """A partly resolved N₂⁺ peak next to 28Si is named, inside the integration window."""
    peaks = clean_peaks() + [(28.0061, 2000)]
    found = SP.analyse(Ctx([source("S1", peaks)]))
    near = [s for s in found if s.explain_key == "spectrum_neighbour"]
    assert len(near) == 1
    s = near[0]
    assert s.elements == ("28Si",) and "¹⁴N₂⁺" in s.title
    assert "inside its integration window" in s.reasoning
    height = dict(s.details)["Height of second peak"]
    assert 30 <= int(height.rstrip("%")) <= 50


def test_weak_peaks_are_not_judged():
    """Too few ions make a peak's centre meaningless, so nothing is said about it."""
    peaks = [(m, 60) for _l, m in ISOTOPES if _l != "56Fe"] + [(55.957, 60)]
    assert SP.analyse(Ctx([source("S1", peaks)])) == []


def test_no_spectrum_no_cards():
    """Samples without raw snapshots (TOFWERK, CSV) are skipped quietly."""
    plain = SP.SpectrumSource("S1", {"SegmentInfo": []})
    assert SP.analyse(Ctx([plain])) == []
    assert SP.analyse(Ctx([])) == []


def test_node_limited_to_other_isotopes_skips_the_card():
    """A node that does not send 56Fe gets no 56Fe card."""
    peaks = [p for p in clean_peaks() if abs(p[0] - 55.9349) > 0.1] + [(55.957, 5000)]
    assert SP.analyse(Ctx([source("S1", peaks)], labels=("28Si", "27Al"))) == []


def test_known_species_include_isobars_and_doubly_charged():
    """Isobars and M²⁺ come from the isotope table, polyatomics from the database."""
    names = {name for name, _mz, _k in SP.known_species("56Fe", 55.9349)}
    assert "⁴⁰Ar¹⁶O⁺" in names
    assert not any("Fe" in n for n in names)
    assert any(k == "isobaric" for _n, _m, k in SP.known_species("58Ni", 57.9353))
    assert any(k == "doubly_charged" for _n, _m, k in SP.known_species("69Ga", 68.9256))


def test_spectrum_detector_is_registered_under_interferences():
    """The detector runs with the others and lists its cards under Interferences."""
    from results.insights.panel import section_of
    assert "spectrum" in rr.category_keys()
    assert section_of("interference") == "Interferences"


def test_explained_figure_draws_the_spectra():
    """The explained figure has the worst sample, then every sample, and draws."""
    peaks = [p for p in clean_peaks() if abs(p[0] - 55.9349) > 0.1]
    peaks += [(55.9349, 1500), (55.957, 4000)]
    found = SP.analyse(Ctx([source("S1", peaks), source("S2", peaks)]))
    s = next(s for s in found if s.explain_key == "spectrum_shift")
    ctx = F.context_from([{"elements": {"56Fe": 10.0}}] * 20, ["56Fe"], multi_sample=True)
    spec = F.figure_for(s, ctx)
    kinds = [p["kind"] for p in spec["panels"]]
    assert kinds == ["spectrum", "spectrum", "text"]
    assert set(spec["panels"][1]["spectra"]) == {"S1", "S2"}
    assert spec["panels"][1]["spec_normalise"] is True
    data = {"type": "sample_data", "particle_data": [{"elements": {"56Fe": 10.0}}] * 20,
            "sample_name": "S1"}
    assert render_problems(spec, table_for(data, "Counts")) == []


def test_spectrum_panel_without_data_says_where_it_comes_from():
    """Picking the spectrum kind by hand explains that it needs an Insights card."""
    from results.figure_builder.core.spec import default_spec, make_panel
    spec = default_spec()
    spec["panels"] = [make_panel(rect=[0, 0, 1, 1], kind="spectrum")]
    data = {"type": "sample_data", "particle_data": [{"elements": {"56Fe": 10.0}}] * 5,
            "sample_name": "S1"}
    problems = render_problems(spec, table_for(data, "Counts"))
    assert problems and "Insights spectrum card" in problems[0]


def test_panel_collects_sources_from_the_main_window():
    """The panel passes each Nu sample's run info, folder, spectrum and the isotopes."""
    from results.insights.panel import spectrum_sources

    class Window:
        selected_isotopes = {"Fe": [55.9349], "Si": [27.9769]}
        sample_run_info = {"S1": run_info([55.9349]), "S2": {"SegmentInfo": []}}
        sample_to_folder_map = {"S1": "/data/S1"}
        sample_raw_spectrum = {}

        def get_formatted_label(self, key):
            element, mass = key.split("-")
            return f"{round(float(mass))}{element}"

    out = spectrum_sources(Window(), ["S1", "S2"])
    assert [s.sample for s in out["samples"]] == ["S1"]
    assert out["samples"][0].folder == "/data/S1"
    assert ("56Fe", 55.9349) in out["isotopes"] and ("28Si", 27.9769) in out["isotopes"]


def test_spectrum_cards_are_not_crowded_out_by_figure_builder_cards():
    """Spectrum cards have their own limit, apart from the Figure Builder cards."""
    peaks = [p for p in clean_peaks() if abs(p[0] - 55.9349) > 0.1]
    peaks += [(55.957, 5000), (28.0061, 2000)]
    found = SP.analyse(Ctx([source("S1", peaks)]))
    others = [rr.Suggestion(f"figure {i}", "r", "time", 0.99, "figure_builder",
                            elements=("56Fe",), samples=("S1",)) for i in range(6)]
    kept = rr._dedupe_suggestions(found + others)
    assert sum(s.node_type == "interference" for s in kept) == len(found) == 2


LA = 138.9064
GD155 = 154.9226
LA_O = LA + 15.99491


HEAVY_DELAY = flight_time(125.0)
"""Trigger delay that starts the heavy synthetic runs at m/z 125."""


def heavy_spectrum(peaks) -> dict:
    """A summed spectrum from m/z 125 with Gaussian peaks ``(m/z, ions)``."""
    t = HEAVY_DELAY + np.arange(N_POINTS) / RATE
    mz = (A + B * t) ** 2
    y = np.zeros(N_POINTS)
    for centre, ions in peaks:
        sigma = centre / RESOLUTION / 2.3548
        step = 2 * math.sqrt(centre) * B / RATE
        y += ions * AREA * step / (sigma * math.sqrt(2 * math.pi)) * np.exp(
            -0.5 * ((mz - centre) / sigma) ** 2)
    return {"spectrum": y.astype(np.float32), "n_snapshots": 60}


def la_run(name, la_ions=400000, oxide=0.04):
    """A run holding only La and its oxide, with a window on every mass 130–160."""
    info = run_info([float(m) for m in range(130, 161)])
    info["SegmentInfo"] = [{"AcquisitionTriggerDelayNs": HEAVY_DELAY}]
    peaks = [(LA, la_ions), (LA_O, la_ions * oxide)] if la_ions else []
    return SP.SpectrumSource(name, info, entry=heavy_spectrum(peaks))


def test_isotope_made_of_an_oxide_gets_a_share_card():
    """155Gd in a La solution is LaO⁺, and the card says how much."""
    isotopes = [("139La", LA), ("155Gd", GD155)]
    ctx = Ctx([la_run("S1")])
    ctx.cache[SP.SOURCES_KEY]["isotopes"] = isotopes
    ctx.matrix = {"139La": np.ones(3), "155Gd": np.ones(3)}
    found = SP.analyse(ctx)
    share = [s for s in found if s.explain_key == "spectrum_share"]
    assert len(share) == 1
    s = share[0]
    assert s.elements == ("155Gd",) and "¹³⁹La¹⁶O⁺" in s.title and "mostly" in s.title
    assert not any(f.explain_key == "spectrum_shift" and f.elements == ("155Gd",) for f in found)
    assert s.facts["spectrum"]["marks"][0]["label"].startswith("¹³⁹La¹⁶O⁺")


def test_insights_and_spectrum_view_share_one_identification():
    """The card reuses the Spectrum view's identification instead of making its own."""
    from utils import interference_detection as idet
    run = la_run("S1")
    ident = idet.identify_run(run.entry, run.run_info)
    assert set(ident.amounts) == {"La"}
    run.identification = (ident, None)
    assert SP.identify(run, {}) is run.identification


def test_closest_blank_is_used():
    """A loaded blank run is compared with, and named on the card."""
    run = la_run("S1")
    blank = la_run("Blank", la_ions=0)
    ident, name = SP.identify(run, {"Blank": blank})
    assert name == "Blank" and ident.blank_used


def test_known_species_follow_the_elements_present():
    """Oxides are listed only for elements found in the sample."""
    everyone = {n for n, _m, _k in SP.known_species("155Gd", GD155)}
    with_la = {n for n, _m, _k in SP.known_species("155Gd", GD155, ["La"])}
    without = {n for n, _m, _k in SP.known_species("155Gd", GD155, ["Ce"])}
    assert "¹³⁹La¹⁶O⁺" in everyone and "¹³⁹La¹⁶O⁺" in with_la
    assert "¹³⁹La¹⁶O⁺" not in without
