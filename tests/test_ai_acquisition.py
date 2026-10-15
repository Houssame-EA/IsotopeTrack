# -*- coding: utf-8 -*-
"""Tests for the raw signal and per-sample results handed to the AI assistant.

A small fake main window holds two runs with known traces, a known
calibration and known detections, so every number in ``sample_summary()``
can be checked by hand against the summary export's formulas.
"""
import math

import numpy as np
import pandas as pd
import pytest

from results.ai.acquisition import StaticAcquisition, WindowAcquisition, match_label
from results.ai.data import Dataset
from results.ai.prompts import build_system_prompt
from results.ai.sandbox import execute

FE = 55.9349
TI = 47.9479
N = 10000
DWELL_MS = 0.1


class _Table:
    """Periodic table stand-in with element densities."""

    def get_density_by_element(self, symbol):
        """Return the density of Fe and Ti in g/cm3."""
        return {'Fe': 7.874, 'Ti': 4.506}.get(symbol)


class _Compounds:
    """Mass fraction service stand-in: Fe is set as Fe2O3 in Lake_A only."""

    def get_mass_fraction(self, element_key, sample_name=None):
        """Return 0.699 for Fe in Lake_A and 1 otherwise."""
        return 0.699 if element_key.startswith('Fe') and sample_name == 'Lake_A' else 1.0

    def get_element_density(self, element_key, sample_name=None):
        """Return the Fe2O3 density for Fe in Lake_A, else nothing."""
        return 5.24 if element_key.startswith('Fe') and sample_name == 'Lake_A' else None


class FakeWindow:
    """The main window stores the assistant reads, with known values."""

    def __init__(self):
        """Fill two runs: Lake_A is calibrated for Fe, Lake_B is not."""
        rng = np.random.default_rng(3)
        t = np.arange(N) * DWELL_MS / 1000.0
        fe_a = rng.poisson(2.0, N).astype(float)
        fe_a[5000] = 400.0
        self.data_by_sample = {
            'Lake_A': {FE: fe_a, TI: rng.poisson(0.5, N).astype(float)},
            'Lake_B': {FE: rng.poisson(1.0, N).astype(float)},
        }
        self.time_array_by_sample = {'Lake_A': t, 'Lake_B': t.copy()}
        self.selected_isotopes = {'Fe': [FE], 'Ti': [TI]}
        self.sample_dwell_times = {'Lake_A': DWELL_MS, 'Lake_B': DWELL_MS}
        self.sample_dilutions = {'Lake_A': 10.0}
        self.average_transport_rate = 0.1
        self.calibration_results = {'Ionic Calibration': {
            f'Fe-{FE:.4f}': {'zero': {'slope': 2000.0}, 'simple': {'slope': 1000.0}}}}
        self.isotope_method_preferences = {f'Fe-{FE:.4f}': 'Simple linear'}
        self.element_thresholds = {'Lake_A': {f'Fe-{FE:.4f}': {
            'background': 2.0, 'LOD_counts': 12.0, 'LOD_MDL': 10.0}}}
        self.element_limits = {'Lake_A': {f'Fe-{FE:.4f}': {
            'MDL': 1.0, 'MQL': 3.33, 'SDL': 62.5, 'SQL': 93.4,
            'background_ppt': 15.0, 'background_sd_ppt': 3.0}}}
        self.sample_detected_peaks = {
            'Lake_A': {('Fe', FE): [{'total_counts': 100.0}, {'total_counts': 300.0}],
                       ('Ti', TI): [{'total_counts': 50.0}]},
            'Lake_B': {('Fe', FE): [{'total_counts': 80.0}]},
        }
        self.periodic_table_info = _Table()
        self.mass_fraction_service = _Compounds()

    def get_formatted_label(self, element_key):
        """Return labels such as ``56Fe``."""
        el, mass = element_key.split('-')
        return f"{round(float(mass))}{el}"

    def find_closest_isotope(self, target_mass, data=None, tolerance=None):
        """Return the channel within 0.1 amu of *target_mass*."""
        best = min(data, key=lambda m: abs(m - target_mass)) if data else None
        return best if best is not None and abs(best - target_mass) < 0.1 else None

    def mass_to_diameter(self, mass_fg, density):
        """Sphere diameter in nm, as the main window computes it."""
        if mass_fg <= 0 or density <= 0:
            return float('nan')
        return ((6 * mass_fg * 1e-15) / (np.pi * density)) ** (1 / 3) * 1e7


