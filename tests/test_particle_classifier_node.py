# -*- coding: utf-8 -*-
"""Tests for the Particle Classifier node's Stage 2 connectivity rules
(tools/particle_classifier_node.py + the validate_classifier_link hook in
widget/canvas_widgets.py). A bug here would let the canvas silently wire up
a connection design §2 says must be hard-blocked, so the allow/deny boundary
is worth pinning down; the rest of the node (placeholder paint, registry
wiring) is exercised via one smoke instantiation, not exhaustively.
"""
import pytest

from tools import particle_classifier_node as pcn


# --------------------------------------------------------------------------- #
# is_allowed_upstream / is_allowed_downstream — pure logic, no Qt
# --------------------------------------------------------------------------- #
class TestUpstreamRule:
    @pytest.mark.parametrize("node_type", [
        "particle_filter", "sample_selector", "multiple_sample_selector"])
    def test_allowed_upstream_types(self, node_type):
        assert pcn.is_allowed_upstream(node_type) is True

    @pytest.mark.parametrize("node_type", [
        "histogram_plot", "batch_sample_selector", "particle_classifier", None])
    def test_disallowed_upstream_types(self, node_type):
        assert pcn.is_allowed_upstream(node_type) is False


class TestDownstreamRule:
    def test_viz_node_allowed(self):
        assert pcn.is_allowed_downstream(
            "histogram_plot", pcn_viz_types()) is True

    @pytest.mark.parametrize("node_type", [
        "clustering_plot", "ai_assistant", "dashboard"])
    def test_excluded_viz_nodes_blocked(self, node_type):
        assert pcn.is_allowed_downstream(node_type, pcn_viz_types()) is False

    def test_non_viz_node_blocked(self):
        assert pcn.is_allowed_downstream(
            "particle_filter", pcn_viz_types()) is False


def pcn_viz_types():
    return {"histogram_plot", "clustering_plot", "ai_assistant", "dashboard"}


# --------------------------------------------------------------------------- #
# validate_classifier_link — exercised through the real canvas (Qt required)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def cw(qapp, monkeypatch):
    import widget.canvas_widgets as cw
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    return cw


class TestAddLinkEnforcement:
    def test_allowed_upstream_link_is_created(self, cw):
        from tools.particle_classifier_node import ParticleClassifierNode
        from tools.particle_filter import ParticleFilterNode
        scene = cw.EnhancedCanvasScene(parent_window=None)
        pf, clf = ParticleFilterNode(), ParticleClassifierNode()
        scene.add_node(pf, cw.QPointF(0, 0))
        scene.add_node(clf, cw.QPointF(200, 0))
        assert scene.add_link(pf, "output", clf, "input") is not None

    def test_disallowed_upstream_link_is_blocked(self, cw):
        from tools.particle_classifier_node import ParticleClassifierNode
        scene = cw.EnhancedCanvasScene(parent_window=None)
        hist, clf = cw.HistogramPlotNode(), ParticleClassifierNode()
        scene.add_node(hist, cw.QPointF(0, 0))
        scene.add_node(clf, cw.QPointF(200, 0))
        assert scene.add_link(hist, "output", clf, "input") is None

    def test_excluded_downstream_link_is_blocked(self, cw):
        from tools.particle_classifier_node import ParticleClassifierNode
        scene = cw.EnhancedCanvasScene(parent_window=None)
        clf, dash = ParticleClassifierNode(), cw.DashboardNode()
        scene.add_node(clf, cw.QPointF(0, 0))
        scene.add_node(dash, cw.QPointF(200, 0))
        assert scene.add_link(clf, "output", dash, "input") is None

    def test_allowed_viz_downstream_link_is_created(self, cw):
        from tools.particle_classifier_node import ParticleClassifierNode
        scene = cw.EnhancedCanvasScene(parent_window=None)
        clf, hist = ParticleClassifierNode(), cw.HistogramPlotNode()
        scene.add_node(clf, cw.QPointF(0, 0))
        scene.add_node(hist, cw.QPointF(200, 0))
        assert scene.add_link(clf, "output", hist, "input") is not None

    def test_unrelated_link_pair_is_unaffected(self, cw):
        scene = cw.EnhancedCanvasScene(parent_window=None)
        ss, pf = cw.SampleSelectorNode(), cw.ParticleFilterNode()
        scene.add_node(ss, cw.QPointF(0, 0))
        scene.add_node(pf, cw.QPointF(200, 0))
        assert scene.add_link(ss, "output", pf, "input") is not None


