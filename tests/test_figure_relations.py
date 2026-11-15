"""Relations between two elements: slope range, fixed-ratio lines, ratio populations and their stories."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder.charts.xy import slope_range
from results.figure_builder.core.engine import make_panel, normalise_spec, render
from results.figure_builder.core.expressions import ParticleTable
from results.insights import engine as rr
from results.insights import evidence as ev
from results.insights import figures as F

SENS = {'28Si': 6.0, '24Mg': 45.0, '56Fe': 90.0, '27Al': 70.0, '55Mn': 110.0}
EXTRA = ['139La', '140Ce', '88Sr', '137Ba', '90Zr', '48Ti', '52Cr', '60Ni', '63Cu', '66Zn']


def powder(seed=11, n=(1500, 4000), clay=(0.10, 0.22), clay_fe=(3.2, 3.2), other=False):
    """Two mineral samples: a main Si-Mg-Fe phase and an Al-bearing one with more Fe.

    Args:
        clay: Share of Al-bearing particles in each sample.
        clay_fe: Si/Fe mass ratio of the Al-bearing phase in each sample (20 in the main phase).
        other: Whether every particle also carries a heavy element making up most of its mass.
    """
    rng = np.random.default_rng(seed)
    parts = []
    for k, name in enumerate(('ASB', 'Js')):
        for i in range(n[k]):
            si = rng.lognormal(3.5, 0.9)
            if rng.random() < clay[k]:
                masses = {'28Si': si, '24Mg': si * 0.5 * rng.lognormal(0, 0.2),
                          '56Fe': si / clay_fe[k] * rng.lognormal(0, 0.25),
                          '27Al': si * 0.12 * rng.lognormal(0, 0.6)}
            else:
                masses = {'28Si': si, '24Mg': si * 0.9 * rng.lognormal(0, 0.2),
                          '56Fe': si / 20.0 * rng.lognormal(0, 0.28)}
            if other:
                masses['137Ba'] = si * 30 * rng.lognormal(0, 1.0)
            for lab in EXTRA:
                if lab not in masses and rng.random() < 0.01:
                    masses[lab] = rng.lognormal(-1.0, 0.5)
            el, mass = {}, {}
            for lab, fg in masses.items():
                c = float(rng.poisson(fg * SENS.get(lab, 80.0)))
                if c >= 6:
                    el[lab], mass[lab] = c, c / SENS.get(lab, 80.0)
            if el:
                parts.append({'source_sample': name, 'elements': el, 'element_mass_fg': mass,
                              'start_time': i * 0.012, 'end_time': i * 0.012 + 0.0006})
    return ParticleTable.from_input({'type': 'multiple_sample_data', 'particle_data': parts,
                                     'sample_names': ['ASB', 'Js']})


def one(t, figure=None, **panel):
    """Draw one panel; return its axes, artist record and report."""
    spec = normalise_spec({'figure': figure or {}, 'panels': [make_panel(**panel)]})
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = render(fig, spec, t)
    assert report.errors == {}
    canvas.draw()
    hd = report.artists[spec['panels'][0]['id']]
    return hd['ax'], hd, report


def context(t, quantities=('counts', 'mass')):
    """A two-group figure context over a table."""
    return F.FigureContext(set(quantities), {}, {}, True, 2, table=t)


def card(key, elements, title='t'):
    """A finding of the given kind."""
    return rr.Suggestion(title, 'r', key.split('_')[0], 0.8, 'x', elements=elements, explain_key=key)


def test_slope_range_brackets_the_truth_when_x_is_noisy():
    """A proportional relation with noise in x: y-on-x is too flat, the range still holds 1."""
    rng = np.random.default_rng(5)
    true = rng.normal(2, 0.5, 3000)
    lo, hi, cx, cy = slope_range(true + rng.normal(0, 0.3, 3000), true + rng.normal(0, 0.05, 3000))
    assert lo < 0.8 and lo < 1 < hi
    assert cx == pytest.approx(2, abs=0.05) and cy == pytest.approx(2, abs=0.05)
    exact = slope_range(true, 3 * true + 1)
    assert exact[0] == pytest.approx(3) and exact[1] == pytest.approx(3)
    assert slope_range(np.ones(10), true[:10]) is None and slope_range(true[:2], true[:2]) is None


def test_scatter_shades_the_slope_range_and_reports_it():
    """The wedge joins the legend and Statistics says whether a fixed ratio is ruled out."""
    t = powder(clay=(0.0, 0.0))
    ax, hd, report = one(t, kind='scatter', x='mass:56Fe', y='mass:28Si', log_x=True, log_y=True,
                         fit_range=True)
    label, lo, hi = hd['slope_range'][0]
    assert lo < 1 <= hi * 1.05 and lo < hi
    assert any('slope' in t.get_text() and ' to ' in t.get_text()
               for t in ax.get_legend().get_texts())
    line = next(s for s in report.stats if 'the slope lies between' in s)
    assert '(y on x)' in line and '(x on y)' in line and 'fixed ratio' in line


def test_fixed_ratio_lines_follow_the_values_asked_for():
    """`median` gives the particles' median ratio; numbers give those ratios, named in the legend."""
    t = powder()
    ax, _hd, report = one(t, kind='scatter', x='mass:56Fe', y='mass:28Si', log_x=True, log_y=True,
                          ratio_lines='median, 3.2, nonsense', ratio_lines_label='28Si/56Fe')
    labels = [x.get_text() for x in ax.get_legend().get_texts()]
    assert '$^{28}$Si/$^{56}$Fe = 3.2' in labels and sum('Si/' in x for x in labels) == 2
    lines = [ln for ln in ax.lines if len(ln.get_xdata()) == 2]
    for ln in lines:
        x, y = np.asarray(ln.get_xdata()), np.asarray(ln.get_ydata())
        assert (y / x)[0] == pytest.approx((y / x)[1])
    assert sum(s.startswith('Fixed-ratio line') for s in report.stats) == 2


