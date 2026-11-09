# `te_store.py`

Storage of the transport efficiency (TE) calibration inside a project file.

The state of the TE window goes into the project metadata. A TE calibration
uses a single element, so only the signal of the selected isotope of every TE
sample is written, under ``te/<method>/<n>/<mass>.npy``. Choosing another
element later reads it from the raw data again.

When a project is saved, each sample's signal is taken from memory; a sample
whose signal is not in memory is copied from the open project when it is
stored there.

---

## Constants

| Name | Value |
|------|-------|
| `TE_DIR` | `'te'` |
| `NUMBER` | `'number'` |
| `MASS` | `'mass'` |
| `MASS_IONIC` | `'mass_ionic'` |
| `TE_MAX_MASS_DIFF` | `1.0` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_channel_entry` | `(sample_dir, mass)` | Return the entry path of one stored mass. |
| `_npy_bytes` | `(arr)` | Serialize an array to ``.npy`` bytes. |
| `picklable_dict` | `(data)` | Return a copy of a dict keeping only the values that can be pickled. |
| `_next_free_dir` | `(method, used)` | Return an unused sample folder name for a method. |
| `write_te_samples` | `(zf, method, folders, memory_arrays, old_source, old_index)` | Write the signal of the selected isotope of the TE samples of one method. |
| `read_te_channel` | `(project_path, info, target_mass, max_diff=TE_MAX_MASS_DIFF)` | Read the stored mass closest to a target for one TE sample. |
| `_te_window` | `(mw)` | Return the TE window of the main window, or None. |
| `te_widget` | `(mw, label)` | Return one method widget of the TE window, or None. |
| `capture_te_snapshot` | `(mw)` | Capture the TE window state on the GUI thread. |
| `write_te_data` | `(zf, mw, old_source)` | Write the TE samples of every stored method into a project being saved. |
| `apply_te_store_after_save` | `(mw, project_path)` | Point the TE widgets at the project just saved, on the GUI thread. |
