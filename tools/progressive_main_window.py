"""Progressive loading system for main window with splash screen support."""
import pathlib
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow
from tools.mass_fraction_calculator import CSVCompoundDatabase


class ProgressiveMainWindow(QObject):
    """
    Progressive main window loader with step-by-step initialization and progress reporting.
    """

    progress_updated = Signal(int, str)
    loading_complete = Signal()

    def __init__(self):
        """
        Initialize the progressive main window loader.
        
        Args:
            None
            
        Returns:
            None
        """
        super().__init__()
        self.main_window = None
        self.current_step = 0
        self.total_steps = 10

        self.loading_steps = [
            (5, "Importing modules...", self.step_import_modules),
            (15, "Initializing core systems...", self.step_init_core),
            (25, "Setting up window layout...", self.step_setup_window),
            (30, "Preloading Mass Fraction DB", self.step_preload_mass_fraction_db),
            (35, "Creating central widgets...", self.step_create_widgets),
            (45, "Initializing plot widgets...", self.step_init_plots),
            (55, "Setting up data structures...", self.step_setup_data),
            (70, "Configuring menu systems...", self.step_setup_menus),
            (85, "Connecting signals...", self.step_connect_signals),
            (90, "Finalizing interface...", self.step_finalize),
            (95, "Parssing CLI arguments...", self.step_parse_cli_arguments),
            (100, "Ready!", self.step_complete)
        ]

    def start_loading(self):
        """
        Start the progressive loading process.
        
        Args:
            None
            
        Returns:
            None
        """
        self.current_step = 0
        self.process_next_step()

    def process_next_step(self):
        """
        Process the next loading step in sequence.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.current_step < len(self.loading_steps):
            progress, status, step_func = self.loading_steps[self.current_step]
            self.progress_updated.emit(progress, status)
            QApplication.processEvents()

            try:
                step_func()
                self.current_step += 1

                QTimer.singleShot(100, self.process_next_step)

            except Exception as e:
                self.progress_updated.emit(100, f"Error: {str(e)}")
                self.loading_complete.emit()
        else:
            self.loading_complete.emit()

    def step_import_modules(self):
        """
        Step 1: Import additional modules if needed.
        
        Args:
            None
            
        Returns:
            None
        """
        QApplication.processEvents()

    def step_init_core(self):
        """
        Step 2: Initialize core MainWindow.
        
        Args:
            None
            
        Returns:
            None
        """
        self.main_window = MainWindow()

    def step_setup_window(self):
        """
        Step 3: Setup window properties.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_create_widgets(self):
        """
        Step 4: Create central widgets.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_init_plots(self):
        """
        Step 5: Initialize plot widgets.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_setup_data(self):
        """
        Step 6: Setup data structures.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_setup_menus(self):
        """
        Step 7: Configure menu systems.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_connect_signals(self):
        """
        Step 8: Connect signals and slots.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_finalize(self):
        """
        Step 9: Finalize interface.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_parse_cli_arguments(self):
        """
        Step 10: Parsing and executing cli arguments. See `TODO` for more info
         about the parser.
        """
        if len(sys.argv) <= 1 or not self.main_window:
            return

        self.main_window.log_status("Parsing cli arguments")  # TODO: dependency injection (DI)

        # Parsing arguments
        parser = self.get_argument_parser()
        arguments: CliArguments = CliArguments.from_args_parser_namespace(parser.parse_args())

        main_window: MainWindow = self.main_window
        main_window.log_status(f"Arguments : {arguments.__str__()}")  # TODO: DI
        if arguments.project_file:
            main_window.log_status(
                f"Project loading via CLI")  # TODO: Change for a new type of log passed via dependency injection
            main_window.load_project(filepath=str(arguments.project_file))
            return

        if arguments.nu_files:
            main_window.log_status(f"Nu data loading via CLI")  # TODO: DI and add an indicator for discarded files
            main_window.process_folders(
                [str(path) for path in arguments.nu_files
                 if path.exists() and path.is_dir()]
            )

        if arguments.tofwerk_files:
            has_h5_extention = lambda path: ".h5" == path.suffix.lower()

            main_window.log_status(f"TOFWERK (.H5) data loading via CLI")  # TODO: DI and add an indicator for discarded files
            main_window.process_tofwerk_files(
                [str(path) for path in arguments.tofwerk_files
                 if path.exists() and has_h5_extention(path)]
            )

        # TODO: check si on peut utiliser le load du Periodic table
        selected_isotopes = self.get_selected_isotopes(arguments.isotopes, arguments.presets)
        if selected_isotopes:
            main_window.log_status(f"Selecting {len(selected_isotopes)} isotope(s) via CLI")  # TODO: DI
            main_window.handle_isotopes_selected(selected_isotopes)

    def get_selected_isotopes(self,
                              isotopes: list[str] | None,
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

        # Reference variables and functions
        import re
        from widget.periodic_table_widget import PeriodicTableWidget, PRESET_LISTS, IsotopeDisplay

        preset_lists = PRESET_LISTS
        preferred_isotopes = IsotopeDisplay.PREFERRED_ISOTOPES
        periodic_table_info = PeriodicTableWidget.create_elements_data()
        mass_by_symbol_and_isotope_label = self.mass_by_symbol_and_isotope_label_from_element_data(
            periodic_table_info)

        isotope_regex = re.compile("^(\\d*)([A-Z][a-z]?)$")

        label_index = 0
        symbol_index = 2

        # Variable that will be returned
        selected_isotopes: dict[str, list[float]] = {}

        def add_isotope_mass_to_selected_isotopes(element_symbol: str, isotope_label: str):
            # Variables from outside scope
            # Mutated : selected_isotopes
            # Immutable : mass_by_symbol_and_isotope_label

            # Adds the mass to the mass list if it exists and isn't already in the list.
            current_masses = selected_isotopes.get(element_symbol, [])

            mass = (
                mass_by_symbol_and_isotope_label
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
                symbol = isotope_match[symbol_index]
                label = isotope_match[label_index]
                add_isotope_mass_to_selected_isotopes(symbol, label)

        # Isotopes specified with presets
        if presets:
            for preset in presets:
                preset_elements = preset_lists[preset]
                for symbol in preset_elements:
                    label = preferred_isotopes[symbol]
                    add_isotope_mass_to_selected_isotopes(symbol, label)

        return selected_isotopes

    def mass_by_symbol_and_isotope_label_from_element_data(self,
                                                           element_data: list
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

    def get_argument_parser(self) -> ArgumentParser:  # TODO: dependency injection
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
            description="Loads data files and isotopes"
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
        )  # TODO : check if it's okay and gives a list
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
            help="Comma separated list of isotopes (needs at least one data source). E.g.: 56Fe,54Fe,107Ag... (can add to --presets)"
        )
        group_data.add_argument(
            "--presets",
            nargs="?",
            type=str,
            help="Comma separated list of isotope presets (needs at least one data source). E.g: 71A,68A-B,68B-C... (is ignored if unknown)"
        )
        return parser

    def step_complete(self):
        """
        Step 11: Loading complete.
        
        Args:
            None
            
        Returns:
            None
        """
        pass

    def get_main_window(self):
        """
        Get the loaded main window.
        
        Args:
            None
            
        Returns:
            MainWindow: The initialized main window instance
        """
        return self.main_window

    def step_preload_mass_fraction_db(self):
        """
        Preload the Mass Fraction CSV database and cache it on the main window.
        
        This step loads the CSV database during splash screen to avoid lag later.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.main_window:
            return
        try:
            db = CSVCompoundDatabase()
            db.auto_load_csv()
            setattr(self.main_window, "_cached_csv_database", db)
            QApplication.processEvents()
        except Exception as e:
            print(f"[ProgressiveMainWindow] CSV preload skipped: {e}")
            QApplication.processEvents()


@dataclass
class CliArguments:  # TODO: move to new file
    project_file: pathlib.Path | None
    nu_files: list[pathlib.Path] | None
    tofwerk_files: list[pathlib.Path] | None
    isotopes: list[str] | None
    presets: list[str] | None

    @staticmethod
    def from_args_parser_namespace(namespace: Namespace):
        return CliArguments(
            project_file=namespace.projectfile,
            nu_files=namespace.nu,
            tofwerk_files=namespace.h5,
            isotopes=namespace.isotopes.split(",") if namespace.isotopes else None,
            presets=namespace.presets.split(",") if namespace.presets else None,
        )
