"""Tests for the canvas-style heatmap options of the Figure Builder."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results.figure_builder.core.expressions import ParticleTable
from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec


@pytest.fixture(scope="module")
def app():
    """A Qt application for off-screen drawing."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def table():
    """Three particle kinds with fixed mass make-up, plus Fe alone."""
    rng = np.random.default_rng(3)
    recipes = [{"27Al": 0.4, "28Si": 0.5, "56Fe": 0.1}, {"48Ti": 0.47, "55Mn": 0.03, "56Fe": 0.5},
               {"56Fe": 1.0}, {"139La": 0.27, "140Ce": 0.54, "146Nd": 0.19}]
    parts = []
    for k, recipe in enumerate(recipes):
        for _ in range(100 + 20 * k):
            size = rng.lognormal(0, 0.5)
            mass = {el: size * share for el, share in recipe.items()}
            parts.append({"elements": {el: m * 100 for el, m in mass.items()},
                          "element_mass_fg": mass,
                          "element_moles_fmol": {el: m / 50 for el, m in mass.items()},
                          "source_sample": "S"})
    return ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                     "particle_data": parts}, "Counts")


def matrix(table, **panel):
    """Draw one heatmap panel and return its matrix record."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    spec = default_spec()
    spec["panels"] = [make_panel(kind="heatmap", heat_rows="combinations", rect=[0, 0, 1, 1],
                                 **panel)]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    assert not report.errors, report.errors
    return report.artists[spec["panels"][0]["id"]]["matrix"]


def test_mass_percent_gives_each_particles_make_up(app, table):
    """Element mass % cells are the per-particle shares of each element."""
    m = matrix(table, heat_quantity="mass_pct", heat_col_order="mass")
    row = next(i for i, r in enumerate(m["rows"]) if r.startswith("Al"))
    cells = dict(zip(m["cols"], m["values"][row]))
    assert cells["$^{27}$Al"] == pytest.approx(40, abs=0.5)
    assert cells["$^{28}$Si"] == pytest.approx(50, abs=0.5)
    assert cells["$^{56}$Fe"] == pytest.approx(10, abs=0.5)
    assert "Element mass %" in m["label"]


def test_columns_follow_isotope_mass(app, table):
    """Columns ordered by isotope mass run from Al to Nd."""
    cols = matrix(table, heat_col_order="mass")["cols"]
    assert cols[0] == "$^{27}$Al" and cols[-1] == "$^{146}$Nd"


def test_rows_ranked_by_one_element_and_searched(app, table):
    """Rows holding Fe, ranked by their Fe moles, with empty columns dropped."""
    m = matrix(table, heat_quantity="moles", heat_sort="element", heat_sort_el="Fe",
               heat_search="Fe")
    assert all("Fe" in r for r in m["rows"])
    fe = m["cols"].index("$^{56}$Fe")
    values = m["values"][:, fe]
    assert list(values) == sorted(values, reverse=True)
    assert not any("Ce" in c for c in m["cols"])


def test_exact_search_start_rank_and_min_share(app, table):
    """Exact match keeps only Fe alone; start rank and minimum share trim rows."""
    assert [r.split(" (")[0] for r in matrix(table, heat_search="Fe",
                                             heat_search_mode="exact")["rows"]] == ["Fe"]
    full = matrix(table)["rows"]
    assert matrix(table, heat_start=2)["rows"] == full[1:]
    shares = matrix(table, heat_quantity="mass", heat_min_share=20)["rows"]
    assert 0 < len(shares) < len(full)


def test_unknown_rank_element_is_explained(app, table):
    """Ranking by an element that is not a column gives a readable error."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    spec = default_spec()
    spec["panels"] = [make_panel(kind="heatmap", heat_rows="combinations", rect=[0, 0, 1, 1],
                                 heat_sort="element", heat_sort_el="Zr")]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    assert any("Zr" in str(e) for e in report.errors.values())
