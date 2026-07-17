# `autosave.py`

Autosave and crash recovery for IsotopeTrack.

---

## Constants

| Name | Value |
|------|-------|
| `RECOVERY_GLOB` | `'recovery_*.itproj'` |
| `POLL_MS` | `1000` |
| `DEBOUNCE_MS` | `4000` |
| `SAFETY_MS` | `180000` |
| `_FINGERPRINT_FIELDS` | `('selected_isotopes', 'sample_parameters', 'isotope_metho…` |

## Classes

### `AutosaveManager` *(extends `QObject`)*

Owns the autosave timer and the recovery files for one MainWindow.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window, interval_ms: int \| None=None)` | Create the manager and its poll timer (disabled if autosave is off). |
| `_now_ms` | `() → int` | Monotonic millisecond clock for debounce/safety timing. |
| `start` | `(self)` | Begin the autosave poll timer (no-op if autosave is disabled). |
| `stop` | `(self)` | Stop the timer and wait for any in-flight heavy snapshot write. |
| `_heavy_path` | `(self) → Path` | Path of this window's heavy recovery file (raw arrays). |
| `_light_path` | `(self) → Path` | Path of this window's light recovery file (metadata + particles). |
| `_has_data` | `(self) → bool` |  |
| `_sample_sig` | `(self)` | Signature of the loaded sample set; a change forces a heavy rewrite. |
| `_flush_parameters` | `(self)` | Commit any pending parameters-table edit into ``sample_parameters``. |
| `_fingerprint` | `(self) → bytes` | Cheap signature of the editable inputs and result counts. |
| `_poll` | `(self)` | Decide, on each tick, whether enough has changed and settled to save. |
| `_write` | `(self, fp)` | Write a heavy snapshot if the sample set changed, else a light one. |
| `_write_heavy` | `(self, sig)` | Write the full ``.itproj`` (raw arrays included) on a background thread. |
| `_on_heavy_ok` | `(self, sig)` | Finalize a heavy write, then write the matching light file. |
| `_on_heavy_fail` | `(self, message)` | Record a failed heavy write so the next poll can retry. |
| `_write_light` | `(self) → bool` | Atomically write the small light snapshot (metadata + particle data). |
| `_toast` | `(self)` | Show the brief 'Autosaved' confirmation if the window supports it. |
| `clear` | `(self)` | Delete this window's recovery files (on a clean save or clean exit). |
| `apply_light_overlay` | `(mw, heavy_path)` | Overlay the newer light snapshot onto a just-loaded heavy recovery file. |
| `find_recovery_files` | `()` | Heavy recovery files from crashed (not currently-running) sessions. |
| `discard_recovery_files` | `(paths)` | Delete the given heavy recovery files and their light companions. |
| `reconfigure` | `(self, enabled: bool, interval_ms: int)` | Apply new settings at runtime and persist to QSettings. |

### `AutoSaveSettingsDialog` *(extends `QDialog`)*

Modal dialog for configuring auto-save enable/disable and interval.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, enabled: bool, interval_ms: int, parent=None)` |  |
| `result_values` | `(self) → tuple[bool, int]` | Return (enabled, interval_ms) chosen by the user. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `recovery_dir` | `() → Path` | Return (creating if needed) the per-user folder holding recovery files. |
| `_pid_alive` | `(pid: int) → bool` | Best-effort check whether ``pid`` belongs to a still-running process. |
