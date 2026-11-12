"""Blanker windows and autoblank flags read from Nu Vitesse run files."""

import json

import pytest

from loading import nu_blanking as nb

START = [0.0405104453917104, 0.00773981241680299]
END = [-0.00858145883440464, 0.00763624356577202]
EDGES = [0.0, 572.5, 681.25, 737.5, 792.5, 995.0, 2026.25, 25650.0]


def _folder(tmp_path):
    info = {"BlankerUsed": 1, "BlMassCalStartCoef": START, "BlMassCalEndCoef": END,
            "TotalAcquisitions": 300000, "NumAccumulations1": 8, "NumAccumulations2": 1,
            "SegmentInfo": [{"Blanker1EdgeTimesNs": EDGES}]}
    (tmp_path / "run.info").write_text(json.dumps(info))
    return tmp_path


def test_fixed_windows_match_the_method_skip_ranges(tmp_path):
    b = nb.read_nu_blanking(_folder(tmp_path))
    inner = [w for w in b["fixed"] if 1 < w[0] and w[1] < 300]
    assert inner[0] == pytest.approx((27.0, 33.0), abs=0.1)
    assert inner[1] == pytest.approx((36.5, 60.0), abs=0.1)
    assert nb.windows_text(b["fixed"]) == "m/z 27.0–33.0, 36.5–59.9"


def test_mass_flags_and_autoblank_fraction():
    b = {"fixed": [(27.0, 33.0)], "auto": [(33.0, 36.5, 15000)], "total_acquisitions": 300000}
    f = nb.mass_flags([30.0, 35.0, 63.0], b)
    assert f[30.0]["blanked"] and not f[63.0]["blanked"]
    assert f[35.0]["autoblank_fraction"] == pytest.approx(0.05)
    assert nb.isotope_flag(34.97, f) is f[35.0]


def test_subtract_windows_keeps_only_the_new_part():
    assert nb.subtract_windows([(27.0, 60.0)], [(27.0, 33.0), (36.5, 60.0)]) == [(33.0, 36.5)]


def test_missing_run_info_gives_none(tmp_path):
    assert nb.read_nu_blanking(tmp_path) is None
