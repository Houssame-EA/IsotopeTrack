"""Tests for resolving an isotope to the channel that carries it.

A batch does not have to be uniform. Instrument software often writes one file
per element, so each sample holds a different single channel. Looking an
isotope up against the sample on screen instead of the sample being processed
therefore returns a mass that sample does not have, and every sample except the
open one silently produces no peaks.
"""
from __future__ import annotations

import pytest


class LookupHost:
    """Minimal stand-in exposing the lookup under test.

    The real method lives on ``MainWindow``, which cannot be imported without a
    full Qt application and the whole analysis stack, so the behaviour is
    mirrored here and kept in step by :func:`test_matches_the_shipped_source`.
    """

    ISOTOPE_MATCH_TOLERANCE = 0.5

    def __init__(self, data=None):
        """Store the channels of the sample currently on screen.

        Args:
            data (dict | None): Mass to signal for the open sample.
        """
        self.data = data or {}

    def find_closest_isotope(self, target_mass, data=None, tolerance=None):
        """Return the channel carrying one isotope, or None.

        Args:
            target_mass (float): Isotope mass being looked for.
            data (dict | None): Channels to search, or None for the open sample.
            tolerance (float | None): Largest accepted difference in amu.

        Returns:
            float | None: The matching mass key, or None when there is none.
        """
        source = self.data if data is None else data
        if not source:
            return None
        limit = self.ISOTOPE_MATCH_TOLERANCE if tolerance is None else tolerance
        closest = min(source.keys(), key=lambda x: abs(x - target_mass))
        if abs(closest - target_mass) > limit:
            return None
        return closest


ONE_ELEMENT_PER_FILE = {
    "Sample1_1": {47.94795: [1.0]},
    "Sample1_2": {51.94051: [1.0]},
    "Sample1_8": {74.92160: [1.0]},
    "Sample1_9": {110.90418: [1.0]},
    "Sample1_12": {196.96656: [1.0]},
}
SELECTED = [47.94795, 51.94051, 74.92160, 110.90418, 196.96656]


class TestPerSampleLookup:
    """Resolving against the right sample."""

    def test_finds_the_channel_in_the_given_sample(self):
        """Each sample resolves its own single channel."""
        host = LookupHost(ONE_ELEMENT_PER_FILE["Sample1_9"])
        for name, data in ONE_ELEMENT_PER_FILE.items():
            mass = next(iter(data))
            assert host.find_closest_isotope(mass, data) == mass, name

    def test_every_sample_keeps_its_element(self):
        """A one-element-per-file batch resolves one element in every sample.

        Before the fix only the open sample resolved anything, because every
        lookup went to its channels.
        """
        host = LookupHost(ONE_ELEMENT_PER_FILE["Sample1_9"])
        for name, data in ONE_ELEMENT_PER_FILE.items():
            found = [iso for iso in SELECTED
                     if host.find_closest_isotope(iso, data) in data]
            assert found == [next(iter(data))], name

    def test_the_open_sample_is_used_when_none_is_given(self):
        """Omitting the sample keeps the old, current-sample behaviour."""
        host = LookupHost({110.90418: [1.0]})
        assert host.find_closest_isotope(110.90418) == 110.90418

    def test_an_absent_isotope_returns_nothing(self):
        """A mass that is not present does not bind to the nearest other one.

        Taking the nearest key unconditionally is what let arsenic resolve to
        a cadmium channel, which then failed a membership test further down and
        removed the element with no message.
        """
        host = LookupHost()
        assert host.find_closest_isotope(74.9216, {110.90418: [1.0]}) is None

    def test_an_empty_sample_returns_nothing(self):
        """A sample with no channels resolves nothing rather than raising."""
        host = LookupHost()
        assert host.find_closest_isotope(74.9216, {}) is None

    @pytest.mark.parametrize("target,present", [
        (63.0, 62.9296),
        (208.0, 207.97604),
        (48.0, 47.94795),
    ])
    def test_a_nominal_mass_still_matches_its_isotope(self, target, present):
        """Rounded masses continue to find the measured channel."""
        host = LookupHost()
        assert host.find_closest_isotope(target, {present: [1.0]}) == present

    def test_the_tolerance_can_be_widened(self):
        """Callers that want the old unconditional nearest can ask for it."""
        host = LookupHost()
        assert host.find_closest_isotope(
            74.9216, {110.90418: [1.0]}, tolerance=1e9) == 110.90418


class TestSourceStaysInStep:
    """The stand-in above must keep matching the shipped implementation."""

    def test_matches_the_shipped_source(self):
        """The real method takes a sample and applies a tolerance."""
        import pathlib
        source = pathlib.Path(__file__).resolve().parents[1] / "mainwindow.py"
        text = source.read_text(encoding="utf-8")
        assert "def find_closest_isotope(self, target_mass, data=None," in text
        assert "ISOTOPE_MATCH_TOLERANCE" in text

    def test_per_sample_callers_pass_their_sample(self):
        """The detection paths look the isotope up in the sample they process."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        peaks = (root / "processing" / "peak_detection.py").read_text(
            encoding="utf-8")
        assert "find_closest_isotope(\n                            isotope, local_data)" in peaks
        assert "find_closest_isotope(\n                    isotope, local_data)" in peaks
