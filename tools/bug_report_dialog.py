"""
tools/bug_report_dialog.py

Dialogs for anonymous error reporting: the "Report a Bug" form in the Help
menu and the one-time question asking whether automatic crash reports may be
sent. Both use the app palette and follow theme changes while open.

What is sent and how it is cleaned is defined in ``tools/crash_reporting.py``.
"""

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from tools import crash_reporting
from tools.theme import dialog_qss, theme

_itk_log = logging.getLogger("IsotopeTrack.tools.bug_report_dialog")


def _extra_qss(p):
    """Return styling for the widgets ``dialog_qss`` does not cover."""
    return f"""
        QDialog QLabel#reportTitle {{
            font-size: 15px;
            font-weight: 700;
        }}
        QDialog QLabel#reportMuted {{
            color: {p.text_secondary};
        }}
        QDialog QLabel#reportNote {{
            color: {p.text_secondary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border_subtle};
            border-radius: 6px;
            padding: 8px 10px;
        }}
        QDialog QLabel#reportStatusOk {{
            color: {p.success};
            font-weight: 600;
        }}
        QDialog QLabel#reportStatusError {{
            color: {p.danger};
            font-weight: 600;
        }}
        QDialog QPlainTextEdit {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 6px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QDialog QPlainTextEdit:focus {{
            border: 1px solid {p.accent};
        }}
        QDialog QPushButton:disabled {{
            background-color: {p.bg_tertiary};
            color: {p.text_muted};
            border: 1px solid {p.border_subtle};
        }}
    """


class _ThemedDialog(QDialog):
    """QDialog that restyles itself whenever the app theme changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._disconnect_theme = theme.connect_theme(self._apply_theme)
        self.finished.connect(lambda _r: self._disconnect_theme())

    def _apply_theme(self, *_args):
        """Apply the current palette to the dialog."""
        p = theme.palette
        self.setStyleSheet(dialog_qss(p) + _extra_qss(p))


class _SendWorker(QThread):
    """Send one bug report off the UI thread."""

    done = Signal(object)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text

    def run(self):
        try:
            self.done.emit(crash_reporting.send_bug_report(self._text))
        except Exception:
            _itk_log.exception("Bug report worker failed")
            self.done.emit(None)


class BugReportDialog(_ThemedDialog):
    """Form where the user describes a problem and sends it anonymously."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report a Bug")
        self.setModal(True)
        self.setMinimumSize(480, 400)
        self._worker = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        title = QLabel("Report a bug")
        title.setObjectName("reportTitle")
        lay.addWidget(title)

        intro = QLabel("Describe what happened and what you were doing just before. "
                       "Steps to make it happen again help the most.")
        intro.setObjectName("reportMuted")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self._text = QPlainTextEdit()
        self._text.setPlaceholderText(
            "Example: I opened the Clusters tab, chose HDBSCAN and pressed Run. "
            "The app froze and closed.")
        self._text.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._text, 1)

        self._counter = QLabel("")
        self._counter.setObjectName("reportMuted")
        self._counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self._counter)

        note = QLabel(
            "Only your text, the IsotopeTrack version and the operating system "
            "are sent. No name, e-mail, computer name, files or data. "
            "Folder paths in the text are removed automatically, so please "
            "don't type personal details.")
        note.setObjectName("reportNote")
        note.setWordWrap(True)
        lay.addWidget(note)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.hide()
        lay.addWidget(self._status)

        row = QHBoxLayout()
        row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        self._send_btn = QPushButton("Send")
        self._send_btn.setDefault(True)
        self._send_btn.clicked.connect(self._send)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._send_btn)
        lay.addLayout(row)

        self._apply_theme()
        self._on_text_changed()

    def _on_text_changed(self):
        """Update the character counter and the Send button state."""
        n = len(self._text.toPlainText())
        limit = crash_reporting.MAX_BUG_REPORT_LENGTH
        self._counter.setText(f"{n} / {limit}")
        self._send_btn.setEnabled(0 < len(self._text.toPlainText().strip()) and n <= limit)

    def _set_status(self, text, ok):
        """Show a result line under the form."""
        self._status.setObjectName("reportStatusOk" if ok else "reportStatusError")
        self._status.setText(text)
        self._status.show()
        self._apply_theme()

    def _send(self):
        """Send the report in the background."""
        if not crash_reporting.sending_allowed():
            self._set_status("Bug reports are only sent from the installed app, "
                             "not when IsotopeTrack runs from source.", ok=False)
            return
        self._send_btn.setEnabled(False)
        self._send_btn.setText("Sending…")
        self._text.setReadOnly(True)
        self._worker = _SendWorker(self._text.toPlainText(), self)
        self._worker.done.connect(self._on_sent)
        self._worker.start()

    def _on_sent(self, event_id):
        """Show the outcome and turn Cancel into Close on success."""
        self._worker = None
        if event_id:
            self._set_status("Thank you. Your report was sent.", ok=True)
            self._send_btn.hide()
            self._cancel_btn.setText("Close")
            self._cancel_btn.setDefault(True)
        else:
            self._set_status("The report could not be sent. Check your internet "
                             "connection and try again.", ok=False)
            self._send_btn.setText("Send")
            self._send_btn.setEnabled(True)
            self._text.setReadOnly(False)

    def reject(self):
        """Wait for a running send before closing."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        super().reject()


class CrashConsentDialog(_ThemedDialog):
    """One-time question asking whether automatic crash reports may be sent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help Improve IsotopeTrack")
        self.setModal(True)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        title = QLabel("Send anonymous crash reports?")
        title.setObjectName("reportTitle")
        lay.addWidget(title)

        intro = QLabel("When IsotopeTrack hits an unexpected error, it can send a "
                       "short technical report so the problem can be found and fixed.")
        intro.setObjectName("reportMuted")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        sent = QLabel(
            "<b>Sent:</b> the type of error, where in the IsotopeTrack code it "
            "happened, the IsotopeTrack version and the operating system.<br><br>"
            "<b>Never sent:</b> your name, e-mail, computer name or IP address, "
            "file or folder names, sample names, measured data or settings.")
        sent.setObjectName("reportNote")
        sent.setWordWrap(True)
        sent.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(sent)

        later = QLabel("You can change this at any time in Help → Send Anonymous Crash Reports.")
        later.setObjectName("reportMuted")
        later.setWordWrap(True)
        lay.addWidget(later)

        row = QHBoxLayout()
        row.addStretch()
        no_btn = QPushButton("Don't Send")
        no_btn.setDefault(True)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Send Reports")
        yes_btn.clicked.connect(self.accept)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        lay.addLayout(row)

        self._apply_theme()


def ask_crash_consent_once(parent=None):
    """Show the consent question if the user has never answered it.

    Args:
        parent (QWidget | None): Window to centre the question on.

    Returns:
        bool | None: The answer, or None when the question was not shown.
    """
    if crash_reporting.consent_asked() or not crash_reporting.sending_allowed():
        return None
    dlg = CrashConsentDialog(parent)
    answer = dlg.exec() == QDialog.DialogCode.Accepted
    crash_reporting.set_reports_enabled(answer)
    return answer


def show_bug_report_dialog(parent=None):
    """Open the Report a Bug form."""
    BugReportDialog(parent).exec()
