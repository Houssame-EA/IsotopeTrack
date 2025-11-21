import json
import csv
import numpy as np
from typing import Dict, Any
from pathlib import Path

class NumpyEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for NumPy data types.
    
    Converts NumPy arrays and numeric types to JSON-serializable Python types.
    """
    def default(self, obj):
        """
        Default encoder for NumPy types.
        
        Args:
            obj (Any): Object to encode
            
        Returns:
            Any: JSON-serializable representation of the object
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)

def convert_numpy_types(obj):
    """
    Recursively convert NumPy types to Python native types.
    
    Args:
        obj (Any): Object to convert (dict, list, np.ndarray, or scalar)
        
    Returns:
        Any: Object with NumPy types converted to Python native types
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    else:
        return obj

def save_session_to_csv(file_path: str, session_data: Dict[str, Any], ionic_window=None) -> None:
    """
    Save session data to CSV format including summary statistics for first 5 seconds.
    
    Args:
        file_path (str): Path to save the CSV file
        session_data (Dict[str, Any]): Session data dictionary
        ionic_window (object, optional): Ionic window object for extracting statistics
        
    Returns:
        None
    """
    try:
        session_data_clean = convert_numpy_types(session_data)
        
        summary_stats_5sec = {}
        if ionic_window and hasattr(ionic_window, 'data') and hasattr(ionic_window, 'selected_isotopes'):
            summary_stats_5sec = extract_5sec_summary_stats(ionic_window)
            summary_stats_5sec = convert_numpy_types(summary_stats_5sec)
        
        main_data = {
            'session_type': 'ionic_calibration',
            'selected_isotopes': json.dumps(session_data_clean['selected_isotopes'], cls=NumpyEncoder),
            'concentration_unit': session_data_clean['concentration_unit'],
            'calibration_results': json.dumps(session_data_clean['calibration_results'], cls=NumpyEncoder),
            'table_data': json.dumps(session_data_clean['table_data'], cls=NumpyEncoder),
            'isotope_method_preferences': json.dumps(session_data_clean.get('isotope_method_preferences', {}), cls=NumpyEncoder),
            'header_internal_data': json.dumps(session_data_clean.get('header_internal_data', {}), cls=NumpyEncoder),
            'summary_stats_5sec': json.dumps(summary_stats_5sec, cls=NumpyEncoder)
        }
        
        main_csv_path = file_path
        if not main_csv_path.endswith('.csv'):
            main_csv_path += '.csv'
            
        with open(main_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=main_data.keys())
            writer.writeheader()
            writer.writerow(main_data)
        
        if summary_stats_5sec:
            save_summary_csv(file_path, summary_stats_5sec)
            
        print(f"Session saved successfully to {main_csv_path}")
        
    except Exception as e:
        raise Exception(f"Failed to save session: {str(e)}")

def extract_5sec_summary_stats(ionic_window) -> Dict[str, Any]:
    """
    Extract summary statistics for first 5 seconds for each selected isotope.
    
    Args:
        ionic_window (object): Ionic window object containing data and selected isotopes
        
    Returns:
        Dict[str, Any]: Dictionary of summary statistics by sample
    """
    summary_stats = {}
    
    try:
        if not ionic_window.data or not ionic_window.selected_isotopes:
            return summary_stats
        
        for folder_path, folder_data in ionic_window.data.items():
            folder_name = Path(folder_path).name
            summary_stats[folder_name] = {
                'sample_info': {},
                'isotope_stats': {}
            }
            
            run_info = folder_data['run_info']
            sample_name = run_info.get("SampleName", folder_name)
            
            seg = run_info["SegmentInfo"][0]
            acqtime = seg["AcquisitionPeriodNs"] * 1e-9
            accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
            dwell_time = acqtime * accumulations
            
            total_points = len(folder_data['signals'])
            time_array = np.arange(total_points) * dwell_time
            five_sec_mask = time_array <= 5.0
            five_sec_points = int(np.sum(five_sec_mask))
            
            summary_stats[folder_name]['sample_info'] = {
                'sample_name': sample_name,
                'dwell_time': float(dwell_time),
                'total_points': int(total_points),
                'five_sec_points': five_sec_points,
                'five_sec_duration': float(5.0)
            }
            
            masses = folder_data['masses']
            signals = folder_data['signals']
            
            for element, isotopes in ionic_window.selected_isotopes.items():
                for isotope_mass in isotopes:
                    mass_index = np.argmin(np.abs(masses - isotope_mass))
                    actual_mass = float(masses[mass_index])
                    
                    isotope_key = f"{element}-{isotope_mass:.4f}"
                    isotope_label = ionic_window.get_isotope_label(element, isotope_mass)
                    
                    counts_5sec = signals[five_sec_mask, mass_index]
                    cps_5sec = counts_5sec / dwell_time
                    
                    summary_stats[folder_name]['isotope_stats'][isotope_key] = {
                        'element': element,
                        'isotope_mass': float(isotope_mass),
                        'actual_mass': actual_mass,
                        'isotope_label': isotope_label,
                        'mean_counts': float(np.mean(counts_5sec)),
                        'std_counts': float(np.std(counts_5sec)),
                        'min_counts': float(np.min(counts_5sec)),
                        'max_counts': float(np.max(counts_5sec)),
                        'mean_cps': float(np.mean(cps_5sec)),
                        'std_cps': float(np.std(cps_5sec)),
                        'min_cps': float(np.min(cps_5sec)),
                        'max_cps': float(np.max(cps_5sec)),
                        'median_cps': float(np.median(cps_5sec)),
                        'rsd_percent': float((np.std(cps_5sec) / np.mean(cps_5sec) * 100)) if np.mean(cps_5sec) > 0 else 0.0,
                        'total_counts_5sec': float(np.sum(counts_5sec)),
                        'data_points_5sec': len(counts_5sec)
                    }
        
    except Exception as e:
        print(f"Error extracting summary statistics: {str(e)}")
        return {}
    
    return summary_stats

def save_summary_csv(base_file_path: str, summary_stats: Dict[str, Any]) -> None:
    """
    Save summary statistics to a separate CSV file.
    
    Args:
        base_file_path (str): Base file path for the summary CSV
        summary_stats (Dict[str, Any]): Summary statistics dictionary
        
    Returns:
        None
    """
    try:
        base_path = Path(base_file_path).with_suffix('')
        summary_csv_path = base_path.parent / f"{base_path.name}_summary_5sec.csv"
        
        summary_rows = []
        for sample_name, sample_data in summary_stats.items():
            sample_info = sample_data['sample_info']
            
            for isotope_key, isotope_stats in sample_data['isotope_stats'].items():
                row = {
                    'sample_name': sample_info['sample_name'],
                    'folder_name': sample_name,
                    'isotope_key': isotope_key,
                    'isotope_label': isotope_stats['isotope_label'],
                    'element': isotope_stats['element'],
                    'isotope_mass': isotope_stats['isotope_mass'],
                    'actual_mass': isotope_stats['actual_mass'],
                    'dwell_time_sec': sample_info['dwell_time'],
                    'five_sec_points': sample_info['five_sec_points'],
                    'mean_counts_5sec': isotope_stats['mean_counts'],
                    'std_counts_5sec': isotope_stats['std_counts'],
                    'min_counts_5sec': isotope_stats['min_counts'],
                    'max_counts_5sec': isotope_stats['max_counts'],
                    'mean_cps_5sec': isotope_stats['mean_cps'],
                    'std_cps_5sec': isotope_stats['std_cps'],
                    'min_cps_5sec': isotope_stats['min_cps'],
                    'max_cps_5sec': isotope_stats['max_cps'],
                    'median_cps_5sec': isotope_stats['median_cps'],
                    'rsd_percent_5sec': isotope_stats['rsd_percent'],
                    'total_counts_5sec': isotope_stats['total_counts_5sec'],
                    'data_points_5sec': isotope_stats['data_points_5sec']
                }
                summary_rows.append(row)
        
        if summary_rows:
            with open(summary_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=summary_rows[0].keys())
                writer.writeheader()
                writer.writerows(summary_rows)
            print(f"Saved summary statistics: {summary_csv_path}")
        
    except Exception as e:
        print(f"Error saving summary statistics: {str(e)}")

def load_session_from_csv(file_path: str) -> Dict[str, Any]:
    """
    Load session data from CSV format.
    
    Args:
        file_path (str): Path to the CSV file to load
        
    Returns:
        Dict[str, Any]: Loaded session data dictionary
    """
    try:
        if not file_path.endswith('.csv'):
            file_path += '.csv'
        
        csv.field_size_limit(1000000) 
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            row = next(reader)
        
        session_data = {
            'selected_isotopes': json.loads(row['selected_isotopes']),
            'concentration_unit': row['concentration_unit'],
            'calibration_results': json.loads(row['calibration_results']),
            'table_data': json.loads(row['table_data']),
            'isotope_method_preferences': json.loads(row.get('isotope_method_preferences', '{}')),
            'header_internal_data': json.loads(row.get('header_internal_data', '{}')),
            'summary_stats_5sec': json.loads(row.get('summary_stats_5sec', '{}'))
        }
        
        return session_data
        
    except Exception as e:
        raise Exception(f"Failed to load session: {str(e)}")

def load_summary_stats_from_csv(base_file_path: str) -> Dict[str, Any]:
    """
    Load summary statistics from CSV file.
    
    Args:
        base_file_path (str): Base file path for the summary CSV
        
    Returns:
        Dict[str, Any]: Dictionary of summary statistics organized by sample
    """
    try:
        base_path = Path(base_file_path).with_suffix('')
        summary_csv_path = base_path.parent / f"{base_path.name}_summary_5sec.csv"
        
        if not summary_csv_path.exists():
            return {}
        
        summary_data = {}
        
        with open(summary_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            summary_rows = list(reader)
            
        for row in summary_rows:
            folder_name = row['folder_name']
            if folder_name not in summary_data:
                summary_data[folder_name] = {'summary': []}
            summary_data[folder_name]['summary'].append(row)
        
        return summary_data
        
    except Exception as e:
        print(f"Error loading summary statistics: {str(e)}")
        return {}