# -*- coding: utf-8 -*-
"""Tests for calibration_methods/sensitivity_checks.py and the Checks window data."""
import numpy as np
import pytest

from calibration_methods import sensitivity_checks as sc


class TestSlopeUncertainty:
    def test_matches_scipy_linregress(self):
        from scipy import stats
        x = np.array([0.0, 1.0, 5.0, 10.0, 20.0])
        y = 1000 * x + 50 + np.array([30.0, -20.0, 40.0, -50.0, 10.0])
        res = sc.slope_uncertainty(x, y, method='simple')
        assert res['se'] == pytest.approx(stats.linregress(x, y).stderr)
        assert res['ci95'] == pytest.approx(stats.t.ppf(0.975, 3) * res['se'])

    def test_perfect_line_has_zero_error(self):
        x = np.array([1.0, 2.0, 3.0])
        for method in ('zero', 'simple'):
            assert sc.slope_uncertainty(x, 4 * x, method=method)['se'] == pytest.approx(0.0, abs=1e-9)

    def test_too_few_points_is_nan(self):
        assert np.isnan(sc.slope_uncertainty([1.0, 2.0], [1.0, 2.0])['se'])

    def test_weighted_uses_known_sigma(self):
        x = np.array([0.0, 1.0, 2.0])
        s = np.array([1.0, 1.0, 1.0])
        res = sc.slope_uncertainty(x, 2 * x, s, method='weighted')
        assert res['se'] == pytest.approx(np.sqrt(3 / (3 * 5 - 9)))


class TestLinearity:
    def test_saturated_top_point_is_flagged(self):
        x = np.array([0.0, 1.0, 5.0, 10.0, 50.0])
        y = 1000 * x
        y[-1] *= 0.8
        res = sc.linearity_check(x, y)
        assert res['flag'] and res['top_deviation_pct'] == pytest.approx(-20.0, abs=0.5)
        assert res['slope_change_pct'] < 0

    def test_linear_data_is_not_flagged(self):
        x = np.array([0.0, 1.0, 5.0, 10.0, 50.0])
        assert not sc.linearity_check(x, 1000 * x + 10)['flag']

    def test_needs_four_standards(self):
        assert sc.linearity_check([0, 1, 2], [0, 1, 2]) is None


class TestAbundance:
    def test_isotope_with_extra_signal_is_flagged(self):
        res = sc.abundance_check({
            'Ce-139.9054': ('Ce', 884.5, 88.45),
            'Ce-141.9092': ('Ce', 111.1 * 1.3, 11.11),
            'Ce-137.9060': ('Ce', 2.51, 0.251),
        })
        assert res['Ce-141.9092']['flag']
        assert res['Ce-141.9092']['deviation_pct'] == pytest.approx(30.0, abs=0.1)
        assert not res['Ce-139.9054']['flag']

    def test_single_isotope_elements_are_skipped(self):
        assert sc.abundance_check({'Au-196.9666': ('Au', 500.0, 100.0)}) == {}


class TestDrift:
    def test_repeated_standard_change_is_reported(self):
        res = sc.repeat_standard_drift([0, 1, 5, 10, 5], [0, 100, 500, 1000, 450])
        assert res['at_x'] == 5 and res['repeats'] == 2
        assert res['max_drift_pct'] == pytest.approx(-10.0)
        assert res['flag']

    def test_no_repeats(self):
        assert sc.repeat_standard_drift([0, 1, 5], [0, 1, 5]) is None

    def test_repeated_blanks_are_ignored(self):
        assert sc.repeat_standard_drift([0, 0, 1], [5, 9, 100]) is None


class TestBlank:
    def test_zero_standard_is_a_blank(self):
        assert sc.blank_source([0.0, 1.0])['is_blank']

    def test_without_zero_the_lowest_standard_is_used(self):
        res = sc.blank_source([0.5, 1.0])
        assert not res['is_blank'] and res['x'] == 0.5


class TestHistory:
    def test_compare_with_latest_earlier_day(self, tmp_path):
        h = sc.SensitivityHistory(str(tmp_path / 'h.json'))
        h.record({'Fe-55.9349': 1000.0}, day='2026-10-01')
        h.record({'Fe-55.9349': 1100.0}, day='2026-10-05')
        h.record({'Fe-55.9349': 700.0}, day='2026-10-09')
        res = sc.SensitivityHistory(str(tmp_path / 'h.json')).compare('Fe-55.9349', 700.0, day='2026-10-09')
        assert res['day'] == '2026-10-05'
        assert res['change_pct'] == pytest.approx(-36.36, abs=0.01)
        assert res['flag']

    def test_same_day_replaces(self, tmp_path):
        h = sc.SensitivityHistory(str(tmp_path / 'h.json'))
        h.record({'K': 1.0}, day='2026-10-09')
        h.record({'K': 2.0}, day='2026-10-09')
        assert h.data['K'] == {'2026-10-09': 2.0}
        assert h.compare('K', 2.0, day='2026-10-09') is None


def test_window_checks(tmp_path):
    """The Ionic window runs every check and counts the warnings per isotope."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from calibration_methods.ionic_CAL import IonicCalibrationWindow
    from calibration_methods.te_common import run_all_fits_on_subset

    w = IonicCalibrationWindow()
    w._sensitivity_history = sc.SensitivityHistory(str(tmp_path / 'h.json'))
    w.selected_isotopes = {'Ce': [139.9054, 141.9092]}
    x = np.array([0.0, 1.0, 5.0, 10.0, 20.0])
    for key, slope in (('Ce-139.9054', 884.5), ('Ce-141.9092', 111.1 * 1.4)):
        y = slope * x + 20.0
        rec = run_all_fits_on_subset(x, y, np.full(5, 5.0), np.ones(5, bool), 6.77)
        rec['folders'] = [f's{i}' for i in range(5)]
        w.calibration_results[key] = rec
        w.isotope_method_preferences[key] = 'Simple linear'
    assert np.isfinite(w.calibration_results['Ce-139.9054']['simple']['slope_se'])

    rows = {r['key']: r for r in w.run_checks(record_history=True)}
    assert rows['Ce-141.9092']['abundance']['flag']
    assert rows['Ce-141.9092']['warnings'] == 1
    assert rows['Ce-139.9054']['blank']['is_blank']
    assert w.checks_action.text() == 'Checks (2)'
    assert 'Ce-139.9054' in w._sensitivity_history.data
    w.data_modified = False
    w.deleteLater()
