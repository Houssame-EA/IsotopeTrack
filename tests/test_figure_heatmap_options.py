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
    panel.setdefault("label_style", "symbol")
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
    m = matrix(table, heat_quantity="mass_pct", heat_col_order="mass", label_style="isotope")
    row = next(i for i, r in enumerate(m["rows"]) if r.startswith("$^{27}$Al"))
    cells = dict(zip(m["cols"], m["values"][row]))
    assert cells["$^{27}$Al"] == pytest.approx(40, abs=0.5)
    assert cells["$^{28}$Si"] == pytest.approx(50, abs=0.5)
    assert cells["$^{56}$Fe"] == pytest.approx(10, abs=0.5)
    assert m["label"] == "Mass %"


def test_columns_follow_atomic_number_by_default(app, table):
    """Columns run by atomic number unless another order is chosen."""
    cols = matrix(table, label_style="isotope")["cols"]
    assert cols == ["$^{27}$Al", "$^{28}$Si", "$^{48}$Ti", "$^{55}$Mn", "$^{56}$Fe",
                    "$^{139}$La", "$^{140}$Ce", "$^{146}$Nd"]


def test_rows_are_particle_combinations(app, table):
    """Rows are titled particle combinations and labelled like the canvas."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    spec = default_spec()
    spec["panels"] = [make_panel(kind="heatmap", heat_rows="combinations", rect=[0, 0, 1, 1],
                                 label_style="symbol")]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    ax = report.artists[spec["panels"][0]["id"]]["ax"]
    assert ax.get_ylabel() == "Particle combination"
    assert "Al, Si, Fe (100)" in report.artists[spec["panels"][0]["id"]]["matrix"]["rows"]


def test_columns_follow_isotope_mass(app, table):
    """Columns ordered by isotope mass run from Al to Nd."""
    cols = matrix(table, heat_col_order="mass", label_style="isotope")["cols"]
    assert cols[0] == "$^{27}$Al" and cols[-1] == "$^{146}$Nd"


def test_rows_ranked_by_one_element_and_searched(app, table):
    """Rows holding Fe, ranked by their Fe moles, with empty columns dropped."""
    m = matrix(table, heat_quantity="moles", heat_sort="element", heat_sort_el="Fe",
               heat_search="Fe", label_style="isotope")
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


def test_rows_ranked_by_the_total_of_one_element(app):
    """Rows follow the summed Pb mass, not the number of particles."""
    parts = []
    for _ in range(200):
        parts.append({"elements": {"208Pb": 10.0}, "element_mass_fg": {"208Pb": 0.025},
                      "source_sample": "S"})
    for _ in range(150):
        parts.append({"elements": {"208Pb": 50.0, "63Cu": 20.0},
                      "element_mass_fg": {"208Pb": 0.333, "63Cu": 0.1}, "source_sample": "S"})
    table = ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                     "particle_data": parts}, "Counts")
    by_count = matrix(table, heat_quantity="mass")["rows"]
    by_total = matrix(table, heat_quantity="mass", heat_sort="element_total",
                      heat_sort_el="Pb")["rows"]
    by_counts_total = matrix(table, heat_sort="element_total", heat_sort_el="Pb")["rows"]
    assert by_count[0] == "Pb (200)"
    assert by_total[0] == "Cu, Pb (150)"
    assert by_counts_total[0] == by_total[0]


def test_rows_ranked_by_the_mean_of_one_element(app):
    """Mean Pb per particle puts few heavy particles above many light ones."""
    parts = []
    for _ in range(200):
        parts.append({"elements": {"208Pb": 10.0}, "element_mass_fg": {"208Pb": 0.03},
                      "source_sample": "S"})
    for _ in range(20):
        parts.append({"elements": {"208Pb": 50.0, "63Cu": 20.0},
                      "element_mass_fg": {"208Pb": 0.2, "63Cu": 0.1}, "source_sample": "S"})
    table = ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                     "particle_data": parts}, "Counts")
    by_mean = matrix(table, heat_quantity="mass", heat_sort="element_mean",
                     heat_sort_el="Pb")["rows"]
    by_total = matrix(table, heat_quantity="mass", heat_sort="element_total",
                      heat_sort_el="Pb")["rows"]
    assert by_mean == ["Cu, Pb (20)", "Pb (200)"]
    assert by_total == ["Pb (200)", "Cu, Pb (20)"]


def test_label_style_applies_to_rows_and_columns(app, table):
    """The panel's isotope label style is used on both axes."""
    iso = matrix(table, label_style="isotope")
    assert "$^{27}$Al, $^{28}$Si, $^{56}$Fe (100)" in iso["rows"]
    assert iso["cols"][0] == "$^{27}$Al"
    sym = matrix(table, label_style="symbol")
    assert "Al, Si, Fe (100)" in sym["rows"]
    assert sym["cols"][0] == "Al"


def test_row_label_keeps_the_largest_elements(app, table):
    """With a limit of 2, a three-element row names its two largest and ends with '...'."""
    m = matrix(table, heat_quantity="mass", heat_max_label=2)
    assert "Al, Si, ... (100)" in m["rows"]
    assert "Ti, Fe, ... (120)" in m["rows"]
    assert "Fe (140)" in m["rows"]
    assert len(m["cols"]) == 8


def test_zero_rotation_is_kept(app, table):
    """A rotation of 0 leaves the column labels horizontal."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    spec = default_spec()
    spec["panels"] = [make_panel(kind="heatmap", heat_rows="combinations", rect=[0, 0, 1, 1],
                                 xtick_rotation=0)]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    ax = report.artists[spec["panels"][0]["id"]]["ax"]
    assert all(t.get_rotation() == 0 for t in ax.get_xticklabels())
