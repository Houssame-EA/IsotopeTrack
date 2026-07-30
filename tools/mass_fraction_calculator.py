from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QCheckBox, QGroupBox, QMessageBox,
    QHeaderView, QSplitter, QFileDialog, QListWidget,
    QListWidgetItem, QWidget, QRadioButton, QButtonGroup,
    QStyledItemDelegate,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QDoubleValidator
from PySide6.QtCore import QUrl
import logging

from tools.mass_fraction_utils import (
    CSVCompoundDatabase,
    parse_formula_to_counts,
    reduce_counts,
    FormulaComboBox,
)
from tools.mass_fraction_utils.compound import Compound
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


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class MassFractionCalculator(QDialog):
    """Mass fraction calculator with sample selection and molecular weight calculations."""

    mass_fractions_updated = Signal(dict)

    COL_ELEMENT = 0
    COL_FORMULA = 1
    COL_MASSFRAC = 2
    COL_MW = 3
    COL_ELEM_DENS = 4
    COL_COMP_DENS = 5
    COL_STRUCTURE = 6

    def __init__(self,
                 selected_isotopes: dict,
                 periodic_table_widget,
                 parent: QWidget | Any=None):
        super().__init__(parent)
        self.selected_isotopes = selected_isotopes
        self.periodic_table_widget = periodic_table_widget
        self.parent_window = parent
        self.mass_fractions: dict[str, float] = {}
        self.densities: dict[str, float] = {}
        self.molecular_weights: dict[str, float] = {}

        self.tracked_elements: set[str] = set(selected_isotopes.keys())

        self.available_samples: list[str] = []
        if parent and hasattr(parent, 'sample_to_folder_map'):
            self.available_samples = list(parent.sample_to_folder_map.keys())

        self.csv_database: CSVCompoundDatabase = getattr(parent, '_cached_csv_database', None)
        if self.csv_database is None:
            self.csv_database = CSVCompoundDatabase()
            self.csv_database.auto_load_csv()
            if parent is not None:
                try:
                    parent._cached_csv_database = self.csv_database
                except AttributeError:
                    _itk_log.exception("Handled exception in __init__")

        self.periodic_table_data = (
            periodic_table_widget.get_elements() if periodic_table_widget else []
        )

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
        if self.csv_database.is_loaded:
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

        if self.csv_database.is_loaded:
            n = len(self.csv_database.signature_to_formula)
            txt = f"database: {n}"
        else:
            txt = "database: Not found"

        self.db_status_label = QLabel(txt)
        header.addWidget(self.db_status_label)

        if not self.csv_database.is_loaded:
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
        hdr.setSectionResizeMode(self.COL_ELEMENT, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_FORMULA, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_MASSFRAC, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_MW, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_ELEM_DENS, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_COMP_DENS, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_STRUCTURE, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(self.COL_ELEMENT, 80)
        self.table.setColumnWidth(self.COL_MASSFRAC, 120)
        self.table.setColumnWidth(self.COL_MW, 140)
        self.table.setColumnWidth(self.COL_ELEM_DENS, 140)
        self.table.setColumnWidth(self.COL_COMP_DENS, 160)
        self.table.setColumnWidth(self.COL_STRUCTURE, 110)

        self.table.setItemDelegateForColumn(
            self.COL_COMP_DENS, _PositiveDoubleDelegate(self.table)
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
            ed = self._element_data(element)
            if ed:
                sorted_elems.append((ed['atomic_number'], element, ed))
        sorted_elems.sort()
        self.table.setRowCount(len(sorted_elems))

        for row, (_, element, ed) in enumerate(sorted_elems):
            el_item = QTableWidgetItem(element)
            el_item.setFlags(el_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            el_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.COL_ELEMENT, el_item)

            # TODO: give the selected_elements around here
            combo = FormulaComboBox(self.csv_database.get_searchable_model(),
                                    default_formula=element,
                                    parent=self, )
            combo.compound_selected.connect(lambda f, d, r=row: self._on_compound_selected(r, f, d))
            self.table.setCellWidget(row, self.COL_FORMULA, combo)

            mf = self._make_readonly_item("1.000000")
            self.table.setItem(row, self.COL_MASSFRAC, mf)

            mass = float(ed.get('mass', 0))
            self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mass:.6f}"))

            edens = float(ed.get('density', 0) or 0)
            self.table.setItem(row, self.COL_ELEM_DENS, self._make_readonly_item(f"{edens:.6f}"))

            cd_item = QTableWidgetItem(f"{edens:.6f}")
            cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.COL_COMP_DENS, cd_item)

            btn = QPushButton("Open")
            btn.setToolTip("Open structure page on Materials Project")
            btn.clicked.connect(lambda _, r=row: self._open_structure(r))
            self.table.setCellWidget(row, self.COL_STRUCTURE, btn)

    @staticmethod
    def _make_readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _element_data(self, symbol: str) -> dict | None:
        for e in self.periodic_table_data:
            if e['symbol'] == symbol:
                return e
        return None

    def _current_formula(self, row: int) -> str:
        combo = self.table.cellWidget(row, self.COL_FORMULA)
        return combo.current_formula() if combo else ''

    def _calc_mass_fraction(self, row: int, formula: str):
        el_item = self.table.item(row, self.COL_ELEMENT)
        if not el_item:
            return
        element = el_item.text()

        counts = reduce_counts(parse_formula_to_counts(formula))
        if not counts:
            mf = 1.0
        else:
            total = target = 0.0
            unknown_element = False
            for el, n in counts.items():
                ed = self._element_data(el)
                if ed:
                    m = float(ed['mass']) * n
                    total += m
                    if el == element:
                        target += m
                else:
                    unknown_element = True
            if unknown_element:
                logger.warning("Formula '%s' contains element(s) not in periodic table data", formula)
            mf = (target / total) if total > 0 and target > 0 else 1.0

        self.table.setItem(row, self.COL_MASSFRAC, self._make_readonly_item(f"{mf:.6f}"))

    def _calc_molecular_weight(self, row: int, formula: str):
        counts = reduce_counts(parse_formula_to_counts(formula))
        mw = 0.0
        valid = bool(counts)
        for el, n in counts.items():
            ed = self._element_data(el)
            if ed:
                mw += float(ed['mass']) * n
            else:
                valid = False
                break

        if not valid or mw <= 0:
            el_item = self.table.item(row, self.COL_ELEMENT)
            if el_item:
                ed = self._element_data(el_item.text())
                mw = float(ed['mass']) if ed else 0.0
            else:
                mw = 0.0

        self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mw:.6f}"))

    def _on_compound_selected(self, row: int, formula: str, density_csv: float):
        self._calc_mass_fraction(row, formula)
        self._calc_molecular_weight(row, formula)

        counts = reduce_counts(parse_formula_to_counts(formula))
        if len(counts) <= 1:
            el_item = self.table.item(row, self.COL_ELEMENT)
            ed = self._element_data(el_item.text()) if el_item else None
            d = float(ed.get('density', 0) or 0) if ed else 0.0
        else:
            d = float(density_csv or 0.0)

        cd_item = QTableWidgetItem(f"{d:.6f}")
        cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_COMP_DENS, cd_item)

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

        combo = self.table.cellWidget(row, self.COL_FORMULA)
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
            el_item = self.table.item(row, self.COL_ELEMENT)
            combo = self.table.cellWidget(row, self.COL_FORMULA)
            if not el_item or not combo:
                continue
            element = el_item.text()
            ed = self._element_data(element)

            combo._set_editor_text(element)
            combo.reset_items()
            combo.formula_selected.emit(element, 0.0)

            self.table.setItem(row, self.COL_MASSFRAC, self._make_readonly_item("1.000000"))
            mass = float(ed['mass']) if ed else 0.0
            self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mass:.6f}"))
            d = float(ed.get('density', 0) or 0) if ed else 0.0
            cd = QTableWidgetItem(f"{d:.6f}")
            cd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.COL_COMP_DENS, cd)

    def _select_all_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(True)

    def _select_no_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(False)

    def _get_selected_samples(self) -> list[str]:
        out = []
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w and w.is_checked():
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
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            combo = self.table.cellWidget(row, self.COL_FORMULA)
            if combo:
                state['formulas'][element] = combo.current_formula()

            for col, key in [
                (self.COL_MASSFRAC, 'mass_fractions'),
                (self.COL_MW, 'molecular_weights'),
                (self.COL_COMP_DENS, 'densities'),
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
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()
            if element in formulas:
                combo = self.table.cellWidget(row, self.COL_FORMULA)
                if combo:
                    saved = formulas[element]
                    combo._set_editor_text(saved)
                    dens = self.csv_database.best_density_for_formula(saved)
                    self._on_compound_selected(row, saved, dens)

            if element in saved_densities:
                custom_density = saved_densities[element]
                cd_item = QTableWidgetItem(f"{custom_density:.6f}")
                cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, self.COL_COMP_DENS, cd_item)

    def _manual_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if path and self.csv_database.load_csv(path):
            self._setup_ui()
            self._populate_table()
            QMessageBox.information(self, "Success", "Database loaded!")

    def _open_structure(self, row: int):
        formula = self._current_formula(row)
        if not formula:
            QMessageBox.warning(self, "No compound", "Please choose a compound first.")
            return
        url = self.csv_database.best_url_for_formula(formula)
        QDesktopServices.openUrl(QUrl(url))

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
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            mf_cell = self.table.item(row, self.COL_MASSFRAC)
            mw_cell = self.table.item(row, self.COL_MW)
            cd_cell = self.table.item(row, self.COL_COMP_DENS)

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

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

    def reject(self):
        self._save_state()
        super().reject()
