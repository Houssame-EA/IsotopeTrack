# -*- coding: utf-8 -*-
"""Tests for the particle-filtering logic in tools/particle_filter.py.

These functions decide which detected particles pass a user's filter (by
composition, element count, or per-element threshold). A bug here silently
changes which particles are counted and reported, so the AND/OR/EXACT logic and
the threshold gating are worth pinning down. The functions tested are pure; the
module imports Qt only for the dialog it also defines.
"""
import pytest

from tools import particle_filter as pf


# --------------------------------------------------------------------------- #
# default_filter_config / active_axes
# --------------------------------------------------------------------------- #
class TestConfigBasics:
    def test_default_config_is_fully_disabled(self):
        cfg = pf.default_filter_config()
        assert pf.active_axes(cfg) == []
        assert cfg["composition"]["enabled"] is False
        assert cfg["count"]["enabled"] is False
        assert cfg["threshold"]["enabled"] is False

    def test_active_axes_empty_config(self):
        assert pf.active_axes({}) == []
        assert pf.active_axes(None) == []

    def test_composition_needs_isotopes(self):
        cfg = pf.default_filter_config()
        cfg["composition"]["enabled"] = True
        assert "composition" not in pf.active_axes(cfg)   # no isotopes yet
        cfg["composition"]["isotopes"] = [{"label": "56Fe", "symbol": "Fe"}]
        assert "composition" in pf.active_axes(cfg)

    def test_count_axis_activates_when_enabled(self):
        cfg = pf.default_filter_config()
        cfg["count"]["enabled"] = True
        assert "count" in pf.active_axes(cfg)

    def test_threshold_needs_a_positive_value(self):
        cfg = pf.default_filter_config()
        # Threshold is a per-isotope modifier on top of Composition (see the
        # cross-box audit), so it only counts as an active axis when
        # Composition is also on — enable it here so the test exercises the
        # positive-value rule rather than the composition gate.
        cfg["composition"].update(enabled=True, isotopes=[{"symbol": "Fe"}])
        cfg["threshold"]["enabled"] = True
        cfg["threshold"]["values"] = {"56Fe": 0}
        assert "threshold" not in pf.active_axes(cfg)     # 0 doesn't count
        cfg["threshold"]["values"] = {"56Fe": 5}
        assert "threshold" in pf.active_axes(cfg)


# --------------------------------------------------------------------------- #
# summarize_config
# --------------------------------------------------------------------------- #
class TestSummarizeConfig:
    def test_inactive_says_no_filter(self):
        assert pf.summarize_config({}) == "No filter"
        assert pf.summarize_config(pf.default_filter_config()) == "No filter"

    def test_composition_and_count(self):
        cfg = pf.default_filter_config()
        cfg["composition"].update(
            enabled=True, mode="AND",
            isotopes=[{"symbol": "Fe"}, {"symbol": "Cr"}])
        cfg["count"].update(enabled=True, op="min", value=2)
        out = pf.summarize_config(cfg)
        assert "Fe·Cr | AND" in out
        assert "≥2 iso" in out

    @pytest.mark.parametrize("op,sym", [("min", "≥"), ("max", "≤"), ("exact", "=")])
    def test_count_operator_symbols(self, op, sym):
        cfg = pf.default_filter_config()
        cfg["count"].update(enabled=True, op=op, value=3)
        assert f"{sym}3 iso" in pf.summarize_config(cfg)


# --------------------------------------------------------------------------- #
# referenced_labels / stale_from_available
# --------------------------------------------------------------------------- #
class TestReferencedAndStale:
    def _cfg(self):
        cfg = pf.default_filter_config()
        cfg["composition"].update(
            enabled=True, isotopes=[{"label": "56Fe"}])
        cfg["threshold"].update(
            enabled=True, values={"52Cr": 3, "63Cu": 0})  # Cu value 0 -> ignored
        return cfg

    def test_referenced_labels(self):
        assert pf.referenced_labels(self._cfg()) == {"56Fe", "52Cr"}

    def test_referenced_empty_for_blank_config(self):
        assert pf.referenced_labels({}) == set()

    def test_stale_are_those_not_available(self):
        stale = pf.stale_from_available({"56Fe"}, self._cfg())
        assert stale == {"52Cr"}


# --------------------------------------------------------------------------- #
# detected_labels
# --------------------------------------------------------------------------- #
class TestDetectedLabels:
    def test_positive_signals_only(self):
        particle = {"elements": {"Fe": 10.0, "Cr": 0.0, "Cu": 5.0}}
        assert pf.detected_labels(particle, "elements", {}) == {"Fe", "Cu"}

    def test_threshold_in_elements_unit(self):
        particle = {"elements": {"Fe": 10.0, "Cu": 5.0}}
        # Fe must reach 20 to count; it doesn't, so only Cu (no threshold) passes.
        out = pf.detected_labels(particle, "elements", {"Fe": 20.0})
        assert out == {"Cu"}

    def test_threshold_in_mass_unit(self):
        particle = {
            "elements": {"Fe": 10.0},
            "element_mass_fg": {"Fe": 2.5},
        }
        assert pf.detected_labels(particle, "element_mass_fg", {"Fe": 2.0}) == {"Fe"}
        assert pf.detected_labels(particle, "element_mass_fg", {"Fe": 9.0}) == set()

    def test_empty_particle(self):
        assert pf.detected_labels({}, "elements", {}) == set()


