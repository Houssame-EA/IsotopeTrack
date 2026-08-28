# -*- coding: utf-8 -*-
"""Tests for parameterised dimensionality reduction in results/cluster/tools.py.

t-SNE's perplexity and UMAP's n_neighbors used to be hard-coded, which meant the
sweep could compare algorithms but never the embedding they clustered. These
tests pin the grid expansion, the clamping that keeps a badly-sized value from
voiding a pipeline, and — most importantly — that a reduction named without
parameters still behaves exactly as it did before.

The estimators themselves are only exercised on tiny matrices: what is being
tested is the plumbing and the guards, not scikit-learn.
"""
import numpy as np
import pytest

from results.cluster import tools


# --------------------------------------------------------------------------- #
# grid expansion
# --------------------------------------------------------------------------- #
class TestDRParamGrid:
    def test_none_has_a_single_empty_combination(self):
        assert tools.build_dr_param_grid('None', {}) == [{}]

    def test_unknown_reduction_degrades_to_one_combination(self):
        assert tools.build_dr_param_grid('Nope', {}) == [{}]

    def test_defaults_produce_exactly_one_combination(self):
        grid = tools.build_dr_param_grid('t-SNE', {})
        assert len(grid) == 1
        assert grid[0]['perplexity'] == 30.0
        assert grid[0]['n_components'] == 3

    def test_cartesian_product_over_selected_values(self):
        grid = tools.build_dr_param_grid(
            't-SNE', {'perplexity': [5, 30, 50], 'init': ['pca', 'random']})
        assert len(grid) == 6
        assert {g['perplexity'] for g in grid} == {5, 30, 50}

    def test_empty_value_list_falls_back_to_the_default(self):
        grid = tools.build_dr_param_grid('UMAP', {'n_neighbors': []})
        assert grid[0]['n_neighbors'] == 15


class TestNormalizeDRSelections:
    def test_plain_name_list_still_works(self):
        out = tools.normalize_dr_selections(['None', 'PCA'])
        assert out == {'None': {}, 'PCA': {}}

    def test_selections_take_precedence(self):
        out = tools.normalize_dr_selections(
            ['t-SNE'], {'t-SNE': {'perplexity': [5]}})
        assert out['t-SNE'] == {'perplexity': [5]}

    def test_both_sources_are_merged(self):
        out = tools.normalize_dr_selections(['None'], {'PCA': {}})
        assert set(out) == {'None', 'PCA'}

    def test_neither_source_gives_nothing(self):
        assert tools.normalize_dr_selections(None, None) == {}


class TestExpandPreCombos:
    def test_one_tuple_per_parameter_combination(self):
        dr_map = tools.normalize_dr_selections(
            None, {'None': {}, 't-SNE': {'perplexity': [5, 30]}})
        combos = tools.expand_pre_combos(['Counts'], ['None', 'CLR'], dr_map)
        assert len(combos) == 2 * (1 + 2)
        assert all(len(c) == 4 for c in combos)

    def test_reduction_free_pipelines_carry_empty_params(self):
        dr_map = tools.normalize_dr_selections(['None'])
        (combo,) = tools.expand_pre_combos(['Counts'], ['None'], dr_map)
        assert combo == ('Counts', 'None', 'None', {})

    def test_count_combinations_scales_with_the_reduction_grid(self):
        dr_map = tools.normalize_dr_selections(
            None, {'PCA': {'whiten': ['off', 'on']}})
        combos = tools.expand_pre_combos(['Counts'], ['None'], dr_map)
        n = tools.count_combinations(combos, {'K-Means': {'k': [2, 3]}})
        assert n == 4  # 2 whiten values x 2 K values


# --------------------------------------------------------------------------- #
# parameter resolution and clamping
# --------------------------------------------------------------------------- #
class TestNComponents:
    def test_all_defers_to_reduction_components(self):
        assert tools._n_components_value('all', 'PCA', 8, 100) == 8

    def test_all_is_capped_by_the_sample_count(self):
        assert tools._n_components_value('all', 'PCA', 8, 3) == 3

    def test_explicit_value_is_clamped_to_the_features_available(self):
        assert tools._n_components_value('10', 'PCA', 4, 100) == 4

    def test_tsne_is_capped_at_three_components(self):
        assert tools._n_components_value('10', 't-SNE', 8, 100) == tools.EMBED_DIMS

    def test_fraction_passes_through_for_pca_as_a_variance_ratio(self):
        assert tools._n_components_value('0.95', 'PCA', 8, 100) == 0.95

    def test_fraction_is_not_passed_through_for_umap(self):
        """UMAP has no variance-ratio mode, so 0.95 would be a fatal
        n_components rather than a share of the variance."""
        assert tools._n_components_value('0.95', 'UMAP', 8, 100) == 1

    def test_unparseable_value_falls_back_to_the_default(self):
        assert tools._n_components_value('???', 'PCA', 6, 100) == 6

    def test_none_reduction_has_no_components(self):
        assert tools._n_components_value('all', 'None', 6, 100) is None


