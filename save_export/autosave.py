"""Autosave and crash recovery for IsotopeTrack.

A long analysis session (loading many samples, per-element parameters,
calibration, canvas plots) only ever reaches disk when the user explicitly
saves. If the app crashes, is force-quit, or the machine sleeps and dies, that
work is lost. This module adds a safety net:

* **Autosave** — on a timer, whenever there are unsaved changes and real data
  loaded, a snapshot of the project is written to a hidden recovery folder using
  the same fast serializer as a normal save (``save_project_v2``), on a
  background thread so the UI never stalls.
* **Crash recovery** — a clean exit deletes its recovery file, so any recovery
  file still present at the next startup means the previous session did *not*
  exit cleanly. The app offers to reload the most recent one.

The recovery snapshot is an ordinary V2 project file, so it loads through the
existing project-load path with no special handling.
"""
from __future__ import annotations

import os
import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QStandardPaths, QSettings
import logging

_itk_log = logging.getLogger("IsotopeTrack.save_export.autosave")

RECOVERY_GLOB = "recovery_*.itproj"
DEFAULT_INTERVAL_MS = 60_000 


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

    Used only to avoid offering to recover a session that is currently open in
    another running instance. On platforms where this cannot be determined we
    err toward 'not alive' so a genuine crash is still recoverable.
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
    """Owns the autosave timer and the recovery file for one MainWindow."""

    def __init__(self, main_window, interval_ms: int | None = None):
        super().__init__(main_window)
        self.main_window = main_window
        self._writing = False
        self._thread = None

        settings = QSettings("IsotopeTrack", "IsotopeTrack")
        self._enabled = settings.value("autosave/enabled", True, type=bool)
        if interval_ms is None:
            try:
                interval_ms = int(settings.value("autosave/interval_ms", DEFAULT_INTERVAL_MS))
            except (TypeError, ValueError):
                interval_ms = DEFAULT_INTERVAL_MS
        interval_ms = max(30_000, interval_ms)  # never tighter than 30 s

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self):
        """Begin the autosave timer (no-op if autosave is disabled)."""
        if self._enabled:
            self._timer.start()

    def stop(self):
        """Stop the autosave timer."""
        self._timer.stop()

    def _recovery_path(self) -> Path:
        wid = getattr(self.main_window, "window_id", "W1")
        return recovery_dir() / f"recovery_{wid}_{os.getpid()}.itproj"

    # ── autosave ──────────────────────────────────────────────────────────
    def _has_data(self) -> bool:
        return bool(getattr(self.main_window, "data_by_sample", None))

    def _tick(self):
        if self._writing:
            return
        if not getattr(self.main_window, "unsaved_changes", False):
            return
        if not self._has_data():
            return
        self.write_snapshot()

    def write_snapshot(self):
        """Write a recovery snapshot on a background thread (reuses SaveProjectThread)."""
        if self._writing:
            return
        try:
            from save_export.project_manager import SaveProjectThread
        except Exception:
            _itk_log.exception("Autosave unavailable: cannot import SaveProjectThread")
            return
        self._writing = True
        path = str(self._recovery_path())
        thread = SaveProjectThread(path, self.main_window)
        thread.succeeded.connect(self._on_ok)
        thread.failed.connect(self._on_fail)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _on_ok(self, path):
        self._writing = False
        _itk_log.info("Autosave snapshot written: %s", path)

    def _on_fail(self, message):
        self._writing = False
        _itk_log.warning("Autosave snapshot failed: %s", message)

    def clear(self):
        """Delete this window's recovery file (call on a clean save or clean exit)."""
        try:
            p = self._recovery_path()
            if p.exists():
                p.unlink()
        except OSError:
            _itk_log.exception("Could not remove recovery file")

    # ── crash recovery ────────────────────────────────────────────────────
    @staticmethod
    def find_recovery_files():
        """Recovery files from crashed (not currently-running) sessions, newest first.

        Returns a list of ``(Path, datetime)`` tuples.
        """
        out = []
        for p in recovery_dir().glob(RECOVERY_GLOB):
            try:
                pid = int(p.stem.split("_")[-1])
            except (ValueError, IndexError):
                pid = -1
            if _pid_alive(pid):
                continue  # belongs to a running instance — skip
            try:
                mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                continue
            out.append((p, mtime))
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    @staticmethod
    def discard_recovery_files(paths):
        """Delete the given leftover recovery files."""
        for p in paths:
            try:
                Path(p).unlink()
            except OSError:
                _itk_log.exception("Could not discard recovery file %s", p)
