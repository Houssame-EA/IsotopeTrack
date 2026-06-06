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

import numpy as np
import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QSplitter, QWidget, QComboBox,
    QAbstractItemView, QMessageBox,
)

import isobaric_correction as isobaric

try:
    from tools.theme import theme as _theme
except Exception:
    _theme = None


def _plot_colors():
    """(background, foreground, raw_pen, corrected_pen) honouring the theme."""
    if _theme is not None:
        p = _theme.palette
        return p.plot_bg, p.plot_fg, (180, 180, 180), p.accent
    return 'w', 'k', (150, 150, 150), (220, 50, 50)


class IsobaricCorrectionDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("Isobaric Correction")
        self.setMinimumSize(900, 560)

        self._corrections = []         
        self._build_ui()
        self._load_corrections()
        self._update_button_states()

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            "Overlaps found among your selected isotopes are listed below. "
            "Select one to preview the signal before and after correction. "
            "Nothing changes until you click <b>Apply</b>."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

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

        splitter = QSplitter(Qt.Horizontal)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Analyte", "Interferent", "Monitor", "Factor R", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.setMinimumWidth(380)
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

        self.equation_label = QLabel("")
        self.equation_label.setWordWrap(True)
        self.equation_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.equation_label.setStyleSheet("font-family: monospace; padding: 6px;")
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


    def _load_corrections(self):
        try:
            self._corrections = self.mw.compute_isobaric_corrections()
        except Exception as e:
            self._corrections = []
            QMessageBox.warning(self, "Isobaric Correction",
                                f"Could not compute corrections:\n{e}")

        self.table.setRowCount(len(self._corrections))
        for r, c in enumerate(self._corrections):
            status = "Ready" if c.enabled else (c.note or "Monitor not measured")
            cells = [c.analyte_label, c.interferent_symbol, c.monitor_label,
                     f"{c.factor:.4f}", status]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                if not c.enabled:
                    item.setForeground(Qt.gray)
                self.table.setItem(r, col, item)

        if not self._corrections:
            self.equation_label.setText(
                "No isobaric overlaps among the selected isotopes.")
        elif self.table.rowCount():
            self.table.selectRow(0)


    def _raw_base_for(self, sample):
        """Current channels with any applied channels restored to raw, so the
        preview is always true-raw vs true-corrected and never double-subtracts.
        """
        sample_data = getattr(self.mw, 'data_by_sample', {}).get(sample, {})
        base = dict(sample_data)
        backup = getattr(self.mw, '_isobaric_raw_backup', {}).get(sample, {})
        for akey, raw in backup.items():
            base[akey] = raw
        return base

    def _enabled_corrections(self):
        return [c for c in self._corrections if getattr(c, 'enabled', False)]


    def _on_row_selected(self):
        self.plot.clear()
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        corr = self._corrections[rows[0].row()]

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
            corrected_map = isobaric.correct_sample_channels(
                base, self._enabled_corrections(), self.mw.find_closest_isotope)
            corrected = corrected_map.get(akey)
            if corrected is not None:
                self.plot.plot(x, np.asarray(corrected, dtype=float),
                               pen=pg.mkPen(corr_pen, width=1), name="OUT (corrected)")
            eqs = [c.equation_text() for c in self._enabled_corrections()
                   if self.mw.find_closest_isotope(c.analyte_mass) == akey]
            self.equation_label.setText("\n".join(eqs))
        else:
            self.equation_label.setText(
                f"{corr.note or 'Monitor not measured.'}\n"
                f"Select a clean {corr.interferent_symbol} isotope "
                f"({corr.monitor_label}) to enable this correction.")
        self.plot.enableAutoRange()

    def _on_apply(self):
        if getattr(self.mw, 'isobaric_applied', False):
            self.mw.revert_isobaric_correction()
        try:
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
        applied = bool(getattr(self.mw, 'isobaric_applied', False))
        has_enabled = bool(self._enabled_corrections())
        self.apply_btn.setEnabled(has_enabled)
        self.revert_btn.setEnabled(applied)
        if not self.status_label.text():
            self.status_label.setText(
                "Applied." if applied else
                ("Ready to apply." if has_enabled else "No correctable overlaps."))

    def _refresh_main_plot(self):
        """Redraw the main window's current trace so the change is visible."""
        try:
            row = self.mw.parameters_table.currentRow()
            if row is not None and row >= 0:
                self.mw.parameters_table_clicked(row, 0)
        except Exception:
            pass