"""Enhanced logging system with GUI display, user action tracking, and context support."""
import logging
import sys
from datetime import datetime
from functools import wraps
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTextEdit, QComboBox, QLabel, QCheckBox, QFrame, QLineEdit)
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
import qtawesome as qta
import json
import traceback


class LogSignaller(QObject):
    """
    Signal emitter for thread-safe logging to GUI.
    """
    
    log_message = Signal(str, str, str, dict)


class EnhancedQtLogHandler(logging.Handler):
    """
    Enhanced logging handler for Qt applications with context support.
    """
    
    def __init__(self, log_window=None):
        """
        Initialize the Qt log handler.
        
        Args:
            log_window (EnhancedLogWindow, optional): Log window to display messages
            
        Returns:
            None
        """
        super().__init__()
        self.signaller = LogSignaller()
        self.log_window = log_window
        if log_window:
            self.signaller.log_message.connect(log_window.add_log_message)
    
    def emit(self, record):
        """
        Emit a log record to the GUI.
        
        Args:
            record (LogRecord): Log record to emit
            
        Returns:
            None
        """
        try:
            msg = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
            
            context = getattr(record, 'context', {})
            
            self.signaller.log_message.emit(record.levelname, msg, timestamp, context)
        except Exception:
            self.handleError(record)


class UserActionLogger:
    """
    Specialized logger for user actions and workflow tracking.
    """
    
    def __init__(self, main_logger):
        """
        Initialize the user action logger.
        
        Args:
            main_logger (Logger): Main logger instance to use
            
        Returns:
            None
        """
        self.main_logger = main_logger
        self.session_start = datetime.now()
        self.action_count = 0
        
    def log_action(self, action_type, description, context=None):
        """
        Log a user action with context.
        
        Args:
            action_type (str): Type of action (e.g., 'CLICK', 'MENU', 'FILE_OP')
            description (str): Human-readable description of the action
            context (dict, optional): Additional context information
            
        Returns:
            None
        """
        self.action_count += 1
        
        context = context or {}
        context.update({
            'action_type': action_type,
            'session_time': str(datetime.now() - self.session_start),
            'action_number': self.action_count
        })
        
        record = logging.LogRecord(
            name=self.main_logger.name,
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=f"[USER ACTION] {action_type}: {description}",
            args=(),
            exc_info=None
        )
        record.context = context
        
        self.main_logger.handle(record)
    
    def log_click(self, widget_name, widget_type=None, additional_info=None):
        """
        Log button/widget clicks.
        
        Args:
            widget_name (str): Name of the clicked widget
            widget_type (str, optional): Type of widget
            additional_info (dict, optional): Additional information
            
        Returns:
            None
        """
        context = {
            'widget_name': widget_name,
            'widget_type': widget_type or 'Unknown',
            'additional_info': additional_info or {}
        }
        self.log_action('CLICK', f"Clicked {widget_name}", context)
    
    def log_menu_action(self, menu_name, action_name):
        """
        Log menu selections.
        
        Args:
            menu_name (str): Name of the menu
            action_name (str): Name of the action
            
        Returns:
            None
        """
        context = {'menu': menu_name, 'action': action_name}
        self.log_action('MENU', f"Selected {menu_name} -> {action_name}", context)
    
    def log_dialog_open(self, dialog_name, dialog_type=None):
        """
        Log dialog openings.
        
        Args:
            dialog_name (str): Name of the dialog
            dialog_type (str, optional): Type of dialog
            
        Returns:
            None
        """
        context = {'dialog_name': dialog_name, 'dialog_type': dialog_type}
        self.log_action('DIALOG_OPEN', f"Opened {dialog_name}", context)
    
    def log_file_operation(self, operation, file_path, success=True):
        """
        Log file operations.
        
        Args:
            operation (str): Type of file operation (e.g., 'load', 'save')
            file_path (str): Path to the file
            success (bool, optional): Whether operation was successful
            
        Returns:
            None
        """
        context = {
            'operation': operation,
            'file_path': str(file_path),
            'success': success
        }
        self.log_action('FILE_OP', f"{operation}: {file_path}", context)
    
    def log_data_operation(self, operation, details=None):
        """
        Log data processing operations.
        
        Args:
            operation (str): Type of data operation
            details (dict, optional): Additional operation details
            
        Returns:
            None
        """
        context = {'operation': operation, 'details': details or {}}
        self.log_action('DATA_OP', f"Data operation: {operation}", context)
    
    def log_analysis_step(self, step_name, parameters=None, results=None):
        """
        Log analysis workflow steps.
        
        Args:
            step_name (str): Name of the analysis step
            parameters (dict, optional): Analysis parameters
            results (dict, optional): Analysis results
            
        Returns:
            None
        """
        context = {
            'step': step_name,
            'parameters': parameters or {},
            'results': results or {}
        }
        self.log_action('ANALYSIS', f"Analysis step: {step_name}", context)


