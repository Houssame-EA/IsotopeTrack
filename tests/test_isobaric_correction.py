# -*- coding: utf-8 -*-
"""Tests for the isobaric correction engine (tools/isobaric_correction.py).

This module is pure logic (numpy + ast only, no GUI) and it implements two
safety-critical pieces:

  1. The arithmetic of overlap correction:
         corrected = max(analyte - R * monitor, 0)
     and R = abundance(interferent @ overlap) / abundance(interferent @ monitor).

  2. A *sandboxed* expression evaluator. Users can type free-text correction
     equations; these tests pin down that the whitelist actually rejects
     dangerous input (imports, attribute access, arbitrary calls, names) while
     still evaluating legitimate math.

If any of these change behaviour, the science (and the security of the
evaluator) is affected, so these are the tests most worth having.
"""
import numpy as np
import pytest

from tools import isobaric_correction as ic


# --------------------------------------------------------------------------- #
# _nominal — nominal (integer) mass rounding
# --------------------------------------------------------------------------- #
class TestNominal:
    def test_rounds_to_nearest_integer(self):
        assert ic._nominal(106.905) == 107      # 107Ag
        assert ic._nominal(55.9349) == 56       # 56Fe
        assert ic._nominal(203.973) == 204      # 204Pb / 204Hg

    def test_handles_exact_and_low_masses(self):
        assert ic._nominal(1.0) == 1
        assert ic._nominal(38.4) == 38
        assert ic._nominal(38.5) == 38  # banker's rounding: round(38.5) -> 38


# --------------------------------------------------------------------------- #
# apply_to_signal — the core subtraction + clamp
# --------------------------------------------------------------------------- #
class TestApplyToSignal:
    def test_basic_subtraction(self):
        analyte = np.array([10.0, 20.0, 30.0])
        monitor = np.array([1.0, 2.0, 3.0])
        out = ic.apply_to_signal(analyte, monitor, factor=2.0, clamp=False)
        np.testing.assert_allclose(out, [8.0, 16.0, 24.0])

    def test_clamped_at_zero(self):
        analyte = np.array([1.0, 5.0])
        monitor = np.array([10.0, 1.0])
        out = ic.apply_to_signal(analyte, monitor, factor=1.0, clamp=True)
        # 1 - 10 -> clamp to 0 ; 5 - 1 -> 4
        np.testing.assert_allclose(out, [0.0, 4.0])

    def test_does_not_mutate_inputs(self):
        analyte = np.array([10.0, 20.0])
        monitor = np.array([1.0, 1.0])
        analyte_copy = analyte.copy()
        ic.apply_to_signal(analyte, monitor, factor=1.0)
        np.testing.assert_array_equal(analyte, analyte_copy)

    def test_zero_factor_is_identity(self):
        analyte = np.array([3.0, 7.0, 11.0])
        monitor = np.array([100.0, 200.0, 300.0])
        out = ic.apply_to_signal(analyte, monitor, factor=0.0, clamp=False)
        np.testing.assert_allclose(out, analyte)

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            ic.apply_to_signal(np.zeros(3), np.zeros(4), factor=1.0)


# --------------------------------------------------------------------------- #
# correction_factor — abundance ratio, with fail-safe
# --------------------------------------------------------------------------- #
class TestCorrectionFactor:
    # Minimal stand-in for the periodic-table accessor the app passes in.
    _HG = {
        "isotopes": [
            {"mass": 201.971, "abundance": 29.86},   # 202Hg (monitor)
            {"mass": 203.973, "abundance": 6.87},     # 204Hg (overlap on 204Pb)
        ]
    }

    def _lookup(self, symbol):
        return self._HG if symbol == "Hg" else None

    def test_known_ratio_pb204_hg(self):
        # R = abundance(204Hg) / abundance(202Hg) = 6.87 / 29.86
        R = ic.correction_factor("Hg", 203.973, 201.971, self._lookup)
        assert R == pytest.approx(6.87 / 29.86, rel=1e-9)

    def test_failsafe_when_monitor_abundance_missing(self):
        # Monitor mass not present -> abundance 0 -> factor 0 (no correction).
        R = ic.correction_factor("Hg", 203.973, 999.0, self._lookup)
        assert R == 0.0

    def test_failsafe_when_element_unknown(self):
        R = ic.correction_factor("Xx", 203.973, 201.971, self._lookup)
        assert R == 0.0


