import pyqtgraph as pg
from PySide6.QtGui import QColor, QPen, QFont, QAction
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSpinBox, QDoubleSpinBox, QColorDialog, 
                               QComboBox, QCheckBox, QLineEdit, QGroupBox, 
                               QFormLayout, QTabWidget, QWidget, QSlider,
                               QFontDialog, QMessageBox, QFileDialog, QMenu)
from PySide6.QtCore import Qt, Signal
import numpy as np
import json
import pandas as pd
from pathlib import Path

class PlotSettingsDialog(QDialog):
    
    def __init__(self, plot_widget, parent=None):
        """
        Initialize the simplified plot settings dialog.
        
        Args:
            plot_widget: The plot widget to configure
            parent: Parent widget for the dialog
            
        Returns:
            None
        """
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setWindowTitle("Plot Settings")
        self.setMinimumSize(500, 450)
        self.setup_ui()
        self.load_persistent_settings()
        
    def setup_ui(self):
        """
        Set up the user interface for the dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        self.create_font_tab()
        self.create_grid_tab()
        
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.reset_button = QPushButton("Reset to Defaults")
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.apply_button.clicked.connect(self.apply_settings)
        self.ok_button.clicked.connect(self.accept_and_apply)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self.reset_to_defaults)
        
    def get_font_families(self):
        """
        Get list of available font families.
        
        Args:
            None
            
        Returns:
            list: List of font family name strings
        """
        return [
            "Times New Roman", "Arial", "Helvetica", "Calibri", "Verdana",
            "Tahoma", "Georgia", "Trebuchet MS", "Comic Sans MS", "Impact",
            "Lucida Console", "Courier New", "Palatino", "Garamond", "Book Antiqua"
        ]
            
    def create_font_tab(self):
        """
        Create global font settings tab.
        
        Args:
            None
            
        Returns:
            None
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        font_group = QGroupBox("Global Font Settings (applies to all text)")
        font_layout = QFormLayout(font_group)
        
        self.global_font_family = QComboBox()
        self.global_font_family.addItems(self.get_font_families())
        self.global_font_family.setCurrentText("Times New Roman")
        
        self.axis_font_size = QSpinBox()
        self.axis_font_size.setRange(6, 72)
        self.axis_font_size.setValue(20)
        
        self.title_font_size = QSpinBox()
        self.title_font_size.setRange(6, 72)
        self.title_font_size.setValue(20)
        
        self.legend_font_size = QSpinBox()
        self.legend_font_size.setRange(6, 72)
        self.legend_font_size.setValue(16)
        
        font_style_layout = QHBoxLayout()
        self.global_bold = QCheckBox("Bold")
        self.global_bold.setChecked(True)
        self.global_italic = QCheckBox("Italic")
        font_style_layout.addWidget(self.global_bold)
        font_style_layout.addWidget(self.global_italic)
        font_style_layout.addStretch()
        
        self.font_color_button = QPushButton()
        self.font_color = QColor("#000000")
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        
        self.bg_color_button = QPushButton()
        self.bg_color = QColor("#FFFFFF")
        self.bg_color_button.setStyleSheet(f"background-color: {self.bg_color.name()}; min-height: 30px;")
        self.bg_color_button.clicked.connect(lambda: self.choose_color('bg'))
        
        self.title_text = QLineEdit()
        
        font_layout.addRow("Font Family (All Text):", self.global_font_family)
        font_layout.addRow("Axis Labels Font Size:", self.axis_font_size)
        font_layout.addRow("Title Font Size:", self.title_font_size)
        font_layout.addRow("Legend Font Size:", self.legend_font_size)
        font_layout.addRow("Font Style (All Text):", font_style_layout)
        font_layout.addRow("Font Color (All Text):", self.font_color_button)
        font_layout.addRow("Background Color:", self.bg_color_button)
        font_layout.addRow("Title Text:", self.title_text)
        
        layout.addWidget(font_group)
        
        note_label = QLabel("Note: These settings apply globally to all axis labels, titles, and legend text.")
        note_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(note_label)
        
        self.tab_widget.addTab(widget, "Fonts")
            
    def create_grid_tab(self):
        """
        Create grid settings tab.
        
        Args:
            None
            
        Returns:
            None
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        grid_group = QGroupBox("Grid Settings")
        grid_layout = QFormLayout(grid_group)
        
        self.show_x_grid = QCheckBox("Show X Grid")
        self.show_y_grid = QCheckBox("Show Y Grid")
        
        self.grid_alpha = QSlider(Qt.Horizontal)
        self.grid_alpha.setRange(0, 255)
        self.grid_alpha.setValue(50)
        self.grid_alpha_label = QLabel("50")
        self.grid_alpha.valueChanged.connect(lambda v: self.grid_alpha_label.setText(str(v)))
        
        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(self.grid_alpha)
        alpha_layout.addWidget(self.grid_alpha_label)
        
        self.grid_color_button = QPushButton()
        self.grid_color = QColor("#808080")
        self.grid_color_button.setStyleSheet(f"background-color: {self.grid_color.name()}; min-height: 30px;")
        self.grid_color_button.clicked.connect(lambda: self.choose_color('grid'))
        
        self.grid_style = QComboBox()
        self.grid_style.addItems(["Solid", "Dashed", "Dotted"])
        self.grid_style.setCurrentText("Solid")
        
        grid_layout.addRow(self.show_x_grid)
        grid_layout.addRow(self.show_y_grid)
        grid_layout.addRow("Grid Color:", self.grid_color_button)
        grid_layout.addRow("Grid Style:", self.grid_style)
        grid_layout.addRow("Transparency:", alpha_layout)
        
        layout.addWidget(grid_group)
        
        self.tab_widget.addTab(widget, "Grid")
        
    def choose_color(self, color_type):
        """
        Open color dialog for different color types.
        
        Args:
            color_type: Type of color to choose ('font', 'bg', or 'grid')
            
        Returns:
            None
        """
        color_map = {
            'font': (self.font_color, self.font_color_button),
            'bg': (self.bg_color, self.bg_color_button),
            'grid': (self.grid_color, self.grid_color_button)
        }
        
        if color_type in color_map:
            current_color, button = color_map[color_type]
            color = QColorDialog.getColor(current_color, self)
            if color.isValid():
                color_map[color_type] = (color, button)
                button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
                setattr(self, f"{color_type}_color", color)
                
    def create_font(self, family, size, bold=False, italic=False):
        """
        Create a QFont with specified properties.
        
        Args:
            family: Font family name
            size: Font size in points
            bold: Whether font should be bold
            italic: Whether font should be italic
            
        Returns:
            QFont: Configured font object
        """
        font = QFont(family, size)
        font.setBold(bold)
        font.setItalic(italic)
        return font

    def load_persistent_settings(self):
        """
        Load persistent settings from plot widget.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self.plot_widget, 'persistent_dialog_settings'):
            settings = self.plot_widget.persistent_dialog_settings
            try:
                self.global_font_family.setCurrentText(settings.get('global_font_family', 'Times New Roman'))
                self.axis_font_size.setValue(settings.get('axis_font_size', 20))
                self.title_font_size.setValue(settings.get('title_font_size', 20))
                self.legend_font_size.setValue(settings.get('legend_font_size', 16))
                self.global_bold.setChecked(settings.get('global_bold', True))
                self.global_italic.setChecked(settings.get('global_italic', False))
                
                self.font_color = QColor(settings.get('font_color', '#000000'))
                self.bg_color = QColor(settings.get('bg_color', '#FFFFFF'))
                self.grid_color = QColor(settings.get('grid_color', '#808080'))
                
                self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
                self.bg_color_button.setStyleSheet(f"background-color: {self.bg_color.name()}; min-height: 30px;")
                self.grid_color_button.setStyleSheet(f"background-color: {self.grid_color.name()}; min-height: 30px;")
                
                self.title_text.setText(settings.get('title_text', ''))
                self.show_x_grid.setChecked(settings.get('show_x_grid', False))
                self.show_y_grid.setChecked(settings.get('show_y_grid', False))
                self.grid_alpha.setValue(settings.get('grid_alpha', 50))
                self.grid_style.setCurrentText(settings.get('grid_style', 'Solid'))
                
            except Exception as e:
                print(f"Error loading persistent settings: {e}")

    def save_persistent_settings(self):
        """
        Save all dialog settings to plot widget for persistence.
        
        Args:
            None
            
        Returns:
            None
        """
        settings = {
            'global_font_family': self.global_font_family.currentText(),
            'axis_font_size': self.axis_font_size.value(),
            'title_font_size': self.title_font_size.value(),
            'legend_font_size': self.legend_font_size.value(),
            'global_bold': self.global_bold.isChecked(),
            'global_italic': self.global_italic.isChecked(),
            'font_color': self.font_color.name(),
            'bg_color': self.bg_color.name(),
            'grid_color': self.grid_color.name(),
            'title_text': self.title_text.text(),
            'show_x_grid': self.show_x_grid.isChecked(),
            'show_y_grid': self.show_y_grid.isChecked(),
            'grid_alpha': self.grid_alpha.value(),
            'grid_style': self.grid_style.currentText()
        }
        
        self.plot_widget.persistent_dialog_settings = settings

    def apply_settings(self):
        """
        Apply settings to the plot widget.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            plot_item = self.plot_widget.getPlotItem()
            
            self.plot_widget.setBackground(self.bg_color)
            
            font_family = self.global_font_family.currentText()
            is_bold = self.global_bold.isChecked()
            is_italic = self.global_italic.isChecked()
            
            axis_font = self.create_font(font_family, self.axis_font_size.value(), is_bold, is_italic)
            title_font = self.create_font(font_family, self.title_font_size.value(), is_bold, is_italic)
            legend_font = self.create_font(font_family, self.legend_font_size.value(), is_bold, is_italic)
            
            x_axis = plot_item.getAxis('bottom')
            y_axis = plot_item.getAxis('left')
            
            x_axis.setStyle(tickFont=axis_font, tickTextOffset=10, tickLength=10)
            y_axis.setStyle(tickFont=axis_font, tickTextOffset=10, tickLength=10)
            
            x_axis.setTextPen(self.font_color)
            y_axis.setTextPen(self.font_color)
            x_axis.setPen(QPen(self.font_color, 1))
            y_axis.setPen(QPen(self.font_color, 1))
            
            font_weight = "bold" if is_bold else "normal"
            font_style = "italic" if is_italic else "normal"
            
            if hasattr(self.plot_widget, 'custom_axis_labels'):
                labels = self.plot_widget.custom_axis_labels
                
                if 'bottom' in labels:
                    label_info = labels['bottom']
                    if label_info.get('units'):
                        plot_item.setLabel('bottom', label_info['text'], units=label_info['units'],
                                        color=self.font_color.name(), 
                                        font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
                    else:
                        plot_item.setLabel('bottom', label_info['text'],
                                        color=self.font_color.name(), 
                                        font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
                
                if 'left' in labels:
                    label_info = labels['left']
                    if label_info.get('units'):
                        plot_item.setLabel('left', label_info['text'], units=label_info['units'],
                                        color=self.font_color.name(), 
                                        font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
                    else:
                        plot_item.setLabel('left', label_info['text'],
                                        color=self.font_color.name(), 
                                        font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
            else:
                plot_item.setLabel('bottom', 'Time', units='s', 
                                color=self.font_color.name(), 
                                font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
                plot_item.setLabel('left', 'Intensity', units='counts', 
                                color=self.font_color.name(), 
                                font=f'{font_style} {font_weight} {self.axis_font_size.value()}pt {font_family}')
            
            if self.show_x_grid.isChecked() or self.show_y_grid.isChecked():
                plot_item.showGrid(
                    x=self.show_x_grid.isChecked(), 
                    y=self.show_y_grid.isChecked(), 
                    alpha=self.grid_alpha.value()/255.0
                )
            else:
                plot_item.showGrid(x=False, y=False)
            
            if self.title_text.text():
                plot_item.setTitle(
                    self.title_text.text(), 
                    color=self.font_color.name(),
                    size=f'{font_style} {font_weight} {self.title_font_size.value()}pt {font_family}'
                )
            else:
                plot_item.setTitle('')
            
            if hasattr(self.plot_widget, 'legend') and self.plot_widget.legend:
                try:
                    legend_size_pt = f'{self.legend_font_size.value()}pt'
                    self.plot_widget.legend.setLabelTextSize(legend_size_pt)
                    self.plot_widget.legend.setLabelTextColor(self.font_color)
                    
                    legend_label_style = {
                        'color': self.font_color.name(),
                        'size': legend_size_pt,
                        'bold': is_bold,
                        'italic': is_italic
                    }
                    
                    if hasattr(self.plot_widget.legend, 'items'):
                        for item in self.plot_widget.legend.items:
                            if len(item) >= 2:
                                sample, label = item[0], item[1]
                                if hasattr(label, 'setText'):
                                    try:
                                        label.setText(label.text, **legend_label_style)
                                    except:
                                        label.setText(label.text, size=legend_size_pt, color=self.font_color.name())
                                        
                except Exception as e:
                    print(f"Warning: Could not update legend font settings: {e}")
            
            plot_item.getViewBox().updateAutoRange()
            x_axis.update()
            y_axis.update()
            self.plot_widget.repaint()
            
            self.store_settings()
            self.save_persistent_settings()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error applying settings: {str(e)}")
            print(f"Detailed error: {e}")
            import traceback
            traceback.print_exc()
            
    def store_settings(self):
        """
        Store settings to widget for future use.
        
        Args:
            None
            
        Returns:
            None
        """
        settings = {
            'global_font_family': self.global_font_family.currentText(),
            'axis_font_size': self.axis_font_size.value(),
            'title_font_size': self.title_font_size.value(),
            'legend_font_size': self.legend_font_size.value(),
            'global_bold': self.global_bold.isChecked(),
            'global_italic': self.global_italic.isChecked(),
            'font_color': self.font_color.name(),
            'bg_color': self.bg_color.name(),
            'title_text': self.title_text.text(),
            'show_x_grid': self.show_x_grid.isChecked(),
            'show_y_grid': self.show_y_grid.isChecked(),
            'grid_color': self.grid_color.name(),
            'grid_alpha': self.grid_alpha.value()
        }
        
        if hasattr(self.plot_widget, 'custom_settings'):
            self.plot_widget.custom_settings.update(settings)
        else:
            self.plot_widget.custom_settings = settings
            
    def reset_to_defaults(self):
        """
        Reset all settings to defaults.
        
        Args:
            None
            
        Returns:
            None
        """
        self.global_font_family.setCurrentText("Times New Roman")
        self.axis_font_size.setValue(20)
        self.title_font_size.setValue(20)
        self.legend_font_size.setValue(16)
        self.global_bold.setChecked(True)
        self.global_italic.setChecked(False)
        
        self.font_color = QColor("#000000")
        self.bg_color = QColor("#FFFFFF")
        self.grid_color = QColor("#808080")
        
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.bg_color_button.setStyleSheet(f"background-color: {self.bg_color.name()}; min-height: 30px;")
        self.grid_color_button.setStyleSheet(f"background-color: {self.grid_color.name()}; min-height: 30px;")
        
        self.title_text.setText("")
        self.show_x_grid.setChecked(False)
        self.show_y_grid.setChecked(False)
        self.grid_alpha.setValue(50)
        self.grid_style.setCurrentText("Solid")
        
        if hasattr(self.plot_widget, 'persistent_dialog_settings'):
            del self.plot_widget.persistent_dialog_settings
                
    def accept_and_apply(self):
        """
        Apply settings and close dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        self.apply_settings()
        self.accept()
        
    def closeEvent(self, event):
        """
        Save settings when dialog is closed.
        
        Args:
            event: Close event object
            
        Returns:
            None
        """
        self.save_persistent_settings()
        super().closeEvent(event)


