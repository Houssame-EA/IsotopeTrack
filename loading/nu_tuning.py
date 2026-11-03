"""Reader for the instrument tuning snapshot written by Nu Instruments software.

Every Nu run folder holds a ``Snapshot.tuning`` XML file listing the value of
every instrument register at acquisition time: plasma and gas flows, cell gas,
and all lens, extraction, quadrupole, time-of-flight and detector voltages.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

_itk_log = logging.getLogger("IsotopeTrack.loading.nu_tuning")

TUNING_FILE = "Snapshot.tuning"


def read_nu_tuning(folder_path):
    """Read the tuning registers of a Nu run folder.

    Args:
        folder_path (str | Path | None): Nu run folder.

    Returns:
        dict | None: Register name -> value (float when numeric, else str), or
        None when the folder has no readable tuning file.
    """
    if not folder_path:
        return None
    path = Path(folder_path) / TUNING_FILE
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        _itk_log.exception("Could not read tuning file %s", path)
        return None
    registers = {}
    for element in root.iter('Register'):
        name = element.get('AliasOrName')
        value = element.get('Value')
        if not name:
            continue
        try:
            registers[name] = float(value)
        except (TypeError, ValueError):
            registers[name] = value
    return registers or None
