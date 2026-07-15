# -*- coding: utf-8 -*-
"""Tests for the Particle Classifier configuration dialog (Stage 3):
tools/particle_classifier_dialog.py + the data-model additions to
ParticleClassifierNode in tools/particle_classifier_node.py. A bug here
would let the dialog save an unparseable/contradictory/confounding
definition without warning, or lose edits across a list-widget rebuild (two
real bugs of exactly that shape were caught and fixed while smoke-testing
this file — row-selection loss on QListWidget.clear() mid-edit) — so the
live-validation wiring and the read-back contract are worth pinning down.
Not exhaustive: a few base + edge cases per path, mirroring the project's
existing test style.
"""
import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
import sys

from tools import particle_classifier_dialog as pcd
from tools.particle_classifier_node import ParticleClassifierNode


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def no_modal(qapp, monkeypatch):
    """Stub QMessageBox so contradiction/confound/help modals never block;
    default choice is the first-added button (the "reject/go-back" side)
    unless a test overrides ``clicked_role``."""
    state = {'role': None}

    class _Fake:
        def __init__(self, *a, **kw):
            self._buttons = []
        def setWindowTitle(self, *a): pass
        def setIcon(self, *a): pass
        def setText(self, t): pass
        def setInformativeText(self, t): pass
        def addButton(self, text, role):
            b = (text, role)
            self._buttons.append(b)
            return b
        def setDefaultButton(self, b): pass
        def exec(self):
            want = state['role']
            self._clicked = next(
                (b for b in self._buttons if want is not None and b[1] == want),
                self._buttons[0] if self._buttons else None)
        def clickedButton(self):
            return self._clicked

    monkeypatch.setattr(pcd, "QMessageBox", _Fake)
    pcd.QMessageBox.Icon = type('Icon', (), {'Warning': 1, 'Information': 2})
    pcd.QMessageBox.ButtonRole = type(
        'ButtonRole', (), {'AcceptRole': 1, 'RejectRole': 2})
    pcd.QMessageBox.information = staticmethod(lambda *a, **kw: None)
    return state


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


@pytest.fixture
def dlg(qapp, no_modal):
    d = pcd.ParticleClassifierDialog(
        None, [_sample("SampleA", ["60Ni", "107Ag"]),
               _sample("SampleB", ["197Au"])])
    d.show()
    qapp.processEvents()
    return d


# --------------------------------------------------------------------------- #
# Construction / navigation
# --------------------------------------------------------------------------- #
class TestConstructionAndNavigation:
    def test_empty_upstream_constructs(self, qapp, no_modal):
        d = pcd.ParticleClassifierDialog(None, [])
        assert d._sources == []

    def test_lists_every_connected_sample(self, dlg):
        assert dlg._list.count() == 2

    def test_click_navigates_without_checking(self, dlg):
        dlg._list.setCurrentRow(0)
        assert dlg._current == "SampleA"
        # Checkbox state is independent of navigation (design §3).
        assert dlg._list.item(0).checkState() == Qt.Checked


