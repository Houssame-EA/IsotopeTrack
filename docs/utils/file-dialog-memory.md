# `file_dialog_memory.py`

Cross-session folder memory for every file dialog in the application.

Wraps the static ``QFileDialog`` convenience methods so all open, save,
and folder-selection dialogs start in the folder the user last picked a
file from, persisted across restarts. On first use, or when the
remembered folder no longer exists, dialogs start on the Desktop. A
caller that passes an explicit absolute location keeps it; a caller that
passes only a suggested file name gets it placed inside the remembered
folder.

---

## Constants

| Name | Value |
|------|-------|
| `_SETTINGS_KEY` | `'files/last_directory'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_last_directory` | `()` | Return the remembered folder, falling back to the Desktop, then home. |
| `save_last_directory` | `(path)` | Persist *path* as the folder future file dialogs should start in. |
| `_resolve_start_dir` | `(requested)` | Combine the caller's requested location with the remembered folder. |
| `install_file_dialog_memory` | `()` | Wrap the static ``QFileDialog`` methods with folder memory. Safe to call more than once. |
