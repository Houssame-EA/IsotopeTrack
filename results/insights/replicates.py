"""Work out which samples are replicates of one another.

Insights compares *groups* of samples, never one replicate against its own
siblings. A group is either set by the user, through the ``sum_group`` field of
a multiple sample selector or the summed replicates of a single selector, or
guessed from the sample names when the user has grouped nothing.

The naming rules are the same ones the multiple sample selector's Auto-group
button uses, so a guess made here matches what the user would get by pressing
that button.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ROOT_PATTERNS = (
    r"(?:^|[_\-\s])(?:replicate|replica|rep|r)[\s_\-]?\d+$",
    r"[_\-\s]?\d+[_\-\s]?(?:replicate|replica|rep|r)$",
    r"[_\-\s]?\d+$",
    r"[_\-\s][A-Za-z]$",
)
"""Replicate suffixes, tried in order; the first one that strips something wins."""


def replicate_root(name: str) -> str:
    """Strip a replicate suffix from a sample name.

    Handles ``liver_rep1``, ``ctrl_R2``, ``sample_3``, ``HgSe_1mg_r1`` and
    ``2024_Au_A``. A replicate marker such as ``r`` or ``rep`` only counts when
    it starts a word, so ``liver_1`` becomes ``liver`` and not ``live``. A strip
    that would leave fewer than two characters is ignored, so a name such as
    ``S1`` is left as it is.

    Args:
        name: A sample name.

    Returns:
        The name without its replicate suffix, or the name unchanged when it
        carries none.
    """
    root = str(name)
    for pattern in _ROOT_PATTERNS:
        stripped = re.sub(pattern, "", root, flags=re.IGNORECASE).strip("_- ")
        if stripped and stripped != root and len(stripped) >= 2:
            return stripped
    return root


@dataclass(frozen=True)
class ReplicateGroup:
    """Samples that measure the same material.

    Attributes:
        name: Group label shown on cards and used as the ``sum_group`` when a
            selector is built for the group.
        members: Sample names in the group, in load order.
        source: ``"user"`` when the user grouped these samples, ``"auto"``
            when the grouping was guessed from names, ``"single"`` for a sample
            that stands alone.
    """

    name: str
    members: tuple[str, ...]
    source: str = "single"

    @property
    def is_replicated(self) -> bool:
        """Return whether the group holds more than one sample."""
        return len(self.members) > 1


def auto_group_map(names) -> dict[str, str]:
    """Guess replicate groups from sample names.

    Only roots shared by two or more samples form a group, so a lone sample
    keeps its own name even when it carries a suffix.

    Args:
        names: Sample names.

    Returns:
        Sample name to group name, for grouped samples only.
    """
    by_root: dict[str, list[str]] = {}
    for name in names:
        by_root.setdefault(replicate_root(name), []).append(name)
    return {
        member: root
        for root, members in by_root.items() if len(members) > 1
        for member in members
    }


def user_group_map(scene, names) -> dict[str, str]:
    """Read the replicate groups the user set on the canvas.

    Multiple sample selectors contribute through each sample's ``sum_group``,
    and single selectors through their summed replicates. When a sample is
    grouped differently on two nodes, the first node found wins.

    Args:
        scene: The canvas scene, or anything exposing ``workflow_nodes``.
        names: The samples being analysed. Groups naming other samples are
            ignored.

    Returns:
        Sample name to group name, for the samples the user grouped.
    """
    wanted = set(names)
    mapping: dict[str, str] = {}
    for node in getattr(scene, "workflow_nodes", None) or []:
        node_type = getattr(node, "node_type", "")
        if node_type == "multiple_sample_selector":
            for sample, cfg in (getattr(node, "sample_config", None) or {}).items():
                group = str((cfg or {}).get("sum_group") or "").strip()
                if group and sample in wanted:
                    mapping.setdefault(sample, group)
        elif node_type == "sample_selector":
            members = list(getattr(node, "replicate_samples", None) or [])
            if getattr(node, "sum_replicates", False) and len(members) > 1:
                group = replicate_root(members[0])
                for sample in members:
                    if sample in wanted:
                        mapping.setdefault(sample, group)
    return mapping


def resolve_groups(names, user_map: dict[str, str] | None = None) -> list[ReplicateGroup]:
    """Split samples into replicate groups.

    Samples the user grouped follow the user's groups. Every other sample is
    grouped by name with the other ungrouped samples, so a selector grouping a
    few samples never stops the rest from being recognised as replicates.

    Args:
        names: Sample names, in load order.
        user_map: Sample to group name, as read by :func:`user_group_map`.

    Returns:
        One group per distinct label, ordered by first member.
    """
    names = list(names)
    user_map = {k: v for k, v in (user_map or {}).items() if k in names}
    rest = [n for n in names if n not in user_map]
    guessed = {
        sample: root for sample, root in auto_group_map(rest).items()
        if root not in user_map.values()
    }

    order: list[str] = []
    members: dict[str, list[str]] = {}
    sources: dict[str, str] = {}
    taken = set(user_map.values()) | set(guessed.values())
    for name in names:
        if name in user_map:
            label, group_source = user_map[name], "user"
        elif name in guessed:
            label, group_source = guessed[name], "auto"
        else:
            label = name if name not in taken else f"{name} (alone)"
            group_source = "single"
        if label not in members:
            order.append(label)
            members[label] = []
            sources[label] = group_source
        members[label].append(name)

    return [ReplicateGroup(label, tuple(members[label]), sources[label]) for label in order]


def describe_grouping(groups) -> str:
    """Summarise a grouping in a few words for the panel header.

    Args:
        groups: Groups from :func:`resolve_groups`.

    Returns:
        Text such as ``"6 samples in 2 replicate groups (guessed from names)"``.
    """
    groups = list(groups)
    n_samples = sum(len(g.members) for g in groups)
    replicated = [g for g in groups if g.is_replicated]
    if not replicated:
        return f"{n_samples} sample{'s' if n_samples != 1 else ''}, no replicates"
    sources = {g.source for g in replicated}
    if sources == {"user"}:
        origin = "your groups"
    elif sources == {"auto"}:
        origin = "guessed from names"
    else:
        origin = "your groups and names"
    return (f"{n_samples} samples in {len(groups)} group"
            f"{'s' if len(groups) != 1 else ''}, {len(replicated)} with replicates ({origin})")
