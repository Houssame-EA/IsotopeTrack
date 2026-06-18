import logging
from pathlib import Path

import pandas as pd

from tools.mass_fraction_calculator_utils.formula_utils import reduce_counts, parse_formula_to_counts, \
    signature_from_counts, canonicalize_preserve_user_order

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV compound database
# ---------------------------------------------------------------------------

class CSVCompoundDatabase:
    """Database loader for materials from CSV with signature-based lookup."""

    def __init__(self):
        self.data: pd.DataFrame | None = None
        self.formula_to_data: dict[str, list[dict]] = {}
        self.element_to_compounds: dict[str, dict[str, float]] = {}
        self.signature_to_formula: dict[str, str] = {}
        self.signature_to_data: dict[str, list[dict]] = {}
        self.is_loaded: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def auto_load_csv(self) -> bool:
        """Try to load CSV from standard locations, preferring trimmed/compressed versions.

        Handles both normal execution and PyInstaller frozen bundles
        (where data files live under sys._MEIPASS).
        """
        import sys

        base_dirs = []

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dirs.append(Path(sys._MEIPASS) / 'data')

        base_dirs.extend([
            Path(__file__).resolve().parent / 'data',
            Path(__file__).resolve().parent.parent / 'data',
            Path.cwd() / 'data',
        ])

        filenames = [
            'materials_trimmed.csv.gz',
        ]
        for base in base_dirs:
            for fname in filenames:
                p = base / fname
                if p.exists():
                    logger.info("Found CSV at %s", p)
                    return self.load_csv(p)
        logger.warning("No CSV file found in standard locations")
        return False

    def load_csv(self, csv_path: str | Path) -> bool:
        """Load CSV and build signature-based indices.

        Uses ``itertuples()`` for ~5-10× speed-up over ``iterrows()``.
        """
        if self.is_loaded:
            return True
        try:
            csv_path = Path(csv_path)
            logger.info("Loading CSV from %s", csv_path)
            self.data = pd.read_csv(csv_path)
            logger.info("CSV loaded with %d rows", len(self.data))

            self.formula_to_data.clear()
            self.element_to_compounds.clear()
            self.signature_to_formula.clear()
            self.signature_to_data.clear()

            for col in ('formula', 'density', 'material_id', 'mp_url', 'space_group'):
                if col not in self.data.columns:
                    self.data[col] = ''

            processed = 0

            for row in self.data.itertuples(index=False):
                try:
                    raw_formula = getattr(row, 'formula', '')
                    if not isinstance(raw_formula, str) or not raw_formula.strip():
                        continue
                    raw_formula = raw_formula.strip()

                    density_raw = getattr(row, 'density', None)
                    density = float(density_raw) if density_raw is not None and pd.notna(density_raw) else 0.0

                    mid_raw = getattr(row, 'material_id', '')
                    material_id = str(mid_raw).strip() if pd.notna(mid_raw) else ''

                    url_raw = getattr(row, 'mp_url', '')
                    mp_url = str(url_raw).strip() if pd.notna(url_raw) else ''
                    if not mp_url and material_id:
                        mp_url = f"https://materialsproject.org/materials/{material_id}"

                    sg_raw = getattr(row, 'space_group', '')
                    space_group = str(sg_raw) if pd.notna(sg_raw) else ''

                    material_data = {
                        'material_id': material_id,
                        'density': density,
                        'formula': raw_formula,
                        'space_group': space_group,
                        'mp_url': mp_url,
                    }

                    self.formula_to_data.setdefault(raw_formula, []).append(material_data)

                    counts = reduce_counts(parse_formula_to_counts(raw_formula))
                    if not counts:
                        continue
                    sig = signature_from_counts(counts)

                    self.signature_to_formula.setdefault(sig, raw_formula)
                    self.signature_to_data.setdefault(sig, []).append(material_data)

                    canon_display = self.signature_to_formula[sig]
                    for element in counts:
                        bucket = self.element_to_compounds.setdefault(element, {})
                        best = bucket.get(canon_display, 0.0)
                        bucket[canon_display] = density if density > 0 else best

                    processed += 1
                except Exception:
                    logger.debug("Skipping row during CSV indexing", exc_info=True)
                    continue

            self.is_loaded = True
            logger.info(
                "Database loaded: %d rows processed, %d canonical compounds indexed",
                processed, len(self.signature_to_formula),
            )
            return True

        except Exception:
            logger.exception("Error loading CSV")
            return False

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _signature_for_formula(self, formula: str) -> str:
        return signature_from_counts(reduce_counts(parse_formula_to_counts(formula)))

    def get_data_by_formula_or_signature(self, formula: str) -> list[dict]:
        return self.signature_to_data.get(self._signature_for_formula(formula), [])

    def best_density_for_formula(self, formula: str) -> float:
        for r in self.get_data_by_formula_or_signature(formula):
            if r.get('density', 0) > 0:
                return float(r['density'])
        return 0.0

    def best_url_for_formula(self, formula: str) -> str:
        for r in self.get_data_by_formula_or_signature(formula):
            url = (r.get('mp_url') or '').strip()
            if url:
                return url
        for r in self.get_data_by_formula_or_signature(formula):
            mid = (r.get('material_id') or '').strip()
            if mid:
                return f"https://materialsproject.org/materials/{mid}"
        canon = canonicalize_preserve_user_order(formula)
        return f"https://materialsproject.org/?search={canon}"

    def get_compounds_for_element(self, element: str) -> list[dict]:
        """Get one entry per canonical formula for initial browsing.

        For multi-polymorph formulas, this shows the first density found.
        Use get_variants_for_formula() to expand into all polymorphs.
        """
        if element not in self.element_to_compounds:
            return []
        compounds = []
        for display_formula, dens in self.element_to_compounds[element].items():
            sig = self._signature_for_formula(display_formula)
            n_variants = len(self.signature_to_data.get(sig, []))
            if dens > 0:
                display_text = f"{display_formula} ({dens:.3f} g/cm³)"
            else:
                display_text = display_formula
            if n_variants > 1:
                display_text += f"  [{n_variants} structures]"
            compounds.append({
                'formula': display_formula,
                'density': float(dens),
                'display_text': display_text,
            })
        compounds.sort(key=lambda x: x['formula'])
        return compounds

    def get_variants_for_formula(self, formula: str) -> list[dict]:
        """Get ALL polymorphs/structures for a given formula.

        Returns one entry per material_id, each with its own density,
        space group, and URL — so the user can pick the right polymorph.
        """
        sig = self._signature_for_formula(formula)
        rows = self.signature_to_data.get(sig, [])
        if not rows:
            return []

        canon = canonicalize_preserve_user_order(formula)
        variants = []
        seen_ids = set()

        for r in rows:
            mid = r.get('material_id', '')
            if mid in seen_ids:
                continue
            seen_ids.add(mid)

            dens = r.get('density', 0.0)
            sg = r.get('space_group', '')

            parts = [canon]
            if sg:
                parts.append(f"[{sg}]")
            if dens > 0:
                parts.append(f"({dens:.3f} g/cm³)")
            if mid:
                parts.append(f"— {mid}")

            variants.append({
                'formula': canon,
                'density': float(dens),
                'space_group': sg,
                'material_id': mid,
                'mp_url': r.get('mp_url', ''),
                'display_text': ' '.join(parts),
            })

        variants.sort(key=lambda x: (x['space_group'], -x['density']))
        return variants

    def get_material_data(self, formula: str) -> list[dict]:
        return self.formula_to_data.get(formula, [])
