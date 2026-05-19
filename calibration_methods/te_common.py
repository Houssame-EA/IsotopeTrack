import csv
import numpy as np
import pyqtgraph as pg
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QGroupBox,
    QMainWindow, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QComboBox, QLabel, QCheckBox, QSpinBox, QDoubleSpinBox,
    QProgressDialog, QApplication, QAbstractItemView, QStyledItemDelegate,
    QLineEdit
)
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtCore import Qt, Signal

from theme import theme, LIGHT


# ──────────────────────────────────────────────────────────────────────────────
# Shared Stylesheet — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def base_stylesheet(p) -> str:
    """Full base stylesheet for calibration/TE windows, built from a
    theme Palette.  Covers main window, group boxes, buttons, inputs,
    tables, labels, tabs, tab bar, and list widgets.

    Call from a window's apply_theme() method so the whole window
    restyles on light/dark toggle:

        self.setStyleSheet(base_stylesheet(theme.palette))
    """
    return f"""
        QMainWindow, QWidget {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QGroupBox {{
            color: {p.text_primary};
            font-weight: bold;
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            background-color: {p.bg_secondary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }}
        QPushButton {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {p.disabled};
            color: {p.text_muted};
        }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}
        QTableWidget {{
            background-color: {p.bg_secondary};
            alternate-background-color: {p.bg_tertiary};
            color: {p.text_primary};
            gridline-color: {p.border};
            border: 1px solid {p.border};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QTabWidget::pane {{
            border: 1px solid {p.border};
            border-radius: 4px;
            background-color: {p.bg_secondary};
            top: -1px;
        }}
        /* QTabBar itself — without this the strip after the last tab
           shows the OS default (white on macOS). */
        QTabBar {{
            background-color: {p.bg_primary};
            qproperty-drawBase: 0;
        }}
        QTabWidget::tab-bar {{ alignment: left; }}
        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            border: 1px solid {p.border};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border-bottom: 1px solid {p.bg_secondary};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
            color: {p.text_primary};
        }}
        QListWidget {{
            background-color: {p.bg_secondary};
            alternate-background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        /* Scrollbars — consistent across themes */
        QScrollBar:vertical {{
            background: {p.bg_primary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {p.bg_primary};
            height: 10px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{ width: 0; }}

        /* ────────────────────────────────────────────────────────────
           Helper object names — widgets can just setObjectName() to
           pick up these styles instead of hardcoding per-widget QSS.
           Using these keeps label styling consistent across modules
           and means dark mode "just works" for every label.
           ──────────────────────────────────────────────────────────── */

        /* Italic muted instruction/hint text — used for "Click to..."
           messages, subtitles, explanatory captions. */
        QLabel#hintLabel {{
            color: {p.text_muted};
            font-style: italic;
            background-color: transparent;
        }}

        /* Status label in its neutral/idle state — bold, muted. */
        QLabel#statusMuted {{
            color: {p.text_muted};
            font-weight: bold;
            background-color: transparent;
        }}

        /* Status label when something succeeded / loaded. */
        QLabel#statusOk {{
            color: {p.success};
            font-weight: bold;
            background-color: transparent;
        }}

        /* Large section title at the top of a window. */
        QLabel#titleLabel {{
            color: {p.text_primary};
            font-size: 20px;
            font-weight: bold;
        }}

        /* Even larger dialog-heading title. */
        QLabel#dialogTitle {{
            color: {p.text_primary};
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        /* Emphasised bold label inside a dialog (e.g. "Choose..." prompt). */
        QLabel#dialogInstruction {{
            color: {p.text_primary};
            font-size: 14px;
            font-weight: bold;
            margin: 10px;
        }}

        /* Small muted description text under a radio button etc. */
        QLabel#helpMuted {{
            color: {p.text_muted};
            margin-left: 20px;
            font-size: 11px;
            background-color: transparent;
        }}

        /* Blue info banner. */
        QLabel#helpInfo {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
            padding: 10px;
            border-radius: 4px;
        }}

        /* Yellow warning banner. */
        QLabel#helpWarning {{
            background-color: {p.warning_bg};
            color: {p.text_primary};
            border: 1px solid {p.warning_border};
            padding: 10px;
            border-radius: 4px;
        }}

        /* Boxed instruction panel with a light background. */
        QFrame#instructionBox {{
            background-color: {p.bg_tertiary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 10px;
        }}

        /* Summary panel (e.g. "N samples, M particles detected"). */
        QLabel#summaryPanel {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 12px;
        }}

        /* Primary call-to-action button (green accent). */
        QPushButton#primaryBtn {{
            background-color: {p.success};
            color: {p.text_inverse};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#primaryBtn:hover {{ background-color: {p.accent_hover}; }}

        /* Neutral secondary button. */
        QPushButton#secondaryBtn {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#secondaryBtn:hover {{
            background-color: {p.bg_hover};
            border-color: {p.accent};
        }}

        /* Warning-style button (orange/yellow). */
        QPushButton#warningBtn {{
            background-color: {p.warning};
            color: {p.text_primary};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton#warningBtn:hover {{
            background-color: {p.accent_hover};
            color: {p.text_inverse};
        }}

        /* Bordered table frame wrapper. */
        QFrame#tableFrame {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
    """

