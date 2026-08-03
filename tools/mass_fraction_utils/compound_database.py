from __future__ import annotations

import logging
from enum import StrEnum, auto, IntEnum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QObject

from tools.mass_fraction_utils.formula_utils import (
    parse_formula_to_counts,
    canonicalize_preserve_user_order,
    signature_from_formula,
    elements_with_count_from_formula
)
from tools.mass_fraction_utils.compound import Compound
from widget.periodic_table_widget import PeriodicTableWidget

logger = logging.getLogger(__name__)


class _MFCol(StrEnum):
    FORMULA = auto()
    DENSITY = auto()
    MATERIAL_ID = auto()
    SPACE_GROUP = auto()
    MP_URL = auto()
    SIGNATURE = auto()
    DISPLAY_TEXT = auto()


class CSVCompoundDatabase:
    """Service that manages the querying of the data of a `CSVCompoundDatabase`"""

    def __init__(self, tracked_elements: list[str] | None = None):
        self.analysed_elements = tracked_elements

        self.df_og: pd.DataFrame = pd.DataFrame()
        self.df: pd.DataFrame = self.df_og
        self.is_loaded = False

    def _init_df_with_analysed_elements(self):
        """
        Initializes `self.df`with the periodic table elements and narrows
        down the search space to compounds containing analyzed elements.
        """
        logger.info("Initializing with elements (from periodic table).")
        self.df = pd.concat([self.df_og, self._elements_as_compound_df()], ignore_index=True)

        if self.analysed_elements:
            self.df = self.df[
                self.df["formula"].str
                .contains("|".join(self.analysed_elements),
                          regex=True)
            ]

    @staticmethod
    def _elements_as_compound_df() -> pd.DataFrame:
        """Returns a `DataFrame` with elements of the periodic table."""
        elements_list = []
        elements_data = PeriodicTableWidget.create_elements_data()  # TODO: change for PeriodicTableInfo
        for element in elements_data:
            element_formula = element["symbol"]
            element_density = element["density"]
            element_display_text = f"{element_formula} - {element_density} g/cm³"
            element_signature = signature_from_formula(element_formula)

            element_row = {
                _MFCol.FORMULA: element_formula,
                _MFCol.DENSITY: element_density,
                _MFCol.MATERIAL_ID: "",
                _MFCol.MP_URL: "",
                _MFCol.SPACE_GROUP: "",
                _MFCol.SIGNATURE: element_signature,
                _MFCol.DISPLAY_TEXT: element_display_text
            }
            elements_list.append(element_row)
        return pd.DataFrame(elements_list)

    def auto_load_csv(self) -> bool:
        """Try to load CSV from standard locations, preferring trimmed/compressed versions.

        Handles both normal execution and PyInstaller frozen bundles
        (where data files live under sys._MEIPASS).
        """
        import sys

        base_dirs = []

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dirs.append(Path(sys._MEIPASS) / 'data')

        base_dirs.extend([
            Path(__file__).resolve().parent / 'data',
            Path(__file__).resolve().parent.parent / 'data',
            Path.cwd() / 'data',
        ])

        filenames = [
            'materials_trimmed.csv.gz',  # TODO: Generate the V2
        ]
        for base in base_dirs:
            for fname in filenames:
                p = base / fname
                if p.exists():
                    logger.info("Found CSV at %s", p)
                    return self.load_csv(p)
        logger.warning("No CSV file found in standard locations")
        self._init_df_with_analysed_elements()
        return False

    def load_csv(self, csv_path: str | Path) -> bool:
        """Load CSV and build signature-based indices."""
        if self.is_loaded:
            return True
        try:
            csv_path = Path(csv_path)
            logger.info("Loading CSV from %s", csv_path)
            self.df_og = pd.read_csv(csv_path)
            if not isinstance(self.df_og, pd.DataFrame):
                self._init_df_with_analysed_elements()

                return False
            logger.info("CSV loaded with %d rows", len(self.df_og))

            for col in (_MFCol.FORMULA, _MFCol.DENSITY, _MFCol.MATERIAL_ID, _MFCol.SPACE_GROUP):
                if col not in self.df_og.columns:
                    self.df_og[col] = ''

            self.df_og[_MFCol.FORMULA] = (self.df_og[_MFCol.FORMULA]
                                          .str.strip()
                                          .replace('', np.nan)
                                          .dropna())

            self.df_og[_MFCol.DENSITY] = (self.df_og[_MFCol.DENSITY]
                                          .astype(float)
                                          .replace(np.nan, 0.0))

            self.df_og[_MFCol.MATERIAL_ID] = (self.df_og[_MFCol.MATERIAL_ID]
                                              .str.strip()
                                              .replace(np.nan, ''))

            if _MFCol.MP_URL not in self.df_og.columns:
                self.df_og[_MFCol.MP_URL] = self.df_og.material_id.apply(self._mp_url_from_material_id)
            else:
                self.df_og[_MFCol.MP_URL] = self.df_og[_MFCol.MP_URL].str.strip()

                self.df_og.loc[self.df_og[_MFCol.MP_URL] == '', _MFCol.MP_URL] = (
                    self.df_og.loc[self.df_og[_MFCol.MP_URL] == '', _MFCol.MATERIAL_ID]
                    .apply(self._mp_url_from_material_id)
                )

            self.df_og[_MFCol.SPACE_GROUP] = self.df_og[_MFCol.SPACE_GROUP].replace(np.nan, '')

            if _MFCol.SIGNATURE not in self.df_og.columns:
                self.df_og[_MFCol.SIGNATURE] = self.df_og.formula.apply(signature_from_formula)

            if _MFCol.DISPLAY_TEXT not in self.df_og.columns:
                self.df_og[_MFCol.DISPLAY_TEXT] = (
                        self.df_og[_MFCol.FORMULA]
                        + " [" + self.df_og[_MFCol.SPACE_GROUP]
                        + "] (" + self.df_og[_MFCol.DENSITY].map("{:.3f}".format)
                        + " g/cm³) - " + self.df_og[_MFCol.MATERIAL_ID])

            # Adds the periodic table elements
            self._init_df_with_analysed_elements()

            self.is_loaded = True
            logger.info(
                "Database loaded: %d rows processed, %d canonical compounds indexed",
                len(self.df_og), len(self.df_og.groupby(_MFCol.FORMULA)),
            )
            return True

        except Exception:
            logger.exception("Error loading CSV")
            return False

    def get_compound(self, index: int) -> Compound:
        """
        Gets the compound based on it's index
        Args:
            index: index to retrieve
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

    def search_compounds_by_formula(self, formula: str, max_count: int = 50) -> list[Compound]:
        """
        Searches for the `max_count` (default 50) shortest compounds
        fitting the formula.

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
            self.df[_MFCol.SIGNATURE].str.contains(regex_product_of_elements, regex=True)
        ].sort_values(by=_MFCol.FORMULA,
                      key=lambda x: x.str.len())[:max_count]

        return self._dicts_to_compound(
            rows_with_formula_elements_sorted_by_length.to_dict("records"))

    def get_searchable_model(self,
                             base_formula: Optional[str] = None,
                             parent: QObject | Any = None) -> CompoundDatabaseModel:
        """
        Gives a usable searchable model.

        Args:
            base_formula: the formula which elements are mandatory when
            searching.
            parent: parent of the resulting `CompoundDatabaseModel`.
        Returns:
            `CompoundDatabaseModel` that can be used to query the `CompoundService`.
        """
        return CompoundDatabaseModel(self, base_formula, parent)

    @staticmethod
    def _mp_url_from_material_id(material_id: str) -> str:
        """Creates a url from the `material_id`"""
        if material_id:
            return f"https://materialsproject.org/materials/{material_id}"
        else:
            return ""

    def row_count(self) -> int:
        return len(self.df)

    def get_first_compound_by_formula(self, formula: str) -> Optional[Compound]:
        # Regex that checks if all elements are present without ordering.
        rows_matching_formula = self.df[self.df[_MFCol.FORMULA] == formula]

        if len(rows_matching_formula) > 0:
            return self._row_to_compound(rows_matching_formula.iloc[0])
        else:
            return None


