import numpy as np
from statistics import NormalDist
from PySide6.QtGui import QColor
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from PySide6.QtWidgets import QWidget, QLabel, QApplication
from PySide6.QtCore import Qt
import os
from functools import lru_cache
from scipy.stats import poisson
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from scipy.special import erfc

os.environ['NUMBA_THREADING_LAYER'] = 'safe'

try:
    from numba import jit, config
    config.THREADING_LAYER = 'safe'
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("numba not available - install with 'pip install numba'")
    def jit(*args, **kwargs):
        """
        Args:
            *args (Any): Additional positional arguments.
            **kwargs (Any): Additional keyword arguments.
        Returns:
            object: Result of the operation.
        """
        def decorator(func):
            """
            Args:
                func (Any): Callable to invoke.
            Returns:
                object: Result of the operation.
            """
            return func
        return decorator
    def prange(x):
        """
        Args:
            x (Any): Input array or value.
        Returns:
            object: Result of the operation.
        """
        return range(x)

try:
    from scipy.ndimage import uniform_filter1d
    from scipy.interpolate import interp1d, RegularGridInterpolator
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("scipy not available - using fallback smoothing")

from scipy import stats, special
from numba import jit

try:
    from sklearn.mixture import GaussianMixture
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("scikit-learn not available - GMM method disabled. Install with 'pip install scikit-learn'")


# ----------------------------------------------------------------------------------------------------------
# ------------------------------------mathematical utility--------------------------------------------
# ----------------------------------------------------------------------------------------------------------

def erf(x: float | np.ndarray) -> float | np.ndarray:
    """
    Error function using SciPy's optimized implementation.

    Args:
        x (float | np.ndarray): Input value or array

    Returns:
        float | np.ndarray: Error function result
    """
    return special.erf(x)


def erfinv(x: float | np.ndarray) -> float | np.ndarray:
    """
    Inverse error function using SciPy's optimized implementation.

    Args:
        x (float | np.ndarray): Input value or array

    Returns:
        float | np.ndarray: Inverse error function result
    """
    return special.erfinv(x)


def lognormal_cdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """
    Optimized log-normal cumulative distribution function.

    Args:
        x (np.ndarray): Input values
        mu (float): Mean of log-normal distribution
        sigma (float): Standard deviation of log-normal distribution

    Returns:
        np.ndarray: CDF values
    """
    return stats.lognorm.cdf(x, s=sigma, scale=np.exp(mu))


def lognormal_quantile(quantile: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """
    Optimized log-normal quantile function.

    Args:
        quantile (np.ndarray): Quantile values
        mu (float): Mean of log-normal distribution
        sigma (float): Standard deviation of log-normal distribution

    Returns:
        np.ndarray: Quantile results
    """
    return stats.lognorm.ppf(quantile, s=sigma, scale=np.exp(mu))


@jit(nopython=True, cache=True)
def _poisson_pdf_numba(k, lam):
    """
    Numba-optimized Poisson probability mass function for single values.

    Args:
        k (int): Number of events
        lam (float): Lambda parameter

    Returns:
        float: Poisson PMF value
    """
    if k < 0:
        return 0.0
    if k == 0:
        return np.exp(-lam)
    log_pmf = k * np.log(lam) - lam
    for i in range(1, k + 1):
        log_pmf -= np.log(i)
    return np.exp(log_pmf)


def poisson_pdf(k: np.ndarray, lam: float) -> np.ndarray:
    """
    Optimized Poisson probability mass function.

    Args:
        k (np.ndarray): Number of events array
        lam (float): Lambda parameter

    Returns:
        np.ndarray: Poisson PMF values
    """
    k = np.asarray(k, dtype=int)
    assert np.all(k >= 0)
    if k.size < 100:
        return np.array([_poisson_pdf_numba(ki, lam) for ki in k.flat]).reshape(k.shape)
    return stats.poisson.pmf(k, lam)


def zero_trunc_quantile(lam: np.ndarray | float, y: np.ndarray | float) -> np.ndarray | float:
    """
    Calculate zero-truncated Poisson quantile.

    Args:
        lam (np.ndarray | float): Lambda parameter
        y (np.ndarray | float): Quantile values

    Returns:
        np.ndarray | float: Zero-truncated quantile values
    """
    k0 = np.exp(-lam)
    return np.maximum((y - k0) / (1.0 - k0), 0.0)


@jit(nopython=True, cache=True)
def sum_iid_lognormals(n: float, mu: float, sigma: float, method: str = "Fenton-Wilkinson") -> tuple[float, float]:
    """
    Sum of n identical independent log-normal distributions.

    Args:
        n (float): Number of distributions to sum
        mu (float): Mean parameter
        sigma (float): Standard deviation parameter
        method (str): Method to use ("Fenton-Wilkinson" or "Lo")

    Returns:
        tuple[float, float]: Resulting mu and sigma
    """
    if method == "Fenton-Wilkinson":
        sigma2_x = np.log((np.exp(sigma ** 2) - 1.0) / n + 1.0)
        mu_x = np.log(n) + mu + 0.5 * (sigma ** 2 - sigma2_x)
        return mu_x, np.sqrt(sigma2_x)
    else:
        exp_term = np.exp(mu + 0.5 * sigma ** 2)
        Sp = n * exp_term
        sigma2_s = n * sigma ** 2 * exp_term ** 2 / Sp ** 2
        return np.log(Sp) - 0.5 * sigma2_s, np.sqrt(sigma2_s)


@jit(nopython=True, cache=True)
def _standard_quantile_scalar(p):
    """
    Optimized scalar standard normal quantile function.

    Args:
        p (float): Probability value

    Returns:
        float: Standard normal quantile
    """
    if p <= 0:
        return -np.inf
    if p >= 1:
        return np.inf
    if p == 0.5:
        return 0.0
    a = np.array([-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2,
                  1.383577518672690e2, -3.066479806614716e1, 2.506628277459239])
    b = np.array([-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2,
                  6.680131188771972e1, -1.328068155288572e1, 1.0])
    c = np.array([-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838,
                  -2.549732539343734, 4.374664141464968, 2.938163982698783])
    d = np.array([7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996,
                  3.754408661907416, 1.0])
    if p < 0.02425:
        z = np.sqrt(-2.0 * np.log(p))
        num = c[0]
        for i in range(1, 6):
            num = num * z + c[i]
        den = d[0]
        for i in range(1, 5):
            den = den * z + d[i]
        return num / den
    elif p > 0.97575:
        z = np.sqrt(-2.0 * np.log(1.0 - p))
        num = c[0]
        for i in range(1, 6):
            num = num * z + c[i]
        den = d[0]
        for i in range(1, 5):
            den = den * z + d[i]
        return -num / den
    else:
        z = (p - 0.5) ** 2
        num = a[0]
        for i in range(1, 6):
            num = num * z + a[i]
        den = b[0]
        for i in range(1, 6):
            den = den * z + b[i]
        return (p - 0.5) * num / den


def standard_quantile(p: float | np.ndarray) -> float | np.ndarray:
    """
    Optimized standard normal quantile function.

    Args:
        p (float | np.ndarray): Probability value or array

    Returns:
        float | np.ndarray: Standard normal quantile values
    """
    if np.isscalar(p):
        return _standard_quantile_scalar(float(p))
    p = np.asarray(p)
    if p.size < 50:
        return np.array([_standard_quantile_scalar(pi) for pi in p.flat]).reshape(p.shape)
    else:
        return stats.norm.ppf(p)


def compound_poisson_lognormal_quantile_approximation(q: float, lam: float, mu: float, sigma: float) -> float:
    """
    Compound Poisson log-normal quantile approximation.

    Args:
        q (float): Quantile value
        lam (float): Lambda parameter
        mu (float): Mean parameter
        sigma (float): Standard deviation parameter

    Returns:
        float: Approximated quantile
    """
    uk = int(poisson.ppf(1.0 - 1e-12, lam))
    k = np.arange(0, uk + 1, dtype=int)
    pdf = poisson.pmf(k, lam)
    valid = np.isfinite(pdf) & (pdf > 0)
    k, pdf = k[valid], pdf[valid]
    q0 = zero_trunc_quantile(lam, q)
    if q0 <= 0.0:
        return 0.0
    weights = pdf[1:] / pdf[1:].sum()
    k = k[1:]
    mus, sigmas = sum_iid_lognormals(k, np.log(1.0) - 0.5 * sigma ** 2, sigma)
    upper_q = lognormal_quantile(np.array([q0]), mus[-1], sigmas[-1])[0]
    xs = np.linspace(lam, upper_q, 10000)
    cdf = np.sum([w * lognormal_cdf(xs, m, s) for w, m, s in zip(weights, mus, sigmas)], axis=0)
    return xs[np.argmax(cdf > q0)]


def compound_poisson_lognormal_quantile_approximation_fast(q: float, lam: float, mu: float, sigma: float) -> float:
    """
    Optimized compound Poisson log-normal quantile approximation.
    2000 linspace points + vectorized matrix multiply for CDF.

    Args:
        q (float): Quantile value
        lam (float): Lambda parameter
        mu (float): Mean parameter
        sigma (float): Standard deviation parameter

    Returns:
        float: Approximated quantile
    """
    uk = int(poisson.ppf(1.0 - 1e-12, lam))
    k = np.arange(0, uk + 1, dtype=int)
    pdf = poisson.pmf(k, lam)
    valid = np.isfinite(pdf) & (pdf > 0)
    k, pdf = k[valid], pdf[valid]
    q0 = zero_trunc_quantile(lam, q)
    if q0 <= 0.0:
        return 0.0
    weights = pdf[1:] / pdf[1:].sum()
    k = k[1:]
    mus, sigmas = sum_iid_lognormals(k, np.log(1.0) - 0.5 * sigma ** 2, sigma)
    upper_q = lognormal_quantile(np.array([q0]), mus[-1], sigmas[-1])[0]
    xs = np.linspace(lam, upper_q, 2000)
    cdf_matrix = np.column_stack([lognormal_cdf(xs, m, s) for m, s in zip(mus, sigmas)])
    cdf = cdf_matrix @ weights
    return xs[np.argmax(cdf > q0)]


# ----------------------------------------------------------------------------------------------------------
# ------------------------------------compound poisson lognormal class---------------------------------------
# ----------------------------------------------------------------------------------------------------------

class CompoundPoissonLognormal:
    """
    Compound Poisson-Lognormal distribution using analytical approximation.

    Implements analytical approximation for compound Poisson distributions
    where individual events follow a log-normal distribution using the
    Fenton-Wilkinson approximation for summing log-normal distributions.
    """

    def get_threshold(self, lambda_bkgd, alpha, sigma=0.47):
        """
        Calculate compound Poisson threshold using log-normal approximation.

        Args:
            lambda_bkgd (float): Background signal mean
            alpha (float): Significance level
            sigma (float): Log standard deviation of single-ion signal

        Returns:
            float: Threshold value
        """
        if lambda_bkgd <= 0:
            return 0.0
        try:
            quantile = 1.0 - alpha
            mu = np.log(1.0) - 0.5 * sigma ** 2
            threshold = compound_poisson_lognormal_quantile_approximation(
                quantile, lambda_bkgd, mu, sigma
            )
            return float(threshold)
        except Exception as e:
            print(f"Lognormal approximation error: {e}, using simple approximation")
            return lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)


