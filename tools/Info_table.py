from PySide6.QtWidgets import (QVBoxLayout, QWidget, QLabel, QHBoxLayout, QScrollArea,
                               QDialog, QTableWidget, QTableWidgetItem, QCheckBox, 
                               QComboBox, QPushButton, QGroupBox, QHeaderView, 
                               QTabWidget, QProgressBar, QFrame, QSpinBox, QTextEdit,
                               QSplitter, QGridLayout, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Slot, QEvent
from PySide6.QtGui import QColor, QBrush, QFont, QCursor
import numpy as np
import json
from pathlib import Path
from scipy.stats import chi2


# ---------------------------------------------------------------------------
#  Isotope anomaly detection (abundance from periodic table widget)
# ---------------------------------------------------------------------------

def _build_abundance_map(element_data):
    """
    Build a {nominal_mass: fractional_abundance} map from periodic-table element data.

    The periodic table stores abundance as a percentage (0-100). We convert to
    fraction (0-1) for statistical calculations.

    Args:
        element_data (dict): Element dict from PeriodicTableWidget, containing
            an 'isotopes' list of dicts with 'mass', 'abundance', 'label'.

    Returns:
        dict: {int(round(mass)): fractional_abundance} for isotopes with abundance > 0
    """
    if not element_data or 'isotopes' not in element_data:
        return {}
    result = {}
    for iso in element_data['isotopes']:
        if not isinstance(iso, dict):
            continue
        mass = iso.get('mass', 0)
        abundance_pct = iso.get('abundance', 0)
        if abundance_pct > 0:
            result[round(mass)] = abundance_pct / 100.0
    return result


def detect_isotope_anomalies(element_symbol, isotope_counts, element_data,
                             min_detections=3):
    """
    Detect anomalies in isotope detection consistency for a single element.

    Compares observed detection counts across isotopes of the same element
    against expected ratios from natural abundances using a chi-squared test.

    Anomaly types reported:
        missing_major     – Major isotope (>10 %) has 0 detections while a
                            minor isotope was detected.
        reverse_detection – Less-abundant isotope detected more than the
                            more-abundant one (chi-squared p < 0.01).
        ratio_anomaly     – Both detected, but observed ratio significantly
                            deviates from natural abundance (chi-squared p < 0.01).
        missing_minor_unexpected – Minor isotope has 0 detections but Poisson
                            probability of 0 given expected count is < 5 %.
        expected           – Minor isotope not detected, consistent with low
                            abundance (Poisson p(0) > 5 %).

    Args:
        element_symbol (str): Element symbol, e.g. "Ag".
        isotope_counts (dict): {isotope_mass (float): n_detected_peaks (int)}
            The keys are the exact masses from the periodic table.
        element_data (dict): Element dict from PeriodicTableWidget.
        min_detections (int): Minimum total detections to run the test.

    Returns:
        list[dict]: Anomaly records with keys:
            type, isotope_a, isotope_b, details, severity, p_value
    """
    abundance_map = _build_abundance_map(element_data)
    if not abundance_map:
        return []

    isotope_info = []
    for iso_mass, count in isotope_counts.items():
        nominal = round(iso_mass)
        abund = abundance_map.get(nominal)
        if abund is not None:
            isotope_info.append((iso_mass, count, abund))

    if len(isotope_info) < 2:
        return []

    total_detections = sum(c for _, c, _ in isotope_info)
    if total_detections < min_detections:
        return []

    anomalies = []

    isotope_info.sort(key=lambda x: x[2], reverse=True)

    el = element_symbol

    for i in range(len(isotope_info)):
        for j in range(i + 1, len(isotope_info)):
            mass_a, count_a, abund_a = isotope_info[i]
            mass_b, count_b, abund_b = isotope_info[j]
            nom_a = round(mass_a)
            nom_b = round(mass_b)

            if count_a == 0 and count_b > 0 and abund_a > 0.10:
                anomalies.append({
                    'type': 'missing_major',
                    'isotope_a': mass_a, 'isotope_b': mass_b,
                    'details': (f"{nom_a}{el} ({abund_a*100:.1f}%) has 0 detections "
                                f"but {nom_b}{el} ({abund_b*100:.1f}%) has {count_b}"),
                    'severity': 'critical',
                    'p_value': None
                })
                continue

            if count_b == 0 and count_a > 0 and abund_a > 0:
                expected_b = count_a * (abund_b / abund_a)
                p_zero = float(np.exp(-expected_b)) if expected_b < 700 else 0.0

                if p_zero > 0.05:
                    anomalies.append({
                        'type': 'expected',
                        'isotope_a': mass_a, 'isotope_b': mass_b,
                        'details': (f"{nom_b}{el} not detected — expected "
                                    f"(abundance {abund_b*100:.2f}%, "
                                    f"expected ~{expected_b:.1f} from {count_a} "
                                    f"detections of {nom_a}{el})"),
                        'severity': 'info',
                        'p_value': p_zero
                    })
                else:
                    anomalies.append({
                        'type': 'missing_minor_unexpected',
                        'isotope_a': mass_a, 'isotope_b': mass_b,
                        'details': (f"{nom_b}{el} has 0 detections but "
                                    f"~{expected_b:.1f} expected from abundance "
                                    f"ratio (p={p_zero:.2e})"),
                        'severity': 'warning',
                        'p_value': p_zero
                    })
                continue

            if count_a > 0 and count_b > 0:
                total_pair = count_a + count_b
                total_abund = abund_a + abund_b
                if total_abund > 0:
                    expected_a = total_pair * (abund_a / total_abund)
                    expected_b_val = total_pair * (abund_b / total_abund)

                    if expected_a >= 1 and expected_b_val >= 1:
                        chi2_stat = (
                            (count_a - expected_a) ** 2 / expected_a +
                            (count_b - expected_b_val) ** 2 / expected_b_val
                        )
                        p_val = float(1.0 - chi2.cdf(chi2_stat, df=1))

                        observed_ratio = count_b / count_a if count_a > 0 else float('inf')
                        expected_ratio = abund_b / abund_a if abund_a > 0 else 0

                        if p_val < 0.01:
                            if count_b > count_a and abund_b < abund_a:
                                anomalies.append({
                                    'type': 'reverse_detection',
                                    'isotope_a': mass_a, 'isotope_b': mass_b,
                                    'details': (
                                        f"{nom_b}{el} ({abund_b*100:.1f}%) has "
                                        f"{count_b} detections > {nom_a}{el} "
                                        f"({abund_a*100:.1f}%) with {count_a} "
                                        f"(χ² p={p_val:.2e})"),
                                    'severity': 'critical',
                                    'p_value': p_val
                                })
                            else:
                                anomalies.append({
                                    'type': 'ratio_anomaly',
                                    'isotope_a': mass_a, 'isotope_b': mass_b,
                                    'details': (
                                        f"Ratio {nom_b}/{nom_a}{el}: observed "
                                        f"{observed_ratio:.2f} vs expected "
                                        f"{expected_ratio:.2f} (χ² p={p_val:.2e})"),
                                    'severity': 'warning',
                                    'p_value': p_val
                                })
    return anomalies

import numpy as np
from scipy.stats import poisson

def batch_pvalues(heights, bg_scalar, sigma=0.47):
    """
    Calculate p-values for a batch of peak heights given a background level.
    
    Args:
        heights (list or np.ndarray): Detected peak heights.
        bg_scalar (float): Mean background level.
        sigma (float): Sigma value for compound Poisson (if applicable).
        
    Returns:
        np.ndarray: Array of calculated p-values.
    """
    heights_arr = np.array(heights)

    pvals = poisson.sf(heights_arr - 1, bg_scalar)

    return pvals


# ---------------------------------------------------------------------------
#  InfoTooltip Widget
# ---------------------------------------------------------------------------

class InfoTooltip(QWidget):
    """
    Custom tooltip widget for displaying sample analysis information and quality metrics.

    Uses SNR for per-isotope quality assessment and natural-abundance ratios
    (from the periodic table widget) for isotope consistency anomaly detection.
    """

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setup_ui()
        self.cached_stats = {}
        self.cached_isotopes = {}
        self._click_filter_installed = False
        self._trigger_widget = None

    def set_trigger_widget(self, widget):
        """Set the widget (e.g. info button) whose clicks should NOT auto-close us.
        Args:
            widget (Any): Target widget.
        """
        self._trigger_widget = widget

    # --- Click-outside-to-dismiss -------------------------------------------

    def show(self):
        """Show the tooltip and install a global click filter."""
        super().show()
        if not self._click_filter_installed:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().installEventFilter(self)
            self._click_filter_installed = True

    def hide(self):
        """Hide the tooltip and remove the global click filter."""
        if self._click_filter_installed:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().removeEventFilter(self)
            self._click_filter_installed = False
        super().hide()

    def eventFilter(self, obj, event):
        """Hide on any mouse click that lands outside the tooltip.
        Args:
            obj (Any): The obj.
            event (Any): Qt event object.
        Returns:
            object: Result of the operation.
        """
        if event.type() == QEvent.MouseButtonPress:
            click_pos = QCursor.pos()
            if self.geometry().contains(click_pos):
                return super().eventFilter(obj, event)
            if self._trigger_widget is not None:
                from PySide6.QtCore import QRect, QPoint
                btn_global_tl = self._trigger_widget.mapToGlobal(QPoint(0, 0))
                btn_screen_rect = QRect(btn_global_tl, self._trigger_widget.size())
                if btn_screen_rect.contains(click_pos):
                    return super().eventFilter(obj, event)
            self.hide()
            return False
        return super().eventFilter(obj, event)

    def setup_ui(self):
        """Setup the user interface."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 25, 25, 25)
        self.main_layout.setSpacing(20)

        self.datetime_widget = QWidget()
        self.datetime_layout = QVBoxLayout(self.datetime_widget)
        self.datetime_layout.setSpacing(5)

        self.date_label = QLabel("Analysis Date: Not available")
        self.time_label = QLabel("Analysis Time: Not available")
        self.date_label.setStyleSheet("font-size: 15px; font-weight: bold; color: black;")
        self.time_label.setStyleSheet("font-size: 15px; font-weight: bold; color: black;")

        self.datetime_layout.addWidget(self.date_label)
        self.datetime_layout.addWidget(self.time_label)
        self.datetime_widget.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.main_layout.addWidget(self.datetime_widget)
        self.datetime_widget.setVisible(False)

        self.stats_widget = QWidget()
        self.stats_layout = QHBoxLayout(self.stats_widget)
        self.stats_layout.setSpacing(20)

        self.stat_boxes = {}
        stat_types = ["Active Samples", "Elements", "Suspected %", "Quality Score"]
        for stat_type in stat_types:
            stat_box = self._create_stat_box()
            self.stat_boxes[stat_type] = stat_box
            self.stats_layout.addWidget(stat_box)

        self.main_layout.addWidget(self.stats_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setMinimumHeight(200)
        self.scroll_area.setMaximumHeight(600)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 0.1);
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.3);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.sample_content = QWidget()
        self.sample_layout = QVBoxLayout(self.sample_content)
        self.scroll_area.setWidget(self.sample_content)
        self.main_layout.addWidget(self.scroll_area)

        self.setFixedWidth(750)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #8860D0, stop:1 #5AB9EA);
                border-radius: 20px;
            }
        """)

    # ----- helpers --------------------------------------------------------

    def _create_stat_box(self):
        """
        Returns:
            object: Result of the operation.
        """
        stat_box = QWidget()
        stat_layout = QVBoxLayout(stat_box)
        value_label = QLabel()
        desc_label = QLabel()
        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        desc_label.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.8);")
        stat_layout.addWidget(value_label)
        stat_layout.addWidget(desc_label)
        stat_box.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 12px;
            }
        """)
        return stat_box

    # ----- public API ------------------------------------------------------

    def update_stats(self, active_samples, total_elements, Suspected_percentage,
                     analysis_date_info=None):
        """
        Update the statistics display.

        Args:
            active_samples (int): Number of active samples
            total_elements (int): Total number of elements
            Suspected_percentage (float): Percentage of suspected values
            analysis_date_info (dict, optional): Dictionary with 'date' and 'time' keys
        """
        quality_score = max(0, 100 - Suspected_percentage)

        new_stats = {
            "Active Samples": str(active_samples),
            "Elements": str(total_elements),
            "Suspected %": f"{Suspected_percentage}%",
            "Quality Score": f"{quality_score:.0f}"
        }

        if analysis_date_info:
            self.datetime_widget.setVisible(True)
            if 'date' in analysis_date_info:
                self.date_label.setText(f"Analysis Date: {analysis_date_info['date']}")
            if 'time' in analysis_date_info:
                self.time_label.setText(f"Analysis Time: {analysis_date_info['time']}")
        else:
            self.datetime_widget.setVisible(False)

        if new_stats != self.cached_stats:
            self.cached_stats = new_stats
            for stat_type, value in new_stats.items():
                stat_box = self.stat_boxes[stat_type]
                value_label = stat_box.layout().itemAt(0).widget()
                desc_label = stat_box.layout().itemAt(1).widget()

                if stat_type == "Suspected %":
                    pct = float(value.strip('%'))
                    if pct >= 50:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FF4444;")
                    elif pct >= 30:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFAA33;")
                    else:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #44FF44;")
                elif stat_type == "Quality Score":
                    score = float(value)
                    if score >= 70:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #44FF44;")
                    elif score >= 50:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFAA33;")
                    else:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FF4444;")

                value_label.setText(value)
                desc_label.setText(stat_type)

    def update_sample_content(self, current_sample, selected_isotopes,
                              detected_peaks, multi_element_particles,
                              periodic_table_widget=None):
        """
        Update the sample content display with isotope information, SNR quality
        metrics, and isotope-consistency anomaly detection.

        Args:
            current_sample (str): Name of current sample
            selected_isotopes (dict): {element: [isotope_mass, ...]}
            detected_peaks (dict): {(element, isotope): [peak_dicts]}
            multi_element_particles (list): List of multi-element particles
            periodic_table_widget: PeriodicTableWidget instance (provides
                abundance data for anomaly detection). If *None*, the anomaly
                section is simply skipped.
        """
        new_isotopes = {
            'sample': current_sample,
            'isotopes': selected_isotopes.copy() if selected_isotopes else {},
            'peaks': detected_peaks.copy() if detected_peaks else {},
            'multi': len(multi_element_particles) if multi_element_particles else 0
        }

        if new_isotopes == self.cached_isotopes:
            return

        self.cached_isotopes = new_isotopes

        for i in reversed(range(self.sample_layout.count())):
            self.sample_layout.itemAt(i).widget().setParent(None)

        if not current_sample:
            return

        sample_box = QWidget()
        sample_layout = QVBoxLayout(sample_box)

        sample_title = QLabel(f"Current Sample: {current_sample}")
        sample_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        sample_layout.addWidget(sample_title)

        if selected_isotopes:
            total_particles = 0
            total_strong = 0
            element_count = 0
            valid_elements = 0

            element_detection_counts = {}

            for element, isotopes in selected_isotopes.items():
                if element not in element_detection_counts:
                    element_detection_counts[element] = {}

                for isotope in isotopes:
                    element_count += 1
                    peaks = detected_peaks.get((element, isotope), [])
                    peak_count = len(peaks)
                    total_particles += peak_count
                    element_detection_counts[element][isotope] = peak_count

                    isotope_widget = QWidget()
                    isotope_layout = QHBoxLayout(isotope_widget)

                    if peak_count < 5:
                        if peak_count == 0:
                            color = "gray"
                            status = "No Data"
                        else:
                            color = "lightblue"
                            status = f"Too Few ({peak_count})"

                        indicator = QLabel("●")
                        indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
                        isotope_layout.addWidget(indicator, 0, Qt.AlignLeft)

                        element_label = QLabel(f"{element}-{isotope:.3f}")
                        element_label.setStyleSheet("color: white; font-weight: bold;")
                        isotope_layout.addWidget(element_label, 1)

                        stats_text = f"{peak_count} particles | {status}"
                        stats_label = QLabel(stats_text)
                        stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 11px;")
                        isotope_layout.addWidget(stats_label, 0, Qt.AlignRight)
                    else:
                        valid_elements += 1
                        strong_peaks = sum(1 for p in peaks if p.get('SNR', 0) >= 1.5)
                        total_strong += strong_peaks

                        strong_percentage = (strong_peaks / peak_count * 100) if peak_count > 0 else 0
                        Suspected_percentage = 100 - strong_percentage

                        if Suspected_percentage >= 50:
                            color = "red"
                            status = "Poor"
                        elif Suspected_percentage >= 30:
                            color = "yellow"
                            status = "Warning"
                        else:
                            color = "lime"
                            status = "Good"

                        indicator = QLabel("●")
                        indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
                        isotope_layout.addWidget(indicator, 0, Qt.AlignLeft)

                        element_label = QLabel(f"{element}-{isotope:.3f}")
                        element_label.setStyleSheet("color: white; font-weight: bold;")
                        isotope_layout.addWidget(element_label, 1)

                        stats_text = f"{strong_peaks}/{peak_count} strong ({strong_percentage:.1f}%) | {status}"
                        stats_label = QLabel(stats_text)
                        stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 11px;")
                        isotope_layout.addWidget(stats_label, 0, Qt.AlignRight)

                    sample_layout.addWidget(isotope_widget)

            if valid_elements > 0:
                overall_widget = QWidget()
                overall_layout = QVBoxLayout(overall_widget)

                overall_title = QLabel("Overall Statistics (5+ particles only)")
                overall_title.setStyleSheet(
                    "font-size: 14px; font-weight: bold; color: white; margin-top: 10px;")
                overall_layout.addWidget(overall_title)

                overall_strong_pct = (total_strong / total_particles * 100) if total_particles > 0 else 0
                overall_Suspected_pct = 100 - overall_strong_pct

                stats_text = (f"Total peaks: {total_particles} | "
                              f"Strong Signals: {overall_strong_pct:.1f}% | "
                              f"Valid Elements: {valid_elements}/{element_count}")
                overall_stats = QLabel(stats_text)
                overall_stats.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 12px;")
                overall_layout.addWidget(overall_stats)

                if overall_Suspected_pct <= 10:
                    quality_text = "Quality: Excellent"
                    quality_color = "lime"
                elif overall_Suspected_pct <= 30:
                    quality_text = "Quality: Good"
                    quality_color = "lightgreen"
                elif overall_Suspected_pct <= 50:
                    quality_text = "Quality: Fair"
                    quality_color = "yellow"
                else:
                    quality_text = "Quality: Needs Attention"
                    quality_color = "red"

                quality_label = QLabel(quality_text)
                quality_label.setStyleSheet(
                    f"color: {quality_color}; font-size: 12px; font-weight: bold;")
                overall_layout.addWidget(quality_label)

                overall_widget.setStyleSheet("""
                    QWidget {
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 8px;
                        padding: 8px;
                        margin-top: 5px;
                    }
                """)
                sample_layout.addWidget(overall_widget)

            if periodic_table_widget is not None:
                all_anomalies = []
                for element, iso_counts in element_detection_counts.items():
                    if len(iso_counts) < 2:
                        continue
                    element_data = periodic_table_widget.get_element_by_symbol(element)
                    if element_data is None:
                        continue
                    anomalies = detect_isotope_anomalies(
                        element, iso_counts, element_data
                    )
                    all_anomalies.extend(anomalies)

                if all_anomalies:
                    anomaly_widget = QWidget()
                    anomaly_layout = QVBoxLayout(anomaly_widget)

                    severity_order = {'critical': 0, 'warning': 1, 'info': 2}
                    all_anomalies.sort(key=lambda a: severity_order.get(a['severity'], 3))

                    n_critical = sum(1 for a in all_anomalies if a['severity'] == 'critical')
                    n_warning  = sum(1 for a in all_anomalies if a['severity'] == 'warning')
                    n_info     = sum(1 for a in all_anomalies if a['severity'] == 'info')

                    title_parts = []
                    if n_critical:
                        title_parts.append(f"{n_critical} critical")
                    if n_warning:
                        title_parts.append(f"{n_warning} warning")
                    if n_info:
                        title_parts.append(f"{n_info} info")

                    anomaly_title = QLabel(
                        f"Isotope Consistency ({', '.join(title_parts)})")
                    anomaly_title.setStyleSheet(
                        "font-size: 14px; font-weight: bold; color: white; margin-top: 10px;")
                    anomaly_layout.addWidget(anomaly_title)

                    severity_colors = {
                        'critical': '#FF4444',
                        'warning': '#78631f',
                        'info': 'rgba(255, 255, 255, 0.7)'
                    }
                    severity_icons = {
                        'critical': '⚠',
                        'warning': '⚡',
                        'info': 'ℹ'
                    }

                    for anomaly in all_anomalies[:10]:
                        icon = severity_icons.get(anomaly['severity'], '•')
                        anom_label = QLabel(f"{icon} {anomaly['details']}")
                        anom_color = severity_colors.get(anomaly['severity'], 'white')
                        anom_label.setStyleSheet(f"color: {anom_color}; font-size: 11px;")
                        anom_label.setWordWrap(True)
                        anomaly_layout.addWidget(anom_label)

                    if len(all_anomalies) > 10:
                        more_label = QLabel(f"... and {len(all_anomalies) - 10} more")
                        more_label.setStyleSheet(
                            "color: rgba(255, 255, 255, 0.6); font-size: 10px;")
                        anomaly_layout.addWidget(more_label)

                    anomaly_widget.setStyleSheet("""
                        QWidget {
                            background: rgba(255, 255, 255, 0.05);
                            border-radius: 8px;
                            padding: 8px;
                            margin-top: 5px;
                        }
                    """)
                    sample_layout.addWidget(anomaly_widget)

        sample_box.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        self.sample_layout.addWidget(sample_box)

        if multi_element_particles is not None:
            multi_box = QWidget()
            multi_layout = QVBoxLayout(multi_box)

            multi_title = QLabel("Multi-element Particles")
            multi_count = QLabel(str(len(multi_element_particles)))
            multi_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
            multi_count.setStyleSheet("font-size: 24px; color: white; margin-top: 5px;")

            multi_layout.addWidget(multi_title)
            multi_layout.addWidget(multi_count)

            if len(multi_element_particles) > 0:
                complexity_text = (
                    f"Sample Complexity: "
                    f"{'High' if len(multi_element_particles) > 100 else 'Medium' if len(multi_element_particles) > 20 else 'Low'}")
                complexity_label = QLabel(complexity_text)
                complexity_label.setStyleSheet(
                    "font-size: 11px; color: rgba(255, 255, 255, 0.8);")
                multi_layout.addWidget(complexity_label)

            multi_box.setStyleSheet("""
                QWidget {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 10px;
                    padding: 15px;
                }
            """)
            self.sample_layout.addWidget(multi_box)