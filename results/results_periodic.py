from PySide6.QtWidgets import (QWidget, QGridLayout, QPushButton, QVBoxLayout, 
                             QLabel, QSizePolicy, QHBoxLayout, QApplication, QFrame,
                             QScrollArea)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QLinearGradient

from tools.theme import theme as _app_theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_periodic")

ELEMENT_CATEGORY_COLORS = {
    'alkali':          '#FF7043',
    'alkaline':        '#BA68C8',
    'transition':      '#5C6BC0',
    'post-transition': '#66BB6A',
    'metalloid':       '#FFA726',
    'other':           '#757575',
    'halogen':         '#42A5F5',
    'noble':           '#8D6E63',
    'lanthanide':      '#26C6DA',
    'actinide':        '#79055c',
}


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
        p = _app_theme.palette
        base_style = "padding: 1px; border-radius: 3px; margin: 1px;"

        if self.is_selected:
            self.setStyleSheet(
                base_style + f"background: {p.accent}; color: {p.text_inverse};"
                f" border: 2px solid {p.accent_hover}; font-weight: 600;"
            )
        else:
            if self.is_available:
                self.setStyleSheet(
                    base_style + f"background: {p.bg_tertiary}; color: {p.text_primary};"
                    f" border: 2px solid {p.border_strong};"
                )
            else:
                self.setStyleSheet(
                    base_style + f"background: {p.bg_tertiary}; color: {p.text_muted};"
                    f" border: 2px solid {p.border_subtle};"
                )
            
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
        Args:
            event (Any): Qt event object.
        """
        if not self.is_selected and self.is_available:
            p = _app_theme.palette
            self.setStyleSheet(
                f"padding: 1px; border-radius: 3px; margin: 1px;"
                f" background: {p.accent_soft}; color: {p.text_primary};"
                f" border: 2px solid {p.accent};"
            )
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
        self._apply_theme_style()
        self._theme_handler = lambda _: self._safe_apply_theme()
        _app_theme.themeChanged.connect(self._theme_handler)
        self.destroyed.connect(self._disconnect_theme)

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

    def _disconnect_theme(self):
        try:
            _app_theme.themeChanged.disconnect(self._theme_handler)
        except Exception:
            # Already disconnected or signal source gone — expected during teardown
            _itk_log.debug("Theme handler already disconnected")

    def _safe_apply_theme(self):
        import shiboken6
        if not shiboken6.isValid(self):
            # C++ widget already deleted — unsubscribe so this never fires again
            self._disconnect_theme()
            return
        try:
            self._apply_theme_style()
        except RuntimeError:
            # Deleted between the check and the call — unsubscribe quietly
            self._disconnect_theme()
            _itk_log.debug("Theme handler removed for deleted widget")

    def _apply_theme_style(self):
        p = _app_theme.palette
        self.setStyleSheet(
            f"QFrame {{ background-color: {p.bg_secondary}; border: 1px solid {p.border};"
            f" border-radius: 4px; padding: 2px; }}"
        )
    
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
        Args:
            isotopes_data (Any): The isotopes data.
        """
        self.selected_isotopes = set((symbol, mass) for symbol, mass in isotopes_data)
        if self.parent_button:
            self.parent_button.clear_highlights()
        for mass, label in self.mass_labels.items():
            is_sel = (self.element_symbol, mass) in self.selected_isotopes
            label.setSelected(is_sel)
            if is_sel and self.parent_button:
                parent_widget = self.parent()
                if parent_widget and hasattr(parent_widget, 'get_elements'):
                    el_data = next(
                        (e for e in parent_widget.get_elements()
                         if e['symbol'] == self.element_symbol), None)
                    if el_data:
                        iso_data = next(
                            (i for i in el_data['isotopes']
                             if isinstance(i, dict) and abs(i['mass'] - mass) < 0.001), None)
                        abundance = iso_data['abundance'] if iso_data else 0
                        self.parent_button.set_highlight(abundance, accumulate=True)

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
        self._apply_theme_bg()
        self._pt_theme_handler = lambda _: self._safe_apply_theme_bg()
        _app_theme.themeChanged.connect(self._pt_theme_handler)
        self.destroyed.connect(self._pt_disconnect_theme)

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

    def _pt_disconnect_theme(self):
        try:
            _app_theme.themeChanged.disconnect(self._pt_theme_handler)
        except Exception:
            _itk_log.exception("Handled exception in _pt_disconnect_theme")

    def _safe_apply_theme_bg(self):
        try:
            self._apply_theme_bg()
        except RuntimeError:
            _itk_log.exception("Handled exception in _safe_apply_theme_bg")

    def _apply_theme_bg(self):
        p = _app_theme.palette
        self.setStyleSheet(f"background-color: {p.bg_primary};")

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
    
        Single source of truth: PeriodicTableWidget.create_elements_data()
        in widget/periodic_table_widget.py. This delegation replaced a
        duplicated 617-line copy of the element table (2026-06).
    
        Returns:
            list: List of element data dictionaries (118 elements with
            symbol, name, mass, isotopes, category, density, etc.).
        """
        from widget.periodic_table_widget import PeriodicTableWidget
        return PeriodicTableWidget.create_elements_data()


class IsotopeChipSelector(QWidget):
    """
    Compact chip-based isotope selector.
    Shows available isotopes grouped by element as clickable toggle chips.
    Much simpler UX than the full periodic table for quick sample configuration.
    """
    selection_changed = Signal()

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._available = []
        self._selected = set()
        self._chips = {}
        self._setup()
        self._chip_theme_handler = lambda _: self._safe_restyle()
        _app_theme.themeChanged.connect(self._chip_theme_handler)
        self.destroyed.connect(self._chip_disconnect_theme)

    def _chip_disconnect_theme(self):
        try:
            _app_theme.themeChanged.disconnect(self._chip_theme_handler)
        except Exception:
            _itk_log.exception("Handled exception in _chip_disconnect_theme")

    def _safe_restyle(self):
        try:
            self._restyle_all()
        except RuntimeError:
            _itk_log.exception("Handled exception in _safe_restyle")

    # ── build ──────────────────────────────────────────────────────────────
    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        hdr = QHBoxLayout()
        self._title_lbl = QLabel("Available Isotopes")
        self._title_lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()

        self._btn_all = QPushButton("Select All")
        self._btn_all.setFixedHeight(26)
        self._btn_all.setCursor(Qt.PointingHandCursor)
        self._btn_all.clicked.connect(self.select_all)

        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.setCursor(Qt.PointingHandCursor)
        self._btn_clear.clicked.connect(self.clear_selection)

        hdr.addWidget(self._btn_all)
        hdr.addWidget(self._btn_clear)
        root.addLayout(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._content = QWidget()
        self._flow = QVBoxLayout(self._content)
        self._flow.setContentsMargins(6, 6, 6, 6)
        self._flow.setSpacing(5)
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll)

        self._restyle_all()

    # ── theme ──────────────────────────────────────────────────────────────
    def _restyle_all(self):
        p = _app_theme.palette
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background:{p.bg_secondary}; border:1px solid {p.border};
                           border-radius:6px; }}
            QScrollBar:vertical {{ background:{p.bg_primary}; width:8px; border:none; }}
            QScrollBar::handle:vertical {{ background:{p.border}; border-radius:4px;
                                           min-height:20px; }}
            QScrollBar::handle:vertical:hover {{ background:{p.text_muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._content.setStyleSheet(f"background:{p.bg_secondary};")
        self._title_lbl.setStyleSheet(
            f"font-weight:600; font-size:12px; color:{p.text_primary};")
        _btn_style = (
            f"QPushButton {{ background:{p.bg_tertiary}; color:{p.text_primary};"
            f" border:1px solid {p.border}; border-radius:4px;"
            f" padding:3px 10px; font-size:11px; }}"
            f"QPushButton:hover {{ border-color:{p.accent}; color:{p.accent}; }}"
        )
        self._btn_all.setStyleSheet(_btn_style)
        self._btn_clear.setStyleSheet(_btn_style)
        for (sym, mass) in self._chips:
            self._style_chip(sym, mass)

    def _style_chip(self, sym, mass):
        """
        Args:
            sym (Any): The sym.
            mass (Any): Mass value in amu.
        """
        chip = self._chips.get((sym, mass))
        if not chip:
            return
        p = _app_theme.palette
        selected = (sym, mass) in self._selected
        cat_color = '#5C6BC0'
        for info in self._available:
            if info[0] == sym and abs(info[1] - mass) < 0.001:
                cat_color = ELEMENT_CATEGORY_COLORS.get(info[4], '#5C6BC0')
                break
        if selected:
            chip.setStyleSheet(
                f"QPushButton {{ background:{cat_color}; color:white;"
                f" border:2px solid {QColor(cat_color).darker(130).name()};"
                f" border-radius:10px; padding:2px 10px;"
                f" font-size:11px; font-weight:600; }}"
                f"QPushButton:hover {{ background:{QColor(cat_color).lighter(115).name()}; }}"
            )
        else:
            chip.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{p.text_secondary};"
                f" border:2px solid {cat_color}; border-radius:10px;"
                f" padding:2px 10px; font-size:11px; }}"
                f"QPushButton:hover {{ background:{cat_color}22; color:{p.text_primary}; }}"
            )

    # ── data ───────────────────────────────────────────────────────────────
    def set_available_isotopes(self, element_data_list, isotope_pairs):
        """
        isotope_pairs: list of (symbol, mass) tuples
        element_data_list: list of element dicts from get_elements()
        Args:
            element_data_list (Any): The element data list.
            isotope_pairs (Any): The isotope pairs.
        """
        self._available = []
        elem_lookup = {e['symbol']: e for e in element_data_list}
        seen = set()
        for sym, mass in sorted(isotope_pairs, key=lambda x: (x[0], x[1])):
            if (sym, mass) in seen:
                continue
            seen.add((sym, mass))
            elem = elem_lookup.get(sym, {})
            cat = elem.get('category', 'other')
            lbl = f"{sym}-{round(mass)}"
            abund = 0
            for iso in elem.get('isotopes', []):
                if isinstance(iso, dict) and abs(iso['mass'] - mass) < 0.001:
                    lbl = iso.get('label', lbl)
                    abund = iso.get('abundance', 0)
                    break
            self._available.append((sym, mass, lbl, abund, cat))
        self._rebuild_chips()

    def _rebuild_chips(self):
        p = _app_theme.palette
        while self._flow.count():
            child = self._flow.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._chips.clear()

        groups = {}
        for sym, mass, lbl, abund, cat in self._available:
            if sym not in groups:
                groups[sym] = {'cat': cat, 'isotopes': []}
            groups[sym]['isotopes'].append((mass, lbl, abund))

        if not groups:
            ph = QLabel("No isotopes available")
            ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(
                f"color:{p.text_muted}; font-style:italic; padding:20px;")
            self._flow.addWidget(ph)
            self._flow.addStretch()
            return

        for sym in sorted(groups.keys(),
                          key=lambda s: min(m for m, _, _ in groups[s]['isotopes'])):
            info = groups[sym]
            cat = info['cat']
            cat_color = ELEMENT_CATEGORY_COLORS.get(cat, '#5C6BC0')

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)

            el_lbl = QLabel(sym)
            el_lbl.setFixedWidth(38)
            el_lbl.setAlignment(Qt.AlignCenter)
            el_lbl.setStyleSheet(
                f"QLabel {{ background:{cat_color}; color:white;"
                f" border-radius:4px; padding:2px 4px;"
                f" font-size:11px; font-weight:bold; }}"
            )
            row.addWidget(el_lbl)

            for mass, lbl, _ in info['isotopes']:
                chip = QPushButton(lbl)
                chip.setFixedHeight(24)
                chip.setCursor(Qt.PointingHandCursor)
                self._chips[(sym, mass)] = chip
                self._style_chip(sym, mass)
                chip.clicked.connect(
                    lambda _=False, s=sym, m=mass: self._toggle(s, m))
                row.addWidget(chip)

            row.addStretch()
            self._flow.addWidget(row_w)

        self._flow.addStretch()

    def _toggle(self, sym, mass):
        """
        Args:
            sym (Any): The sym.
            mass (Any): Mass value in amu.
        """
        key = (sym, mass)
        if key in self._selected:
            self._selected.remove(key)
        else:
            self._selected.add(key)
        self._style_chip(sym, mass)
        self.selection_changed.emit()

    def set_selected(self, isotope_list):
        """isotope_list: list of {'symbol':..., 'mass':...} dicts
        Args:
            isotope_list (Any): The isotope list.
        """
        self._selected = {(it['symbol'], it['mass']) for it in isotope_list}
        for (sym, mass) in self._chips:
            self._style_chip(sym, mass)

    def get_selected(self):
        """Returns list of (symbol, mass) tuples"""
        return list(self._selected)

    def select_all(self):
        for sym, mass, *_ in self._available:
            self._selected.add((sym, mass))
        for (sym, mass) in self._chips:
            self._style_chip(sym, mass)
        self.selection_changed.emit()

    def clear_selection(self):
        self._selected.clear()
        for (sym, mass) in self._chips:
            self._style_chip(sym, mass)
        self.selection_changed.emit()


if __name__ == '__main__':
    app = QApplication([])
    
    window = CompactPeriodicTableWidget()
    window.show()
    app.exec()