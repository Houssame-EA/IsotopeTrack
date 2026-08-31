"""
tools/update_checker.py

Checks GitHub Releases for a newer version of IsotopeTrack, downloads the
installer for this platform inside the application and hands the verified file
to the operating system, so the user's remaining work is one drag (macOS) or
one installer wizard (Windows).

Both network steps run in background QThreads so the UI never freezes, and the
downloaded file is checked against the ``SHA256SUMS.txt`` asset published by
the release workflow before it is opened. A file fetched here is written by
Python rather than by a browser, so on macOS it carries no ``com.apple``
quarantine attribute and Gatekeeper does not raise its "unidentified
developer" warning for it.

Uses only the standard library + PySide6 (no extra dependencies).
"""

import hashlib
import json
import os
import ssl
import sys
import urllib.request

from PySide6.QtCore import (QThread, Signal, QObject, QSettings, QUrl,
                            QStandardPaths, QProcess, Qt)
from PySide6.QtWidgets import QMessageBox, QProgressDialog
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
DOWNLOAD_TIMEOUT = 60
DOWNLOAD_CHUNK = 256 * 1024
CHECKSUMS_ASSET = "sha256sums.txt"

SETTINGS_ORG = "IsotopeTrack"
SETTINGS_APP = "IsotopeTrack"
SKIP_KEY       = "updates/skipped_version"
AUTO_CHECK_KEY = "updates/auto_check"


def auto_check_enabled():
    """Return True when IsotopeTrack may check for updates on startup.

    Returns:
        bool: Stored preference, defaulting to True.

    Notes:
        The manual ``Help -> Check for Updates`` action ignores this flag; it
        only governs the automatic check, so a laboratory that has validated a
        method against one version can pin it and never be prompted.
    """
    return QSettings(SETTINGS_ORG, SETTINGS_APP).value(
        AUTO_CHECK_KEY, True, type=bool)


def set_auto_check_enabled(enabled):
    """Store whether IsotopeTrack checks for updates on startup.

    Args:
        enabled (bool): True to check automatically on launch.
    """
    QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(
        AUTO_CHECK_KEY, bool(enabled))


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


def _request(url):
    """Build a GitHub request carrying the headers the API expects.

    Args:
        url (str): Absolute URL to fetch.

    Returns:
        urllib.request.Request: Prepared request.
    """
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "IsotopeTrack-UpdateChecker",
    })