# --------------------------------------------------------------------------- #
# Node registration + placeholder item — one smoke instantiation
# --------------------------------------------------------------------------- #
class TestRegistration:
    def test_registered_in_node_factories_and_item_map(self, cw):
        assert cw._NODE_FACTORIES["particle_classifier"] is \
            pcn.ParticleClassifierNode
        assert "particle_classifier" in cw._NODE_ITEM_MAP

    def test_placeholder_item_constructs_and_paints(self, cw):
        from PySide6.QtWidgets import QGraphicsScene
        from PySide6.QtGui import QPixmap, QPainter
        wf = pcn.ParticleClassifierNode()
        item = cw.ParticleClassifierNodeItem(wf)
        scene = QGraphicsScene()
        scene.addItem(item)
        pix = QPixmap(50, 50)
        pix.fill()
        painter = QPainter(pix)
        scene.render(painter)
        painter.end()
        assert wf._has_input is True
        assert wf._has_output is True


# --------------------------------------------------------------------------- #
# Node duplication carries the full classifier configuration
# --------------------------------------------------------------------------- #
class TestDuplicateNodeCopiesConfig:
    def test_duplicate_carries_definitions_and_state(self, cw):
        """Ctrl+C / right-click Duplicate must copy the classifier's full
        state, not produce a blank node -- duplicate_node() has its own
        hardcoded attribute list separate from save/load's, and every piece
        of classifier state must be present in it."""
        from tools.particle_classifier_node import (
            ParticleClassifierNode, new_definition_id)
        scene = cw.EnhancedCanvasScene(parent_window=None)
        clf = ParticleClassifierNode()
        clf.definitions = [{
            'id': new_definition_id(), 'target_sample': 'SampleA',
            'expression_text': '60Ni', 'match_mode': 'partial',
            'group_name': 'Nickel', 'color': None}]
        clf.groups = {'Nickel': '#10B981'}
        clf.overlap_mode = 'priority'
        clf.unmatched_mode = 'discard'
        clf.unclassified_color = '#123456'
        clf.group_pooling_policies = {'Mix': 'keep'}
        clf.confound_dismissals = [{'id_a': 'x', 'id_b': 'y',
                                    'expr_a': '60Ni', 'expr_b': '60Ni+107Ag'}]
        scene.add_node(clf, cw.QPointF(0, 0))

        item = scene.duplicate_node(scene.node_items[clf])
        assert item is not None
        dup = item.workflow_node
        assert dup is not clf
        assert dup.definitions == clf.definitions
        assert dup.definitions is not clf.definitions  # deep-copied
        assert dup.groups == clf.groups
        assert dup.overlap_mode == 'priority'
        assert dup.unmatched_mode == 'discard'
        assert dup.unclassified_color == '#123456'
        assert dup.group_pooling_policies == {'Mix': 'keep'}
        assert dup.confound_dismissals == clf.confound_dismissals


