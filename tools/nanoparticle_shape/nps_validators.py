from typing import Any

from tools.mass_fraction_calculator_utils.formula_utils import canonicalize_preserve_user_order
from utils.validation import ValidationInfos


def _format_represents(represents: str | None = None):
    return f" ({represents})" if represents else ''


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

    if not reduced_formula:
        return reduced_formula, ValidationInfos(
            errors=[f"\"{formula}\"{_format_represents(represents)} was "
                    f"reduced to an empty formula"]
        )
    if reduced_formula != formula:
        return reduced_formula, ValidationInfos(
            messages=[f"\"{formula}\"{_format_represents(represents)} was "
                      f"reduced to \"{reduced_formula}\""]
        )

    return reduced_formula, ValidationInfos()


def validate_required(value: Any, represents: str | None = None) -> ValidationInfos:
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


def validate_trim(value: str, represents: str | None = None) -> tuple[str, ValidationInfos]:
    """
    Trims the value and gives the appropriate messages.
    Args:
        value (str): Value to trim
        represents (str | None): What the value represents to the user

    Returns:
        `tuple[str, ValidationInfos]` a tuple of the trimmed value
        and the `ValidationInfos` of the operation
    """
    stripped_value = value.strip()
    messages = []
    if stripped_value != value:
        messages.append(f"\"{value}\"{_format_represents(represents)} was "
                        f"trimmed to \"{stripped_value}\"")

    return stripped_value, ValidationInfos(messages=messages)
