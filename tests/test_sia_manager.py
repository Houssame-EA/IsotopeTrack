"""Tests for the SIA manager: outliers, sigma in use, labels, history and projects."""

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QTableWidget

from loading import sia_stats
from loading.SIA_manager import DEFAULT_SIGMA, _build_histogram, _weighted_stats

SIGMAS = {27.0: 0.48, 48.0: 0.49, 56.0: 0.50, 63.0: 0.47, 107.0: 0.51,
          140.0: 0.49, 159.0: 0.75, 197.0: 0.50}


def _result():
    """Synthetic worker result with one outlier mass at m/z 159."""
    rng = np.random.default_rng(1)
    c, k = _build_histogram(rng.lognormal(np.log(100), 0.47, 20000), 80)
    overall = np.stack((c, k), axis=1)
    m, s, sig = _weighted_stats(overall[:, 0], overall[:, 1])
    per = {}
    for mass, sg in SIGMAS.items():
        per[f"{mass:.4f}"] = {"distribution": overall, "mass": mass, "mean_signal": m,
                              "std_signal": s, "sigma": sg, "num_points": 5000}
    info = {"source_folder": "/data/sia", "sample_name": "SIA_test", "instrument_type": "Nu Vitesse",
            "total_counts": 1e6, "num_acquisitions": 20000, "num_masses": 200,
            "mass_range": (5.0, 250.0), "distribution_points": len(overall),
            "mean_signal": m, "std_signal": s, "calculated_sigma": sig,
            "analysis_datetime": "2026-10-01T09:00:00Z", "signal_values": overall[:, 0].copy(),
            "weights": overall[:, 1] / overall[:, 1].sum(), "average_single_ion_area": 100.0,
            "num_valid_masses": len(per)}
    return {"single_ion_distribution_data": overall, "single_ion_source_folder": "/data/sia",
            "per_mass_distributions": per, "single_ion_info": info}


@pytest.fixture
def mw(monkeypatch, tmp_path):
    """Main window with message boxes silenced and a temporary history file."""
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(sia_stats, "default_history_path", lambda: str(tmp_path / "sia_history.json"))
    from mainwindow import MainWindow
    w = MainWindow()
    mgr = w.sia_manager
    mgr._history = None
    mgr._themed_msgbox = lambda *a, **k: None
    w.sample_parameters = {"S1": {"Fe-55.9349": {"sigma": 0.55}, "Tb-158.9254": {"sigma": 0.55}}}
    w.mark_element_changed = lambda *a, **k: None
    yield w
    w.close()


def _load(w):
    w.sia_manager._on_finished(_result())


def test_loading_applies_sigma_everywhere(mw):
    _load(mw)
    mgr = mw.sia_manager
    sig = mgr.single_ion_info["calculated_sigma"]
    assert mw.sigma_spinbox.value() == pytest.approx(sig, abs=1e-3)
    assert mw._global_sigma == pytest.approx(mw.sigma_spinbox.value())
    for el in mw.sample_parameters["S1"].values():
        assert el["sigma"] == pytest.approx(mw.sigma_spinbox.value())
    assert mgr.sigma_source_label.text().startswith("SIA SIA_test · 2026-10-01")


def test_exclude_outliers_updates_sigma_and_back(mw):
    _load(mw)
    mgr = mw.sia_manager
    overall = mw.sigma_spinbox.value()
    mgr.set_exclude_outliers(True)
    expected = np.mean([v for k, v in SIGMAS.items() if k != 159.0])
    assert mw.sigma_spinbox.value() == pytest.approx(expected, abs=1e-3)
    assert mw.sample_parameters["S1"]["Fe-55.9349"]["sigma"] == pytest.approx(mw.sigma_spinbox.value())
    assert "1 outlier excluded" in mgr.sigma_source_label.text()
    mgr.set_exclude_outliers(False)
    assert mw.sigma_spinbox.value() == pytest.approx(overall)


