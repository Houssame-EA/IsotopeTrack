"""Superseded by :mod:`loading.file_list_panel`.

The horizontal thumbnail strip this module used to provide was replaced by a
vertical list beside the preview, so the preview keeps the height it needs.
The names are re-exported here so any stale import keeps working; delete this
file once nothing references it.
"""
from __future__ import annotations

from loading.file_list_panel import FileEntry, FileListPanel

FileCard = FileEntry
FileCarousel = FileListPanel

__all__ = ["FileCard", "FileCarousel", "FileEntry", "FileListPanel"]
