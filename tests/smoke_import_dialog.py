"""Headless smoke run for the file-import dialog.

Builds a small batch of CSV files, opens the dialog offscreen and drives the
new preview, keep/remove and file-list behaviour the way a user would, then
checks that the emitted import configuration carries the removals through.

Run with::

    QT_QPA_PLATFORM=offscreen python tests/smoke_import_dialog.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

from loading.import_csv_dialogs import FileStructureDialog
from loading.import_exclusions import SCOPE_FILE


def write_files(directory: pathlib.Path) -> list[str]:
    """Write three CSV files with a shared column layout.

    Each file opens with the metadata preamble real instrument exports carry,
    and the Notes column holds a word on every row. Both shapes used to reduce
    the preview to nothing.

    Args:
        directory (pathlib.Path): Folder to write into.

    Returns:
        list[str]: Paths of the files that were written.
    """
    paths = []
    for index in range(3):
        path = directory / f"sample_{index}.csv"
        frame = pd.DataFrame({
            "Time": np.arange(3000) * 0.001,
            "Ag107": np.random.default_rng(index).poisson(4, 3000),
            "Au197": np.random.default_rng(index + 9).poisson(2, 3000),
            "Notes": ["ok" for _ in range(3000)],
        })
        preamble = (
            f"C:\\runs\\2024_HDSP\\sample_{index}.d\n"
            "Intensity Vs Time,CPS\n"
            "Acquired      : 2024-09-18 using Batch HDSP\n"
        )
        path.write_text(preamble + frame.to_csv(index=False), encoding="utf-8")
        paths.append(str(path))
    return paths


def check(label: str, condition: bool) -> bool:
    """Print and record the outcome of one assertion.

    Args:
        label (str): Description of what was checked.
        condition (bool): Whether the check passed.

    Returns:
        bool: The condition, unchanged.
    """
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    return condition


def main() -> int:
    """Drive the dialog and report whether every check passed.

    Returns:
        int: Zero when every check passed, one otherwise.
    """
    app = QApplication.instance() or QApplication([])
    results = []

    with tempfile.TemporaryDirectory() as tmp:
        paths = write_files(pathlib.Path(tmp))
        dialog = FileStructureDialog(paths)
        model = dialog.preview_table.preview_model()
        opening_rows = model.rowCount()
        app.processEvents()

        print("Preview loading")
        results.append(check("model attached", model is not None))
        results.append(check("opens on a 20 row grid", opening_rows == 20))
        results.append(check("fills the viewport after opening",
                             model.rowCount() >= opening_rows))
        results.append(check("more rows available", model.canFetchMore() is True))
        results.append(check("grid pads to 20 columns", model.columnCount() == 20))
        results.append(check("four real columns", model.real_column_count() == 4))

        model.fetchMore()
        results.append(check("scrolling reveals more", model.rowCount() > 20))

        dialog._load_all_rows()
        results.append(check("load all reaches 3000 data rows",
                             model.data_row_count() == 3000))
        results.append(check("preamble stays visible above the header",
                             model.real_row_count() == 3004))
        results.append(check("source exhausted", model.is_exhausted() is True))

        print("Nothing is assigned until asked")
        results.append(check("no mappings on open",
                             not any(dialog._effective_mappings(i)
                                     for i in range(3))))
        results.append(check("import stays disabled",
                             not dialog.import_button.isEnabled()))

        print("Detect isotopes on demand")
        dialog._auto_detect_isotopes()
        mapped = {v['column_name'] for v in dialog._effective_mappings(0).values()}
        results.append(check("Ag107 and Au197 detected",
                             {"Ag107", "Au197"} == mapped))
        results.append(check("only the open file is touched",
                             not dialog._effective_mappings(1)))

        print("Column removal")
        dialog.exclusions.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        results.append(check("Notes removed",
                             dialog.exclusions.is_column_excluded(0, "Notes")))
        results.append(check("column still visible in preview",
                             model.real_column_count() == 4))
        results.append(check("other files untouched",
                             not dialog.exclusions.is_column_excluded(1, "Notes")))

        print("Row removal")
        dialog.exclusions.set_rows_removed(0, range(0, 25), True, SCOPE_FILE)
        results.append(check("25 rows removed",
                             len(dialog.exclusions.excluded_rows(0)) == 25))
        results.append(check("rows still visible in preview",
                             model.real_row_count() == 3004))

        print("Undo and redo")
        dialog.exclusions.undo()
        results.append(check("undo restores rows",
                             not dialog.exclusions.excluded_rows(0)))
        results.append(check("undo left the column removed",
                             dialog.exclusions.is_column_excluded(0, "Notes")))
        dialog.exclusions.redo()
        results.append(check("redo reapplies rows",
                             len(dialog.exclusions.excluded_rows(0)) == 25))
        dialog.exclusions.undo()
        dialog.exclusions.undo()
        results.append(check("second undo restores the column",
                             not dialog.exclusions.is_column_excluded(0, "Notes")))

        print("Removals stay on this file")
        dialog.exclusions.restore_all()
        dialog.exclusions.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        results.append(check("only the open file is cut",
                             dialog.exclusions.is_column_excluded(0, "Notes")
                             and not dialog.exclusions.is_column_excluded(1, "Notes")))
        results.append(check("no scope selector left",
                             not hasattr(dialog, "scope_combo")))

        print("Removing a mapped column suspends its mapping")
        dialog.exclusions.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        active = {v['column_name'] for v in dialog._effective_mappings(0).values()}
        results.append(check("mapping no longer active", "Ag107" not in active))
        results.append(check("mapping record kept for undo",
                             any(v['column_name'] == "Ag107"
                                 for v in dialog.column_mappings.values())))
        dialog.exclusions.undo()
        restored = {v['column_name'] for v in dialog._effective_mappings(0).values()}
        results.append(check("undo brings the mapping back", "Ag107" in restored))

        print("Selection-driven removal")
        dialog.exclusions.restore_all()
        from PySide6.QtCore import QItemSelectionModel
        dialog.preview_table.selectColumn(3)
        chooser = dialog.preview_table.selectionModel()
        for row in (10, 11, 12):
            chooser.select(dialog.preview_table.model().index(row, 0),
                           QItemSelectionModel.Select | QItemSelectionModel.Rows)
        columns, rows = dialog._selection_targets()
        results.append(check("column and rows selected together",
                             columns == {"Notes"} and rows == {10, 11, 12}))
        results.append(check("remove button enabled",
                             dialog.remove_button.isEnabled()))
        dialog._remove_selection()
        results.append(check("both kinds removed at once",
                             dialog.exclusions.excluded_columns(0) == {"Notes"}
                             and dialog.exclusions.excluded_rows(0) == {10, 11, 12}))
        results.append(check("mixed removal is one undo step",
                             dialog.exclusions.undo_label().startswith("Remove")))
        dialog.exclusions.undo()
        results.append(check("one undo reverses both",
                             not dialog.exclusions.excluded_columns(0)
                             and not dialog.exclusions.excluded_rows(0)))

        print("Header row")
        results.append(check("preview is raw", model.is_raw() is True))
        results.append(check("header found on line 4", model.header_row() == 3))
        results.append(check("names come from the header row",
                             model.columns[:2] == ["Time", "Ag107"]))
        dialog._set_header_row(4)
        results.append(check("header can be moved", model.header_row() == 4))
        results.append(check("moving relabels the columns",
                             model.columns[:2] != ["Time", "Ag107"]))
        dialog._reset_header_row()
        model = dialog.preview_table.preview_model()
        results.append(check("detection can be restored",
                             model.header_row() == 3))

        print("Row numbering reaches the importer")
        dialog.exclusions.restore_all()
        dialog.exclusions.set_rows_removed(0, [4, 5, 6], True, SCOPE_FILE)
        shifted = dialog._build_import_config()['files'][0]['excluded_rows']
        results.append(check("preview rows shift to data rows",
                             shifted == [0, 1, 2]))
        dialog.exclusions.restore_all()

        print("Live readouts")
        dialog.exclusions.set_rows_removed(0, range(4, 44), True, SCOPE_FILE)
        text = dialog._effective_label.text()
        results.append(check("effective row count updates",
                             "40 removed" in text))
        results.append(check("status line reports how it was parsed",
                             "comma-separated" in dialog._row_status_label.text()))
        dialog.exclusions.undo()

        print("File list")
        results.append(check("three rows", dialog.file_list.count() == 3))
        results.append(check("open file has a thumbnail",
                             bool(dialog.file_list.card(0).header)))
        dialog._load_all_thumbnails()
        results.append(check("every card has a thumbnail",
                             all(dialog.file_list.card(i).header
                                 for i in range(3))))
        results.append(check("starts on the first file",
                             dialog.file_list.current_index() == 0))
        dialog.file_list.set_current(2)
        results.append(check("switching moves the dialog",
                             dialog.current_file_index == 2))
        results.append(check("preview rebuilt for the new file",
                             dialog.preview_table.preview_model() is not model))

        print("Column windowing")
        results.append(check("narrow file shows all four columns",
                             model.real_column_count() == 4))
        results.append(check("no columns left to reveal",
                             model.can_fetch_more_columns() is False))

        print("Restore all")
        dialog.file_list.set_current(0)
        dialog.exclusions.restore_all()
        dialog.preview_table.selectColumn(3)
        results.append(check("remove enabled with a selection",
                             dialog.remove_button.isEnabled()))
        dialog._remove_selection()
        results.append(check("selection survives the removal",
                             dialog.remove_button.isEnabled() is False))
        results.append(check("restore offered once anything is removed",
                             dialog.restore_button.isEnabled()))
        dialog.exclusions.set_columns_removed(1, ["Notes"], True, SCOPE_FILE)
        dialog._restore_everything()
        results.append(check("restore clears every file",
                             not dialog.exclusions.has_any()))

        print("Trimmed controls")
        for gone in ("undo_button", "redo_button", "_keep_mapped_button",
                     "_restore_all_button", "_redetect_button",
                     "_remove_button"):
            results.append(check(f"{gone} removed", not hasattr(dialog, gone)))

        print("Apply to all files")
        dialog.file_list.set_current(0)
        dialog.exclusions.restore_all()
        from PySide6.QtCore import Qt
        from loading.import_csv_dialogs import ApplyTargetsDialog
        candidates = [(i, pathlib.Path(p).name)
                      for i, p in enumerate(paths) if i != 0]
        picker = ApplyTargetsDialog(candidates, "sample_0.csv")
        results.append(check("picker lists the other files",
                             picker.list.count() == 2))
        results.append(check("everything ticked to begin with",
                             picker.selected_indexes() == [1, 2]))
        results.append(check("apply counts the ticks",
                             picker.apply_button.text() == "Apply to 2 files"))
        picker._set_all(False)
        results.append(check("apply disabled with nothing ticked",
                             not picker.apply_button.isEnabled()))
        picker.list.item(1).setCheckState(Qt.Checked)
        results.append(check("unticking narrows the target",
                             picker.selected_indexes() == [2]))
        picker.deleteLater()

        dialog.exclusions.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        report = dialog._perform_apply_to_all(
            list(dialog._effective_mappings(0).values()), [1, 2])
        results.append(check("every other file updated", report["files"] == 2))
        results.append(check("identical names matched exactly",
                             report["exact"] == 4))
        results.append(check("removals travelled too",
                             dialog.exclusions.excluded_columns(2) == {"Notes"}))
        results.append(check("mappings applied to the others",
                             len(dialog._effective_mappings(2)) == 2))
        results.append(check("detection ran on the targets too",
                             "detected" in report))
        results.append(check("no file needs opening to be mapped",
                             all(dialog._effective_mappings(i) for i in range(3))))
        dialog.exclusions.restore_all()

        print("Parse detection")
        detected = dialog._detected_settings(0)
        results.append(check("separator detected", detected["delimiter"] == ","))
        results.append(check("encoding detected",
                             detected["encoding"].startswith("utf-8")))
        results.append(check("no settings panel left",
                             not hasattr(dialog, "delimiter_combo")))
        results.append(check("preamble skipped", detected["skip_rows"] == 3))
        results.append(check("real columns found",
                             model.columns[:2] == ["Time", "Ag107"]))

        print("Mappings survive a file switch")
        dialog.file_list.set_current(0)
        preserved = {v['column_name'] for v in dialog.column_mappings.values()
                     if v['file_index'] == 0}
        results.append(check("mappings still present after returning",
                             {"Ag107", "Au197"} <= preserved))

        print("Settings reload keeps mappings")
        dialog._do_reload()
        after_reload = {v['column_name'] for v in dialog.column_mappings.values()
                        if v['file_index'] == 0}
        results.append(check("mappings survive a reload",
                             {"Ag107", "Au197"} <= after_reload))

        print("Parameters follow the sample")
        dialog.file_list.set_current(0)
        app.processEvents()
        dialog.time_column_combo.setCurrentIndex(1)
        dialog.calc_dwell_radio.setChecked(True)
        app.processEvents()
        results.append(check("calculated dwell is shown",
                             abs(dialog.dwell_time_spin.value() - 1.0) < 1e-6))
        results.append(check("dwell box is read-only while calculating",
                             not dialog.dwell_time_spin.isEnabled()))
        results.append(check("tooltip names where it came from",
                             "Read from" in dialog.dwell_time_spin.toolTip()))
        dialog.data_type_combo.setCurrentIndex(1)

        dialog.file_list.set_current(1)
        app.processEvents()
        results.append(check("a fresh sample starts on its own defaults",
                             dialog.time_column_combo.currentIndex() == 0
                             and dialog.data_type_combo.currentIndex() == 0))
        dialog.file_list.set_current(0)
        app.processEvents()
        results.append(check("returning restores that sample's settings",
                             dialog.calc_dwell_radio.isChecked()
                             and dialog.data_type_combo.currentIndex() == 1))
        results.append(check("and its calculated dwell",
                             abs(dialog.dwell_time_spin.value() - 1.0) < 1e-6))

        print("Import configuration")
        dialog.file_list.set_current(0)
        dialog.exclusions.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        config = dialog._build_import_config()
        first = config['files'][0]
        results.append(check("exclusions reach the config",
                             "Notes" in first['excluded_columns']))
        results.append(check("every file is described",
                             len(config['files']) == 3))
        results.append(check("settings carry the parse options",
                             config['settings']['delimiter'] == ","))
        results.append(check("each file carries its own time settings",
                             all('dwell_time_ms' in f for f in config['files'])))
        results.append(check("the calculated dwell reaches the config",
                             abs(config['files'][0]['dwell_time_ms'] - 1.0) < 1e-6))
        results.append(check("each file carries its own parse options",
                             all('delimiter' in f for f in config['files'])))

        print("Worker applies the exclusions")
        from loading.import_csv_dialogs import DataProcessThread
        worker = DataProcessThread(config)
        frame = worker._load_delimited(first['path'], config['settings'])
        from loading.import_exclusions import apply_exclusions
        filtered = apply_exclusions(frame, first['excluded_columns'],
                                    first['excluded_rows'])
        results.append(check("Notes dropped at import",
                             "Notes" not in filtered.columns))
        results.append(check("signal columns kept",
                             "Ag107" in filtered.columns))

        dialog.close()
        dialog.deleteLater()

    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
