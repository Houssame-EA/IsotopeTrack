from tools.nano_particle_shape.nps_validators import validate_required, validate_stoichiometry
from utils.validation import IValidation, ValidationInfos


class NanoParticleShape(IValidation):
    """
    Base class for nano particle shapes.
    """

    def __init__(self, name=None):
        self.name = name

    def get_name(self):
        """
        Returns:
            (str) string of the informal way of calling the nano particle shape.
        """
        return self.name

    def get_formula(self):
        """
        Returns:
            (str) string that represents the nano particle.
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

        Returns: `ValidationInfos` that lists all invalid fields in `errors`
        (`list[str]`) and list of all cleanups as `messages`
        (`list[str]`).
        """
        messages: list[str] = []
        if not self.name:
            self.name = self.get_formula()
            messages.append(f"No name was given to the shape, so the formula "
                            f"\"{self.get_formula()}\" was taken instead")

        return ValidationInfos(messages=messages)

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
        return "Shpere"

    def validate(self) -> ValidationInfos:
        if not self.formula:
            validation = validate_required(self.formula, "Formula")
        else:
            self.formula, validation = validate_stoichiometry(self.formula)

            if not validation.has_errors():
                validation.merge(super().validate())
        return validation
