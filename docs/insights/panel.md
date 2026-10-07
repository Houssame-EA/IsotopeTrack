# `panel.py`

The Insights side panel of the results canvas.

The panel searches every loaded sample on its own with the engine in
:mod:`results.insights.engine`, lists what it finds under section headings,
explains each finding, and builds the plot or the explained figure a finding
calls for, behind a selector holding only the samples and elements involved.

Public entry points for the canvas dialog are :func:`integrate_insights_panel`
and :func:`make_insights_toggle_button`.

---

## Constants

| Name | Value |
|------|-------|
| `_NODE_SLOT_W` | `150` |
| `_NODE_SLOT_H` | `125` |
| `_SLOT_SPAN` | `6` |
| `_ISOTOPE_IN_TEXT` | `re.compile('(?<![\\w.])(\\d{1,3})([A-Z][a-z]?)(?![a-z])')` |
| `_FILTER_KEY` | `'insights/plot_filter'` |

## Classes

### `_IsotopeTile` *(extends `QWidget`)*

A small periodic-table tile: mass number above the element symbol.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label: str, parent=None)` | Create a tile for an isotope label such as ``"56Fe"``. |
| `paintEvent` | `(self, event)` | Draw the tile in the current theme. |

### `_RefreshButton` *(extends `QPushButton`)*

Square button drawing its own circular arrow.

The arrow is painted rather than typed as a glyph, because the "↻"
character is missing from some system fonts and then shows as a
placeholder.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Create the button without text; the arrow is drawn in :meth:`paintEvent`. |
| `paintEvent` | `(self, event)` | Draw the frame from the style sheet, then the arrow in the theme colour. |

### `_StrengthDots` *(extends `QWidget`)*

Three dots, filled to show how strong a finding is.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, filled: int, parent=None)` | Create the dots with *filled* of three filled. |
| `paintEvent` | `(self, event)` | Draw the dots in the theme's accent colour. |

### `_Card` *(extends `QFrame`)*

One finding in the panel.

