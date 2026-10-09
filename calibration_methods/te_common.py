import csv
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QTableWidgetItem, QMessageBox,
    QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox, QStyledItemDelegate,
    QLineEdit
)
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtCore import Qt

from tools.theme import theme, LIGHT, app_qss
from processing import detection_registry
import logging
_itk_log = logging.getLogger("IsotopeTrack.calibration_methods.te_common")


# ──────────────────────────────────────────────────────────────────────────────
# Shared Stylesheet — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def base_stylesheet(p) -> str:
    """Stylesheet for the calibration and transport-rate windows.

    It is the shared application sheet (:func:`tools.theme.app_qss`, the
    Figure Builder look) plus the text and banner roles these windows use
    through object names. Call it from a window's ``apply_theme`` so the
    window restyles on the light/dark switch::

        self.setStyleSheet(base_stylesheet(theme.palette))
    """
    return app_qss(p) + f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget#qt_scrollarea_viewport,
    QScrollArea > QWidget#qt_scrollarea_viewport > QWidget {{ background: transparent; }}
    QLabel#hintLabel {{ color: {p.text_muted}; font-size: 11px; }}
    QLabel#statusMuted {{ color: {p.text_muted}; font-weight: 600; }}
    QLabel#statusOk {{ color: {p.success}; font-weight: 600; }}
    QLabel#titleLabel {{ color: {p.text_primary}; font-size: 15px; font-weight: 700; }}
    QLabel#dialogTitle {{
        color: {p.text_primary};
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 6px;
    }}
    QLabel#dialogInstruction {{
        color: {p.text_primary};
        font-size: 13px;
        font-weight: 600;
        margin: 6px 0;
    }}
    QLabel#helpMuted {{ color: {p.text_muted}; margin-left: 22px; font-size: 11px; }}
    QLabel#helpInfo, QLabel#helpWarning {{
        background: {p.bg_secondary};
        color: {p.text_secondary};
        border: 1px solid {p.border_subtle};
        border-left: 3px solid {p.accent};
        border-radius: 6px;
        padding: 8px 10px;
    }}
    QLabel#helpWarning {{ border-left-color: {p.warning}; }}
    QFrame#instructionBox {{
        background: {p.bg_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        padding: 8px;
    }}
    QLabel#summaryPanel {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-left: 3px solid {p.accent};
        border-radius: 6px;
        padding: 10px;
    }}
    QPushButton#secondaryBtn {{ min-width: 80px; }}
    QPushButton#warningBtn {{
        background: {p.warning_bg};
        color: {p.text_primary};
        border: 1px solid {p.warning};
    }}
    QPushButton#warningBtn:hover {{ border-color: {p.accent}; }}
    QFrame#tableFrame {{ background: transparent; border: none; }}
    """


def section_stylesheet(p) -> str:
    """Rules for the collapsible sections and panel headers of the TE windows.

    Each section header is a white card with an accent arrow, matching the
    toolbar cards of the Figure Builder.
    """
    return f"""
    QWidget#collapsibleHeader {{
        background: {p.bg_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
    }}
    QWidget#collapsibleHeader:hover {{ border-color: {p.accent}; }}
    QLabel#collapsibleArrow {{ color: {p.accent}; font-size: 10px; font-weight: 700; }}
    QLabel#collapsibleTitle {{ color: {p.text_primary}; font-weight: 700; font-size: 13px; }}
    QLabel#collapsibleStatus {{ color: {p.text_muted}; font-size: 11px; }}
    QLabel#panelHeader {{
        color: {p.text_secondary};
        font-weight: 700;
        font-size: 12px;
        padding-bottom: 4px;
        border-bottom: 1px solid {p.border_subtle};
    }}
    """


BASE_STYLESHEET = base_stylesheet(LIGHT)


# ──────────────────────────────────────────────────────────────────────────────
# Preview Label Styles  (used in TE_input live preview) — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def preview_styles(p) -> dict:
    """Stylesheets for the result-preview label, keyed 'default', 'error',
    'warning' and 'success'.

    Each is a white card like the Figure Builder's; the state is carried by
    a coloured left edge and the text colour, which read well in both themes.
    """
    card = (f"background-color: {p.bg_secondary}; border: 1px solid {p.border_subtle}; "
            "border-radius: 8px; padding: 12px; font-size: 14px;")
    return {
        "default": f"{card} color: {p.text_muted};",
        "error":   f"{card} color: {p.danger}; border-left: 3px solid {p.danger};",
        "warning": f"{card} color: {p.text_primary}; border-left: 3px solid {p.warning};",
        "success": f"{card} color: {p.success}; font-weight: 600; border-left: 3px solid {p.success};",
    }


# Backward-compatible constant.
PREVIEW_STYLES = preview_styles(LIGHT)


# ──────────────────────────────────────────────────────────────────────────────
# "Back to Main" button style  (used in TE.py and ionic_CAL.py) — palette-aware
# ──────────────────────────────────────────────────────────────────────────────

def return_button_style(p) -> str:
    """Stylesheet for the 'Back to Main' button of the calibration windows.

    A quiet tool-style button in the Figure Builder look: no frame until
    hovered, so the window's single accent button stays the call to action.
    """
    return f"""
        QPushButton {{
            background: transparent;
            color: {p.text_secondary};
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {p.accent_soft};
            color: {p.text_primary};
            border-color: {p.border};
        }}
        QPushButton:pressed {{ background: {p.bg_selected}; border-color: {p.accent}; }}
    """


def return_button_icon_color(p) -> str:
    """Colour of the house icon on the 'Back to Main' button."""
    return p.text_secondary


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
    "background": pg.mkPen(color=(128, 128, 128), style=Qt.DashLine, width=1),
    "threshold": pg.mkPen(color=(220, 20, 60), style=Qt.DashLine, width=1),
    "integrated": {"symbol": "o", "size": 5,
                   "brush": pg.mkBrush(255, 165, 0, 200)},
    "peaks": {"symbol": "o", "size": 9,
              "brush": pg.mkBrush(46, 204, 113, 240)},
    "grid_alpha": 0.2,
    "highlight": pg.mkPen(color=(255, 0, 0), width=1),
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
        with open(file_path, mode="w", newline="", encoding="utf-8") as fh:
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

    except (OSError, UnicodeError, ValueError) as exc:
        QMessageBox.critical(
            parent_widget, "Export Error", f"Error exporting results: {exc}"
        )
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Detection-parameter table builder  (shared by TE_number & TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_DETECTION_PARAMS = {
    "method": "CPLN table",
    "manual_threshold": 10.0,
    "min_continuous": 1,
    "alpha": 0.000001,
}

DETECTION_METHODS = detection_registry.selectable_labels()


def populate_detection_row(table, row, sample_name, element_label,
                           defaults=None):
    """Populate a single row in a detection-parameters QTableWidget.

    Inserts read-only sample/element labels and configurable spin-box/combo
    widgets for detection method, threshold etc.

    Args:
        table (QTableWidget): Target table (must have ≥9 columns).
        row (int): Row index to populate.
        sample_name (str): Display name for the sample.
        element_label (str): Isotope label (e.g. '208Pb').
        defaults (dict | None): Override keys from DEFAULT_DETECTION_PARAMS.
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
    method_combo.addItems(DETECTION_METHODS)
    method_combo.setCurrentText(cfg["method"])
    table.setCellWidget(row, 2, method_combo)

    # Column 3 – manual threshold
    threshold_spin = QDoubleSpinBox()
    threshold_spin.setRange(0.0, 1e9)
    threshold_spin.setDecimals(2)
    threshold_spin.setValue(cfg["manual_threshold"])
    threshold_spin.setEnabled(detection_registry.get(cfg["method"]).is_manual)
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
        lambda text, r=row: table.cellWidget(r, 3).setEnabled(
            detection_registry.get(text).is_manual)
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
    except (ValueError, AttributeError, RuntimeError) as exc:
        _itk_log.exception("Handled exception in read_detection_row")
        _itk_log.error(f"Warning: falling back to defaults for row {row}: {exc}")
        return dict(DEFAULT_DETECTION_PARAMS)


