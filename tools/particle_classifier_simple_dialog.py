# -*- coding: utf-8 -*-
"""Simple Particle Classifier dialog, in the shared application look.

Everything the classic editor does, laid out to read like a sentence:

- **Sample** (left, top): which sample is shown, whether it is included in
  the output, whether every sample uses the same groups, and copying one
  sample's groups to others.
- **Groups** (left): the groups in priority order, with live particle
  counts, buttons to add and reorder them, and the unclassified count.
- **Group editor** (right): name and colour, then the rule as rows,
  "Must have + 60Ni + 107Ag", "Must not have − 56Fe", "Other isotopes
  allowed / not allowed", with a plain-words reading of it and the live
  count. A group can have several rules ("+ Or another rule"); a particle
  matching any of them joins the group. Any rule can be edited as text
  with the full expression language.
- **Advanced** (bottom): what happens to a particle that matches several
  groups, and to particles that match none.

On OK it shows the same overlap warning as the classic editor. It reads
and writes exactly the same data as
:class:`tools.particle_classifier_dialog.ParticleClassifierDialog` (same
constructor arguments and ``get_*`` read-back methods), so the node, saved
projects and the relabelling pass are unchanged, and the classic editor
stays one click away.
"""

from __future__ import annotations

import copy as _copy
from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPushButton, QRadioButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from tools.theme import theme as _app_theme, app_qss
from tools.particle_filter import normalize_sources, source_labels
from tools.particle_classifier_node import DEFAULT_UNCLASSIFIED_COLOR
from tools.particle_classifier_dialog import _ColorBtn, _next_palette_color
from tools.particle_classifier_rules import (
    isotope_sort_key, new_group, new_rule, expression_to_recipe,
    rule_expression, group_signature, groups_from_definitions,
    definitions_from_groups, sample_summary, rule_notes, remove_isotopes,
    has_unresolved_issues, overlapping_pairs, confound_key_from_record,
    confound_record, parse_simple, to_simple, combinations, combination_groups,
)
from tools.particle_classifier_expr import ExpressionSyntaxError

import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_simple_dialog")

SIMPLE_HELP_HTML = (
    "<b>Groups</b><br>"
    "Each group is a kind of particle, for example <i>Smelter</i> or "
    "<i>Road dust</i>. Downstream charts show the group instead of its "
    "isotopes.<br><br>"
    "<b>Rules</b><br>"
    "Add the isotopes a particle <b>must have</b> (+), those of which it needs "
    "<b>at least one</b> (~), those of which it has <b>exactly one</b> (\u2460), "
    "and the ones it <b>must not have</b> (−), and "
    "choose whether other isotopes are allowed. "
    "Click an isotope to remove it. <i>+ Or another rule</i> adds an "
    "alternative: a particle matching any rule joins the group. The count "
    "updates as you edit.<br><br>"
    "<b>Samples</b><br>"
    "With <i>Same groups for all samples</i> ticked, the groups apply to "
    "every connected sample. Untick it to set up each sample separately, and "
    "use <i>Copy groups to</i> to reuse a sample's groups. <i>Include in "
    "output</i> decides which samples leave this node.<br><br>"
    "<b>Order</b><br>"
    "The order of the groups matters only when a particle that matches "
    "several groups is counted in the first one (Advanced).<br><br>"
    "<b>Text</b><br>"
    "<i>Edit as text</i> uses the same signs as the rows: "
    "<tt>+Ni +Ag -Fe</tt> (has Ni and Ag, not Fe), "
    "<tt>+Ti (+Fe or +Al)</tt> (Ti with Fe or Al), "
    "<tt>oneof(+Ag, +Cu)</tt> (exactly one of them), "
    "<tt>-(+Ni +Ag)</tt> (not both). An element name stands for the isotope "
    "measured in your data; write the mass when there are several, "
    "e.g. <tt>+56Fe</tt>. The classic syntax "
    "(<tt>60Ni+[107Ag, 197Au]+!(56Fe)</tt>) still works."
)

_UNMATCHED_MODES = ('unclassified', 'discard', 'passthrough')
_MINUS = '−'


