"""Tests for the lazy import preview and the keep/remove state.

These cover the parts of the import dialog that decide what data reaches the
application: how many rows the preview pulls and when, where a trailing text
footer stops the read, and whether a removal can be undone and redone without
the state drifting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from loading.csv.preview_model import (
    INITIAL_VISIBLE_COLUMNS, INITIAL_VISIBLE_ROWS, MIN_GRID_COLUMNS,
    MIN_GRID_ROWS, DelimitedRowSource,
    ExcelRowSource, LazyPreviewModel,
    build_row_source, describe_delimiter, detect_delimiter, detect_encoding,
    file_type_of, find_first_stopping_row, format_cell, read_columns_only,
    detect_layout, detect_table_width, sniff_delimited_settings,
)
from loading.csv.exclusions import (
    SCOPE_ALL, SCOPE_FILE, ExclusionManager, apply_exclusions,
)


@pytest.fixture(scope="session")
def qapp():
    """Return a process-wide offscreen QApplication for the Qt-backed tests."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def numeric_csv(tmp_path):
    """Write a 500-row numeric CSV and return its path."""
    path = tmp_path / "signal.csv"
    frame = pd.DataFrame({
        "Time": np.arange(500) * 0.001,
        "Ag107": np.arange(500, dtype=float),
        "Au197": np.arange(500, dtype=float) * 2,
    })
    frame.to_csv(path, index=False)
    return path


@pytest.fixture
def footer_csv(tmp_path):
    """Write a CSV whose data stops at row 40 with a trailing text footer."""
    path = tmp_path / "with_footer.csv"
    lines = ["Time,Ag107"]
    lines += [f"{i * 0.001},{i}" for i in range(40)]
    lines += ["End of acquisition,", "Operator notes,here"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TestFileTypeOf:
    """Extension classification used to pick a reader."""

    @pytest.mark.parametrize("name,expected", [
        ("a.csv", "delimited"),
        ("a.CSV", "delimited"),
        ("a.txt", "delimited"),
        ("a.xlsx", "excel"),
        ("a.XLSM", "excel"),
        ("a.h5", "unknown"),
        ("a", "unknown"),
    ])
    def test_classifies_extensions(self, name, expected):
        """Each supported extension maps to its reader family."""
        assert file_type_of(name) == expected


class TestFindFirstStoppingRow:
    """Detection of the row where usable data ends."""

    def test_all_numeric_frame_has_no_stop(self):
        """A fully numeric frame is consumed to the end."""
        frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        assert find_first_stopping_row(frame) == len(frame)

    def test_empty_frame_stops_at_zero(self):
        """An empty frame reports a stop at row zero."""
        assert find_first_stopping_row(pd.DataFrame()) == 0

    def test_stops_at_footer_row(self):
        """A row whose measurement columns hold no number ends the data."""
        frame = pd.DataFrame({"a": [1.0, 2.0, np.nan], "b": ["", "", "footer"]})
        assert find_first_stopping_row(frame) == 2

    def test_stops_at_blank_row(self):
        """A wholly empty row marks the end of the data."""
        frame = pd.DataFrame({"a": [1.0, np.nan], "b": [2.0, np.nan]})
        assert find_first_stopping_row(frame) == 1

    def test_keeps_rows_that_have_a_text_column(self):
        """A genuine label column must not be mistaken for a footer.

        This is the case that previously truncated such a file to zero rows:
        every row held a word, so the very first row looked like a footer.
        """
        frame = pd.DataFrame({
            "Time": [0.0, 0.1, 0.2],
            "Ag107": [4, 5, 6],
            "Notes": ["ok", "ok", "spike"],
        })
        assert find_first_stopping_row(frame) == 3

    def test_stops_after_a_text_column_file(self):
        """A footer still ends the data even when a label column exists."""
        frame = pd.DataFrame({
            "Time": [0.0, 0.1, np.nan],
            "Ag107": [4.0, 5.0, np.nan],
            "Notes": ["ok", "ok", "End of acquisition"],
        })
        assert find_first_stopping_row(frame) == 2

    def test_handles_numeric_column_read_as_text(self):
        """A numeric column pandas read as text is still treated as data."""
        frame = pd.DataFrame({
            "Time": ["0.0", "0.1", "End"],
            "Ag107": ["4", "5", ""],
        })
        assert find_first_stopping_row(frame) == 2

    def test_all_text_frame_runs_to_the_end(self):
        """With no measurement columns, only a blank row ends the data."""
        frame = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
        assert find_first_stopping_row(frame) == 2


class TestFormatCell:
    """Display formatting for preview cells."""

    @pytest.mark.parametrize("value,expected", [
        (None, ""),
        (float("nan"), ""),
        (3.0, "3"),
        (0.001, "0.001"),
        ("text", "text"),
    ])
    def test_formats_values(self, value, expected):
        """Values render without float representation noise."""
        assert format_cell(value) == expected


class TestDelimitedRowSource:
    """Chunked reading of delimited files."""

    def test_reads_columns_without_data(self, numeric_csv):
        """Column names are available before any row is fetched."""
        source = DelimitedRowSource(numeric_csv)
        assert source.columns == ["Time", "Ag107", "Au197"]
        source.close()

    def test_fetch_returns_requested_row_count(self, numeric_csv):
        """A fetch hands back exactly the number of rows asked for."""
        source = DelimitedRowSource(numeric_csv)
        assert len(source.fetch(20)) == 20
        assert len(source.fetch(30)) == 30
        source.close()

    def test_fetches_do_not_overlap(self, numeric_csv):
        """Successive fetches continue where the previous one stopped."""
        source = DelimitedRowSource(numeric_csv)
        first = source.fetch(10)
        second = source.fetch(10)
        assert list(first["Ag107"]) == list(range(10))
        assert list(second["Ag107"]) == list(range(10, 20))
        source.close()

    def test_exhausts_at_end_of_file(self, numeric_csv):
        """The source reports exhaustion once every row has been served."""
        source = DelimitedRowSource(numeric_csv)
        total = 0
        while not source.is_exhausted():
            total += len(source.fetch(200))
        assert total == 500
        assert source.fetch(10).empty
        source.close()

    def test_stops_at_footer(self, footer_csv):
        """Trailing text ends the read and is reported."""
        source = DelimitedRowSource(footer_csv)
        frame = source.fetch(1000)
        assert len(frame) == 40
        assert source.is_exhausted()
        assert source.truncated_at() == 40
        source.close()

    def test_honours_skip_rows(self, tmp_path):
        """Leading junk rows are discarded before the header."""
        path = tmp_path / "skip.csv"
        path.write_text("junk line\nanother\nTime,Ag107\n0.1,5\n0.2,6\n",
                        encoding="utf-8")
        source = DelimitedRowSource(path, skip_rows=2)
        assert source.columns == ["Time", "Ag107"]
        assert len(source.fetch(10)) == 2
        source.close()

    def test_strips_byte_order_mark(self, tmp_path):
        """A UTF-8 BOM does not corrupt the first column name."""
        path = tmp_path / "bom.csv"
        path.write_text("Time,Ag107\n0.1,5\n", encoding="utf-8-sig")
        source = DelimitedRowSource(path, encoding="utf-8")
        assert source.columns[0] == "Time"
        source.close()

    def test_handles_semicolon_delimiter(self, tmp_path):
        """A non-comma separator is honoured."""
        path = tmp_path / "semi.csv"
        path.write_text("Time;Ag107\n0,1;5\n", encoding="utf-8")
        source = DelimitedRowSource(path, delimiter=";")
        assert source.columns == ["Time", "Ag107"]
        source.close()

    def test_accepts_escaped_tab(self, tmp_path):
        """The literal two-character tab token from the UI is translated."""
        path = tmp_path / "tabbed.txt"
        path.write_text("Time\tAg107\n0.1\t5\n", encoding="utf-8")
        source = DelimitedRowSource(path, delimiter="\\t")
        assert source.columns == ["Time", "Ag107"]
        source.close()


class TestExcelRowSource:
    """Chunked reading of Excel workbooks."""

    @pytest.fixture
    def workbook(self, tmp_path):
        """Write a small two-sheet workbook and return its path."""
        path = tmp_path / "book.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"Time": [0.1, 0.2, 0.3], "Ag107": [1, 2, 3]}).to_excel(
                writer, sheet_name="Data", index=False)
            pd.DataFrame({"Other": [9]}).to_excel(
                writer, sheet_name="Notes", index=False)
        return path

    def test_reads_first_sheet(self, workbook):
        """The default sheet is read with its header."""
        source = ExcelRowSource(workbook)
        assert source.columns == ["Time", "Ag107"]
        assert len(source.fetch(10)) == 3
        source.close()

    def test_reads_second_sheet(self, workbook):
        """A sheet index other than zero selects that sheet."""
        source = ExcelRowSource(workbook, sheet_index=1)
        assert source.columns == ["Other"]
        source.close()


