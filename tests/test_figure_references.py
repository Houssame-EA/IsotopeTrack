"""Tests for reference compositions, ternary references, sunburst pies,
bubble dot plots and minor-element detectability in the Figure Builder."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results.figure_builder.core import references as R
from results.figure_builder.core.expressions import ParticleTable, evaluate
from results.figure_builder.core.limits import attach_limits, group_limit
from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec


@pytest.fixture(scope="module")
def app():
    """A Qt application for widgets and off-screen drawing."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def builtin_references():
    """Every test starts from the built-in reference values."""
    R.set_user({})
    yield
    R.set_user({})


def _table(particles, samples=("S",)):
    """A particle table over *particles* from *samples*."""
    data = {"type": "multiple_sample_data", "sample_names": list(samples), "particle_data": particles}
    return ParticleTable.from_input(data, "Counts")


def _render(panel, table):
    """Draw one panel off-screen and return its report."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    spec = default_spec()
    spec["panels"] = [make_panel(rect=[0, 0, 1, 1], **panel)]
    fig = Figure()
    FigureCanvasAgg(fig)
    return render(fig, normalise_spec(spec), table)


@pytest.mark.parametrize("formula, expected", [
    ("SiO2", {"Si": 1, "O": 2}),
    ("Al2Si2O5(OH)4", {"Al": 2, "Si": 2, "O": 9, "H": 4}),
    ("K0.65Al2.65Si3.35O10(OH)2", {"K": 0.65, "Al": 2.65, "Si": 3.35, "O": 12, "H": 2}),
    ("CaMg(CO3)2", {"Ca": 1, "Mg": 1, "C": 2, "O": 6}),
    ("CaSO4·2H2O", {"Ca": 1, "S": 1, "O": 6, "H": 4}),
])
def test_formulas_are_read(formula, expected):
    """Formulas with parentheses, decimals and hydrates give atoms per formula unit."""
    assert R.parse_formula(formula) == pytest.approx(expected)


@pytest.mark.parametrize("bad", ["", "Xx2O", "Al2(SiO4", "Al2)O3"])
def test_bad_formulas_are_refused(bad):
    """Unknown elements and unbalanced parentheses raise."""
    with pytest.raises(ValueError):
        R.parse_formula(bad)


def test_every_builtin_mineral_formula_reads():
    """The built-in minerals all parse."""
    for formula in R.MINERALS.values():
        assert R.parse_formula(formula)


def test_upper_crust_values_follow_the_source():
    """Oxides convert to element mass fractions; Al:Fe of the crust is 2.08."""
    crust = R.crust()
    assert crust["Si"] == pytest.approx(0.3113, rel=1e-3)
    assert crust["Al"] == pytest.approx(0.0815, rel=1e-3)
    assert crust["Fe"] == pytest.approx(0.0392, rel=1e-3)
    assert crust["Ti"] == pytest.approx(0.003836, rel=1e-3)
    assert crust["Ba"] == pytest.approx(628e-6)
    assert R.crust_ratio("Al", "Fe") == pytest.approx(2.08, abs=0.005)
    assert R.crust_ratio("48Ti", "Fe56") == pytest.approx(0.0979, abs=0.0005)
    molar = R.crust_ratio("Al", "Fe", "moles")
    assert molar == pytest.approx(2.08 * 55.845 / 26.982, rel=1e-3)


def test_user_values_replace_builtin_ones():
    """A changed crust value and an added mineral are used everywhere."""
    R.set_user({"crust": {"Ti": 7672}, "minerals": {"my clay": "Al2Si4O10(OH)2"}})
    assert R.crust_ratio("Ti", "Fe") == pytest.approx(2 * 0.0979, rel=0.01)
    assert R.composition("my clay", ["Al", "Si", "Fe"]) == pytest.approx([1 / 3, 2 / 3, 0.0])


def test_compositions_by_moles_and_mass():
    """Reference compositions are normalised in the requested basis."""
    assert R.composition("kaolinite", ["Al", "Si", "Fe"]) == pytest.approx([0.5, 0.5, 0.0])
    by_mass = R.composition("kaolinite", ["Al", "Si", "Fe"], "mass")
    assert by_mass[0] == pytest.approx(26.982 / (26.982 + 28.085), rel=1e-4)
    crust = R.composition("upper crust", ["Al", "Si", "Fe"])
    assert sum(crust) == pytest.approx(1.0) and crust[1] > crust[0] > crust[2]
    with pytest.raises(ValueError):
        R.composition("rutile", ["Al", "Si", "Fe"])


def test_reference_lists_are_split():
    """Names and labelled formulas are both accepted."""
    assert R.split_entries("kaolinite, my clay: K0.6Al2Si3O10(OH)2;upper crust") == [
        ("kaolinite", "kaolinite"), ("my clay", "K0.6Al2Si3O10(OH)2"), ("upper crust", "upper crust")]


def test_crust_ratio_inside_expressions():
    """crust() gives enrichment factors in any expression and refuses unquoted names."""
    from results.figure_builder.core.expressions import ExpressionError
    t = _table([{"elements": {"56Fe": 10, "48Ti": 2},
                 "element_mass_fg": {"56Fe": 1.0, "48Ti": 0.2}, "source_sample": "S"}])
    ef = evaluate('(mass:Ti / mass:Fe) / crust("Ti", "Fe")', t)
    assert ef[0] == pytest.approx(0.2 / R.crust_ratio("Ti", "Fe"))
    with pytest.raises(ExpressionError):
        evaluate("crust(Ti, Fe)", t)


def _clays(n=300, seed=3):
    """Particles with Al, Si and Fe in counts and moles."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        c = rng.dirichlet([3, 4, 1.2])
        out.append({"elements": {"27Al": c[0] * 100, "28Si": c[1] * 100, "56Fe": c[2] * 100},
                    "element_moles_fmol": {"27Al": c[0], "28Si": c[1], "56Fe": c[2]},
                    "source_sample": "S"})
    return out


