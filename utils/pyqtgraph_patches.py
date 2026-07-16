"""Runtime compatibility patches for third-party libraries.

pyqtgraph's built-in export dialog (right-click on a plot, then Export)
crashes on some PySide6 builds because ``QTreeWidget.headerItem()`` returns
a mis-wrapped ``QWidgetItem`` that lacks ``setText``. The patch below makes
the dialog's UI setup tolerant of that binding bug so the dialog opens
normally. The affected header rows are hidden immediately after creation,
so skipping the text assignment has no visible effect.

The dialog is also styled from the application's active ``ThemeManager``
palette and restyled live whenever the theme changes, so it follows the
app's dark and light modes instead of the default Qt look.
"""

import importlib
import os

_patched = False


class _NoOpHeaderItem:
    """Stand-in header item used when the real one is mis-wrapped."""

    def setText(self, column, text):
        """Ignore the header text assignment; the header is hidden anyway."""
        return None


def apply_pyqtgraph_patches():
    """Install all pyqtgraph compatibility patches. Safe to call more than once."""
    global _patched
    if _patched:
        return
    _patched = True
    _patch_export_dialog_template()
    _patch_file_dialog()
    _patch_exporter_save_directory()


def _export_dialog_stylesheet():
    """Return the export-dialog stylesheet built from the active theme palette."""
    from tools.theme import ThemeManager, export_dialog_qss

    return export_dialog_qss(ThemeManager().palette)


def _install_theme_binding(form):
    """Apply the themed stylesheet to *form* and keep it in sync with theme changes."""
    try:
        from tools.theme import ThemeManager
    except Exception:
        return

    def restyle(*args):
        """Reapply the palette stylesheet, ignoring forms that were destroyed."""
        try:
            form.setStyleSheet(_export_dialog_stylesheet())
        except RuntimeError:
            pass

    restyle()
    try:
        ThemeManager().themeChanged.connect(restyle)
    except Exception:
        pass


def _patch_file_dialog():
    """Theme pyqtgraph's non-native file save dialogs so they follow the app palette."""
    try:
        from pyqtgraph.widgets import FileDialog as file_dialog_module
    except Exception:
        return

    original_init = file_dialog_module.FileDialog.__init__

    def patched_init(self, *args):
        """Build the dialog normally, then bind it to the application theme."""
        original_init(self, *args)
        _install_theme_binding(self)

    file_dialog_module.FileDialog.__init__ = patched_init


def _patch_exporter_save_directory():
    """Start export save dialogs in the app-wide remembered folder, or the Desktop on first use."""
    try:
        exporter_module = importlib.import_module("pyqtgraph.exporters.Exporter")
        from utils.file_dialog_memory import load_last_directory, save_last_directory
    except Exception:
        return

    exporter_class = exporter_module.Exporter
    original_dialog = exporter_class.fileSaveDialog
    original_finished = exporter_class.fileSaveFinished

    def file_save_dialog(self, filter=None, opts=None):
        """Open the save dialog in the remembered folder before delegating to pyqtgraph."""
        if exporter_module.LastExportDirectory is None:
            exporter_module.LastExportDirectory = load_last_directory()
        return original_dialog(self, filter=filter, opts=opts)

    def file_save_finished(self, fileName):
        """Persist the chosen folder, then run pyqtgraph's normal save handling."""
        save_last_directory(os.path.split(fileName)[0])
        return original_finished(self, fileName)

    exporter_class.fileSaveDialog = file_save_dialog
    exporter_class.fileSaveFinished = file_save_finished


def _patch_export_dialog_template():
    """Wrap the export dialog's ``setupUi`` so a broken ``headerItem`` binding cannot crash it and the dialog follows the app theme."""
    try:
        from pyqtgraph.GraphicsScene import exportDialogTemplate_generic as template
        from pyqtgraph.Qt import QtWidgets
    except Exception:
        return

    original_setup_ui = template.Ui_Form.setupUi
    original_header_item = QtWidgets.QTreeWidget.headerItem

    def safe_header_item(tree):
        """Return the tree's header item, or a no-op stand-in if it is unusable."""
        item = original_header_item(tree)
        if hasattr(item, "setText"):
            return item
        return _NoOpHeaderItem()

    def setup_ui(self, form):
        """Run the original ``setupUi`` with a crash-proof ``headerItem`` in place, then theme the dialog."""
        QtWidgets.QTreeWidget.headerItem = safe_header_item
        try:
            original_setup_ui(self, form)
        finally:
            QtWidgets.QTreeWidget.headerItem = original_header_item
        _install_theme_binding(form)

    template.Ui_Form.setupUi = setup_ui
