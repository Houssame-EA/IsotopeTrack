# -*- coding: utf-8 -*-
"""Tests for composition-aware ground truth in results/cluster/tools.py.

Ground truth used to be defined by elemental combination alone, so two alloy
standards made of the same elements — say Ag-Au at 80:20 and Ag-Au at 50:50 —
collapsed into one truth group and the second entry was silently dropped as a
duplicate element set. These tests pin the two-stage behaviour that replaces it:
presence matching first, then target percentages with a tolerance.

The important guarantees, in order of how badly a regression would hurt:

* two components sharing an element set survive when both declare percentages;
* particles land in the nearest target and only inside its tolerance, with the
  ambiguous ones going to ``other`` rather than to the closer wrong answer;
* every pre-existing presence-only definition still behaves exactly as before,
  including the old ``(name, elements)`` two-tuple shape.
"""
import numpy as np
import pytest

from results.cluster import tools


ELEMENTS = ['107Ag', '197Au', '48Ti']

TWO_ALLOYS = "AgAu(1)=107Ag:80+197Au:20 ~5 ; AgAu(2)=107Ag:50+197Au:50 ~5"


def _alloy_rows(ag_pct, n, seed, spread=0.5):
    """Rows of an Ag-Au alloy at a given Ag mass %, with a little scatter."""
    rng = np.random.default_rng(seed)
    ag = rng.normal(ag_pct, spread, n)
    return np.column_stack([ag, 100.0 - ag, np.zeros(n)])


# --------------------------------------------------------------------------- #
# parse_components
# --------------------------------------------------------------------------- #
class TestParseComponents:
    def test_presence_only_entry_has_no_spec(self):
        (name, elems, spec), = tools.parse_components("56Fe+60Ni")
        assert name == "56Fe+60Ni"
        assert elems == ['56Fe', '60Ni']
        assert spec is None

    def test_fused_token_still_splits(self):
        (name, elems, spec), = tools.parse_components("FeNiCo")
        assert elems == ['Fe', 'Ni', 'Co']
        assert spec is None

    def test_percentages_and_tolerance(self):
        (name, elems, spec), = tools.parse_components(
            "AgAu(1)=107Ag:80+197Au:20 ~5")
        assert name == 'AgAu(1)'
        assert elems == ['107Ag', '197Au']
        assert spec['targets'] == {'107Ag': 80.0, '197Au': 20.0}
        assert spec['tol'] == 5.0

    def test_plus_minus_sign_accepted_as_tolerance(self):
        (_, _, spec), = tools.parse_components("X=107Ag:80+197Au:20 ±2.5")
        assert spec['tol'] == 2.5

    def test_missing_tolerance_falls_back_to_default(self):
        (_, _, spec), = tools.parse_components("X=107Ag:80+197Au:20")
        assert spec['tol'] == tools.DEFAULT_COMPOSITION_TOL

    def test_targets_are_normalised_to_100(self):
        (_, _, spec), = tools.parse_components("X=107Ag:8+197Au:2")
        assert spec['targets'] == pytest.approx({'107Ag': 80.0, '197Au': 20.0})
        assert spec['raw_sum'] == 10.0

    def test_unreadable_percentage_degrades_to_presence(self):
        (_, elems, spec), = tools.parse_components("X=107Ag:abc+197Au:20")
        assert elems == ['107Ag', '197Au']
        assert '107Ag' not in spec['targets']


