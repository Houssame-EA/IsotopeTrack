"""
Isobaric Correction dialog — calculator-style equation editor.

Overlaps come from the known interference list in
data/interference_corrections.json. Every analyte channel has one correction
equation. The default is the published table equation; the user can replace
it with any calculator-style expression:

    raw - 0.230074*Hg202 + 2*(Ar38/K39) - sqrt(Pt195)

'raw' is the analyte channel; Element+mass tokens (Hg202, Ar38, Cr54)
reference measured channels; + - * / ** parentheses and log, log10, sqrt,
exp, abs are supported. The result is always clamped at zero.

Custom equations persist in data/isobaric_overrides.json and are restored
next session. 'Reset to default' brings back the table equation. Analytes are
listed by atomic mass, lowest first. Open with:

    from widget.isobaric_correction_dialog import IsobaricCorrectionDialog
    IsobaricCorrectionDialog(self).exec()
"""

import numpy as np
import pyqtgraph as pg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QSplitter, QWidget, QComboBox,
    QAbstractItemView, QMessageBox, QLineEdit,
)

import tools.isobaric_correction as isobaric
import logging
_itk_log = logging.getLogger("IsotopeTrack.widget.isobaric_correction_dialog")

try:
    from tools.theme import theme as _theme
except Exception:
    _itk_log.exception("Handled exception in <module>")
    _theme = None


def _plot_colors():
    """Return (background, foreground, raw_pen, corrected_pen) colours for the preview plot.

    Raw signal is drawn in red, corrected signal in blue, regardless of the
    active theme, so the IN/OUT traces are always easy to distinguish.
    """
    if _theme is not None:
        p = _theme.palette
        return p.plot_bg, p.plot_fg, (220, 50, 50), (50, 120, 220)
    return 'w', 'k', (220, 50, 50), (50, 120, 220)


