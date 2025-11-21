from PySide6.QtWidgets import (QWidget, QGridLayout, QPushButton, QVBoxLayout, 
                             QLabel, QSizePolicy, QHBoxLayout, QDialog, QApplication,
                             QFrame)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRect, Property, QPoint
from PySide6.QtGui import QColor, QPainter, QLinearGradient
import json
import math


class CompactAnimatedButton(QPushButton):
    """
    Custom animated button for periodic table elements with isotope selection support.
    
    This button displays element symbols and handles mouse interactions for isotope selection.
    It supports visual highlighting based on isotope abundance and progressive selection modes.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the compact animated button.
        
        Args:
            parent (QWidget): Parent widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent)
        self._scale = 1.0
        self.isotope_display = None
        self.highlight_percentage = 0
        self.selected_abundances = []
        self.highlight_color = QColor(153,153,153)
        self.is_selected = False

    def set_isotope_display(self, display):
        """
        Set the isotope display panel for this button.
        
        Args:
            display (CompactIsotopeDisplay): Isotope display widget to associate with this button
        
        Returns:
            None
        """
        self.isotope_display = display
        display.set_parent_button(self)

    def paintEvent(self, event):
        """
        Custom paint event to draw gradient highlight overlay.
        
        Draws a gradient overlay from bottom to top based on the highlight percentage,
        representing selected isotope abundances.
        
        Args:
            event (QPaintEvent): Paint event object
        
        Returns:
            None
        """
        super().paintEvent(event)
        if self.highlight_percentage > 0:
            painter = QPainter(self)
            highlight_height = int(self.height() * (min(self.highlight_percentage, 100) / 100))
            gradient = QLinearGradient(0, self.height() - highlight_height, 0, self.height())
            gradient.setColorAt(0, self.highlight_color)
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            painter.fillRect(0, self.height() - highlight_height, self.width(), highlight_height, gradient)

    def set_highlight(self, percentage, accumulate=True):
        """
        Set or accumulate highlight percentage for isotope abundance visualization.
        
        Args:
            percentage (float): Abundance percentage to add or set
            accumulate (bool): If True, add to existing abundances; if False, replace them
        
        Returns:
            None
        """
        if accumulate:
            self.selected_abundances.append(percentage)
            self.highlight_percentage = min(sum(self.selected_abundances), 100)
        else:
            self.selected_abundances = [percentage]
            self.highlight_percentage = min(percentage, 100)
        self.update()

    def remove_highlight(self, percentage):
        """
        Remove a specific abundance percentage from the highlight.
        
        Args:
            percentage (float): Abundance percentage to remove
        
        Returns:
            None
        """
        if percentage in self.selected_abundances:
            self.selected_abundances.remove(percentage)
            self.highlight_percentage = min(sum(self.selected_abundances), 100)
        self.update()

    def clear_highlights(self):
        """
        Clear all highlight percentages and reset visual state.
        
        Args:
            None
        
        Returns:
            None
        """
        self.selected_abundances = []
        self.highlight_percentage = 0
        self.update()

    def mousePressEvent(self, event):
        """
        Handle mouse press events for isotope selection.
        
        Left click: Progressive isotope selection through available isotopes
        Right click: Toggle isotope display panel at button position
        
        Args:
            event (QMouseEvent): Mouse event object
        
        Returns:
            None
        """
        periodic_table = self.parent()
        element = next((e for e in periodic_table.get_elements() 
                      if e['symbol'] == self.property('element_symbol')), None)
        
        if not element or not self.isEnabled():
            return
            
        if event.button() == Qt.LeftButton:
            if self.isotope_display:
                self.isotope_display.select_next_available_isotope()
                
        elif event.button() == Qt.RightButton:
            periodic_table.close_all_isotope_displays_except(self)
            if self.isotope_display:
                pos = self.mapToGlobal(self.rect().topRight())
                pos = self.parent().mapFromGlobal(pos)
                self.isotope_display.toggle_at_position(pos)
        
        event.accept()


class CompactSelectableIsotopeLabel(QLabel):
    """
    Selectable label widget for individual isotopes with visual feedback.
    
    Displays isotope information and handles click events for selection.
    Visual styling changes based on selection state and availability.
    """
    
    clicked = Signal(object, float)
    
    def __init__(self, text, isotope_mass, is_available=False, parent=None):
        """
        Initialize the selectable isotope label.
        
        Args:
            text (str): Display text for the isotope
            isotope_mass (float): Mass number of the isotope
            is_available (bool): Whether this isotope is available for selection
            parent (QWidget): Parent widget (optional)
        
        Returns:
            None
        """
        super().__init__(text, parent)
        self.isotope_mass = isotope_mass
        self.is_selected = False
        self.is_available = is_available
        self.setCursor(Qt.PointingHandCursor)
        self.updateStyle()
        font = self.font()
        font.setPointSize(10)
        self.setFont(font)
        
    def setSelected(self, selected):
        """
        Set the selection state of this isotope label.
        
        Args:
            selected (bool): True if selected, False otherwise
        
        Returns:
            None
        """
        self.is_selected = selected
        self.updateStyle()
        
    def updateStyle(self):
        """
        Update visual styling based on selection and availability state.
        
        Selected: Cyan background
        Available: Green background
        Unavailable: Gray background
        
        Args:
            None
        
        Returns:
            None
        """
        base_style = "padding: 1px; border-radius: 1px; margin: 1px; color: white;"
        
        if self.is_selected:
            self.setStyleSheet(base_style + "background: rgba(0, 188, 212, 180); border: 2px solid rgba(0, 188, 212, 220);")
        else:
            if self.is_available:
                self.setStyleSheet(base_style + "background: rgba(76, 175, 80, 180); border: 2px solid rgba(76, 175, 80, 220);")
            else:
                self.setStyleSheet(base_style + "background: rgba(61, 61, 61, 180); border: 2px solid rgba(61, 61, 61, 220);")
            
    def mousePressEvent(self, event):
        """
        Handle mouse press events to emit clicked signal.
        
        Args:
            event (QMouseEvent): Mouse event object
        
        Returns:
            None
        """
        if event.button() == Qt.LeftButton and self.is_available:
            self.clicked.emit(self, self.isotope_mass)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        """
        Handle mouse enter event for hover effect.
        
        Args:
            event (QEnterEvent): Enter event object
        
        Returns:
            None
        """
        if not self.is_selected and self.is_available:
            hover_style = "padding: 1px; border-radius: 1px; margin: 1px; color: white; background: rgba(76, 175, 80, 220); border: 1px solid rgba(76, 175, 80, 240);"
            self.setStyleSheet(hover_style)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """
        Handle mouse leave event to restore normal styling.
        
        Args:
            event (QEvent): Event object
        
        Returns:
            None
        """
        self.updateStyle()
        super().leaveEvent(event)


class CompactIsotopeDisplay(QFrame):
    """
    Popup panel displaying available isotopes for an element with selection capability.
    
    This widget appears next to element buttons and shows a list of isotopes with
    their abundances. It supports progressive selection, individual selection,
    and animated show/hide transitions.
    """
    
    isotope_selected = Signal(str, float, float)
    
    def __init__(self, parent=None):
        """
        Initialize the isotope display panel.
        
        Args:
            parent (QWidget): Parent widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent)
        self.setStyleSheet("QFrame { background-color: rgba(45, 45, 45, 220); border: 1px solid #444; border-radius: 2px; padding: 2px; }")
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(1)
        self.setLayout(self.layout)
        self.selected_isotopes = set()
        self.available_isotopes = []
        self.setMouseTracking(True)
        self.hide()
        self.is_visible = False
        self.element_symbol = None
        self.parent_button = None
    
    def get_selected_isotopes_data(self):
        """
        Get list of selected isotopes as tuples.
        
        Args:
            None
        
        Returns:
            list: List of (symbol, mass) tuples for selected isotopes
        """
        return [(symbol, mass) for symbol, mass in self.selected_isotopes]
        
    def load_selected_isotopes(self, isotopes_data):
        """
        Load and display previously selected isotopes.
        
        Args:
            isotopes_data (list): List of (symbol, mass) tuples to select
        
        Returns:
            None
        """
        self.selected_isotopes = set((symbol, mass) for symbol, mass in isotopes_data)
        for mass, label in self.mass_labels.items():
            label.setSelected((self.element_symbol, mass) in self.selected_isotopes)

    def set_isotopes(self, element, available_element_masses=None):
        """
        Populate the display with isotopes for the given element.
        
        Creates labels for each isotope, marking which are available for selection
        based on the available_element_masses parameter.
        
        Args:
            element (dict): Element data dictionary with isotopes list
            available_element_masses (list): List of (element_symbol, mass) tuples indicating available isotopes
        
        Returns:
            None
        """
        self.element_symbol = element['symbol']
        
        self.available_isotopes = []
        if available_element_masses:
            for elem_symbol, mass in available_element_masses:
                if elem_symbol == self.element_symbol:
                    self.available_isotopes.append(mass)
        
        self.available_isotopes.sort()
        
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                
        sorted_isotopes = []
        self.mass_labels = {}
            
        for isotope in element['isotopes']:
            if isinstance(isotope, dict):
                mass = isotope['mass']
                label = isotope['label']
                abundance = isotope.get('abundance', 0)
            else:
                mass = isotope
                mass_number = round(mass)
                label = f"{element['symbol']}-{mass_number}"
                abundance = 0
                
            is_available = mass in self.available_isotopes
            sorted_isotopes.append((mass, label, abundance, is_available))
            
        sorted_isotopes.sort(key=lambda x: x[0])
        
        for mass, label, abundance, is_available in sorted_isotopes:
            if abundance > 0:
                clean_label = label.split()[0] if ' ' in label else label
                display_text = f"{clean_label} ({abundance:.1f}%)"
            else:
                display_text = label
                
            isotope_label = CompactSelectableIsotopeLabel(display_text, mass, is_available, self)
            
            self.mass_labels[mass] = isotope_label
            
            if (self.element_symbol, mass) in self.selected_isotopes:
                isotope_label.setSelected(True)
            
            isotope_label.clicked.connect(self.on_isotope_clicked)
            self.layout.addWidget(isotope_label)
            
        self.adjustSize()

    def set_parent_button(self, button):
        """
        Set the parent button that owns this isotope display.
        
        Args:
            button (CompactAnimatedButton): Parent button widget
        
        Returns:
            None
        """
        self.parent_button = button
        
    def toggle_at_position(self, pos):
        """
        Toggle display visibility at the specified position.
        
        Args:
            pos (QPoint): Position to show the display
        
        Returns:
            None
        """
        if self.is_visible:
            self.hide_with_animation()
        else:
            self.show_at_position(pos)
            
    def hide_with_animation(self):
        """
        Hide the display with a collapsing animation.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.isVisible():
            return
            
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(100)
        start_rect = self.geometry()
        end_rect = QRect(self.x(), self.y(), 0, self.height())
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QEasingCurve.InQuad)
        self.anim.finished.connect(self._on_hide_finished)
        self.anim.start()
        
    def _on_hide_finished(self):
        """
        Callback when hide animation completes.
        
        Args:
            None
        
        Returns:
            None
        """
        self.hide()
        self.is_visible = False

    def show_at_position(self, pos):
        """
        Show the display at the specified position with an expanding animation.
        
        Automatically positions the panel to the left or right of the element button
        based on available screen space.
        
        Args:
            pos (QPoint): Position relative to parent widget
        
        Returns:
            None
        """
        screen_rect = QApplication.primaryScreen().geometry()
        parent_rect = self.parent().rect()
        
        button_global_pos = self.parent_button.mapToGlobal(self.parent_button.rect().topLeft())
        button_rect = QRect(button_global_pos, self.parent_button.size())
        
        ideal_width = 80
        ideal_height = self.sizeHint().height()
        
        relative_x = self.parent_button.x() / parent_rect.width()
        is_right_side = relative_x > 0.5
        
        if is_right_side:
            x = button_rect.left() - ideal_width
        else:
            x = button_rect.right()
            
        if button_rect.bottom() + ideal_height > screen_rect.bottom():
            y = button_rect.top() - ideal_height
        else:
            y = button_rect.top()
            
        pos = self.parent().mapFromGlobal(QPoint(x, y))
        
        self.move(pos)
        self.show()
        self.raise_()
        self.is_visible = True
        
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(100)
        
        if is_right_side:
            start_rect = QRect(pos.x() + ideal_width, pos.y(), 0, ideal_height)
            end_rect = QRect(pos.x(), pos.y(), ideal_width, ideal_height)
        else:
            start_rect = QRect(pos.x(), pos.y(), 0, ideal_height)
            end_rect = QRect(pos.x(), pos.y(), ideal_width, ideal_height)
            
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def mousePressEvent(self, event):
        """
        Handle mouse press events to close display when clicking outside.
        
        Args:
            event (QMouseEvent): Mouse event object
        
        Returns:
            None
        """
        if not self.rect().contains(event.position().toPoint()):
            self.hide_with_animation()
        super().mousePressEvent(event)

    def get_selected_isotopes(self):
        """
        Get list of currently selected isotopes.
        
        Args:
            None
        
        Returns:
            list: List of (symbol, mass) tuples for selected isotopes
        """
        return list(self.selected_isotopes)

    def select_next_available_isotope(self):
        """
        Progressive isotope selection - add the next available isotope.
        
        Selects isotopes in order of increasing mass. When all are selected,
        clears the selection and starts over.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.available_isotopes:
            return
        
        current_selected_count = len([mass for symbol, mass in self.selected_isotopes 
                                    if symbol == self.element_symbol])
        
        if current_selected_count >= len(self.available_isotopes):
            isotopes_to_remove = [(symbol, mass) for symbol, mass in self.selected_isotopes 
                                if symbol == self.element_symbol]
            for isotope_id in isotopes_to_remove:
                self.selected_isotopes.remove(isotope_id)
                
            for mass in self.available_isotopes:
                if mass in self.mass_labels:
                    self.mass_labels[mass].setSelected(False)
            
            if self.parent_button:
                self.parent_button.clear_highlights()
            
            current_selected_count = 0
        
        if current_selected_count < len(self.available_isotopes):
            next_mass = self.available_isotopes[current_selected_count]
            
            if next_mass in self.mass_labels:
                label = self.mass_labels[next_mass]
                identifier = (self.element_symbol, next_mass)
                self.selected_isotopes.add(identifier)
                label.setSelected(True)
                
                element_data = next((e for e in self.parent().get_elements() 
                                   if e['symbol'] == self.element_symbol), None)
                if element_data:
                    isotope_data = next((iso for iso in element_data['isotopes'] 
                                       if isinstance(iso, dict) and iso['mass'] == next_mass), None)
                    abundance = isotope_data['abundance'] if isotope_data else 0
                    
                    if self.parent_button:
                        self.parent_button.set_highlight(abundance, accumulate=True)
                    
                    self.isotope_selected.emit(self.element_symbol, next_mass, abundance)

    def select_all_available_isotopes(self):
        """
        Select all available isotopes for this element at once.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.available_isotopes:
            return
            
        isotopes_to_remove = [(symbol, mass) for symbol, mass in self.selected_isotopes 
                            if symbol == self.element_symbol]
        for isotope_id in isotopes_to_remove:
            self.selected_isotopes.remove(isotope_id)
            
        if self.parent_button:
            self.parent_button.clear_highlights()
        
        for mass in self.available_isotopes:
            if mass in self.mass_labels:
                label = self.mass_labels[mass]
                identifier = (self.element_symbol, mass)
                self.selected_isotopes.add(identifier)
                label.setSelected(True)
                
                element_data = next((e for e in self.parent().get_elements() 
                                   if e['symbol'] == self.element_symbol), None)
                if element_data:
                    isotope_data = next((iso for iso in element_data['isotopes'] 
                                       if isinstance(iso, dict) and iso['mass'] == mass), None)
                    abundance = isotope_data['abundance'] if isotope_data else 0
                    
                    if self.parent_button:
                        self.parent_button.set_highlight(abundance, accumulate=True)
                    
                    self.isotope_selected.emit(self.element_symbol, mass, abundance)

    def select_preferred_isotope(self, mass):
        """
        Select a specific isotope by mass, clearing other selections.
        
        Args:
            mass (float): Mass number of the isotope to select
        
        Returns:
            None
        """
        if mass in self.mass_labels and mass in self.available_isotopes:
            label = self.mass_labels[mass]
            
            isotopes_to_remove = [(symbol, m) for symbol, m in self.selected_isotopes 
                                if symbol == self.element_symbol]
            for isotope_id in isotopes_to_remove:
                self.selected_isotopes.remove(isotope_id)
                if isotope_id[1] in self.mass_labels:
                    self.mass_labels[isotope_id[1]].setSelected(False)
                
            element_data = next((e for e in self.parent().get_elements() 
                               if e['symbol'] == self.element_symbol), None)
            if element_data:
                isotope_data = next((iso for iso in element_data['isotopes'] 
                                   if isinstance(iso, dict) and iso['mass'] == mass), None)
                abundance = isotope_data['abundance'] if isotope_data else 0
            
                identifier = (self.element_symbol, mass)
                self.selected_isotopes.add(identifier)
                
                label.setSelected(True)
                
                if self.parent_button:
                    self.parent_button.set_highlight(abundance, accumulate=False)
                
                self.isotope_selected.emit(self.element_symbol, mass, abundance)

    def on_isotope_clicked(self, label, isotope_mass):
        """
        Handle isotope label click events to toggle selection.
        
        Args:
            label (CompactSelectableIsotopeLabel): The clicked label widget
            isotope_mass (float): Mass number of the clicked isotope
        
        Returns:
            None
        """
        if isotope_mass not in self.available_isotopes:
            return
            
        element_data = next((e for e in self.parent().get_elements() 
                           if e['symbol'] == self.element_symbol), None)
        if element_data:
            isotope_data = next((iso for iso in element_data['isotopes'] 
                               if isinstance(iso, dict) and iso['mass'] == isotope_mass), None)
            abundance = isotope_data['abundance'] if isotope_data else 0
            
            identifier = (self.element_symbol, isotope_mass)
            if identifier in self.selected_isotopes:
                self.selected_isotopes.remove(identifier)
                label.setSelected(False)
                if self.parent_button:
                    self.parent_button.remove_highlight(abundance)
            else:
                self.selected_isotopes.add(identifier)
                label.setSelected(True)
                if self.parent_button:
                    self.parent_button.set_highlight(abundance, accumulate=True)
            
            self.isotope_selected.emit(self.element_symbol, isotope_mass, abundance)

    def clear_selection(self):
        """
        Clear all isotope selections for this element.
        
        Args:
            None
        
        Returns:
            None
        """
        self.selected_isotopes.clear()
        for mass, label in self.mass_labels.items():
            label.setSelected(False)
        if self.parent_button:
            self.parent_button.clear_highlights()


class CompactPeriodicTableWidget(QWidget):
    """
    Interactive periodic table widget with isotope selection capabilities.
    
    Displays a compact periodic table where elements can be clicked to select specific
    isotopes. Elements are color-coded by category and can be enabled/disabled based
    on available isotopes in the data.
    """
    
    element_clicked = Signal(dict)
    isotope_selected = Signal(str, float, float)
    
    def __init__(self, parent=None):
        """
        Initialize the periodic table widget.
        
        Args:
            parent (QWidget): Parent widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent)
        self.buttons = {}
        self.current_element = None
        self.scale_factor = 1.5
        self.available_element_masses = []
        self.initUI()
        
    def initUI(self):
        """
        Initialize the user interface and create element buttons.
        
        Creates the grid layout and populates it with element buttons positioned
        according to standard periodic table layout.
        
        Args:
            None
        
        Returns:
            None
        """
        self.setStyleSheet("background-color: #eeeeee;")
        
        layout = QGridLayout()
        layout.setSpacing(1)
        layout.setContentsMargins(2, 2, 2, 2)
        self.setLayout(layout)

        for element in self.get_elements():
            btn = self.create_element_button(element)
            
            col = element['col']
            row = element['row']
            
            if col > 1:
                col += 10
                
            if element['category'] in ['lanthanide', 'actinide']:
                if element['category'] == 'lanthanide':
                    row = 8
                else:
                    row = 9
            else:
                if col > 12:
                    col += 1
                    
            layout.addWidget(btn, row, col)
            self.buttons[element['symbol']] = btn

    def create_element_button(self, element):
        """
        Create an element button with isotope display and styling.
        
        Args:
            element (dict): Element data dictionary
        
        Returns:
            CompactAnimatedButton: Configured element button widget
        """
        btn = CompactAnimatedButton()
        button_size = int(25 * self.scale_factor)
        btn.setFixedSize(button_size, button_size)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setStyleSheet(self.get_element_style(element))
        btn.setProperty('element_symbol', element['symbol'])
        
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(1, 1, 1, 1)

        symbol = QLabel(element['symbol'])
        symbol.setAlignment(Qt.AlignCenter)
        symbol.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold; background-color: transparent;")

        layout.addWidget(symbol)
        btn.setLayout(layout)
        
        isotope_display = CompactIsotopeDisplay(self)
        isotope_display.set_isotopes(element, self.available_element_masses)
        isotope_display.isotope_selected.connect(
            lambda symbol, mass, abundance: self.on_isotope_selected(element, mass, abundance)
        )
        btn.set_isotope_display(isotope_display)
        
        btn.clicked.connect(lambda: self.on_element_button_clicked(element))
        
        return btn
    
    def on_element_button_clicked(self, element):
        """
        Handle element button click event.
        
        Args:
            element (dict): Element data dictionary
        
        Returns:
            None
        """
        self.element_clicked.emit(element)
        
    def on_isotope_selected(self, element, mass, abundance):
        """
        Handle isotope selection event.
        
        Args:
            element (dict): Element data dictionary
            mass (float): Mass number of selected isotope
            abundance (float): Natural abundance percentage
        
        Returns:
            None
        """
        self.isotope_selected.emit(element['symbol'], mass, abundance)

    def get_element_style(self, element, highlighted=False):
        """
        Get CSS stylesheet for element button based on category and state.
        
        Args:
            element (dict): Element data dictionary
            highlighted (bool): Whether element should be highlighted
        
        Returns:
            str: CSS stylesheet string for the button
        """
        category_colors = {
            'alkali': ('#FF7043', '#FF5722'),
            'alkaline': ('#BA68C8', '#9C27B0'),
            'transition': ('#5C6BC0', '#424B82'),
            'post-transition': ('#66BB6A', '#4CAF50'),
            'metalloid': ('#FFA726', '#FF9800'),
            'other': ('#757575', '#4A4A4A'),
            'halogen': ('#42A5F5', '#2196F3'),
            'noble': ('#8D6E63', '#795548'),
            'lanthanide': ('#26C6DA', '#00BCD4'),
            'actinide': ('#79055c', '#79055c')
        }
        
        base_color, darker_color = category_colors.get(element['category'], ('#424242', '#333333'))
        
        if highlighted:
            base_color = QColor(base_color).lighter(150).name()
            darker_color = QColor(darker_color).lighter(150).name()
            
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {base_color}, stop:1 {darker_color});
                border: 1px solid {darker_color};
                border-radius: 2px;
                padding: 1px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {QColor(base_color).lighter(120).name()}, stop:1 {QColor(darker_color).lighter(120).name()});
                border: 1px solid {QColor(darker_color).lighter(140).name()};
            }}
            QPushButton:disabled {{
                background: #2a2a2a;
                border: 1px solid #333333;
                color: #666666;
            }}
        """

    def update_available_masses(self, available_element_masses):
        """
        Update which elements are available based on detected element-mass pairs.
        
        Supports both new format (element-mass pairs) and legacy format (masses only)
        for backward compatibility.
        
        Args:
            available_element_masses (list): List of tuples (element_symbol, mass) or list of masses
        
        Returns:
            None
        """
        if not available_element_masses:
            return
            
        if isinstance(available_element_masses[0], (int, float)):
            self._update_by_mass_tolerance(available_element_masses)
        else:
            self.available_element_masses = available_element_masses
            self._update_by_element_mass_pairs(available_element_masses)

    def _update_by_element_mass_pairs(self, element_mass_pairs):
        """
        Update availability based on exact element-mass pairs.
        
        Args:
            element_mass_pairs (list): List of (element_symbol, mass) tuples
        
        Returns:
            None
        """
        available_set = set()
        for element_symbol, mass in element_mass_pairs:
            available_set.add((element_symbol, mass))
        
        for symbol, btn in self.buttons.items():
            element = next((e for e in self.get_elements() if e['symbol'] == symbol), None)
            if element:
                has_match = False
                matching_masses = []
                
                for isotope in element['isotopes']:
                    if isinstance(isotope, dict):
                        isotope_mass = isotope['mass']
                    else:
                        isotope_mass = isotope
                        
                    if (symbol, isotope_mass) in available_set:
                        has_match = True
                        matching_masses.append(isotope_mass)
                
                btn.setEnabled(has_match)
                
                if btn.isotope_display:
                    btn.isotope_display.set_isotopes(element, element_mass_pairs)
                
                if has_match:
                    tooltip = (f"{element['name']}\nAvailable isotopes: "
                              f"{', '.join(f'{m:.1f}' for m in matching_masses)}")
                    btn.setStyleSheet(self.get_element_style(element))
                else:
                    tooltip = f"{element['name']} (No matching isotopes)"
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #2a2a2a;
                            border: 1px solid #333333;
                            color: #666666;
                            border-radius: 2px;
                            padding: 1px;
                        }
                    """)
                btn.setToolTip(tooltip)

    def _update_by_mass_tolerance(self, available_masses):
        """
        Update availability based on mass tolerance for backward compatibility.
        
        Uses a tolerance-based matching approach when only masses are provided
        without element symbols.
        
        Args:
            available_masses (list): List of mass numbers
        
        Returns:
            None
        """
        mass_tolerance = 0.1
        
        for symbol, btn in self.buttons.items():
            element = next((e for e in self.get_elements() if e['symbol'] == symbol), None)
            if element:
                element_isotopes = []
                for isotope in element['isotopes']:
                    if isinstance(isotope, dict):
                        element_isotopes.append(isotope['mass'])
                    else:
                        element_isotopes.append(isotope)
                        
                isotope_matches = [mass for mass in available_masses 
                                if any(abs(mass - isotope) < mass_tolerance for isotope in element_isotopes)]
                
                is_available = len(isotope_matches) > 0
                btn.setEnabled(is_available)
                
                if is_available:
                    tooltip = (f"{element['name']}\nAvailable isotopes: "
                              f"{', '.join(f'{m:.1f}' for m in isotope_matches)}")
                    btn.setStyleSheet(self.get_element_style(element))
                else:
                    tooltip = f"{element['name']} (No matching isotopes)"
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #2a2a2a;
                            border: 1px solid #333333;
                            color: #666666;
                            border-radius: 2px;
                            padding: 1px;
                        }
                    """)
                btn.setToolTip(tooltip)

    def get_element_by_symbol(self, symbol):
        """
        Get element data dictionary by symbol.
        
        Args:
            symbol (str): Element symbol (e.g., 'Fe', 'Au')
        
        Returns:
            dict or None: Element data dictionary if found, None otherwise
        """
        return next((e for e in self.get_elements() if e['symbol'] == symbol), None)
    
    def close_all_isotope_displays_except(self, current_button):
        """
        Close all isotope display panels except the one for the current button.
        
        Args:
            current_button (CompactAnimatedButton): Button whose display should remain open
        
        Returns:
            None
        """
        for button in self.buttons.values():
            if button != current_button and button.isotope_display:
                if button.isotope_display.isVisible():
                    button.isotope_display.hide_with_animation()

    def clear_all_highlights(self):
        """
        Clear highlighting from all element buttons.
        
        Args:
            None
        
        Returns:
            None
        """
        for element_symbol, button in self.buttons.items():
            element = self.get_element_by_symbol(element_symbol)
            if element:
                button.setStyleSheet(self.get_element_style(element))
    
    def clear_all_selections(self):
        """
        Clear all isotope selections from all elements.
        
        Resets all buttons to their default state based on availability.
        
        Args:
            None
        
        Returns:
            None
        """
        for button in self.buttons.values():
            if button.isotope_display:
                button.isotope_display.clear_selection()
                button.clear_highlights()
                element = self.get_element_by_symbol(button.property('element_symbol'))
                if element and button.isEnabled():
                    button.setStyleSheet(self.get_element_style(element))

    def get_selected_isotopes(self):
        """
        Get all currently selected isotopes from all elements.
        
        Args:
            None
        
        Returns:
            dict: Dictionary mapping element symbols to lists of selected mass numbers
        """
        selected_data = {}
        
        for symbol, button in self.buttons.items():
            if button.isotope_display and button.isotope_display.selected_isotopes:
                isotopes = []
                for sym, mass in button.isotope_display.selected_isotopes:
                    if sym == symbol:
                        isotopes.append(mass)
                if isotopes:
                    selected_data[symbol] = isotopes
        
        return selected_data


    def get_elements(self):
        """
        Get the periodic table elements data.
        
        Returns a list of dictionaries containing element properties including
        symbol, name, mass, position, isotopes, category, and other properties.
        
        Args:
            None
        
        Returns:
            list: List of element data dictionaries
        """
        return [
            {'symbol': 'H', 'name': 'Hydrogen', 'mass': 1.008, 'row': 0, 'col': 0, 'isotopes': [{'mass': 1.00783, 'abundance': 99.9844, 'label': '1H'}, {'mass': 2.0141, 'abundance': 0.01557, 'label': '2H'}, {'mass': 3.016049, 'abundance': 0, 'label': '3H'}], 'category': 'other', 'atomic_number': 1, 'density': 0.00008988, 'ionization_energy': 13.6},
            {'symbol': 'He', 'name': 'Helium', 'mass': 4.003, 'row': 0, 'col': 17, 'isotopes': [{'mass': 3.01603, 'abundance': 0.00013, 'label': '3He'}, {'mass': 4.0026, 'abundance': 99.9999, 'label': '4He'}], 'category': 'noble', 'atomic_number': 2, 'density': 0.0001785, 'ionization_energy': 24.6},
            
            {'symbol': 'Li', 'name': 'Lithium', 'mass': 6.941, 'row': 1, 'col': 0, 'isotopes': [{'mass': 6.01512, 'abundance': 7.589, 'label': '6Li'}, {'mass': 7.016, 'abundance': 92.411, 'label': '7Li'}], 'category': 'alkali', 'atomic_number': 3, 'density': 0.534, 'ionization_energy': 5.4},
            {'symbol': 'Be', 'name': 'Beryllium', 'mass': 9.012, 'row': 1, 'col': 1, 'isotopes': [{'mass': 9.01218, 'abundance': 100, 'label': '9Be'}], 'category': 'alkaline', 'atomic_number': 4, 'density': 1.85, 'ionization_energy': 9.3},
            {'symbol': 'B', 'name': 'Boron', 'mass': 10.811, 'row': 1, 'col': 12, 'isotopes': [{'mass': 10.01294, 'abundance': 19.82, 'label': '10B'}, {'mass': 11.00931, 'abundance': 80.18, 'label': '11B'}], 'category': 'metalloid', 'atomic_number': 5, 'density': 2.34, 'ionization_energy': 8.3},
            {'symbol': 'C', 'name': 'Carbon', 'mass': 12.011, 'row': 1, 'col': 13, 'isotopes': [{'mass': 12, 'abundance': 98.8922, 'label': '12C'}, {'mass': 13.00335, 'abundance': 1.1078, 'label': '13C'}], 'category': 'other', 'atomic_number': 6, 'density': 2.267, 'ionization_energy': 11.3},
            {'symbol': 'N', 'name': 'Nitrogen', 'mass': 14.007, 'row': 1, 'col': 14, 'isotopes': [{'mass': 14.00307, 'abundance': 99.6337, 'label': '14N'}, {'mass': 15.00011, 'abundance': 0.3663, 'label': '15N'}], 'category': 'other', 'atomic_number': 7, 'density': 0.0012506, 'ionization_energy': 14.5},
            {'symbol': 'O', 'name': 'Oxygen', 'mass': 15.999, 'row': 1, 'col': 15, 'isotopes': [{'mass': 15.99491, 'abundance': 99.7628, 'label': '16O'}, {'mass': 16.99913, 'abundance': 0.0372, 'label': '17O'}, {'mass': 17.99916, 'abundance': 0.20004, 'label': '18O'}], 'category': 'other', 'atomic_number': 8, 'density': 0.001429, 'ionization_energy': 13.6},
            {'symbol': 'F', 'name': 'Fluorine', 'mass': 18.998, 'row': 1, 'col': 16, 'isotopes': [{'mass': 18.9984, 'abundance': 100, 'label': '19F'}], 'category': 'halogen', 'atomic_number': 9, 'density': 0.001696, 'ionization_energy': 17.4},
            {'symbol': 'Ne', 'name': 'Neon', 'mass': 20.180, 'row': 1, 'col': 17, 'isotopes': [{'mass': 19.99244, 'abundance': 90.4838, 'label': '20Ne'}, {'mass': 20.99385, 'abundance': 0.2696, 'label': '21Ne'}, {'mass': 21.99138, 'abundance': 9.2465, 'label': '22Ne'}], 'category': 'noble', 'atomic_number': 10, 'density': 0.0008999, 'ionization_energy': 21.6},

            {'symbol': 'Na', 'name': 'Sodium', 'mass': 22.990, 'row': 2, 'col': 0, 'isotopes': [{'mass': 22.98977, 'abundance': 100, 'label': '23Na'}], 'category': 'alkali', 'atomic_number': 11, 'density': 0.968, 'ionization_energy': 5.14},
            {'symbol': 'Mg', 'name': 'Magnesium', 'mass': 24.305, 'row': 2, 'col': 1, 'isotopes': [{'mass': 23.98505, 'abundance': 78.992, 'label': '24Mg'}, {'mass': 24.98584, 'abundance': 10.003, 'label': '25Mg'}, {'mass': 25.9826, 'abundance': 11.005, 'label': '26Mg'}], 'category': 'alkaline', 'atomic_number': 12, 'density': 1.738, 'ionization_energy': 7.65},
            {'symbol': 'Al', 'name': 'Aluminum', 'mass': 26.982, 'row': 2, 'col': 12, 'isotopes': [{'mass': 26.98154, 'abundance': 100, 'label': '27Al'}], 'category': 'post-transition', 'atomic_number': 13, 'density': 2.70, 'ionization_energy': 5.99},
            {'symbol': 'Si', 'name': 'Silicon', 'mass': 28.086, 'row': 2, 'col': 13, 'isotopes': [{'mass': 27.97693, 'abundance': 92.2297, 'label': '28Si'}, {'mass': 28.97649, 'abundance': 4.6832, 'label': '29Si'}, {'mass': 29.97377, 'abundance': 3.08716, 'label': '30Si'}], 'category': 'metalloid', 'atomic_number': 14, 'density': 2.33, 'ionization_energy': 8.15},
            {'symbol': 'P', 'name': 'Phosphorus', 'mass': 30.974, 'row': 2, 'col': 14, 'isotopes': [{'mass': 30.97376, 'abundance': 100, 'label': '31P'}], 'category': 'other', 'atomic_number': 15, 'density': 1.82, 'ionization_energy': 10.49},
            {'symbol': 'S', 'name': 'Sulfur', 'mass': 32.065, 'row': 2, 'col': 15, 'isotopes': [{'mass': 31.97207, 'abundance': 95.018, 'label': '32S'}, {'mass': 32.97146, 'abundance': 0.75, 'label': '33S'}, {'mass': 33.96787, 'abundance': 4.215, 'label': '34S'}, {'mass': 35.96708, 'abundance': 0.017, 'label': '36S'}], 'category': 'other', 'atomic_number': 16, 'density': 2.067, 'ionization_energy': 10.36},
            {'symbol': 'Cl', 'name': 'Chlorine', 'mass': 35.453, 'row': 2, 'col': 16, 'isotopes': [{'mass': 34.96885, 'abundance': 75.771, 'label': '35Cl'}, {'mass': 36.9659, 'abundance': 24.229, 'label': '37Cl'}], 'category': 'halogen', 'atomic_number': 17, 'density': 0.003214, 'ionization_energy': 12.97},
            {'symbol': 'Ar', 'name': 'Argon', 'mass': 39.948, 'row': 2, 'col': 17, 'isotopes': [{'mass': 35.96755, 'abundance': 0.3365, 'label': '36Ar'}, {'mass': 37.96273, 'abundance': 0.0632, 'label': '38Ar'}, {'mass': 39.96238, 'abundance': 99.6003, 'label': '40Ar'}], 'category': 'noble', 'atomic_number': 18, 'density': 0.001784, 'ionization_energy': 15.76},
            # Period 4
            {'symbol': 'K', 'name': 'Potassium', 'mass': 39.098, 'row': 3, 'col': 0, 'isotopes': [{'mass': 38.96371, 'abundance': 93.2581, 'label': '39K'}, {'mass': 39.964, 'abundance': 0.01167, 'label': '40K'}, {'mass': 40.96183, 'abundance': 6.7302, 'label': '41K'}], 'category': 'alkali', 'atomic_number': 19, 'density': 0.856, 'ionization_energy': 4.34},
            {'symbol': 'Ca', 'name': 'Calcium', 'mass': 40.078, 'row': 3, 'col': 1, 'isotopes': [{'mass': 39.96259, 'abundance': 96.941, 'label': '40Ca'}, {'mass': 41.95862, 'abundance': 0.647, 'label': '42Ca'}, {'mass': 42.95877, 'abundance': 0.135, 'label': '43Ca'}, {'mass': 43.95549, 'abundance': 2.086, 'label': '44Ca'}, {'mass': 45.95369, 'abundance': 0.004, 'label': '46Ca'}, {'mass': 47.95253, 'abundance': 0.187, 'label': '48Ca'}], 'category': 'alkaline', 'atomic_number': 20, 'density': 1.55, 'ionization_energy': 6.11},

            {'symbol': 'Sc', 'name': 'Scandium', 'mass': 44.956, 'row': 3, 'col': 2, 'isotopes': [{'mass': 44.95591, 'abundance': 100, 'label': '45Sc'}], 'category': 'transition', 'atomic_number': 21, 'density': 2.985, 'ionization_energy': 6.56},
            {'symbol': 'Ti', 'name': 'Titanium', 'mass': 47.867, 'row': 3, 'col': 3, 'isotopes': [
                {'mass': 45.95263, 'abundance': 8.249, 'label': '46Ti'},
                {'mass': 46.95177, 'abundance': 7.437, 'label': '47Ti'},
                {'mass': 47.94795, 'abundance': 73.72, 'label': '48Ti'},
                {'mass': 48.94787, 'abundance': 5.409, 'label': '49Ti'},
                {'mass': 49.94479, 'abundance': 5.185, 'label': '50Ti'}
            ], 'category': 'transition', 'atomic_number': 22, 'density': 4.507, 'ionization_energy': 6.83},

            {'symbol': 'V', 'name': 'Vanadium', 'mass': 50.942, 'row': 3, 'col': 4, 'isotopes': [
                {'mass': 49.94716, 'abundance': 0.2497, 'label': '50V'},
                {'mass': 50.94396, 'abundance': 99.7503, 'label': '51V'}
            ], 'category': 'transition', 'atomic_number': 23, 'density': 6.11, 'ionization_energy': 6.75},

            {'symbol': 'Cr', 'name': 'Chromium', 'mass': 51.996, 'row': 3, 'col': 5, 'isotopes': [
                {'mass': 49.94646, 'abundance': 4.3452, 'label': '50Cr'},
                {'mass': 51.94051, 'abundance': 83.7895, 'label': '52Cr'},
                {'mass': 52.94065, 'abundance': 9.5006, 'label': '53Cr'},
                {'mass': 53.93888, 'abundance': 2.3647, 'label': '54Cr'}
            ], 'category': 'transition', 'atomic_number': 24, 'density': 7.14, 'ionization_energy': 6.77},

            {'symbol': 'Mn', 'name': 'Manganese', 'mass': 54.938, 'row': 3, 'col': 6, 'isotopes': [
                {'mass': 54.93805, 'abundance': 100, 'label': '55Mn'}
            ], 'category': 'transition', 'atomic_number': 25, 'density': 7.47, 'ionization_energy': 7.43},

            {'symbol': 'Fe', 'name': 'Iron', 'mass': 55.845, 'row': 3, 'col': 7, 'isotopes': [
                {'mass': 53.93961, 'abundance': 5.845, 'label': '54Fe'},
                {'mass': 55.93494, 'abundance': 91.754, 'label': '56Fe'},
                {'mass': 56.9354, 'abundance': 2.1191, 'label': '57Fe'},
                {'mass': 57.93328, 'abundance': 0.2819, 'label': '58Fe'}
            ], 'category': 'transition', 'atomic_number': 26, 'density': 7.874, 'ionization_energy': 7.90},

            {'symbol': 'Co', 'name': 'Cobalt', 'mass': 58.933, 'row': 3, 'col': 8, 'isotopes': [
                {'mass': 58.9332, 'abundance': 100, 'label': '59Co'}
            ], 'category': 'transition', 'atomic_number': 27, 'density': 8.9, 'ionization_energy': 7.88},

            {'symbol': 'Ni', 'name': 'Nickel', 'mass': 58.693, 'row': 3, 'col': 9, 'isotopes': [
                {'mass': 57.93535, 'abundance': 68.0769, 'label': '58Ni'},
                {'mass': 59.93079, 'abundance': 26.2231, 'label': '60Ni'},
                {'mass': 60.93106, 'abundance': 1.1399, 'label': '61Ni'},
                {'mass': 61.92835, 'abundance': 3.6345, 'label': '62Ni'},
                {'mass': 63.92797, 'abundance': 0.9256, 'label': '64Ni'}
            ], 'category': 'transition', 'atomic_number': 28, 'density': 8.908, 'ionization_energy': 7.64},

            {'symbol': 'Cu', 'name': 'Copper', 'mass': 63.546, 'row': 3, 'col': 10, 'isotopes': [
                {'mass': 62.9296, 'abundance': 69.174, 'label': '63Cu'},
                {'mass': 64.92779, 'abundance': 30.826, 'label': '65Cu'}
            ], 'category': 'transition', 'atomic_number': 29, 'density': 8.96, 'ionization_energy': 7.73},

            {'symbol': 'Zn', 'name': 'Zinc', 'mass': 65.38, 'row': 3, 'col': 11, 'isotopes': [
                {'mass': 63.92915, 'abundance': 48.63, 'label': '64Zn'},
                {'mass': 65.92604, 'abundance': 27.9, 'label': '66Zn'},
                {'mass': 66.92713, 'abundance': 4.1, 'label': '67Zn'},
                {'mass': 67.92485, 'abundance': 18.75, 'label': '68Zn'},
                {'mass': 69.92532, 'abundance': 0.62, 'label': '70Zn'}
            ], 'category': 'transition', 'atomic_number': 30, 'density': 7.14, 'ionization_energy': 9.39},
            {'symbol': 'Ga', 'name': 'Gallium', 'mass': 69.723, 'row': 3, 'col': 12, 'isotopes': [
                {'mass': 68.92558, 'abundance': 60.1079, 'label': '69Ga'},
                {'mass': 70.9247, 'abundance': 39.8921, 'label': '71Ga'}
            ], 'category': 'post-transition', 'atomic_number': 31, 'density': 5.904, 'ionization_energy': 5.99},

            {'symbol': 'Ge', 'name': 'Germanium', 'mass': 72.63, 'row': 3, 'col': 13, 'isotopes': [
                {'mass': 69.92425, 'abundance': 21.234, 'label': '70Ge'},
                {'mass': 71.92208, 'abundance': 27.662, 'label': '72Ge'},
                {'mass': 72.92346, 'abundance': 7.717, 'label': '73Ge'},
                {'mass': 73.92118, 'abundance': 35.943, 'label': '74Ge'},
                {'mass': 75.9214, 'abundance': 7.444, 'label': '76Ge'}
            ], 'category': 'metalloid', 'atomic_number': 32, 'density': 5.323, 'ionization_energy': 7.90},

            {'symbol': 'As', 'name': 'Arsenic', 'mass': 74.922, 'row': 3, 'col': 14, 'isotopes': [
                {'mass': 74.9216, 'abundance': 100, 'label': '75As'}
            ], 'category': 'metalloid', 'atomic_number': 33, 'density': 5.727, 'ionization_energy': 9.79},

            {'symbol': 'Se', 'name': 'Selenium', 'mass': 78.971, 'row': 3, 'col': 15, 'isotopes': [
                {'mass': 73.92248, 'abundance': 0.889, 'label': '74Se'},
                {'mass': 75.91921, 'abundance': 9.366, 'label': '76Se'},
                {'mass': 76.91991, 'abundance': 7.635, 'label': '77Se'},
                {'mass': 77.91773, 'abundance': 23.772, 'label': '78Se'},
                {'mass': 79.91652, 'abundance': 49.607, 'label': '80Se'},
                {'mass': 81.91671, 'abundance': 8.731, 'label': '82Se'}
            ], 'category': 'other', 'atomic_number': 34, 'density': 4.819, 'ionization_energy': 9.75},

            {'symbol': 'Br', 'name': 'Bromine', 'mass': 79.904, 'row': 3, 'col': 16, 'isotopes': [
                {'mass': 78.91834, 'abundance': 50.686, 'label': '79Br'},
                {'mass': 80.91629, 'abundance': 49.314, 'label': '81Br'}
            ], 'category': 'halogen', 'atomic_number': 35, 'density': 3.12, 'ionization_energy': 11.81},

            {'symbol': 'Kr', 'name': 'Krypton', 'mass': 83.798, 'row': 3, 'col': 17, 'isotopes': [
                {'mass': 77.9204, 'abundance': 0.35351, 'label': '78Kr'},
                {'mass': 79.91638, 'abundance': 2.28086, 'label': '80Kr'},
                {'mass': 81.91348, 'abundance': 11.583, 'label': '82Kr'},
                {'mass': 82.91413, 'abundance': 11.4953, 'label': '83Kr'},
                {'mass': 83.91151, 'abundance': 56.9889, 'label': '84Kr'},
                {'mass': 85.91061, 'abundance': 17.2984, 'label': '86Kr'}
            ], 'category': 'noble', 'atomic_number': 36, 'density': 0.003733, 'ionization_energy': 14.00},

            {'symbol': 'Rb', 'name': 'Rubidium', 'mass': 85.468, 'row': 4, 'col': 0, 'isotopes': [
                {'mass': 84.9118, 'abundance': 72.1654, 'label': '85Rb'},
                {'mass': 86.90918, 'abundance': 27.8346, 'label': '87Rb'}
            ], 'category': 'alkali', 'atomic_number': 37, 'density': 1.532, 'ionization_energy': 4.18},

            {'symbol': 'Sr', 'name': 'Strontium', 'mass': 87.62, 'row': 4, 'col': 1, 'isotopes': [
                {'mass': 83.91343, 'abundance': 0.5574, 'label': '84Sr'},
                {'mass': 85.90927, 'abundance': 9.8566, 'label': '86Sr'},
                {'mass': 86.90889, 'abundance': 7.0015, 'label': '87Sr'},
                {'mass': 87.90562, 'abundance': 82.5845, 'label': '88Sr'}
            ], 'category': 'alkaline', 'atomic_number': 38, 'density': 2.64, 'ionization_energy': 5.69},

            {'symbol': 'Y', 'name': 'Yttrium', 'mass': 88.906, 'row': 4, 'col': 2, 'isotopes': [
                {'mass': 88.90586, 'abundance': 100, 'label': '89Y'}
            ], 'category': 'transition', 'atomic_number': 39, 'density': 4.47, 'ionization_energy': 6.22},
            {'symbol': 'Zr', 'name': 'Zirconium', 'mass': 91.224, 'row': 4, 'col': 3, 'isotopes': [
                {'mass': 89.90471, 'abundance': 51.452, 'label': '90Zr'},
                {'mass': 90.90564, 'abundance': 11.223, 'label': '91Zr'},
                {'mass': 91.90504, 'abundance': 17.146, 'label': '92Zr'},
                {'mass': 93.90632, 'abundance': 17.38, 'label': '94Zr'},
                {'mass': 95.90827, 'abundance': 2.799, 'label': '96Zr'}
            ], 'category': 'transition', 'atomic_number': 40, 'density': 6.51, 'ionization_energy': 6.63},

            {'symbol': 'Nb', 'name': 'Niobium', 'mass': 92.906, 'row': 4, 'col': 4, 'isotopes': [
                {'mass': 92.90638, 'abundance': 100, 'label': '93Nb'}
            ], 'category': 'transition', 'atomic_number': 41, 'density': 8.57, 'ionization_energy': 6.76},

            {'symbol': 'Mo', 'name': 'Molybdenum', 'mass': 95.95, 'row': 4, 'col': 5, 'isotopes': [
                {'mass': 91.90681, 'abundance': 14.8362, 'label': '92Mo'},
                {'mass': 93.90509, 'abundance': 9.2466, 'label': '94Mo'},
                {'mass': 94.90584, 'abundance': 15.9201, 'label': '95Mo'},
                {'mass': 95.90468, 'abundance': 16.6756, 'label': '96Mo'},
                {'mass': 96.90602, 'abundance': 9.5551, 'label': '97Mo'},
                {'mass': 97.90541, 'abundance': 24.1329, 'label': '98Mo'},
                {'mass': 99.90747, 'abundance': 9.6335, 'label': '100Mo'}
            ], 'category': 'transition', 'atomic_number': 42, 'density': 10.22, 'ionization_energy': 7.09},

            {'symbol': 'Tc', 'name': 'Technetium', 'mass': 98, 'row': 4, 'col': 6, 'isotopes': [
                {'mass': 99, 'abundance': 100, 'label': '99Tc'}
            ], 'category': 'transition', 'atomic_number': 43, 'density': 11.5, 'ionization_energy': 7.28},

            {'symbol': 'Ru', 'name': 'Ruthenium', 'mass': 101.07, 'row': 4, 'col': 7, 'isotopes': [
                {'mass': 95.9076, 'abundance': 5.542, 'label': '96Ru'},
                {'mass': 97.90529, 'abundance': 1.8688, 'label': '98Ru'},
                {'mass': 98.90594, 'abundance': 12.7579, 'label': '99Ru'},
                {'mass': 99.90422, 'abundance': 12.5985, 'label': '100Ru'},
                {'mass': 100.90558, 'abundance': 17.06, 'label': '101Ru'},
                {'mass': 101.90435, 'abundance': 31.5519, 'label': '102Ru'},
                {'mass': 103.90542, 'abundance': 18.621, 'label': '104Ru'}
            ], 'category': 'transition', 'atomic_number': 44, 'density': 12.37, 'ionization_energy': 7.36},

            {'symbol': 'Rh', 'name': 'Rhodium', 'mass': 102.906, 'row': 4, 'col': 8, 'isotopes': [
                {'mass': 102.9055, 'abundance': 100, 'label': '103Rh'}
            ], 'category': 'transition', 'atomic_number': 45, 'density': 12.41, 'ionization_energy': 7.46},

            {'symbol': 'Pd', 'name': 'Palladium', 'mass': 106.42, 'row': 4, 'col': 9, 'isotopes': [
                {'mass': 101.90561, 'abundance': 1.02, 'label': '102Pd'},
                {'mass': 103.90403, 'abundance': 11.14, 'label': '104Pd'},
                {'mass': 104.90508, 'abundance': 22.33, 'label': '105Pd'},
                {'mass': 105.90348, 'abundance': 27.33, 'label': '106Pd'},
                {'mass': 107.90389, 'abundance': 26.46, 'label': '108Pd'},
                {'mass': 109.90517, 'abundance': 11.72, 'label': '110Pd'}
            ], 'category': 'transition', 'atomic_number': 46, 'density': 12.02, 'ionization_energy': 8.34},

            {'symbol': 'Ag', 'name': 'Silver', 'mass': 107.868, 'row': 4, 'col': 10, 'isotopes': [
                {'mass': 106.9051, 'abundance': 51.8392, 'label': '107Ag'},
                {'mass': 108.90475, 'abundance': 48.1608, 'label': '109Ag'}
            ], 'category': 'transition', 'atomic_number': 47, 'density': 10.5, 'ionization_energy': 7.58},



            {'symbol': 'Cd', 'name': 'Cadmium', 'mass': 112.414, 'row': 4, 'col': 11, 'isotopes': [
                {'mass': 105.90646, 'abundance': 1.25, 'label': '106Cd'},
                {'mass': 107.90419, 'abundance': 0.89, 'label': '108Cd'},
                {'mass': 109.90301, 'abundance': 12.49, 'label': '110Cd'},
                {'mass': 110.90418, 'abundance': 12.8, 'label': '111Cd'},
                {'mass': 111.90276, 'abundance': 24.13, 'label': '112Cd'},
                {'mass': 112.9044, 'abundance': 12.22, 'label': '113Cd'},
                {'mass': 113.90336, 'abundance': 28.73, 'label': '114Cd'},
                {'mass': 115.90476, 'abundance': 7.49, 'label': '116Cd'}
            ], 'category': 'transition', 'atomic_number': 48, 'density': 8.65, 'ionization_energy': 8.99},

            {'symbol': 'In', 'name': 'Indium', 'mass': 114.818, 'row': 4, 'col': 12, 'isotopes': [
                {'mass': 112.90406, 'abundance': 4.288, 'label': '113In'},
                {'mass': 114.90388, 'abundance': 95.712, 'label': '115In'}
            ], 'category': 'post-transition', 'atomic_number': 49, 'density': 7.31, 'ionization_energy': 5.79},

            {'symbol': 'Sn', 'name': 'Tin', 'mass': 118.71, 'row': 4, 'col': 13, 'isotopes': [
                {'mass': 111.90482, 'abundance': 0.973, 'label': '112Sn'},
                {'mass': 113.90278, 'abundance': 0.659, 'label': '114Sn'},
                {'mass': 114.90334, 'abundance': 0.339, 'label': '115Sn'},
                {'mass': 115.90174, 'abundance': 14.536, 'label': '116Sn'},
                {'mass': 116.90295, 'abundance': 7.676, 'label': '117Sn'},
                {'mass': 117.90161, 'abundance': 24.223, 'label': '118Sn'},
                {'mass': 118.90331, 'abundance': 8.585, 'label': '119Sn'},
                {'mass': 119.9022, 'abundance': 32.593, 'label': '120Sn'},
                {'mass': 121.90344, 'abundance': 4.629, 'label': '122Sn'},
                {'mass': 123.90527, 'abundance': 5.789, 'label': '124Sn'}
            ], 'category': 'post-transition', 'atomic_number': 50, 'density': 7.31, 'ionization_energy': 7.34},

            {'symbol': 'Sb', 'name': 'Antimony', 'mass': 121.76, 'row': 4, 'col': 14, 'isotopes': [
                {'mass': 120.90382, 'abundance': 57.213, 'label': '121Sb'},
                {'mass': 122.90422, 'abundance': 42.787, 'label': '123Sb'}
            ], 'category': 'metalloid', 'atomic_number': 51, 'density': 6.697, 'ionization_energy': 8.64},

            {'symbol': 'Te', 'name': 'Tellurium', 'mass': 127.6, 'row': 4, 'col': 15, 'isotopes': [
                {'mass': 119.90402, 'abundance': 0.096, 'label': '120Te'},
                {'mass': 121.90306, 'abundance': 2.603, 'label': '122Te'},
                {'mass': 122.90428, 'abundance': 0.908, 'label': '123Te'},
                {'mass': 123.90283, 'abundance': 4.816, 'label': '124Te'},
                {'mass': 124.90444, 'abundance': 7.139, 'label': '125Te'},
                {'mass': 125.90331, 'abundance': 18.952, 'label': '126Te'},
                {'mass': 127.90446, 'abundance': 31.687, 'label': '128Te'},
                {'mass': 129.90623, 'abundance': 33.799, 'label': '130Te'}
            ], 'category': 'metalloid', 'atomic_number': 52, 'density': 6.24, 'ionization_energy': 9.01},

            {'symbol': 'I', 'name': 'Iodine', 'mass': 126.904, 'row': 4, 'col': 16, 'isotopes': [
                {'mass': 126.90448, 'abundance': 100, 'label': '127I'}
            ], 'category': 'halogen', 'atomic_number': 53, 'density': 4.94, 'ionization_energy': 10.45},

            {'symbol': 'Xe', 'name': 'Xenon', 'mass': 131.293, 'row': 4, 'col': 17, 'isotopes': [
                {'mass': 123.90612, 'abundance': 0.08913, 'label': '124Xe'},
                {'mass': 125.90428, 'abundance': 0.0888, 'label': '126Xe'},
                {'mass': 127.90353, 'abundance': 1.91732, 'label': '128Xe'},
                {'mass': 128.90478, 'abundance': 26.4396, 'label': '129Xe'},
                {'mass': 129.90351, 'abundance': 4.08271, 'label': '130Xe'},
                {'mass': 130.90508, 'abundance': 21.1796, 'label': '131Xe'},
                {'mass': 131.90415, 'abundance': 26.8916, 'label': '132Xe'},
                {'mass': 133.9054, 'abundance': 10.4423, 'label': '134Xe'},
                {'mass': 135.90722, 'abundance': 8.8689, 'label': '136Xe'}
            ], 'category': 'noble', 'atomic_number': 54, 'density': 0.005887, 'ionization_energy': 12.13},

            {'symbol': 'Cs', 'name': 'Cesium', 'mass': 132.905, 'row': 5, 'col': 0, 'isotopes': [
                {'mass': 132.90543, 'abundance': 100, 'label': '133Cs'}
            ], 'category': 'alkali', 'atomic_number': 55, 'density': 1.93, 'ionization_energy': 3.89},

            {'symbol': 'Ba', 'name': 'Barium', 'mass': 137.327, 'row': 5, 'col': 1, 'isotopes': [
                {'mass': 129.90628, 'abundance': 0.1058, 'label': '130Ba'},
                {'mass': 131.90504, 'abundance': 0.1012, 'label': '132Ba'},
                {'mass': 133.90449, 'abundance': 2.417, 'label': '134Ba'},
                {'mass': 134.90567, 'abundance': 6.592, 'label': '135Ba'},
                {'mass': 135.90456, 'abundance': 7.853, 'label': '136Ba'},
                {'mass': 136.90582, 'abundance': 11.232, 'label': '137Ba'},
                {'mass': 137.90524, 'abundance': 71.699, 'label': '138Ba'}
            ], 'category': 'alkaline', 'atomic_number': 56, 'density': 3.51, 'ionization_energy': 5.21},

            {'symbol': 'La', 'name': 'Lanthanum', 'mass': 138.905, 'row': 5, 'col': 2, 'isotopes': [
                {'mass': 137.90711, 'abundance': 0.09017, 'label': '138La'},
                {'mass': 138.90636, 'abundance': 99.9098, 'label': '139La'}
            ], 'category': 'lanthanide', 'atomic_number': 57, 'density': 6.146, 'ionization_energy': 5.58},

            {'symbol': 'Ce', 'name': 'Cerium', 'mass': 140.116, 'row': 8, 'col': 3, 'isotopes': [
                {'mass': 135.90714, 'abundance': 0.186, 'label': '136Ce'},
                {'mass': 137.906, 'abundance': 0.251, 'label': '138Ce'},
                {'mass': 139.90544, 'abundance': 88.449, 'label': '140Ce'},
                {'mass': 141.90925, 'abundance': 11.114, 'label': '142Ce'}
            ], 'category': 'lanthanide', 'atomic_number': 58, 'density': 6.689, 'ionization_energy': 5.54},

            {'symbol': 'Pr', 'name': 'Praseodymium', 'mass': 140.908, 'row': 8, 'col': 4, 'isotopes': [
                {'mass': 140.90766, 'abundance': 100, 'label': '141Pr'}
            ], 'category': 'lanthanide', 'atomic_number': 59, 'density': 6.64, 'ionization_energy': 5.47},

            {'symbol': 'Nd', 'name': 'Neodymium', 'mass': 144.242, 'row': 8, 'col': 5, 'isotopes': [
                {'mass': 141.90773, 'abundance': 27.16, 'label': '142Nd'},
                {'mass': 142.90982, 'abundance': 12.18, 'label': '143Nd'},
                {'mass': 143.9101, 'abundance': 23.83, 'label': '144Nd'},
                {'mass': 144.91258, 'abundance': 8.3, 'label': '145Nd'},
                {'mass': 145.91313, 'abundance': 17.17, 'label': '146Nd'},
                {'mass': 147.9169, 'abundance': 5.74, 'label': '148Nd'},
                {'mass': 149.9209, 'abundance': 5.62, 'label': '150Nd'}
            ], 'category': 'lanthanide', 'atomic_number': 60, 'density': 7.01, 'ionization_energy': 5.53},
            
            {'symbol': 'Pm', 'name': 'Promethium', 'mass': 145, 'row': 8, 'col': 6, 'isotopes': [
                {'mass': 144.913, 'abundance': 0, 'label': '145Pm'},  
                {'mass': 145.915, 'abundance': 0, 'label': '146Pm'}  
            ], 'category': 'lanthanide', 'atomic_number': 61, 'density': 7.26, 'ionization_energy': 5.58},

            {'symbol': 'Sm', 'name': 'Samarium', 'mass': 150.36, 'row': 8, 'col': 7, 'isotopes': [
                {'mass': 143.91201, 'abundance': 3.0734, 'label': '144Sm'},
                {'mass': 146.91491, 'abundance': 14.9934, 'label': '147Sm'},
                {'mass': 147.91483, 'abundance': 11.2406, 'label': '148Sm'},
                {'mass': 148.91719, 'abundance': 13.8189, 'label': '149Sm'},
                {'mass': 149.91729, 'abundance': 7.3796, 'label': '150Sm'},
                {'mass': 151.91974, 'abundance': 26.7421, 'label': '152Sm'},
                {'mass': 153.92222, 'abundance': 22.752, 'label': '154Sm'}
            ], 'category': 'lanthanide', 'atomic_number': 62, 'density': 7.52, 'ionization_energy': 5.64},

            {'symbol': 'Eu', 'name': 'Europium', 'mass': 151.964, 'row': 8, 'col': 8, 'isotopes': [
                {'mass': 150.91986, 'abundance': 47.81, 'label': '151Eu'},
                {'mass': 152.92124, 'abundance': 52.19, 'label': '153Eu'}
            ], 'category': 'lanthanide', 'atomic_number': 63, 'density': 5.244, 'ionization_energy': 5.67},

            {'symbol': 'Gd', 'name': 'Gadolinium', 'mass': 157.25, 'row': 8, 'col': 9, 'isotopes': [
                {'mass': 151.9198, 'abundance': 0.2029, 'label': '152Gd'},
                {'mass': 153.92088, 'abundance': 2.1809, 'label': '154Gd'},
                {'mass': 154.92263, 'abundance': 14.7998, 'label': '155Gd'},
                {'mass': 155.92213, 'abundance': 20.4664, 'label': '156Gd'},
                {'mass': 156.92397, 'abundance': 15.6518, 'label': '157Gd'},
                {'mass': 157.92411, 'abundance': 24.8347, 'label': '158Gd'},
                {'mass': 159.92706, 'abundance': 21.8635, 'label': '160Gd'}
            ], 'category': 'lanthanide', 'atomic_number': 64, 'density': 7.895, 'ionization_energy': 6.15},
            
            
            {'symbol': 'Tb', 'name': 'Terbium', 'mass': 158.925, 'row': 8, 'col': 10, 'isotopes': [
            {'mass': 158.92535, 'abundance': 100, 'label': '159Tb'}
            ], 'category': 'lanthanide', 'atomic_number': 65, 'density': 8.229, 'ionization_energy': 5.86},

            {'symbol': 'Dy', 'name': 'Dysprosium', 'mass': 162.5, 'row': 8, 'col': 11, 'isotopes': [
            {'mass': 155.92429, 'abundance': 0.056, 'label': '156Dy'},
            {'mass': 157.92441, 'abundance': 0.096, 'label': '158Dy'},
            {'mass': 159.9252, 'abundance': 2.34, 'label': '160Dy'},
            {'mass': 160.92694, 'abundance': 18.91, 'label': '161Dy'},
            {'mass': 161.92681, 'abundance': 25.51, 'label': '162Dy'},
            {'mass': 162.92874, 'abundance': 24.9, 'label': '163Dy'},
            {'mass': 163.92918, 'abundance': 28.19, 'label': '164Dy'}
            ], 'category': 'lanthanide', 'atomic_number': 66, 'density': 8.55, 'ionization_energy': 5.94},

            {'symbol': 'Ho', 'name': 'Holmium', 'mass': 164.93, 'row': 8, 'col': 12, 'isotopes': [
            {'mass': 164.93033, 'abundance': 100, 'label': '165Ho'}
            ], 'category': 'lanthanide', 'atomic_number': 67, 'density': 8.795, 'ionization_energy': 6.02},

            {'symbol': 'Er', 'name': 'Erbium', 'mass': 167.259, 'row': 8, 'col': 13, 'isotopes': [
            {'mass': 161.92879, 'abundance': 0.137, 'label': '162Er'},
            {'mass': 163.92921, 'abundance': 1.609, 'label': '164Er'},
            {'mass': 165.93035, 'abundance': 33.61, 'label': '166Er'},
            {'mass': 166.93206, 'abundance': 22.93, 'label': '167Er'},
            {'mass': 167.93238, 'abundance': 26.79, 'label': '168Er'},
            {'mass': 169.93548, 'abundance': 14.93, 'label': '170Er'}
            ], 'category': 'lanthanide', 'atomic_number': 68, 'density': 9.066, 'ionization_energy': 6.11},

            {'symbol': 'Tm', 'name': 'Thulium', 'mass': 168.934, 'row': 8, 'col': 14, 'isotopes': [
            {'mass': 168.93426, 'abundance': 100, 'label': '169Tm'}
            ], 'category': 'lanthanide', 'atomic_number': 69, 'density': 9.321, 'ionization_energy': 6.18},

            {'symbol': 'Yb', 'name': 'Ytterbium', 'mass': 173.054, 'row': 8, 'col': 15, 'isotopes': [
            {'mass': 167.93391, 'abundance': 0.127, 'label': '168Yb'},
            {'mass': 169.93477, 'abundance': 3.04, 'label': '170Yb'},
            {'mass': 170.93634, 'abundance': 14.28, 'label': '171Yb'},
            {'mass': 171.93639, 'abundance': 21.83, 'label': '172Yb'},
            {'mass': 172.93822, 'abundance': 16.13, 'label': '173Yb'},
            {'mass': 173.93887, 'abundance': 31.83, 'label': '174Yb'},
            {'mass': 175.94258, 'abundance': 12.76, 'label': '176Yb'}
            ], 'category': 'lanthanide', 'atomic_number': 70, 'density': 6.965, 'ionization_energy': 6.25},

            {'symbol': 'Lu', 'name': 'Lutetium', 'mass': 174.967, 'row': 8, 'col': 16, 'isotopes': [
            {'mass': 174.94079, 'abundance': 97.416, 'label': '175Lu'},
            {'mass': 175.94269, 'abundance': 2.584, 'label': '176Lu'}
            ], 'category': 'lanthanide', 'atomic_number': 71, 'density': 9.84, 'ionization_energy': 5.43},

            {'symbol': 'Hf', 'name': 'Hafnium', 'mass': 178.49, 'row': 5, 'col': 3, 'isotopes': [
            {'mass': 173.94007, 'abundance': 0.162, 'label': '174Hf'},
            {'mass': 175.94142, 'abundance': 5.2604, 'label': '176Hf'},
            {'mass': 176.94323, 'abundance': 18.5953, 'label': '177Hf'},
            {'mass': 177.94371, 'abundance': 27.2811, 'label': '178Hf'},
            {'mass': 178.94583, 'abundance': 13.621, 'label': '179Hf'},
            {'mass': 179.94656, 'abundance': 35.0802, 'label': '180Hf'}
            ], 'category': 'transition', 'atomic_number': 72, 'density': 13.31, 'ionization_energy': 6.83},

            {'symbol': 'Ta', 'name': 'Tantalum', 'mass': 180.948, 'row': 5, 'col': 4, 'isotopes': [
            {'mass': 179.94749, 'abundance': 0.0123, 'label': '180Ta'},
            {'mass': 180.94801, 'abundance': 99.9877, 'label': '181Ta'}
            ], 'category': 'transition', 'atomic_number': 73, 'density': 16.654, 'ionization_energy': 7.55},
            {'symbol': 'W', 'name': 'Tungsten', 'mass': 183.84, 'row': 5, 'col': 5, 'isotopes': [
            {'mass': 179.94673, 'abundance': 0.1198, 'label': '180W'},
            {'mass': 181.94823, 'abundance': 26.4985, 'label': '182W'},
            {'mass': 182.95025, 'abundance': 14.3136, 'label': '183W'},
            {'mass': 183.95095, 'abundance': 30.6422, 'label': '184W'},
            {'mass': 185.95438, 'abundance': 28.4259, 'label': '186W'}
            ], 'category': 'transition', 'atomic_number': 74, 'density': 19.3, 'ionization_energy': 7.86},

            {'symbol': 'Re', 'name': 'Rhenium', 'mass': 186.207, 'row': 5, 'col': 6, 'isotopes': [
            {'mass': 184.95298, 'abundance': 37.398, 'label': '185Re'},
            {'mass': 186.95577, 'abundance': 62.602, 'label': '187Re'}
            ], 'category': 'transition', 'atomic_number': 75, 'density': 21.02, 'ionization_energy': 7.83},

            {'symbol': 'Os', 'name': 'Osmium', 'mass': 190.23, 'row': 5, 'col': 7, 'isotopes': [
            {'mass': 183.95251, 'abundance': 0.0197, 'label': '184Os'},
            {'mass': 185.95385, 'abundance': 1.5859, 'label': '186Os'},
            {'mass': 186.95576, 'abundance': 1.9644, 'label': '187Os'},
            {'mass': 187.95585, 'abundance': 13.2434, 'label': '188Os'},
            {'mass': 188.95816, 'abundance': 16.1466, 'label': '189Os'},
            {'mass': 189.95846, 'abundance': 26.2584, 'label': '190Os'},
            {'mass': 191.96149, 'abundance': 40.7815, 'label': '192Os'}
            ], 'category': 'transition', 'atomic_number': 76, 'density': 22.59, 'ionization_energy': 8.44},

            {'symbol': 'Ir', 'name': 'Iridium', 'mass': 192.217, 'row': 5, 'col': 8, 'isotopes': [
            {'mass': 190.9606, 'abundance': 37.272, 'label': '191Ir'},
            {'mass': 192.96294, 'abundance': 62.728, 'label': '193Ir'}
            ], 'category': 'transition', 'atomic_number': 77, 'density': 22.56, 'ionization_energy': 8.97},

            {'symbol': 'Pt', 'name': 'Platinum', 'mass': 195.084, 'row': 5, 'col': 9, 'isotopes': [
            {'mass': 189.95994, 'abundance': 0.01363, 'label': '190Pt'},
            {'mass': 191.96105, 'abundance': 0.78266, 'label': '192Pt'},
            {'mass': 193.96268, 'abundance': 32.967, 'label': '194Pt'},
            {'mass': 194.96479, 'abundance': 33.8316, 'label': '195Pt'},
            {'mass': 195.96495, 'abundance': 25.2417, 'label': '196Pt'},
            {'mass': 197.96788, 'abundance': 7.16349, 'label': '198Pt'}
            ], 'category': 'transition', 'atomic_number': 78, 'density': 21.45, 'ionization_energy': 8.96},

            {'symbol': 'Au', 'name': 'Gold', 'mass': 196.967, 'row': 5, 'col': 10, 'isotopes': [
            {'mass': 196.96656, 'abundance': 100, 'label': '197Au'}
            ], 'category': 'transition', 'atomic_number': 79, 'density': 19.3, 'ionization_energy': 9.23},

            {'symbol': 'Hg', 'name': 'Mercury', 'mass': 200.592, 'row': 5, 'col': 11, 'isotopes': [
            {'mass': 195.96581, 'abundance': 0.15344, 'label': '196Hg'},
            {'mass': 197.96676, 'abundance': 9.968, 'label': '198Hg'},
            {'mass': 198.96827, 'abundance': 16.873, 'label': '199Hg'},
            {'mass': 199.96832, 'abundance': 23.096, 'label': '200Hg'},
            {'mass': 200.97029, 'abundance': 13.181, 'label': '201Hg'},
            {'mass': 201.97063, 'abundance': 29.863, 'label': '202Hg'},
            {'mass': 203.97348, 'abundance': 6.865, 'label': '204Hg'}
            ], 'category': 'transition', 'atomic_number': 80, 'density': 13.534, 'ionization_energy': 10.44},

            {'symbol': 'Tl', 'name': 'Thallium', 'mass': 204.38, 'row': 5, 'col': 12, 'isotopes': [
            {'mass': 202.97234, 'abundance': 29.524, 'label': '203Tl'},
            {'mass': 204.97441, 'abundance': 70.476, 'label': '205Tl'}
            ], 'category': 'post-transition', 'atomic_number': 81, 'density': 11.85, 'ionization_energy': 6.11},


                        {'symbol': 'Pb', 'name': 'Lead', 'mass': 207.2, 'row': 5, 'col': 13, 'isotopes': [
            {'mass': 203.97304, 'abundance': 1.4245, 'label': '204Pb'},
            {'mass': 205.97446, 'abundance': 24.1447, 'label': '206Pb'},
            {'mass': 206.97589, 'abundance': 22.0827, 'label': '207Pb'},
            {'mass': 207.97604, 'abundance': 52.3481, 'label': '208Pb'}
            ], 'category': 'post-transition', 'atomic_number': 82, 'density': 11.34, 'ionization_energy': 7.42},
                        {'symbol': 'Bi', 'name': 'Bismuth', 'mass': 208.98, 'row': 5, 'col': 14, 'isotopes': [
            {'mass': 208.98039, 'abundance': 100, 'label': '209Bi'}
            ], 'category': 'post-transition', 'atomic_number': 83, 'density': 9.78, 'ionization_energy': 7.29},
                        
                        {'symbol': 'Th', 'name': 'Thorium', 'mass': 232.038, 'row': 9, 'col': 3, 'isotopes': [
            {'mass': 232.03805, 'abundance': 100, 'label': '232Th'}
            ], 'category': 'actinide', 'atomic_number': 90, 'density': 11.72, 'ionization_energy': 6.31},

            {'symbol': 'U', 'name': 'Uranium', 'mass': 238.029, 'row': 9, 'col': 5, 'isotopes': [
            {'mass': 233.0396, 'abundance': 0, 'label': '233U'},
            {'mass': 234.04095, 'abundance': 0.00548, 'label': '234U'},
            {'mass': 235.04393, 'abundance': 0.72, 'label': '235U'},
            {'mass': 236.0456, 'abundance': 0, 'label': '236U'},
            {'mass': 237.05, 'abundance': 0, 'label': '237U'},
            {'mass': 238.05079, 'abundance': 99.2745, 'label': '238U'}
            ], 'category': 'actinide', 'atomic_number': 92, 'density': 19.1, 'ionization_energy': 6.19},

            {'symbol': 'Np', 'name': 'Neptunium', 'mass': 237, 'row': 9, 'col': 6, 'isotopes': [
            {'mass': 237.048004, 'abundance': 100, 'label': '237Np'}
            ], 'category': 'actinide', 'atomic_number': 93, 'density': 20.45, 'ionization_energy': 6.27},

            {'symbol': 'Pu', 'name': 'Plutonium', 'mass': 244, 'row': 9, 'col': 7, 'isotopes': [
            {'mass': 239.0522, 'abundance': 100, 'label': '239Pu'}
            ], 'category': 'actinide', 'atomic_number': 94, 'density': 19.84, 'ionization_energy': 6.03},

            {'symbol': 'Po', 'name': 'Polonium', 'mass': 209, 'row': 5, 'col': 15, 'isotopes': [
                {'mass': 208.982, 'abundance': 0, 'label': '209Po'},
                {'mass': 209.983, 'abundance': 0, 'label': '210Po'}
            ], 'category': 'metalloid', 'atomic_number': 84, 'density': 9.196, 'ionization_energy': 8.42},

            {'symbol': 'At', 'name': 'Astatine', 'mass': 210, 'row': 5, 'col': 16, 'isotopes': [
                {'mass': 209.987, 'abundance': 0, 'label': '210At'}
            ], 'category': 'halogen', 'atomic_number': 85, 'density': 7, 'ionization_energy': 9.3},

            {'symbol': 'Rn', 'name': 'Radon', 'mass': 222, 'row': 5, 'col': 17, 'isotopes': [
                {'mass': 210.991, 'abundance': 0, 'label': '211Rn'},
                {'mass': 222.018, 'abundance': 0, 'label': '222Rn'}
            ], 'category': 'noble', 'atomic_number': 86, 'density': 0.00973, 'ionization_energy': 10.75},

            {'symbol': 'Fr', 'name': 'Francium', 'mass': 223, 'row': 6, 'col': 0, 'isotopes': [
                {'mass': 223.020, 'abundance': 0, 'label': '223Fr'}
            ], 'category': 'alkali', 'atomic_number': 87, 'density': 1.87, 'ionization_energy': 4.07},

            {'symbol': 'Ra', 'name': 'Radium', 'mass': 226, 'row': 6, 'col': 1, 'isotopes': [
                {'mass': 223.019, 'abundance': 0, 'label': '223Ra'},
                {'mass': 224.020, 'abundance': 0, 'label': '224Ra'},
                {'mass': 226.025, 'abundance': 0, 'label': '226Ra'}
            ], 'category': 'alkaline', 'atomic_number': 88, 'density': 5.5, 'ionization_energy': 5.28},

            {'symbol': 'Ac', 'name': 'Actinium', 'mass': 227, 'row': 6, 'col': 2, 'isotopes': [
                {'mass': 227.028, 'abundance': 0, 'label': '227Ac'}
            ], 'category': 'actinide', 'atomic_number': 89, 'density': 10.07, 'ionization_energy': 5.17},

            {'symbol': 'Pa', 'name': 'Protactinium', 'mass': 231.036, 'row': 9, 'col': 4, 'isotopes': [
                {'mass': 231.036, 'abundance': 0, 'label': '231Pa'}
            ], 'category': 'actinide', 'atomic_number': 91, 'density': 15.37, 'ionization_energy': 5.89},

            {'symbol': 'Am', 'name': 'Americium', 'mass': 243, 'row': 9, 'col': 8, 'isotopes': [
                {'mass': 241.057, 'abundance': 0, 'label': '241Am'},
                {'mass': 243.061, 'abundance': 0, 'label': '243Am'}
            ], 'category': 'actinide', 'atomic_number': 95, 'density': 13.69, 'ionization_energy': 5.97},

            {'symbol': 'Cm', 'name': 'Curium', 'mass': 247, 'row': 9, 'col': 9, 'isotopes': [
                {'mass': 243.061, 'abundance': 0, 'label': '243Cm'},
                {'mass': 244.063, 'abundance': 0, 'label': '244Cm'},
                {'mass': 245.065, 'abundance': 0, 'label': '245Cm'},
                {'mass': 246.067, 'abundance': 0, 'label': '246Cm'},
                {'mass': 247.070, 'abundance': 0, 'label': '247Cm'}
            ], 'category': 'actinide', 'atomic_number': 96, 'density': 13.51, 'ionization_energy': 5.99},

            {'symbol': 'Bk', 'name': 'Berkelium', 'mass': 247, 'row': 9, 'col': 10, 'isotopes': [
                {'mass': 247.070, 'abundance': 0, 'label': '247Bk'},
                {'mass': 249.075, 'abundance': 0, 'label': '249Bk'}
            ], 'category': 'actinide', 'atomic_number': 97, 'density': 14.79, 'ionization_energy': 6.20},

            {'symbol': 'Cf', 'name': 'Californium', 'mass': 251, 'row': 9, 'col': 11, 'isotopes': [
                {'mass': 249.075, 'abundance': 0, 'label': '249Cf'},
                {'mass': 250.076, 'abundance': 0, 'label': '250Cf'},
                {'mass': 251.080, 'abundance': 0, 'label': '251Cf'}
            ], 'category': 'actinide', 'atomic_number': 98, 'density': 15.1, 'ionization_energy': 6.28},

            {'symbol': 'Es', 'name': 'Einsteinium', 'mass': 252, 'row': 9, 'col': 12, 'isotopes': [
                {'mass': 252.083, 'abundance': 0, 'label': '252Es'}
            ], 'category': 'actinide', 'atomic_number': 99, 'density': 8.84, 'ionization_energy': 6.42},

            {'symbol': 'Fm', 'name': 'Fermium', 'mass': 257, 'row': 9, 'col': 13, 'isotopes': [
                {'mass': 257.095, 'abundance': 0, 'label': '257Fm'}
            ], 'category': 'actinide', 'atomic_number': 100, 'density': 9.7, 'ionization_energy': 6.50},

            {'symbol': 'Md', 'name': 'Mendelevium', 'mass': 258, 'row': 9, 'col': 14, 'isotopes': [
                {'mass': 258.098, 'abundance': 0, 'label': '258Md'}
            ], 'category': 'actinide', 'atomic_number': 101, 'density': 10.3, 'ionization_energy': 6.58},

            {'symbol': 'No', 'name': 'Nobelium', 'mass': 259, 'row': 9, 'col': 15, 'isotopes': [
                {'mass': 259.101, 'abundance': 0, 'label': '259No'}
            ], 'category': 'actinide', 'atomic_number': 102, 'density': 9.9, 'ionization_energy': 6.65},

            {'symbol': 'Lr', 'name': 'Lawrencium', 'mass': 266, 'row': 9, 'col': 16, 'isotopes': [
                {'mass': 266, 'abundance': 0, 'label': '266Lr'}
            ], 'category': 'actinide', 'atomic_number': 103, 'density': 14.4, 'ionization_energy': 4.9},

            {'symbol': 'Rf', 'name': 'Rutherfordium', 'mass': 267, 'row': 6, 'col': 3, 'isotopes': [
                {'mass': 267, 'abundance': 0, 'label': '267Rf'}
            ], 'category': 'transition', 'atomic_number': 104, 'density': 23.2, 'ionization_energy': 6.0},

            {'symbol': 'Db', 'name': 'Dubnium', 'mass': 268, 'row': 6, 'col': 4, 'isotopes': [
                {'mass': 268, 'abundance': 0, 'label': '268Db'}
            ], 'category': 'transition', 'atomic_number': 105, 'density': 29.3, 'ionization_energy': 6.8},

            {'symbol': 'Sg', 'name': 'Seaborgium', 'mass': 269, 'row': 6, 'col': 5, 'isotopes': [
                {'mass': 269, 'abundance': 0, 'label': '269Sg'}
            ], 'category': 'transition', 'atomic_number': 106, 'density': 35.0, 'ionization_energy': 7.8},

            {'symbol': 'Bh', 'name': 'Bohrium', 'mass': 270, 'row': 6, 'col': 6, 'isotopes': [
                {'mass': 270, 'abundance': 0, 'label': '270Bh'}
            ], 'category': 'transition', 'atomic_number': 107, 'density': 37.1, 'ionization_energy': 7.7},

            {'symbol': 'Hs', 'name': 'Hassium', 'mass': 277, 'row': 6, 'col': 7, 'isotopes': [
                {'mass': 277, 'abundance': 0, 'label': '277Hs'}
            ], 'category': 'transition', 'atomic_number': 108, 'density': 40.7, 'ionization_energy': 7.6},

            {'symbol': 'Mt', 'name': 'Meitnerium', 'mass': 278, 'row': 6, 'col': 8, 'isotopes': [
                {'mass': 278, 'abundance': 0, 'label': '278Mt'}
            ], 'category': 'transition', 'atomic_number': 109, 'density': 37.4, 'ionization_energy': 7.7},

            {'symbol': 'Ds', 'name': 'Darmstadtium', 'mass': 281, 'row': 6, 'col': 9, 'isotopes': [
                {'mass': 281, 'abundance': 0, 'label': '281Ds'}
            ], 'category': 'transition', 'atomic_number': 110, 'density': 34.8, 'ionization_energy': 7.5},

            {'symbol': 'Rg', 'name': 'Roentgenium', 'mass': 282, 'row': 6, 'col': 10, 'isotopes': [
                {'mass': 282, 'abundance': 0, 'label': '282Rg'}
            ], 'category': 'transition', 'atomic_number': 111, 'density': 28.7, 'ionization_energy': 7.3},

            {'symbol': 'Cn', 'name': 'Copernicium', 'mass': 285, 'row': 6, 'col': 11, 'isotopes': [
                {'mass': 285, 'abundance': 0, 'label': '285Cn'}
            ], 'category': 'transition', 'atomic_number': 112, 'density': 23.7, 'ionization_energy': 7.2},

            {'symbol': 'Nh', 'name': 'Nihonium', 'mass': 286, 'row': 6, 'col': 12, 'isotopes': [
                {'mass': 286, 'abundance': 0, 'label': '286Nh'}
            ], 'category': 'post-transition', 'atomic_number': 113, 'density': 16, 'ionization_energy': 7.1},

            {'symbol': 'Fl', 'name': 'Flerovium', 'mass': 289, 'row': 6, 'col': 13, 'isotopes': [
                {'mass': 289, 'abundance': 0, 'label': '289Fl'}
            ], 'category': 'post-transition', 'atomic_number': 114, 'density': 14, 'ionization_energy': 8.0},

            {'symbol': 'Mc', 'name': 'Moscovium', 'mass': 290, 'row': 6, 'col': 14, 'isotopes': [
                {'mass': 290, 'abundance': 0, 'label': '290Mc'}
            ], 'category': 'post-transition', 'atomic_number': 115, 'density': 13.5, 'ionization_energy': 5.5},

            {'symbol': 'Lv', 'name': 'Livermorium', 'mass': 293, 'row': 6, 'col': 15, 'isotopes': [
                {'mass': 293, 'abundance': 0, 'label': '293Lv'}
            ], 'category': 'post-transition', 'atomic_number': 116, 'density': 12.9, 'ionization_energy': 6.8},

            {'symbol': 'Ts', 'name': 'Tennessine', 'mass': 294, 'row': 6, 'col': 16, 'isotopes': [
                {'mass': 294, 'abundance': 0, 'label': '294Ts'}
            ], 'category': 'halogen', 'atomic_number': 117, 'density': 7.2, 'ionization_energy': 7.3},

            {'symbol': 'Og', 'name': 'Oganesson', 'mass': 294, 'row': 6, 'col': 17, 'isotopes': [
                {'mass': 294, 'abundance': 0, 'label': '294Og'}
            ], 'category': 'noble', 'atomic_number': 118, 'density': 5.0, 'ionization_energy': 8.9}
        ]


if __name__ == '__main__':
    app = QApplication([])
    
    window = CompactPeriodicTableWidget()
    window.show()
    app.exec()