class TestBuildRowSource:
    """Reader selection from import settings."""

    def test_builds_delimited_source(self, numeric_csv):
        """A CSV path yields a delimited reader."""
        source = build_row_source(numeric_csv, {"delimiter": ",",
                                                "encoding": "utf-8"})
        assert isinstance(source, DelimitedRowSource)
        source.close()

    def test_rejects_unknown_extension(self, tmp_path):
        """An unsupported extension raises rather than guessing."""
        path = tmp_path / "data.h5"
        path.write_bytes(b"\x00")
        with pytest.raises(ValueError):
            build_row_source(path, {})

    def test_read_columns_only_returns_names(self, numeric_csv):
        """Column names come back without loading data rows."""
        assert read_columns_only(numeric_csv, {}) == ["Time", "Ag107", "Au197"]

    def test_read_columns_only_survives_bad_path(self, tmp_path):
        """An unreadable file yields an empty list instead of raising."""
        assert read_columns_only(tmp_path / "missing.csv", {}) == []


class TestLazyPreviewModel:
    """Progressive row loading behind the preview table."""

    def test_starts_with_initial_window(self, qapp, numeric_csv):
        """The model exposes a small first window rather than the whole file."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.real_row_count() == INITIAL_VISIBLE_ROWS
        assert model.real_column_count() == 3
        model.close()

    def test_can_fetch_more_before_exhaustion(self, qapp, numeric_csv):
        """More rows are advertised while the file has data left."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.canFetchMore() is True
        model.close()

    def test_fetch_more_reveals_further_rows(self, qapp, numeric_csv):
        """Fetching grows the visible row count."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        before = model.rowCount()
        model.fetchMore()
        assert model.rowCount() > before
        model.close()

    def test_scrolling_reaches_the_end_of_the_file(self, qapp, numeric_csv):
        """Repeated fetching reveals every row and then stops."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        guard = 0
        while model.canFetchMore() and guard < 100:
            model.fetchMore()
            guard += 1
        assert model.rowCount() == 500
        assert model.is_exhausted() is True
        model.close()

    def test_load_all_reads_everything_at_once(self, qapp, numeric_csv):
        """Loading all rows skips the incremental steps."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.load_all() == 500
        model.close()

    def test_reports_footer_truncation(self, qapp, footer_csv):
        """The row where trailing text began is reported to the caller."""
        model = LazyPreviewModel(build_row_source(footer_csv, {}))
        model.load_all()
        assert model.rowCount() == 40
        assert model.truncated_at() == 40
        model.close()

    def test_display_values_match_the_file(self, qapp, numeric_csv):
        """Cells render the underlying values."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.data(model.index(0, 1), Qt.DisplayRole) == "0"
        assert model.data(model.index(3, 1), Qt.DisplayRole) == "3"
        model.close()

    def test_headers_use_file_column_names(self, qapp, numeric_csv):
        """Horizontal headers show the file's own column names."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Ag107"
        model.close()

    def test_removed_cells_are_struck_through(self, qapp, numeric_csv):
        """A removed column renders with a strikeout font instead of vanishing."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        model.set_excluded_columns({1})
        font = model.data(model.index(0, 1), Qt.FontRole)
        assert font is not None and font.strikeOut() is True
        assert model.real_column_count() == 3
        model.close()

    def test_removed_rows_are_struck_through(self, qapp, numeric_csv):
        """A removed row renders with a strikeout font."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        model.set_excluded_rows({2})
        font = model.data(model.index(2, 0), Qt.FontRole)
        assert font is not None and font.strikeOut() is True
        model.close()


class TestExclusionManager:
    """Keep/remove state, scope and history."""

    def test_starts_empty(self):
        """Nothing is removed before the user acts."""
        manager = ExclusionManager(3)
        assert manager.has_any() is False
        assert manager.excluded_columns(0) == set()

    def test_removes_a_column_for_one_file(self):
        """A file-scoped removal leaves the other files untouched."""
        manager = ExclusionManager(3)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        assert manager.is_column_excluded(0, "Ag107") is True
        assert manager.is_column_excluded(1, "Ag107") is False

    def test_removes_a_column_for_all_files(self):
        """An all-files removal reaches every file in the batch."""
        manager = ExclusionManager(3)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_ALL)
        assert all(manager.is_column_excluded(i, "Ag107") for i in range(3))

    def test_restores_a_column(self):
        """Restoring clears the removal."""
        manager = ExclusionManager(2)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        manager.set_columns_removed(0, ["Ag107"], False, SCOPE_FILE)
        assert manager.is_column_excluded(0, "Ag107") is False

    def test_removes_rows(self):
        """Row removals are tracked per file."""
        manager = ExclusionManager(2)
        manager.set_rows_removed(0, [3, 4, 5], True, SCOPE_FILE)
        assert manager.excluded_rows(0) == {3, 4, 5}
        assert manager.is_row_excluded(0, 4) is True

    def test_keep_only_columns_removes_the_rest(self):
        """Keeping a subset removes everything else."""
        manager = ExclusionManager(1)
        manager.keep_only_columns(0, ["Time", "Ag107"],
                                  ["Time", "Ag107", "Au197", "Pt195"])
        assert manager.excluded_columns(0) == {"Au197", "Pt195"}

    def test_undo_reverses_a_removal(self):
        """Undo puts a removed column back."""
        manager = ExclusionManager(2)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        assert manager.can_undo() is True
        manager.undo()
        assert manager.is_column_excluded(0, "Ag107") is False

    def test_redo_reapplies_a_removal(self):
        """Redo reapplies what undo reversed."""
        manager = ExclusionManager(2)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        manager.undo()
        assert manager.can_redo() is True
        manager.redo()
        assert manager.is_column_excluded(0, "Ag107") is True

    def test_undo_walks_back_several_steps(self):
        """Each removal is its own history entry."""
        manager = ExclusionManager(1)
        manager.set_columns_removed(0, ["a"], True, SCOPE_FILE)
        manager.set_columns_removed(0, ["b"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [1], True, SCOPE_FILE)
        manager.undo()
        manager.undo()
        assert manager.excluded_columns(0) == {"a"}
        assert manager.excluded_rows(0) == set()

    def test_new_change_clears_the_redo_stack(self):
        """A fresh change after an undo discards the redo branch."""
        manager = ExclusionManager(1)
        manager.set_columns_removed(0, ["a"], True, SCOPE_FILE)
        manager.undo()
        manager.set_columns_removed(0, ["b"], True, SCOPE_FILE)
        assert manager.can_redo() is False

    def test_undo_on_empty_history_is_safe(self):
        """Undo with no history returns an empty label and changes nothing."""
        manager = ExclusionManager(1)
        assert manager.undo() == ""
        assert manager.has_any() is False

    def test_history_labels_describe_the_change(self):
        """The undo label names what would be reversed."""
        manager = ExclusionManager(1)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_FILE)
        assert "Ag107" in manager.undo_label()

    def test_undo_after_all_files_scope_restores_every_file(self):
        """Undo of an all-files change reverses it everywhere."""
        manager = ExclusionManager(3)
        manager.set_columns_removed(0, ["Ag107"], True, SCOPE_ALL)
        manager.undo()
        assert not any(manager.is_column_excluded(i, "Ag107") for i in range(3))

    def test_restore_all_clears_every_file(self):
        """Restoring everything empties the whole batch in one step."""
        manager = ExclusionManager(2)
        manager.set_columns_removed(0, ["a"], True, SCOPE_ALL)
        manager.set_rows_removed(1, [2], True, SCOPE_FILE)
        manager.restore_all()
        assert manager.has_any() is False

    def test_copy_to_all_mirrors_one_file(self):
        """One file's removals can be pushed onto the rest."""
        manager = ExclusionManager(3)
        manager.set_columns_removed(0, ["a"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [7], True, SCOPE_FILE)
        manager.copy_to_all(0)
        assert manager.excluded_columns(2) == {"a"}
        assert manager.excluded_rows(2) == {7}

    def test_summary_describes_the_state(self):
        """The summary counts both kinds of removal."""
        manager = ExclusionManager(1)
        assert manager.summary(0) == "Nothing removed"
        manager.set_columns_removed(0, ["a", "b"], True, SCOPE_FILE)
        assert "2 columns" in manager.summary(0)

    def test_batch_is_one_undo_step(self):
        """Removing columns and rows together undoes as a single action."""
        manager = ExclusionManager(1)
        manager.begin_batch("Remove 1 column and 3 rows")
        manager.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [4, 5, 6], True, SCOPE_FILE)
        manager.end_batch()

        assert manager.excluded_columns(0) == {"Notes"}
        assert manager.excluded_rows(0) == {4, 5, 6}
        manager.undo()
        assert manager.excluded_columns(0) == set()
        assert manager.excluded_rows(0) == set()

    def test_batch_emits_once(self, qapp):
        """A batch notifies listeners a single time, when it closes."""
        manager = ExclusionManager(1)
        seen = []
        manager.changed.connect(lambda: seen.append(1))
        manager.begin_batch("mixed")
        manager.set_columns_removed(0, ["a"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [1], True, SCOPE_FILE)
        assert seen == []
        manager.end_batch()
        assert len(seen) == 1

    def test_batch_label_names_the_whole_action(self):
        """The history entry describes the batch, not its last part."""
        manager = ExclusionManager(1)
        manager.begin_batch("Remove 1 column and 3 rows")
        manager.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [4, 5, 6], True, SCOPE_FILE)
        manager.end_batch()
        assert manager.undo_label() == "Remove 1 column and 3 rows"


