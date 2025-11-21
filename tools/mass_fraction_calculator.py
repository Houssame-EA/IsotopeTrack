"""Mass fraction calculator with compound database, sample selection, and molecular weight calculations."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                              QTableWidgetItem, QPushButton, QLabel, QLineEdit,
                              QComboBox, QCheckBox, QGroupBox, QMessageBox,
                              QHeaderView, QSplitter, QTextEdit, QTabWidget,
                              QSpinBox, QDoubleSpinBox, QFrame, QProgressBar, QFileDialog,
                              QListWidget, QListWidgetItem, QWidget)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QColor, QDesktopServices
from PySide6.QtCore import QUrl
import re
import pandas as pd
from pathlib import Path
from functools import reduce
from math import gcd

_ELEMENT_RE = re.compile(r'([A-Z][a-z]?)(\d*(?:\.\d+)?)')

def _parse_formula_to_counts(formula: str) -> dict:
    """
    Parse a chemical formula string into a dict of element -> integer count.
    
    Args:
        formula (str): Chemical formula (e.g., 'TiO2', 'H2O')
        
    Returns:
        dict: Element counts dictionary
    """
    counts = {}
    for el, num in _ELEMENT_RE.findall(str(formula)):
        if num == '' or num is None:
            n = 1
        else:
            try:
                n = int(round(float(num)))
            except Exception:
                n = 1
        counts[el] = counts.get(el, 0) + max(n, 0)
    return {k: v for k, v in counts.items() if v > 0}

def _reduce_counts(counts: dict) -> dict:
    """
    Reduce a composition dict by dividing all counts by their GCD.
    
    Args:
        counts (dict): Element counts dictionary
        
    Returns:
        dict: Reduced element counts
    """
    if not counts:
        return counts
    nums = [abs(int(v)) for v in counts.values() if int(v) != 0]
    if not nums:
        return counts
    g = reduce(gcd, nums)
    if g <= 1:
        return counts
    return {k: v // g for k, v in counts.items()}

def _element_order_in_formula(formula: str):
    """
    Return elements in the order they first appear in the user's typed string.
    
    Args:
        formula (str): Chemical formula
        
    Returns:
        list: Ordered list of element symbols
    """
    order = []
    for el, _ in _ELEMENT_RE.findall(str(formula)):
        if el not in order:
            order.append(el)
    return order

def _signature_from_counts(counts: dict) -> str:
    """
    Order-independent signature used for matching equivalent formulas.
    
    Args:
        counts (dict): Element counts dictionary
        
    Returns:
        str: Canonical signature string
    """
    if not counts:
        return ''
    items = sorted(counts.items(), key=lambda x: x[0])
    return '|'.join(f'{el}{num}' for el, num in items)

def _join_formula_from_counts(counts: dict, prefer_order=None) -> str:
    """
    Build a formula string from counts.
    
    Args:
        counts (dict): Element counts dictionary
        prefer_order (list, optional): Preferred element ordering
        
    Returns:
        str: Formula string
    """
    if not counts:
        return ''
    if prefer_order:
        rest = [e for e in counts.keys() if e not in prefer_order]
        ordered = list(dict.fromkeys(list(prefer_order) + sorted(rest)))
    else:
        ordered = sorted(counts.keys())
    parts = []
    for el in ordered:
        n = counts[el]
        parts.append(el if n == 1 else f'{el}{n}')
    return ''.join(parts)

def canonicalize_preserve_user_order(formula: str) -> str:
    """
    Reduce stoichiometry but preserve the user's element order.
    
    Args:
        formula (str): Chemical formula
        
    Returns:
        str: Canonicalized formula with preserved element order
    """
    counts = _reduce_counts(_parse_formula_to_counts(formula))
    order = _element_order_in_formula(formula)
    return _join_formula_from_counts(counts, prefer_order=order)


class CSVCompoundDatabase:
    """
    Database loader for materials from CSV file with signature-based lookup.
    """
    
    def __init__(self):
        """
        Initialize the compound database.
        
        Args:
            None
            
        Returns:
            None
        """
        self.data = None
        self.formula_to_data = {}         
        self.element_to_compounds = {} 
        self.signature_to_formula = {}    
        self.signature_to_data = {}      
        self.is_loaded = False
        
    def auto_load_csv(self):
        """
        Automatically load CSV database from standard locations.
        
        Args:
            None
            
        Returns:
            bool: True if loaded successfully
        """
        possible_paths = [
            Path("") #data/materials_with_id_and_density.csv
        ]
        for csv_path in possible_paths:
            if csv_path.exists():
                print(f"Found CSV file at: {csv_path}")
                return self.load_csv(csv_path)
        print("No CSV file found in standard locations")
        return False
        
    def load_csv(self, csv_path):
        """
        Load CSV database and build indices (signature-based).
        
        Args:
            csv_path (str or Path): Path to CSV file
            
        Returns:
            bool: True if loaded successfully
        """
        if self.is_loaded:
            return True
        try:
            print(f"Loading CSV from: {csv_path}")
            self.data = pd.read_csv(csv_path)
            print(f"CSV loaded with {len(self.data)} rows")
            
            self.formula_to_data.clear()
            self.element_to_compounds.clear()
            self.signature_to_formula.clear()
            self.signature_to_data.clear()
            
            processed_count = 0
            
            for _, row in self.data.iterrows():
                try:
                    raw_formula = row.get('formula', '')
                    if pd.isna(raw_formula) or not isinstance(raw_formula, str) or not raw_formula.strip():
                        continue
                    raw_formula = raw_formula.strip()

                    density = float(row.get('density', 0)) if pd.notna(row.get('density')) else 0.0

                    material_id = str(row.get('material_id', '')).strip() if pd.notna(row.get('material_id')) else ''
                    mp_url = str(row.get('mp_url', '')).strip() if pd.notna(row.get('mp_url')) else ''
                    if not mp_url and material_id:
                        mp_url = f"https://materialsproject.org/materials/{material_id}"

                    material_data = {
                        'material_id': material_id,
                        'density': density,
                        'formula': raw_formula,
                        'space_group': str(row.get('space_group', '')) if pd.notna(row.get('space_group')) else '',
                        'mp_url': mp_url
                    }

                    self.formula_to_data.setdefault(raw_formula, []).append(material_data)

                    counts = _reduce_counts(_parse_formula_to_counts(raw_formula))
                    if not counts:
                        continue
                    sig = _signature_from_counts(counts)

                    self.signature_to_formula.setdefault(sig, raw_formula)
                    self.signature_to_data.setdefault(sig, []).append(material_data)

                    for element in set(counts.keys()):
                        if element not in self.element_to_compounds:
                            self.element_to_compounds[element] = {}
                        canon_display = self.signature_to_formula[sig]
                        best = self.element_to_compounds[element].get(canon_display, 0.0)
                        chosen = density if density > 0 else best
                        self.element_to_compounds[element][canon_display] = chosen

                    processed_count += 1
                except Exception:
                    continue

            self.is_loaded = True
            total_canon = len(self.signature_to_formula)
            print(f"Database loaded: {processed_count} rows processed, {total_canon} canonical compounds indexed")
            return True
            
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return False

    def _signature_for_formula(self, formula: str) -> str:
        """
        Generate canonical signature for formula.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            str: Canonical signature
        """
        counts = _reduce_counts(_parse_formula_to_counts(formula))
        return _signature_from_counts(counts)

    def get_data_by_formula_or_signature(self, formula: str):
        """
        Return rows matching the canonical signature of the formula.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            list: List of material data dictionaries
        """
        sig = self._signature_for_formula(formula)
        return self.signature_to_data.get(sig, [])

    def best_density_for_formula(self, formula: str) -> float:
        """
        Pick a reasonable density for display from rows sharing the signature.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            float: Best available density value
        """
        rows = self.get_data_by_formula_or_signature(formula)
        for r in rows:
            if r.get('density', 0) > 0:
                return float(r['density'])
        return 0.0

    def best_url_for_formula(self, formula: str) -> str:
        """
        Pick a URL for the compound from available data.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            str: Materials Project URL
        """
        rows = self.get_data_by_formula_or_signature(formula)
        for r in rows:
            url = (r.get('mp_url') or '').strip()
            if url:
                return url
        for r in rows:
            mid = (r.get('material_id') or '').strip()
            if mid:
                return f"https://materialsproject.org/materials/{mid}"
        canon = canonicalize_preserve_user_order(formula)
        return f"https://materialsproject.org/?search={canon}"

    def get_compounds_for_element(self, element):
        """
        Get canonical compounds containing the element.
        
        Args:
            element (str): Element symbol
            
        Returns:
            list: List of compound dictionaries with formula, density, display_text
        """
        if element not in self.element_to_compounds:
            return []
        compounds = []
        for display_formula, dens in self.element_to_compounds[element].items():
            if dens > 0:
                display_text = f"{display_formula} ({dens:.3f} g/cm³)"
            else:
                display_text = display_formula
            compounds.append({'formula': display_formula, 'density': float(dens), 'display_text': display_text})
        compounds.sort(key=lambda x: x['formula'])
        return compounds

    def get_material_data(self, formula):
        """
        Get rows matching the exact raw formula string.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            list: List of material data dictionaries
        """
        return self.formula_to_data.get(formula, [])


class FormulaComboBox(QComboBox):
    """
    Editable combobox for chemical formulas with auto-canonicalization.
    """
    
    formula_selected = Signal(str, float)
    
    def __init__(self, element, csv_database, parent=None):
        """
        Initialize the formula combo box.
        
        Args:
            element (str): Element symbol
            csv_database (CSVCompoundDatabase): Database instance
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.element = element
        self.csv_database = csv_database
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText("Type a formula (e.g., TiO2)")
        self._programmatic = False
        self._all_items = []

        self.setup_compounds()

        self.activated[int].connect(self.on_item_activated)
        self.lineEdit().editingFinished.connect(self.on_editing_finished)
        self.lineEdit().textChanged.connect(self._on_text_changed)

    def setup_compounds(self):
        """
        Populate with element and canonical compounds.
        
        Args:
            None
            
        Returns:
            None
        """
        self._all_items.clear()
        self._all_items.append({'display_text': self.element, 'formula': self.element})
        if self.csv_database.is_loaded:
            for compound in self.csv_database.get_compounds_for_element(self.element):
                self._all_items.append({'display_text': compound['display_text'], 'formula': compound['formula']})
        self._rebuild_items(self._all_items)
        self._set_editor_text(self.element)

    def _rebuild_items(self, items):
        """
        Rebuild dropdown items list.
        
        Args:
            items (list): List of item dictionaries
            
        Returns:
            None
        """
        self.blockSignals(True)
        self.clear()
        for it in items:
            self.addItem(it['display_text'], it['formula'])
        self.blockSignals(False)

    def filter_to_formula(self, user_canon_formula: str):
        """
        Show only the one canonical formula in the dropdown.
        
        Args:
            user_canon_formula (str): Canonicalized formula
            
        Returns:
            None
        """
        dens = self.csv_database.best_density_for_formula(user_canon_formula)
        display = f"{user_canon_formula} ({dens:.3f} g/cm³)" if dens > 0 else user_canon_formula
        self._rebuild_items([{'display_text': display, 'formula': user_canon_formula}])
        self._set_editor_text(user_canon_formula)

    def reset_items(self):
        """
        Restore the full list.
        
        Args:
            None
            
        Returns:
            None
        """
        self._rebuild_items(self._all_items)

    def _set_editor_text(self, text: str):
        """
        Set editor text programmatically.
        
        Args:
            text (str): Text to set
            
        Returns:
            None
        """
        self._programmatic = True
        self.lineEdit().setText(text)
        self._programmatic = False

    def current_formula(self) -> str:
        """
        Return the user-preserved canonical formula based on editor text.
        
        Args:
            None
            
        Returns:
            str: Canonicalized formula
        """
        text = (self.lineEdit().text() or '').strip()
        if not text:
            return self.element
        return canonicalize_preserve_user_order(text)

    def _on_text_changed(self, text: str):
        """
        Handle text changed event.
        
        Args:
            text (str): New text
            
        Returns:
            None
        """
        if self._programmatic:
            return
        if not (text or '').strip():
            self.reset_items()

    def on_item_activated(self, index: int):
        """
        Handle dropdown item selection.
        
        Args:
            index (int): Selected item index
            
        Returns:
            None
        """
        picked_formula = self.itemData(index)
        if not isinstance(picked_formula, str) or not picked_formula:
            picked_formula = (self.lineEdit().text() or '').strip()

        user_canon = canonicalize_preserve_user_order(picked_formula)
        dens = self.csv_database.best_density_for_formula(user_canon)
        self._set_editor_text(user_canon)

        counts = _reduce_counts(_parse_formula_to_counts(user_canon))
        if len(counts.keys()) >= 2:
            self.filter_to_formula(user_canon)
        else:
            self.reset_items()

        self.formula_selected.emit(user_canon, dens)

    def on_editing_finished(self):
        """
        Handle editing finished event.
        
        Args:
            None
            
        Returns:
            None
        """
        if self._programmatic:
            return
        typed = (self.lineEdit().text() or '').strip()
        if not typed:
            self._set_editor_text(self.element)
            self.reset_items()
            self.formula_selected.emit(self.element, 0.0)
            return

        user_canon = canonicalize_preserve_user_order(typed)
        dens = self.csv_database.best_density_for_formula(user_canon)
        self._set_editor_text(user_canon)

        counts = _reduce_counts(_parse_formula_to_counts(user_canon))
        if len(counts.keys()) >= 2:
            self.filter_to_formula(user_canon)
        else:
            self.reset_items()

        self.formula_selected.emit(user_canon, dens)


