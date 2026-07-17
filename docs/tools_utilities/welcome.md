# `welcome.py`

Welcome / Home screen for IsotopeTrack.

---

## Constants

| Name | Value |
|------|-------|
| `DOCS_URL` | `'https://isotopetrack.readthedocs.io/en/latest/'` |
| `PAPER_URL` | `'https://doi.org/10.1071/EN25111'` |
| `GITHUB_URL` | `'https://github.com/Houssame-EA/IsotopeTrack'` |
| `_SETTINGS_ORG` | `'IsotopeTrack'` |
| `_SETTINGS_APP` | `'IsotopeTrack'` |
| `_RECENT_KEY` | `'recent/projects'` |
| `_SHOW_KEY` | `'welcome/show_on_startup'` |
| `_MAX_RECENT` | `8` |

## Classes

### `_ActionCard` *(extends `QPushButton`)*

A large icon + title + subtitle button used for the primary actions.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, icon, title, subtitle, parent=None)` |  |
| `restyle` | `(self)` |  |

### `WelcomeDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window=None)` |  |
| `_run` | `(self, method_name)` |  |
| `_open_recent` | `(self, item)` |  |
| `_populate_recent` | `(self)` |  |
| `_link_button` | `(self, icon, text, url)` |  |
| `_restyle` | `(self)` |  |
| `_disconnect` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_settings` | `()` |  |
| `add_recent_project` | `(path)` | Record *path* as the most recently used project (deduped, capped). |
| `get_recent_projects` | `(existing_only=True)` |  |
| `should_show_on_startup` | `()` |  |
| `set_show_on_startup` | `(value: bool)` |  |
| `_resource_path` | `(rel)` |  |
