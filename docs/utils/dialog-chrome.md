# `dialog_chrome.py`

Maximise buttons and remembered sizes for every dialog in the application.

Windows gives a ``QDialog`` only a close button, so a dialog holding a figure
can only be enlarged by dragging its corners — for every dialog, every time it
is opened. macOS supplies a zoom button for free, which is why the problem is
invisible there. This module adds the maximise button on both platforms and
remembers each dialog's size between openings, so the resizing is done once
rather than on every visit.

It works through a single application-wide event filter rather than a change to
each of the dialog classes. There are more than eighty of them, a hand-edited
list would fall out of date the moment one was added, and the behaviour wanted
here is uniform. The filter acts on ``Polish``, which Qt delivers while a widget
is being shown but before its native window exists, so the flags are in place
from the start and the window is never created twice or made to flicker.

Not every dialog should be touched. Qt's own standard dialogs — message boxes
above all, of which this application shows several hundred — are sized by their
contents and look wrong with a maximise button. Frameless and tool windows have
deliberately chosen chrome, and a dialog given a fixed size is asking not to be
resized at all. All of these are left alone.

---

## Constants

| Name | Value |
|------|-------|
| `_SETTINGS_GROUP` | `'dialogs'` |
| `_APPLIED_PROPERTY` | `'_itk_chrome_applied'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_standard_dialog_types` | `()` | Return the Qt dialog classes that keep their own chrome. |
| `_is_eligible` | `(widget)` | Report whether a widget should be given a maximise button. |
| `_settings_key` | `(widget)` | Return the settings key a dialog's geometry is stored under. |
| `_on_screen` | `(widget)` | Report whether a dialog's frame lands on a currently attached screen. |
| `_apply_chrome` | `(widget)` | Add the maximise button and restore the remembered size. |
| `_remember_geometry` | `(widget)` | Store a dialog's size and position for the next time it is opened. |
| `install_dialog_chrome` | `(app)` | Give every application dialog a maximise button and a remembered size. |
