# `equations_reference.py`

Equations & References — complete mathematical reference.

Every equation used in IsotopeTrack, organised by topic (Sensitivity,
Transport Rate, Detection & SIA, Quantification, Clustering). Equations
are rendered as real LaTeX via matplotlib mathtext; every equation has a
description, a definition of every parameter, and a worked numerical
example. References are given for each topic.

All formulas mirror the actual implementation in
calibration_methods/ionic_CAL.py, calibration_methods/te_common.py,
calibration_methods/TE_mass.py, processing/peak_detection.py,
loading/SIA_manager.py, mainwindow.py, utils/dilution.py,
tools/mass_fraction_calculator.py and results/results_cluster.py.

---

## Constants

| Name | Value |
|------|-------|
| `_PIXMAP_CACHE` | `{}` |
| `REFERENCES` | `{'currie1968': dict(label='Currie 1968', citation='Currie…` |
| `TOPIC_SENSITIVITY` | `[('h', '\n     <h2>Sensitivity — equations &amp; worked e…` |
| `TOPIC_TRANSPORT` | `[('h', "\n     <h2>Transport Rate — equations &amp; worke…` |
| `TOPIC_DETECTION` | `[('h', '\n     <h2>Detection &amp; Single-Ion Distributio…` |
| `TOPIC_QUANTIFICATION` | `[('h', "\n     <h2>Quantification — from counts to mass, …` |
| `TOPIC_CLUSTERING` | `[('h', '\n     <h2>Clustering — every method, explained</…` |
| `TOPICS` | `{'sensitivity': TOPIC_SENSITIVITY, 'transport': TOPIC_TRA…` |

## Classes

### `EquationLabel` *(extends `QLabel`)*

Label displaying one LaTeX equation, re-rendered on theme change.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, latex, fontsize=13, parent=None)` | Store the LaTeX source and render it. |
| `_render` | `(self)` | Render the equation with the current theme text color. |

### `ExampleBox` *(extends `QFrame`)*

Highlighted 'Worked example' box, styled with the theme accent.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, html, parent=None)` | Build the example box. |
| `apply_theme` | `(self)` | Apply the current theme palette to the box. |

### `RefEntry` *(extends `QFrame`)*

One reference in the References section: full citation, where it

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, key, parent=None)` | Build the reference entry. |
| `apply_theme` | `(self, highlight=False)` | Apply the theme palette, optionally with a flash highlight. |
| `flash` | `(self)` | Briefly highlight the entry after a citation click. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `render_latex` | `(latex, color, fontsize=13, scale=2.0)` | Render a LaTeX (mathtext) string to a high-DPI QPixmap. |
| `_scroll_ancestor` | `(widget)` | Find the QScrollArea containing a widget, if any. |
| `_handle_link` | `(href, container)` | Handle a clicked link: jump to a reference or open a URL. |
| `_prose_label` | `(html)` | Create a themed rich-text prose label. |
| `_where_html` | `(rows)` | Build the 'where:' parameter-definition table HTML. |
| `build_topic_widget` | `(topic_key, parent=None)` | Build the widget for one equations topic. |
