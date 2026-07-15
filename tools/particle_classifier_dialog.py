# -*- coding: utf-8 -*-
"""Particle Classifier configuration dialog (Stage 3).

Per-sample-first LHS/RHS UI per ``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §3:
a table of every incoming sample on the left (checkbox = include in output +
bulk-apply target; click = navigate, these are deliberately separate
mechanisms — see ``ParticleFilterDialog`` in ``tools/particle_filter.py`` for
the precedent this mirrors), and a working panel on the right for whichever
sample is currently navigated to, listing that sample's classifier
definitions with live syntax/stale/contradiction/confound validation (§5,
§9) built on top of the Stage 1 expression engine
(``tools/particle_classifier_expr.py``).

Definitions are stored as one flat, global, priority-ordered list on the
node (:class:`tools.particle_classifier_node.ParticleClassifierNode`); each
definition is scoped to exactly one sample via its ``target_sample`` field.
This dialog is the only place that list is edited.
"""

from __future__ import annotations

import copy as _copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QComboBox, QGroupBox, QDialogButtonBox, QListWidget, QListWidgetItem,
    QSplitter, QScrollArea, QFrame, QLineEdit, QRadioButton, QButtonGroup,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from tools.theme import theme as _app_theme
from tools.particle_filter import normalize_sources, source_labels
from tools.particle_classifier_node import (
    new_definition_id, DEFAULT_UNCLASSIFIED_COLOR,
)
from tools.particle_classifier_expr import (
    parse, ExpressionSyntaxError, referenced_isotopes, find_confound,
    classify_formula,
)
from results.shared_plot_utils import pick_color_hex, DEFAULT_SAMPLE_COLORS

import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_dialog")

_ERROR_COLOR = "#EF4444"
_WARNING_COLOR = "#F59E0B"


class _ColorBtn(QPushButton):
    """Small color-square button that opens the shared color picker.

    Copied verbatim from ``results/results_pie_charts.py``'s ``_ColorBtn`` —
    the established color-square pattern this project's design doc points to
    (see ``pick_color_hex`` in ``results/shared_plot_utils.py``).
    """

    def __init__(self, color='#FFFFFF', parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 20)
        self._color = color
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            "QPushButton {"
            f"background-color:{self._color};"
            "border:1px solid #666;border-radius:2px;"
            "}"
        )

    def color(self):
        return self._color

    def set_color(self, c):
        self._color = c
        self._apply()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            picked = pick_color_hex(self._color, owner=self,
                                    title="Select Color")
            if picked:
                self.set_color(picked)
        super().mousePressEvent(event)


def _next_palette_color(used_colors):
    """Pick the next unused color from the app's default sample palette.

    Args:
        used_colors (set): Colors already assigned to existing groups.

    Returns:
        str: A hex color, falling back to the first palette entry if every
            palette color is already in use.
    """
    for c in DEFAULT_SAMPLE_COLORS:
        if c not in used_colors:
            return c
    return DEFAULT_SAMPLE_COLORS[0]


