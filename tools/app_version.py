"""
tools/app_version.py — single source of truth for the running app's version.

This value is kept in sync automatically by version.py (the bump script).
Other modules should import from here rather than hard-coding a version:

    from tools.app_version import __version__
"""

__version__ = "1.0.7"