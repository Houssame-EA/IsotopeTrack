"""Tests for the mean signals the main window hands to the results canvas."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from results.figure_builder.core import massbias as mb
from save_export.project_manager import ProjectManager
from utils.signal_stats import mean_signal_ratio


def label(key):
    """Return ``205Tl`` style labels from ``Tl-204.9744`` keys."""
    element, mass = key.split('-')
    return f"{round(float(mass))}{element}"


def test_ratio_of_two_mean_signals():
    """The ratio divides the two means of the sample."""
    means = {'S1': {'205Tl': 7.0, '203Tl': 2.0}}
    assert mean_signal_ratio(means, 'S1', '205Tl', '203Tl') == 3.5
    assert mean_signal_ratio(means, 'S1', '205Tl', '208Pb') is None
    assert mean_signal_ratio(means, 'S2', '205Tl', '203Tl') is None
    assert mean_signal_ratio(None, 'S1', '205Tl', '203Tl') is None


def test_ratio_finds_renamed_samples():
    """Particle Filter and Batch Windows names are traced back."""
    means = {'S1': {'205Tl': 6.0, '203Tl': 3.0},
             'S2 [W2 (Project B)]': {'205Tl': 4.0, '203Tl': 1.0}}
    assert mean_signal_ratio(means, 'S1 (filt x2)', '205Tl', '203Tl') == 2.0
    assert mean_signal_ratio(means, 'S2 [W2 (Project B)] (filt x1)', '205Tl', '203Tl') == 4.0


def manager():
    """Return a project manager on a stand-in main window."""
    pm = ProjectManager.__new__(ProjectManager)
    pm.main_window = SimpleNamespace(get_formatted_label=label)
    return pm


def test_batch_snapshot_keeps_means_not_signals():
    """The saved snapshot drops the raw signals and the window."""
    out = {'type': 'batch_sample_list', 'particle_data': [{'elements': {'205Tl': 3.0}}],
           'data': {'S1 [W1 (A)]': {204.97: np.zeros(10)}},
           'mean_signal': {'S1 [W1 (A)]': {'205Tl': 7.0}}, 'parent_window': object()}
    snap = manager()._batch_snapshot(out)
    assert 'data' not in snap and 'parent_window' not in snap
    assert snap['mean_signal'] == {'S1 [W1 (A)]': {'205Tl': 7.0}}
    assert snap['particle_data'] == out['particle_data']


def test_old_snapshot_gets_means_from_its_signals():
    """A snapshot saved with raw signals and no means has its means computed once."""
    signal = np.full(10, 6.0)
    signal[0] = np.nan
    old = {'type': 'batch_sample_list', 'particle_data': [],
           'available_isotopes': {'Tl': [204.9744, 202.9723]},
           'data': {'S1 [W1 (A)]': {204.97: signal, 202.97: np.full(10, 2.0)}}}
    snap = manager()._batch_snapshot(old)
    assert 'data' not in snap
    assert snap['mean_signal'] == {'S1 [W1 (A)]': {'205Tl': 6.0, '203Tl': 2.0}}


def test_saved_snapshot_is_kept_when_no_window_is_linked():
    """Saving a reopened project keeps the batch results it was opened with."""
    node = SimpleNamespace(selected_windows=[],
                           _saved_output_snapshot={'particle_data': [1], 'mean_signal': {'S': {}}})
    node_data = {}
    manager()._serialize_batch_output(node, node_data)
    assert node_data['batch_output_snapshot']['particle_data'] == [1]


def test_figure_builder_correction_reads_the_canvas_means():
    """The ionic reference ratio comes from the canvas data without any window."""
    table = SimpleNamespace(mean_signal={'A': {'205Tl': 8.0, '203Tl': 4.0}})
    mb.attach(table, None, None)
    assert table.ionic_ratio('A', '205Tl', '203Tl') == 2.0
    assert table.ionic_ratio('B', '205Tl', '203Tl') is None