# --------------------------------------------------------------------------- #
# Duplicate + reconnect to a DIFFERENT upstream: stale definitions must not
# masquerade as active configuration (mirrors ParticleFilterNode's
# _incoming_names / is_active() pattern from the vlad-filter-upgrade branch).
# --------------------------------------------------------------------------- #
class TestStaleDefinitionsAfterRewire:
    def _node_with_defs(self):
        from tools.particle_classifier_node import (
            ParticleClassifierNode, new_definition_id)
        node = ParticleClassifierNode()
        node.definitions = [{
            'id': new_definition_id(), 'target_sample': 'Hello',
            'expression_text': '60Ni', 'match_mode': 'partial',
            'group_name': 'IronOre', 'color': None}]
        return node

    def test_active_definitions_empty_before_any_data(self):
        node = self._node_with_defs()
        assert node._active_definitions() == []
        assert node.summary_text() == "No definitions"

    def test_active_definitions_counts_when_sample_connected(self):
        node = self._node_with_defs()
        node.process_data({
            'type': 'sample_data', 'sample_name': 'Hello', 'data': {},
            'particle_data': [], 'selected_isotopes': [],
            'total_particles': 0, 'concentration_meta': {},
            'parent_window': None})
        assert len(node._active_definitions()) == 1
        assert node.summary_text() == "1 definition"

    def test_stale_after_rewire_to_different_sample_not_deleted(self):
        """Reconnecting to a totally different sample must NOT count the
        old definitions as active, but must NOT delete them either."""
        node = self._node_with_defs()
        node.process_data({
            'type': 'sample_data', 'sample_name': 'NewSample', 'data': {},
            'particle_data': [], 'selected_isotopes': [],
            'total_particles': 0, 'concentration_meta': {},
            'parent_window': None})
        assert node._active_definitions() == []          # inert now
        assert node.summary_text() == "No definitions"    # badge reflects that
        assert len(node.definitions) == 1                 # but NOT deleted
        assert node.definitions[0]['target_sample'] == 'Hello'

    def test_confound_checker_ignores_disconnected_sample(self, cw):
        """The actual reported bug: a duplicated-and-rewired node's
        confound warning must never reference a sample that isn't
        connected to THIS dialog session."""
        from tools.particle_classifier_dialog import ParticleClassifierDialog
        node = self._node_with_defs()
        node.definitions.append({
            'id': 'second-def', 'target_sample': 'Hello',
            'expression_text': '60Ni+107Ag', 'match_mode': 'partial',
            'group_name': 'Recycling', 'color': None})
        # Dialog opened against a snapshot for a DIFFERENT sample entirely
        # -- 'Hello' is not among the currently connected sources.
        snapshot = {
            'type': 'sample_data', 'sample_name': 'NewSample', 'data': {},
            'particle_data': [{'elements': {'56Fe': 1.0}}],
            'selected_isotopes': [{'label': '56Fe'}], 'total_particles': 1,
            'concentration_meta': {'NewSample': {}}, 'parent_window': None,
        }
        dlg = ParticleClassifierDialog(None, [snapshot], node.definitions,
                                       node.groups, node.overlap_mode,
                                       node.unmatched_mode,
                                       node.unclassified_color,
                                       node.selected_sources,
                                       node.group_pooling_policies,
                                       node.confound_dismissals)
        assert dlg._collect_active_confound_pairs() == []

    def test_real_canvas_duplicate_and_relink_end_to_end(self, cw):
        """Same scenario driven through the REAL canvas mechanics --
        scene.add_link/duplicate_node, not direct process_data() calls --
        so a real add_link's _trigger_data_flow is what refreshes
        _incoming_names, exactly like an actual user duplicating a
        configured node and connecting it to a different source."""
        from PySide6.QtCore import QObject, Signal, QPointF
        from tools.particle_classifier_node import (
            ParticleClassifierNode, new_definition_id)

        class _StubSource(QObject):
            position_changed = Signal(object)
            configuration_changed = Signal()

            def __init__(self, output):
                super().__init__()
                self.title = "Stub Source"
                self.node_type = "sample_selector"
                self.position = QPointF(0, 0)
                self._has_input, self._has_output = False, True
                self.input_channels, self.output_channels = [], ["output"]
                self._output = output
                self.selected_sample = None
                self.sum_replicates = False
                self.replicate_samples = []
                self.selected_isotopes = []

            def set_position(self, pos):
                self.position = pos

            def get_output_data(self):
                return self._output

        def multi(names, combos):
            particles = [{'elements': {iso: 1.0 for iso in c},
                         'source_sample': n}
                        for n in names for c in combos]
            return {'type': 'multiple_sample_data', 'sample_names': names,
                    'particle_data': particles, 'data': {}, 'data_types': {},
                    'selected_isotopes': [], 'total_particles': len(particles),
                    'concentration_meta': {n: {} for n in names},
                    'parent_window': None}

        scene = cw.EnhancedCanvasScene(parent_window=None)
        old_source = _StubSource(multi(['Hello', 'Sir'], [['60Ni']]))
        parent = ParticleClassifierNode()
        scene.add_node(old_source, QPointF(0, 0))
        scene.add_node(parent, QPointF(200, 0))
        assert scene.add_link(old_source, "output", parent, "input") is not None
        parent.definitions = [{
            'id': new_definition_id(), 'target_sample': 'Hello',
            'expression_text': '60Ni', 'match_mode': 'partial',
            'group_name': 'IronOre', 'color': None}]
        assert set(parent._incoming_names) == {'Hello', 'Sir'}
        assert len(parent._active_definitions()) == 1

        dup_item = scene.duplicate_node(scene.node_items[parent])
        dup = dup_item.workflow_node
        assert not any(lk.sink_node is dup for lk in scene.workflow_links)
        assert dup._active_definitions() == []

        new_source = _StubSource(multi(['NewSample'], [['56Fe']]))
        scene.add_node(new_source, QPointF(0, 300))
        assert scene.add_link(new_source, "output", dup, "input") is not None
        # process_data fired for real via _trigger_data_flow.
        assert dup._incoming_names == ['NewSample']
        assert dup._active_definitions() == []
        assert len(dup.definitions) == 1  # stale IronOre def preserved
