# `explain.py`

Plain-language explanations of each kind of finding.

Every card in the Insights panel can open a details section with three short
paragraphs, shown as plain prose without headings: first exactly what was
measured and tested, with the thresholds the code applies, so the claim can
be checked; then what the pattern usually means physically; last, the common
ways the same pattern arises for other reasons and what to look at to tell
them apart.

The texts describe the method and its known pitfalls only. They never claim
more than the statistics support: a finding is a pattern in the data, and the
explanation says which causes are consistent with it, not which one is true.

---

## Classes

### `Explanation`

The three paragraphs shown under a finding.

Attributes:
    found: How the finding was detected.
    meaning: How to read it.
    check: What to verify before relying on it.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `explanation_for` | `(key: str, category: str='') → Explanation \| None` | Return the explanation for a finding. |
