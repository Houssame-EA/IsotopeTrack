from typing import Any

from tools.mass_fraction_calculator_utils.formula_utils import canonicalize_preserve_user_order
from utils.validation import ValidationInfos


def validate_stoichiometry(formula: str, represents: str | None = None) -> tuple[str, ValidationInfos]:
    """
    Validates the stoichiometry of a formula, and returns it reduced, with a
    `ValidationInfos` message (or error if the result is empty).
    Args:
        formula: The formula to reduce.
        represents: What the formula represents (or is associated with) for the
         user.

    Returns:
        `tuple[str, ValidationInfos]` a tuple, which first field is a `str` of
        the reduced formula and the second field is the `ValidationInfos` of
        the operation
    """
    reduced_formula = canonicalize_preserve_user_order(formula)
    formated_represents = f" ({represents})" if represents else ''

    if not reduced_formula:
        return reduced_formula, ValidationInfos(
            errors=[f"\"{formula}\"{formated_represents} was stoichiometrically "
                    f"reduced to an empty formula"]
        )
    if reduced_formula != formula:
        return reduced_formula, ValidationInfos(
            messages=[f"\"{formula}\"{formated_represents} was "
                      f"stoichiometrically reduced to \"{reduced_formula}\""]
        )

    return reduced_formula, ValidationInfos()


def validate_required(value: Any, represents: str | None = None):
    """
    If the `value` argument is truthy `ValidationInfos` will be empty.
    Otherwise, `ValidationInfos` will have a "value required" error.
    Args:
        value: The value to check truthiness
        represents: What the value represents to the user

    Returns:
        empty `ValidationInfos` if `value` is truthy else a `ValidationInfos`
        with a "value required" error.
    """
    if not value:
        if represents:
            return ValidationInfos(errors=[f"{represents} is/are required."])
        else:
            return ValidationInfos(errors=[f"Required field(s) is/are missing."])
    return ValidationInfos()
