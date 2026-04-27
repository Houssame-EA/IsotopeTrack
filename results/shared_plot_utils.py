import re
import math
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvasBase
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QMessageBox, QMenu, QDialog,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QDialogButtonBox
)
from PySide6.QtCore import Qt
import pyqtgraph as pg


# ─────────────────────────────────────────────
# Draggable matplotlib canvas (shared by heatmap, single/multiple, etc.)
# ─────────────────────────────────────────────

class MplDraggableCanvas(_FigureCanvasBase):
    """
    FigureCanvasQTAgg with built-in axes-drag support.

    • Left-click + drag on any axes **background** repositions that subplot
      within the figure (like the pie-chart node).
    • Middle-click anywhere resets all axes to the auto tight_layout positions.
    • Right-click is forwarded to Qt as usual (context menus work unchanged).

    Drop-in replacement for ``FigureCanvasQTAgg``:
    just pass the same ``Figure`` object::

        self.canvas = MplDraggableCanvas(self.figure)
    """

    def __init__(self, figure, parent=None):
        """
        Args:
            figure (Any): The figure.
            parent (Any): Parent widget or object.
        """
        super().__init__(figure)
        if parent:
            self.setParent(parent)

        self._drag_ax        = None
        self._drag_start_px  = None
        self._drag_ax_pos0   = None

        self._auto_positions: dict = {}

        self.mpl_connect('button_press_event',   self._drag_press)
        self.mpl_connect('motion_notify_event',  self._drag_motion)
        self.mpl_connect('button_release_event', self._drag_release)

    # ── Public API ─────────────────────────────────────────────────────

    def reset_layout(self):
        """Reset all axes to auto tight_layout positions."""
        try:
            self.figure.tight_layout()
        except Exception:
            pass
        self._auto_positions.clear()
        self.draw_idle()

    def snapshot_positions(self):
        """
        Save the current bounding box of every axes so reset_layout can
        restore them accurately even after manual drags.
        Called automatically after every full redraw.
        """
        self._auto_positions = {
            id(ax): ax.get_position() for ax in self.figure.get_axes()
        }

    # ── Drag internals ─────────────────────────────────────────────────

    def _drag_press(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button != 1 or event.inaxes is None:
            return
        for ann in event.inaxes.get_children():
            try:
                hit, _ = ann.contains(event)
                if hit and hasattr(ann, 'draggable'):
                    return
            except Exception:
                pass
        self._drag_ax       = event.inaxes
        self._drag_start_px = (event.x, event.y)
        self._drag_ax_pos0  = event.inaxes.get_position()

    def _drag_motion(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if self._drag_ax is None or event.x is None:
            return
        w_px, h_px = self.figure.get_size_inches() * self.figure.dpi
        dx = (event.x - self._drag_start_px[0]) / w_px
        dy = (event.y - self._drag_start_px[1]) / h_px
        p  = self._drag_ax_pos0
        self._drag_ax.set_position([p.x0 + dx, p.y0 + dy, p.width, p.height])
        self.draw_idle()

    def _drag_release(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button == 2:
            self.reset_layout()
        self._drag_ax       = None
        self._drag_start_px = None
        self._drag_ax_pos0  = None


# ─────────────────────────────────────────────
# Element label formatting (Symbol vs Mass+Symbol)
# ─────────────────────────────────────────────

LABEL_MODES = ['Symbol', 'Mass + Symbol']


def format_element_label(key: str, mode: str) -> str:
    """Format an element key for display according to label mode.

    'Symbol'        → bare symbol, stripping any leading mass number
                      e.g. '107Ag' → 'Ag',  '107Ag, 197Au' → 'Ag, Au'
    'Mass + Symbol' → keep as-is (full isotope notation)
                      e.g. '107Ag',          '107Ag, 197Au'
    Args:
        key (str): Dictionary or storage key.
        mode (str): Operating mode string.
    Returns:
        str: Result of the operation.
    """
    if mode == 'Mass + Symbol':
        return key
    tokens = [re.sub(r'^\d+', '', tok.strip()) for tok in key.split(',')]
    return ', '.join(tokens)


DEFAULT_FONT_FAMILY = "Times New Roman"
DEFAULT_FONT_SIZE = 18
DEFAULT_FONT_COLOR = "#000000"

FONT_FAMILIES = [
    "Times New Roman", "Arial", "Helvetica", "Calibri", "Verdana",
    "Tahoma", "Georgia", "Trebuchet MS", "Comic Sans MS", "Impact",
    "Lucida Console", "Courier New", "Palatino", "Garamond", "Book Antiqua"
]

DEFAULT_SAMPLE_COLORS = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#06B6D4', '#F97316', '#84CC16', '#EC4899', '#6366F1'
]

DATA_TYPE_OPTIONS = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)'
]

DATA_KEY_MAPPING = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Mass %': 'element_mass_fg',
    'Particle Mass %': 'particle_mass_fg',
    'Element Mole %': 'element_moles_fmol',
    'Particle Mole %': 'particle_moles_fmol'
}

TERNARY_DATA_TYPE_OPTIONS = [
    'Counts (%)',
    'Element Mass (%)',
    'Particle Mass (%)',
    'Element Moles (%)',
    'Particle Moles (%)',
]

TERNARY_DATA_KEY_MAPPING = {
    'Counts (%)': 'elements',
    'Element Mass (%)': 'element_mass_fg',
    'Particle Mass (%)': 'particle_mass_fg',
    'Element Moles (%)': 'element_moles_fmol',
    'Particle Moles (%)': 'particle_moles_fmol',
}

VIRIDIS_POSITIONS = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
VIRIDIS_COLORS = np.array([
    [68, 1, 84, 255],
    [59, 82, 139, 255],
    [33, 145, 140, 255],
    [94, 201, 98, 255],
    [253, 231, 37, 255]
], dtype=np.ubyte)


# ─────────────────────────────────────────────
# Font helpers
# ─────────────────────────────────────────────

def get_font_config(config: dict) -> dict:
    """Extract font configuration from a config dict.
    Args:
        config (dict): Configuration dictionary.
    Returns:
        dict: Result of the operation.
    """
    return {
        'family': config.get('font_family', DEFAULT_FONT_FAMILY),
        'size': config.get('font_size', DEFAULT_FONT_SIZE),
        'bold': config.get('font_bold', False),
        'italic': config.get('font_italic', False),
        'color': config.get('font_color', DEFAULT_FONT_COLOR),
    }


def make_qfont(config: dict) -> QFont:
    """Build a QFont from a config dict.
    Args:
        config (dict): Configuration dictionary.
    Returns:
        QFont: Result of the operation.
    """
    fc = get_font_config(config)
    font = QFont(fc['family'], fc['size'])
    font.setBold(fc['bold'])
    font.setItalic(fc['italic'])
    return font


def apply_font_to_pyqtgraph(plot_item, config: dict):
    """
    Apply font settings to a PyQtGraph PlotItem (axes, ticks, legend).

    Args:
        plot_item: pg.PlotItem
        config: dict with font_family, font_size, font_bold, font_italic, font_color
    """
    try:
        fc = get_font_config(config)
        font = make_qfont(config)
        color = QColor(fc['color'])

        for axis_name in ('bottom', 'left'):
            axis = plot_item.getAxis(axis_name)
            axis.setStyle(tickFont=font, tickTextOffset=10, tickLength=10)
            axis.setTextPen(color)
            axis.setPen(QPen(color, 1))
            axis.update()

        legend = getattr(plot_item, 'legend', None)
        if legend is not None:
            try:
                size_css = f'{fc["size"]}pt'
                legend.setLabelTextSize(size_css)
                legend.setLabelTextColor(color)
                for sample, label in legend.items:
                    if hasattr(label, 'setText'):
                        label.setText(label.text, color=fc['color'],
                                      size=size_css, bold=fc['bold'],
                                      italic=fc['italic'])
                legend.update()
            except Exception as e:
                print(f"Warning: legend font update failed: {e}")
    except Exception as e:
        print(f"Error applying pyqtgraph font settings: {e}")


def set_axis_labels(plot_item, x_label: str, y_label: str, config: dict):
    """Set axis labels with proper font formatting on a PyQtGraph PlotItem.
    Args:
        plot_item (Any): The plot item.
        x_label (str): The x label.
        y_label (str): The y label.
        config (dict): Configuration dictionary.
    """
    fc = get_font_config(config)
    weight = "bold" if fc['bold'] else "normal"
    style = "italic" if fc['italic'] else "normal"
    font_str = f'{style} {weight} {fc["size"]}pt {fc["family"]}'
    plot_item.setLabel('bottom', x_label, color=fc['color'], font=font_str)
    plot_item.setLabel('left', y_label, color=fc['color'], font=font_str)


