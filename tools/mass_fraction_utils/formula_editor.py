from typing import Any, Optional

from PySide6.QtCore import Signal, QTimer, QModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget, QCompleter

from tools.mass_fraction_utils import CSVCompoundDatabase, canonicalize_preserve_user_order, reduce_counts, \
    parse_formula_to_counts
from tools.mass_fraction_utils.compound import Compound
from tools.mass_fraction_utils.compound_database import CompoundDatabaseModel


# ---------------------------------------------------------------------------
# FormulaComboBox – editable combo with live filtering
# ---------------------------------------------------------------------------

class DirectQCompleter(QCompleter):
    """Enables a `QCompleter` to show all model results regardless of the input"""

    def splitPath(self, _, /):
        return [""]


class FormulaComboBox(QLineEdit):
    compound_changed = Signal(Compound)

    def __init__(self,
                 compound_db: CSVCompoundDatabase,
                 default_formula: str = "",
                 parent: QWidget | Any = None):
        super().__init__(parent=parent)
        self.default_formula = default_formula
        self._formula = default_formula
        self.setText(default_formula)
        self.compound_db = compound_db
        self.compound_model = self.compound_db.get_searchable_model(self.default_formula)
        self._setup_completion()

        self.textChanged.connect(self.set_formula)

    def _setup_completion(self):
        formula_completion = DirectQCompleter()
        formula_completion.setParent(self)

        self.compound_model.setParent(formula_completion)
        formula_completion.setModel(self.compound_model) # Check if parent would be completer or self.
        self.textChanged.connect(self.compound_model.search)
        # TODO: Check if a UnfilteredPopupCompletion is better.
        formula_completion.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        formula_completion.activated[QModelIndex].connect(self._formula_selected)

        self.setCompleter(formula_completion)

    def _formula_selected(self, index: QModelIndex):
        compound = self.compound_model.data(index, role=CompoundDatabaseModel.DataColumn.COMPOUND)
        self.blockSignals(True)
        self.formula = compound.formula
        self.blockSignals(False)
        self.compound_changed.emit(compound)

    def set_formula(self, formula:str):
        self.formula = formula

    def current_formula(self) -> str:
        return self.formula

    def reset_formula(self):
        self.formula = self.default_formula

    @property
    def formula(self) -> str:
        return self._formula

    @formula.setter
    def formula(self, value: str):
        self._formula = value
        if value != self.text():
            self.setText(value)
        # Get the best compound based on the formula
        compound = self.compound_db.get_first_compound_by_formula(self.formula)
        if compound is None:
            self.compound_changed.emit(Compound(formula=self.formula, density=0))
        else:
            self.compound_changed.emit(compound)
