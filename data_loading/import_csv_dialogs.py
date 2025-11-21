import sys
import pandas as pd
import numpy as np
import re
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QTableWidget, QTableWidgetItem, QPushButton, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QGroupBox, QGridLayout,
                             QTextEdit, QTabWidget, QWidget, QFileDialog, QMessageBox,
                             QProgressDialog, QApplication, QHeaderView, QFrame,
                             QSplitter, QListWidget, QListWidgetItem, QLineEdit,
                             QButtonGroup, QRadioButton)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor, QPalette
from widget.periodic_table_widget import PeriodicTableWidget

class CSVPreviewTableWidget(QTableWidget):
    """
    Custom table widget for CSV preview with enhanced features.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the CSV preview table widget.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectColumns)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
    def highlight_column(self, column, color=QColor(173, 216, 230)):
        """
        Highlight a specific column.
        
        Args:
            column (int): Column index to highlight
            color (QColor): Color to use for highlighting
            
        Returns:
            None
        """
        for row in range(self.rowCount()):
            item = self.item(row, column)
            if item:
                item.setBackground(color)

class IsotopeMatchingWidget(QWidget):
    """
    Widget for matching CSV columns to isotopes.
    """
    
    def __init__(self, periodic_table_data, parent=None):
        """
        Initialize the isotope matching widget.
        
        Args:
            periodic_table_data (list): List of periodic table element data
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.periodic_table_data = periodic_table_data
        self.setup_ui()
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Isotope:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type element symbol or mass...")
        self.search_box.textChanged.connect(self.filter_isotopes)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)
        
        self.isotope_list = QListWidget()
        self.isotope_list.setMaximumHeight(200)
        self.populate_isotope_list()
        layout.addWidget(self.isotope_list)
        
    def populate_isotope_list(self):
        """
        Populate the isotope list from periodic table data.
        
        Args:
            None
            
        Returns:
            None
        """
        self.isotope_list.clear()
        if not self.periodic_table_data:
            common_isotopes = []
            for isotope in common_isotopes:
                text = f"{isotope['label']} - {isotope['element_name']} ({isotope['mass']:.4f} amu)"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, isotope)
                self.isotope_list.addItem(item)
            return
        
        isotopes = []
        for element in self.periodic_table_data:
            symbol = element['symbol']
            for isotope in element['isotopes']:
                if isinstance(isotope, dict):
                    mass = isotope['mass']
                    abundance = isotope.get('abundance', 0)
                    label = isotope.get('label', f"{round(mass)}{symbol}")
                else:
                    mass = isotope
                    abundance = 0
                    label = f"{round(mass)}{symbol}"
                
                isotopes.append({
                    'symbol': symbol,
                    'mass': mass,
                    'abundance': abundance,
                    'label': label,
                    'element_name': element['name']
                })
        
        isotopes.sort(key=lambda x: x['mass'])
        
        for isotope in isotopes:
            text = f"{isotope['label']} - {isotope['element_name']} ({isotope['mass']:.4f} amu)"
            if isotope['abundance'] > 0:
                text += f" - {isotope['abundance']:.1f}%"
            
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, isotope)
            self.isotope_list.addItem(item)
    
    def filter_isotopes(self, text):
        """
        Filter isotopes based on search text.
        
        Args:
            text (str): Search text
            
        Returns:
            None
        """
        for i in range(self.isotope_list.count()):
            item = self.isotope_list.item(i)
            isotope_data = item.data(Qt.UserRole)
            matches = (
                text.lower() in isotope_data['symbol'].lower() or
                text.lower() in isotope_data['element_name'].lower() or
                text.lower() in isotope_data['label'].lower() or
                text in str(isotope_data['mass'])
            )
            item.setHidden(not matches)
    
    def get_selected_isotope(self):
        """
        Get the currently selected isotope.
        
        Args:
            None
            
        Returns:
            dict | None: Selected isotope data or None
        """
        current_item = self.isotope_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None

