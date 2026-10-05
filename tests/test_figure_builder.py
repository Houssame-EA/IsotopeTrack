"""Tests for the Figure Builder node (results/figure_builder)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder import engine as E
from results.figure_builder.expressions import (
    ExpressionError, ParticleTable, evaluate, pretty, split_list)


def make_input(n=600, multi=True, classifier=False, seed=3):
    """Synthetic canvas stream with three samples and Ag/Au/Fe isotopes."""
    rng = np.random.default_rng(seed)
    samples = ['Blank', 'Ag NP', 'AgAu']
    parts = []
    for i in range(n):
        ag = rng.lognormal(4 + (i % 3) * 0.4, 0.4)
        au = rng.lognormal(3.5, 0.6) if i % 2 else 0.0
        fe = rng.lognormal(3, 0.5)
        el = {k: v for k, v in {'107Ag': ag, '197Au': au, '56Fe': fe}.items() if v > 0}
        p = {'source_sample': samples[i % 3] if multi else 'S1', 'elements': el,
             'element_mass_fg': {k: v / 100 for k, v in el.items()}, 'start_time': i * 1e-3}
        if classifier:
            p['_classifier_bucket'] = 'AgAu' if au else 'Ag-only'
        parts.append(p)
    data = {'type': 'multiple_sample_data' if multi else 'sample_data', 'particle_data': parts,
            'selected_isotopes': [{'label': '107Ag'}, {'label': '197Au'}, {'label': '56Fe'}]}
    if multi:
        data['sample_names'] = samples
    else:
        data['sample_name'] = 'S1'
    if classifier:
        data['_classifier_registry'] = {'Ag-only': {'color': '#1baf7a'}, 'AgAu': {'color': '#4a3aa7'}}
    return data


@pytest.fixture
def table():
    return ParticleTable.from_input(make_input(classifier=True))


def test_table_labels_and_aliases(table):
    assert table.labels == ['107Ag', '197Au', '56Fe']
    assert table.symbol_aliases() == {'Ag': '107Ag', 'Au': '197Au', 'Fe': '56Fe'}
    assert len(table) == 600


def test_arithmetic_and_aliases(table):
    a = evaluate('Ag', table)
    b = evaluate('107Ag', table)
    assert np.array_equal(a, b)
    ratio = evaluate('Ag/Fe', table)
    assert np.allclose(ratio, a / evaluate('Fe', table))
    assert np.allclose(evaluate('`107Ag` * 2', table), 2 * a)


def test_other_quantities_and_specials(table):
    assert np.allclose(evaluate('mass:Ag', table), evaluate('Ag', table) / 100)
    total = evaluate('total', table)
    assert np.allclose(total, evaluate('Ag', table) + evaluate('Au', table) + evaluate('Fe', table))
    assert set(np.unique(evaluate('n_elements', table))) <= {2.0, 3.0}


def test_conditions_and_text(table):
    m = evaluate('sample == "Blank" and Ag > median(Ag)', table, as_mask=True)
    assert m.dtype == bool and 0 < m.sum() < 200
    assert evaluate('sample in ["Blank", "AgAu"]', table, as_mask=True).sum() == 400
    assert evaluate('class == "AgAu"', table, as_mask=True).sum() == 300
    assert evaluate('not (Au > 0)', table, as_mask=True).sum() == 300


@pytest.mark.parametrize('bad', ['Zn', 'Ag +', '__import__("os")', 'Ag.real',
                                 'open("x")', '(lambda: 1)()', 'sample + 1'])
def test_rejects_bad_expressions(table, bad):
    with pytest.raises(ExpressionError):
        evaluate(bad, table)


def test_pretty_labels(table):
    assert pretty('Ag', table) == r'$^{107}$Ag (counts)'
    assert pretty('mass:Fe', table) == r'$^{56}$Fe mass (fg)'
    assert pretty('Ag/Au', table, 'symbol') == 'Ag/Au'


def test_split_list():
    assert split_list('Ag, max(Fe, Au), "a,b"') == ['Ag', 'max(Fe, Au)', '"a,b"']


def test_rule_groups_first_match_wins(table):
    panel = E.make_panel(group_by='rules', rules=[
        {'name': 'low', 'when': 'Ag < 60', 'color': '#ff0000'},
        {'name': 'low2', 'when': 'Ag < 100', 'color': '#00ff00'}])
    groups = E.resolve_groups(panel, table)
    assert [g.name for g in groups] == ['low', 'low2', 'Other']
    stacked = np.vstack([g.mask for g in groups]).sum(axis=0)
    assert np.all(stacked == 1)


def test_class_groups_use_classifier_colors(table):
    groups = E.resolve_groups(E.make_panel(group_by='class'), table)
    assert {g.name: g.color for g in groups} == {'Ag-only': '#1baf7a', 'AgAu': '#4a3aa7'}


def test_holm_correction_is_monotone():
    adj = E._correct([0.01, 0.04, 0.03], 'holm')
    assert adj == pytest.approx([0.03, 0.06, 0.06])
    assert E._correct([0.2, 0.3], 'bonferroni') == pytest.approx([0.4, 0.6])


def _render(spec, table):
    fig = Figure()
    FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    fig.canvas.draw()
    return report


@pytest.mark.parametrize('panel', [
    dict(kind='scatter', x='Ag', y='Ag/Fe', y2='mass:Fe', log_x=True, log_y=True,
         group_by='rules', rules=[{'name': 'r', 'when': 'Ag/Fe < 3', 'color': '#e34948'}],
         show_fit=True, show_r=True, hlines='3', diagonal=True),
    dict(kind='scatter', x='Ag', y='Fe', color_by='total'),
    dict(kind='histogram', value='Ag', log_x=True, group_by='sample', test='ks'),
    dict(kind='box', value='Ag', log_y=True, group_by='sample', test='welch',
         correction='holm', show_points=True),
    dict(kind='violin', value='Ag', log_y=True, group_by='class', test='mannwhitney'),
    dict(kind='bar', value='Ag, Au, Fe', group_by='sample', error='sem'),
    dict(kind='bar', value='Ag', group_by='sample', test='anova'),
    dict(kind='pie', group_by='class', donut=True),
    dict(kind='pie', pie_mode='values', value='Ag, Au, Fe'),
    dict(kind='density', x='Ag', y='Fe', log_x=True, log_y=True),
    dict(kind='ternary', a='Ag', b='Au', c='Fe', group_by='sample', drop_zeros=False),
    dict(kind='text', text='Hello'),
    dict(kind='code', code="ax.plot(df['total'].values[:10]); report('ok')"),
])
def test_every_kind_renders(table, panel):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(**panel)]
    report = _render(spec, table)
    assert report.errors == {}


def test_stats_report_contains_tests(table):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(kind='box', value='Ag', group_by='sample', test='student')]
    report = _render(spec, table)
    assert len(report.stats) == 3
    assert all("Student's t-test" in s for s in report.stats)


def test_broken_panel_does_not_break_others(table):
    spec = E.default_spec()
    good = E.make_panel(rect=[0, 0, 0.5, 1], kind='scatter', x='Ag', y='Fe')
    bad = E.make_panel(rect=[0.5, 0, 0.5, 1], kind='scatter', x='Zn', y='Fe')
    spec['panels'] = [good, bad]
    report = _render(spec, table)
    assert list(report.errors) == [bad['id']]
    assert report.counts[good['id']] > 0


def test_empty_data_reports_error():
    report = _render(E.default_spec(), ParticleTable.from_input(None))
    assert len(report.errors) == 1


def test_spec_is_json_serialisable_and_normalises():
    spec = E.apply_template(E.default_spec(), '2 × 2')
    again = E.normalise_spec(json.loads(json.dumps(spec)))
    assert again == E.normalise_spec(spec)
    assert len(again['panels']) == 4
    partial = E.normalise_spec({'panels': [{'kind': 'pie'}]})
    assert partial['panels'][0]['id'] and partial['figure']['width'] == 8.0


def test_node_fills_axes_from_data():
    from results.figure_builder import FigureBuilderNode
    node = FigureBuilderNode()
    node.process_data(make_input(multi=False))
    panel = node.config['panels'][0]
    assert (panel['x'], panel['y']) == ('107Ag', '197Au')
    assert len(node.build_table()) == 600


def test_dialog_draws_panel_with_mouse():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from results.figure_builder import FigureBuilderDialog, FigureBuilderNode
    node = FigureBuilderNode()
    node.process_data(make_input())
    node.config['panels'][0]['rect'] = [0, 0, 0.5, 1]
    dlg = FigureBuilderDialog(node)
    dlg.resize(1200, 800)
    dlg.show()
    QTest.qWait(50)
    sk = dlg.sketch
    page = sk.page_rect()

    def pt(fx, fy):
        return QPoint(int(page.x() + fx * page.width()), int(page.y() + fy * page.height()))

    QTest.mousePress(sk, Qt.LeftButton, Qt.NoModifier, pt(0.6, 0.1))
    QTest.mouseMove(sk, pt(0.9, 0.9))
    QTest.mouseRelease(sk, Qt.LeftButton, Qt.NoModifier, pt(0.9, 0.9))
    assert len(node.config['panels']) == 2
    QTest.mousePress(sk, Qt.LeftButton, Qt.ShiftModifier, pt(0.1, 0.1))
    QTest.mouseMove(sk, pt(0.4, 0.4))
    QTest.mouseRelease(sk, Qt.LeftButton, Qt.ShiftModifier, pt(0.4, 0.4))
    assert len(node.config['panels']) == 3
    dlg._render()
    assert dlg._last_report.errors == {}
    assert dlg.export_bytes('png', 50)[:4] == b'\x89PNG'
    dlg.close()