def apply_font_to_matplotlib(ax, config: dict):
    """
    Apply font settings to a Matplotlib Axes (ticks, title, colorbar).

    Args:
        ax: matplotlib Axes
        config: dict with font keys
    """
    try:
        fc = get_font_config(config)
        weight = 'bold' if fc['bold'] else 'normal'
        style = 'italic' if fc['italic'] else 'normal'

        ax.tick_params(axis='both', which='major', labelsize=fc['size'], colors=fc['color'])
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontfamily(fc['family'])
            label.set_fontweight(weight)
            label.set_fontstyle(style)
            label.set_color(fc['color'])

        if ax.get_title():
            ax.set_title(ax.get_title(),
                         fontfamily=fc['family'], fontsize=fc['size'] + 2,
                         fontweight=weight, fontstyle=style, color=fc['color'])

        if hasattr(ax, 'collections'):
            for coll in ax.collections:
                cbar = getattr(coll, 'colorbar', None)
                if cbar is not None:
                    _apply_font_to_colorbar(cbar, fc)
    except Exception as e:
        print(f"Error applying matplotlib font settings: {e}")


def make_font_properties(config: dict):
    """
    Create matplotlib FontProperties from a config dict.

    Useful for mpltern ternary axes and other matplotlib text that needs
    explicit FontProperties objects (not just keyword args).

    Args:
        config: dict with 'font_family', 'font_size', 'font_bold', 'font_italic'

    Returns:
        matplotlib.font_manager.FontProperties
    """
    import matplotlib.font_manager as fm
    fc = get_font_config(config)
    return fm.FontProperties(
        family=fc['family'],
        size=fc['size'],
        weight='bold' if fc['bold'] else 'normal',
        style='italic' if fc['italic'] else 'normal',
    )


def apply_font_to_ternary(ax, config: dict):
    """
    Apply font settings to a mpltern ternary Axes.

    Handles the three ternary axes (taxis, laxis, raxis), title, and legend.

    Args:
        ax: matplotlib ternary Axes (mpltern projection)
        config: dict with font keys
    """
    try:
        fp = make_font_properties(config)
        fc = get_font_config(config)

        for axis_name in ('taxis', 'laxis', 'raxis'):
            axis = getattr(ax, axis_name, None)
            if axis is None:
                continue
            for lbl in axis.get_ticklabels():
                lbl.set_fontproperties(fp)
                lbl.set_color(fc['color'])

        legend = ax.get_legend()
        if legend is not None:
            for txt in legend.get_texts():
                txt.set_fontproperties(fp)
                txt.set_color(fc['color'])
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_alpha(0.9)
            legend.get_frame().set_edgecolor('gray')

        title = ax.get_title()
        if title:
            ax.set_title(title, fontproperties=fp, color=fc['color'])
    except Exception as e:
        print(f"Error applying ternary font settings: {e}")


def _apply_font_to_colorbar(cbar, fc: dict):
    """Apply font config dict to a matplotlib colorbar.
    Args:
        cbar (Any): The cbar.
        fc (dict): The fc.
    """
    weight = 'bold' if fc['bold'] else 'normal'
    style = 'italic' if fc['italic'] else 'normal'
    cbar.ax.tick_params(labelsize=fc['size'], colors=fc['color'])
    for label in cbar.ax.get_yticklabels():
        label.set_fontfamily(fc['family'])
        label.set_fontweight(weight)
        label.set_fontstyle(style)
        label.set_color(fc['color'])
    if cbar.ax.get_ylabel():
        cbar.set_label(cbar.ax.get_ylabel(),
                       fontfamily=fc['family'], fontsize=fc['size'],
                       fontweight=weight, fontstyle=style, color=fc['color'])


def apply_font_to_colorbar_standalone(cbar, config: dict, label_text: str = ""):
    """Apply font settings to a standalone matplotlib colorbar with an explicit label.
    Args:
        cbar (Any): The cbar.
        config (dict): Configuration dictionary.
        label_text (str): The label text.
    """
    fc = get_font_config(config)
    weight = 'bold' if fc['bold'] else 'normal'
    style = 'italic' if fc['italic'] else 'normal'

    cbar.ax.tick_params(labelsize=fc['size'], colors=fc['color'])
    for label in cbar.ax.get_yticklabels():
        label.set_fontfamily(fc['family'])
        label.set_fontweight(weight)
        label.set_fontstyle(style)
        label.set_color(fc['color'])
    if label_text:
        cbar.set_label(label_text, fontfamily=fc['family'], fontsize=fc['size'],
                       fontweight=weight, fontstyle=style, color=fc['color'])


# ─────────────────────────────────────────────
# Data filtering
# ─────────────────────────────────────────────

