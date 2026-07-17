# `interactive_guide.py`

Interactive user-guide framework.

---

## Classes

### `HotspotImage` *(extends `QWidget`)*

Paint a screenshot scaled to the widget width and overlay

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, image_path, hotspots, parent=None)` | Initialise the widget with an image and its hotspot list. |
| `_aspect` | `(self)` | Return the height/width ratio of the loaded screenshot. |
| `resizeEvent` | `(self, event)` | Keep the widget height locked to the image aspect ratio. |
| `sizeHint` | `(self)` | Return the preferred size of the widget. |
| `_hotspot_rect` | `(self, spot)` | Map a hotspot's normalised rect to widget coordinates. |
| `_spot_at` | `(self, pos)` | Return the hotspot under a mouse position, if any. |
| `mouseMoveEvent` | `(self, event)` | Track hover state and switch the cursor over hotspots. |
| `leaveEvent` | `(self, event)` | Clear the hover highlight when the mouse leaves the image. |
| `mousePressEvent` | `(self, event)` | Emit hotspotClicked when a hotspot is left-clicked. |
| `set_selected` | `(self, spot_id)` | Mark a hotspot as the current selection and repaint. |
| `paintEvent` | `(self, event)` | Draw the screenshot and the hotspot overlays. |
| `_paint_badges` | `(self, painter, accent)` | Draw a numbered circle badge on each hotspot. |

### `InteractiveImagePage` *(extends `QWidget`)*

Scrollable page: intro text, interactive screenshot, and a

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, page, parent=None)` | Build the page from its content definition. |
| `_show_overview` | `(self)` | Show the default detail text listing all clickable regions. |
| `_show_detail` | `(self, spot_id)` | Display the explanation for the clicked hotspot. |
| `show_hotspot` | `(self, spot_id)` | Publicly select a hotspot and show its explanation. |
| `_step` | `(self, delta)` | Step to the previous or next hotspot on this page. |
| `apply_theme` | `(self)` | Apply the currently active theme palette to the page. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_resource_path` | `(relative_path)` | Resolve a resource path relative to the app bundle or source root. |
| `build_section_widget` | `(section, parent=None)` | Build the widget for one guide section. |
