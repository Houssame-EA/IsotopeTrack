# -*- coding: utf-8 -*-
"""Tests for the filled log-normal histograms that are the default for sizes and masses."""
import re

import matplotlib
import numpy as np
import pytest

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from results.ai.data import Dataset
from results.ai.figures import lognormal_hist
from results.ai.prompts import build_system_prompt
from results.ai.sandbox import execute
from results.ai.synthetic import make_dataset


@pytest.fixture(scope='module')
def planted():
    """The synthetic dataset with its limits."""
    dc, truth, limits = make_dataset(seed=11)
    ds = Dataset(dc)
    ds.set_limits(limits)
    return ds


def test_fit_recovers_the_distribution():
    """Median and GSD of a known log-normal come back."""
    v = np.random.default_rng(1).lognormal(np.log(80), np.log(1.5), 20000)
    fig, ax = plt.subplots()
    out = lognormal_hist(ax, v, label='A', unit='nm')
    assert out['n'] == 20000
    assert out['gm'] == pytest.approx(80, rel=0.02)
    assert out['gsd'] == pytest.approx(1.5, rel=0.02)
    assert ax.get_xscale() == 'log'
    plt.close(fig)


def test_bars_are_filled_and_the_curve_sits_on_them():
    """Bars are filled, one fitted line is drawn and its peak matches the bars."""
    v = np.random.default_rng(2).lognormal(np.log(50), np.log(1.4), 5000)
    bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 40)
    fig, ax = plt.subplots()
    lognormal_hist(ax, v, bins, color='#0072B2', label='A')
    assert all(p.get_fill() for p in ax.patches)
    assert len(ax.lines) == 1
    counts, _ = np.histogram(v, bins)
    assert ax.lines[0].get_ydata().max() == pytest.approx(counts.max(), rel=0.15)
    plt.close(fig)


def test_fit_is_in_the_legend_and_can_be_left_out():
    """The legend label carries the fit; fit=False draws bars only."""
    v = np.random.default_rng(3).lognormal(3, 0.4, 500)
    fig, ax = plt.subplots()
    lognormal_hist(ax, v, label='River_A', unit='nm')
    label = ax.patches[0].get_label()
    assert re.search(r'River_A \(GM [\d.]+ nm, GSD [\d.]+\)', label)
    fig2, ax2 = plt.subplots()
    lognormal_hist(ax2, v, label='River_A', fit=False)
    assert not ax2.lines and ax2.patches[0].get_label() == 'River_A'
    plt.close(fig)
    plt.close(fig2)


def test_too_few_values_draw_without_a_fit():
    """Two values give bars and no curve."""
    fig, ax = plt.subplots()
    out = lognormal_hist(ax, [10.0, 20.0, float('nan'), -1.0], label='A')
    assert out['n'] == 2 and np.isnan(out['gm']) and not ax.lines
    plt.close(fig)


def test_example_from_the_prompt_runs(planted):
    """The model's example draws the histograms with the fit in the figure description."""
    code = (
        "fig, ax = plt.subplots(figsize=(6.5, 4))\n"
        "c = col('size', 'Ti')\n"
        "v = df[c].dropna()\n"
        "bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 50)\n"
        "for s in samples:\n"
        "    lognormal_hist(ax, df.loc[df['sample'] == s, c].dropna(), bins, color=SAMPLE_COLORS[s], label=s, unit='nm')\n"
        "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Particles'); ax.legend()\n"
    )
    res = execute(code, planted, 60)
    assert not res.error and not res.warnings
    assert res.figures[0]['description'].count('GSD') == 3
    prompt = build_system_prompt(planted, 16384, 'chat', 10)
    assert 'lognormal_hist(ax, df.loc' in prompt and "histtype='step', lw" not in prompt


