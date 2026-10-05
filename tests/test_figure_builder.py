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
    adj = E.correct([0.01, 0.04, 0.03], 'holm')
    assert adj == pytest.approx([0.03, 0.06, 0.06])
    assert E.correct([0.2, 0.3], 'bonferroni') == pytest.approx([0.4, 0.6])


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


def test_variables_are_usable_and_validated(table):
    problems = table.set_variables([
        {'name': 'agfe', 'expr': 'Ag/Fe'},
        {'name': 'twice', 'expr': 'agfe * 2'},
        {'name': 'loop', 'expr': 'loop + 1'},
        {'name': 'Ag', 'expr': '1'},
        {'name': '1bad', 'expr': 'Ag'},
    ])
    assert set(problems) == {'loop', 'Ag', '1bad'}
    assert np.allclose(evaluate('twice', table), 2 * evaluate('Ag', table) / evaluate('Fe', table))
    assert 'agfe' in table.dataframe().columns


def test_render_installs_spec_variables(table):
    spec = E.default_spec()
    spec['variables'] = [{'name': 'r', 'expr': 'Ag/Fe'}, {'name': 'oops', 'expr': 'Zn'}]
    spec['panels'] = [E.make_panel(kind='histogram', value='r', log_x=True)]
    report = _render(spec, table)
    assert report.errors == {}
    assert list(report.variable_errors) == ['oops']


def test_group_overrides(table):
    panel = E.make_panel(group_by='sample', hidden_groups=['AgAu'],
                         group_labels={'Blank': 'Procedural blank'},
                         group_colors={'Blank': '#000000'}, group_order=['Ag NP', 'Blank'])
    groups = E.resolve_groups(panel, table)
    assert [g.label for g in groups] == ['Ag NP', 'Procedural blank']
    assert groups[1].color == '#000000' and groups[1].key == 'Blank'


def test_palette_drives_group_colours(table):
    from results.figure_builder import styles as S
    spec = E.default_spec()
    spec['figure']['palette'] = 'Tableau'
    spec['panels'] = [E.make_panel(kind='box', value='Ag', group_by='sample')]
    fig = Figure()
    FigureCanvasAgg(fig)
    E.render(fig, spec, table)
    from matplotlib.colors import to_hex
    faces = [to_hex(p.get_facecolor(), keep_alpha=False) for p in fig.axes[0].patches]
    assert faces[:3] == [c.lower() for c in S.PALETTES['Tableau'][:3]]


@pytest.mark.parametrize('panel', [
    dict(kind='line', x='time', y='Ag', group_by='sample', band='sd', show_points=True),
    dict(kind='line', x='time', bins=20),
    dict(kind='histogram', value='Ag', log_x=True, kde=True, density=True),
    dict(kind='histogram', value='Ag', cumulative=True, group_by='sample'),
    dict(kind='bar', value='Ag, Au', group_by='sample', stacked=True, horizontal=True),
    dict(kind='bar', value='Ag', group_by='class', horizontal=True, log_y=True),
    dict(kind='box', value='Ag', group_by='sample', notch=True, show_mean=True, hide_ns=True,
         test='welch', xtick_rotation=45, show_n=False),
    dict(kind='violin', value='Ag', group_by='sample', show_mean=True),
    dict(kind='scatter', x='Ag', y='Fe', size_by='Au', marker='D', edge_width=0.5,
         frame='box', tick_dir='in', minor_ticks=True, sci_x=True, sci_y=True,
         legend_loc='outside right', group_by='sample', aspect_equal=True,
         series=[{'label': 's', 'x': 'Ag', 'y': 'Au', 'filter': 'Au > 0', 'style': 'points+line',
                  'marker': 'x', 'size': 10}],
         annotations=[{'text': 'here', 'x': '0.1', 'y': '0.9', 'arrow_x': '0.5',
                       'arrow_y': '0.5', 'box': True, 'bold': True},
                      {'text': 'data', 'x': '100', 'y': '50', 'coords': 'data'}]),
    dict(kind='scatter', x='Ag', y='Fe', legend_loc='below', group_by='class', frame='none'),
    dict(kind='pie', group_by='sample', legend_loc='outside right', edge_width=1.0),
    dict(kind='density', x='Ag', y='Fe', reverse_cmap=True, colormap='magma'),
    dict(kind='text', text='Caption', text_size=14, title='Notes'),
])
def test_v2_options_render(table, panel):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(**panel)]
    report = _render(spec, table)
    assert report.errors == {}


