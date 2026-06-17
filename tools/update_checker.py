"""
tools/update_checker.py

Checks GitHub Releases for a newer version of IsotopeTrack and, if one exists,
shows a non-blocking notification with a "Download" button.

The network request runs in a background QThread so the UI never freezes.
Uses only the standard library + PySide6 (no extra dependencies).
"""

import json
import ssl
import sys
import urllib.request

from PySide6.QtCore import QThread, Signal, QObject, QSettings, QUrl
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QDesktopServices
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.update_checker")

try:
    from utils.app_version import __version__ as CURRENT_VERSION
except Exception:
    _itk_log.exception("Handled exception in <module>")
    CURRENT_VERSION = "0.0.0"

# ---------------------------------------------------------------------------
GITHUB_OWNER = "Houssame-EA"
GITHUB_REPO  = "IsotopeTrack"
# ---------------------------------------------------------------------------

GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 8 

SETTINGS_ORG = "IsotopeTrack"
SETTINGS_APP = "IsotopeTrack"
SKIP_KEY     = "updates/skipped_version"


def _parse_version(text):
    """Turn 'v1.2.3' or '1.2.3' into a comparable tuple (1, 2, 3)."""
    text = (text or "").strip().lstrip("vV")
    parts = []
    for chunk in text.split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break 
        parts.append(int(num) if num else 0)
    return tuple(parts) if parts else (0,)


def _is_newer(latest, current):
    return _parse_version(latest) > _parse_version(current)


def _ssl_context():
    """Return an SSL context with a trusted CA bundle.

    On macOS (and inside frozen/PyInstaller apps) Python frequently can't find
    the system root certificates, which raises
    'CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate'.
    certifi ships a known-good CA bundle and is already included in the build,
    so we point the handshake at it. Falls back to the platform default if
    certifi isn't importable for some reason.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        _itk_log.exception("Handled exception in _ssl_context")
        return ssl.create_default_context()


def _pick_asset(assets):
    """Choose the download URL matching this OS, by name hint + extension.

    Matches your real asset names:
        Windows -> IsotopeTrack_Setup_<ver>_W.exe   (hint '_w', ext .exe)
        macOS   -> IsotopeTrack_M.dmg                (hint '_m', ext .dmg)
    """
    if sys.platform.startswith("win"):
        hints, exts = ("_w", "setup"), (".exe", ".msi", ".zip")
    elif sys.platform == "darwin":
        hints, exts = ("_m",), (".dmg", ".pkg")
    else: 
        hints, exts = (), (".appimage", ".deb", ".tar.gz")

    candidates = [
        a for a in assets
        if (a.get("name") or "").lower().endswith(exts)
    ]
    for a in candidates:
        name = (a.get("name") or "").lower()
        if any(h in name for h in hints):
            return a.get("browser_download_url")
    if candidates:
        return candidates[0].get("browser_download_url")
    return None 


class _UpdateWorker(QThread):
    """Fetches the latest release info from GitHub in a background thread."""
    finished_ok = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "IsotopeTrack-UpdateChecker",
                },
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT,
                                        context=_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("draft") or data.get("prerelease"):
                self.failed.emit("Latest release is a draft or prerelease.")
                return

            self.finished_ok.emit({
                "version": (data.get("tag_name") or "").lstrip("vV"),
                "page_url": data.get("html_url") or "",
                "notes": data.get("body") or "",
                "download_url": _pick_asset(data.get("assets") or []),
            })
        except Exception as exc:
            _itk_log.exception("Handled exception in run")
            self.failed.emit(str(exc))


class UpdateChecker(QObject):
    """
    Usage (from the main window):
        self._update_checker = UpdateChecker(self)
        self._update_checker.check(silent=True)    # automatic, on startup
        self._update_checker.check(silent=False)   # manual, from a menu item

    silent=True  -> only speaks up when an update is found (quiet if offline)
    silent=False -> always reports the result (for a "Check for Updates" menu)
    """

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self._window = parent_window
        self._worker = None
        self._silent = True

    def check(self, silent=True):
        self._silent = silent
        self._worker = _UpdateWorker()
        self._worker.finished_ok.connect(self._on_result)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, message):
        if not self._silent:
            QMessageBox.information(
                self._window, "Check for Updates",
                "Could not check for updates right now.\n\n" + message,
            )

    def _on_result(self, info):
        latest = info["version"]

        if not _is_newer(latest, CURRENT_VERSION):
            if not self._silent:
                QMessageBox.information(
                    self._window, "Check for Updates",
                    f"You're on the latest version ({CURRENT_VERSION}).",
                )
            return

        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if self._silent and settings.value(SKIP_KEY, "") == latest:
            return  

        self._prompt(info)

    def _prompt(self, info):
        latest = info["version"]
        box = QMessageBox(self._window)
        box.setWindowTitle("Update Available")
        box.setIcon(QMessageBox.Information)
        box.setText(
            "A new version of IsotopeTrack is available.\n\n"
            f"Installed:  {CURRENT_VERSION}\n"
            f"Latest:      {latest}"
        )
        notes = (info.get("notes") or "").strip()
        if notes:
            box.setDetailedText(notes) 

        download_btn = box.addButton("Download", QMessageBox.AcceptRole)
        box.addButton("Remind Me Later", QMessageBox.RejectRole)
        skip_btn = box.addButton("Skip This Version", QMessageBox.DestructiveRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is download_btn:
            url = info.get("download_url") or info.get("page_url")
            if url:
                QDesktopServices.openUrl(QUrl(url))
        elif clicked is skip_btn:
            QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(SKIP_KEY, latest)
