"""Maximise buttons and remembered sizes for every dialog in the application.

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
"""

import logging

_itk_log = logging.getLogger("IsotopeTrack.utils.dialog_chrome")

_SETTINGS_GROUP = "dialogs"
_APPLIED_PROPERTY = "_itk_chrome_applied"
_installed = False
_filter = None


def _standard_dialog_types():
    """Return the Qt dialog classes that keep their own chrome.

    Returns:
        tuple: Classes to leave untouched.
    """
    from PySide6.QtWidgets import (QColorDialog, QErrorMessage, QFileDialog,
                                   QFontDialog, QInputDialog, QMessageBox,
                                   QProgressDialog)
    return (QMessageBox, QInputDialog, QFileDialog, QColorDialog, QFontDialog,
            QProgressDialog, QErrorMessage)


def _is_eligible(widget):
    """Report whether a widget should be given a maximise button.

    Args:
        widget (QWidget): The candidate, normally a dialog being shown.

    Returns:
        bool: True when the dialog is one of the application's own resizable
        dialogs.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog

    if not isinstance(widget, QDialog):
        return False
    if isinstance(widget, _standard_dialog_types()):
        return False

    flags = widget.windowFlags()
    if flags & Qt.WindowType.FramelessWindowHint:
        return False
    if (flags & Qt.WindowType.Tool) == Qt.WindowType.Tool:
        return False
    if widget.minimumSize() == widget.maximumSize():
        return False
    return True


def _settings_key(widget):
    """Return the settings key a dialog's geometry is stored under.

    Keyed by class name so each dialog remembers its own size independently,
    and so the key survives the object being recreated on every opening.

    Args:
        widget (QWidget): The dialog.

    Returns:
        str: The key.
    """
    return "%s/%s/geometry" % (_SETTINGS_GROUP, type(widget).__name__)


def _on_screen(widget):
    """Report whether a dialog's frame lands on a currently attached screen.

    Restored geometry can point at a monitor that has since been unplugged, or
    at a resolution that no longer exists, which would open the dialog off the
    edge of the desktop where it cannot be reached.

    Args:
        widget (QWidget): The dialog, already moved to the restored geometry.

    Returns:
        bool: True when part of the frame is visible on some screen.
    """
    from PySide6.QtWidgets import QApplication

    frame = widget.frameGeometry()
    for screen in QApplication.screens():
        if screen.availableGeometry().intersects(frame):
            return True
    return False


def _apply_chrome(widget):
    """Add the maximise button and restore the remembered size.

    Args:
        widget (QWidget): An eligible dialog, not yet shown.
    """
    from PySide6.QtCore import Qt, QSettings

    flags = widget.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
    if widget.windowModality() == Qt.WindowModality.NonModal:
        flags |= Qt.WindowType.WindowMinimizeButtonHint
    widget.setWindowFlags(flags)

    saved = QSettings("IsotopeTrack", "IsotopeTrack").value(_settings_key(widget))
    if not saved:
        return
    try:
        if widget.restoreGeometry(saved) and not _on_screen(widget):
            widget.resize(widget.sizeHint())
    except Exception:
        _itk_log.exception("Handled exception restoring dialog geometry")


def _remember_geometry(widget):
    """Store a dialog's size and position for the next time it is opened.

    Args:
        widget (QWidget): The dialog being hidden.
    """
    from PySide6.QtCore import QSettings

    try:
        QSettings("IsotopeTrack", "IsotopeTrack").setValue(
            _settings_key(widget), widget.saveGeometry())
    except Exception:
        _itk_log.exception("Handled exception saving dialog geometry")


def install_dialog_chrome(app):
    """Give every application dialog a maximise button and a remembered size.

    Safe to call more than once; only the first call installs the filter.

    Args:
        app (QApplication): The running application instance.
    """
    global _installed, _filter
    if _installed:
        return
    _installed = True

    from PySide6.QtCore import QEvent, QObject

    class _DialogChrome(QObject):
        """Application-wide filter that adorns dialogs as they are shown."""

        def eventFilter(self, obj, event):
            """Adorn eligible dialogs on polish and save their size on hide.

            Args:
                obj (QObject): The object the event was sent to.
                event (QEvent): The event.

            Returns:
                bool: Always False — the event is observed, never consumed.
            """
            try:
                kind = event.type()
                if kind == QEvent.Type.Polish:
                    if (not obj.property(_APPLIED_PROPERTY)
                            and _is_eligible(obj)):
                        obj.setProperty(_APPLIED_PROPERTY, True)
                        _apply_chrome(obj)
                elif kind == QEvent.Type.Hide:
                    if obj.property(_APPLIED_PROPERTY):
                        _remember_geometry(obj)
            except Exception:
                _itk_log.exception("Handled exception in dialog chrome filter")
            return False

    _filter = _DialogChrome(app)
    app.installEventFilter(_filter)
