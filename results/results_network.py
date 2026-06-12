"""
Network / Chord Diagram Node – circular element correlation network.

Elements are arranged around a circle.  Edges represent significant
pairwise Pearson correlations.  Red = positive, Blue = negative.
Edge width ∝ |r|.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
from matplotlib.patches import Circle
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import (
    get_font_config,
    FontSettingsGroup, ExportSettingsGroup, MplDraggableCanvas,
    LABEL_MODES, format_element_label, Renderer,
    get_display_name, download_matplotlib_figure,
    per_ml_active, per_ml_factor, conc_meta_available, single_sample_name,
    format_per_ml, pick_color_hex,
)
from results.utils_sort import sort_elements_by_mass
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_network")


# ── Constants ──────────────────────────────────────────────────────────

NET_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

NET_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

DEFAULT_CONFIG = {
    'data_type_display':    'Counts',
    'r_threshold':          0.3,
    'min_particles':        5,
    'positive_color':       '#EF4444',
    'negative_color':       '#3B82F6',
    'node_color':           '#14B8A6',
    'edge_alpha':           0.6,
    'edge_width_factor':    3.0,
    'node_radius':          0.06,
    'scale_node_size_by_amount': False,
    'show_labels':          True,
    'show_edge_count':      True,
    'show_sample_count':    True,
    'show_mean_abs_r':      True,
    'layout_radius_factor': 0.38,
    'label_mode':           'Symbol',
    'font_family':          'Times New Roman',
    'font_size':            10,
    'font_bold':            False,
    'font_italic':          False,
    'font_color':           '#000000',
    'sample_name_mappings': {},
    'bg_color':             '#FFFFFF',
    'export_format':        'svg',
    'export_dpi':           300,
    'use_custom_figsize':   False,
    'figsize_w':            14.0,
    'figsize_h':            8.0,
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _compute_edges(particles, elements, data_key, r_threshold, min_n):
    """Return list of (i, j, r) where |r| >= threshold.
    Args:
        particles (Any): The particles.
        elements (Any): The elements.
        data_key (Any): The data key.
        r_threshold (Any): The r threshold.
        min_n (Any): The min n.
    Returns:
        object: Result of the operation.
    """
    n = len(elements)
    vectors = {el: [] for el in elements}
    for p in particles:
        d = p.get(data_key, {})
        for el in elements:
            v = d.get(el, 0)
            if data_key != 'elements':
                if v <= 0 or (isinstance(v, float) and np.isnan(v)):
                    v = 0
            vectors[el].append(v)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            vi = np.array(vectors[elements[i]], dtype=float)
            vj = np.array(vectors[elements[j]], dtype=float)
            mask = (vi > 0) & (vj > 0)
            if mask.sum() >= min_n:
                try:
                    r, p = pearsonr(vi[mask], vj[mask])
                    if abs(r) >= r_threshold:
                        edges.append((i, j, r))
                except Exception:
                    _itk_log.exception("Handled exception in _compute_edges")
                    pass
    return edges


def _compute_node_amounts(particles, elements, data_key, aggregation="Sum"):
    """Aggregate per-element amounts for one sample and one selected data type.

    Args:
        particles (list[dict]): Particle records belonging to one sample.
        elements (list[str]): Canonical element keys used by the network.
        data_key (str): Selected particle dictionary key from ``NET_DATA_KEY_MAP``.
        aggregation (str): Aggregation mode for node sizing, either ``Sum`` or
            ``Mean``.

    Returns:
        dict[str, float]: Aggregated value for each canonical element. ``Sum``
            adds all finite numeric values, treating missing and invalid entries
            as zero. ``Mean`` averages only finite values greater than zero and
            returns zero when an element has no valid contributing values.
    """
    mode = str(aggregation or "Sum").strip().title()
    if mode not in {"Sum", "Mean"}:
        mode = "Sum"

    node_amounts = {element: 0.0 for element in elements}
    mean_totals = {element: 0.0 for element in elements}
    mean_counts = {element: 0 for element in elements}
    for particle in particles:
        values = particle.get(data_key, {})
        for element in elements:
            value = values.get(element, 0)
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                _itk_log.exception("Handled exception in _compute_node_amounts")
                numeric_value = 0.0
            if mode == "Sum":
                if np.isfinite(numeric_value):
                    node_amounts[element] += numeric_value
            elif np.isfinite(numeric_value) and numeric_value > 0:
                mean_totals[element] += numeric_value
                mean_counts[element] += 1

    if mode == "Mean":
        for element in elements:
            if mean_counts[element] > 0:
                node_amounts[element] = mean_totals[element] / mean_counts[element]
            else:
                node_amounts[element] = 0.0
    return node_amounts


def _normalize_node_size_aggregation(value):
    """Normalize node-size aggregation config values to supported options.

    Args:
        value (Any): Raw config or UI value to normalize.

    Returns:
        str: ``Sum`` or ``Mean``, defaulting to ``Sum`` for unsupported values.
    """
    normalized = str(value or "Sum").strip().title()
    return normalized if normalized in {"Sum", "Mean"} else "Sum"


def _node_size_note_text(cfg):
    """Build the figure-level node-size explanation text when scaling is enabled.

    Args:
        cfg (dict): Current plot configuration.

    Returns:
        str: Compact explanation for the figure header, or an empty string when
            proportional node sizing is disabled.
    """
    if not cfg.get('scale_node_size_by_amount', False):
        return ""

    data_type = cfg.get('data_type_display', 'Counts') ##why here are we passing in counts 11:25 am 10 jun 2026
    aggregation = _normalize_node_size_aggregation(
        cfg.get('node_size_aggregation', 'Sum')) ##and here why are we passing in sum automatically, could this cause 
                                                 ## the lengend invariance? 11:26 10/06/2026
    return (
        f"Node size: log10-scaled by {data_type} ({aggregation}); "
        f"smallest valid node has base radius; max radius = {_node_size_max_scale():g}x base"
    )


def _node_size_max_scale():
    """Return the current maximum node-radius scale for proportional sizing.

    Returns:
        float: Maximum allowed radius multiplier relative to the configured base
            node radius.
    """
    return 4.0


def _node_size_visual_legend_enabled(cfg):
    """Return whether the figure should render the RHS node-size visual legend.

    Args:
        cfg (dict): Current plot configuration.

    Returns:
        bool: ``True`` when proportional node sizing is enabled.
    """
    return bool(cfg.get('scale_node_size_by_amount', False))


def _node_size_amount_unit(data_type):
    """Return a compact unit label for node-size amount text.

    Args:
        data_type (str): Current ``data_type_display`` label.

    Returns:
        str: Compact amount unit suffix for the selected data type.
    """
    if data_type == 'Counts':
        return 'counts'
    if '(fg)' in data_type:
        return 'fg'
    if '(fmol)' in data_type:
        return 'fmol'
    if '(nm)' in data_type:
        return 'nm'
    return ''


def _format_node_size_amount(value, unit):
    """Format a quantitative node-size amount label compactly for the RHS legend.

    Args:
        value (float | None): Numeric amount to format.
        unit (str): Unit suffix to append when available.

    Returns:
        str: Compact value string such as ``1.23e4 counts`` or ``12.3 nm``.
    """
    if value is None or not np.isfinite(value):
        return 'unavailable'

    abs_value = abs(float(value))
    if abs_value == 0:
        text = '0'
    elif abs_value >= 1e4 or abs_value < 1e-2:
        text = f"{value:.2e}".replace('e+0', 'e').replace('e+', 'e').replace('e-0', 'e-')
    elif abs_value >= 100:
        text = f"{value:.0f}"
    elif abs_value >= 10:
        text = f"{value:.1f}"
    else:
        text = f"{value:.3g}"
    return f"{text} {unit}".strip()


def _collect_node_size_base_amounts(network_payloads):
    """Collect per-network minimum valid node amounts used for proportional sizing.

    Args:
        network_payloads (dict | list[dict] | None): Extracted network payload for
            single-sample or multi-sample display.

    Returns:
        list[float]: Per-sample minimum valid positive node amounts, preserving
            the current subplot/sample ordering.
    """
    if not network_payloads:
        return []

    payload_list = []
    if isinstance(network_payloads, dict) and 'elements' in network_payloads:
        payload_list = [network_payloads]
    elif isinstance(network_payloads, dict):
        payload_list = list(network_payloads.values())

    mins = []
    for payload in payload_list:
        node_amounts = payload.get('node_amounts', {}) if isinstance(payload, dict) else {}
        valid_values = [
            float(value) for value in node_amounts.values()
            if np.isfinite(value) and value > 0
        ]
        if valid_values:
            mins.append(min(valid_values))
    return mins


def _node_size_legend_scales(max_scale):
    """Return example radius scales for the RHS node-size visual legend.

    The preferred examples are ``1.0x``, ``1.5x``, and ``2.0x`` base radius.
    When the current maximum radius scale is lower than one of those examples,
    the returned values adapt safely to stay within the active cap.

    Args:
        max_scale (float): Active maximum proportional node-radius scale.

    Returns:
        list[float]: Ordered example radius multipliers for the visual legend.
    """
    max_scale = _node_size_max_scale()
    preferred = [1.0, 1.5, 2.0]
    if max_scale >= preferred[-1]:
        return preferred

    midpoint = 1.0 + max(0.0, max_scale - 1.0) / 2.0
    scales = [1.0, midpoint, max_scale]
    unique_scales = []
    for scale in scales:
        rounded = round(scale, 3)
        if rounded not in unique_scales:
            unique_scales.append(rounded)
    return unique_scales


def _node_size_legend_amount_ratio(radius_scale):
    """Convert a radius scale into the corresponding relative amount ratio.

    Args:
        radius_scale (float): Radius multiplier relative to the base node radius.

    Returns:
        float: Relative amount ratio implied by the log10 scaling formula.
    """
    return 10 ** (radius_scale - 1.0)


def _node_size_visual_legend_labels(scales):
    """Build compact labels for RHS node-size legend example circles.

    Args:
        scales (list[float]): Radius multipliers relative to base node radius.

    Returns:
        list[str]: Compact legend labels describing radius and amount ratio.
    """
    labels = []
    for scale in scales:
        if abs(scale - 1.0) < 1e-9:
            labels.append("1.0x radius / base amount")
            continue
        amount_ratio = _node_size_legend_amount_ratio(scale)
        if amount_ratio >= 10:
            amount_text = f"{amount_ratio:.0f}x amount"
        else:
            amount_text = f"{amount_ratio:.1f}x amount"
        labels.append(f"{scale:.1f}x radius / {amount_text}")
    return labels


def _legend_base_amount_text(network_payloads, data_type):
    """Build the quantitative base-amount line for the RHS node-size legend.

    In multi-sample mode, the legend intentionally uses the first sample's
    minimum valid node amount as the visual base reference so the legend has one
    concrete anchor value instead of a range.

    Args:
        network_payloads (dict | list[dict] | None): Extracted network payload
            for the current redraw.
        data_type (str): Current ``data_type_display`` label.

    Returns:
        str: Compact base-amount description for the RHS legend.
    """
    base_amounts = _collect_node_size_base_amounts(network_payloads)
    unit = _node_size_amount_unit(data_type)
    if not base_amounts:
        return "sample min: unavailable"
    return f"sample min: {_format_node_size_amount(base_amounts[0], unit)}"


def _top_annotation_layout(has_legend, has_node_size_note):
    """Return coordinated figure annotation positions and layout bounds.

    Args:
        has_legend (bool): Whether the shared correlation sign legend is present.
        has_node_size_note (bool): Whether the node-size explanation text is present.

    Returns:
        dict: Layout values for figure-level annotations, including top note
            position, bottom legend anchor, RHS visual legend slot, and the
            ``tight_layout`` bounds that reserve enough space around subplots.
    """
    layout = {
        'legend_y': 0.035,
        'note_y': 0.975,
        'tight_top': 0.92,
        'tight_bottom': 0.08,
        'tight_right': 1.00,
        'rhs_axes': [0.80, 0.20, 0.18, 0.60],
    }
    if has_legend and has_node_size_note:
        layout['note_y'] = 0.975
        layout['tight_top'] = 0.90
        layout['tight_bottom'] = 0.10
    elif has_legend:
        layout['tight_bottom'] = 0.10
    elif has_node_size_note:
        layout['tight_top'] = 0.89
    return layout


def _compute_node_radii(elements, node_amounts, base_radius, enabled):
    """Compute per-element node radii from aggregated isotope amounts.

    When proportional sizing is disabled, or when no valid positive amounts are
    available, every element keeps the base radius. Otherwise each valid amount
    is scaled relative to the smallest positive finite value in that sample
    using ``1 + log10(value / min_valid)`` and capped at the current maximum
    radius scale.

    Args:
        elements (list[str]): Canonical element keys used by the network.
        node_amounts (dict[str, float] | None): Per-element aggregated amounts
            for the currently selected data type.
        base_radius (float): Fixed node radius from plot config.
        enabled (bool): Whether proportional node sizing is active.

    Returns:
        dict[str, float]: Radius to use for each canonical element key.
    """
    base_radii = {element: base_radius for element in elements}
    if not enabled or not node_amounts:
        return base_radii

    valid_values = {
        element: float(value)
        for element, value in node_amounts.items()
        if np.isfinite(value) and value > 0
    }
    if not valid_values:
        return base_radii

    min_valid = min(valid_values.values())
    max_scale = _node_size_max_scale()
    radius_by_element = {}
    for element in elements:
        value = valid_values.get(element)
        if value is None:
            radius_by_element[element] = base_radius
            continue
        scale = 1.0 + np.log10(value / min_valid)
        scale = min(max_scale, max(1.0, scale))
        radius_by_element[element] = base_radius * scale
    return radius_by_element


def _pick_color_hex(current_color, parent=None, title="Select Color", fallback="#FFFFFF"):
    """Open a safe color dialog and return a validated hex color string.

    The dialog is parented to a neutral owner widget instead of a colored swatch
    button so button-local stylesheets do not leak into the QColorDialog.

    Args:
        current_color (str | QColor | None): Current color value to seed.
        parent (QWidget | None): Safe parent widget for the color dialog.
        title (str): Dialog title shown by Qt.
        fallback (str): Hex color used when the current value is invalid.

    Returns:
        str: Selected hex color, or the previous validated color when the user
            cancels the dialog.
    """
    fallback_qcolor = QColor(fallback if QColor(fallback).isValid() else '#FFFFFF')
    if isinstance(current_color, QColor):
        current_qcolor = current_color if current_color.isValid() else fallback_qcolor
    else:
        current_qcolor = QColor(current_color) if current_color is not None else fallback_qcolor
        if not current_qcolor.isValid():
            current_qcolor = fallback_qcolor

    from PySide6.QtWidgets import QColorDialog

    picked = QColorDialog.getColor(current_qcolor, parent, title)
    if picked.isValid():
        return picked.name()
    return current_qcolor.name()


# ── Settings Dialog ────────────────────────────────────────────────────

class _ColorBtn(QPushButton):
    def __init__(self, color='#FFFFFF', parent=None, dialog_parent=None, title="Select Color"):
        """Create a small color swatch button with a safe color picker.

        Args:
            color (str): Initial hex color for the swatch.
            parent (QWidget | None): Widget parent for the button itself.
            dialog_parent (QWidget | None): Safe parent used when opening the
                QColorDialog.
            title (str): Title shown by the color picker dialog.
        """
        super().__init__(parent)
        self.setFixedSize(34, 22)
        self._color = color
        self._dialog_parent = dialog_parent
        self._dialog_title = title
        self._apply()

    def _apply(self):
        """Refresh the swatch preview without styling any parent dialog."""
        self.setStyleSheet(
            "QPushButton {"
            f"background-color:{self._color};border:1px solid #666;border-radius:2px;"
            "}")

    def color(self):
        """Return the currently selected network-preview color."""
        return self._color

    def mousePressEvent(self, event):
        """Open the shared safe color picker for this swatch on left click.

        Args:
            event (QMouseEvent): Button press event from Qt.
        """
        if event.button() == Qt.LeftButton:
            self._color = _pick_color_hex(
                self._color,
                parent=self._dialog_parent,
                title=self._dialog_title,
                fallback='#FFFFFF',
            )
            self._apply()
        super().mousePressEvent(event)


class _NetworkFontSettingsGroup(FontSettingsGroup):
    """Network-local font settings group with a safe font color picker."""

    def __init__(self, config, dialog_parent=None):
        """Initialize the network font settings wrapper.

        Args:
            config (dict): Plot configuration dictionary.
            dialog_parent (QWidget | None): Safe parent for QColorDialog.
        """
        super().__init__(config)
        self._dialog_parent = dialog_parent

    def _pick_color(self):
        """Select the font color without inheriting swatch button stylesheets."""
        picked_hex = _pick_color_hex(
            self._color,
            parent=self._dialog_parent,
            title="Font Color",
            fallback='#000000',
        )
        self._color = QColor(picked_hex)
        self.color_btn.setStyleSheet(
            f"background-color: {self._color.name()}; min-height: 25px;")


class NetworkSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None, scope='all'):
        """Build the network settings dialog for format or quantity controls.

        Args:
            cfg (dict): Current plot configuration.
            input_data (dict | None): Upstream input payload for sample context.
            parent (QWidget | None): Parent widget.
            scope (str): Section scope to display: ``all``, ``format``, or
                ``quantities``.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Network plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Network plot quantities configuration")
        else:
            self.setWindowTitle("Network Diagram Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)  ## left off reading here 11:25 am jun 10 2026
        self._input_data = input_data
        self._scope = scope
        self.dtype_combo = None
        self.thresh_spin = None
        self.min_part = None
        self._pos_btn = None
        self._neg_btn = None
        self._node_btn = None
        self.alpha_spin = None
        self.width_spin = None
        self.node_r = None
        self.radius_spin = None
        self.labels_cb = None
        self.scale_node_sizes_cb = None
        self.node_size_agg_combo = None
        self.node_size_note = None
        self.edge_count_cb = None
        self.sample_count_cb = None
        self.mean_abs_r_cb = None
        self.label_mode_combo = None
        self._font_grp = None
        self._export_grp = None
        self._sample_edits = {}
        self._build_ui()

    def _build_ui(self):
        """Create dialog controls for the requested settings scope."""
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        if self._scope in ('all', 'quantities'):
            g1 = QGroupBox("Data")
            f1 = QFormLayout(g1)
            self.dtype_combo = QComboBox()
            self.dtype_combo.addItems(NET_DATA_TYPES)
            self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
            f1.addRow("Data Type:", self.dtype_combo)
            self.thresh_spin = QDoubleSpinBox()
            self.thresh_spin.setRange(0.0, 0.99); self.thresh_spin.setDecimals(2)
            self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.3))
            f1.addRow("|r| Threshold:", self.thresh_spin)
            self.min_part = QDoubleSpinBox()
            self.min_part.setRange(2, 1000); self.min_part.setDecimals(0)
            self.min_part.setValue(self._cfg.get('min_particles', 5))
            f1.addRow("Min Particles:", self.min_part)
            self.scale_node_sizes_cb = QCheckBox()
            self.scale_node_sizes_cb.setChecked(
                self._cfg.get('scale_node_size_by_amount', False))
            self.scale_node_sizes_cb.setToolTip(
                "Uses log10 scaling within each sample. The smallest valid isotope amount keeps the base node radius.")
            f1.addRow("Scale node size by data amount:", self.scale_node_sizes_cb)
            self.node_size_agg_combo = QComboBox()
            self.node_size_agg_combo.addItems(["Sum", "Mean"])
            self.node_size_agg_combo.setCurrentText(_normalize_node_size_aggregation(
                self._cfg.get('node_size_aggregation', 'Sum')))
            self.node_size_agg_combo.setToolTip(
                "Controls how per-isotope values are aggregated before log10 node-size scaling.")
            f1.addRow("Node Size Aggregation:", self.node_size_agg_combo)
            self.node_size_note = QLabel(
                "Sum gives total burden; Mean gives typical contributing-event value. "
                "Mean is usually more interpretable for diameter-based data types.")
            self.node_size_note.setWordWrap(True)
            self.node_size_note.setStyleSheet("color:#6B7280; font-size:11px;")
            lay.addWidget(self.node_size_note)
            lay.addWidget(g1)

        if self._scope in ('all', 'format'):
            g2 = QGroupBox("Colors")
            f2 = QFormLayout(g2)
            self._pos_btn  = _ColorBtn(
                self._cfg.get('positive_color', '#EF4444'),
                dialog_parent=self,
                title="Positive Correlation Color",
            )
            self._neg_btn  = _ColorBtn(
                self._cfg.get('negative_color', '#3B82F6'),
                dialog_parent=self,
                title="Negative Correlation Color",
            )
            self._node_btn = _ColorBtn(
                self._cfg.get('node_color', '#14B8A6'),
                dialog_parent=self,
                title="Node Color",
            )
            f2.addRow("Positive (r>0):", self._pos_btn)
            f2.addRow("Negative (r<0):", self._neg_btn)
            f2.addRow("Node Color:", self._node_btn)
            lay.addWidget(g2)

            g3 = QGroupBox("Display")
            f3 = QFormLayout(g3)
            self.alpha_spin = QDoubleSpinBox()
            self.alpha_spin.setRange(0.1, 1.0); self.alpha_spin.setDecimals(1)
            self.alpha_spin.setValue(self._cfg.get('edge_alpha', 0.6))
            f3.addRow("Edge Transparency:", self.alpha_spin)
            self.width_spin = QDoubleSpinBox()
            self.width_spin.setRange(0.5, 10.0); self.width_spin.setDecimals(1)
            self.width_spin.setValue(self._cfg.get('edge_width_factor', 3.0))
            f3.addRow("Edge Width Factor:", self.width_spin)
            self.node_r = QDoubleSpinBox()
            self.node_r.setRange(0.02, 0.15); self.node_r.setDecimals(3)
            self.node_r.setValue(self._cfg.get('node_radius', 0.06))
            f3.addRow("Node Radius:", self.node_r)
            self.radius_spin = QDoubleSpinBox()
            self.radius_spin.setRange(0.15, 0.48); self.radius_spin.setDecimals(2)
            self.radius_spin.setValue(self._cfg.get('layout_radius_factor', 0.38))
            f3.addRow("Layout Radius:", self.radius_spin)
            self.labels_cb = QCheckBox()
            self.labels_cb.setChecked(self._cfg.get('show_labels', True))
            f3.addRow("Show Labels:", self.labels_cb)
            self.edge_count_cb = QCheckBox()
            self.edge_count_cb.setChecked(self._cfg.get('show_edge_count', True))
            f3.addRow("Show Edge Count:", self.edge_count_cb)
            self.sample_count_cb = QCheckBox()
            self.sample_count_cb.setChecked(self._cfg.get('show_sample_count', True))
            f3.addRow("Show Sample Count:", self.sample_count_cb)
            self.mean_abs_r_cb = QCheckBox()
            self.mean_abs_r_cb.setChecked(self._cfg.get('show_mean_abs_r', True))
            f3.addRow("Show Mean |r|:", self.mean_abs_r_cb)
            self.label_mode_combo = QComboBox()
            self.label_mode_combo.addItems(LABEL_MODES)
            self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
            f3.addRow("Isotope Label:", self.label_mode_combo)
            lay.addWidget(g3)

            sample_names = []
            if _is_multi(self._input_data):
                sample_names = list(self._input_data.get('sample_names', []))
            elif self._input_data and self._input_data.get('type') == 'sample_data':
                sample_name = self._input_data.get('sample_name', 'Sample')
                sample_names = [sample_name]
            if sample_names:
                mappings = self._cfg.get('sample_name_mappings', {})
                g4 = QGroupBox("Sample Names")
                v4 = QVBoxLayout(g4)
                for sample_name in sample_names:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(sample_name))
                    edit = QLineEdit(mappings.get(sample_name, sample_name))
                    edit.setPlaceholderText(sample_name)
                    edit.setFixedWidth(220)
                    row.addWidget(edit)
                    self._sample_edits[sample_name] = edit
                    reset_btn = QPushButton("Reset")
                    reset_btn.setFixedWidth(50)
                    reset_btn.clicked.connect(
                        lambda _, raw=sample_name: self._sample_edits[raw].setText(raw))
                    row.addWidget(reset_btn)
                    row.addStretch()
                    v4.addLayout(row)
                lay.addWidget(g4)

            self._font_grp = _NetworkFontSettingsGroup(self._cfg, dialog_parent=self)
            lay.addWidget(self._font_grp.build())

            self._export_grp = ExportSettingsGroup(self._cfg)
            lay.addWidget(self._export_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def collect(self):
        """Collect normalized config values from the visible dialog controls.

        This method explicitly commits any in-progress spinbox text edits before
        reading values so manually typed numeric input is not lost when the user
        clicks ``OK`` while a field still has focus.
        """
        self._commit_numeric_inputs()
        d = {
            'data_type_display':    self.dtype_combo.currentText() if self.dtype_combo else self._cfg.get('data_type_display', 'Counts'),
            'r_threshold':          self.thresh_spin.value() if self.thresh_spin else self._cfg.get('r_threshold', 0.3),
            'min_particles':        int(self.min_part.value()) if self.min_part else int(self._cfg.get('min_particles', 5)),
            'positive_color':       self._pos_btn.color() if self._pos_btn else self._cfg.get('positive_color', '#EF4444'),
            'negative_color':       self._neg_btn.color() if self._neg_btn else self._cfg.get('negative_color', '#3B82F6'),
            'node_color':           self._node_btn.color() if self._node_btn else self._cfg.get('node_color', '#14B8A6'),
            'scale_node_size_by_amount': self.scale_node_sizes_cb.isChecked() if self.scale_node_sizes_cb else self._cfg.get('scale_node_size_by_amount', False),
            'node_size_aggregation': _normalize_node_size_aggregation(
                self.node_size_agg_combo.currentText() if self.node_size_agg_combo else self._cfg.get('node_size_aggregation', 'Sum')),
            'edge_alpha':           self.alpha_spin.value() if self.alpha_spin else self._cfg.get('edge_alpha', 0.6),
            'edge_width_factor':    self.width_spin.value() if self.width_spin else self._cfg.get('edge_width_factor', 3.0),
            'node_radius':          self.node_r.value() if self.node_r else self._cfg.get('node_radius', 0.06),
            'layout_radius_factor': self.radius_spin.value() if self.radius_spin else self._cfg.get('layout_radius_factor', 0.38),
            'show_labels':          self.labels_cb.isChecked() if self.labels_cb else self._cfg.get('show_labels', True),
            'show_edge_count':      self.edge_count_cb.isChecked() if self.edge_count_cb else self._cfg.get('show_edge_count', True),
            'show_sample_count':    self.sample_count_cb.isChecked() if self.sample_count_cb else self._cfg.get('show_sample_count', True),
            'show_mean_abs_r':      self.mean_abs_r_cb.isChecked() if self.mean_abs_r_cb else self._cfg.get('show_mean_abs_r', True),
            'label_mode':           self.label_mode_combo.currentText() if self.label_mode_combo else self._cfg.get('label_mode', 'Symbol'),
        }
        if self._font_grp is not None:
            d.update(self._font_grp.collect())
        if self._export_grp is not None:
            d.update(self._export_grp.collect())
        if self._sample_edits:
            d['sample_name_mappings'] = {
                raw_name: edit.text().strip()
                for raw_name, edit in self._sample_edits.items()
                if edit.text().strip() and edit.text().strip() != raw_name
            }
        return d

    def _commit_numeric_inputs(self):
        """Commit pending text edits for all numeric spinboxes in the dialog.

        QDoubleSpinBox keeps the typed text in its editor until focus changes or
        Qt explicitly interprets the text. Calling ``interpretText()`` here
        ensures the saved config reflects the value the user typed, including the
        node-radius field that is commonly confirmed by pressing ``OK`` directly.
        """
        for widget in (
            self.thresh_spin,
            self.min_part,
            self.alpha_spin,
            self.width_spin,
            self.node_r,
            self.radius_spin,
        ):
            if widget is not None:
                widget.interpretText()


# ── Display Dialog ─────────────────────────────────────────────────────

class NetworkDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        """Create the Matplotlib-backed network display dialog.

        Args:
            node (NetworkDiagramNode): Source node that owns the plot config.
            parent_window (QWidget | None): Parent window for the dialog.
        """
        super().__init__(parent_window)
        self.node = node
        self._initial_refresh_pending = True
        self.setWindowTitle("Element Correlation Network")
        self.setMinimumSize(1000, 700)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def showEvent(self, event):
        """Schedule one post-show redraw so the first open uses settled geometry.

        Args:
            event (QShowEvent): Qt show event for the dialog.
        """
        super().showEvent(event)
        if self._initial_refresh_pending:
            self._initial_refresh_pending = False
            QTimer.singleShot(0, self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._info = QLabel("")
        self._info.setStyleSheet("color:#94A3B8; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._info)

        self.figure = Figure(figsize=(14, 8), dpi=120, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.canvas, stretch=1)

        tb = QHBoxLayout(); tb.setContentsMargins(0, 2, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_r = QPushButton("Reset layout")
        btn_r.setToolTip("Reset subplot positions (or middle-click)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export figure")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_fmt)
        tb.addWidget(btn_qty)
        tb.addWidget(btn_r)
        tb.addWidget(btn_e)
        lay.addLayout(tb)

    # ── Context menu ───────────────────────────────────────────────────

    def _ctx_menu(self, pos):
        """Open a quick-toggle context menu for network display settings.

        Args:
            pos (QPoint): Canvas-local click position. The menu uses cursor
                position for display.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('show_labels', 'Show Isotope Labels'),
            ('show_edge_count', 'Show Edge Count'),
            ('show_sample_count', 'Show Sample Count'),
            ('show_mean_abs_r', 'Show Mean |r|'),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, True))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        menu.exec(QCursor.pos())
    def _toggle(self, key):
        """Flip a boolean config flag and redraw the current figure.

        Args:
            key (str): Boolean config key to toggle.
        """
        self.node.config[key] = not self.node.config.get(key, True)
        self._refresh()

    def _set(self, key, value):
        """Set a config value and redraw the current figure.

        Args:
            key (str): Config key to update.
            value (Any): New value for the config key.
        """
        self.node.config[key] = value
        self._refresh()

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.figure, self, "network_diagram")

    def _open_plot_format_settings(self):
        """Open the formatting dialog and apply accepted display settings."""
        dlg = NetworkSettingsDialog(
            self.node.config, self.node.input_data, self, scope='format')
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """Open the quantities dialog and apply accepted quantity settings."""
        dlg = NetworkSettingsDialog(
            self.node.config, self.node.input_data, self, scope='quantities')
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_settings(self):
        """Open the combined settings dialog and apply accepted changes."""
        dlg = NetworkSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh / draw ─────────────────────────────────────────────────

    def _refresh(self):
        """Rebuild the Matplotlib figure from current config and extracted data.

        The refresh flow finalizes subplot layout before computing the RHS
        node-size visual legend so legend marker sizes are derived from the
        settled network axes transform on the first redraw, not only after a
        second no-op dialog confirmation.
        """
        try:
            cfg = self.node.config
            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 14.0),
                                            cfg.get('figsize_h', 8.0))
            self.figure.clear()
            self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))

            data = self.node.extract_network_data()
            reference_ax = None
            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No data available\nConnect to a Sample Selector node.',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.axis('off')
                self._info.setText("")
                self.canvas.draw()
                return

            if isinstance(data, dict) and 'elements' in data:
                ax = self.figure.add_subplot(111)
                reference_ax = ax
                legend_signs = self._draw_network(ax, data, cfg)
                self._info.setText(
                    f"{len(data['elements'])} elements · "
                    f"{len(data['edges'])} edges · "
                    f"{data.get('n_particles', 0)} particles")
            else:
                names = list(data.keys())
                n = len(names)
                cols = min(n, 3)
                rows = math.ceil(n / cols)
                total_edges = 0
                legend_signs = set()
                for idx, sn in enumerate(names):
                    nd = data[sn]
                    ax = self.figure.add_subplot(rows, cols, idx + 1)
                    if reference_ax is None:
                        reference_ax = ax
                    legend_signs.update(self._draw_network(ax, nd, cfg))
                    total_edges += len(nd['edges'])
                self._info.setText(f"{n} groups · {total_edges} total edges")

            has_legend = bool(legend_signs)
            has_node_size_note = bool(_node_size_note_text(cfg))
            has_rhs_node_size_legend = _node_size_visual_legend_enabled(cfg)
            top_layout = _top_annotation_layout(has_legend, has_node_size_note)
            if has_rhs_node_size_legend:
                top_layout['tight_right'] = 0.76
            if has_legend:
                self._apply_shared_legend(cfg, legend_signs, top_layout)
            if has_node_size_note:
                self._apply_node_size_note(cfg, top_layout)
            if has_legend or has_node_size_note or has_rhs_node_size_legend:
                self.figure.tight_layout(rect=(
                    0.0,
                    top_layout['tight_bottom'],
                    top_layout['tight_right'],
                    top_layout['tight_top'],
                ))
            else:
                self.figure.tight_layout()
            if has_rhs_node_size_legend:
                # Finalize subplot transforms before deriving display-space legend sizes.
                self.canvas.draw()
                self._apply_node_size_visual_legend(cfg, data, reference_ax, top_layout)
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error refreshing network diagram: {e}")
            import traceback; traceback.print_exc()

    def _draw_network(self, ax, net_data, cfg):
        """Draw one correlation network on an axes and report legend signs.

        Args:
            ax (matplotlib.axes.Axes): Target axes.
            net_data (dict): Extracted network payload for one sample.
            cfg (dict): Current plot configuration.

        Returns:
            set[str]: Sign labels needed for the shared correlation legend.
        """
        elements = net_data['elements']
        edges    = net_data['edges']
        n        = len(elements)

        bg       = cfg.get('bg_color', '#FFFFFF')
        pos_c    = cfg.get('positive_color', '#EF4444')
        neg_c    = cfg.get('negative_color', '#3B82F6')
        node_c   = cfg.get('node_color', '#14B8A6')
        edge_a   = cfg.get('edge_alpha', 0.6)
        edge_wf  = cfg.get('edge_width_factor', 3.0)
        node_r   = cfg.get('node_radius', 0.06)
        node_amounts = net_data.get('node_amounts', {})
        scale_node_sizes = cfg.get('scale_node_size_by_amount', False)
        R        = cfg.get('layout_radius_factor', 0.38)
        label_mode = cfg.get('label_mode', 'Symbol')
        fc       = get_font_config(cfg)
        radius_by_element = _compute_node_radii(
            elements, node_amounts, node_r, scale_node_sizes)

        fmt_labels = [format_element_label(el, label_mode, Renderer.MATHTEXT, cfg) for el in elements]

        ax.set_facecolor(bg)
        ax.set_xlim(-0.55, 0.55)
        ax.set_ylim(-0.55, 0.55)
        ax.set_aspect('equal')
        ax.axis('off')

        if n < 2:
            ax.text(0, 0, 'Insufficient elements', ha='center', va='center',
                    color='gray', fontsize=fc['size'])
            return set()

        positions = []
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            positions.append((R * math.cos(angle), R * math.sin(angle)))

        mean_r = np.mean([abs(e[2]) for e in edges]) if edges else 0.0
        legend_signs = set()
        for (i, j, r) in edges:
            xi, yi = positions[i]
            xj, yj = positions[j]
            color = pos_c if r > 0 else neg_c
            lw = max(0.5, abs(r) * edge_wf)
            ax.plot([xi, xj], [yi, yj], color=color, lw=lw,
                    alpha=edge_a, solid_capstyle='round', zorder=1)
            legend_signs.add('positive' if r > 0 else 'negative')

        for i, el in enumerate(elements):
            px, py = positions[i]
            fmt_el = fmt_labels[i]
            current_radius = radius_by_element.get(el, node_r)

            circle = Circle((px, py), current_radius, color=node_c, zorder=3,
                             linewidth=1.5, edgecolor='white')
            ax.add_patch(circle)

            ax.text(px, py, fmt_el, ha='center', va='center',
                    fontsize=max(6, fc['size'] - 2), color='white',
                    fontweight='bold', zorder=4)

            if cfg.get('show_labels', True):
                angle = 2 * math.pi * i / n - math.pi / 2
                lx = (R + current_radius + 0.04) * math.cos(angle)
                ly = (R + current_radius + 0.04) * math.sin(angle)
                ha = 'center'
                if math.cos(angle) > 0.1:
                    ha = 'left'
                elif math.cos(angle) < -0.1:
                    ha = 'right'
                va = 'center'
                if math.sin(angle) > 0.1:
                    va = 'bottom'
                elif math.sin(angle) < -0.1:
                    va = 'top'
                ax.text(lx, ly, fmt_el, ha=ha, va=va,
                        fontsize=fc['size'], color=fc['color'],
                        fontfamily=fc['family'],
                        fontweight='bold' if fc['bold'] else 'normal',
                        fontstyle='italic' if fc['italic'] else 'normal', zorder=5)

        title, subtitle = self._build_title_and_subtitle(net_data, cfg, mean_r)

        _fw = 'bold' if fc['bold'] else 'normal'
        _fst = 'italic' if fc['italic'] else 'normal'
        if title and subtitle:
            ax.set_title(f"{title}\n{subtitle}", fontsize=fc['size'],
                         color=fc['color'], pad=6, fontfamily=fc['family'],
                         fontweight=_fw, fontstyle=_fst)
        elif title:
            ax.set_title(title, fontsize=fc['size'],
                         color=fc['color'], pad=6, fontfamily=fc['family'],
                         fontweight=_fw, fontstyle=_fst)
        elif subtitle:
            ax.set_title(subtitle, fontsize=fc['size'],
                         color=fc['color'], pad=6, fontfamily=fc['family'],
                         fontweight=_fw, fontstyle=_fst)

        return legend_signs

    def _build_title_and_subtitle(self, net_data, cfg, mean_r):
        """Build config-driven title and subtitle text for one network plot.

        Args:
            net_data (dict): Extracted plot payload for one sample or aggregate.
            cfg (dict): Current plot configuration.
            mean_r (float): Mean absolute correlation magnitude for visible edges.

        Returns:
            tuple[str, str]: Title text and subtitle text. Either value may be
                an empty string when nothing should be rendered on that line.
        """
        raw_sample_name = net_data.get('sample_name', '')
        title = get_display_name(raw_sample_name, cfg) if raw_sample_name else ''
        if title and cfg.get('show_sample_count', True):
            title = f"{title} (n={net_data.get('n_particles', 0)})"

        edge_count = len(net_data.get('edges', []))
        subtitle_parts = []
        if cfg.get('show_edge_count', True):
            edge_label = "edge" if edge_count == 1 else "edges"
            subtitle_parts.append(f"{edge_count} {edge_label}")
        if cfg.get('show_mean_abs_r', True) and edge_count:
            subtitle_parts.append(f"mean|r|={mean_r:.2f}")
        subtitle = "  ·  ".join(subtitle_parts)
        return title, subtitle

    def _apply_shared_legend(self, cfg, legend_signs, top_layout):
        """Add one figure-level correlation legend in the bottom figure margin.

        Args:
            cfg (dict): Current plot configuration.
            legend_signs (set[str]): Sign labels requested by the drawn panels.
            top_layout (dict): Coordinated top annotation layout values.

        Returns:
            bool: ``True`` when a shared legend was added to the figure.
        """
        if not legend_signs:
            return False

        import matplotlib.lines as mlines
        from matplotlib.font_manager import FontProperties

        fc = get_font_config(cfg)
        font_weight = 'bold' if fc['bold'] else 'normal'
        font_style = 'italic' if fc['italic'] else 'normal'
        leg_fp = FontProperties(
            family=fc['family'],
            size=max(6, fc['size'] - 1),
            weight=font_weight,
            style=font_style,
        )

        handles = []
        if 'positive' in legend_signs:
            handles.append(mlines.Line2D(
                [], [], color=cfg.get('positive_color', '#EF4444'), lw=2, label='r > 0'))
        if 'negative' in legend_signs:
            handles.append(mlines.Line2D(
                [], [], color=cfg.get('negative_color', '#3B82F6'), lw=2, label='r < 0'))
        if not handles:
            return False

        legend = self.figure.legend(
            handles=handles,
            loc='lower center',
            bbox_to_anchor=(0.5, top_layout['legend_y']),
            ncol=len(handles),
            prop=leg_fp,
            framealpha=0.85,
        )
        for txt in legend.get_texts():
            txt.set_color(fc['color'])
        return True

    def _apply_node_size_note(self, cfg, top_layout):
        """Add one figure-level node-size explanation below the top legend row.

        Args:
            cfg (dict): Current plot configuration.
            top_layout (dict): Coordinated top annotation layout values.

        Returns:
            bool: ``True`` when a node-size explanation was added.
        """
        note = _node_size_note_text(cfg)
        if not note:
            return False

        fc = get_font_config(cfg)
        self.figure.text(
            0.5, top_layout['note_y'], note,
            ha='center', va='top',
            fontsize=max(6, fc['size'] - 1),
            color=fc['color'],
            fontfamily=fc['family'],
            fontweight='bold' if fc['bold'] else 'normal',
            fontstyle='italic' if fc['italic'] else 'normal',
        )
        return True

    def _measure_reference_node_diameter_points(self, cfg, reference_ax):
        """Measure the plotted base node diameter in display points.

        Args:
            cfg (dict): Current plot configuration containing the base node
                radius.
            reference_ax (matplotlib.axes.Axes | None): A rendered network axes
                used to measure the base node patch with the same transform as
                the plotted graph.

        Returns:
            float: The visible outer diameter of a base-radius node in points,
            including the white outline. A conservative fallback is returned if
            the live measurement cannot be completed.
        """
        fallback_diameter_points = 2.0 * 18.0 * 72.0 / self.figure.dpi
        if reference_ax is None:
            return fallback_diameter_points

        try:
            renderer = self.figure.canvas.get_renderer()
            if renderer is None:
                return fallback_diameter_points

            base_radius = float(cfg.get('node_radius', 0.06))
            probe = Circle(
                (0.0, 0.0),
                base_radius,
                color=cfg.get('node_color', '#14B8A6'),
                linewidth=1.5,
                edgecolor='white',
                visible=False,
            )
            reference_ax.add_patch(probe)
            try:
                bbox = probe.get_window_extent(renderer)
            finally:
                probe.remove()

            width_px = max(4.0, float(bbox.width))
            return width_px * 72.0 / self.figure.dpi
        except Exception:
            _itk_log.exception("Handled exception in _measure_reference_node_diameter_points")
            return fallback_diameter_points

    def _apply_node_size_visual_legend(self, cfg, network_payloads, reference_ax, top_layout):
        """Draw a RHS visual legend showing example proportional node sizes.

        Args:
            cfg (dict): Current plot configuration.
            network_payloads (dict | None): Current extracted network payload used
                to compute per-sample node-size minima.
            reference_ax (matplotlib.axes.Axes | None): A representative network
                axes used to align the visual base radius with plotted node size.
            top_layout (dict): Coordinated figure annotation layout values.

        Returns:
            bool: ``True`` when the RHS visual legend was drawn.
        """
        if not _node_size_visual_legend_enabled(cfg):
            return False

        legend_ax = self.figure.add_axes(top_layout['rhs_axes'])
        legend_ax.set_axis_off()
        legend_ax.set_xlim(0.0, 1.0)
        legend_ax.set_ylim(0.0, 1.0)

        fc = get_font_config(cfg)
        data_type = cfg.get('data_type_display', 'Counts')
        aggregation = _normalize_node_size_aggregation(
            cfg.get('node_size_aggregation', 'Sum'))
        title_text = (
            "Node size\n"
            f"{data_type} - {aggregation}"
        )
        legend_ax.text(
            0.04, 0.98, title_text,
            ha='left', va='top',
            fontsize=max(6, fc['size'] - 1),
            color=fc['color'],
            fontfamily=fc['family'],
            fontweight='bold' if fc['bold'] else 'normal',
            fontstyle='italic' if fc['italic'] else 'normal',
            transform=legend_ax.transAxes,
        )
        legend_ax.text(
            0.04, 0.84, "log10 scale\nrelative to sample min",
            ha='left', va='top',
            fontsize=max(5, fc['size'] - 3),
            color=fc['color'],
            fontfamily=fc['family'],
            fontweight='bold' if fc['bold'] else 'normal',
            fontstyle='italic' if fc['italic'] else 'normal',
            transform=legend_ax.transAxes,
        )

        scales = _node_size_legend_scales(_node_size_max_scale())
        labels = _node_size_visual_legend_labels(scales)
        min_text = _legend_base_amount_text(network_payloads, data_type)

        legend_ax.text(
            0.04, 0.72, min_text,
            ha='left', va='top',
            fontsize=max(5, fc['size'] - 3),
            color=fc['color'],
            fontfamily=fc['family'],
            fontweight='bold' if fc['bold'] else 'normal',
            fontstyle='italic' if fc['italic'] else 'normal',
            transform=legend_ax.transAxes,
        )

        y_positions = [0.58, 0.40, 0.22][:len(scales)]
        node_edge_width_points = 1.5
        base_diameter_points = self._measure_reference_node_diameter_points(
            cfg, reference_ax)
        for y, scale, label in zip(y_positions, scales, labels):
            marker_diameter_points = max(
                4.0,
                base_diameter_points * scale,
            )
            legend_ax.plot(
                [0.18], [y],
                marker='o',
                linestyle='None',
                markersize=marker_diameter_points,
                markerfacecolor=cfg.get('node_color', '#14B8A6'),
                markeredgecolor='white',
                markeredgewidth=node_edge_width_points,
                transform=legend_ax.transAxes,
            )
            legend_ax.text(
                0.34, y, label,
                ha='left', va='center',
                fontsize=max(5, fc['size'] - 3),
                color=fc['color'],
                fontfamily=fc['family'],
                fontweight='bold' if fc['bold'] else 'normal',
                fontstyle='italic' if fc['italic'] else 'normal',
                transform=legend_ax.transAxes,
            )
        return True


# ── Node ───────────────────────────────────────────────────────────────

class NetworkDiagramNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Network"
        self.node_type       = "network_diagram"
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ["input"]
        self.output_channels = []
        self.config          = dict(DEFAULT_CONFIG)
        self.input_data      = None

    def set_position(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        Returns:
            bool: Result of the operation.
        """
        dlg = NetworkDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        """
        Args:
            input_data (Any): The input data.
        """
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def _get_elements(self):
        """
        Returns:
            object: Result of the operation.
        """
        sel = self.input_data.get('selected_isotopes', [])
        if sel:
            return sort_elements_by_mass([i['label'] for i in sel])
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(p.get('elements', {}).keys())
        return sort_elements_by_mass(list(all_elems))

    def extract_network_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        data_key    = NET_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        aggregation = _normalize_node_size_aggregation(
            self.config.get('node_size_aggregation', 'Sum'))
        r_threshold = self.config.get('r_threshold', 0.3)
        min_n       = self.config.get('min_particles', 5)
        itype       = self.input_data.get('type')
        elements    = self._get_elements()
        if len(elements) < 2:
            return None
        if itype == 'sample_data':
            return self._extract_single(
                data_key, elements, r_threshold, min_n, aggregation)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(
                data_key, elements, r_threshold, min_n, aggregation)
        return None

    def _extract_single(self, data_key, elements, r_threshold, min_n, aggregation):
        """Extract single-sample network data without presentation-side counts.

        Args:
            data_key (str): Selected particle property key.
            elements (list[str]): Ordered element labels.
            r_threshold (float): Absolute Pearson threshold.
            min_n (int): Minimum co-detected particle count.
            aggregation (str): Node-size aggregation mode for display scaling.

        Returns:
            dict | None: Network payload for rendering, or ``None`` when no
                particles are available.
        """
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        edges  = _compute_edges(particles, elements, data_key, r_threshold, min_n)
        sname  = self.input_data.get('sample_name', 'Sample')
        return {
            'elements':    elements,
            'edges':       edges,
            'n_particles': len(particles),
            'node_amounts': _compute_node_amounts(
                particles, elements, data_key, aggregation=aggregation),
            'sample_name': sname,
        }

    def _extract_multi(self, data_key, elements, r_threshold, min_n, aggregation):
        """Extract per-sample network data for a multi-sample selection.

        Args:
            data_key (str): Selected particle property key.
            elements (list[str]): Ordered element labels.
            r_threshold (float): Absolute Pearson threshold.
            min_n (int): Minimum co-detected particle count.
            aggregation (str): Node-size aggregation mode for display scaling.

        Returns:
            dict[str, dict] | None: Per-sample network payloads keyed by raw
                sample name, or ``None`` when no plottable samples remain.
        """
        particles = self.input_data.get('particle_data', [])
        names     = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None
        result = {}
        for sn in names:
            sp = [p for p in particles if p.get('source_sample') == sn]
            if len(sp) < min_n:
                continue
            edges = _compute_edges(sp, elements, data_key, r_threshold, min_n)
            result[sn] = {
                'elements':    elements,
                'edges':       edges,
                'n_particles': len(sp),
                'node_amounts': _compute_node_amounts(
                    sp, elements, data_key, aggregation=aggregation),
                'sample_name': sn,
            }
        return result if result else None