class TestApplyExclusions:
    """Translation of removal state into an actual filtered frame."""

    @pytest.fixture
    def frame(self):
        """Return a small frame with three columns and five rows."""
        return pd.DataFrame({
            "Time": [0, 1, 2, 3, 4],
            "Ag107": [10, 11, 12, 13, 14],
            "Au197": [20, 21, 22, 23, 24],
        })

    def test_no_removals_returns_the_frame(self, frame):
        """An empty removal set leaves the frame alone."""
        assert apply_exclusions(frame, set(), set()) is frame

    def test_drops_columns(self, frame):
        """Removed columns are gone from the result."""
        result = apply_exclusions(frame, {"Ag107"}, set())
        assert list(result.columns) == ["Time", "Au197"]

    def test_drops_rows_by_position(self, frame):
        """Removed rows are matched positionally, as the preview numbers them."""
        result = apply_exclusions(frame, set(), {0, 2})
        assert list(result["Time"]) == [1, 3, 4]

    def test_drops_rows_and_columns_together(self, frame):
        """Both kinds of removal apply in one pass."""
        result = apply_exclusions(frame, {"Au197"}, {4})
        assert list(result.columns) == ["Time", "Ag107"]
        assert len(result) == 4

    def test_ignores_unknown_column_names(self, frame):
        """A stale column name does not raise."""
        result = apply_exclusions(frame, {"NotHere"}, set())
        assert list(result.columns) == list(frame.columns)

    def test_result_index_is_reset(self, frame):
        """The filtered frame is positionally indexed for downstream code."""
        result = apply_exclusions(frame, set(), {0, 1})
        assert list(result.index) == [0, 1, 2]


