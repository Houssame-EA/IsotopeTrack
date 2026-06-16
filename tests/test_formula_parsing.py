# -*- coding: utf-8 -*-
"""Tests for the chemical-formula helpers in tools/mass_fraction_calculator.py.

These parse user-typed formulas (including parenthesised/nested groups) into
element counts and canonicalise them. They feed the mass-fraction lookup, so a
parsing error would propagate into reported particle masses. The functions are
pure; the module imports Qt/pandas only for the dialog and CSV database.
"""
from tools.mass_fraction_calculator import (
    _parse_formula_to_counts,
    _safe_int,
    _element_order_in_formula,
    _reduce_counts,
    _signature_from_counts,
    _join_formula_from_counts,
    canonicalize_preserve_user_order,
)


class TestParseFormulaToCounts:
    def test_simple(self):
        assert _parse_formula_to_counts("H2O") == {"H": 2, "O": 1}
        assert _parse_formula_to_counts("Fe2O3") == {"Fe": 2, "O": 3}

    def test_implicit_one(self):
        assert _parse_formula_to_counts("NaCl") == {"Na": 1, "Cl": 1}

    def test_parenthesised_group(self):
        assert _parse_formula_to_counts("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}

    def test_nested_groups(self):
        assert _parse_formula_to_counts("Al2(SO4)3") == {"Al": 2, "S": 3, "O": 12}

    def test_repeated_element_accumulates(self):
        # CH3CH2OH -> C2 H6 O1
        assert _parse_formula_to_counts("CH3CH2OH") == {"C": 2, "H": 6, "O": 1}

    def test_empty_and_invalid(self):
        assert _parse_formula_to_counts("") == {}
        assert _parse_formula_to_counts(None) == {}


class TestSafeInt:
    def test_parses_int(self):
        assert _safe_int("2") == 2

    def test_empty_returns_default(self):
        assert _safe_int("") == 1
        assert _safe_int("", default=5) == 5

    def test_rounds_floats(self):
        assert _safe_int("2.6") == 3

    def test_zero_falls_back_to_default(self):
        # max(0, 0) is falsy, so the documented behaviour returns the default.
        assert _safe_int("0") == 1
        assert _safe_int("0", default=4) == 4

    def test_garbage_returns_default(self):
        assert _safe_int("abc") == 1


class TestElementOrder:
    def test_first_appearance_order(self):
        assert _element_order_in_formula("H2O") == ["H", "O"]
        assert _element_order_in_formula("CaCO3") == ["Ca", "C", "O"]

    def test_dedup_keeps_first(self):
        assert _element_order_in_formula("CH3CH2OH") == ["C", "H", "O"]


class TestReduceCounts:
    def test_divides_by_gcd(self):
        assert _reduce_counts({"H": 2, "O": 2}) == {"H": 1, "O": 1}
        assert _reduce_counts({"C": 6, "H": 12, "O": 6}) == {"C": 1, "H": 2, "O": 1}

    def test_already_reduced_unchanged(self):
        assert _reduce_counts({"Fe": 2, "O": 3}) == {"Fe": 2, "O": 3}

    def test_empty(self):
        assert _reduce_counts({}) == {}


class TestSignature:
    def test_order_independent(self):
        a = _signature_from_counts({"O": 2, "H": 2})
        b = _signature_from_counts({"H": 2, "O": 2})
        assert a == b == "H2|O2"

    def test_empty(self):
        assert _signature_from_counts({}) == ""


class TestJoinFormula:
    def test_sorted_default_and_drops_ones(self):
        # n == 1 is rendered without the number; default order is alphabetical.
        assert _join_formula_from_counts({"H": 2, "O": 1}) == "H2O"

    def test_respects_preferred_order(self):
        assert _join_formula_from_counts({"H": 2, "O": 1}, prefer_order=["O", "H"]) == "OH2"
        assert _join_formula_from_counts({"Na": 1, "Cl": 1}, prefer_order=["Na", "Cl"]) == "NaCl"


class TestCanonicalize:
    def test_reduces_but_keeps_user_order(self):
        assert canonicalize_preserve_user_order("H2O2") == "HO"
        assert canonicalize_preserve_user_order("C6H12O6") == "CH2O"

    def test_irreducible_roundtrips(self):
        assert canonicalize_preserve_user_order("Fe2O3") == "Fe2O3"
