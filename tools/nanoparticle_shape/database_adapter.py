from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QObject
import pandas as pd
from PySide6.QtWidgets import QCompleter

from tools.mass_fraction_calculator_utils.compound_database import CSVCompoundDatabase
from tools.mass_fraction_calculator_utils.formula_utils import elements_with_count_from_formula
from tools.nanoparticle_shape.nanoparticle_shapes import Compound


class CompoundService:
    """Service that manages the querying of the data of a `CSVCompoundDatabase`"""
    def __init__(self, database: CSVCompoundDatabase, tracked_elements: list[str] | None = None):
        self.analysed_elements = tracked_elements

        self.df_og = database.data if database.data is not None else pd.DataFrame()
        self.df: pd.DataFrame = self.df_og

        self._filter_by_analysed_elements()

    def _filter_by_analysed_elements(self):
        if not self.analysed_elements:
            return
        self.df = self.df_og[
            self.df_og["formula"].str
            .contains("|".join(self.analysed_elements),
                      regex=True)
        ]

    def get_compound(self, index: int) -> Compound:
        """
        Gets the compound based on it's index
        Args:
            index: index to retreve
        """
        return self._row_to_compound(self.df.iloc[index])

    @staticmethod
    def _row_to_compound(row) -> Compound:
        return Compound(**row.to_dict())

    @staticmethod
    def _dicts_to_compound(dicts: list[dict]) -> list[Compound]:
        return list(map(lambda x: Compound(**x), dicts))

    def __len__(self):
        return len(self.df)

    def search_compounds_by_formula(self, formula: str, max_count: int = 50) ->list[Compound]:
        """
        Searches for the `max_count` shortest compounds fitting the formula.
        Args:
            formula: The formula that we want to look for closest match.
            max_count: (default=`50`) Maximum amount of matches returned.
        Returns:
            A list of the `max_count` closest matches.
        """
        # Regex that checks if all elements are present without ordering.
        regex_product_of_elements = "".join([f"(?=.*{element})"
                                             for element in elements_with_count_from_formula(formula)])

        rows_with_formula_elements_sorted_by_length = self.df[
            self.df["signature"].str.contains(regex_product_of_elements, regex=True)
        ][:max_count].sort_values(by="formula",
                                  key=lambda x: x.str.len())

        return self._dicts_to_compound(
            rows_with_formula_elements_sorted_by_length.to_dict("records"))

    def get_searchable_model(self, parent: QObject | Any = None):
        """
        Gives a usable searchable model.

        Args:
            parent: parent of the resulting `CompoundDatabaseModel`.
        Returns:
            `CompoundDatabaseModel` that can be used to query the `CompoundService`.
        """
        return CompoundDatabaseModel(self, parent)


class CompoundDatabaseModel(QAbstractListModel):
    """Adaptor between `CompoundService` and `QAbastractListModel`"""
    def __init__(self, database: CompoundService, parent=None):
        super().__init__(parent=parent)
        self.db = database
        self.results: list[Compound] = []

    def rowCount(self, /, parent=QModelIndex()):
        return len(self.results)

    def data(self, index, /, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.results[index.row()].display_text
        if role == Qt.ItemDataRole.EditRole:
            return self.results[index.row()].formula
        if role == Qt.ItemDataRole.UserRole:
            return self.results[index.row()].density
        return None

    def search(self, text: str):
        """
        Updates the model results with the passed `text
        Args:
            text: String that will be used to search
        """
        self.beginResetModel()
        self.results = self.db.search_compounds_by_formula(text)
        self.endResetModel()


class DirectQCompleter(QCompleter):
    """Enables a `QCompleter` to show all model results regardless of the input"""
    def splitPath(self, _, /):
        return [""]
