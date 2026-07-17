# `results_dashboard.py`

---

## Constants

| Name | Value |
|------|-------|
| `DASHBOARD_HTML` | `'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset…` |

## Classes

### `DashboardDisplayDialog` *(extends `QDialog`)*

Full-window enhanced Chart.js dashboard.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dashboard_node, parent_window=None)` |  |
| `_inject_data` | `(self, ok)` |  |

### `DashboardNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `process_data` | `(self, input_data)` |  |
| `get_data_summary` | `(self)` |  |
| `configure` | `(self, parent_window)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_positive` | `(v)` |  |
| `_build_dashboard_data` | `(data_context)` | Extract everything the dashboard JS needs. |
