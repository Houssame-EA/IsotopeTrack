# `particle_filter.py`

Particle Filter node for the Workflow Canvas.

A composable filter that sits between sample selector nodes (Single Sample,
Multi-Sample, or Batch) and any figure node. Several sample nodes can be
connected to the filter at once: every incoming sample — including each
summed group inside a Multi-Sample stream — appears in a sample list on the
left side of the configuration dialog. Each sample carries its own filter
settings: click a sample, tune its criteria in the right pane, then move to
the next one.

Per sample, up to four independent criteria axes are available (AND logic
between active axes): isotopic composition (AND / OR / EXACT / NOT(AND) /
NOT(OR) / NOT(EXACT) match), detected-isotope count, per-isotope signal
thresholds, and particle data (mass / counts range filters).

The output is regrouped so figures can read it: one chosen sample is
re-emitted as single-sample data, several chosen samples are regrouped into
multi-sample data with their ``source_sample`` tags, so every downstream
figure node consumes the result transparently.

---

## Constants

| Name | Value |
|------|-------|
| `_FILTERABLE_TYPES` | `('sample_data', 'single_sample_data', 'multiple_sample_da…` |
| `_ELEM_DATA_CACHE` | `None` |
| `_NOT_MODES` | `{'NOT(AND)': 'AND', 'NOT(OR)': 'OR', 'NOT(EXACT)': 'EXACT'}` |
| `_PD_SCALAR_GETTERS` | `{'mass': _particle_scalar_mass_fg, 'counts': _particle_sc…` |
| `_FILT_SUFFIX_RE` | `re.compile('^(?P<base>.*?)\\s*\\(filt x(?P<n>\\d+)\\)\\s*$')` |

## Classes

### `ParticleFilterDialog` *(extends `QDialog`)*

Two-pane configurator for the Particle Filter node.