def test_mixed_panel_types_with_letters(planted):
    """A ternary next to a heatmap in one figure, with (a) and (b)."""
    from results.ai.figures import TERNARY
    first = 'ternary' if TERNARY else 'polar'
    code = (
        f"fig, (a, b) = new_figure(1, 2, size=(10, 4), projection=['{first}', None])\n"
        "b.imshow(np.random.rand(4, 4)); b.set_xlabel('x'); b.set_ylabel('y')\n"
        + ("a.scatter([0.2, 0.3], [0.3, 0.3], [0.5, 0.4])\n" if TERNARY else "a.plot([0, 1], [1, 2])\n")
        + "label_panels([a, b])\n"
    )
    res = execute(code, planted, 60)
    assert not res.error
    fig = res.figures[0]['figure']
    assert getattr(fig.axes[0], 'name', '') == first and fig.axes[1].name == 'rectilinear'
    letters = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert '(a)' in letters and '(b)' in letters
    prompt = build_system_prompt(planted, 16384, 'chat', 10)
    assert 'label_panels([a, b])' in prompt and "None])" in prompt


def test_empty_figure_is_left_out_and_explained(planted):
    """A figure created before a check that skips the plot is not shown; the model is told."""
    code = ("fig, ax = plt.subplots()\n"
            "out = find_outliers('mass_fg', threshold=1000)\n"
            "if len(out):\n"
            "    ax.scatter(out['value'], out['robust_z'])\n"
            "show_table(out, title='Outliers')\n")
    res = execute(code, planted, 60)
    assert not res.error and not res.figures
    from results.ai.sandbox import result_digest
    assert 'had nothing drawn on it' in result_digest(res)


def test_unused_grid_panels_are_hidden(planted):
    """Five plots in a 2 x 3 grid: the sixth panel is hidden and raises no warning, letters or not."""
    code = ("fig, axes = plt.subplots(2, 3, figsize=(12, 7))\n"
            "for ax, el in zip(axes.flat, ['Ti', 'Fe', 'Ce', 'La', 'Ag']):\n"
            "    v = df[col('mass_fg', el)].dropna()\n"
            "    ax.hist(v, bins=30); ax.set_xlabel(f'{el} mass (fg)'); ax.set_ylabel('Particles')\n"
            "label_panels(axes.flat)\n")
    res = execute(code, planted, 60)
    assert not res.error
    fig = res.figures[0]['figure']
    assert sum(ax.get_visible() for ax in fig.axes) == 5
    assert not any('empty' in w for w in res.warnings)


def test_twelve_figures_allowed_thirteen_refused(planted):
    """Up to 12 figures in one code block; the 13th is refused with a clear error."""
    twelve = "for k in range(12):\n    fig, ax = plt.subplots(); ax.plot([0, 1], [k, k + 1]); ax.set_xlabel('x'); ax.set_ylabel('y')\n"
    res = execute(twelve, planted, 60)
    assert not res.error and len(res.figures) == 12
    res = execute(twelve.replace('12', '13'), planted, 60)
    assert 'At most 12 figures' in res.error


def test_zero_bars_on_a_log_axis_are_flagged(planted):
    """Bars of zero on a log axis vanish; a histogram with empty bins does not count."""
    code = ("fig, ax = plt.subplots()\n"
            "ax.barh(['a', 'b', 'c', 'd'], [2.0, 0.5, 0.0, 0.0]); ax.set_xscale('log')\n"
            "ax.set_xlabel('ratio'); ax.set_ylabel('combination')\n")
    res = execute(code, planted, 60)
    assert any('2 bar(s) are zero' in w for w in res.warnings)
    hist = ("fig, ax = plt.subplots()\n"
            "ax.hist(df[col('mass_fg', 'Ti')].dropna(), bins=60); ax.set_yscale('log')\n"
            "ax.set_xlabel('Ti mass (fg)'); ax.set_ylabel('Particles')\n")
    res = execute(hist, planted, 60)
    assert not any('bar(s) are zero' in w for w in res.warnings)


def test_rules_about_figure_count_and_where_to_create_them(planted):
    """The rules give the 12-figure limit and say to create a figure only where it is drawn on."""
    prompt = build_system_prompt(planted, 16384, 'chat', 10)
    assert 'at most 12 figures per code block' in prompt
    assert 'create a figure only where you draw on it' in prompt
