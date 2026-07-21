"""
This file defines the interface to get information about an element and
it's isotopes.
Notes:
    Here are the fields in the elements data:

    * symbole
    * name
    * mass
    * row
    * col
    * isotopes
        * mass
        * abundance
        * label
    * category
    * atomic_number
    * density
    * ionization_energy
"""
from widget.periodic_table_widget import PeriodicTableWidget
import pandas as pd


class PeriodicTableInfo:
    def __init__(self):
        self.elements_data: pd.DataFrame = pd.DataFrame(
            PeriodicTableWidget.create_elements_data()).set_index("symbol", drop=False)
        # Note to def. always use `loc[]` to use the indexes (iloc[int] is for the numerical index).

    def get_element_by_symbol(self, symbol:str):
        if symbol not in self.elements_data.index:
            return None
        return self.elements_data.loc[symbol].to_dict()
