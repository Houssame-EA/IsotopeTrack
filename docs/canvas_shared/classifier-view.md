# `classifier_view.py`

Shared reader API for rendering Particle Classifier output in viz nodes.

Pure Python, **no Qt** -- importable and unit-testable headless from
anywhere. The matching UI piece (the role picker) lives beside the other
reusable settings-group builders in ``results/shared_plot_utils.py``
(``ClassifierViewGroup``), because that is where every settings dialog
already looks for them.

Why this module exists
----------------------

The Particle Classifier collapses each particle's composition dicts to a
single ``{bucket_label: value}`` entry so a bucket looks "exactly like
another isotope" downstream (``.claude/PARTICLE_CLASSIFIER_DESIGN.md`` §7).
That works for any node reading one composition key at a time, and breaks
every node that needs the particle's whole key-SET (co-occurrence
groupings) or 2+ keys from one particle at once (ratios, correlations,
ternary vertices). Rather than a bespoke fix per node, the classifier now
*dual-carries* the untouched originals alongside the collapse, and this
module is the single seam every viz node reads them through.

See ``.claude/aug24.md``, "Classifier -> viz plotting correctness".

The role model
--------------

A bucket plays exactly one role in a given plot, and which roles are even
*available* is a property of the node's arity class, not of the chart type:

``ROLE_SERIES``
    The bucket IS the plotted category (today's behavior: one bar, one
    wedge, one histogram series per bucket). Only meaningful for nodes that
    read one composition key at a time -- for anything else the collapse is
    exactly what breaks the chart, so offering SERIES would be offering the
    bug.
``ROLE_FACET``
    The bucket partitions particles into separate panels; real isotopes go
    back on the axes *within* each panel. "Within Smelter-type particles,
    does Fe correlate with Ti?"
``ROLE_ENCODE``
    One shared plot over real isotopes; the bucket becomes a color/marker/
    highlight on individual marks. The canonical "scatter colored by
    classification". For aggregate-statistic charts (correlation matrix,
    network) there are no per-particle marks to color, so ENCODE there means
    annotating the isotope axis labels by which expression references them.
``ROLE_OFF``
    Ignore buckets; render real isotopes exactly as an unclassified stream
    would. The honest default for every non-SERIES node, so a chart never
    silently degenerates -- it shows the normal thing until the user opts in.

A fifth role, VALIDATE (comparing a *discovered* clustering against the
*asserted* buckets), is specific to the clustering node and deliberately
not implemented here -- see ``aug24.md``'s "Hibernated: clustering".

---

## Constants

