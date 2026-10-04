"""
This file describes the base classes for particle data builders. In this
The particle builders are classes that will add information to a ``dict``.
"""


class ParticleBuilder:
    """
    Base class for ``ParticleBuilder``, classes that add entries to a
    dictionary.
    """

    def __init__(self):
        self.initialized = False

    def init(self):
        """
        Call to initialize the builders starting this step of the chain. It's
        for expensive calculations that don't need to be called every time
        the operation is executed.
        """
        self.initialized = True

    def build(self, particle: dict) -> dict:
        """
        Call to build on the data starting this step of the chain.

        Args:
            particle: Current state of the data to build on (it will be mutated).

        Returns:
            The particle with the mutated data of all the chain links starting
            this link.
        """
        return particle
