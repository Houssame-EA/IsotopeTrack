# -*- coding: utf-8 -*-
"""Tests for the simple Particle Classifier: the group <-> definition
conversion in tools/particle_classifier_rules.py and the features of
tools/particle_classifier_simple_dialog.py that the classic editor also
has. A bug here would silently change what a saved classifier matches when
the user only opens the dialog and presses OK, so the round trip is pinned
down first.
"""
import sys

import pytest

from tools import particle_classifier_rules as pcr


def _defn(did, sample, expr, group=None, mode='partial', color=None):
    return {'id': did, 'target_sample': sample, 'expression_text': expr,
            'match_mode': mode, 'group_name': group, 'color': color}


def _rule(must=(), must_not=(), exact=False):
    r = pcr.new_rule()
    r['must'], r['must_not'], r['exact'] = list(must), list(must_not), exact
    return r


class TestRecipe:
    def test_recipe_to_expression(self):
        assert pcr.recipe_to_expression(['60Ni', '107Ag'], ['56Fe']) == '60Ni+107Ag+!(56Fe)'
        assert pcr.recipe_to_expression([], []) == ''
        assert pcr.recipe_to_expression([], ['56Fe']) == '!(56Fe)'
        assert pcr.recipe_to_expression(['48Ti'], ['55Mn'], ['60Ni', '52Cr']) == '48Ti+[60Ni, 52Cr]+!(55Mn)'
        assert pcr.recipe_to_expression([], [], ['60Ni', '52Cr']) == '[60Ni, 52Cr]'

    def test_expression_to_recipe_simple_shapes(self):
        assert pcr.expression_to_recipe('60Ni') == (['60Ni'], [], [], [])
        assert pcr.expression_to_recipe('60Ni + 107Ag+!(56Fe)') == (['60Ni', '107Ag'], [], [], ['56Fe'])
        assert pcr.expression_to_recipe('') == ([], [], [], [])

    def test_expression_to_recipe_reads_at_least_one_of(self):
        assert pcr.expression_to_recipe('48Ti+[60Ni, 52Cr]') == (['48Ti'], ['60Ni', '52Cr'], [], [])
        assert pcr.expression_to_recipe('[60Ni, 107Ag]') == ([], ['60Ni', '107Ag'], [], [])
        assert pcr.expression_to_recipe('48Ti+[60Ni, 52Cr]+!(55Mn)') == (['48Ti'], ['60Ni', '52Cr'], [], ['55Mn'])

    def test_expression_to_recipe_reads_exactly_one_of(self):
        assert pcr.expression_to_recipe('197Au+{107Ag; 63Cu}') == (['197Au'], [], ['107Ag', '63Cu'], [])
        assert pcr.expression_to_recipe('48Ti+[60Ni, 52Cr]+{107Ag; 63Cu}+!(55Mn)') == (
            ['48Ti'], ['60Ni', '52Cr'], ['107Ag', '63Cu'], ['55Mn'])
        assert pcr.recipe_to_expression(['197Au'], [], [], ['107Ag', '63Cu']) == '197Au+{107Ag; 63Cu}'

    def test_expression_to_recipe_rejects_what_rows_cannot_show(self):
        assert pcr.expression_to_recipe('{60Ni; 107Ag}+{197Au; 195Pt}') is None
        assert pcr.expression_to_recipe('{60Ni+107Ag; 197Au}') is None
        assert pcr.expression_to_recipe('[60Ni, 107Ag]+{60Ni; 197Au}') is None
        assert pcr.expression_to_recipe('!(60Ni+107Ag)') is None
        assert pcr.expression_to_recipe('[60Ni, 107Ag]+[197Au, 195Pt]') is None
        assert pcr.expression_to_recipe('[60Ni+107Ag, 197Au]') is None
        assert pcr.expression_to_recipe('60Ni+') is None

    def test_round_trip_keeps_meaning(self):
        for text in ('60Ni', '60Ni+107Ag', '48Ti+!(56Fe)+!(27Al)', '48Ti+[60Ni, 52Cr]+!(55Mn)',
                     '48Ti+[60Ni, 52Cr]+{107Ag; 63Cu}+!(55Mn)'):
            must, any_of, one_of, must_not = pcr.expression_to_recipe(text)
            assert pcr.recipe_to_expression(must, must_not, any_of, one_of) == text

    def test_isotope_sort_key_orders_by_mass(self):
        labels = ['107Ag', '56Fe', '197Au', '60Ni']
        assert sorted(labels, key=pcr.isotope_sort_key) == ['56Fe', '60Ni', '107Ag', '197Au']


