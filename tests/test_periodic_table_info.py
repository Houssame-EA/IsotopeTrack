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
