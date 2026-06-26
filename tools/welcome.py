"""Welcome / Home screen for IsotopeTrack.

Shown on first launch of the primary window (and from Help → Welcome). Gives
new users an obvious entry point — import data, load a project, open the docs
or the paper — and returning users quick access to recent projects.
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QCheckBox, QListWidget, QListWidgetItem, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QPixmap, QDesktopServices, QIcon
from PySide6.QtCore import QUrl
import logging

from tools.theme import theme, dialog_qss

try:
    import qtawesome as qta
except Exception:
    qta = None

try:
    from utils.app_version import __version__ as APP_VERSION
except Exception:
    # Fallback only used if the import fails; kept in sync by version.py.
    APP_VERSION = "1.10.5"

_itk_log = logging.getLogger("IsotopeTrack.tools.welcome")

DOCS_URL = "https://isotopetrack.readthedocs.io/en/latest/"
PAPER_URL = "https://doi.org/10.1071/EN25111"
GITHUB_URL = "https://github.com/Houssame-EA/IsotopeTrack"

_SETTINGS_ORG = "IsotopeTrack"
_SETTINGS_APP = "IsotopeTrack"
_RECENT_KEY = "recent/projects"
_SHOW_KEY = "welcome/show_on_startup"
_MAX_RECENT = 8


# --------------------------------------------------------------------------- #
# Recent projects (persisted via QSettings)
# --------------------------------------------------------------------------- #

def _settings():
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def add_recent_project(path):
    """Record *path* as the most recently used project (deduped, capped)."""
    if not path:
        return
    try:
        path = str(Path(path))
    except Exception:
        return
    s = _settings()
    items = s.value(_RECENT_KEY, []) or []
    if isinstance(items, str):
        items = [items]
    items = [p for p in items if p and p != path]
    items.insert(0, path)
    s.setValue(_RECENT_KEY, items[:_MAX_RECENT])


def get_recent_projects(existing_only=True):
    s = _settings()
    items = s.value(_RECENT_KEY, []) or []
    if isinstance(items, str):
        items = [items]
    if existing_only:
        items = [p for p in items if p and Path(p).exists()]
    return items[:_MAX_RECENT]


def should_show_on_startup():
    return bool(_settings().value(_SHOW_KEY, False, type=bool))


def set_show_on_startup(value: bool):
    _settings().setValue(_SHOW_KEY, bool(value))


def _resource_path(rel):
    try:
        base = Path(sys._MEIPASS)
    except AttributeError:
        base = Path(__file__).resolve().parent.parent
    return base / rel


# --------------------------------------------------------------------------- #
# Welcome dialog
# --------------------------------------------------------------------------- #

class _ActionCard(QPushButton):
    """A large icon + title + subtitle button used for the primary actions."""

    def __init__(self, icon, title, subtitle, parent=None):
        super().__init__(parent)
        self._icon_name = icon
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(4)
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._icon_label)
        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet("font-weight: 700; font-size: 13px; background: transparent;")
        lay.addWidget(self._title)
        self._subtitle = QLabel(subtitle)
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet("font-size: 11px; background: transparent;")
        lay.addWidget(self._subtitle)

    def restyle(self):
        p = theme.palette
        if qta is not None:
            try:
                self._icon_label.setPixmap(
                    qta.icon(self._icon_name, color=p.accent).pixmap(26, 26))
            except Exception:
                _itk_log.debug("welcome card icon unavailable")
        self._title.setStyleSheet(
            f"font-weight:700; font-size:13px; color:{p.text_primary}; background:transparent;")
        self._subtitle.setStyleSheet(
            f"font-size:11px; color:{p.text_secondary}; background:transparent;")
        self.setStyleSheet(
            f"QPushButton {{ background: {p.bg_secondary}; border: 1px solid {p.border};"
            f" border-radius: 10px; }}"
            f"QPushButton:hover {{ border: 1px solid {p.accent}; background: {p.bg_hover}; }}"
        )


class WelcomeDialog(QDialog):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self._mw = main_window
        self.setWindowTitle("Welcome to IsotopeTrack")
        self.setModal(False)
        self.setMinimumSize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(8)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(14)
        self._logo = QLabel()
        self._logo.setFixedSize(56, 56)
        self._logo.setAlignment(Qt.AlignCenter)
        icon_path = _resource_path("images/isotrack_icon.png")
        if icon_path.exists():
            pm = QPixmap(str(icon_path))
            if not pm.isNull():
                self._logo.setPixmap(
                    pm.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(self._logo, 0, Qt.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self._app_title = QLabel("IsotopeTrack")
        self._app_title.setStyleSheet("font-size: 26px; font-weight: 800; background: transparent;")
        title_box.addWidget(self._app_title)
        self._tagline = QLabel(
            (f"Version {APP_VERSION}  •  " if APP_VERSION else "")
            + "Single-particle ICP-ToF-MS analysis")
        title_box.addWidget(self._tagline)
        header.addLayout(title_box)
        header.addStretch()
        root.addLayout(header)

        root.addSpacing(8)

        # ── Primary actions ─────────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self._cards = []
        self._import_card = _ActionCard(
            "fa6s.file-import", "Import Data", "Folder, .h5 or CSV")
        self._import_card.clicked.connect(lambda: self._run("select_folder"))
        self._load_card = _ActionCard(
            "fa6s.folder-open", "Load Project", "Open a saved .itproj")
        self._load_card.clicked.connect(lambda: self._run("load_project"))
        self._new_card = _ActionCard(
            "fa6s.window-restore", "New Window", "Start a fresh session")
        self._new_card.clicked.connect(lambda: self._run("open_new_window"))
        for c in (self._import_card, self._load_card, self._new_card):
            self._cards.append(c)
            actions.addWidget(c)
        root.addLayout(actions)

        root.addSpacing(10)

        # ── Recent projects ─────────────────────────────────────────────────
        self._recent_header = QLabel("RECENT PROJECTS")
        root.addWidget(self._recent_header)
        self._recent_list = QListWidget()
        self._recent_list.setUniformItemSizes(True)
        self._recent_list.itemActivated.connect(self._open_recent)
        self._recent_list.itemClicked.connect(self._open_recent)
        root.addWidget(self._recent_list, 1)
        self._populate_recent()

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        self._docs_btn = self._link_button("fa6s.book", "Documentation", DOCS_URL)
        self._paper_btn = self._link_button("fa6s.file-lines", "Paper", PAPER_URL)
        self._gh_btn = self._link_button("fa6s.code-branch", "GitHub", GITHUB_URL)
        footer.addWidget(self._docs_btn)
        footer.addWidget(self._paper_btn)
        footer.addWidget(self._gh_btn)
        footer.addStretch()
        root.addLayout(footer)

        bottom = QHBoxLayout()
        self._show_cb = QCheckBox("Show this screen on startup")
        self._show_cb.setChecked(should_show_on_startup())
        self._show_cb.toggled.connect(set_show_on_startup)
        bottom.addWidget(self._show_cb)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

        self._theme_unsub = theme.connect_theme(lambda *_: self._restyle())
        self.destroyed.connect(lambda *_: self._disconnect())
        self._restyle()

    # -- actions ---------------------------------------------------------------

    def _run(self, method_name):
        self.accept()
        if self._mw is not None and hasattr(self._mw, method_name):
            try:
                getattr(self._mw, method_name)()
            except Exception:
                _itk_log.exception("Welcome action '%s' failed", method_name)

    def _open_recent(self, item):
        path = item.data(Qt.UserRole)
        if not path:
            return
        self.accept()
        if self._mw is not None and hasattr(self._mw, "load_project"):
            try:
                self._mw.load_project(filepath=path)
            except Exception:
                _itk_log.exception("Could not open recent project")

    def _populate_recent(self):
        self._recent_list.clear()
        recent = get_recent_projects()
        if not recent:
            placeholder = QListWidgetItem("No recent projects yet")
            placeholder.setFlags(Qt.NoItemFlags)
            self._recent_list.addItem(placeholder)
            return
        for path in recent:
            name = Path(path).stem
            it = QListWidgetItem(f"  {name}")
            it.setToolTip(path)
            it.setData(Qt.UserRole, path)
            if qta is not None:
                try:
                    it.setIcon(qta.icon("fa6s.file", color=theme.palette.text_secondary))
                except Exception:
                    pass
            self._recent_list.addItem(it)

    def _link_button(self, icon, text, url):
        b = QPushButton(text)
        b.setObjectName("welcomeLink")
        b.setFlat(True)
        b.setCursor(Qt.PointingHandCursor)
        b._icon_name = icon
        b.clicked.connect(lambda *_: QDesktopServices.openUrl(QUrl(url)))
        return b

    # -- styling ---------------------------------------------------------------

    def _restyle(self):
        p = theme.palette
        self.setStyleSheet(dialog_qss(p))
        self._app_title.setStyleSheet(
            f"font-size:26px; font-weight:800; color:{p.text_primary}; background:transparent;")
        self._tagline.setStyleSheet(
            f"font-size:13px; color:{p.text_secondary}; background:transparent;")
        self._recent_header.setStyleSheet(
            f"color:{p.text_muted}; font-size:11px; font-weight:700; letter-spacing:1px;")
        self._recent_list.setStyleSheet(
            f"QListWidget {{ background:{p.bg_secondary}; border:1px solid {p.border};"
            f" border-radius:8px; padding:4px; }}"
            f"QListWidget::item {{ padding:8px; border-radius:6px; color:{p.text_primary}; }}"
            f"QListWidget::item:hover {{ background:{p.bg_hover}; }}"
            f"QListWidget::item:selected {{ background:{p.accent_soft}; color:{p.text_primary}; }}"
        )
        link_qss = (
            f"QPushButton#welcomeLink {{ background:transparent; color:{p.accent};"
            f" border:none; padding:6px 10px; font-weight:600; }}"
            f"QPushButton#welcomeLink:hover {{ color:{p.accent_hover};"
            f" text-decoration:underline; }}"
        )
        for b in (self._docs_btn, self._paper_btn, self._gh_btn):
            b.setStyleSheet(link_qss)
            if qta is not None:
                try:
                    b.setIcon(qta.icon(b._icon_name, color=p.accent))
                except Exception:
                    pass
        for c in self._cards:
            c.restyle()
        if qta is not None:
            for it in (self._recent_list.item(i) for i in range(self._recent_list.count())):
                if it and it.data(Qt.UserRole):
                    try:
                        it.setIcon(qta.icon("fa6s.file", color=p.text_secondary))
                    except Exception:
                        pass

    def _disconnect(self):
        try:
            if callable(self._theme_unsub):
                self._theme_unsub()
        except Exception:
            _itk_log.debug("welcome theme slot already disconnected")
