"""Reading files the user attaches to a chat message."""
import base64
import logging
import os
import re

_itk_log = logging.getLogger("IsotopeTrack.results.ai.attachments")


IMAGE_EXTS = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
              '.bmp':'image/bmp','.tiff':'image/tiff','.webp':'image/webp'}
TEXT_EXTS  = {'.txt','.csv','.json','.md','.tsv','.xml'}

def read_image_b64(path):
    """Read an image file as base64 for vision models.

    Args:
        path (str): Image file.

    Returns:
        tuple: ``(base64_text, mime_type)``.
    """
    ext = os.path.splitext(path)[1].lower()
    mime = IMAGE_EXTS.get(ext, 'image/png')
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    return data, mime

def extract_pdf_text(path):
    """Extract the text of a PDF.

    Args:
        path (str): PDF file.

    Returns:
        str | None: The text, ``None`` when nothing could be read, or
        ``"__MISSING_PYPDF__"`` when pypdf is not installed.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        text = '\n'.join(pg.extract_text() or '' for pg in reader.pages)
        return text.strip() or None
    except ImportError:
        _itk_log.debug("Handled exception in extract_pdf_text")
        return "__MISSING_PYPDF__"
    except Exception:
        _itk_log.exception("Handled exception in extract_pdf_text")
        return None

def read_text_file(path):
    """Read a text file, truncated to 60,000 characters.

    Args:
        path (str): Text file.

    Returns:
        str: The content.
    """
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    if len(content) > 60000:
        content = content[:60000] + "\n\n[... file truncated at 60,000 chars ...]"
    return content


def try_parse_table(text):
    """Try to parse printed text as a table. Returns (headers, rows) or None."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2: return None
    sep_idx = None
    for i, l in enumerate(lines):
        if re.match(r'^[\s\-=|]+$', l) and len(l.strip()) > 4:
            sep_idx = i; break
    header_idx = (sep_idx - 1) if sep_idx and sep_idx > 0 else 0
    data_start  = (sep_idx + 1) if sep_idx is not None else 1
    header_line = lines[header_idx]
    data_lines  = lines[data_start:]
    if not data_lines: return None
    def _split(line):
        """Split one printed table row on runs of spaces or tabs."""
        return [c.strip() for c in re.split(r'  +|\t', line.strip()) if c.strip()]
    headers = _split(header_line)
    if len(headers) < 2: return None
    rows = []
    for l in data_lines:
        if re.match(r'^[\s\-=|]+$', l): continue
        row = _split(l)
        if len(row) >= 2: rows.append(row)
    if not rows: return None
    nc = len(headers)
    rows = [(r + [''] * nc)[:nc] for r in rows]
    return headers, rows