class ParticleClassifierDialog(QDialog):
    """Per-sample-first configurator for the Particle Classifier node.

    Left pane: every incoming sample with a checkbox (include in output +
    bulk-apply target). Right pane: the classifier definitions of the
    sample currently clicked, with live syntax/stale/contradiction/confound
    validation. "Apply to Current/Selected Samples" copies the current
    panel's definitions onto other samples (as independent copies with
    their own ``target_sample`` and ``id``, per design §4's "no
    definition-reuse across samples" model).
    """

    _VALIDATE_DEBOUNCE_MS = 250

    def __init__(self, parent, upstreams, definitions=None, groups=None,
                 overlap_mode='double_count', unmatched_mode='unclassified',
                 unclassified_color=None, selected_sources=None):
        super().__init__(parent)
        self.setWindowTitle("Particle Classifier Configuration")
        self.setModal(True)
        self.resize(1040, 720)
        self.setMinimumSize(880, 600)
        self.setStyleSheet(self._style())
        _app_theme.themeChanged.connect(
            lambda _: self.setStyleSheet(self._style()))

        self.parent_window = parent
        if isinstance(upstreams, dict):
            upstreams = [upstreams]
        self._upstreams = [u for u in (upstreams or []) if u]
        self._sources = normalize_sources(self._upstreams)
        self._src_by_name = {s['name']: s for s in self._sources}

        self._definitions = _copy.deepcopy(definitions) if definitions else []
        self._groups = _copy.deepcopy(groups) if groups else {}
        self._overlap_mode = overlap_mode or 'double_count'
        self._unmatched_mode = unmatched_mode or 'unclassified'
        self._unclassified_color = (
            unclassified_color or DEFAULT_UNCLASSIFIED_COLOR)
        self._selected_sources = (list(selected_sources)
                                  if selected_sources is not None else None)

        self._current = None
        self._current_def_id = None
        self._loading = False
        self._has_unresolved_issues = False
        self._confound_prompted_pairs = set()

        self._validate_timer = QTimer(self)
        self._validate_timer.setSingleShot(True)
        self._validate_timer.setInterval(self._VALIDATE_DEBOUNCE_MS)
        self._validate_timer.timeout.connect(self._validate_current)

        self._build()

        if self._sources:
            self._list.setCurrentRow(0)
        else:
            self._load_pane(None)

    # ------------------------------------------------------------------ #
    # Styling
    # ------------------------------------------------------------------ #
    @staticmethod
    def _style():
        """Build the dialog stylesheet for the current app theme.

        Returns:
            str: ``_dialog_base_style()`` plus group-box/list styling,
                mirroring ``ParticleFilterDialog._style``.
        """
        from widget.canvas_widgets import _dialog_base_style
        p = _app_theme.palette
        return _dialog_base_style() + f"""
        QGroupBox {{
            border: 1px solid {p.border};
            border-radius: 8px;
            margin-top: 12px;
            padding: 14px 10px 10px 10px;
            font-weight: 600;
            color: {p.text_primary};
            background: {p.bg_secondary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }}
        QListWidget {{
            background: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            font-size: 12px;
        }}
        QListWidget::item {{
            padding: 6px 6px;
            border-radius: 5px;
        }}
        QListWidget::item:selected {{
            background: {p.accent_soft};
            color: {p.text_primary};
        }}
        """

    @staticmethod
    def _section_label(text):
        """Build a small uppercase section label (mirrors ParticleFilterDialog)."""
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:700; letter-spacing:1px;"
            f" color:{_app_theme.palette.text_muted}; padding-bottom:2px;")
        return lbl

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        p = _app_theme.palette
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([300, 740])
        root.addWidget(splitter, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _build_left(self):
        p = _app_theme.palette
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        lv.addWidget(self._section_label("Samples"))
        hint = QLabel("Check = include in output  ·  Click = edit its definitions")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{p.text_muted}; font-size:11px; font-weight:400;")
        lv.addWidget(hint)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_checked)
        if self._sources:
            for s in self._sources:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, s['name'])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                checked = (self._selected_sources is None
                           or s['name'] in self._selected_sources)
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                self._list.addItem(item)
                self._refresh_row(item)
        else:
            ph = QListWidgetItem("No samples connected yet")
            ph.setFlags(Qt.NoItemFlags)
            self._list.addItem(ph)
        lv.addWidget(self._list, 1)

        btn_all = QPushButton("Select All Samples")
        btn_all.clicked.connect(self._select_all_samples)
        lv.addWidget(btn_all)

        grp_um = QGroupBox("Unmatched Particles")
        umv = QVBoxLayout(grp_um)
        self._um_group = QButtonGroup(self)
        self._rb_unclassified = QRadioButton("Unclassified bucket")
        self._rb_discard = QRadioButton("Discard")
        self._rb_passthrough = QRadioButton("Pass-through as original")
        for i, rb in enumerate(
                (self._rb_unclassified, self._rb_discard, self._rb_passthrough)):
            self._um_group.addButton(rb, i)
            umv.addWidget(rb)
        {'unclassified': self._rb_unclassified,
         'discard': self._rb_discard,
         'passthrough': self._rb_passthrough}[self._unmatched_mode].setChecked(True)
        self._um_group.buttonClicked.connect(self._on_unmatched_mode_changed)
        lv.addWidget(grp_um)

        grp_ov = QGroupBox("Overlapping Definitions")
        ovv = QVBoxLayout(grp_ov)
        self._ov_group = QButtonGroup(self)
        self._rb_double_count = QRadioButton("Allow double-counting")
        self._rb_priority = QRadioButton("Priority ordering")
        self._ov_group.addButton(self._rb_double_count, 0)
        self._ov_group.addButton(self._rb_priority, 1)
        ovv.addWidget(self._rb_double_count)
        ovv.addWidget(self._rb_priority)
        (self._rb_priority if self._overlap_mode == 'priority'
         else self._rb_double_count).setChecked(True)
        self._ov_group.buttonClicked.connect(self._on_overlap_mode_changed)
        lv.addWidget(grp_ov)

        return left

    def _build_right(self):
        p = _app_theme.palette
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 0, 0, 0)
        rv.setSpacing(6)

        head = QHBoxLayout()
        self._pane_title = QLabel("Definitions")
        self._pane_title.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{p.text_primary};")
        head.addWidget(self._pane_title, 1)
        btn_help = QPushButton("Help")
        btn_help.clicked.connect(self._show_help)
        head.addWidget(btn_help)
        rv.addLayout(head)

        apply_row = QHBoxLayout()
        btn_apply_current = QPushButton("Apply to Current Sample")
        btn_apply_current.clicked.connect(self._apply_to_current_sample)
        btn_apply_selected = QPushButton("Apply to Selected Samples")
        btn_apply_selected.clicked.connect(self._apply_to_selected_samples)
        apply_row.addWidget(btn_apply_current)
        apply_row.addWidget(btn_apply_selected)
        rv.addLayout(apply_row)

        splitter = QSplitter(Qt.Horizontal)

        defs_col = QWidget()
        dcv = QVBoxLayout(defs_col)
        dcv.setContentsMargins(0, 0, 0, 0)
        dcv.setSpacing(6)
        dcv.addWidget(self._section_label("Definitions (priority order)"))
        self._def_list = QListWidget()
        self._def_list.currentRowChanged.connect(self._on_def_selected)
        dcv.addWidget(self._def_list, 1)

        def_btn_row = QHBoxLayout()
        btn_new = QPushButton("+ New")
        btn_new.clicked.connect(self._add_definition)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_current_definition)
        def_btn_row.addWidget(btn_new)
        def_btn_row.addWidget(btn_del)
        dcv.addLayout(def_btn_row)

        prio_row = QHBoxLayout()
        self._btn_up = QPushButton("▲ Move Up")
        self._btn_up.clicked.connect(lambda: self._move_definition(-1))
        self._btn_down = QPushButton("▼ Move Down")
        self._btn_down.clicked.connect(lambda: self._move_definition(1))
        prio_row.addWidget(self._btn_up)
        prio_row.addWidget(self._btn_down)
        dcv.addLayout(prio_row)
        self._prio_hint = QLabel(
            "Priority order only affects output when \"Priority ordering\" "
            "is selected under Overlapping Definitions.")
        self._prio_hint.setWordWrap(True)
        self._prio_hint.setStyleSheet(
            f"color:{p.text_muted}; font-size:10px; font-weight:400;")
        dcv.addWidget(self._prio_hint)

        splitter.addWidget(defs_col)
        splitter.addWidget(self._build_edit_panel())
        splitter.setSizes([260, 480])
        rv.addWidget(splitter, 1)

        return right

    def _build_edit_panel(self):
        p = _app_theme.palette
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(8, 0, 0, 0)
        pv.setSpacing(8)

        pv.addWidget(self._section_label("Expression"))
        self._expr_edit = QLineEdit()
        self._expr_edit.setPlaceholderText("e.g. 60Ni+107Ag  or  [60Ni, 197Au]")
        self._expr_edit.textChanged.connect(self._on_expr_changed)
        pv.addWidget(self._expr_edit)

        self._expr_error = QLabel()
        self._expr_error.setWordWrap(True)
        self._expr_error.setStyleSheet(
            f"color:{_ERROR_COLOR}; font-size:11px; font-weight:600;")
        self._expr_error.hide()
        pv.addWidget(self._expr_error)

        self._tautology_badge = QLabel(
            "ⓘ Tautology: this formula matches any combination of its "
            "referenced isotopes.")
        self._tautology_badge.setWordWrap(True)
        self._tautology_badge.setStyleSheet(
            f"color:{p.text_muted}; font-size:11px; font-style:italic;"
            f" border:1px dashed {p.border}; border-radius:4px; padding:4px;")
        self._tautology_badge.hide()
        pv.addWidget(self._tautology_badge)

        stale_row = QHBoxLayout()
        self._stale_lbl = QLabel()
        self._stale_lbl.setWordWrap(True)
        self._stale_lbl.setStyleSheet(
            f"color:{_WARNING_COLOR}; font-size:11px; font-style:italic;"
            f" border:1px dashed {_WARNING_COLOR}; border-radius:4px; padding:4px;")
        self._stale_lbl.hide()
        self._btn_rm_stale = QPushButton("Remove stale")
        self._btn_rm_stale.clicked.connect(self._remove_stale)
        self._btn_rm_stale.hide()
        stale_row.addWidget(self._stale_lbl, 1)
        stale_row.addWidget(self._btn_rm_stale)
        pv.addLayout(stale_row)

        match_row = QHBoxLayout()
        self._match_group = QButtonGroup(self)
        self._rb_exact = QRadioButton(
            "Show selected isotopes only (exact match)")
        self._rb_partial = QRadioButton(
            "Show selected isotopes present (partial match)")
        self._match_group.addButton(self._rb_exact, 0)
        self._match_group.addButton(self._rb_partial, 1)
        self._rb_partial.setChecked(True)
        self._match_group.buttonClicked.connect(self._on_field_changed)
        match_row.addWidget(self._rb_partial)
        match_row.addWidget(self._rb_exact)
        pv.addLayout(match_row)

        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("Group:"))
        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        # Commit on Enter / dropdown-pick / focus-out only -- NOT on every
        # keystroke. currentTextChanged fires per-character in an editable
        # combo box, which previously treated every partial string typed
        # ("C", "Co", "Con"...) as a brand-new group (reassigning colors
        # each time) and rebuilt the sibling definitions list mid-keystroke,
        # stealing focus out of this box.
        self._group_combo.activated.connect(self._on_group_committed)
        self._group_combo.lineEdit().editingFinished.connect(
            self._on_group_committed)
        group_row.addWidget(self._group_combo, 1)
        group_row.addWidget(QLabel("Color:"))
        self._color_btn = _ColorBtn(DEFAULT_SAMPLE_COLORS[0])
        self._color_btn.clicked.connect(self._on_color_picked)
        group_row.addWidget(self._color_btn)
        pv.addLayout(group_row)

        pv.addStretch()
        scroll.setWidget(panel)
        return scroll

    # ------------------------------------------------------------------ #
    # LHS: sample navigation / checkbox
    # ------------------------------------------------------------------ #
    def _refresh_row(self, item):
        name = item.data(Qt.UserRole)
        if not name:
            return
        s = self._src_by_name.get(name)
        n_defs = len(self._defs_for(name))
        text = f"{name}   ({s['total'] if s else 0})"
        if n_defs:
            text += f"\n      {n_defs} definition" + ("s" if n_defs != 1 else "")
        item.setText(text)

    def _on_row_changed(self, current, previous):
        if previous is not None and previous.data(Qt.UserRole):
            self._refresh_row(previous)
        name = current.data(Qt.UserRole) if current else None
        self._load_pane(name)

    def _on_item_checked(self, item):
        pass

    def _checked_names(self):
        names = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.data(Qt.UserRole)
            if name and item.checkState() == Qt.Checked:
                names.append(name)
        return names

    def _select_all_samples(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole):
                item.setCheckState(Qt.Checked)

    # ------------------------------------------------------------------ #
    # Definitions storage helpers
    # ------------------------------------------------------------------ #
    def _defs_for(self, sample_name):
        """List definitions targeting one sample, in global priority order."""
        return [d for d in self._definitions
                if d.get('target_sample') == sample_name]

    def _find_def(self, def_id):
        for d in self._definitions:
            if d['id'] == def_id:
                return d
        return None

    # ------------------------------------------------------------------ #
    # RHS: pane load / definitions list
    # ------------------------------------------------------------------ #
    def _load_pane(self, name):
        self._loading = True
        self._current = name
        self._pane_title.setText(f"Definitions — {name}" if name else "Definitions")
        self._refresh_def_list()
        if self._def_list.count():
            self._def_list.setCurrentRow(0)
            self._on_def_selected(0)
        else:
            self._current_def_id = None
            self._load_definition_into_editor(None)
        self._loading = False

    def _refresh_def_list(self):
        self._def_list.clear()
        for d in self._defs_for(self._current):
            self._def_list.addItem(self._def_list_label(d))

    def _def_list_label(self, d):
        name = d.get('group_name') or d.get('expression_text') or "(empty)"
        return f"{name}"

    def _on_def_selected(self, row):
        defs = self._defs_for(self._current)
        if 0 <= row < len(defs):
            self._current_def_id = defs[row]['id']
            self._load_definition_into_editor(defs[row])
        else:
            self._current_def_id = None
            self._load_definition_into_editor(None)

    def _load_definition_into_editor(self, d):
        self._loading = True
        if d is None:
            self._expr_edit.setText("")
            self._rb_partial.setChecked(True)
            self._group_combo.setCurrentText("")
            self._color_btn.set_color(DEFAULT_SAMPLE_COLORS[0])
            self._expr_edit.setEnabled(False)
            self._group_combo.setEnabled(False)
            self._color_btn.setEnabled(False)
            self._rb_exact.setEnabled(False)
            self._rb_partial.setEnabled(False)
            self._clear_validation_ui()
        else:
            self._expr_edit.setEnabled(True)
            self._group_combo.setEnabled(True)
            self._color_btn.setEnabled(True)
            self._rb_exact.setEnabled(True)
            self._rb_partial.setEnabled(True)
            self._expr_edit.setText(d.get('expression_text', ''))
            (self._rb_exact if d.get('match_mode') == 'exact'
             else self._rb_partial).setChecked(True)
            self._refresh_group_combo()
            self._group_combo.setCurrentText(d.get('group_name') or '')
            self._color_btn.set_color(
                d.get('color') or self._color_for_definition(d))
        self._loading = False
        if d is not None:
            self._validate_current()

    def _refresh_group_combo(self):
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("")
        for name in sorted(self._groups):
            self._group_combo.addItem(name)
        self._group_combo.blockSignals(False)

    def _color_for_definition(self, d):
        """Resolve a definition's effective color (own color, group color,
        or the next free palette slot for an ungrouped definition)."""
        group = d.get('group_name')
        if group and group in self._groups:
            return self._groups[group]
        if d.get('color'):
            return d['color']
        used = set(self._groups.values()) | {
            x.get('color') for x in self._definitions if x.get('color')}
        return _next_palette_color(used)

    # ------------------------------------------------------------------ #
    # Definition list actions: new / delete / reorder
    # ------------------------------------------------------------------ #
    def _add_definition(self):
        if not self._current:
            return
        d = {
            'id': new_definition_id(),
            'target_sample': self._current,
            'expression_text': '',
            'match_mode': 'partial',
            'group_name': None,
            'color': None,
        }
        self._definitions.append(d)
        _itk_log.info("Added classifier definition %s on sample %r",
                      d['id'], self._current)
        self._refresh_def_list()
        last_row = self._def_list.count() - 1
        self._def_list.setCurrentRow(last_row)
        self._on_def_selected(last_row)
        self._refresh_row_for(self._current)

    def _delete_current_definition(self):
        if not self._current_def_id:
            return
        d = self._find_def(self._current_def_id)
        if d:
            self._definitions.remove(d)
            _itk_log.info("Deleted classifier definition %s", d['id'])
        self._current_def_id = None
        self._refresh_def_list()
        if self._def_list.count():
            self._def_list.setCurrentRow(0)
            self._on_def_selected(0)
        else:
            self._load_definition_into_editor(None)
        self._refresh_row_for(self._current)

    def _move_definition(self, delta):
        """Move the current definition up/down within the GLOBAL priority
        list (self._definitions), then refresh the sample-filtered view."""
        if not self._current_def_id:
            return
        idx = next((i for i, d in enumerate(self._definitions)
                    if d['id'] == self._current_def_id), None)
        if idx is None:
            return
        new_idx = idx + delta
        if not (0 <= new_idx < len(self._definitions)):
            return
        self._definitions[idx], self._definitions[new_idx] = (
            self._definitions[new_idx], self._definitions[idx])
        _itk_log.info("Reordered classifier definition %s: priority %d -> %d",
                      self._current_def_id, idx, new_idx)
        self._reselect_definition_after_rebuild(self._current_def_id)

    def _refresh_row_for(self, sample_name):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) == sample_name:
                self._refresh_row(item)
                break

    # ------------------------------------------------------------------ #
    # Field edits -> write back into the definition dict
    # ------------------------------------------------------------------ #
    def _current_definition(self):
        return self._find_def(self._current_def_id) if self._current_def_id else None

    def _on_expr_changed(self, text):
        d = self._current_definition()
        if d is None or self._loading:
            return
        d['expression_text'] = text
        self._validate_timer.start()

    def _on_field_changed(self, *_a):
        d = self._current_definition()
        if d is None or self._loading:
            return
        d['match_mode'] = 'exact' if self._rb_exact.isChecked() else 'partial'
        _itk_log.info("Definition %s match_mode -> %s", d['id'], d['match_mode'])

    def _on_group_committed(self, *_a):
        """Commit the group-name field once the user finishes editing it
        (Enter, picking from the dropdown, or focus-out) — not on every
        keystroke. See the comment at the combo box's signal wiring."""
        d = self._current_definition()
        if d is None or self._loading:
            return
        def_id = d['id']
        text = (self._group_combo.currentText() or '').strip()
        if text == (d.get('group_name') or ''):
            return  # unchanged -- avoid pointless list rebuilds/refocus
        d['group_name'] = text or None
        if text:
            if text not in self._groups:
                used = set(self._groups.values())
                self._groups[text] = _next_palette_color(used)
                _itk_log.info("Created classifier group %r with color %s",
                              text, self._groups[text])
            self._color_btn.set_color(self._groups[text])
            d['color'] = None
        self._reselect_definition_after_rebuild(def_id)
        self._refresh_row_for(self._current)

    def _reselect_definition_after_rebuild(self, def_id):
        """Rebuild the definitions list widget and restore the given
        definition's selection.

        ``QListWidget.clear()`` (inside ``_refresh_def_list``) resets
        ``currentRow()`` to -1, which fires ``currentRowChanged(-1)`` and
        would otherwise clobber ``_current_def_id`` mid-edit — the same
        "signal fires during rebuild" class of bug this file already guards
        against in ``_move_definition``/``_add_definition``/etc.
        """
        self._refresh_def_list()
        defs = self._defs_for(self._current)
        row = next((i for i, d in enumerate(defs) if d['id'] == def_id), 0)
        self._def_list.setCurrentRow(row)
        self._current_def_id = def_id

    def _on_color_picked(self):
        d = self._current_definition()
        if d is None:
            return
        color = self._color_btn.color()
        group = d.get('group_name')
        if group:
            self._groups[group] = color
            _itk_log.info("Group %r color -> %s", group, color)
        else:
            d['color'] = color
            _itk_log.info("Definition %s color -> %s", d['id'], color)

    def _on_unmatched_mode_changed(self, *_a):
        self._unmatched_mode = (
            'unclassified' if self._rb_unclassified.isChecked() else
            'discard' if self._rb_discard.isChecked() else 'passthrough')
        _itk_log.info("Unmatched-particle mode -> %s", self._unmatched_mode)

    def _on_overlap_mode_changed(self, *_a):
        self._overlap_mode = (
            'priority' if self._rb_priority.isChecked() else 'double_count')
        _itk_log.info("Overlap mode -> %s", self._overlap_mode)

    # ------------------------------------------------------------------ #
    # Validation: syntax, stale isotopes, contradiction/tautology, confound
    # ------------------------------------------------------------------ #
    def _clear_validation_ui(self):
        self._expr_error.setText("")
        self._expr_error.hide()
        self._tautology_badge.hide()
        self._stale_lbl.setText("")
        self._stale_lbl.hide()
        self._btn_rm_stale.hide()

    def _validate_current(self):
        d = self._current_definition()
        if d is None:
            self._clear_validation_ui()
            return
        text = d.get('expression_text', '')
        self._clear_validation_ui()
        if not text.strip():
            self._recompute_unresolved_issues()
            return
        try:
            ast = parse(text)
        except ExpressionSyntaxError as exc:
            self._expr_error.setText(f"⚠ {exc}")
            self._expr_error.show()
            _itk_log.warning("Definition %s syntax error: %s", d['id'], exc)
            self._recompute_unresolved_issues()
            return

        self._check_stale(d, ast)

        verdict = classify_formula(ast)
        if verdict == "contradiction":
            proceed = self._show_contradiction_modal(d)
            _itk_log.warning(
                "Definition %s is a contradiction (user chose %s)",
                d['id'], "save anyway" if proceed else "go back")
        elif verdict == "tautology":
            self._tautology_badge.show()

        self._check_confound(d, ast)
        self._recompute_unresolved_issues()

    def _check_stale(self, d, ast):
        source = self._src_by_name.get(self._current)
        if source is None:
            return
        available = source_labels(source)
        referenced = referenced_isotopes(ast)
        stale = sorted(referenced - available)
        if stale:
            self._stale_lbl.setText(
                "⚠ Not in this sample's data (ignored while classifying): "
                + ", ".join(stale))
            self._stale_lbl.show()
            self._btn_rm_stale.show()
            _itk_log.info("Definition %s has stale isotopes: %s",
                         d['id'], stale)

    def _remove_stale(self):
        d = self._current_definition()
        if d is None:
            return
        source = self._src_by_name.get(self._current)
        available = source_labels(source) if source else set()
        try:
            ast = parse(d.get('expression_text', ''))
        except ExpressionSyntaxError:
            return
        referenced = referenced_isotopes(ast)
        stale = referenced - available
        if not stale:
            return
        _itk_log.info("Removing stale isotopes from definition %s: %s",
                      d['id'], sorted(stale))
        # Textual removal: strip each stale isotope token; leaves a
        # dangling operator only in pathological hand-edited cases, which
        # will surface as a normal syntax error the user can then fix.
        text = d.get('expression_text', '')
        for iso in stale:
            text = text.replace(iso, '')
        d['expression_text'] = text
        self._expr_edit.setText(text)

    def _show_contradiction_modal(self, d):
        """Warning-and-choice modal for a self-contradictory definition.

        Mirrors the ``calibration_methods/ionic_CAL.py`` single-point
        calibration modal template (design §9.3).

        Returns:
            bool: True if the user chose to save anyway.
        """
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Contradictory Definition")
        dlg.setIcon(QMessageBox.Icon.Warning)
        name = d.get('group_name') or d.get('expression_text') or "This definition"
        dlg.setText(f"<b>{name}</b> can never match any particle.")
        dlg.setInformativeText(
            "Its expression is a logical contradiction — no combination of "
            "present/absent isotopes satisfies it. You can go back and fix "
            "the expression, or save it anyway (it will simply never "
            "classify any particles).")
        btn_back = dlg.addButton("Go Back and Fix",
                                 QMessageBox.ButtonRole.RejectRole)
        btn_save = dlg.addButton("Save Anyway",
                                 QMessageBox.ButtonRole.AcceptRole)
        dlg.setDefaultButton(btn_back)
        dlg.exec()
        return dlg.clickedButton() is btn_save

    def _check_confound(self, d, ast):
        """Structural confound check against every other definition on the
        same sample (design §5)."""
        others = [x for x in self._defs_for(self._current) if x['id'] != d['id']]
        for other in others:
            try:
                other_ast = parse(other.get('expression_text', ''))
            except ExpressionSyntaxError:
                continue
            witness = find_confound(ast, other_ast)
            if witness is None:
                continue
            pair_key = frozenset({d['id'], other['id']})
            if pair_key in self._confound_prompted_pairs:
                continue
            self._confound_prompted_pairs.add(pair_key)
            _itk_log.warning(
                "Confound detected between definitions %s and %s on "
                "sample %r: %s", d['id'], other['id'], self._current,
                sorted(witness))
            self._show_confound_modal(d, other)

    def _show_confound_modal(self, def_a, def_b):
        """Node-level warning-and-choice modal for a detected confound
        (design §5): explain by name, offer Allow double-counting (default)
        or switch to Priority ordering."""
        name_a = def_a.get('group_name') or def_a.get('expression_text') or "Definition A"
        name_b = def_b.get('group_name') or def_b.get('expression_text') or "Definition B"
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Overlapping Definitions Detected")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(
            f"Your definitions allow the same particle to fit both "
            f"<b>{name_a}</b> and <b>{name_b}</b>.")
        dlg.setInformativeText(
            "This applies to the whole node, not just this pair: choose "
            "whether overlapping definitions may both claim the same "
            "particle (double-counting), or whether priority order should "
            "decide — once a particle is claimed by a higher-priority "
            "definition, lower-priority definitions never see it.")
        btn_double = dlg.addButton("Allow Double-Counting",
                                   QMessageBox.ButtonRole.AcceptRole)
        btn_priority = dlg.addButton("Switch to Priority Ordering",
                                     QMessageBox.ButtonRole.RejectRole)
        dlg.setDefaultButton(btn_double)
        dlg.exec()
        if dlg.clickedButton() is btn_priority:
            self._overlap_mode = 'priority'
            self._rb_priority.setChecked(True)
        else:
            self._overlap_mode = 'double_count'
            self._rb_double_count.setChecked(True)
        _itk_log.info("Overlap mode set via confound modal -> %s",
                      self._overlap_mode)

    def _recompute_unresolved_issues(self):
        """Refresh the has-unresolved-issues flag (drives the node icon's
        warning badge): true when any definition currently has a stale
        isotope reference."""
        has_issue = False
        for d in self._definitions:
            text = d.get('expression_text', '')
            if not text.strip():
                continue
            try:
                ast = parse(text)
            except ExpressionSyntaxError:
                has_issue = True
                continue
            source = self._src_by_name.get(d.get('target_sample'))
            if source is None:
                continue
            available = source_labels(source)
            if referenced_isotopes(ast) - available:
                has_issue = True
        self._has_unresolved_issues = has_issue

    # ------------------------------------------------------------------ #
    # Apply to Current / Selected Samples
    # ------------------------------------------------------------------ #
    def _apply_to_current_sample(self):
        if self._current:
            _itk_log.info("Applied panel state to current sample %r",
                          self._current)
            self._refresh_row_for(self._current)

    def _apply_to_selected_samples(self):
        if not self._current:
            return
        targets = [n for n in self._checked_names() if n != self._current]
        if not targets:
            return
        source_defs = self._defs_for(self._current)
        for target in targets:
            # Remove any previous definitions this dialog session applied
            # to the target sample before, so repeated "Apply" clicks don't
            # accumulate duplicates.
            self._definitions = [
                d for d in self._definitions
                if not (d.get('target_sample') == target
                        and d.get('_applied_from') == self._current)]
            for d in source_defs:
                copy_d = _copy.deepcopy(d)
                copy_d['id'] = new_definition_id()
                copy_d['target_sample'] = target
                copy_d['_applied_from'] = self._current
                self._definitions.append(copy_d)
            self._refresh_row_for(target)
        _itk_log.info(
            "Applied %d definition(s) from sample %r to selected samples: %s",
            len(source_defs), self._current, targets)
        self._refresh_def_list()

    # ------------------------------------------------------------------ #
    # Help
    # ------------------------------------------------------------------ #
    def _show_help(self):
        QMessageBox.information(
            self, "Particle Classifier Help",
            "<b>Expression syntax</b><br>"
            "&bull; <code>+</code> = AND (e.g. <code>60Ni+107Ag</code>)<br>"
            "&bull; <code>[a, b]</code> = OR across branches<br>"
            "&bull; <code>{a; b}</code> = one-hot XOR (exactly one branch)<br>"
            "&bull; <code>!(a)</code> = NOT<br>"
            "&bull; Isotopes are written mass-first, correctly cased: "
            "<code>60Ni</code>, <code>208Pb</code><br><br>"
            "<b>Exact vs. Partial match</b><br>"
            "Partial: the formula must hold true using only the isotopes "
            "it references; other isotopes on the particle are ignored.<br>"
            "Exact: same, plus the particle may contain nothing outside "
            "the formula's own isotopes.<br><br>"
            "<b>Groups</b><br>"
            "Give two definitions the same group name to pool their "
            "matches into one shared, colored bucket downstream.")

    # ------------------------------------------------------------------ #
    # Read-back contract (called by ParticleClassifierNode.configure)
    # ------------------------------------------------------------------ #
    def get_definitions(self):
        """Return the edited definitions list (internal bookkeeping keys
        like ``_applied_from`` stripped).

        Returns:
            list: Definition dicts.
        """
        out = []
        for d in self._definitions:
            clean = {k: v for k, v in d.items() if not k.startswith('_')}
            out.append(clean)
        return out

    def get_groups(self):
        return dict(self._groups)

    def get_overlap_mode(self):
        return self._overlap_mode

    def get_unmatched_mode(self):
        return self._unmatched_mode

    def get_unclassified_color(self):
        return self._unclassified_color

    def get_selected_sources(self):
        checked = self._checked_names()
        if len(checked) == len(self._sources):
            return None
        return checked

    def get_has_unresolved_issues(self):
        return self._has_unresolved_issues
