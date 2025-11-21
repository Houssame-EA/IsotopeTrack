"""Loading data from Nu Instruments."""
import json
import logging
from math import gamma
from pathlib import Path
from typing import BinaryIO, Generator

import numpy as np
import numpy.lib.recfunctions as rfn
from scipy.special import gammainc

logger = logging.getLogger(__name__)


def is_nu_run_info_file(path: Path) -> bool:
    """
    Check if file exists and is called 'run.info'.
    
    Args:
        path (Path): Path to check
        
    Returns:
        bool: True if file exists and is named 'run.info'
    """
    if not path.exists() or path.name != "run.info":
        return False
    return True


def is_nu_directory(path: Path) -> bool:
    """
    Check if path is a directory containing 'run.info' and 'integrated.index'.
    
    Args:
        path (Path): Path to check
        
    Returns:
        bool: True if valid Nu directory
    """
    if not path.is_dir() or not path.exists():
        return False
    if not path.joinpath("run.info").exists():
        return False
    if not path.joinpath("integrated.index").exists(): 
        return False

    return True


def blank_nu_signal_data(
    autob_events: list[np.ndarray],
    signals: np.ndarray,
    masses: np.ndarray,
    num_acc: int,
    start_coef: tuple[float, float],
    end_coef: tuple[float, float],
) -> np.ndarray:
    """
    Apply auto-blanking to the integrated data.
    
    There must be one cycle/segment and no missing acquisitions/data.

    Args:
        autob_events (list[np.ndarray]): List of events from read_nu_autob_binary
        signals (np.ndarray): Concatenated data from read_nu_integ_data_binary
        masses (np.ndarray): 1D array of masses from get_masses_from_nu_data
        num_acc (int): Number of accumulations per acquisition
        start_coef (tuple[float, float]): Blanker open coefficients 'BlMassCalStartCoef'
        end_coef (tuple[float, float]): Blanker close coefficients 'BlMassCalEndCoef'

    Returns:
        np.ndarray: Blanked data
    """
    start_event = None
    for event in autob_events:
        if event["type"] == 0 and start_event is None:
            start_event = event
        elif event["type"] == 1 and start_event is not None:
            start_masses = (
                start_coef[0] + start_coef[1] * start_event["edges"][0][::2] * 1.25
            ) ** 2
            end_masses = (
                end_coef[0] + end_coef[1] * start_event["edges"][0][1::2] * 1.25
            ) ** 2
            mass_idx = np.searchsorted(masses, (start_masses, end_masses))
            mass_idx = mass_idx[:, mass_idx[0] != mass_idx[1]]

            acq_start, acq_end = (
                int(start_event["acq_number"][0] // num_acc) - 1,
                int(event["acq_number"][0] // num_acc) - 1,
            )

            for s, e in mass_idx.T:
                signals[acq_start:acq_end, s:e] = np.nan

            start_event = None

    return signals


def collect_nu_autob_data(
    root: Path,
    index: list[dict],
    cyc_number: int | None = None,
    seg_number: int | None = None,
) -> list[np.ndarray]:
    """
    Collect Nu autoblank data from multiple files.
    
    Args:
        root (Path): Root directory path
        index (list[dict]): List of index dictionaries
        cyc_number (int | None): Cycle number to filter, or None for all
        seg_number (int | None): Segment number to filter, or None for all
        
    Returns:
        list[np.ndarray]: List of autoblank event arrays
    """
    autobs = []
    for idx in index:
        autob_path = root.joinpath(f"{idx['FileNum']}.autob")
        if autob_path.exists():
            events = read_nu_autob_binary(
                autob_path,
                idx["FirstCycNum"],
                idx["FirstSegNum"],
                idx["FirstAcqNum"],
            )
            if cyc_number is not None:
                events = [ev for ev in events if ev["cyc_number"] == cyc_number]
            if seg_number is not None:
                events = [ev for ev in events if ev["seg_number"] == seg_number]
            autobs.extend(events)
        else:
            logger.warning(
                f"collect_nu_autob_data: missing autob {idx['FileNum']}, skipping"
            )
    return autobs


def collect_nu_integ_data(
    root: Path,
    index: list[dict],
    cyc_number: int | None = None,
    seg_number: int | None = None,
) -> list[np.ndarray]:
    """
    Collect Nu integrated data from multiple files.
    
    Args:
        root (Path): Root directory path
        index (list[dict]): List of index dictionaries
        cyc_number (int | None): Cycle number to filter, or None for all
        seg_number (int | None): Segment number to filter, or None for all
        
    Returns:
        list[np.ndarray]: List of integrated data arrays
    """
    integs = []
    for idx in index:
        integ_path = root.joinpath(f"{idx['FileNum']}.integ")
        if integ_path.exists():
            data = read_nu_integ_binary(
                integ_path,
                idx["FirstCycNum"],
                idx["FirstSegNum"],
                idx["FirstAcqNum"],
            )
            if cyc_number is not None:
                data = data[data["cyc_number"] == cyc_number]
            if seg_number is not None:
                data = data[data["seg_number"] == seg_number]
            if data.size > 0:
                integs.append(data)
        else:
            logger.warning(
                f"collect_nu_integ_data: missing integ {idx['FileNum']}, skipping"
            )
    return integs


def get_dwelltime_from_info(info: dict) -> float:
    """
    Read the dwell time (total acquisition time) from run.info.
    
    Rounds to the nearest nanosecond.

    Args:
        info (dict): Dictionary of parameters from read_nu_directory

    Returns:
        float: Dwell time in seconds
    """
    seg = info["SegmentInfo"][0]
    acqtime = seg["AcquisitionPeriodNs"] * 1e-9
    accumulations = info["NumAccumulations1"] * info["NumAccumulations2"]
    return np.around(acqtime * accumulations, 9)


def get_signals_from_nu_data(integs: list[np.ndarray], num_acc: int) -> np.ndarray:
    """
    Convert signals from integ data to counts.

    Preserves run length when missing data is present.
    Modified to handle multiple cycles.

    Args:
        integs (list[np.ndarray]): List of data from read_integ_binary
        num_acc (int): Number of accumulations per acquisition

    Returns:
        np.ndarray: Signals in counts
    """
    all_cycles = set()
    for integ in integs:
        if integ.size > 0:
            all_cycles.update(np.unique(integ["cyc_number"]))
    all_cycles = sorted(all_cycles)
    
    max_acq_per_cycle = {}
    for cycle in all_cycles:
        cycle_max = 0
        for integ in integs:
            if integ.size > 0:
                mask = integ["cyc_number"] == cycle
                if np.any(mask):
                    cycle_max = max(cycle_max, np.max(integ["acq_number"][mask]))
        max_acq_per_cycle[cycle] = cycle_max
    
    signal_length = 0
    for cycle in all_cycles:
        signal_length += max_acq_per_cycle[cycle] // num_acc
    
    signal_width = integs[0]["result"]["signal"].shape[1] if integs[0].size > 0 else 0
    signals = np.full((signal_length, signal_width), np.nan, dtype=np.float32)
    
    current_offset = 0
    for cycle in all_cycles:
        cycle_length = max_acq_per_cycle[cycle] // num_acc
        
        for integ in integs:
            if integ.size == 0:
                continue
            
            mask = integ["cyc_number"] == cycle
            if not np.any(mask):
                continue
            
            cycle_data = integ[mask]
            
            for i in range(len(cycle_data)):
                idx = (cycle_data["acq_number"][i] // num_acc) - 1 + current_offset
                if 0 <= idx < len(signals):
                    signals[idx] = cycle_data["result"]["signal"][i]
        
        current_offset += cycle_length
    
    return signals


def get_masses_from_nu_data(
    integ: np.ndarray, cal_coef: tuple[float, float], segment_delays: dict[int, float]
) -> np.ndarray:
    """
    Convert Nu peak centers into masses.

    Args:
        integ (np.ndarray): Data from read_integ_binary
        cal_coef (tuple[float, float]): Calibration coefficients from run.info 'MassCalCoefficients'
        segment_delays (dict[int, float]): Dictionary of segment numbers and delays from SegmentInfo

    Returns:
        np.ndarray: 2D array of masses
    """
    delays = np.zeros(max(segment_delays.keys()))
    for k, v in segment_delays.items():
        delays[k - 1] = v
    delays = np.atleast_1d(delays[integ["seg_number"] - 1])

    masses = (integ["result"]["center"] * 0.5) + delays[:, None]
    return (cal_coef[0] + masses * cal_coef[1]) ** 2


def read_nu_autob_binary(
    path: Path,
    first_cyc_number: int | None = None,
    first_seg_number: int | None = None,
    first_acq_number: int | None = None,
) -> list[np.ndarray]:
    """
    Read Nu autoblank binary file.
    
    Args:
        path (Path): Path to .autob file
        first_cyc_number (int | None): Expected first cycle number
        first_seg_number (int | None): Expected first segment number
        first_acq_number (int | None): Expected first acquisition number
        
    Returns:
        list[np.ndarray]: List of autoblank event arrays
    """
    def autob_dtype(size: int) -> np.dtype:
        return np.dtype(
            [
                ("cyc_number", np.uint32),
                ("seg_number", np.uint32),
                ("acq_number", np.uint32),
                ("trig_start_time", np.uint32),
                ("trig_end_time", np.uint32),
                ("type", np.uint8),
                ("num_edges", np.int32),
                ("edges", np.uint32, size),
            ]
        )

    def read_autob_events(fp: BinaryIO) -> Generator[np.ndarray, None, None]:
        while fp:
            data = fp.read(4 + 4 + 4 + 4 + 4 + 1 + 4)
            if not data:
                return
            size = int.from_bytes(data[-4:], "little")
            autob = np.empty(1, dtype=autob_dtype(size))
            autob.data.cast("B")[: len(data)] = data
            if size > 0:
                autob["edges"] = np.frombuffer(fp.read(size * 4), dtype=np.uint32)
            yield autob

    with path.open("rb") as fp:
        autob_events = list(read_autob_events(fp))

    return autob_events


def read_nu_integ_binary(
    path: Path,
    first_cyc_number: int | None = None,
    first_seg_number: int | None = None,
    first_acq_number: int | None = None,
) -> np.ndarray:
    """
    Read Nu integrated binary file.
    
    Args:
        path (Path): Path to .integ file
        first_cyc_number (int | None): Expected first cycle number
        first_seg_number (int | None): Expected first segment number
        first_acq_number (int | None): Expected first acquisition number
        
    Returns:
        np.ndarray: Integrated data array
    """
    def integ_dtype(size: int) -> np.dtype:
        data_dtype = np.dtype(
            {
                "names": ["center", "signal"],
                "formats": [np.float32, np.float32],
                "itemsize": 4 + 4 + 4 + 1, 
            }
        )
        return np.dtype(
            [
                ("cyc_number", np.uint32),
                ("seg_number", np.uint32),
                ("acq_number", np.uint32),
                ("num_results", np.uint32),
                ("result", data_dtype, size),
            ]
        )

    with path.open("rb") as fp:
        cyc_number = int.from_bytes(fp.read(4), "little")
        if first_cyc_number is not None and cyc_number != first_cyc_number:
            raise ValueError("read_integ_binary: incorrect FirstCycNum")
        seg_number = int.from_bytes(fp.read(4), "little")
        if first_seg_number is not None and seg_number != first_seg_number:
            raise ValueError("read_integ_binary: incorrect FirstSegNum")
        acq_number = int.from_bytes(fp.read(4), "little")
        if first_acq_number is not None and acq_number != first_acq_number:
            raise ValueError("read_integ_binary: incorrect FirstAcqNum")
        num_results = int.from_bytes(fp.read(4), "little")
        fp.seek(0)

        return np.frombuffer(fp.read(), dtype=integ_dtype(num_results))


def read_nu_directory(
    path: str | Path,
    max_integ_files: int | None = None,
    autoblank: bool = True,
    cycle: int | None = None,
    segment: int | None = None,
    raw: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Read the Nu Instruments raw data directory, returning data and run info.

    Directory must contain 'run.info', 'integrated.index' and at least one '.integ'
    file. Data is read from '.integ' files listed in the 'integrated.index' and
    are checked for correct starting cycle, segment and acquisition numbers.

    Args:
        path (str | Path): Path to data directory
        max_integ_files (int | None): Maximum number of files to read
        autoblank (bool): Apply autoblanking to overrange regions
        cycle (int | None): Limit import to cycle
        segment (int | None): Limit import to segment
        raw (bool): Return raw ADC counts

    Returns:
        tuple: (masses, signals, run_info) where:
            - masses (np.ndarray): Masses from first acquisition
            - signals (np.ndarray): Signals in counts
            - run_info (dict): Dictionary of parameters from run.info
    """
    path = Path(path)
    if not is_nu_directory(path): 
        raise ValueError("read_nu_directory: missing 'run.info' or 'integrated.index'")

    with path.joinpath("run.info").open("r") as fp:
        run_info = json.load(fp)
    with path.joinpath("autob.index").open("r") as fp:
        autob_index = json.load(fp)
    with path.joinpath("integrated.index").open("r") as fp:
        integ_index = json.load(fp)

    if max_integ_files is not None:
        integ_index = integ_index[:max_integ_files]

    segment_delays = {
        s["Num"]: s["AcquisitionTriggerDelayNs"] for s in run_info["SegmentInfo"]
    }

    accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]

    integs = collect_nu_integ_data(
        path, integ_index, cyc_number=cycle, seg_number=segment
    )
    masses = get_masses_from_nu_data(
        integs[0], run_info["MassCalCoefficients"], segment_delays
    )[0]
    signals = get_signals_from_nu_data(integs, accumulations)

    if not raw:
        signals /= run_info["AverageSingleIonArea"]

    if autoblank:
        autobs = collect_nu_autob_data(
            path, autob_index, cyc_number=cycle, seg_number=segment
        )
        signals = blank_nu_signal_data(
            autobs,
            signals,
            masses,
            accumulations,
            run_info["BlMassCalStartCoef"],
            run_info["BlMassCalEndCoef"],
        )
        
    return masses, signals, run_info


def select_nu_signals(
    masses: np.ndarray,
    signals: np.ndarray,
    selected_masses: dict[str, float],
    max_mass_diff: float = 0.1,
) -> np.ndarray:
    """
    Reduce signals to the isotopes in selected_masses.
    
    'masses' must be sorted.

    Args:
        masses (np.ndarray): Masses from read_nu_directory
        signals (np.ndarray): Signals from read_nu_directory
        selected_masses (dict[str, float]): Dictionary of isotope name to mass
        max_mass_diff (float): Maximum difference (Da) from mass to allow

    Returns:
        np.ndarray: Structured array of signals

    Raises:
        ValueError: If the smallest mass difference from 'selected_masses' is
            greater than 'max_mass_diff'
    """
    def find_closest_idx(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(x, y, side="left")
        prev_less = np.abs(y - x[np.maximum(idx - 1, 0)]) < np.abs(
            y - x[np.minimum(idx, len(x) - 1)]
        )
        prev_less = (idx == len(x)) | prev_less
        idx[prev_less] -= 1
        return idx

    assert np.all(masses[:-1] <= masses[1:])

    selected = np.fromiter(selected_masses.values(), dtype=np.float32)
    idx = find_closest_idx(masses, selected)

    diffs = np.abs(masses[idx] - selected)

    if np.any(diffs > max_mass_diff):
        raise ValueError(
            "select_nu_signals: could not find mass closer than 'max_mass_diff'"
        )

    dtype = np.dtype(
        {
            "names": list(selected_masses.keys()),
            "formats": [np.float32 for _ in idx],
        }
    )
    return rfn.unstructured_to_structured(signals[:, idx], dtype=dtype)


def single_ion_distribution(
    counts: np.ndarray, bins: str | int | np.ndarray = "auto"
) -> np.ndarray:
    """
    Calculate the single ion distribution from calibration data.

    SIA is calculated as an average of all isotopes with a >1e-5 and <1e-3
    chance of containing a two ion event.

    Args:
        counts (np.ndarray): Raw ADC counts
        bins (str | int | np.ndarray): Binning of histogram, see np.histogram_bin_edges

    Returns:
        np.ndarray: Array of stacked bin centers and counts
    """
    pzeros = np.count_nonzero(counts, axis=0) / counts.shape[0]
    
    poi2 = gammainc(3, pzeros) 
    
    x = counts[:, (poi2 > 1e-5) & (poi2 < 1e-3)]
    
    hist, bins = np.histogram(x[x > 0], bins=bins)
    return np.stack(((bins[1:] + bins[:-1]) / 2.0, hist), axis=1)