def apply_saturation_filter(element_data: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Remove particles where *any* element exceeds the saturation threshold.

    Args:
        element_data: DataFrame (rows = particles, cols = elements)
        config: dict with 'filter_saturated' and 'saturation_threshold'

    Returns:
        Filtered DataFrame.
    """
    if not config.get('filter_saturated', True):
        return element_data

    threshold = config.get('saturation_threshold', 10000)
    numeric_df = element_data.select_dtypes(include='number')
    mask = (numeric_df < threshold).all(axis=1)
    filtered = element_data[mask]
    print(f"Saturation filter: {len(element_data)} → {len(filtered)} particles (threshold={threshold})")
    return filtered


def apply_zero_filter(x: np.ndarray, y: np.ndarray,
                      color: np.ndarray = None) -> tuple:
    """
    Remove entries where x or y ≤ 0.

    Returns:
        (x, y, color) filtered arrays.  color may be None.
    Args:
        x (np.ndarray): Input array or value.
        y (np.ndarray): Input array or value.
        color (np.ndarray): Colour value.
    """
    mask = (x > 0) & (y > 0)
    c = color[mask] if color is not None else None
    return x[mask], y[mask], c


def apply_log_transform(values: np.ndarray, others: list = None):
    """
    Apply log10 to *values*, removing non-positive entries.

    Args:
        values: array to log-transform.
        others: list of companion arrays to filter in parallel (or None).

    Returns:
        (log_values, filtered_others) — filtered_others is a list or None.
    """
    mask = values > 0
    log_vals = np.log10(values[mask])
    if others is not None:
        return log_vals, [o[mask] for o in others]
    return log_vals, None


# ─────────────────────────────────────────────
# Equation evaluation
# ─────────────────────────────────────────────

def evaluate_equation(equation: str, element_data: dict) -> float:
    """
    Safely evaluate a mathematical equation with element name substitution.

    Supported functions: log (log10), ln, sqrt, abs, min, max, pow.

    Args:
        equation: expression string, e.g. "Fe/Ti"
        element_data: {element_name: float_value, …}

    Returns:
        float result

    Raises:
        ValueError on invalid expression.
    """
    expr = equation
    for name, value in element_data.items():
        pattern = r'\b' + re.escape(name) + r'\b'
        expr = re.sub(pattern, str(value), expr)

    expr = (expr
            .replace('log(', 'math.log10(')
            .replace('ln(', 'math.log(')
            .replace('sqrt(', 'math.sqrt(')
            )

    safe_dict = {"__builtins__": {}, "math": math,
                 "abs": abs, "min": min, "max": max, "pow": pow}
    try:
        result = eval(expr, safe_dict)
        if math.isnan(result) or math.isinf(result):
            raise ValueError("Result is NaN or infinite")
        return result
    except ZeroDivisionError:
        return float('nan')
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


def evaluate_equation_array(equation: str, df: pd.DataFrame) -> np.ndarray:
    """
    Evaluate an equation row-by-row over a DataFrame.

    Returns:
        numpy array of results (NaN for failed rows).
    Args:
        equation (str): The equation.
        df (pd.DataFrame): Pandas DataFrame.
    """
    results = np.full(len(df), np.nan)
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            results[idx] = evaluate_equation(equation, row.to_dict())
        except Exception:
            pass
    return results


# ─────────────────────────────────────────────
# Color helpers
# ─────────────────────────────────────────────

def get_sample_color(sample_name: str, index: int, config: dict) -> str:
    """Return hex color for a sample, falling back to default palette.
    Args:
        sample_name (str): The sample name.
        index (int): Row or item index.
        config (dict): Configuration dictionary.
    Returns:
        str: Result of the operation.
    """
    colors = config.get('sample_colors', {})
    if sample_name in colors:
        return colors[sample_name]
    return DEFAULT_SAMPLE_COLORS[index % len(DEFAULT_SAMPLE_COLORS)]


def get_display_name(original_name: str, config: dict) -> str:
    """Return custom display name or original.
    Args:
        original_name (str): The original name.
        config (dict): Configuration dictionary.
    Returns:
        str: Result of the operation.
    """
    return config.get('sample_name_mappings', {}).get(original_name, original_name)


def make_viridis_colormap():
    """Create a viridis-like PyQtGraph ColorMap.
    Returns:
        object: Result of the operation.
    """
    return pg.ColorMap(VIRIDIS_POSITIONS, VIRIDIS_COLORS)


# ─────────────────────────────────────────────
# Particle-by-element matrix extraction
# ─────────────────────────────────────────────

def build_element_matrix(particles: list, data_key: str) -> pd.DataFrame | None:
    """
    Build a particles × elements DataFrame from a list of particle dicts.

    Args:
        particles: list of particle dicts
        data_key: key inside each particle dict ('elements', 'element_mass_fg', etc.)

    Returns:
        DataFrame or None.
    """
    if not particles:
        return None

    all_elements = set()
    for p in particles:
        all_elements.update(p.get(data_key, {}).keys())
    if not all_elements:
        return None
    all_elements = sorted(all_elements)

    rows = []
    for p in particles:
        d = p.get(data_key, {})
        row = []
        for elem in all_elements:
            v = d.get(elem, 0)
            if data_key == 'elements':
                row.append(v if v > 0 else 0)
            else:
                row.append(v if (v > 0 and not np.isnan(v)) else 0)
        rows.append(row)

    return pd.DataFrame(rows, columns=all_elements)


# ─────────────────────────────────────────────
# Automated correlation detection
# ─────────────────────────────────────────────

def compute_correlation_matrix(df: pd.DataFrame, min_nonzero: int = 10) -> pd.DataFrame:
    """
    Compute pairwise Pearson correlation for all element columns.

    Only considers pairs where both columns have ≥ min_nonzero positive values.

    Args:
        df: particles × elements DataFrame
        min_nonzero: minimum number of jointly non-zero observations

    Returns:
        Correlation matrix as DataFrame (NaN where insufficient data).
    """
    cols = list(df.columns)
    n = len(cols)
    corr = pd.DataFrame(np.nan, index=cols, columns=cols)

    for i in range(n):
        corr.iloc[i, i] = 1.0
        for j in range(i + 1, n):
            x = df[cols[i]].values
            y = df[cols[j]].values
            mask = (x > 0) & (y > 0)
            if mask.sum() >= min_nonzero:
                r = np.corrcoef(x[mask], y[mask])[0, 1]
                corr.iloc[i, j] = r
                corr.iloc[j, i] = r

    return corr


def find_top_correlations(df: pd.DataFrame, n_top: int = 10,
                          min_nonzero: int = 10) -> list[dict]:
    """
    Find the top-N strongest correlations (by |r|) among all element pairs.

    Args:
        df: particles × elements DataFrame
        n_top: number of top correlations to return
        min_nonzero: minimum jointly non-zero observations

    Returns:
        List of dicts: [{'x': elem1, 'y': elem2, 'r': corr_value, 'n': count}, …]
        sorted by descending |r|.
    """
    corr = compute_correlation_matrix(df, min_nonzero)
    cols = list(corr.columns)
    pairs = []

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if not np.isnan(r):
                x = df[cols[i]].values
                y = df[cols[j]].values
                count = int(((x > 0) & (y > 0)).sum())
                pairs.append({'x': cols[i], 'y': cols[j], 'r': r, 'n': count})

    pairs.sort(key=lambda p: abs(p['r']), reverse=True)
    return pairs[:n_top]


# ─────────────────────────────────────────────
# Custom color bar (PyQtGraph scatter plots)
# ─────────────────────────────────────────────

class CustomColorBar:
    """
    Visual color bar for scatter plots using plot primitives.

    Creates colored rectangles + value labels on the right side of a PlotItem.
    """

    def __init__(self, plot_item, colormap, vmin: float, vmax: float,
                 config: dict, element_name: str = ""):
        """
        Args:
            plot_item (Any): The plot item.
            colormap (Any): The colormap.
            vmin (float): The vmin.
            vmax (float): The vmax.
            config (dict): Configuration dictionary.
            element_name (str): The element name.
        """
        self.plot_item = plot_item
        self.colormap = colormap
        self.vmin = vmin
        self.vmax = vmax
        self.config = config
        self.element_name = element_name
        self.items: list = []

    def create(self) -> list:
        """Draw the color bar and return list of added plot items.
        Returns:
            list: Result of the operation.
        """
        try:
            fc = get_font_config(self.config)
            data_type = self.config.get('data_type_display', 'Counts')

            n_seg = 20
            vr = self.plot_item.getViewBox().viewRange()
            xr, yr = vr[0], vr[1]

            bx = xr[1] + 0.05 * (xr[1] - xr[0])
            bw = 0.03 * (xr[1] - xr[0])
            bh = 0.7 * (yr[1] - yr[0])
            by = yr[0] + 0.15 * (yr[1] - yr[0])
            sh = bh / n_seg

            for i, val in enumerate(np.linspace(0, 1, n_seg)):
                rgba = self.colormap.map(val, mode='byte')
                color = QColor(int(rgba[0]), int(rgba[1]), int(rgba[2]), 255)
                yp = by + i * sh
                rx = [bx, bx + bw, bx + bw, bx, bx]
                ry = [yp, yp, yp + sh, yp + sh, yp]
                item = pg.PlotDataItem(x=rx, y=ry, fillLevel=yp,
                                       fillBrush=pg.mkBrush(color),
                                       pen=pg.mkPen(color))
                self.plot_item.addItem(item)
                self.items.append(item)

            for i in range(5):
                frac = i / 4
                val = self.vmin + frac * (self.vmax - self.vmin)
                yp = by + frac * bh
                ti = pg.TextItem(f"{val:.2f}", color=fc['color'], anchor=(0, 0.5))
                ti.setPos(bx + bw + 0.01 * (xr[1] - xr[0]), yp)
                self.plot_item.addItem(ti)
                self.items.append(ti)

            if self.element_name:
                title = f"{self.element_name} ({data_type})"
                ti = pg.TextItem(title, color=fc['color'], anchor=(0.5, 0))
                ti.setPos(bx + bw / 2, by + bh + 0.05 * (yr[1] - yr[0]))
                self.plot_item.addItem(ti)
                self.items.append(ti)

            return self.items
        except Exception as e:
            print(f"Error creating color bar: {e}")
            return []

    def remove(self):
        """Remove all color bar items from the plot."""
        for item in self.items:
            try:
                self.plot_item.removeItem(item)
            except Exception:
                pass
        self.items.clear()


# ─────────────────────────────────────────────
# PyQtGraph scatter helpers
# ─────────────────────────────────────────────

def create_single_color_scatter(plot_item, x, y, config, color='#3B82F6'):
    """Add a uniform-color scatter to plot_item. Returns the ScatterPlotItem.
    Args:
        plot_item (Any): The plot item.
        x (Any): Input array or value.
        y (Any): Input array or value.
        config (Any): Configuration dictionary.
        color (Any): Colour value.
    """
    size = config.get('marker_size', 6) ** 2
    alpha = int(config.get('marker_alpha', 0.7) * 255)
    c = QColor(color)
    scatter = pg.ScatterPlotItem(
        x=x, y=y, size=size,
        pen=pg.mkPen(color='black', width=0.5),
        brush=pg.mkBrush(c.red(), c.green(), c.blue(), alpha)
    )
    plot_item.addItem(scatter)
    return scatter


def create_color_mapped_scatter(plot_item, x, y, color_values, config,
                                base_color='#3B82F6', element_name="",
                                active_color_bars=None):
    """
    Add a color-mapped scatter to plot_item.

    Returns the ScatterPlotItem.
    If active_color_bars (list) is provided, appends the new CustomColorBar to it.
    Args:
        plot_item (Any): The plot item.
        x (Any): Input array or value.
        y (Any): Input array or value.
        color_values (Any): The color values.
        config (Any): Configuration dictionary.
        base_color (Any): The base color.
        element_name (Any): The element name.
        active_color_bars (Any): The active color bars.
    """
    try:
        valid = ~np.isnan(color_values)
        if not np.any(valid):
            return create_single_color_scatter(plot_item, x, y, config, base_color)

        cmin, cmax = np.nanmin(color_values), np.nanmax(color_values)
        if cmax == cmin:
            return create_single_color_scatter(plot_item, x, y, config, base_color)

        norm = (color_values - cmin) / (cmax - cmin)
        cmap = make_viridis_colormap()

        size = config.get('marker_size', 6) ** 2
        alpha = int(config.get('marker_alpha', 0.7) * 255)

        spots = []
        for i in range(len(x)):
            if np.isnan(color_values[i]):
                c = QColor(base_color)
                brush = (c.red(), c.green(), c.blue(), alpha)
            else:
                rgba = cmap.map(norm[i], mode='byte')
                brush = (int(rgba[0]), int(rgba[1]), int(rgba[2]), alpha)
            spots.append({
                'pos': (x[i], y[i]),
                'size': size,
                'pen': pg.mkPen(color='black', width=0.5),
                'brush': pg.mkBrush(*brush)
            })

        scatter = pg.ScatterPlotItem()
        scatter.addPoints(spots)
        plot_item.addItem(scatter)

        if element_name and active_color_bars is not None:
            cb = CustomColorBar(plot_item, cmap, cmin, cmax, config, element_name)
            cb.create()
            active_color_bars.append(cb)

        return scatter
    except Exception as e:
        print(f"Error creating color-mapped scatter: {e}")
        return create_single_color_scatter(plot_item, x, y, config, base_color)


def add_trend_line(plot_item, x, y, color):
    """Add a dashed linear regression line.
    Args:
        plot_item (Any): The plot item.
        x (Any): Input array or value.
        y (Any): Input array or value.
        color (Any): Colour value.
    """
    try:
        if len(x) > 1:
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            xt = np.linspace(x.min(), x.max(), 100)
            plot_item.addItem(pg.PlotDataItem(
                x=xt, y=p(xt),
                pen=pg.mkPen(color=color, style=Qt.DashLine, width=2)))
    except Exception as e:
        print(f"Error adding trend line: {e}")


def add_correlation_text(plot_item, x, y, config):
    """Add Pearson r text in the top-left corner of the plot.
    Args:
        plot_item (Any): The plot item.
        x (Any): Input array or value.
        y (Any): Input array or value.
        config (Any): Configuration dictionary.
    """
    try:
        if len(x) > 1:
            r = np.corrcoef(x, y)[0, 1]
            fc = get_font_config(config)
            ti = pg.TextItem(f'r = {r:.3f}', anchor=(0, 1), color=fc['color'])
            plot_item.addItem(ti)
            vr = plot_item.getViewBox().state['viewRange']
            ti.setPos(vr[0][0] + 0.05 * (vr[0][1] - vr[0][0]),
                      vr[1][0] + 0.95 * (vr[1][1] - vr[1][0]))
    except Exception as e:
        print(f"Error adding correlation text: {e}")


# ─────────────────────────────────────────────
# Export / download helpers
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Download Configuration Dialog
# ─────────────────────────────────────────────

class DownloadConfigDialog(QDialog):
    """
    Unified download configuration dialog for all plot types.

    Supports PNG (with scale or custom pixel size), SVG, PDF, and CSV output.
    Used by both PyQtGraph and Matplotlib export helpers.

    CSV export requires the caller to attach data via set_csv_data() before
    calling exec(). The dialog hides irrelevant resolution/appearance
    controls when CSV is selected.
    """

    FORMATS_PYQTGRAPH  = ['PNG', 'SVG', 'PDF', 'CSV']
    FORMATS_MATPLOTLIB = ['PNG', 'SVG', 'PDF', 'CSV']

    def __init__(self, default_filename: str = 'figure',
                 formats: list[str] | None = None,
                 parent=None):
        """
        Args:
            default_filename (str): The default filename.
            formats (list[str] | None): The formats.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Download Figure")
        self.setMinimumWidth(380)
        self._filename_base = default_filename
        self._formats = formats or self.FORMATS_PYQTGRAPH
        self._csv_data = None
        self._csv_columns = None
        self._build_ui()

    # ── Public API for CSV data ──────────────────────────────

    def set_csv_data(self, data, columns: dict | None = None):
        """
        Attach data so the dialog can export CSV directly.

        Args:
            data: one of:
                - pd.DataFrame  (particles × elements, or x/y columns)
                - dict           {sample_name: pd.DataFrame}
                - list[dict]     particle dicts (will be flattened)
                - dict with 'x'/'y' keys  → simple two-column frame
            columns: optional rename mapping, e.g. {'x': 'Fe (counts)', 'y': 'Ti (counts)'}
        """
        self._csv_data = data
        self._csv_columns = columns

    # ── UI Construction ──────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── File ──────────────────────────────────────────────
        file_group = QGroupBox("File")
        fl = QFormLayout(file_group)

        self.filename_edit = QLineEdit(self._filename_base)
        fl.addRow("Filename (no ext):", self.filename_edit)

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(self._formats)
        self.fmt_combo.currentTextChanged.connect(self._on_format_change)
        fl.addRow("Format:", self.fmt_combo)

        layout.addWidget(file_group)

        # ── Resolution / Size ─────────────────────────────────
        self._res_group = QGroupBox("Resolution / Size")
        fl2 = QFormLayout(self._res_group)

        self.use_custom_size = QCheckBox("Use custom pixel dimensions")
        self.use_custom_size.setChecked(False)
        self.use_custom_size.stateChanged.connect(self._on_size_toggle)
        fl2.addRow(self.use_custom_size)

        self._scale_row_label = QLabel("Scale factor:")
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 8)
        self.scale_spin.setValue(2)
        self.scale_spin.setSuffix("×")
        self.scale_spin.setToolTip(
            "Multiplies the on-screen pixel size.\n"
            "2× → double resolution (good for publications).\n"
            "Only applies to PNG.")
        fl2.addRow(self._scale_row_label, self.scale_spin)

        self._dpi_row_label = QLabel("DPI (PNG/PDF):")
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" dpi")
        fl2.addRow(self._dpi_row_label, self.dpi_spin)
        self._dpi_row_label.setVisible(False)
        self.dpi_spin.setVisible(False)

        self._w_label = QLabel("Width:")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(400, 8000)
        self.width_spin.setValue(1920)
        self.width_spin.setSuffix(" px")
        fl2.addRow(self._w_label, self.width_spin)

        self._h_label = QLabel("Height:")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(300, 6000)
        self.height_spin.setValue(1200)
        self.height_spin.setSuffix(" px")
        fl2.addRow(self._h_label, self.height_spin)

        layout.addWidget(self._res_group)

        # ── Appearance ────────────────────────────────────────
        self._app_group = QGroupBox("Appearance")
        fl3 = QFormLayout(self._app_group)

        self.bg_combo = QComboBox()
        self.bg_combo.addItems(['White', 'Transparent', 'Black'])
        fl3.addRow("Background:", self.bg_combo)

        layout.addWidget(self._app_group)

        self._csv_group = QGroupBox("CSV Options")
        fl4 = QFormLayout(self._csv_group)

        self.csv_separator_combo = QComboBox()
        self.csv_separator_combo.addItems(['Comma (,)', 'Semicolon (;)', 'Tab'])
        fl4.addRow("Separator:", self.csv_separator_combo)

        self.csv_include_index = QCheckBox("Include row index")
        self.csv_include_index.setChecked(False)
        fl4.addRow(self.csv_include_index)

        self.csv_decimal_spin = QSpinBox()
        self.csv_decimal_spin.setRange(1, 12)
        self.csv_decimal_spin.setValue(6)
        self.csv_decimal_spin.setSuffix(" digits")
        fl4.addRow("Decimal precision:", self.csv_decimal_spin)

        layout.addWidget(self._csv_group)
        self._csv_group.setVisible(False)

        # ── Buttons ───────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._on_format_change(self.fmt_combo.currentText())
        self._on_size_toggle()

    # ── Slot helpers ─────────────────────────────────────────

    def _on_format_change(self, fmt: str):
        """
        Args:
            fmt (str): The fmt.
        """
        is_png = (fmt == 'PNG')
        is_csv = (fmt == 'CSV')

        self._res_group.setVisible(not is_csv)
        self._app_group.setVisible(not is_csv)
        self._csv_group.setVisible(is_csv)

        if not is_csv:
            self.use_custom_size.setEnabled(is_png)
            self.scale_spin.setEnabled(is_png and not self.use_custom_size.isChecked())
            self._scale_row_label.setEnabled(is_png and not self.use_custom_size.isChecked())
            self.width_spin.setEnabled(is_png and self.use_custom_size.isChecked())
            self.height_spin.setEnabled(is_png and self.use_custom_size.isChecked())
            self._w_label.setEnabled(is_png and self.use_custom_size.isChecked())
            self._h_label.setEnabled(is_png and self.use_custom_size.isChecked())
            self.bg_combo.setEnabled(fmt != 'SVG')

    def _on_size_toggle(self):
        custom = self.use_custom_size.isChecked()
        is_png = self.fmt_combo.currentText() == 'PNG'
        self.scale_spin.setEnabled(not custom and is_png)
        self._scale_row_label.setEnabled(not custom and is_png)
        self.width_spin.setEnabled(custom and is_png)
        self.height_spin.setEnabled(custom and is_png)
        self._w_label.setEnabled(custom and is_png)
        self._h_label.setEnabled(custom and is_png)

    def show_dpi_control(self, visible: bool = True):
        """Call from Matplotlib callers to expose the DPI spinner.
        Args:
            visible (bool): Whether the item is visible.
        """
        self._dpi_row_label.setVisible(visible)
        self.dpi_spin.setVisible(visible)

    # ── Result ────────────────────────────────────────────────

    def _get_csv_separator(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        text = self.csv_separator_combo.currentText()
        if 'Semicolon' in text:
            return ';'
        elif 'Tab' in text:
            return '\t'
        return ','

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'filename':         self.filename_edit.text().strip() or 'figure',
            'format':           self.fmt_combo.currentText(),
            'scale':            self.scale_spin.value(),
            'dpi':              self.dpi_spin.value(),
            'use_custom_size':  self.use_custom_size.isChecked(),
            'width':            self.width_spin.value(),
            'height':           self.height_spin.value(),
            'background':       self.bg_combo.currentText(),
            'csv_separator':    self._get_csv_separator(),
            'csv_include_index': self.csv_include_index.isChecked(),
            'csv_precision':    self.csv_decimal_spin.value(),
        }


