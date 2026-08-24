# -*- coding: utf-8 -*-
"""Tests for calibration_methods/calibration_registry.py.

The registry centralises calibration method names that were previously
duplicated as string literals across ~13 modules. These tests pin the registry
to the exact values those literals used, so the centralisation is behaviour-
preserving (no display name, stored project name, or emitted signal name
changes). The module imports nothing heavy, so this runs without PySide6.
"""
from calibration_methods import calibration_registry as reg


def test_default_transport_labels_unchanged():
    # These are the values stored in saved projects and shown in the UI.
    assert reg.default_transport_labels() == [
        "Liquid weight", "Number based", "Mass based",
    ]


def test_label_to_signal_map_matches_old_METHOD_SIGNAL_MAP():
    # Was hard-coded as _METHOD_SIGNAL_MAP in calibration_methods/TE.py.
    assert reg.label_to_signal_map() == {
        "Liquid weight": "Weight Method",
        "Number based": "Particle Method",
        "Mass based": "Mass Method",
    }


def test_transport_signal_names_unchanged():
    # Was the membership list in MainWindow.handle_calibration_result.
    assert reg.transport_signal_names() == [
        "Weight Method", "Particle Method", "Mass Method",
    ]


def test_ionic_constant():
    assert reg.IONIC == "Ionic Calibration"
    assert reg.is_ionic("Ionic Calibration") is True
    assert reg.is_ionic("Weight Method") is False


def test_is_transport_signal():
    for name in ["Weight Method", "Particle Method", "Mass Method"]:
        assert reg.is_transport_signal(name) is True
    for name in ["Ionic Calibration", "Liquid weight", "nope", ""]:
        assert reg.is_transport_signal(name) is False


def test_label_and_signal_lists_align():
    methods = reg.transport_methods()
    assert [m.label for m in methods] == reg.default_transport_labels()
    assert [m.signal_name for m in methods] == reg.transport_signal_names()
