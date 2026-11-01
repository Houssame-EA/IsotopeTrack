"""Storage of the sensitivity (ionic) calibration session inside a project file.

The window state (concentration table, fits, manual slopes, exclusions) goes
into the project metadata. The signals of every calibration standard are
written as one compressed ``ionic/<n>.npz`` entry each, so the calibration can
be reopened and changed without the original standard folders.

The state is captured on the GUI thread (``refresh_calibration_snapshot``)
before a save starts, because the save itself runs on a worker thread and must
not touch Qt widgets.
"""
from __future__ import annotations

import io
import logging

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.save_export.calibration_store")

IONIC_DIR = "ionic"


def ionic_entry(index):
    """Return the zip entry path of one calibration standard.

    Args:
        index (int): Position of the standard in the window.

    Returns:
        str: Entry path inside the project zip.
    """
    return f"{IONIC_DIR}/{index:03d}.npz"


def ionic_fingerprint(data, folders):
    """Return a cheap identity of the standards held in memory.

    Two fingerprints are equal when the same signal arrays are loaded for the
    same folders, which is how a save knows the standards stored in the open
    project can be copied instead of compressed again.

    Args:
        data (dict): Folder -> {'masses', 'signals', 'run_info'}.
        folders (iterable): Folder order used by the window.

    Returns:
        tuple: Fingerprint.
    """
    return tuple(
        (folder, id(data[folder].get('signals')), np.shape(data[folder].get('signals')))
        for folder in folders
        if folder in data
    )


def refresh_calibration_snapshot(mw):
    """Capture the sensitivity calibration state on the GUI thread.

    When the calibration window exists and holds standards, its live state is
    used. Otherwise the state restored from the open project (not yet shown in
    a window) is carried forward unchanged.

    Args:
        mw: MainWindow instance.
    """
    window = getattr(mw, 'ionic_calibration_window', None)
    snapshot = {'state': None, 'data': None, 'fingerprint': None}
    if window is not None and getattr(window, 'folder_paths', None):
        try:
            snapshot['state'] = window.export_project_state()
            fingerprint = ionic_fingerprint(window.data, window.folder_paths)
            snapshot['fingerprint'] = fingerprint
            stored = getattr(mw, '_ionic_saved_entries', None) or {}
            unchanged = (
                fingerprint == getattr(mw, '_ionic_saved_fingerprint', None)
                and all(folder in stored for folder, _id, _shape in fingerprint)
            )
            if not unchanged:
                snapshot['data'] = dict(window.data)
        except Exception:
            _itk_log.exception("Could not capture the sensitivity calibration state")
    elif getattr(mw, '_ionic_saved_state', None):
        snapshot['state'] = mw._ionic_saved_state
        snapshot['fingerprint'] = getattr(mw, '_ionic_saved_fingerprint', None)
    try:
        from save_export.te_store import capture_te_snapshot
        snapshot['te'] = capture_te_snapshot(mw)
    except Exception:
        _itk_log.exception("Could not capture the transport efficiency state")
        snapshot['te'] = {'state': getattr(mw, '_te_saved_state', None), 'memory_arrays': {}}
    mw._calibration_snapshot = snapshot


def snapshot_state(mw):
    """Return the captured sensitivity calibration state, or None.

    Args:
        mw: MainWindow instance.

    Returns:
        dict | None: Session state without signal arrays.
    """
    snapshot = getattr(mw, '_calibration_snapshot', None)
    if snapshot is None:
        return getattr(mw, '_ionic_saved_state', None)
    return snapshot.get('state')


def te_snapshot_state(mw):
    """Return the captured transport efficiency state, or None.

    Args:
        mw: MainWindow instance.

    Returns:
        dict | None: TE session state without signal arrays.
    """
    snapshot = getattr(mw, '_calibration_snapshot', None)
    if snapshot is None or 'te' not in snapshot:
        return getattr(mw, '_te_saved_state', None)
    return (snapshot.get('te') or {}).get('state')


def write_ionic_data(zf, mw, old_source):
    """Write the signals of the calibration standards into a project being saved.

    Args:
        zf (zipfile.ZipFile): Destination archive opened for writing.
        mw: MainWindow instance.
        old_source: ``ReserveSource`` on the currently open project, used to
            copy the standards forward when the window was never opened.

    Returns:
        dict: Standard folder path -> entry path written.
    """
    snapshot = getattr(mw, '_calibration_snapshot', None) or {}
    state = snapshot.get('state')
    if not state:
        return {}
    folders = list(state.get('folder_paths') or [])
    entries = {}

    data = snapshot.get('data')
    if data is not None:
        for index, folder in enumerate(folders):
            record = data.get(folder)
            if not record or record.get('signals') is None:
                continue
            buf = io.BytesIO()
            np.savez_compressed(
                buf,
                masses=np.asarray(record['masses']),
                signals=np.asarray(record['signals']),
            )
            entry = ionic_entry(index)
            zf.writestr(entry, buf.getvalue())
            entries[folder] = entry
        return entries

    old_entries = getattr(mw, '_ionic_saved_entries', None) or {}
    wanted = set(folders)
    for folder, entry in old_entries.items():
        if folder not in wanted:
            continue
        try:
            zf.writestr(entry, old_source.read_entry(entry))
            entries[folder] = entry
        except Exception:
            _itk_log.exception("Could not copy calibration standard %s", folder)
    return entries


def read_ionic_data(project_path, entries, state):
    """Read the calibration standards back from a project file.

    Args:
        project_path (str | Path): Project file path.
        entries (dict): Standard folder path -> entry path, from the manifest.
        state (dict): Saved session state (provides each standard's run info).

    Returns:
        dict: Folder -> {'masses', 'signals', 'run_info'}, the structure the
        calibration window keeps in ``data``.
    """
    import zipfile

    run_infos = (state or {}).get('run_info') or {}
    data = {}
    if not project_path or not entries:
        return data
    with zipfile.ZipFile(project_path, 'r') as zf:
        for folder, entry in entries.items():
            try:
                npz = np.load(io.BytesIO(zf.read(entry)), allow_pickle=False)
                data[folder] = {
                    'masses': npz['masses'],
                    'signals': npz['signals'],
                    'run_info': run_infos.get(folder) or {},
                }
            except Exception:
                _itk_log.exception("Could not read calibration standard %s", folder)
    return data
