
from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPointF
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget, QSplitter,
)

from theme import theme as _theme

# ──────────────────────────────────────────────────────────────────────────────
# Category metadata — icon + label only; colour comes from palette
# ──────────────────────────────────────────────────────────────────────────────

_FONT = "Segoe UI"

_CAT_META: dict[str, dict] = {
    "correlation":  {"icon": "⬡", "label": "Correlation"},
    "distribution": {"icon": "▦", "label": "Distribution"},
    "clustering":   {"icon": "✦", "label": "Clustering"},
    "composition":  {"icon": "◔", "label": "Composition"},
    "isotope":      {"icon": "⚛", "label": "Isotopic Ratio"},
    "comparison":   {"icon": "⇄", "label": "Comparison"},
    "network":      {"icon": "⬡", "label": "Network"},
    "outlier":      {"icon": "↑", "label": "Outlier"},
}

@dataclass
class Suggestion:
    title: str
    reasoning: str
    category: str        
    confidence: float   
    node_type: str    
    config: dict = field(default_factory=dict)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.75: return "high"
        if self.confidence >= 0.45: return "medium"
        return "low"


# ──────────────────────────────────────────────────────────────────────────────
# Statistical helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return f if (f > 0 and not math.isnan(f)) else None
    except Exception:
        return None


def _element_matrix(particles: list[dict]) -> dict[str, np.ndarray]:
    all_els: dict[str, list] = {}
    for p in particles:
        for el in p.get("elements", {}):
            all_els.setdefault(el, [])
    for p in particles:
        els = p.get("elements", {})
        for el in all_els:
            v = _safe_float(els.get(el, 0))
            all_els[el].append(v if v is not None else 0.0)
    return {el: np.asarray(vals) for el, vals in all_els.items()}


def _det_counts(mat: dict[str, np.ndarray]) -> dict[str, int]:
    return {el: int(np.sum(v > 0)) for el, v in mat.items()}


def _pearson_log(a: np.ndarray, b: np.ndarray) -> float | None:
    mask = (a > 0) & (b > 0)
    if mask.sum() < 8: return None
    xa, xb = a[mask], b[mask]
    if xa.std() == 0 or xb.std() == 0: return None
    return float(np.corrcoef(np.log1p(xa), np.log1p(xb))[0, 1])


def _bimodality_bc(arr: np.ndarray) -> float:
    arr = arr[arr > 0]
    if len(arr) < 8: return 0.0
    n = len(arr)
    std = arr.std()
    if std == 0: return 0.0
    m3 = float(np.mean((arr - arr.mean()) ** 3)) / (std ** 3 + 1e-30)
    m4 = float(np.mean((arr - arr.mean()) ** 4)) / (std ** 4 + 1e-30)
    return (m3 ** 2 + 1) / (m4 + 3 * ((n-1)**2) / ((n-2)*(n-3) + 1e-9))


def _isotope_symbol(name: str) -> str | None:
    m = re.match(r"^\d+([A-Za-z]+)$", name.strip())
    return m.group(1) if m else None


def _group_isotopes(elements: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list] = {}
    for el in elements:
        sym = _isotope_symbol(el)
        if sym:
            groups.setdefault(sym, []).append(el)
    return {sym: iso for sym, iso in groups.items() if len(iso) >= 2}


# ──────────────────────────────────────────────────────────────────────────────
# Analysis worker (runs in a QThread)
# ──────────────────────────────────────────────────────────────────────────────

