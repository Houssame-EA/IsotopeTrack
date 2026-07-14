# -*- coding: utf-8 -*-
"""Particle Classifier canvas node — Stage 2 (registration + connectivity).

Stage 2 scope per ``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §14: canvas
registration, hard-blocked connectivity restrictions, node registry entries,
and a minimal placeholder node item. No dialog UI, no expression wiring, no
output relabeling yet — those are later stages (§14.3-5). Double-clicking the
node currently does nothing beyond what the base ``WorkflowNode.configure``
no-op provides.

Connectivity (design §2):
    Upstream:   Particle Filter, Single Sample, Multiple Sample only.
    Downstream: any Visualization-category node except Clustering,
                AI Data Assistant, and Dashboard.
Invalid link attempts must be hard-blocked at the canvas level (the link
cannot be drawn) with an explicit error dialog — see
``validate_classifier_link`` and its wiring into
``EnhancedCanvasScene.add_link`` in ``widget/canvas_widgets.py``.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, Signal

import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_node")

NODE_TYPE = "particle_classifier"

#: Upstream node types this node accepts a link from (design §2).
ALLOWED_UPSTREAM_TYPES = frozenset({
    "particle_filter", "sample_selector", "multiple_sample_selector",
})

#: Downstream node types explicitly excluded even though they are
#: Visualization-category (design §2, §12).
EXCLUDED_DOWNSTREAM_TYPES = frozenset({
    "clustering_plot", "ai_assistant", "dashboard",
})


def is_allowed_upstream(node_type: str) -> bool:
    """Whether a node type may feed data into a Particle Classifier node.

    Args:
        node_type (str): The candidate upstream node's ``node_type`` string.

    Returns:
        bool: True if the connection is permitted.
    """
    return node_type in ALLOWED_UPSTREAM_TYPES


def is_allowed_downstream(node_type: str, viz_node_types) -> bool:
    """Whether a node type may receive data from a Particle Classifier node.

    Args:
        node_type (str): The candidate downstream node's ``node_type``
            string.
        viz_node_types (Iterable[str]): The full set of Visualization-
            category node type strings known to the canvas (the category
            boundary is defined by palette placement, not a runtime field
            on the node class — see design §2/Stage-2 research notes).

    Returns:
        bool: True if the connection is permitted.
    """
    if node_type in EXCLUDED_DOWNSTREAM_TYPES:
        return False
    return node_type in viz_node_types


class ParticleClassifierNode(QObject):
    """Placeholder Particle Classifier workflow node (Stage 2).

    Duck-types the attributes ``WorkflowNode``/``NodeItem`` expect, matching
    the pattern used by :class:`tools.particle_filter.ParticleFilterNode`.
    Holds no classification state yet; that arrives in Stage 3 (per-sample
    definitions UI) and Stage 4 (output relabeling).
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Particle Classifier"
        self.node_type = NODE_TYPE
        self.parent_window = parent_window
        self.position = QPointF(0, 0)
        self._has_input = True
        self._has_output = True
        self.input_channels = ["input"]
        self.output_channels = ["output"]
        self.input_data = None
        self.scene_ref = None

    def set_position(self, pos):
        """Update the node position and notify the canvas item."""
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        """Receive pushed upstream data (Stage 2: stored only, not used)."""
        self.input_data = input_data
        self.configuration_changed.emit()

    def get_output_data(self):
        """Stage 2 placeholder: passes upstream data through unmodified.

        Real relabeling logic (matched/unclassified/pass-through particles)
        is implemented in Stage 4.

        Returns:
            dict | None: The single upstream dict, or None if unconnected.
        """
        scene = self.scene_ref
        if scene is not None:
            try:
                for lk in getattr(scene, 'workflow_links', []):
                    if lk.sink_node is self:
                        data = lk.get_data()
                        if data:
                            return data
            except Exception:
                _itk_log.exception("Handled exception in get_output_data")
        return self.input_data

    def configure(self, parent_window):
        """Stage 2: no dialog yet (Stage 3 adds the LHS/RHS UI)."""
        return False


def build_particle_classifier_node_item():
    """Create the ParticleClassifierNodeItem class bound to canvas widgets.

    Imported lazily so this module never imports ``widget.canvas_widgets``
    at module level, avoiding a circular import — same pattern as
    :func:`tools.particle_filter.build_particle_filter_node_item`.

    Returns:
        type: The ParticleClassifierNodeItem class.
    """
    from widget.canvas_widgets import NodeItem, DS

    class ParticleClassifierNodeItem(NodeItem):
        """Minimal placeholder icon node item for the Particle Classifier."""

        def __init__(self, wf, pw=None):
            super().__init__(wf)
            self.parent_window = pw
            wf.configuration_changed.connect(self.update)

        def paint(self, painter, option, widget=None):
            self.paint_icon_node(
                painter, (DS.INDIGO, "#4F46E5"),
                "fa6s.tags", "Classifier",
            )

        def configure_node(self):
            """Stage 2: no dialog yet (Stage 3 adds the LHS/RHS UI)."""
            pass

    return ParticleClassifierNodeItem