def apply_global_method(table, method_name):
    """Set the detection method combo box on every row to *method_name*.

    Args:
        table (QTableWidget): The detection parameters table.
        method_name (str): Method string to set (e.g. 'Currie').
    """
    for row in range(table.rowCount()):
        combo = table.cellWidget(row, 2)
        if combo:
            combo.setCurrentText(method_name)


# ──────────────────────────────────────────────────────────────────────────────
# Sample-result plotting  (shared by TE_number & TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

def _style_plot_axes(plot_widget, title=None):
    """Apply the main-window plot appearance to *plot_widget*.

    Mirrors the tail of ``MainWindow.plot_results``: themed background/axes
    (no grid), 'Counts' / 'Time (s)' labels and free mouse interaction.

    Args:
        plot_widget (pg.PlotWidget): Target plot widget.
        title (str | None): Optional plot title.
    """
    plot_widget.setLabel("left", "Counts")
    plot_widget.setLabel("bottom", "Time (s)")
    if title is not None:
        plot_widget.setTitle(title)
    if hasattr(plot_widget, "apply_theme"):
        plot_widget.apply_theme()
    else:
        plot_widget.setBackground(theme.palette.plot_bg)
    plot_widget.setMouseEnabled(x=True, y=True)


def plot_raw_signal(plot_widget, sample_name, signal, time_array):
    """Plot a raw signal preview using the main-window plot settings.

    Args:
        plot_widget (pg.PlotWidget): Target plot widget.
        sample_name (str): Sample display name (used in the title).
        signal (np.ndarray): Raw signal array.
        time_array (np.ndarray): Time array (seconds).
    """
    plot_widget.clear()

    pen = PLOT_STYLES["raw_signal"]
    pen.setCosmetic(True)
    plot_widget.addItem(pg.PlotCurveItem(
        x=np.asarray(time_array), y=np.asarray(signal),
        pen=pen, name="Raw Signal", skipFiniteCheck=True,
    ))

    _add_styled_legend(plot_widget)
    _style_plot_axes(plot_widget, f"Raw Signal Preview - {sample_name}")
    plot_widget.enableAutoRange()


