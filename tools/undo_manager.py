"""In-session undo/redo for IsotopeTrack's editable analysis state.

Captures the user-editable inputs — isotope selection, per-element detection
parameters (including parameters-table edits), calibration values, dilution,
mass-fraction and density settings — as small pickled snapshots, so Ctrl/Cmd+Z
steps back through setting changes and Ctrl/Cmd+Shift+Z steps forward again.

The loaded raw signal and the computed particle results are deliberately not
captured, so snapshots stay in the kilobyte range and undo is fast even with a
multi-gigabyte dataset open. After an undo the inputs revert and the UI
refreshes; re-run detection to recompute results from the restored parameters.

Changes are detected by polling rather than by instrumenting every mutation
site, so no other code needs to know undo exists. The history resets when the
loaded sample set changes, matching the rule that whole-sample changes are not
undoable.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mainwindow import MainWindow

import pickle
import logging

from PySide6.QtCore import QObject, QTimer

_itk_log = logging.getLogger("IsotopeTrack.undo")

_MAIN_WINDOW_FIELDS = (
    'selected_isotopes',
    'sample_parameters',
    'isotope_method_preferences',
    'element_thresholds',
    'element_limits',
    'calibration_results',
    'average_transport_rate',
    'selected_transport_rate_methods',
    'transport_rate_methods',
    'sample_dilutions',
    'overlap_threshold_percentage',
    '_global_sigma',
    '_sigma_mode',
    'detection_states',
    'saturation_filter_enabled',
)
_MASS_FRACTION_SERVICE_FIELDS = {
    'element_mass_fractions',
    'element_densities',
    'element_molecular_weights',
    'sample_mass_fractions',
    'sample_densities',
    'sample_molecular_weights',
}

MAX_DEPTH = 40
POLL_MS = 1200


class UndoManager(QObject):
    """Polling, snapshot-based undo/redo for one ``MainWindow``."""

    def __init__(self, main_window: MainWindow):
        """Create the manager and its change-detection timer."""
        super().__init__(main_window)
        self.mw: MainWindow = main_window
        self._stack = []
        self._index = -1
        self._restoring = False
        self._sample_sig = None

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._maybe_record)

    def start(self):
        """Begin watching for input changes."""
        self._timer.start()

    def stop(self):
        """Stop watching for input changes."""
        self._timer.stop()

    def _flush_parameters(self):
        """Commit any pending parameters-table edit into ``sample_parameters``."""
        flush = getattr(self.mw, 'save_current_parameters', None)
        if callable(flush):
            try:
                flush()
            except Exception:
                _itk_log.debug("Parameter flush before undo snapshot skipped")

    def _snapshot(self):
        """Return the current editable inputs pickled, or None on failure."""
        state = {f: getattr(self.mw, f, None) for f in _MAIN_WINDOW_FIELDS}
        for field in _MASS_FRACTION_SERVICE_FIELDS:
            state[field] = getattr(self.mw.mass_fraction_service, field, None)
        try:
            return pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            _itk_log.exception("Undo snapshot failed")
            return None

    def _has_data(self):
        """True when at least one sample is loaded."""
        return bool(getattr(self.mw, 'data_by_sample', None))

    def _current_sample_sig(self):
        """Signature of the loaded sample set."""
        d = getattr(self.mw, 'data_by_sample', None) or {}
        return tuple(sorted(d.keys()))

    def _maybe_record(self):
        """Push a new undo step when the inputs changed since the last one."""
        if self._restoring or not self._has_data():
            return
        self._flush_parameters()
        sig = self._current_sample_sig()
        if sig != self._sample_sig:
            self._sample_sig = sig
            self._stack = []
            self._index = -1
        snap = self._snapshot()
        if snap is None:
            return
        if self._index >= 0 and self._stack[self._index] == snap:
            return
        del self._stack[self._index + 1:]
        self._stack.append(snap)
        if len(self._stack) > MAX_DEPTH:
            self._stack.pop(0)
        self._index = len(self._stack) - 1
        self._update_actions()

    def can_undo(self):
        """True when there is an earlier state to return to."""
        return self._index > 0

    def can_redo(self):
        """True when there is a later state to move forward to."""
        return -1 < self._index < len(self._stack) - 1

    def undo(self):
        """Step back to the previous editable-input state."""
        self._maybe_record()
        if not self.can_undo():
            self._notify("Nothing to undo")
            return
        self._index -= 1
        self._apply(self._stack[self._index])
        self._notify("Undo")

    def redo(self):
        """Step forward again after an undo."""
        if not self.can_redo():
            self._notify("Nothing to redo")
            return
        self._index += 1
        self._apply(self._stack[self._index])
        self._notify("Redo")

    def _apply(self, snap):
        """Restore a snapshot's inputs and refresh the UI to match."""
        try:
            state = pickle.loads(snap)
        except Exception:
            _itk_log.exception("Undo restore failed")
            return
        self._restoring = True
        try:
            for f in _MAIN_WINDOW_FIELDS:
                setattr(self.mw, f, state.get(f))
            for f in _MASS_FRACTION_SERVICE_FIELDS:
                setattr(self.mw.mass_fraction_service, f, state.get(f))
            self._refresh_ui()
            self.mw.unsaved_changes = True
        finally:
            self._restoring = False
        self._update_actions()

    def _refresh_ui(self):
        """Rebuild the input-facing UI from restored state without side effects."""
        mw = self.mw
        try:
            if hasattr(mw, 'sigma_spinbox'):
                mw.sigma_spinbox.blockSignals(True)
                mw.sigma_spinbox.setValue(getattr(mw, '_global_sigma', 0.55))
                mw.sigma_spinbox.blockSignals(False)
            if hasattr(mw, '_build_element_lookup_cache'):
                mw._build_element_lookup_cache()
            if getattr(mw, 'periodic_table_widget', None) and getattr(mw, 'selected_isotopes', None):
                mw._update_periodic_table_selections()
            if hasattr(mw, 'update_sample_table'):
                mw.update_sample_table()
            cur = getattr(mw, 'current_sample', None)
            tbl = getattr(mw, 'sample_table', None)
            if cur and tbl is not None and tbl.rowCount() > 0:
                for row in range(tbl.rowCount()):
                    it = tbl.item(row, 0)
                    if it and it.text() == cur:
                        tbl.selectRow(row)
                        mw.on_sample_selected(it)
                        break
            if hasattr(mw, 'update_calibration_display'):
                mw.update_calibration_display()
        except Exception:
            _itk_log.exception("Undo UI refresh failed")

    def _notify(self, msg):
        """Show a brief toast for the undo/redo outcome if supported."""
        try:
            notify = getattr(self.mw, 'notify', None)
            if callable(notify):
                notify(msg, "info", 1200)
        except Exception:
            _itk_log.debug("Undo toast skipped")

    def _update_actions(self):
        """Keep the Edit-menu Undo/Redo actions' enabled state in sync."""
        try:
            ua = getattr(self.mw, '_undo_action', None)
            ra = getattr(self.mw, '_redo_action', None)
            if ua is not None:
                ua.setEnabled(self.can_undo())
            if ra is not None:
                ra.setEnabled(self.can_redo())
        except RuntimeError:
            pass