class CheckableListItem(QWidget):
    """
    Custom widget for list items with checkboxes.
    """
    
    def __init__(self, sample_name, parent=None):
        """
        Initialize checkable list item.
        
        Args:
            sample_name (str): Name of the sample
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.sample_name = sample_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        
        self.label = QLabel(sample_name)
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addStretch()
        
    def is_checked(self):
        """
        Check if item is selected.
        
        Args:
            None
            
        Returns:
            bool: True if checked
        """
        return self.checkbox.isChecked()
        
    def set_checked(self, checked):
        """
        Set checkbox state.
        
        Args:
            checked (bool): New checkbox state
            
        Returns:
            None
        """
        self.checkbox.setChecked(checked)


class MassFractionCalculator(QDialog):
    """
    Mass fraction calculator with sample selection and molecular weight calculations.
    """
    
    mass_fractions_updated = Signal(dict)
    
    def __init__(self, selected_isotopes, periodic_table_widget, parent=None):
        """
        Initialize the mass fraction calculator.
        
        Args:
            selected_isotopes (dict): Dictionary of selected isotopes
            periodic_table_widget: Periodic table widget reference
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.selected_isotopes = selected_isotopes
        self.periodic_table_widget = periodic_table_widget
        self.parent_window = parent
        self.mass_fractions = {}
        self.densities = {}
        self.molecular_weights = {}
        
        self.available_samples = []
        if parent and hasattr(parent, 'sample_to_folder_map'):
            self.available_samples = list(parent.sample_to_folder_map.keys())
        
        self.csv_database = getattr(parent, '_cached_csv_database', None)
        if self.csv_database is None:
            self.csv_database = CSVCompoundDatabase()
            self.csv_database.auto_load_csv()
            if hasattr(parent, '__dict__'):
                parent._cached_csv_database = self.csv_database
        
        self.periodic_table_data = periodic_table_widget.get_elements() if periodic_table_widget else []
        
        self.setWindowTitle("Mass Fraction Calculator")
        self.setFixedSize(1500, 700)
        
        self.setup_ui()
        self.populate_table()
        self.restore_previous_state()
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        main_layout = QHBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QGroupBox("Sample Selection")
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        sample_controls = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_samples)
        sample_controls.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_samples)
        sample_controls.addWidget(select_none_btn)
        
        left_layout.addLayout(sample_controls)
        
        sample_list_label = QLabel(f"Available Samples ({len(self.available_samples)}):")
        sample_list_label.setStyleSheet("font-weight: bold; margin: 5px 0px;")
        left_layout.addWidget(sample_list_label)
        
        self.sample_list = QListWidget()
        self.sample_list.setMaximumHeight(400)
        
        for sample_name in self.available_samples:
            item = QListWidgetItem()
            item_widget = CheckableListItem(sample_name)
            item.setSizeHint(item_widget.sizeHint())
            
            self.sample_list.addItem(item)
            self.sample_list.setItemWidget(item, item_widget)
        
        left_layout.addWidget(self.sample_list)
        
        apply_group = QGroupBox("Apply Options")
        apply_layout = QVBoxLayout(apply_group)
        
        self.apply_selected_radio = QCheckBox("Apply to selected samples only")
        self.apply_selected_radio.setChecked(True)
        apply_layout.addWidget(self.apply_selected_radio)
        
        self.apply_all_radio = QCheckBox("Apply to all samples (global)")
        apply_layout.addWidget(self.apply_all_radio)
        
        self.apply_selected_radio.toggled.connect(
            lambda checked: self.apply_all_radio.setChecked(not checked) if checked else None
        )
        self.apply_all_radio.toggled.connect(
            lambda checked: self.apply_selected_radio.setChecked(not checked) if checked else None
        )
        
        left_layout.addWidget(apply_group)
        left_layout.addStretch()
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Mass Fraction Calculator")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        if self.csv_database.is_loaded:
            status_text = f"Materials database: {len(self.csv_database.signature_to_formula)} canonical compounds loaded"
            status_style = "color: #28a745; font-size: 12px; font-weight: bold;"
        else:
            status_text = "Materials database: Not found"
            status_style = "color: #ffc107; font-size: 12px; font-weight: bold;"
        
        self.db_status_label = QLabel(status_text)
        self.db_status_label.setStyleSheet(status_style)
        header_layout.addWidget(self.db_status_label)
        
        if not self.csv_database.is_loaded:
            load_btn = QPushButton("Load CSV")
            load_btn.clicked.connect(self.manual_load_csv)
            header_layout.addWidget(load_btn)
        
        right_layout.addLayout(header_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        headers = [
            'Element',
            'Compound Formula',
            'Mass Fraction',
            'Molecular Weight\n(g/mol)',
            'Element Density\n(g/cm³)',
            'Compound Density\n(g/cm³)',
            'Structure'
        ]
        self.table.setHorizontalHeaderLabels(headers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 160)
        self.table.setColumnWidth(6, 110)
        
        right_layout.addWidget(self.table)
        
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Pure Elements")
        reset_btn.clicked.connect(self.reset_to_default)
        button_layout.addWidget(reset_btn)
        
        calculate_btn = QPushButton("Calculate All Mass Fractions")
        calculate_btn.clicked.connect(self.calculate_all_mass_fractions)
        button_layout.addWidget(calculate_btn)
        
        button_layout.addStretch()
        
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        apply_btn.clicked.connect(self.apply_mass_fractions)
        button_layout.addWidget(apply_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        right_layout.addLayout(button_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 1200])
        
        main_layout.addWidget(splitter)
    
    def select_all_samples(self):
        """
        Select all samples in the list.
        
        Args:
            None
            
        Returns:
            None
        """
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            widget = self.sample_list.itemWidget(item)
            if widget:
                widget.set_checked(True)
    
    def select_no_samples(self):
        """
        Deselect all samples in the list.
        
        Args:
            None
            
        Returns:
            None
        """
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            widget = self.sample_list.itemWidget(item)
            if widget:
                widget.set_checked(False)
    
    def get_selected_samples(self):
        """
        Get list of selected sample names.
        
        Args:
            None
            
        Returns:
            list: List of selected sample names
        """
        selected = []
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            widget = self.sample_list.itemWidget(item)
            if widget and widget.is_checked():
                selected.append(widget.sample_name)
        return selected
    
    def save_current_state(self):
        """
        Save current state to parent window for persistence.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.parent_window:
            return
            
        state = {
            'mass_fractions': {},
            'densities': {},
            'molecular_weights': {},
            'formulas': {},
            'selected_samples': self.get_selected_samples(),
            'apply_to_all': self.apply_all_radio.isChecked()
        }
        
        for row in range(self.table.rowCount()):
            element_item = self.table.item(row, 0)
            if element_item:
                element = element_item.text()
                
                formula_combo = self.table.cellWidget(row, 1)
                if formula_combo:
                    state['formulas'][element] = formula_combo.current_formula()
                
                mf_item = self.table.item(row, 2)
                if mf_item:
                    try:
                        state['mass_fractions'][element] = float(mf_item.text())
                    except:
                        state['mass_fractions'][element] = 1.0
                
                mw_item = self.table.item(row, 3)
                if mw_item:
                    try:
                        state['molecular_weights'][element] = float(mw_item.text())
                    except:
                        pass
                
                density_item = self.table.item(row, 5)
                if density_item:
                    try:
                        state['densities'][element] = float(density_item.text())
                    except:
                        pass
        
        self.parent_window._mass_fraction_calculator_state = state
        
    def get_molecular_weight_for_formula(self, formula):
        """
        Calculate molecular weight from formula using periodic table data.
        
        Args:
            formula (str): Chemical formula
            
        Returns:
            float or None: Molecular weight in g/mol
        """
        try:
            counts = _reduce_counts(_parse_formula_to_counts(formula))
            if not counts:
                return None
                
            total_mass = 0.0
            for el, n in counts.items():
                ed = self.get_element_by_symbol(el)
                if ed:
                    m = float(ed['mass']) * n
                    total_mass += m
                else:
                    return None
                    
            return total_mass if total_mass > 0 else None
            
        except Exception:
            return None
    
    def restore_previous_state(self):
        """
        Restore previous state from parent window.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.parent_window or not hasattr(self.parent_window, '_mass_fraction_calculator_state'):
            return
            
        state = self.parent_window._mass_fraction_calculator_state
        
        if 'apply_to_all' in state:
            self.apply_all_radio.setChecked(state['apply_to_all'])
            self.apply_selected_radio.setChecked(not state['apply_to_all'])
        
        if 'selected_samples' in state:
            selected_samples = set(state['selected_samples'])
            for i in range(self.sample_list.count()):
                item = self.sample_list.item(i)
                widget = self.sample_list.itemWidget(item)
                if widget:
                    widget.set_checked(widget.sample_name in selected_samples)
        
        formulas = state.get('formulas', {})
        for row in range(self.table.rowCount()):
            element_item = self.table.item(row, 0)
            if element_item:
                element = element_item.text()
                
                if element in formulas:
                    formula_combo = self.table.cellWidget(row, 1)
                    if formula_combo:
                        saved_formula = formulas[element]
                        formula_combo._set_editor_text(saved_formula)
                        
                        density = self.csv_database.best_density_for_formula(saved_formula)
                        self.on_compound_selected(row, saved_formula, density)
    
    def closeEvent(self, event):
        """
        Save state when dialog is closed.
        
        Args:
            event (QCloseEvent): Close event
            
        Returns:
            None
        """
        self.save_current_state()
        super().closeEvent(event)
    
    def reject(self):
        """
        Save state when dialog is cancelled.
        
        Args:
            None
            
        Returns:
            None
        """
        self.save_current_state()
        super().reject()
    
    def manual_load_csv(self):
        """
        Manually load CSV database file.
        
        Args:
            None
            
        Returns:
            None
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if file_path:
            if self.csv_database.load_csv(file_path):
                self.setup_ui()
                self.populate_table()
                QMessageBox.information(self, "Success", "Database loaded!")
        
    def populate_table(self):
        """
        Populate the element table with data.
        
        Args:
            None
            
        Returns:
            None
        """
        sorted_elements = []
        for element, isotopes in self.selected_isotopes.items():
            element_data = self.get_element_by_symbol(element)
            if element_data:
                sorted_elements.append((element_data['atomic_number'], element, element_data))
        
        sorted_elements.sort()
        self.table.setRowCount(len(sorted_elements))
        
        for row, (atomic_number, element, element_data) in enumerate(sorted_elements):
            element_item = QTableWidgetItem(element)
            element_item.setFlags(element_item.flags() & ~Qt.ItemIsEditable)
            element_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, element_item)
            
            formula_combo = FormulaComboBox(element, self.csv_database, self)
            formula_combo.formula_selected.connect(lambda f, d, r=row: self.on_compound_selected(r, f, d))
            self.table.setCellWidget(row, 1, formula_combo)
            
            mf_item = QTableWidgetItem("1.000000")
            mf_item.setFlags(mf_item.flags() & ~Qt.ItemIsEditable)
            mf_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, mf_item)
            
            atomic_mass = float(element_data.get('mass', 0))
            mw_item = QTableWidgetItem(f"{atomic_mass:.6f}")
            mw_item.setFlags(mw_item.flags() & ~Qt.ItemIsEditable)
            mw_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, mw_item)
            
            element_density = float(element_data.get('density', 0) or 0)
            ed_item = QTableWidgetItem(f"{element_density:.6f}")
            ed_item.setFlags(ed_item.flags() & ~Qt.ItemIsEditable)
            ed_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, ed_item)
            
            cd_item = QTableWidgetItem(f"{element_density:.6f}")
            cd_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, cd_item)

            open_btn = QPushButton("Open")
            open_btn.setToolTip("Open structure page for current compound")
            open_btn.clicked.connect(lambda _, r=row: self.open_structure_for_row(r))
            self.table.setCellWidget(row, 6, open_btn)
    
    def on_compound_selected(self, row, formula, density_from_csv):
        """
        Handle compound selection and update table row.
        
        Args:
            row (int): Table row index
            formula (str): Selected formula
            density_from_csv (float): Density from database
            
        Returns:
            None
        """
        self.calculate_mass_fraction_for_formula(row, formula)
        self.calculate_molecular_weight_for_formula(row, formula)

        counts = _reduce_counts(_parse_formula_to_counts(formula))
        if len(counts.keys()) <= 1:
            element_item = self.table.item(row, 0)
            if element_item:
                ed = self.get_element_by_symbol(element_item.text())
                d = float(ed.get('density', 0) or 0) if ed else 0.0
            else:
                d = 0.0
        else:
            d = float(density_from_csv or 0.0)

        density_item = QTableWidgetItem(f"{d:.6f}")
        density_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, density_item)
    
    def get_element_by_symbol(self, symbol):
        """
        Get element data by symbol.
        
        Args:
            symbol (str): Element symbol
            
        Returns:
            dict or None: Element data dictionary
        """
        for element in self.periodic_table_data:
            if element['symbol'] == symbol:
                return element
        return None
    
    def _current_formula_in_row(self, row: int) -> str:
        """
        Get current formula from row.
        
        Args:
            row (int): Table row index
            
        Returns:
            str: Current formula string
        """
        combo = self.table.cellWidget(row, 1)
        if not combo:
            return ''
        return combo.current_formula()
    
    def calculate_mass_fraction_for_formula(self, row, formula):
        """
        Calculate mass fraction of the row's element within the formula.
        
        Args:
            row (int): Table row index
            formula (str): Chemical formula
            
        Returns:
            None
        """
        element_item = self.table.item(row, 0)
        if not element_item:
            return
        element = element_item.text()

        try:
            counts = _reduce_counts(_parse_formula_to_counts(formula))
            if not counts:
                mf = 1.0
            else:
                total_mass = 0.0
                target_mass = 0.0
                for el, n in counts.items():
                    ed = self.get_element_by_symbol(el)
                    if ed:
                        m = float(ed['mass']) * n
                        total_mass += m
                        if el == element:
                            target_mass += m
                mf = (target_mass / total_mass) if (total_mass > 0 and target_mass > 0) else 1.0

            item = QTableWidgetItem(f"{mf:.6f}")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item)
        except Exception as e:
            print(f"Error calculating mass fraction: {e}")
    
    def calculate_molecular_weight_for_formula(self, row, formula):
        """
        Calculate and display molecular weight for the formula.
        
        Args:
            row (int): Table row index
            formula (str): Chemical formula
            
        Returns:
            None
        """
        try:
            molecular_weight = self.get_molecular_weight_for_formula(formula)
            if molecular_weight is not None:
                mw_text = f"{molecular_weight:.6f}"
            else:
                element_item = self.table.item(row, 0)
                if element_item:
                    element_data = self.get_element_by_symbol(element_item.text())
                    if element_data:
                        mw_text = f"{float(element_data.get('mass', 0)):.6f}"
                    else:
                        mw_text = "0.000000"
                else:
                    mw_text = "0.000000"
            
            item = QTableWidgetItem(mw_text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item)
        except Exception as e:
            print(f"Error calculating molecular weight: {e}")
    
    def calculate_all_mass_fractions(self):
        """
        Calculate mass fractions and molecular weights for all rows.
        
        Args:
            None
            
        Returns:
            None
        """
        for row in range(self.table.rowCount()):
            formula = self._current_formula_in_row(row)
            if formula:
                self.calculate_mass_fraction_for_formula(row, formula)
                self.calculate_molecular_weight_for_formula(row, formula)
    
    def reset_to_default(self):
        """
        Reset all elements to pure element state.
        
        Args:
            None
            
        Returns:
            None
        """
        for row in range(self.table.rowCount()):
            element_item = self.table.item(row, 0)
            formula_combo = self.table.cellWidget(row, 1)
            if element_item and formula_combo:
                element = element_item.text()
                element_data = self.get_element_by_symbol(element)
                
                formula_combo._set_editor_text(element)
                formula_combo.reset_items()
                formula_combo.formula_selected.emit(element, 0.0)
                
                mf_item = QTableWidgetItem("1.000000")
                mf_item.setFlags(mf_item.flags() & ~Qt.ItemIsEditable)
                mf_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, mf_item)
                
                if element_data:
                    atomic_mass = float(element_data.get('mass', 0))
                    mw_item = QTableWidgetItem(f"{atomic_mass:.6f}")
                else:
                    mw_item = QTableWidgetItem("0.000000")
                mw_item.setFlags(mw_item.flags() & ~Qt.ItemIsEditable)
                mw_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, mw_item)
                
                d = float(element_data.get('density', 0) or 0) if element_data else 0.0
                density_item = QTableWidgetItem(f"{d:.6f}")
                density_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 5, density_item)
    
    def open_structure_for_row(self, row: int):
        """
        Open the structure page for the currently selected compound in this row.
        
        Args:
            row (int): Table row index
            
        Returns:
            None
        """
        formula = self._current_formula_in_row(row)
        if not formula:
            QMessageBox.warning(self, "No compound", "Please choose a compound first.")
            return
        url = self.csv_database.best_url_for_formula(formula)
        if not url:
            url = f"https://materialsproject.org/?search={formula}"
        QDesktopServices.openUrl(QUrl(url))
    
    def apply_mass_fractions(self):
        """
        Apply mass fractions and close dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        selected_samples = self.get_selected_samples()
        apply_to_all = self.apply_all_radio.isChecked()
        
        if not apply_to_all and not selected_samples:
            QMessageBox.warning(self, "No Samples Selected", 
                              "Please select at least one sample or choose 'Apply to all samples'.")
            return
        
        for row in range(self.table.rowCount()):
            element_item = self.table.item(row, 0)
            mass_fraction_item = self.table.item(row, 2)
            molecular_weight_item = self.table.item(row, 3)
            density_item = self.table.item(row, 5)
            
            if element_item and mass_fraction_item:
                element = element_item.text()
                try:
                    self.mass_fractions[element] = float(mass_fraction_item.text())
                except Exception:
                    self.mass_fractions[element] = 1.0
                
                if molecular_weight_item:
                    try:
                        self.molecular_weights[element] = float(molecular_weight_item.text())
                    except Exception:
                        pass
                        
                if density_item:
                    try:
                        self.densities[element] = float(density_item.text())
                    except Exception:
                        pass
        
        self.save_current_state()
        
        self.mass_fractions_updated.emit({
            'mass_fractions': self.mass_fractions,
            'densities': self.densities,
            'molecular_weights': self.molecular_weights,
            'apply_to_all': apply_to_all,
            'selected_samples': selected_samples if not apply_to_all else []
        })
        self.accept()