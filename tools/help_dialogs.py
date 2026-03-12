from PySide6.QtWidgets import (
    QApplication, QDialog, QTabWidget, QVBoxLayout, QPushButton,
    QMainWindow, QLabel, QScrollArea, QWidget, QHBoxLayout,
    QSlider, QSpinBox, QComboBox, QGridLayout, QGroupBox,
    QCheckBox, QDoubleSpinBox, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
import sys
import numpy as np
import pyqtgraph as pg
from pathlib import Path
from statistics import NormalDist
from scipy import stats as sp_stats


def get_resource_path(relative_path):
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


# ---------------------------------------------------------------------------
#  Stub – replace with real import in production
# ---------------------------------------------------------------------------
class CompoundPoissonLognormal:
    def get_threshold(self, background, alpha, sigma=0.47):
        z = NormalDist().inv_cdf(1.0 - alpha)
        return background + z * np.sqrt(max(background, 0.5)) * (1 + sigma)


# ---------------------------------------------------------------------------
#  SP-ICP-ToF-MS Signal Generator
# ---------------------------------------------------------------------------
class SPICPToFMSSimulator:
    """
    Physically realistic SP-ICP-ToF-MS signal generator.

    Background
    ----------
    Each dwell-time bin: Poisson(lambda_bg).
    At low lambda (< 3) most bins are zero -- matching real ToF data.

    Particle peak width -- derived automatically from dwell time
    -----------------------------------------------------------
    Ion cloud transit duration ~ 400 us (fixed physical constant).

        peak_bins = max(1, round(400 us / dwell_us))

    At 25 us dwell  -> 16 bins per particle  (multi-point event)
    At 75 us dwell  ->  5 bins per particle
    At 500 us dwell ->  1 bin  per particle  (single-point event)

    Total particle signal is CONSERVED regardless of dwell time.
    """

    ION_CLOUD_US = 400.0

    def generate(
        self,
        acq_time_s=60.0,
        dwell_us=76.71,
        lambda_bg=1.1,
        n_particles=300,
        particle_mean_counts=150.0,
        particle_sigma_log=0.5,
        seed=None,
    ):
        """
        Returns
        -------
        times            : np.ndarray  (seconds)
        signal           : np.ndarray  (counts per dwell)
        particle_centres : np.ndarray  (centre-bin index of each particle)
        peak_width       : int         (bins per particle event)
        particle_totals  : np.ndarray  (total counts per particle, for reference)
        """
        rng = np.random.default_rng(seed)

        dwell_s  = dwell_us * 1e-6
        n_points = max(100, round(acq_time_s / dwell_s))
        times    = np.arange(n_points, dtype=np.float64) * dwell_s

        signal = rng.poisson(lambda_bg, size=n_points).astype(np.float64)

        peak_width = max(1, round(self.ION_CLOUD_US / dwell_us))

        particle_centres = np.array([], dtype=int)
        particle_totals  = np.array([], dtype=float)

        if n_particles > 0 and n_points > 2 * peak_width + 2:
            mu_log  = np.log(particle_mean_counts)
            centres = rng.integers(peak_width, n_points - peak_width, size=n_particles)
            totals  = rng.lognormal(mu_log, particle_sigma_log, size=n_particles)

            if peak_width == 1:
                for c, ts in zip(centres, totals):
                    signal[c] += ts
            else:
                hw    = peak_width // 2
                x     = np.arange(-hw, hw + 1, dtype=float)
                gauss = np.exp(-0.5 * (x / max(1.0, peak_width / 4.0)) ** 2)
                gauss /= gauss.sum()
                for c, ts in zip(centres, totals):
                    lo   = max(0, c - hw)
                    hi   = min(n_points, c + hw + 1)
                    g_lo = lo - (c - hw)
                    g_hi = g_lo + (hi - lo)
                    signal[lo:hi] += ts * gauss[g_lo:g_hi]

            particle_centres = np.asarray(centres, dtype=int)
            particle_totals  = totals

        return times, signal, particle_centres, peak_width, particle_totals


# ---------------------------------------------------------------------------
#  Style helpers
# ---------------------------------------------------------------------------
def _styled_label(html, bg="#f0f4ff", border="#4a90d9"):
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setStyleSheet(
        f"QLabel {{ background:{bg}; border:2px solid {border}; "
        "border-radius:8px; padding:8px 10px; font-size:12px; }}"
    )
    return lbl


def _slider(lo, hi, val):
    sl = QSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(val)
    return sl


# ---------------------------------------------------------------------------
#  Main interactive visualiser
# ---------------------------------------------------------------------------
class InteractiveEquationVisualizer(QWidget):
    METHODS = ["Currie", "Formula_C", "Compound_Poisson", "Manual"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(920)

        self._sim  = SPICPToFMSSimulator()
        self._cpln = CompoundPoissonLognormal()

        # cached results
        self._times           = np.array([])
        self._signal          = np.array([])
        self._particle_idx    = np.array([], dtype=int)
        self._particle_totals = np.array([])
        self._threshold       = 0.0
        self._lod             = 0.0
        self._background      = 0.0
        self._peak_width      = 1

        self._build_ui()

        # Debounce timer: fires _run_simulation after controls settle
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._run_simulation)

        self._run_simulation()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(6)

        # ── Left: scrollable controls ──────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(372)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_w   = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setSpacing(8)
        left_lay.addWidget(self._grp_acquisition())
        left_lay.addWidget(self._grp_background())
        left_lay.addWidget(self._grp_particles())
        left_lay.addWidget(self._grp_detection())
        left_lay.addWidget(self._stats_box())
        left_lay.addStretch()
        left_scroll.setWidget(left_w)
        root.addWidget(left_scroll)

        # ── Right: scrollable plot panel ───────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        right_w   = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setSpacing(8)
        right_lay.setContentsMargins(4, 4, 4, 4)

        # equation strip
        self._eq_label = QLabel()
        self._eq_label.setWordWrap(True)
        self._eq_label.setTextFormat(Qt.RichText)
        self._eq_label.setMinimumHeight(52)
        self._eq_label.setMaximumHeight(72)
        self._eq_label.setStyleSheet(
            "QLabel { background:#f0f4ff; border:2px solid #4a90d9; "
            "border-radius:8px; padding:6px 10px; "
            "font-family:'Courier New',monospace; font-size:11px; }"
        )
        right_lay.addWidget(self._eq_label)

        # --- time trace ---
        trace_lbl = QLabel("<b>Signal trace</b>")
        trace_lbl.setStyleSheet("font-size:12px; padding:2px;")
        right_lay.addWidget(trace_lbl)

        self._trace_plot = pg.PlotWidget()
        self._trace_plot.setBackground("w")
        self._trace_plot.setLabel("left", "Counts per dwell")
        self._trace_plot.setLabel("bottom", "Time (s)")
        self._trace_plot.setMinimumHeight(320)
        right_lay.addWidget(self._trace_plot)

        # --- intensity histogram ---
        hist_lbl = QLabel("<b>Intensity histogram of detected events</b>")
        hist_lbl.setStyleSheet("font-size:12px; padding:2px;")
        right_lay.addWidget(hist_lbl)

        self._hist_plot = pg.PlotWidget()
        self._hist_plot.setBackground("w")
        self._hist_plot.setLabel("bottom", "Intensity (counts per dwell)")
        self._hist_plot.setLabel("left", "Number of detected events")
        self._hist_plot.setMinimumHeight(320)
        right_lay.addWidget(self._hist_plot)

        # bottom padding so scroll always reveals the full histogram
        right_lay.addSpacing(20)

        right_scroll.setWidget(right_w)
        root.addWidget(right_scroll, stretch=1)

    # ── Control groups ─────────────────────────────────────────────────
    def _grp_acquisition(self):
        grp = QGroupBox("Acquisition Parameters")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        lay = QGridLayout(grp)
        lay.setVerticalSpacing(5)

        # acquisition time
        lay.addWidget(QLabel("Acquisition time:"), 0, 0)
        self._acq_spin = QDoubleSpinBox()
        self._acq_spin.setRange(1.0, 180.0)
        self._acq_spin.setDecimals(1)
        self._acq_spin.setSingleStep(10.0)
        self._acq_spin.setValue(60.0)
        self._acq_spin.setSuffix(" s")
        self._acq_spin.setToolTip(
            "Total acquisition time (max 3 min = 180 s).\n"
            "n_points = round(acq_time / dwell_time)."
        )
        self._acq_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._acq_spin, 0, 1)

        self._acq_sl = _slider(10, 1800, 600)
        self._acq_sl.setToolTip("Acquisition time × 10")
        # KEY FIX: slider connects to a helper that BOTH syncs the spinbox AND schedules
        self._acq_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._acq_spin, v / 10.0))
        self._acq_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._acq_sl, int(v * 10)))
        lay.addWidget(self._acq_sl, 1, 0, 1, 2)

        # dwell time
        lay.addWidget(QLabel("Dwell time:"), 2, 0)
        self._dwell_spin = QDoubleSpinBox()
        self._dwell_spin.setRange(1.0, 10000.0)
        self._dwell_spin.setDecimals(2)
        self._dwell_spin.setSingleStep(25.0)
        self._dwell_spin.setValue(76.71)
        self._dwell_spin.setSuffix(" us")
        self._dwell_spin.setToolTip(
            "Dwell time per acquisition bin.\n"
            "E.g. 25 us spectra x 3 accumulations = 75 us.\n\n"
            "Peak width is derived automatically:\n"
            "  peak_bins = max(1, round(400 us / dwell_us))\n"
            "Short dwell -> multi-bin particle events.\n"
            "Long dwell  -> single-bin particle events."
        )
        self._dwell_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._dwell_spin, 2, 1)

        self._dwell_sl = _slider(10, 10000, 767)
        self._dwell_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._dwell_spin, v / 10.0))
        self._dwell_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._dwell_sl, int(v * 10)))
        lay.addWidget(self._dwell_sl, 3, 0, 1, 2)

        # derived info labels
        self._acq_info = QLabel()
        self._acq_info.setStyleSheet("color:#555; font-size:10px;")
        lay.addWidget(self._acq_info, 4, 0, 1, 2)

        self._pw_label = QLabel()
        self._pw_label.setStyleSheet("color:#2060a0; font-size:10px; font-weight:bold;")
        lay.addWidget(self._pw_label, 5, 0, 1, 2)

        # seed
        lay.addWidget(QLabel("Random seed:"), 6, 0)
        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(0, 9999)
        self._seed_spin.setValue(42)
        self._seed_spin.setSpecialValueText("random")
        self._seed_spin.setToolTip("0 = different result each run.")
        self._seed_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._seed_spin, 6, 1)

        return grp

    def _grp_background(self):
        grp = QGroupBox("Background")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        lay = QGridLayout(grp)
        lay.setVerticalSpacing(5)

        lay.addWidget(QLabel("lambda_bg (counts/dwell):"), 0, 0)
        self._bg_spin = QDoubleSpinBox()
        self._bg_spin.setRange(0.01, 50.0)
        self._bg_spin.setDecimals(3)
        self._bg_spin.setSingleStep(0.1)
        self._bg_spin.setValue(1.1)
        self._bg_spin.setToolTip(
            "Poisson mean background per dwell.\n"
            "lambda < 3: sparse signal, many zero bins (typical ToF).\n"
            "lambda > 10: dense dissolved-element background."
        )
        self._bg_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._bg_spin, 0, 1)

        self._bg_sl = _slider(1, 500, 11)
        self._bg_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._bg_spin, v / 10.0))
        self._bg_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._bg_sl, int(v * 10)))
        lay.addWidget(self._bg_sl, 1, 0, 1, 2)

        return grp

    def _grp_particles(self):
        grp = QGroupBox("Particles")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        lay = QGridLayout(grp)
        lay.setVerticalSpacing(5)

        lay.addWidget(QLabel("Number of particles:"), 0, 0)
        self._npart_spin = QSpinBox()
        self._npart_spin.setRange(0, 30000)
        self._npart_spin.setSingleStep(100)
        self._npart_spin.setValue(300)
        self._npart_spin.setToolTip("Up to 30 000 particle events.")
        self._npart_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._npart_spin, 0, 1)

        self._npart_sl = _slider(0, 30000, 300)
        self._npart_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._npart_spin, v))
        self._npart_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._npart_sl, v))
        lay.addWidget(self._npart_sl, 1, 0, 1, 2)

        lay.addWidget(QLabel("Size distribution sigma_log:"), 2, 0)
        self._psig_spin = QDoubleSpinBox()
        self._psig_spin.setRange(0.01, 3.0)
        self._psig_spin.setDecimals(3)
        self._psig_spin.setSingleStep(0.05)
        self._psig_spin.setValue(0.5)
        self._psig_spin.setToolTip(
            "Log-normal sigma of the particle signal distribution.\n"
            "Monodisperse ~ 0.1   Typical ~ 0.4-0.6   Very broad > 0.9"
        )
        self._psig_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._psig_spin, 2, 1)

        self._psig_sl = _slider(1, 300, 50)
        self._psig_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._psig_spin, v / 100.0))
        self._psig_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._psig_sl, int(v * 100)))
        lay.addWidget(self._psig_sl, 3, 0, 1, 2)

        return grp

    def _grp_detection(self):
        grp = QGroupBox("Detection Method")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        lay = QGridLayout(grp)
        lay.setVerticalSpacing(5)

        lay.addWidget(QLabel("Method:"), 0, 0)
        self._method_combo = QComboBox()
        self._method_combo.addItems(self.METHODS)
        self._method_combo.currentTextChanged.connect(self._schedule)
        lay.addWidget(self._method_combo, 0, 1)

        lay.addWidget(QLabel("Alpha:"), 1, 0)
        self._alpha_spin = QDoubleSpinBox()
        self._alpha_spin.setRange(1e-9, 0.5)
        self._alpha_spin.setDecimals(9)
        self._alpha_spin.setValue(1e-6)
        self._alpha_spin.setToolTip(
            "Type-I error rate (false-positive probability).\n"
            "Smaller alpha -> stricter (higher) threshold."
        )
        self._alpha_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._alpha_spin, 1, 1)

        self._alpha_sl = _slider(0, 90, 60)
        self._alpha_sl.setToolTip("Left = smaller alpha (stricter)")
        self._alpha_sl.valueChanged.connect(self._alpha_moved)
        lay.addWidget(self._alpha_sl, 2, 0, 1, 2)

        lay.addWidget(QLabel("CP-LN sigma:"), 3, 0)
        self._cpsig_spin = QDoubleSpinBox()
        self._cpsig_spin.setRange(0.01, 2.0)
        self._cpsig_spin.setDecimals(3)
        self._cpsig_spin.setValue(0.47)
        self._cpsig_spin.setToolTip("Used only by Compound_Poisson method.")
        self._cpsig_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._cpsig_spin, 3, 1)

        lay.addWidget(QLabel("Manual threshold:"), 4, 0)
        self._manual_spin = QDoubleSpinBox()
        self._manual_spin.setRange(0.0, 1e6)
        self._manual_spin.setDecimals(2)
        self._manual_spin.setValue(5.0)
        self._manual_spin.setToolTip("Used only when 'Manual' method is selected.")
        self._manual_spin.valueChanged.connect(self._schedule)
        lay.addWidget(self._manual_spin, 4, 1)

        self._show_part_chk = QCheckBox("Show true particle positions on trace")
        self._show_part_chk.setChecked(True)
        self._show_part_chk.stateChanged.connect(self._update_plots)
        lay.addWidget(self._show_part_chk, 5, 0, 1, 2)

        self._log_chk = QCheckBox("Histogram: log Y-axis")
        self._log_chk.setChecked(False)
        self._log_chk.stateChanged.connect(self._update_plots)
        lay.addWidget(self._log_chk, 6, 0, 1, 2)

        self._show_lognorm_chk = QCheckBox("Show log-normal fit on histogram")
        self._show_lognorm_chk.setChecked(True)
        self._show_lognorm_chk.stateChanged.connect(self._update_plots)
        lay.addWidget(self._show_lognorm_chk, 7, 0, 1, 2)

        return grp

    def _stats_box(self):
        self._stats_label = QLabel("Run simulation to see statistics.")
        self._stats_label.setWordWrap(True)
        self._stats_label.setTextFormat(Qt.RichText)
        self._stats_label.setStyleSheet(
            "QLabel { background:#e8f5e8; border:2px solid #28a745; "
            "border-radius:8px; padding:8px; font-size:11px; }"
        )
        return self._stats_label

    # ------------------------------------------------------------------ #
    # Slider <-> spinbox sync                                              #
    # KEY: _sl_to_spin does NOT call _schedule (avoids double-trigger).   #
    # The slider's lambda is the only caller, so schedule happens once.   #
    # _spin_to_sl is called from spinbox.valueChanged which itself fires  #
    # _schedule via its own connection.                                    #
    # ------------------------------------------------------------------ #
    def _sl_to_spin(self, spin, val):
        """Slider moved -> update spinbox (silently) then schedule update."""
        spin.blockSignals(True)
        spin.setValue(val)
        spin.blockSignals(False)
        self._schedule()          # <-- THIS is what was missing before

    @staticmethod
    def _spin_to_sl(sl, val):
        """Spinbox changed -> update slider (silently). Schedule already fired."""
        sl.blockSignals(True)
        sl.setValue(int(val))
        sl.blockSignals(False)

    def _alpha_moved(self, v):
        alpha = 1.0 if v == 0 else 10 ** (-v / 10.0)
        self._alpha_spin.blockSignals(True)
        self._alpha_spin.setValue(alpha)
        self._alpha_spin.blockSignals(False)
        self._schedule()

    def _schedule(self):
        self._timer.start()

    # ------------------------------------------------------------------ #
    # Simulation                                                           #
    # ------------------------------------------------------------------ #
    def _run_simulation(self):
        seed = self._seed_spin.value() if self._seed_spin.value() > 0 else None

        (self._times, self._signal,
         self._particle_idx, self._peak_width,
         self._particle_totals) = self._sim.generate(
            acq_time_s=self._acq_spin.value(),
            dwell_us=self._dwell_spin.value(),
            lambda_bg=self._bg_spin.value(),
            n_particles=self._npart_spin.value(),
            particle_mean_counts=150.0,
            particle_sigma_log=self._psig_spin.value(),
            seed=seed,
        )

        bg    = self._bg_spin.value()
        self._background = bg
        self._threshold, eq_html, ref_html = self._calc_threshold(
            self._method_combo.currentText(), bg,
            self._alpha_spin.value(),
            self._manual_spin.value(),
            self._cpsig_spin.value())
        self._lod = bg + 3.0 * np.sqrt(max(bg, 0.5))

        self._eq_label.setText(
            f"<b>{self._method_combo.currentText()}:</b> {eq_html}"
            + (f" <span style='color:#666;font-size:10px'>[{ref_html}]</span>"
               if ref_html else "")
        )

        n_pts = len(self._times)
        total = float(self._times[-1]) if n_pts else 0.0
        dw    = self._dwell_spin.value()
        pw    = self._peak_width
        self._acq_info.setText(f"n_points = {n_pts:,}   |   total = {total:.2f} s")
        self._pw_label.setText(
            f"Peak width = {pw} bin(s)  "
            f"[round(400 us / {dw:.1f} us)]"
        )

        self._update_plots()
        self._update_stats()

    # ------------------------------------------------------------------ #
    # Plots                                                                #
    # ------------------------------------------------------------------ #
    def _update_plots(self):
        if self._times.size == 0:
            return
        self._draw_trace()
        self._draw_histogram()

    def _draw_trace(self):
        p = self._trace_plot
        p.clear()
        p.addLegend(offset=(10, 10))

        t   = self._times
        s   = self._signal
        bg  = self._background
        thr = self._threshold
        lod = self._lod

        p.plot(t, s,
               pen=pg.mkPen("#2060c0", width=1), name="Signal")
        p.plot(t, np.full_like(t, bg),
               pen=pg.mkPen("#27ae60", width=1.5, style=Qt.DashLine),
               name=f"Background  (lambda={bg:.2f})")
        p.plot(t, np.full_like(t, lod),
               pen=pg.mkPen("#e67e22", width=1.5, style=Qt.DotLine),
               name=f"LOD = {lod:.2f}")
        p.plot(t, np.full_like(t, thr),
               pen=pg.mkPen("#e74c3c", width=2, style=Qt.DashLine),
               name=f"Threshold = {thr:.2f}")

        # detected events (above threshold)
        det = s > thr
        if np.any(det):
            p.addItem(pg.ScatterPlotItem(
                t[det], s[det],
                symbol="o", size=5,
                pen=pg.mkPen("#c0392b"),
                brush=pg.mkBrush(231, 76, 60, 180),
                name="Detected events",
            ))

        # true particle positions (optional)
        if self._show_part_chk.isChecked() and self._particle_idx.size > 0:
            pi = self._particle_idx
            pi = pi[(pi >= 0) & (pi < len(s))]
            p.addItem(pg.ScatterPlotItem(
                t[pi], s[pi],
                symbol="d", size=9,
                pen=pg.mkPen("#f39c12", width=1),
                brush=pg.mkBrush(243, 156, 18, 100),
                name="True particle positions",
            ))

        p.setTitle(
            f"SP-ICP-ToF-MS Trace  |  dwell={self._dwell_spin.value():.1f} us  |  "
            f"peak width={self._peak_width} bin(s)  |  {len(t):,} points"
        )

    def _draw_histogram(self):
        """
        Histogram of DETECTED events only (signal > threshold).
        X-axis: Intensity (counts per dwell)
        Y-axis: Number of detected events
        Overlaid: fitted log-normal PDF scaled to counts.
        Vertical dashed lines: LOD and Threshold.
        """
        p = self._hist_plot
        p.clear()

        s   = self._signal
        thr = self._threshold
        lod = self._lod

        # ── Only detected events ──────────────────────────────────────
        detected = s[s > thr]
        n_det    = len(detected)

        if n_det < 2:
            p.setTitle("Histogram — no detected events above threshold")
            return

        # ── Histogram bins ────────────────────────────────────────────
        max_val = float(np.percentile(detected, 99.5))
        max_val = max(max_val, thr * 2.0, 10.0)
        n_bins  = min(200, max(30, int(max_val / 2)))

        counts, edges = np.histogram(detected, bins=n_bins, range=(thr, max_val))
        centres = (edges[:-1] + edges[1:]) / 2.0
        width   = edges[1] - edges[0]

        # colour by rough signal magnitude
        # light blue for low end, darker orange for high end
        p.addItem(pg.BarGraphItem(
            x=centres, height=counts,
            width=width,
            brush=pg.mkBrush(70, 130, 200, 180),
            pen=pg.mkPen(None),
        ))

        # ── Log-normal fit ────────────────────────────────────────────
        if self._show_lognorm_chk.isChecked() and n_det >= 5:
            try:
                ln_s, ln_loc, ln_scale = sp_stats.lognorm.fit(
                    detected, floc=0)
                x_fit = np.linspace(thr, max_val, 400)
                pdf   = sp_stats.lognorm.pdf(x_fit, ln_s, ln_loc, ln_scale)
                # scale PDF to match histogram counts
                scale_factor = n_det * width
                y_fit = pdf * scale_factor

                p.plot(x_fit, y_fit,
                       pen=pg.mkPen("#e74c3c", width=2.5),
                       name=f"Log-normal fit  sigma={ln_s:.3f}")

                # annotate fit parameters
                mu_fit = np.log(ln_scale)     # mu in log-space
                median_fit = np.exp(mu_fit)
                p.addItem(pg.TextItem(
                    f"Log-normal fit:\n"
                    f"  median = {median_fit:.1f}\n"
                    f"  sigma  = {ln_s:.3f}",
                    color="#c0392b",
                    anchor=(0, 0),
                ))
                # position the text near the peak of the fit
                peak_x_idx = np.argmax(y_fit)
                p.items[-1].setPos(x_fit[peak_x_idx] * 1.05,
                                   float(np.max(y_fit)) * 0.9)
            except Exception:
                pass

        p.addLegend(offset=(10, 10))

        # ── LOD vertical line ────────────────────────────────────────
        lod_line = pg.InfiniteLine(
            pos=lod, angle=90,
            pen=pg.mkPen("#e67e22", width=2, style=Qt.DashLine),
            label=f"LOD = {lod:.1f}",
            labelOpts={"color": "#e67e22", "position": 0.88,
                       "anchors": [(0, 1), (0, 1)]},
        )
        p.addItem(lod_line)

        # ── Threshold vertical line ──────────────────────────────────
        thr_line = pg.InfiniteLine(
            pos=thr, angle=90,
            pen=pg.mkPen("#8e44ad", width=2, style=Qt.DashDotLine),
            label=f"Threshold = {thr:.1f}",
            labelOpts={"color": "#8e44ad", "position": 0.96,
                       "anchors": [(0, 1), (0, 1)]},
        )
        p.addItem(thr_line)

        p.setLogMode(y=self._log_chk.isChecked())

        method = self._method_combo.currentText()
        p.setTitle(
            f"Intensity histogram of detected events  |  "
            f"{method}  |  n={n_det:,}"
        )
        p.setLabel("bottom", "Intensity (counts per dwell)")
        p.setLabel("left",
                   "Number of detected events" +
                   (" [log]" if self._log_chk.isChecked() else ""))

    # ------------------------------------------------------------------ #
    # Stats panel                                                          #
    # ------------------------------------------------------------------ #
    def _update_stats(self):
        s      = self._signal
        thr    = self._threshold
        n_det  = int(np.sum(s > thr))
        n_true = len(self._particle_idx)
        total  = float(self._times[-1]) if len(self._times) else 0.0

        tp = fn = 0
        if n_true > 0:
            valid = self._particle_idx[
                (self._particle_idx >= 0) & (self._particle_idx < len(s))]
            tp = int(np.sum(s[valid] > thr))
            fn = n_true - tp
        fp = max(0, n_det - tp)
        dr = f"{100*tp/n_true:.1f}%" if n_true > 0 else "N/A"
        er = f"{n_det/total:.1f}/s"  if total  > 0 else "N/A"

        self._stats_label.setText(
            f"<b>Simulation summary</b><br>"
            f"Acq. time: <b>{total:.2f} s</b>  |  "
            f"Points: <b>{len(s):,}</b>  |  "
            f"Dwell: <b>{self._dwell_spin.value():.1f} us</b><br>"
            f"Peak width: <b>{self._peak_width}</b> bin(s)  |  "
            f"Background lambda: <b>{self._background:.3f}</b><br>"
            f"Threshold: <b>{thr:.2f}</b>  |  "
            f"LOD: <b>{self._lod:.2f}</b><br>"
            f"True particles: <b>{n_true}</b>  |  "
            f"Detected: <b>{n_det}</b><br>"
            f"TP <b>{tp}</b>  FP <b>{fp}</b>  FN <b>{fn}</b>  |  "
            f"DR: <b>{dr}</b>  |  Rate: <b>{er}</b>"
        )

    # ------------------------------------------------------------------ #
    # Threshold calculation                                                #
    # ------------------------------------------------------------------ #
    def _calc_threshold(self, method, bg, alpha, manual, sigma):
        if method == "Currie":
            z   = NormalDist().inv_cdf(1.0 - alpha)
            eps = 0.5 if bg < 10 else 0.0
            thr = bg + z * np.sqrt((bg + eps) * 2.0)
            eq  = ("Threshold = lambda + z_alpha * sqrt[(lambda+eps)*2]  "
                   "(eps=continuity correction)")
            ref = "Currie JRNC 276, 285 (2008)"

        elif method == "Formula_C":
            z   = NormalDist().inv_cdf(1.0 - alpha)
            tr  = 1.0
            thr = bg + (z**2 / 2.0 * tr
                        + z * np.sqrt(z**2 / 4.0 * tr**2
                                      + bg * tr * (1.0 + tr)))
            eq  = "Threshold = lambda + z^2/2*tr + z*sqrt[z^2/4*tr^2 + lambda*tr*(1+tr)]"
            ref = "MARLAP Vol III §20 Formula C"

        elif method == "Compound_Poisson":
            thr = self._cpln.get_threshold(bg, alpha, sigma=sigma)
            eq  = f"Compound Poisson-LogNormal (Fenton-Wilkinson)  sigma={sigma:.3f}"
            ref = "Lockwood et al. JAAS 2025"

        elif method == "Manual":
            thr = manual
            eq  = "Threshold = User-defined value"
            ref = ""
        else:
            thr = bg * 3
            eq  = ref = ""

        return float(thr), eq, ref


