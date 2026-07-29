from dataclasses import dataclass


@dataclass
class Compound:
    formula: str = ""
    density: float = 0.0
    material_id: str = ""
    mp_url: str = ""
    space_group: str = ""
    signature: str = ""
    display_text: str | None = None