class TestParseDetection:
    """Working out how a delimited file is put together without asking."""

    @pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
    def test_detects_each_separator(self, tmp_path, sep):
        """Each supported separator is recognised from the file's own lines."""
        path = tmp_path / "probe.csv"
        rows = ["Time", "Ag107", "Au197"]
        lines = [sep.join(rows)]
        lines += [sep.join(["0.1", "5", "6"]) for _ in range(8)]
        path.write_text("\n".join(lines), encoding="utf-8")
        assert detect_delimiter(path, "utf-8") == sep

    def test_prefers_the_consistent_separator(self, tmp_path):
        """A comma inside quoted text does not outrank the real separator."""
        path = tmp_path / "quoted.csv"
        lines = ["Time;Ag107;Label"]
        lines += [f'0.{i};{i};"a, b, c, d"' for i in range(8)]
        path.write_text("\n".join(lines), encoding="utf-8")
        assert detect_delimiter(path, "utf-8") == ";"

    def test_detects_byte_order_mark(self, tmp_path):
        """A UTF-8 BOM selects the signature-aware encoding."""
        path = tmp_path / "bom.csv"
        path.write_text("Time,Ag107\n0.1,5\n", encoding="utf-8-sig")
        assert detect_encoding(path) == "utf-8-sig"

    def test_detects_utf16(self, tmp_path):
        """A UTF-16 file is recognised from its byte-order mark."""
        path = tmp_path / "wide.csv"
        path.write_text("Time,Ag107\n0.1,5\n", encoding="utf-16")
        assert detect_encoding(path) == "utf-16"

    def test_falls_back_for_undecodable_bytes(self, tmp_path):
        """An encoding is always returned, even for awkward bytes."""
        path = tmp_path / "raw.csv"
        path.write_bytes(b"Time,Ag107\n0.1,\xff\xfe\x00abc\n")
        assert detect_encoding(path) in ("utf-8-sig", "cp1252", "latin-1",
                                         "utf-16")

    def test_missing_file_is_safe(self, tmp_path):
        """Detection on an absent file returns defaults rather than raising."""
        settings = sniff_delimited_settings(tmp_path / "gone.csv")
        assert settings["delimiter"] == ","

    def test_sniff_returns_both_settings(self, tmp_path):
        """Sniffing reports the separator and the encoding together."""
        path = tmp_path / "semi.csv"
        lines = ["Time;Ag107"] + [f"0.{i};5" for i in range(6)]
        path.write_text("\n".join(lines), encoding="utf-8")
        settings = sniff_delimited_settings(path)
        assert settings["delimiter"] == ";"
        assert settings["encoding"].startswith("utf-8")

    def test_sniffed_settings_drive_the_reader(self, tmp_path):
        """A semicolon file parses into real columns without being told."""
        path = tmp_path / "auto.csv"
        lines = ["Time;Ag107;Au197"] + [f"0.{i};5;6" for i in range(6)]
        path.write_text("\n".join(lines), encoding="utf-8")
        source = build_row_source(path, sniff_delimited_settings(path))
        assert source.columns == ["Time", "Ag107", "Au197"]
        source.close()

    @pytest.mark.parametrize("sep,name", [
        (",", "comma"), (";", "semicolon"), ("\t", "tab"), ("|", "pipe"),
    ])
    def test_describes_separators_in_words(self, sep, name):
        """Separators are reported to the user by name, not by symbol."""
        assert describe_delimiter(sep) == name


