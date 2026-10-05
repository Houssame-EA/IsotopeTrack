"""Chart gallery: every chart type drawn with the user's own particles, ready to pick."""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout)

from results.figure_builder.core import engine as E

THUMB = QSize(232, 174)

GALLERY_GROUPS = {
    'Particles X vs Y': ['scatter', 'density', 'hexbin', 'contour', 'line', 'pairs'],
    'Distributions': ['histogram', 'ecdf', 'qq', 'box', 'violin', 'strip', 'ridgeline'],
    'Composition': ['combinations', 'upset', 'composition', 'pie', 'waffle', 'treemap', 'radar',
                    'ternary', 'lollipop', 'bar'],
    'Matrices and more': ['corr_matrix', 'cooccurrence', 'heatmap', 'parallel', 'timeline'],
}
"""How chart types are grouped in the gallery."""


def _placeholder(text: str, color: str = '#9aa4b2') -> QIcon:
    pix = QPixmap(THUMB)
    pix.fill(QColor('#f6f7f9'))
    qp = QPainter(pix)
    qp.setPen(QColor(color))
    f = QFont()
    f.setPointSizeF(10)
    qp.setFont(f)
    qp.drawText(pix.rect(), Qt.AlignCenter | Qt.TextWordWrap, text)
    qp.end()
    return QIcon(pix)


class ChartGallery(QDialog):
    """Live thumbnails of every chart type; double-click one to use it.

    Signals:
        chosen(str, bool): the chart type, and True to replace the selected
            panel (False adds a new panel).
    """

    chosen = Signal(str, bool)

    def __init__(self, spec: dict, table, render, prepare, has_selection: bool, parent=None):
        """
        Args:
            spec: The current design (its figure style and variables are reused).
            table: The particles to draw.
            render: ``render(spec, table, dpi) -> (QPixmap, report, fig)``.
            prepare: Fills sensible defaults into a new panel dict.
            has_selection: Whether a panel is selected that could be changed.
        """
        super().__init__(parent)
        self.setWindowTitle('Chart gallery — drawn with your particles')
        self.resize(1080, 760)
        self.spec = spec
        self.table = table
        self.render = render
        self.prepare = prepare
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        hint = QLabel('Every chart below is drawn with your own data. Double-click one to add it.')
        hint.setObjectName('fbHint')
        top.addWidget(hint, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search charts…')
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(240)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search)
        lay.addLayout(top)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 22, THUMB.height() + 46))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(4)
        self.list.setUniformItemSizes(True)
        self.list.itemDoubleClicked.connect(lambda _it: self._use(False))
        lay.addWidget(self.list, 1)
        self.items: dict[str, QListWidgetItem] = {}
        order = [k for ks in GALLERY_GROUPS.values() for k in ks if k in E.PANEL_KINDS]
        order += [k for k in E.PANEL_KINDS if k not in order and k not in ('text', 'code')]
        for kind in order:
            item = QListWidgetItem(_placeholder('drawing…'), E.PANEL_KINDS[kind])
            item.setData(Qt.UserRole, kind)
            item.setToolTip(self._group_of(kind))
            self.list.addItem(item)
            self.items[kind] = item
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.replace_btn = QPushButton('Use for the selected panel')
        self.replace_btn.setEnabled(has_selection)
        self.replace_btn.clicked.connect(lambda: self._use(True))
        add = QPushButton('Add as a new panel')
        add.setObjectName('fbPrimary')
        add.setDefault(True)
        add.clicked.connect(lambda: self._use(False))
        close = QPushButton('Close')
        close.clicked.connect(self.reject)
        buttons.addWidget(self.replace_btn)
        buttons.addWidget(add)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self._queue = list(order)
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._render_next)
        self._timer.start()

    @staticmethod
    def _group_of(kind: str) -> str:
        for name, kinds in GALLERY_GROUPS.items():
            if kind in kinds:
                return name
        return ''

    def thumbnail_spec(self, kind: str) -> dict:
        """A one-panel design showing ``kind`` in the current figure style."""
        figure = copy.deepcopy(self.spec.get('figure') or {})
        figure.update(width=4.0, height=3.0, title='', panel_letters=False,
                      font_size=min(9, float(figure.get('font_size') or 9)), title_size=0,
                      label_size=0, tick_size=0)
        panel = self.prepare(E.make_panel(kind=kind, rect=[0.0, 0.0, 1.0, 1.0]))
        return {'data_type': self.spec.get('data_type', 'Counts'),
                'variables': copy.deepcopy(self.spec.get('variables') or []),
                'figure': figure, 'panels': [panel]}

    def _render_next(self):
        if not self._queue:
            self._timer.stop()
            return
        kind = self._queue.pop(0)
        item = self.items.get(kind)
        if item is None:
            return
        try:
            pix, report, _fig = self.render(self.thumbnail_spec(kind), self.table, 58)
            if report.errors:
                item.setIcon(_placeholder('Needs settings for this data:\n'
                                          + next(iter(report.errors.values()))[:80]))
            else:
                item.setIcon(QIcon(pix.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        except Exception as exc:
            item.setIcon(_placeholder(f'Could not draw:\n{str(exc)[:80]}', '#b42318'))

    def _filter(self, text: str):
        text = text.strip().lower()
        for kind, item in self.items.items():
            hay = f'{kind} {item.text()} {self._group_of(kind)}'.lower()
            item.setHidden(bool(text) and text not in hay)

    def _use(self, replace: bool):
        item = self.list.currentItem()
        if item is None:
            return
        self.chosen.emit(item.data(Qt.UserRole), replace and self.replace_btn.isEnabled())
        self.accept()

    def done(self, result):
        self._timer.stop()
        super().done(result)
