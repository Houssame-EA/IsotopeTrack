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

os.environ['NUMBA_THREADING_LAYER'] = 'safe'

try:
    from numba import jit, config
    config.THREADING_LAYER = 'safe'
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("numba not available - install with 'pip install numba'")
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def prange(x):
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


    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------mathematical utility--------------------------------------------
    #----------------------------------------------------------------------------------------------------------  
              
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
        sigma2_x = np.log((np.exp(sigma**2) - 1.0) / n + 1.0)
        mu_x = np.log(n) + mu + 0.5 * (sigma**2 - sigma2_x)
        return mu_x, np.sqrt(sigma2_x)
    else:
        exp_term = np.exp(mu + 0.5 * sigma**2)
        Sp = n * exp_term
        sigma2_s = n * sigma**2 * exp_term**2 / Sp**2
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
    mus, sigmas = sum_iid_lognormals(k, np.log(1.0) - 0.5 * sigma**2, sigma)
    upper_q = lognormal_quantile(np.array([q0]), mus[-1], sigmas[-1])[0]
    xs = np.linspace(lam, upper_q, 10000)
    cdf = np.sum([w * lognormal_cdf(xs, m, s) for w, m, s in zip(weights, mus, sigmas)], axis=0)
    
    return xs[np.argmax(cdf > q0)]

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------compound poisson lognormal class--------------------------------------------
    #----------------------------------------------------------------------------------------------------------  
              
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
            mu = np.log(1.0) - 0.5 * sigma**2 
            
            threshold = compound_poisson_lognormal_quantile_approximation(
                quantile, lambda_bkgd, mu, sigma
            )
            
            return float(threshold)
            
        except Exception as e:
            print(f"Lognormal approximation error: {e}, using simple approximation")
            return lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------peak detection class--------------------------------------------
    #----------------------------------------------------------------------------------------------------------  
              
