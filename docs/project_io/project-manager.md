# `project_manager.py`

---

## Classes

### `SaveProjectThread` *(extends `QThread`)*

Run the heavy project-save work off the UI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, filepath, main_window)` | Store the destination path and the window whose state is saved. |
| `run` | `(self) → None` | Write the project, emitting progress and a final success/failure signal. |

### `ProjectManager`

Handles saving and loading of IsotopeTrack project files.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window)` | Initialize the ProjectManager with a reference to the main window. |
| `_set_file_icon_cross_platform` | `(self, file_path)` | Set custom icon for the saved project file on both Windows and macOS. |
| `_set_icon_macos` | `(self, file_path)` | Set custom icon for macOS using native tools. |
| `_set_icon_windows` | `(self, file_path)` | Set custom icon for Windows by registering file type. |
| `_set_icon_linux` | `(self, file_path)` | Set custom icon for Linux. |
| `save_project` | `(self, on_complete=None, blocking=False, save_as=False)` | Save the current project state to a compressed file. |
| `_on_save_progress` | `(self, pct, msg)` | Update the progress bar and status label during a threaded save. |
| `_finalize_save_success` | `(self, filepath)` | Apply the post-save UI updates after a successful write. |
| `_on_save_succeeded` | `(self, filepath)` | Handle the worker thread's success signal on the UI thread. |
| `_on_save_failed` | `(self, message)` | Handle the worker thread's failure signal on the UI thread. |
| `_save_blocking` | `(self, filepath, on_complete)` | Save synchronously on the calling thread and return the result. |
| `load_project` | `(self, filepath=None)` | Load a previously saved project. |
| `_finalize_load` | `(self)` | Common post-load setup for both v1 and v2 formats. |
| `_migrate_sample_parameters` | `(self)` | Ensure all per-element parameter dicts contain every field that the |
| `_collect_project_data` | `(self, canvas_state)` | Collect all project data for saving. |
| `_restore_project_data` | `(self, project_data)` | Restore project data from loaded file. |
| `_serialize_canvas_state` | `(self)` | Serialize the current canvas state for saving. |
| `_serialize_node_config` | `(self, node, node_data)` | Serialize node-specific configuration. |
| `_serialize_batch_output` | `(self, node, node_data)` | Bake a Batch Windows node's combined output into its saved data. |
| `_deserialize_canvas_state` | `(self, canvas_state)` | Recreate the canvas state from saved data. |
| `_deserialize_node_config` | `(self, workflow_node, node_data)` | Restore node configuration from saved data. |
| `_reset_data_structures` | `(self)` | Reset all data structures before loading a saved project. |
| `_update_ui_after_load` | `(self)` | Update UI components after loading project. |
| `_check_version_compatibility` | `(self, file_version)` | Check if the file version is compatible with current version. |
| `get_project_info` | `(self, file_path)` | Get basic information about a project file without fully loading it. |
