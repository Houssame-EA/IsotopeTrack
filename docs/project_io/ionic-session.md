# `ionic_session.py`

---

## Classes

### `NumpyEncoder` *(extends `json.JSONEncoder`)*

Custom JSON encoder for NumPy data types.

Converts NumPy arrays and numeric types to JSON-serializable Python types.

| Method | Signature | Description |
|--------|-----------|-------------|
| `default` | `(self, obj)` | Default encoder for NumPy types. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `convert_numpy_types` | `(obj)` | Recursively convert NumPy types to Python native types. |
| `save_session_to_csv` | `(file_path: str, session_data: Dict[str, Any], ionic_window=None) → No` | Save session data to CSV format including summary statistics for first 5 seconds. |
| `extract_5sec_summary_stats` | `(ionic_window) → Dict[str, Any]` | Extract summary statistics for first 5 seconds for each selected isotope. |
| `save_summary_csv` | `(base_file_path: str, summary_stats: Dict[str, Any]) → None` | Save summary statistics to a separate CSV file. |
| `load_session_from_csv` | `(file_path: str) → Dict[str, Any]` | Load session data from CSV format. |
| `load_summary_stats_from_csv` | `(base_file_path: str) → Dict[str, Any]` | Load summary statistics from CSV file. |
