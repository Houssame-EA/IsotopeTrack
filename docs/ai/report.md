# `report.py`

Export a conversation as one self-contained HTML report.

The report keeps everything needed to trust and repeat an answer: the
questions, the model's explanations, the code that ran, the tables and the
figures (embedded as PNG). It opens in any browser and prints to PDF.

---

## Constants

| Name | Value |
|------|-------|
| `_CSS` | `'\nbody{font-family:-apple-system,Segoe UI,Helvetica,Aria…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_table_html` | `(t, max_rows=200)` | HTML for one result table. |
| `build_html` | `(title, records, dataset_line='')` | Render a conversation transcript. |
