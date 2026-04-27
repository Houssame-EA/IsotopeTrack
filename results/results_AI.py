from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QSplitter, QTextEdit, QProgressBar, QMessageBox, QComboBox,
    QSlider, QStackedWidget, QScrollArea, QWidget, QMenu, QDialogButtonBox,
    QFileDialog, QSizePolicy, QCheckBox,
)
from PySide6.QtCore import QObject, Signal, QPointF, QThread, QTimer, Qt
from PySide6.QtGui import QPixmap, QImage, QFont, QCursor, QColor
import requests, io, re, json, time, math, threading
from collections import Counter, defaultdict
import numpy as np
from theme import theme as global_theme

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure as MplFigure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


OLLAMA_BASE  = "http://localhost:11434"
OLLAMA_CHAT  = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS  = f"{OLLAMA_BASE}/api/tags"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-sonnet-4-20250514"

PLOT_COLORS = [
    '#663399','#2E86AB','#A23B72','#F18F01','#C73E1D',
    '#2D6A4F','#7209B7','#3A86FF','#FB5607','#8338EC',
    '#06D6A0','#118AB2','#EF476F','#FFD166','#073B4C',
]

CODE_EXEC_TIMEOUT = 30
MAX_CODE_RETRIES = 2
CHARS_PER_TOKEN = 3.5
STREAM_RENDER_INTERVAL_MS = 80
SAMPLE_PARTICLES_COUNT = 15


class Theme:
    _dark = False
    LIGHT = {
        'bg':'#FFFFFF','bg_secondary':'#FAFAFA','bg_tertiary':'#F3F4F6',
        'surface':'#FFFFFF','surface_hover':'#F9FAFB',
        'border':'#E5E7EB','border_light':'#F3F4F6',
        'text':'#1F2937','text_secondary':'#6B7280','text_tertiary':'#9CA3AF',
        'accent':'#D97706','accent_hover':'#B45309','accent_surface':'#FFFBEB',
        'user_bubble':'#D97706','user_text':'#FFFFFF',
        'ai_bubble':'#F3F4F6','ai_text':'#1F2937',
        'think_bg':'#F0FDF4','think_border':'#BBF7D0','think_text':'#166534',
        'error_bg':'#FEF2F2','error_border':'#FECACA','error_text':'#991B1B',
        'error_code_bg':'#FEE2E2',
        'ctx_bg':'#F0FDF4','ctx_border':'#BBF7D0','ctx_text':'#166534',
        'code_bg':'#1F2937','code_text':'#E5E7EB',
        'input_bg':'#FFFFFF','input_border':'#D1D5DB','input_focus':'#D97706',
        'scrollbar_bg':'#F3F4F6','scrollbar_handle':'#D1D5DB',
        'success_dot':'#10B981','warn_dot':'#F59E0B','error_dot':'#EF4444',
        'progress_bg':'#E5E7EB','progress_chunk':'#D97706',
        'badge_bg':'#D1FAE5','badge_text':'#065F46',
        'sug_bg':'#F8FAFC','sug_text':'#374151','sug_border':'#E5E7EB',
        'sug_hover_bg':'#FFFBEB','sug_hover_border':'#D97706','sug_hover_text':'#B45309',
        'fig_border':'#E5E7EB','fig_bg':'#FFFFFF',
        'fig_btn_bg':'#F3F4F6','fig_btn_border':'#D1D5DB',
        'stop_bg':'#EF4444','stop_hover':'#DC2626','speed_text':'#9CA3AF',
        'carousel_bg':'#FAFAFA','ctrl_bg':'#F3F4F6',
    }
    DARK = {
        'bg':'#1A1A1A','bg_secondary':'#212121','bg_tertiary':'#2A2A2A',
        'surface':'#262626','surface_hover':'#303030',
        'border':'#3A3A3A','border_light':'#333333',
        'text':'#ECECEC','text_secondary':'#A0A0A0','text_tertiary':'#707070',
        'accent':'#E8A745','accent_hover':'#D4922E','accent_surface':'#2D2518',
        'user_bubble':'#C8871E','user_text':'#FFFFFF',
        'ai_bubble':'#2A2A2A','ai_text':'#ECECEC',
        'think_bg':'#1A2E1A','think_border':'#2D4A2D','think_text':'#7FCC7F',
        'error_bg':'#2E1A1A','error_border':'#4A2D2D','error_text':'#F08080',
        'error_code_bg':'#351E1E',
        'ctx_bg':'#1A2E1A','ctx_border':'#2D4A2D','ctx_text':'#7FCC7F',
        'code_bg':'#0D0D0D','code_text':'#D4D4D4',
        'input_bg':'#262626','input_border':'#3A3A3A','input_focus':'#E8A745',
        'scrollbar_bg':'#212121','scrollbar_handle':'#404040',
        'success_dot':'#34D399','warn_dot':'#FBBF24','error_dot':'#F87171',
        'progress_bg':'#333333','progress_chunk':'#E8A745',
        'badge_bg':'#1A2E1A','badge_text':'#7FCC7F',
        'sug_bg':'#262626','sug_text':'#C0C0C0','sug_border':'#3A3A3A',
        'sug_hover_bg':'#2D2518','sug_hover_border':'#E8A745','sug_hover_text':'#E8A745',
        'fig_border':'#3A3A3A','fig_bg':'#262626',
        'fig_btn_bg':'#333333','fig_btn_border':'#444444',
        'stop_bg':'#DC2626','stop_hover':'#B91C1C','speed_text':'#707070',
        'carousel_bg':'#212121','ctrl_bg':'#2A2A2A',
    }
    @classmethod
    def is_dark(cls): return cls._dark
    @classmethod
    def toggle(cls): cls._dark = not cls._dark
    @classmethod
    def sync_with_global(cls): cls._dark = global_theme.is_dark
    @classmethod
    def c(cls, key): return (cls.DARK if cls._dark else cls.LIGHT).get(key, '#FF00FF')

Theme.sync_with_global()


def _safe_positive(v):
    """
    Args:
        v (Any): The v.
    Returns:
        object: Result of the operation.
    """
    try: v = float(v); return v > 0 and not np.isnan(v)
    except: return False

def _extract_element_values(particles, field='elements'):
    """Extract per-element values from a dict field. Returns {label: [values]}.
    Args:
        particles (Any): The particles.
        field (Any): The field.
    """
    result = {}
    for p in particles:
        d = p.get(field, {})
        if not isinstance(d, dict): continue
        for el, v in d.items():
            try: v = float(v)
            except: continue
            if v > 0 and not np.isnan(v):
                result.setdefault(el, []).append(v)
    return result

def _extract_element_counts(particles):
    """Count how many particles contain each element (by counts > 0).
    Args:
        particles (Any): The particles.
    Returns:
        object: Result of the operation.
    """
    c = {}
    for p in particles:
        for el, v in p.get('elements', {}).items():
            if _safe_positive(v): c[el] = c.get(el, 0) + 1
    return c

def _extract_total_values(particles, total_key='total_element_mass_fg'):
    """Extract a scalar from the 'totals' dict for each particle.
    Args:
        particles (Any): The particles.
        total_key (Any): The total key.
    Returns:
        object: Result of the operation.
    """
    vals = []
    for p in particles:
        t = p.get('totals', {})
        if isinstance(t, dict) and total_key in t:
            v = t[total_key]
            if _safe_positive(v): vals.append(float(v))
    return vals

def _extract_combinations(particles):
    """
    Args:
        particles (Any): The particles.
    Returns:
        object: Result of the operation.
    """
    combos = {}
    for p in particles:
        det = sorted(el for el, v in p.get('elements', {}).items() if _safe_positive(v))
        if det: key = ' + '.join(det); combos[key] = combos.get(key, 0) + 1
    return combos

def _extract_by_sample(particles, dc):
    """
    Args:
        particles (Any): The particles.
        dc (Any): The dc.
    Returns:
        object: Result of the operation.
    """
    names = dc.get('sample_names', [])
    bs = {}
    for p in particles:
        src = p.get('source_sample', '')
        if src: bs.setdefault(src, []).append(p)
    ordered = {}
    for n in names:
        if n in bs: ordered[n] = bs[n]
    for n, ps in bs.items():
        if n not in ordered: ordered[n] = ps
    return ordered

def _get_all_elements(particles):
    """
    Args:
        particles (Any): The particles.
    Returns:
        list: Result of the operation.
    """
    ec = _extract_element_counts(particles)
    return [el for el, _ in sorted(ec.items(), key=lambda x: -x[1])]


