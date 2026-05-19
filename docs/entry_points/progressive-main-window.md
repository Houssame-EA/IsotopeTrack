# `progressive_main_window.py`

Progressive loading system for main window with splash screen support.

---

## Classes

### `ProgressiveMainWindow` *(extends `QObject`)*

Progressive main window loader with step-by-step initialization and progress reporting.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Initialize the progressive main window loader. |
| `start_loading` | `(self)` | Start the progressive loading process. |
| `process_next_step` | `(self)` | Process the next loading step in sequence. |
| `step_import_modules` | `(self)` | Step 1: Import additional modules if needed. |
| `step_init_core` | `(self)` | Step 2: Initialize core MainWindow. |
| `step_setup_window` | `(self)` | Step 3: Setup window properties. |
| `step_create_widgets` | `(self)` | Step 4: Create central widgets. |
| `step_init_plots` | `(self)` | Step 5: Initialize plot widgets. |
| `step_setup_data` | `(self)` | Step 6: Setup data structures. |
| `step_setup_menus` | `(self)` | Step 7: Configure menu systems. |
| `step_connect_signals` | `(self)` | Step 8: Connect signals and slots. |
| `step_finalize` | `(self)` | Step 9: Finalize interface. |
| `step_complete` | `(self)` | Step 10: Loading complete. |
| `get_main_window` | `(self)` | Get the loaded main window. |
| `step_preload_mass_fraction_db` | `(self)` | Preload the Mass Fraction CSV database and cache it on the main window. |