class CompoundPoissonLognormalOptimized:
    """
    Optimized Compound Poisson-Lognormal with dict cache
    keyed on rounded (lambda, alpha, sigma) + faster quantile approximation.
    """

    def __init__(self):
        self._threshold_cache = {}

    def get_threshold(self, lambda_bkgd, alpha, sigma=0.47):
        """
        Calculate compound Poisson threshold with caching.

        Args:
            lambda_bkgd (float): Background signal mean
            alpha (float): Significance level
            sigma (float): Log standard deviation of single-ion signal

        Returns:
            float: Threshold value
        """
        if lambda_bkgd <= 0:
            return 0.0
        cache_key = (round(float(lambda_bkgd), 2), alpha, sigma)
        if cache_key in self._threshold_cache:
            return self._threshold_cache[cache_key]
        try:
            quantile = 1.0 - alpha
            mu = np.log(1.0) - 0.5 * sigma ** 2
            threshold = compound_poisson_lognormal_quantile_approximation_fast(
                quantile, lambda_bkgd, mu, sigma
            )
            result = float(threshold)
            self._threshold_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"Lognormal approximation error: {e}, using simple approximation")
            result = lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)
            self._threshold_cache[cache_key] = result
            return result

    def clear_cache(self):
        """Clear the threshold cache (e.g. when sigma changes)."""
        self._threshold_cache.clear()


INTEGRATION_METHODS = ["Background", "Threshold", "Midpoint"]

PEAK_SPLIT_METHODS = [
    "No Splitting",
    "1D Watershed",
]


# ----------------------------------------------------------------------------------------------------------
# ------------------------------------module-level splitting helpers-----------------------------------------
# ----------------------------------------------------------------------------------------------------------

def _assignments_to_regions(assignments: np.ndarray, n_peaks: int, start_idx: int):
    """
    Convert per-sample peak-index assignments to a list of contiguous
    (global_start, global_end) index pairs — one per peak component.

    Points assigned to the same component are merged into the tightest
    contiguous block that covers all assigned indices. Empty components
    are silently dropped.

    Args:
        assignments (np.ndarray): per-sample peak index (0 … n_peaks-1)
        n_peaks     (int):        total number of components
        start_idx   (int):        global index of region[0]

    Returns:
        list[tuple[int,int]]: sorted list of (global_start, global_end)
    """
    sub_regions = []
    for peak_id in range(n_peaks):
        indices = np.where(assignments == peak_id)[0]
        if len(indices) == 0:
            continue
        sub_regions.append((start_idx + int(indices[0]),
                             start_idx + int(indices[-1])))
    sub_regions.sort(key=lambda r: r[0])
    return [(s, e) for s, e in sub_regions if e >= s]


# ----------------------------------------------------------------------------------------------------------
# ------------------------------------PeakDetection class---------------------------------------------------
# ----------------------------------------------------------------------------------------------------------

