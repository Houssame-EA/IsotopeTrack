"""
This file contains a readonly service (info) for periodic table data.
"""
from enum import StrEnum, auto
from typing import Optional

import numpy as np
import pandas as pd

from widget.periodic_table_widget import PeriodicTableWidget


class _Col(StrEnum):
    """
    Columns in the dataframe and the maps of the `PeriodicTableInfo`.
    Notes:
        This is supposed to be an inner class of `PeriodicTableInfo` but,
        for readability it was put outside.
    """
    SYMBOL = auto()
    NAME = auto()
    MASS = auto()
    ROW = auto()
    COL = auto()
    ISOTOPES = auto()
    ISOTOPE_MASS = "mass"
    ISOTOPE_ABUNDANCE = "abundance"
    ISOTOPE_LABEL = "label"
    CATEGORY = auto()
    ATOMIC_NUMBER = auto()
    DENSITY = auto()
    IONIZATION_ENERGY = auto()


class PeriodicTableInfo:
    """
    This class is used to provide information about elements and isotopes
    of the periodic table.
    """

    def __init__(self):
        self.df = pd.DataFrame(
            PeriodicTableWidget.create_elements_data()
        ).set_index(_Col.SYMBOL, drop=False)

    def get_mass_by_element(self, element: str) -> Optional[float]:
        """
        Args:
            element: element symbol
        Returns:
            The mass of the element based on the symbol passed.
        """
        try:
            np_value: np.float64 = self.df.at[element, _Col.MASS]
            return np_value
        except KeyError:
            return None

    def get_density_by_element(self, element: str) -> Optional[float]:
        """
        Args:
            element: element symbol
        Returns:
            Optional[float]: The density of the element based on the symbol passed.
        """
        try:
            np_value: np.float64 = self.df.at[element, _Col.DENSITY]
            return np_value
        except KeyError:
            return None
