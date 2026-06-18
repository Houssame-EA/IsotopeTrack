# `update_checker.py`

tools/update_checker.py

---

## Constants

| Name | Value |
|------|-------|
| `GITHUB_OWNER` | `'Houssame-EA'` |
| `GITHUB_REPO` | `'IsotopeTrack'` |
| `GITHUB_API_URL` | `f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REP…` |
| `REQUEST_TIMEOUT` | `8` |
| `SETTINGS_ORG` | `'IsotopeTrack'` |
| `SETTINGS_APP` | `'IsotopeTrack'` |
| `SKIP_KEY` | `'updates/skipped_version'` |

## Classes

### `_UpdateWorker` *(extends `QThread`)*

Fetches the latest release info from GitHub in a background thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(self)` |  |

### `UpdateChecker` *(extends `QObject`)*

Usage (from the main window):

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window)` |  |
| `check` | `(self, silent=True)` |  |
| `_on_failed` | `(self, message)` |  |
| `_on_result` | `(self, info)` |  |
| `_prompt` | `(self, info)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_parse_version` | `(text)` | Turn 'v1.2.3' or '1.2.3' into a comparable tuple (1, 2, 3). |
| `_is_newer` | `(latest, current)` |  |
| `_ssl_context` | `()` | Return an SSL context with a trusted CA bundle. |
| `_pick_asset` | `(assets)` | Choose the download URL matching this OS, by name hint + extension. |
