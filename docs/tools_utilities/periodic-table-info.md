# `periodic_table_info.py`

This file contains a readonly service (info) for periodic table data.

---

## Classes

### `_Col` *(extends `StrEnum`)*

Columns in the maps of the `PeriodicTableInfo`.
Notes:
    This is supposed to be an inner class of `PeriodicTableInfo` but,
    for readability it was put outside.

### `PeriodicTableInfo`

This class is used to provide information about elements and isotopes
of the periodic table.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `element_exists` | `(self, element: str) → bool` | Args: |
| `get_mass_by_element` | `(self, element: str) → Optional[float]` | Args: |
| `get_density_by_element` | `(self, element: str) → Optional[float]` | Args: |
| `get_element_by_symbol` | `(self, element: str) → Optional[dict]` | Args: |
| `get_all_elements_as_set` | `(self) → set[str]` | Gets all symboles of the periodic table. |
