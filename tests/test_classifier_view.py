# -*- coding: utf-8 -*-
"""Tests for the classifier -> viz "one size fits most" foundation:

- ``results/classifier_view.py`` — the shared reader API every viz node
  goes through to render classifier output (dual-carried raw composition,
  bucket registry, particle identity/dedupe, the role model).
- The dual-carry wiring itself in ``tools/particle_classifier_relabel.py``
  and ``ParticleClassifierNode.get_output_data``.
- ``shared_plot_utils.build_element_matrix``'s ``raw=``/``dedupe=`` seam.
- ``shared_plot_utils.ClassifierViewGroup`` — the role picker.
- The config-aliasing fix (``deep_copy_config`` at node construction).

The invariant that matters most here: dual-carry is **additive**. The
destructive collapse still happens exactly as before, so every node that
reads one composition key at a time is bit-for-bit unaffected; the real
isotopes just also survive alongside it for the nodes that need them.

See ``.claude/aug24.md``, "Classifier -> viz plotting correctness".
"""
import pytest

from results import classifier_view as cv
from tools import particle_classifier_relabel as pcr
from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id


def _particle(elements, sample='SampleA'):
    return {
        'elements': dict(elements),
        'element_mass_fg': {k: v * 0.1 for k, v in elements.items()},
        'element_moles_fmol': {k: v * 0.01 for k, v in elements.items()},
        'mass_percentages': {k: 100.0 / len(elements) for k in elements},
        'mole_percentages': {k: 100.0 / len(elements) for k in elements},
        'source_sample': sample,
        'element_diameter_nm': {k: 42.0 for k in elements},
    }


def _def(expr, target='SampleA', group=None, match_mode='partial'):
    return {'id': new_definition_id(), 'target_sample': target,
            'expression_text': expr, 'match_mode': match_mode,
            'group_name': group, 'color': None}


def _relabel(particles, defs, overlap='double_count', unmatched='unclassified',
             groups=None):
    return pcr.relabel_particles(
        particles, defs, groups or {}, overlap, unmatched, '#9CA3AF')


# --------------------------------------------------------------------------- #
# Dual-carry: the collapse still happens, the originals survive alongside it
# --------------------------------------------------------------------------- #
class TestDualCarry:
    def test_collapse_still_destructive_as_before(self):
        """The whole point of dual-carry is that it changes nothing for the
        nodes the collapse always worked for.

        Note the collapsed value is 10, not 14: the collapse sums only the
        MATCHED DEFINITION's referenced isotopes, so 107Ag is excluded as
        outside this definition's vocabulary (mirroring the evaluator's own
        partial/exact semantics). That asymmetry is exactly why the raw
        composition has to be carried separately — the collapsed entry is
        not a lossy summary of the particle, it is a summary of the
        definition's view of the particle."""
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        assert out[0]['elements'] == {'60Ni': 10}

    def test_raw_composition_recoverable(self):
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        assert cv.composition(out[0], 'elements') == {'60Ni': 10, '107Ag': 4}

    def test_collapsed_available_explicitly(self):
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        assert cv.composition(out[0], 'elements', collapsed=True) == {'60Ni': 10}

    def test_collapse_aggregates_across_a_definitions_isotopes(self):
        """When a definition DOES reference both isotopes, they sum — which
        is the behavior that makes a bucket look like one isotope."""
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})],
                       [_def('60Ni+107Ag')])
        assert out[0]['elements'] == {'60Ni+107Ag': 14}

    def test_raw_carried_by_reference_not_copied(self):
        """Near-zero memory cost is the reason dual-carry is affordable at
        all — assert it really is reference-sharing, not a deep copy."""
        p = _particle({'60Ni': 10})
        original = p['elements']
        out = _relabel([p], [_def('60Ni')])
        assert out[0][pcr.RAW_KEY]['elements'] is original

    def test_upstream_particle_never_mutated(self):
        p = _particle({'60Ni': 10, '107Ag': 4})
        _relabel([p], [_def('60Ni')])
        assert p['elements'] == {'60Ni': 10, '107Ag': 4}

    @pytest.mark.parametrize("key", [
        'elements', 'element_mass_fg', 'element_moles_fmol',
        'mass_percentages', 'mole_percentages'])
    def test_every_relabeled_key_is_carried(self, key):
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        assert set(cv.composition(out[0], key)) == {'60Ni', '107Ag'}

    def test_bucket_label_stamped(self):
        out = _relabel([_particle({'60Ni': 10})],
                       [_def('60Ni', group='Smelter')],
                       groups={'Smelter': '#FF6600'})
        assert cv.bucket_of(out[0]) == 'Smelter'

    def test_unclassified_particle_labelled(self):
        out = _relabel([_particle({'197Au': 3})], [_def('60Ni')])
        assert cv.bucket_of(out[0]) == 'Unclassified'

    def test_passthrough_particle_has_no_bucket_but_still_answers(self):
        out = _relabel([_particle({'197Au': 3})], [_def('60Ni')],
                       unmatched='passthrough')
        assert cv.bucket_of(out[0]) is None
        # Still readable through the same helper — no special case needed.
        assert cv.composition(out[0], 'elements') == {'197Au': 3}

    def test_discard_mode_emits_nothing(self):
        out = _relabel([_particle({'197Au': 3})], [_def('60Ni')],
                       unmatched='discard')
        assert out == []

    def test_diameter_fields_untouched_and_readable(self):
        """Diameters are never relabeled (standing project constraint), so
        composition() must fall through to the particle's own dict."""
        out = _relabel([_particle({'60Ni': 10})], [_def('60Ni')])
        assert cv.composition(out[0], 'element_diameter_nm') == {'60Ni': 42.0}

    def test_non_classifier_particle_reads_through_unchanged(self):
        p = _particle({'60Ni': 10})
        assert cv.composition(p, 'elements') == {'60Ni': 10}
        assert cv.bucket_of(p) is None


# --------------------------------------------------------------------------- #
# Particle identity + dedupe (the double_count hazard)
# --------------------------------------------------------------------------- #
class TestParticleIdentity:
    def test_src_index_stamped_on_every_branch(self):
        particles = [_particle({'60Ni': 10}), _particle({'197Au': 3})]
        out = _relabel(particles, [_def('60Ni')])
        assert [p[pcr.SRC_INDEX_KEY] for p in out] == [0, 1]

    def test_double_counted_copies_share_one_identity(self):
        """One source particle matching two definitions is emitted twice —
        both copies must resolve to the SAME identity, or dedupe can't work."""
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})],
                       [_def('60Ni'), _def('107Ag')], overlap='double_count')
        assert len(out) == 2
        assert cv.particle_identity(out[0]) == cv.particle_identity(out[1])

    def test_dedupe_collapses_double_counted(self):
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})],
                       [_def('60Ni'), _def('107Ag')], overlap='double_count')
        assert len(cv.dedupe_particles(out)) == 1

    def test_dedupe_keeps_genuinely_distinct_particles(self):
        particles = [_particle({'60Ni': 10}), _particle({'60Ni': 20})]
        out = _relabel(particles, [_def('60Ni')])
        assert len(cv.dedupe_particles(out)) == 2

    def test_identity_is_sample_scoped(self):
        """src_index is only unique WITHIN a sample, so two samples' particle
        0 must not collide into one identity."""
        a = _relabel([_particle({'60Ni': 10}, sample='A')], [_def('60Ni', 'A')])
        b = _relabel([_particle({'60Ni': 10}, sample='B')], [_def('60Ni', 'B')])
        assert cv.particle_identity(a[0]) != cv.particle_identity(b[0])
        assert len(cv.dedupe_particles(a + b)) == 2

    def test_dedupe_passes_through_non_classifier_particles(self):
        particles = [_particle({'60Ni': 10}), _particle({'107Ag': 4})]
        assert cv.dedupe_particles(particles) == particles

    def test_dedupe_is_order_stable(self):
        particles = [_particle({'60Ni': i}) for i in range(1, 6)]
        out = cv.dedupe_particles(_relabel(particles, [_def('60Ni')]))
        assert [p[pcr.SRC_INDEX_KEY] for p in out] == [0, 1, 2, 3, 4]


# --------------------------------------------------------------------------- #
# Bucket registry + the literal expression (july22.md #8)
# --------------------------------------------------------------------------- #
class TestBucketRegistry:
    def test_expression_recoverable_from_label(self):
        reg = pcr.build_bucket_registry(
            [_def('60Ni+107Ag', group='Smelter')], {'Smelter': '#FF6600'},
            'unclassified', '#9CA3AF')
        data = {'_classifier_registry': reg}
        assert cv.expressions_for(data, 'Smelter') == ['60Ni+107Ag']

    def test_multi_definition_group_keeps_every_expression(self):
        """A group backed by 2 definitions has 2 expressions — flattening to
        one string would silently drop the other."""
        reg = pcr.build_bucket_registry(
            [_def('60Ni', group='Smelter'), _def('197Au', group='Smelter')],
            {'Smelter': '#FF6600'}, 'unclassified', '#9CA3AF')
        assert cv.expressions_for({'_classifier_registry': reg}, 'Smelter') == [
            '60Ni', '197Au']

    def test_caption_shows_name_and_expression(self):
        reg = pcr.build_bucket_registry(
            [_def('60Ni+107Ag', group='Smelter')], {'Smelter': '#FF6600'},
            'unclassified', '#9CA3AF')
        cap = cv.bucket_caption({'_classifier_registry': reg}, 'Smelter')
        assert 'Smelter' in cap and '60Ni+107Ag' in cap

    def test_caption_truncates_long_expressions(self):
        reg = pcr.build_bucket_registry(
            [_def('60Ni', group='G')], {'G': '#FFF'}, 'unclassified', '#9CA3AF')
        reg['G']['definitions'][0]['expression_text'] = 'X' * 200
        cap = cv.bucket_caption({'_classifier_registry': reg}, 'G', max_len=20)
        assert len(cap) < 60 and cap.endswith('…)')

    def test_unclassified_bucket_registered_with_no_expression(self):
        reg = pcr.build_bucket_registry(
            [_def('60Ni')], {}, 'unclassified', '#9CA3AF')
        assert 'Unclassified' in reg
        assert cv.expressions_for({'_classifier_registry': reg},
                                  'Unclassified') == []

    def test_unclassified_absent_in_discard_mode(self):
        reg = pcr.build_bucket_registry([_def('60Ni')], {}, 'discard', '#9CA3AF')
        assert 'Unclassified' not in reg

    def test_blank_expressions_skipped(self):
        reg = pcr.build_bucket_registry(
            [_def('   ')], {}, 'discard', '#9CA3AF')
        assert reg == {}

    def test_colliding_labels_accumulate_rather_than_overwrite(self):
        """Two ungrouped definitions with identical expression text collapse
        to one label — they must pool, not silently drop one."""
        reg = pcr.build_bucket_registry(
            [_def('60Ni'), _def('60Ni')], {}, 'discard', '#9CA3AF')
        assert len(reg) == 1
        assert len(next(iter(reg.values()))['definitions']) == 2

    def test_bucket_color_exposed(self):
        reg = pcr.build_bucket_registry(
            [_def('60Ni', group='Smelter')], {'Smelter': '#FF6600'},
            'discard', '#9CA3AF')
        assert cv.bucket_color({'_classifier_registry': reg},
                               'Smelter') == '#FF6600'


# --------------------------------------------------------------------------- #
# Stream introspection through the real node
# --------------------------------------------------------------------------- #
def _wired_node(unmatched='unclassified', overlap='double_count'):
    node = ParticleClassifierNode()
    node.input_data = {
        'type': 'sample_data',
        'sample_name': 'SampleA',
        'particle_data': [
            _particle({'60Ni': 10, '107Ag': 4}),
            _particle({'197Au': 3}),
        ],
        'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'},
                              {'label': '197Au'}],
    }
    node.definitions = [_def('60Ni', group='Smelter')]
    node.groups = {'Smelter': '#FF6600'}
    node.unmatched_mode = unmatched
    node.overlap_mode = overlap
    return node


class TestStreamIntrospection:
    def test_plain_sample_is_not_a_classifier_stream(self):
        assert cv.is_classifier_stream({'type': 'sample_data'}) is False
        assert cv.is_classifier_stream(None) is False

    def test_classifier_output_is_detected(self):
        out = _wired_node().get_output_data()
        assert cv.is_classifier_stream(out) is True

    def test_raw_isotope_vocabulary_survives(self):
        """selected_isotopes gets rewritten to bucket labels; the real
        vocabulary must still be recoverable or isotope pickers break."""
        out = _wired_node().get_output_data()
        assert cv.raw_isotope_labels(out) == ['60Ni', '107Ag', '197Au']

    def test_selected_isotopes_still_names_buckets(self):
        """The design §7 behavior downstream SERIES nodes rely on is intact."""
        out = _wired_node().get_output_data()
        labels = [i['label'] for i in out['selected_isotopes']]
        assert 'Smelter' in labels

    def test_raw_vocabulary_falls_back_on_plain_stream(self):
        plain = {'selected_isotopes': [{'label': '60Ni'}]}
        assert cv.raw_isotope_labels(plain) == ['60Ni']

    def test_registry_present_on_output(self):
        out = _wired_node().get_output_data()
        assert cv.expressions_for(out, 'Smelter') == ['60Ni']

    def test_particles_partition_by_bucket(self):
        out = _wired_node().get_output_data()
        groups = cv.particles_by_bucket(out['particle_data'])
        assert set(groups) == {'Smelter', 'Unclassified'}

    def test_passthrough_particles_group_under_none(self):
        out = _wired_node(unmatched='passthrough').get_output_data()
        groups = cv.particles_by_bucket(out['particle_data'])
        assert None in groups

    def test_has_multiple_buckets(self):
        assert cv.has_multiple_buckets(_wired_node().get_output_data()) is True
        single = _wired_node(unmatched='discard').get_output_data()
        assert cv.has_multiple_buckets(single) is False


# --------------------------------------------------------------------------- #
# The role model
# --------------------------------------------------------------------------- #
class TestRoles:
    def test_series_only_offered_to_per_key_nodes(self):
        assert cv.ROLE_SERIES in cv.available_roles(cv.ARITY_PER_KEY)
        assert cv.ROLE_SERIES not in cv.available_roles(cv.ARITY_KEY_SET)
        assert cv.ROLE_SERIES not in cv.available_roles(cv.ARITY_MULTI_KEY)

    def test_off_always_available(self):
        for arity in (cv.ARITY_PER_KEY, cv.ARITY_KEY_SET, cv.ARITY_MULTI_KEY):
            assert cv.ROLE_OFF in cv.available_roles(arity)

    def test_defaults_preserve_existing_behavior(self):
        assert cv.default_role(cv.ARITY_PER_KEY) == cv.ROLE_SERIES
        assert cv.default_role(cv.ARITY_MULTI_KEY) == cv.ROLE_OFF

    def test_unknown_arity_is_conservative(self):
        assert cv.ROLE_SERIES not in cv.available_roles('nonsense')
        assert cv.default_role('nonsense') == cv.ROLE_OFF

    def test_non_classifier_stream_always_off(self):
        cfg = {cv.ROLE_CONFIG_KEY: cv.ROLE_FACET}
        assert cv.effective_role(cfg, {'type': 'sample_data'},
                                 cv.ARITY_MULTI_KEY) == cv.ROLE_OFF

    def test_stored_role_honored_on_classifier_stream(self):
        out = _wired_node().get_output_data()
        cfg = {cv.ROLE_CONFIG_KEY: cv.ROLE_FACET}
        assert cv.effective_role(cfg, out, cv.ARITY_MULTI_KEY) == cv.ROLE_FACET

    def test_impossible_stored_role_falls_back_not_crashes(self):
        """A saved project can restore a role the node can't honor — links
        reload with connection rules suspended, so this must be caught at
        render time, not assumed away."""
        out = _wired_node().get_output_data()
        cfg = {cv.ROLE_CONFIG_KEY: cv.ROLE_SERIES}
        assert cv.effective_role(cfg, out, cv.ARITY_MULTI_KEY) == cv.ROLE_OFF

    def test_missing_role_uses_arity_default(self):
        out = _wired_node().get_output_data()
        assert cv.effective_role({}, out, cv.ARITY_PER_KEY) == cv.ROLE_SERIES


