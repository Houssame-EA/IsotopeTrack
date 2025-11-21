from PySide6.QtCore import QThread, Signal
from pathlib import Path
import json
import numpy as np
import data_loading.vitesse_loading
import data_loading.tofwerk_loading

class DataProcessThread(QThread):
    """
    Thread for processing data from Nu Instruments or TOFWERK formats.
    Handles loading, mass selection, and data extraction in background.
    """
    
    progress = Signal(int)
    finished = Signal(object, object, object, str, str)
    error = Signal(str)

    def __init__(self, folder_path, selected_masses, sample_name):
        """
        Initialize the data processing thread.
        
        Args:
            folder_path (str): Path to data folder or file
            selected_masses (list): List of masses to extract
            sample_name (str): Name of the sample
            
        Returns:
            None
        """
        QThread.__init__(self)  
        self.folder_path = folder_path
        self.selected_masses = selected_masses
        self.sample_name = sample_name  
        self.max_mass_diff = 0.5

    @staticmethod
    def detect_data_format(folder_path):
        """
        Detect whether data is Nu Instruments or TOFWERK format.
        
        Args:
            folder_path (str): Path to data folder or file
            
        Returns:
            str: Data format ('nu', 'tofwerk', or 'unknown')
        """
        path = Path(folder_path)
        
        if path.is_dir() and (path / "run.info").exists():
            return "nu"
        
        if path.is_file() and data_loading.tofwerk_loading.is_tofwerk_file(path):
            return "tofwerk"
        
        if path.is_dir():
            h5_files = list(path.glob("*.h5"))
            if h5_files and any(data_loading.tofwerk_loading.is_tofwerk_file(f) for f in h5_files):
                return "tofwerk"
        
        return "unknown"

    @staticmethod
    def get_masses_only(folder_path):
        """
        Extract only masses from the data directory without loading full signals.
        
        Args:
            folder_path (str): Path to data folder or file
            
        Returns:
            np.ndarray | None: Array of masses or None if error
        """
        try:
            path = Path(folder_path)
            data_format = DataProcessThread.detect_data_format(folder_path)
            
            print(f"\n=== DEBUG: get_masses_only ===")
            print(f"Path: {path}")
            print(f"Data format detected: {data_format}")
            
            if data_format == "nu":
                masses, _, _ = data_loading.vitesse_loading.read_nu_directory(
                    path=folder_path,
                    max_integ_files=1,
                    autoblank=False,
                    raw=False
                )
                print(f"NU masses found: {len(masses)} masses")
                return masses
            
            elif data_format == "tofwerk":
                print(f"Processing TOFWERK file...")
                
                if path.is_file():
                    h5_file = path
                    print(f"Using file: {h5_file}")
                else:
                    h5_files = [f for f in path.glob("*.h5") if data_loading.tofwerk_loading.is_tofwerk_file(f)]
                    if not h5_files:
                        print("No .h5 files found in directory")
                        return None
                    h5_file = h5_files[0]
                    print(f"Using first .h5 file in directory: {h5_file}")
                
                print(f"Reading TOFWERK file...")
                data, info, dwell_time = data_loading.tofwerk_loading.read_tofwerk_file(h5_file)
                
                print(f"\n--- TOFWERK FILE STRUCTURE ---")
                print(f"Data shape: {data.shape}")
                print(f"Data dtype: {data.dtype}")
                if hasattr(data.dtype, 'names') and data.dtype.names:
                    print(f"Data field names: {data.dtype.names}")
                    print(f"Number of fields: {len(data.dtype.names)}")
                
                print(f"\nInfo shape: {info.shape}")
                print(f"Info dtype: {info.dtype}")
                print(f"Info field names: {info.dtype.names}")
                
                print(f"\nDwell time: {dwell_time}")
                
                print(f"\nFirst 5 entries of info:")
                for i in range(min(5, len(info))):
                    print(f"  Entry {i}: {info[i]}")
                
                if 'mass' in info.dtype.names:
                    masses = info['mass']
                    print(f"\nFound 'mass' field in info")
                    print(f"Mass values (first 10): {masses[:10]}")
                    print(f"Mass range: {np.min(masses):.4f} to {np.max(masses):.4f}")
                else:
                    print(f"\nNo 'mass' field found, trying to extract from labels...")
                    print(f"Label field sample: {info['label'][:5]}")
                    try:
                        masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                         for label in info['label']])
                        print(f"Successfully extracted masses from labels")
                        print(f"Mass values (first 10): {masses[:10]}")
                        print(f"Mass range: {np.min(masses):.4f} to {np.max(masses):.4f}")
                    except Exception as e:
                        print(f"Failed to extract masses from labels: {e}")
                        return None
                
                print(f"Total masses found: {len(masses)}")
                print(f"=== END DEBUG ===\n")
                return masses
                
        except Exception as e:
            print(f"Error getting masses: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def find_closest_masses(self, available_masses, target_masses, max_diff=0.5):
        """
        Find the closest available masses to the target masses within tolerance.
        
        Args:
            available_masses (np.ndarray): Array of available masses
            target_masses (list): List of target masses
            max_diff (float): Maximum allowed difference
            
        Returns:
            dict: Mapping of target masses to actual masses
        """
        mass_mapping = {}
        for target in target_masses:
            differences = np.abs(available_masses - target)
            min_diff_idx = np.argmin(differences)
            min_diff = differences[min_diff_idx]
            
            if min_diff <= max_diff:
                mass_mapping[target] = available_masses[min_diff_idx]
            
        return mass_mapping

    def process_nu_data(self):
        """
        Process Nu Instruments data.
        
        Args:
            None
            
        Returns:
            tuple: (selected_data_dict, run_info, time_array, analysis_datetime)
        """
        run_info_path = Path(self.folder_path) / "run.info"
        if not run_info_path.exists():
            raise FileNotFoundError(f"run.info not found in {self.folder_path}")

        with open(run_info_path, "r") as fp:
            run_info = json.load(fp)
        analysis_datetime = run_info.get("AnalysisDateTime", "Unknown")
        self.progress.emit(10)
        
        seg = run_info["SegmentInfo"][0]
        acqtime = seg["AcquisitionPeriodNs"] * 1e-9
        accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
        dwell_time = acqtime * accumulations

        self.progress.emit(20)
        masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(
            path=self.folder_path,
            max_integ_files=None,
            autoblank=True,
            cycle=None,
            segment=None,
            raw=False
        )
        
        self.progress.emit(60)

        mass_mapping = self.find_closest_masses(masses, self.selected_masses)
        
        if not mass_mapping:
            raise ValueError("No matching masses found within tolerance. Available masses: " + 
                        ", ".join(f"{m:.4f}" for m in masses))

        selected_masses_dict = {
            f"{int(target_mass)}": actual_mass 
            for target_mass, actual_mass in mass_mapping.items()
        }
        
        self.progress.emit(75)

        selected_data = data_loading.vitesse_loading.select_nu_signals(
            masses=masses,
            signals=signals,
            selected_masses=selected_masses_dict,
            max_mass_diff=self.max_mass_diff
        )
        
        self.progress.emit(90)

        selected_data_dict = {}
        for target_mass in self.selected_masses:
            if target_mass in mass_mapping:
                actual_mass = mass_mapping[target_mass]
                label = f"{int(target_mass)}"
                if label in selected_data.dtype.names:
                    selected_data_dict[target_mass] = selected_data[label].copy()

        time_array = np.arange(len(signals)) * dwell_time
        
        return selected_data_dict, run_info, time_array, analysis_datetime

    def process_tofwerk_data(self):
        """
        Process TOFWERK data.
        
        Args:
            None
            
        Returns:
            tuple: (selected_data_dict, run_info, time_array, analysis_datetime)
        """
        path = Path(self.folder_path)
        
        print(f"\n=== DEBUG: process_tofwerk_data ===")
        print(f"Processing path: {path}")
        print(f"Selected masses: {self.selected_masses}")
        
        if path.is_file():
            h5_file = path
            print(f"Using single file: {h5_file}")
        else:
            h5_files = [f for f in path.glob("*.h5") if data_loading.tofwerk_loading.is_tofwerk_file(f)]
            if not h5_files:
                raise FileNotFoundError("No valid TOFWERK .h5 files found")
            h5_file = h5_files[0]
            print(f"Using first .h5 file in directory: {h5_file}")
        
        self.progress.emit(20)
        
        print(f"Reading TOFWERK data...")
        data, info, dwell_time = data_loading.tofwerk_loading.read_tofwerk_file(h5_file)
        
        print(f"\n--- TOFWERK DATA PROCESSING ---")
        print(f"Data shape: {data.shape}")
        print(f"Data dtype: {data.dtype}")
        if hasattr(data.dtype, 'names') and data.dtype.names:
            print(f"Data field names: {list(data.dtype.names)}")
            print(f"First few field names: {list(data.dtype.names)[:10]}")
        
        print(f"Info shape: {info.shape}")
        print(f"Dwell time: {dwell_time}")
        
        self.progress.emit(60)
        
        if 'mass' in info.dtype.names:
            masses = info['mass']
            print(f"Using 'mass' field from info")
        else:
            print(f"No 'mass' field, extracting from labels...")
            try:
                masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                 for label in info['label']])
                print(f"Successfully extracted masses from labels")
            except Exception as e:
                print(f"Failed to extract masses from labels: {e}")
                raise ValueError("Could not extract masses from TOFWERK data")
        
        print(f"Available masses: {masses[:10]}... (showing first 10)")
        print(f"Mass range: {np.min(masses):.4f} to {np.max(masses):.4f}")
        
        mass_mapping = self.find_closest_masses(masses, self.selected_masses)
        print(f"Mass mapping found: {mass_mapping}")
        
        if not mass_mapping:
            raise ValueError("No matching masses found within tolerance. Available masses: " + 
                        ", ".join(f"{m:.4f}" for m in masses[:20]))
        
        self.progress.emit(75)
        
        selected_data_dict = {}
        print(f"\nExtracting data for selected masses...")
        
        for target_mass in self.selected_masses:
            if target_mass in mass_mapping:
                actual_mass = mass_mapping[target_mass]
                print(f"Processing target mass {target_mass} -> actual mass {actual_mass}")
                
                mass_idx = np.argmin(np.abs(masses - actual_mass))
                print(f"Mass index: {mass_idx}")
                
                if hasattr(data.dtype, 'names') and data.dtype.names and len(data.dtype.names) > mass_idx:
                    field_name = data.dtype.names[mass_idx]
                    print(f"Using field name: {field_name}")
                    selected_data_dict[target_mass] = data[field_name].copy()
                    print(f"Data shape for this mass: {selected_data_dict[target_mass].shape}")
                    print(f"Data sample (first 5 values): {selected_data_dict[target_mass][:5]}")
                else:
                    print(f"Fallback: using array indexing")
                    if len(data.shape) > 1 and data.shape[1] > mass_idx:
                        selected_data_dict[target_mass] = data[:, mass_idx].copy()
                        print(f"Data shape for this mass: {selected_data_dict[target_mass].shape}")
                    else:
                        selected_data_dict[target_mass] = data.copy()
                        print(f"Using entire data array (single mass?)")
        
        print(f"Successfully extracted data for {len(selected_data_dict)} masses")
        
        self.progress.emit(90)
        
        time_array = np.arange(len(data)) * dwell_time
        print(f"Time array length: {len(time_array)}, range: {time_array[0]:.6f} to {time_array[-1]:.6f}")
        
        run_info = {
            "DataFormat": "TOFWERK",
            "DwellTime": dwell_time,
            "NumberOfMasses": len(masses),
            "OriginalFile": str(h5_file)
        }
        
        analysis_datetime = "Unknown"
        
        print(f"=== END DEBUG ===\n")
        return selected_data_dict, run_info, time_array, analysis_datetime

    def run(self):
        """
        Execute the data processing thread.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            self.progress.emit(0)
            
            data_format = self.detect_data_format(self.folder_path)
            print(f"\nProcessing {data_format} format for sample: {self.sample_name}")
            
            if data_format == "nu":
                selected_data_dict, run_info, time_array, analysis_datetime = self.process_nu_data()
            elif data_format == "tofwerk":
                selected_data_dict, run_info, time_array, analysis_datetime = self.process_tofwerk_data()
            else:
                raise ValueError(f"Unknown data format in {self.folder_path}")
            
            self.progress.emit(100)
            print(f"Successfully processed {self.sample_name} - {len(selected_data_dict)} masses extracted")
            self.finished.emit(selected_data_dict, run_info, time_array, self.sample_name, analysis_datetime)

        except Exception as e:
            print(f"Error processing {self.sample_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"Processing error: {str(e)}")