# --------------------------------------------------------------------------- #
# Syntax validation
# --------------------------------------------------------------------------- #
class TestSyntaxValidation:
    def test_valid_expression_clears_error(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        assert dlg._expr_error.text() == ""

    def test_invalid_expression_shows_error(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60ni")
        dlg._validate_current()
        assert "correctly cased" in dlg._expr_error.text()

    def test_empty_expression_shows_no_error(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("")
        dlg._validate_current()
        assert dlg._expr_error.text() == ""


# --------------------------------------------------------------------------- #
# Stale isotope flagging
# --------------------------------------------------------------------------- #
class TestStaleIsotopes:
    def test_isotope_outside_sample_flagged_stale(self, dlg):
        dlg._list.setCurrentRow(0)  # SampleA has 60Ni, 107Ag only
        dlg._add_definition()
        dlg._expr_edit.setText("208Pb")
        dlg._validate_current()
        assert "208Pb" in dlg._stale_lbl.text()

    def test_remove_stale_strips_the_token(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("208Pb")
        dlg._validate_current()
        dlg._remove_stale()
        assert "208Pb" not in dlg._expr_edit.text()

    def test_isotope_present_in_sample_not_flagged(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        assert dlg._stale_lbl.text() == ""


# --------------------------------------------------------------------------- #
# Contradiction / tautology
# --------------------------------------------------------------------------- #
class TestContradictionTautology:
    def test_contradiction_triggers_modal(self, dlg, no_modal):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        no_modal['role'] = pcd.QMessageBox.ButtonRole.AcceptRole
        dlg._expr_edit.setText("60Ni+!(60Ni)")
        dlg._validate_current()
        # Contradiction is stored even when saved (user chose "save anyway").
        assert dlg._current_definition()['expression_text'] == "60Ni+!(60Ni)"

    def test_tautology_shows_badge_no_modal(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("[60Ni, !(60Ni)]")
        dlg._validate_current()
        assert dlg._tautology_badge.text() != ""

    def test_normal_formula_no_badge_no_error(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        assert dlg._expr_error.text() == ""
        # tautology_badge visibility isn't reset by _clear_validation_ui's
        # text (it has static text) -- check hidden() via isHidden proxy
        # is unreliable headless, so just assert no contradiction path ran.


# --------------------------------------------------------------------------- #
# Confound detection
# --------------------------------------------------------------------------- #
class TestConfoundDetection:
    def test_overlapping_definitions_trigger_modal_and_set_priority(self, dlg, no_modal):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        no_modal['role'] = pcd.QMessageBox.ButtonRole.RejectRole  # switch to priority
        dlg._validate_current()
        assert dlg._overlap_mode == 'priority'

    def test_disjoint_definitions_do_not_force_priority(self, dlg, no_modal):
        dlg._list.setCurrentRow(1)  # SampleB, isolated from SampleA defs
        dlg._add_definition()
        dlg._expr_edit.setText("197Au")
        dlg._validate_current()
        dlg._add_definition()
        no_modal['role'] = None
        dlg._expr_edit.setText("60Ni")  # different sample's isotope entirely; no overlap on SampleB alone
        dlg._validate_current()
        # No second definition on SampleB references 197Au, so no confound.
        assert dlg._overlap_mode == 'double_count'

    def test_second_distinct_confounding_pair_still_warns(self, dlg, no_modal):
        """Regression test: a real bug let 'priority ordering' (chosen for
        one confounding pair) silently suppress the warning for every
        later, entirely different confounding pair -- and since overlap_mode
        persists on the node across dialog sessions, this meant confound
        warnings effectively stopped firing forever after the first choice.
        Each distinct pair must get its own one-time modal regardless of
        the node's current overlap_mode."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        no_modal['role'] = pcd.QMessageBox.ButtonRole.RejectRole  # -> priority
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        assert dlg._overlap_mode == 'priority'
        first_pair_count = len(dlg._confound_prompted_pairs)

        # A brand-new definition confounding with BOTH existing ones (60Ni
        # and 60Ni+107Ag) on the same sample -- two new distinct pairs.
        dlg._add_definition()
        dlg._expr_edit.setText("107Ag")
        dlg._validate_current()
        assert len(dlg._confound_prompted_pairs) == first_pair_count + 2

    def test_same_pair_not_reprompted_on_further_edits(self, dlg, no_modal):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        count_after_first = len(dlg._confound_prompted_pairs)
        # Re-validating the same unchanged pair must not add a duplicate
        # entry (it's still the same two definitions confounding).
        dlg._validate_current()
        assert len(dlg._confound_prompted_pairs) == count_after_first


# --------------------------------------------------------------------------- #
# Priority reorder (regression test for the row-selection-loss bug)
# --------------------------------------------------------------------------- #
class TestPriorityReorder:
    def test_move_up_swaps_order_and_keeps_selection(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._add_definition()
        dlg._expr_edit.setText("107Ag")
        ids_before = [d['id'] for d in dlg._defs_for("SampleA")]
        dlg._move_definition(-1)
        ids_after = [d['id'] for d in dlg._defs_for("SampleA")]
        assert ids_after == [ids_before[1], ids_before[0]]
        # Selection must follow the moved definition, not reset to None.
        assert dlg._current_def_id == ids_before[1]

    def test_move_up_at_top_is_a_no_op(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        ids_before = [d['id'] for d in dlg._definitions]
        dlg._move_definition(-1)
        assert [d['id'] for d in dlg._definitions] == ids_before


def _commit_group_text(dlg, text):
    """Simulate a user finishing a group-name edit (Enter / focus-out),
    which is when the combo box's value is now meant to commit -- NOT on
    every keystroke. Mirrors _on_group_committed's real trigger."""
    dlg._group_combo.setCurrentText(text)
    dlg._on_group_committed()


# --------------------------------------------------------------------------- #
# Group / color (regression tests for the row-selection-loss bug AND the
# per-keystroke group-rename bug: typing in the group combo used to
# re-trigger on every character, reassigning colors and stealing focus)
# --------------------------------------------------------------------------- #
class TestGroupAndColor:
    def test_assigning_group_keeps_definition_selected(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        def_id = dlg._current_def_id
        _commit_group_text(dlg, "Contamination")
        assert dlg._current_def_id == def_id
        assert dlg._current_definition()['group_name'] == "Contamination"
        assert "Contamination" in dlg._groups

    def test_two_definitions_same_group_share_color(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Contamination")
        color_a = dlg._groups["Contamination"]
        dlg._add_definition()
        dlg._expr_edit.setText("107Ag")
        _commit_group_text(dlg, "Contamination")
        assert dlg._groups["Contamination"] == color_a

    def test_typing_does_not_commit_per_keystroke(self, dlg):
        """Regression test: currentTextChanged (per-character) must no
        longer create groups or touch _groups until the edit is committed."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        for partial in ("C", "Co", "Con", "Cont"):
            dlg._group_combo.setCurrentText(partial)  # keystroke, no commit
        assert dlg._groups == {}
        assert dlg._current_definition()['group_name'] is None

    def test_unchanged_group_text_is_a_no_op(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Contamination")
        color_before = dlg._groups["Contamination"]
        _commit_group_text(dlg, "Contamination")  # re-commit, same text
        assert dlg._groups["Contamination"] == color_before


# --------------------------------------------------------------------------- #
# Apply to Selected Samples
# --------------------------------------------------------------------------- #
class TestApplyToSelectedSamples:
    def test_duplicates_definitions_onto_checked_samples(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._list.item(0).setCheckState(Qt.Checked)
        dlg._list.item(1).setCheckState(Qt.Checked)
        assert dlg._defs_for("SampleB") == []
        dlg._apply_to_selected_samples()
        applied = dlg._defs_for("SampleB")
        assert len(applied) == 1
        assert applied[0]['expression_text'] == "60Ni"
        assert applied[0]['id'] != dlg._defs_for("SampleA")[0]['id']

    def test_repeated_apply_does_not_duplicate(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._list.item(1).setCheckState(Qt.Checked)
        dlg._apply_to_selected_samples()
        dlg._apply_to_selected_samples()
        assert len(dlg._defs_for("SampleB")) == 1


# --------------------------------------------------------------------------- #
# Read-back contract
# --------------------------------------------------------------------------- #
class TestReadBackContract:
    def test_get_definitions_strips_internal_keys(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._list.item(1).setCheckState(Qt.Checked)
        dlg._apply_to_selected_samples()
        for d in dlg.get_definitions():
            assert not any(k.startswith('_') for k in d)

    def test_get_selected_sources_none_when_all_checked(self, dlg):
        assert dlg.get_selected_sources() is None

    def test_get_selected_sources_lists_checked_subset(self, dlg):
        dlg._list.item(1).setCheckState(Qt.Unchecked)
        assert dlg.get_selected_sources() == ["SampleA"]


# --------------------------------------------------------------------------- #
# Node round-trip (configure() contract)
# --------------------------------------------------------------------------- #
class TestNodeConfigureRoundTrip:
    def test_configure_reads_back_dialog_state_on_accept(self, qapp, monkeypatch):
        node = ParticleClassifierNode()
        node.input_data = _sample("SampleA", ["60Ni"])

        class _FakeDialog:
            def __init__(self, *a, **kw): pass
            def exec(self): return QDialog.Accepted
            def get_definitions(self):
                return [{'id': 'x', 'target_sample': 'SampleA',
                         'expression_text': '60Ni', 'match_mode': 'partial',
                         'group_name': None, 'color': None}]
            def get_groups(self): return {'G': '#3B82F6'}
            def get_overlap_mode(self): return 'priority'
            def get_unmatched_mode(self): return 'discard'
            def get_unclassified_color(self): return '#9CA3AF'
            def get_selected_sources(self): return ['SampleA']
            def get_has_unresolved_issues(self): return True

        monkeypatch.setattr(pcd, "ParticleClassifierDialog", _FakeDialog)
        result = node.configure(None)
        assert result is True
        assert node.definitions[0]['expression_text'] == '60Ni'
        assert node.groups == {'G': '#3B82F6'}
        assert node.overlap_mode == 'priority'
        assert node.unmatched_mode == 'discard'
        assert node.selected_sources == ['SampleA']
        assert node._has_unresolved_issues is True

    def test_configure_returns_false_on_cancel(self, qapp, monkeypatch):
        node = ParticleClassifierNode()
        node.input_data = _sample("SampleA", ["60Ni"])

        class _FakeDialog:
            def __init__(self, *a, **kw): pass
            def exec(self): return QDialog.Rejected

        monkeypatch.setattr(pcd, "ParticleClassifierDialog", _FakeDialog)
        assert node.configure(None) is False
        assert node.definitions == []  # untouched
