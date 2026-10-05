"""Tests for the Figure Builder node (results/figure_builder)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder.core import engine as E
from results.figure_builder.core.expressions import (
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
    from results.figure_builder.core import styles as S
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
    from results.figure_builder.core import styles as S
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
    from results.figure_builder.ui.dataview import summary_frame
    df = summary_frame(table, 'sample')
    row = df[(df['group'] == 'Blank') & (df['column'] == '197Au')].iloc[0]
    assert row['particles'] == 200 and row['detected'] == 100


@pytest.fixture
def dialog(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from results.figure_builder.ui import dialog as D
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
    assert dialog.spec['figure']['font_size'] == 12
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


@pytest.mark.parametrize('panel', [
    dict(kind='corr_matrix', log_values=True, show_sig=True, triangle='lower', corr_method='spearman'),
    dict(kind='corr_matrix', isotopes='Ag, Fe, Ag/Fe', corr_method='kendall', annotate=False),
    dict(kind='heatmap', group_by='sample', heat_value='detect'),
    dict(kind='heatmap', group_by='class', heat_value='median', heat_norm='zscore', transpose=True),
    dict(kind='heatmap', heat_rows='combinations', top_n=5, log_color=True),
    dict(kind='heatmap', heat_rows='particles', max_rows=50),
    dict(kind='cooccurrence', cooc_mode='conditional', triangle='upper'),
    dict(kind='cooccurrence', cooc_mode='count'),
    dict(kind='combinations', group_by='sample', horizontal=True, combo_filter='multi'),
    dict(kind='combinations', as_percent=False, top_n=3),
    dict(kind='composition', group_by='sample', comp_mode='total', horizontal=True),
    dict(kind='composition', group_by='class', isotopes='mass:Ag, mass:Au',
         item_labels={'mass:Ag': 'Silver'}),
    dict(kind='pairs', isotopes='Ag, Au, Fe', log_values=True, group_by='sample'),
    dict(kind='pairs', isotopes='Ag, Fe', pairs_upper='scatter'),
])
def test_new_chart_kinds_render(table, panel):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(**panel)]
    report = _render(spec, table)
    assert report.errors == {}
    assert report.counts[spec['panels'][0]['id']] > 0


def test_corr_matrix_values(table):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(kind='corr_matrix', isotopes='Ag, total')]
    report = _render(spec, table)
    assert any('107Ag vs total' in s for s in report.stats)
    assert not any('$' in s for s in report.stats)


def test_per_panel_quantity(table):
    spec = E.default_spec()
    counts = E.make_panel(rect=[0, 0, 0.5, 1], kind='scatter', x='Ag', y='Fe')
    mass = E.make_panel(rect=[0.5, 0, 0.5, 1], kind='scatter', x='Ag', y='Fe',
                        data_type='Element Mass (fg)')
    spec['panels'] = [counts, mass]
    fig = Figure()
    FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    assert report.errors == {}
    a1 = report.artists[counts['id']]['ax']
    a2 = report.artists[mass['id']]['ax']
    assert 'counts' in a1.get_xlabel() and 'mass (fg)' in a2.get_xlabel()
    assert a2.get_xlim()[1] < a1.get_xlim()[1]


def test_text_styles_figure_and_panel(table):
    spec = E.default_spec()
    spec['figure']['title'] = 'Main'
    spec['figure']['text_styles'] = {'ticks': {'bold': True, 'size': 7},
                                     'figure_title': {'italic': True}}
    panel = E.make_panel(kind='scatter', x='Ag', y='Fe', title='T',
                         text_styles={'x_label': {'italic': True, 'color': '#ff0000', 'size': 15},
                                      'title': {'bold': False}})
    spec['panels'] = [panel]
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    canvas.draw()
    ax = report.artists[panel['id']]['ax']
    assert ax.xaxis.label.get_style() == 'italic'
    assert ax.xaxis.label.get_color() == '#ff0000'
    assert ax.xaxis.label.get_fontsize() == 15
    assert ax.title.get_weight() == 'normal'
    assert ax.yaxis.label.get_style() == 'normal'
    labels = ax.get_xticklabels()
    assert labels and all(t.get_weight() == 'bold' and t.get_fontsize() == 7 for t in labels)
    assert fig._suptitle.get_style() == 'italic'


def test_ternary_corner_labels_and_styles(table):
    spec = E.default_spec()
    panel = E.make_panel(kind='ternary', a='Ag', b='Au', c='Fe', drop_zeros=False,
                         a_label='Silver', text_styles={'corner_labels': {'bold': True}})
    spec['panels'] = [panel]
    report = _render(spec, table)
    ax = report.artists[panel['id']]['ax']
    assert ax.taxis.label.get_text() == 'Silver'
    assert ax.taxis.label.get_weight() == 'bold'
    assert ax.laxis.label.get_weight() == 'bold'


def test_hits_find_labels(dialog):
    from results.figure_builder.ui import interact
    dialog.apply_layout('Side by side')
    p0, p1 = dialog.spec['panels']
    dialog.set_panel_kind(p1, 'ternary')
    p0['title'] = 'Left'
    dialog._render()
    elements = {(h.panel_id, h.element) for h in dialog._hits}
    for el in ('title', 'x_label', 'y_label', 'plot', 'ticks_x'):
        assert (p0['id'], el) in elements
    for el in ('corner_a', 'corner_b', 'corner_c'):
        assert (p1['id'], el) in elements
    yl = next(h for h in dialog._hits if h.panel_id == p0['id'] and h.element == 'y_label')
    cx, cy = (yl.box[0] + yl.box[2]) / 2, (yl.box[1] + yl.box[3]) / 2
    assert interact.hit_at(dialog._hits, cx, cy).element == 'y_label'


def test_double_click_renames_and_menus(dialog, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from results.figure_builder.ui import interact
    p0 = dialog.spec['panels'][0]
    dialog._render()
    xl = next(h for h in dialog._hits if h.panel_id == p0['id'] and h.element == 'x_label')
    monkeypatch.setattr(QInputDialog, 'getText', staticmethod(lambda *a, **k: ('Silver signal', True)))
    dialog._on_preview_double((xl.box[0] + xl.box[2]) / 2, (xl.box[1] + xl.box[3]) / 2)
    assert p0['x_label'] == 'Silver signal'
    menu = interact.build_menu(dialog, xl, 0.5, 0.9)
    texts = [a.text() for a in menu.actions()]
    assert 'Bold' in texts and 'Italic' in texts
    next(a for a in menu.actions() if a.text() == 'Italic').trigger()
    assert p0['text_styles']['x_label']['italic'] is True
    plot = next(h for h in dialog._hits if h.panel_id == p0['id'] and h.element == 'plot')
    pm = interact.build_menu(dialog, plot, 0.5, 0.5)
    names = [a.text() for a in pm.actions()]
    for wanted in ('Chart type', 'Quantity (unit)', 'Log X', 'Add', 'Delete panel'):
        assert wanted in names
    quantity = next(a for a in pm.actions() if a.text() == 'Quantity (unit)').menu()
    next(a for a in quantity.actions() if a.text() == 'Element Mass (fg)').trigger()
    assert p0['data_type'] == 'Element Mass (fg)'
    page = interact.build_menu(dialog, None, 0.5, 0.5)
    add = next(a for a in page.actions() if a.text() == 'Add panel here').menu()
    before = len(dialog.spec['panels'])
    next(a for a in add.actions() if a.text() == 'Correlation matrix').trigger()
    assert len(dialog.spec['panels']) == before + 1
    assert dialog.spec['panels'][-1]['kind'] == 'corr_matrix'
    dialog._render()
    assert dialog._last_report.errors == {}


def test_sidebar_toggle(dialog):
    dialog._toggle_sidebar(False)
    assert not dialog.left_panel.isVisible()
    dialog.show_editor_tab('Groups')
    assert dialog.left_panel.isVisible()
    assert dialog.editor.tabs.tabText(dialog.editor.tabs.currentIndex()) == 'Groups'


def test_node_thumbnail_without_window():
    from results.figure_builder import FigureBuilderNode
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    node = FigureBuilderNode()
    node.process_data(make_input())
    pm = node._figure_thumbnail
    assert pm is not None and not pm.isNull() and pm.width() == 420
    assert node._figure_thumbnail is pm
    node._figure_thumbnail = None
    assert node._figure_thumbnail is pm
    node.config['panels'][0]['kind'] = 'histogram'
    node.config['panels'][0]['value'] = 'Ag'
    assert node._figure_thumbnail is not pm


def test_decorations_stay_inside_panels(table):
    spec = E.apply_template(E.default_spec(), '2 × 2')
    for p, kind in zip(spec['panels'], ('scatter', 'corr_matrix', 'box', 'ternary')):
        p.update(kind=kind, x='Ag', y='Fe', value='Ag', a='Ag', b='Au', c='Fe', log_x=True,
                 log_y=True, x_min='40', x_max='70', group_by='sample', drop_zeros=False,
                 y_label='A rather long label for the vertical axis')
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    canvas.draw()
    renderer = canvas.get_renderer()
    for p in spec['panels']:
        ax = report.artists[p['id']]['ax']
        tb = ax.get_tightbbox(renderer).transformed(fig.transFigure.inverted())
        x, y, w, h = p['rect']
        assert tb.x0 >= x - 0.01 and tb.x1 <= x + w + 0.01
        assert tb.y0 >= 1 - y - h - 0.01 and tb.y1 <= 1 - y + 0.01


def test_hover_readouts(dialog):
    from results.figure_builder.ui import direct
    dialog.apply_layout('2 × 2')
    p0, p1, p2, p3 = dialog.spec['panels']
    dialog.set_panel_kind(p1, 'corr_matrix')
    dialog.set_panel_kind(p2, 'box')
    p2['group_by'] = 'sample'
    dialog.set_panel_kind(p3, 'histogram')
    dialog._render()
    fig = dialog.last_fig

    def frac(ax, x, y):
        fx, fy = fig.transFigure.inverted().transform(ax.transData.transform((x, y)))
        return fx, 1 - fy

    hd = dialog.last_report.artists[p0['id']]
    layer = hd['points'][0]
    fx, fy = frac(hd['ax'], layer['x'][0], layer['y'][0])
    text = direct.readout(dialog, dialog._hit(fx, fy), fx, fy)
    assert text.startswith('Particle #') and 'sample:' in text
    fx, fy = frac(dialog.last_report.artists[p1['id']]['ax'], 0, 1)
    assert 'Pearson r' in direct.readout(dialog, dialog._hit(fx, fy), fx, fy)
    fx, fy = frac(dialog.last_report.artists[p2['id']]['ax'], 2, 80)
    assert 'Ag NP' in direct.readout(dialog, dialog._hit(fx, fy), fx, fy)
    ax3 = dialog.last_report.artists[p3['id']]['ax']
    fx, fy = frac(ax3, sum(ax3.get_xlim()) / 2, sum(ax3.get_ylim()) / 2)
    assert 'particles in' in direct.readout(dialog, dialog._hit(fx, fy), fx, fy)


def test_drags_move_legend_zoom_and_panels(dialog):
    p0 = dialog.spec['panels'][0]
    p0['group_by'] = 'sample'
    p0['annotations'] = [{'text': 'note', 'x': '0.1', 'y': '0.9', 'coords': 'axes'}]
    dialog._render()
    leg = next(h for h in dialog._hits if h.element == 'legend')
    cx, cy = (leg.box[0] + leg.box[2]) / 2, (leg.box[1] + leg.box[3]) / 2
    assert dialog._drag_resolver(cx, cy)[0] == 'legend'
    dialog._on_drag_finished('legend', cx, cy, cx - 0.2, cy + 0.2)
    assert p0['legend_loc'] == 'custom' and len(p0['legend_xy']) == 2
    note = next(h for h in dialog._hits if h.element == 'annotation')
    nx, ny = (note.box[0] + note.box[2]) / 2, (note.box[1] + note.box[3]) / 2
    assert dialog._drag_resolver(nx, ny)[0] == 'note'
    dialog._on_drag_finished('note', nx, ny, nx + 0.1, ny + 0.1)
    assert float(p0['annotations'][0]['x']) > 0.15
    dialog._render()
    plot = next(h for h in dialog._hits if h.element == 'plot')
    sx, sy = plot.box[0] + 0.02, plot.box[1] + 0.02
    ex, ey = plot.box[2] - 0.05, plot.box[3] - 0.05
    assert dialog._drag_resolver(sx, sy)[0] == 'zoom'
    dialog._on_drag_finished('zoom', sx, sy, ex, ey)
    assert p0['x_min'] and p0['y_max']
    from results.figure_builder.ui import interact
    menu = interact.build_menu(dialog, plot, 0.5, 0.5)
    next(a for a in menu.actions() if a.text() == 'Reset zoom').trigger()
    assert not p0['x_min'] and not p0['y_max']
    dialog.apply_layout('Side by side')
    right = dialog.spec['panels'][1]
    x, y, w, h = right['rect']
    assert dialog._drag_resolver(x + w - 0.005, y + h - 0.005)[0] == 'resize'
    dialog._on_drag_finished('resize', x + w, y + h, x + w - 0.2, y + h - 0.3)
    assert right['rect'][2] < w and right['rect'][3] < h
    dialog._render()
    margin = next(h for h in dialog._hits if h.panel_id == right['id'] and h.element == 'panel')
    dialog._drag_hit = margin
    dialog._on_drag_finished('move', x + 0.01, y + 0.01, x - 0.09, y + 0.11)
    assert right['rect'][0] < x and right['rect'][1] > y
    dialog._render()
    assert dialog.last_report.errors == {}


def test_window_uses_app_theme(dialog):
    from results.figure_builder.ui import look
    p = look.palette()
    assert p.accent.lower() in dialog.styleSheet().lower()
    assert dialog.export_btn.objectName() == 'fbPrimary'


def test_app_style_is_default():
    spec = E.default_spec()
    assert spec['figure']['palette'] == 'IsotopeTrack'
    assert spec['figure']['font_family'] == 'Times New Roman'
    assert spec['panels'][0]['frame'] == 'box' and spec['panels'][0]['minor_ticks']
    assert 'IsotopeTrack (app style)' in E.STYLE_PRESETS


@pytest.mark.parametrize('panel', [
    dict(kind='strip', value='Ag', log_y=True, group_by='sample', test='welch', summary_box=True),
    dict(kind='strip', value='Ag', group_by='class', strip_summary='median_iqr', sina=False),
    dict(kind='strip', value='Ag', strip_summary='mean_ci'),
    dict(kind='ridgeline', value='Ag', log_x=True, group_by='sample', mark_stats='median', overlap=1.2),
    dict(kind='hexbin', x='Ag', y='Fe', log_x=True, log_y=True, bins=20),
    dict(kind='contour', x='Ag', y='Fe', log_x=True, log_y=True, group_by='sample', show_points=True),
    dict(kind='contour', x='Ag', y='Fe', filled=False, levels=4),
    dict(kind='radar', group_by='sample'),
    dict(kind='radar', group_by='class', radar_mode='detect', radar_fill=False),
    dict(kind='radar', radar_mode='mean', isotopes='Ag, Au, Fe, total'),
    dict(kind='parallel', group_by='sample', max_lines=50),
    dict(kind='parallel', parallel_scale='raw'),
    dict(kind='histogram', value='Ag', log_x=True, group_by='sample', fit_dist='lognormal',
         mark_stats='both', summary_box=True, summary_loc='lower left'),
    dict(kind='histogram', value='Ag', fit_dist='normal', density=True),
    dict(kind='box', value='Ag', group_by='sample', summary_box=True),
])
def test_more_chart_kinds_render(table, panel):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(**panel)]
    report = _render(spec, table)
    assert report.errors == {}
    assert report.counts[spec['panels'][0]['id']] > 0


def test_lognormal_fit_reported(table):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(kind='histogram', value='Ag', fit_dist='lognormal')]
    report = _render(spec, table)
    assert any('geometric mean' in s for s in report.stats)


def test_shapes_are_drawn_and_listed(table):
    spec = E.default_spec()
    panel = E.make_panel(kind='scatter', x='Ag', y='Fe', group_by='sample', shapes=[
        {'type': 'xband', 'x1': '', 'x2': '40', 'label': 'Below LOD', 'alpha': 0.3},
        {'type': 'yband', 'y1': '10', 'y2': '20', 'hatch': '//'},
        {'type': 'box', 'x1': '100', 'x2': '200', 'y1': '20', 'y2': '60', 'layer': 'front'},
        {'type': 'hline', 'y1': '30', 'style': ':'},
        {'type': 'vline', 'x1': '150'},
        {'type': 'line', 'slope': '0.3', 'intercept': '0', 'label': 'Fe = 0.3 Ag'},
    ])
    spec['panels'] = [panel]
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    canvas.draw()
    assert report.errors == {}
    ax = report.artists[panel['id']]['ax']
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert 'Below LOD' in labels and 'Fe = 0.3 Ag' in labels
    assert any(lab.startswith('Blank') for lab in labels)
    assert ax.get_xlim()[0] < 40


def test_axis_controls(table):
    spec = E.default_spec()
    panel = E.make_panel(kind='scatter', x='Ag', y='Fe', x_ticks='100', y_ticks='10, 20, 50',
                         x_format='thousands', y_format='1dp', invert_y=True, grid=True,
                         grid_axis='y', grid_minor=True, axis_color='#ff0000', legend_frame=False)
    spec['panels'] = [panel]
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    canvas.draw()
    ax = report.artists[panel['id']]['ax']
    assert list(ax.get_yticks()) == [10, 20, 50]
    assert ax.yaxis_inverted()
    assert all(t.get_text().endswith('.0') for t in ax.get_yticklabels() if t.get_text())
    xt = ax.get_xticks()
    assert np.allclose(np.diff(xt), 100)
    assert ax.spines['left'].get_edgecolor()[:3] == (1.0, 0.0, 0.0)


def test_shift_drag_shades_x_range(dialog):
    p0 = dialog.spec['panels'][0]
    dialog._render()
    plot = next(h for h in dialog._hits if h.element == 'plot')
    sx, sy = plot.box[0] + 0.05, plot.box[1] + 0.1
    ex, ey = plot.box[0] + 0.15, plot.box[1] + 0.12
    mode, _box = dialog._drag_resolver(sx, sy, {'shift': True, 'ctrl': False})
    assert mode == 'shade_x'
    dialog._on_drag_finished(mode, sx, sy, ex, ey)
    assert p0['shapes'][-1]['type'] == 'xband'
    assert float(p0['shapes'][-1]['x1']) < float(p0['shapes'][-1]['x2'])
    mode, _box = dialog._drag_resolver(sx, sy, {'shift': False, 'ctrl': True})
    assert mode == 'shade_y'
    dialog._on_drag_finished(mode, sx, sy, sx + 0.01, sy + 0.1)
    assert p0['shapes'][-1]['type'] == 'yband'
    dialog._render()
    assert dialog.last_report.errors == {}


def test_grey_area_menu(dialog):
    from results.figure_builder.ui import interact
    p0 = dialog.spec['panels'][0]
    dialog._render()
    plot = next(h for h in dialog._hits if h.element == 'plot')
    menu = interact.build_menu(dialog, plot, (plot.box[0] + plot.box[2]) / 2,
                               (plot.box[1] + plot.box[3]) / 2)
    add = next(a for a in menu.actions() if a.text() == 'Add').menu()
    item = next(a for a in add.actions() if a.text().startswith('Grey area below y'))
    item.trigger()
    assert p0['shapes'][-1]['type'] == 'yband' and p0['shapes'][-1]['y1'] == ''
    next(a for a in add.actions() if a.text() == 'Line y = x').trigger()
    assert p0['shapes'][-1]['type'] == 'line'


def _cbar_spec(**extra):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(kind='scatter', x='Ag/Fe', y='Au', y2='Fe', color_by='total',
                                   log_x=True, title='Colour bar', **extra)]
    return E.normalise_spec(spec)


def _draw(spec, table):
    fig = Figure(figsize=(spec['figure']['width'], spec['figure']['height']))
    FigureCanvasAgg(fig)
    report = E.render(fig, spec, table)
    fig.canvas.draw()
    return fig, report


def _fig_box(fig, artist):
    renderer = fig.canvas.get_renderer()
    return artist.get_tightbbox(renderer).transformed(fig.transFigure.inverted())


def test_colour_bar_clears_right_axis(table):
    spec = _cbar_spec()
    fig, report = _draw(spec, table)
    assert report.errors == {}
    hd = report.artists[spec['panels'][0]['id']]
    renderer = fig.canvas.get_renderer()
    ax2 = hd['ax2']
    ticks = [t.get_window_extent(renderer) for t in ax2.get_yticklabels() if t.get_text()]
    right = max([b.x1 for b in ticks] + [ax2.yaxis.label.get_window_extent(renderer).x1])
    bar = hd['cbar'].ax.get_window_extent(renderer)
    assert bar.x0 > right
    box = _fig_box(fig, hd['cbar'].ax)
    assert box.x1 <= 1.0 + 1e-3


@pytest.mark.parametrize('loc', ['right', 'left', 'top', 'bottom', 'inside right', 'inside top'])
def test_colour_bar_positions(table, loc):
    spec = _cbar_spec(cbar_loc=loc)
    fig, report = _draw(spec, table)
    assert report.errors == {}
    hd = report.artists[spec['panels'][0]['id']]
    bar = hd['cbar'].ax.get_position()
    plot = hd['ax'].get_position()
    if loc == 'right':
        assert bar.x0 > plot.x1
    elif loc == 'left':
        assert bar.x1 < plot.x0
    elif loc == 'top':
        assert bar.y0 > plot.y1 and bar.width > bar.height
    elif loc == 'bottom':
        assert bar.y1 < plot.y0 and bar.width > bar.height
    else:
        assert plot.x0 < bar.x0 and bar.x1 < plot.x1 and plot.y0 < bar.y0 and bar.y1 < plot.y1
    box = _fig_box(fig, hd['cbar'].ax)
    assert box.x0 >= -1e-3 and box.y0 >= -1e-3 and box.x1 <= 1 + 1e-3 and box.y1 <= 1 + 1e-3


def test_colour_bar_size_and_log(table):
    spec = _cbar_spec(cbar_length=0.5, cbar_width=0.3, cbar_log=True)
    fig, report = _draw(spec, table)
    hd = report.artists[spec['panels'][0]['id']]
    bar, plot = hd['cbar'].ax.get_position(), hd['ax'].get_position()
    assert abs(bar.height / plot.height - 0.5) < 0.02
    assert abs(bar.width * spec['figure']['width'] - 0.3) < 0.02
    from matplotlib.colors import LogNorm
    assert isinstance(hd['cbar'].norm, LogNorm)


@pytest.mark.parametrize('kind', ['density', 'hexbin', 'corr_matrix', 'heatmap', 'cooccurrence'])
def test_other_colour_bars_move(table, kind):
    spec = E.default_spec()
    panel = E.make_panel(kind=kind, x='Ag', y='Fe', cbar_loc='bottom')
    if kind in ('corr_matrix', 'heatmap', 'cooccurrence'):
        panel['isotopes'] = 'Ag, Au, Fe'
    spec['panels'] = [panel]
    spec = E.normalise_spec(spec)
    fig, report = _draw(spec, table)
    assert report.errors == {}
    hd = report.artists[spec['panels'][0]['id']]
    bar = hd['cbar'].ax.get_position()
    assert bar.width > bar.height and bar.y1 < hd['ax'].get_position().y0


def test_colour_bar_drag_and_menu(dialog):
    from results.figure_builder.ui import interact
    p0 = dialog.spec['panels'][0]
    p0.update(kind='scatter', x='Ag/Fe', y='Au', y2='Fe', color_by='total')
    dialog._render()
    assert dialog.last_report.errors == {}
    cb = next(h for h in dialog._hits if h.element == 'cbar')
    cx, cy = (cb.box[0] + cb.box[2]) / 2, cb.box[1] + 0.3 * (cb.box[3] - cb.box[1])
    hd = dialog.last_report.artists[p0['id']]
    pos = hd['cbar'].ax.get_position()
    bx, by = (pos.x0 + pos.x1) / 2, 1 - (pos.y0 + pos.y1) / 2
    assert interact.hit_at(dialog._hits, bx, by).element == 'cbar'
    assert dialog._drag_resolver(bx, by)[0] == 'cbar'
    dialog._drag_hit = cb
    dialog._on_drag_finished('cbar', cx, cy, cx - 0.15, cy + 0.05)
    assert p0['cbar_loc'] == 'custom' and len(p0['cbar_xy']) == 2
    assert p0['cbar_xy'][0] < 1.0
    dialog._render()
    assert dialog.last_report.errors == {}
    cbh = next(h for h in dialog._hits if h.element == 'cbar')
    menu = interact.build_menu(dialog, cbh, cx, cy)
    pos = next(a for a in menu.actions() if a.text() == 'Colour bar position').menu()
    next(a for a in pos.actions() if a.text() == 'Below the plot').trigger()
    assert p0['cbar_loc'] == 'bottom'
    next(a for a in menu.actions() if a.text() == 'Thicker').trigger()
    assert p0['cbar_width'] > 0.14
    dialog._render()
    assert dialog.last_report.errors == {}


NEW_KINDS = [
    dict(kind='ecdf', value='Ag', group_by='sample', log_x=True),
    dict(kind='lollipop'),
    dict(kind='lollipop', group_by='sample', lolli_stat='detect', lolli_vertical=True),
    dict(kind='lollipop', group_by='class', lolli_stat='mean', log_y=True),
    dict(kind='timeline', group_by='sample'),
    dict(kind='timeline', time_mode='cumulative', value='Au'),
    dict(kind='timeline', time_mode='signal', value='Ag', log_y=True),
    dict(kind='treemap', group_by='class'),
    dict(kind='treemap', share_mode='combinations', legend=True),
]


@pytest.mark.parametrize('panel', NEW_KINDS, ids=lambda p: '-'.join(str(v) for v in p.values()))
def test_newest_chart_kinds_render(table, panel):
    spec = E.default_spec()
    spec['panels'] = [E.make_panel(**panel)]
    fig, report = _draw(E.normalise_spec(spec), table)
    assert report.errors == {}
    assert report.counts[spec['panels'][0]['id']] > 0


def test_squarify_fills_the_area():
    from results.figure_builder.charts.more import squarify
    rects = squarify([50, 25, 15, 10], 0, 0, 4, 3)
    assert len(rects) == 4
    assert abs(sum(w * h for _x, _y, w, h in rects) - 12) < 1e-9
    for x, y, w, h in rects:
        assert x >= -1e-9 and y >= -1e-9 and x + w <= 4 + 1e-9 and y + h <= 3 + 1e-9


@pytest.mark.parametrize('extra', [
    dict(ellipse='2sd'), dict(ellipse='1sd', log_x=True, log_y=True), dict(hull=True),
    dict(trend='median'), dict(trend='mean', log_x=True), dict(show_fit=True, fit_band=True),
    dict(marginals='hist'), dict(marginals='kde', log_x=True), dict(marginals='box'),
    dict(inset_zoom='40, 80, 10, 25', inset_loc='lower right'),
], ids=lambda d: '-'.join(f'{k}={v}' for k, v in d.items()))
def test_scatter_extras(table, extra):
    spec = E.normalise_spec({'panels': [E.make_panel(kind='scatter', x='Ag', y='Fe', group_by='sample',
                                                     **extra)]})
    fig, report = _draw(spec, table)
    assert report.errors == {}
    hd = report.artists[spec['panels'][0]['id']]
    if extra.get('marginals'):
        assert 'marg_top' in hd and 'marg_right' in hd
        assert hd['marg_top'].get_position().y0 > hd['ax'].get_position().y1
        assert hd['marg_right'].get_position().x0 > hd['ax'].get_position().x1
    if extra.get('inset_zoom'):
        ins = hd['inset']
        assert ins.get_xlim() == (40.0, 80.0)


def test_marginals_and_colour_bar_do_not_overlap(table):
    spec = E.normalise_spec({'panels': [E.make_panel(kind='scatter', x='Ag', y='Fe', color_by='total',
                                                     marginals='hist')]})
    fig, report = _draw(spec, table)
    hd = report.artists[spec['panels'][0]['id']]
    assert hd['cbar'].ax.get_position().x0 > hd['marg_right'].get_position().x1


def test_dark_and_hand_drawn_presets(table):
    from results.figure_builder.core import styles as S
    spec = E.normalise_spec({'panels': [E.make_panel(kind='strip', value='Ag', group_by='sample')]})
    dark = S.apply_style_preset(spec, 'Dark (slides)')
    fig, report = _draw(dark, table)
    assert report.errors == {}
    ax = report.artists[dark['panels'][0]['id']]['ax']
    from matplotlib.colors import to_hex
    assert to_hex(ax.xaxis.label.get_color()) == '#e2e8f0'
    assert to_hex(fig.get_facecolor()) == '#0f172a'
    back = S.apply_style_preset(dark, 'IsotopeTrack (app style)')
    assert back['figure']['ink'] == '' and back['figure']['background'] == '#ffffff'
    sketch = S.apply_style_preset(spec, 'Hand-drawn')
    fig, report = _draw(sketch, table)
    assert report.errors == {}
    ax = report.artists[sketch['panels'][0]['id']]['ax']
    assert any(c.get_sketch_params() for c in ax.collections)


def test_gallery_renders_thumbnails(dialog):
    from PySide6.QtCore import Qt
    from results.figure_builder.ui.dialog import render_to_pixmap
    from results.figure_builder.ui.gallery import ChartGallery
    g = ChartGallery(dialog.spec, dialog.table, render_to_pixmap, dialog._kind_defaults, True, dialog)
    assert set(g.items) == set(E.PANEL_KINDS) - {'text', 'code'}
    for kind in ('lollipop', 'treemap', 'ecdf'):
        _pix, report, _fig = render_to_pixmap(g.thumbnail_spec(kind), dialog.table, 40)
        assert report.errors == {}, kind
    g._timer.stop()
    while g._queue[:3]:
        g._render_next()
        if len(g._queue) < len(g.items) - 3:
            break
    g.search.setText('ternary')
    assert not g.items['ternary'].isHidden() and g.items['scatter'].isHidden()
    picked = []
    g.chosen.connect(lambda k, r: picked.append((k, r)))
    g.list.setCurrentItem(g.items['ternary'])
    g._use(False)
    assert picked == [('ternary', False)]
    before = len(dialog.spec['panels'])
    dialog.add_panel('treemap')
    assert len(dialog.spec['panels']) == before + 1
    assert g.items['ternary'].data(Qt.UserRole) == 'ternary'


def test_surprise_me_is_undoable(dialog):
    dialog._render()
    before = json.dumps(dialog.spec, sort_keys=True, default=str)
    preset, palette = dialog.surprise(seed=4)
    dialog._render()
    assert dialog.spec['figure']['palette'] == palette
    assert json.dumps(dialog.spec, sort_keys=True, default=str) != before
    assert dialog.last_report.errors == {}
    dialog.undo()
    assert json.dumps(dialog.spec, sort_keys=True, default=str) == before


def test_scatter_extras_menu(dialog):
    from results.figure_builder.ui import interact
    p0 = dialog.spec['panels'][0]
    p0['kind'] = 'scatter'
    dialog._render()
    plot = next(h for h in dialog._hits if h.element == 'plot')
    menu = interact.build_menu(dialog, plot, 0.5, 0.5)
    extras = next(a for a in menu.actions() if a.text() == 'Extras').menu()
    next(a for a in extras.actions() if a.text() == 'Histograms along the edges').trigger()
    assert p0['marginals'] == 'hist'
    next(a for a in extras.actions() if a.text() == '95% ellipse around each group').trigger()
    assert p0['ellipse'] == '2sd'
    dialog._render()
    assert dialog.last_report.errors == {}
