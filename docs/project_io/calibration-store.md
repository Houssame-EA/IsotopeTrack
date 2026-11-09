# `calibration_store.py`

Storage of the sensitivity (ionic) calibration session inside a project file.

The window state (concentration table, fits, manual slopes, exclusions) goes
into the project metadata. The signals of every calibration standard are
written as one compressed ``ionic/<n>.npz`` entry each, so the calibration can
be reopened and changed without the original standard folders.

The state is captured on the GUI thread (``refresh_calibration_snapshot``)
before a save starts, because the save itself runs on a worker thread and must
not touch Qt widgets.

---

## Constants

| Name | Value |
|------|-------|
| `IONIC_DIR` | `'ionic'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `ionic_entry` | `(index)` | Return the zip entry path of one calibration standard. |
| `ionic_fingerprint` | `(data, folders)` | Return a cheap identity of the standards held in memory. |
| `refresh_calibration_snapshot` | `(mw)` | Capture the sensitivity calibration state on the GUI thread. |
| `snapshot_state` | `(mw)` | Return the captured sensitivity calibration state, or None. |
| `te_snapshot_state` | `(mw)` | Return the captured transport efficiency state, or None. |
| `write_ionic_data` | `(zf, mw, old_source)` | Write the signals of the calibration standards into a project being saved. |
| `read_ionic_data` | `(project_path, entries, state)` | Read the calibration standards back from a project file. |