class TestLearningRate:
    @pytest.mark.parametrize('raw', ['auto', '', None, 'nonsense'])
    def test_non_numeric_becomes_auto(self, raw):
        assert tools._learning_rate_value(raw) == 'auto'

    def test_numeric_string_becomes_a_float(self):
        assert tools._learning_rate_value('200') == 200.0


class TestSupportedKwargs:
    def test_unknown_keyword_is_dropped(self):
        class Est:
            def __init__(self, a=1, b=2):
                pass
        assert tools._supported_kwargs(Est, {'a': 1, 'zzz': 9}) == {'a': 1}

    def test_var_keyword_estimators_keep_everything(self):
        class Est:
            def __init__(self, **kw):
                pass
        assert tools._supported_kwargs(Est, {'zzz': 9}) == {'zzz': 9}


# --------------------------------------------------------------------------- #
# apply_reduction
# --------------------------------------------------------------------------- #
@pytest.fixture
def blobs():
    rng = np.random.default_rng(0)
    return np.vstack([rng.normal(0, 1, (30, 5)), rng.normal(6, 1, (30, 5))])


class TestApplyReduction:
    def test_none_returns_the_matrix_untouched(self, blobs):
        out = tools.apply_reduction('None', blobs, {})
        assert out is blobs

    def test_pca_default_keeps_every_component(self, blobs):
        out = tools.apply_reduction('PCA', blobs, {'n_components': 'all'})
        assert out.shape == blobs.shape

    def test_pca_respects_an_explicit_component_count(self, blobs):
        out = tools.apply_reduction('PCA', blobs, {'n_components': '2'})
        assert out.shape == (blobs.shape[0], 2)

    def test_pca_whiten_changes_the_embedding(self, blobs):
        plain = tools.apply_reduction('PCA', blobs, {'whiten': 'off'})
        white = tools.apply_reduction('PCA', blobs, {'whiten': 'on'})
        assert not np.allclose(plain, white)

    def test_pca_survives_an_invalid_solver_choice(self, blobs):
        """'arpack' rejects n_components == n_features, so the fallback to the
        default solver must catch it."""
        out = tools.apply_reduction(
            'PCA', blobs, {'n_components': 'all', 'svd_solver': 'arpack'})
        assert out.shape[0] == blobs.shape[0]

    def test_tsne_perplexity_is_clamped_to_the_sample_count(self):
        """A perplexity of 400 on 10 points would raise inside scikit-learn."""
        rng = np.random.default_rng(1)
        small = rng.normal(0, 1, (10, 4))
        out = tools.apply_reduction('t-SNE', small, {'perplexity': 400.0})
        assert out.shape == (10, 3)

    def test_tsne_perplexity_actually_changes_the_embedding(self, blobs):
        a = tools.apply_reduction('t-SNE', blobs,
                                  {'perplexity': 5.0, 'random_state': 0})
        b = tools.apply_reduction('t-SNE', blobs,
                                  {'perplexity': 19.0, 'random_state': 0})
        assert not np.allclose(a, b)

    def test_tsne_seed_is_honoured(self, blobs):
        a = tools.apply_reduction('t-SNE', blobs, {'random_state': 7})
        b = tools.apply_reduction('t-SNE', blobs, {'random_state': 7})
        assert np.allclose(a, b)

    def test_tsne_non_euclidean_metric_drops_the_pca_init(self, blobs):
        """A PCA init is undefined outside the metric it was computed in, and
        scikit-learn raises rather than coping, so the guard matters."""
        out = tools.apply_reduction(
            't-SNE', blobs, {'metric': 'cosine', 'init': 'pca'})
        assert out.shape == (blobs.shape[0], 3)

    def test_tsne_respects_n_components(self, blobs):
        out = tools.apply_reduction('t-SNE', blobs, {'n_components': 2})
        assert out.shape == (blobs.shape[0], 2)

    @pytest.mark.skipif(not tools._UMAP_OK, reason="UMAP not installed")
    def test_umap_neighbors_are_clamped(self):
        rng = np.random.default_rng(2)
        small = rng.normal(0, 1, (8, 4))
        out = tools.apply_reduction('UMAP', small, {'n_neighbors': 500})
        assert out.shape[0] == 8

    @pytest.mark.skipif(not tools._UMAP_OK, reason="UMAP not installed")
    def test_umap_min_dist_cannot_exceed_spread(self, blobs):
        out = tools.apply_reduction(
            'UMAP', blobs, {'min_dist': 0.9, 'spread': 0.5})
        assert out.shape[0] == blobs.shape[0]

    def test_umap_without_the_dependency_is_a_no_op(self, blobs, monkeypatch):
        """umap is optional, so a missing install must degrade to "no
        reduction" rather than raise out of the clustering worker."""
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == 'umap':
                raise ImportError('no umap')
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, '__import__', fake_import)
        assert tools.apply_reduction('UMAP', blobs, {}) is blobs