def _add_styled_legend(plot_widget):
    """Add a legend styled exactly like the main window's (20 pt labels)."""
    legend = plot_widget.addLegend(offset=(10, 10))
    legend.setParentItem(plot_widget.graphicsItem())
    plot_widget.legend = legend
    if hasattr(plot_widget, "_style_legend"):
        plot_widget._style_legend(legend)
    return legend


def plot_detection_results(plot_widget, sample_name, signal,
                           particles, lambda_bkgd, threshold, time_array,
                           peak_detector=None):
    """Render the particle-detection visualisation on *plot_widget*.

    This is a direct transcription of ``MainWindow.plot_results`` so the TE
    windows show detection exactly the way the main window does: raw signal,
    background and threshold lines, orange dots on every integrated point and
    a green dot on each peak maximum.

    Args:
        plot_widget (pg.PlotWidget): Target pyqtgraph plot widget.
        sample_name (str): Sample display name (used in the title).
        signal (np.ndarray): Raw signal array.
        particles (list[dict]): List of particle dicts from PeakDetection.
        lambda_bkgd (float | np.ndarray): Background level (scalar or per-point).
        threshold (float | np.ndarray): Detection threshold (scalar or per-point).
        time_array (np.ndarray): Time array (seconds).
        peak_detector (PeakDetection | None): Unused, kept for API compatibility.
    """
    plot_widget.clear()

    signal = np.asarray(signal)
    time_array = np.asarray(time_array)

    if isinstance(lambda_bkgd, np.ndarray):
        background_line = lambda_bkgd
    else:
        background_line = np.full_like(time_array, lambda_bkgd, dtype=float)
    if isinstance(threshold, np.ndarray):
        threshold_line = threshold
    else:
        threshold_line = np.full_like(time_array, threshold, dtype=float)

    plot_data = [
        (time_array, signal, PLOT_STYLES["raw_signal"], "Raw Signal"),
        (time_array, background_line, PLOT_STYLES["background"],
         "Background Level"),
        (time_array, threshold_line, PLOT_STYLES["threshold"],
         "Detection Threshold"),
    ]

    for x, y, pen, name in plot_data:
        keep = np.diff(y, n=2, append=np.inf, prepend=np.inf) != 0
        pen.setCosmetic(True)
        plot_widget.addItem(pg.PlotCurveItem(
            x=x[keep], y=y[keep], pen=pen, name=name, skipFiniteCheck=True,
        ))

    _add_styled_legend(plot_widget)

    if particles:
        integ_times, integ_heights = [], []
        peak_times, peak_heights = [], []

        for p in particles:
            if p is None:
                continue
            left_idx = int(p["left_idx"])
            right_idx = int(p["right_idx"])
            end = min(right_idx + 1, len(signal), len(time_array))
            start = min(left_idx, end)
            if start >= end:
                continue

            p_method = p.get("integration_method", "Background")
            if np.isscalar(lambda_bkgd):
                bkgd_l = lambda_bkgd
                thresh_l = threshold
            else:
                bkgd_l = lambda_bkgd[start:end]
                thresh_l = (threshold[start:end]
                            if not np.isscalar(threshold) else threshold)
            if p_method == "Threshold":
                integ_level = thresh_l
            elif p_method == "Midpoint":
                integ_level = (np.asarray(bkgd_l) + np.asarray(thresh_l)) / 2.0
            else:
                integ_level = bkgd_l

            s_region = signal[start:end]
            above = s_region > integ_level
            valid = np.arange(start, end)[above]
            integ_times.extend(time_array[valid].tolist())
            integ_heights.extend(signal[valid].tolist())

            peak_global = start + int(np.argmax(s_region))
            peak_times.append(float(time_array[peak_global]))
            peak_heights.append(float(signal[peak_global]))

        if integ_times:
            scatter_integ = pg.ScatterPlotItem(
                x=np.array(integ_times), y=np.array(integ_heights),
                symbol=PLOT_STYLES["integrated"]["symbol"],
                size=PLOT_STYLES["integrated"]["size"],
                brush=PLOT_STYLES["integrated"]["brush"],
                pen=pg.mkPen(None),
                name="Integrated points",
            )
            scatter_integ._role = "particle_integration"
            scatter_integ._legend_representative = True
            plot_widget.addItem(scatter_integ)

        if peak_times:
            scatter_peak = pg.ScatterPlotItem(
                x=np.array(peak_times), y=np.array(peak_heights),
                symbol=PLOT_STYLES["peaks"]["symbol"],
                size=PLOT_STYLES["peaks"]["size"],
                brush=PLOT_STYLES["peaks"]["brush"],
                pen=pg.mkPen(None),
                name="Peak Maximum",
            )
            scatter_peak._role = "peak_maximum"
            scatter_peak._legend_representative = True
            plot_widget.addItem(scatter_peak)

    legend = getattr(plot_widget, "legend", None)
    if legend is not None:
        for _sample, label in legend.items:
            label.setText(label.text, size="20pt")

    _style_plot_axes(plot_widget, f"Particle Detection Results – {sample_name}")
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
        name="Highlighted Peak",
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