class _AnalysisWorker(QThread):
    finished = Signal(list)  
    progress = Signal(str)

    def __init__(self, data_context: dict):
        super().__init__()
        self._dc = data_context

    def run(self):
        suggestions: list[Suggestion] = []
        dc = self._dc
        if not dc:
            self.finished.emit([])
            return

        particles: list[dict] = dc.get("particle_data", [])
        sample_names: list[str] = dc.get("sample_names", [])
        is_multi = dc.get("type") == "multiple_sample_data" and len(sample_names) > 1

        if len(particles) < 5:
            self.finished.emit([])
            return

        self.progress.emit("Building element matrix…")
        mat = _element_matrix(particles)
        if not mat:
            self.finished.emit([])
            return

        det = _det_counts(mat)
        n = len(particles)
        all_els = [el for el, c in sorted(det.items(), key=lambda x: -x[1])]
        min_det = max(5, n * 0.04)
        els = [e for e in all_els if det[e] >= min_det]

        self.progress.emit("Computing correlations…")
        corr: list[tuple] = []
        for i in range(len(els)):
            for j in range(i + 1, len(els)):
                r = _pearson_log(mat[els[i]], mat[els[j]])
                if r is not None:
                    corr.append((abs(r), r, els[i], els[j]))
        corr.sort(key=lambda x: -x[0])

        for abs_r, r, ea, eb in corr[:3]:
            if abs_r < 0.55: break
            direction = "positive" if r > 0 else "negative"
            strength = "strong" if abs_r >= 0.80 else "moderate"
            suggestions.append(Suggestion(
                title=f"{ea} vs {eb}",
                reasoning=(
                    f"{strength.capitalize()} {direction} correlation "
                    f"(r = {r:+.2f}) across "
                    f"{det[ea]:,} / {det[eb]:,} detected particles."
                ),
                category="correlation",
                confidence=min(abs_r, 1.0),
                node_type="correlation_plot",
                config={"x_element": ea, "y_element": eb},
            ))

        self.progress.emit("Analysing isotope pairs…")
        iso_groups = _group_isotopes(all_els)
        non_iso = [e for e in els if _isotope_symbol(e) is None]

        for sym, isos in list(iso_groups.items())[:4]:
            isos_s = sorted(isos, key=lambda x: int(re.match(r"^(\d+)", x).group(1)))
            num, den = isos_s[0], isos_s[-1]
            if num not in mat or den not in mat: continue
            joint_mask = (mat[num] > 0) & (mat[den] > 0)
            joint = int(joint_mask.sum())
            if joint < 5: continue

            ratio_arr = np.where(joint_mask, mat[num] / (mat[den] + 1e-30), np.nan)

            best_el3: str | None = None
            best_r3: float = 0.0
            for el3 in non_iso:
                if el3 in (num, den): continue
                m3 = joint_mask & (mat[el3] > 0)
                if m3.sum() < 8: continue
                r3v = ratio_arr[m3]
                e3v = mat[el3][m3]
                if r3v.std() < 1e-10 or e3v.std() < 1e-10: continue
                try:
                    r3 = float(np.corrcoef(np.log1p(r3v), np.log1p(e3v))[0, 1])
                    if abs(r3) > abs(best_r3):
                        best_r3, best_el3 = r3, el3
                except Exception:
                    continue

            cfg: dict = {
                "element1": num,
                "element2": den,
                "x_axis_element": den,
            }
            extra = ""
            if best_el3 and abs(best_r3) >= 0.40:
                cfg["x_axis_element"] = best_el3
                dir3 = "positively" if best_r3 > 0 else "negatively"
                extra = (
                    f" Ratio is {dir3} correlated with "
                    f"{best_el3} (r = {best_r3:+.2f}) — set as X-axis."
                )

            suggestions.append(Suggestion(
                title=f"{num} / {den} ratio",
                reasoning=f"{joint:,} particles carry both isotopes.{extra}",
                category="isotope",
                confidence=min(joint / n * 2, 0.93),
                node_type="isotopic_ratio_plot",
                config=cfg,
            ))

        # ── 3. Bimodality / clustering ────────────────────────────────────────
        self.progress.emit("Checking distribution shapes…")
        bimodal = [(bc, el) for el in els
                   if (bc := _bimodality_bc(mat[el])) > 0.555]
        bimodal.sort(key=lambda x: -x[0])

        if bimodal:
            top_els = [e for _, e in bimodal[:5]]
            bc_top = bimodal[0][0]
            suggestions.append(Suggestion(
                title=f"Clusters in {', '.join(top_els[:3])}",
                reasoning=(
                    f"{len(bimodal)} element(s) show bimodal distributions "
                    f"(BC up to {bc_top:.2f}) — distinct particle populations likely."
                ),
                category="clustering",
                confidence=min((bc_top - 0.555) / 0.3 + 0.45, 0.92),
                node_type="clustering_plot",
                config={"elements": top_els[:5]},
            ))

        self.progress.emit("Ranking element variability…")
        cv_list = []
        for el in els:
            v = mat[el][mat[el] > 0]
            if len(v) >= 5:
                cv_list.append((float(v.std() / (v.mean() + 1e-30)), el))
        cv_list.sort(key=lambda x: -x[0])

        if cv_list:
            top_cv = [e for _, e in cv_list[:4]]
            cv_val = cv_list[0][0]
            suggestions.append(Suggestion(
                title=f"Wide spread: {', '.join(top_cv[:3])}",
                reasoning=(
                    f"Coefficient of variation up to {cv_val:.1f}× — "
                    "concentrations vary enormously between particles."
                ),
                category="distribution",
                confidence=min(cv_val / 3.0, 0.85),
                node_type="box_plot",
                config={"elements": top_cv},
            ))
            suggestions.append(Suggestion(
                title=f"Histogram: {top_cv[0]}",
                reasoning=(
                    f"{top_cv[0]} has the highest variability (CV = {cv_val:.1f}×). "
                    "Check for log-normality or multimodality."
                ),
                category="distribution",
                confidence=min(cv_val / 3.0, 0.85) * 0.85,
                node_type="histogram_plot",
                config={"element": top_cv[0]},
            ))

        self.progress.emit("Counting element combinations…")
        combos: dict[tuple, int] = {}
        for p in particles:
            detected = tuple(sorted(
                el for el, v in p.get("elements", {}).items()
                if _safe_float(v) is not None
            ))
            if detected:
                combos[detected] = combos.get(detected, 0) + 1

        if combos:
            top_combo, top_cnt = max(combos.items(), key=lambda x: x[1])
            conf = min(top_cnt / n + 0.3, 0.88)
            suggestions.append(Suggestion(
                title="Element composition",
                reasoning=(
                    f"Most common: {' + '.join(top_combo[:4])} "
                    f"({top_cnt:,} / {n:,} particles, "
                    f"{top_cnt/n*100:.0f}%)."
                ),
                category="composition",
                confidence=conf,
                node_type="element_bar_chart_plot",
                config={},
            ))
            suggestions.append(Suggestion(
                title="Particle type breakdown",
                reasoning=(
                    f"{len(combos):,} distinct element combinations. "
                    "A pie chart shows which multi-element types dominate."
                ),
                category="composition",
                confidence=conf * 0.80,
                node_type="pie_chart_plot",
                config={},
            ))

        self.progress.emit("Scanning for outliers…")
        outlier_els = []
        for el in els:
            v = mat[el][mat[el] > 0]
            if len(v) < 10: continue
            q1, q3 = np.percentile(v, 25), np.percentile(v, 75)
            frac = float(np.sum(v > q3 + 3 * (q3 - q1))) / len(v)
            if frac > 0.02:
                outlier_els.append((frac, el))
        outlier_els.sort(key=lambda x: -x[0])

        if outlier_els:
            frac, el = outlier_els[0]
            suggestions.append(Suggestion(
                title=f"Outliers: {el}",
                reasoning=(
                    f"{frac*100:.1f}% of {el} particles exceed 3× IQR — "
                    "possible distinct high-concentration population."
                ),
                category="outlier",
                confidence=min(frac * 5 + 0.4, 0.80),
                node_type="heatmap_plot",
                config={"highlight_element": el},
            ))

        if is_multi and all_els:
            top_el = all_els[0]
            by_sample: dict[str, list] = {}
            for p in particles:
                src = p.get("source_sample", "")
                v = _safe_float(p.get("elements", {}).get(top_el, 0))
                by_sample.setdefault(src, []).append(v or 0.0)
            means = {s: float(np.mean([x for x in vs if x > 0] or [0]))
                     for s, vs in by_sample.items() if s in sample_names}
            vals = [v for v in means.values() if v > 0]
            if vals:
                spread = (max(vals) - min(vals)) / (max(vals) + 1e-30)
                suggestions.append(Suggestion(
                    title=f"{top_el} across {len(sample_names)} samples",
                    reasoning=(
                        f"Mean {top_el} varies {spread*100:.0f}% between samples."
                    ),
                    category="comparison",
                    confidence=min(spread + 0.3, 0.90),
                    node_type="concentration_comparison",
                    config={"element": top_el},
                ))

        if len(els) >= 4:
            suggestions.append(Suggestion(
                title=f"Full matrix: {len(els)} elements",
                reasoning=(
                    "All pairwise log-correlations in one heatmap. "
                    "Clusters reveal shared mineralogical sources."
                ),
                category="correlation",
                confidence=0.68,
                node_type="correlation_matrix",
                config={},
            ))

        seen: dict[str, int] = {}
        deduped: list[Suggestion] = []
        for s in sorted(suggestions, key=lambda x: -x.confidence):
            limit = 2 if s.node_type == "correlation_plot" else 1
            if seen.get(s.node_type, 0) < limit:
                deduped.append(s)
                seen[s.node_type] = seen.get(s.node_type, 0) + 1

        self.finished.emit(deduped)