@pytest.fixture
def wide_csv(tmp_path):
    """Write a 60-column CSV and return its path."""
    path = tmp_path / "wide.csv"
    data = {"Time": np.arange(50) * 0.001}
    for index in range(59):
        data[f"m{index}"] = np.arange(50)
    pd.DataFrame(data).to_csv(path, index=False)
    return path


class TestColumnWindowing:
    """Progressive column reveal for wide instrument exports."""

    def test_opens_on_a_column_window(self, qapp, wide_csv):
        """A wide file starts with only its first block of columns shown."""
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        assert model.real_column_count() == INITIAL_VISIBLE_COLUMNS
        assert model.total_column_count() == 60
        model.close()

    def test_narrow_file_shows_every_column(self, qapp, numeric_csv):
        """A file narrower than the window is fully visible from the start."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.real_column_count() == 3
        assert model.can_fetch_more_columns() is False
        model.close()

    def test_fetching_reveals_the_next_block(self, qapp, wide_csv):
        """Scrolling right exposes further columns."""
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        assert model.fetch_more_columns() is True
        assert model.real_column_count() == 40
        model.close()

    def test_fetching_stops_at_the_last_column(self, qapp, wide_csv):
        """Reveal never runs past the number of columns the file has."""
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        guard = 0
        while model.can_fetch_more_columns() and guard < 20:
            model.fetch_more_columns()
            guard += 1
        assert model.real_column_count() == 60
        assert model.fetch_more_columns() is False
        model.close()

    def test_reveal_all_columns_in_one_step(self, qapp, wide_csv):
        """Every column can be exposed at once when the user asks."""
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        assert model.reveal_all_columns() == 60
        model.close()

    def test_headers_follow_the_window(self, qapp, wide_csv):
        """A hidden column reports no header until it is revealed."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        assert model.headerData(25, Qt.Horizontal, Qt.DisplayRole) == ""
        model.fetch_more_columns()
        assert model.headerData(25, Qt.Horizontal, Qt.DisplayRole) == "m24"
        model.close()

    def test_column_positions_stay_stable(self, qapp, wide_csv):
        """Revealing columns does not renumber the ones already shown."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        before = model.headerData(5, Qt.Horizontal, Qt.DisplayRole)
        model.fetch_more_columns()
        assert model.headerData(5, Qt.Horizontal, Qt.DisplayRole) == before
        model.close()

    def test_exclusions_survive_a_reveal(self, qapp, wide_csv):
        """A column removed before a reveal stays removed afterwards."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(wide_csv, {}))
        model.set_excluded_columns({3})
        model.fetch_more_columns()
        font = model.data(model.index(0, 3), Qt.FontRole)
        assert font is not None and font.strikeOut() is True
        model.close()


