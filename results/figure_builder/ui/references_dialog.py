"""Window for viewing and editing the reference values figures compare against.

Two tables: the upper-continental-crust abundances (built-in values from
Rudnick and Gao 2014, each of which can be overridden) and mineral formulas
(the built-in list plus the user's own). Changes are kept in the application
settings and used by every figure from then on.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from results.figure_builder.core import references as R


class ReferencesDialog(QDialog):
    """Edit upper-crust abundances and mineral formulas used by the figures."""

    def __init__(self, parent=None):
        """Build both tables from the built-in values and the user's own."""
        super().__init__(parent)
        self.setWindowTitle('Reference values')
        self.resize(560, 560)
        user = R.load_user()
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        crust_page = QWidget()
        cl = QVBoxLayout(crust_page)
        note = QLabel(f'Upper continental crust. Built-in values: {R.CRUST_SOURCE} '
                      'Type your own value in the right column to replace one; leave it empty '
                      'to use the built-in value.')
        note.setWordWrap(True)
        cl.addWidget(note)
        builtin = R.builtin_crust()
        self.crust_table = QTableWidget(len(builtin), 3)
        self.crust_table.setHorizontalHeaderLabels(['Element', 'Built-in (µg/g)', 'Your value (µg/g)'])
        self.crust_table.verticalHeader().setVisible(False)
        self.crust_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row, (el, frac) in enumerate(sorted(builtin.items(), key=lambda kv: R.ATOMIC_WEIGHTS[kv[0]])):
            for col, text in enumerate((el, f'{frac * 1e6:.4g}', str(user['crust'].get(el, '')))):
                item = QTableWidgetItem(text)
                if col < 2:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.crust_table.setItem(row, col, item)
        cl.addWidget(self.crust_table)
        tabs.addTab(crust_page, 'Upper crust')

        mineral_page = QWidget()
        ml = QVBoxLayout(mineral_page)
        mnote = QLabel('Ideal formulas used to place minerals on ternary diagrams. Real minerals '
                       'vary; add your own measured composition as a formula, e.g. '
                       'K0.6Al2.3Si3.4O10(OH)2.')
        mnote.setWordWrap(True)
        ml.addWidget(mnote)
        rows = {**R.MINERALS, **user['minerals']}
        self.mineral_table = QTableWidget(len(rows), 2)
        self.mineral_table.setHorizontalHeaderLabels(['Name', 'Formula'])
        self.mineral_table.verticalHeader().setVisible(False)
        self.mineral_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row, (name, formula) in enumerate(rows.items()):
            self.mineral_table.setItem(row, 0, QTableWidgetItem(name))
            self.mineral_table.setItem(row, 1, QTableWidgetItem(formula))
        ml.addWidget(self.mineral_table)
        bar = QHBoxLayout()
        add = QPushButton('+ Add mineral')
        add.clicked.connect(self._add_mineral)
        remove = QPushButton('Remove selected')
        remove.clicked.connect(self._remove_mineral)
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch()
        ml.addLayout(bar)
        tabs.addTab(mineral_page, 'Minerals')

        self.error = QLabel('')
        self.error.setStyleSheet('color: #b91c1c;')
        self.error.setWordWrap(True)
        root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel
                                   | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore)
        root.addWidget(buttons)

    def _add_mineral(self):
        """Append an empty mineral row and start editing its name."""
        row = self.mineral_table.rowCount()
        self.mineral_table.insertRow(row)
        self.mineral_table.setItem(row, 0, QTableWidgetItem(''))
        self.mineral_table.setItem(row, 1, QTableWidgetItem(''))
        self.mineral_table.editItem(self.mineral_table.item(row, 0))

    def _remove_mineral(self):
        """Remove the selected mineral rows."""
        for row in sorted({i.row() for i in self.mineral_table.selectedIndexes()}, reverse=True):
            self.mineral_table.removeRow(row)

    def _restore(self):
        """Clear every user value and show the built-in tables again."""
        for row in range(self.crust_table.rowCount()):
            self.crust_table.item(row, 2).setText('')
        self.mineral_table.setRowCount(len(R.MINERALS))
        for row, (name, formula) in enumerate(R.MINERALS.items()):
            self.mineral_table.setItem(row, 0, QTableWidgetItem(name))
            self.mineral_table.setItem(row, 1, QTableWidgetItem(formula))

    def values(self) -> dict:
        """The user's values as shown: changed crust abundances and minerals that differ.

        Raises:
            ValueError: When a value is not a positive number or a formula
                cannot be read.
        """
        crust = {}
        for row in range(self.crust_table.rowCount()):
            el = self.crust_table.item(row, 0).text()
            text = (self.crust_table.item(row, 2).text() or '').strip()
            if not text:
                continue
            try:
                value = float(text)
            except ValueError as exc:
                raise ValueError(f'{el}: "{text}" is not a number') from exc
            if value <= 0:
                raise ValueError(f'{el}: the value must be positive')
            crust[el] = value
        minerals = {}
        for row in range(self.mineral_table.rowCount()):
            name = (self.mineral_table.item(row, 0).text() if self.mineral_table.item(row, 0) else '').strip()
            formula = (self.mineral_table.item(row, 1).text() if self.mineral_table.item(row, 1) else '').strip()
            if not name or not formula:
                continue
            R.parse_formula(formula)
            if R.MINERALS.get(name) != formula:
                minerals[name] = formula
        return {'crust': crust, 'minerals': minerals}

    def _save(self):
        """Check and keep the values, or say what is wrong."""
        try:
            values = self.values()
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        R.save_user(values)
        self.accept()
