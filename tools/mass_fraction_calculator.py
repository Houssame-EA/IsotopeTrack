from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QGroupBox, QMessageBox,
    QHeaderView, QSplitter, QTextEdit, QTabWidget,
    QSpinBox, QDoubleSpinBox, QFrame, QProgressBar,
    QFileDialog, QListWidget, QListWidgetItem, QWidget,
    QRadioButton, QButtonGroup, QStyledItemDelegate,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QFont, QColor, QDesktopServices, QDoubleValidator
from PySide6.QtCore import QUrl
import logging
import re
import pandas as pd
from pathlib import Path
from functools import reduce
from math import gcd

from theme import theme

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formula parsing – supports parentheses, e.g. Ca(OH)2, Al2(SO4)3
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'([A-Z][a-z]?|\(|\))(\d*(?:\.\d+)?)')


def _parse_formula_to_counts(formula: str) -> dict:
    """Parse a chemical formula string into {element: integer_count}.

    Handles parenthesised groups such as Ca(OH)2 → {'Ca': 1, 'O': 2, 'H': 2}.
    Nested parentheses are supported.

    Args:
        formula: Chemical formula string.

    Returns:
        dict mapping element symbols to positive integer counts.
    """
    if not formula or not isinstance(formula, str):
        return {}

    stack: list[dict] = [{}]

    for token, num_str in _TOKEN_RE.findall(formula):
        if token == '(':
            stack.append({})
        elif token == ')':
            if len(stack) < 2:
                continue
            multiplier = _safe_int(num_str, default=1)
            top = stack.pop()
            for el, cnt in top.items():
                stack[-1][el] = stack[-1].get(el, 0) + cnt * multiplier
        else:
            n = _safe_int(num_str, default=1)
            stack[-1][token] = stack[-1].get(token, 0) + n

    while len(stack) > 1:
        top = stack.pop()
        for el, cnt in top.items():
            stack[-1][el] = stack[-1].get(el, 0) + cnt

    return {k: v for k, v in stack[0].items() if v > 0}


def _safe_int(s: str, *, default: int = 1) -> int:
    """Convert a numeric string to a positive int, rounding floats.
    Args:
        s (str): The s.
        default (int): The default.
    Returns:
        int: Result of the operation.
    """
    if not s:
        return default
    try:
        return max(int(round(float(s))), 0) or default
    except (ValueError, TypeError):
        return default


_ELEMENT_ORDER_RE = re.compile(r'([A-Z][a-z]?)')


def _element_order_in_formula(formula: str) -> list[str]:
    """Return elements in the order they first appear in *formula*.
    Args:
        formula (str): The formula.
    Returns:
        list[str]: Result of the operation.
    """
    seen: set[str] = set()
    order: list[str] = []
    for el in _ELEMENT_ORDER_RE.findall(str(formula)):
        if el not in seen:
            seen.add(el)
            order.append(el)
    return order


