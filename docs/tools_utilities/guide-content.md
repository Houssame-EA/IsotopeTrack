# `guide_content.py`

Content definitions for the interactive user guide.

Each SECTION contains PAGES; each page shows one screenshot from the
images/ folder with clickable hotspots. Hotspot rectangles are
(x, y, w, h) normalised to the image size (0..1). The 'body' HTML is
shown in the detail panel when the region is clicked.

Rendering is done by tools/interactive_guide.py.

---

## Constants

| Name | Value |
|------|-------|
| `SECTION_MAIN_WINDOW` | `dict(title='Main Window', pages=[dict(title='Main Window'…` |
| `SECTION_GETTING_STARTED` | `dict(title='Getting Started', pages=[dict(title='Welcome …` |
| `SECTION_MENUS` | `dict(title='Menus & Settings', pages=[dict(title='View Me…` |
| `SECTION_ELEMENTS_SIGNALS` | `dict(title='Elements & Signals', pages=[dict(title='Perio…` |
| `SECTION_DETECTION` | `dict(title='Detection', pages=[dict(title='Batch Edit Par…` |
| `SECTION_CALIBRATION` | `dict(title='Calibration', pages=[dict(title='Ionic Cal. —…` |
| `SECTION_RESULTS` | `dict(title='Results Canvas', pages=[dict(title='Workflow …` |
| `SECTION_EXPORT` | `dict(title='Export', pages=[dict(title='Export Options', …` |
| `SECTIONS` | `[SECTION_MAIN_WINDOW, SECTION_GETTING_STARTED, SECTION_ME…` |
