"""The available shapes classes (subclasses of `NanoParticleShape`)."""
from tools.mass_fraction_calculator_utils.formula_utils import parse_formula_to_counts
from tools.nanoparticle_shape.nps_validators import validate_required, validate_stoichiometry_and_required, \
    validate_trim, \
    validate_strictly_positive
from utils.validation import IValidation, ValidationInfos
from dataclasses import dataclass


@dataclass
class Compound(IValidation):
    formula: str = ""
    density: float = 0.0
    material_id: str = ""
    mp_url: str = ""
    space_group: str = ""
    signature: str = ""
    display_text: str | None = None

    def __str__(self):
        return (self.display_text
                if self.display_text is not None
                else "")

    def get_elements_with_counts(self) -> dict[str, int]:
        """
        Returns elements with their counts
        """
        return parse_formula_to_counts(self.formula)

    def validate(self) -> ValidationInfos:
        """
        Validates formula and density only.

        Validations:

        * Formula and density are required.
        * Density must not be negative or null.
        * Formula will be stoichiometrically reformated.

        Notes:
            If others are required, user a `Validator` class to implement the
            other validation type.

        Returns:
            `ValidationInfos` that represents the state of the object.
        """
        return self._validate_formula().merge(self._validate_density())

    def _validate_formula(self):
        self.formula, stoichiometry_validation = validate_stoichiometry_and_required(self.formula, "Formula")
        return stoichiometry_validation

    def _validate_density(self):
        required_validation = validate_required(self.density, "Density")
        if required_validation.has_errors():
            return required_validation
        return validate_strictly_positive(self.density, "Density")


class NanoParticleShape(IValidation):
    """
    Base class for nanoparticle shapes.
    """

    def __init__(self, name=None):
        if name is None:
            name = ""
        self.name = name

    def get_name(self):
        """
        Returns:
            string of the informal way of calling the nanoparticle shape.
        """
        return self.name

    def get_formula(self):
        """
        Returns:
            string that represents the nanoparticle.
        """
        return "No formula"

    def get_shape(self):
        """
        Returns:
            (str) shape name.
        """
        return "No shape name"

    def validate(self) -> ValidationInfos:
        """
        Cleanup (strip, reformat, etc.) and validation of all fields.

        Returns:
            `ValidationInfos` that lists all invalid fields in `errors`
            (`list[str]`) and list of all cleanups as `messages`
            (`list[str]`).
        """
        self.name, trim_validation = validate_trim(self.name, represents="Name")
        if not self.name:
            self.name = self.get_formula()
            return ValidationInfos(messages=[f"No name was given to the shape, "
                                             f"so the formula \"{self.get_formula()}\" "
                                             f"was taken instead"])
        return trim_validation

    def __repr__(self):
        return f"<{self.__module__}.{self.__class__.__name__} formula={self.get_formula()}, shape={self.get_shape()}>"


class CoreShellNPS(NanoParticleShape):
    def __init__(self,
                 core: Compound | None = None,
                 shell: Compound | None = None,
                 name=None):
        super().__init__(name=name)

        if core is None:
            core = Compound()
        self.core: Compound = core
        if shell is None:
            shell = Compound()
        self.shell: Compound = shell

    def get_formula(self):
        return f"{self.core.formula}  + {self.shell.formula}"

    def get_shape(self):
        return "Core-Shell"

    def validate(self) -> ValidationInfos:
        validation = self._validate_core().merge(self._validate_shell())

        if not validation.has_errors():
            validation.merge(super().validate())

        return validation

    def _validate_core(self) -> ValidationInfos:
        return self.core.validate().add_identifier("Core")

    def _validate_shell(self) -> ValidationInfos:
        return self.shell.validate().add_identifier("Shell")


class SphereNPS(NanoParticleShape):
    def __init__(self,
                 formula: Compound | None = None,
                 name=None):
        super().__init__(name=name)

        if formula is None:
            formula = Compound()
        self.formula: Compound = formula

    def get_formula(self):
        return self.formula.formula

    def get_shape(self):
        return "Sphere"

    def validate(self) -> ValidationInfos:
        validation = self.formula.validate().add_identifier("Formula")

        if not validation.has_errors():
            validation.merge(super().validate())
        return validation