class CompoundDatabaseModel(QAbstractListModel):
    """Adaptor between `CompoundService` and `QAbstractListModel`"""
    class DataColumn(IntEnum):
        DISPLAY_TEXT = Qt.ItemDataRole.DisplayRole
        FORMULA = Qt.ItemDataRole.EditRole
        COMPOUND = Qt.ItemDataRole.UserRole | 0x00
        DENSITY = Qt.ItemDataRole.UserRole | 0x01


    def __init__(self,
                 database: CSVCompoundDatabase,
                 base_formula: Optional[str] = None,
                 parent: QObject | Any = None):
        super().__init__(parent=parent)
        self.db = database
        self.base_formula = (canonicalize_preserve_user_order(base_formula)
                             if base_formula
                             else None)
        self.results: list[Compound] = []
        self.search(self.base_formula or "")

    def rowCount(self, /, parent=QModelIndex()):
        return len(self.results)

    def data(self, index, /, role=DataColumn.DISPLAY_TEXT):
        if role == self.DataColumn.DISPLAY_TEXT:
            return self.results[index.row()].display_text
        if role == self.DataColumn.FORMULA:
            return self.results[index.row()].formula
        if role == self.DataColumn.DENSITY:
            return self.results[index.row()].density
        if role == self.DataColumn.COMPOUND:
            return self.results[index.row()]
        return None

    def search(self, text: str):
        """
        Updates the model results with the passed `text
        Args:
            text: String that will be used to search
        """
        # Adds the base formula/element
        element_counts = parse_formula_to_counts(self.base_formula)
        for element in element_counts.keys():
            if element not in text:
                text += element

        self.beginResetModel()
        self.results = self.db.search_compounds_by_formula(text)
        self.endResetModel()

    def get_first_compound(self) -> Optional[Compound]:
        return self.results[0] if len(self.results) > 0 else None
