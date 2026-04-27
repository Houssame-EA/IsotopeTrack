import io
import json
import pickle
import gzip
import zipfile
import tempfile
import time
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Format version constants
# ---------------------------------------------------------------------------
FORMAT_V2_MAGIC = b"ITPROJ_V2\n"
FORMAT_V1_GZIP_MAGIC = b"\x1f\x8b"

# ---------------------------------------------------------------------------
#  Helpers: particle list <-> columnar numpy
# ---------------------------------------------------------------------------

_ELEMENT_DICT_KEYS = [
    'elements', 'element_mass_fg', 'element_moles_fmol',
    'particle_mass_fg', 'particle_moles_fmol',
    'element_diameter_nm', 'particle_diameter_nm',
    'mass_fractions_used', 'densities_used', 'molar_masses',
    'mass_fg', 'mass_percentages', 'mole_percentages',
]

_SCALAR_KEYS = [
    'start_time', 'end_time', 'left_idx', 'right_idx',
    'max_height', 'total_counts', 'SNR', 'threshold',
    'background', 'element_count',
]


def _particles_to_columnar(particles):
    """
    Convert a list of particle dicts to a columnar dict of numpy arrays.
    
    This is 10-100x smaller and faster to serialize than a list of dicts
    because repeated key strings are eliminated and numpy arrays compress
    much better than pickled Python objects.
    
    Args:
        particles (list): List of particle dictionaries from sample_particle_data
        
    Returns:
        dict: Columnar representation with:
            - 'n': int, number of particles
            - 'element_labels': list of str, ordered element display labels
            - 'scalars': dict of key -> numpy array (float64) for scalar fields
            - 'element_arrays': dict of dict_key -> 2D numpy array (n_particles x n_elements)
            - 'totals': dict of key -> numpy array
            - 'extra_keys': pickled dict for any non-standard keys
    """
    if not particles:
        return {'n': 0, 'element_labels': [], 'scalars': {}, 'element_arrays': {}}

    n = len(particles)

    all_element_labels = set()
    for p in particles:
        if 'elements' in p:
            all_element_labels.update(p['elements'].keys())
    element_labels = sorted(all_element_labels)
    label_to_idx = {lbl: i for i, lbl in enumerate(element_labels)}
    n_elements = len(element_labels)

    scalars = {}
    for key in _SCALAR_KEYS:
        arr = np.zeros(n, dtype=np.float64)
        for i, p in enumerate(particles):
            arr[i] = p.get(key, 0.0)
        if np.any(arr != 0):
            scalars[key] = arr

    element_arrays = {}
    for dict_key in _ELEMENT_DICT_KEYS:
        mat = np.zeros((n, n_elements), dtype=np.float64)
        has_data = False
        for i, p in enumerate(particles):
            d = p.get(dict_key, {})
            if isinstance(d, dict):
                for lbl, val in d.items():
                    if lbl in label_to_idx:
                        try:
                            mat[i, label_to_idx[lbl]] = float(val)
                            has_data = True
                        except (TypeError, ValueError):
                            pass
        if has_data:
            element_arrays[dict_key] = mat

    totals = {}
    totals_keys = set()
    for p in particles:
        t = p.get('totals', {})
        if isinstance(t, dict):
            totals_keys.update(t.keys())
    for key in totals_keys:
        arr = np.zeros(n, dtype=np.float64)
        for i, p in enumerate(particles):
            t = p.get('totals', {})
            arr[i] = t.get(key, 0.0)
        totals[key] = arr

    extra_particles = []
    complex_keys = set()
    for p in particles:
        extra = {}
        for k, v in p.items():
            if k in _SCALAR_KEYS or k in _ELEMENT_DICT_KEYS or k == 'totals':
                continue
            if k.startswith('_'):
                continue
            extra[k] = v
            complex_keys.add(k)
        if 'densities_used' in p and isinstance(p['densities_used'], dict):
            extra['densities_used'] = p['densities_used']
        extra_particles.append(extra)

    has_extras = any(bool(e) for e in extra_particles)

    result = {
        'n': n,
        'element_labels': element_labels,
        'scalars': scalars,
        'element_arrays': element_arrays,
        'totals': totals,
    }
    if has_extras:
        result['extras'] = extra_particles

    return result


