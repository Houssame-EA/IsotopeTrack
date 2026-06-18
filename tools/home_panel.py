"""Home panel for IsotopeTrack.

Shown in the main plot area only while no data is loaded — so it never
covers an actual plot. Instead of a blank panel, it offers a quick way to
pick up where you left off:

* a "Recover unsaved session" card when a previous run crashed
  (autosave snapshot present), and
* a list of recently saved projects,

plus Import / Load actions. It tracks the same recent-projects store the
Welcome screen uses and the autosave recovery files written by
``AutosaveManager``.
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFrame,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPainter, QColor
import logging

from tools.theme import theme

try:
    import qtawesome as qta
except Exception:
    qta = None

try:
    from tools.welcome import get_recent_projects
except Exception:
    def get_recent_projects(existing_only=True):
        return []

_itk_log = logging.getLogger("IsotopeTrack.tools.home_panel")


def _recovery_sessions():
    """Return [(Path, datetime)] for recoverable crashed sessions, newest first."""
    try:
        from save_export.autosave import AutosaveManager
        return AutosaveManager.find_recovery_files() or []
    except Exception:
        _itk_log.debug("Could not query recovery sessions")
        return []


class HomePanel(QWidget):
    """Resume-focused landing panel that overlays the empty plot area."""

    def __init__(self, overlay_target=None,
                 on_open_project=None, on_recover=None, parent=None):
        super().__init__(parent if parent is not None else overlay_target)
        self._overlay_target = overlay_target
        self._on_open_project = on_open_project
        self._on_recover = on_recover
        self.setAttribute(Qt.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addStretch()

        # Centered content column.
        self._column = QFrame()
        self._column.setObjectName("homeColumn")
        self._column.setMaximumWidth(560)
        col = QVBoxLayout(self._column)
        col.setContentsMargins(28, 26, 28, 26)
        col.setSpacing(10)

        self._title = QLabel("Welcome back")
        self._title.setObjectName("homeTitle")
        col.addWidget(self._title)

        self._subtitle = QLabel("Pick up where you left off, or import new data.")
        self._subtitle.setObjectName("homeSubtitle")
        self._subtitle.setWordWrap(True)
        col.addWidget(self._subtitle)

        # Recovery card (shown only when a crashed session is available).
        self._recover_btn = QPushButton()
        self._recover_btn.setObjectName("homeRecover")
        self._recover_btn.setCursor(Qt.PointingHandCursor)
        self._recover_btn.clicked.connect(self._do_recover)
        self._recover_btn.setVisible(False)
        col.addSpacing(4)
        col.addWidget(self._recover_btn)

        self._recent_header = QLabel("RECENT PROJECTS")
        self._recent_header.setObjectName("homeRecentHeader")
        col.addSpacing(6)
        col.addWidget(self._recent_header)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("homeRecentList")
        self._recent_list.setUniformItemSizes(True)
        self._recent_list.setMaximumHeight(190)
        self._recent_list.itemClicked.connect(self._open_recent)
        self._recent_list.itemActivated.connect(self._open_recent)
        col.addWidget(self._recent_list)

        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addWidget(self._column)
        wrap.addStretch()
        root.addLayout(wrap)
        root.addStretch()

        if overlay_target is not None:
            overlay_target.installEventFilter(self)
            self.setGeometry(overlay_target.rect())

        self._theme_unsub = theme.connect_theme(lambda *_: self._restyle())
        self.destroyed.connect(lambda *_: self._disconnect())

        self.refresh()
        self._restyle()

    # -- data ------------------------------------------------------------------

    def refresh(self):
        """Re-read recovery sessions + recent projects and rebuild the panel."""
        # Recovery card
        sessions = _recovery_sessions()
        self._recovery_path = None
        if sessions:
            path, when = sessions[0]
            self._recovery_path = path
            ts = when.strftime("%b %d, %H:%M") if hasattr(when, "strftime") else ""
            label = "  Recover unsaved session"
            if ts:
                label += f"   ·   crashed {ts}"
            self._recover_btn.setText(label)
            if qta is not None:
                try:
                    self._recover_btn.setIcon(
                        qta.icon("fa6s.rotate-left", color=theme.palette.text_inverse))
                except Exception:
                    pass
            self._recover_btn.setVisible(True)
        else:
            self._recover_btn.setVisible(False)

        # Recent projects
        self._recent_list.clear()
        recent = get_recent_projects()
        if recent:
            self._recent_header.setVisible(True)
            self._recent_list.setVisible(True)
            for path in recent:
                it = QListWidgetItem(f"  {Path(path).stem}")
                it.setToolTip(path)
                it.setData(Qt.UserRole, path)
                if qta is not None:
                    try:
                        it.setIcon(qta.icon("fa6s.file", color=theme.palette.text_secondary))
                    except Exception:
                        pass
                self._recent_list.addItem(it)
        else:
            self._recent_header.setVisible(False)
            self._recent_list.setVisible(False)

        # Tailor the heading to whether there's anything to resume.
        if self._recovery_path or recent:
            self._title.setText("Welcome back")
            self._subtitle.setText("Pick up where you left off.")
        else:
            self._title.setText("Get started")
            self._subtitle.setText(
                "Import a Nu Vitesse folder, a TOFWERK .h5 file, or CSV data "
                "to begin your analysis.")

    # -- actions ---------------------------------------------------------------

    def _do_recover(self):
        if self._recovery_path and callable(self._on_recover):
            try:
                self._on_recover(self._recovery_path)
            except Exception:
                _itk_log.exception("Recover action failed")

    def _open_recent(self, item):
        path = item.data(Qt.UserRole)
        if path and callable(self._on_open_project):
            try:
                self._on_open_project(path)
            except Exception:
                _itk_log.exception("Open recent failed")

    # -- styling ---------------------------------------------------------------

    def _restyle(self):
        p = theme.palette
        self._column.setStyleSheet(
            f"QFrame#homeColumn {{ background: {p.bg_secondary};"
            f" border: 1px solid {p.border}; border-radius: 14px; }}")
        self._title.setStyleSheet(
            f"QLabel#homeTitle {{ color:{p.text_primary}; font-size:22px;"
            f" font-weight:800; background:transparent; }}")
        self._subtitle.setStyleSheet(
            f"QLabel#homeSubtitle {{ color:{p.text_secondary}; font-size:13px;"
            f" background:transparent; }}")
        self._recent_header.setStyleSheet(
            f"QLabel#homeRecentHeader {{ color:{p.text_muted}; font-size:11px;"
            f" font-weight:700; letter-spacing:1px; background:transparent; }}")
        self._recover_btn.setStyleSheet(
            f"QPushButton#homeRecover {{ background:{p.warning}; color:{p.text_inverse};"
            f" border:none; border-radius:8px; padding:11px 14px; text-align:left;"
            f" font-weight:700; font-size:13px; }}"
            f"QPushButton#homeRecover:hover {{ background:{p.accent_hover}; }}")
        self._recent_list.setStyleSheet(
            f"QListWidget#homeRecentList {{ background:{p.bg_tertiary};"
            f" border:1px solid {p.border}; border-radius:8px; padding:4px; }}"
            f"QListWidget#homeRecentList::item {{ padding:8px; border-radius:6px;"
            f" color:{p.text_primary}; }}"
            f"QListWidget#homeRecentList::item:hover {{ background:{p.bg_hover}; }}"
            f"QListWidget#homeRecentList::item:selected {{ background:{p.accent_soft};"
            f" color:{p.text_primary}; }}")
        if qta is not None and self._recover_btn.isVisible():
            try:
                self._recover_btn.setIcon(
                    qta.icon("fa6s.rotate-left", color=p.text_inverse))
            except Exception:
                pass
        self.update()

    def paintEvent(self, event):
        # Opaque backdrop so the empty plot underneath doesn't show through.
        p = theme.palette
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(p.bg_primary))
        painter.end()

    def eventFilter(self, obj, event):
        if obj is self._overlay_target and event.type() in (QEvent.Resize, QEvent.Move):
            self.setGeometry(self._overlay_target.rect())
        return False

    def _disconnect(self):
        try:
            if callable(self._theme_unsub):
                self._theme_unsub()
        except Exception:
            _itk_log.debug("home panel theme slot already disconnected")
