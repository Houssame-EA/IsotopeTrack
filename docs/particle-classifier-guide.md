# Particle Classifier — user guide

The Particle Classifier sorts particles into named groups based on **which isotopes they contain**, then hands those groups to the rest of your workflow.

The mental model that makes everything else follow:

!!! tip "The one idea"
    The classifier relabels each particle's composition so that **the group name behaves like another isotope**. A chart that could plot `56Fe` can plot `Tirewear` the same way.

---

## Getting started

1. Drag a **Particle Classifier** onto the canvas.
2. Connect a **Particle Filter**, **Single Sample**, or **Multiple Sample** node upstream. Those are the only permitted upstream types.
3. Connect any Visualization node downstream (except the AI Data Assistant).
4. Double-click the classifier to configure it.
5. Pick a sample on the left, define one or more rules for it on the right, then **Apply to Current Sample** or **Apply to Selected Samples**.

Each rule is a **definition**: a name, an expression over isotopes, and a match mode. A particle matching a definition joins that group.

---

## Expression syntax

Expressions describe **which isotopes are present**, nothing more. There are no comparison or threshold operators — you cannot write `56Fe > 100`. Presence is the only question.

| Syntax | Meaning | Example |
|---|---|---|
| `+` | AND | `60Ni+107Ag` — contains both |
| `[a, b]` | OR across branches | `[60Ni, 107Ag]` — contains either |
| `{a; b}` | one-hot XOR | `{60Ni; 107Ag}` — exactly one, never both |
| `!(a)` | NOT | `!(208Pb)` — does not contain Pb |

Isotopes are written **mass first, correctly cased**: `56Fe`, `208Pb`, `27Al`.

Expressions combine, so `49Ti+27Al` is "contains both Ti and Al" and `[49Ti, 27Al]+!(208Pb)` is "contains Ti or Al, but not Pb".

---

## The two settings that surprise people

Both are set once and quietly shape everything downstream. If a chart looks wrong, check these first.

### Overlap mode: `priority` vs `double_count`

A particle can satisfy several definitions at once. This decides what happens.

**`priority`** — the particle lands in **exactly one** group: the first definition, in list order, that it matches.

- Order matters enormously. A broad definition placed *after* a narrower one can be starved of members entirely. If `common` = `49Ti+27Al` is listed first and `carney` = `27Al` second, then every Al-bearing particle that also has Ti goes to `common`, and `carney` only ever receives Al-without-Ti particles. If your data has none, `carney` gets **zero** members — which looks like a bug and isn't.
- Because no particle is ever in two groups, **group-vs-group comparisons are structurally empty**. On the correlation matrix, every group×group cell is blank. The chart says so rather than leaving you to guess.

**`double_count`** — the particle joins **every** group it matches, and is emitted once per match.

- This is what makes group-vs-group comparisons possible at all.
- It means the classifier reports **more particles than you have**. A particle matching two definitions is counted twice. This is intended, but it is why particle counts can differ between charts.

### Unmatched mode

What happens to particles that match no definition:

- **Unclassified** — collected into a single `Unclassified` group, which appears on charts alongside your named groups.
- **Passthrough** — left with their original isotopes, unlabelled.

For colour-based displays the two behave the same: neither gets a group colour.

---

## How charts present groups: the four roles

Charts that support the classifier offer a **role** in their settings, under a classifier group box. The box only appears when a classifier is actually connected upstream.

| Role | What it does | Use it when |
|---|---|---|
| **GROUPS** | Group names replace isotopes on the axis | You want to compare groups directly |
| **PANELS** | One subplot per group, real isotopes inside each | You want the isotope picture *within* each group |
| **COLORS** | One shared plot over real isotopes, group as colour | You want the whole sample at once, with group membership visible |
| **OFF** | Ignore groups entirely | You want the honest raw-isotope baseline |

Not every chart offers all four. Which roles appear depends on how many composition values that chart needs from a single particle at once — a ratio chart needs two simultaneously, so replacing them both with one group name would be meaningless. Charts only offer the roles that make sense for them.

---

## Aggregation scope: BY DEFINITION vs TOTAL PARTICLE

When a group name sits on an axis, the chart needs **a number** for that group, for each particle. This setting decides what that number sums over.

| Scope | The group's value is… |
|---|---|
| **BY DEFINITION** | only the isotopes the matching definition named |
| **TOTAL PARTICLE** | every isotope the qualifying particle carries |

**Example.** `Tirewear` is defined as `66Zn`. A particle contains Zn, Pb and Fe.

- **BY DEFINITION** → the group's value is that particle's **Zn only**.
- **TOTAL PARTICLE** → the group's value is its **Zn + Pb + Fe**.

### Why this matters more than it looks

