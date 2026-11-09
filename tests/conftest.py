# -*- coding: utf-8 -*-
"""Shared pytest configuration for the IsotopeTrack test suite.

This module makes the test suite runnable headlessly:

* It puts the repository root on ``sys.path`` so ``import processing.*``,
  ``import tools.*`` etc. resolve without installing the package.
* It forces Qt into the "offscreen" platform plugin so modules that import
  PySide6 at import time (most of the codebase) load without a display server.
  This is what lets the suite run in CI.

Run the suite with::

    pip install -r requirements-test.txt
    pytest
"""
from __future__ import annotations

import os
import pathlib
import sys

# Force Qt offscreen BEFORE any PySide6 import happens anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the repository importable (tests live in <repo>/tests).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest


@pytest.fixture(autouse=True)
def _base_units(monkeypatch):
    """Run every test in the base units (fg, fmol, nm, ppb).

    The units chosen in the app are kept in the user's settings, so without
    this a test could see pg on a machine where someone picked pg.
    """
    import utils.unit as unit_mod
    monkeypatch.setattr(unit_mod, "save_units", lambda u: None)
    monkeypatch.setattr(unit_mod.units, "_current", unit_mod.ExportUnits())
