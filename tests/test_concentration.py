# -*- coding: utf-8 -*-
"""Tests for the concentration math in tools/dilution_utils.py.

These convert a raw particle count into particles-per-millilitre, via the
analyzed acquisition time, the transport rate, the analyzed volume, and the
dilution factor. This is the final number reported to the user, so the chain
of conversions is critical. The functions read attributes off the main window;
the tests use a tiny fake window that exposes only what each function needs.
"""
import types

import numpy as np

from tools import dilution_utils as du


def make_window(**attrs):
    """A stand-in for MainWindow exposing only the attributes under test."""
    return types.SimpleNamespace(**attrs)


class TestHasTransportRate:
    def test_true_when_positive(self):
        assert du.has_transport_rate(make_window(average_transport_rate=12.0)) is True

    def test_false_when_zero_or_missing(self):
        assert du.has_transport_rate(make_window(average_transport_rate=0)) is False
        assert du.has_transport_rate(make_window()) is False


class TestEffectiveAcquisitionTime:
    def test_full_span_without_exclusions(self):
        w = make_window(time_array_by_sample={"S1": np.arange(0.0, 11.0)})  # 0..10
        assert du.effective_acquisition_time(w, "S1") == 10.0

    def test_uses_current_sample_fallback(self):
        w = make_window(
            time_array_by_sample={},
            current_sample="S1",
            time_array=np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
        )
        assert du.effective_acquisition_time(w, "S1") == 5.0

    def test_too_short_array_is_zero(self):
        w = make_window(time_array_by_sample={"S1": np.array([0.0])})
        assert du.effective_acquisition_time(w, "S1") == 0.0

    def test_unknown_sample_is_zero(self):
        w = make_window(time_array_by_sample={"S1": np.arange(0.0, 11.0)})
        assert du.effective_acquisition_time(w, "Nope") == 0.0


class TestEffectiveVolume:
    def test_volume_is_rate_times_time(self):
        # rate 100 µL/s * 10 s = 1000 µL = 1.0 mL
        w = make_window(
            average_transport_rate=100.0,
            time_array_by_sample={"S1": np.arange(0.0, 11.0)},
        )
        assert du.effective_volume_ml(w, "S1") == 1.0

    def test_no_transport_rate_is_zero(self):
        w = make_window(
            average_transport_rate=0.0,
            time_array_by_sample={"S1": np.arange(0.0, 11.0)},
        )
        assert du.effective_volume_ml(w, "S1") == 0.0


class TestParticlesPerMl:
    def _window(self, dilution=1.0):
        return make_window(
            average_transport_rate=100.0,                      # -> 1.0 mL over 10 s
            time_array_by_sample={"S1": np.arange(0.0, 11.0)},
            sample_dilutions={"S1": dilution},
        )

    def test_basic_concentration(self):
        # 500 particles / 1.0 mL = 500 /mL
        assert du.particles_per_ml(self._window(), "S1", 500) == 500.0

    def test_dilution_is_applied(self):
        # 500 /mL * dilution 2 = 1000 /mL
        assert du.particles_per_ml(self._window(dilution=2.0), "S1", 500) == 1000.0

    def test_dilution_can_be_skipped(self):
        out = du.particles_per_ml(self._window(dilution=2.0), "S1", 500,
                                  apply_dilution=False)
        assert out == 500.0

    def test_zero_count_is_zero(self):
        assert du.particles_per_ml(self._window(), "S1", 0) == 0.0

    def test_no_volume_is_zero(self):
        w = make_window(average_transport_rate=0.0,
                        time_array_by_sample={"S1": np.arange(0.0, 11.0)})
        assert du.particles_per_ml(w, "S1", 500) == 0.0
