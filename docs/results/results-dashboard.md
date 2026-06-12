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
| `__init__` | `(self, dashboard_node, parent_window=None)` | Args: |
| `_inject_data` | `(self, ok)` | Args: |

### `DashboardNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `get_data_summary` | `(self)` | Returns: |
| `configure` | `(self, parent_window)` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_positive` | `(v)` | Args: |
| `_build_dashboard_data` | `(data_context)` | Extract everything the dashboard JS needs. |
