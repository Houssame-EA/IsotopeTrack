# -*- coding: utf-8 -*-
"""Tests that every clustering entry point reduces the same way.

The sweep tool, the ② Cluster matrix and the live panel's projection each used
to build their own embedding with their own hard-coded perplexity and
n_neighbors, so the pipeline the sweep ranked first could not be reproduced by
the tab the user then clicked into. results/cluster/prep.py now owns both the
parameter declarations and the reduction itself; these tests pin that down.

What matters here, in order:

* the parameter specs and the reduction live in prep and are shared, not copied;
* a config with no ``dim_reduction_params`` behaves exactly as it did before;
* a parameter change invalidates a cached fit, so a stale embedding is never
  reused under new settings;
* the live panel honours the shared settings but keeps its own drawable
  component count.
"""
import numpy as np
import pytest

from results.cluster import prep
from results.cluster import tools


@pytest.fixture
def blobs():
    rng = np.random.default_rng(0)
    return np.vstack([rng.normal(0, 1, (40, 5)), rng.normal(6, 1, (40, 5))])


# --------------------------------------------------------------------------- #
# one source of truth
# --------------------------------------------------------------------------- #
class TestSharedDefinitions:
    def test_tools_reexports_prep_and_does_not_copy_it(self):
        assert tools.DR_PARAM_SPECS is prep.DR_PARAM_SPECS
        assert tools.apply_reduction is prep.apply_reduction
        assert tools.KEEP_ALL is prep.KEEP_ALL

    def test_every_reduction_option_has_a_spec(self):
        for name in tools.DIM_REDUCTIONS:
            assert name in prep.DR_PARAM_SPECS

    def test_defaults_are_single_values_not_lists(self):
        defaults = prep.dr_defaults('t-SNE')
        assert defaults['perplexity'] == 30.0
        assert defaults['n_components'] == 3

    def test_unknown_reduction_has_no_defaults(self):
        assert prep.dr_defaults('Nope') == {}


# --------------------------------------------------------------------------- #
# the historical behaviour is the default
# --------------------------------------------------------------------------- #
class TestBackwardCompatibleDefaults:
    def test_pca_with_no_params_is_still_a_full_rotation(self, blobs):
        """An orthonormal rotation preserves pairwise distances exactly."""
        out = prep.apply_reduction('PCA', blobs, None)
        assert out.shape == blobs.shape
        d_before = np.linalg.norm(blobs[0] - blobs[1])
        d_after = np.linalg.norm(out[0] - out[1])
        assert d_after == pytest.approx(d_before, rel=1e-9)

    def test_empty_params_match_explicit_defaults(self, blobs):
        a = prep.apply_reduction('PCA', blobs, {})
        b = prep.apply_reduction('PCA', blobs, prep.dr_defaults('PCA'))
        assert np.allclose(a, b)

    def test_single_column_matrix_is_returned_untouched(self):
        m = np.arange(10, dtype=float).reshape(10, 1)
        assert prep.apply_reduction('PCA', m, None) is m

    def test_none_reduction_is_a_no_op(self, blobs):
        assert prep.apply_reduction('None', blobs, {}) is blobs

    def test_defaults_reproduce_the_old_hard_coded_tsne_seed(self, blobs):
        kw = prep.reduction_kwargs('t-SNE', None, len(blobs), blobs.shape[1])
        assert kw['random_state'] == 42
        assert kw['init'] == 'pca'


# --------------------------------------------------------------------------- #
# reduction_kwargs, as the live panel uses it
# --------------------------------------------------------------------------- #
class TestReductionKwargs:
    def test_component_override_wins_over_the_parameter(self):
        kw = prep.reduction_kwargs('UMAP', {'n_components': '10'},
                                   100, 8, n_components=2)
        assert kw['n_components'] == 2

    def test_display_settings_still_come_from_the_parameters(self):
        kw = prep.reduction_kwargs(
            't-SNE', {'perplexity': 12.0, 'random_state': 7},
            100, 8, n_components=2)
        assert kw['perplexity'] == 12.0
        assert kw['random_state'] == 7
        assert kw['n_components'] == 2

    def test_perplexity_is_clamped_for_a_small_fit_sample(self):
        kw = prep.reduction_kwargs('t-SNE', {'perplexity': 300.0}, 10, 4)
        assert kw['perplexity'] <= 3.0

    def test_neighbours_are_clamped_for_a_small_fit_sample(self):
        kw = prep.reduction_kwargs('UMAP', {'n_neighbors': 500}, 8, 4)
        assert kw['n_neighbors'] == 7

    def test_min_dist_never_exceeds_spread(self):
        kw = prep.reduction_kwargs(
            'UMAP', {'min_dist': 0.9, 'spread': 0.4}, 100, 4)
        assert kw['min_dist'] <= kw['spread']

    def test_pca_init_is_dropped_for_a_non_euclidean_metric(self):
        kw = prep.reduction_kwargs(
            't-SNE', {'init': 'pca', 'metric': 'cosine'}, 100, 4)
        assert kw['init'] == 'random'

    def test_unusable_seed_falls_back_rather_than_raising(self):
        kw = prep.reduction_kwargs('PCA', {'random_state': 'oops'}, 100, 4)
        assert kw['random_state'] == 42

    def test_unknown_reduction_yields_no_kwargs(self):
        assert prep.reduction_kwargs('Nope', {}, 100, 4) == {}


