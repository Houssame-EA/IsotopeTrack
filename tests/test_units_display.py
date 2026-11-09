"""The main window and the Calibration Information dialog follow the app's units.

Values are still computed in fg and nm; only what is shown changes, and it
changes again as soon as the user picks other units.
"""

import types

import pytest
from PySide6.QtWidgets import QApplication, QWidget

import utils.unit as unit_mod
from utils.unit import ExportUnits


@pytest.fixture
def app_units():
    """The app's units, starting from the base units (see ``conftest.py``)."""
    return unit_mod.units


@pytest.fixture(scope="module")
def qapp():
    """The Qt application."""
    return QApplication.instance() or QApplication([])


class Label:
    """Stands in for the summary label and keeps the last text."""

    text = ""

    def setText(self, text):
        self.text = text


def summary_window():
    """The parts of the main window the element summary reads.

    One Fe particle of 2000 counts, with a slope of 2 and a transport rate
    of 1 µL/s, is 1000 fg of iron.
    """
    win = types.SimpleNamespace(
        current_sample="S",
        data={},
        element_thresholds={},
        average_transport_rate=1.0,
        calibration_results={"Ionic Calibration": {"Fe-55.9349": {"zero": {"slope": 2000.0}}}},
        isotope_method_preferences={},
        detected_peaks={},
        summary_label=Label(),
        get_formatted_label=lambda key: "56Fe",
        find_closest_isotope=lambda iso: None,
        particles_per_ml=lambda *a: 0.0,
    )
    return win


def test_element_summary_shows_the_chosen_mass_unit(qapp, app_units):
    """The summary's masses read 1000 fg by default and 1 pg in picograms."""
    import mainwindow
    win = summary_window()
    particles = [{"total_counts": 2000.0}]
    mainwindow.MainWindow.update_element_summary(win, "Fe", 55.9349, particles)
    assert "Total Mass (fg)" in win.summary_label.text
    assert "1000.00000" in win.summary_label.text
    app_units.set(ExportUnits(mass_unit="pg"))
    mainwindow.MainWindow.update_element_summary(win, "Fe", 55.9349, particles)
    assert "Mean Mass (pg)" in win.summary_label.text
    assert "1.00000" in win.summary_label.text
    assert "(fg)" not in win.summary_label.text


def test_main_window_redraws_the_summary_when_units_change(qapp, app_units):
    """Picking other units shows the last summary again."""
    import mainwindow
    seen = []
    win = types.SimpleNamespace(_last_summary_args=("Fe", 55.9349, []),
                                update_element_summary=lambda *a: seen.append(a))
    mainwindow.MainWindow._on_units_changed(win, ExportUnits(mass_unit="ng"))
    assert seen == [("Fe", 55.9349, [])]


class Owner(QWidget):
    """The main window as the Calibration Information dialog sees it."""

    def __init__(self):
        super().__init__()
        self.current_sample = "S"
        self.element_thresholds = {"S": {}}
        self.element_limits = {"S": {"56Fe": {"MDL": 2000.0, "MQL": 4000.0,
                                              "SDL": 45.0, "SQL": 60.0}}}

    def calculate_mass_limits(self):
        """Keep the limits as they are."""


def limits_row(dialog):
    """``{column title: text}`` of the first row of the ionic table."""
    table = dialog.ionic_calibration_table
    return {table.horizontalHeaderItem(c).text(): table.item(0, c).text()
            for c in range(table.columnCount()) if table.item(0, c)}


def test_calibration_info_limits_follow_the_units(qapp, app_units):
    """MDL and SDL are shown in fg and nm, then in pg and µm after a change."""
    from widget.calibration_info import CalibrationInfoDialog
    owner = Owner()
    results = {"Ionic Calibration": {"Fe-55.9349": {"zero": {"slope": 1.0, "r_squared": 0.999}}}}
    dialog = CalibrationInfoDialog(results, [], {"Fe-55.9349": "Force through zero"}, parent=owner)
    row = limits_row(dialog)
    assert row["MDL\n(fg)"] == "2.00e+03"
    assert row["SDL\n(nm)"] == "45.0"
    app_units.set(ExportUnits(mass_unit="pg", diameter_unit="µm"))
    row = limits_row(dialog)
    assert row["MDL\n(pg)"] == "2.00e+00"
    assert row["SDL\n(µm)"] == "0.0450"
    dialog.close()
