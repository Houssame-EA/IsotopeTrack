# -*- coding: utf-8 -*-
"""Tests for results/utils_sort.py.

These helpers decide the order isotopes appear in tables, legends and plots.
The module is pure (only ``re``), so it is the cheapest possible thing to test
and a wrong sort is an immediately visible bug for users.
"""
from results.utils_sort import (
    extract_mass_and_element,
    sort_elements_by_mass,
    sort_element_dict_by_mass,
    element_alphabetical_key,
)


class TestExtractMassAndElement:
    def test_splits_mass_and_symbol(self):
        assert extract_mass_and_element("55Fe") == (55, "Fe")
        assert extract_mass_and_element("107Ag") == (107, "Ag")

    def test_symbol_without_mass_sorts_last(self):
        # 999 sentinel pushes mass-less labels to the end of an ascending sort.
        assert extract_mass_and_element("Fe") == (999, "Fe")

    def test_strips_whitespace(self):
        assert extract_mass_and_element("  56Fe  ") == (56, "Fe")


class TestSortElementsByMass:
    def test_orders_ascending_by_mass(self):
        out = sort_elements_by_mass(["107Ag", "56Fe", "12C"])
        assert out == ["12C", "56Fe", "107Ag"]

    def test_massless_labels_go_last(self):
        out = sort_elements_by_mass(["Fe", "12C", "197Au"])
        assert out == ["12C", "197Au", "Fe"]

    def test_stable_and_non_destructive(self):
        original = ["56Fe", "12C"]
        sort_elements_by_mass(original)
        assert original == ["56Fe", "12C"]  # input not mutated

    def test_empty_list(self):
        assert sort_elements_by_mass([]) == []


class TestSortElementDictByMass:
    def test_reorders_keys_by_mass(self):
        d = {"107Ag": 1, "12C": 2, "56Fe": 3}
        assert list(sort_element_dict_by_mass(d).keys()) == ["12C", "56Fe", "107Ag"]

    def test_preserves_values(self):
        d = {"107Ag": "a", "12C": "b"}
        out = sort_element_dict_by_mass(d)
        assert out["12C"] == "b" and out["107Ag"] == "a"

    def test_empty_dict_passthrough(self):
        assert sort_element_dict_by_mass({}) == {}


class TestElementAlphabeticalKey:
    def test_ignores_mass_prefix(self):
        # '107Ag' and 'Ag' both key on 'ag'.
        assert element_alphabetical_key("107Ag") == element_alphabetical_key("Ag")

    def test_case_insensitive(self):
        assert element_alphabetical_key("56FE") == "fe"

    def test_used_as_sort_key(self):
        labels = ["56Fe", "107Ag", "63Cu"]
        assert sorted(labels, key=element_alphabetical_key) == ["107Ag", "63Cu", "56Fe"]
