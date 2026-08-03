from enum import IntEnum
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QCheckBox, QGroupBox, QMessageBox,
    QHeaderView, QSplitter, QFileDialog, QListWidget,
    QListWidgetItem, QWidget, QRadioButton, QButtonGroup,
    QStyledItemDelegate,
)
from PySide6.QtCore import Qt, Signal, QLocale
from PySide6.QtGui import QDesktopServices, QDoubleValidator, QColor, QBrush
import logging

from tools.mass_fraction_utils import (
    CSVCompoundDatabase,
    parse_formula_to_counts,
    reduced_counts_from_formula,
    FormulaComboBox,
)
from tools.mass_fraction_utils.compound import Compound
from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo
from tools.theme import theme

_itk_log = logging.getLogger("IsotopeTrack.tools.mass_fraction_calculator")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sample list item
# ---------------------------------------------------------------------------

class CheckableListItem(QWidget):
    """Compact widget with checkbox + label for sample list."""

    def __init__(self, sample_name: str, parent=None):
        super().__init__(parent)
        self.sample_name = sample_name

        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.label = QLabel(sample_name)

        lay.addWidget(self.checkbox)
        lay.addWidget(self.label)
        lay.addStretch()

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


# ---------------------------------------------------------------------------
# Validated density delegate (for editable compound-density column)
# ---------------------------------------------------------------------------