# ─────────────────────────────────────────────
# CSV Data Export
# ─────────────────────────────────────────────

def _prepare_csv_dataframe(data, columns: dict | None = None) -> pd.DataFrame:
    """
    Normalise various data shapes into a single DataFrame for CSV export.

    Accepted input types:
        - pd.DataFrame       → returned as-is (with optional column rename)
        - dict of DataFrames → concatenated with a 'Sample' column
        - list[dict]         → flattened particle dicts
        - dict with arrays   → simple column frame (e.g. {'x': [...], 'y': [...]})
    Args:
        data (Any): Input data.
        columns (dict | None): The columns.
    Returns:
        pd.DataFrame: Result of the operation.
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy()

    elif isinstance(data, dict) and all(isinstance(v, pd.DataFrame) for v in data.values()):
        frames = []
        for name, frame in data.items():
            f = frame.copy()
            f.insert(0, 'Sample', name)
            frames.append(f)
        df = pd.concat(frames, ignore_index=True)

    elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        rows = []
        for p in data:
            row = {}
            for key, val in p.items():
                if isinstance(val, dict):
                    for k2, v2 in val.items():
                        col = f"{k2}" if key == 'elements' else f"{k2} ({key})"
                        row[col] = v2
                else:
                    row[key] = val
            rows.append(row)
        df = pd.DataFrame(rows).fillna(0)

    elif isinstance(data, dict):
        df = pd.DataFrame(data)

    else:
        raise ValueError(f"Unsupported data type for CSV export: {type(data)}")

    if columns:
        df = df.rename(columns=columns)

    return df


def export_csv(data, parent, default_name: str = 'data',
               columns: dict | None = None,
               separator: str = ',',
               include_index: bool = False,
               precision: int = 6):
    """
    Export data to CSV with a file-save dialog.

    Args:
        data:          DataFrame, dict of DataFrames, list of particle dicts, etc.
        parent:        QWidget parent for dialogs
        default_name:  suggested filename (no extension)
        columns:       optional column rename mapping
        separator:     CSV delimiter
        include_index: whether to write the DataFrame index
        precision:     float decimal places
    """
    ext = 'tsv' if separator == '\t' else 'csv'
    path, _ = QFileDialog.getSaveFileName(
        parent, "Export Data",
        f"{default_name}.{ext}",
        f"CSV Files (*.csv *.tsv);;All Files (*)"
    )
    if not path:
        return
    if not path.lower().endswith(('.csv', '.tsv')):
        path += f'.{ext}'

    try:
        df = _prepare_csv_dataframe(data, columns)
        df.to_csv(path, sep=separator, index=include_index,
                  float_format=f'%.{precision}f')
        QMessageBox.information(
            parent, "Saved",
            f"Exported {len(df)} rows × {len(df.columns)} columns to:\n{path}"
        )
    except Exception as e:
        QMessageBox.critical(parent, "Export Error", f"CSV export failed:\n{e}")
        import traceback; traceback.print_exc()


def export_plot_data_csv(x_data, y_data, parent,
                         x_label: str = 'X', y_label: str = 'Y',
                         color_data=None, color_label: str = '',
                         sample_labels=None,
                         default_name: str = 'plot_data',
                         separator: str = ',',
                         include_index: bool = False,
                         precision: int = 6):
    """
    Export scatter / correlation plot arrays to CSV.

    Handles single-sample and multi-sample data.

    Args:
        x_data:        np.ndarray  OR  list[np.ndarray]
        y_data:        np.ndarray  OR  list[np.ndarray]
        color_data:    optional np.ndarray or list[np.ndarray]
        sample_labels: list of sample name strings
    """
    if isinstance(x_data, np.ndarray):
        x_data = [x_data]
        y_data = [y_data]
        color_data = [color_data] if color_data is not None else None
        sample_labels = sample_labels or ['']

    rows = []
    for i, (x, y) in enumerate(zip(x_data, y_data)):
        sample = sample_labels[i] if sample_labels else ''
        for j in range(len(x)):
            row = {}
            if sample:
                row['Sample'] = sample
            row[x_label] = x[j]
            row[y_label] = y[j]
            if color_data is not None and i < len(color_data) and color_data[i] is not None:
                row[color_label or 'Color'] = color_data[i][j]
            rows.append(row)

    df = pd.DataFrame(rows)
    export_csv(df, parent, default_name,
               separator=separator, include_index=include_index,
               precision=precision)


def export_element_matrix_csv(df: pd.DataFrame, parent,
                              default_name: str = 'particle_data',
                              separator: str = ',',
                              include_index: bool = False,
                              precision: int = 6):
    """Export a particles × elements DataFrame directly to CSV.
    Args:
        df (pd.DataFrame): Pandas DataFrame.
        parent (Any): Parent widget or object.
        default_name (str): The default name.
        separator (str): The separator.
        include_index (bool): The include index.
        precision (int): The precision.
    """
    export_csv(df, parent, default_name,
               separator=separator, include_index=include_index,
               precision=precision)


# ─────────────────────────────────────────────
# Unified PyQtGraph export (PNG / SVG / PDF / CSV)
# ─────────────────────────────────────────────

def download_pyqtgraph_figure(plot_widget, parent,
                               default_name: str = 'figure',
                               csv_data=None,
                               csv_columns: dict | None = None):
    """
    Export a PyQtGraph GraphicsLayoutWidget to PNG, SVG, PDF, or CSV.

    The FULL scene is captured (all subplots), not just a single PlotItem.

    Args:
        plot_widget:  pg.GraphicsLayoutWidget
        parent:       QWidget parent for dialogs
        default_name: suggested filename stem (no extension)
        csv_data:     data to export when CSV is chosen (DataFrame, dict, etc.)
        csv_columns:  optional column rename mapping for CSV
    """
    import pyqtgraph.exporters as exp

    dlg = DownloadConfigDialog(default_name, parent=parent)
    if csv_data is not None:
        dlg.set_csv_data(csv_data, csv_columns)
    if dlg.exec() != QDialog.Accepted:
        return

    cfg = dlg.collect()
    fmt = cfg['format']

    # ── CSV branch ────────────────────────────────────────────
    if fmt == 'CSV':
        if csv_data is None and dlg._csv_data is None:
            QMessageBox.warning(parent, "No Data",
                                "No data available for CSV export.\n"
                                "Choose an image format instead.")
            return
        data = csv_data if csv_data is not None else dlg._csv_data
        export_csv(data, parent, cfg['filename'],
                   columns=csv_columns or dlg._csv_columns,
                   separator=cfg['csv_separator'],
                   include_index=cfg['csv_include_index'],
                   precision=cfg['csv_precision'])
        return

    # ── Image / vector branch ─────────────────────────────────
    ext_map = {'PNG': 'png', 'SVG': 'svg', 'PDF': 'pdf'}
    ext = ext_map[fmt]

    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Figure",
        f"{cfg['filename']}.{ext}",
        f"{fmt} Files (*.{ext});;All Files (*)"
    )
    if not path:
        return
    if not path.lower().endswith(f'.{ext}'):
        path += f'.{ext}'

    try:
        scene = plot_widget.scene()

        if fmt == 'SVG':
            exporter = exp.SVGExporter(scene)
            exporter.export(path)

        elif fmt == 'PNG':
            exporter = exp.ImageExporter(scene)

            bg = cfg['background']
            if bg == 'Transparent':
                exporter.parameters()['background'] = pg.mkColor(0, 0, 0, 0)
            elif bg == 'Black':
                exporter.parameters()['background'] = pg.mkColor('k')
            else:
                exporter.parameters()['background'] = pg.mkColor('w')

            if cfg['use_custom_size']:
                exporter.parameters()['width']  = cfg['width']
                exporter.parameters()['height'] = cfg['height']
            else:
                exporter.parameters()['width']  = int(plot_widget.width()  * cfg['scale'])
                exporter.parameters()['height'] = int(plot_widget.height() * cfg['scale'])

            exporter.export(path)

        elif fmt == 'PDF':
            from PySide6.QtPrintSupport import QPrinter
            from PySide6.QtGui import QPainter, QPixmap
            import tempfile, os

            exporter = exp.ImageExporter(scene)
            exporter.parameters()['background'] = pg.mkColor('w')
            exporter.parameters()['width']  = int(plot_widget.width()  * 3)
            exporter.parameters()['height'] = int(plot_widget.height() * 3)

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
            exporter.export(tmp_path)

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageOrientation(QPrinter.Landscape)

            pixmap  = QPixmap(tmp_path)
            painter = QPainter(printer)
            rect    = painter.viewport()
            size    = pixmap.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            os.unlink(tmp_path)

        QMessageBox.information(parent, "Saved", f"Figure saved to:\n{path}")

    except Exception as e:
        QMessageBox.critical(parent, "Export Error", f"Failed to export figure:\n{e}")
        import traceback; traceback.print_exc()


# ─────────────────────────────────────────────
# Unified Matplotlib export (PNG / SVG / PDF / CSV)
# ─────────────────────────────────────────────

def download_matplotlib_figure(figure, parent,
                                default_name: str = 'figure',
                                csv_data=None,
                                csv_columns: dict | None = None):
    """
    Export a Matplotlib Figure to PNG, SVG, PDF, or CSV.

    Args:
        figure:       matplotlib.figure.Figure
        parent:       QWidget parent for dialogs
        default_name: suggested filename stem (no extension)
        csv_data:     data to export when CSV is chosen
        csv_columns:  optional column rename mapping for CSV
    """
    dlg = DownloadConfigDialog(
        default_name,
        formats=['PNG', 'SVG', 'PDF', 'CSV'],
        parent=parent
    )
    dlg.show_dpi_control(True)
    if csv_data is not None:
        dlg.set_csv_data(csv_data, csv_columns)
    if dlg.exec() != QDialog.Accepted:
        return

    cfg = dlg.collect()
    fmt = cfg['format']

    # ── CSV branch ────────────────────────────────────────────
    if fmt == 'CSV':
        if csv_data is None and dlg._csv_data is None:
            QMessageBox.warning(parent, "No Data",
                                "No data available for CSV export.\n"
                                "Choose an image format instead.")
            return
        data = csv_data if csv_data is not None else dlg._csv_data
        export_csv(data, parent, cfg['filename'],
                   columns=csv_columns or dlg._csv_columns,
                   separator=cfg['csv_separator'],
                   include_index=cfg['csv_include_index'],
                   precision=cfg['csv_precision'])
        return

    # ── Image / vector branch ─────────────────────────────────
    ext_map = {'PNG': 'png', 'SVG': 'svg', 'PDF': 'pdf'}
    ext = ext_map[fmt]

    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Figure",
        f"{cfg['filename']}.{ext}",
        f"{fmt} Files (*.{ext});;All Files (*)"
    )
    if not path:
        return
    if not path.lower().endswith(f'.{ext}'):
        path += f'.{ext}'

    try:
        bg = cfg['background']
        facecolor = 'none' if bg == 'Transparent' else ('black' if bg == 'Black' else 'white')

        figure.savefig(
            path,
            dpi=cfg['dpi'],
            bbox_inches='tight',
            facecolor=facecolor,
            edgecolor='none',
        )
        QMessageBox.information(parent, "Saved", f"Figure saved to:\n{path}")

    except Exception as e:
        QMessageBox.critical(parent, "Export Error", f"Failed to export figure:\n{e}")
        import traceback; traceback.print_exc()
# ─────────────────────────────────────────────
# Generic right-click settings dialog builder
# ─────────────────────────────────────────────

class FontSettingsGroup:
    """
    Reusable font-settings QGroupBox builder.

    Call .build() to get the QGroupBox, then .collect() to read current values.
    """

    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary.
        """
        self._config = config
        self.family_combo = None
        self.size_spin = None
        self.bold_cb = None
        self.italic_cb = None
        self.color_btn = None
        self._color = QColor(config.get('font_color', DEFAULT_FONT_COLOR))

    def build(self, on_change=None) -> QGroupBox:
        """
        Args:
            on_change (Any): The on change.
        Returns:
            QGroupBox: Result of the operation.
        """
        group = QGroupBox("Font Settings")
        layout = QFormLayout(group)

        self.family_combo = QComboBox()
        self.family_combo.addItems(FONT_FAMILIES)
        self.family_combo.setCurrentText(self._config.get('font_family', DEFAULT_FONT_FAMILY))
        if on_change:
            self.family_combo.currentTextChanged.connect(on_change)
        layout.addRow("Font Family:", self.family_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(self._config.get('font_size', DEFAULT_FONT_SIZE))
        if on_change:
            self.size_spin.valueChanged.connect(on_change)
        layout.addRow("Font Size:", self.size_spin)

        style_row = QHBoxLayout()
        self.bold_cb = QCheckBox("Bold")
        self.bold_cb.setChecked(self._config.get('font_bold', False))
        self.italic_cb = QCheckBox("Italic")
        self.italic_cb.setChecked(self._config.get('font_italic', False))
        if on_change:
            self.bold_cb.stateChanged.connect(on_change)
            self.italic_cb.stateChanged.connect(on_change)
        style_row.addWidget(self.bold_cb)
        style_row.addWidget(self.italic_cb)
        style_row.addStretch()
        layout.addRow("Style:", style_row)

        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(
            f"background-color: {self._color.name()}; min-height: 25px;")
        self.color_btn.clicked.connect(self._pick_color)
        if on_change:
            self.color_btn.clicked.connect(on_change)
        layout.addRow("Color:", self.color_btn)

        return group

    def _pick_color(self):
        c = QColorDialog.getColor(self._color)
        if c.isValid():
            self._color = c
            self.color_btn.setStyleSheet(
                f"background-color: {c.name()}; min-height: 25px;")

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'font_family': self.family_combo.currentText(),
            'font_size': self.size_spin.value(),
            'font_bold': self.bold_cb.isChecked(),
            'font_italic': self.italic_cb.isChecked(),
            'font_color': self._color.name(),
        }


