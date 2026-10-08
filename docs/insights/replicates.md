# `replicates.py`

Work out which samples are replicates of one another.

Insights compares *groups* of samples, never one replicate against its own
siblings. A group is either set by the user, through the ``sum_group`` field of
a multiple sample selector or the summed replicates of a single selector, or
guessed from the sample names when the user has grouped nothing.

The naming rules are the same ones the multiple sample selector's Auto-group
button uses, so a guess made here matches what the user would get by pressing
that button.

---

## Constants

| Name | Value |
|------|-------|
| `_ROOT_PATTERNS` | `('(?:^\|[_\\-\\s])(?:replicate\|replica\|rep\|r)[\\s_\\-]?\\d…` |

## Classes

### `ReplicateGroup`

Samples that measure the same material.

Attributes:
    name: Group label shown on cards and used as the ``sum_group`` when a
        selector is built for the group.
    members: Sample names in the group, in load order.
    source: ``"user"`` when the user grouped these samples, ``"auto"``
        when the grouping was guessed from names, ``"single"`` for a sample
        that stands alone.

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_replicated` | `(self) → bool` | Return whether the group holds more than one sample. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `replicate_root` | `(name: str) → str` | Strip a replicate suffix from a sample name. |
| `auto_group_map` | `(names) → dict[str, str]` | Guess replicate groups from sample names. |
| `user_group_map` | `(scene, names) → dict[str, str]` | Read the replicate groups the user set on the canvas. |
| `resolve_groups` | `(names, user_map: dict[str, str] \| None=None) → list[ReplicateGroup]` | Split samples into replicate groups. |
| `describe_grouping` | `(groups) → str` | Summarise a grouping in a few words for the panel header. |