Under **TOTAL PARTICLE** a group's value is a property of the *particle*, not of the group — it does not depend on which group is asking. So if a particle belongs to two groups, both groups hold the **identical number** for it.

On the correlation matrix, with the default "both present" zero handling, that makes any two groups correlate at exactly **1.00** — no matter how unrelated their definitions are. Two groups defined on completely different isotopes still hit 1.00, because the correlation is computed only over particles in both, and there the two columns are literally the same numbers.

That is why such cells show a `*` instead of a value: the 1.00 is arithmetic, not evidence.

Switch to **BY DEFINITION** and the same pair might read `0.94`. Both look like "high correlation" — but the first carries no information at all and the second is a real (if size-driven) relationship. Measured on one dataset, the underlying column values were **5× larger** under TOTAL PARTICLE, while the correlation barely moved. The numbers look alike and mean opposite things, which is precisely why the marker exists.

**Rule of thumb:** if you want group-vs-group comparisons to *mean* something, use **BY DEFINITION**. TOTAL PARTICLE is the better default for group-vs-isotope questions.

---

## Reading the `*` marker (correlation matrix)

The matrix marks correlations that are **arithmetic rather than evidence**, so that a genuine `1.00` between two unrelated things still stands out instead of blending into a wall of guaranteed 1s.

| What you see | Meaning |
|---|---|
| `*` alone | The value is **fixed by construction** and carries no information — the value is replaced. The leading diagonal is always marked. |
| `0.87*` | **Part-whole contamination** — the number is real and worth reading, but inflated because one side is a sum containing the other. |

A group correlated against one of its own defining isotopes is the common annotated case: the group's value is a sum that *includes* that isotope, so of course they track.

---

## Which charts support the classifier

| Chart | Support |
|---|---|
| Histogram | GROUPS, OFF |
| Element bar chart | GROUPS, OFF |
| Box plot | GROUPS, OFF |
| **Heatmap** | **all four roles** |
| **Correlation matrix** | GROUPS, PANELS, OFF |
| Pie chart | not yet |
| Element composition | not yet |
| Concentration comparison | not yet |
| Molar ratio | not yet |
| Isotopic ratio | not yet |
| Single / multiple element | not yet |
| Network diagram | not yet |
| Triangle plot | not yet |
| Correlation plot (scatter) | not yet |
| Clustering | not planned — see below |

### What "not yet" means in practice

You can still connect a classifier to those charts. They **ignore it completely** and plot exactly what they would have plotted with no classifier attached: your original isotopes, with each particle counted once. A one-time notice explains this the first time you open each chart type; tick the box to stop seeing it.

This is deliberate. Reading classifier output without support for it would show one synthetic "isotope" per group and produce confident, wrong numbers.

Two consequences worth knowing:

- **Group names never appear** on those charts, whatever the classifier says.
- With **`double_count`** on, those charts show **fewer particles** than the classifier reports, because they count each real particle once. That is the correct number, but it will look like a discrepancy side by side.

### Clustering

Clustering is not on the list and is not planned as a role adaptation. Clustering *discovers* groups from the data; the classifier *asserts* them. Colouring discovered clusters by asserted groups is close to a tautology. The useful thing would be a comparison — a confusion matrix or an agreement score between the two partitions — which is a different feature, not a display option.

---

## Troubleshooting

**A group has no members.** Under `priority`, check definition order — a broader definition listed after a narrower one may be starved. See [Overlap mode](#overlap-mode-priority-vs-double_count).

**Group-vs-group cells are all blank.** Expected under `priority`: no particle is ever in two groups, so no two groups co-occur. Switch to `double_count` if you need those comparisons.

**Every group-vs-group cell shows `*`.** You are on TOTAL PARTICLE with "both present" zero handling. The correlations really are exactly 1.00 by construction. Switch to BY DEFINITION for an informative number.

**Particle counts differ between charts.** Under `double_count` the classifier emits a particle once per matching group. Charts that support the classifier respect that; charts that ignore it count each real particle once.

**No classifier options appear in a chart's settings.** Either no classifier is connected upstream, or that chart doesn't support the classifier yet — see the support table.

**The chart didn't update after I changed something upstream.** It should update on its own. If it doesn't, that's a bug worth reporting.

---

## Related reference pages

- [`particle_classifier_node.py`](tools_utilities/particle-classifier-node.md) — the canvas node
- [`particle_classifier_dialog.py`](tools_utilities/particle-classifier-dialog.md) — the configuration dialog
- [`particle_classifier_expr.py`](tools_utilities/particle-classifier-expr.md) — expression parsing
- [`particle_classifier_relabel.py`](tools_utilities/particle-classifier-relabel.md) — how relabeling works
- [`classifier_view.py`](canvas_shared/classifier-view.md) — the shared reader API every chart uses to read classifier data
