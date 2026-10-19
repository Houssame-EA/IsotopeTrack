"""Tests for widget/frozen_column.py: the first table column stays in place."""
import pytest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from widget.frozen_column import FrozenColumns


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


def test_first_column_follows_table(qapp):
    table = QTableWidget(5, 30)
    for r in range(5):
        table.setItem(r, 0, QTableWidgetItem(f'sample {r}'))
    clicks = []
    table.cellClicked.connect(lambda r, c: clicks.append((r, c)))
    table.resize(500, 200)
    frozen = FrozenColumns(table, 1)
    table.show()
    qapp.processEvents()

    assert frozen.model() is table.model()
    assert frozen.selectionModel() is table.selectionModel()
    assert not frozen.isColumnHidden(0) and frozen.isColumnHidden(1)

    table.setColumnWidth(0, 180)
    table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
    qapp.processEvents()
    assert frozen.columnWidth(0) == 180
    assert frozen.isVisible()

    table.insertColumn(30)
    assert frozen.isColumnHidden(30)

    frozen.clicked.emit(table.model().index(3, 0))
    assert clicks == [(3, 0)]
    table.close()