class CustomPlotItem(pg.PlotItem):
    
    def __init__(self, *args, **kwargs):
        """
        Initialize custom plot item with simplified menu.
        
        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
            
        Returns:
            None
        """
        super().__init__(*args, **kwargs)
        self.plot_widget = None
        self._settings_action = None
        
    def getContextMenus(self, event):
        """
        Override to add only plot settings to the default menu.
        
        Args:
            event: Context menu event
            
        Returns:
            QMenu: Context menu with plot settings action
        """
        menu = super().getContextMenus(event)
        
        if self.plot_widget is not None:
            existing_actions = [action.text() for action in menu.actions()]
            
            if "Plot Settings..." not in existing_actions:
                menu.addSeparator()
                
                if self._settings_action is None:
                    self._settings_action = QAction("Plot Settings...", self.plot_widget)
                    self._settings_action.triggered.connect(self.plot_widget.open_plot_settings)
                
                menu.addAction(self._settings_action)
        
        return menu


class EnhancedPlotWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        """
        Initialize enhanced plot widget with custom features.
        
        Args:
            parent: Parent widget
            
        Returns:
            None
        """
        self.custom_plot_item = CustomPlotItem()
        
        super().__init__(parent, plotItem=self.custom_plot_item)
        
        self.custom_plot_item.plot_widget = self
        
        self.setup_appearance()
        self.setup_interaction_features()
        self.data_items = {}
        self.original_range = None
        self.custom_settings = {}
        self.persistent_dialog_settings = {}
        
    def setup_appearance(self):
        """
        Set up the visual appearance of the plot widget.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setBackground('white')
        plot_item = self.getPlotItem()
        plot_item.showGrid(x=False, y=False)
        plot_item.getAxis('left').setGrid(False)
        plot_item.getAxis('bottom').setGrid(False)
        plot_item.getAxis('left').enableAutoSIPrefix(False)
        
        axis_pen = QPen(QColor("#000000"), 1)
        text_color = QColor("#000000")
        
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)
        
        label_font = QFont('Times New Roman', 20)
        label_font.setBold(True)
        
        for axis in ['left', 'bottom']:
            ax = plot_item.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setFont(tick_font)
            
            ax.setStyle(
                tickFont=tick_font,
                tickTextOffset=10,
                tickLength=10
            )
        
        self.setLabel('left', 'Intensity', units='counts', color="#000000", 
                    font='bold 20pt Times New Roman')
        self.setLabel('bottom', 'Time', units='s', color="#000000", 
                    font='bold 20pt Times New Roman')
        
        self.legend = self.addLegend(offset=(-30, 30))
        self.legend.setLabelTextColor(text_color)
        self.legend.setLabelTextSize('16pt')
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.legend.setPen(pg.mkPen(color="#000000", width=1, style=Qt.SolidLine, cosmetic=True, alpha=100))
                    
    def setup_interaction_features(self):
        """
        Set up interactive features like crosshairs and mouse controls.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setMouseEnabled(x=True, y=True)
        view_box = self.getPlotItem().getViewBox()
        view_box.setMouseMode(view_box.RectMode)
        
        try:
            self.vertical_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#000000", width=0.5))
            self.horizontal_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#000000", width=0.5))
            self.addItem(self.vertical_line)
            self.addItem(self.horizontal_line)
            self.scene().sigMouseMoved.connect(self.mouse_moved)
        except Exception as e:
            print(f"Warning: Could not setup crosshair: {str(e)}")
        
    def open_plot_settings(self):
        """
        Open simplified plot settings dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        dialog = PlotSettingsDialog(self, self.parent())
        dialog.exec()

    def wheelEvent(self, event):
        """
        Handle mouse wheel zoom events independently for x and y axes.
        
        Args:
            event: Wheel event object
            
        Returns:
            None
        """
        try:
            x_range, y_range = self.getPlotItem().getViewBox().viewRange()
            zoom_factor = 0.5 if event.angleDelta().y() > 0 else 2.0
            mouse_point = self.getPlotItem().vb.mapSceneToView(event.position())
            mouse_x = mouse_point.x()
            mouse_y = mouse_point.y()
            plot_rect = self.getPlotItem().vb.sceneBoundingRect()
            rel_x = (event.position().x() - plot_rect.left()) / plot_rect.width()
            rel_y = (event.position().y() - plot_rect.top()) / plot_rect.height()
            margin = 0.1 
            zoom_x = rel_x >= 0 and rel_x <= 1 and rel_y > (1 - margin) 
            zoom_y = rel_y >= 0 and rel_y <= 1 and rel_x < margin
            if zoom_x:
                x_min = mouse_x - (mouse_x - x_range[0]) * zoom_factor
                x_max = mouse_x + (x_range[1] - mouse_x) * zoom_factor
                self.getPlotItem().setXRange(x_min, x_max, padding=0)
            elif zoom_y:
                y_min = mouse_y - (mouse_y - y_range[0]) * zoom_factor
                y_max = mouse_y + (y_range[1] - mouse_y) * zoom_factor
                self.getPlotItem().setYRange(y_min, y_max, padding=0)
            event.accept()
        except Exception as e:
            print(f"Warning: Error handling wheel zoom: {str(e)}")

    def update_plot(self, time_array, data):
        """
        Update the plot with new data.
        
        Args:
            time_array: Array of time values
            data: Dictionary mapping mass values to signal arrays
            
        Returns:
            None
        """
        if time_array is None or not data:
            return
            
        line_width = 1
        
        default_colors = [
            '#3498db',
            '#2ecc71',
            '#e74c3c',
            '#9b59b6',
            '#f1c40f',
            '#1abc9c',
            '#e67e22'
        ]
        
        for mass in list(self.data_items.keys()):
            if mass not in data:
                self.removeItem(self.data_items[mass])
                del self.data_items[mass]
        
        for i, (mass, signals) in enumerate(data.items()):
            try:
                color = QColor(default_colors[i % len(default_colors)])
                
                if len(signals) == 0 or len(time_array) == 0:
                    continue
                    
                signals = np.nan_to_num(signals, nan=0.0)
                
                try:
                    signals_smooth = self.smooth_data(signals)
                except Exception:
                    signals_smooth = signals
                
                min_len = min(len(time_array), len(signals_smooth))
                time_array_plot = time_array[:min_len]
                signals_smooth = signals_smooth[:min_len]
                
                pen = pg.mkPen(color=color, width=line_width, style=Qt.SolidLine)
                
                if mass in self.data_items:
                    self.data_items[mass].setData(time_array_plot, signals_smooth)
                    self.data_items[mass].setPen(pen)
                else:
                    plot_item = pg.PlotDataItem(
                        time_array_plot,
                        signals_smooth,
                        pen=pen,
                        name=f'Mass {mass}',
                        antialias=True
                    )
                    self.addItem(plot_item)
                    self.data_items[mass] = plot_item
                    
            except Exception as e:
                print(f"Warning: Error plotting mass {mass}: {str(e)}")
        
        if self.original_range is None:
            self.original_range = self.viewRange()
    
    def smooth_data(self, data, window=5):
        """
        Apply simple moving average smoothing.
        
        Args:
            data: Array of data values to smooth
            window: Window size for smoothing
            
        Returns:
            ndarray: Smoothed data array
        """
        try:
            if len(data) < window:
                return data
            
            pad_data = np.pad(data, (window//2, window//2), mode='edge')
            
            weights = np.ones(window) / window
            smoothed = np.convolve(pad_data, weights, mode='valid')
            
            return smoothed
        except Exception as e:
            print(f"Warning: Smoothing failed, returning original data: {str(e)}")
            return data
    
    def mouse_moved(self, pos):
        """
        Handle mouse movement for crosshair display.
        
        Args:
            pos: Mouse position
            
        Returns:
            None
        """
        try:
            if self.sceneBoundingRect().contains(pos):
                mouse_point = self.getPlotItem().vb.mapSceneToView(pos)
                self.vertical_line.setPos(mouse_point.x())
                self.horizontal_line.setPos(mouse_point.y())
        except Exception:
            pass
            
    def clear_plot(self):
        """
        Clear all plots and reset zoom.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            for item in self.data_items.values():
                self.removeItem(item)
            self.data_items.clear()
            self.original_range = None
        except Exception as e:
            print(f"Warning: Error clearing plot: {str(e)}")


class BasicPlotWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        """
        Initialize basic plot widget.
        
        Args:
            parent: Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setup_basic_appearance()
        self.data_items = {}
        self.persistent_dialog_settings = {}
        
    def setup_basic_appearance(self):
        """
        Set up basic visual appearance.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setBackground('white')
        
        plot_item = self.getPlotItem()
        plot_item.showGrid(x=False, y=False)
        
        axis_pen = QPen(QColor("#000000"), 1)
        text_color = QColor("#000000")
        
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)
        
        for axis in ['left', 'bottom']:
            ax = plot_item.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setFont(tick_font)
            
            ax.setStyle(
                tickFont=tick_font,
                tickTextOffset=10,
                tickLength=10
            )
        
        self.setLabel('left', 'Intensity (counts)', color="#000000", 
                    font='bold 20pt Times New Roman')
        self.setLabel('bottom', 'Time (s)', color="#000000", 
                    font='bold 20pt Times New Roman')
        
        self.setMouseEnabled(x=True, y=False)

    def update_plot(self, time_array, data):
        """
        Update the plot with new data.
        
        Args:
            time_array: Array of time values
            data: Dictionary mapping mass values to signal arrays
            
        Returns:
            None
        """
        if time_array is None or not data:
            return
            
        colors = ['b', 'g', 'r', 'c', 'm', 'y']
        
        for mass in list(self.data_items.keys()):
            if mass not in data:
                self.removeItem(self.data_items[mass])
                del self.data_items[mass]
        
        for i, (mass, signals) in enumerate(data.items()):
            color = colors[i % len(colors)]
            
            if len(signals) == 0 or len(time_array) == 0:
                continue
                
            min_len = min(len(time_array), len(signals))
            time_array = time_array[:min_len]
            signals = signals[:min_len]
            
            if mass in self.data_items:
                self.data_items[mass].setData(time_array, signals)
            else:
                plot_item = pg.PlotDataItem(
                    time_array,
                    signals,
                    pen=color,
                    name=str(mass)
                )
                self.addItem(plot_item)
                self.data_items[mass] = plot_item
    
    def clear_plot(self):
        """
        Clear all plots.
        
        Args:
            None
            
        Returns:
            None
        """
        for item in self.data_items.values():
            self.removeItem(item)
        self.data_items.clear()

    def setTitle(self, title):
        """
        Set plot title.
        
        Args:
            title: Title text to display
            
        Returns:
            None
        """
        self.getPlotItem().setTitle(title)
        

