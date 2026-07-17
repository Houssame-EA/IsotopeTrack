# `file_dialog_memory.py`

Cross-session folder memory for every file dialog in the application.

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