# --------------------------------------------------------------------------- #
# build_element_matrix raw/dedupe seam
# --------------------------------------------------------------------------- #
class TestBuildElementMatrix:
    def test_collapsed_default_yields_one_column_per_bucket(self):
        """The status quo that makes every multi-key chart degenerate."""
        from results.shared_plot_utils import build_element_matrix
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        df = build_element_matrix(out, 'elements')
        assert list(df.columns) == ['60Ni']

    def test_raw_restores_real_isotope_columns(self):
        from results.shared_plot_utils import build_element_matrix
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})], [_def('60Ni')])
        df = build_element_matrix(out, 'elements', raw=True)
        assert list(df.columns) == ['107Ag', '60Ni']

    def test_dedupe_prevents_double_weighting(self):
        from results.shared_plot_utils import build_element_matrix
        out = _relabel([_particle({'60Ni': 10, '107Ag': 4})],
                       [_def('60Ni'), _def('107Ag')], overlap='double_count')
        assert len(build_element_matrix(out, 'elements', raw=True)) == 2
        assert len(build_element_matrix(
            out, 'elements', raw=True, dedupe=True)) == 1

    def test_unchanged_on_plain_particles(self):
        from results.shared_plot_utils import build_element_matrix
        particles = [_particle({'60Ni': 10, '107Ag': 4})]
        plain = build_element_matrix(particles, 'elements')
        raw = build_element_matrix(particles, 'elements', raw=True, dedupe=True)
        assert list(plain.columns) == list(raw.columns)
        assert len(plain) == len(raw)


# --------------------------------------------------------------------------- #
# Config aliasing — the leak that made bucket colors cross node instances
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


class TestConfigIsolation:
    def test_two_nodes_do_not_share_nested_config(self, qapp):
        from results.results_bar_charts import HistogramPlotNode
        a, b = HistogramPlotNode(), HistogramPlotNode()
        a.config['element_colors']['60Ni'] = '#FF0000'
        assert b.config['element_colors'] == {}

    def test_class_default_never_mutated(self, qapp):
        from results.results_bar_charts import HistogramPlotNode
        node = HistogramPlotNode()
        node.config['element_colors']['60Ni'] = '#FF0000'
        assert HistogramPlotNode.DEFAULT_CONFIG['element_colors'] == {}

    def test_seeding_colors_does_not_leak_across_nodes(self, qapp):
        """The real-world shape of the bug: classifier bucket colors seeded
        into one figure appearing in every other node of that class."""
        from results.results_bar_charts import HistogramPlotNode
        from results.shared_plot_utils import seed_suggested_element_colors
        a, b = HistogramPlotNode(), HistogramPlotNode()
        seed_suggested_element_colors(a.config, {'label_colors': {'S': '#FF0'}})
        assert a.config['element_colors'] == {'S': '#FF0'}
        assert b.config['element_colors'] == {}
        assert HistogramPlotNode.DEFAULT_CONFIG['element_colors'] == {}

    def test_seeding_is_safe_even_on_a_shallow_config(self):
        """Defense in depth: seeding must not write into a caller's shared
        dict even if some future node regresses to dict(DEFAULT_CONFIG)."""
        from results.shared_plot_utils import seed_suggested_element_colors
        shared = {}
        cfg = {'element_colors': shared}
        seed_suggested_element_colors(cfg, {'label_colors': {'S': '#FF0'}})
        assert shared == {}
        assert cfg['element_colors'] == {'S': '#FF0'}


# --------------------------------------------------------------------------- #
# ClassifierViewGroup — real widget, no mocks
# --------------------------------------------------------------------------- #
class TestClassifierViewGroup:
    def test_na_message_on_non_classifier_stream(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        grp = ClassifierViewGroup({}, {'type': 'sample_data'},
                                  cv.ARITY_MULTI_KEY)
        box = grp.build()
        assert box is not None
        assert grp.role_combo is None
        assert grp.collect() == {}

    def test_offers_only_valid_roles(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_MULTI_KEY)
        box = grp.build()  # held: the combo is a child, GC'ing box kills it
        offered = [grp.role_combo.itemData(i)
                   for i in range(grp.role_combo.count())]
        assert box is not None
        assert cv.ROLE_SERIES not in offered
        assert set(offered) == {cv.ROLE_FACET, cv.ROLE_ENCODE, cv.ROLE_OFF}

    def test_collect_returns_flat_scalar_role(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_MULTI_KEY)
        box = grp.build()
        grp.role_combo.setCurrentIndex(grp.role_combo.findData(cv.ROLE_FACET))
        collected = grp.collect()
        assert box is not None
        assert collected == {
            cv.ROLE_CONFIG_KEY: cv.ROLE_FACET,
            cv.SCOPE_CONFIG_KEY: cv.SCOPE_DEFINITION,
        }
        assert isinstance(collected[cv.ROLE_CONFIG_KEY], str)
        assert isinstance(collected[cv.SCOPE_CONFIG_KEY], str)

    def test_preselects_stored_role(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({cv.ROLE_CONFIG_KEY: cv.ROLE_ENCODE}, out,
                                  cv.ARITY_MULTI_KEY)
        box = grp.build()
        assert box is not None
        assert grp.role_combo.currentData() == cv.ROLE_ENCODE

    def test_round_trips_through_config(self, qapp):
        """Pick a role, collect it into config, rebuild — the picker must
        come back showing what was stored (this is what makes it survive a
        project save/load, since config is what gets persisted)."""
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        cfg = {}
        first = ClassifierViewGroup(cfg, out, cv.ARITY_KEY_SET)
        box1 = first.build()
        first.role_combo.setCurrentIndex(
            first.role_combo.findData(cv.ROLE_FACET))
        cfg.update(first.collect())
        assert cfg[cv.ROLE_CONFIG_KEY] == cv.ROLE_FACET

        second = ClassifierViewGroup(cfg, out, cv.ARITY_KEY_SET)
        box2 = second.build()
        assert box1 is not None and box2 is not None
        assert second.role_combo.currentData() == cv.ROLE_FACET


# --------------------------------------------------------------------------- #
# Wired into real per-node settings dialogs, "Configure plot quantities" scope
# --------------------------------------------------------------------------- #
# One representative per arity class, covering both constructor idioms in the
# codebase (input_data threaded straight through the dialog's own __init__,
# vs. threaded via a `node=` reference). Not exhaustive over all 14 wired
# dialogs — that would just be restating the diff — but enough to prove the
# wiring pattern actually works end-to-end through a real Qt dialog, not just
# through ClassifierViewGroup in isolation.
class TestWiredIntoSettingsDialogs:
    def test_heatmap_quantities_offers_all_four_roles(self, qapp):
        """heatmap_plot has its own ARITY_HEATMAP (2026-08-25) -- unlike the
        generic ARITY_KEY_SET nodes (element composition, single/multiple),
        heatmap has a bespoke, safe GROUPS aggregation
        (classifier_view.group_composition_rows) that never degenerates the
        way a naive set-of-keys SERIES collapse would, so SERIES is offered
        here specifically -- see ARITY_HEATMAP's docstring."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='quantities',
                                    input_data=out)
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert set(offered) == {cv.ROLE_SERIES, cv.ROLE_FACET, cv.ROLE_ENCODE, cv.ROLE_OFF}

    def test_heatmap_format_scope_has_no_classifier_group(self, qapp):
        """The picker belongs in quantities only -- format scope must not
        build one at all."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='format',
                                    input_data=out)
        assert dlg._classifier_group is None

    def test_correlation_matrix_offers_all_four_roles(self, qapp):
        """correlation_matrix moved to its own ARITY_MATRIX (2026-08-26).

        It IS a multi-key node, but unlike its former ``ARITY_MULTI_KEY``
        siblings it has a non-degenerate GROUPS mode: a MIXED vocabulary
        where real isotopes and classifier groups share both axes, so an
        isotope x group cell is populated for every matched particle with no
        overlap between definitions needed. The other multi-key nodes still
        must NOT be handed SERIES -- that is the whole reason this got its
        own constant instead of widening the shared one."""
        from results.results_matrix import MatrixSettingsDialog
        out = _wired_node().get_output_data()
        dlg = MatrixSettingsDialog({}, out, scope='quantities')
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert set(offered) == {cv.ROLE_SERIES, cv.ROLE_FACET,
                                cv.ROLE_ENCODE, cv.ROLE_OFF}
        assert cv.ROLE_SERIES not in cv.available_roles(cv.ARITY_MULTI_KEY)

    def test_histogram_quantities_offers_series(self, qapp):
        """histogram_plot is ARITY_PER_KEY -- SERIES (today's behavior) must
        be offered and be the default when no role is stored yet."""
        from results.results_bar_charts import HistogramSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HistogramSettingsDialog({}, False, [], input_data=out)
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES in offered
        assert dlg._classifier_group.role_combo.currentData() == cv.ROLE_SERIES

    def test_element_composition_quantities_offers_key_set_roles(self, qapp):
        from results.results_pie_charts import ElementCompositionSettingsDialog
        out = _wired_node().get_output_data()
        dlg = ElementCompositionSettingsDialog({}, out, [], scope='quantities')
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES not in offered

    def test_na_shown_when_no_classifier_upstream(self, qapp):
        """The N/A requirement, exercised through a real node dialog, not
        just ClassifierViewGroup directly."""
        from results.results_heatmap import HeatmapSettingsDialog
        plain = {'type': 'sample_data', 'selected_isotopes': []}
        dlg = HeatmapSettingsDialog({}, False, [], scope='quantities',
                                    input_data=plain)
        assert dlg._classifier_group.role_combo is None
        assert dlg._classifier_group.collect() == {}

    def test_selected_role_survives_dialog_collect(self, qapp):
        """Picking FACET in the real dialog and calling collect() (exactly
        what OK does) must produce the role key in the returned config."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='quantities',
                                    input_data=out)
        combo = dlg._classifier_group.role_combo
        combo.setCurrentIndex(combo.findData(cv.ROLE_FACET))
        collected = dlg.collect()
        assert collected[cv.ROLE_CONFIG_KEY] == cv.ROLE_FACET

    def test_molar_ratio_quantities_wired(self, qapp):
        """Different constructor idiom (positional input_data, no `scope`
        kwarg default) -- confirms the pattern isn't heatmap-specific."""
        from results.results_molar_ratio import MolarRatioSettingsDialog
        out = _wired_node().get_output_data()
        dlg = MolarRatioSettingsDialog({}, out, [], scope='quantities')
        assert dlg._classifier_group is not None
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES not in offered

    def test_triangle_quantities_wired(self, qapp):
        """Triangle had no input_data plumbing at all before this change --
        confirms the newly-added parameter actually reaches the dialog."""
        from results.results_triangle import TernarySettingsDialog
        out = _wired_node().get_output_data()
        dlg = TernarySettingsDialog({}, [], False, [], scope='quantities',
                                    input_data=out)
        assert dlg._classifier_group is not None
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES not in offered


# --------------------------------------------------------------------------- #
# Role labels (manual-QA-driven rename, 2026-08-24) + per-role disabling
# --------------------------------------------------------------------------- #
class TestRoleLabels:
    """Names/descriptions are user-specified wording -- pin them exactly so a
    future refactor can't silently drift from what was actually asked for."""

    def test_labels_match_manual_qa_wording_exactly(self):
        assert cv.ROLE_LABELS[cv.ROLE_SERIES] == \
            "GROUPS - plot the classifier groups themselves"
        assert cv.ROLE_LABELS[cv.ROLE_FACET] == \
            "PANELS - one subplot per group, plotting isotopic data"
        assert cv.ROLE_LABELS[cv.ROLE_ENCODE] == \
            "COLORS - Isotopic data color-coded by classifier groups"
        assert cv.ROLE_LABELS[cv.ROLE_OFF] == \
            "OFF - Ignore particle classifier groups"


class TestDisabledRoles:
    """``disabled_roles`` is currently unused by any node -- the per-key-
    independent nodes drop PANELS/COLORS at the arity level instead, which is
    a cleaner fit for "this whole class of chart doesn't offer these." The
    mechanism is kept and tested because per-NODE constraints are expected as
    the remaining nodes land (e.g. a node where PANELS is meaningful but
    COLORS isn't), and it's the UI pattern already agreed on for that case:
    keep the option visible with its reason rather than making it vanish."""

    def test_disabled_role_shows_reason_and_is_unselectable(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup(
            {}, out, cv.ARITY_MULTI_KEY,
            disabled_roles={cv.ROLE_FACET: "needs a single-sample stream"})
        box = grp.build()
        assert box is not None
        model = grp.role_combo.model()
        idx = grp.role_combo.findData(cv.ROLE_FACET)
        assert model.item(idx).isEnabled() is False
        assert "needs a single-sample stream" in grp.role_combo.itemText(idx)

    def test_other_roles_stay_enabled(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup(
            {}, out, cv.ARITY_MULTI_KEY,
            disabled_roles={cv.ROLE_FACET: "reason"})
        box = grp.build()
        assert box is not None
        model = grp.role_combo.model()
        for role in (cv.ROLE_ENCODE, cv.ROLE_OFF):
            idx = grp.role_combo.findData(role)
            assert model.item(idx).isEnabled() is True

    def test_stored_disabled_role_falls_back_to_default_on_build(self, qapp):
        """A role saved when it was still usable, now disabled -- must not
        leave a disabled item selected."""
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup(
            {cv.ROLE_CONFIG_KEY: cv.ROLE_FACET}, out, cv.ARITY_MULTI_KEY,
            disabled_roles={cv.ROLE_FACET: "reason"})
        box = grp.build()
        assert box is not None
        assert grp.role_combo.currentData() == cv.default_role(cv.ARITY_MULTI_KEY)

    def test_no_disabled_roles_behaves_as_before(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_MULTI_KEY)
        box = grp.build()
        assert box is not None
        model = grp.role_combo.model()
        for i in range(grp.role_combo.count()):
            assert model.item(i).isEnabled() is True


# --------------------------------------------------------------------------- #
# Histogram: the actual per-node role behavior (GROUPS/OFF/PANELS/COLORS)
# --------------------------------------------------------------------------- #
def _hist_classifier_node():
    """Two buckets, each defined by a DIFFERENT single isotope, so PANELS/
    COLORS output is trivially distinguishable per bucket."""
    from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

    def p(ni, ag):
        e = {}
        if ni:
            e['60Ni'] = ni
        if ag:
            e['107Ag'] = ag
        return {'elements': e, 'source_sample': 'SampleA'}

    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'sample_data', 'sample_name': 'SampleA',
        'particle_data': [p(10, 0), p(10, 0), p(0, 8), p(0, 8)],
        'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'}],
    }
    clf.definitions = [
        {'id': new_definition_id(), 'target_sample': 'SampleA',
         'expression_text': '60Ni', 'match_mode': 'partial',
         'group_name': 'Smelter', 'color': None},
        {'id': new_definition_id(), 'target_sample': 'SampleA',
         'expression_text': '107Ag', 'match_mode': 'partial',
         'group_name': 'Background', 'color': None},
    ]
    clf.groups = {'Smelter': '#FF6600', 'Background': '#3B82F6'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = 'double_count'
    return clf


class TestHistogramRoleBehavior:
    """The bug report this responds to: selecting OFF changed nothing.
    Root cause was that no node read the stored role at all -- extract_plot_data
    always used the classifier's collapsed view regardless of config. These pin
    the fix at the data-extraction layer, not just the picker UI."""

    def test_groups_is_unchanged_from_pre_role_behavior(self, qapp):
        """GROUPS must still read the collapsed bucket-labelled composition --
        this is the zero-behavior-change guarantee dual-carry promised."""
        from results.results_bar_charts import HistogramPlotNode
        out = _hist_classifier_node().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        assert node.classifier_role() == cv.ROLE_SERIES
        data = node.extract_plot_data()
        assert set(data.keys()) == {'Smelter', 'Background'}

    def test_off_reads_real_isotopes_not_buckets(self, qapp):
        """The literal bug: OFF must render as if the classifier weren't
        connected -- real isotope labels, not bucket names."""
        from results.results_bar_charts import HistogramPlotNode
        out = _hist_classifier_node().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = node.extract_plot_data()
        assert set(data.keys()) == {'60Ni', '107Ag'}
        assert 'Smelter' not in data and 'Background' not in data

    def test_panels_colors_not_offered(self, qapp):
        """PANELS/COLORS are deliberately deferred for per-key-independent
        charts (see .claude/aug24.md improvements list) -- they must not be
        selectable, and a stale saved role naming one must fall back rather
        than silently rendering something unintended."""
        from results.results_bar_charts import HistogramPlotNode, HistogramSettingsDialog
        out = _hist_classifier_node().get_output_data()
        dlg = HistogramSettingsDialog({}, False, [], input_data=out)
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert offered == [cv.ROLE_SERIES, cv.ROLE_OFF]

        node = HistogramPlotNode()
        node.process_data(out)
        for stale in (cv.ROLE_FACET, cv.ROLE_ENCODE):
            node.config[cv.ROLE_CONFIG_KEY] = stale
            assert node.classifier_role() == cv.ROLE_SERIES

    def test_dialog_renders_without_crashing_across_all_roles(self, qapp):
        """Real headless Qt dialog, not a mock -- exercises _refresh() end to
        end for every offered role, plus the two deferred ones to prove a
        stale saved config can't crash the render path."""
        from results.results_bar_charts import HistogramPlotNode, HistogramDisplayDialog
        out = _hist_classifier_node().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        dlg = HistogramDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF, cv.ROLE_FACET, cv.ROLE_ENCODE):
            node.config[cv.ROLE_CONFIG_KEY] = role
            dlg._refresh()  # must not raise

    def test_layout_follows_upstream_shape_only(self, qapp):
        """With PANELS/COLORS deferred, no role re-partitions the data, so the
        multi-panel path must key off the upstream stream shape alone."""
        from results.results_bar_charts import HistogramPlotNode, HistogramDisplayDialog
        out = _hist_classifier_node().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        dlg = HistogramDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            node.config[cv.ROLE_CONFIG_KEY] = role
            assert dlg._effective_is_multi() is False
            assert dlg._get_hist_display_mode() == 'single'

    def test_off_updates_available_elements_for_color_pickers(self, qapp):
        """The per-element color/legend picker list must also reflect the
        real isotope vocabulary under OFF, not just the plotted histogram."""
        from results.results_bar_charts import HistogramPlotNode, HistogramDisplayDialog
        out = _hist_classifier_node().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        dlg = HistogramDisplayDialog(node, None)
        assert set(dlg._get_available_elements()) == {'Smelter', 'Background'}
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        assert set(dlg._get_available_elements()) == {'60Ni', '107Ag'}


