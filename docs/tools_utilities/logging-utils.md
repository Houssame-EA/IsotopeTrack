# `logging_utils.py`

---

## Constants

| Name | Value |
|------|-------|
| `LOG_DIR` | `_get_log_dir()` |
| `_MAX_GUI_ENTRIES` | `5000` |
| `_GUI_REFRESH_MS` | `80` |

## Classes

### `_ContextFilter` *(extends `logging.Filter`)*

Attaches the active domain context to every log record.

| Method | Signature | Description |
|--------|-----------|-------------|
| `filter` | `(self, record: logging.LogRecord) → bool` | Set record.context and record.context_str from the active context. |

### `_LogSignaller` *(extends `QObject`)*

### `EnhancedQtLogHandler` *(extends `logging.Handler`)*

Routes Python log records to the GUI log window via Qt signals.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, log_window: 'EnhancedLogWindow \| None'=None)` |  |
| `emit` | `(self, record: logging.LogRecord) → None` |  |

### `JsonlFileHandler` *(extends `logging.Handler`)*

Appends structured JSON-lines to a .jsonl log file.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, filepath: Path)` |  |
| `emit` | `(self, record: logging.LogRecord) → None` |  |
| `close` | `(self) → None` |  |

### `_BufferHandler` *(extends `logging.Handler`)*

Fills a shared list with entry dicts until the GUI window takes over.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, buffer: list)` |  |
| `emit` | `(self, record: logging.LogRecord) → None` |  |

### `_LogStatsBar` *(extends `QFrame`)*

Live counters at the bottom of the log window.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget \| None=None)` |  |
| `apply_theme` | `(self, palette=None) → None` |  |
| `increment` | `(self, key: str) → None` |  |
| `reset` | `(self) → None` |  |
| `_tick` | `(self) → None` |  |

### `_ContextPanel` *(extends `QFrame`)*

Formatted key-value display for a selected log entry's context.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget \| None=None)` |  |
| `apply_theme` | `(self, palette=None) → None` |  |
| `show_entry` | `(self, entry: dict) → None` |  |
| `clear` | `(self) → None` |  |
| `_copy_text` | `(self) → None` |  |

### `EnhancedLogWindow` *(extends `QDialog`)*

Full-featured log viewer with dark / light theme support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent: QWidget \| None=None)` |  |
| `_setup_ui` | `(self) → None` |  |
| `_muted_lbl` | `(text: str) → QLabel` |  |
| `_vline` | `() → QFrame` |  |
| `_flat_btn` | `(icon_name: str, color: str, tooltip: str) → QPushButton` |  |
| `_on_theme_changed` | `(self, name: str) → None` | Called by ThemeManager.themeChanged — re-theme and re-render. |
| `_toggle_theme` | `(self) → None` |  |
| `apply_theme` | `(self, palette=None) → None` | Apply dark or light stylesheet to every component. |
| `_receive_entry` | `(self, entry: dict) → None` | Buffer incoming entries; actual rendering is done by rate-limiter. |
| `_flush_pending` | `(self) → None` | Batch-render all buffered entries at most every _GUI_REFRESH_MS. |
| `_render_entry` | `(self, entry: dict, cursor: QTextCursor) → None` | Append one formatted entry at *cursor*. |
| `_full_render` | `(self) → None` | Re-render all entries from scratch (used after trim or theme change). |
| `_update_stats` | `(self, entry: dict) → None` |  |
| `_update_module_filter` | `(self, entry: dict) → None` |  |
| `_apply_filter` | `(self) → None` |  |
| `_on_cursor_moved` | `(self) → None` |  |
| `_jump_to_next_error` | `(self) → None` |  |
| `_on_autoscroll_toggled` | `(self, checked: bool) → None` |  |
| `_on_wrap_toggled` | `(self, checked: bool) → None` |  |
| `_copy_selected` | `(self) → None` |  |
| `_clear` | `(self) → None` |  |
| `_save_txt` | `(self) → None` |  |
| `_export_jsonl` | `(self) → None` |  |
| `closeEvent` | `(self, event) → None` | Hide instead of destroying so the full log history is always kept. |
| `add_log_message` | `(self, level: str, message: str, timestamp: str, context: dict \| None=` | Compatibility shim — prefer connecting to _receive_entry via signal. |

### `UserActionLogger`

Tracks user interactions and analysis workflow steps.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, logger: logging.Logger)` |  |
| `log_action` | `(self, action_type: str, description: str, context: dict \| None=None) ` |  |
| `log_click` | `(self, widget_name: str, widget_type: str='', extra: dict \| None=None)` |  |
| `log_menu_action` | `(self, menu: str, action: str) → None` |  |
| `log_dialog_open` | `(self, name: str, kind: str='') → None` |  |
| `log_file_operation` | `(self, op: str, path: str \| Path, success: bool=True) → None` |  |
| `log_data_operation` | `(self, op: str, details: dict \| None=None) → None` |  |
| `log_analysis_step` | `(self, step: str, parameters: dict \| None=None, results: dict \| None=N` |  |

### `EnhancedLoggingManager`

Creates and manages the root logger, file handlers, and the GUI log window.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self) → None` |  |
| `_setup_logging` | `(self) → None` |  |
| `_install_exception_hook` | `(self) → None` |  |
| `_prune_old_logs` | `(keep: int=50) → None` |  |
| `get_logger` | `(self, name: str \| None=None) → logging.Logger` |  |
| `get_user_action_logger` | `(self) → UserActionLogger` |  |
| `_log_window_is_alive` | `(self) → bool` | Return whether the cached log window exists and its Qt object is still valid. |
| `_discard_log_window` | `(self) → None` | Drop the cached log window and detach its Qt log handler. |
| `create_log_window` | `(self, parent: QWidget \| None=None) → EnhancedLogWindow` | Return the shared log window, rebuilding it if it was destroyed. |
| `show_log_window` | `(self, parent: QWidget \| None=None) → EnhancedLogWindow` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `push_log_context` | `(**fields) → contextvars.Token` | Merge domain fields into the active logging context. |
| `reset_log_context` | `(token: contextvars.Token) → None` | Restore the logging context to the state captured by a push token. |
| `log_context` | `(**fields)` | Stamp domain context onto every log record emitted inside the block. |
| `set_current_window` | `(window_id) → None` | Set or clear the window identifier stamped on every log record. |
| `_get_log_dir` | `() → Path` | Return a writable log directory for all platforms and packaging modes. |
| `_mode` | `(palette=None) → str` | Return 'dark' or 'light' given a Palette object or the live ThemeManager. |
| `_build_entry` | `(record: logging.LogRecord) → dict` | Convert a LogRecord to a rich entry dict used by the GUI and JSONL. |
| `log_user_action` | `(action_type: str, description: str \| None=None)` | Decorator: automatically log a user action when the decorated method is called. |
| `log_performance` | `(threshold_ms: float=0)` | Decorator: log wall-clock execution time. |
