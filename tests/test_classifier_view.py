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
        dlg.close()