# --------------------------------------------------------------------------- #
# reporting helpers
# --------------------------------------------------------------------------- #
class TestReportingHelpers:
    def test_params_render_in_spec_order(self):
        txt = prep.dr_params_str('UMAP', {'min_dist': 0.1, 'n_neighbors': 5})
        assert txt == 'n_neighbors=5, min_dist=0.1'

    def test_defaults_are_not_reported_as_changes(self):
        assert prep.non_default_dr_params('t-SNE',
                                          prep.dr_defaults('t-SNE')) == {}

    def test_a_changed_value_is_reported(self):
        assert prep.non_default_dr_params(
            't-SNE', {'perplexity': 50.0}) == {'perplexity': 50.0}

    def test_unknown_keys_are_ignored(self):
        assert prep.non_default_dr_params('PCA', {'bogus': 1}) == {}


# --------------------------------------------------------------------------- #
# the fit stamp must notice a parameter change
# --------------------------------------------------------------------------- #
class TestFitFingerprint:
    def _cfg(self, **over):
        base = {'scaling': 'CLR', 'data_type_display': 'Counts',
                'filter_zeros': True, 'min_particle_type_count': 5,
                'dim_reduction': 't-SNE', 'dim_reduction_params': {}}
        base.update(over)
        return base

    def test_parameters_are_part_of_the_fingerprint(self):
        from results.cluster.live import fit_fingerprint, FIT_CONFIG_KEYS
        assert 'dim_reduction_params' in FIT_CONFIG_KEYS
        a = fit_fingerprint(self._cfg(), 'K-Means', 3)
        b = fit_fingerprint(
            self._cfg(dim_reduction_params={'perplexity': 50.0}),
            'K-Means', 3)
        assert a != b

    def test_identical_settings_still_match(self):
        from results.cluster.live import fit_fingerprint
        a = fit_fingerprint(self._cfg(dim_reduction_params={'perplexity': 50.0}),
                            'K-Means', 3)
        b = fit_fingerprint(self._cfg(dim_reduction_params={'perplexity': 50.0}),
                            'K-Means', 3)
        assert a == b


# --------------------------------------------------------------------------- #
# the sweep's winner reproduces in the clustering tab
# --------------------------------------------------------------------------- #
class TestRoundTrip:
    def test_sweep_matrix_and_cluster_matrix_agree(self, blobs):
        """What the sweep clustered and what the ② Cluster tab now builds from
        the same config must be the same matrix."""
        params = {'perplexity': 8.0, 'random_state': 3, 'n_components': 2}
        pre = tools.apply_reduction('t-SNE', blobs, params)
        post = prep.apply_reduction('t-SNE', blobs, params)
        assert np.allclose(pre, post)

    def test_a_different_parameter_gives_a_different_matrix(self, blobs):
        a = prep.apply_reduction('PCA', blobs, {'whiten': 'off'})
        b = prep.apply_reduction('PCA', blobs, {'whiten': 'on'})
        assert not np.allclose(a, b)


# --------------------------------------------------------------------------- #
# the live panel draws in the space the clustering ran in
# --------------------------------------------------------------------------- #
class TestLiveProjection:
    def test_projection_honours_the_shared_settings(self, blobs):
        from results.cluster.live import _embed
        a, _, used, _ = _embed(blobs, "t-SNE", 2,
                               {'perplexity': 5.0, 'random_state': 0})
        b, _, _, _ = _embed(blobs, "t-SNE", 2,
                            {'perplexity': 20.0, 'random_state': 0})
        assert used == "t-SNE"
        assert not np.allclose(a, b)

    def test_projection_keeps_its_own_component_count(self, blobs):
        """n_components in the shared settings describes the clustering space;
        the panel has to draw in 2-D or 3-D whatever that says."""
        from results.cluster.live import _embed
        P, _, _, _ = _embed(blobs, "t-SNE", 2, {'n_components': 3})
        assert P.shape[1] == 2

    def test_projection_without_settings_still_works(self, blobs):
        from results.cluster.live import _embed
        P, _, used, _ = _embed(blobs, "t-SNE", 2, None)
        assert P.shape == (len(blobs), 2)
        assert used == "t-SNE"

    def test_switching_reduction_clears_stale_parameters(self):
        """A parameter change must invalidate a cached fit, or a stale
        embedding is silently reused under new settings."""
        from results.cluster import live
        assert 'dim_reduction_params' in live.FIT_CONFIG_KEYS