class TestGroupsFromDefinitions:
    def test_same_groups_on_every_sample_is_shared(self):
        defs = [_defn('a', 'S1', '60Ni+107Ag', 'Smelter'),
                _defn('b', 'S2', '60Ni+107Ag', 'Smelter')]
        by_sample, shared = pcr.groups_from_definitions(defs, {'Smelter': '#123456'}, ['S1', 'S2'])
        assert shared
        group = by_sample['S1'][0]
        assert group['name'] == 'Smelter'
        assert group['color'] == '#123456'
        assert group['rules'][0]['must'] == ['60Ni', '107Ag']

    def test_different_groups_per_sample_is_not_shared(self):
        defs = [_defn('a', 'S1', '60Ni', 'Smelter'), _defn('b', 'S2', '197Au', 'Gold')]
        assert not pcr.groups_from_definitions(defs, {}, ['S1', 'S2'])[1]

    def test_no_definitions_is_shared(self):
        by_sample, shared = pcr.groups_from_definitions([], {}, ['S1', 'S2'])
        assert shared and by_sample == {'S1': [], 'S2': []}

    def test_complex_expression_becomes_text_rule(self):
        defs = [_defn('a', 'S1', '[60Ni+107Ag, 197Au]', 'Mix')]
        rule = pcr.groups_from_definitions(defs, {}, ['S1'])[0]['S1'][0]['rules'][0]
        assert rule['text_mode'] and rule['text'] == '[60Ni+107Ag, 197Au]'

    def test_group_with_two_definitions_has_two_rules(self):
        defs = [_defn('a', 'S1', '60Ni', 'Smelter'), _defn('b', 'S1', '107Ag', 'Smelter')]
        by_sample, _shared = pcr.groups_from_definitions(defs, {}, ['S1'])
        assert len(by_sample['S1']) == 1
        assert [r['must'] for r in by_sample['S1'][0]['rules']] == [['60Ni'], ['107Ag']]

    def test_exact_mode_is_read(self):
        defs = [_defn('a', 'S1', '48Ti', 'TiO2', mode='exact')]
        assert pcr.groups_from_definitions(defs, {}, ['S1'])[0]['S1'][0]['rules'][0]['exact']


