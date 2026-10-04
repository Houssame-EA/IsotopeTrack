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


# --------------------------------------------------------------------------- #
# ParticleFilterDialog._apply_to_all: group-overwrite confirmation. Requires
# Qt (instantiates the real dialog), unlike the pure-function tests above.
# --------------------------------------------------------------------------- #

def _single_with_isotope_meta(name, n=3, iso="60Ni"):
    """Like _single, but with full isotope metadata (symbol/mass) so
    ParticleFilterDialog._load_pane's periodic-table lookup doesn't choke —
    the pure-function tests above never exercise that path, so _single
    doesn't need it, but instantiating the real dialog does."""
    parts = [{"elements": {iso: float(i + 1)}, "source_sample": name}
             for i in range(n)]
    return {"type": "sample_data", "sample_name": name, "particle_data": parts,
            "data": {name: {}},
            "selected_isotopes": [{"label": iso, "symbol": "Ni", "mass": 60}],
            "total_particles": n, "concentration_meta": {name: {}},
            "parent_window": None}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def filter_dialog(qapp):
    """A real ParticleFilterDialog with 3 single samples (S1, S2, S3),
    merge_singles off so custom groups take effect."""
    def _make(groups=None):
        upstreams = [_single_with_isotope_meta(n) for n in ("S1", "S2", "S3")]
        return pf.ParticleFilterDialog(
            None, upstreams, merge_singles=False, sample_groups=groups)
    return _make


@pytest.fixture
def mock_group_overwrite_box(monkeypatch):
    """Patch QMessageBox.exec/clickedButton to auto-answer the group-
    overwrite confirmation without a real event loop. `answer['proceed']`
    controls which button `clickedButton()` reports; `answer['shown']`
    records whether exec() was actually called."""
    from PySide6.QtWidgets import QMessageBox
    answer = {"proceed": True, "shown": False}

    def _exec(self):
        answer["shown"] = True
        return 0

    def _clicked(self):
        target = "Overwrite" if answer["proceed"] else "Cancel"
        for b in self.buttons():
            if b.text() == target:
                return b
        return None

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", _clicked)
    return answer


def _check(dlg, names):
    from PySide6.QtCore import Qt
    for i in range(dlg._list.count()):
        item = dlg._list.item(i)
        n = item.data(Qt.UserRole)
        item.setCheckState(Qt.Checked if n in names else Qt.Unchecked)


class TestApplyToAllGroupOverwriteWarning:
    def test_no_conflict_applies_silently(
            self, filter_dialog, mock_group_overwrite_box):
        dlg = filter_dialog()
        dlg._load_pane("S2")
        dlg._group_edit.setText("X")
        _check(dlg, ["S1", "S2"])
        dlg._apply_to_all()
        assert not mock_group_overwrite_box["shown"]
        assert dlg._groups.get("S1") == "X"
        assert dlg._groups.get("S2") == "X"

    def test_reapplying_identical_group_is_a_noop_no_dialog(
            self, filter_dialog, mock_group_overwrite_box):
        dlg = filter_dialog(groups={"S1": "X"})
        dlg._load_pane("S2")
        dlg._group_edit.setText("X")
        _check(dlg, ["S1", "S2"])
        dlg._apply_to_all()
        assert not mock_group_overwrite_box["shown"]

    def test_conflict_and_cancel_changes_nothing(
            self, filter_dialog, mock_group_overwrite_box):
        dlg = filter_dialog(groups={"S1": "OldGroup"})
        dlg._load_pane("S2")
        dlg._group_edit.setText("NewGroup")
        _check(dlg, ["S1", "S2"])
        mock_group_overwrite_box["proceed"] = False
        before = dict(dlg._groups)
        dlg._apply_to_all()
        assert mock_group_overwrite_box["shown"]
        assert dlg._groups == before          # nothing changed at all
        assert dlg._groups.get("S1") == "OldGroup"

    def test_conflict_and_confirm_overwrites(
            self, filter_dialog, mock_group_overwrite_box):
        dlg = filter_dialog(groups={"S1": "OldGroup"})
        dlg._load_pane("S2")
        dlg._group_edit.setText("NewGroup")
        _check(dlg, ["S1", "S2"])
        mock_group_overwrite_box["proceed"] = True
        dlg._apply_to_all()
        assert mock_group_overwrite_box["shown"]
        assert dlg._groups.get("S1") == "NewGroup"
        assert dlg._groups.get("S2") == "NewGroup"

    def test_clearing_a_group_is_also_a_conflict(
            self, filter_dialog, mock_group_overwrite_box):
        """Setting the group field to empty (ungrouping) on a sample that
        already has a different (non-empty) group must warn too."""
        dlg = filter_dialog(groups={"S1": "OldGroup"})
        dlg._load_pane("S2")
        dlg._group_edit.setText("")
        _check(dlg, ["S1", "S2"])
        mock_group_overwrite_box["proceed"] = False
        dlg._apply_to_all()
        assert mock_group_overwrite_box["shown"]
        assert dlg._groups.get("S1") == "OldGroup"   # cancel -> untouched

    def test_current_sample_excluded_from_its_own_conflict_check(
            self, filter_dialog, mock_group_overwrite_box):
        """Editing the CURRENT sample's own group field is never itself a
        'conflict' -- only OTHER checked samples can conflict."""
        dlg = filter_dialog(groups={"S2": "OldGroup"})
        dlg._load_pane("S2")
        dlg._group_edit.setText("NewGroup")
        _check(dlg, ["S2"])
        assert dlg._group_overwrite_conflicts({"S2"}, "NewGroup") == []
        dlg._apply_to_all()
        assert not mock_group_overwrite_box["shown"]
        assert dlg._groups.get("S2") == "NewGroup"