# --------------------------------------------------------------------------- #
# particle_passes  (the core AND/OR/EXACT + count logic)
# --------------------------------------------------------------------------- #
class TestParticlePasses:
    def _particle(self, **elements):
        return {"elements": elements}

    def test_no_filters_passes_everything(self):
        p = self._particle(Fe=1.0)
        assert pf.particle_passes(p, set(), "AND", None, "elements", {}) is True

    def test_and_requires_all_present(self):
        p = self._particle(Fe=1.0, Cr=1.0)
        assert pf.particle_passes(p, {"Fe", "Cr"}, "AND", None, "elements", {}) is True
        assert pf.particle_passes(p, {"Fe", "Cr", "Ni"}, "AND", None, "elements", {}) is False

    def test_or_requires_any_present(self):
        p = self._particle(Fe=1.0)
        assert pf.particle_passes(p, {"Fe", "Ni"}, "OR", None, "elements", {}) is True
        assert pf.particle_passes(p, {"Ni", "Co"}, "OR", None, "elements", {}) is False

    def test_exact_requires_identical_set(self):
        p = self._particle(Fe=1.0, Cr=1.0)
        assert pf.particle_passes(p, {"Fe", "Cr"}, "EXACT", None, "elements", {}) is True
        assert pf.particle_passes(p, {"Fe"}, "EXACT", None, "elements", {}) is False

    @pytest.mark.parametrize("op,value,expected", [
        ("min", 2, True),    # 2 elements present, >= 2
        ("min", 3, False),
        ("max", 2, True),    # <= 2
        ("max", 1, False),
        ("exact", 2, True),
        ("exact", 1, False),
    ])
    def test_count_operators(self, op, value, expected):
        p = self._particle(Fe=1.0, Cr=1.0)
        result = pf.particle_passes(
            p, set(), "AND", {"op": op, "value": value}, "elements", {})
        assert result is expected


# --------------------------------------------------------------------------- #
# Sample-name handling: append-not-drop disambiguation + (filt xN) provenance
# --------------------------------------------------------------------------- #

def _single(name, n=3, iso="60Ni"):
    """A minimal single-sample upstream dict with n one-isotope particles."""
    parts = [{"elements": {iso: float(i + 1)}, "source_sample": name}
             for i in range(n)]
    return {"type": "sample_data", "sample_name": name, "particle_data": parts,
            "data": {name: {}}, "selected_isotopes": [{"label": iso}],
            "total_particles": n,
            "concentration_meta": {name: {"volume_ml": 2.0,
                                          "dilution_factor": 1.0}},
            "parent_window": None}


class TestDisambiguateName:
    def test_free_name_unchanged(self):
        assert pf._disambiguate_name("S1", set()) == "S1"

    def test_collision_appends_incrementing_number(self):
        seen = set()
        got = []
        for _ in range(3):
            nm = pf._disambiguate_name("S1", seen)
            seen.add(nm)
            got.append(nm)
        assert got == ["S1", "S1 (2)", "S1 (3)"]

    def test_literal_numbered_name_just_gets_another_suffix(self):
        assert pf._disambiguate_name("S1 (2)", {"S1 (2)"}) == "S1 (2) (2)"


class TestNormalizeSourcesAppends:
    def test_same_named_sources_are_kept_not_dropped(self):
        srcs = pf.normalize_sources([_single("S1"), _single("S1"), _single("S2")])
        assert [s["name"] for s in srcs] == ["S1", "S1 (2)", "S2"]

    def test_blank_single_sample_name_defaults_to_Sample(self):
        # _expand_upstream_entries defaults a blank single-sample name to
        # "Sample" rather than dropping it, so normalize keeps one entry.
        srcs = pf.normalize_sources([_single("")])
        assert [s["name"] for s in srcs] == ["Sample"]

    def test_resolve_and_normalize_also_appends(self):
        srcs = pf.resolve_and_normalize_sources(
            [_single("S1"), _single("S1")], {})
        assert [s["name"] for s in srcs] == ["S1", "S1 (2)"]


class TestFiltSuffix:
    def test_fresh_name_gains_x1(self):
        assert pf._bump_filt_suffix("S1") == "S1 (filt x1)"

    def test_existing_suffix_increments(self):
        assert pf._bump_filt_suffix("S1 (filt x1)") == "S1 (filt x2)"
        assert pf._bump_filt_suffix("S1 (filt x9)") == "S1 (filt x10)"

    def test_merged_name_restarts_at_x1(self):
        assert pf._bump_filt_suffix("Combined") == "Combined (filt x1)"

    def test_literal_number_then_filt(self):
        assert pf._bump_filt_suffix("S1 (2)") == "S1 (2) (filt x1)"


class TestDuplicateResolutionIgnoreDropsOne:
    """Regression: when two duplicates are identical in BOTH name and count,
    an 'ignore' resolution must drop exactly ONE (not the whole pair, which
    would emit nothing)."""

    def _entries(self):
        return pf.normalize_sources([_single("S1", n=5), _single("S1", n=5)])

    def test_ignore_drops_exactly_one_of_identical_pair(self):
        entries = [dict(e) for e in
                   (pf._expand_upstream_entries(_single("S1", n=5))
                    + pf._expand_upstream_entries(_single("S1", n=5)))]
        sig = pf._duplicate_signature(entries[0], entries[1])
        resolutions = {sig: {"action": "ignore", "target": ("S1", 5)}}
        out = pf._apply_duplicate_resolutions(entries, resolutions)
        assert len(out) == 1  # one survives, not zero

    def test_keep_separate_keeps_both_of_identical_pair(self):
        entries = (pf._expand_upstream_entries(_single("S1", n=5))
                   + pf._expand_upstream_entries(_single("S1", n=5)))
        sig = pf._duplicate_signature(entries[0], entries[1])
        resolutions = {sig: {"action": "keep_separate", "target": ("S1", 5),
                             "rename_to": "S1 copy"}}
        out = pf._apply_duplicate_resolutions(entries, resolutions)
        assert len(out) == 2
