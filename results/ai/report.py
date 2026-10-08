"""Export a conversation as one self-contained HTML report.

The report keeps everything needed to trust and repeat an answer: the
questions, the model's explanations, the code that ran, the tables and the
figures (embedded as PNG). It opens in any browser and prints to PDF.
"""
from __future__ import annotations

import base64
import html
import time

from results.ai.theme import md_to_html

_CSS = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:960px;margin:32px auto;
     padding:0 20px;color:#0F172A;line-height:1.55}
h1{font-size:22px;margin-bottom:2px} .meta{color:#64748B;font-size:13px;margin-bottom:28px}
.user{background:#EFF6FF;border-left:4px solid #3B82F6;padding:10px 14px;margin:22px 0 10px;border-radius:6px}
.ai{margin:8px 0}
details{margin:8px 0} summary{cursor:pointer;color:#475569;font-size:13px}
pre{background:#0F172A;color:#E2E8F0;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px}
table{border-collapse:collapse;font-size:12px;margin:8px 0;width:100%}
th,td{border:1px solid #E2E8F0;padding:4px 8px;text-align:left} th{background:#F1F5F9}
.caption{font-weight:600;font-size:13px;margin-top:14px} .note{color:#64748B;font-size:12px}
.err{background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;padding:8px 12px;border-radius:6px;font-size:13px}
img{max-width:100%;border:1px solid #E2E8F0;border-radius:6px;margin:6px 0}
@media print{details{display:block} summary{display:none}}
"""


def _table_html(t, max_rows=200):
    """HTML for one result table."""
    head = ''.join(f"<th>{html.escape(str(h))}</th>" for h in t.get('headers', []))
    rows = t.get('rows', [])
    body = ''.join('<tr>' + ''.join(f"<td>{html.escape(str(c))}</td>" for c in r) + '</tr>'
                   for r in rows[:max_rows])
    more = f"<div class='note'>{len(rows) - max_rows} more rows not shown.</div>" if len(rows) > max_rows else ''
    note = f"<div class='note'>{html.escape(t['note'])}</div>" if t.get('note') else ''
    return (f"<div class='caption'>{html.escape(t.get('title', ''))}</div>{note}"
            f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}")


def build_html(title, records, dataset_line=''):
    """Render a conversation transcript.

    Args:
        title (str): Report title.
        records (list): Transcript entries, each a dict with a ``kind`` of
            ``user``, ``assistant``, ``code``, ``table``, ``figure``,
            ``text``, ``error`` or ``exploration``.
        dataset_line (str): One line describing the data.

    Returns:
        str: The HTML document.
    """
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
           f"<style>{_CSS}</style></head><body>",
           f"<h1>{html.escape(title)}</h1>",
           f"<div class='meta'>IsotopeTrack AI Data Assistant · {time.strftime('%Y-%m-%d %H:%M')}"
           + (f" · {html.escape(dataset_line)}" if dataset_line else '') + "</div>"]
    for r in records:
        kind = r.get('kind')
        if kind == 'user':
            out.append(f"<div class='user'>{html.escape(r.get('text', ''))}</div>")
        elif kind == 'assistant':
            out.append(f"<div class='ai'>{md_to_html(r.get('text', ''))}</div>")
        elif kind == 'code':
            out.append("<details><summary>Code that ran</summary>"
                       f"<pre>{html.escape(r.get('text', ''))}</pre></details>")
        elif kind == 'table':
            out.append(_table_html(r.get('table', {})))
        elif kind == 'figure':
            png = r.get('png') or b''
            b64 = base64.b64encode(png).decode('ascii')
            out.append(f"<div class='caption'>{html.escape(r.get('title', ''))}</div>"
                       f"<img alt='figure' src='data:image/png;base64,{b64}'>")
        elif kind == 'text':
            out.append(f"<pre>{html.escape(r.get('text', ''))}</pre>")
        elif kind == 'error':
            out.append(f"<div class='err'>{html.escape(r.get('text', ''))}</div>")
        elif kind == 'exploration':
            out.append(f"<div class='caption'>Exploration: {html.escape(r.get('question', ''))}</div>")
            out.append(f"<div class='ai'>{md_to_html(r.get('summary', ''))}</div>")
            findings = r.get('findings') or ''
            if findings:
                out.append(f"<details><summary>Recorded findings</summary><pre>{html.escape(findings)}</pre></details>")
    out.append("</body></html>")
    return '\n'.join(out)