def _columnar_to_particles(col_data):
    """
    Reconstruct list of particle dicts from columnar representation.
    
    Args:
        col_data (dict): Columnar data from _particles_to_columnar
        
    Returns:
        list: List of particle dictionaries matching the original format
    """
    n = col_data.get('n', 0)
    if n == 0:
        return []

    element_labels = col_data.get('element_labels', [])
    scalars = col_data.get('scalars', {})
    element_arrays = col_data.get('element_arrays', {})
    totals_arrays = col_data.get('totals', {})
    extras = col_data.get('extras', [{}] * n)

    particles = []
    for i in range(n):
        p = {}

        for key, arr in scalars.items():
            val = float(arr[i])
            if key in ('left_idx', 'right_idx', 'element_count'):
                p[key] = int(val)
            else:
                p[key] = val

        for dict_key, mat in element_arrays.items():
            d = {}
            for j, lbl in enumerate(element_labels):
                val = float(mat[i, j])
                if val != 0.0:
                    d[lbl] = val
            if d:
                p[dict_key] = d
            else:
                p[dict_key] = {}

        if 'elements' not in p:
            p['elements'] = {}

        if totals_arrays:
            t = {}
            for key, arr in totals_arrays.items():
                t[key] = float(arr[i])
            p['totals'] = t

        if i < len(extras) and extras[i]:
            p.update(extras[i])

        particles.append(p)

    return particles


# ---------------------------------------------------------------------------
#  V2 SAVE
# ---------------------------------------------------------------------------

