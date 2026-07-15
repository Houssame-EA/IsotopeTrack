# -*- coding: utf-8 -*-
"""Tests for the Stage 4 particle-relabeling engine
(tools/particle_classifier_relabel.py) and its wiring into
ParticleClassifierNode.get_output_data.

The scientific correctness of this module matters more than most: it
decides what numbers a user sees in downstream mass/moles visualizations.
Key invariant under test — the Mass Fraction Calculator boundary: a group
backed by exactly one definition always keeps full particle-level fidelity
(pure relabeling of one already-internally-consistent particle population);
a group pooling 2+ definitions only keeps particle_mass_fg/particle_moles_fmol/
mass_fg (and their metadata) when the user explicitly opts in, since those
particles may carry different underlying MFC assumptions. elements/
element_mass_fg/element_moles_fmol/mass_percentages/mole_percentages are
always additive and safe regardless of pooling.
"""
import pytest

from tools import particle_classifier_relabel as pcr
from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id


def _particle(elements, sample='SampleA'):
    """A particle with every composition dict this module touches populated,
    mirroring mainwindow.py's real per-particle calculation output."""
    return {
        'elements': dict(elements),
        'element_mass_fg': {k: v * 0.1 for k, v in elements.items()},
        'element_moles_fmol': {k: v * 0.01 for k, v in elements.items()},
        'particle_mass_fg': {k: 100.0 for k in elements},
        'particle_moles_fmol': {k: 5.0 for k in elements},
        'mass_fg': {k: 100.0 for k in elements},
        'mass_fractions_used': {k: 1.0 for k in elements},
        'densities_used': {k: {'element_density': 8.9} for k in elements},
        'molar_masses': {k: 58.7 for k in elements},
        'mass_percentages': {k: 100.0 / len(elements) for k in elements},
        'mole_percentages': {k: 100.0 / len(elements) for k in elements},
        'totals': {'total_element_mass_fg': 1.0},
        'source_sample': sample,
        'element_diameter_nm': {k: 42.0 for k in elements},
        'particle_diameter_nm': 42.0,
    }


def _def(expr, target='SampleA', group=None, match_mode='partial'):
    return {'id': new_definition_id(), 'target_sample': target,
            'expression_text': expr, 'match_mode': match_mode,
            'group_name': group, 'color': None}


# --------------------------------------------------------------------------- #
# classify_particle
# --------------------------------------------------------------------------- #
class TestClassifyParticle:
    def test_matching_definition_found(self):
        p = _particle({'60Ni': 10})
        matches = pcr.classify_particle(p, [_def('60Ni')], 'double_count')
        assert len(matches) == 1

    def test_no_match_returns_empty(self):
        p = _particle({'208Pb': 1})
        matches = pcr.classify_particle(p, [_def('60Ni')], 'double_count')
        assert matches == []

    def test_double_count_returns_all_matches(self):
        p = _particle({'60Ni': 10, '107Ag': 5})
        defs = [_def('60Ni'), _def('60Ni+107Ag')]
        matches = pcr.classify_particle(p, defs, 'double_count')
        assert len(matches) == 2

    def test_priority_returns_only_highest(self):
        p = _particle({'60Ni': 10, '107Ag': 5})
        defs = [_def('60Ni'), _def('60Ni+107Ag')]  # index 0 = highest priority
        matches = pcr.classify_particle(p, defs, 'priority')
        assert len(matches) == 1
        assert matches[0] is defs[0]

    def test_exact_mode_rejects_extra_isotopes(self):
        p = _particle({'60Ni': 10, '107Ag': 5})
        matches = pcr.classify_particle(
            p, [_def('60Ni', match_mode='exact')], 'double_count')
        assert matches == []

    def test_unparseable_definition_is_skipped_not_raised(self):
        p = _particle({'60Ni': 10})
        bad = _def('60ni')  # lowercase -- invalid syntax
        assert pcr.classify_particle(p, [bad], 'double_count') == []


# --------------------------------------------------------------------------- #
# Aggregation policy -- the science-critical boundary
# --------------------------------------------------------------------------- #
class TestAggregationPolicy:
    def test_single_definition_group_keeps_everything(self):
        p = _particle({'60Ni': 10, '107Ag': 5})
        d = _def('60Ni+107Ag', group='Contamination')
        out = pcr.relabel_particles(
            [p], [d], {'Contamination': '#3B82F6'}, 'double_count',
            'unclassified', '#9CA3AF')[0]
        assert out['elements'] == {'Contamination': 15}
        assert out['particle_mass_fg'] == {'Contamination': 200.0}
        assert out['mass_fractions_used'] == {'Contamination': 1.0}
        assert out['element_diameter_nm'] == p['element_diameter_nm']
        assert out['particle_diameter_nm'] == 42.0
        assert out['source_sample'] == 'SampleA'

    def test_multi_definition_group_drops_mfc_keys_by_default(self):
        p1, p2 = _particle({'60Ni': 10}), _particle({'197Au': 3})
        defs = [_def('60Ni', group='Mix'), _def('197Au', group='Mix')]
        out = pcr.relabel_particles(
            p := [p1, p2], defs, {'Mix': '#EF4444'}, 'double_count',
            'unclassified', '#9CA3AF')
        for r in out:
            assert 'particle_mass_fg' not in r
            assert 'particle_moles_fmol' not in r
            assert 'mass_fg' not in r
            assert 'mass_fractions_used' not in r
            assert 'densities_used' not in r
            assert 'molar_masses' not in r

    def test_multi_definition_group_keeps_additive_keys_always(self):
        p1, p2 = _particle({'60Ni': 10}), _particle({'197Au': 3})
        defs = [_def('60Ni', group='Mix'), _def('197Au', group='Mix')]
        out = pcr.relabel_particles(
            [p1, p2], defs, {'Mix': '#EF4444'}, 'double_count',
            'unclassified', '#9CA3AF')
        for r in out:
            assert r['elements'] in ({'Mix': 10}, {'Mix': 3})
            assert 'mass_percentages' in r
            assert 'mole_percentages' in r

    def test_multi_definition_group_keeps_mfc_keys_when_policy_is_keep(self):
        p1, p2 = _particle({'60Ni': 10}), _particle({'197Au': 3})
        defs = [_def('60Ni', group='Mix'), _def('197Au', group='Mix')]
        out = pcr.relabel_particles(
            [p1, p2], defs, {'Mix': '#EF4444'}, 'double_count',
            'unclassified', '#9CA3AF', group_pooling_policies={'Mix': 'keep'})
        for r in out:
            assert 'particle_mass_fg' in r

    def test_diameter_fields_never_touched(self):
        """Standing project-wide constraint: never read/write diameter."""
        p = _particle({'60Ni': 10, '107Ag': 5})
        d = _def('60Ni+107Ag')
        out = pcr.relabel_particles(
            [p], [d], {}, 'double_count', 'unclassified', '#9CA3AF')[0]
        assert out['element_diameter_nm'] == p['element_diameter_nm']
        assert out['particle_diameter_nm'] == p['particle_diameter_nm']


