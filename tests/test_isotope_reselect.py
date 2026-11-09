"""Isotopes that are deselected and selected again, and reopened projects.

A deselected isotope's data stays in memory for the session, so selecting
it again never needs the raw data, and saving the project keeps it in the
project's reserve. Reopening a project marks every saved isotope of an
element in the periodic table, not only the last one.
"""

import logging
import types
import zipfile

import numpy as np

from save_export.isotope_reserve import (
    SOURCE_SESSION, read_reserve_channels, write_sample_reserve,
)


class NoSource:
    """An open project without a reserve for the sample."""

    def masses_for(self, sample_name, folder_path):
        return []


def test_saving_keeps_isotopes_deselected_in_the_session(tmp_path):
    """Deselected channels are written to the reserve; selected ones are not."""
    path = tmp_path / "p.itproj"
    kept = {47.94795: np.arange(5.0), 48.94787: np.arange(5.0) * 2}
    with zipfile.ZipFile(path, "w") as zf:
        written, origin = write_sample_reserve(zf, "S", [46.95177, 48.94787], "/nowhere",
                                               NoSource(), kept=kept)
    assert written == [47.94795] and origin == SOURCE_SESSION
    back = read_reserve_channels(path, "S", written)
    assert np.array_equal(back[47.94795], np.arange(5.0))


def fake_window(session_reserve):
    """The parts of the main window that add isotopes back."""
    added = {}
    win = types.SimpleNamespace(
        data_by_sample={"S": {46.95177: np.ones(3)}},
        sample_to_folder_map={"S": "/Volumes/gone/S"},
        session_reserve=session_reserve,
        sample_reserve_masses={},
        _project_filepath=None,
        logger=logging.getLogger("test"),
        mark_element_changed=lambda *a: None,
    )
    win.handle_new_elements_finished = lambda data, *a: added.update(data)
    return win, added


def test_reselected_isotope_comes_back_without_the_raw_data():
    """An isotope deselected earlier is taken back from memory, not from the drive."""
    import mainwindow
    signal = np.arange(4.0)
    win, added = fake_window({"S": {47.94795: signal}})
    raw_needed = mainwindow.MainWindow._add_isotopes_from_reserve(win, {("Ti", 47.94795)})
    assert raw_needed == {}
    assert np.array_equal(added[47.94795], signal)
    assert win.session_reserve["S"] == {}


def test_a_never_loaded_isotope_still_asks_for_the_raw_data():
    """An isotope that was never in memory still has to be read from the run."""
    import mainwindow
    win, _added = fake_window({})
    raw_needed = mainwindow.MainWindow._add_isotopes_from_reserve(win, {("Ti", 49.94479)})
    assert raw_needed == {"S": [("Ti", 49.94479)]}


def test_reopened_project_marks_every_isotope_of_an_element():
    """Three saved Ti isotopes are all selected again in the periodic table."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import mainwindow
    from widget.periodic_table_widget import PeriodicTableWidget
    table = PeriodicTableWidget()
    ti = next(e for e in table.get_elements() if e["symbol"] == "Ti")
    masses = [iso["mass"] for iso in ti["isotopes"] if isinstance(iso, dict)]
    table.update_available_masses(list(masses))
    win = types.SimpleNamespace(periodic_table_widget=table, selected_isotopes={"Ti": masses[1:4]})
    mainwindow.MainWindow._update_periodic_table_selections(win)
    chosen = sorted(m for _s, m in table.buttons["Ti"].isotope_display.selected_isotopes)
    assert chosen == sorted(masses[1:4])
