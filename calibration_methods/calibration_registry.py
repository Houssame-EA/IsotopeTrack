"""Single source of truth for IsotopeTrack's calibration methods.

There are two families:

* **Transport-rate methods.** Each has a *display label* — shown in the UI and
  stored in saved projects (e.g. ``"Liquid weight"``) — and a *signal name* —
  the string the calibration window emits to
  ``MainWindow.handle_calibration_result`` (e.g. ``"Weight Method"``). These two
  naming schemes were previously duplicated, by hand, across ~13 modules.
* **Ionic calibration.** A single method, :data:`IONIC`.

Centralising the names, their mapping, and their order here means adding a
transport-rate method is a single :func:`register_transport` call (plus wiring
the method's widget in ``calibration_methods/TE.py``), instead of editing string
literals in many files.

The module imports nothing heavy (no PySide6), so the name data is unit-testable
without a display server — see ``tests/test_calibration_registry.py``.
"""
from __future__ import annotations


class TransportMethod:
    """One transport-rate calibration method.

    Args:
        label: Display name, also the value stored in saved projects
            (e.g. ``"Liquid weight"``).
        signal_name: Name emitted to ``handle_calibration_result``
            (e.g. ``"Weight Method"``).
    """

    def __init__(self, label, signal_name):
        self.label = label
        self.signal_name = signal_name

    def __repr__(self):
        return f"TransportMethod({self.label!r} -> {self.signal_name!r})"


_TRANSPORT = []


def register_transport(method):
    """Register a :class:`TransportMethod` (returns it)."""
    _TRANSPORT.append(method)
    return method


# Order matches the historic default list ["Liquid weight", "Number based",
# "Mass based"] and the historic _METHOD_SIGNAL_MAP in calibration_methods/TE.py.
register_transport(TransportMethod("Liquid weight", "Weight Method"))
register_transport(TransportMethod("Number based", "Particle Method"))
register_transport(TransportMethod("Mass based", "Mass Method"))


#: The ionic calibration method name (stored/emitted verbatim).
IONIC = "Ionic Calibration"


def transport_methods():
    """All transport methods in registration order."""
    return list(_TRANSPORT)


def default_transport_labels():
    """Ordered display labels, e.g. ``['Liquid weight', 'Number based', 'Mass based']``."""
    return [m.label for m in _TRANSPORT]


def transport_signal_names():
    """Signal names the calibration window emits, e.g. ``['Weight Method', ...]``."""
    return [m.signal_name for m in _TRANSPORT]


def label_to_signal_map():
    """Display label -> signal name (the old ``_METHOD_SIGNAL_MAP``)."""
    return {m.label: m.signal_name for m in _TRANSPORT}


def is_ionic(name):
    """True if ``name`` is the ionic calibration method."""
    return name == IONIC


def is_transport_signal(name):
    """True if ``name`` is one of the transport-rate *signal* names."""
    return name in transport_signal_names()