class CalibrationPlotWidget(EnhancedPlotWidget):
    def __init__(self, parent=None):
        """
        Initialize calibration plot widget.
        
        Args:
            parent: Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setup_calibration_appearance()
        
    def setup_calibration_appearance(self):
        """
        Set up appearance specific to calibration plots.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setBackground('white')
        plot_item = self.getPlotItem()
        plot_item.showGrid(x=False, y=False)
        
        axis_pen = QPen(QColor("#000000"), 1)
        text_color = QColor("#000000")
        
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)
        
        for axis in ['left', 'bottom']:
            ax = plot_item.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setFont(tick_font)
            
            ax.setStyle(
                tickFont=tick_font,
                tickTextOffset=10,
                tickLength=10
            )
        
        self.legend = self.addLegend()
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.legend.setPen(pg.mkPen(color="#000000", width=1, alpha=100))
        
    def setLabel(self, axis, text, units=None, color=None, font=None):
        """
        Set axis label with optional color and font parameters.
        
        Args:
            axis: Axis identifier ('left' or 'bottom')
            text: Label text
            units: Optional units string
            color: Optional color specification
            font: Optional font specification
            
        Returns:
            None
        """
        if units:
            if color and font:
                self.getPlotItem().setLabel(axis, text, units=units, color=color, font=font)
            elif color:
                self.getPlotItem().setLabel(axis, text, units=units, color=color)
            else:
                self.getPlotItem().setLabel(axis, text, units=units)
        else:
            if color and font:
                self.getPlotItem().setLabel(axis, text, color=color, font=font)
            elif color:
                self.getPlotItem().setLabel(axis, text, color=color)
            else:
                self.getPlotItem().setLabel(axis, text)

    def update_plot(self, x_data, y_data, y_std, method='zero', y_fit=None, key="Data"):
        """
        Plot calibration data with error bars and fit line.
        
        Args:
            x_data: X-axis data values
            y_data: Y-axis data values
            y_std: Standard deviation for error bars
            method: Calibration method name
            y_fit: Optional fitted y values
            key: Data series key identifier
            
        Returns:
            None
        """
        self.clear_plot()
        
        error = pg.ErrorBarItem(
            x=np.array(x_data), 
            y=np.array(y_data),
            height=np.array(y_std) * 2,
            beam=0.05
        )
        self.addItem(error)
        
        scatter = pg.ScatterPlotItem(
            x=x_data,
            y=y_data,
            symbol='o',
            size=12,
            pen=pg.mkPen('b', width=1),
            brush='b',
            name='Data points'
        )
        self.addItem(scatter)
        if y_fit is not None:
            line = pg.PlotDataItem(
                x_data,
                y_fit,
                pen=pg.mkPen('r', width=1),
                name=f'{method.capitalize()} fit'
            )
            self.addItem(line)
        
        self.autoRange()
        
    def clear_plot(self):
        """
        Clear the calibration plot and recreate legend.
        
        Args:
            None
            
        Returns:
            None
        """
        self.getPlotItem().clear()
        self.legend = self.addLegend()
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.legend.setPen(pg.mkPen(color="#000000", width=1, alpha=100))
        
    def setTitle(self, title):
        """
        Set the plot title.
        
        Args:
            title: Title text to display
            
        Returns:
            None
        """
        self.getPlotItem().setTitle(title)