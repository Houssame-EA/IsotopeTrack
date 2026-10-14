# `particle_classifier_simple_dialog.py`

Simple Particle Classifier dialog, in the shared application look.

Everything the classic editor does, laid out to read like a sentence:

- **Sample** (left, top): which sample is shown, whether it is included in
  the output, whether every sample uses the same groups, and copying one
  sample's groups to others.
- **Groups** (left): the groups in priority order, with live particle
  counts, buttons to add and reorder them, and the unclassified count.
- **Group editor** (right): name and colour, then the rule as rows,
  "Must have + 60Ni + 107Ag", "Must not have − 56Fe", "Other isotopes
  allowed / not allowed", with a plain-words reading of it and the live
  count. A group can have several rules ("+ Or another rule"); a particle
  matching any of them joins the group. Any rule can be edited as text
  with the full expression language.
- **Advanced** (bottom): what happens to a particle that matches several
  groups, and to particles that match none.

On OK it shows the same overlap warning as the classic editor. It reads
and writes exactly the same data as
:class:`tools.particle_classifier_dialog.ParticleClassifierDialog` (same
constructor arguments and ``get_*`` read-back methods), so the node, saved
projects and the relabelling pass are unchanged, and the classic editor
stays one click away.

---

## Constants

| Name | Value |
|------|-------|
| `SIMPLE_HELP_HTML` | `"<b>Groups</b><br>Each group is a kind of particle, for e…` |
| `_UNMATCHED_MODES` | `('unclassified', 'discard', 'passthrough')` |
| `_MINUS` | `'−'` |

## Classes

### `SimpleClassifierDialog` *(extends `QDialog`)*

Group-first configurator for the Particle Classifier node.

