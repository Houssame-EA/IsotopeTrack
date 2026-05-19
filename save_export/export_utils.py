from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox,
                              QCheckBox, QRadioButton, QScrollArea, QWidget,
                              QDialogButtonBox, QFileDialog, QMessageBox,
                              QHBoxLayout, QLabel, QDoubleSpinBox, QFrame,
                              QPushButton, QButtonGroup, QSizePolicy)
from PySide6.QtCore import Qt
import time
import numpy as np
import math
import time

from theme import theme, dialog_qss
from tools.unit import ExportUnits, load_units, show_advanced_dialog

def is_pure_element(mass_fraction):
    """
    Check if mass fraction indicates a pure element (effectively 1.0).
    
    Args:
        mass_fraction (float): Mass fraction value
        
    Returns:
        bool: True if pure element, False otherwise
    """
    return math.isclose(mass_fraction, 1.0, abs_tol=1e-6)

def get_molecular_weight_for_export(main_window, element_key, sample_name=None):
    """
    Get molecular weight for export calculations.
    
    Args:
        main_window (object): Main window object
        element_key (str): Element key in format 'Element-Isotope'
        sample_name (str, optional): Sample name
        
    Returns:
        float | None: Molecular weight or None if not found
    """
    if hasattr(main_window, 'get_molecular_weight'):
        return main_window.get_molecular_weight(element_key, sample_name)
    
    element = element_key.split('-')[0]
    if main_window.periodic_table_widget:
        element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
        if element_data:
            return float(element_data.get('mass', 0))
    return None

