# -*- coding: utf-8 -*-
"""Tests for the AI assistant's particle table and spICP-ToF-MS analyses.

Every analysis is checked against a synthetic stream where the answer is
known (:mod:`results.ai.synthetic`): Spiked_C has larger Ti particles, Ce
and La form one particle type, Ti and Fe only meet by chance, River_B has
an Fe burst between 20 and 22 s, and Ag+Au alloy particles exist only in
Spiked_C.
"""
import numpy as np
import pytest

from results.ai import analysis as A
from results.ai.data import Dataset, particle_frame, resolve_quantity
from results.ai.synthetic import make_dataset


@pytest.fixture(scope='module')
def planted():
    """The synthetic dataset, its truth and its detection limits."""
    dc, truth, limits = make_dataset(seed=11)
    ds = Dataset(dc)
    ds.set_limits(limits)
    return ds, truth


class TestParticleTable:
    """The flat particle table."""

    def test_columns_and_nan_for_missing(self):
        """Undetected elements are NaN and combos are sorted."""
        ps = [{'elements': {'56Fe': 10, '27Al': 0}, 'element_mass_fg': {'56Fe': 1.0},
               'start_time': 0.0, 'end_time': 0.001, 'source_sample': 'S'},
              {'elements': {'27Al': 5, '56Fe': 3}, 'element_mass_fg': {'27Al': 2.0, '56Fe': 0.5},
               'start_time': 1.0, 'end_time': 1.0005, 'source_sample': 'S'}]
        df = particle_frame(ps)
        assert np.isnan(df.loc[0, 'counts_27Al'])
        assert df.loc[1, 'combo'] == '27Al + 56Fe'
        assert list(df['n_elements']) == [1, 2]
        assert df.attrs['elements'][0] == '56Fe'
        assert df.loc[1, 'duration_ms'] == pytest.approx(0.5)

    def test_quantity_aliases(self):
        """Loose quantity names resolve."""
        assert resolve_quantity('size') == 'diameter_nm'
        assert resolve_quantity('Mass') == 'mass_fg'
        with pytest.raises(KeyError):
            resolve_quantity('colour')

    def test_element_resolution(self, planted):
        """Symbols, reversed labels and case are accepted."""
        ds, _ = planted
        assert ds.resolve_element('ti') == '48Ti'
        assert ds.resolve_element('Fe-56') == '56Fe'
        with pytest.raises(KeyError):
            ds.resolve_element('Pu')

    def test_runs_and_lod(self, planted):
        """Run spans come from particle times; limits are looked up per sample."""
        ds, truth = planted
        runs = ds.runs()
        assert set(runs['run']) == set(truth.samples)
        assert (runs['span_s'] > 55).all()
        assert ds.lod('Ti', 'mass_fg') == pytest.approx(truth.lod_mass_fg['48Ti'])

    def test_safe_context_hides_window(self):
        """The context given to generated code has no main window."""
        ds = Dataset({'particle_data': [], 'parent_window': object(), 'type': 'sample_data'})
        assert 'parent_window' not in ds.safe_context()


class TestAnalyses:
    """Each analysis finds what was planted, and only that."""

    def test_compare_samples_finds_larger_ti(self, planted):
        """Spiked_C stands out with a significant test."""
        ds, _ = planted
        out = A.compare_samples(ds, 'Ti')
        top = out.sort_values('median').iloc[-1]
        assert top['sample'] == 'Spiked_C'
        assert top['p_vs_rest'] < 1e-6
        assert 'Kruskal-Wallis' in out.attrs['note']

    def test_coincidence_separates_real_from_chance(self, planted):
        """Ce+La is far above chance; Ti+Fe is not."""
        ds, _ = planted
        cela = A.coincidence(ds, 'Ce', 'La').iloc[-1]
        tife = A.coincidence(ds, 'Ti', 'Fe').iloc[-1]
        assert cela['ratio'] > 50 and cela['p'] < 1e-10
        assert 0.6 < tife['ratio'] < 1.5 and tife['p'] > 0.01

    def test_co_occurrence_verdicts(self, planted):
        """Planted associations are found and chance pairs are not."""
        ds, _ = planted
        out = A.co_occurrence(ds)
        verdict = {(r.a, r.b): r.verdict for r in out.itertuples()}
        assert 'real association' in verdict[('140Ce', '139La')]
        assert 'real association' in verdict[('107Ag', '197Au')]
        assert verdict[('48Ti', '56Fe')] == 'explained by chance coincidence'

    def test_time_bursts_finds_the_planted_burst(self, planted):
        """The Fe burst is found in River_B, between 20 and 22 s."""
        ds, truth = planted
        out = A.time_bursts(ds, 'Fe')
        sample, t0, t1 = truth.burst
        assert len(out) and set(out['run']) == {sample}
        assert out['t_from'].min() >= t0 - 1 and out['t_to'].max() <= t1 + 1

    def test_enrichment_finds_the_alloy_sample(self, planted):
        """Ag+Au is the most over-represented combination, in Spiked_C."""
        ds, truth = planted
        out = A.combination_enrichment(ds)
        top = out.iloc[0]
        assert top['combo'] == '107Ag + 197Au' and top['sample'] == truth.alloy_sample

    def test_size_distribution_flags_truncation(self):
        """A distribution peaking at the detection limit is flagged."""
        dc, truth, limits = make_dataset(seed=3, scale=0.5)
        ds = Dataset(dc)
        limits['48Ti']['diameter_nm'] = {s: 50.0 for s in truth.samples}
        ds.set_limits(limits)
        out = A.size_distribution(ds, 'Ti')
        flags = dict(zip(out['sample'], out['truncated']))
        assert flags['River_A'] and not flags['Spiked_C']
        heights = dict(zip(out['sample'], out['height_at_lod_pct']))
        assert heights['River_A'] > heights['Spiked_C']

    def test_near_detection_limit(self, planted):
        """Elements and samples are ranked by how close they sit to the LOD."""
        ds, _ = planted
        out = A.near_detection_limit(ds)
        assert {'element', 'sample', 'pct_near_lod'} <= set(out.columns)
        assert out['pct_near_lod'].is_monotonic_decreasing

    def test_outliers_are_extreme(self, planted):
        """Every reported outlier is beyond the threshold."""
        ds, _ = planted
        out = A.find_outliers(ds, 'mass_fg', threshold=3)
        assert (out['robust_z'].abs() >= 3).all()

    def test_long_format(self, planted):
        """One row per particle and detected element."""
        ds, _ = planted
        out = A.long_format(ds, 'mass', ['Ce', 'La'])
        assert set(out['element']) == {'140Ce', '139La'}
        assert len(out) == ds.df['counts_140Ce'].notna().sum() + ds.df['counts_139La'].notna().sum()

    def test_cluster_particles(self, planted):
        """Clustering returns one label per particle and a summary."""
        ds, _ = planted
        summary, labels = A.cluster_particles(ds, k=4)
        assert len(labels) == len(ds.df)
        assert summary['n'].sum() == (labels >= 0).sum()
        with pytest.raises(ValueError):
            A.cluster_particles(ds, algorithm='Nonsense')

    def test_holm(self):
        """Holm adjustment is monotone and capped at 1."""
        adj = A.holm([0.01, 0.04, 0.03, float('nan')])
        assert adj[0] == pytest.approx(0.03)
        assert adj[2] == pytest.approx(0.06) and adj[1] == pytest.approx(0.06)
        assert np.isnan(adj[3])
