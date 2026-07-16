"""Cross-session folder memory for every file dialog in the application.

Wraps the static ``QFileDialog`` convenience methods so all open, save,
and folder-selection dialogs start in the folder the user last picked a
file from, persisted across restarts. On first use, or when the
remembered folder no longer exists, dialogs start on the Desktop. A
caller that passes an explicit absolute location keeps it; a caller that
passes only a suggested file name gets it placed inside the remembered
folder.
"""

import os

_SETTINGS_KEY = "files/last_directory"
_installed = False


def load_last_directory():
    """Return the remembered folder, falling back to the Desktop, then home."""
    from PySide6.QtCore import QSettings, QStandardPaths

    saved = QSettings("IsotopeTrack", "IsotopeTrack").value(_SETTINGS_KEY, "")
    if saved and os.path.isdir(saved):
        return saved
    desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if desktop and os.path.isdir(desktop):
        return desktop
    return os.path.expanduser("~")


def save_last_directory(path):
    """Persist *path* as the folder future file dialogs should start in."""
    from PySide6.QtCore import QSettings

    if path and os.path.isdir(path):
        QSettings("IsotopeTrack", "IsotopeTrack").setValue(_SETTINGS_KEY, path)


def _resolve_start_dir(requested):
    """Combine the caller's requested location with the remembered folder."""
    if not requested:
        return load_last_directory()
    if not os.path.isabs(requested) and os.path.dirname(requested) == "":
        return os.path.join(load_last_directory(), requested)
    return requested


def install_file_dialog_memory():
    """Wrap the static ``QFileDialog`` methods with folder memory. Safe to call more than once."""
    global _installed
    if _installed:
        return
    _installed = True

    from PySide6.QtWidgets import QFileDialog

    original_open = QFileDialog.getOpenFileName
    original_open_many = QFileDialog.getOpenFileNames
    original_save = QFileDialog.getSaveFileName
    original_existing_dir = QFileDialog.getExistingDirectory

    def get_open_file_name(parent=None, caption="", dir="", *args, **kwargs):
        """Open-file dialog that starts in and updates the remembered folder."""
        start = _resolve_start_dir(kwargs.pop("dir", dir))
        path, selected_filter = original_open(parent, caption, start, *args, **kwargs)
        if path:
            save_last_directory(os.path.dirname(path))
        return path, selected_filter

    def get_open_file_names(parent=None, caption="", dir="", *args, **kwargs):
        """Multi-file open dialog that starts in and updates the remembered folder."""
        start = _resolve_start_dir(kwargs.pop("dir", dir))
        paths, selected_filter = original_open_many(parent, caption, start, *args, **kwargs)
        if paths:
            save_last_directory(os.path.dirname(paths[0]))
        return paths, selected_filter

    def get_save_file_name(parent=None, caption="", dir="", *args, **kwargs):
        """Save-file dialog that starts in and updates the remembered folder."""
        start = _resolve_start_dir(kwargs.pop("dir", dir))
        path, selected_filter = original_save(parent, caption, start, *args, **kwargs)
        if path:
            save_last_directory(os.path.dirname(path))
        return path, selected_filter

    def get_existing_directory(parent=None, caption="", dir="", *args, **kwargs):
        """Folder-selection dialog that starts in and updates the remembered folder."""
        start = _resolve_start_dir(kwargs.pop("dir", dir))
        path = original_existing_dir(parent, caption, start, *args, **kwargs)
        if path:
            save_last_directory(path)
        return path

    original_exec = QFileDialog.exec

    def dialog_exec(self, *args):
        """Instance-dialog ``exec`` that starts in and updates the remembered folder.

        Covers dialogs built directly with ``QFileDialog(parent)`` (such as the
        multi-folder Nu data import), which never go through the static
        convenience methods. The start folder is only redirected when the
        dialog still points at the process working directory, so callers that
        set an explicit directory keep it.
        """
        try:
            current = os.path.normpath(self.directory().absolutePath())
            if current in ("", ".", os.path.normpath(os.getcwd())):
                self.setDirectory(load_last_directory())
        except Exception:
            pass
        result = original_exec(self, *args)
        try:
            if result and self.selectedFiles():
                chosen = self.selectedFiles()[0]
                save_last_directory(chosen if os.path.isdir(chosen) else os.path.dirname(chosen))
        except Exception:
            pass
        return result

    QFileDialog.getOpenFileName = staticmethod(get_open_file_name)
    QFileDialog.getOpenFileNames = staticmethod(get_open_file_names)
    QFileDialog.getSaveFileName = staticmethod(get_save_file_name)
    QFileDialog.getExistingDirectory = staticmethod(get_existing_directory)
    QFileDialog.exec = dialog_exec
