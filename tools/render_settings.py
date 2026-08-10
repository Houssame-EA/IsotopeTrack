"""Persisted rendering preferences shared by the launcher and the UI.

The cluster animation is drawn by Chromium, which reads its GPU flag from the
environment before any application object exists. Keeping the key and its
default in one place lets ``Run.py`` apply the preference at startup and the
View menu change it later without the two drifting apart.

GPU rendering is the default. Old graphics drivers can make Chromium abort
below Python, taking the whole application with it, so the preference exists
as an escape hatch for machines where the Clusters tab misbehaves.
"""
from PySide6.QtCore import QSettings

_ORG = "IsotopeTrack"
_APP = "IsotopeTrack"
_CLUSTER_GPU_KEY = "render/cluster_gpu"


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
