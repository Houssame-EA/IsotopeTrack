# -*- coding: utf-8 -*-
"""Tests for the core expression engine in tools/particle_classifier_expr.py.

These functions decide which particles a classifier definition matches, and
whether two definitions can confound each other or are self-contradictory /
tautological. A bug here silently mislabels particles downstream (Stage 4),
so the tokenizer/parser's strictness, the evaluator's AND/OR/one-hot-XOR/NOT
semantics, and the structural confound/contradiction analyses are worth
pinning down precisely. Everything tested here is pure Python — no Qt.
"""
import pytest

from tools import particle_classifier_expr as pce


# --------------------------------------------------------------------------- #
# tokenize
# --------------------------------------------------------------------------- #
class TestTokenize:
    def test_simple_and(self):
        toks = pce.tokenize("60Ni+107Ag")
        assert [t.kind for t in toks] == ['ISOTOPE', '+', 'ISOTOPE']
        assert [t.value for t in toks] == ['60Ni', '+', '107Ag']

    def test_whitespace_around_structural_chars_tolerated(self):
        toks = pce.tokenize(" 60Ni  +  107Ag ")
        assert [t.value for t in toks] == ['60Ni', '+', '107Ag']

    def test_all_structural_chars(self):
        toks = pce.tokenize("[60Ni, 107Ag] + {197Au; 208Pb} + !(60Ni)")
        kinds = [t.kind for t in toks]
        assert kinds == [
            '[', 'ISOTOPE', ',', 'ISOTOPE', ']', '+',
            '{', 'ISOTOPE', ';', 'ISOTOPE', '}', '+',
            '!', '(', 'ISOTOPE', ')',
        ]

    def test_lowercase_symbol_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60ni")

    def test_all_caps_symbol_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60NI")

    def test_whitespace_inside_isotope_token_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60 Ni")

    def test_two_isotopes_glued_together_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60Ni107Ag")

    def test_unknown_character_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60Ni & 107Ag")

    def test_isotope_missing_mass_number_is_error(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("Ni")

    def test_three_letter_symbol_rejected(self):
        # No real element symbol is 3 letters; anything past 2 letters
        # glued on with no separator is a tokenizer error.
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.tokenize("60Nix")


# --------------------------------------------------------------------------- #
# parse — valid parses
# --------------------------------------------------------------------------- #
class TestParseValid:
    def test_single_isotope(self):
        ast = pce.parse("60Ni")
        assert ast == pce.Isotope("60Ni")

    def test_and_chain(self):
        ast = pce.parse("60Ni+107Ag+197Au")
        assert isinstance(ast, pce.And)
        assert ast.terms == [
            pce.Isotope("60Ni"), pce.Isotope("107Ag"), pce.Isotope("197Au")]

    def test_or_group(self):
        ast = pce.parse("[60Ni, 107Ag]")
        assert isinstance(ast, pce.Or)
        assert ast.branches == [pce.Isotope("60Ni"), pce.Isotope("107Ag")]

    def test_xor_group(self):
        ast = pce.parse("{60Ni; 107Ag; 197Au}")
        assert isinstance(ast, pce.Xor)
        assert len(ast.branches) == 3

    def test_not_group(self):
        ast = pce.parse("!(60Ni)")
        assert isinstance(ast, pce.Not)
        assert ast.inner == pce.Isotope("60Ni")

    def test_not_allows_whitespace_before_paren(self):
        ast = pce.parse("!  (60Ni)")
        assert isinstance(ast, pce.Not)

    def test_parentheses_grouping(self):
        ast = pce.parse("(60Ni+107Ag)")
        assert isinstance(ast, pce.And)

    def test_nested_or_branch_is_compound(self):
        # One OR-branch is itself an AND-compound (design §8 example).
        ast = pce.parse("[60Ni+107Ag, 197Au]")
        assert isinstance(ast, pce.Or)
        assert isinstance(ast.branches[0], pce.And)
        assert ast.branches[1] == pce.Isotope("197Au")

    def test_deeply_nested(self):
        ast = pce.parse("!({60Ni; [107Ag, 197Au]})")
        assert isinstance(ast, pce.Not)
        assert isinstance(ast.inner, pce.Xor)
        assert isinstance(ast.inner.branches[1], pce.Or)


# --------------------------------------------------------------------------- #
# parse — syntax errors
# --------------------------------------------------------------------------- #
class TestParseErrors:
    def test_empty_expression(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("")

    def test_whitespace_only_expression(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("   ")

    def test_missing_closing_bracket(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("[60Ni, 107Ag")

    def test_missing_opening_bracket(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("60Ni, 107Ag]")

    def test_mismatched_bracket_types(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("[60Ni, 107Ag}")

    def test_wrong_bracket_for_or_group(self):
        # OR uses [...]; using {...} with comma separators is malformed.
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("{60Ni, 107Ag}")

    def test_not_without_parens(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("!60Ni")

    def test_not_with_space_then_no_paren(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("!60Ni)")

    def test_trailing_operator(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("60Ni+")

    def test_leading_operator(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("+60Ni")

    def test_dangling_comma_in_or(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("[60Ni,]")

    def test_stray_closing_paren(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("60Ni)")

    def test_double_plus(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("60Ni++107Ag")

    def test_trailing_garbage_after_valid_expression(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("(60Ni) 107Ag")

    def test_empty_parens(self):
        with pytest.raises(pce.ExpressionSyntaxError):
            pce.parse("()")


# --------------------------------------------------------------------------- #
# referenced_isotopes
# --------------------------------------------------------------------------- #
class TestReferencedIsotopes:
    def test_simple(self):
        assert pce.referenced_isotopes(pce.parse("60Ni+107Ag")) == \
            {"60Ni", "107Ag"}

    def test_nested(self):
        ast = pce.parse("!({60Ni; [107Ag, 197Au+208Pb]})")
        assert pce.referenced_isotopes(ast) == \
            {"60Ni", "107Ag", "197Au", "208Pb"}

    def test_single_isotope(self):
        assert pce.referenced_isotopes(pce.parse("60Ni")) == {"60Ni"}


# --------------------------------------------------------------------------- #
# evaluate — partial mode, all four operators
# --------------------------------------------------------------------------- #
class TestEvaluatePartial:
    def test_isotope_leaf(self):
        ast = pce.parse("60Ni")
        assert pce.evaluate(ast, {"60Ni"}, "partial") is True
        assert pce.evaluate(ast, {"107Ag"}, "partial") is False

    def test_and_requires_all(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.evaluate(ast, {"60Ni", "107Ag"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni", "107Ag", "197Au"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni"}, "partial") is False

    def test_or_requires_any(self):
        ast = pce.parse("[60Ni, 107Ag]")
        assert pce.evaluate(ast, {"60Ni"}, "partial") is True
        assert pce.evaluate(ast, {"107Ag"}, "partial") is True
        assert pce.evaluate(ast, {"197Au"}, "partial") is False

    def test_not_negates(self):
        ast = pce.parse("!(60Ni)")
        assert pce.evaluate(ast, {"107Ag"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni"}, "partial") is False

    def test_ignores_isotopes_outside_vocabulary(self):
        ast = pce.parse("60Ni")
        assert pce.evaluate(ast, {"60Ni", "197Au"}, "partial") is True

    def test_xor_one_hot_exactly_one_of_two(self):
        ast = pce.parse("{60Ni; 107Ag}")
        assert pce.evaluate(ast, {"60Ni"}, "partial") is True
        assert pce.evaluate(ast, {"107Ag"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni", "107Ag"}, "partial") is False
        assert pce.evaluate(ast, set(), "partial") is False

    def test_xor_one_hot_three_branches_not_parity(self):
        # One-hot XOR: exactly one of three must hold. Classic parity XOR
        # would make "all three present" evaluate True (odd count) — this
        # must be False under one-hot semantics.
        ast = pce.parse("{60Ni; 107Ag; 197Au}")
        assert pce.evaluate(ast, {"60Ni"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni", "107Ag"}, "partial") is False
        assert pce.evaluate(ast, {"60Ni", "107Ag", "197Au"}, "partial") is False
        assert pce.evaluate(ast, set(), "partial") is False

    def test_nested_and_within_or(self):
        ast = pce.parse("[60Ni+107Ag, 197Au]")
        assert pce.evaluate(ast, {"60Ni", "107Ag"}, "partial") is True
        assert pce.evaluate(ast, {"60Ni"}, "partial") is False
        assert pce.evaluate(ast, {"197Au"}, "partial") is True

    def test_deeply_nested_combo(self):
        ast = pce.parse("!({60Ni; [107Ag, 197Au]})")
        # Xor branch 1 (60Ni) true, branch 2 (107Ag or 197Au) false -> xor True -> not -> False
        assert pce.evaluate(ast, {"60Ni"}, "partial") is False
        # Neither branch true -> xor False -> not -> True
        assert pce.evaluate(ast, set(), "partial") is True

    def test_invalid_mode_raises(self):
        ast = pce.parse("60Ni")
        with pytest.raises(ValueError):
            pce.evaluate(ast, {"60Ni"}, "bogus")


# --------------------------------------------------------------------------- #
# evaluate — exact mode
# --------------------------------------------------------------------------- #
class TestEvaluateExact:
    def test_exact_pass_when_set_matches_vocabulary(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.evaluate(ast, {"60Ni", "107Ag"}, "exact") is True

    def test_exact_fails_with_extra_isotope(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.evaluate(ast, {"60Ni", "107Ag", "197Au"}, "exact") is False

    def test_partial_still_passes_with_extra_isotope(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.evaluate(ast, {"60Ni", "107Ag", "197Au"}, "partial") is True

    def test_exact_fails_if_formula_itself_not_satisfied(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.evaluate(ast, {"60Ni"}, "exact") is False

    def test_exact_with_or_group_only_allows_branch_isotopes(self):
        ast = pce.parse("[60Ni, 107Ag]")
        assert pce.evaluate(ast, {"60Ni"}, "exact") is True
        assert pce.evaluate(ast, {"60Ni", "197Au"}, "exact") is False


# --------------------------------------------------------------------------- #
# find_confound
# --------------------------------------------------------------------------- #
class TestFindConfound:
    def test_disjoint_isotopes_still_confound_under_partial_semantics(self):
        # Partial-match ignores isotopes outside a formula's own vocabulary,
        # so a particle carrying both 60Ni and 107Ag satisfies "60Ni" and
        # "107Ag" simultaneously -- this is a genuine confound, not a
        # false positive, precisely because neither formula excludes the
        # other's isotope.
        a = pce.parse("60Ni")
        b = pce.parse("107Ag")
        witness = pce.find_confound(a, b)
        assert witness == frozenset({"60Ni", "107Ag"})

    def test_overlapping_definitions_confound(self):
        a = pce.parse("60Ni")
        b = pce.parse("60Ni+107Ag")
        witness = pce.find_confound(a, b)
        assert witness is not None
        assert "60Ni" in witness
        assert "107Ag" in witness

    def test_mutually_exclusive_not_confound(self):
        a = pce.parse("60Ni")
        b = pce.parse("!(60Ni)")
        assert pce.find_confound(a, b) is None

    def test_or_groups_can_confound(self):
        a = pce.parse("[60Ni, 107Ag]")
        b = pce.parse("[107Ag, 197Au]")
        witness = pce.find_confound(a, b)
        # Any assignment satisfying both suffices as a witness; the
        # cheapest is both formulas' shared isotope 107Ag present alone,
        # but the enumeration order here yields another valid witness
        # (60Ni AND 197Au both present) first -- also a legitimate
        # simultaneous-match assignment given partial semantics ignore
        # isotopes outside each formula's own vocabulary.
        assert witness is not None
        assert pce.evaluate(a, witness, "partial") is True
        assert pce.evaluate(b, witness, "partial") is True

    def test_exact_mode_disjoint_vocab_never_confounds(self):
        # Real bug report: under partial semantics "60Ni" and "107Ag"
        # confound (see test_disjoint_isotopes_still_confound_under_
        # partial_semantics above), but if BOTH definitions are Exact
        # Match, no real particle can satisfy both simultaneously -- exact
        # mode requires the particle to carry no isotopes outside each
        # formula's own vocabulary, and these two vocabularies are
        # disjoint, so there is no valid intersection.
        a = pce.parse("60Ni")
        b = pce.parse("107Ag")
        assert pce.find_confound(a, b, "exact", "exact") is None

    def test_exact_mode_still_confounds_when_vocab_overlaps(self):
        # "60Ni" (exact) is satisfied by a particle whose only isotope is
        # 60Ni; "[60Ni,107Ag]" (exact) is also satisfied by that same
        # particle (60Ni present, nothing outside its own vocabulary) --
        # a genuine confound survives even under exact/exact.
        a = pce.parse("60Ni")
        b = pce.parse("[60Ni,107Ag]")
        witness = pce.find_confound(a, b, "exact", "exact")
        assert witness == frozenset({"60Ni"})

    def test_mixed_partial_and_exact_still_confounds(self):
        # A partial-match side imposes no "nothing else present" ceiling,
        # so it can still confound with an exact-match side whenever the
        # exact side's own vocabulary is satisfiable on its own.
        a = pce.parse("60Ni")  # partial
        b = pce.parse("60Ni+107Ag")  # exact
        witness = pce.find_confound(a, b, "partial", "exact")
        assert witness == frozenset({"60Ni", "107Ag"})

    def test_default_modes_preserve_old_partial_behavior(self):
        # Omitting mode_a/mode_b must reproduce the pre-fix partial/partial
        # behavior exactly, so existing callers are unaffected.
        a = pce.parse("60Ni")
        b = pce.parse("107Ag")
        assert pce.find_confound(a, b) == frozenset({"60Ni", "107Ag"})


# --------------------------------------------------------------------------- #
# classify_formula
# --------------------------------------------------------------------------- #
class TestClassifyFormula:
    def test_genuine_contradiction(self):
        ast = pce.parse("60Ni+!(60Ni)")
        assert pce.classify_formula(ast) == "contradiction"

    def test_genuine_tautology(self):
        ast = pce.parse("[60Ni, !(60Ni)]")
        assert pce.classify_formula(ast) == "tautology"

    def test_normal_formula(self):
        ast = pce.parse("60Ni+107Ag")
        assert pce.classify_formula(ast) == "normal"

    def test_single_isotope_is_normal(self):
        ast = pce.parse("60Ni")
        assert pce.classify_formula(ast) == "normal"

    def test_xor_of_isotope_and_its_negation_is_tautology(self):
        ast = pce.parse("{60Ni; !(60Ni)}")
        assert pce.classify_formula(ast) == "tautology"