class LegendGroup:
    """
    Reusable legend settings QGroupBox builder.

    Call .build() to get the QGroupBox, then .collect() to read current values.
    """

    _POSITIONS = [
        'best', 'upper right', 'upper left', 'lower left', 'lower right',
        'center left', 'center right', 'lower center', 'upper center', 'center',
    ]

    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary.
        """
        self._config = config
        self.show_cb = None
        self.pos_combo = None
        self.outside_cb = None

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        group = QGroupBox("Legend")
        layout = QFormLayout(group)

        self.show_cb = QCheckBox("Show Legend")
        self.show_cb.setChecked(self._config.get('legend_show', False))
        layout.addRow("", self.show_cb)

        self.pos_combo = QComboBox()
        self.pos_combo.addItems(self._POSITIONS)
        cur = self._config.get('legend_position', 'best')
        if cur in self._POSITIONS:
            self.pos_combo.setCurrentText(cur)
        layout.addRow("Position:", self.pos_combo)

        self.outside_cb = QCheckBox("Place Outside Axes")
        self.outside_cb.setChecked(self._config.get('legend_outside', False))
        layout.addRow("", self.outside_cb)

        return group

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'legend_show':     self.show_cb.isChecked(),
            'legend_position': self.pos_combo.currentText(),
            'legend_outside':  self.outside_cb.isChecked(),
        }


class ExportSettingsGroup:
    """
    Reusable export settings QGroupBox builder (background colour, format, DPI, figure size).

    Call .build() to get the QGroupBox, then .collect() to read current values.
    """

    _FORMATS = ['SVG', 'PDF', 'PNG', 'EPS']
    _BACKGROUNDS = ['White', 'Transparent', 'Black']

    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary.
        """
        self._config = config
        self._bg_btn = None
        self._bg_color = config.get('bg_color', '#FFFFFF')
        self.fmt_combo = None
        self.dpi_spin = None
        self.custom_size_cb = None
        self.width_spin = None
        self.height_spin = None

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        from PySide6.QtWidgets import QDoubleSpinBox as _QDbl
        group = QGroupBox("Export & Appearance")
        layout = QFormLayout(group)

        self._bg_btn = QPushButton()
        self._bg_btn.setFixedHeight(24)
        self._bg_btn.setStyleSheet(
            f'background-color:{self._bg_color}; border:1px solid #666; border-radius:2px;')
        self._bg_btn.clicked.connect(self._pick_bg)
        layout.addRow("Background:", self._bg_btn)

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(self._FORMATS)
        cur = self._config.get('export_format', 'svg').upper()
        self.fmt_combo.setCurrentText(cur if cur in self._FORMATS else 'SVG')
        layout.addRow("Format:", self.fmt_combo)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setSuffix(" dpi")
        self.dpi_spin.setValue(self._config.get('export_dpi', 300))
        layout.addRow("DPI:", self.dpi_spin)

        self.custom_size_cb = QCheckBox("Custom Figure Size")
        self.custom_size_cb.setChecked(self._config.get('use_custom_figsize', False))
        layout.addRow("", self.custom_size_cb)

        size_row = QHBoxLayout()
        self.width_spin = _QDbl()
        self.width_spin.setRange(2.0, 40.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setDecimals(1)
        self.width_spin.setSuffix(" in")
        self.width_spin.setValue(self._config.get('figsize_w', 12.0))
        self.height_spin = _QDbl()
        self.height_spin.setRange(2.0, 30.0)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.setDecimals(1)
        self.height_spin.setSuffix(" in")
        self.height_spin.setValue(self._config.get('figsize_h', 8.0))
        size_row.addWidget(QLabel("W:"))
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("H:"))
        size_row.addWidget(self.height_spin)
        w = QWidget(); w.setLayout(size_row)
        layout.addRow("Figure Size:", w)

        return group

    def _pick_bg(self):
        c = QColorDialog.getColor(QColor(self._bg_color))
        if c.isValid():
            self._bg_color = c.name()
            self._bg_btn.setStyleSheet(
                f'background-color:{self._bg_color}; border:1px solid #666; border-radius:2px;')

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'bg_color':           self._bg_color,
            'export_format':      self.fmt_combo.currentText().lower(),
            'export_dpi':         self.dpi_spin.value(),
            'use_custom_figsize': self.custom_size_cb.isChecked(),
            'figsize_w':          self.width_spin.value(),
            'figsize_h':          self.height_spin.value(),
        }