# --------------------------------------------------------------------------- #
# classifier_view: overlap-mode awareness + mass-aware sorting
# --------------------------------------------------------------------------- #
class TestOverlapModeAwareness:
    def test_overlap_mode_exposed_on_classifier_output(self, qapp):
        out = _hist_classifier_node().get_output_data()
        assert cv.overlap_mode(out) == 'double_count'
        assert cv.is_double_count(out) is True

    def test_priority_mode_not_double_count(self, qapp):
        node = _hist_classifier_node()
        node.overlap_mode = 'priority'
        out = node.get_output_data()
        assert cv.overlap_mode(out) == 'priority'
        assert cv.is_double_count(out) is False

    def test_none_for_non_classifier_stream(self):
        assert cv.overlap_mode({'type': 'sample_data'}) is None
        assert cv.is_double_count({'type': 'sample_data'}) is False
        assert cv.overlap_mode(None) is None


class TestMassSortKey:
    """See classifier_view.mass_sort_key's docstring: a classifier bucket
    label has no parseable mass of its own, so it must sort by the mean mass
    of the real isotopes matched within its particles, not tie at the
    'unparseable' fallback every bucket would otherwise share."""

    def _two_group_node(self):
        """'Alpha' backed by heavy 197Au, 'Zulu' backed by light 60Ni --
        alphabetical and mass order disagree, so any test that passes here
        is actually exercising mass, not coincidentally matching another
        ordering."""
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

        def p(iso):
            return {'elements': {iso: 5}, 'source_sample': 'A'}

        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'sample_data', 'sample_name': 'A',
            'particle_data': [p('197Au')] * 4 + [p('60Ni')] * 4,
            'selected_isotopes': [{'label': '60Ni'}, {'label': '197Au'}],
        }
        clf.definitions = [
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '197Au', 'match_mode': 'partial',
             'group_name': 'Alpha', 'color': None},
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '60Ni', 'match_mode': 'partial',
             'group_name': 'Zulu', 'color': None},
        ]
        clf.groups = {'Alpha': '#FF0000', 'Zulu': '#00FF00'}
        clf.unmatched_mode = 'discard'
        clf.overlap_mode = 'double_count'
        return clf

    def test_bucket_sorts_by_mean_matched_isotope_mass(self, qapp):
        out = self._two_group_node().get_output_data()
        assert cv.mass_sort_key(out, 'Alpha') == 197.0
        assert cv.mass_sort_key(out, 'Zulu') == 60.0

    def test_sort_labels_disagrees_with_alphabetical_on_purpose(self, qapp):
        """The whole point of the fixture: alphabetical says Alpha first,
        mass says Zulu first. If this ever returns ['Alpha', 'Zulu'] the
        sort silently fell back to alphabetical/insertion order again."""
        out = self._two_group_node().get_output_data()
        assert cv.sort_labels_by_mass(out, ['Alpha', 'Zulu']) == ['Zulu', 'Alpha']

    def test_multi_isotope_group_averages(self, qapp):
        """A group matching two isotopes across its particles sorts by
        their mean, not just one of them."""
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

        def p(ni=0, ag=0):
            e = {}
            if ni:
                e['60Ni'] = ni
            if ag:
                e['107Ag'] = ag
            return {'elements': e, 'source_sample': 'A'}

        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'sample_data', 'sample_name': 'A',
            'particle_data': [p(ni=5), p(ag=5)],
            'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'}],
        }
        clf.definitions = [
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '[60Ni,107Ag]', 'match_mode': 'partial',
             'group_name': 'Mixed', 'color': None},
        ]
        clf.groups = {'Mixed': '#3B82F6'}
        clf.unmatched_mode = 'discard'
        clf.overlap_mode = 'double_count'
        out = clf.get_output_data()
        assert cv.mass_sort_key(out, 'Mixed') == pytest.approx((60 + 107) / 2)

    def test_real_isotope_label_falls_through_to_own_mass(self, qapp):
        """A label that isn't a registered bucket (e.g. a real isotope under
        OFF, or a passthrough particle's own key) must sort by its own
        parsed mass, identically to sort_elements_by_mass -- not get treated
        as an unknown bucket."""
        out = self._two_group_node().get_output_data()
        assert cv.mass_sort_key(out, '107Ag') == 107.0

    def test_unclassified_bucket_with_no_isotopes_does_not_crash(self, qapp):
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id
        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'sample_data', 'sample_name': 'A',
            'particle_data': [], 'selected_isotopes': [],
        }
        clf.definitions = [
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '60Ni', 'match_mode': 'partial',
             'group_name': None, 'color': None},
        ]
        clf.groups = {}
        clf.unmatched_mode = 'unclassified'
        clf.overlap_mode = 'double_count'
        out = clf.get_output_data()
        assert cv.mass_sort_key(out, 'Unclassified') == 999.0

    def test_identical_result_to_plain_sorter_on_non_classifier_data(self):
        """No regression for the common case: no classifier upstream at all."""
        from results.utils_sort import sort_elements_by_mass
        labels = ['107Ag', '60Ni', '197Au']
        assert cv.sort_labels_by_mass(None, labels) == sort_elements_by_mass(labels)
        assert cv.sort_labels_by_mass({'type': 'sample_data'}, labels) == \
            sort_elements_by_mass(labels)


# --------------------------------------------------------------------------- #
# element_bar_chart_plot: GROUPS/OFF + double-count note + mass-aware sort
# --------------------------------------------------------------------------- #
def _ebc_classifier_node(overlap_mode='double_count'):
    """Mirrors _hist_classifier_node but for element bar chart's shape
    (counts, not value lists) -- two buckets, each a single distinct
    isotope, plus a third real isotope that stays unclassified."""
    from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

    def p(ni=0, ag=0, au=0):
        e = {}
        if ni:
            e['60Ni'] = ni
        if ag:
            e['107Ag'] = ag
        if au:
            e['197Au'] = au
        return {'elements': e, 'source_sample': 'A'}

    particles = ([p(ni=10) for _ in range(5)]
                 + [p(ag=8) for _ in range(3)]
                 + [p(au=7) for _ in range(2)])

    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'sample_data', 'sample_name': 'A', 'particle_data': particles,
        'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'},
                              {'label': '197Au'}],
    }
    clf.definitions = [
        {'id': new_definition_id(), 'target_sample': 'A',
         'expression_text': '60Ni', 'match_mode': 'partial',
         'group_name': 'Smelter', 'color': None},
        {'id': new_definition_id(), 'target_sample': 'A',
         'expression_text': '107Ag', 'match_mode': 'partial',
         'group_name': 'Background', 'color': None},
    ]
    clf.groups = {'Smelter': '#FF6600', 'Background': '#3B82F6'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = overlap_mode
    return clf


class TestElementBarChartRoleBehavior:
    def test_groups_is_unchanged_from_pre_role_behavior(self, qapp):
        from results.results_bar_charts import ElementBarChartPlotNode
        out = _ebc_classifier_node().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        assert node.classifier_role() == cv.ROLE_SERIES
        data = node.extract_plot_data()
        assert data == {'Smelter': 5, 'Background': 3, 'Unclassified': 2}

    def test_off_counts_real_isotopes_not_buckets(self, qapp):
        """The same bug class as histogram's OFF, fixed the same way."""
        from results.results_bar_charts import ElementBarChartPlotNode
        out = _ebc_classifier_node().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = node.extract_plot_data()
        assert data == {'60Ni': 5, '107Ag': 3, '197Au': 2}
        assert 'Smelter' not in data

    def test_panels_colors_not_offered(self, qapp):
        from results.results_bar_charts import BarChartSettingsDialog
        out = _ebc_classifier_node().get_output_data()
        dlg = BarChartSettingsDialog({}, False, [], input_data=out)
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert offered == [cv.ROLE_SERIES, cv.ROLE_OFF]

    def test_available_bar_elements_follows_role(self, qapp):
        from results.results_bar_charts import ElementBarChartPlotNode, ElementBarChartDisplayDialog
        out = _ebc_classifier_node().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        dlg = ElementBarChartDisplayDialog(node, None)
        assert set(dlg._get_available_bar_elements()) == \
            {'Smelter', 'Background', 'Unclassified'}
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        assert set(dlg._get_available_bar_elements()) == {'60Ni', '107Ag', '197Au'}

    def test_dialog_renders_without_crashing(self, qapp):
        from results.results_bar_charts import ElementBarChartPlotNode, ElementBarChartDisplayDialog
        out = _ebc_classifier_node().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        dlg = ElementBarChartDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            node.config[cv.ROLE_CONFIG_KEY] = role
            dlg._refresh()  # must not raise

    def test_double_count_note_shown_when_applicable(self, qapp):
        from PySide6.QtWidgets import QLabel
        from results.results_bar_charts import BarChartSettingsDialog
        out = _ebc_classifier_node(overlap_mode='double_count').get_output_data()
        dlg = BarChartSettingsDialog({}, False, [], input_data=out)
        found = any('double count' in child.text().lower()
                    for child in dlg.findChildren(QLabel))
        assert found

    def test_double_count_note_absent_for_priority_mode(self, qapp):
        from PySide6.QtWidgets import QLabel
        from results.results_bar_charts import BarChartSettingsDialog
        out = _ebc_classifier_node(overlap_mode='priority').get_output_data()
        dlg = BarChartSettingsDialog({}, False, [], input_data=out)
        found = any('double count' in child.text().lower()
                    for child in dlg.findChildren(QLabel))
        assert not found

    def test_mass_aware_bar_order(self, qapp):
        """End-to-end: the dropdown/bar order for a classifier stream must
        come from sort_labels_by_mass, not the plain isotope-only sorter --
        proven with a fixture where the two orderings disagree."""
        from results.results_bar_charts import ElementBarChartPlotNode, ElementBarChartDisplayDialog
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

        def p(iso):
            return {'elements': {iso: 5}, 'source_sample': 'A'}

        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'sample_data', 'sample_name': 'A',
            'particle_data': [p('197Au')] * 4 + [p('60Ni')] * 4,
            'selected_isotopes': [{'label': '60Ni'}, {'label': '197Au'}],
        }
        clf.definitions = [
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '197Au', 'match_mode': 'partial',
             'group_name': 'Alpha', 'color': None},
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '60Ni', 'match_mode': 'partial',
             'group_name': 'Zulu', 'color': None},
        ]
        clf.groups = {'Alpha': '#FF0000', 'Zulu': '#00FF00'}
        clf.unmatched_mode = 'discard'
        clf.overlap_mode = 'double_count'
        out = clf.get_output_data()

        node = ElementBarChartPlotNode()
        node.process_data(out)
        dlg = ElementBarChartDisplayDialog(node, None)
        assert dlg._get_available_bar_elements() == ['Zulu', 'Alpha']


