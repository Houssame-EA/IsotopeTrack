from typing import Any

from PySide6.QtCore import Signal, QModelIndex
from PySide6.QtWidgets import QLineEdit, QWidget, QCompleter

from tools.theme import theme
from tools.mass_fraction_utils.compound import Compound
from tools.mass_fraction_utils.compound_database import CSVCompoundDatabase, CompoundDatabaseModel
from tools.mass_fraction_utils.formula_utils import signature_from_formula


# ---------------------------------------------------------------------------
# FormulaComboBox – editable combo with live filtering
# ---------------------------------------------------------------------------

class DirectQCompleter(QCompleter):
    """Enables a `QCompleter` to show all model results regardless of the input"""

    def splitPath(self, _, /):
        return [""]


class FormulaEditor(QLineEdit):
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
        self.compound_model: CompoundDatabaseModel = self.compound_db.get_searchable_model(self.default_formula)
        self._setup_completion()

        self.textChanged.connect(self.set_formula)

    def _setup_completion(self):
        formula_completion = DirectQCompleter(parent=self)
        formula_completion.popup().setStyleSheet(
            f"""
            QListView {{ 
                background-color: {theme.palette.bg_secondary}; 
                color: {theme.palette.text_primary}; 
            }}""")
        self.compound_model.setParent(formula_completion)
        formula_completion.setModel(self.compound_model)
        self.textEdited.connect(self.compound_model.search)
        formula_completion.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        formula_completion.activated[QModelIndex].connect(self._formula_selected)
        self.setCompleter(formula_completion)

    def _formula_selected(self, index: QModelIndex):
        compound = self.compound_model.data(index, role=CompoundDatabaseModel.DataColumn.COMPOUND)
        self.blockSignals(True)
        self.formula = compound.formula
        self.blockSignals(False)
        self.compound_changed.emit(compound)

    def set_formula(self, formula: str):
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
        compound = self.compound_model.get_first_compound()

        if (compound and signature_from_formula(compound.formula)
                == signature_from_formula(self.formula)):
            self.compound_changed.emit(compound)
        else:
            self.compound_changed.emit(Compound(formula=self.formula, density=0))
