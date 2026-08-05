"""This module contains classes to manage data related compounds."""
from dataclasses import dataclass


@dataclass
class Compound:
    """Data object containing compound data."""
    formula: str = ""
    density: float = 0.0
    material_id: str = ""
    mp_url: str = ""
    space_group: str = ""
    signature: str = ""
    display_text: str | None = None
