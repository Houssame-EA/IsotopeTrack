from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QSlider,
    QDialogButtonBox, QMessageBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QFont
import pyqtgraph as pg
import numpy as np
import math
from scipy import stats
from scipy.stats import gaussian_kde

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, apply_font_to_pyqtgraph, set_axis_labels,
    FontSettingsGroup,
    get_sample_color, get_display_name,
    download_pyqtgraph_figure,
    format_element_label, LABEL_MODES, Renderer, HtmlAxisItem,
    SHADE_TYPES, _QT_LINE, _apply_box,
    _add_shaded_region_hist, _add_stat_lines_hist, _add_det_limit_v, _add_det_limit_h,
)
try:
    from widget.custom_plot_widget import (
        PlotSettingsDialog as _PlotSettingsDialog,
        get_system_font_families as _get_system_font_families,
    )
    _CUSTOM_PLOT_AVAILABLE = True
except Exception:
    _PlotSettingsDialog = None
    _get_system_font_families = lambda: FONT_FAMILIES[:]
    _CUSTOM_PLOT_AVAILABLE = False
from results.utils_sort import (
    sort_elements_by_mass, sort_element_dict_by_mass, element_alphabetical_key,
)


HIST_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Diameter (nm)', 'Particle Diameter (nm)',
]

SUMMABLE_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
]

HIST_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

HIST_LABEL_MAP = {
    'Counts': 'Intensity (counts)',
    'Element Mass (fg)': 'Element Mass (fg)',
    'Particle Mass (fg)': 'Particle Mass (fg)',
    'Element Moles (fmol)': 'Element Moles (fmol)',
    'Particle Moles (fmol)': 'Particle Moles (fmol)',
    'Element Diameter (nm)': 'Element Diameter (nm)',
    'Particle Diameter (nm)': 'Particle Diameter (nm)',
}

HIST_DISPLAY_MODES = [
    'Overlaid (Different Colors)',
    'Side by Side Subplots',
    'Individual Subplots',
]

BAR_DISPLAY_MODES = [
    'Grouped Bars (Side by Side)',
    'By Sample (Element Colors)',
    'Individual Subplots',
    'Side by Side Subplots',
    'Stacked Bars',
]

SORT_OPTIONS = [
    'No Sorting',
    'Ascending',
    'Descending',
    'Alphabetical',
]

CURVE_TYPES = [ 'Log-Normal Fit', 'Normal Fit']

DEFAULT_ELEMENT_COLORS = [
    '#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E',
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
]


def _normalize_hist_display_mode(mode: str) -> str:
    """Normalize legacy histogram display-mode aliases to active modes.

    Args:
        mode (str): Display mode from config or UI.

    Returns:
        str: Supported histogram display mode.

    Preserved behavior:
        Existing configs that stored ``Combined with Legend`` are supported by
        aliasing that value to ``Overlaid (Different Colors)``.
    """
    if mode == 'Combined with Legend':
        return 'Overlaid (Different Colors)'
    if mode in HIST_DISPLAY_MODES:
        return mode
    return HIST_DISPLAY_MODES[0]


def _fmt_elem(elem: str, cfg: dict) -> str:
    """Format an element key using the configured label_mode.

    'Symbol'        → strip leading mass number  (e.g. '107Ag' → 'Ag')
    'Mass + Symbol' → keep as-is                 (e.g. '107Ag')
    Args:
        elem (str): The elem.
        cfg (dict): The cfg.
    Returns:
        str: Result of the operation.
    """
    return format_element_label(elem, cfg.get('label_mode', 'Symbol'), Renderer.HTML)