def _ebc_multi_sample_classifier_node(overlap_mode='priority'):
    """Two-sample classifier stream for By Sample (Element Colors) mode.

    Per-element totals across both samples clear the default
    ``min_particle_count`` (10) threshold on purpose, so every legend row
    that should render actually does."""
    from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

    def p(sample, ni=0, ag=0, au=0):
        e = {}
        if ni:
            e['60Ni'] = ni
        if ag:
            e['107Ag'] = ag
        if au:
            e['197Au'] = au
        return {'elements': e, 'source_sample': sample}

    particles = (
        [p('A', ni=10) for _ in range(15)]
        + [p('A', ag=8) for _ in range(12)]
        + [p('B', ni=10) for _ in range(14)]
        + [p('B', au=7) for _ in range(11)]
    )

    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
        'particle_data': particles,
        'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'},
                              {'label': '197Au'}],
    }
    defs = []
    for s in ('A', 'B'):
        defs.append({'id': new_definition_id(), 'target_sample': s,
                      'expression_text': '60Ni', 'match_mode': 'partial',
                      'group_name': 'Smelter', 'color': None})
        defs.append({'id': new_definition_id(), 'target_sample': s,
                      'expression_text': '107Ag', 'match_mode': 'partial',
                      'group_name': 'Background', 'color': None})
    clf.definitions = defs
    clf.groups = {'Smelter': '#FF6600', 'Background': '#3B82F6'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = overlap_mode
    return clf


class TestBySampleLegendElementVisibility:
    """Regression coverage for a legend-click-to-hide bug reported live:
    in Element Bar Chart's 'By Sample (Element Colors)' mode (multi-sample
    input, x-axis = samples, legend = elements), clicking a legend swatch
    built no interactive object at all -- the click silently did nothing,
    for both GROUPS and OFF roles. Root cause: _draw_by_sample built plain
    pg.BarGraphItem legend swatches instead of _ClickableLegendSwatch, and
    never called _attach_bar_chart_legend_toggle -- unlike the Grouped/
    Stacked sample-legend path, which already had this wiring for samples."""

    def _dialog_for(self, role, overlap_mode='priority'):
        from results.results_bar_charts import ElementBarChartPlotNode, ElementBarChartDisplayDialog
        out = _ebc_multi_sample_classifier_node(overlap_mode).get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = role
        node.config['display_mode'] = 'By Sample (Element Colors)'
        return ElementBarChartDisplayDialog(node, None), node

    def _legend_of(self, dlg):
        import pyqtgraph as pg
        pi = next(item for item in dlg.pw.scene().items()
                  if isinstance(item, pg.PlotItem))
        return pi, getattr(pi, 'legend', None)

    def test_groups_legend_click_hides_element(self, qapp):
        from PySide6.QtCore import Qt
        from results.results_bar_charts import _get_legend_sample_graphics_item

        dlg, node = self._dialog_for(cv.ROLE_SERIES)
        assert node.classifier_role() == cv.ROLE_SERIES
        _pi, legend = self._legend_of(dlg)
        assert legend is not None and len(legend.items) == 3

        sample_item, _label = legend.items[0]
        swatch = _get_legend_sample_graphics_item(sample_item)
        raw_key = getattr(swatch, '_raw_key', None)
        assert raw_key, "legend swatch has no raw key bound -- click does nothing"

        class _Ev:
            def button(self):
                return Qt.LeftButton
            def accept(self):
                pass

        assert raw_key not in dlg._hidden_bar_elements
        swatch.mouseClickEvent(_Ev())
        assert raw_key in dlg._hidden_bar_elements

        swatch.mouseClickEvent(_Ev())
        assert raw_key not in dlg._hidden_bar_elements
        dlg.close()

    def test_off_legend_click_hides_element(self, qapp):
        """Same bug, same fix, verified for OFF (real isotopes) too."""
        from PySide6.QtCore import Qt
        from results.results_bar_charts import _get_legend_sample_graphics_item

        dlg, node = self._dialog_for(cv.ROLE_OFF)
        assert node.classifier_role() == cv.ROLE_OFF
        _pi, legend = self._legend_of(dlg)
        assert legend is not None and len(legend.items) == 3

        sample_item, _label = legend.items[0]
        swatch = _get_legend_sample_graphics_item(sample_item)
        raw_key = getattr(swatch, '_raw_key', None)
        assert raw_key

        class _Ev:
            def button(self):
                return Qt.LeftButton
            def accept(self):
                pass

        swatch.mouseClickEvent(_Ev())
        assert raw_key in dlg._hidden_bar_elements
        dlg.close()

    def test_hiding_all_elements_shows_empty_state_message(self, qapp):
        dlg, node = self._dialog_for(cv.ROLE_SERIES)
        _pi, legend = self._legend_of(dlg)
        for row in list(legend.items):
            sample_item, _label = row
            from results.results_bar_charts import _get_legend_sample_graphics_item
            raw_key = getattr(_get_legend_sample_graphics_item(sample_item), '_raw_key', None)
            dlg._toggle_bar_element_visibility(raw_key)

        import pyqtgraph as pg
        pi, _legend = self._legend_of(dlg)
        texts = [it.toPlainText() for it in pi.items
                if isinstance(it, pg.TextItem) and hasattr(it, 'toPlainText')]
        assert any('No visible elements' in t for t in texts)
        dlg.close()

    def test_hidden_state_isolated_per_dialog(self, qapp):
        """Hiding an element in one dialog instance must not leak into a
        freshly constructed one for the same node."""
        from results.results_bar_charts import ElementBarChartDisplayDialog
        dlg1, node = self._dialog_for(cv.ROLE_SERIES)
        dlg1._toggle_bar_element_visibility('Smelter')
        assert 'Smelter' in dlg1._hidden_bar_elements

        dlg2 = ElementBarChartDisplayDialog(node, None)
        assert dlg2._hidden_bar_elements == set()
        dlg1.close()
        dlg2.close()

    def test_csv_export_respects_hidden_elements_in_by_sample_mode(self, qapp):
        import pandas as pd
        dlg, node = self._dialog_for(cv.ROLE_SERIES)
        dlg._toggle_bar_element_visibility('Smelter')

        captured = {}

        def _fake_download(pw, parent, default_name=None, csv_data=None):
            captured['csv_data'] = csv_data

        import results.results_bar_charts as rbc
        orig = rbc.download_pyqtgraph_figure
        rbc.download_pyqtgraph_figure = _fake_download
        try:
            dlg._download_figure()
        finally:
            rbc.download_pyqtgraph_figure = orig

        df = captured['csv_data']
        assert df is not None
        assert 'Smelter' not in set(df['Element'])
        assert {'Background', 'Unclassified'}.issubset(set(df['Element']))
        dlg.close()

    def test_grouped_bars_csv_hidden_sample_mode_string_matches(self, qapp):
        """The mode-string comparison must match BAR_DISPLAY_MODES exactly
        ('Grouped Bars (Side by Side)', not the truncated 'Grouped Bars'),
        otherwise hidden-sample CSV filtering silently never applies in the
        default display mode."""
        from results.results_bar_charts import ElementBarChartPlotNode, ElementBarChartDisplayDialog
        out = _ebc_multi_sample_classifier_node().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        node.config['display_mode'] = 'Grouped Bars (Side by Side)'
        dlg = ElementBarChartDisplayDialog(node, None)
        dlg._toggle_bar_sample_visibility('A')

        captured = {}

        def _fake_download(pw, parent, default_name=None, csv_data=None):
            captured['csv_data'] = csv_data

        import results.results_bar_charts as rbc
        orig = rbc.download_pyqtgraph_figure
        rbc.download_pyqtgraph_figure = _fake_download
        try:
            dlg._download_figure()
        finally:
            rbc.download_pyqtgraph_figure = orig

        df = captured['csv_data']
        assert df is not None
        assert 'A' not in set(df['Sample'])


# --------------------------------------------------------------------------- #
# box_plot: GROUPS/OFF across all 7 data types + subplot-mode identity
# --------------------------------------------------------------------------- #
_BOX_BUCKET_LABELS = {'Smelter', 'Background', 'Unclassified'}
_BOX_ISOTOPE_LABELS = {'60Ni', '107Ag', '197Au'}


def _box_particle(sample, ni=None, ag=None, au=None):
    """One particle with per-isotope entries for every box-plot data type
    (elements/mass/moles x element-or-particle, plus both diameter keys).
    Only 'elements' + the additive/percentage/MFC keys get bucket-collapsed
    by the classifier; the diameter keys never do (see
    tools/particle_classifier_relabel.py's module docstring)."""
    part = {'elements': {}, 'element_mass_fg': {}, 'element_moles_fmol': {},
            'particle_mass_fg': {}, 'particle_moles_fmol': {},
            'element_diameter_nm': {}, 'particle_diameter_nm': {},
            'source_sample': sample}
    for iso, val in (('60Ni', ni), ('107Ag', ag), ('197Au', au)):
        if val is not None:
            part['elements'][iso] = 1
            part['element_mass_fg'][iso] = val * 10
            part['element_moles_fmol'][iso] = val
            part['particle_mass_fg'][iso] = val * 20
            part['particle_moles_fmol'][iso] = val * 2
            part['element_diameter_nm'][iso] = val + 100
            part['particle_diameter_nm'][iso] = val + 200
    return part


def _box_classifier_node(overlap_mode='priority', unmatched_mode='unclassified'):
    """Two-sample classifier stream: sample A has Smelter(60Ni)+Background
    (107Ag) particles, sample B has Smelter(60Ni)+unmatched(197Au) --
    per-element totals comfortably clear box plot's default
    min_particle_count of 0."""
    from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

    particles = (
        [_box_particle('A', ni=5) for _ in range(6)]
        + [_box_particle('A', ag=8) for _ in range(4)]
        + [_box_particle('B', ni=5) for _ in range(5)]
        + [_box_particle('B', au=3) for _ in range(3)]
    )
    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
        'particle_data': particles,
        'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'},
                              {'label': '197Au'}],
    }
    defs = []
    for s in ('A', 'B'):
        defs.append({'id': new_definition_id(), 'target_sample': s,
                      'expression_text': '60Ni', 'match_mode': 'partial',
                      'group_name': 'Smelter', 'color': None})
        defs.append({'id': new_definition_id(), 'target_sample': s,
                      'expression_text': '107Ag', 'match_mode': 'partial',
                      'group_name': 'Background', 'color': None})
    clf.definitions = defs
    clf.groups = {'Smelter': '#FF6600', 'Background': '#3B82F6'}
    clf.unmatched_mode = unmatched_mode
    clf.overlap_mode = overlap_mode
    return clf


class TestBoxPlotRoleBehavior:
    """Regression coverage for a bug reported live: box plot's role picker
    UI existed (ClassifierViewGroup was already wired into its settings
    dialog) but nothing downstream ever read it. OFF was a total no-op, and
    worse, behavior secretly depended on which data type was selected: the
    additive keys (elements/mass/moles) are destructively bucket-collapsed
    by the classifier itself, so they always showed groups; the diameter
    keys are deliberately never touched by the classifier, so they always
    showed real isotopes -- regardless of which role was picked, for every
    data type."""

    def test_groups_is_unchanged_from_pre_role_behavior(self, qapp):
        from results.results_box_plot import BoxPlotNode
        out = _box_classifier_node().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        assert node.classifier_role() == cv.ROLE_SERIES
        data = node.extract_plot_data()
        labels = set()
        for sd in data.values():
            labels.update(sd.keys())
        assert labels <= _BOX_BUCKET_LABELS
        assert data['A']['Smelter'] == [1, 1, 1, 1, 1, 1]

    def test_off_counts_real_isotopes_not_buckets(self, qapp):
        from results.results_box_plot import BoxPlotNode
        out = _box_classifier_node().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = node.extract_plot_data()
        labels = set()
        for sd in data.values():
            labels.update(sd.keys())
        assert labels == _BOX_ISOTOPE_LABELS
        assert 'Smelter' not in labels

    @pytest.mark.parametrize('display_name', [
        'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
        'Element Moles (fmol)', 'Particle Moles (fmol)',
        'Element Diameter (nm)', 'Particle Diameter (nm)',
    ])
    def test_all_data_types_respect_role(self, qapp, display_name):
        """The exact bug: OFF did nothing (additive keys always collapsed),
        AND diameter never respected GROUPS (never collapsed by the
        classifier at all) -- for every one of the 7 data types."""
        from results.results_box_plot import BoxPlotNode
        out = _box_classifier_node().get_output_data()

        node = BoxPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = display_name
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        groups_data = node.extract_plot_data()
        groups_labels = set()
        for sd in (groups_data or {}).values():
            groups_labels.update(sd.keys())
        assert groups_labels, f"{display_name}: GROUPS produced nothing"
        assert groups_labels <= _BOX_BUCKET_LABELS, \
            f"{display_name}: GROUPS leaked real isotope labels {groups_labels}"

        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        off_data = node.extract_plot_data()
        off_labels = set()
        for sd in (off_data or {}).values():
            off_labels.update(sd.keys())
        assert off_labels, f"{display_name}: OFF produced nothing"
        assert off_labels == _BOX_ISOTOPE_LABELS, \
            f"{display_name}: OFF did not switch to real isotopes ({off_labels})"

    def test_diameter_groups_by_bucket_under_groups_role(self, qapp):
        """The specific complaint: 'element diameter becomes all isotopes'
        no matter the role, because the classifier never bucket-collapses
        diameter fields. GROUPS must now re-key each isotope's diameter
        under its particle's bucket instead."""
        from results.results_box_plot import BoxPlotNode
        out = _box_classifier_node().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Diameter (nm)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = node.extract_plot_data()
        assert set(data['A'].keys()) <= _BOX_BUCKET_LABELS
        assert data['A']['Smelter'] == [105, 105, 105, 105, 105, 105]

    def test_mass_respects_off_role(self, qapp):
        """The specific complaint: 'element mass just stays in the group'
        no matter the role, because the classifier destructively relabels
        elements/mass/moles. OFF must now read the dual-carried raw
        composition instead of the already-collapsed particle dict."""
        from results.results_box_plot import BoxPlotNode
        out = _box_classifier_node().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = node.extract_plot_data()
        assert set(data['A'].keys()) == {'60Ni', '107Ag'}
        assert data['A']['60Ni'] == [50, 50, 50, 50, 50, 50]

    def test_passthrough_particle_falls_back_to_isotope_label(self, qapp):
        """A particle with no bucket assigned (passthrough, unmatched) has
        nothing to group diameter values by, so GROUPS must fall back to
        its own real isotope label rather than dropping the data."""
        from results.results_box_plot import BoxPlotNode
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id
        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'sample_data', 'sample_name': 'A',
            'particle_data': [_box_particle('A', au=9)],
            'selected_isotopes': [{'label': '197Au'}],
        }
        clf.definitions = [
            {'id': new_definition_id(), 'target_sample': 'A',
             'expression_text': '60Ni', 'match_mode': 'partial',
             'group_name': 'Smelter', 'color': None},
        ]
        clf.groups = {'Smelter': '#FF6600'}
        clf.unmatched_mode = 'passthrough'
        clf.overlap_mode = 'priority'
        out = clf.get_output_data()

        node = BoxPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Diameter (nm)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = node.extract_plot_data()
        assert data == {'197Au': [109]}

    def test_panels_colors_not_offered(self, qapp):
        from results.results_box_plot import BoxPlotSettingsDialog
        out = _box_classifier_node().get_output_data()
        dlg = BoxPlotSettingsDialog({}, out, None, scope='quantities')
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert offered == [cv.ROLE_SERIES, cv.ROLE_OFF]

    def test_dialog_renders_without_crashing(self, qapp):
        from results.results_box_plot import BoxPlotNode, BoxPlotDisplayDialog
        out = _box_classifier_node().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        dlg = BoxPlotDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            node.config[cv.ROLE_CONFIG_KEY] = role
            dlg._refresh()  # must not raise
        dlg.close()


