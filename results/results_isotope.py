from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QGraphicsWidget, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject, QRectF
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QBrush
import pyqtgraph as pg
import numpy as np
import math
import re
import pandas as pd

from results.utils_sort import extract_mass_and_element

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS, DATA_TYPE_OPTIONS, DATA_KEY_MAPPING,
    get_font_config, make_qfont, apply_font_to_pyqtgraph, set_axis_labels,
    FontSettingsGroup,
    apply_saturation_filter, build_element_matrix,
    get_sample_color, get_display_name,
    download_pyqtgraph_figure,
)


def _mass_of(label: str) -> float | None:
    """
    Extract mass number from an isotope label like '206Pb', '203Tl'.
    Delegates to extract_mass_and_element from utils_sort.

    Returns:
        Mass number as float, or None if not found.
    """
    if not label:
        return None
    mass, _ = extract_mass_and_element(label)
    return float(mass) if mass != 999 else None


# ═══════════════════════════════════════════════
# Batch window helper — strip " [Wn]" suffix
# ═══════════════════════════════════════════════

_BATCH_SUFFIX_RE = re.compile(r'\s*\[W\d+\]\s*$')


def _strip_batch_suffix(sample_name: str) -> str:
    """Strip batch window suffix like ' [W1]' from a sample name.

    BatchSampleSelectorNode renames samples as  ``"<orig> [W<n>]"``.
    This helper recovers the original name so we can look it up in the
    source window's ``sample_particle_data``.

    >>> _strip_batch_suffix("NIST610 [W2]")
    'NIST610'
    >>> _strip_batch_suffix("plain_sample")
    'plain_sample'
    """
    return _BATCH_SUFFIX_RE.sub('', sample_name)


CORRECTION_METHODS = [
    'None',
    'Exponential Law (Internal Standard)',
]

DISPLAY_MODES = [
    'Overlaid (Different Colors)',
    'Side by Side Subplots',
    'Individual Subplots',
    'Combined with Legend',
]

# Jet-like colormap matching reference figure style
JET_POSITIONS = np.array([0.0, 0.11, 0.34, 0.65, 0.89, 1.0])
JET_COLORS = np.array([
    [0, 0, 143, 255],
    [0, 0, 255, 255],
    [0, 255, 255, 255],
    [255, 255, 0, 255],
    [255, 0, 0, 255],
    [128, 0, 0, 255],
], dtype=np.ubyte)


def make_jet_colormap():
    """Create a jet-like PyQtGraph ColorMap for scatter color dimension."""
    return pg.ColorMap(JET_POSITIONS, JET_COLORS)


# ═══════════════════════════════════════════════
# Custom Inset Legend For 3rd Element (Colorbar)
# ═══════════════════════════════════════════════

class InsetColorBarItem(pg.GraphicsWidget):
    """Draws an inset legend-style colorbar inside the plot."""
    def __init__(self, label_text, parent=None):
        super().__init__(parent)
        self.label_text = label_text
        self.setMinimumSize(180, 50)
        self.setZValue(100) # Ensure it stays above the scatter points
        
    def paint(self, p, opt, widget):
        # Draw label text
        p.setPen(pg.mkPen('k'))
        font = p.font()
        font.setPointSize(12)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, 0, 180, 25), Qt.AlignCenter, self.label_text)
        
        # Draw horizontal color gradient
        grad = QLinearGradient(10, 25, 170, 25)
        for pos, color in zip(JET_POSITIONS, JET_COLORS):
            grad.setColorAt(pos, QColor(*color))
            
        p.setBrush(QBrush(grad))
        p.setPen(pg.mkPen('k', width=1))
        p.drawRect(10, 28, 160, 14)


# ═══════════════════════════════════════════════
# Mean signal ratio from full time series
# ═══════════════════════════════════════════════

def get_overall_mean_signal(parent_window, formatted_label: str) -> float | None:
    if not parent_window or not hasattr(parent_window, 'data'):
        return None
    if not hasattr(parent_window, 'selected_isotopes'):
        return None

    for el, isos in parent_window.selected_isotopes.items():
        for iso in isos:
            ek = f"{el}-{iso:.4f}"
            if hasattr(parent_window, 'get_formatted_label'):
                if parent_window.get_formatted_label(ek) == formatted_label:
                    if hasattr(parent_window, 'find_closest_isotope'):
                        isotope_key = parent_window.find_closest_isotope(iso)
                        if isotope_key and isotope_key in parent_window.data:
                            return float(np.mean(parent_window.data[isotope_key]))
    return None


def compute_ratio_from_mean_signals(
    parent_window, num_label: str, den_label: str
) -> tuple:
    mean_num = get_overall_mean_signal(parent_window, num_label)
    mean_den = get_overall_mean_signal(parent_window, den_label)

    if mean_num is None:
        return None, f"No time series data found for '{num_label}'"
    if mean_den is None:
        return None, f"No time series data found for '{den_label}'"
    if mean_den == 0:
        return None, f"Mean signal for '{den_label}' is zero"

    ratio = mean_num / mean_den
    sample = getattr(parent_window, 'current_sample', '(unknown)')
    info = (f"mean({num_label})={mean_num:.2f} / mean({den_label})={mean_den:.2f} "
            f"= {ratio:.6f}  [sample: {sample}]")
    return ratio, info


def get_all_isotope_labels(parent_window) -> list:
    if not parent_window or not hasattr(parent_window, 'selected_isotopes'):
        return []
    labels = []
    for el, isos in parent_window.selected_isotopes.items():
        for iso in isos:
            ek = f"{el}-{iso:.4f}"
            if hasattr(parent_window, 'get_formatted_label'):
                labels.append(parent_window.get_formatted_label(ek))
            else:
                labels.append(f"{round(iso)}{el}")
    return sorted(labels)


# ═══════════════════════════════════════════════
# Isotope correction math — Exponential Law only
# ═══════════════════════════════════════════════

def compute_exponential_correction(
    r_measured: np.ndarray,
    m_num: float, m_den: float,
    ref_certified: float, ref_measured: float,
    m_ref_num: float, m_ref_den: float,
) -> np.ndarray:
    if ref_measured <= 0 or ref_certified <= 0:
        return r_measured
    if m_ref_num <= 0 or m_ref_den <= 0 or m_num <= 0 or m_den <= 0:
        return r_measured

    try:
        f = math.log(ref_certified / ref_measured) / math.log(m_ref_num / m_ref_den)
        correction_factor = (m_num / m_den) ** f
        return r_measured * correction_factor
    except (ValueError, ZeroDivisionError):
        return r_measured


def apply_isotope_correction(r_measured: np.ndarray, config: dict) -> np.ndarray:
    method = config.get('correction_method', 'None')

    if method == 'None':
        return r_measured

    elif method == 'Exponential Law (Internal Standard)':
        elem1 = config.get('element1', '')
        elem2 = config.get('element2', '')
        m_num = _mass_of(elem1)
        m_den = _mass_of(elem2)
        ref_num = config.get('ref_isotope_num', '')
        ref_den = config.get('ref_isotope_den', '')
        m_ref_num = _mass_of(ref_num)
        m_ref_den = _mass_of(ref_den)
        ref_certified = config.get('ref_certified_ratio', 1.0)
        ref_measured = config.get('ref_measured_ratio', 1.0)

        if all(v is not None for v in [m_num, m_den, m_ref_num, m_ref_den]):
            return compute_exponential_correction(
                r_measured, m_num, m_den,
                ref_certified, ref_measured,
                m_ref_num, m_ref_den)
        return r_measured

    return r_measured


def _find_particles_for_sample(sample_name, dk, node=None, parent_window=None):
    """Find unfiltered particles for a sample.

    Prefer window sources (unfiltered) over node input (may be isotope-filtered).

    FIX (batch windows): When sample_name contains a batch suffix like
    " [W1]", we also search all open windows using the *original* name
    so that particles from any batch source window can be found.
    """
    pw = parent_window
    original_name = _strip_batch_suffix(sample_name)
    is_batch_name = (original_name != sample_name)

    # 1. Try parent window with exact name
    if pw and hasattr(pw, 'sample_particle_data'):
        particles = pw.sample_particle_data.get(sample_name, [])
        if particles:
            return particles
        # Also try original name (batch mode: parent may have the un-suffixed name)
        if is_batch_name:
            particles = pw.sample_particle_data.get(original_name, [])
            if particles:
                return particles

    # 2. Search ALL open windows (handles batch mode where data is in
    #    a different window than the parent)
    app = QApplication.instance()
    if app and hasattr(app, 'main_windows'):
        for w in app.main_windows:
            if w is pw:
                continue
            if hasattr(w, 'sample_particle_data'):
                # Try exact name
                particles = w.sample_particle_data.get(sample_name, [])
                if particles:
                    return particles
                # Try stripped original name (for batch-renamed samples)
                if is_batch_name:
                    particles = w.sample_particle_data.get(original_name, [])
                    if particles:
                        return particles

    # 3. Fallback: node input data (contains all batch particles)
    if node and hasattr(node, 'input_data') and node.input_data:
        particles = node.input_data.get('particle_data', [])
        found = [p for p in particles
                 if p.get('original_sample', p.get('source_sample', '')) == sample_name
                 or p.get('source_sample', '') == sample_name]
        if found:
            return found
        # Also try matching by original name for batch-renamed samples
        if is_batch_name:
            found = [p for p in particles
                     if p.get('original_sample', '') == original_name
                     and p.get('source_sample', '') == sample_name]
            if found:
                return found

    return []


def get_correction_factor(config: dict) -> float:
    method = config.get('correction_method', 'None')

    if method == 'Exponential Law (Internal Standard)':
        elem1, elem2 = config.get('element1', ''), config.get('element2', '')
        m_num, m_den = _mass_of(elem1), _mass_of(elem2)
        ref_num = config.get('ref_isotope_num', '')
        ref_den = config.get('ref_isotope_den', '')
        m_rn, m_rd = _mass_of(ref_num), _mass_of(ref_den)
        rc = config.get('ref_certified_ratio', 1.0)
        rm = config.get('ref_measured_ratio', 1.0)
        if all(v and v > 0 for v in [m_num, m_den, m_rn, m_rd, rc, rm]):
            try:
                f = math.log(rc / rm) / math.log(m_rn / m_rd)
                return (m_num / m_den) ** f
            except (ValueError, ZeroDivisionError):
                pass
        return 1.0

    return 1.0