def _particle(sample, run, t):
    """One Fe particle as the canvas sends it."""
    return {'start_time': t, 'end_time': t + 0.0005, 'source_sample': sample,
            'original_sample': run, 'elements': {'56Fe': 100.0}, 'element_mass_fg': {'56Fe': 10.0}}


@pytest.fixture
def window():
    """A fresh fake main window."""
    return FakeWindow()


@pytest.fixture
def single(window):
    """A single-sample dataset connected to the window."""
    dc = {'type': 'sample_data', 'sample_name': 'Lake_A',
          'particle_data': [_particle('Lake_A', 'Lake_A', 0.5)]}
    return Dataset(dc, window)


@pytest.fixture
def pooled(window):
    """Both runs pooled into one sample called Lakes."""
    dc = {'type': 'multiple_sample_data', 'sample_names': ['Lakes'],
          'particle_data': [_particle('Lakes', 'Lake_A', 0.5), _particle('Lakes', 'Lake_B', 0.6)]}
    return Dataset(dc, window)


def _row(frame, run, element):
    """Return the summary row of one run and element."""
    hit = frame[(frame['run'] == run) & (frame['element'] == element)]
    assert len(hit) == 1
    return hit.iloc[0]


class TestSummary:
    """sample_summary() against the summary export's formulas."""

    def test_calibrated_element(self, single, window):
        """Every number of a calibrated element matches a hand calculation."""
        row = _row(single.acquisition.summary(), 'Lake_A', '56Fe')
        acq_s = (N - 1) * DWELL_MS / 1000.0
        volume = 0.1 * acq_s / 1000.0
        signal = window.data_by_sample['Lake_A'][FE]
        assert row['particles'] == 2
        assert row['volume_ml'] == pytest.approx(volume)
        assert row['particles_per_ml'] == pytest.approx(2 / volume)
        assert row['particles_per_ml_corrected'] == pytest.approx(20 / volume)
        assert row['mean_mass_fg'] == pytest.approx(20.0)
        assert row['median_mass_fg'] == pytest.approx(20.0)
        assert row['total_mass_fg'] == pytest.approx(40.0)
        assert row['mass_conc_ug_l'] == pytest.approx(40.0 / volume * 10.0 * 1e-6)
        d = [window.mass_to_diameter(m, 7.874) for m in (10.0, 30.0)]
        assert row['mean_diameter_nm'] == pytest.approx(np.mean(d))
        assert row['mean_signal_counts'] == pytest.approx(signal.mean())
        assert row['signal_sd_counts'] == pytest.approx(signal.std(ddof=1))
        assert row['mean_signal_ppb'] == pytest.approx(signal.mean() / (DWELL_MS / 1000.0) / 1000.0)
        assert row['slope_cps_per_ppb'] == 1000.0
        assert row['calibration_method'] == 'Simple linear'
        assert row['background_counts'] == 2.0
        assert row['background_ppt'] == 15.0
        assert row['background_sd_ppt'] == 3.0
        assert row['threshold_counts'] == 12.0
        assert row['lod_net_counts'] == 10.0
        assert (row['mdl_fg'], row['mql_fg'], row['sdl_nm'], row['sql_nm']) == (1.0, 3.33, 62.5, 93.4)
        assert row['transport_rate_ul_s'] == 0.1
        assert row['dwell_ms'] == DWELL_MS
        assert row['dilution'] == 10.0
        assert row['acquisition_s'] == pytest.approx(acq_s)

    def test_uncalibrated_element_is_nan_not_zero(self, single):
        """Without an ionic calibration, masses and ppb stay NaN; counts still count."""
        row = _row(single.acquisition.summary(), 'Lake_A', '48Ti')
        assert row['particles'] == 1
        assert row['particles_per_ml'] > 0
        for c in ('mean_mass_fg', 'mass_conc_ug_l', 'mean_signal_ppb', 'slope_cps_per_ppb',
                  'background_ppt', 'mdl_fg'):
            assert math.isnan(row[c]), c

    def test_single_sample_only_its_run(self, single):
        """A single-sample dataset exposes only its own run."""
        frame = single.acquisition.summary()
        assert set(frame['run']) == {'Lake_A'}
        assert set(frame['element']) == {'56Fe', '48Ti'}

    def test_pooled_runs_keep_their_sample(self, pooled):
        """Pooled runs report their own numbers under the pooled sample name."""
        frame = pooled.acquisition.summary()
        assert set(frame['run']) == {'Lake_A', 'Lake_B'}
        assert set(frame['sample']) == {'Lakes'}
        assert _row(frame, 'Lake_B', '56Fe')['dilution'] == 1.0

    def test_no_transport_rate(self, window, single):
        """Without a transport rate, concentrations are NaN, not infinite."""
        window.average_transport_rate = 0
        row = _row(single.acquisition.summary(), 'Lake_A', '56Fe')
        assert math.isnan(row['particles_per_ml']) and math.isnan(row['mass_conc_ug_l'])
        assert row['particles'] == 2


