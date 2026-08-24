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
        assert collected == {cv.ROLE_CONFIG_KEY: cv.ROLE_FACET}
        assert isinstance(collected[cv.ROLE_CONFIG_KEY], str)

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
    def test_heatmap_quantities_offers_key_set_roles(self, qapp):
        """heatmap_plot is ARITY_KEY_SET -- SERIES must not be offered."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='quantities',
                                    input_data=out)
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES not in offered
        assert cv.ROLE_FACET in offered and cv.ROLE_ENCODE in offered

    def test_heatmap_format_scope_has_no_classifier_group(self, qapp):
        """The picker belongs in quantities only -- format scope must not
        build one at all."""
        from results.results_heatmap import HeatmapSettingsDialog
        out = _wired_node().get_output_data()
        dlg = HeatmapSettingsDialog({}, False, [], scope='format',
                                    input_data=out)
        assert dlg._classifier_group is None

    def test_correlation_matrix_quantities_offers_multi_key_roles(self, qapp):
        """correlation_matrix is ARITY_MULTI_KEY -- SERIES must not be
        offered (there is no single-key axis a bucket could be)."""
        from results.results_matrix import MatrixSettingsDialog
        out = _wired_node().get_output_data()
        dlg = MatrixSettingsDialog({}, out, scope='quantities')
        offered = [dlg._classifier_group.role_combo.itemData(i) for i in
                   range(dlg._classifier_group.role_combo.count())]
        assert cv.ROLE_SERIES not in offered

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
