"""Tests for the manual sensitivity override of the Ionic Calibration window.

A manual slope replaces the fitted calibration of one isotope, so it feeds
every mass computed downstream. These tests drive the real widgets: the
Override checkbox and slope box of the Manual Sensitivity tab, the inline
slope box of the Calibration Results tab, and the global buttons, and check
that each path leaves one consistent record (slope, line, LOD, LOQ) behind.
"""
import math

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from calibration_methods.ionic_CAL import IonicCalibrationWindow, _r2_text
from calibration_methods.te_common import run_all_fits_on_subset

FE = 'Fe-55.9349'
CE = 'Ce-139.9054'


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = IonicCalibrationWindow()
    w.selected_isotopes = {'Fe': [55.9349], 'Ce': [139.9054]}
    w.update_table_columns()
    w.update_element_isotope_combo()
    x = np.array([0.0, 1.0, 5.0, 10.0, 20.0])
    for key, slope in ((FE, 1200.0), (CE, 800.0)):
        y = slope * x + 300.0
        y_std = np.array([50.0, 60.0, 70.0, 80.0, 90.0])
        rec = run_all_fits_on_subset(x, y, y_std, np.ones(x.size, bool), 7.87)
        rec['folders'] = [f's{i}' for i in range(x.size)]
        w.calibration_results[key] = rec
        w.isotope_method_preferences[key] = 'Simple linear'
    w.update_sensitivity_table()
    w.update_results_table()
    yield w
    w.data_modified = False
    w.deleteLater()


def _row_widgets(w, key):
    row = w._sensitivity_row(key)
    assert row >= 0
    return w.sensitivity_table.cellWidget(row, 1), w.sensitivity_table.cellWidget(row, 2)


def _assert_consistent(w, key, slope):
    rec = w.calibration_results[key]['manual']
    assert rec['slope'] == pytest.approx(slope)
    assert w.sensitivity_overrides[key]['slope'] == pytest.approx(slope)
    x = np.asarray(w.calibration_results[key]['x'])
    assert rec['y_fit'] == pytest.approx((slope * x).tolist())
    assert rec['lod'] == pytest.approx(3.0 * 50.0 / slope)
    assert rec['loq'] == pytest.approx(10.0 * 50.0 / slope)
    assert math.isnan(rec['r_squared'])


def test_ticking_override_applies_the_fitted_slope(window):
    """Ticking the box must create the override; it used to delete it."""
    checkbox, spinbox = _row_widgets(window, FE)
    assert not spinbox.isEnabled()
    checkbox.setChecked(True)
    assert FE in window.sensitivity_overrides
    assert spinbox.isEnabled()
    assert window.isotope_method_preferences[FE] == 'Manual'
    _assert_consistent(window, FE, window.calibration_results[FE]['simple']['slope'])


def test_override_ticked_before_calculation_starts_from_fit(qapp):
    """A row drawn before Calculate must still start from the fit once it exists."""
    w = IonicCalibrationWindow()
    w.selected_isotopes = {'Fe': [55.9349]}
    w.update_table_columns()
    w.update_element_isotope_combo()
    w.update_sensitivity_table()
    x = np.array([0.0, 1.0, 5.0, 10.0])
    rec = run_all_fits_on_subset(x, 1200.0 * x + 300.0, np.full(4, 50.0), np.ones(4, bool), 7.87)
    rec['folders'] = [f's{i}' for i in range(4)]
    w.calibration_results[FE] = rec
    w.update_calibration_with_overrides()
    checkbox, spinbox = _row_widgets(w, FE)
    assert spinbox.value() == pytest.approx(rec['simple']['slope'], rel=1e-6)
    checkbox.setChecked(True)
    assert w.sensitivity_overrides[FE]['slope'] == pytest.approx(rec['simple']['slope'])
    w.data_modified = False
    w.deleteLater()


def test_editing_the_slope_updates_line_and_limits(window):
    checkbox, spinbox = _row_widgets(window, FE)
    checkbox.setChecked(True)
    spinbox.setValue(1500.0)
    _assert_consistent(window, FE, 1500.0)


def test_unticking_returns_to_a_fitted_method(window):
    checkbox, _ = _row_widgets(window, FE)
    checkbox.setChecked(True)
    checkbox.setChecked(False)
    assert FE not in window.sensitivity_overrides
    assert 'manual' not in window.calibration_results[FE]
    assert window.isotope_method_preferences[FE] in ('Force through zero', 'Simple linear', 'Weighted')


def test_inline_slope_and_tab_stay_in_sync(window):
    """The Calibration Results slope box and the tab row are one value."""
    window.element_isotope_combo.setCurrentIndex(window.element_isotope_combo.findData(FE))
    window.calibration_method_combo.setCurrentText('Manual')
    assert FE in window.sensitivity_overrides
    window.manual_slope_input.setValue(999.0)
    window.on_manual_slope_changed()
    _assert_consistent(window, FE, 999.0)
    checkbox, spinbox = _row_widgets(window, FE)
    assert checkbox.isChecked()
    assert spinbox.value() == pytest.approx(999.0)


def test_non_positive_slope_is_rejected(window):
    assert window.apply_manual_slope(FE, 0.0) is False
    assert window.apply_manual_slope(FE, -5.0) is False
    assert FE not in window.sensitivity_overrides


def test_override_all_and_apply_to_overridden(window):
    window.global_manual_slope_input.setValue(42.0)
    window.apply_global_slope_to_all()
    for key in (FE, CE):
        _assert_consistent(window, key, 42.0)
        assert _row_widgets(window, key)[0].isChecked()

    _row_widgets(window, CE)[0].setChecked(False)
    window.global_manual_slope_input.setValue(77.0)
    window.apply_global_slope_to_checked()
    _assert_consistent(window, FE, 77.0)
    assert CE not in window.sensitivity_overrides


def test_recalculation_rebuilds_manual_record(window):
    """After new standards, an override keeps its slope but its LOD follows the new blank."""
    window.apply_manual_slope(FE, 1000.0)
    window.calibration_results[FE]['y_std'] = [100.0, 60.0, 70.0, 80.0, 90.0]
    window.update_calibration_with_overrides()
    rec = window.calibration_results[FE]['manual']
    assert rec['slope'] == pytest.approx(1000.0)
    assert rec['lod'] == pytest.approx(3.0 * 100.0 / 1000.0)


def test_manual_r_squared_is_shown_as_dash():
    assert _r2_text(float('nan'), 4) == '—'
    assert _r2_text(0.99951, 4) == '0.9995'
