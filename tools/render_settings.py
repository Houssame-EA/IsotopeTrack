"""Persisted rendering and canvas preferences shared by the launcher and the UI.

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
"""
from PySide6.QtCore import QSettings

_ORG = "IsotopeTrack"
_APP = "IsotopeTrack"
_CLUSTER_GPU_KEY = "render/cluster_gpu"
_STALE_WARNING_KEY = "canvas/suppress_stale_warning"


def cluster_gpu_enabled():
    """Return True when the cluster animation may use the GPU.

    Returns:
        bool: Stored preference, defaulting to True.
    """
    return QSettings(_ORG, _APP).value(_CLUSTER_GPU_KEY, True, type=bool)


def set_cluster_gpu_enabled(enabled):
    """Store whether the cluster animation may use the GPU.

    The value is read once at startup, so a change applies on the next launch.

    Args:
        enabled (bool): True to allow GPU rendering.
    """
    QSettings(_ORG, _APP).setValue(_CLUSTER_GPU_KEY, bool(enabled))


def stale_warning_suppressed():
    """Return True when the "Downstream plots may change" reminder is off.

    The preference is application-wide and persists across restarts: once the
    user ticks "Don't show this again" on any node's reminder, no node of any
    type raises it again until the flag is cleared.

    Returns:
        bool: Stored preference, defaulting to False (reminder shown).
    """
    return QSettings(_ORG, _APP).value(_STALE_WARNING_KEY, False, type=bool)


def set_stale_warning_suppressed(suppressed):
    """Store whether the "Downstream plots may change" reminder is silenced.

    Written when the user ticks "Don't show this again" on the reminder, from
    either implementation of it; read back by both on the next apply, so the
    opt-out is immediate and shared rather than per node.

    Args:
        suppressed (bool): True to stop showing the reminder everywhere.
    """
    QSettings(_ORG, _APP).setValue(_STALE_WARNING_KEY, bool(suppressed))
