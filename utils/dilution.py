"""Dilution and particle-concentration calculations (non-visual).

Pure logic operating on a window-like object that exposes the relevant
sample data. The dilution editor dialog and prompt UI live in
``tools/dilution_utils.py``; this module has no Qt-widget dependencies so it
can be unit-tested without a GUI.
"""
import re
import logging
_itk_log = logging.getLogger("IsotopeTrack.utils.dilution")


def normalize_factor(value, minimum=1.0):
    """
    Coerce a value into a valid dilution factor.

    Args:
        value (Any): Raw value to normalize.
        minimum (float): Lower bound enforced on the result.

    Returns:
        float: A float not below minimum, defaulting to minimum on failure.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        _itk_log.exception("Handled exception in normalize_factor")
        return minimum
    return result if result >= minimum else minimum


def get_sample_dilution(window, sample_name):
    """
    Return the dilution factor stored for a sample on a window.

    Args:
        window (Any): Owning window holding a sample_dilutions mapping.
        sample_name (str): Sample identifier.

    Returns:
        float: Stored dilution factor, defaulting to 1.0 when unset.
    """
    store = getattr(window, 'sample_dilutions', None)
    if not isinstance(store, dict):
        return 1.0
    return normalize_factor(store.get(sample_name, 1.0))


def set_sample_dilution(window, sample_name, factor):
    """Store a dilution factor for a sample on a window.

    Args:
        window (Any): Owning window holding a sample_dilutions mapping.
        sample_name (str): Sample identifier.
        factor (float): Dilution factor to store, clamped to a minimum of 1.0.
    """
    if not isinstance(getattr(window, 'sample_dilutions', None), dict):
        window.sample_dilutions = {}
    window.sample_dilutions[sample_name] = normalize_factor(factor)


def detect_dilution_from_name(name):
    """
    Detect a dilution factor encoded in a sample or file name.

    Recognizes a number followed by the letter x as a separate token, such as
    sample_50x or run-2.5x, ignoring case and any known file extension. When
    several such tokens are present the last one is used, since the dilution is
    conventionally written at the end of the name.

    Args:
        name (str): Sample name or file name to inspect.

    Returns:
        float: Detected dilution factor, or None when no pattern matches.
    """
    if not name:
        return None
    stem = re.sub(r'\.(csv|tsv|xlsx|xls|h5|txt)$', '', str(name), flags=re.IGNORECASE)
    matches = re.findall(r'(?:^|[\s_\-])(\d+(?:\.\d+)?)[xX](?=$|[\s_\-])', stem)
    if not matches:
        return None
    try:
        value = float(matches[-1])
    except ValueError:
        _itk_log.exception("Handled exception in detect_dilution_from_name")
        return None
    return value if value >= 1.0 else None


def detect_dilution_for_sample(window, sample_name):
    """
    Detect a dilution factor for a sample, preferring its source file name.

    The original file or folder path recorded for the sample is inspected
    first, since sample display names are often cleaned of the encoded factor.
    The sample name itself is used as a fallback.

    Args:
        window (Any): Owning window exposing sample_to_folder_map.
        sample_name (str): Sample identifier.

    Returns:
        float: Detected dilution factor, or None when no pattern matches.
    """
    source = None
    folder_map = getattr(window, 'sample_to_folder_map', None)
    if isinstance(folder_map, dict):
        source = folder_map.get(sample_name)
    if source:
        try:
            from pathlib import Path
            stem = Path(str(source)).name
        except Exception:
            _itk_log.exception("Handled exception in detect_dilution_for_sample")
            stem = str(source)
        detected = detect_dilution_from_name(stem)
        if detected is not None:
            return detected
    return detect_dilution_from_name(sample_name)


def has_transport_rate(window):
    """Report whether a window has a usable transport rate calibration.

    Returns:
        bool: True when an average transport rate greater than zero exists.
    """
    rate = getattr(window, 'average_transport_rate', 0)
    return bool(rate and rate > 0)


def effective_acquisition_time(window, sample_name, element_key=None):
    """
    Return the analyzed acquisition time in seconds for a sample.

    Excluded time regions visible for the sample are subtracted from the full
    acquisition span. Sample scope exclusions always apply; element scope
    exclusions apply only when element_key matches the stored region. When the
    detector non-linearity filter is enabled, its flagged time windows are
    also subtracted; any portion of a window already inside a manual
    exclusion region is not subtracted twice.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Optional element key for element scope exclusions.

    Returns:
        float: Effective acquisition time in seconds, never negative.
    """
    time_array = None
    by_sample = getattr(window, 'time_array_by_sample', {})
    if sample_name in by_sample:
        time_array = by_sample.get(sample_name)
    elif sample_name == getattr(window, 'current_sample', None):
        time_array = getattr(window, 'time_array', None)
    if time_array is None or len(time_array) < 2:
        return 0.0
    t_min = float(time_array[0])
    t_max = float(time_array[-1])
    total_time = t_max - t_min
    exclusion_bounds = []
    if hasattr(window, '_visible_exclusion_entries_for'):
        for entry in window._visible_exclusion_entries_for(sample_name, element_key):
            bounds = entry.get('bounds')
            if not bounds:
                continue
            x0 = max(float(bounds[0]), t_min)
            x1 = min(float(bounds[1]), t_max)
            if x1 > x0:
                total_time -= (x1 - x0)
                exclusion_bounds.append((x0, x1))
    if getattr(window, 'saturation_filter_enabled', False):
        for w0, w1 in getattr(window, 'saturation_windows', {}).get(sample_name, []):
            w0 = max(float(w0), t_min)
            w1 = min(float(w1), t_max)
            if w1 <= w0:
                continue
            overlap = 0.0
            for x0, x1 in exclusion_bounds:
                overlap += max(0.0, min(w1, x1) - max(w0, x0))
            total_time -= max(0.0, (w1 - w0) - overlap)
    return max(total_time, 0.0)


def effective_volume_ml(window, sample_name, element_key=None):
    """
    Return the analyzed sample volume in millilitres for a sample.

    Volume is the average transport rate in microlitres per second multiplied
    by the effective acquisition time, converted to millilitres.

    Args:
        window (Any): Owning window exposing the transport rate.
        sample_name (str): Sample identifier.
        element_key (str): Optional element key for element scope exclusions.

    Returns:
        float: Effective analyzed volume in millilitres, 0.0 when no transport
            rate calibration is available.
    """
    rate = getattr(window, 'average_transport_rate', 0)
    if not rate or rate <= 0:
        return 0.0
    seconds = effective_acquisition_time(window, sample_name, element_key)
    return (rate * seconds) / 1000.0


def particles_per_ml(window, sample_name, particle_count, element_key=None,
                     apply_dilution=True):
    """
    Return the particle number concentration in particles per millilitre.

    Args:
        window (Any): Owning window exposing volume and dilution helpers.
        sample_name (str): Sample identifier.
        particle_count (int): Number of particles for the quantity of interest.
        element_key (str): Optional element key for element scope exclusions.
        apply_dilution (bool): Multiply by the sample dilution factor when True.

    Returns:
        float: Concentration in particles per millilitre, 0.0 when the analyzed
            volume is unavailable.
    """
    volume_ml = effective_volume_ml(window, sample_name, element_key)
    if volume_ml <= 0 or not particle_count:
        return 0.0
    value = particle_count / volume_ml
    if apply_dilution:
        value *= get_sample_dilution(window, sample_name)
    return value
