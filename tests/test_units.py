# -*- coding: utf-8 -*-
"""Tests for tools/unit.py (ExportUnits value object).

ExportUnits converts the app's internal units (fg / fmol / nm) into whatever
the user picked for export, and formats the numbers. A wrong conversion factor
would silently corrupt every exported mass, mole and size value, so the factor
table and the formatting rules are worth pinning down.

(Persistence via QSettings is intentionally not tested here — it needs a real
Qt settings backend; the conversion/formatting logic is pure.)
"""
import math

from tools.unit import ExportUnits, MASS_UNITS, MOLES_UNITS, DIAMETER_UNITS


class TestConversionFactors:
    def test_mass_factors_are_relative_to_fg(self):
        assert MASS_UNITS["fg"] == 1.0
        assert MASS_UNITS["pg"] == 1e-3      # 1000 fg = 1 pg
        assert MASS_UNITS["ag"] == 1e3       # 1 fg = 1000 ag

    def test_moles_and_diameter_anchors(self):
        assert MOLES_UNITS["fmol"] == 1.0
        assert DIAMETER_UNITS["nm"] == 1.0


class TestDefaultFormatting:
    def setup_method(self):
        self.u = ExportUnits()  # fg / fmol / nm, decimal, 4/6/2 decimals

    def test_mass_default_decimals(self):
        assert self.u.fmt_mass(1.2345678) == "1.2346"   # 4 dp

    def test_moles_default_decimals(self):
        assert self.u.fmt_moles(1.0) == "1.000000"       # 6 dp

    def test_diameter_default_decimals(self):
        assert self.u.fmt_diameter(12.5) == "12.50"      # 2 dp

    def test_labels_track_units(self):
        assert self.u.mass_label == "fg"
        assert self.u.moles_label == "fmol"
        assert self.u.diameter_label == "nm"


class TestUnitConversion:
    def test_mass_fg_to_pg(self):
        u = ExportUnits(mass_unit="pg")
        # 1000 fg -> 1.0 pg
        assert u.fmt_mass(1000.0) == "1.0000"

    def test_diameter_nm_to_um(self):
        u = ExportUnits(diameter_unit="µm")
        # 1000 nm -> 1.0 µm
        assert u.fmt_diameter(1000.0) == "1.00"

    def test_moles_fmol_to_amol(self):
        u = ExportUnits(moles_unit="amol")
        # 1 fmol -> 1000 amol
        assert u.fmt_moles(1.0) == "1000.000000"


class TestScientificFormat:
    def test_scientific_notation(self):
        u = ExportUnits(number_format="scientific", mass_decimals=2)
        assert u.fmt_mass(12345.0) == "1.23e+04"


class TestRobustFormatting:
    def test_none_becomes_zero(self):
        u = ExportUnits()
        assert u._format(None, 4) == "0"

    def test_unparseable_becomes_zero(self):
        u = ExportUnits()
        assert u._format("not-a-number", 4) == "0"

    def test_or_zero_helpers(self):
        u = ExportUnits()
        assert u.fmt_mass_or_zero(0) == "0"
        assert u.fmt_mass_or_zero(-5.0) == "0"
        assert u.fmt_moles_or_zero(0) == "0"
        assert u.fmt_diameter_or_zero(0) == "0"
        assert u.fmt_diameter_or_zero(float("nan")) == "0"
        # A real positive value still formats normally.
        assert u.fmt_mass_or_zero(2.0) == "2.0000"
