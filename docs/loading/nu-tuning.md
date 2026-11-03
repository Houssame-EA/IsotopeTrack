# `nu_tuning.py`

Reader for the instrument tuning snapshot written by Nu Instruments software.

Every Nu run folder holds a ``Snapshot.tuning`` XML file listing the value of
every instrument register at acquisition time: plasma and gas flows, cell gas,
and all lens, extraction, quadrupole, time-of-flight and detector voltages.

---

## Constants

| Name | Value |
|------|-------|
| `TUNING_FILE` | `'Snapshot.tuning'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `read_nu_tuning` | `(folder_path)` | Read the tuning registers of a Nu run folder. |