def export_data(main_window):
    """
    Export all sample data and summary file in one unified process with mass fraction, 
    mole support, dilution factors, and data type selection.
    
    Args:
        main_window (object): Main window object
        
    Returns:
        bool: True if export successful, False otherwise
    """
    if not main_window.data_by_sample:
        QMessageBox.warning(main_window, "Warning", "No data available to export.")
        return False
    
    export_dialog = QDialog(main_window)
    export_dialog.setWindowTitle("Export Options")
    export_dialog.setObjectName("exportOptionsDialog")
    export_dialog.setMinimumSize(500, 560)
    export_dialog.resize(540, 640)

    # -- Theme application + live updates ---------------------------------
    def _build_dialog_qss(palette):
        """Dialog-wide QSS: the generic dialog styling plus the extras we
        need for the segmented Data Type toggle and the count/link row.
        Args:
            palette (Any): Colour palette object.
        Returns:
            object: Result of the operation.
        """
        extras = f"""
            QPushButton#segLeft, QPushButton#segRight {{
                background-color: {palette.bg_tertiary};
                color: {palette.text_secondary};
                border: 1px solid {palette.border};
                padding: 6px 14px;
                min-width: 0;
            }}
            QPushButton#segLeft  {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
            QPushButton#segRight {{ border-top-left-radius: 0;  border-bottom-left-radius: 0;  border-left: none; }}
            QPushButton#segLeft:checked, QPushButton#segRight:checked {{
                background-color: {palette.accent};
                color: {palette.text_inverse};
                border-color: {palette.accent};
            }}
            QPushButton#segLeft:hover:!checked, QPushButton#segRight:hover:!checked {{
                background-color: {palette.bg_hover};
                color: {palette.text_primary};
            }}
            QPushButton#linkButton {{
                background: transparent;
                border: none;
                color: {palette.accent};
                padding: 2px 4px;
                min-width: 0;
                text-align: left;
            }}
            QPushButton#linkButton:hover {{
                color: {palette.accent_hover};
                text-decoration: underline;
            }}
            QLabel#countLabel {{ color: {palette.text_secondary}; }}
            QLabel#dotLabel   {{ color: {palette.text_muted}; }}
            QFrame#divider    {{ background-color: {palette.border_subtle}; border: none; }}
        """
        return dialog_qss(palette) + extras

    def _apply_dialog_theme(*_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        export_dialog.setStyleSheet(_build_dialog_qss(theme.palette))

    _apply_dialog_theme()
    theme.themeChanged.connect(_apply_dialog_theme)
    export_dialog.destroyed.connect(
        lambda *_: theme.themeChanged.disconnect(_apply_dialog_theme)
    )

    layout = QVBoxLayout(export_dialog)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(14)

    # ---- 1. Data Type: segmented toggle ---------------------------------
    data_type_row = QHBoxLayout()
    data_type_row.setSpacing(0)
    data_type_row.setContentsMargins(0, 0, 0, 0)

    data_type_label = QLabel("Data Type")
    data_type_label.setStyleSheet("font-weight: 600;")

    element_type_btn = QPushButton("Element")
    element_type_btn.setObjectName("segLeft")
    element_type_btn.setCheckable(True)
    element_type_btn.setChecked(True)

    particle_type_btn = QPushButton("Particle")
    particle_type_btn.setObjectName("segRight")
    particle_type_btn.setCheckable(True)

    for b in (element_type_btn, particle_type_btn):
        b.setCursor(Qt.PointingHandCursor)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    data_type_group = QButtonGroup(export_dialog)
    data_type_group.setExclusive(True)
    data_type_group.addButton(element_type_btn)
    data_type_group.addButton(particle_type_btn)

    data_type_row.addWidget(data_type_label)
    data_type_row.addSpacing(16)
    data_type_row.addWidget(element_type_btn)
    data_type_row.addWidget(particle_type_btn)
    data_type_row.addStretch()
    layout.addLayout(data_type_row)

    # ---- 2. Samples section ---------------------------------------------
    samples_group = QGroupBox("Samples")
    samples_layout = QVBoxLayout()
    samples_layout.setContentsMargins(12, 10, 12, 12)
    samples_layout.setSpacing(8)

    header_row = QHBoxLayout()
    header_row.setSpacing(8)
    count_label = QLabel()
    count_label.setObjectName("countLabel")
    select_all_btn = QPushButton("Select all")
    select_all_btn.setObjectName("linkButton")
    select_all_btn.setCursor(Qt.PointingHandCursor)
    select_all_btn.setFlat(True)
    sep_label = QLabel("·")
    sep_label.setObjectName("dotLabel")
    clear_btn = QPushButton("Clear")
    clear_btn.setObjectName("linkButton")
    clear_btn.setCursor(Qt.PointingHandCursor)
    clear_btn.setFlat(True)

    header_row.addWidget(count_label)
    header_row.addStretch()
    header_row.addWidget(select_all_btn)
    header_row.addWidget(sep_label)
    header_row.addWidget(clear_btn)
    samples_layout.addLayout(header_row)

    divider = QFrame()
    divider.setObjectName("divider")
    divider.setFrameShape(QFrame.NoFrame)
    divider.setFixedHeight(1)
    samples_layout.addWidget(divider)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setObjectName("sampleScrollArea")
    scroll_content = QWidget()
    scroll_content.setObjectName("sampleScrollContent")
    scroll_layout = QVBoxLayout(scroll_content)
    scroll_layout.setContentsMargins(2, 2, 2, 2)
    scroll_layout.setSpacing(2)

    sample_checkboxes = {}
    dilution_spinboxes = {}

    for sample_name in main_window.sample_to_folder_map.keys():
        row_widget = QWidget()
        row_widget.setObjectName("sampleRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(8)

        cb = QCheckBox(sample_name)
        cb.setChecked(True)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(cb, 1)
        sample_checkboxes[sample_name] = cb

        dilution_spinbox = QDoubleSpinBox()
        dilution_spinbox.setRange(1.0, 1000000.0)
        dilution_spinbox.setValue(1.0)
        dilution_spinbox.setDecimals(3)
        dilution_spinbox.setSuffix("x")
        dilution_spinbox.setFixedWidth(100)
        dilution_spinbox.setToolTip("Dilution factor for this sample")
        row.addWidget(dilution_spinbox)
        dilution_spinboxes[sample_name] = dilution_spinbox

        scroll_layout.addWidget(row_widget)

    scroll_layout.addStretch()
    scroll.setWidget(scroll_content)
    samples_layout.addWidget(scroll, 1)
    samples_group.setLayout(samples_layout)
    layout.addWidget(samples_group, 1)

    # ---- 3. Export contents: two checkboxes -----------------------------
    export_group = QGroupBox("Export")
    export_layout = QHBoxLayout()
    export_layout.setContentsMargins(12, 8, 12, 10)
    export_layout.setSpacing(20)

    export_samples_cb = QCheckBox("Sample files")
    export_samples_cb.setChecked(True)
    export_summary_cb = QCheckBox("Summary file")
    export_summary_cb.setChecked(True)

    export_layout.addWidget(export_samples_cb)
    export_layout.addWidget(export_summary_cb)
    export_layout.addStretch()
    export_group.setLayout(export_layout)
    layout.addWidget(export_group)

    # ---- Buttons --------------------------------------------------------
    export_units_state = {"units": load_units()}

    button_row = QHBoxLayout()
    button_row.setContentsMargins(0, 0, 0, 0)
    button_row.setSpacing(8)

    advanced_btn = QPushButton("Advanced…")
    advanced_btn.setToolTip("Change units (mass, moles, diameter) and number format")

    def _open_advanced():
        new_units = show_advanced_dialog(export_dialog, export_units_state["units"])
        if new_units is not None:
            export_units_state["units"] = new_units
    advanced_btn.clicked.connect(_open_advanced)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    ok_btn = buttons.button(QDialogButtonBox.Ok)
    ok_btn.setText("Export")
    ok_btn.setDefault(True)
    buttons.accepted.connect(export_dialog.accept)
    buttons.rejected.connect(export_dialog.reject)

    button_row.addWidget(advanced_btn)
    button_row.addStretch()
    button_row.addWidget(buttons)
    layout.addLayout(button_row)

    # ---- Behaviour ------------------------------------------------------
    total_samples = len(sample_checkboxes)

    def update_count_label():
        n_checked = sum(1 for cb in sample_checkboxes.values() if cb.isChecked())
        count_label.setText(f"{n_checked} of {total_samples} selected")
        ok_btn.setEnabled(
            n_checked > 0
            and (export_samples_cb.isChecked() or export_summary_cb.isChecked())
        )

    def select_all():
        for cb in sample_checkboxes.values():
            cb.setChecked(True)

    def clear_all():
        for cb in sample_checkboxes.values():
            cb.setChecked(False)

    select_all_btn.clicked.connect(select_all)
    clear_btn.clicked.connect(clear_all)
    for cb in sample_checkboxes.values():
        cb.stateChanged.connect(lambda *_: update_count_label())
    export_samples_cb.stateChanged.connect(lambda *_: update_count_label())
    export_summary_cb.stateChanged.connect(lambda *_: update_count_label())
    update_count_label()

    if export_dialog.exec() != QDialog.Accepted:
        return False

    # -- function expects (keeps downstream code unchanged) --------------
    selected_samples = [s for s, cb in sample_checkboxes.items() if cb.isChecked()]
    sample_dilutions = {s: dilution_spinboxes[s].value() for s in selected_samples}

    data_type = "particle" if particle_type_btn.isChecked() else "element"
    export_units = export_units_state["units"]

    if not selected_samples:
        QMessageBox.warning(main_window, "Warning", "No samples selected for export.")
        return False

    want_samples = export_samples_cb.isChecked()
    want_summary = export_summary_cb.isChecked()
    if want_samples and want_summary:
        export_type = "all"
    elif want_samples:
        export_type = "samples"
    elif want_summary:
        export_type = "summary"
    else:
        QMessageBox.warning(main_window, "Warning", "Select at least one of Sample files or Summary file.")
        return False
        
    original_sample = main_window.current_sample
    try:
        for sample_name in selected_samples:
            main_window.current_sample = sample_name
            main_window.calculate_mass_limits()
    finally:
        main_window.current_sample = original_sample
        
    export_dir = QFileDialog.getExistingDirectory(main_window, "Select Export Directory")
   
    if not export_dir:
        return False

    try:
        successful_exports = 0
        failed_exports = []
        
        current_date = time.strftime('%Y-%m-%d')
        current_time = time.strftime('%H:%M:%S')
        
        all_elements = []
        for element, isotopes in main_window.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                display_label = main_window.get_formatted_label(element_key)
                atomic_mass = isotope
                all_elements.append((element_key, display_label, element, isotope, atomic_mass))
        
        all_elements.sort(key=lambda x: x[3])
        element_labels = [display_label for _, display_label, _, _, _ in all_elements]
        
        if export_type in ["all", "summary"]:
            summary_file_path = f"{export_dir}/{time.strftime('%H-%M-%S')}summary_results.csv"
            try:
                with open(summary_file_path, 'w') as summary_file:
                    export_summary_file_with_mass_fractions(
                        main_window, summary_file, selected_samples, all_elements, element_labels, sample_dilutions, data_type,
                        units=export_units,
                    )
                
                successful_exports += 1
                
            except Exception as e:
                failed_exports.append(("Summary file", str(e)))
                print(f"Error creating summary file: {str(e)}")

        if export_type in ["all", "samples"]:
            for sample_name in selected_samples:
                try:
                    safe_sample_name = "".join(x for x in sample_name if x.isalnum() or x in (' ', '-', '_'))
                    file_path = f"{export_dir}/{safe_sample_name}_results.csv"
                    
                    ionic_data = main_window.calibration_results.get("Ionic Calibration", {})
                    threshold_data = main_window.element_thresholds.get(sample_name, {})
                    dilution_factor = sample_dilutions[sample_name]
                    
                    export_sample_file_with_mass_fractions(
                        main_window, sample_name, file_path, all_elements, ionic_data, threshold_data, dilution_factor, data_type,
                        units=export_units,
                    )
                    
                    successful_exports += 1
                    
                except Exception as e:
                    failed_exports.append((sample_name, str(e)))
                    print(f"Error exporting {sample_name}: {str(e)}")
                    continue

        if successful_exports > 0:
            success_msg = f"Successfully exported {successful_exports} file(s) to {export_dir}"
            if failed_exports:
                error_details = "\n".join([f"{name}: {error}" for name, error in failed_exports])
                success_msg += f"\n\nFailed exports ({len(failed_exports)}):\n{error_details}"
            QMessageBox.information(main_window, "Export Complete", success_msg)
        else:
            error_details = "\n".join([f"{name}: {error}" for name, error in failed_exports])
            QMessageBox.critical(main_window, "Export Error", f"Failed to export any files:\n\n{error_details}")

        main_window.status_label.setText(f"Exported {successful_exports} file(s) to {export_dir}")
        return True

    except Exception as e:
        QMessageBox.critical(main_window, "Export Error", f"Error during export: {str(e)}")
        print(f"Export error: {str(e)}")
        return False

def export_mass_fraction_info(main_window, file_handle, selected_samples, data_type):
    """
    Export mass fraction configuration information with data type and molecular weights.
    
    Args:
        main_window (object): Main window object
        file_handle (file): Open file handle for writing
        selected_samples (list): List of selected sample names
        data_type (str): Data type ('element' or 'particle')
        
    Returns:
        None
    """
    file_handle.write("Mass Fraction Configuration:\n")
    file_handle.write(f"Data Type: {data_type.capitalize()} Type\n")
    file_handle.write("Type,Element,Mass Fraction,Molecular Weight (g/mol),Compound Density (g/cm³),Element Density (g/cm³),Notes\n")
    
    if hasattr(main_window, 'element_mass_fractions') and main_window.element_mass_fractions:
        for element, mass_fraction in main_window.element_mass_fractions.items():
            compound_density = main_window.element_densities.get(element, '') if hasattr(main_window, 'element_densities') else ''
            molecular_weight = main_window.element_molecular_weights.get(element, '') if hasattr(main_window, 'element_molecular_weights') else ''
            
            element_density = ''
            if main_window.periodic_table_widget:
                element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                if element_data:
                    element_density = f"{element_data.get('density', 0):.3f}"
            
            notes = "Applied to all samples" if not is_pure_element(mass_fraction) else "Pure element"
            mw_display = f"{molecular_weight:.6f}" if molecular_weight else element_density
            file_handle.write(f"Global,{element},{mass_fraction:.6f},{mw_display},{compound_density},{element_density},{notes}\n")
    
    if hasattr(main_window, 'sample_mass_fractions'):
        for sample_name in selected_samples:
            if sample_name in main_window.sample_mass_fractions:
                sample_fractions = main_window.sample_mass_fractions[sample_name]
                sample_densities = main_window.sample_densities.get(sample_name, {}) if hasattr(main_window, 'sample_densities') else {}
                sample_molecular_weights = main_window.sample_molecular_weights.get(sample_name, {}) if hasattr(main_window, 'sample_molecular_weights') else {}
                
                for element, mass_fraction in sample_fractions.items():
                    compound_density = sample_densities.get(element, '')
                    molecular_weight = sample_molecular_weights.get(element, '')
                    
                    element_density = ''
                    if main_window.periodic_table_widget:
                        element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                        if element_data:
                            element_density = f"{element_data.get('density', 0):.3f}"
                    
                    notes = f"Sample-specific override" if not is_pure_element(mass_fraction) else "Pure element"
                    mw_display = f"{molecular_weight:.6f}" if molecular_weight else element_density
                    file_handle.write(f"{sample_name},{element},{mass_fraction:.6f},{mw_display},{compound_density},{element_density},{notes}\n")
    
    if (not hasattr(main_window, 'element_mass_fractions') or not main_window.element_mass_fractions) and \
       (not hasattr(main_window, 'sample_mass_fractions') or not main_window.sample_mass_fractions):
        file_handle.write("Default,All Elements,1.000000,From Periodic Table,From Periodic Table,From Periodic Table,Pure elements assumed\n")
    
    file_handle.write("\n")

def export_summary_file_with_mass_fractions(main_window, summary_file, selected_samples, all_elements, element_labels, sample_dilutions, data_type, units=None):
    """
    Export summary file with mixed element/particle calculations based on mass fractions and molecular weights.
    
    Args:
        main_window (object): Main window object
        summary_file (file): Open file handle for writing
        selected_samples (list): List of selected sample names
        all_elements (list): List of tuples containing element data
        element_labels (list): List of formatted element labels
        sample_dilutions (dict): Dictionary of sample dilution factors
        data_type (str): Data type ('element' or 'particle')
        units (ExportUnits | None): Unit preferences. If None, uses defaults (fg/fmol/nm).

    Returns:
        None
    """
    if units is None:
        units = ExportUnits()
    summary_file.write("IsotopeTrack Summary Results\n")
    summary_file.write(f"Date: {time.strftime('%Y-%m-%d')}\n")
    summary_file.write(f"Time: {time.strftime('%H:%M:%S')}\n")
    summary_file.write(f"Data Type: {data_type.capitalize()} Type\n\n")
    
    summary_file.write("SAMPLE STATISTICS SUMMARY\n")
    summary_file.write("-----------------------\n\n")
    
    export_mass_fraction_info(main_window, summary_file, selected_samples, data_type)
    
    summary_file.write("Dilution Factors Applied:\n")
    summary_file.write("Sample,Dilution Factor\n")
    for sample_name in selected_samples:
        dilution = sample_dilutions.get(sample_name, 1.0)
        summary_file.write(f"{sample_name},{dilution:.3f}x\n")
    summary_file.write("\n")
    
    summary_file.write("Total Particles\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    
    total_particles_data = []
    particles_per_ml_data = []
    corrected_particles_per_ml_data = []
    mass_fraction_data = []
    molecular_weight_data = []
    detection_params_data = []
    background_counts_data = []
    background_ppt_data = []
    mean_mass_data = []
    median_mass_data = []
    std_mass_data = []
    total_mass_data = []
    mean_moles_data = []
    median_moles_data = []
    std_moles_data = []
    total_moles_data = []
    mean_diameter_data = []

    for sample_name in selected_samples:
        try:
            total_particles_row = [sample_name]
            particles_per_ml_row = [sample_name]
            corrected_particles_per_ml_row = [sample_name]
            mass_fraction_row = [sample_name]
            molecular_weight_row = [sample_name]
            background_counts_row = [sample_name]
            background_ppt_row = [sample_name]
            mean_mass_row = [sample_name]
            median_mass_row = [sample_name]
            std_mass_row = [sample_name]
            total_mass_row = [sample_name]
            mean_moles_row = [sample_name]
            median_moles_row = [sample_name]
            std_moles_row = [sample_name]
            total_moles_row = [sample_name]
            mean_diameter_row = [sample_name]
            
            ionic_data = main_window.calibration_results.get("Ionic Calibration", {})
            threshold_data = main_window.element_thresholds.get(sample_name, {})
            dilution_factor = sample_dilutions.get(sample_name, 1.0)
            
            total_volume_ml = 0
            if main_window.average_transport_rate > 0 and sample_name in main_window.time_array_by_sample:
                time_array = main_window.time_array_by_sample[sample_name]
                total_time = time_array[-1] - time_array[0]
                total_volume_ml = (main_window.average_transport_rate * total_time) / 1000

            for element_key, display_label, element, isotope, atomic_mass in all_elements:
                particle_count = 0
                if sample_name in main_window.sample_detected_peaks:
                    if (element, isotope) in main_window.sample_detected_peaks[sample_name]:
                        particle_count = len(main_window.sample_detected_peaks[sample_name][(element, isotope)])

                particles_per_ml = (particle_count / total_volume_ml) if total_volume_ml > 0 else 0
                corrected_particles_per_ml = particles_per_ml * dilution_factor
                
                total_particles_row.append(str(particle_count))
                particles_per_ml_row.append(f"{particles_per_ml:.2f}")
                corrected_particles_per_ml_row.append(f"{corrected_particles_per_ml:.2f}")
                
                mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
                mass_fraction_row.append(f"{mass_fraction:.6f}")
                
                molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
                molecular_weight_row.append(f"{molecular_weight:.6f}" if molecular_weight else f"{atomic_mass:.6f}")
                
                is_pure = is_pure_element(mass_fraction)
                
                use_particle_calc = (data_type == "particle" and not is_pure)
                
                if sample_name in main_window.sample_detected_peaks and (element, isotope) in main_window.sample_detected_peaks[sample_name]:
                    particles = main_window.sample_detected_peaks[sample_name][(element, isotope)]
                    if particles:
                        counts = [p.get('total_counts', 0) for p in particles if p is not None]
                        
                        masses = []
                        moles = []
                        diameters = []
                        
                        if counts and ionic_data.get(element_key):
                            cal_data = ionic_data[element_key]
                            preferred_method = main_window.isotope_method_preferences.get(element_key, 'Force through zero')
                            method_map = {
                                'Force through zero': 'zero',
                                'Simple linear': 'simple',
                                'Weighted': 'weighted',
                                'Manual': 'manual', 
                            }
                            method_key = method_map.get(preferred_method, 'zero')
                            method_data = cal_data.get(method_key, cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get ('manual',{})))))
                            
                            if method_data and 'slope' in method_data and main_window.average_transport_rate > 0:
                                slope = method_data['slope']
                                conversion_factor = slope / (main_window.average_transport_rate * 1000)
                                
                                element_density = None
                                if main_window.periodic_table_widget:
                                    element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                                    if element_data:
                                        element_density = element_data.get('density')
                                
                                if conversion_factor > 0 and atomic_mass > 0:
                                    for count_val in counts:
                                        element_mass = count_val / conversion_factor
                                        
                                        if use_particle_calc:
                                            particle_mass = element_mass / mass_fraction
                                            masses.append(particle_mass)
                                            
                                            if molecular_weight and molecular_weight > 0:
                                                particle_mole = particle_mass / molecular_weight
                                            else:
                                                particle_mole = element_mass / atomic_mass
                                            moles.append(particle_mole)
                                            
                                            compound_density = main_window.get_element_density(element_key, sample_name)
                                            if compound_density and compound_density > 0:
                                                diameter = main_window.mass_to_diameter(particle_mass, compound_density)
                                                if not np.isnan(diameter):
                                                    diameters.append(diameter)
                                        else:
                                            masses.append(element_mass)
                                            element_mole = element_mass / atomic_mass
                                            moles.append(element_mole)
                                            
                                            if element_density and element_density > 0:
                                                diameter = main_window.mass_to_diameter(element_mass, element_density)
                                                if not np.isnan(diameter):
                                                    diameters.append(diameter)
                        
                        if masses:
                            mean_mass = np.mean(masses)
                            median_mass = np.median(masses)
                            std_mass = np.std(masses) if len(masses) > 1 else 0
                            total_mass = np.sum(masses)
                            
                            mean_mass_row.append(units.fmt_mass(mean_mass))
                            median_mass_row.append(units.fmt_mass(median_mass))
                            std_mass_row.append(units.fmt_mass(std_mass))
                            total_mass_row.append(units.fmt_mass(total_mass))
                        else:
                            mean_mass_row.append("0")
                            median_mass_row.append("0")
                            std_mass_row.append("0")
                            total_mass_row.append("0")
                        
                        if moles:
                            mean_moles = np.mean(moles)
                            median_moles = np.median(moles)
                            std_moles = np.std(moles) if len(moles) > 1 else 0
                            total_moles = np.sum(moles)
                            
                            mean_moles_row.append(units.fmt_moles(mean_moles))
                            median_moles_row.append(units.fmt_moles(median_moles))
                            std_moles_row.append(units.fmt_moles(std_moles))
                            total_moles_row.append(units.fmt_moles(total_moles))
                        else:
                            mean_moles_row.append("0")
                            median_moles_row.append("0")
                            std_moles_row.append("0")
                            total_moles_row.append("0")
                        
                        if diameters:
                            mean_diameter = np.mean(diameters)
                            mean_diameter_row.append(units.fmt_diameter(mean_diameter))
                        else:
                            mean_diameter_row.append("0")
                    else:
                        mean_mass_row.append("0")
                        median_mass_row.append("0")
                        std_mass_row.append("0")
                        total_mass_row.append("0")
                        mean_moles_row.append("0")
                        median_moles_row.append("0")
                        std_moles_row.append("0")
                        total_moles_row.append("0")
                        mean_diameter_row.append("0")
                else:
                    mean_mass_row.append("0")
                    median_mass_row.append("0")
                    std_mass_row.append("0")
                    total_mass_row.append("0")
                    mean_moles_row.append("0")
                    median_moles_row.append("0")
                    std_moles_row.append("0")
                    total_moles_row.append("0")
                    mean_diameter_row.append("0")
                
                background = threshold_data.get(element_key, {}).get('background', 0)
                background_ppt = main_window.element_limits.get(sample_name, {}).get(element_key, {}).get('background_ppt', 0)
                background_counts_row.append(f"{background:.2f}")
                background_ppt_row.append(f"{background_ppt:.5f}")
                
                if element_key in main_window.sample_parameters.get(sample_name, {}):
                    params = main_window.sample_parameters[sample_name][element_key]
                    use_window = params.get('use_window_size', False)
                    param_row = [
                        sample_name,
                        display_label,
                        str(params.get('include', True)),
                        params.get('method', 'Compound Poisson LogNormal'),
                        str(params.get('sigma', getattr(main_window, '_global_sigma', 0.55))),
                        str(params.get('manual_threshold', 10.0)),
                        str(params.get('min_continuous', 1)),
                        str(params.get('alpha', 0.000001)),
                        params.get('integration_method', "Background"),
                        str(params.get('iterative', True)),
                        str(use_window),
                        str(params.get('window_size', 5000)) if use_window else "N/A",
                        params.get('split_method', "1D Watershed"),
                        str(params.get('valley_ratio', 0.50)),
                    ]
                    detection_params_data.append(param_row)

            total_particles_data.append(total_particles_row)
            particles_per_ml_data.append(particles_per_ml_row)
            corrected_particles_per_ml_data.append(corrected_particles_per_ml_row)
            mass_fraction_data.append(mass_fraction_row)
            molecular_weight_data.append(molecular_weight_row)
            background_counts_data.append(background_counts_row)
            background_ppt_data.append(background_ppt_row)
            mean_mass_data.append(mean_mass_row)
            median_mass_data.append(median_mass_row)
            std_mass_data.append(std_mass_row)
            total_mass_data.append(total_mass_row)
            mean_moles_data.append(mean_moles_row)
            median_moles_data.append(median_moles_row)
            std_moles_data.append(std_moles_row)
            total_moles_data.append(total_moles_row)
            mean_diameter_data.append(mean_diameter_row)
                                    
        except Exception as e:
            print(f"Error processing {sample_name} for summary: {str(e)}")
            continue
    
    for row in total_particles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Particles per mL (Original)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in particles_per_ml_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Particles per mL (Dilution Corrected)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in corrected_particles_per_ml_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Mass Fractions Applied\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mass_fraction_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Molecular Weights Applied (g/mol)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in molecular_weight_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Mean Mass ({units.mass_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mean_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Median Mass ({units.mass_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in median_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Standard Deviation of Mass ({units.mass_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in std_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Total Mass ({units.mass_label}) per Element\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in total_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Mean Moles ({units.moles_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mean_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Median Moles ({units.moles_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in median_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Standard Deviation of Moles ({units.moles_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in std_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Total Moles ({units.moles_label}) per Element\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in total_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write(f"Mean Diameter ({units.diameter_label})\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mean_diameter_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Ionic background (counts)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in background_counts_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Ionic Background (ppt)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in background_ppt_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")

    summary_file.write("Detection Parameters\n")
    sigma_mode = getattr(main_window, '_sigma_mode', 'global')
    global_sigma = getattr(main_window, '_global_sigma', 0.55)
    summary_file.write(f"Sigma Mode: {sigma_mode}\n")
    summary_file.write(f"Global Sigma: {global_sigma:.3f}\n\n")
    summary_file.write("Sample,Element,Include,Method,Sigma,Manual Threshold,Min Points,Alpha (Error Rate),Integration Method,Iterative,Window Size Enabled,Window Size,Split Method,Valley Ratio\n")
    for row in detection_params_data:
        summary_file.write(",".join(row) + "\n")

def export_sample_file_with_mass_fractions(main_window, sample_name, file_path, all_elements, ionic_data, threshold_data, dilution_factor, data_type, units=None):
    """
    Export individual sample file with mixed element/particle calculations based on mass fractions and molecular weights.
    
    Args:
        main_window (object): Main window object
        sample_name (str): Sample name
        file_path (str): Output file path
        all_elements (list): List of tuples containing element data
        ionic_data (dict): Ionic calibration data
        threshold_data (dict): Threshold data
        dilution_factor (float): Dilution factor
        data_type (str): Data type ('element' or 'particle')
        units (ExportUnits | None): Unit preferences. If None, uses defaults (fg/fmol/nm).
        
    Returns:
        None
    """
    if units is None:
        units = ExportUnits()
    with open(file_path, 'w') as f:
        f.write(f"Sample: {sample_name}\n")
        f.write(f"Data Type: {data_type.capitalize()} Type\n")
        f.write(f"Dilution Factor Applied: {dilution_factor:.3f}x\n")
        
        if sample_name in main_window.sample_analysis_dates:
            date_info = main_window.sample_analysis_dates[sample_name]
            if 'date' in date_info:
                f.write(f"Analysis Date: {date_info['date']}\n")
            if 'time' in date_info:
                f.write(f"Analysis Time: {date_info['time']}\n")
                
        f.write(f"Export Date: {time.strftime('%Y-%m-%d')}\n")
        f.write(f"Export Time: {time.strftime('%H:%M:%S')}\n")
        
        f.write("-" * 50 + "\n\n")

        f.write("Calibration Information:\n")
        f.write(f"Transport Rate: {main_window.average_transport_rate:.4f} µL/s\n")
        
        dwell_time_ms = main_window.sample_dwell_times.get(sample_name, 0.0)
        f.write(f"Dwell Time: {dwell_time_ms:.4f} ms\n\n")

        f.write("Mass Fraction Configuration:\n")
        f.write(f"Data Type: {data_type.capitalize()} Type\n")
        headers = [
            "Element", "Mass Fraction", "Molecular Weight (g/mol)", "Element Density (g/cm³)", "Density Used (g/cm³)", "Notes"
        ]
        f.write(",".join(headers) + "\n")

        for element_key, display_label, element, isotope, atomic_mass in all_elements:
            mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
            molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
            is_pure = is_pure_element(mass_fraction)
            
            element_density = ""
            if main_window.periodic_table_widget:
                element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                if element_data:
                    element_density = f"{element_data.get('density', 0):.3f}"
            
            use_particle_calc = (data_type == "particle" and not is_pure)
            if use_particle_calc:
                compound_density = main_window.get_element_density(element_key, sample_name)
                density_used = f"{compound_density:.3f}" if compound_density else element_density
            else:
                density_used = element_density
            
            notes = "Pure element"
            if not is_pure:
                if (hasattr(main_window, 'sample_mass_fractions') and 
                    sample_name in main_window.sample_mass_fractions and 
                    element in main_window.sample_mass_fractions[sample_name]):
                    notes = "Sample-specific compound"
                elif (hasattr(main_window, 'element_mass_fractions') and 
                      element in main_window.element_mass_fractions):
                    notes = "Global compound setting"
            
            mw_display = f"{molecular_weight:.6f}" if molecular_weight else f"{atomic_mass:.6f}"
            
            row_data = [
                display_label,
                f"{mass_fraction:.6f}",
                mw_display,
                element_density,
                density_used,
                notes
            ]
            f.write(",".join(row_data) + "\n")

        f.write("\n")

        headers = [
            "Element", "Slope (cps/ppb)", "R²", "BEC (ppb)", "LOD (ppb)", 
            "LOQ (ppb)", "Threshold (counts)", "LOD_MDL (counts)", "Background (ppt)", "Background SD (ppt)", 
            f"MDL ({units.mass_label})", f"MQL ({units.mass_label})", f"SDL ({units.diameter_label})", f"SQL ({units.diameter_label})", "Mass Fraction Used", "Molecular Weight (g/mol)", "Density Used (g/cm³)"
        ]
        
        f.write(",".join(headers) + "\n")

        for element_key, display_label, element, isotope, atomic_mass in all_elements:
            cal_data = ionic_data.get(element_key, {})
            preferred_method = main_window.isotope_method_preferences.get(element_key, 'Force through zero')
            method_map = {
                'Force through zero': 'zero',
                'Simple linear': 'simple',
                'Weighted': 'weighted',
                'Manual': 'manual',  
            }
            method_key = method_map.get(preferred_method, 'zero')
            method_data = cal_data.get(method_key, cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{})))))
            thresholds = threshold_data.get(element_key, {})
            limits = main_window.element_limits.get(sample_name, {}).get(element_key, {})
            
            mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
            molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
            is_pure = is_pure_element(mass_fraction)
            
            element_density = None
            if main_window.periodic_table_widget:
                element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                if element_data:
                    element_density = element_data.get('density')
            
            use_particle_calc = (data_type == "particle" and not is_pure)
            if use_particle_calc:
                compound_density = main_window.get_element_density(element_key, sample_name)
                working_density = compound_density if compound_density else element_density
                density_label = f"{compound_density:.3f}" if compound_density else f"{element_density:.3f}" if element_density else "N/A"
            else:
                working_density = element_density
                density_label = f"{element_density:.3f}" if element_density else "N/A"

            row_data = [
                display_label,
                f"{method_data.get('slope', 'N/A'):.2e}" if method_data else "N/A",
                f"{method_data.get('r_squared', 'N/A'):.6f}" if method_data else "N/A",
                f"{method_data.get('bec', 'N/A'):.2f}" if method_data else "N/A",
                f"{method_data.get('lod', 'N/A'):.2f}" if method_data else "N/A",
                f"{method_data.get('loq', 'N/A'):.2f}" if method_data else "N/A",
                f"{thresholds.get('LOD_counts', 'N/A'):.2f}" if 'LOD_counts' in thresholds else "N/A",    
                f"{thresholds.get('LOD_MDL', 'N/A'):.2f}" if 'LOD_MDL' in thresholds else "N/A",  
                f"{limits.get('background_ppt', 'N/A'):.5f}" if 'background_ppt' in limits else "N/A",
                f"{limits.get('background_sd_ppt', 'N/A'):.5f}" if 'background_sd_ppt' in limits else "N/A"
            ]
            
            element_mdl = limits.get('MDL', 0)
            element_mql = limits.get('MQL', 0)
            
            if use_particle_calc:
                mdl = element_mdl / mass_fraction if element_mdl > 0 and mass_fraction > 0 else 0
                mql = element_mql / mass_fraction if element_mql > 0 and mass_fraction > 0 else 0
            else:
                mdl = element_mdl
                mql = element_mql
            
            sdl = 0
            sql = 0
            if working_density and working_density > 0:
                if mdl > 0:
                    sdl = main_window.mass_to_diameter(mdl, working_density)
                if mql > 0:
                    sql = main_window.mass_to_diameter(mql, working_density)
            
            mw_display = f"{molecular_weight:.6f}" if molecular_weight else f"{atomic_mass:.6f}"
            
            row_data.extend([
                units.fmt_mass(mdl) if mdl > 0 else "N/A",
                units.fmt_mass(mql) if mql > 0 else "N/A",
                units.fmt_diameter(sdl) if sdl > 0 and not np.isnan(sdl) else "N/A",
                units.fmt_diameter(sql) if sql > 0 and not np.isnan(sql) else "N/A",
                f"{mass_fraction:.6f}",
                mw_display,
                density_label
            ])
            
            f.write(",".join(row_data) + "\n")
            
        f.write("\n")

        f.write("Detection Parameters:\n")
        sigma_mode = getattr(main_window, '_sigma_mode', 'global')
        global_sigma = getattr(main_window, '_global_sigma', 0.55)
        f.write(f"Sigma Mode: {sigma_mode}\n")
        f.write(f"Global Sigma: {global_sigma:.3f}\n")
        det_headers = [
            "Element", "Include", "Method", "Sigma", "Manual Threshold",
            "Min Points", "Alpha (Error Rate)", "Integration Method",
            "Iterative", "Window Size Enabled", "Window Size",
            "Split Method", "Valley Ratio"
        ]
        f.write(",".join(det_headers) + "\n")
        sample_params = main_window.sample_parameters.get(sample_name, {})
        for element_key, display_label, element, isotope, atomic_mass in all_elements:
            params = sample_params.get(element_key, {})
            use_window = params.get('use_window_size', False)
            det_row = [
                display_label,
                str(params.get('include', True)),
                params.get('method', 'Compound Poisson LogNormal'),
                str(params.get('sigma', global_sigma)),
                str(params.get('manual_threshold', 10.0)),
                str(params.get('min_continuous', 1)),
                str(params.get('alpha', 0.000001)),
                params.get('integration_method', 'Background'),
                str(params.get('iterative', True)),
                str(use_window),
                str(params.get('window_size', 5000)) if use_window else "N/A",
                params.get('split_method', '1D Watershed'),
                str(params.get('valley_ratio', 0.50)),
            ]
            f.write(",".join(det_row) + "\n")
        f.write("\n")

        f.write("Particle Statistics:\n")
        particle_headers = ["Element", "Total Particles", "Particles/mL (Original)", "Particles/mL (Dilution Corrected)", "Dilution Factor", "Mass Fraction Used", "Molecular Weight (g/mol)"]
        f.write(",".join(particle_headers) + "\n")

        total_volume_ml = 0
        if main_window.average_transport_rate > 0 and sample_name in main_window.time_array_by_sample:
            time_array = main_window.time_array_by_sample[sample_name]
            total_time = time_array[-1] - time_array[0]
            total_volume_ml = (main_window.average_transport_rate * total_time) / 1000

        for element_key, display_label, element, isotope, atomic_mass in all_elements:
            particle_count = 0
            if sample_name in main_window.sample_detected_peaks:
                if (element, isotope) in main_window.sample_detected_peaks[sample_name]:
                    particle_count = len(main_window.sample_detected_peaks[sample_name][(element, isotope)])

            particles_per_ml = (particle_count / total_volume_ml) if total_volume_ml > 0 else 0
            corrected_particles_per_ml = particles_per_ml * dilution_factor
            mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
            molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
            mw_display = f"{molecular_weight:.6f}" if molecular_weight else f"{atomic_mass:.6f}"
            
            row_data = [
                display_label,
                str(particle_count),
                f"{particles_per_ml:.2f}",
                f"{corrected_particles_per_ml:.2f}",
                f"{dilution_factor:.3f}x",
                f"{mass_fraction:.6f}",
                mw_display
            ]
            f.write(",".join(row_data) + "\n")

        f.write("\n")

        if sample_name in main_window.sample_particle_data:
            particles = main_window.sample_particle_data[sample_name]
            
            f.write("Totals:\n")
            
            total_headers = ["Measurement Type"]
            for _, display_label, _, _, _ in all_elements:
                total_headers.extend([
                    f"{display_label} (counts)",
                    f"{display_label} ({units.mass_label})",
                    f"{display_label} ({units.moles_label})",
                    f"{display_label} Mass %",
                    f"{display_label} Mole %"
                ])
            
            total_headers.extend([f"Total ({units.mass_label})", f"Total ({units.moles_label})"])
            
            f.write(",".join(total_headers) + "\n")
            
            total_masses = {display_label: 0 for _, display_label, _, _, _ in all_elements}
            total_moles = {display_label: 0 for _, display_label, _, _, _ in all_elements}
            
            for particle in particles:
                for element_key, display_label, element, isotope, atomic_mass in all_elements:
                    counts = particle['elements'].get(display_label, 0)
                    mass_fg = 0
                    moles = 0
                    
                    if counts > 0 and element_key in ionic_data:
                        cal_data = ionic_data[element_key]
                        preferred_method = main_window.isotope_method_preferences.get(element_key, 'Force through zero')
                        method_map = {
                            'Force through zero': 'zero',
                            'Simple linear': 'simple',
                            'Weighted': 'weighted',
                            'Manual': 'manual',
                        }
                        method_key = method_map.get(preferred_method, 'zero')
                        method_data = cal_data.get(method_key, cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{})))))
                        
                        if method_data and 'slope' in method_data and main_window.average_transport_rate > 0:
                            slope = method_data['slope']
                            conversion_factor = slope / (main_window.average_transport_rate * 1000)
                            mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
                            molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
                            is_pure = is_pure_element(mass_fraction)
                            
                            if conversion_factor > 0 and atomic_mass > 0:
                                element_mass = counts / conversion_factor
                                
                                use_particle_calc = (data_type == "particle" and not is_pure)
                                if use_particle_calc:
                                    mass_fg = element_mass / mass_fraction
                                    if molecular_weight and molecular_weight > 0:
                                        moles = mass_fg / molecular_weight
                                    else:
                                        moles = element_mass / atomic_mass
                                else:
                                    mass_fg = element_mass
                                    moles = element_mass / atomic_mass
                    
                    total_masses[display_label] += mass_fg
                    total_moles[display_label] += moles
            
            grand_total_mass = sum(total_masses.values())
            grand_total_moles = sum(total_moles.values())
            
            total_row = ["Total"]
            for _, display_label, _, _, _ in all_elements:
                mass = total_masses[display_label]
                moles = total_moles[display_label]
                
                mass_percent = (mass / grand_total_mass * 100) if grand_total_mass > 0 else 0
                mole_percent = (moles / grand_total_moles * 100) if grand_total_moles > 0 else 0
                
                total_row.extend([
                    "0",
                    units.fmt_mass(mass),
                    units.fmt_moles(moles),
                    f"{mass_percent:.2f}",
                    f"{mole_percent:.2f}"
                ])
            
            total_row.extend([
                units.fmt_mass(grand_total_mass), 
                units.fmt_moles(grand_total_moles)
            ])
            
            f.write(",".join(total_row) + "\n")
            f.write("\n")
            
        if sample_name in main_window.sample_particle_data:
            f.write("Results:\n")
            
            headers = ["Particle ID", "Start Time (s)", "End Time (s)"]
            for _, display_label, _, _, _ in all_elements:
                headers.extend([
                    f"{display_label} (counts)",
                    f"{display_label} ({units.mass_label})",
                    f"{display_label} ({units.moles_label})",
                    f"{display_label} ({units.diameter_label})"
                ])
            
            headers.extend([f"Total ({units.mass_label})", f"Total ({units.moles_label})"])
            
            f.write(",".join(headers) + "\n")

            for i, particle in enumerate(main_window.sample_particle_data[sample_name], 1):
                row_data = [str(i), f"{particle['start_time']:.6f}", f"{particle['end_time']:.6f}"]
                
                total_mass = 0
                total_moles = 0
                
                for element_key, display_label, element, isotope, atomic_mass in all_elements:
                    counts = particle['elements'].get(display_label, 0)
                    mass_fg = 0
                    moles = 0
                    diameter_nm = 0
                    mass_fraction = main_window.get_mass_fraction(element_key, sample_name)
                    molecular_weight = get_molecular_weight_for_export(main_window, element_key, sample_name)
                    is_pure = is_pure_element(mass_fraction)
                    
                    if counts > 0 and element_key in ionic_data:
                        cal_data = ionic_data[element_key]
                        preferred_method = main_window.isotope_method_preferences.get(element_key, 'Force through zero')
                        method_map = {
                            'Force through zero': 'zero',
                            'Simple linear': 'simple',
                            'Weighted': 'weighted',
                            'Manual': 'manual',
                        }
                        method_key = method_map.get(preferred_method, 'zero')
                        method_data = cal_data.get(method_key, cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{})))))
                        
                        if method_data and 'slope' in method_data and main_window.average_transport_rate > 0:
                            slope = method_data['slope']
                            conversion_factor = slope / (main_window.average_transport_rate * 1000)
                            
                            if conversion_factor > 0 and atomic_mass > 0:
                                element_mass = counts / conversion_factor
                                
                                use_particle_calc = (data_type == "particle" and not is_pure)
                                if use_particle_calc:
                                    mass_fg = element_mass / mass_fraction
                                    if molecular_weight and molecular_weight > 0:
                                        moles = mass_fg / molecular_weight
                                    else:
                                        moles = element_mass / atomic_mass
                                    
                                    compound_density = main_window.get_element_density(element_key, sample_name)
                                    if compound_density and compound_density > 0:
                                        diameter_nm = main_window.mass_to_diameter(mass_fg, compound_density)
                                else:
                                    mass_fg = element_mass
                                    moles = element_mass / atomic_mass
                                    
                                    if main_window.periodic_table_widget:
                                        element_data = main_window.periodic_table_widget.get_element_by_symbol(element)
                                        if element_data:
                                            element_density = element_data.get('density')
                                            if element_density and element_density > 0:
                                                diameter_nm = main_window.mass_to_diameter(element_mass, element_density)
                                
                                total_mass += mass_fg
                                total_moles += moles
                    
                    row_data.extend([
                        f"{counts:.4f}",
                        units.fmt_mass_or_zero(mass_fg),
                        units.fmt_moles_or_zero(moles),
                        units.fmt_diameter_or_zero(diameter_nm),
                    ])
                
                row_data.extend([
                    units.fmt_mass(total_mass),
                    units.fmt_moles(total_moles),
                ])
                
                f.write(",".join(row_data) + "\n")