class _PositiveDoubleDelegate(QStyledItemDelegate):
    """Only accept positive floats when editing density cells."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        validator = QDoubleValidator(0.0, 1e6, 6, editor)
        validator.setLocale(QLocale.c())
        editor.setValidator(validator)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.ItemDataRole.DisplayRole) or '')

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        try:
            val = float(text)
            if val < 0:
                raise ValueError
        except ValueError:
            _itk_log.exception("Handled exception in setModelData")
            return
        model.setData(index, f"{val:.6f}", Qt.ItemDataRole.EditRole)
        model.setData(
            index,
            QBrush(QColor("yellow")) if val == 0 else QBrush(Qt.BrushStyle.NoBrush),
            Qt.ItemDataRole.BackgroundRole,
        )


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class _MfcCol(IntEnum):
    """Enum containing columns and their positions in the table."""
    ELEMENT = 0
    FORMULA = 1
    MASSFRAC = 2
    MW = 3
    ELEM_DENS = 4
    COMP_DENS = 5
    STRUCTURE_BTN = 6


class MassFractionCalculator(QDialog):
    """Mass fraction calculator with sample selection and molecular weight calculations."""

    mass_fractions_updated = Signal(dict)

    def __init__(self,
                 selected_isotopes: dict,
                 periodic_table_info: PeriodicTableInfo,
                 compound_db: CSVCompoundDatabase,
                 /,
                 parent: QWidget | Any = None):
        super().__init__(parent)
        self.selected_isotopes = selected_isotopes
        self.periodic_table_info = periodic_table_info
        self.parent_window = parent
        self.mass_fractions: dict[str, float] = {}
        self.densities: dict[str, float] = {}
        self.molecular_weights: dict[str, float] = {}

        self.tracked_elements: set[str] = set(selected_isotopes.keys())

        self.available_samples: list[str] = []
        if parent and hasattr(parent, 'sample_to_folder_map'):
            self.available_samples = list(parent.sample_to_folder_map.keys())

        self.compound_db: CSVCompoundDatabase = compound_db

        self.setWindowTitle("Mass Fraction Calculator")
        self.setMinimumSize(1100, 550)
        self.resize(1500, 700)

        self._setup_ui()
        self._populate_table()
        self._restore_previous_state()

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply the currently active theme palette to this dialog."""
        self.setStyleSheet(self._build_stylesheet())
        if hasattr(self, 'db_status_label'):
            self._refresh_db_status_style()
        if hasattr(self, '_apply_btn'):
            self._refresh_apply_button_style()

    def closeEvent(self, event):
        """Disconnect theme signal so we don't leak slots on closed dialogs."""
        try:
            self._save_state()
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            _itk_log.exception("Handled exception in closeEvent")
        super().closeEvent(event)

    def _build_stylesheet(self) -> str:
        """Dark/light aware stylesheet for the whole dialog."""
        p = theme.palette
        return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QWidget {{
            color: {p.text_primary};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QGroupBox {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 8px;
            color: {p.text_primary};
        }}

        /* Sample list — the main source of the white area in dark mode */
        QListWidget {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 2px;
            outline: 0;
        }}
        QListWidget::item {{
            color: {p.text_primary};
            padding: 2px;
            border-radius: 3px;
        }}
        QListWidget::item:hover {{
            background-color: {p.bg_hover};
        }}
        QListWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}

        /* Checkboxes inside the sample list and elsewhere */
        QCheckBox {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 1px solid {p.border};
            background-color: {p.bg_tertiary};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {p.accent};
            background-color: {p.accent};
        }}

        /* Radio buttons for Apply Options */
        QRadioButton {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
            padding: 2px;
        }}
        QRadioButton::indicator {{
            width: 14px;
            height: 14px;
        }}
        QRadioButton::indicator:unchecked {{
            border: 2px solid {p.border};
            border-radius: 8px;
            background-color: {p.bg_tertiary};
        }}
        QRadioButton::indicator:checked {{
            border: 2px solid {p.accent};
            border-radius: 8px;
            background-color: {p.accent};
        }}

        /* Table */
        QTableWidget {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            alternate-background-color: {p.bg_tertiary};
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QTableWidget::item {{
            padding: 4px;
            color: {p.text_primary};
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
        QHeaderView {{
            background-color: {p.bg_tertiary};
            border: none;
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px 8px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}

        /* Inputs */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 18px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}

        /* Buttons (default styling — Apply button overrides below) */
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
            color: {p.text_inverse};
        }}
        QPushButton:disabled {{
            color: {p.text_muted};
            background-color: {p.bg_secondary};
        }}

        /* Splitter handle — otherwise a bright light bar in dark mode */
        QSplitter::handle {{
            background-color: {p.border};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background: {p.bg_primary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.text_muted};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {p.bg_primary};
            height: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        """

    def _refresh_db_status_style(self):
        p = theme.palette
        if self.compound_db.is_loaded:
            color = p.success
        else:
            color = p.warning
        self.db_status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
        )

    def _refresh_apply_button_style(self):
        p = theme.palette
        self._apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {p.accent};
                color: {p.text_inverse};
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.accent_pressed};
            }}
        """)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- left panel: sample selection ----------------------------
        left_panel = self._build_sample_panel()

        # ---- right panel: table + buttons ----------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addLayout(self._build_header())
        self._build_table()
        right_layout.addWidget(self.table)
        right_layout.addLayout(self._build_buttons())

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1200])

        main_layout.addWidget(splitter)

    # -- sub-builders --------------------------------------------------

    def _build_sample_panel(self) -> QGroupBox:
        panel = QGroupBox("Sample Selection")
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)

        btn_row = QHBoxLayout()
        sa = QPushButton("Select All")
        sa.clicked.connect(self._select_all_samples)
        sn = QPushButton("Select None")
        sn.clicked.connect(self._select_no_samples)
        btn_row.addWidget(sa)
        btn_row.addWidget(sn)
        layout.addLayout(btn_row)

        lbl = QLabel(f"Available Samples ({len(self.available_samples)}):")
        lbl.setStyleSheet("font-weight: bold; margin: 5px 0;")
        layout.addWidget(lbl)

        self.sample_list = QListWidget()
        self.sample_list.setMaximumHeight(400)
        for name in self.available_samples:
            item = QListWidgetItem()
            widget = CheckableListItem(name)
            item.setSizeHint(widget.sizeHint())
            self.sample_list.addItem(item)
            self.sample_list.setItemWidget(item, widget)
        layout.addWidget(self.sample_list)

        apply_group = QGroupBox("Apply Options")
        apply_layout = QVBoxLayout(apply_group)

        self._apply_btn_group = QButtonGroup(self)
        self.radio_selected = QRadioButton("Apply to selected samples only")
        self.radio_all = QRadioButton("Apply to all samples (global)")
        self.radio_selected.setChecked(True)
        self._apply_btn_group.addButton(self.radio_selected, 0)
        self._apply_btn_group.addButton(self.radio_all, 1)
        apply_layout.addWidget(self.radio_selected)
        apply_layout.addWidget(self.radio_all)

        layout.addWidget(apply_group)
        layout.addStretch()
        return panel

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()

        title = QLabel("Mass Fraction Calculator")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")
        header.addWidget(title)
        header.addStretch()

        if self.compound_db.is_loaded:
            txt = f"database: {self.compound_db.row_count()}"
        else:
            txt = "database: Not found"

        self.db_status_label = QLabel(txt)
        header.addWidget(self.db_status_label)

        if not self.compound_db.is_loaded:
            load_btn = QPushButton("Load CSV")
            load_btn.clicked.connect(self._manual_load_csv)
            header.addWidget(load_btn)

        return header

    def _build_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Element',
            'Compound Formula',
            'Mass Fraction',
            'Molecular Weight\n(g/mol)',
            'Element Density\n(g/cm³)',
            'Compound Density\n(g/cm³)',
            'Structure',
        ])

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(_MfcCol.ELEMENT, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(_MfcCol.FORMULA, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_MfcCol.MASSFRAC, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(_MfcCol.MW, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(_MfcCol.ELEM_DENS, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(_MfcCol.COMP_DENS, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(_MfcCol.STRUCTURE_BTN, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(_MfcCol.ELEMENT, 80)
        self.table.setColumnWidth(_MfcCol.MASSFRAC, 120)
        self.table.setColumnWidth(_MfcCol.MW, 140)
        self.table.setColumnWidth(_MfcCol.ELEM_DENS, 140)
        self.table.setColumnWidth(_MfcCol.COMP_DENS, 160)
        self.table.setColumnWidth(_MfcCol.STRUCTURE_BTN, 110)

        self.table.setItemDelegateForColumn(
            _MfcCol.COMP_DENS, _PositiveDoubleDelegate(self.table)
        )

    def _build_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Pure Elements")
        reset_btn.clicked.connect(self._reset_to_default)
        layout.addWidget(reset_btn)

        calc_btn = QPushButton("Calculate All Mass Fractions")
        calc_btn.clicked.connect(self._calculate_all)
        layout.addWidget(calc_btn)

        layout.addStretch()

        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self._apply_mass_fractions)
        self._apply_btn = apply_btn
        layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        return layout

    def _populate_table(self):
        sorted_elems = []
        for element in self.selected_isotopes:
            ed = self.periodic_table_info.get_element_by_symbol(element)
            if ed:
                sorted_elems.append((ed['atomic_number'], element, ed))
        sorted_elems.sort()
        self.table.setRowCount(len(sorted_elems))

        for row, (_, element, ed) in enumerate(sorted_elems):
            el_item = QTableWidgetItem(element)
            el_item.setFlags(el_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            el_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, _MfcCol.ELEMENT, el_item)

            # TODO: give the selected_elements around here
            combo = FormulaComboBox(self.compound_db,
                                    default_formula=element,
                                    parent=self)
            combo.compound_changed.connect(lambda compound, r=row: self._on_compound_selected(r, compound))
            self.table.setCellWidget(row, _MfcCol.FORMULA, combo)

            mf = self._make_readonly_item("1.000000")
            self.table.setItem(row, _MfcCol.MASSFRAC, mf)

            mass = float(ed.get('mass', 0))
            self.table.setItem(row, _MfcCol.MW, self._make_readonly_item(f"{mass:.6f}"))

            edens = float(ed.get('density', 0) or 0)
            self.table.setItem(row, _MfcCol.ELEM_DENS, self._make_readonly_item(f"{edens:.6f}"))

            cd_item = QTableWidgetItem()
            self._set_compound_density_item(cd_item, edens)
            self.table.setItem(row, _MfcCol.COMP_DENS, cd_item)

            self._update_compound_btn(row, Compound(formula=element))

    @staticmethod
    def _make_readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _set_compound_density_item(item: QTableWidgetItem, density: float) -> None:
        """Display zero compound densities as a warning without overriding normal cells."""
        item.setText(f"{density:.6f}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(
            QBrush(QColor("yellow")) if density == 0 else QBrush(Qt.BrushStyle.NoBrush)
        )

    def _current_formula(self, row: int) -> str:
        combo = self.table.cellWidget(row, _MfcCol.FORMULA)
        if isinstance(combo, FormulaComboBox):
            return combo.text()  # TODO: empiric testing
        else:
            return ''

    def _calc_mass_fraction(self, row: int, formula: str):
        el_item = self.table.item(row, _MfcCol.ELEMENT)
        if not el_item:
            return
        element = el_item.text()

        counts = reduced_counts_from_formula(formula)
        if not counts:
            mf = 1.0
        else:
            total = target = 0.0
            unknown_element = False
            for el, n in counts.items():
                m = self.periodic_table_info.get_mass_by_element(el)
                if m:
                    m = m * n
                    total += m
                    if el == element:
                        target += m
                else:
                    unknown_element = True
            if unknown_element:
                logger.warning("Formula '%s' contains element(s) not in periodic table data", formula)
            mf = (target / total) if total > 0 and target > 0 else 1.0

        self.table.setItem(row, _MfcCol.MASSFRAC, self._make_readonly_item(f"{mf:.6f}"))

    def _calc_molecular_weight(self, row: int, formula: str):
        counts = reduced_counts_from_formula(formula)
        mw = 0.0
        valid = bool(counts)
        for el, n in counts.items():
            m = self.periodic_table_info.get_mass_by_element(el)
            if m:
                mw += m * n
            else:
                valid = False
                break

        if not valid or mw <= 0:
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            if el_item:
                m = self.periodic_table_info.get_mass_by_element(el_item.text())
                mw = m if m else 0.0
            else:
                mw = 0.0

        self.table.setItem(row, _MfcCol.MW, self._make_readonly_item(f"{mw:.6f}"))

    def _on_compound_selected(self, row: int, compound: Optional[Compound]):
        # TODO: Check if we can change farther down stream the formula thingy
        if compound is None:
            return
        formula = compound.formula
        self._calc_mass_fraction(row, formula)
        self._calc_molecular_weight(row, formula)
        self._update_compound_btn(row, compound)

        counts = reduced_counts_from_formula(formula)
        if len(counts) <= 1:
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            density = self.periodic_table_info.get_density_by_element(el_item.text()) if el_item else None
            d = density if density else 0.0
        else:
            d = float(compound.density or 0.0)

        cd_item = self.table.item(row, _MfcCol.COMP_DENS) or QTableWidgetItem()
        self._set_compound_density_item(cd_item, d)
        self.table.setItem(row, _MfcCol.COMP_DENS, cd_item)

        self._highlight_tracked(row, formula)

    def _highlight_tracked(self, row: int, formula: str):
        """Set a tooltip showing which elements in the compound are being tracked.
        Args:
            row (int): Row index.
            formula (str): The formula.
        """
        counts = parse_formula_to_counts(formula)
        tracked_in = sorted(set(counts.keys()) & self.tracked_elements)
        other = sorted(set(counts.keys()) - self.tracked_elements)

        combo = self.table.cellWidget(row, _MfcCol.FORMULA)
        if combo and len(counts) >= 2:
            parts = []
            if tracked_in:
                parts.append(f"Tracked: {', '.join(tracked_in)}")
            if other:
                parts.append(f"Not tracked: {', '.join(other)}")
            combo.setToolTip('\n'.join(parts))

    def _calculate_all(self):
        for row in range(self.table.rowCount()):
            f = self._current_formula(row)
            if f:
                self._calc_mass_fraction(row, f)
                self._calc_molecular_weight(row, f)

    def _reset_to_default(self):
        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            combo = self.table.cellWidget(row, _MfcCol.FORMULA)
            if not el_item or not isinstance(combo, FormulaComboBox):
                continue
            element = el_item.text()
            ed = self.periodic_table_info.get_element_by_symbol(element)

            combo.set_formula(element)
            combo.reset_formula()

            self.table.setItem(row, _MfcCol.MASSFRAC, self._make_readonly_item("1.000000"))
            mass = float(ed['mass']) if ed else 0.0
            self.table.setItem(row, _MfcCol.MW, self._make_readonly_item(f"{mass:.6f}"))
            d = float(ed.get('density', 0) or 0) if ed else 0.0
            cd = QTableWidgetItem()
            self._set_compound_density_item(cd, d)
            self.table.setItem(row, _MfcCol.COMP_DENS, cd)

    def _select_all_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if isinstance(w, CheckableListItem):
                w.set_checked(True)

    def _select_no_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if isinstance(w, CheckableListItem):
                w.set_checked(False)

    def _get_selected_samples(self) -> list[str]:
        out = []
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if isinstance(w, CheckableListItem) and w.is_checked():
                out.append(w.sample_name)
        return out

    def _save_state(self):
        if not self.parent_window:
            return
        state: dict = {
            'mass_fractions': {},
            'densities': {},
            'molecular_weights': {},
            'formulas': {},
            'selected_samples': self._get_selected_samples(),
            'apply_to_all': self.radio_all.isChecked(),
        }
        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            combo = self.table.cellWidget(row, _MfcCol.FORMULA)
            if combo:
                state['formulas'][element] = combo.current_formula()

            for col, key in [
                (_MfcCol.MASSFRAC, 'mass_fractions'),
                (_MfcCol.MW, 'molecular_weights'),
                (_MfcCol.COMP_DENS, 'densities'),
            ]:
                cell = self.table.item(row, col)
                if cell:
                    try:
                        state[key][element] = float(cell.text())
                    except ValueError:
                        _itk_log.exception("Handled exception in _save_state")

        self.parent_window._mass_fraction_calculator_state = state

    def _restore_previous_state(self):
        if not self.parent_window:
            return
        state = getattr(self.parent_window, '_mass_fraction_calculator_state', None)
        if not state:
            return

        self.radio_all.setChecked(state.get('apply_to_all', False))
        self.radio_selected.setChecked(not state.get('apply_to_all', False))

        selected = set(state.get('selected_samples', []))
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(w.sample_name in selected)

        formulas = state.get('formulas', {})
        saved_densities = state.get('densities', {})

        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            if not el_item:
                continue
            element = el_item.text()
            if element in formulas:
                combo = self.table.cellWidget(row, _MfcCol.FORMULA)
                if isinstance(combo, FormulaComboBox):
                    saved = formulas[element]
                    combo.set_formula(saved)

            if element in saved_densities:
                custom_density = saved_densities[element]
                cd_item = QTableWidgetItem()
                self._set_compound_density_item(cd_item, custom_density)
                self.table.setItem(row, _MfcCol.COMP_DENS, cd_item)

    def _manual_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv, *.csv.gz)")
        if path and self.compound_db.load_csv(path):
            self.db_status_label.setText(f"database: {self.compound_db.row_count()}")
            self._refresh_db_status_style()
            QMessageBox.information(self, "Success", "Database loaded!")

    def _apply_mass_fractions(self):
        selected = self._get_selected_samples()
        apply_all = self.radio_all.isChecked()

        if not apply_all and not selected:
            QMessageBox.warning(
                self, "No Samples Selected",
                "Please select at least one sample or choose 'Apply to all samples'.",
            )
            return

        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, _MfcCol.ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            mf_cell = self.table.item(row, _MfcCol.MASSFRAC)
            mw_cell = self.table.item(row, _MfcCol.MW)
            cd_cell = self.table.item(row, _MfcCol.COMP_DENS)

            try:
                self.mass_fractions[element] = float(mf_cell.text()) if mf_cell else 1.0
            except ValueError:
                _itk_log.exception("Handled exception in _apply_mass_fractions")
                self.mass_fractions[element] = 1.0

            if mw_cell:
                try:
                    self.molecular_weights[element] = float(mw_cell.text())
                except ValueError:
                    _itk_log.exception("Handled exception in _apply_mass_fractions")

            if cd_cell:
                try:
                    val = float(cd_cell.text())
                    if val > 0:
                        self.densities[element] = val
                except ValueError:
                    _itk_log.exception("Handled exception in _apply_mass_fractions")

        self._save_state()

        self.mass_fractions_updated.emit({
            'mass_fractions': self.mass_fractions,
            'densities': self.densities,
            'molecular_weights': self.molecular_weights,
            'apply_to_all': apply_all,
            'selected_samples': selected if not apply_all else [],
        })
        self.accept()

    def reject(self):
        self._save_state()
        super().reject()

    def _update_compound_btn(self, row: int, compound: Compound):
        btn_widget = self.table.cellWidget(row, _MfcCol.STRUCTURE_BTN)
        if not isinstance(btn_widget, QPushButton):
            if isinstance(btn_widget, QWidget):
                btn_widget.hide()
                btn_widget.deleteLater()

            btn_widget = QPushButton("Open")
            self.table.setCellWidget(row, _MfcCol.STRUCTURE_BTN, btn_widget)

        btn_widget.clicked.disconnect()

        if compound.mp_url:
            btn_widget.clicked.connect(lambda: QDesktopServices.openUrl(compound.mp_url))
            btn_widget.setToolTip(f"Opens default browser at: {compound.mp_url}")
            btn_widget.setDisabled(False)
        else:
            btn_widget.setDisabled(True)
            btn_widget.setToolTip("No online material found")
