"""Tests for the Qt-free SIA statistics and history helpers."""

import datetime as dt
import json
import math

import numpy as np
import pytest

from loading import sia_stats as ss


def _per_mass(sigmas, n=5000, start=20.0, step=15.0):
    """Build a per-mass dict with the given sigma values."""
    out = {}
    for i, s in enumerate(sigmas):
        m = start + i * step
        out[f"{m:.4f}"] = {"mass": m, "sigma": s, "num_points": n,
                           "mean_signal": 100.0, "std_signal": 50.0}
    return out


def test_standard_error_formula():
    assert ss.sigma_standard_error(0.5, 51) == pytest.approx(0.5 / math.sqrt(100))
    assert math.isnan(ss.sigma_standard_error(0.5, 1))


def test_robust_mask_finds_single_outlier():
    vals = [0.48, 0.49, 0.50, 0.47, 0.51, 0.49, 0.75]
    mask = ss.robust_outlier_mask(vals)
    assert mask.tolist() == [False] * 6 + [True]


def test_robust_mask_not_masked_by_outlier_itself():
    vals = [0.50, 0.51, 0.49, 0.50, 0.52, 0.48, 0.50, 0.95, 0.97]
    mean, sd = np.mean(vals), np.std(vals)
    assert not np.any(np.abs(np.array(vals) - mean) > 2 * sd)
    assert ss.robust_outlier_mask(vals).sum() == 2


def test_robust_mask_small_or_flat_input():
    assert not ss.robust_outlier_mask([0.5, 0.9, 0.4]).any()
    assert not ss.robust_outlier_mask([0.5] * 6 + [0.9]).any()


def test_weighted_mean_prefers_heavy_points():
    mean, _ = ss.weighted_mean_sd([0.4, 0.6], [9.0, 1.0])
    assert mean == pytest.approx(0.42)


def test_linear_trend_recovers_slope():
    x = np.linspace(20, 220, 12)
    y = 0.45 + 0.0005 * x
    fit = ss.linear_trend(x, y + np.random.default_rng(0).normal(0, 1e-4, x.size))
    assert fit["slope"] == pytest.approx(0.0005, rel=0.05)
    assert fit["p_value"] < 1e-6


def test_linear_trend_flat_is_not_significant():
    rng = np.random.default_rng(3)
    x = np.linspace(20, 220, 15)
    fit = ss.linear_trend(x, 0.5 + rng.normal(0, 0.02, x.size))
    assert fit["p_value"] > 0.01


def test_linear_trend_needs_three_points():
    assert ss.linear_trend([1, 2], [1, 2]) is None


def test_summary_and_effective_sigma():
    pm = _per_mass([0.48, 0.49, 0.50, 0.47, 0.51, 0.49, 0.75])
    s_all = ss.summarize_per_mass(pm, False)
    s_ex = ss.summarize_per_mass(pm, True)
    assert s_all["n_outliers"] == 1 and not s_all["excluded"]
    assert s_ex["excluded"]
    assert s_ex["mean"] == pytest.approx(np.mean([0.48, 0.49, 0.50, 0.47, 0.51, 0.49]))
    assert s_all["mean"] > s_ex["mean"]
    assert ss.effective_sigma(0.47, pm, False) == (0.47, "overall")
    sig, src = ss.effective_sigma(0.47, pm, True)
    assert src == "per_mass_mean" and sig == pytest.approx(s_ex["mean"])


def test_effective_sigma_without_outliers_stays_overall():
    pm = _per_mass([0.48, 0.49, 0.50, 0.47, 0.51])
    assert ss.effective_sigma(0.47, pm, True) == (0.47, "overall")


def test_summary_weights_by_events():
    pm = _per_mass([0.40, 0.60, 0.50, 0.50])
    pm[next(iter(pm))]["num_points"] = 100000
    s = ss.summarize_per_mass(pm)
    assert s["mean"] < 0.5


def test_nearest_per_mass_tolerance():
    pm = _per_mass([0.5, 0.6])
    assert ss.nearest_per_mass(pm, 21.0)[1]["sigma"] == 0.5
    assert ss.nearest_per_mass(pm, 26.0) is None