class TestDefinitionsFromGroups:
    def test_unchanged_round_trip_is_identical(self):
        defs = [_defn('a', 'S1', '60Ni + 107Ag', 'Smelter'),
                _defn('b', 'S1', '48Ti', 'TiO2', mode='exact'),
                _defn('c', 'S1', '[197Au, 195Pt]', 'Noble'),
                _defn('d', 'S1', '197Au', 'Noble')]
        groups = {'Smelter': '#111111', 'TiO2': '#222222', 'Noble': '#333333'}
        by_sample, _shared = pcr.groups_from_definitions(defs, groups, ['S1'])
        out, out_groups = pcr.definitions_from_groups(by_sample, ['S1'], defs, groups)
        assert out == defs
        assert out_groups == groups

    def test_ids_are_reused_and_new_rules_get_new_ids(self):
        defs = [_defn('keep-me', 'S1', '60Ni', 'Smelter')]
        by_sample, _ = pcr.groups_from_definitions(defs, {'Smelter': '#111111'}, ['S1'])
        gold = pcr.new_group('Gold', '#333333')
        gold['rules'][0]['must'] = ['197Au']
        by_sample['S1'].append(gold)
        out, groups = pcr.definitions_from_groups(by_sample, ['S1'], defs, {'Smelter': '#111111'})
        assert out[0]['id'] == 'keep-me'
        assert out[1]['id'] != 'keep-me'
        assert out[1]['expression_text'] == '197Au'
        assert groups == {'Smelter': '#111111', 'Gold': '#333333'}

    def test_empty_rules_and_groups_are_skipped(self):
        out, groups = pcr.definitions_from_groups({'S1': [pcr.new_group('Empty')]}, ['S1'])
        assert out == [] and groups == {}

    def test_disconnected_samples_are_kept(self):
        old = [_defn('x', 'GoneSample', '60Ni', 'Smelter')]
        out, groups = pcr.definitions_from_groups({'S1': []}, ['S1'], old, {'Smelter': '#111111'})
        assert out == old
        assert groups == {'Smelter': '#111111'}

    def test_edited_recipe_writes_new_expression(self):
        defs = [_defn('a', 'S1', '60Ni', 'Smelter')]
        by_sample, _ = pcr.groups_from_definitions(defs, {}, ['S1'])
        rule = by_sample['S1'][0]['rules'][0]
        rule['must_not'].append('56Fe')
        rule['exact'] = True
        out, _groups = pcr.definitions_from_groups(by_sample, ['S1'], defs, {})
        assert out[0]['expression_text'] == '60Ni+!(56Fe)'
        assert out[0]['match_mode'] == 'exact'

    def test_two_rules_become_two_definitions_of_one_group(self):
        group = pcr.new_group('Smelter', '#111111')
        group['rules'] = [_rule(['60Ni']), _rule(['107Ag'])]
        out, groups = pcr.definitions_from_groups({'S1': [group]}, ['S1'])
        assert [d['expression_text'] for d in out] == ['60Ni', '107Ag']
        assert {d['group_name'] for d in out} == {'Smelter'}


class TestNotesAndChecks:
    def test_sample_summary_counts_groups_and_unmatched(self):
        particles = [{'elements': {'60Ni': 1, '107Ag': 1}},
                     {'elements': {'60Ni': 1, '107Ag': 1, '56Fe': 1}},
                     {'elements': {'48Ti': 1}}]
        defs = [_defn('a', 'S1', '60Ni+107Ag+!(56Fe)', 'Smelter')]
        assert pcr.sample_summary(particles, defs, 'double_count') == ({'Smelter': 1}, 2, 3)

    def test_two_rules_count_a_particle_once(self):
        particles = [{'elements': {'60Ni': 1, '107Ag': 1}}]
        defs = [_defn('a', 'S1', '60Ni', 'Smelter'), _defn('b', 'S1', '107Ag', 'Smelter')]
        assert pcr.sample_summary(particles, defs, 'double_count')[0] == {'Smelter': 1}

    def test_unresolved_issues(self):
        labels = {'S1': {'60Ni', '107Ag'}}
        assert not pcr.has_unresolved_issues([_defn('a', 'S1', '60Ni', 'G')], labels)
        assert pcr.has_unresolved_issues([_defn('a', 'S1', '197Au', 'G')], labels)
        assert pcr.has_unresolved_issues([_defn('a', 'S1', '60Ni+', 'G')], labels)
        assert pcr.has_unresolved_issues([_defn('a', 'S1', '60Ni+!(60Ni)', 'G')], labels)

    def test_rule_notes(self):
        text = pcr.new_rule()
        text['text_mode'], text['text'] = True, '60Ni+!(60Ni)'
        assert pcr.rule_notes(text)['contradiction']
        text['text'] = '[60Ni, !(60Ni)]'
        assert pcr.rule_notes(text)['tautology']
        text['text'] = '60Ni+'
        assert pcr.rule_notes(text)['error']
        assert pcr.rule_notes(_rule(['60Ni', '197Au']), {'60Ni'})['missing'] == ['197Au']

    def test_remove_isotopes(self):
        rule = _rule(['60Ni', '197Au'], ['195Pt'])
        pcr.remove_isotopes(rule, ['197Au', '195Pt'])
        assert rule['must'] == ['60Ni'] and rule['must_not'] == []
        text = pcr.new_rule()
        text['text_mode'], text['text'] = True, '[60Ni, 197Au]'
        pcr.remove_isotopes(text, ['197Au'])
        assert text['text'] == '[60Ni, ]'

    def test_combinations_and_their_groups(self):
        particles = [{'elements': {'107Ag': 1, '60Ni': 1}}, {'elements': {'60Ni': 1, '107Ag': 1}},
                     {'elements': {'48Ti': 1}}, {'elements': {}}]
        combos = pcr.combinations(particles)
        assert combos == [(('60Ni', '107Ag'), 2), (('48Ti',), 1)]
        defs = [_defn('a', 'S1', '60Ni', 'Smelter'), _defn('b', 'S1', '107Ag', 'Silver')]
        assert pcr.combination_groups(('60Ni', '107Ag'), defs, 'double_count') == ['Smelter', 'Silver']
        assert pcr.combination_groups(('60Ni', '107Ag'), defs, 'priority') == ['Smelter']
        assert pcr.combination_groups(('48Ti',), defs, 'double_count') == []

    def test_overlapping_pairs_and_dismissals(self):
        defs = [_defn('a', 'S1', '60Ni', 'A'), _defn('b', 'S1', '107Ag', 'B'),
                _defn('c', 'S2', '60Ni', 'C')]
        pairs = pcr.overlapping_pairs(defs, {'S1', 'S2'}, set())
        assert len(pairs) == 1
        key = pairs[0][3]
        assert pcr.confound_key_from_record(pcr.confound_record(key)) == key
        assert pcr.overlapping_pairs(defs, {'S1', 'S2'}, {key}) == []
        assert pcr.overlapping_pairs(defs, {'S2'}, set()) == []


