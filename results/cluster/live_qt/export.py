"""PNG export for the main plot and the detail view.

Renders a widget into a ``QImage`` at a chosen scale, optionally with a
transparent background and enlarged type, then asks where to save it.
"""

from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .state import THEME


def export_name(S, what):
    """Build a suggested filename for an export.

    Args:
        S (LiveState): The view state, for the algorithm name and scale.
        what (str): Which figure, e.g. ``'plot'`` or ``'detail'``.

    Returns:
        str: A filename such as ``cluster-lab_plot_K-Means_3x.png``.
    """
    algo = re.sub(r'[^\w+-]+', '-', str(S.algo or 'plot'))
    return 'cluster-lab_%s_%s_%dx.png' % (what, algo, S.exp.scale)


def render_widget(widget, scale, transparent, font_boost=1.0):
    """Render a widget into an image at a multiple of its on-screen size.

    ``font_boost`` temporarily enlarges the widget's font so type grows
    relative to the figure rather than with it, which keeps labels readable
    once the exported image is scaled back down for a document.

    Args:
        widget (QWidget): The widget to capture.
        scale (float): Resolution multiplier.
        transparent (bool): Leave the background clear instead of filling it.
        font_boost (float): Multiplier applied to the widget's font size.

    Returns:
        QImage: The rendered image.
    """
    w = max(1, widget.width())
    h = max(1, widget.height())
    img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32)
    img.setDevicePixelRatio(scale)
    img.fill(Qt.transparent if transparent else QColor(THEME.bg))

    old_font = widget.font()
    if font_boost and font_boost != 1.0:
        f = widget.font()
        base = f.pointSizeF() if f.pointSizeF() > 0 else 10.0
        f.setPointSizeF(base * font_boost)
        widget.setFont(f)
    try:
        p = QPainter(img)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            widget.render(p, targetOffset=widget.rect().topLeft())
        finally:
            p.end()
    finally:
        if font_boost and font_boost != 1.0:
            widget.setFont(old_font)
    return img


def save_image(img, parent, suggested):
    """Ask where to put a PNG and write it.

    Args:
        img (QImage): The image to save.
        parent (QWidget | None): Dialog parent.
        suggested (str): Suggested filename.

    Returns:
        str | None: The path written, or None when cancelled or on failure.
    """
    start = os.path.join(os.path.expanduser('~'), suggested)
    path, _ = QFileDialog.getSaveFileName(parent, 'Export image', start,
                                          'PNG image (*.png)')
    if not path:
        return None
    if not path.lower().endswith('.png'):
        path += '.png'
    if not img.save(path, 'PNG'):
        QMessageBox.warning(parent, 'Export failed',
                            'Could not write %s' % path)
        return None
    return path


def export_plot(S, plot_widget, parent=None):
    """Export the main scatter at the chosen scale.

    Args:
        S (LiveState): The view state.
        plot_widget (QWidget): The scatter widget to capture.
        parent (QWidget | None): Dialog parent.

    Returns:
        str | None: The path written, or None.
    """
    if not S.data or S.data.get('empty'):
        QMessageBox.information(parent, 'Export', 'Nothing to export yet')
        return None
    img = render_widget(plot_widget, S.exp.scale, S.exp.transparent,
                        S.exp.font_boost)
    return save_image(img, parent, export_name(S, 'plot'))


def export_inset(S, inset_box, parent=None):
    """Export the detail view together with its title.

    The whole titled box is captured, so the heading and subtitle appear in
    the image without being drawn a second time.

    Args:
        S (LiveState): The view state.
        inset_box (QWidget): The titled detail box to capture.
        parent (QWidget | None): Dialog parent.

    Returns:
        str | None: The path written, or None.
    """
    fr = S.current_frame()
    d = ((fr or {}).get('extra') or {}).get('inset')
    if not d:
        QMessageBox.information(parent, 'Export', 'No detail view to export')
        return None
    img = render_widget(inset_box, S.exp.scale, S.exp.transparent,
                        S.exp.font_boost)
    return save_image(img, parent, export_name(S, 'detail'))