# --------------------------------------------------------------------------- #
# resolve_components
# --------------------------------------------------------------------------- #
class TestResolveComponents:
    def test_same_elements_both_with_percentages_are_kept(self):
        res = tools.resolve_components(
            tools.parse_components(TWO_ALLOYS), ELEMENTS)
        assert res['names'] == ['AgAu(1)', 'AgAu(2)']
        assert res['duplicate_sets'] == []
        assert res['composition_count'] == 2

    def test_same_elements_without_percentages_still_rejected(self):
        res = tools.resolve_components(
            tools.parse_components("AgAu=107Ag+197Au ; AgAu2=107Ag+197Au"),
            ELEMENTS)
        assert res['names'] == ['AgAu']
        assert res['duplicate_sets'] == [('AgAu2', 'AgAu')]

    def test_bare_entry_colliding_with_a_specced_one_is_rejected(self):
        """The bare entry loses: it would swallow the whole combination
        before stage two ever ran."""
        res = tools.resolve_components(
            tools.parse_components(
                "AgAu(1)=107Ag:80+197Au:20 ~5 ; AgAu=107Ag+197Au"),
            ELEMENTS)
        assert res['names'] == ['AgAu(1)']
        assert res['duplicate_sets'] == [('AgAu', 'AgAu(1)')]

    def test_targets_resolve_to_column_indices(self):
        res = tools.resolve_components(
            tools.parse_components("X=Ag:80+Au:20 ~5"), ELEMENTS)
        assert res['specs'][0]['targets'] == {0: 80.0, 1: 20.0}

    def test_element_without_a_percentage_is_reported_and_zeroed(self):
        res = tools.resolve_components(
            tools.parse_components("X=107Ag:80+197Au ~5"), ELEMENTS)
        assert res['specs'][0]['targets'][1] == 0.0
        assert res['partial_percentages'] == [('X', ['197Au'])]
        assert any('197Au' in i for i in res['issues'])

    def test_rescaling_is_reported(self):
        res = tools.resolve_components(
            tools.parse_components("X=107Ag:8+197Au:2 ~5"), ELEMENTS)
        assert res['renormalised'] == [('X', 10.0)]

    def test_two_tuple_entries_still_accepted(self):
        res = tools.resolve_components(
            [('AgAu', ['107Ag', '197Au']), ('Ti', ['48Ti'])], ELEMENTS)
        assert res['names'] == ['AgAu', 'Ti']
        assert res['specs'] == [None, None]


# --------------------------------------------------------------------------- #
# build_ground_truth — the behaviour that motivated all of this
# --------------------------------------------------------------------------- #
class TestGroundTruthComposition:
    def test_two_alloys_of_the_same_elements_separate(self):
        m = np.vstack([_alloy_rows(80, 50, seed=1),
                       _alloy_rows(50, 40, seed=2)])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components(TWO_ALLOYS))
        assert truth['counts']['AgAu(1)'] == 50
        assert truth['counts']['AgAu(2)'] == 40
        assert truth['counts']['other'] == 0
        assert set(truth['labels'][:50]) == {truth['name_to_id']['AgAu(1)']}
        assert set(truth['labels'][50:]) == {truth['name_to_id']['AgAu(2)']}

    def test_particle_outside_every_tolerance_becomes_other(self):
        """65:35 sits 15 points from both targets, so no honest answer
        exists and the particle must not be forced into either."""
        m = np.array([[65.0, 35.0, 0.0]])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components(TWO_ALLOYS))
        assert truth['counts']['other'] == 1
        assert truth['outside_tolerance'] == 1

    def test_particle_goes_to_the_nearer_target(self):
        m = np.array([[78.0, 22.0, 0.0], [52.0, 48.0, 0.0]])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components(TWO_ALLOYS))
        assert truth['names'][truth['labels'][0]] == 'AgAu(1)'
        assert truth['names'][truth['labels'][1]] == 'AgAu(2)'

    def test_wider_tolerance_absorbs_the_ambiguous_particle(self):
        m = np.array([[65.0, 35.0, 0.0]])
        truth = tools.build_ground_truth(
            m, ELEMENTS,
            tools.parse_components("A=107Ag:80+197Au:20 ~20 ; "
                                   "B=107Ag:50+197Au:50 ~1"))
        assert truth['names'][truth['labels'][0]] == 'A'

    def test_percentages_ignore_elements_outside_the_component(self):
        """A trace of Ti must not shift the Ag:Au ratio.

        The first assertion pins stage one: presence puts the particle in the
        three-element group. Had the ratio been taken over all columns it would
        read 79.7:19.9 and still sit inside ~1, so the second assertion is what
        pins the renormalisation.
        """
        m = np.array([[80.0, 20.0, 0.4]])
        comps = tools.parse_components(
            "AgAu(1)=107Ag:80+197Au:20 ~1 ; AgAuTi=107Ag+197Au+48Ti")
        truth = tools.build_ground_truth(m, ELEMENTS, comps)
        assert truth['names'][truth['labels'][0]] == 'AgAuTi'

        truth2 = tools.build_ground_truth(
            np.array([[80.0, 20.0, 0.0]]), ELEMENTS, comps)
        assert truth2['names'][truth2['labels'][0]] == 'AgAu(1)'

    def test_composition_matrix_overrides_the_presence_matrix(self):
        counts = np.array([[10.0, 90.0, 0.0]])          # signal says 10:90
        mass = np.array([[80.0, 20.0, 0.0]])            # mass says 80:20
        truth = tools.build_ground_truth(
            counts, ELEMENTS, tools.parse_components(TWO_ALLOYS),
            composition_matrix=mass)
        assert truth['names'][truth['labels'][0]] == 'AgAu(1)'
        assert truth['composition_basis'] == 'supplied matrix'

    def test_empty_composition_matrix_falls_back_and_says_so(self):
        counts = np.array([[80.0, 20.0, 0.0]])
        truth = tools.build_ground_truth(
            counts, ELEMENTS, tools.parse_components(TWO_ALLOYS),
            composition_matrix=np.zeros_like(counts))
        assert truth['names'][truth['labels'][0]] == 'AgAu(1)'
        assert 'supplied was empty' in truth['composition_basis']

    def test_lone_component_with_targets_still_enforces_tolerance(self):
        m = np.array([[80.0, 20.0, 0.0], [55.0, 45.0, 0.0]])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components("AgAu(1)=107Ag:80+197Au:20 ~5"))
        assert truth['counts']['AgAu(1)'] == 1
        assert truth['counts']['other'] == 1

    def test_other_flags_still_win_over_a_composition_match(self):
        m = _alloy_rows(80, 4, seed=3)
        flags = np.array([False, True, False, True])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components(TWO_ALLOYS),
            other_flags=flags)
        assert truth['counts']['other'] == 2


