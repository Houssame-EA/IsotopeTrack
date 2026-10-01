"""
This node enables the viewing of individual particle values as a tree/json
format.

TODO:
    Resizing of the window. Right now it's clanky.
TODO:
    Make it respect the single responsibility principle.
TODO:
    "Filters" the user should be able to :
    * Add and remove fields
    * Filter particles based on value
    * The filter should give number previews (similar to filter already there)
    * Filters should be saved as configs
TODO:
    Nice to have, particle matcher using start/end time with the sample to
    see how they change.
TODO: Export to JSON or CSV
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal, QAbstractItemModel, QObject, QPersistentModelIndex, QModelIndex, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QTreeView

DEFAULT_CONFIG = {}


class ParticleViewerNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, /, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.title = "Particle Viewer"
        self.node_type = "particle_viewer"
        self.position = None
        self._has_input = True
        self._has_output = True
        self.input_channels = ["input"]
        self.output_channels = ["output"]
        self.config = dict(DEFAULT_CONFIG)
        self.input_data = None

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = ParticleViewerDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_data(self) -> list:
        if not self.input_data:
            return []
        return self.input_data.get('particle_data', [])
    def get_output_data(self):
        return self.input_data


@dataclass
class ParticleModelRootItem:
    children: list[ParticleModelItem | ParticleModelLeafItem]

    def get_row_count(self):
        return len(self.children)


@dataclass
class ParticleModelItem:
    parent: ParticleModelItem | ParticleModelRootItem
    key: int
    user_key: Any
    children: list[ParticleModelItem | ParticleModelLeafItem]

    def get_row_count(self):
        return len(self.children)


@dataclass
class ParticleModelLeafItem:
    parent: ParticleModelItem | ParticleModelRootItem
    key: int
    user_key: Any
    value: Any

    def get_row_count(self):
        return 0


class ParticleModel(QAbstractItemModel):

    def __init__(self, /, particle_data: list, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.root_item: ParticleModelRootItem = ParticleModel._to_tree(particle_data)

    @staticmethod
    def _to_tree(particle_data: list):
        root = ParticleModelRootItem(
            children=[]
        )
        root.children = [ParticleModel._parse_list_level(data=data, key=i, user_key=i, parent=root)
                         for i, data in enumerate(particle_data)]
        return root

    @staticmethod
    def _parse_list_level(data, key, user_key, parent):
        if not isinstance(data, list | dict):
            return ParticleModelLeafItem(parent=parent, key=key, user_key=user_key, value=data)

        item = ParticleModelItem(parent=parent, key=key, user_key=user_key, children=[])

        if isinstance(data, list):
            item.children = [
                ParticleModel._parse_list_level(
                    data=child_data,
                    key=i,
                    user_key=i,
                    parent=item)
                for i, child_data in enumerate(data)
            ]
            return item
        else:
            item.children = [
                ParticleModel._parse_list_level(
                    data=child_key_val[1],
                    key=i,
                    user_key=child_key_val[0],
                    parent=item)
                for i, child_key_val in enumerate(data.items())
            ]
            return item

    def get_item(self,
                 index: QModelIndex | QPersistentModelIndex = QModelIndex()
                 ) -> ParticleModelRootItem | ParticleModelItem | ParticleModelLeafItem:
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.root_item

    def index(self,
              row: int,
              column: int,
              /,
              parent: QModelIndex | QPersistentModelIndex = QModelIndex()
              ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item: ParticleModelItem | ParticleModelRootItem | ParticleModelLeafItem = (
            self.get_item(parent)
        )

        if isinstance(parent_item, ParticleModelItem | ParticleModelRootItem):
            return self.createIndex(row, column, parent_item.children[row])
        if isinstance(parent_item, ParticleModelLeafItem):
            return self.createIndex(row, column, parent_item.value)

        return QModelIndex()

    def parent(self, index: QModelIndex = QModelIndex()) -> QAbstractItemModel:
        if not index.isValid():
            return QModelIndex()

        child_item = self.get_item(index)

        if isinstance(child_item, ParticleModelItem | ParticleModelLeafItem):
            parent_item = child_item.parent
            key = child_item.key
        else:
            parent_item = None
            key = None

        if parent_item == self.root_item or not parent_item:
            return QModelIndex()

        return self.createIndex(key or 0, 0, parent_item)

    def rowCount(self, /,
                 parent: QModelIndex | QPersistentModelIndex = QModelIndex()
                 ) -> int:
        if parent.isValid() and parent.column() > 0:
            return 0

        parent_item = self.get_item(parent)
        if isinstance(parent_item, ParticleModelLeafItem):
            return 0
        return len(parent_item.children)

    def columnCount(self, /,
                    parent: QModelIndex | QPersistentModelIndex = QModelIndex()
                    ) -> int:
        # Because of key values
        return 2

    def data(self,
             index: QModelIndex | QPersistentModelIndex, /,
             role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        particle_item = index.internalPointer()
        if isinstance(particle_item, ParticleModelLeafItem):
            match index.column():
                case 0:
                    return str(particle_item.user_key)
                case 1:
                    return str(particle_item.value)
        if isinstance(particle_item, ParticleModelItem):
            match index.column():
                case 0:
                    return str(particle_item.user_key)
                case 1:
                    return ""
                case _:
                    return None
        elif isinstance(particle_item, ParticleModelRootItem):
            match index.column():
                case 0:
                    return "Key"
                case 1:
                    return ""
                case _:
                    return None
        else:
            return None

    def flags(self,
              index: QModelIndex | QPersistentModelIndex,
              /) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | QAbstractItemModel.flags(self, index)

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation, /,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None

        match section:
            case 0:
                return "Key"
            case 1:
                return "Value"
            case _:
                return None

    def set_particle_data(self, particle_data: list):
        self.beginResetModel()
        self.root_item = self._to_tree(particle_data)
        self.endResetModel()


class ParticleViewerSettingsDialog(QDialog):
    preview_requested = Signal(dict)


class ParticleViewerDialog(QDialog):
    def __init__(self, /, node: ParticleViewerNode, parent: QWidget | Any = None):
        super().__init__(parent=parent)
        self.node = node
        self.setWindowTitle("Particle Data Viewer")

        self._initial_refresh_pending = True

        self.tree_view = QTreeView(parent=self)
        self.tree_model: ParticleModel = ParticleModel(self.node.extract_data(), parent=self.tree_view)
        self.tree_view.setModel(self.tree_model)

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def showEvent(self, event: QShowEvent, /) -> None:
        super().showEvent(event)
        if self._initial_refresh_pending:
            self._initial_refresh_pending = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.tree_view)
        self.setLayout(layout)

    def export_data(self):
        # TODO: Export to JSON or CSV
        pass

    def _refresh(self):
        self.tree_model.set_particle_data(self.node.extract_data())
