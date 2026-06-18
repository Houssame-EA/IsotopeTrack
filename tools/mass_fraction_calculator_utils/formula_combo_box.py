from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QComboBox

from tools.mass_fraction_calculator_utils.compound_database import CSVCompoundDatabase
from tools.mass_fraction_calculator_utils.formula_utils import canonicalize_preserve_user_order, reduce_counts, \
    parse_formula_to_counts


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
        super().__init__(parent)
        self.element = element
        self.csv_database = csv_database
        self.tracked_elements = tracked_elements or set()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
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

        # TODO: `[int]` is legacy so it should be removed... but examples still uses it
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
        """Show all polymorphs/structures for the confirmed formula."""
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

        counts = reduce_counts(parse_formula_to_counts(user_canon))
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

        counts = reduce_counts(parse_formula_to_counts(user_canon))
        if len(counts) >= 2:
            self.filter_to_formula(user_canon)
        else:
            self.reset_items()

        self.formula_selected.emit(user_canon, dens)