def test_percent_histogram_gives_every_group_the_same_area():
    """Each group's bars add to 100 whatever its size, and the axis says so."""
    _ax, hd, _report = one(powder(), kind='histogram', value='56Fe', group_by='sample',
                           log_x=True, hist_percent=True)
    for _label, _edges, heights in hd['hist']:
        assert heights.sum() == pytest.approx(100.0, abs=0.5)
    assert hd['ax'].get_ylabel() == '% of each group'
    _ax, hd, _report = one(powder(), kind='histogram', value='56Fe', group_by='sample')
    assert hd['ax'].get_ylabel() == 'Particle count'


def test_log_axis_of_about_a_decade_gets_plain_1_2_5_ticks():
    """An axis from 0.2 to 3 is labelled 0.2, 0.5, 1, 2 instead of a lone 10⁰."""
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.set_yscale('log')
    ax.plot([1, 2], [0.2, 3.0])
    from results.figure_builder.core.common import tidy_log_ticks
    tidy_log_ticks(ax)
    canvas.draw()
    lo, hi = ax.get_ylim()
    shown = [t.get_text() for t, v in zip(ax.get_yticklabels(), ax.get_yticks()) if lo <= v <= hi]
    assert sorted(shown, key=float) == ['0.2', '0.5', '1', '2']
    ax.set_ylim(0.01, 1000)
    canvas.draw()
    assert any('10^' in t.get_text() for t in ax.get_yticklabels())


def test_legend_entries_raise_isotopes():
    """`With 27Al` in a legend is written like the axis labels."""
    ax, _hd, _report = one(powder(), kind='histogram', value='56Fe', group_by='rules', rules=[
        {'name': 'With 27Al', 'when': '27Al > 0', 'color': '#c2410c'},
        {'name': 'Without 27Al', 'when': '27Al == 0', 'color': '#64748b'}])
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels[0].startswith('With $^{27}$Al') and labels[1].startswith('Without $^{27}$Al')


