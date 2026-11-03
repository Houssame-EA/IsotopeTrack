"""Storage of the transport efficiency (TE) calibration inside a project file.

The state of the TE window goes into the project metadata. A TE calibration
uses a single element, so only the signal of the selected isotope of every TE
sample is written, under ``te/<method>/<n>/<mass>.npy``. Choosing another
element later reads it from the raw data again.

When a project is saved, each sample's signal is taken from memory; a sample
whose signal is not in memory is copied from the open project when it is
stored there.
"""
from __future__ import annotations

import io
import logging
import pickle
import zipfile

import numpy as np

from save_export.isotope_reserve import RESERVE_COMPRESSION, RESERVE_COMPRESSLEVEL

_itk_log = logging.getLogger("IsotopeTrack.save_export.te_store")

TE_DIR = "te"
NUMBER = "number"
MASS = "mass"
MASS_IONIC = "mass_ionic"
TE_MAX_MASS_DIFF = 1.0


def _channel_entry(sample_dir, mass):
    """Return the entry path of one stored mass.

    Args:
        sample_dir (str): Sample folder inside the zip, e.g. ``te/number/000``.
        mass (float): Channel mass.

    Returns:
        str: Entry path.
    """
    return f"{sample_dir}/{float(mass):.6f}.npy"


def _npy_bytes(arr):
    """Serialize an array to ``.npy`` bytes.

    Args:
        arr (np.ndarray): Array.

    Returns:
        bytes: Payload.
    """
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr), allow_pickle=False)
    return buf.getvalue()


def picklable_dict(data):
    """Return a copy of a dict keeping only the values that can be pickled.

    Args:
        data (dict | None): Source dict.

    Returns:
        dict | None: Filtered copy.
    """
    if data is None:
        return None
    kept = {}
    for key, value in data.items():
        try:
            pickle.dumps(value)
        except Exception:
            continue
        kept[key] = value
    return kept


def _next_free_dir(method, used):
    """Return an unused sample folder name for a method.

    Args:
        method (str): TE method key.
        used (set[str]): Folder names already taken.

    Returns:
        str: New folder name.
    """
    index = 0
    while f"{TE_DIR}/{method}/{index:03d}" in used:
        index += 1
    name = f"{TE_DIR}/{method}/{index:03d}"
    used.add(name)
    return name


def write_te_samples(zf, method, folders, memory_arrays, old_source, old_index):
    """Write the signal of the selected isotope of the TE samples of one method.

    Args:
        zf (zipfile.ZipFile): Destination archive opened for writing.
        method (str): TE method key, e.g. ``'number'``.
        folders (list[str]): Sample sources, in window order.
        memory_arrays (dict): Source -> {'channels': {mass: array}, 'time_array': array}
            holding the selected isotope signal of each loaded sample.
        old_source: ``ReserveSource`` on the currently open project.
        old_index (dict): Source -> info, the index of this method in the open project.

    Returns:
        dict: Source -> {'dir', 'masses', 'dwell', 'n'} for every sample written.
    """
    index = {}
    used = {info['dir'] for folder, info in (old_index or {}).items() if folder in folders}

    for folder in folders:
        old = (old_index or {}).get(folder)
        if old and folder not in memory_arrays:
            try:
                for mass in old['masses']:
                    entry = _channel_entry(old['dir'], mass)
                    zf.writestr(entry, old_source.read_entry(entry),
                                compress_type=RESERVE_COMPRESSION,
                                compresslevel=RESERVE_COMPRESSLEVEL)
                index[folder] = dict(old)
                continue
            except Exception:
                _itk_log.exception("Could not copy stored TE sample %s", folder)

        if folder not in memory_arrays:
            continue
        sample_dir = old['dir'] if old else _next_free_dir(method, used)
        try:
            channels = memory_arrays[folder].get('channels') or {}
            time_array = np.asarray(memory_arrays[folder].get('time_array'))
            masses = sorted(float(m) for m in channels)
            for mass in masses:
                zf.writestr(_channel_entry(sample_dir, mass), _npy_bytes(channels[mass]),
                            compress_type=RESERVE_COMPRESSION,
                            compresslevel=RESERVE_COMPRESSLEVEL)
            n = len(time_array)
            dwell = float(np.mean(np.diff(time_array))) if n > 1 else 0.0
            index[folder] = {'dir': sample_dir, 'masses': masses, 'dwell': dwell, 'n': n}
        except Exception:
            _itk_log.exception("Could not save TE sample %s", folder)
    return index