class TestSimpleSyntax:
    LABELS = {'48Ti', '56Fe', '54Fe', '27Al', '60Ni', '107Ag', '197Au', '195Pt', '63Cu'}

    @pytest.mark.parametrize('simple, classic', [
        ('+60Ni +107Ag -56Fe', '60Ni+107Ag+!(56Fe)'),
        ('+48Ti (+56Fe or +27Al)', '48Ti+[56Fe, 27Al]'),
        ('+197Au oneof(+107Ag, +63Cu)', '197Au+{107Ag; 63Cu}'),
        ('-(+60Ni +107Ag)', '!(60Ni+107Ag)'),
        ('+60Ni +107Ag or +197Au', '[60Ni+107Ag, 197Au]'),
        ('60Ni and 107Ag not 56Fe', '60Ni+107Ag+!(56Fe)'),
        ('+60ni \u2212195pt', '60Ni+!(195Pt)'),
    ])
    def test_simple_to_classic(self, simple, classic):
        assert pcr.parse_simple(simple, self.LABELS) == classic

    def test_element_names_resolve_to_measured_isotope(self):
        assert pcr.parse_simple('+Ni +Ag -Cu', self.LABELS) == '60Ni+107Ag+!(63Cu)'

    def test_ambiguous_or_missing_element_is_an_error(self):
        with pytest.raises(pcr.ExpressionSyntaxError, match='54Fe, 56Fe'):
            pcr.parse_simple('+Fe', self.LABELS)
        with pytest.raises(pcr.ExpressionSyntaxError, match='No Pb'):
            pcr.parse_simple('+Pb', self.LABELS)

    def test_classic_syntax_still_accepted(self):
        for text in ('60Ni+[107Ag, 197Au]+!(56Fe)', '{60Ni; 197Au}', '!(56Fe)'):
            assert pcr.parse_simple(text, self.LABELS) == text

    def test_invalid_text_raises(self):
        for text in ('+', '+60Ni (', 'oneof(+60Ni)', '+60Ni ]', ''):
            with pytest.raises(pcr.ExpressionSyntaxError):
                pcr.parse_simple(text, self.LABELS)

    @pytest.mark.parametrize('classic', [
        '60Ni+107Ag+!(56Fe)', '48Ti+[56Fe, 27Al]', '197Au+{107Ag; 63Cu}',
        '!(60Ni+107Ag)', '[60Ni+107Ag, 197Au]', '48Ti', '!([56Fe, 27Al])',
    ])
    def test_round_trip_through_simple(self, classic):
        assert pcr.parse_simple(pcr.to_simple(classic), self.LABELS) == classic

    def test_to_simple_examples(self):
        assert pcr.to_simple('48Ti+[56Fe, 27Al]') == '+48Ti (+56Fe or +27Al)'
        assert pcr.to_simple('60Ni+107Ag+!(56Fe)') == '+60Ni +107Ag -56Fe'
        assert pcr.to_simple('not valid ((') == 'not valid (('


