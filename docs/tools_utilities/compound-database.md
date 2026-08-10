# `compound_database.py`

This module manages the data loading and querying of compounds.

---

## Classes

### `_MFCol` *(extends `StrEnum`)*

Enum of the columns of the `CompoundDatabase`'s dataframe.

When more columns get added please change this `enum`.

### `CompoundDatabase`

Service that manages the loading and querying of compound data

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, analysed_elements: list[str] \| None=None)` | Args: |
| `init_with_analysed_elements` | `(self, analysed_elements: list[str] \| None=None)` | Initializes the queried dataframe (`self.df`) with the periodic |
| `_elements_as_compound_df` | `() → pd.DataFrame` | Returns a `DataFrame` with elements of the periodic table. |
| `auto_load_csv` | `(self) → bool` | Try to load CSV from standard locations, preferring trimmed/compressed versions. |
| `load_csv` | `(self, csv_path: str \| Path) → bool` | Loads the CSV and initializes with the analyzed elements. |
| `_row_to_compound` | `(row) → Compound` | Maps a row to a `Compound`. |
| `_dicts_to_compound` | `(dicts: list[dict]) → list[Compound]` | Maps multiples rows to compounds. |
| `__len__` | `(self)` |  |
| `search_compounds_by_formula` | `(self, formula: str, max_count: int=50) → list[Compound]` | Searches for the `max_count` (default 50) shortest compounds |
| `get_searchable_model` | `(self, base_formula: Optional[str]=None, parent: QObject \| Any=None) →` | Gives a searchable model for Qt Views. |
| `_mp_url_from_material_id` | `(material_id: str) → str` | Creates a url from the `material_id` |
| `total_row_count` | `(self) → int` | Total loaded row count without the periodic table elements |
| `row_count` | `(self) → int` | Total loaded row count with the periodic table but with only |
| `get_first_compound_by_formula` | `(self, formula: str) → Optional[Compound]` | Gives the first compound associated with the formula. |

### `CompoundDatabaseModel` *(extends `QAbstractListModel`)*

Adaptor between `CompoundService` and `QAbstractListModel`.

Note that It's not a direct adaptor because it has the added
functionality of further obligating the presence of elements
of the base formula.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, database: CompoundDatabase, base_formula: Optional[str]=None, p` |  |
| `rowCount` | `(self, /, parent=QModelIndex())` | Returns the amount of compounds from the last search. |
| `data` | `(self, index, /, role=DataColumn.DISPLAY_TEXT)` | Returns data based on the index row and the role. |
| `search` | `(self, text: str)` | Updates the model results with the passed `text` and base formula. |
| `get_first_compound` | `(self) → Optional[Compound]` | Returns the first `Compound` based on the last research. |