class _PlotWidgetAdapter:
    """Wraps a (GraphicsLayoutWidget, PlotItem) pair so that all editor
    dialogs from custom_plot_widget.py treat it like a pg.PlotWidget.

    ``custom_axis_labels`` and ``persistent_dialog_settings`` are stored
    directly on the PlotItem (prefixed with '_') so they survive across
    multiple double-click events even though the adapter is re-created
    each time.
    """

    def __init__(self, glw, plot_item):
        """
        Args:
            glw (Any): The glw.
            plot_item (Any): The plot item.
        """
        self._glw = glw
        self._pi = plot_item
        self.legend = getattr(plot_item, 'legend', None)

    # ── State that must survive re-creation ──────────────────────────

    @property
    def custom_axis_labels(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not hasattr(self._pi, '_custom_axis_labels'):
            self._pi._custom_axis_labels = {}
        return self._pi._custom_axis_labels

    @custom_axis_labels.setter
    def custom_axis_labels(self, val):
        """
        Args:
            val (Any): The val.
        """
        self._pi._custom_axis_labels = val

    @property
    def persistent_dialog_settings(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not hasattr(self._pi, '_persistent_dialog_settings'):
            self._pi._persistent_dialog_settings = {}
        return self._pi._persistent_dialog_settings

    @persistent_dialog_settings.setter
    def persistent_dialog_settings(self, val):
        """
        Args:
            val (Any): The val.
        """
        self._pi._persistent_dialog_settings = val

    # ── PlotWidget interface ─────────────────────────────────────────

    def getPlotItem(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._pi

    def backgroundBrush(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._glw.backgroundBrush()

    def setBackground(self, color):
        """
        Args:
            color (Any): Colour value.
        """
        try:
            self._glw.setBackground(color)
        except Exception:
            pass

    def repaint(self):
        try:
            self._glw.repaint()
        except Exception:
            pass

    def parent(self):
        """
        Returns:
            object: Result of the operation.
        """
        try:
            return self._glw.parent()
        except Exception:
            return None


class EnhancedGraphicsLayoutWidget(pg.GraphicsLayoutWidget):
    """GraphicsLayoutWidget with double-click inline editing.

    Double-clicking on any subplot opens the same editor dialogs that
    EnhancedPlotWidget uses in the main signal window:
      • Title label      → TitleEditorDialog
      • Left axis        → AxisLabelEditorDialog('left')
      • Bottom axis      → AxisLabelEditorDialog('bottom')
      • Legend           → LegendEditorDialog
      • Background area  → BackgroundEditorDialog

    Works correctly across all multi-subplot display modes.
    """

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent=parent)

    # ── Helpers ──────────────────────────────────────────────────────

    def _plot_item_at(self, scene_pos):
        """Return the PlotItem whose bounding rect contains scene_pos.
        Args:
            scene_pos (Any): The scene pos.
        Returns:
            None
        """
        for item in self.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    rect = item.mapRectToScene(item.boundingRect())
                    if rect.contains(scene_pos):
                        return item
                except Exception:
                    pass
        return None

    def _adapter_for(self, plot_item):
        """Build an adapter for plot_item, syncing legend from it.
        Args:
            plot_item (Any): The plot item.
        Returns:
            object: Result of the operation.
        """
        adapter = _PlotWidgetAdapter(self, plot_item)
        adapter.legend = getattr(plot_item, 'legend', None)
        return adapter

    def _closest_scatter(self, pi, scene_pos, threshold_px=20):
        """
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            mx, my = dp.x(), dp.y()
            vr = vb.viewRange()
            xr = vr[0][1] - vr[0][0]
            yr = vr[1][1] - vr[1][0]
            if xr == 0 or yr == 0:
                return None
            best, best_d = None, float('inf')
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
                    try:
                        xd = pts['x']; yd = pts['y']
                    except Exception:
                        continue
                dx = (xd - mx) / xr; dy = (yd - my) / yr
                dists = np.sqrt(dx**2 + dy**2)
                md = dists[np.argmin(dists)]
                if md * self.width() < threshold_px and md < best_d:
                    best_d = md; best = item
            return best
        except Exception:
            return None

    def _closest_curve(self, pi, scene_pos, threshold_px=15):
        """
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            mx, my = dp.x(), dp.y()
            vr = vb.viewRange()
            xr = vr[0][1] - vr[0][0]
            yr = vr[1][1] - vr[1][0]
            if xr == 0 or yr == 0:
                return None
            best, best_d = None, float('inf')
            for item in pi.listDataItems():
                if isinstance(item, pg.ScatterPlotItem):
                    continue
                if not isinstance(item, (pg.PlotCurveItem, pg.PlotDataItem)):
                    continue
                xd = item.getData()[0] if isinstance(item, pg.PlotDataItem) \
                    else item.xData
                yd = item.getData()[1] if isinstance(item, pg.PlotDataItem) \
                    else item.yData
                if xd is None or yd is None or len(xd) == 0:
                    continue
                dx = (xd - mx) / xr; dy = (yd - my) / yr
                dists = np.sqrt(dx**2 + dy**2)
                md = dists[np.argmin(dists)]
                if md * self.width() < threshold_px and md < best_d:
                    best_d = md; best = item
            return best
        except Exception:
            return None

    def _bar_at(self, pi, scene_pos):
        """Return the BarGraphItem the cursor is inside (data-space test).
        Skips legend swatches (width == 0).
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
        Returns:
            None
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            cx, cy = dp.x(), dp.y()
            for item in pi.items:
                if not isinstance(item, pg.BarGraphItem):
                    continue
                w = item.opts.get('width', 0)
                if (not hasattr(w, '__len__') and w == 0):
                    continue
                x_arr = item.opts.get('x', [])
                h_arr = item.opts.get('height', [])
                if not hasattr(x_arr, '__len__'):
                    x_arr = [x_arr]
                if not hasattr(h_arr, '__len__'):
                    h_arr = [h_arr]
                half_w = (w / 2) if not hasattr(w, '__len__') else \
                         (w[0] / 2 if len(w) else 0.35)
                for xi, hi in zip(x_arr, h_arr):
                    y_lo, y_hi = min(0.0, float(hi)), max(0.0, float(hi))
                    if (float(xi) - half_w <= cx <= float(xi) + half_w
                            and y_lo <= cy <= y_hi):
                        return item
        except Exception:
            pass
        return None

    # ── Double-click ─────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if not _CUSTOM_PLOT_AVAILABLE:
            super().mouseDoubleClickEvent(event)
            return
        try:
            from widget.custom_plot_widget import (
                TitleEditorDialog, AxisLabelEditorDialog,
                LegendEditorDialog, BackgroundEditorDialog,
                ScatterEditorDialog, TraceEditorDialog,
            )

            pos = (event.position() if hasattr(event, 'position')
                   else event.pos())
            scene_pos = self.mapToScene(pos.toPoint())

            pi = self._plot_item_at(scene_pos)
            if pi is None:
                event.accept()
                return

            adapter = self._adapter_for(pi)
            dlg_parent = self.parent()

            tl = pi.titleLabel
            if tl and tl.isVisible():
                if tl.mapRectToScene(
                        tl.boundingRect()).contains(scene_pos):
                    TitleEditorDialog(adapter, dlg_parent).exec()
                    event.accept(); return

            la = pi.getAxis('left')
            if la.mapRectToScene(
                    la.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(
                    adapter, 'left', dlg_parent).exec()
                event.accept(); return

            ba = pi.getAxis('bottom')
            if ba.mapRectToScene(
                    ba.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(
                    adapter, 'bottom', dlg_parent).exec()
                event.accept(); return

            legend = getattr(pi, 'legend', None)
            if legend and legend.isVisible():
                try:
                    if legend.mapRectToScene(
                            legend.boundingRect()).contains(scene_pos):
                        adapter.legend = legend
                        LegendEditorDialog(adapter, dlg_parent).exec()
                        event.accept(); return
                except Exception:
                    pass

            scat = self._closest_scatter(pi, scene_pos)
            if scat is not None:
                ScatterEditorDialog(scat, adapter, dlg_parent).exec()
                event.accept(); return

            curve = self._closest_curve(pi, scene_pos)
            if curve is not None:
                TraceEditorDialog(curve, adapter, dlg_parent).exec()
                event.accept(); return

            bar_item = self._bar_at(pi, scene_pos)
            if bar_item is not None:
                from PySide6.QtWidgets import QColorDialog
                try:
                    cur = pg.mkBrush(
                        bar_item.opts.get('brush', 'b')).color()
                except Exception:
                    cur = QColor(100, 120, 220)
                new_c = QColorDialog.getColor(cur, self, "Bar Color")
                if new_c.isValid():
                    alpha = new_c.alpha() if new_c.alpha() < 255 else 215
                    bar_item.setOpts(
                        brush=pg.mkBrush(
                            new_c.red(), new_c.green(),
                            new_c.blue(), alpha),
                        pen=pg.mkPen('w', width=0.5))
                event.accept(); return

            BackgroundEditorDialog(adapter, dlg_parent).exec()
            event.accept()

        except Exception as e:
            print(f"EnhancedGraphicsLayoutWidget double-click error: {e}")
            import traceback; traceback.print_exc()
            super().mouseDoubleClickEvent(event)


def _get_element_color(element, index, cfg):
    """Get color for an element from config or defaults.
    Args:
        element (Any): The element.
        index (Any): Row or item index.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    colors = cfg.get('element_colors', {})
    if element in colors:
        return colors[element]
    return DEFAULT_ELEMENT_COLORS[index % len(DEFAULT_ELEMENT_COLORS)]


def _get_element_display_name(element, cfg):
    """Get display name for an element (renamed or original).
    Args:
        element (Any): The element.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    mappings = cfg.get('element_name_mappings', {})
    return mappings.get(element, element)


def _get_xy_labels(cfg):
    """Build x/y label strings.
    Args:
        cfg (Any): The cfg.
    Returns:
        tuple: Result of the operation.
    """
    dt = cfg.get('data_type_display', 'Counts')
    x_base = HIST_LABEL_MAP.get(dt, 'Value')
    y_base = 'Number of Particles'
    return x_base, y_base


def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _sample_names(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        list: Result of the operation.
    """
    if input_data and input_data.get('type') == 'multiple_sample_data':
        return input_data.get('sample_names', [])
    return []


def _can_sum(cfg):
    """Check if current data type supports per-particle summation.
    Args:
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    return cfg.get('data_type_display', 'Counts') in SUMMABLE_DATA_TYPES


def _apply_element_groups(particles, dk, groups):
    """Apply element groups to particle data by summing per particle.

    Args:
        particles: list of particle dicts
        dk: data key (e.g. 'elements', 'element_mass_fg', ...)
        groups: list of group dicts

    Returns:
        dict {display_label: [values]}  where grouped elements are summed
        per particle, ungrouped elements kept as-is.
    """
    if not particles:
        return {}

    elem_to_group = {}
    for grp in groups:
        for el in grp.get('elements', []):
            elem_to_group[el] = grp['name']

    out = {}
    for p in particles:
        d = p.get(dk, {})
        if not d:
            continue

        group_sums = {}
        for el, val in d.items():
            if val <= 0:
                continue
            if dk != 'elements' and np.isnan(val):
                continue

            grp_name = elem_to_group.get(el)
            if grp_name:
                group_sums[grp_name] = group_sums.get(grp_name, 0.0) + val
            else:
                out.setdefault(el, []).append(val)

        for grp_name, total in group_sums.items():
            if total > 0:
                out.setdefault(grp_name, []).append(total)

    return out


def _apply_element_groups_multi(particles, sample_names, dk, groups):
    """Apply element groups to multi-sample particle data.

    Returns:
        dict {sample_name: {display_label: [values]}}
    Args:
        particles (Any): The particles.
        sample_names (Any): The sample names.
        dk (Any): The dk.
        groups (Any): The groups.
    """
    if not particles:
        return {}

    elem_to_group = {}
    for grp in groups:
        for el in grp.get('elements', []):
            elem_to_group[el] = grp['name']

    result = {sn: {} for sn in sample_names}

    for p in particles:
        src = p.get('source_sample')
        if src not in result:
            continue
        d = p.get(dk, {})
        if not d:
            continue

        group_sums = {}
        for el, val in d.items():
            if val <= 0:
                continue
            if dk != 'elements' and np.isnan(val):
                continue

            grp_name = elem_to_group.get(el)
            if grp_name:
                group_sums[grp_name] = group_sums.get(grp_name, 0.0) + val
            else:
                result[src].setdefault(el, []).append(val)

        for grp_name, total in group_sums.items():
            if total > 0:
                result[src].setdefault(grp_name, []).append(total)

    return {k: v for k, v in result.items() if v}


class ElementGroupEditor(QGroupBox):
    """Widget for defining element groups (sum per particle)."""

    def __init__(self, groups, available_elements, parent=None):
        """
        Args:
            groups (Any): The groups.
            available_elements (Any): The available elements.
            parent (Any): Parent widget or object.
        """
        super().__init__("Element Groups (Sum per Particle)", parent)
        self._groups = [dict(g) for g in groups]
        self._available = available_elements or []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Group elements to SUM their values within each particle.\n"
            "e.g. group Fe + Si + Ti → each particle's Fe+Si+Ti mass "
            "is summed into one value.\n"
            "Only applies to Counts, Mass, Moles (not Diameter).")
        info.setStyleSheet("color: #6B7280; font-size: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._group_list = QListWidget()
        self._group_list.setMaximumHeight(120)
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        layout.addWidget(self._group_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Add Group")
        self._add_btn.clicked.connect(self._add_group)
        btn_row.addWidget(self._add_btn)
        self._remove_btn = QPushButton("− Remove")
        self._remove_btn.clicked.connect(self._remove_group)
        self._remove_btn.setEnabled(False)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._detail_frame = QFrame()
        self._detail_frame.setFrameShape(QFrame.StyledPanel)
        dl = QVBoxLayout(self._detail_frame)
        dl.setContentsMargins(6, 6, 6, 6)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Group Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. HgSe, Total Metal, ...")
        self._name_edit.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self._name_edit)
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(30, 22)
        self._color_btn.clicked.connect(self._pick_color)
        name_row.addWidget(self._color_btn)
        dl.addLayout(name_row)

        dl.addWidget(QLabel("Select elements to include in this group:"))
        self._elem_list = QListWidget()
        self._elem_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._elem_list.setMaximumHeight(150)
        self._elem_list.itemSelectionChanged.connect(
            self._on_elements_changed)
        dl.addWidget(self._elem_list)

        layout.addWidget(self._detail_frame)
        self._detail_frame.setVisible(False)

        self._refresh_group_list()

    def _refresh_group_list(self):
        self._group_list.clear()
        for g in self._groups:
            name = g.get('name', 'Unnamed')
            elems = ', '.join(g.get('elements', []))
            self._group_list.addItem(f"{name}  [{elems}]")

    def _on_group_selected(self, row):
        """
        Args:
            row (Any): Row index.
        """
        has = 0 <= row < len(self._groups)
        self._remove_btn.setEnabled(has)
        self._detail_frame.setVisible(has)
        if has:
            g = self._groups[row]
            self._name_edit.blockSignals(True)
            self._name_edit.setText(g.get('name', ''))
            self._name_edit.blockSignals(False)

            c = g.get('color',
                       DEFAULT_ELEMENT_COLORS[
                           row % len(DEFAULT_ELEMENT_COLORS)])
            self._color_btn.setStyleSheet(
                f"background-color: {c}; border: 1px solid black;")

            self._elem_list.blockSignals(True)
            self._elem_list.clear()
            selected_elems = set(g.get('elements', []))

            used_elsewhere = set()
            for i, og in enumerate(self._groups):
                if i != row:
                    used_elsewhere.update(og.get('elements', []))

            for el in self._available:
                item = QListWidgetItem(el)
                if el in used_elsewhere:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setToolTip(f"{el} already in another group")
                self._elem_list.addItem(item)
                if el in selected_elems:
                    item.setSelected(True)
            self._elem_list.blockSignals(False)

    def _add_group(self):
        idx = len(self._groups)
        self._groups.append({
            'name': f'Group {idx + 1}',
            'elements': [],
            'color': DEFAULT_ELEMENT_COLORS[
                idx % len(DEFAULT_ELEMENT_COLORS)],
        })
        self._refresh_group_list()
        self._group_list.setCurrentRow(len(self._groups) - 1)

    def _remove_group(self):
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            self._groups.pop(row)
            self._refresh_group_list()
            if self._groups:
                self._group_list.setCurrentRow(
                    min(row, len(self._groups) - 1))

    def _on_name_changed(self, text):
        """
        Args:
            text (Any): Text string.
        """
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            self._groups[row]['name'] = text.strip() or f'Group {row + 1}'
            self._refresh_group_list()
            self._group_list.setCurrentRow(row)

    def _on_elements_changed(self):
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            selected = []
            for i in range(self._elem_list.count()):
                item = self._elem_list.item(i)
                if item.isSelected() and (item.flags() & Qt.ItemIsEnabled):
                    selected.append(item.text())
            self._groups[row]['elements'] = selected
            self._refresh_group_list()
            self._group_list.setCurrentRow(row)

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            cur = QColor(self._groups[row].get('color', '#663399'))
            c = QColorDialog.getColor(cur, self, "Group Color")
            if c.isValid():
                self._groups[row]['color'] = c.name()
                self._color_btn.setStyleSheet(
                    f"background-color: {c.name()}; "
                    f"border: 1px solid black;")

    def collect(self):
        """Return list of valid groups (with ≥1 element and a name).
        Returns:
            list: Result of the operation.
        """
        return [g for g in self._groups
                if g.get('elements') and g.get('name')]


class HistogramSettingsDialog(QDialog):
    """Full settings dialog for histogram node."""

    def __init__(self, config, is_multi, sample_names, parent=None,
                 available_elements=None):
        """
        Args:
            config (Any): Configuration dictionary.
            is_multi (Any): The is multi.
            sample_names (Any): The sample names.
            parent (Any): Parent widget or object.
            available_elements (Any): The available elements.
        """
        super().__init__(parent)
        self.setWindowTitle("Histogram Settings")
        self.setMinimumWidth(520)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._available_elements = available_elements or []
        self._build_ui()

    def _build_ui(self):
        """
        Returns:
            tuple: Result of the operation.
        """
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if self._multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(HIST_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                _normalize_hist_display_mode(
                    self._cfg.get('display_mode', HIST_DISPLAY_MODES[0])))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(HIST_DATA_TYPES)
        self.data_type.setCurrentText(
            self._cfg.get('data_type_display', 'Counts'))
        fl.addRow("Data:", self.data_type)
        layout.addWidget(g)

        self._group_editor = ElementGroupEditor(
            self._cfg.get('element_groups', []),
            self._available_elements)
        layout.addWidget(self._group_editor)

        g = QGroupBox("Element Display Names")
        el_vl = QVBoxLayout(g)
        el_vl.addWidget(QLabel(
            "Rename individual elements in legend and stats:"))
        self._elem_name_edits = {}

        existing_names = self._cfg.get('element_name_mappings', {})
        all_elements = list(self._available_elements)

        for el in all_elements:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(el)
            lbl.setFixedWidth(80)
            row.addWidget(lbl)
            ne = QLineEdit(existing_names.get(el, el))
            ne.setFixedWidth(180)
            ne.setPlaceholderText(el)
            row.addWidget(ne)
            self._elem_name_edits[el] = ne
            rst = QPushButton("\u21ba")
            rst.setFixedSize(22, 22)
            rst.setToolTip(f"Reset to: {el}")
            rst.clicked.connect(
                lambda _, e=el: self._elem_name_edits[e].setText(e))
            row.addWidget(rst)
            row.addStretch()
            w_row = QWidget()
            w_row.setLayout(row)
            el_vl.addWidget(w_row)

        if not all_elements:
            el_vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        g = QGroupBox("Curve && Median")
        fl = QFormLayout(g)
        self.show_curve = QCheckBox()
        self.show_curve.setChecked(self._cfg.get('show_curve', True))
        fl.addRow("Show Density Curve:", self.show_curve)
        self.curve_type = QComboBox()
        self.curve_type.addItems(CURVE_TYPES)
        self.curve_type.setCurrentText(
            self._cfg.get('curve_type', 'Kernel Density'))
        fl.addRow("Curve Type:", self.curve_type)
        self.show_median = QCheckBox()
        self.show_median.setChecked(self._cfg.get('show_median', True))
        fl.addRow("Show Median Line (legacy):", self.show_median)
        self._curve_color = QColor(self._cfg.get('curve_color', '#2C3E50'))
        self.curve_color_btn = QPushButton()
        self.curve_color_btn.setFixedSize(60, 25)
        self.curve_color_btn.setStyleSheet(
            f"background-color: {self._curve_color.name()}; "
            f"border: 1px solid black;")
        self.curve_color_btn.clicked.connect(self._pick_curve_color)
        fl.addRow("Curve Color:", self.curve_color_btn)
        layout.addWidget(g)

        g = QGroupBox("Statistical Overlays")
        fl = QFormLayout(g)

        def _color_row(cfg_key, label, default_color):
            """Return (row_widget, color_holder, style_combo, width_spin).
            Args:
                cfg_key (Any): The cfg key.
                label (Any): Label text.
                default_color (Any): The default color.
            Returns:
                tuple: Result of the operation.
            """
            rw = QWidget(); rh = QHBoxLayout(rw); rh.setContentsMargins(0,0,0,0)
            holder = [self._cfg.get(cfg_key, default_color)]
            btn = QPushButton(); btn.setFixedSize(26, 22)
            btn.setStyleSheet(f"background:{holder[0]};")
            def _pick(h=holder, b=btn):
                """
                Args:
                    h (Any): The h.
                    b (Any): The b.
                """
                from PySide6.QtWidgets import QColorDialog as _CD
                c = _CD.getColor(QColor(h[0]), self)
                if c.isValid():
                    h[0] = c.name(); b.setStyleSheet(f"background:{h[0]};")
            btn.clicked.connect(_pick)
            rh.addWidget(btn); rh.addStretch()
            return rw, holder

        self.show_median_line = QCheckBox()
        self.show_median_line.setChecked(self._cfg.get('show_median_line', False))
        med_w, self._med_color = _color_row('median_line_color', 'med', '#0F6E56')
        med_row = QHBoxLayout()
        med_row.addWidget(self.show_median_line); med_row.addWidget(med_w)
        med_container = QWidget(); med_container.setLayout(med_row)
        fl.addRow("Median Line:", med_container)

        self.show_mean_line = QCheckBox()
        self.show_mean_line.setChecked(self._cfg.get('show_mean_line', False))
        mean_w, self._mean_color = _color_row('mean_line_color', 'mean', '#B45309')
        mean_row = QHBoxLayout()
        mean_row.addWidget(self.show_mean_line); mean_row.addWidget(mean_w)
        mean_container = QWidget(); mean_container.setLayout(mean_row)
        fl.addRow("Mean Line:", mean_container)

        self.show_mode_marker = QCheckBox()
        self.show_mode_marker.setChecked(self._cfg.get('show_mode_marker', False))
        mode_w, self._mode_color = _color_row('mode_line_color', 'mode', '#7C3AED')
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.show_mode_marker); mode_row.addWidget(mode_w)
        mode_container = QWidget(); mode_container.setLayout(mode_row)
        fl.addRow("Mode Marker:", mode_container)

        self.shade_combo = QComboBox()
        self.shade_combo.addItems(SHADE_TYPES)
        self.shade_combo.setCurrentText(self._cfg.get('shade_type', 'None'))
        fl.addRow("Shaded Region:", self.shade_combo)

        shade_row_w = QWidget(); shade_rh = QHBoxLayout(shade_row_w)
        shade_rh.setContentsMargins(0,0,0,0)
        self._shade_color_val = self._cfg.get('shade_color', '#534AB7')
        self._shade_clr_btn = QPushButton(); self._shade_clr_btn.setFixedSize(26, 22)
        self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color_val};")
        self._shade_clr_btn.clicked.connect(self._pick_shade_color_hist)
        self._shade_alpha_spin = QDoubleSpinBox()
        self._shade_alpha_spin.setRange(0.01, 1.0); self._shade_alpha_spin.setDecimals(2)
        self._shade_alpha_spin.setValue(self._cfg.get('shade_alpha', 0.18))
        shade_rh.addWidget(self._shade_clr_btn)
        shade_rh.addWidget(QLabel("alpha:")); shade_rh.addWidget(self._shade_alpha_spin)
        shade_rh.addStretch()
        fl.addRow("Shade Color / alpha:", shade_row_w)

        self.show_det_cb = QCheckBox()
        self.show_det_cb.setChecked(self._cfg.get('show_det_limit', False))
        fl.addRow("Detection Limit Line:", self.show_det_cb)
        self.det_val_spin = QDoubleSpinBox()
        self.det_val_spin.setRange(0.0, 999999999); self.det_val_spin.setDecimals(4)
        self.det_val_spin.setValue(self._cfg.get('det_limit_value', 1.0))
        fl.addRow("DL Value:", self.det_val_spin)
        self.det_label_edit = QLineEdit(self._cfg.get('det_limit_label', ''))
        self.det_label_edit.setPlaceholderText("Auto  (e.g.  DL: 1.0)")
        fl.addRow("DL Label:", self.det_label_edit)
        self.show_box_cb = QCheckBox()
        self.show_box_cb.setChecked(self._cfg.get('show_box', True))
        fl.addRow("Figure Box (frame):", self.show_box_cb)
        layout.addWidget(g)

        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
        self.bins = QSpinBox()
        self.bins.setRange(5, 200)
        self.bins.setValue(self._cfg.get('bins', 20))
        fl.addRow("Bins:", self.bins)
        self.alpha = QSlider(Qt.Horizontal)
        self.alpha.setRange(10, 100)
        self.alpha.setValue(int(self._cfg.get('alpha', 0.7) * 100))
        fl.addRow("Transparency:", self.alpha)
        self.log_x = QCheckBox()
        self.log_x.setChecked(self._cfg.get('log_x', False))
        fl.addRow("Log X-axis:", self.log_x)
        self.log_y = QCheckBox()
        self.log_y.setChecked(self._cfg.get('log_y', False))
        fl.addRow("Log Y-axis:", self.log_y)
        self.show_stats = QCheckBox()
        self.show_stats.setChecked(self._cfg.get('show_stats', True))
        fl.addRow("Show Statistics:", self.show_stats)
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Isotope Label:", self.label_mode)
        layout.addWidget(g)

        g = QGroupBox("Axis Limits")
        fl = QFormLayout(g)
        self.auto_x = QCheckBox("Auto X")
        self.auto_x.setChecked(self._cfg.get('auto_x', True))
        fl.addRow(self.auto_x)
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        self.x_min = QDoubleSpinBox()
        self.x_min.setRange(-999999, 999999)
        self.x_min.setValue(self._cfg.get('x_min', 0))
        self.x_max = QDoubleSpinBox()
        self.x_max.setRange(-999999, 999999)
        self.x_max.setValue(self._cfg.get('x_max', 1000))
        hl.addWidget(self.x_min)
        hl.addWidget(QLabel("to"))
        hl.addWidget(self.x_max)
        fl.addRow("X Range:", w)
        self.auto_y = QCheckBox("Auto Y")
        self.auto_y.setChecked(self._cfg.get('auto_y', True))
        fl.addRow(self.auto_y)
        w2 = QWidget()
        hl2 = QHBoxLayout(w2)
        hl2.setContentsMargins(0, 0, 0, 0)
        self.y_min = QDoubleSpinBox()
        self.y_min.setRange(0, 999999)
        self.y_min.setValue(self._cfg.get('y_min', 0))
        self.y_max = QDoubleSpinBox()
        self.y_max.setRange(0, 999999)
        self.y_max.setValue(self._cfg.get('y_max', 100))
        hl2.addWidget(self.y_min)
        hl2.addWidget(QLabel("to"))
        hl2.addWidget(self.y_max)
        fl.addRow("Y Range:", w2)
        layout.addWidget(g)

        if self._multi:
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("\u21ba")
                rst.setFixedSize(22, 22)
                rst.clicked.connect(
                    lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                w3 = QWidget()
                w3.setLayout(row)
                vl.addWidget(w3)
            layout.addWidget(g)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _pick_curve_color(self):
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._curve_color, self, "Curve Color")
        if c.isValid():
            self._curve_color = c
            self.curve_color_btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid black;")

    def _pick_shade_color_hist(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._shade_color_val), self)
        if c.isValid():
            self._shade_color_val = c.name()
            self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color_val};")

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        out = dict(self._cfg)
        out['data_type_display'] = self.data_type.currentText()
        out['element_groups'] = self._group_editor.collect()
        out['show_curve'] = self.show_curve.isChecked()
        out['curve_type'] = self.curve_type.currentText()
        out['show_median'] = self.show_median.isChecked()
        out['curve_color'] = self._curve_color.name()
        out['show_median_line'] = self.show_median_line.isChecked()
        out['median_line_color'] = self._med_color[0]
        out['show_mean_line'] = self.show_mean_line.isChecked()
        out['mean_line_color'] = self._mean_color[0]
        out['show_mode_marker'] = self.show_mode_marker.isChecked()
        out['mode_line_color'] = self._mode_color[0]
        out['shade_type'] = self.shade_combo.currentText()
        out['shade_color'] = self._shade_color_val
        out['shade_alpha'] = self._shade_alpha_spin.value()
        out['show_det_limit'] = self.show_det_cb.isChecked()
        out['det_limit_value'] = self.det_val_spin.value()
        out['det_limit_label'] = self.det_label_edit.text().strip()
        out['show_box'] = self.show_box_cb.isChecked()
        out['bins'] = self.bins.value()
        out['alpha'] = self.alpha.value() / 100.0
        out['log_x'] = self.log_x.isChecked()
        out['log_y'] = self.log_y.isChecked()
        out['show_stats'] = self.show_stats.isChecked()
        out['auto_x'] = self.auto_x.isChecked()
        out['x_min'] = self.x_min.value()
        out['x_max'] = self.x_max.value()
        out['auto_y'] = self.auto_y.isChecked()
        out['y_min'] = self.y_min.value()
        out['y_max'] = self.y_max.value()
        out['element_name_mappings'] = {
            e: ne.text().strip() or e
            for e, ne in self._elem_name_edits.items()}
        if self._multi:
            out['display_mode'] = _normalize_hist_display_mode(
                self.display_mode.currentText())
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        out['label_mode'] = self.label_mode.currentText()
        return out


class HistogramFormatSettingsDialog(QDialog):
    """Global visual-format settings dialog for Histogram plots.

    This dialog is intentionally config-driven and plot-global: it collects
    only presentation settings (fonts, labels, visual toggles, and element
    colors) and relies on Histogram redraw to apply those settings uniformly
    across all subplot PlotItems.
    """

    def __init__(self, config, is_multi, sample_names, parent=None,
                 available_elements=None):
        """
        Initialize the histogram format-only settings dialog.

        Args:
            config (dict): Current histogram config snapshot.
            is_multi (bool): Whether current histogram data is multi-sample.
            sample_names (list[str]): Source sample names for display-name edits.
            parent (QWidget | None): Parent dialog.
            available_elements (list[str] | None): Element keys available for
                global element-color and display-name edits.

        Preserved behavior:
            Scientific quantity controls (bins/data type/curve type/shade type/
            element groups/log axes/display mode) are intentionally excluded and
            remain in the quantities configuration workflow.
        """
        super().__init__(parent)
        self.setWindowTitle("Histogram plot format settings")
        self.setMinimumWidth(520)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._available_elements = available_elements or []
        self._font_color = QColor(self._cfg.get('font_color', '#000000'))
        self._elem_color_btns = {}
        self._build_ui()

    def _build_ui(self):
        """Build visual-only controls used by the histogram format route."""
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        g = QGroupBox("Font && Text")
        fl = QFormLayout(g)
        self.font_family = QComboBox()
        self.font_family.addItems(_get_system_font_families())
        self.font_family.setCurrentText(self._cfg.get('font_family', 'Times New Roman'))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(self._cfg.get('font_size', 18))
        self.font_bold = QCheckBox()
        self.font_bold.setChecked(self._cfg.get('font_bold', False))
        self.font_italic = QCheckBox()
        self.font_italic.setChecked(self._cfg.get('font_italic', False))
        self.font_color_btn = QPushButton()
        self.font_color_btn.setFixedSize(70, 24)
        self._refresh_font_color_btn()
        self.font_color_btn.clicked.connect(self._pick_font_color)
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Font Family:", self.font_family)
        fl.addRow("Font Size:", self.font_size)
        fl.addRow("Bold:", self.font_bold)
        fl.addRow("Italic:", self.font_italic)
        fl.addRow("Font Color:", self.font_color_btn)
        fl.addRow("Isotope Label:", self.label_mode)
        layout.addWidget(g)

        g = QGroupBox("Visual Toggles")
        fl = QFormLayout(g)
        self.show_curve = QCheckBox()
        self.show_curve.setChecked(self._cfg.get('show_curve', True))
        self.show_stats = QCheckBox()
        self.show_stats.setChecked(self._cfg.get('show_stats', True))
        self.show_box = QCheckBox()
        self.show_box.setChecked(self._cfg.get('show_box', True))
        self.show_median_line = QCheckBox()
        self.show_median_line.setChecked(self._cfg.get('show_median_line', False))
        self.show_mean_line = QCheckBox()
        self.show_mean_line.setChecked(self._cfg.get('show_mean_line', False))
        self.show_mode_marker = QCheckBox()
        self.show_mode_marker.setChecked(self._cfg.get('show_mode_marker', False))
        self.show_det_limit = QCheckBox()
        self.show_det_limit.setChecked(self._cfg.get('show_det_limit', False))
        fl.addRow("Show Density Curve:", self.show_curve)
        fl.addRow("Show Statistics:", self.show_stats)
        fl.addRow("Figure Box (frame):", self.show_box)
        fl.addRow("Median Line:", self.show_median_line)
        fl.addRow("Mean Line:", self.show_mean_line)
        fl.addRow("Mode Marker:", self.show_mode_marker)
        fl.addRow("Detection Limit Line:", self.show_det_limit)
        layout.addWidget(g)

        g = QGroupBox("Grid")
        fl = QFormLayout(g)
        self.show_x_grid = QCheckBox()
        self.show_x_grid.setChecked(self._cfg.get('show_x_grid', False))
        self.show_y_grid = QCheckBox()
        self.show_y_grid.setChecked(self._cfg.get('show_y_grid', False))
        self.grid_alpha = QDoubleSpinBox()
        self.grid_alpha.setRange(0.05, 1.0)
        self.grid_alpha.setDecimals(2)
        self.grid_alpha.setSingleStep(0.05)
        self.grid_alpha.setValue(float(self._cfg.get('grid_alpha', 0.2)))
        fl.addRow("Show X Grid:", self.show_x_grid)
        fl.addRow("Show Y Grid:", self.show_y_grid)
        fl.addRow("Grid Alpha:", self.grid_alpha)
        layout.addWidget(g)

        g = QGroupBox("Element Colors")
        vl = QVBoxLayout(g)
        existing_colors = self._cfg.get('element_colors', {})
        for i, el in enumerate(self._available_elements):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(el))
            btn = QPushButton()
            btn.setFixedSize(70, 24)
            col = existing_colors.get(
                el, DEFAULT_ELEMENT_COLORS[i % len(DEFAULT_ELEMENT_COLORS)])
            btn._color = QColor(col)
            btn.setStyleSheet(
                f"background-color: {btn._color.name()}; border: 1px solid black;")
            btn.clicked.connect(lambda _, e=el: self._pick_element_color(e))
            row.addWidget(btn)
            row.addStretch()
            vl.addLayout(row)
            self._elem_color_btns[el] = btn
        if not self._available_elements:
            vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        g = QGroupBox("Element Display Names")
        el_vl = QVBoxLayout(g)
        self._elem_name_edits = {}
        existing_names = self._cfg.get('element_name_mappings', {})
        for el in self._available_elements:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(el)
            lbl.setFixedWidth(90)
            row.addWidget(lbl)
            ne = QLineEdit(existing_names.get(el, el))
            ne.setFixedWidth(180)
            ne.setPlaceholderText(el)
            row.addWidget(ne)
            self._elem_name_edits[el] = ne
            rst = QPushButton("\u21ba")
            rst.setFixedSize(22, 22)
            rst.clicked.connect(lambda _, e=el: self._elem_name_edits[e].setText(e))
            row.addWidget(rst)
            row.addStretch()
            el_vl.addLayout(row)
        if not self._available_elements:
            el_vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        if self._multi:
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("\u21ba")
                rst.setFixedSize(22, 22)
                rst.clicked.connect(lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                vl.addLayout(row)
            layout.addWidget(g)
        else:
            self._name_edits = None

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _refresh_font_color_btn(self):
        """Refresh the font-color swatch preview."""
        self.font_color_btn.setStyleSheet(
            f"background-color: {self._font_color.name()}; border: 1px solid black;")

    def _pick_font_color(self):
        """Select and store a global histogram font color."""
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._font_color, self, "Font Color")
        if c.isValid():
            self._font_color = c
            self._refresh_font_color_btn()

    def _pick_element_color(self, element):
        """Select an element color used globally across histogram subplots."""
        from PySide6.QtWidgets import QColorDialog
        btn = self._elem_color_btns.get(element)
        if btn is None:
            return
        c = QColorDialog.getColor(btn._color, self, f"{element} Color")
        if c.isValid():
            btn._color = c
            btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid black;")

    def collect(self) -> dict:
        """Collect only histogram visual-format settings.

        Returns:
            dict: Format-only config updates that are safe to merge via
            ``node.config.update(...)`` without overwriting quantity settings.
        """
        out = {}
        out['font_family'] = self.font_family.currentText()
        out['font_size'] = self.font_size.value()
        out['font_bold'] = self.font_bold.isChecked()
        out['font_italic'] = self.font_italic.isChecked()
        out['font_color'] = self._font_color.name()
        out['label_mode'] = self.label_mode.currentText()
        out['show_curve'] = self.show_curve.isChecked()
        out['show_stats'] = self.show_stats.isChecked()
        out['show_box'] = self.show_box.isChecked()
        out['show_median_line'] = self.show_median_line.isChecked()
        out['show_mean_line'] = self.show_mean_line.isChecked()
        out['show_mode_marker'] = self.show_mode_marker.isChecked()
        out['show_det_limit'] = self.show_det_limit.isChecked()
        out['show_x_grid'] = self.show_x_grid.isChecked()
        out['show_y_grid'] = self.show_y_grid.isChecked()
        out['grid_alpha'] = self.grid_alpha.value()
        out['element_name_mappings'] = {
            e: ne.text().strip() or e
            for e, ne in self._elem_name_edits.items()
        }
        out['element_colors'] = {
            e: btn._color.name()
            for e, btn in self._elem_color_btns.items()
        }
        if self._multi and self._name_edits is not None:
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        return out


def _get_label_color(label, idx, cfg):
    """Get color for a label: check element_colors → group color → default.
    Args:
        label (Any): Label text.
        idx (Any): The idx.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    ec = cfg.get('element_colors', {})
    if label in ec:
        return ec[label]
    for i, g in enumerate(cfg.get('element_groups', [])):
        if g.get('name') == label:
            return g.get('color',
                         DEFAULT_ELEMENT_COLORS[
                             i % len(DEFAULT_ELEMENT_COLORS)])
    return DEFAULT_ELEMENT_COLORS[idx % len(DEFAULT_ELEMENT_COLORS)]


class HistogramDisplayDialog(QDialog):
    """Full-figure histogram dialog with PyQtGraph and right-click menu."""

    def __init__(self, histogram_node, parent_window=None):
        """
        Args:
            histogram_node (Any): The histogram node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = histogram_node
        self.parent_window = parent_window
        self.setWindowTitle("Particle Data Histogram Analysis")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        """
        Build histogram canvas, stats footer, and standardized bottom buttons.

        Preserved behavior:
            Plot calculations are unchanged; this only adds consistent UI entry
            points for formatting, quantity configuration, layout reset, and
            figure export.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.pw, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.stats_label)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.setToolTip("Reset plot ranges to automatic view.")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        layout.addLayout(bb)


    def _ctx_menu(self, pos):
        """
        Show lightweight histogram quick actions.

        Args:
            pos (Any): Position point.

        Preserved behavior:
            Keeps right-click focused on visual quick toggles and isotope label
            mode while full quantity/format/reset/export workflows are handled by
            bottom buttons.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_curve',  'Density Curve',       True),
            ('show_stats',  'Statistics',          True),
            ('show_box',    'Figure Box (frame)',   True),
        ]:
            a = tg.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        tg.addSeparator()
        sep1 = tg.addAction("-- Stat Lines --"); sep1.setEnabled(False)
        for key, label in [
            ('show_median_line',  'Median Line'),
            ('show_mean_line',    'Mean Line'),
            ('show_mode_marker',  'Mode Marker'),
            ('show_det_limit',    'Detection Limit'),
        ]:
            a = tg.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))
        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle_key(self, key):
        """
        Args:
            key (Any): Dictionary or storage key.
        """
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._refresh()

    def _get_available_elements(self):
        """Get raw element names from input (before grouping).
        Returns:
            object: Result of the operation.
        """
        try:
            data = self.node.input_data
            if not data:
                return []
            dt = self.node.config.get('data_type_display', 'Counts')
            dk = HIST_DATA_KEY_MAP.get(dt, 'elements')
            elems = set()
            for p in data.get('particle_data', []):
                elems.update(p.get(dk, {}).keys())
            return sorted(elems)
        except Exception:
            return []

    def _open_settings(self, title_override=None):
        """Open histogram quantity/configuration controls.

        Args:
            title_override (str | None): Optional explicit window title used by
                standardized bottom-button routes.

        Preserved behavior:
            Reuses the existing combined Histogram settings schema for this
            migration pass, keeping scientific quantity semantics unchanged.
        """
        dlg = HistogramSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self,
            available_elements=self._get_available_elements())
        if title_override:
            dlg.setWindowTitle(title_override)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open histogram format-only settings with global multi-subplot scope.

        Preserved behavior:
            Avoids single-PlotItem mutation paths so accepted changes are stored
            in canonical config and then redrawn consistently across all
            histogram subplots and legends.
        """
        dlg = HistogramFormatSettingsDialog(
            self.node.config,
            _is_multi(self.node.input_data),
            _sample_names(self.node.input_data),
            self,
            available_elements=self._get_available_elements(),
        )
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """
        Open histogram quantity/configuration controls.

        Preserved behavior:
            Keeps quantity/scientific options in the dedicated bottom-button
            route and applies the standardized title.
        """
        self._open_settings(
            title_override="Histogram plot quantities configuration")

    def _open_plot_settings(self, title_override=None, show_apply=True):
        """Compatibility wrapper for the legacy single-plot settings editor.

        Args:
            title_override (str | None): Optional window-title override.
            show_apply (bool): Whether live Apply is visible in the dialog.

        Preserved behavior:
            Left available for non-primary legacy entry points, but Histogram's
            standardized format workflow uses ``HistogramFormatSettingsDialog``
            so settings apply globally across multi-subplot layouts.
        """
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            dlg = _PlotSettingsDialog(
                _PlotWidgetAdapter(self.pw, pi), self, show_apply=show_apply)
            if title_override:
                try:
                    dlg.setWindowTitle(title_override)
                except Exception:
                    pass
            dlg.exec()

    def _download_figure(self):
        """Export histogram figure and CSV via existing PyQtGraph helper."""
        import pandas as pd
        csv_df = None
        try:
            plot_data = self.node.extract_plot_data()
            cfg = self.node.config
            dt = cfg.get('data_type_display', 'Counts')
            if plot_data:
                rows = []
                if _is_multi(self.node.input_data):
                    for sn, sd in plot_data.items():
                        dname = get_display_name(sn, cfg)
                        for elem, vals in sd.items():
                            disp = _get_element_display_name(elem, cfg)
                            for v in vals:
                                rows.append({
                                    'Sample': dname,
                                    'Element/Group': elem,
                                    'Display Name': disp,
                                    dt: v})
                else:
                    for elem, vals in plot_data.items():
                        disp = _get_element_display_name(elem, cfg)
                        for v in vals:
                            rows.append({
                                'Element/Group': elem,
                                'Display Name': disp,
                                dt: v})
                if rows:
                    csv_df = pd.DataFrame(rows)
        except Exception as e:
            print(f"Warning: could not build CSV data: {e}")

        download_pyqtgraph_figure(
            self.pw, self, default_name='histogram', csv_data=csv_df)

    def _export_figure(self):
        """Route standardized bottom export action to histogram export path."""
        self._download_figure()

    def _disable_native_pyqtgraph_context_menu(self):
        """
        Disable native PyQtGraph menus locally for Histogram.

        Preserved behavior:
            Prevents stacked native menus for this dialog only; global
            PyQtGraph behavior remains unchanged.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    pass
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    pass

    def _reset_layout(self):
        """
        Reset histogram layout/ranges without changing scientific settings.

        Preserved behavior:
            Data type, bins, curve/shade options, grouping, and log-axis
            semantics remain unchanged; only auto-range layout state is reset.
        """
        self.node.config['auto_x'] = True
        self.node.config['auto_y'] = True
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    pass
        self._refresh()


    def _refresh(self):
        """
        Rebuild and redraw the histogram canvas from current configuration.

        Preserved behavior:
            Scientific calculations and data extraction are unchanged. This
            method now normalizes legacy display-mode aliases and reapplies
            local native-menu suppression after redraw so the custom histogram
            context menu remains authoritative.
        """
        try:
            parent_layout = self.pw.parent().layout()
            idx = parent_layout.indexOf(self.pw)
            parent_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            parent_layout.insertWidget(idx, self.pw, stretch=1)

            plot_data = self.node.extract_plot_data()
            cfg = self.node.config

            if not plot_data:
                pi = self.pw.addPlot()
                t = pg.TextItem(
                    "No particle data available\n"
                    "Connect to Sample Selector\n"
                    "and run particle detection",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(t)
                t.setPos(0.5, 0.5)
                pi.hideAxis('left')
                pi.hideAxis('bottom')
                self.stats_label.setText("")
                return

            if _is_multi(self.node.input_data):
                mode = _normalize_hist_display_mode(
                    cfg.get('display_mode', HIST_DISPLAY_MODES[0]))
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                else:
                    self._draw_overlaid(plot_data, cfg)
            else:
                pi = self.pw.addPlot()
                _draw_single_histogram(pi, plot_data, cfg)
                if cfg.get('show_stats', True):
                    _add_stats_text(pi, plot_data, cfg)

            self._disable_native_pyqtgraph_context_menu()
            self._update_stats(plot_data)

        except Exception as e:
            print(f"Error updating histogram: {e}")
            import traceback
            traceback.print_exc()

    def _draw_subplots(self, plot_data, cfg):
        """
        Draw one subplot per sample using per-element color encoding.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        samples = list(plot_data.keys())
        cols = min(2, len(samples))
        for idx, sn in enumerate(samples):
            if idx > 0 and idx % cols == 0:
                self.pw.nextRow()
            pi = self.pw.addPlot(title=get_display_name(sn, cfg))
            sd = plot_data[sn]
            if sd:
                _draw_single_histogram(pi, sd, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Draw side-by-side sample subplots using per-element color encoding.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        first_pi = None
        xl, yl = _get_xy_labels(cfg)
        for idx, (sn, sd) in enumerate(plot_data.items()):
            pi = self.pw.addPlot(row=0, col=idx, title=get_display_name(sn, cfg))
            if sd:
                _draw_single_histogram(pi, sd, cfg)
            if first_pi is None:
                first_pi = pi
            else:
                pi.setYLink(first_pi)
                pi.getAxis('left').setLabel('')
                pi.getAxis('left').setStyle(showValues=False)
            if cfg.get('log_x', False):
                pi.getAxis('bottom').setLogMode(True)
            if cfg.get('log_y', False):
                pi.getAxis('left').setLogMode(True)
            if not cfg.get('auto_x', True):
                xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
                if cfg.get('log_x', False) and xn > 0 and xx > 0:
                    xn, xx = float(np.log10(xn)), float(np.log10(xx))
                pi.setXRange(xn, xx, padding=0)
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_overlaid(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        pi = self.pw.addPlot()
        dt = cfg.get('data_type_display', 'Counts')
        log_x = cfg.get('log_x', False)
        bins_n = cfg.get('bins', 20)

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        for idx, (sn, sd) in enumerate(plot_data.items()):
            if not sd:
                continue
            color = get_sample_color(sn, idx, cfg)
            dname = get_display_name(sn, cfg)
            combined = []
            for vals in sd.values():
                combined.extend(vals)
            v = _prepare_values(combined, dt, log_x)
            if v is None:
                continue
            _draw_histogram_bars(pi, v, cfg, color, bins_n)
            co = QColor(color)
            swatch = pg.BarGraphItem(
                x=[0], height=[0], width=0,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), 180))
            legend.addItem(swatch, dname)

        xl, yl = _get_xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        if cfg.get('log_x', False):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y', False):
            pi.getAxis('left').setLogMode(True)
        if not cfg.get('auto_x', True):
            xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
            if cfg.get('log_x', False) and xn > 0 and xx > 0:
                xn, xx = float(np.log10(xn)), float(np.log10(xx))
            pi.setXRange(xn, xx, padding=0)
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg.get('y_min', 0), cfg.get('y_max', 100), padding=0)
        _apply_histogram_grid(pi, cfg)
        apply_font_to_pyqtgraph(pi, cfg)

    def _draw_combined(self, plot_data, cfg):
        """
        Legacy wrapper for historical ``Combined with Legend`` mode values.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        self._draw_overlaid(plot_data, cfg)

    def _update_stats(self, plot_data):
        """
        Args:
            plot_data (Any): The plot data.
        """
        cfg = self.node.config
        groups = cfg.get('element_groups', [])
        group_info = ""
        if groups and _can_sum(cfg):
            names = [g['name'] for g in groups if g.get('name')]
            if names:
                group_info = f"  \u00b7  Groups: {', '.join(names)}"

        if _is_multi(self.node.input_data):
            total = sum(
                sum(len(v) for v in sd.values())
                for sd in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} samples  \u00b7  "
                f"{total:,} values{group_info}")
        else:
            total = sum(len(v) for v in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} elements/groups  \u00b7  "
                f"{total:,} values{group_info}")


class HistogramPlotNode(QObject):
    """Histogram visualization node with element grouping support.

    Element groups sum selected element values PER PARTICLE into a
    single combined value, then plot the histogram of those sums.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'data_type_display': 'Counts',
        'element_groups': [],
        'element_name_mappings': {},
        'show_curve': True,
        'curve_type': 'Kernel Density',
        'show_median': True,
        'show_median_line': False,
        'show_mean_line': False,
        'show_mode_marker': False,
        'median_line_color': '#0F6E56',
        'median_line_style': 'dash',
        'median_line_width': 2,
        'mean_line_color': '#B45309',
        'mean_line_style': 'solid',
        'mean_line_width': 2,
        'mode_line_color': '#7C3AED',
        'mode_line_style': 'dot',
        'mode_line_width': 2,
        'curve_color': '#2C3E50',
        'bins': 20,
        'alpha': 0.7,
        'log_x': False,
        'log_y': False,
        'show_stats': True,
        'shade_type': 'None',
        'shade_color': '#534AB7',
        'shade_alpha': 0.18,
        'show_det_limit': False,
        'det_limit_value': 1.0,
        'det_limit_color': '#DC2626',
        'det_limit_style': 'dash',
        'det_limit_width': 2,
        'det_limit_label': '',
        'show_box': True,
        'x_min': 0, 'x_max': 1000, 'auto_x': True,
        'y_min': 0, 'y_max': 100, 'auto_y': True,
        'element_colors': {},
        'display_mode': 'Overlaid (Different Colors)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode': 'Symbol',
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Histogram"
        self.node_type = "histogram_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

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
        dlg = HistogramDisplayDialog(self, parent_window)
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

    def extract_plot_data(self):
        """Extract plottable data, applying element groups when active.

        Groups SUM element values per particle. For example if a
        particle has Fe=10fg, Si=5fg, Ti=3fg and group "FeSiTi"
        includes [Fe, Si, Ti], that particle contributes 18fg to
        the "FeSiTi" histogram. Ungrouped elements stay separate.
        Returns:
            None
        """
        if not self.input_data:
            return None

        dt = self.config.get('data_type_display', 'Counts')
        dk = HIST_DATA_KEY_MAP.get(dt, 'elements')
        itype = self.input_data.get('type')

        groups = self.config.get('element_groups', [])
        use_groups = bool(groups) and _can_sum(self.config)

        if itype == 'sample_data':
            if use_groups:
                particles = self.input_data.get('particle_data', [])
                out = _apply_element_groups(particles, dk, groups)
                return out or None
            return self._extract_single(dk)

        elif itype == 'multiple_sample_data':
            if use_groups:
                particles = self.input_data.get('particle_data', [])
                names = self.input_data.get('sample_names', [])
                out = _apply_element_groups_multi(
                    particles, names, dk, groups)
                return out or None
            return self._extract_multi(dk)

        return None

    def _extract_single(self, dk):
        """
        Args:
            dk (Any): The dk.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        out = {}
        for p in particles:
            d = p.get(dk, {})
            for el, val in d.items():
                if dk == 'elements':
                    if val > 0:
                        out.setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        out.setdefault(el, []).append(val)
        return out or None

    def _extract_multi(self, dk):
        """
        Args:
            dk (Any): The dk.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles:
            return None
        result = {sn: {} for sn in names}
        for p in particles:
            src = p.get('source_sample')
            if src not in result:
                continue
            d = p.get(dk, {})
            for el, val in d.items():
                if dk == 'elements':
                    if val > 0:
                        result[src].setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        result[src].setdefault(el, []).append(val)
        return {k: v for k, v in result.items() if v} or None

class BarChartSettingsDialog(QDialog):
    """Scope-aware settings dialog for the element bar chart."""

    def __init__(self, config, is_multi, sample_names, parent=None, scope='all'):
        """
        Initialize bar-chart settings dialog with optional scope filtering.

        Args:
            config (dict): Current plot configuration.
            is_multi (bool): Whether data contains multiple samples.
            sample_names (list[str]): Source sample names used for display controls.
            parent (Any): Parent widget.
            scope (str): ``'format'``, ``'quantities'``, or ``'all'``.

        Preserved behavior:
            Existing config key semantics and rendering behavior are unchanged; this
            only controls which settings groups are shown by each bottom-button route.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Element bar chart plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Element bar chart plot quantities configuration")
        else:
            self.setWindowTitle("Element Bar Chart Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._scope = scope

        self.display_mode = None
        self.show_values = None
        self.sort_bars = None
        self.log_y = None
        self.label_mode = None
        self.min_count = None
        self._name_edits = None
        self._order_list = None

        self._build_ui()

    def _build_ui(self):
        """
        Build settings controls for the selected scope.

        Scope behavior:
            - ``format``: visual/presentation controls.
            - ``quantities``: scientific/view arrangement controls.
            - ``all``: legacy combined dialog.
        """
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if self._multi and self._scope in ('all', 'quantities'):
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(BAR_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                self._cfg.get('display_mode', BAR_DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'format'):
            g = QGroupBox("Plot Format")
            fl = QFormLayout(g)
            self.show_values = QCheckBox()
            self.show_values.setChecked(self._cfg.get('show_values', True))
            fl.addRow("Show Values on Bars:", self.show_values)
            self.label_mode = QComboBox()
            self.label_mode.addItems(LABEL_MODES)
            self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
            fl.addRow("Isotope Label:", self.label_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'quantities'):
            g = QGroupBox("Plot Quantities")
            fl = QFormLayout(g)
            self.sort_bars = QComboBox()
            self.sort_bars.addItems(SORT_OPTIONS)
            self.sort_bars.setCurrentText(self._cfg.get('sort_bars', 'No Sorting'))
            fl.addRow("Sort Bars:", self.sort_bars)
            self.log_y = QCheckBox()
            self.log_y.setChecked(self._cfg.get('log_y', False))
            fl.addRow("Log Y-axis:", self.log_y)
            self.min_count = QSpinBox()
            self.min_count.setRange(0, 100000)
            self.min_count.setValue(self._cfg.get('min_particle_count', 10))
            self.min_count.setSuffix(" particles")
            self.min_count.setToolTip(
                "Hide elements with fewer particles than this threshold.\n"
                "Set to 0 to show all elements.")
            fl.addRow("Min Particle Count:", self.min_count)
            layout.addWidget(g)

        if self._multi and self._scope in ('all', 'format'):
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("Reset")
                rst.setFixedWidth(50)
                rst.clicked.connect(lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                w = QWidget()
                w.setLayout(row)
                vl.addWidget(w)
            layout.addWidget(g)

        if self._multi and self._scope in ('all', 'quantities'):
            g2 = QGroupBox("Sample Display Order")
            vl2 = QVBoxLayout(g2)
            hint = QLabel("Drag or use Up/Down to set order; useful for time series.")
            hint.setStyleSheet("color: #6B7280; font-size: 10px;")
            hint.setWordWrap(True)
            vl2.addWidget(hint)
            from PySide6.QtWidgets import QAbstractItemView as _AIV
            self._order_list = QListWidget()
            self._order_list.setMaximumHeight(130)
            self._order_list.setDragDropMode(_AIV.InternalMove)
            cur_order = self._cfg.get('sample_order', [])
            ordered = [s for s in cur_order if s in self._samples]
            ordered += [s for s in self._samples if s not in ordered]
            for s in ordered:
                self._order_list.addItem(s)
            vl2.addWidget(self._order_list)
            btn_row = QHBoxLayout()
            up_btn = QPushButton("Up")
            up_btn.setFixedWidth(72)
            up_btn.clicked.connect(self._move_up)
            dn_btn = QPushButton("Down")
            dn_btn.setFixedWidth(72)
            dn_btn.clicked.connect(self._move_down)
            btn_row.addWidget(up_btn)
            btn_row.addWidget(dn_btn)
            btn_row.addStretch()
            vl2.addLayout(btn_row)
            layout.addWidget(g2)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _move_up(self):
        """Move selected sample-order row up in quantities scope."""
        if self._order_list is None:
            return
        row = self._order_list.currentRow()
        if row > 0:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row - 1, item)
            self._order_list.setCurrentRow(row - 1)

    def _move_down(self):
        """Move selected sample-order row down in quantities scope."""
        if self._order_list is None:
            return
        row = self._order_list.currentRow()
        if row < self._order_list.count() - 1:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row + 1, item)
            self._order_list.setCurrentRow(row + 1)

    def collect(self) -> dict:
        """
        Collect settings values only for controls present in the active scope.

        Returns:
            dict: Updated config dictionary to merge into node config.

        Preserved behavior:
            Prevents scope-related missing-widget errors and preserves untouched keys.
        """
        out = dict(self._cfg)
        if self.show_values is not None:
            out['show_values'] = self.show_values.isChecked()
        if self.sort_bars is not None:
            out['sort_bars'] = self.sort_bars.currentText()
        if self.log_y is not None:
            out['log_y'] = self.log_y.isChecked()
        if self.label_mode is not None:
            out['label_mode'] = self.label_mode.currentText()
        if self.min_count is not None:
            out['min_particle_count'] = self.min_count.value()
        if self._multi and self.display_mode is not None:
            out['display_mode'] = self.display_mode.currentText()
        if self._multi and self._name_edits is not None:
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        if self._multi and self._order_list is not None:
            out['sample_order'] = [
                self._order_list.item(i).text()
                for i in range(self._order_list.count())]
        return out

def _prepare_values(values, data_type, log_x):
    """Filter and optionally log-transform histogram values.
    Args:
        values (Any): Array or sequence of values.
        data_type (Any): The data type.
        log_x (Any): The log x.
    Returns:
        object: Result of the operation.
    """
    if not values:
        return None
    v = np.array(values, dtype=float)
    if data_type != 'Counts':
        v = v[(v > 0) & ~np.isnan(v)]
    if len(v) == 0:
        return None
    if log_x:
        v = v[v > 0]
        if len(v) == 0:
            return None
        v = np.log10(v)
    return v


def _draw_histogram_bars(plot_item, values, cfg, color_hex, bins_n=None,
                         name=''):
    """Draw histogram bars using PyQtGraph BarGraphItem.

    Returns: (processed_values, bin_edges, counts)
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
        color_hex (Any): The color hex.
        bins_n (Any): The bins n.
        name (Any): Name string.
    """
    if bins_n is None:
        bins_n = cfg.get('bins', 20)
    alpha = int(cfg.get('alpha', 0.7) * 255)
    log_y = cfg.get('log_y', False)

    counts, bin_edges = np.histogram(values, bins=bins_n)
    y_plot = np.log10(counts.astype(float) + 1) if log_y else counts.astype(float)

    centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bw = bin_edges[1] - bin_edges[0] if len(bin_edges) > 1 else 1.0

    co = QColor(color_hex)
    bar = pg.BarGraphItem(
        x=centres, height=y_plot, width=bw * 0.95,
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
        pen=pg.mkPen(color='w', width=0.5))
    if name:
        bar.opts['_trace_name'] = name
    plot_item.addItem(bar)

    return values, bin_edges, counts


def _apply_histogram_grid(plot_item, cfg):
    """Apply histogram grid visibility/alpha settings to a PlotItem.

    Args:
        plot_item: Target ``pg.PlotItem``.
        cfg (dict): Histogram config containing ``show_x_grid``,
            ``show_y_grid``, and ``grid_alpha``.

    Preserved behavior:
        Affects only plot presentation and does not alter histogram data or
        quantity semantics.
    """
    show_x = cfg.get('show_x_grid', False)
    show_y = cfg.get('show_y_grid', False)
    alpha = float(cfg.get('grid_alpha', 0.2))
    alpha = max(0.0, min(1.0, alpha))
    plot_item.showGrid(x=show_x, y=show_y, alpha=alpha)


def _add_density_curve(plot_item, values, cfg, bin_edges, total_count):
    """Add density curve overlay scaled to match count histogram.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
        bin_edges (Any): The bin edges.
        total_count (Any): The total count.
    """
    curve_type = cfg.get('curve_type', 'Kernel Density')
    curve_color = cfg.get('curve_color', '#2C3E50')
    log_y = cfg.get('log_y', False)

    try:
        bin_width = bin_edges[1] - bin_edges[0] if len(bin_edges) > 1 else 1.0
        x_min, x_max = values.min(), values.max()
        x_range = x_max - x_min
        if x_range <= 0:
            return
        x_curve = np.linspace(x_min - 0.1 * x_range, x_max + 0.1 * x_range, 300)

        if curve_type == 'Log-Normal Fit' and np.all(values > 0):
            shape, loc, scale = stats.lognorm.fit(values, floc=0)
            y_curve = stats.lognorm.pdf(x_curve, shape, loc, scale)
        elif curve_type == 'Normal Fit':
            mu, sigma = stats.norm.fit(values)
            y_curve = stats.norm.pdf(x_curve, mu, sigma)
        else:
            y_curve = gaussian_kde(values)(x_curve)

        y_scaled = y_curve * total_count * bin_width
        if log_y:
            y_scaled = np.log10(y_scaled + 1)

        plot_item.addItem(pg.PlotDataItem(
            x=x_curve, y=y_scaled,
            pen=pg.mkPen(color=curve_color, width=2.5)))
    except Exception as e:
        print(f"Density curve error: {e}")


def _add_median_line(plot_item, values, cfg):
    """Add median vertical line with annotation.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
    """
    fc = get_font_config(cfg)
    median = np.median(values)

    plot_item.addItem(pg.InfiniteLine(
        pos=median, angle=90,
        pen=pg.mkPen(color='#1F2937', style=pg.QtCore.Qt.DashLine, width=1.8)))

    txt = f"median: {median:.2f}"
    ti = pg.TextItem(txt, anchor=(0, 1), color='#1F2937')
    ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                      max(fc.get('size', 18) - 4, 7)))
    plot_item.addItem(ti)
    try:
        vb = plot_item.getViewBox()
        rng = vb.viewRange()
        y_top = rng[1][1] if rng[1][1] > 0 else 10
        ti.setPos(median + (rng[0][1] - rng[0][0]) * 0.01, y_top * 0.92)
    except Exception:
        ti.setPos(median, 0)


def _add_stats_text(plot_item, plot_data, cfg):
    """Add statistics text box to histogram plot.
    Args:
        plot_item (Any): The plot item.
        plot_data (Any): The plot data.
        cfg (Any): The cfg.
    """
    fc = get_font_config(cfg)
    dt = cfg.get('data_type_display', 'Counts')
    sorted_data = sort_element_dict_by_mass(plot_data)

    lines = []
    for el, vals in sorted_data.items():
        if not vals:
            continue
        if dt != 'Counts':
            v = [x for x in vals if x > 0 and not np.isnan(x)]
        else:
            v = vals
        if not v:
            continue
        n = len(v)
        m = np.mean(v)
        md = np.median(v)
        if 'Mass' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.2f} fg, med={md:.2f} fg")
        elif 'Moles' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.4f} fmol, med={md:.4f} fmol")
        elif 'Diameter' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.1f} nm, med={md:.1f} nm")
        else:
            lines.append(f"{el}: n={n}, \u03bc={m:.1f}, med={md:.1f}")

    if lines:
        ti = pg.TextItem(
            '\n'.join(lines), anchor=(0, 1),
            border=pg.mkPen(color='#CBD5E1', width=1),
            fill=pg.mkBrush(255, 255, 255, 220),
            color='#374151')
        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                          max(fc.get('size', 18) - 4, 7)))
        plot_item.addItem(ti)
        try:
            vb = plot_item.getViewBox()
            rng = vb.viewRange()
            ti.setPos(rng[0][0] + (rng[0][1] - rng[0][0]) * 0.02,
                      rng[1][1] * 0.98)
        except Exception:
            ti.setPos(0, 0)


def _draw_single_histogram(plot_item, element_data, cfg, single_color=None):
    """Draw histogram for one set of element data onto a PyQtGraph PlotItem.
    Args:
        plot_item (Any): The plot item.
        element_data (Any): The element data.
        cfg (Any): The cfg.
        single_color (Any): The single color.
    Returns:
        object: Result of the operation.
    """
    dt = cfg.get('data_type_display', 'Counts')
    log_x = cfg.get('log_x', False)
    bins_n = cfg.get('bins', 20)

    sorted_data = sort_element_dict_by_mass(element_data)
    is_single = len(sorted_data) == 1

    all_vals = []
    for idx, (elem, raw_vals) in enumerate(sorted_data.items()):
        vals = _prepare_values(raw_vals, dt, log_x)
        if vals is None:
            continue

        color = single_color or _get_element_color(elem, idx, cfg)
        _draw_histogram_bars(plot_item, vals, cfg, color, bins_n,
                             name=_fmt_elem(elem, cfg))
        all_vals.append(vals)

        if is_single:
            _, bin_edges = np.histogram(vals, bins=bins_n)
            if cfg.get('show_curve', True) and len(vals) > 5:
                _add_density_curve(plot_item, vals, cfg, bin_edges, len(vals))
            if cfg.get('show_median', True):
                _add_median_line(plot_item, vals, cfg)

    if all_vals:
        pooled = np.concatenate(all_vals) if len(all_vals) > 1 else all_vals[0]
        _add_shaded_region_hist(plot_item, pooled, cfg)
        _add_stat_lines_hist(plot_item, pooled, cfg)
        _add_det_limit_v(plot_item, cfg)
    _apply_box(plot_item, cfg)

    xl, yl = _get_xy_labels(cfg)
    set_axis_labels(plot_item, xl, yl, cfg)

    if cfg.get('log_x', False):
        plot_item.getAxis('bottom').setLogMode(True)
    if cfg.get('log_y', False):
        plot_item.getAxis('left').setLogMode(True)

    if not cfg.get('auto_x', True):
        xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
        if cfg.get('log_x', False) and xn > 0 and xx > 0:
            xn, xx = float(np.log10(xn)), float(np.log10(xx))
        plot_item.setXRange(xn, xx, padding=0)
    if not cfg.get('auto_y', True):
        plot_item.setYRange(cfg.get('y_min', 0), cfg.get('y_max', 100), padding=0)

    _apply_histogram_grid(plot_item, cfg)
    if not is_single and len(sorted_data) > 1:
        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(plot_item.graphicsItem())
        plot_item.legend = legend
        for idx, elem in enumerate(sorted_data.keys()):
            color = single_color or _get_element_color(elem, idx, cfg)
            co = QColor(color)
            swatch = pg.BarGraphItem(x=[0], height=[0], width=0,
                                     brush=pg.mkBrush(co.red(), co.green(), co.blue(), 180))
            legend.addItem(swatch, _fmt_elem(elem, cfg))

    apply_font_to_pyqtgraph(plot_item, cfg)
    return sorted_data


def _sort_elements_for_display(elements, counts, sort_option):
    """Sort elements by user preference.
    Args:
        elements (Any): The elements.
        counts (Any): The counts.
        sort_option (Any): The sort option.
    Returns:
        tuple: Result of the operation.
    """
    mass_sorted = sort_elements_by_mass(elements)
    if sort_option == 'No Sorting':
        ec = dict(zip(elements, counts))
        return mass_sorted, [ec[e] for e in mass_sorted]
    elif sort_option == 'Ascending':
        pairs = sorted(zip(elements, counts), key=lambda x: x[1])
    elif sort_option == 'Descending':
        pairs = sorted(zip(elements, counts), key=lambda x: x[1], reverse=True)
    elif sort_option == 'Alphabetical':
        pairs = sorted(zip(elements, counts), key=lambda x: element_alphabetical_key(x[0]))
    else:
        ec = dict(zip(elements, counts))
        return mass_sorted, [ec[e] for e in mass_sorted]
    el, ct = zip(*pairs) if pairs else ([], [])
    return list(el), list(ct)


def _draw_single_bar_chart(plot_item, element_counts, cfg, single_color=None,
                            show_y_label=True):
    """Draw bar chart for one set of element counts onto a PyQtGraph PlotItem.
    Args:
        plot_item (Any): The plot item.
        element_counts (Any): The element counts.
        cfg (Any): The cfg.
        single_color (Any): The single color.
        show_y_label (Any): The show y label.
    """
    log_y = cfg.get('log_y', False)
    sort_opt = cfg.get('sort_bars', 'No Sorting')
    show_vals = cfg.get('show_values', True)
    fc = get_font_config(cfg)
    min_count = cfg.get('min_particle_count', 0)

    if min_count > 0:
        element_counts = {e: c for e, c in element_counts.items()
                          if c >= min_count}

    elems = list(element_counts.keys())
    counts = [element_counts[e] for e in elems]
    elems, counts = _sort_elements_for_display(elems, counts, sort_opt)

    original_counts = list(counts)
    if log_y:
        counts = [np.log10(c + 1) for c in counts]

    x = np.arange(len(elems), dtype=float)

    for i, (xi, elem, c) in enumerate(zip(x, elems, counts)):
        color = single_color or _get_element_color(elem, i, cfg)
        co = QColor(color)
        bar = pg.BarGraphItem(
            x=[xi], height=[c], width=0.7,
            brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
            pen=pg.mkPen(color='w', width=0.5))
        bar.opts['_trace_name'] = _fmt_elem(elem, cfg)
        plot_item.addItem(bar)

    if show_vals:
        max_c = max(counts) if counts else 1
        for i, (xi, c, oc) in enumerate(zip(x, counts, original_counts)):
            if oc > 0:
                ti = pg.TextItem(str(int(oc)), anchor=(0.5, 1), color='#374151')
                ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                  max(fc.get('size', 18) - 4, 7)))
                plot_item.addItem(ti)
                ti.setPos(xi, c + max_c * 0.02)

    ax_bottom = plot_item.getAxis('bottom')
    ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(elems)]
    ax_bottom.setTicks([ticks])

    yl = 'Particle Count' 
    xl = 'Isotope Elements'
    set_axis_labels(plot_item, xl, yl if show_y_label else '', cfg)
    
    if log_y:
        plot_item.getAxis('left').setLogMode(True)
    _add_det_limit_h(plot_item, cfg)
    _apply_box(plot_item, cfg)
    apply_font_to_pyqtgraph(plot_item, cfg)


class ElementBarChartDisplayDialog(QDialog):
    """Full-figure bar chart dialog with controlled custom context menu."""

    def __init__(self, bar_node, parent_window=None):
        """
        Initialize the element bar chart display dialog.

        Args:
            bar_node (Any): Plot node providing config and extracted plot data.
            parent_window (Any): Parent window reference.
        """
        super().__init__(parent_window)
        self.node = bar_node
        self.parent_window = parent_window
        self.setWindowTitle("Element Particle Count Bar Chart")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        """
        Build the PyQtGraph canvas plus standardized bottom action buttons.

        Preserved behavior:
            Plot rendering/data logic is unchanged. This only routes UI entry points
            for format settings, quantity settings, reset, and export.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.pw, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.stats_label)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.setToolTip("Reset plot view ranges to default auto-range.")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        layout.addLayout(bb)

    def _ctx_menu(self, pos):
        """
        Show the custom bar-chart right-click menu.

        Args:
            pos (Any): Local click position within the graphics widget.

        Preserved behavior:
            Keeps lightweight visual toggles plus plot-specific quick sorting while
            delegating full configuration/export/reset to bottom buttons.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_values', 'Show Values on Bars', True),
            ('show_box', 'Figure Box (frame)', True),
            ('show_det_limit', 'Detection Limit Line', False),
        ]:
            a = tg.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode)
            a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        sort_menu = menu.addMenu("Sort Bars")
        cur_sort = cfg.get('sort_bars', 'No Sorting')
        for s in SORT_OPTIONS:
            a = sort_menu.addAction(s)
            a.setCheckable(True)
            a.setChecked(s == cur_sort)
            a.triggered.connect(lambda _, v=s: self._set('sort_bars', v))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle_key(self, key):
        """
        Toggle a lightweight visual option from the custom context menu.

        Args:
            key (str): Config key to toggle.
        """
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        """
        Set a config value from right-click quick actions.

        Args:
            key (str): Config key to update.
            value (Any): New value to set.
        """
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        """
        Open the legacy all-in-one settings dialog for compatibility.

        Preserved behavior:
            Existing combined route remains available internally; bottom buttons now
            use scoped settings dialogs.
        """
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open the rich PyQtGraph visual editor for bar-chart formatting.

        Preserved behavior:
            This intentionally reuses the pre-migration PlotSettings workflow for
            visual edits (fonts, grid/axis styling, trace/item appearance, and
            related plot presentation controls) while keeping quantity controls in
            the separate ``Configure plot quantities`` dialog. The format route
            intentionally hides live ``Apply`` so users confirm changes through
            one-shot ``OK``.
        """
        self._open_plot_settings(
            title_override="Element bar chart plot format settings",
            show_apply=False)

    def _open_configure_plot_quantities(self):
        """Open quantities-scoped bar chart settings dialog."""
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self, scope='quantities')
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_settings(self, title_override=None, show_apply=True):
        """
        Open the existing PlotSettingsDialog on the first available PlotItem.

        Args:
            title_override (str | None): Optional window-title override used by
                the standardized bottom ``Plot format settings`` route.
            show_apply (bool): Whether the shared PlotSettings dialog should
                expose live ``Apply``. Element bar chart format workflow passes
                ``False`` to enforce one-shot confirmation via ``OK``.

        Preserved behavior:
            Uses the same PyQtGraph formatting editor path that existed before
            right-click cleanup, but keeps it accessible via bottom buttons
            instead of context-menu entries.
        """
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            dlg = _PlotSettingsDialog(
                _PlotWidgetAdapter(self.pw, pi), self, show_apply=show_apply)
            if title_override:
                try:
                    dlg.setWindowTitle(title_override)
                except Exception:
                    pass
            dlg.exec()

    def _download_figure(self):
        """Export bar chart as image or CSV via existing PyQtGraph export path."""
        import pandas as pd
        csv_df = None
        try:
            plot_data = self.node.extract_plot_data()
            cfg = self.node.config

            if plot_data:
                rows = []
                if _is_multi(self.node.input_data):
                    for sn, sd in plot_data.items():
                        dname = get_display_name(sn, cfg)
                        for elem, count in sd.items():
                            rows.append({'Sample': dname, 'Element': elem, 'Particle Count': count})
                else:
                    for elem, count in plot_data.items():
                        rows.append({'Element': elem, 'Particle Count': count})
                if rows:
                    csv_df = pd.DataFrame(rows)
        except Exception as e:
            print(f"Warning: could not build CSV data: {e}")

        download_pyqtgraph_figure(
            self.pw, self,
            default_name='bar_chart',
            csv_data=csv_df,
        )

    def _export_figure(self):
        """Route standardized export button to existing bar-chart export path."""
        self._download_figure()

    def _disable_native_pyqtgraph_context_menu(self):
        """
        Disable native PyQtGraph plot/view menus for this dialog only.

        Preserved behavior:
            This does not alter PyQtGraph globally or in other plots; it only
            suppresses stacked native menus in this bar-chart dialog.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    pass
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    pass

    def _reset_layout(self):
        """
        Reset current PyQtGraph view ranges to auto-range without changing data.

        Preserved behavior:
            Sorting and quantity configuration are left unchanged.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    pass
    # ── Refresh ─────────────────────────────

    def _refresh(self):
        try:
            parent_layout = self.pw.parent().layout()
            idx = parent_layout.indexOf(self.pw)
            parent_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            parent_layout.insertWidget(idx, self.pw, stretch=1)

            plot_data = self.node.extract_plot_data()
            cfg = self.node.config

            if not plot_data:
                pi = self.pw.addPlot()
                t = pg.TextItem(
                    "No particle data available\n"
                    "Connect to Sample Selector\nand run particle detection",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(t)
                t.setPos(0.5, 0.5)
                pi.hideAxis('left')
                pi.hideAxis('bottom')
                self.stats_label.setText("")
                return

            if _is_multi(self.node.input_data):
                mode = cfg.get('display_mode', BAR_DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                elif mode == 'Stacked Bars':
                    self._draw_stacked(plot_data, cfg)
                elif mode == 'By Sample (Element Colors)':
                    self._draw_by_sample(plot_data, cfg)
                else:
                    self._draw_grouped(plot_data, cfg)
            else:
                pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom')})
                _draw_single_bar_chart(pi, plot_data, cfg)

            self._disable_native_pyqtgraph_context_menu()
            self._update_stats(plot_data)

        except Exception as e:
            print(f"Error updating bar chart: {e}")
            import traceback
            traceback.print_exc()

    def _draw_subplots(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        samples = list(plot_data.keys())
        n = len(samples)
        cols = min(2, n)
        for idx, sn in enumerate(samples):
            if idx > 0 and idx % cols == 0:
                self.pw.nextRow()
            pi = self.pw.addPlot(title=get_display_name(sn, cfg),
                                  axisItems={'bottom': HtmlAxisItem('bottom')})
            sd = plot_data[sn]
            if sd:
                color = get_sample_color(sn, idx, cfg)
                _draw_single_bar_chart(pi, sd, cfg, single_color=color)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        samples = list(plot_data.keys())
        for idx, sn in enumerate(samples):
            pi = self.pw.addPlot(title=get_display_name(sn, cfg),
                                  axisItems={'bottom': HtmlAxisItem('bottom')})
            sd = plot_data[sn]
            if sd:
                color = get_sample_color(sn, idx, cfg)
                _draw_single_bar_chart(pi, sd, cfg, single_color=color,
                                        show_y_label=(idx == 0))

    def _draw_grouped(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        show_vals = cfg.get('show_values', True)
        sort_opt = cfg.get('sort_bars', 'No Sorting')

        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))

        min_count = cfg.get('min_particle_count', 0)
        if min_count > 0:
            all_elems = [e for e in all_elems
                        if sum(sd.get(e, 0) for sd in plot_data.values()) >= min_count]

        if sort_opt != 'No Sorting':
            totals = [(e, sum(plot_data[s].get(e, 0) for s in plot_data))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(all_elems), dtype=float)
        n_samples = len(plot_data)
        bar_w = 0.8 / max(n_samples, 1)

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        global_max = 0
        for i, (sn, sd) in enumerate(plot_data.items()):
            color = get_sample_color(sn, i, cfg)
            dname = get_display_name(sn, cfg)
            heights = [sd.get(e, 0) for e in all_elems]
            orig = list(heights)
            if log_y:
                heights = [np.log10(h + 1) for h in heights]
            cur_max = max(heights) if heights else 0
            if cur_max > global_max:
                global_max = cur_max

            offsets = x + (i - n_samples / 2 + 0.5) * bar_w
            co = QColor(color)
            bar = pg.BarGraphItem(
                x=offsets, height=heights, width=bar_w,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                pen=pg.mkPen(color='w', width=0.5))
            bar.opts['_trace_name'] = dname
            pi.addItem(bar)

            swatch = pg.BarGraphItem(x=[0], height=[0], width=0,
                                      brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215))
            legend.addItem(swatch, dname)

            if show_vals:
                for j, (xp, h, o) in enumerate(zip(offsets, heights, orig)):
                    if o > 0:
                        ti = pg.TextItem(str(int(o)), anchor=(0.5, 1), color='#374151')
                        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                          max(fc.get('size', 18) - 5, 6)))
                        pi.addItem(ti)
                        ti.setPos(xp, h + global_max * 0.02)

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(all_elems)]
        ax_bottom.setTicks([ticks])

        yl = 'Particle Count' 
        set_axis_labels(pi, 'Isotope Elements', yl, cfg)
        
        if log_y:
            pi.getAxis('left').setLogMode(True)        
        apply_font_to_pyqtgraph(pi, cfg)

    def _draw_stacked(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        sort_opt = cfg.get('sort_bars', 'No Sorting')

        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))

        min_count = cfg.get('min_particle_count', 0)
        if min_count > 0:
            all_elems = [e for e in all_elems
                        if sum(sd.get(e, 0) for sd in plot_data.values()) >= min_count]

        if sort_opt != 'No Sorting':
            totals = [(e, sum(plot_data[s].get(e, 0) for s in plot_data))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(all_elems), dtype=float)
        bottom = np.zeros(len(all_elems))

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        for i, (sn, sd) in enumerate(plot_data.items()):
            color = get_sample_color(sn, i, cfg)
            dname = get_display_name(sn, cfg)
            heights = np.array([sd.get(e, 0) for e in all_elems], dtype=float)

            if log_y:
                top = bottom + heights
                h_plot = np.log10(top + 1) - np.log10(bottom + 1)
                b_plot = np.log10(bottom + 1)
            else:
                h_plot = heights
                b_plot = bottom

            co = QColor(color)
            for j in range(len(x)):
                bar = pg.BarGraphItem(
                    x=[x[j]], height=[h_plot[j]], width=0.7,
                    brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                    pen=pg.mkPen(color='w', width=0.5))
                bar.opts['_trace_name'] = dname
                bar.setPos(0, b_plot[j])
                pi.addItem(bar)

            swatch = pg.BarGraphItem(x=[0], height=[0], width=0,
                                      brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215))
            legend.addItem(swatch, dname)
            bottom += heights

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(all_elems)]
        ax_bottom.setTicks([ticks])

        yl = 'Particle Count' 
        set_axis_labels(pi, 'Isotope Elements', yl, cfg)
        
        if log_y:
            pi.getAxis('left').setLogMode(True)        
        apply_font_to_pyqtgraph(pi, cfg)

    def _draw_by_sample(self, plot_data, cfg):
        """X-axis = samples, one bar per element per sample, colors = elements.
        Respects sample_order for time-series use.
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        show_vals = cfg.get('show_values', True)
        sort_opt = cfg.get('sort_bars', 'No Sorting')
        min_count = cfg.get('min_particle_count', 0)

        sample_order = cfg.get('sample_order', [])
        if sample_order:
            samples = [s for s in sample_order if s in plot_data]
            samples += [s for s in plot_data if s not in samples]
        else:
            samples = list(plot_data.keys())

        all_elems_set = set()
        for sd in plot_data.values():
            all_elems_set.update(sd.keys())
        if min_count > 0:
            all_elems_set = {
                e for e in all_elems_set
                if sum(plot_data[s].get(e, 0) for s in samples) >= min_count}
        all_elems = sort_elements_by_mass(list(all_elems_set))

        if sort_opt != 'No Sorting' and samples:
            totals = [(e, sum(plot_data[s].get(e, 0) for s in samples))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(samples), dtype=float)
        n_elems = max(len(all_elems), 1)
        bar_w = 0.8 / n_elems

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        global_max = 0.0
        for j, elem in enumerate(all_elems):
            color = _get_element_color(elem, j, cfg)
            label = _fmt_elem(elem, cfg)
            heights = [plot_data[s].get(elem, 0) for s in samples]
            orig = list(heights)
            if log_y:
                heights = [np.log10(h + 1) for h in heights]
            cur_max = max(heights) if heights else 0.0
            if cur_max > global_max:
                global_max = cur_max

            offsets = x + (j - n_elems / 2 + 0.5) * bar_w
            co = QColor(color)
            bar = pg.BarGraphItem(
                x=offsets, height=heights, width=bar_w,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                pen=pg.mkPen(color='w', width=0.5))
            bar.opts['_trace_name'] = label
            pi.addItem(bar)

            swatch = pg.BarGraphItem(x=[0], height=[0], width=0,
                                     brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215))
            legend.addItem(swatch, label)

            if show_vals:
                for xp, h, o in zip(offsets, heights, orig):
                    if o > 0:
                        ti = pg.TextItem(str(int(o)), anchor=(0.5, 1),
                                         color='#374151')
                        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                         max(fc.get('size', 18) - 5, 6)))
                        pi.addItem(ti)
                        ti.setPos(xp, h + global_max * 0.02)

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), get_display_name(s, cfg))
                 for i, s in enumerate(samples)]
        ax_bottom.setTicks([ticks])

        set_axis_labels(pi, 'Sample', 'Particle Count', cfg)
        if log_y:
            pi.getAxis('left').setLogMode(True)
        apply_font_to_pyqtgraph(pi, cfg)

    def _update_stats(self, plot_data):
        """
        Args:
            plot_data (Any): The plot data.
        """
        if _is_multi(self.node.input_data):
            total = sum(sum(v for v in sd.values()) for sd in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} samples  \u00b7  {total:,} total particles")
        else:
            total = sum(plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} elements  \u00b7  {total:,} total particles")


class ElementBarChartPlotNode(QObject):
    """Element particle-count bar chart node with right-click context menu."""

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'show_values': True,
        'sort_bars': 'No Sorting',
        'log_x': False,
        'log_y': False,
        'show_box': True,
        'show_det_limit': False,
        'det_limit_value': 1.0,
        'det_limit_color': '#DC2626',
        'det_limit_style': 'dash',
        'det_limit_width': 2,
        'det_limit_label': '',
        'element_colors': {},
        'display_mode': 'Grouped Bars (Side by Side)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'sample_order': [],
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode': 'Symbol',
        'min_particle_count': 10,
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Element Bar Chart"
        self.node_type = "element_bar_chart_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

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
        dlg = ElementBarChartDisplayDialog(self, parent_window)
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

    def extract_plot_data(self):
        """Extract element particle counts from input.
        Returns:
            None
        """
        if not self.input_data:
            return None

        itype = self.input_data.get('type')

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data')
            if not particles:
                return None
            counts = {}
            for p in particles:
                for el, val in p.get('elements', {}).items():
                    if val > 0:
                        counts[el] = counts.get(el, 0) + 1
            return counts or None

        elif itype == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            if not particles:
                return None
            result = {sn: {} for sn in names}
            for p in particles:
                src = p.get('source_sample')
                if src not in result:
                    continue
                for el, val in p.get('elements', {}).items():
                    if val > 0:
                        result[src][el] = result[src].get(el, 0) + 1
            return {k: v for k, v in result.items() if v} or None

        return None


