# `render_settings.py`

Persisted rendering and canvas preferences shared by the launcher and the UI.

The cluster animation is drawn by Chromium, which reads its GPU flag from the
environment before any application object exists. Keeping the key and its
default in one place lets ``Run.py`` apply the preference at startup and the
View menu change it later without the two drifting apart.

GPU rendering is the default. Old graphics drivers can make Chromium abort
below Python, taking the whole application with it, so the preference exists
as an escape hatch for machines where the Clusters tab misbehaves.

The same store also holds the application-wide opt-out for the "Downstream
plots may change" reminder raised when a canvas node's configuration is
applied. That reminder is shown by two independent implementations —
``widget.canvas_widgets._warn_before_apply_changes`` for the sample-selector
family and ``tools.particle_filter.ParticleFilterDialog._try_accept`` for the
Particle Filter — so the flag lives here, outside both, and ticking "Don't
show this again" in either one silences all of them for good.

---

## Constants

| Name | Value |
|------|-------|
| `_ORG` | `'IsotopeTrack'` |
| `_APP` | `'IsotopeTrack'` |
| `_CLUSTER_GPU_KEY` | `'render/cluster_gpu'` |
| `_STALE_WARNING_KEY` | `'canvas/suppress_stale_warning'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `cluster_gpu_enabled` | `()` | Return True when the cluster animation may use the GPU. |
| `set_cluster_gpu_enabled` | `(enabled)` | Store whether the cluster animation may use the GPU. |
| `stale_warning_suppressed` | `()` | Return True when the "Downstream plots may change" reminder is off. |
| `set_stale_warning_suppressed` | `(suppressed)` | Store whether the "Downstream plots may change" reminder is silenced. |
