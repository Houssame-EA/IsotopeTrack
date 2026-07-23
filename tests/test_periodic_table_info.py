import unittest

from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo


class TestPeriodicTableInfo(unittest.TestCase):
    def setUp(self) -> None:
        self.periodic_table_info = PeriodicTableInfo()

    def test_get_mass_by_element(self):
        self.assertAlmostEqual(self.periodic_table_info.get_mass_by_element("H"),
                               1.008,
                               3)

    def test_get_mass_by_element_invalid_input(self):
        self.assertIsNone(self.periodic_table_info.get_density_by_element("Invalid"))

    def test_get_density_by_element(self):
        self.assertAlmostEqual(self.periodic_table_info.get_density_by_element("H"),
                               8.988E-05,
                               9)

    def test_get_density_by_element_invalid_input(self):
        self.assertIsNone(self.periodic_table_info.get_density_by_element("Invalid"))

    def test_element_exists_true(self):
        self.assertTrue(self.periodic_table_info.element_exists("H"))

    def test_element_exists_false(self):
        self.assertFalse(self.periodic_table_info.element_exists("Invalid"))

    def test_get_element_by_symbol(self):
        element_dict = self.periodic_table_info.get_element_by_symbol("H")

        self.assertIsNotNone(element_dict)
        self.assertDictEqual(element_dict,
                             {'symbol': 'H', 'name': 'Hydrogen',
                              'mass': 1.008, 'row': 0, 'col': 0,
                              'isotopes': [{'mass': 1.00783, 'abundance': 99.9844, 'label': '1H'},
                                           {'mass': 2.0141, 'abundance': 0.01557, 'label': '2H'},
                                           {'mass': 3.016049, 'abundance': 0, 'label': '3H'}],
                              'category': 'other', 'atomic_number': 1,
                              'density': 8.988e-05, 'ionization_energy': 13.6})

    def test_get_element_by_symbol_invalid(self):
        element_dict = self.periodic_table_info.get_element_by_symbol("Invalid")
        self.assertIsNone(element_dict)