def test_network_names_sit_outside_their_nodes_and_legend_shows_only_signs_present():
    """Labels are offset from the node by its radius; no `r < 0` entry without such a link."""
    ax, hd, _report = one(powder(), kind='network', isotopes='28Si, 56Fe, 24Mg, 27Al',
                          net_r_min=0.3, log_values=True, data_type='Element Mass (fg)')
    notes = [t for t in ax.texts if getattr(t, 'xyann', None) is not None]
    assert len(notes) == 4
    assert all(np.hypot(*t.xyann) > 8 for t in notes)
    assert all('mass' not in t.get_text() for t in notes)
    assert hd['network']['edges'] and all(e[2] > 0 for e in hd['network']['edges'])
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ['r > 0']


@pytest.mark.parametrize('name, two', [('one', False), ('tails', False), ('two', True),
                                       ('close', False), ('few', False)])
def test_ratio_peaks_tells_two_populations_from_one(name, two):
    """Two well-separated peaks are found; long tails, close peaks and a tiny second one are not."""
    rng = np.random.default_rng(3)
    data = {
        'one': 10 ** rng.normal(0.1, 0.15, 3000),
        'tails': 10 ** (rng.standard_t(3, 3000) * 0.12),
        'two': np.r_[10 ** rng.normal(0.5, 0.12, 2500), 10 ** rng.normal(1.3, 0.15, 700)],
        'close': np.r_[10 ** rng.normal(0.5, 0.15, 2500), 10 ** rng.normal(0.7, 0.15, 1500)],
        'few': np.r_[10 ** rng.normal(0.5, 0.12, 2500), 10 ** rng.normal(1.3, 0.15, 100)],
    }[name]
    found = ev.ratio_peaks(data)
    assert found['two'] is two
    if two:
        assert found['centres'][0] == pytest.approx(10 ** 0.5, rel=0.05)
        assert found['centres'][1] == pytest.approx(10 ** 1.3, rel=0.05)
        assert found['shares'][0] == pytest.approx(2500 / 3200, abs=0.03)
    assert ev.ratio_peaks(data[:20]) is None


def test_correlation_story_names_two_ratio_populations():
    """Two branches are a caution: lines at both ratios, a histogram marking them, no single fit."""
    t = powder()
    spec = F.figure_for(card('correlation', ('28Si', '56Fe'), '28Si vs 56Fe'), context(t))
    scatter = next(p for p in spec['panels'] if p['kind'] == 'scatter')
    low, high = (float(v) for v in scatter['ratio_lines'].split(','))
    assert low == pytest.approx(3.2, rel=0.15) and high == pytest.approx(20, rel=0.15)
    assert scatter['fit_range'] and not scatter['show_fit']
    hist = next(p for p in spec['panels'] if p['kind'] == 'histogram')
    assert hist['vlines'] == scatter['ratio_lines'] and hist['hist_percent']
    legend = spec['panels'][-1]['text']
    assert '✗ The 28Si/56Fe ratio falls into two populations, near 3.' in legend
    assert 'Measured over all particles: the slope lies between' in legend
    assert 'each population follows its own dashed line' in legend
    fig = Figure()
    FigureCanvasAgg(fig)
    assert render(fig, spec, t).errors == {}


def test_correlation_story_of_one_population_passes_and_shows_the_counting_band():
    """One ratio population is a pass; the ratio against signal carries its counting band."""
    t = powder(clay=(0.0, 0.0))
    spec = F.figure_for(card('correlation', ('28Si', '56Fe')), context(t))
    legend = spec['panels'][-1]['text']
    assert '✓ The 28Si/56Fe ratio forms one population (median ' in legend
    median = float(legend.split('forms one population (median ')[1].split(')')[0])
    assert median == pytest.approx(20, rel=0.1)
    scatter = next(p for p in spec['panels'] if p.get('fit_range'))
    assert scatter['ratio_lines'] == 'median'
    band = [p for p in spec['panels'] if p.get('poisson_band')]
    assert band and band[0]['y'] == '28Si / 56Fe' and band[0]['x'] == '56Fe'
    assert 'excess scatter' in legend and 'the composition itself varies' in legend