# --------------------------------------------------------------------------- #
# Unmatched-particle modes (design §6)
# --------------------------------------------------------------------------- #
class TestUnmatchedModes:
    def _setup(self):
        return _particle({'208Pb': 1}), _def('60Ni')

    def test_unclassified_bucket(self):
        p, d = self._setup()
        out = pcr.relabel_particles(
            [p], [d], {}, 'double_count', 'unclassified', '#9CA3AF')
        assert len(out) == 1
        assert out[0]['elements'] == {'Unclassified': 1}

    def test_discard(self):
        p, d = self._setup()
        out = pcr.relabel_particles(
            [p], [d], {}, 'double_count', 'discard', '#9CA3AF')
        assert out == []

    def test_passthrough_keeps_original_composition(self):
        p, d = self._setup()
        out = pcr.relabel_particles(
            [p], [d], {}, 'double_count', 'passthrough', '#9CA3AF')
        assert len(out) == 1
        assert out[0]['elements'] == {'208Pb': 1}

    def test_mixed_matched_and_passthrough_in_one_sample(self):
        matched = _particle({'60Ni': 10})
        unmatched = _particle({'208Pb': 1})
        out = pcr.relabel_particles(
            [matched, unmatched], [_def('60Ni', group='Contamination')], {},
            'double_count', 'passthrough', '#9CA3AF')
        assert len(out) == 2
        labels = [r['elements'] for r in out]
        assert {'Contamination': 10} in labels  # matched one relabeled to its group
        assert {'208Pb': 1} in labels  # unmatched kept fully raw


# --------------------------------------------------------------------------- #
# multi_definition_groups / group_pooling_status
# --------------------------------------------------------------------------- #
class TestGroupPoolingHelpers:
    def test_identifies_multi_definition_groups(self):
        defs = [_def('60Ni', group='A'), _def('107Ag', group='A'),
                _def('197Au', group='B')]
        assert pcr.multi_definition_groups(defs) == ['A']

    def test_single_definition_groups_excluded(self):
        defs = [_def('60Ni', group='A'), _def('107Ag', group='B')]
        assert pcr.multi_definition_groups(defs) == []

    def test_ungrouped_definitions_ignored(self):
        defs = [_def('60Ni'), _def('107Ag')]
        assert pcr.multi_definition_groups(defs) == []


# --------------------------------------------------------------------------- #
# Node-level get_output_data wiring
# --------------------------------------------------------------------------- #
class TestNodeOutputWiring:
    def _single_sample_upstream(self, particles):
        return {
            'type': 'sample_data',
            'sample_name': 'SampleA',
            'data': {},
            'particle_data': particles,
            'selected_isotopes': [{'label': '60Ni'}],
            'total_particles': len(particles),
            'concentration_meta': {'SampleA': {'volume_ml': 5.0}},
            'parent_window': None,
        }

    def test_preserves_concentration_meta_and_type(self):
        node = ParticleClassifierNode()
        node.definitions = [_def('60Ni')]
        node.input_data = self._single_sample_upstream([_particle({'60Ni': 10})])
        out = node.get_output_data()
        assert out['type'] == 'sample_data'
        assert out['concentration_meta'] == {'SampleA': {'volume_ml': 5.0}}

    def test_relabels_particle_data(self):
        node = ParticleClassifierNode()
        node.definitions = [_def('60Ni')]
        node.input_data = self._single_sample_upstream([_particle({'60Ni': 10})])
        out = node.get_output_data()
        assert out['particle_data'][0]['elements'] == {'60Ni': 10}
        assert out['filtered_particles'] == 1

    def test_no_upstream_returns_none(self):
        node = ParticleClassifierNode()
        assert node.get_output_data() is None

    def test_selected_sources_filters_samples(self):
        node = ParticleClassifierNode()
        node.definitions = [_def('60Ni')]
        node.selected_sources = ['SampleB']  # not in upstream
        node.input_data = self._single_sample_upstream([_particle({'60Ni': 10})])
        assert node.get_output_data() is None
