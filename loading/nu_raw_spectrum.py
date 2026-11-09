"""Resolved mass spectrum rebuilt from the ``.raw`` snapshots of a Nu run.

Besides the integrated data, Nu Instruments software writes a few raw
digitizer snapshots per run (about one per second). Each snapshot is one TOF
extraction covering the full mass range, stored as sample-to-sample
differences. Their running sum is the waveform; adding all snapshots gives a
resolved spectrum where peak shape, resolution and the position of each
integration window can be checked.
"""
from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.loading.nu_raw_spectrum")

ZOOM_HALF_WIDTH = 0.5
MIN_IONS_FOR_WIDTH = 20


def _read_text(path):
    """Return the text of a plain or gzip-compressed file.

    Args:
        path (Path): File path.

    Returns:
        str: File content.
    """
    with open(path, 'rb') as fp:
        magic = fp.read(2)
    opener = gzip.open if magic == b'\x1f\x8b' else open
    with opener(path, 'rt', encoding='utf-8', errors='replace') as fp:
        return fp.read()


def _iter_records(text):
    """Yield the JSON records of a ``.raw`` file.

    Args:
        text (str): File content.

    Yields:
        dict: One snapshot record with a ``raw`` list.
    """
    decoder = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in ' \r\n\t,[]':
            i += 1
        if i >= n:
            return
        record, i = decoder.raw_decode(text, i)
        yield record


def read_nu_raw_spectrum(folder_path):
    """Sum the raw snapshots of a Nu run folder into one resolved spectrum.

    Args:
        folder_path (str | Path | None): Nu run folder.

    Returns:
        dict | None: ``{'spectrum': float32 array, 'n_snapshots': int}``, or
        None when the folder has no usable ``.raw`` data.
    """
    if not folder_path:
        return None
    folder = Path(folder_path)
    index_path = folder / 'raw.index'
    if not index_path.is_file():
        return None
    try:
        index = json.loads(index_path.read_text(encoding='utf-8', errors='replace'))
    except (OSError, ValueError):
        _itk_log.exception("Could not read %s", index_path)
        return None
    total = None
    count = 0
    for entry in index if isinstance(index, list) else []:
        raw_path = folder / f"{entry.get('FileNum')}.raw"
        if not raw_path.is_file() or raw_path.stat().st_size == 0:
            continue
        try:
            for record in _iter_records(_read_text(raw_path)):
                deltas = np.asarray(record.get('raw') or [], dtype=np.float64)
                if deltas.size == 0:
                    continue
                waveform = np.cumsum(deltas)
                if total is None:
                    total = np.zeros_like(waveform)
                if waveform.size != total.size:
                    continue
                total += waveform
                count += 1
        except (OSError, ValueError):
            _itk_log.exception("Could not read %s", raw_path)
    if total is None or count == 0:
        return None
    return {'spectrum': total.astype(np.float32), 'n_snapshots': count}


def _time_to_mass(run_info, time_ns):
    """Convert flight time to m/z with the run's mass calibration.

    Args:
        run_info (dict): Nu run.info.
        time_ns (np.ndarray | float): Flight time in ns.

    Returns:
        np.ndarray | float: m/z.
    """
    a, b = run_info['MassCalCoefficients']
    return (a + np.asarray(time_ns, dtype=np.float64) * b) ** 2


def spectrum_masses(run_info, n_points):
    """Return the m/z of every point of a raw spectrum.

    Args:
        run_info (dict): Nu run.info.
        n_points (int): Number of spectrum points.

    Returns:
        np.ndarray: m/z of each point.
    """
    rate = float(run_info.get('SampleRateGsSec') or 2.0)
    delay = float(run_info['SegmentInfo'][0]['AcquisitionTriggerDelayNs'])
    return _time_to_mass(run_info, np.arange(n_points) / rate + delay)


def integration_window(run_info, target_mass):
    """Return the integration and baseline windows closest to a mass.

    Args:
        run_info (dict): Nu run.info.
        target_mass (float): Isotope mass.

    Returns:
        dict | None: ``window``, ``baseline1``, ``baseline2`` as (start, end)
        in m/z, or None when the run defines no regions.
    """
    regions = run_info.get('IntegrationRegions') or []
    if not regions:
        return None
    best = min(regions, key=lambda r: abs(
        0.5 * (_time_to_mass(run_info, r['Start']) + _time_to_mass(run_info, r['End'])) - target_mass))
    pair = lambda s, e: (float(_time_to_mass(run_info, best[s])), float(_time_to_mass(run_info, best[e])))
    return {
        'window': pair('Start', 'End'),
        'baseline1': pair('Baseline1Start', 'Baseline1End'),
        'baseline2': pair('Baseline2Start', 'Baseline2End'),
    }


def integration_windows(run_info):
    """Return the integration window of every measured mass.

    Args:
        run_info (dict): Nu run.info.

    Returns:
        list: ``(start, end)`` in m/z, one per integration region.
    """
    return [(float(_time_to_mass(run_info, r['Start'])), float(_time_to_mass(run_info, r['End'])))
            for r in run_info.get('IntegrationRegions') or []]


def peak_check(masses, spectrum, target_mass, window=None, half_width=ZOOM_HALF_WIDTH,
               single_ion_area=None):
    """Measure the peak nearest a mass in a resolved spectrum.

    Args:
        masses (np.ndarray): m/z of each spectrum point.
        spectrum (np.ndarray): Summed signal.
        target_mass (float): Isotope mass.
        window (tuple | None): Integration window (start, end) in m/z.
        half_width (float): Search range around the mass, in Da.
        single_ion_area (float | None): Area of one ion, to estimate how many
            ions form the peak.

    Returns:
        dict | None: ``centre``, ``width`` (FWHM, Da), ``resolution``,
        ``inside`` (bool, or None without a window), ``ions`` (float or None)
        and ``reliable`` (False when too few ions make the width meaningless);
        None without a peak.
    """
    mask = np.abs(masses - target_mass) <= half_width
    if not mask.any():
        return None
    mz, y = masses[mask], spectrum[mask]
    if y.max() <= 0:
        return None
    peak = int(np.argmax(y))
    above = y >= y[peak] / 2.0
    left = peak
    while left > 0 and above[left - 1]:
        left -= 1
    right = peak
    while right < len(y) - 1 and above[right + 1]:
        right += 1
    width = float(mz[right] - mz[left]) if right > left else float(np.median(np.diff(mz)))
    centre = float(mz[peak])
    inside = None if window is None else bool(window[0] <= centre <= window[1])
    ions = None
    if single_ion_area and single_ion_area > 0:
        lo, hi = window if window is not None else (centre - 3 * width, centre + 3 * width)
        in_peak = (masses >= lo) & (masses <= hi)
        ions = float(np.clip(spectrum[in_peak], 0, None).sum() / single_ion_area)
    return {'centre': centre, 'width': width,
            'resolution': centre / width if width > 0 else float('nan'), 'inside': inside,
            'ions': ions, 'reliable': ions is None or ions >= MIN_IONS_FOR_WIDTH}
