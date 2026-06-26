import unittest

from utils.validation import ValidationInfos


class TestCompound(unittest.TestCase):
    def test_validation__init__(self):
        messages = ["Message 1", "Message 2"]
        errors = ["Error 1", "Error 2"]
        validation_info = ValidationInfos(messages=messages, errors=errors)

        self.assertTrue(validation_info.has_messages())
        self.assertTrue(validation_info.has_errors())
        self.assertEqual(messages, validation_info.messages)
        self.assertEqual(errors, validation_info.errors)

    def test_merge(self):
        message1 = ["Message 1"]
        message2 = ["Message 2"]
        error1 = ["Error 1"]
        error2 = ["Error 2"]

        validation_info1 = ValidationInfos(messages=message1, errors=error1)
        validation_info2 = ValidationInfos(messages=message2, errors=error2)

        validation_merge = validation_info1.merge(validation_info2).merge(validation_info2)

        self.assertIs(validation_info1, validation_merge)
        self.assertEqual(3, len(validation_merge.messages))
        self.assertEqual(3, len(validation_merge.errors))

    def test_compact_list(self):
        message1 = ["Message 1"]
        message2 = ["Message 2"]
        error1 = ["Error 1"]
        error2 = ["Error 2"]

        validation_info1 = ValidationInfos(messages=message1, errors=error1)
        validation_info2 = ValidationInfos(messages=message2, errors=error2)

        validation_info = ValidationInfos.compact([validation_info1, validation_info2, validation_info1])

        self.assertIsNot(validation_info, validation_info1)
        self.assertIsNot(validation_info, validation_info2)
        self.assertEqual(3, len(validation_info.messages))
        self.assertEqual(3, len(validation_info.errors))

    def test_compact_list_empty(self):
        validation_info = ValidationInfos.compact([])

        self.assertIsInstance(validation_info, ValidationInfos)
        self.assertFalse(validation_info.has_messages())
        self.assertFalse(validation_info.has_errors())
