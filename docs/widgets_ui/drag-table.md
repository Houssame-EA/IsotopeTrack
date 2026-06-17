# `drag_table.py`

---

## Classes

### `DraggableTableWidget` *(extends `QTableWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialize the draggable table widget for calibration folders. |
| `dropEvent` | `(self, event: QDropEvent)` | Handle drop events for row reordering by swapping data between rows. |
| `dragEnterEvent` | `(self, event: QDragEnterEvent)` | Handle drag enter events to validate drag source. |
| `dragMoveEvent` | `(self, event: QDragMoveEvent)` | Handle drag move events during dragging operation. |
| `show_context_menu` | `(self, position)` | Display context menu with add and remove options. |
| `add_folder` | `(self)` | Add a new calibration folder to the table. |
| `remove_selected` | `(self)` | Remove the currently selected row from the table. |
| `update_with_folder_paths` | `(self, folders)` | Update the table with a list of folder paths. |
| `get_folder_path` | `(self, row)` | Get the folder path for a specific row. |