BASE_STYLESHEET = base_stylesheet(LIGHT)


# ──────────────────────────────────────────────────────────────────────────────
# Preview Label Styles  (used in TE_input live preview) — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def preview_styles(p) -> dict:
    """Return the four preview-label stylesheet strings tinted for the
    given palette.  Keys: 'default', 'error', 'warning', 'success'.

    In dark mode the pastel backgrounds are replaced with muted tones
    from the palette so text stays readable.
    """
    if p.name == "dark":
        default_bg, default_fg = p.bg_tertiary,  p.text_secondary
        error_bg,   error_fg   = "#4a2326",      "#f48771"   # muted red
        warning_bg, warning_fg = p.warning_bg,   p.warning
        success_bg, success_fg = "#1e3a28",      p.success   # muted green
    else:
        default_bg, default_fg = "#f0f0f0", "#6c757d"
        error_bg,   error_fg   = "#f8d7da", "#721c24"
        warning_bg, warning_fg = "#fff3cd", "#856404"
        success_bg, success_fg = "#d4edda", "#155724"
    base = "padding: 15px; border-radius: 5px; font-size: 14px;"
    return {
        "default": f"background-color: {default_bg}; color: {default_fg}; {base}",
        "error":   f"background-color: {error_bg};   color: {error_fg};   {base}",
        "warning": f"background-color: {warning_bg}; color: {warning_fg}; {base}",
        "success": f"background-color: {success_bg}; color: {success_fg}; font-weight: bold; {base}",
    }


# Backward-compatible constant.
PREVIEW_STYLES = preview_styles(LIGHT)


# ──────────────────────────────────────────────────────────────────────────────
# "Back to Main" button style  (used in TE.py and ionic_CAL.py) — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def return_button_style(p) -> str:
    """Stylesheet for the 'Back to Main' button.  In light mode it keeps
    the original warm pink/orange gradient.  In dark mode it switches to
    a solid, muted accent so it doesn't blind the user.
    """
    if p.name == "dark":
        return f"""
            QPushButton {{
                background-color: {p.danger};
                color: {p.text_inverse};
                border: 2px solid {p.danger};
                border-radius: 22px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
                border: 2px solid {p.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.accent_pressed};
                border: 2px solid {p.accent_pressed};
            }}
        """
    # Light mode — preserve the original warm gradient.
    return """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #FF6B6B, stop:0.5 #FF8E53, stop:1 #FF6B9D);
            color: white;
            border: 3px solid #FF4081;
            padding: 8px 16px;
            text-align: center;
            font-size: 14px;
            font-weight: bold;
            border-radius: 22px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #FF5252, stop:0.5 #FF7043, stop:1 #FF4081);
            border: 3px solid #E91E63;
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #E53935, stop:0.5 #FF5722, stop:1 #E91E63);
            border: 3px solid #AD1457;
            padding: 9px 15px 7px 17px;
        }
    """


