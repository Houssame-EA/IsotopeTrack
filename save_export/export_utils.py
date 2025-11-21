from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, 
                              QCheckBox, QRadioButton, QScrollArea, QWidget, 
                              QDialogButtonBox, QFileDialog, QMessageBox,
                              QHBoxLayout, QLabel, QDoubleSpinBox)
from PySide6.QtCore import Qt
import time
import numpy as np
import math
import time

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
    export_dialog.resize(500, 700)
    
    layout = QVBoxLayout(export_dialog)
    
    data_type_group = QGroupBox("Data Type Selection")
    data_type_layout = QVBoxLayout()
    
    element_type_rb = QRadioButton("Element Type Data")
    particle_type_rb = QRadioButton("Particle Type Data")
    element_type_rb.setChecked(True)
    
    data_type_layout.addWidget(element_type_rb)
    data_type_layout.addWidget(particle_type_rb)
    data_type_group.setLayout(data_type_layout)
    layout.addWidget(data_type_group)
    
    sample_group = QGroupBox("Select Samples to Export & Set Dilution Factors")
    sample_layout = QVBoxLayout()
    
    select_all_cb = QCheckBox("Select All")
    select_all_cb.setChecked(True)
    sample_layout.addWidget(select_all_cb)
    
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_content = QWidget()
    scroll_layout = QVBoxLayout(scroll_content)
    
    sample_checkboxes = {}
    dilution_spinboxes = {}
    
    for sample_name in main_window.sample_to_folder_map.keys():
        sample_row = QHBoxLayout()
        
        cb = QCheckBox(sample_name)
        cb.setChecked(True)
        sample_row.addWidget(cb)
        sample_checkboxes[sample_name] = cb
        
        sample_row.addStretch()
        
        dilution_label = QLabel("Dilution Factor:")
        sample_row.addWidget(dilution_label)
        
        dilution_spinbox = QDoubleSpinBox()
        dilution_spinbox.setRange(1.0, 1000000.0)
        dilution_spinbox.setValue(1.0)
        dilution_spinbox.setDecimals(3)
        dilution_spinbox.setSuffix("x")
        sample_row.addWidget(dilution_spinbox)
        dilution_spinboxes[sample_name] = dilution_spinbox
        
        row_widget = QWidget()
        row_widget.setLayout(sample_row)
        scroll_layout.addWidget(row_widget)
    
    scroll_content.setLayout(scroll_layout)
    scroll.setWidget(scroll_content)
    sample_layout.addWidget(scroll)
    sample_group.setLayout(sample_layout)
    layout.addWidget(sample_group)
    
    type_group = QGroupBox("Export Type")
    type_layout = QVBoxLayout()
    
    export_all_rb = QRadioButton("Export all (sample files and summary)")
    export_samples_rb = QRadioButton("Export sample files only")
    export_summary_rb = QRadioButton("Export summary file only")
    export_all_rb.setChecked(True)
    
    type_layout.addWidget(export_all_rb)
    type_layout.addWidget(export_samples_rb)
    type_layout.addWidget(export_summary_rb)
    type_group.setLayout(type_layout)
    layout.addWidget(type_group)
    
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(export_dialog.accept)
    buttons.rejected.connect(export_dialog.reject)
    layout.addWidget(buttons)
    
    def toggle_all_samples(state):
        for cb in sample_checkboxes.values():
            cb.setChecked(state == Qt.Checked)
    
    select_all_cb.stateChanged.connect(toggle_all_samples)
    
    if export_dialog.exec() != QDialog.Accepted:
        return False
    
    selected_samples = [sample for sample, cb in sample_checkboxes.items() if cb.isChecked()]
    sample_dilutions = {sample: dilution_spinboxes[sample].value() 
                       for sample in selected_samples}
    
    data_type = "particle" if particle_type_rb.isChecked() else "element"
    
    if not selected_samples:
        QMessageBox.warning(main_window, "Warning", "No samples selected for export.")
        return False
    
    export_type = "all"
    if export_samples_rb.isChecked():
        export_type = "samples"
    elif export_summary_rb.isChecked():
        export_type = "summary"
        
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
                        main_window, summary_file, selected_samples, all_elements, element_labels, sample_dilutions, data_type
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
                        main_window, sample_name, file_path, all_elements, ionic_data, threshold_data, dilution_factor, data_type
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

