"""Text panels: wrapping to the panel width, bold runs, check lists and isotope labels."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from results.figure_builder.core import richtext
from results.figure_builder.core.engine import render
from results.figure_builder.core.expressions import ParticleTable
from results.figure_builder.core.spec import default_spec, make_panel

LONG = "The quick brown fox jumps over the lazy dog and keeps running. " * 12


def table():
    """A small particle table with two isotopes of one element and one of another."""
    parts = []
    for i in range(60):
        el = {"206Pb": 10.0 + i, "56Fe": 5.0 + i}
        if i % 2:
            el["207Pb"] = 9.0 + i
        parts.append({"source_sample": "S1", "elements": el, "start_time": i * 1e-3})
    return ParticleTable.from_input({"type": "sample_data", "sample_name": "S1",
                                     "particle_data": parts})


def drawn(text, rect=(0.0, 0.0, 0.5, 1.0), size=10, **figure):
    """Render one text panel and return its axes after a draw."""
    spec = default_spec()
    spec["figure"].update(figure)
    spec["panels"] = [make_panel(rect=list(rect), kind="text", text=text, text_size=size)]
    fig = Figure()
    canvas = FigureCanvasAgg(fig)
    report = render(fig, spec, table())
    assert not report.errors
    canvas.draw()
    return fig.axes[0]


def test_paragraphs_split_marks_and_bold_runs():
    """New lines start paragraphs, ** marks bold, a leading mark makes a check."""
    got = richtext.paragraphs("**Title.** plain words\n\n✓ passed **well**\n✗ failed\n– open")
    assert got[0] == ("", [("Title.", True), (" plain words", False)])
    assert got[1] == ("", [])
    assert got[2] == ("✓", [("passed ", False), ("well", True)])
    assert [m for m, _r in got[3:]] == ["✗", "–"]


def test_unclosed_bold_is_left_as_typed():
    """A lone ** is not markup."""
    assert richtext.paragraphs("2 ** 3 is eight") == [("", [("2 ** 3 is eight", False)])]


def test_dash_inside_a_sentence_is_not_a_check():
    """Only a mark followed by a space opens a check."""
    assert richtext.paragraphs("–5 counts")[0][0] == ""
    assert richtext.paragraphs("– undecided")[0][0] == "–"


@pytest.mark.parametrize("width_in", [2.0, 4.0, 9.0])
def test_lines_fit_the_width_and_narrower_blocks_are_taller(width_in):
    """No wrapped line is wider than its room, and less room means more lines."""
    lines, height = richtext.layout(LONG, width_in * 72, 10, "DejaVu Sans")
    room = width_in * 72 - 2 * richtext.PAD * 10
    for line in lines:
        last = line.segments[-1]
        assert last.x + richtext._measure(last.text, 10, last.bold, ("DejaVu Sans",)) <= room
    wider = richtext.layout(LONG, (width_in + 2) * 72, 10, "DejaVu Sans")
    assert len(wider[0]) < len(lines) and wider[1] < height
    assert richtext.height_in(LONG, width_in, 10, "DejaVu Sans") == pytest.approx(height / 72)


def test_text_panel_wraps_inside_its_own_width():
    """A long paragraph in a half-width panel never crosses the panel's right edge."""
    ax = drawn(LONG)
    box = ax.get_window_extent()
    assert len(ax.texts) > 6
    assert max(t.get_window_extent().x1 for t in ax.texts) <= box.x1 + 1
    assert min(t.get_window_extent().x0 for t in ax.texts) >= box.x0


def test_check_marks_take_their_colour_and_text_hangs_beside_them():
    """Passed is green, failed red, undecided grey; wrapped check text stays indented."""
    ax = drawn("✓ " + LONG + "\n✗ no\n– maybe")
    colors = {t.get_text(): t.get_color() for t in ax.texts if t.get_text() in richtext.MARK_COLORS}
    assert colors == richtext.MARK_COLORS
    mark = next(t for t in ax.texts if t.get_text() == "✓")
    words = [t for t in ax.texts if t.get_text() not in richtext.MARK_COLORS]
    first_check = [t for t in words if t.get_text().startswith(("The", "quick", "fox", "dog", "and"))]
    assert all(t.get_position()[0] > mark.get_position()[0] for t in first_check)


def test_bold_runs_are_drawn_bold_on_the_same_line():
    """A bold run and the plain words after it share a baseline."""
    ax = drawn("**Conclusion.** The ratio holds.")
    bold, plain = ax.texts[0], ax.texts[1]
    assert bold.get_text() == "Conclusion." and bold.get_fontweight() == "bold"
    assert plain.get_fontweight() == "normal" and plain.get_position()[0] > bold.get_position()[0]
    assert bold.get_position()[1] == pytest.approx(plain.get_position()[1])


def test_isotopes_follow_the_figure_label_style():
    """Mass numbers are raised when the figure writes isotopes that way, and only then."""
    raised = " ".join(t.get_text() for t in drawn("206Pb/207Pb in 95% of 300 particles").texts)
    assert "$^{206}$Pb/$^{207}$Pb" in raised and "95%" in raised and "300" in raised
    plain = " ".join(t.get_text() for t in drawn("206Pb/207Pb", label_style="raw").texts)
    assert "$" not in plain


def test_empty_text_panel_draws_nothing():
    """A text panel with no words is simply blank."""
    assert len(drawn("").texts) == 0


def test_combination_names_an_element_once():
    """Two isotopes of one element make one name in a combination label."""
    from results.figure_builder.charts.matrices import combination_keys
    t = table()
    keys, _values = combination_keys(t, ["206Pb", "207Pb", "56Fe"], np.ones(len(t), dtype=bool))
    assert set(keys) == {"Pb + Fe"}
