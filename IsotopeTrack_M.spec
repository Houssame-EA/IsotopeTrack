# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

sklearn_hidden = collect_submodules('sklearn')
scipy_hidden   = collect_submodules('scipy')
numba_hidden   = collect_submodules('numba')

pandas_meta = []
for _pkg in ('pytz', 'pandas', 'numpy', 'python-dateutil', 'six', 'tzdata'):
    try:
        pandas_meta += copy_metadata(_pkg)
    except Exception:
        pass

_rth = os.path.join(os.path.dirname(os.path.abspath(SPEC)), '_rth_no_pyarrow.py')
with open(_rth, 'w') as _f:
    _f.write(
        "import sys, types\n"
        "if 'pyarrow' not in sys.modules:\n"
        "    m = types.ModuleType('pyarrow')\n"
        "    m.__version__ = '0.0.0'\n"
        "    sys.modules['pyarrow'] = m\n"
    )

data_files = []

if os.path.exists('images'):
    for image_file in os.listdir('images'):
        if image_file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
            image_path = os.path.join('images', image_file)
            if os.path.isfile(image_path):
                data_files.append((image_path, 'images'))
                print(f"Including image: {image_file}")

if os.path.exists('data'):
    for data_file in os.listdir('data'):
        if data_file.endswith(('.csv', '.txt', '.csv.gz', '.json', '.xml')):
            data_path = os.path.join('data', data_file)
            if os.path.isfile(data_path):
                data_files.append((data_path, 'data'))
                print(f"Including data file: {data_file}")

if os.path.exists('images/isotrack_icon.ico'):
    data_files.append(('images/isotrack_icon.ico', '.'))

# ── CPLN quantile look-up table (used by processing/peak_detection.py) ───────
if os.path.exists('processing/cpln_quantiles.npz'):
    data_files.append(('processing/cpln_quantiles.npz', 'processing'))
    print("Including cpln_quantiles.npz")
else:
    print("WARNING: processing/cpln_quantiles.npz not found — peak detection LUT will be missing!")

print(f"Total data files to include: {len(data_files)}")

