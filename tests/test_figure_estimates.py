"""Group estimates: the ratio of sums with its interval, the Estimate chart and the value ellipse."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder.core import estimates as est
from results.figure_builder.core.engine import make_panel, normalise_spec, render
from results.figure_builder.core.expressions import ParticleTable
from results.insights import engine as rr
from results.insights import evidence as ev
from results.insights import figures as F

TRUE = {'Smelter': (1.160, 2.10), 'Background': (1.105, 2.04)}
"""True 206Pb/207Pb and 208Pb/206Pb of each simulated sample."""


def lead(seed=7, n=700, replicates=1):
    """Pb particles with counting noise, two samples of known isotope ratios."""
    rng = np.random.default_rng(seed)
    parts = []
    for name, (r67, r86) in TRUE.items():
        for i in range(n):
            total = rng.lognormal(5.2, 0.9)
            share = np.array([1.0, 1.0 / r67, r86])
            c = rng.poisson(total * share / share.sum()).astype(float)
            if (c < 5).any():
                continue
            el = dict(zip(('206Pb', '207Pb', '208Pb'), c))
            el['56Fe'] = float(rng.lognormal(3, 0.5))
            p = {'source_sample': name, 'elements': el, 'start_time': i * 1e-3}
            if replicates > 1:
                p['original_sample'] = f'{name}_{i % replicates + 1}'
            parts.append(p)
    return ParticleTable.from_input({'type': 'multiple_sample_data', 'particle_data': parts,
                                     'sample_names': list(TRUE)})


def one(t, **panel):
    """Draw one panel; return its axes, artist record and report."""
    spec = normalise_spec({'panels': [make_panel(**panel)]})
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = render(fig, spec, t)
    assert report.errors == {}
    canvas.draw()
    hd = report.artists[spec['panels'][0]['id']]
    return hd['ax'], hd, report


def test_ratio_is_the_ratio_of_sums_with_the_counting_error():
    """For raw counts of one population the standard error is R·√(1/ΣA + 1/ΣB)."""
    rng = np.random.default_rng(1)
    total = rng.lognormal(5, 1, 4000)
    a, b = rng.poisson(total * 0.54).astype(float), rng.poisson(total * 0.46).astype(float)
    ok = (a > 0) & (b > 0)
    a, b = a[ok], b[ok]
    e = est.estimate(a / b, b)
    pooled = a.sum() / b.sum()
    assert e.value == pytest.approx(pooled)
    assert e.se == pytest.approx(pooled * np.sqrt(1 / a.sum() + 1 / b.sum()), rel=0.05)
    assert abs(e.value - 0.54 / 0.46) < 3 * e.se
    assert abs(np.mean(a / b) - 0.54 / 0.46) > abs(e.value - 0.54 / 0.46)
    assert e.half == pytest.approx(est.Z95 * e.se) and e.n == a.size


def test_error_widens_when_the_particles_truly_differ():
    """Two isotopic populations pooled give a wider interval than counting alone."""
    rng = np.random.default_rng(2)
    total = rng.lognormal(6, 0.5, 2000)
    r = np.where(rng.random(2000) < 0.5, 1.0, 1.4)
    a, b = rng.poisson(total * r / (1 + r)).astype(float), rng.poisson(total / (1 + r)).astype(float)
    e = est.estimate(a / b, b)
    counting = e.value * np.sqrt(1 / a.sum() + 1 / b.sum())
    assert e.se > 2 * counting


def test_plain_value_is_a_mean_with_its_standard_error():
    """Without a denominator the estimate is the mean and SD/√n."""
    v = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
    e = est.estimate(v)
    assert e.value == pytest.approx(2.5) and e.n == 4
    assert e.se == pytest.approx(np.std(v[:4], ddof=1) / 2)
    assert est.estimate([1.0, 2.0]) is None


@pytest.mark.parametrize('expr, den', [
    ('206Pb / 207Pb', '207Pb'), ('(206Pb / 207Pb) * 1.01', '207Pb'),
    ('(206Pb / 207Pb) * mb_ab12', '207Pb'), ('mass:Fe/mass:Ti', 'mass:Ti'),
    ('Fe / (Fe + Ti)', '(Fe + Ti)'), ('Fe + Ti', None), ('a/b/c', None), ('Fe*2/Ti', None),
    ('', None),
])
def test_denominator_is_read_only_from_a_simple_ratio(expr, den):
    """One top-level division gives a denominator; anything else is not a ratio."""
    assert est.denominator(expr) == den


def test_difference_and_formatting():
    """The z-test of two estimates, and a value written to its interval's digits."""
    a = est.Estimate(1.163, 0.008, 600, np.zeros(600))
    b = est.Estimate(1.111, 0.008, 600, np.zeros(600))
    z, p = est.difference(a, b)
    assert z == pytest.approx(0.052 / np.hypot(0.008, 0.008)) and p < 1e-4
    assert est.difference(a, a)[1] == pytest.approx(1.0)
    assert est.fmt_pm(1.16314, 0.0157) == '1.163 ± 0.016'
    assert est.fmt_pm(2.1213, 0.23) == '2.12 ± 0.23'
    assert est.fmt_pm(1.5, 0.0) == '1.5'