class TestCompound:
    """Element and compound-corrected particle values side by side."""

    def test_summary_has_both(self, single, window):
        """With Fe2O3 set, particle masses are element masses / 0.699 at the oxide density."""
        row = _row(single.acquisition.summary(), 'Lake_A', '56Fe')
        assert row['mass_fraction'] == pytest.approx(0.699)
        assert row['mean_mass_fg'] == pytest.approx(20.0)
        assert row['particle_mean_mass_fg'] == pytest.approx(20.0 / 0.699)
        assert row['particle_total_mass_fg'] == pytest.approx(40.0 / 0.699)
        assert row['particle_mass_conc_ug_l'] == pytest.approx(row['mass_conc_ug_l'] / 0.699)
        d = [window.mass_to_diameter(m / 0.699, 5.24) for m in (10.0, 30.0)]
        assert row['particle_mean_diameter_nm'] == pytest.approx(np.mean(d))

    def test_pure_element_values_match(self, pooled):
        """Without a compound, particle values equal element values."""
        row = _row(pooled.acquisition.summary(), 'Lake_B', '56Fe')
        assert row['mass_fraction'] == 1.0
        assert row['particle_mean_mass_fg'] == pytest.approx(row['mean_mass_fg'])
        assert row['particle_mean_diameter_nm'] == pytest.approx(row['mean_diameter_nm'])

    def test_particle_limits_follow_the_compound(self):
        """lod() on particle mass and diameter is on the corrected scale."""
        rho, frac = 5.24, 0.7
        def d(m, r):
            return ((6 * m * 1e-15) / (np.pi * r)) ** (1 / 3) * 1e7
        ps = []
        for i, m in enumerate((2.0, 5.0, 9.0)):
            ps.append({'start_time': i, 'end_time': i + 0.0005, 'source_sample': 'S',
                       'elements': {'56Fe': 10.0}, 'element_mass_fg': {'56Fe': m},
                       'element_diameter_nm': {'56Fe': d(m, 7.874)},
                       'particle_mass_fg': {'56Fe': m / frac},
                       'particle_diameter_nm': {'56Fe': d(m / frac, rho)}})
        ds = Dataset({'type': 'sample_data', 'sample_name': 'S', 'particle_data': ps})
        ds.set_limits({'56Fe': {'mass_fg': {'S': 1.0}, 'diameter_nm': {'S': d(1.0, 7.874)}}})
        assert ds.lod('Fe', 'mass_fg') == pytest.approx(1.0)
        assert ds.lod('Fe', 'particle_mass_fg') == pytest.approx(1.0 / frac)
        assert ds.lod('Fe', 'particle_diameter_nm') == pytest.approx(d(1.0 / frac, rho))

    def test_particle_columns_filled_for_pure_elements(self, single):
        """Particles without compound values get particle columns equal to the element ones."""
        df = single.df
        assert df['particle_mass_fg_56Fe'].iloc[0] == df['mass_fg_56Fe'].iloc[0]
        assert single.column('particle_mass_fg', 'Fe') == 'particle_mass_fg_56Fe'

    def test_prompt_defaults_to_element_mass(self, single):
        """Element mass is the default; the particle mass is opt-in, and the setting flips it."""
        text = build_system_prompt(single, 16384)
        assert 'Mass first' in text
        assert 'Use the element values by default: mass_fg_<el>' in text
        assert "compare_samples('Ti', 'mass_fg')" in text
        flipped = build_system_prompt(single, 16384, mass_basis='particle')
        assert 'Use the particle (compound-corrected) values by default' in flipped
        assert "compare_samples('Ti', 'particle_mass_fg')" in flipped
        assert '{mq}' not in text + flipped and '{quantity_rule}' not in text + flipped


