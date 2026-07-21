import unittest

from data_builder import SphereDataBuilder, ResultDataBuilder
from tools.nanoparticle_shape.nanoparticle_shapes import SphereNPS, Compound


class TestSphereDataBuilder(unittest.TestCase):
    def test_constructor(self):
        """Tests the basic `__init__` of the SphereDataBuilder"""
        # Arrange
        sphere_nps = SphereNPS(
            formula=Compound(
                formula="AuAg",
                density=14.44,
            ),
            name="Sphere Name"
        )
        tracked_elements = ["Au", "Ag"]
        next_builder = ResultDataBuilder()

        # Act
        data_builder = SphereDataBuilder(
            sphere_nps=sphere_nps,
            tracked_elements=tracked_elements,
            next=next_builder
        )

        # Assert
        self.assertIs(data_builder.sphere_nps, sphere_nps)
        self.assertIs(data_builder.tracked_elements, tracked_elements)
        self.assertIs(data_builder.next, next_builder)

    def test_set_required_elements(self):
        """Tests what elements are expected to be retained"""
        # Arrange
        sphere_nps = SphereNPS(
            formula=Compound(
                formula="AuAgO",
                density=14.44,
            ),
            name="Sphere Name"
        )
        tracked_elements = ["Au", "Ag", "Ti"]

        data_builder = SphereDataBuilder(
            sphere_nps=sphere_nps,
            tracked_elements=tracked_elements,
        )

        # Act
        data_builder.set_required_elements()

        # Assert
        self.assertSetEqual(set(data_builder.required_elements), {"Ag", "Au"})

    def test_init(self):
        """Makes sure that the builder and the next one is initialized"""
        # Arrange
        sphere_nps = SphereNPS(
            formula=Compound(
                formula="AuAgO",
                density=14.44,
            ),
            name="Sphere Name"
        )
        tracked_elements = ["Au", "Ag", "Ti"]
        next_builder = ResultDataBuilder()

        data_builder = SphereDataBuilder(
            sphere_nps=sphere_nps,
            tracked_elements=tracked_elements,
            next=next_builder
        )
        # Act
        data_builder.init()

        # Assert
        self.assertTrue(data_builder.initialized)
        self.assertTrue(next_builder.initialized,
                        "The next builder was not initialized. Please call "
                        "`super().init()` in the override.")
        self.assertGreater(len(data_builder.tracked_elements), 0)
