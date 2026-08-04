"""Model and calculation state for the mass-fraction table."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

from tools.mass_fraction_utils import reduced_counts_from_formula
from tools.mass_fraction_utils.compound import Compound
from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo

logger = logging.getLogger(__name__)


class MassFractionColumn(IntEnum):
    ELEMENT = 0
    FORMULA = 1
    MASS_FRACTION = 2
    MOLECULAR_WEIGHT = 3
    ELEMENT_DENSITY = 4
    COMPOUND_DENSITY = 5
    STRUCTURE = 6


HEADERS = (
    "Element", "Compound Formula", "Mass Fraction", "Molecular Weight\n(g/mol)",
    "Element Density\n(g/cm³)", "Compound Density\n(g/cm³)", "Structure",
)


@dataclass
class MassFractionRow:
    element: str
    formula: str
    mass_fraction: float
    molecular_weight: float
    element_density: float
    compound_density: float
    compound: Compound


class MassFractionTableModel(QAbstractTableModel):
    """Owns editable mass-fraction data, validation, and derived values."""

    def __init__(self, selected_isotopes: dict, periodic_table_info: PeriodicTableInfo, parent=None):
        super().__init__(parent)
        self.periodic_table_info = periodic_table_info
        self._rows = self._initial_rows(selected_isotopes)

    def _initial_rows(self, selected_isotopes: dict) -> list[MassFractionRow]:
        elements = []
        for element in selected_isotopes:
            info = self.periodic_table_info.get_element_by_symbol(element)
            if info:
                elements.append((info["atomic_number"], element, info))
        rows = []
        for _, element, info in sorted(elements):
            density = float(info.get("density", 0) or 0)
            rows.append(MassFractionRow(
                element, element, 1.0, float(info.get("mass", 0)), density,
                density, Compound(formula=element, density=density),
            ))
        return rows

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(MassFractionColumn)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, column = self._rows[index.row()], MassFractionColumn(index.column())
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            values = {
                MassFractionColumn.ELEMENT: row.element,
                MassFractionColumn.FORMULA: row.formula,
                MassFractionColumn.MASS_FRACTION: f"{row.mass_fraction:.6f}",
                MassFractionColumn.MOLECULAR_WEIGHT: f"{row.molecular_weight:.6f}",
                MassFractionColumn.ELEMENT_DENSITY: f"{row.element_density:.6f}",
                MassFractionColumn.COMPOUND_DENSITY: f"{row.compound_density:.6f}",
                MassFractionColumn.STRUCTURE: "Open",
            }
            return values[column]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.BackgroundRole and column == MassFractionColumn.COMPOUND_DENSITY and row.compound_density == 0:
            return QBrush(QColor("yellow"))
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == MassFractionColumn.FORMULA:
                return self._formula_tooltip(row.formula)
            if column == MassFractionColumn.STRUCTURE and not row.compound.mp_url:
                return "No online material found"
        if role == Qt.ItemDataRole.UserRole:
            return row.compound
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() in (MassFractionColumn.FORMULA, MassFractionColumn.COMPOUND_DENSITY):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if index.column() != MassFractionColumn.COMPOUND_DENSITY:
            return False
        try:
            density = float(str(value).strip())
        except (TypeError, ValueError):
            return False
        if density < 0:
            return False
        self._rows[index.row()].compound_density = density
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])
        return True

    def set_compound(self, row_number: int, compound: Compound) -> None:
        if not 0 <= row_number < len(self._rows):
            return
        row = self._rows[row_number]
        row.formula = compound.formula
        row.compound = compound
        row.mass_fraction = self._mass_fraction(row.element, row.formula)
        row.molecular_weight = self._molecular_weight(row.element, row.formula)
        counts = reduced_counts_from_formula(row.formula)
        row.compound_density = (
            float(self.periodic_table_info.get_density_by_element(row.element) or 0)
            if len(counts) <= 1 else float(compound.density or 0)
        )
        self._emit_row_changed(row_number)

    def reset_to_pure_elements(self) -> None:
        for row in self._rows:
            info = self.periodic_table_info.get_element_by_symbol(row.element) or {}
            row.formula = row.element
            row.mass_fraction = 1.0
            row.molecular_weight = float(info.get("mass", 0))
            row.compound_density = float(info.get("density", 0) or 0)
            row.compound = Compound(formula=row.element, density=row.compound_density)
        self._emit_all_changed()

    def recalculate_all(self) -> None:
        for row in self._rows:
            row.mass_fraction = self._mass_fraction(row.element, row.formula)
            row.molecular_weight = self._molecular_weight(row.element, row.formula)
        self._emit_all_changed()

    def export_values(self) -> dict:
        return {
            "mass_fractions": {row.element: row.mass_fraction for row in self._rows},
            "densities": {row.element: row.compound_density for row in self._rows if row.compound_density > 0},
            "molecular_weights": {row.element: row.molecular_weight for row in self._rows},
        }

    def save_state(self) -> dict:
        values = self.export_values()
        values["formulas"] = {row.element: row.formula for row in self._rows}
        values["densities"] = {row.element: row.compound_density for row in self._rows}
        return values

    def restore_state(self, state: dict) -> None:
        formulas, densities = state.get("formulas", {}), state.get("densities", {})
        for row in self._rows:
            if row.element in formulas:
                formula = formulas[row.element]
                row.formula = formula
                row.compound = Compound(formula=formula, density=0)
                row.mass_fraction = self._mass_fraction(row.element, formula)
                row.molecular_weight = self._molecular_weight(row.element, formula)
            if row.element in densities:
                row.compound_density = float(densities[row.element])
        self._emit_all_changed()

    def _mass_fraction(self, target_element: str, formula: str) -> float:
        counts = reduced_counts_from_formula(formula)
        if not counts:
            return 1.0
        total = target = 0.0
        for element, count in counts.items():
            mass = self.periodic_table_info.get_mass_by_element(element)
            if mass:
                total += mass * count
                if element == target_element:
                    target += mass * count
            else:
                logger.warning("Formula '%s' contains an unknown element", formula)
        return target / total if total > 0 and target > 0 else 1.0

    def _molecular_weight(self, fallback_element: str, formula: str) -> float:
        counts = reduced_counts_from_formula(formula)
        weight = 0.0
        for element, count in counts.items():
            mass = self.periodic_table_info.get_mass_by_element(element)
            if not mass:
                return float(self.periodic_table_info.get_mass_by_element(fallback_element) or 0)
            weight += mass * count
        return weight if weight > 0 else float(self.periodic_table_info.get_mass_by_element(fallback_element) or 0)

    def _formula_tooltip(self, formula: str) -> str:
        tracked = set(row.element for row in self._rows)
        counts = reduced_counts_from_formula(formula)
        if len(counts) < 2:
            return ""
        tracked_in = sorted(set(counts) & tracked)
        other = sorted(set(counts) - tracked)
        return "\n".join(filter(None, (
            f"Tracked: {', '.join(tracked_in)}" if tracked_in else "",
            f"Not tracked: {', '.join(other)}" if other else "",
        )))

    def _emit_row_changed(self, row: int) -> None:
        self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))

    def _emit_all_changed(self) -> None:
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, self.columnCount() - 1))
