# `undo_manager.py`

In-session undo/redo for IsotopeTrack's editable analysis state.

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

---

## Constants

| Name | Value |
|------|-------|
| `_FIELDS` | `('selected_isotopes', 'sample_parameters', 'isotope_metho…` |
| `MAX_DEPTH` | `40` |
| `POLL_MS` | `1200` |

## Classes

### `UndoManager` *(extends `QObject`)*

Polling, snapshot-based undo/redo for one ``MainWindow``.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window)` | Create the manager and its change-detection timer. |
| `start` | `(self)` | Begin watching for input changes. |
| `stop` | `(self)` | Stop watching for input changes. |
| `_flush_parameters` | `(self)` | Commit any pending parameters-table edit into ``sample_parameters``. |
| `_snapshot` | `(self)` | Return the current editable inputs pickled, or None on failure. |
| `_has_data` | `(self)` | True when at least one sample is loaded. |
| `_current_sample_sig` | `(self)` | Signature of the loaded sample set. |
| `_maybe_record` | `(self)` | Push a new undo step when the inputs changed since the last one. |
| `can_undo` | `(self)` | True when there is an earlier state to return to. |
| `can_redo` | `(self)` | True when there is a later state to move forward to. |
| `undo` | `(self)` | Step back to the previous editable-input state. |
| `redo` | `(self)` | Step forward again after an undo. |
| `_apply` | `(self, snap)` | Restore a snapshot's inputs and refresh the UI to match. |
| `_refresh_ui` | `(self)` | Rebuild the input-facing UI from restored state without side effects. |
| `_notify` | `(self, msg)` | Show a brief toast for the undo/redo outcome if supported. |
| `_update_actions` | `(self)` | Keep the Edit-menu Undo/Redo actions' enabled state in sync. |
