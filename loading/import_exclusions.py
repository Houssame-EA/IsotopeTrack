"""Keep/remove state for the file-import dialog, with undo, redo and scope.

The user decides which columns and rows of each file actually reach the import.
Every change is recorded as a labelled snapshot, so any removal can be stepped
back with undo and reapplied with redo, and each change can be scoped either to
the file on screen or to every file in the batch.

Snapshots are whole-state copies rather than diffs. The state is a handful of
string and integer sets per file, so a full copy costs microseconds, and the
approach cannot drift out of sync with the live state the way an inverse-command
stack can.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

_itk_log = logging.getLogger("IsotopeTrack.loading.import_exclusions")

MAX_HISTORY = 150

SCOPE_FILE = "file"
SCOPE_ALL = "all"


@dataclass
class FileExclusions:
    """Columns and rows the user has removed from a single file."""

    columns: set[str] = field(default_factory=set)
    rows: set[int] = field(default_factory=set)

    def is_empty(self) -> bool:
        """Return True when nothing has been removed from this file."""
        return not self.columns and not self.rows

    def copy(self) -> "FileExclusions":
        """Return an independent copy of this file's removals."""
        return FileExclusions(columns=set(self.columns), rows=set(self.rows))


class ExclusionManager(QObject):
    """Tracks removed columns and rows per file with snapshot undo and redo.

    Signals:
        changed: Emitted whenever the effective removal state changes.
        historyChanged: Emitted whenever undo or redo availability changes.
    """

    changed = Signal()
    historyChanged = Signal()

    def __init__(self, file_count: int, parent=None):
        """Create an empty state for ``file_count`` files.

        Args:
            file_count (int): Number of files in the import batch.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._file_count = max(0, int(file_count))
        self._state: dict[int, FileExclusions] = {
            i: FileExclusions() for i in range(self._file_count)
        }
        self._undo: list[tuple[str, dict[int, FileExclusions]]] = []
        self._redo: list[tuple[str, dict[int, FileExclusions]]] = []
        self._batch_depth = 0
        self._batch_label = ""

    def begin_batch(self, label: str) -> None:
        """Group the changes that follow into a single undo step.

        Removing a mixed selection of columns and rows is one action to the
        user, so it should be one entry in the history rather than two.

        Args:
            label (str): Description of the whole batch.
        """
        if self._batch_depth == 0:
            self._batch_label = label
            self._push(label)
        self._batch_depth += 1

    def end_batch(self) -> None:
        """Close the current undo group and notify listeners once."""
        if self._batch_depth == 0:
            return
        self._batch_depth -= 1
        if self._batch_depth == 0:
            self._batch_label = ""
            self._emit()

    def file_count(self) -> int:
        """Return how many files this manager tracks."""
        return self._file_count

    def exclusions_for(self, file_index: int) -> FileExclusions:
        """Return the live removal state for one file.

        Args:
            file_index (int): Position of the file in the batch.

        Returns:
            FileExclusions: The live state object, created on first access.
        """
        if file_index not in self._state:
            self._state[file_index] = FileExclusions()
        return self._state[file_index]

    def excluded_columns(self, file_index: int) -> set[str]:
        """Return the removed column names for one file.

        Args:
            file_index (int): Position of the file in the batch.
        """
        return set(self.exclusions_for(file_index).columns)

    def excluded_rows(self, file_index: int) -> set[int]:
        """Return the removed row numbers for one file.

        Args:
            file_index (int): Position of the file in the batch.
        """
        return set(self.exclusions_for(file_index).rows)

    def is_column_excluded(self, file_index: int, name: str) -> bool:
        """Return True when a column has been removed from one file.

        Args:
            file_index (int): Position of the file in the batch.
            name (str): Column name to test.
        """
        return name in self.exclusions_for(file_index).columns

    def is_row_excluded(self, file_index: int, row: int) -> bool:
        """Return True when a row has been removed from one file.

        Args:
            file_index (int): Position of the file in the batch.
            row (int): Zero-based row number to test.
        """
        return row in self.exclusions_for(file_index).rows

    def has_any(self) -> bool:
        """Return True when anything anywhere has been removed."""
        return any(not e.is_empty() for e in self._state.values())

    def summary(self, file_index: int) -> str:
        """Return a short human-readable description of one file's removals.

        Args:
            file_index (int): Position of the file in the batch.

        Returns:
            str: Text such as ``"2 columns, 15 rows removed"``.
        """
        state = self.exclusions_for(file_index)
        if state.is_empty():
            return "Nothing removed"
        parts = []
        if state.columns:
            parts.append(f"{len(state.columns)} column"
                         f"{'s' if len(state.columns) != 1 else ''}")
        if state.rows:
            parts.append(f"{len(state.rows)} row"
                         f"{'s' if len(state.rows) != 1 else ''}")
        return f"{', '.join(parts)} removed"

    def set_columns_removed(self, file_index: int, names, removed: bool,
                            scope: str = SCOPE_FILE,
                            label: str | None = None) -> None:
        """Remove or restore columns, recording one undo step.

        Args:
            file_index (int): File the change originated from.
            names: Iterable of column names to change.
            removed (bool): True to remove, False to restore.
            scope (str): ``SCOPE_FILE`` for this file only, ``SCOPE_ALL`` for all.
            label (str | None): Override for the undo-history label.
        """
        names = {str(n) for n in names}
        if not names:
            return
        targets = self._targets(file_index, scope)
        verb = "Remove" if removed else "Restore"
        noun = next(iter(names)) if len(names) == 1 else f"{len(names)} columns"
        default = f"{verb} {noun}" + (" (all files)" if scope == SCOPE_ALL else "")
        self._push(label or default)
        for index in targets:
            state = self.exclusions_for(index)
            if removed:
                state.columns |= names
            else:
                state.columns -= names
        self._emit()

    def set_rows_removed(self, file_index: int, rows, removed: bool,
                         scope: str = SCOPE_FILE,
                         label: str | None = None) -> None:
        """Remove or restore rows, recording one undo step.

        Args:
            file_index (int): File the change originated from.
            rows: Iterable of zero-based row numbers to change.
            removed (bool): True to remove, False to restore.
            scope (str): ``SCOPE_FILE`` for this file only, ``SCOPE_ALL`` for all.
            label (str | None): Override for the undo-history label.
        """
        rows = {int(r) for r in rows}
        if not rows:
            return
        targets = self._targets(file_index, scope)
        verb = "Remove" if removed else "Restore"
        noun = (f"row {next(iter(rows)) + 1}" if len(rows) == 1
                else f"{len(rows)} rows")
        default = f"{verb} {noun}" + (" (all files)" if scope == SCOPE_ALL else "")
        self._push(label or default)
        for index in targets:
            state = self.exclusions_for(index)
            if removed:
                state.rows |= rows
            else:
                state.rows -= rows
        self._emit()

    def keep_only_columns(self, file_index: int, keep, all_columns,
                          scope: str = SCOPE_FILE) -> None:
        """Remove every column except those in ``keep``.

        Args:
            file_index (int): File the change originated from.
            keep: Iterable of column names to retain.
            all_columns: Iterable of every column name in the file.
            scope (str): ``SCOPE_FILE`` for this file only, ``SCOPE_ALL`` for all.
        """
        keep = {str(n) for n in keep}
        drop = {str(c) for c in all_columns} - keep
        if not drop:
            return
        self.set_columns_removed(
            file_index, drop, True, scope,
            label=f"Keep only {len(keep)} column{'s' if len(keep) != 1 else ''}")

    def restore_all(self, file_index: int | None = None) -> None:
        """Restore everything, either for one file or for the whole batch.

        Args:
            file_index (int | None): File to restore, or None for every file.
        """
        if file_index is None:
            if not self.has_any():
                return
            self._push("Restore everything")
            for state in self._state.values():
                state.columns.clear()
                state.rows.clear()
        else:
            if self.exclusions_for(file_index).is_empty():
                return
            self._push("Restore this file")
            state = self.exclusions_for(file_index)
            state.columns.clear()
            state.rows.clear()
        self._emit()

    def copy_to_all(self, file_index: int) -> None:
        """Apply one file's removals to every other file in the batch.

        Args:
            file_index (int): File whose removals become the template.
        """
        source = self.exclusions_for(file_index)
        self._push("Apply removals to all files")
        for index in range(self._file_count):
            if index == file_index:
                continue
            self._state[index] = source.copy()
        self._emit()

    def can_undo(self) -> bool:
        """Return True when there is a change to step back."""
        return bool(self._undo)

    def can_redo(self) -> bool:
        """Return True when there is a stepped-back change to reapply."""
        return bool(self._redo)

    def undo_label(self) -> str:
        """Return the description of the change undo would reverse."""
        return self._undo[-1][0] if self._undo else ""

    def redo_label(self) -> str:
        """Return the description of the change redo would reapply."""
        return self._redo[-1][0] if self._redo else ""

    def undo(self) -> str:
        """Step back one change.

        Returns:
            str: The label of the reversed change, or an empty string if the
                history was already empty.
        """
        if not self._undo:
            return ""
        label, snapshot = self._undo.pop()
        self._redo.append((label, self._snapshot()))
        self._state = snapshot
        self._emit()
        return label

    def redo(self) -> str:
        """Reapply the most recently undone change.

        Returns:
            str: The label of the reapplied change, or an empty string if there
                was nothing to redo.
        """
        if not self._redo:
            return ""
        label, snapshot = self._redo.pop()
        self._undo.append((label, self._snapshot()))
        self._state = snapshot
        self._emit()
        return label

    def _targets(self, file_index: int, scope: str) -> list[int]:
        """Return the file indices a scoped change applies to.

        Args:
            file_index (int): File the change originated from.
            scope (str): ``SCOPE_FILE`` or ``SCOPE_ALL``.
        """
        if scope == SCOPE_ALL:
            return list(range(self._file_count)) or [file_index]
        return [file_index]

    def _snapshot(self) -> dict[int, FileExclusions]:
        """Return an independent copy of the entire removal state."""
        return {k: v.copy() for k, v in self._state.items()}

    def _push(self, label: str) -> None:
        """Record the current state on the undo stack and clear the redo stack.

        Inside a batch the snapshot is taken once, by ``begin_batch``, so the
        individual changes that follow do not each become their own step.

        Args:
            label (str): Human-readable description of the change about to happen.
        """
        if self._batch_depth > 0:
            return
        self._undo.append((label, self._snapshot()))
        if len(self._undo) > MAX_HISTORY:
            self._undo.pop(0)
        self._redo.clear()

    def _emit(self) -> None:
        """Notify listeners that the state and the history both moved.

        Emission is suppressed inside a batch so the UI repaints once when the
        batch closes rather than after every part of it.
        """
        if self._batch_depth > 0:
            return
        self.changed.emit()
        self.historyChanged.emit()


def apply_exclusions(frame, excluded_columns, excluded_rows):
    """Return ``frame`` with the removed columns and rows dropped.

    Row numbers are matched against positional row order, which is how the
    preview numbers them, so a removal made in the preview lands on the same
    physical row at import time.

    Args:
        frame: DataFrame loaded from the file.
        excluded_columns: Iterable of column names to drop.
        excluded_rows: Iterable of zero-based positional row numbers to drop.

    Returns:
        The filtered frame, or the original object if nothing was removed.
    """
    columns = {str(c) for c in (excluded_columns or set())}
    rows = {int(r) for r in (excluded_rows or set())}
    if not columns and not rows:
        return frame

    result = frame
    if columns:
        drop = [c for c in result.columns if str(c) in columns]
        if drop:
            result = result.drop(columns=drop)
    if rows:
        keep = [i for i in range(len(result)) if i not in rows]
        if len(keep) != len(result):
            result = result.iloc[keep]
    return result.reset_index(drop=True)