a = Analysis(
    ['Run.py'],
    pathex=[],
    binaries=[],
    datas=data_files + pandas_meta,
    hiddenimports=[
        # ── Qt / PySide6 ─────────────────────────────────────────────────────
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPrintSupport',

        # ── PyQtGraph ─────────────────────────────────────────────────────────
        'pyqtgraph',
        'pyqtgraph.Qt',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.graphicsItems.ViewBox',
        'pyqtgraph.graphicsItems.PlotItem',
        'pyqtgraph.graphicsItems.LegendItem',
        'pyqtgraph.graphicsItems.TextItem',
        'pyqtgraph.graphicsItems.ScatterPlotItem',
        'pyqtgraph.graphicsItems.InfiniteLine',
        'pyqtgraph.graphicsItems.LinearRegionItem',
        'pyqtgraph.exporters',
        'pyqtgraph.exporters.ImageExporter',
        'pyqtgraph.exporters.SVGExporter',

        # ── QtAwesome ─────────────────────────────────────────────────────────
        'qtawesome',
        'qtawesome.iconic_font',
        'qtawesome.animation',
        'qtawesome.icon_browser',

        # ── NumPy ─────────────────────────────────────────────────────────────
        'numpy',
        'numpy.lib',
        'numpy.lib.recfunctions',
        'numpy.random',
        'numpy.core',
        'numpy.linalg',
        'numpy.fft',
        

        'numpy._core',
        'numpy._core.multiarray',
        'numpy._core.numeric',
        'numpy._core.umath',
        'numpy._core.fromnumeric',
        'numpy._core.arrayprint',
        'numpy._core.defchararray',
        'numpy._core.records',
        'numpy._core.memmap',
        'numpy._core.function_base',
        'numpy._core.machar',
        'numpy._core.getlimits',
        'numpy._core.shape_base',
        'numpy._core.einsumfunc',
        'numpy._core._multiarray_umath',
        'numpy._core._multiarray_tests',
        'numpy._core._dtype',
        'numpy._core._dtype_ctypes',
        'numpy._core._exceptions',
        'numpy._core._internal',
        'numpy._core._methods',
        'numpy._core._string_helpers',
        'numpy._core._type_aliases',
        'numpy._core._ufunc_config',

        # ── Compression ───────────────────────────────────────────────────────────────
        'lz4',
        'lz4.frame',
        'lz4.block',

        # ── SciPy ─────────────────────────────────────────────────────────────
        *scipy_hidden,

        # ── Numba / llvmlite ──────────────────────────────────────────────────
        *numba_hidden,
        'llvmlite',
        'llvmlite.binding',

        # ── Poisson ───────────────────────────────────────────────────────────
        'poisson',

        # ── Pandas ────────────────────────────────────────────────────────────
        'pandas',
        'pandas.io.formats.excel',
        'pandas.io.common',
        'pandas.io.parsers.readers',

        # ── Matplotlib ────────────────────────────────────────────────────────
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.colors',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_agg',
        'matplotlib.figure',
        'matplotlib.patches',
        'matplotlib.lines',
        'matplotlib.text',
        'matplotlib.font_manager',

        # ── mpltern (ternary plots) ───────────────────────────────────────────
        'mpltern',
        'mpltern.ternary',
        'mpltern.ternary.axes',

        # ── scikit-learn ──────────────────────────────────────────────────────
        *sklearn_hidden,

        # ── h5py (Cython extensions must be listed explicitly) ────────────────
        'h5py',
        'h5py._conv',
        'h5py._proxy',
        'h5py._npystrings',
        'h5py._errors',
        'h5py._objects',
        'h5py.defs',
        'h5py.h5',
        'h5py.h5a',
        'h5py.h5d',
        'h5py.h5ds',
        'h5py.h5f',
        'h5py.h5fd',
        'h5py.h5g',
        'h5py.h5i',
        'h5py.h5l',
        'h5py.h5o',
        'h5py.h5p',
        'h5py.h5r',
        'h5py.h5s',
        'h5py.h5t',
        'h5py.h5z',
        'h5py.ipy_completer',
        'h5py.version',

        # ── HTTP / network ────────────────────────────────────────────────────
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests.exceptions',
        'requests.models',
        'requests.sessions',
        'requests.structures',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',

        # ── Concurrency ───────────────────────────────────────────────────────
        'concurrent.futures',
        'multiprocessing',
        'threading',

        # ── Standard library ──────────────────────────────────────────────────
        'json',
        'pathlib',
        'collections',
        'io',
        'base64',
        'datetime',
        'time',
        'math',
        'statistics',
        'hashlib',
        'pickle',
        'gzip',
        'warnings',
        'gc',
        're',

        # ── Application root ──────────────────────────────────────────────────
        'mainwindow',
        'theme',

        # ── calibration_methods/ ──────────────────────────────────────────────
        'calibration_methods',
        'calibration_methods.ionic_CAL',
        'calibration_methods.TE_input',
        'calibration_methods.TE_mass',
        'calibration_methods.TE_number',
        'calibration_methods.TE',
        'calibration_methods.te_common',

        # ── loading/ ─────────────────────────────────────────────────────────
        'loading',
        'loading.data_thread',
        'loading.import_csv_dialogs',
        'loading.SIA_manager',
        'loading.tofwerk_loading',
        'loading.vitesse_loading',

        # ── processing/ ───────────────────────────────────────────────────────
        'processing',
        'processing.peak_detection',

        # ── results/ ─────────────────────────────────────────────────────────
        'results',
        'results.results_AI',
        'results.results_bar_charts',
        'results.results_box_plot',
        'results.results_cluster',
        'results.results_concentration',
        'results.results_correlation',
        'results.results_dashboard',
        'results.results_heatmap',
        'results.results_isotope',
        'results.results_matrix',
        'results.results_molar_ratio',
        'results.results_network',
        'results.results_periodic',
        'results.results_pie_charts',
        'results.results_single_multiple',
        'results.results_triangle',
        'results.shared_annotation',
        'results.shared_plot_utils',
        'results.utils_sort',

        # ── save_export/ ──────────────────────────────────────────────────────
        'save_export',
        'save_export.export_utils',
        'save_export.fast_project_io',
        'save_export.ionic_session',
        'save_export.project_manager',

        # ── tools/ ────────────────────────────────────────────────────────────
        'tools',
        'tools.app_version',
        'tools.update_checker',
        'tools.help_dialogs',
        'tools.Info_table',
        'tools.info_file',
        'tools.logging_utils',
        'tools.mass_fraction_calculator',
        'tools.progressive_main_window',
        'tools.signal_selector_dialog',
        'tools.splash_screen',
        'tools.tutorial',
        'tools.unit',

        # ── widget/ ───────────────────────────────────────────────────────────
        'widget',
        'widget.batch_parameters',
        'widget.calibration_info',
        'widget.canvas_widgets',
        'widget.colors',
        'widget.custom_plot_widget',
        'widget.drag_table',
        'widget.interference_database',
        'widget.numeric_table',
        'widget.periodic_table_widget',
        'widget.signal_calculator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[_rth],
    excludes=[
        'tkinter',
        'turtle',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'plotly',
        'pyarrow',
        'openpyxl',
        'xlsxwriter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IsotopeTrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    icon='images/isotrack_icon.ico' if os.path.exists('images/isotrack_icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IsotopeTrack',
)

app = BUNDLE(
    coll,
    name='IsotopeTrack.app',
    icon='images/isotrack_icon.ico' if os.path.exists('images/isotrack_icon.ico') else None,
    bundle_identifier='com.isotrack.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.7',
        'CFBundleVersion': '1.0.7',
        'CFBundleDisplayName': 'IsotopeTrack',
        'CFBundleName': 'IsotopeTrack',
        'NSRequiresAquaSystemAppearance': 'False',
        'NSRemovableVolumesUsageDescription':
            'IsotopeTrack needs access to read data files from external drives.',
    },
)
