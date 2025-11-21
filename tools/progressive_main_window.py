"""Progressive loading system for main window with splash screen support."""
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
            (95, "Finalizing interface...", self.step_finalize),
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
    
    def step_complete(self):
        """
        Step 10: Loading complete.
        
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