# `data_thread.py`

---

## Classes

### `DataProcessThread` *(extends `QThread`)*

Thread for processing data from Nu Instruments or TOFWERK formats.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, folder_path, selected_masses, sample_name)` | Initialize the data processing thread. |
| `cleanup` | `(self)` | Disconnect all signals so this thread object can be garbage-collected. |
| `detect_data_format` | `(folder_path)` | Detect whether data is Nu Instruments or TOFWERK format. |
| `get_masses_only` | `(folder_path)` | Extract only masses from the data directory without loading full signals. |
| `find_closest_masses` | `(self, available_masses, target_masses, max_diff=0.5)` | Find the closest available masses to the target masses within tolerance. |
| `process_nu_data` | `(self)` | Process Nu Instruments data. |
| `process_tofwerk_data` | `(self)` | Process TOFWERK data. |
| `run` | `(self)` | Execute the data processing thread. |
