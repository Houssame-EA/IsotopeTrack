"""Everything that reads a CSV, TXT or Excel file into IsotopeTrack.

The pieces are split by what they are responsible for rather than by which
widget shows them, so the data path can be tested without a display:

``preview_model``
    Reading files. Encoding, separator and header-row detection, chunked
    readers that hand out rows on demand, and the table model that windows a
    file into the preview.
``exclusions``
    Which columns and rows the user has taken out, with undo and redo.
``file_list``
    The side list of files, with a thumbnail of each one's own data.
``dialog``
    The import dialog itself, and the worker thread that performs the import.

Import from this package rather than from the modules inside it: the names
below are the supported surface, and the split between modules may change.

    from loading.csv import show_csv_structure_dialog
"""
from __future__ import annotations

from loading.csv.preview_model import (
    DELIMITED_EXTS,
    EXCEL_EXTS,
    INITIAL_VISIBLE_COLUMNS,
    INITIAL_VISIBLE_ROWS,
    MIN_GRID_COLUMNS,
    MIN_GRID_ROWS,
    DelimitedRowSource,
    ExcelRowSource,
    LazyPreviewModel,
    RowSource,
    build_row_source,
    describe_delimiter,
    detect_delimiter,
    detect_encoding,
    detect_layout,
    detect_table_width,
    file_type_of,
    find_first_stopping_row,
    format_cell,
    numeric_like_columns,
    read_columns_only,
    sniff_delimited_settings,
)
from loading.csv.exclusions import (
    SCOPE_ALL,
    SCOPE_FILE,
    ExclusionManager,
    FileExclusions,
    apply_exclusions,
)
from loading.csv.file_list import FileEntry, FileListPanel, FileSlider
from loading.csv.profiles import (
    ImportProfile, clear_profiles, load_profiles, save_profile,
)
from loading.csv.dialog import (
    ApplyTargetsDialog,
    RecentSetupsDialog,
    CSVDataProcessThread,
    CSVPreviewTableWidget,
    CSVStructureDialog,
    DataProcessThread,
    FileStructureDialog,
    IsotopeBadgeBar,
    IsotopePickerDialog,
    show_csv_calibration_dialog,
    show_csv_structure_dialog,
)

__all__ = [
    "DELIMITED_EXTS",
    "EXCEL_EXTS",
    "INITIAL_VISIBLE_COLUMNS",
    "INITIAL_VISIBLE_ROWS",
    "MIN_GRID_COLUMNS",
    "MIN_GRID_ROWS",
    "SCOPE_ALL",
    "SCOPE_FILE",
    "ApplyTargetsDialog",
    "ImportProfile",
    "RecentSetupsDialog",
    "CSVDataProcessThread",
    "CSVPreviewTableWidget",
    "CSVStructureDialog",
    "DataProcessThread",
    "DelimitedRowSource",
    "ExcelRowSource",
    "ExclusionManager",
    "FileEntry",
    "FileExclusions",
    "FileListPanel",
    "FileStructureDialog",
    "IsotopeBadgeBar",
    "IsotopePickerDialog",
    "LazyPreviewModel",
    "RowSource",
    "apply_exclusions",
    "build_row_source",
    "describe_delimiter",
    "detect_delimiter",
    "detect_encoding",
    "detect_layout",
    "detect_table_width",
    "file_type_of",
    "find_first_stopping_row",
    "format_cell",
    "numeric_like_columns",
    "read_columns_only",
    "FileSlider",
    "show_csv_calibration_dialog",
    "show_csv_structure_dialog",
    "sniff_delimited_settings",
    "clear_profiles",
    "load_profiles",
    "save_profile",
]