# --------------------------------------------------------------------------- #
# caching
# --------------------------------------------------------------------------- #
def _particles(n, seed=0):
    rng = np.random.default_rng(seed)
    return [{'elements': {'107Ag': float(v), '197Au': float(v) * 0.5}}
            for v in rng.uniform(1, 100, n)]


class TestPreprocessorCache:
    def test_different_params_are_cached_separately(self):
        pre = tools.Preprocessor(_particles(40), ['107Ag', '197Au'])
        a = pre.matrix('Counts', 'None', 'PCA', {'whiten': 'off'})
        b = pre.matrix('Counts', 'None', 'PCA', {'whiten': 'on'})
        assert len(pre._reduced_cache) == 2
        assert not np.allclose(a, b)

    def test_same_params_hit_the_cache(self):
        pre = tools.Preprocessor(_particles(40), ['107Ag', '197Au'])
        a = pre.matrix('Counts', 'None', 'PCA', {'whiten': 'off'})
        b = pre.matrix('Counts', 'None', 'PCA', {'whiten': 'off'})
        assert a is b
        assert len(pre._reduced_cache) == 1

    def test_param_order_does_not_split_the_cache(self):
        pre = tools.Preprocessor(_particles(40), ['107Ag', '197Au'])
        pre.matrix('Counts', 'None', 'PCA', {'whiten': 'off', 'svd_solver': 'auto'})
        pre.matrix('Counts', 'None', 'PCA', {'svd_solver': 'auto', 'whiten': 'off'})
        assert len(pre._reduced_cache) == 1

    def test_omitting_params_matches_the_old_call_shape(self):
        pre = tools.Preprocessor(_particles(40), ['107Ag', '197Au'])
        out = pre.matrix('Counts', 'None', 'None')
        assert out.shape[0] == 40


# --------------------------------------------------------------------------- #
# result-row helpers
# --------------------------------------------------------------------------- #
class TestParamStrings:
    def test_empty_params_render_as_nothing(self):
        assert tools._dr_params_str('None', {}) == ''

    def test_params_render_in_spec_order(self):
        txt = tools._dr_params_str('UMAP', {'min_dist': 0.1, 'n_neighbors': 5})
        assert txt == 'n_neighbors=5, min_dist=0.1'

    def test_best_line_suffix_is_bracketed(self):
        assert tools._best_dr_suffix(
            {'dim_reduction': 't-SNE',
             'dr_params_str': 'perplexity=50'}) == ' [perplexity=50]'

    def test_best_line_suffix_empty_without_a_reduction(self):
        assert tools._best_dr_suffix(
            {'dim_reduction': 'None', 'dr_params': {}}) == ''

    def test_non_default_params_are_detected(self):
        assert tools._non_default_dr_params(
            't-SNE', {'perplexity': 50.0}) == {'perplexity': 50.0}

    def test_default_params_report_nothing_to_warn_about(self):
        grid = tools.build_dr_param_grid('t-SNE', {})
        assert tools._non_default_dr_params('t-SNE', grid[0]) == {}


# --------------------------------------------------------------------------- #
# end to end
# --------------------------------------------------------------------------- #
class TestSweepIntegration:
    def _kwargs(self, **over):
        base = dict(
            particle_data=_particles(60),
            elements=['107Ag', '197Au'],
            components=tools.parse_components("107Ag+197Au"),
            data_types=['Counts'],
            scalings=['None'],
            algo_selections={'K-Means': {'k': [2]}},
            internal_metrics=[],
            external_metrics=['ARI'],
            min_clusters=1,
            max_clusters=100,
        )
        base.update(over)
        return base

    def test_each_reduction_parameter_becomes_its_own_row(self):
        out = tools.run_sweep(**self._kwargs(
            dr_selections={'PCA': {'whiten': ['off', 'on']}}))
        assert len(out['results']) == 2
        assert {r['dr_params_str'] for r in out['results']} == {
            tools._dr_params_str('PCA', dict(r['dr_params']))
            for r in out['results']}
        assert len({r['dr_params']['whiten'] for r in out['results']}) == 2

    def test_legacy_dim_reductions_list_still_runs(self):
        out = tools.run_sweep(**self._kwargs(dim_reductions=['None']))
        assert len(out['results']) == 1
        assert out['results'][0]['dr_params'] == {}
        assert out['results'][0]['dr_params_str'] == ''

    def test_rows_carry_the_parameters_that_produced_them(self):
        out = tools.run_sweep(**self._kwargs(
            dr_selections={'PCA': {'n_components': ['2']}}))
        row = out['results'][0]
        assert row['dr_params']['n_components'] == '2'
        assert 'n_components=2' in row['dr_params_str']