class PeakDetection:
    """
    Enhanced peak detection with iterative background calculation.
    
    Features:
    - Iterative threshold calculation
    - Vectorized NumPy operations
    - Batch threshold processing
    - Memory optimization and caching
    - Safe parallel processing
    - Analytical log-normal compound Poisson for ToF data
    - Custom window size support
    """
    
    def __init__(self):
        """
        Initialize PeakDetection instance.
        
        Args:
            self: PeakDetection instance
            
        Returns:
            None
        """
        self._cache_hits = 0
        self._cache_misses = 0
        self.iter_eps = 1e-3  
        self.default_max_iters = 4  
        self.compound_poisson_lognormal = CompoundPoissonLognormal()
        self.incremental_enabled = True
        
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------performance--------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 
    def optimize_data_types(self, signal):
        """
        Optimize signal data types to reduce memory usage.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Signal array
            
        Returns:
            ndarray: Optimized signal array
        """
        if signal.dtype == np.float64:
            if np.all(np.abs(signal) < 1e6):
                return signal.astype(np.float32)
        return signal

    def prepare_signals_for_processing(self, signals_dict):
        """
        Prepare all signals for processing by optimizing data types.
        
        Args:
            self: PeakDetection instance
            signals_dict (dict): Dictionary of signals
            
        Returns:
            dict: Dictionary of optimized signals
        """
        optimized_signals = {}
        for key, signal in signals_dict.items():
            optimized_signals[key] = self.optimize_data_types(signal)
        return optimized_signals
    
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------numba optimized--------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 
    
    @staticmethod
    @jit(nopython=True, nogil=True)
    def _find_particles_numba(raw_signal, threshold, lambda_bkgd, min_continuous_points):
        """
        JIT-compiled particle detection without parallel processing.
        
        Args:
            raw_signal (ndarray): Raw signal data
            threshold (float): Detection threshold
            lambda_bkgd (float): Background level
            min_continuous_points (int): Minimum continuous points required
            
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
                    peak_idx = start_idx
                    for j in range(start_idx, end_idx + 1):
                        if raw_signal[j] > max_height:
                            max_height = raw_signal[j]
                            peak_idx = j
                        total_counts += raw_signal[j] - lambda_bkgd
                    
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
    def _smooth_signal_numba(signal, window_size):
        """
        JIT-compiled signal smoothing.
        
        Args:
            signal (ndarray): Signal to smooth
            window_size (int): Window size for smoothing
            
        Returns:
            ndarray: Smoothed signal
        """
        n = len(signal)
        smoothed = np.zeros(n)
        half_window = window_size // 2
        
        for i in range(n): 
            start = max(0, i - half_window)
            end = min(n, i + half_window + 1)
            total = 0.0
            count = 0
            for j in range(start, end):
                total += signal[j]
                count += 1
            smoothed[i] = total / count
        
        return smoothed

    @staticmethod
    @jit(nopython=True, nogil=True)
    def _calculate_currie_numba(lambda_bkgd, z_a):
        """
        JIT-compiled Currie threshold calculation.
        
        Args:
            lambda_bkgd (float): Background level
            z_a (float): Z-score for alpha level
            
        Returns:
            float: Currie threshold
        """
        if lambda_bkgd <= 0:
            return 0.0
        epsilon = 0.5 if lambda_bkgd < 10 else 0.0
        eta = 2.0
        threshold_1 = z_a * np.sqrt((lambda_bkgd + epsilon) * eta)
        return lambda_bkgd + threshold_1
    
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------signl smoothing--------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 
    
    def smooth_signal(self, signal, window_length=3, iterations=1):
        """
        Threading-safe signal smoothing.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Signal to smooth
            window_length (int): Smoothing window length
            iterations (int): Number of smoothing iterations
            
        Returns:
            ndarray: Smoothed signal
        """
        signal = self.optimize_data_types(signal)
        window_length = int(window_length)
        
        if window_length % 2 == 0:
            window_length += 1
        
        if NUMBA_AVAILABLE and len(signal) > 1000:
            smoothed = signal.astype(np.float64)
            for _ in range(iterations):
                smoothed = self._smooth_signal_numba(smoothed, window_length)
            return smoothed.astype(signal.dtype)
            
        elif SCIPY_AVAILABLE:
            smoothed = signal.astype(np.float64)
            for _ in range(iterations):
                smoothed = uniform_filter1d(smoothed, size=window_length, mode='nearest')
            return smoothed.astype(signal.dtype)
            
        else:
            return self.smooth_signal_fallback(signal, window_length, iterations)
    
    def smooth_signal_fallback(self, signal, window_length=3, iterations=1):
        """
        Fallback smoothing method when Numba and SciPy unavailable.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Signal to smooth
            window_length (int): Window length
            iterations (int): Number of iterations
            
        Returns:
            ndarray: Smoothed signal
        """
        smoothed = signal.copy()
        
        for _ in range(iterations):
            padded = np.pad(smoothed, (window_length//2, window_length//2), mode='edge')
            window = np.ones(window_length) / window_length
            smoothed = np.convolve(padded, window, mode='valid')
        
        return smoothed
    
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------calculation--------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 
    
    def calculate_iterative_threshold(self, signal, method, alpha=0.000001, max_iters=4, 
                                manual_threshold=10.0, element_key=None, sigma=0.47,
                                use_window_size=False, window_size=5000):
        """
        Calculate threshold using iterative background refinement.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Signal data
            method (str): Detection method
            alpha (float): Significance level
            max_iters (int): Maximum iterations
            manual_threshold (float): Manual threshold value
            element_key (str): Element identifier
            sigma (float): Sigma parameter for compound Poisson
            use_window_size (bool): Whether to apply window size
            window_size (int): Window size for background calculation
            
        Returns:
            dict: Threshold data including background and convergence info
        """
        working_signal = self.apply_window_size(signal, use_window_size, window_size)
        overall_mean_signal = np.mean(working_signal)
        
        if method == "Manual":
            manual_thresh = manual_threshold
            
            below_threshold_data = working_signal[working_signal < manual_thresh]
            if len(below_threshold_data) > 0:
                lambda_bkgd = np.mean(below_threshold_data)
            else:
                lambda_bkgd = overall_mean_signal
                
            return {
                'threshold': manual_thresh,
                'background': lambda_bkgd,
                'LOD_counts': manual_thresh,
                'LOD_MDL': max(0, manual_thresh - lambda_bkgd),
                'iterations': 1,
                'convergence': 'manual_threshold_with_background_correction',
                'method_used': 'Manual',
                'window_applied': use_window_size,
                'window_size_used': window_size if use_window_size else None,
                'overall_mean': overall_mean_signal
            }

        if max_iters == 0:
            threshold = self._calculate_single_threshold(overall_mean_signal, method, alpha, sigma)
            iterations_performed = 0
            convergence_status = 'no_iteration_for_threshold'
        else:
            threshold = np.inf
            prev_threshold = np.inf
            iters = 0
            iter_eps = 1e-3
            
            while (np.abs(prev_threshold - threshold) > iter_eps and iters < max_iters) or iters == 0:
                prev_threshold = threshold
                
                if threshold == np.inf:
                    lambda_for_threshold = overall_mean_signal
                else:
                    below_threshold_data = working_signal[working_signal < threshold]
                    if len(below_threshold_data) > 0:
                        lambda_for_threshold = np.mean(below_threshold_data)
                    else:
                        lambda_for_threshold = overall_mean_signal
                
                threshold = self._calculate_single_threshold(lambda_for_threshold, method, alpha, sigma)
                iters += 1

                if threshold <= 0:
                    threshold = lambda_for_threshold + 3.0 * np.sqrt(max(lambda_for_threshold, 1))
                    break
            
            iterations_performed = iters
            convergence_status = f'converged_after_{iters}_iterations' if iters < max_iters else f'max_iters_reached_{max_iters}'

        below_threshold_data = working_signal[working_signal < threshold]
        if len(below_threshold_data) > 0:
            lambda_bkgd = np.mean(below_threshold_data)
            background_status = 'background_calculated_excluding_peaks'
        else:
            lambda_bkgd = overall_mean_signal
            background_status = 'background_fallback_to_mean'
        
        return {
            'threshold': threshold,
            'background': lambda_bkgd,
            'LOD_counts': threshold,
            'LOD_MDL': max(0, threshold - lambda_bkgd),
            'iterations': iterations_performed,
            'convergence': f'{convergence_status}_with_{background_status}',
            'method_used': method,
            'window_applied': use_window_size,
            'window_size_used': window_size if use_window_size else None,
            'overall_mean': overall_mean_signal
        }
        
    def _calculate_single_threshold(self, lambda_bkgd, method, alpha, sigma=0.47):
        """
        Calculate threshold for single iteration.
        
        Args:
            self: PeakDetection instance
            lambda_bkgd (float): Background level
            method (str): Detection method
            alpha (float): Significance level
            sigma (float): Sigma parameter
            
        Returns:
            float: Calculated threshold
        """
        if method == "Currie":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            return self._calculate_currie_fast(lambda_bkgd, z_a)
        elif method == "Formula_C":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            return self._calculate_formula_c_fast(lambda_bkgd, z_a)
        elif method == "Compound Poisson LogNormal":
            return self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma)
        else:
            return lambda_bkgd + 3.0 * np.sqrt(lambda_bkgd)
    
    @lru_cache(maxsize=10000)
    def _cached_threshold_calculation(self, lambda_bkgd, method, alpha, isotope_key):
        """
        Cached threshold calculation for performance.
        
        Args:
            self: PeakDetection instance
            lambda_bkgd (float): Background level
            method (str): Detection method
            alpha (float): Significance level
            isotope_key (str): Isotope identifier for caching
            
        Returns:
            float: Calculated threshold
        """
        if method == "Currie":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            if NUMBA_AVAILABLE:
                return self._calculate_currie_numba(lambda_bkgd, z_a)
            else:
                return self._calculate_currie_fast(lambda_bkgd, z_a)
        elif method == "Formula_C":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            return self._calculate_formula_c_fast(lambda_bkgd, z_a)
        elif method == "Compound Poisson LogNormal":
            return self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma=0.47)

    def calculate_thresholds_batch_safe(self, signals_dict, params_dict, method_groups=None, isotope_mapping=None):
        """
        Safe batch threshold calculation with iterative refinement and window size support.
        
        Args:
            self: PeakDetection instance
            signals_dict (dict): Dictionary of signal arrays
            params_dict (dict): Dictionary of parameter sets
            method_groups (dict, optional): Grouped methods
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
                    
                    isotope_key = isotope_mapping.get(element_key, element_key) if isotope_mapping else element_key
                    
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
                            window_size=window_size
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
                            'window_size_used': window_size if use_window_size else None
                        }
        
        return all_threshold_data

    def _calculate_currie_fast(self, lambda_bkgd, z_a):
        """
        Fast Currie threshold calculation.
        
        Args:
            self: PeakDetection instance
            lambda_bkgd (float): Background level
            z_a (float): Z-score
            
        Returns:
            float: Currie threshold
        """
        if lambda_bkgd <= 0:
            return 0
        epsilon = 0.5 if lambda_bkgd < 10 else 0.0
        eta = 2.0
        threshold_1 = z_a * np.sqrt((lambda_bkgd + epsilon) * eta)
        return lambda_bkgd + threshold_1

    def _calculate_formula_c_fast(self, lambda_bkgd, z_a):
        """
        Fast Formula C threshold calculation.
        
        Args:
            self: PeakDetection instance
            lambda_bkgd (float): Background level
            z_a (float): Z-score
            
        Returns:
            float: Formula C threshold
        """
        if lambda_bkgd <= 0:
            return 0
        tr = 1.0
        threshold_1 = z_a**2 / 2.0 * tr + z_a * np.sqrt(
            z_a**2 / 4.0 * tr * tr + lambda_bkgd * tr * (1.0 + tr)
        )
        return lambda_bkgd + threshold_1
    
    def calculate_thresholds_batch(self, signals_dict, params_dict, method_groups=None):
        """
        Wrapper for safe batch threshold processing.
        
        Args:
            self: PeakDetection instance
            signals_dict (dict): Dictionary of signals
            params_dict (dict): Dictionary of parameters
            method_groups (dict, optional): Grouped methods
            
        Returns:
            dict: Threshold data for all elements
        """
        return self.calculate_thresholds_batch_safe(signals_dict, params_dict, method_groups)

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------core--------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 

    def find_particles_safe(self, time, smoothed_signal, raw_signal, lambda_bkgd, threshold, 
                          min_width=3, min_continuous_points=1, apply_smoothing=False, 
                          integration_method="Background"):
        """
        Threading-safe particle detection.
        
        Args:
            self: PeakDetection instance
            time (ndarray): Time array
            smoothed_signal (ndarray): Smoothed signal
            raw_signal (ndarray): Raw signal
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            min_width (int): Minimum particle width
            min_continuous_points (int): Minimum continuous points
            apply_smoothing (bool): Whether smoothing was applied
            integration_method (str): Integration method name
            
        Returns:
            list: List of detected particle dictionaries
        """
        raw_signal = self.optimize_data_types(raw_signal)
        smoothed_signal = self.optimize_data_types(smoothed_signal)
        
        if NUMBA_AVAILABLE and len(raw_signal) > 500:
            
            raw_signal_f64 = raw_signal.astype(np.float64)
            
            starts, ends, heights, counts = self._find_particles_numba(
                raw_signal_f64, float(threshold), float(lambda_bkgd), min_continuous_points
            )
            
            particles = []
            for i in range(len(starts)):
                start_idx, end_idx = starts[i], ends[i]
                height = heights[i]
                total_counts = counts[i]
                
                peak_local_idx = np.argmax(raw_signal[start_idx:end_idx+1])
                peak_global_idx = start_idx + peak_local_idx
                
                snr = height / threshold if threshold > 0 else 0
                particles.append({
                    'peak_time': time[peak_global_idx],
                    'max_height': height,
                    'total_counts': total_counts,
                    'SNR': snr,
                    'left_idx': start_idx,
                    'right_idx': end_idx,
                    'peak_valid': snr >= 3
                })
            return particles
        else:
            return self.find_particles_vectorized(time, smoothed_signal, raw_signal, 
                                                lambda_bkgd, threshold, min_width, 
                                                min_continuous_points, apply_smoothing, 
                                                integration_method)
    
    def find_particles_vectorized(self, time, smoothed_signal, raw_signal, lambda_bkgd, threshold, 
                                min_width=3, min_continuous_points=1, apply_smoothing=False, 
                                integration_method="Background"):
        """
        Vectorized particle detection using NumPy.
        
        Args:
            self: PeakDetection instance
            time (ndarray): Time array
            smoothed_signal (ndarray): Smoothed signal
            raw_signal (ndarray): Raw signal
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            min_width (int): Minimum particle width
            min_continuous_points (int): Minimum continuous points
            apply_smoothing (bool): Whether smoothing was applied
            integration_method (str): Integration method
            
        Returns:
            list: List of detected particle dictionaries
        """
        detection_signal = smoothed_signal if apply_smoothing else raw_signal
        boundary_level = lambda_bkgd
        
        above_boundary = detection_signal > boundary_level
        padded_above = np.concatenate(([False], above_boundary, [False]))
        boundary_changes = np.diff(padded_above.astype(int))
        
        region_starts = np.where(boundary_changes == 1)[0]
        region_ends = np.where(boundary_changes == -1)[0]
        
        if len(region_starts) == 0 or len(region_ends) == 0:
            return []
        
        min_len = min(len(region_starts), len(region_ends))
        region_starts = region_starts[:min_len]
        region_ends = region_ends[:min_len]
        
        particles = []
        
        for start_idx, end_idx in zip(region_starts, region_ends):
            end_idx = min(end_idx, len(raw_signal) - 1)
            
            if end_idx <= start_idx:
                continue
                
            raw_region = raw_signal[start_idx:end_idx + 1]
            region_above_threshold = raw_region > threshold
            
            if min_continuous_points > 1:
                consecutive_kernel = np.ones(min_continuous_points)
                consecutive_check = np.convolve(region_above_threshold.astype(int), 
                                            consecutive_kernel, mode='valid')
                max_consecutive = np.max(consecutive_check) if len(consecutive_check) > 0 else 0
                
                if max_consecutive < min_continuous_points:
                    continue
            elif not np.any(region_above_threshold):
                continue
            
            total_counts = np.sum(raw_region - lambda_bkgd)
            
            if total_counts <= 0:
                continue
                
            peak_local_idx = np.argmax(raw_region)
            peak_global_idx = start_idx + peak_local_idx
            max_height = raw_region[peak_local_idx]
            
            snr = max_height / threshold if threshold > 0 else 0
            
            particles.append({
                'peak_time': time[peak_global_idx],
                'max_height': max_height,
                'total_counts': total_counts,
                'SNR': snr,
                'left_idx': start_idx,
                'right_idx': end_idx,
                'peak_valid': snr >= 3
            })
        
        return particles
    
    def find_particles(self, time, smoothed_signal, raw_signal, lambda_bkgd, threshold, min_width=3, 
                      min_continuous_points=1, apply_smoothing=False, integration_method="Background"):
        """
        Wrapper for safe particle detection.
        
        Args:
            self: PeakDetection instance
            time (ndarray): Time array
            smoothed_signal (ndarray): Smoothed signal
            raw_signal (ndarray): Raw signal
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            min_width (int): Minimum width
            min_continuous_points (int): Minimum continuous points
            apply_smoothing (bool): Whether smoothing applied
            integration_method (str): Integration method
            
        Returns:
            list: List of detected particles
        """
        return self.find_particles_safe(time, smoothed_signal, raw_signal, lambda_bkgd, 
                                       threshold, min_width, min_continuous_points, 
                                       apply_smoothing, integration_method)

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------processing--------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def process_single_sample_safe(self, main_window, sample_name):
        """
        Threading-safe sample processing with iterative calculation.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            dict or None: Processing results or None on error
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
                
                try:
                    if params['apply_smoothing']:
                        smoothed_signal = self.smooth_signal(
                            signal,
                            window_length=int(params['smooth_window']),
                            iterations=int(params['iterations'])
                        )
                    else:
                        smoothed_signal = signal

                    detected_particles = self.find_particles_safe(
                        local_time, smoothed_signal, signal,
                        threshold_data['background'], threshold_data['threshold'],
                        min_continuous_points=int(params['min_continuous']),
                        apply_smoothing=params['apply_smoothing']
                    )
                    
                    detected_peaks_for_sample[(element, isotope)] = detected_particles
                    local_thresholds[element_key] = threshold_data
                    
                    display_label = main_window.get_formatted_label(element_key)
                    if detected_particles:
                        all_particles.append({
                            'element': element,
                            'isotope': isotope,
                            'signal': signal,
                            'clusters': [(p['left_idx'], p['right_idx']) for p in detected_particles]
                        })
                        
                        for particle in detected_particles:
                            if particle is None:
                                continue
                            row_data = [
                                display_label,
                                f"{local_time[particle['left_idx']]:.4f}",
                                f"{local_time[particle['right_idx']]:.4f}",
                                f"{particle['total_counts']:.0f}",
                                f"{particle['max_height']:.0f}",
                                f"{particle['SNR']:.2f}"
                            ]
                            results_data.append(row_data)
                    
                except Exception as e:
                    print(f"Error processing {element}-{isotope}: {str(e)}")
                    continue
            
            return {
                'sample_name': sample_name,
                'detected_peaks': detected_peaks_for_sample,
                'results_data': results_data,
                'all_particles': all_particles,
                'thresholds': local_thresholds
            }
                
        except Exception as e:
            print(f"Error processing sample {sample_name}: {str(e)}")
            return None

    def process_single_sample(self, main_window, sample_name):
        """
        Wrapper for safe sample processing.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            dict or None: Processing results
        """
        return self.process_single_sample_safe(main_window, sample_name)
    
    def detect_peaks_with_poisson(self, signal, window_length=3, iterations=1, alpha=0.000001, 
                apply_smoothing=False, sample_name=None, element_key=None, method="Compound Poisson LogNormal",
                manual_threshold=10.0, element_thresholds=None, current_sample=None,
                use_window_size=False, window_size=5000):
        """
        Detect peaks using Poisson-based methods with iterative calculation.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Signal data
            window_length (int): Smoothing window length
            iterations (int): Smoothing iterations
            alpha (float): Significance level
            apply_smoothing (bool): Whether to apply smoothing
            sample_name (str, optional): Sample name
            element_key (str, optional): Element identifier
            method (str): Detection method
            manual_threshold (float): Manual threshold value
            element_thresholds (dict, optional): Threshold storage
            current_sample (str, optional): Current sample name
            use_window_size (bool): Whether to use window size
            window_size (int): Window size for calculation
            
        Returns:
            tuple: Smoothed signal, background, threshold, mean, threshold data
        """
        if apply_smoothing:
            smoothed_signal = self.smooth_signal(signal, window_length, iterations)
        else:
            smoothed_signal = signal.copy()
        
        try:
            threshold_data = self.calculate_iterative_threshold(
                signal=signal,
                method=method,
                alpha=alpha,
                max_iters=4, 
                manual_threshold=manual_threshold,
                element_key=element_key,
                use_window_size=use_window_size,
                window_size=window_size
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
                    'window_size_used': window_size if use_window_size else None
                }
            elif method == "Compound Poisson LogNormal":
                threshold = self.compound_poisson_lognormal.get_threshold(lambda_bkgd, alpha, sigma=0.47)
                threshold_data = {
                    'threshold': threshold,
                    'background': lambda_bkgd,
                    'LOD_counts': threshold,
                    'iterations': 1,
                    'convergence': 'lognormal_approximation',
                    'method_used': method,
                    'window_applied': use_window_size,
                    'window_size_used': window_size if use_window_size else None
                }
        
        mean_nonzero = np.mean(signal[signal > 0]) if len(signal[signal > 0]) > 0 else 0
        return smoothed_signal, lambda_bkgd, threshold, mean_nonzero, threshold_data

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------incremental detection --------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def detect_particles_incremental(self, main_window):
        """
        Incremental particle detection for changed elements only.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            
        Returns:
            None
        """
        original_sample = main_window.current_sample
        overlay = None
        
        try:
            overlay = QWidget(main_window)
            overlay.setGeometry(main_window.rect())
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
            
            message_label = QLabel("Incremental iterative peak detection in progress...", overlay)
            message_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 0); font-size: 16px; font-weight: bold;")
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
            
            main_window.status_label.setText(f"Processing {total_changed_elements} changed elements across {len(samples_to_process)} samples")
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
                        message_label.setText(f"Incremental detection: {progress}% complete\n"
                                            f"Processed {processed_elements}/{total_changed_elements} elements")
                    QApplication.processEvents()
        
            if original_sample in samples_to_process:
                self.update_current_sample_display(main_window, original_sample)
            
            main_window.progress_bar.setVisible(False)
            main_window.status_label.setText(f"Incremental detection complete! Processed {total_changed_elements} changed elements")
            
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
        """
        Process only changed elements for a sample incrementally.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            changed_elements (list): List of changed element tuples
            
        Returns:
            dict or None: Processing results or None on error
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
                    
                    try:
                        if params['apply_smoothing']:
                            smoothed_signal = self.smooth_signal(
                                signal,
                                window_length=int(params['smooth_window']),
                                iterations=int(params['iterations'])
                            )
                        else:
                            smoothed_signal = signal
                        
                        detected_particles = self.find_particles_safe(
                            local_time, smoothed_signal, signal,
                            threshold_data['background'], threshold_data['threshold'],
                            min_continuous_points=int(params['min_continuous']),
                            apply_smoothing=params['apply_smoothing']
                        )
                        
                        detected_peaks_updates[(element, isotope)] = detected_particles
                        threshold_updates[element_key] = threshold_data
            
                        display_label = main_window.get_formatted_label(element_key)
                        if detected_particles:
                            for particle in detected_particles:
                                if particle is None:
                                    continue
                                row_data = [
                                    display_label,
                                    f"{local_time[particle['left_idx']]:.4f}",
                                    f"{local_time[particle['right_idx']]:.4f}",
                                    f"{particle['total_counts']:.0f}",
                                    f"{particle['max_height']:.0f}",
                                    f"{particle['SNR']:.2f}"
                                ]
                                results_data_updates.append(row_data)
                        
                    except Exception as e:
                        print(f"Error processing {element}-{isotope}: {str(e)}")
                        continue

            for element, isotope, element_key in excluded_elements:
                detected_peaks_updates[(element, isotope)] = []
                threshold_updates[element_key] = {
                    'threshold': 0,
                    'background': 0,
                    'LOD_counts': 0,
                    'LOD_MDL': 0,
                    'iterations': 0,
                    'convergence': 'element_excluded',
                    'method_used': 'Excluded',
                    'window_applied': False,
                    'window_size_used': None
                }
            
            return {
                'sample_name': sample_name,
                'detected_peaks_updates': detected_peaks_updates,
                'results_data_updates': results_data_updates,
                'threshold_updates': threshold_updates,
                'changed_elements': [f"{e}-{i:.4f}" for e, i, _, _, _ in valid_elements] + [f"{e}-{i:.4f}" for e, i, _ in excluded_elements]
            }
            
        except Exception as e:
            print(f"Error in incremental processing for {sample_name}: {str(e)}")
            return None
    
    def merge_detection_results(self, main_window, sample_name, new_results, changed_elements):
        """
        Merge new detection results with existing results.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            new_results (dict): New detection results
            changed_elements (list): List of changed elements
            
        Returns:
            None
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
            
            filtered_results = [row for row in existing_results if row[0] not in changed_element_labels]
        
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
                            'clusters': [(p['left_idx'], p['right_idx']) for p in particles if p]
                        })
            updated_multi_element_particles = self.process_multi_element_particles(
                all_particles,
                main_window.time_array_by_sample[sample_name],
                {sample_name: main_window.sample_detected_peaks[sample_name]},
                main_window.selected_isotopes,
                main_window.get_formatted_label,
                sample_name,
                {sample_name: main_window.element_thresholds[sample_name]},
                main_window.parameters_table
            )
            
            main_window.sample_particle_data[sample_name] = updated_multi_element_particles
            
        except Exception as e:
            print(f"Error merging results for {sample_name}: {str(e)}")
            import traceback
            traceback.print_exc() 
        
    def update_current_sample_display(self, main_window, sample_name):
        """
        Update display for currently selected sample.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            None
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
        """
        Apply window size limitation to signal if enabled.
        
        Args:
            self: PeakDetection instance
            signal (ndarray): Input signal
            use_window_size (bool): Whether to apply window
            window_size (int): Size of window
            
        Returns:
            ndarray: Windowed or original signal
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
        """
        Determine which elements need reprocessing for a sample.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            tuple: Lists of changed and new elements
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
 
        current_params = main_window.sample_parameters.get(sample_name, {})
        
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
    
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------multi element particle processing--------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def process_multi_element_particles(self, all_particles, time_array, sample_detected_peaks, 
                                  selected_isotopes, get_formatted_label_func, 
                                  current_sample, element_thresholds, parameters_table,
                                  min_overlap_percentage=50.0):
        """
        Process and identify multi-element particles.
        
        Args:
            self: PeakDetection instance
            all_particles (list): List of all detected particles
            time_array (ndarray): Time array
            sample_detected_peaks (dict): Detected peaks by sample
            selected_isotopes (dict): Selected isotopes dictionary
            get_formatted_label_func (callable): Function to format labels
            current_sample (str): Current sample name
            element_thresholds (dict): Element threshold data
            parameters_table: Parameters table widget
            min_overlap_percentage (float): Minimum overlap percentage
            
        Returns:
            list: List of multi-element particle dictionaries
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
                        if (p['left_idx'] <= cluster[0] <= p['right_idx']) or \
                        (p['left_idx'] <= cluster[1] <= p['right_idx']) or \
                        (cluster[0] <= p['left_idx'] and cluster[1] >= p['right_idx']):
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
                    counts = np.sum(signal[cluster[0]:cluster[1]+1] - background)
                    if counts < 0:
                        counts = 0
                
                all_ranges.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'display_label': display_label,
                    'counts': counts
                })
        
        all_ranges.sort(key=lambda x: x['start_time'])
        
        for range_data in all_ranges:
            if not multi_element_particles or not self.is_overlapping(range_data, multi_element_particles[-1]):
                multi_element_particles.append({
                    'start_time': range_data['start_time'],
                    'end_time': range_data['end_time'],
                    'elements': {range_data['display_label']: range_data['counts']}
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
        """
        Check if particles overlap by at least 50 percent.
        
        Args:
            self: PeakDetection instance
            particle (dict): First particle
            multi_particle (dict): Second particle
            
        Returns:
            bool: True if particles overlap sufficiently
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
    
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------main detection--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
    
    def detect_particles(self, main_window):
        """
        Main threading-safe particle detection function.
        
        Args:
            self: PeakDetection instance
            main_window: MainWindow instance
            
        Returns:
            None
        """
        original_sample = main_window.current_sample
        overlay = None
        
        try:
            overlay = QWidget(main_window)
            overlay.setGeometry(main_window.rect())
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
            
            message_text = "iterative particle detection in progress...\nUsing: Iterative Background Calculation, Numba JIT (safe), Vectorization, Batch Processing, Caching"
                
            message_label = QLabel(message_text, overlay)
            message_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 0); font-size: 16px; font-weight: bold;")
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
                                main_window.parameters_table
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
                                        main_window.data_by_sample[sample_name][main_window.find_closest_isotope(last_element[1])],
                                        last_element[0],
                                        last_element[1]
                                    )
                                
                                for row in range(main_window.parameters_table.rowCount()):
                                    display_label = main_window.parameters_table.item(row, 0).text()
                                    for element, isotopes in main_window.selected_isotopes.items():
                                        for isotope in isotopes:
                                            if (element, isotope) in detected_peaks:
                                                status_item = main_window.parameters_table.item(row, 9)
                                                if status_item:
                                                    status_item.setText(f"Found {len(detected_peaks[(element, isotope)])} peaks")
                                                    
                                main_window.update_multi_element_table()
                            
                            completed_samples += 1
                            progress = int((completed_samples / total_samples) * 100)
                            main_window.progress_bar.setValue(progress)
                            main_window.status_label.setText(f"Processing... ({completed_samples}/{total_samples})")
                        
                                
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
                                        detected_particles = main_window.sample_detected_peaks[original_sample][(element, isotope)]
                                        status_item = main_window.parameters_table.item(row, 9)
                                        if status_item:
                                            status_item.setText(f"Found {len(detected_particles)} peaks")
            
            main_window.progress_bar.setVisible(False)
            main_window.status_label.setText("Iterative peak detection completed successfully!")
            
            main_window.update_calibration_display()
            
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
        
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------visual--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
    
    def get_snr_color(self, snr):
        """
        Get color based on signal-to-noise ratio.
        
        Args:
            self: PeakDetection instance
            snr (float): Signal-to-noise ratio
            
        Returns:
            QColor: Color for visualization
        """
        if snr <= 1.1:
            return QColor(231, 76, 60)     
        elif snr <= 1.2:
            return QColor(243, 156, 18)    
        elif snr <= 1.5:
            return QColor(241, 196, 15)    
        else:
            return QColor(46, 204, 113)   
        
    