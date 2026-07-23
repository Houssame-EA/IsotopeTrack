"""
This file contains a readonly service (info) for periodic table data.
"""
from enum import StrEnum, auto
from typing import Optional

from widget.periodic_table_widget import PeriodicTableWidget


class _Col(StrEnum):
    """
    Columns in the maps of the `PeriodicTableInfo`.
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
        self.elements = {element_info[_Col.SYMBOL]: element_info
                         for element_info in
                         PeriodicTableWidget.create_elements_data()}

    def element_exists(self, element: str) -> bool:
        """
        Args:
            element: element to verify the existence
        Returns:
            `True` if the element exists, `False` if it doesn't exist.
        """
        return element in self.elements.keys()

    def get_mass_by_element(self, element: str) -> Optional[float]:
        """
        Args:
            element: element symbol
        Returns:
            The mass of the element based on the symbol passed.
        """
        return self.elements.get(element, {}).get(_Col.MASS, None)

    def get_density_by_element(self, element: str) -> Optional[float]:
        """
        Args:
            element: element symbol
        Returns:
            Optional[float]: The density of the element based on the
            symbol passed.
        """
        return self.elements.get(element, {}).get(_Col.DENSITY, None)

    def get_element_by_symbol(self, element: str) -> Optional[dict]:
        """
        Args:
            element: Element symbol
        Returns:
            Optional[dict]: A `dict` with the element properties
        """
        return self.elements.get(element, None)