def test_ternary_draws_references_in_moles(app):
    """Minerals, the crust and a bulk value are placed on a molar ternary."""
    rep = _render({"kind": "ternary", "a": "moles:Al", "b": "moles:Si", "c": "moles:Fe",
                   "tern_refs": "kaolinite, fayalite, upper crust, mine: Al2Si4O10(OH)2",
                   "tern_bulk": "1, 1.6, 0.5"}, _table(_clays()))
    assert not rep.errors
    line = next(s for s in rep.stats if s.startswith("Reference points"))
    assert "kaolinite (50/50/0 %)" in line and "fayalite (0/33/67 %)" in line and "mine" in line


def test_ternary_refuses_references_in_counts(app):
    """Counts depend on sensitivity, so references are not drawn on them."""
    rep = _render({"kind": "ternary", "a": "Al", "b": "Si", "c": "Fe", "tern_refs": "kaolinite"},
                  _table(_clays()))
    assert not rep.errors
    assert any("moles or mass" in s for s in rep.stats)


def _signatures():
    """Ce particles often with La, Fe with Al, Ti alone; masses carried too."""
    rng = np.random.default_rng(1)
    out = []
    for i in range(400):
        if i % 4 < 2:
            e, m = {"140Ce": 900.0}, {"140Ce": 9.0}
            if i % 4 == 0:
                e["139La"], m["139La"] = 2000.0, 4.0
        elif i % 4 == 2:
            e, m = {"56Fe": 50.0, "27Al": 400.0}, {"56Fe": 5.0, "27Al": 1.0}
        else:
            e, m = {"48Ti": 30.0}, {"48Ti": 2.0}
        out.append({"elements": e, "element_mass_fg": m, "source_sample": "S"})
    return out


def test_sunburst_uses_mass_for_the_main_element(app):
    """La has more counts than Ce but less mass, so Ce is the main element."""
    from results.figure_builder.charts.categorical import sunburst_items
    t = _table(_signatures())
    inner, outer, basis, n = sunburst_items(make_panel(kind="pie", pie_mode="sunburst"), t)
    assert basis == "mass" and n == 400
    assert dict(inner) == pytest.approx({"Ce": 200, "Fe": 100, "Ti": 100})
    assert dict(outer["Ce"]) == pytest.approx({"+ La": 100, "alone": 100})
    assert dict(outer["Fe"]) == pytest.approx({"+ Al": 100})
    rep = _render({"kind": "pie", "pie_mode": "sunburst"}, t)
    assert not rep.errors and rep.stats[0].startswith("Sunburst, main element by mass")


def test_bubble_dot_plot_colours_and_sizes(app):
    """Rows by sample, colour by combination, size by element count, horizontal."""
    from results.figure_builder.charts.extra import strip_colour_groups
    parts = _signatures()
    for i, p in enumerate(parts):
        p["source_sample"] = "A" if i % 2 else "B"
    t = _table(parts, ("A", "B"))
    panel = make_panel(kind="strip", value="Ce", group_by="sample", strip_color="combination")
    groups = strip_colour_groups(panel, t, np.ones(len(t), dtype=bool))
    assert {name for name, _c, _m in groups} >= {"Ce", "Ce + La"}
    rep = _render({"kind": "strip", "value": "mass:Ce", "group_by": "sample",
                   "strip_color": "combination", "strip_size": "n_elements",
                   "strip_horizontal": True, "log_y": True}, t)
    assert not rep.errors
    rep = _render({"kind": "strip", "value": "Ce", "group_by": "sample", "strip_color": "rules",
                   "rules": [{"name": "with La", "when": "La > 0", "color": "#ff0000"}]}, t)
    assert not rep.errors


def _fe_ti(samples=("S1", "S2")):
    """Fe–Al particles; Ti only shows in the larger ones."""
    rng = np.random.default_rng(8)
    out = []
    for s in samples:
        for _ in range(400):
            fe = rng.lognormal(np.log(0.4), 1.0)
            e, m = {"56Fe": fe * 100, "27Al": fe * 160}, {"56Fe": fe, "27Al": fe * 2.08}
            if fe > 0.5:
                e["48Ti"], m["48Ti"] = fe * 12, fe * 0.098
            out.append({"elements": e, "element_mass_fg": m, "source_sample": s,
                        "original_sample": s})
    return out


