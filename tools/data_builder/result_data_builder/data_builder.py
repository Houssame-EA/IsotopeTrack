"""
This file describes the base classes for the data builders. In this context,
data builders are classes that will add information to a ``dict``. The builders
will use a chain of responsibility pattern so multiple NPSs can be selected at once.
"""
from typing import Self, Optional


class ResultDataBuilder:
    """
    Base class for ``ResultDataBuilder``, classes that add entries to a
    dictionary.
    """

    def __init__(self, next: Optional[Self] = None):
        self.next: Optional[Self] = next
        self.initialized = False

    def set_next(self, next: Self) -> Self:
        """
        Sets the next ``ResultDataBuilder`` in the chain.
        Args:
            next: The next ``ResultDataBuilder`` in the chain.
        Returns:
            Next to easily chain them together.
        """
        self.next = next
        return next

    def init(self):
        """
        Call to initialize the builders starting this step of the chain. It's
        for expensive calculations that don't need to be called every build
        should be done here.

        Notes:
            To keep consistency, always call `super().init()` when trying to
            pass to the next chain link.
        """
        self.initialized = True
        if self.next:
            self.next.init()

    def build_on(self, particle: dict) -> dict:
        """
        Call to build on the data starting this step of the chain.

        Notes:
            To keep consistency, always call `super().particle()` when trying to
            pass to the next chain link.

        Args:
            particle: Current state of the data to build on (it will be mutated).

        Returns:
            The particle with the mutated data of all the chain links starting
            this link.
        """
        if self.next:
            return self.next.build_on(particle)
        else:
            return particle
