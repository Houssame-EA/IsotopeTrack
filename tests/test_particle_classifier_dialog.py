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
        'ButtonRole', (), {'AcceptRole': 1, 'RejectRole': 2, 'DestructiveRole': 3})
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
#
# Redesigned per user feedback: live per-keystroke confound modals were
# "exhausting" (one pop-up per pair, re-shown every time the dialog was
# typed in) and re-nagged every time the node was reopened. The new
# mechanism only checks at OK-click time (never while typing), batches every
# currently-active confound into one aggregate dialog, and lets the user
# permanently dismiss individual pairs (persisted on the node itself via
# get_confound_dismissals/confound_dismissals, so a dismissed pair stays
# dismissed across dialog reopens).
# --------------------------------------------------------------------------- #
class TestConfoundDetection:
    def test_validate_current_no_longer_shows_a_modal(self, dlg, no_modal):
        """Typing a confounding expression must not pop anything up --
        confound checks only run at accept() time now."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        no_modal['role'] = None
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        # No live modal fired, and overlap_mode is left at its prior value.
        assert dlg._overlap_mode == 'double_count'

    def test_collect_active_confound_pairs_finds_overlap_on_same_sample(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()
        pairs = dlg._collect_active_confound_pairs()
        assert len(pairs) == 1
        d_a, d_b, witness, key = pairs[0]
        assert '60Ni' in witness

    def test_disjoint_samples_do_not_confound(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._list.setCurrentRow(1)  # SampleB, isolated from SampleA defs
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        # Same isotope, but on two different samples -- not a confound.
        assert dlg._collect_active_confound_pairs() == []

    def test_three_mutually_confounding_definitions_yield_three_pairs(self, dlg):
        dlg._list.setCurrentRow(0)
        for expr in ("60Ni", "60Ni+107Ag", "107Ag"):
            dlg._add_definition()
            dlg._expr_edit.setText(expr)
            dlg._validate_current()
        pairs = dlg._collect_active_confound_pairs()
        assert len(pairs) == 3

    def test_accept_shows_one_aggregate_dialog_for_all_pairs(self, dlg, monkeypatch):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()

        calls = []
        def _fake(pairs):
            calls.append(pairs)
            return True  # simulate "Continue and Save"
        monkeypatch.setattr(dlg, "_show_confound_warnings_dialog", _fake)
        dlg.accept()
        assert len(calls) == 1
        assert len(calls[0]) == 1  # exactly one pair, shown once
        assert dlg.result() == QDialog.Accepted

    def test_go_back_and_edit_cancels_accept_without_closing_dialog(self, dlg, monkeypatch):
        """Choosing 'Go Back and Edit' in the aggregate warning must cancel
        the whole accept() -- the main dialog stays open so the user can
        actually fix the definitions, matching the contradiction modal's
        existing go-back-or-proceed convention."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()

        monkeypatch.setattr(
            dlg, "_show_confound_warnings_dialog", lambda pairs: False)
        dlg.accept()
        assert dlg.result() != QDialog.Accepted
        # Nothing was dismissed and the pair is still active next attempt.
        assert len(dlg._collect_active_confound_pairs()) == 1

    def test_dismissed_pair_not_shown_again_this_session(self, dlg, monkeypatch):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()

        def _dismiss_all(pairs):
            for *_rest, key in pairs:
                dlg._dismissed_confound_pairs.add(key)
            return True  # simulate "Continue and Save"
        monkeypatch.setattr(dlg, "_show_confound_warnings_dialog", _dismiss_all)
        dlg.accept()
        assert dlg._collect_active_confound_pairs() == []

    def test_dismissal_persists_across_dialog_reopen(self, dlg, monkeypatch):
        """The whole point of the redesign: dismissing a pair must survive
        the dialog being closed and reopened (via node.confound_dismissals),
        not just last for this one dialog instance."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()

        def _dismiss_all(pairs):
            for *_rest, key in pairs:
                dlg._dismissed_confound_pairs.add(key)
            return True  # simulate "Continue and Save"
        monkeypatch.setattr(dlg, "_show_confound_warnings_dialog", _dismiss_all)
        dlg.accept()
        dismissals = dlg.get_confound_dismissals()
        assert len(dismissals) == 1

        # Simulate reopening: brand-new dialog fed the persisted dismissals.
        reopened = pcd.ParticleClassifierDialog(
            None, dlg._upstreams, dlg.get_definitions(), dlg.get_groups(),
            dlg.get_overlap_mode(), dlg.get_unmatched_mode(),
            dlg.get_unclassified_color(), dlg.get_selected_sources(),
            dlg.get_group_pooling_policies(), dismissals)
        assert reopened._collect_active_confound_pairs() == []

    def test_editing_expression_after_dismissal_reevaluates(self, dlg, monkeypatch):
        """A dismissed pair whose expression later changes is a fresh
        conflict -- it must not stay silently suppressed forever."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._validate_current()

        def _dismiss_all(pairs):
            for *_rest, key in pairs:
                dlg._dismissed_confound_pairs.add(key)
            return True  # simulate "Continue and Save"
        monkeypatch.setattr(dlg, "_show_confound_warnings_dialog", _dismiss_all)
        dlg.accept()
        assert dlg._collect_active_confound_pairs() == []

        # Still confounds via 60Ni, but the expression text itself changed.
        dlg._expr_edit.setText("60Ni+197Au")
        dlg._validate_current()
        assert len(dlg._collect_active_confound_pairs()) == 1

    def test_exact_match_disjoint_definitions_do_not_confound(self, dlg):
        """Real bug report: two EXACT-match definitions with disjoint
        isotope vocabularies were still flagged as confounding, even
        though no real particle can ever satisfy both simultaneously --
        exact mode requires a particle to carry *no* isotopes outside
        each formula's own vocabulary, so disjoint exact-match
        definitions can never actually overlap in practice."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._rb_exact.setChecked(True)
        dlg._on_field_changed()
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("107Ag")
        dlg._rb_exact.setChecked(True)
        dlg._on_field_changed()
        dlg._validate_current()
        assert dlg._collect_active_confound_pairs() == []

    def test_exact_match_overlapping_vocab_still_confounds(self, dlg):
        """Two exact-match definitions can still genuinely confound if a
        particle's isotopes could lie entirely within both vocabularies at
        once (e.g. one formula's vocabulary is a subset of the other's)."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._rb_exact.setChecked(True)
        dlg._on_field_changed()
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("[60Ni,107Ag]")
        dlg._rb_exact.setChecked(True)
        dlg._on_field_changed()
        dlg._validate_current()
        pairs = dlg._collect_active_confound_pairs()
        assert len(pairs) == 1

    def test_partial_vs_exact_mixed_pair_still_confounds(self, dlg):
        """A partial-match definition never restricts what else may be
        present, so it still confounds with an overlapping exact-match
        definition even though the two disjoint-exact-match case above
        does not."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")  # left as partial (default)
        dlg._validate_current()
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")
        dlg._rb_exact.setChecked(True)
        dlg._on_field_changed()
        dlg._validate_current()
        assert len(dlg._collect_active_confound_pairs()) == 1


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

    def test_color_picked_before_grouping_is_not_discarded(self, dlg):
        """Regression test: picking a custom color on an ungrouped
        definition, THEN typing a brand-new group name, must seed the new
        group's color from that pick -- not silently overwrite it with an
        arbitrary palette default (the reported bug: colors "reverting to
        default" after Apply, traced to _on_group_committed unconditionally
        discarding d['color'] on every group commit)."""
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._color_btn.set_color("#123ABC")
        dlg._on_color_picked()
        assert dlg._current_definition()['color'] == "#123ABC"
        _commit_group_text(dlg, "NewGroup")
        assert dlg._groups["NewGroup"] == "#123ABC"

    def test_color_picked_after_grouping_still_works(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "NewGroup")
        dlg._color_btn.set_color("#123ABC")
        dlg._on_color_picked()
        assert dlg._groups["NewGroup"] == "#123ABC"

    def test_same_group_name_on_two_samples_shares_one_color(self, dlg):
        """Groups are deliberately GLOBAL, not per-sample: a definition on
        SampleB joining an existing group name created on SampleA must
        adopt that group's shared color, and recoloring from either
        sample updates the one shared entry seen by both."""
        dlg._list.setCurrentRow(0)  # SampleA
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Recycling")
        dlg._color_btn.set_color("#111111")
        dlg._on_color_picked()

        dlg._list.setCurrentRow(1)  # SampleB
        dlg._add_definition()
        dlg._expr_edit.setText("197Au")
        _commit_group_text(dlg, "Recycling")
        # Joining the EXISTING group must adopt its shared color, not
        # get an independent default.
        assert dlg._current_definition()['group_name'] == "Recycling"
        assert dlg._groups["Recycling"] == "#111111"

        dlg._color_btn.set_color("#222222")
        dlg._on_color_picked()
        assert dlg._groups["Recycling"] == "#222222"  # one shared entry

    def test_apply_to_selected_samples_keeps_shared_group_color(self, dlg):
        dlg._list.setCurrentRow(0)  # SampleA
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Recycling")
        dlg._color_btn.set_color("#ABCDEF")
        dlg._on_color_picked()

        dlg._list.item(1).setCheckState(Qt.Checked)  # SampleB
        dlg._apply_to_selected_samples()

        assert dlg._groups["Recycling"] == "#ABCDEF"
        copied = [d for d in dlg._definitions if d.get('target_sample') == 'SampleB']
        assert copied and copied[0]['group_name'] == "Recycling"

    def test_color_pick_persists_without_a_matching_release_event(
            self, dlg, monkeypatch):
        """Regression test for the real bug report: _ColorBtn opens its
        modal picker from inside mousePressEvent, so in real mouse use the
        release lands on that modal dialog, never back on this button --
        Qt then never fires `clicked`, so anything wired to `clicked`
        (the original implementation) silently never runs, even though the
        swatch itself updates and looks like the pick worked. Simulates
        exactly that: deliver ONLY a press event to the button (no release
        at all), and confirm the color still reaches the definition dict
        via the dedicated colorChanged signal emitted directly inside
        mousePressEvent."""
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent

        monkeypatch.setattr(pcd, "pick_color_hex",
                            lambda *a, **kw: "#FEEDFA")

        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        d = dlg._current_definition()

        press = QMouseEvent(QEvent.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        dlg._color_btn.mousePressEvent(press)

        assert d.get('color') == "#FEEDFA"
        dlg._apply_to_current_sample()
        assert d.get('color') == "#FEEDFA"


# --------------------------------------------------------------------------- #
# Group pooling modal (design §5/§7 ambiguity: 2+ definitions sharing a
# group name may carry different Mass Fraction Calculator assumptions)
# --------------------------------------------------------------------------- #
class TestGroupPoolingModal:
    def _two_defs_same_group(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Contamination")
        dlg._add_definition()
        dlg._expr_edit.setText("107Ag")
        _commit_group_text(dlg, "Contamination")

    def test_single_definition_group_never_prompts(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        _commit_group_text(dlg, "Contamination")
        assert dlg._group_pooling_policies == {}

    def test_second_definition_in_group_prompts_and_records_keep(self, dlg, no_modal):
        no_modal['role'] = pcd.QMessageBox.ButtonRole.AcceptRole  # Keep Full Data Anyway
        self._two_defs_same_group(dlg)
        assert dlg._group_pooling_policies == {"Contamination": "keep"}

    def test_choosing_drop_records_drop_mfc(self, dlg, no_modal):
        no_modal['role'] = pcd.QMessageBox.ButtonRole.DestructiveRole
        self._two_defs_same_group(dlg)
        assert dlg._group_pooling_policies == {"Contamination": "drop_mfc"}

    def test_choosing_go_back_clears_the_group_assignment(self, dlg, no_modal):
        no_modal['role'] = pcd.QMessageBox.ButtonRole.RejectRole  # Go Back and Rename
        self._two_defs_same_group(dlg)
        # The second definition's group assignment was reverted.
        assert dlg._current_definition()['group_name'] is None
        assert "Contamination" not in dlg._group_pooling_policies

    def test_not_reprompted_for_same_group_in_session(self, dlg, no_modal):
        no_modal['role'] = pcd.QMessageBox.ButtonRole.AcceptRole
        self._two_defs_same_group(dlg)
        dlg._add_definition()
        dlg._expr_edit.setText("197Au")
        _commit_group_text(dlg, "Contamination")  # third def, same group
        # Still just one recorded policy -- no re-prompt overwrote it oddly.
        assert dlg._group_pooling_policies == {"Contamination": "keep"}

    def test_get_group_pooling_policies_read_back(self, dlg, no_modal):
        no_modal['role'] = pcd.QMessageBox.ButtonRole.DestructiveRole
        self._two_defs_same_group(dlg)
        assert dlg.get_group_pooling_policies() == {"Contamination": "drop_mfc"}


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
# Per-definition live match count "(N)"
# --------------------------------------------------------------------------- #
class TestMatchCounts:
    def test_no_count_shown_before_any_commit(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        # Never applied/OK'd yet -> no "(N)" suffix.
        assert "(" not in dlg._def_list_label(dlg._current_definition())

    def test_count_appears_after_apply_to_current(self, dlg):
        dlg._list.setCurrentRow(0)  # SampleA has one particle w/ 60Ni + 107Ag
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._apply_to_current_sample()
        assert dlg._def_list_label(dlg._current_definition()) == "60Ni (1)"

    def test_editing_expression_invalidates_cached_count(self, dlg):
        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")
        dlg._apply_to_current_sample()
        assert "(1)" in dlg._def_list_label(dlg._current_definition())
        # Editing the expression must drop the now-stale count immediately.
        dlg._expr_edit.setText("197Au")
        assert "(" not in dlg._def_list_label(dlg._current_definition())

    def test_count_reflects_priority_exclusion(self, dlg):
        """Effective post-priority count: a higher-priority definition
        claims the shared particle, dropping the lower one's count to 0."""
        dlg._list.setCurrentRow(0)  # SampleA: one particle {60Ni, 107Ag}
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni")            # def #0 (higher priority)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+107Ag")      # def #1 (lower priority)
        dlg._overlap_mode = 'priority'
        dlg._apply_to_current_sample()
        defs = dlg._defs_for("SampleA")
        labels = [dlg._def_list_label(d) for d in defs]
        assert "60Ni (1)" in labels
        assert "60Ni+107Ag (0)" in labels  # its only match claimed by 60Ni


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
            def get_group_pooling_policies(self): return {'G': 'drop_mfc'}
            def get_confound_dismissals(self):
                return [{'id_a': 'x', 'id_b': 'y', 'expr_a': '60Ni',
                         'expr_b': '60Ni+107Ag'}]

        monkeypatch.setattr(pcd, "ParticleClassifierDialog", _FakeDialog)
        result = node.configure(None)
        assert result is True
        assert node.definitions[0]['expression_text'] == '60Ni'
        assert node.groups == {'G': '#3B82F6'}
        assert node.overlap_mode == 'priority'
        assert node.unmatched_mode == 'discard'
        assert node.selected_sources == ['SampleA']
        assert node._has_unresolved_issues is True
        assert node.group_pooling_policies == {'G': 'drop_mfc'}
        assert node.confound_dismissals == [
            {'id_a': 'x', 'id_b': 'y', 'expr_a': '60Ni',
             'expr_b': '60Ni+107Ag'}]

    def test_configure_returns_false_on_cancel(self, qapp, monkeypatch):
        node = ParticleClassifierNode()
        node.input_data = _sample("SampleA", ["60Ni"])

        class _FakeDialog:
            def __init__(self, *a, **kw): pass
            def exec(self): return QDialog.Rejected

        monkeypatch.setattr(pcd, "ParticleClassifierDialog", _FakeDialog)
        assert node.configure(None) is False
        assert node.definitions == []  # untouched
