"""Formatted text for text panels: paragraphs, bold runs and check lists.

A text panel's words are wrapped to the width of the panel itself, measured
with the font the figure uses, so a long legend never runs past the edge of
the figure. The markup is small enough to type by hand:

* a new line starts a new paragraph, an empty line leaves a gap;
* ``**words**`` are set in bold;
* a line starting with ``✓``, ``✗`` or ``–`` is a check: the mark is drawn in
  green, red or grey and the text hangs beside it;
* isotope labels such as ``206Pb`` get a superscript mass number when the
  figure writes isotopes that way.

:func:`layout` works out the lines, :func:`height_in` the room they need and
:func:`draw` puts them on an axes. Nothing here depends on Qt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

MARK_COLORS = {'✓': '#15803d', '✗': '#b91c1c', '–': '#6b7280'}
"""Colour of each check mark: passed, failed, undecided."""

LINE_SPACING = 1.3
"""Line height as a multiple of the font size."""

PARAGRAPH_GAP = 0.45
"""Space between paragraphs, in font sizes."""

CHECK_GAP = 0.12
"""Space between consecutive check lines, in font sizes."""

INDENT = 1.45
"""Indent of a check's text past its mark, in font sizes."""

PAD = 0.6
"""Space kept clear around the block, in font sizes."""

FIT = 0.97
"""Share of the width the measured words may fill, leaving room for hinting."""

_BOLD = re.compile(r'\*\*(.+?)\*\*')
_ISOTOPE = re.compile(r'(?<![\w.$])(\d{1,3})([A-Z][a-z]?)(?![a-z$])')


@dataclass
class Segment:
    """Words drawn in one go.

    Attributes:
        x: Left edge in points from the block's left edge.
        text: The words.
        bold: Whether they are set in bold.
        color: Their colour, or an empty string for the figure's ink.
    """

    x: float
    text: str
    bold: bool = False
    color: str = ''


@dataclass
class Line:
    """One wrapped line.

    Attributes:
        baseline: Distance of the baseline below the block's top, in points.
        segments: What the line holds, left to right.
    """

    baseline: float
    segments: list = field(default_factory=list)


def _family_key(family) -> tuple:
    """A font family as a hashable tuple."""
    if family is None:
        import matplotlib
        family = matplotlib.rcParams['font.family']
    return (family,) if isinstance(family, str) else tuple(family)