def build_axis_labels(config: dict, mode: str = 'simple') -> tuple[str, str]:
    """
    Build x/y axis label strings from config.

    Returns:
        (x_label, y_label)
    Args:
        config (dict): Configuration dictionary.
        mode (str): Operating mode string.
    """
    dt = config.get('data_type_display', 'Counts')
    log_x = config.get('log_x', False)
    log_y = config.get('log_y', False)

    if mode == 'simple' or config.get('mode') == 'Simple Element Correlation':
        xn = config.get('x_element', 'X')
        yn = config.get('y_element', 'Y')
    else:
        xn = config.get('x_label', config.get('x_equation', 'X'))
        yn = config.get('y_label', config.get('y_equation', 'Y'))

    xl = f"log₁₀({xn}) ({dt})" if log_x else f"{xn} ({dt})"
    yl = f"log₁₀({yn}) ({dt})" if log_y else f"{yn} ({dt})"
    return xl, yl


import pyqtgraph as pg
from PySide6.QtCore import Qt as _Qt
from PySide6.QtGui import QColor as _QColor

SHADE_TYPES = [
    'None',
    'Mean +/- 1 SD',
    'Mean +/- 2 SD',
    'Median +/- IQR  (Q1-Q3)',
    'P5 - P95',
    'P1 - P99',
]

