# -*- coding: utf-8 -*-
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from results.shared_plot_utils import (
    format_element_label,
    format_combination_label,
    format_label_text_tokens,
)


class TestAtomicNotationLabelFormatting(unittest.TestCase):
    def test_atomic_notation_prefix(self):
        self.assertEqual(format_element_label("197Au", "Atomic Notation"), "<sup>197</sup>Au")
        self.assertEqual(format_element_label("56Fe", "Atomic Notation"), "<sup>56</sup>Fe")
        self.assertEqual(format_element_label("107Ag", "Atomic Notation"), "<sup>107</sup>Ag")

    def test_atomic_notation_other_common_forms(self):
        expected = "<sup>197</sup>Au"
        self.assertEqual(format_element_label("Au197", "Atomic Notation"), expected)
        self.assertEqual(format_element_label("Au-197", "Atomic Notation"), expected)
        self.assertEqual(format_element_label("Au 197", "Atomic Notation"), expected)

    def test_atomic_notation_plain_symbol(self):
        self.assertEqual(format_element_label("Au", "Atomic Notation"), "Au")
        self.assertEqual(format_element_label("Fe", "Atomic Notation"), "Fe")

    def test_weird_labels_do_not_crash(self):
        out1 = format_element_label("???", "Atomic Notation")
        out2 = format_element_label("???", "Atomic Notation")
        self.assertEqual(out1, out2)

    def test_existing_modes_preserved(self):
        self.assertEqual(format_element_label("197Au", "Symbol"), "Au")
        self.assertEqual(format_element_label("197Au", "Mass + Symbol"), "197Au")

    def test_combination_label_modes(self):
        raw = "197Au, 56Fe"
        self.assertEqual(format_combination_label(raw, "Symbol"), "Au, Fe")
        self.assertEqual(format_combination_label(raw, "Mass + Symbol"), "197Au, 56Fe")
        self.assertEqual(
            format_combination_label(raw, "Atomic Notation"),
            "<sup>197</sup>Au, <sup>56</sup>Fe",
        )

    def test_axis_text_token_formatting(self):
        self.assertEqual(
            format_label_text_tokens("197Au (Counts)", "Atomic Notation"),
            "<sup>197</sup>Au (Counts)",
        )
        self.assertEqual(
            format_label_text_tokens("log\u2081\u2080(197Au) (Counts)", "Atomic Notation"),
            "log\u2081\u2080(<sup>197</sup>Au) (Counts)",
        )


if __name__ == "__main__":
    unittest.main()
