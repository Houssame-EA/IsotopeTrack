# `pyqtgraph_patches.py`

Runtime compatibility patches for third-party libraries.

---

## Classes

### `_NoOpHeaderItem`

Stand-in header item used when the real one is mis-wrapped.

| Method | Signature | Description |
|--------|-----------|-------------|
| `setText` | `(self, column, text)` | Ignore the header text assignment; the header is hidden anyway. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `apply_pyqtgraph_patches` | `()` | Install all pyqtgraph compatibility patches. Safe to call more than once. |
| `_export_dialog_stylesheet` | `()` | Return the export-dialog stylesheet built from the active theme palette. |
| `_install_theme_binding` | `(form)` | Apply the themed stylesheet to *form* and keep it in sync with theme changes. |
| `_patch_file_dialog` | `()` | Theme pyqtgraph's non-native file save dialogs so they follow the app palette. |
| `_patch_exporter_save_directory` | `()` | Start export save dialogs in the app-wide remembered folder, or the Desktop on first use. |
| `_patch_export_dialog_template` | `()` | Wrap the export dialog's ``setupUi`` so a broken ``headerItem`` binding cannot crash it and the dialog follows the app theme. |