def test_size_classes_are_not_a_check_when_the_two_elements_are_the_particle():
    """Si and Fe make up the particle, so thirds of total mass slice the plot and prove nothing."""
    legend = F.figure_for(card('correlation', ('28Si', '56Fe')), context(powder()))['panels'][-1]['text']
    assert 'within size classes' not in legend and 'within every size class' not in legend
    story = dict((p['title'], c) for p, c in F._correlation(card('correlation', ('28Si', '56Fe')),
                                                             context(powder())))
    assert 'it is not used as a check' in story['28Si against 56Fe by particle size']


def test_size_classes_stay_a_check_when_another_element_is_most_of_the_particle():
    """With the particle mostly something else, the size split is independent and is checked."""
    ctx = context(powder(other=True))
    ctx.checks = ev.Checks()
    F._correlation(card('correlation', ('28Si', '56Fe')), ctx)
    assert any('size class' in text for _ok, text in ctx.checks.items)


def split_checks(**kwargs):
    """The checks of a ratio-split story over a powder."""
    ctx = context(powder(**kwargs), quantities=('counts',))
    ctx.checks = ev.Checks()
    F._ratio_split(card('ratio_split', ('56Fe', '24Mg', '27Al')), ctx)
    return ctx.checks.items


def test_ratio_split_says_same_ratios_only_when_they_are_the_same():
    """Same split and same ratios pass; same split with different ratios is a caution."""
    same = split_checks()
    assert any(ok and text.startswith('every sample shows the same two ratios') for ok, text in same)
    differ = split_checks(clay_fe=(0.8, 3.2))
    row = next((ok, text) for ok, text in differ if 'sample to sample' in text)
    assert row[0] is False and row[1].startswith('every sample splits the same way, but')


def test_ratio_split_panels_use_log_axes_and_percent():
    """Signals and ratios span decades; the smaller population stays visible."""
    story = F._ratio_split(card('ratio_split', ('56Fe', '24Mg', '27Al')),
                           F.FigureContext({'counts'}, {}, {}, True, 2))
    first, hist, third = story[0][0], story[1][0], story[2][0]
    assert first['log_x'] and first['log_y'] and third['log_y']
    assert hist['hist_percent']


def test_matrix_keeps_the_two_elements_and_their_closest_company():
    """A finding about two elements shows a matrix of at most eight, those two first."""
    ctx = context(powder())
    company = F._company(ctx, ('56Fe', '27Al')).split(', ')
    assert company[:2] == ['56Fe', '27Al'] and len(company) == F.MATRIX_ELEMENTS
    assert {'28Si', '24Mg'} <= set(company)
    assert F._company(F.FigureContext({'counts'}, {}, {}, True, 2), ('56Fe', '27Al')) == ''
    story = F._cooccurrence(card('cooccurrence_avoid', ('27Al', '56Fe')), ctx)
    matrix = next(p for p, _c in story if p['kind'] == 'cooccurrence')
    assert matrix['isotopes'].startswith('27Al, 56Fe') and matrix['isotopes'].count(',') == 7
    assert story[1][0]['agg'] == 'detect_pct'


def test_group_copies_of_histograms_and_boxes_share_their_value_axis():
    """Rows of a grouped figure can be compared: one range for every group's copy."""
    ctx = context(powder())
    rule = {'ASB': 'sample == "ASB"', 'Js': 'sample == "Js"'}
    for kind, axis, log in (('histogram', 'x', 'log_x'), ('box', 'y', 'log_y')):
        copies = F.same_ranges(ctx, [{'kind': kind, 'value': '56Fe / 24Mg', log: True,
                                      'filter': rule[name]} for name in rule])
        assert copies[0][f'{axis}_min'] == copies[1][f'{axis}_min']
        assert float(copies[0][f'{axis}_min']) < float(copies[0][f'{axis}_max'])
    untouched = F.same_ranges(ctx, [{'kind': 'bar', 'value': '56Fe'}])
    assert 'y_min' not in untouched[0]


def test_grouped_histograms_compare_by_shape():
    """A histogram overlaying groups is drawn in percent of each group."""
    rows = F.by_groups([({'kind': 'histogram', 'value': '56Fe'}, 'Caption.')], ['ASB', 'Js'])
    panel = rows[0][0][0]
    assert panel['group_by'] == 'sample' and panel['hist_percent'] and rows[0][2] == 'wide'
    assert 'share of its own particles' in rows[0][1]