| Name | Value |
|------|-------|
| `ROLE_SERIES` | `'series'` |
| `ROLE_FACET` | `'facet'` |
| `ROLE_ENCODE` | `'encode'` |
| `ROLE_OFF` | `'off'` |
| `ROLE_CONFIG_KEY` | `'classifier_role'` |
| `ROLE_LABELS` | `{ROLE_SERIES: 'GROUPS - plot the classifier groups themse…` |
| `ARITY_PER_KEY` | `'per_key'` |
| `ARITY_KEY_SET` | `'key_set'` |
| `ARITY_MULTI_KEY` | `'multi_key'` |
| `ARITY_HEATMAP` | `'heatmap'` |
| `ARITY_MATRIX` | `'matrix'` |
| `_ROLES_BY_ARITY` | `{ARITY_PER_KEY: (ROLE_SERIES, ROLE_OFF), ARITY_KEY_SET: (…` |
| `_DEFAULT_ROLE_BY_ARITY` | `{ARITY_PER_KEY: ROLE_SERIES, ARITY_KEY_SET: ROLE_OFF, ARI…` |
| `SCOPE_DEFINITION` | `'definition'` |
| `SCOPE_TOTAL_PARTICLE` | `'total_particle'` |
| `SCOPE_CONFIG_KEY` | `'classifier_agg_scope'` |
| `SCOPE_LABELS` | `{SCOPE_DEFINITION: 'BY DEFINITION - only the isotopes tha…` |
| `DENOMINATOR_WHOLE_GROUP` | `'whole_group'` |
| `DENOMINATOR_DETECTED_ONLY` | `'detected_only'` |
| `DENOMINATOR_CONFIG_KEY` | `'classifier_group_denominator'` |
| `DENOMINATOR_LABELS` | `{DENOMINATOR_WHOLE_GROUP: 'Whole Group - every particle i…` |
| `FALLBACK_BUCKET_COLOR` | `'#3B82F6'` |
| `UNCLASSIFIED_LABEL` | `'Unclassified'` |
| `CLASSIFIER_WIP_NODE_TYPES` | `frozenset({'pie_chart_plot', 'element_composition_plot', …` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `available_roles` | `(arity)` | Roles a node of this arity class may offer. |
| `default_role` | `(arity)` | The role a node of this arity should start in. |
| `effective_role` | `(config, input_data, arity)` | Resolve the role actually in force for this render. |
| `effective_scope` | `(config, input_data)` | Resolve the aggregation scope actually in force for this render. |
| `effective_denominator` | `(config, input_data)` | Resolve the group-row denominator actually in force for this render. |
| `is_classifier_stream` | `(input_data)` | Whether this upstream data came through a Particle Classifier. |
| `bucket_registry` | `(input_data)` | ``{label: {'color', 'is_group', 'definitions': [...]}}`` for the stream. |
| `bucket_labels` | `(input_data)` | Every bucket label this stream can contain, in registry order. |
| `bucket_color` | `(input_data, label, default=None)` | The user's chosen color for one bucket, or ``default``. |
| `expressions_for` | `(input_data, label)` | The literal classifier expression(s) defining one bucket. |
| `bucket_caption` | `(input_data, label, max_len=80)` | A display string naming a bucket AND what actually defines it. |
| `raw_selected_isotopes` | `(input_data)` | The upstream isotope vocabulary, before bucket relabeling. |
| `raw_isotope_labels` | `(input_data)` | Just the label strings from :func:`raw_selected_isotopes`. |
| `composition` | `(particle, data_key, collapsed=False)` | One particle's composition dict for ``data_key``. |
| `scope_isotopes` | `(particle, scope)` | The isotope keys "in scope" for this particle's bucket membership, |
| `composition_items_for_role` | `(particle, data_key, role, scope=SCOPE_DEFINITION)` | ``(label, value)`` pairs one particle contributes for ``data_key`` |
| `bucket_of` | `(particle)` | The bucket label assigned to one particle. |
| `particle_identity` | `(particle)` | A hashable identity for one *source* particle. |
| `dedupe_particles` | `(particles)` | Collapse double-counted copies back to one particle each. |
| `particles_by_bucket` | `(particles, include_unclassified=True)` | Partition particles by assigned bucket -- the FACET primitive. |
| `group_composition_rows` | `(particles, data_key, scope, denominator)` | Aggregate real per-isotope values into one row per classifier bucket. |
| `default_row_bucket_colors` | `(input_data, row_particles, include_unclassified=False)` | Classifier-derived underline color(s) for one COLORS-mode heatmap row. |
| `has_multiple_buckets` | `(input_data)` | Whether faceting/encoding by bucket would produce more than one group. |
| `overlap_mode` | `(input_data)` | The classifier's overlap resolution mode for this stream. |
| `is_double_count` | `(input_data)` | Whether a particle can be emitted into more than one bucket at once. |
| `mass_sort_key` | `(input_data, label, data_key='elements')` | A numeric sort key that makes classifier bucket labels sort like |
| `sort_labels_by_mass` | `(input_data, labels, data_key='elements')` | ``sort_elements_by_mass``-shaped drop-in that also handles bucket |
| `sort_label_dict_by_mass` | `(input_data, label_dict, data_key='elements')` | ``sort_element_dict_by_mass``-shaped drop-in that also handles |
| `classifier_support_is_wip` | `(node_type)` | Whether classifier support is unshipped for this viz node type. |
| `declassified_particles` | `(particles)` | Particles as they would have been with no classifier in the chain. |
| `declassified_stream` | `(input_data)` | ``input_data`` with classifier structure undone -- see |
| `adopt_declassified` | `(node, input_data)` | ``process_data`` helper for a node whose classifier support is WIP. |