# ──────────────────────────────────────────────────────────────────────────────
# Canvas helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_source_node(scene) -> object | None:
    """Return the configured sample node with the most particles."""
    best, best_n = None, 0
    for node in scene.workflow_nodes:
        if not getattr(node, "_has_output", False):
            continue
        for d in [
            *(
                [node.get_output_data()]
                if hasattr(node, "get_output_data")
                else []
            ),
            getattr(node, "input_data", None),
        ]:
            if not isinstance(d, dict):
                continue
            cnt = len(d.get("particle_data", []))
            if cnt > best_n:
                best, best_n = node, cnt
    return best


def _get_open_sample_names(scene) -> list[str]:
    names: list[str] = []
    for node in scene.workflow_nodes:
        s = getattr(node, "selected_sample", None)
        if s:
            names.append(s)
            continue
        ss = getattr(node, "selected_samples", None)
        if ss:
            names.extend(ss)
            continue
        d = getattr(node, "input_data", None)
        if isinstance(d, dict):
            if d.get("type") == "multiple_sample_data":
                names.extend(d.get("sample_names", []))
            elif d.get("type") == "sample_data":
                n = d.get("sample_name")
                if n:
                    names.append(n)
    seen: set = set()
    return [n for n in names if n and not (n in seen or seen.add(n))] 