RETURN_BUTTON_STYLE = return_button_style(LIGHT)


def show_data_source_dialog(parent=None):
    """Show the "Select Data Source" popup and return the user's choice.

    The dialog presents three radio options — NU folders, generic data
    files, and TOFWERK .h5 — each with a short explanatory caption.
    Visually it follows the current theme (light or dark) automatically.

    Args:
        parent (QWidget | None): Parent for modality.

    Returns:
        str | None: ``'folder'``, ``'csv'``, or ``'tofwerk'`` for the user's
        selection, or ``None`` if they cancelled.
    """

    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QPushButton,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle("Select Data Source")
    dlg.setMinimumWidth(500)
    dlg.setMinimumHeight(400)
    # Apply the current theme so the popup picks up dark mode.
    dlg.setStyleSheet(base_stylesheet(theme.palette))

    layout = QVBoxLayout(dlg)

    instruction = QLabel("Choose your data source type:")
    instruction.setObjectName("dialogInstruction")
    layout.addWidget(instruction)

    folder_radio = QRadioButton("NU Folders (with run.info files)", dlg)
    csv_radio = QRadioButton("Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb)", dlg)
    tofwerk_radio = QRadioButton("TOFWERK Files (*.h5)", dlg)
    folder_radio.setChecked(True)

    radio_layout = QVBoxLayout()
    radio_layout.addWidget(folder_radio)
    radio_layout.addWidget(csv_radio)
    radio_layout.addWidget(tofwerk_radio)
    layout.addLayout(radio_layout)

    for text in (
        "• Select folders containing NU instrument data with run.info files\n"
        "• Supports multiple folders for batch processing\n"
        "• ⚠️ Mass ranges must match main analysis",

        "• Select Data Files with mass spectrometry data\n"
        "• Configure column mappings and time settings\n"
        "• ✅ No mass range validation required",

        "• Select TOFWERK .h5 files from TofDAQ acquisitions\n"
        "• Supports multiple files for batch processing\n"
        "• ✅ No mass range validation required",
    ):
        desc = QLabel(text)
        desc.setObjectName("helpMuted")
        layout.addWidget(desc)

    layout.addStretch()

    button_row = QHBoxLayout()
    ok_btn = QPushButton("Continue", dlg)
    ok_btn.setObjectName("primaryBtn")
    cancel_btn = QPushButton("Cancel", dlg)
    cancel_btn.setObjectName("secondaryBtn")
    button_row.addStretch()
    button_row.addWidget(ok_btn)
    button_row.addWidget(cancel_btn)
    layout.addLayout(button_row)

    ok_btn.clicked.connect(dlg.accept)
    cancel_btn.clicked.connect(dlg.reject)

    if dlg.exec() != QDialog.Accepted:
        return None

    if folder_radio.isChecked():
        return "folder"
    if csv_radio.isChecked():
        return "csv"
    if tofwerk_radio.isChecked():
        return "tofwerk"
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Plot Style Constants
# ──────────────────────────────────────────────────────────────────────────────

PLOT_STYLES = {
    "raw_signal": pg.mkPen(color=(30, 144, 255), width=1),
    "background": pg.mkPen(color=(128, 128, 128), style=Qt.DashLine, width=1.5),
    "threshold": pg.mkPen(color=(220, 20, 60), style=Qt.DashLine, width=1.5),
    "peaks": {"symbol": "t", "size": 12, "brush": "r", "pen": "r"},
    "grid_alpha": 0.2,
    "highlight": pg.mkPen(color=(255, 0, 0), width=3),
}

HISTOGRAM_COLORS = [
    (30, 144, 255, 180),
    (50, 205, 50, 180),
    (255, 69, 0, 180),
    (147, 112, 219, 180),
    (255, 215, 0, 180),
    (0, 191, 255, 180),
    (255, 127, 80, 180),
    (32, 178, 170, 180),
]


# ──────────────────────────────────────────────────────────────────────────────
# SNR → QColor mapping for particle row colouring
# ──────────────────────────────────────────────────────────────────────────────

