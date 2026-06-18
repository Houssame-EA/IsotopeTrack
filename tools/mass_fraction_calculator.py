from enum import Enum

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

from tools.mass_fraction_calculator_utils.formula_utils import parse_formula_to_counts, reduce_counts
from tools.mass_fraction_calculator_utils.formula_combo_box import FormulaComboBox
from tools.mass_fraction_calculator_utils.compound_database import CSVCompoundDatabase
from tools.np_shape import NanoParticleShapeWidget
from tools.theme import theme

_itk_log = logging.getLogger("IsotopeTrack.tools.mass_fraction_calculator")

logger2 = logging.getLogger(__name__)



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
        editor.setValidator(QDoubleValidator(0.0, 1e6, 6, editor))
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

    class CalculatorColumn(Enum):
        """`CalculatorColumn` stores display information about the table"""
        ELEMENT = 0, 'Element', QHeaderView.ResizeMode.Fixed, 80
        FORMULA = 1, 'Compound Formula', QHeaderView.ResizeMode.Stretch, None
        MASSFRAC = 2, 'Mass Fraction', QHeaderView.ResizeMode.Fixed, 120
        MW = 3, 'Molecular Weight\n(g/mol)', QHeaderView.ResizeMode.Fixed, 140
        ELEM_DENS = 4, 'Element Density\n(g/cm³)', QHeaderView.ResizeMode.Fixed, 140
        COMP_DENS = 5, 'Compound Density\n(g/cm³)', QHeaderView.ResizeMode.Fixed, 160
        STRUCTURE = 6, 'Structure', QHeaderView.ResizeMode.Fixed, 110

        def __init__(self, col_index: int,
                     title: str,
                     resize_mode: QHeaderView.ResizeMode,
                     width: int | None = None):
            """
             Args:
                col_index (int): Column index in the table
                title (str): Title that will be displayed for the column
                resize_mode (QHeaderView.ResizeMode): `QHeaderView.ResizeMode` of the column
                width (int | None): Width of the column (if `resize_mode` allows it)
            """
            self.col_index = col_index
            self.title = title

            self.resize_mode = resize_mode
            self.width = width

        @classmethod
        def col_indexes(cls) -> list[int]:
            """
            Returns:
                a list of column indexes
            """
            return [column.col_index for column in cls]

        @classmethod
        def titles(cls) -> list[str]:
            """
            Returns:
                a list of all titles
            """
            return [column.title for column in cls]

    def __init__(self, selected_isotopes: dict, periodic_table_widget, parent=None):
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
        QTableWidget, QTableView {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            alternate-background-color: {p.bg_tertiary};
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QTableWidget::item, QTableView::item {{
            padding: 4px;
            color: {p.text_primary};
        }}
        QTableWidget::item:selected, QTableView::item:selected {{
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
        splitter = QSplitter(Qt.Orientation.Horizontal, parent=self)

        # ---- left panel: sample selection ----------------------------
        left_panel = self._build_sample_panel()

        # ---- right panel: MFC + NP Shape + button panel ----------------------------
        # Mass Fraction Calculator
        mfc_widget = self._build_mass_fraction_calculator_widget()
        # NP Shape
        nps_widget = NanoParticleShapeWidget(self)
        button_panel = self._build_dialog_control_buttons()

        mfc_nps_splitter = QSplitter(Qt.Orientation.Vertical)
        mfc_nps_splitter.addWidget(mfc_widget)
        mfc_nps_splitter.addWidget(nps_widget)
        mfc_nps_splitter.setStretchFactor(0, 1)
        mfc_nps_splitter.setStretchFactor(1, 1)

        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        right_layout.addWidget(mfc_nps_splitter)
        right_layout.addWidget(button_panel)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1200])

        main_layout.addWidget(splitter)

    def _build_mass_fraction_calculator_widget(self) -> QWidget:
        mfc_panel = QWidget()
        mfc_layout = QVBoxLayout(mfc_panel)

        mfc_layout.addLayout(self._build_header())
        self.table = self._build_table()
        mfc_layout.addWidget(self.table)
        return mfc_panel

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
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        header.addWidget(title)
        self._add_mfc_controls_to_layout(header)
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
        table = QTableWidget()
        table.setColumnCount(len(self.CalculatorColumn))
        table.setHorizontalHeaderLabels(self.CalculatorColumn.titles())

        hdr = table.horizontalHeader()
        # Build one by one the columns' headers based on `self.CalculatorColumn` enum.
        for column in self.CalculatorColumn:
            hdr.setSectionResizeMode(column.col_index, column.resize_mode)
            if (column.resize_mode == QHeaderView.ResizeMode.Fixed
                    and column.width):
                table.setColumnWidth(column.col_index, column.width)

        table.setItemDelegateForColumn(
            self.CalculatorColumn.COMP_DENS.col_index, _PositiveDoubleDelegate(table)
        )
        return table

    def _build_dialog_control_buttons(self) -> QWidget:
        layout = QHBoxLayout()
        layout.addStretch()

        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self._apply_mass_fractions)
        self._apply_btn = apply_btn
        layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        btn_panel = QWidget()
        btn_panel.setLayout(layout)
        return btn_panel

    def _add_mfc_controls_to_layout(self, layout: QHBoxLayout):
        reset_btn = QPushButton("Reset to Pure Elements")
        reset_btn.clicked.connect(self._reset_to_default)
        layout.addWidget(reset_btn)

        calc_btn = QPushButton("Calculate All Mass Fractions")
        calc_btn.clicked.connect(self._calculate_all)
        layout.addWidget(calc_btn)

    def _populate_table(self):
        sorted_elems = []
        for element in self.selected_isotopes:
            ed = self._element_data(element)
            if ed:
                sorted_elems.append((ed['atomic_number'], element, ed))
        sorted_elems.sort()
        self.table.setRowCount(len(sorted_elems))

        for row, (_, element, ed) in enumerate(sorted_elems):
            # Adds the element symbole
            el_item = QTableWidgetItem(element)
            el_item.setFlags(el_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            el_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.CalculatorColumn.ELEMENT.col_index, el_item)

            # Adds Compound Formula
            combo = FormulaComboBox(
                element, self.csv_database,
                tracked_elements=self.tracked_elements,
                parent=self,
            )
            combo.formula_selected.connect(lambda f, d, r=row: self._on_compound_selected(r, f, d))
            self.table.setCellWidget(row, self.CalculatorColumn.FORMULA.col_index, combo)

            # Adds Mass Fraction
            mf = self._make_readonly_item("1.000000")
            self.table.setItem(row, self.CalculatorColumn.MASSFRAC.col_index, mf)

            # Adds Molecular Weight
            mass = float(ed.get('mass', 0))
            self.table.setItem(row, self.CalculatorColumn.MW.col_index, self._make_readonly_item(f"{mass:.6f}"))

            # Adds Density
            edens = float(ed.get('density', 0) or 0)
            self.table.setItem(row, self.CalculatorColumn.ELEM_DENS.col_index, self._make_readonly_item(f"{edens:.6f}"))

            # Compound Density
            cd_item = QTableWidgetItem(f"{edens:.6f}")
            cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.CalculatorColumn.COMP_DENS.col_index, cd_item)

            # Adds link from the compound to materialsproject
            btn = QPushButton("Open")
            btn.setToolTip("Open structure page on Materials Project")
            btn.clicked.connect(lambda _, r=row: self._open_structure(r))
            self.table.setCellWidget(row, self.CalculatorColumn.STRUCTURE.col_index, btn)

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
        combo = self.table.cellWidget(row, self.CalculatorColumn.FORMULA.col_index)
        return combo.current_formula() if combo else ''

    def _calc_mass_fraction(self, row: int, formula: str):
        # Get the string formula
        el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
        if not el_item:
            return
        element = el_item.text()

        # Get the elements count with reduced values
        counts = reduce_counts(parse_formula_to_counts(formula))
        # Defines the mass fraction (mf) for the element
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
                logger2.warning("Formula '%s' contains element(s) not in periodic table data", formula)
            mf = (target / total) if total > 0 and target > 0 else 1.0

        # Displays the result
        self.table.setItem(row, self.CalculatorColumn.MASSFRAC.col_index, self._make_readonly_item(f"{mf:.6f}"))

    def _calc_molecular_weight(self, row: int, formula: str):
        # Get the elements count with reduced values
        counts = reduce_counts(parse_formula_to_counts(formula))
        # Calculate molecular weight (MW) while checking if the molecule is
        # valid (all elements exists in `_element_data`).
        mw = 0.0
        valid = bool(counts)
        for el, n in counts.items():
            ed = self._element_data(el)
            if ed:
                mw += float(ed['mass']) * n
            else:
                valid = False
                break

        # Invalid molecules or invalid molecular mass will set the molecular
        # mass to the row's element mass or 0 (if the element is not found in
        # the row or the element data)
        if not valid or mw <= 0:
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            if el_item:
                ed = self._element_data(el_item.text())
                mw = float(ed['mass']) if ed else 0.0
            else:
                mw = 0.0

        # Display the final molecular weight
        self.table.setItem(row, self.CalculatorColumn.MW.col_index, self._make_readonly_item(f"{mw:.6f}"))

    def _on_compound_selected(self, row: int, formula: str, density_csv: float):
        # Update mass fraction and molecular weight
        self._calc_mass_fraction(row, formula)
        self._calc_molecular_weight(row, formula)

        # reduce counts
        counts = reduce_counts(parse_formula_to_counts(formula))
        # If the counts are only tracking the element
        if len(counts) <= 1:
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            ed = self._element_data(el_item.text()) if el_item else None
            d = float(ed.get('density', 0) or 0) if ed else 0.0
        else:
            d = float(density_csv or 0.0)

        cd_item = QTableWidgetItem(f"{d:.6f}")
        cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.CalculatorColumn.COMP_DENS.col_index, cd_item)

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

        combo = self.table.cellWidget(row, self.CalculatorColumn.FORMULA.col_index)
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
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            combo = self.table.cellWidget(row, self.CalculatorColumn.FORMULA.col_index)
            if not el_item or not combo:
                continue
            element = el_item.text()
            ed = self._element_data(element)

            combo._set_editor_text(element)
            combo.reset_items()
            combo.formula_selected.emit(element, 0.0)

            self.table.setItem(row, self.CalculatorColumn.MASSFRAC.col_index, self._make_readonly_item("1.000000"))
            mass = float(ed['mass']) if ed else 0.0
            self.table.setItem(row, self.CalculatorColumn.MW.col_index, self._make_readonly_item(f"{mass:.6f}"))
            d = float(ed.get('density', 0) or 0) if ed else 0.0
            cd = QTableWidgetItem(f"{d:.6f}")
            cd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, self.CalculatorColumn.COMP_DENS.col_index, cd)

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
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            if not el_item:
                continue
            element = el_item.text()

            combo = self.table.cellWidget(row, self.CalculatorColumn.FORMULA.col_index)
            if combo:
                state['formulas'][element] = combo.current_formula()

            for col, key in [
                (self.CalculatorColumn.MASSFRAC.col_index, 'mass_fractions'),
                (self.CalculatorColumn.MW.col_index, 'molecular_weights'),
                (self.CalculatorColumn.COMP_DENS.col_index, 'densities'),
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
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            if not el_item:
                continue
            element = el_item.text()
            if element in formulas:
                combo = self.table.cellWidget(row, self.CalculatorColumn.FORMULA.col_index)
                if combo:
                    saved = formulas[element]
                    combo._set_editor_text(saved)
                    dens = self.csv_database.best_density_for_formula(saved)
                    self._on_compound_selected(row, saved, dens)

            if element in saved_densities:
                custom_density = saved_densities[element]
                cd_item = QTableWidgetItem(f"{custom_density:.6f}")
                cd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, self.CalculatorColumn.COMP_DENS.col_index, cd_item)

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
            el_item = self.table.item(row, self.CalculatorColumn.ELEMENT.col_index)
            if not el_item:
                continue
            element = el_item.text()

            mf_cell = self.table.item(row, self.CalculatorColumn.MASSFRAC.col_index)
            mw_cell = self.table.item(row, self.CalculatorColumn.MW.col_index)
            cd_cell = self.table.item(row, self.CalculatorColumn.COMP_DENS.col_index)

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
