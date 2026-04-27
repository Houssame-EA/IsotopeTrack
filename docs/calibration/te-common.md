# `te_common.py`

---

## Constants

| Name | Value |
|------|-------|
| `BASE_STYLESHEET` | `base_stylesheet(LIGHT)` |
| `PREVIEW_STYLES` | `preview_styles(LIGHT)` |
| `RETURN_BUTTON_STYLE` | `return_button_style(LIGHT)` |
| `PLOT_STYLES` | `{'raw_signal': pg.mkPen(color=(30, 144, 255), w...` |
| `HISTOGRAM_COLORS` | `[(30, 144, 255, 180), (50, 205, 50, 180), (255,...` |
| `DEFAULT_DETECTION_PARAMS` | `{'method': 'Compound Poisson LogNormal', 'manua...` |

## Classes

### `NumericDelegate` *(extends `QStyledItemDelegate`)*

Custom delegate that restricts table-cell editing to numeric values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `createEditor` | `(self, parent, option, index)` | Create a QLineEdit with a QDoubleValidator for the given cell. |

## Functions

### `base_stylesheet`

```python
def base_stylesheet(p) → str
```

Full base stylesheet for calibration/TE windows, built from a
theme Palette.  Covers main window, group boxes, buttons, inputs,
tables, labels, tabs, tab bar, and list widgets.

Call from a window's apply_theme() method so the whole window
restyles on light/dark toggle:

self.setStyleSheet(base_stylesheet(theme.palette))

**Args:**

- `p (Any): The p.`

**Returns:**

- `str: Result of the operation.`

### `preview_styles`

```python
def preview_styles(p) → dict
```

Return the four preview-label stylesheet strings tinted for the
given palette.  Keys: 'default', 'error', 'warning', 'success'.

In dark mode the pastel backgrounds are replaced with muted tones
from the palette so text stays readable.

**Args:**

- `p (Any): The p.`

**Returns:**

- `dict: Result of the operation.`

### `return_button_style`

```python
def return_button_style(p) → str
```

Stylesheet for the 'Back to Main' button.  In light mode it keeps
the original warm pink/orange gradient.  In dark mode it switches to
a solid, muted accent so it doesn't blind the user.

**Args:**

- `p (Any): The p.`

**Returns:**

- `str: Result of the operation.`

### `show_data_source_dialog`

```python
def show_data_source_dialog(parent = None)
```

Show the "Select Data Source" popup and return the user's choice.

The dialog presents three radio options — NU folders, generic data
files, and TOFWERK .h5 — each with a short explanatory caption.
Visually it follows the current theme (light or dark) automatically.


**Args:**

- `parent (QWidget | None): Parent for modality.`


**Returns:**

- `str | None: ``'folder'``, ``'csv'``, or ``'tofwerk'`` for the user's`
- `selection, or ``None`` if they cancelled.`

### `snr_to_color`

```python
def snr_to_color(ratio, palette = None)
```

Map a signal-to-noise ratio to a QColor for table row highlighting.


**Args:**

- `ratio (float): Height-to-threshold ratio of a detected particle.`
- `palette: Optional theme Palette.  If omitted, uses the current`
- `theme.palette — so dark mode automatically gets muted`
- `tiers that read on dark backgrounds.`


**Returns:**

- `QColor: Green (>=3), light yellow (>=2), peach (>=1), or pink (<1)`
- `in light mode; muted equivalents in dark mode.`

### `create_scrollable_container`

```python
def create_scrollable_container(parent_layout = None, spacing = 15)
```

Build a QScrollArea wrapping a container QWidget with a QVBoxLayout.

This pattern is repeated in virtually every tab across all TE modules.


**Args:**

- `parent_layout (QLayout | None): If provided, the scroll area is added`
- `to this layout automatically.`
- `spacing (int): Spacing between items inside the container layout.`


**Returns:**

- `tuple[QScrollArea, QVBoxLayout]: The scroll area and the inner layout`
- `to which child widgets should be added.`

### `export_table_to_csv`

```python
def export_table_to_csv(table, parent_widget, dialog_title = 'Export Detection Results')
```

Export the contents of a QTableWidget to a CSV file.

Opens a save-file dialog, writes column headers followed by every row,
and reports success or failure via QMessageBox.


**Args:**

- `table (QTableWidget): The table whose data should be exported.`
- `parent_widget (QWidget): Parent widget for the file dialog and messages.`
- `dialog_title (str): Title shown in the save-file dialog.`


**Returns:**

- `str | None: The path to the saved file, or None if the user cancelled`
- `or an error occurred.`

### `populate_detection_row`

```python
def populate_detection_row(table, row, sample_name, element_label, defaults = None)
```

