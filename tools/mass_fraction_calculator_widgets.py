"""Focused UI widgets used by the mass-fraction calculator dialog."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QLocale, QPoint, Qt, Signal
from PySide6.QtGui import QDesktopServices, QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QStyledItemDelegate, QStyleOptionViewItem, QTableView,
    QVBoxLayout, QWidget,
)

from tools.mass_fraction_table_model import MassFractionColumn, MassFractionTableModel
from tools.mass_fraction_utils import CSVCompoundDatabase, FormulaComboBox
from tools.mass_fraction_utils.compound import Compound


class _CheckableSampleItem(QWidget):
    def __init__(self, sample_name: str, parent=None):
        super().__init__(parent)
        self.sample_name = sample_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        layout.addWidget(self.checkbox)
        layout.addWidget(QLabel(sample_name))
        layout.addStretch()


class SampleSelectionWidget(QGroupBox):
    """Selects which samples receive values when the dialog is applied."""

    def __init__(self, sample_names: list[str], parent=None):
        super().__init__("Sample Selection", parent)
        self.setFixedWidth(280)
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_none = QPushButton("Select None")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        select_none.clicked.connect(lambda: self._set_all_checked(False))
        buttons.addWidget(select_all)
        buttons.addWidget(select_none)
        layout.addLayout(buttons)
        label = QLabel(f"Available Samples ({len(sample_names)}):")
        label.setStyleSheet("font-weight: bold; margin: 5px 0;")
        layout.addWidget(label)

        self.sample_list = QListWidget()
        self.sample_list.setMaximumHeight(400)
        for name in sample_names:
            item = QListWidgetItem(self.sample_list)
            widget = _CheckableSampleItem(name)
            item.setSizeHint(widget.sizeHint())
            self.sample_list.setItemWidget(item, widget)
        layout.addWidget(self.sample_list)

        apply_group = QGroupBox("Apply Options")
        apply_layout = QVBoxLayout(apply_group)
        self.selected_radio = QRadioButton("Apply to selected samples only")
        self.all_radio = QRadioButton("Apply to all samples (global)")
        self.selected_radio.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.selected_radio)
        group.addButton(self.all_radio)
        apply_layout.addWidget(self.selected_radio)
        apply_layout.addWidget(self.all_radio)
        layout.addWidget(apply_group)
        layout.addStretch()

    def _setup_ui(self):
        pass
    def selected_samples(self) -> list[str]:
        result = []
        for row in range(self.sample_list.count()):
            widget = self.sample_list.itemWidget(self.sample_list.item(row))
            if isinstance(widget, _CheckableSampleItem) and widget.checkbox.isChecked():
                result.append(widget.sample_name)
        return result

    def apply_to_all(self) -> bool:
        return self.all_radio.isChecked()

    def restore_state(self, state: dict) -> None:
        self.all_radio.setChecked(state.get("apply_to_all", False))
        self.selected_radio.setChecked(not state.get("apply_to_all", False))
        selected = set(state.get("selected_samples", []))
        for row in range(self.sample_list.count()):
            widget = self.sample_list.itemWidget(self.sample_list.item(row))
            if isinstance(widget, _CheckableSampleItem):
                widget.checkbox.setChecked(widget.sample_name in selected)

    def _set_all_checked(self, checked: bool) -> None:
        for row in range(self.sample_list.count()):
            widget = self.sample_list.itemWidget(self.sample_list.item(row))
            if isinstance(widget, _CheckableSampleItem):
                widget.checkbox.setChecked(checked)


class _FormulaDelegate(QStyledItemDelegate):
    def __init__(self, compound_db: CSVCompoundDatabase, parent=None):
        super().__init__(parent)
        self.compound_db = compound_db

    def createEditor(self, parent, option, index):
        editor = FormulaComboBox(self.compound_db, default_formula=index.data() or "", parent=parent)
        editor.compound_changed.connect(lambda compound, row=index.row(): self._set_compound(row, compound))
        return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, FormulaComboBox):
            editor.blockSignals(True)
            editor.set_formula(index.data(Qt.ItemDataRole.EditRole) or "")
            editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        # FormulaComboBox updates the calculator model as the user types.
        return

    def _set_compound(self, row: int, compound: Compound) -> None:
        parent = self.parent()
        if isinstance(parent, QTableView) and isinstance(parent.model(), MassFractionTableModel):
            parent.model().set_compound(row, compound)


class _DensityDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        validator = QDoubleValidator(0.0, 1e6, 6, editor)
        validator.setLocale(QLocale.c())
        editor.setValidator(validator)
        return editor

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text().strip(), Qt.ItemDataRole.EditRole)


class _StructureDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index):
        button = QPushButton("Open")
        button.setEnabled(bool(index.data(Qt.ItemDataRole.UserRole).mp_url))
        button.resize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        button.render(painter, QPoint())
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == event.Type.MouseButtonRelease and option.rect.contains(event.position().toPoint()):
            compound: Optional[Compound] = index.data(Qt.ItemDataRole.UserRole)
            if compound and compound.mp_url:
                QDesktopServices.openUrl(compound.mp_url)
                return True
        return False


class MassFractionTableWidget(QTableView):
    """View layer for a :class:`MassFractionTableModel`."""

    def __init__(self, model: MassFractionTableModel, compound_db: CSVCompoundDatabase, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setItemDelegateForColumn(MassFractionColumn.FORMULA, _FormulaDelegate(compound_db, self))
        self.setItemDelegateForColumn(MassFractionColumn.COMPOUND_DENSITY, _DensityDelegate(self))
        self.setItemDelegateForColumn(MassFractionColumn.STRUCTURE, _StructureDelegate(self))
        header = self.horizontalHeader()
        header.setSectionResizeMode(MassFractionColumn.ELEMENT, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(MassFractionColumn.FORMULA, QHeaderView.ResizeMode.Stretch)
        for column in (
                MassFractionColumn.MASS_FRACTION, MassFractionColumn.MOLECULAR_WEIGHT,
                MassFractionColumn.ELEMENT_DENSITY, MassFractionColumn.COMPOUND_DENSITY,
                MassFractionColumn.STRUCTURE,
        ):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        for column, width in ((MassFractionColumn.ELEMENT, 80), (MassFractionColumn.MASS_FRACTION, 120),
                              (MassFractionColumn.MOLECULAR_WEIGHT, 140), (MassFractionColumn.ELEMENT_DENSITY, 140),
                              (MassFractionColumn.COMPOUND_DENSITY, 160), (MassFractionColumn.STRUCTURE, 110)):
            self.setColumnWidth(column, width)
        # Formula fields were always visible in the former QTableWidget UI.
        for row in range(model.rowCount()):
            self.openPersistentEditor(model.index(row, MassFractionColumn.FORMULA))


class CalculationActionsWidget(QWidget):
    reset_requested = Signal()
    calculate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        reset = QPushButton("Reset to Pure Elements")
        calculate = QPushButton("Calculate All Mass Fractions")
        reset.clicked.connect(self.reset_requested)
        calculate.clicked.connect(self.calculate_requested)
        layout.addWidget(reset)
        layout.addWidget(calculate)
        layout.addStretch()


class DialogActionsWidget(QWidget):
    apply_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.apply_button = QPushButton("Apply Changes")
        cancel = QPushButton("Cancel")
        self.apply_button.clicked.connect(self.apply_requested)
        cancel.clicked.connect(self.cancel_requested)
        layout.addWidget(self.apply_button)
        layout.addWidget(cancel)
