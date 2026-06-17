# -*- coding: utf-8 -*-
"""Round-trip tests for the project I/O core in save_export/.

Saving a project converts the per-particle data into a compact columnar form
(`_particles_to_columnar`) and loading reconstructs it (`_columnar_to_particles`).
If that pair is not a faithful round-trip, users silently lose or corrupt data
on save/load. We also test the numpy->JSON conversion used when writing
session/summary files.

These functions are pure (no GUI, no disk), so the whole save/load contract can
be verified in memory.
"""
import json

import numpy as np

from save_export.fast_project_io import (
    _particles_to_columnar,
    _columnar_to_particles,
)
from save_export.ionic_session import convert_numpy_types, NumpyEncoder


def roundtrip(particles):
    return _columnar_to_particles(_particles_to_columnar(particles))


# --------------------------------------------------------------------------- #
# columnar round-trip
# --------------------------------------------------------------------------- #
class TestParticleRoundTrip:
    def _particle(self):
        return {
            "start_time": 1.5, "end_time": 2.5,
            "left_idx": 10, "right_idx": 20,
            "max_height": 100.0, "total_counts": 500.0,
            "SNR": 5.0, "threshold": 3.0, "background": 1.0,
            "element_count": 2,
            "elements": {"56Fe": 10.0, "107Ag": 5.0},
            "totals": {"mass_fg": 12.0},
        }

    def test_single_particle_is_identical(self):
        p = self._particle()
        assert roundtrip([p]) == [p]

    def test_integer_fields_stay_int(self):
        p = self._particle()
        out = roundtrip([p])[0]
        assert isinstance(out["left_idx"], int)
        assert isinstance(out["right_idx"], int)
        assert isinstance(out["element_count"], int)

    def test_empty_list(self):
        assert roundtrip([]) == []

    def test_multiple_particles_with_different_elements(self):
        p1 = {"elements": {"56Fe": 10.0}, "max_height": 50.0}
        p2 = {"elements": {"107Ag": 5.0}, "max_height": 70.0}
        out = roundtrip([p1, p2])
        assert out[0]["elements"] == {"56Fe": 10.0}
        assert out[1]["elements"] == {"107Ag": 5.0}
        assert out[0]["max_height"] == 50.0 and out[1]["max_height"] == 70.0

    def test_custom_keys_preserved_via_extras(self):
        p = {"elements": {"56Fe": 1.0}, "cluster_id": "A", "flagged": True}
        out = roundtrip([p])[0]
        assert out["cluster_id"] == "A"
        assert out["flagged"] is True

    def test_private_keys_are_dropped(self):
        # Keys starting with '_' are intentionally not persisted.
        p = {"elements": {"56Fe": 1.0}, "_cache": [1, 2, 3]}
        assert "_cache" not in roundtrip([p])[0]


# --------------------------------------------------------------------------- #
# numpy -> native conversion for JSON
# --------------------------------------------------------------------------- #
class TestConvertNumpyTypes:
    def test_scalars(self):
        assert convert_numpy_types(np.int64(5)) == 5
        assert isinstance(convert_numpy_types(np.int64(5)), int)
        assert convert_numpy_types(np.float64(2.5)) == 2.5
        assert isinstance(convert_numpy_types(np.float64(2.5)), float)
        assert convert_numpy_types(np.bool_(True)) is True

    def test_array_becomes_list(self):
        assert convert_numpy_types(np.array([1, 2, 3])) == [1, 2, 3]

    def test_nested_structures(self):
        obj = {"a": np.int64(1), "b": [np.float64(2.0), {"c": np.array([3, 4])}]}
        assert convert_numpy_types(obj) == {"a": 1, "b": [2.0, {"c": [3, 4]}]}

    def test_plain_python_passthrough(self):
        obj = {"x": 1, "y": "str", "z": [1.0, 2.0]}
        assert convert_numpy_types(obj) == obj

    def test_result_is_json_serializable(self):
        obj = {"a": np.int64(1), "b": np.array([1.5, 2.5])}
        # Should not raise after conversion.
        json.dumps(convert_numpy_types(obj))


class TestNumpyEncoder:
    def test_encoder_handles_numpy(self):
        obj = {"i": np.int64(7), "f": np.float64(1.5), "arr": np.array([1, 2])}
        decoded = json.loads(json.dumps(obj, cls=NumpyEncoder))
        assert decoded == {"i": 7, "f": 1.5, "arr": [1, 2]}
