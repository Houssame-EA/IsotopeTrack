# `results_dashboard.py`

---

## Constants

| Name | Value |
|------|-------|
| `DASHBOARD_HTML` | `'<!DOCTYPE html>\n<html lang="en">\n<head>\n<me...` |

## Classes

### `DashboardDisplayDialog` *(extends `QDialog`)*

Full-window enhanced Chart.js dashboard.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dashboard_node, parent_window = None)` | Args: |
| `_inject_data` | `(self, ok)` | Args: |

### `DashboardNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `get_data_summary` | `(self)` | Returns: |
| `configure` | `(self, parent_window)` | Args: |

## Functions

### `_safe_positive`

```python
def _safe_positive(v)
```


**Args:**

- `v (Any): The v.`

**Returns:**

- `object: Result of the operation.`

### `_build_dashboard_data`

```python
def _build_dashboard_data(data_context)
```

Extract everything the dashboard JS needs.

**Args:**

- `data_context (Any): The data context.`

**Returns:**

- `dict: Result of the operation.`
