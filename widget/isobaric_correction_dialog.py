"""
Isobaric Correction dialog.

Shows every isobaric overlap among the currently selected isotopes, lets the
user preview the IN (raw) vs OUT (corrected) signal for each one with the exact
equation, and applies the correction only when the user commits. Apply makes
the corrected signal the working data; Revert puts the raw signal back.

It owns no correction logic — it calls the MainWindow methods you already have
(compute_isobaric_corrections / apply_isobaric_correction /
revert_isobaric_correction) and the engine for the preview math. Place this in
your widget/ package (e.g. widget/isobaric_correction_dialog.py) and open it
from a button/menu via:

    from widget.isobaric_correction_dialog import IsobaricCorrectionDialog
    IsobaricCorrectionDialog(self).exec()
"""

import copy

import numpy as np
import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QSplitter, QWidget, QComboBox,
    QAbstractItemView, QMessageBox, QDoubleSpinBox, QButtonGroup, QRadioButton,
)

import isobaric_correction as isobaric

try:
    from tools.theme import theme as _theme
except Exception:
    _theme = None


def _plot_colors():
    """Return (background, foreground, raw_pen, corrected_pen) colours for the preview plot.

    Raw signal is drawn in red, corrected signal in blue. Both colours are
    applied regardless of the active theme so the IN/OUT traces are always
    easy to distinguish.
    """
    if _theme is not None:
        p = _theme.palette
        return p.plot_bg, p.plot_fg, (220, 50, 50), (50, 120, 220)
    return 'w', 'k', (220, 50, 50), (50, 120, 220)