class TestSignal:
    """signal() returns the raw trace, read-only."""

    def test_trace_and_slice(self, single, window):
        """The full trace and a time window come back as time_s and counts."""
        full = single.acquisition.signal('Lake_A', 'Fe')
        assert list(full.columns) == ['time_s', 'counts']
        assert len(full) == N
        np.testing.assert_array_equal(full['counts'].to_numpy(), window.data_by_sample['Lake_A'][FE])
        part = single.acquisition.signal('Lake_A', 'fe56', t0=0.4999, t1=0.5001)
        assert part['counts'].max() == 400.0
        assert part['time_s'].between(0.4999, 0.5001).all()

    def test_copy_does_not_touch_window(self, single, window):
        """Changing the returned trace leaves the main window's array as it was."""
        before = window.data_by_sample['Lake_A'][FE].copy()
        out = single.acquisition.signal('Lake_A', '56Fe')
        out['counts'] *= 0
        np.testing.assert_array_equal(window.data_by_sample['Lake_A'][FE], before)

    def test_pooled_sample_needs_a_run(self, pooled):
        """A pooled sample name is refused with the runs it holds."""
        with pytest.raises(KeyError, match='Lake_A, Lake_B'):
            pooled.acquisition.signal('Lakes', 'Fe')
        assert len(pooled.acquisition.signal('lake_b', 'Fe')) == N

    def test_unknown_names(self, single):
        """Unknown runs and elements list what exists."""
        with pytest.raises(KeyError, match='Lake_A'):
            single.acquisition.signal('Lake_Z', 'Fe')
        with pytest.raises(KeyError, match='56Fe'):
            single.acquisition.signal('Lake_A', 'Au')

    def test_label_matching(self):
        """Labels accept symbols, case and reversed forms."""
        labels = ['48Ti', '56Fe']
        assert match_label('Ti', labels) == '48Ti'
        assert match_label('Fe-56', labels) == '56Fe'
        assert match_label('56fe', labels) == '56Fe'


class TestSandboxAndPrompt:
    """The functions reach generated code and the prompt describes them."""

    def test_generated_code_uses_both(self, single):
        """Code in the sandbox reads the summary and plots a trace."""
        code = (
            "s = sample_summary()\n"
            "show_table(s[['run', 'element', 'particles_per_ml_corrected', 'background_ppt']], title='Per run')\n"
            "tr = signal('Lake_A', 'Fe', t0=0.4, t1=0.6)\n"
            "fig, ax = plt.subplots()\n"
            "ax.plot(tr['time_s'], tr['counts'], lw=0.5)\n"
            "ax.set_xlabel('Time (s)'); ax.set_ylabel('Fe counts')\n"
            "print(int(tr['counts'].max()))\n"
        )
        res = execute(code, single, None)
        assert res.error == ''
        assert res.text.strip() == '400'
        assert res.tables and res.tables[0]['title'] == 'Per run'
        assert len(res.figures) == 1

    def test_hidden_from_data_context(self, window):
        """The acquisition object never appears in data_context."""
        acq = StaticAcquisition({'R': {'56Fe': (np.arange(3.0), np.ones(3))}})
        ds = Dataset({'type': 'sample_data', 'sample_name': 'R', 'acquisition': acq,
                      'particle_data': [_particle('R', 'R', 0.1)]})
        assert ds.acquisition is acq
        assert 'acquisition' not in ds.safe_context()
        assert len(ds.acquisition.signal('R', 'Fe')) == 3

    def test_prompt_with_and_without(self, single):
        """The prompt documents the functions only when the raw data exists."""
        with_raw = build_system_prompt(single, 16384)
        assert 'sample_summary()' in with_raw and 'available for 1 runs' in with_raw
        bare = Dataset({'type': 'sample_data', 'sample_name': 'S',
                        'particle_data': [_particle('S', 'S', 0.1)]})
        text = build_system_prompt(bare, 16384)
        assert 'RAW SIGNAL AND PER-SAMPLE RESULTS (' not in text
        assert 'NOT available — do not call signal()' in text
        res = execute("signal('S', 'Fe')", bare, None)
        assert 'not available' in res.error

    def test_static_rows_get_sample(self):
        """Static rows take their sample from the groups."""
        acq = StaticAcquisition({'A1': {}}, rows=[{'run': 'A1', 'element': '56Fe', 'particles': 5}],
                                groups={'A1': 'A'})
        frame = acq.summary()
        assert frame.loc[0, 'sample'] == 'A'
        assert isinstance(frame, pd.DataFrame)
        assert math.isnan(frame.loc[0, 'background_ppt'])

    def test_window_without_data(self):
        """A window with no loaded samples gives no source."""
        assert not WindowAcquisition.available(object())
