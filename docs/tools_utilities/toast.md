# `toast.py`

Non-blocking toast notifications for IsotopeTrack.

A lightweight, theme-aware replacement for transient ``QMessageBox.information``
popups. Toasts slide in from the top-right of the host window, stack
vertically, auto-dismiss, and never steal focus or block the UI.

Usage:
    self.toasts = ToastManager(self)          # once, on the main window
    self.toasts.show("Project saved", "success")

Levels: "success", "info", "warning", "error".

---

## Constants

| Name | Value |
|------|-------|
| `_LEVELS` | `{'success': ('fa6s.circle-check', 'success'), 'info': ('f…` |
| `_MARGIN` | `18` |
| `_GAP` | `10` |
| `_WIDTH` | `330` |

## Classes

### `Toast` *(extends `QFrame`)*

A single auto-dismissing notification card.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, host, message, level='info', duration=3500, on_done=None)` |  |
| `_apply_style` | `(self, accent)` |  |
| `appear` | `(self, target: QPoint)` | Slide in from the right + fade in to *target* (top-left in host). |
| `move_to` | `(self, target: QPoint)` | Animate a reposition (when toasts above are dismissed). |
| `dismiss` | `(self)` |  |
| `_finalize` | `(self)` |  |
| `enterEvent` | `(self, event)` |  |
| `leaveEvent` | `(self, event)` |  |

### `ToastManager` *(extends `QObject`)*

Owns the stack of toasts for one window and keeps them positioned.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, host: QWidget)` |  |
| `show` | `(self, message, level='info', duration=3500)` |  |
| `success` | `(self, message, duration=3500)` |  |
| `info` | `(self, message, duration=3500)` |  |
| `warning` | `(self, message, duration=4500)` |  |
| `error` | `(self, message, duration=6000)` |  |
| `_remove` | `(self, toast)` |  |
| `_target_for` | `(self, index)` |  |
| `_reflow` | `(self, animate_existing=False, appear=None)` |  |
| `eventFilter` | `(self, obj, event)` |  |
