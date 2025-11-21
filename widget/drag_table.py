import os
from PySide6.QtWidgets import (QComboBox, QMessageBox, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView, QMenu)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent
from PySide6.QtCore import Qt


class DraggableTableWidget(QTableWidget):
    def __init__(self, parent=None):
        """
        Initialize the draggable table widget for calibration folders.
        
        Args:
            parent: Parent widget for the table
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.verticalHeader().setVisible(True)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["File", "Concentration", "Unit"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setMinimumHeight(300)
        
        self.folder_paths = {}
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setDragDropMode(QTableWidget.DragDrop)

    def dropEvent(self, event: QDropEvent):
        """
        Handle drop events for row reordering by swapping data between rows.
        
        Args:
            event: Drop event containing information about the drop operation
            
        Returns:
            None
        """
        if event.source() == self:
            selected_row = self.currentRow()
            drop_row = self.rowAt(event.position().toPoint().y())
            
            if drop_row != -1 and selected_row != drop_row:
                file1 = self.item(selected_row, 0).text()
                file2 = self.item(drop_row, 0).text()
                self.setItem(selected_row, 0, QTableWidgetItem(file2))
                self.setItem(drop_row, 0, QTableWidgetItem(file1))
                
                conc1 = self.item(selected_row, 1).text()
                conc2 = self.item(drop_row, 1).text()
                self.setItem(selected_row, 1, QTableWidgetItem(conc2))
                self.setItem(drop_row, 1, QTableWidgetItem(conc1))
                
                unit1 = self.cellWidget(selected_row, 2).currentText()
                unit2 = self.cellWidget(drop_row, 2).currentText()
                self.cellWidget(selected_row, 2).setCurrentText(unit2)
                self.cellWidget(drop_row, 2).setCurrentText(unit1)
                
                path1 = self.folder_paths.get(selected_row, '')
                path2 = self.folder_paths.get(drop_row, '')
                self.folder_paths[selected_row] = path2
                self.folder_paths[drop_row] = path1
                
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        Handle drag enter events to validate drag source.
        
        Args:
            event: Drag enter event object
            
        Returns:
            None
        """
        if event.source() == self:
            event.accept()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event: QDragMoveEvent):
        """
        Handle drag move events during dragging operation.
        
        Args:
            event: Drag move event object
            
        Returns:
            None
        """
        if event.source() == self:
            event.accept()
        else:
            event.ignore()

    def show_context_menu(self, position):
        """
        Display context menu with add and remove options.
        
        Args:
            position: Position where context menu should be displayed
            
        Returns:
            None
        """
        context_menu = QMenu(self)
        add_action = context_menu.addAction("Add Folder")
        remove_action = context_menu.addAction("Remove Selected")
        
        action = context_menu.exec(self.mapToGlobal(position))
        
        if action == add_action:
            self.add_folder()
        elif action == remove_action:
            self.remove_selected()

    def add_folder(self):
        """
        Add a new calibration folder to the table.
        
        Args:
            None
            
        Returns:
            None
        """
        folder = QFileDialog.getExistingDirectory(self, "Select Calibration Folder")
        if folder:
            row_position = self.rowCount()
            self.insertRow(row_position)
            
            self.folder_paths[row_position] = folder
            
            self.setItem(row_position, 0, QTableWidgetItem(os.path.basename(folder)))
            self.setItem(row_position, 1, QTableWidgetItem("0"))
            unit_combo = QComboBox()
            unit_combo.addItems(["ppb", "ng/L", "µg/L", "ppt"])
            self.setCellWidget(row_position, 2, unit_combo)

    def remove_selected(self):
        """
        Remove the currently selected row from the table.
        
        Args:
            None
            
        Returns:
            None
        """
        current_row = self.currentRow()
        if current_row >= 0:
            if current_row in self.folder_paths:
                del self.folder_paths[current_row]
            
            new_paths = {}
            for row, path in self.folder_paths.items():
                if row > current_row:
                    new_paths[row - 1] = path
                else:
                    new_paths[row] = path
            self.folder_paths = new_paths
            
            self.removeRow(current_row)
        else:
            QMessageBox.warning(self, "Warning", "Please select a row to remove")

    def update_with_folder_paths(self, folders):
        """
        Update the table with a list of folder paths.
        
        Args:
            folders: List of folder path strings to populate the table
            
        Returns:
            None
        """
        self.setRowCount(0)
        self.folder_paths.clear()
        
        for i, folder in enumerate(folders):
            self.insertRow(i)
            self.folder_paths[i] = folder
            self.setItem(i, 0, QTableWidgetItem(os.path.basename(folder)))
            self.setItem(i, 1, QTableWidgetItem("0"))
            unit_combo = QComboBox()
            unit_combo.addItems(["ppb", "ng/L", "µg/L", "ppt"])
            self.setCellWidget(i, 2, unit_combo)

    def get_folder_path(self, row):
        """
        Get the folder path for a specific row.
        
        Args:
            row: Row index to retrieve folder path for
            
        Returns:
            str: Folder path string for the specified row, or empty string if not found
        """
        return self.folder_paths.get(row, '')