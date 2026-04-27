# `export_utils.py`

---

## Functions

### `is_pure_element`

```python
def is_pure_element(mass_fraction)
```

Check if mass fraction indicates a pure element (effectively 1.0).


**Args:**

- `mass_fraction (float): Mass fraction value`


**Returns:**

- `bool: True if pure element, False otherwise`

### `get_molecular_weight_for_export`

```python
def get_molecular_weight_for_export(main_window, element_key, sample_name = None)
```

Get molecular weight for export calculations.


**Args:**

- `main_window (object): Main window object`
- `element_key (str): Element key in format 'Element-Isotope'`
- `sample_name (str, optional): Sample name`


**Returns:**

- `float | None: Molecular weight or None if not found`

### `export_data`

```python
def export_data(main_window)
```

Export all sample data and summary file in one unified process with mass fraction,
mole support, dilution factors, and data type selection.


**Args:**

- `main_window (object): Main window object`


**Returns:**

- `bool: True if export successful, False otherwise`

### `export_mass_fraction_info`

```python
def export_mass_fraction_info(main_window, file_handle, selected_samples, data_type)
```

Export mass fraction configuration information with data type and molecular weights.


**Args:**

- `main_window (object): Main window object`
- `file_handle (file): Open file handle for writing`
- `selected_samples (list): List of selected sample names`
- `data_type (str): Data type ('element' or 'particle')`


**Returns:**

- `None`

### `export_summary_file_with_mass_fractions`

```python
def export_summary_file_with_mass_fractions(main_window, summary_file, selected_samples, all_elements, element_labels, sample_dilutions, data_type, units = None)
```

Export summary file with mixed element/particle calculations based on mass fractions and molecular weights.


**Args:**

- `main_window (object): Main window object`
- `summary_file (file): Open file handle for writing`
- `selected_samples (list): List of selected sample names`
- `all_elements (list): List of tuples containing element data`
- `element_labels (list): List of formatted element labels`
- `sample_dilutions (dict): Dictionary of sample dilution factors`
- `data_type (str): Data type ('element' or 'particle')`
- `units (ExportUnits | None): Unit preferences. If None, uses defaults (fg/fmol/nm).`


**Returns:**

- `None`

### `export_sample_file_with_mass_fractions`

```python
def export_sample_file_with_mass_fractions(main_window, sample_name, file_path, all_elements, ionic_data, threshold_data, dilution_factor, data_type, units = None)
```

Export individual sample file with mixed element/particle calculations based on mass fractions and molecular weights.


**Args:**

- `main_window (object): Main window object`
- `sample_name (str): Sample name`
- `file_path (str): Output file path`
- `all_elements (list): List of tuples containing element data`
- `ionic_data (dict): Ionic calibration data`
- `threshold_data (dict): Threshold data`
- `dilution_factor (float): Dilution factor`
- `data_type (str): Data type ('element' or 'particle')`
- `units (ExportUnits | None): Unit preferences. If None, uses defaults (fg/fmol/nm).`


**Returns:**

- `None`
