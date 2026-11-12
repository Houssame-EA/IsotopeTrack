"""Periodic table follows the mass range of the open sample."""

import numpy as np


def _table():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from widget.periodic_table_widget import PeriodicTableWidget
    return PeriodicTableWidget()


def test_elements_outside_the_sample_are_greyed_but_keep_their_selection():
    table = _table()
    project = list(np.arange(20.0, 240.0, 1.0)) + [58.9332]
    sample = list(np.arange(61.0, 240.0, 1.0))
    table.update_available_masses(project)
    co = table.buttons["Co"]
    co.isotope_display.selected_isotopes.add(("Co", 58.9332))

    table.set_sample_context("L52", sample)

    assert not co.isEnabled()
    assert "Not measured in L52" in co.toolTip()
    assert ("Co", 58.9332) in co.isotope_display.selected_isotopes
    assert table.buttons["Pb"].isEnabled()
    assert "L52" in table._sample_label.text()
    assert not table._legend.isHidden()

    table.set_sample_context(None, None)
    assert co.isEnabled()
    assert table._legend.isHidden()
    table.close()


def test_blanked_elements_stay_selectable_and_are_marked():
    table = _table()
    masses = list(np.arange(20.0, 240.0, 1.0))
    table.update_available_masses(masses)
    blanking = {"fixed": [(27.0, 33.0), (36.5, 60.0)], "auto": [(33.0, 36.5, 15000)],
                "total_acquisitions": 300000}
    table.set_sample_context("2ppb-Cal", masses, blanking)

    fe = table.buttons["Fe"]
    assert fe.isEnabled() and fe.blank_mark == "blanked"
    assert "Blanked by the method" in fe.toolTip()
    assert table.buttons["Cl"].blank_mark == "auto"
    assert table.buttons["Cu"].blank_mark is None
    ni = table.buttons["Ni"]
    assert ni.blank_mark is None
    assert any(n == "blanked" for n in ni.isotope_display.mass_notes.values())
    table.close()