_QT_LINE = {
    'solid': _Qt.SolidLine,
    'dash':  _Qt.DashLine,
    'dot':   _Qt.DotLine,
}


def filter_outliers_percentile(values: np.ndarray, pct: float = 99.0) -> np.ndarray:
    """Remove values outside [100-pct, pct] percentile range.

    Args:
        values: 1-D array of numeric values.
        pct:    Upper keep-percentile (e.g. 99 keeps the central 98%).

    Returns:
        Filtered array (may be shorter than input).
    """
    if len(values) < 4:
        return values
    lo, hi = np.percentile(values, [100.0 - pct, pct])
    return values[(values >= lo) & (values <= hi)]


def apply_outlier_filter(values: np.ndarray, cfg: dict) -> np.ndarray:
    """Apply percentile outlier filter when cfg['filter_outliers'] is True.
    Args:
        values (np.ndarray): Array or sequence of values.
        cfg (dict): The cfg.
    Returns:
        np.ndarray: Result of the operation.
    """
    if not cfg.get('filter_outliers', False):
        return values
    pct = float(cfg.get('outlier_percentile', 99.0))
    return filter_outliers_percentile(values, pct)


def _apply_box(plot_item, cfg: dict):
    """Show or hide the top + right axes (figure box frame).
    Args:
        plot_item (Any): The plot item.
        cfg (dict): The cfg.
    """
    show = cfg.get('show_box', True)
    plot_item.showAxis('top', show)
    plot_item.showAxis('right', show)
    if show:
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)


def _add_shaded_region_hist(plot_item, values: np.ndarray, cfg: dict):
    """Vertical shaded statistical band for histogram-type plots.

    ``values`` must be in plot-space already (log10 if log_x is on).
    Applies to every subplot since it is called per-panel.
    Args:
        plot_item (Any): The plot item.
        values (np.ndarray): Array or sequence of values.
        cfg (dict): The cfg.
    Returns:
        object: Result of the operation.
    """
    shade_type = cfg.get('shade_type', 'None')
    if shade_type == 'None' or len(values) < 3:
        return
    log_x = cfg.get('log_x', True)
    color = cfg.get('shade_color', '#534AB7')
    alpha = int(cfg.get('shade_alpha', 0.18) * 255)
    real_vals = (10 ** values) if log_x else values

    def _to_plot(v):
        """
        Args:
            v (Any): The v.
        Returns:
            object: Result of the operation.
        """
        v = float(v)
        return float(np.log10(max(v, 1e-12))) if log_x else v

    lo = hi = None
    if shade_type == 'Mean +/- 1 SD':
        mu, sd = float(np.mean(real_vals)), float(np.std(real_vals))
        lo, hi = _to_plot(max(mu - sd, 1e-12 if log_x else mu - sd)), _to_plot(mu + sd)
    elif shade_type == 'Mean +/- 2 SD':
        mu, sd = float(np.mean(real_vals)), float(np.std(real_vals))
        lo, hi = _to_plot(max(mu - 2*sd, 1e-12 if log_x else mu - 2*sd)), _to_plot(mu + 2*sd)
    elif shade_type == 'Median +/- IQR  (Q1-Q3)':
        q1, q3 = np.percentile(real_vals, [25, 75])
        lo, hi = _to_plot(q1), _to_plot(q3)
    elif shade_type == 'P5 - P95':
        p5, p95 = np.percentile(real_vals, [5, 95])
        lo, hi = _to_plot(p5), _to_plot(p95)
    elif shade_type == 'P1 - P99':
        p1, p99 = np.percentile(real_vals, [1, 99])
        lo, hi = _to_plot(p1), _to_plot(p99)

    if lo is None or not np.isfinite(lo) or not np.isfinite(hi):
        return
    qc = _QColor(color); qc.setAlpha(alpha)
    band = pg.LinearRegionItem(
        values=(min(lo, hi), max(lo, hi)),
        orientation='vertical',
        brush=pg.mkBrush(qc),
        pen=pg.mkPen(color, width=0.8, style=_Qt.DashLine),
        movable=False,
    )
    band.setZValue(-10)
    plot_item.addItem(band)


