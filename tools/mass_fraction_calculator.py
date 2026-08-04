"""Mass-fraction calculator dialog composed from focused widgets."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from tools.mass_fraction_calculator_widgets import (
    CalculationActionsWidget, DialogActionsWidget, MassFractionTableWidget,
    SampleSelectionWidget,
)
from tools.mass_fraction_table_model import MassFractionTableModel
from tools.mass_fraction_utils import CSVCompoundDatabase
from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo
from tools.theme import theme

_itk_log = logging.getLogger("IsotopeTrack.tools.mass_fraction_calculator")


class MassFractionCalculator(QDialog):
    """Coordinates calculator widgets and commits their working state on Apply."""

    mass_fractions_updated = Signal(dict)

    def __init__(self,
                 selected_isotopes: dict,
                 periodic_table_info: PeriodicTableInfo,
                 compound_db: CSVCompoundDatabase,
                 /,
                 parent: QWidget | Any = None, ):
        super().__init__(parent)
        self.parent_window = parent
        self.compound_db = compound_db
        self.setWindowTitle("Mass Fraction Calculator")
        self.setMinimumSize(1100, 550)
        self.resize(1500, 700)

        sample_names = list(getattr(parent, "sample_to_folder_map", {}).keys())
        self.model = MassFractionTableModel(selected_isotopes, periodic_table_info, self)
        self.sample_selector = SampleSelectionWidget(sample_names, self)
        self.table_widget = MassFractionTableWidget(self.model, compound_db, self)
        self.calculation_actions = CalculationActionsWidget(self)
        self.dialog_actions = DialogActionsWidget(self)
        self._setup_ui()
        self._connect_signals()
        self._restore_previous_state()
        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addLayout(self._build_header())
        right_layout.addWidget(self.table_widget)

        action_row = QHBoxLayout()
        action_row.addWidget(self.calculation_actions)
        action_row.addWidget(self.dialog_actions)
        right_layout.addLayout(action_row)

        splitter.addWidget(self.sample_selector)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1200])
        main_layout.addWidget(splitter)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("Mass Fraction Calculator")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title)
        layout.addStretch()
        self.db_status_label = QLabel()
        layout.addWidget(self.db_status_label)
        self.load_button = QPushButton("Load CSV")
        self.load_button.clicked.connect(self._manual_load_csv)
        layout.addWidget(self.load_button)
        self._refresh_database_status()
        return layout

    def _connect_signals(self) -> None:
        self.calculation_actions.reset_requested.connect(self.model.reset_to_pure_elements)
        self.calculation_actions.calculate_requested.connect(self.model.recalculate_all)
        self.dialog_actions.apply_requested.connect(self._apply_mass_fractions)
        self.dialog_actions.cancel_requested.connect(self.reject)

    def _refresh_database_status(self) -> None:
        if self.compound_db.is_loaded:
            self.db_status_label.setText(f"database: {self.compound_db.row_count()}")
            self.load_button.hide()
        else:
            self.db_status_label.setText("database: Not found")
            self.load_button.show()
        palette = theme.palette
        color = palette.success if self.compound_db.is_loaded else palette.warning
        self.db_status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def _manual_load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv, *.csv.gz)")
        if path and self.compound_db.load_csv(path):
            self._refresh_database_status()
            QMessageBox.information(self, "Success", "Database loaded!")

    def _apply_mass_fractions(self) -> None:
        selected = self.sample_selector.selected_samples()
        apply_to_all = self.sample_selector.apply_to_all()
        if not apply_to_all and not selected:
            QMessageBox.warning(
                self, "No Samples Selected",
                "Please select at least one sample or choose 'Apply to all samples'.",
            )
            return
        self._save_state()
        payload = self.model.export_values()
        payload.update({
            "apply_to_all": apply_to_all,
            "selected_samples": selected if not apply_to_all else [],
        })
        self.mass_fractions_updated.emit(payload)
        self.accept()

    def _save_state(self) -> None:
        if not self.parent_window:
            return
        state = self.model.save_state()
        state.update({
            "selected_samples": self.sample_selector.selected_samples(),
            "apply_to_all": self.sample_selector.apply_to_all(),
        })
        self.parent_window._mass_fraction_calculator_state = state

    def _restore_previous_state(self) -> None:
        if not self.parent_window:
            return
        state = getattr(self.parent_window, "_mass_fraction_calculator_state", None)
        if state:
            self.model.restore_state(state)
            self.sample_selector.restore_state(state)

    def reject(self) -> None:
        """Cancel leaves MainWindow unchanged but retains this dialog's draft."""
        self._save_state()
        super().reject()

    def closeEvent(self, event) -> None:
        self._save_state()
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            _itk_log.debug("Theme signal already disconnected", exc_info=True)
        super().closeEvent(event)

    def apply_theme(self) -> None:
        self.setStyleSheet(self._build_stylesheet())
        self._refresh_database_status()
        palette = theme.palette
        self.dialog_actions.apply_button.setStyleSheet(f"""
            QPushButton {{ background-color: {palette.accent}; color: {palette.text_inverse};
                padding: 8px 16px; border-radius: 4px; border: none; font-weight: bold; min-width: 120px; }}
            QPushButton:hover {{ background-color: {palette.accent_hover}; }}
            QPushButton:pressed {{ background-color: {palette.accent_pressed}; }}
        """)

    @staticmethod
    def _build_stylesheet() -> str:
        p = theme.palette
        return f"""
            QDialog {{ background-color: {p.bg_primary}; color: {p.text_primary}; }}
            QWidget, QLabel, QCheckBox, QRadioButton {{ color: {p.text_primary}; }}
            QGroupBox {{ color: {p.text_primary}; border: 1px solid {p.border};
                border-radius: 6px; margin-top: 12px; padding-top: 10px; font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; padding: 0 8px; }}
            QListWidget, QTableView {{ background-color: {p.bg_secondary}; color: {p.text_primary}; border: 1px solid {p.border};
                border-radius: 4px; alternate-background-color: {p.bg_tertiary}; selection-background-color: {p.accent};
                selection-color: {p.text_inverse}; gridline-color: {p.border}; }}
            QListWidget {{ background-color: {p.bg_tertiary}; padding: 2px; outline: 0; }}
            QListWidget::item:hover {{ background-color: {p.bg_hover}; }}
            QTableView::item {{ padding: 4px; }}
            QHeaderView::section {{ background-color: {p.bg_tertiary}; color: {p.text_primary}; padding: 6px 8px;
                border: none; border-right: 1px solid {p.border}; border-bottom: 1px solid {p.border}; font-weight: 600; }}
            QLineEdit, QComboBox {{ background-color: {p.bg_tertiary}; color: {p.text_primary}; border: 1px solid {p.border};
                border-radius: 4px; padding: 4px 8px; selection-background-color: {p.accent}; selection-color: {p.text_inverse}; }}
            QPushButton {{ background-color: {p.bg_tertiary}; color: {p.text_primary}; border: 1px solid {p.border};
                border-radius: 4px; padding: 6px 14px; min-width: 80px; }}
            QPushButton:hover {{ background-color: {p.bg_hover}; border-color: {p.accent}; }}
            QPushButton:disabled {{ color: {p.text_muted}; background-color: {p.bg_secondary}; }}
            QSplitter::handle {{ background-color: {p.border}; width: 5px; }}
            QSplitter::handle:horizontal {{ width: 1px; }}
            QRadioButton, QCheckBox {{ background-color: transparent; }}
            QRadioButton::indicator {{ border-radius: 8px; }}
            QRadioButton::indicator:unchecked, QCheckBox::indicator:unchecked {{ border: 2px solid {p.border}; background-color: {p.bg_tertiary};}}
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {{ border: 2px solid {p.accent}; background-color: {p.accent}; }}
        """
