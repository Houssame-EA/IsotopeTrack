import unittest

from tools.mass_fraction_calculator_utils.mass_fraction_service import MassFractionService
from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo


class TestMassFractionService(unittest.TestCase):
    element1 = "H"
    element2 = "C"
    defaultVal1 = 1
    defaultVal2 = 2

    defaultValSample = 3

    selected_samples = ["sample1"]

    def setUp(self) -> None:
        self.mass_fraction_service = MassFractionService(PeriodicTableInfo())
        self.mass_fraction_service.set_element_infos(
            {"H": 1, "C": 2},
            {"H": 1, "C": 2},
            {"H": 1, "C": 2}
        )

        self.mass_fraction_service.set_sample_infos(
            {"H": 3},
            {"H": 3},
            {"H": 3},
            self.selected_samples
        )

    def test_get_mass_fraction(self):
        mass_fraction = self.mass_fraction_service.get_mass_fraction(self.element1)

        self.assertEqual(mass_fraction, self.defaultVal1)

    def test_get_mass_fraction_sample(self):
        mass_fraction = self.mass_fraction_service.get_mass_fraction(self.element1, self.selected_samples[0])

        self.assertEqual(mass_fraction, self.defaultValSample)

    def test_get_mass_fraction_undefined_element(self):
        mass_fraction = self.mass_fraction_service.get_mass_fraction("He", self.selected_samples[0])

        self.assertEqual(mass_fraction, 1)

    def test_get_mass_fraction_invalid_element(self):
        mass_fraction = self.mass_fraction_service.get_mass_fraction("Not Valid")

        self.assertEqual(mass_fraction, 1)

    def test_get_element_density(self):
        density = self.mass_fraction_service.get_element_density(self.element1)

        self.assertEqual(density, self.defaultVal1)

    def test_get_element_density_sample(self):
        density = self.mass_fraction_service.get_element_density(self.element1, self.selected_samples[0])

        self.assertEqual(density, self.defaultValSample)

    def test_get_element_density_undefined_element(self):
        density = self.mass_fraction_service.get_element_density("He", self.selected_samples[0])

        self.assertAlmostEqual(density, 0.0001785)

    def test_get_element_density_invalid_element(self):
        density = self.mass_fraction_service.get_element_density("Not Valid")

        self.assertIsNone(density)

    def test_get_molecular_weight(self):
        molecular_weight = self.mass_fraction_service.get_molecular_weight(self.element1)

        self.assertEqual(molecular_weight, self.defaultVal1)

    def test_get_molecular_weight_sample(self):
        molecular_weight = self.mass_fraction_service.get_molecular_weight(self.element1, self.selected_samples[0])

        self.assertEqual(molecular_weight, self.defaultValSample)

    def test_get_molecular_weight_undefined_element(self):
        molecular_weight = self.mass_fraction_service.get_molecular_weight("He", self.selected_samples[0])

        self.assertAlmostEqual(molecular_weight, 4.003)

    def test_get_molecular_weight_invalid_element(self):
        molecular_weight = self.mass_fraction_service.get_molecular_weight("Not Valid")

        self.assertIsNone(molecular_weight)

    def test_set_element_info(self):
        self.mass_fraction_service.set_element_infos(
            {"H": 4},
            {"H": 4},
            {"H": 4})

        # Assert for element level
        self.assertEqual(self.mass_fraction_service.get_mass_fraction("H"), 4)
        self.assertEqual(self.mass_fraction_service.get_element_density("H"), 4)
        self.assertEqual(self.mass_fraction_service.get_molecular_weight("H"), 4)

        # Assert for periodic table level
        self.assertEqual(self.mass_fraction_service.get_mass_fraction("C"), 1)
        self.assertAlmostEqual(self.mass_fraction_service.get_element_density("C"), 2.267)
        self.assertAlmostEqual(self.mass_fraction_service.get_molecular_weight("C"), 12.011)

    def test_set_sample_info(self):
        self.mass_fraction_service.set_sample_infos(
            {"H": 4},
            {"H": 4},
            {"H": 4},
            self.selected_samples + ["Sample2"])

        # Assert for samples
        self.assertEqual(self.mass_fraction_service.get_mass_fraction("H", self.selected_samples[0]), 4)
        self.assertEqual(self.mass_fraction_service.get_element_density("H", self.selected_samples[0]), 4)
        self.assertEqual(self.mass_fraction_service.get_molecular_weight("H", self.selected_samples[0]), 4)

        self.assertEqual(self.mass_fraction_service.get_mass_fraction("H", "Sample2"), 4)
        self.assertEqual(self.mass_fraction_service.get_element_density("H", "Sample2"), 4)
        self.assertEqual(self.mass_fraction_service.get_molecular_weight("H", "Sample2"), 4)

        # Assert for element level
        self.assertEqual(self.mass_fraction_service.get_mass_fraction("C", self.selected_samples[0]), 2)
        self.assertEqual(self.mass_fraction_service.get_element_density("C", self.selected_samples[0]), 2)
        self.assertEqual(self.mass_fraction_service.get_molecular_weight("C", self.selected_samples[0]), 2)

        # Assert for the periodic table
        self.assertEqual(self.mass_fraction_service.get_mass_fraction("Li", self.selected_samples[0]), 1)
        self.assertAlmostEqual(self.mass_fraction_service.get_element_density("Li", self.selected_samples[0]), 0.534)
        self.assertAlmostEqual(self.mass_fraction_service.get_molecular_weight("Li", self.selected_samples[0]), 6.941)