def build_equation_text(config: dict, sample_name: str = None) -> str:
    method = config.get('correction_method', 'None')

    if method == 'None':
        return ''

    e1 = config.get('element1', '?')
    e2 = config.get('element2', '?')
    prefix = f"[{sample_name}] " if sample_name else ""

    if method == 'Exponential Law (Internal Standard)':
        ref_num = config.get('ref_isotope_num', '?')
        ref_den = config.get('ref_isotope_den', '?')
        R_T_std = config.get('ref_certified_ratio', 1.0)
        R_M_std = config.get('ref_measured_ratio', 1.0)
        m_i = _mass_of(e1) or 0
        m_j = _mass_of(e2) or 0
        m_std_num = _mass_of(ref_num) or 0
        m_std_den = _mass_of(ref_den) or 0

        try:
            if R_M_std > 0 and R_T_std > 0 and m_std_num > 0 and m_std_den > 0:
                p_val = math.log(R_T_std / R_M_std) / math.log(m_std_num / m_std_den)
            else:
                p_val = 0
            if m_i > 0 and m_j > 0:
                cf = (m_i / m_j) ** p_val
            else:
                cf = 1.0
        except (ValueError, ZeroDivisionError):
            p_val = 0
            cf = 1.0

        lines = [
            f"{prefix}Exponential Law — Russell et al. (1978)\nRidley, W. I. (2005). Plumbo-isotopy: the measurement of lead isotopes by multi-collector inductively coupled mass spectrometry.",
            f"",
            f"  Internal standard: {ref_num}/{ref_den}",
            f"  R_T_std (certified) = {R_T_std:.6f}",
            f"  R_M_std (measured)  = {R_M_std:.6f}",
            f"",
            f"  p = ln(R_T_std / R_M_std) / ln(m_std_num / m_std_den)",
            f"    = ln({R_T_std:.6f} / {R_M_std:.6f}) / ln({m_std_num:.0f} / {m_std_den:.0f})",
            f"    = {p_val:.6f}",
            f"",
            f"  R_T({e1}/{e2}) = R_M({e1}/{e2}) × ({m_i:.0f}/{m_j:.0f})^p",
            f"               = R_M × {cf:.6f}",
        ]
        return '\n'.join(lines)

    return ''


# ═══════════════════════════════════════════════
# Per-sample correction config helper
# ═══════════════════════════════════════════════

def _default_sample_correction() -> dict:
    return {
        'correction_method': 'None',
        'ref_isotope_num': '',
        'ref_isotope_den': '',
        'ref_certified_ratio': 1.0,
        'ref_measured_ratio': 1.0,
        'exp_ref_sample': '(manual)',
    }


def get_sample_correction_config(cfg: dict, sample_name: str = None) -> dict:
    if not cfg.get('per_sample_correction', False) or not sample_name:
        return cfg

    sample_cfgs = cfg.get('sample_correction_configs', {})
    scfg = sample_cfgs.get(sample_name)
    if not scfg:
        merged = dict(cfg)
        merged['correction_method'] = 'None'
        return merged

    merged = dict(cfg)
    for k in _default_sample_correction():
        if k in scfg:
            merged[k] = scfg[k]
    return merged


# ═══════════════════════════════════════════════
# Poisson confidence intervals
# ═══════════════════════════════════════════════

def poisson_ratio_sigma(R: float, lambda_B: np.ndarray) -> np.ndarray:
    safe_lB = np.maximum(lambda_B, 1.0)
    return np.sqrt(R * (1.0 + R) / safe_lB)


def poisson_ci_curves(R: float, x_range: np.ndarray, k: float = 2.0):
    sigma = poisson_ratio_sigma(R, x_range)
    upper = R + k * sigma
    lower = np.maximum(R - k * sigma, 0.0)
    return upper, lower


# ═══════════════════════════════════════════════
# Per-Sample Correction Dialog
# ═══════════════════════════════════════════════

class SampleCorrectionDialog(QDialog):
    def __init__(self, sample_name: str, sample_cfg: dict,
                 available_elements: list, all_sample_names: list,
                 node=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Correction Settings — {sample_name}")
        self.setMinimumWidth(480)
        self._sample_name = sample_name
        self._cfg = dict(sample_cfg) if sample_cfg else _default_sample_correction()
        self._elems = available_elements
        self._all_samples = all_sample_names
        self._node = node
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"Configure isotope correction for: <b>{self._sample_name}</b>")
        info.setWordWrap(True)
        layout.addWidget(info)

        g = QGroupBox("Correction Method")
        fl = QFormLayout(g)

        self.correction_method = QComboBox()
        self.correction_method.addItems(CORRECTION_METHODS)
        self.correction_method.setCurrentText(self._cfg.get('correction_method', 'None'))
        self.correction_method.currentTextChanged.connect(self._on_method_changed)
        fl.addRow("Method:", self.correction_method)

        self.exp_frame = QFrame()
        exp_layout = QVBoxLayout(self.exp_frame)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_fl = QFormLayout()
        exp_layout.addLayout(exp_fl)

        self.ref_num = QComboBox()
        self.ref_num.setEditable(True)
        self.ref_num.addItems(self._elems)
        cur = self._cfg.get('ref_isotope_num', '')
        if cur:
            self.ref_num.setCurrentText(cur)
        exp_fl.addRow("Ref. Numerator:", self.ref_num)

        self.ref_den = QComboBox()
        self.ref_den.setEditable(True)
        self.ref_den.addItems(self._elems)
        cur = self._cfg.get('ref_isotope_den', '')
        if cur:
            self.ref_den.setCurrentText(cur)
        exp_fl.addRow("Ref. Denominator:", self.ref_den)

        self.ref_certified = QDoubleSpinBox()
        self.ref_certified.setRange(0.0, 100000.0)
        self.ref_certified.setDecimals(6)
        self.ref_certified.setValue(self._cfg.get('ref_certified_ratio', 1.0))
        exp_fl.addRow("Certified Ref. Ratio:", self.ref_certified)

        self.ref_measured = QDoubleSpinBox()
        self.ref_measured.setRange(0.0, 100000.0)
        self.ref_measured.setDecimals(6)
        self.ref_measured.setValue(self._cfg.get('ref_measured_ratio', 1.0))
        exp_fl.addRow("Measured Ref. Ratio:", self.ref_measured)

        self.exp_ref_sample = QComboBox()
        self.exp_ref_sample.addItem("(manual)")
        if self._all_samples:
            self.exp_ref_sample.addItems(self._all_samples)
        cur_s = self._cfg.get('exp_ref_sample', '(manual)')
        idx = self.exp_ref_sample.findText(cur_s)
        if idx >= 0:
            self.exp_ref_sample.setCurrentIndex(idx)
        exp_fl.addRow("Compute from Sample:", self.exp_ref_sample)

        auto_btn = QPushButton("Compute measured ratio from selected sample")
        auto_btn.clicked.connect(self._auto_compute_exp)
        exp_layout.addWidget(auto_btn)

        self.exp_info = QLabel("")
        self.exp_info.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        self.exp_info.setWordWrap(True)
        exp_layout.addWidget(self.exp_info)

        fl.addRow(self.exp_frame)

        layout.addWidget(g)

        self._on_method_changed()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_method_changed(self):
        method = self.correction_method.currentText()
        self.exp_frame.setVisible(method == 'Exponential Law (Internal Standard)')

    def _auto_compute_exp(self):
        num_label = self.ref_num.currentText().strip()
        den_label = self.ref_den.currentText().strip()
        if not num_label or not den_label:
            self.exp_info.setText("Select reference numerator and denominator first.")
            return

        node = self._node
        pw = node.parent_window if node and hasattr(node, 'parent_window') else None
        dk = DATA_KEY_MAPPING.get(
            node.config.get('data_type_display', 'Counts') if node else 'Counts',
            'elements')

        # Find which original replicates belong to this grouped sample
        original_names = []
        if node and hasattr(node, 'input_data') and node.input_data:
            seen = set()
            for p in node.input_data.get('particle_data', []):
                if p.get('source_sample', '') == self._sample_name:
                    orig = p.get('original_sample', p.get('source_sample', ''))
                    if orig and orig not in seen:
                        seen.add(orig)
                        original_names.append(orig)
        if not original_names:
            original_names = [self._sample_name]
        original_names.sort()

        # Compute ratio per replicate — same logic as _compute_replicate_ratios
        ratios = []
        rep_details = []

        for sn in original_names:
            # 1. Try _find_particles_for_sample (searches all windows + node input)
            particles = _find_particles_for_sample(sn, dk, node=node, parent_window=pw)
            if particles:
                num_vals = [p.get(dk, p.get('elements', {})).get(num_label, 0)
                            for p in particles]
                den_vals = [p.get(dk, p.get('elements', {})).get(den_label, 0)
                            for p in particles]
                num_vals = [v for v in num_vals if v > 0]
                den_vals = [v for v in den_vals if v > 0]
                if num_vals and den_vals:
                    r = float(np.mean(num_vals)) / float(np.mean(den_vals))
                    ratios.append(r)
                    rep_details.append(f"  {sn}: {r:.6f}")
                    continue

            # 2. Fallback: time-series — search ALL windows, not just pw
            ratio_found = False
            original_name = _strip_batch_suffix(sn)
            windows_to_search = [pw] if pw else []
            app = QApplication.instance()
            if app and hasattr(app, 'main_windows'):
                for w in app.main_windows:
                    if w is not pw and w not in windows_to_search:
                        windows_to_search.append(w)

            for w in windows_to_search:
                if not w or not hasattr(w, 'data_by_sample') or not hasattr(w, 'selected_isotopes'):
                    continue
                for try_name in ([sn, original_name] if original_name != sn else [sn]):
                    sd = w.data_by_sample.get(try_name)
                    if sd:
                        r = IsotopeSettingsDialog._ratio_from_sample_ts(
                            w, sd, num_label, den_label)
                        if r is not None:
                            ratios.append(r)
                            rep_details.append(f"  {sn}: {r:.6f}")
                            ratio_found = True
                            break
                if ratio_found:
                    break

        if not ratios:
            self.exp_info.setText(
                f"No valid data for {num_label}/{den_label} in "
                f"replicates: {', '.join(original_names)}")
            return

        mean_ratio = float(np.mean(ratios))
        self.ref_measured.setValue(mean_ratio)
        self.exp_info.setText(
            f"{num_label}/{den_label} = {mean_ratio:.6f} "
            f"(mean of {len(ratios)} replicates)\n"
            + "\n".join(rep_details))

    def collect(self) -> dict:
        return {
            'correction_method': self.correction_method.currentText(),
            'ref_isotope_num': self.ref_num.currentText(),
            'ref_isotope_den': self.ref_den.currentText(),
            'ref_certified_ratio': self.ref_certified.value(),
            'ref_measured_ratio': self.ref_measured.value(),
            'exp_ref_sample': self.exp_ref_sample.currentText(),
        }


# ═══════════════════════════════════════════════
# Settings Dialog
# ═══════════════════════════════════════════════

