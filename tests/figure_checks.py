"""Shared checks that a Figure Builder design draws, for the tests."""

from __future__ import annotations


def table_for(data: dict | None, data_type: str):
    """The particle table a design draws from.

    Args:
        data: A particle stream as the canvas passes it between nodes.
        data_type: The design's default quantity, e.g. ``"Counts"``.
    """
    from results.figure_builder.core.expressions import ParticleTable
    return ParticleTable.from_input(data, data_type or "Counts")


def render_problems(spec: dict, table) -> list[str]:
    """Draw *spec* off-screen and report what failed.

    Args:
        spec: A Figure Builder design.
        table: Particle table to draw from.

    Returns:
        One message per panel that could not be drawn, plus any bad variable;
        empty when the whole figure drew.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render

    fig = Figure()
    FigureCanvasAgg(fig)
    try:
        report = render(fig, spec, table)
    except Exception as exc:
        return [f"The figure could not be drawn: {exc}"]
    order = {p["id"]: i for i, p in enumerate(spec.get("panels", []))}
    out = [f"panel {order.get(pid, 0) + 1}: {msg}" for pid, msg in report.errors.items()]
    out += [f"variable {name}: {msg}" for name, msg in report.variable_errors.items()]
    return out
