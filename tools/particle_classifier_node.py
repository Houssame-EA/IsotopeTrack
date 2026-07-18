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
        #: ``{group_name: color}`` -- deliberately GLOBAL, shared across
        #: every sample: a group name means "this substance," and every
        #: definition assigned to it (on any sample) renders the same
        #: color everywhere, including downstream in the graphs. This was
        #: briefly made per-sample-scoped, but reverted: (1) downstream viz
        #: color-seeding is fundamentally keyed by label TEXT alone with no
        #: sample dimension, so per-sample-divergent colors could never
        #: actually render distinctly in a chart anyway -- they'd just look
        #: like a bug (the "wrong" sample's color winning); (2) the user
        #: explicitly wants same-named groups to always match across
        #: samples for consistency, since divergent colors for the same
        #: substance name is not a use case anyone wants. If two samples'
        #: definitions need visually distinct colors, give them distinct
        #: group names.
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
        #: Confound pairs the user has permanently dismissed via the
        #: aggregate confound-warning dialog's per-pair "don't warn me
        #: again" checkbox (design §5), so reopening this node's dialog
        #: doesn't re-warn about them. See
        #: ParticleClassifierDialog._confound_pair_key /
        #: get_confound_dismissals.
        self.confound_dismissals = []
        #: Sample names actually feeding this node right now, refreshed on
        #: every process_data() call. Mirrors
        #: tools.particle_filter.ParticleFilterNode._incoming_names: when a
        #: node is duplicated or its upstream link is swapped to a
        #: different source, self.definitions may still contain entries
        #: whose target_sample belonged to the OLD connection and no
        #: longer exists anywhere in the new one. Those entries are kept
        #: (never silently deleted — the user may reconnect the original
        #: source later) but must not count toward "is this node actually
        #: configured" displays (summary_text(), the node icon's badge)
        #: — see the same reasoning in ParticleFilterNode.is_active().
        self._incoming_names = []

    def set_position(self, pos):
        """Update the node position and notify the canvas item."""
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        """Receive pushed single-link upstream data."""
        self.input_data = input_data
        self._recompute_incoming_names(input_data)
        self.configuration_changed.emit()

    def _recompute_incoming_names(self, input_data):
        """Refresh the set of sample names currently feeding this node."""
        from tools.particle_filter import normalize_sources
        try:
            sources = normalize_sources([input_data]) if input_data else []
        except Exception:
            _itk_log.exception("Handled exception in _recompute_incoming_names")
            sources = []
        self._incoming_names = [s['name'] for s in sources]

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
            particles = relabeled_by_sample.get(sources[0]['name'], [])
            out['particle_data'] = particles
            out['filtered_particles'] = len(particles)
            out['label_colors'] = label_colors
            out['selected_isotopes'] = self._output_selected_isotopes(
                particles, data.get('selected_isotopes'), label_colors)
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
        out['selected_isotopes'] = self._output_selected_isotopes(
            combined, data.get('selected_isotopes'), label_colors)
        return out

    @staticmethod
    def _output_selected_isotopes(particles, upstream_selected, label_colors):
        """Rebuild ``selected_isotopes`` to name the SYNTHETIC labels the
        relabeled particles now actually carry (design §7: downstream nodes
        should see a classifier bucket "exactly like another isotope").

        Without this, the output would still advertise the upstream's raw
        isotope labels (e.g. ``56Fe``) in ``selected_isotopes`` even though
        every particle's composition dict has been relabeled to bucket
        names (e.g. ``IronOre``). Downstream nodes that key off
        ``selected_isotopes`` first rather than discovering labels from the
        particle data itself (e.g. Concentration Comparison / Correlation
        Matrix / Network Diagram via their ``_get_elements``) would then
        look up isotope names that no longer exist in the particles and
        find nothing.

        Labels are taken from the particles themselves (first-appearance
        order), so this stays correct for every unmatched-mode — including
        ``passthrough``, where unmatched particles keep their original raw
        isotope keys, which legitimately appear alongside the synthetic
        bucket labels. Each label reuses its matching upstream
        ``selected_isotopes`` entry when one exists (preserving any extra
        keys a passed-through raw isotope carried), otherwise a fresh
        ``{'label', 'color'}`` entry is synthesized.

        Args:
            particles (list): The relabeled output particle dicts.
            upstream_selected (list | None): The upstream's own
                ``selected_isotopes`` list, if any.
            label_colors (dict): ``{label: hex}`` for synthetic labels.

        Returns:
            list: ``[{'label': ..., ...}, ...]`` naming the labels the
                output particles actually carry.
        """
        upstream_by_label = {}
        for iso in (upstream_selected or []):
            lbl = iso.get('label') if isinstance(iso, dict) else str(iso)
            if lbl and lbl not in upstream_by_label:
                upstream_by_label[lbl] = iso

        out, seen = [], set()
        for p in particles:
            for label in (p.get('elements') or {}):
                if label in seen:
                    continue
                seen.add(label)
                if isinstance(upstream_by_label.get(label), dict):
                    out.append(dict(upstream_by_label[label]))
                else:
                    entry = {'label': label}
                    if label in label_colors:
                        entry['color'] = label_colors[label]
                    out.append(entry)
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
            self.selected_sources, self.group_pooling_policies,
            self.confound_dismissals)
        if dlg.exec() == QDialog.Accepted:
            self.definitions = dlg.get_definitions()
            self.groups = dlg.get_groups()
            self.overlap_mode = dlg.get_overlap_mode()
            self.unmatched_mode = dlg.get_unmatched_mode()
            self.unclassified_color = dlg.get_unclassified_color()
            self.selected_sources = dlg.get_selected_sources()
            self.group_pooling_policies = dlg.get_group_pooling_policies()
            self._has_unresolved_issues = dlg.get_has_unresolved_issues()
            self.confound_dismissals = dlg.get_confound_dismissals()
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

    def _active_definitions(self):
        """Definitions whose target_sample is actually connected right now.

        Excludes entries left over from a duplicate or a rewired upstream
        (their target_sample belongs to a connection that no longer
        exists) so they don't count toward "is this node configured"
        displays — mirrors
        :meth:`tools.particle_filter.ParticleFilterNode.is_active`. Never
        deletes anything from :attr:`definitions`; if the node is later
        reconnected back to a matching sample, those entries become active
        again automatically.

        Returns:
            list: Subset of :attr:`definitions`.
        """
        current = set(self._incoming_names)
        return [d for d in self.definitions if d.get('target_sample') in current]

    def summary_text(self):
        """Build the live summary shown under the node icon.

        Returns:
            str: e.g. "3 definitions", "No definitions" (including when
                every stored definition is left over from a duplicate/
                rewire and targets a sample that isn't connected anymore).
        """
        n = len(self._active_definitions())
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
    from widget.canvas_widgets import NodeItem, DS

    class ParticleClassifierNodeItem(NodeItem):
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

        def paint(self, painter, option, widget=None):
            wf = self.workflow_node
            n = len(wf._active_definitions())
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

        def configure_node(self):
            """Open the classifier configuration dialog (double-click).

            On Accept, pushes freshly relabeled output to every currently
            connected sink so an already-open downstream viz figure
            reflects the new configuration immediately, instead of only on
            its next unrelated redraw (design §7 "stale plot" fix).

            Deliberately NOT wired to ``configuration_changed`` (which also
            fires from ``process_data`` on every routine upstream push,
            including during project-load link restoration) — that would
            re-run this node's full downstream chain on every data arrival
            instead of only on a user-initiated reconfigure, and did cause
            a real startup hang on project load. This push only ever runs
            once, synchronously, as a direct result of this dialog's OK
            button — never automatically.
            """
            if not self.parent_window:
                return
            if not self.workflow_node.configure(self.parent_window):
                return
            s = self.scene()
            if not s:
                return
            try:
                result = self.workflow_node.get_output_data()
            except Exception:
                _itk_log.exception("Handled exception in ParticleClassifierNodeItem.configure_node")
                return
            for lk in s.workflow_links:
                if lk.source_node == self.workflow_node:
                    try:
                        if hasattr(lk.sink_node, "process_data"):
                            lk.sink_node.process_data(result)
                    except Exception:
                        _itk_log.exception("Handled exception in ParticleClassifierNodeItem.configure_node")

    return ParticleClassifierNodeItem