class IsotopeSettingsDialog(QDialog):
    def __init__(self, config: dict, available_elements: list,
                 all_isotope_labels: list,
                 is_multi: bool, sample_names: list,
                 parent_window=None, parent=None,
                 node=None):
        super().__init__(parent)
        self.setWindowTitle("Isotopic Ratio Settings")
        self.setMinimumWidth(560)
        self._cfg = dict(config)
        self._elems = available_elements
        self._all_isotopes = all_isotope_labels
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._parent_window = parent_window
        self._node = node

        import copy
        self._sample_corr_cfgs = copy.deepcopy(
            config.get('sample_correction_configs', {}))

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        tabs = QTabWidget()
        outer.addWidget(tabs)

        general_widget = QWidget()
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setWidget(general_widget)
        layout = QVBoxLayout(general_widget)
        layout.setSpacing(8)

        if self._is_multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(DISPLAY_MODES)
            self.display_mode.setCurrentText(self._cfg.get('display_mode', DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        fl.addRow("Data:", self.data_type)
        layout.addWidget(g)

        g = QGroupBox("Element Selection")
        fl = QFormLayout(g)
        self.elem1 = QComboBox()
        self.elem1.addItems(self._elems)
        e1 = self._cfg.get('element1', self._elems[0] if self._elems else '')
        if e1 in self._elems:
            self.elem1.setCurrentText(e1)
        fl.addRow("Numerator (A):", self.elem1)

        self.elem2 = QComboBox()
        self.elem2.addItems(self._elems)
        e2 = self._cfg.get('element2', self._elems[1] if len(self._elems) > 1 else '')
        if e2 in self._elems:
            self.elem2.setCurrentText(e2)
        fl.addRow("Denominator (B):", self.elem2)

        self.x_elem = QComboBox()
        self.x_elem.addItems(self._elems)
        xd = self._cfg.get('x_axis_element', e2)
        if xd in self._elems:
            self.x_elem.setCurrentText(xd)
        fl.addRow("X-axis Element:", self.x_elem)

        self.color_elem = QComboBox()
        self.color_elem.addItem("")
        self.color_elem.addItems(self._elems)
        ce = self._cfg.get('color_element', '')
        if ce in self._elems:
            self.color_elem.setCurrentText(ce)
        fl.addRow("Color Element (3rd):", self.color_elem)

        layout.addWidget(g)

        g = QGroupBox("Reference Lines")
        fl = QFormLayout(g)
        self.show_natural = QCheckBox()
        self.show_natural.setChecked(self._cfg.get('show_natural_line', False))
        fl.addRow("Natural Abundance Line:", self.show_natural)
        self.show_standard = QCheckBox()
        self.show_standard.setChecked(self._cfg.get('show_standard_line', False))
        fl.addRow("Standard Ratio Line:", self.show_standard)
        self.show_mean = QCheckBox()
        self.show_mean.setChecked(self._cfg.get('show_mean_line', True))
        fl.addRow("Mean Ratio Line:", self.show_mean)
        layout.addWidget(g)

        g = QGroupBox("Confidence Intervals")
        fl = QFormLayout(g)
        self.show_ci = QCheckBox("Show Poisson 95 % CI (±2σ)")
        self.show_ci.setChecked(self._cfg.get('show_confidence_intervals', True))
        fl.addRow(self.show_ci)
        layout.addWidget(g)

        g = QGroupBox("Filtering")
        fl = QFormLayout(g)
        self.filter_zeros = QCheckBox()
        self.filter_zeros.setChecked(self._cfg.get('filter_zeros', True))
        fl.addRow("Filter Zero Values:", self.filter_zeros)
        self.filter_sat = QCheckBox()
        self.filter_sat.setChecked(self._cfg.get('filter_saturated', False))
        fl.addRow("Filter Saturated:", self.filter_sat)
        self.sat_thresh = QDoubleSpinBox()
        self.sat_thresh.setRange(0.1, 99999999.0)
        self.sat_thresh.setDecimals(1)
        self.sat_thresh.setValue(self._cfg.get('saturation_threshold', 9999999.0))
        fl.addRow("Saturation Threshold:", self.sat_thresh)
        layout.addWidget(g)

        g = QGroupBox("Axis Settings")
        fl = QFormLayout(g)
        self.log_x = QCheckBox()
        self.log_x.setChecked(self._cfg.get('log_x', False))
        fl.addRow("Log X-axis:", self.log_x)
        self.log_y = QCheckBox()
        self.log_y.setChecked(self._cfg.get('log_y', False))
        fl.addRow("Log Y-axis:", self.log_y)
        self.x_max = QDoubleSpinBox()
        self.x_max.setRange(1.0, 99999999.0)
        self.x_max.setDecimals(0)
        self.x_max.setValue(self._cfg.get('x_max', 99999999.0))
        fl.addRow("X-axis Maximum:", self.x_max)
        layout.addWidget(g)

        g = QGroupBox("Display Options")
        fl = QFormLayout(g)
        self.marker_size = QSpinBox()
        self.marker_size.setRange(1, 30)
        self.marker_size.setValue(self._cfg.get('marker_size', 8))
        fl.addRow("Marker Size:", self.marker_size)
        self.marker_alpha = QDoubleSpinBox()
        self.marker_alpha.setRange(0.1, 1.0)
        self.marker_alpha.setSingleStep(0.1)
        self.marker_alpha.setDecimals(1)
        self.marker_alpha.setValue(self._cfg.get('marker_alpha', 0.7))
        fl.addRow("Marker Transparency:", self.marker_alpha)

        if not self._is_multi:
            self._single_color_btn = QPushButton()
            sc = self._cfg.get('single_sample_color', '#E74C3C')
            self._single_color = QColor(sc)
            self._single_color_btn.setStyleSheet(
                f"background-color: {sc}; min-height: 25px; border: 1px solid black;")
            self._single_color_btn.clicked.connect(self._pick_single_color)
            fl.addRow("Marker Color:", self._single_color_btn)
        layout.addWidget(g)

        if self._is_multi:
            g = QGroupBox("Sample Colors")
            vl = QVBoxLayout(g)
            self._color_btns = {}
            self._name_edits = {}
            colors = self._cfg.get('sample_colors', {})
            mappings = self._cfg.get('sample_name_mappings', {})
            for i, sn in enumerate(self._sample_names):
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(180)
                row.addWidget(ne)
                self._name_edits[sn] = ne
                cb = QPushButton()
                cb.setFixedSize(30, 22)
                c = colors.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                cb.setStyleSheet(f"background-color: {c}; border: 1px solid black;")
                cb.clicked.connect(lambda _, s=sn, b=cb: self._pick_sample_color(s, b))
                row.addWidget(cb)
                self._color_btns[sn] = (cb, c)
                row.addStretch()
                w = QWidget()
                w.setLayout(row)
                vl.addWidget(w)
            layout.addWidget(g)

        self._font_group = FontSettingsGroup(self._cfg)
        layout.addWidget(self._font_group.build())

        tabs.addTab(general_scroll, "General")

        corr_widget = QWidget()
        corr_scroll = QScrollArea()
        corr_scroll.setWidgetResizable(True)
        corr_scroll.setWidget(corr_widget)
        corr_layout = QVBoxLayout(corr_widget)
        corr_layout.setSpacing(8)

        self.per_sample_cb = QCheckBox("Enable per-sample correction (each sample has its own settings)")
        self.per_sample_cb.setChecked(self._cfg.get('per_sample_correction', False))
        self.per_sample_cb.toggled.connect(self._on_per_sample_toggled)
        corr_layout.addWidget(self.per_sample_cb)

        self.global_corr_frame = QFrame()
        gcl = QVBoxLayout(self.global_corr_frame)
        gcl.setContentsMargins(0, 0, 0, 0)

        g = QGroupBox("Global Isotope Correction — Exponential Law (IMF)")
        fl = QFormLayout(g)

        self.correction_method = QComboBox()
        self.correction_method.addItems(CORRECTION_METHODS)
        self.correction_method.setCurrentText(self._cfg.get('correction_method', 'None'))
        self.correction_method.currentTextChanged.connect(self._on_method_changed)
        fl.addRow("Method:", self.correction_method)

        self.exp_frame = QFrame()
        exp_layout = QVBoxLayout(self.exp_frame)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_fl = QFormLayout()
        exp_layout.addLayout(exp_fl)

        ref_elems = self._all_isotopes if self._all_isotopes else self._elems

        self.ref_num = QComboBox()
        self.ref_num.setEditable(True)
        self.ref_num.addItems(ref_elems)
        cur_ref_num = self._cfg.get('ref_isotope_num', '')
        if cur_ref_num:
            self.ref_num.setCurrentText(cur_ref_num)
        exp_fl.addRow("Ref. Numerator:", self.ref_num)

        self.ref_den = QComboBox()
        self.ref_den.setEditable(True)
        self.ref_den.addItems(ref_elems)
        cur_ref_den = self._cfg.get('ref_isotope_den', '')
        if cur_ref_den:
            self.ref_den.setCurrentText(cur_ref_den)
        exp_fl.addRow("Ref. Denominator:", self.ref_den)

        self.ref_certified = QDoubleSpinBox()
        self.ref_certified.setRange(0.0, 100000.0)
        self.ref_certified.setDecimals(6)
        self.ref_certified.setValue(self._cfg.get('ref_certified_ratio', 1.0))
        exp_fl.addRow("Certified Ref. Ratio:", self.ref_certified)

        self.ref_measured = QDoubleSpinBox()
        self.ref_measured.setRange(0.0, 100000.0)
        self.ref_measured.setDecimals(6)
        self.ref_measured.setValue(self._cfg.get('ref_measured_ratio', 1.0))
        exp_fl.addRow("Measured Ref. Ratio:", self.ref_measured)

        self.exp_ref_sample = QComboBox()
        self.exp_ref_sample.addItem("(All samples merged)")
        if self._sample_names:
            self.exp_ref_sample.addItems(self._sample_names)
        cur_exp = self._cfg.get('exp_ref_sample', '(All samples merged)')
        idx = self.exp_ref_sample.findText(cur_exp)
        if idx >= 0:
            self.exp_ref_sample.setCurrentIndex(idx)
        exp_fl.addRow("Compute from Sample:", self.exp_ref_sample)

        auto_ref_btn = QPushButton("Compute measured ratio from sample")
        auto_ref_btn.clicked.connect(self._auto_compute_ref_measured)
        exp_layout.addWidget(auto_ref_btn)

        self.ref_info_label = QLabel("")
        self.ref_info_label.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        self.ref_info_label.setWordWrap(True)
        exp_layout.addWidget(self.ref_info_label)

        fl.addRow(self.exp_frame)

        gcl.addWidget(g)
        corr_layout.addWidget(self.global_corr_frame)

        self._on_method_changed()

        self.per_sample_frame = QFrame()
        psl = QVBoxLayout(self.per_sample_frame)
        psl.setContentsMargins(0, 0, 0, 0)

        info_lbl = QLabel(
            "Each sample has independent correction settings.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #666; font-size: 11px; font-style: italic; padding: 4px;")
        psl.addWidget(info_lbl)

        self.sample_corr_table = QTableWidget()
        self.sample_corr_table.setColumnCount(4)
        self.sample_corr_table.setHorizontalHeaderLabels(
            ["Sample", "Method", "Details", ""])

        samples_to_show = self._sample_names if self._is_multi else ["(Current Sample)"]
        self.sample_corr_table.setRowCount(len(samples_to_show))

        for row, sn in enumerate(samples_to_show):
            item = QTableWidgetItem(sn)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.sample_corr_table.setItem(row, 0, item)

            scfg = self._sample_corr_cfgs.get(sn, _default_sample_correction())
            method_item = QTableWidgetItem(scfg.get('correction_method', 'None'))
            method_item.setFlags(method_item.flags() & ~Qt.ItemIsEditable)
            self.sample_corr_table.setItem(row, 1, method_item)

            details = self._format_correction_details(scfg)
            det_item = QTableWidgetItem(details)
            det_item.setFlags(det_item.flags() & ~Qt.ItemIsEditable)
            self.sample_corr_table.setItem(row, 2, det_item)

            btn = QPushButton("Configure…")
            btn.clicked.connect(lambda _, s=sn, r=row: self._configure_sample_correction(s, r))
            self.sample_corr_table.setCellWidget(row, 3, btn)

        h = self.sample_corr_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        self.sample_corr_table.setColumnWidth(3, 100)

        psl.addWidget(self.sample_corr_table)

        copy_row = QHBoxLayout()
        copy_btn = QPushButton("Copy selected sample's correction to all others")
        copy_btn.clicked.connect(self._copy_correction_to_all)
        copy_row.addWidget(copy_btn)
        copy_row.addStretch()
        psl.addLayout(copy_row)

        corr_layout.addWidget(self.per_sample_frame)

        ratio_group = QGroupBox("Replicate Reference Ratios — Individual Samples")
        ratio_vl = QVBoxLayout(ratio_group)

        ratio_ctrl = QHBoxLayout()
        ratio_ctrl.addWidget(QLabel("Ref. Numerator:"))
        self._rep_ref_num = QComboBox()
        self._rep_ref_num.setEditable(True)
        self._rep_ref_num.addItems(ref_elems)
        if cur_ref_num:
            self._rep_ref_num.setCurrentText(cur_ref_num)
        ratio_ctrl.addWidget(self._rep_ref_num)

        ratio_ctrl.addWidget(QLabel("Ref. Denominator:"))
        self._rep_ref_den = QComboBox()
        self._rep_ref_den.setEditable(True)
        self._rep_ref_den.addItems(ref_elems)
        if cur_ref_den:
            self._rep_ref_den.setCurrentText(cur_ref_den)
        ratio_ctrl.addWidget(self._rep_ref_den)

        rep_compute_btn = QPushButton("Compute")
        rep_compute_btn.clicked.connect(self._compute_replicate_ratios)
        ratio_ctrl.addWidget(rep_compute_btn)
        ratio_vl.addLayout(ratio_ctrl)

        cert_row = QHBoxLayout()
        cert_row.addWidget(QLabel("Certified Ref. Ratio (for CF axis):"))
        self._rep_certified = QDoubleSpinBox()
        self._rep_certified.setRange(0.0, 100000.0)
        self._rep_certified.setDecimals(6)
        self._rep_certified.setValue(self._cfg.get('ref_certified_ratio', 1.0))
        cert_row.addWidget(self._rep_certified)
        cert_row.addStretch()
        ratio_vl.addLayout(cert_row)

        self._rep_plot = pg.PlotWidget(background='w')
        self._rep_plot.setMinimumHeight(280)
        self._rep_plot.showGrid(x=False, y=True, alpha=0.3)
        ratio_vl.addWidget(self._rep_plot)

        self._rep_info = QLabel("")
        self._rep_info.setWordWrap(True)
        self._rep_info.setStyleSheet(
            "color: #333; font-size: 11px; padding: 4px;")
        ratio_vl.addWidget(self._rep_info)

        corr_layout.addWidget(ratio_group)

        self._on_per_sample_toggled(self.per_sample_cb.isChecked())

        tabs.addTab(corr_scroll, "Isotope Correction")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _format_correction_details(self, scfg):
        method = scfg.get('correction_method', 'None')
        if method == 'None':
            return "No correction"
        elif method == 'Exponential Law (Internal Standard)':
            rn = scfg.get('ref_isotope_num', '?')
            rd = scfg.get('ref_isotope_den', '?')
            rc = scfg.get('ref_certified_ratio', 1.0)
            rm = scfg.get('ref_measured_ratio', 1.0)
            return f"Ref: {rn}/{rd}, cert={rc:.4f}, meas={rm:.4f}"
        return ""

    def _on_per_sample_toggled(self, enabled):
        self.global_corr_frame.setVisible(not enabled)
        self.per_sample_frame.setVisible(enabled)

    def _on_method_changed(self):
        method = self.correction_method.currentText()
        self.exp_frame.setVisible(method == 'Exponential Law (Internal Standard)')

    def _configure_sample_correction(self, sample_name, row):
        scfg = self._sample_corr_cfgs.get(sample_name, _default_sample_correction())
        scfg['element1'] = self.elem1.currentText()
        scfg['element2'] = self.elem2.currentText()

        ref_elems = self._all_isotopes if self._all_isotopes else self._elems

        dlg = SampleCorrectionDialog(
            sample_name, scfg, ref_elems,
            self._sample_names, node=self._node, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_cfg = dlg.collect()
            self._sample_corr_cfgs[sample_name] = new_cfg
            self.sample_corr_table.item(row, 1).setText(new_cfg.get('correction_method', 'None'))
            self.sample_corr_table.item(row, 2).setText(self._format_correction_details(new_cfg))

    def _copy_correction_to_all(self):
        rows = set()
        for item in self.sample_corr_table.selectedItems():
            rows.add(item.row())
        if len(rows) != 1:
            QMessageBox.information(self, "Info", "Select exactly one sample row to copy from.")
            return

        src_row = rows.pop()
        samples = self._sample_names if self._is_multi else ["(Current Sample)"]
        src_name = samples[src_row]
        src_cfg = self._sample_corr_cfgs.get(src_name, _default_sample_correction())

        import copy
        for row, sn in enumerate(samples):
            if row == src_row:
                continue
            self._sample_corr_cfgs[sn] = copy.deepcopy(src_cfg)
            self.sample_corr_table.item(row, 1).setText(src_cfg.get('correction_method', 'None'))
            self.sample_corr_table.item(row, 2).setText(self._format_correction_details(src_cfg))
            
    
    def _get_input_sample_names(self):
        """Get the list of individual replicate/sample names from the node's
        input data instead of from the parent window, so only samples that
        were actually selected are shown.
        
        FIX 2: Previously this used pw.sample_particle_data.keys() which
        returned ALL samples loaded in the main window, not just the ones
        feeding into this node.
        """
        if not self._node:
            return []

        input_data = getattr(self._node, 'input_data', None)
        if not input_data:
            return []

        particles = input_data.get('particle_data', [])
        if not particles:
            return []

        # Collect unique original sample names (individual replicates)
        # preserving discovery order
        seen = set()
        names = []
        for p in particles:
            sn = p.get('original_sample', p.get('source_sample', ''))
            if sn and sn not in seen:
                seen.add(sn)
                names.append(sn)

        return sorted(names)


    def _compute_replicate_ratios(self):
        """Compute and plot the measured reference ratio for each individual replicate,
        with an optional right Y-axis showing the correction factor (CF)."""
        ref_num = self._rep_ref_num.currentText().strip()
        ref_den = self._rep_ref_den.currentText().strip()
        if not ref_num or not ref_den:
            self._rep_info.setText("Select reference numerator and denominator first.")
            return

        pw = self._parent_window
        dk = DATA_KEY_MAPPING.get(
            self._cfg.get('data_type_display', 'Counts'), 'elements')

        # Get samples from node input data, not parent window
        all_samples = self._get_input_sample_names()

        if not all_samples:
            if pw:
                if hasattr(pw, 'sample_particle_data') and pw.sample_particle_data:
                    all_samples = sorted(pw.sample_particle_data.keys())
                elif hasattr(pw, 'data_by_sample') and pw.data_by_sample:
                    all_samples = sorted(pw.data_by_sample.keys())

        if not all_samples:
            self._rep_info.setText("No individual sample data found.")
            return

        # Compute ratios using unified particle lookup
        ratios = []
        valid_names = []
        n_particles_list = []

        for sn in all_samples:
            particles = _find_particles_for_sample(sn, dk, node=self._node, parent_window=pw)
            if particles:
                num_vals = [
                    p.get(dk, p.get('elements', {})).get(ref_num, 0)
                    for p in particles]
                den_vals = [
                    p.get(dk, p.get('elements', {})).get(ref_den, 0)
                    for p in particles]
                num_vals = [v for v in num_vals if v > 0]
                den_vals = [v for v in den_vals if v > 0]
                if num_vals and den_vals:
                    ratio = float(np.mean(num_vals)) / float(np.mean(den_vals))
                    ratios.append(ratio)
                    valid_names.append(sn)
                    n_particles_list.append(min(len(num_vals), len(den_vals)))
                    continue

            # Last fallback: time-series data — search ALL windows, not just pw
            ratio_found = False
            windows_to_search = [pw] if pw else []
            app = QApplication.instance()
            if app and hasattr(app, 'main_windows'):
                for w in app.main_windows:
                    if w is not pw and w not in windows_to_search:
                        windows_to_search.append(w)

            original_name = _strip_batch_suffix(sn)
            for w in windows_to_search:
                if not w or not hasattr(w, 'data_by_sample') or not hasattr(w, 'selected_isotopes'):
                    continue
                # Try exact name first, then stripped name
                for try_name in ([sn, original_name] if original_name != sn else [sn]):
                    sd = w.data_by_sample.get(try_name)
                    if sd:
                        ratio_ts = self._ratio_from_sample_ts(w, sd, ref_num, ref_den)
                        if ratio_ts is not None:
                            ratios.append(ratio_ts)
                            valid_names.append(sn)
                            n_particles_list.append(0)
                            ratio_found = True
                            break
                if ratio_found:
                    break

        if not ratios:
            self._rep_info.setText(
                f"No valid data for {ref_num}/{ref_den} across any replicate.")
            return

        # ── Plot ──────────────────────────────────────────────────────
        self._rep_plot.clear()

        if hasattr(self, '_cf_vb'):
            try:
                self._rep_plot.scene().removeItem(self._cf_vb)
            except Exception:
                pass
            self._cf_vb = None

        x = np.arange(len(ratios))
        ratios_arr = np.array(ratios)
        mean_r = float(np.mean(ratios_arr))

        line = pg.PlotDataItem(
            x=x, y=ratios_arr,
            pen=pg.mkPen('#3B82F6', width=2),
            symbol='o', symbolSize=9,
            symbolPen=pg.mkPen('#1E293B', width=1),
            symbolBrush=pg.mkBrush('#3B82F6'))
        self._rep_plot.addItem(line)

        if mean_r > 0:
            outlier_x = []
            outlier_y = []
            for i, r in enumerate(ratios):
                if abs(r - mean_r) / mean_r > 0.05:
                    outlier_x.append(i)
                    outlier_y.append(r)
            if outlier_x:
                outliers = pg.ScatterPlotItem(
                    x=outlier_x, y=outlier_y,
                    size=12, symbol='o',
                    pen=pg.mkPen('#EF4444', width=2),
                    brush=pg.mkBrush('#EF4444'))
                self._rep_plot.addItem(outliers)

        mean_line = pg.InfiniteLine(
            pos=mean_r, angle=0,
            pen=pg.mkPen('#EF4444', width=2),
            label=f'Mean = {mean_r:.6f}',
            labelOpts={'position': 0.9, 'color': '#EF4444', 'movable': True})
        self._rep_plot.addItem(mean_line)

        cert = self._rep_certified.value()

        # ── Right Y-axis: Correction Factor (CF) ─────────────────────
        e1 = self.elem1.currentText() if hasattr(self, 'elem1') else self._cfg.get('element1', '')
        e2 = self.elem2.currentText() if hasattr(self, 'elem2') else self._cfg.get('element2', '')
        m_i = _mass_of(e1)
        m_j = _mass_of(e2)
        m_std_num = _mass_of(ref_num)
        m_std_den = _mass_of(ref_den)

        cf_values = None
        can_compute_cf = (
            cert > 0 and abs(cert - 1.0) > 1e-9
            and m_i and m_j and m_std_num and m_std_den
            and m_i > 0 and m_j > 0 and m_std_num > 0 and m_std_den > 0
        )

        if not can_compute_cf:
            missing = []
            if cert <= 0 or abs(cert - 1.0) <= 1e-9:
                missing.append(f"certified ratio = {cert:.6f} (must be ≠ 1.0)")
            if not m_i or m_i <= 0:
                missing.append(f"cannot extract mass from numerator '{e1}'")
            if not m_j or m_j <= 0:
                missing.append(f"cannot extract mass from denominator '{e2}'")
            if not m_std_num or m_std_num <= 0:
                missing.append(f"cannot extract mass from ref numerator '{ref_num}'")
            if not m_std_den or m_std_den <= 0:
                missing.append(f"cannot extract mass from ref denominator '{ref_den}'")
            cf_diagnostic = "CF axis not shown: " + "; ".join(missing)
        else:
            cf_diagnostic = None
            cf_values = []
            for r_m in ratios:
                if r_m > 0:
                    try:
                        p = math.log(cert / r_m) / math.log(m_std_num / m_std_den)
                        cf = (m_i / m_j) ** p
                        cf_values.append(cf)
                    except (ValueError, ZeroDivisionError):
                        cf_values.append(np.nan)
                else:
                    cf_values.append(np.nan)
            cf_values = np.array(cf_values)

        if cf_values is not None and np.any(~np.isnan(cf_values)):
            pi = self._rep_plot.getPlotItem()
            self._cf_vb = pg.ViewBox()
            pi.showAxis('right')
            pi.scene().addItem(self._cf_vb)
            pi.getAxis('right').linkToView(self._cf_vb)
            self._cf_vb.setXLink(pi)

            pi.getAxis('right').setLabel(
                'Correction Factor (CF)',
                color='#F97316',
                **{'font-size': '11pt'})
            pi.getAxis('right').setPen(pg.mkPen('#F97316', width=1.5))
            pi.getAxis('right').setTextPen(pg.mkPen('#F97316'))

            cf_line = pg.PlotDataItem(
                x=x, y=cf_values,
                pen=pg.mkPen('#F97316', width=2, style=Qt.DashLine),
                symbol='s', symbolSize=8,
                symbolPen=pg.mkPen('#F97316', width=1),
                symbolBrush=pg.mkBrush('#F97316'))
            self._cf_vb.addItem(cf_line)

            cf_one_line = pg.InfiniteLine(
                pos=1.0, angle=0,
                pen=pg.mkPen('#F97316', width=1, style=Qt.DotLine))
            self._cf_vb.addItem(cf_one_line)

            def update_cf_views():
                self._cf_vb.setGeometry(pi.vb.sceneBoundingRect())
                self._cf_vb.linkedViewChanged(pi.vb, self._cf_vb.XAxis)

            pi.vb.sigResized.connect(update_cf_views)
            update_cf_views()

        ax = self._rep_plot.getAxis('bottom')
        ax.setTicks([[(i, n) for i, n in enumerate(valid_names)]])

        if len(valid_names) > 6:
            ax.setStyle(tickTextOffset=10)
            font = ax.tickFont if hasattr(ax, 'tickFont') and ax.tickFont else None
            if font is None:
                from PySide6.QtGui import QFont as QF
                font = QF()
            font.setPointSize(8)
            ax.setTickFont(font)

        self._rep_plot.setLabel('left', f'{ref_num} / {ref_den}')
        self._rep_plot.setLabel('bottom', 'Individual Replicate')

        # ── Stats summary ─────────────────────────────────────────────
        std_r = float(np.std(ratios_arr))
        rsd = (std_r / mean_r * 100) if mean_r > 0 else 0
        median_r = float(np.median(ratios_arr))
        r_min = float(np.min(ratios_arr))
        r_max = float(np.max(ratios_arr))

        info_lines = [
            f"Replicates: {len(ratios)}  |  "
            f"Mean: {mean_r:.6f}  |  Median: {median_r:.6f}  |  "
            f"Std: {std_r:.6f}  |  RSD: {rsd:.2f}%",
            f"Range: [{r_min:.6f} — {r_max:.6f}]",
        ]
        if cert > 0 and abs(cert - 1.0) > 1e-9:
            bias = ((mean_r - cert) / cert) * 100
            info_lines.append(
                f"Bias vs certified: {bias:+.3f}%")

        if cf_values is not None and np.any(~np.isnan(cf_values)):
            valid_cf = cf_values[~np.isnan(cf_values)]
            mean_cf = float(np.mean(valid_cf))
            std_cf = float(np.std(valid_cf))
            info_lines.append(
                f"CF ({e1}/{e2}):  Mean = {mean_cf:.6f}  |  Std = {std_cf:.6f}  |  "
                f"Range: [{float(np.min(valid_cf)):.6f} — {float(np.max(valid_cf)):.6f}]")
        elif cf_diagnostic:
            info_lines.append(cf_diagnostic)

        self._rep_info.setText("\n".join(info_lines))

    @staticmethod
    def _ratio_from_sample_ts(pw, sample_ts, ref_num_label, ref_den_label):
        """Compute ref ratio from time-series data for a single sample."""
        if not hasattr(pw, 'selected_isotopes'):
            return None
        num_key = den_key = None
        for el, isos in pw.selected_isotopes.items():
            for iso in isos:
                ek = f"{el}-{iso:.4f}"
                lbl = (pw.get_formatted_label(ek)
                       if hasattr(pw, 'get_formatted_label')
                       else f"{round(iso)}{el}")
                if lbl == ref_num_label:
                    if hasattr(pw, 'find_closest_isotope'):
                        num_key = pw.find_closest_isotope(iso)
                if lbl == ref_den_label:
                    if hasattr(pw, 'find_closest_isotope'):
                        den_key = pw.find_closest_isotope(iso)
        if (num_key and den_key
                and num_key in sample_ts and den_key in sample_ts):
            mn = float(np.mean(sample_ts[num_key]))
            md = float(np.mean(sample_ts[den_key]))
            if md > 0:
                return mn / md
        return None

    def _auto_compute_ref_measured(self):
        """Compute the measured reference ratio.

        FIX (batch windows): When the parent window lookup fails (which
        happens in batch mode because the parent window may not contain
        all batch samples), fall back to computing from the node's input
        particle data, which contains particles from ALL batch windows.
        Also searches all open windows for time-series data.
        """
        num_label = self.ref_num.currentText().strip()
        den_label = self.ref_den.currentText().strip()
        if not num_label or not den_label:
            self.ref_info_label.setText("Select reference numerator and denominator first.")
            return

        pw = self._parent_window

        # 1. Try parent window time-series (original behavior)
        if pw:
            ratio, info = compute_ratio_from_mean_signals(pw, num_label, den_label)
            if ratio is not None:
                self.ref_measured.setValue(ratio)
                self.ref_info_label.setText(f"{num_label}/{den_label} = {ratio:.6f}\n{info}")
                return

        # 2. Fallback: compute from node's input particle data
        #    (works for batch mode since input_data has all particles)
        node = self._node
        if node and hasattr(node, 'input_data') and node.input_data:
            dk = DATA_KEY_MAPPING.get(
                self._cfg.get('data_type_display', 'Counts'), 'elements')
            particles = node.input_data.get('particle_data', [])

            # If a specific sample is selected in the dropdown, filter to it
            selected_sample = self.exp_ref_sample.currentText()
            if selected_sample and selected_sample != '(All samples merged)':
                particles = [p for p in particles
                             if p.get('source_sample', '') == selected_sample
                             or p.get('original_sample', '') == selected_sample]

            if particles:
                num_vals = [p.get(dk, p.get('elements', {})).get(num_label, 0)
                            for p in particles]
                den_vals = [p.get(dk, p.get('elements', {})).get(den_label, 0)
                            for p in particles]
                num_vals = [v for v in num_vals if v > 0]
                den_vals = [v for v in den_vals if v > 0]
                if num_vals and den_vals:
                    ratio = float(np.mean(num_vals)) / float(np.mean(den_vals))
                    self.ref_measured.setValue(ratio)
                    src = selected_sample if selected_sample != '(All samples merged)' else 'all samples'
                    self.ref_info_label.setText(
                        f"{num_label}/{den_label} = {ratio:.6f}\n"
                        f"Computed from {len(num_vals)} particles ({src})")
                    return

        # 3. Fallback: search ALL open windows for time-series data
        app = QApplication.instance()
        if app and hasattr(app, 'main_windows'):
            for w in app.main_windows:
                if w is pw:
                    continue
                ratio, info = compute_ratio_from_mean_signals(w, num_label, den_label)
                if ratio is not None:
                    self.ref_measured.setValue(ratio)
                    self.ref_info_label.setText(
                        f"{num_label}/{den_label} = {ratio:.6f}\n{info}\n"
                        f"(from another open window)")
                    return

        self.ref_info_label.setText(
            "No data found in parent window, node input, or other open windows.")

    def _pick_single_color(self):
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self._single_color, self, "Marker Color")
        if color.isValid():
            self._single_color = color
            self._single_color_btn.setStyleSheet(
                f"background-color: {color.name()}; min-height: 25px; border: 1px solid black;")

    def _pick_sample_color(self, name, btn):
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._color_btns[name][1])
        c = QColorDialog.getColor(cur, self, f"Color for {name}")
        if c.isValid():
            btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid black;")
            self._color_btns[name] = (btn, c.name())

    def collect(self) -> dict:
        out = dict(self._cfg)
        out['data_type_display'] = self.data_type.currentText()
        out['element1'] = self.elem1.currentText()
        out['element2'] = self.elem2.currentText()
        out['x_axis_element'] = self.x_elem.currentText()
        out['color_element'] = self.color_elem.currentText()

        out['per_sample_correction'] = self.per_sample_cb.isChecked()
        out['sample_correction_configs'] = dict(self._sample_corr_cfgs)

        out['correction_method'] = self.correction_method.currentText()
        out['ref_isotope_num'] = self.ref_num.currentText()
        out['ref_isotope_den'] = self.ref_den.currentText()
        out['ref_certified_ratio'] = self.ref_certified.value()
        out['ref_measured_ratio'] = self.ref_measured.value()
        out['exp_ref_sample'] = self.exp_ref_sample.currentText()

        out['show_natural_line'] = self.show_natural.isChecked()
        out['show_standard_line'] = self.show_standard.isChecked()
        out['show_mean_line'] = self.show_mean.isChecked()

        out['show_confidence_intervals'] = self.show_ci.isChecked()

        out['filter_zeros'] = self.filter_zeros.isChecked()
        out['filter_saturated'] = self.filter_sat.isChecked()
        out['saturation_threshold'] = self.sat_thresh.value()

        out['log_x'] = self.log_x.isChecked()
        out['log_y'] = self.log_y.isChecked()
        out['x_max'] = self.x_max.value()

        out['marker_size'] = self.marker_size.value()
        out['marker_alpha'] = self.marker_alpha.value()

        if not self._is_multi:
            out['single_sample_color'] = self._single_color.name()

        if self._is_multi:
            out['display_mode'] = self.display_mode.currentText()
            sc = {}
            for sn, (btn, c) in self._color_btns.items():
                sc[sn] = c
            out['sample_colors'] = sc
            nm = {}
            for sn, ne in self._name_edits.items():
                nm[sn] = ne.text()
            out['sample_name_mappings'] = nm

        out.update(self._font_group.collect())
        return out


# ═══════════════════════════════════════════════
# Display Dialog (right-click context menu)
# ═══════════════════════════════════════════════

class IsotopicRatioDisplayDialog(QDialog):
    def __init__(self, isotopic_ratio_node, parent_window=None):
        super().__init__(parent_window)
        self.node = isotopic_ratio_node
        self.parent_window = parent_window
        self.setWindowTitle("Isotopic Ratio Analysis")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._setup_ui()
        self._cached_elements = []       
        self._auto_calc_natural()
        self._auto_calc_standard()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _is_multi(self) -> bool:
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _available_elements(self) -> list:
        if self._cached_elements:
            return self._cached_elements
        sel = (self.node.input_data or {}).get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    def _all_isotope_labels(self) -> list:
        return get_all_isotope_labels(self.parent_window)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.plot_widget)


    def _auto_calc_natural(self):
        try:
            e1 = self.node.config.get('element1', '')
            e2 = self.node.config.get('element2', '')
            if not e1 or not e2:
                return

            from results.results_periodic import CompactPeriodicTableWidget
            pt = CompactPeriodicTableWidget()
            elements = pt.get_elements()

            a1 = a2 = None
            for elem in elements:
                for iso in elem['isotopes']:
                    if isinstance(iso, dict):
                        if iso.get('label') == e1:
                            a1 = iso.get('abundance', 0)
                        elif iso.get('label') == e2:
                            a2 = iso.get('abundance', 0)

            if a1 and a2 and a1 > 0 and a2 > 0:
                self.node.config['natural_ratio'] = a1 / a2
        except Exception:
            pass

    def _auto_calc_standard(self):
        try:
            pw = self.parent_window
            if not pw or not hasattr(pw, 'calibration_results'):
                return
            e1 = self.node.config.get('element1', '')
            e2 = self.node.config.get('element2', '')
            if not e1 or not e2:
                return

            ionic = pw.calibration_results.get("Ionic Calibration", {})
            if not ionic:
                return

            def _find_key(label):
                if not hasattr(pw, 'selected_isotopes'):
                    return None
                for el, isos in pw.selected_isotopes.items():
                    for iso in isos:
                        k = f"{el}-{iso:.4f}"
                        if hasattr(pw, 'get_formatted_label') and pw.get_formatted_label(k) == label:
                            return k
                return None

            def _get_slope(cal, key):
                prefs = getattr(pw, 'isotope_method_preferences', {})
                pref = prefs.get(key, 'Force through zero')
                mmap = {'Force through zero': 'zero', 'Simple linear': 'simple',
                        'Weighted': 'weighted', 'Manual': 'manual'}
                mk = mmap.get(pref, 'zero')
                md = cal.get(mk)
                if md and 'slope' in md:
                    return md['slope']
                for fb in ['weighted', 'simple', 'zero', 'manual']:
                    md = cal.get(fb)
                    if md and 'slope' in md:
                        return md['slope']
                return None

            k1, k2 = _find_key(e1), _find_key(e2)
            if not k1 or not k2:
                return
            s1, s2 = _get_slope(ionic.get(k1, {}), k1), _get_slope(ionic.get(k2, {}), k2)
            if s1 and s2 and s1 > 0 and s2 > 0:
                self.node.config['standard_ratio'] = s1 / s2
        except Exception:
            pass

    def _show_context_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Log X-axis", 'log_x')
        self._add_toggle(toggle_menu, "Log Y-axis", 'log_y')
        self._add_toggle(toggle_menu, "Poisson 95% CI", 'show_confidence_intervals')
        self._add_toggle(toggle_menu, "Natural Abundance Line", 'show_natural_line')
        self._add_toggle(toggle_menu, "Standard Ratio Line", 'show_standard_line')
        self._add_toggle(toggle_menu, "Mean Ratio Line", 'show_mean_line')
        self._add_toggle(toggle_menu, "Filter Zeros", 'filter_zeros')
        self._add_toggle(toggle_menu, "Filter Saturated", 'filter_saturated')
        self._add_toggle(toggle_menu, "Per-Sample Correction", 'per_sample_correction')

        dt_menu = menu.addMenu("Data Type")
        current_dt = cfg.get('data_type_display', 'Counts')
        for dt in DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == current_dt)
            a.triggered.connect(lambda _, d=dt: self._set_data_type(d))

        elems = self._available_elements()
        if elems:
            e1_menu = menu.addMenu("Numerator (A)")
            for e in elems:
                a = e1_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('element1'))
                a.triggered.connect(lambda _, el=e: self._set_elem('element1', el))

            e2_menu = menu.addMenu("Denominator (B)")
            for e in elems:
                a = e2_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('element2'))
                a.triggered.connect(lambda _, el=e: self._set_elem('element2', el))

            xa_menu = menu.addMenu("X-axis Element")
            for e in elems:
                a = xa_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('x_axis_element'))
                a.triggered.connect(lambda _, el=e: self._set_elem('x_axis_element', el))

            ce_menu = menu.addMenu("Color Element (3rd)")
            a_none = ce_menu.addAction("(None — solid color)")
            a_none.setCheckable(True)
            a_none.setChecked(not cfg.get('color_element'))
            a_none.triggered.connect(lambda _: self._set_elem('color_element', ''))
            ce_menu.addSeparator()
            for e in elems:
                a = ce_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('color_element'))
                a.triggered.connect(lambda _, el=e: self._set_elem('color_element', el))

        if not cfg.get('per_sample_correction', False):
            cm_menu = menu.addMenu("Isotope Correction (Global)")
            cur_method = cfg.get('correction_method', 'None')
            for m in CORRECTION_METHODS:
                a = cm_menu.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur_method)
                a.triggered.connect(lambda _, method=m: self._set_correction(method))

        if self._is_multi():
            dm_menu = menu.addMenu("Display Mode")
            cur = cfg.get('display_mode', DISPLAY_MODES[0])
            for m in DISPLAY_MODES:
                a = dm_menu.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set_display_mode(mode))

        menu.addSeparator()

        settings_action = menu.addAction("⚙  Configure…")
        settings_action.triggered.connect(self._open_settings)

        dl_action = menu.addAction("💾 Download Figure…")
        dl_action.triggered.connect(self._download_figure)

        menu.exec(QCursor.pos())
    
    def _download_figure(self):
        csv_data = self._build_csv_data()
        download_pyqtgraph_figure(
            self.plot_widget, self, "isotopic_ratio",
            csv_data=csv_data)

    def _add_toggle(self, menu, label, key):
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(self.node.config.get(key, False))
        a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

    def _toggle(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _set_data_type(self, dt):
        self.node.config['data_type_display'] = dt
        self._refresh()

    def _set_elem(self, key, elem):
        self.node.config[key] = elem
        self._refresh()

    def _set_correction(self, method):
        self.node.config['correction_method'] = method
        self._refresh()

    def _set_display_mode(self, mode):
        self.node.config['display_mode'] = mode
        self._refresh()

    def _open_settings(self):
        dlg = IsotopeSettingsDialog(
            self.node.config, self._available_elements(),
            self._all_isotope_labels(),
            self._is_multi(), self._sample_names(),
            self.parent_window, self,
            node=self.node)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._auto_calc_natural()
            self._auto_calc_standard()
            self._refresh()

    def _refresh(self):
        self.plot_widget.clear()
        plot_data = self.node.extract_plot_data()

        if not plot_data:
            self._cached_elements = []
            pi = self.plot_widget.addPlot()
            ti = pg.TextItem(
                "No particle data available\nConnect to Sample Selector and Isotope Filter",
                anchor=(0.5, 0.5), color='gray')
            pi.addItem(ti)
            ti.setPos(0.5, 0.5)
            pi.hideAxis('left')
            pi.hideAxis('bottom')
            return

        try:
            if self._is_multi():
                elems = set()
                for sd in plot_data.values():
                    if isinstance(sd, dict) and 'element_data' in sd:
                        cols = sd['element_data'].columns
                        elems.update(c for c in cols if not c.startswith('_'))
                self._cached_elements = sorted(elems)
            elif 'element_data' in plot_data:
                self._cached_elements = [
                    c for c in plot_data['element_data'].columns
                    if not c.startswith('_')]
        except Exception:
            self._cached_elements = []

        cfg = self.node.config

        if self._is_multi():
            mode = cfg.get('display_mode', DISPLAY_MODES[0])
            if mode == 'Individual Subplots':
                self._draw_subplots(plot_data, cfg)
            elif mode == 'Side by Side Subplots':
                self._draw_side_by_side(plot_data, cfg)
            else:
                pi = self.plot_widget.addPlot(row=0, col=0)
                self._draw_combined(pi, plot_data, cfg)
        else:
            pi = self.plot_widget.addPlot(row=0, col=0)
            self._draw_single(pi, plot_data, cfg)

    def _prepare_sample(self, element_data, cfg, sample_name=None):
        eff_cfg = get_sample_correction_config(cfg, sample_name)

        e1 = cfg.get('element1', '')
        e2 = cfg.get('element2', '')
        x_elem = cfg.get('x_axis_element', e2)
        color_elem = cfg.get('color_element', '')

        if not e1 or not e2:
            return None
        if e1 not in element_data.columns or e2 not in element_data.columns:
            return None

        meta_cols = [c for c in ['_source_sample', '_original_sample'] if c in element_data.columns]
        meta_data = element_data[meta_cols]
        numeric_data = element_data.drop(columns=meta_cols)

        df = apply_saturation_filter(numeric_data, cfg)
        if df.empty:
            return None

        for col in meta_cols:
            df[col] = meta_data[col]

        if cfg.get('filter_zeros', True):
            mask = (df[e1] > 0) & (df[e2] > 0)
            df = df[mask]
                    
        if len(df) == 0:
            return None

        ratios = (df[e1] / df[e2]).values

        method = eff_cfg.get('correction_method', 'None')
        corr_col = '_original_sample' if '_original_sample' in df.columns else '_source_sample'
        if method != 'None' and corr_col in df.columns:
            sources = df[corr_col].values
            unique_sources = set(s for s in sources if s)
            if len(unique_sources) > 1:
                ratios = self._correct_per_replicate(
                    df, ratios, eff_cfg, e1, e2, sources)
            else:
                ratios = apply_isotope_correction(ratios, eff_cfg)
        else:
            ratios = apply_isotope_correction(ratios, eff_cfg)

        if x_elem in df.columns:
            x = df[x_elem].values
        else:
            x = df[e2].values

        corrected_linear = ratios.copy()
        mean_raw = float(np.mean((df[e1] / df[e2]).values))

        color_values = None
        if color_elem and color_elem in df.columns:
            raw_colors = df[color_elem].values.astype(float)
            color_values = np.full_like(raw_colors, np.nan)
            valid_c = raw_colors > 0
            color_values[valid_c] = np.log10(raw_colors[valid_c])

        if cfg.get('log_x', False):
            mask = x > 0
            x, ratios = x[mask], ratios[mask]
            if color_values is not None:
                color_values = color_values[mask]
            if len(x) == 0:
                return None
            x = np.log10(x)

        if cfg.get('log_y', False):
            mask = ratios > 0
            x, ratios = x[mask], ratios[mask]
            if color_values is not None:
                color_values = color_values[mask]
            if len(ratios) == 0:
                return None
            ratios = np.log10(ratios)

        return x, ratios, len(element_data), color_values, corrected_linear, mean_raw
    
    def _build_csv_data(self) -> pd.DataFrame | None:
        """Build a DataFrame of per-particle isotopic ratio data for CSV export."""
        
        
        plot_data = self.node.extract_plot_data()
        if not plot_data:
            return None

        cfg = self.node.config
        e1 = cfg.get('element1', '')
        e2 = cfg.get('element2', '')
        x_elem = cfg.get('x_axis_element', e2)
        dk = DATA_KEY_MAPPING.get(cfg.get('data_type_display', 'Counts'), 'elements')
        dt = cfg.get('data_type_display', 'Counts')

        rows = []

        if self._is_multi():
            for sn, sd in plot_data.items():
                if not sd or 'element_data' not in sd:
                    continue
                result = self._prepare_sample(sd['element_data'], cfg, sample_name=sn)
                if result is None:
                    continue
                x, ratios, n_total, color_values, corrected_linear, mean_raw = result
                
                # Get raw element data for additional columns
                edf = sd['element_data']
                meta_cols = [c for c in edf.columns if c.startswith('_')]
                numeric_cols = [c for c in edf.columns if not c.startswith('_')]
                
                for i in range(len(corrected_linear)):
                    row = {
                        'Sample': get_display_name(sn, cfg),
                        f'{e1}/{e2} (corrected)': corrected_linear[i],
                        f'{x_elem} ({dt})': x[i] if not cfg.get('log_x') else 10**x[i],
                    }
                    # Add all raw element columns
                    if i < len(edf):
                        for col in numeric_cols:
                            row[f'{col} ({dt})'] = edf.iloc[i][col]
                    rows.append(row)
        else:
            edf = plot_data.get('element_data')
            if edf is None:
                return None
            sample_key = "(Current Sample)" if cfg.get('per_sample_correction') else None
            result = self._prepare_sample(edf, cfg, sample_name=sample_key)
            if result is None:
                return None
            x, ratios, n_total, color_values, corrected_linear, mean_raw = result
            
            numeric_cols = [c for c in edf.columns if not c.startswith('_')]
            
            for i in range(len(corrected_linear)):
                row = {
                    f'{e1}/{e2} (corrected)': corrected_linear[i],
                    f'{x_elem} ({dt})': x[i] if not cfg.get('log_x') else 10**x[i],
                }
                if i < len(edf):
                    for col in numeric_cols:
                        row[f'{col} ({dt})'] = edf.iloc[i][col]
                rows.append(row)

        return pd.DataFrame(rows) if rows else None

    def _correct_per_replicate(self, df, ratios, eff_cfg, e1, e2, sources):
        """Apply per-replicate exponential correction.
        
        FIX 1: Now computes the reference ratio directly from the particle
        data in the DataFrame for each replicate, instead of only looking
        up the parent window (which may not have per-replicate data keyed
        by the correct sample name, causing all replicates to get the same
        fallback ratio).
        """
        ref_num_label = eff_cfg.get('ref_isotope_num', '')
        ref_den_label = eff_cfg.get('ref_isotope_den', '')
        R_T_std = eff_cfg.get('ref_certified_ratio', 1.0)
        m_i = _mass_of(eff_cfg.get('element1', e1))
        m_j = _mass_of(eff_cfg.get('element2', e2))
        m_std_num = _mass_of(ref_num_label)
        m_std_den = _mass_of(ref_den_label)

        if not all(v and v > 0 for v in [m_i, m_j, m_std_num, m_std_den, R_T_std]):
            return apply_isotope_correction(ratios, eff_cfg)

        corrected = ratios.copy()
        unique_sources = set(s for s in sources if s)

        for src in unique_sources:
            mask = sources == src
            if not np.any(mask):
                continue

            R_M_std = None

            # ── FIX 1: Compute ref ratio directly from df particles ──
            if ref_num_label in df.columns and ref_den_label in df.columns:
                src_df = df[mask]
                num_vals = src_df[ref_num_label].values.astype(float)
                den_vals = src_df[ref_den_label].values.astype(float)
                valid = (num_vals > 0) & (den_vals > 0)
                if np.any(valid):
                    R_M_std = float(np.mean(num_vals[valid])) / float(np.mean(den_vals[valid]))

            # Fallback: try parent window lookup AND all other windows
            if R_M_std is None or R_M_std <= 0:
                R_M_std = self._compute_replicate_ref_ratio(
                    src, ref_num_label, ref_den_label)

            # Last resort: use global measured ratio from config
            if R_M_std is None or R_M_std <= 0:
                R_M_std = eff_cfg.get('ref_measured_ratio', 1.0)
                if R_M_std <= 0:
                    continue

            try:
                p = math.log(R_T_std / R_M_std) / math.log(m_std_num / m_std_den)
                cf = (m_i / m_j) ** p
                corrected[mask] = ratios[mask] * cf
            except (ValueError, ZeroDivisionError):
                pass

        return corrected

    def _compute_replicate_ref_ratio(self, sample_name, ref_num_label, ref_den_label):
        """Compute the reference ratio for a specific replicate sample.

        FIX (batch windows): Now searches ALL open windows — not just
        self.parent_window — using both the exact sample name and the
        stripped batch name (e.g., 'SampleA' from 'SampleA [W1]').
        """
        original_name = _strip_batch_suffix(sample_name)
        names_to_try = [sample_name]
        if original_name != sample_name:
            names_to_try.append(original_name)

        # Build list of all windows to search
        windows_to_search = []
        if self.parent_window:
            windows_to_search.append(self.parent_window)
        app = QApplication.instance()
        if app and hasattr(app, 'main_windows'):
            for w in app.main_windows:
                if w not in windows_to_search:
                    windows_to_search.append(w)

        # Try particle data across all windows
        dk = DATA_KEY_MAPPING.get(
            self.node.config.get('data_type_display', 'Counts'), 'elements')

        for w in windows_to_search:
            if not hasattr(w, 'sample_particle_data'):
                continue
            for try_name in names_to_try:
                particles = w.sample_particle_data.get(try_name, [])
                if particles:
                    num_vals = [p.get(dk, p.get('elements', {})).get(ref_num_label, 0)
                                for p in particles]
                    den_vals = [p.get(dk, p.get('elements', {})).get(ref_den_label, 0)
                                for p in particles]
                    num_vals = [v for v in num_vals if v > 0]
                    den_vals = [v for v in den_vals if v > 0]
                    if num_vals and den_vals:
                        return float(np.mean(num_vals)) / float(np.mean(den_vals))

        # Try time-series data across all windows
        for w in windows_to_search:
            if not hasattr(w, 'data_by_sample') or not hasattr(w, 'selected_isotopes'):
                continue
            # Also try sample_data dict
            for data_attr in ('data_by_sample', 'sample_data'):
                data_dict = getattr(w, data_attr, None)
                if not isinstance(data_dict, dict):
                    continue
                for try_name in names_to_try:
                    sample_ts = data_dict.get(try_name)
                    if sample_ts:
                        result = self._ratio_from_time_series(
                            w, sample_ts, ref_num_label, ref_den_label)
                        if result is not None:
                            return result

        return None

    def _ratio_from_time_series(self, pw, sample_ts, ref_num_label, ref_den_label):
        if not hasattr(pw, 'selected_isotopes'):
            return None
        num_key = den_key = None
        for el, isos in pw.selected_isotopes.items():
            for iso in isos:
                ek = f"{el}-{iso:.4f}"
                lbl = (pw.get_formatted_label(ek)
                       if hasattr(pw, 'get_formatted_label') else f"{round(iso)}{el}")
                if lbl == ref_num_label:
                    if hasattr(pw, 'find_closest_isotope'):
                        num_key = pw.find_closest_isotope(iso)
                if lbl == ref_den_label:
                    if hasattr(pw, 'find_closest_isotope'):
                        den_key = pw.find_closest_isotope(iso)
        if num_key and den_key and num_key in sample_ts and den_key in sample_ts:
            mn = float(np.mean(sample_ts[num_key]))
            md = float(np.mean(sample_ts[den_key]))
            if md > 0:
                return mn / md
        return None

    def _build_labels(self, cfg, sample_name=None):
        e1 = cfg.get('element1', '')
        e2 = cfg.get('element2', '')
        x_elem = cfg.get('x_axis_element', e2)
        dt = cfg.get('data_type_display', 'Counts')

        eff_cfg = get_sample_correction_config(cfg, sample_name)
        method = eff_cfg.get('correction_method', 'None')

        x_label = f"{x_elem} ({dt})"

        y_base = f"Ratio {e1}/{e2}"
        if method != 'None':
            y_base += f" (corrected)"
        y_label = y_base

        return x_label, y_label

    def _add_scatter(self, pi, x, y, cfg, color, color_values=None):
        size = cfg.get('marker_size', 8)
        alpha = int(cfg.get('marker_alpha', 0.7) * 255)
        pen = pg.mkPen(color='black', width=0.5)

        if color_values is not None and len(color_values) == len(x):
            cmap = make_jet_colormap()
            
            valid_mask = ~np.isnan(color_values)
            if np.any(valid_mask):
                vmin = float(np.nanmin(color_values[valid_mask]))
                vmax = float(np.nanmax(color_values[valid_mask]))
            else:
                vmin, vmax = 0.0, 1.0
                
            if vmax <= vmin:
                vmax = vmin + 1.0

            normalized = (color_values - vmin) / (vmax - vmin)
            normalized = np.clip(normalized, 0.0, 1.0)

            lut = cmap.getLookupTable(nPts=256)
            
            brushes = []
            default_brush = pg.mkBrush(180, 180, 180, alpha)

            for val in normalized:
                if np.isnan(val):
                    brushes.append(default_brush)
                else:
                    idx_val = int(val * 255)
                    idx_val = max(0, min(255, idx_val))
                    rgb = lut[idx_val]
                    brushes.append(pg.mkBrush(int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha))

            scatter = pg.ScatterPlotItem(
                x=x, y=y, size=size, pen=pen, brush=brushes)
            pi.addItem(scatter)
            
            if np.any(valid_mask):
                return scatter, vmin, vmax
            else:
                return scatter, None, None
        else:
            c = QColor(color)
            brush = pg.mkBrush(c.red(), c.green(), c.blue(), alpha)
            scatter = pg.ScatterPlotItem(
                x=x, y=y, size=size, pen=pen, brush=brush)
            pi.addItem(scatter)
            return scatter, None, None

    def _add_inset_colorbar(self, pi, cfg, vmin, vmax):
        color_elem = cfg.get('color_element', '')
        dt = cfg.get('data_type_display', 'Counts')
        
        # Label specifies log10 transformation
        label_text = f"log10 {color_elem} ({dt})"
        
        cbar = InsetColorBarItem(label_text)
        cbar.setParentItem(pi.vb)
        
        # Keep legend anchored right
        def update_pos():
            rect = pi.vb.boundingRect()
            cbar.setPos(rect.width() - 190, 15)
            
        pi.vb.sigResized.connect(update_pos)
        update_pos()

    def _add_poisson_ci(self, pi, cfg, mean_ratio, color, x_data=None, sample_name=None):
        if not cfg.get('show_confidence_intervals', True):
            return

        log_x = cfg.get('log_x', False)
        log_y = cfg.get('log_y', False)
        dt = cfg.get('data_type_display', 'Counts')

        R = mean_ratio
        if R <= 0:
            return

        if x_data is not None and len(x_data) > 0:
            x_min = float(np.min(x_data))
            x_max = float(np.max(x_data))
            margin = (x_max - x_min) * 0.05 if x_max > x_min else 1.0
            x_min -= margin
            x_max += margin
        else:
            x_min, x_max = 1, 10000

        x_range = np.linspace(x_min, x_max, 200)

        if log_x:
            linear_x = 10.0 ** x_range
        else:
            linear_x = x_range.copy()

        if dt == 'Counts':
            lambda_B = np.maximum(linear_x, 1.0)
        elif 'Mass' in dt:
            lambda_B = np.maximum(linear_x * 100.0, 1.0)
        elif 'Moles' in dt:
            lambda_B = np.maximum(linear_x * 10000.0, 1.0)
        else:
            lambda_B = np.maximum(linear_x, 1.0)

        upper, lower = poisson_ci_curves(R, lambda_B, k=2.0)

        eff_cfg = get_sample_correction_config(cfg, sample_name)
        cf = get_correction_factor(eff_cfg)
        upper = upper * cf
        lower = lower * cf

        if log_y:
            upper = np.where(upper > 0, np.log10(upper), np.nan)
            lower = np.where(lower > 0, np.log10(lower), np.nan)

        c = QColor(color)
        pen_rgba = (c.red(), c.green(), c.blue(), 180)
        pi.addItem(pg.PlotDataItem(x=x_range, y=upper,
                                   pen=pg.mkPen(color=pen_rgba, width=1.5)))
        pi.addItem(pg.PlotDataItem(x=x_range, y=lower,
                                   pen=pg.mkPen(color=pen_rgba, width=1.5)))

    def _make_legend_proxy(self, color, style='solid', width=2):
        pen_style = Qt.SolidLine if style == 'solid' else Qt.DashLine
        return pg.PlotDataItem(
            x=[0, 1], y=[0, 0],
            pen=pg.mkPen(color=color, style=pen_style, width=width))

    def _add_reference_lines(self, pi, cfg, ratios_linear, legend_items, sample_name=None):
        log_y = cfg.get('log_y', False)
        eff_cfg = get_sample_correction_config(cfg, sample_name)
        method = eff_cfg.get('correction_method', 'None')
        cf = get_correction_factor(eff_cfg) if method != 'None' else 1.0

        if cfg.get('show_natural_line', False):
            nat = cfg.get('natural_ratio', 0)
            if nat and nat > 0:
                display = np.log10(nat) if log_y else nat
                pi.addItem(pg.InfiniteLine(
                    pos=display, angle=0,
                    pen=pg.mkPen(color='blue', style=Qt.DashLine, width=2)))
                legend_items.append(
                    (self._make_legend_proxy('blue', 'dash'), f"Natural: {nat:.4f}"))

        if cfg.get('show_standard_line', False):
            std = cfg.get('standard_ratio', 0)
            if std and std > 0:
                corrected_std = std * cf
                display = np.log10(corrected_std) if (log_y and corrected_std > 0) else corrected_std
                pi.addItem(pg.InfiniteLine(
                    pos=display, angle=0,
                    pen=pg.mkPen(color='green', style=Qt.DashLine, width=2)))
                legend_items.append(
                    (self._make_legend_proxy('green', 'dash'), f"Standard: {corrected_std:.4f}"))

        if cfg.get('show_mean_line', True) and len(ratios_linear) > 0:
            mean_r = np.mean(ratios_linear)
            display = np.log10(mean_r) if (log_y and mean_r > 0) else mean_r
            pi.addItem(pg.InfiniteLine(
                pos=display, angle=0,
                pen=pg.mkPen(color='red', width=2)))
            legend_items.append(
                (self._make_legend_proxy('red', 'solid'), f"Mean: {mean_r:.4f}"))

    def _apply_labels_and_font(self, pi, cfg, x_label=None, y_label=None, sample_name=None):
        if x_label is None or y_label is None:
            x_label, y_label = self._build_labels(cfg, sample_name)
        set_axis_labels(pi, x_label, y_label, cfg)
        apply_font_to_pyqtgraph(pi, cfg)

        if cfg.get('log_x'):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)

    def _draw_single(self, pi, plot_data, cfg):
        edf = plot_data.get('element_data')
        if edf is None:
            return

        sample_key = "(Current Sample)" if cfg.get('per_sample_correction', False) else None

        result = self._prepare_sample(edf, cfg, sample_name=sample_key)
        if result is None:
            ti = pg.TextItem("No valid data for selected elements",
                             anchor=(0.5, 0.5), color='gray')
            pi.addItem(ti)
            ti.setPos(0.5, 0.5)
            return

        x, ratios, _, color_values, corrected_linear, mean_raw = result
        color = cfg.get('single_sample_color', '#E74C3C')
        e1, e2 = cfg.get('element1', ''), cfg.get('element2', '')

        scatter, vmin, vmax = self._add_scatter(pi, x, ratios, cfg, color, color_values)
        legend_items = [(scatter, f"Ratio {e1}/{e2}")]

        self._add_poisson_ci(pi, cfg, mean_raw, color, x_data=x, sample_name=sample_key)
        self._add_reference_lines(pi, cfg, corrected_linear, legend_items, sample_name=sample_key)

        legend = pi.addLegend()
        for item, name in legend_items:
            legend.addItem(item, name)

        self._apply_labels_and_font(pi, cfg, sample_name=sample_key)

        # Draw inset element legend colorbar if color element used
        if vmin is not None and vmax is not None:
            self._add_inset_colorbar(pi, cfg, vmin, vmax)

    def _draw_combined(self, pi, plot_data, cfg):
        legend_items = []
        all_corrected = []
        global_vmin, global_vmax = float('inf'), float('-inf')
        has_color = bool(cfg.get('color_element'))

        for i, (sn, sd) in enumerate(plot_data.items()):
            if not sd or 'element_data' not in sd:
                continue
            result = self._prepare_sample(sd['element_data'], cfg, sample_name=sn)
            if result is None:
                continue
            x, ratios, _, color_values, corrected_linear, mean_raw = result
            color = get_sample_color(sn, i, cfg)
            dname = get_display_name(sn, cfg)

            all_corrected.extend(corrected_linear.tolist())

            scatter, vmin, vmax = self._add_scatter(pi, x, ratios, cfg, color, color_values)
            if vmin is not None:
                global_vmin = min(global_vmin, vmin)
                global_vmax = max(global_vmax, vmax)
            legend_items.append((scatter, dname))

            self._add_poisson_ci(pi, cfg, mean_raw, color, x_data=x, sample_name=sn)

        self._add_reference_lines(pi, cfg,
                                  np.array(all_corrected) if all_corrected else np.array([]),
                                  legend_items)

        if legend_items:
            legend = pi.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

        self._apply_labels_and_font(pi, cfg)

        if has_color and global_vmin < global_vmax:
            self._add_inset_colorbar(pi, cfg, global_vmin, global_vmax)

    def _draw_subplots(self, plot_data, cfg):
        samples = list(plot_data.keys())
        n = len(samples)
        cols = min(3, n)
        rows = math.ceil(n / cols)

        for idx, sn in enumerate(samples):
            r, c = idx // cols, idx % cols
            pi = self.plot_widget.addPlot(row=r, col=c)

            sd = plot_data[sn]
            if not sd or 'element_data' not in sd:
                continue

            color = get_sample_color(sn, idx, cfg)
            self._draw_single_on_plot(pi, sd['element_data'], cfg, color, sn)
            pi.setTitle(get_display_name(sn, cfg))

    def _draw_side_by_side(self, plot_data, cfg):
        first_pi = None
        col_idx = 0  
        for sn, sd in plot_data.items():
            if not sd or 'element_data' not in sd:
                continue

            pi = self.plot_widget.addPlot(row=0, col=col_idx)
            color = get_sample_color(sn, col_idx, cfg)
            
            self._draw_single_on_plot(pi, sd['element_data'], cfg, color, sn)
            pi.setTitle(get_display_name(sn, cfg))
            if first_pi is None:
                first_pi = pi
            else:
                pi.setYLink(first_pi)
                pi.getAxis('left').setLabel('') 
                
            col_idx += 1

    def _draw_single_on_plot(self, pi, edf, cfg, color, sample_name):
        result = self._prepare_sample(edf, cfg, sample_name=sample_name)
        if result is None:
            return

        x, ratios, _, color_values, corrected_linear, mean_raw = result

        scatter, vmin, vmax = self._add_scatter(pi, x, ratios, cfg, color, color_values)
        legend_items = [(scatter, get_display_name(sample_name, cfg))]

        self._add_poisson_ci(pi, cfg, mean_raw, color, x_data=x, sample_name=sample_name)
        self._add_reference_lines(pi, cfg, corrected_linear, legend_items, sample_name=sample_name)

        legend = pi.addLegend()
        for item, name in legend_items:
            legend.addItem(item, name)

        self._apply_labels_and_font(pi, cfg, sample_name=sample_name)
        
        if vmin is not None and vmax is not None:
            self._add_inset_colorbar(pi, cfg, vmin, vmax)