def _add_hband(plot_item, lo: float, hi: float,
               color: str = '#534AB7', alpha: float = 0.18,
               label: str = ''):
    """Horizontal shaded band for scatter / box plots (Y-axis range).
    Args:
        plot_item (Any): The plot item.
        lo (float): The lo.
        hi (float): The hi.
        color (str): Colour value.
        alpha (float): The alpha.
        label (str): Label text.
    """
    qc = _QColor(color); qc.setAlpha(int(alpha * 255))
    band = pg.LinearRegionItem(
        values=(min(lo, hi), max(lo, hi)),
        orientation='horizontal',
        brush=pg.mkBrush(qc),
        pen=pg.mkPen(color, width=0.8, style=_Qt.DashLine),
        movable=False,
    )
    band.setZValue(-10)
    plot_item.addItem(band)


def _add_stat_lines_hist(plot_item, values: np.ndarray, cfg: dict):
    """Vertical stat lines (median / mean / mode) for histogram plots.

    ``values`` must already be in plot-space.
    Colors, styles, widths all read from cfg.
    Args:
        plot_item (Any): The plot item.
        values (np.ndarray): Array or sequence of values.
        cfg (dict): The cfg.
    """
    if len(values) == 0:
        return
    log_x = cfg.get('log_x', True)

    if cfg.get('show_median_line', False):
        med = float(np.median(values))
        med_real = 10**med if log_x else med
        color = cfg.get('median_line_color', '#0F6E56')
        style = _QT_LINE.get(cfg.get('median_line_style', 'dash'), _Qt.DashLine)
        width = int(cfg.get('median_line_width', 2))
        plot_item.addItem(pg.InfiniteLine(
            pos=med, angle=90,
            pen=pg.mkPen(color=color, style=style, width=width),
            label=f'median: {med_real:.3g}',
            labelOpts={'color': color, 'movable': False, 'position': 0.92,
                       'anchors': [(0, 1), (0, 1)]},
        ))

    if cfg.get('show_mean_line', False):
        real_vals = (10**values) if log_x else values
        mu = float(np.mean(real_vals))
        mu_plot = float(np.log10(max(mu, 1e-12))) if log_x else mu
        color = cfg.get('mean_line_color', '#B45309')
        style = _QT_LINE.get(cfg.get('mean_line_style', 'solid'), _Qt.SolidLine)
        width = int(cfg.get('mean_line_width', 2))
        plot_item.addItem(pg.InfiniteLine(
            pos=mu_plot, angle=90,
            pen=pg.mkPen(color=color, style=style, width=width),
            label=f'mean: {mu:.3g}',
            labelOpts={'color': color, 'movable': False, 'position': 0.80,
                       'anchors': [(0, 1), (0, 1)]},
        ))

    if cfg.get('show_mode_marker', False) and len(values) > 3:
        try:
            bins = max(10, int(cfg.get('bins', 50)))
            counts, edges = np.histogram(values, bins=bins)
            peak_idx = int(np.argmax(counts))
            peak_x = float((edges[peak_idx] + edges[peak_idx + 1]) / 2)
            peak_real = 10**peak_x if log_x else peak_x
            color = cfg.get('mode_line_color', '#7C3AED')
            style = _QT_LINE.get(cfg.get('mode_line_style', 'dot'), _Qt.DotLine)
            width = int(cfg.get('mode_line_width', 2))
            plot_item.addItem(pg.InfiniteLine(
                pos=peak_x, angle=90,
                pen=pg.mkPen(color=color, style=style, width=width),
                label=f'mode: {peak_real:.3g}',
                labelOpts={'color': color, 'movable': False, 'position': 0.68,
                           'anchors': [(0, 1), (0, 1)]},
            ))
        except Exception as e:
            print(f'[mode marker] {e}')


def _add_det_limit_v(plot_item, cfg: dict):
    """Vertical detection limit line (for histogram / molar ratio plots).
    Args:
        plot_item (Any): The plot item.
        cfg (dict): The cfg.
    """
    if not cfg.get('show_det_limit', False):
        return
    val = float(cfg.get('det_limit_value', 1.0))
    log_x = cfg.get('log_x', False)
    pos = float(np.log10(max(val, 1e-12))) if log_x else val
    color = cfg.get('det_limit_color', '#DC2626')
    style = _QT_LINE.get(cfg.get('det_limit_style', 'dash'), _Qt.DashLine)
    width = int(cfg.get('det_limit_width', 2))
    label = cfg.get('det_limit_label', '').strip() or f'DL: {val:g}'
    plot_item.addItem(pg.InfiniteLine(
        pos=pos, angle=90,
        pen=pg.mkPen(color=color, style=style, width=width),
        label=label,
        labelOpts={'color': color, 'movable': False, 'position': 0.45,
                   'anchors': [(0, 1), (0, 1)]},
    ))


def _add_det_limit_h(plot_item, cfg: dict):
    """Horizontal detection limit line (for box plot / scatter plots).
    Args:
        plot_item (Any): The plot item.
        cfg (dict): The cfg.
    """
    if not cfg.get('show_det_limit', False):
        return
    val = float(cfg.get('det_limit_value', 1.0))
    color = cfg.get('det_limit_color', '#DC2626')
    style = _QT_LINE.get(cfg.get('det_limit_style', 'dash'), _Qt.DashLine)
    width = int(cfg.get('det_limit_width', 2))
    label = cfg.get('det_limit_label', '').strip() or f'DL: {val:g}'
    plot_item.addItem(pg.InfiniteLine(
        pos=val, angle=0,
        pen=pg.mkPen(color=color, style=style, width=width),
        label=label,
        labelOpts={'color': color, 'movable': False, 'position': 0.98,
                   'anchors': [(1, 1), (1, 1)]},
    ))


def _add_ref_line_vertical(plot_item, cfg: dict,
                           num_label: str = 'X', den_label: str = 'Y'):
    """Customisable vertical reference line (e.g. ratio = 1).

    Reads: show_ref_line, ref_line_value, ref_line_label,
           ref_line_color, ref_line_style, ref_line_width, log_x.
    Args:
        plot_item (Any): The plot item.
        cfg (dict): The cfg.
        num_label (str): The num label.
        den_label (str): The den label.
    """
    if not cfg.get('show_ref_line', False):
        return
    val = float(cfg.get('ref_line_value', 1.0))
    if val <= 0:
        return
    log_x = cfg.get('log_x', True)
    pos = float(np.log10(val)) if log_x else val
    color = cfg.get('ref_line_color', '#A32D2D')
    style = _QT_LINE.get(cfg.get('ref_line_style', 'dash'), _Qt.DashLine)
    width = int(cfg.get('ref_line_width', 2))
    custom_lbl = cfg.get('ref_line_label', '').strip()
    label = custom_lbl if custom_lbl else f'{num_label}:{den_label} = {val:g}'
    line = pg.InfiniteLine(
        pos=pos, angle=90,
        pen=pg.mkPen(color=color, style=style, width=width),
        label=label,
        labelOpts={'color': color, 'movable': False, 'position': 0.55,
                   'anchors': [(0, 1), (0, 1)]},
    )
    line.setZValue(5)
    plot_item.addItem(line)


def build_quick_toggles_menu(parent_menu, cfg: dict,
                              display_toggles: list,
                              stat_toggles: list | None = None,
                              shade_types: list | None = None):
    """Build the uniform Quick Toggles submenu.

    Args:
        parent_menu:     The QMenu to add the Quick Toggles submenu to.
        cfg:             Current node config dict.
        display_toggles: list of (cfg_key, label, default) for top section.
        stat_toggles:    list of (cfg_key, label) for stat lines section.
        shade_types:     list of shade type strings; if given, adds shade submenu.

    Returns:
        The QMenu for Quick Toggles (so caller can connect signals).
    """
    from PySide6.QtWidgets import QMenu as _QMenu
    tm = parent_menu.addMenu('Quick Toggles')

    def _add(menu, label, key, default=False):
        """
        Args:
            menu (Any): QMenu object.
            label (Any): Label text.
            key (Any): Dictionary or storage key.
            default (Any): The default.
        Returns:
            object: Result of the operation.
        """
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(cfg.get(key, default))
        return a

    for key, label, *rest in display_toggles:
        default = rest[0] if rest else False
        _add(tm, label, key, default)

    if stat_toggles:
        tm.addSeparator()
        sep = tm.addAction('-- Stat Lines --')
        sep.setEnabled(False)
        for key, label in stat_toggles:
            _add(tm, label, key)

    if shade_types:
        tm.addSeparator()
        sep2 = tm.addAction('-- Shaded Region --')
        sep2.setEnabled(False)
        shm = tm.addMenu('Shade Type')
        for st in shade_types:
            a = shm.addAction(st)
            a.setCheckable(True)
            a.setChecked(cfg.get('shade_type', 'None') == st)

    return tm