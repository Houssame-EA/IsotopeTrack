# -*- coding: utf-8 -*-
"""Particle Classifier canvas node.

Stage 2 (canvas registration, hard-blocked connectivity restrictions, node
registry entries, minimal placeholder node item) and Stage 3 (real
definition storage + the configuration dialog from
``tools/particle_classifier_dialog.py``) per
``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §14. Output relabeling (§7) is
still Stage 4 — ``get_output_data`` still passes upstream data through
unmodified.

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

import uuid

from PySide6.QtCore import QObject, QPointF, Signal
from PySide6.QtWidgets import QDialog

import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.particle_classifier_node")


def _ual():
    """Return the UserActionLogger, or None if logging isn't ready.

    Returns:
        object: The user action logger instance, or None.
    """
    try:
        from tools.logging_utils import logging_manager
        return logging_manager.get_user_action_logger()
    except Exception:
        _itk_log.exception("Handled exception in _ual")
        return None

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


#: Default neutral-gray color for the "Unclassified" bucket (design §6).
DEFAULT_UNCLASSIFIED_COLOR = "#9CA3AF"


def new_definition_id():
    """Generate a fresh, stable identity for a classifier definition.

    Returns:
        str: A UUID4 hex string.
    """
    return uuid.uuid4().hex


class ParticleClassifierNode(QObject):
    """Particle Classifier workflow node.

    Duck-types the attributes ``WorkflowNode``/``NodeItem`` expect, matching
    the pattern used by :class:`tools.particle_filter.ParticleFilterNode`.

    Holds the node-wide state edited by ``ParticleClassifierDialog``
    (``tools/particle_classifier_dialog.py``):

    - ``definitions``: one flat, priority-ordered list of definition dicts,
      each scoped to exactly one sample (design §4). Shape::

          {
              'id': str,                     # stable identity, see new_definition_id()
              'target_sample': str,          # sample name this definition is scoped to
              'expression_text': str,        # raw user text, re-parsed on load
              'match_mode': 'partial' | 'exact',
              'group_name': str | None,      # None = auto-named bucket of one
              'color': str | None,           # None = auto-derived from group/palette
          }

      List order *is* the priority order (index 0 = highest priority).
    - ``groups``: ``{group_name: color_hex}`` registry (design §4).
    - ``overlap_mode``: ``'double_count'`` (default) or ``'priority'`` — a
      single node-wide choice, not per-pair (design §5).
    - ``unmatched_mode``: ``'unclassified'`` (default), ``'discard'``, or
      ``'passthrough'`` (design §6).
    - ``unclassified_color``: overridable color for the Unclassified bucket.
    - ``selected_sources``: ``None`` (all connected samples included) or a
      list of sample names — same convention as
      :attr:`tools.particle_filter.ParticleFilterNode.selected_sources`.

    Output relabeling (design §7) is Stage 4 — ``get_output_data`` still
    passes upstream data through unmodified.
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

        self.definitions = []
        self.groups = {}
        self.overlap_mode = 'double_count'
        self.unmatched_mode = 'unclassified'
        self.unclassified_color = DEFAULT_UNCLASSIFIED_COLOR
        self.selected_sources = None
        #: {group_name: "keep" | "drop_mfc"} for every multi-definition
        #: group (design §5/§7 ambiguity — see
        #: tools/particle_classifier_relabel.py's module docstring),
        #: chosen via the dialog's group-pooling warning modal.
        self.group_pooling_policies = {}
        #: Set by the dialog on Accept: True when any definition currently
        #: has a stale isotope reference. Drives the node icon's warning
        #: badge (see build_particle_classifier_node_item).
        self._has_unresolved_issues = False

    def set_position(self, pos):
        """Update the node position and notify the canvas item."""
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        """Receive pushed single-link upstream data."""
        self.input_data = input_data
        self.configuration_changed.emit()

    def _pull_upstream_all(self):
        """Fetch the upstream dict from every input link.

        Falls back to the last pushed data when the node is not (yet) part
        of a scene. Mirrors
        :meth:`tools.particle_filter.ParticleFilterNode._pull_upstream_all`.

        Returns:
            list: Non-None upstream data dicts.
        """
        out = []
        scene = self.scene_ref
        if scene is not None:
            try:
                for lk in getattr(scene, 'workflow_links', []):
                    if lk.sink_node is self:
                        out.append(lk.get_data())
            except Exception:
                _itk_log.exception("Handled exception in _pull_upstream_all")
        if not out and self.input_data is not None:
            out = [self.input_data]
        return [u for u in out if u]

    def get_output_data(self):
        """Relabel every connected sample's particles per this node's
        classifier definitions (design §7) and hand the result downstream
        with the exact same top-level shape it arrived in — this is a
        relabel-in-place operation, never a sample merge/regroup, so
        single-sample input stays single-sample, multi-sample input stays
        multi-sample with its per-sample structure intact.

        Never touches ``concentration_meta``, diameter fields, or any
        other non-composition metadata (design §2, §7) — only the
        ``particle_data`` list changes.

        Returns:
            dict | None: The relabeled output dict, or None if unconnected
                or no sample survives the ``selected_sources``/unmatched-
                mode filtering.
        """
        from tools.particle_filter import normalize_sources
        from tools.particle_classifier_relabel import (
            relabel_particles, suggested_label_colors)

        upstreams = self._pull_upstream_all()
        if not upstreams:
            return None
        data = upstreams[0]
        if data.get('type') not in ('sample_data', 'multiple_sample_data'):
            # Non-particle upstream types (shouldn't occur given the
            # canvas-level connectivity restriction, but stay defensive):
            # pass through unmodified rather than guessing.
            return data

        sources = normalize_sources([data])
        if self.selected_sources is not None:
            sources = [s for s in sources if s['name'] in self.selected_sources]
        if not sources:
            return None

        relabeled_by_sample = {}
        for s in sources:
            defs = self.definitions_for_sample(s['name'])
            relabeled_by_sample[s['name']] = relabel_particles(
                s['particles'], defs, self.groups, self.overlap_mode,
                self.unmatched_mode, self.unclassified_color,
                self.group_pooling_policies)

        label_colors = suggested_label_colors(
            self.definitions, self.groups, self.unmatched_mode,
            self.unclassified_color)

        if data.get('type') == 'sample_data':
            out = dict(data)
            out['particle_data'] = relabeled_by_sample.get(
                sources[0]['name'], [])
            out['filtered_particles'] = len(out['particle_data'])
            out['label_colors'] = label_colors
            return out

        # multiple_sample_data: preserve per-sample structure, only the
        # combined particle_data list (and its filtered count) changes.
        out = dict(data)
        combined = []
        for s in sources:
            combined.extend(relabeled_by_sample.get(s['name'], []))
        out['particle_data'] = combined
        out['filtered_particles'] = len(combined)
        out['sample_names'] = [s['name'] for s in sources]
        out['label_colors'] = label_colors
        return out

    def definitions_for_sample(self, sample_name):
        """List this node's definitions targeting one sample, in priority order.

        Args:
            sample_name (str): The sample name to filter by.

        Returns:
            list: Subset of :attr:`definitions` whose ``target_sample``
                matches, in the same relative (priority) order.
        """
        return [d for d in self.definitions
                if d.get('target_sample') == sample_name]

    def configure(self, parent_window):
        """Open the configuration dialog (double-click).

        Mirrors :meth:`tools.particle_filter.ParticleFilterNode.configure`'s
        pull-snapshot / open-dialog / read-back-on-accept shape.

        Returns:
            bool: True when the dialog was accepted.
        """
        from tools.particle_classifier_dialog import ParticleClassifierDialog
        snapshots = self._pull_upstream_all()
        dlg = ParticleClassifierDialog(
            parent_window, snapshots, self.definitions, self.groups,
            self.overlap_mode, self.unmatched_mode, self.unclassified_color,
            self.selected_sources, self.group_pooling_policies)
        if dlg.exec() == QDialog.Accepted:
            self.definitions = dlg.get_definitions()
            self.groups = dlg.get_groups()
            self.overlap_mode = dlg.get_overlap_mode()
            self.unmatched_mode = dlg.get_unmatched_mode()
            self.unclassified_color = dlg.get_unclassified_color()
            self.selected_sources = dlg.get_selected_sources()
            self.group_pooling_policies = dlg.get_group_pooling_policies()
            self._has_unresolved_issues = dlg.get_has_unresolved_issues()
            self.configuration_changed.emit()
            ual = _ual()
            if ual:
                ual.log_action(
                    'DATA_OP',
                    f'Canvas node configured: {self.summary_text()}',
                    {'node': 'ParticleClassifier',
                     'num_definitions': len(self.definitions),
                     'num_groups': len(self.groups),
                     'overlap_mode': self.overlap_mode,
                     'unmatched_mode': self.unmatched_mode,
                     'selected_sources': self.selected_sources})
            return True
        return False

    def summary_text(self):
        """Build the live summary shown under the node icon.

        Returns:
            str: e.g. "3 definitions", "No definitions".
        """
        n = len(self.definitions)
        if n == 0:
            return "No definitions"
        return f"{n} definition" + ("s" if n != 1 else "")


