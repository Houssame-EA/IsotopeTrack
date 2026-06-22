"""Autosave and crash recovery for IsotopeTrack.

A long analysis session (loading many samples, per-element parameters,
calibration, canvas plots) only ever reaches disk when the user explicitly
saves. If the app crashes, is force-quit, or the machine sleeps and dies, that
work is lost. This module is the safety net.

Two-tier snapshots
-------------------
A saved project embeds the raw signal, which can be gigabytes; rewriting all of
it every couple of minutes is wasteful. Instead the recovery snapshot is split:

* a **heavy** file (an ordinary ``.itproj``) holding the raw per-sample arrays,
  written once and refreshed only when the loaded sample set changes; and
* a **light** file holding just the small, frequently-changing state
  (parameters, results, calibration, detected particles), rewritten on a
  debounce after edits settle plus a periodic safety net.

Light writes are atomic (temp file + rename) so a crash mid-write can never
corrupt the recovery state. On recovery the heavy file is loaded normally and
the newer light file is overlaid on top.

Crash recovery
--------------
A clean exit deletes its recovery files, so any file still present at the next
startup means the previous session did not exit cleanly, and the app offers to
reload the most recent one.
"""
from __future__ import annotations

import os
import time
import pickle
import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QStandardPaths, QSettings
import logging

_itk_log = logging.getLogger("IsotopeTrack.save_export.autosave")

RECOVERY_GLOB = "recovery_*.itproj"

POLL_MS = 1000
DEBOUNCE_MS = 4000
SAFETY_MS = 180_000

_FINGERPRINT_FIELDS = (
    'selected_isotopes',
    'sample_parameters',
    'isotope_method_preferences',
    'element_thresholds',
    'element_limits',
    'calibration_results',
    'average_transport_rate',
    'selected_transport_rate_methods',
    'element_mass_fractions',
    'element_densities',
    'sample_mass_fractions',
    'sample_densities',
    'sample_dilutions',
    'overlap_threshold_percentage',
    '_global_sigma',
    '_sigma_mode',
    'detection_states',
    'saturation_filter_enabled',
)


