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
from scipy import stats as sp_stats
from widget.custom_plot_widget import EnhancedPlotWidget

from theme import theme



def get_resource_path(relative_path):
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


# ---------------------------------------------------------------------------
#  Real CompoundPoissonLognormal — imported from peak_detection
# ---------------------------------------------------------------------------
try:
    from processing.peak_detection import CompoundPoissonLognormal
except ImportError:
    # Fallback: accurate approximation matching the detection code
    from scipy.stats import poisson as _sp_poisson, lognorm as _sp_lognorm

    def _zero_trunc_q(lam, y):
        k0 = np.exp(-lam)
        return max((y - k0) / (1.0 - k0), 0.0)

    def _sum_iid_ln(n, mu, sigma):
        sig2x = np.log((np.exp(sigma ** 2) - 1.0) / n + 1.0)
        mux = np.log(n) + mu + 0.5 * (sigma ** 2 - sig2x)
        return mux, np.sqrt(sig2x)

    class CompoundPoissonLognormal:
        def get_threshold(self, lambda_bkgd, alpha, sigma=0.47):
            if lambda_bkgd <= 0:
                return 0.0
            try:
                q = 1.0 - alpha
                mu = np.log(1.0) - 0.5 * sigma ** 2
                uk = int(_sp_poisson.ppf(1.0 - 1e-12, lambda_bkgd))
                k = np.arange(0, uk + 1, dtype=int)
                pdf = _sp_poisson.pmf(k, lambda_bkgd)
                valid = np.isfinite(pdf) & (pdf > 0)
                k, pdf = k[valid], pdf[valid]
                q0 = _zero_trunc_q(lambda_bkgd, q)
                if q0 <= 0.0:
                    return 0.0
                weights = pdf[1:] / pdf[1:].sum()
                k = k[1:]
                mus_arr = np.array([_sum_iid_ln(ki, mu, sigma)[0] for ki in k])
                sigs_arr = np.array([_sum_iid_ln(ki, mu, sigma)[1] for ki in k])
                upper_q = _sp_lognorm.ppf(q0, s=sigs_arr[-1], scale=np.exp(mus_arr[-1]))
                xs = np.linspace(lambda_bkgd, upper_q, 2000)
                cdf_matrix = np.column_stack([
                    _sp_lognorm.cdf(xs, s=s, scale=np.exp(m))
                    for m, s in zip(mus_arr, sigs_arr)
                ])
                cdf = cdf_matrix @ weights
                return float(xs[np.argmax(cdf > q0)])
            except Exception:
                return lambda_bkgd + 3.0 * np.sqrt(max(lambda_bkgd, 1))


# ---------------------------------------------------------------------------
#  SP-ICP-ToF-MS Signal Generator  (compound Poisson multinomial model)
# ---------------------------------------------------------------------------
class SPICPToFMSSimulator:
    """
    Background — compound Poisson-lognormal per bin
    ------------------------------------------------
    Each dwell bin receives N ~ Poisson(lambda_bg) ions, where each
    ion contributes X_i ~ Lognormal(mu_sir, sigma_sir) with E[X_i]=1.
    Bin signal = sum(X_i).  When N=0 the bin reads exactly zero,
    producing the characteristic sparse, continuous-valued background
    seen in real ToF data.

    Particle peak width — derived automatically from dwell time
    -----------------------------------------------------------
    Ion cloud transit duration ~ 400 µs (fixed physical constant).

        peak_bins = max(1, round(400 µs / dwell_µs))

    Particle signal model (compound Poisson + lognormal temporal profile)
    ---------------------------------------------------------------------
    For each nanoparticle:
      1. Expected ion yield drawn from Lognormal(µ_size, sigma_size)
         to represent polydisperse particle size distribution.
      2. Actual detected ions  N ~ Poisson(expected_yield).
      3. Each ion contributes  X_i ~ Lognormal(µ_sir, sigma_sir)
         with E[X_i] = 1  (single-ion response distribution).
      4. Ions are distributed across peak_bins via Multinomial(N, probs)
         where probs follow a lognormal temporal envelope:
           probs[k] ∝ LN_PDF(k + 0.5 | µ_temporal, σ_temporal)
         This produces the asymmetric peak shape observed in real data:
         sharp rise as the ion cloud enters the plasma, followed by a
         longer lognormal tail.
      5. Per-bin signal = sum of lognormal responses for ions in that bin.

    The temporal profile parameters (σ_temporal=0.64, scale=3.08) were
    fitted from real spICP-ToF-MS particle events measured at 204 µs
    dwell time and are scaled proportionally for other dwell times.

    Both background and particle signals share the same SIR distribution,
    producing continuous-valued output identical in character to real
    spICP-ToF-MS data.
    """

    ION_CLOUD_US = 400.0
    _TEMPORAL_SIGMA = 0.85
    _TEMPORAL_SCALE_US = 3.8 * 204.4    # ≈ 777 µs in physical time

    def _temporal_profile(self, dwell_us):
        """
        Compute the lognormal temporal probability vector for distributing
        ions across dwell-time bins.  The profile is defined in physical
        time (µs) and sampled at the given dwell resolution.

        The ion cloud temporal envelope is:
            p(t) ∝ LN_PDF(t | σ=0.64, scale≈630 µs)
        producing the asymmetric shape observed in real data: fast rise
        to a peak at ~2 bins (at 204 µs dwell), then a lognormal tail.

        Args:
            dwell_us: Dwell time per bin in microseconds.

        Returns:
            probs: ndarray, lognormal temporal probabilities (sums to 1).
                   Length = number of significant bins for one event.
        """
        # Window: 5× the nominal cloud duration to capture the full tail
        total_us = 5.0 * self.ION_CLOUD_US
        n_bins = max(2, round(total_us / dwell_us))

        # Evaluate lognormal PDF at bin centres (in physical time)
        t_centers = (np.arange(n_bins, dtype=np.float64) + 0.5) * dwell_us
        log_t = np.log(t_centers / self._TEMPORAL_SCALE_US)
        probs = np.exp(-0.5 * (log_t / self._TEMPORAL_SIGMA) ** 2) / t_centers

        # Trim trailing bins below 0.3% of peak
        peak_val = np.max(probs)
        significant = probs > peak_val * 0.003
        if np.any(significant):
            last_sig = np.where(significant)[0][-1]
            probs = probs[:last_sig + 1]

        probs = np.maximum(probs, 1e-15)
        probs /= probs.sum()
        return probs

    def generate(
        self,
        acq_time_s=60.0,
        dwell_us=76.71,
        lambda_bg=1.1,
        n_particles=300,
        particle_mean_counts=150.0,
        particle_sigma_log=0.5,
        sigma_sir=0.47,
        seed=None,
    ):
        """
        Args:
            acq_time_s: Total acquisition time in seconds.
            dwell_us: Dwell time per bin in microseconds.
            lambda_bg: Poisson mean background per dwell bin.
            n_particles: Number of nanoparticle events.
            particle_mean_counts: Mean expected ion yield per particle.
            particle_sigma_log: Log-sigma of the particle size distribution.
            sigma_sir: Log-sigma of the single-ion response distribution.
            seed: Random seed (None = non-reproducible).

        Returns:
            times: ndarray, time axis in seconds.
            signal: ndarray, counts per dwell bin.
            particle_centres: ndarray, centre-bin index of each particle.
            peak_width: int, bins per particle event.
            particle_totals: ndarray, total integrated counts per particle.
        """
        rng = np.random.default_rng(seed)

        dwell_s = dwell_us * 1e-6
        n_points = max(100, round(acq_time_s / dwell_s))
        times = np.arange(n_points, dtype=np.float64) * dwell_s

        # ── Single-ion response parameters (shared by background + particles) ──
        mu_sir = -0.5 * sigma_sir ** 2  # ensures E[X_i] = 1

        # ── Background: compound Poisson-lognormal per bin ──
        # N_bg ~ Poisson(lambda_bg), S = sum_{i=1}^{N} X_i, X_i ~ LN(mu_sir, sigma_sir)
        bg_ion_counts = rng.poisson(lambda_bg, size=n_points)
        total_bg_ions = int(np.sum(bg_ion_counts))
        signal = np.zeros(n_points, dtype=np.float64)
        if total_bg_ions > 0:
            all_bg_responses = rng.lognormal(mu_sir, sigma_sir, size=total_bg_ions)
            bg_cumsum = np.cumsum(bg_ion_counts)
            bg_starts = np.zeros(n_points, dtype=int)
            bg_starts[1:] = bg_cumsum[:-1]
            for i in np.where(bg_ion_counts > 0)[0]:
                signal[i] = np.sum(all_bg_responses[bg_starts[i]:bg_cumsum[i]])

        peak_width = max(1, round(self.ION_CLOUD_US / dwell_us))

        particle_centres = np.array([], dtype=int)
        particle_totals = np.array([], dtype=float)

        if n_particles > 0 and n_points > 2 * peak_width + 2:
            # Particle size distribution (expected ion yields)
            mu_size = np.log(particle_mean_counts)
            expected_yields = rng.lognormal(mu_size, particle_sigma_log, size=n_particles)

            # Poisson sampling of actual ion counts
            actual_ions = rng.poisson(np.maximum(expected_yields, 0).astype(np.float64))

            totals = np.zeros(n_particles, dtype=np.float64)

            # Precompute the lognormal temporal profile for this dwell time
            temporal_probs = self._temporal_profile(dwell_us)
            event_bins = len(temporal_probs)

            # Place particle onsets with enough room for the full event
            centres = rng.integers(0, n_points - event_bins, size=n_particles)

            for p_idx in range(n_particles):
                onset = centres[p_idx]
                n_ions = actual_ions[p_idx]
                if n_ions <= 0:
                    continue

                # Draw single-ion responses
                ion_signals = rng.lognormal(mu_sir, sigma_sir, size=int(n_ions))
                particle_total = np.sum(ion_signals)
                totals[p_idx] = particle_total

                if event_bins == 1:
                    signal[onset] += particle_total
                else:
                    hi = min(n_points, onset + event_bins)
                    n_bins = hi - onset
                    if n_bins <= 0:
                        continue

                    probs = temporal_probs[:n_bins].copy()
                    probs /= probs.sum()

                    bin_ion_counts = rng.multinomial(int(n_ions), probs)

                    ion_idx = 0
                    for b in range(n_bins):
                        bc = bin_ion_counts[b]
                        if bc > 0:
                            signal[onset + b] += np.sum(ion_signals[ion_idx:ion_idx + bc])
                            ion_idx += bc

            # Report centre as the onset + peak of temporal profile
            peak_offset = int(np.argmax(temporal_probs))
            particle_centres = np.minimum(
                np.asarray(centres, dtype=int) + peak_offset,
                n_points - 1
            )
            particle_totals = totals

        return times, signal, particle_centres, peak_width, particle_totals