class SimpleClassifierDialog(QDialog):
    """Group-first configurator for the Particle Classifier node.

    Args:
        parent: Parent widget.
        upstreams (list | dict): Upstream data dict(s) feeding the node.
        definitions (list | None): The node's definitions.
        groups (dict | None): The node's ``{group_name: color}`` registry.
        overlap_mode (str): ``'double_count'`` or ``'priority'``.
        unmatched_mode (str): ``'unclassified'``, ``'discard'`` or
            ``'passthrough'``.
        unclassified_color (str | None): Colour of the Unclassified bucket.
        selected_sources (list | None): Samples included in the output
            (None means all).
        group_pooling_policies (dict | None): ``{group_name: 'keep' |
            'drop_mfc'}`` for groups with several rules.
        confound_dismissals (list | None): Overlap warnings the user chose
            never to see again.
    """

    _COUNT_DEBOUNCE_MS = 200
    _LABEL_WIDTH = 110

    def __init__(self, parent, upstreams, definitions=None, groups=None,
                 overlap_mode='double_count', unmatched_mode='unclassified',
                 unclassified_color=None, selected_sources=None,
                 group_pooling_policies=None, confound_dismissals=None):
        super().__init__(parent)
        self.setWindowTitle("Particle Classifier")
        self.setModal(True)
        self.resize(1300, 720)
        self.setMinimumSize(1120, 580)
        self.setStyleSheet(self._style())
        _app_theme.themeChanged.connect(self._restyle)

        if isinstance(upstreams, dict):
            upstreams = [upstreams]
        self._upstreams = [u for u in (upstreams or []) if u]
        self._sources = normalize_sources(self._upstreams)
        self._names = [s['name'] for s in self._sources]
        self._src_by_name = {s['name']: s for s in self._sources}

        self._overlap_mode = overlap_mode or 'double_count'
        self._unmatched_mode = unmatched_mode or 'unclassified'
        self._unclassified_color = unclassified_color or DEFAULT_UNCLASSIFIED_COLOR
        self._set_included(selected_sources)
        self._pooling = dict(group_pooling_policies or {})
        self._pooling_prompted = set()
        self._dismissed = {confound_key_from_record(r) for r in (confound_dismissals or [])}

        self._sample = self._names[0] if self._names else None
        self._row = None
        self._rule_idx = 0
        self._loading = False
        self._counts = {}
        self._unmatched = 0
        self._total = 0
        self._out_definitions = None
        self._out_groups = None
        self._issues = False

        self._combo_cache = {}
        self._count_timer = QTimer(self)
        self._count_timer.setSingleShot(True)
        self._count_timer.setInterval(self._COUNT_DEBOUNCE_MS)
        self._count_timer.timeout.connect(self._recompute_counts)

        self._load_state(definitions, groups)
        self._build()
        self._refresh_all(select_row=0)

    def _style(self):
        """Shared application sheet plus the cards, rows and isotope chips."""
        p = _app_theme.palette
        return app_qss(p) + f"""
        QFrame#fbCard, QFrame#fbToolbar {{
            background: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 8px;
        }}
        QFrame#fbPreview {{
            background: {p.bg_tertiary};
            border: 1px solid {p.border};
            border-radius: 8px;
        }}
        QGroupBox {{ background: transparent; }}
        QWidget#plainPanel {{ background: transparent; }}
        QLabel#cardTitle {{ font-weight: 700; }}
        QLabel#rowLabel {{ color: {p.text_secondary}; font-weight: 600; }}
        QLabel#readsAs {{ color: {p.text_secondary}; }}
        QLabel#countBig {{ font-size: 22px; font-weight: 700; }}
        QLabel#exprSmall {{
            color: {p.text_muted};
            font-family: "Menlo", "Consolas", monospace;
            font-size: 12px;
        }}
        QPushButton#chipHave, QPushButton#chipNot {{
            border: 1px solid transparent;
            border-radius: 11px;
            padding: 3px 10px;
            font-family: "Menlo", "Consolas", monospace;
            font-weight: 700;
        }}
        QPushButton#chipHave {{ background: {p.accent_soft}; color: {p.accent_pressed}; }}
        QPushButton#chipNot {{ background: rgba(231, 76, 60, 0.14); color: {p.danger}; }}
        QPushButton#chipAny {{
            border: 1px solid transparent;
            border-radius: 11px;
            padding: 3px 10px;
            font-family: "Menlo", "Consolas", monospace;
            font-weight: 700;
            background: rgba(243, 156, 18, 0.20);
            color: {p.text_primary};
        }}
        QPushButton#chipOne {{
            border: 1px solid transparent;
            border-radius: 11px;
            padding: 3px 10px;
            font-family: "Menlo", "Consolas", monospace;
            font-weight: 700;
            background: rgba(142, 68, 173, 0.16);
            color: {p.text_primary};
        }}
        QPushButton#chipOne:hover {{
            border-color: {p.danger};
            text-decoration: line-through;
        }}
        QPushButton#chipAny:hover {{
            border-color: {p.danger};
            text-decoration: line-through;
        }}
        QPushButton#chipHave:hover, QPushButton#chipNot:hover {{
            border-color: {p.danger};
            text-decoration: line-through;
        }}
        QPushButton#addIso {{
            padding: 0;
            min-width: 26px;
            max-width: 26px;
            min-height: 22px;
            max-height: 22px;
            border-radius: 11px;
            font-size: 15px;
            font-weight: 700;
        }}
        QPushButton#addIso::menu-indicator {{ image: none; width: 0; }}
        QPushButton#ruleTab {{ padding: 3px 12px; }}
        QPushButton#ruleTab:checked {{
            background: {p.accent_soft};
            border-color: {p.accent};
            color: {p.accent_pressed};
        }}
        QPushButton#linkBtn {{
            background: transparent;
            border: none;
            color: {p.accent};
            padding: 3px 4px;
        }}
        QPushButton#linkBtn:hover {{ text-decoration: underline; }}
        QPushButton#arrowBtn {{ padding: 4px 8px; }}
        QListWidget {{ font-size: 13px; background: {p.bg_secondary}; border: 1px solid {p.border}; }}
        QListWidget::item {{ padding: 7px 6px; border-radius: 5px; }}
        QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.text_primary}; }}
        """

    def _restyle(self, *_a):
        try:
            self.setStyleSheet(self._style())
        except RuntimeError:
            pass

    def _set_included(self, selected_sources):
        if selected_sources is None:
            self._included = set(self._names)
        else:
            self._included = {n for n in selected_sources if n in self._names}

    def _load_state(self, definitions, groups):
        """Load node definitions into groups and fill missing colours."""
        self._prev_definitions = _copy.deepcopy(definitions or [])
        self._prev_groups = dict(groups or {})
        by_sample, shared = groups_from_definitions(
            self._prev_definitions, self._prev_groups, self._names)
        self._groups_by_sample = by_sample
        self._shared = shared
        self._shared_groups = (_copy.deepcopy(by_sample[self._names[0]])
                               if self._names else [])
        used = {c for c in self._prev_groups.values() if c}
        for groups_list in [self._shared_groups] + list(self._groups_by_sample.values()):
            for group in groups_list:
                if not group.get('color'):
                    group['color'] = _next_palette_color(used)
                    used.add(group['color'])

    def _row_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName('rowLabel')
        lbl.setFixedWidth(self._LABEL_WIDTH)
        return lbl

    @staticmethod
    def _section_label(text):
        lbl = QLabel(text)
        lbl.setObjectName('cardTitle')
        return lbl

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addWidget(self._build_toolbar())
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_left_card())
        body.addWidget(self._build_editor_card(), 1)
        body.addWidget(self._build_combos_card())
        root.addLayout(body, 1)
        root.addWidget(self._build_advanced())

    def _build_toolbar(self):
        bar_frame = QFrame()
        bar_frame.setObjectName('fbToolbar')
        bar = QHBoxLayout(bar_frame)
        bar.setContentsMargins(10, 6, 10, 6)
        bar.setSpacing(8)
        title = QLabel("Particle Classifier")
        title.setObjectName('appTitle')
        bar.addWidget(title)
        bar.addStretch(1)
        btn_classic = QPushButton("Classic editor")
        btn_classic.clicked.connect(self._open_classic)
        bar.addWidget(btn_classic)
        btn_help = QPushButton("Help")
        btn_help.clicked.connect(self._show_help)
        bar.addWidget(btn_help)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bar.addWidget(btn_cancel)
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName('fbPrimary')
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        bar.addWidget(btn_ok)
        return bar_frame

    def _build_left_card(self):
        card = QFrame()
        card.setObjectName('fbCard')
        card.setFixedWidth(280)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        v.addWidget(self._section_label("Sample"))
        self._sample_combo = QComboBox()
        self._sample_combo.addItems(self._names)
        self._sample_combo.setEnabled(bool(self._names))
        self._sample_combo.currentTextChanged.connect(self._on_sample_changed)
        v.addWidget(self._sample_combo)
        v.addSpacing(6)
        self._include_cb = QCheckBox("Include this sample in the output")
        self._include_cb.toggled.connect(self._on_include_toggled)
        v.addWidget(self._include_cb)
        v.addSpacing(8)
        self._shared_cb = QCheckBox("Same groups for all samples")
        self._shared_cb.setChecked(self._shared)
        self._shared_cb.setEnabled(len(self._names) > 1)
        self._shared_cb.toggled.connect(self._on_shared_toggled)
        v.addWidget(self._shared_cb)
        v.addSpacing(6)
        self._btn_copy = QPushButton("Copy groups to…")
        self._copy_menu = QMenu(self._btn_copy)
        self._copy_menu.aboutToShow.connect(self._fill_copy_menu)
        self._btn_copy.setMenu(self._copy_menu)
        v.addWidget(self._btn_copy)
        self._included_lbl = QLabel()
        self._included_lbl.setObjectName('fbHint')
        v.addWidget(self._included_lbl)

        v.addSpacing(6)
        v.addWidget(self._section_label("Groups"))
        self._group_list = QListWidget()
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        v.addWidget(self._group_list, 1)
        row = QHBoxLayout()
        row.setSpacing(6)
        self._btn_new = QPushButton("+ New group")
        self._btn_new.clicked.connect(self._add_group)
        row.addWidget(self._btn_new, 1)
        self._btn_up = QPushButton("▲")
        self._btn_up.setObjectName('arrowBtn')
        self._btn_up.setToolTip("Move up (higher priority)")
        self._btn_up.clicked.connect(lambda: self._move_group(-1))
        row.addWidget(self._btn_up)
        self._btn_down = QPushButton("▼")
        self._btn_down.setObjectName('arrowBtn')
        self._btn_down.setToolTip("Move down (lower priority)")
        self._btn_down.clicked.connect(lambda: self._move_group(1))
        row.addWidget(self._btn_down)
        v.addLayout(row)
        self._order_hint = QLabel(
            "Order matters only when a particle is counted in the first "
            "matching group (Advanced).")
        self._order_hint.setObjectName('fbHint')
        self._order_hint.setWordWrap(True)
        v.addWidget(self._order_hint)
        self._unclassified_lbl = QLabel()
        self._unclassified_lbl.setObjectName('fbHint')
        v.addWidget(self._unclassified_lbl)
        return card

    def _build_editor_card(self):
        card = QFrame()
        card.setObjectName('fbCard')
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self._row_label("Name"))
        self._name_edit = QLineEdit()
        self._name_edit.setMaximumWidth(240)
        self._name_edit.editingFinished.connect(self._on_name_committed)
        top.addWidget(self._name_edit)
        top.addSpacing(8)
        top.addWidget(QLabel("Color"))
        self._color_btn = _ColorBtn('#3B82F6')
        self._color_btn.colorChanged.connect(self._on_color_picked)
        top.addWidget(self._color_btn)
        top.addStretch(1)
        self._btn_delete = QPushButton("Delete group")
        self._btn_delete.clicked.connect(self._delete_group)
        top.addWidget(self._btn_delete)
        v.addLayout(top)

        rules = QHBoxLayout()
        rules.setSpacing(6)
        rules.addWidget(self._row_label("Rule"))
        self._rule_tabs_row = QHBoxLayout()
        self._rule_tabs_row.setSpacing(4)
        rules.addLayout(self._rule_tabs_row)
        self._btn_add_rule = QPushButton("+ Or another rule")
        self._btn_add_rule.setObjectName('linkBtn')
        self._btn_add_rule.setToolTip("A particle that matches any rule joins this group")
        self._btn_add_rule.clicked.connect(self._add_rule)
        rules.addWidget(self._btn_add_rule)
        rules.addStretch(1)
        self._btn_remove_rule = QPushButton("Remove this rule")
        self._btn_remove_rule.clicked.connect(self._remove_rule)
        rules.addWidget(self._btn_remove_rule)
        v.addLayout(rules)

        self._recipe_box = QWidget()
        self._recipe_box.setObjectName('plainPanel')
        rv = QVBoxLayout(self._recipe_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(12)
        have = QHBoxLayout()
        have.setSpacing(8)
        have.addWidget(self._row_label("Must have"))
        self._have_row = QHBoxLayout()
        self._have_row.setSpacing(6)
        have.addLayout(self._have_row, 1)
        rv.addLayout(have)
        any_of = QHBoxLayout()
        any_of.setSpacing(8)
        any_of.addWidget(self._row_label("At least one of"))
        self._any_row = QHBoxLayout()
        self._any_row.setSpacing(6)
        any_of.addLayout(self._any_row, 1)
        rv.addLayout(any_of)
        one_of = QHBoxLayout()
        one_of.setSpacing(8)
        one_of.addWidget(self._row_label("Exactly one of"))
        self._one_row = QHBoxLayout()
        self._one_row.setSpacing(6)
        one_of.addLayout(self._one_row, 1)
        rv.addLayout(one_of)
        not_have = QHBoxLayout()
        not_have.setSpacing(8)
        not_have.addWidget(self._row_label("Must not have"))
        self._not_row = QHBoxLayout()
        self._not_row.setSpacing(6)
        not_have.addLayout(self._not_row, 1)
        rv.addLayout(not_have)
        v.addWidget(self._recipe_box)

        self._text_box = QWidget()
        self._text_box.setObjectName('plainPanel')
        th = QHBoxLayout(self._text_box)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(8)
        th.addWidget(self._row_label("Expression"), 0, Qt.AlignTop)
        tv = QVBoxLayout()
        tv.setSpacing(4)
        self._expr_edit = QLineEdit()
        self._expr_edit.setPlaceholderText("e.g.  +Ni +Ag -Fe     or     +Ti (+Fe or +Al)")
        self._expr_edit.textChanged.connect(self._on_text_changed)
        tv.addWidget(self._expr_edit)
        syntax = QLabel("+ has   ·   - has not   ·   or   ·   oneof(+a, +b) exactly one   ·   ( ) group   ·   Fe = the Fe isotope in your data")
        syntax.setObjectName('fbHint')
        tv.addWidget(syntax)
        th.addLayout(tv, 1)
        v.addWidget(self._text_box)

        other = QHBoxLayout()
        other.setSpacing(14)
        other.addWidget(self._row_label("Other isotopes"))
        self._rb_allowed = QRadioButton("Allowed")
        self._rb_exact = QRadioButton("Not allowed")
        self._exact_group = QButtonGroup(self)
        self._exact_group.addButton(self._rb_allowed, 0)
        self._exact_group.addButton(self._rb_exact, 1)
        self._rb_allowed.setChecked(True)
        self._exact_group.buttonClicked.connect(self._on_exact_changed)
        other.addWidget(self._rb_allowed)
        other.addWidget(self._rb_exact)
        other.addStretch(1)
        v.addLayout(other)

        self._reads_lbl = QLabel()
        self._reads_lbl.setObjectName('readsAs')
        self._reads_lbl.setWordWrap(True)
        v.addWidget(self._reads_lbl)

        self._note_lbl = QLabel()
        self._note_lbl.setObjectName('fbHint')
        self._note_lbl.setWordWrap(True)
        self._note_lbl.hide()
        v.addWidget(self._note_lbl)

        msg_row = QHBoxLayout()
        msg_row.setSpacing(8)
        self._msg_lbl = QLabel()
        self._msg_lbl.setObjectName('fbError')
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.hide()
        msg_row.addWidget(self._msg_lbl, 1)
        self._btn_remove_missing = QPushButton("Remove them")
        self._btn_remove_missing.clicked.connect(self._remove_missing)
        self._btn_remove_missing.hide()
        msg_row.addWidget(self._btn_remove_missing, 0, Qt.AlignTop)
        v.addLayout(msg_row)

        v.addStretch(1)

        result = QFrame()
        result.setObjectName('fbPreview')
        rh = QHBoxLayout(result)
        rh.setContentsMargins(14, 10, 14, 10)
        rh.setSpacing(10)
        self._count_lbl = QLabel("–")
        self._count_lbl.setObjectName('countBig')
        rh.addWidget(self._count_lbl)
        self._pct_lbl = QLabel()
        rh.addWidget(self._pct_lbl)
        rh.addStretch(1)
        self._expr_lbl = QLabel()
        self._expr_lbl.setObjectName('exprSmall')
        self._expr_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rh.addWidget(self._expr_lbl)
        self._btn_mode = QPushButton("Edit as text")
        self._btn_mode.clicked.connect(self._toggle_text_mode)
        rh.addWidget(self._btn_mode)
        v.addWidget(result)

        self._editor_widgets = [
            self._name_edit, self._color_btn, self._btn_delete,
            self._btn_add_rule, self._btn_remove_rule, self._recipe_box,
            self._text_box, self._rb_allowed, self._rb_exact, self._btn_mode]
        return card

    def _build_combos_card(self):
        card = QFrame()
        card.setObjectName('fbCard')
        card.setFixedWidth(300)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)
        v.addWidget(self._section_label("Combinations in this sample"))
        hint = QLabel("Click one to add its isotopes to the selected rule. "
                      "The square shows the group it falls in.")
        hint.setObjectName('fbHint')
        hint.setWordWrap(True)
        v.addWidget(hint)
        self._combo_filter = QLineEdit()
        self._combo_filter.setPlaceholderText("Filter, e.g. Ti or 60Ni")
        self._combo_filter.textChanged.connect(self._refresh_combos)
        v.addWidget(self._combo_filter)
        self._combo_list = QListWidget()
        self._combo_list.itemClicked.connect(self._on_combo_clicked)
        v.addWidget(self._combo_list, 1)
        self._combo_more = QLabel()
        self._combo_more.setObjectName('fbHint')
        self._combo_more.setWordWrap(True)
        v.addWidget(self._combo_more)
        return card

    _MAX_COMBOS = 200

    def _sample_combinations(self):
        if self._sample is None:
            return []
        if self._sample not in self._combo_cache:
            source = self._src_by_name[self._sample]
            self._combo_cache[self._sample] = combinations(source.get('particles') or [])
        return self._combo_cache[self._sample]

    def _refresh_combos(self, *_a):
        """List the selected sample's isotope combinations with their groups."""
        self._combo_list.clear()
        combos = self._sample_combinations()
        terms = [t.lower() for t in self._combo_filter.text().split() if t]
        if terms:
            combos = [(isos, n) for isos, n in combos
                      if all(any(t in iso.lower() for iso in isos) for t in terms)]
        defs = self._current_sample_definitions()
        colors = {(g.get('name') or '').strip(): g.get('color') for g in self._groups()}
        shown = combos[:self._MAX_COMBOS]
        for isos, n in shown:
            names = combination_groups(isos, defs, self._overlap_mode)
            item = QListWidgetItem(f"{' + '.join(isos)}   \u00b7   {n:,}")
            pix = QPixmap(12, 12)
            pix.fill(QColor(colors.get(names[0]) or '#BDBDBD') if names
                     else QColor(_app_theme.palette.border))
            item.setIcon(QIcon(pix))
            item.setToolTip(("In: " + ", ".join(names)) if names else "Not in any group")
            item.setData(Qt.UserRole, list(isos))
            self._combo_list.addItem(item)
        total = len(self._sample_combinations())
        if self._sample is None:
            self._combo_more.setText("")
        elif terms:
            self._combo_more.setText(f"{len(combos):,} of {total:,} combinations match the filter")
        elif total > len(shown):
            self._combo_more.setText(f"Showing the {len(shown):,} most common of {total:,} combinations")
        else:
            self._combo_more.setText(f"{total:,} combinations")

    def _on_combo_clicked(self, item):
        """Add the clicked combination's isotopes to the selected rule's Must have row."""
        isos = item.data(Qt.UserRole) or []
        if self._current_group() is None:
            self._add_group()
        rule = self._current_rule()
        if rule is None:
            return
        if rule.get('text_mode'):
            self._msg_lbl.setText("Switch to Simple view to add a combination to this rule.")
            self._msg_lbl.show()
            return
        for iso in isos:
            self._add_isotope('must', iso)

    def _build_advanced(self):
        wrap = QFrame()
        wrap.setObjectName('fbCard')
        v = QVBoxLayout(wrap)
        v.setContentsMargins(10, 4, 10, 6)
        v.setSpacing(6)
        self._adv_btn = QToolButton()
        self._adv_btn.setText("Advanced  ·  overlapping groups, unmatched particles")
        self._adv_btn.setCheckable(True)
        self._adv_btn.setArrowType(Qt.RightArrow)
        self._adv_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._adv_btn.toggled.connect(self._on_advanced_toggled)
        v.addWidget(self._adv_btn)

        self._adv_body = QWidget()
        self._adv_body.setObjectName('plainPanel')
        h = QHBoxLayout(self._adv_body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        ov_box = QGroupBox("A particle that matches several groups")
        ovv = QVBoxLayout(ov_box)
        ovv.setContentsMargins(12, 14, 12, 12)
        ovv.setSpacing(12)
        self._ov_group = QButtonGroup(self)
        self._rb_double = QRadioButton("Count it in every group it matches")
        self._rb_priority = QRadioButton("Count it only in the first group (list order)")
        self._ov_group.addButton(self._rb_double, 0)
        self._ov_group.addButton(self._rb_priority, 1)
        ovv.addWidget(self._rb_double)
        ovv.addWidget(self._rb_priority)
        self._ov_group.buttonClicked.connect(self._on_overlap_changed)
        h.addWidget(ov_box, 1)

        um_box = QGroupBox("Particles that match no group")
        umv = QVBoxLayout(um_box)
        umv.setContentsMargins(12, 14, 12, 12)
        umv.setSpacing(12)
        self._um_group = QButtonGroup(self)
        self._rb_unclassified = QRadioButton("Put them in an Unclassified group")
        self._rb_discard = QRadioButton("Remove them")
        self._rb_passthrough = QRadioButton("Keep them with their original isotopes")
        for i, rb in enumerate((self._rb_unclassified, self._rb_discard,
                                self._rb_passthrough)):
            self._um_group.addButton(rb, i)
            umv.addWidget(rb)
        self._um_group.buttonClicked.connect(self._on_unmatched_changed)
        h.addWidget(um_box, 1)

        self._adv_body.hide()
        v.addWidget(self._adv_body)
        self._sync_advanced()
        return wrap

    def _sync_advanced(self):
        (self._rb_priority if self._overlap_mode == 'priority'
         else self._rb_double).setChecked(True)
        mode = self._unmatched_mode if self._unmatched_mode in _UNMATCHED_MODES else 'unclassified'
        {'unclassified': self._rb_unclassified,
         'discard': self._rb_discard,
         'passthrough': self._rb_passthrough}[mode].setChecked(True)

    def _groups(self):
        """The group list being edited: the shared one, or the current sample's."""
        if self._shared or self._sample is None:
            return self._shared_groups
        return self._groups_by_sample.setdefault(self._sample, [])

    def _current_group(self):
        groups = self._groups()
        if self._row is None or not (0 <= self._row < len(groups)):
            return None
        return groups[self._row]

    def _current_rule(self):
        group = self._current_group()
        if group is None or not group['rules']:
            return None
        self._rule_idx = max(0, min(self._rule_idx, len(group['rules']) - 1))
        return group['rules'][self._rule_idx]

    def _groups_for_output(self):
        if self._shared:
            return {name: _copy.deepcopy(self._shared_groups) for name in self._names}
        return {name: self._groups_by_sample.get(name, []) for name in self._names}

    def _available_isotopes(self):
        """Isotopes offered in the pickers, in mass order."""
        if self._shared or self._sample is None:
            labels = set()
            for s in self._sources:
                labels |= source_labels(s)
        else:
            labels = source_labels(self._src_by_name[self._sample])
        return sorted(labels, key=isotope_sort_key)

    def _refresh_all(self, select_row=None):
        if select_row is not None:
            groups = self._groups()
            self._row = select_row if 0 <= select_row < len(groups) else (0 if groups else None)
            self._rule_idx = 0
        self._refresh_sample_controls()
        self._refresh_group_list()
        self._load_group()
        self._recompute_counts()

    def _refresh_sample_controls(self):
        has = self._sample is not None
        self._include_cb.blockSignals(True)
        self._include_cb.setChecked(has and self._sample in self._included)
        self._include_cb.blockSignals(False)
        self._include_cb.setEnabled(has)
        self._btn_copy.setVisible(not self._shared and len(self._names) > 1)
        if has:
            self._included_lbl.setText(
                f"{len(self._included)} of {len(self._names)} samples in the output")
        else:
            self._included_lbl.setText("No samples connected yet")

    def _refresh_group_list(self):
        self._group_list.blockSignals(True)
        self._group_list.clear()
        for group in self._groups():
            item = QListWidgetItem(self._group_item_text(group))
            pix = QPixmap(12, 12)
            pix.fill(QColor(group.get('color') or '#BDBDBD'))
            item.setIcon(QIcon(pix))
            self._group_list.addItem(item)
        if self._row is not None:
            self._group_list.setCurrentRow(self._row)
        self._group_list.blockSignals(False)
        n = len(self._groups())
        self._btn_new.setEnabled(bool(self._names))
        self._btn_up.setEnabled(self._row is not None and self._row > 0)
        self._btn_down.setEnabled(self._row is not None and self._row < n - 1)

    def _group_item_text(self, group):
        count = self._counts.get((group.get('name') or '').strip(),
                                 0 if self._sample is not None else None)
        name = group.get('name') or "(unnamed)"
        return f"{name}   ·   {count:,}" if count is not None else name

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _load_group(self):
        """Show the selected group and its selected rule in the editor."""
        group = self._current_group()
        self._loading = True
        enabled = group is not None
        for w in self._editor_widgets:
            w.setEnabled(enabled)
        if group is None:
            self._name_edit.setText("")
            self._clear_layout(self._have_row)
            self._clear_layout(self._any_row)
            self._clear_layout(self._one_row)
            self._clear_layout(self._not_row)
            self._clear_layout(self._rule_tabs_row)
            self._expr_edit.setText("")
            self._text_box.hide()
            self._recipe_box.show()
            self._btn_remove_rule.hide()
            self._loading = False
            self._update_feedback()
            return
        self._name_edit.setText(group.get('name') or '')
        self._color_btn.set_color(group.get('color') or '#3B82F6')
        self._refresh_rule_tabs()
        self._load_rule()
        self._loading = False
        self._update_feedback()

    def _refresh_rule_tabs(self):
        group = self._current_group()
        self._clear_layout(self._rule_tabs_row)
        n = len(group['rules']) if group else 0
        if n > 1:
            for i in range(n):
                tab = QPushButton(str(i + 1))
                tab.setObjectName('ruleTab')
                tab.setCheckable(True)
                tab.setChecked(i == self._rule_idx)
                tab.setToolTip(f"Rule {i + 1}")
                tab.clicked.connect(partial(self._select_rule, i))
                self._rule_tabs_row.addWidget(tab)
        self._btn_remove_rule.setVisible(n > 1)
        self._rule_tabs_row.invalidate()

    def _load_rule(self):
        rule = self._current_rule()
        was_loading = self._loading
        self._loading = True
        if rule is None:
            self._loading = was_loading
            return
        (self._rb_exact if rule.get('exact') else self._rb_allowed).setChecked(True)
        text_mode = bool(rule.get('text_mode'))
        self._recipe_box.setVisible(not text_mode)
        self._text_box.setVisible(text_mode)
        self._btn_mode.setText("Simple view" if text_mode else "Edit as text")
        if text_mode:
            draft = rule.get('_draft')
            self._expr_edit.setText(draft if draft is not None else to_simple(rule.get('text', '')))
        else:
            self._expr_edit.setText('')
        self._refresh_chips()
        self._loading = was_loading

    def _select_rule(self, idx, *_a):
        self._rule_idx = idx
        self._refresh_rule_tabs()
        self._load_rule()
        self._update_feedback()

    def _refresh_chips(self):
        rule = self._current_rule()
        for kind, row, obj in (('must', self._have_row, 'chipHave'),
                               ('any', self._any_row, 'chipAny'),
                               ('one', self._one_row, 'chipOne'),
                               ('must_not', self._not_row, 'chipNot')):
            self._clear_layout(row)
            if rule is None:
                continue
            sign = {'must': '+', 'any': '~', 'one': '\u2460', 'must_not': _MINUS}[kind]
            for iso in rule.get(kind) or []:
                chip = QPushButton(f"{sign} {iso}")
                chip.setObjectName(obj)
                chip.setToolTip(f"Click to remove {iso}")
                chip.setCursor(Qt.PointingHandCursor)
                chip.clicked.connect(partial(self._remove_isotope, kind, iso))
                row.addWidget(chip)
            add = QPushButton("+")
            add.setObjectName('addIso')
            add.setToolTip("Add an isotope")
            menu = QMenu(add)
            used = (set(rule.get('must') or []) | set(rule.get('any') or [])
                    | set(rule.get('one') or []) | set(rule.get('must_not') or []))
            choices = [iso for iso in self._available_isotopes() if iso not in used]
            for iso in choices:
                act = menu.addAction(iso)
                act.triggered.connect(partial(self._add_isotope, kind, iso))
            if not choices:
                none = menu.addAction("No more isotopes in this data")
                none.setEnabled(False)
            add.setMenu(menu)
            row.addWidget(add)
            row.addStretch(1)
            row.invalidate()
            row.parentWidget().updateGeometry()

    def _add_isotope(self, kind, iso, *_a):
        rule = self._current_rule()
        if rule is None:
            return
        rule.setdefault('any', [])
        rule.setdefault('one', [])
        for other in ('must', 'any', 'one', 'must_not'):
            if other != kind and iso in rule[other]:
                rule[other].remove(iso)
        if iso not in rule[kind]:
            rule[kind].append(iso)
        self._rule_changed()

    def _remove_isotope(self, kind, iso, *_a):
        rule = self._current_rule()
        if rule is None or iso not in (rule.get(kind) or []):
            return
        rule[kind].remove(iso)
        self._rule_changed()

    def _rule_changed(self):
        self._refresh_chips()
        self._update_feedback()
        self._count_timer.start()

    @staticmethod
    def _join(items, word):
        if len(items) < 3:
            return f" {word} ".join(items)
        return ", ".join(items[:-1]) + f" {word} " + items[-1]

    @classmethod
    def _rule_phrase(cls, rule):
        """One rule in plain words, or None when it has nothing to say."""
        if rule.get('text_mode'):
            text = to_simple(rule.get('text') or '').strip()
            return f"matches {text}" if text else None
        must, must_not = rule.get('must') or [], rule.get('must_not') or []
        any_of = rule.get('any') or []
        one_of = rule.get('one') or []
        if not must and not must_not and not any_of and not one_of:
            return None
        parts = []
        if must:
            parts.append("has " + cls._join(must, "and"))
        if any_of:
            parts.append(("has " if len(any_of) == 1 else "at least one of ")
                         + cls._join(any_of, "or"))
        if one_of:
            parts.append(("has " if len(one_of) == 1 else "exactly one of ")
                         + cls._join(one_of, "or"))
        if must_not:
            parts.append("without " + cls._join(must_not, "or"))
        parts.append("nothing else" if rule.get('exact') else "other isotopes allowed")
        return ", ".join(parts)

    @classmethod
    def _reads_as(cls, group):
        """The whole group in plain words.

        Args:
            group (dict): A group.

        Returns:
            str: e.g. "Reads as: a particle has 60Ni and 107Ag, without 56Fe,
                other isotopes allowed."
        """
        phrases = [cls._rule_phrase(r) for r in group.get('rules') or []]
        phrases = [p for p in phrases if p]
        if not phrases:
            return "Add the isotopes that define this group with the + buttons."
        if len(phrases) == 1:
            return f"Reads as: a particle {phrases[0]}."
        return "Reads as: a particle " + ";  or ".join(phrases) + "."

    def _update_feedback(self):
        """Show the rule's expression, its plain-words reading and any problem."""
        group = self._current_group()
        rule = self._current_rule()
        self._btn_remove_missing.hide()
        self._note_lbl.hide()
        if group is None or rule is None:
            self._expr_lbl.setText("")
            self._reads_lbl.setText("")
            self._msg_lbl.hide()
            return
        self._expr_lbl.setText(rule_expression(rule))
        self._reads_lbl.setText(self._reads_as(group))
        labels = (source_labels(self._src_by_name[self._sample])
                  if self._sample is not None else None)
        notes = rule_notes(rule, labels)
        problems = []
        error = rule.get('_text_error') if rule.get('text_mode') else None
        error = error or notes['error']
        if error:
            problems.append(error)
        if notes['contradiction']:
            problems.append("This rule can never match a particle: it asks for an "
                            "isotope to be present and absent at the same time.")
        if notes['missing']:
            problems.append(f"Not measured in {self._sample}: "
                            + ", ".join(notes['missing']) + " (ignored there).")
            self._btn_remove_missing.show()
        self._msg_lbl.setText("\n".join(problems))
        self._msg_lbl.setVisible(bool(problems))
        if error:
            self._reads_lbl.setText("")
        if notes['tautology']:
            self._note_lbl.setText("Note: this rule matches any combination of its "
                                   "isotopes, so it does not narrow anything down.")
            self._note_lbl.show()

    def _remove_missing(self):
        rule = self._current_rule()
        if rule is None or self._sample is None:
            return
        notes = rule_notes(rule, source_labels(self._src_by_name[self._sample]))
        if not notes['missing']:
            return
        remove_isotopes(rule, notes['missing'])
        rule['_draft'] = None
        rule['_text_error'] = None
        self._load_rule()
        self._update_feedback()
        self._count_timer.start()

    def _toggle_text_mode(self):
        rule = self._current_rule()
        if rule is None:
            return
        rule['_draft'] = None
        rule['_text_error'] = None
        if not rule.get('text_mode'):
            rule['text'] = rule_expression(rule)
            rule['text_mode'] = True
        else:
            recipe = expression_to_recipe(rule.get('text', ''))
            if recipe is None:
                self._msg_lbl.setText(
                    "This expression uses logic the rows can't show (two "
                    "or-groups, nested brackets, or a minus in front of "
                    "brackets). Keep editing it as text, or split it with "
                    "+ Or another rule.")
                self._msg_lbl.show()
                return
            rule['must'], rule['any'], rule['one'], rule['must_not'] = recipe
            rule['orig'] = tuple(list(x) for x in recipe) + (rule.get('text', ''),)
            rule['text_mode'] = False
        self._load_rule()
        self._update_feedback()
        self._count_timer.start()

    def _on_text_changed(self, text):
        if self._loading:
            return
        rule = self._current_rule()
        if rule is None or not rule.get('text_mode'):
            return
        rule['_draft'] = text
        try:
            rule['text'] = parse_simple(text, self._available_isotopes()) if text.strip() else ''
            rule['_text_error'] = None
        except ExpressionSyntaxError as exc:
            rule['text'] = text
            rule['_text_error'] = str(exc)
        self._update_feedback()
        self._count_timer.start()

    def _on_exact_changed(self, *_a):
        rule = self._current_rule()
        if rule is None or self._loading:
            return
        rule['exact'] = self._rb_exact.isChecked()
        self._update_feedback()
        self._count_timer.start()

    def _on_name_committed(self):
        group = self._current_group()
        if group is None or self._loading:
            return
        new = self._name_edit.text().strip()
        old = group.get('name') or ''
        if new == old:
            return
        taken = {(g.get('name') or '').strip() for g in self._groups() if g is not group}
        if not new or new in taken:
            self._name_edit.setText(old)
            self._msg_lbl.setText("Each group needs its own, non-empty name.")
            self._msg_lbl.show()
            return
        group['name'] = new
        if old in self._pooling and new not in self._pooling:
            self._pooling[new] = self._pooling.pop(old)
        self._refresh_group_list()
        self._update_feedback()
        self._count_timer.start()

    def _on_color_picked(self, color):
        group = self._current_group()
        if group is None:
            return
        name = group.get('name')
        group['color'] = color
        for groups in [self._shared_groups] + list(self._groups_by_sample.values()):
            for g in groups:
                if g.get('name') == name:
                    g['color'] = color
        self._refresh_group_list()

    def _add_group(self):
        groups = self._groups()
        taken = {(g.get('name') or '').strip() for g in groups}
        n = len(groups) + 1
        while f"Group {n}" in taken:
            n += 1
        used = {g.get('color') for g in groups if g.get('color')}
        groups.append(new_group(f"Group {n}", _next_palette_color(used)))
        self._row = len(groups) - 1
        self._rule_idx = 0
        self._refresh_all()
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _delete_group(self):
        groups = self._groups()
        group = self._current_group()
        if group is None:
            return
        groups.remove(group)
        self._row = min(self._row, len(groups) - 1) if groups else None
        self._rule_idx = 0
        self._refresh_all()

    def _move_group(self, delta):
        """Move the selected group up or down the priority order."""
        groups = self._groups()
        if self._row is None:
            return
        new = self._row + delta
        if not (0 <= new < len(groups)):
            return
        groups[self._row], groups[new] = groups[new], groups[self._row]
        self._row = new
        self._refresh_group_list()
        self._count_timer.start()

    def _add_rule(self):
        """Add an alternative rule to the selected group (classic pooling)."""
        group = self._current_group()
        if group is None:
            return
        group['rules'].append(new_rule())
        self._rule_idx = len(group['rules']) - 1
        if len(group['rules']) == 2 and not self._ask_pooling(group):
            group['rules'].pop()
            self._rule_idx = 0
        self._load_group()
        self._count_timer.start()

    def _remove_rule(self):
        group = self._current_group()
        if group is None or len(group['rules']) < 2:
            return
        group['rules'].pop(self._rule_idx)
        self._rule_idx = max(0, self._rule_idx - 1)
        self._load_group()
        self._count_timer.start()

    def _ask_pooling(self, group):
        """Ask once per group how particle-mass statistics are pooled.

        Same question and choices as the classic editor: particles from
        different rules may rest on different Mass Fraction Calculator
        assumptions.

        Returns:
            bool: False when the user chose to go back.
        """
        name = group.get('name') or ''
        key = (None if self._shared else self._sample, name)
        if key in self._pooling_prompted:
            return True
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Group With Several Rules")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(f"<b>{name}</b> will pool particles from more than one rule.")
        dlg.setInformativeText(
            "Particles matching either rule will be pooled and displayed under "
            "one shared label downstream, but they may have different underlying "
            "Mass Fraction Calculator assumptions, so particle-level mass/moles "
            "statistics (e.g. mean particle mass) for this group could mix "
            "incompatible values. Counts, element mass, and element moles are "
            "always safe and unaffected by this choice.")
        btn_keep = dlg.addButton("Keep Full Data Anyway", QMessageBox.ButtonRole.AcceptRole)
        btn_drop = dlg.addButton("Drop Particle-Mass Stats for This Group",
                                 QMessageBox.ButtonRole.DestructiveRole)
        btn_back = dlg.addButton("Go Back", QMessageBox.ButtonRole.RejectRole)
        dlg.setDefaultButton(btn_drop)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is btn_back:
            return False
        self._pooling_prompted.add(key)
        self._pooling[name] = 'keep' if clicked is btn_keep else 'drop_mfc'
        _itk_log.info("Group %r pooling policy -> %s", name, self._pooling[name])
        return True

    def _on_group_selected(self, row):
        if self._loading:
            return
        self._on_name_committed()
        self._row = row if row >= 0 else None
        self._rule_idx = 0
        n = len(self._groups())
        self._btn_up.setEnabled(self._row is not None and self._row > 0)
        self._btn_down.setEnabled(self._row is not None and self._row < n - 1)
        self._load_group()
        self._update_count_labels()

    def _on_sample_changed(self, name):
        if not name or name == self._sample:
            return
        self._on_name_committed()
        self._sample = name
        if not self._shared:
            self._row = 0 if self._groups() else None
            self._rule_idx = 0
        self._refresh_all()

    def _on_include_toggled(self, checked):
        if self._sample is None:
            return
        if checked:
            self._included.add(self._sample)
        else:
            self._included.discard(self._sample)
        self._refresh_sample_controls()

    def _set_shared_checkbox(self, checked):
        self._shared_cb.blockSignals(True)
        self._shared_cb.setChecked(checked)
        self._shared_cb.blockSignals(False)

    def _on_shared_toggled(self, checked):
        """Switch between one set of groups for all samples and per-sample groups.

        Turning sharing on copies the selected sample's groups to every
        sample, after asking when other samples are set up differently.
        """
        self._on_name_committed()
        if checked:
            current = self._groups_by_sample.get(self._sample) or []
            mine = [group_signature(g) for g in current]
            differs = any([group_signature(g) for g in self._groups_by_sample.get(n) or []] != mine
                          for n in self._names)
            if differs:
                answer = QMessageBox.question(
                    self, "Same groups for all samples",
                    f"Other samples are set up differently. Replace their groups "
                    f"with the groups of {self._sample}?")
                if answer != QMessageBox.StandardButton.Yes:
                    self._set_shared_checkbox(False)
                    return
            self._shared_groups = _copy.deepcopy(current)
        else:
            for name in self._names:
                self._groups_by_sample[name] = _copy.deepcopy(self._shared_groups)
        self._shared = checked
        self._refresh_all(select_row=0)

    def _fill_copy_menu(self):
        self._copy_menu.clear()
        others = [n for n in self._names if n != self._sample]
        for name in others:
            act = self._copy_menu.addAction(name)
            act.triggered.connect(partial(self._copy_groups_to, [name]))
        if len(others) > 1:
            self._copy_menu.addSeparator()
            act = self._copy_menu.addAction("All other samples")
            act.triggered.connect(partial(self._copy_groups_to, others))

    def _copy_groups_to(self, targets, *_a):
        """Replace the groups of ``targets`` with copies of this sample's groups."""
        self._on_name_committed()
        current = self._groups_by_sample.get(self._sample) or []
        for name in targets:
            self._groups_by_sample[name] = _copy.deepcopy(current)
        _itk_log.info("Copied %d group(s) from %r to %s", len(current), self._sample, targets)
        self._included_lbl.setText(f"Groups copied to {', '.join(targets)}")

    def _on_overlap_changed(self, *_a):
        self._overlap_mode = 'priority' if self._rb_priority.isChecked() else 'double_count'
        self._count_timer.start()

    def _on_unmatched_changed(self, *_a):
        self._unmatched_mode = _UNMATCHED_MODES[self._um_group.checkedId()]

    def _on_advanced_toggled(self, on):
        self._adv_btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self._adv_body.setVisible(on)

    def _current_sample_definitions(self):
        if self._sample is None:
            return []
        defs, _groups = definitions_from_groups(
            {self._sample: self._groups()}, [self._sample])
        return defs

    def _recompute_counts(self):
        """Count particles per group for the selected sample."""
        if self._sample is None:
            self._counts, self._unmatched, self._total = {}, 0, 0
        else:
            source = self._src_by_name[self._sample]
            self._counts, self._unmatched, self._total = sample_summary(
                source.get('particles') or [], self._current_sample_definitions(),
                self._overlap_mode)
        for i, group in enumerate(self._groups()):
            item = self._group_list.item(i)
            if item is not None:
                item.setText(self._group_item_text(group))
        self._update_count_labels()
        self._refresh_combos()

    def _update_count_labels(self):
        if self._sample is None:
            self._unclassified_lbl.setText("")
        else:
            self._unclassified_lbl.setText(
                f"Unclassified   ·   {self._unmatched:,} of {self._total:,} particles")
        group = self._current_group()
        if group is None or self._sample is None:
            self._count_lbl.setText("–")
            self._pct_lbl.setText("")
            return
        n = self._counts.get((group.get('name') or '').strip(), 0)
        self._count_lbl.setText(f"{n:,}")
        pct = (100.0 * n / self._total) if self._total else 0.0
        self._pct_lbl.setText(f"particles  ·  {pct:.1f}% of this sample")
        self._pct_lbl.setToolTip(self._sample)

    def _build_output(self):
        """Definitions and group colours for the current edits."""
        if not self._names:
            return _copy.deepcopy(self._prev_definitions), dict(self._prev_groups)
        return definitions_from_groups(
            self._groups_for_output(), self._names,
            self._prev_definitions, self._prev_groups)

    def _selected_sources_out(self):
        if not self._names or self._included >= set(self._names):
            return None
        return [n for n in self._names if n in self._included]

    def _open_classic(self):
        """Open the classic editor on the current edits and load its result back."""
        from tools.particle_classifier_dialog import ParticleClassifierDialog
        self._on_name_committed()
        defs, groups = self._build_output()
        dlg = ParticleClassifierDialog(
            self, self._upstreams, defs, groups, self._overlap_mode,
            self._unmatched_mode, self._unclassified_color,
            self._selected_sources_out(), self._pooling,
            [confound_record(k) for k in self._dismissed])
        if dlg.exec() != QDialog.Accepted:
            return
        self._overlap_mode = dlg.get_overlap_mode()
        self._unmatched_mode = dlg.get_unmatched_mode()
        self._unclassified_color = dlg.get_unclassified_color()
        self._set_included(dlg.get_selected_sources())
        self._pooling = dlg.get_group_pooling_policies()
        self._dismissed = {confound_key_from_record(r) for r in dlg.get_confound_dismissals()}
        self._load_state(dlg.get_definitions(), dlg.get_groups())
        self._set_shared_checkbox(self._shared)
        self._sync_advanced()
        self._refresh_all(select_row=0)

    def _show_help(self):
        QMessageBox.information(self, "Particle Classifier Help", SIMPLE_HELP_HTML)

    def _show_overlap_warning(self, pairs):
        """One warning listing every pair of rules that can match the same particle.

        Same choices as the classic editor: go back and edit, or continue;
        a per-pair "don't warn me again"; and the node-wide choice of how a
        particle matching several groups is counted.

        Returns:
            bool: True to continue and save.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Overlapping Rules")
        dlg.setModal(True)
        dlg.resize(540, 460)
        dlg.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(dlg)
        intro = QLabel("These rules can both match the same particle:")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        checkboxes = []
        for d_a, d_b, witness, key in pairs:
            name_a = d_a.get('group_name') or d_a.get('expression_text') or "Rule A"
            name_b = d_b.get('group_name') or d_b.get('expression_text') or "Rule B"
            sample = d_a.get('target_sample') or ""
            row = QLabel(f"<span style='color:#6B7280'>[{sample}]</span> "
                         f"<b>{name_a}</b> ↔ <b>{name_b}</b>  "
                         f"({', '.join(sorted(witness, key=isotope_sort_key))})")
            row.setWordWrap(True)
            iv.addWidget(row)
            cb = QCheckBox("Don't warn me about this pair again")
            iv.addWidget(cb)
            checkboxes.append((key, cb))
        iv.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        grp = QGroupBox("A particle that matches several groups")
        gv = QVBoxLayout(grp)
        bg = QButtonGroup(dlg)
        rb_double = QRadioButton("Count it in every group it matches")
        rb_priority = QRadioButton("Count it only in the first group (list order)")
        bg.addButton(rb_double, 0)
        bg.addButton(rb_priority, 1)
        (rb_priority if self._overlap_mode == 'priority' else rb_double).setChecked(True)
        gv.addWidget(rb_double)
        gv.addWidget(rb_priority)
        layout.addWidget(grp)

        bb = QDialogButtonBox()
        btn_back = bb.addButton("Go Back and Edit", QDialogButtonBox.RejectRole)
        btn_go = bb.addButton("Continue and Save", QDialogButtonBox.AcceptRole)
        btn_go.setObjectName('fbPrimary')
        btn_back.setDefault(True)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)

        proceed = dlg.exec() == QDialog.Accepted
        self._overlap_mode = 'priority' if rb_priority.isChecked() else 'double_count'
        self._sync_advanced()
        if proceed:
            for key, cb in checkboxes:
                if cb.isChecked():
                    self._dismissed.add(key)
        return proceed

    def accept(self):
        """Build the node data, warn about overlapping rules, then close."""
        self._on_name_committed()
        defs, groups = self._build_output()
        pairs = overlapping_pairs(defs, set(self._names), self._dismissed)
        if pairs and not self._show_overlap_warning(pairs):
            self._recompute_counts()
            return
        self._out_definitions = defs
        self._out_groups = groups
        live = {d.get('group_name') for d in defs if d.get('group_name')}
        self._pooling = {k: v for k, v in self._pooling.items() if k in live}
        labels = {s['name']: source_labels(s) for s in self._sources}
        self._issues = has_unresolved_issues(defs, labels)
        _itk_log.info("Simple classifier dialog accepted: %d definition(s), %d group(s)",
                      len(defs), len(groups))
        super().accept()

    def get_definitions(self):
        """Definitions in the node's format (internal keys stripped).

        Returns:
            list: Definition dicts.
        """
        defs = self._out_definitions
        if defs is None:
            defs, _groups = self._build_output()
        return [{k: v for k, v in d.items() if not k.startswith('_')} for d in defs]

    def get_groups(self):
        """``{group_name: color}`` for the saved definitions."""
        if self._out_groups is None:
            return self._build_output()[1]
        return dict(self._out_groups)

    def get_overlap_mode(self):
        return self._overlap_mode

    def get_unmatched_mode(self):
        return self._unmatched_mode

    def get_unclassified_color(self):
        return self._unclassified_color

    def get_selected_sources(self):
        return self._selected_sources_out()

    def get_has_unresolved_issues(self):
        return self._issues

    def get_group_pooling_policies(self):
        return dict(self._pooling)

    def get_confound_dismissals(self):
        return [confound_record(k) for k in self._dismissed]
