# `attachments.py`

Reading files the user attaches to a chat message.

---

## Constants

| Name | Value |
|------|-------|
| `IMAGE_EXTS` | `{'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'ima…` |
| `TEXT_EXTS` | `{'.txt', '.csv', '.json', '.md', '.tsv', '.xml'}` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `read_image_b64` | `(path)` | Read an image file as base64 for vision models. |
| `extract_pdf_text` | `(path)` | Extract the text of a PDF. |
| `read_text_file` | `(path)` | Read a text file, truncated to 60,000 characters. |
| `try_parse_table` | `(text)` | Try to parse printed text as a table. Returns (headers, rows) or None. |