Populate a single row in a detection-parameters QTableWidget.

Inserts read-only sample/element labels and configurable spin-box/combo
widgets for detection method, threshold etc.


**Args:**

- `table (QTableWidget): Target table (must have ≥9 columns).`
- `row (int): Row index to populate.`
- `sample_name (str): Display name for the sample.`
- `element_label (str): Isotope label (e.g. '208Pb').`
- `defaults (dict | None): Override keys from DEFAULT_DETECTION_PARAMS.`


**Returns:**

- `None`

### `read_detection_row`

```python
def read_detection_row(table, row)
```

Read all detection parameters from a single row of the detection table.


**Args:**

- `table (QTableWidget): The detection parameters table.`
- `row (int): Row index to read.`


**Returns:**

- `dict: Keys match DEFAULT_DETECTION_PARAMS. Falls back to defaults`
- `if widgets are missing.`

### `apply_global_method`

```python
def apply_global_method(table, method_name)
```

Set the detection method combo box on every row to *method_name*.


**Args:**

- `table (QTableWidget): The detection parameters table.`
- `method_name (str): Method string to set (e.g. 'Currie').`


**Returns:**

- `None`

### `plot_detection_results`

```python
def plot_detection_results(plot_widget, sample_name, signal, particles, lambda_bkgd, threshold, time_array, peak_detector = None)
```

Render a comprehensive particle-detection visualisation on *plot_widget*.

Draws raw signal, background/threshold lines, and
detected peaks colour-coded by SNR.


**Args:**

- `plot_widget (pg.PlotWidget): Target pyqtgraph plot widget.`
- `sample_name (str): Sample display name (used in the title).`
- `signal (np.ndarray): Raw signal array.`
- `particles (list[dict]): List of particle dicts from PeakDetection.`
- `lambda_bkgd (float): Background level.`
- `threshold (float): Detection threshold.`
- `time_array (np.ndarray): Time array (seconds).`
- `peak_detector (PeakDetection | None): If provided, its`
- ```get_snr_color`` method is used for scatter colouring.`


**Returns:**

- `None`

### `highlight_particle`

```python
def highlight_particle(plot_widget, particle, time_array, signal, current_item_ref = None)
```

Draw a red highlight over a single particle in *plot_widget*.


**Args:**

- `plot_widget (pg.PlotWidget): Target plot.`
- `particle (dict): Particle dict with 'left_idx' / 'right_idx'.`
- `time_array (np.ndarray): Time array.`
- `signal (np.ndarray): Raw signal array.`
- `current_item_ref (pg.PlotCurveItem | None): Previously highlighted item`
- `to remove before adding the new one.`


**Returns:**

- `pg.PlotCurveItem: The newly added highlight curve (store it so it can`
- `be removed on the next call).`

### `particle_mass_from_diameter`

```python
def particle_mass_from_diameter(diameter_nm, density_g_cm3)
```

Compute the mass of a spherical particle.


**Args:**

- `diameter_nm (float): Particle diameter in nanometres.`
- `density_g_cm3 (float): Bulk density in g/cm³.`


**Returns:**

- `dict: Keys 'volume_m3', 'volume_nm3', 'mass_kg', 'mass_fg'.`

### `number_method_transport_rate`

```python
def number_method_transport_rate(particles_detected, diameter_nm, concentration_ng_l, acquisition_time_s, density_g_cm3)
```

Calculate transport rate using the particle-number method.

η = N_detected / (C_number × t)   →   expressed in µL/s.


**Args:**

- `particles_detected (int): Number of detected particle events.`
- `diameter_nm (float): Certified particle diameter (nm).`
- `concentration_ng_l (float): Particle mass concentration (ng/L).`
- `acquisition_time_s (float): Total acquisition time (s).`
- `density_g_cm3 (float): Element density (g/cm³).`


**Returns:**

- `dict: 'transport_rate_ul_s', 'particles_per_ml', 'particle_mass_fg',`
- `'particle_volume_nm3', 'status'.`

### `weight_method_transport_rate`

```python
def weight_method_transport_rate(w_initial_g, w_final_g, w_waste_g, time_s)
```

Calculate transport rate using the liquid-weight method.


**Args:**

- `w_initial_g (float): Initial sample mass (g).`
- `w_final_g (float): Final sample mass (g).`
- `w_waste_g (float): Waste container mass increase (g).`
- `time_s (float): Analysis time (seconds).`


**Returns:**

- `dict: 'transport_rate_ul_s', 'sample_consumed_g',`
- `'volume_to_plasma_g', 'status'.`


**Raises:**

- `ValueError: If any physical constraint is violated.`