def _reduce_counts(counts: dict) -> dict:
    """Divide all counts by their GCD to get the empirical formula.
    Args:
        counts (dict): The counts.
    Returns:
        dict: Result of the operation.
    """
    if not counts:
        return counts
    nums = [abs(int(v)) for v in counts.values() if int(v) != 0]
    if not nums:
        return counts
    g = reduce(gcd, nums)
    if g <= 1:
        return counts
    return {k: v // g for k, v in counts.items()}


def _signature_from_counts(counts: dict) -> str:
    """Order-independent canonical key for matching equivalent formulas.
    Args:
        counts (dict): The counts.
    Returns:
        str: Result of the operation.
    """
    if not counts:
        return ''
    return '|'.join(f'{el}{n}' for el, n in sorted(counts.items()))


def _join_formula_from_counts(counts: dict, prefer_order: list[str] | None = None) -> str:
    """Build a human-readable formula string from counts.
    Args:
        counts (dict): The counts.
        prefer_order (list[str] | None): The prefer order.
    Returns:
        str: Result of the operation.
    """
    if not counts:
        return ''
    if prefer_order:
        rest = sorted(e for e in counts if e not in prefer_order)
        ordered = list(dict.fromkeys(list(prefer_order) + rest))
    else:
        ordered = sorted(counts)
    parts = []
    for el in ordered:
        n = counts.get(el, 0)
        if n <= 0:
            continue
        parts.append(el if n == 1 else f'{el}{n}')
    return ''.join(parts)


def canonicalize_preserve_user_order(formula: str) -> str:
    """Reduce stoichiometry but preserve the user's element order.
    Args:
        formula (str): The formula.
    Returns:
        str: Result of the operation.
    """
    counts = _reduce_counts(_parse_formula_to_counts(formula))
    order = _element_order_in_formula(formula)
    return _join_formula_from_counts(counts, prefer_order=order)


# ---------------------------------------------------------------------------
# CSV compound database
# ---------------------------------------------------------------------------

class CSVCompoundDatabase:
    """Database loader for materials from CSV with signature-based lookup."""

    def __init__(self):
        self.data: pd.DataFrame | None = None
        self.formula_to_data: dict[str, list[dict]] = {}
        self.element_to_compounds: dict[str, dict[str, float]] = {}
        self.signature_to_formula: dict[str, str] = {}
        self.signature_to_data: dict[str, list[dict]] = {}
        self.is_loaded: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def auto_load_csv(self) -> bool:
        """Try to load CSV from standard locations, preferring trimmed/compressed versions.

        Handles both normal execution and PyInstaller frozen bundles
        (where data files live under sys._MEIPASS).
        Returns:
            bool: Result of the operation.
        """
        import sys

        base_dirs = []

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dirs.append(Path(sys._MEIPASS) / 'data')

        base_dirs.extend([
            Path(__file__).resolve().parent / 'data',
            Path(__file__).resolve().parent.parent / 'data',
            Path.cwd() / 'data',
        ])

        filenames = [
            'materials_trimmed.csv.gz',
        ]
        for base in base_dirs:
            for fname in filenames:
                p = base / fname
                if p.exists():
                    logger.info("Found CSV at %s", p)
                    return self.load_csv(p)
        logger.warning("No CSV file found in standard locations")
        return False

    def load_csv(self, csv_path: str | Path) -> bool:
        """Load CSV and build signature-based indices.

        Uses ``itertuples()`` for ~5-10× speed-up over ``iterrows()``.
        Args:
            csv_path (str | Path): The csv path.
        Returns:
            bool: Result of the operation.
        """
        if self.is_loaded:
            return True
        try:
            csv_path = Path(csv_path)
            logger.info("Loading CSV from %s", csv_path)
            self.data = pd.read_csv(csv_path)
            logger.info("CSV loaded with %d rows", len(self.data))

            self.formula_to_data.clear()
            self.element_to_compounds.clear()
            self.signature_to_formula.clear()
            self.signature_to_data.clear()

            for col in ('formula', 'density', 'material_id', 'mp_url', 'space_group'):
                if col not in self.data.columns:
                    self.data[col] = ''

            processed = 0

            for row in self.data.itertuples(index=False):
                try:
                    raw_formula = getattr(row, 'formula', '')
                    if not isinstance(raw_formula, str) or not raw_formula.strip():
                        continue
                    raw_formula = raw_formula.strip()

                    density_raw = getattr(row, 'density', None)
                    density = float(density_raw) if density_raw is not None and pd.notna(density_raw) else 0.0

                    mid_raw = getattr(row, 'material_id', '')
                    material_id = str(mid_raw).strip() if pd.notna(mid_raw) else ''

                    url_raw = getattr(row, 'mp_url', '')
                    mp_url = str(url_raw).strip() if pd.notna(url_raw) else ''
                    if not mp_url and material_id:
                        mp_url = f"https://materialsproject.org/materials/{material_id}"

                    sg_raw = getattr(row, 'space_group', '')
                    space_group = str(sg_raw) if pd.notna(sg_raw) else ''

                    material_data = {
                        'material_id': material_id,
                        'density': density,
                        'formula': raw_formula,
                        'space_group': space_group,
                        'mp_url': mp_url,
                    }

                    self.formula_to_data.setdefault(raw_formula, []).append(material_data)

                    counts = _reduce_counts(_parse_formula_to_counts(raw_formula))
                    if not counts:
                        continue
                    sig = _signature_from_counts(counts)

                    self.signature_to_formula.setdefault(sig, raw_formula)
                    self.signature_to_data.setdefault(sig, []).append(material_data)

                    canon_display = self.signature_to_formula[sig]
                    for element in counts:
                        bucket = self.element_to_compounds.setdefault(element, {})
                        best = bucket.get(canon_display, 0.0)
                        bucket[canon_display] = density if density > 0 else best

                    processed += 1
                except Exception:
                    logger.debug("Skipping row during CSV indexing", exc_info=True)
                    continue

            self.is_loaded = True
            logger.info(
                "Database loaded: %d rows processed, %d canonical compounds indexed",
                processed, len(self.signature_to_formula),
            )
            return True

        except Exception:
            logger.exception("Error loading CSV")
            return False

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _signature_for_formula(self, formula: str) -> str:
        """
        Args:
            formula (str): The formula.
        Returns:
            str: Result of the operation.
        """
        return _signature_from_counts(_reduce_counts(_parse_formula_to_counts(formula)))

    def get_data_by_formula_or_signature(self, formula: str) -> list[dict]:
        """
        Args:
            formula (str): The formula.
        Returns:
            list[dict]: Result of the operation.
        """
        return self.signature_to_data.get(self._signature_for_formula(formula), [])

    def best_density_for_formula(self, formula: str) -> float:
        """
        Args:
            formula (str): The formula.
        Returns:
            float: Result of the operation.
        """
        for r in self.get_data_by_formula_or_signature(formula):
            if r.get('density', 0) > 0:
                return float(r['density'])
        return 0.0

    def best_url_for_formula(self, formula: str) -> str:
        """
        Args:
            formula (str): The formula.
        Returns:
            str: Result of the operation.
        """
        for r in self.get_data_by_formula_or_signature(formula):
            url = (r.get('mp_url') or '').strip()
            if url:
                return url
        for r in self.get_data_by_formula_or_signature(formula):
            mid = (r.get('material_id') or '').strip()
            if mid:
                return f"https://materialsproject.org/materials/{mid}"
        canon = canonicalize_preserve_user_order(formula)
        return f"https://materialsproject.org/?search={canon}"

    def get_compounds_for_element(self, element: str) -> list[dict]:
        """Get one entry per canonical formula for initial browsing.

        For multi-polymorph formulas, this shows the first density found.
        Use get_variants_for_formula() to expand into all polymorphs.
        Args:
            element (str): The element.
        Returns:
            list[dict]: Result of the operation.
        """
        if element not in self.element_to_compounds:
            return []
        compounds = []
        for display_formula, dens in self.element_to_compounds[element].items():
            sig = self._signature_for_formula(display_formula)
            n_variants = len(self.signature_to_data.get(sig, []))
            if dens > 0:
                display_text = f"{display_formula} ({dens:.3f} g/cm³)"
            else:
                display_text = display_formula
            if n_variants > 1:
                display_text += f"  [{n_variants} structures]"
            compounds.append({
                'formula': display_formula,
                'density': float(dens),
                'display_text': display_text,
            })
        compounds.sort(key=lambda x: x['formula'])
        return compounds

    def get_variants_for_formula(self, formula: str) -> list[dict]:
        """Get ALL polymorphs/structures for a given formula.

        Returns one entry per material_id, each with its own density,
        space group, and URL — so the user can pick the right polymorph.
        Args:
            formula (str): The formula.
        """
        sig = self._signature_for_formula(formula)
        rows = self.signature_to_data.get(sig, [])
        if not rows:
            return []

        canon = canonicalize_preserve_user_order(formula)
        variants = []
        seen_ids = set()

        for r in rows:
            mid = r.get('material_id', '')
            if mid in seen_ids:
                continue
            seen_ids.add(mid)

            dens = r.get('density', 0.0)
            sg = r.get('space_group', '')

            parts = [canon]
            if sg:
                parts.append(f"[{sg}]")
            if dens > 0:
                parts.append(f"({dens:.3f} g/cm³)")
            if mid:
                parts.append(f"— {mid}")

            variants.append({
                'formula': canon,
                'density': float(dens),
                'space_group': sg,
                'material_id': mid,
                'mp_url': r.get('mp_url', ''),
                'display_text': ' '.join(parts),
            })

        variants.sort(key=lambda x: (x['space_group'], -x['density']))
        return variants

    def get_material_data(self, formula: str) -> list[dict]:
        """
        Args:
            formula (str): The formula.
        Returns:
            list[dict]: Result of the operation.
        """
        return self.formula_to_data.get(formula, [])


# ---------------------------------------------------------------------------
# FormulaComboBox – editable combo with live filtering
# ---------------------------------------------------------------------------

class FormulaComboBox(QComboBox):
    """Editable combobox for chemical formulas with debounced filtering.

    Key design decisions that prevent the old recursion crash:
    1. Both the combobox AND lineEdit signals are blocked during rebuilds
    2. Filtering is debounced (300 ms) so rapid typing doesn't queue rebuilds
    3. Only the top MAX_DROPDOWN_ITEMS matches are shown, not thousands
    4. Minimum 2 characters before filtering starts (avoids huge result sets)
    """

    formula_selected = Signal(str, float)

    MAX_DROPDOWN_ITEMS = 50
    MIN_FILTER_CHARS = 2
    DEBOUNCE_MS = 300

    def __init__(self, element: str, csv_database: CSVCompoundDatabase,
                 tracked_elements: set[str] | None = None, parent=None):
        """
        Args:
            element (str): The element.
            csv_database (CSVCompoundDatabase): The csv database.
            tracked_elements (set[str] | None): The tracked elements.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.element = element
        self.csv_database = csv_database
        self.tracked_elements = tracked_elements or set()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(15)
        self.lineEdit().setPlaceholderText("Type a formula (e.g., TiO2)")

        self.setCompleter(None)

        self._updating = False
        self._all_items: list[dict] = []

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._do_filter)

        self._setup_compounds()

        self.activated[int].connect(self._on_item_activated)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)
        self.lineEdit().textChanged.connect(self._on_text_changed)

    # -- population --------------------------------------------------------

    def _setup_compounds(self):
        """Build the full item list but only load a capped subset into the widget."""
        self._all_items.clear()
        self._all_items.append({'display_text': self.element, 'formula': self.element})
        if self.csv_database.is_loaded:
            for c in self.csv_database.get_compounds_for_element(self.element):
                self._all_items.append({
                    'display_text': c['display_text'],
                    'formula': c['formula'],
                })
        self._rebuild_items(self._all_items[:self.MAX_DROPDOWN_ITEMS])
        self._set_editor_text(self.element)

    def _rebuild_items(self, items: list[dict]):
        """Replace dropdown items, blocking ALL signals to prevent recursion.

        Each item dict must have 'display_text' and 'formula'.
        Optionally 'density' (float) — stored alongside formula in itemData.
        Args:
            items (list[dict]): Sequence of items.
        """
        self._updating = True
        self.blockSignals(True)
        self.lineEdit().blockSignals(True)
        try:
            current_text = self.lineEdit().text()
            self.clear()
            for it in items:
                density = it.get('density', 0.0)
                self.addItem(it['display_text'], (it['formula'], density))
            self.lineEdit().setText(current_text)
        finally:
            self.lineEdit().blockSignals(False)
            self.blockSignals(False)
            self._updating = False

    # -- filtering ---------------------------------------------------------

    def _do_filter(self):
        """Actually perform the filter (called by debounce timer)."""
        typed = (self.lineEdit().text() or '').strip()
        if len(typed) < self.MIN_FILTER_CHARS:
            self._rebuild_items(self._all_items[:self.MAX_DROPDOWN_ITEMS])
            return

        typed_canon = canonicalize_preserve_user_order(typed)
        variants = self.csv_database.get_variants_for_formula(typed_canon)
        if variants:
            self._rebuild_items(variants[:self.MAX_DROPDOWN_ITEMS])
            return

        needle = typed.lower()
        scored: list[tuple[int, dict]] = []
        for it in self._all_items:
            fl = it['formula'].lower()
            dl = it['display_text'].lower()
            if fl.startswith(needle):
                scored.append((0, it))
            elif needle in fl:
                scored.append((1, it))
            elif needle in dl:
                scored.append((2, it))

        scored.sort(key=lambda x: x[0])
        filtered = [it for _, it in scored[:self.MAX_DROPDOWN_ITEMS]]

        if not filtered:
            filtered = self._all_items[:self.MAX_DROPDOWN_ITEMS]

        self._rebuild_items(filtered)

    def filter_to_formula(self, user_canon_formula: str):
        """Show all polymorphs/structures for the confirmed formula.
        Args:
            user_canon_formula (str): The user canon formula.
        """
        variants = self.csv_database.get_variants_for_formula(user_canon_formula)
        if variants:
            self._rebuild_items(variants[:self.MAX_DROPDOWN_ITEMS])
        else:
            dens = self.csv_database.best_density_for_formula(user_canon_formula)
            display = f"{user_canon_formula} ({dens:.3f} g/cm³)" if dens > 0 else user_canon_formula
            self._rebuild_items([{
                'display_text': display,
                'formula': user_canon_formula,
                'density': dens,
            }])
        self._set_editor_text(user_canon_formula)

    def reset_items(self):
        """Restore the capped default list."""
        self._rebuild_items(self._all_items[:self.MAX_DROPDOWN_ITEMS])

    # -- helpers -----------------------------------------------------------

    def _set_editor_text(self, text: str):
        """Set the lineEdit text without triggering any slots.
        Args:
            text (str): Text string.
        """
        self._updating = True
        self.lineEdit().blockSignals(True)
        try:
            self.lineEdit().setText(text)
        finally:
            self.lineEdit().blockSignals(False)
            self._updating = False

    def current_formula(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        text = (self.lineEdit().text() or '').strip()
        if not text:
            return self.element
        return canonicalize_preserve_user_order(text)

    # -- slots -------------------------------------------------------------

    def _on_text_changed(self, text: str):
        """Debounce: restart timer on every keystroke, filter when typing pauses.
        Args:
            text (str): Text string.
        """
        if self._updating:
            return
        self._debounce_timer.start()

    def _on_item_activated(self, index: int):
        """
        Args:
            index (int): Row or item index.
        """
        if self._updating:
            return
        self._debounce_timer.stop()

        data = self.itemData(index)
        if isinstance(data, tuple) and len(data) == 2:
            picked_formula, picked_density = data
        elif isinstance(data, str):
            picked_formula = data
            picked_density = 0.0
        else:
            picked_formula = (self.lineEdit().text() or '').strip()
            picked_density = 0.0

        user_canon = canonicalize_preserve_user_order(picked_formula)
        dens = picked_density if picked_density > 0 else self.csv_database.best_density_for_formula(user_canon)
        self._set_editor_text(user_canon)

        counts = _reduce_counts(_parse_formula_to_counts(user_canon))
        if len(counts) >= 2:
            self.filter_to_formula(user_canon)
        else:
            self.reset_items()

        self.formula_selected.emit(user_canon, dens)

    def _on_editing_finished(self):
        if self._updating:
            return
        self._debounce_timer.stop()

        typed = (self.lineEdit().text() or '').strip()
        if not typed:
            self._set_editor_text(self.element)
            self.reset_items()
            self.formula_selected.emit(self.element, 0.0)
            return

        user_canon = canonicalize_preserve_user_order(typed)
        dens = self.csv_database.best_density_for_formula(user_canon)
        self._set_editor_text(user_canon)

        counts = _reduce_counts(_parse_formula_to_counts(user_canon))
        if len(counts) >= 2:
            self.filter_to_formula(user_canon)
        else:
            self.reset_items()

        self.formula_selected.emit(user_canon, dens)


# ---------------------------------------------------------------------------
# Sample list item
# ---------------------------------------------------------------------------

class CheckableListItem(QWidget):
    """Compact widget with checkbox + label for sample list."""

    def __init__(self, sample_name: str, parent=None):
        """
        Args:
            sample_name (str): The sample name.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.sample_name = sample_name

        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 2, 5, 2)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.label = QLabel(sample_name)

        lay.addWidget(self.checkbox)
        lay.addWidget(self.label)
        lay.addStretch()

    def is_checked(self) -> bool:
        """
        Returns:
            bool: Result of the operation.
        """
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        """
        Args:
            checked (bool): Whether the item is checked.
        """
        self.checkbox.setChecked(checked)


