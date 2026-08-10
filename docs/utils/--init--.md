# `__init__.py`

Non-visual utility modules for IsotopeTrack.

This package holds pure-logic helpers with no Qt-widget dependencies:
versioning, isobaric-interference math, export-unit definitions, and
dilution/concentration calculations. UI code lives in ``tools`` and
``widget``; keeping the logic here makes it easy to test and reuse without
constructing the GUI.

---