# ═══════════════════════════════════════════════
# Node
# ═══════════════════════════════════════════════

class IsotopicRatioPlotNode(QObject):

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'element1': '',
        'element2': '',
        'x_axis_element': '',
        'color_element': '',
        'data_type_display': 'Counts',
        'correction_method': 'None',
        'ref_isotope_num': '',
        'ref_isotope_den': '',
        'ref_certified_ratio': 1.0,
        'ref_measured_ratio': 1.0,
        'exp_ref_sample': '(All samples merged)',
        'per_sample_correction': False,
        'sample_correction_configs': {},
        'show_equation': True,
        'natural_ratio': 1.0,
        'standard_ratio': 1.0,
        'show_natural_line': False,
        'show_standard_line': False,
        'show_mean_line': True,
        'filter_zeros': True,
        'filter_saturated': False,
        'saturation_threshold': 9999999.0,
        'log_x': False,
        'log_y': False,
        'x_max': 99999999.0,
        'show_confidence_intervals': True,
        'marker_size': 8,
        'marker_alpha': 0.7,
        'single_sample_color': '#E74C3C',
        'display_mode': 'Overlaid (Different Colors)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
    }

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Isotopic"
        self.node_type = "isotopic_ratio_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = IsotopicRatioDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        if not self.config.get('element1') or not self.config.get('element2'):
            self._auto_configure_elements()
        self.configuration_changed.emit()

    def _auto_configure_elements(self):
        elems = self._get_elements()
        if len(elems) >= 2:
            self.config['element1'] = elems[0]
            self.config['element2'] = elems[1]
            self.config['x_axis_element'] = elems[1]

    def _get_elements(self) -> list:
        if not self.input_data:
            return []
        sel = self.input_data.get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    def extract_plot_data(self):
        if not self.input_data:
            return None
        dk = DATA_KEY_MAPPING.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data')
            df = build_element_matrix(particles, dk) if particles else None
            if df is not None:
                sources = [p.get('source_sample', '') for p in particles]
                originals = [
                    p.get('original_sample', p.get('source_sample', ''))
                    for p in particles
                ]
                if len(sources) == len(df):
                    df['_source_sample'] = sources
                    df['_original_sample'] = originals
            return {'element_data': df} if df is not None else None

        elif itype == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            if not particles:
                return None
            grouped = {n: [] for n in names}
            for p in particles:
                src = p.get('source_sample')
                if src in grouped:
                    grouped[src].append(p)
            result = {}
            for sn, plist in grouped.items():
                df = build_element_matrix(plist, dk)
                if df is not None:
                    sources = [p.get('source_sample', sn) for p in plist]
                    originals = [
                        p.get('original_sample', p.get('source_sample', sn))
                        for p in plist
                    ]
                    if len(sources) == len(df):
                        df['_source_sample'] = sources
                        df['_original_sample'] = originals
                    result[sn] = {'element_data': df}
            return result or None

        return None