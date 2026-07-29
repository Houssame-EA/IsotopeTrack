from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractScrollArea, QApplication, QComboBox, QDialog, QDoubleSpinBox,
    QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QRadioButton,
    QButtonGroup, QSizePolicy, QSplitter, QTableView, QToolButton,
    QVBoxLayout, QWidget,
)

from widget.periodic_table_widget import PeriodicTableWidget
from tools.theme import theme, dialog_qss
from loading.csv_preview_model import (
    DELIMITED_EXTS, EXCEL_EXTS, INITIAL_VISIBLE_ROWS, LazyPreviewModel,
    build_row_source, describe_delimiter, file_type_of, find_first_stopping_row,
    read_columns_only, sniff_delimited_settings,
)
from loading.import_exclusions import (
    SCOPE_FILE, ExclusionManager, apply_exclusions,
)
from loading.file_list_panel import FileListPanel
import logging
_itk_log = logging.getLogger("IsotopeTrack.loading.import_csv_dialogs")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREVIEW_MAX_ROWS = INITIAL_VISIBLE_ROWS


_ISOTOPE_RE = re.compile(
    r'(?:Mass[_\s]*|M(?=\d))?'
    r'(?:(\d{1,3})[_\-\s\[\]]*([A-Z][a-z]?)'
    r'|([A-Z][a-z]?)[_\-\s\[\]]*(\d{1,3}))',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Preview table with inline isotope-badge column headers
# ---------------------------------------------------------------------------

class CSVPreviewTableWidget(QTableView):
    """Themed preview view over a lazily loaded model.

    Rows arrive as the user scrolls: the view asks the model for more whenever
    the viewport nears the bottom, and the model reads the next block from disk.
    Right-clicking a column or row header offers the keep/remove actions.

    Signals:
        columnMenuRequested: Emitted with a column position and a global point.
        rowMenuRequested: Emitted with a list of row numbers and a global point.
    """

    columnMenuRequested = Signal(int, object)
    rowMenuRequested = Signal(object, object)

    def __init__(self, parent=None):
        """Configure selection behaviour, headers and theming."""
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectItems)
        self.setSelectionMode(QTableView.ExtendedSelection)
        self.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(True)
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.setMinimumWidth(420)

        header = self.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_column_menu)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsClickable(True)
        header.setHighlightSections(True)

        rows = self.verticalHeader()
        rows.setContextMenuPolicy(Qt.CustomContextMenu)
        rows.customContextMenuRequested.connect(self._on_row_menu)
        rows.setDefaultSectionSize(22)
        rows.setSectionsClickable(True)
        rows.setHighlightSections(True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_body_menu)

        self.horizontalScrollBar().valueChanged.connect(self._on_scrolled_right)

        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

    def _on_scrolled_right(self, value: int):
        """Reveal further columns when the view nears its right edge.

        Qt fetches more rows on its own but has no column equivalent, so the
        horizontal scrollbar drives that half explicitly.

        Args:
            value (int): Current horizontal scrollbar position.
        """
        model = self.preview_model()
        if model is None or not model.can_fetch_more_columns():
            return
        bar = self.horizontalScrollBar()
        if bar.maximum() <= 0:
            return
        if value >= bar.maximum() - bar.pageStep() // 2:
            model.fetch_more_columns()

    def fit_columns(self):
        """Size columns to their contents within sensible bounds.

        Unbounded fitting lets one long text column push the table wider than
        the screen, which drags the whole dialog with it. Clamping keeps the
        table inside its pane and lets it scroll instead.
        """
        self.resizeColumnsToContents()
        header = self.horizontalHeader()
        for section in range(header.count()):
            header.resizeSection(
                section, max(48, min(header.sectionSize(section), 220)))

    def ensure_columns_fill_viewport(self):
        """Reveal enough columns to cover the visible width.

        Without this a narrow file would leave the right of the table blank on
        a wide window, with no scrollbar to trigger the usual reveal.
        """
        model = self.preview_model()
        if model is None:
            return
        guard = 0
        while (model.can_fetch_more_columns()
               and self.horizontalScrollBar().maximum() <= 0
               and guard < 20):
            model.fetch_more_columns()
            self.fit_columns()
            guard += 1

    def selected_targets(self) -> tuple[set[int], set[int]]:
        """Return the column positions and row numbers the selection covers.

        Whole columns and whole rows can be picked at the same time, so both
        sets can come back populated. A partial drag across cells is read as a
        row selection, which is what people mean when they sweep over a band of
        bad readings. Selecting every column is read as columns only, so
        ``Ctrl+A`` does not also mean "remove every row".

        Returns:
            tuple[set[int], set[int]]: Column positions and zero-based row numbers.
        """
        selection = self.selectionModel()
        model = self.preview_model()
        if selection is None or model is None:
            return set(), set()

        columns = {i.column() for i in selection.selectedColumns()
                   if i.column() < model.real_column_count()}
        rows = {i.row() for i in selection.selectedRows()
                if i.row() < model.real_row_count()}

        if columns and len(columns) >= model.real_column_count():
            rows = set()
        if not columns and not rows:
            rows = {i.row() for i in selection.selectedIndexes()
                    if i.row() < model.real_row_count()}
        return columns, rows

    def cleanup(self):
        """Disconnect the theme signal and release the model's file handle."""
        try:
            theme.themeChanged.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            _itk_log.debug("Preview theme signal already disconnected")
        model = self.model()
        if isinstance(model, LazyPreviewModel):
            model.close()

    def preview_model(self) -> LazyPreviewModel | None:
        """Return the lazy model backing the view, if one is set."""
        model = self.model()
        return model if isinstance(model, LazyPreviewModel) else None

    def _on_column_menu(self, pos):
        """Relay a header right-click as a column menu request.

        Args:
            pos: Position within the horizontal header.
        """
        section = self.horizontalHeader().logicalIndexAt(pos)
        if section >= 0:
            self.columnMenuRequested.emit(
                section, self.horizontalHeader().mapToGlobal(pos))

    def _on_row_menu(self, pos):
        """Relay a row-header right-click as a row menu request.

        Args:
            pos: Position within the vertical header.
        """
        section = self.verticalHeader().logicalIndexAt(pos)
        if section < 0:
            return
        selected = sorted({i.row() for i in self.selectionModel().selectedRows()})
        rows = selected if section in selected else [section]
        self.rowMenuRequested.emit(rows, self.verticalHeader().mapToGlobal(pos))

    def _on_body_menu(self, pos):
        """Relay a right-click inside the table as a column menu request.

        Args:
            pos: Position within the viewport.
        """
        index = self.indexAt(pos)
        if index.isValid():
            self.columnMenuRequested.emit(
                index.column(), self.viewport().mapToGlobal(pos))

    def _apply_theme(self, *_):
        """Restyle the view and its headers for the active palette."""
        p = theme.palette
        self.setStyleSheet(f"""
            QTableView {{
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
            QHeaderView::section:vertical {{
                font-weight: normal;
                color: {p.text_muted};
                padding: 2px 6px;
            }}
            QTableView::item:selected {{
                background-color: {p.accent};
                color: {p.text_inverse};
            }}
        """)
        model = self.preview_model()
        if model is not None:
            model.set_muted_colour(QColor(p.text_muted))


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
        """Create the empty strip and its layout."""
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 4)
        self._layout.setSpacing(0)
        self._badges: list[QToolButton] = []
        self._isotopes: list[dict | None] = []
        self._widths: list[int] = []
        self._leading = 0

    def set_leading_offset(self, pixels: int):
        """Indent the strip so badge one sits over preview column one.

        The preview reserves a gutter on the left for its row numbers, and
        without the same indent every badge would sit one gutter-width left of
        the column it belongs to.

        Args:
            pixels (int): Width of the preview's row-number gutter.
        """
        self._leading = max(0, int(pixels))
        self._layout.setContentsMargins(self._leading, 0, 0, 4)

    def sync_with_columns(self, column_widths: list[int]):
        """Create one badge per column, matching the preview's column widths.

        Args:
            column_widths (list[int]): Width in pixels of each preview column.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._badges.clear()
        self._isotopes = [None] * len(column_widths)
        self._widths = list(column_widths)

        for col_idx, w in enumerate(column_widths):
            btn = QToolButton()
            btn.setFixedHeight(26)
            btn.setFixedWidth(max(w, 24))
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
        """Update the badge for one column.

        Args:
            column_index (int): Position of the column.
            isotope (dict | None): Isotope record, or None when unmapped.
        """
        if 0 <= column_index < len(self._isotopes):
            self._isotopes[column_index] = isotope
            self._refresh_badge(column_index)

    def update_widths(self, column_widths: list[int]):
        """Re-apply widths after the preview table resizes its columns.

        Args:
            column_widths (list[int]): Width in pixels of each preview column.
        """
        self._widths = list(column_widths)
        for i, w in enumerate(column_widths):
            if i < len(self._badges):
                self._badges[i].setFixedWidth(max(w, 24))
                self._refresh_badge(i)

    def _label_for(self, column_index: int, isotope: dict | None) -> str:
        """Return badge text that fits the column it sits above.

        Args:
            column_index (int): Position of the column.
            isotope (dict | None): Isotope record, or None when unmapped.

        Returns:
            str: Text short enough to render without being elided to nonsense.
        """
        width = (self._widths[column_index]
                 if column_index < len(self._widths) else 60)
        if isotope is None:
            return "＋" if width < 68 else "＋ assign"
        label = str(isotope['label'])
        if width < 44:
            return "●"
        if width < 78:
            return label
        return f"{label}  ✕"

    def _refresh_badge(self, column_index: int):
        """Restyle one badge to match its mapping state.

        Args:
            column_index (int): Position of the column.
        """
        btn = self._badges[column_index]
        iso = self._isotopes[column_index]
        p = theme.palette
        btn.setText(self._label_for(column_index, iso))
        if iso:
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
            btn.setToolTip("Click to map this column to an isotope")
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    color: {p.text_muted};
                    border: 1px dashed {p.border};
                    border-radius: 4px;
                    padding: 1px 2px;
                }}
                QToolButton:hover {{
                    color: {p.text_primary};
                    border: 1px dashed {p.accent};
                }}
            """)

    def _show_context_menu(self, column_index: int):
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
            _itk_log.exception("Handled exception in __init__")

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
        item = self.list.currentItem()
        if item and not item.isHidden():
            self._selected = item.data(Qt.UserRole)
            self.accept()

    def selected_isotope(self) -> dict | None:
        return self._selected


