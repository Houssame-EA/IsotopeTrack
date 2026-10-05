"""Data explorer for the Figure Builder: every particle, and summaries by group."""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QTableView,
    QVBoxLayout, QWidget,
)

from results.figure_builder.expressions import ExpressionError, ParticleTable, evaluate


class FrameModel(QAbstractTableModel):
    """Read-only Qt model over a pandas DataFrame (handles 100k+ rows lazily)."""

    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self.df = df if df is not None else pd.DataFrame()

    def set_frame(self, df: pd.DataFrame):
        """Replace the displayed frame."""
        self.beginResetModel()
        self.df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        v = self.df.iat[index.row(), index.column()]
        if role == Qt.DisplayRole:
            if isinstance(v, (float, np.floating)):
                if not np.isfinite(v):
                    return '' if np.isnan(v) else str(v)
                return f'{v:.4g}'
            return str(v)
        if role == Qt.TextAlignmentRole:
            if isinstance(v, (int, float, np.number)):
                return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self.df.columns[section])
        return str(self.df.index[section])

    def sort(self, column, order=Qt.AscendingOrder):
        if self.df.empty:
            return
        self.beginResetModel()
        self.df = self.df.sort_values(self.df.columns[column],
                                      ascending=order == Qt.AscendingOrder, kind='mergesort')
        self.endResetModel()


def summary_frame(table: ParticleTable, by: str, only_detected: bool = True) -> pd.DataFrame:
    """Per-group statistics of every numeric column.

    Args:
        table: Particle table (variables included).
        by: ``'all'``, ``'sample'`` or ``'class'``.
        only_detected: Ignore zeros (not detected) when summarising.

    Returns:
        DataFrame with one row per (group, column).
    """
    df = table.dataframe()
    numeric = [c for c in df.columns if c not in ('sample', 'class')]
    groups = [('All particles', np.ones(len(df), dtype=bool))]
    if by in ('sample', 'class'):
        col = df[by].to_numpy()
        names = table.samples() if by == 'sample' else table.classes()
        groups = [(str(n), col == n) for n in names]
    rows = []
    for gname, mask in groups:
        for c in numeric:
            v = df[c].to_numpy(dtype=float)[mask]
            v = v[np.isfinite(v)]
            n_all = v.size
            if only_detected:
                v = v[v != 0]
            if v.size == 0:
                rows.append([gname, c, n_all, 0] + [np.nan] * 7)
                continue
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            rows.append([gname, c, n_all, v.size, float(np.mean(v)),
                         float(np.std(v, ddof=1)) if v.size > 1 else np.nan,
                         float(np.min(v)), float(q1), float(med), float(q3), float(np.max(v))])
    return pd.DataFrame(rows, columns=['group', 'column', 'particles', 'detected', 'mean', 'sd',
                                       'min', 'q1', 'median', 'q3', 'max'])


class DataExplorer(QWidget):
    """Browse the particle table or group summaries, filter, sort and export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)
        row = QHBoxLayout()
        row.addWidget(QLabel('Show'))
        self.mode = QComboBox()
        for k, label in (('particles', 'Every particle'), ('sum_all', 'Summary — all particles'),
                         ('sum_sample', 'Summary — by sample'), ('sum_class', 'Summary — by class')):
            self.mode.addItem(label, k)
        self.mode.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.mode)
        row.addWidget(QLabel('where'))
        from results.figure_builder.widgets import ExpressionEdit
        self.where = ExpressionEdit()
        self.where.setPlaceholderText('optional, e.g. Fe > 0 and sample == "Blank"')
        self.where.returnPressed.connect(self.refresh)
        self.where.editingFinished.connect(self.refresh)
        row.addWidget(self.where, 1)
        self.info = QLabel('')
        self.info.setStyleSheet('color: #6b7280;')
        row.addWidget(self.info)
        export = QPushButton('Export CSV…')
        export.clicked.connect(self._export)
        row.addWidget(export)
        lay.addLayout(row)
        self.view = QTableView()
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setDefaultSectionSize(22)
        self.model = FrameModel()
        self.view.setModel(self.model)
        lay.addWidget(self.view, 1)
        self._frame = pd.DataFrame()

    def set_table(self, table: ParticleTable):
        """Point the explorer at a (new) particle table."""
        self.table = table
        self.where.set_names(table.names() if table is not None else [])
        if self.isVisible():
            self.refresh()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.refresh()

    def _filtered_table(self):
        text = self.where.text().strip()
        if not text or self.table is None:
            self.where.mark(None)
            return self.table, None
        try:
            mask = evaluate(text, self.table, as_mask=True)
        except ExpressionError as exc:
            self.where.mark(str(exc))
            return self.table, None
        self.where.mark(None)
        return self.table, mask

    def refresh(self, *_args):
        """Recompute what is shown."""
        if self.table is None or not len(self.table):
            self.model.set_frame(pd.DataFrame())
            self.info.setText('No particles')
            return
        table, mask = self._filtered_table()
        mode = self.mode.currentData()
        if mode == 'particles':
            df = table.dataframe()
            if mask is not None:
                df = df[mask]
            self._frame = df
            self.info.setText(f'{len(df):,} particles')
        else:
            sub = table
            if mask is not None:
                sub = ParticleTable([p for p, m in zip(table.particles, mask) if m],
                                    table.default_prefix, table.labels, table.sample_order,
                                    table.class_order, table.class_colors)
                sub._single_sample = getattr(table, '_single_sample', None)
                sub.set_variables(table.variables)
            by = {'sum_all': 'all', 'sum_sample': 'sample', 'sum_class': 'class'}[mode]
            self._frame = summary_frame(sub, by)
            self.info.setText('zeros (not detected) excluded from statistics')
        self.model.set_frame(self._frame)
        self.view.resizeColumnsToContents()

    def _export(self):
        if self._frame is None or self._frame.empty:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export data', 'figure_data.csv',
                                              'CSV (*.csv)')
        if path:
            self._frame.to_csv(path, index=False)