# ──────────────────────────────────────────────────────────────────────────────
# Ionic-calibration regression  (shared by ionic_CAL & TE_mass)
# ──────────────────────────────────────────────────────────────────────────────

def fit_zero(x, y):
    """
    Force-through-zero (FTZ) linear regression.

    Finds the slope that minimises Σ(y - slope·x)² with intercept = 0.

    Equation
    --------
    slope = Σ(x·y) / Σ(x²)               [ordinary least squares, no intercept]
    R²    = 1 − Σ(y − ŷ)² / Σ(y²)        [denominator uses Σy² not Σ(y−ȳ)²
                                            because the model passes through 0]

    Args:
        x (np.ndarray): Concentration values (base unit, e.g. ppb).
        y (np.ndarray): Mean signal values (cps).

    Returns:
        dict with keys: slope, intercept (always 0), r_squared, y_fit.
    """
    slope = np.sum(x * y) / np.sum(x * x)
    y_fit = slope * x
    ss_res = np.sum((y - y_fit) ** 2)
    ss_tot = np.sum(y ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return {
        "slope": slope,
        "intercept": 0.0,
        "r_squared": r_squared,
        "y_fit": y_fit,
    }


def fit_simple(x, y):
    """
    Ordinary least squares (OLS) linear regression.

    Finds slope and intercept that minimise Σ(y − slope·x − intercept)².

    Equation
    --------
    [slope, intercept] = (XᵀX)⁻¹ Xᵀy   via np.linalg.lstsq
    R²  = 1 − Σ(y − ŷ)² / Σ(y − ȳ)²

    Args:
        x (np.ndarray): Concentration values.
        y (np.ndarray): Mean signal values (cps).

    Returns:
        dict with keys: slope, intercept, r_squared, y_fit.
    """
    A = np.vstack([x, np.ones(len(x))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    y_fit = slope * x + intercept
    ss_res = np.sum((y - y_fit) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "y_fit": y_fit,
    }


def fit_weighted(x, y, y_std):
    """
    Weighted least squares (WLS) linear regression.

    Points with lower variance receive higher weight, giving more influence
    to the most precise measurements.

    Equation
    --------
    wᵢ      = 1 / σᵢ²
    slope   = (Σw · Σwxy − Σwx · Σwy) / (Σw · Σwx² − (Σwx)²)
    intercept = (Σwx² · Σwy − Σwx · Σwxy) / (Σw · Σwx² − (Σwx)²)
    R²_w    = 1 − Σwᵢ(yᵢ − ŷᵢ)² / Σwᵢ(yᵢ − ȳ)²

    Falls back to OLS when the denominator is numerically zero (i.e. all
    points have equal / zero variance).

    Args:
        x (np.ndarray): Concentration values.
        y (np.ndarray): Mean signal values (cps).
        y_std (np.ndarray): Standard deviations of the signal.

    Returns:
        dict with keys: slope, intercept, r_squared, y_fit.
    """
    weights = 1.0 / (y_std ** 2)
    w_sum   = np.sum(weights)
    wx_sum  = np.sum(weights * x)
    wy_sum  = np.sum(weights * y)
    wxx_sum = np.sum(weights * x * x)
    wxy_sum = np.sum(weights * x * y)

    denominator = w_sum * wxx_sum - wx_sum * wx_sum

    if abs(denominator) > 1e-17:
        slope     = (w_sum * wxy_sum - wx_sum * wy_sum) / denominator
        intercept = (wxx_sum * wy_sum - wx_sum * wxy_sum) / denominator
        y_fit     = slope * x + intercept
        ss_res    = np.sum(weights * (y - y_fit) ** 2)
        ss_tot    = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    else:
        ols = fit_simple(x, y)
        slope, intercept, y_fit = ols["slope"], ols["intercept"], ols["y_fit"]
        r_squared = ols["r_squared"]

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "y_fit": y_fit,
    }


def compute_figures_of_merit(slope, intercept, sigma_blank):
    """
    Compute analytical figures of merit from regression results.

    Equations (IUPAC / Miller & Miller convention)
    -----------------------------------------------
    LOD = 3 · σ_blank / slope      [3-sigma limit of detection]
    LOQ = 10 · σ_blank / slope     [10-sigma limit of quantification]
    BEC = intercept / slope         [blank-equivalent concentration]
            (= LOD for FTZ, where intercept ≡ 0)

    All values are in the *base unit* (ppb by default) and are converted
    to the display unit separately before being shown in the UI.

    Args:
        slope (float): Calibration slope (cps / base_unit).
        intercept (float): Calibration intercept (cps).
        sigma_blank (float): Standard deviation of signal at lowest
            concentration standard (used as proxy for blank noise).

    Returns:
        dict with keys: lod, loq, bec.
            Values are np.nan when slope == 0.
    """
    if slope == 0:
        return {"lod": np.nan, "loq": np.nan, "bec": np.nan}

    lod = (3.0  * sigma_blank) / slope
    loq = (10.0 * sigma_blank) / slope
    bec = intercept / slope

    return {"lod": lod, "loq": loq, "bec": bec}


def run_all_fits_on_subset(x, y, y_std, included_mask, density):
    """
    Run the three calibration fits on the subset of points selected by
    ``included_mask`` and return the full result record for one isotope.

    Fits use only the included points, but ``y_fit`` is evaluated at
    every original x so the residuals subplot can show the distance
    between every point (included or not) and the fit line.

    Args:
        x, y, y_std: parallel 1-D numpy arrays (all points).
        included_mask: bool array same shape as x. True = use in fit.
        density: element density for the results record.

    Returns:
        dict or None. ``None`` when fewer than 2 included points remain.
    """
    if int(np.sum(included_mask)) < 2:
        return None

    xi = x[included_mask]
    yi = y[included_mask]
    si = y_std[included_mask]

    sigma_blank = float(si[int(np.argmin(xi))])

    f_zero     = fit_zero(xi, yi)
    f_simple   = fit_simple(xi, yi)
    f_weighted = fit_weighted(xi, yi, si)

    def eval_line(slope, intercept):
        return (slope * x + intercept).tolist()

    y_fit_zero     = eval_line(f_zero["slope"],     0.0)
    y_fit_simple   = eval_line(f_simple["slope"],   f_simple["intercept"])
    y_fit_weighted = eval_line(f_weighted["slope"], f_weighted["intercept"])

    fom_zero     = compute_figures_of_merit(
        f_zero["slope"],     0.0,                     sigma_blank)
    fom_simple   = compute_figures_of_merit(
        f_simple["slope"],   f_simple["intercept"],   sigma_blank)
    fom_weighted = compute_figures_of_merit(
        f_weighted["slope"], f_weighted["intercept"], sigma_blank)

    from calibration_methods.sensitivity_checks import slope_uncertainty
    unc_zero = slope_uncertainty(xi, yi, method='zero')
    unc_simple = slope_uncertainty(xi, yi, method='simple')
    unc_weighted = slope_uncertainty(xi, yi, si, method='weighted')
    fom_zero.update(slope_se=unc_zero['se'], slope_ci95=unc_zero['ci95'])
    fom_simple.update(slope_se=unc_simple['se'], slope_ci95=unc_simple['ci95'])
    fom_weighted.update(slope_se=unc_weighted['se'], slope_ci95=unc_weighted['ci95'])

    return {
        'zero': {
            'slope':     f_zero["slope"],
            'intercept': 0.0,
            'r_squared': f_zero["r_squared"],
            'y_fit':     y_fit_zero,
            **fom_zero,
        },
        'simple': {
            'slope':     f_simple["slope"],
            'intercept': f_simple["intercept"],
            'r_squared': f_simple["r_squared"],
            'y_fit':     y_fit_simple,
            **fom_simple,
        },
        'weighted': {
            'slope':     f_weighted["slope"],
            'intercept': f_weighted["intercept"],
            'r_squared': f_weighted["r_squared"],
            'y_fit':     y_fit_weighted,
            **fom_weighted,
        },
        'x':       x.tolist(),
        'y':       y.tolist(),
        'y_std':   y_std.tolist(),
        'density': density,
    }


def compute_outlier_indices(y, y_fit, included_mask, z_threshold=1.5):
    """Flag included points whose standardized residual exceeds ``z_threshold``.

    Standardization uses the sample standard deviation of the *included*
    residuals (ddof=1). With too few points the flag is disabled.

    Args:
        y (array-like): Measured signal values.
        y_fit (array-like): Fitted signal values, evaluated at every point.
        included_mask (array-like): Bool mask, True where the point is in the fit.
        z_threshold (float): Standardized-residual cut-off.

    Returns:
        set[int]: indices into the full ``y`` array.
    """
    y = np.asarray(y, dtype=float)
    y_fit = np.asarray(y_fit, dtype=float)
    if y.shape != y_fit.shape or len(y) == 0:
        return set()

    included_idx = [i for i, m in enumerate(included_mask) if m]
    if len(included_idx) < 4:
        return set()

    residuals = y - y_fit
    s = float(np.std(residuals[included_idx], ddof=1))
    if not np.isfinite(s) or s <= 0:
        return set()

    return {
        i for i in included_idx
        if abs(residuals[i] / s) > z_threshold
    }

def standards_in_sample_name(sample_name, presets):
    """
    Named multi-element standards (preset lists) found in a sample name.

    A preset such as ``71A``, ``68A-B`` or ``CMS-1 Rare Earth`` matches in
    any case, with ``-``, ``_``, ``.`` or a space (or nothing) between its
    characters, and not inside a longer word or number: ``71A_2ppb`` and
    ``68a_b 1 ppb`` match, ``171A`` does not. For a preset with spaces its
    first word alone (``CMS-1``) also matches.

    Args:
        sample_name: The sample (file or folder) name.
        presets: {preset name: [element symbols]}.

    Returns:
        (set of element symbols of the matched presets,
         sample name with the matched text blanked out).
    """
    import re
    found = set()
    remaining = sample_name
    names = []
    for preset in presets:
        names.append((preset, preset))
        head = preset.split(' ')[0]
        if head != preset:
            names.append((head, preset))
    names.sort(key=lambda item: -len(item[0]))
    for text, preset in names:
        chars = [re.escape(c) for c in text if c.isalnum()]
        if not chars:
            continue
        pattern = r'(?<![A-Za-z0-9])' + r'[-_. ]?'.join(chars) + r'(?![A-Za-z0-9])'
        if re.search(pattern, remaining, flags=re.IGNORECASE):
            found.update(presets[preset])
            remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
    return found, remaining


def elements_in_sample_name(sample_name, elements, presets=None):
    """
    Elements named in a calibration sample name.

    A name is cut into letter runs (digits, spaces and punctuation separate
    them). A run counts when it spells one or more element symbols with
    their exact capitalisation (``Fe``, ``FeCe``, the ``Ce`` of ``140Ce``),
    so lower-case unit text such as ``ppb`` is never read as ``Pb``, and
    all-capital words of three letters or more (``PPB``, ``ICP``, ``STD``)
    are ignored. Full
    element names (``Iron``, ``cerium``) are recognised in any case. When
    *presets* is given, named standards such as ``71A`` contribute all
    their elements (see :func:`standards_in_sample_name`), and their text
    is not read again as symbols (``68B-C`` is not boron and carbon).

    Args:
        sample_name: The sample (file or folder) name.
        elements: Periodic-table entries, each with ``symbol`` and ``name``.
        presets: Optional {standard name: [element symbols]}.

    Returns:
        set of element symbols found in the name.
    """
    import re
    symbols = {e['symbol'] for e in elements}
    names = {str(e.get('name', '')).lower(): e['symbol'] for e in elements if e.get('name')}
    found = set()
    if presets:
        found, sample_name = standards_in_sample_name(sample_name, presets)

    def split_symbols(run):
        if not run:
            return []
        for size in (2, 1):
            head = run[:size]
            if len(head) == size and head in symbols:
                rest = split_symbols(run[size:])
                if rest is not None:
                    return [head] + rest
        return None

    for run in re.findall(r'[A-Za-z]+', sample_name):
        if run.lower() in names:
            found.add(names[run.lower()])
            continue
        if len(run) >= 3 and run.isupper():
            continue
        parts = split_symbols(run) if run[0].isupper() else None
        if parts:
            found.update(parts)
    return found
