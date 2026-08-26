"""
Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

Single sample  → one matrix.
Multi-sample   → side-by-side or individual subplot matrices.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor
from matplotlib.figure import Figure
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import copy_figure_to_clipboard
from results.shared_plot_utils import (
    get_font_config, apply_font_to_matplotlib,
    apply_font_to_colorbar_standalone, FontSettingsGroup,
    ExportSettingsGroup,
    MplDraggableCanvas, LABEL_MODES, format_element_label,
    Renderer, get_display_name, download_matplotlib_figure,
    pick_color_hex,
)
from results.utils_sort import sort_elements_by_mass
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_matrix")


# ── Constants ──────────────────────────────────────────────────────────

MATRIX_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

MATRIX_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

MATRIX_COLORMAPS = [
    'RdBu_r', 'coolwarm', 'seismic', 'BrBG', 'PiYG', 'PRGn',
    'RdYlBu', 'Spectral', 'bwr',
]

MATRIX_DISPLAY_MODES = [
    'Side by Side',
    'Individual Subplots',
    'Difference Matrix',
]

DEGREE_SIGN = "\N{DEGREE SIGN}"

DEFAULT_HIGHLIGHT_COLOR = '#000000'

#: Glyph marking a correlation that is arithmetic rather than evidence.
#:
#: Two distinct meanings, deliberately sharing one symbol because they are
#: the same warning to a reader ("this number is partly definitional"):
#:
#: - **On its own**, replacing the value: the correlation is fixed BY
#:   CONSTRUCTION and carries no information -- the leading diagonal in any
#:   matrix, and (once the classifier pass lands) a single-isotope group
#:   against its own defining isotope.
#: - **Appended to a value** (``0.87*``): part-whole contamination -- the
#:   number is real and worth reading, but inflated because one side is a sum
#:   that contains the other. See ``_draw_matrix_ax``.
#:
#: The point is to stop a matrix full of guaranteed 1s from training the eye
#: to ignore strong values, so that a genuine r = 1 between two things that
#: are NOT definitionally linked stands out as a finding.
TRIVIALITY_MARKER = '*'

# ── Zero handling ──────────────────────────────────────────────────────
#
# Which particles a pair is correlated over. This was hardcoded to "both"
# forever; it is a real scientific choice that changes the QUESTION being
# answered, with or without a classifier attached:
#
#   both   -- "among particles carrying BOTH, do their amounts co-vary?"
#   either -- "among particles carrying AT LEAST ONE, how do they relate?"
#   all    -- "across every particle, do these co-vary?"
#
# Caveat worth knowing (surfaced in the UI): once zeros are included, Pearson
# r increasingly measures CO-OCCURRENCE (do they appear together) rather than
# co-variation of amounts (when both are present, do they scale together).
# That is the point of offering the choice, not a defect -- but it is a
# different question and should be read as one.
ZERO_MODE_BOTH = 'both'
ZERO_MODE_EITHER = 'either'
ZERO_MODE_ALL = 'all'
ZERO_MODE_CONFIG_KEY = 'zero_handling'

ZERO_MODE_LABELS = {
    ZERO_MODE_BOTH: "Both present - only particles carrying both (default)",
    ZERO_MODE_EITHER: "Either present - particles carrying at least one",
    ZERO_MODE_ALL: "All particles - absences count as zero",
}

#: Config key: which classifier group PANELS role shows (multi-sample).
PANEL_GROUP_CONFIG_KEY = 'classifier_panel_group'

#: Config key: whether part-whole-contaminated cells count toward the
#: header's mean|r| summary. Off by default -- they inflate it by
#: construction, which is the whole reason they are marked.
PART_WHOLE_IN_STATS_KEY = 'part_whole_in_stats'


def _pair_mask(vi, vj, zero_mode):
    """Boolean mask of the particles a pair is correlated over.

    Args:
        vi (numpy.ndarray): Values for the first label, per particle.
        vj (numpy.ndarray): Values for the second label, per particle.
        zero_mode (str): One of the ``ZERO_MODE_*`` constants.

    Returns:
        numpy.ndarray: Boolean mask, same length as the inputs.
    """
    if zero_mode == ZERO_MODE_ALL:
        return np.ones(vi.shape, dtype=bool)
    if zero_mode == ZERO_MODE_EITHER:
        return (vi > 0) | (vj > 0)
    return (vi > 0) & (vj > 0)


def effective_zero_mode(cfg):
    """Resolve the zero-handling mode, defaulting to the historical
    both-present rule so existing projects render exactly as before."""
    mode = (cfg or {}).get(ZERO_MODE_CONFIG_KEY)
    return mode if mode in (ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL) else ZERO_MODE_BOTH


def _normalize_highlighted_elements(raw):
    """Return ``{element: hex_color}`` from the highlighted_elements config value."""
    if isinstance(raw, dict):
        return dict(raw)
    return {k: DEFAULT_HIGHLIGHT_COLOR for k in (raw or [])}


CELL_LABEL_MODES = ['r value', 'Particle count', 'Both']

DEFAULT_CONFIG = {
    'data_type_display':  'Counts',
    'min_particles':      5,
    'cell_label':         'r value',
    'r_threshold':        0.0,
    'show_values':        True,
    'show_diagonal':      True,
    # Historical both-present rule stays the default so existing projects
    # render byte-identically; see ZERO_MODE_* for what the others mean.
    'zero_handling':      ZERO_MODE_BOTH,
    'part_whole_in_stats': False,
    'classifier_panel_group': None,
    'colormap':           'RdBu_r',
    'display_mode':       'Side by Side',
    'font_family':        'Times New Roman',
    'font_size':          10,
    'font_bold':          False,
    'font_italic':        False,
    'font_color':         '#000000',
    'sample_colors':      {},
    'sample_name_mappings': {},
    'highlighted_elements': {},
    'label_mode':         'Symbol',
    'x_rotation':         0,
    'bg_color':           '#FFFFFF',
    'export_format':      'svg',
    'export_dpi':         300,
    'use_custom_figsize': False,
    'figsize_w':          14.0,
    'figsize_h':          8.0,
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _clean_value(v, data_key):
    """One raw composition value, normalised for correlation.

    Negative/NaN entries become 0 for every key except ``elements`` (raw
    counts), matching the long-standing behaviour of this module.
    """
    if data_key != 'elements':
        if v <= 0 or (isinstance(v, float) and np.isnan(v)):
            return 0
    return v


def correlate_columns(columns, labels, min_particles=5,
                      zero_mode=ZERO_MODE_BOTH):
    """Pearson-r matrix over pre-built per-label value columns.

    Split out of :func:`_compute_correlation_matrix` so the classifier path
    can supply columns for a MIXED vocabulary (real isotopes alongside
    classifier groups) without duplicating the statistics.

    Args:
        columns (dict): ``{label: sequence of per-particle values}``. Every
            column must be the same length -- index *k* is the same particle
            in all of them.
        labels (list): Ordered labels forming both matrix axes.
        min_particles (int): A pair is only correlated when at least this
            many particles are actually USED for it (see ``zero_mode``);
            below the cut-off the cell stays NaN.
        zero_mode (str): One of the ``ZERO_MODE_*`` constants.

    Returns:
        tuple: ``(r_matrix, p_matrix, count_matrix)``, where ``count_matrix``
        holds the number of particles actually used for each pair -- so
        ``min_particles`` and the header's pair-count line always describe
        the rule currently in force, not a co-detection rule the matrix may
        no longer be using. ``(None, None, None)`` when fewer than two
        labels are supplied.
    """
    n = len(labels)
    if n < 2:
        return None, None, None
    try:
        min_pairs = int(min_particles)
    except (TypeError, ValueError):
        min_pairs = 5
    min_pairs = max(2, min_pairs)

    mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)
    counts = np.zeros((n, n), dtype=np.int64)
    cols = {lbl: np.nan_to_num(np.asarray(columns[lbl], dtype=float), nan=0.0)
            for lbl in labels}
    for i in range(n):
        for j in range(n):
            vi = cols[labels[i]]
            vj = cols[labels[j]]
            mask = _pair_mask(vi, vj, zero_mode)
            used = int(mask.sum())
            counts[i, j] = used
            if used >= min_pairs:
                try:
                    r, p = pearsonr(vi[mask], vj[mask])
                    mat[i, j] = r
                    p_mat[i, j] = p
                except Exception:
                    # Constant input (zero variance) is the common case here:
                    # e.g. every used particle carries the same value, which
                    # pearsonr rejects rather than returning NaN.
                    _itk_log.debug(
                        "pearsonr failed for pair (%r, %r); leaving NaN",
                        labels[i], labels[j])
    return mat, p_mat, counts


def _compute_correlation_matrix(particles, elements, data_key, min_particles=5,
                                zero_mode=ZERO_MODE_BOTH):
    """Build NxN Pearson-r matrix from particle data.

    The plain, non-classifier path: every axis label is a real isotope read
    straight off each particle.

    Args:
        particles (list): Particle records to correlate.
        elements (list): Ordered isotope/element labels forming the matrix axes.
        data_key (str): Per-particle dictionary key holding the values.
        min_particles (int): Minimum number of particles actually used for a
            pair before it is correlated; below that the pair stays NaN.
        zero_mode (str): One of the ``ZERO_MODE_*`` constants -- which
            particles count toward a pair. Defaults to the historical
            both-present rule.

    Returns:
        tuple: ``(r_matrix, p_matrix, count_matrix)`` as NxN arrays.
        ``(None, None, None)`` when fewer than two elements are supplied.
    """
    n = len(elements)
    if n < 2:
        return None, None, None
    columns = {el: [] for el in elements}
    for p in particles:
        d = p.get(data_key, {})
        for el in elements:
            columns[el].append(_clean_value(d.get(el, 0), data_key))
    return correlate_columns(columns, elements, min_particles, zero_mode)


#: Composition keys the classifier deliberately never bucket-collapses,
#: because there is no principled way to sum a diameter across isotopes (see
#: ``tools.particle_classifier_relabel``). A classifier group therefore has
#: no scalar value for these, so GROUPS role drops the group columns and
#: says so rather than inventing a statistic.
_UNSUMMABLE_KEYS = ('element_diameter_nm', 'particle_diameter_nm')


def _merge_copies_by_identity(particles):
    """Group a particle list into one entry per REAL particle.

    Under ``double_count`` the classifier emits a particle matching several
    definitions once per match, each copy carrying a single bucket key. Any
    statistic computed over those copies as if they were separate particles
    is wrong twice over: the isotope values get double-weighted, and no
    single row ever holds two groups at once, so group x group can never
    populate.

    ``classifier_view.dedupe_particles`` deliberately does something else --
    it keeps ONE copy and discards the rest, which is right for a pure
    isotope statistic but throws away exactly the per-bucket values a mixed
    matrix needs. Hence grouping rather than deduping.

    Args:
        particles (list): Particle dicts, possibly containing several copies
            of the same source particle.

    Returns:
        list[list]: One inner list of copies per real particle, in first-
        appearance order so the result is reproducible run to run. Particles
        with no identity (a non-classifier stream) each stand alone.
    """
    from results import classifier_view as cv
    order, groups_by_key = [], {}
    for p in particles:
        ident = cv.particle_identity(p)
        key = ident if ident is not None else id(p)
        if key not in groups_by_key:
            groups_by_key[key] = []
            order.append(key)
        groups_by_key[key].append(p)
    return [groups_by_key[k] for k in order]


def build_mixed_columns(particles, isotopes, groups, data_key, scope):
    """Per-particle value columns for a MIXED isotope + group vocabulary.

    The GROUPS-role primitive for the correlation matrix. Both axes carry the
    same vocabulary (it is a matrix), so this produces one column per label:

    - **isotope** -- the particle's REAL value for that isotope, read through
      ``classifier_view.composition(collapsed=False)`` so a matched particle's
      destructively-collapsed dict does not hide it.
    - **group** -- the particle's value for that bucket when it is a member,
      and ``0`` when it is not. Membership is whatever the classifier decided
      (priority ordering or ``double_count``); this never re-decides it.

    The group's value honours the active aggregation scope: BY DEFINITION
    counts only the isotopes its triggering expression named, TOTAL PARTICLE
    counts every isotope the qualifying particle carries.

    Why this is the useful shape (and group-only is not): an isotope x group
    cell is populated for **every** matched particle, needing no overlap
    between definitions -- unlike group x group, which requires a particle to
    be in both groups at once and is therefore empty under ``priority``.

    Args:
        particles (list): One sample's particle dicts.
        isotopes (list): Real isotope labels to include.
        groups (list): Classifier bucket labels to include.
        data_key (str): e.g. ``'elements'``, ``'element_mass_fg'``.
        scope (str): ``classifier_view.SCOPE_*``.

    Returns:
        tuple: ``(columns, contributing)`` where ``columns`` is
        ``{label: [values]}`` parallel across labels, and ``contributing`` is
        ``{group: set(isotopes that actually fed its value)}`` -- the input
        to the triviality masks, since a group correlated against one of its
        own contributing isotopes is arithmetic rather than evidence.
    """
    from results import classifier_view as cv
    columns = {lbl: [] for lbl in list(isotopes) + list(groups)}
    contributing = {g: set() for g in groups}
    group_set = set(groups)

    # One row per REAL particle, not per emitted copy. Under ``double_count``
    # the classifier emits a particle matching two definitions as TWO dicts,
    # each carrying only ONE bucket key. Iterating those directly gives one
    # row with common>0/carney=0 and another with common=0/carney>0, so no
    # row ever has both -- and group x group comes out entirely blank even
    # WITH double-counting enabled, which is precisely the case
    # double-counting exists to make plottable. (Bug found in manual QA,
    # 2026-08-26.) Merging also stops a doubly-matched particle contributing
    # its isotope values twice and double-weighting every isotope x isotope
    # correlation.
    for copies in _merge_copies_by_identity(particles):
        raw = cv.composition(copies[0], data_key, collapsed=False)
        for iso in isotopes:
            columns[iso].append(_clean_value(raw.get(iso, 0), data_key))

        per_group = {g: 0 for g in groups}
        for p in copies:
            bucket = cv.bucket_of(p)
            if bucket not in group_set:
                continue
            # Reuse the same reader every other node's GROUPS role goes
            # through, so scope semantics (and the MFC pooling-safety gate)
            # cannot drift between nodes.
            items = cv.composition_items_for_role(
                p, data_key, cv.ROLE_SERIES, scope)
            value_for_bucket = sum(
                _clean_value(v, data_key) for lbl, v in items if lbl == bucket)
            per_group[bucket] = value_for_bucket
            contributing[bucket] |= (cv.scope_isotopes(p, scope) & set(raw))
        for g in groups:
            columns[g].append(per_group[g])

    return columns, contributing


def triviality_masks(labels, isotopes, groups, contributing, scope=None):
    """``(exact, partial)`` NxN bool masks for a mixed-vocabulary matrix.

    Marks correlations that are arithmetic rather than evidence, so a
    genuine r = 1 between two things that are NOT definitionally linked
    still reads as a finding (see ``TRIVIALITY_MARKER``):

    - **exact** -- the value is fixed by construction. A group whose value is
      fed by exactly ONE isotope simply IS that isotope's column, so their
      correlation is 1 every time.
    - **partial** -- part-whole contamination. A group fed by several
      isotopes is a SUM CONTAINING each of them, so correlating it against
      any one component is inflated by construction -- but the number is
      real, and different components genuinely differ, so it is annotated
      rather than replaced.

    The leading diagonal is not included here; ``_draw_matrix_ax`` always
    adds it, with or without a classifier.

    **group x group under TOTAL PARTICLE is exact by construction.** In that
    scope a group's value for a particle is the sum of EVERY isotope that
    particle carries -- which does not depend on which group is asking. So
    for any particle belonging to two groups at once, both columns hold the
    identical number and the pair correlates at exactly 1. This only becomes
    visible once ``double_count`` lets a particle occupy two groups, and it
    is emphatically not a finding, so it is marked rather than reported.
    Under BY DEFINITION the two groups sum different isotope sets, so the
    same cell IS informative and is left unmarked.

    Args:
        labels (list): Ordered axis labels (isotopes then groups).
        isotopes (list): The isotope labels among them.
        groups (list): The classifier group labels among them.
        contributing (dict): ``{group: set(isotopes that fed its value)}``.
        scope (str | None): ``classifier_view.SCOPE_*`` in force; needed
            because whether group x group is tautological depends on it.
    """
    from results import classifier_view as cv
    n = len(labels)
    exact = np.zeros((n, n), dtype=bool)
    partial = np.zeros((n, n), dtype=bool)
    if not groups:
        return exact, partial
    index = {lbl: k for k, lbl in enumerate(labels)}

    if scope == cv.SCOPE_TOTAL_PARTICLE:
        for a in groups:
            for b in groups:
                ia, ib = index.get(a), index.get(b)
                if ia is not None and ib is not None and ia != ib:
                    exact[ia, ib] = True
    for g in groups:
        fed_by = contributing.get(g) or set()
        gi = index.get(g)
        if gi is None:
            continue
        for iso in fed_by:
            ii = index.get(iso)
            if ii is None:
                continue
            target = exact if len(fed_by) == 1 else partial
            target[gi, ii] = True
            target[ii, gi] = True
    return exact, partial


def _matrix_stats(mat, exclude=None):
    """Summary line for the header: mean |r| and the share of strong pairs.

    Args:
        mat (numpy.ndarray): NxN Pearson-r matrix.
        exclude (numpy.ndarray | None): Optional NxN bool mask of cells to
            leave OUT of the summary -- used for part-whole-contaminated
            cells, which are inflated by construction and would otherwise
            drag ``mean|r|`` upward for reasons that are arithmetic rather
            than scientific. The diagonal is always excluded regardless.
    """
    n = mat.shape[0]
    skip = (np.zeros((n, n), dtype=bool) if exclude is None
            else np.asarray(exclude, dtype=bool))
    off_diag = [mat[i, j] for i in range(n) for j in range(n)
                if i != j and not skip[i, j] and not np.isnan(mat[i, j])]
    if not off_diag:
        return "No valid correlations"
    arr = np.array(off_diag)
    return f"mean|r|={np.mean(np.abs(arr)):.3f}  ·  {np.mean(np.abs(arr) > 0.7)*100:.0f}% pairs >0.7"


def _pair_count_stats(counts, min_particles):
    """Summarise how the Min Particles cut-off lands on the current data.

    Args:
        counts (numpy.ndarray): NxN co-detection counts per element pair.
        min_particles (int): Active Min Particles threshold.

    Returns:
        str: Short status string, empty when counts are unavailable.
    """
    if counts is None or not isinstance(counts, np.ndarray) or counts.size == 0:
        return ""
    n = counts.shape[0]
    if n < 2:
        return ""
    iu = np.triu_indices(n, k=1)
    pairs = counts[iu]
    if pairs.size == 0:
        return ""
    kept = int(np.sum(pairs >= max(2, int(min_particles))))
    total = int(pairs.size)
    return (f"min particles {int(min_particles)} keeps {kept}/{total} pairs "
            f"(pair overlap median {int(np.median(pairs))}, max {int(pairs.max())})")


# ── Settings Dialog ────────────────────────────────────────────────────

class MatrixSettingsDialog(QDialog):
    preview_requested = Signal(dict)

    def __init__(self, cfg, input_data, parent=None, scope='all'):
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Correlation matrix plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Correlation matrix plot quantities configuration")
        else:
            self.setWindowTitle("Correlation Matrix Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._scope = scope
        self.dtype_combo = None
        self.min_part = None
        self.thresh_spin = None
        self.cell_label_combo = None
        self.show_vals = None
        self.show_diag = None
        self.cmap_combo = None
        self.label_mode_combo = None
        self.x_rotation_spin = None
        self.mode_combo = None
        self.zero_mode_combo = None
        self.panel_group_combo = None
        self.part_whole_cb = None
        self._mode_note = None
        self._font_grp = None
        self._export_grp = None
        self._classifier_group = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        if self._scope in ('all', 'quantities'):
            from results.shared_plot_utils import ClassifierViewGroup
            from results import classifier_view as cv
            # COLORS is offered but disabled: unlike heatmap, both axes here
            # carry the SAME vocabulary and every cell is an aggregate over
            # many particles, so there is no per-particle mark to colour.
            # Shown-and-explained beats silently missing.
            self._classifier_group = ClassifierViewGroup(
                self._cfg, self._input_data, cv.ARITY_MATRIX,
                disabled_roles={
                    cv.ROLE_ENCODE:
                        "work in progress - a matrix cell is an aggregate, "
                        "not a particle, so there is nothing to colour yet"})
            lay.addWidget(self._classifier_group.build())

            g0 = QGroupBox("Zero Handling")
            f0 = QFormLayout(g0)
            self.zero_mode_combo = QComboBox()
            for mode in (ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL):
                self.zero_mode_combo.addItem(ZERO_MODE_LABELS[mode], mode)
            z_idx = self.zero_mode_combo.findData(effective_zero_mode(self._cfg))
            if z_idx >= 0:
                self.zero_mode_combo.setCurrentIndex(z_idx)
            self.zero_mode_combo.setToolTip(
                "Which particles a pair is correlated over.\n\n"
                "This changes the QUESTION, not just the filtering: once\n"
                "zeros are included, Pearson r increasingly measures whether\n"
                "two things OCCUR TOGETHER rather than whether their amounts\n"
                "scale together. Both are legitimate; they are not the same.")
            f0.addRow("Correlate over:", self.zero_mode_combo)
            lay.addWidget(g0)

        if self._scope in ('all', 'quantities'):
            g1 = QGroupBox("Data")
            f1 = QFormLayout(g1)
            self.dtype_combo = QComboBox()
            self.dtype_combo.addItems(MATRIX_DATA_TYPES)
            self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
            f1.addRow("Data Type:", self.dtype_combo)
            self.min_part = QDoubleSpinBox()
            self.min_part.setRange(2, 10000000); self.min_part.setDecimals(0)
            self.min_part.setValue(self._cfg.get('min_particles', 5))
            self.min_part.setToolTip(
                "A pair is only correlated when both elements are detected together\n"
                "in at least this many particles. Pairs below the cut-off stay blank.\n"
                "The plot header reports how many pairs survive.")
            f1.addRow("Min Particles:", self.min_part)
            self.thresh_spin = QDoubleSpinBox()
            self.thresh_spin.setRange(0.0, 0.99); self.thresh_spin.setDecimals(2)
            self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.0))
            f1.addRow("|r| Threshold:", self.thresh_spin)
            self.cell_label_combo = QComboBox()
            self.cell_label_combo.addItems(CELL_LABEL_MODES)
            self.cell_label_combo.setCurrentText(self._cfg.get('cell_label', 'r value'))
            self.cell_label_combo.setToolTip(
                "What each cell prints when Show r Values is on.\n"
                "Particle count shows how many particles carry both elements,\n"
                "which is the number Min Particles is compared against.")
            f1.addRow("Cell Label:", self.cell_label_combo)
            lay.addWidget(g1)

        if self._scope in ('all', 'format'):
            g2 = QGroupBox("Display")
            f2 = QFormLayout(g2)
            self.show_vals = QCheckBox()
            self.show_vals.setChecked(self._cfg.get('show_values', True))
            f2.addRow("Show r Values:", self.show_vals)
            self.show_diag = QCheckBox()
            self.show_diag.setChecked(self._cfg.get('show_diagonal', True))
            f2.addRow("Show Diagonal:", self.show_diag)
            self.cmap_combo = QComboBox()
            self.cmap_combo.addItems(MATRIX_COLORMAPS)
            raw_cmap = self._cfg.get('colormap', 'RdBu_r').split()[0]
            self.cmap_combo.setCurrentText(raw_cmap if raw_cmap in MATRIX_COLORMAPS else 'RdBu_r')
            f2.addRow("Colormap:", self.cmap_combo)
            self.label_mode_combo = QComboBox()
            self.label_mode_combo.addItems(LABEL_MODES)
            self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
            f2.addRow("Isotope Label:", self.label_mode_combo)
            from PySide6.QtWidgets import QSpinBox as _QSpin
            self.x_rotation_spin = _QSpin()
            self.x_rotation_spin.setRange(0, 90)
            self.x_rotation_spin.setSuffix(DEGREE_SIGN)
            self.x_rotation_spin.setValue(self._cfg.get('x_rotation', 0))
            f2.addRow("X Label Rotation:", self.x_rotation_spin)
            lay.addWidget(g2)

        if self._scope in ('all', 'quantities') and self._classifier_group is not None \
                and self._classifier_group._applicable:
            from results import classifier_view as cv
            role_combo = self._classifier_group.role_combo

            gp = QGroupBox("Classifier Cells")
            fp = QFormLayout(gp)
            self.part_whole_cb = QCheckBox(
                "Count part-whole cells toward mean |r|")
            self.part_whole_cb.setChecked(
                self._cfg.get(PART_WHOLE_IN_STATS_KEY, False))
            self.part_whole_cb.setToolTip(
                "A group's value is a sum over isotopes, so correlating it\n"
                "against one of its own components is inflated by\n"
                "construction (marked '" + TRIVIALITY_MARKER + "' on the plot).\n"
                "Off by default so the header's mean |r| reflects findings\n"
                "rather than arithmetic.")
            fp.addRow(self.part_whole_cb)
            lay.addWidget(gp)

            if _is_multi(self._input_data):
                gg = QGroupBox("Panel Group")
                vg = QVBoxLayout(gg)
                self.panel_group_combo = QComboBox()
                for lbl in cv.bucket_registry(self._input_data):
                    self.panel_group_combo.addItem(lbl, lbl)
                pg_idx = self.panel_group_combo.findData(
                    self._cfg.get(PANEL_GROUP_CONFIG_KEY))
                if pg_idx >= 0:
                    self.panel_group_combo.setCurrentIndex(pg_idx)
                vg.addWidget(QLabel(
                    "Which classifier group to show, one matrix per sample:"))
                vg.addWidget(self.panel_group_combo)
                lay.addWidget(gg)

                def _sync_panel_group():
                    is_panels = role_combo.currentData() == cv.ROLE_FACET
                    self.panel_group_combo.setEnabled(is_panels)
                    self.panel_group_combo.setToolTip(
                        "" if is_panels else
                        "Only applies under PANELS -- other roles don't show "
                        "one classifier group at a time.")
                role_combo.currentIndexChanged.connect(_sync_panel_group)
                _sync_panel_group()

        if self._scope in ('all', 'quantities') and _is_multi(self._input_data):
            g3 = QGroupBox("Multi-Sample Display")
            f3 = QFormLayout(g3)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(MATRIX_DISPLAY_MODES)
            self.mode_combo.setCurrentText(
                self._cfg.get('display_mode', MATRIX_DISPLAY_MODES[0]))
            f3.addRow("Display Mode:", self.mode_combo)
            self._mode_note = QLabel(
                "Unavailable under PANELS — that role already lays the figure "
                "out as one matrix per sample for the selected group.")
            self._mode_note.setWordWrap(True)
            self._mode_note.setStyleSheet("color:#B45309; font-size:11px;")
            self._mode_note.setVisible(False)
            f3.addRow(self._mode_note)
            lay.addWidget(g3)

            if self._classifier_group is not None and self._classifier_group.role_combo is not None:
                from results import classifier_view as cv
                _rc = self._classifier_group.role_combo

                def _sync_mode():
                    is_panels = _rc.currentData() == cv.ROLE_FACET
                    self.mode_combo.setEnabled(not is_panels)
                    self._mode_note.setVisible(is_panels)
                _rc.currentIndexChanged.connect(_sync_mode)
                _sync_mode()

        if self._scope in ('all', 'format'):
            self._font_grp = FontSettingsGroup(self._cfg)
            lay.addWidget(self._font_grp.build())

            self._export_grp = ExportSettingsGroup(self._cfg)
            lay.addWidget(self._export_grp.build())

        _btn_row = QHBoxLayout()
        _btn_row.addStretch()
        _apply_btn = QPushButton("Apply")
        _done_btn = QPushButton("Done")
        _cancel_btn = QPushButton("Cancel")
        _apply_btn.clicked.connect(lambda: self.preview_requested.emit(self.collect()))
        _done_btn.clicked.connect(self.accept)
        _cancel_btn.clicked.connect(self.reject)
        _btn_row.addWidget(_apply_btn)
        _btn_row.addWidget(_done_btn)
        _btn_row.addWidget(_cancel_btn)
        root.addLayout(_btn_row)

    def collect(self):
        d = {
            'data_type_display': self.dtype_combo.currentText() if self.dtype_combo else self._cfg.get('data_type_display', 'Counts'),
            'min_particles':     int(self.min_part.value()) if self.min_part else int(self._cfg.get('min_particles', 5)),
            'r_threshold':       self.thresh_spin.value() if self.thresh_spin else self._cfg.get('r_threshold', 0.0),
            'cell_label':        self.cell_label_combo.currentText() if self.cell_label_combo else self._cfg.get('cell_label', 'r value'),
            'show_values':       self.show_vals.isChecked() if self.show_vals else self._cfg.get('show_values', True),
            'show_diagonal':     self.show_diag.isChecked() if self.show_diag else self._cfg.get('show_diagonal', True),
            'colormap':          self.cmap_combo.currentText() if self.cmap_combo else self._cfg.get('colormap', 'RdBu_r'),
            'label_mode':        self.label_mode_combo.currentText() if self.label_mode_combo else self._cfg.get('label_mode', 'Symbol'),
            'x_rotation':        self.x_rotation_spin.value() if self.x_rotation_spin else self._cfg.get('x_rotation', 0),
        }
        if self._font_grp is not None:
            d.update(self._font_grp.collect())
        if self._export_grp is not None:
            d.update(self._export_grp.collect())
        if self._classifier_group is not None:
            d.update(self._classifier_group.collect())
        if self.mode_combo is not None:
            d['display_mode'] = self.mode_combo.currentText()
        if self.zero_mode_combo is not None:
            d[ZERO_MODE_CONFIG_KEY] = self.zero_mode_combo.currentData()
        if self.panel_group_combo is not None and self.panel_group_combo.count():
            d[PANEL_GROUP_CONFIG_KEY] = self.panel_group_combo.currentData()
        if self.part_whole_cb is not None:
            d[PART_WHOLE_IN_STATS_KEY] = self.part_whole_cb.isChecked()
        return d


# ── Display Dialog ─────────────────────────────────────────────────────

class CorrelationMatrixDisplayDialog(QDialog):
    """Matplotlib-based correlation matrix dialog with drag support."""

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Correlation Matrix Analysis")
        self.setMinimumSize(1100, 750)
        self._axes_row_elems = {}
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._header = QLabel("")
        self._header.setStyleSheet("color:#94A3B8; font-size:12px; padding:4px 8px;")
        lay.addWidget(self._header)

        self.figure = Figure(figsize=(14, 8), dpi=120, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.canvas, stretch=1)

        tb = QHBoxLayout(); tb.setContentsMargins(0, 2, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_r = QPushButton("Reset layout")
        btn_r.setToolTip("Reset subplot positions (or middle-click)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export figure")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_fmt)
        tb.addWidget(btn_qty)
        tb.addWidget(btn_r)
        tb.addWidget(btn_e)
        lay.addLayout(tb)

    # ── Context menu ───────────────────────────────────────────────────

    def _ctx_menu(self, pos):
        """Build a minimal Matrix right-click menu with quick controls only.

        The context menu is intentionally limited to `Quick Toggles` and
        `Isotope Label`. Full format/quantity configuration, reset, and export
        are intentionally delegated to the four bottom buttons.

        Preserved behavior:
        - Toggle and label-mode actions still update the same config keys.
        - Matrix calculations, thresholds, and data semantics are unchanged.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_values', 'Show r Values'),
                            ('show_diagonal', 'Show Diagonal')]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        row_elem = self._get_row_at(pos)
        highlighted = _normalize_highlighted_elements(cfg.get('highlighted_elements', {}))
        if row_elem is not None:
            menu.addSeparator()
            if row_elem in highlighted:
                a = menu.addAction("Remove highlight from this row")
                a.triggered.connect(lambda _, e=row_elem: self._toggle_row_highlight(e, False))
                a3 = menu.addAction("Change highlight color...")
                a3.triggered.connect(lambda _, e=row_elem: self._change_row_highlight_color(e))
            else:
                a = menu.addAction("Highlight this row")
                a.triggered.connect(lambda _, e=row_elem: self._toggle_row_highlight(e, True))

        if highlighted:
            if row_elem is None:
                menu.addSeparator()
            a2 = menu.addAction("Clear all row highlights")
            a2.triggered.connect(lambda _: self._clear_all_highlights())

        menu.addSeparator()
        act_copy_fig = menu.addAction("Copy figure")
        act_copy_fig.triggered.connect(
            lambda: copy_figure_to_clipboard(self.canvas))
        menu.exec(QCursor.pos())
    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _get_row_at(self, widget_pos):
        """Return the element for the matrix row at widget_pos, or None."""
        canvas_h = self.canvas.height()
        mpl_x = float(widget_pos.x())
        mpl_y = float(canvas_h - widget_pos.y())
        for ax in self.figure.get_axes():
            row_elems = self._axes_row_elems.get(id(ax))
            if not row_elems:
                continue
            try:
                inv = ax.transData.inverted()
                data_x, data_y = inv.transform((mpl_x, mpl_y))
                row_idx = int(round(data_y))
                xlim = ax.get_xlim(); ylim = ax.get_ylim()
                x_min = min(xlim); x_max = max(xlim)
                y_min = min(ylim); y_max = max(ylim)
                if (x_min - 0.5 <= data_x <= x_max + 0.5
                        and y_min - 0.5 <= data_y <= y_max + 0.5
                        and 0 <= row_idx < len(row_elems)):
                    return row_elems[row_idx]
            except Exception:
                pass
        return None

    def _toggle_row_highlight(self, elem, add):
        highlighted = _normalize_highlighted_elements(self.node.config.get('highlighted_elements', {}))
        if add:
            highlighted[elem] = highlighted.get(elem, DEFAULT_HIGHLIGHT_COLOR)
        else:
            highlighted.pop(elem, None)
        self.node.config['highlighted_elements'] = highlighted
        self._refresh()

    def _change_row_highlight_color(self, elem):
        highlighted = _normalize_highlighted_elements(self.node.config.get('highlighted_elements', {}))
        current = highlighted.get(elem, DEFAULT_HIGHLIGHT_COLOR)
        picked = pick_color_hex(current, self, "Choose Highlight Color")
        if picked is not None:
            highlighted[elem] = picked
            self.node.config['highlighted_elements'] = highlighted
            self._refresh()

    def _clear_all_highlights(self):
        self.node.config['highlighted_elements'] = {}
        self._refresh()

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.figure, self, "correlation_matrix")

    def _open_plot_format_settings(self):
        _snap = dict(self.node.config)
        dlg = MatrixSettingsDialog(
            self.node.config, self.node.input_data, self, scope='format')
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_configure_plot_quantities(self):
        _snap = dict(self.node.config)
        dlg = MatrixSettingsDialog(
            self.node.config, self.node.input_data, self, scope='quantities')
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_settings(self):
        dlg = MatrixSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh / draw ─────────────────────────────────────────────────

    def _refresh(self):
        try:
            from results import classifier_view as cv
            self._axes_row_elems = {}
            cfg = self.node.config
            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 14.0),
                                            cfg.get('figsize_h', 8.0))
            self.figure.clear()
            self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))

            if self.node.classifier_role() == cv.ROLE_FACET:
                self._draw_panels(cfg)
                self.figure.tight_layout()
                self.canvas.draw()
                self.canvas.snapshot_positions()
                return

            data = self.node.extract_matrix_data()
            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No data available\nConnect to a Sample Selector node.',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.axis('off')
                self._header.setText("")
                self.canvas.draw()
                return

            multi = _is_multi(self.node.input_data)
            if multi:
                mode = cfg.get('display_mode', 'Side by Side')
                if mode == 'Difference Matrix' and len(data) == 2:
                    self._draw_difference(data, cfg)
                else:
                    self._draw_multi(data, cfg)
            else:
                self._draw_single(data, cfg)

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error refreshing correlation matrix: {e}")
            import traceback; traceback.print_exc()

    def _stats_exclusion(self, info, cfg):
        """Which cells to leave out of the header's mean|r|.

        Part-whole cells are inflated by construction, so they are excluded
        by default; the user can opt them back in.
        """
        if cfg.get(PART_WHOLE_IN_STATS_KEY, False):
            return None
        return info.get('partial_trivial')

    def _group_note(self, info):
        """Explain a GROUPS matrix that came out structurally empty, rather
        than leaving the user to stare at a blank grid.

        Group x group needs a particle to be in BOTH groups at once, which
        under ``priority`` overlap mode never happens -- every particle lands
        in exactly one bucket. That is a property of the classifier's
        settings, not a failure here, so it is stated plainly.
        """
        from results import classifier_view as cv
        groups = info.get('groups') or []
        if info.get('groups_dropped'):
            return ("groups omitted: a diameter has no meaningful sum across "
                    "isotopes, so a group has no value to correlate")
        if len(groups) < 2:
            return ""
        if cv.is_double_count(self.node.input_data):
            return ""
        return ("group x group is empty under 'priority' overlap: a particle "
                "belongs to one group only, so no two groups ever co-occur")

    def _draw_single(self, data, cfg):
        mat = data['matrix']
        elems = data['elements']
        n = data.get('n_particles', 0)
        pair_info = _pair_count_stats(data.get('pair_counts'),
                                      data.get('min_particles', 5))
        note = self._group_note(data)
        self._header.setText(
            f"Correlation Matrix · {len(elems)} elements · {n} particles · "
            f"{_matrix_stats(mat, self._stats_exclusion(data, cfg))}"
            + (f" · {pair_info}" if pair_info else "")
            + (f" · {note}" if note else ""))
        ax = self.figure.add_subplot(111)
        self._draw_matrix_ax(ax, mat, elems, cfg, title="",
                             counts=data.get('pair_counts'),
                             exact_trivial=data.get('exact_trivial'),
                             partial_trivial=data.get('partial_trivial'))
        apply_font_to_matplotlib(ax, cfg)

    def _draw_multi(self, data, cfg):
        names = list(data.keys())
        n = len(names)
        cols = min(n, 3)
        rows = math.ceil(n / cols)
        first = data[names[0]]
        pair_info = _pair_count_stats(first.get('pair_counts'),
                                      first.get('min_particles', 5))
        note = self._group_note(first)
        self._header.setText(f"Correlation Matrices · {n} samples"
                             + (f" · {pair_info}" if pair_info else "")
                             + (f" · {note}" if note else ""))
        for idx, sn in enumerate(names):
            info = data[sn]
            ax = self.figure.add_subplot(rows, cols, idx + 1)
            dn = get_display_name(sn, cfg)
            self._draw_matrix_ax(ax, info['matrix'], info['elements'], cfg,
                                 title=f"{dn}  (n={info.get('n_particles',0)})",
                                 counts=info.get('pair_counts'),
                                 exact_trivial=info.get('exact_trivial'),
                                 partial_trivial=info.get('partial_trivial'))
            apply_font_to_matplotlib(ax, cfg)

    def _draw_panels(self, cfg):
        """PANELS role: one correlation matrix per classifier group
        (single-sample), or one per sample for the chosen group
        (multi-sample) -- mirroring heatmap's PANELS exactly.
        """
        from results import classifier_view as cv
        panel_data = self.node.extract_panel_data()

        if _is_multi(self.node.input_data):
            group = self.node.panel_group()
            per_sample = (panel_data or {}).get(group) or {}
            panels = [(get_display_name(sn, cfg), info)
                     for sn, info in per_sample.items()]
            heading = (cv.bucket_caption(self.node.input_data, group)
                       if group else "")
            empty = (f'No correlatable data in "{group}" for any sample'
                     if group else 'No classifier group selected')
        else:
            panels = [(cv.bucket_caption(self.node.input_data, lbl), info)
                     for lbl, info in (panel_data or {}).items()]
            heading = ""
            empty = 'No classified data available'

        if not panels:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5,
                    f'{empty}\n\nA group needs at least two isotopes on its axes;\n'
                    'BY DEFINITION scope narrows those to the ones its\n'
                    'expression names, which can leave too few to correlate.',
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=11, color='gray')
            ax.axis('off')
            self._header.setText(heading)
            return

        self._header.setText(
            (f"{heading} · " if heading else "")
            + f"{len(panels)} panel(s) · one correlation matrix per "
            + ("sample" if _is_multi(self.node.input_data) else "classifier group"))
        cols = min(len(panels), 3)
        rows = math.ceil(len(panels) / cols)
        for idx, (title, info) in enumerate(panels):
            ax = self.figure.add_subplot(rows, cols, idx + 1)
            self._draw_matrix_ax(
                ax, info['matrix'], info['elements'], cfg,
                title=f"{title}  (n={info.get('n_particles', 0)})",
                counts=info.get('pair_counts'))
            apply_font_to_matplotlib(ax, cfg)

    def _draw_difference(self, data, cfg):
        names = list(data.keys())
        info1, info2 = data[names[0]], data[names[1]]
        common = [e for e in info1['elements'] if e in info2['elements']]
        if not common:
            self._draw_multi(data, cfg); return
        idx1 = {e: i for i, e in enumerate(info1['elements'])}
        idx2 = {e: i for i, e in enumerate(info2['elements'])}
        n = len(common)
        diff = np.full((n, n), np.nan)
        for i, ei in enumerate(common):
            for j, ej in enumerate(common):
                r1 = info1['matrix'][idx1[ei], idx1[ej]]
                r2 = info2['matrix'][idx2[ei], idx2[ej]]
                if not np.isnan(r1) and not np.isnan(r2):
                    diff[i, j] = r1 - r2
        self._header.setText(f"Δr = {names[0]} − {names[1]} · {_matrix_stats(diff)}")
        ax = self.figure.add_subplot(111)
        self._draw_matrix_ax(ax, diff, common, cfg,
                             title=f"Difference: {names[0]} − {names[1]}")
        apply_font_to_matplotlib(ax, cfg)

    def _draw_matrix_ax(self, ax, mat, elems, cfg, title="", counts=None,
                        exact_trivial=None, partial_trivial=None):
        """Draw one correlation matrix onto ax using imshow.

        Args:
            ax: Matplotlib axes to draw on.
            mat (numpy.ndarray): NxN Pearson-r matrix.
            elems (list): Element labels for both axes.
            cfg (dict): Plot configuration.
            title (str): Optional axes title.
            counts (numpy.ndarray): Optional NxN co-detection counts, used when
                the cell label mode asks for the per-pair particle count.
            exact_trivial (numpy.ndarray | None): Optional NxN bool mask of
                cells whose value is fixed *by construction* and therefore
                carries no information -- rendered as :data:`TRIVIALITY_MARKER`
                INSTEAD of the number. The leading diagonal is always included
                (an element correlates with itself at exactly 1, every time,
                in every matrix). Pass extra cells to mark others.
            partial_trivial (numpy.ndarray | None): Optional NxN bool mask of
                cells that are *partly* arithmetic rather than evidence --
                rendered as the real value WITH the marker appended
                (``0.87*``). The motivating case is part-whole correlation: a
                classifier group's value is a sum over isotopes, so correlating
                it against one of its own component isotopes is inflated by
                construction, but -- unlike the diagonal -- the number is not
                fixed and different components genuinely differ, so throwing it
                away would destroy real information.

        Why mark triviality at all: a matrix full of guaranteed 1s trains the
        eye to skip strong values, which is exactly backwards. Marking the
        arithmetic ones means a genuine r = 1 between two things that are NOT
        definitionally linked reads as the finding it is, instead of blending
        into the diagonal.
        """
        n = len(elems)
        # The diagonal is trivially 1 in every correlation matrix ever drawn,
        # with or without a classifier -- always marked, never opt-in.
        exact_mask = np.eye(n, dtype=bool)
        if exact_trivial is not None:
            exact_mask |= np.asarray(exact_trivial, dtype=bool)
        partial_mask = (np.zeros((n, n), dtype=bool) if partial_trivial is None
                        else np.asarray(partial_trivial, dtype=bool))
        threshold = cfg.get('r_threshold', 0.0)
        show_diag = cfg.get('show_diagonal', True)
        show_vals = cfg.get('show_values', True)
        cmap      = cfg.get('colormap', 'RdBu_r').split()[0]
        label_mode = cfg.get('label_mode', 'Symbol')
        x_rotation = cfg.get('x_rotation', 0)
        fc        = get_font_config(cfg)

        plot_mat = mat.copy()
        for i in range(n):
            for j in range(n):
                if i != j and not np.isnan(plot_mat[i, j]):
                    if abs(plot_mat[i, j]) < threshold:
                        plot_mat[i, j] = np.nan
            if not show_diag:
                plot_mat[i, i] = np.nan

        im = ax.imshow(plot_mat, cmap=cmap, vmin=-1, vmax=1,
                       aspect='equal', interpolation='nearest')

        fmt_elems = [format_element_label(e, label_mode, Renderer.MATHTEXT, cfg) for e in elems]

        ax.set_xticks(range(n))
        ax.set_xticklabels(fmt_elems, rotation=x_rotation,
                           ha='right' if x_rotation > 0 else 'center',
                           fontsize=fc['size'], color=fc['color'])
        ax.set_yticks(range(n))
        ax.set_yticklabels(fmt_elems, fontsize=fc['size'], color=fc['color'])

        self._axes_row_elems[id(ax)] = elems
        highlighted = _normalize_highlighted_elements(cfg.get('highlighted_elements', {}))
        if highlighted:
            for i, el in enumerate(elems):
                if el in highlighted:
                    ax.axhline(y=i + 0.35, color=highlighted[el], linewidth=2, alpha=0.9,
                               xmin=-0.15, xmax=0, clip_on=False)
                    ax.get_yticklabels()[i].set_weight('bold')

        if title:
            ax.set_title(title, fontsize=fc['size'] + 2,
                         fontweight='bold' if fc['bold'] else 'normal',
                         color=fc['color'], pad=10)

        if show_vals:
            cell_label = cfg.get('cell_label', 'r value')
            has_counts = isinstance(counts, np.ndarray) and counts.shape == plot_mat.shape
            for i in range(n):
                for j in range(n):
                    v = plot_mat[i, j]
                    if np.isnan(v):
                        continue
                    # The r-value text only. The particle count is a real
                    # observation even in a trivial cell (how many particles
                    # carry that element), so it is never replaced -- only
                    # the correlation half of a 'Both' label is.
                    if exact_mask[i, j]:
                        r_text = TRIVIALITY_MARKER
                    elif partial_mask[i, j]:
                        r_text = f"{v:.2f}{TRIVIALITY_MARKER}"
                    else:
                        r_text = f"{v:.2f}"
                    if cell_label == 'Particle count' and has_counts:
                        label = f"{int(counts[i, j])}"
                    elif cell_label == 'Both' and has_counts:
                        label = f"{r_text}\n{int(counts[i, j])}"
                    else:
                        label = r_text
                    tc = 'white' if abs(v) > 0.6 else 'black'
                    ax.text(j, i, label, ha='center', va='center',
                            fontsize=max(6, fc['size'] - 2), color=tc,
                            fontweight='bold' if fc['bold'] else 'normal')

        cbar = self.figure.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        apply_font_to_colorbar_standalone(cbar, cfg, "Pearson r")

        ax.set_facecolor(cfg.get('bg_color', '#FFFFFF'))