def test_estimate_chart_recovers_the_true_ratios():
    """Each sample's value sits within its interval of the truth, and the two are told apart."""
    ax, hd, report = one(lead(), kind='estimate', value='206Pb / 207Pb', group_by='sample')
    got = {label: (value, se) for label, value, se, _n in hd['estimates']}
    for name, (r67, _r86) in TRUE.items():
        value, se = got[name]
        assert abs(value - r67) < 3 * se and se < 0.012
    assert [t.get_text().split('\n')[0] for t in ax.get_yticklabels()] == list(TRUE)
    assert sum('±' in t.get_text() for t in ax.texts) == 2
    assert any(line.startswith('Smelter: ratio of summed signals 1.1') for line in report.stats)
    against = next(line for line in report.stats if line.startswith('Smelter against Background'))
    assert 'z = ' in against and float(against.split('p = ')[1]) < 0.001
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels == ['Ratio of summed signals ± 95% interval', 'Median of particles']


def test_estimate_chart_marks_each_replicate():
    """A pooled group shows its replicates as open circles and names them in the legend."""
    ax, _hd, _report = one(lead(replicates=3), kind='estimate', value='206Pb / 207Pb',
                           group_by='sample')
    assert 'Each replicate' in [t.get_text() for t in ax.get_legend().get_texts()]
    open_circles = [ln for ln in ax.lines if ln.get_marker() == 'o' and ln.get_markerfacecolor() == 'none']
    assert len(open_circles) == 6
    ax, _hd, _report = one(lead(replicates=3), kind='estimate', value='206Pb / 207Pb',
                           group_by='sample', est_replicates=False, est_median=False)
    assert [t.get_text() for t in ax.get_legend().get_texts()] == \
        ['Ratio of summed signals ± 95% interval']


def test_estimate_chart_of_a_plain_value_and_upright():
    """A value that is not a ratio is a mean; the groups can run along the bottom."""
    ax, hd, report = one(lead(), kind='estimate', value='56Fe', group_by='sample',
                         est_vertical=True)
    assert [t.get_text().split('\n')[0] for t in ax.get_xticklabels()] == list(TRUE)
    assert any(': mean ' in line for line in report.stats)
    label, value, se, n = hd['estimates'][0]
    assert value == pytest.approx(np.exp(3 + 0.125), rel=0.1) and se > 0 and n > 400


def test_estimate_chart_needs_particles():
    """A group with too few particles is left out; none at all is an error."""
    spec = normalise_spec({'panels': [make_panel(kind='estimate', value='206Pb / 207Pb',
                                                 filter='206Pb > 1e9')]})
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, lead())
    assert 'three or more particles' in next(iter(report.errors.values()))


def test_value_ellipse_on_a_three_isotope_plot():
    """The group value and its ellipse replace the points in the legend and hold the truth."""
    ax, hd, report = one(lead(), kind='scatter', x='207Pb / 206Pb', y='208Pb / 206Pb',
                         group_by='sample', ellipse='mean95', iso_refs='all', iso_ref_line=True)
    rows = {label: (x, hx, y, hy) for label, x, hx, y, hy, _n in hd['group_values']}
    for name, (r67, r86) in TRUE.items():
        x, hx, y, hy = rows[name]
        assert abs(x - 1 / r67) < 2 * hx and abs(y - r86) < 2 * hy
        assert hx < 0.02 and hy < 0.04
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert sum('value and 95% ellipse' in t for t in labels) == 2
    assert not any(t.startswith('Smelter (n=') and 'ellipse' not in t for t in labels)
    dotted = [ln for ln in ax.lines if ln.get_linestyle() not in ('-', 'None') and len(ln.get_xdata()) == 2]
    assert len(dotted) == 1
    assert any(line.startswith('Smelter: x = 0.8') for line in report.stats)


