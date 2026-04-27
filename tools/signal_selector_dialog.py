from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QScrollArea, QWidget,
    QColorDialog, QFrame, QGroupBox, QLineEdit,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import pyqtgraph as pg
import numpy as np

from theme import theme


DEFAULT_SAMPLE_COLORS = [
    '#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
    '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#7f7f7f',
]

DEFAULT_ELEMENT_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
]


def _style_group_box() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QGroupBox {{
            font-weight: 700;
            font-size: 12px;
            color: {p.text_secondary};
            letter-spacing: 0.8px;
            text-transform: uppercase;
            border: 1px solid {p.border};
            border-radius: 10px;
            margin-top: 16px;
            padding-top: 20px;
            background-color: {p.bg_secondary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: {p.accent};
        }}
    """


def _style_scroll_area() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    return """
        QScrollArea {
            border: none;
            background-color: transparent;
        }
    """


def _style_checkbox() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border-radius: 4px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 2px solid {p.border};
            background-color: {p.bg_tertiary};
        }}
        QCheckBox::indicator:checked {{
            border: 2px solid {p.accent};
            background-color: {p.accent};
            image: url(none);
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {p.accent_hover};
        }}
    """


def _style_row_widget() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QWidget {{
            background-color: {p.bg_tertiary};
            border: 1px solid {p.border_subtle};
            border-radius: 7px;
        }}
        QWidget:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
    """


def _style_utility_btn() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.accent};
            border: 1px solid {p.border};
            border-radius: 5px;
            padding: 4px 12px;
            font-weight: 600;
            font-size: 11px;
            letter-spacing: 0.3px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border-color: {p.accent};
        }}
        QPushButton:pressed {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
    """


def _style_plot_btn() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QPushButton {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: none;
            border-radius: 6px;
            padding: 10px 28px;
            font-weight: 700;
            font-size: 13px;
            letter-spacing: 0.4px;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}
    """


def _style_cancel_btn() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    p = theme.palette
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {p.text_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 10px 22px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            color: {p.accent};
            border-color: {p.accent};
        }}
    """


# ── Widgets ───────────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    """Custom color picker button widget."""

    colorChanged = Signal(str)

    def __init__(self, color="#1f77b4"):
        """
        Initialize the color button.

        Args:
            color (str, optional): Initial color in hex format. Defaults to "#1f77b4"

        Returns:
            None
        """
        super().__init__()
        self.current_color = color
        self.setFixedSize(28, 22)
        self.setToolTip("Click to change color")
        self._apply_style()
        self.clicked.connect(self.pick_color)

    def _apply_style(self):
        """
        Apply stylesheet to reflect the current color.

        Args:
            None

        Returns:
            None
        """
        p = theme.palette
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                border: 2px solid {p.border};
                border-radius: 5px;
            }}
            QPushButton:hover {{
                border: 2px solid {p.accent};
            }}
        """)

    def pick_color(self):
        """
        Open the color picker dialog and emit colorChanged if a new color is chosen.

        Args:
            None

        Returns:
            None
        """
        color = QColorDialog.getColor(QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self._apply_style()
            self.colorChanged.emit(self.current_color)

    def get_color(self):
        """
        Return the current color.

        Args:
            None

        Returns:
            str: Current color in hex format
        """
        return self.current_color

    def set_color(self, color):
        """
        Set a new color and update appearance.

        Args:
            color (str): New color in hex format

        Returns:
            None
        """
        self.current_color = color
        self._apply_style()


# ── Dialog ────────────────────────────────────────────────────────────────────

class SignalSelectorDialog(QDialog):
    """
    Dialog for selecting and configuring multiple signals for simultaneous display.

    Supports overlaying signals from multiple samples and multiple elements.
    Each sample has a configurable color. Each element has a configurable color.
    All traces use solid lines.
    """

    def __init__(self, main_window, parent=None):
        """
        Initialize the signal selector dialog.

        Args:
            main_window (MainWindow): Reference to main window
            parent (QWidget, optional): Parent widget

        Returns:
            None
        """
        super().__init__(parent)
        self.main_window = main_window
        self.signal_configs = {}
        self.sample_configs = {}

        self.setWindowTitle("Multi-Signal Display")
        self.setMinimumWidth(520)
        self.setMinimumHeight(660)
        self.resize(600, 780)

        self._setup_ui()
        self.populate_samples()
        self.populate_signals()

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Re-apply all theme-aware styling.

        Called on construction, via the themeChanged signal, and again on
        every showEvent so a cached dialog instance picks up the current
        theme when it's re-displayed.
        """
        p = theme.palette
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p.bg_primary};
                color: {p.text_primary};
            }}
            QLabel {{
                color: {p.text_primary};
                background-color: transparent;
                border: none;
            }}
            QLineEdit {{
                background-color: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 5px 8px;
                selection-background-color: {p.accent};
                selection-color: {p.text_inverse};
            }}
            QLineEdit:focus {{
                border: 1px solid {p.accent};
            }}
            QScrollBar:vertical {{
                background: {p.bg_primary};
                width: 10px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.text_muted};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        if hasattr(self, '_sample_group'):
            self._sample_group.setStyleSheet(_style_group_box())
        if hasattr(self, '_element_group'):
            self._element_group.setStyleSheet(_style_group_box())
        if hasattr(self, '_element_scroll'):
            self._apply_element_scroll_style()
        if hasattr(self, '_sample_scroll'):
            self._apply_sample_scroll_style()
        if hasattr(self, '_button_bar_frame'):
            self._apply_button_bar_style()
        if hasattr(self, '_cancel_btn'):
            self._cancel_btn.setStyleSheet(_style_cancel_btn())
        if hasattr(self, '_plot_btn'):
            self._plot_btn.setStyleSheet(_style_plot_btn())
        for btn in getattr(self, '_utility_btns', []):
            btn.setStyleSheet(_style_utility_btn())
        for row_entry in getattr(self, '_row_widgets', []):
            row_entry['row'].setStyleSheet(_style_row_widget())
            row_entry['checkbox'].setStyleSheet(_style_checkbox())
            row_entry['label'].setStyleSheet(self._row_label_style())
            row_entry['color_btn']._apply_style()

    def showEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        self.apply_theme()
        super().showEvent(event)

    def _apply_element_scroll_style(self):
        p = theme.palette
        self._element_scroll.setStyleSheet(_style_scroll_area() + f"""
            QScrollArea {{
                border: 1px solid {p.border};
                border-radius: 6px;
                background-color: {p.bg_tertiary};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {p.bg_tertiary};
            }}
            QWidget#signalsListInner {{
                background-color: {p.bg_tertiary};
            }}
        """)

    def _apply_sample_scroll_style(self):
        p = theme.palette
        self._sample_scroll.setStyleSheet(_style_scroll_area() + f"""
            QScrollArea {{
                border: 1px solid {p.border};
                border-radius: 6px;
                background-color: {p.bg_tertiary};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {p.bg_tertiary};
            }}
            QWidget#sampleListInner {{
                background-color: {p.bg_tertiary};
            }}
        """)
    def _apply_button_bar_style(self):
        p = theme.palette
        self._button_bar_frame.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
            }}
        """)

    def _row_label_style(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        p = theme.palette
        return (
            f"font-size: 12px; color: {p.text_primary}; font-weight: 500; "
            f"border: none; background: transparent;"
        )

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self):
        """
        Build and assemble the dialog layout.

        Two-column layout: samples on the left, elements on the right.
        Same footprint as the batch parameters dialog — less scrolling,
        everything visible at once.
        """
        outer = QVBoxLayout(self)
        outer.setSpacing(10)
        outer.setContentsMargins(16, 16, 16, 12)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(10)
        selection_row.addWidget(self._build_sample_group(), 1)
        selection_row.addWidget(self._build_element_group(), 1)
        outer.addLayout(selection_row, 1)

        outer.addWidget(self._build_button_bar())


    def _build_sample_group(self):
        """
        Build the sample selection group box.

        Args:
            None

        Returns:
            QGroupBox: Sample selector with checkboxes and color pickers
        """
        if not hasattr(self, '_utility_btns'):
            self._utility_btns = []
        if not hasattr(self, '_row_widgets'):
            self._row_widgets = []

        group = QGroupBox("Samples")
        self._sample_group = group
        layout = QVBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 12)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._utility_btn("Select all", self.select_all_samples))
        toolbar.addWidget(self._utility_btn("Clear", self.deselect_all_samples))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        self._sample_scroll = scroll

        self.sample_list_widget = QWidget()
        self.sample_list_widget.setObjectName("sampleListInner")
        self.sample_list_layout = QVBoxLayout(self.sample_list_widget)
        self.sample_list_layout.setSpacing(4)
        self.sample_list_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self.sample_list_widget)
        layout.addWidget(scroll, 1)
        return group

    def _build_element_group(self):
        """
        Build the element/signal selection group box.

        Returns:
            QGroupBox: Element selector with checkboxes and color pickers
        """
        group = QGroupBox("Elements")
        self._element_group = group
        layout = QVBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 12)

        self._element_filter = QLineEdit()
        self._element_filter.setPlaceholderText("Filter elements…")
        self._element_filter.setClearButtonEnabled(True)
        self._element_filter.textChanged.connect(self._filter_elements)
        layout.addWidget(self._element_filter)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._utility_btn("Select all", self.select_all))
        toolbar.addWidget(self._utility_btn("Clear", self.deselect_all))
        toolbar.addStretch()
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        self._element_scroll = scroll

        self.signals_widget = QWidget()
        self.signals_widget.setObjectName("signalsListInner")
        self.signals_layout = QVBoxLayout(self.signals_widget)
        self.signals_layout.setSpacing(4)
        self.signals_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self.signals_widget)
        layout.addWidget(scroll, 1)
        return group

    def _build_button_bar(self):
        """
        Bottom row with Cancel and Plot Signals buttons.

        Returns:
            QFrame: Button bar (no decorative frame — stays transparent).
        """
        frame = QFrame()
        self._button_bar_frame = frame
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 4, 0, 0)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._cancel_btn = cancel_btn

        plot_btn = QPushButton("Plot Signals")
        plot_btn.clicked.connect(self.plot_signals)
        plot_btn.setDefault(True)
        self._plot_btn = plot_btn

        layout.addStretch()
        layout.addWidget(cancel_btn)
        layout.addWidget(plot_btn)
        return frame

    # ── Row factory ───────────────────────────────────────────────────────

    def _utility_btn(self, text, slot):
        """
        Create a small utility button (Select All / Deselect All).

        Args:
            text (str): Button label
            slot (callable): Click handler

        Returns:
            QPushButton: Configured utility button
        """
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        if not hasattr(self, '_utility_btns'):
            self._utility_btns = []
        self._utility_btns.append(btn)
        btn.setStyleSheet(_style_utility_btn())
        return btn

    def _build_row(self, label_text, color, checked=True, on_check_changed=None):
        """
        Build a single checkbox + label + color-picker row widget.

        Args:
            label_text (str): Display text for the row
            color (str): Initial hex color for the color button
            checked (bool, optional): Initial checkbox state. Defaults to True
            on_check_changed (callable, optional): Slot for stateChanged signal

        Returns:
            tuple[QWidget, QCheckBox, ColorButton]: The row widget and its controls
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        if on_check_changed:
            checkbox.stateChanged.connect(on_check_changed)

        lbl = QLabel(label_text)
        color_btn = ColorButton(color)

        row.setStyleSheet(_style_row_widget())
        checkbox.setStyleSheet(_style_checkbox())
        lbl.setStyleSheet(self._row_label_style())

        if not hasattr(self, '_row_widgets'):
            self._row_widgets = []
        self._row_widgets.append({
            'row': row,
            'checkbox': checkbox,
            'label': lbl,
            'color_btn': color_btn,
        })

        layout.addWidget(checkbox)
        layout.addWidget(lbl, stretch=1)
        layout.addWidget(color_btn)

        return row, checkbox, color_btn

    # ── Populate ──────────────────────────────────────────────────────────

    def populate_samples(self):
        """
        Populate the sample list from loaded data. Current sample is checked by default.
        """
        samples = list(getattr(self.main_window, 'data_by_sample', {}).keys())
        current = getattr(self.main_window, 'current_sample', None)

        for idx, name in enumerate(samples):
            row, checkbox, color_btn = self._build_row(
                label_text=name,
                color=DEFAULT_SAMPLE_COLORS[idx % len(DEFAULT_SAMPLE_COLORS)],
                checked=(name == current),
                on_check_changed=self._update_sample_count,
            )
            self.sample_configs[name] = {'checkbox': checkbox, 'color_btn': color_btn}
            self.sample_list_layout.addWidget(row)

        self.sample_list_layout.addStretch()
        self._update_sample_count()

    def populate_signals(self):
        """
        Populate the signals list ordered by isotope mass.
        """
        pairs = sorted(
            (
                (element, isotope)
                for element, isotopes in self.main_window.selected_isotopes.items()
                for isotope in isotopes
            ),
            key=lambda x: x[1],
        )

        for idx, (element, isotope) in enumerate(pairs):
            element_key = f"{element}-{isotope:.4f}"
            display_label = self.main_window.get_formatted_label(element_key)

            row, checkbox, color_btn = self._build_row(
                label_text=display_label,
                color=DEFAULT_ELEMENT_COLORS[idx % len(DEFAULT_ELEMENT_COLORS)],
                checked=True,
                on_check_changed=self._update_element_count,
            )
            self.signal_configs[element_key] = {
                'checkbox': checkbox,
                'color_btn': color_btn,
                'display_label': display_label,
                'element': element,
                'isotope': isotope,
                '_row': row,
            }
            self.signals_layout.addWidget(row)

        self.signals_layout.addStretch()
        self._update_element_count()

    # ── Selection helpers ─────────────────────────────────────────────────

    def select_all(self):
        """Select all element checkboxes that are currently visible.

        Respects the filter: if you've narrowed the list with the filter
        input, only the matching rows get checked.
        """
        for cfg in self.signal_configs.values():
            row = cfg.get('_row')
            if row is None or row.isVisible():
                cfg['checkbox'].setChecked(True)

    def deselect_all(self):
        """Clear element checkboxes that are currently visible."""
        for cfg in self.signal_configs.values():
            row = cfg.get('_row')
            if row is None or row.isVisible():
                cfg['checkbox'].setChecked(False)

    def select_all_samples(self):
        """Select all sample checkboxes."""
        for cfg in self.sample_configs.values():
            cfg['checkbox'].setChecked(True)

    def deselect_all_samples(self):
        """Clear all sample checkboxes."""
        for cfg in self.sample_configs.values():
            cfg['checkbox'].setChecked(False)

    def _update_sample_count(self):
        """Refresh the sample count shown in the group title."""
        total = len(self.sample_configs)
        selected = sum(
            1 for cfg in self.sample_configs.values()
            if cfg['checkbox'].isChecked()
        )
        if hasattr(self, '_sample_group'):
            self._sample_group.setTitle(f"Samples  ({selected}/{total})")

    def _update_element_count(self):
        """Refresh the element count shown in the group title."""
        total = len(self.signal_configs)
        selected = sum(
            1 for cfg in self.signal_configs.values()
            if cfg['checkbox'].isChecked()
        )
        if hasattr(self, '_element_group'):
            self._element_group.setTitle(f"Elements  ({selected}/{total})")

    def _filter_elements(self):
        """Show/hide element rows based on the filter input's text."""
        text = self._element_filter.text().lower().strip()
        for cfg in self.signal_configs.values():
            row = cfg.get('_row')
            if row is None:
                continue
            label = cfg.get('display_label', '').lower()
            row.setVisible(not text or text in label)

    # ── Data helpers ──────────────────────────────────────────────────────

    def _get_selected_samples(self):
        """
        Return selected samples with their visual configuration.

        Args:
            None

        Returns:
            list[dict]: Each dict has keys 'name' and 'color'
        """
        return [
            {'name': name, 'color': cfg['color_btn'].get_color()}
            for name, cfg in self.sample_configs.items()
            if cfg['checkbox'].isChecked()
        ]

    def _get_selected_elements(self):
        """
        Return selected element configurations.

        Args:
            None

        Returns:
            list[dict]: Each dict has keys 'key', 'color', 'display_label', 'element', 'isotope'
        """
        return [
            {
                'key': key,
                'color': cfg['color_btn'].get_color(),
                'display_label': cfg['display_label'],
                'element': cfg['element'],
                'isotope': cfg['isotope'],
            }
            for key, cfg in self.signal_configs.items()
            if cfg['checkbox'].isChecked()
        ]

    def _find_closest_mass(self, sample_data, target_mass):
        """
        Find the key in sample_data closest to target_mass.

        Args:
            sample_data (dict): Sample data keyed by mass
            target_mass (float): Target isotope mass

        Returns:
            float or None: Closest mass key, or None if empty
        """
        if not sample_data:
            return None
        return min(sample_data.keys(), key=lambda x: abs(x - target_mass))

    def _get_detected_peaks(self, sample_name, element, isotope):
        """
        Retrieve detected peaks for a given sample and element.

        Args:
            sample_name (str): Name of the sample
            element (str): Element symbol
            isotope (float): Isotope mass

        Returns:
            list: Detected particle dicts, or empty list
        """
        return self.main_window.sample_detected_peaks.get(
            sample_name, {}
        ).get((element, isotope), [])

    # ── Plot ──────────────────────────────────────────────────────────────

    def plot_signals(self):
        """
        Plot all selected signals with optimized performance.

        Uses collinear point removal and PlotCurveItem for fast rendering.
        When multiple samples are selected each sample's color is used;
        when a single sample is selected element colors are used instead.
        All traces use solid lines.

        Args:
            None

        Returns:
            None
        """
        selected_samples = self._get_selected_samples()
        selected_elements = self._get_selected_elements()

        if not selected_samples or not selected_elements:
            return

        pw = self.main_window.plot_widget
        pw.clear()
        pw.setBackground('w')
        pw.showGrid(x=False, y=False, alpha=0.2)
        pw.setLabel('left', 'Counts')
        pw.setLabel('bottom', 'Time (s)')

        legend = pw.addLegend(
            offset=(10, 10),
            brush=pg.mkBrush(255, 255, 255, 150),
            pen=pg.mkPen(200, 200, 200, 100),
        )

        multi_sample = len(selected_samples) > 1
        single_element = len(selected_elements) == 1
        scatter_groups = {}

        for elem_cfg in selected_elements:
            isotope = elem_cfg['isotope']
            element = elem_cfg['element']
            element_color = elem_cfg['color']
            display_label = elem_cfg['display_label']

            for sample_cfg in selected_samples:
                sample_name = sample_cfg['name']
                sample_color = sample_cfg['color']

                sample_data = self.main_window.data_by_sample.get(sample_name, {})
                time_array = self.main_window.time_array_by_sample.get(sample_name)

                if not sample_data or time_array is None:
                    continue

                closest_mass = self._find_closest_mass(sample_data, isotope)
                if closest_mass is None:
                    continue

                signal = sample_data[closest_mass]
                trace_color = sample_color if multi_sample else element_color

                if multi_sample and not single_element:
                    legend_label = f"{display_label} — {sample_name}"
                elif multi_sample:
                    legend_label = sample_name
                else:
                    legend_label = display_label

                pen = pg.mkPen(trace_color, width=1, style=Qt.SolidLine)
                pen.setCosmetic(True)

                keep = np.diff(signal, n=2, append=np.inf, prepend=np.inf) != 0
                curve = pg.PlotCurveItem(
                    x=time_array[keep],
                    y=signal[keep],
                    pen=pen,
                    name=legend_label,
                    skipFiniteCheck=True,
                )
                pw.addItem(curve)

                for particle in self._get_detected_peaks(sample_name, element, isotope):
                    if particle is None:
                        continue
                    left_idx = particle['left_idx']
                    right_idx = particle['right_idx']
                    if right_idx >= len(signal) or left_idx >= len(signal):
                        continue
                    peak_idx = left_idx + np.argmax(signal[left_idx: right_idx + 1])
                    if peak_idx >= len(time_array):
                        continue
                    group = scatter_groups.setdefault(
                        trace_color, {'times': [], 'heights': []}
                    )
                    group['times'].append(time_array[peak_idx])
                    group['heights'].append(signal[peak_idx])

        for color, data in scatter_groups.items():
            if data['times']:
                pw.addItem(pg.ScatterPlotItem(
                    x=np.array(data['times']),
                    y=np.array(data['heights']),
                    symbol='o',
                    size=6,
                    brush=pg.mkBrush(color),
                    pen=pg.mkPen(255, 255, 255, 100, width=1),
                ))

        for sample, label in legend.items:
            label.setText(label.text, size='20pt')

        pw.setMouseEnabled(x=True, y=True)
        pw.enableAutoRange()
        self.accept()