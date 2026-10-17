# -*- coding: utf-8 -*-
"""Tests for the Single Sample and Multi-Sample selector dialogs and nodes.

Covers particle counts per sample, Shift-click range selection, grouping
the ticked samples under a suggested name with colour tags, stepping
through samples with the arrows (applied live) and restoring the starting
selection on Cancel.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QWidget

import widget.canvas_widgets as cw
from widget.canvas_widgets import (
    MultipleSampleSelectorDialog, SampleSelectorDialog, SampleSelectorNode,
    sample_particle_counts, suggest_group_name,
)

SAMPLES = ['Influent_Day1_1', 'Influent_Day1_2', 'Influent_Day1_3',
           'Effluent_Day1_1', 'Effluent_Day1_2', 'Blank_1']


@pytest.fixture(scope='module')
def app():
    """The Qt application."""
    return QApplication.instance() or QApplication([])


class FakeWindow(QWidget):
    """A main window with particles for each sample."""

    selected_isotopes = {}

    def __init__(self):
        """Give every sample a different number of particles."""
        super().__init__()
        self.sample_particle_data = {s: [{'elements': {}}] * (k + 1) for k, s in enumerate(SAMPLES)}
        self.sample_to_folder_map = {s: s for s in SAMPLES}

    def get_formatted_label(self, key):
        """Label for an isotope key."""
        return key


def test_counts_and_group_suggestion():
    """Counts come from the window or a batch; names suggest their shared root."""
    w = type('W', (), {'sample_particle_data': {'a': [1, 2], 'b': []}})()
    assert sample_particle_counts(w, ['a', 'b']) == {'a': 2, 'b': 0}
    batch = [{'source_sample': 'a'}, {'source_sample': 'a'}, {'source_sample': 'b'}]
    assert sample_particle_counts(None, ['a', 'b', 'c'], batch) == {'a': 2, 'b': 1, 'c': 0}
    assert sample_particle_counts(object(), ['a']) == {}
    assert suggest_group_name(['Influent_Day1_1', 'Influent_Day1_2']) == 'Influent_Day1'
    assert suggest_group_name(['RiverA_x', 'RiverA_y']) .startswith('RiverA')
    assert suggest_group_name(['abc', 'xyz']) == 'Group'


def test_shift_click_ticks_a_range(app, monkeypatch):
    """Shift-click from the first to the fourth sample ticks all four."""
    d = MultipleSampleSelectorDialog(FakeWindow(), SAMPLES, counts={})
    monkeypatch.setattr(cw, '_shift_held', lambda: False)
    d._row_widgets[SAMPLES[0]][1].setChecked(True)
    d._on_clicked(SAMPLES[0], True)
    monkeypatch.setattr(cw, '_shift_held', lambda: True)
    d._row_widgets[SAMPLES[3]][1].setChecked(True)
    d._on_clicked(SAMPLES[3], True)
    ticked = [s for s, (_, cb, _) in d._row_widgets.items() if cb.isChecked()]
    assert ticked == SAMPLES[:4]
    d.deleteLater()


def test_group_checked_uses_the_suggestion(app):
    """With the field empty, the ticked samples get their shared name and one colour."""
    d = MultipleSampleSelectorDialog(FakeWindow(), SAMPLES, counts={s: 10 for s in SAMPLES})
    for s in SAMPLES[:3]:
        d._row_widgets[s][1].setChecked(True)
    assert 'Influent_Day1' in d._group_input.placeholderText()
    d._apply_group_to_checked()
    sel, _, cfg = d.get_selection()
    assert sel == SAMPLES[:3]
    assert {cfg[s]['sum_group'] for s in SAMPLES[:3]} == {'Influent_Day1'}
    assert cfg[SAMPLES[3]]['sum_group'] == ''
    colours = {d._tags[s].styleSheet() for s in SAMPLES[:3]}
    assert len(colours) == 1 and 'background:#' in colours.pop()
    assert '30 particles' in d._preview.text()
    d.deleteLater()


def test_arrows_step_through_samples(app):
    """Each arrow press leaves exactly one sample ticked and reports it to the node."""
    seen = []
    d = SampleSelectorDialog(FakeWindow(), SAMPLES, current_selection=SAMPLES[0],
                             counts={s: 5 for s in SAMPLES},
                             on_step=lambda dlg: seen.append(dlg.get_selection()[0]) or True)
    d._step(1)
    d._step(1)
    d._step(-1)
    assert seen == [SAMPLES[1], SAMPLES[2], SAMPLES[1]]
    assert d.get_selection()[0] == SAMPLES[1]
    assert '(2 of 6)' in d._preview.text()
    d._step(-1)
    d._step(-1)
    assert d.get_selection()[0] == SAMPLES[-1]
    d.deleteLater()


def test_refused_step_goes_back(app):
    """When the node refuses a step, the previous sample stays selected."""
    d = SampleSelectorDialog(FakeWindow(), SAMPLES, current_selection=SAMPLES[0], on_step=lambda dlg: False)
    d._step(1)
    assert d.get_selection()[0] == SAMPLES[0]
    d.deleteLater()


def test_node_applies_steps_live_and_cancel_restores(app, monkeypatch):
    """Steps reach the node at once; Cancel puts back the starting sample."""
    win = FakeWindow()
    node = SampleSelectorNode(win)
    node.selected_sample = SAMPLES[0]
    changes = []
    node.configuration_changed.connect(lambda: changes.append(node.selected_sample))
    monkeypatch.setattr(cw, '_warn_before_apply_changes', lambda parent, n: True)
    monkeypatch.setattr(cw, '_ual', lambda: None)

    def fake_exec(dlg):
        """Step twice, then cancel."""
        dlg._step(1)
        dlg._step(1)
        return QDialog.Rejected
    monkeypatch.setattr(SampleSelectorDialog, 'exec', fake_exec)
    assert node.configure(win) is False
    assert changes == [SAMPLES[1], SAMPLES[2], SAMPLES[0]]
    assert node.selected_sample == SAMPLES[0]


def test_node_keeps_the_stepped_sample_on_ok(app, monkeypatch):
    """OK after stepping keeps the sample shown last."""
    win = FakeWindow()
    node = SampleSelectorNode(win)
    node.selected_sample = SAMPLES[0]
    monkeypatch.setattr(cw, '_warn_before_apply_changes', lambda parent, n: True)
    monkeypatch.setattr(cw, '_ual', lambda: None)

    def fake_exec(dlg):
        """Step once and accept."""
        dlg._step(1)
        return QDialog.Accepted
    monkeypatch.setattr(SampleSelectorDialog, 'exec', fake_exec)
    assert node.configure(win) is True
    assert node.selected_sample == SAMPLES[1] and not node.sum_replicates


def test_highlight_click_shift_and_cmd(app):
    """Click highlights one row, Shift a range, Cmd/Ctrl adds or removes one."""
    d = MultipleSampleSelectorDialog(FakeWindow(), SAMPLES, counts={})
    d._hl_click(SAMPLES[0], Qt.NoModifier)
    d._hl_click(SAMPLES[2], Qt.ShiftModifier)
    assert d._hl_ordered() == SAMPLES[:3]
    d._hl_click(SAMPLES[5], Qt.ControlModifier)
    d._hl_click(SAMPLES[1], Qt.ControlModifier)
    assert d._hl_ordered() == [SAMPLES[0], SAMPLES[2], SAMPLES[5]]
    assert d._hl_bar.isVisibleTo(d) and d._hl_label.text() == '3 highlighted'
    d._hl_click(SAMPLES[4], Qt.NoModifier)
    assert d._hl_ordered() == [SAMPLES[4]]
    d.deleteLater()


def test_actions_on_highlighted_rows(app):
    """Include, Group with the shared name, Ungroup and Exclude act on the highlight only."""
    d = MultipleSampleSelectorDialog(FakeWindow(), SAMPLES, counts={})
    d._hl_set(SAMPLES[3:5])
    assert 'Effluent_Day1' in d._group_input.placeholderText()
    d._apply_group_to_checked()
    sel, _, cfg = d.get_selection()
    assert sel == SAMPLES[3:5] and {cfg[s]['sum_group'] for s in sel} == {'Effluent_Day1'}
    d._hl_set([SAMPLES[0]])
    d._include_highlighted()
    d._hl_set([SAMPLES[4]])
    d._ungroup_highlighted()
    d._exclude_highlighted()
    sel, _, cfg = d.get_selection()
    assert sel == [SAMPLES[0], SAMPLES[3]]
    assert cfg[SAMPLES[4]]['sum_group'] == '' and cfg[SAMPLES[3]]['sum_group'] == 'Effluent_Day1'
    d.deleteLater()


def test_arrows_step_through_the_highlight(app):
    """With rows highlighted, the arrows stay inside them."""
    d = SampleSelectorDialog(FakeWindow(), SAMPLES, current_selection=SAMPLES[3])
    d._hl_set([SAMPLES[1], SAMPLES[3], SAMPLES[5]])
    d._step(1)
    assert d.get_selection()[0] == SAMPLES[5]
    d._step(1)
    assert d.get_selection()[0] == SAMPLES[1]
    assert '(1 of 3)' in d._preview.text()
    d._hl_set([SAMPLES[0], SAMPLES[2]])
    d._include_highlighted()
    assert d.get_selection()[0] == [SAMPLES[0], SAMPLES[1], SAMPLES[2]]
    d.deleteLater()


def test_select_all_and_escape_keys(app):
    """Cmd/Ctrl+A highlights every shown row; Esc clears the highlight first."""
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    d = MultipleSampleSelectorDialog(FakeWindow(), SAMPLES, counts={})
    d._search.setText('Influent')
    d.setFocus()
    d.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.ControlModifier))
    assert d._hl_ordered() == SAMPLES[:3]
    d.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert d._highlighted == [] and d.result() == 0
    d.deleteLater()
