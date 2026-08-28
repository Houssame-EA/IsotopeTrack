# `update_checker.py`

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

---

## Constants

| Name | Value |
|------|-------|
| `GITHUB_OWNER` | `'Houssame-EA'` |
| `GITHUB_REPO` | `'IsotopeTrack'` |
| `GITHUB_API_URL` | `f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REP…` |
| `REQUEST_TIMEOUT` | `8` |
| `DOWNLOAD_TIMEOUT` | `60` |
| `DOWNLOAD_CHUNK` | `256 * 1024` |
| `CHECKSUMS_ASSET` | `'sha256sums.txt'` |
| `SETTINGS_ORG` | `'IsotopeTrack'` |
| `SETTINGS_APP` | `'IsotopeTrack'` |
| `SKIP_KEY` | `'updates/skipped_version'` |
| `AUTO_CHECK_KEY` | `'updates/auto_check'` |

## Classes

### `_UpdateWorker` *(extends `QThread`)*

Fetches the latest release info from GitHub in a background thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(self)` |  |

### `_DownloadWorker` *(extends `QThread`)*

Streams one release asset to disk, reporting progress as it goes.

The bytes land in a ``.part`` file that is renamed only once the transfer
completes, so a cancelled or interrupted download never leaves behind a
truncated installer that looks ready to open. The SHA-256 is computed on
the way past, costing nothing extra in time or memory.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, url, dest_path, parent=None)` |  |
| `cancel` | `(self)` | Ask the transfer to stop at the next chunk boundary. |
| `run` | `(self)` |  |
| `_discard_partial` | `(self)` | Remove the incomplete file, ignoring a failure to do so. |

### `_DownloadCancelled` *(extends `Exception`)*

Raised inside the download thread when the user presses Cancel.

### `UpdateChecker` *(extends `QObject`)*

Usage (from the main window):
    self._update_checker = UpdateChecker(self)
    self._update_checker.check(silent=True)    # automatic, on startup
    self._update_checker.check(silent=False)   # manual, from a menu item

silent=True  -> only speaks up when an update is found (quiet if offline)
silent=False -> always reports the result (for a "Check for Updates" menu)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window)` |  |
| `check` | `(self, silent=True)` |  |
| `_on_failed` | `(self, message)` |  |
| `_on_result` | `(self, info)` |  |
| `_prompt` | `(self, info)` |  |
| `_start_download` | `(self, info)` | Fetch the installer in the background, showing a progress dialog. |
| `_on_download_progress` | `(self, done, total)` | Advance the progress dialog as bytes arrive. |
| `_on_download_failed` | `(self, message)` | Close the progress dialog and report a failed or cancelled transfer. |
| `_on_download_finished` | `(self, path, digest)` | Verify the finished download and offer to open it. |
| `_offer_to_open` | `(self, path)` | Tell the user where the installer is and offer to launch it. |
| `_launch` | `(self, path)` | Hand the downloaded file to the operating system. |
| `_open_release_page` | `(self, info)` | Open the release in the browser as the fallback route. |
| `_close_progress` | `(self)` | Dispose of the progress dialog once a transfer ends. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `auto_check_enabled` | `()` | Return True when IsotopeTrack may check for updates on startup. |
| `set_auto_check_enabled` | `(enabled)` | Store whether IsotopeTrack checks for updates on startup. |
| `_parse_version` | `(text)` | Turn 'v1.2.3' or '1.2.3' into a comparable tuple (1, 2, 3). |
| `_is_newer` | `(latest, current)` |  |
| `_ssl_context` | `()` | Return an SSL context with a trusted CA bundle. |
| `_request` | `(url)` | Build a GitHub request carrying the headers the API expects. |
| `_pick_asset` | `(assets)` | Choose the release asset matching this OS, by name hint + extension. |
| `_checksums_url` | `(assets)` | Return the URL of the release's checksum manifest, when published. |
| `_parse_checksums` | `(text, asset_name)` | Extract one asset's expected digest from a ``shasum`` manifest. |
| `_download_dir` | `()` | Return the folder new installers are written to. |
| `_unique_path` | `(directory, filename)` | Return a path in ``directory`` that does not overwrite an existing file. |
| `_human_size` | `(num_bytes)` | Format a byte count for the progress dialog. |