class DataProcessThread(QThread):
    """
    Thread to process data according to configuration - supports CSV, TXT, and Excel files.
    """
    
    progress = Signal(int)
    finished = Signal(object, object, object, str, str)
    error = Signal(str)
    
    def __init__(self, config, parent=None):
        """
        Initialize the data processing thread.
        
        Args:
            config (dict): Configuration dictionary
            parent (QObject, optional): Parent object
            
        Returns:
            None
        """
        super().__init__(parent)
        self.config = config
        
    def run(self):
        """
        Execute the thread processing.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            total_files = len(self.config['files'])
            
            for file_index, file_config in enumerate(self.config['files']):
                try:
                    progress = int((file_index / total_files) * 90)
                    self.progress.emit(progress)
                    result = self.process_file(file_config, file_index)
                    if result:
                        sample_name, sample_data = result
                        self.finished.emit(
                            sample_data['signals'], 
                            sample_data['run_info'], 
                            sample_data['time_array'], 
                            sample_name,
                            sample_data.get('datetime', '')
                        )
                        
                except Exception as e:
                    self.error.emit(f"Error processing file {file_config['name']}: {str(e)}")
                    continue
            self.progress.emit(100)
                
        except Exception as e:
            self.error.emit(f"Data processing error: {str(e)}")
            
    def process_file(self, file_config, file_index):
        """
        Process a single file - supports CSV, TXT, and Excel formats.
        
        Args:
            file_config (dict): File configuration dictionary
            file_index (int): Index of the file
            
        Returns:
            tuple | None: (sample_name, sample_data) or None if error
        """
        try:
            file_path = file_config['path']
            settings = self.config['settings']
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ['.csv', '.txt']:
                df = self.load_delimited_file(file_path, settings)
            elif file_ext in ['.xls', '.xlsx', '.xlsm', '.xlsb']:
                df = self.load_excel_file(file_path, settings)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
                
            sample_name = Path(file_path).stem
            time_array, final_dwell_time = self.process_time_column(df, settings)
            signals = self.process_isotope_columns(
                df, 
                file_config['mappings'], 
                settings, 
                final_dwell_time
            )
            run_info = self.create_run_info(df, settings, file_path, final_dwell_time, file_ext)
            
            sample_data = {
                'signals': signals,
                'time_array': time_array,
                'run_info': run_info,
                'datetime': '' 
            }
            return sample_name, sample_data
            
        except Exception as e:
            self.error.emit(f"Error processing {file_path}: {str(e)}")
            return None
    
    def load_delimited_file(self, file_path, settings):
        """
        Load CSV or TXT file with delimiter parsing and stop at first empty row or text row.
        
        Args:
            file_path (str): Path to file
            settings (dict): Import settings
            
        Returns:
            pd.DataFrame: Loaded data
        """
        delimiter = settings['delimiter']
        if delimiter == "\\t":
            delimiter = "\t"
        
        df = pd.read_csv(
            file_path,
            delimiter=delimiter,
            header=settings['header_row'] if settings['header_row'] >= 0 else None,
            skiprows=range(settings['skip_rows']) if settings['skip_rows'] > 0 else None,
            encoding=settings['encoding']
        )
        
        first_stopping_row = self.find_first_stopping_row(df)
        if first_stopping_row < len(df):
            print(f"Stopping data import at row {first_stopping_row} (found empty row or text)")
            df = df.iloc[:first_stopping_row].copy()
        
        return df
    
    def load_excel_file(self, file_path, settings):
        """
        Load Excel file with robust error handling and stop at first empty row or text row.
        
        Args:
            file_path (str): Path to Excel file
            settings (dict): Import settings
            
        Returns:
            pd.DataFrame: Loaded data
        """
        try:
            try:
                import openpyxl
            except ImportError:
                raise ImportError(
                    "openpyxl is required for Excel file support. "
                    "Install it with: pip install openpyxl"
                )
            
            sheet_index = settings.get('sheet_name', 0)
            header_row = settings['header_row'] if settings['header_row'] >= 0 else None
            skip_rows = settings['skip_rows']

            if skip_rows < 0:
                skip_rows = 0
            if sheet_index < 0:
                sheet_index = 0

            read_args = {
                'sheet_name': sheet_index,
                'engine': 'openpyxl'
            }
        
            if skip_rows > 0:
                read_args['skiprows'] = list(range(skip_rows))
            if header_row is not None:
                if skip_rows > 0:
                    if header_row >= skip_rows:
                        read_args['header'] = header_row - skip_rows
                    else:
                        read_args['header'] = None
                else:
                    read_args['header'] = header_row
            else:
                read_args['header'] = None
            
            df = pd.read_excel(file_path, **read_args)
            
            first_stopping_row = self.find_first_stopping_row(df)
            if first_stopping_row < len(df):
                print(f"Stopping data import at row {first_stopping_row} (found empty row or text)")
                df = df.iloc[:first_stopping_row].copy()
                
            return df
            
        except Exception as e:
            print(f"Error loading Excel file {file_path}: {e}")
            try:
                df = pd.read_excel(file_path, header=None, engine='openpyxl')
                first_stopping_row = self.find_first_stopping_row(df)
                if first_stopping_row < len(df):
                    df = df.iloc[:first_stopping_row].copy()
                return df
            except Exception as fallback_error:
                print(f"Excel fallback also failed: {fallback_error}")
                return pd.DataFrame({'Column_0': ['No data available'], 'Column_1': ['Error loading Excel file']})

    def process_time_column(self, df, settings):
        """
        Process or generate time array and determine final dwell time.
        
        Args:
            df (pd.DataFrame): Data frame
            settings (dict): Import settings
            
        Returns:
            tuple: (time_array, final_dwell_time_s)
        """
        time_column = settings.get('time_column')
        use_calculated_dwell = settings.get('use_calculated_dwell', False)
        manual_dwell_ms = settings['dwell_time_ms']
        
        if time_column and time_column in df.columns:
            time_data = df[time_column].values.astype(float)
            time_unit = settings['time_unit']
            if time_unit == 'milliseconds':
                time_data = time_data / 1000.0
            elif time_unit == 'microseconds':
                time_data = time_data / 1000000.0
            elif time_unit == 'nanoseconds':
                time_data = time_data / 1000000000.0
                
            if use_calculated_dwell and len(time_data) > 1:
                time_diffs = np.diff(time_data)
                valid_diffs = time_diffs[time_diffs > 0]
                if len(valid_diffs) > 0:
                    calculated_dwell_time_s = np.median(valid_diffs)
                else:
                    calculated_dwell_time_s = manual_dwell_ms / 1000.0
            else:
                calculated_dwell_time_s = manual_dwell_ms / 1000.0
            
            return time_data, calculated_dwell_time_s
        else:
            dwell_time_s = manual_dwell_ms / 1000.0
            num_points = len(df)
            time_array = np.arange(num_points, dtype=float) * dwell_time_s
            return time_array, dwell_time_s
        
    def find_first_stopping_row(self, df):
        """
        Find the first row that is either empty OR contains words/text.
        
        Args:
            df (pd.DataFrame): Data frame to check
            
        Returns:
            int: Index of first stopping row
        """
        for i in range(len(df)):
            row = df.iloc[i]
            
            is_empty = True
            has_text = False
            
            for val in row:
                if pd.notna(val):  
                    str_val = str(val).strip()
                    if str_val != '': 
                        is_empty = False
                        
                        import re
                        if re.search(r'[a-zA-Z]{2,}', str_val):
                            has_text = True
                            break
            if is_empty or has_text:
                return i
        
        return len(df) 
                    
    def process_isotope_columns(self, df, mappings, settings, final_dwell_time_s):
        """
        Process isotope data columns with final dwell time.
        
        Args:
            df (pd.DataFrame): Data frame
            mappings (dict): Column to isotope mappings
            settings (dict): Import settings
            final_dwell_time_s (float): Final dwell time in seconds
            
        Returns:
            dict: Dictionary of isotope signals
        """
        signals = {}
        data_type = settings['data_type']
        
        for mapping in mappings.values():
            col_name = mapping['column_name']
            isotope = mapping['isotope']
            
            if col_name in df.columns:
                data = df[col_name].values.astype(float)
                if data_type == "Counts per second (CPS)":
                    data = data * final_dwell_time_s
                signals[isotope['mass']] = data
                
        return signals
        
    def create_run_info(self, df, settings, file_path, final_dwell_time_s, file_ext):
        """
        Create run info dictionary for data.
        
        Args:
            df (pd.DataFrame): Data frame
            settings (dict): Import settings
            file_path (str): Path to file
            final_dwell_time_s (float): Final dwell time in seconds
            file_ext (str): File extension
            
        Returns:
            dict: Run information dictionary
        """
        num_points = len(df)
        total_duration_s = (num_points - 1) * final_dwell_time_s if num_points > 1 else 0

        if file_ext in ['.xls', '.xlsx', '.xlsm', '.xlsb']:
            data_type = 'Excel'
        elif file_ext == '.txt':
            data_type = 'Text'
        else:
            data_type = 'CSV'
        
        return {
            'SampleName': Path(file_path).stem,
            'DataType': data_type,
            'OriginalFile': str(file_path),
            'NumDataPoints': num_points,
            'DwellTimeMs': final_dwell_time_s * 1000,
            'UseCalculatedDwell': settings.get('use_calculated_dwell', False),
            'TimeUnit': settings['time_unit'],
            'DataFormat': settings['data_type'],
            'Delimiter': settings.get('delimiter', 'N/A'),
            'Encoding': settings.get('encoding', 'N/A'),
            'SheetName': settings.get('sheet_name', 'N/A'),
            'TotalDurationSeconds': total_duration_s,
            'SegmentInfo': [{
                'AcquisitionPeriodNs': final_dwell_time_s * 1e9 
            }],
            'NumAccumulations1': 1, 
            'NumAccumulations2': 1  
        }

CSVDataProcessThread = DataProcessThread

class FileStructureDialog(QDialog):
    """
    Main dialog for file import with structure configuration - supports CSV, TXT, and Excel.
    """
    
    file_configured = Signal(dict)
    
    def __init__(self, file_paths, parent=None):
        """
        Initialize the file structure dialog.
        
        Args:
            file_paths (list | str): List of file paths or single file path
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.current_file_index = 0
        self.file_data = {}
        self.column_mappings = {}
        self.periodic_table_data = []
        
        if parent and hasattr(parent, 'periodic_table_widget') and parent.periodic_table_widget:
            try:
                self.periodic_table_data = parent.periodic_table_widget.get_elements()
            except:
                pass
        if not self.periodic_table_data:
            try:
                ptw = PeriodicTableWidget()
                self.periodic_table_data = ptw.get_elements()
            except:
                pass
        
        self.setWindowTitle("File Import Configuration")
        self.setModal(True)
        self.resize(1200, 800)
        
        self.setup_ui()
        self.load_first_file()
        
    def setup_ui(self):
        """
        Setup the main UI.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        file_header = self.create_file_header()
        layout.addWidget(file_header)
        
        splitter = QSplitter(Qt.Horizontal)
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 500])
        layout.addWidget(splitter)
        
        button_layout = self.create_button_layout()
        layout.addLayout(button_layout)
        
    def create_file_header(self):
        """
        Create file selection header.
        
        Args:
            None
            
        Returns:
            QFrame: Header widget
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        layout = QHBoxLayout(frame)
        
        layout.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        self.file_combo.addItems([Path(f).name for f in self.file_paths])
        self.file_combo.currentIndexChanged.connect(self.switch_file)
        layout.addWidget(self.file_combo)
        
        layout.addStretch()
        self.file_info_label = QLabel()
        layout.addWidget(self.file_info_label)
        
        return frame
        
    def create_left_panel(self):
        """
        Create left panel with file preview and settings.
        
        Args:
            None
            
        Returns:
            QWidget: Left panel widget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.settings_group = QGroupBox("Import Settings")
        self.settings_layout = QGridLayout(self.settings_group)
        layout.addWidget(self.settings_group)
        
        skip_group = QGroupBox("Skip Rows")
        skip_layout = QHBoxLayout(skip_group)
        skip_layout.addWidget(QLabel("Skip first rows:"))
        self.skip_rows_spin = QSpinBox()
        self.skip_rows_spin.setMinimum(0)
        self.skip_rows_spin.setMaximum(50)
        self.skip_rows_spin.valueChanged.connect(self.reload_preview)
        skip_layout.addWidget(self.skip_rows_spin)
        layout.addWidget(skip_group)
        
        time_group = QGroupBox("Time Configuration")
        time_layout = QGridLayout(time_group)
        
        time_layout.addWidget(QLabel("Time Column:"), 0, 0)
        self.time_column_combo = QComboBox()
        self.time_column_combo.addItem("None - Generate Time")
        self.time_column_combo.currentTextChanged.connect(self.on_time_column_changed)
        time_layout.addWidget(self.time_column_combo, 0, 1)
        
        time_layout.addWidget(QLabel("Time Unit:"), 0, 2)
        self.time_unit_combo = QComboBox()
        self.time_unit_combo.addItems(["seconds", "milliseconds", "microseconds", "nanoseconds"])
        time_layout.addWidget(self.time_unit_combo, 0, 3)
        
        time_layout.addWidget(QLabel("Dwell Time:"), 1, 0)
        self.dwell_method_group = QButtonGroup()
        self.calc_dwell_radio = QRadioButton("Calculate from time data")
        self.manual_dwell_radio = QRadioButton("Manual entry")
        self.manual_dwell_radio.setChecked(True)
        self.dwell_method_group.addButton(self.calc_dwell_radio)
        self.dwell_method_group.addButton(self.manual_dwell_radio)
        self.calc_dwell_radio.toggled.connect(self.on_dwell_method_changed)
        
        dwell_method_layout = QHBoxLayout()
        dwell_method_layout.addWidget(self.calc_dwell_radio)
        dwell_method_layout.addWidget(self.manual_dwell_radio)
        time_layout.addLayout(dwell_method_layout, 1, 1, 1, 2)
        
        time_layout.addWidget(QLabel("Dwell Time (ms):"), 2, 0)
        self.dwell_time_spin = QDoubleSpinBox()
        self.dwell_time_spin.setRange(0.001, 10000)
        self.dwell_time_spin.setValue(0.100)
        self.dwell_time_spin.setDecimals(3)
        time_layout.addWidget(self.dwell_time_spin, 2, 1)
        
        time_layout.addWidget(QLabel("Data Type:"), 2, 2)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Counts", "Counts per second (CPS)"])
        time_layout.addWidget(self.data_type_combo, 2, 3)
        
        layout.addWidget(time_group)
        
        preview_group = QGroupBox("Data Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_table = CSVPreviewTableWidget()
        self.preview_table.setMaximumHeight(300)
        preview_layout.addWidget(self.preview_table)
        
        layout.addWidget(preview_group)
        
        return widget
    
    def setup_delimited_settings(self):
        """
        Setup settings for CSV/TXT files with validation.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            for i in reversed(range(self.settings_layout.count())):
                child = self.settings_layout.itemAt(i)
                if child and child.widget():
                    child.widget().setParent(None)
                    
            self.settings_layout.addWidget(QLabel("Delimiter:"), 0, 0)
            self.delimiter_combo = QComboBox()
            self.delimiter_combo.addItems([",", ";", "\\t", "|", " "])
            self.delimiter_combo.setEditable(True)
            self.delimiter_combo.currentTextChanged.connect(self.reload_preview)
            self.settings_layout.addWidget(self.delimiter_combo, 0, 1)
            
            self.settings_layout.addWidget(QLabel("Encoding:"), 1, 0)
            self.encoding_combo = QComboBox()
            self.encoding_combo.addItems(["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"])
            self.encoding_combo.currentTextChanged.connect(self.reload_preview)
            self.settings_layout.addWidget(self.encoding_combo, 1, 1)
            
        except Exception as e:
            print(f"Error setting up delimited settings: {e}")
        
    def setup_excel_settings(self):
        """
        Setup settings for Excel files with validation.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            for i in reversed(range(self.settings_layout.count())):
                child = self.settings_layout.itemAt(i)
                if child and child.widget():
                    child.widget().setParent(None)
                    
            self.settings_layout.addWidget(QLabel("Sheet:"), 0, 0)
            self.sheet_combo = QComboBox()
            self.populate_sheet_list()
            self.sheet_combo.currentTextChanged.connect(self.reload_preview)
            self.settings_layout.addWidget(self.sheet_combo, 0, 1)
            
            self.delimiter_combo = None
            self.encoding_combo = None
            
        except Exception as e:
            print(f"Error setting up Excel settings: {e}")

    def populate_sheet_list(self):
        """
        Populate sheet list for Excel files with better error handling.
        
        Args:
            None
            
        Returns:
            None
        """
        if not hasattr(self, 'sheet_combo'):
            return
            
        self.sheet_combo.clear()
        
        try:
            file_path = self.file_paths[self.current_file_index]
            sheet_names = []
            try:
                excel_file = pd.ExcelFile(file_path, engine='openpyxl')
                sheet_names = excel_file.sheet_names
            except Exception as e1:
                print(f"Pandas ExcelFile failed: {e1}")
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(file_path, read_only=True)
                    sheet_names = wb.sheetnames
                    wb.close()
                except Exception as e2:
                    print(f"Direct openpyxl failed: {e2}")
                    
            if sheet_names:
                for i, sheet_name in enumerate(sheet_names):
                    self.sheet_combo.addItem(f"{sheet_name} (Sheet {i})")
            else:
                self.sheet_combo.addItem("Sheet1 (Sheet 0)")
                
        except Exception as e:
            self.sheet_combo.addItem("Sheet1 (Sheet 0)")
            print(f"Warning: Could not read Excel sheets from {file_path}: {e}")
        
    def on_time_column_changed(self):
        """
        Handle time column selection change.
        
        Args:
            None
            
        Returns:
            None
        """
        has_time_column = self.time_column_combo.currentIndex() > 0
        self.calc_dwell_radio.setEnabled(has_time_column)
        if not has_time_column:
            self.manual_dwell_radio.setChecked(True)
            self.calc_dwell_radio.setChecked(False)
    
    def on_dwell_method_changed(self):
        """
        Handle dwell time method change.
        
        Args:
            None
            
        Returns:
            None
        """
        manual_enabled = self.manual_dwell_radio.isChecked()
        self.dwell_time_spin.setEnabled(manual_enabled)
        
    def create_right_panel(self):
        """
        Create right panel with column mapping.
        
        Args:
            None
            
        Returns:
            QWidget: Right panel widget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        mapping_group = QGroupBox("Column to Isotope Mapping")
        mapping_layout = QVBoxLayout(mapping_group)
        
        self.current_file_label = QLabel()
        self.current_file_label.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                border: 1px solid #2196F3;
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
                color: #1565c0;
            }
        """)
        mapping_layout.addWidget(self.current_file_label)
        
        instructions = QLabel(
            "1. Select a column from the preview table on the left\n"
            "2. Choose the corresponding isotope below\n"
            "3. Click 'Map Column' to create the mapping\n"
            "4. Use 'Apply to All Files' to copy settings to other files"
        )
        instructions.setStyleSheet("color: #666; margin: 5px;")
        mapping_layout.addWidget(instructions)
        
        self.selection_label = QLabel("No column selected")
        self.selection_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin: 5px;")
        mapping_layout.addWidget(self.selection_label)
        
        self.isotope_matcher = IsotopeMatchingWidget(self.periodic_table_data)
        mapping_layout.addWidget(self.isotope_matcher)
        
        self.map_button = QPushButton("Map Selected Column to Isotope")
        self.map_button.clicked.connect(self.map_column_to_isotope)
        self.map_button.setEnabled(False)
        mapping_layout.addWidget(self.map_button)
        
        layout.addWidget(mapping_group)
        
        self.mappings_group = QGroupBox("Current Mappings")
        mappings_layout = QVBoxLayout(self.mappings_group)
        
        self.mappings_list = QListWidget()
        self.mappings_list.setMaximumHeight(200)
        mappings_layout.addWidget(self.mappings_list)
        
        remove_button = QPushButton("Remove Selected Mapping")
        remove_button.clicked.connect(self.remove_mapping)
        mappings_layout.addWidget(remove_button)
        
        layout.addWidget(self.mappings_group)
        
        auto_detect_button = QPushButton("Auto-Detect Isotopes")
        auto_detect_button.clicked.connect(self.auto_detect_isotopes)
        auto_detect_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(auto_detect_button)
        
        return widget
        
    def create_button_layout(self):
        """
        Create bottom button layout.
        
        Args:
            None
            
        Returns:
            QHBoxLayout: Button layout
        """
        layout = QHBoxLayout()
        
        layout.addStretch()
        
        self.apply_all_button = QPushButton("Apply to All Files")
        self.apply_all_button.clicked.connect(self.apply_to_all_files)
        self.apply_all_button.setEnabled(False)
        self.apply_all_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        layout.addWidget(self.apply_all_button)       
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)
        
        self.import_button = QPushButton("Import Data")
        self.import_button.clicked.connect(self.accept_import)
        self.import_button.setEnabled(False)
        self.import_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        layout.addWidget(self.import_button)
        
        return layout

    def apply_to_all_files(self):
        """
        Apply current file settings and mappings to all other files.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.validate_current_file_for_apply_all():
            return
        
        current_file_name = Path(self.file_paths[self.current_file_index]).name
        other_files = [Path(f).name for i, f in enumerate(self.file_paths) if i != self.current_file_index]
        
        if not other_files:
            QMessageBox.information(self, "No Other Files", "There are no other files to apply settings to.")
            return
            
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Apply to All Files")
        msg.setText(f"Apply settings and mappings from '{current_file_name}' to {len(other_files)} other file(s)?")
        file_list = "\n".join([f"• {name}" for name in other_files[:5]])
        if len(other_files) > 5:
            file_list += f"\n... and {len(other_files) - 5} more files"
        msg.setDetailedText(f"Files that will be updated:\n{file_list}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        if msg.exec() != QMessageBox.Yes:
            return
            
        applied_count = self.perform_apply_to_all()
        QMessageBox.information(
            self, 
            "Settings Applied", 
            f"Successfully applied settings and mappings to {applied_count} file(s)."
        )
        self.validate_configuration()

    def validate_current_file_for_apply_all(self):
        """
        Validate that current file has proper configuration for applying to all.
        
        Args:
            None
            
        Returns:
            bool: True if valid configuration exists
        """
        current_file_mappings = [
            v for k, v in self.column_mappings.items() 
            if v['file_index'] == self.current_file_index
        ]
        
        if not current_file_mappings:
            QMessageBox.warning(
                self, 
                "No Mappings", 
                f"The current file has no column mappings configured.\n\n"
                f"Please configure at least one isotope mapping before using 'Apply to All'."
            )
            return False
            
        if len(self.file_paths) <= 1:
            QMessageBox.information(self, "Single File", "There are no other files to apply settings to.")
            return False
        
        return True

    def perform_apply_to_all(self):
        """
        Perform the actual application of settings to all files.
        
        Args:
            None
            
        Returns:
            int: Number of files successfully applied
        """
        applied_count = 0
        current_settings = self.get_current_file_settings()
        current_mappings = [
            v for k, v in self.column_mappings.items() 
            if v['file_index'] == self.current_file_index
        ]

        for target_file_index in range(len(self.file_paths)):
            if target_file_index == self.current_file_index:
                continue
            
            try:
                success = self.apply_settings_to_file(target_file_index, current_settings, current_mappings)
                if success:
                    applied_count += 1
            except Exception as e:
                print(f"Error applying settings to file {target_file_index}: {e}")
                continue
        
        return applied_count

    def get_current_file_settings(self):
        """
        Get current file's import settings.
        
        Args:
            None
            
        Returns:
            dict: Current settings dictionary
        """
        settings = {}
        
        file_type = self.get_file_type(self.file_paths[self.current_file_index])
        
        if file_type == 'delimited':
            settings.update({
                'delimiter': self.delimiter_combo.currentText() if hasattr(self, 'delimiter_combo') else ',',
                'encoding': self.encoding_combo.currentText() if hasattr(self, 'encoding_combo') else 'utf-8',
            })
        elif file_type == 'excel':
            settings.update({
                'sheet_index': self.sheet_combo.currentIndex() if hasattr(self, 'sheet_combo') else 0,
            })
        
        settings.update({
            'header_row': 0,
            'skip_rows': self.skip_rows_spin.value(),
            'time_column_index': self.time_column_combo.currentIndex(),
            'time_unit': self.time_unit_combo.currentText(),
            'dwell_time_ms': self.dwell_time_spin.value(),
            'use_calculated_dwell': self.calc_dwell_radio.isChecked(),
            'data_type': self.data_type_combo.currentText()
        })
        
        return settings

    def apply_settings_to_file(self, target_file_index, settings, source_mappings):
        """
        Apply settings and mappings to a specific file.
        
        Args:
            target_file_index (int): Index of target file
            settings (dict): Settings to apply
            source_mappings (list): Source mappings to apply
            
        Returns:
            bool: True if successful
        """
        try:
            original_index = self.current_file_index
            self.current_file_index = target_file_index
            self.load_file(self.file_paths[target_file_index])
            self.apply_column_mappings_by_name(target_file_index, source_mappings)
            self.current_file_index = original_index
            self.load_file(self.file_paths[original_index])
            return True
        except Exception as e:
            print(f"Error applying settings to file {target_file_index}: {e}")
            return False

    def apply_column_mappings_by_name(self, target_file_index, source_mappings):
        """
        Apply column mappings to target file by matching column names.
        
        Args:
            target_file_index (int): Index of target file
            source_mappings (list): Source mappings to apply
            
        Returns:
            int: Number of mappings applied
        """
        if not hasattr(self, 'current_df') or self.current_df is None:
            return
        
        target_columns = list(self.current_df.columns)
        applied_mappings = 0
        
        keys_to_remove = [
            k for k in self.column_mappings.keys() 
            if self.column_mappings[k]['file_index'] == target_file_index
        ]
        for key in keys_to_remove:
            del self.column_mappings[key]
        
        for source_mapping in source_mappings:
            source_col_name = source_mapping['column_name']
            
            target_col_index = None
            for i, col_name in enumerate(target_columns):
                if str(col_name).strip() == source_col_name.strip():
                    target_col_index = i
                    break
            
            if target_col_index is None:
                for i, col_name in enumerate(target_columns):
                    if str(col_name).strip().lower() == source_col_name.strip().lower():
                        target_col_index = i
                        break
            
            if target_col_index is None:
                for i, col_name in enumerate(target_columns):
                    col_str = str(col_name).strip().lower()
                    source_str = source_col_name.strip().lower()
                    if (source_str in col_str or col_str in source_str) and len(source_str) > 2:
                        target_col_index = i
                        break
            
            if target_col_index is not None:
                mapping_key = f"{target_file_index}_{target_col_index}"
                self.column_mappings[mapping_key] = {
                    'file_index': target_file_index,
                    'column_index': target_col_index,
                    'column_name': str(target_columns[target_col_index]),
                    'isotope': source_mapping['isotope'].copy()
                }
                applied_mappings += 1
        
        return applied_mappings
        
    def load_first_file(self):
        """
        Load the first file.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.file_paths:
            self.load_file(self.file_paths[0])
            
    def switch_file(self, index):
        """
        Switch to a different file and update mappings display.
        
        Args:
            index (int): File index to switch to
            
        Returns:
            None
        """
        if 0 <= index < len(self.file_paths):
            self.current_file_index = index
            self.load_file(self.file_paths[index])
            self.update_mappings_list()
            self.validate_configuration()
            
    def get_file_type(self, file_path):
        """
        Determine file type from extension.
        
        Args:
            file_path (str): Path to file
            
        Returns:
            str: File type ('delimited', 'excel', or 'unknown')
        """
        ext = Path(file_path).suffix.lower()
        if ext in ['.csv', '.txt']:
            return 'delimited'
        elif ext in ['.xls', '.xlsx', '.xlsm', '.xlsb']:
            return 'excel'
        else:
            return 'unknown'
                
    def load_file(self, file_path):
        """
        Load a file with current settings - enhanced error handling.
        
        Args:
            file_path (str): Path to file to load
            
        Returns:
            None
        """
        try:
            file_type = self.get_file_type(file_path)
            
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")
                
            if file_type == 'delimited':
                self.setup_delimited_settings()
                self.current_df = self.load_delimited_file(file_path)
            elif file_type == 'excel':
                self.setup_excel_settings()
                self.current_df = self.load_excel_file(file_path)
            else:
                raise ValueError(f"Unsupported file type: {Path(file_path).suffix}")
            
            if self.current_df is None or self.current_df.empty:
                raise ValueError("No data could be loaded from file")
                
            self.update_preview()
            self.update_file_info()
            self.update_time_column_options()
            self.update_current_file_indicator()
            self.highlight_mapped_columns()
            
        except Exception as e:
            error_msg = f"Error loading {Path(file_path).name}: {str(e)}"
            print(error_msg)
            
            self.current_df = pd.DataFrame({
                'Error': [f'Could not load file: {Path(file_path).name}'],
                'Reason': [str(e)[:50] + "..." if len(str(e)) > 50 else str(e)]
            })
            
            try:
                self.update_preview()
                self.update_file_info()
            except:
                pass
        
    def load_delimited_file(self, file_path):
        """
        Load CSV or TXT file with robust error handling.
        
        Args:
            file_path (str): Path to file
            
        Returns:
            pd.DataFrame: Loaded data
        """
        try:
            delimiter = getattr(self.delimiter_combo, 'currentText', lambda: ',')() if hasattr(self, 'delimiter_combo') and self.delimiter_combo else ","
            if delimiter == "\\t":
                delimiter = "\t"
            
            skip_rows = self.skip_rows_spin.value()
            encoding = getattr(self.encoding_combo, 'currentText', lambda: 'utf-8')() if hasattr(self, 'encoding_combo') and self.encoding_combo else "utf-8"
            
            read_args = {
                'delimiter': delimiter,
                'encoding': encoding,
                'nrows': 100,
                'on_bad_lines': 'warn'
            }
            
            if skip_rows > 0:
                read_args['skiprows'] = list(range(skip_rows))
                read_args['header'] = 0
            else:
                read_args['header'] = 0
                
            return pd.read_csv(file_path, **read_args)
            
        except Exception as e:
            print(f"Error loading delimited file {file_path}: {e}")
            try:
                return pd.read_csv(file_path, nrows=10, header=None, on_bad_lines='warn')
            except Exception as fallback_error:
                print(f"Fallback also failed: {fallback_error}")
                return pd.DataFrame({'Column_0': ['No data available'], 'Column_1': ['Error loading file']})

    def load_excel_file(self, file_path):
        """
        Load Excel file with comprehensive error handling.
        
        Args:
            file_path (str): Path to Excel file
            
        Returns:
            pd.DataFrame: Loaded data
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for Excel file support. Install it with: pip install openpyxl")
        
        sheet_index = 0
        skip_rows = 0
        
        if hasattr(self, 'sheet_combo') and self.sheet_combo:
            sheet_index = max(0, self.sheet_combo.currentIndex())
        skip_rows = max(0, self.skip_rows_spin.value())
        
        try:
            read_args = {
                'sheet_name': sheet_index,
                'nrows': 100,
                'engine': 'openpyxl'
            }
            
            if skip_rows > 0:
                read_args['skiprows'] = list(range(skip_rows))
                read_args['header'] = 0
            else:
                read_args['header'] = 0
                
            return pd.read_excel(file_path, **read_args)
            
        except Exception as e:
            print(f"Error loading Excel file {file_path}: {e}")
            return pd.DataFrame({'Column_0': ['No data available'], 'Column_1': ['Error loading Excel file']})
                
    def update_current_file_indicator(self):
        """
        Update the current file indicator.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self, 'current_file_label'):
            file_path = self.file_paths[self.current_file_index]
            file_name = Path(file_path).name
            file_type = self.get_file_type(file_path).upper()
            current_mappings = len([k for k, v in self.column_mappings.items() 
                                if v['file_index'] == self.current_file_index])
            self.current_file_label.setText(
                f"Current File: {file_name} ({file_type}) | Mappings: {current_mappings}"
            )

    def highlight_mapped_columns(self):
        """
        Highlight columns that are already mapped for current file.
        
        Args:
            None
            
        Returns:
            None
        """
        for col in range(self.preview_table.columnCount()):
            for row in range(self.preview_table.rowCount()):
                item = self.preview_table.item(row, col)
                if item:
                    item.setBackground(QColor(255, 255, 255))
        
        current_file_mappings = {
            k: v for k, v in self.column_mappings.items() 
            if v['file_index'] == self.current_file_index
        }
        
        for mapping in current_file_mappings.values():
            col_index = mapping['column_index']
            self.preview_table.highlight_column(col_index, QColor(144, 238, 144))

    def reload_preview(self):
        """
        Reload preview with current settings.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self, '_reload_timer'):
            self._reload_timer.stop()
            
        from PySide6.QtCore import QTimer
        self._reload_timer = QTimer()
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._do_reload_preview)
        self._reload_timer.start(300)
        
    def _do_reload_preview(self):
        """
        Actually perform the reload.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            if hasattr(self, 'current_df') and self.file_paths:
                self.load_file(self.file_paths[self.current_file_index])
        except Exception as e:
            print(f"Error in reload preview: {e}")
                
    def update_preview(self):
        """
        Update the preview table.
        
        Args:
            None
            
        Returns:
            None
        """
        if not hasattr(self, 'current_df'):
            return
            
        df = self.current_df
        
        self.preview_table.setRowCount(min(20, len(df)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(col) for col in df.columns])
        
        for row in range(min(20, len(df))):
            for col in range(len(df.columns)):
                value = df.iloc[row, col]
                item = QTableWidgetItem(str(value))
                self.preview_table.setItem(row, col, item)
        
        self.preview_table.itemSelectionChanged.connect(self.on_column_selected)
        self.preview_table.resizeColumnsToContents()
        
    def update_file_info(self):
        """
        Update file information display.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self, 'current_df'):
            rows, cols = self.current_df.shape
            file_size = Path(self.file_paths[self.current_file_index]).stat().st_size / 1024
            file_type = self.get_file_type(self.file_paths[self.current_file_index]).upper()
            self.file_info_label.setText(f"{rows} rows × {cols} columns | {file_size:.1f} KB | {file_type}")
            
    def update_time_column_options(self):
        """
        Update time column dropdown options.
        
        Args:
            None
            
        Returns:
            None
        """
        self.time_column_combo.clear()
        self.time_column_combo.addItem("None - Generate Time")
        
        if hasattr(self, 'current_df'):
            for col in self.current_df.columns:
                self.time_column_combo.addItem(str(col))
                
    def on_column_selected(self):
        """
        Handle column selection in preview table.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            if hasattr(self, '_updating_selection') and self._updating_selection:
                return
                
            self._updating_selection = True
            
            selection_model = self.preview_table.selectionModel()
            if not selection_model:
                return
                
            selected_columns = selection_model.selectedColumns()
            
            if selected_columns:
                col_index = selected_columns[0].column()
                if hasattr(self, 'current_df') and 0 <= col_index < len(self.current_df.columns):
                    col_name = str(self.current_df.columns[col_index])
                    self.selection_label.setText(f"Selected: Column {col_index} - '{col_name}'")
                    self.map_button.setEnabled(True)
                    
                    self.preview_table.blockSignals(True)
                    try:
                        self.preview_table.selectColumn(col_index)
                    finally:
                        self.preview_table.blockSignals(False)
                else:
                    self.selection_label.setText("Invalid column selection")
                    self.map_button.setEnabled(False)
            else:
                self.selection_label.setText("No column selected")
                self.map_button.setEnabled(False)
                
        except Exception as e:
            print(f"Error in column selection: {e}")
            self.selection_label.setText("Error in column selection")
            self.map_button.setEnabled(False)
        finally:
            self._updating_selection = False
                
    def map_column_to_isotope(self):
        """
        Map selected column to selected isotope.
        
        Args:
            None
            
        Returns:
            None
        """
        selection = self.preview_table.selectionModel().selectedColumns()
        if not selection:
            QMessageBox.warning(self, "No Selection", "Please select a column first.")
            return
            
        col_index = selection[0].column()
        col_name = str(self.current_df.columns[col_index])
        
        isotope = self.isotope_matcher.get_selected_isotope()
        if not isotope:
            QMessageBox.warning(self, "No Isotope Selected", "Please select an isotope from the list.")
            return
            
        mapping_key = f"{self.current_file_index}_{col_index}"
        self.column_mappings[mapping_key] = {
            'file_index': self.current_file_index,
            'column_index': col_index,
            'column_name': col_name,
            'isotope': isotope
        }
        
        self.update_mappings_list()
        self.validate_configuration()
        self.preview_table.highlight_column(col_index, QColor(144, 238, 144))
        
    def remove_mapping(self):
        """
        Remove selected mapping.
        
        Args:
            None
            
        Returns:
            None
        """
        current_item = self.mappings_list.currentItem()
        if current_item:
            mapping_key = current_item.data(Qt.UserRole)
            if mapping_key in self.column_mappings:
                del self.column_mappings[mapping_key]
                self.update_mappings_list()
                self.validate_configuration()
                
    def update_mappings_list(self):
        """
        Update the current mappings list.
        
        Args:
            None
            
        Returns:
            None
        """
        self.mappings_list.clear()
        
        current_file_mappings = {
            k: v for k, v in self.column_mappings.items() 
            if v['file_index'] == self.current_file_index
        }
        
        for mapping_key, mapping in current_file_mappings.items():
            isotope = mapping['isotope']
            text = f"Column '{mapping['column_name']}' → {isotope['label']} ({isotope['element_name']})"
            
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, mapping_key)
            self.mappings_list.addItem(item)
        
        if hasattr(self.mappings_group, 'setTitle'):
            file_name = Path(self.file_paths[self.current_file_index]).name
            count = len(current_file_mappings)
            self.mappings_group.setTitle(f"Current Mappings for {file_name} ({count} items)")
                
    def auto_detect_isotopes(self):
        """
        Auto-detect isotopes from column names.
        
        Args:
            None
            
        Returns:
            None
        """
        if not hasattr(self, 'current_df'):
            return
            
        detected_count = 0
        
        selected_time_column = None
        if self.time_column_combo.currentIndex() > 0:
            selected_time_column = self.time_column_combo.currentText()
        
        keys_to_remove = [k for k in self.column_mappings.keys() 
                        if self.column_mappings[k]['file_index'] == self.current_file_index]
        for key in keys_to_remove:
            del self.column_mappings[key]
        
        for col_index, col_name in enumerate(self.current_df.columns):
            col_name_str = str(col_name)
            
            if selected_time_column and col_name_str == selected_time_column:
                continue
                
            isotope = self.detect_isotope_from_name(col_name_str)
            if isotope:
                mapping_key = f"{self.current_file_index}_{col_index}"
                self.column_mappings[mapping_key] = {
                    'file_index': self.current_file_index,
                    'column_index': col_index,
                    'column_name': col_name_str,
                    'isotope': isotope
                }
                detected_count += 1
                self.preview_table.highlight_column(col_index, QColor(173, 216, 230))
                
        self.update_mappings_list()
        self.validate_configuration()
        
        QMessageBox.information(self, "Auto-Detection Complete", 
                            f"Detected {detected_count} isotopes from column names.")
            
    def detect_isotope_from_name(self, col_name):
        """
        Detect isotope from column name.
        
        Args:
            col_name (str): Column name to parse
            
        Returns:
            dict | None: Isotope data dictionary or None if not detected
        """
        cleaned_name = col_name.strip()
        
        patterns = [
            r'(\d+(?:\.\d+)?)([A-Za-z]{1,2})',
            r'([A-Za-z]{1,2})(\d+(?:\.\d+)?)',
            r'([A-Za-z]{1,2})[_\-\s]?(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)[_\-\s]?([A-Za-z]{1,2})',
            r'Mass[_\s]*(\d+(?:\.\d+)?)',
            r'M(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)$',
            r'^(\d+(?:\.\d+)?)(?:[^0-9]|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_name, re.IGNORECASE)
            if match:
                try:
                    group1, group2 = match.groups()
                    
                    if group1.isdigit():
                        mass = float(group1)
                        element = group2.capitalize()
                    else:
                        element = group1.capitalize()
                        mass = float(group2)
                    
                    for element_data in self.periodic_table_data:
                        if element_data['symbol'] == element:
                            for isotope in element_data['isotopes']:
                                if isinstance(isotope, dict):
                                    isotope_mass = isotope['mass']
                                    if abs(isotope_mass - mass) < 1.0:
                                        return {
                                            'symbol': element,
                                            'mass': isotope_mass,
                                            'abundance': isotope.get('abundance', 0),
                                            'label': isotope.get('label', f"{round(mass)}{element}"),
                                            'element_name': element_data['name']
                                        }
                                else:
                                    isotope_mass = isotope
                                    if abs(isotope_mass - mass) < 1.0:
                                        return {
                                            'symbol': element,
                                            'mass': isotope_mass,
                                            'abundance': 0,
                                            'label': f"{round(mass)}{element}",
                                            'element_name': element_data['name']
                                        }
                except (ValueError, IndexError):
                    continue
                    
        return None
        
    def validate_configuration(self):
        """
        Validate the current configuration.
        
        Args:
            None
            
        Returns:
            None
        """
        current_file_mappings = len([
            k for k, v in self.column_mappings.items() 
            if v['file_index'] == self.current_file_index
        ])
        
        total_mappings = len(self.column_mappings)
        files_with_mappings = len(set(
            v['file_index'] for v in self.column_mappings.values()
        ))

        self.apply_all_button.setEnabled(
            current_file_mappings > 0 and len(self.file_paths) > 1
        )
        
        self.import_button.setEnabled(total_mappings > 0)
        
    def get_import_configuration(self):
        """
        Get the complete import configuration.
        
        Args:
            None
            
        Returns:
            dict: Complete import configuration dictionary
        """
        config = {
            'files': [],
            'settings': {
                'delimiter': getattr(self.delimiter_combo, 'currentText', lambda: ',')() if hasattr(self, 'delimiter_combo') else ',',
                'header_row': 0,
                'skip_rows': self.skip_rows_spin.value(),
                'encoding': getattr(self.encoding_combo, 'currentText', lambda: 'utf-8')() if hasattr(self, 'encoding_combo') else 'utf-8',
                'sheet_name': self.sheet_combo.currentIndex() if hasattr(self, 'sheet_combo') else 0,
                'time_column': self.time_column_combo.currentText() if self.time_column_combo.currentIndex() > 0 else None,
                'time_unit': self.time_unit_combo.currentText(),
                'dwell_time_ms': self.dwell_time_spin.value(),
                'use_calculated_dwell': self.calc_dwell_radio.isChecked(),
                'data_type': self.data_type_combo.currentText()
            },
            'mappings': self.column_mappings
        }
        
        for i, file_path in enumerate(self.file_paths):
            file_config = {
                'path': file_path,
                'name': Path(file_path).name,
                'type': self.get_file_type(file_path),
                'mappings': {k: v for k, v in self.column_mappings.items() 
                           if v['file_index'] == i}
            }
            config['files'].append(file_config)
            
        return config
        
    def accept_import(self):
        """
        Accept and emit the import configuration.
        
        Args:
            None
            
        Returns:
            None
        """
        config = self.get_import_configuration()
        self.file_configured.emit(config)
        self.accept()
        
CSVStructureDialog = FileStructureDialog

def show_csv_structure_dialog(file_paths, parent=None):
    """
    Show the file structure dialog and return configuration.
    
    Args:
        file_paths (list | str): File path(s) to configure
        parent (QWidget, optional): Parent widget
        
    Returns:
        dict | None: Configuration dictionary or None if canceled
    """
    dialog = FileStructureDialog(file_paths, parent)
    config = None
    
    def on_configured(cfg):
        nonlocal config
        config = cfg
        
    dialog.file_configured.connect(on_configured)
    
    if dialog.exec() == QDialog.Accepted:
        return config
    return None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    test_files = []
    dialog = FileStructureDialog(test_files)
    dialog.show()
    sys.exit(app.exec())