# --------------------------------------------------------------------------- #
# validate_expression — the security whitelist
# --------------------------------------------------------------------------- #
class TestValidateExpressionSecurity:
    @pytest.mark.parametrize("expr", [
        "raw - 0.23 * Hg202",
        "raw - 1575.95*Ar38 - 0.000125*K39",
        "raw - 0.5 * (Hg202 / Hg201)",
        "sqrt(raw) + log(Hg202)",
        "raw ** 1 - abs(Ar38)",
    ])
    def test_accepts_legitimate_equations(self, expr):
        ok, msg, _ = ic.validate_expression(expr)
        assert ok, f"should accept {expr!r}, got error: {msg}"

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('echo hi')",   # import via builtin
        "raw.__class__",                          # attribute access
        "open('/etc/passwd')",                    # disallowed call
        "eval('1+1')",                            # disallowed call
        "raw; import os",                         # statement / multi
        "lambda: 1",                              # lambda
        "[x for x in raw]",                       # comprehension
        "{1: 2}",                                 # dict literal
        "raw if raw else 0",                      # conditional expr
    ])
    def test_rejects_dangerous_or_unsupported(self, expr):
        ok, msg, _ = ic.validate_expression(expr)
        assert not ok, f"should REJECT {expr!r} but it was accepted"
        assert msg, "rejection should carry an explanatory message"

    def test_rejects_unknown_name(self):
        ok, msg, _ = ic.validate_expression("raw - foo")
        assert not ok
        assert "unknown name" in msg.lower()

    def test_empty_is_rejected(self):
        ok, msg, _ = ic.validate_expression("   ")
        assert not ok

    def test_reports_referenced_nominals(self):
        ok, _, nominals = ic.validate_expression("raw - 0.2*Hg202 + 0.1*Ar38")
        assert ok
        assert nominals == [38, 202]

    def test_channel_availability_check(self):
        # 202 measured, 38 not -> should fail and name the missing channel.
        ok, msg, _ = ic.validate_expression(
            "raw - 0.2*Hg202 - 0.1*Ar38", available_nominals={202})
        assert not ok
        assert "38" in msg


# --------------------------------------------------------------------------- #
# evaluate_equation — end-to-end safe evaluation against channel data
# --------------------------------------------------------------------------- #
class TestEvaluateEquation:
    def _eq(self, expr, analyte_mass=204.0):
        return ic.EquationCorrection(
            analyte_symbol="Pb",
            analyte_mass=analyte_mass,
            analyte_label="204Pb",
            expression=expr,
        )

    @staticmethod
    def _identity_closest(mass):
        # Channels are keyed by nominal float in this fixture.
        return float(round(mass))

    def test_simple_correction(self):
        sample = {204.0: np.array([10.0, 20.0, 5.0]),
                  202.0: np.array([10.0, 10.0, 10.0])}
        eq = self._eq("raw - 0.5*Hg202")
        out = ic.evaluate_equation(eq, sample, self._identity_closest)
        # 10-5, 20-5, 5-5 -> [5, 15, 0]
        np.testing.assert_allclose(out, [5.0, 15.0, 0.0])

    def test_clamped_non_negative(self):
        sample = {204.0: np.array([1.0, 2.0]),
                  202.0: np.array([10.0, 10.0])}
        eq = self._eq("raw - 1.0*Hg202")
        out = ic.evaluate_equation(eq, sample, self._identity_closest)
        assert np.all(out >= 0.0)

    def test_missing_channel_returns_none(self):
        sample = {204.0: np.array([1.0, 2.0])}  # no 202 channel
        eq = self._eq("raw - 1.0*Hg202")
        out = ic.evaluate_equation(eq, sample, self._identity_closest)
        assert out is None

    def test_division_by_zero_is_sanitized(self):
        sample = {204.0: np.array([10.0, 20.0]),
                  202.0: np.array([0.0, 0.0])}
        eq = self._eq("raw / Hg202")
        out = ic.evaluate_equation(eq, sample, self._identity_closest)
        # No inf/nan should leak through; result is finite.
        assert np.all(np.isfinite(out))
