"""Figure details: share intervals, slim bars, tidy log ticks, raised isotopes, page layout."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder.charts.categorical import _stacked_labels, wilson_interval
from results.figure_builder.core.engine import make_panel, normalise_spec, render
from results.figure_builder.core.expressions import ParticleTable
from results.insights import figures as F


def table(n=400, spread=1.0):
    """Two samples; Au is in half of S1's particles and a fifth of S2's."""
    rng = np.random.default_rng(4)
    parts = []
    for i in range(n):
        sample = 'S1' if i % 2 else 'S2'
        el = {'107Ag': float(rng.lognormal(4, spread)), '56Fe': float(rng.lognormal(3, spread))}
        if (i // 2) % (2 if sample == 'S1' else 5) == 0:
            el['197Au'] = float(rng.lognormal(3, 0.5))
        parts.append({'source_sample': sample, 'elements': el,
                      'element_mass_fg': {k: v / 100 for k, v in el.items()},
                      'start_time': i * 1e-3})
    return ParticleTable.from_input({'type': 'multiple_sample_data', 'particle_data': parts,
                                     'sample_names': ['S1', 'S2']})


def one(t, figure=None, **panel):
    """Draw one panel and return its axes after a full draw."""
    spec = normalise_spec({'figure': figure or {}, 'panels': [make_panel(**panel)]})
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = render(fig, spec, t)
    assert report.errors == {}
    canvas.draw()
    return report.artists[spec['panels'][0]['id']]['ax']


def test_wilson_interval_matches_known_values():
    """Checked against the textbook 5 of 10 case, and sane at the ends."""
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    lo, hi = wilson_interval(0, 50)
    assert lo == 0.0 and 0.0 < hi < 0.1
    lo, hi = wilson_interval(50, 50)
    assert hi == 1.0 and 0.9 < lo < 1.0
    assert all(np.isnan(v) for v in wilson_interval(0, 0))


def test_share_bars_carry_their_interval_and_label_clears_it():
    """A share with 95% CI gets a whisker; the value is written above its upper end."""
    ax = one(table(), kind='bar', value='Au', agg='detect_pct', group_by='sample',
             error='ci95', bar_values=True)
    heights = [r.get_height() for r in ax.patches]
    assert heights == pytest.approx([50.0, 20.0])
    segments = [seg for coll in ax.collections for seg in coll.get_segments()]
    assert len(segments) == 2
    for seg, h, n in zip(sorted(segments, key=lambda s: -s[1][1]), heights, (200, 200)):
        lo, hi = wilson_interval(round(h * n / 100), n)
        assert seg[0][1] == pytest.approx(100 * lo) and seg[1][1] == pytest.approx(100 * hi)
    labels = {t.get_text(): t for t in ax.texts}
    assert set(labels) == {'50%', '20%'}
    assert labels['50%'].xy[1] > 50.0
    assert ax.get_ylim()[1] > labels['50%'].xy[1]


def test_share_bars_without_ci_have_no_whisker():
    """Other error settings leave a share as a plain bar."""
    ax = one(table(), kind='bar', value='Au', agg='detect_pct', group_by='sample', error='sd')
    assert [seg for coll in ax.collections for seg in coll.get_segments()] == []


def test_few_bars_stay_slim():
    """Two bars leave room at the sides instead of filling the panel."""
    ax = one(table(), kind='bar', value='Au', agg='detect_pct', group_by='sample')
    lo, hi = ax.get_xlim()
    assert lo < -0.6 and hi > 1.6
    assert sum(r.get_width() for r in ax.patches) / (hi - lo) < 0.6


def test_long_category_labels_move_their_brackets_to_a_second_line():
    """Labels that would touch are stacked; labels that fit are left alone."""
    fig = Figure(figsize=(8, 6))
    wide = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    narrow = fig.add_axes([0.1, 0.1, 0.3, 0.8])
    cats = ['Small (< 0.949 fg)', 'Medium (0.949–2.04 fg)', 'Large (≥ 2.04 fg)']
    assert _stacked_labels(wide, cats) == cats
    assert _stacked_labels(narrow, cats) == ['Small\n(< 0.949 fg)', 'Medium\n(0.949–2.04 fg)',
                                             'Large\n(≥ 2.04 fg)']
    assert _stacked_labels(narrow, ['S1', 'S2']) == ['S1', 'S2']


def tick_texts(axis):
    """Non-empty tick labels of an axis, major and minor."""
    return [t.get_text() for t in axis.get_ticklabels(which='both') if t.get_text()]


def test_log_axis_under_a_decade_has_plain_round_ticks():
    """No 2×10⁰: a narrow log axis is labelled 100, 120, 140."""
    ax = one(table(spread=0.05), kind='scatter', x='Ag', y='Fe', log_x=True, log_y=True)
    lo, hi = ax.get_xlim()
    assert hi / lo < 10
    texts = tick_texts(ax.xaxis)
    assert len(texts) >= 3
    assert all('times' not in t and '10^' not in t for t in texts)
    assert all(lo * 0.5 < float(t) < hi * 2 for t in texts)


def test_log_axis_over_decades_keeps_powers_of_ten():
    """A wide log axis is unchanged."""
    ax = one(table(spread=1.5), kind='scatter', x='Ag', y='Fe', log_x=True, log_y=True)
    assert any('10^' in t for t in tick_texts(ax.xaxis))


def test_chosen_tick_format_is_left_alone():
    """A tick format set by the user wins over the tidy ticks."""
    ax = one(table(spread=0.05), kind='scatter', x='Ag', y='Fe', log_x=True, x_format='1dp')
    assert all('.' in t and len(t.split('.')[1]) == 1 for t in tick_texts(ax.xaxis))


def test_title_and_labels_raise_the_isotopes_the_data_holds():
    """Typed titles match the automatic labels; other words keep their digits."""
    ax = one(table(), kind='histogram', value='Ag', title='107Ag in sample 10X',
             x_label='107Ag counts')
    assert ax.get_title() == '$^{107}$Ag in sample 10X'
    assert ax.get_xlabel() == '$^{107}$Ag counts'


def test_raw_label_style_keeps_titles_as_typed():
    """With isotopes written as typed, nothing is raised."""
    ax = one(table(), figure={'label_style': 'raw'}, kind='histogram', value='Ag',
             title='107Ag by sample')
    assert ax.get_title() == '107Ag by sample'


def test_contour_points_can_be_drawn_larger_and_on_top():
    """The points of a contour panel follow the size and layer asked for."""
    ax = one(table(), kind='contour', x='Ag', y='Fe', log_x=True, log_y=True, show_points=True,
             points_size=9, points_alpha=0.7, points_zorder=4)
    dots = [c for c in ax.collections if len(c.get_offsets()) > 50]
    assert dots and dots[0].get_sizes()[0] == 9 and dots[0].get_zorder() == 4


def test_sparse_cloud_gets_contours_and_a_dense_one_a_density_map(monkeypatch):
    """A map of counts per cell is drawn only when the cells would hold enough particles."""
    t = table()
    ctx = F.FigureContext({'counts'}, {}, {}, True, 2, table=t)
    panel, caption = F._where_most(ctx, '107Ag', '56Fe', '107Ag > 0 and 56Fe > 0', 'x', 'y')
    assert panel['kind'] == 'contour' and panel['show_points'] and 'contours' in caption
    monkeypatch.setattr(F, 'DENSE_PARTICLES', 100)
    panel, caption = F._where_most(ctx, '107Ag', '56Fe', '107Ag > 0 and 56Fe > 0', 'x', 'y')
    assert panel['kind'] == 'hexbin' and 'density map' in caption
    bare = F.FigureContext({'counts'}, {}, {}, True, 2)
    assert F._where_most(bare, '107Ag', '56Fe', '', 'x', 'y')[0]['kind'] == 'hexbin'


def rows(*kinds):
    """Rows as by_groups returns them, two panels in a split row."""
    return [([{}] if k == 'wide' else [{}, {}], '', k) for k in kinds]


def test_full_width_panels_pair_up_two_to_a_line():
    """Four spanning panels fill two lines, each panel half the width."""
    rects, caption, width, height = F.rows_layout(rows('wide', 'wide', 'wide', 'wide'), 2, 'x')
    assert [r[2] for r in rects] == [0.5] * 4
    assert [r[0] for r in rects] == [0.0, 0.5, 0.0, 0.5]
    assert rects[0][1] == rects[1][1] and rects[2][1] == rects[3][1] > rects[0][1]
    assert height < 2 * 3.9 + 1.5
    assert caption[1] == pytest.approx(rects[-1][1] + rects[-1][3])


def test_odd_panel_and_split_rows_keep_their_own_line():
    """A split row breaks the pairing, and a spanning panel left over stays full width."""
    assert F._lines(rows('wide', 'split', 'wide', 'wide', 'wide'), 2) == [[0], [1], [2, 3], [4]]
    rects, _c, _w, _h = F.rows_layout(rows('wide', 'split', 'wide'), 2, 'x')
    assert [r[2] for r in rects] == [1.0, 0.5, 0.5, 1.0]


def test_many_groups_keep_full_width_panels():
    """Beyond four groups a half-width panel drawing every group would be cramped."""
    by_sample = [([{'group_by': 'sample'}], '', 'wide') for _ in range(3)]
    assert F._lines(by_sample, 5) == [[0], [1], [2]]
