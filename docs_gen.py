#!/usr/bin/env python3
"""
docs_gen.py — Regenerate the MkDocs module reference pages from source code.

Scans the IsotopeTrack source tree with `ast`, writes one markdown page per
module (constants / classes / methods / functions tables), rebuilds each
section's index.md, and rewrites the `nav:` block of mkdocs.yml.

Usage:
    python docs_gen.py

Run this whenever modules are added, removed, or significantly changed.
The docs GitHub workflow also runs it automatically before deploying.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"

# ── Section layout: (nav title, docs subdir, description, [source files]) ────
def _glob(pattern, exclude=()):
    return sorted(
        p for p in ROOT.glob(pattern)
        if "__pycache__" not in p.parts and p.name not in exclude
    )

SECTIONS = [
    ("Entry Points", "entry_points",
     "Application startup: CLI parsing, splash screen, progressive loading.",
     [ROOT / "Run.py", ROOT / "tools/cli_utils.py",
      ROOT / "tools/progressive_main_window.py", ROOT / "tools/splash_screen.py"]),
    ("Main Window", "main_window",
     "The central application window.",
     [ROOT / "mainwindow.py"]),
    ("Theme System", "theme",
     "Application-wide theming and colors.",
     [ROOT / "tools/theme.py", ROOT / "widget/colors.py"]),
    ("Data Loading", "loading",
     "Instrument data readers: Nu Vitesse, TOFWERK, CSV, and background threads.",
     _glob("loading/*.py")),
    ("Project & I/O", "project_io",
     "Project save/load, session management, and export utilities.",
     _glob("save_export/*.py") + [ROOT / "tools/unit.py"]),
    ("Peak Detection", "peak_detection",
     "Particle detection algorithms and single-ion-area management.",
     _glob("processing/*.py")),
    ("Calibration", "calibration",
     "Ionic calibration and transport-efficiency methods.",
     _glob("calibration_methods/*.py")),
    ("Canvas & Shared", "canvas_shared",
     "Workflow canvas and shared plotting infrastructure.",
     [ROOT / "widget/canvas_widgets.py", ROOT / "widget/custom_plot_widget.py",
      ROOT / "results/shared_plot_utils.py", ROOT / "results/shared_annotation.py",
      ROOT / "results/utils_sort.py"]),
    ("Results", "results",
     "All plot/analysis result modules (bar charts, clustering, isotope ratios, AI, …).",
     [p for p in _glob("results/results_*.py")]),
    ("Widgets & UI", "widgets_ui",
     "Reusable dialogs, tables, and UI widgets.",
     [p for p in _glob("widget/*.py")
      if p.name not in ("canvas_widgets.py", "custom_plot_widget.py", "colors.py")]
     + [ROOT / "tools/help_dialogs.py", ROOT / "tools/tutorial.py",
        ROOT / "tools/element_picker.py", ROOT / "tools/parameters_table.py",
        ROOT / "tools/Info_table.py", ROOT / "tools/info_file.py",
        ROOT / "tools/signal_selector_dialog.py"]),
    ("Tools & Utilities", "tools_utilities",
     "Support utilities: logging, materials database, filters, updates.",
     [p for p in _glob("tools/*.py")
      if p.name not in ("cli_utils.py", "progressive_main_window.py",
                        "splash_screen.py", "theme.py", "unit.py",
                        "help_dialogs.py", "tutorial.py", "element_picker.py",
                        "parameters_table.py", "Info_table.py", "info_file.py",
                        "signal_selector_dialog.py")]),
    ("Utils (Non-Visual)", "utils",
     "Pure-logic helpers with no Qt UI: versioning, isobaric-interference math, "
     "export units, and dilution/concentration calculations.",
     _glob("utils/*.py")),
]

SIG_MAX = 70


def first_line(doc):
    if not doc:
        return ""
    line = doc.strip().splitlines()[0].strip()
    return line.replace("|", "\\|")


def fmt_sig(fn):
    try:
        args = ast.unparse(fn.args)
    except Exception:
        args = "..."
    sig = f"({args})"
    ret = ""
    if fn.returns is not None:
        try:
            ret = f" → {ast.unparse(fn.returns)}"
        except Exception:
            ret = ""
    out = sig + ret
    if len(out) > SIG_MAX:
        out = out[:SIG_MAX]
    return out.replace("|", "\\|")


def parse_module(path):
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    mod_doc = ast.get_docstring(tree)

    constants, classes, functions = [], [], []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.isupper() or (name.startswith("_") and name[1:].isupper()):
                try:
                    val = ast.unparse(node.value)
                except Exception:
                    val = "…"
                if len(val) > 60:
                    val = val[:57] + "…"
                constants.append((name, val.replace("|", "\\|")))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((node.name, fmt_sig(node),
                              first_line(ast.get_docstring(node))))
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            methods = [(n.name, fmt_sig(n), first_line(ast.get_docstring(n)))
                       for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append((node.name, bases, first_line(ast.get_docstring(node)),
                            methods))
    return mod_doc, constants, classes, functions


def slug(name):
    return name[:-3].replace("_", "-").lower()


def render_page(path, mod_doc, constants, classes, functions):
    L = [f"# `{path.name}`", ""]
    if mod_doc:
        L += [mod_doc, ""]
    L += ["---", ""]
    if constants:
        L += ["## Constants", "", "| Name | Value |", "|------|-------|"]
        L += [f"| `{n}` | `{v}` |" for n, v in constants]
        L.append("")
    if classes:
        L += ["## Classes", ""]
        for name, bases, doc, methods in classes:
            ext = f" *(extends `{', '.join(bases)}`)*" if bases else ""
            L.append(f"### `{name}`{ext}")
            L.append("")
            if doc:
                L += [doc, ""]
            if methods:
                L += ["| Method | Signature | Description |",
                      "|--------|-----------|-------------|"]
                L += [f"| `{m}` | `{s}` | {d} |" for m, s, d in methods]
                L.append("")
    if functions:
        L += ["## Functions", "", "| Function | Signature | Description |",
              "|----------|-----------|-------------|"]
        L += [f"| `{f}` | `{s}` | {d} |" for f, s, d in functions]
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main():
    nav_lines = ["nav:", "- Home: index.md", "- Changelog: changelog.md"]
    for title, subdir, desc, files in SECTIONS:
        files = [f for f in files if f.exists()]
        if not files:
            continue
        outdir = DOCS / subdir
        outdir.mkdir(parents=True, exist_ok=True)
        # remove stale generated pages (keep index.md until regenerated)
        valid = {f"{slug(f.name)}.md" for f in files} | {"index.md"}
        for old in outdir.glob("*.md"):
            if old.name not in valid:
                old.unlink()
                print(f"  removed stale {old.relative_to(ROOT)}")

        nav_lines.append(f"- {title}:")
        nav_lines.append(f"    - Overview: {subdir}/index.md")
        idx = [f"# {title}", "", desc, "", "---", ""]
        for f in files:
            mod_doc, consts, classes, funcs = parse_module(f)
            page = render_page(f, mod_doc, consts, classes, funcs)
            (outdir / f"{slug(f.name)}.md").write_text(page, encoding="utf-8")
            n_m = sum(len(c[3]) for c in classes)
            idx.append(f"### [`{f.name}`]({slug(f.name)}.md)")
            idx.append(first_line(mod_doc) or "")
            idx.append("")
            idx.append(f"**{len(classes)}** classes &nbsp;·&nbsp; "
                       f"**{len(funcs)}** functions &nbsp;·&nbsp; "
                       f"**{n_m}** methods")
            idx.append("")
            nav_lines.append(f'    - "{f.name}": {subdir}/{slug(f.name)}.md')
        (outdir / "index.md").write_text("\n".join(idx).rstrip() + "\n",
                                         encoding="utf-8")
        print(f"{title}: {len(files)} pages")

    # ── rewrite nav: block in mkdocs.yml ─────────────────────────────────────
    cfg = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    new_nav = "\n".join(nav_lines) + "\n"
    m = re.search(r"^nav:\n(?:[-\s].*\n?)*", cfg, re.M)
    if m:
        cfg = cfg[:m.start()] + new_nav + cfg[m.end():]
    else:
        cfg = cfg.rstrip() + "\n\n" + new_nav
    (ROOT / "mkdocs.yml").write_text(cfg, encoding="utf-8")
    print("mkdocs.yml nav updated")


if __name__ == "__main__":
    main()
