"""Progressive loading system for main window with splash screen support."""
import sys
from argparse import ArgumentParser

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow
from tools.cli_utils import get_selected_isotopes, CliArguments
from tools.logging_utils import logging_manager
from tools.mass_fraction_calculator import CSVCompoundDatabase
from widget.periodic_table_widget import PeriodicTableWidget
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.progressive_main_window")


class ProgressiveMainWindow(QObject):
    """
    Progressive main window loader with step-by-step initialization and progress reporting.
    """

    progress_updated = Signal(int, str)
    loading_complete = Signal()

    def __init__(self, cli_parser: ArgumentParser):
        """
        Initialize the progressive main window loader.
        
        Args:
            cli_parser (argparse.ArgumentParser): Parser used to get the Cli arguments.
            
        Returns:
            None
        """
        super().__init__()
        self.cli_parser = cli_parser
        if not hasattr(self, 'logger'):
            self.logger = logging_manager.get_logger('ProgressiveMainWindow')
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
        
        Returns:
            None
        """
        self.current_step = 0
        self.process_next_step()

    def process_next_step(self):
        """
        Process the next loading step in sequence.
        
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
                _itk_log.exception("Handled exception in process_next_step")
                self.progress_updated.emit(100, f"Error: {str(e)}")
                self.loading_complete.emit()
        else:
            self.loading_complete.emit()

    def step_import_modules(self):
        """
        Step 1: Import additional modules if needed.
        """
        QApplication.processEvents()

    def step_init_core(self):
        """
        Step 2: Initialize core MainWindow.
        
        Returns:
            None
        """
        self.main_window = MainWindow()

    def step_setup_window(self):
        """
        Step 3: Setup window properties.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_create_widgets(self):
        """
        Step 4: Create central widgets.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_init_plots(self):
        """
        Step 5: Initialize plot widgets.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_setup_data(self):
        """
        Step 6: Setup data structures.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_setup_menus(self):
        """
        Step 7: Configure menu systems.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_connect_signals(self):
        """
        Step 8: Connect signals and slots.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_finalize(self):
        """
        Step 9: Finalize interface.
        
        Returns:
            None
        """
        if self.main_window:
            QApplication.processEvents()

    def step_parse_cli_arguments(self):
        """
        Step 10: Parsing and executing cli arguments.
        """
        if len(sys.argv) <= 1 or not isinstance(self.main_window, MainWindow):
            return

        self.log_status("Parsing cli arguments")

        # Parsing arguments
        arguments: CliArguments = CliArguments.from_args_parser_namespace(self.cli_parser.parse_args())

        self.log_status(f"Arguments : {arguments}")

        if arguments.project_file:
            self.log_status(f"Project loading via CLI")
            self.main_window.load_project(filepath=str(arguments.project_file))
            return

        loaded_files = False

        if arguments.nu_files:
            self.log_status(f"Nu data loading via CLI")
            self.main_window.process_folders(
                [str(path) for path in arguments.nu_files
                 if path.exists() and path.is_dir()]
            )
            loaded_files = True

        if arguments.tofwerk_files:
            has_h5_extention = lambda path: ".h5" == path.suffix.lower()

            self.log_status(f"TOFWERK (.H5) data loading via CLI")
            self.main_window.process_tofwerk_files(
                [str(path) for path in arguments.tofwerk_files
                 if path.exists() and has_h5_extention(path)]
            )
            loaded_files = True

        periodic_table = self.main_window.periodic_table_widget
        if loaded_files and isinstance(periodic_table, PeriodicTableWidget):
            periodic_table.hide()
            selected_isotopes_by_element = get_selected_isotopes(arguments.isotopes, arguments.presets)
            if selected_isotopes_by_element:
                # Tries to load the isotopes
                selected_isotopes_count = sum([len(masses) for masses in selected_isotopes_by_element.values()])
                self.log_status(f"Selecting {selected_isotopes_count} isotopes(s) via CLI")
                updated_element_cout, not_loaded_elements = periodic_table.update_selection(
                    selected_isotopes_by_element)

                # Automatically confirms the loaded isotopes
                self.log_status(f"Selected {updated_element_cout} / {selected_isotopes_count} isotopes. "
                                f"Missing elements/isotopes: {not_loaded_elements}")
                periodic_table.confirm_selections()
        else:
            if not loaded_files:
                self.log_status("No files loaded --> No isotope loaded")
            else:
                self.log_status("No periodic table loaded --> No isotope loaded")

    def step_complete(self):
        """
        Step 11: Loading complete.
        
        Returns:
            None
        """
        pass

    def get_main_window(self):
        """
        Get the loaded main window.
        
        Returns:
            MainWindow: The initialized main window instance
        """
        return self.main_window

    def step_preload_mass_fraction_db(self):
        """
        Preload the Mass Fraction CSV database and cache it on the main window.
        
        This step loads the CSV database during splash screen to avoid lag later.
        
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
            _itk_log.exception("Handled exception in step_preload_mass_fraction_db")
            print(f"[ProgressiveMainWindow] CSV preload skipped: {e}")
            QApplication.processEvents()

    def log_status(self, message: str):
        """
        Logs the message that's given.

        Notes: This method is made to be extended as needed.

        Args:
            message (str): String that will be displayed in the log.
        """
        self.logger.info(message)
