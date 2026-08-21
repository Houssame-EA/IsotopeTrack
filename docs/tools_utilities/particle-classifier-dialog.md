# `particle_classifier_dialog.py`

Particle Classifier configuration dialog (Stage 3).

Per-sample-first LHS/RHS UI per ``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §3:
a table of every incoming sample on the left (checkbox = include in output +
bulk-apply target; click = navigate, these are deliberately separate
mechanisms — see ``ParticleFilterDialog`` in ``tools/particle_filter.py`` for
the precedent this mirrors), and a working panel on the right for whichever
sample is currently navigated to, listing that sample's classifier
definitions with live syntax/stale/contradiction/confound validation (§5,
§9) built on top of the Stage 1 expression engine
(``tools/particle_classifier_expr.py``).

Definitions are stored as one flat, global, priority-ordered list on the
node (:class:`tools.particle_classifier_node.ParticleClassifierNode`); each
definition is scoped to exactly one sample via its ``target_sample`` field.
This dialog is the only place that list is edited.

Group colors (``self._groups`` / the node's ``groups`` attribute) are
deliberately GLOBAL, shared across every sample -- a group name means "this
substance," and any definition assigned to it on any sample renders the
same color everywhere, including downstream in the graphs. Typing an
existing group name on a different sample joins that same shared bucket
and adopts its color; there is no per-sample override. (A per-sample-
independent-color variant of this was tried and reverted: downstream viz
color-seeding is fundamentally keyed by label TEXT alone with no sample
dimension, so per-sample-divergent colors could never actually render
distinctly in a chart anyway -- they just looked like the wrong color was
winning. Consistency across samples is also simply what a same-named
group is FOR.)

---

## Constants

| Name | Value |
|------|-------|
| `_ERROR_COLOR` | `'#EF4444'` |
| `_WARNING_COLOR` | `'#F59E0B'` |

## Classes

### `_ColorBtn` *(extends `QPushButton`)*

Small color-square button that opens the shared color picker.

Based on ``results/results_pie_charts.py``'s ``_ColorBtn`` (see
``pick_color_hex`` in ``results/shared_plot_utils.py``), but that
original relies on callers polling ``.color()`` at commit time rather
than reacting to a signal. This dialog instead pushes color edits into
the definition dict immediately (matching every other field's
``_on_xxx_changed`` pattern here), which needs its own
``colorChanged`` signal: ``clicked`` is NOT safe to use for this,
because opening a modal color-picker dialog from inside
``mousePressEvent`` means the user's mouse-release lands on that
dialog, not back on this button, so Qt never delivers a matching
release event here and ``clicked`` silently never fires (the swatch
still updates, since ``set_color`` runs unconditionally, giving the
illusion the pick worked while nothing downstream ever ran).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color='#FFFFFF', parent=None)` |  |
| `_apply` | `(self)` |  |
| `color` | `(self)` |  |
| `set_color` | `(self, c)` |  |
| `mousePressEvent` | `(self, event)` |  |

### `ParticleClassifierDialog` *(extends `QDialog`)*

Per-sample-first configurator for the Particle Classifier node.

Left pane: every incoming sample with a checkbox (include in output +
bulk-apply target). Right pane: the classifier definitions of the
sample currently clicked, with live syntax/stale/contradiction/confound
validation. "Apply to Current/Selected Samples" copies the current
panel's definitions onto other samples (as independent copies with
their own ``target_sample`` and ``id``, per design §4's "no
definition-reuse across samples" model).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, upstreams, definitions=None, groups=None, overlap_mode=` |  |
| `_style` | `()` | Build the dialog stylesheet for the current app theme. |
| `_section_label` | `(text)` | Build a small uppercase section label (mirrors ParticleFilterDialog). |
| `_build` | `(self)` |  |
| `_build_left` | `(self)` |  |
| `_build_right` | `(self)` |  |
| `_build_edit_panel` | `(self)` |  |
| `_refresh_row` | `(self, item)` |  |
| `_on_row_changed` | `(self, current, previous)` |  |
| `_on_item_checked` | `(self, item)` |  |
| `_checked_names` | `(self)` |  |
| `_select_all_samples` | `(self)` |  |
| `_defs_for` | `(self, sample_name)` | List definitions targeting one sample, in global priority order. |
| `_recompute_match_counts_for_sample` | `(self, sample_name)` | Refresh the effective match-count cache for one sample's |
| `_find_def` | `(self, def_id)` |  |
| `_load_pane` | `(self, name)` |  |
| `_refresh_def_list` | `(self)` |  |
| `_def_list_label` | `(self, d)` |  |
| `_on_def_selected` | `(self, row)` |  |
| `_load_definition_into_editor` | `(self, d)` |  |
| `_refresh_group_combo` | `(self)` | List every group name node-wide -- groups are global (see |
| `_color_for_definition` | `(self, d)` | Resolve a definition's effective color (own color, group color, |
| `_add_definition` | `(self)` |  |
| `_delete_current_definition` | `(self)` |  |
| `_move_definition` | `(self, delta)` | Move the current definition up/down within the GLOBAL priority |
| `_refresh_row_for` | `(self, sample_name)` |  |
| `_current_definition` | `(self)` |  |
| `_on_expr_changed` | `(self, text)` |  |
| `_on_field_changed` | `(self, *_a)` |  |
| `_on_group_committed` | `(self, *_a)` | Commit the group-name field once the user finishes editing it |
| `_prune_orphan_groups` | `(self)` | Drop any group (and its pooling policy) no live definition |
| `_check_group_pooling` | `(self, group_name)` | Warn once per session when a group now pools 2+ definitions |
| `_show_group_pooling_modal` | `(self, group_name)` | Warning-and-choice modal for a multi-definition group (design |
| `_reselect_definition_after_rebuild` | `(self, def_id)` | Rebuild the definitions list widget and restore the given |
| `_on_color_picked` | `(self)` |  |
| `_on_unmatched_mode_changed` | `(self, *_a)` |  |
| `_on_overlap_mode_changed` | `(self, *_a)` |  |
| `_clear_validation_ui` | `(self)` |  |
| `_validate_current` | `(self)` |  |
| `_check_stale` | `(self, d, ast)` |  |
| `_remove_stale` | `(self)` |  |
| `_show_contradiction_modal` | `(self, d)` | Warning-and-choice modal for a self-contradictory definition. |
| `_confound_pair_key` | `(d_a, d_b)` | Stable, order-independent identity for a confounding pair. |
| `_confound_pair_key_from_dict` | `(rec)` |  |
| `_collect_active_confound_pairs` | `(self)` | Find every currently-confounding definition pair (design §5), |
| `_show_confound_warnings_dialog` | `(self, pairs)` | One aggregate warning for every currently active confound pair |
| `accept` | `(self)` | Show the aggregate confound warning (if any) before closing. |
| `_recompute_unresolved_issues` | `(self)` | Refresh the has-unresolved-issues flag (drives the node icon's |
| `_apply_to_current_sample` | `(self)` |  |
| `_apply_to_selected_samples` | `(self)` |  |
| `_show_help` | `(self)` | Same explanation as the one-time onboarding modal shown on |
| `get_definitions` | `(self)` | Return the edited definitions list (any internal |
| `get_groups` | `(self)` |  |
| `get_overlap_mode` | `(self)` |  |
| `get_unmatched_mode` | `(self)` |  |
| `get_unclassified_color` | `(self)` |  |
| `get_selected_sources` | `(self)` |  |
| `get_has_unresolved_issues` | `(self)` |  |
| `get_group_pooling_policies` | `(self)` |  |
| `get_confound_dismissals` | `(self)` | Serializable form of permanently-dismissed confound pairs. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_next_palette_color` | `(used_colors)` | Pick the next unused color from the app's default sample palette. |
