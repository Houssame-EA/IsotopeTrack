"""Auto-fill of calibration concentrations restricted to the elements named in a sample."""
import pytest
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from calibration_methods.te_common import elements_in_sample_name

ELEMENTS = [{'symbol': s, 'name': n} for s, n in (
    ('Fe', 'Iron'), ('Ce', 'Cerium'), ('Au', 'Gold'), ('Pb', 'Lead'), ('B', 'Boron'),
    ('S', 'Sulfur'), ('In', 'Indium'), ('C', 'Carbon'), ('O', 'Oxygen'))]


@pytest.mark.parametrize('name, expected', [
    ('Fe_10ppb', {'Fe'}),
    ('FeCe 5ppb', {'Fe', 'Ce'}),
    ('140Ce_1ppb', {'Ce'}),
    ('Fe-Ce-Au 2 ppb', {'Fe', 'Ce', 'Au'}),
    ('iron 3 ppb', {'Fe'}),
    ('10ppb', set()),
    ('Mix 20 ppb', set()),
    ('Std 5ppb', set()),
    ('PPB test', set()),
    ('blank', set()),
])
def test_elements_in_sample_name(name, expected):
    assert elements_in_sample_name(name, ELEMENTS) == expected


@pytest.mark.parametrize('name, expected', [
    ('PPB test 10', set()),
    ('ICP_STD_10ppb', set()),
    ('Fe_Ce_10ppb', {'Fe', 'Ce'}),
    ('142Nd_143Nd 5ppb', {'Nd'}),
    ('Sample 1', set()),
])
def test_real_periodic_table(qapp, name, expected):
    from widget.periodic_table_widget import PeriodicTableWidget
    assert elements_in_sample_name(name, PeriodicTableWidget().get_elements()) == expected


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


def test_autofill_fills_only_named_elements(qapp):
    from calibration_methods.ionic_CAL import IonicCalibrationWindow
    w = IonicCalibrationWindow()
    w.selected_isotopes = {'Fe': [55.9349, 56.9354], 'Ce': [139.9054, 141.9092]}
    w.update_table_columns()
    samples = ['Blank', 'Fe_10ppb', '140Ce_1ppb', 'FeCe 5ppb', 'Mix 20 ppb', 'Au_4ppb', 'Fe_kept_2ppb']
    w.table.setRowCount(len(samples))
    for r, name in enumerate(samples):
        w.table.setItem(r, 0, QTableWidgetItem(name))
    cols = {w.table.horizontalHeaderItem(c).data(0x0100): c for c in range(1, w.table.columnCount())}
    w.table.setItem(6, cols['Ce-139.9054'], QTableWidgetItem('7'))

    w.auto_fill_concentrations()

    def row(r):
        return {k: w.table.item(r, c).text() for k, c in cols.items()}

    assert set(row(0).values()) == {'0'}
    assert row(1) == {'Fe-55.9349': '10.0', 'Fe-56.9354': '10.0', 'Ce-139.9054': '-1', 'Ce-141.9092': '-1'}
    assert row(2) == {'Fe-55.9349': '-1', 'Fe-56.9354': '-1', 'Ce-139.9054': '1.0', 'Ce-141.9092': '1.0'}
    assert set(row(3).values()) == {'5.0'}
    assert set(row(4).values()) == {'20.0'}
    assert set(row(5).values()) == {'4.0'}
    assert row(6)['Ce-139.9054'] == '7'
    assert row(6)['Ce-141.9092'] == '-1'
    assert row(6)['Fe-55.9349'] == '2.0'
    w.data_modified = False
    w.deleteLater()
