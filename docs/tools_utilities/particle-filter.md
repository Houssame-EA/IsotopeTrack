# `particle_filter.py`

Particle Filter node for the Workflow Canvas.

---

## Constants

| Name | Value |
|------|-------|
| `_FILTERABLE_TYPES` | `('sample_data', 'single_sample_data', 'multiple_sample_da…` |

## Classes

### `ParticleFilterDialog` *(extends `QDialog`)*

Two-pane configurator for the Particle Filter node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, upstreams, sample_filters=None, selected_sources=None, ` |  |
| `_load_elem_data` | `()` | Load the periodic-table element metadata used by the chips. |
| `_style` | `()` | Build the dialog stylesheet for the current app theme. |
| `_build` | `(self)` | Assemble the two-pane layout: sample list on the left, the |
| `_build_pane` | `(self, pv)` | Build the three filter-axis sections of the right pane. |
| `_section_label` | `(text)` | Build a small uppercase section label. |
| `_refresh_row` | `(self, item)` | Refresh one sample row: name, particle count and filter tag. |
| `_on_row_changed` | `(self, current, previous)` | Switch the right pane to the newly clicked sample. |
| `_on_item_checked` | `(self, item)` | React to an include/exclude checkbox toggle. |
| `_save_pane` | `(self, name)` | Store the right pane's state as the given sample's filter. |
| `_load_pane` | `(self, name)` | Load one sample's filter configuration into the right pane. |
| `_pane_config` | `(self)` | Read the right pane into a filter configuration dict. |
| `_apply_to_all` | `(self)` | Copy the current sample's filter to every other sample, pruned to |
| `_on_chips_changed` | `(self)` | React to a chip toggle: refresh threshold rows and the preview. |
| `_on_unit_changed` | `(self)` | Relabel the threshold spinboxes for the newly selected unit. |
| `_schedule_preview` | `(self, *_)` | Restart the debounce timer for the live preview. |
| `_selected_isotopes` | `(self)` | Map the chip selection back to isotope dicts. |
| `_sync_thr_values` | `(self)` | Persist the current spinbox values into the working dict. |
| `_rebuild_thr_rows` | `(self)` | Rebuild the threshold form: one spinbox per element selected in |
| `_refresh_stale_area` | `(self)` | Show or hide the stale-criteria hint and Remove-stale button. |
| `_remove_stale` | `(self)` | Remove every stale criterion of the current sample in one click. |
| `_checked_names` | `(self)` | List the sample names currently checked in the left list. |
| `_update_preview` | `(self)` | Recompute the pass counts on the upstream snapshot (debounced). |
| `get_merged_name` | `(self)` | Read the exit name for merged Single Sample inputs. |
| `get_selected_sources` | `(self)` | Read the include/exclude check states. |
| `get_sample_filters` | `(self)` | Assemble the per-sample filter configurations. |

### `ParticleFilterNode` *(extends `QObject`)*

Composable particle filter node with per-sample settings.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` | Update the node position and notify the canvas item. |
| `process_data` | `(self, input_data)` | Receive pushed upstream data, refresh stale state and propagate. |
| `_pull_upstream_all` | `(self)` | Fetch the upstream dict from every input link. |
| `get_output_data` | `(self)` | Gather every upstream stream, filter each chosen sample with its |
| `_build_single_output` | `(self, source, kept)` | Emit one chosen sample using the single-sample data schema. |
| `_build_multi_output` | `(self, sources, results)` | Regroup several chosen samples into the multi-sample data schema. |
| `_recompute_stale` | `(self, sources)` | Refresh the cached stale-label list against the incoming samples. |
| `stale_labels` | `(self)` | List labels referenced by filters but missing in their samples. |
| `is_active` | `(self)` | Report whether the node is doing anything beyond passthrough. |
| `summary_text` | `(self)` | Build the live summary shown under the node icon. |
| `configure` | `(self, parent_window)` | Open the configuration dialog (double-click). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ual` | `()` | Return the UserActionLogger, or None if logging isn't ready. |
| `_empty_conc_meta` | `()` | Build an empty concentration metadata entry. |
| `default_filter_config` | `()` | Build the default (inactive) per-sample filter configuration. |
| `active_axes` | `(config)` | List the filter axes that are enabled and meaningfully configured. |
| `summarize_config` | `(config)` | Build a short human-readable summary of one filter configuration. |
| `referenced_labels` | `(config)` | Collect the element labels referenced by enabled filter axes. |
| `stale_from_available` | `(avail, config)` | Find referenced labels that are missing from the available set. |
| `detected_labels` | `(particle, thr_unit, thr_values)` | Build the set of element labels detected in a particle. |
| `particle_passes` | `(particle, comp_labels, mode, count_cfg, thr_unit, thr_values)` | Evaluate every active filter axis against one particle (AND logic). |
| `effective_criteria` | `(config, stale)` | Resolve a filter configuration into evaluation-ready criteria. |
| `normalize_sources` | `(upstreams)` | Flatten the connected upstream dicts into one simple sample list. |
| `source_labels` | `(source)` | Collect the element labels available in one source entry. |
| `apply_sample_filter` | `(source, config, retag=True)` | Filter one source's particles with that sample's own configuration. |
| `retag_particles` | `(particles, name)` | Regroup already-copied particles under a new sample name. |
| `merge_single_sources` | `(sources, name)` | Combine several single-sample source entries into one synthetic one. |
| `prune_config_to_labels` | `(config, labels)` | Copy a filter configuration keeping only criteria for given labels. |
| `build_particle_filter_node_item` | `()` | Create the ParticleFilterNodeItem class bound to the canvas widgets. |