@lru_cache(maxsize=20000)
def _measure(word: str, size: float, bold: bool, family: tuple) -> float:
    """Width of *word* in points."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import text_to_path
    prop = FontProperties(family=list(family), size=size, weight='bold' if bold else 'normal')
    math = word.count('$') >= 2 and word.count('$') % 2 == 0
    try:
        return float(text_to_path.get_text_width_height_descent(word, prop, ismath=math)[0])
    except Exception:
        return 0.5 * size * len(word)


def _space(size: float, bold: bool, family: tuple) -> float:
    """Width of the space between two words, in points."""
    gap = _measure('a a', size, bold, family) - 2 * _measure('a', size, bold, family)
    return gap if gap > 0 else 0.25 * size


def with_isotopes(text: str, known=None) -> str:
    """Write isotope labels in *text* with a superscript mass number.

    Args:
        text: Plain text; text already holding mathtext is left alone.
        known: The isotope labels to raise, such as the ones a particle
            table holds. Every label-shaped word is raised when omitted.
    """
    if '$' in text:
        return text
    if known is None:
        return _ISOTOPE.sub(r'$^{\1}$\2', text)
    known = set(known)
    return _ISOTOPE.sub(
        lambda m: f'$^{{{m.group(1)}}}${m.group(2)}' if m.group(0) in known else m.group(0), text)


def paragraphs(text: str) -> list[tuple[str, list[tuple[str, bool]]]]:
    """Split text into paragraphs of bold and plain runs.

    Returns:
        ``(mark, runs)`` per paragraph: *mark* is a check mark or an empty
        string, *runs* are ``(words, bold)`` pairs. An empty paragraph has
        no runs and stands for a gap.
    """
    out = []
    for raw in str(text or '').replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        mark = ''
        if line[:1] in MARK_COLORS and line[1:2] in ('', ' '):
            mark, line = line[0], line[1:].strip()
        runs = []
        pos = 0
        for m in _BOLD.finditer(line):
            if m.start() > pos:
                runs.append((line[pos:m.start()], False))
            runs.append((m.group(1), True))
            pos = m.end()
        if pos < len(line):
            runs.append((line[pos:], False))
        out.append((mark, runs))
    return out


def layout(text: str, width_pt: float, size: float, family=None,
           isotopes: bool = False, known=None) -> tuple[list[Line], float]:
    """Wrap *text* to a width.

    Args:
        text: The text with its markup.
        width_pt: Room for the block, in points, padding included.
        size: Font size in points.
        family: Font family or families; the current matplotlib font when omitted.
        isotopes: Whether isotope labels get a superscript mass number.
        known: The isotope labels to raise; every label-shaped word when omitted.

    Returns:
        ``(lines, height)``: the wrapped lines and the height the block
        needs in points, padding included.
    """
    fam = _family_key(family)
    pad = PAD * size
    room = max(4 * size, (width_pt - 2 * pad) * FIT)
    step = LINE_SPACING * size
    lines: list[Line] = []
    y = pad
    previous = None
    for mark, runs in paragraphs(text):
        if not runs and not mark:
            y += 0.6 * step
            previous = None
            continue
        if previous is not None:
            y += (CHECK_GAP if mark and previous else PARAGRAPH_GAP) * size
        left = INDENT * size if mark else 0.0
        words = []
        for chunk, bold in runs:
            for w in chunk.split():
                words.append((with_isotopes(w, known) if isotopes else w, bold))
        line = Line(y + 0.8 * size)
        if mark:
            line.segments.append(Segment(0.0, mark, True, MARK_COLORS[mark]))
        x = left
        current = None
        for word, bold in words:
            gap = _space(size, bold, fam) if x > left else 0.0
            joined = current is not None and current.bold == bold
            if joined:
                end = current.x + _measure(f'{current.text} {word}', size, bold, fam)
            else:
                end = x + gap + _measure(word, size, bold, fam)
            if x > left and end > room:
                lines.append(line)
                y += step
                line = Line(y + 0.8 * size)
                x, gap, current, joined = left, 0.0, None, False
                end = x + _measure(word, size, bold, fam)
            if joined:
                current.text += ' ' + word
            else:
                current = Segment(x + gap, word, bold)
                line.segments.append(current)
            x = end
        lines.append(line)
        y += step
        previous = bool(mark)
    return lines, y + pad


def height_in(text: str, width_in: float, size: float, family=None,
              isotopes: bool = False) -> float:
    """Height in inches that *text* needs when wrapped to *width_in* inches."""
    return layout(text, width_in * 72.0, size, family, isotopes)[1] / 72.0


def draw(ax, text: str, size: float | None = None, isotopes: bool = False,
         color: str | None = None, known=None) -> list:
    """Draw *text* on *ax*, wrapped to its width, from the top-left corner.

    Args:
        ax: The axes holding the block; its frame is left as it is.
        text: The text with its markup.
        size: Font size in points; the figure's font size when omitted.
        isotopes: Whether isotope labels get a superscript mass number.
        color: Colour of the words; the figure's text colour when omitted.
        known: The isotope labels to raise; every label-shaped word when omitted.

    Returns:
        The text artists drawn.
    """
    import matplotlib
    fig = ax.figure
    size = float(size or matplotlib.rcParams['font.size'])
    box = ax.get_position()
    width = box.width * fig.get_figwidth() * 72.0
    height = max(1.0, box.height * fig.get_figheight() * 72.0)
    lines, _total = layout(text, width, size, None, isotopes, known)
    pad = PAD * size
    artists = []
    for line in lines:
        for seg in line.segments:
            artists.append(ax.text(
                (pad + seg.x) / max(width, 1.0), 1.0 - line.baseline / height, seg.text,
                transform=ax.transAxes, ha='left', va='baseline', fontsize=size,
                fontweight='bold' if seg.bold else 'normal',
                color=seg.color or color or matplotlib.rcParams['text.color']))
    return artists