def save_project_v2(filepath, mw, progress_callback=None):
    """
    Save project in optimized v2 format.
    
    Uses ZIP archive with separate numpy files per sample, lz4-compressed
    pickle for metadata, and columnar particle storage.
    
    Args:
        filepath (str or Path): Output file path (.itproj)
        mw: MainWindow instance with all data attributes
        progress_callback (callable, optional): func(percent, message) for progress updates
        
    Returns:
        bool: True on success
    """
    filepath = Path(filepath)
    t0 = time.time()

    def _progress(pct, msg=""):
        """
        Args:
            pct (Any): Progress percentage (0–100).
            msg (Any): Message string.
        """
        if progress_callback:
            progress_callback(pct, msg)

    _progress(0, "Preparing metadata...")

    metadata = {
        'format_version': 2,
        'selected_isotopes': mw.selected_isotopes,
        'sample_parameters': mw.sample_parameters,
        'sample_detected_peaks': mw.sample_detected_peaks,
        'sample_dwell_times': mw.sample_dwell_times,
        'sample_results_data': mw.sample_results_data,
        'isotope_method_preferences': mw.isotope_method_preferences,
        'sample_analysis_dates': mw.sample_analysis_dates,
        'element_thresholds': mw.element_thresholds,
        'element_limits': getattr(mw, 'element_limits', {}),
        'calibration_results': mw.calibration_results,
        'average_transport_rate': mw.average_transport_rate,
        'selected_transport_rate_methods': mw.selected_transport_rate_methods,
        'current_sample': mw.current_sample,
        'sample_to_folder_map': {k: str(v) for k, v in mw.sample_to_folder_map.items()},
        'overlap_threshold_percentage': mw.overlap_threshold_percentage,
        '_global_sigma': mw._global_sigma,
        '_sigma_mode': getattr(mw, '_sigma_mode', 'global'),
        '_exclusion_regions_by_sample': getattr(mw, '_exclusion_regions_by_sample', {}),
        'sample_run_info': getattr(mw, 'sample_run_info', {}),
        'sample_method_info': getattr(mw, 'sample_method_info', {}),
        'element_mass_fractions': getattr(mw, 'element_mass_fractions', {}),
        'element_densities': getattr(mw, 'element_densities', {}),
        'element_molecular_weights': getattr(mw, 'element_molecular_weights', {}),
        'sample_mass_fractions': getattr(mw, 'sample_mass_fractions', {}),
        'sample_densities': getattr(mw, 'sample_densities', {}),
        'sample_molecular_weights': getattr(mw, 'sample_molecular_weights', {}),
        'sample_status': getattr(mw, 'sample_status', {}),
        'detection_states': getattr(mw, 'detection_states', {}),
        'transport_rate_methods': getattr(mw, 'transport_rate_methods', ["Liquid weight", "Number based", "Mass based"]),
        'all_masses': getattr(mw, 'all_masses', None),
        'folder_paths': getattr(mw, 'folder_paths', []),
        '_display_label_to_element': getattr(mw, '_display_label_to_element', {}),
        'element_parameter_hashes': getattr(mw, 'element_parameter_hashes', {}),
        'multi_element_particles': getattr(mw, 'multi_element_particles', []),
        'needs_initial_detection': list(getattr(mw, 'needs_initial_detection', set())),
        'sidebar_width': getattr(mw, 'sidebar_width', 200),
        'sidebar_visible': getattr(mw, 'sidebar_visible', True),
        'csv_config': getattr(mw, 'csv_config', None),
        'pending_csv_processing': getattr(mw, 'pending_csv_processing', False),
    }

    if hasattr(mw, 'canvas_results_dialog') and mw.canvas_results_dialog is not None:
        try:
            canvas = mw.canvas_results_dialog
            if hasattr(canvas, 'canvas') and hasattr(canvas.canvas, 'scene'):
                scene = canvas.canvas.scene
                if hasattr(scene, 'serialize_workflow'):
                    metadata['canvas_workflow'] = scene.serialize_workflow()
                else:
                    from save_export.project_manager import ProjectManager
                    pm = ProjectManager(mw)
                    metadata['canvas_workflow'] = pm._serialize_canvas_state()
        except Exception as e:
            logger.warning(f"Could not serialize canvas workflow: {e}")

    _progress(10, "Compressing metadata...")

    try:
        import lz4.frame as lz4f
        meta_pkl = pickle.dumps(metadata, protocol=pickle.HIGHEST_PROTOCOL)
        meta_compressed = lz4f.compress(meta_pkl)
        compression_lib = 'lz4'
    except ImportError:
        logger.warning("lz4 not installed, falling back to gzip for metadata")
        meta_pkl = pickle.dumps(metadata, protocol=pickle.HIGHEST_PROTOCOL)
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=1) as gz:
            gz.write(meta_pkl)
        meta_compressed = buf.getvalue()
        compression_lib = 'gzip'

    sample_names = list(mw.data_by_sample.keys())
    total_samples = len(sample_names)

    tmp_path = filepath.with_suffix('.itproj.tmp')

    try:
        with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_STORED) as zf:
            zf.writestr('__format__', 'ITPROJ_V2')
            
            manifest = {
                'format_version': 2,
                'compression': compression_lib,
                'sample_names': sample_names,
                'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))

            zf.writestr('metadata.dat', meta_compressed)

            for idx, sample_name in enumerate(sample_names):
                pct = 15 + int(35 * idx / max(total_samples, 1))
                _progress(pct, f"Saving arrays: {sample_name}")

                sample_data = mw.data_by_sample.get(sample_name, {})
                time_arr = mw.time_array_by_sample.get(sample_name)

                if sample_data or time_arr is not None:
                    arrays_dict = {}
                    
                    if time_arr is not None:
                        arrays_dict['__time__'] = np.asarray(time_arr)
                    
                    mass_keys = []
                    for mass_key, arr in sample_data.items():
                        safe_key = f"mass_{mass_key:.6f}"
                        arrays_dict[safe_key] = np.asarray(arr)
                        mass_keys.append((safe_key, float(mass_key)))
                    
                    arrays_dict['__mass_keys__'] = np.array(
                        [mk for _, mk in mass_keys], dtype=np.float64
                    )
                    arrays_dict['__mass_safe_keys__'] = np.array(
                        [sk for sk, _ in mass_keys], dtype='U50'
                    )

                    buf = io.BytesIO()
                    np.savez_compressed(buf, **arrays_dict)
                    safe_name = sample_name.replace('/', '_').replace('\\', '_')
                    zf.writestr(f'arrays/{safe_name}.npz', buf.getvalue())

            for idx, sample_name in enumerate(sample_names):
                pct = 50 + int(40 * idx / max(total_samples, 1))
                _progress(pct, f"Saving particles: {sample_name}")

                particles = mw.sample_particle_data.get(sample_name, [])
                if particles:
                    col_data = _particles_to_columnar(particles)
                    
                    buf = io.BytesIO()
                    pickle.dump(col_data, buf, protocol=pickle.HIGHEST_PROTOCOL)
                    
                    safe_name = sample_name.replace('/', '_').replace('\\', '_')
                    zf.writestr(f'particles/{safe_name}.pkl', buf.getvalue())

        _progress(95, "Finalizing...")

        if filepath.exists():
            filepath.unlink()
        tmp_path.rename(filepath)

        elapsed = time.time() - t0
        _progress(100, f"Saved in {elapsed:.1f}s")
        logger.info(f"Project saved (v2) in {elapsed:.1f}s: {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error saving project v2: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        raise


# ---------------------------------------------------------------------------
#  V2 LOAD
# ---------------------------------------------------------------------------

def load_project_v2(filepath, mw, progress_callback=None):
    """
    Load project from v2 format.
    
    Args:
        filepath (str or Path): Input file path (.itproj)
        mw: MainWindow instance to populate
        progress_callback (callable, optional): func(percent, message) for progress updates
        
    Returns:
        bool: True on success
    """
    filepath = Path(filepath)
    t0 = time.time()

    def _progress(pct, msg=""):
        """
        Args:
            pct (Any): Progress percentage (0–100).
            msg (Any): Message string.
        """
        if progress_callback:
            progress_callback(pct, msg)

    _progress(0, "Opening project file...")

    with zipfile.ZipFile(filepath, 'r') as zf:
        manifest = json.loads(zf.read('manifest.json'))
        compression_lib = manifest.get('compression', 'lz4')
        sample_names = manifest.get('sample_names', [])

        _progress(5, "Loading metadata...")

        meta_compressed = zf.read('metadata.dat')
        
        if compression_lib == 'lz4':
            import lz4.frame as lz4f
            meta_pkl = lz4f.decompress(meta_compressed)
        else:
            buf = io.BytesIO(meta_compressed)
            with gzip.GzipFile(fileobj=buf, mode='rb') as gz:
                meta_pkl = gz.read()
        
        metadata = pickle.loads(meta_pkl)

        _progress(10, "Restoring settings...")

        _restore_metadata(mw, metadata)

        total_samples = len(sample_names)
        for idx, sample_name in enumerate(sample_names):
            pct = 15 + int(40 * idx / max(total_samples, 1))
            _progress(pct, f"Loading arrays: {sample_name}")

            safe_name = sample_name.replace('/', '_').replace('\\', '_')
            arrays_path = f'arrays/{safe_name}.npz'
            
            if arrays_path in zf.namelist():
                buf = io.BytesIO(zf.read(arrays_path))
                npz = np.load(buf, allow_pickle=False)
                
                if '__time__' in npz:
                    mw.time_array_by_sample[sample_name] = npz['__time__']
                
                sample_data = {}
                if '__mass_keys__' in npz and '__mass_safe_keys__' in npz:
                    mass_keys = npz['__mass_keys__']
                    safe_keys = npz['__mass_safe_keys__']
                    for mk, sk in zip(mass_keys, safe_keys):
                        sample_data[float(mk)] = npz[str(sk)]
                
                mw.data_by_sample[sample_name] = sample_data

        for idx, sample_name in enumerate(sample_names):
            pct = 55 + int(40 * idx / max(total_samples, 1))
            _progress(pct, f"Loading particles: {sample_name}")

            safe_name = sample_name.replace('/', '_').replace('\\', '_')
            particles_path = f'particles/{safe_name}.pkl'
            
            if particles_path in zf.namelist():
                buf = io.BytesIO(zf.read(particles_path))
                col_data = pickle.loads(buf.getvalue())
                mw.sample_particle_data[sample_name] = _columnar_to_particles(col_data)
            else:
                mw.sample_particle_data[sample_name] = []

    elapsed = time.time() - t0
    _progress(100, f"Loaded in {elapsed:.1f}s")
    logger.info(f"Project loaded (v2) in {elapsed:.1f}s: {filepath}")
    return True


def _restore_metadata(mw, metadata):
    """
    Restore metadata dict to MainWindow attributes.
    
    Args:
        mw: MainWindow instance
        metadata (dict): Metadata dictionary from save
    """
    simple_attrs = [
        'selected_isotopes', 'sample_parameters', 'sample_detected_peaks',
        'sample_dwell_times', 'sample_results_data', 'isotope_method_preferences',
        'sample_analysis_dates', 'element_thresholds', 'element_limits',
        'calibration_results', 'average_transport_rate',
        'selected_transport_rate_methods', 'current_sample',
        'overlap_threshold_percentage', '_global_sigma', '_sigma_mode',
        '_exclusion_regions_by_sample',
        'sample_run_info', 'sample_method_info',
        'element_mass_fractions', 'element_densities', 'element_molecular_weights',
        'sample_mass_fractions', 'sample_densities', 'sample_molecular_weights',
        'sample_status', 'detection_states',
        'transport_rate_methods',
        'all_masses',
        'folder_paths',
        '_display_label_to_element',
        'element_parameter_hashes',
        'multi_element_particles',
        'sidebar_width', 'sidebar_visible',
        'csv_config', 'pending_csv_processing',
    ]
    
    for attr in simple_attrs:
        if attr in metadata:
            setattr(mw, attr, metadata[attr])

    if not hasattr(mw, '_sigma_mode') or mw._sigma_mode is None:
        mw._sigma_mode = 'global'
    if not hasattr(mw, '_global_sigma') or mw._global_sigma is None:
        mw._global_sigma = 0.55
    if not hasattr(mw, '_exclusion_regions_by_sample'):
        mw._exclusion_regions_by_sample = {}
    if not hasattr(mw, 'sample_status'):
        mw.sample_status = {}

    nid = metadata.get('needs_initial_detection', [])
    if isinstance(nid, list):
        mw.needs_initial_detection = set(nid)
    elif isinstance(nid, set):
        mw.needs_initial_detection = nid

    folder_map = metadata.get('sample_to_folder_map', {})
    mw.sample_to_folder_map = {k: Path(v) if v else v for k, v in folder_map.items()}

    mw._formatted_label_cache = {}
    mw._element_data_cache = {}

    if 'canvas_workflow' in metadata and metadata['canvas_workflow']:
        mw._pending_canvas_workflow = metadata['canvas_workflow']


# ---------------------------------------------------------------------------
#  V1 LOAD (backward compatibility - the old gzip+pickle format)
# ---------------------------------------------------------------------------

def load_project_v1(filepath, mw, progress_callback=None):
    """
    Load project from old v1 gzip+pickle format.
    
    This is the original format - just loads the old way.
    
    Args:
        filepath (str or Path): Input file path (.itproj)
        mw: MainWindow instance to populate
        progress_callback (callable, optional): func(percent, message)
        
    Returns:
        dict: The loaded project_data dictionary (for the existing
              ProjectManager._restore_project_data to process)
    """
    if progress_callback:
        progress_callback(10, "Loading legacy format (gzip)...")

    with gzip.open(str(filepath), 'rb') as f:
        project_data = pickle.load(f)

    if progress_callback:
        progress_callback(100, "Legacy project loaded")

    return project_data


# ---------------------------------------------------------------------------
#  AUTO-DETECT loader
# ---------------------------------------------------------------------------

def detect_format(filepath):
    """
    Detect project file format version.
    
    Args:
        filepath (str or Path): File path to check
        
    Returns:
        int: Format version (1 for old gzip+pickle, 2 for new ZIP)
    """
    filepath = Path(filepath)
    
    with open(filepath, 'rb') as f:
        magic = f.read(4)
    
    if magic[:4] == b'PK\x03\x04':
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if '__format__' in zf.namelist():
                    return 2
        except zipfile.BadZipFile:
            pass
    
    if magic[:2] == FORMAT_V1_GZIP_MAGIC:
        return 1
    
    try:
        with gzip.open(str(filepath), 'rb') as f:
            f.read(1)
        return 1
    except Exception:
        pass
    
    raise ValueError(f"Unrecognized project file format: {filepath}")


def load_project_auto(filepath, mw, progress_callback=None):
    """
    Auto-detect format and load project.
    
    Supports both v1 (legacy gzip+pickle) and v2 (optimized ZIP) formats.
    
    Args:
        filepath (str or Path): Input file path
        mw: MainWindow instance
        progress_callback (callable, optional): func(percent, message)
        
    Returns:
        For v2: True (data already restored to mw)
        For v1: dict (project_data for existing _restore_project_data to handle)
    """
    version = detect_format(filepath)
    
    if version == 2:
        return load_project_v2(filepath, mw, progress_callback)
    else:
        return load_project_v1(filepath, mw, progress_callback)


# ---------------------------------------------------------------------------
#  Integration helpers
# ---------------------------------------------------------------------------

def estimate_project_size(mw):
    """
    Estimate uncompressed project size for progress bar calibration.
    
    Args:
        mw: MainWindow instance
        
    Returns:
        dict: Size estimates with keys 'arrays_mb', 'particles_mb', 'metadata_mb', 'total_mb'
    """
    import sys
    
    arrays_bytes = 0
    for sample_name, sample_data in mw.data_by_sample.items():
        for mass, arr in sample_data.items():
            arrays_bytes += arr.nbytes if hasattr(arr, 'nbytes') else 0
        time_arr = mw.time_array_by_sample.get(sample_name)
        if time_arr is not None:
            arrays_bytes += time_arr.nbytes if hasattr(time_arr, 'nbytes') else 0
    
    particles_count = sum(
        len(p) for p in mw.sample_particle_data.values()
    )
    particles_bytes = particles_count * 500
    
    metadata_bytes = 1_000_000 
    
    return {
        'arrays_mb': arrays_bytes / 1e6,
        'particles_mb': particles_bytes / 1e6,
        'metadata_mb': metadata_bytes / 1e6,
        'total_mb': (arrays_bytes + particles_bytes + metadata_bytes) / 1e6,
        'particle_count': particles_count,
    }