# ---------------------------------------------------------------------------
# Validated density delegate (for editable compound-density column)
# ---------------------------------------------------------------------------

class _PositiveDoubleDelegate(QStyledItemDelegate):
    """Only accept positive floats when editing density cells."""

    def createEditor(self, parent, option, index):
        """
        Args:
            parent (Any): Parent widget or object.
            option (Any): The option.
            index (Any): Row or item index.
        Returns:
            object: Result of the operation.
        """
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator(0.0, 1e6, 6, editor))
        return editor

    def setEditorData(self, editor, index):
        """
        Args:
            editor (Any): The editor.
            index (Any): Row or item index.
        """
        editor.setText(index.data(Qt.DisplayRole) or '')

    def setModelData(self, editor, model, index):
        """
        Args:
            editor (Any): The editor.
            model (Any): Data model object.
            index (Any): Row or item index.
        """
        text = editor.text().strip()
        try:
            val = float(text)
            if val < 0:
                raise ValueError
        except ValueError:
            return
        model.setData(index, f"{val:.6f}", Qt.EditRole)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class MassFractionCalculator(QDialog):
    """Mass fraction calculator with sample selection and molecular weight calculations."""

    mass_fractions_updated = Signal(dict)

    COL_ELEMENT = 0
    COL_FORMULA = 1
    COL_MASSFRAC = 2
    COL_MW = 3
    COL_ELEM_DENS = 4
    COL_COMP_DENS = 5
    COL_STRUCTURE = 6

    def __init__(self, selected_isotopes: dict, periodic_table_widget, parent=None):
        """
        Args:
            selected_isotopes (dict): The selected isotopes.
            periodic_table_widget (Any): The periodic table widget.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.selected_isotopes = selected_isotopes
        self.periodic_table_widget = periodic_table_widget
        self.parent_window = parent
        self.mass_fractions: dict[str, float] = {}
        self.densities: dict[str, float] = {}
        self.molecular_weights: dict[str, float] = {}

        self.tracked_elements: set[str] = set(selected_isotopes.keys())

        self.available_samples: list[str] = []
        if parent and hasattr(parent, 'sample_to_folder_map'):
            self.available_samples = list(parent.sample_to_folder_map.keys())

        self.csv_database: CSVCompoundDatabase = getattr(parent, '_cached_csv_database', None)
        if self.csv_database is None:
            self.csv_database = CSVCompoundDatabase()
            self.csv_database.auto_load_csv()
            if parent is not None:
                try:
                    parent._cached_csv_database = self.csv_database
                except AttributeError:
                    pass

        self.periodic_table_data = (
            periodic_table_widget.get_elements() if periodic_table_widget else []
        )

        self.setWindowTitle("Mass Fraction Calculator")
        self.setMinimumSize(1100, 550)
        self.resize(1500, 700)

        self._setup_ui()
        self._populate_table()
        self._restore_previous_state()

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply the currently active theme palette to this dialog."""
        self.setStyleSheet(self._build_stylesheet())
        if hasattr(self, 'db_status_label'):
            self._refresh_db_status_style()
        if hasattr(self, '_apply_btn'):
            self._refresh_apply_button_style()

    def closeEvent(self, event):
        """Disconnect theme signal so we don't leak slots on closed dialogs.
        Args:
            event (Any): Qt event object.
        """
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)

    def _build_stylesheet(self) -> str:
        """Dark/light aware stylesheet for the whole dialog.
        Returns:
            str: Result of the operation.
        """
        p = theme.palette
        return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QWidget {{
            color: {p.text_primary};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QGroupBox {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 8px;
            color: {p.text_primary};
        }}

        /* Sample list — the main source of the white area in dark mode */
        QListWidget {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 2px;
            outline: 0;
        }}
        QListWidget::item {{
            color: {p.text_primary};
            padding: 2px;
            border-radius: 3px;
        }}
        QListWidget::item:hover {{
            background-color: {p.bg_hover};
        }}
        QListWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}

        /* Checkboxes inside the sample list and elsewhere */
        QCheckBox {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 1px solid {p.border};
            background-color: {p.bg_tertiary};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {p.accent};
            background-color: {p.accent};
        }}

        /* Radio buttons for Apply Options */
        QRadioButton {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
            padding: 2px;
        }}
        QRadioButton::indicator {{
            width: 14px;
            height: 14px;
        }}
        QRadioButton::indicator:unchecked {{
            border: 2px solid {p.border};
            border-radius: 8px;
            background-color: {p.bg_tertiary};
        }}
        QRadioButton::indicator:checked {{
            border: 2px solid {p.accent};
            border-radius: 8px;
            background-color: {p.accent};
        }}

        /* Table */
        QTableWidget {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            alternate-background-color: {p.bg_tertiary};
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QTableWidget::item {{
            padding: 4px;
            color: {p.text_primary};
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
        QHeaderView {{
            background-color: {p.bg_tertiary};
            border: none;
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px 8px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}

        /* Inputs */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 18px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}

        /* Buttons (default styling — Apply button overrides below) */
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
            color: {p.text_inverse};
        }}
        QPushButton:disabled {{
            color: {p.text_muted};
            background-color: {p.bg_secondary};
        }}

        /* Splitter handle — otherwise a bright light bar in dark mode */
        QSplitter::handle {{
            background-color: {p.border};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background: {p.bg_primary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.text_muted};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {p.bg_primary};
            height: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        """

    def _refresh_db_status_style(self):
        p = theme.palette
        if self.csv_database.is_loaded:
            color = p.success
        else:
            color = p.warning
        self.db_status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
        )

    def _refresh_apply_button_style(self):
        p = theme.palette
        self._apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {p.accent};
                color: {p.text_inverse};
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.accent_pressed};
            }}
        """)


    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # ---- left panel: sample selection ----------------------------
        left_panel = self._build_sample_panel()

        # ---- right panel: table + buttons ----------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addLayout(self._build_header())
        self._build_table()
        right_layout.addWidget(self.table)
        right_layout.addLayout(self._build_buttons())

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1200])

        main_layout.addWidget(splitter)

    # -- sub-builders --------------------------------------------------

    def _build_sample_panel(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        panel = QGroupBox("Sample Selection")
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)

        btn_row = QHBoxLayout()
        sa = QPushButton("Select All")
        sa.clicked.connect(self._select_all_samples)
        sn = QPushButton("Select None")
        sn.clicked.connect(self._select_no_samples)
        btn_row.addWidget(sa)
        btn_row.addWidget(sn)
        layout.addLayout(btn_row)

        lbl = QLabel(f"Available Samples ({len(self.available_samples)}):")
        lbl.setStyleSheet("font-weight: bold; margin: 5px 0;")
        layout.addWidget(lbl)

        self.sample_list = QListWidget()
        self.sample_list.setMaximumHeight(400)
        for name in self.available_samples:
            item = QListWidgetItem()
            widget = CheckableListItem(name)
            item.setSizeHint(widget.sizeHint())
            self.sample_list.addItem(item)
            self.sample_list.setItemWidget(item, widget)
        layout.addWidget(self.sample_list)

        apply_group = QGroupBox("Apply Options")
        apply_layout = QVBoxLayout(apply_group)

        self._apply_btn_group = QButtonGroup(self)
        self.radio_selected = QRadioButton("Apply to selected samples only")
        self.radio_all = QRadioButton("Apply to all samples (global)")
        self.radio_selected.setChecked(True)
        self._apply_btn_group.addButton(self.radio_selected, 0)
        self._apply_btn_group.addButton(self.radio_all, 1)
        apply_layout.addWidget(self.radio_selected)
        apply_layout.addWidget(self.radio_all)

        layout.addWidget(apply_group)
        layout.addStretch()
        return panel

    def _build_header(self) -> QHBoxLayout:
        """
        Returns:
            QHBoxLayout: Result of the operation.
        """
        header = QHBoxLayout()

        title = QLabel("Mass Fraction Calculator")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")
        header.addWidget(title)
        header.addStretch()

        if self.csv_database.is_loaded:
            n = len(self.csv_database.signature_to_formula)
            txt = f"database: {n}"
        else:
            txt = "database: Not found"

        self.db_status_label = QLabel(txt)
        header.addWidget(self.db_status_label)

        if not self.csv_database.is_loaded:
            load_btn = QPushButton("Load CSV")
            load_btn.clicked.connect(self._manual_load_csv)
            header.addWidget(load_btn)

        return header

    def _build_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Element',
            'Compound Formula',
            'Mass Fraction',
            'Molecular Weight\n(g/mol)',
            'Element Density\n(g/cm³)',
            'Compound Density\n(g/cm³)',
            'Structure',
        ])

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ELEMENT, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_FORMULA, QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_MASSFRAC, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_MW, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_ELEM_DENS, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_COMP_DENS, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_STRUCTURE, QHeaderView.Fixed)

        self.table.setColumnWidth(self.COL_ELEMENT, 80)
        self.table.setColumnWidth(self.COL_MASSFRAC, 120)
        self.table.setColumnWidth(self.COL_MW, 140)
        self.table.setColumnWidth(self.COL_ELEM_DENS, 140)
        self.table.setColumnWidth(self.COL_COMP_DENS, 160)
        self.table.setColumnWidth(self.COL_STRUCTURE, 110)

        self.table.setItemDelegateForColumn(
            self.COL_COMP_DENS, _PositiveDoubleDelegate(self.table)
        )

    def _build_buttons(self) -> QHBoxLayout:
        """
        Returns:
            QHBoxLayout: Result of the operation.
        """
        layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Pure Elements")
        reset_btn.clicked.connect(self._reset_to_default)
        layout.addWidget(reset_btn)

        calc_btn = QPushButton("Calculate All Mass Fractions")
        calc_btn.clicked.connect(self._calculate_all)
        layout.addWidget(calc_btn)

        layout.addStretch()

        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self._apply_mass_fractions)
        self._apply_btn = apply_btn
        layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        return layout


    def _populate_table(self):
        sorted_elems = []
        for element in self.selected_isotopes:
            ed = self._element_data(element)
            if ed:
                sorted_elems.append((ed['atomic_number'], element, ed))
        sorted_elems.sort()
        self.table.setRowCount(len(sorted_elems))

        for row, (_, element, ed) in enumerate(sorted_elems):
            el_item = QTableWidgetItem(element)
            el_item.setFlags(el_item.flags() & ~Qt.ItemIsEditable)
            el_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_ELEMENT, el_item)

            combo = FormulaComboBox(
                element, self.csv_database,
                tracked_elements=self.tracked_elements,
                parent=self,
            )
            combo.formula_selected.connect(lambda f, d, r=row: self._on_compound_selected(r, f, d))
            self.table.setCellWidget(row, self.COL_FORMULA, combo)

            mf = self._make_readonly_item("1.000000")
            self.table.setItem(row, self.COL_MASSFRAC, mf)

            mass = float(ed.get('mass', 0))
            self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mass:.6f}"))

            edens = float(ed.get('density', 0) or 0)
            self.table.setItem(row, self.COL_ELEM_DENS, self._make_readonly_item(f"{edens:.6f}"))

            cd_item = QTableWidgetItem(f"{edens:.6f}")
            cd_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_COMP_DENS, cd_item)

            btn = QPushButton("Open")
            btn.setToolTip("Open structure page on Materials Project")
            btn.clicked.connect(lambda _, r=row: self._open_structure(r))
            self.table.setCellWidget(row, self.COL_STRUCTURE, btn)

    @staticmethod
    def _make_readonly_item(text: str) -> QTableWidgetItem:
        """
        Args:
            text (str): Text string.
        Returns:
            QTableWidgetItem: Result of the operation.
        """
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        return item


    def _element_data(self, symbol: str) -> dict | None:
        """
        Args:
            symbol (str): The symbol.
        Returns:
            dict | None: Result of the operation.
        """
        for e in self.periodic_table_data:
            if e['symbol'] == symbol:
                return e
        return None

    def _current_formula(self, row: int) -> str:
        """
        Args:
            row (int): Row index.
        Returns:
            str: Result of the operation.
        """
        combo = self.table.cellWidget(row, self.COL_FORMULA)
        return combo.current_formula() if combo else ''

    def _calc_mass_fraction(self, row: int, formula: str):
        """
        Args:
            row (int): Row index.
            formula (str): The formula.
        """
        el_item = self.table.item(row, self.COL_ELEMENT)
        if not el_item:
            return
        element = el_item.text()

        counts = _reduce_counts(_parse_formula_to_counts(formula))
        if not counts:
            mf = 1.0
        else:
            total = target = 0.0
            unknown_element = False
            for el, n in counts.items():
                ed = self._element_data(el)
                if ed:
                    m = float(ed['mass']) * n
                    total += m
                    if el == element:
                        target += m
                else:
                    unknown_element = True
            if unknown_element:
                logger.warning("Formula '%s' contains element(s) not in periodic table data", formula)
            mf = (target / total) if total > 0 and target > 0 else 1.0

        self.table.setItem(row, self.COL_MASSFRAC, self._make_readonly_item(f"{mf:.6f}"))

    def _calc_molecular_weight(self, row: int, formula: str):
        """
        Args:
            row (int): Row index.
            formula (str): The formula.
        """
        counts = _reduce_counts(_parse_formula_to_counts(formula))
        mw = 0.0
        valid = bool(counts)
        for el, n in counts.items():
            ed = self._element_data(el)
            if ed:
                mw += float(ed['mass']) * n
            else:
                valid = False
                break

        if not valid or mw <= 0:
            el_item = self.table.item(row, self.COL_ELEMENT)
            if el_item:
                ed = self._element_data(el_item.text())
                mw = float(ed['mass']) if ed else 0.0
            else:
                mw = 0.0

        self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mw:.6f}"))

    def _on_compound_selected(self, row: int, formula: str, density_csv: float):
        """
        Args:
            row (int): Row index.
            formula (str): The formula.
            density_csv (float): The density csv.
        """
        self._calc_mass_fraction(row, formula)
        self._calc_molecular_weight(row, formula)

        counts = _reduce_counts(_parse_formula_to_counts(formula))
        if len(counts) <= 1:
            el_item = self.table.item(row, self.COL_ELEMENT)
            ed = self._element_data(el_item.text()) if el_item else None
            d = float(ed.get('density', 0) or 0) if ed else 0.0
        else:
            d = float(density_csv or 0.0)

        cd_item = QTableWidgetItem(f"{d:.6f}")
        cd_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, self.COL_COMP_DENS, cd_item)

        self._highlight_tracked(row, formula)

    def _highlight_tracked(self, row: int, formula: str):
        """Set a tooltip showing which elements in the compound are being tracked.
        Args:
            row (int): Row index.
            formula (str): The formula.
        """
        counts = _parse_formula_to_counts(formula)
        tracked_in = sorted(set(counts.keys()) & self.tracked_elements)
        other = sorted(set(counts.keys()) - self.tracked_elements)

        combo = self.table.cellWidget(row, self.COL_FORMULA)
        if combo and len(counts) >= 2:
            parts = []
            if tracked_in:
                parts.append(f"Tracked: {', '.join(tracked_in)}")
            if other:
                parts.append(f"Not tracked: {', '.join(other)}")
            combo.setToolTip('\n'.join(parts))

    def _calculate_all(self):
        for row in range(self.table.rowCount()):
            f = self._current_formula(row)
            if f:
                self._calc_mass_fraction(row, f)
                self._calc_molecular_weight(row, f)

    def _reset_to_default(self):
        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, self.COL_ELEMENT)
            combo = self.table.cellWidget(row, self.COL_FORMULA)
            if not el_item or not combo:
                continue
            element = el_item.text()
            ed = self._element_data(element)

            combo._set_editor_text(element)
            combo.reset_items()
            combo.formula_selected.emit(element, 0.0)

            self.table.setItem(row, self.COL_MASSFRAC, self._make_readonly_item("1.000000"))
            mass = float(ed['mass']) if ed else 0.0
            self.table.setItem(row, self.COL_MW, self._make_readonly_item(f"{mass:.6f}"))
            d = float(ed.get('density', 0) or 0) if ed else 0.0
            cd = QTableWidgetItem(f"{d:.6f}")
            cd.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_COMP_DENS, cd)


    def _select_all_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(True)

    def _select_no_samples(self):
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(False)

    def _get_selected_samples(self) -> list[str]:
        """
        Returns:
            list[str]: Result of the operation.
        """
        out = []
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w and w.is_checked():
                out.append(w.sample_name)
        return out


    def _save_state(self):
        if not self.parent_window:
            return
        state: dict = {
            'mass_fractions': {},
            'densities': {},
            'molecular_weights': {},
            'formulas': {},
            'selected_samples': self._get_selected_samples(),
            'apply_to_all': self.radio_all.isChecked(),
        }
        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            combo = self.table.cellWidget(row, self.COL_FORMULA)
            if combo:
                state['formulas'][element] = combo.current_formula()

            for col, key in [
                (self.COL_MASSFRAC, 'mass_fractions'),
                (self.COL_MW, 'molecular_weights'),
                (self.COL_COMP_DENS, 'densities'),
            ]:
                cell = self.table.item(row, col)
                if cell:
                    try:
                        state[key][element] = float(cell.text())
                    except ValueError:
                        pass

        self.parent_window._mass_fraction_calculator_state = state

    def _restore_previous_state(self):
        if not self.parent_window:
            return
        state = getattr(self.parent_window, '_mass_fraction_calculator_state', None)
        if not state:
            return

        self.radio_all.setChecked(state.get('apply_to_all', False))
        self.radio_selected.setChecked(not state.get('apply_to_all', False))

        selected = set(state.get('selected_samples', []))
        for i in range(self.sample_list.count()):
            w = self.sample_list.itemWidget(self.sample_list.item(i))
            if w:
                w.set_checked(w.sample_name in selected)

        formulas = state.get('formulas', {})
        saved_densities = state.get('densities', {})

        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()
            if element in formulas:
                combo = self.table.cellWidget(row, self.COL_FORMULA)
                if combo:
                    saved = formulas[element]
                    combo._set_editor_text(saved)
                    dens = self.csv_database.best_density_for_formula(saved)
                    self._on_compound_selected(row, saved, dens)

            if element in saved_densities:
                custom_density = saved_densities[element]
                cd_item = QTableWidgetItem(f"{custom_density:.6f}")
                cd_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, self.COL_COMP_DENS, cd_item)


    def _manual_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if path and self.csv_database.load_csv(path):
            self._setup_ui()
            self._populate_table()
            QMessageBox.information(self, "Success", "Database loaded!")

    def _open_structure(self, row: int):
        """
        Args:
            row (int): Row index.
        """
        formula = self._current_formula(row)
        if not formula:
            QMessageBox.warning(self, "No compound", "Please choose a compound first.")
            return
        url = self.csv_database.best_url_for_formula(formula)
        QDesktopServices.openUrl(QUrl(url))

    def _apply_mass_fractions(self):
        selected = self._get_selected_samples()
        apply_all = self.radio_all.isChecked()

        if not apply_all and not selected:
            QMessageBox.warning(
                self, "No Samples Selected",
                "Please select at least one sample or choose 'Apply to all samples'.",
            )
            return

        for row in range(self.table.rowCount()):
            el_item = self.table.item(row, self.COL_ELEMENT)
            if not el_item:
                continue
            element = el_item.text()

            mf_cell = self.table.item(row, self.COL_MASSFRAC)
            mw_cell = self.table.item(row, self.COL_MW)
            cd_cell = self.table.item(row, self.COL_COMP_DENS)

            try:
                self.mass_fractions[element] = float(mf_cell.text()) if mf_cell else 1.0
            except ValueError:
                self.mass_fractions[element] = 1.0

            if mw_cell:
                try:
                    self.molecular_weights[element] = float(mw_cell.text())
                except ValueError:
                    pass

            if cd_cell:
                try:
                    val = float(cd_cell.text())
                    if val > 0:
                        self.densities[element] = val
                except ValueError:
                    pass

        self._save_state()

        self.mass_fractions_updated.emit({
            'mass_fractions': self.mass_fractions,
            'densities': self.densities,
            'molecular_weights': self.molecular_weights,
            'apply_to_all': apply_all,
            'selected_samples': selected if not apply_all else [],
        })
        self.accept()


    def closeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        self._save_state()
        super().closeEvent(event)

    def reject(self):
        self._save_state()
        super().reject()