"""
This node enables the viewing of individual particle values as a tree/json
format.

TODO: Should we enable users to modify directly in this ndoe.
"""
from __future__ import annotations

import keyword
from dataclasses import dataclass
from typing import Any, Hashable, Optional

from PySide6.QtCore import Signal, QAbstractItemModel, QObject, QPersistentModelIndex, QModelIndex, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QTreeView

from results import results_reader

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
        self._has_ouput = False  # TODO: Change this to true because we want observability
        self.input_channels = ["input"]
        self.output_channels = []  # TODO: Maybe try this
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
        print("ParticleModel __init__", flush=True)
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
        print("ParticleModel get_item", flush=True)
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
        print("ParticleModel index", flush=True)

        if not self.hasIndex(row, column, parent):
            return QModelIndex()  # TODO: check if that's it

        parent_item: ParticleModelItem | ParticleModelRootItem | ParticleModelLeafItem = (
            self.get_item(parent)
        )

        if isinstance(parent_item, ParticleModelItem | ParticleModelRootItem):
            return self.createIndex(row, column, parent_item.children[row])
        if isinstance(parent_item, ParticleModelLeafItem):
            return self.createIndex(row, column, parent_item.value)

        return QModelIndex()

    def parent(self, index: QModelIndex = QModelIndex()) -> QAbstractItemModel:
        print("ParticleModel parent", flush=True)
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
        print("ParticleModel rowCount", flush=True)
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
        print("ParticleModel columnCount", flush=True)
        return 2

    def data(self,
             index: QModelIndex | QPersistentModelIndex, /,
             role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        print("ParticleModel data", flush=True)

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
                    return str(particle_item.children)
                case _:
                    return None
        elif isinstance(particle_item, ParticleModelRootItem):
            match index.column():
                case 0:
                    return "Key"
                case 1:
                    return str(particle_item.children)
                case _:
                    return None
        else:
            return None

    def flags(self,
              index: QModelIndex | QPersistentModelIndex,
              /) -> Qt.ItemFlag:
        print("ParticleModel flags", flush=True)
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | QAbstractItemModel.flags(self, index)

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation, /,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        print("ParticleModel headerData", flush=True)

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
        print("ParticleModel set_particle_data", flush=True)
        self.beginResetModel()
        self.root_item = self._to_tree(particle_data)
        self.endResetModel()


class ParticleViewerSettingsDialog(QDialog):
    preview_requested = Signal(dict)


class ParticleViewerDialog(QDialog):
    def __init__(self, /, node: ParticleViewerNode, parent: QWidget | Any = None):
        super().__init__(parent=parent)
        print("ParticleViewerDialog __init__", flush=True)
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
        print("ParticleViewerDialog showEvent", flush=True)
        super().showEvent(event)
        if self._initial_refresh_pending:
            self._initial_refresh_pending = False

    def _build_ui(self):
        print("ParticleViewerDialog _build_ui", flush=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.tree_view)
        self.setLayout(layout)

    def export_data(self):
        # TODO: Export to JSON or CSV
        pass

    def _refresh(self):
        print("ParticleViewerDialog refresh", flush=True)
        self.tree_model.set_particle_data(self.node.extract_data())