# ── Node ───────────────────────────────────────────────────────────────

class CorrelationMatrixNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title           = "Corr. Matrix"
        self.node_type       = "correlation_matrix"
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ["input"]
        self.output_channels = []
        from results.shared_plot_utils import deep_copy_config
        self.config          = deep_copy_config(DEFAULT_CONFIG)
        self.input_data      = None

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = CorrelationMatrixDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def classifier_role(self):
        """GROUPS/PANELS/COLORS/OFF in force for this render.

        Config-derived: the ``classifier_`` prefix is what makes
        ``_FigureView`` resolve this against the FIGURE's config rather than
        the node's -- see ``shared_plot_utils._FigureView``. Renaming it off
        that prefix silently pins the role to its default forever.
        """
        from results import classifier_view as cv
        return cv.effective_role(self.config, self.input_data, cv.ARITY_MATRIX)

    def classifier_scope(self):
        """BY DEFINITION vs TOTAL PARTICLE, defaulting to TOTAL PARTICLE for
        this node (BY DEFINITION yields a 1x1 -- i.e. nothing -- for a
        single-isotope group, so it is a power-user view, not a sane
        default). Same view-config routing note as :meth:`classifier_role`.
        """
        from results import classifier_view as cv
        if not cv.is_classifier_stream(self.input_data):
            return cv.SCOPE_DEFINITION
        stored = (self.config or {}).get(cv.SCOPE_CONFIG_KEY)
        if stored in (cv.SCOPE_DEFINITION, cv.SCOPE_TOTAL_PARTICLE):
            return stored
        return cv.SCOPE_TOTAL_PARTICLE

    def panel_groups(self):
        """Classifier groups PANELS role can show, registry order."""
        from results import classifier_view as cv
        return list(cv.bucket_registry(self.input_data).keys())

    def panel_group(self):
        """The single group PANELS shows per sample (multi-sample only).

        Resolved against the CURRENT group list every render, so a stored
        choice that no longer exists falls back rather than rendering
        nothing.
        """
        groups = self.panel_groups()
        if not groups:
            return None
        stored = self.config.get(PANEL_GROUP_CONFIG_KEY)
        return stored if stored in groups else groups[0]

    def _zero_mode(self):
        return effective_zero_mode(self.config)

    def extract_matrix_data(self):
        """Matrix data for GROUPS / COLORS / OFF.

        Returns ``None`` under PANELS, whose shape is per-group and is served
        by :meth:`extract_panel_data` instead -- callers of this method (and
        the dialog) branch on the role before asking.
        """
        if not self.input_data:
            return None
        from results import classifier_view as cv
        if self.classifier_role() == cv.ROLE_FACET:
            return None
        data_key = MATRIX_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(data_key)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key)
        return None

    def _isotope_labels(self):
        """Real isotope labels for the axes, mass-sorted.

        Reads the classifier's dual-carried raw vocabulary when one is
        upstream: ``selected_isotopes`` gets rewritten to bucket labels by
        the classifier, so building axes from it directly is what produced
        the original all-NaN matrix.
        """
        from results import classifier_view as cv
        labels = cv.raw_isotope_labels(self.input_data)
        if labels:
            return sort_elements_by_mass(labels)
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(cv.composition(p, 'elements', collapsed=False).keys())
        return sort_elements_by_mass(list(all_elems))

    def _group_labels(self, data_key):
        """Classifier groups eligible to sit on the axes under GROUPS role.

        Empty for a diameter data type: the classifier never bucket-collapses
        those (no principled way to sum a diameter across isotopes), so a
        group has no scalar value to correlate and the axes stay
        isotopes-only rather than inventing one.
        """
        from results import classifier_view as cv
        if data_key in _UNSUMMABLE_KEYS:
            return []
        return list(cv.bucket_registry(self.input_data).keys())

    def _get_elements(self):
        sel = self.input_data.get('selected_isotopes', [])
        if sel:
            return sort_elements_by_mass([i['label'] for i in sel])
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(p.get('elements', {}).keys())
        return sort_elements_by_mass(list(all_elems))

    def _min_particles(self):
        """Return the configured Min Particles value, clamped to a usable minimum.

        Returns:
            int: Minimum co-occurring particle count required per element pair.
        """
        try:
            value = int(self.config.get('min_particles', 5))
        except (TypeError, ValueError):
            value = 5
        return max(2, value)

    def _matrix_for(self, particles, data_key):
        """One matrix payload for a set of particles, honouring the role.

        Under GROUPS the axes carry a MIXED vocabulary (real isotopes plus
        classifier groups) and the payload gains triviality masks; under
        COLORS/OFF it is the plain isotope matrix, unchanged from before
        classifier awareness existed.

        Returns:
            dict | None: The payload ``_draw_matrix_ax`` and the header
            consume, or None when there is nothing correlatable.
        """
        from results import classifier_view as cv
        role = self.classifier_role()
        min_particles = self._min_particles()
        zero_mode = self._zero_mode()

        if role == cv.ROLE_SERIES and cv.is_classifier_stream(self.input_data):
            isotopes = self._isotope_labels()
            groups = self._group_labels(data_key)
            # Blocked, not interleaved: isotopes first, then groups, so the
            # three regions of the matrix (isotope x isotope, isotope x
            # group, group x group) are visually separable.
            labels = list(isotopes) + list(groups)
            if len(labels) < 2:
                return None
            scope = self.classifier_scope()
            columns, contributing = build_mixed_columns(
                particles, isotopes, groups, data_key, scope)
            mat, p_mat, counts = correlate_columns(
                columns, labels, min_particles, zero_mode)
            if mat is None:
                return None
            exact, partial = triviality_masks(
                labels, isotopes, groups, contributing, scope)
            return {'elements': labels, 'matrix': mat, 'p_matrix': p_mat,
                    'pair_counts': counts, 'min_particles': min_particles,
                    'n_particles': len(particles),
                    'exact_trivial': exact, 'partial_trivial': partial,
                    'groups': groups, 'isotopes': isotopes,
                    'groups_dropped': bool(data_key in _UNSUMMABLE_KEYS
                                           and cv.bucket_registry(self.input_data))}

        is_clf = cv.is_classifier_stream(self.input_data)
        elements = self._isotope_labels() if is_clf else self._get_elements()
        if len(elements) < 2:
            return None
        # Pure isotope statistic, so a double_count particle must be counted
        # ONCE -- every copy carries the same real composition, and leaving
        # them in silently double-weights that particle's contribution to
        # every Pearson r on this matrix.
        rows = cv.dedupe_particles(particles) if is_clf else particles
        columns = {el: [] for el in elements}
        for p in rows:
            raw = cv.composition(p, data_key, collapsed=False)
            for el in elements:
                columns[el].append(_clean_value(raw.get(el, 0), data_key))
        mat, p_mat, counts = correlate_columns(
            columns, elements, min_particles, zero_mode)
        if mat is None:
            return None
        return {'elements': elements, 'matrix': mat, 'p_matrix': p_mat,
                'pair_counts': counts, 'min_particles': min_particles,
                'n_particles': len(particles)}

    def _extract_single(self, data_key):
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        return self._matrix_for(particles, data_key)

    def _extract_multi(self, data_key):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None
        min_particles = self._min_particles()
        result = {}
        for sn in names:
            sp = [p for p in particles if p.get('source_sample') == sn]
            if len(sp) < min_particles:
                continue
            info = self._matrix_for(sp, data_key)
            if info is not None:
                result[sn] = info
        return result if result else None

    def extract_panel_data(self):
        """PANELS-role data: one correlation matrix per classifier group,
        computed over ONLY that group's particles, with real isotopes on both
        axes -- "for particles belonging to this group, how do their isotopes
        relate?".

        The aggregation scope matters a great deal here, and differently than
        under GROUPS: it decides which isotopes are even eligible for the
        axes. BY DEFINITION restricts them to the isotopes the group's
        expression names -- which for a single-isotope group leaves one label
        and therefore no matrix at all -- while TOTAL PARTICLE admits every
        isotope the qualifying particles carry.

        Returns:
            dict | None: ``{group: matrix_payload}`` for single-sample input,
            ``{group: {sample: matrix_payload}}`` for multi-sample, omitting
            any (group, sample) pair with nothing correlatable so no empty
            panel is ever drawn.
        """
        if not self.input_data:
            return None
        from results import classifier_view as cv
        if not cv.is_classifier_stream(self.input_data):
            return None
        data_key = MATRIX_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        scope = self.classifier_scope()
        min_particles = self._min_particles()
        zero_mode = self._zero_mode()
        itype = self.input_data.get('type')

        def _panel(plist):
            """Isotope-only matrix over one bucket's particles.

            Deduped: a group backed by SEVERAL definitions can, under
            ``double_count``, receive the same real particle once per
            matching definition -- all landing in this one bucket. Left as
            is, that particle would be counted twice inside its own panel.
            """
            plist = cv.dedupe_particles(plist)
            eligible = set()
            for p in plist:
                eligible |= (cv.scope_isotopes(p, scope)
                             & set(cv.composition(p, 'elements', collapsed=False)))
            labels = sort_elements_by_mass(list(eligible))
            if len(labels) < 2:
                return None
            columns = {el: [] for el in labels}
            for p in plist:
                raw = cv.composition(p, data_key, collapsed=False)
                for el in labels:
                    columns[el].append(_clean_value(raw.get(el, 0), data_key))
            mat, p_mat, counts = correlate_columns(
                columns, labels, min_particles, zero_mode)
            if mat is None:
                return None
            return {'elements': labels, 'matrix': mat, 'p_matrix': p_mat,
                    'pair_counts': counts, 'min_particles': min_particles,
                    'n_particles': len(plist)}

        def _by_group(plist):
            out = {}
            for label, members in cv.particles_by_bucket(
                    plist, include_unclassified=True).items():
                if label is None or not members:
                    continue  # passthrough carries no bucket to panel by
                info = _panel(members)
                if info is not None:
                    out[label] = info
            return out

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data') or []
            return _by_group(particles) or None

        if itype == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            grouped = {n: [] for n in names}
            for p in particles:
                if p.get('source_sample') in grouped:
                    grouped[p['source_sample']].append(p)
            result = {}
            for sn in names:
                for label, info in _by_group(grouped[sn]).items():
                    result.setdefault(label, {})[sn] = info
            return result or None
        return None


