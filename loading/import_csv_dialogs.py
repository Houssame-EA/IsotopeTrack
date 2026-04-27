from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QProgressDialog, QPushButton, QRadioButton, QButtonGroup, QSizePolicy,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QToolButton, QVBoxLayout, QWidget,
)

from widget.periodic_table_widget import PeriodicTableWidget
from theme import theme, dialog_qss


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DELIMITED_EXTS = {'.csv', '.txt'}
EXCEL_EXTS     = {'.xls', '.xlsx', '.xlsm', '.xlsb'}

PREVIEW_MAX_ROWS = 20
LOAD_SAMPLE_ROWS = 100


_ISOTOPE_RE = re.compile(
    r'(?:Mass[_\s]*|M(?=\d))?'
    r'(?:(\d{1,3})[_\-\s\[\]]*([A-Z][a-z]?)'
    r'|([A-Z][a-z]?)[_\-\s\[\]]*(\d{1,3}))',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data-loading helpers (pure, no Qt)
# ---------------------------------------------------------------------------

def file_type_of(path: str | Path) -> str:
    """Return 'delimited', 'excel', or 'unknown' for a given file path.
    Args:
        path (str | Path): File or directory path.
    Returns:
        str: Result of the operation.
    """
    ext = Path(path).suffix.lower()
    if ext in DELIMITED_EXTS:
        return 'delimited'
    if ext in EXCEL_EXTS:
        return 'excel'
    return 'unknown'


def find_first_stopping_row(df: pd.DataFrame) -> int:
    """
    Return the index of the first row that is empty or contains text-heavy
    cells (2+ consecutive letters).

    Dtype-aware fast path: numeric columns are checked with ``isna()`` (fast),
    and only object columns are subjected to the regex scan. On a 100k × 30
    all-numeric frame this runs in ~5 ms versus ~7 s for a naive per-cell scan.
    Args:
        df (pd.DataFrame): Pandas DataFrame.
    Returns:
        int: Result of the operation.
    """
    if df.empty:
        return 0

    obj_cols = df.select_dtypes(include=['object']).columns
    num_cols = df.columns.difference(obj_cols)

    if len(obj_cols) == 0:
        row_all_nan = df.isna().all(axis=1).to_numpy()
        if not row_all_nan.any():
            return len(df)
        return int(np.argmax(row_all_nan))

    if len(num_cols):
        num_part_nan = df[num_cols].isna().all(axis=1)
    else:
        num_part_nan = pd.Series(True, index=df.index)

    obj_str = (df[obj_cols].astype(str)
                           .apply(lambda s: s.str.strip())
                           .fillna(''))
    obj_lower = obj_str.apply(lambda s: s.str.lower())
    obj_empty = ((obj_str == '') | (obj_lower == 'nan')).all(axis=1)
    obj_text  = obj_str.apply(
        lambda s: s.str.contains(r'[A-Za-z]{2,}', regex=True, na=False)
    ).any(axis=1)

    row_all_empty = num_part_nan & obj_empty
    row_has_text  = obj_text

    bad = (row_all_empty | row_has_text).to_numpy()
    if not bad.any():
        return len(df)
    return int(np.argmax(bad))


# ---------------------------------------------------------------------------
# Preview table with inline isotope-badge column headers
# ---------------------------------------------------------------------------

class CSVPreviewTableWidget(QTableWidget):
    """Themed preview table; column selection enabled for mapping."""

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectColumns)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

    def _apply_theme(self, *_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette
        self.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {p.border};
                background-color: {p.bg_secondary};
                alternate-background-color: {p.bg_tertiary};
                color: {p.text_primary};
                selection-background-color: {p.accent};
                selection-color: {p.text_inverse};
            }}
            QHeaderView::section {{
                background-color: {p.bg_tertiary};
                color: {p.text_primary};
                padding: 5px;
                border: 1px solid {p.border};
                font-weight: bold;
            }}
            QTableWidget::item:selected {{
                background-color: {p.accent};
                color: {p.text_inverse};
            }}
        """)

    def highlight_column(self, column: int, color: QColor | None = None):
        """Tint every cell in ``column`` with ``color`` (default = accent_soft).
        Args:
            column (int): The column.
            color (QColor | None): Colour value.
        """
        if color is None:
            color = QColor(theme.palette.accent_soft)
        for row in range(self.rowCount()):
            item = self.item(row, column)
            if item:
                item.setBackground(color)

    def clear_column_highlight(self, column: int):
        """Reset column cells to the default (alternating) background.
        Args:
            column (int): The column.
        """
        for row in range(self.rowCount()):
            item = self.item(row, column)
            if item:
                item.setBackground(QColor(0, 0, 0, 0))


class IsotopeBadgeBar(QWidget):
    """
    Horizontal strip of one clickable badge per data column, positioned
    directly above the preview table. Each badge shows the current isotope
    mapping (or a faint '+ assign' placeholder) and opens an isotope picker
    popover on click.

    We use a widget strip (rather than custom-painted header labels) because
    QHeaderView does not natively host arbitrary widgets, and this approach
    gives us full theming/hover/popover control with minimal fuss.
    """

    mapping_requested = Signal(int)
    unmap_requested   = Signal(int)

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 4)
        self._layout.setSpacing(2)
        self._badges: list[QToolButton] = []
        self._isotopes: list[dict | None] = []

    def sync_with_columns(self, column_widths: list[int]):
        """Create one badge per column, with widths matching the preview table.
        Args:
            column_widths (list[int]): The column widths.
        """
        for b in self._badges:
            b.setParent(None)
            b.deleteLater()
        self._badges.clear()
        self._isotopes = [None] * len(column_widths)

        for col_idx, w in enumerate(column_widths):
            btn = QToolButton()
            btn.setFixedHeight(28)
            btn.setMinimumWidth(max(w, 60))
            btn.setMaximumWidth(max(w, 60))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _pos, c=col_idx: self._show_context_menu(c))
            btn.clicked.connect(lambda _=False, c=col_idx:
                                self.mapping_requested.emit(c))
            self._layout.addWidget(btn)
            self._badges.append(btn)
            self._refresh_badge(col_idx)

        self._layout.addStretch(1)

    def set_mapping(self, column_index: int, isotope: dict | None):
        """Update the badge for one column (None = unmapped).
        Args:
            column_index (int): The column index.
            isotope (dict | None): The isotope.
        """
        if 0 <= column_index < len(self._isotopes):
            self._isotopes[column_index] = isotope
            self._refresh_badge(column_index)

    def update_widths(self, column_widths: list[int]):
        """Re-apply widths after the preview table resizes its columns.
        Args:
            column_widths (list[int]): The column widths.
        """
        for i, w in enumerate(column_widths):
            if i < len(self._badges):
                self._badges[i].setMinimumWidth(max(w, 60))
                self._badges[i].setMaximumWidth(max(w, 60))

    def _refresh_badge(self, column_index: int):
        """
        Args:
            column_index (int): The column index.
        """
        btn = self._badges[column_index]
        iso = self._isotopes[column_index]
        p = theme.palette
        if iso:
            btn.setText(f"  {iso['label']}  ✕")
            btn.setToolTip(
                f"Mapped to {iso['label']} — {iso['element_name']} "
                f"({iso['mass']:.4f} amu)\n"
                f"Left-click to change · Right-click for options"
            )
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: {p.accent};
                    color: {p.text_inverse};
                    border: 1px solid {p.accent};
                    border-radius: 4px;
                    font-weight: bold;
                    padding: 2px 6px;
                }}
                QToolButton:hover {{ background-color: {p.accent_hover}; }}
            """)
        else:
            btn.setText("＋ assign")
            btn.setToolTip("Click to map this column to an isotope")
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    color: {p.text_muted};
                    border: 1px dashed {p.border};
                    border-radius: 4px;
                    padding: 2px 6px;
                }}
                QToolButton:hover {{
                    color: {p.text_primary};
                    border: 1px dashed {p.accent};
                }}
            """)

    def _show_context_menu(self, column_index: int):
        """
        Args:
            column_index (int): The column index.
        """
        if not (0 <= column_index < len(self._isotopes)):
            return
        iso = self._isotopes[column_index]
        menu = QMenu(self)
        if iso:
            menu.addAction("Change isotope…",
                           lambda: self.mapping_requested.emit(column_index))
            menu.addAction("Unmap",
                           lambda: self.unmap_requested.emit(column_index))
        else:
            menu.addAction("Assign isotope…",
                           lambda: self.mapping_requested.emit(column_index))
        menu.exec(self._badges[column_index].mapToGlobal(
            self._badges[column_index].rect().bottomLeft()))


# ---------------------------------------------------------------------------
# Isotope picker popover (replaces the always-visible IsotopeMatchingWidget)
# ---------------------------------------------------------------------------

class IsotopePickerDialog(QDialog):
    """
    Modal popover for selecting an isotope. Opened from a column badge.
    Pre-filters the list with the column name so the user lands on the
    most likely match when an auto-detection was ambiguous.
    """

    def __init__(self, periodic_table_data: list,
                 initial_filter: str = "", parent=None):
        """
        Args:
            periodic_table_data (list): The periodic table data.
            initial_filter (str): The initial filter.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Isotope")
        self.setModal(True)
        self.resize(380, 480)
        self.periodic_table_data = periodic_table_data
        self._selected: dict | None = None

        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit(initial_filter)
        self.search_box.setPlaceholderText("Element symbol, mass, or name…")
        self.search_box.textChanged.connect(self._filter)
        search_row.addWidget(self.search_box)
        layout.addLayout(search_row)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._accept_current)
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("Select")
        ok_btn.clicked.connect(self._accept_current)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._populate()
        if initial_filter:
            self._filter(initial_filter)

        try:
            self.setStyleSheet(dialog_qss(theme.palette))
        except Exception:
            pass

    def _populate(self):
        self.list.clear()
        isotopes: list[dict] = []
        for element in self.periodic_table_data or []:
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
                    'symbol': symbol, 'mass': mass, 'abundance': abundance,
                    'label': label, 'element_name': element['name'],
                })
        isotopes.sort(key=lambda x: x['mass'])

        for iso in isotopes:
            text = f"{iso['label']} — {iso['element_name']} ({iso['mass']:.4f} amu)"
            if iso['abundance'] > 0:
                text += f"  ·  {iso['abundance']:.1f}%"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, iso)
            self.list.addItem(item)

    def _filter(self, text: str):
        """
        Args:
            text (str): Text string.
        """
        needle = text.lower().strip()
        first_visible = None
        for i in range(self.list.count()):
            item = self.list.item(i)
            iso = item.data(Qt.UserRole)
            hay = f"{iso['symbol']} {iso['element_name']} {iso['label']} {iso['mass']}".lower()
            matches = needle in hay if needle else True
            item.setHidden(not matches)
            if matches and first_visible is None:
                first_visible = i
        if first_visible is not None:
            self.list.setCurrentRow(first_visible)

    def _accept_current(self, *_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        item = self.list.currentItem()
        if item and not item.isHidden():
            self._selected = item.data(Qt.UserRole)
            self.accept()

    def selected_isotope(self) -> dict | None:
        """
        Returns:
            dict | None: Result of the operation.
        """
        return self._selected


# ---------------------------------------------------------------------------
# Data-processing thread (unchanged public API; light internal cleanup)
# ---------------------------------------------------------------------------

class DataProcessThread(QThread):
    """Worker thread that loads CSV/TXT/Excel files per the import config."""

    progress = Signal(int)
    finished = Signal(object, object, object, str, str)
    error    = Signal(str)

    def __init__(self, config, parent=None):
        """
        Args:
            config (Any): Configuration dictionary.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.config = config

    def run(self):
        try:
            total_files = max(1, len(self.config['files']))
            for file_index, file_config in enumerate(self.config['files']):
                try:
                    self.progress.emit(int((file_index / total_files) * 90))
                    result = self.process_file(file_config, file_index)
                    if result:
                        sample_name, sample_data = result
                        self.finished.emit(
                            sample_data['signals'],
                            sample_data['run_info'],
                            sample_data['time_array'],
                            sample_name,
                            sample_data.get('datetime', ''),
                        )
                except Exception as e:
                    self.error.emit(
                        f"Error processing file {file_config['name']}: {e}")
                    continue
            self.progress.emit(100)
        except Exception as e:
            self.error.emit(f"Data processing error: {e}")

    # -- per-file pipeline ------------------------------------------------

    def process_file(self, file_config, file_index):
        """
        Args:
            file_config (Any): The file config.
            file_index (Any): The file index.
        Returns:
            tuple: Result of the operation.
        """
        try:
            file_path = file_config['path']
            settings = self.config['settings']
            ext = Path(file_path).suffix.lower()

            if ext in DELIMITED_EXTS:
                df = self._load_delimited(file_path, settings)
            elif ext in EXCEL_EXTS:
                df = self._load_excel(file_path, settings)
            else:
                raise ValueError(f"Unsupported file format: {ext}")

            sample_name = Path(file_path).stem
            time_array, final_dwell = self._process_time(df, settings)
            signals = self._process_isotopes(
                df, file_config['mappings'], settings, final_dwell)
            run_info = self._run_info(df, settings, file_path, final_dwell, ext)

            return sample_name, {
                'signals': signals,
                'time_array': time_array,
                'run_info': run_info,
                'datetime': '',
            }
        except Exception as e:
            self.error.emit(f"Error processing {file_path}: {e}")
            return None

    def _load_delimited(self, file_path, settings):
        """
        Args:
            file_path (Any): Path to the file.
            settings (Any): Settings dictionary.
        Returns:
            object: Result of the operation.
        """
        delim = settings['delimiter']
        if delim == "\\t":
            delim = "\t"
        df = pd.read_csv(
            file_path,
            delimiter=delim,
            header=settings['header_row'] if settings['header_row'] >= 0 else None,
            skiprows=range(settings['skip_rows']) if settings['skip_rows'] > 0 else None,
            encoding=settings['encoding'],
        )
        stop = find_first_stopping_row(df)
        if stop < len(df):
            df = df.iloc[:stop].copy()
        return df

    def _load_excel(self, file_path, settings):
        """
        Args:
            file_path (Any): Path to the file.
            settings (Any): Settings dictionary.
        Returns:
            object: Result of the operation.
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "openpyxl is required for Excel files. "
                "Install with: pip install openpyxl")

        sheet_index = max(0, settings.get('sheet_name', 0) or 0)
        header_row  = settings['header_row'] if settings['header_row'] >= 0 else None
        skip_rows   = max(0, settings['skip_rows'])

        read_args = {'sheet_name': sheet_index, 'engine': 'openpyxl'}
        if skip_rows > 0:
            read_args['skiprows'] = list(range(skip_rows))
        if header_row is not None:
            read_args['header'] = (header_row - skip_rows
                                   if header_row >= skip_rows else None)
        else:
            read_args['header'] = None

        try:
            df = pd.read_excel(file_path, **read_args)
        except Exception:
            df = pd.read_excel(file_path, header=None, engine='openpyxl')

        stop = find_first_stopping_row(df)
        if stop < len(df):
            df = df.iloc[:stop].copy()
        return df

    def _process_time(self, df, settings):
        """
        Args:
            df (Any): Pandas DataFrame.
            settings (Any): Settings dictionary.
        Returns:
            tuple: Result of the operation.
        """
        time_column = settings.get('time_column')
        use_calc    = settings.get('use_calculated_dwell', False)
        manual_ms   = settings['dwell_time_ms']

        if time_column and time_column in df.columns:
            time_data = df[time_column].values.astype(float)
            unit = settings['time_unit']
            divisor = {'seconds': 1.0, 'milliseconds': 1e3,
                       'microseconds': 1e6, 'nanoseconds': 1e9}.get(unit, 1.0)
            time_data = time_data / divisor

            if use_calc and len(time_data) > 1:
                dwell_s = float(np.median(np.diff(time_data)))
            else:
                dwell_s = manual_ms / 1000.0
            return time_data, dwell_s

        dwell_s = manual_ms / 1000.0
        time_data = np.arange(len(df)) * dwell_s
        return time_data, dwell_s

    def _process_isotopes(self, df, mappings, settings, dwell_s):
        """
        Args:
            df (Any): Pandas DataFrame.
            mappings (Any): The mappings.
            settings (Any): Settings dictionary.
            dwell_s (Any): The dwell s.
        Returns:
            object: Result of the operation.
        """
        signals = {}
        is_cps = settings['data_type'] == "Counts per second (CPS)"
        for mapping in mappings.values():
            col = mapping['column_name']
            iso = mapping['isotope']
            if col in df.columns:
                data = df[col].values.astype(float)
                if is_cps:
                    data = data * dwell_s
                signals[iso['mass']] = data
        return signals

    def _run_info(self, df, settings, file_path, dwell_s, ext):
        """
        Args:
            df (Any): Pandas DataFrame.
            settings (Any): Settings dictionary.
            file_path (Any): Path to the file.
            dwell_s (Any): The dwell s.
            ext (Any): The ext.
        Returns:
            dict: Result of the operation.
        """
        n = len(df)
        duration = (n - 1) * dwell_s if n > 1 else 0
        data_type = ('Excel' if ext in EXCEL_EXTS
                     else 'Text' if ext == '.txt' else 'CSV')
        return {
            'SampleName': Path(file_path).stem,
            'DataType': data_type,
            'OriginalFile': str(file_path),
            'NumDataPoints': n,
            'DwellTimeMs': dwell_s * 1000,
            'UseCalculatedDwell': settings.get('use_calculated_dwell', False),
            'TimeUnit': settings['time_unit'],
            'DataFormat': settings['data_type'],
            'Delimiter': settings.get('delimiter', 'N/A'),
            'Encoding': settings.get('encoding', 'N/A'),
            'SheetName': settings.get('sheet_name', 'N/A'),
            'TotalDurationSeconds': duration,
            'SegmentInfo': [{'AcquisitionPeriodNs': dwell_s * 1e9}],
            'NumAccumulations1': 1,
            'NumAccumulations2': 1,
        }