# ---------------------------------------------------------------------------
# Apply-target picker
# ---------------------------------------------------------------------------

class ApplyTargetsDialog(QDialog):
    """Tick the files a setup should be pushed to.

    Everything starts ticked, so confirming without touching anything applies
    to the whole batch. Unticking is how a batch that needs two different
    setups gets them: apply one setup to some files, then another to the rest.
    """

    def __init__(self, names, source_name: str, preselected=None, parent=None):
        """Build the checklist of candidate files.

        Args:
            names: ``(index, filename)`` pairs for every file that could be
                updated.
            source_name (str): Name of the file whose setup is being copied.
            preselected: Indices to tick, or None to tick everything.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self.setWindowTitle("Apply to files")
        self.setModal(True)
        self.resize(380, 460)
        self._names = list(names)

        layout = QVBoxLayout(self)

        heading = QLabel(
            f"Give these files the setup from <b>{source_name}</b>: its header "
            "row, removed columns and rows, and isotope mappings. Each file is "
            "then checked for isotopes of its own.")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self.list = QListWidget()
        for index, name in self._names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            ticked = preselected is None or index in set(preselected)
            item.setCheckState(Qt.Checked if ticked else Qt.Unchecked)
            item.setData(Qt.UserRole, index)
            self.list.addItem(item)
        self.list.itemChanged.connect(self._refresh_state)
        layout.addWidget(self.list, 1)

        picks = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_all(True))
        picks.addWidget(select_all)
        select_none = QPushButton("Select none")
        select_none.clicked.connect(lambda: self._set_all(False))
        picks.addWidget(select_none)
        picks.addStretch()
        layout.addLayout(picks)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.apply_button = QPushButton("Apply")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.accept)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)

        self._refresh_state()
        try:
            self.setStyleSheet(dialog_qss(theme.palette))
        except Exception:
            _itk_log.debug("Could not style the apply picker", exc_info=True)

    def selected_indexes(self) -> list[int]:
        """Return the positions of the ticked files.

        Returns:
            list[int]: Files the caller should update.
        """
        chosen = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() == Qt.Checked:
                chosen.append(item.data(Qt.UserRole))
        return chosen

    def _set_all(self, ticked: bool):
        """Tick or untick every file at once.

        Args:
            ticked (bool): True to select all, False to select none.
        """
        self.list.blockSignals(True)
        try:
            for row in range(self.list.count()):
                self.list.item(row).setCheckState(
                    Qt.Checked if ticked else Qt.Unchecked)
        finally:
            self.list.blockSignals(False)
        self._refresh_state()

    def _refresh_state(self, *_):
        """Keep the Apply button in step with how many files are ticked."""
        count = len(self.selected_indexes())
        self.apply_button.setEnabled(count > 0)
        self.apply_button.setText(
            f"Apply to {count} file{'s' if count != 1 else ''}"
            if count else "Apply")


# ---------------------------------------------------------------------------
# Column keep/remove panel
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Data-processing thread (unchanged public API; light internal cleanup)
# ---------------------------------------------------------------------------

class DataProcessThread(QThread):
    """Worker thread that loads CSV/TXT/Excel files per the import config."""

    progress = Signal(int)
    finished = Signal(object, object, object, str, str)
    error    = Signal(str)

    def __init__(self, config, parent=None):
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
                    _itk_log.exception("Handled exception in run")
                    self.error.emit(
                        f"Error processing file {file_config['name']}: {e}")
                    continue
            self.progress.emit(100)
        except Exception as e:
            _itk_log.exception("Handled exception in run")
            self.error.emit(f"Data processing error: {e}")

    # -- per-file pipeline ------------------------------------------------

    def process_file(self, file_config, file_index):
        file_path = file_config.get('path', '<unknown>')
        try:
            settings = dict(self.config['settings'])
            for key, target in (('delimiter', 'delimiter'),
                                ('encoding', 'encoding'),
                                ('sheet_index', 'sheet_name'),
                                ('time_column', 'time_column'),
                                ('time_unit', 'time_unit'),
                                ('dwell_time_ms', 'dwell_time_ms'),
                                ('use_calculated_dwell', 'use_calculated_dwell'),
                                ('data_type', 'data_type')):
                if key in file_config:
                    settings[target] = file_config[key]
            ext = Path(file_path).suffix.lower()

            if ext in DELIMITED_EXTS:
                df = self._load_delimited(file_path, settings)
            elif ext in EXCEL_EXTS:
                df = self._load_excel(file_path, settings)
            else:
                raise ValueError(f"Unsupported file format: {ext}")

            df = apply_exclusions(
                df,
                file_config.get('excluded_columns', ()),
                file_config.get('excluded_rows', ()),
            )
            if df.empty:
                raise ValueError(
                    "Every row was removed from this file; "
                    "restore some rows before importing.")

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
            _itk_log.exception("Handled exception in process_file")
            self.error.emit(f"Error processing {file_path}: {e}")
            return None

    def _load_delimited(self, file_path, settings):
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
        try:
            import importlib
            importlib.import_module('openpyxl')
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
            _itk_log.exception("Handled exception in _load_excel")
            df = pd.read_excel(file_path, header=None, engine='openpyxl')

        stop = find_first_stopping_row(df)
        if stop < len(df):
            df = df.iloc[:stop].copy()
        return df

    def _process_time(self, df, settings):
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
            'SheetName': settings.get('sheet_label',
                                      settings.get('sheet_name', 'N/A')),
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
        super().__init__(parent)
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.current_file_index = 0
        self.column_mappings: dict[str, dict] = {}
        self._updating_selection = False
        self._current_columns: list[str] = []
        self._load_failed: set[int] = set()
        self._detected: dict[int, dict] = {}
        self._params: dict[int, dict] = {}
        self._loading_settings = False

        self.exclusions = ExclusionManager(len(self.file_paths), self)
        self.exclusions.changed.connect(self._on_exclusions_changed)

        self.periodic_table_data = self._load_periodic_table(parent)

        self.setWindowTitle("File Import Configuration")
        self.setModal(True)
        self.setMinimumSize(880, 560)
        self.resize(1150, 780)

        self._build_ui()
        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

        if self.file_paths:
            self._load_file(self.file_paths[0])
            QTimer.singleShot(0, self._load_all_thumbnails)

    def closeEvent(self, event):
        """Disconnect theme signals before closing to allow garbage collection."""
        try:
            theme.themeChanged.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            _itk_log.debug("Dialog theme signal already disconnected")
        for name in ('preview_table', 'file_list'):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.cleanup()
        super().closeEvent(event)

    @staticmethod
    def _load_periodic_table(parent) -> list:
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
                _itk_log.exception("Handled exception in _load_periodic_table")
                continue
        return []

    # -- UI construction -------------------------------------------------

    def _build_ui(self):
        """Lay the dialog out as a wide preview beside a narrow side panel."""
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([860, 280])
        root.addWidget(splitter, 1)

        root.addLayout(self._build_button_row())

    def _build_left_panel(self) -> QWidget:
        """Build the preview and the time settings beneath it."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        lay.addWidget(self._build_preview_group(), 1)
        lay.addWidget(self._build_time_group())
        return w

    def _build_time_group(self) -> QGroupBox:
        """Build the time and data-format controls with the live row readout."""
        group = QGroupBox("Time and data format")
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        tg = QGridLayout(group)
        tg.setContentsMargins(8, 4, 8, 6)
        tg.setVerticalSpacing(4)

        tg.addWidget(QLabel("Time column:"), 0, 0)
        self.time_column_combo = QComboBox()
        self.time_column_combo.addItem("None — generate from dwell")
        self.time_column_combo.currentTextChanged.connect(self._on_time_column_changed)
        tg.addWidget(self.time_column_combo, 0, 1)

        tg.addWidget(QLabel("Time unit:"), 0, 2)
        self.time_unit_combo = QComboBox()
        self.time_unit_combo.addItems(
            ["seconds", "milliseconds", "microseconds", "nanoseconds"])
        self.time_unit_combo.currentTextChanged.connect(self._store_params)
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
        self.dwell_time_spin.valueChanged.connect(self._store_params)
        tg.addWidget(self.dwell_time_spin, 2, 1)

        tg.addWidget(QLabel("Data type:"), 2, 2)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Counts", "Counts per second (CPS)"])
        self.data_type_combo.currentTextChanged.connect(self._store_params)
        tg.addWidget(self.data_type_combo, 2, 3)

        self._effective_label = QLabel()
        self._effective_label.setToolTip(
            "What this file contributes to the import once removed rows and "
            "columns are taken out")
        tg.addWidget(self._effective_label, 3, 0, 1, 4)
        return group

    def _build_preview_group(self) -> QGroupBox:
        """Build the preview table, its badge strip and the selection toolbar."""
        group = QGroupBox("Preview and column mapping")
        pg = QVBoxLayout(group)
        pg.setContentsMargins(8, 4, 8, 6)
        pg.setSpacing(4)

        hint = QLabel(
            "Select cells, or click column and row headers to take whole ones, "
            "then press Remove selected. Click a badge to change an isotope."
        )
        hint.setWordWrap(True)
        self._instructions_label = hint
        pg.addWidget(hint)

        pg.addLayout(self._build_structure_toolbar())

        self.badge_bar = IsotopeBadgeBar()
        self.badge_bar.mapping_requested.connect(self._open_picker_for_column)
        self.badge_bar.unmap_requested.connect(self._unmap_column)
        pg.addWidget(self.badge_bar)

        self.preview_table = CSVPreviewTableWidget()
        self.preview_table.setMinimumHeight(300)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding,
                                         QSizePolicy.Expanding)
        self.preview_table.columnMenuRequested.connect(self._show_column_menu)
        self.preview_table.rowMenuRequested.connect(self._show_row_menu)
        self.preview_table.horizontalHeader().sectionResized.connect(
            lambda *_: self._sync_badge_widths())
        pg.addWidget(self.preview_table, 1)

        self._row_status_label = QLabel()
        pg.addWidget(self._row_status_label)
        return group

    def _build_structure_toolbar(self) -> QHBoxLayout:
        """Build the removal, undo, redo, scope and load-all controls."""
        row = QHBoxLayout()
        row.setSpacing(6)

        self.remove_button = QPushButton("Remove selected")
        self.remove_button.setEnabled(False)
        self.remove_button.setShortcut(QKeySequence.Delete)
        self.remove_button.clicked.connect(self._remove_selection)
        row.addWidget(self.remove_button)

        self.restore_button = QPushButton("Restore all")
        self.restore_button.setEnabled(False)
        self.restore_button.setToolTip(
            "Put back every removed row and column")
        self.restore_button.clicked.connect(self._restore_everything)
        row.addWidget(self.restore_button)

        self.detect_button = QPushButton("Detect isotopes")
        self.detect_button.setToolTip(
            "Read the column names of this file and assign the isotopes they "
            "look like. Nothing is assigned until you ask for it.")
        self.detect_button.clicked.connect(self._auto_detect_isotopes)
        row.addWidget(self.detect_button)

        self._undo_shortcut = QShortcut(QKeySequence.Undo, self)
        self._undo_shortcut.activated.connect(self._undo_exclusion)
        self._redo_shortcut = QShortcut(QKeySequence.Redo, self)
        self._redo_shortcut.activated.connect(self._redo_exclusion)

        row.addSpacing(8)
        self.sheet_label = QLabel("Sheet:")
        self.sheet_label.setVisible(False)
        row.addWidget(self.sheet_label)
        self.sheet_combo = QComboBox()
        self.sheet_combo.setVisible(False)
        self.sheet_combo.setMinimumWidth(110)
        self.sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        row.addWidget(self.sheet_combo)

        row.addStretch()

        self.load_all_button = QPushButton("Load all rows")
        self.load_all_button.setToolTip(
            "Read the rest of the file into the preview now instead of "
            "waiting for scrolling to pull it in")
        self.load_all_button.clicked.connect(self._load_all_rows)
        row.addWidget(self.load_all_button)
        return row

    def _build_right_panel(self) -> QWidget:
        """Build the side panel: the file list above the mapping list."""
        w = QWidget()
        w.setMinimumWidth(230)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.file_list = FileListPanel(self.file_paths)
        self.file_list.currentChanged.connect(self._switch_file)
        self.file_list.selectionChanged.connect(self._refresh_apply_button)
        lay.addWidget(self.file_list, 1)

        self.mappings_group = QGroupBox("Current mappings")
        mg = QVBoxLayout(self.mappings_group)
        mg.setContentsMargins(8, 4, 8, 6)

        self.mappings_list = QListWidget()
        self.mappings_list.setToolTip(
            "Isotopes are detected from the column names. "
            "Click a badge above the preview to change one.")
        mg.addWidget(self.mappings_list, 1)

        lay.addWidget(self.mappings_group, 1)
        return w

    def _build_button_row(self) -> QHBoxLayout:
        """Build the confirm row at the foot of the dialog."""
        row = QHBoxLayout()

        self.apply_all_button = QPushButton("Apply to files…")
        self.apply_all_button.setToolTip(
            "Give every other file this file's header row, removed columns "
            "and rows, and isotope mappings, checking each mapping against "
            "that file's own column names")
        self.apply_all_button.clicked.connect(self._apply_to_all_files)
        self.apply_all_button.setEnabled(False)
        row.addWidget(self.apply_all_button)

        row.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        row.addWidget(self.cancel_button)

        self.import_button = QPushButton("Import data")
        self.import_button.setDefault(True)
        self.import_button.clicked.connect(self._accept_import)
        self.import_button.setEnabled(False)
        row.addWidget(self.import_button)
        return row

    # -- Theming ---------------------------------------------------------

    @staticmethod
    def _button_qss(p, filled: bool) -> str:
        """Return the stylesheet for one action button.

        Every action uses the same accent colour. Colour is reserved for the
        state of the data, not for ranking the buttons, so nothing in the row
        reads as a warning the user has to decode before pressing it.

        Args:
            p: Active theme palette.
            filled (bool): True for the primary action, False for the rest.

        Returns:
            str: Qt stylesheet for a ``QPushButton``.
        """
        if filled:
            base = (f"background-color: {p.accent}; color: {p.text_inverse}; "
                    f"border: 1px solid {p.accent};")
            hover = f"background-color: {p.accent_hover}; border-color: {p.accent_hover};"
        else:
            base = (f"background-color: transparent; color: {p.accent}; "
                    f"border: 1px solid {p.border};")
            hover = f"background-color: {p.accent_soft}; border-color: {p.accent};"
        return f"""
            QPushButton {{
                {base}
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: {'bold' if filled else 'normal'};
            }}
            QPushButton:hover {{ {hover} }}
            QPushButton:disabled {{
                background-color: transparent;
                color: {p.text_muted};
                border: 1px solid {p.disabled};
            }}
        """

    def _apply_theme(self, *_):
        """Restyle the dialog and its buttons for the active palette."""
        p = theme.palette
        self.setStyleSheet(dialog_qss(p))

        if hasattr(self, '_instructions_label'):
            self._instructions_label.setStyleSheet(
                f"color: {p.text_secondary}; margin: 2px;")

        primary = ('import_button', 'remove_button')
        secondary = ('apply_all_button', 'cancel_button', 'restore_button',
                     'detect_button', 'load_all_button')
        for name in primary:
            button = getattr(self, name, None)
            if button is not None:
                button.setStyleSheet(self._button_qss(p, True))
        for name in secondary:
            button = getattr(self, name, None)
            if button is not None:
                button.setStyleSheet(self._button_qss(p, False))

        if hasattr(self, '_row_status_label'):
            self._row_status_label.setStyleSheet(
                f"color: {p.text_secondary}; font-style: italic; margin: 2px;")

        if hasattr(self, 'preview_table'):
            model = self.preview_table.preview_model()
            if model is not None:
                model.set_muted_colour(QColor(p.text_muted))
                self._refresh_column_tints()

    # -- Advanced disclosure ---------------------------------------------

    def _detected_settings(self, index: int) -> dict:
        """Return the parse settings worked out from one file's own contents.

        Separator and encoding are sniffed rather than asked for, which is what
        lets the dialog drop its settings panel: the answer is in the file, and
        guessing it wrongly shows up immediately in the preview.

        Args:
            index (int): Position of the file in the batch.

        Returns:
            dict: Parse settings for that file.
        """
        cached = self._detected.get(index)
        if cached is not None:
            return cached

        path = self.file_paths[index]
        settings = {
            'delimiter': ',',
            'encoding': 'utf-8',
            'sheet_index': 0,
            'skip_rows': 0,
            'header_row': 0,
            'file_type': file_type_of(path),
        }
        if settings['file_type'] == 'delimited':
            try:
                settings.update(sniff_delimited_settings(path))
            except Exception:
                _itk_log.debug("Could not sniff %s", path, exc_info=True)
        self._detected[index] = settings
        return settings

    def _set_header_row(self, preview_row: int):
        """Treat one preview row as the row that names the columns.

        Detection finds the header on its own for the exports seen so far, but
        an unusual preamble can fool it. The correction is made where the
        mistake is visible: point at the row the table really starts on. The
        whole file is already loaded, so this costs nothing but a repaint.

        Args:
            preview_row (int): Zero-based preview row holding the column names.
        """
        model = self.preview_table.preview_model()
        if model is None or not model.is_raw():
            return
        if not model.set_header_row(preview_row):
            return
        settings = self._detected_settings(self.current_file_index)
        settings['skip_rows'] = preview_row
        self._detected[self.current_file_index] = settings

    def _on_header_row_changed(self, row: int):
        """Rebuild everything that depends on the column names.

        Args:
            row (int): The row now acting as the header.
        """
        model = self.preview_table.preview_model()
        if model is None:
            return
        self._current_columns = list(model.columns)
        self._refresh_time_column_options()
        self._refresh_mapped_columns_highlight()
        self._refresh_mappings_list()
        self._apply_exclusions_to_model()
        self._refresh_thumbnail(self.current_file_index)
        self.preview_table.fit_columns()
        self._sync_badge_widths(rebuild=True)
        self._refresh_row_status()
        self._refresh_file_list_status()
        self._validate_configuration()

    def _reset_header_row(self):
        """Forget a manual header choice and detect the layout again."""
        index = self.current_file_index
        self._detected.pop(index, None)
        self._load_file(self.file_paths[index])

    # -- Per-file loading pipeline ---------------------------------------

    def _switch_file(self, index: int):
        """Show a different file from the deck.

        Args:
            index (int): Position of the file in the batch.
        """
        if 0 <= index < len(self.file_paths):
            self.current_file_index = index
            self._load_file(self.file_paths[index])

    def _current_settings(self) -> dict:
        """Return the parse settings in force for the file on screen."""
        return dict(self._detected_settings(self.current_file_index))

    def _params_for(self, index: int) -> dict:
        """Return the time and data-format choices made for one file.

        These are held per file rather than shared, because a batch often mixes
        a survey run with a long acquisition and they do not share a dwell.
        Switching files therefore has to show that file's own numbers.

        Args:
            index (int): Position of the file in the batch.

        Returns:
            dict: That file's time settings, created with defaults on first use.
        """
        stored = self._params.get(index)
        if stored is None:
            stored = {
                'time_column': None,
                'time_unit': 'seconds',
                'dwell_time_ms': 0.100,
                'use_calculated_dwell': False,
                'data_type': 'Counts',
                'calculated_dwell_ms': None,
            }
            self._params[index] = stored
        return stored

    def _store_params(self, *_):
        """Save the panel's current values against the file on screen."""
        if self._loading_settings:
            return
        stored = self._params_for(self.current_file_index)
        stored['time_column'] = (self.time_column_combo.currentText()
                                 if self.time_column_combo.currentIndex() > 0
                                 else None)
        stored['time_unit'] = self.time_unit_combo.currentText()
        stored['use_calculated_dwell'] = self.calc_dwell_radio.isChecked()
        stored['data_type'] = self.data_type_combo.currentText()
        if not stored['use_calculated_dwell']:
            stored['dwell_time_ms'] = self.dwell_time_spin.value()
        self._update_calculated_dwell()
        stored['calculated_dwell_ms'] = (
            self._calculated_dwell_ms()
            if stored['use_calculated_dwell'] else None)
        self._refresh_effective_readout()

    def _params_for_config(self, index: int) -> dict:
        """Return one file's time settings with the dwell already resolved.

        In calculated mode the entered dwell is only a fallback, so the value
        handed on is the one read from the time column: the number the user was
        shown is the number that reaches the import.

        Args:
            index (int): Position of the file in the batch.

        Returns:
            dict: Time settings ready to travel with the import config.
        """
        stored = dict(self._params_for(index))
        calculated = stored.pop('calculated_dwell_ms', None)
        if stored['use_calculated_dwell'] and calculated:
            stored['dwell_time_ms'] = calculated
        return stored

    def _load_params(self):
        """Put the current file's stored choices back into the panel."""
        stored = self._params_for(self.current_file_index)
        self._loading_settings = True
        try:
            wanted = stored['time_column']
            index = (self.time_column_combo.findText(wanted)
                     if wanted else -1)
            self.time_column_combo.setCurrentIndex(max(0, index))
            unit = self.time_unit_combo.findText(stored['time_unit'])
            if unit >= 0:
                self.time_unit_combo.setCurrentIndex(unit)
            kind = self.data_type_combo.findText(stored['data_type'])
            if kind >= 0:
                self.data_type_combo.setCurrentIndex(kind)
            can_calculate = self.time_column_combo.currentIndex() > 0
            self.calc_dwell_radio.setEnabled(can_calculate)
            if stored['use_calculated_dwell'] and can_calculate:
                self.calc_dwell_radio.setChecked(True)
            else:
                self.manual_dwell_radio.setChecked(True)
            self.dwell_time_spin.setValue(stored['dwell_time_ms'])
        finally:
            self._loading_settings = False
        self._update_calculated_dwell()

    def _time_column_position(self) -> int | None:
        """Return which column the time values sit in, if one is chosen."""
        if self.time_column_combo.currentIndex() <= 0:
            return None
        name = self.time_column_combo.currentText()
        try:
            return [str(c) for c in self._current_columns].index(name)
        except ValueError:
            return None

    def _calculated_dwell_ms(self) -> float | None:
        """Return the dwell implied by the time column, in milliseconds.

        Returns:
            float | None: The median step between readings, or None when there
                is no usable time column loaded yet.
        """
        model = self.preview_table.preview_model()
        position = self._time_column_position()
        if model is None or position is None:
            return None

        frame = model.frame()
        start = (model.header_row() or 0) + 1 if model.is_raw() else 0
        window = frame.iloc[start:start + 5000, position]
        values = pd.to_numeric(
            window.astype(str).str.strip(), errors='coerce').dropna()
        if len(values) < 2:
            return None

        divisor = {'seconds': 1.0, 'milliseconds': 1e3,
                   'microseconds': 1e6, 'nanoseconds': 1e9}.get(
                       self.time_unit_combo.currentText(), 1.0)
        steps = np.diff(values.to_numpy(dtype=float) / divisor)
        steps = steps[np.isfinite(steps) & (steps > 0)]
        if not len(steps):
            return None
        return float(np.median(steps)) * 1000.0

    def _update_calculated_dwell(self):
        """Show the dwell read from the time column when that mode is chosen.

        Asking the app to work the dwell out and then leaving the box showing
        the old manual number is the kind of thing that quietly ends up in a
        report, so the calculated value is displayed as soon as it is known.
        """
        if not hasattr(self, 'dwell_time_spin'):
            return
        calculating = self.calc_dwell_radio.isChecked()
        self.dwell_time_spin.setEnabled(not calculating)
        if not calculating:
            self.dwell_time_spin.setToolTip("Time between readings")
            return

        dwell = self._calculated_dwell_ms()
        was_loading = self._loading_settings
        self._loading_settings = True
        try:
            if dwell is None:
                self.dwell_time_spin.setToolTip(
                    "No usable numbers in the time column yet")
            else:
                self.dwell_time_spin.setValue(
                    min(max(dwell, self.dwell_time_spin.minimum()),
                        self.dwell_time_spin.maximum()))
                self.dwell_time_spin.setToolTip(
                    f"Read from '{self.time_column_combo.currentText()}': "
                    f"{dwell:.6g} ms between readings")
        finally:
            self._loading_settings = was_loading

    def _load_file(self, file_path: str):
        """Build a lazy preview for a file, degrading gracefully on error.

        Args:
            file_path (str): Path to the file.
        """
        index = self.current_file_index
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            ftype = file_type_of(file_path)
            self._update_settings_visibility(ftype)
            if ftype == 'excel':
                self._populate_sheet_list(file_path)
            elif ftype == 'unknown':
                raise ValueError(f"Unsupported file type: {Path(file_path).suffix}")

            settings = self._current_settings()
            source = build_row_source(file_path, settings, raw=True)
            if not source.columns:
                source.close()
                raise ValueError("No columns could be read from this file")

            self._load_failed.discard(index)
            model = LazyPreviewModel(
                source, self, header_row=settings.get('skip_rows', 0))
            self._install_model(model)
            self._current_columns = list(model.columns)

            self._refresh_time_column_options()
            self._load_params()
            self._refresh_mapped_columns_highlight()
            self._refresh_mappings_list()
            self._apply_exclusions_to_model()
            self._refresh_thumbnail(index)
            self._refresh_row_status()
            self._refresh_file_list_status()
            self._on_selection_changed()
            self._validate_configuration()

        except Exception as e:
            _itk_log.error("Could not load %s: %s", Path(file_path).name, e)
            _itk_log.debug("Load failure detail", exc_info=True)
            self._load_failed.add(index)
            self._install_model(None)
            self._current_columns = []
            self._row_status_label.setText(
                f"Could not read {Path(file_path).name} — {str(e)[:90]}")
            self._effective_label.setText("")
            self._refresh_file_list_status()
            self._on_selection_changed()
            self._validate_configuration()

    def _refresh_thumbnail(self, index: int):
        """Give the file's card in the strip a miniature of its own data.

        Args:
            index (int): Position of the file in the batch.
        """
        model = self.preview_table.preview_model()
        if model is None:
            return
        frame = model.frame()
        start = (model.header_row() or 0) + 1 if model.is_raw() else 0
        rows = [list(frame.iloc[r])
                for r in range(start, min(start + 5, len(frame)))]
        self._set_card_thumbnail(index, self._current_columns, rows)

    def _set_card_thumbnail(self, index: int, columns, rows):
        """Push one file's miniature and removal marks onto its card.

        Args:
            index (int): Position of the file in the batch.
            columns: Column names of that file.
            rows: First few row sequences of that file.
        """
        excluded = self.exclusions.excluded_columns(index)
        positions = {i for i, name in enumerate(columns)
                     if str(name) in excluded}
        self.file_list.set_thumbnail(index, columns, rows, positions)

    def _load_all_thumbnails(self):
        """Read a few rows of every other file so each card shows its shape.

        Each file is sniffed on its own, so a batch that mixes a comma export
        with a semicolon one still shows both correctly.

        Only the header and five rows are read per file, which keeps opening a
        large batch cheap while still letting the strip show what each file
        looks like rather than a row of identical placeholders.
        """
        for index, path in enumerate(self.file_paths):
            if index == self.current_file_index:
                continue
            source = None
            try:
                settings = self._detected_settings(index)
                source = build_row_source(path, settings)
                frame = source.fetch(5)
                rows = [list(frame.iloc[r]) for r in range(len(frame))]
                self._set_card_thumbnail(index, source.columns, rows)
            except Exception:
                _itk_log.debug("No thumbnail for %s", path, exc_info=True)
                self.file_list.set_status(
                    index, subtitle="Could not be read", failed=True)
            finally:
                if source is not None:
                    source.close()
        self._refresh_file_list_status()
        self._validate_configuration()

    def _install_model(self, model):
        """Attach a preview model to the view, releasing the previous one.

        Args:
            model (LazyPreviewModel | None): New model, or None to clear the view.
        """
        previous = self.preview_table.preview_model()
        self.preview_table.setModel(model)
        if previous is not None:
            previous.close()
            previous.deleteLater()
        if model is None:
            self.badge_bar.sync_with_columns([])
            return
        model.set_muted_colour(QColor(theme.palette.text_muted))
        model.set_accent_colour(QColor(theme.palette.accent))
        model.rowsAppended.connect(self._refresh_row_status)
        model.sourceExhausted.connect(self._refresh_row_status)
        model.columnsRevealed.connect(self._on_columns_revealed)
        model.headerRowChanged.connect(self._on_header_row_changed)
        selection = self.preview_table.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._on_selection_changed)
        self.preview_table.fit_columns()
        self._sync_badge_widths(rebuild=True)
        QTimer.singleShot(0, self._fill_viewport)

    def _on_columns_revealed(self, *_):
        """Re-fit the badge strip after more columns come into view."""
        self.preview_table.fit_columns()
        self._apply_exclusions_to_model()
        self._sync_badge_widths(rebuild=True)
        self._refresh_mapped_columns_highlight()
        self._refresh_row_status()

    def _fill_viewport(self):
        """Load enough rows and columns to fill the visible table.

        The model opens on a small window and Qt only asks for more once the
        user scrolls, so without this a tall or wide window would show the
        opening block of data surrounded by empty space.
        """
        model = self.preview_table.preview_model()
        if model is None:
            return
        row_height = max(1, self.preview_table.verticalHeader().defaultSectionSize())
        wanted = self.preview_table.viewport().height() // row_height + 2
        guard = 0
        while model.rowCount() < wanted and model.canFetchMore() and guard < 60:
            model.fetchMore()
            guard += 1
        self.preview_table.ensure_columns_fill_viewport()

    def _update_settings_visibility(self, ftype: str):
        """Show the sheet selector only when a workbook has more than one sheet.

        Args:
            ftype (str): Coarse file family of the current file.
        """
        self.sheet_combo.setVisible(
            ftype == 'excel' and self.sheet_combo.count() > 1)
        self.sheet_label.setVisible(self.sheet_combo.isVisible())

    def _populate_sheet_list(self, file_path: str):
        """Fill the sheet selector with the workbook's sheet names.

        Args:
            file_path (str): Path to the workbook.
        """
        self._loading_settings = True
        self.sheet_combo.blockSignals(True)
        try:
            self.sheet_combo.clear()
            try:
                import openpyxl  # noqa: F401
                wb = openpyxl.load_workbook(file_path, read_only=True,
                                            data_only=False)
                for name in wb.sheetnames:
                    self.sheet_combo.addItem(name)
                wb.close()
                chosen = self._detected_settings(
                    self.current_file_index).get('sheet_index', 0)
                self.sheet_combo.setCurrentIndex(
                    min(chosen, max(0, self.sheet_combo.count() - 1)))
            except Exception:
                _itk_log.warning("Could not list sheets in %s", file_path)
                _itk_log.debug("Sheet listing detail", exc_info=True)
                self.sheet_combo.addItem("Sheet1")
        finally:
            self.sheet_combo.blockSignals(False)
            self._loading_settings = False

    # -- Preview rendering ----------------------------------------------

    def _sync_badge_widths(self, rebuild: bool = False):
        """Match the isotope badges to the preview's columns and row gutter.

        Args:
            rebuild (bool): True to recreate the badges, False to resize them.
        """
        model = self.preview_table.preview_model()
        if model is None:
            return
        header = self.preview_table.horizontalHeader()
        widths = [header.sectionSize(i)
                  for i in range(model.real_column_count())]
        self.badge_bar.set_leading_offset(
            self.preview_table.verticalHeader().width())
        if rebuild:
            self.badge_bar.sync_with_columns(widths)
        else:
            self.badge_bar.update_widths(widths)

    def _refresh_row_status(self, *_):
        """Describe the file, how much is loaded and what has been removed."""
        model = self.preview_table.preview_model()
        if model is None:
            self._row_status_label.setText("")
            self._effective_label.setText("")
            return

        path = Path(self.file_paths[self.current_file_index])
        settings = self._detected_settings(self.current_file_index)
        data_rows = model.data_row_count()
        counted = f"{data_rows:,}" if model.is_exhausted() else f"{data_rows:,}+"
        total_columns = model.total_column_count()
        shown = model.columnCount()
        columns = (f"{total_columns} columns" if shown >= total_columns
                   else f"{shown} of {total_columns} columns, scroll right for more")
        parts = [
            f"{counted} data rows × {columns}"
            f"  ·  {path.stat().st_size / 1024:,.1f} KB",
        ]
        header = model.header_row()
        if header is not None:
            parts.append(
                f"column names on line {header + 1}"
                + (", right-click a row to change" if header else ""))
        if settings['file_type'] == 'delimited':
            parts.append(
                f"read as {describe_delimiter(settings['delimiter'])}"
                f"-separated, {settings['encoding'].replace('-sig', '')}")
        if not model.is_exhausted():
            parts.append("scroll down to load more")
        truncated = model.truncated_at()
        if truncated is not None:
            parts.append(f"data ends at row {truncated:,} (trailing text found)")
        self._row_status_label.setText("  ·  ".join(parts))
        self.load_all_button.setEnabled(not model.is_exhausted())
        self._refresh_effective_readout()

    def _refresh_effective_readout(self, *_):
        """Show what the current file contributes once removals are applied."""
        if not hasattr(self, '_effective_label'):
            return
        model = self.preview_table.preview_model()
        if model is None:
            self._effective_label.setText("")
            return

        index = self.current_file_index
        removed = self.exclusions.exclusions_for(index)
        dropped = len(self._data_relative_rows(index))
        rows = max(0, model.data_row_count() - dropped)
        signals = len(self._effective_mappings(index))
        approx = "" if model.is_exhausted() else " of those loaded so far"

        parts = [f"Importing {rows:,} rows{approx}"]
        if dropped:
            parts.append(f"{dropped:,} removed")
        parts.append(f"{signals} signal column{'s' if signals != 1 else ''}")
        if removed.columns:
            parts.append(f"{len(removed.columns)} column"
                         f"{'s' if len(removed.columns) != 1 else ''} removed")

        if rows:
            dwell_s = self.dwell_time_spin.value() / 1000.0
            source = ("dwell read from the time column"
                      if self.calc_dwell_radio.isChecked() else "dwell entered")
            parts.append(
                f"{self.dwell_time_spin.value():.6g} ms {source}"
                f" · {(rows - 1) * dwell_s:,.3f} s duration")
        self._effective_label.setText("  ·  ".join(parts))

    def _load_all_rows(self):
        """Pull the rest of the current file into the preview immediately."""
        model = self.preview_table.preview_model()
        if model is None:
            return
        previous = QApplication.overrideCursor()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            model.reveal_all_columns()
            model.load_all()
        finally:
            QApplication.restoreOverrideCursor()
            if previous is not None:
                QApplication.setOverrideCursor(previous)
        self._refresh_row_status()

    def _refresh_file_list_status(self):
        """Update every card in the deck with its mapping and removal state."""
        for index in range(len(self.file_paths)):
            mapped = len(self._effective_mappings(index))
            failed = index in self._load_failed
            if failed:
                subtitle = "Could not be read"
            else:
                subtitle = self.exclusions.summary(index)
            self.file_list.set_status(
                index,
                subtitle=subtitle,
                badge=f"{mapped}" if mapped else "",
                ready=mapped > 0 and not failed,
                failed=failed,
            )

    def _refresh_time_column_options(self):
        """Repopulate the time-column selector from the current file's columns."""
        current = self.time_column_combo.currentText()
        self.time_column_combo.blockSignals(True)
        try:
            self.time_column_combo.clear()
            self.time_column_combo.addItem("None — generate from dwell")
            for c in self._current_columns:
                self.time_column_combo.addItem(str(c))
            idx = self.time_column_combo.findText(current)
            if idx >= 0:
                self.time_column_combo.setCurrentIndex(idx)
        finally:
            self.time_column_combo.blockSignals(False)

    # -- Keep / remove handling ------------------------------------------

    def _scope(self) -> str:
        """Return the scope a removal applies to.

        Removals always affect only the file on screen. Pushing them to the
        rest of the batch is what the apply button is for, so there is nothing
        to choose here.
        """
        return SCOPE_FILE

    def _selection_targets(self) -> tuple[set[str], set[int]]:
        """Return the column names and row numbers the selection covers.

        Returns:
            tuple[set[str], set[int]]: Selected column names and row numbers.
        """
        positions, rows = self.preview_table.selected_targets()
        names = {n for n in (self._column_name(p) for p in positions)
                 if n is not None}
        return names, rows

    def _describe_selection(self, columns, rows) -> str:
        """Return a short phrase naming what the selection covers.

        Args:
            columns: Selected column names.
            rows: Selected row numbers.

        Returns:
            str: Text such as ``"2 columns and 15 rows"``.
        """
        parts = []
        if columns:
            parts.append(f"{len(columns)} column"
                         f"{'s' if len(columns) != 1 else ''}")
        if rows:
            parts.append(f"{len(rows):,} row{'s' if len(rows) != 1 else ''}")
        return " and ".join(parts) if parts else "nothing"

    def _on_selection_changed(self, *_):
        """Update the removal buttons to match the current selection."""
        columns, rows = self._selection_targets()
        has_selection = bool(columns or rows)
        summary = self._describe_selection(columns, rows)

        excluded_cols = self.exclusions.excluded_columns(self.current_file_index)
        excluded_rows = self.exclusions.excluded_rows(self.current_file_index)
        any_present = bool((columns - excluded_cols) or (rows - excluded_rows))

        self.remove_button.setEnabled(has_selection and any_present)
        self.remove_button.setToolTip(
            f"Remove {summary}" if has_selection
            else "Select cells, columns or rows first")
        self.restore_button.setEnabled(self.exclusions.has_any())

    def _remove_selection(self):
        """Remove whatever the preview selection covers, in one undo step."""
        self._change_selection(removed=True)

    def _restore_everything(self):
        """Put back every removed row and column across the whole batch.

        The scope selector governs what a removal touches, not this: a button
        labelled "Restore all" that left some files still cut about would be a
        trap, so it always clears the lot.
        """
        self.exclusions.restore_all()
        self._row_status_label.setText("Everything restored")

    def _change_selection(self, removed: bool):
        """Apply one removal or restoration to the current selection.

        Columns and rows move together so a mixed selection is a single entry
        in the undo history rather than two.

        Args:
            removed (bool): True to remove the selection, False to restore it.
        """
        columns, rows = self._selection_targets()
        if not columns and not rows:
            return
        scope = self._scope()
        verb = "Remove" if removed else "Restore"
        label = f"{verb} {self._describe_selection(columns, rows)}"

        self.exclusions.begin_batch(label)
        try:
            if columns:
                self.exclusions.set_columns_removed(
                    self.current_file_index, columns, removed, scope)
            if rows:
                self.exclusions.set_rows_removed(
                    self.current_file_index, rows, removed, scope)
        finally:
            self.exclusions.end_batch()
        self._on_selection_changed()

    def _column_name(self, column_index: int) -> str | None:
        """Return the name of a column position in the current file.

        Args:
            column_index (int): Position of the column.
        """
        if 0 <= column_index < len(self._current_columns):
            return str(self._current_columns[column_index])
        return None

    def _show_column_menu(self, column_index: int, global_pos):
        """Offer the keep/remove and mapping actions for one column.

        Args:
            column_index (int): Position of the column that was right-clicked.
            global_pos: Screen position for the menu.
        """
        name = self._column_name(column_index)
        if name is None:
            return
        removed = self.exclusions.is_column_excluded(
            self.current_file_index, name)
        scope = self._scope()
        suffix = ""

        menu = QMenu(self)
        if removed:
            menu.addAction(
                f"Restore '{name}'{suffix}",
                lambda: self.exclusions.set_columns_removed(
                    self.current_file_index, [name], False, scope))
        else:
            menu.addAction(
                f"Remove '{name}'{suffix}",
                lambda: self.exclusions.set_columns_removed(
                    self.current_file_index, [name], True, scope))
            menu.addAction(
                f"Remove every other column{suffix}",
                lambda: self.exclusions.keep_only_columns(
                    self.current_file_index, [name], self._current_columns, scope))
        menu.addSeparator()
        menu.addAction("Assign isotope…",
                       lambda: self._open_picker_for_column(column_index))
        menu.addSeparator()
        menu.addAction("Restore everything in this file",
                       lambda: self.exclusions.restore_all(self.current_file_index))
        menu.exec(global_pos)

    def _show_row_menu(self, rows, global_pos):
        """Offer the keep/remove actions for the selected rows.

        Args:
            rows: List of zero-based row numbers that were right-clicked.
            global_pos: Screen position for the menu.
        """
        rows = [int(r) for r in rows]
        if not rows:
            return
        scope = self._scope()
        suffix = ""
        label = (f"row {rows[0] + 1}" if len(rows) == 1
                 else f"{len(rows)} selected rows")
        excluded = self.exclusions.excluded_rows(self.current_file_index)
        all_removed = all(r in excluded for r in rows)

        menu = QMenu(self)
        if all_removed:
            menu.addAction(
                f"Restore {label}{suffix}",
                lambda: self.exclusions.set_rows_removed(
                    self.current_file_index, rows, False, scope))
        else:
            menu.addAction(
                f"Remove {label}{suffix}",
                lambda: self.exclusions.set_rows_removed(
                    self.current_file_index, rows, True, scope))
            menu.addAction(
                f"Remove everything above row {rows[0] + 1}{suffix}",
                lambda: self.exclusions.set_rows_removed(
                    self.current_file_index, range(rows[0]), True, scope,
                    label=f"Remove first {rows[0]} rows"))
            menu.addAction(
                f"Remove everything below row {rows[-1] + 1}{suffix}",
                lambda: self._remove_rows_below(rows[-1], scope))
        menu.addSeparator()
        menu.addAction("Restore all rows in this file",
                       lambda: self.exclusions.set_rows_removed(
                           self.current_file_index, excluded, False, SCOPE_FILE))

        model = self.preview_table.preview_model()
        if model is not None and model.is_raw():
            menu.addSeparator()
            if rows[0] != model.header_row():
                menu.addAction("Use this row as the column names",
                               lambda: self._set_header_row(rows[0]))
            menu.addAction("Detect the header again", self._reset_header_row)
        menu.exec(global_pos)

    def _remove_rows_below(self, last_kept: int, scope: str):
        """Remove every loaded row after ``last_kept``.

        The rest of the file is read first so the removal covers the whole file
        rather than only the rows that happen to have been scrolled into view.

        Args:
            last_kept (int): Zero-based number of the last row to keep.
            scope (str): ``SCOPE_FILE`` or ``SCOPE_ALL``.
        """
        model = self.preview_table.preview_model()
        if model is None:
            return
        if not model.is_exhausted():
            self._load_all_rows()
        total = model.loaded_row_count()
        rows = range(last_kept + 1, total)
        self.exclusions.set_rows_removed(
            self.current_file_index, rows, True, scope,
            label=f"Remove rows after {last_kept + 1}")

    def _undo_exclusion(self):
        """Step back the most recent keep/remove change."""
        label = self.exclusions.undo()
        if label:
            self._row_status_label.setText(f"Undone: {label}")

    def _redo_exclusion(self):
        """Reapply the most recently undone keep/remove change."""
        label = self.exclusions.redo()
        if label:
            self._row_status_label.setText(f"Redone: {label}")

    def _on_exclusions_changed(self):
        """Repaint the preview, strip and readouts after a keep/remove change."""
        self._apply_exclusions_to_model()
        self._refresh_column_tints()
        self._refresh_mappings_list()
        self._refresh_thumbnail(self.current_file_index)
        self._refresh_row_status()
        self._refresh_file_list_status()
        self._on_selection_changed()
        self._validate_configuration()

    def _apply_exclusions_to_model(self):
        """Push the current file's removals into the preview model."""
        model = self.preview_table.preview_model()
        if model is None:
            return
        excluded = self.exclusions.excluded_columns(self.current_file_index)
        positions = {i for i, name in enumerate(self._current_columns)
                     if str(name) in excluded}
        model.set_excluded_columns(positions)
        model.set_excluded_rows(
            self.exclusions.excluded_rows(self.current_file_index))

    def _effective_mappings(self, file_index: int) -> dict[str, dict]:
        """Return the mappings of one file that a removal is not suppressing.

        A mapping on a removed column is kept rather than deleted, so restoring
        the column with undo brings the isotope assignment back with it. This
        filter is what stops a suppressed mapping from reaching the import.

        Args:
            file_index (int): Position of the file in the batch.

        Returns:
            dict[str, dict]: Mapping key to mapping record for active mappings.
        """
        excluded = self.exclusions.excluded_columns(file_index)
        return {k: v for k, v in self.column_mappings.items()
                if v['file_index'] == file_index
                and v['column_name'] not in excluded}

    # -- Selection, time-column, and dwell-method handlers ----------------

    def _on_time_column_changed(self, text: str):
        """React to a different column being named as the time axis.

        Args:
            text (str): Newly selected time-column name.
        """
        if self.time_column_combo.currentIndex() > 0:
            self.calc_dwell_radio.setEnabled(True)
        else:
            self.calc_dwell_radio.setEnabled(False)
            self.manual_dwell_radio.setChecked(True)

        self._refresh_time_column_options_if_needed(text)
        self._update_calculated_dwell()
        self._store_params()

    def _refresh_time_column_options_if_needed(self, selected_time_col: str):
        """If the time column was previously mapped, remove that mapping.

        Args:
            selected_time_col (str): Newly selected time-column name.
        """
        if selected_time_col in ("", "None — generate from dwell"):
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
        if keys_to_drop:
            self._refresh_column_tints()
            self._refresh_mappings_list()
            self._validate_configuration()

    def _on_dwell_method_changed(self):
        """Swap between the entered dwell and the one read from the data."""
        if not self._loading_settings and self.manual_dwell_radio.isChecked():
            stored = self._params_for(self.current_file_index)
            self._loading_settings = True
            try:
                self.dwell_time_spin.setValue(stored['dwell_time_ms'])
            finally:
                self._loading_settings = False
        self._update_calculated_dwell()
        self._store_params()

    # -- Mapping operations ---------------------------------------------

    def _open_picker_for_column(self, column_index: int):
        """Open the isotope picker for a column and commit the result.

        Args:
            column_index (int): Position of the column being mapped.
        """
        col_name = self._column_name(column_index)
        if col_name is None:
            return

        if self.exclusions.is_column_excluded(self.current_file_index, col_name):
            QMessageBox.information(
                self, "Column removed",
                f"'{col_name}' has been removed from this import. "
                "Restore it in the Structure panel before mapping it.")
            return

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

    def _commit_mapping(self, column_index: int, column_name: str, isotope: dict,
                        refresh: bool = True):
        """Record one column-to-isotope mapping for the current file.

        Args:
            column_index (int): Position of the column.
            column_name (str): Name of the column.
            isotope (dict): Isotope record chosen or detected for the column.
            refresh (bool): False to skip the UI refresh during bulk updates.
        """
        key = f"{self.current_file_index}_{column_index}"
        self.column_mappings[key] = {
            'file_index': self.current_file_index,
            'column_index': column_index,
            'column_name': column_name,
            'isotope': isotope,
        }
        self.badge_bar.set_mapping(column_index, isotope)
        if refresh:
            self._refresh_column_tints()
            self._refresh_mappings_list()
            self._refresh_file_list_status()
            self._validate_configuration()

    def _unmap_column(self, column_index: int):
        """Remove the isotope mapping for one column of the current file.

        Args:
            column_index (int): Position of the column.
        """
        key = f"{self.current_file_index}_{column_index}"
        if key in self.column_mappings:
            del self.column_mappings[key]
            self.badge_bar.set_mapping(column_index, None)
            self._refresh_column_tints()
            self._refresh_mappings_list()
            self._refresh_file_list_status()
            self._validate_configuration()

    def _refresh_mappings_list(self):
        """Rebuild the list of mappings belonging to the current file."""
        self.mappings_list.clear()
        index = self.current_file_index
        excluded = self.exclusions.excluded_columns(index)
        current = {k: v for k, v in self.column_mappings.items()
                   if v['file_index'] == index}
        for key, m in current.items():
            iso = m['isotope']
            text = f"{m['column_name']}  →  {iso['label']}  ({iso['element_name']})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            if m['column_name'] in excluded:
                item.setText(f"{text}   ·  column removed")
                item.setForeground(QColor(theme.palette.text_muted))
                item.setToolTip(
                    "This column has been removed, so the mapping is paused. "
                    "Restore the column to use it again.")
            self.mappings_list.addItem(item)

        active = len(self._effective_mappings(index))
        suffix = (f"{active} of {len(current)} active"
                  if active != len(current) else f"{active}")
        self.mappings_group.setTitle(f"Mappings ({suffix})")

    def _refresh_column_tints(self):
        """Tint the preview columns whose mapping is active."""
        model = self.preview_table.preview_model()
        if model is None:
            return
        success = QColor(theme.palette.success)
        success.setAlpha(90)
        tints = {
            m['column_index']: success
            for m in self._effective_mappings(self.current_file_index).values()
            if 0 <= m['column_index'] < model.columnCount()
        }
        model.set_column_tints(tints)

    def _refresh_mapped_columns_highlight(self):
        """Restore the badges and tints for the current file's mappings."""
        model = self.preview_table.preview_model()
        if model is None:
            return
        for m in self.column_mappings.values():
            if m['file_index'] != self.current_file_index:
                continue
            col = m['column_index']
            if 0 <= col < model.columnCount():
                self.badge_bar.set_mapping(col, m['isotope'])
        self._refresh_column_tints()

    # -- Auto-detection --------------------------------------------------

    def _auto_detect_isotopes(self, silent: bool = False):
        """Scan column names for isotope patterns and create mappings.

        This only ever runs because the user pressed the button. Nothing is
        assigned when a file is opened: the preview shows the file as it is,
        and the mapping is the user's to make, with this as a shortcut rather
        than a decision taken on their behalf.

        Args:
            silent (bool): True to skip the completion message.
        """
        if not self._current_columns:
            return

        existing = [k for k, v in self.column_mappings.items()
                    if v['file_index'] == self.current_file_index]

        time_col = (self.time_column_combo.currentText()
                    if self.time_column_combo.currentIndex() > 0 else None)
        excluded = self.exclusions.excluded_columns(self.current_file_index)

        for k in existing:
            col_idx = self.column_mappings[k]['column_index']
            del self.column_mappings[k]
            self.badge_bar.set_mapping(col_idx, None)

        detected = 0
        for col_idx, col in enumerate(self._current_columns):
            col_name = str(col)
            if time_col and col_name == time_col:
                continue
            if col_name in excluded:
                continue
            iso = self._detect_isotope_from_name(col_name)
            if iso:
                self._commit_mapping(col_idx, col_name, iso, refresh=False)
                detected += 1

        self._refresh_column_tints()
        self._refresh_mappings_list()
        self._refresh_file_list_status()
        self._validate_configuration()

        if not silent:
            self._row_status_label.setText(
                f"Detected {detected} isotope"
                f"{'s' if detected != 1 else ''} from the column names"
                if detected else
                "No column names look like isotopes — assign them by clicking "
                "a badge above the preview")

    def _detect_isotope_from_name(self, col_name: str) -> dict | None:
        """Match a column name against the isotope regex and the periodic table."""
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
            _itk_log.exception("Handled exception in _detect_isotope_from_name")
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

    def _apply_targets(self) -> list[int]:
        """Return the files an apply would write to.

        Highlighting several files in the list narrows the apply to those, so a
        batch that needs two different setups can have both. Highlighting only
        the open file, which is what a plain click leaves, means the whole
        batch, since that is the usual case.

        Returns:
            list[int]: Positions of the files to update.
        """
        chosen = [i for i in self.file_list.selected_indexes()
                  if i != self.current_file_index]
        if chosen:
            return chosen
        return [i for i in range(len(self.file_paths))
                if i != self.current_file_index]

    def _refresh_apply_button(self):
        """Enable applying once this file has something worth copying."""
        self.apply_all_button.setToolTip(
            "Choose which files should take this file's header row, removed "
            "columns and rows, and isotope mappings. Each chosen file is then "
            "checked for isotopes of its own.")
        self.apply_all_button.setEnabled(
            len(self.file_paths) > 1
            and bool(self._effective_mappings(self.current_file_index)))

    def _apply_to_all_files(self):
        """Give the chosen files this file's setup, verifying as it goes."""
        source = self.current_file_index
        current_map = list(self._effective_mappings(source).values())
        candidates = [(i, Path(p).name)
                      for i, p in enumerate(self.file_paths) if i != source]
        if not current_map or not candidates:
            return

        picker = ApplyTargetsDialog(
            candidates, Path(self.file_paths[source]).name,
            preselected=self._apply_targets(), parent=self)
        if picker.exec() != QDialog.Accepted:
            return
        targets = picker.selected_indexes()
        if not targets:
            return

        report = self._perform_apply_to_all(current_map, targets)
        copied = report['exact'] + report['confirmed']
        message = (f"Applied to {report['files']} files · "
                   f"{copied} columns copied")
        if report['detected']:
            message += f" · {report['detected']} more found by detection"
        unmatched = sum(1 for note in report['notes'] if 'unmapped' in note)
        if unmatched:
            message += f" · {unmatched} still unmapped"
        self._row_status_label.setText(message)

        self._refresh_file_list_status()
        self._validate_configuration()

    def _perform_apply_to_all(self, source_mappings: list[dict],
                              targets=None) -> dict:
        """Copy the current file's whole setup onto the chosen files.

        Args:
            source_mappings (list[dict]): Active mappings of the current file.
            targets: Files to update, or None for every other file.

        Returns:
            dict: Counts of copied, confirmed and freshly detected mappings,
                plus notes about everything that did not apply.
        """
        source = self.current_file_index
        source_settings = self._detected_settings(source)
        source_exclusions = self.exclusions.exclusions_for(source)
        report = {'files': 0, 'exact': 0, 'confirmed': 0, 'detected': 0,
                  'notes': []}
        if targets is None:
            targets = [i for i in range(len(self.file_paths)) if i != source]

        self.exclusions.begin_batch("Apply setup to other files")
        try:
            for target in targets:
                if target == source:
                    continue
                self._apply_setup_to_file(
                    target, source_mappings, source_settings,
                    source_exclusions, report)
        finally:
            self.exclusions.end_batch()

        self._refresh_mapped_columns_highlight()
        self._refresh_mappings_list()
        return report

    def _apply_setup_to_file(self, target: int, source_mappings: list[dict],
                             source_settings: dict, source_exclusions,
                             report: dict) -> None:
        """Apply one file's setup to another and record what happened.

        Args:
            target (int): File being updated.
            source_mappings (list[dict]): Active mappings of the source file.
            source_settings (dict): Parse settings of the source file.
            source_exclusions: Removed columns and rows of the source file.
            report (dict): Running tally to add this file's outcome to.
        """
        name = Path(self.file_paths[target]).name
        settings = self._settings_for_apply(target, source_settings)
        columns = read_columns_only(self.file_paths[target], settings)
        if not columns:
            report['notes'].append(f"{name}: could not be read, left alone")
            return

        self._detected[target] = settings
        self._params[target] = dict(self._params_for(self.current_file_index))
        report['files'] += 1

        for key in [k for k, v in self.column_mappings.items()
                    if v['file_index'] == target]:
            del self.column_mappings[key]

        present = {str(c) for c in columns}
        self.exclusions.set_columns_removed(
            target, source_exclusions.columns & present, True, SCOPE_FILE)
        if source_exclusions.rows:
            self.exclusions.set_rows_removed(
                target, source_exclusions.rows, True, SCOPE_FILE)

        excluded = self.exclusions.excluded_columns(target)
        taken: set[int] = set()
        for mapping in source_mappings:
            wanted = mapping['column_name'].strip()
            index, how = self._verify_mapping(columns, wanted, mapping['isotope'])
            if index is None:
                report['notes'].append(
                    f"{name}: no column matches '{wanted}', left unmapped")
                continue
            if str(columns[index]) in excluded:
                report['notes'].append(
                    f"{name}: '{columns[index]}' is removed, left unmapped")
                continue
            self.column_mappings[f"{target}_{index}"] = {
                'file_index': target,
                'column_index': index,
                'column_name': str(columns[index]),
                'isotope': dict(mapping['isotope']),
            }
            taken.add(index)
            report[how] += 1
            if how == 'confirmed':
                report['notes'].append(
                    f"{name}: '{wanted}' matched to '{columns[index]}' "
                    f"by isotope {mapping['isotope']['label']}")

        report['detected'] += self._detect_remaining_isotopes(
            target, columns, taken, excluded)

    def _detect_remaining_isotopes(self, target: int, columns, taken: set[int],
                                   excluded) -> int:
        """Name the isotopes in a file's leftover columns.

        A batch is rarely uniform: one run carries a channel the others do not.
        Copying the source mappings covers what the files share, and running
        detection over what is left covers the rest, so a file never has to be
        opened just to press the detect button on it.

        Args:
            target (int): File being updated.
            columns: Column names of that file.
            taken (set[int]): Column positions the copy already claimed.
            excluded: Column names removed from that file.

        Returns:
            int: How many further columns were mapped.
        """
        time_column = (self.time_column_combo.currentText()
                       if self.time_column_combo.currentIndex() > 0 else None)
        found = 0
        for position, column in enumerate(columns):
            if position in taken:
                continue
            name = str(column)
            if name in excluded or (time_column and name == time_column):
                continue
            isotope = self._detect_isotope_from_name(name)
            if not isotope:
                continue
            self.column_mappings[f"{target}_{position}"] = {
                'file_index': target,
                'column_index': position,
                'column_name': name,
                'isotope': isotope,
            }
            found += 1
        return found

    def _settings_for_apply(self, target: int, source_settings: dict) -> dict:
        """Return the parse settings to use when copying a setup onto a file.

        The source file's header row is tried first, since a batch normally
        shares one export format, but it is only kept if it actually yields
        columns. Otherwise the target keeps what its own detection found, which
        stops one odd file in a batch from being read at the wrong offset.

        Args:
            target (int): File being updated.
            source_settings (dict): Parse settings of the source file.

        Returns:
            dict: Settings for the target file.
        """
        own = dict(self._detected_settings(target))
        if own['file_type'] != 'delimited':
            return own

        candidate = dict(own)
        candidate['skip_rows'] = source_settings.get('skip_rows', 0)
        if candidate['skip_rows'] == own.get('skip_rows', 0):
            return own
        if read_columns_only(self.file_paths[target], candidate):
            return candidate
        return own

    def _verify_mapping(self, columns: list[str], wanted: str,
                        isotope: dict) -> tuple[int | None, str]:
        """Find the column in a target file that a mapping should move to.

        A name that matches outright is taken as-is. Failing that, a column
        whose own name resolves to the same isotope is accepted, which covers
        an instrument writing ``Ag107`` in one export and ``107Ag`` in the
        next. Nothing looser is allowed: the old substring fallback would
        happily match ``Li7`` to ``Li7_background`` and silently import the
        wrong channel.

        Args:
            columns (list[str]): Column names of the target file.
            wanted (str): Column name the mapping came from.
            isotope (dict): Isotope the mapping assigns.

        Returns:
            tuple[int | None, str]: Column position and how it was matched,
                one of ``'exact'`` or ``'confirmed'``.
        """
        needle = wanted.strip()
        for index, column in enumerate(columns):
            if str(column).strip() == needle:
                return index, 'exact'
        lowered = needle.lower()
        for index, column in enumerate(columns):
            if str(column).strip().lower() == lowered:
                return index, 'exact'

        for index, column in enumerate(columns):
            found = self._detect_isotope_from_name(str(column))
            if found and abs(found['mass'] - isotope['mass']) < 0.5 \
                    and found['symbol'] == isotope['symbol']:
                return index, 'confirmed'
        return None, 'none'

    def _on_sheet_changed(self, index: int):
        """Reload the workbook from a different sheet.

        Args:
            index (int): Position of the chosen sheet.
        """
        if index < 0 or self._loading_settings:
            return
        settings = self._detected.get(self.current_file_index)
        if settings is None:
            return
        settings['sheet_index'] = index
        self._debounced_reload()

    def _debounced_reload(self, *_):
        """Coalesce rapid settings changes into a single reload."""
        if not hasattr(self, '_reload_timer'):
            self._reload_timer = QTimer(self)
            self._reload_timer.setSingleShot(True)
            self._reload_timer.timeout.connect(self._do_reload)
        self._reload_timer.start(300)

    def _do_reload(self):
        """Reload the current file after a settings change."""
        try:
            if self.file_paths:
                self._load_file(self.file_paths[self.current_file_index])
        except Exception as e:
            _itk_log.error("Reload failed: %s", e)
            _itk_log.debug("Reload failure detail", exc_info=True)

    # -- Validation / config emission -----------------------------------

    def _prune_stale_mappings(self):
        """Remove mapping keys whose file_index is out of range for the current file list.

        This guards against ghost entries that accumulate if files are ever
        removed or if the dialog is reused with a different file list.
        """
        valid_indices = set(range(len(self.file_paths)))
        stale = [k for k, v in self.column_mappings.items()
                 if v.get('file_index') not in valid_indices]
        for k in stale:
            del self.column_mappings[k]

    def _validate_configuration(self):
        """Enable the action buttons according to the current configuration."""
        self._prune_stale_mappings()
        total = sum(len(self._effective_mappings(i))
                    for i in range(len(self.file_paths)))
        self._refresh_apply_button()
        self.import_button.setEnabled(
            total > 0 and self.current_file_index not in self._load_failed)
        self._refresh_effective_readout()

    def _unmapped_files(self) -> list[str]:
        """Return the names of files that would import with no signal columns."""
        return [Path(fp).name for i, fp in enumerate(self.file_paths)
                if not self._effective_mappings(i) or i in self._load_failed]

    def _build_import_config(self) -> dict:
        """Assemble the configuration dict handed to the worker thread.

        Returns:
            dict: Global parse settings plus a per-file record carrying that
                file's mappings and the columns and rows the user removed.
        """
        import copy
        self._store_params()
        current = self._detected_settings(self.current_file_index)
        current_params = self._params_for_config(self.current_file_index)
        config: dict[str, Any] = {
            'files': [],
            'settings': {
                'delimiter': current['delimiter'],
                'header_row': 0,
                'skip_rows': current['skip_rows'],
                'encoding': current['encoding'],
                'sheet_name': current['sheet_index'],
                'sheet_label': (self.sheet_combo.currentText()
                                if current['file_type'] == 'excel' else 'N/A'),
                'time_column': current_params['time_column'],
                'time_unit': current_params['time_unit'],
                'dwell_time_ms': current_params['dwell_time_ms'],
                'use_calculated_dwell': current_params['use_calculated_dwell'],
                'data_type': current_params['data_type'],
            },
        }
        for i, fp in enumerate(self.file_paths):
            detected = self._detected_settings(i)
            config['files'].append({
                'path': fp,
                'name': Path(fp).name,
                'type': file_type_of(fp),
                'mappings': copy.deepcopy(self._effective_mappings(i)),
                'excluded_columns': sorted(self.exclusions.excluded_columns(i)),
                'excluded_rows': self._data_relative_rows(i),
                'delimiter': detected['delimiter'],
                'encoding': detected['encoding'],
                'sheet_index': detected['sheet_index'],
                'skip_rows': detected['skip_rows'],
                **self._params_for_config(i),
            })
        return config

    def _data_relative_rows(self, index: int) -> list[int]:
        """Return one file's removed rows renumbered from the first data row.

        The preview counts rows from the top of the file so the preamble stays
        visible, but the importer skips that preamble and counts from the first
        reading. Without this shift a row removed in the preview would take a
        different row out of the imported data.

        Args:
            index (int): Position of the file in the batch.

        Returns:
            list[int]: Removed rows, numbered as the importer will number them.
        """
        offset = self._detected_settings(index).get('skip_rows', 0) + 1
        return sorted(
            max(0, row - offset)
            for row in self.exclusions.excluded_rows(index)
            if row >= offset
        )

    def _accept_import(self):
        """Confirm any unmapped files, then emit the import configuration."""
        unmapped = self._unmapped_files()
        if unmapped:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Files without mappings")
            msg.setText(
                f"{len(unmapped)} file(s) have no mapped columns and will "
                "produce no data. Import anyway?")
            detail = "\n".join(f"• {n}" for n in unmapped[:12])
            if len(unmapped) > 12:
                detail += f"\n… and {len(unmapped) - 12} more"
            msg.setDetailedText(detail)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            if msg.exec() != QMessageBox.Yes:
                return
        self.file_configured.emit(self._build_import_config())
        self.accept()


