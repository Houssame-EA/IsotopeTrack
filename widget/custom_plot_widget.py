import pyqtgraph as pg
from PySide6.QtGui import QColor, QPen, QFont, QAction, QFontDatabase
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSpinBox, QDoubleSpinBox, QColorDialog, 
                               QComboBox, QCheckBox, QLineEdit, QGroupBox, 
                               QFormLayout, QTabWidget, QWidget, QSlider,
                               QFontDialog, QMessageBox, QFileDialog, QMenu,
                               QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal
import numpy as np
import json
import pandas as pd
from pathlib import Path

from theme import theme as _app_theme


# ── Theme helpers for editor dialogs ─────────────────────────────────────────

def _editor_dialog_qss():
    """Stylesheet applied to every small plot editor dialog
    (TraceEditor, ScatterEditor, AxisLabelEditor, TitleEditor,
    LegendEditor, BackgroundEditor, etc). Pulls from the current theme.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QGroupBox {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 1em;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 6px;
            color: {p.text_primary};
        }}
        QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 6px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 16px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
        }}
        /* SpinBox up/down buttons were painting white on dark backgrounds */
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {p.bg_tertiary};
            border: 1px solid {p.border};
            width: 14px;
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {p.bg_hover};
        }}
        QCheckBox {{
            color: {p.text_primary};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border-radius: 3px;
            border: 2px solid {p.border};
            background-color: {p.bg_secondary};
        }}
        QCheckBox::indicator:checked {{
            background-color: {p.accent};
            border-color: {p.accent};
        }}
        QScrollArea {{ border: none; background: transparent; }}
        /* Tab widget — previously the pane stayed white in dark mode */
        QTabWidget::pane {{
            background-color: {p.bg_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            top: -1px;
        }}
        QTabBar {{
            background-color: transparent;
            qproperty-drawBase: 0;
        }}
        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            border: 1px solid {p.border};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 6px 14px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border-color: {p.accent};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
            color: {p.text_primary};
        }}
        /* Slider — the groove was light by default */
        QSlider::groove:horizontal {{
            background: {p.bg_tertiary};
            border: 1px solid {p.border};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {p.accent};
            border: 1px solid {p.accent};
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {p.accent_hover};
        }}
        /* Default button styling — used by the bottom-bar Reset/Apply/OK/
           Cancel buttons. Children that set their own stylesheet (inline
           Apply buttons in the Traces tab, color swatches) override this. */
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_soft};
        }}
        QPushButton:disabled {{
            background-color: {p.bg_secondary};
            color: {p.text_muted};
            border: 1px solid {p.border_subtle};
        }}
        /* Catch-all for the form-row labels and any plain QWidget panels
           that would otherwise show through the OS light palette */
        QWidget {{
            color: {p.text_primary};
        }}
        QMessageBox {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
    """


def _editor_header_qss():
    """Header label at the top of each editor dialog (was '#2c3e50' bold).
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return f"font-size: 15px; font-weight: bold; color: {p.text_primary};"


def _editor_ok_button_qss():
    """Primary OK/Apply button. Was hardcoded #3498db → #2980b9.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return (
        f"QPushButton{{background:{p.accent};color:{p.text_inverse};"
        f"border:none;border-radius:4px;padding:8px 18px;font-weight:bold}}"
        f"QPushButton:hover{{background:{p.accent_hover}}}"
    )


def _editor_cancel_button_qss():
    """Neutral Cancel button. Was hardcoded #95a5a6 → #7f8c8d.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return (
        f"QPushButton{{background:{p.bg_tertiary};color:{p.text_primary};"
        f"border:1px solid {p.border};border-radius:4px;padding:8px 18px;"
        f"font-weight:bold}}"
        f"QPushButton:hover{{background:{p.bg_hover};"
        f"border:1px solid {p.accent}}}"
    )


def _color_swatch_qss(hex_color):
    """Small color picker swatch. hex_color may be any valid CSS color.
    Args:
        hex_color (Any): The hex color.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return (
        f"background-color:{hex_color};"
        f"border:2px solid {p.border};border-radius:4px;"
    )


def _tall_color_swatch_qss(hex_color):
    """Full-width color swatch used in the PlotSettingsDialog form rows
    (font color / background color / grid color). Keeps the border
    theme-aware so the button doesn't look pasted-on in dark mode.
    Args:
        hex_color (Any): The hex color.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return (
        f"background-color:{hex_color};"
        f"border:1px solid {p.border};"
        f"border-radius:4px;"
        f"min-height:30px;"
    )


def _hint_label_qss():
    """Italic tip / hint labels (the 'Double-click any element…' line and
    the 'Edit all traces…' header on the Traces tab). Used to be hardcoded
    #555/#666/#999 which is unreadable in dark mode.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return f"color:{p.text_secondary};font-style:italic;padding:6px;"


def _trace_row_qss():
    """Per-trace row background on the Traces tab (formerly hardcoded white
    `#fff`). Uses the theme's tertiary surface in both light and dark mode,
    with a left-edge accent bar to visually distinguish it from scatter rows.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    return (
        f"QFrame{{background:{p.bg_tertiary};"
        f"border:1px solid {p.border_subtle};"
        f"border-left:3px solid {p.accent};"
        f"border-radius:6px;padding:6px;}}"
        f"QFrame:hover{{border:1px solid {p.accent};"
        f"border-left:3px solid {p.accent};}}"
    )


def _scatter_row_qss():
    """Per-scatter row background on the Traces tab (formerly cream `#fff8f0`
    with an orange accent). Shares the same dark surface as trace rows but
    uses a 'success' / teal left-edge accent so scatter vs. line is still
    visually distinguishable — no more olive-yellow warning color showing up
    in dark mode.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    accent_bar = getattr(p, 'success', p.accent)
    return (
        f"QFrame{{background:{p.bg_tertiary};"
        f"border:1px solid {p.border_subtle};"
        f"border-left:3px solid {accent_bar};"
        f"border-radius:6px;padding:6px;}}"
        f"QFrame:hover{{border:1px solid {accent_bar};"
        f"border-left:3px solid {accent_bar};}}"
    )


def _inline_apply_btn_qss(variant='primary'):
    """Small 'Apply' button rendered inside each trace/scatter row.
    `variant` is either 'primary' (trace rows) or 'warn' (scatter rows).
    Theme-aware replacement for the old hardcoded blue/orange — the
    'warn' variant now uses the theme's success color to stay readable.
    Args:
        variant (Any): The variant.
    Returns:
        object: Result of the operation.
    """
    p = _app_theme.palette
    if variant == 'warn':
        bg = getattr(p, 'success', p.accent)
        bg_hover = p.accent_pressed
        return (
            f"QPushButton{{background:{bg};color:{p.text_inverse};"
            f"border:none;border-radius:3px;padding:4px;font-size:11px}}"
            f"QPushButton:hover{{background:{bg_hover}}}"
        )
    return (
        f"QPushButton{{background:{p.accent};color:{p.text_inverse};"
        f"border:none;border-radius:3px;padding:4px;font-size:11px}}"
        f"QPushButton:hover{{background:{p.accent_hover}}}"
    )


def _install_theme_subscription(dialog):
    """Attach the editor_dialog_qss to a dialog AND keep it updated when the
    user toggles theme. Safe to call from any editor dialog's __init__.
    Args:
        dialog (Any): Parent or target dialog.
    """
    dialog.setStyleSheet(_editor_dialog_qss())

    def _reapply():
        try:
            dialog.setStyleSheet(_editor_dialog_qss())
        except RuntimeError:
            pass

    _app_theme.themeChanged.connect(_reapply)
    original_close = dialog.closeEvent
    def _close(event):
        """
        Args:
            event (Any): Qt event object.
        """
        try:
            _app_theme.themeChanged.disconnect(_reapply)
        except (TypeError, RuntimeError):
            pass
        original_close(event)
    dialog.closeEvent = _close


# ── Line style mapping ────────────────────────────────────────────────────────

LINE_STYLE_MAP = {
    "Solid":          Qt.SolidLine,
    "Dash":           Qt.DashLine,
    "Dot":            Qt.DotLine,
    "Dash-Dot":       Qt.DashDotLine,
    "Dash-Dot-Dot":   Qt.DashDotDotLine,
}

LINE_STYLE_REVERSE = {v: k for k, v in LINE_STYLE_MAP.items()}

# ── Scatter symbols ───────────────────────────────────────────────────────────

SCATTER_SYMBOLS = {
    "Circle":       'o',
    "Square":       's',
    "Triangle Up":  't',
    "Triangle Down": 't1',
    "Diamond":      'd',
    "Plus":         '+',
    "Cross":        'x',
    "Star":         'star',
    "Pentagon":     'p',
    "Hexagon":      'h',
}

SCATTER_SYMBOLS_REVERSE = {v: k for k, v in SCATTER_SYMBOLS.items()}


# ── System font helper ────────────────────────────────────────────────────────

def get_system_font_families():
    """
    Get available system font families from Qt font database,
    sorted with common scientific fonts first.

    Returns:
        list: Sorted list of font family names
    """
    all_families = QFontDatabase.families()

    preferred = [
        "Times New Roman", "Arial", "Helvetica", "Helvetica Neue",
        "Calibri", "Verdana", "Georgia", "Cambria",
        "Palatino", "Garamond", "Book Antiqua",
        "Courier New", "Consolas", "DejaVu Sans",
    ]

    top = [f for f in preferred if f in all_families]
    rest = sorted([f for f in all_families if f not in top])

    return top + rest