def test_counts_are_written_as_they_are_read():
    """No 1.44e+03 in a legend."""
    assert F._count(1440.2) == '1,440' and F._count(28.71) == '28.7' and F._count(99.96) == '100'


def test_coincidence_check_says_how_much_could_be_chance():
    """A failed coincidence check quotes the share instead of `many`."""
    ctx = context(powder(n=(3000, 3000)))
    ctx.checks = ev.Checks()
    sentence = F._coincidence_sentence(ctx, '28Si', '56Fe')
    assert 'e+0' not in sentence and 'co-detections' in sentence
    ok, text = ctx.checks.items[0]
    assert ('may be coincidences' in text) is (not ok)
    if not ok:
        assert 'so up to ' in text and '% of the pairings' in text


def test_composition_merges_small_shares_and_caps_its_legend():
    """Dozens of trace isotopes become one grey Others; the named ones stay in listed order."""
    from results.figure_builder.charts.categorical import MAX_COMPOSITION_ITEMS, _keep_items
    shares = np.array([[40.0, 0.2, 30.0, 0.0, 29.8], [10.0, 0.4, 60.0, 0.0, 29.6]])
    assert _keep_items(shares, 1.0) == [0, 2, 4]
    assert _keep_items(shares, 0.0) == [0, 1, 2, 4]
    many = np.linspace(1, 20, 20)[None, :]
    kept = _keep_items(many, 0.0)
    assert len(kept) == MAX_COMPOSITION_ITEMS - 1 and kept == sorted(kept) and 19 in kept
    ax, _hd, report = one(powder(), kind='composition', other_pct=1.0)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels[-1].startswith('Others (') and len(labels) <= MAX_COMPOSITION_ITEMS
    assert any('Si' in x for x in labels) and not any('La' in x for x in labels)
    assert any(s.startswith('Composition, merged as Others: ') for s in report.stats)
    tops = [p.get_y() + p.get_height() for p in ax.patches]
    assert max(tops) == pytest.approx(100.0, abs=0.01)


def matrix_card():
    """The Full matrix card as the detector writes it: no elements, a list in its details."""
    return rr.Suggestion('Full matrix: 4 elements', 'r', 'correlation', 0.68, 'correlation_matrix',
                         explain_key='correlation',
                         details=[('Elements', '28Si, 56Fe, 24Mg, 27Al')])


def test_full_matrix_card_shows_its_correlation_matrix():
    """A card about a correlation matrix opens with that matrix, of its own elements."""
    t = powder()
    spec = F.figure_for(matrix_card(), context(t))
    plots = [p for p in spec['panels'] if p['kind'] != 'text']
    assert plots[0]['kind'] == 'corr_matrix' and plots[0]['isotopes'] == '28Si, 56Fe, 24Mg, 27Al'
    assert {p['kind'] for p in plots} >= {'corr_matrix', 'network', 'cooccurrence'}
    assert all(p.get('isotopes') == '28Si, 56Fe, 24Mg, 27Al' for p in plots)
    legend = spec['panels'][-1]['text']
    assert 'Measured over all particles: ' in legend and 'the strongest is ' in legend
    assert '**Checks: ' in legend and 'pairs' in legend
    fig = Figure()
    FigureCanvasAgg(fig)
    assert render(fig, spec, t).errors == {}


def test_matrix_without_listed_elements_falls_back_to_the_composition():
    """With nothing to build a matrix from, the composition story stands in."""
    bare = rr.Suggestion('Full matrix', 'r', 'correlation', 0.6, 'x', explain_key='correlation')
    spec = F.figure_for(bare, context(powder()))
    assert spec['panels'][0]['kind'] == 'combinations'
    composition = next(p for p in spec['panels'] if p['kind'] == 'composition')
    assert composition['other_pct'] == 1.0


def test_pair_correlations_are_ranked_and_counted():
    """Every pair with enough shared particles, strongest first."""
    rows = F._pair_correlations(context(powder()), ['28Si', '24Mg', '56Fe'], 'mass')
    assert len(rows) == 3 and abs(rows[0][2]) >= abs(rows[-1][2])
    assert {rows[0][0], rows[0][1]} == {'28Si', '24Mg'} and rows[0][3] > 1000


