"""Detection limits of each element, read from the main window's calibration.

The Figure Builder and Insights mark detection limits on their axes. These
helpers read them exactly as the main window's calibration table computes
them, for any sample, not only the one selected when calibrating.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def isotope_keys(parent_window, labels) -> dict[str, str]:
    """Map isotope labels such as ``"56Fe"`` to the main window's keys such as ``"Fe-55.9349"``.

    Args:
        parent_window: Main window exposing ``selected_isotopes`` and
            ``get_formatted_label``.
        labels: Labels to resolve.

    Returns:
        The labels that could be matched, with their keys.
    """
    available = getattr(parent_window, "selected_isotopes", None)
    if not isinstance(available, dict):
        return {}
    formatter = getattr(parent_window, "get_formatted_label", None)
    wanted = set(labels or ())
    out: dict[str, str] = {}
    for symbol, masses in available.items():
        for mass in masses or ():
            try:
                key = f"{symbol}-{float(mass):.4f}"
            except (TypeError, ValueError):
                continue
            label = key
            if callable(formatter):
                try:
                    label = formatter(key) or key
                except Exception:
                    _log.debug("Label lookup failed for %s", key)
            if label in wanted:
                out[label] = key
    return out


def _mean_value(value) -> float | None:
    """Mean of a stored number or time series, or ``None`` when it is not usable."""
    import numpy as np
    try:
        out = float(np.mean(value))
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _conversion_factors(parent_window) -> dict[str, float]:
    """Counts-per-femtogram factors the main window uses to turn counts into mass.

    They come from the ionic calibration slope of each isotope's preferred
    method and the average transport rate, exactly as the particle masses
    were computed.
    """
    build = getattr(parent_window, "_build_element_conversion_cache", None)
    if not callable(build):
        return {}
    try:
        cache = build()
    except Exception:
        _log.debug("Could not read the calibration conversion factors")
        return {}
    return {label: entry["conversion_factor"] for label, entry in (cache or {}).items()
            if isinstance(entry, dict) and entry.get("conversion_factor")}


def detection_limits(parent_window, samples, labels) -> dict[str, dict[str, dict[str, float]]]:
    """Read each element's detection limits per sample, as the calibration reports them.

    * Counts: the net detection limit ``LOD_MDL`` that peak detection stored
      for the sample and isotope (threshold minus background, averaged over
      the run when it is time-resolved). Particle counts are background
      subtracted, so this is the limit on the same scale as the plotted
      counts.
    * Mass: the MDL in fg, that net limit divided by the calibration's
      counts-per-femtogram factor, the same formula and factor the main
      window uses for its calibration table and for every particle's mass.
      Where no factor is available, the MDL stored in ``element_limits`` is
      used instead.
    * Size: the SDL in nm, the diameter of a sphere of the pure element with
      that mass, using the same element density as the particle sizes.

    Args:
        parent_window: Main window holding ``element_thresholds``,
            ``element_limits`` and the calibration.
        samples: Samples to read.
        labels: Isotope labels to resolve, such as ``"56Fe"``.

    Returns:
        ``{label: {"counts" | "mass" | "d": {sample: value}}}`` holding only
        the limits that could be found.
    """
    import numpy as np
    thresholds = getattr(parent_window, "element_thresholds", None)
    stored_limits = getattr(parent_window, "element_limits", None)
    if not isinstance(thresholds, dict) or not labels:
        return {}
    stored_limits = stored_limits if isinstance(stored_limits, dict) else {}
    keys = isotope_keys(parent_window, labels)
    factors = _conversion_factors(parent_window)
    table = getattr(parent_window, "periodic_table_info", None)
    to_diameter = getattr(parent_window, "mass_to_diameter", None)
    out: dict[str, dict[str, dict[str, float]]] = {}
    for label, key in keys.items():
        found: dict[str, dict[str, float]] = {}
        density = None
        if table is not None and hasattr(table, "get_density_by_element"):
            try:
                density = table.get_density_by_element(str(key).split("-")[0])
            except Exception:
                density = None
        for sample in samples:
            entry = (thresholds.get(sample) or {}).get(key)
            net = None
            if isinstance(entry, dict):
                net = _mean_value(entry.get("LOD_MDL"))
                if not net:
                    threshold = _mean_value(entry.get("threshold", 0)) or 0.0
                    background = _mean_value(entry.get("background", 0)) or 0.0
                    net = max(0.0, threshold - background)
            if net and net > 0:
                found.setdefault("counts", {})[sample] = net
            mdl = None
            factor = factors.get(label)
            if net and factor and factor > 0:
                mdl = net / factor
            else:
                saved = (stored_limits.get(sample) or {}).get(key)
                if isinstance(saved, dict):
                    mdl = _mean_value(saved.get("MDL"))
            if mdl and mdl > 0:
                found.setdefault("mass", {})[sample] = mdl
                if density and density > 0 and callable(to_diameter):
                    sdl = to_diameter(mdl, density)
                    if sdl and np.isfinite(sdl) and sdl > 0:
                        found.setdefault("d", {})[sample] = float(sdl)
        if found:
            out[label] = found
    return out


def attach_limits(table, parent_window) -> None:
    """Give a particle table the calibrated detection limits of its samples.

    Pooled groups (summed replicates) carry each particle's
    ``original_sample``, so every group is linked to the samples it was built
    from and uses their limits.

    Sets ``table.detection_limits`` (see :func:`detection_limits`) and
    ``table.sample_members``, table sample name to the original samples.
    """
    members: dict[str, set] = {}
    single = getattr(table, "_single_sample", None)
    for p in getattr(table, "particles", None) or ():
        shown = p.get("source_sample") or single or "Sample"
        members.setdefault(shown, set()).add(p.get("original_sample") or shown)
    table.sample_members = {k: sorted(v) for k, v in members.items()}
    originals = sorted({s for v in members.values() for s in v})
    try:
        table.detection_limits = detection_limits(parent_window, originals, list(table.labels))
    except Exception:
        _log.debug("Could not read detection limits for the figure")
        table.detection_limits = {}


def group_limit(table, prefix: str, label: str, mask=None) -> float | None:
    """Highest calibrated limit of *label* among the samples of the masked particles.

    The highest is the level above which every one of those samples detects
    the element, so it is the safe value for a pooled group.

    Args:
        table: A table that went through :func:`attach_limits`.
        prefix: ``"counts"``, ``"mass"`` or ``"d"``.
        label: Isotope label.
        mask: Particles to consider; all when ``None``.

    Returns:
        The limit, or ``None`` when no sample of those particles has one.
    """
    import numpy as np
    per_sample = ((getattr(table, "detection_limits", None) or {}).get(label) or {}).get(prefix) or {}
    if not per_sample or not len(table):
        return None
    shown = table.column("sample")
    if mask is not None:
        shown = shown[np.asarray(mask, dtype=bool)]
    members = getattr(table, "sample_members", None) or {}
    values = [per_sample[o] for s in set(shown.tolist()) for o in members.get(s, [s])
              if o in per_sample]
    return max(values) if values else None
