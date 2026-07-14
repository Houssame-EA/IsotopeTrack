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
