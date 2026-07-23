# `cli_utils.py`

File with function and classes that manages arguments that are passed with the
Command Line Interface (CLI)

---

## Constants

| Name | Value |
|------|-------|
| `PREFERRED_ISOTOPES` | `IsotopeDisplay.PREFERRED_ISOTOPES` |
| `MASS_BY_SYMBOLE_AND_ISOTOPE_LABEL` | `_mass_by_symbol_and_isotope_label_from_element_data(Perio…` |
| `LABEL_INDEX` | `0` |
| `SYMBOL_INDEX` | `2` |

## Classes

### `CliArguments`

Object used to work with CLI arguments.

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_args_parser_namespace` | `(namespace: Namespace)` | Converts an `argpars.Namespace` into a `CliArguments`. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_mass_by_symbol_and_isotope_label_from_element_data` | `(element_data: list) → dict[str, dict[str, float]]` | Gives a restructured dict from element data. |
| `get_argument_parser` | `() → ArgumentParser` | This function builds and return the `ArgumentParser` that |
| `get_selected_isotopes` | `(isotopes: list[str] \| None, presets: list[str] \| None) → dict[str, li` | Formats a dictionary of elements with list of selected isotope mass, as required by |