The isotopes the finding is about lead the card as periodic-table tiles,
followed by the headline, the evidence, the samples it covers, how strong
it is, and a button naming the plot it adds.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, s: Suggestion, on_add, samples_text: str='', on_figure=None, pa` | Build a card for one suggestion. |
| `_build` | `(self)` | Lay out the card's contents. |
| `_build_details` | `(self, explanation) → QWidget` | Build the hidden details section: key numbers, then the explanation. |
| `_toggle_details` | `(self)` | Show or hide the details section. |
| `_figure_clicked` | `(self)` | Add the explained figure, and confirm on the button. |
| `_clicked` | `(self)` | Add the plot, and confirm on the button. |

### `SmartInsightsPanel` *(extends `QWidget`)*

Resizable pane that searches the data and lists what it finds.

Embedded as the rightmost pane of the canvas splitter and hidden by default,
toggled by the button from :func:`make_insights_toggle_button`.

The panel searches on its own: when it is shown, when the loaded samples or
their replicate groups change, and when another plot type is picked. Every
loaded sample and every element is searched, whatever is selected on the
canvas. The plot types menu chooses which kinds of plot to search for;
findings are listed under section headings, and each card builds its plot
with only the samples and elements the finding is about.

Use :func:`integrate_insights_panel` to construct and attach one rather than
instantiating this directly.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scene, parent_window, parent=None)` | Build the panel and subscribe it to theme and selection changes. |
| `_build_ui` | `(self)` | Assemble the header, scope summary, plot type menu and finding list. |
| `_apply_theme` | `(self)` | Restyle the panel from the current theme palette. |
| `_update_types_label` | `(self)` | Say on the plot types button what is being shown. |
| `_sync_filter_actions` | `(self)` | Tick the menu item matching the current filter. |
| `current_filter` | `(self) → str \| None` | Return the plot type being shown, or ``None`` for all of them. |
| `_set_filter` | `(self, node_type: str \| None)` | Show one plot type, or all of them. |
| `_show_only` | `(self, key: str)` | Show one plot type only. |
| `_set_status` | `(self, text: str)` | Show a short progress line under the header, or hide it when empty. |
| `scan` | `(self, force: bool=False)` | Search for whatever the picked plot types still need. |
| `refresh` | `(self)` | Search everything again from scratch. |
| `run_category` | `(self, key: str, force: bool=False)` | Show only the plot types one detector feeds, and search for them. |
| `_check_scope` | `(self)` | Search again when the loaded samples or replicate groups have changed. |
| `_on_scene_selection` | `(self, *_)` | Re-check the scope soon after the canvas changes. |
| `_stop_worker` | `(self)` | Cancel any in-flight analysis and stop listening to it. |
| `_update_sample_strip` | `(self, scope: AnalysisScope \| None=None)` | Describe which samples are searched and how they group into replicates. |
| `_on_partial` | `(self, suggestions: list[Suggestion], detector: str, scope_key: str)` | Show one detector's findings as soon as it finishes. |
| `_on_done` | `(self, keys=frozenset(), scope_key: str='')` | Finish a search and start another if more plot types were picked meanwhile. |
| `visible_suggestions` | `(self) → list[Suggestion]` | Return the cards for the picked plot types, ranked and de-duplicated. |
| `_update_chip_counts` | `(self)` | Write how many findings each plot type has into the menu. |
| `_render` | `(self, searching: bool=False, force: bool=False)` | Show the findings for the current filter, under their section headings. |
| `_apply_render` | `(self, busy: bool=False)` | Lay out the current findings, keeping cards that are already shown. |
| `_release_held` | `(self)` | Show findings that were held back while the pointer was over the list. |
| `_pointer_over_list` | `(self) → bool` | Whether the mouse is over the list of findings. |
| `eventFilter` | `(self, watched, event)` | Show held-back findings once the pointer leaves the list. |
| `_rebuild_cards` | `(self)` | Lay out section headings and cards, reusing the cards already on screen. |
| `_empty_message` | `(self) → str` | Explain why there are no cards, and what to do about it. |
| `_show_empty` | `(self)` | Show the empty-state message in place of the cards. |
| `_show_placeholder` | `(self, text: str)` | Put a short message where the cards would go. |
| `_clear_cards` | `(self)` | Remove every card and heading, leaving the trailing stretch in place. |
| `_add_figure` | `(self, s: Suggestion)` | Add the figure that walks through a finding, panels a to f with a legend. |
| `_add_suggestion` | `(self, s: Suggestion, node_type: str \| None=None, config: dict \| None=` | Build the branch a suggestion describes and wire it into the canvas. |
| `_build_scoped_selector` | `(self, s: Suggestion, factories: dict, narrow_elements: bool=True)` | Create a sample selector holding only what the finding is about. |
| `_flash_status` | `(self, message: str, msec: int=2600)` | Show a transient message in the status line. |
| `showEvent` | `(self, event)` | Start searching as soon as the panel is shown. |
| `hideEvent` | `(self, event)` | Stop watching for data changes while hidden. |
| `closeEvent` | `(self, event)` | Release resources if the panel is ever closed directly. |
| `_teardown` | `(self)` | Drop the theme subscription and stop any running analysis. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_find_source_node` | `(scene) → object \| None` | Find the node a newly added plot node should be wired to. |
| `_occupied_rects` | `(scene) → list[tuple[float, float, float, float]]` | List the space every node on the canvas already takes up. |
| `_free_position` | `(scene, preferred)` | Find a spot for a new node that no existing node is sitting on. |
| `_raw_pool_for` | `(scene, parent_window) → dict` | Every loaded particle by sample, as the engine reads it. |
| `_isotope_entries` | `(parent_window, scene, labels) → list[dict]` | Resolve element labels into the isotope records a selector expects. |
| `isotope_markup` | `(text: str) → str` | Write isotope labels in text with a superscript mass number. |
| `section_of` | `(category: str) → str` | Return the section heading a finding of *category* is listed under. |
| `strength_label` | `(confidence: float) → tuple[str, int]` | Word and number of filled dots describing how strong a finding is. |
| `selection_units` | `(s: Suggestion, scope: AnalysisScope \| None) → list[tuple[str, tuple[s` | Group a suggestion's samples the way its selector will treat them. |
| `describe_samples` | `(s: Suggestion, scope: AnalysisScope \| None) → str` | Describe the samples a card covers in a few words. |
| `describe_scope` | `(scope: AnalysisScope) → tuple[str, str]` | Two plain sentences describing what Insights searches. |
| `_load_filter` | `() → str \| None` | Read the plot type the user last chose to show, or ``None`` for all. |
| `_save_filter` | `(node_type: str \| None) → None` | Remember which plot type the user chose to show. |
| `card_key` | `(s: Suggestion) → tuple` | Identity of a finding's card, so a card can be kept across refreshes. |
| `integrate_insights_panel` | `(canvas_dialog, splitter: QSplitter) → SmartInsightsPanel` | Append a :class:`SmartInsightsPanel` as the rightmost pane of *splitter*. |
| `make_insights_toggle_button` | `(canvas_dialog, splitter: QSplitter) → QPushButton` | Create the header button that shows and hides the insights panel. |