def snr_to_color(ratio, palette=None):
    """
    Map a signal-to-noise ratio to a QColor for table row highlighting.

    Args:
        ratio (float): Height-to-threshold ratio of a detected particle.
        palette: Optional theme Palette.  If omitted, uses the current
            theme.palette — so dark mode automatically gets muted
            tiers that read on dark backgrounds.

    Returns:
        QColor: Green (>=3), light yellow (>=2), peach (>=1), or pink (<1)
        in light mode; muted equivalents in dark mode.
    """
    p = palette or theme.palette
    if p.name == "dark":
        # Use the severity tiers the main theme already defines — these
        # are the same colors used in the results table.
        if ratio >= 3.0: return QColor(p.tier_low)       # muted green
        if ratio >= 2.0: return QColor(p.tier_medium)    # muted yellow
        if ratio >= 1.0: return QColor(p.tier_high)      # muted orange
        return QColor(p.tier_critical)                   # muted red
    if ratio >= 3.0:
        return QColor(144, 238, 144)
    elif ratio >= 2.0:
        return QColor(255, 255, 224)
    elif ratio >= 1.0:
        return QColor(255, 239, 213)
    return QColor(255, 200, 200)


# ──────────────────────────────────────────────────────────────────────────────
# NumericDelegate  (was duplicated in TE_mass and ionic_CAL)
# ──────────────────────────────────────────────────────────────────────────────

class NumericDelegate(QStyledItemDelegate):
    """Custom delegate that restricts table-cell editing to numeric values."""

    def createEditor(self, parent, option, index):
        """
        Create a QLineEdit with a QDoubleValidator for the given cell.

        Args:
            parent (QWidget): Parent widget for the editor.
            option (QStyleOptionViewItem): Style option for the item.
            index (QModelIndex): Model index of the item being edited.

        Returns:
            QLineEdit: Editor widget with numeric-only input.
        """
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator())
        return editor


# ──────────────────────────────────────────────────────────────────────────────
# Scrollable Section helper
# ──────────────────────────────────────────────────────────────────────────────

