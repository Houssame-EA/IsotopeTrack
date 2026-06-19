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

from PySide6.QtCore import QObject, QTimer, QStandardPaths, QSettings, QThread
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox,
                                QSpinBox, QLabel, QPushButton, QFrame)
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
        """Stop the autosave timer and wait for any in-flight snapshot write.

        Critically, this blocks until a running ``SaveProjectThread`` has
        finished. If it didn't, the background thread would still be
        serializing project data while the interpreter tears down on exit,
        and the final GC pass would crash walking that half-freed state.
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
                # Underlying C++ thread object already deleted — nothing to wait on.
                pass
        self._writing = False

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
        self._set_status("Auto-saving…")
        path = str(self._recovery_path())
        thread = SaveProjectThread(path, self.main_window)
        thread.succeeded.connect(self._on_ok)
        thread.failed.connect(self._on_fail)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()
        try:
            thread.setPriority(QThread.Priority.LowPriority)
        except Exception:
            pass

    def _on_ok(self, path):
        self._writing = False
        _itk_log.info("Autosave snapshot written: %s", path)
        self._set_status("Ready")
        try:
            notify = getattr(self.main_window, "notify", None)
            if callable(notify):
                notify("Autosaved", "success", 1800)
        except Exception:
            _itk_log.debug("Autosave toast skipped")

    def _on_fail(self, message):
        self._writing = False
        self._set_status("Ready")
        _itk_log.warning("Autosave snapshot failed: %s", message)

    def _set_status(self, text: str):
        try:
            lbl = getattr(self.main_window, "status_label", None)
            if lbl is not None:
                lbl.setText(text)
        except RuntimeError:
            pass

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

    def reconfigure(self, enabled: bool, interval_ms: int):
        """Apply new settings at runtime and persist to QSettings."""
        interval_ms = max(30_000, interval_ms)
        self._enabled = enabled
        self._timer.setInterval(interval_ms)
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()
        settings = QSettings("IsotopeTrack", "IsotopeTrack")
        settings.setValue("autosave/enabled", enabled)
        settings.setValue("autosave/interval_ms", interval_ms)


class AutoSaveSettingsDialog(QDialog):
    """Modal dialog for configuring auto-save enable/disable and interval."""

    def __init__(self, enabled: bool, interval_ms: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto Save Settings")
        self.setMinimumWidth(340)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(18, 18, 18, 14)

        self._enabled_cb = QCheckBox("Enable automatic saving")
        self._enabled_cb.setChecked(enabled)
        lay.addWidget(self._enabled_cb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        lay.addWidget(sep)

        self._interval_frame = QFrame()
        interval_lay = QVBoxLayout(self._interval_frame)
        interval_lay.setContentsMargins(0, 0, 0, 0)
        interval_lay.setSpacing(8)

        spinner_row = QHBoxLayout()
        spinner_row.addWidget(QLabel("Save every:"))

        self._hours_spin = QSpinBox()
        self._hours_spin.setRange(0, 23)
        self._hours_spin.setSuffix(" h")
        self._hours_spin.setFixedWidth(72)
        spinner_row.addWidget(self._hours_spin)

        self._minutes_spin = QSpinBox()
        self._minutes_spin.setRange(0, 59)
        self._minutes_spin.setSuffix(" min")
        self._minutes_spin.setFixedWidth(82)
        spinner_row.addWidget(self._minutes_spin)
        spinner_row.addStretch()
        interval_lay.addLayout(spinner_row)

        hint = QLabel("Minimum interval is 30 seconds.\nZero hours and zero minutes defaults to 30 s.")
        hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        interval_lay.addWidget(hint)
        lay.addWidget(self._interval_frame)

        total_seconds = interval_ms // 1000
        self._hours_spin.setValue(total_seconds // 3600)
        self._minutes_spin.setValue((total_seconds % 3600) // 60)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        self._enabled_cb.toggled.connect(self._interval_frame.setEnabled)
        self._interval_frame.setEnabled(enabled)

    def result_values(self) -> tuple[bool, int]:
        """Return (enabled, interval_ms) chosen by the user."""
        enabled = self._enabled_cb.isChecked()
        hours = self._hours_spin.value()
        minutes = self._minutes_spin.value()
        interval_ms = max(30_000, (hours * 3600 + minutes * 60) * 1000)
        return enabled, interval_ms
