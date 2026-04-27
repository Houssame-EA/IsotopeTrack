# `logging_utils.py`

---

## Constants

| Name | Value |
|------|-------|
| `LOG_DIR` | `_get_log_dir()` |
| `_MAX_GUI_ENTRIES` | `5000` |
| `_GUI_REFRESH_MS` | `80` |

## Classes

### `_LogSignaller` *(extends `QObject`)*

### `EnhancedQtLogHandler` *(extends `logging.Handler`)*

Routes Python log records to the GUI log window via Qt signals.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, log_window: 'EnhancedLogWindow | None' = None)` | Args: |
| `emit` | `(self, record: logging.LogRecord) → None` | Args: |

### `JsonlFileHandler` *(extends `logging.Handler`)*

Appends structured JSON-lines to a .jsonl log file.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, filepath: Path)` | Args: |
| `emit` | `(self, record: logging.LogRecord) → None` | Args: |
| `close` | `(self) → None` | Returns: |

### `_BufferHandler` *(extends `logging.Handler`)*

Fills a shared list with entry dicts until the GUI window takes over.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, buffer: list)` | Args: |
| `emit` | `(self, record: logging.LogRecord) → None` | Args: |

### `_LogStatsBar` *(extends `QFrame`)*

Live counters at the bottom of the log window.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget | None = None)` | Args: |
| `apply_theme` | `(self, palette = None) → None` | Args: |
| `increment` | `(self, key: str) → None` | Args: |
| `reset` | `(self) → None` | Returns: |
| `_tick` | `(self) → None` | Returns: |

### `_ContextPanel` *(extends `QFrame`)*

Formatted key-value display for a selected log entry's context.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget | None = None)` | Args: |
| `apply_theme` | `(self, palette = None) → None` | Args: |
| `show_entry` | `(self, entry: dict) → None` | Args: |
| `clear` | `(self) → None` | Returns: |
| `_copy_text` | `(self) → None` | Returns: |

### `EnhancedLogWindow` *(extends `QDialog`)*

Full-featured log viewer with dark / light theme support.