def test_needed_major_mass_is_the_minor_limit_over_the_ratio(app):
    """Fe needed to see Ti = MDL(Ti) / crustal Ti:Fe, per group from its own samples."""
    from results.figure_builder.charts.detectability import required_masses
    t = _table(_fe_ti(), ("S1", "S2"))
    t.detection_limits = {"48Ti": {"mass": {"S1": 0.03, "S2": 0.05}}}
    t.sample_members = {"S1": ["S1"], "S2": ["S2"]}
    sample = t.column("sample")
    panel = make_panel(kind="box", value="mass:Fe", ptl_minor="Ti")
    (minor, per_group, how), = required_masses(panel, t, "56Fe", [sample == "S1", sample == "S2"])
    ratio = R.crust_ratio("Ti", "Fe")
    assert minor == "Ti" and how == "upper-crust ratio"
    assert per_group == pytest.approx([0.03 / ratio, 0.05 / ratio])
    panel["ptl_ratio"] = "0.2"
    (_m, per_group, how), = required_masses(panel, t, "56Fe", [sample == "S1"])
    assert per_group == pytest.approx([0.15]) and "0.2" in how


def test_box_and_scatter_report_detectability(app):
    """Box plots report the share too small to show Ti; scatters where Ti becomes visible."""
    t = _table(_fe_ti(), ("S1", "S2"))
    t.detection_limits = {"48Ti": {"mass": {"S1": 0.03, "S2": 0.05}}}
    t.sample_members = {"S1": ["S1"], "S2": ["S2"]}
    rep = _render({"kind": "box", "value": "mass:Fe", "group_by": "sample", "log_y": True,
                   "ptl_minor": "Ti"}, t)
    assert not rep.errors
    assert any(s.startswith("Too small to show Ti") and "S1" in s for s in rep.stats)
    rep = _render({"kind": "scatter", "x": "mass:Fe", "y": "mass:Al", "log_x": True,
                   "log_y": True, "ptl_minor": "Ti", "crust_line": True}, t)
    assert not rep.errors
    need = 0.05 / R.crust_ratio("Ti", "Fe")
    assert any(f"{need:.3g} fg" in s for s in rep.stats)


@pytest.mark.parametrize("panel, message", [
    ({"kind": "box", "value": "Fe", "ptl_minor": "Ti"}, "one element's mass"),
    ({"kind": "box", "value": "mass:Fe", "ptl_minor": "Ti"}, "No calibrated mass detection limit"),
    ({"kind": "box", "value": "mass:Fe", "ptl_minor": "Zr"}, "not measured"),
])
def test_detectability_explains_why_nothing_is_drawn(app, panel, message):
    """Counts, missing limits and unmeasured elements each give a reason, not an error."""
    rep = _render(panel, _table(_fe_ti(("S1",)), ("S1",)))
    assert not rep.errors
    assert any(message in s for s in rep.stats)


def test_pooled_groups_use_their_members_limits():
    """A summed replicate group takes the highest limit among its replicates."""
    parts = [{"elements": {"48Ti": 5}, "source_sample": "Liver", "original_sample": f"Liver_{i}"}
             for i in (1, 2)]

    class Window:
        """Main-window stand-in."""

        selected_isotopes = {"Ti": [47.9479]}
        element_thresholds = {"Liver_1": {"Ti-47.9479": {"LOD_MDL": 4.0}},
                              "Liver_2": {"Ti-47.9479": {"LOD_MDL": 6.0}}}

        def get_formatted_label(self, key):
            """Mass number then symbol."""
            symbol, mass = key.split("-")
            return f"{round(float(mass))}{symbol}"

    t = _table(parts, ("Liver",))
    attach_limits(t, Window())
    assert t.sample_members == {"Liver": ["Liver_1", "Liver_2"]}
    assert group_limit(t, "counts", "48Ti") == pytest.approx(6.0)
    assert group_limit(t, "mass", "48Ti") is None


def test_reference_dialog_keeps_only_changes(app):
    """The dialog returns changed crust values and new minerals, and refuses bad ones."""
    from results.figure_builder.ui.references_dialog import ReferencesDialog
    dlg = ReferencesDialog()
    rows = {dlg.crust_table.item(r, 0).text(): r for r in range(dlg.crust_table.rowCount())}
    dlg.crust_table.item(rows["Ti"], 2).setText("4000")
    dlg._add_mineral()
    last = dlg.mineral_table.rowCount() - 1
    dlg.mineral_table.item(last, 0).setText("my clay")
    dlg.mineral_table.item(last, 1).setText("Al2Si4O10(OH)2")
    assert dlg.values() == {"crust": {"Ti": 4000.0}, "minerals": {"my clay": "Al2Si4O10(OH)2"}}
    dlg.crust_table.item(rows["Ti"], 2).setText("abc")
    with pytest.raises(ValueError):
        dlg.values()
    dlg._restore()
    assert dlg.values() == {"crust": {}, "minerals": {}}
