# `Run.py`

---

## Classes

### `IsotopeTrackApplication` *(extends `QApplication`)*

QApplication that handles the macOS 'open document' event.

When a .itproj file is double-clicked in Finder while IsotopeTrack is already
running, macOS delivers a QFileOpenEvent rather than a command-line argument.
This routes that file to an open window — or queues it until one exists. A
cold launch is handled separately by ``argv_emulation`` plus the CLI parser.

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
