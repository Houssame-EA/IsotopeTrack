# `particle_classifier_node.py`

Particle Classifier canvas node.

Stage 2 (canvas registration, hard-blocked connectivity restrictions, node
registry entries, minimal placeholder node item) and Stage 3 (real
definition storage + the configuration dialog from
``tools/particle_classifier_dialog.py``) per
``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §14. Output relabeling (§7) is
still Stage 4 — ``get_output_data`` still passes upstream data through
unmodified.

Connectivity (design §2):
    Upstream:   Particle Filter, Single Sample, Multiple Sample only.
    Downstream: any Visualization-category node except AI Data Assistant
                (permanently excluded) and the work-in-progress set in
                WIP_EXCLUDED_DOWNSTREAM_TYPES (Clustering,
                Single/Multiple, Correlation Matrix, Network, Molar Ratio,
                Isotopic Ratio, Ternary Plot) -- temporarily disabled until
                each is verified meaningful on classifier-bucketed data.
Invalid link attempts must be hard-blocked at the canvas level (the link
cannot be drawn) with an explicit error dialog — see
``validate_classifier_link`` and its wiring into
``EnhancedCanvasScene.add_link`` in ``widget/canvas_widgets.py``.

---

## Constants

| Name | Value |
|------|-------|
| `NODE_TYPE` | `'particle_classifier'` |
| `ALLOWED_UPSTREAM_TYPES` | `frozenset({'particle_filter', 'sample_selector', 'multipl…` |
| `WIP_EXCLUDED_DOWNSTREAM_TYPES` | `frozenset({'clustering_plot', 'single_multiple_element_pl…` |
| `EXCLUDED_DOWNSTREAM_TYPES` | `WIP_EXCLUDED_DOWNSTREAM_TYPES \| frozenset({'ai_assistant'})` |
| `DEFAULT_UNCLASSIFIED_COLOR` | `'#9CA3AF'` |
| `_HIDE_ONBOARDING_SETTING` | `'hide_particle_classifier_onboarding'` |
| `CLASSIFIER_HELP_HTML` | `"<b>What this node does</b><br>Classifies particles into …` |

## Classes

### `ParticleClassifierNode` *(extends `QObject`)*

Particle Classifier workflow node.

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` | Update the node position and notify the canvas item. |
| `process_data` | `(self, input_data)` | Receive pushed single-link upstream data. |
| `_recompute_incoming_names` | `(self, input_data)` | Refresh the effective sample names currently feeding this node. |
| `_pull_upstream_all` | `(self)` | Fetch the upstream dict from every input link. |
| `_combined_upstream_dict` | `(self)` | Return the effective input dict for this node, keeping every |
| `get_output_data` | `(self)` | Relabel every connected sample's particles per this node's |
| `_output_selected_isotopes` | `(particles, upstream_selected, label_colors)` | Rebuild ``selected_isotopes`` to name the SYNTHETIC labels the |
| `definitions_for_sample` | `(self, sample_name)` | List this node's definitions targeting one sample, in priority order. |
| `configure` | `(self, parent_window)` | Open the configuration dialog (double-click). |
| `_active_definitions` | `(self)` | Definitions whose target_sample is actually connected right now. |
| `summary_text` | `(self)` | Build the live summary shown under the node icon. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ual` | `()` | Return the UserActionLogger, or None if logging isn't ready. |
| `is_allowed_upstream` | `(node_type: str) → bool` | Whether a node type may feed data into a Particle Classifier node. |
| `is_allowed_downstream` | `(node_type: str, viz_node_types) → bool` | Whether a node type may receive data from a Particle Classifier node. |
| `new_definition_id` | `()` | Generate a fresh, stable identity for a classifier definition. |
| `maybe_show_classifier_onboarding` | `(parent_window)` | Show the one-time onboarding modal the first time this node type is |
| `build_particle_classifier_node_item` | `()` | Create the ParticleClassifierNodeItem class bound to canvas widgets. |