Args:
    parent: Parent widget.
    upstreams (list | dict): Upstream data dict(s) feeding the node.
    definitions (list | None): The node's definitions.
    groups (dict | None): The node's ``{group_name: color}`` registry.
    overlap_mode (str): ``'double_count'`` or ``'priority'``.
    unmatched_mode (str): ``'unclassified'``, ``'discard'`` or
        ``'passthrough'``.
    unclassified_color (str | None): Colour of the Unclassified bucket.
    selected_sources (list | None): Samples included in the output
        (None means all).
    group_pooling_policies (dict | None): ``{group_name: 'keep' |
        'drop_mfc'}`` for groups with several rules.
    confound_dismissals (list | None): Overlap warnings the user chose
        never to see again.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, upstreams, definitions=None, groups=None, overlap_mode=` |  |
| `_style` | `(self)` | Shared application sheet plus the cards, rows and isotope chips. |
| `_restyle` | `(self, *_a)` |  |
| `_set_included` | `(self, selected_sources)` |  |
| `_load_state` | `(self, definitions, groups)` | Load node definitions into groups and fill missing colours. |
| `_row_label` | `(self, text)` |  |
| `_recipe_label` | `(self, name, syntax)` | Row name with its text syntax in parentheses, e.g. ``Must have (+60Ni)``. |
| `_recipe_label_html` | `(name, syntax)` | Rich text for a recipe row name with its syntax in a muted colour. |
| `_section_label` | `(text)` |  |
| `_build` | `(self)` |  |
| `_build_toolbar` | `(self)` |  |
| `_build_left_card` | `(self)` |  |
| `_build_editor_card` | `(self)` |  |
| `_build_combos_card` | `(self)` |  |
| `_sample_combinations` | `(self)` |  |
| `_refresh_combos` | `(self, *_a)` | List the selected sample's isotope combinations with their groups. |
| `_on_combo_clicked` | `(self, item)` | Add the clicked combination's isotopes to the selected rule's Must have row. |
| `_build_advanced` | `(self)` |  |
| `_sync_advanced` | `(self)` |  |
| `_groups` | `(self)` | The group list being edited: the shared one, or the current sample's. |
| `_current_group` | `(self)` |  |
| `_current_rule` | `(self)` |  |
| `_groups_for_output` | `(self)` |  |
| `_available_isotopes` | `(self)` | Isotopes offered in the pickers, in mass order. |
| `_refresh_all` | `(self, select_row=None)` |  |
| `_refresh_sample_controls` | `(self)` |  |
| `_refresh_group_list` | `(self)` |  |
| `_group_item_text` | `(self, group)` |  |
| `_clear_layout` | `(layout)` |  |
| `_load_group` | `(self)` | Show the selected group and its selected rule in the editor. |
| `_refresh_rule_tabs` | `(self)` |  |
| `_load_rule` | `(self)` |  |
| `_select_rule` | `(self, idx, *_a)` |  |
| `_refresh_chips` | `(self)` |  |
| `_add_isotope` | `(self, kind, iso, *_a)` |  |
| `_remove_isotope` | `(self, kind, iso, *_a)` |  |
| `_rule_changed` | `(self)` |  |
| `_join` | `(items, word)` |  |
| `_rule_phrase` | `(cls, rule)` | One rule in plain words, or None when it has nothing to say. |
| `_reads_as` | `(cls, group)` | The whole group in plain words. |
| `_update_feedback` | `(self)` | Show the rule's expression, its plain-words reading and any problem. |
| `_remove_missing` | `(self)` |  |
| `_toggle_text_mode` | `(self)` |  |
| `_on_text_changed` | `(self, text)` |  |
| `_on_exact_changed` | `(self, *_a)` |  |
| `_on_name_committed` | `(self)` |  |
| `_on_color_picked` | `(self, color)` |  |
| `_add_group` | `(self)` |  |
| `_delete_group` | `(self)` |  |
| `_move_group` | `(self, delta)` | Move the selected group up or down the priority order. |
| `_add_rule` | `(self)` | Add an alternative rule to the selected group (classic pooling). |
| `_remove_rule` | `(self)` |  |
| `_ask_pooling` | `(self, group)` | Ask once per group how particle-mass statistics are pooled. |
| `_on_group_selected` | `(self, row)` |  |
| `_on_sample_changed` | `(self, name)` |  |
| `_on_include_toggled` | `(self, checked)` |  |
| `_set_shared_checkbox` | `(self, checked)` |  |
| `_on_shared_toggled` | `(self, checked)` | Switch between one set of groups for all samples and per-sample groups. |
| `_fill_copy_menu` | `(self)` |  |
| `_copy_groups_to` | `(self, targets, *_a)` | Replace the groups of ``targets`` with copies of this sample's groups. |
| `_on_overlap_changed` | `(self, *_a)` |  |
| `_on_unmatched_changed` | `(self, *_a)` |  |
| `_on_advanced_toggled` | `(self, on)` |  |
| `_current_sample_definitions` | `(self)` |  |
| `_recompute_counts` | `(self)` | Count particles per group for the selected sample. |
| `_update_groups_strip` | `(self)` | Show every group of this sample with its colour and count, then Unclassified. |
| `_update_count_labels` | `(self)` |  |
| `_build_output` | `(self)` | Definitions and group colours for the current edits. |
| `_selected_sources_out` | `(self)` |  |
| `_open_classic` | `(self)` | Open the classic editor on the current edits and load its result back. |
| `_show_help` | `(self)` |  |
| `_show_overlap_warning` | `(self, pairs)` | One warning listing every pair of rules that can match the same particle. |
| `accept` | `(self)` | Build the node data, warn about overlapping rules, then close. |
| `get_definitions` | `(self)` | Definitions in the node's format (internal keys stripped). |
| `get_groups` | `(self)` | ``{group_name: color}`` for the saved definitions. |
| `get_overlap_mode` | `(self)` |  |
| `get_unmatched_mode` | `(self)` |  |
| `get_unclassified_color` | `(self)` |  |
| `get_selected_sources` | `(self)` |  |
| `get_has_unresolved_issues` | `(self)` |  |
| `get_group_pooling_policies` | `(self)` |  |
| `get_confound_dismissals` | `(self)` |  |
