# `splash_screen.py`

Animated splash screen with particle effects and progressive loading integration.

---

## Classes

### `Config`

### `AnimatedValue` *(extends `QObject`)*

Animatable float that triggers a widget repaint on every change.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, widget: QWidget, initial: float=0.0)` |  |
| `_get` | `(self) → float` |  |
| `_set` | `(self, value: float) → None` |  |

### `Particle`

Particle orbiting a center point with a pulsing size/opacity.

| Method | Signature | Description |
|--------|-----------|-------------|
| `random` | `(cls, center: QPointF, orbit_radius: float) → 'Particle'` |  |
| `update` | `(self, time_factor: float) → None` |  |
| `position` | `(self) → QPointF` |  |

### `SplashScreen` *(extends `QWidget`)*

Animated circular splash screen with particle effects and progress.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, logo_path: Optional[str]=None, app_name: str='IsotopeTrack', ve` |  |
| `_configure_window` | `(self) → None` |  |
| `_build_particles` | `(self) → None` |  |
| `_build_ui` | `(self) → None` |  |
| `_build_gradients` | `(self) → None` | Pre-compute gradients that never change between frames. |
| `_build_animations` | `(self) → None` |  |
| `update_progress` | `(self, progress: float, status_text: str='') → None` | Update progress (0–100) and optional status text. |
| `set_loading_complete` | `(self) → None` | Mark loading complete and schedule the close. |
| `get_progress` | `(self) → float` |  |
| `set_progress` | `(self, value: float) → None` |  |
| `_tick` | `(self) → None` |  |
| `paintEvent` | `(self, event) → None` |  |
| `_paint_glow` | `(self, painter: QPainter) → None` |  |
| `_paint_rings` | `(self, painter: QPainter) → None` |  |
| `_paint_particles` | `(self, painter: QPainter) → None` |  |
| `_paint_progress_arc` | `(self, painter: QPainter) → None` |  |
| `_paint_progress_text` | `(self, painter: QPainter) → None` |  |
| `_finish` | `(self) → None` |  |
| `closeEvent` | `(self, event) → None` |  |

### `SplashCoordinator` *(extends `QObject`)*

Coordinates the splash screen with progressive main-window loading.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, logo_path: Optional[str]=None, main_window_class: Optional[type` |  |
| `start` | `(self) → None` |  |
| `_on_loading_complete` | `(self) → None` |  |
| `_on_splash_finished` | `(self) → None` |  |
