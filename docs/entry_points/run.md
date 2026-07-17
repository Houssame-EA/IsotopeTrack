# `Run.py`

---

## Classes

### `IsotopeTrackApplication` *(extends `QApplication`)*

QApplication that handles the macOS 'open document' event.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, argv)` |  |
| `event` | `(self, e)` |  |
| `_dispatch_open` | `(self, path)` | Load ``path`` into a visible window. Returns False if none exists yet. |
| `flush_pending_opens` | `(self)` | Load any open requests that arrived before a window existed. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `resource_path` | `(relative_path)` | Get absolute path to resource — works for dev and PyInstaller. |
