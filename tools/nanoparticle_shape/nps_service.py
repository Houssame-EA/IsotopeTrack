import copy
from typing import Self

from _hashlib import HASH

from tools.nanoparticle_shape.nanoparticle_shapes import NanoParticleShape
from utils.validation import ValidationErrorException, ValidationInfos


class NanoParticleShapeService:
    """
    This class manages the NanoParticle Shapes (NPS) at an app level.

    This means that all app NPS related actions will pass by this class.
    It should be provided by dependency injection when needed. In the current
    architecture, the MainWindow will be the owner of that dependency and will
    be the one providing it.
    """

    def __init__(self, nps_list: list[NanoParticleShape] | None = None):
        if nps_list is None:
            nps_list = []
        self.nps_list = nps_list

    def shape_count(self):
        """
        Returns:
            (int) the amount of nanoparticle shape stored in the service.
        """
        return len(self.nps_list)

    def get_shape(self, index: int) -> NanoParticleShape | None:
        """
        Provides the shape if it's index exists (otherwise: `None`)
        Args:
            index (int): Index of the shape in the list.

        Returns:
            the `NanoParticleShape` at the specified index or `None` if the
            index is invalid
        """
        if self.is_index_invalid(index):
            return None
        return copy.deepcopy(self.nps_list[index])

    def is_index_invalid(self, index: int) -> bool:
        return index < 0 or index >= len(self.nps_list)

    def delete_shape(self, index: int):
        """
        Removes nano particule shape from the data.
        Args:
            index: Index of the shape to remove
        """
        self.nps_list.pop(index)

    def update_shape(self, index: int, nps: NanoParticleShape):
        """
        Modifies or inserts a `NanoParticleShape` at the specified index.
        Args:
            index (int): `int` ranging from zero to `self.shape_count()`.
            nps (NanoParticleShape): NanoParticleShape to be inserted.

        Raises:
            ValidationErrorException : When the `nps` has errors on `nps.validate()`.
            IndexError : When the `index` is out of bound.
        """
        validation_info = nps.validate()
        if validation_info.has_errors():
            raise ValidationErrorException(validation_info)

        if index == len(self.nps_list):
            self.nps_list.append(nps)

        if self.is_index_invalid(index):
            raise IndexError(f"IndexOutOfBound: {index} is an invalid index (max index : {len(self.nps_list)})")
        self.nps_list[index] = copy.deepcopy(nps)

    def get_all_shapes(self) -> list[NanoParticleShape]:
        """
        Gets all shapes known to the service
        Returns:
            A list of all `NanoParticleShapes`
        """
        return copy.deepcopy(self.nps_list)

    def load_shapes(self, nps_list: list[NanoParticleShape]) -> list[ValidationInfos]:
        """
        Batch adding of `NanoParticleShape`.
        Args:
            nps_list: List of `NanoParticleShape`s to be added to the service.
        Returns:
            A list of `ValidationInfos` identified by their indexes.
        """
        validation_list = []
        for index, nps in enumerate(nps_list):
            if not isinstance(nps, NanoParticleShape):
                validation_list.append(
                    ValidationInfos(errors=[f"Element {index}: is not a nanoparticle shape."])
                )
                continue

            validation = nps.validate().add_identifier(f"Element {index}")

            if validation.has_errors() or validation.has_messages():
                validation_list.append(validation)

                if validation.has_errors():
                    continue

            self.nps_list.append(copy.deepcopy(nps))

        return validation_list

    def copy(self):
        """
        Returns:
            A copy itself for future incremental update.
        """
        return copy.deepcopy(self)

    def incremental_update(self, other: Self):
        """
        Updates itself to match the ``other``.
        Args:
            other: The ``NanoParticuleShapeService`` to update to.
        """
        self.nps_list = other.nps_list

    def add_fingerprint_to(self, hash: HASH):
        """
        Adds its part of the fingerprint to the `hash`.
        Args:
            hash: hash to modify.
        """
        hash.update(repr(self.nps_list).encode("utf-8", "replace"))