def create_scrollable_container(parent_layout=None, spacing=15):
    """
    Build a QScrollArea wrapping a container QWidget with a QVBoxLayout.

    This pattern is repeated in virtually every tab across all TE modules.

    Args:
        parent_layout (QLayout | None): If provided, the scroll area is added
            to this layout automatically.
        spacing (int): Spacing between items inside the container layout.

    Returns:
        tuple[QScrollArea, QVBoxLayout]: The scroll area and the inner layout
        to which child widgets should be added.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)

    container = QWidget()
    inner_layout = QVBoxLayout(container)
    inner_layout.setSpacing(spacing)
    scroll.setWidget(container)

    if parent_layout is not None:
        parent_layout.addWidget(scroll)

    return scroll, inner_layout


# ──────────────────────────────────────────────────────────────────────────────
# CSV Export  (was duplicated identically in TE_number and TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

def export_table_to_csv(table, parent_widget, dialog_title="Export Detection Results"):
    """
    Export the contents of a QTableWidget to a CSV file.

    Opens a save-file dialog, writes column headers followed by every row,
    and reports success or failure via QMessageBox.

    Args:
        table (QTableWidget): The table whose data should be exported.
        parent_widget (QWidget): Parent widget for the file dialog and messages.
        dialog_title (str): Title shown in the save-file dialog.

    Returns:
        str | None: The path to the saved file, or None if the user cancelled
        or an error occurred.
    """
    if table.rowCount() == 0:
        QMessageBox.warning(parent_widget, "Export Error", "No results to export.")
        return None

    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, dialog_title, "", "CSV Files (*.csv)"
    )
    if not file_path:
        return None
    if not file_path.endswith(".csv"):
        file_path += ".csv"

    try:
        with open(file_path, mode="w", newline="") as fh:
            writer = csv.writer(fh)
            headers = [
                table.horizontalHeaderItem(c).text()
                for c in range(table.columnCount())
            ]
            writer.writerow(headers)
            for row in range(table.rowCount()):
                row_data = []
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)

        QMessageBox.information(
            parent_widget, "Export Successful", f"Results exported to {file_path}"
        )
        return file_path

    except Exception as exc:
        QMessageBox.critical(
            parent_widget, "Export Error", f"Error exporting results: {exc}"
        )
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Detection-parameter table builder  (shared by TE_number & TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_DETECTION_PARAMS = {
    "method": "Compound Poisson LogNormal",
    "manual_threshold": 10.0,
    "min_continuous": 1,
    "alpha": 0.000001,
}


def populate_detection_row(table, row, sample_name, element_label,
                           defaults=None):
    """
    Populate a single row in a detection-parameters QTableWidget.

    Inserts read-only sample/element labels and configurable spin-box/combo
    widgets for detection method, threshold etc.

    Args:
        table (QTableWidget): Target table (must have ≥9 columns).
        row (int): Row index to populate.
        sample_name (str): Display name for the sample.
        element_label (str): Isotope label (e.g. '208Pb').
        defaults (dict | None): Override keys from DEFAULT_DETECTION_PARAMS.

    Returns:
        None
    """
    cfg = {**DEFAULT_DETECTION_PARAMS, **(defaults or {})}

    # Column 0 – sample name (read-only)
    name_item = QTableWidgetItem(sample_name)
    name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
    table.setItem(row, 0, name_item)

    # Column 1 – element (read-only)
    elem_item = QTableWidgetItem(element_label)
    elem_item.setFlags(elem_item.flags() & ~Qt.ItemIsEditable)
    table.setItem(row, 1, elem_item)

    # Column 2 – detection method
    method_combo = QComboBox()
    method_combo.addItems([
         "Manual", "Compound Poisson Monte Carlo", "Compound Poisson LogNormal"
    ])
    method_combo.setCurrentText(cfg["method"])
    table.setCellWidget(row, 2, method_combo)

    # Column 3 – manual threshold
    threshold_spin = QDoubleSpinBox()
    threshold_spin.setRange(0.0, 1e9)
    threshold_spin.setDecimals(2)
    threshold_spin.setValue(cfg["manual_threshold"])
    threshold_spin.setEnabled(cfg["method"] == "Manual")
    table.setCellWidget(row, 3, threshold_spin)

    # Column 4 – min continuous points
    min_pts_spin = QSpinBox()
    min_pts_spin.setRange(1, 50)
    min_pts_spin.setValue(cfg["min_continuous"])
    table.setCellWidget(row, 4, min_pts_spin)

    # Column 5 – alpha
    alpha_spin = QDoubleSpinBox()
    alpha_spin.setRange(1e-8, 0.1)
    alpha_spin.setDecimals(8)
    alpha_spin.setValue(cfg["alpha"])
    alpha_spin.setSingleStep(1e-6)
    table.setCellWidget(row, 5, alpha_spin)

    # Wire enable/disable logic
    method_combo.currentTextChanged.connect(
        lambda text, r=row: table.cellWidget(r, 3).setEnabled(text == "Manual")
    )



def read_detection_row(table, row):
    """
    Read all detection parameters from a single row of the detection table.

    Args:
        table (QTableWidget): The detection parameters table.
        row (int): Row index to read.

    Returns:
        dict: Keys match DEFAULT_DETECTION_PARAMS. Falls back to defaults
        if widgets are missing.
    """
    try:
        method_w = table.cellWidget(row, 2)
        thresh_w = table.cellWidget(row, 3)
        minpts_w = table.cellWidget(row, 4)
        alpha_w = table.cellWidget(row, 5)

        if not all([method_w, thresh_w, minpts_w, alpha_w]):
            raise ValueError(f"Missing widgets in row {row}")

        return {
            "method": method_w.currentText(),
            "manual_threshold": thresh_w.value(),
            "min_continuous": minpts_w.value(),
            "alpha": alpha_w.value(),
        }
    except Exception as exc:
        print(f"Warning: falling back to defaults for row {row}: {exc}")
        return dict(DEFAULT_DETECTION_PARAMS)


def apply_global_method(table, method_name):
    """
    Set the detection method combo box on every row to *method_name*.

    Args:
        table (QTableWidget): The detection parameters table.
        method_name (str): Method string to set (e.g. 'Currie').

    Returns:
        None
    """
    for row in range(table.rowCount()):
        combo = table.cellWidget(row, 2)
        if combo:
            combo.setCurrentText(method_name)


# ──────────────────────────────────────────────────────────────────────────────
# Sample-result plotting  (shared by TE_number & TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

def plot_detection_results(plot_widget, sample_name, signal,
                           particles, lambda_bkgd, threshold, time_array,
                           peak_detector=None):
    """
    Render a comprehensive particle-detection visualisation on *plot_widget*.

    Draws raw signal, background/threshold lines, and
    detected peaks colour-coded by SNR.

    Args:
        plot_widget (pg.PlotWidget): Target pyqtgraph plot widget.
        sample_name (str): Sample display name (used in the title).
        signal (np.ndarray): Raw signal array.
        particles (list[dict]): List of particle dicts from PeakDetection.
        lambda_bkgd (float): Background level.
        threshold (float): Detection threshold.
        time_array (np.ndarray): Time array (seconds).
        peak_detector (PeakDetection | None): If provided, its
            ``get_snr_color`` method is used for scatter colouring.

    Returns:
        None
    """
    plot_widget.clear()

    traces = [
        (time_array, signal, PLOT_STYLES["raw_signal"], "Raw Signal"),
        (time_array, np.full_like(time_array, lambda_bkgd, dtype=float),
         PLOT_STYLES["background"], "Background Level"),
        (time_array, np.full_like(time_array, threshold, dtype=float),
         PLOT_STYLES["threshold"], "Detection Threshold"),
    ]
    for x, y, pen, name in traces:
        plot_widget.plot(x=x, y=y, pen=pen, name=name)

    if particles:
        times, heights, snrs = [], [], []
        for p in particles:
            if p is None:
                continue
            peak_idx = np.argmax(signal[p["left_idx"]:p["right_idx"] + 1])
            times.append(time_array[p["left_idx"] + peak_idx])
            heights.append(p["max_height"])
            snrs.append(p["max_height"] / threshold if threshold > 0 else 0)

        if peak_detector and hasattr(peak_detector, "get_snr_color"):
            brushes = [pg.mkBrush(peak_detector.get_snr_color(s)) for s in snrs]
        else:
            brushes = [pg.mkBrush(snr_to_color(s)) for s in snrs]

        scatter = pg.ScatterPlotItem(
            x=times, y=heights,
            symbol=PLOT_STYLES["peaks"]["symbol"],
            size=PLOT_STYLES["peaks"]["size"],
            brush=brushes,
            pen=PLOT_STYLES["peaks"]["pen"],
            name="Detected Peaks",
        )
        plot_widget.addItem(scatter)

    plot_widget.setBackground(theme.palette.plot_bg)
    plot_widget.showGrid(x=True, y=True, alpha=PLOT_STYLES["grid_alpha"])
    plot_widget.setLabel("left", "Counts")
    plot_widget.setLabel("bottom", "Time (s)")
    plot_widget.setTitle(f"Particle Detection Results – {sample_name}")
    plot_widget.setMouseEnabled(x=True, y=True)
    plot_widget.enableAutoRange()


def highlight_particle(plot_widget, particle, time_array, signal,
                       current_item_ref=None):
    """
    Draw a red highlight over a single particle in *plot_widget*.

    Args:
        plot_widget (pg.PlotWidget): Target plot.
        particle (dict): Particle dict with 'left_idx' / 'right_idx'.
        time_array (np.ndarray): Time array.
        signal (np.ndarray): Raw signal array.
        current_item_ref (pg.PlotCurveItem | None): Previously highlighted item
            to remove before adding the new one.

    Returns:
        pg.PlotCurveItem: The newly added highlight curve (store it so it can
        be removed on the next call).
    """
    if current_item_ref is not None:
        plot_widget.removeItem(current_item_ref)

    sl = slice(particle["left_idx"], particle["right_idx"] + 1)
    curve = pg.PlotCurveItem(
        x=time_array[sl], y=signal[sl],
        pen=PLOT_STYLES["highlight"],
        name="Selected Particle",
    )
    plot_widget.addItem(curve)
    return curve


# ──────────────────────────────────────────────────────────────────────────────
# Transport-rate physics helpers
# ──────────────────────────────────────────────────────────────────────────────

def particle_mass_from_diameter(diameter_nm, density_g_cm3):
    """
    Compute the mass of a spherical particle.

    Args:
        diameter_nm (float): Particle diameter in nanometres.
        density_g_cm3 (float): Bulk density in g/cm³.

    Returns:
        dict: Keys 'volume_m3', 'volume_nm3', 'mass_kg', 'mass_fg'.
    """
    diameter_m = diameter_nm * 1e-9
    density_kg_m3 = density_g_cm3 * 1000.0
    volume_m3 = (4.0 / 3.0) * np.pi * (diameter_m / 2.0) ** 3
    mass_kg = volume_m3 * density_kg_m3
    return {
        "volume_m3": volume_m3,
        "volume_nm3": volume_m3 * 1e27,
        "mass_kg": mass_kg,
        "mass_fg": mass_kg * 1e18,
    }


def number_method_transport_rate(particles_detected, diameter_nm,
                                 concentration_ng_l, acquisition_time_s,
                                 density_g_cm3):
    """
    Calculate transport rate using the particle-number method.

    η = N_detected / (C_number × t)   →   expressed in µL/s.

    Args:
        particles_detected (int): Number of detected particle events.
        diameter_nm (float): Certified particle diameter (nm).
        concentration_ng_l (float): Particle mass concentration (ng/L).
        acquisition_time_s (float): Total acquisition time (s).
        density_g_cm3 (float): Element density (g/cm³).

    Returns:
        dict: 'transport_rate_ul_s', 'particles_per_ml', 'particle_mass_fg',
              'particle_volume_nm3', 'status'.
    """
    pm = particle_mass_from_diameter(diameter_nm, density_g_cm3)

    particles_per_l = concentration_ng_l / (pm["mass_kg"] * 1e12)
    particles_per_ml = particles_per_l / 1000.0

    if particles_per_ml > 0 and acquisition_time_s > 0:
        rate_ml_s = particles_detected / (particles_per_ml * acquisition_time_s)
        return {
            "transport_rate_ul_s": rate_ml_s * 1000.0,
            "particles_per_ml": particles_per_ml,
            "particle_mass_fg": pm["mass_fg"],
            "particle_volume_nm3": pm["volume_nm3"],
            "status": "Success",
        }
    return {
        "transport_rate_ul_s": 0.0,
        "particles_per_ml": 0.0,
        "particle_mass_fg": pm["mass_fg"],
        "particle_volume_nm3": pm["volume_nm3"],
        "status": "Error: Invalid parameters",
    }


def weight_method_transport_rate(w_initial_g, w_final_g, w_waste_g, time_s):
    """
    Calculate transport rate using the liquid-weight method.

    Args:
        w_initial_g (float): Initial sample mass (g).
        w_final_g (float): Final sample mass (g).
        w_waste_g (float): Waste container mass increase (g).
        time_s (float): Analysis time (seconds).

    Returns:
        dict: 'transport_rate_ul_s', 'sample_consumed_g',
              'volume_to_plasma_g', 'status'.

    Raises:
        ValueError: If any physical constraint is violated.
    """
    if time_s <= 0:
        raise ValueError("Analysis time must be greater than zero.")
    sample_consumed = w_initial_g - w_final_g
    if sample_consumed <= 0:
        raise ValueError("Initial mass must be greater than final mass.")
    volume_to_plasma = sample_consumed - w_waste_g
    if volume_to_plasma <= 0:
        raise ValueError(
            "Sample consumed must be greater than waste collected."
        )
    rate = (volume_to_plasma * 1000.0) / time_s  # µL/s
    return {
        "transport_rate_ul_s": rate,
        "sample_consumed_g": sample_consumed,
        "volume_to_plasma_g": volume_to_plasma,
        "status": "Success",
    }