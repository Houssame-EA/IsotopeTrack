# `bug_report_dialog.py`

tools/bug_report_dialog.py

Dialogs for anonymous error reporting: the "Report a Bug" form in the Help
menu and the one-time question asking whether automatic crash reports may be
sent. Both use the app palette and follow theme changes while open.

What is sent and how it is cleaned is defined in ``tools/crash_reporting.py``.

---

## Classes

### `_ThemedDialog` *(extends `QDialog`)*

QDialog that restyles itself whenever the app theme changes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_apply_theme` | `(self, *_args)` | Apply the current palette to the dialog. |

### `_SendWorker` *(extends `QThread`)*

Send one bug report off the UI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, parent=None)` |  |
| `run` | `(self)` |  |

### `BugReportDialog` *(extends `_ThemedDialog`)*

Form where the user describes a problem and sends it anonymously.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_on_text_changed` | `(self)` | Update the character counter and the Send button state. |
| `_set_status` | `(self, text, ok)` | Show a result line under the form. |
| `_send` | `(self)` | Send the report in the background. |
| `_on_sent` | `(self, event_id)` | Show the outcome and turn Cancel into Close on success. |
| `reject` | `(self)` | Wait for a running send before closing. |

### `CrashConsentDialog` *(extends `_ThemedDialog`)*

One-time question asking whether automatic crash reports may be sent.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_extra_qss` | `(p)` | Return styling for the widgets ``dialog_qss`` does not cover. |
| `ask_crash_consent_once` | `(parent=None)` | Show the consent question if the user has never answered it. |
| `show_bug_report_dialog` | `(parent=None)` | Open the Report a Bug form. |
