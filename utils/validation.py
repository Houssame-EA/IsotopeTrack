from abc import ABC, abstractmethod
from typing import Self


class ValidationInfos:
    """This class contains information collected by validation classes"""

    def __init__(self,
                 messages: list[str] | None = None,
                 errors: list[str] | None = None):
        self.messages: list[str] = messages or []
        self.errors: list[str] = errors or []

    def has_errors(self) -> bool:
        """
        Returns: `True` if there's errors and `False` if there's no errors
        """
        return (self.errors is not None
                and len(self.errors) > 0)

    def has_messages(self) -> bool:
        """
        Returns: `True` if there's messages and `False` if there's no messages
        """
        return (self.messages is not None
                and len(self.messages) > 0)

    def merge(self, other: Self) -> Self:
        """
        Merges another `ValidationInfos` with the current one.
        Args:
            other (ValidationInfos): The other `ValidationInfos` to be merged
        Returns:
            The caller `ValidationInfos` with the merged data (no copy).
        """
        if not isinstance(other, ValidationInfos):
            return self
        self.messages = self.messages + other.messages
        self.errors = self.errors + other.errors
        return self

    def add_identifier(self, identifier: str):
        """
        Adds an identifier at the beginning of messages and errors.

        Examples:
            `identifier` = "Core":

            * Messages: "Core: message..."
            * Errors: "Core: error..."

        Args:
            identifier: String that we want to prefix to the messages.

        Returns:
            `self` for fluid programming.
        """
        self.messages = [f"{identifier}: {message}" for message in self.messages]
        self.errors = [f"{identifier}: {error}" for error in self.errors]
        return self

    def __repr__(self):
        return f"<{self.__module__}.{self.__class__.__name__} errors={self.errors} messages={self.messages}>"


class IValidation(ABC):
    """
    Validation interface. Classes using this interface must implement a
    `validate` method that clean up and check for class integrity.
    """

    @abstractmethod
    def validate(self) -> ValidationInfos:
        """
        Cleanup (strip, reformat, etc.) and validation of all fields.

        Returns: `ValidationInfos` that lists all invalid fields in `errors`
        (`list[str]`) and list of all cleanups as `messages`
        (`list[str]`).
        """
        pass


class ValidationErrorException(RuntimeError):
    """Custom error for failed validations."""
    def __init__(self, validation_infos:ValidationInfos, *args):
        super().__init__(*args)
        self.validation_infos = validation_infos

    def __str__(self):
        return (f"Validation Error: the following errors where raised: "
                f"{', '.join(self.validation_infos.errors)}")

    def __repr__(self):
        return f"<{self.__module__}.{self.__class__} validation_infos={self.validation_infos}, args={self.args}>"