class PeakDetection:
    """
    Features:
    - Iterative threshold calculation with Aitken Δ² acceleration
    - Vectorized NumPy operations + Numba JIT
    - Batch threshold processing with caching
    - Rolling-window (dynamic) background
    - Analytical log-normal compound Poisson for ToF data
    - Multiple integration methods (Background, Threshold, Midpoint)
    - Five peak-splitting methods (see PEAK_SPLIT_METHODS)

    Threshold methods:
      "Compound Poisson LogNormal"   – Analytical CPLN (Fenton-Wilkinson)
      "Manual"                       – User-specified threshold

    Integration methods:
      "Background"  – signal − lambda_bkgd  (full peak region)
      "Threshold"   – signal − threshold    (only above threshold)
      "Midpoint"    – signal − midpoint     (only above midpoint)

    Peak splitting methods:
      "No Splitting"  – baseline, no change
      "1D Watershed"  – valley-depth ratio criterion (default, ratio=0.50)
    """

    def __init__(self):
        """Initialize PeakDetection instance."""
        self._cache_hits = 0
        self._cache_misses = 0
        self.iter_eps = 1e-3
        self.default_max_iters = 4
        self.compound_poisson_lognormal = CompoundPoissonLognormalOptimized()
        self.incremental_enabled = True

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------performance-----------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def optimize_data_types(self, signal):
        """
        Optimize signal data types to reduce memory usage.
        Skips f32 downcast when numba path will immediately cast back to f64.

        Args:
            signal (ndarray): Signal array

        Returns:
            ndarray: Optimized signal array
        """
        if NUMBA_AVAILABLE and len(signal) > 500:
            return signal
        if signal.dtype == np.float64:
            if np.all(np.abs(signal) < 1e6):
                return signal.astype(np.float32)
        return signal

    def prepare_signals_for_processing(self, signals_dict):
        """
        Prepare all signals for processing by optimizing data types.

        Args:
            signals_dict (dict): Dictionary of signals

        Returns:
            dict: Dictionary of optimized signals
        """
        return {key: self.optimize_data_types(sig) for key, sig in signals_dict.items()}

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------numba optimized------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    @staticmethod
    @jit(nopython=True, nogil=True)
    def _find_particles_numba(raw_signal, threshold, lambda_bkgd, min_continuous_points, integration_level):
        """
        JIT-compiled particle detection with configurable integration baseline.

        Args:
            raw_signal            (ndarray): Raw signal data
            threshold             (float):   Detection threshold
            lambda_bkgd           (float):   Background level (defines peak region boundaries)
            min_continuous_points (int):     Minimum continuous points required
            integration_level     (float):   Baseline for integration

        Returns:
            tuple: Lists of particle starts, ends, heights, and counts
        """
        n = len(raw_signal)
        particles_start = []
        particles_end = []
        particles_height = []
        particles_counts = []

        i = 0
        while i < n:
            if raw_signal[i] > lambda_bkgd:
                start_idx = i
                while i < n and raw_signal[i] > lambda_bkgd:
                    i += 1
                end_idx = i - 1

                consecutive_count = 0
                max_consecutive = 0
                for j in range(start_idx, end_idx + 1):
                    if raw_signal[j] > threshold:
                        consecutive_count += 1
                        if consecutive_count > max_consecutive:
                            max_consecutive = consecutive_count
                    else:
                        consecutive_count = 0

                if max_consecutive >= min_continuous_points:
                    max_height = 0.0
                    total_counts = 0.0
                    for j in range(start_idx, end_idx + 1):
                        if raw_signal[j] > max_height:
                            max_height = raw_signal[j]
                        if raw_signal[j] > integration_level:
                            total_counts += raw_signal[j] - integration_level

                    if total_counts > 0:
                        particles_start.append(start_idx)
                        particles_end.append(end_idx)
                        particles_height.append(max_height)
                        particles_counts.append(total_counts)
            else:
                i += 1
        return particles_start, particles_end, particles_height, particles_counts

    @staticmethod
    @jit(nopython=True, nogil=True)
    def _find_particles_numba_dynamic(raw_signal, threshold_arr, lambda_bkgd_arr,
                                      min_continuous_points, integration_level_arr):
        """
        JIT-compiled particle detection for dynamic array thresholds (window)
        with configurable integration baseline array.
        Args:
            raw_signal (Any): The raw signal.
            threshold_arr (Any): The threshold arr.
            lambda_bkgd_arr (Any): The lambda bkgd arr.
            min_continuous_points (Any): The min continuous points.
            integration_level_arr (Any): The integration level arr.
        Returns:
            tuple: Result of the operation.
        """
        n = len(raw_signal)
        particles_start = []
        particles_end = []
        particles_height = []
        particles_counts = []

        i = 0
        while i < n:
            if raw_signal[i] > lambda_bkgd_arr[i]:
                start_idx = i
                while i < n and raw_signal[i] > lambda_bkgd_arr[i]:
                    i += 1
                end_idx = i - 1

                consecutive_count = 0
                max_consecutive = 0
                for j in range(start_idx, end_idx + 1):
                    if raw_signal[j] > threshold_arr[j]:
                        consecutive_count += 1
                        if consecutive_count > max_consecutive:
                            max_consecutive = consecutive_count
                    else:
                        consecutive_count = 0

                if max_consecutive >= min_continuous_points:
                    max_height = 0.0
                    total_counts = 0.0
                    for j in range(start_idx, end_idx + 1):
                        if raw_signal[j] > max_height:
                            max_height = raw_signal[j]
                        if raw_signal[j] > integration_level_arr[j]:
                            total_counts += raw_signal[j] - integration_level_arr[j]

                    if total_counts > 0:
                        particles_start.append(start_idx)
                        particles_end.append(end_idx)
                        particles_height.append(max_height)
                        particles_counts.append(total_counts)
            else:
                i += 1
        return particles_start, particles_end, particles_height, particles_counts

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------threshold calculation-------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def calculate_iterative_threshold(self, signal, method, alpha=0.000001, max_iters=4,
                                      manual_threshold=10.0, element_key=None, sigma=0.47,
                                      use_window_size=False, window_size=5000):
        """
        Calculate threshold using iterative background refinement with
        Aitken Δ² acceleration for faster convergence.

        The iterative loop estimates the background (lambda) by excluding
        above-threshold points, then recomputes the threshold from the
        refined background. This is a fixed-point iteration:

            T_{n+1} = f(mean(signal[signal < T_n]))

        Standard iteration converges linearly. Aitken Δ² acceleration
        uses three consecutive iterates (T0, T1, T2) to extrapolate
        directly to the fixed point:

            T_accel = T0 - (T1 - T0)² / (T2 - 2·T1 + T0)

        Args:
            signal            (ndarray): Signal data
            method            (str):     Detection method
            alpha             (float):   Significance level
            max_iters         (int):     Maximum iterations (safety cap)
            manual_threshold  (float):   Manual threshold value
            element_key       (str):     Element identifier
            sigma             (float):   Sigma parameter for compound Poisson
            use_window_size   (bool):    Whether to apply rolling window
            window_size       (int):     Window size for background calculation

        Returns:
            dict: Threshold data including background and convergence info
        """
        overall_mean_signal = np.mean(signal)

        if method == "Manual":
            threshold = manual_threshold
            if use_window_size:
                lambda_bkgd = self._rolling_background(signal, threshold, window_size)
            else:
                below = signal[signal < threshold]
                lambda_bkgd = np.mean(below) if len(below) > 0 else overall_mean_signal
            return {
                'threshold': threshold,
                'background': lambda_bkgd,
                'LOD_counts': threshold,
                'LOD_MDL': np.maximum(0, threshold - np.mean(lambda_bkgd)
                                      if use_window_size else threshold - lambda_bkgd),
                'iterations': 1,
                'convergence': 'manual',
                'method_used': 'Manual',
                'window_applied': use_window_size,
                'window_size_used': window_size if use_window_size else None,
            }

        if use_window_size:
            kernel = np.ones(window_size) / window_size
            lambda_for_threshold = np.convolve(
                np.pad(signal, window_size // 2, mode='reflect'), kernel, mode='valid'
            )[:len(signal)]
            threshold = np.full_like(signal, np.inf)
            prev_threshold = np.full_like(signal, np.inf)
        else:
            lambda_for_threshold = overall_mean_signal
            threshold = np.inf
            prev_threshold = np.inf

        iters = 0
        iter_eps = 1e-3
        thresh_history = []
        aitken_applied = False

        while iters < max_iters or iters == 0:
            if iters > 0:
                prev_threshold = threshold
                if use_window_size:
                    lambda_for_threshold = self._rolling_background(signal, threshold, window_size)
                else:
                    below = signal[signal < threshold]
                    lambda_for_threshold = np.mean(below) if len(below) > 0 else overall_mean_signal

            if use_window_size:
                threshold = self._calculate_array_threshold(lambda_for_threshold, method, alpha, sigma)
                thresh_scalar = float(np.mean(threshold))
                max_diff = np.max(np.abs(prev_threshold - threshold)) if iters > 0 else np.inf
            else:
                threshold = self._calculate_single_threshold(lambda_for_threshold, method, alpha, sigma)
                thresh_scalar = float(threshold)
                max_diff = np.abs(prev_threshold - threshold)

            thresh_history.append(thresh_scalar)
            iters += 1

            if max_diff <= iter_eps:
                break

            if len(thresh_history) >= 3 and not aitken_applied:
                t0, t1, t2 = thresh_history[-3], thresh_history[-2], thresh_history[-1]
                denom = t2 - 2.0 * t1 + t0
                if abs(denom) > 1e-15:
                    t_accel = t0 - (t1 - t0) ** 2 / denom
                    t_min = min(t0, t1, t2)
                    t_max = max(t0, t1, t2)
                    if t_accel > 0 and t_min * 0.8 <= t_accel <= t_max * 1.2:
                        if use_window_size:
                            scale = t_accel / thresh_scalar if thresh_scalar > 0 else 1.0
                            threshold = threshold * scale
                        else:
                            threshold = t_accel
                        aitken_applied = True
                        if abs(t_accel - thresh_scalar) <= iter_eps:
                            break

        lambda_bkgd = lambda_for_threshold
        mean_bg = np.mean(lambda_bkgd) if use_window_size else lambda_bkgd
        mean_thresh = np.mean(threshold) if use_window_size else threshold

        convergence_tag = (f'aitken_converged_after_{iters}'
                           if aitken_applied else f'converged_after_{iters}')

        return {
            'threshold': threshold,
            'background': lambda_bkgd,
            'LOD_counts': mean_thresh,
            'LOD_MDL': max(0, mean_thresh - mean_bg),
            'iterations': iters,
            'convergence': convergence_tag,
            'method_used': method,
            'window_applied': use_window_size,
            'window_size_used': window_size if use_window_size else None,
        }

    def _rolling_background(self, signal, threshold, window_size):
        """
        Calculates a dynamic rolling background excluding peaks above threshold.
        Uses uniform_filter1d — O(n) regardless of window_size.
        Args:
            signal (Any): The signal.
            threshold (Any): The threshold.
            window_size (Any): The window size.
        Returns:
            object: Result of the operation.
        """
        valid_mask = signal < threshold
        valid_signal = signal * valid_mask
        mask_float = valid_mask.astype(np.float64)
        mean_signal = uniform_filter1d(valid_signal.astype(np.float64), size=window_size, mode='reflect')
        mean_mask = uniform_filter1d(mask_float, size=window_size, mode='reflect')
        mean_mask = np.maximum(mean_mask, 1.0 / window_size)
        local_bg = mean_signal / mean_mask
        return local_bg[:len(signal)]

    def _calculate_array_threshold(self, lambda_bkgd_array, method, alpha, sigma=0.47):
        """
        Fast threshold calculation for moving window arrays.
        Adaptive interpolation grid size.
        Args:
            lambda_bkgd_array (Any): The lambda bkgd array.
            method (Any): The method.
            alpha (Any): The alpha.
            sigma (Any): Standard deviation (sigma) value.
        Returns:
            object: Result of the operation.
        """
        if method in ["Manual"]:
            return self._calculate_single_threshold(lambda_bkgd_array, method, alpha, sigma)
        elif method in ["Compound Poisson LogNormal"]:
            min_bg = np.min(lambda_bkgd_array)
            max_bg = np.max(lambda_bkgd_array)
            if min_bg == max_bg:
                single_thresh = self._calculate_single_threshold(min_bg, method, alpha, sigma)
                return np.full_like(lambda_bkgd_array, single_thresh)
            n_eval = min(30, max(5, int((max_bg - min_bg) / 0.5)))
            eval_bg = np.linspace(min_bg, max_bg, n_eval)
            eval_thresh = np.array([
                self._calculate_single_threshold(bg, method, alpha, sigma) for bg in eval_bg
            ])
            return np.interp(lambda_bkgd_array, eval_bg, eval_thresh)
        else:
            return lambda_bkgd_array + 3.0 * np.sqrt(np.maximum(lambda_bkgd_array, 1))

    def _calculate_single_threshold(self, lambda_bkgd, method, alpha, sigma=0.47):
        """
        Calculate threshold for a single background value.
        Dispatches to the appropriate method engine.

        Args:
            lambda_bkgd (float): Background level
            method      (str):   Detection method
            alpha       (float): Significance level
            sigma       (float): Sigma parameter

        Returns:
            float: Calculated threshold
        """
        if method == "Compound Poisson LogNormal":
            return self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma)
        else:
            return lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)

    @lru_cache(maxsize=10000)
    def _cached_threshold_calculation(self, lambda_bkgd, method, alpha, isotope_key):
        """
        Cached threshold calculation for performance.

        Args:
            lambda_bkgd (float): Background level
            method      (str):   Detection method
            alpha       (float): Significance level
            isotope_key (str):   Isotope identifier for caching

        Returns:
            float: Calculated threshold
        """
        if method == "Compound Poisson LogNormal":
            return self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma=0.47)
        else:
            return lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)

    def calculate_thresholds_batch_safe(self, signals_dict, params_dict,
                                        method_groups=None, isotope_mapping=None):
        """
        Safe batch threshold calculation with iterative refinement and window size support.

        Args:
            signals_dict    (dict): Dictionary of signal arrays
            params_dict     (dict): Dictionary of parameter sets
            method_groups   (dict, optional): Grouped methods
            isotope_mapping (dict, optional): Isotope key mapping

        Returns:
            dict: Dictionary of threshold data for all elements
        """
        optimized_signals = self.prepare_signals_for_processing(signals_dict)

        if method_groups is None:
            method_groups = {}
            for element_key, params in params_dict.items():
                method = params['method']
                if method not in method_groups:
                    method_groups[method] = []
                method_groups[method].append(element_key)

        all_threshold_data = {}

        for method, element_keys in method_groups.items():
            for element_key in element_keys:
                params = params_dict[element_key]
                signal = optimized_signals[element_key]

                use_iterative = params.get('iterative', True)
                max_iters = params.get('max_iterations', 4) if use_iterative else 0
                alpha = params.get('alpha', 0.000001)
                manual_threshold = params.get('manual_threshold', 10.0)
                sigma = params.get('sigma', 0.47)
                use_window_size = params.get('use_window_size', False)
                window_size = params.get('window_size', 5000)
                isotope_key = (isotope_mapping.get(element_key, element_key)
                               if isotope_mapping else element_key)

                try:
                    threshold_data = self.calculate_iterative_threshold(
                        signal=signal,
                        method=method,
                        alpha=alpha,
                        max_iters=max_iters,
                        manual_threshold=manual_threshold,
                        element_key=isotope_key,
                        sigma=sigma,
                        use_window_size=use_window_size,
                        window_size=window_size,
                    )
                    threshold_data['isotope_key'] = isotope_key
                    threshold_data['iterative_used'] = use_iterative
                    all_threshold_data[element_key] = threshold_data

                except Exception as e:
                    print(f"Error calculating iterative threshold for {element_key} using {method}: {e}")
                    working_signal = self.apply_window_size(signal, use_window_size, window_size)
                    lambda_bkgd = np.mean(working_signal)
                    threshold = lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)
                    all_threshold_data[element_key] = {
                        'threshold': threshold,
                        'background': lambda_bkgd,
                        'LOD_counts': threshold,
                        'LOD_MDL': max(0, threshold - lambda_bkgd),
                        'iterations': 0,
                        'convergence': 'fallback_due_to_error',
                        'method_used': method,
                        'isotope_key': isotope_key,
                        'iterative_used': False,
                        'window_applied': use_window_size,
                        'window_size_used': window_size if use_window_size else None,
                    }

        return all_threshold_data

    def calculate_thresholds_batch(self, signals_dict, params_dict, method_groups=None):
        """Wrapper for safe batch threshold processing.
        Args:
            signals_dict (Any): The signals dict.
            params_dict (Any): The params dict.
            method_groups (Any): The method groups.
        Returns:
            object: Result of the operation.
        """
        return self.calculate_thresholds_batch_safe(signals_dict, params_dict, method_groups)

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------integration helpers---------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _compute_integration_level(lambda_bkgd, threshold, integration_method):
        """
        Compute the integration baseline level based on the chosen method.

        Integration methods:
          "Background" : baseline = lambda_bkgd   (full peak, most inclusive)
          "Threshold"  : baseline = threshold      (most conservative)
          "Midpoint"   : baseline = (lambda_bkgd + threshold) / 2

        Works with both scalar and array inputs.

        Args:
            lambda_bkgd        (float | ndarray): Background level
            threshold          (float | ndarray): Detection threshold
            integration_method (str):             One of INTEGRATION_METHODS

        Returns:
            float | ndarray: Integration baseline level
        """
        if integration_method == "Threshold":
            return threshold
        elif integration_method == "Midpoint":
            return (lambda_bkgd + threshold) / 2.0
        else:
            return lambda_bkgd

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------peak splitting section------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def split_peak_region(self, signal, start_idx, end_idx,
                          lambda_bkgd, threshold,
                          split_method="1D Watershed", sigma=0.47,
                          **kwargs):
        """
        Dispatcher: apply the chosen splitting method to a single peak region
        [start_idx, end_idx] (inclusive) and return a list of
        (sub_start, sub_end) pairs.

        Each sub-region is guaranteed to satisfy  sub_end >= sub_start.
        Falls back to [(start_idx, end_idx)] on any error.

        Args:
            signal            (ndarray):          Full raw signal array
            start_idx         (int):              Left boundary (inclusive)
            end_idx           (int):              Right boundary (inclusive)
            lambda_bkgd       (float | ndarray):  Background level
            threshold         (float | ndarray):  Detection threshold
            split_method      (str):              One of PEAK_SPLIT_METHODS
            sigma             (float):            Log-normal sigma (unused, kept for API compat)

        Returns:
            list[tuple[int,int]]: List of (sub_start, sub_end) pairs
        """
        try:
            if split_method == "No Splitting" or split_method is None:
                return [(start_idx, end_idx)]
            elif split_method == "1D Watershed":
                return self._split_watershed_1d(
                    signal, start_idx, end_idx, lambda_bkgd, threshold,
                    **kwargs)
            else:
                return [(start_idx, end_idx)]
        except Exception as exc:
            print(f"split_peak_region ({split_method}) error: {exc}")
            return [(start_idx, end_idx)]


    # ── Method 1 — No Splitting ───────────────────────────────────────────────

    @staticmethod
    def _split_no_split(signal, start_idx, end_idx, **kwargs):
        """Baseline: return the region unchanged.
        Args:
            signal (Any): The signal.
            start_idx (Any): The start idx.
            end_idx (Any): The end idx.
            **kwargs (Any): Additional keyword arguments.
        Returns:
            list: Result of the operation.
        """
        return [(start_idx, end_idx)]

    # ── Method 2 — 1D Watershed ──────────────────────────────────────────────

    @staticmethod
    def _split_watershed_1d(signal, start_idx, end_idx,
                            lambda_bkgd, threshold,
                            min_valley_ratio=0.50,
                            min_peak_distance=2,
                            _depth=0,
                            **kwargs):
        """
        1D Watershed peak splitting — operates directly on the raw signal
        with no pre-smoothing.

        Finds local maxima above threshold, then checks each valley between
        consecutive maxima:
          - valley_val / min(peak_left, peak_right) < min_valley_ratio
        If the criterion is met the region is split at the valley minimum.
        Recursion handles nested doublets.

        Args:
            signal            (ndarray): Full raw signal array
            start_idx         (int):     Left boundary (inclusive)
            end_idx           (int):     Right boundary (inclusive)
            lambda_bkgd       (float | ndarray): Background level
            threshold         (float | ndarray): Detection threshold
            min_valley_ratio  (float):   Valley-to-peak ratio below which a
                                         split is triggered (default 0.50)
            min_peak_distance (int):     Minimum samples between two peaks

        Returns:
            list[tuple[int,int]]: (sub_start, sub_end) pairs
        """
        if _depth > 10:
            return [(start_idx, end_idx)]

        raw_region = signal[start_idx:end_idx + 1]
        n = len(raw_region)
        if n < 3:
            return [(start_idx, end_idx)]

        thresh_val = (float(np.mean(threshold[start_idx:end_idx + 1]))
                      if not np.isscalar(threshold) else float(threshold))

        peaks, _ = find_peaks(raw_region, height=thresh_val,
                              distance=max(1, min_peak_distance))

        if len(peaks) <= 1:
            return [(start_idx, end_idx)]

        # ── Find qualifying split valleys ──────────────────────────────────
        split_points = []
        keep = [peaks[0]]
        for i in range(1, len(peaks)):
            li, ri = keep[-1], peaks[i]
            valley_val = float(raw_region[li:ri + 1].min())
            left_peak  = float(raw_region[li])
            right_peak = float(raw_region[ri])
            min_peak   = min(left_peak, right_peak)

            ratio = valley_val / min_peak if min_peak > 0 else 0.0
            if ratio < min_valley_ratio:
                valley_local = int(np.argmin(raw_region[li:ri + 1]))
                split_points.append(li + valley_local)
                keep.append(peaks[i])
            else:
                if right_peak > left_peak:
                    keep[-1] = peaks[i]

        if not split_points:
            return [(start_idx, end_idx)]

        # ── Build sub-regions and recurse ──────────────────────────────────
        sub_regions = []
        prev = start_idx
        for sp in split_points:
            g = start_idx + sp
            sub_regions.append((prev, g))
            prev = g + 1
        sub_regions.append((prev, end_idx))
        sub_regions = [(s, e) for s, e in sub_regions if e >= s]

        result = []
        for s, e in sub_regions:
            result.extend(
                PeakDetection._split_watershed_1d(
                    signal, s, e, lambda_bkgd, threshold,
                    min_valley_ratio, min_peak_distance,
                    _depth=_depth + 1,
                )
            )
        return result if result else [(start_idx, end_idx)]


    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------particle metrics helper-----------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _particle_from_region(time, signal, start_idx, end_idx,
                               lambda_bkgd, threshold, integration_level,
                               min_continuous_points, integration_method):
        """
        Extract particle metrics from a single [start_idx, end_idx] sub-region.

        Returns a particle dict, or None if:
          • the region does not contain enough consecutive above-threshold points
          • integrated counts are non-positive

        Args:
            time                  (ndarray):         Time array
            signal                (ndarray):         Raw signal
            start_idx             (int):             Sub-region left boundary
            end_idx               (int):             Sub-region right boundary
            lambda_bkgd           (float|ndarray):   Background level
            threshold             (float|ndarray):   Detection threshold
            integration_level     (float|ndarray):   Integration baseline
            min_continuous_points (int):             Minimum consecutive points
            integration_method    (str):             Integration method label

        Returns:
            dict | None: Particle dict or None
        """
        raw_region = signal[start_idx:end_idx + 1]

        local_thresh = (threshold[start_idx:end_idx + 1]
                        if not np.isscalar(threshold) else threshold)
        local_intlvl = (integration_level[start_idx:end_idx + 1]
                        if not np.isscalar(integration_level) else integration_level)

        above_thresh = raw_region > (local_thresh
                                     if np.isscalar(local_thresh)
                                     else np.asarray(local_thresh))
        if min_continuous_points > 1:
            kernel = np.ones(min_continuous_points)
            conv = np.convolve(above_thresh.astype(int), kernel, mode='valid')
            if len(conv) == 0 or int(np.max(conv)) < min_continuous_points:
                return None
        elif not np.any(above_thresh):
            return None

        above_intlvl = raw_region > (local_intlvl
                                      if np.isscalar(local_intlvl)
                                      else np.asarray(local_intlvl))
        total_counts = float(np.sum((raw_region - local_intlvl) * above_intlvl))
        if total_counts <= 0:
            return None

        peak_local_idx = int(np.argmax(raw_region))
        peak_global_idx = start_idx + peak_local_idx
        max_height = float(raw_region[peak_local_idx])

        peak_thresh = (float(threshold[peak_global_idx])
                       if not np.isscalar(threshold) else float(threshold))
        snr = max_height / peak_thresh if peak_thresh > 0 else 0.0

        return {
            'peak_time': time[peak_global_idx],
            'max_height': max_height,
            'total_counts': total_counts,
            'SNR': snr,
            'left_idx': start_idx,
            'right_idx': end_idx,
            'peak_valid': snr >= 3,
            'integration_method': integration_method,
        }

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------core detection-------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def find_particles_safe(self, time, raw_signal, lambda_bkgd, threshold,
                            min_width=3, min_continuous_points=1,
                            integration_method="Background",
                            split_method="1D Watershed",
                            sigma=0.47,
                            min_valley_ratio=0.50):
        """
        Threading-safe particle detection with configurable integration method
        and peak splitting.

        Args:
            time                  (ndarray):        Time array
            raw_signal            (ndarray):        Raw signal
            lambda_bkgd   (float|ndarray):          Background level
            threshold     (float|ndarray):          Detection threshold
            min_width             (int):            Minimum particle width (samples)
            min_continuous_points (int):            Minimum consecutive above-threshold points
            integration_method    (str):            "Background", "Threshold", or "Midpoint"
            split_method          (str):            One of PEAK_SPLIT_METHODS
            sigma                 (float):          Log-normal sigma (unused, kept for API compat)

        Returns:
            list[dict]: Detected particle dictionaries
        """
        signal = self.optimize_data_types(raw_signal)
        integration_level = self._compute_integration_level(
            lambda_bkgd, threshold, integration_method
        )

        # ── Numba fast path ──────────────────────────────────────────────────
        if NUMBA_AVAILABLE and len(signal) > 500:
            signal_f64 = signal.astype(np.float64)

            if np.isscalar(threshold):
                starts, ends, heights, counts = self._find_particles_numba(
                    signal_f64,
                    float(threshold),
                    float(lambda_bkgd),
                    min_continuous_points,
                    float(integration_level),
                )
            else:
                bkgd_arr = (np.asarray(lambda_bkgd, dtype=np.float64)
                            if not np.isscalar(lambda_bkgd)
                            else np.full(len(signal_f64), float(lambda_bkgd), dtype=np.float64))
                integration_level_arr = np.asarray(integration_level, dtype=np.float64)
                starts, ends, heights, counts = self._find_particles_numba_dynamic(
                    signal_f64,
                    threshold.astype(np.float64),
                    bkgd_arr,
                    min_continuous_points,
                    integration_level_arr,
                )

            particles = []
            for i in range(len(starts)):
                s_idx, e_idx = starts[i], ends[i]

                sub_regions = self.split_peak_region(
                    signal_f64, s_idx, e_idx,
                    lambda_bkgd, threshold,
                    split_method=split_method, sigma=sigma,
                    min_valley_ratio=min_valley_ratio,
                )

                for (ss, se) in sub_regions:
                    p = self._particle_from_region(
                        time, signal, ss, se,
                        lambda_bkgd, threshold, integration_level,
                        min_continuous_points, integration_method,
                    )
                    if p is not None:
                        particles.append(p)

            return particles

        # ── Pure-NumPy path ──────────────────────────────────────────────────
        return self.find_particles_vectorized(
            time, signal,
            lambda_bkgd, threshold,
            min_width, min_continuous_points,
            integration_method,
            split_method=split_method,
            sigma=sigma,
            min_valley_ratio=min_valley_ratio,
        )

    def find_particles_vectorized(self, time, raw_signal, lambda_bkgd, threshold,
                                  min_width=3, min_continuous_points=1,
                                  integration_method="Background",
                                  split_method="1D Watershed",
                                  sigma=0.47,
                                  min_valley_ratio=0.50):
        """
        Vectorized particle detection using NumPy with configurable integration
        and peak splitting.

        Args:
            (same as find_particles_safe)

        Returns:
            list[dict]: Detected particle dictionaries
        """
        integration_level = self._compute_integration_level(
            lambda_bkgd, threshold, integration_method
        )

        above_bg = raw_signal > (lambda_bkgd
                                 if np.isscalar(lambda_bkgd)
                                 else np.asarray(lambda_bkgd))
        padded = np.concatenate(([False], above_bg, [False]))
        changes = np.diff(padded.astype(int))
        starts_arr = np.where(changes == 1)[0]
        ends_arr = np.where(changes == -1)[0]

        if len(starts_arr) == 0 or len(ends_arr) == 0:
            return []

        min_len = min(len(starts_arr), len(ends_arr))
        starts_arr = starts_arr[:min_len]
        ends_arr = ends_arr[:min_len]

        particles = []

        for raw_start, raw_end in zip(starts_arr, ends_arr):
            raw_end = min(raw_end, len(raw_signal) - 1)
            if raw_end <= raw_start:
                continue

            raw_region = raw_signal[raw_start:raw_end + 1]
            local_thresh = (threshold[raw_start:raw_end + 1]
                            if not np.isscalar(threshold) else threshold)
            above_threshold = raw_region > (local_thresh
                                             if np.isscalar(local_thresh)
                                             else np.asarray(local_thresh))

            if min_continuous_points > 1:
                kernel = np.ones(min_continuous_points)
                conv = np.convolve(above_threshold.astype(int), kernel, mode='valid')
                if len(conv) == 0 or int(np.max(conv)) < min_continuous_points:
                    continue
            elif not np.any(above_threshold):
                continue

            sub_regions = self.split_peak_region(
                raw_signal, raw_start, raw_end,
                lambda_bkgd, threshold,
                split_method=split_method, sigma=sigma,
                min_valley_ratio=min_valley_ratio,
            )

            for (ss, se) in sub_regions:
                se = min(se, len(raw_signal) - 1)
                if se <= ss:
                    continue
                p = self._particle_from_region(
                    time, raw_signal, ss, se,
                    lambda_bkgd, threshold, integration_level,
                    min_continuous_points, integration_method,
                )
                if p is not None:
                    particles.append(p)

        return particles

    def find_particles(self, time, raw_signal, lambda_bkgd, threshold,
                       min_width=3, min_continuous_points=1,
                       integration_method="Background",
                       split_method="1D Watershed",
                       sigma=0.47,
                       min_valley_ratio=0.50):
        """Wrapper for safe particle detection.
        Args:
            time (Any): The time.
            raw_signal (Any): The raw signal.
            lambda_bkgd (Any): The lambda bkgd.
            threshold (Any): The threshold.
            min_width (Any): The min width.
            min_continuous_points (Any): The min continuous points.
            integration_method (Any): The integration method.
            split_method (Any): The split method.
            sigma (Any): Standard deviation (sigma) value.
            min_valley_ratio (Any): The min valley ratio.
        Returns:
            object: Result of the operation.
        """
        return self.find_particles_safe(
            time, raw_signal, lambda_bkgd, threshold,
            min_width, min_continuous_points,
            integration_method,
            split_method=split_method,
            sigma=sigma,
            min_valley_ratio=min_valley_ratio,
        )

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------processing------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def process_single_sample_safe(self, main_window, sample_name):
        """Threading-safe sample processing with iterative calculation.
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
        Returns:
            dict: Result of the operation.
        """
        try:
            local_data = main_window.data_by_sample[sample_name]
            local_time = main_window.time_array_by_sample[sample_name]
            sample_params = main_window.sample_parameters.get(sample_name, {})

            signals_for_batch = {}
            params_for_batch = {}
            isotope_mapping = {}
            valid_elements = []

            for element, isotopes in main_window.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    if element_key in sample_params and sample_params[element_key].get('include', True):
                        isotope_key = main_window.find_closest_isotope(isotope)
                        if isotope_key is not None and isotope_key in local_data:
                            signals_for_batch[element_key] = local_data[isotope_key]
                            params_for_batch[element_key] = sample_params[element_key]
                            isotope_mapping[element_key] = isotope_key
                            valid_elements.append((element, isotope, element_key, isotope_key))

            if not signals_for_batch:
                return None

            batch_threshold_data = self.calculate_thresholds_batch_safe(
                signals_for_batch, params_for_batch, isotope_mapping=isotope_mapping
            )

            detected_peaks_for_sample = {}
            all_particles = []
            results_data = []
            local_thresholds = {}

            for element, isotope, element_key, isotope_key in valid_elements:
                if element_key not in batch_threshold_data:
                    continue

                signal = local_data[isotope_key]
                params = params_for_batch[element_key]
                threshold_data = batch_threshold_data[element_key]
                integration_method = params.get('integration_method', 'Background')
                split_method = params.get('split_method', '1D Watershed')
                sigma = params.get('sigma', 0.47)
                min_valley_ratio = params.get('valley_ratio', 0.50)

                try:
                    detected_particles = self.find_particles_safe(
                        local_time, signal,
                        threshold_data['background'], threshold_data['threshold'],
                        min_continuous_points=int(params['min_continuous']),
                        integration_method=integration_method,
                        split_method=split_method,
                        sigma=sigma,
                        min_valley_ratio=min_valley_ratio,
                    )

                    detected_peaks_for_sample[(element, isotope)] = detected_particles
                    local_thresholds[element_key] = threshold_data

                    display_label = main_window.get_formatted_label(element_key)
                    if detected_particles:
                        all_particles.append({
                            'element': element,
                            'isotope': isotope,
                            'signal': signal,
                            'clusters': [(p['left_idx'], p['right_idx']) for p in detected_particles],
                        })
                        for particle in detected_particles:
                            if particle is None:
                                continue
                            results_data.append([
                                display_label,
                                f"{local_time[particle['left_idx']]:.4f}",
                                f"{local_time[particle['right_idx']]:.4f}",
                                f"{particle['total_counts']:.0f}",
                                f"{particle['max_height']:.0f}",
                                f"{particle['SNR']:.2f}",
                            ])

                except Exception as e:
                    print(f"Error processing {element}-{isotope}: {str(e)}")
                    continue

            return {
                'sample_name': sample_name,
                'detected_peaks': detected_peaks_for_sample,
                'results_data': results_data,
                'all_particles': all_particles,
                'thresholds': local_thresholds,
            }

        except Exception as e:
            print(f"Error processing sample {sample_name}: {str(e)}")
            return None

    def process_single_sample(self, main_window, sample_name):
        """
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
        Returns:
            object: Result of the operation.
        """
        return self.process_single_sample_safe(main_window, sample_name)

    def detect_peaks_with_poisson(self, signal, alpha=0.000001,
                                  sample_name=None, element_key=None,
                                  method="Compound Poisson LogNormal",
                                  manual_threshold=10.0, element_thresholds=None,
                                  current_sample=None,
                                  sigma=0.47, iterative=True,
                                  use_window_size=False, window_size=5000):
        """Detect peaks using Poisson-based methods with iterative calculation.

        Args:
            signal            (ndarray): Raw signal array
            alpha             (float):   Significance level (default 1e-6)
            sample_name       (str):     Sample name (unused, kept for API compat)
            element_key       (str):     Element identifier for caching
            method            (str):     "Compound Poisson LogNormal" or "Manual"
            manual_threshold  (float):   Threshold value when method == "Manual"
            element_thresholds (dict):   Pre-calculated thresholds (unused here)
            current_sample    (str):     Current sample name (unused, kept for API compat)
            sigma             (float):   Log-normal sigma for CPLN (default 0.47)
            iterative         (bool):    Enable iterative background refinement (default True)
            use_window_size   (bool):    Use rolling-window background (default False)
            window_size       (int):     Window size for rolling background (default 5000)

        Returns:
            tuple: (signal, lambda_bkgd, threshold, mean_nonzero, threshold_data)
        """
        max_iters = self.default_max_iters if iterative else 1
        try:
            threshold_data = self.calculate_iterative_threshold(
                signal=signal,
                method=method,
                alpha=alpha,
                max_iters=max_iters,
                manual_threshold=manual_threshold,
                element_key=element_key,
                sigma=sigma,
                use_window_size=use_window_size,
                window_size=window_size,
            )
            lambda_bkgd = threshold_data['background']
            threshold = threshold_data['threshold']

        except Exception as e:
            working_signal = self.apply_window_size(signal, use_window_size, window_size)
            lambda_bkgd = np.mean(working_signal) if len(working_signal) > 0 else 0

            if method == "Manual":
                threshold = manual_threshold
                threshold_data = {
                    'threshold': threshold,
                    'background': lambda_bkgd,
                    'LOD_counts': threshold,
                    'iterations': 0,
                    'convergence': 'manual',
                    'method_used': method,
                    'window_applied': use_window_size,
                    'window_size_used': window_size if use_window_size else None,
                }
            elif method == "Compound Poisson LogNormal":
                threshold = self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma=sigma)
                threshold_data = {
                    'threshold': threshold,
                    'background': lambda_bkgd,
                    'LOD_counts': threshold,
                    'iterations': 1,
                    'convergence': 'lognormal_approximation',
                    'method_used': method,
                    'window_applied': use_window_size,
                    'window_size_used': window_size if use_window_size else None,
                }

        mean_nonzero = np.mean(signal[signal > 0]) if len(signal[signal > 0]) > 0 else 0
        return signal, lambda_bkgd, threshold, mean_nonzero, threshold_data

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------incremental detection-------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def detect_particles_incremental(self, main_window):
        """Incremental particle detection for changed elements only.
        Args:
            main_window (Any): The main window.
        """
        original_sample = main_window.current_sample
        overlay = None

        try:
            overlay = QWidget(main_window)
            overlay.setGeometry(main_window.rect())
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")

            message_label = QLabel("Incremental iterative peak detection in progress...", overlay)
            message_label.setStyleSheet(
                "color: white; background-color: rgba(0, 0, 0, 0); "
                "font-size: 16px; font-weight: bold;"
            )
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setGeometry(overlay.rect())
            overlay.show()
            QApplication.processEvents()

            main_window.progress_bar.setVisible(True)
            main_window.progress_bar.setValue(0)

            total_changed_elements = 0
            samples_to_process = {}

            for sample_name in main_window.data_by_sample.keys():
                main_window.load_or_initialize_parameters(sample_name)
                changed_elements, _ = self.get_changed_elements(main_window, sample_name)
                if changed_elements:
                    samples_to_process[sample_name] = changed_elements
                    total_changed_elements += len(changed_elements)

            if total_changed_elements == 0:
                main_window.status_label.setText("No changes detected - skipping detection")
                main_window.progress_bar.setVisible(False)
                if overlay:
                    overlay.hide()
                    overlay.deleteLater()
                return

            main_window.status_label.setText(
                f"Processing {total_changed_elements} changed elements "
                f"across {len(samples_to_process)} samples"
            )
            QApplication.processEvents()

            processed_elements = 0

            for sample_name, changed_elements in samples_to_process.items():
                result = self.process_sample_incremental(main_window, sample_name, changed_elements)

                if result:
                    self.merge_detection_results(main_window, sample_name, result, changed_elements)
                    processed_elements += len(changed_elements)
                    progress = int((processed_elements / total_changed_elements) * 100)
                    main_window.progress_bar.setValue(progress)

                    if overlay and message_label:
                        message_label.setText(
                            f"Incremental detection: {progress}% complete\n"
                            f"Processed {processed_elements}/{total_changed_elements} elements"
                        )
                    QApplication.processEvents()

            if original_sample in samples_to_process:
                self.update_current_sample_display(main_window, original_sample)

            main_window.progress_bar.setVisible(False)
            main_window.status_label.setText(
                f"Incremental detection complete! Processed {total_changed_elements} changed elements"
            )

        except Exception as e:
            print(f"Error in incremental detect_particles: {str(e)}")
            import traceback
            traceback.print_exc()
            main_window.status_label.setText("Error during incremental detection")
            main_window.progress_bar.setVisible(False)
        finally:
            if overlay:
                overlay.hide()
                overlay.deleteLater()

        main_window.unsaved_changes = True

    def process_sample_incremental(self, main_window, sample_name, changed_elements):
        """Process only changed elements for a sample incrementally.
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
            changed_elements (Any): The changed elements.
        Returns:
            dict: Result of the operation.
        """
        try:
            local_data = main_window.data_by_sample[sample_name]
            local_time = main_window.time_array_by_sample[sample_name]
            sample_params = main_window.sample_parameters.get(sample_name, {})

            signals_for_batch = {}
            params_for_batch = {}
            valid_elements = []
            excluded_elements = []

            for element, isotope, element_key, change_type in changed_elements:
                if element_key in sample_params:
                    if sample_params[element_key].get('include', True):
                        isotope_key = main_window.find_closest_isotope(isotope)
                        if isotope_key is not None and isotope_key in local_data:
                            signals_for_batch[element_key] = local_data[isotope_key]
                            params_for_batch[element_key] = sample_params[element_key]
                            valid_elements.append((element, isotope, element_key, isotope_key, change_type))
                    else:
                        excluded_elements.append((element, isotope, element_key))

            detected_peaks_updates = {}
            results_data_updates = []
            threshold_updates = {}

            if signals_for_batch:
                batch_threshold_data = self.calculate_thresholds_batch_safe(
                    signals_for_batch, params_for_batch
                )

                for element, isotope, element_key, isotope_key, change_type in valid_elements:
                    if element_key not in batch_threshold_data:
                        continue

                    signal = local_data[isotope_key]
                    params = params_for_batch[element_key]
                    threshold_data = batch_threshold_data[element_key]
                    integration_method = params.get('integration_method', 'Background')
                    split_method = params.get('split_method', '1D Watershed')
                    sigma = params.get('sigma', 0.47)
                    min_valley_ratio = params.get('valley_ratio', 0.50)

                    try:
                        detected_particles = self.find_particles_safe(
                            local_time, signal,
                            threshold_data['background'], threshold_data['threshold'],
                            min_continuous_points=int(params['min_continuous']),
                            integration_method=integration_method,
                            split_method=split_method,
                            sigma=sigma,
                            min_valley_ratio=min_valley_ratio,
                        )

                        detected_peaks_updates[(element, isotope)] = detected_particles
                        threshold_updates[element_key] = threshold_data

                        display_label = main_window.get_formatted_label(element_key)
                        if detected_particles:
                            for particle in detected_particles:
                                if particle is None:
                                    continue
                                results_data_updates.append([
                                    display_label,
                                    f"{local_time[particle['left_idx']]:.4f}",
                                    f"{local_time[particle['right_idx']]:.4f}",
                                    f"{particle['total_counts']:.0f}",
                                    f"{particle['max_height']:.0f}",
                                    f"{particle['SNR']:.2f}",
                                ])

                    except Exception as e:
                        print(f"Error processing {element}-{isotope}: {str(e)}")
                        continue

            for element, isotope, element_key in excluded_elements:
                detected_peaks_updates[(element, isotope)] = []
                threshold_updates[element_key] = {
                    'threshold': 0, 'background': 0, 'LOD_counts': 0, 'LOD_MDL': 0,
                    'iterations': 0, 'convergence': 'element_excluded',
                    'method_used': 'Excluded', 'window_applied': False,
                    'window_size_used': None,
                }

            return {
                'sample_name': sample_name,
                'detected_peaks_updates': detected_peaks_updates,
                'results_data_updates': results_data_updates,
                'threshold_updates': threshold_updates,
                'changed_elements': (
                    [f"{e}-{i:.4f}" for e, i, _, _, _ in valid_elements] +
                    [f"{e}-{i:.4f}" for e, i, _ in excluded_elements]
                ),
            }

        except Exception as e:
            print(f"Error in incremental processing for {sample_name}: {str(e)}")
            return None

    def merge_detection_results(self, main_window, sample_name, new_results, changed_elements):
        """Merge new detection results with existing results.
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
            new_results (Any): The new results.
            changed_elements (Any): The changed elements.
        """
        try:
            if sample_name not in main_window.sample_detected_peaks:
                main_window.sample_detected_peaks[sample_name] = {}
            if sample_name not in main_window.element_thresholds:
                main_window.element_thresholds[sample_name] = {}
            if sample_name not in main_window.sample_results_data:
                main_window.sample_results_data[sample_name] = []

            for element_isotope_key, particles in new_results['detected_peaks_updates'].items():
                main_window.sample_detected_peaks[sample_name][element_isotope_key] = particles

            for element_key, threshold_data in new_results['threshold_updates'].items():
                main_window.element_thresholds[sample_name][element_key] = threshold_data

            existing_results = main_window.sample_results_data[sample_name]
            changed_element_labels = set()

            for element, isotope, element_key, change_type in changed_elements:
                display_label = main_window.get_formatted_label(element_key)
                changed_element_labels.add(display_label)

            filtered_results = [row for row in existing_results
                                 if row[0] not in changed_element_labels]
            filtered_results.extend(new_results['results_data_updates'])
            main_window.sample_results_data[sample_name] = filtered_results

            all_particles = []
            for (element, isotope), particles in main_window.sample_detected_peaks[sample_name].items():
                if particles:
                    element_key = f"{element}-{isotope:.4f}"
                    isotope_key = main_window.find_closest_isotope(isotope)
                    if isotope_key and isotope_key in main_window.data_by_sample[sample_name]:
                        signal = main_window.data_by_sample[sample_name][isotope_key]
                        all_particles.append({
                            'element': element,
                            'isotope': isotope,
                            'signal': signal,
                            'clusters': [(p['left_idx'], p['right_idx']) for p in particles if p],
                        })

            updated_multi_element_particles = self.process_multi_element_particles(
                all_particles,
                main_window.time_array_by_sample[sample_name],
                {sample_name: main_window.sample_detected_peaks[sample_name]},
                main_window.selected_isotopes,
                main_window.get_formatted_label,
                sample_name,
                {sample_name: main_window.element_thresholds[sample_name]},
                main_window.parameters_table,
            )
            main_window.sample_particle_data[sample_name] = updated_multi_element_particles

        except Exception as e:
            print(f"Error merging results for {sample_name}: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_current_sample_display(self, main_window, sample_name):
        """Update display for currently selected sample.
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
        """
        if sample_name == main_window.current_sample:
            main_window.detected_peaks = main_window.sample_detected_peaks.get(sample_name, {})
            if sample_name in main_window.sample_particle_data:
                main_window.multi_element_particles = main_window.sample_particle_data[sample_name]
                main_window.update_multi_element_table()
            current_row = main_window.parameters_table.currentRow()
            if current_row >= 0:
                main_window.parameters_table_clicked(current_row, 0)

    def apply_window_size(self, signal, use_window_size, window_size):
        """Apply window size limitation to signal if enabled.
        Args:
            signal (Any): The signal.
            use_window_size (Any): The use window size.
            window_size (Any): The window size.
        Returns:
            object: Result of the operation.
        """
        if not use_window_size or window_size <= 0:
            return signal
        signal_length = len(signal)
        if window_size >= signal_length:
            return signal
        start_idx = max(0, (signal_length - window_size) // 2)
        end_idx = min(signal_length, start_idx + window_size)
        return signal[start_idx:end_idx]

    def get_changed_elements(self, main_window, sample_name):
        """Determine which elements need reprocessing for a sample.
        Args:
            main_window (Any): The main window.
            sample_name (Any): The sample name.
        Returns:
            tuple: Result of the operation.
        """
        changed_elements = []
        new_file_elements = []

        if sample_name in main_window.needs_initial_detection:
            for element, isotopes in main_window.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    new_file_elements.append((element, isotope, element_key, 'new_file'))
            main_window.needs_initial_detection.discard(sample_name)
            return new_file_elements, []

        for element, isotopes in main_window.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                current_hash = main_window.get_parameter_hash(sample_name, element_key)
                stored_hash = main_window.element_parameter_hashes.get(sample_name, {}).get(element_key)

                if (stored_hash != current_hash or
                        main_window.detection_states.get(sample_name, {}).get(element_key) == 'changed'):
                    changed_elements.append((element, isotope, element_key, 'changed'))

                    if sample_name not in main_window.element_parameter_hashes:
                        main_window.element_parameter_hashes[sample_name] = {}
                    main_window.element_parameter_hashes[sample_name][element_key] = current_hash

                    if sample_name in main_window.detection_states:
                        main_window.detection_states[sample_name].pop(element_key, None)

        return changed_elements, []

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------multi-element particle processing-------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def process_multi_element_particles(self, all_particles, time_array, sample_detected_peaks,
                                        selected_isotopes, get_formatted_label_func,
                                        current_sample, element_thresholds, parameters_table,
                                        min_overlap_percentage=50.0):
        """Process and identify multi-element particles.
        Args:
            all_particles (Any): The all particles.
            time_array (Any): The time array.
            sample_detected_peaks (Any): The sample detected peaks.
            selected_isotopes (Any): The selected isotopes.
            get_formatted_label_func (Any): The get formatted label func.
            current_sample (Any): The current sample.
            element_thresholds (Any): The element thresholds.
            parameters_table (Any): The parameters table.
            min_overlap_percentage (Any): The min overlap percentage.
        Returns:
            object: Result of the operation.
        """
        multi_element_particles = []

        included_elements = {}
        for row in range(parameters_table.rowCount()):
            include_checkbox = parameters_table.cellWidget(row, 1)
            element_item = parameters_table.item(row, 0)
            if element_item and include_checkbox and include_checkbox.isChecked():
                display_label = element_item.text()
                for element, isotopes in selected_isotopes.items():
                    for isotope in isotopes:
                        element_key = f"{element}-{isotope:.4f}"
                        if get_formatted_label_func(element_key) == display_label:
                            included_elements[(element, isotope)] = True
                            break

        detected_peaks = sample_detected_peaks.get(current_sample, {})
        all_ranges = []

        for particle_data in all_particles:
            element = particle_data['element']
            isotope = particle_data['isotope']

            if not included_elements.get((element, isotope), False):
                continue

            element_key = f"{element}-{isotope:.4f}"
            display_label = get_formatted_label_func(element_key)
            element_particles = detected_peaks.get((element, isotope), [])

            clusters_to_particles = {}
            if element_particles:
                for particle in element_particles:
                    if particle is None:
                        continue
                    particle_range = (particle['left_idx'], particle['right_idx'])
                    clusters_to_particles[particle_range] = particle

            for i, cluster in enumerate(particle_data['clusters']):
                start_time = time_array[cluster[0]]
                end_time = time_array[cluster[1]]

                particle = clusters_to_particles.get(cluster)

                if particle is None:
                    for p in element_particles:
                        if p is None:
                            continue
                        if ((p['left_idx'] <= cluster[0] <= p['right_idx']) or
                                (p['left_idx'] <= cluster[1] <= p['right_idx']) or
                                (cluster[0] <= p['left_idx'] and cluster[1] >= p['right_idx'])):
                            particle = p
                            break

                if particle is not None and 'total_counts' in particle:
                    counts = particle['total_counts']
                else:
                    signal = particle_data['signal']
                    background = 0
                    if current_sample in element_thresholds:
                        thresholds = element_thresholds[current_sample]
                        if element_key in thresholds:
                            background = thresholds[element_key].get('background', 0)
                    counts = np.sum(signal[cluster[0]:cluster[1] + 1] - background)
                    if counts < 0:
                        counts = 0

                all_ranges.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'display_label': display_label,
                    'counts': counts,
                })

        all_ranges.sort(key=lambda x: x['start_time'])

        for range_data in all_ranges:
            if not multi_element_particles or not self.is_overlapping(range_data, multi_element_particles[-1]):
                multi_element_particles.append({
                    'start_time': range_data['start_time'],
                    'end_time': range_data['end_time'],
                    'elements': {range_data['display_label']: range_data['counts']},
                })
            else:
                current_particle = multi_element_particles[-1]
                current_particle['end_time'] = max(current_particle['end_time'], range_data['end_time'])
                current_particle['start_time'] = min(current_particle['start_time'], range_data['start_time'])
                if range_data['display_label'] in current_particle['elements']:
                    current_particle['elements'][range_data['display_label']] += range_data['counts']
                else:
                    current_particle['elements'][range_data['display_label']] = range_data['counts']

        return multi_element_particles

    def is_overlapping(self, particle, multi_particle):
        """Check if particles overlap by at least 50 percent.
        Args:
            particle (Any): The particle.
            multi_particle (Any): The multi particle.
        Returns:
            object: Result of the operation.
        """
        start1, end1 = particle['start_time'], particle['end_time']
        start2, end2 = multi_particle['start_time'], multi_particle['end_time']

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)

        if overlap_start >= overlap_end:
            return False

        overlap_duration = overlap_end - overlap_start
        duration1 = end1 - start1
        duration2 = end2 - start2

        if duration1 <= 0 or duration2 <= 0:
            return False

        overlap_percent1 = (overlap_duration / duration1) * 100
        overlap_percent2 = (overlap_duration / duration2) * 100
        return max(overlap_percent1, overlap_percent2) >= 50.0

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------main detection-------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def detect_particles(self, main_window):
        """Main threading-safe particle detection function.
        Args:
            main_window (Any): The main window.
        """
        original_sample = main_window.current_sample
        overlay = None

        try:
            overlay = QWidget(main_window)
            overlay.setGeometry(main_window.rect())
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")

            message_text = (
                "iterative particle detection in progress...\n"
                "Using: Iterative Background Calculation, Numba JIT (safe), "
                "Vectorization, Batch Processing, Caching"
            )
            message_label = QLabel(message_text, overlay)
            message_label.setStyleSheet(
                "color: white; background-color: rgba(0, 0, 0, 0); "
                "font-size: 16px; font-weight: bold;"
            )
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setGeometry(overlay.rect())
            overlay.show()
            QApplication.processEvents()

            main_window.progress_bar.setVisible(True)
            main_window.progress_bar.setValue(0)
            main_window.status_label.setText("Initializing iterative detection...")
            QApplication.processEvents()

            for sample_name in main_window.data_by_sample.keys():
                main_window.load_or_initialize_parameters(sample_name)

            max_workers = max(1, multiprocessing.cpu_count() - 1)
            total_samples = len(main_window.data_by_sample)
            completed_samples = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_sample = {
                    executor.submit(self.process_single_sample_safe, main_window, sample_name): sample_name
                    for sample_name in main_window.data_by_sample.keys()
                }

                for future in concurrent.futures.as_completed(future_to_sample):
                    sample_name = future_to_sample[future]
                    try:
                        result = future.result()
                        if result:
                            temp_multi_element_particles = self.process_multi_element_particles(
                                result['all_particles'],
                                main_window.time_array_by_sample[sample_name],
                                {sample_name: result['detected_peaks']},
                                main_window.selected_isotopes,
                                main_window.get_formatted_label,
                                sample_name,
                                {sample_name: result['thresholds']},
                                main_window.parameters_table,
                            )

                            main_window.sample_detected_peaks[sample_name] = result['detected_peaks']
                            main_window.sample_results_data[sample_name] = result['results_data']
                            main_window.sample_particle_data[sample_name] = temp_multi_element_particles.copy()
                            main_window.element_thresholds[sample_name] = result['thresholds']

                            if sample_name == main_window.current_sample:
                                detected_peaks = result['detected_peaks']
                                if detected_peaks:
                                    last_element = list(detected_peaks.keys())[-1]
                                    main_window.update_results_table(
                                        detected_peaks[last_element],
                                        main_window.data_by_sample[sample_name][
                                            main_window.find_closest_isotope(last_element[1])],
                                        last_element[0],
                                        last_element[1],
                                    )

                                for row in range(main_window.parameters_table.rowCount()):
                                    display_label = main_window.parameters_table.item(row, 0).text()
                                    for element, isotopes in main_window.selected_isotopes.items():
                                        for isotope in isotopes:
                                            if (element, isotope) in detected_peaks:
                                                status_item = main_window.parameters_table.item(row, 9)
                                                if status_item:
                                                    status_item.setText(
                                                        f"Found {len(detected_peaks[(element, isotope)])} peaks"
                                                    )

                                main_window.update_multi_element_table()

                            completed_samples += 1
                            progress = int((completed_samples / total_samples) * 100)
                            main_window.progress_bar.setValue(progress)
                            main_window.status_label.setText(
                                f"Processing... ({completed_samples}/{total_samples})"
                            )
                            QApplication.processEvents()

                    except Exception as e:
                        print(f"Error processing {sample_name}: {str(e)}")

            if original_sample in main_window.data_by_sample:
                main_window.current_sample = original_sample
                main_window.data = main_window.data_by_sample[original_sample]
                main_window.time_array = main_window.time_array_by_sample[original_sample]
                main_window.detected_peaks = main_window.sample_detected_peaks.get(original_sample, {})

                if original_sample in main_window.sample_detected_peaks:
                    for row in range(main_window.parameters_table.rowCount()):
                        display_label = main_window.parameters_table.item(row, 0).text()
                        for element, isotopes in main_window.selected_isotopes.items():
                            for isotope in isotopes:
                                element_key = f"{element}-{isotope:.4f}"
                                if main_window.get_formatted_label(element_key) == display_label:
                                    if (element, isotope) in main_window.sample_detected_peaks[original_sample]:
                                        detected_particles = main_window.sample_detected_peaks[original_sample][
                                            (element, isotope)]
                                        status_item = main_window.parameters_table.item(row, 9)
                                        if status_item:
                                            status_item.setText(f"Found {len(detected_particles)} peaks")

            main_window.progress_bar.setVisible(False)
            main_window.status_label.setText("Iterative peak detection completed successfully!")
            main_window.update_calibration_display()

            if hasattr(main_window, 'color_parameters_table_rows'):
                main_window.color_parameters_table_rows()

            if hasattr(main_window, 'calculate_mass_limits'):
                main_window.calculate_mass_limits()

        except Exception as e:
            print(f"Error in detect_particles: {str(e)}")
            main_window.status_label.setText("Error during iterative peak detection")
            main_window.progress_bar.setVisible(False)
        finally:
            if overlay:
                overlay.hide()
                overlay.deleteLater()

        main_window.unsaved_changes = True

    # ----------------------------------------------------------------------------------------------------------
    # ------------------------------------visual---------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------

    def get_snr_color(self, snr):
        """Get color based on signal-to-noise ratio.
        Args:
            snr (Any): The snr.
        Returns:
            object: Result of the operation.
        """
        if snr <= 1.1:
            return QColor(231, 76, 60)
        elif snr <= 1.2:
            return QColor(243, 156, 18)
        elif snr <= 1.5:
            return QColor(241, 196, 15)
        else:
            return QColor(46, 204, 113)