# ---------------------------------------------------------------------------
#  Peak integration visualiser
# ---------------------------------------------------------------------------
class PeakIntegrationVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(420)
        layout = QVBoxLayout(self)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        layout.addWidget(self.plot)

        controls = QHBoxLayout()
        bg_grp  = QGroupBox("Background level")
        bg_lay  = QVBoxLayout(bg_grp)
        self.bg_sl = _slider(5, 30, 10)
        self.bg_sl.valueChanged.connect(self.update_visualization)
        bg_lay.addWidget(self.bg_sl)
        controls.addWidget(bg_grp)

        thr_grp = QGroupBox("Threshold level")
        thr_lay = QVBoxLayout(thr_grp)
        self.thr_sl = _slider(20, 70, 40)
        self.thr_sl.valueChanged.connect(self.update_visualization)
        thr_lay.addWidget(self.thr_sl)
        controls.addWidget(thr_grp)
        layout.addLayout(controls)

        self._gen_data()
        self.update_visualization()

    def _gen_data(self):
        self.x   = np.linspace(0, 10, 500)
        self.raw = 100 * np.exp(-(self.x - 5)**2 / 0.5) + 10
        np.random.seed(42)
        self.raw += np.random.normal(0, 2, len(self.x))

    def update_visualization(self):
        self.plot.clear()
        bg  = self.bg_sl.value()
        thr = self.thr_sl.value()
        sig = self.raw - 10 + bg

        self.plot.plot(self.x, sig, pen="b", name="Signal")
        self.plot.plot(self.x, [bg]*len(self.x),
                       pen=pg.mkPen("g", style=Qt.DashLine, width=2),
                       name="Background")
        self.plot.plot(self.x, [thr]*len(self.x),
                       pen=pg.mkPen("r", style=Qt.DashLine, width=2),
                       name="Threshold")

        half = len(sig) // 2
        li = ri = half
        for i in range(half, 0, -1):
            if sig[i] <= bg:
                li = i
                break
        for i in range(half, len(sig)):
            if sig[i] <= bg:
                ri = i
                break

        self.plot.addItem(pg.FillBetweenItem(
            pg.PlotDataItem(self.x[li:ri+1], sig[li:ri+1]),
            pg.PlotDataItem(self.x[li:ri+1], [bg]*(ri-li+1)),
            brush=pg.mkBrush(100, 100, 255, 100),
        ))
        area = np.sum(sig[li:ri+1] - bg)
        ti   = pg.TextItem(
            f"Integrated area: {area:.1f} counts\n"
            f"Bounds: [{self.x[li]:.2f}, {self.x[ri]:.2f}] s",
            color="k", anchor=(0, 0))
        ti.setPos(self.x[li], sig[li] + 5)
        self.plot.addItem(ti)
        self.plot.setLabel("left", "Signal")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setTitle("Background Integration Method (IsotopeTrack)")
        self.plot.addLegend()


