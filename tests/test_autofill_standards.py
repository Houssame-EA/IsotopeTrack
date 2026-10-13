"""Auto-fill of calibration concentrations restricted to the elements named in a sample."""
import pytest
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from calibration_methods.te_common import elements_in_sample_name, standards_in_sample_name

PRESETS = {'71A': ['Fe', 'Ce', 'Pb', 'B'], '68A-B': ['Ag', 'Sn'], '68B-C': ['Au', 'Pt'],
           'CMS-1 Rare Earth': ['Ce', 'La']}


@pytest.mark.parametrize('name, expected', [
    ('71A_2ppb', {'Fe', 'Ce', 'Pb', 'B'}),
    ('71a 2 ppb', {'Fe', 'Ce', 'Pb', 'B'}),
    ('68A-B_1ppb', {'Ag', 'Sn'}),
    ('68AB 1ppb', {'Ag', 'Sn'}),
    ('68B-C 0.5ppb', {'Au', 'Pt'}),
    ('68B_C_Au 1ppb', {'Au', 'Pt'}),
    ('CMS-1 5ppb', {'Ce', 'La'}),
    ('171A_2ppb', set()),
    ('71A_68B-C_1ppb', {'Fe', 'Ce', 'Pb', 'B', 'Au', 'Pt'}),
    ('Fe_10ppb', {'Fe'}),
])
def test_presets_in_sample_name(name, expected):
    assert elements_in_sample_name(name, ELEMENTS + [{'symbol': s, 'name': ''} for s in
                                   ('Ag', 'Sn', 'Pt', 'La')], PRESETS) == expected


def test_preset_text_is_not_read_as_symbols():
    found, rest = standards_in_sample_name('68B-C_1ppb', PRESETS)
    assert found == {'Au', 'Pt'} and 'B' not in rest and 'C' not in rest

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
    samples = ['Blank', 'Fe_10ppb', '140Ce_1ppb', 'FeCe 5ppb', 'Mix 20 ppb', 'Au_4ppb', 'Fe_kept_2ppb',
               '71A_2ppb', '68B-C_1ppb']
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
    assert set(row(7).values()) == {'2.0'}
    assert set(row(8).values()) == {'-1'}
    w.data_modified = False
    w.deleteLater()


def test_list_loaded_in_periodic_table_is_recognised(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from widget import periodic_table_widget as ptw
    from calibration_methods.ionic_CAL import IonicCalibrationWindow

    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings("IsotopeTrack", "IsotopeTrack").remove("periodic_table/loaded_lists")
    list_file = tmp_path / '68B-A.txt'
    list_file.write_text('Fe:55.9349\nFe:56.9354\n', encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(list_file), ''))
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

    ptw.PeriodicTableWidget().load_selections()
    assert ptw.loaded_lists()['68B-A'] == ['Fe']
    assert ptw.named_element_lists()['71A'] == ptw.PRESET_LISTS['71A']

    w = IonicCalibrationWindow()
    w.selected_isotopes = {'Fe': [55.9349, 56.9354], 'Ce': [139.9054]}
    w.update_table_columns()
    w.table.setRowCount(1)
    w.table.setItem(0, 0, QTableWidgetItem('68b_a 1ppb'))
    w.auto_fill_concentrations()
    values = {w.table.horizontalHeaderItem(c).data(0x0100): w.table.item(0, c).text()
              for c in range(1, w.table.columnCount())}
    assert values == {'Fe-55.9349': '1.0', 'Fe-56.9354': '1.0', 'Ce-139.9054': '-1'}
    w.data_modified = False
    w.deleteLater()
