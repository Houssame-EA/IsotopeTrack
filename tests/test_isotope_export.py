"""The Isotopic Ratio node's CSV export: one row per plotted particle, its own values."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results import results_isotope as ri


@pytest.fixture(scope="module")
def app():
    """The running QApplication, created if needed."""
    return QApplication.instance() or QApplication([])


def particles(n, sample, seed):
    """Particles where some lack Mg, so the plot drops them, and a few very large ones."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        si = float(rng.poisson(rng.lognormal(np.log(80), 0.6))) + 1
        mg = 0.0 if i % 7 == 0 else float(rng.poisson(si * 0.4)) + 1
        if i % 11 == 0:
            si = 50000.0
        c = {"24Mg": mg, "28Si": si, "27Al": float(i)}
        out.append({"elements": c, "element_mass_fg": {k: v / 10 for k, v in c.items()},
                    "source_sample": sample, "original_sample": sample})
    return out


def dialog(app, parts, names, data_type):
    """An Isotopic Ratio window on *parts*, plotting Mg/Si against Si."""
    node = ri.IsotopicRatioPlotNode()
    node.config.update({"element1": "24Mg", "element2": "28Si", "x_axis_element": "28Si",
                        "data_type_display": data_type, "log_x": True, "log_y": True})
    if len(names) > 1:
        node.input_data = {"type": "multiple_sample_data", "sample_names": names,
                           "particle_data": parts,
                           "selected_isotopes": [{"label": k} for k in ("24Mg", "28Si", "27Al")]}
    else:
        node.input_data = {"type": "sample_data", "sample_name": names[0], "particle_data": parts,
                           "selected_isotopes": [{"label": k} for k in ("24Mg", "28Si", "27Al")]}
    return ri.IsotopicRatioDisplayDialog(node)


@pytest.mark.parametrize("names", [["S1"], ["S1", "S2"]])
def test_each_row_is_one_particle(app, names):
    """The ratio, X and isotope columns of a row all come from the same particle."""
    parts = [p for k, n in enumerate(names) for p in particles(300, n, k)]
    dlg = dialog(app, parts, names, "Counts")
    df = dlg._build_csv_data()
    assert df is not None and len(df) > 0
    assert len(df) < len(parts)
    ratio = df["24Mg/28Si (corrected)"].to_numpy()
    assert np.allclose(ratio, df["24Mg (Counts)"] / df["28Si (Counts)"])
    assert list(df.columns).count("28Si (Counts)") == 1
    assert (df["24Mg (Counts)"] > 0).all()
    if len(names) > 1:
        assert set(df["Sample"]) == set(names)


def test_mass_rows_keep_count_ratios(app):
    """In mass the ratio is still from counts, and the mass columns are that particle's."""
    parts = particles(300, "S1", 3)
    dlg = dialog(app, parts, ["S1"], "Element Mass (fg)")
    df = dlg._build_csv_data()
    assert df is not None and len(df) > 0
    mass_cols = [c for c in df.columns if c.endswith("(Element Mass (fg))")]
    assert "27Al (Element Mass (fg))" in mass_cols
    by_al = {p["element_mass_fg"]["27Al"]: p["elements"] for p in parts}
    for _, row in df.iterrows():
        counts = by_al[row["27Al (Element Mass (fg))"]]
        assert row["24Mg/28Si (corrected)"] == pytest.approx(counts["24Mg"] / counts["28Si"])
