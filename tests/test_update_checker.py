# -*- coding: utf-8 -*-
"""Tests for the in-app updater in tools/update_checker.py.

The updater now downloads the installer itself instead of handing the URL to
a browser, so the failure modes worth pinning are the ones a user would meet
as a corrupt or missing file rather than as a Python traceback:

* the right asset is chosen per platform, and a release with nothing for this
  platform reports that instead of picking a stray file;
* the checksum manifest published by the release workflow is parsed whether or
  not its entries carry a path prefix or a binary marker;
* a completed download is byte-exact, hashes to the digest the caller will
  compare, and leaves no ``.part`` file behind;
* a cancelled or failed transfer leaves neither the final file nor the partial
  one, so a half installer is never presented as ready to open.
"""
import functools
import hashlib
import http.server
import os
import sys
import tempfile
import threading
from unittest import mock

import pytest
from PySide6.QtCore import QCoreApplication, QTimer

from tools import update_checker as uc


ASSETS = [
    {"name": "IsotopeTrack_Setup_1.10.11_W.exe",
     "browser_download_url": "url-windows", "size": 90},
    {"name": "IsotopeTrack_M.dmg",
     "browser_download_url": "url-macos", "size": 80},
    {"name": "SHA256SUMS.txt",
     "browser_download_url": "url-sums", "size": 1},
]


@pytest.fixture(scope="module")
def qapp():
    """Return a Qt event loop the download worker's signals can run on."""
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture(scope="module")
def payload():
    """Return the bytes served as a stand-in installer."""
    return os.urandom(300_000)


@pytest.fixture(scope="module")
def server(payload):
    """Serve ``payload`` as IsotopeTrack_M.dmg from a local HTTP server."""
    directory = tempfile.mkdtemp()
    with open(os.path.join(directory, "IsotopeTrack_M.dmg"), "wb") as fh:
        fh.write(payload)

    class _Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(
        ("127.0.0.1", 0), functools.partial(_Quiet, directory=directory))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _run(qapp, worker, timeout_ms=30000):
    """Run one download worker to completion and return its outcome.

    Args:
        qapp (QCoreApplication): Event loop to spin.
        worker (uc._DownloadWorker): Worker to start.
        timeout_ms (int): Safety net so a hung transfer fails the test.

    Returns:
        dict: ``{'path', 'digest'}`` on success, ``{'error'}`` on failure or
        cancellation, plus ``ticks`` with the progress updates seen.
    """
    out = {"ticks": []}
    worker.progress.connect(lambda done, total: out["ticks"].append((done, total)))
    worker.finished_ok.connect(
        lambda path, digest: (out.update(path=path, digest=digest), qapp.quit()))
    worker.failed.connect(lambda message: (out.update(error=message), qapp.quit()))
    QTimer.singleShot(timeout_ms, qapp.quit)
    worker.start()
    qapp.exec()
    worker.wait()
    return out


@pytest.mark.parametrize("platform, expected", [
    ("darwin", "IsotopeTrack_M.dmg"),
    ("win32", "IsotopeTrack_Setup_1.10.11_W.exe"),
])
def test_asset_matches_platform(platform, expected):
    with mock.patch.object(uc.sys, "platform", platform):
        assert uc._pick_asset(ASSETS)["name"] == expected


def test_no_asset_for_platform_returns_none():
    with mock.patch.object(uc.sys, "platform", "darwin"):
        assert uc._pick_asset([{"name": "release-notes.txt"}]) is None


def test_checksum_manifest_url_is_found():
    assert uc._checksums_url(ASSETS) == "url-sums"
    assert uc._checksums_url([{"name": "IsotopeTrack_M.dmg"}]) is None


@pytest.mark.parametrize("asset, digest", [
    ("IsotopeTrack_M.dmg", "abc123"),
    ("IsotopeTrack_Setup_1.10.11_W.exe", "def456"),
])
def test_checksums_parse_with_prefix_and_marker(asset, digest):
    manifest = ("abc123  dist/IsotopeTrack_M.dmg\n"
                "def456 *IsotopeTrack_Setup_1.10.11_W.exe\n")
    assert uc._parse_checksums(manifest, asset) == digest


def test_checksums_missing_entry_is_none():
    assert uc._parse_checksums("abc123  other.dmg\n", "IsotopeTrack_M.dmg") is None
    assert uc._parse_checksums("", "IsotopeTrack_M.dmg") is None


@pytest.mark.parametrize("latest, current, newer", [
    ("1.10.11", "1.10.10", True),
    ("v1.11.0", "1.10.10", True),
    ("1.10.10", "1.10.10", False),
    ("1.9.20", "1.10.0", False),
])
def test_version_comparison(latest, current, newer):
    assert uc._is_newer(latest, current) is newer


def test_download_is_complete_and_hashed(qapp, server, payload, tmp_path):
    dest = str(tmp_path / "IsotopeTrack_M.dmg")
    out = _run(qapp, uc._DownloadWorker(f"{server}/IsotopeTrack_M.dmg", dest))

    assert out.get("path") == dest, out.get("error")
    assert out["digest"] == hashlib.sha256(payload).hexdigest()
    assert os.path.getsize(dest) == len(payload)
    assert not os.path.exists(dest + ".part")
    assert out["ticks"] and out["ticks"][-1][0] == len(payload)


def test_cancelled_download_leaves_nothing(qapp, server, tmp_path):
    dest = str(tmp_path / "IsotopeTrack_M.dmg")
    worker = uc._DownloadWorker(f"{server}/IsotopeTrack_M.dmg", dest)
    worker.progress.connect(lambda done, total: worker.cancel())
    out = _run(qapp, worker)

    assert out.get("error") == ""
    assert "path" not in out
    assert not os.path.exists(dest)
    assert not os.path.exists(dest + ".part")


def test_failed_download_reports_and_cleans_up(qapp, server, tmp_path):
    dest = str(tmp_path / "IsotopeTrack_M.dmg")
    out = _run(qapp, uc._DownloadWorker(f"{server}/not-a-release.dmg", dest))

    assert out.get("error")
    assert "path" not in out
    assert not os.path.exists(dest)
    assert not os.path.exists(dest + ".part")


def test_existing_file_is_not_overwritten(tmp_path):
    (tmp_path / "IsotopeTrack_M.dmg").write_bytes(b"older download")
    chosen = uc._unique_path(str(tmp_path), "IsotopeTrack_M.dmg")
    assert os.path.basename(chosen) == "IsotopeTrack_M (1).dmg"


def test_auto_check_preference_round_trips():
    original = uc.auto_check_enabled()
    try:
        uc.set_auto_check_enabled(False)
        assert uc.auto_check_enabled() is False
        uc.set_auto_check_enabled(True)
        assert uc.auto_check_enabled() is True
    finally:
        uc.set_auto_check_enabled(original)
