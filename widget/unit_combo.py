"""A combo box of data types that shows them in the app's chosen units.

The items keep their saved names (``"Element Mass (fg)"``) for the code and
the project files, while the user sees ``"Element Mass (pg)"`` when the mass
unit is pg. Choosing other units relabels the items at once.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from utils.unit import units

KEY_ROLE = Qt.ItemDataRole.UserRole + 41
"""Item role holding the saved name of each data type."""


class UnitComboBox(QComboBox):
    """Combo box whose texts follow the app's units and whose API uses the saved names.

    ``currentText``, ``setCurrentText``, ``findText`` and ``itemText`` all
    work with the saved names, so code written for a plain ``QComboBox`` of
    data types keeps working unchanged.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        units.unitsChanged.connect(self._relabel)
        self.destroyed.connect(lambda *_: _disconnect(self._relabel))

    def _key(self, index):
        key = self.itemData(index, KEY_ROLE)
        return key if key is not None else super().itemText(index)

    def _relabel(self, *_):
        """Show every item in the newly chosen units, keeping the choice."""
        try:
            blocked = self.blockSignals(True)
            for i in range(self.count()):
                super().setItemText(i, units.relabel(self._key(i)))
            self.blockSignals(blocked)
        except RuntimeError:
            _disconnect(self._relabel)

    def addItem(self, *args):
        """Add one data type; the text may be preceded by an icon, as for ``QComboBox``."""
        args = list(args)
        pos = 1 if args and not isinstance(args[0], str) else 0
        key = args[pos]
        args[pos] = units.relabel(key)
        super().addItem(*args)
        self.setItemData(self.count() - 1, key, KEY_ROLE)

    def addItems(self, texts):
        """Add several data types."""
        for t in texts:
            self.addItem(t)

    def insertItem(self, index, *args):
        """Insert one data type at *index*."""
        args = list(args)
        pos = 1 if args and not isinstance(args[0], str) else 0
        key = args[pos]
        args[pos] = units.relabel(key)
        super().insertItem(index, *args)
        self.setItemData(index, key, KEY_ROLE)

    def itemText(self, index):
        """The saved name of the item at *index*."""
        return self._key(index)

    def setItemText(self, index, text):
        """Rename the item at *index*; *text* is a saved name."""
        super().setItemText(index, units.relabel(text))
        self.setItemData(index, text, KEY_ROLE)

    def currentText(self):
        """The saved name of the chosen data type."""
        i = self.currentIndex()
        return self._key(i) if i >= 0 else super().currentText()

    def findText(self, text, flags=Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchCaseSensitive):
        """Index of the item whose saved name (or shown text) is *text*, or -1."""
        for i in range(self.count()):
            if self._key(i) == text:
                return i
        return super().findText(text, flags)

    def setCurrentText(self, text):
        """Choose the item whose saved name (or shown text) is *text*."""
        i = self.findText(text)
        if i >= 0:
            self.setCurrentIndex(i)
        else:
            super().setCurrentText(text)


def _disconnect(slot):
    try:
        units.unitsChanged.disconnect(slot)
    except (RuntimeError, TypeError):
        pass