# --------------------------------------------------------------------------- #
# Dilution-factor mismatch on merge (july22.md issue #7): detection, the
# resolution dialog, and merge_single_sources honoring a stored resolution.
# A bug here either silently produces a wrong particles/mL (pre-existing
# first-member behavior) or crashes a merge outright, so the tolerance
# boundary and all three resolution paths (sample/manual/unavailable) are
# worth pinning down precisely.
# --------------------------------------------------------------------------- #

def _conc(dil, vol=2.0, te=True):
    return {"volume_ml": vol, "dilution_factor": dil, "te_available": te}


class TestDilutionFactorsConflict:
    def test_identical_factors_no_conflict(self):
        assert not pf.dilution_factors_conflict(
            [("A", _conc(10.0)), ("B", _conc(10.0))])

    def test_clearly_different_factors_conflict(self):
        assert pf.dilution_factors_conflict(
            [("A", _conc(10.0)), ("B", _conc(999.0))])

    def test_within_rel_tol_not_a_conflict(self):
        # 0.001% tolerance: comfortably inside for a large-magnitude factor.
        assert not pf.dilution_factors_conflict(
            [("A", _conc(5000.0)), ("B", _conc(5000.0 * (1 + 1e-7)))])

    def test_just_outside_rel_tol_is_a_conflict(self):
        assert pf.dilution_factors_conflict(
            [("A", _conc(5000.0)), ("B", _conc(5000.0 * (1 + 1e-4)))])

    def test_small_decimal_genuinely_different_values_conflict(self):
        assert pf.dilution_factors_conflict(
            [("A", _conc(1.001)), ("B", _conc(1.002))])

    def test_single_member_never_conflicts(self):
        assert not pf.dilution_factors_conflict([("A", _conc(10.0))])

    def test_missing_meta_defaults_to_1_0(self):
        assert not pf.dilution_factors_conflict([("A", None), ("B", _conc(1.0))])

    def test_three_way_two_same_one_different(self):
        assert pf.dilution_factors_conflict(
            [("A", _conc(10.0)), ("B", _conc(10.0)), ("C", _conc(20.0))])


class TestDilutionConflictDialog:
    def test_groups_by_tolerance_equal_value(self, qapp):
        members = [("S1", _conc(10.0)), ("S2", _conc(10.0)), ("S3", _conc(999.0))]
        dlg = pf.DilutionConflictDialog(None, "Combined", members)
        names_by_factor = {round(f, 3): names for f, names in dlg._groups}
        assert names_by_factor[10.0] == ["S1", "S2"]
        assert names_by_factor[999.0] == ["S3"]

    def test_default_resolution_picks_first_group(self, qapp):
        members = [("S1", _conc(10.0)), ("S2", _conc(999.0))]
        dlg = pf.DilutionConflictDialog(None, "Combined", members)
        res = dlg.resolution()
        assert res["choice"] == "sample"
        assert res["dilution_factor"] == pytest.approx(10.0)
        assert sorted(n for n, _f in res["conflict_values"]) == ["S1", "S2"]

    def test_unavailable_radio(self, qapp):
        members = [("S1", _conc(10.0)), ("S2", _conc(999.0))]
        dlg = pf.DilutionConflictDialog(None, "Combined", members)
        dlg._unavailable_radio.setChecked(True)
        res = dlg.resolution()
        assert res == {
            "choice": "unavailable", "dilution_factor": 0.0,
            "source_label": "unavailable (dilution mismatch)",
            "conflict_values": [("S1", 10.0), ("S2", 999.0)],
        }

    def test_manual_radio(self, qapp):
        members = [("S1", _conc(10.0)), ("S2", _conc(999.0))]
        dlg = pf.DilutionConflictDialog(None, "Combined", members)
        dlg._custom_radio.setChecked(True)
        dlg._custom_spin.setValue(42.5)
        res = dlg.resolution()
        assert res["choice"] == "manual"
        assert res["dilution_factor"] == pytest.approx(42.5)