def export_summary_file_with_mass_fractions(main_window, summary_file, selected_samples, all_elements, element_labels, sample_dilutions, data_type):
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
        
    Returns:
        None
    """
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
                            
                            mean_mass_row.append(f"{mean_mass:.2f}")
                            median_mass_row.append(f"{median_mass:.2f}")
                            std_mass_row.append(f"{std_mass:.2f}")
                            total_mass_row.append(f"{total_mass:.2f}")
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
                            
                            mean_moles_row.append(f"{mean_moles:.6f}")
                            median_moles_row.append(f"{median_moles:.6f}")
                            std_moles_row.append(f"{std_moles:.6f}")
                            total_moles_row.append(f"{total_moles:.6f}")
                        else:
                            mean_moles_row.append("0")
                            median_moles_row.append("0")
                            std_moles_row.append("0")
                            total_moles_row.append("0")
                        
                        if diameters:
                            mean_diameter = np.mean(diameters)
                            mean_diameter_row.append(f"{mean_diameter:.1f}")
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
                    param_row = [
                        sample_name,
                        display_label,
                        str(params.get('include', True)),
                        params.get('method', "Compound Poisson LogNormal"),  
                        str(params.get('manual_threshold', 10.0)),  
                        str(params.get('apply_smoothing', False)),  
                        str(params.get('smooth_window', 3)),
                        str(params.get('iterations', 1)),
                        str(params.get('min_continuous', 1)),  
                        str(params.get('alpha', 0.000001)), 
                        params.get('integration_method', "Background"),
                        str(params.get('iterative', True)), 
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
    
    summary_file.write("Mean Mass (fg)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mean_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Median Mass (fg)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in median_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Standard Deviation of Mass (fg)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in std_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Total Mass (fg) per Element\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in total_mass_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Mean Moles (fmol)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in mean_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Median Moles (fmol)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in median_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Standard Deviation of Moles (fmol)\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in std_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Total Moles (fmol) per Element\n")
    summary_file.write("Sample," + ",".join(element_labels) + "\n")
    for row in total_moles_data:
        summary_file.write(",".join(row) + "\n")
    summary_file.write("\n")
    
    summary_file.write("Mean Diameter (nm)\n")
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

    summary_file.write("Detection Parameters\n\n")
    summary_file.write("Sample,Element,Include,Method,Manual Threshold,Apply Smoothing,Window Length,Iterations,Min Points,Alpha (Error Rate),Integration Method,Iterative\n")
    for row in detection_params_data:
        summary_file.write(",".join(row) + "\n")

def export_sample_file_with_mass_fractions(main_window, sample_name, file_path, all_elements, ionic_data, threshold_data, dilution_factor, data_type):
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
        
    Returns:
        None
    """
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
            "MDL (fg)", "MQL (fg)", "SDL (nm)", "SQL (nm)", "Mass Fraction Used", "Molecular Weight (g/mol)", "Density Used (g/cm³)"
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
                f"{mdl:.2e}" if mdl > 0 else "N/A",
                f"{mql:.2e}" if mql > 0 else "N/A",
                f"{sdl:.1f}" if sdl > 0 and not np.isnan(sdl) else "N/A",
                f"{sql:.1f}" if sql > 0 and not np.isnan(sql) else "N/A",
                f"{mass_fraction:.6f}",
                mw_display,
                density_label
            ])
            
            f.write(",".join(row_data) + "\n")
            
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
                    f"{display_label} (fg)",
                    f"{display_label} (fmol)",
                    f"{display_label} Mass %",
                    f"{display_label} Mole %"
                ])
            
            total_headers.extend(["Total (fg)", "Total (fmol)"])
            
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
                    f"{mass:.4f}",
                    f"{moles:.6f}",
                    f"{mass_percent:.2f}",
                    f"{mole_percent:.2f}"
                ])
            
            total_row.extend([
                f"{grand_total_mass:.4f}", 
                f"{grand_total_moles:.6f}"
            ])
            
            f.write(",".join(total_row) + "\n")
            f.write("\n")
            
        if sample_name in main_window.sample_particle_data:
            f.write("Results:\n")
            
            headers = ["Particle ID", "Start Time (s)", "End Time (s)"]
            for _, display_label, _, _, _ in all_elements:
                headers.extend([
                    f"{display_label} (counts)",
                    f"{display_label} (fg)",
                    f"{display_label} (fmol)",
                    f"{display_label} (nm)"
                ])
            
            headers.extend(["Total (fg)", "Total (fmol)"])
            
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
                        f"{mass_fg:.8f}" if mass_fg > 0 else "0",
                        f"{moles:.10f}" if moles > 0 else "0",
                        f"{diameter_nm:.2f}" if diameter_nm > 0 and not np.isnan(diameter_nm) else "0"
                    ])
                
                row_data.extend([
                    f"{total_mass:.8f}", 
                    f"{total_moles:.10f}"
                ])
                
                f.write(",".join(row_data) + "\n")