import unittest
from unittest.mock import MagicMock

from data_builder import ResultDataBuilder


class TestResultDataBuilder(unittest.TestCase):
    def test_constructor_no_next(self):
        # Arrange/Act
        data_builder = ResultDataBuilder()

        # Assert
        self.assertIsNone(data_builder.next)
        self.assertFalse(data_builder.initialized)

    def test_constructor_next(self):
        # Arrange
        next_builder = ResultDataBuilder()

        # Act
        data_builder = ResultDataBuilder(next=next_builder)

        # Assert
        self.assertIs(data_builder.next, next_builder)
        self.assertFalse(data_builder.initialized)

    def test_set_next(self):
        # Arrange
        next_builder = ResultDataBuilder()
        data_builder = ResultDataBuilder()

        # Act
        chaining_builder = data_builder.set_next(next_builder)

        # Assert
        self.assertIs(data_builder.next, next_builder)
        self.assertIs(chaining_builder, next_builder)

    def test_init(self):
        # Arrange
        next_builder = ResultDataBuilder()
        data_builder = ResultDataBuilder(next=next_builder)

        # Act
        data_builder.init()

        # Assert
        self.assertTrue(data_builder.initialized)
        self.assertTrue(next_builder.initialized)

    def test_build_on(self):
        # Arrange
        original_particle = {"elements": {"56Fe": 400}}

        data_builder = ResultDataBuilder()

        # Acte
        data_builder.init()
        result = data_builder.build_on(original_particle)

        # Assert
        self.assertIs(result, original_particle)

    def test_build_on_with_next(self):
        # Arrange
        original_particle = {"elements": {"56Fe": 400}}
        result_particle = {"elements": {"56Fe": 400}, "densities": {"56Fe": 30}}

        next_builder = ResultDataBuilder()
        next_builder.build_on = MagicMock(return_value=result_particle)

        data_builder = ResultDataBuilder(next=next_builder)

        # Acte
        data_builder.init()
        result = data_builder.build_on(original_particle)

        # Assert
        next_builder.build_on.assert_called_once_with(original_particle)
        self.assertIs(result, result_particle)