TEN = [str(i) for i in range(1, 11)]


def test_many_groups_turn_histograms_into_ridges():
    """Beyond four groups an overlaid histogram becomes one ridge per group."""
    for grouping in ({}, {'group_by': 'sample'}):
        rows = F.by_groups([({'kind': 'histogram', 'value': '56Fe', 'log_x': True, 'bins': 40,
                              'dl_value': '0.2', **grouping}, 'Caption.')], TEN)
        panel = rows[0][0][0]
        assert panel['kind'] == 'ridgeline' and panel['group_by'] == 'sample'
        assert panel['mark_stats'] == 'median' and panel['dl_value'] == '0.2' and 'bins' not in panel
        assert 'Each ridge is one group' in rows[0][1]
    few = F.by_groups([({'kind': 'histogram', 'value': '56Fe', 'group_by': 'sample'}, 'C.')],
                      ['A', 'B'])
    assert few[0][0][0]['kind'] == 'histogram' and few[0][0][0]['hist_percent']


def test_a_panel_split_its_own_way_is_never_recoloured_by_group():
    """With and without an element, or by size, stays that split however many groups there are."""
    story = [({'kind': 'histogram', 'value': 'a / b', 'group_by': 'rules', 'rules': [1, 2]}, 'H.'),
             ({'kind': 'bar', 'value': 'c', 'group_by': 'size'}, 'B.'),
             ({'kind': 'scatter', 'x': 'a', 'y': 'b', 'color_by': 'c'}, 'S.'),
             ({'kind': 'combinations'}, 'C.')]
    rows = F.by_groups(story, TEN)
    assert [r[0][0].get('group_by') for r in rows] == ['rules', 'size', None, 'sample']
    assert all(r[1].endswith('All groups together.') for r in rows[:3])
    assert rows[3][1].endswith('Each colour is one group.')


def test_with_many_groups_only_pooled_panels_pair_up_and_group_rows_grow():
    """A matrix and a network share a line; panels drawing ten groups keep the width and gain height."""
    rows = [([{'kind': 'network'}], '', 'wide'), ([{'kind': 'corr_matrix'}], '', 'wide'),
            ([{'kind': 'combinations', 'group_by': 'sample'}], '', 'wide'),
            ([{'kind': 'strip', 'group_by': 'sample'}], '', 'wide')]
    assert F._lines(rows, 10) == [[0, 1], [2], [3]]
    assert F._lines(rows, 2) == [[0, 1], [2, 3]]
    rects, _caption, _width, height = F.rows_layout(rows, 10, 'x')
    assert [r[2] for r in rects] == [0.5, 0.5, 1.0, 1.0]
    assert rects[3][3] > rects[2][3] * 1.3
    assert F._line_height(rows, [3], 6) == 3.9 and F._line_height(rows, [2], 10) == 3.9


def test_network_can_use_the_rank_correlation_of_the_matrix_beside_it():
    """With Spearman chosen, the links are the pairs the rank matrix shows above the threshold."""
    t = powder()
    els = ['28Si', '56Fe', '24Mg', '27Al']
    _ax, hd, _report = one(t, kind='network', isotopes=', '.join(els), net_r_min=0.5,
                           log_values=True, net_method='spearman', data_type='Element Mass (fg)')
    linked = {frozenset((els[i], els[j])) for i, j, _r, _n in hd['network']['edges']}
    expected = {frozenset((a, b)) for a, b, rho, _n in
                F._pair_correlations(context(t), els, 'mass') if abs(rho) >= 0.5}
    assert linked == expected and linked


def test_network_story_keeps_to_its_own_elements():
    """The combinations panel lists the group's elements, not every isotope measured."""
    story = F._network(card('network', ('56Fe', '28Si', '27Al')), context(powder()))
    assert all(p['isotopes'] == '56Fe, 28Si, 27Al' for p, _c in story)
    assert story[0][0]['net_method'] == 'spearman'