# ---------------------------------------------------------------------------
#  Style helpers
# ---------------------------------------------------------------------------
# NOTE: The real _styled_label implementation is defined lower in the file
# (after the visualizer classes, alongside _equation_label). It is the clean
# prose-style variant matching the User Guide. The earlier duplicate that
# lived here has been removed to avoid confusion — Python was already using
# the lower definition since it's defined last, but keeping both around made
# editing error-prone.


def _slider(lo, hi, val):
    sl = QSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(val)
    return sl


# ---------------------------------------------------------------------------
#  Main interactive visualiser
# ---------------------------------------------------------------------------
class InteractiveEquationVisualizer(QWidget):
    METHODS = ["Compound_Poisson", "Manual"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(750)

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
        left_scroll.setFixedWidth(350)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_w   = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setSpacing(8)
        left_lay.addWidget(self._grp_acquisition())
        left_lay.addWidget(self._grp_background())
        left_lay.addWidget(self._grp_particles())
        left_lay.addWidget(self._grp_detection())
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

        self._trace_plot = EnhancedPlotWidget()
        self._trace_plot.setLabel("left", "Counts per dwell")
        self._trace_plot.setLabel("bottom", "Time (s)")
        self._trace_plot.setMinimumHeight(260)
        right_lay.addWidget(self._trace_plot)

        # --- intensity histogram ---
        hist_lbl = QLabel("<b>Intensity histogram of detected events</b>")
        hist_lbl.setStyleSheet("font-size:12px; padding:2px;")
        right_lay.addWidget(hist_lbl)

        self._hist_plot = EnhancedPlotWidget()

        self._hist_plot.setLabel("bottom", "Intensity (counts per dwell)")
        self._hist_plot.setLabel("left", "Number of detected events")
        self._hist_plot.setMinimumHeight(260)
        right_lay.addWidget(self._hist_plot)

        # bottom padding so scroll always reveals the full histogram
        right_lay.addSpacing(20)

        right_scroll.setWidget(right_w)
        root.addWidget(right_scroll, stretch=1)

    # ── Control groups ─────────────────────────────────────────────────
    def _grp_acquisition(self):
        grp = QGroupBox("Acquisition Parameters")
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
        self._acq_sl.valueChanged.connect(
            lambda v: self._sl_to_spin(self._acq_spin, v / 10.0))
        self._acq_spin.valueChanged.connect(
            lambda v: self._spin_to_sl(self._acq_sl, int(v * 10)))
        lay.addWidget(self._acq_sl, 1, 0, 1, 2)

        # dwell time
        lay.addWidget(QLabel("Dwell time:"), 2, 0)
        self._dwell_spin = QDoubleSpinBox()
        self._dwell_spin.setRange(25.0, 10000.0)
        self._dwell_spin.setDecimals(2)
        self._dwell_spin.setSingleStep(25.0)
        self._dwell_spin.setValue(200.0)
        self._dwell_spin.setSuffix(" us")
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
            "Log-normal sigma of the particle size distribution.\n"
            "Controls the spread of expected ion yields across particles.\n"
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

        lay.addWidget(QLabel("CP-LN sigma (σ_SIR):"), 3, 0)
        self._cpsig_spin = QDoubleSpinBox()
        self._cpsig_spin.setRange(0.01, 2.0)
        self._cpsig_spin.setDecimals(3)
        self._cpsig_spin.setValue(0.47)
        self._cpsig_spin.setToolTip(
            "Single-ion response log-sigma.\n"
            "Used by the Compound_Poisson method "
            "and also to shape the per-ion responses in the simulated signal."
        )
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

        self._log_chk = QCheckBox("Histogram: log Y-axis")
        self._log_chk.setChecked(False)
        self._log_chk.stateChanged.connect(self._update_plots)
        lay.addWidget(self._log_chk, 5, 0, 1, 2)

        self._show_lognorm_chk = QCheckBox("Show log-normal fit on histogram")
        self._show_lognorm_chk.setChecked(True)
        self._show_lognorm_chk.stateChanged.connect(self._update_plots)
        lay.addWidget(self._show_lognorm_chk, 6, 0, 1, 2)

        return grp


    def _sl_to_spin(self, spin, val):
        """Slider moved -> update spinbox (silently) then schedule update."""
        spin.blockSignals(True)
        spin.setValue(val)
        spin.blockSignals(False)
        self._schedule()

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
            sigma_sir=self._cpsig_spin.value(),
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

        p.addItem(pg.BarGraphItem(
            x=centres, height=counts,
            width=width,
            brush=pg.mkBrush(70, 130, 200, 180),
            pen=pg.mkPen(None),
        ))

        if self._show_lognorm_chk.isChecked() and n_det >= 5:
            try:
                ln_s, ln_loc, ln_scale = sp_stats.lognorm.fit(
                    detected, floc=0)
                x_fit = np.linspace(thr, max_val, 400)
                pdf   = sp_stats.lognorm.pdf(x_fit, ln_s, ln_loc, ln_scale)
                scale_factor = n_det * width
                y_fit = pdf * scale_factor

                p.plot(x_fit, y_fit,
                       pen=pg.mkPen("#e74c3c", width=2.5),
                       name=f"Log-normal fit  sigma={ln_s:.3f}")

                mu_fit = np.log(ln_scale)
                median_fit = np.exp(mu_fit)
                fit_text = pg.TextItem(
                    f"Log-normal fit:\n"
                    f"  median = {median_fit:.1f}\n"
                    f"  sigma  = {ln_s:.3f}",
                    color="#c0392b",
                    anchor=(0, 0),
                )
                peak_x_idx = np.argmax(y_fit)
                fit_text.setPos(x_fit[peak_x_idx] * 1.05,
                                float(np.max(y_fit)) * 0.9)
                p.addItem(fit_text)
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


    def _calc_threshold(self, method, bg, alpha, manual, sigma):
        if method == "Compound_Poisson":
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
#  Peak integration visualiser  (three methods)
# ---------------------------------------------------------------------------
class PeakIntegrationVisualizer(QWidget):
    """
    Interactive visualizer showing three peak integration methods:
      - Background: integrate from where signal crosses background level.
      - Threshold: integrate only the region above the detection threshold.
      - Midpoint: integrate from where signal crosses (background + threshold) / 2.
    """

    METHODS = ["Background", "Threshold", "Midpoint"]
    METHOD_COLORS = {
        "Background": (100, 100, 255, 100),
        "Threshold": (255, 100, 100, 100),
        "Midpoint": (100, 200, 100, 100),
    }
    METHOD_FORMULAS = {
        "Background": (
            "<b>Background Integration</b><br>"
            "Bounds: signal crosses background level on each side of the peak.<br>"
            "<code>Total = Σ (Signal[i] − Background)  for i ∈ [left, right]</code><br>"
            "Captures the full ion cloud. Used in IsotopeTrack by default."
        ),
        "Threshold": (
            "<b>Threshold Integration</b><br>"
            "Bounds: only bins where signal exceeds the detection threshold.<br>"
            "<code>Total = Σ (Signal[i] − Background)  for i where Signal[i] > Threshold</code><br>"
            "More conservative; may undercount signal in the tails."
        ),
        "Midpoint": (
            "<b>Midpoint Integration</b><br>"
            "Bounds: signal crosses the midpoint = (Background + Threshold) / 2.<br>"
            "<code>Total = Σ (Signal[i] − Background)  for i ∈ [left_mid, right_mid]</code><br>"
            "Compromise between full-cloud and threshold-only approaches."
        ),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(500)
        layout = QVBoxLayout(self)

        # Formula label (updates with method)
        self._formula_label = _styled_label("", bg="#fff8e1", border="#f39c12")
        self._formula_label.setMinimumHeight(70)
        layout.addWidget(self._formula_label)

        self.plot = EnhancedPlotWidget()

        layout.addWidget(self.plot)

        controls = QHBoxLayout()

        # Method selector
        method_grp = QGroupBox("Integration method")
        method_lay = QVBoxLayout(method_grp)
        self._method_combo = QComboBox()
        self._method_combo.addItems(self.METHODS)
        self._method_combo.currentTextChanged.connect(self.update_visualization)
        method_lay.addWidget(self._method_combo)
        controls.addWidget(method_grp)

        bg_grp = QGroupBox("Background level")
        bg_lay = QVBoxLayout(bg_grp)
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
        self.x = np.linspace(0, 10, 500)
        self.raw = 100 * np.exp(-(self.x - 5) ** 2 / 0.5) + 10
        np.random.seed(42)
        self.raw += np.random.normal(0, 2, len(self.x))

    def update_visualization(self):
        self.plot.clear()
        bg = self.bg_sl.value()
        thr = self.thr_sl.value()
        method = self._method_combo.currentText()
        sig = self.raw - 10 + bg
        midpoint = (bg + thr) / 2.0

        # Update formula
        self._formula_label.setText(self.METHOD_FORMULAS.get(method, ""))

        # Plot signal and reference lines
        self.plot.plot(self.x, sig, pen="b", name="Signal")
        self.plot.plot(self.x, [bg] * len(self.x),
                       pen=pg.mkPen("g", style=Qt.DashLine, width=2),
                       name=f"Background = {bg}")
        self.plot.plot(self.x, [thr] * len(self.x),
                       pen=pg.mkPen("r", style=Qt.DashLine, width=2),
                       name=f"Threshold = {thr}")

        if method == "Midpoint":
            self.plot.plot(self.x, [midpoint] * len(self.x),
                           pen=pg.mkPen("#8e44ad", style=Qt.DotLine, width=2),
                           name=f"Midpoint = {midpoint:.1f}")

        # Determine integration bounds
        half = len(sig) // 2

        if method == "Background":
            li = ri = half
            for i in range(half, 0, -1):
                if sig[i] <= bg:
                    li = i
                    break
            for i in range(half, len(sig)):
                if sig[i] <= bg:
                    ri = i
                    break
            shade_x = self.x[li:ri + 1]
            shade_sig = sig[li:ri + 1]
            shade_base = np.full_like(shade_sig, bg)
            area = float(np.sum(shade_sig - bg))

        elif method == "Threshold":
            above = sig > thr
            # Find the contiguous region around the peak
            li = ri = half
            for i in range(half, 0, -1):
                if not above[i]:
                    li = i + 1
                    break
            for i in range(half, len(sig)):
                if not above[i]:
                    ri = i - 1
                    break
            li = max(li, 0)
            ri = min(ri, len(sig) - 1)
            shade_x = self.x[li:ri + 1]
            shade_sig = sig[li:ri + 1]
            shade_base = np.full_like(shade_sig, bg)
            area = float(np.sum(shade_sig - bg))

        else:  # Midpoint
            li = ri = half
            for i in range(half, 0, -1):
                if sig[i] <= midpoint:
                    li = i
                    break
            for i in range(half, len(sig)):
                if sig[i] <= midpoint:
                    ri = i
                    break
            shade_x = self.x[li:ri + 1]
            shade_sig = sig[li:ri + 1]
            shade_base = np.full_like(shade_sig, bg)
            area = float(np.sum(shade_sig - bg))

        # Draw shaded region
        fill_color = self.METHOD_COLORS[method]
        self.plot.addItem(pg.FillBetweenItem(
            pg.PlotDataItem(shade_x, shade_sig),
            pg.PlotDataItem(shade_x, shade_base),
            brush=pg.mkBrush(*fill_color),
        ))

        ti = pg.TextItem(
            f"{method} integration\n"
            f"Integrated area: {area:.1f} counts\n"
            f"Bounds: [{self.x[li]:.2f}, {self.x[ri]:.2f}] s",
            color="k", anchor=(0, 0))
        ti.setPos(self.x[li], float(np.max(sig)) * 0.85)
        self.plot.addItem(ti)

        self.plot.setLabel("left", "Signal (counts)")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setTitle(f"{method} Integration Method")
        self.plot.addLegend()


# ---------------------------------------------------------------------------
#  Iterative Threshold Visualizer
# ---------------------------------------------------------------------------
class IterativeThresholdVisualizer(QWidget):
    """
    Interactive visualizer explaining the iterative background refinement
    with Aitken delta-squared acceleration used in IsotopeTrack.

    The algorithm is a fixed-point iteration:
        T_{n+1} = f(mean(signal[signal < T_n]))

    Aitken acceleration uses three consecutive iterates to extrapolate
    directly to the fixed point:
        T_accel = T0 - (T1 - T0)^2 / (T2 - 2*T1 + T0)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(700)

        self._sim = SPICPToFMSSimulator()
        self._cpln = CompoundPoissonLognormal()

        root = QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(6)

        # ── Left: controls ─────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(340)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setSpacing(6)

        left_lay.addWidget(_styled_label(
            "<h3 style='margin:0'>Iterative Threshold Refinement</h3>"
            "<p style='margin:4px 0 0 0'>"
            "The threshold depends on the background λ, which in turn "
            "depends on which points are <i>below</i> the threshold. "
            "This circular dependency is resolved by iterating:</p>"
            "<ol style='margin:2px 0'>"
            "<li>Estimate λ = mean(signal)</li>"
            "<li>Compute threshold T = f(λ, α, σ)</li>"
            "<li>Re-estimate λ = mean(signal[signal &lt; T])</li>"
            "<li>Repeat until T converges</li>"
            "</ol>"
            "<p><b>Aitken Δ² acceleration</b> extrapolates from three iterates "
            "(T₀, T₁, T₂) to the fixed point, typically reaching iteration-6 "
            "accuracy after only 3 CPLN evaluations.</p>"
            "<p style='color:#666; font-size:10px'>"
            "Aitken, A.C. Proc. Roy. Soc. Edinburgh 46, 289–305 (1926).</p>",
            bg="#eef4ff", border="#4a90d9",
        ))

        # Controls
        params_grp = QGroupBox("Simulation Parameters")
        params_lay = QGridLayout(params_grp)

        params_lay.addWidget(QLabel("λ_bg:"), 0, 0)
        self._bg_spin = QDoubleSpinBox()
        self._bg_spin.setRange(0.1, 20.0)
        self._bg_spin.setDecimals(2)
        self._bg_spin.setValue(1.5)
        self._bg_spin.valueChanged.connect(self._regenerate)
        params_lay.addWidget(self._bg_spin, 0, 1)

        params_lay.addWidget(QLabel("Particles:"), 1, 0)
        self._npart_spin = QSpinBox()
        self._npart_spin.setRange(10, 2000)
        self._npart_spin.setValue(200)
        self._npart_spin.valueChanged.connect(self._regenerate)
        params_lay.addWidget(self._npart_spin, 1, 1)

        params_lay.addWidget(QLabel("Alpha:"), 2, 0)
        self._alpha_spin = QDoubleSpinBox()
        self._alpha_spin.setRange(1e-9, 0.1)
        self._alpha_spin.setDecimals(9)
        self._alpha_spin.setValue(1e-6)
        self._alpha_spin.valueChanged.connect(self._run_iteration)
        params_lay.addWidget(self._alpha_spin, 2, 1)

        params_lay.addWidget(QLabel("σ_SIR:"), 3, 0)
        self._sigma_spin = QDoubleSpinBox()
        self._sigma_spin.setRange(0.1, 2.0)
        self._sigma_spin.setDecimals(3)
        self._sigma_spin.setValue(0.47)
        self._sigma_spin.valueChanged.connect(self._run_iteration)
        params_lay.addWidget(self._sigma_spin, 3, 1)

        params_lay.addWidget(QLabel("Max iterations:"), 4, 0)
        self._maxiter_spin = QSpinBox()
        self._maxiter_spin.setRange(1, 20)
        self._maxiter_spin.setValue(8)
        self._maxiter_spin.valueChanged.connect(self._run_iteration)
        params_lay.addWidget(self._maxiter_spin, 4, 1)

        left_lay.addWidget(params_grp)

        left_lay.addStretch()
        left_scroll.setWidget(left_w)
        root.addWidget(left_scroll)

        # ── Right: plots ───────────────────────────────────────────────
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setSpacing(6)

        self._trace_plot = EnhancedPlotWidget()
        self._trace_plot.setLabel("left", "Counts")
        self._trace_plot.setLabel("bottom", "Time (s)")
        self._trace_plot.setMinimumHeight(280)
        right_lay.addWidget(self._trace_plot)
        
        self._conv_plot = EnhancedPlotWidget()

        self._conv_plot.setLabel("left", "Threshold value")
        self._conv_plot.setLabel("bottom", "Iteration")
        self._conv_plot.setMinimumHeight(280)
        right_lay.addWidget(self._conv_plot)

        root.addWidget(right_w, stretch=1)

        self._signal = np.array([])
        self._times = np.array([])

        self._regenerate()

    def _regenerate(self):
        """Generate new signal data and re-run iteration."""
        _, self._signal, _, _, _ = self._sim.generate(
            acq_time_s=30.0,
            dwell_us=76.71,
            lambda_bg=self._bg_spin.value(),
            n_particles=self._npart_spin.value(),
            particle_mean_counts=100.0,
            particle_sigma_log=0.5,
            sigma_sir=self._sigma_spin.value(),
            seed=42,
        )
        dwell_s = 76.71e-6
        self._times = np.arange(len(self._signal)) * dwell_s
        self._run_iteration()

    def _run_iteration(self):
        """Run the iterative threshold with and without Aitken, then plot."""
        signal = self._signal
        if signal.size == 0:
            return

        alpha = self._alpha_spin.value()
        sigma = self._sigma_spin.value()
        max_iters = self._maxiter_spin.value()
        bg_init = float(np.mean(signal))

        # ── Standard iteration (no Aitken) ─────────────────────────────
        std_thresholds = []
        std_backgrounds = []
        lam = bg_init
        for it in range(max_iters):
            thr = self._cpln.get_threshold(lam, alpha, sigma=sigma)
            std_thresholds.append(float(thr))
            std_backgrounds.append(float(lam))
            below = signal[signal < thr]
            lam_new = float(np.mean(below)) if len(below) > 0 else lam
            if abs(lam_new - lam) < 1e-4 and it > 0:
                lam = lam_new
                break
            lam = lam_new

        # ── With Aitken acceleration ───────────────────────────────────
        aitken_thresholds = []
        aitken_applied_at = None
        lam = bg_init
        for it in range(max_iters):
            thr = self._cpln.get_threshold(lam, alpha, sigma=sigma)
            aitken_thresholds.append(float(thr))

            # Aitken after 3 iterates
            if len(aitken_thresholds) == 3 and aitken_applied_at is None:
                t0, t1, t2 = aitken_thresholds[-3], aitken_thresholds[-2], aitken_thresholds[-1]
                denom = t2 - 2.0 * t1 + t0
                if abs(denom) > 1e-15:
                    t_accel = t0 - (t1 - t0) ** 2 / denom
                    t_min = min(t0, t1, t2)
                    t_max = max(t0, t1, t2)
                    if t_accel > 0 and t_min * 0.8 <= t_accel <= t_max * 1.2:
                        aitken_thresholds.append(float(t_accel))
                        aitken_applied_at = len(aitken_thresholds) - 1
                        break

            below = signal[signal < thr]
            lam_new = float(np.mean(below)) if len(below) > 0 else lam
            if abs(lam_new - lam) < 1e-4 and it > 0:
                lam = lam_new
                break
            lam = lam_new

        # ── Plot trace with final thresholds ───────────────────────────
        p = self._trace_plot
        p.clear()
        p.addLegend(offset=(10, 10))
        p.plot(self._times, signal, pen=pg.mkPen("#2060c0", width=1), name="Signal")

        colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db",
                  "#9b59b6", "#1abc9c", "#e91e63"]

        for i, thr_val in enumerate(std_thresholds):
            col = colors[i % len(colors)]
            p.plot(self._times, np.full_like(self._times, thr_val),
                   pen=pg.mkPen(col, width=1.5, style=Qt.DashLine),
                   name=f"Iter {i}: T={thr_val:.3f}")

        p.setTitle("Signal with iterative threshold convergence")

        # ── Convergence plot ───────────────────────────────────────────
        p2 = self._conv_plot
        p2.clear()
        p2.addLegend(offset=(10, 10))

        iters_std = np.arange(len(std_thresholds))
        p2.plot(iters_std, std_thresholds,
                pen=pg.mkPen("#2060c0", width=2),
                symbol="o", symbolSize=8,
                symbolBrush=pg.mkBrush("#2060c0"),
                name=f"Standard ({len(std_thresholds)} iters)")

        iters_aitken = np.arange(len(aitken_thresholds))
        p2.plot(iters_aitken, aitken_thresholds,
                pen=pg.mkPen("#e74c3c", width=2),
                symbol="s", symbolSize=8,
                symbolBrush=pg.mkBrush("#e74c3c"),
                name=f"Aitken Δ² ({len(aitken_thresholds)} iters)")

        if aitken_applied_at is not None:
            p2.addItem(pg.ScatterPlotItem(
                [aitken_applied_at], [aitken_thresholds[aitken_applied_at]],
                symbol="star", size=18,
                pen=pg.mkPen("#27ae60", width=2),
                brush=pg.mkBrush(39, 174, 96, 180),
            ))
            aitken_label = pg.TextItem(
                "Aitken\nextrapolation",
                color="#27ae60", anchor=(0, 1))
            aitken_label.setPos(aitken_applied_at + 0.1,
                                aitken_thresholds[aitken_applied_at])
            p2.addItem(aitken_label)

        p2.setTitle("Threshold convergence: standard vs Aitken Δ²")

        # ── Result summary ─────────────────────────────────────────────
        final_std = std_thresholds[-1] if std_thresholds else 0
        final_aitken = aitken_thresholds[-1] if aitken_thresholds else 0


# ---------------------------------------------------------------------------
#  Watershed Splitting Visualizer
# ---------------------------------------------------------------------------
class WatershedSplittingVisualizer(QWidget):
    """
    Interactive visualizer for the 1D watershed peak splitting algorithm.

    The algorithm detects merged (overlapping) particle events and splits them:
      1. Find local maxima above the threshold in a contiguous region.
      2. For each pair of adjacent maxima, find the valley minimum.
      3. Check two criteria:
           a) Valley depth ratio:  valley / min(peak_left, peak_right)  < valley_ratio
           b) Prominence: both sub-peaks have prominence > threshold × min_prominence_factor
      4. If both criteria are met, split at the valley minimum.

    References
    ----------
    Beucher, S. & Lantuéjoul, C. "Use of Watersheds in Contour Detection."
        Int. Workshop on Image Processing, CCETT/IRISA, Rennes (1979).
    Adapted to 1D peak splitting for spICP-ToF-MS by IsotopeTrack.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(650)
        self._cpln = CompoundPoissonLognormal()

        root = QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(6)

        # ── Left: controls and explanation ─────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(360)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setSpacing(6)

        left_lay.addWidget(_styled_label(
            "<h3 style='margin:0'>1D Watershed Peak Splitting</h3>"
            "<p style='margin:4px 0 0 0'>"
            "When two nanoparticles arrive within the same ion cloud transit "
            "time (~400 µs), their signals overlap and appear as a single "
            "merged peak. The 1D watershed algorithm detects and separates "
            "these merged events.</p>"
            "<p><b>Algorithm:</b></p>"
            "<ol style='margin:2px 0'>"
            "<li>Find local maxima above threshold in the region</li>"
            "<li>For each pair of adjacent maxima, locate the valley minimum</li>"
            "<li>Check splitting criteria:<br>"
            "   &nbsp;a) Valley ratio &lt; threshold<br>"
            "   &nbsp;b) Both sub-peaks have sufficient prominence</li>"
            "<li>Split at the valley minimum (sharp boundary)</li>"
            "</ol>"
            "<p style='color:#666; font-size:10px'>"
            "Adapted from: Beucher, S. & Lantuéjoul, C. "
            "\"Use of Watersheds in Contour Detection.\" "
            "Int. Workshop on Image Processing, CCETT/IRISA, Rennes (1979).<br>"
            "1D adaptation for spICP-ToF-MS: IsotopeTrack.</p>",
            bg="#fff0f0", border="#e74c3c",
        ))

        params_grp = QGroupBox("Peak Parameters")
        params_lay = QGridLayout(params_grp)

        params_lay.addWidget(QLabel("Peak separation:"), 0, 0)
        self._sep_spin = QDoubleSpinBox()
        self._sep_spin.setRange(0.5, 5.0)
        self._sep_spin.setDecimals(2)
        self._sep_spin.setSingleStep(0.1)
        self._sep_spin.setValue(2.0)
        self._sep_spin.setToolTip("Distance between the two peak centres (a.u.)")
        self._sep_spin.valueChanged.connect(self._update)
        params_lay.addWidget(self._sep_spin, 0, 1)

        params_lay.addWidget(QLabel("Peak 1 height:"), 1, 0)
        self._h1_spin = QDoubleSpinBox()
        self._h1_spin.setRange(20, 500)
        self._h1_spin.setValue(100)
        self._h1_spin.valueChanged.connect(self._update)
        params_lay.addWidget(self._h1_spin, 1, 1)

        params_lay.addWidget(QLabel("Peak 2 height:"), 2, 0)
        self._h2_spin = QDoubleSpinBox()
        self._h2_spin.setRange(20, 500)
        self._h2_spin.setValue(70)
        self._h2_spin.valueChanged.connect(self._update)
        params_lay.addWidget(self._h2_spin, 2, 1)

        params_lay.addWidget(QLabel("Background:"), 3, 0)
        self._bg_spin = QDoubleSpinBox()
        self._bg_spin.setRange(1, 30)
        self._bg_spin.setValue(5)
        self._bg_spin.valueChanged.connect(self._update)
        params_lay.addWidget(self._bg_spin, 3, 1)

        left_lay.addWidget(params_grp)

        split_grp = QGroupBox("Splitting Criteria")
        split_lay = QGridLayout(split_grp)

        split_lay.addWidget(QLabel("Valley ratio:"), 0, 0)
        self._valley_spin = QDoubleSpinBox()
        self._valley_spin.setRange(0.1, 1.0)
        self._valley_spin.setDecimals(2)
        self._valley_spin.setSingleStep(0.05)
        self._valley_spin.setValue(0.5)
        self._valley_spin.setToolTip(
            "Maximum valley/peak ratio to allow splitting.\n"
            "Lower value = more conservative (requires deeper valley)."
        )
        self._valley_spin.valueChanged.connect(self._update)
        split_lay.addWidget(self._valley_spin, 0, 1)

        split_lay.addWidget(QLabel("Min prominence factor:"), 1, 0)
        self._prom_spin = QDoubleSpinBox()
        self._prom_spin.setRange(0.1, 5.0)
        self._prom_spin.setDecimals(2)
        self._prom_spin.setSingleStep(0.1)
        self._prom_spin.setValue(1.0)
        self._prom_spin.setToolTip(
            "Minimum prominence as fraction of threshold.\n"
            "Both sub-peaks must exceed: threshold × factor."
        )
        self._prom_spin.valueChanged.connect(self._update)
        split_lay.addWidget(self._prom_spin, 1, 1)

        left_lay.addWidget(split_grp)

        left_lay.addStretch()
        left_scroll.setWidget(left_w)
        root.addWidget(left_scroll)

        # ── Right: plots ───────────────────────────────────────────────
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)

        self._merged_plot = EnhancedPlotWidget()

        self._merged_plot.setLabel("left", "Signal (counts)")
        self._merged_plot.setLabel("bottom", "Bin index")
        self._merged_plot.setMinimumHeight(280)
        right_lay.addWidget(self._merged_plot)

        self._split_plot = EnhancedPlotWidget()

        self._split_plot.setLabel("left", "Signal (counts)")
        self._split_plot.setLabel("bottom", "Bin index")
        self._split_plot.setMinimumHeight(280)
        right_lay.addWidget(self._split_plot)

        root.addWidget(right_w, stretch=1)

        self._update()

    def _update(self):
        sep = self._sep_spin.value()
        h1 = self._h1_spin.value()
        h2 = self._h2_spin.value()
        bg = self._bg_spin.value()
        valley_ratio = self._valley_spin.value()
        prom_factor = self._prom_spin.value()

        # ── Generate two overlapping lognormal-shaped particle events ──
        # Each event has the asymmetric shape: sharp rise → peak → lognormal tail
        n_pts = 300
        x = np.linspace(0, 10, n_pts)
        dx = x[1] - x[0]

        # Lognormal temporal profile for each particle event
        sigma_t = 0.85
        scale_t = 1.2  # in x-axis units

        def lognormal_peak(x_arr, onset, height, scale=scale_t, sigma=sigma_t):
            """Generate a single lognormal-shaped particle event."""
            t = x_arr - onset
            result = np.zeros_like(x_arr)
            pos = t > 0
            if not np.any(pos):
                return result
            log_t = np.log(t[pos] / scale)
            result[pos] = np.exp(-0.5 * (log_t / sigma) ** 2) / t[pos]
            mx = np.max(result)
            if mx > 0:
                result = result / mx * height
            return result

        # Two particles arriving close together — their signals overlap
        onset1 = 5.0 - sep / 2 - 0.5  # onset of particle 1
        onset2 = 5.0 + sep / 2 - 0.5  # onset of particle 2

        peak1 = lognormal_peak(x, onset1, h1)
        peak2 = lognormal_peak(x, onset2, h2)

        sig = peak1 + peak2 + bg
        np.random.seed(42)
        sig += np.random.normal(0, 0.3, len(x))
        sig = np.maximum(sig, 0)

        threshold = self._cpln.get_threshold(bg, alpha=1e-6, sigma=0.47)

        # ── Find the two main peaks using prominence-based detection ───
        from scipy.signal import find_peaks as _find_peaks
        above_thresh = sig > threshold
        peak_region = np.where(above_thresh)[0]
        if len(peak_region) < 3:
            self._merged_plot.clear()
            self._split_plot.clear()
            return

        start_idx = peak_region[0]
        end_idx = peak_region[-1]
        region = sig[start_idx:end_idx + 1]

        # Require each peak to have prominence >= 20% of the tallest point
        # in the region — this filters out noise bumps in the long tail
        min_prom = max(region) * 0.20
        raw_peaks, props = _find_peaks(region, prominence=min_prom)

        if len(raw_peaks) < 2:
            # Fall back to the two highest points if fewer than 2 found
            raw_peaks = np.argsort(region)[::-1][:2]
            raw_peaks = np.sort(raw_peaks)

        # Keep only the two most prominent peaks
        if len(raw_peaks) > 2:
            prominences = props.get("prominences", region[raw_peaks])
            top2 = np.argsort(prominences)[::-1][:2]
            raw_peaks = np.sort(raw_peaks[top2])

        maxima = list(raw_peaks)

        # ── Plot merged signal (top) ───────────────────────────────────
        p1 = self._merged_plot
        p1.clear()
        p1.addLegend(offset=(10, 10))

        # Show individual particle contributions (dashed)
        p1.plot(x, peak1 + bg, pen=pg.mkPen("#3498db", width=1.5, style=Qt.DotLine),
                name="Particle 1 (individual)")
        p1.plot(x, peak2 + bg, pen=pg.mkPen("#e67e22", width=1.5, style=Qt.DotLine),
                name="Particle 2 (individual)")

        # Show merged signal (solid)
        p1.plot(x, sig, pen=pg.mkPen("#2060c0", width=2), name="Merged signal")
        p1.plot(x, np.full_like(x, bg),
                pen=pg.mkPen("#27ae60", width=1.5, style=Qt.DashLine),
                name=f"Background = {bg:.1f}")
        p1.plot(x, np.full_like(x, threshold),
                pen=pg.mkPen("#e74c3c", width=1.5, style=Qt.DashLine),
                name=f"Threshold = {threshold:.1f}")

        # ── Check splitting ────────────────────────────────────────────
        split_performed = False
        valley_info = ""
        split_point_global = None

        if len(maxima) >= 2:
            left_idx = maxima[0]
            right_idx = maxima[1]
            valley_seg = region[left_idx:right_idx + 1]
            valley_local = np.argmin(valley_seg)
            valley_idx = left_idx + valley_local
            valley_val = region[valley_idx]
            valley_global = start_idx + valley_idx

            left_peak = region[left_idx]
            right_peak = region[right_idx]
            min_peak = min(left_peak, right_peak)

            ratio = valley_val / min_peak if min_peak > 0 else 0.0
            left_prom = left_peak - valley_val
            right_prom = right_peak - valley_val
            min_prom_required = threshold * prom_factor

            # ── Apply splitting criteria ───────────────────────────────
            if (ratio < valley_ratio and
                    left_prom >= min_prom_required and
                    right_prom >= min_prom_required):
                split_performed = True
                split_point_global = valley_global

            # Mark valley with down-triangle
            p1.addItem(pg.ScatterPlotItem(
                [x[valley_global]], [sig[valley_global]],
                symbol="t3", size=14,
                pen=pg.mkPen("#9b59b6", width=2),
                brush=pg.mkBrush(155, 89, 182, 200),
            ))

            # Vertical line at valley (split boundary)
            p1.addItem(pg.InfiniteLine(
                pos=x[valley_global], angle=90,
                pen=pg.mkPen("#9b59b6", width=2, style=Qt.DashDotLine),
            ))

            # Valley annotation
            valley_text = pg.TextItem(
                f"Valley ratio = {ratio:.3f}\n"
                f"Left prom = {left_prom:.1f}\n"
                f"Right prom = {right_prom:.1f}",
                color="#9b59b6", anchor=(0.5, 1))
            valley_text.setPos(x[valley_global], valley_val - 3)
            p1.addItem(valley_text)


        p1.setTitle(
            f"Merged peak analysis  |  {len(maxima)} maxima detected"
        )

        # ── Plot split result ──────────────────────────────────────────
        p2 = self._split_plot
        p2.clear()
        p2.addLegend(offset=(10, 10))

        if split_performed and split_point_global is not None:
            # Left sub-peak
            left_mask = np.zeros_like(x, dtype=bool)
            left_mask[start_idx:split_point_global + 1] = True

            right_mask = np.zeros_like(x, dtype=bool)
            right_mask[split_point_global + 1:end_idx + 1] = True

            p2.plot(x, sig, pen=pg.mkPen("#cccccc", width=1), name="Original")

            if np.any(left_mask):
                p2.addItem(pg.FillBetweenItem(
                    pg.PlotDataItem(x[left_mask], sig[left_mask]),
                    pg.PlotDataItem(x[left_mask], np.full(np.sum(left_mask), bg)),
                    brush=pg.mkBrush(52, 152, 219, 120),
                ))
                area_left = float(np.sum(sig[left_mask] - bg))
                p2.plot(x[left_mask], sig[left_mask],
                        pen=pg.mkPen("#3498db", width=2), name=f"Peak 1 ({area_left:.0f} cts)")

            if np.any(right_mask):
                p2.addItem(pg.FillBetweenItem(
                    pg.PlotDataItem(x[right_mask], sig[right_mask]),
                    pg.PlotDataItem(x[right_mask], np.full(np.sum(right_mask), bg)),
                    brush=pg.mkBrush(231, 76, 60, 120),
                ))
                area_right = float(np.sum(sig[right_mask] - bg))
                p2.plot(x[right_mask], sig[right_mask],
                        pen=pg.mkPen("#e74c3c", width=2), name=f"Peak 2 ({area_right:.0f} cts)")

            # Split boundary
            p2.addItem(pg.InfiniteLine(
                pos=x[split_point_global], angle=90,
                pen=pg.mkPen("#9b59b6", width=2, style=Qt.DashDotLine),
                label="Split point",
                labelOpts={"color": "#9b59b6", "position": 0.9},
            ))

            p2.setTitle("After watershed splitting — two separate particle events")
        else:
            p2.plot(x, sig, pen=pg.mkPen("#2060c0", width=1.5), name="Signal (no split)")
            p2.addItem(pg.FillBetweenItem(
                pg.PlotDataItem(x[start_idx:end_idx + 1], sig[start_idx:end_idx + 1]),
                pg.PlotDataItem(x[start_idx:end_idx + 1],
                                np.full(end_idx - start_idx + 1, bg)),
                brush=pg.mkBrush(52, 152, 219, 80),
            ))
            p2.setTitle("No split — single particle event retained")

        p2.plot(x, np.full_like(x, bg),
                pen=pg.mkPen("#27ae60", width=1, style=Qt.DashLine))
        p2.plot(x, np.full_like(x, threshold),
                pen=pg.mkPen("#e74c3c", width=1, style=Qt.DashLine))


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
def _help_dialog_qss() -> str:
    """Shared QSS for help/info dialogs — palette-aware."""
    p = theme.palette
    return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QTabWidget::pane {{
            border: 1px solid {p.border};
            background-color: {p.bg_secondary};
            border-radius: 6px;
        }}
        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            border: 1px solid {p.border};
            padding: 8px 14px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}
        QTabBar::tab:selected {{
            background-color: {p.bg_secondary};
            color: {p.accent};
            font-weight: 600;
            border-bottom: 1px solid {p.bg_secondary};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
        }}
        QScrollArea {{
            border: none;
            background-color: {p.bg_secondary};
        }}
        /* Inner content widget of each scrollable tab — without this the
           widget stays white on macOS even with the dialog-level bg set. */
        QWidget#helpContent {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
        }}
        /* Scroll area viewport cascade — catches the widget between the
           scroll area and the content that otherwise paints white. */
        QScrollArea > QWidget > QWidget {{
            background-color: {p.bg_secondary};
        }}
        QScrollBar:vertical {{
            background: {p.bg_secondary};
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
        QPushButton {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: none;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: 600;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QGroupBox {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 6px;
            color: {p.text_primary};
        }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 3px 6px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QCheckBox {{
            color: {p.text_primary};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 1px solid {p.border};
            background-color: {p.bg_tertiary};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {p.accent};
            background-color: {p.accent};
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {p.border};
            height: 4px;
            background: {p.bg_tertiary};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {p.accent};
            border: 1px solid {p.accent};
            width: 14px;
            margin: -6px 0;
            border-radius: 7px;
        }}
    """


class DetectionMethodsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detection Methods - IsotopeTrack")

        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(1500, int(avail.width() * 0.85))
            h = min(950, int(avail.height() * 0.85))
        else:
            w, h = 1200, 800
        self.resize(w, h)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addWidget(_styled_label(
            "<h2 style='margin:0'>SP-ICP-ToF-MS Signal Simulator &amp; Detection Explorer</h2>"
            "<p style='margin:4px 0 0 0'>"
            "Physically realistic background (compound Poisson) and particle signals "
            "(compound Poisson-lognormal model with multinomial bin distribution). "
            "Peak width is derived automatically from dwell time.<br>"
            "<b>Methods:</b> Compound Poisson-Lognormal (analytical, "
            "Lockwood et al. <i>JAAS</i> 2025), "
            "Manual.</p>",
        ))

        tabs = QTabWidget()
        tabs.addTab(self._tab_simulator(), "Signal Simulator")
        tabs.addTab(self._tab_integration(), "Peak Integration")
        tabs.addTab(self._tab_iterative(), "Iterative Threshold")
        tabs.addTab(self._tab_watershed(), "Watershed Splitting")
        layout.addWidget(tabs)

        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(_help_dialog_qss())

    def showEvent(self, event):
        # Re-apply theme every time the dialog is shown — covers the
        # case where mainwindow caches the dialog instance and the user
        # toggles the theme while the dialog is hidden, then reopens it.
        self.apply_theme()
        super().showEvent(event)

    def _tab_simulator(self):
        w   = QWidget()
        w.setObjectName("helpContent")
        w.setAutoFillBackground(True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.addWidget(InteractiveEquationVisualizer())
        return w

    def _tab_integration(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        cw = QWidget()
        cw.setObjectName("helpContent")
        cw.setAutoFillBackground(True)
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(20, 16, 20, 24)
        cl.setSpacing(10)
        cl.addWidget(_styled_label(
            "<h3 style='margin-top:0'>Peak Integration Methods</h3>"
            "<p>IsotopeTrack supports three integration approaches for quantifying "
            "the total signal of a detected nanoparticle event. "
            "Use the selector below to compare how each method defines the "
            "integration bounds and the resulting area.</p>"
            "<p><b>Background:</b> integrates from where the signal returns to the "
            "background level — captures the full ion cloud (default).<br>"
            "<b>Threshold:</b> integrates only bins exceeding the detection threshold "
            "— more conservative, avoids noise tails.<br>"
            "<b>Midpoint:</b> integrates from (background + threshold) / 2 — "
            "a compromise between the two.</p>",
        ))
        cl.addWidget(PeakIntegrationVisualizer())
        scroll.setWidget(cw)
        return scroll

    def _tab_iterative(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        cw = QWidget()
        cw.setObjectName("helpContent")
        cw.setAutoFillBackground(True)
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(0, 4, 0, 0)
        cl.addWidget(IterativeThresholdVisualizer())
        scroll.setWidget(cw)
        return scroll

    def _tab_watershed(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        cw = QWidget()
        cw.setObjectName("helpContent")
        cw.setAutoFillBackground(True)
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(0, 4, 0, 0)
        cl.addWidget(WatershedSplittingVisualizer())
        scroll.setWidget(cw)
        return scroll


def _styled_label(html, bg=None, border=None):
    """
    Rich-text section label — clean prose, no decorative box.

    The old version wrapped each call in a colored, bordered panel. That
    look was heavy and inconsistent (especially in dark mode). This
    version ignores bg/border (kept for API compatibility with existing
    callers) and returns a plain prose section that matches the User
    Guide dialog.

    Args:
        html (str): HTML content for the label.
        bg: Ignored (kept for backwards compatibility).
        border: Ignored (kept for backwards compatibility).

    Returns:
        QLabel: Rich-text label with no box.
    """
    p = theme.palette
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    lbl.setStyleSheet(
        f"font-size:13px; line-height:1.5; padding: 4px 2px; "
        f"color:{p.text_primary}; background:transparent; border:none;"
    )
    return lbl


def _equation_label(html):
    """
    Equation block — subtle left accent bar, no full box.

    Reads as an indented quote, matching the User Guide's clean prose
    style instead of the old bordered cream panel.

    Args:
        html (str): HTML content containing the equation(s).

    Returns:
        QLabel: Equation-styled label.
    """
    p = theme.palette
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setStyleSheet(
        f"font-size:13px; padding:6px 14px; margin:2px 0 2px 8px; "
        f"border-left: 3px solid {p.accent}; "
        f"color:{p.text_primary}; background:transparent;"
    )
    lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return lbl


class CalibrationMethodsDialog(QDialog):
    """Dialog displaying calibration method descriptions and equations."""

    def __init__(self, parent=None):
        """
        Initialise the calibration methods dialog.

        Args:
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration Methods – IsotopeTrack")
        self.resize(960, 760)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_overview(), "Overview")
        tabs.addTab(self._tab_ionic(), "Ionic Calibration")
        tabs.addTab(self._tab_transport(), "Transport Rate")
        layout.addWidget(tabs)

        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(_help_dialog_qss())

    def showEvent(self, event):
        # Re-apply theme every time the dialog is shown — covers the
        # case where mainwindow caches the dialog instance and the user
        # toggles the theme while the dialog is hidden, then reopens it.
        self.apply_theme()
        super().showEvent(event)

    def _img(self, path, w=600, h=400):
        """
        Load and scale an image resource into a QLabel.

        Args:
            path (str): Relative path under the resource directory.
            w (int): Maximum display width.
            h (int): Maximum display height.

        Returns:
            QLabel: Label containing the scaled pixmap, or an error message.
        """
        try:
            pm = QPixmap(str(get_resource_path(path)))
            if not pm.isNull():
                lbl = QLabel()
                lbl.setPixmap(
                    pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                lbl.setAlignment(Qt.AlignCenter)
                return lbl
        except Exception:
            pass
        return QLabel(f"<i style='color:red'>Image not found: {path}</i>")

    def _scroll(self, *widgets):
        """
        Wrap an arbitrary number of widgets inside a scrollable area.

        Uses the same auto-fill-background trick as the User Guide dialog
        so the content widget actually paints the theme background on
        macOS instead of falling back to white.

        Args:
            *widgets: Widgets to add vertically inside the scroll area.

        Returns:
            QScrollArea: Scrollable container widget.
        """
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.NoFrame)
        sc.viewport().setAutoFillBackground(False)

        cw = QWidget()
        cw.setObjectName("helpContent")
        cw.setAutoFillBackground(True)
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(20, 16, 20, 24)
        cl.setSpacing(10)
        for w in widgets:
            cl.addWidget(w)
        cl.addStretch()
        sc.setWidget(cw)
        return sc

    # ── Tab: Overview ────────────────────────────────────────────────────

    def _tab_overview(self):
        """
        Build the Overview tab content.

        Returns:
            QScrollArea: Tab widget with overview description and image.
        """
        return self._scroll(
            _styled_label(
                "<h2>Calibration Overview</h2>"
                "<p>Two independent calibrations convert raw ICP-ToF-MS counts "
                "into physical quantities:</p>"
                "<ol>"
                "<li><b>Ionic Calibration</b> – relates dissolved concentration "
                "to instrument response (counts·s⁻¹).</li>"
                "<li><b>Transport Rate Calibration</b> – determines the sample "
                "volume entering the plasma per second (µL·s⁻¹).</li>"
                "</ol>"
                "<p><b>Outputs:</b> particle mass (fg), diameter (nm), "
                "number concentration (particles·mL⁻¹), LOD, LOQ.</p>",
                bg="#eef4ff", border="#4a90d9",
            ),
            self._img("images/calibration_overview.png"),
        )

    # ── Tab: Ionic Calibration ───────────────────────────────────────────

    def _tab_ionic(self):
        """
        Build the Ionic Calibration tab with regression methods and FOM equations.

        Returns:
            QScrollArea: Tab widget with descriptions, equations, and image.
        """
        return self._scroll(
            # --- Introduction ---
            _styled_label(
                "<h2>Ionic Calibration</h2>"
                "<p>Standard solutions of known concentration are measured "
                "and a regression of signal (counts·s⁻¹) vs. concentration "
                "is performed. IsotopeTrack fits three models automatically "
                "and selects the one with the highest R².</p>",
                bg="#eef4ff", border="#4a90d9",
            ),

            # --- Method 1: Force through zero ---
            _styled_label(
                "<h3>1. Force Through Zero</h3>"
                "<p>Linear regression forced through the origin (intercept = 0). "
                "Appropriate when the blank signal is negligible.</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Model:</b>&nbsp;&nbsp; y = m · x"
                "<br><br>"
                "<b>Slope:</b>&nbsp;&nbsp; m = Σ(xᵢ · yᵢ) / Σ(xᵢ²)"
                "<br><br>"
                "<b>R²:</b>&nbsp;&nbsp; R² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(yᵢ²)"
                "<br>"
                "<span style='color:#666; font-size:11px;'>"
                "Note: denominator is Σ(yᵢ²), not Σ(yᵢ − ȳ)², because the "
                "model passes through the origin.</span>"
            ),

            # --- Method 2: Simple Linear ---
            _styled_label(
                "<h3>2. Simple Linear (OLS)</h3>"
                "<p>Ordinary least-squares regression with a free intercept. "
                "The standard approach for most calibration curves.</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Model:</b>&nbsp;&nbsp; y = m · x + b"
                "<br><br>"
                "<b>Solution:</b>&nbsp;&nbsp; [m, b] = (X<sup>T</sup>X)⁻¹ · X<sup>T</sup>y"
                "<br>"
                "<span style='color:#666; font-size:11px;'>"
                "where X is the design matrix [x, 1].</span>"
                "<br><br>"
                "<b>R²:</b>&nbsp;&nbsp; R² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(yᵢ − ȳ)²"
            ),

            # --- Method 3: Weighted ---
            _styled_label(
                "<h3>3. Weighted Linear (WLS)</h3>"
                "<p>Weighted least-squares regression where each point is "
                "weighted by the inverse variance of its signal. Gives more "
                "influence to precise measurements — useful when variance "
                "increases with concentration (heteroscedastic data).</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Weights:</b>&nbsp;&nbsp; wᵢ = 1 / σᵢ²"
                "<br><br>"
                "<b>Slope:</b>&nbsp;&nbsp; m = (Σw · Σwxy − Σwx · Σwy) / "
                "(Σw · Σwx² − (Σwx)²)"
                "<br><br>"
                "<b>Intercept:</b>&nbsp;&nbsp; b = (Σwx² · Σwy − Σwx · Σwxy) / "
                "(Σw · Σwx² − (Σwx)²)"
                "<br><br>"
                "<b>R²<sub>w</sub>:</b>&nbsp;&nbsp; R²<sub>w</sub> = "
                "1 − Σwᵢ(yᵢ − ŷᵢ)² / Σwᵢ(yᵢ − ȳ)²"
            ),

            # --- Figures of Merit ---
            _styled_label(
                "<h3>Figures of Merit (IUPAC convention)</h3>"
                "<p>Computed for each regression method using the standard "
                "deviation of the lowest-concentration standard (σ<sub>blank</sub>) "
                "as a proxy for blank noise.</p>",
                bg="#fff3e0", border="#ffb74d",
            ),
            _equation_label(
                "<b>LOD</b> (Limit of Detection):"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "LOD = 3 · σ<sub>blank</sub> / m"
                "<br><br>"
                "<b>LOQ</b> (Limit of Quantification):"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "LOQ = 10 · σ<sub>blank</sub> / m"
                "<br><br>"
                "<b>BEC</b> (Blank Equivalent Concentration):"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "BEC = b / m"
                "<br><br>"
                "<span style='color:#666; font-size:11px;'>"
                "where m = slope (counts·s⁻¹ per conc. unit), "
                "b = intercept (counts·s⁻¹), "
                "σ<sub>blank</sub> = std. dev. of signal at lowest standard.</span>"
            ),

            # --- Calibration curve image ---
            self._img("images/ionic_calibration.png"),
        )

    # ── Tab: Transport Rate ──────────────────────────────────────────────

    def _tab_transport(self):
        """
        Build the Transport Rate tab with all three method equations.

        Returns:
            QScrollArea: Tab widget with descriptions, equations, and images.
        """
        return self._scroll(
            # --- Introduction ---
            _styled_label(
                "<h2>Transport Rate Calibration</h2>"
                "<p>The transport rate (η, µL·s⁻¹) is the volume of sample "
                "delivered to the plasma per second. It is required to convert "
                "detected particle counts into mass and number concentration.</p>"
                "<p>Errors in transport rate propagate directly into size and "
                "concentration errors (Pace <i>et al.</i>, <i>Anal. Chem.</i> "
                "<b>83</b>, 9361, 2011; Laborda <i>et al.</i>, <i>Anal. Chem.</i> "
                "<b>91</b>, 13275, 2019).</p>",
                bg="#eef4ff", border="#4a90d9",
            ),

            # --- Method 1: Weight Method ---
            _styled_label(
                "<h3>1. Weight Method</h3>"
                "<p>The most direct approach: measure the mass loss of the "
                "sample vial and the mass collected in the waste container "
                "over a known analysis time.</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Sample consumed:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "Δm<sub>sample</sub> = m<sub>initial</sub> − m<sub>final</sub>"
                "<br><br>"
                "<b>Volume reaching plasma:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "V<sub>plasma</sub> = Δm<sub>sample</sub> − m<sub>waste</sub>"
                "<br><br>"
                "<b>Transport rate:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "η = V<sub>plasma</sub> / (ρ · Δt)"
                "<br><br>"
                "<span style='color:#666; font-size:11px;'>"
                "where ρ ≈ 1.0 g·mL⁻¹ for dilute aqueous solutions, "
                "Δt = analysis time (s). Result in µL·s⁻¹.</span>"
            ),

            # --- Method 2: Particle Number Method ---
            _styled_label(
                "<h3>2. Particle Number Method</h3>"
                "<p>Uses a nanoparticle suspension of known size and "
                "concentration. The transport rate is derived from the "
                "ratio of detected to expected particle events.</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Single-particle mass:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "m<sub>p</sub> = (π/6) · d³ · ρ<sub>p</sub>"
                "<br><br>"
                "<b>Expected particle number concentration:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "C<sub>N</sub> = C<sub>mass</sub> / m<sub>p</sub>"
                "<br><br>"
                "<b>Transport rate:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "η = N<sub>detected</sub> / (C<sub>N</sub> · Δt)"
                "<br><br>"
                "<span style='color:#666; font-size:11px;'>"
                "where d = nominal particle diameter (nm), "
                "ρ<sub>p</sub> = particle density (g·cm⁻³), "
                "C<sub>mass</sub> = mass concentration (ng·L⁻¹), "
                "N<sub>detected</sub> = number of detected particle events, "
                "Δt = acquisition time (s).</span>"
            ),

            # --- Method 3: Mass Method ---
            _styled_label(
                "<h3>3. Mass Method (Dual-Calibration)</h3>"
                "<p>Combines the particle calibration slope (counts vs. mass) "
                "with the ionic calibration slope (signal vs. concentration) "
                "to derive the transport rate as a ratio of the two sensitivities.</p>",
                bg="#e8f5e9", border="#66bb6a",
            ),
            _equation_label(
                "<b>Particle calibration:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "S<sub>part</sub> = slope of (total counts) vs. (particle mass in fg)"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "<span style='color:#666;'>units: counts · fg⁻¹</span>"
                "<br><br>"
                "<b>Ionic calibration:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "S<sub>ion</sub> = slope of (signal in counts·s⁻¹) vs. "
                "(concentration)"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "<span style='color:#666;'>units: counts·s⁻¹ per conc. unit</span>"
                "<br><br>"
                "<b>Transport rate:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "η = S<sub>ion</sub> / S<sub>part</sub>"
                "<br><br>"
                "<span style='color:#666; font-size:11px;'>"
                "The ionic slope is adjusted to consistent mass units before "
                "division (e.g. ppb → µg·L⁻¹ if needed).</span>"
            ),

            # --- Particle sizing from transport rate ---
            _styled_label(
                "<h3>Downstream: Particle Sizing</h3>"
                "<p>Once the transport rate is known, individual particle "
                "masses and diameters are calculated from their detected "
                "counts.</p>",
                bg="#fff3e0", border="#ffb74d",
            ),
            _equation_label(
                "<b>Particle mass:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "m<sub>p</sub> (fg) = total counts / (S<sub>ion</sub> / η)"
                "<br><br>"
                "<b>Volume:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "V = m<sub>p</sub> / ρ<sub>p</sub>"
                "<br><br>"
                "<b>Equivalent spherical diameter:</b>"
                "<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                "d = 2 · (3V / 4π)<sup>1/3</sup>"
            ),

            # --- Images ---
            self._img("images/methods.png"),
            self._img("images/transport_effect.png"),
        )
        
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
            "<h3 align='center'>Version 1.0.2</h3>"
            "<p align='center'>Advanced SP-ICP-ToF-MS data analysis.<br>"
            "Peak detection - Calibration - Nanoparticle quantification.</p>"
        ))
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignCenter)

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(_help_dialog_qss())

    def showEvent(self, event):
        self.apply_theme()
        super().showEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dlg = DetectionMethodsDialog()
    dlg.showMaximized()
    sys.exit(app.exec())