# `fast_project_io.py`

---

## Constants

| Name | Value |
|------|-------|
| `FORMAT_V2_MAGIC` | `b'ITPROJ_V2\n'` |
| `FORMAT_V1_GZIP_MAGIC` | `b'\x1f\x8b'` |
| `_ELEMENT_DICT_KEYS` | `['elements', 'element_mass_fg', 'element_moles_...` |
| `_SCALAR_KEYS` | `['start_time', 'end_time', 'left_idx', 'right_i...` |

## Functions

### `_particles_to_columnar`

```python
def _particles_to_columnar(particles)
```

Convert a list of particle dicts to a columnar dict of numpy arrays.

This is 10-100x smaller and faster to serialize than a list of dicts
because repeated key strings are eliminated and numpy arrays compress
much better than pickled Python objects.


**Args:**

- `particles (list): List of particle dictionaries from sample_particle_data`


**Returns:**

- `dict: Columnar representation with:`
- `- 'n': int, number of particles`
- `- 'element_labels': list of str, ordered element display labels`
- `- 'scalars': dict of key -> numpy array (float64) for scalar fields`
- `- 'element_arrays': dict of dict_key -> 2D numpy array (n_particles x n_elements)`
- `- 'totals': dict of key -> numpy array`
- `- 'extra_keys': pickled dict for any non-standard keys`

### `_columnar_to_particles`

```python
def _columnar_to_particles(col_data)
```

Reconstruct list of particle dicts from columnar representation.


**Args:**

- `col_data (dict): Columnar data from _particles_to_columnar`


**Returns:**

- `list: List of particle dictionaries matching the original format`

### `save_project_v2`

```python
def save_project_v2(filepath, mw, progress_callback = None)
```

Save project in optimized v2 format.

Uses ZIP archive with separate numpy files per sample, lz4-compressed
pickle for metadata, and columnar particle storage.


**Args:**

- `filepath (str or Path): Output file path (.itproj)`
- `mw: MainWindow instance with all data attributes`
- `progress_callback (callable, optional): func(percent, message) for progress updates`


**Returns:**

- `bool: True on success`

### `load_project_v2`

```python
def load_project_v2(filepath, mw, progress_callback = None)
```

Load project from v2 format.


**Args:**

- `filepath (str or Path): Input file path (.itproj)`
- `mw: MainWindow instance to populate`
- `progress_callback (callable, optional): func(percent, message) for progress updates`


**Returns:**

- `bool: True on success`

### `_restore_metadata`

```python
def _restore_metadata(mw, metadata)
```

Restore metadata dict to MainWindow attributes.


**Args:**

- `mw: MainWindow instance`
- `metadata (dict): Metadata dictionary from save`

### `load_project_v1`

```python
def load_project_v1(filepath, mw, progress_callback = None)
```

Load project from old v1 gzip+pickle format.

This is the original format - just loads the old way.


**Args:**

- `filepath (str or Path): Input file path (.itproj)`
- `mw: MainWindow instance to populate`
- `progress_callback (callable, optional): func(percent, message)`


**Returns:**

- `dict: The loaded project_data dictionary (for the existing`
- `ProjectManager._restore_project_data to process)`

### `detect_format`

```python
def detect_format(filepath)
```

Detect project file format version.


**Args:**

- `filepath (str or Path): File path to check`


**Returns:**

- `int: Format version (1 for old gzip+pickle, 2 for new ZIP)`

### `load_project_auto`

```python
def load_project_auto(filepath, mw, progress_callback = None)
```

Auto-detect format and load project.

Supports both v1 (legacy gzip+pickle) and v2 (optimized ZIP) formats.


**Args:**

- `filepath (str or Path): Input file path`
- `mw: MainWindow instance`
- `progress_callback (callable, optional): func(percent, message)`


**Returns:**

- `For v2: True (data already restored to mw)`
- `For v1: dict (project_data for existing _restore_project_data to handle)`

### `estimate_project_size`

```python
def estimate_project_size(mw)
```

Estimate uncompressed project size for progress bar calibration.


**Args:**

- `mw: MainWindow instance`


**Returns:**

- `dict: Size estimates with keys 'arrays_mb', 'particles_mb', 'metadata_mb', 'total_mb'`