class EnhancedLogWindow(QDialog):
    """
    Enhanced log viewing window with filtering and context display.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the enhanced log window.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("IsotopeTrack - Application Log")
        self.setWindowIcon(qta.icon('fa6s.file-lines', color="#2c3e50"))
        self.resize(1200, 700)
        
        self.log_entries = []
        self.setup_ui()
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        
        self.level_filter = QComboBox()
        self.level_filter.addItems(['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'USER ACTION'])
        self.level_filter.setCurrentText('ALL')
        self.level_filter.currentTextChanged.connect(self.filter_logs)
        
        self.action_filter = QComboBox()
        self.action_filter.addItems(['ALL ACTIONS', 'CLICK', 'MENU', 'DIALOG_OPEN', 'FILE_OP', 'DATA_OP', 'ANALYSIS'])
        self.action_filter.currentTextChanged.connect(self.filter_logs)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search logs...")
        self.search_box.textChanged.connect(self.filter_logs)
        
        self.show_context_checkbox = QCheckBox("Show Context")
        self.show_context_checkbox.setChecked(True)
        self.show_context_checkbox.toggled.connect(self.filter_logs)
        
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_logs)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_logs)
        
        export_json_button = QPushButton("Export JSON")
        export_json_button.clicked.connect(self.export_logs_json)
        
        toolbar_layout.addWidget(QLabel("Level:"))
        toolbar_layout.addWidget(self.level_filter)
        toolbar_layout.addWidget(QLabel("Action:"))
        toolbar_layout.addWidget(self.action_filter)
        toolbar_layout.addWidget(QLabel("Search:"))
        toolbar_layout.addWidget(self.search_box)
        toolbar_layout.addWidget(self.show_context_checkbox)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(clear_button)
        toolbar_layout.addWidget(save_button)
        toolbar_layout.addWidget(export_json_button)
        
        layout.addWidget(toolbar)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        font = QFont("Consolas", 16)
        self.log_display.setFont(font)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                line-height: 1.4;
            }
        """)
        
        layout.addWidget(self.log_display)
    
    def add_log_message(self, level, message, timestamp, context=None):
        """
        Add log message with context support.
        
        Args:
            level (str): Log level (DEBUG, INFO, WARNING, ERROR)
            message (str): Log message
            timestamp (str): Timestamp string
            context (dict, optional): Additional context information
            
        Returns:
            None
        """
        entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'context': context or {},
            'full_text': f"[{timestamp}] {level:8} | {message}"
        }
        
        if context and any(context.values()):
            if self.show_context_checkbox.isChecked():
                context_str = self.format_context(context)
                entry['full_text'] += f"\n    Context: {context_str}"
        
        self.log_entries.append(entry)
        self.filter_logs()
    
    def format_context(self, context):
        """
        Format context information for display.
        
        Args:
            context (dict): Context dictionary
            
        Returns:
            str: Formatted context string
        """
        if not context:
            return ""
        
        formatted_parts = []
        for key, value in context.items():
            if isinstance(value, dict) and value:
                nested = ", ".join(f"{k}={v}" for k, v in value.items() if v)
                if nested:
                    formatted_parts.append(f"{key}=({nested})")
            elif value:
                formatted_parts.append(f"{key}={value}")
        
        return " | ".join(formatted_parts)
    
    def filter_logs(self):
        """
        Enhanced log filtering with action types and search.
        
        Args:
            None
            
        Returns:
            None
        """
        level_filter = self.level_filter.currentText()
        action_filter = self.action_filter.currentText()
        search_text = self.search_box.text().lower()
        show_context = self.show_context_checkbox.isChecked()
        
        filtered_entries = []
        for entry in self.log_entries:
            if level_filter != 'ALL':
                if level_filter == 'USER ACTION':
                    if '[USER ACTION]' not in entry['message']:
                        continue
                elif entry['level'] != level_filter:
                    continue
            
            if action_filter != 'ALL ACTIONS':
                if action_filter not in entry['context'].get('action_type', ''):
                    continue
            
            if search_text:
                searchable_text = entry['message'].lower()
                if entry['context']:
                    searchable_text += " " + str(entry['context']).lower()
                if search_text not in searchable_text:
                    continue
            
            display_text = entry['full_text']
            if show_context and entry['context']:
                context_str = self.format_context(entry['context'])
                if context_str:
                    display_text = f"[{entry['timestamp']}] {entry['level']:8} | {entry['message']}\n    Context: {context_str}"
            else:
                display_text = f"[{entry['timestamp']}] {entry['level']:8} | {entry['message']}"
            
            entry['display_text'] = display_text
            filtered_entries.append(entry)
        
        self.log_display.clear()
        for entry in filtered_entries:
            color = self.get_level_color(entry['level'], entry.get('context', {}))
            html_text = f'<span style="color: {color};">{entry["display_text"]}</span><br>'
            self.log_display.insertHtml(html_text)
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)
    
    def get_level_color(self, level, context=None):
        """
        Get color for log level with special handling for user actions.
        
        Args:
            level (str): Log level
            context (dict, optional): Context dictionary
            
        Returns:
            str: Hex color code
        """
        if '[USER ACTION]' in str(context.get('action_type', '')):
            action_colors = {
                'CLICK': '#00bcd4',
                'MENU': '#ff9800',
                'DIALOG_OPEN': '#9c27b0',
                'FILE_OP': '#4caf50',
                'DATA_OP': '#2196f3',
                'ANALYSIS': '#e91e63'
            }
            return action_colors.get(context.get('action_type', ''), '#00bcd4')
        
        colors = {
            'DEBUG': '#6c757d',
            'INFO': '#17a2b8', 
            'WARNING': '#ffc107',
            'ERROR': '#dc3545'
        }
        return colors.get(level, '#d4d4d4')
    
    def clear_logs(self):
        """
        Clear all log entries.
        
        Args:
            None
            
        Returns:
            None
        """
        self.log_entries.clear()
        self.log_display.clear()
    
    def save_logs(self):
        """
        Save logs to a text file.
        
        Args:
            None
            
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", 
            f"isotope_track_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        if filename:
            with open(filename, 'w') as f:
                for entry in self.log_entries:
                    f.write(entry['display_text'] + '\n')
    
    def export_logs_json(self):
        """
        Export logs with full context as JSON.
        
        Args:
            None
            
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Logs as JSON", 
            f"isotope_track_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.log_entries, f, indent=2, default=str)