class IsobaricCorrectionDialog(QDialog):
    def __init__(self, main_window, parent=None):
        """Initialise the dialog and load corrections for the current selection.

        Args:
            main_window: The application MainWindow instance. Used to access
                selected_isotopes, data_by_sample, periodic_table_widget, and
                the correction apply/revert methods.
            parent: Optional parent widget; defaults to main_window.
        """
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("Isobaric Correction")
        self.setMinimumSize(960, 580)

        self._corrections = []            
        self._table_corrections = []      
        self._abundance_corrections = []  
        self._custom_factors: dict = {}   
        self._build_ui()
        self._load_corrections()
        self._update_button_states()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build and lay out all widgets in the dialog.

        Creates the intro label, sample selector, source toggle, left correction
        table, right preview plot, base-equation label, custom-R spinbox,
        active-equation label, and the Apply / Revert / Close button row.
        """
        root = QVBoxLayout(self)

        intro = QLabel(
            "Overlaps found among your selected isotopes are listed below. "
            "Select one to preview the signal before and after correction. "
            "Nothing changes until you click <b>Apply</b>."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Sample selector
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Preview sample:"))
        self.sample_combo = QComboBox()
        samples = list(getattr(self.mw, 'data_by_sample', {}).keys())
        self.sample_combo.addItems(samples)
        cur = getattr(self.mw, 'current_sample', None)
        if cur in samples:
            self.sample_combo.setCurrentText(cur)
        self.sample_combo.currentTextChanged.connect(self._on_row_selected)
        sample_row.addWidget(self.sample_combo)
        sample_row.addStretch()
        root.addLayout(sample_row)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Correction source:"))
        self._src_group = QButtonGroup(self)
        self._radio_table = QRadioButton("Reference table (recommended)")
        self._radio_abund = QRadioButton("Abundance ratio")
        self._radio_table.setChecked(True)
        self._src_group.addButton(self._radio_table, 0)
        self._src_group.addButton(self._radio_abund, 1)
        self._radio_table.toggled.connect(self._on_source_toggled)
        src_row.addWidget(self._radio_table)
        src_row.addWidget(self._radio_abund)
        src_row.addStretch()
        root.addLayout(src_row)

        splitter = QSplitter(Qt.Horizontal)

        # Left: corrections table (6 columns)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Analyte", "Interferent", "Monitor", "Factor R", "Source", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.setMinimumWidth(440)
        splitter.addWidget(self.table)

        right = QWidget()
        right_l = QVBoxLayout(right)
        bg, fg, _, _ = _plot_colors()
        self.plot = pg.PlotWidget()
        self.plot.setBackground(bg)
        self.plot.setLabel('left', 'Counts')
        self.plot.setLabel('bottom', 'Time (s)')
        self.plot.addLegend(offset=(10, 10))
        right_l.addWidget(self.plot, stretch=1)

        self.base_equation_label = QLabel("")
        self.base_equation_label.setWordWrap(True)
        self.base_equation_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.base_equation_label.setStyleSheet(
            "font-family: monospace; padding: 4px 6px; color: gray;")
        right_l.addWidget(self.base_equation_label)

        factor_row = QHBoxLayout()
        factor_row.addWidget(QLabel("Custom R:"))
        self.factor_spinbox = QDoubleSpinBox()
        self.factor_spinbox.setDecimals(6)
        self.factor_spinbox.setRange(0.0, 1000.0)
        self.factor_spinbox.setSingleStep(0.0001)
        self.factor_spinbox.setEnabled(False)
        self.factor_spinbox.setToolTip(
            "Override the correction factor R for this overlap. "
            "The base value is always preserved above.")
        self.factor_spinbox.valueChanged.connect(self._on_factor_changed)
        factor_row.addWidget(self.factor_spinbox)
        self.reset_factor_btn = QPushButton("Reset to base")
        self.reset_factor_btn.setEnabled(False)
        self.reset_factor_btn.setToolTip("Restore the auto-calculated R value.")
        self.reset_factor_btn.clicked.connect(self._on_reset_factor)
        factor_row.addWidget(self.reset_factor_btn)
        factor_row.addStretch()
        right_l.addLayout(factor_row)

        self.equation_label = QLabel("")
        self.equation_label.setWordWrap(True)
        self.equation_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.equation_label.setStyleSheet("font-family: monospace; padding: 4px 6px;")
        right_l.addWidget(self.equation_label)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        btn_row = QHBoxLayout()
        self.status_label = QLabel("")
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._on_apply)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.clicked.connect(self._on_revert)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.revert_btn)
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Correction loading
    # ------------------------------------------------------------------

    def _load_corrections(self):
        """Compute both table-sourced and abundance-ratio corrections, then populate the table.

        Builds two independent correction lists:
          - _table_corrections: from the empirical reference table (recommended)
          - _abundance_corrections: from natural-abundance ratios (fallback)

        The active list (_corrections) is whichever source the radio button
        selects. The monitor pool for both is all measured data channels so
        corrections are enabled without the user having to manually select
        monitor isotopes.
        """
        selected = getattr(self.mw, 'selected_isotopes', {})
        ptw = getattr(self.mw, 'periodic_table_widget', None)
        all_channels = sorted({
            m
            for sd in getattr(self.mw, 'data_by_sample', {}).values()
            for m in sd.keys()
        })

        try:
            self._table_corrections = isobaric.build_table_corrections(
                selected,
                available_masses=all_channels or None,
            )
        except Exception as e:
            self._table_corrections = []
            QMessageBox.warning(self, "Isobaric Correction",
                                f"Could not load table corrections:\n{e}")

        try:
            if ptw and selected:
                self._abundance_corrections = isobaric.build_all_corrections(
                    selected,
                    ptw.get_element_by_symbol,
                    ptw.get_elements,
                    monitor_pool=all_channels or None,
                )
            else:
                self._abundance_corrections = []
        except Exception as e:
            self._abundance_corrections = []
            QMessageBox.warning(self, "Isobaric Correction",
                                f"Could not compute abundance corrections:\n{e}")

        use_table = bool(self._table_corrections)
        self._radio_table.blockSignals(True)
        self._radio_abund.blockSignals(True)
        self._radio_table.setChecked(use_table)
        self._radio_abund.setChecked(not use_table)
        self._radio_table.blockSignals(False)
        self._radio_abund.blockSignals(False)

        self._corrections = self._table_corrections if use_table else self._abundance_corrections
        self._populate_table()

    def _populate_table(self):
        """Fill the correction table widget from the current _corrections list."""
        self._custom_factors.clear()
        self.table.setRowCount(len(self._corrections))
        for r, c in enumerate(self._corrections):
            source_tag = "Table" if c.source == "table" else "~ab ratio"
            status = "✓ Ready" if c.enabled else (c.note or "⚠ Monitor not in selection")
            cells = [c.analyte_label, c.interferent_symbol, c.monitor_label,
                     f"{c.factor:.6f}", source_tag, status]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setForeground(Qt.gray if not c.enabled else Qt.black)
                self.table.setItem(r, col, item)

        if not self._corrections:
            self.equation_label.setText("No isobaric overlaps among the selected isotopes.")
            self.base_equation_label.setText("")
        elif self.table.rowCount():
            self.table.selectRow(0)

    def _on_source_toggled(self, checked: bool):
        """Switch the active correction list between table and abundance-ratio source.

        Called when either radio button changes. Resets custom factor overrides
        and repopulates the table from the newly selected source.

        Args:
            checked: True when the table radio button is selected (ignored;
                     the active button is read directly from the button group).
        """
        if self._radio_table.isChecked():
            self._corrections = self._table_corrections
        else:
            self._corrections = self._abundance_corrections
        self._populate_table()
        self._update_button_states()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _raw_base_for(self, sample):
        """Return channel data with any previously applied corrections restored to raw.

        The preview is always true-raw vs true-corrected so it never
        double-subtracts on top of an already-applied correction.

        Args:
            sample: Sample name key in data_by_sample.

        Returns:
            Dict mapping mass keys to signal arrays.
        """
        sample_data = getattr(self.mw, 'data_by_sample', {}).get(sample, {})
        base = dict(sample_data)
        backup = getattr(self.mw, '_isobaric_raw_backup', {}).get(sample, {})
        for akey, raw in backup.items():
            base[akey] = raw
        return base

    def _enabled_corrections(self):
        """Return only the corrections that are currently enabled (monitor present)."""
        return [c for c in self._corrections if getattr(c, 'enabled', False)]

    def _effective_corrections(self):
        """Return enabled corrections with any user-overridden R factors applied.

        Copies corrections that have a custom factor stored in _custom_factors
        so the originals are never mutated. Used for both the preview plot and
        the Apply step.
        """
        result = []
        for i, c in enumerate(self._corrections):
            if not getattr(c, 'enabled', False):
                continue
            if i in self._custom_factors:
                c = copy.copy(c)
                c.factor = self._custom_factors[i]
            result.append(c)
        return result

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_factor_changed(self, value: float):
        """Handle a change to the Custom R spinbox.

        Stores the override in _custom_factors (or removes it when the value
        matches the base factor), enables the Reset button, and refreshes the
        preview plot and active equation label without reloading the whole row.

        Args:
            value: New R factor value entered by the user.
        """
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        row_idx = rows[0].row()
        corr = self._corrections[row_idx]
        if abs(value - corr.factor) < 1e-9:
            self._custom_factors.pop(row_idx, None)
        else:
            self._custom_factors[row_idx] = value
        self.reset_factor_btn.setEnabled(row_idx in self._custom_factors)
        self._refresh_equation_and_preview(row_idx)

    def _on_reset_factor(self):
        """Restore the auto-calculated R factor for the selected correction.

        Removes the custom override from _custom_factors, resets the spinbox
        to the base value without triggering _on_factor_changed, disables the
        Reset button, and refreshes the preview.
        """
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        row_idx = rows[0].row()
        self._custom_factors.pop(row_idx, None)
        corr = self._corrections[row_idx]
        self.factor_spinbox.blockSignals(True)
        self.factor_spinbox.setValue(corr.factor)
        self.factor_spinbox.blockSignals(False)
        self.reset_factor_btn.setEnabled(False)
        self._refresh_equation_and_preview(row_idx)

    def _refresh_equation_and_preview(self, row_idx: int):
        """Re-draw plot and update active equation label for the given row.

        Args:
            row_idx: Index into _corrections for the row being refreshed.
        """
        corr = self._corrections[row_idx]
        custom_r = self._custom_factors.get(row_idx, corr.factor)

        sample = self.sample_combo.currentText() or getattr(self.mw, 'current_sample', None)
        if not sample or not corr.enabled:
            return

        base = self._raw_base_for(sample)
        akey = self.mw.find_closest_isotope(corr.analyte_mass)
        if akey is None or akey not in base:
            return

        self.plot.clear()
        time = getattr(self.mw, 'time_array_by_sample', {}).get(sample)
        if time is None:
            time = getattr(self.mw, 'time_array', None)
        raw = np.asarray(base[akey], dtype=float)
        x = np.asarray(time, dtype=float) if time is not None else np.arange(raw.size)
        _, _, raw_pen, corr_pen = _plot_colors()
        self.plot.plot(x, raw, pen=pg.mkPen(raw_pen, width=1), name="IN (raw)")

        effective = self._effective_corrections()
        corrected_map = isobaric.correct_sample_channels(
            base, effective, self.mw.find_closest_isotope)
        corrected = corrected_map.get(akey)
        if corrected is not None:
            self.plot.plot(x, np.asarray(corrected, dtype=float),
                           pen=pg.mkPen(corr_pen, width=1), name="OUT (corrected)")

        active = copy.copy(corr)
        active.factor = custom_r
        self.equation_label.setText(active.equation_text())
        self.plot.enableAutoRange()

    def _on_row_selected(self):
        """Update the preview plot and equation labels when a table row is selected.

        Populates the base-equation label (always the source formula),
        sets the Custom R spinbox to the stored override or the base factor,
        then plots the raw (red) vs corrected (blue) signal for the selected
        analyte channel in the current preview sample.
        """
        self.plot.clear()
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        row_idx = rows[0].row()
        corr = self._corrections[row_idx]

        self.base_equation_label.setText("Base: " + corr.equation_text())

        self.factor_spinbox.blockSignals(True)
        self.factor_spinbox.setValue(self._custom_factors.get(row_idx, corr.factor))
        self.factor_spinbox.setEnabled(corr.enabled)
        self.factor_spinbox.blockSignals(False)
        self.reset_factor_btn.setEnabled(row_idx in self._custom_factors)

        sample = self.sample_combo.currentText() or getattr(self.mw, 'current_sample', None)
        if not sample:
            self.equation_label.setText("No sample loaded to preview.")
            return

        base = self._raw_base_for(sample)
        akey = self.mw.find_closest_isotope(corr.analyte_mass)
        if akey is None or akey not in base:
            self.equation_label.setText(
                f"Analyte channel for {corr.analyte_label} not present in this sample.")
            return

        time = getattr(self.mw, 'time_array_by_sample', {}).get(sample)
        if time is None:
            time = getattr(self.mw, 'time_array', None)
        raw = np.asarray(base[akey], dtype=float)
        x = np.asarray(time, dtype=float) if time is not None else np.arange(raw.size)

        _, _, raw_pen, corr_pen = _plot_colors()
        self.plot.plot(x, raw, pen=pg.mkPen(raw_pen, width=1), name="IN (raw)")

        if corr.enabled:
            effective = self._effective_corrections()
            corrected_map = isobaric.correct_sample_channels(
                base, effective, self.mw.find_closest_isotope)
            corrected = corrected_map.get(akey)
            if corrected is not None:
                self.plot.plot(x, np.asarray(corrected, dtype=float),
                               pen=pg.mkPen(corr_pen, width=1), name="OUT (corrected)")
            eqs = [c.equation_text() for c in effective
                   if c.enabled and self.mw.find_closest_isotope(c.analyte_mass) == akey]
            self.equation_label.setText("\n".join(eqs))
        else:
            note = corr.note or (
                f"⚠ Monitor not in selection — "
                f"add {corr.monitor_label} to your isotope selection "
                f"to enable this correction.")
            self.equation_label.setText(note)
        self.plot.enableAutoRange()

    def _on_apply(self):
        """Apply all enabled corrections (with any custom R overrides) to the working data.

        If a correction has already been applied it is reverted first to avoid
        double-subtraction. Passes the effective corrections (custom R values
        included) to MainWindow.apply_isobaric_correction so every sample is
        updated consistently. Falls back to the no-argument call if the main
        window does not yet accept the corrections kwarg.
        """
        if getattr(self.mw, 'isobaric_applied', False):
            self.mw.revert_isobaric_correction()
        try:
            effective = self._effective_corrections()
            changed = self.mw.apply_isobaric_correction(corrections=effective)
        except TypeError:
            changed = self.mw.apply_isobaric_correction()
        except Exception as e:
            QMessageBox.critical(self, "Isobaric Correction", f"Apply failed:\n{e}")
            return
        self.status_label.setText(
            f"Applied — {changed} channel(s) corrected." if changed
            else "Nothing to apply (no enabled corrections).")
        self._refresh_main_plot()
        self._on_row_selected()
        self._update_button_states()

    def _on_revert(self):
        """Revert all applied corrections and restore the original raw signal.

        Delegates to MainWindow.revert_isobaric_correction, then refreshes
        the main plot and the preview so the user sees the raw data again.
        """
        try:
            self.mw.revert_isobaric_correction()
        except Exception as e:
            QMessageBox.critical(self, "Isobaric Correction", f"Revert failed:\n{e}")
            return
        self.status_label.setText("Reverted — raw signal restored.")
        self._refresh_main_plot()
        self._on_row_selected()
        self._update_button_states()

    def _update_button_states(self):
        """Sync the Apply / Revert button enabled states with the current correction status.

        Apply is enabled when at least one correction is ready; Revert is
        enabled only when a correction has already been applied. Also sets a
        default status message when no explicit action message is present.
        """
        applied = bool(getattr(self.mw, 'isobaric_applied', False))
        has_enabled = bool(self._enabled_corrections())
        self.apply_btn.setEnabled(has_enabled)
        self.revert_btn.setEnabled(applied)
        if not self.status_label.text():
            self.status_label.setText(
                "Applied." if applied else
                ("Ready to apply." if has_enabled else "No correctable overlaps."))

    def _refresh_main_plot(self):
        """Redraw the main window's current trace so the applied correction is visible."""
        try:
            row = self.mw.parameters_table.currentRow()
            if row is not None and row >= 0:
                self.mw.parameters_table_clicked(row, 0)
        except Exception:
            pass