@pytest.fixture
def instrument_export(tmp_path):
    """Write a CSV shaped like a real instrument export.

    Three metadata lines and a blank one precede the header, and a printed-on
    footer follows the data, which is what these files look like in practice.
    """
    path = tmp_path / "Sample1_9.csv"
    lines = [
        r"C:\Users\Mary-Luyza\2024_HDSP\2024-09-18\Sample1_9.d",
        "Intensity Vs Time,CPS",
        "Acquired      : 2024-09-18 14:22:31 using Batch HDSP",
        "",
        "Time [Sec],Ag107,Au197,Pt195",
    ]
    lines += [f"{i * 0.001},{i % 7},{i % 5},{i % 3}" for i in range(300)]
    lines += ["", "Printed: 2024-09-18"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TestHeaderDetection:
    """Finding the header row under a block of export metadata."""

    def test_finds_the_header_under_metadata(self, instrument_export):
        """The header is located past the preamble, not on line one."""
        delimiter, skip = detect_layout(instrument_export, "utf-8")
        assert delimiter == ","
        assert skip == 3

    def test_plain_file_needs_no_skip(self, numeric_csv):
        """A file that starts with its header is not skipped into."""
        assert detect_layout(numeric_csv, "utf-8") == (",", 0)

    def test_reads_the_real_columns(self, instrument_export):
        """Reading with the detected settings yields the instrument's columns.

        Before header detection this file produced one column named after the
        acquisition path, and zero rows.
        """
        settings = sniff_delimited_settings(instrument_export)
        source = build_row_source(instrument_export, settings)
        assert source.columns == ["Time [Sec]", "Ag107", "Au197", "Pt195"]
        source.close()

    def test_reads_the_real_rows(self, instrument_export):
        """The data rows survive both the preamble and the footer."""
        settings = sniff_delimited_settings(instrument_export)
        model = LazyPreviewModel(build_row_source(instrument_export, settings))
        assert model.load_all() == 300
        model.close()

    def test_detects_semicolon_under_metadata(self, tmp_path):
        """Separator and header are found together, not one before the other."""
        path = tmp_path / "euro.csv"
        lines = ["Instrument report", "Operator;Mary", "Time;Ag107;Au197"]
        lines += [f"0.{i};4;5" for i in range(30)]
        path.write_text("\n".join(lines), encoding="utf-8")
        assert detect_layout(path, "utf-8") == (";", 2)

    def test_prefers_the_longest_run(self, tmp_path):
        """A short two-field preamble does not outrank the real table."""
        path = tmp_path / "tricky.csv"
        lines = ["Batch,2024-09-18", "Operator,Mary"]
        lines += ["Time,Ag107,Au197"] + [f"0.{i},4,5" for i in range(40)]
        path.write_text("\n".join(lines), encoding="utf-8")
        assert detect_layout(path, "utf-8") == (",", 2)

    def test_skip_rows_can_be_overridden(self, instrument_export):
        """An explicit skip wins over the detected one."""
        settings = sniff_delimited_settings(instrument_export, skip_rows=4)
        assert settings["skip_rows"] == 4

    def test_unreadable_file_returns_defaults(self, tmp_path):
        """Detection on a missing file falls back rather than raising."""
        assert detect_layout(tmp_path / "gone.csv", "utf-8") == (",", 0)


class TestRawPreview:
    """Showing the file line for line and choosing the header row."""

    def _model(self, path):
        """Return a raw-mode model over one file.

        Args:
            path: File to preview.

        Returns:
            LazyPreviewModel: A model showing every physical line.
        """
        settings = sniff_delimited_settings(path)
        source = build_row_source(path, settings, raw=True)
        return LazyPreviewModel(source, header_row=settings["skip_rows"])

    def test_preamble_is_visible(self, qapp, instrument_export):
        """The metadata lines are shown rather than skipped away."""
        from PySide6.QtCore import Qt
        model = self._model(instrument_export)
        first = model.data(model.index(0, 0), Qt.DisplayRole)
        assert "Sample1_9.d" in first
        model.close()

    def test_header_row_is_marked(self, qapp, instrument_export):
        """The detected header row is reported and rendered in bold."""
        from PySide6.QtCore import Qt
        model = self._model(instrument_export)
        assert model.header_row() == 3
        font = model.data(model.index(3, 0), Qt.FontRole)
        assert font is not None and font.bold() is True
        model.close()

    def test_rows_above_the_header_are_dimmed(self, qapp, instrument_export):
        """Lines that will not be imported are visibly greyed."""
        from PySide6.QtCore import Qt
        model = self._model(instrument_export)
        assert model.data(model.index(0, 0), Qt.ForegroundRole) is not None
        assert model.data(model.index(10, 0), Qt.ForegroundRole) is None
        model.close()

    def test_column_names_come_from_the_header_row(self, qapp, instrument_export):
        """Headers read from the chosen row, not from line one."""
        model = self._model(instrument_export)
        assert model.columns == ["Time [Sec]", "Ag107", "Au197", "Pt195"]
        model.close()

    def test_moving_the_header_relabels_columns(self, qapp, instrument_export):
        """Choosing another row renames the columns without a re-read."""
        model = self._model(instrument_export)
        assert model.set_header_row(1) is True
        assert model.columns[0] == "Intensity Vs Time"
        model.close()

    def test_moving_to_the_same_row_is_a_no_op(self, qapp, instrument_export):
        """Re-choosing the current header reports no change."""
        model = self._model(instrument_export)
        assert model.set_header_row(3) is False
        model.close()

    def test_data_row_count_excludes_the_preamble(self, qapp, instrument_export):
        """Only rows below the header count as data."""
        model = self._model(instrument_export)
        model.load_all()
        assert model.data_row_count() == 300
        assert model.real_row_count() == 304
        model.close()

    def test_data_row_count_follows_the_header(self, qapp, instrument_export):
        """Moving the header down leaves fewer data rows."""
        model = self._model(instrument_export)
        model.load_all()
        model.set_header_row(5)
        assert model.data_row_count() == 298
        model.close()

    def test_preview_rows_map_to_data_rows(self, qapp, instrument_export):
        """Preview numbering converts to importer numbering."""
        model = self._model(instrument_export)
        assert model.to_data_row(4) == 0
        assert model.to_data_row(9) == 5
        model.close()

    def test_row_labels_mark_the_sections(self, qapp, instrument_export):
        """The row gutter distinguishes preamble, header and data."""
        from PySide6.QtCore import Qt
        model = self._model(instrument_export)
        assert model.headerData(0, Qt.Vertical, Qt.DisplayRole) == "\u00b7"
        assert model.headerData(3, Qt.Vertical, Qt.DisplayRole) == "\u25b8"
        assert model.headerData(4, Qt.Vertical, Qt.DisplayRole) == "1"
        model.close()

    def test_footer_still_ends_the_data(self, qapp, instrument_export):
        """Raw mode does not disable footer trimming, it only delays the scan."""
        model = self._model(instrument_export)
        model.load_all()
        assert model.data_row_count() == 300
        model.close()

    def test_blank_labels_fall_back_to_positions(self, qapp, tmp_path):
        """A header cell with no text still yields a usable column name."""
        path = tmp_path / "gap.csv"
        path.write_text("Time,,Au197\n0.1,5,6\n0.2,7,8\n", encoding="utf-8")
        model = self._model(path)
        assert model.columns[1] == "Column 2"
        model.close()

    def test_non_raw_model_reports_no_header_row(self, qapp, numeric_csv):
        """A model built the ordinary way is not in raw mode."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        assert model.is_raw() is False
        assert model.header_row() is None
        assert model.set_header_row(2) is False
        model.close()


class TestRestoreAndScope:
    """Restoring removals, on its own and across files."""

    def test_restore_reverses_a_removal(self):
        """A removed column comes back when restored."""
        manager = ExclusionManager(2)
        manager.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        manager.set_columns_removed(0, ["Notes"], False, SCOPE_FILE)
        assert manager.excluded_columns(0) == set()

    def test_restore_only_touches_what_was_asked(self):
        """Restoring one column leaves the others removed."""
        manager = ExclusionManager(1)
        manager.set_columns_removed(0, ["a", "b"], True, SCOPE_FILE)
        manager.set_columns_removed(0, ["a"], False, SCOPE_FILE)
        assert manager.excluded_columns(0) == {"b"}

    def test_restore_across_all_files(self):
        """An all-files restore clears the column everywhere."""
        manager = ExclusionManager(3)
        manager.set_columns_removed(0, ["Notes"], True, SCOPE_ALL)
        manager.set_columns_removed(0, ["Notes"], False, SCOPE_ALL)
        assert not any(manager.is_column_excluded(i, "Notes") for i in range(3))

    def test_restore_mixed_selection_in_one_step(self):
        """Columns and rows restore together as a single history entry."""
        manager = ExclusionManager(1)
        manager.begin_batch("remove")
        manager.set_columns_removed(0, ["Notes"], True, SCOPE_FILE)
        manager.set_rows_removed(0, [1, 2], True, SCOPE_FILE)
        manager.end_batch()

        manager.begin_batch("restore")
        manager.set_columns_removed(0, ["Notes"], False, SCOPE_FILE)
        manager.set_rows_removed(0, [1, 2], False, SCOPE_FILE)
        manager.end_batch()

        assert manager.has_any() is False
        manager.undo()
        assert manager.excluded_columns(0) == {"Notes"}
        assert manager.excluded_rows(0) == {1, 2}


class TestGridPadding:
    """The grid keeps a full shape even for a small file."""

    @pytest.fixture
    def tiny_csv(self, tmp_path):
        """Write a three-column, four-row CSV and return its path."""
        path = tmp_path / "tiny.csv"
        path.write_text(
            "Time,Ag107,Au197\n0.1,5,6\n0.2,7,8\n0.3,9,1\n0.4,2,3\n",
            encoding="utf-8")
        return path

    def test_short_file_still_fills_the_grid(self, qapp, tiny_csv):
        """A four-row file draws the full grid rather than four stripes."""
        model = LazyPreviewModel(build_row_source(tiny_csv, {}))
        assert model.rowCount() == MIN_GRID_ROWS
        assert model.columnCount() == MIN_GRID_COLUMNS
        model.close()

    def test_real_counts_report_the_file(self, qapp, tiny_csv):
        """The padding does not disturb what the file actually holds."""
        model = LazyPreviewModel(build_row_source(tiny_csv, {}))
        assert model.real_row_count() == 4
        assert model.real_column_count() == 3
        model.close()

    def test_padded_cells_are_blank(self, qapp, tiny_csv):
        """Cells past the data carry no text."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(tiny_csv, {}))
        assert model.data(model.index(15, 10), Qt.DisplayRole) is None
        model.close()

    def test_padded_headers_are_blank(self, qapp, tiny_csv):
        """Column and row headers past the data show nothing."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(tiny_csv, {}))
        assert model.headerData(10, Qt.Horizontal, Qt.DisplayRole) == ""
        assert model.headerData(15, Qt.Vertical, Qt.DisplayRole) == ""
        model.close()

    def test_padded_cells_cannot_be_selected(self, qapp, tiny_csv):
        """Empty grid cells are not selectable, so they cannot be removed."""
        from PySide6.QtCore import Qt
        model = LazyPreviewModel(build_row_source(tiny_csv, {}))
        assert not (model.flags(model.index(15, 10)) & Qt.ItemIsSelectable)
        assert model.flags(model.index(1, 1)) & Qt.ItemIsSelectable
        model.close()

    def test_a_large_file_is_not_clipped(self, qapp, numeric_csv):
        """Padding is a floor, never a ceiling."""
        model = LazyPreviewModel(build_row_source(numeric_csv, {}))
        model.load_all()
        assert model.rowCount() == 500
        model.close()


@pytest.fixture
def padded_export(tmp_path):
    """Write a CSV shaped like a real Agilent time-resolved export.

    Every line is padded to five fields with trailing separators, including
    the metadata block, and the file ends with blank lines and a printed-on
    stamp. Line endings are CRLF, as the instrument writes them.
    """
    path = tmp_path / "Sample1_1.csv"
    lines = [
        r"D:\Agilent\ICPMH\1\DATA\Mary\2024_HDSP\CHDS1.b\Sample1.d,,,,",
        "Intensity Vs Time,Counts,,,",
        "Acquired      : 2024-09-18 1:39:01 PM using Batch CHDS1.b,,,,",
        "Time [Sec],Ti48 -> 64,,,",
    ]
    lines += [f"{0.02112 + i * 0.0001:.5f},{300 + i}.06,,," for i in range(400)]
    lines += [",,,,", ",,,,", "          Printed:2024-09-18 1:44:58 PM,,,,"]
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return path


class TestPaddedExport:
    """A file whose every line is padded to the same width.

    Counting fields cannot find the header in these, because the metadata rows
    are padded to the width of the table. This shape reduced the preview to one
    column named after the acquisition path and no rows at all.
    """

    def test_header_is_found_despite_the_padding(self, padded_export):
        """The header is the line above where the numbers start."""
        delimiter, skip = detect_layout(padded_export, "utf-8-sig")
        assert delimiter == ","
        assert skip == 3

    def test_padding_columns_are_trimmed(self, padded_export):
        """Columns empty from top to bottom are not shown as data."""
        width, full = detect_table_width(padded_export, "utf-8-sig", ",")
        assert (width, full) == (2, 5)

    def test_settings_carry_both_widths(self, padded_export):
        """Parsing needs the full width; display needs the trimmed one."""
        settings = sniff_delimited_settings(padded_export)
        assert settings["width"] == 2
        assert settings["full_width"] == 5
        assert settings["skip_rows"] == 3

    def test_reads_the_instrument_columns(self, padded_export):
        """The real column names come through, not the acquisition path."""
        settings = sniff_delimited_settings(padded_export)
        source = build_row_source(padded_export, settings)
        assert source.columns == ["Time [Sec]", "Ti48 -> 64"]
        source.close()

    def test_reads_every_data_row(self, padded_export):
        """All readings load, and the printed-on footer is left behind."""
        settings = sniff_delimited_settings(padded_export)
        model = LazyPreviewModel(build_row_source(padded_export, settings))
        assert model.load_all() == 400
        model.close()

    def test_raw_preview_keeps_the_preamble_visible(self, qapp, padded_export):
        """The metadata lines stay on screen above the marked header row."""
        from PySide6.QtCore import Qt
        settings = sniff_delimited_settings(padded_export)
        source = build_row_source(padded_export, settings, raw=True)
        model = LazyPreviewModel(source, header_row=settings["skip_rows"])
        assert "Sample1.d" in model.data(model.index(0, 0), Qt.DisplayRole)
        assert model.header_row() == 3
        assert model.columns == ["Time [Sec]", "Ti48 -> 64"]
        model.close()

    def test_crlf_does_not_reach_the_values(self, padded_export):
        """Carriage returns are stripped rather than parsed into a column."""
        settings = sniff_delimited_settings(padded_export)
        source = build_row_source(padded_export, settings)
        frame = source.fetch(3)
        assert "\r" not in str(frame.iloc[0, 1])
        source.close()


class TestNothingIsSilentlyDropped:
    """Guards on the two places sampling could lose data."""

    def test_a_named_column_is_never_trimmed(self, tmp_path):
        """A column the header names survives even if it is empty for a while.

        Trimming looks at the sampled lines, and the header is one of them, so
        a named column can never be mistaken for the writer's padding.
        """
        path = tmp_path / "sparse.csv"
        lines = ["Time,Ag107,LateCol"]
        for i in range(400):
            late = "" if i < 300 else str(i)
            lines.append(f"{i * 0.001},{i % 9},{late}")
        path.write_text("\n".join(lines), encoding="utf-8")
        assert detect_table_width(path, "utf-8-sig", ",") == (3, 3)

    def test_a_column_with_late_values_is_never_trimmed(self, tmp_path):
        """An unnamed column holding values further down is still kept."""
        path = tmp_path / "stray.csv"
        lines = ["Time,Ag107,,"]
        for i in range(400):
            stray = "stray" if i == 250 else ""
            lines.append(f"{i * 0.001},{i % 9},,{stray}")
        path.write_text("\n".join(lines), encoding="utf-8")
        width, _ = detect_table_width(path, "utf-8-sig", ",")
        assert width == 4

    def test_a_long_preamble_is_still_found(self, tmp_path):
        """A preamble longer than the first sample does not defeat detection."""
        path = tmp_path / "long.csv"
        lines = [f"metadata line {i},,," for i in range(150)]
        lines.append("Time,Ag107,,")
        lines += [f"{i * 0.001},{i % 9},," for i in range(200)]
        path.write_text("\n".join(lines), encoding="utf-8")
        assert sniff_delimited_settings(path)["skip_rows"] == 150

    def test_every_data_row_after_a_long_preamble_loads(self, qapp, tmp_path):
        """Widening the scan finds the header without costing rows."""
        path = tmp_path / "long.csv"
        lines = [f"metadata line {i},,," for i in range(150)]
        lines.append("Time,Ag107,,")
        lines += [f"{i * 0.001},{i % 9},," for i in range(200)]
        path.write_text("\n".join(lines), encoding="utf-8")
        settings = sniff_delimited_settings(path)
        model = LazyPreviewModel(build_row_source(path, settings))
        assert model.load_all() == 200
        model.close()

    def test_loading_everything_matches_a_plain_read(self, qapp, numeric_csv):
        """The windowed reader returns the same values as one plain read.

        The preview windows what it shows; it must not window what it holds.
        """
        settings = sniff_delimited_settings(numeric_csv)
        model = LazyPreviewModel(build_row_source(numeric_csv, settings))
        model.load_all()
        plain = pd.read_csv(numeric_csv)
        assert model.loaded_row_count() == len(plain)
        assert np.allclose(model.frame()["Ag107"].to_numpy(),
                           plain["Ag107"].to_numpy())
