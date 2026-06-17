import copy

from tools.nano_particle_shape.nano_particle_shapes import NanoParticleShape


class NanoParticleShapeService:
    """
    This class manages the Nano Particle Shapes (NPS at an app level).

    This means that all app NPS related actions will pass by this class.
    It should be provided by dependency injection when needed. In the current
    architecture. The MainWindow will be the owner of that dependency and will
    be the one providing it.
    """

    def __init__(self, nps_list: list[NanoParticleShape] | None = None):
        if nps_list is None:
            nps_list = []
        self.nps_list = nps_list

    @staticmethod
    def validate_shape(shape: NanoParticleShape):
        """
        Validate a shape's properties to make sure that they don't violate
        nps_list.
        Args:
            shape: shape to validate

        Returns:

        Raises:

        """
        return isinstance(shape, NanoParticleShape)

    def shape_count(self):
        """

        Returns:
            (int) amount of nano particle shape stored in the service.
        """
        return len(self.nps_list)

    def get_shape(self, index: int) -> NanoParticleShape | None:
        """

        Args:
            index: Index of the shape in the list.

        Returns:
            the NanoParticleShape at the specified index or None if the
            index is invalid
        """
        if self.is_index_invalid(index):
            return None
        return copy.deepcopy(self.nps_list[index])

    def is_index_invalid(self, index: int) -> bool:
        return index < 0 or index >= len(self.nps_list)

    def delete_shape(self, index: int):
        """
        Removes nano particule shape from the data
        Args:
            index: Index of the shape to remove
        """
        self.nps_list.pop(index)

    def update_shape(self, index: int, nps: NanoParticleShape):
        if not self.validate_shape(nps):
            print("Shape faild validations")  # TODO: raise an error
            return

        if index == len(self.nps_list):
            self.nps_list.append(nps)

        if self.is_index_invalid(index):
            print("Le changement n'a pas eu lieu")  # TODO: raise an error
            return
        self.nps_list[index] = nps
