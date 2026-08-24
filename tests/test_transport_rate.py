# -*- coding: utf-8 -*-
"""Tests for the transport-efficiency calculations in
calibration_methods/te_common.py.

Transport rate scales every particle-number concentration the app reports, so
these are science-critical. The functions are pure numerics; the module imports
Qt only for the dialogs it also defines.
"""
import math

import pytest

from calibration_methods.te_common import (
    particle_mass_from_diameter,
    number_method_transport_rate,
    weight_method_transport_rate,
)


class TestParticleMassFromDiameter:
    def test_volume_of_sphere(self):
        # Volume of a sphere = (pi/6) * d^3. For d = 100 nm:
        out = particle_mass_from_diameter(100.0, 1.0)
        assert out["volume_nm3"] == pytest.approx(math.pi / 6 * 100.0 ** 3)

    def test_mass_matches_density_times_volume(self):
        # mass(fg) = (pi/6) * d_nm^3 * density(g/cm3) * 1e-6
        d, rho = 100.0, 10.49      # ~silver
        expected_fg = (math.pi / 6) * d ** 3 * rho * 1e-6
        assert particle_mass_from_diameter(d, rho)["mass_fg"] == pytest.approx(expected_fg)

    def test_mass_scales_with_diameter_cubed(self):
        m1 = particle_mass_from_diameter(50.0, 5.0)["mass_fg"]
        m2 = particle_mass_from_diameter(100.0, 5.0)["mass_fg"]
        assert m2 == pytest.approx(8.0 * m1)   # double diameter -> 8x mass

    def test_mass_scales_linearly_with_density(self):
        m1 = particle_mass_from_diameter(80.0, 2.0)["mass_fg"]
        m2 = particle_mass_from_diameter(80.0, 6.0)["mass_fg"]
        assert m2 == pytest.approx(3.0 * m1)

    def test_unit_conversions_are_consistent(self):
        out = particle_mass_from_diameter(100.0, 1.0)
        assert out["volume_nm3"] == pytest.approx(out["volume_m3"] * 1e27)
        assert out["mass_fg"] == pytest.approx(out["mass_kg"] * 1e18)


class TestNumberMethodTransportRate:
    def test_valid_inputs_succeed(self):
        out = number_method_transport_rate(
            particles_detected=1000, diameter_nm=100.0,
            concentration_ng_l=100.0, acquisition_time_s=60.0,
            density_g_cm3=10.49)
        assert out["status"] == "Success"
        assert out["transport_rate_ul_s"] > 0.0
        assert out["particles_per_ml"] > 0.0

    def test_particle_mass_is_consistent(self):
        out = number_method_transport_rate(1000, 100.0, 100.0, 60.0, 10.49)
        ref = particle_mass_from_diameter(100.0, 10.49)
        assert out["particle_mass_fg"] == pytest.approx(ref["mass_fg"])

    def test_internal_rate_relationship(self):
        # rate(uL/s) = detected / (particles_per_ml * t) * 1000
        n, t = 1000, 60.0
        out = number_method_transport_rate(n, 100.0, 100.0, t, 10.49)
        expected = n / (out["particles_per_ml"] * t) * 1000.0
        assert out["transport_rate_ul_s"] == pytest.approx(expected)

    def test_zero_time_is_error(self):
        out = number_method_transport_rate(1000, 100.0, 100.0, 0.0, 10.49)
        assert out["status"].startswith("Error")
        assert out["transport_rate_ul_s"] == 0.0


class TestWeightMethodTransportRate:
    def test_known_case(self):
        # consumed = 10 - 9 = 1 g ; to plasma = 1 - 0.5 = 0.5 g
        # rate = 0.5 g * 1000 / 100 s = 5.0 uL/s
        out = weight_method_transport_rate(
            w_initial_g=10.0, w_final_g=9.0, w_waste_g=0.5, time_s=100.0)
        assert out["status"] == "Success"
        assert out["sample_consumed_g"] == pytest.approx(1.0)
        assert out["volume_to_plasma_g"] == pytest.approx(0.5)
        assert out["transport_rate_ul_s"] == pytest.approx(5.0)

    def test_zero_time_raises(self):
        with pytest.raises(ValueError):
            weight_method_transport_rate(10.0, 9.0, 0.5, 0.0)

    def test_no_consumption_raises(self):
        with pytest.raises(ValueError):
            weight_method_transport_rate(9.0, 10.0, 0.5, 100.0)  # final > initial

    def test_waste_exceeds_consumption_raises(self):
        with pytest.raises(ValueError):
            weight_method_transport_rate(10.0, 9.0, 2.0, 100.0)  # waste > consumed
