"""
File with function and classes that manages arguments that are passed with the
Command Line Interface (CLI)
"""
import pathlib
import re
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from widget.periodic_table_widget import PRESET_LISTS, IsotopeDisplay, PeriodicTableWidget


def _mass_by_symbol_and_isotope_label_from_element_data(element_data: list
                                                        ) -> dict[str, dict[str, float]]:
    """
    Gives a restructured dict from element data.

    The minimal information contained in the dictionaries of the list is :
    * `symbol` : symbol of the element
    * `isotopes` : isotopes associated to the element. It has to have the following information
        * `label` : label of the isotope composed of the atomic number and the symbol (e.g.: 56Fe)
        * `mass` : atomic mass of the isotope

    The returned dict structure will be : dict[symbol][label] = mass.

    Args:
        element_data: list of dictionaries containing information on elements (and isotopes).

    Returns:
        (dict[str, dict[str, float]) returns a dictionary of mass by element symbol and isotope label.
    """
    mass_by_symbol_and_isotope_label = {}

    # Restructuring of periodic_table_info to make it easier to work with
    # It associates the symbol and the isotope label to it's mass
    for element in element_data:
        # Makes the element symbol the key of an isotope dict
        mass_by_symbol_and_isotope_label[element['symbol']] = isotopes_dict = {}
        # Creation of the isotope dictionary (key = label, value = mass)
        for isotope in element['isotopes']:
            isotopes_dict[isotope['label']] = isotope['mass']

    return mass_by_symbol_and_isotope_label


# Constants
PREFERRED_ISOTOPES = IsotopeDisplay.PREFERRED_ISOTOPES
MASS_BY_SYMBOLE_AND_ISOTOPE_LABEL = _mass_by_symbol_and_isotope_label_from_element_data(
    PeriodicTableWidget.create_elements_data())

isotope_regex = re.compile("^(\\d*)([A-Z][a-z]?)$")

LABEL_INDEX = 0
SYMBOL_INDEX = 2


def get_argument_parser() -> ArgumentParser:
    """
    This function builds and return the `ArgumentParser` that
    will take care of CLI inputs.

    Returns: an `ArgumentParser` with the app's configuration
    """
    parser = ArgumentParser(
        prog="IsotopeTrack",
        description="IsotopeTrack is a free, open-source desktop "
                    "application for single-particle ICP-ToF-MS (spICP-MS) "
                    "data analysis.\nIt supports Nu Vitesse and TOFWERK "
                    "instruments and provides a full graphical pipeline — "
                    "from raw signal loading to multi-element statistical "
                    "results.",
    )
    group_project = parser.add_argument_group(
        title="Project File",
        description="Loads a project file (if given, all other arguments will be ignored)",
    )
    group_data = parser.add_argument_group(
        title="Data Loading",
        description="Loads data files and isotopes (files, directories, isotopes"
                    " and presets are ignored if unknown)"
    )

    group_project.add_argument(
        "projectfile",
        nargs="?",
        type=pathlib.Path
    )
    group_data.add_argument(
        "--nu",
        nargs="*",
        type=pathlib.Path,
        help="List of Nu data directories"
    )
    group_data.add_argument(
        "--h5",
        nargs="*",
        type=pathlib.Path,
        help="List of h5 data files"
    )
    group_data.add_argument(
        "--isotopes",
        nargs="?",
        type=str,
        help="Comma separated list of isotopes (needs at least one data source). "
             "E.g.: 56Fe,54Fe,107Ag... (can add to --presets)"
    )
    group_data.add_argument(
        "--presets",
        nargs="?",
        type=str,
        help="Comma separated list of isotope presets (needs at least one data source). "
             "E.g: 71A,68A-B,68B-C..."
    )
    return parser


def get_selected_isotopes(isotopes: list[str] | None,
                          presets: list[str] | None
                          ) -> dict[str, list[float]]:
    """
    Formats a dictionary of elements with list of selected isotope mass, as required by
    `MainWindow.handle_isotopes_selected`.
    Args:
        isotopes (list[str]): List of isotope labels. Unknown labels will be discarded
        presets (list[str]): List of elements presets. Unknown presets will be discarted

    Returns:
        (dict[str, list[float]]) return a dictionary of lists of isotope mass by their element
        (key = element, value = list[isotope_mass])
    """
    if not isotopes and not presets:
        return {}

    # Variable that will be returned
    selected_isotopes: dict[str, list[float]] = {}

    def _add_isotope_mass_to_selected_isotopes(element_symbol: str, isotope_label: str):
        """
        Adds an isotope mass to a selected isotope by directly modifying `selected_isotopes`.
        It also uses `mass_by_symbole_and_isotope_label` to obtain the mass.

        Args:
            element_symbol: symbol of the element
            isotope_label:
        """
        # Adds the mass to the mass list if it exists and isn't already in the list.
        current_masses = selected_isotopes.get(element_symbol, [])

        mass = (
            MASS_BY_SYMBOLE_AND_ISOTOPE_LABEL
            .get(element_symbol, {})
            .get(isotope_label)
        )

        if mass is not None and mass not in current_masses:
            selected_isotopes[element_symbol] = [*current_masses, mass]

    # Isotopes directly specified
    if isotopes:
        for isotope_str in isotopes:
            isotope_match = isotope_regex.match(isotope_str)
            if not isotope_match:
                continue
            symbol = isotope_match[SYMBOL_INDEX]
            label = isotope_match[LABEL_INDEX]
            _add_isotope_mass_to_selected_isotopes(symbol, label)

    # Isotopes specified with presets
    if presets:
        for preset in presets:
            preset_elements = PRESET_LISTS[preset]
            for symbol in preset_elements:
                label = PREFERRED_ISOTOPES[symbol]
                _add_isotope_mass_to_selected_isotopes(symbol, label)

    return selected_isotopes


@dataclass
class CliArguments:
    """
    Object used to work with CLI arguments.

    Notes it was mostly used to help the LSP.
    """
    project_file: pathlib.Path | None
    nu_files: list[pathlib.Path] | None
    tofwerk_files: list[pathlib.Path] | None
    isotopes: list[str] | None
    presets: list[str] | None

    @staticmethod
    def from_args_parser_namespace(namespace: Namespace):
        """
        Converts an `argpars.Namespace` into a `CliArguments`.
        Args:
            namespace (Namespace): Namespace containing the value of the CliArguments.

        Returns:
            (CliArguments) An object with the mapped values from the Namespace.

        """
        return CliArguments(
            project_file=namespace.projectfile,
            nu_files=namespace.nu,
            tofwerk_files=namespace.h5,
            isotopes=namespace.isotopes.split(",") if namespace.isotopes else None,
            presets=namespace.presets.split(",") if namespace.presets else None,
        )