def _get_data_context(scene) -> dict:
    best: dict | None = None
    best_n = 0
    for node in scene.workflow_nodes:
        candidates = []
        if hasattr(node, "get_output_data"):
            try:
                d = node.get_output_data()
                if isinstance(d, dict):
                    candidates.append(d)
            except Exception as exc:
                print(f"[Insights] get_output_data failed on '{getattr(node,'title',node)}': {exc}")
        raw = getattr(node, "input_data", None)
        if isinstance(raw, dict):
            candidates.append(raw)
        for d in candidates:
            cnt = len(d.get("particle_data", []))
            if cnt > best_n:
                best, best_n = d, cnt
    if best_n:
        print(f"[Insights] {best_n:,} particles (type={best.get('type','?')})")
    return best or {}


# ──────────────────────────────────────────────────────────────────────────────
# Suggestion card  — muted, theme-aware, no vivid category colours
# ──────────────────────────────────────────────────────────────────────────────

class _Card(QFrame):
    def __init__(self, s: Suggestion, on_add, parent=None):
        super().__init__(parent)
        self._s = s
        self._on_add = on_add
        self._build()

    def _build(self):
        p = _theme.palette
        meta = _CAT_META.get(self._s.category, _CAT_META["correlation"])
        conf_col = {
            "high": p.success, "medium": p.warning, "low": p.disabled
        }[self._s.confidence_label]

        self.setObjectName("insightCard")
        self.setStyleSheet(f"""
            QFrame#insightCard {{
                background: {p.bg_secondary};
                border: 1px solid {p.border_subtle};
                border-left: 3px solid {p.accent};
                border-radius: 6px;
            }}
            QFrame#insightCard:hover {{
                background: {p.bg_hover};
                border-color: {p.border};
                border-left: 3px solid {p.accent_hover};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(4)

        tag = QLabel(f"{meta['icon']}  {meta['label'].upper()}")
        tag.setStyleSheet(f"""
            color: {p.text_muted}; font-size: 9px; font-weight: 700;
            font-family: '{_FONT}'; background: transparent; letter-spacing: 0.5px;
        """)
        root.addWidget(tag)

        title = QLabel(self._s.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"""
            color: {p.text_primary}; font-size: 12px; font-weight: 600;
            font-family: '{_FONT}'; background: transparent;
        """)
        root.addWidget(title)

        reason = QLabel(self._s.reasoning)
        reason.setWordWrap(True)
        reason.setStyleSheet(f"""
            color: {p.text_secondary}; font-size: 11px;
            font-family: '{_FONT}'; background: transparent;
        """)
        root.addWidget(reason)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        cf_w = QWidget()
        cf_w.setStyleSheet("background: transparent;")
        cf_vl = QVBoxLayout(cf_w)
        cf_vl.setContentsMargins(0, 0, 0, 0)
        cf_vl.setSpacing(2)

        cf_lbl = QLabel(
            f"{self._s.confidence_label.upper()}  {int(self._s.confidence * 100)}%"
        )
        cf_lbl.setStyleSheet(
            f"color: {conf_col}; font-size: 9px; font-family: '{_FONT}';"
            " background: transparent;"
        )

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(self._s.confidence * 100))
        bar.setFixedHeight(3)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: {p.border_subtle}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {conf_col}; border-radius: 1px; }}
        """)

        cf_vl.addWidget(cf_lbl)
        cf_vl.addWidget(bar)
        footer.addWidget(cf_w, 1)

        btn = QPushButton("+ Add")
        btn.setFixedSize(52, 24)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {p.accent}; color: {p.text_inverse};
                border: none; border-radius: 4px;
                font-size: 10px; font-weight: 600; font-family: '{_FONT}';
            }}
            QPushButton:hover  {{ background: {p.accent_hover}; }}
            QPushButton:pressed {{ background: {p.accent_pressed}; }}
        """)
        btn.clicked.connect(self._clicked)
        footer.addWidget(btn)
        root.addLayout(footer)

    def _clicked(self):
        self._on_add(self._s)
        p = _theme.palette
        orig = self.styleSheet()
        self.setStyleSheet(
            orig.replace(
                f"background: {p.bg_secondary}",
                f"background: {p.bg_selected}",
            )
        )
        QTimer.singleShot(450, lambda: self.setStyleSheet(orig))


# ──────────────────────────────────────────────────────────────────────────────
# The integrated panel
# ──────────────────────────────────────────────────────────────────────────────

class SmartInsightsPanel(QWidget):
    """
    Resizable QWidget embedded as the rightmost pane of the canvas QSplitter.
    Call refresh() to rerun analysis; it runs automatically when the panel
    becomes visible.
    """

    def __init__(self, scene, parent_window, parent=None):
        super().__init__(parent)
        self._scene = scene
        self._pw = parent_window
        self._worker: _AnalysisWorker | None = None
        self._suggestions: list[Suggestion] = []
        self.setMinimumWidth(250)

        self._build_ui()
        self._apply_theme()
        self._theme_dc = _theme.connect_theme(lambda _: self._apply_theme())


    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QFrame()
        self._hdr.setObjectName("iHdr")
        self._hdr.setFixedHeight(52)
        hl = QHBoxLayout(self._hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(6)

        self._title_lbl = QLabel("✦  Insights")
        self._title_lbl.setObjectName("iTitleLbl")

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("iCountLbl")

        tleft = QVBoxLayout()
        tleft.setSpacing(1)
        tleft.addWidget(self._title_lbl)
        tleft.addWidget(self._count_lbl)

        self._refresh_btn = QPushButton("↺")
        self._refresh_btn.setObjectName("iRefreshBtn")
        self._refresh_btn.setFixedSize(26, 26)
        self._refresh_btn.setToolTip("Re-analyse")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)

        hl.addLayout(tleft)
        hl.addStretch()
        hl.addWidget(self._refresh_btn)
        root.addWidget(self._hdr)

        self._strip = QFrame()
        self._strip.setObjectName("iStrip")
        self._strip.setFixedHeight(26)
        sl = QHBoxLayout(self._strip)
        sl.setContentsMargins(12, 0, 12, 0)
        self._sample_lbl = QLabel("")
        self._sample_lbl.setObjectName("iSampleLbl")
        sl.addWidget(self._sample_lbl)
        root.addWidget(self._strip)

        self._bar = QProgressBar()
        self._bar.setObjectName("iBar")
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(2)
        self._bar.setTextVisible(False)
        self._bar.setVisible(False)
        root.addWidget(self._bar)

        self._status = QLabel("")
        self._status.setObjectName("iStatus")
        self._status.setAlignment(Qt.AlignCenter)
        root.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._card_w = QWidget()
        self._card_w.setObjectName("iCardW")
        self._card_layout = QVBoxLayout(self._card_w)
        self._card_layout.setContentsMargins(8, 8, 8, 8)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()
        scroll.setWidget(self._card_w)
        root.addWidget(scroll, 1)

        self._ftr = QFrame()
        self._ftr.setObjectName("iFtr")
        self._ftr.setFixedHeight(24)
        fl = QHBoxLayout(self._ftr)
        fl.setContentsMargins(12, 0, 12, 0)
        self._hint_lbl = QLabel("+ Add auto-connects and pre-configures the node")
        self._hint_lbl.setObjectName("iHintLbl")
        fl.addStretch()
        fl.addWidget(self._hint_lbl)
        root.addWidget(self._ftr)

    def _apply_theme(self):
        p = _theme.palette
        self.setStyleSheet(f"""
            SmartInsightsPanel {{
                background: {p.bg_primary};
                border-left: 1px solid {p.border};
            }}
            QFrame#iHdr {{
                background: {p.bg_secondary};
                border-bottom: 1px solid {p.border};
            }}
            QFrame#iStrip {{
                background: {p.bg_tertiary};
                border-bottom: 1px solid {p.border_subtle};
            }}
            QFrame#iFtr {{
                background: {p.bg_secondary};
                border-top: 1px solid {p.border};
            }}
            QLabel#iTitleLbl {{
                color: {p.text_primary}; font-size: 13px; font-weight: 700;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iCountLbl {{
                color: {p.text_muted}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iSampleLbl {{
                color: {p.text_secondary}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iStatus {{
                color: {p.text_muted}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent; padding: 2px;
            }}
            QLabel#iHintLbl {{
                color: {p.text_muted}; font-size: 9px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QPushButton#iRefreshBtn {{
                background: transparent; color: {p.text_muted};
                border: 1px solid {p.border}; border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton#iRefreshBtn:hover {{
                color: {p.text_primary}; border-color: {p.accent};
            }}
            QProgressBar#iBar {{
                background: {p.bg_secondary}; border: none;
            }}
            QProgressBar#iBar::chunk {{ background: {p.accent}; }}
            QWidget#iCardW {{ background: transparent; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {p.bg_secondary}; width: 5px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        if self._suggestions:
            self._rebuild_cards()

    def refresh(self):
        """Re-run analysis. Auto-called when the panel becomes visible."""
        self._update_sample_strip()
        dc = _get_data_context(self._scene)
        self._clear_cards()
        self._bar.setVisible(True)
        self._bar.setRange(0, 0)
        self._refresh_btn.setEnabled(False)
        self._count_lbl.setText("")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(400)

        self._worker = _AnalysisWorker(dc)
        self._worker.progress.connect(self._status.setText)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _update_sample_strip(self):
        names = _get_open_sample_names(self._scene)
        if names:
            text = "  ·  ".join(names[:4])
            if len(names) > 4:
                text += f"  +{len(names)-4} more"
            self._sample_lbl.setText(f"📂  {text}")
        else:
            self._sample_lbl.setText("No samples connected yet")

    def _on_done(self, suggestions: list[Suggestion]):
        self._bar.setVisible(False)
        self._status.setText("")
        self._refresh_btn.setEnabled(True)
        self._suggestions = suggestions
        n = len(suggestions)
        self._count_lbl.setText(
            f"{n} insight{'s' if n != 1 else ''}" if n else "No suggestions"
        )
        self._rebuild_cards() if suggestions else self._show_empty()

    def _rebuild_cards(self):
        self._clear_cards()
        for s in self._suggestions:
            card = _Card(s, on_add=self._add_suggestion)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def _show_empty(self):
        p = _theme.palette
        lbl = QLabel("Connect a Sample Selector node\nto generate insights.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {p.text_muted}; font-size: 11px; font-family: '{_FONT}';"
            " padding: 24px; background: transparent;"
        )
        self._card_layout.insertWidget(self._card_layout.count() - 1, lbl)

    def _clear_cards(self):
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


    def _add_suggestion(self, s: Suggestion):
        try:
            from widget.canvas_widgets import _NODE_FACTORIES
        except ImportError:
            print("[Insights] Could not import _NODE_FACTORIES")
            return

        factory = _NODE_FACTORIES.get(s.node_type)
        if factory is None:
            print(f"[Insights] Unknown node_type: {s.node_type}")
            return

        scene = self._scene
        new_node = factory(self._pw)

        if s.config and isinstance(getattr(new_node, "config", None), dict):
            new_node.config.update(s.config)

        source = _find_source_node(scene)
        n_existing = len(scene.workflow_nodes)

        if source:
            src_item = scene.node_items.get(source)
            base = src_item.pos() if src_item else QPointF(300, 200)
            col = n_existing % 3
            row = n_existing // 3
            pos = QPointF(base.x() + 220 + col * 8, base.y() + row * 130)
        else:
            pos = QPointF(300 + n_existing * 12, 200 + n_existing * 12)

        scene.add_node(new_node, pos)

        if source and getattr(source, "_has_output", False):
            scene.add_link(source, "output", new_node, "input")


    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)  

    def closeEvent(self, event):
        self._theme_dc()
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(400)
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Integration helpers — call from CanvasResultsDialog._build()
# ──────────────────────────────────────────────────────────────────────────────