@pytest.mark.parametrize('name', ['Long blank', 'A very long procedural blank name, batch 2026'])
def test_outside_legend_fits_inside_panel(table, name):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(rect=[0, 0, 0.5, 1], kind='scatter', x='Ag', y='Fe',
                                   group_by='sample', legend_loc='outside right',
                                   group_labels={'Blank': name})]
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    E.render(fig, spec, table)
    canvas.draw()
    leg = fig.axes[0].get_legend()
    box = leg.get_window_extent(canvas.get_renderer()).transformed(fig.transFigure.inverted())
    assert box.x1 <= 0.5 + 1e-3
    assert fig.axes[0].get_position().width > 0.15


def test_style_presets_and_strip():
    from results.figure_builder import styles as S
    spec = E.apply_template(E.default_spec(), '2 × 2')
    for name in S.STYLE_PRESETS:
        styled = S.apply_style_preset(spec, name)
        assert styled['panels'][0]['id'] == spec['panels'][0]['id']
    pres = S.apply_style_preset(spec, 'Presentation')
    assert pres['figure']['font_size'] == 16
    assert all(p['grid'] for p in pres['panels'])
    small = E.strip_spec(pres)
    assert 'marker' not in small['panels'][0]
    assert E.normalise_spec(small)['figure']['font_size'] == 16


def test_summary_frame(table):
    from results.figure_builder.dataview import summary_frame
    df = summary_frame(table, 'sample')
    row = df[(df['group'] == 'Blank') & (df['column'] == '197Au')].iloc[0]
    assert row['particles'] == 200 and row['detected'] == 100


@pytest.fixture
def dialog(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from results.figure_builder import dialog as D
    monkeypatch.setattr(D, 'SETTINGS', ('IsotopeTrackTests', 'FigureBuilderTests'))
    node = D.FigureBuilderNode()
    node.process_data(make_input(classifier=True))
    dlg = D.FigureBuilderDialog(node)
    dlg.resize(1300, 850)
    dlg.show()
    yield dlg
    from PySide6.QtCore import QSettings
    QSettings('IsotopeTrackTests', 'FigureBuilderTests').clear()
    dlg.close()


def test_dialog_undo_redo_and_add_panel(dialog):
    dialog._render()
    before = len(dialog.spec['panels'])
    dialog.add_panel('histogram')
    dialog._render()
    assert len(dialog.spec['panels']) == before + 1
    assert dialog.spec['panels'][-1]['value'] == '107Ag'
    dialog.undo()
    assert len(dialog.spec['panels']) == before
    assert dialog.node.config is dialog.spec
    dialog.redo()
    assert len(dialog.spec['panels']) == before + 1


def test_dialog_designs_round_trip(dialog):
    dialog._apply_style('Presentation')
    dialog.spec['variables'] = [{'name': 'r', 'expr': 'Ag/Fe'}]
    designs = dialog.saved_designs()
    designs['mine'] = E.strip_spec(dialog.spec)
    dialog._store_designs(designs)
    dialog._load_spec(E.default_spec())
    assert dialog.spec['figure']['font_size'] == 11
    dialog.apply_design(dialog.saved_designs()['mine'])
    assert dialog.spec['figure']['font_size'] == 16
    assert dialog.spec['variables'] == [{'name': 'r', 'expr': 'Ag/Fe'}]
    dialog._render()
    assert dialog._last_report.errors == {}


def test_dialog_preview_click_selects_panel(dialog):
    dialog._apply_template('Side by side')
    right = dialog.spec['panels'][1]['id']
    dialog._on_preview_click(0.8, 0.5)
    assert dialog.sketch.selected == right
    assert dialog.editor.panel is dialog.spec['panels'][1]


def test_dialog_variables_tab(dialog):
    dialog.var_table.set_rows([{'name': 'agfe', 'expr': 'Ag/Fe'}])
    dialog._on_variables()
    assert dialog.spec['variables'] == [{'name': 'agfe', 'expr': 'Ag/Fe'}]
    assert 'agfe' in dialog.table.names()
    dialog.spec['panels'][0]['y'] = 'agfe'
    dialog._render()
    assert dialog._last_report.errors == {}
