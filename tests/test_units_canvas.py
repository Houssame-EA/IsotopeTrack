"""The canvas, its figures, the Figure Builder, Insights and clustering follow the app's units.

Figures receive the particles in the chosen units and name those units;
the main window's particles, filters and classifiers stay in fg, fmol and nm.
"""

import types

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

import utils.unit as unit_mod
from utils.unit import ExportUnits


@pytest.fixture(scope="module")
def qapp():
    """The Qt application."""
    return QApplication.instance() or QApplication([])


def particle(fe_fg=2000.0, d_nm=50.0):
    """One particle in the base units, as the main window builds it."""
    return {"elements": {"56Fe": 500.0},
            "element_mass_fg": {"56Fe": fe_fg}, "particle_mass_fg": {"56Fe": fe_fg * 2},
            "element_moles_fmol": {"56Fe": 3.0}, "particle_moles_fmol": {"56Fe": 3.0},
            "element_diameter_nm": {"56Fe": d_nm}, "particle_diameter_nm": {"56Fe": d_nm},
            "totals": {"total_element_mass_fg": fe_fg, "total_particle_mass_fg": fe_fg * 2,
                       "total_element_moles_fmol": 3.0, "total_particle_moles_fmol": 3.0}}


def test_canvas_data_is_converted_without_touching_the_main_window():
    """Figures get pg and µm; the main window keeps fg and nm."""
    unit_mod.units.set(ExportUnits(mass_unit="pg", diameter_unit="µm", moles_unit="amol"))
    source = {"type": "sample_data", "particle_data": [particle()]}
    shown = unit_mod.units.convert_input(source)
    p = shown["particle_data"][0]
    assert p["element_mass_fg"]["56Fe"] == pytest.approx(2.0)
    assert p["particle_mass_fg"]["56Fe"] == pytest.approx(4.0)
    assert p["element_diameter_nm"]["56Fe"] == pytest.approx(0.05)
    assert p["element_moles_fmol"]["56Fe"] == pytest.approx(3000.0)
    assert p["totals"]["total_element_mass_fg"] == pytest.approx(2.0)
    assert p["elements"]["56Fe"] == 500.0
    assert source["particle_data"][0]["element_mass_fg"]["56Fe"] == 2000.0


def test_base_units_hand_the_same_data_through():
    """With fg, fmol, nm and ppb chosen, nothing is copied or changed."""
    source = {"type": "sample_data", "particle_data": [particle()]}
    assert unit_mod.units.convert_input(source) is source


def test_data_type_list_shows_units_but_keeps_saved_names(qapp):
    """The list reads Element Mass (pg) while the code and project see Element Mass (fg)."""
    from widget.unit_combo import UnitComboBox
    combo = UnitComboBox()
    combo.addItems(["Counts", "Element Mass (fg)", "Element Diameter (nm)"])
    combo.setCurrentText("Element Mass (fg)")
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    assert combo.currentText() == "Element Mass (fg)"
    assert combo.itemData(combo.currentIndex(), 0) == "Element Mass (pg)"
    assert combo.findText("Element Diameter (nm)") == 2
    unit_mod.units.set(ExportUnits())
    assert combo.itemData(1, 0) == "Element Mass (fg)"


def test_figure_nodes_receive_the_chosen_units(qapp):
    """A box plot node stores the particles in the chosen mass unit."""
    from results.results_box_plot import BoxPlotNode
    unit_mod.units.set(ExportUnits(mass_unit="ng"))
    node = BoxPlotNode()
    node.process_data({"type": "sample_data", "particle_data": [particle(2e6)]})
    assert node.input_data["particle_data"][0]["element_mass_fg"]["56Fe"] == pytest.approx(2.0)


def test_canvas_redraws_every_figure_when_units_change(qapp):
    """Choosing other units sends the data through the canvas again."""
    from widget.canvas_widgets import EnhancedCanvasScene
    scene = EnhancedCanvasScene()
    calls = []
    scene.flush_data_flow = lambda: calls.append(1)
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    assert calls == [1]


def test_figure_builder_names_and_limits_follow_units(qapp):
    """Axis names read pg and the drawn MDL is converted with the particles."""
    from results.figure_builder.core import limits
    from results.figure_builder.core.expressions import ParticleTable, pretty
    unit_mod.units.set(ExportUnits(mass_unit="pg", diameter_unit="µm"))
    data = unit_mod.units.convert_input({"type": "sample_data", "sample_name": "S",
                                         "particle_data": [particle(), particle(4000.0)]})
    table = ParticleTable.from_input(data, "Element Mass (fg)")
    assert pretty("Fe", table, with_unit=True).endswith("(pg)")
    assert pretty("d:Fe", table, with_unit=True).endswith("(µm)")
    shown = limits._in_display_units({"56Fe": {"mass": {"S": 1000.0}, "d": {"S": 40.0},
                                               "counts": {"S": 12.0}}})
    assert shown["56Fe"]["mass"]["S"] == pytest.approx(1.0)
    assert shown["56Fe"]["d"]["S"] == pytest.approx(0.04)
    assert shown["56Fe"]["counts"]["S"] == 12.0


def test_figure_builder_axis_titles_follow_units(qapp):
    """A typed title such as Particle mass (fg) is shown in the chosen unit."""
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import _show_units
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    fig = Figure()
    ax = fig.add_subplot()
    ax.set_xlabel("Particle mass (fg)")
    ax.set_ylabel("AuNP sample")
    _show_units(fig)
    assert ax.get_xlabel() == "Particle mass (pg)"
    assert ax.get_ylabel() == "AuNP sample"


def test_insights_card_values_follow_units():
    """Card text quotes values converted into the chosen unit."""
    from results.insights import engine as rr
    unit_mod.units.set(ExportUnits(diameter_unit="µm", mass_unit="pg"))
    assert rr.shown_unit("element_diameter_nm") == "µm"
    assert rr.shown_unit("element_mass_fg") == "pg"
    assert rr.shown_unit("elements") == "counts"
    assert rr.units.convert_for(250.0, "element_diameter_nm") == pytest.approx(0.25)


def test_insights_limit_lines_follow_units():
    """Limit lines in figures made from a card use the canvas's units."""
    from results.insights import figures as F
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    ctx = F.FigureContext(limits={("mass", "56Fe"): {"S": 850.0}})
    assert F._limit(ctx, "mass", "56Fe")["dl_value"] == "0.85"
    assert "0.85 pg" in F.limits_sentence(ctx)
    assert F._qname("mass") == "mass (pg)"


def test_insights_evidence_table_matches_the_canvas():
    """The numbers quoted in a figure's legend come from particles in the chosen units."""
    from results.insights import evidence
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    table = evidence.table_from([("S", ("S",))], {"S": [particle(), particle(4000.0)]})
    values = np.asarray(evidence.values(table, "mass:56Fe"), dtype=float)
    assert sorted(values.tolist()) == pytest.approx([2.0, 4.0])