class InteractiveFigureWidget(QFrame):
    def __init__(self, spec, particles, dc):
        """
        Args:
            spec (Any): The spec.
            particles (Any): The particles.
            dc (Any): The dc.
        """
        super().__init__()
        self._spec = spec; self._particles = particles; self._dc = dc
        self._all_elements = _get_all_elements(particles)
        layout = QVBoxLayout(self); layout.setContentsMargins(8,8,8,8); layout.setSpacing(6)
        title = spec.get('title', 'Figure')
        self._title_lbl = QLabel(f"<b>{title}</b>")
        self._title_lbl.setTextFormat(Qt.RichText); self._title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_lbl)
        self._fig = MplFigure(figsize=(7,4.5), dpi=100); self._fig.set_facecolor('white')
        self._canvas = FigureCanvas(self._fig); self._canvas.setMinimumHeight(350)
        layout.addWidget(self._canvas, stretch=1)
        self._ctrl_frame = QFrame()
        self._ctrl_layout = QHBoxLayout(self._ctrl_frame)
        self._ctrl_layout.setContentsMargins(4,4,4,4); self._ctrl_layout.setSpacing(8)
        layout.addWidget(self._ctrl_frame)
        br = QHBoxLayout(); br.addStretch()
        sb = QPushButton("Save PNG"); sb.clicked.connect(self._save); br.addWidget(sb)
        ss = QPushButton("Save SVG"); ss.clicked.connect(lambda: self._save('svg')); br.addWidget(ss)
        layout.addLayout(br)
        self._build_controls(); self._render()

    def _build_controls(self): pass
    def _render(self): pass
    def _save(self, fmt='png'):
        """
        Args:
            fmt (Any): The fmt.
        """
        path, _ = QFileDialog.getSaveFileName(self, "Save", f"figure.{fmt}", f"{fmt.upper()} (*.{fmt})")
        if path: self._fig.savefig(path, format=fmt, dpi=150, bbox_inches='tight', facecolor='white')

    def _add_combo(self, label, items, default=None, cb=None):
        """
        Args:
            label (Any): Label text.
            items (Any): Sequence of items.
            default (Any): The default.
            cb (Any): The cb.
        Returns:
            object: Result of the operation.
        """
        l = QLabel(f"{label}:"); l.setStyleSheet(f"color:{Theme.c('text')};font-size:11px;")
        self._ctrl_layout.addWidget(l)
        c = QComboBox(); c.addItems(items)
        if default and default in items: c.setCurrentText(default)
        if cb: c.currentTextChanged.connect(cb)
        c.setStyleSheet(f"QComboBox{{background:{Theme.c('surface')};color:{Theme.c('text')};border:1px solid {Theme.c('border')};border-radius:4px;padding:3px 8px;}}")
        self._ctrl_layout.addWidget(c); return c

    def _add_slider(self, label, mn, mx, val, cb=None):
        """
        Args:
            label (Any): Label text.
            mn (Any): The mn.
            mx (Any): The mx.
            val (Any): The val.
            cb (Any): The cb.
        Returns:
            object: Result of the operation.
        """
        l = QLabel(f"{label}:"); l.setStyleSheet(f"color:{Theme.c('text')};font-size:11px;")
        self._ctrl_layout.addWidget(l)
        s = QSlider(Qt.Horizontal); s.setRange(mn, mx); s.setValue(val); s.setMaximumWidth(120)
        vl = QLabel(str(val)); vl.setFixedWidth(30); vl.setStyleSheet(f"color:{Theme.c('text')};font-size:11px;")
        def _ch(v): vl.setText(str(v))
        if cb:
            def _ch2(v): vl.setText(str(v)); cb(v)
            s.valueChanged.connect(_ch2)
        else:
            s.valueChanged.connect(_ch)
        self._ctrl_layout.addWidget(s); self._ctrl_layout.addWidget(vl); return s

    def _add_toggle(self, label, default=False, cb=None):
        """
        Args:
            label (Any): Label text.
            default (Any): The default.
            cb (Any): The cb.
        Returns:
            object: Result of the operation.
        """
        c = QCheckBox(label); c.setChecked(default)
        c.setStyleSheet(f"color:{Theme.c('text')};font-size:11px;")
        if cb: c.toggled.connect(cb)
        self._ctrl_layout.addWidget(c); return c

    def apply_theme(self):
        self._title_lbl.setStyleSheet(f"color:{Theme.c('text')};font-size:14px;")
        self._ctrl_frame.setStyleSheet(f"QFrame{{background:{Theme.c('ctrl_bg')};border-radius:8px;}}")

# ── Data getter helpers for widgets ─────────────────────────

def _get_element_data(particles, var, element):
    """Get data for a specific variable and element (or ALL).
    Args:
        particles (Any): The particles.
        var (Any): The var.
        element (Any): The element.
    Returns:
        tuple: Result of the operation.
    """
    field_map = {
        'diameter': 'element_diameter_nm',
        'mass': 'element_mass_fg',
        'counts': 'elements',
        'moles': 'element_moles_fmol',
        'mass_pct': 'mass_percentages',
        'mole_pct': 'mole_percentages',
    }
    field = field_map.get(var, 'elements')
    if element == 'ALL':
        vals = _extract_element_values(particles, field)
        return [v for vs in vals.values() for v in vs], 'All elements'
    else:
        vals = _extract_element_values(particles, field)
        return vals.get(element, []), element

def _get_total_data(particles, var):
    """Get per-particle total values.
    Args:
        particles (Any): The particles.
        var (Any): The var.
    Returns:
        object: Result of the operation.
    """
    key_map = {
        'total_mass': 'total_element_mass_fg',
        'total_moles': 'total_element_moles_fmol',
    }
    key = key_map.get(var, var)
    return _extract_total_values(particles, key)


class HistogramWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        self._var = self._add_combo("Data",
            ['diameter','mass','counts','moles','mass_pct','total_mass'],
            default=s.get('variable','diameter'), cb=lambda _: self._render())
        self._elem = self._add_combo("Element", ['ALL'] + self._all_elements,
            default=s.get('element', self._all_elements[0] if self._all_elements else 'ALL'),
            cb=lambda _: self._render())
        self._bins = self._add_slider("Bins", 10, 200, s.get('bins', 50), cb=lambda _: self._render())
        self._logx = self._add_toggle("Log X", s.get('log_x', False), lambda _: self._render())
        self._logy = self._add_toggle("Log Y", False, lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        var = self._var.currentText(); elem = self._elem.currentText(); nb = self._bins.value()
        if var == 'total_mass':
            data = _get_total_data(self._particles, 'total_mass'); label = 'Total particle mass'
            unit = 'fg'
        else:
            data, label = _get_element_data(self._particles, var, elem)
            unit = {'diameter':'nm','mass':'fg','counts':'counts','moles':'fmol',
                    'mass_pct':'%','mole_pct':'%'}.get(var, '')
        if not data:
            ax.text(0.5,0.5,f'No {var} data for {elem}',ha='center',va='center',
                    transform=ax.transAxes,fontsize=12,color='#999')
            self._canvas.draw(); return
        data = np.array(data)
        if self._logx.isChecked() and np.min(data) > 0:
            dp = np.log10(data); xl = f'log₁₀({var}) [{unit}]'
        else: dp = data; xl = f'{var} ({unit})'
        ax.hist(dp, bins=nb, color=PLOT_COLORS[0], alpha=0.8, edgecolor='white', linewidth=0.5)
        ax.set_xlabel(xl, fontsize=10); ax.set_ylabel('Count', fontsize=10)
        ax.set_title(f'{label} — {var} (n={len(data):,})', fontsize=11)
        if self._logy.isChecked(): ax.set_yscale('log')
        st = f'mean={np.mean(data):.2f}\nmedian={np.median(data):.2f}\nstd={np.std(data):.2f}'
        ax.text(0.98,0.95,st,transform=ax.transAxes,fontsize=8,va='top',ha='right',
                bbox=dict(boxstyle='round',facecolor='wheat',alpha=0.5))
        self._fig.tight_layout(); self._canvas.draw()


class ScatterWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        vars_ = ['diameter','mass','counts','moles','mass_pct','mole_pct']
        self._xv = self._add_combo("X", vars_, default=s.get('x','diameter'), cb=lambda _: self._render())
        self._yv = self._add_combo("Y", vars_, default=s.get('y','mass'), cb=lambda _: self._render())
        self._elem = self._add_combo("Element", self._all_elements[:20],
            default=s.get('element', self._all_elements[0] if self._all_elements else ''),
            cb=lambda _: self._render())
        self._logx = self._add_toggle("Log X", s.get('log_x',True), lambda _: self._render())
        self._logy = self._add_toggle("Log Y", s.get('log_y',True), lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        el = self._elem.currentText()
        xd, _ = _get_element_data(self._particles, self._xv.currentText(), el)
        yd, _ = _get_element_data(self._particles, self._yv.currentText(), el)
        n = min(len(xd), len(yd))
        if n == 0:
            ax.text(0.5,0.5,f'No data for {el}',ha='center',va='center',
                    transform=ax.transAxes,fontsize=12,color='#999')
            self._canvas.draw(); return
        x, y = np.array(xd[:n]), np.array(yd[:n])
        ax.scatter(x, y, c=PLOT_COLORS[0], alpha=0.5, s=8, edgecolors='none')
        ax.set_xlabel(self._xv.currentText(),fontsize=10)
        ax.set_ylabel(self._yv.currentText(),fontsize=10)
        ax.set_title(f'{el} (n={n:,})',fontsize=11)
        if self._logx.isChecked() and np.min(x)>0: ax.set_xscale('log')
        if self._logy.isChecked() and np.min(y)>0: ax.set_yscale('log')
        self._fig.tight_layout(); self._canvas.draw()


class BarChartWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        self._topn = self._add_slider("Top N",5,min(50,len(self._all_elements)),
            s.get('top_n',min(15,len(self._all_elements))), cb=lambda _: self._render())
        self._sort = self._add_combo("Sort",['Count ↓','Count ↑','Name'],
            default='Count ↓', cb=lambda _: self._render())
        self._metric = self._add_combo("Metric",['particle_count','mean_diameter','mean_mass'],
            default=s.get('metric','particle_count'), cb=lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        n = self._topn.value(); metric = self._metric.currentText()
        ec = _extract_element_counts(self._particles)
        diam = _extract_element_values(self._particles, 'element_diameter_nm')
        mass = _extract_element_values(self._particles, 'element_mass_fg')
        items = []
        for el, cnt in ec.items():
            if metric == 'particle_count': val = cnt
            elif metric == 'mean_diameter': val = np.mean(diam[el]) if el in diam and diam[el] else 0
            elif metric == 'mean_mass': val = np.mean(mass[el]) if el in mass and mass[el] else 0
            else: val = cnt
            items.append((el, val))
        sm = self._sort.currentText()
        if sm == 'Count ↓': items.sort(key=lambda x: -x[1])
        elif sm == 'Count ↑': items.sort(key=lambda x: x[1])
        else: items.sort(key=lambda x: x[0])
        items = items[:n]
        labels = [x[0] for x in items]; values = [x[1] for x in items]
        colors = [PLOT_COLORS[i%len(PLOT_COLORS)] for i in range(len(items))]
        bars = ax.barh(range(len(items)), values, color=colors, edgecolor='white', linewidth=0.5)
        ax.set_yticks(range(len(items))); ax.set_yticklabels(labels, fontsize=9); ax.invert_yaxis()
        unit = {'particle_count':'particles','mean_diameter':'nm','mean_mass':'fg'}
        ax.set_xlabel(f'{metric.replace("_"," ").title()} ({unit.get(metric,"")})', fontsize=10)
        ax.set_title(f'Top {n} elements', fontsize=11)
        for i, (bar, val) in enumerate(zip(bars, values)):
            fmt = f'{val:,.0f}' if metric == 'particle_count' else f'{val:.1f}'
            ax.text(bar.get_width() + max(values)*0.01, i, fmt, va='center', fontsize=8)
        self._fig.tight_layout(); self._canvas.draw()


class BoxPlotWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        self._var = self._add_combo("Variable",['diameter','mass','counts','moles'],
            default=s.get('variable','diameter'), cb=lambda _: self._render())
        self._topn = self._add_slider("Elements",3,min(15,len(self._all_elements)),
            s.get('top_n',min(8,len(self._all_elements))), cb=lambda _: self._render())
        self._logy = self._add_toggle("Log Y", s.get('log_y',False), lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        var = self._var.currentText(); n = self._topn.value()
        field = {'diameter':'element_diameter_nm','mass':'element_mass_fg',
                 'counts':'elements','moles':'element_moles_fmol'}.get(var,'elements')
        data_dict = _extract_element_values(self._particles, field)
        ec = _extract_element_counts(self._particles)
        top = sorted(ec.items(), key=lambda x: -x[1])[:n]
        labels = [el for el, _ in top if el in data_dict and data_dict[el]]
        box_data = [data_dict[el] for el in labels]
        if not box_data:
            ax.text(0.5,0.5,f'No {var} data',ha='center',va='center',transform=ax.transAxes,fontsize=12,color='#999')
            self._canvas.draw(); return
        bp = ax.boxplot(box_data, labels=labels, patch_artist=True, showfliers=True,
                        flierprops=dict(marker='.', markersize=2, alpha=0.3))
        for i, patch in enumerate(bp['boxes']):
            patch.set_facecolor(PLOT_COLORS[i%len(PLOT_COLORS)]); patch.set_alpha(0.7)
        ax.set_ylabel(var.capitalize(), fontsize=10)
        ax.set_title(f'{var.capitalize()} by element', fontsize=11)
        ax.tick_params(axis='x', rotation=45)
        if self._logy.isChecked(): ax.set_yscale('log')
        self._fig.tight_layout(); self._canvas.draw()


class HeatmapWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        self._topn = self._add_slider("Elements",5,min(20,len(self._all_elements)),
            s.get('top_n',min(12,len(self._all_elements))), cb=lambda _: self._render())
        self._norm = self._add_toggle("Normalize", True, lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        n = self._topn.value()
        ec = _extract_element_counts(self._particles)
        top = [el for el, _ in sorted(ec.items(), key=lambda x: -x[1])[:n]]
        mat = np.zeros((n,n), dtype=float)
        idx = {el:i for i, el in enumerate(top)}
        for p in self._particles:
            present = [el for el in top if _safe_positive(p.get('elements',{}).get(el, 0))]
            for i, a in enumerate(present):
                for b in present[i:]:
                    mat[idx[a]][idx[b]] += 1
                    if a != b: mat[idx[b]][idx[a]] += 1
        if self._norm.isChecked() and np.max(mat) > 0:
            diag = np.diag(mat).copy(); diag[diag==0] = 1
            for i in range(n):
                for j in range(n): mat[i][j] /= min(diag[i], diag[j])
        im = ax.imshow(mat, cmap='YlOrRd', aspect='auto')
        ax.set_xticks(range(n)); ax.set_xticklabels(top, rotation=45, ha='right', fontsize=8)
        ax.set_yticks(range(n)); ax.set_yticklabels(top, fontsize=8)
        ax.set_title('Element co-occurrence', fontsize=11)
        self._fig.colorbar(im, ax=ax, shrink=0.8)
        self._fig.tight_layout(); self._canvas.draw()


class PieChartWidget(InteractiveFigureWidget):
    def _build_controls(self):
        s = self._spec
        self._topn = self._add_slider("Slices",5,min(20,len(self._all_elements)),
            s.get('top_n',min(10,len(self._all_elements))), cb=lambda _: self._render())
        self._metric = self._add_combo("Metric",['particle_count','total_mass'],
            default='particle_count', cb=lambda _: self._render())
        self._ctrl_layout.addStretch()

    def _render(self):
        self._fig.clear(); ax = self._fig.add_subplot(111)
        n = self._topn.value(); metric = self._metric.currentText()
        ec = _extract_element_counts(self._particles)
        if metric == 'total_mass':
            mass = _extract_element_values(self._particles, 'element_mass_fg')
            items = [(el, sum(mass.get(el,[0]))) for el in ec]
        else: items = list(ec.items())
        items.sort(key=lambda x: -x[1]); top = items[:n]
        others = sum(v for _, v in items[n:])
        if others > 0: top.append(('Others', others))
        labels = [x[0] for x in top]; values = [x[1] for x in top]
        colors = [PLOT_COLORS[i%len(PLOT_COLORS)] for i in range(len(top))]
        ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%',
               startangle=90, pctdistance=0.85, textprops={'fontsize':9})
        ax.set_title(f'Composition by {metric.replace("_"," ")}', fontsize=11)
        self._fig.tight_layout(); self._canvas.draw()


WIDGET_MAP = {
    'histogram': HistogramWidget, 'scatter': ScatterWidget,
    'bar': BarChartWidget, 'box': BoxPlotWidget,
    'heatmap': HeatmapWidget, 'pie': PieChartWidget,
}

def build_figure_widget(spec, particles, dc):
    """
    Args:
        spec (Any): The spec.
        particles (Any): The particles.
        dc (Any): The dc.
    Returns:
        object: Result of the operation.
    """
    cls = WIDGET_MAP.get(spec.get('type','histogram'), HistogramWidget)
    return cls(spec, particles, dc)


class FigureCarousel(QFrame):
    def __init__(self):
        super().__init__()
        self._slides = []; self._current = -1
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)
        self._nav = QFrame(); nl = QHBoxLayout(self._nav); nl.setContentsMargins(12,6,12,6)
        self._prev = QPushButton("◀"); self._prev.setFixedSize(32,32); self._prev.clicked.connect(self._go_prev); nl.addWidget(self._prev)
        self._page = QLabel("No figures yet"); self._page.setAlignment(Qt.AlignCenter); nl.addWidget(self._page, stretch=1)
        self._next = QPushButton("▶"); self._next.setFixedSize(32,32); self._next.clicked.connect(self._go_next); nl.addWidget(self._next)
        lo.addWidget(self._nav)
        self._stack = QStackedWidget(); lo.addWidget(self._stack, stretch=1)
        self._empty = QLabel("Ask for a figure:\n\"histogram of 56Fe diameters\"\n\"bar chart of elements\"\n\"scatter diameter vs mass for 208Pb\"")
        self._empty.setAlignment(Qt.AlignCenter); self._empty.setWordWrap(True)
        self._stack.addWidget(self._empty); self._upd_nav(); self.apply_theme()

    def add_figure(self, w):
        """
        Args:
            w (Any): The w.
        """
        self._slides.append(w); self._stack.addWidget(w)
        self._current = len(self._slides)-1; self._stack.setCurrentWidget(w); self._upd_nav()

    def _go_prev(self):
        if self._current > 0: self._current -= 1; self._stack.setCurrentWidget(self._slides[self._current]); self._upd_nav()
    def _go_next(self):
        if self._current < len(self._slides)-1: self._current += 1; self._stack.setCurrentWidget(self._slides[self._current]); self._upd_nav()

    def _upd_nav(self):
        n = len(self._slides)
        if n == 0: self._page.setText("No figures yet"); self._prev.setEnabled(False); self._next.setEnabled(False)
        else: self._page.setText(f"Figure {self._current+1} / {n}"); self._prev.setEnabled(self._current>0); self._next.setEnabled(self._current<n-1)

    def clear(self):
        for w in self._slides: self._stack.removeWidget(w); w.deleteLater()
        self._slides.clear(); self._current = -1; self._upd_nav()

    def apply_theme(self):
        self.setStyleSheet(f"QFrame{{background:{Theme.c('carousel_bg')};}}")
        self._nav.setStyleSheet(f"QFrame{{background:{Theme.c('bg_secondary')};border-bottom:1px solid {Theme.c('border')};}}")
        self._page.setStyleSheet(f"color:{Theme.c('text')};font-size:13px;font-weight:600;")
        bs = f"QPushButton{{background:{Theme.c('surface')};border:1px solid {Theme.c('border')};border-radius:16px;color:{Theme.c('text')};font-size:14px;}}QPushButton:hover{{background:{Theme.c('surface_hover')};}}QPushButton:disabled{{color:{Theme.c('text_tertiary')};}}"
        self._prev.setStyleSheet(bs); self._next.setStyleSheet(bs)
        self._empty.setStyleSheet(f"color:{Theme.c('text_secondary')};font-size:13px;")
        for w in self._slides:
            if hasattr(w,'apply_theme'): w.apply_theme()


_SAFE_BUILTINS = {
    'abs':abs,'all':all,'any':any,'bool':bool,'dict':dict,'enumerate':enumerate,
    'filter':filter,'float':float,'format':format,'int':int,'isinstance':isinstance,
    'len':len,'list':list,'map':map,'max':max,'min':min,'print':print,'range':range,
    'round':round,'set':set,'sorted':sorted,'str':str,'sum':sum,'tuple':tuple,
    'type':type,'zip':zip,'True':True,'False':False,'None':None,
    'ValueError':ValueError,'TypeError':TypeError,'KeyError':KeyError,'Exception':Exception,
}
_CODE_RE = re.compile(r'```python\s*\n(.*?)```', re.DOTALL)
_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
_JSON_VIZ_RE = re.compile(r'```json-viz\s*\n(.*?)```', re.DOTALL)
_JSON_RE = re.compile(r'```json\s*\n(.*?)```', re.DOTALL)
_IMPORT_RE = re.compile(r'^\s*(?:import\s+\w+|from\s+\w+\s+import\s+.+)\s*$', re.MULTILINE)

def _sanitize_code(code):
    """
    Args:
        code (Any): The code.
    Returns:
        object: Result of the operation.
    """
    code = _IMPORT_RE.sub('', code)
    code = re.sub(r'^\s*plt\.show\(\)\s*$','',code,flags=re.MULTILINE)
    code = re.sub(r'^\s*plt\.savefig\(.*?\)\s*$','',code,flags=re.MULTILINE)
    return code.strip()

def _execute_raw_code(code, particles, dc, return_fig=False):
    """
    Args:
        code (Any): The code.
        particles (Any): The particles.
        dc (Any): The dc.
        return_fig (Any): The return fig.
    Returns:
        tuple: Result of the operation.
    """
    code = _sanitize_code(code)
    bs = _extract_by_sample(particles, dc) if dc else {}
    ns = {
        '__builtins__': _SAFE_BUILTINS, 'np':np, 'plt':plt, 'Figure':MplFigure,
        'math':math, 'Counter':Counter, 'defaultdict':defaultdict,
        'particles':particles,
        'elements': _extract_element_values(particles, 'elements'),
        'element_counts': _extract_element_counts(particles),
        'masses': _extract_element_values(particles, 'element_mass_fg'),
        'diameters': _extract_element_values(particles, 'element_diameter_nm'),
        'moles': _extract_element_values(particles, 'element_moles_fmol'),
        'mass_pct': _extract_element_values(particles, 'mass_percentages'),
        'mole_pct': _extract_element_values(particles, 'mole_percentages'),
        'total_masses': _extract_total_values(particles, 'total_element_mass_fg'),
        'total_moles': _extract_total_values(particles, 'total_element_moles_fmol'),
        'sample_names': dc.get('sample_names',[]) if dc else [],
        'sample_name': dc.get('sample_name','Sample') if dc else 'Sample',
        'by_sample':bs, 'data_context':dc or {}, 'COLORS':PLOT_COLORS,
    }
    try:
        from scipy import stats; ns['stats'] = stats
    except: pass
    err = [None]
    def _run():
        try: plt.close('all'); exec(code, ns)
        except Exception as e: err[0] = f"{type(e).__name__}: {e}"
    t = threading.Thread(target=_run, daemon=True); t.start(); t.join(timeout=CODE_EXEC_TIMEOUT)
    if t.is_alive(): plt.close('all'); return None, "Timeout"
    if err[0]: plt.close('all'); return None, err[0]
    fig = plt.gcf()
    if not fig.get_axes(): plt.close(fig); return None, "No figure."
    if return_fig: return fig, None
    fig.set_facecolor('white'); fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); buf.seek(0)
    img = QImage(); img.loadFromData(buf.getvalue())
    return (QPixmap.fromImage(img) if not img.isNull() else None), None


def _md_to_html(text):
    """
    Args:
        text (Any): Text string.
    Returns:
        object: Result of the operation.
    """
    lines = text.split('\n'); html = []; in_code = False; in_list = False; buf = []
    cbg=Theme.c('code_bg'); cfg=Theme.c('code_text'); ac=Theme.c('accent'); bd=Theme.c('border')
    ibg=Theme.c('bg_tertiary')
    for line in lines:
        if line.strip().startswith('```') and not in_code:
            if in_list: html.append('</ul>'); in_list=False
            in_code=True; buf=[]; continue
        if line.strip().startswith('```') and in_code:
            in_code=False
            html.append(f'<div style="background:{cbg};color:{cfg};padding:10px 14px;border-radius:8px;font-family:monospace;font-size:12px;margin:6px 0;">{"<br>".join(buf)}</div>')
            continue
        if in_code: buf.append(line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')); continue
        s=line.strip()
        if s.startswith('### '): html.append(f'<div style="font-size:14px;font-weight:700;margin:10px 0 4px;color:{ac};">{_ifmt(s[4:],ibg)}</div>'); continue
        if s.startswith('## '): html.append(f'<div style="font-size:15px;font-weight:700;margin:12px 0 4px;">{_ifmt(s[3:],ibg)}</div>'); continue
        if s.startswith('# '): html.append(f'<div style="font-size:16px;font-weight:700;margin:14px 0 6px;">{_ifmt(s[2:],ibg)}</div>'); continue
        if s.startswith('- ') or s.startswith('* '):
            if not in_list: html.append('<ul style="margin:4px 0 4px 18px;padding:0;">'); in_list=True
            html.append(f'<li style="margin:2px 0;">{_ifmt(s[2:],ibg)}</li>'); continue
        if in_list: html.append('</ul>'); in_list=False
        if not s: html.append('<div style="height:6px;"></div>'); continue
        html.append(f'<div style="margin:2px 0;">{_ifmt(s,ibg)}</div>')
    if in_list: html.append('</ul>')
    return ''.join(html)

def _ifmt(t, ibg='#F3F4F6'):
    """
    Args:
        t (Any): The t.
        ibg (Any): The ibg.
    Returns:
        object: Result of the operation.
    """
    t=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',t)
    t=re.sub(r'\*(.+?)\*',r'<i>\1</i>',t)
    t=re.sub(r'`(.+?)`',rf'<code style="background:{ibg};padding:1px 5px;border-radius:3px;font-family:monospace;font-size:12px;">\1</code>',t)
    return t

def _trim_history(h, max_t):
    """
    Args:
        h (Any): The h.
        max_t (Any): The max t.
    Returns:
        object: Result of the operation.
    """
    if not h: return h
    total=0; cut=len(h)
    for i in range(len(h)-1,-1,-1):
        total+=max(1,int(len(h[i].get('content',''))/CHARS_PER_TOKEN))
        if total>max_t: cut=i+1; break
    else: cut=0
    return h[min(cut,max(0,len(h)-2)):]


def _build_system_prompt(dc, backend='claude'):
    """
    Args:
        dc (Any): The dc.
        backend (Any): The backend.
    Returns:
        object: Result of the operation.
    """
    intro = """You are an expert analytical chemist specialising in spICP-ToF-MS and nanoparticle characterisation.

YOUR PRIMARY JOB IS TO TALK AND EXPLAIN.
Answer questions in plain text first. Be quantitative — cite real numbers.
Only create figures when the user explicitly asks (e.g. "plot", "chart", "histogram", "show me").

★ CRITICAL DATA STRUCTURE
Element labels are: '208Pb', '56Fe', '63Cu', '109Ag', '118Sn', '209Bi'
  Format: mass_number + element_symbol (NO space). Example: '208Pb' not 'Pb 208'

Each particle is a dict with these keys:
  elements:            {'208Pb': 137.2, '56Fe': 129.5}     ← signal counts
  element_mass_fg:     {'208Pb': 1.62}                      ← mass in fg
  element_diameter_nm: {'208Pb': 64.8}                      ← diameter in nm
  element_moles_fmol:  {'208Pb': 0.0078}                    ← moles in fmol
  particle_mass_fg:    {'208Pb': 1.62}                      ← DICT not scalar!
  particle_diameter_nm:{'208Pb': 64.8}                      ← DICT not scalar!
  totals:              {'total_element_mass_fg': 4.3, ...}  ← aggregated
  mass_percentages:    {'206Pb': 33.0, '208Pb': 37.6}
  mole_percentages:    same structure
  source_sample:       'sample_name'
  start_time / end_time: float (seconds)

IMPORTANT: particle_diameter_nm and particle_mass_fg are dicts, NOT scalars.
To get total mass use: totals['total_element_mass_fg']"""

    if backend == 'claude':
        fig_instructions = """

FIGURES — use ```json-viz blocks when user asks for a chart/plot/figure.
The app renders them as interactive widgets with sliders, dropdowns, toggles.

Supported types:
  histogram: {"type":"histogram","title":"...","element":"208Pb","variable":"diameter","bins":50,"log_x":false}
  scatter:   {"type":"scatter","title":"...","x":"diameter","y":"mass","element":"56Fe","log_x":true,"log_y":true}
  bar:       {"type":"bar","title":"...","top_n":15,"metric":"particle_count"}
  box:       {"type":"box","title":"...","variable":"diameter","top_n":8,"log_y":false}
  heatmap:   {"type":"heatmap","title":"...","top_n":12}
  pie:       {"type":"pie","title":"...","top_n":10}

Variables: diameter, mass, counts, moles, mass_pct, mole_pct, total_mass
Metrics (bar): particle_count, mean_diameter, mean_mass
You can output MULTIPLE json-viz blocks for comparison.

If json-viz can't do it, use ```python code blocks (same variables as Ollama below)."""
    else:
        fig_instructions = """

FIGURES — write ```python code blocks when user asks for a chart/plot/figure.
The app executes your code in a sandbox with these pre-loaded variables:

  particles        → list of particle dicts (the raw data)
  elements         → {'208Pb': [137.2, ...], '56Fe': [129.5, ...]}  counts per element
  element_counts   → {'208Pb': 1200, '56Fe': 800}                   how many particles have each
  masses           → {'208Pb': [1.62, ...]}                          mass values per element
  diameters        → {'208Pb': [64.8, ...]}                          diameters per element
  moles            → {'208Pb': [0.0078, ...]}                        moles per element
  mass_pct         → {'208Pb': [37.6, ...]}                          mass % per element
  mole_pct         → {'208Pb': [37.6, ...]}                          mole % per element
  total_masses     → [4.3, 2.8, ...]                                 total mass per particle (flat list)
  total_moles      → [0.02, ...]                                     total moles per particle (flat list)
  sample_names     → ['sample1', 'sample2']
  sample_name      → 'sample1' (single sample mode)
  by_sample        → {'sample1': [particles...]}                     grouped by source
  COLORS           → ['#663399', '#2E86AB', ...]                     colour palette

  np, plt, math, Counter, defaultdict, stats (scipy.stats) are available.

RULES:
- Do NOT write import statements — everything is already loaded.
- Do NOT call plt.show() or plt.savefig() — the app handles it.
- Always start with plt.figure() or fig, ax = plt.subplots()
- Use COLORS for consistent colouring.
- Element labels are like '208Pb', '56Fe' — use list(elements.keys()) to see them all.

EXAMPLE — histogram of 56Fe diameters:
```python
fig, ax = plt.subplots(figsize=(8, 5))
data = diameters.get('56Fe', [])
if data:
    ax.hist(data, bins=50, color=COLORS[0], alpha=0.8, edgecolor='white')
    ax.set_xlabel('Diameter (nm)')
    ax.set_ylabel('Count')
    ax.set_title(f'56Fe diameter distribution (n={len(data):,})')
    ax.axvline(np.mean(data), color='red', linestyle='--', label=f'mean={np.mean(data):.1f} nm')
    ax.legend()
```

EXAMPLE — bar chart of element frequencies:
```python
fig, ax = plt.subplots(figsize=(8, 5))
top = sorted(element_counts.items(), key=lambda x: -x[1])[:15]
labels, values = zip(*top)
ax.barh(range(len(top)), values, color=[COLORS[i%len(COLORS)] for i in range(len(top))])
ax.set_yticks(range(len(top)))
ax.set_yticklabels(labels)
ax.invert_yaxis()
ax.set_xlabel('Particle count')
ax.set_title('Top 15 elements by frequency')
```

EXAMPLE — compare Fe mass across two samples:
```python
fig, ax = plt.subplots(figsize=(8, 5))
for i, (name, parts) in enumerate(by_sample.items()):
    fe_mass = [p.get('element_mass_fg', {}).get('56Fe', 0) for p in parts if p.get('element_mass_fg', {}).get('56Fe', 0) > 0]
    if fe_mass:
        ax.hist(fe_mass, bins=30, alpha=0.6, color=COLORS[i], label=f'{name} (n={len(fe_mass)})')
ax.set_xlabel('56Fe mass (fg)')
ax.set_ylabel('Count')
ax.set_title('56Fe mass distribution by sample')
ax.legend()
```"""

    base = intro + fig_instructions

    if not dc: return base + "\n\nSTATUS: No data loaded."
    particles = dc.get('particle_data', [])
    n = len(particles)
    if n == 0: return base + "\n\nSTATUS: 0 particles."

    ec = _extract_element_counts(particles)
    combos = _extract_combinations(particles)
    top_e = sorted(ec.items(), key=lambda x: -x[1])
    top_c = sorted(combos.items(), key=lambda x: -x[1])
    single = sum(1 for p in particles if sum(1 for v in p.get('elements',{}).values() if _safe_positive(v))==1)

    ctx = f"\n\n━━━ DATASET ━━━\n"
    dt = dc.get('type','')
    if dt == 'sample_data': ctx += f"Sample: {dc.get('sample_name','?')}\n"
    elif dt == 'multiple_sample_data':
        names = dc.get('sample_names',[]); ctx += f"Samples ({len(names)}): {', '.join(str(n) for n in names[:8])}\n"

    ctx += (f"Particles: {n:,} (single-element: {single:,}, multi-element: {n-single:,})\n"
            f"Unique elements: {len(ec)}\n\nFREQUENCIES:\n")
    for el, cnt in top_e[:15]:
        ctx += f"  {el:12s} {cnt:6,} ({cnt/n*100:.1f}%)\n"
    if len(top_e) > 15: ctx += f"  ... +{len(top_e)-15} more\n"

    ctx += "\nCOMBINATIONS:\n"
    for combo, cnt in top_c[:8]:
        ctx += f"  {cnt:6,} ({cnt/n*100:.1f}%)  {combo}\n"

    ss = min(SAMPLE_PARTICLES_COUNT, n)
    sample = particles[:ss] if n <= ss else [particles[int(i*n/ss)] for i in range(ss)]
    ctx += f"\n━━━ SAMPLE ({ss} particles) ━━━\n"
    for i, p in enumerate(sample[:3]):
        ctx += f"P{i}: {json.dumps(p, indent=2, default=str)}\n\n"
    for p in sample[3:]:
        compact = {}
        for k, v in p.items():
            if isinstance(v, dict):
                trimmed = {ek: round(ev,2) if isinstance(ev,float) else ev
                           for ek, ev in v.items() if _safe_positive(ev) if isinstance(ev,(int,float))}
                if trimmed: compact[k] = trimmed
            elif v and v != 0:
                compact[k] = round(v,2) if isinstance(v,float) else v
        ctx += json.dumps(compact, default=str) + "\n"

    tm = _extract_total_values(particles, 'total_element_mass_fg')
    if tm: ctx += f"\nTotal mass: n={len(tm)}, mean={np.mean(tm):.2f}, median={np.median(tm):.2f} fg\n"
    diam = _extract_element_values(particles, 'element_diameter_nm')
    if diam:
        ctx += "Per-element diameters (top 5):\n"
        for el, _ in top_e[:5]:
            if el in diam and diam[el]:
                v = diam[el]; ctx += f"  {el:12s}: n={len(v)}, mean={np.mean(v):.1f}, std={np.std(v):.1f} nm\n"

    return base + ctx


class StreamWorker(QThread):
    """Unified streaming worker for both Ollama and Claude API."""
    token_received = Signal(str)
    stream_done = Signal(str)
    error_occurred = Signal(str)
    stats_update = Signal(int, float)
    usage_update = Signal(int, int)

    def __init__(self, backend, msgs, sys_prompt, config):
        """
        Args:
            backend (Any): The backend.
            msgs (Any): The msgs.
            sys_prompt (Any): The sys prompt.
            config (Any): Configuration dictionary.
        """
        super().__init__()
        self.backend = backend
        self.msgs = msgs; self.sys = sys_prompt; self.cfg = config
        self._cancelled = threading.Event(); self._resp = None

    def stop(self):
        self._cancelled.set()
        if self._resp:
            try: self._resp.close()
            except: pass

    def run(self):
        if self.backend == 'claude': self._run_claude()
        else: self._run_ollama()

    def _run_claude(self):
        try:
            self._resp = requests.post(ANTHROPIC_API_URL,
                headers={"x-api-key":self.cfg['api_key'],"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":self.cfg.get('model',ANTHROPIC_MODEL),"max_tokens":4096,
                      "system":self.sys,"messages":self.msgs,"stream":True},
                timeout=300, stream=True)
            if self._resp.status_code == 429:
                self.error_occurred.emit("Rate limited — wait 30s and retry."); return
            if self._resp.status_code != 200:
                try: err=self._resp.json().get('error',{}).get('message','')
                except: err=''
                self.error_occurred.emit(f"HTTP {self._resp.status_code}: {err}"); return
            full=[]; tc=0; t0=time.monotonic(); it=0; ot=0
            for line in self._resp.iter_lines(decode_unicode=True):
                if self._cancelled.is_set(): break
                if not line or not line.startswith('data: '): continue
                ds=line[6:]
                if ds.strip()=='[DONE]': break
                try: ev=json.loads(ds)
                except: continue
                et=ev.get('type','')
                if et=='content_block_delta':
                    d=ev.get('delta',{})
                    if d.get('type')=='text_delta':
                        txt=d.get('text','')
                        if txt: full.append(txt); tc+=1; self.token_received.emit(txt)
                        if tc%10==0: self.stats_update.emit(tc, time.monotonic()-t0)
                elif et=='message_delta': ot=ev.get('usage',{}).get('output_tokens',0)
                elif et=='message_start': it=ev.get('message',{}).get('usage',{}).get('input_tokens',0)
            complete=''.join(full).strip()
            if self._cancelled.is_set():
                self.stream_done.emit((complete+"\n\n*[Stopped]*") if complete else "*[Cancelled]*")
            elif complete:
                self.stats_update.emit(tc, time.monotonic()-t0)
                if it or ot: self.usage_update.emit(it, ot)
                self.stream_done.emit(complete)
            else: self.error_occurred.emit("Empty response.")
        except requests.exceptions.ConnectionError:
            if not self._cancelled.is_set(): self.error_occurred.emit("Cannot connect to Claude API.")
        except Exception as e:
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _run_ollama(self):
        try:
            messages = [{"role":"system","content":self.sys}] + self.msgs
            self._resp = requests.post(OLLAMA_CHAT, json={
                "model":self.cfg.get('model','deepseek-r1:14b'),
                "messages":messages, "stream":True,
                "options":{"temperature":self.cfg.get('temperature',0.6),
                           "num_ctx":self.cfg.get('num_ctx',8192),"num_predict":4096},
            }, timeout=300, stream=True)
            if self._resp.status_code != 200:
                self.error_occurred.emit(f"Ollama HTTP {self._resp.status_code}"); return
            full=[]; tc=0; t0=time.monotonic()
            for line in self._resp.iter_lines(decode_unicode=True):
                if self._cancelled.is_set(): break
                if not line: continue
                try: chunk=json.loads(line)
                except: continue
                content=chunk.get('message',{}).get('content','')
                if content: full.append(content); tc+=1; self.token_received.emit(content)
                if tc%10==0: self.stats_update.emit(tc, time.monotonic()-t0)
                if chunk.get('done',False): break
            complete=''.join(full).strip()
            if self._cancelled.is_set():
                self.stream_done.emit((complete+"\n\n*[Stopped]*") if complete else "*[Cancelled]*")
            elif complete:
                self.stats_update.emit(tc, time.monotonic()-t0)
                self.stream_done.emit(complete)
            else: self.error_occurred.emit("Empty response.")
        except requests.exceptions.ConnectionError:
            if not self._cancelled.is_set(): self.error_occurred.emit("Cannot connect to Ollama. Run: ollama serve")
        except Exception as e:
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))


class BackendDialog(QDialog):
    def __init__(self, current_cfg, parent=None):
        """
        Args:
            current_cfg (Any): The current cfg.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("AI Backend Settings"); self.setMinimumWidth(500)
        self._cfg = dict(current_cfg)
        lo = QVBoxLayout(self); lo.setSpacing(12)
        lo.addWidget(QLabel("Choose AI Backend"))

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Backend:"))
        self._backend = QComboBox()
        self._backend.addItems(["Claude API (recommended)","Ollama (local/free)"])
        if current_cfg.get('backend') == 'ollama': self._backend.setCurrentIndex(1)
        self._backend.currentIndexChanged.connect(self._on_backend)
        hl.addWidget(self._backend); lo.addLayout(hl)

        self._claude_frame = QFrame(); cf = QVBoxLayout(self._claude_frame); cf.setContentsMargins(0,0,0,0)
        cf.addWidget(QLabel("API Key (stays in memory only):"))
        self._key = QLineEdit(); self._key.setPlaceholderText("sk-ant-api03-...")
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setText(current_cfg.get('api_key',''))
        cf.addWidget(self._key)
        self._claude_status = QLabel(""); cf.addWidget(self._claude_status)
        tb = QPushButton("Test Connection"); tb.clicked.connect(self._test_claude); cf.addWidget(tb)
        lo.addWidget(self._claude_frame)

        self._ollama_frame = QFrame(); of = QVBoxLayout(self._ollama_frame); of.setContentsMargins(0,0,0,0)
        mh = QHBoxLayout(); mh.addWidget(QLabel("Model:"))
        self._model = QComboBox(); self._model.setEditable(True)
        self._model.addItems(['deepseek-r1:14b','deepseek-r1:7b','qwen2.5:14b','llama3.2'])
        self._model.setCurrentText(current_cfg.get('model','deepseek-r1:14b'))
        mh.addWidget(self._model); of.addLayout(mh)
        self._ollama_status = QLabel(""); of.addWidget(self._ollama_status)
        otb = QPushButton("Test Ollama"); otb.clicked.connect(self._test_ollama); of.addWidget(otb)
        lo.addWidget(self._ollama_frame)

        self._on_backend(self._backend.currentIndex())

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lo.addWidget(btns)

    def _on_backend(self, idx):
        """
        Args:
            idx (Any): The idx.
        """
        is_claude = idx == 0
        self._claude_frame.setVisible(is_claude)
        self._ollama_frame.setVisible(not is_claude)

    def _test_claude(self):
        k = self._key.text().strip()
        if not k.startswith('sk-ant-'): self._claude_status.setText("⚠ Key should start with sk-ant-"); return
        self._claude_status.setText("Testing…")
        try:
            r = requests.post(ANTHROPIC_API_URL, headers={
                "x-api-key":k,"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":ANTHROPIC_MODEL,"max_tokens":10,"messages":[{"role":"user","content":"Hi"}]},timeout=15)
            if r.status_code == 200: self._claude_status.setText("✓ Connected!")
            else: self._claude_status.setText(f"✗ HTTP {r.status_code}")
        except Exception as e: self._claude_status.setText(f"✗ {e}")

    def _test_ollama(self):
        self._ollama_status.setText("Testing…")
        try:
            r = requests.get(OLLAMA_TAGS, timeout=5)
            if r.status_code == 200:
                models = [m.get('name','') for m in r.json().get('models',[])]
                self._ollama_status.setText(f"✓ {len(models)} models: {', '.join(models[:5])}")
                self._model.clear(); self._model.addItems(models)
            else: self._ollama_status.setText("✗ Ollama not responding")
        except: self._ollama_status.setText("✗ Cannot connect. Run: ollama serve")

    def get_config(self):
        """
        Returns:
            dict: Result of the operation.
        """
        is_claude = self._backend.currentIndex() == 0
        return {
            'backend': 'claude' if is_claude else 'ollama',
            'api_key': self._key.text().strip() if is_claude else '',
            'model': ANTHROPIC_MODEL if is_claude else self._model.currentText(),
            'temperature': 0.6,
            'num_ctx': 8192,
        }


class TextBubble(QFrame):
    def __init__(self, text, is_user=False):
        """
        Args:
            text (Any): Text string.
            is_user (Any): The is user.
        """
        super().__init__()
        self._text=text; self._iu=is_user
        self.setContentsMargins(0,4,0,4)
        lo=QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        w=QHBoxLayout(); w.setContentsMargins(0,0,0,0)
        self._b=QFrame(); bl=QVBoxLayout(self._b); bl.setContentsMargins(14,10,14,10)
        self._l=QLabel(); self._l.setWordWrap(True)
        if not is_user: self._l.setTextFormat(Qt.RichText); self._l.setOpenExternalLinks(True)
        bl.addWidget(self._l)
        if is_user: w.addStretch()
        w.addWidget(self._b)
        if not is_user: w.addStretch()
        lo.addLayout(w); self.apply_theme()

    def apply_theme(self):
        if self._iu:
            bg=Theme.c('user_bubble'); fg=Theme.c('user_text')
            self._b.setStyleSheet(f"QFrame{{background:{bg};border-radius:16px;border-bottom-right-radius:4px;}}")
            self._l.setStyleSheet(f"color:{fg};font-size:14px;"); self._l.setText(self._text)
        else:
            bg=Theme.c('ai_bubble'); fg=Theme.c('ai_text')
            self._b.setStyleSheet(f"QFrame{{background:{bg};border-radius:16px;border-bottom-left-radius:4px;}}")
            self._l.setStyleSheet(f"color:{fg};font-size:14px;line-height:1.5;"); self._l.setText(_md_to_html(self._text))

class StreamBubble(QFrame):
    def __init__(self):
        super().__init__()
        self._raw=""; self._pend=[]
        self.setContentsMargins(0,4,0,4)
        lo=QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        w=QHBoxLayout(); w.setContentsMargins(0,0,0,0)
        self._b=QFrame(); bl=QVBoxLayout(self._b); bl.setContentsMargins(14,10,14,10)
        self._l=QLabel(); self._l.setWordWrap(True); self._l.setTextFormat(Qt.RichText)
        bl.addWidget(self._l); w.addWidget(self._b); w.addStretch(); lo.addLayout(w)
        self._t=QTimer(self); self._t.setInterval(STREAM_RENDER_INTERVAL_MS)
        self._t.timeout.connect(self._flush); self.apply_theme()

    def append(self, tok):
        """
        Args:
            tok (Any): The tok.
        """
        self._pend.append(tok)
        if not self._t.isActive(): self._t.start()

    def _flush(self):
        if not self._pend: self._t.stop(); return
        self._raw+=''.join(self._pend); self._pend.clear()
        d=_THINK_RE.sub('',self._raw).strip()
        d=_JSON_VIZ_RE.sub('[Figure...]',d); d=_JSON_RE.sub('[ ...]',d)
        self._l.setText(_md_to_html(d)+f'<span style="color:{Theme.c("accent")};">▊</span>')

    def finalise(self):
        self._t.stop()
        if self._pend: self._raw+=''.join(self._pend); self._pend.clear()
        d=_THINK_RE.sub('',self._raw).strip()
        d=_JSON_VIZ_RE.sub('',d); d=_JSON_RE.sub('',d); d=_CODE_RE.sub('',d)
        self._l.setText(_md_to_html(d.strip()))

    def get_text(self):
        """
        Returns:
            object: Result of the operation.
        """
        if self._pend: self._raw+=''.join(self._pend); self._pend.clear()
        return self._raw

    def apply_theme(self):
        bg=Theme.c('ai_bubble'); fg=Theme.c('ai_text')
        self._b.setStyleSheet(f"QFrame{{background:{bg};border-radius:16px;border-bottom-left-radius:4px;}}")
        self._l.setStyleSheet(f"color:{fg};font-size:14px;line-height:1.5;")

class FigureBubble(QFrame):
    def __init__(self, pix):
        """
        Args:
            pix (Any): The pix.
        """
        super().__init__()
        self.setContentsMargins(0,4,0,4)
        lo=QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        c=QFrame(); cl=QVBoxLayout(c); cl.setContentsMargins(8,8,8,6)
        img=QLabel(); img.setAlignment(Qt.AlignCenter)
        img.setPixmap(pix.scaledToWidth(min(600,pix.width()),Qt.SmoothTransformation))
        cl.addWidget(img); lo.addWidget(c)
        c.setStyleSheet(f"QFrame{{background:{Theme.c('fig_bg')};border:1px solid {Theme.c('fig_border')};border-radius:12px;}}")
    def apply_theme(self): pass

class ErrorBubble(QFrame):
    def __init__(self, err):
        """
        Args:
            err (Any): The err.
        """
        super().__init__()
        self.setContentsMargins(0,4,0,4)
        lo=QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        c=QFrame(); cl=QVBoxLayout(c); cl.setContentsMargins(12,8,12,8)
        cl.addWidget(QLabel(f"⚠ {err}")); lo.addWidget(c)
        c.setStyleSheet(f"QFrame{{background:{Theme.c('error_bg')};border:1px solid {Theme.c('error_border')};border-radius:12px;}}")
    def apply_theme(self): pass


class AIChatDialog(QDialog):
    def __init__(self, ai_node, pw=None):
        """
        Args:
            ai_node (Any): The ai node.
            pw (Any): The pw.
        """
        super().__init__(pw)
        self.node=ai_node; self.current_data=None; self._worker=None
        self._total_in=0; self._total_out=0
        self._history=[]; self._widgets=[]; self._sb=None; self._retry=0
        self._cfg = {
            'backend': 'claude',
            'api_key': '',
            'model': ANTHROPIC_MODEL,
            'temperature': 0.6,
            'num_ctx': 8192,
        }
        self.setWindowTitle("AI Data Assistant")
        self.setMinimumSize(1200,700); self.resize(1400,800)
        self._build_ui()

    def _build_ui(self):
        main=QVBoxLayout(self); main.setContentsMargins(0,0,0,0); main.setSpacing(0)

        hdr=QFrame(); hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        self._title=QLabel("AI Assistant"); hl.addWidget(self._title); hl.addStretch()
        self._backend_lbl=QLabel("No backend"); hl.addWidget(self._backend_lbl)
        self._cost=QLabel(""); self._cost.setVisible(False); hl.addWidget(self._cost)
        self._speed=QLabel(""); self._speed.setVisible(False); hl.addWidget(self._speed)
        tb=QPushButton("Settings"); tb.clicked.connect(self._open_settings); hl.addWidget(tb); self._sbtn=tb
        self._dot=QLabel("●"); hl.addWidget(self._dot)
        self._status=QLabel("Not connected"); hl.addWidget(self._status)
        main.addWidget(hdr); self._hdr=hdr

        self._split=QSplitter(Qt.Horizontal)

        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        self._sug=QFrame(); self._sug_lo=QHBoxLayout(self._sug); self._sug_lo.setContentsMargins(12,6,12,6)
        ll.addWidget(self._sug)
        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._cw=QWidget(); self._cl=QVBoxLayout(self._cw)
        self._cl.setContentsMargins(12,12,12,12); self._cl.setSpacing(4); self._cl.addStretch()
        sc.setWidget(self._cw); ll.addWidget(sc,stretch=1); self._scroll=sc
        self._think=QFrame(); self._think.setVisible(False)
        tl=QHBoxLayout(self._think); tl.setContentsMargins(12,4,12,4)
        self._tlbl=QLabel("Thinking…"); tl.addWidget(self._tlbl)
        prog=QProgressBar(); prog.setRange(0,0); prog.setMaximumHeight(3); tl.addWidget(prog)
        ll.addWidget(self._think)
        inp=QFrame(); il=QHBoxLayout(inp); il.setContentsMargins(12,8,12,8); il.setSpacing(8)
        self._input=QLineEdit(); self._input.setPlaceholderText("Ask about your data…")
        self._input.returnPressed.connect(self._send); il.addWidget(self._input)
        self._stop=QPushButton("■ Stop"); self._stop.setVisible(False); self._stop.clicked.connect(self._do_stop); il.addWidget(self._stop)
        self._sendb=QPushButton("Send"); self._sendb.clicked.connect(self._send); il.addWidget(self._sendb)
        ll.addWidget(inp); self._inp_frame=inp
        self._split.addWidget(left)

        self._carousel=FigureCarousel()
        self._split.addWidget(self._carousel)
        self._split.setSizes([500,700])
        main.addWidget(self._split,stretch=1)

        self._apply_theme()
        global_theme.themeChanged.connect(self._on_global_theme_change)
        self._add_ai("Hello! I'm your AI data assistant.\n\n"
                      "**Setup:** Click **Settings** to choose Claude API or Ollama.\n\n"
                      "**How it works:**\n"
                      "- Ask questions → text explanations with real numbers\n"
                      "- Ask for charts → **interactive figures** on the right panel\n"
                      "- Each figure has **sliders, dropdowns, toggles**\n"
                      "- Navigate figures with **◀ ▶**")
        self._update_sug(None)

    def _open_settings(self):
        d=BackendDialog(self._cfg, self)
        if d.exec()==QDialog.Accepted:
            self._cfg=d.get_config()
            b=self._cfg['backend']
            if b=='claude' and self._cfg.get('api_key'):
                self._dot.setStyleSheet(f"color:{Theme.c('success_dot')};font-size:10px;")
                self._status.setText("Claude connected")
                self._backend_lbl.setText(f"Claude ({ANTHROPIC_MODEL})")
                self._add_ai("**Connected to Claude.** Load data and ask away!")
            elif b=='ollama':
                self._dot.setStyleSheet(f"color:{Theme.c('success_dot')};font-size:10px;")
                self._status.setText(f"Ollama: {self._cfg.get('model','?')}")
                self._backend_lbl.setText(f"Ollama ({self._cfg.get('model','')})")
                self._add_ai(f"**Using Ollama** ({self._cfg.get('model','')}).")
            else:
                self._dot.setStyleSheet(f"color:{Theme.c('error_dot')};font-size:10px;")
                self._status.setText("Not connected")
            self._update_sug(self.current_data)

    def _on_global_theme_change(self, name):
        """Sync with the main window's theme and re-apply.
        Args:
            name (Any): Name string.
        """
        Theme._dark = (name == "dark")
        self._apply_theme()

    def _apply_theme(self):
        bg=Theme.c('bg'); bg2=Theme.c('bg_secondary'); fg=Theme.c('text')
        fg2=Theme.c('text_secondary'); bd=Theme.c('border'); ac=Theme.c('accent'); sf=Theme.c('surface')
        self.setStyleSheet(f"QDialog{{background:{bg};}}"
            f"QScrollArea{{border:none;background:{bg};}}"
            f"QScrollBar:vertical{{background:{Theme.c('scrollbar_bg')};width:8px;border-radius:4px;}}"
            f"QScrollBar::handle:vertical{{background:{Theme.c('scrollbar_handle')};min-height:30px;border-radius:4px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        self._hdr.setStyleSheet(f"QFrame{{background:{bg2};border-bottom:1px solid {bd};}}")
        self._title.setStyleSheet(f"font-size:16px;font-weight:700;color:{fg};")
        self._backend_lbl.setStyleSheet(f"color:{Theme.c('speed_text')};font-size:11px;")
        self._cost.setStyleSheet(f"color:{Theme.c('speed_text')};font-size:11px;font-family:monospace;")
        self._speed.setStyleSheet(f"color:{Theme.c('speed_text')};font-size:11px;font-family:monospace;")
        self._sbtn.setStyleSheet(f"QPushButton{{background:{sf};border:1px solid {bd};border-radius:6px;padding:5px 12px;font-size:12px;color:{fg};}}")
        self._status.setStyleSheet(f"color:{fg2};font-size:12px;")
        self._sug.setStyleSheet(f"QFrame{{border-bottom:1px solid {Theme.c('border_light')};background:{bg};}}")
        self._think.setStyleSheet(f"QFrame{{background:{bg2};border-top:1px solid {Theme.c('border_light')};}}")
        self._tlbl.setStyleSheet(f"color:{fg2};font-size:13px;font-style:italic;")
        self._inp_frame.setStyleSheet(f"QFrame{{background:{bg2};border-top:1px solid {bd};}}")
        self._input.setStyleSheet(f"QLineEdit{{border:1px solid {Theme.c('input_border')};border-radius:10px;padding:10px 16px;font-size:14px;background:{Theme.c('input_bg')};color:{fg};}}")
        self._sendb.setStyleSheet(f"QPushButton{{background:{ac};color:white;border:none;border-radius:10px;padding:10px 20px;font-size:14px;font-weight:600;}}")
        self._stop.setStyleSheet(f"QPushButton{{background:{Theme.c('stop_bg')};color:white;border:none;border-radius:10px;padding:10px 16px;font-size:14px;font-weight:600;}}")
        self._carousel.apply_theme()
        for w in self._widgets:
            if hasattr(w,'apply_theme'): w.apply_theme()

    def _update_sug(self, data):
        """
        Args:
            data (Any): Input data.
        """
        for i in reversed(range(self._sug_lo.count())):
            w=self._sug_lo.itemAt(i).widget()
            if w: w.setParent(None)
        b = self._cfg.get('backend','')
        if not ((b=='claude' and self._cfg.get('api_key')) or b=='ollama'): return
        if data:
            items=["Summarize my data","Histogram of diameters","Element bar chart",
                   "Scatter diameter vs mass","Element heatmap","Box plot comparison"]
        else: items=["What can you do?"]
        for s in items:
            btn=QPushButton(s)
            btn.setStyleSheet(f"QPushButton{{background:{Theme.c('sug_bg')};color:{Theme.c('sug_text')};border:1px solid {Theme.c('sug_border')};border-radius:16px;padding:5px 14px;font-size:12px;}}"
                              f"QPushButton:hover{{background:{Theme.c('sug_hover_bg')};border-color:{Theme.c('sug_hover_border')};color:{Theme.c('sug_hover_text')};}}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _,t=s: (self._input.setText(t), self._send()))
            self._sug_lo.addWidget(btn)

    def update_data_context(self, data):
        """
        Args:
            data (Any): Input data.
        """
        self.current_data=data
        if data:
            self._update_sug(data)
            dt=data.get('type','')
            if dt=='sample_data':
                self._add_ai(f"**Data loaded:** {data.get('sample_name','?')} — {len(data.get('particle_data',[])):,} particles.")
            elif dt=='multiple_sample_data':
                self._add_ai(f"**Multi-sample:** {len(data.get('sample_names',[]))} samples, {len(data.get('particle_data',[])):,} particles.")

    def _do_stop(self):
        if self._worker: self._worker.stop()

    def _send(self):
        text=self._input.text().strip()
        if not text: return
        b = self._cfg.get('backend','')
        if not ((b=='claude' and self._cfg.get('api_key')) or b=='ollama'):
            self._open_settings(); return

        self._input.setEnabled(False); self._sendb.setVisible(False); self._stop.setVisible(True)
        self._add_user(text); self._input.clear()
        self._history.append({"role":"user","content":text}); self._retry=0
        self._think.setVisible(True); self._tlbl.setText("Thinking…")
        self._speed.setVisible(True); self._speed.setText("")

        self._sb=StreamBubble(); self._widgets.append(self._sb)
        self._cl.insertWidget(self._cl.count()-1, self._sb)

        sys_prompt=_build_system_prompt(self.current_data, b)
        max_t = 50000 if b=='claude' else max(512, self._cfg.get('num_ctx',8192)-2000)
        trimmed=_trim_history(list(self._history), max_t)

        self._worker=StreamWorker(b, trimmed, sys_prompt, self._cfg)
        self._worker.token_received.connect(self._on_tok)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.usage_update.connect(self._on_usage)
        self._worker.stream_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.start()

    def _on_tok(self, t):
        """
        Args:
            t (Any): The t.
        """
        if self._sb: self._sb.append(t); self._scrollb()

    def _on_stats(self, n, el):
        """
        Args:
            n (Any): Count or number of items.
            el (Any): The el.
        """
        if el>0: self._speed.setText(f"{n/el:.1f} tok/s")

    def _on_usage(self, i, o):
        """
        Args:
            i (Any): The i.
            o (Any): The o.
        """
        self._total_in+=i; self._total_out+=o
        cost=(self._total_in*3.0+self._total_out*15.0)/1_000_000
        self._cost.setText(f"~${cost:.3f}"); self._cost.setVisible(True)

    def _on_done(self, full):
        """
        Args:
            full (Any): The full.
        """
        self._think.setVisible(False); self._stop.setVisible(False); self._sendb.setVisible(True)
        if self._sb: self._sb.finalise()
        self._history.append({"role":"assistant","content":full})

        particles = self.current_data.get('particle_data',[]) if self.current_data else []

        for m in _JSON_VIZ_RE.finditer(full):
            try:
                spec=json.loads(m.group(1).strip())
                if isinstance(spec,dict) and 'type' in spec and particles:
                    self._carousel.add_figure(build_figure_widget(spec, particles, self.current_data))
            except: pass
        for m in _JSON_RE.finditer(full):
            try:
                spec=json.loads(m.group(1).strip())
                if isinstance(spec,dict) and spec.get('type') in WIDGET_MAP and particles:
                    self._carousel.add_figure(build_figure_widget(spec, particles, self.current_data))
            except: pass

        for m in _CODE_RE.finditer(full):
            if not particles: continue
            pix, err=_execute_raw_code(m.group(1).strip(), particles, self.current_data)
            if pix:
                fb=FigureBubble(pix); self._widgets.append(fb); self._cl.insertWidget(self._cl.count()-1,fb)
            elif err:
                eb=ErrorBubble(err); self._widgets.append(eb); self._cl.insertWidget(self._cl.count()-1,eb)

        self._sb=None; self._scrollb()
        QTimer.singleShot(5000, lambda: self._speed.setVisible(False))
        self._enable()

    def _on_err(self, err):
        """
        Args:
            err (Any): The err.
        """
        self._think.setVisible(False); self._stop.setVisible(False); self._sendb.setVisible(True)
        self._speed.setVisible(False)
        if self._sb: self._sb.finalise(); self._sb=None
        if self._history and self._history[-1]['role']=='user': self._history.pop()
        self._add_ai(f"**Error:** {err}"); self._enable()

    def _enable(self):
        self._input.setEnabled(True); self._sendb.setVisible(True); self._stop.setVisible(False); self._input.setFocus()

    def _add_user(self, t):
        """
        Args:
            t (Any): The t.
        """
        b=TextBubble(t,True); self._widgets.append(b); self._cl.insertWidget(self._cl.count()-1,b); self._scrollb()

    def _add_ai(self, t):
        """
        Args:
            t (Any): The t.
        """
        b=TextBubble(t,False); self._widgets.append(b); self._cl.insertWidget(self._cl.count()-1,b); self._scrollb()

    def _scrollb(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))


class AIAssistantNode(QObject):
    position_changed=Signal(QPointF); configuration_changed=Signal()
    DEFAULT_CONFIG={'backend':'claude','model':ANTHROPIC_MODEL}

    def __init__(self, pw=None):
        """
        Args:
            pw (Any): The pw.
        """
        super().__init__()
        self.title="AI Data Assistant"; self.node_type="ai_assistant"
        self.position=QPointF(0,0); self._has_input=True; self._has_output=False
        self.input_channels=["input"]; self.output_channels=[]
        self.parent_window=pw; self.input_data=None; self.chat_dialog=None
        self.config=dict(self.DEFAULT_CONFIG)

    def set_position(self, p):
        """
        Args:
            p (Any): The p.
        """
        if self.position!=p: self.position=p; self.position_changed.emit(p)

    def process_data(self, d):
        """
        Args:
            d (Any): The d.
        """
        self.input_data=d
        if self.chat_dialog and self.chat_dialog.isVisible(): self.chat_dialog.update_data_context(d)
        self.configuration_changed.emit()

    def get_data_summary(self):
        """
        Returns:
            object: Result of the operation.
        """
        d=self.input_data
        if not d: return "No data"
        dt=d.get('type','?')
        if dt=='sample_data': return f"{d.get('sample_name','?')} — {len(d.get('particle_data',[])):,} particles"
        if dt=='multiple_sample_data': return f"{len(d.get('sample_names',[]))} samples — {len(d.get('particle_data',[])):,} particles"
        return dt

    def configure(self, pw):
        """
        Args:
            pw (Any): The pw.
        Returns:
            bool: Result of the operation.
        """
        if not self.chat_dialog: self.chat_dialog=AIChatDialog(self, pw)
        if self.input_data: self.chat_dialog.update_data_context(self.input_data)
        self.chat_dialog.show(); self.chat_dialog.raise_(); self.chat_dialog.activateWindow()
        return True

def create_ai_assistant_node(pw): return AIAssistantNode(pw)
def show_ai_assistant_dialog(pw, data=None):
    """
    Args:
        pw (Any): The pw.
        data (Any): Input data.
    """
    n=AIAssistantNode(pw)
    if data: n.process_data(data)
    AIChatDialog(n,pw).exec()