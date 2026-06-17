# `fast_project_io.py`

---

## Constants

| Name | Value |
|------|-------|
| `FORMAT_V2_MAGIC` | `b'ITPROJ_V2\n'` |
| `FORMAT_V1_GZIP_MAGIC` | `b'\x1f\x8b'` |
| `_ELEMENT_DICT_KEYS` | `['elements', 'element_mass_fg', 'element_moles_fmol', 'pa…` |
| `_SCALAR_KEYS` | `['start_time', 'end_time', 'left_idx', 'right_idx', 'max_…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_particles_to_columnar` | `(particles)` | Convert a list of particle dicts to a columnar dict of numpy arrays. |
| `_columnar_to_particles` | `(col_data)` | Reconstruct list of particle dicts from columnar representation. |
| `save_project_v2` | `(filepath, mw, progress_callback=None)` | Save project in optimized v2 format. |
| `load_project_v2` | `(filepath, mw, progress_callback=None)` | Load project from v2 format. |
| `_restore_metadata` | `(mw, metadata)` | Restore metadata dict to MainWindow attributes. |
| `load_project_v1` | `(filepath, mw, progress_callback=None)` | Load project from old v1 gzip+pickle format. |
| `detect_format` | `(filepath)` | Detect project file format version. |
| `load_project_auto` | `(filepath, mw, progress_callback=None)` | Auto-detect format and load project. |
| `estimate_project_size` | `(mw)` | Estimate uncompressed project size for progress bar calibration. |