Left pane: every incoming sample with a check (include / exclude) and a
short tag showing its filter. Right pane: the filter settings of the
sample currently clicked — isotopic composition (chips + AND/OR/EXACT/
NOT variants), isotopic count, per-isotope thresholds, and particle
data (mass / counts). Each sample keeps its own settings; "Apply to
selected samples" copies the current one to every checked sample.
The live preview runs on the upstream snapshot fetched once at dialog
open and is debounced (~250 ms) after the last user change.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, upstreams, sample_filters=None, selected_sources=None, ` |  |
| `_load_elem_data` | `()` | Load the periodic-table element metadata used by the chips. |
| `_style` | `()` | Build the dialog stylesheet for the current app theme. |
| `_build` | `(self)` | Assemble the two-pane layout: sample list on the left, the |
| `_build_pane` | `(self, pv)` | Build the four filter-axis sections of the right pane. |
| `_build_particle_data_field` | `(self, parent_layout, key, title, unit)` | Build one Particle Data sub-filter row (Mass, Counts). |
| `_validate_particle_data_field` | `(self, key, fields=None)` | Validate one Particle Data sub-filter's inputs and show/hide its |
| `_section_label` | `(text)` | Build a small uppercase section label. |
| `_refresh_row` | `(self, item)` | Refresh one sample row: name, particle count and filter tag. |
| `_on_row_changed` | `(self, current, previous)` | Switch the right pane to the newly clicked sample. |
| `_on_item_checked` | `(self, item)` | React to an include/exclude checkbox toggle. |
| `_save_pane` | `(self, name)` | Store the right pane's state as the given sample's filter. |
| `_load_pane` | `(self, name)` | Load one sample's filter configuration into the right pane. |
| `_read_particle_data_field` | `(self, key)` | Read one Particle Data sub-filter's widgets into a config dict. |
| `_pane_config` | `(self)` | Read the right pane into a filter configuration dict. |
| `_apply_to_all` | `(self)` | Copy the current sample's filter — and, for single-sample rows, |
| `_toggle_select_all` | `(self)` | Check every sample row, or uncheck every row if all are already |
| `_update_select_all_label` | `(self)` | Relabel the Select-all button to reflect the current check state. |
| `_on_merge_toggle` | `(self, checked)` | React to the "Merge single samples into one" checkbox. |
| `get_merge_singles` | `(self)` | Report whether single-sample inputs should merge into one. |
| `get_sample_groups` | `(self)` | Read the per-sample custom group names set for single-sample |
| `_on_chips_changed` | `(self)` | React to a chip toggle: refresh threshold rows and the preview. |
| `_on_unit_changed` | `(self)` | Relabel the threshold spinboxes for the newly selected unit. |
| `_schedule_preview` | `(self, *_)` | Restart the debounce timer for the live preview. |
| `_selected_isotopes` | `(self)` | Map the chip selection back to isotope dicts. |
| `_sync_thr_values` | `(self)` | Persist the current spinbox values into the working dict. |
| `_rebuild_thr_rows` | `(self)` | Rebuild the threshold form: one spinbox per isotope selected in |
| `_refresh_stale_area` | `(self)` | Show or hide the stale-criteria hint and Remove-stale button. |
| `_remove_stale` | `(self)` | Remove every stale criterion of the current sample in one click. |
| `_checked_names` | `(self)` | List the sample names currently checked in the left list. |
| `_update_preview` | `(self)` | Recompute the pass counts on the upstream snapshot (debounced). |
| `get_merged_name` | `(self)` | Read the exit name for merged Single Sample inputs. |
| `_try_accept` | `(self)` | Block accept while the current sample's Particle Data box is |
| `stale_warning_suppressed` | `(self)` | Read whether "Don't show this again" was checked on last accept. |
| `get_selected_sources` | `(self)` | Read the include/exclude check states. |
| `get_sample_filters` | `(self)` | Assemble the per-sample filter configurations. |

### `ParticleFilterNode` *(extends `QObject`)*

Composable particle filter node with per-sample settings.

Any number of sample selector nodes can feed this node. Every incoming
sample — including summed groups inside a Multi-Sample stream — appears
in the configuration dialog, where each one carries its own filter
settings. The output is regrouped so figures can read it: one chosen
sample is emitted as single-sample data, several chosen samples are
regrouped into multi-sample data. Filtering always operates on copies;
upstream data is never mutated.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` | Update the node position and notify the canvas item. |
| `process_data` | `(self, input_data)` | Receive pushed upstream data, refresh stale state and propagate. |
| `_stored_sample_names` | `(self)` | Sample names this node currently carries settings for. |
| `reconcile_incoming` | `(self, parent_window=None, new_link=None)` | Reconcile stored per-sample settings against the samples actually |
| `_check_duplicate_source` | `(self, new_link, parent_window=None)` | Detect whether the source that was just wired in looks like a |
| `_warn_duplicate_source` | `(self, parent_window, new_link, new_entry, existing_entry, sig)` | Ask the user how to handle a suspected duplicate sample. |
| `_warn_partial_mismatch` | `(self, parent_window, matched, missing, added)` | Tell the user the newly connected source only partly matches the |
| `_pull_upstream_all` | `(self)` | Fetch the upstream dict from every input link. |
| `get_output_data` | `(self)` | Gather every upstream stream, filter each chosen sample with its |
| `_get_output_data_impl` | `(self)` |  |
| `_build_single_output` | `(self, source, kept)` | Emit one chosen sample using the single-sample data schema. |
| `_build_multi_output` | `(self, sources, results)` | Regroup several chosen samples into the multi-sample data schema. |
| `_recompute_stale` | `(self, sources)` | Refresh cached knowledge of the incoming samples: which isotope |
| `stale_labels` | `(self)` | List labels referenced by filters but missing in their samples. |
| `is_active` | `(self)` | Report whether the node is doing anything beyond passthrough. |
| `summary_text` | `(self)` | Build the live summary shown under the node icon. |
| `configure` | `(self, parent_window)` | Open the configuration dialog (double-click). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ual` | `()` | Return the UserActionLogger, or None if logging isn't ready. |
| `_num_text` | `(v)` | Format a numeric filter value for a QLineEdit without trailing zeros. |
| `_empty_conc_meta` | `()` | Build an empty concentration metadata entry. |
| `_default_particle_data_field` | `()` | Build one (mass or counts) sub-filter's default (inactive) state. |
| `default_filter_config` | `()` | Build the default (inactive) per-sample filter configuration. |
| `_particle_data_field_valid` | `(field)` | Check whether one Particle Data sub-filter (mass/counts) is valid. |
| `particle_data_valid` | `(pd_cfg)` | Check whether an enabled Particle Data box's sub-filters are valid. |
| `active_axes` | `(config)` | List the filter axes that are enabled and meaningfully configured. |
| `summarize_config` | `(config)` | Build a short human-readable summary of one filter configuration. |
| `referenced_labels` | `(config)` | Collect the isotope labels referenced by enabled filter axes. |
| `stale_from_available` | `(avail, config)` | Find referenced labels that are missing from the available set. |
| `detected_labels` | `(particle, thr_unit, thr_values)` | Build the set of isotope labels detected in a particle. |
| `_composition_passes` | `(comp_labels, mode, detected)` | Evaluate the isotopic composition axis for one particle. |
| `_particle_scalar_mass_fg` | `(particle)` | Read a particle's whole-particle mass total (fg), if computed. |
| `_particle_scalar_counts` | `(particle)` | Read a particle's whole-particle raw signal count (machine |
| `_particle_data_field_passes` | `(particle, key, field)` | Evaluate one Particle Data sub-filter (mass or counts). |
| `particle_passes` | `(particle, comp_labels, mode, count_cfg, thr_unit, thr_values, particl` | Evaluate every active filter axis against one particle (AND logic). |
| `effective_criteria` | `(config, stale)` | Resolve a filter configuration into evaluation-ready criteria. |
| `_expand_upstream_entries` | `(u)` | Flatten ONE upstream dict into source entries, with no cross-stream |
| `_disambiguate_name` | `(name, seen)` | Return a unique sample name, appending ``" (N)"`` on collision. |
| `normalize_sources` | `(upstreams)` | Flatten the connected upstream dicts into one simple sample list. |
| `_duplicate_signature` | `(entry_a, entry_b)` | Stable, content-based key identifying a suspected-duplicate pair. |
| `_apply_duplicate_resolutions` | `(entries, resolutions)` | Apply previously-decided duplicate-sample resolutions to a raw |
| `resolve_and_normalize_sources` | `(upstreams, resolutions=None)` | Like :func:`normalize_sources`, but first applies any remembered |
| `source_labels` | `(source)` | Collect the isotope labels available in one source entry. |
| `apply_sample_filter` | `(source, config, retag=True)` | Filter one source's particles with that sample's own configuration. |
| `retag_particles` | `(particles, name)` | Regroup already-copied particles under a new sample name. |
| `merge_single_sources` | `(sources, name)` | Combine several single-sample source entries into one synthetic one. |
| `_bump_filt_suffix` | `(name)` | Append or increment a ``"(filt xN)"`` provenance suffix on a sample name. |
| `_retag_copy` | `(p, name)` | Shallow-copy a particle and regroup the copy under ``name``. |
| `_apply_filt_provenance` | `(out)` | Stamp a filter output dict's sample names with ``"(filt xN)"``. |
| `build_multi_sample_dict` | `(sources, parent_window=None)` | Assemble a ``multiple_sample_data`` dict from normalized source entries. |
| `prune_config_to_labels` | `(config, labels)` | Copy a filter configuration keeping only criteria for given labels. |
| `build_particle_filter_node_item` | `()` | Create the ParticleFilterNodeItem class bound to the canvas widgets. |
