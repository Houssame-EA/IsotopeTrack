"""Remembered import setups for the CSV dialog.

Configuring an import is the same work every time a batch of the same
instrument export arrives: point at the header row, map the columns to
isotopes, set the dwell. This keeps the last few setups so that work can be
recalled instead of repeated.

Setups are stored by column *name*, never by column position, so a recalled
setup still lands correctly on an export whose columns moved. A name that no
longer exists is reported rather than guessed at.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime

from PySide6.QtCore import QSettings

_itk_log = logging.getLogger("IsotopeTrack.loading.csv.profiles")

SETTINGS_ORG = "IsotopeTrack"
SETTINGS_APP = "IsotopeTrack"
SETTINGS_KEY = "csv_import/recent_setups"
MAX_PROFILES = 5


@dataclass
class ImportProfile:
    """One remembered import setup."""

    created: str = ""
    label: str = ""
    file_count: int = 0
    header_row: int = 0
    delimiter: str = ","
    params: dict = field(default_factory=dict)
    mappings: list = field(default_factory=list)
    removed_columns: list = field(default_factory=list)

    def describe(self) -> str:
        """Return a one-line summary for the chooser.

        Returns:
            str: Isotope labels and file count, or a note that nothing is mapped.
        """
        isotopes = [m.get('isotope', {}).get('label', '?')
                    for m in self.mappings]
        if not isotopes:
            return f"{self.file_count} file(s), nothing mapped"
        shown = ", ".join(isotopes[:6])
        if len(isotopes) > 6:
            shown += f" and {len(isotopes) - 6} more"
        return f"{len(isotopes)} isotope(s): {shown}"

    def when(self) -> str:
        """Return the save time in a readable form.

        Returns:
            str: A short date and time, or an empty string if it is unknown.
        """
        try:
            return datetime.fromisoformat(self.created).strftime(
                "%d %b %Y at %H:%M")
        except ValueError:
            return ""


def _settings() -> QSettings:
    """Return the shared application settings store."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def load_profiles() -> list[ImportProfile]:
    """Return the remembered setups, most recent first.

    A store that cannot be read is treated as empty rather than raised: a
    corrupt preference should not stop a file being imported.

    Returns:
        list[ImportProfile]: The saved setups.
    """
    raw = _settings().value(SETTINGS_KEY, "")
    if not raw:
        return []
    try:
        records = json.loads(raw)
    except (ValueError, TypeError):
        _itk_log.warning("Could not read the remembered import setups")
        return []

    profiles = []
    for record in records[:MAX_PROFILES]:
        if not isinstance(record, dict):
            continue
        try:
            profiles.append(ImportProfile(**record))
        except TypeError:
            _itk_log.debug("Skipping an unreadable setup record")
    return profiles


def save_profile(profile: ImportProfile) -> list[ImportProfile]:
    """Add one setup to the front of the list and drop the oldest.

    A setup identical to the most recent one replaces it instead of stacking
    up, so importing the same batch twice does not fill the list with copies.

    Args:
        profile (ImportProfile): The setup to remember.

    Returns:
        list[ImportProfile]: The stored setups after the addition.
    """
    profiles = [p for p in load_profiles() if not _same_setup(p, profile)]
    profiles.insert(0, profile)
    profiles = profiles[:MAX_PROFILES]
    try:
        _settings().setValue(
            SETTINGS_KEY, json.dumps([asdict(p) for p in profiles]))
    except (TypeError, ValueError):
        _itk_log.exception("Could not store the import setup")
    return profiles


def clear_profiles() -> None:
    """Forget every remembered setup."""
    _settings().remove(SETTINGS_KEY)


def _same_setup(left: ImportProfile, right: ImportProfile) -> bool:
    """Return True when two setups would do the same thing.

    Args:
        left (ImportProfile): First setup.
        right (ImportProfile): Second setup.
    """
    return (left.header_row == right.header_row
            and left.params == right.params
            and left.removed_columns == right.removed_columns
            and [(m.get('column'), m.get('isotope', {}).get('label'))
                 for m in left.mappings]
            == [(m.get('column'), m.get('isotope', {}).get('label'))
                for m in right.mappings])