class TestBoxPlotSubplotModes:
    """Multi-sample display-mode coverage: both 'Subplots by sample' and
    'Subplots by isotope' read the same role-aware plot_data, so panel/box
    identity should follow the role automatically with no per-mode special
    casing -- plus the 'Export this subplot' fix (previously wired only
    for 'Subplots by isotope')."""

    def _dialog_for(self, role, mode, overlap_mode='priority'):
        from results.results_box_plot import BoxPlotNode, BoxPlotDisplayDialog
        out = _box_classifier_node(overlap_mode).get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = role
        node.config['display_mode'] = mode
        return BoxPlotDisplayDialog(node, None), node

    def test_subplots_by_sample_panel_identity_is_sample_both_roles(self, qapp):
        import pyqtgraph as pg
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            dlg, _node = self._dialog_for(role, 'Subplots by sample')
            panels = [item for item in dlg.pw.scene().items()
                      if isinstance(item, pg.PlotItem)]
            assert len(panels) == 2, f"[{role}] expected 2 sample panels"
            sample_ids = {c.get('sample') for c in
                          dlg._subplot_context_by_plotitem.values()}
            assert sample_ids == {'A', 'B'}, f"[{role}] {sample_ids}"
            dlg.close()

    def test_subplots_by_isotope_panel_identity_is_role_dependent(self, qapp):
        import pyqtgraph as pg
        dlg, _node = self._dialog_for(cv.ROLE_SERIES, 'Subplots by isotope')
        panel_ids = {c.get('element') for c in
                     dlg._subplot_context_by_plotitem.values()}
        assert panel_ids <= _BOX_BUCKET_LABELS
        dlg.close()

        dlg2, _node2 = self._dialog_for(cv.ROLE_OFF, 'Subplots by isotope')
        panel_ids2 = {c.get('element') for c in
                      dlg2._subplot_context_by_plotitem.values()}
        assert panel_ids2 == _BOX_ISOTOPE_LABELS
        dlg2.close()

    def test_bucket_panels_sort_by_mass_not_alphabetically(self, qapp):
        """Adversarial fixture where alphabetical and mass order disagree,
        proving the panel order comes from sort_labels_by_mass and isn't
        coincidentally alphabetical."""
        from results.results_box_plot import BoxPlotNode, BoxPlotDisplayDialog
        from tools.particle_classifier_node import ParticleClassifierNode, new_definition_id

        def p(iso, sample='A'):
            return {'elements': {iso: 1}, 'source_sample': sample}

        particles = (
            [p('197Au')] * 4 + [p('60Ni')] * 4
            + [p('197Au', 'B')] * 4 + [p('60Ni', 'B')] * 4
        )
        clf = ParticleClassifierNode()
        clf.input_data = {
            'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
            'particle_data': particles,
            'selected_isotopes': [{'label': '60Ni'}, {'label': '197Au'}],
        }
        defs = []
        for s in ('A', 'B'):
            defs.append({'id': new_definition_id(), 'target_sample': s,
                          'expression_text': '197Au', 'match_mode': 'partial',
                          'group_name': 'Alpha', 'color': None})
            defs.append({'id': new_definition_id(), 'target_sample': s,
                          'expression_text': '60Ni', 'match_mode': 'partial',
                          'group_name': 'Zulu', 'color': None})
        clf.definitions = defs
        clf.groups = {'Alpha': '#FF0000', 'Zulu': '#00FF00'}
        clf.unmatched_mode = 'discard'
        clf.overlap_mode = 'priority'
        out = clf.get_output_data()

        node = BoxPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        node.config['display_mode'] = 'Subplots by isotope'
        dlg = BoxPlotDisplayDialog(node, None)
        dlg._refresh()
        panel_order = [c.get('element') for c in
                       dlg._subplot_context_by_plotitem.values()]
        assert panel_order == ['Zulu', 'Alpha'], panel_order
        dlg.close()

    def test_export_subplot_enabled_for_both_multi_sample_modes(self, qapp):
        import pyqtgraph as pg
        from results.results_box_plot import _normalize_box_display_mode
        for mode in ('Subplots by isotope', 'Subplots by sample'):
            dlg, node = self._dialog_for(cv.ROLE_SERIES, mode)
            plot_item = next(item for item in dlg.pw.scene().items()
                             if isinstance(item, pg.PlotItem))
            subplot_ctx = dlg._subplot_context_by_plotitem.get(plot_item)
            assert subplot_ctx is not None, f"[{mode}] no subplot context"

            display_mode = _normalize_box_display_mode(node.config.get('display_mode'))
            can_export = (
                display_mode in ('Subplots by isotope', 'Subplots by sample')
                and plot_item is not None and subplot_ctx is not None
            )
            assert can_export, f"[{mode}] export-subplot still disabled"
            dlg.close()

    def test_export_subplot_filename_stems_differ_by_mode(self, qapp):
        import pyqtgraph as pg
        import results.results_box_plot as rbp
        for mode, expected_suffix in (('Subplots by isotope', '_by_sample'),
                                       ('Subplots by sample', '_by_element')):
            dlg, _node = self._dialog_for(cv.ROLE_SERIES, mode)
            plot_item = next(item for item in dlg.pw.scene().items()
                             if isinstance(item, pg.PlotItem))
            subplot_ctx = dlg._subplot_context_by_plotitem.get(plot_item)

            captured = {}
            def _fake_download(pw, parent, default_name=None, export_item=None):
                captured['name'] = default_name
            orig = rbp.download_pyqtgraph_figure
            rbp.download_pyqtgraph_figure = _fake_download
            try:
                dlg._export_subplot(plot_item, subplot_ctx)
            finally:
                rbp.download_pyqtgraph_figure = orig

            assert captured['name'].endswith(expected_suffix), \
                f"[{mode}] {captured['name']!r}"
            dlg.close()