CSVStructureDialog = FileStructureDialog


def show_csv_structure_dialog(file_paths, parent=None) -> dict | None:
    """Open the import dialog and return its configuration.

    Args:
        file_paths: One path or a list of paths to configure.
        parent: Optional parent widget supplying the periodic table.

    Returns:
        dict | None: The import configuration, or None if the user cancelled.
    """
    dialog = FileStructureDialog(file_paths, parent)
    config: dict | None = None

    def on_configured(cfg):
        """Capture the configuration emitted when the user confirms.

        Args:
            cfg (dict): Import configuration built by the dialog.
        """
        nonlocal config
        config = cfg

    dialog.file_configured.connect(on_configured)
    return config if dialog.exec() == QDialog.Accepted else None


def show_csv_calibration_dialog(file_paths, parent=None) -> dict | None:
    """Open the import dialog for calibration files.

    Calibration standards are configured exactly like sample files, so this is
    the same dialog under the name the calibration modules import.

    Args:
        file_paths: One path or a list of paths to configure.
        parent: Optional parent widget supplying the periodic table.

    Returns:
        dict | None: The import configuration, or None if the user cancelled.
    """
    return show_csv_structure_dialog(file_paths, parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    test_files: list[str] = []
    dialog = FileStructureDialog(test_files)
    dialog.show()
    sys.exit(app.exec())