class TraceEditorDialog(QDialog):
    """Edit a single trace: color, width, line style, legend name."""

    def __init__(self, curve_item, plot_widget, parent=None):
        """
        Args:
            curve_item (Any): The curve item.
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.curve_item = curve_item
        self.plot_widget = plot_widget
        self.setWindowTitle("Edit Trace")
        self.setFixedWidth(380)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Trace Properties")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.name_edit = QLineEdit()
        current_name = self.curve_item.opts.get('name', None)
        if current_name is None:
            cn = getattr(self.curve_item, 'name', None)
            current_name = cn() if callable(cn) else cn
        self.name_edit.setText(current_name or "")
        form.addRow("Legend name:", self.name_edit)

        pen = self.curve_item.opts.get('pen', None)
        if isinstance(pen, QPen):
            self.current_color = pen.color()
            self.current_width = pen.widthF()
            self.current_style = pen.style()
        else:
            mkpen = pg.mkPen(pen)
            self.current_color = mkpen.color()
            self.current_width = max(mkpen.widthF(), 1.0)
            self.current_style = mkpen.style()

        self.color_button = QPushButton()
        self.color_button.setFixedHeight(30)
        self._refresh_color_btn()
        self.color_button.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_button)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(self.current_width)
        form.addRow("Line width:", self.width_spin)

        self.style_combo = QComboBox()
        self.style_combo.addItems(LINE_STYLE_MAP.keys())
        self.style_combo.setCurrentText(LINE_STYLE_REVERSE.get(self.current_style, "Solid"))
        form.addRow("Line style:", self.style_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _refresh_color_btn(self):
        self.color_button.setStyleSheet(
            _color_swatch_qss(self.current_color.name()) + "min-height:30px;"
        )

    def _pick_color(self):
        c = QColorDialog.getColor(self.current_color, self, "Trace Color")
        if c.isValid():
            self.current_color = c
            self._refresh_color_btn()

    def _apply(self):
        style = LINE_STYLE_MAP.get(self.style_combo.currentText(), Qt.SolidLine)
        new_pen = pg.mkPen(self.current_color, width=self.width_spin.value(), style=style)
        new_pen.setCosmetic(True)
        self.curve_item.setPen(new_pen)

        new_name = self.name_edit.text().strip()
        if new_name:
            self.curve_item.opts['name'] = new_name
            legend = getattr(self.plot_widget, 'legend', None)
            if legend is None:
                legend = self.plot_widget.getPlotItem().legend
            if legend:
                try:
                    for sample_item, label_item in legend.items:
                        if sample_item.item is self.curve_item:
                            label_item.setText(new_name)
                            break
                except Exception:
                    pass
        self.accept()


class ScatterEditorDialog(QDialog):
    """Edit scatter points: fill color, symbol shape, size."""

    def __init__(self, scatter_item, plot_widget, parent=None):
        """
        Args:
            scatter_item (Any): The scatter item.
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.scatter_item = scatter_item
        self.plot_widget = plot_widget
        self.setWindowTitle("Edit Points")
        self.setFixedWidth(380)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Point Properties")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        opts = self.scatter_item.opts
        try:
            self.current_color = pg.mkBrush(opts.get('brush', 'r')).color()
        except Exception:
            self.current_color = QColor(255, 0, 0)

        self.color_button = QPushButton()
        self.color_button.setFixedHeight(30)
        self.color_button.setStyleSheet(_color_swatch_qss(self.current_color.name()))
        self.color_button.clicked.connect(self._pick_color)
        form.addRow("Fill color:", self.color_button)

        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(SCATTER_SYMBOLS.keys())
        cur_sym = opts.get('symbol', 'o')
        self.symbol_combo.setCurrentText(SCATTER_SYMBOLS_REVERSE.get(cur_sym, "Circle"))
        form.addRow("Symbol:", self.symbol_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(2, 30)
        self.size_spin.setValue(opts.get('size', 6))
        form.addRow("Size:", self.size_spin)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _pick_color(self):
        c = QColorDialog.getColor(self.current_color, self, "Point Color")
        if c.isValid():
            self.current_color = c
            self.color_button.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        symbol = SCATTER_SYMBOLS.get(self.symbol_combo.currentText(), 'o')
        self.scatter_item.setSymbol(symbol)
        self.scatter_item.setSize(self.size_spin.value())
        self.scatter_item.setBrush(pg.mkBrush(self.current_color))
        self.scatter_item.setPen(pg.mkPen(self.current_color.darker(120), width=1))
        self.accept()


class AxisLabelEditorDialog(QDialog):
    """Edit an axis label: text, units, font, size, bold/italic, color."""

    def __init__(self, plot_widget, axis_name, parent=None):
        """
        Args:
            plot_widget (Any): The plot widget.
            axis_name (Any): The axis name.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.axis_name = axis_name
        self.setWindowTitle(f"Edit {'Y' if axis_name == 'left' else 'X'} Axis")
        self.setFixedWidth(400)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        axis_display = "Y-Axis" if self.axis_name == 'left' else "X-Axis"
        header = QLabel(f"{axis_display} Label Properties")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        ax = self.plot_widget.getPlotItem().getAxis(self.axis_name)

        self.label_edit = QLineEdit(ax.labelText or "")
        form.addRow("Label text:", self.label_edit)

        self.units_edit = QLineEdit(ax.labelUnits or "")
        form.addRow("Units:", self.units_edit)

        self.font_combo = QComboBox()
        self.font_combo.addItems(get_system_font_families())
        self.font_combo.setCurrentText("Times New Roman")
        self.font_combo.setMaxVisibleItems(20)
        form.addRow("Font family:", self.font_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(20)
        form.addRow("Font size:", self.size_spin)

        style_layout = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.bold_check.setChecked(True)
        self.italic_check = QCheckBox("Italic")
        style_layout.addWidget(self.bold_check)
        style_layout.addWidget(self.italic_check)
        style_layout.addStretch()
        form.addRow("Style:", style_layout)

        self.label_color = QColor("#000000")
        self.color_button = QPushButton()
        self.color_button.setFixedHeight(30)
        self.color_button.setStyleSheet(_color_swatch_qss("#000000"))
        self.color_button.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_button)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _pick_color(self):
        c = QColorDialog.getColor(self.label_color, self, "Label Color")
        if c.isValid():
            self.label_color = c
            self.color_button.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        family = self.font_combo.currentText()
        size = self.size_spin.value()
        bold = "bold" if self.bold_check.isChecked() else "normal"
        italic = "italic" if self.italic_check.isChecked() else "normal"
        font_str = f"{italic} {bold} {size}pt {family}"

        text = self.label_edit.text().strip()
        units = self.units_edit.text().strip() or None

        plot_item = self.plot_widget.getPlotItem()
        if units:
            plot_item.setLabel(self.axis_name, text, units=units, color=self.label_color.name(), font=font_str)
        else:
            plot_item.setLabel(self.axis_name, text, color=self.label_color.name(), font=font_str)

        tick_font = QFont(family, size)
        tick_font.setBold(self.bold_check.isChecked())
        tick_font.setItalic(self.italic_check.isChecked())
        ax = plot_item.getAxis(self.axis_name)
        ax.setStyle(tickFont=tick_font, tickTextOffset=10, tickLength=10)
        ax.setTextPen(self.label_color)
        ax.setPen(QPen(self.label_color, 1))

        if not hasattr(self.plot_widget, 'custom_axis_labels'):
            self.plot_widget.custom_axis_labels = {}
        self.plot_widget.custom_axis_labels[self.axis_name] = {
            'text': text, 'units': units, 'font': font_str, 'color': self.label_color.name()}
        self.accept()


class TitleEditorDialog(QDialog):
    """Edit the plot title."""

    def __init__(self, plot_widget, parent=None):
        """
        Args:
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setWindowTitle("Edit Plot Title")
        self.setFixedWidth(400)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Title Properties")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.title_edit = QLineEdit()
        pi = self.plot_widget.getPlotItem()
        self.title_edit.setText(pi.titleLabel.text if pi.titleLabel and pi.titleLabel.text else "")
        form.addRow("Title:", self.title_edit)

        self.font_combo = QComboBox()
        self.font_combo.addItems(get_system_font_families())
        self.font_combo.setCurrentText("Times New Roman")
        self.font_combo.setMaxVisibleItems(20)
        form.addRow("Font:", self.font_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(20)
        form.addRow("Size:", self.size_spin)

        style_layout = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.bold_check.setChecked(True)
        self.italic_check = QCheckBox("Italic")
        style_layout.addWidget(self.bold_check)
        style_layout.addWidget(self.italic_check)
        style_layout.addStretch()
        form.addRow("Style:", style_layout)

        self.title_color = QColor("#000000")
        self.color_button = QPushButton()
        self.color_button.setFixedHeight(30)
        self.color_button.setStyleSheet(_color_swatch_qss("#000000"))
        self.color_button.clicked.connect(self._pick_color)
        form.addRow("Color:", self.color_button)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _pick_color(self):
        c = QColorDialog.getColor(self.title_color, self, "Title Color")
        if c.isValid():
            self.title_color = c
            self.color_button.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        family = self.font_combo.currentText()
        size = self.size_spin.value()
        bold = "bold" if self.bold_check.isChecked() else "normal"
        italic = "italic" if self.italic_check.isChecked() else "normal"
        text = self.title_edit.text().strip()
        font_str = f"{italic} {bold} {size}pt {family}"
        pi = self.plot_widget.getPlotItem()
        if text:
            pi.setTitle(text, color=self.title_color.name(), size=font_str)
        else:
            pi.setTitle('')
        self.accept()


class LegendEditorDialog(QDialog):
    """Edit legend appearance."""

    def __init__(self, plot_widget, parent=None):
        """
        Args:
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setWindowTitle("Edit Legend")
        self.setFixedWidth(350)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Legend Properties")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        legend = getattr(self.plot_widget, 'legend', None)
        self.visible_check = QCheckBox("Show legend")
        self.visible_check.setChecked(legend is not None and legend.isVisible())
        form.addRow(self.visible_check)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 48)
        self.size_spin.setValue(16)
        form.addRow("Font size:", self.size_spin)

        self.text_color = QColor("#000000")
        self.color_button = QPushButton()
        self.color_button.setFixedHeight(30)
        self.color_button.setStyleSheet(_color_swatch_qss("#000000"))
        self.color_button.clicked.connect(self._pick_color)
        form.addRow("Text color:", self.color_button)

        self.bg_alpha = QSlider(Qt.Horizontal)
        self.bg_alpha.setRange(0, 255)
        self.bg_alpha.setValue(150)
        self.bg_alpha_label = QLabel("150")
        self.bg_alpha.valueChanged.connect(lambda v: self.bg_alpha_label.setText(str(v)))
        al = QHBoxLayout()
        al.addWidget(self.bg_alpha)
        al.addWidget(self.bg_alpha_label)
        form.addRow("BG opacity:", al)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _pick_color(self):
        c = QColorDialog.getColor(self.text_color, self, "Legend Text Color")
        if c.isValid():
            self.text_color = c
            self.color_button.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        legend = getattr(self.plot_widget, 'legend', None)
        if legend is None:
            self.accept()
            return
        legend.setVisible(self.visible_check.isChecked())
        sz = f'{self.size_spin.value()}pt'
        try:
            legend.setLabelTextSize(sz)
            legend.setLabelTextColor(self.text_color)
        except Exception:
            pass
        legend.setBrush(pg.mkBrush(255, 255, 255, self.bg_alpha.value()))
        try:
            for s, l in legend.items:
                l.setText(l.text, size=sz, color=self.text_color.name())
        except Exception:
            pass
        self.accept()


class BackgroundEditorDialog(QDialog):
    """Edit background color and grid."""

    def __init__(self, plot_widget, parent=None):
        """
        Args:
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setWindowTitle("Edit Background")
        self.setFixedWidth(320)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Background & Grid")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.bg_color = QColor(self.plot_widget.backgroundBrush().color())
        self.bg_button = QPushButton()
        self.bg_button.setFixedHeight(30)
        self.bg_button.setStyleSheet(_color_swatch_qss(self.bg_color.name()))
        self.bg_button.clicked.connect(self._pick_bg)
        form.addRow("Background:", self.bg_button)

        self.show_x_grid = QCheckBox("Show X grid")
        self.show_y_grid = QCheckBox("Show Y grid")
        form.addRow(self.show_x_grid)
        form.addRow(self.show_y_grid)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _pick_bg(self):
        c = QColorDialog.getColor(self.bg_color, self, "Background Color")
        if c.isValid():
            self.bg_color = c
            self.bg_button.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        self.plot_widget.setBackground(self.bg_color)
        self.plot_widget.getPlotItem().showGrid(
            x=self.show_x_grid.isChecked(), y=self.show_y_grid.isChecked(), alpha=0.2)
        self.accept()


class PlotSettingsDialog(QDialog):

    def __init__(self, plot_widget, parent=None):
        """
        Args:
            plot_widget (Any): The plot widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setWindowTitle("Plot Settings")
        self.setMinimumSize(620, 550)
        _install_theme_subscription(self)
        self._setup_ui()
        self._load_persistent()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self._create_font_tab()
        self._create_grid_tab()
        self._create_traces_tab()

        btn_layout = QHBoxLayout()
        self.reset_button = QPushButton("Reset to Defaults")
        self.apply_button = QPushButton("Apply")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        btn_layout.addWidget(self.reset_button)
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_button)
        btn_layout.addWidget(self.ok_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addLayout(btn_layout)

        self.apply_button.clicked.connect(self._apply_settings)
        self.ok_button.clicked.connect(self._accept_and_apply)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self._reset_defaults)

    # ── Font tab ──────────────────────────────────────────────────────────

    def _create_font_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("Global Font Settings")
        fl = QFormLayout(grp)

        self.global_font_family = QComboBox()
        self.global_font_family.addItems(get_system_font_families())
        self.global_font_family.setCurrentText("Times New Roman")
        self.global_font_family.setMaxVisibleItems(20)

        self.axis_font_size = QSpinBox(); self.axis_font_size.setRange(6,72); self.axis_font_size.setValue(20)
        self.title_font_size = QSpinBox(); self.title_font_size.setRange(6,72); self.title_font_size.setValue(20)
        self.legend_font_size = QSpinBox(); self.legend_font_size.setRange(6,72); self.legend_font_size.setValue(16)

        sl = QHBoxLayout()
        self.global_bold = QCheckBox("Bold"); self.global_bold.setChecked(True)
        self.global_italic = QCheckBox("Italic")
        sl.addWidget(self.global_bold); sl.addWidget(self.global_italic); sl.addStretch()

        self.font_color_button = QPushButton(); self.font_color = QColor("#000000")
        self.font_color_button.setStyleSheet(_tall_color_swatch_qss("#000000"))
        self.font_color_button.clicked.connect(lambda: self._choose_color('font'))

        self.bg_color_button = QPushButton(); self.bg_color = QColor("#FFFFFF")
        self.bg_color_button.setStyleSheet(_tall_color_swatch_qss("#FFFFFF"))
        self.bg_color_button.clicked.connect(lambda: self._choose_color('bg'))

        self.title_text = QLineEdit()

        fl.addRow("Font Family:", self.global_font_family)
        fl.addRow("Axis Font Size:", self.axis_font_size)
        fl.addRow("Title Font Size:", self.title_font_size)
        fl.addRow("Legend Font Size:", self.legend_font_size)
        fl.addRow("Font Style:", sl)
        fl.addRow("Font Color:", self.font_color_button)
        fl.addRow("Background Color:", self.bg_color_button)
        fl.addRow("Title Text:", self.title_text)

        lay.addWidget(grp)
        note = QLabel("Tip: Double-click any element on the plot to edit it directly.")
        note.setStyleSheet(_hint_label_qss())
        lay.addWidget(note)
        self.tab_widget.addTab(w, "Fonts")

    # ── Grid tab ──────────────────────────────────────────────────────────

    def _create_grid_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("Grid Settings")
        gl = QFormLayout(grp)

        self.show_x_grid = QCheckBox("Show X Grid")
        self.show_y_grid = QCheckBox("Show Y Grid")

        self.grid_alpha = QSlider(Qt.Horizontal); self.grid_alpha.setRange(0,255); self.grid_alpha.setValue(50)
        self.grid_alpha_label = QLabel("50")
        self.grid_alpha.valueChanged.connect(lambda v: self.grid_alpha_label.setText(str(v)))
        al = QHBoxLayout(); al.addWidget(self.grid_alpha); al.addWidget(self.grid_alpha_label)

        self.grid_color_button = QPushButton(); self.grid_color = QColor("#808080")
        self.grid_color_button.setStyleSheet(_tall_color_swatch_qss("#808080"))
        self.grid_color_button.clicked.connect(lambda: self._choose_color('grid'))

        self.grid_style = QComboBox()
        self.grid_style.addItems(["Solid","Dashed","Dotted"])

        gl.addRow(self.show_x_grid); gl.addRow(self.show_y_grid)
        gl.addRow("Grid Color:", self.grid_color_button)
        gl.addRow("Grid Style:", self.grid_style)
        gl.addRow("Transparency:", al)

        lay.addWidget(grp)
        self.tab_widget.addTab(w, "Grid")

    # ── Traces tab ────────────────────────────────────────────────────────

    def _create_traces_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        info = QLabel("Edit all traces and scatter points on the current plot:")
        info.setStyleSheet(_hint_label_qss())
        lay.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _p = _app_theme.palette
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{_p.bg_primary};}}"
            f"QScrollArea > QWidget > QWidget{{background:{_p.bg_primary};}}"
        )
        self.traces_container = QWidget()
        self.traces_container.setStyleSheet(f"background:{_p.bg_primary};")
        self.traces_layout = QVBoxLayout(self.traces_container)
        self.traces_layout.setSpacing(6)
        self.traces_layout.setContentsMargins(4,4,4,4)
        scroll.setWidget(self.traces_container)
        lay.addWidget(scroll)

        self._populate_traces()
        self.tab_widget.addTab(w, "Traces")

    def _populate_traces(self):
        while self.traces_layout.count():
            child = self.traces_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        plot_item = self.plot_widget.getPlotItem()
        idx = 0

        for item in plot_item.listDataItems():
            if isinstance(item, pg.ScatterPlotItem):
                continue
            if isinstance(item, (pg.PlotCurveItem, pg.PlotDataItem)):
                self.traces_layout.addWidget(self._curve_row(item, idx))
                idx += 1

        for item in plot_item.items:
            if isinstance(item, pg.ScatterPlotItem):
                self.traces_layout.addWidget(self._scatter_row(item, idx))
                idx += 1

        bar_groups: dict = {}
        for item in plot_item.items:
            if not isinstance(item, pg.BarGraphItem):
                continue
            try:
                w = item.opts.get('width', 0)
                if (not hasattr(w, '__len__') and w == 0) or \
                   (hasattr(w, '__len__') and len(w) and max(w) == 0):
                    continue
            except Exception:
                pass
            name = item.opts.get('_trace_name',
                                  item.opts.get('name', f'Bar {idx}'))
            bar_groups.setdefault(name, []).append(item)

        for name, bars in bar_groups.items():
            self.traces_layout.addWidget(self._bar_row(name, bars, idx))
            idx += 1

        if idx == 0:
            lbl = QLabel("No traces on the current plot.")
            lbl.setStyleSheet(_hint_label_qss() + "padding:20px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.traces_layout.addWidget(lbl)

        self.traces_layout.addStretch()

    def _curve_row(self, item, index):
        """
        Args:
            item (Any): List or table item.
            index (Any): Row or item index.
        Returns:
            object: Result of the operation.
        """
        row = QFrame()
        row.setStyleSheet(_trace_row_qss())
        rl = QHBoxLayout(row); rl.setContentsMargins(8,4,8,4)

        name = item.opts.get('name', f'Trace {index+1}')
        ne = QLineEdit(name or f'Trace {index+1}'); ne.setFixedWidth(180)
        rl.addWidget(QLabel("📈")); rl.addWidget(ne)

        pen = item.opts.get('pen', None)
        color = pg.mkPen(pen).color() if pen else QColor('#000')
        cb = QPushButton(); cb.setFixedSize(30,25); cb._color = color
        cb.setStyleSheet(_color_swatch_qss(color.name()))
        cb.setCursor(Qt.PointingHandCursor)
        def pick(*_args, btn=cb):
            """
            Args:
                btn (Any): The btn.
                *_args (Any): Additional positional arguments.
            """
            c = QColorDialog.getColor(btn._color, self)
            if c.isValid():
                btn._color = c
                btn.setStyleSheet(_color_swatch_qss(c.name()))
        cb.clicked.connect(pick)
        rl.addWidget(cb)

        ws = QDoubleSpinBox(); ws.setRange(0.5,10); ws.setSingleStep(0.5)
        ws.setValue(pg.mkPen(pen).widthF() if pen else 1.0); ws.setFixedWidth(60)
        rl.addWidget(QLabel("W:")); rl.addWidget(ws)

        sc = QComboBox(); sc.addItems(LINE_STYLE_MAP.keys())
        cur_style = pg.mkPen(pen).style() if pen else Qt.SolidLine
        sc.setCurrentText(LINE_STYLE_REVERSE.get(cur_style, "Solid")); sc.setFixedWidth(90)
        rl.addWidget(sc); rl.addStretch()

        ab = QPushButton("Apply"); ab.setFixedWidth(60)
        ab.setStyleSheet(_inline_apply_btn_qss('primary'))
        def apply_c(*_args, itm=item, name_e=ne, col_b=cb, w_s=ws, st_c=sc):
            """
            Args:
                itm (Any): The itm.
                name_e (Any): The name e.
                col_b (Any): The col b.
                w_s (Any): The w s.
                st_c (Any): The st c.
                *_args (Any): Additional positional arguments.
            """
            sty = LINE_STYLE_MAP.get(st_c.currentText(), Qt.SolidLine)
            p = pg.mkPen(col_b._color, width=w_s.value(), style=sty)
            p.setCosmetic(True)
            itm.setPen(p)
            try:
                itm.update()
            except Exception:
                pass
            nn = name_e.text().strip()
            if nn:
                itm.opts['name'] = nn
                legend = (
                    getattr(self.plot_widget, 'legend', None)
                    or self.plot_widget.getPlotItem().legend
                )
                if legend:
                    try:
                        for s, l in legend.items:
                            if s.item is itm:
                                l.setText(nn); break
                    except Exception:
                        pass
            try:
                self.plot_widget.getPlotItem().update()
                self.plot_widget.repaint()
            except Exception:
                pass
        ab.clicked.connect(apply_c)
        rl.addWidget(ab)
        return row

    def _scatter_row(self, item, index):
        """
        Args:
            item (Any): List or table item.
            index (Any): Row or item index.
        Returns:
            object: Result of the operation.
        """
        row = QFrame()
        row.setStyleSheet(_scatter_row_qss())
        rl = QHBoxLayout(row); rl.setContentsMargins(8,4,8,4)
        rl.addWidget(QLabel("⬤")); rl.addWidget(QLabel(f"Points {index+1}"))

        try: color = pg.mkBrush(item.opts.get('brush','r')).color()
        except: color = QColor(255,0,0)

        cb = QPushButton(); cb.setFixedSize(30,25); cb._color = color
        cb.setStyleSheet(_color_swatch_qss(color.name()))
        cb.setCursor(Qt.PointingHandCursor)
        def pick(*_args, btn=cb):
            """
            Args:
                btn (Any): The btn.
                *_args (Any): Additional positional arguments.
            """
            c = QColorDialog.getColor(btn._color, self)
            if c.isValid():
                btn._color = c
                btn.setStyleSheet(_color_swatch_qss(c.name()))
        cb.clicked.connect(pick)
        rl.addWidget(cb)

        sy = QComboBox(); sy.addItems(SCATTER_SYMBOLS.keys())
        sy.setCurrentText(SCATTER_SYMBOLS_REVERSE.get(item.opts.get('symbol','o'), "Circle"))
        sy.setFixedWidth(110)
        rl.addWidget(sy)

        ss = QSpinBox(); ss.setRange(2,30); ss.setValue(item.opts.get('size',6)); ss.setFixedWidth(50)
        rl.addWidget(QLabel("Size:")); rl.addWidget(ss); rl.addStretch()

        ab = QPushButton("Apply"); ab.setFixedWidth(60)
        ab.setStyleSheet(_inline_apply_btn_qss('warn'))
        def apply_s(*_args, itm=item, col_b=cb, sym_c=sy, sz_s=ss):
            """
            Args:
                itm (Any): The itm.
                col_b (Any): The col b.
                sym_c (Any): The sym c.
                sz_s (Any): The sz s.
                *_args (Any): Additional positional arguments.
            """
            itm.setSymbol(SCATTER_SYMBOLS.get(sym_c.currentText(), 'o'))
            itm.setSize(sz_s.value())
            itm.setBrush(pg.mkBrush(col_b._color))
            itm.setPen(pg.mkPen(col_b._color.darker(120), width=1))
            try:
                itm.update()
                self.plot_widget.getPlotItem().update()
                self.plot_widget.repaint()
            except Exception:
                pass
        ab.clicked.connect(apply_s)
        rl.addWidget(ab)
        return row

    def _bar_row(self, name, items, index):
        """One row in the Traces tab for a group of BarGraphItems that
        share the same label (element name or sample name).
        Changing the color and pressing Apply repaints all bars in the group.
        Args:
            name (Any): Name string.
            items (Any): Sequence of items.
            index (Any): Row or item index.
        Returns:
            object: Result of the operation.
        """
        row = QFrame()
        row.setStyleSheet(_scatter_row_qss())
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 4, 8, 4)

        rl.addWidget(QLabel("▊"))

        name_lbl = QLabel(name or f"Bar {index + 1}")
        name_lbl.setFixedWidth(160)
        rl.addWidget(name_lbl)

        try:
            color = pg.mkBrush(items[0].opts.get('brush', 'b')).color()
        except Exception:
            color = QColor(100, 120, 220)

        cb = QPushButton()
        cb.setFixedSize(30, 25)
        cb._color = color
        cb.setStyleSheet(_color_swatch_qss(color.name()))
        cb.setCursor(Qt.PointingHandCursor)

        def pick(*_args, btn=cb):
            """
            Args:
                btn (Any): The btn.
                *_args (Any): Additional positional arguments.
            """
            c = QColorDialog.getColor(btn._color, self, "Bar Color")
            if c.isValid():
                btn._color = c
                btn.setStyleSheet(_color_swatch_qss(c.name()))

        cb.clicked.connect(pick)
        rl.addWidget(cb)
        rl.addStretch()

        ab = QPushButton("Apply")
        ab.setFixedWidth(60)
        ab.setStyleSheet(_inline_apply_btn_qss('warn'))

        def apply_b(*_args, itms=items, col_b=cb):
            """
            Args:
                itms (Any): The itms.
                col_b (Any): The col b.
                *_args (Any): Additional positional arguments.
            """
            c = col_b._color
            alpha = c.alpha() if c.alpha() < 255 else 215
            new_brush = pg.mkBrush(c.red(), c.green(), c.blue(), alpha)
            new_pen   = pg.mkPen('w', width=0.5)
            for itm in itms:
                try:
                    itm.setOpts(brush=new_brush, pen=new_pen)
                    itm.update()
                except Exception:
                    pass
            try:
                self.plot_widget.getPlotItem().update()
                self.plot_widget.repaint()
            except Exception:
                pass

        ab.clicked.connect(apply_b)
        rl.addWidget(ab)
        return row

    # ── Helpers ───────────────────────────────────────────────────────────

    def _choose_color(self, color_type):
        """
        Args:
            color_type (Any): The color type.
        """
        cmap = {'font': (self.font_color, self.font_color_button),
                'bg': (self.bg_color, self.bg_color_button),
                'grid': (self.grid_color, self.grid_color_button)}
        if color_type in cmap:
            cur, btn = cmap[color_type]
            c = QColorDialog.getColor(cur, self)
            if c.isValid():
                btn.setStyleSheet(_tall_color_swatch_qss(c.name()))
                setattr(self, f"{color_type}_color", c)

    def _load_persistent(self):
        if hasattr(self.plot_widget, 'persistent_dialog_settings'):
            s = self.plot_widget.persistent_dialog_settings
            try:
                self.global_font_family.setCurrentText(s.get('global_font_family','Times New Roman'))
                self.axis_font_size.setValue(s.get('axis_font_size',20))
                self.title_font_size.setValue(s.get('title_font_size',20))
                self.legend_font_size.setValue(s.get('legend_font_size',16))
                self.global_bold.setChecked(s.get('global_bold',True))
                self.global_italic.setChecked(s.get('global_italic',False))
                self.font_color = QColor(s.get('font_color','#000000'))
                self.bg_color = QColor(s.get('bg_color','#FFFFFF'))
                self.grid_color = QColor(s.get('grid_color','#808080'))
                self.font_color_button.setStyleSheet(_tall_color_swatch_qss(self.font_color.name()))
                self.bg_color_button.setStyleSheet(_tall_color_swatch_qss(self.bg_color.name()))
                self.grid_color_button.setStyleSheet(_tall_color_swatch_qss(self.grid_color.name()))
                self.title_text.setText(s.get('title_text',''))
                self.show_x_grid.setChecked(s.get('show_x_grid',False))
                self.show_y_grid.setChecked(s.get('show_y_grid',False))
                self.grid_alpha.setValue(s.get('grid_alpha',50))
                self.grid_style.setCurrentText(s.get('grid_style','Solid'))
            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save_persistent(self):
        self.plot_widget.persistent_dialog_settings = {
            'global_font_family': self.global_font_family.currentText(),
            'axis_font_size': self.axis_font_size.value(),
            'title_font_size': self.title_font_size.value(),
            'legend_font_size': self.legend_font_size.value(),
            'global_bold': self.global_bold.isChecked(),
            'global_italic': self.global_italic.isChecked(),
            'font_color': self.font_color.name(),
            'bg_color': self.bg_color.name(),
            'grid_color': self.grid_color.name(),
            'title_text': self.title_text.text(),
            'show_x_grid': self.show_x_grid.isChecked(),
            'show_y_grid': self.show_y_grid.isChecked(),
            'grid_alpha': self.grid_alpha.value(),
            'grid_style': self.grid_style.currentText()}

    def _apply_settings(self):
        try:
            pi = self.plot_widget.getPlotItem()
            self.plot_widget.setBackground(self.bg_color)
            ff = self.global_font_family.currentText()
            ib = self.global_bold.isChecked()
            ii = self.global_italic.isChecked()
            af = QFont(ff, self.axis_font_size.value()); af.setBold(ib); af.setItalic(ii)
            fw = "bold" if ib else "normal"
            fs = "italic" if ii else "normal"

            for an in ['bottom','left']:
                ax = pi.getAxis(an)
                ax.setStyle(tickFont=af, tickTextOffset=10, tickLength=10)
                ax.setTextPen(self.font_color)
                ax.setPen(QPen(self.font_color, 1))

            if hasattr(self.plot_widget, 'custom_axis_labels'):
                for an in ['bottom','left']:
                    if an in self.plot_widget.custom_axis_labels:
                        info = self.plot_widget.custom_axis_labels[an]
                        args = [an, info['text']]
                        kw = {'color': self.font_color.name(),
                              'font': f'{fs} {fw} {self.axis_font_size.value()}pt {ff}'}
                        if info.get('units'):
                            kw['units'] = info['units']
                        pi.setLabel(*args, **kw)
            else:
                pi.setLabel('bottom','Time',units='s',color=self.font_color.name(),
                           font=f'{fs} {fw} {self.axis_font_size.value()}pt {ff}')
                pi.setLabel('left','Intensity',units='counts',color=self.font_color.name(),
                           font=f'{fs} {fw} {self.axis_font_size.value()}pt {ff}')

            if self.show_x_grid.isChecked() or self.show_y_grid.isChecked():
                pi.showGrid(x=self.show_x_grid.isChecked(), y=self.show_y_grid.isChecked(),
                           alpha=self.grid_alpha.value()/255.0)
            else:
                pi.showGrid(x=False, y=False)

            if self.title_text.text():
                pi.setTitle(self.title_text.text(), color=self.font_color.name(),
                           size=f'{fs} {fw} {self.title_font_size.value()}pt {ff}')
            else:
                pi.setTitle('')

            legend = getattr(self.plot_widget, 'legend', None)
            if legend:
                try:
                    lsz = f'{self.legend_font_size.value()}pt'
                    legend.setLabelTextSize(lsz)
                    legend.setLabelTextColor(self.font_color)
                    for s, l in legend.items:
                        l.setText(l.text, size=lsz, color=self.font_color.name())
                except Exception:
                    pass

            pi.getViewBox().updateAutoRange()
            self.plot_widget.repaint()
            self._save_persistent()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error applying settings: {str(e)}")

    def _reset_defaults(self):
        self.global_font_family.setCurrentText("Times New Roman")
        self.axis_font_size.setValue(20); self.title_font_size.setValue(20); self.legend_font_size.setValue(16)
        self.global_bold.setChecked(True); self.global_italic.setChecked(False)
        for c, btn in [("#000000",self.font_color_button),("#FFFFFF",self.bg_color_button),("#808080",self.grid_color_button)]:
            btn.setStyleSheet(_tall_color_swatch_qss(c))
        self.font_color = QColor("#000000"); self.bg_color = QColor("#FFFFFF"); self.grid_color = QColor("#808080")
        self.title_text.setText(""); self.show_x_grid.setChecked(False); self.show_y_grid.setChecked(False)
        self.grid_alpha.setValue(50); self.grid_style.setCurrentText("Solid")
        if hasattr(self.plot_widget, 'persistent_dialog_settings'):
            del self.plot_widget.persistent_dialog_settings

    def _accept_and_apply(self):
        self._apply_settings(); self.accept()

    def closeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        self._save_persistent(); super().closeEvent(event)


class CustomPlotItem(pg.PlotItem):
    def __init__(self, *args, **kwargs):
        """
        Args:
            *args (Any): Additional positional arguments.
            **kwargs (Any): Additional keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.plot_widget = None
        self._settings_action = None

    def getContextMenus(self, event):
        """
        Args:
            event (Any): Qt event object.
        Returns:
            object: Result of the operation.
        """
        menu = super().getContextMenus(event)
        if self.plot_widget is not None:
            existing = [a.text() for a in menu.actions()]
            if "Plot Settings..." not in existing:
                menu.addSeparator()
                if self._settings_action is None:
                    self._settings_action = QAction("Plot Settings...", self.plot_widget)
                    self._settings_action.triggered.connect(self.plot_widget.open_plot_settings)
                menu.addAction(self._settings_action)
        return menu


class ExclusionRegion(pg.LinearRegionItem):
    """
    A vertical shaded band marking an excluded X-range.

    Each region carries a ``scope``:
      - ``'element'`` : applies only to the element currently displayed.
                        Drawn with a red dashed outline.
      - ``'sample'``  : applies to every element in the active sample.
                        Drawn with a thicker blue solid outline so it is
                        visually distinct from element-scope bands.

    Drag the middle to move, drag the edges to resize. Right-click on
    the band for a small menu (Remove / Edit bounds / Change scope /
    Clear all). The widget that owns this region is held as ``_owner``
    so the region can ask the owner to apply the chosen action.
    """

    _STYLES = {
        'element': dict(
            brush=(220, 50, 50, 55),
            hover=(220, 50, 50, 95),
            pen_color='#c62828',
            pen_width=1,
            pen_style=Qt.DashLine,
        ),
        'sample': dict(
            brush=(21, 101, 192, 55),
            hover=(21, 101, 192, 95),
            pen_color='#0d47a1',
            pen_width=2,
            pen_style=Qt.SolidLine,
        ),
    }

    def __init__(self, values, owner, scope='element'):
        """
        Args:
            values (Any): Array or sequence of values.
            owner (Any): The owner.
            scope (Any): The scope.
        """
        scope = scope if scope in self._STYLES else 'element'
        style = self._STYLES[scope]
        super().__init__(
            values=values,
            orientation='vertical',
            brush=pg.mkBrush(*style['brush']),
            hoverBrush=pg.mkBrush(*style['hover']),
            pen=pg.mkPen(style['pen_color'],
                         width=style['pen_width'],
                         style=style['pen_style']),
            movable=True,
            bounds=None,
        )
        self.setZValue(50)
        self._owner = owner
        self._scope = scope

    # ── Scope ────────────────────────────────────────────────────────
    def scope(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._scope

    def set_scope(self, scope):
        """Change scope in-place (updates the visual styling).

        Notifies the owner so MainWindow can move the region between
        its element-scope and sample-scope bookkeeping stores.
        Args:
            scope (Any): The scope.
        """
        if scope not in self._STYLES or scope == self._scope:
            return
        self._scope = scope
        style = self._STYLES[scope]
        try:
            self.setBrush(pg.mkBrush(*style['brush']))
            self.hoverBrush = pg.mkBrush(*style['hover'])
            new_pen = pg.mkPen(style['pen_color'],
                               width=style['pen_width'],
                               style=style['pen_style'])
            for line in getattr(self, 'lines', []):
                try:
                    line.setPen(new_pen)
                except Exception:
                    pass
            self.update()
        except Exception:
            pass
        if self._owner is not None:
            try:
                self._owner._emit_exclusion_changed()
            except Exception:
                pass

    # ── Right-click menu ─────────────────────────────────────────────
    def mouseClickEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        try:
            if ev.button() == Qt.RightButton:
                ev.accept()
                self._show_context_menu(ev)
                return
        except Exception:
            pass
        super().mouseClickEvent(ev)

    def _show_context_menu(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        menu = QMenu()
        act_remove = menu.addAction("Remove this region")
        act_edit = menu.addAction("Edit bounds…")

        menu.addSeparator()
        scope_menu = menu.addMenu("Change scope")
        act_scope_element = scope_menu.addAction("For this element only")
        act_scope_element.setCheckable(True)
        act_scope_element.setChecked(self._scope == 'element')
        act_scope_sample = scope_menu.addAction(
            "For this sample (all elements)")
        act_scope_sample.setCheckable(True)
        act_scope_sample.setChecked(self._scope == 'sample')

        menu.addSeparator()
        act_clear = menu.addAction("Clear all exclusion regions")

        try:
            from PySide6.QtCore import QPoint
            sp = ev.screenPos()
            gp = QPoint(int(sp.x()), int(sp.y()))
        except Exception:
            from PySide6.QtGui import QCursor
            gp = QCursor.pos()

        chosen = menu.exec(gp)
        if chosen is act_remove:
            if self._owner is not None:
                self._owner.remove_exclusion_region(self)
        elif chosen is act_edit:
            self._edit_bounds_dialog()
        elif chosen is act_scope_element:
            self.set_scope('element')
        elif chosen is act_scope_sample:
            self.set_scope('sample')
        elif chosen is act_clear:
            if self._owner is not None:
                self._owner.clear_exclusion_regions()

    def _edit_bounds_dialog(self):
        lo, hi = sorted(self.getRegion())
        dlg = QDialog()
        dlg.setWindowTitle("Edit exclusion region")
        try:
            dlg.setStyleSheet(_editor_dialog_qss())
        except Exception:
            pass

        form = QFormLayout()
        sb_lo = QDoubleSpinBox()
        sb_lo.setRange(-1e12, 1e12); sb_lo.setDecimals(6); sb_lo.setValue(lo)
        sb_hi = QDoubleSpinBox()
        sb_hi.setRange(-1e12, 1e12); sb_hi.setDecimals(6); sb_hi.setValue(hi)
        form.addRow("Start:", sb_lo)
        form.addRow("End:", sb_hi)

        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        try:
            ok_btn.setStyleSheet(_editor_ok_button_qss())
            cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        except Exception:
            pass
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        btns.addStretch(1); btns.addWidget(ok_btn); btns.addWidget(cancel_btn)

        layout = QVBoxLayout(dlg)
        layout.addLayout(form)
        layout.addLayout(btns)

        if dlg.exec() == QDialog.Accepted:
            a = sb_lo.value(); b = sb_hi.value()
            if a > b:
                a, b = b, a
            self.setRegion((a, b))


class EnhancedPlotWidget(pg.PlotWidget):
    exclusionRegionsChanged = Signal()

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        self.custom_plot_item = CustomPlotItem()
        super().__init__(parent, plotItem=self.custom_plot_item)
        self.custom_plot_item.plot_widget = self
        self.setup_appearance()
        self.setup_interaction_features()
        self.data_items = {}
        self.original_range = None
        self.custom_settings = {}
        self.persistent_dialog_settings = {}

        self._excluded_regions = []
        self._suppress_exclusion_signal = False
        self._last_context_menu_x = None
        self._install_exclusion_context_menu()

    def setup_appearance(self):
        self.setBackground('white')
        pi = self.getPlotItem()
        pi.showGrid(x=False, y=False)
        pi.hideButtons()
        pi.getAxis('left').setGrid(False)
        pi.getAxis('bottom').setGrid(False)
        pi.getAxis('left').enableAutoSIPrefix(False)

        axis_pen = QPen(QColor("#000000"), 1)
        text_color = QColor("#000000")
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)

        for axis in ['left', 'bottom']:
            ax = pi.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setFont(tick_font)
            ax.setStyle(tickFont=tick_font, tickTextOffset=10, tickLength=10)

        self.setLabel('left', 'Intensity', units='counts', color="#000000",
                       font='bold 20pt Times New Roman')
        self.setLabel('bottom', 'Time', units='s', color="#000000",
                       font='bold 20pt Times New Roman')

        self.legend = self.addLegend(offset=(-30, 30))
        self.legend.setLabelTextColor(text_color)
        self.legend.setLabelTextSize('16pt')
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.legend.setPen(pg.mkPen(color="#000000", width=1, style=Qt.SolidLine, cosmetic=True, alpha=100))

    def setup_interaction_features(self):
        self.setMouseEnabled(x=True, y=True)
        vb = self.getPlotItem().getViewBox()
        vb.setMouseMode(vb.RectMode)
        try:
            self.vertical_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#000000", width=0.5))
            self.horizontal_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#000000", width=0.5))
            self.addItem(self.vertical_line)
            self.addItem(self.horizontal_line)
            self.scene().sigMouseMoved.connect(self.mouse_moved)
        except Exception as e:
            print(f"Warning: Could not setup crosshair: {e}")
        self._install_autorange_button()

    # ── Auto-scale corner button ──────────────────────────────────────────

    def _install_autorange_button(self):
        """Overlay a small auto-scale button in the top-right corner."""
        btn = QPushButton("⤢", self)
        btn.setFixedSize(24, 24)
        btn.setToolTip("Auto-scale (View All)")
        btn.setStyleSheet(
            "QPushButton{background:rgba(50,50,50,150);color:#ccc;"
            "border:1px solid #555;border-radius:3px;"
            "font-size:13px;padding:0;}"
            "QPushButton:hover{background:rgba(90,90,90,220);color:#fff;}"
            "QPushButton:pressed{background:rgba(30,30,30,220);}"
        )
        btn.clicked.connect(
            lambda: self.getPlotItem().getViewBox().autoRange())
        btn.raise_()
        self._autorange_btn = btn
        self._reposition_autorange_btn()

    def _reposition_autorange_btn(self):
        if getattr(self, '_autorange_btn', None) is not None:
            m = 6
            self._autorange_btn.move(
                self.width() - self._autorange_btn.width() - m, m)
            self._autorange_btn.raise_()

    def resizeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        super().resizeEvent(event)
        self._reposition_autorange_btn()

    # ── Exclusion regions ────────────────────────────────────────────────

    def _install_exclusion_context_menu(self):
        """
        Add 'Add exclusion region here (this element / whole sample)' and
        'Clear all exclusion regions' entries to the ViewBox right-click
        menu.

        We also remember the X-coordinate of the click so 'Add here' can
        place the new band under the cursor.
        """
        try:
            vb = self.getPlotItem().getViewBox()
            menu = vb.menu

            menu.addSeparator()

            self._action_add_exclusion_element = QAction(
                "Add exclusion region here (this element)", menu)
            self._action_add_exclusion_element.triggered.connect(
                lambda: self._add_exclusion_region_at_cursor(scope='element'))
            menu.addAction(self._action_add_exclusion_element)

            self._action_add_exclusion_sample = QAction(
                "Add exclusion region here (whole sample)", menu)
            self._action_add_exclusion_sample.triggered.connect(
                lambda: self._add_exclusion_region_at_cursor(scope='sample'))
            menu.addAction(self._action_add_exclusion_sample)

            self._action_clear_exclusions = QAction(
                "Clear all exclusion regions", menu)
            self._action_clear_exclusions.triggered.connect(
                self.clear_exclusion_regions)
            menu.addAction(self._action_clear_exclusions)

            menu.aboutToShow.connect(self._capture_context_menu_position)
        except Exception as e:
            print(f"Warning: Could not install exclusion context menu: {e}")

    def _capture_context_menu_position(self):
        """Cache the data-X under the cursor when the context menu opens."""
        try:
            from PySide6.QtGui import QCursor
            vb = self.getPlotItem().getViewBox()
            global_pos = QCursor.pos()
            scene_pos = self.mapToScene(self.mapFromGlobal(global_pos))
            data_pos = vb.mapSceneToView(scene_pos)
            self._last_context_menu_x = float(data_pos.x())
        except Exception:
            self._last_context_menu_x = None

    def _add_exclusion_region_at_cursor(self, scope='element'):
        """Create a new band centred on the last right-click X-position.

        Falls back to the centre of the current X view-range if the
        click position couldn't be captured. Width defaults to 5% of the
        current X-range so the band is immediately visible and grabbable.
        Args:
            scope (Any): The scope.
        """
        try:
            vb = self.getPlotItem().getViewBox()
            (x_min, x_max), _ = vb.viewRange()
            span = (x_max - x_min) * 0.05
            if span <= 0:
                span = 1.0
            cx = (self._last_context_menu_x
                  if self._last_context_menu_x is not None
                  else 0.5 * (x_min + x_max))
            self.add_exclusion_region(cx - span / 2.0, cx + span / 2.0,
                                      scope=scope)
        except Exception as e:
            print(f"Warning: Could not add exclusion region: {e}")

    def add_exclusion_region(self, x_min, x_max, scope='element'):
        """Add a new exclusion band spanning [x_min, x_max] (data coords).

        ``scope`` is either ``'element'`` (red, applies only to the
        currently displayed element) or ``'sample'`` (blue, applies to
        every element in the sample). MainWindow uses these to decide
        which signals to mask before particle detection.

        Returns the created ExclusionRegion. Emits exclusionRegionsChanged.
        Args:
            x_min (Any): The x min.
            x_max (Any): The x max.
            scope (Any): The scope.
        """
        try:
            x_min = float(x_min); x_max = float(x_max)
            if x_min > x_max:
                x_min, x_max = x_max, x_min
            region = ExclusionRegion(values=(x_min, x_max), owner=self,
                                     scope=scope)
            self.addItem(region, ignoreBounds=True)
            region.sigRegionChangeFinished.connect(self._on_region_edited)
            self._excluded_regions.append(region)
            self._emit_exclusion_changed()
            return region
        except Exception as e:
            print(f"Warning: add_exclusion_region failed: {e}")
            return None

    def remove_exclusion_region(self, region):
        """Remove a single exclusion band. Emits exclusionRegionsChanged.
        Args:
            region (Any): The region.
        """
        try:
            if region in self._excluded_regions:
                self._excluded_regions.remove(region)
            try:
                self.removeItem(region)
            except Exception:
                pass
            self._emit_exclusion_changed()
        except Exception as e:
            print(f"Warning: remove_exclusion_region failed: {e}")

    def clear_exclusion_regions(self):
        """Remove every exclusion band. Emits exclusionRegionsChanged."""
        if not self._excluded_regions:
            return
        for region in list(self._excluded_regions):
            try:
                self.removeItem(region)
            except Exception:
                pass
        self._excluded_regions.clear()
        self._emit_exclusion_changed()

    def get_exclusion_regions(self):
        """Return excluded X-ranges as a list of (x_min, x_max, scope).

        Bands are returned in the order they were added so MainWindow can
        match per-region scope without re-merging. (Merging happens only
        in get_exclusion_mask, which is what cares about it.)
        Returns:
            object: Result of the operation.
        """
        out = []
        for r in self._excluded_regions:
            try:
                lo, hi = sorted(r.getRegion())
                out.append((float(lo), float(hi), r.scope()))
            except Exception:
                continue
        return out

    def set_exclusion_regions(self, regions):
        """Replace the current set of exclusion bands with the given list.

        ``regions`` is an iterable whose elements may be either:
          - (x_min, x_max)               -> implicitly scope='element'
          - (x_min, x_max, scope)        -> explicit scope
          - {'bounds': (x0, x1), 'scope': ...}  -> dict form

        Used by MainWindow when the active sample or element changes —
        it rebuilds the visible band set from its bookkeeping store.

        Emits exclusionRegionsChanged exactly once at the end.
        Args:
            regions (Any): The regions.
        """
        self._suppress_exclusion_signal = True
        try:
            self.clear_exclusion_regions()
            for entry in (regions or []):
                if isinstance(entry, dict):
                    lo, hi = entry.get('bounds', (None, None))
                    sc = entry.get('scope', 'element')
                else:
                    if len(entry) == 3:
                        lo, hi, sc = entry
                    else:
                        lo, hi = entry; sc = 'element'
                if lo is None or hi is None:
                    continue
                self.add_exclusion_region(lo, hi, scope=sc)
        finally:
            self._suppress_exclusion_signal = False
        self._emit_exclusion_changed()

    def get_exclusion_mask(self, x_array):
        """Boolean mask the same length as `x_array`.

        True  = keep this sample (NOT inside any exclusion band)
        False = exclude this sample (inside at least one band)

        Note: this mask is built from ALL visible bands regardless of
        scope. Per-element masking on the back-end is MainWindow's job.
        Args:
            x_array (Any): The x array.
        Returns:
            object: Result of the operation.
        """
        x = np.asarray(x_array)
        mask = np.ones(len(x), dtype=bool)
        for lo, hi, _scope in self.get_exclusion_regions():
            mask &= ~((x >= lo) & (x <= hi))
        return mask

    def _on_region_edited(self, *_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        self._emit_exclusion_changed()

    def _emit_exclusion_changed(self):
        if not self._suppress_exclusion_signal:
            try:
                self.exclusionRegionsChanged.emit()
            except Exception:
                pass

    # ── Override clear() so exclusion bands + crosshair survive ──────────
    def clear(self):
        detached = list(self._excluded_regions)
        for region in detached:
            try:
                try:
                    region.sigRegionChangeFinished.disconnect(
                        self._on_region_edited)
                except Exception:
                    pass
                self.removeItem(region)
            except Exception:
                pass

        super().clear()

        try:
            if hasattr(self, 'vertical_line') and self.vertical_line is not None:
                self.addItem(self.vertical_line)
            if hasattr(self, 'horizontal_line') and self.horizontal_line is not None:
                self.addItem(self.horizontal_line)
        except Exception:
            pass

        self._suppress_exclusion_signal = True
        try:
            for region in detached:
                try:
                    self.addItem(region, ignoreBounds=True)
                    region.sigRegionChangeFinished.connect(
                        self._on_region_edited)
                except Exception:
                    pass
        finally:
            self._suppress_exclusion_signal = False

    def open_plot_settings(self):
        PlotSettingsDialog(self, self.parent()).exec()

    # ── Double-click editing ──────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        """
        Hit-detection priority:
          0. Inside an exclusion region → swallow (let region handle it)
          1. Title → TitleEditorDialog
          2. Left axis → AxisLabelEditorDialog('left')
          3. Bottom axis → AxisLabelEditorDialog('bottom')
          4. Legend → LegendEditorDialog
          5. Near scatter → ScatterEditorDialog
          6. Near curve → TraceEditorDialog
          7. Empty area → BackgroundEditorDialog
        Args:
            event (Any): Qt event object.
        """
        try:
            pos = event.position() if hasattr(event, 'position') else event.pos()
            scene_pos = self.mapToScene(pos.toPoint())
            pi = self.getPlotItem()

            try:
                vb = pi.getViewBox()
                data_pos = vb.mapSceneToView(scene_pos)
                cx = float(data_pos.x())
                for lo, hi, _scope in self.get_exclusion_regions():
                    if lo <= cx <= hi:
                        event.accept()
                        return
            except Exception:
                pass

            tl = pi.titleLabel
            if tl and tl.isVisible():
                if tl.mapRectToScene(tl.boundingRect()).contains(scene_pos):
                    TitleEditorDialog(self, self.parent()).exec()
                    event.accept(); return

            la = pi.getAxis('left')
            if la.mapRectToScene(la.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(self, 'left', self.parent()).exec()
                event.accept(); return

            ba = pi.getAxis('bottom')
            if ba.mapRectToScene(ba.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(self, 'bottom', self.parent()).exec()
                event.accept(); return

            legend = getattr(self, 'legend', None)
            if legend and legend.isVisible():
                try:
                    if legend.mapRectToScene(legend.boundingRect()).contains(scene_pos):
                        LegendEditorDialog(self, self.parent()).exec()
                        event.accept(); return
                except Exception:
                    pass

            scat = self._find_closest_scatter(scene_pos)
            if scat is not None:
                ScatterEditorDialog(scat, self, self.parent()).exec()
                event.accept(); return

            curve = self._find_closest_curve(scene_pos)
            if curve is not None:
                TraceEditorDialog(curve, self, self.parent()).exec()
                event.accept(); return

            BackgroundEditorDialog(self, self.parent()).exec()
            event.accept()

        except Exception as e:
            print(f"Warning: Double-click handler error: {e}")
            super().mouseDoubleClickEvent(event)

    def _find_closest_scatter(self, scene_pos, threshold_px=20):
        """
        Args:
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        pi = self.getPlotItem()
        vb = pi.getViewBox()
        dp = vb.mapSceneToView(scene_pos)
        mx, my = dp.x(), dp.y()
        vr = vb.viewRange()
        xr = vr[0][1] - vr[0][0]
        yr = vr[1][1] - vr[1][0]
        if xr == 0 or yr == 0:
            return None
        best = None; best_d = float('inf')
        for item in pi.items:
            if not isinstance(item, pg.ScatterPlotItem):
                continue
            pts = item.data
            if pts is None or len(pts) == 0:
                continue
            try:
                xd = np.array([p[0] for p in pts])
                yd = np.array([p[1] for p in pts])
            except (IndexError, TypeError):
                try: xd = pts['x']; yd = pts['y']
                except: continue
            dx = (xd - mx) / xr; dy = (yd - my) / yr
            dists = np.sqrt(dx**2 + dy**2)
            mi = np.argmin(dists); md = dists[mi]
            px = md * self.width()
            if px < threshold_px and md < best_d:
                best_d = md; best = item
        return best

    def _find_closest_curve(self, scene_pos, threshold_px=15):
        """
        Args:
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        pi = self.getPlotItem()
        vb = pi.getViewBox()
        dp = vb.mapSceneToView(scene_pos)
        mx, my = dp.x(), dp.y()
        vr = vb.viewRange()
        xr = vr[0][1] - vr[0][0]
        yr = vr[1][1] - vr[1][0]
        if xr == 0 or yr == 0:
            return None
        best = None; best_d = float('inf')
        for item in pi.listDataItems():
            if isinstance(item, pg.ScatterPlotItem):
                continue
            if not isinstance(item, (pg.PlotCurveItem, pg.PlotDataItem)):
                continue
            if isinstance(item, pg.PlotDataItem):
                xd, yd = item.getData()
            else:
                xd = item.xData; yd = item.yData
            if xd is None or yd is None or len(xd) == 0:
                continue
            dx = (xd - mx) / xr; dy = (yd - my) / yr
            dists = np.sqrt(dx**2 + dy**2)
            mi = np.argmin(dists); md = dists[mi]
            px = md * self.width()
            if px < threshold_px and md < best_d:
                best_d = md; best = item
        return best

    # ── Wheel zoom ────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        try:
            xr, yr = self.getPlotItem().getViewBox().viewRange()
            zf = 0.5 if event.angleDelta().y() > 0 else 2.0
            mp = self.getPlotItem().vb.mapSceneToView(event.position())
            mx, my = mp.x(), mp.y()
            pr = self.getPlotItem().vb.sceneBoundingRect()
            rx = (event.position().x() - pr.left()) / pr.width()
            ry = (event.position().y() - pr.top()) / pr.height()
            m = 0.1
            if rx >= 0 and rx <= 1 and ry > (1 - m):
                self.getPlotItem().setXRange(mx - (mx - xr[0]) * zf, mx + (xr[1] - mx) * zf, padding=0)
            elif ry >= 0 and ry <= 1 and rx < m:
                self.getPlotItem().setYRange(my - (my - yr[0]) * zf, my + (yr[1] - my) * zf, padding=0)
            event.accept()
        except Exception as e:
            print(f"Warning: wheel zoom error: {e}")

    def update_plot(self, time_array, data):
        """
        Args:
            time_array (Any): The time array.
            data (Any): Input data.
        """
        if time_array is None or not data:
            return
        colors = ['#3498db','#2ecc71','#e74c3c','#9b59b6','#f1c40f','#1abc9c','#e67e22']
        for mass in list(self.data_items.keys()):
            if mass not in data:
                self.removeItem(self.data_items[mass]); del self.data_items[mass]
        for i, (mass, signals) in enumerate(data.items()):
            try:
                color = QColor(colors[i % len(colors)])
                if len(signals) == 0 or len(time_array) == 0: continue
                signals = np.nan_to_num(signals, nan=0.0)
                try: signals_smooth = self.smooth_data(signals)
                except: signals_smooth = signals
                ml = min(len(time_array), len(signals_smooth))
                tap = time_array[:ml]; ss = signals_smooth[:ml]
                pen = pg.mkPen(color=color, width=1, style=Qt.SolidLine)
                if mass in self.data_items:
                    self.data_items[mass].setData(tap, ss); self.data_items[mass].setPen(pen)
                else:
                    pi = pg.PlotDataItem(tap, ss, pen=pen, name=f'Mass {mass}', antialias=True)
                    self.addItem(pi); self.data_items[mass] = pi
            except Exception as e:
                print(f"Warning: Error plotting mass {mass}: {e}")
        if self.original_range is None:
            self.original_range = self.viewRange()

    def mouse_moved(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        try:
            if self.sceneBoundingRect().contains(pos):
                mp = self.getPlotItem().vb.mapSceneToView(pos)
                self.vertical_line.setPos(mp.x()); self.horizontal_line.setPos(mp.y())
        except: pass

    def clear_plot(self):
        try:
            for item in self.data_items.values(): self.removeItem(item)
            self.data_items.clear(); self.original_range = None
        except Exception as e:
            print(f"Warning: Error clearing plot: {e}")


class BasicPlotWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setup_basic_appearance()
        self.data_items = {}
        self.persistent_dialog_settings = {}

    def setup_basic_appearance(self):
        self.setBackground('white')
        pi = self.getPlotItem(); pi.showGrid(x=False, y=False)
        pi.hideButtons()
        ap = QPen(QColor("#000000"), 1); tc = QColor("#000000")
        tf = QFont('Times New Roman', 20); tf.setBold(True)
        for axis in ['left','bottom']:
            ax = pi.getAxis(axis); ax.setPen(ap); ax.setTextPen(tc); ax.setFont(tf)
            ax.setStyle(tickFont=tf, tickTextOffset=10, tickLength=10)
        self.setLabel('left','Intensity (counts)',color="#000000",font='bold 20pt Times New Roman')
        self.setLabel('bottom','Time (s)',color="#000000",font='bold 20pt Times New Roman')
        self.setMouseEnabled(x=True, y=False)
        self._install_autorange_button()

    def _install_autorange_button(self):
        btn = QPushButton("⤢", self)
        btn.setFixedSize(24, 24)
        btn.setToolTip("Auto-scale (View All)")
        btn.setStyleSheet(
            "QPushButton{background:rgba(50,50,50,150);color:#ccc;"
            "border:1px solid #555;border-radius:3px;"
            "font-size:13px;padding:0;}"
            "QPushButton:hover{background:rgba(90,90,90,220);color:#fff;}"
            "QPushButton:pressed{background:rgba(30,30,30,220);}"
        )
        btn.clicked.connect(
            lambda: self.getPlotItem().getViewBox().autoRange())
        btn.raise_()
        self._autorange_btn = btn
        self._reposition_autorange_btn()

    def _reposition_autorange_btn(self):
        if getattr(self, '_autorange_btn', None) is not None:
            m = 6
            self._autorange_btn.move(
                self.width() - self._autorange_btn.width() - m, m)
            self._autorange_btn.raise_()

    def resizeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        super().resizeEvent(event)
        self._reposition_autorange_btn()

    def update_plot(self, time_array, data):
        """
        Args:
            time_array (Any): The time array.
            data (Any): Input data.
        """
        if time_array is None or not data: return
        colors = ['b','g','r','c','m','y']
        for mass in list(self.data_items.keys()):
            if mass not in data: self.removeItem(self.data_items[mass]); del self.data_items[mass]
        for i, (mass, signals) in enumerate(data.items()):
            c = colors[i % len(colors)]
            if len(signals) == 0 or len(time_array) == 0: continue
            ml = min(len(time_array), len(signals))
            ta = time_array[:ml]; s = signals[:ml]
            if mass in self.data_items: self.data_items[mass].setData(ta, s)
            else:
                pi = pg.PlotDataItem(ta, s, pen=c, name=str(mass))
                self.addItem(pi); self.data_items[mass] = pi

    def clear_plot(self):
        for i in self.data_items.values(): self.removeItem(i)
        self.data_items.clear()

    def setTitle(self, title):
        """
        Args:
            title (Any): Window or dialog title.
        """
        self.getPlotItem().setTitle(title)


class CalibrationPlotWidget(EnhancedPlotWidget):
    """
    Calibration plot with interactive exclusion of outlier points.
    """

   
    point_exclusion_toggled = Signal(int)

    _DOUBLE_CLICK_MS = 350

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._x = np.array([])
        self._y = np.array([])
        self._y_std = np.array([])
        self._y_fit = np.array([])
        self._excluded = set()
        self._outliers = set()
        self._folder_names = []
        self._last_fit_stats = None
        self._last_unit_label = None
        self._pending_click_index = None

        self._setup_calibration_appearance()
        self._build_calibration_items()

        from PySide6.QtCore import QTimer
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._emit_pending_click)

        self.getPlotItem().getViewBox().sigRangeChanged.connect(
            lambda *_: self._reposition_equation())


    def setup_interaction_features(self):
        """Override: calibration plot uses no crosshair lines."""
        self.setMouseEnabled(x=True, y=True)
        vb = self.getPlotItem().getViewBox()
        vb.setMouseMode(vb.RectMode)
        self.vertical_line = None
        self.horizontal_line = None
        self._install_autorange_button()

    def _setup_calibration_appearance(self):
        self.setBackground('white')
        pi = self.getPlotItem()
        pi.showGrid(x=False, y=False)
        pi.hideButtons()
        ap = QPen(QColor("#000000"), 1)
        tc = QColor("#000000")
        tf = QFont('Times New Roman', 20)
        tf.setBold(True)
        for axis in ['left', 'bottom']:
            ax = pi.getAxis(axis)
            ax.setPen(ap)
            ax.setTextPen(tc)
            ax.setFont(tf)
            ax.setStyle(tickFont=tf, tickTextOffset=10, tickLength=10)
        self.legend = self.addLegend()
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.legend.setPen(pg.mkPen(color="#000000", width=1, alpha=100))

    # ── Persistent plot items ────────────────────────────────────────────

    def _build_calibration_items(self):
        self._err_item = pg.ErrorBarItem(pen=pg.mkPen((90, 90, 90), width=1))
        self.addItem(self._err_item)

        self._fit_line = pg.PlotDataItem(
            pen=pg.mkPen('#e53935', width=2),
            name='Fit',
        )
        self.addItem(self._fit_line)

        self._scatter_outliers = pg.ScatterPlotItem(
            size=22, symbol='o',
            pen=pg.mkPen('#fb8c00', width=2),
            brush=pg.mkBrush(0, 0, 0, 0),
        )
        self.addItem(self._scatter_outliers)

        self._scatter_included = pg.ScatterPlotItem(
            size=12, symbol='o',
            pen=pg.mkPen('w', width=1),
            brush=pg.mkBrush('#1e88e5'),
            hoverable=True,
            name='Included',
        )
        self.addItem(self._scatter_included)

        self._scatter_excluded = pg.ScatterPlotItem(
            size=14, symbol='x',
            pen=pg.mkPen('#9e9e9e', width=2),
            brush=pg.mkBrush(0, 0, 0, 0),
            hoverable=True,
            name='Excluded',
        )
        self.addItem(self._scatter_excluded)

        self._equation_text = pg.TextItem(anchor=(0, 0), color='#333333')
        self._equation_text.setFont(QFont('Times New Roman', 12))
        self.addItem(self._equation_text, ignoreBounds=True)

        self._tooltip = pg.TextItem(
            anchor=(0, 1),
            color='#000000',
            fill=pg.mkBrush(255, 255, 220, 230),
            border=pg.mkPen('#666666'),
        )
        self._tooltip.setFont(QFont('Helvetica', 10))
        self._tooltip.setZValue(100)
        self.addItem(self._tooltip, ignoreBounds=True)
        self._tooltip.setVisible(False)

        self._scatter_included.sigClicked.connect(self._on_scatter_clicked)
        self._scatter_excluded.sigClicked.connect(self._on_scatter_clicked)

    # ── Public API ───────────────────────────────────────────────────────

    def setLabel(self, axis, text, units=None, color=None, font=None):
        """
        Args:
            axis (Any): The axis.
            text (Any): Text string.
            units (Any): The units.
            color (Any): Colour value.
            font (Any): Font object.
        """
        kw = {}
        if units: kw['units'] = units
        if color: kw['color'] = color
        if font: kw['font'] = font
        self.getPlotItem().setLabel(axis, text, **kw)

    def setTitle(self, title):
        """
        Args:
            title (Any): Window or dialog title.
        """
        self.getPlotItem().setTitle(title)

    def update_plot(self, x_data, y_data, y_std, method='zero', y_fit=None,
                    key="Data", *,
                    excluded_indices=None, folder_names=None, fit_stats=None,
                    outlier_indices=None, unit_label=None):
        """
        Refresh the plot with new data.

        The first six arguments match the original signature so existing
        callers keep working. The keyword-only args below are the new
        interactive-plot features; pass them to get the new behaviour,
        omit them to get the old look.

        Args:
            excluded_indices: iterable of ints; points rendered as grey X.
            folder_names: list[str] same length as x_data, used in tooltip.
            fit_stats: dict with 'slope', 'intercept', 'r_squared' for the
                on-plot equation annotation.
            outlier_indices: iterable of ints; orange-ring overlay.
            unit_label: e.g. 'ppb'; appears in the equation + tooltip.
        """
        x = np.asarray(x_data, dtype=float)
        y = np.asarray(y_data, dtype=float)
        y_std_arr = (np.asarray(y_std, dtype=float)
                     if y_std is not None and len(y_std)
                     else np.zeros_like(y))
        y_fit_arr = (np.asarray(y_fit, dtype=float)
                     if y_fit is not None and len(y_fit)
                     else np.zeros_like(y))

        self._x = x
        self._y = y
        self._y_std = y_std_arr
        self._y_fit = y_fit_arr
        self._folder_names = (list(folder_names) if folder_names
                              else [f"Point {i + 1}" for i in range(len(x))])
        self._excluded = set(int(i) for i in (excluded_indices or []))
        self._outliers = set(int(i) for i in (outlier_indices or []))
        self._last_fit_stats = fit_stats
        self._last_unit_label = unit_label

        if method:
            self._fit_line.opts['name'] = f'{str(method).capitalize()} fit'

        self._redraw_markers()
        self._redraw_fit_line()
        self._redraw_equation()
        self.getPlotItem().getViewBox().autoRange()

    def clear_plot(self):
        self._x = np.array([])
        self._y = np.array([])
        self._y_std = np.array([])
        self._y_fit = np.array([])
        self._excluded.clear()
        self._outliers.clear()
        self._folder_names = []
        self._last_fit_stats = None
        self._last_unit_label = None

        self._scatter_included.setData([], [])
        self._scatter_excluded.setData([], [])
        self._scatter_outliers.setData([], [])
        self._fit_line.setData([], [])
        self._err_item.setData(x=np.array([]), y=np.array([]),
                               height=np.array([]))
        self._equation_text.setText('')
        self._tooltip.setVisible(False)


    def mouseDoubleClickEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if self._click_timer.isActive():
            self._click_timer.stop()
        self._pending_click_index = None
        super().mouseDoubleClickEvent(event)

    # ── Redraw helpers ──────────────────────────────────────────────────

    def _redraw_markers(self):
        x, y = self._x, self._y
        if len(x) == 0:
            self._scatter_included.setData([], [])
            self._scatter_excluded.setData([], [])
            self._scatter_outliers.setData([], [])
            self._err_item.setData(x=np.array([]), y=np.array([]),
                                   height=np.array([]))
            return

        included_idx = [i for i in range(len(x)) if i not in self._excluded]
        excluded_idx = [i for i in range(len(x)) if i in self._excluded]

        inc_spots = [{'pos': (x[i], y[i]), 'data': int(i)}
                     for i in included_idx]
        exc_spots = [{'pos': (x[i], y[i]), 'data': int(i)}
                     for i in excluded_idx]
        self._scatter_included.setData(inc_spots)
        self._scatter_excluded.setData(exc_spots)

        outlier_pts = [i for i in included_idx if i in self._outliers]
        if outlier_pts:
            self._scatter_outliers.setData(x[outlier_pts], y[outlier_pts])
        else:
            self._scatter_outliers.setData([], [])

        if included_idx:
            inc = np.array(included_idx)
            self._err_item.setData(
                x=x[inc], y=y[inc],
                height=2 * self._y_std[inc],
                beam=0.05,
            )
        else:
            self._err_item.setData(x=np.array([]), y=np.array([]),
                                   height=np.array([]))

    def _redraw_fit_line(self):
        if len(self._x) == 0 or len(self._y_fit) == 0:
            self._fit_line.setData([], [])
            return
        included = [i for i in range(len(self._x)) if i not in self._excluded]
        if len(included) < 2:
            self._fit_line.setData([], [])
            return
        inc = np.array(included)
        xi = self._x[inc]
        yi = self._y_fit[inc]
        order = np.argsort(xi)
        self._fit_line.setData(xi[order], yi[order])

    def _redraw_equation(self):
        stats = self._last_fit_stats
        if not stats:
            self._equation_text.setText('')
            return
        slope = float(stats.get('slope', 0.0))
        intercept = float(stats.get('intercept', 0.0))
        r2 = float(stats.get('r_squared', 0.0))

        if abs(intercept) < 1e-9:
            eq = f"y = {slope:.4g} \u00B7 x"
        elif intercept >= 0:
            eq = f"y = {slope:.4g} \u00B7 x + {intercept:.4g}"
        else:
            eq = f"y = {slope:.4g} \u00B7 x \u2212 {abs(intercept):.4g}"

        suffix = f"  [{self._last_unit_label}]" if self._last_unit_label else ""
        lines = [f"{eq}{suffix}", f"R\u00B2 = {r2:.5f}"]
        if self._excluded:
            lines.append(f"({len(self._excluded)} point(s) excluded)")
        self._equation_text.setText('\n'.join(lines))
        self._reposition_equation()

    def _reposition_equation(self):
        try:
            vb = self.getPlotItem().getViewBox()
            (x_min, x_max), (y_min, y_max) = vb.viewRange()
            dx = (x_max - x_min) * 0.02
            dy = (y_max - y_min) * 0.02
            self._equation_text.setPos(x_min + dx, y_max - dy)
        except Exception:
            pass

    # ── Click & hover handlers ──────────────────────────────────────────

    def _on_scatter_clicked(self, _plot, points, event=None):
        """A single press on a scatter fires this. We queue the
        exclusion toggle and let mouseDoubleClickEvent cancel it if a
        second click follows within _DOUBLE_CLICK_MS.
        Args:
            _plot (Any): The  plot.
            points (Any): The points.
            event (Any): Qt event object.
        """
        if not points:
            return
        raw = points[0].data()
        if raw is None:
            return
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            return
        self._pending_click_index = idx
        self._click_timer.start(self._DOUBLE_CLICK_MS)

    def _emit_pending_click(self):
        if self._pending_click_index is not None:
            self.point_exclusion_toggled.emit(self._pending_click_index)
            self._pending_click_index = None


class BarEditorDialog(QDialog):
    """
    Simple editor for a single m/z bar: fill color.

    Operates directly on the bar meta-dict so changes are immediately
    reflected in the chart and survive subsequent data refreshes.
    """

    def __init__(self, meta, parent=None):
        """
        Args:
            meta (Any): The meta.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._meta = meta
        self.setWindowTitle(f"Bar — {meta['label']}")
        self.setFixedWidth(360)
        _install_theme_subscription(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"Bar Properties — {self._meta['label']}")
        header.setStyleSheet(_editor_header_qss())
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self._fill_color = QColor(self._meta.get('color', '#4488cc'))
        self._fill_btn = QPushButton()
        self._fill_btn.setFixedHeight(30)
        self._fill_btn.setStyleSheet(_color_swatch_qss(self._fill_color.name()))
        self._fill_btn.clicked.connect(self._pick_fill)
        form.addRow("Fill color:", self._fill_btn)

        layout.addLayout(form)

        p = _app_theme.palette
        info = QLabel(f"Mean signal: {self._meta.get('height', 0):.2f} counts")
        info.setStyleSheet(f"color:{p.text_secondary};font-size:11px;margin-top:4px;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setStyleSheet(_editor_ok_button_qss())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_editor_cancel_button_qss())
        ok_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _pick_fill(self):
        c = QColorDialog.getColor(self._fill_color, self, "Fill Color")
        if c.isValid():
            self._fill_color = c
            self._fill_btn.setStyleSheet(_color_swatch_qss(c.name()))

    def _apply(self):
        self._meta['color'] = self._fill_color.name()
        try:
            self._meta['bar_item'].setOpts(brush=pg.mkBrush(self._fill_color))
        except Exception:
            pass
        self.accept()


class MzBarPlotWidget(pg.PlotWidget):
    """
    Drop-in pg.PlotWidget for the inline m/z bar chart.

    Gives the same double-click-to-edit experience as EnhancedPlotWidget:

      Double-click title       → TitleEditorDialog
      Double-click left axis   → AxisLabelEditorDialog('left')
      Double-click bottom axis → AxisLabelEditorDialog('bottom')
      Double-click a bar       → BarEditorDialog  (fill color)
      Double-click empty area  → BackgroundEditorDialog
      Right-click anywhere     → 'Plot Settings…' → PlotSettingsDialog
                                 (Font + Grid tabs; Traces tab omitted
                                  because bars are not PlotDataItem objects)
    """

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        pi = CustomPlotItem()
        super().__init__(parent, plotItem=pi)
        pi.plot_widget = self
        self._bar_meta = []

    # ── Required by CustomPlotItem.getContextMenus ────────────────────
    def open_plot_settings(self):
        PlotSettingsDialog(self, self.parent()).exec()

    # ── Bar metadata (called by MainWindow after every redraw) ────────
    def set_bar_meta(self, meta):
        """Store per-bar metadata dicts for hit-testing on double-click.
        Args:
            meta (Any): The meta.
        """
        self._bar_meta = list(meta)

    # ── Double-click editing ──────────────────────────────────────────
    def mouseDoubleClickEvent(self, event):
        """
        Hit-detection priority (same order as EnhancedPlotWidget):
          1. Title            → TitleEditorDialog
          2. Left axis        → AxisLabelEditorDialog('left')
          3. Bottom axis      → AxisLabelEditorDialog('bottom')
          4. Bar (by x pos)   → BarEditorDialog
          5. Empty area       → BackgroundEditorDialog
        Args:
            event (Any): Qt event object.
        """
        try:
            pos       = event.position() if hasattr(event, 'position') else event.pos()
            scene_pos = self.mapToScene(pos.toPoint())
            pi        = self.getPlotItem()
            vb        = pi.getViewBox()

            tl = pi.titleLabel
            if tl and tl.isVisible():
                if tl.mapRectToScene(tl.boundingRect()).contains(scene_pos):
                    TitleEditorDialog(self, self.parent()).exec()
                    event.accept(); return

            la = pi.getAxis('left')
            if la.mapRectToScene(la.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(self, 'left', self.parent()).exec()
                event.accept(); return

            ba = pi.getAxis('bottom')
            if ba.mapRectToScene(ba.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(self, 'bottom', self.parent()).exec()
                event.accept(); return

            try:
                data_pos = vb.mapSceneToView(scene_pos)
                x_click  = float(data_pos.x())
                for meta in self._bar_meta:
                    if abs(x_click - meta['x']) <= 0.33:
                        BarEditorDialog(meta, self.parent()).exec()
                        event.accept(); return
            except Exception:
                pass

            BackgroundEditorDialog(self, self.parent()).exec()
            event.accept()

        except Exception as exc:
            print(f"Warning: MzBarPlotWidget double-click error: {exc}")
            super().mouseDoubleClickEvent(event)