# --------------------------------------------------------------------------- #
# build_ground_truth — nothing that worked before may change
# --------------------------------------------------------------------------- #
class TestGroundTruthBackwardCompatible:
    def test_presence_only_definitions_unchanged(self):
        m = np.vstack([_alloy_rows(80, 5, seed=4),
                       _alloy_rows(50, 3, seed=5),
                       np.array([[0.0, 0.0, 12.0]])])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components("107Ag+197Au ; 48Ti"))
        assert truth['counts']['107Ag+197Au'] == 8
        assert truth['counts']['48Ti'] == 1
        assert truth['counts']['other'] == 0
        assert truth['outside_tolerance'] == 0

    def test_old_two_tuple_component_shape_accepted(self):
        m = _alloy_rows(80, 6, seed=6)
        truth = tools.build_ground_truth(
            m, ELEMENTS, [('AgAu', ['107Ag', '197Au'])])
        assert truth['counts']['AgAu'] == 6

    def test_zero_signal_rows_are_other(self):
        m = np.zeros((3, 3))
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components(TWO_ALLOYS))
        assert truth['counts']['other'] == 3

    def test_empty_matrix_is_handled(self):
        truth = tools.build_ground_truth(
            np.zeros((0, 3)), ELEMENTS, tools.parse_components(TWO_ALLOYS))
        assert truth['labels'].shape == (0,)
        assert truth['unmatched'] == 0

    def test_presence_threshold_still_applies(self):
        """Au at 0.5% of signal drops out above a 1% presence threshold, so
        the particle reads as pure Ag."""
        m = np.array([[99.5, 0.5, 0.0]])
        truth = tools.build_ground_truth(
            m, ELEMENTS, tools.parse_components("107Ag ; 107Ag+197Au"),
            presence_threshold=0.01)
        assert truth['names'][truth['labels'][0]] == '107Ag'
