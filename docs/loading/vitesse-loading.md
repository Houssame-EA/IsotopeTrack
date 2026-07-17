# `vitesse_loading.py`

Loading data from Nu Instruments.

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `open_nu_binary` | `(path: Path) → BinaryIO` | Open a Nu binary file, transparently decompressing gzip if needed. |
| `is_nu_run_info_file` | `(path: Path) → bool` | Check if file exists and is called 'run.info'. |
| `is_nu_directory` | `(path: Path) → bool` | Check if path is a directory containing 'run.info' and 'integrated.index'. |
| `blank_nu_signal_data` | `(autob_events: list[np.ndarray], signals: np.ndarray, masses: np.ndarr` | Apply auto-blanking to the integrated data. |
| `collect_nu_autob_data` | `(root: Path, index: list[dict], cyc_number: int \| None=None, seg_numbe` | Collect Nu autoblank data from multiple files. |
| `collect_nu_integ_data` | `(root: Path, index: list[dict], cyc_number: int \| None=None, seg_numbe` | Collect Nu integrated data from multiple files. |
| `get_dwelltime_from_info` | `(info: dict) → float` | Read the dwell time (total acquisition time) from run.info. |
| `get_signals_from_nu_data` | `(integs: list[np.ndarray], num_acc: int) → np.ndarray` | Convert signals from integ data to counts. |
| `get_masses_from_nu_data` | `(integ: np.ndarray, cal_coef: tuple[float, float], segment_delays: dic` | Convert Nu peak centers into masses. |
| `read_nu_autob_binary` | `(path: Path, first_cyc_number: int \| None=None, first_seg_number: int ` | Read Nu autoblank binary file. |
| `read_nu_integ_binary` | `(path: Path, first_cyc_number: int \| None=None, first_seg_number: int ` | Read Nu integrated binary file. |
| `read_nu_directory` | `(path: str \| Path, max_integ_files: int \| None=None, autoblank: bool=T` | Read the Nu Instruments raw data directory, returning data and run info. |
| `select_nu_signals` | `(masses: np.ndarray, signals: np.ndarray, selected_masses: dict[str, f` | Reduce signals to the isotopes in selected_masses. |
| `single_ion_distribution` | `(counts: np.ndarray, bins: str \| int \| np.ndarray='auto') → np.ndarray` | Calculate the single ion distribution from calibration data. |
