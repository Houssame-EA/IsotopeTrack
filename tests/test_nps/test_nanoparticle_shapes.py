import unittest

from tools.mass_fraction_calculator_utils.formula_utils import signature_from_formula
from tools.nanoparticle_shape.nanoparticle_shapes import Compound


class TestCompound(unittest.TestCase):
    def test_compound__init__(self):
        # Arrange
        formula = "H2O"
        density = 1.04
        material_id = "mp-1974803"
        mp_url = "https://next-gen.materialsproject.org/materials/mp-1974803"
        space_group = "Cc"
        signature = signature_from_formula(formula)
        display_text = "display text"

        # Act
        compound = Compound(formula=formula,
                            density=density,
                            material_id=material_id,
                            mp_url=mp_url,
                            space_group=space_group,
                            signature=signature,
                            display_text=display_text)

        # Assert
        self.assertEqual(compound.formula, formula)
        self.assertEqual(compound.density, density)
        self.assertEqual(compound.material_id, material_id)
        self.assertEqual(compound.mp_url, mp_url)
        self.assertEqual(compound.space_group, space_group)
        self.assertEqual(compound.signature, signature)
        self.assertEqual(compound.display_text, display_text)
        self.assertEqual(str(compound), display_text)

    def test_compound_validate_minimal_pass(self):
        # Arrange
        compound = Compound(formula="H2O", density=0.1)
        # Act
        validation = compound.validate()

        # Assert
        self.assertFalse(validation.has_errors())
        self.assertFalse(validation.has_messages())

    def test_compound_validate_formula_is_modified(self):
        # Arrange
        compound = Compound(formula="H2O2", density=0.1)

        # Act
        validation = compound.validate()

        # Assert
        self.assertFalse(validation.has_errors())
        self.assertTrue(validation.has_messages())
        self.assertEqual(compound.formula, "HO")

    def test_compound_validate_density_0_error(self):
        # Arrange
        compound = Compound(formula="H2O", density=0.0)

        # Act
        validation = compound.validate()

        # Assert
        self.assertTrue(validation.has_errors())
        self.assertFalse(validation.has_messages())
        self.assertEqual(len(validation.errors), 1)

    def test_compound_validate_density_neg_error(self):
        # Arrange
        compound = Compound(formula="H2O", density=-10.0)

        # Act
        validation = compound.validate()

        # Assert
        self.assertTrue(validation.has_errors())
        self.assertFalse(validation.has_messages())
        self.assertEqual(len(validation.errors), 1)


    def test_compound_validate_formula_density_required(self):
        # Arrange/Act
        validation_infos = Compound().validate()

        # Assert
        self.assertTrue(validation_infos.has_errors())
        self.assertEqual(len(validation_infos.errors), 2)
        self.assertFalse(validation_infos.has_messages())





if __name__ == '__main__':
    unittest.main()