CSVDataProcessThread = DataProcessThread


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class FileStructureDialog(QDialog):
    """Configure and preview import of one or more CSV/TXT/Excel files."""

    file_configured = Signal(dict)

    # -- init ------------------------------------------------------------

    def __init__(self, file_paths, parent=None):
        """
        Args:
            file_paths (Any): The file paths.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.current_file_index = 0
        self.column_mappings: dict[str, dict] = {}
        self.current_df: pd.DataFrame | None = None
        self._updating_selection = False

        self.periodic_table_data = self._load_periodic_table(parent)

        self.setWindowTitle("File Import Configuration")
        self.setModal(True)
        self.resize(1150, 780)

        self._build_ui()
        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

        if self.file_paths:
            self._load_file(self.file_paths[0])

    @staticmethod
    def _load_periodic_table(parent) -> list:
        """
        Args:
            parent (Any): Parent widget or object.
        Returns:
            list: Result of the operation.
        """
        for getter in (
            lambda: parent.periodic_table_widget.get_elements()
                    if parent and getattr(parent, 'periodic_table_widget', None)
                    else None,
            lambda: PeriodicTableWidget().get_elements(),
        ):
            try:
                data = getter()
                if data:
                    return data
            except Exception:
                continue
        return []

    # -- UI construction -------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(self._build_file_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([750, 380])
        root.addWidget(splitter, 1)

        root.addLayout(self._build_button_row())

    def _build_file_header(self) -> QFrame:
        """
        Returns:
            QFrame: Result of the operation.
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        self._header_frame = frame
        lay = QHBoxLayout(frame)
        lay.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        self.file_combo.addItems([Path(f).name for f in self.file_paths])
        self.file_combo.currentIndexChanged.connect(self._switch_file)
        lay.addWidget(self.file_combo, 1)
        lay.addStretch()
        self.file_info_label = QLabel()
        lay.addWidget(self.file_info_label)
        return frame

    def _build_left_panel(self) -> QWidget:
        """
        Returns:
            QWidget: Result of the operation.
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        # --- Collapsible advanced settings ------------------------------
        self._advanced_toggle = QToolButton()
        self._advanced_toggle.setText("▸ Advanced file settings")
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setChecked(False)
        self._advanced_toggle.setAutoRaise(True)
        self._advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._advanced_toggle.clicked.connect(self._toggle_advanced)
        lay.addWidget(self._advanced_toggle)

        self._advanced_body = QWidget()
        adv = QGridLayout(self._advanced_body)
        adv.setContentsMargins(6, 0, 0, 6)

        adv.addWidget(QLabel("Delimiter:"), 0, 0)
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([",", ";", "\\t", "|", " "])
        self.delimiter_combo.setEditable(True)
        self.delimiter_combo.currentTextChanged.connect(self._debounced_reload)
        adv.addWidget(self.delimiter_combo, 0, 1)

        adv.addWidget(QLabel("Encoding:"), 0, 2)
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(
            ["utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-1"])
        self.encoding_combo.currentTextChanged.connect(self._debounced_reload)
        adv.addWidget(self.encoding_combo, 0, 3)

        adv.addWidget(QLabel("Sheet:"), 1, 0)
        self.sheet_combo = QComboBox()
        self.sheet_combo.currentIndexChanged.connect(self._debounced_reload)
        adv.addWidget(self.sheet_combo, 1, 1)

        adv.addWidget(QLabel("Skip rows:"), 1, 2)
        self.skip_rows_spin = QSpinBox()
        self.skip_rows_spin.setRange(0, 50)
        self.skip_rows_spin.valueChanged.connect(self._debounced_reload)
        adv.addWidget(self.skip_rows_spin, 1, 3)

        self._advanced_body.setVisible(False)
        lay.addWidget(self._advanced_body)

        # --- Time + data-format group (always visible, compact) ---------
        time_group = QGroupBox("Time & Data Format")
        tg = QGridLayout(time_group)

        tg.addWidget(QLabel("Time column:"), 0, 0)
        self.time_column_combo = QComboBox()
        self.time_column_combo.addItem("None — generate from dwell")
        self.time_column_combo.currentTextChanged.connect(self._on_time_column_changed)
        tg.addWidget(self.time_column_combo, 0, 1)

        tg.addWidget(QLabel("Time unit:"), 0, 2)
        self.time_unit_combo = QComboBox()
        self.time_unit_combo.addItems(
            ["seconds", "milliseconds", "microseconds", "nanoseconds"])
        tg.addWidget(self.time_unit_combo, 0, 3)

        self.dwell_method_group = QButtonGroup(self)
        self.calc_dwell_radio   = QRadioButton("Calculate from time data")
        self.manual_dwell_radio = QRadioButton("Manual entry")
        self.manual_dwell_radio.setChecked(True)
        self.dwell_method_group.addButton(self.calc_dwell_radio)
        self.dwell_method_group.addButton(self.manual_dwell_radio)
        self.calc_dwell_radio.toggled.connect(self._on_dwell_method_changed)

        tg.addWidget(QLabel("Dwell time:"), 1, 0)
        dwell_row = QHBoxLayout()
        dwell_row.addWidget(self.calc_dwell_radio)
        dwell_row.addWidget(self.manual_dwell_radio)
        dwell_row.addStretch()
        tg.addLayout(dwell_row, 1, 1, 1, 3)

        tg.addWidget(QLabel("Dwell (ms):"), 2, 0)
        self.dwell_time_spin = QDoubleSpinBox()
        self.dwell_time_spin.setRange(0.001, 10000)
        self.dwell_time_spin.setDecimals(3)
        self.dwell_time_spin.setValue(0.100)
        tg.addWidget(self.dwell_time_spin, 2, 1)

        tg.addWidget(QLabel("Data type:"), 2, 2)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Counts", "Counts per second (CPS)"])
        tg.addWidget(self.data_type_combo, 2, 3)

        lay.addWidget(time_group)

        # --- Preview with inline badge bar above ------------------------
        preview_group = QGroupBox("Preview & column mapping")
        pg = QVBoxLayout(preview_group)

        hint = QLabel(
            "Isotopes are auto-detected from column names. "
            "Click a badge above any column to change or unmap it."
        )
        hint.setWordWrap(True)
        self._instructions_label = hint
        pg.addWidget(hint)

        self.badge_bar = IsotopeBadgeBar()
        self.badge_bar.mapping_requested.connect(self._open_picker_for_column)
        self.badge_bar.unmap_requested.connect(self._unmap_column)
        pg.addWidget(self.badge_bar)

        self.preview_table = CSVPreviewTableWidget()
        self.preview_table.setMinimumHeight(280)
        self.preview_table.itemSelectionChanged.connect(self._on_column_selected)
        self.preview_table.horizontalHeader().sectionResized.connect(
            lambda *_: self._sync_badge_widths())
        pg.addWidget(self.preview_table, 1)

        lay.addWidget(preview_group, 1)
        return w

    def _build_right_panel(self) -> QWidget:
        """
        Returns:
            QWidget: Result of the operation.
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        self.current_file_label = QLabel()
        lay.addWidget(self.current_file_label)

        self.mappings_group = QGroupBox("Current mappings")
        mg = QVBoxLayout(self.mappings_group)

        self.mappings_list = QListWidget()
        self.mappings_list.setMinimumHeight(220)
        mg.addWidget(self.mappings_list, 1)

        row = QHBoxLayout()
        self._remove_button = QPushButton("Remove selected")
        self._remove_button.clicked.connect(self._remove_mapping)
        row.addWidget(self._remove_button)

        self._redetect_button = QPushButton("Re-detect isotopes")
        self._redetect_button.clicked.connect(self._auto_detect_isotopes)
        row.addWidget(self._redetect_button)
        mg.addLayout(row)

        lay.addWidget(self.mappings_group, 1)
        lay.addStretch()
        return w

    def _build_button_row(self) -> QHBoxLayout:
        """
        Returns:
            QHBoxLayout: Result of the operation.
        """
        row = QHBoxLayout()
        row.addStretch()

        self.apply_all_button = QPushButton("Apply to all files")
        self.apply_all_button.clicked.connect(self._apply_to_all_files)
        self.apply_all_button.setEnabled(False)
        row.addWidget(self.apply_all_button)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)

        self.import_button = QPushButton("Import data")
        self.import_button.clicked.connect(self._accept_import)
        self.import_button.setEnabled(False)
        row.addWidget(self.import_button)
        return row

    # -- Theming ---------------------------------------------------------

    def _apply_theme(self, *_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette
        self.setStyleSheet(dialog_qss(p))

        if hasattr(self, '_header_frame'):
            self._header_frame.setStyleSheet(
                f"background-color: {p.bg_tertiary}; "
                f"color: {p.text_primary}; padding: 5px;")

        if hasattr(self, 'current_file_label'):
            self.current_file_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {p.accent_soft};
                    border: 1px solid {p.accent};
                    border-radius: 4px;
                    padding: 5px;
                    font-weight: bold;
                    color: {p.text_primary};
                }}""")

        if hasattr(self, '_instructions_label'):
            self._instructions_label.setStyleSheet(
                f"color: {p.text_secondary}; margin: 2px;")

        if hasattr(self, '_redetect_button'):
            self._redetect_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {p.accent};
                    color: {p.text_inverse};
                    padding: 6px;
                    font-weight: bold;
                    border-radius: 4px;
                    border: 1px solid {p.accent};
                }}
                QPushButton:hover {{ background-color: {p.accent_hover}; }}""")

        if hasattr(self, 'apply_all_button'):
            self.apply_all_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {p.warning};
                    color: {p.text_inverse};
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                    border: 1px solid {p.warning};
                }}
                QPushButton:hover {{ background-color: {p.accent_hover}; }}
                QPushButton:disabled {{
                    background-color: {p.disabled};
                    color: {p.text_muted};
                    border: 1px solid {p.disabled};
                }}""")

        if hasattr(self, 'import_button'):
            self.import_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {p.success};
                    color: {p.text_inverse};
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                    border: 1px solid {p.success};
                }}
                QPushButton:hover {{ background-color: {p.accent_hover}; }}
                QPushButton:disabled {{
                    background-color: {p.disabled};
                    color: {p.text_muted};
                    border: 1px solid {p.disabled};
                }}""")

        if hasattr(self, 'preview_table'):
            soft = QColor(p.accent_soft)
            for row in range(self.preview_table.rowCount()):
                for col in range(self.preview_table.columnCount()):
                    item = self.preview_table.item(row, col)
                    if item is None:
                        continue
                    bg = item.background().color()
                    if (bg.alpha() > 0
                            and bg != QColor(p.bg_secondary)
                            and bg != QColor(p.bg_tertiary)):
                        item.setBackground(soft)

    # -- Advanced disclosure ---------------------------------------------

    def _toggle_advanced(self):
        on = self._advanced_toggle.isChecked()
        self._advanced_body.setVisible(on)
        self._advanced_toggle.setText(
            "▾ Advanced file settings" if on else "▸ Advanced file settings")

    # -- Per-file loading pipeline ---------------------------------------

    def _switch_file(self, index: int):
        """
        Args:
            index (int): Row or item index.
        """
        if 0 <= index < len(self.file_paths):
            self.current_file_index = index
            self._load_file(self.file_paths[index])

    def _load_file(self, file_path: str):
        """Load a file with the current settings; degrade gracefully on error.
        Args:
            file_path (str): Path to the file.
        """
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            ftype = file_type_of(file_path)
            self._update_settings_visibility(ftype)

            if ftype == 'delimited':
                self.current_df = self._load_delimited_preview(file_path)
            elif ftype == 'excel':
                self._populate_sheet_list(file_path)
                self.current_df = self._load_excel_preview(file_path)
            else:
                raise ValueError(f"Unsupported file type: {Path(file_path).suffix}")

            if self.current_df is None or self.current_df.empty:
                raise ValueError("No data could be loaded from file")

            self._refresh_preview()
            self._refresh_file_info()
            self._refresh_time_column_options()
            self._refresh_current_file_indicator()
            self._auto_detect_isotopes(silent=True)
            self._refresh_mapped_columns_highlight()
            self._refresh_mappings_list()
            self._validate_configuration()

        except Exception as e:
            error_msg = f"Error loading {Path(file_path).name}: {e}"
            print(error_msg)
            self.current_df = pd.DataFrame({
                'Error':  [f'Could not load: {Path(file_path).name}'],
                'Reason': [str(e)[:80]],
            })
            try:
                self._refresh_preview()
                self._refresh_file_info()
            except Exception:
                pass

    def _update_settings_visibility(self, ftype: str):
        """Enable the settings relevant to the current file type.
        Args:
            ftype (str): The ftype.
        """
        is_delim = ftype == 'delimited'
        is_xl    = ftype == 'excel'
        self.delimiter_combo.setEnabled(is_delim)
        self.encoding_combo.setEnabled(is_delim)
        self.sheet_combo.setEnabled(is_xl)

    def _populate_sheet_list(self, file_path: str):
        """
        Args:
            file_path (str): Path to the file.
        """
        self.sheet_combo.blockSignals(True)
        try:
            self.sheet_combo.clear()
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True,
                                            data_only=False)
                for name in wb.sheetnames:
                    self.sheet_combo.addItem(name)
                wb.close()
            except Exception:
                self.sheet_combo.addItem("Sheet1")
        finally:
            self.sheet_combo.blockSignals(False)

    def _load_delimited_preview(self, file_path: str) -> pd.DataFrame:
        """
        Args:
            file_path (str): Path to the file.
        Returns:
            pd.DataFrame: Result of the operation.
        """
        delim = self.delimiter_combo.currentText() or ","
        if delim == "\\t":
            delim = "\t"
        encoding = self.encoding_combo.currentText() or "utf-8"
        skip = self.skip_rows_spin.value()

        read_args: dict[str, Any] = {
            'delimiter': delim,
            'encoding': encoding,
            'nrows': LOAD_SAMPLE_ROWS,
            'on_bad_lines': 'warn',
        }
        if skip > 0:
            read_args['skiprows'] = list(range(skip))

        try:
            df = pd.read_csv(file_path, **read_args)
        except UnicodeDecodeError:
            read_args['encoding'] = 'utf-8'
            read_args['encoding_errors'] = 'replace'
            df = pd.read_csv(file_path, **read_args)

        stop = find_first_stopping_row(df)
        if stop < len(df):
            df = df.iloc[:stop].copy()
        return df

    def _load_excel_preview(self, file_path: str) -> pd.DataFrame:
        """
        Args:
            file_path (str): Path to the file.
        Returns:
            pd.DataFrame: Result of the operation.
        """
        sheet = max(0, self.sheet_combo.currentIndex())
        skip  = self.skip_rows_spin.value()
        read_args: dict[str, Any] = {
            'sheet_name': sheet, 'engine': 'openpyxl',
            'nrows': LOAD_SAMPLE_ROWS, 'header': 0,
        }
        if skip > 0:
            read_args['skiprows'] = list(range(skip))
        try:
            df = pd.read_excel(file_path, **read_args)
        except Exception:
            df = pd.read_excel(file_path, header=None, engine='openpyxl',
                               nrows=LOAD_SAMPLE_ROWS)
        stop = find_first_stopping_row(df)
        if stop < len(df):
            df = df.iloc[:stop].copy()
        return df

    # -- Preview rendering ----------------------------------------------

    def _refresh_preview(self):
        if self.current_df is None:
            return
        df = self.current_df
        n_rows = min(PREVIEW_MAX_ROWS, len(df))
        self.preview_table.setRowCount(n_rows)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels(
            [str(c) for c in df.columns])

        for r in range(n_rows):
            for c in range(len(df.columns)):
                self.preview_table.setItem(
                    r, c, QTableWidgetItem(str(df.iloc[r, c])))

        self.preview_table.resizeColumnsToContents()
        self._sync_badge_widths(rebuild=True)

    def _sync_badge_widths(self, rebuild: bool = False):
        """
        Args:
            rebuild (bool): The rebuild.
        """
        if self.current_df is None:
            return
        header = self.preview_table.horizontalHeader()
        widths = [header.sectionSize(i)
                  for i in range(self.preview_table.columnCount())]
        if rebuild:
            self.badge_bar.sync_with_columns(widths)
        else:
            self.badge_bar.update_widths(widths)

    def _refresh_file_info(self):
        if self.current_df is None:
            return
        rows, cols = self.current_df.shape
        size_kb = Path(self.file_paths[self.current_file_index]).stat().st_size / 1024
        ftype   = file_type_of(self.file_paths[self.current_file_index]).upper()
        self.file_info_label.setText(
            f"{rows} rows × {cols} columns  ·  {size_kb:.1f} KB  ·  {ftype}")

    def _refresh_time_column_options(self):
        current = self.time_column_combo.currentText()
        self.time_column_combo.blockSignals(True)
        try:
            self.time_column_combo.clear()
            self.time_column_combo.addItem("None — generate from dwell")
            if self.current_df is not None:
                for c in self.current_df.columns:
                    self.time_column_combo.addItem(str(c))
            idx = self.time_column_combo.findText(current)
            if idx >= 0:
                self.time_column_combo.setCurrentIndex(idx)
        finally:
            self.time_column_combo.blockSignals(False)

    def _refresh_current_file_indicator(self):
        name = Path(self.file_paths[self.current_file_index]).name
        total = len(self.file_paths)
        idx   = self.current_file_index + 1
        self.current_file_label.setText(f"File {idx}/{total}: {name}")

    # -- Selection, time-column, and dwell-method handlers ----------------

    def _on_column_selected(self):
        if self._updating_selection:
            return
        self._updating_selection = True
        try:
            sel = self.preview_table.selectionModel()
            if sel and sel.selectedColumns():
                col_index = sel.selectedColumns()[0].column()
                self.preview_table.blockSignals(True)
                try:
                    self.preview_table.selectColumn(col_index)
                finally:
                    self.preview_table.blockSignals(False)
        finally:
            self._updating_selection = False

    def _on_time_column_changed(self, text: str):
        """
        Args:
            text (str): Text string.
        """
        if self.time_column_combo.currentIndex() > 0:
            self.calc_dwell_radio.setEnabled(True)
            if not self.manual_dwell_radio.isChecked():
                self.calc_dwell_radio.setChecked(True)
        else:
            self.calc_dwell_radio.setEnabled(False)
            self.manual_dwell_radio.setChecked(True)

        self._refresh_time_column_options_if_needed(text)

    def _refresh_time_column_options_if_needed(self, selected_time_col: str):
        """If the time column was previously mapped, remove that mapping.
        Args:
            selected_time_col (str): The selected time col.
        """
        if self.current_df is None or selected_time_col in (
                "", "None — generate from dwell"):
            return
        keys_to_drop = [
            k for k, v in self.column_mappings.items()
            if (v['file_index'] == self.current_file_index
                and v['column_name'] == selected_time_col)
        ]
        for k in keys_to_drop:
            col_idx = self.column_mappings[k]['column_index']
            del self.column_mappings[k]
            self.badge_bar.set_mapping(col_idx, None)
            self.preview_table.clear_column_highlight(col_idx)
        if keys_to_drop:
            self._refresh_mappings_list()
            self._validate_configuration()

    def _on_dwell_method_changed(self):
        self.dwell_time_spin.setEnabled(self.manual_dwell_radio.isChecked())

    # -- Mapping operations ---------------------------------------------

    def _open_picker_for_column(self, column_index: int):
        """Open the isotope picker for ``column_index`` and commit the result.
        Args:
            column_index (int): The column index.
        """
        if self.current_df is None:
            return
        if not (0 <= column_index < len(self.current_df.columns)):
            return

        col_name = str(self.current_df.columns[column_index])

        if self.time_column_combo.currentIndex() > 0 and \
                self.time_column_combo.currentText() == col_name:
            QMessageBox.information(
                self, "Time column",
                f"'{col_name}' is currently set as the time column. "
                "Change the time column in the Time & Data Format panel "
                "before mapping this column to an isotope.")
            return

        dlg = IsotopePickerDialog(
            self.periodic_table_data,
            initial_filter=col_name,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            iso = dlg.selected_isotope()
            if iso:
                self._commit_mapping(column_index, col_name, iso)

    def _commit_mapping(self, column_index: int, column_name: str, isotope: dict):
        """
        Args:
            column_index (int): The column index.
            column_name (str): The column name.
            isotope (dict): The isotope.
        """
        key = f"{self.current_file_index}_{column_index}"
        self.column_mappings[key] = {
            'file_index': self.current_file_index,
            'column_index': column_index,
            'column_name': column_name,
            'isotope': isotope,
        }
        self.badge_bar.set_mapping(column_index, isotope)
        self.preview_table.highlight_column(
            column_index, QColor(theme.palette.success))
        self._refresh_mappings_list()
        self._validate_configuration()

    def _unmap_column(self, column_index: int):
        """
        Args:
            column_index (int): The column index.
        """
        key = f"{self.current_file_index}_{column_index}"
        if key in self.column_mappings:
            del self.column_mappings[key]
            self.badge_bar.set_mapping(column_index, None)
            self.preview_table.clear_column_highlight(column_index)
            self._refresh_mappings_list()
            self._validate_configuration()

    def _remove_mapping(self):
        item = self.mappings_list.currentItem()
        if not item:
            return
        key = item.data(Qt.UserRole)
        if key in self.column_mappings:
            col_idx = self.column_mappings[key]['column_index']
            del self.column_mappings[key]
            self.badge_bar.set_mapping(col_idx, None)
            self.preview_table.clear_column_highlight(col_idx)
            self._refresh_mappings_list()
            self._validate_configuration()

    def _refresh_mappings_list(self):
        self.mappings_list.clear()
        current = {k: v for k, v in self.column_mappings.items()
                   if v['file_index'] == self.current_file_index}
        for key, m in current.items():
            iso = m['isotope']
            text = f"{m['column_name']}  →  {iso['label']}  ({iso['element_name']})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.mappings_list.addItem(item)

        name = Path(self.file_paths[self.current_file_index]).name
        self.mappings_group.setTitle(
            f"Current mappings — {name}  ({len(current)} items)")

    def _refresh_mapped_columns_highlight(self):
        if self.current_df is None:
            return
        for c in range(self.preview_table.columnCount()):
            self.preview_table.clear_column_highlight(c)
        for m in self.column_mappings.values():
            if m['file_index'] != self.current_file_index:
                continue
            col = m['column_index']
            if 0 <= col < self.preview_table.columnCount():
                self.preview_table.highlight_column(
                    col, QColor(theme.palette.success))
                self.badge_bar.set_mapping(col, m['isotope'])

    # -- Auto-detection --------------------------------------------------

    def _auto_detect_isotopes(self, silent: bool = False):
        """Scan column names for isotope patterns and create mappings.
        Args:
            silent (bool): Whether to suppress output.
        """
        if self.current_df is None:
            return

        time_col = (self.time_column_combo.currentText()
                    if self.time_column_combo.currentIndex() > 0 else None)

        stale = [k for k, v in self.column_mappings.items()
                 if v['file_index'] == self.current_file_index]
        for k in stale:
            col_idx = self.column_mappings[k]['column_index']
            del self.column_mappings[k]
            self.badge_bar.set_mapping(col_idx, None)
            self.preview_table.clear_column_highlight(col_idx)

        detected = 0
        for col_idx, col in enumerate(self.current_df.columns):
            col_name = str(col)
            if time_col and col_name == time_col:
                continue
            iso = self._detect_isotope_from_name(col_name)
            if iso:
                self._commit_mapping(col_idx, col_name, iso)
                detected += 1

        self._refresh_mappings_list()
        self._validate_configuration()

        if not silent:
            QMessageBox.information(
                self, "Auto-detection complete",
                f"Detected {detected} isotope(s) from column names.")

    def _detect_isotope_from_name(self, col_name: str) -> dict | None:
        """Match a column name against the isotope regex and the periodic table.
        Args:
            col_name (str): The col name.
        Returns:
            dict | None: Result of the operation.
        """
        if not self.periodic_table_data:
            return None
        m = _ISOTOPE_RE.search(col_name)
        if not m:
            return None

        if m.group(1) and m.group(2):
            mass_str, element = m.group(1), m.group(2)
        elif m.group(3) and m.group(4):
            element, mass_str = m.group(3), m.group(4)
        else:
            return None

        try:
            mass = float(mass_str)
        except ValueError:
            return None
        element = element.capitalize()

        for el_data in self.periodic_table_data:
            if el_data['symbol'] != element:
                continue
            for iso in el_data['isotopes']:
                if isinstance(iso, dict):
                    iso_mass, abundance = iso['mass'], iso.get('abundance', 0)
                    label = iso.get('label', f"{round(iso_mass)}{element}")
                else:
                    iso_mass, abundance = iso, 0
                    label = f"{round(iso_mass)}{element}"
                if abs(iso_mass - mass) < 1.0:
                    return {
                        'symbol': element,
                        'mass': iso_mass,
                        'abundance': abundance,
                        'label': label,
                        'element_name': el_data['name'],
                    }
        return None

    # -- Apply-to-all-files ---------------------------------------------

    def _apply_to_all_files(self):
        current_map = [v for v in self.column_mappings.values()
                       if v['file_index'] == self.current_file_index]
        if not current_map:
            QMessageBox.warning(
                self, "No mappings",
                "Configure at least one mapping before using Apply to all.")
            return
        if len(self.file_paths) <= 1:
            QMessageBox.information(
                self, "Single file", "There are no other files.")
            return

        current_name = Path(self.file_paths[self.current_file_index]).name
        others = [Path(f).name for i, f in enumerate(self.file_paths)
                  if i != self.current_file_index]

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Apply to all files")
        msg.setText(f"Apply mappings from '{current_name}' to "
                    f"{len(others)} other file(s)?")
        detail = "\n".join(f"• {n}" for n in others[:5])
        if len(others) > 5:
            detail += f"\n… and {len(others) - 5} more"
        msg.setDetailedText(f"Files that will be updated:\n{detail}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() != QMessageBox.Yes:
            return

        applied = self._perform_apply_to_all(current_map)
        QMessageBox.information(
            self, "Applied",
            f"Applied mappings to {applied} file(s).")
        self._validate_configuration()

    def _perform_apply_to_all(self, source_mappings: list[dict]) -> int:
        """For each other file, map columns by matching name (case-insensitive).
        Args:
            source_mappings (list[dict]): The source mappings.
        Returns:
            int: Result of the operation.
        """
        applied = 0
        for tgt in range(len(self.file_paths)):
            if tgt == self.current_file_index:
                continue
            try:
                target_cols = self._read_columns_only(self.file_paths[tgt])
            except Exception as e:
                print(f"Cannot read columns of {self.file_paths[tgt]}: {e}")
                continue

            stale = [k for k, v in self.column_mappings.items()
                     if v['file_index'] == tgt]
            for k in stale:
                del self.column_mappings[k]

            for src in source_mappings:
                src_name = src['column_name'].strip()
                idx = self._match_column(src_name, target_cols)
                if idx is not None:
                    key = f"{tgt}_{idx}"
                    self.column_mappings[key] = {
                        'file_index': tgt,
                        'column_index': idx,
                        'column_name': str(target_cols[idx]),
                        'isotope': dict(src['isotope']),
                    }
            applied += 1

        self._refresh_mapped_columns_highlight()
        self._refresh_mappings_list()
        return applied

    @staticmethod
    def _match_column(name: str, columns: list[str]) -> int | None:
        """Find the index of a column matching ``name`` (exact → ci → substring).
        Args:
            name (str): Name string.
            columns (list[str]): The columns.
        Returns:
            int | None: Result of the operation.
        """
        name_s = name.strip()
        for i, c in enumerate(columns):
            if str(c).strip() == name_s:
                return i
        needle = name_s.lower()
        for i, c in enumerate(columns):
            if str(c).strip().lower() == needle:
                return i
        if len(needle) > 2:
            for i, c in enumerate(columns):
                cs = str(c).strip().lower()
                if needle in cs or cs in needle:
                    return i
        return None

    def _read_columns_only(self, file_path: str) -> list[str]:
        """Return the column names of ``file_path`` without loading data.
        Args:
            file_path (str): Path to the file.
        Returns:
            list[str]: Result of the operation.
        """
        ftype = file_type_of(file_path)
        if ftype == 'delimited':
            delim = self.delimiter_combo.currentText() or ","
            if delim == "\\t":
                delim = "\t"
            encoding = self.encoding_combo.currentText() or "utf-8"
            skip = self.skip_rows_spin.value()
            try:
                df = pd.read_csv(file_path, delimiter=delim, encoding=encoding,
                                 nrows=0,
                                 skiprows=range(skip) if skip > 0 else None)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, delimiter=delim, encoding='utf-8',
                                 encoding_errors='replace', nrows=0,
                                 skiprows=range(skip) if skip > 0 else None)
            return [str(c) for c in df.columns]
        elif ftype == 'excel':
            sheet = max(0, self.sheet_combo.currentIndex())
            skip = self.skip_rows_spin.value()
            df = pd.read_excel(file_path, sheet_name=sheet, engine='openpyxl',
                               nrows=0,
                               skiprows=list(range(skip)) if skip > 0 else None)
            return [str(c) for c in df.columns]
        return []

    # -- Reload debouncing ----------------------------------------------

    def _debounced_reload(self, *_):
        """Coalesce rapid settings changes into a single reload.
        Args:
            *_ (Any): Additional positional arguments.
        """
        if not hasattr(self, '_reload_timer'):
            self._reload_timer = QTimer(self)
            self._reload_timer.setSingleShot(True)
            self._reload_timer.timeout.connect(self._do_reload)
        self._reload_timer.start(300)

    def _do_reload(self):
        try:
            if self.file_paths:
                self._load_file(self.file_paths[self.current_file_index])
        except Exception as e:
            print(f"Reload failed: {e}")

    # -- Validation / config emission -----------------------------------

    def _validate_configuration(self):
        current = sum(1 for v in self.column_mappings.values()
                      if v['file_index'] == self.current_file_index)
        total = len(self.column_mappings)
        self.apply_all_button.setEnabled(
            current > 0 and len(self.file_paths) > 1)
        self.import_button.setEnabled(total > 0)

    def _build_import_config(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        ftype_current = file_type_of(self.file_paths[self.current_file_index])
        config: dict[str, Any] = {
            'files': [],
            'settings': {
                'delimiter': (self.delimiter_combo.currentText()
                              if ftype_current == 'delimited' else ','),
                'header_row': 0,
                'skip_rows': self.skip_rows_spin.value(),
                'encoding': (self.encoding_combo.currentText()
                             if ftype_current == 'delimited' else 'utf-8'),
                'sheet_name': (self.sheet_combo.currentIndex()
                               if ftype_current == 'excel' else 0),
                'time_column': (self.time_column_combo.currentText()
                                if self.time_column_combo.currentIndex() > 0
                                else None),
                'time_unit': self.time_unit_combo.currentText(),
                'dwell_time_ms': self.dwell_time_spin.value(),
                'use_calculated_dwell': self.calc_dwell_radio.isChecked(),
                'data_type': self.data_type_combo.currentText(),
            },
            'mappings': self.column_mappings,
        }
        for i, fp in enumerate(self.file_paths):
            config['files'].append({
                'path': fp,
                'name': Path(fp).name,
                'type': file_type_of(fp),
                'mappings': {k: v for k, v in self.column_mappings.items()
                             if v['file_index'] == i},
            })
        return config

    def _accept_import(self):
        self.file_configured.emit(self._build_import_config())
        self.accept()


CSVStructureDialog = FileStructureDialog


def show_csv_structure_dialog(file_paths, parent=None) -> dict | None:
    """Open the import dialog; return the config dict or None if cancelled.
    Args:
        file_paths (Any): The file paths.
        parent (Any): Parent widget or object.
    Returns:
        dict | None: Result of the operation.
    """
    dialog = FileStructureDialog(file_paths, parent)
    config: dict | None = None

    def on_configured(cfg):
        """
        Args:
            cfg (Any): The cfg.
        """
        nonlocal config
        config = cfg

    dialog.file_configured.connect(on_configured)
    return config if dialog.exec() == QDialog.Accepted else None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    test_files: list[str] = []
    dialog = FileStructureDialog(test_files)
    dialog.show()
    sys.exit(app.exec())