def test_per_isotope_mode_skips_outlier_mass(mw):
    _load(mw)
    mgr = mw.sia_manager
    mw._sigma_mode = "per_isotope"
    mgr._assign_per_mass_sigma(quiet=True)
    assert mw.sample_parameters["S1"]["Tb-158.9254"]["sigma"] == pytest.approx(0.75)
    mgr.set_exclude_outliers(True)
    params = mw.sample_parameters["S1"]
    assert params["Fe-55.9349"]["sigma"] == pytest.approx(0.50)
    assert params["Fe-55.9349"]["_sigma_from_sia"]
    assert params["Tb-158.9254"]["sigma"] == pytest.approx(mgr.get_effective_sigma())
    assert not params["Tb-158.9254"]["_sigma_from_sia"]
    assert mgr.get_per_mass_sigma(158.93) == pytest.approx(mgr.get_effective_sigma())


def test_hand_edit_is_reported(mw):
    _load(mw)
    mw.sigma_spinbox.setValue(0.6)
    assert mw.sia_manager.sigma_source_label.text().startswith("σ edited by hand")


def test_clear_resets_sigma_and_label(mw):
    _load(mw)
    mgr = mw.sia_manager
    mgr.set_exclude_outliers(True)
    mgr._clear_sia_data()
    assert mw.sigma_spinbox.value() == pytest.approx(DEFAULT_SIGMA)
    assert all(el["sigma"] == DEFAULT_SIGMA for el in mw.sample_parameters["S1"].values())
    assert not mgr._exclude_outliers
    assert not mgr.sigma_source_label.isVisible()


def test_mass_labels_have_isotopes(mw):
    mgr = mw.sia_manager
    assert mgr.mass_label(55.9349) == "⁵⁶Fe"
    assert mgr.isotope_text(57.9353).split(" / ")[0] == "58Ni"


def test_dialog_mass_selector_and_outlier_checkbox(mw):
    _load(mw)
    mgr = mw.sia_manager
    mgr.show_single_ion_info()
    QApplication.processEvents()
    texts = [mgr.mass_selector.itemText(i) for i in range(mgr.mass_selector.count())]
    assert any("⁵⁶Fe" in t for t in texts)
    assert mgr.outlier_checkbox.isEnabled()
    mgr.outlier_checkbox.setChecked(True)
    assert mgr._exclude_outliers
    assert mw.sigma_spinbox.value() < mgr.single_ion_info["calculated_sigma"] + 0.05


def test_history_records_once_per_sia(mw):
    _load(mw)
    _load(mw)
    hist = mw.sia_manager.history()
    assert len(hist.entries) == 1
    assert hist.entries[0]["sigma"] == pytest.approx(mw.sia_manager.single_ion_info["calculated_sigma"])


def test_history_dialog_lists_sessions(mw):
    _load(mw)
    dlg = mw.sia_manager.show_history_dialog()
    QApplication.processEvents()
    table = dlg.findChild(QTableWidget)
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "SIA_test"
    dlg.close()


def test_history_message():
    from loading.SIA_manager import SingleIonDistributionManager as M
    assert "earlier session" in M._history_message({"n_previous": 1})
    text = M._history_message({"n_previous": 5, "sigma": "action", "average_single_ion_area": "ok"})
    assert "±3 SD" in text


def test_project_round_trip(mw, monkeypatch):
    from save_export import fast_project_io as fio
    _load(mw)
    mw.sia_manager.set_exclude_outliers(True)
    meta = fio.build_metadata(mw)
    assert meta["sia_state"]["exclude_outliers"]
    mgr = mw.sia_manager
    mgr.single_ion_distribution_data = None
    mgr.single_ion_info = {}
    mgr.per_mass_distributions = {}
    mgr._exclude_outliers = False
    fio._restore_metadata(mw, meta)
    assert mgr.is_sia_loaded()
    assert mgr._exclude_outliers
    assert len(mgr.per_mass_distributions) == len(SIGMAS)
    assert mgr.info_sid_button.isEnabled()