def test_shared_denominator_tilts_the_ellipse():
    """Two ratios over one denominator vary together, so their covariance is positive."""
    t = lead()
    from results.figure_builder.charts.estimate import group_estimate
    m = t.column('sample') == 'Smelter'
    a = group_estimate(t, '207Pb / 206Pb', m)
    b = group_estimate(t, '208Pb / 206Pb', m)
    cov = est.covariance(a, b)
    assert cov[0, 1] > 0 and cov[0, 1] == cov[1, 0]
    x, y = est.ellipse(a, b)
    assert x.min() < a.value < x.max() and y.min() < b.value < y.max()


def story(key, table, title='206Pb/207Pb: Smelter vs Background'):
    """An isotope story over the two lead samples."""
    s = rr.Suggestion(title, 'r', 'isotope', 0.8, 'x', elements=('206Pb', '207Pb'),
                      explain_key=key)
    ctx = F.FigureContext({'counts'}, {}, {}, True, 2, present={'206Pb', '207Pb', '208Pb'},
                          table=table)
    return F.figure_for(s, ctx)


def test_group_difference_story_leads_with_the_estimate_and_passes_its_checks():
    """The difference between samples is the finding, so finding it is a pass."""
    t = lead()
    spec = story('isotope_groups', t)
    assert spec['panels'][0]['kind'] == 'estimate' and spec['panels'][0]['group_by'] == 'sample'
    legend = spec['panels'][-1]['text']
    assert "✓ The samples' pooled ratios differ: Smelter 1.1" in legend
    assert '✓ 206Pb/207Pb ratio differs between groups, as the finding says' in legend
    assert '✗' not in legend
    assert 'The largest difference, Smelter against Background, is +' in legend
    fig = Figure()
    FigureCanvasAgg(fig)
    assert render(fig, spec, t).errors == {}


def test_single_population_story_still_flags_groups_that_differ():
    """When one shared ratio is the finding, groups that differ stay a caution."""
    legend = story('isotope', lead(), '206Pb/207Pb in Pb particles')['panels'][-1]['text']
    assert '✗ 206Pb/207Pb ratio differs between groups (' in legend
    assert 'The ratio of the summed counts, which large particles decide, is 1.1' in legend


def test_three_isotope_panel_shows_values_zoomed_to_the_sources():
    """One panel for all samples, with value ellipses, faint particles and framed sources."""
    spec = story('isotope_groups', lead())
    three = next(p for p in spec['panels'] if p.get('title') == 'Three-isotope plot')
    assert three['ellipse'] == 'mean95' and three['group_by'] == 'sample' and three['iso_ref_line']
    assert three['alpha'] <= 0.2
    assert float(three['x_min']) < 0.8357 < 0.9617 < float(three['x_max']) < 1.1
    assert float(three['y_min']) < 2.04 < 2.228 < float(three['y_max']) < 2.4
    assert 'zoomed to the sample values and the sources' in spec['panels'][-1]['text']


def test_zoom_frames_values_and_sources():
    """The window covers every interval and source with a margin; nothing to frame gives none."""
    window = F._zoom([(1.0, 0.1, 2.0, 0.1)], [(1.5, 2.5)])
    assert float(window['x_min']) < 0.84 and float(window['x_max']) > 1.5
    assert float(window['y_min']) < 1.84 and float(window['y_max']) > 2.5
    assert F._zoom([], []) == {}


def test_pooled_matches_the_chart():
    """The legend's numbers are the chart's numbers."""
    t = lead()
    rows = dict(ev.pooled(t, '206Pb / 207Pb'))
    _ax, hd, _report = one(t, kind='estimate', value='206Pb / 207Pb', group_by='sample')
    for label, value, se, n in hd['estimates']:
        assert rows[label].value == pytest.approx(value) and rows[label].n == n