def build_particle_classifier_node_item():
    """Create the ParticleClassifierNodeItem class bound to canvas widgets.

    Imported lazily so this module never imports ``widget.canvas_widgets``
    at module level, avoiding a circular import — same pattern as
    :func:`tools.particle_filter.build_particle_filter_node_item`.

    Returns:
        type: The ParticleClassifierNodeItem class.
    """
    from widget.canvas_widgets import NodeItem, _StatusNodeMixin, DS

    class ParticleClassifierNodeItem(NodeItem, _StatusNodeMixin):
        """Tag icon node item for the Particle Classifier.

        Shows a live summary badge mirroring
        ``ParticleFilterNodeItem.paint``'s badge pattern
        (``tools/particle_filter.py``): a definition-count badge when
        healthy, a warning badge when any definition currently has a stale
        isotope reference or an unresolved contradiction.
        """

        def __init__(self, wf, pw=None):
            super().__init__(wf)
            self.parent_window = pw
            wf.configuration_changed.connect(self.update)
            wf.configuration_changed.connect(self._trigger)

        def paint(self, painter, option, widget=None):
            wf = self.workflow_node
            n = len(wf.definitions)
            if getattr(wf, '_has_unresolved_issues', False):
                badge, bc = "⚠", DS.WARNING
            elif n:
                badge, bc = str(n), DS.SUCCESS
            else:
                badge, bc = "", None
            self.paint_icon_node(
                painter, (DS.INDIGO, "#4F46E5"),
                "fa6s.tags", "Classifier",
                badge, bc,
            )

        def _trigger(self):
            """Push freshly relabeled output to downstream nodes on change."""
            self._run_calculation_async()

        def configure_node(self):
            """Open the classifier configuration dialog (double-click)."""
            if self.parent_window:
                self.workflow_node.configure(self.parent_window)

    return ParticleClassifierNodeItem