def _sample(name, isotopes):
    return {
        'type': 'sample_data',
        'sample_name': name,
        'data': {},
        'particle_data': [{'elements': {iso: 1.0 for iso in isotopes}}],
        'selected_isotopes': [{'label': iso} for iso in isotopes],
        'total_particles': 1,
        'concentration_meta': {name: {}},
        'parent_window': None,
    }


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def make_dialog(qapp):
    from tools.particle_classifier_simple_dialog import SimpleClassifierDialog
    made = []

    def _make(defs=None, groups=None, **kw):
        d = SimpleClassifierDialog(
            None, [_sample("SampleA", ["60Ni", "107Ag"]), _sample("SampleB", ["197Au"])],
            defs, groups, **kw)
        d._show_overlap_warning = lambda pairs: True
        made.append(d)
        return d
    yield _make
    for d in made:
        d.deleteLater()


class TestSimpleDialog:
    def test_open_and_ok_keeps_existing_setup(self, make_dialog):
        defs = [_defn('a', 'SampleA', '60Ni+107Ag', 'Smelter'),
                _defn('b', 'SampleB', '60Ni+107Ag', 'Smelter')]
        dlg = make_dialog(defs, {'Smelter': '#111111'}, overlap_mode='priority',
                          unmatched_mode='discard', selected_sources=['SampleA'],
                          group_pooling_policies={'Smelter': 'keep'})
        dlg.accept()
        assert dlg.get_definitions() == defs
        assert dlg.get_groups() == {'Smelter': '#111111'}
        assert dlg.get_overlap_mode() == 'priority'
        assert dlg.get_unmatched_mode() == 'discard'
        assert dlg.get_selected_sources() == ['SampleA']

    def test_new_group_applies_to_every_sample(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._add_isotope('must_not', '107Ag')
        dlg.accept()
        out = dlg.get_definitions()
        assert {d['target_sample'] for d in out} == {'SampleA', 'SampleB'}
        assert {d['expression_text'] for d in out} == {'60Ni+!(107Ag)'}
        assert set(dlg.get_groups()) == {'Group 1'}

    def test_live_count(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._recompute_counts()
        assert dlg._counts == {'Group 1': 1}
        assert dlg._count_lbl.text() == '1'

    def test_exclude_sample_from_output(self, make_dialog):
        dlg = make_dialog()
        assert dlg.get_selected_sources() is None
        dlg._include_cb.setChecked(False)
        assert dlg.get_selected_sources() == ['SampleB']

    def test_priority_order(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._add_group()
        dlg._add_isotope('must', '107Ag')
        dlg._move_group(-1)
        dlg.accept()
        names = [d['group_name'] for d in dlg.get_definitions() if d['target_sample'] == 'SampleA']
        assert names == ['Group 2', 'Group 1']

    def test_second_rule_asks_pooling_and_saves_two_definitions(self, make_dialog, monkeypatch):
        dlg = make_dialog()
        asked = []

        def _fake_ask(group):
            asked.append(group['name'])
            dlg._pooling[group['name']] = 'drop_mfc'
            return True
        monkeypatch.setattr(dlg, '_ask_pooling', _fake_ask)
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._add_rule()
        dlg._add_isotope('must', '197Au')
        dlg.accept()
        exprs = [d['expression_text'] for d in dlg.get_definitions() if d['target_sample'] == 'SampleA']
        assert exprs == ['60Ni', '197Au']
        assert asked == ['Group 1']
        assert dlg.get_group_pooling_policies() == {'Group 1': 'drop_mfc'}

    def test_going_back_from_pooling_removes_the_new_rule(self, make_dialog, monkeypatch):
        dlg = make_dialog()
        monkeypatch.setattr(dlg, '_ask_pooling', lambda group: False)
        dlg._add_group()
        dlg._add_rule()
        assert len(dlg._current_group()['rules']) == 1

    def test_per_sample_groups_and_copy(self, make_dialog):
        dlg = make_dialog()
        dlg._shared_cb.setChecked(False)
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._copy_groups_to(['SampleB'])
        dlg.accept()
        assert {d['target_sample'] for d in dlg.get_definitions()} == {'SampleA', 'SampleB'}

    def test_overlap_warning_go_back_keeps_dialog_open(self, make_dialog):
        dlg = make_dialog()
        dlg._show_overlap_warning = lambda pairs: False
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._add_group()
        dlg._add_isotope('must', '107Ag')
        dlg.accept()
        assert dlg.result() == 0
        assert dlg._out_definitions is None

    def test_text_mode_accepts_simple_syntax(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._toggle_text_mode()
        dlg._loading = False
        dlg._on_text_changed('+Ni -Ag')
        assert dlg._current_rule()['text'] == '60Ni+!(107Ag)'
        dlg._on_text_changed('+Ni (')
        assert dlg._msg_lbl.isVisibleTo(dlg)
        dlg._on_text_changed('+Ni oneof(+Ag, +Au)')
        dlg.accept()
        assert {d['expression_text'] for d in dlg.get_definitions()} == {'60Ni+{107Ag; 197Au}'}

    def test_or_expression_shows_in_rows(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._toggle_text_mode()
        dlg._loading = False
        dlg._on_text_changed('+60Ni (+107Ag or +197Au)')
        dlg._toggle_text_mode()
        rule = dlg._current_rule()
        assert not rule['text_mode']
        assert (rule['must'], rule['any'], rule['must_not']) == (['60Ni'], ['107Ag', '197Au'], [])
        assert 'at least one of 107Ag or 197Au' in dlg._reads_lbl.text()
        dlg._add_isotope('any', '60Ni')
        assert rule['must'] == [] and rule['any'] == ['107Ag', '197Au', '60Ni']
        dlg.accept()
        assert {d['expression_text'] for d in dlg.get_definitions()} == {'[107Ag, 197Au, 60Ni]'}

    def test_exactly_one_of_row(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._add_isotope('one', '107Ag')
        dlg._add_isotope('one', '197Au')
        assert 'exactly one of 107Ag or 197Au' in dlg._reads_lbl.text()
        dlg.accept()
        assert {d['expression_text'] for d in dlg.get_definitions()} == {'{107Ag; 197Au}'}

    def test_clicking_a_combination_fills_must_have(self, make_dialog):
        dlg = make_dialog()
        assert dlg._combo_list.count() == 1
        dlg._on_combo_clicked(dlg._combo_list.item(0))
        rule = dlg._current_rule()
        assert rule['must'] == ['60Ni', '107Ag']
        dlg._recompute_counts()
        assert dlg._combo_list.item(0).toolTip() == 'In: Group 1'

    def test_remove_missing_isotopes(self, make_dialog):
        dlg = make_dialog()
        dlg._add_group()
        dlg._add_isotope('must', '60Ni')
        dlg._current_rule()['must'].append('197Au')
        dlg._update_feedback()
        assert dlg._btn_remove_missing.isVisibleTo(dlg)
        dlg._remove_missing()
        assert dlg._current_rule()['must'] == ['60Ni']