class IsobaricCorrectionDialog(QDialog):
    def __init__(self, main_window, parent=None):
        """Initialise the dialog and load equations for the current selection.

        Args:
            main_window: The application MainWindow instance. Used to access
                selected_isotopes, data_by_sample, periodic_table_widget, and
                the correction apply/revert methods.
            parent: Optional parent widget; defaults to main_window.
        """
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("Isobaric Correction")
        self.setMinimumSize(1000, 620)

        self._entries = []
        self._overrides = isobaric.load_overrides()
        self._all_channels: set = set()
        self._updating_editor = False
        self._build_ui()
        self._load_entries()
        self._update_button_states()

    def _build_ui(self):
        """Build and lay out all widgets in the dialog.

        Creates the intro label, sample selector, analyte table (left),
        preview plot + default equation + equation editor + validation label
        (right), and the Apply / Revert / Close button row.
        """
        root = QVBoxLayout(self)

        intro = QLabel(
            "Each analyte has one correction <b>equation</b>. The default is "
            "the reference-table equation; you can replace it with any "
            "calculator-style expression using <code>raw</code>, channel "
            "tokens like <code>Hg202</code>, numbers, + − × ÷, parentheses, "
            "and log / sqrt / exp / abs. The result is clamped at zero. "
            "Your custom equation is saved automatically. Nothing changes "
            "until you click <b>Apply</b>."
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

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Analyte", "Equation", "Source", "Status"])
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

        editor_row = QHBoxLayout()
        editor_row.addWidget(QLabel("Equation: corrected = max("))
        self.expr_edit = QLineEdit()
        self.expr_edit.setStyleSheet("font-family: monospace;")
        self.expr_edit.setToolTip(
            "Calculator-style expression. 'raw' is the analyte channel; "
            "Element+mass tokens like Hg202 reference measured channels. "
            "Allowed: numbers, + - * / ** ( ) and log, log10, sqrt, exp, abs.")
        self.expr_edit.textChanged.connect(self._on_expression_changed)
        editor_row.addWidget(self.expr_edit, stretch=1)
        editor_row.addWidget(QLabel(", 0 )"))
        self.reset_btn = QPushButton("Reset to default")
        self.reset_btn.setToolTip(
            "Restore the reference-table equation for this analyte.")
        self.reset_btn.clicked.connect(self._on_reset_analyte)
        editor_row.addWidget(self.reset_btn)
        right_l.addLayout(editor_row)

        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 2px 6px;")
        right_l.addWidget(self.validation_label)

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

    def reload(self):
        """Refresh the dialog for reuse without recreating it.

        Called by MainWindow when the persistent dialog instance is reopened.
        Reloads the persisted overrides, rebuilds the sample selector from the
        currently loaded samples, and repopulates the equations for the
        current isotope selection. The dialog is kept alive between opens
        because destroying it crashes in the pyqtgraph/PySide6 teardown.
        """
        self._overrides = isobaric.load_overrides()
        self.sample_combo.blockSignals(True)
        self.sample_combo.clear()
        samples = list(getattr(self.mw, 'data_by_sample', {}).keys())
        self.sample_combo.addItems(samples)
        cur = getattr(self.mw, 'current_sample', None)
        if cur in samples:
            self.sample_combo.setCurrentText(cur)
        self.sample_combo.blockSignals(False)
        self.status_label.setText("")
        self._load_entries()
        self._update_button_states()

    def _load_entries(self):
        """Build one equation entry per selected analyte, sorted by mass.

        Each entry holds the analyte identity, its pristine table equation,
        and the active expression (the saved custom one when present,
        otherwise the table default). The measured channel pool is collected
        from every loaded sample for validation.
        """
        selected = getattr(self.mw, 'selected_isotopes', {})
        all_channels = sorted({
            m
            for sd in getattr(self.mw, 'data_by_sample', {}).values()
            for m in sd.keys()
        })
        self._all_channels = {isobaric._nominal(m) for m in all_channels}

        pairs = sorted(
            ((symbol, mass)
             for symbol, masses in selected.items()
             for mass in masses),
            key=lambda p: p[1])

        self._entries = []
        for symbol, mass in pairs:
            defaults = isobaric.default_table_terms(symbol, mass)
            if not defaults:
                continue
            label = defaults[0].analyte_label
            default_expr = isobaric.expression_from_terms(defaults)
            ov = self._overrides.get(f"eq::{label}") or {}
            expr = ov.get('expr')
            if not expr and isinstance(ov.get('terms'), list):
                legacy = [isobaric.term_from_dict(symbol, mass, label, d)
                          for d in ov['terms']]
                expr = isobaric.expression_from_terms(legacy)
            entry = {
                'symbol': symbol,
                'mass': mass,
                'label': label,
                'default_expr': default_expr,
                'expr': expr or default_expr,
            }
            self._validate_entry(entry)
            self._entries.append(entry)

        self._populate_table()

    def _validate_entry(self, entry: dict):
        """Validate an entry's expression and store enabled/note on it.

        Args:
            entry: The analyte entry dict to validate in place.
        """
        ok, msg, _ = isobaric.validate_expression(
            entry['expr'], self._all_channels or None)
        entry['enabled'] = ok
        entry['note'] = "" if ok else f"⚠ {msg}"

    def _is_custom(self, entry: dict) -> bool:
        """True when the entry's expression differs from the table default."""
        return entry['expr'].strip() != entry['default_expr'].strip()

    def _populate_table(self, select_row: int = 0):
        """Fill the analyte table from the current entries.

        Args:
            select_row: Row to select after populating (clamped to range).
        """
        self.table.setRowCount(len(self._entries))
        for r in range(len(self._entries)):
            self._update_row(r)

        if not self._entries:
            self.equation_label.setText(
                "No isobaric overlaps among the selected isotopes.")
            self.base_equation_label.setText("")
        elif self.table.rowCount():
            self.table.selectRow(min(select_row, self.table.rowCount() - 1))

    def _update_row(self, r: int):
        """Refresh one table row from its entry after edits.

        Args:
            r: Row index into the entries list.
        """
        e = self._entries[r]
        source_tag = "Custom" if self._is_custom(e) else "Table"
        status = "✓ Ready" if e['enabled'] else (e['note'] or "⚠ Invalid")
        cells = [e['label'], e['expr'], source_tag, status]
        for col, text in enumerate(cells):
            item = QTableWidgetItem(str(text))
            item.setForeground(Qt.gray if not e['enabled'] else Qt.black)
            self.table.setItem(r, col, item)

    def _persist_entry(self, entry: dict):
        """Save (or clear) the custom equation for one analyte to disk.

        The override is removed when the expression matches the table
        default, so 'Table' status returns automatically.

        Args:
            entry: The analyte entry whose expression to persist.
        """
        key = f"eq::{entry['label']}"
        if self._is_custom(entry):
            self._overrides[key] = {'expr': entry['expr']}
        else:
            self._overrides.pop(key, None)
        try:
            isobaric.save_overrides(self._overrides)
        except Exception:
            _itk_log.exception("Handled exception in _persist_entry")
            pass

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

    def _corrections_for(self, entries):
        """Build engine correction objects for the given entries.

        Args:
            entries: Iterable of analyte entry dicts.

        Returns:
            List of enabled correction objects (EquationCorrection for custom
            expressions, table term objects otherwise).
        """
        out = []
        for e in entries:
            if not e['enabled']:
                continue
            if self._is_custom(e):
                out.append(isobaric.EquationCorrection(
                    analyte_symbol=e['symbol'],
                    analyte_mass=e['mass'],
                    analyte_label=e['label'],
                    expression=e['expr'],
                ))
            else:
                for t in isobaric.default_table_terms(e['symbol'], e['mass']):
                    t.enabled = (isobaric._nominal(t.monitor_mass)
                                 in self._all_channels and t.factor > 0.0)
                    if t.enabled:
                        out.append(t)
        return out

    def _effective_corrections(self):
        """Return enabled correction objects for every analyte entry."""
        return self._corrections_for(self._entries)

    def _selected_row(self):
        """Index of the selected table row, or None."""
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else None

    def _on_expression_changed(self, text: str):
        """Validate, store, and persist the edited expression live.

        Invalid expressions show an error and are not persisted; the last
        valid equation stays active until the text becomes valid again.

        Args:
            text: Current contents of the equation line edit.
        """
        if self._updating_editor:
            return
        row_idx = self._selected_row()
        if row_idx is None:
            return
        entry = self._entries[row_idx]

        ok, msg, nominals = isobaric.validate_expression(
            text, self._all_channels or None)
        if ok:
            entry['expr'] = text.strip()
            entry['enabled'] = True
            entry['note'] = ""
            self._persist_entry(entry)
            used = ", ".join(f"m/z {n}" for n in nominals) or "none"
            self.validation_label.setStyleSheet("color: green; padding: 2px 6px;")
            self.validation_label.setText(f"✓ valid — channels used: {used}")
            self._update_row(row_idx)
            self._refresh_equations(entry)
            self._refresh_preview(entry)
        else:
            self.validation_label.setStyleSheet("color: red; padding: 2px 6px;")
            self.validation_label.setText(f"✗ {msg}")
        self._update_button_states()

    def _on_reset_analyte(self):
        """Restore the reference-table equation for the selected analyte."""
        row_idx = self._selected_row()
        if row_idx is None:
            return
        entry = self._entries[row_idx]
        entry['expr'] = entry['default_expr']
        self._validate_entry(entry)
        self._persist_entry(entry)
        self._updating_editor = True
        self.expr_edit.setText(entry['expr'])
        self._updating_editor = False
        self.validation_label.setText("")
        self._update_row(row_idx)
        self._refresh_equations(entry)
        self._refresh_preview(entry)
        self._update_button_states()

    def _refresh_equations(self, entry: dict):
        """Update the default and active equation labels for an entry.

        Args:
            entry: The analyte entry being shown.
        """
        self.base_equation_label.setText(
            f"Default: corrected({entry['label']}) = "
            f"max( {entry['default_expr']}, 0 )")
        active = (f"corrected({entry['label']}) = max( {entry['expr']}, 0 )")
        if entry['note']:
            active += "\n" + entry['note']
        self.equation_label.setText(active)

    def _refresh_preview(self, entry: dict):
        """Re-draw the IN/OUT preview plot for an entry's analyte channel.

        Args:
            entry: The analyte entry being previewed.
        """
        self.plot.clear()
        sample = self.sample_combo.currentText() or getattr(self.mw, 'current_sample', None)
        if not sample:
            return
        base = self._raw_base_for(sample)
        akey = self.mw.find_closest_isotope(entry['mass'])
        if akey is None or akey not in base:
            return

        time = getattr(self.mw, 'time_array_by_sample', {}).get(sample)
        if time is None:
            time = getattr(self.mw, 'time_array', None)
        raw = np.asarray(base[akey], dtype=float)
        x = np.asarray(time, dtype=float) if time is not None else np.arange(raw.size)
        _, _, raw_pen, corr_pen = _plot_colors()
        self.plot.plot(x, raw, pen=pg.mkPen(raw_pen, width=1), name="IN (raw)")

        corrections = self._corrections_for([entry])
        if corrections:
            corrected_map = isobaric.correct_sample_channels(
                base, corrections, self.mw.find_closest_isotope)
            corrected = corrected_map.get(akey)
            if corrected is not None:
                self.plot.plot(x, np.asarray(corrected, dtype=float),
                               pen=pg.mkPen(corr_pen, width=1), name="OUT (corrected)")
        self.plot.enableAutoRange()

    def _on_row_selected(self):
        """Load the editor, equations, and preview for the selected analyte."""
        row_idx = self._selected_row()
        if row_idx is None:
            self.plot.clear()
            return
        entry = self._entries[row_idx]
        self._updating_editor = True
        self.expr_edit.setText(entry['expr'])
        self._updating_editor = False
        if entry['enabled']:
            self.validation_label.setText("")
        else:
            self.validation_label.setStyleSheet("color: red; padding: 2px 6px;")
            self.validation_label.setText(entry['note'])
        self._refresh_equations(entry)
        self._refresh_preview(entry)

    def _on_apply(self):
        """Apply every enabled equation to the working data.

        If a correction has already been applied it is reverted first to
        avoid double-subtraction. Passes the effective corrections to
        MainWindow.apply_isobaric_correction so every sample is updated
        consistently. Falls back to the no-argument call if the main window
        does not yet accept the corrections kwarg.
        """
        if getattr(self.mw, 'isobaric_applied', False):
            self.mw.revert_isobaric_correction()
        try:
            effective = self._effective_corrections()
            changed = self.mw.apply_isobaric_correction(corrections=effective)
        except TypeError:
            _itk_log.exception("Handled exception in _on_apply")
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
        """Sync button enabled states with the current correction status.

        Apply is enabled when at least one equation is ready; Revert is
        enabled only when a correction has already been applied. Also sets a
        default status message when no explicit action message is present.
        """
        applied = bool(getattr(self.mw, 'isobaric_applied', False))
        has_enabled = any(e['enabled'] for e in self._entries)
        self.apply_btn.setEnabled(has_enabled)
        self.revert_btn.setEnabled(applied)
        self.reset_btn.setEnabled(bool(self._entries))
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
            _itk_log.exception("Handled exception in _refresh_main_plot")
            pass
