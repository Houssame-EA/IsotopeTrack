"""
This module is a "temporary" way of marking methods and functions as
deprecated. It's a "temporary" solution so when it changes version the
newer method of `@warning.deprecated(message)` should be used instead.

This system is based of the following article:

* https://sqlpey.com/python/top-6-ways-to-implement-deprecation-in-python-using-decorators/
"""
import functools
import warnings
import sys

if sys.version_info.major == 3 and sys.version_info.minor >= 13:
    import logging
    logging.critical("The python version of the project has changed. Please "
                     "remove any `from utils.deprecated import deprecated` "
                     "and use `from warning import deprecated` instead.")


def deprecated(message: str):
    """
    A decorator to mark functions as deprecated. Emits a warning when the
    function is invoked.

    Args:
        message: message warning or helping to resolve the deprecation.
    """
    def _decorator(func):
        @functools.wraps(func)
        def _new_func(*args, **kwargs):
            warnings.simplefilter("default", DeprecationWarning)
            warnings.warn(
                f"Call to deprecated function {func.__name__}: {message}.",
                category=DeprecationWarning,
                stacklevel=2
            )
            warnings.simplefilter("default", DeprecationWarning)
            return func(*args, **kwargs)

        return _new_func

    return _decorator