def recovery_dir() -> Path:
    """Return (creating if needed) the per-user folder holding recovery files."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if not base:
        base = str(Path.home() / ".isotopetrack")
    d = Path(base) / "recovery"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        _itk_log.exception("Could not create recovery directory")
    return d


def _pid_alive(pid: int) -> bool:
    """Best-effort check whether ``pid`` belongs to a still-running process.

    Used to avoid offering to recover a session that is currently open in
    another running instance. Where this cannot be determined we err toward
    'not alive' so a genuine crash is still recoverable.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class AutosaveManager(QObject):
    """Owns the autosave timer and the recovery files for one MainWindow."""

    def __init__(self, main_window, interval_ms: int | None = None):
        """Create the manager and its poll timer (disabled if autosave is off)."""
        super().__init__(main_window)
        self.main_window = main_window
        self._writing = False
        self._thread = None

        settings = QSettings("IsotopeTrack", "IsotopeTrack")
        self._enabled = settings.value("autosave/enabled", True, type=bool)

        now = self._now_ms()
        self._heavy_sig = None
        self._last_fp = None
        self._fp_at_last_write = None
        self._pending_fp = None
        self._last_activity_ms = now
        self._last_write_ms = now

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    @staticmethod
    def _now_ms() -> int:
        """Monotonic millisecond clock for debounce/safety timing."""
        return int(time.monotonic() * 1000)

    def start(self):
        """Begin the autosave poll timer (no-op if autosave is disabled)."""
        if self._enabled:
            self._timer.start()

    def stop(self):
        """Stop the timer and wait for any in-flight heavy snapshot write.

        Blocks until a running ``SaveProjectThread`` finishes, otherwise the
        background thread would still be serializing project data while the
        interpreter tears down on exit.
        """
        self._timer.stop()
        thread = self._thread
        if thread is not None:
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(10000):
                        thread.terminate()
                        thread.wait(2000)
            except RuntimeError:
                pass
        self._writing = False

    def _heavy_path(self) -> Path:
        """Path of this window's heavy recovery file (raw arrays)."""
        wid = getattr(self.main_window, "window_id", "W1")
        return recovery_dir() / f"recovery_{wid}_{os.getpid()}.itproj"

    def _light_path(self) -> Path:
        """Path of this window's light recovery file (metadata + particles)."""
        return self._heavy_path().with_suffix('.light')

    def _has_data(self) -> bool:
        return bool(getattr(self.main_window, "data_by_sample", None))

    def _sample_sig(self):
        """Signature of the loaded sample set; a change forces a heavy rewrite."""
        d = getattr(self.main_window, "data_by_sample", None) or {}
        return tuple(sorted(d.keys()))

    def _flush_parameters(self):
        """Commit any pending parameters-table edit into ``sample_parameters``.

        The table only writes back to ``sample_parameters`` on certain events,
        so flush first to be sure the snapshot reflects the visible edits.
        """
        flush = getattr(self.main_window, "save_current_parameters", None)
        if callable(flush):
            try:
                flush()
            except Exception:
                _itk_log.debug("Parameter flush before autosave skipped")

    def _fingerprint(self) -> bytes:
        """Cheap signature of the editable inputs and result counts.

        Detects whether anything worth autosaving changed without serializing
        the whole project on every poll.
        """
        import hashlib
        h = hashlib.md5()
        mw = self.main_window
        for f in _FINGERPRINT_FIELDS:
            try:
                h.update(repr(getattr(mw, f, None)).encode('utf-8', 'replace'))
            except Exception:
                pass
        for attr in ('sample_particle_data', 'sample_detected_peaks', 'sample_results_data'):
            d = getattr(mw, attr, None) or {}
            try:
                for k in sorted(d.keys()):
                    v = d[k]
                    n = len(v) if hasattr(v, '__len__') else 0
                    h.update(f"{attr}:{k}:{n}".encode('utf-8', 'replace'))
            except Exception:
                pass
        return h.digest()

    def _poll(self):
        """Decide, on each tick, whether enough has changed and settled to save."""
        if self._writing or not self._has_data():
            return
        self._flush_parameters()
        if not getattr(self.main_window, "unsaved_changes", False):
            return
        fp = self._fingerprint()
        now = self._now_ms()
        if fp != self._last_fp:
            self._last_fp = fp
            self._last_activity_ms = now
        if fp == self._fp_at_last_write:
            return
        settled = (now - self._last_activity_ms) >= DEBOUNCE_MS
        safety = (now - self._last_write_ms) >= SAFETY_MS
        if settled or safety:
            self._write(fp)

    def _write(self, fp):
        """Write a heavy snapshot if the sample set changed, else a light one."""
        self._pending_fp = fp
        sig = self._sample_sig()
        if sig != self._heavy_sig or not self._heavy_path().exists():
            self._write_heavy(sig)
        elif self._write_light():
            self._fp_at_last_write = fp
            self._last_write_ms = self._now_ms()
            self._toast()

    def _write_heavy(self, sig):
        """Write the full ``.itproj`` (raw arrays included) on a background thread."""
        try:
            from save_export.project_manager import SaveProjectThread
        except Exception:
            _itk_log.exception("Autosave unavailable: cannot import SaveProjectThread")
            return
        self._writing = True
        thread = SaveProjectThread(str(self._heavy_path()), self.main_window)
        thread.succeeded.connect(lambda _p, _sig=sig: self._on_heavy_ok(_sig))
        thread.failed.connect(self._on_heavy_fail)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _on_heavy_ok(self, sig):
        """Finalize a heavy write, then write the matching light file."""
        self._heavy_sig = sig
        self._writing = False
        self._write_light()
        if self._pending_fp is not None:
            self._fp_at_last_write = self._pending_fp
        self._last_write_ms = self._now_ms()
        self._toast()

    def _on_heavy_fail(self, message):
        """Record a failed heavy write so the next poll can retry."""
        self._writing = False
        _itk_log.warning("Autosave (heavy) failed: %s", message)

    def _write_light(self) -> bool:
        """Atomically write the small light snapshot (metadata + particle data)."""
        try:
            from save_export.fast_project_io import build_metadata
        except Exception:
            _itk_log.exception("Autosave unavailable: cannot import build_metadata")
            return False
        payload = {
            'metadata': build_metadata(self.main_window),
            'sample_particle_data': getattr(self.main_window, 'sample_particle_data', {}),
        }
        light_path = self._light_path()
        tmp = light_path.with_suffix('.light.tmp')
        try:
            with open(tmp, 'wb') as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, light_path)
            return True
        except Exception:
            _itk_log.exception("Autosave (light) failed")
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            return False

    def _toast(self):
        """Show the brief 'Autosaved' confirmation if the window supports it."""
        try:
            notify = getattr(self.main_window, "notify", None)
            if callable(notify):
                notify("Autosaved", "success", 1500)
        except Exception:
            _itk_log.debug("Autosave toast skipped")

    def clear(self):
        """Delete this window's recovery files (on a clean save or clean exit)."""
        for p in (self._heavy_path(), self._light_path()):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                _itk_log.exception("Could not remove recovery file %s", p)

    @staticmethod
    def apply_light_overlay(mw, heavy_path):
        """Overlay the newer light snapshot onto a just-loaded heavy recovery file.

        The heavy ``.itproj`` restores the raw arrays and a baseline of the rest;
        this then applies the latest parameters, results, calibration and
        particle data saved since that baseline.
        """
        light_path = Path(heavy_path).with_suffix('.light')
        if not light_path.exists():
            return
        try:
            with open(light_path, 'rb') as f:
                payload = pickle.load(f)
        except Exception:
            _itk_log.exception("Could not read light recovery overlay")
            return
        try:
            from save_export.fast_project_io import _restore_metadata
            meta = payload.get('metadata')
            if meta:
                _restore_metadata(mw, meta)
            if 'sample_particle_data' in payload:
                mw.sample_particle_data = payload['sample_particle_data']
            pm = getattr(mw, 'project_manager', None)
            if pm is not None and hasattr(pm, '_update_ui_after_load'):
                pm._update_ui_after_load()
        except Exception:
            _itk_log.exception("Could not apply light recovery overlay")

    @staticmethod
    def find_recovery_files():
        """Heavy recovery files from crashed (not currently-running) sessions.

        Returns a list of ``(Path, datetime)`` tuples, newest first.
        """
        out = []
        for p in recovery_dir().glob(RECOVERY_GLOB):
            try:
                pid = int(p.stem.split("_")[-1])
            except (ValueError, IndexError):
                pid = -1
            if _pid_alive(pid):
                continue
            try:
                mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                continue
            out.append((p, mtime))
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    @staticmethod
    def discard_recovery_files(paths):
        """Delete the given heavy recovery files and their light companions."""
        for p in paths:
            for target in (Path(p), Path(p).with_suffix('.light')):
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    _itk_log.exception("Could not discard recovery file %s", target)
