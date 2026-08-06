# `mass_fraction_calculator.py`

Mass-fraction calculator dialog is the widget that handles mass fraction
definition based on known compounds or user entries.

---

## Classes

### `MassFractionCalculator` *(extends `QDialog`)*

Coordinates calculator widgets and commits their working state on Apply.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, selected_isotopes: dict, periodic_table_info: PeriodicTableInfo` |  |
| `_setup_ui` | `(self) → None` |  |
| `_build_header` | `(self) → QHBoxLayout` |  |
| `_connect_signals` | `(self) → None` |  |
| `_refresh_database_status` | `(self) → None` |  |
| `_manual_load_csv` | `(self) → None` |  |
| `_apply_mass_fractions` | `(self) → None` |  |
| `_save_state` | `(self) → None` |  |
| `_restore_previous_state` | `(self) → None` |  |
| `reject` | `(self) → None` | Cancel leaves MainWindow unchanged but retains this dialog's draft. |
| `closeEvent` | `(self, event) → None` | Handles window closing that saves the state to reload |
| `apply_theme` | `(self) → None` | Applies the theme to the window and it's component. |
| `_build_stylesheet` | `() → str` |  |