# --------------------------------------------------------------------------- #
# Aggregation scope: BY DEFINITION vs TOTAL PARTICLE -- found live 2026-08-25
# from a mean-above-the-whisker box-plot reading that turned out to be a real,
# correct number, not a bug: a matched bucket's value has always counted only
# the isotopes its triggering expression names, silently dropping every other
# isotope a qualifying particle also carries. See aug24.md.
# --------------------------------------------------------------------------- #
class TestMatchIsotopesKeyDualCarry:
    """Pure relabel-level: MATCH_ISOTOPES_KEY records exactly the isotope
    set each output copy's own BY-DEFINITION collapse used, so a later
    reader can recover it once the collapse is just a single number with
    no memory of its own inputs."""

    def test_matched_particle_carries_its_own_definition_isotopes(self):
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6, '63Cu': 4})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        assert out[0][pcr.MATCH_ISOTOPES_KEY] == {'60Ni'}

    def test_unclassified_carries_every_isotope_the_particle_has(self):
        """No expression to scope by -- MATCH_ISOTOPES_KEY is the full set,
        the same thing TOTAL PARTICLE would also compute (see
        TestCompositionItemsForRoleScope.test_unclassified_is_scope_invariant)."""
        out = _relabel([_particle({'56Fe': 6, '63Cu': 4})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        assert out[0][pcr.BUCKET_KEY] == 'Unclassified'
        assert out[0][pcr.MATCH_ISOTOPES_KEY] == {'56Fe', '63Cu'}

    def test_passthrough_carries_no_match_isotopes_key(self):
        out = _relabel([_particle({'56Fe': 6})], [_def('60Ni', group='Smelter')],
                       overlap='priority', unmatched='passthrough')
        assert out[0][pcr.BUCKET_KEY] is None
        assert pcr.MATCH_ISOTOPES_KEY not in out[0]

    def test_double_count_each_copy_keeps_its_own_definition_isotopes(self):
        """Each copy stores the isotopes of the ONE definition it
        represents, not the union across all matched definitions -- see
        TestCompositionItemsForRoleScope's double_count test for why this
        still gives each copy the WHOLE particle under TOTAL PARTICLE."""
        out = _relabel(
            [_particle({'60Ni': 10, '107Ag': 8, '63Cu': 4})],
            [_def('60Ni', group='Smelter'), _def('107Ag', group='Background')],
            overlap='double_count')
        assert len(out) == 2
        by_label = {c[pcr.BUCKET_KEY]: c for c in out}
        assert by_label['Smelter'][pcr.MATCH_ISOTOPES_KEY] == {'60Ni'}
        assert by_label['Background'][pcr.MATCH_ISOTOPES_KEY] == {'107Ag'}


class TestCompositionItemsForRoleScope:
    """classifier_view.composition_items_for_role's scope parameter."""

    def test_default_scope_is_definition(self):
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        assert cv.composition_items_for_role(p, 'elements', cv.ROLE_SERIES) == \
            cv.composition_items_for_role(
                p, 'elements', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)

    def test_scope_definition_matches_historical_collapse_bit_for_bit(self):
        """The whole point: SCOPE_DEFINITION must be indistinguishable from
        every node's behavior before this feature existed."""
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        assert cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_DEFINITION) == \
            list(p['element_mass_fg'].items()) == [('Smelter', 1.0)]

    def test_scope_total_particle_sums_every_isotope(self):
        """element_mass_fg = 0.1 * elements per _particle()'s construction:
        60Ni -> 1.0, 56Fe -> 0.6, total = 1.6 -- Fe now counts even though
        the Smelter expression only names 60Ni."""
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        assert cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE) == \
            [('Smelter', pytest.approx(1.6))]

    def test_off_role_ignores_scope_entirely(self):
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        off_def = cv.composition_items_for_role(
            p, 'elements', cv.ROLE_OFF, cv.SCOPE_DEFINITION)
        off_total = cv.composition_items_for_role(
            p, 'elements', cv.ROLE_OFF, cv.SCOPE_TOTAL_PARTICLE)
        assert off_def == off_total
        assert set(off_def) == {('60Ni', 10), ('56Fe', 6)}

    def test_diameter_scope_definition_keeps_only_matched_isotopes(self):
        """Diameter is never bucket-collapsed by the classifier at all (no
        principled way to sum a diameter), so SCOPE_DEFINITION here means
        something different than for additive keys: which of the
        particle's own per-isotope diameter entries survive, not what gets
        summed."""
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        items = cv.composition_items_for_role(
            p, 'element_diameter_nm', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        assert items == [('Smelter', 42.0)]

    def test_diameter_scope_total_particle_keeps_every_isotope(self):
        out = _relabel([_particle({'60Ni': 10, '56Fe': 6})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        items = cv.composition_items_for_role(
            p, 'element_diameter_nm', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert sorted(items) == sorted([('Smelter', 42.0), ('Smelter', 42.0)])

    def test_diameter_passthrough_falls_back_unfiltered_regardless_of_scope(self):
        out = _relabel([_particle({'56Fe': 6})], [_def('60Ni', group='Smelter')],
                       overlap='priority', unmatched='passthrough')
        p = out[0]
        d = cv.composition_items_for_role(
            p, 'element_diameter_nm', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        t = cv.composition_items_for_role(
            p, 'element_diameter_nm', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert d == t == [('56Fe', 42.0)]

    def test_unclassified_is_scope_invariant(self):
        """No expression to scope by, so DEFINITION and TOTAL PARTICLE are
        the same set for Unclassified, by construction, for every data
        type -- additive keys here, diameter covered by the passthrough-
        style test above via the same fallback path."""
        out = _relabel([_particle({'56Fe': 6, '63Cu': 4})],
                       [_def('60Ni', group='Smelter')], overlap='priority')
        p = out[0]
        assert p[pcr.BUCKET_KEY] == 'Unclassified'
        d = cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        t = cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert d == t

    def test_passthrough_is_scope_invariant_for_additive_keys(self):
        out = _relabel([_particle({'56Fe': 6})], [_def('60Ni', group='Smelter')],
                       overlap='priority', unmatched='passthrough')
        p = out[0]
        assert p[pcr.BUCKET_KEY] is None
        d = cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        t = cv.composition_items_for_role(
            p, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert d == t == [('56Fe', pytest.approx(0.6))]

    def test_double_count_total_particle_gives_each_copy_the_whole_particle(self):
        """The explicitly-confirmed interpretation: under double_count,
        each of a particle's several copies gets the FULL original
        particle's isotopes under TOTAL PARTICLE, not just its own
        definition's -- isotopes unrelated to either definition (63Cu
        here) count toward BOTH buckets' totals. Counts here are the raw
        per-isotope values _particle() was given (10, 8, 4), not particle
        presence, so the expected sum is 10+8+4=22 for BOTH copies."""
        out = _relabel(
            [_particle({'60Ni': 10, '107Ag': 8, '63Cu': 4})],
            [_def('60Ni', group='Smelter'), _def('107Ag', group='Background')],
            overlap='double_count')
        by_label = {c[pcr.BUCKET_KEY]: c for c in out}
        smelter_total = cv.composition_items_for_role(
            by_label['Smelter'], 'elements', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        bg_total = cv.composition_items_for_role(
            by_label['Background'], 'elements', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert smelter_total == [('Smelter', 22)]
        assert bg_total == [('Background', 22)]
        # BY DEFINITION stays exactly as before: no cross-bucket leakage,
        # each copy sees only its own definition's isotope (60Ni=10 or
        # 107Ag=8), never 63Cu and never the other definition's isotope.
        smelter_def = cv.composition_items_for_role(
            by_label['Smelter'], 'elements', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        bg_def = cv.composition_items_for_role(
            by_label['Background'], 'elements', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        assert smelter_def == [('Smelter', 10)]
        assert bg_def == [('Background', 8)]

    def test_drop_mfc_group_blocks_total_particle_fabrication(self):
        """The critical safety case: an MFC-dependent key (particle_mass_fg)
        with REAL data present, on a multi-definition group whose pooling
        policy is "drop_mfc" -- the classifier's own collapse refuses to
        combine it (different isotopes may rest on different Mass Fraction
        Calculator assumptions). TOTAL PARTICLE must respect that same
        refusal rather than silently re-deriving the number the classifier
        itself declined to compute."""
        particle = {
            'elements': {'60Ni': 1, '107Ag': 1},
            'element_mass_fg': {'60Ni': 5.0, '107Ag': 8.0},
            'particle_mass_fg': {'60Ni': 55.0, '107Ag': 88.0},
            'source_sample': 'SampleA',
        }
        out = pcr.relabel_particles(
            [particle],
            [_def('60Ni', group='Mixed'), _def('107Ag', group='Mixed')],
            {'Mixed': '#123456'}, 'double_count', 'unclassified', '#888888',
            group_pooling_policies={'Mixed': 'drop_mfc'})
        for copy in out:
            assert 'particle_mass_fg' not in copy
            # The raw data genuinely exists (proving this isn't a vacuous
            # pass because there was nothing to fabricate from).
            assert copy[pcr.RAW_KEY]['particle_mass_fg'] == \
                {'60Ni': 55.0, '107Ag': 88.0}
            total = cv.composition_items_for_role(
                copy, 'particle_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
            assert total == []

    def test_non_mfc_key_unaffected_by_drop_mfc_gate(self):
        """The gate is specific to MFC-dependent keys -- element_mass_fg
        (additive, MFC-independent) must still combine normally under
        TOTAL PARTICLE even inside a drop_mfc-pooled group."""
        particle = {
            'elements': {'60Ni': 1, '107Ag': 1},
            'element_mass_fg': {'60Ni': 5.0, '107Ag': 8.0},
            'source_sample': 'SampleA',
        }
        out = pcr.relabel_particles(
            [particle],
            [_def('60Ni', group='Mixed'), _def('107Ag', group='Mixed')],
            {'Mixed': '#123456'}, 'double_count', 'unclassified', '#888888',
            group_pooling_policies={'Mixed': 'drop_mfc'})
        mixed_copy = out[0]
        total = cv.composition_items_for_role(
            mixed_copy, 'element_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert total == [('Mixed', pytest.approx(13.0))]

    def test_keep_mfc_group_allows_total_particle_through(self):
        """The contrast case: a single-definition group (no pooling
        ambiguity, keep_mfc naturally true) DOES let TOTAL PARTICLE compute
        a real combined number for an MFC-dependent key."""
        particle = {
            'elements': {'60Ni': 1, '107Ag': 1},
            'element_mass_fg': {'60Ni': 5.0, '107Ag': 8.0},
            'particle_mass_fg': {'60Ni': 55.0, '107Ag': 88.0},
            'source_sample': 'SampleA',
        }
        out = pcr.relabel_particles(
            [particle], [_def('60Ni', group='Smelter')],
            {'Smelter': '#123456'}, 'priority', 'unclassified', '#888888')
        copy = out[0]
        by_def = cv.composition_items_for_role(
            copy, 'particle_mass_fg', cv.ROLE_SERIES, cv.SCOPE_DEFINITION)
        total = cv.composition_items_for_role(
            copy, 'particle_mass_fg', cv.ROLE_SERIES, cv.SCOPE_TOTAL_PARTICLE)
        assert by_def == [('Smelter', 55.0)]
        assert total == [('Smelter', pytest.approx(143.0))]


class TestEffectiveScope:
    def test_non_classifier_stream_always_definition(self):
        assert cv.effective_scope({cv.SCOPE_CONFIG_KEY: cv.SCOPE_TOTAL_PARTICLE},
                                  {'type': 'sample_data'}) == cv.SCOPE_DEFINITION

    def test_invalid_stored_value_falls_back_to_definition(self):
        out = _relabel([_particle({'60Ni': 10})], [_def('60Ni', group='Smelter')],
                       overlap='priority')
        stream = {'_classifier_registry': {'Smelter': {}}, 'particle_data': out}
        assert cv.effective_scope({cv.SCOPE_CONFIG_KEY: 'garbage'}, stream) == \
            cv.SCOPE_DEFINITION

    def test_missing_config_key_defaults_to_definition(self):
        out = _relabel([_particle({'60Ni': 10})], [_def('60Ni', group='Smelter')],
                       overlap='priority')
        stream = {'_classifier_registry': {'Smelter': {}}, 'particle_data': out}
        assert cv.effective_scope({}, stream) == cv.SCOPE_DEFINITION

    def test_explicit_total_particle_is_honored(self):
        out = _relabel([_particle({'60Ni': 10})], [_def('60Ni', group='Smelter')],
                       overlap='priority')
        stream = {'_classifier_registry': {'Smelter': {}}, 'particle_data': out}
        assert cv.effective_scope(
            {cv.SCOPE_CONFIG_KEY: cv.SCOPE_TOTAL_PARTICLE}, stream) == \
            cv.SCOPE_TOTAL_PARTICLE


class TestClassifierViewGroupScopeCombo:
    """The shared settings-dialog widget's second combo box."""

    def test_offers_both_scopes(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_PER_KEY)
        box = grp.build()
        assert box is not None
        offered = [grp.scope_combo.itemData(i)
                  for i in range(grp.scope_combo.count())]
        assert offered == [cv.SCOPE_DEFINITION, cv.SCOPE_TOTAL_PARTICLE]

    def test_enabled_when_role_is_groups(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_PER_KEY)
        box = grp.build()
        assert box is not None
        assert grp.role_combo.currentData() == cv.ROLE_SERIES
        assert grp.scope_combo.isEnabled()

    def test_disabled_when_role_is_off(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_PER_KEY)
        box = grp.build()
        assert box is not None
        grp.role_combo.setCurrentIndex(grp.role_combo.findData(cv.ROLE_OFF))
        assert not grp.scope_combo.isEnabled()

    def test_disabled_for_multi_key_arity(self, qapp):
        """ARITY_MULTI_KEY never offers SERIES at all, so the scope combo
        should never be enabled for it regardless of the initial role."""
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_MULTI_KEY)
        box = grp.build()
        assert box is not None
        assert grp.role_combo.currentData() != cv.ROLE_SERIES
        assert not grp.scope_combo.isEnabled()

    def test_collect_includes_scope(self, qapp):
        from results.shared_plot_utils import ClassifierViewGroup
        out = _wired_node().get_output_data()
        grp = ClassifierViewGroup({}, out, cv.ARITY_PER_KEY)
        box = grp.build()
        assert box is not None
        grp.scope_combo.setCurrentIndex(
            grp.scope_combo.findData(cv.SCOPE_TOTAL_PARTICLE))
        collected = grp.collect()
        assert collected[cv.SCOPE_CONFIG_KEY] == cv.SCOPE_TOTAL_PARTICLE


def _scope_test_stream():
    """Single-sample classifier stream for node-level scope tests: 20
    Smelter particles (60Ni+56Fe each) and 15 Unclassified particles
    (107Ag), sized so BY-DEFINITION vs TOTAL-PARTICLE produce visibly
    different, easy-to-assert-on numbers."""
    def p(ni=None, fe=None, ag=None):
        e, m, d = {}, {}, {}
        for iso, val in (('60Ni', ni), ('56Fe', fe), ('107Ag', ag)):
            if val is not None:
                e[iso] = 1
                m[iso] = val * 10.0
                d[iso] = val + 100.0
        return {'elements': e, 'element_mass_fg': m, 'element_diameter_nm': d,
                'source_sample': 'A'}

    particles = ([p(ni=5, fe=3) for _ in range(20)]
                 + [p(ag=8) for _ in range(15)])
    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'sample_data', 'sample_name': 'A', 'particle_data': particles,
        'selected_isotopes': [{'label': '60Ni'}, {'label': '56Fe'},
                              {'label': '107Ag'}],
    }
    clf.definitions = [_def('60Ni', target='A', group='Smelter')]
    clf.groups = {'Smelter': '#FF6600'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = 'priority'
    return clf


class TestHistogramScopeWiring:
    def test_classifier_scope_method_exists(self, qapp):
        from results.results_bar_charts import HistogramPlotNode
        node = HistogramPlotNode()
        assert hasattr(node, 'classifier_scope')

    def test_mass_extraction_differs_by_scope(self, qapp):
        from results.results_bar_charts import HistogramPlotNode
        out = _scope_test_stream().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES

        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        data_def = node.extract_plot_data()
        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
        data_total = node.extract_plot_data()

        assert data_def['Smelter'] == [50.0] * 20
        assert data_total['Smelter'] == [80.0] * 20

    def test_diameter_now_respects_groups_role(self, qapp):
        """Regression for the gap found while wiring this feature:
        histogram's diameter data types never went through the
        role-aware/bucket-collapse-aware reader at all, so GROUPS silently
        showed real ungrouped isotopes -- same bug class box plot had,
        just never fixed here until now."""
        from results.results_bar_charts import HistogramPlotNode
        out = _scope_test_stream().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Diameter (nm)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES

        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        data_def = node.extract_plot_data()
        assert set(data_def.keys()) <= {'Smelter', 'Unclassified'}
        assert len(data_def['Smelter']) == 20

        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
        data_total = node.extract_plot_data()
        assert len(data_total['Smelter']) == 40  # 60Ni AND 56Fe per particle

    def test_dialog_renders_across_role_and_scope_combinations(self, qapp):
        from results.results_bar_charts import HistogramPlotNode, HistogramDisplayDialog
        out = _scope_test_stream().get_output_data()
        node = HistogramPlotNode()
        node.process_data(out)
        dlg = HistogramDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            for scope in (cv.SCOPE_DEFINITION, cv.SCOPE_TOTAL_PARTICLE):
                node.config[cv.ROLE_CONFIG_KEY] = role
                node.config[cv.SCOPE_CONFIG_KEY] = scope
                dlg._refresh()  # must not raise


class TestBoxPlotScopeWiring:
    def test_classifier_scope_method_exists(self, qapp):
        from results.results_box_plot import BoxPlotNode
        node = BoxPlotNode()
        assert hasattr(node, 'classifier_scope')

    def test_mass_extraction_differs_by_scope(self, qapp):
        from results.results_box_plot import BoxPlotNode
        out = _scope_test_stream().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES

        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        data_def = node.extract_plot_data()
        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
        data_total = node.extract_plot_data()

        assert data_def['Smelter'] == [50.0] * 20
        assert data_total['Smelter'] == [80.0] * 20

    def test_dialog_renders_across_role_and_scope_combinations(self, qapp):
        from results.results_box_plot import BoxPlotNode, BoxPlotDisplayDialog
        out = _scope_test_stream().get_output_data()
        node = BoxPlotNode()
        node.process_data(out)
        dlg = BoxPlotDisplayDialog(node, None)
        for role in (cv.ROLE_SERIES, cv.ROLE_OFF):
            for scope in (cv.SCOPE_DEFINITION, cv.SCOPE_TOTAL_PARTICLE):
                node.config[cv.ROLE_CONFIG_KEY] = role
                node.config[cv.SCOPE_CONFIG_KEY] = scope
                dlg._refresh()  # must not raise


class TestElementBarChartScopeInvariance:
    """Confirms the deliberate choice NOT to wire scope into element bar
    chart: it only ever counts particles (val > 0 -> +1), never reads the
    numeric magnitude of a bucket's collapsed value, so BY DEFINITION and
    TOTAL PARTICLE are provably indistinguishable in its output."""

    def test_no_scope_wiring_present(self, qapp):
        from results.results_bar_charts import ElementBarChartPlotNode
        node = ElementBarChartPlotNode()
        assert not hasattr(node, 'classifier_scope')

    def test_output_identical_regardless_of_scope_config(self, qapp):
        from results.results_bar_charts import ElementBarChartPlotNode
        out = _scope_test_stream().get_output_data()
        node = ElementBarChartPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES

        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        data_def = node.extract_plot_data()
        node.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
        data_total = node.extract_plot_data()

        assert data_def == data_total == {'Smelter': 20, 'Unclassified': 15}


# --------------------------------------------------------------------------- #
# heatmap_plot: GROUPS/PANELS/COLORS/OFF roles (ARITY_HEATMAP, 2026-08-25)
# --------------------------------------------------------------------------- #
def _heatmap_particle(sample='A', **isotopes):
    """One particle with 'elements'/'element_mass_fg' for every isotope
    given -- values chosen (isotope_count * 10.0) so DEFINITION vs
    TOTAL_PARTICLE and Whole-Group vs Detected-Only produce distinct,
    easy-to-assert-on numbers."""
    e, m = {}, {}
    for iso, count in isotopes.items():
        e[iso] = count
        m[iso] = count * 10.0
    return {'elements': e, 'element_mass_fg': m, 'source_sample': sample}


def _heatmap_test_stream(sample='A'):
    """Single-sample classifier stream: 3 "clean" Smelter particles
    (60Ni+56Fe only), 1 "dirty" Smelter particle (also carries 63Cu -- only
    visible under TOTAL_PARTICLE/Whole-Group), 2 Unclassified particles
    (107Ag). Smelter triggered by 60Ni alone (partial match)."""
    particles = (
        [_heatmap_particle(sample, **{'60Ni': 5, '56Fe': 3}) for _ in range(3)]
        + [_heatmap_particle(sample, **{'60Ni': 4, '56Fe': 2, '63Cu': 9})]
        + [_heatmap_particle(sample, **{'107Ag': 8}) for _ in range(2)]
    )
    clf = ParticleClassifierNode()
    clf.input_data = {
        'type': 'sample_data', 'sample_name': sample, 'particle_data': particles,
        'selected_isotopes': [{'label': x} for x in ('60Ni', '56Fe', '63Cu', '107Ag')],
    }
    clf.definitions = [_def('60Ni', target=sample, group='Smelter')]
    clf.groups = {'Smelter': '#FF6600'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = 'priority'
    return clf


class TestGroupCompositionRows:
    """classifier_view.group_composition_rows -- the GROUPS-role primitive
    heatmap_plot's ARITY_HEATMAP uses; built generally for reuse."""

    def test_definition_scope_only_shows_referenced_isotopes(self):
        out = _heatmap_test_stream().get_output_data()
        rows = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_DEFINITION,
            cv.DENOMINATOR_WHOLE_GROUP)
        assert set(rows['Smelter']['total_values'].keys()) == {'60Ni'}
        assert rows['Smelter']['particle_count'] == 4

    def test_total_particle_scope_reveals_every_isotope(self):
        out = _heatmap_test_stream().get_output_data()
        rows = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_TOTAL_PARTICLE,
            cv.DENOMINATOR_WHOLE_GROUP)
        assert set(rows['Smelter']['total_values'].keys()) == {'60Ni', '56Fe', '63Cu'}

    def test_whole_group_zero_pads_non_carriers(self):
        out = _heatmap_test_stream().get_output_data()
        rows = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_TOTAL_PARTICLE,
            cv.DENOMINATOR_WHOLE_GROUP)
        cu = rows['Smelter']['total_values']['63Cu']
        assert sorted(cu) == [0.0, 0.0, 0.0, 90.0]
        assert len(cu) == rows['Smelter']['particle_count'] == 4

    def test_detected_only_has_no_padding(self):
        out = _heatmap_test_stream().get_output_data()
        rows = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_TOTAL_PARTICLE,
            cv.DENOMINATOR_DETECTED_ONLY)
        assert rows['Smelter']['total_values']['63Cu'] == [90.0]

    def test_unclassified_scope_invariant(self):
        out = _heatmap_test_stream().get_output_data()
        rows_def = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_DEFINITION,
            cv.DENOMINATOR_WHOLE_GROUP)
        rows_total = cv.group_composition_rows(
            out['particle_data'], 'element_mass_fg', cv.SCOPE_TOTAL_PARTICLE,
            cv.DENOMINATOR_WHOLE_GROUP)
        assert rows_def['Unclassified'] == rows_total['Unclassified']

    def test_passthrough_particles_excluded(self):
        particles = [_particle({'56Fe': 4})]
        out = _relabel(particles, [_def('60Ni', group='Smelter')],
                       overlap='priority', unmatched='passthrough')
        rows = cv.group_composition_rows(out, 'elements', cv.SCOPE_DEFINITION,
                                         cv.DENOMINATOR_WHOLE_GROUP)
        assert rows == {}

    def test_drop_mfc_gate_blocks_fabrication_both_scopes(self):
        """A drop_mfc-pooled group's MFC-dependent key must show nothing --
        under EITHER scope, unlike composition_items_for_role where
        DEFINITION was safe by construction (it only ever echoed the
        classifier's own number back). Here both scopes independently
        re-read raw data, so both need the gate."""
        p1 = _particle({'60Ni': 10, '107Ag': 8})
        p1['particle_mass_fg'] = {'60Ni': 55.0, '107Ag': 88.0}
        defs = [_def('60Ni', group='Mixed'), _def('107Ag', group='Mixed')]
        out = _relabel([p1], defs, overlap='double_count', unmatched='unclassified',
                       groups={'Mixed': '#123456'})
        # simulate the drop_mfc policy the way relabel_particles would apply it
        from tools.particle_classifier_relabel import relabel_particles
        out = relabel_particles([p1], defs, {'Mixed': '#123456'}, 'double_count',
                                'unclassified', '#9CA3AF',
                                group_pooling_policies={'Mixed': 'drop_mfc'})
        rows_def = cv.group_composition_rows(out, 'particle_mass_fg', cv.SCOPE_DEFINITION,
                                             cv.DENOMINATOR_WHOLE_GROUP)
        rows_total = cv.group_composition_rows(out, 'particle_mass_fg', cv.SCOPE_TOTAL_PARTICLE,
                                               cv.DENOMINATOR_WHOLE_GROUP)
        assert rows_def['Mixed']['total_values'] == {}
        assert rows_total['Mixed']['total_values'] == {}
        # particle_count still reflects true membership even though the
        # data for this key is withheld
        assert rows_def['Mixed']['particle_count'] == 2


class TestDefaultRowBucketColors:
    """classifier_view.default_row_bucket_colors -- the COLORS-role default-
    underline primitive. Presence-only matching means a row's bucket
    membership is always uniform (verified here, not just asserted)."""

    def test_uniform_single_bucket_row(self):
        out = _heatmap_test_stream().get_output_data()
        smelter = [p for p in out['particle_data'] if cv.bucket_of(p) == 'Smelter']
        assert cv.default_row_bucket_colors(out, smelter) == ['#FF6600']

    def test_unclassified_is_not_colored_by_default(self):
        """Spec correction (2026-08-25): COLORS colors particles that matched
        something the user DEFINED. "Unclassified" and "passthrough" both
        mean "matched nothing", so they must look identical -- uncolored --
        rather than differing purely by an upstream mode switch that says
        nothing about the science. Was previously colored gray."""
        out = _heatmap_test_stream().get_output_data()
        unclassified = [p for p in out['particle_data'] if cv.bucket_of(p) == 'Unclassified']
        assert unclassified, "fixture must actually contain unclassified particles"
        assert cv.default_row_bucket_colors(out, unclassified) == []
        # Still reachable for any future caller that genuinely wants it.
        assert cv.default_row_bucket_colors(
            out, unclassified, include_unclassified=True)

    def test_double_count_row_gets_one_color_per_matched_bucket(self):
        clf = ParticleClassifierNode()
        clf.input_data = {'type': 'sample_data', 'sample_name': 'SampleA',
                          'particle_data': [_particle({'60Ni': 10, '107Ag': 8})],
                          'selected_isotopes': [{'label': '60Ni'}, {'label': '107Ag'}]}
        clf.definitions = [_def('60Ni', group='Smelter'), _def('107Ag', group='Background')]
        clf.groups = {'Smelter': '#FF0000', 'Background': '#00FF00'}
        clf.unmatched_mode = 'unclassified'
        clf.overlap_mode = 'double_count'
        out = clf.get_output_data()
        out_particles = out['particle_data']
        assert len(out_particles) == 2  # one copy per matched definition
        colors = cv.default_row_bucket_colors(out, out_particles)
        assert colors == ['#FF0000', '#00FF00']

    def test_all_passthrough_row_has_no_colors(self):
        out = _relabel([_particle({'56Fe': 4})], [_def('60Ni', group='Smelter')],
                       overlap='priority', unmatched='passthrough')
        assert cv.default_row_bucket_colors({'_classifier_registry': {}}, out) == []


class TestEffectiveDenominator:
    def test_non_classifier_stream_defaults_whole_group(self):
        assert cv.effective_denominator({}, {'type': 'sample_data'}) == cv.DENOMINATOR_WHOLE_GROUP

    def test_invalid_stored_value_falls_back(self):
        out = _heatmap_test_stream().get_output_data()
        cfg = {cv.DENOMINATOR_CONFIG_KEY: 'nonsense'}
        assert cv.effective_denominator(cfg, out) == cv.DENOMINATOR_WHOLE_GROUP

    def test_explicit_detected_only_honored(self):
        out = _heatmap_test_stream().get_output_data()
        cfg = {cv.DENOMINATOR_CONFIG_KEY: cv.DENOMINATOR_DETECTED_ONLY}
        assert cv.effective_denominator(cfg, out) == cv.DENOMINATOR_DETECTED_ONLY


class TestHeatmapComboSignatureClassifierAware:
    """Regression test for a real bug found while building GROUPS role: the
    combination-row grouping (``_combo_signature``, used by OFF/COLORS/
    PANELS) originally read a particle's composition dict directly, which
    for a MATCHED classifier particle is already the collapsed
    ``{bucket_label: value}`` singleton -- every particle sharing a bucket
    would have produced the SAME degenerate one-key signature, reproducing
    the exact "1x1 diagonal per bucket" bug this whole effort exists to fix,
    for OFF/COLORS/PANELS specifically (GROUPS was never affected, it never
    calls this function). Fixed by reading through
    ``classifier_view.composition(..., collapsed=False)``."""

    def test_off_role_shows_real_isotope_combinations_not_bucket_labels(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = node.extract_plot_data()
        assert 'Smelter' not in data and 'Unclassified' not in data
        assert any('60Ni' in k and '56Fe' in k for k in data)
        assert '107Ag' in data

    def test_combo_signature_matches_non_classifier_baseline(self):
        """Safety net: for data that never touched a classifier, the fixed
        version must be byte-identical to reading the dict directly (no
        RAW_KEY dual-carry present, so classifier_view.composition() falls
        straight through to the same particle.get(data_key))."""
        from results.results_heatmap import _combo_signature
        particle = {'element_mass_fg': {'60Ni': 50.0, '56Fe': 30.0}}
        sig = _combo_signature(particle, 'element_mass_fg')
        assert sig == (frozenset({'60Ni', '56Fe'}), {'60Ni': 50.0, '56Fe': 30.0})


class TestHeatmapNodeExtraction:
    """HeatmapPlotNode's role-aware extract_plot_data()/extract_panel_data()."""

    def test_classifier_role_scope_denominator_methods_exist(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        node = HeatmapPlotNode()
        assert hasattr(node, 'classifier_role')
        assert hasattr(node, 'classifier_scope')
        assert hasattr(node, 'classifier_denominator')

    def test_groups_role_row_shape_has_count_and_particle_count(self, qapp):
        """Regression test: _group_rows originally omitted 'count' (only
        'particle_count'), which crashed _combine_data (Combined Heatmap
        display mode) with a KeyError -- _build_combinations's rows always
        carry both (redundantly equal) keys and _group_rows must match that
        shape exactly, not just what draw_combinations_heatmap itself reads."""
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = node.extract_plot_data()
        for row in data.values():
            assert row['count'] == row['particle_count']

    def test_groups_role_show_expression_toggle(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        node.config['show_group_expression'] = True
        data = node.extract_plot_data()
        assert any(k.startswith('Smelter (') for k in data)
        assert 'Unclassified' in data  # no expression -> unaffected

    def test_panels_role_extract_plot_data_returns_none(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        assert node.extract_plot_data() is None

    def test_panels_role_partitions_by_bucket(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        panels = node.extract_panel_data()
        assert set(panels.keys()) == {'Smelter', 'Unclassified'}
        assert sum(d['particle_count'] for d in panels['Smelter'].values()) == 4
        assert sum(d['particle_count'] for d in panels['Unclassified'].values()) == 2

    def test_colors_role_extraction_identical_to_off(self, qapp):
        from results.results_heatmap import HeatmapPlotNode
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data_off = node.extract_plot_data()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        data_colors = node.extract_plot_data()
        assert data_off == data_colors


class TestHeatmapDialogRoleWiring:
    """HeatmapDisplayDialog end-to-end across all 4 roles -- real headless
    Qt, mirroring histogram/box_plot's own dialog-level role tests."""

    def _dialog(self):
        from results.results_heatmap import HeatmapPlotNode, HeatmapDisplayDialog
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        return node, HeatmapDisplayDialog(node, None)

    def test_all_four_roles_render_without_raising(self, qapp):
        node, dlg = self._dialog()
        for role in (cv.ROLE_SERIES, cv.ROLE_FACET, cv.ROLE_ENCODE, cv.ROLE_OFF):
            node.config[cv.ROLE_CONFIG_KEY] = role
            dlg._refresh()
            assert len(dlg.figure.get_axes()) >= 1

    def test_groups_role_label_not_mangled_by_symbol_mode(self, qapp):
        """'Smelter' starts with the real element symbol 'Sm' -- must not be
        stripped to that under 'Symbol'/'Atomic Notation' label modes."""
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        node.config['label_mode'] = 'Symbol'
        dlg._refresh()
        ax = dlg.figure.get_axes()[0]
        y_labels = [t.get_text() for t in ax.get_yticklabels()]
        assert any('Smelter' in lbl for lbl in y_labels)

    def test_panels_role_single_sample_one_panel_per_group(self, qapp):
        """Single-sample PANELS shows every group at once, no selector --
        there is nothing to switch between (spec, 2026-08-25)."""
        from results.results_heatmap import PANEL_GROUP_CONFIG_KEY
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        dlg._refresh()
        titled = [ax for ax in dlg.figure.get_axes() if ax.get_title()]
        assert {ax.get_title() for ax in titled} == {'Smelter', 'Unclassified'}

    def test_panels_titles_follow_show_expression_toggle(self, qapp):
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        node.config['show_group_expression'] = True
        dlg._refresh()
        titles = {ax.get_title() for ax in dlg.figure.get_axes() if ax.get_title()}
        assert 'Smelter (60Ni)' in titles
        # Unclassified has no expression, so it is unaffected either way.
        assert 'Unclassified' in titles

    def test_colors_legend_hidden_by_manual_override_shown_otherwise(self, qapp):
        from results.results_heatmap import UNDERLINE_CONFIG_KEY
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        node.config[UNDERLINE_CONFIG_KEY] = {}
        dlg._refresh()
        ax = dlg.figure.get_axes()[0]
        assert ax.get_legend() is not None

        row = dlg._axes_row_combos[id(ax)][0]
        node.config[UNDERLINE_CONFIG_KEY] = {row: '#000000'}
        dlg._refresh()
        assert dlg.figure.get_axes()[0].get_legend() is None

        node.config[UNDERLINE_CONFIG_KEY] = {}
        dlg._refresh()
        assert dlg.figure.get_axes()[0].get_legend() is not None

    def test_colors_legend_survives_offscreen_manual_override(self, qapp):
        """Regression: the legend was suppressed whenever ANY stored override
        existed, even for a row outside heatmap's visible top-N slice -- so
        one old underline on a since-filtered-out row hid the legend forever.
        Gating must consider only rows actually on screen."""
        from results.results_heatmap import UNDERLINE_CONFIG_KEY
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        node.config[UNDERLINE_CONFIG_KEY] = {'zz_row_not_currently_shown': '#000000'}
        dlg._refresh()
        assert dlg.figure.get_axes()[0].get_legend() is not None

    def test_colors_role_draws_underline_segments(self, qapp):
        from results.results_heatmap import UNDERLINE_CONFIG_KEY
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        node.config[UNDERLINE_CONFIG_KEY] = {}
        dlg._refresh()
        ax = dlg.figure.get_axes()[0]
        assert len(ax.lines) > 0

    def test_colors_does_not_underline_unclassified(self, qapp):
        """COLORS colors particles that matched something the user DEFINED.
        "Unclassified" and "passthrough" are two spellings of "matched
        nothing" and must look the same (uncolored), rather than differing
        purely by an upstream mode switch (spec correction, 2026-08-25)."""
        from results.results_heatmap import _default_row_bucket_colors_by_combo
        node, dlg = self._dialog()
        out = node.input_data
        defaults = _default_row_bucket_colors_by_combo(
            out['particle_data'], 'element_mass_fg', out)
        assert defaults, "matched rows must still be colored"
        assert not any(
            cv.bucket_of(p) == cv.UNCLASSIFIED_LABEL
            for key in defaults
            for p in out['particle_data']
            if key == '107Ag')

    def test_colors_legend_excludes_unclassified(self, qapp):
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        entries = dict(dlg._bucket_legend_entries())
        assert 'Smelter' in entries
        assert cv.UNCLASSIFIED_LABEL not in entries

    def _multi_node(self):
        from results.results_heatmap import HeatmapPlotNode
        out_a = _heatmap_test_stream('A').get_output_data()
        out_b = _heatmap_test_stream('B').get_output_data()
        multi = dict(out_a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
                      'particle_data': out_a['particle_data'] + out_b['particle_data']})
        node = HeatmapPlotNode()
        node.process_data(multi)
        node.config['data_type_display'] = 'Element Mass (fg)'
        return node, multi

    def test_multi_sample_panels_one_subplot_per_sample_for_chosen_group(self, qapp):
        """Multi-sample PANELS inverts the single-sample layout: the user
        picks ONE group and gets one subplot per SAMPLE, so the comparison
        is across samples rather than across groups (spec, 2026-08-25)."""
        from results.results_heatmap import (
            HeatmapDisplayDialog, PANEL_GROUP_CONFIG_KEY)
        node, _ = self._multi_node()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        node.config[PANEL_GROUP_CONFIG_KEY] = 'Smelter'
        dlg = HeatmapDisplayDialog(node, None)
        dlg._refresh()
        titles = {ax.get_title() for ax in dlg.figure.get_axes() if ax.get_title()}
        assert titles == {'A', 'B'}

    def test_multi_sample_panels_skips_samples_without_the_group(self, qapp):
        """A group defined for some samples but not others must yield no
        subplot at all for the samples it never applied to -- not an empty
        one (the classifier can hold different definitions per sample)."""
        from results.results_heatmap import HeatmapPlotNode
        out_a = _heatmap_test_stream('A').get_output_data()
        # Sample B: same particles, but NO definitions -> nothing is Smelter.
        clf_b = _heatmap_test_stream('B')
        clf_b.definitions = []
        out_b = clf_b.get_output_data()
        multi = dict(out_a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
                      'particle_data': out_a['particle_data'] + out_b['particle_data']})
        node = HeatmapPlotNode()
        node.process_data(multi)
        node.config['data_type_display'] = 'Element Mass (fg)'
        panels = node.extract_panel_data()
        assert set(panels['Smelter'].keys()) == {'A'}

    def test_panel_group_falls_back_when_stored_group_is_gone(self, qapp):
        """A saved project whose classifier was later re-configured must not
        render an empty window -- resolve against the CURRENT group list."""
        from results.results_heatmap import PANEL_GROUP_CONFIG_KEY
        node, _ = self._multi_node()
        node.config[PANEL_GROUP_CONFIG_KEY] = 'a_group_that_no_longer_exists'
        assert node.panel_group() in node.panel_groups()

    def test_panels_group_combo_and_display_mode_gating(self, qapp):
        """The group dropdown lives in Configure plot quantities (not inline),
        and PANELS defines its own layout so the multi-sample display-mode
        options are disabled with a visible reason under that role."""
        from results.results_heatmap import HeatmapSettingsDialog
        node, multi = self._multi_node()
        dlg = HeatmapSettingsDialog(node.config, True, ['A', 'B'],
                                    scope='quantities', input_data=multi)
        assert dlg.panel_group_combo is not None
        offered = [dlg.panel_group_combo.itemData(i)
                  for i in range(dlg.panel_group_combo.count())]
        assert 'Smelter' in offered

        role_combo = dlg._classifier_group.role_combo
        role_combo.setCurrentIndex(role_combo.findData(cv.ROLE_FACET))
        assert dlg.panel_group_combo.isEnabled()
        assert not dlg.display_mode.isEnabled()

        role_combo.setCurrentIndex(role_combo.findData(cv.ROLE_OFF))
        assert not dlg.panel_group_combo.isEnabled()
        assert dlg.display_mode.isEnabled()

    def test_cell_statistic_lives_in_quantities_not_format(self, qapp):
        """Cell value / Show spread decide WHAT NUMBER a cell reports, so they
        belong to "Configure plot quantities". They sat in the format scope
        historically, next to the genuinely cosmetic "Cell Appearance" group
        they are easy to confuse with (moved 2026-08-26)."""
        from results.results_heatmap import HeatmapSettingsDialog
        q = HeatmapSettingsDialog({}, False, [], scope='quantities', input_data=None)
        f = HeatmapSettingsDialog({}, False, [], scope='format', input_data=None)
        assert q.cell_stat_combo is not None and q.cell_spread_combo is not None
        assert f.cell_stat_combo is None and f.cell_spread_combo is None
        # The cosmetic neighbours must NOT have moved with it.
        assert f.cell_lw_spin is not None
        assert f.ann_fontsize_spin is not None

    def test_format_scope_preserves_cell_statistic_values(self, qapp):
        """A scope that no longer builds those widgets must pass the stored
        values through untouched rather than resetting them to defaults."""
        from results.results_heatmap import HeatmapSettingsDialog
        f = HeatmapSettingsDialog({'cell_stat': 'Mode', 'cell_spread': 'SD'},
                                  False, [], scope='format', input_data=None)
        cfg = f.collect()
        assert cfg['cell_stat'] == 'Mode'
        assert cfg['cell_spread'] == 'SD'

    def test_single_sample_settings_has_no_panel_group_combo(self, qapp):
        """Single-sample PANELS shows every group at once, so there is
        nothing to select -- the combo must not be built at all."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _heatmap_test_stream().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='quantities',
                                    input_data=out)
        assert dlg.panel_group_combo is None

    def test_combined_heatmap_display_mode_does_not_crash_under_groups(self, qapp):
        """Regression test for the KeyError('count') bug: Combined Heatmap
        mode merges every sample's rows via _combine_data, which reads
        'count' -- must work for GROUPS rows exactly like combination rows."""
        from results.results_heatmap import HeatmapPlotNode, HeatmapDisplayDialog
        out_a = _heatmap_test_stream('A').get_output_data()
        out_b = _heatmap_test_stream('B').get_output_data()
        multi = dict(out_a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
                      'particle_data': out_a['particle_data'] + out_b['particle_data']})
        node = HeatmapPlotNode()
        node.process_data(multi)
        node.config['data_type_display'] = 'Element Mass (fg)'
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        node.config['display_mode'] = 'Combined Heatmap'
        dlg = HeatmapDisplayDialog(node, None)
        dlg._refresh()  # must not raise
        assert len(dlg.figure.get_axes()) >= 1

    def test_denominator_and_show_expression_dialog_controls(self, qapp):
        from results.results_heatmap import HeatmapSettingsDialog
        out = _heatmap_test_stream().get_output_data()
        qdlg = HeatmapSettingsDialog({}, False, [], scope='quantities', input_data=out)
        assert qdlg.denominator_combo is not None
        offered = [qdlg.denominator_combo.itemData(i)
                  for i in range(qdlg.denominator_combo.count())]
        assert set(offered) == {cv.DENOMINATOR_WHOLE_GROUP, cv.DENOMINATOR_DETECTED_ONLY}

        fdlg = HeatmapSettingsDialog({}, False, [], scope='format', input_data=out)
        assert fdlg.show_expression_cb is not None

    def test_colors_underline_margin_widened_when_underlines_present(self, qapp):
        """Regression test for a real bug found by rendering to PNG and
        looking, not just checking Line2D objects exist: the underline is
        drawn at xmin=-0.22 AXES-fraction, well outside the axes' own
        bounding box, but tight_layout() has no idea that decoration needs
        room -- on a real render this left the axes' own left edge around
        figure-fraction 0.08, and the underline's -0.22-of-axes-width reach
        landed at a NEGATIVE figure-fraction x, i.e. past the edge of the
        canvas -- rendering as a barely-visible sliver at best. Confirmed
        by user report and by an actual saved-PNG inspection."""
        from results.results_heatmap import UNDERLINE_CONFIG_KEY
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        dlg._refresh()
        off_left = dlg.figure.subplotpars.left

        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        node.config[UNDERLINE_CONFIG_KEY] = {}
        dlg._refresh()
        assert dlg._any_underlines_this_render is True
        assert dlg.figure.subplotpars.left >= 0.24
        assert dlg.figure.subplotpars.left > off_left

    def test_no_margin_widening_when_no_underlines(self, qapp):
        """OFF/GROUPS/PANELS never draw the underline at all -- the margin
        fix must not fire (and must not needlessly shrink normal charts)
        when there's nothing to make room for."""
        node, dlg = self._dialog()
        node.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        dlg._refresh()
        assert dlg._any_underlines_this_render is False


class TestFigureViewConfigRouting:
    """The bug that made a full day of classifier work invisible in the app
    while every automated test passed (2026-08-25).

    Multi-figure viz nodes are never handed to their dialog directly: the app
    wraps them in a ``_FigureView`` so each figure window keeps independent
    settings (``open_node_figures`` -> ``_add_node_figure`` ->
    ``dialog_class(VIEW, ...)``). The settings dialog writes the user's
    choices into ``view.config``. But ``_FigureView.__getattr__`` only swapped
    that config in for methods named ``extract_*`` -- so ``classifier_role``,
    ``classifier_scope``, ``classifier_denominator`` and ``panel_group`` read
    the NODE's config, which nothing ever writes to, and returned their
    defaults forever.

    Symptoms, all reproduced before the fix: PANELS showed "No data
    available" (``extract_plot_data`` correctly returned None for FACET while
    ``_refresh`` still believed the role was OFF and took the non-FACET
    branch); COLORS drew no underlines and no legend; GROUPS *appeared* to
    work purely because extraction was wrapped and did see the right role.

    **Every test in this file previously built its dialog around the raw
    node**, which the app never does -- which is why 1204 green tests said
    nothing about production. These tests use the real path on purpose.
    """

    def _view_and_dialog(self, role):
        from results.results_heatmap import HeatmapPlotNode, HeatmapDisplayDialog
        from results.shared_plot_utils import _FigureView
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        node.config['data_type_display'] = 'Element Mass (fg)'
        view = _FigureView(node, HeatmapDisplayDialog, None)
        view.config[cv.ROLE_CONFIG_KEY] = role
        return node, view, HeatmapDisplayDialog(view, None)

    def test_role_follows_the_figures_config_not_the_nodes(self, qapp):
        node, view, _ = self._view_and_dialog(cv.ROLE_FACET)
        assert node.config.get(cv.ROLE_CONFIG_KEY) is None
        assert view.classifier_role() == cv.ROLE_FACET

    def test_scope_and_denominator_follow_the_figures_config(self, qapp):
        node, view, _ = self._view_and_dialog(cv.ROLE_SERIES)
        view.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
        view.config[cv.DENOMINATOR_CONFIG_KEY] = cv.DENOMINATOR_DETECTED_ONLY
        assert view.classifier_scope() == cv.SCOPE_TOTAL_PARTICLE
        assert view.classifier_denominator() == cv.DENOMINATOR_DETECTED_ONLY

    def test_panels_render_through_a_view_instead_of_no_data(self, qapp):
        """The headline symptom: "No data available, right-click for options"
        under PANELS."""
        _, _, dlg = self._view_and_dialog(cv.ROLE_FACET)
        dlg._refresh()
        texts = [t.get_text() for a in dlg.figure.get_axes() for t in a.texts]
        assert not any('No data available' in t for t in texts), texts
        titled = [a.get_title() for a in dlg.figure.get_axes() if a.get_title()]
        assert set(titled) == {'Smelter', 'Unclassified'}

    def test_colors_draw_through_a_view(self, qapp):
        from results.results_heatmap import UNDERLINE_CONFIG_KEY
        _, view, dlg = self._view_and_dialog(cv.ROLE_ENCODE)
        view.config[UNDERLINE_CONFIG_KEY] = {}
        dlg._refresh()
        ax = dlg.figure.get_axes()[0]
        assert ax.get_legend() is not None
        assert len(ax.lines) > 0
        assert dlg.figure.subplotpars.left >= 0.24

    def test_panel_group_selection_follows_the_figures_config(self, qapp):
        from results.results_heatmap import (
            HeatmapPlotNode, HeatmapDisplayDialog, PANEL_GROUP_CONFIG_KEY)
        from results.shared_plot_utils import _FigureView
        out_a = _heatmap_test_stream('A').get_output_data()
        out_b = _heatmap_test_stream('B').get_output_data()
        multi = dict(out_a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
                      'particle_data': out_a['particle_data'] + out_b['particle_data']})
        node = HeatmapPlotNode()
        node.process_data(multi)
        view = _FigureView(node, HeatmapDisplayDialog, None)
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        view.config[PANEL_GROUP_CONFIG_KEY] = 'Unclassified'
        assert view.panel_group() == 'Unclassified'

    def test_two_figures_of_one_node_keep_independent_roles(self, qapp):
        """The whole reason _FigureView exists -- and the thing that broke."""
        from results.results_heatmap import HeatmapPlotNode, HeatmapDisplayDialog
        from results.shared_plot_utils import _FigureView
        out = _heatmap_test_stream().get_output_data()
        node = HeatmapPlotNode()
        node.process_data(out)
        v1 = _FigureView(node, HeatmapDisplayDialog, None)
        v2 = _FigureView(node, HeatmapDisplayDialog, None)
        v1.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        v2.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_ENCODE
        assert v1.classifier_role() == cv.ROLE_SERIES
        assert v2.classifier_role() == cv.ROLE_ENCODE

    def test_other_nodes_classifier_methods_route_too(self, qapp):
        """histogram and box plot carry the same config-derived methods and
        are equally multi-figure -- the general fix must cover them, not just
        heatmap (histogram's element-colour picker reads the role from the
        dialog, so it was silently wrong through a view as well)."""
        from results.results_bar_charts import HistogramPlotNode, HistogramDisplayDialog
        from results.results_box_plot import BoxPlotNode, BoxPlotDisplayDialog
        from results.shared_plot_utils import _FigureView
        out = _scope_test_stream().get_output_data()
        for node_cls, dlg_cls in ((HistogramPlotNode, HistogramDisplayDialog),
                                  (BoxPlotNode, BoxPlotDisplayDialog)):
            node = node_cls()
            node.process_data(out)
            view = _FigureView(node, dlg_cls, None)
            view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
            view.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_TOTAL_PARTICLE
            assert view.classifier_role() == cv.ROLE_OFF, node_cls.__name__
            assert view.classifier_scope() == cv.SCOPE_TOTAL_PARTICLE, node_cls.__name__

    def test_marker_decorator_also_routes(self, qapp):
        """view_config_method covers methods that don't match a prefix, so a
        future config-derived method can opt in explicitly instead of relying
        on being named just so."""
        from results.shared_plot_utils import _FigureView, view_config_method

        class _Node:
            def __init__(self):
                self.config = {'x': 'node'}

            @view_config_method
            def marked(self):
                return self.config.get('x')

            def unmarked(self):
                return self.config.get('x')

        node = _Node()
        view = _FigureView(node, None, None)
        view.config['x'] = 'figure'
        assert view.marked() == 'figure'
        assert view.unmarked() == 'node'


class TestUnderlineRenameMigration:
    """The feature was renamed highlight -> underline (2026-08-25) because
    that is what it draws. The config key moved with it, so saved projects
    must keep working."""

    def test_legacy_key_is_read(self):
        from results.results_heatmap import (
            _read_underlined_combos, LEGACY_UNDERLINE_CONFIG_KEY)
        cfg = {LEGACY_UNDERLINE_CONFIG_KEY: {'60Ni': '#ABCDEF'}}
        assert _read_underlined_combos(cfg) == {'60Ni': '#ABCDEF'}

    def test_current_key_wins_over_legacy(self):
        from results.results_heatmap import (
            _read_underlined_combos, UNDERLINE_CONFIG_KEY,
            LEGACY_UNDERLINE_CONFIG_KEY)
        cfg = {UNDERLINE_CONFIG_KEY: {'60Ni': '#111111'},
               LEGACY_UNDERLINE_CONFIG_KEY: {'60Ni': '#222222'}}
        assert _read_underlined_combos(cfg) == {'60Ni': '#111111'}

    def test_writing_clears_the_legacy_key(self):
        from results.results_heatmap import (
            _write_underlined_combos, UNDERLINE_CONFIG_KEY,
            LEGACY_UNDERLINE_CONFIG_KEY)
        cfg = {LEGACY_UNDERLINE_CONFIG_KEY: {'60Ni': '#222222'}}
        _write_underlined_combos(cfg, {'60Ni': '#333333'})
        assert cfg[UNDERLINE_CONFIG_KEY] == {'60Ni': '#333333'}
        assert LEGACY_UNDERLINE_CONFIG_KEY not in cfg

    def test_legacy_list_format_still_normalizes(self):
        """The even older list-of-keys shape (all rendered black) predates
        per-row colors and must still load."""
        from results.results_heatmap import (
            _read_underlined_combos, LEGACY_UNDERLINE_CONFIG_KEY,
            DEFAULT_UNDERLINE_COLOR)
        cfg = {LEGACY_UNDERLINE_CONFIG_KEY: ['60Ni', '107Ag']}
        assert _read_underlined_combos(cfg) == {
            '60Ni': DEFAULT_UNDERLINE_COLOR, '107Ag': DEFAULT_UNDERLINE_COLOR}


class TestFalsyGroupColorDoesNotEraseBucket:
    """``groups.get(name, fallback)`` only substitutes when the key is
    ABSENT, so a group registered with an explicitly empty color resolved to
    None and was then silently dropped by every color consumer -- a bucket
    that renders as nothing at all is indistinguishable from a bug."""

    def test_registry_gets_a_real_color_for_a_none_valued_group(self):
        out = _relabel([_particle({'60Ni': 10})],
                       [_def('60Ni', group='Smelter')],
                       overlap='priority', groups={'Smelter': None})
        assert out[0][pcr.BUCKET_KEY] == 'Smelter'
        from tools.particle_classifier_relabel import build_bucket_registry
        reg = build_bucket_registry([_def('60Ni', group='Smelter')],
                                    {'Smelter': None}, 'unclassified', '#9CA3AF')
        assert reg['Smelter']['color']

    def test_bucket_without_registry_color_still_gets_a_color(self):
        """Even if a colorless entry somehow reaches the reader, the row must
        still be colored rather than silently skipped."""
        particles = _relabel([_particle({'60Ni': 10})],
                             [_def('60Ni', group='Smelter')], overlap='priority')
        stream = {'_classifier_registry': {'Smelter': {'color': None}}}
        assert cv.default_row_bucket_colors(stream, particles) == [
            cv.FALLBACK_BUCKET_COLOR]

    def test_unclassified_excluded_by_default_included_on_request(self):
        particles = _relabel([_particle({'107Ag': 4})],
                             [_def('60Ni', group='Smelter')], overlap='priority')
        stream = {'_classifier_registry': {
            cv.UNCLASSIFIED_LABEL: {'color': '#9CA3AF'}}}
        assert cv.default_row_bucket_colors(stream, particles) == []
        assert cv.default_row_bucket_colors(
            stream, particles, include_unclassified=True) == ['#9CA3AF']