# ---------------------------------------------------------------------------
#  Help manager
# ---------------------------------------------------------------------------
class HelpManager:
    def __init__(self, parent=None):
        self.parent             = parent
        self.user_guide_dialog  = None
        self.detection_dialog   = None
        self.calibration_dialog = None

    def show_user_guide(self):
        """Show the user guide dialog."""
        try:
            from tools.tutorial import UserGuideDialog
        except ImportError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.parent, "User Guide",
                "User guide module is not available in this context.")
            return
        if not self.user_guide_dialog:
            self.user_guide_dialog = UserGuideDialog(self.parent)
        self.user_guide_dialog.show()
        self.user_guide_dialog.raise_()

    def show_detection_methods(self):
        if not self.detection_dialog:
            self.detection_dialog = DetectionMethodsDialog(self.parent)
        self.detection_dialog.show()
        self.detection_dialog.raise_()

    def show_calibration_methods(self):
        if not self.calibration_dialog:
            self.calibration_dialog = CalibrationMethodsDialog(self.parent)
        self.calibration_dialog.show()
        self.calibration_dialog.raise_()


# ---------------------------------------------------------------------------
#  Detection Methods Dialog
# ---------------------------------------------------------------------------
class DetectionMethodsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detection Methods - IsotopeTrack")
        self.resize(1600, 1000)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        layout.addWidget(_styled_label(
            "<h2 style='margin:0'>SP-ICP-ToF-MS Signal Simulator &amp; Detection Explorer</h2>"
            "<p style='margin:4px 0 0 0'>"
            "Physically realistic background (compound Poisson) and particle signals "
            "(log-normal distribution, multi-bin at short dwell times). "
            "Peak width is derived automatically from dwell time. "
            "Scroll the right panel to see the full intensity histogram.</p>",
            bg="#eef4ff", border="#4a90d9",
        ))

        tabs = QTabWidget()
        tabs.addTab(self._tab_simulator(), "Signal Simulator")
        tabs.addTab(self._tab_integration(), "Peak Integration")
        layout.addWidget(tabs)

        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

    def _tab_simulator(self):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.addWidget(InteractiveEquationVisualizer())
        return w

    def _tab_integration(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        cw = QWidget()
        cl = QVBoxLayout(cw)
        cl.addWidget(_styled_label(
            "<h3 style='margin-top:0'>Peak Integration - Background Method</h3>"
            "<p>IsotopeTrack integrates from where signal returns to background level on "
            "each side of the peak, capturing the full ion cloud.</p>"
            "<p><b>Formula:</b> Total counts = sum(Signal[i] - Background) "
            "for i in [left_bound, right_bound]</p>",
            bg="#fff8e1", border="#f39c12",
        ))
        cl.addWidget(PeakIntegrationVisualizer())
        scroll.setWidget(cw)
        return scroll


# ---------------------------------------------------------------------------
#  Calibration Methods Dialog
# ---------------------------------------------------------------------------
class CalibrationMethodsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Methods - IsotopeTrack")
        self.resize(900, 700)
        layout = QVBoxLayout(self)
        tabs   = QTabWidget()
        tabs.addTab(self._tab_overview(), "Overview")
        tabs.addTab(self._tab_ionic(), "Ionic Calibration")
        tabs.addTab(self._tab_transport(), "Transport Rate")
        layout.addWidget(tabs)
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

    def _img(self, path, w=600, h=400):
        try:
            pm = QPixmap(str(get_resource_path(path)))
            if not pm.isNull():
                lbl = QLabel()
                lbl.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                lbl.setAlignment(Qt.AlignCenter)
                return lbl
        except Exception:
            pass
        return QLabel(f"<i style='color:red'>Image not found: {path}</i>")

    def _scroll(self, *widgets):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        cw = QWidget()
        cl = QVBoxLayout(cw)
        for w in widgets:
            cl.addWidget(w)
        cl.addStretch()
        sc.setWidget(cw)
        return sc

    def _tab_overview(self):
        return self._scroll(_styled_label(
            "<h2>Calibration Overview</h2>"
            "<p>Two calibrations convert raw counts to physical quantities:</p>"
            "<ol><li><b>Ionic Calibration</b> - concentration to counts/s</li>"
            "<li><b>Transport Rate</b> - sample volume entering plasma per second (uL/s)</li></ol>"
            "<p>Outputs: particle mass (fg), diameter (nm), number concentration (particles/mL), LOD, LOQ.</p>",
            bg="#eef4ff", border="#4a90d9"),
            self._img("images/calibration_overview.png"))

    def _tab_ionic(self):
        return self._scroll(_styled_label(
            "<h2>Ionic Calibration</h2>"
            "<p>Three methods tested automatically; best R^2 selected:</p>"
            "<ul><li><b>Simple Linear</b> - through origin</li>"
            "<li><b>Linear</b> - with intercept</li>"
            "<li><b>Weighted</b> - improved accuracy at low concentrations</li></ul>"
            "<p>Key outputs: sensitivity (counts/ppb), R^2, BEC, LOD, LOQ.</p>",
            bg="#eef4ff", border="#4a90d9"),
            self._img("images/ionic_calibration.png"))

    def _tab_transport(self):
        return self._scroll(_styled_label(
            "<h2>Transport Rate Calibration</h2>"
            "<p>Errors in transport efficiency propagate directly into size and concentration errors.</p>"
            "<p><i>Pace et al. Anal. Chem. 83, 9361 (2011).</i></p>\n Laurie et al. Anal. Chem. 91, 20, 13275-13284 (2019).",
            bg="#eef4ff", border="#4a90d9"),
            self._img("images/methods.png"),
            self._img("images/transport_effect.png"))


# ---------------------------------------------------------------------------
#  About dialog
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About IsotopeTrack")
        self.setFixedSize(500, 380)
        lay = QVBoxLayout(self)

        title = QLabel("<h1>IsotopeTrack</h1>")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size:52px")
        logo.setText("🔬")
        try:
            pm = QPixmap(str(get_resource_path("images/isotrack_icon.png")))
            if not pm.isNull():
                logo.setPixmap(pm.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                logo.setText("")
        except Exception:
            pass
        lay.addWidget(logo)

        lay.addWidget(QLabel(
            "<h3 align='center'>Version 1.0.1</h3>"
            "<p align='center'>Advanced SP-ICP-ToF-MS data analysis.<br>"
            "Peak detection - Calibration - Nanoparticle quantification.</p>"
        ))
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignCenter)


# ---------------------------------------------------------------------------
#  Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dlg = DetectionMethodsDialog()
    dlg.showMaximized()
    sys.exit(app.exec())