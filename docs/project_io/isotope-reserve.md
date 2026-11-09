# `isotope_reserve.py`

Reserve of unselected isotopes stored inside an IsotopeTrack project file.

Every mass channel of a sample that is not part of the current isotope
selection is written to ``reserve/<sample>/<mass>.npy`` inside the ``.itproj``
zip, one compressed entry per channel. The selected isotopes keep living in
``arrays/`` exactly as before, so opening a project costs nothing extra; a
reserve channel is only read when the user asks for it.

When a project is saved, each sample's reserve is taken from the project file
that is currently open (when it already holds a reserve for the same sample
and data source), otherwise from the original raw data, otherwise the sample
is saved without a reserve.

---

## Constants

| Name | Value |
|------|-------|
| `RESERVE_DIR` | `'reserve'` |
| `RESERVE_COMPRESSION` | `zipfile.ZIP_DEFLATED` |
| `RESERVE_COMPRESSLEVEL` | `6` |
| `MAX_MASS_DIFF` | `0.5` |
| `SOURCE_PROJECT` | `'project'` |
| `SOURCE_RAW` | `'raw'` |
| `SOURCE_NONE` | `'none'` |
| `SOURCE_SESSION` | `'session'` |

## Classes

### `ReserveSource`

Read access to the reserve stored in an existing project file.

Opened on the project that is currently loaded, so a save can carry its
reserve forward without touching the raw data.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, project_path)` | Open the project archive and read its reserve index. |
| `masses_for` | `(self, sample_name, folder_path)` | Return the reserve masses usable for a sample, or an empty list. |
| `read_payload` | `(self, sample_name, mass)` | Return the ``.npy`` bytes of one stored channel. |
| `read_entry` | `(self, name)` | Return the bytes of any entry of the open project. |
| `close` | `(self)` | Close the underlying archive. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `safe_sample_name` | `(sample_name)` | Return the sample name with path separators replaced, as used in zip entries. |
| `entry_name` | `(sample_name, mass)` | Return the zip entry path of one reserve channel. |
| `_array_to_npy_bytes` | `(arr)` | Serialize an array to ``.npy`` bytes. |
| `_npy_bytes_to_array` | `(data)` | Deserialize ``.npy`` bytes. |
| `_write_channel` | `(zf, sample_name, mass, payload)` | Write one reserve channel entry, compressed. |
| `closest_channel_indices` | `(channel_masses, target_masses, max_diff=MAX_MASS_DIFF)` | Return the indices of the channels the target masses resolve to. |
| `raw_source_kind` | `(folder_path)` | Return the raw data format of a sample source, or None when unusable. |
| `iter_raw_channels` | `(folder_path)` | Yield every mass channel of a Nu or TOFWERK acquisition. |
| `write_sample_reserve` | `(zf, sample_name, selected_masses, folder_path, source, kept=None)` | Write the reserve of one sample into a project archive being saved. |
| `_write_stored_reserve` | `(zf, sample_name, selected_masses, folder_path, source)` | Write the reserve kept in the open project, or else read from the raw data. |
| `read_reserve_channel` | `(project_path, sample_name, mass)` | Read one channel back from a project's reserve. |
| `match_reserve_masses` | `(reserve_masses, target_masses, max_diff=MAX_MASS_DIFF)` | Map each target isotope mass to its closest reserve channel. |
| `read_reserve_channels` | `(project_path, sample_name, masses)` | Read several channels of one sample from a project's reserve. |