def _pick_asset(assets):
    """Choose the release asset matching this OS, by name hint + extension.

    Args:
        assets (list): ``assets`` array from the GitHub release payload.

    Returns:
        dict | None: The matching asset entry, or ``None`` when the release
        carries nothing for this platform.

    Notes:
        Matches the real asset names::

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
            return a
    return candidates[0] if candidates else None


def _checksums_url(assets):
    """Return the URL of the release's checksum manifest, when published.

    Args:
        assets (list): ``assets`` array from the GitHub release payload.

    Returns:
        str | None: Download URL of ``SHA256SUMS.txt``, or ``None`` for
        releases built before the workflow started publishing it.
    """
    for a in assets:
        if (a.get("name") or "").lower() == CHECKSUMS_ASSET:
            return a.get("browser_download_url")
    return None


def _parse_checksums(text, asset_name):
    """Extract one asset's expected digest from a ``shasum`` manifest.

    Args:
        text (str): Manifest contents, one ``<digest>  <filename>`` per line.
        asset_name (str): Asset whose digest is wanted.

    Returns:
        str | None: Lower-case hex digest, or ``None`` when the manifest does
        not mention the asset.

    Notes:
        File names are compared on their base name, so manifests generated
        with a path prefix such as ``dist/IsotopeTrack_M.dmg`` still match.
    """
    wanted = (asset_name or "").strip().lower()
    for line in (text or "").splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        digest, name = parts[0], parts[-1].lstrip("*")
        if os.path.basename(name).lower() == wanted:
            return digest.lower()
    return None


def _download_dir():
    """Return the folder new installers are written to.

    Returns:
        str: The user's Downloads folder, falling back to the home directory
        and then to the temporary directory when neither is writable.
    """
    for location in (QStandardPaths.DownloadLocation,
                     QStandardPaths.HomeLocation):
        path = QStandardPaths.writableLocation(location)
        if path and os.path.isdir(path) and os.access(path, os.W_OK):
            return path
    import tempfile
    return tempfile.gettempdir()


def _unique_path(directory, filename):
    """Return a path in ``directory`` that does not overwrite an existing file.

    Args:
        directory (str): Destination folder.
        filename (str): Preferred file name.

    Returns:
        str: ``directory/filename``, or the same name with ``(1)``, ``(2)``
        and so on inserted before the extension when it is already taken.
    """
    stem, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    index = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem} ({index}){ext}")
        index += 1
    return candidate


def _human_size(num_bytes):
    """Format a byte count for the progress dialog.

    Args:
        num_bytes (int): Size in bytes.

    Returns:
        str: Size with a unit, for example ``'86.4 MB'``.
    """
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


class _UpdateWorker(QThread):
    """Fetches the latest release info from GitHub in a background thread."""
    finished_ok = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            with urllib.request.urlopen(_request(GITHUB_API_URL),
                                        timeout=REQUEST_TIMEOUT,
                                        context=_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("draft") or data.get("prerelease"):
                self.failed.emit("Latest release is a draft or prerelease.")
                return

            assets = data.get("assets") or []
            asset = _pick_asset(assets)
            expected = None
            manifest_url = _checksums_url(assets)
            if asset and manifest_url:
                try:
                    with urllib.request.urlopen(_request(manifest_url),
                                                timeout=REQUEST_TIMEOUT,
                                                context=_ssl_context()) as resp:
                        expected = _parse_checksums(
                            resp.read().decode("utf-8", "replace"),
                            asset.get("name"))
                except Exception:
                    _itk_log.exception("Could not read the checksum manifest")

            self.finished_ok.emit({
                "version": (data.get("tag_name") or "").lstrip("vV"),
                "page_url": data.get("html_url") or "",
                "notes": data.get("body") or "",
                "asset_name": (asset or {}).get("name") or "",
                "asset_size": int((asset or {}).get("size") or 0),
                "download_url": (asset or {}).get("browser_download_url"),
                "sha256": expected,
            })
        except Exception as exc:
            _itk_log.exception("Handled exception in run")
            self.failed.emit(str(exc))


class _DownloadWorker(QThread):
    """Streams one release asset to disk, reporting progress as it goes.

    The bytes land in a ``.part`` file that is renamed only once the transfer
    completes, so a cancelled or interrupted download never leaves behind a
    truncated installer that looks ready to open. The SHA-256 is computed on
    the way past, costing nothing extra in time or memory.
    """

    progress = Signal(int, int)
    finished_ok = Signal(str, str)
    failed = Signal(str)

    def __init__(self, url, dest_path, parent=None):
        super().__init__(parent)
        self._url = url
        self._dest_path = dest_path
        self._part_path = dest_path + ".part"
        self._cancelled = False

    def cancel(self):
        """Ask the transfer to stop at the next chunk boundary."""
        self._cancelled = True

    def run(self):
        digest = hashlib.sha256()
        done = 0
        try:
            with urllib.request.urlopen(_request(self._url),
                                        timeout=DOWNLOAD_TIMEOUT,
                                        context=_ssl_context()) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                with open(self._part_path, "wb") as fh:
                    while True:
                        if self._cancelled:
                            raise _DownloadCancelled()
                        chunk = resp.read(DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)
            os.replace(self._part_path, self._dest_path)
            self.finished_ok.emit(self._dest_path, digest.hexdigest())
        except _DownloadCancelled:
            self._discard_partial()
            self.failed.emit("")
        except Exception as exc:
            _itk_log.exception("Handled exception in download")
            self._discard_partial()
            self.failed.emit(str(exc))

    def _discard_partial(self):
        """Remove the incomplete file, ignoring a failure to do so."""
        try:
            if os.path.exists(self._part_path):
                os.remove(self._part_path)
        except OSError:
            _itk_log.exception("Could not remove the partial download")


class _DownloadCancelled(Exception):
    """Raised inside the download thread when the user presses Cancel."""


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
        self._downloader = None
        self._progress = None
        self._info = {}
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
        size_note = (f"\nDownload:  {_human_size(info.get('asset_size'))}"
                     if info.get("asset_size") else "")
        box.setText(
            "A new version of IsotopeTrack is available.\n\n"
            f"Installed:  {CURRENT_VERSION}\n"
            f"Latest:      {latest}" + size_note
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
            self._start_download(info)
        elif clicked is skip_btn:
            QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(SKIP_KEY, latest)

    def _start_download(self, info):
        """Fetch the installer in the background, showing a progress dialog.

        Args:
            info (dict): Release payload assembled by :class:`_UpdateWorker`.

        Notes:
            Falls back to opening the release page in the browser whenever the
            release carries no asset for this platform, so the user is never
            left without a route to the update.
        """
        url = info.get("download_url")
        if not url:
            self._open_release_page(info)
            return

        self._info = dict(info)
        name = info.get("asset_name") or os.path.basename(url)
        dest = _unique_path(_download_dir(), name)

        self._progress = QProgressDialog(
            f"Downloading {name}…", "Cancel", 0, 100, self._window)
        self._progress.setWindowTitle("Downloading Update")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._progress.setValue(0)

        self._downloader = _DownloadWorker(url, dest, self)
        self._downloader.progress.connect(self._on_download_progress)
        self._downloader.finished_ok.connect(self._on_download_finished)
        self._downloader.failed.connect(self._on_download_failed)
        self._progress.canceled.connect(self._downloader.cancel)
        self._downloader.start()

    def _on_download_progress(self, done, total):
        """Advance the progress dialog as bytes arrive.

        Args:
            done (int): Bytes written so far.
            total (int): Bytes expected, ``0`` when the server omits the
                length; the asset size from the release payload is used then.
        """
        if self._progress is None:
            return
        expected = total or int(self._info.get("asset_size") or 0)
        if expected > 0:
            self._progress.setMaximum(100)
            self._progress.setValue(int(done / expected * 100))
            self._progress.setLabelText(
                f"Downloading {self._info.get('asset_name', 'update')}…\n"
                f"{_human_size(done)} of {_human_size(expected)}")
        else:
            self._progress.setMaximum(0)
            self._progress.setLabelText(
                f"Downloading {self._info.get('asset_name', 'update')}…\n"
                f"{_human_size(done)}")

    def _on_download_failed(self, message):
        """Close the progress dialog and report a failed or cancelled transfer.

        Args:
            message (str): Error text, empty when the user pressed Cancel.
        """
        self._close_progress()
        if not message:
            return
        box = QMessageBox(self._window)
        box.setWindowTitle("Download Failed")
        box.setIcon(QMessageBox.Warning)
        box.setText("The update could not be downloaded.\n\n" + message)
        page_btn = box.addButton("Open Release Page", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is page_btn:
            self._open_release_page(self._info)

    def _on_download_finished(self, path, digest):
        """Verify the finished download and offer to open it.

        Args:
            path (str): Where the installer was written.
            digest (str): SHA-256 computed while streaming.

        Notes:
            A mismatch deletes the file rather than leaving a suspect
            installer in the user's Downloads folder. Releases published
            before the workflow started attaching ``SHA256SUMS.txt`` carry no
            expected digest, and are accepted on the strength of the HTTPS
            transfer alone.
        """
        self._close_progress()
        expected = (self._info.get("sha256") or "").lower()
        if expected and digest.lower() != expected:
            try:
                os.remove(path)
            except OSError:
                _itk_log.exception("Could not remove the mismatched download")
            QMessageBox.warning(
                self._window, "Download Verification Failed",
                "The downloaded file did not match the checksum published "
                "with the release, so it has been deleted.\n\n"
                "This usually means the transfer was interrupted. Please try "
                "again, or download the update from the release page.",
            )
            return

        self._offer_to_open(path)

    def _offer_to_open(self, path):
        """Tell the user where the installer is and offer to launch it.

        Args:
            path (str): The verified installer on disk.

        Notes:
            IsotopeTrack keeps running either way. On Windows the running
            application can hold locks the installer needs, so the message
            asks the user to close it first rather than quitting underneath
            unsaved work.
        """
        box = QMessageBox(self._window)
        box.setWindowTitle("Update Downloaded")
        box.setIcon(QMessageBox.Information)
        if sys.platform.startswith("win"):
            body = ("The installer has been saved to:\n\n"
                    f"{path}\n\n"
                    "Close IsotopeTrack before running it, so the installer "
                    "can replace the files it needs.")
        else:
            body = ("The update has been saved to:\n\n"
                    f"{path}\n\n"
                    "Opening it mounts the disk image; drag IsotopeTrack to "
                    "your Applications folder to finish.")
        box.setText(body)
        open_btn = box.addButton("Open", QMessageBox.AcceptRole)
        reveal_btn = box.addButton("Show in Folder", QMessageBox.ActionRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is open_btn:
            self._launch(path)
        elif clicked is reveal_btn:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(path)))

    def _launch(self, path):
        """Hand the downloaded file to the operating system.

        Args:
            path (str): The verified installer on disk.
        """
        try:
            if sys.platform.startswith("win"):
                started = QProcess.startDetached(path, [])
                if started:
                    return
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            _itk_log.exception("Handled exception in _launch")
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _open_release_page(self, info):
        """Open the release in the browser as the fallback route.

        Args:
            info (dict): Release payload; its ``page_url`` is used when set.
        """
        url = (info or {}).get("page_url")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _close_progress(self):
        """Dispose of the progress dialog once a transfer ends."""
        if self._progress is not None:
            self._progress.reset()
            self._progress.deleteLater()
            self._progress = None