def read_te_channel(project_path, info, target_mass, max_diff=TE_MAX_MASS_DIFF):
    """Read the stored mass closest to a target for one TE sample.

    Args:
        project_path (str | Path): Project file path.
        info (dict): Sample entry from the TE index.
        target_mass (float): Isotope mass wanted.
        max_diff (float): Largest accepted difference in Da.

    Returns:
        tuple: (signal, stored mass, index of that mass in the stored list).

    Raises:
        ValueError: When no stored mass is close enough.
    """
    masses = np.asarray(info['masses'], dtype=np.float64)
    if masses.size == 0:
        raise ValueError("No masses stored for this sample")
    idx = int(np.argmin(np.abs(masses - float(target_mass))))
    if abs(masses[idx] - float(target_mass)) > max_diff:
        raise ValueError(
            f"No suitable isotope found for mass {target_mass:.4f}. "
            f"Closest stored: {masses[idx]:.4f}")
    with zipfile.ZipFile(project_path, 'r') as zf:
        data = zf.read(_channel_entry(info['dir'], masses[idx]))
    return np.load(io.BytesIO(data), allow_pickle=False), float(masses[idx]), idx


def _te_window(mw):
    """Return the TE window of the main window, or None."""
    return getattr(mw, 'transport_rate_window', None)


def te_widget(mw, label):
    """Return one method widget of the TE window, or None.

    Args:
        mw: MainWindow instance.
        label (str): Method label, e.g. ``'Number based'``.

    Returns:
        QWidget | None: The widget.
    """
    window = _te_window(mw)
    if window is None:
        return None
    return getattr(window, '_method_widgets', {}).get(label)


def capture_te_snapshot(mw):
    """Capture the TE window state on the GUI thread.

    Args:
        mw: MainWindow instance.

    Returns:
        dict: {'state': dict | None, 'memory_arrays': {method: {...}}}.
    """
    window = _te_window(mw)
    if window is None:
        return {'state': getattr(mw, '_te_saved_state', None), 'memory_arrays': {}}
    state = {'method': window.method_combo.currentText()}
    memory_arrays = {}
    liquid = te_widget(mw, "Liquid weight")
    if liquid is not None and hasattr(liquid, 'export_project_state'):
        state['liquid'] = liquid.export_project_state()
    number = te_widget(mw, "Number based")
    if number is not None and hasattr(number, 'export_project_state'):
        number_state = number.export_project_state()
        if number_state.get('folder_paths'):
            state['number'] = number_state
            memory_arrays[NUMBER] = number.export_memory_arrays()
    mass = te_widget(mw, "Mass based")
    if mass is not None and hasattr(mass, 'export_project_state'):
        mass_state = mass.export_project_state()
        if mass_state.get('particle_folder_paths') or mass_state.get('calibration_folder_paths'):
            state['mass'] = mass_state
            particles, standards = mass.export_memory_arrays()
            memory_arrays[MASS] = particles
            memory_arrays[MASS_IONIC] = standards
    return {'state': state, 'memory_arrays': memory_arrays}


def write_te_data(zf, mw, old_source):
    """Write the TE samples of every stored method into a project being saved.

    Args:
        zf (zipfile.ZipFile): Destination archive opened for writing.
        mw: MainWindow instance.
        old_source: ``ReserveSource`` on the currently open project.

    Returns:
        dict: Method -> sample index, for the manifest.
    """
    snapshot = (getattr(mw, '_calibration_snapshot', None) or {}).get('te') or {}
    state = snapshot.get('state') or {}
    old_index = getattr(mw, '_te_saved_index', None) or {}
    result = {}
    number_state = state.get('number')
    if number_state:
        result[NUMBER] = write_te_samples(
            zf, NUMBER, list(number_state.get('folder_paths') or []),
            (snapshot.get('memory_arrays') or {}).get(NUMBER) or {},
            old_source, old_index.get(NUMBER) or {},
        )
    mass_state = state.get('mass')
    if mass_state:
        arrays = snapshot.get('memory_arrays') or {}
        result[MASS] = write_te_samples(
            zf, MASS, list(mass_state.get('particle_folder_paths') or []),
            arrays.get(MASS) or {}, old_source, old_index.get(MASS) or {},
        )
        result[MASS_IONIC] = write_te_samples(
            zf, MASS_IONIC, list(mass_state.get('calibration_folder_paths') or []),
            arrays.get(MASS_IONIC) or {}, old_source, old_index.get(MASS_IONIC) or {},
        )
    return result


def apply_te_store_after_save(mw, project_path):
    """Point the TE widgets at the project just saved, on the GUI thread.

    Samples now stored in the project can be read from it afterwards, so a
    raw folder that disappears later is no longer needed.

    Args:
        mw: MainWindow instance.
        project_path (str): Path of the saved project.
    """
    saved = getattr(mw, '_te_saved_index', None) or {}
    number = te_widget(mw, "Number based")
    if number is not None and hasattr(number, 'attach_project_store'):
        number.attach_project_store(str(project_path), saved.get(NUMBER) or {})
    mass = te_widget(mw, "Mass based")
    if mass is not None and hasattr(mass, 'attach_project_store'):
        mass.attach_project_store(str(project_path), saved.get(MASS) or {}, saved.get(MASS_IONIC) or {})