ELEMENTS = [
    {"symbol": "Fe", "isotopes": [{"mass": 55.93494, "abundance": 91.754, "label": "56Fe"},
                                  {"mass": 57.93328, "abundance": 0.2819, "label": "58Fe"}]},
    {"symbol": "Ni", "isotopes": [{"mass": 57.93534, "abundance": 68.077, "label": "58Ni"}]},
    {"symbol": "Tc", "isotopes": [{"mass": 97.9, "abundance": 0, "label": "98Tc"}]},
]


def test_isotopes_at_mass_orders_by_abundance_and_preference():
    idx = ss.isotope_index(ELEMENTS)
    assert ss.isotopes_at_mass(idx, 57.9353) == ["58Ni", "58Fe"]
    assert ss.isotopes_at_mass(idx, 57.9353, preferred=["58Fe"]) == ["58Fe", "58Ni"]
    assert ss.isotopes_at_mass(idx, 97.9) == []


def test_mass_label_uses_superscripts():
    idx = ss.isotope_index(ELEMENTS)
    assert ss.mass_label(55.9349, idx) == "⁵⁶Fe"
    assert ss.mass_label(57.9353, idx) == "⁵⁸Ni / ⁵⁸Fe"
    assert ss.mass_label(12.0, idx) == "m/z 12"


def test_parse_datetime():
    assert ss.parse_datetime("2026-10-01T09:12:00Z") == dt.datetime(2026, 10, 1, 9, 12)
    assert ss.parse_datetime("Unknown") is None
    assert ss.parse_datetime(None) is None


def _info(sigma, area=100.0, when="2026-10-01T09:00:00Z", name="SIA"):
    return {"sample_name": name, "instrument_type": "Nu Vitesse", "calculated_sigma": sigma,
            "mean_signal": 110.0, "average_single_ion_area": area,
            "analysis_datetime": when, "num_valid_masses": 3}


def test_history_entry_fields():
    e = ss.history_entry(_info(0.47), _per_mass([0.5]), "/data/a")
    assert e["date"] == "2026-10-01T09:00:00" and e["date_from_file"]
    assert e["per_mass_sigma"] == {"20.0000": 0.5}
    json.dumps(e)


def test_history_entry_without_file_date_uses_now():
    now = dt.datetime(2026, 10, 13, 8, 0, 0)
    e = ss.history_entry(_info(0.47, when="Unknown"), {}, "/x.h5", now=now)
    assert e["date"] == "2026-10-13T08:00:00" and not e["date_from_file"]


def test_control_limits_and_classify():
    assert ss.control_limits([0.5, 0.5]) is None
    lim = ss.control_limits([0.48, 0.50, 0.52, 0.49, 0.51])
    assert ss.classify(0.50, lim) == "ok"
    assert ss.classify(lim["mean"] + 2.5 * lim["sd"], lim) == "warn"
    assert ss.classify(lim["mean"] - 3.5 * lim["sd"], lim) == "action"
    assert ss.classify(0.5, None) == "unknown"


def test_history_store_record_replace_remove(tmp_path):
    path = str(tmp_path / "h" / "sia_history.json")
    h = ss.SIAHistory(path)
    for i, s in enumerate([0.48, 0.50, 0.52, 0.49]):
        r = h.record(ss.history_entry(_info(s, when=f"2026-09-0{i + 1}T09:00:00"), {}, f"/d/{i}"))
    assert r["n_previous"] == 3 and r["sigma"] == "ok"
    r = h.record(ss.history_entry(_info(0.90, when="2026-10-01T09:00:00"), {}, "/d/new"))
    assert r["sigma"] == "action"
    again = h.record(ss.history_entry(_info(0.90, when="2026-10-01T09:00:00"), {}, "/d/new"))
    assert again["n_previous"] == 4
    h2 = ss.SIAHistory(path)
    assert len(h2.entries) == 5
    assert [e["date"][:10] for e in h2.sorted_entries()][0] == "2026-09-01"
    key = h2.sorted_entries()[-1]["key"]
    assert h2.remove(key) and not h2.remove(key)
    assert len(ss.SIAHistory(path).entries) == 4


def test_history_survives_corrupt_file(tmp_path):
    p = tmp_path / "sia_history.json"
    p.write_text("{not json")
    assert ss.SIAHistory(str(p)).entries == []
