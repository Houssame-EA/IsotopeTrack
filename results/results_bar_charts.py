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
    format_element_label, LABEL_MODES,
    SHADE_TYPES, _QT_LINE, _apply_box,
    _add_shaded_region_hist, _add_stat_lines_hist, _add_det_limit_v, _add_det_limit_h,
)
try:
    from widget.custom_plot_widget import PlotSettingsDialog as _PlotSettingsDialog
    _CUSTOM_PLOT_AVAILABLE = True
except Exception:
    _PlotSettingsDialog = None
    _CUSTOM_PLOT_AVAILABLE = False
from results.utils_sort import (
    sort_elements_by_mass, sort_element_dict_by_mass,
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
    'Combined with Legend',
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
    return format_element_label(elem, cfg.get('label_mode', 'Symbol'))


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
                self._cfg.get('display_mode', HIST_DISPLAY_MODES[0]))
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
        fl.addRow("Element Label:", self.label_mode)
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
            out['display_mode'] = self.display_mode.currentText()
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        out['label_mode'] = self.label_mode.currentText()
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


    def _ctx_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_curve',  'Density Curve',       True),
            ('show_stats',  'Statistics',          True),
            ('log_x',       'Log X-axis',          False),
            ('log_y',       'Log Y-axis',          False),
            ('auto_x',      'Auto X Range',        True),
            ('auto_y',      'Auto Y Range',        True),
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

        tg.addSeparator()
        sep2 = tg.addAction("-- Shaded Region --"); sep2.setEnabled(False)
        shm = tg.addMenu("Shade Type")
        for st in SHADE_TYPES:
            a = shm.addAction(st); a.setCheckable(True)
            a.setChecked(cfg.get('shade_type', 'None') == st)
            a.triggered.connect(lambda _, v=st: self._set('shade_type', v))

        dt_menu = menu.addMenu("Data Type")
        cur_dt = cfg.get('data_type_display', 'Counts')
        for dt in HIST_DATA_TYPES:
            a = dt_menu.addAction(dt); a.setCheckable(True)
            a.setChecked(dt == cur_dt)
            a.triggered.connect(lambda _, d=dt: self._set('data_type_display', d))

        ct_menu = menu.addMenu("Curve Type")
        cur_ct = cfg.get('curve_type', 'Kernel Density')
        for ct in CURVE_TYPES:
            a = ct_menu.addAction(ct); a.setCheckable(True)
            a.setChecked(ct == cur_ct)
            a.triggered.connect(lambda _, c=ct: self._set('curve_type', c))

        if _is_multi(self.node.input_data):
            dm_menu = menu.addMenu("Display Mode")
            cur = cfg.get('display_mode', HIST_DISPLAY_MODES[0])
            for m in HIST_DISPLAY_MODES:
                a = dm_menu.addAction(m); a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set('display_mode', mode))

        groups = cfg.get('element_groups', [])
        if groups:
            menu.addSeparator()
            gm = menu.addMenu(f"Element Groups ({len(groups)})")
            for g in groups:
                name = g.get('name', '?')
                elems = ' + '.join(g.get('elements', []))
                a = gm.addAction(f"{name} = {elems}")
                a.setEnabled(False)

        menu.addSeparator()
        menu.addAction("Configure...").triggered.connect(self._open_settings)
        menu.addAction("Download Figure...").triggered.connect(self._download_figure)
        if _CUSTOM_PLOT_AVAILABLE:
            menu.addAction("Plot Settings...").triggered.connect(self._open_plot_settings)
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

    def _open_settings(self):
        dlg = HistogramSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self,
            available_elements=self._get_available_elements())
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_settings(self):
        """Open the full PlotSettingsDialog (font, grid, traces) on the
        first available PlotItem inside the GraphicsLayoutWidget."""
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            _PlotSettingsDialog(_PlotWidgetAdapter(self.pw, pi), self).exec()

    def _download_figure(self):
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
                mode = cfg.get('display_mode', HIST_DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                elif mode == 'Combined with Legend':
                    self._draw_combined(plot_data, cfg)
                else:
                    self._draw_overlaid(plot_data, cfg)
            else:
                pi = self.pw.addPlot()
                _draw_single_histogram(pi, plot_data, cfg)
                if cfg.get('show_stats', True):
                    _add_stats_text(pi, plot_data, cfg)

            self._update_stats(plot_data)

        except Exception as e:
            print(f"Error updating histogram: {e}")
            import traceback
            traceback.print_exc()

    def _draw_subplots(self, plot_data, cfg):
        """
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
                color = get_sample_color(sn, idx, cfg)
                _draw_single_histogram(pi, sd, cfg, single_color=color)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        first_pi = None
        xl, yl = _get_xy_labels(cfg)
        for idx, (sn, sd) in enumerate(plot_data.items()):
            pi = self.pw.addPlot(row=0, col=idx, title=get_display_name(sn, cfg))
            if sd:
                color = get_sample_color(sn, idx, cfg)
                _draw_single_histogram(pi, sd, cfg, single_color=color)
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
        apply_font_to_pyqtgraph(pi, cfg)

    def _draw_combined(self, plot_data, cfg):
        """
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
    """Full settings dialog for element bar chart node."""

    def __init__(self, config, is_multi, sample_names, parent=None):
        """
        Args:
            config (Any): Configuration dictionary.
            is_multi (Any): The is multi.
            sample_names (Any): The sample names.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Element Bar Chart Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._build_ui()

    def _build_ui(self):
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
            self.display_mode.addItems(BAR_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                self._cfg.get('display_mode', BAR_DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
        self.show_values = QCheckBox()
        self.show_values.setChecked(self._cfg.get('show_values', True))
        fl.addRow("Show Values on Bars:", self.show_values)
        self.sort_bars = QComboBox()
        self.sort_bars.addItems(SORT_OPTIONS)
        self.sort_bars.setCurrentText(self._cfg.get('sort_bars', 'No Sorting'))
        fl.addRow("Sort Bars:", self.sort_bars)
        self.log_y = QCheckBox()
        self.log_y.setChecked(self._cfg.get('log_y', False))
        fl.addRow("Log Y-axis:", self.log_y)
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Element Label:", self.label_mode)
        self.min_count = QSpinBox()
        self.min_count.setRange(0, 100000)
        self.min_count.setValue(self._cfg.get('min_particle_count', 10))
        self.min_count.setSuffix(" particles")
        self.min_count.setToolTip(
            "Hide elements with fewer particles than this threshold.\n"
            "Set to 0 to show all elements.")
        fl.addRow("Min Particle Count:", self.min_count)
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
                w = QWidget()
                w.setLayout(row)
                vl.addWidget(w)
            layout.addWidget(g)

            g2 = QGroupBox("Sample Display Order")
            vl2 = QVBoxLayout(g2)
            hint = QLabel(
                "Drag or use ↑↓ to set the order — useful for time series.")
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
            up_btn = QPushButton("↑  Up")
            up_btn.setFixedWidth(72)
            up_btn.clicked.connect(self._move_up)
            dn_btn = QPushButton("↓  Down")
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
        row = self._order_list.currentRow()
        if row > 0:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row - 1, item)
            self._order_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._order_list.currentRow()
        if row < self._order_list.count() - 1:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row + 1, item)
            self._order_list.setCurrentRow(row + 1)

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        out = dict(self._cfg)
        out['show_values'] = self.show_values.isChecked()
        out['sort_bars'] = self.sort_bars.currentText()
        out['log_y'] = self.log_y.isChecked()
        out['label_mode'] = self.label_mode.currentText()
        out['min_particle_count'] = self.min_count.value()
        if self._multi:
            out['display_mode'] = self.display_mode.currentText()
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
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
        pairs = sorted(zip(elements, counts), key=lambda x: x[0])
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
    """Full-figure bar chart dialog with PyQtGraph and right-click context menu."""

    def __init__(self, bar_node, parent_window=None):
        """
        Args:
            bar_node (Any): The bar node.
            parent_window (Any): The parent window.
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

    # ── Context menu ────────────────────────

    def _ctx_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_values', 'Show Values on Bars', True),
            ('log_y',       'Log Y-axis',          False),
            ('show_box',    'Figure Box (frame)',   True),
        ]:
            a = tg.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        tg.addSeparator()
        sep = tg.addAction("-- Reference Lines --"); sep.setEnabled(False)
        det_a = tg.addAction("Detection Limit Line"); det_a.setCheckable(True)
        det_a.setChecked(cfg.get('show_det_limit', False))
        det_a.triggered.connect(lambda _: self._toggle_key('show_det_limit'))

        sort_menu = menu.addMenu("Sort Bars")
        cur_sort = cfg.get('sort_bars', 'No Sorting')
        for s in SORT_OPTIONS:
            a = sort_menu.addAction(s); a.setCheckable(True)
            a.setChecked(s == cur_sort)
            a.triggered.connect(lambda _, v=s: self._set('sort_bars', v))

        if _is_multi(self.node.input_data):
            dm = menu.addMenu("Display Mode")
            cur = cfg.get('display_mode', BAR_DISPLAY_MODES[0])
            for m in BAR_DISPLAY_MODES:
                a = dm.addAction(m); a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set('display_mode', mode))

        menu.addSeparator()
        menu.addAction("Configure...").triggered.connect(self._open_settings)
        menu.addAction("Download Figure...").triggered.connect(self._download_figure)
        if _CUSTOM_PLOT_AVAILABLE:
            menu.addAction("Plot Settings...").triggered.connect(self._open_plot_settings)
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

    def _open_settings(self):
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_settings(self):
        """Open the full PlotSettingsDialog (font, grid, traces) on the
        first available PlotItem inside the GraphicsLayoutWidget."""
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            _PlotSettingsDialog(_PlotWidgetAdapter(self.pw, pi), self).exec()
            
    def _download_figure(self):
        """Export bar chart as image or CSV."""
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
                pi = self.pw.addPlot()
                _draw_single_bar_chart(pi, plot_data, cfg)

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
            pi = self.pw.addPlot(title=get_display_name(sn, cfg))
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
            pi = self.pw.addPlot(title=get_display_name(sn, cfg))
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
        pi = self.pw.addPlot()
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
                totals.sort(key=lambda x: x[0])
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
        pi = self.pw.addPlot()
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
                totals.sort(key=lambda x: x[0])
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
        pi = self.pw.addPlot()
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
                totals.sort(key=lambda x: x[0])
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