def integrate_insights_panel(canvas_dialog, splitter: QSplitter) -> SmartInsightsPanel:
    """
    Append SmartInsightsPanel as the rightmost pane of *splitter*.

    Example usage inside CanvasResultsDialog._build()::

        # After creating splitter and adding palette + canvas:
        from results.results_smart_suggest import (
            integrate_insights_panel, make_insights_toggle_button)

        self.insights_panel = integrate_insights_panel(self, splitter)
        splitter.setSizes([240, 820, 0])    # 0 = panel starts hidden

        # In the header layout, before the Clear button:
        self._insights_btn = make_insights_toggle_button(self, splitter)
        hl.addWidget(self._insights_btn)
    """
    panel = SmartInsightsPanel(
        scene=canvas_dialog.canvas.scene,
        parent_window=canvas_dialog.parent,
        parent=canvas_dialog,
    )
    panel.setVisible(False)
    splitter.addWidget(panel)
    return panel


def make_insights_toggle_button(canvas_dialog, splitter: QSplitter) -> QPushButton:
    """
    Create the header toggle button that shows/hides the insights panel.
    The button text reflects the current state (open / closed).
    """
    def _toggle():
        panel = canvas_dialog.insights_panel
        sizes = splitter.sizes()
        if panel.isVisible():
            canvas_dialog._insights_prev_w = sizes[-1] or 300
            panel.setVisible(False)
            btn.setText("✦  Insights")
            btn.setToolTip("Open Insights")
        else:
            panel.setVisible(True)
            w = getattr(canvas_dialog, "_insights_prev_w", 300)
            new_sizes = list(sizes)
            new_sizes[-1] = w
            new_sizes[-2] = max(100, new_sizes[-2] - w)
            splitter.setSizes(new_sizes)
            btn.setText("✦  Insights  ‹")
            btn.setToolTip("Close Insights")

    def _style():
        p = _theme.palette
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {p.accent_soft}; color: {p.accent};
                border: 1px solid {p.accent}; border-radius: 6px;
                padding: 0 14px; font-size: 11px; font-weight: 700;
                font-family: '{_FONT}';
            }}
            QPushButton:hover {{
                background: {p.accent_hover}; color: {p.text_inverse};
            }}
            QPushButton:pressed {{
                background: {p.accent_pressed}; color: {p.text_inverse};
            }}
        """)

    btn = QPushButton("✦  Insights")
    btn.setFixedHeight(30)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("Open Insights")
    _style()
    _theme.connect_theme(lambda _: _style())
    btn.clicked.connect(_toggle)
    return btn