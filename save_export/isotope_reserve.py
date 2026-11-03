"""Reserve of unselected isotopes stored inside an IsotopeTrack project file.

Every mass channel of a sample that is not part of the current isotope
selection is written to ``reserve/<sample>/<mass>.npy`` inside the ``.itproj``
zip, one compressed entry per channel. The selected isotopes keep living in
``arrays/`` exactly as before, so opening a project costs nothing extra; a
reserve channel is only read when the user asks for it.

When a project is saved, each sample's reserve is taken from the project file
that is currently open (when it already holds a reserve for the same sample
and data source), otherwise from the original raw data, otherwise the sample
is saved without a reserve.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.save_export.isotope_reserve")

RESERVE_DIR = "reserve"
RESERVE_COMPRESSION = zipfile.ZIP_DEFLATED
RESERVE_COMPRESSLEVEL = 6
MAX_MASS_DIFF = 0.5

SOURCE_PROJECT = "project"
SOURCE_RAW = "raw"
SOURCE_NONE = "none"


def safe_sample_name(sample_name):
    """Return the sample name with path separators replaced, as used in zip entries.

    Args:
        sample_name (str): Sample name.

    Returns:
        str: Name safe to use inside a zip entry path.
    """
    return sample_name.replace('/', '_').replace('\\', '_')


def entry_name(sample_name, mass):
    """Return the zip entry path of one reserve channel.

    Args:
        sample_name (str): Sample name.
        mass (float): Channel mass.

    Returns:
        str: Entry path inside the project zip.
    """
    return f"{RESERVE_DIR}/{safe_sample_name(sample_name)}/{float(mass):.6f}.npy"


def _array_to_npy_bytes(arr):
    """Serialize an array to ``.npy`` bytes.

    Args:
        arr (np.ndarray): Array to serialize.

    Returns:
        bytes: The ``.npy`` payload.
    """
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr), allow_pickle=False)
    return buf.getvalue()


def _npy_bytes_to_array(data):
    """Deserialize ``.npy`` bytes.

    Args:
        data (bytes): The ``.npy`` payload.

    Returns:
        np.ndarray: The stored array.
    """
    return np.load(io.BytesIO(data), allow_pickle=False)


def _write_channel(zf, sample_name, mass, payload):
    """Write one reserve channel entry, compressed.

    Args:
        zf (zipfile.ZipFile): Destination archive opened for writing.
        sample_name (str): Sample name.
        mass (float): Channel mass.
        payload (bytes): ``.npy`` bytes of the channel signal.
    """
    zf.writestr(
        entry_name(sample_name, mass),
        payload,
        compress_type=RESERVE_COMPRESSION,
        compresslevel=RESERVE_COMPRESSLEVEL,
    )


def closest_channel_indices(channel_masses, target_masses, max_diff=MAX_MASS_DIFF):
    """Return the indices of the channels the target masses resolve to.

    Uses the same rule as the data loader: each target maps to its closest
    channel when that channel lies within ``max_diff``.

    Args:
        channel_masses (array-like): Available channel masses.
        target_masses (iterable): Selected isotope masses.
        max_diff (float): Largest accepted mass difference in Da.

    Returns:
        set[int]: Indices into ``channel_masses``.
    """
    channel_masses = np.asarray(channel_masses, dtype=np.float64)
    used = set()
    if channel_masses.size == 0:
        return used
    for target in target_masses:
        diffs = np.abs(channel_masses - float(target))
        idx = int(np.argmin(diffs))
        if diffs[idx] <= max_diff:
            used.add(idx)
    return used


def raw_source_kind(folder_path):
    """Return the raw data format of a sample source, or None when unusable.

    Args:
        folder_path (str | Path | None): Path recorded for the sample.

    Returns:
        str | None: ``'nu'``, ``'tofwerk'`` or None.
    """
    if not folder_path:
        return None
    path = Path(folder_path)
    if not path.exists():
        return None
    try:
        from loading.data_thread import DataProcessThread
        kind = DataProcessThread.detect_data_format(str(path))
    except Exception:
        _itk_log.exception("Could not detect raw data format for %s", folder_path)
        return None
    return kind if kind in ('nu', 'tofwerk') else None


def iter_raw_channels(folder_path):
    """Yield every mass channel of a Nu or TOFWERK acquisition.

    The signals are read with the same settings as the data loader, so a
    channel taken from the reserve is identical to one loaded from the raw
    data.

    Args:
        folder_path (str | Path): Nu run folder or TOFWERK file/folder.

    Yields:
        tuple[float, np.ndarray]: Channel mass and its signal.
    """
    kind = raw_source_kind(folder_path)
    if kind == 'nu':
        import loading.vitesse_loading as vitesse
        masses, signals, _run_info = vitesse.read_nu_directory(
            path=str(folder_path),
            max_integ_files=None,
            autoblank=True,
            cycle=None,
            segment=None,
            raw=False,
        )
        signals = np.asarray(signals)
        for idx, mass in enumerate(np.asarray(masses, dtype=np.float64)):
            yield float(mass), signals[:, idx].astype(np.float32, copy=False)
        return

    if kind == 'tofwerk':
        import loading.tofwerk_loading as tofwerk
        path = Path(folder_path)
        if path.is_file():
            h5_file = path
        else:
            h5_files = [f for f in path.glob("*.h5") if tofwerk.is_tofwerk_file(f)]
            if not h5_files:
                return
            h5_file = h5_files[0]
        data, info, _dwell = tofwerk.read_tofwerk_file(h5_file)
        if 'mass' in info.dtype.names:
            masses = np.asarray(info['mass'], dtype=np.float64)
        else:
            masses = np.array([
                float(label.decode() if isinstance(label, bytes) else label)
                for label in info['label']
            ])
        names = data.dtype.names if hasattr(data.dtype, 'names') else None
        for idx, mass in enumerate(masses):
            if names and len(names) > idx:
                yield float(mass), np.asarray(data[names[idx]])
            elif data.ndim > 1 and data.shape[1] > idx:
                yield float(mass), np.asarray(data[:, idx])
        return


class ReserveSource:
    """Read access to the reserve stored in an existing project file.

    Opened on the project that is currently loaded, so a save can carry its
    reserve forward without touching the raw data.
    """

    def __init__(self, project_path):
        """Open the project archive and read its reserve index.

        Args:
            project_path (str | Path | None): Path of the currently open project.
        """
        self._zf = None
        self.manifest = {}
        self.index = {}
        self.sources = {}
        if not project_path:
            return
        path = Path(project_path)
        if not path.is_file():
            return
        try:
            zf = zipfile.ZipFile(path, 'r')
        except (zipfile.BadZipFile, OSError):
            return
        try:
            manifest = json.loads(zf.read('manifest.json'))
        except (KeyError, ValueError):
            zf.close()
            return
        self._zf = zf
        self.manifest = manifest
        self.index = {
            name: [float(m) for m in masses]
            for name, masses in (manifest.get('reserve') or {}).items()
        }
        self.sources = dict(manifest.get('reserve_sources') or {})

    def masses_for(self, sample_name, folder_path):
        """Return the reserve masses usable for a sample, or an empty list.

        The stored reserve is only reused when it was built from the same data
        source, so a different sample that happens to share a name is never
        given another sample's signals.

        Args:
            sample_name (str): Sample name.
            folder_path (str | Path | None): Current data source of the sample.

        Returns:
            list[float]: Masses available in the stored reserve.
        """
        if self._zf is None or sample_name not in self.index:
            return []
        if str(self.sources.get(sample_name, '')) != str(folder_path or ''):
            return []
        return self.index[sample_name]

    def read_payload(self, sample_name, mass):
        """Return the ``.npy`` bytes of one stored channel.

        Args:
            sample_name (str): Sample name.
            mass (float): Channel mass.

        Returns:
            bytes: The ``.npy`` payload.
        """
        return self._zf.read(entry_name(sample_name, mass))

    def read_entry(self, name):
        """Return the bytes of any entry of the open project.

        Args:
            name (str): Entry path inside the zip.

        Returns:
            bytes: Entry content.
        """
        if self._zf is None:
            raise KeyError(name)
        return self._zf.read(name)

    def close(self):
        """Close the underlying archive."""
        if self._zf is not None:
            self._zf.close()
            self._zf = None


def write_sample_reserve(zf, sample_name, selected_masses, folder_path, source):
    """Write the reserve of one sample into a project archive being saved.

    Args:
        zf (zipfile.ZipFile): Destination archive opened for writing.
        sample_name (str): Sample name.
        selected_masses (iterable): Isotope masses currently selected for the sample.
        folder_path (str | Path | None): Raw data source of the sample.
        source (ReserveSource): Reserve of the currently open project.

    Returns:
        tuple[list[float], str]: Masses written and where they came from
        (``'project'``, ``'raw'`` or ``'none'``).
    """
    selected_masses = [float(m) for m in selected_masses]

    stored = source.masses_for(sample_name, folder_path)
    if stored:
        used = closest_channel_indices(stored, selected_masses)
        written = []
        for idx, mass in enumerate(stored):
            if idx in used:
                continue
            _write_channel(zf, sample_name, mass, source.read_payload(sample_name, mass))
            written.append(mass)
        return written, SOURCE_PROJECT

    if raw_source_kind(folder_path) is None:
        return [], SOURCE_NONE

    channels = list(iter_raw_channels(folder_path))
    used = closest_channel_indices([m for m, _ in channels], selected_masses)
    written = []
    for idx, (mass, signal) in enumerate(channels):
        if idx in used:
            continue
        _write_channel(zf, sample_name, mass, _array_to_npy_bytes(signal))
        written.append(mass)
    return written, SOURCE_RAW


def read_reserve_channel(project_path, sample_name, mass):
    """Read one channel back from a project's reserve.

    Args:
        project_path (str | Path): Project file path.
        sample_name (str): Sample name.
        mass (float): Channel mass as listed in the manifest.

    Returns:
        np.ndarray: The channel signal.
    """
    with zipfile.ZipFile(project_path, 'r') as zf:
        return _npy_bytes_to_array(zf.read(entry_name(sample_name, mass)))


def match_reserve_masses(reserve_masses, target_masses, max_diff=MAX_MASS_DIFF):
    """Map each target isotope mass to its closest reserve channel.

    Args:
        reserve_masses (iterable): Channel masses available in the reserve.
        target_masses (iterable): Isotope masses being added.
        max_diff (float): Largest accepted mass difference in Da.

    Returns:
        dict: Target mass -> reserve channel mass, for the targets that match.
    """
    masses = np.asarray(list(reserve_masses), dtype=np.float64)
    matched = {}
    if masses.size == 0:
        return matched
    for target in target_masses:
        diffs = np.abs(masses - float(target))
        idx = int(np.argmin(diffs))
        if diffs[idx] <= max_diff:
            matched[target] = float(masses[idx])
    return matched


def read_reserve_channels(project_path, sample_name, masses):
    """Read several channels of one sample from a project's reserve.

    Args:
        project_path (str | Path): Project file path.
        sample_name (str): Sample name.
        masses (iterable): Channel masses as listed in the manifest.

    Returns:
        dict: Channel mass -> signal array.
    """
    with zipfile.ZipFile(project_path, 'r') as zf:
        return {
            float(m): _npy_bytes_to_array(zf.read(entry_name(sample_name, m)))
            for m in masses
        }