class EnhancedLoggingManager:
    """
    Enhanced logging manager with user action tracking.
    """
    
    def __init__(self):
        """
        Initialize the enhanced logging manager.
        
        Args:
            None
            
        Returns:
            None
        """
        self.logger = None
        self.log_window = None
        self.qt_handler = None
        self.user_action_logger = None
        self.setup_logging()
    
    def setup_logging(self):
        """
        Setup logging with console, file, and user action handlers.
        
        Args:
            None
            
        Returns:
            None
        """
        self.logger = logging.getLogger('IsotopeTrack')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        try:
            file_handler = logging.FileHandler('isotope_track.log', mode='a')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Could not setup file logging: {e}")
        
        self.user_action_logger = UserActionLogger(self.logger)
    
    def create_log_window(self, parent=None):
        """
        Create or retrieve the log window.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            EnhancedLogWindow: The log window instance
        """
        if self.log_window is None:
            self.log_window = EnhancedLogWindow(parent)
            
            self.qt_handler = EnhancedQtLogHandler(self.log_window)
            self.qt_handler.setLevel(logging.DEBUG)
            qt_formatter = logging.Formatter('%(name)s - %(message)s')
            self.qt_handler.setFormatter(qt_formatter)
            self.logger.addHandler(self.qt_handler)
        
        return self.log_window
    
    def get_logger(self, name=None):
        """
        Get a logger instance.
        
        Args:
            name (str, optional): Logger name suffix
            
        Returns:
            Logger: Logger instance
        """
        if name:
            return logging.getLogger(f'IsotopeTrack.{name}')
        return self.logger
    
    def get_user_action_logger(self):
        """
        Get the user action logger.
        
        Args:
            None
            
        Returns:
            UserActionLogger: User action logger instance
        """
        return self.user_action_logger
    
    def show_log_window(self, parent=None):
        """
        Show the log window.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            EnhancedLogWindow: The shown log window
        """
        log_window = self.create_log_window(parent)
        log_window.show()
        log_window.raise_()
        return log_window


def log_user_action(action_type, description=None):
    """
    Decorator to automatically log user actions.
    
    Args:
        action_type (str): Type of action to log
        description (str, optional): Action description
        
    Returns:
        function: Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, 'user_action_logger') and self.user_action_logger:
                func_name = func.__name__
                desc = description or f"Executed {func_name}"
                
                context = {}
                if hasattr(self, 'current_sample') and self.current_sample:
                    context['current_sample'] = self.current_sample
                if hasattr(self, 'selected_isotopes') and self.selected_isotopes:
                    context['selected_elements'] = list(self.selected_isotopes.keys())
                
                self.user_action_logger.log_action(action_type, desc, context)
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

logging_manager = EnhancedLoggingManager()