"""The available shapes classes (subclasses of `NanoParticleShape`)."""
from tools.nanoparticle_shape.nps_validators import validate_required, validate_stoichiometry, validate_trim
from utils.validation import IValidation, ValidationInfos
from dataclasses import dataclass


@dataclass(frozen=True)
class Compound:
    formula: str
    density: float
    material_id: str
    mp_url: str
    space_group: str
    signature: str
    display_text: str | None

    def display_text_with_inner_params(self):
        return (f"{self.formula} [{self.space_group}] ({self.density:.3f} g/cm³)"
                             f" — {self.material_id}")

    def __str__(self):
        return self.display_text


class NanoParticleShape(IValidation):
    """
    Base class for nanoparticle shapes.
    """

    def __init__(self, name=None):
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
    def __init__(self, name=None, core=None, shell=None):
        super().__init__(name=name)
        self.core: str | None = core
        self.shell: str | None = shell

    def get_formula(self):
        return f"{str(self.core)}  + {self.shell}"

    def get_shape(self):
        return "Core-Shell"

    def validate(self) -> ValidationInfos:
        validation = self._validate_core().merge(self._validate_shell())

        if not validation.has_errors():
            validation.merge(super().validate())

        return validation

    def _validate_core(self) -> ValidationInfos:
        if not self.core:
            return validate_required(self.core, represents="Core formula")

        self.core, stoichiometry_validation = validate_stoichiometry(self.core,
                                                                     represents="Core")
        return stoichiometry_validation

    def _validate_shell(self) -> ValidationInfos:
        if not self.shell:
            return validate_required(self.shell, represents="Shell formula")

        self.shell, shell_validation_infos = validate_stoichiometry(self.shell,
                                                                    represents="Shell")
        return shell_validation_infos


class SphereNPS(NanoParticleShape):
    def __init__(self, formula=None, name=None):
        super().__init__(name=name)
        self.formula: str | None = formula

    def get_formula(self):
        return self.formula

    def get_shape(self):
        return "Sphere"

    def validate(self) -> ValidationInfos:
        if not self.formula:
            validation = validate_required(self.formula, "Formula")
        else:
            self.formula, validation = validate_stoichiometry(self.formula, "Formula")

            if not validation.has_errors():
                validation.merge(super().validate())
        return validation