Key features
------------
* Theme-aware colour coding — updates live when the app theme changes
* Level-based colour coding with background tints (dark & light)
* DEBUG lines show module / function / line number
* ERROR / CRITICAL lines surface exception traces in the context panel
* Rate-limited GUI refresh — no freeze on log bursts
* Jump-to-next-error navigation
* Copy selected lines to clipboard
* Save as .txt or export as .jsonl
* Live statistics bar with session timer
* All entries are preserved when the window is hidden / closed

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget | None = None)` | Args: |
| `_setup_ui` | `(self) → None` | Returns: |
| `_muted_lbl` | `(text: str) → QLabel` | Args: |
| `_vline` | `() → QFrame` | Returns: |
| `_flat_btn` | `(icon_name: str, color: str, tooltip: str) → QPushButton` | Args: |
| `_on_theme_changed` | `(self, name: str) → None` | Called by ThemeManager.themeChanged — re-theme and re-render. |
| `_toggle_theme` | `(self) → None` | Returns: |
| `apply_theme` | `(self, palette = None) → None` | Apply dark or light stylesheet to every component. |
| `_receive_entry` | `(self, entry: dict) → None` | Buffer incoming entries; actual rendering is done by rate-limiter. |
| `_flush_pending` | `(self) → None` | Batch-render all buffered entries at most every _GUI_REFRESH_MS. |
| `_render_entry` | `(self, entry: dict, cursor: QTextCursor) → None` | Append one formatted entry at *cursor*. |
| `_full_render` | `(self) → None` | Re-render all entries from scratch (used after trim or theme change). |
| `_update_stats` | `(self, entry: dict) → None` | Args: |
| `_update_module_filter` | `(self, entry: dict) → None` | Args: |
| `_apply_filter` | `(self) → None` | Returns: |
| `_on_cursor_moved` | `(self) → None` | Returns: |
| `_jump_to_next_error` | `(self) → None` | Returns: |
| `_on_autoscroll_toggled` | `(self, checked: bool) → None` | Args: |
| `_on_wrap_toggled` | `(self, checked: bool) → None` | Args: |
| `_copy_selected` | `(self) → None` | Returns: |
| `_clear` | `(self) → None` | Returns: |
| `_save_txt` | `(self) → None` | Returns: |
| `_export_jsonl` | `(self) → None` | Returns: |
| `closeEvent` | `(self, event) → None` | Hide instead of destroying so the full log history is always kept. |
| `add_log_message` | `(self, level: str, message: str, timestamp: str, context: dict | None ` | Compatibility shim — prefer connecting to _receive_entry via signal. |

### `UserActionLogger`

Tracks user interactions and analysis workflow steps.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, logger: logging.Logger)` | Args: |
| `log_action` | `(self, action_type: str, description: str, context: dict | None = None` | Args: |
| `log_click` | `(self, widget_name: str, widget_type: str = '', extra: dict | None = N` | Args: |
| `log_menu_action` | `(self, menu: str, action: str) → None` | Args: |
| `log_dialog_open` | `(self, name: str, kind: str = '') → None` | Args: |
| `log_file_operation` | `(self, op: str, path: str | Path, success: bool = True) → None` | Args: |
| `log_data_operation` | `(self, op: str, details: dict | None = None) → None` | Args: |
| `log_analysis_step` | `(self, step: str, parameters: dict | None = None, results: dict | None` | Args: |

### `EnhancedLoggingManager`

Creates and manages the root logger, file handlers, and the GUI log window.

Pre-window buffer
-----------------
All log records emitted before ``create_log_window`` is called are
stored in ``_pre_window_buffer``.  When the window is first opened the
buffer is replayed so no startup messages are ever lost.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self) → None` | Returns: |
| `_setup_logging` | `(self) → None` | Returns: |
| `_install_exception_hook` | `(self) → None` | Returns: |
| `_prune_old_logs` | `(keep: int = 50) → None` | Args: |
| `get_logger` | `(self, name: str | None = None) → logging.Logger` | Args: |
| `get_user_action_logger` | `(self) → UserActionLogger` | Returns: |
| `create_log_window` | `(self, parent: QWidget | None = None) → EnhancedLogWindow` | Args: |
| `show_log_window` | `(self, parent: QWidget | None = None) → EnhancedLogWindow` | Args: |

## Functions

### `_get_log_dir`

```python
def _get_log_dir() → Path
```

Return a writable log directory for all platforms and packaging modes.

**Returns:**

- `Path: Result of the operation.`

### `_mode`

```python
def _mode(palette = None) → str
```

Return 'dark' or 'light' given a Palette object or the live ThemeManager.

**Args:**

- `palette (Any): Colour palette object.`

**Returns:**

- `str: Result of the operation.`

### `_build_entry`

```python
def _build_entry(record: logging.LogRecord) → dict
```

Convert a LogRecord to a rich entry dict used by the GUI and JSONL.

**Args:**

- `record (logging.LogRecord): The record.`

**Returns:**

- `dict: Result of the operation.`

### `log_user_action`

```python
def log_user_action(action_type: str, description: str | None = None)
```

Decorator: automatically log a user action when the decorated method is called.

Usage::

@log_user_action('CLICK', 'Detect Peaks button')
def detect_particles(self): ...

**Args:**

- `action_type (str): The action type.`
- `description (str | None): The description.`

**Returns:**

- `object: Result of the operation.`

### `log_performance`

```python
def log_performance(threshold_ms: float = 0)
```

Decorator: log wall-clock execution time.

Only logs if elapsed time >= *threshold_ms* (default 0 = always log).

Usage::

@log_performance(threshold_ms=200)
def detect_particles(self): ...

**Args:**

- `threshold_ms (float): The threshold ms.`

**Returns:**

- `object: Result of the operation.`