class TestResolveDilutionConflict:
    def test_no_conflict_returns_none_no_dialog(self, qapp, monkeypatch):
        called = []
        monkeypatch.setattr(pf.QDialog, "exec", lambda self: called.append(1) or pf.QDialog.Accepted)
        result = pf.resolve_dilution_conflict(
            None, "G", [("A", _conc(5.0)), ("B", _conc(5.0))])
        assert result is None
        assert called == []

    def test_conflict_and_accept_returns_dict(self, qapp, monkeypatch):
        monkeypatch.setattr(pf.QDialog, "exec", lambda self: pf.QDialog.Accepted)
        result = pf.resolve_dilution_conflict(
            None, "G", [("A", _conc(10.0)), ("B", _conc(20.0))])
        assert isinstance(result, dict)
        assert set(result) >= {"choice", "dilution_factor", "source_label",
                               "conflict_values"}

    def test_conflict_and_cancel_returns_false(self, qapp, monkeypatch):
        monkeypatch.setattr(pf.QDialog, "exec", lambda self: pf.QDialog.Rejected)
        result = pf.resolve_dilution_conflict(
            None, "G", [("A", _conc(10.0)), ("B", _conc(20.0))])
        assert result is False


class TestMergeSingleSourcesDilution:
    def _source(self, name, n, dil, vol=2.0):
        parts = [{"elements": {"60Ni": 1.0}, "source_sample": name}
                for _ in range(n)]
        return {"name": name, "origin": "single", "particles": parts,
                "total": n, "sample_data": None, "conc": _conc(dil, vol),
                "isotopes": [{"label": "60Ni"}], "parent_window": None}

    def test_no_resolution_uses_first_member_legacy_behavior(self):
        merged = pf.merge_single_sources(
            [self._source("A", 3, 10.0), self._source("B", 3, 20.0)], "Combined")
        assert merged["conc"]["dilution_factor"] == pytest.approx(10.0)
        assert "dilution_mismatch" not in merged["conc"]
        assert merged["conc"]["volume_ml"] == pytest.approx(4.0)

    def test_sample_resolution_overrides_first_member(self):
        res = {"choice": "sample", "dilution_factor": 20.0,
              "source_label": "B (20x)",
              "conflict_values": [("A", 10.0), ("B", 20.0)]}
        merged = pf.merge_single_sources(
            [self._source("A", 3, 10.0), self._source("B", 3, 20.0)],
            "Combined", res)
        assert merged["conc"]["dilution_factor"] == pytest.approx(20.0)
        assert merged["conc"]["dilution_mismatch"] is True
        assert merged["conc"]["dilution_choice"] == "sample"
        assert merged["conc"]["dilution_source_label"] == "B (20x)"

    def test_unavailable_resolution_zeroes_factor(self):
        res = {"choice": "unavailable", "dilution_factor": 0.0,
              "source_label": "unavailable (dilution mismatch)",
              "conflict_values": [("A", 10.0), ("B", 20.0)]}
        merged = pf.merge_single_sources(
            [self._source("A", 3, 10.0), self._source("B", 3, 20.0)],
            "Combined", res)
        assert merged["conc"]["dilution_factor"] == 0.0
        assert merged["conc"]["dilution_choice"] == "unavailable"

    def test_particle_composition_unaffected_by_dilution_path(self):
        """Per-particle representations (counts, mass, moles) must be
        byte-identical regardless of which dilution path was taken --
        dilution factor only ever feeds particles/mL."""
        sources = [self._source("A", 3, 10.0), self._source("B", 3, 20.0)]
        m1 = pf.merge_single_sources(sources, "Combined")
        m2 = pf.merge_single_sources(sources, "Combined",
                                     {"choice": "manual", "dilution_factor": 1.0,
                                      "source_label": "x", "conflict_values": []})
        assert m1["particles"] == m2["particles"]
        assert len(m1["particles"]) == 6
