"""Older projects read a sample's spectrum from its run folder only when the user asks."""

import json
import logging
import types

import numpy as np
import pytest

from save_export.project_manager import samples_waiting_for_spectrum


@pytest.fixture(autouse=True)
def app():
    """The QApplication the wait cursor and the plot need."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def write_run(folder, n=3, points=40):
    """A Nu run folder with *n* raw snapshots of *points* points each."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw.index").write_text(json.dumps([{"FileNum": 1}]))
    records = "".join(json.dumps({"raw": [1] * points}) for _ in range(n))
    (folder / "1.raw").write_text(records)
    return folder


class Status:
    """Stand-in for the main window's status label."""

    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


def window(folder_map, stored=None, on_request=()):
    """The parts of the main window the spectrum lookup uses."""
    import mainwindow
    win = types.SimpleNamespace(
        sample_raw_spectrum=dict(stored or {}),
        sample_to_folder_map=dict(folder_map),
        _raw_spectrum_missing=set(),
        _raw_spectrum_on_request=set(on_request),
        _interference_by_sample={},
        status_label=Status(),
        logger=logging.getLogger("test"),
        refreshed=[],
    )
    win._raw_spectrum_for = lambda s: mainwindow.MainWindow._raw_spectrum_for(win, s)
    win._refresh_spectrum_view = lambda: win.refreshed.append(True)
    return win


def test_opened_project_waits_for_every_sample_saved_without_a_spectrum():
    """Samples with a stored spectrum are ready; the others wait for the user."""
    win = types.SimpleNamespace(
        sample_to_folder_map={"A": "/run/A", "B": "/run/B", "C": "/run/C"},
        sample_raw_spectrum={"A": {"spectrum": np.ones(3), "n_snapshots": 2}, "B": {}})
    assert samples_waiting_for_spectrum(win) == {"B", "C"}
    assert samples_waiting_for_spectrum(types.SimpleNamespace()) == set()


def test_waiting_sample_is_not_looked_up_in_its_folder(tmp_path, monkeypatch):
    """No folder is read on its own for a sample waiting for the user."""
    import mainwindow
    run = write_run(tmp_path / "A")
    calls = []
    real = mainwindow.read_nu_raw_spectrum
    monkeypatch.setattr(mainwindow, "read_nu_raw_spectrum", lambda f: calls.append(f) or real(f))
    win = window({"A": run}, on_request={"A"})
    assert win._raw_spectrum_for("A") is None
    assert calls == []


def test_new_sample_is_still_read_from_its_folder(tmp_path):
    """A sample loaded from its folder in this session reads its spectrum as before."""
    win = window({"A": write_run(tmp_path / "A", n=3)})
    entry = win._raw_spectrum_for("A")
    assert entry["n_snapshots"] == 3 and entry["spectrum"].size == 40


def test_button_reads_the_spectrum_and_redraws(tmp_path):
    """Asking for the spectrum reads it once, keeps it and refreshes the view."""
    import mainwindow
    win = window({"A": write_run(tmp_path / "A", n=2)}, on_request={"A"})
    assert mainwindow.MainWindow.load_raw_spectrum_on_request(win, "A") is True
    assert "A" not in win._raw_spectrum_on_request
    assert win.sample_raw_spectrum["A"]["n_snapshots"] == 2
    assert win.refreshed and "loaded" in win.status_label.text


def test_button_with_the_folder_gone_keeps_waiting(tmp_path):
    """With the drive unplugged the sample keeps its button and nothing is marked missing."""
    import mainwindow
    win = window({"A": tmp_path / "gone"}, on_request={"A"})
    assert mainwindow.MainWindow.load_raw_spectrum_on_request(win, "A") is False
    assert "A" in win._raw_spectrum_on_request and "A" not in win._raw_spectrum_missing
    assert "not found" in win.status_label.text


def test_message_names_the_folder_and_offers_the_button(tmp_path):
    """The Spectrum view says where the spectrum would come from, and the button loads it."""
    import mainwindow
    run = write_run(tmp_path / "A")
    win = window({"A": run, "B": tmp_path / "gone"}, on_request={"A", "B"})
    win.load_raw_spectrum_on_request = lambda s: win.refreshed.append(s)
    text, (label, callback) = mainwindow.MainWindow._spectrum_request_message(win, "A")
    assert str(run) in text and "not reachable" not in text
    assert label == "Load spectrum from the run folder"
    callback()
    assert win.refreshed == ["A"]
    text_b, _action = mainwindow.MainWindow._spectrum_request_message(win, "B")
    assert "not reachable" in text_b


def test_spectrum_view_shows_the_button_only_with_an_action():
    """The button appears with a request and goes away with a plain message or a spectrum."""
    from widget.custom_plot_widget import SpectrumPlotWidget
    w = SpectrumPlotWidget()
    w.resize(800, 400)
    w.show()
    clicked = []
    w.show_message("Waiting", ("Load", lambda: clicked.append(1)))
    assert w._action_btn.isVisible() and w._action_btn.text() == "Load"
    w._action_btn.click()
    assert clicked == [1]
    w.show_message("Nothing here")
    assert not w._action_btn.isVisible()
    w.show_message("Waiting", ("Load", lambda: None))
    w.set_spectrum("A", np.linspace(1, 10, 50), np.ones(50))
    assert not w._action_btn.isVisible()
    w.hide()
