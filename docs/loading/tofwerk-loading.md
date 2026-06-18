# `tofwerk_loading.py`

Loading data from TOFWERK ICP-ToF.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `is_tofwerk_file` | `(path: Path) → bool` | Check if a file is a TOFWERK file. |
| `calibrate_index_to_mass` | `(indices: np.ndarray, mode: int, p: list[float]) → np.ndarray` | Calibrate sample indices to mass / charge. |
| `calibrate_mass_to_index` | `(masses: np.ndarray, mode: int, p: list[float]) → np.ndarray` | Calibrate mass / charge to sample indices. |
| `factor_extraction_to_acquisition` | `(h5: h5py._hl.files.File) → float` | Calculate factor for extraction to acquisition conversion. |
| `integrate_tof_data` | `(h5: h5py._hl.files.File, idx: np.ndarray \| None=None, progress_callba` | Integrate TofData to recreate PeakData. |
| `read_tofwerk_file` | `(path: Path \| str, idx: np.ndarray \| None=None, progress_callback=None` | Read a TOFWERK TofDaq .hdf file and return peak data and peak info. |
