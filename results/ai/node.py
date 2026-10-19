"""The AI Assistant canvas node."""
from PySide6.QtCore import QObject, QPointF, Signal

from results.shared_plot_utils import deep_copy_config


class AIAssistantNode(QObject):
    """Canvas node that hands its input particles to the AI chat window.

    The node has one input and no output. The chat window is created the
    first time the node is opened and kept, so conversations survive closing
    and reopening it.
    """

    position_changed = Signal(QPointF)
    configuration_changed = Signal()
    DEFAULT_CONFIG = {'backend': 'ollama', 'model': ''}

    def __init__(self, pw=None):
        """Create the node.

        Args:
            pw: The main window, used to read calibration and detection limits.
        """
        super().__init__()
        self.title = "AI Data Assistant"
        self.node_type = "ai_assistant"
        self.position = QPointF(0, 0)
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.parent_window = pw
        self.input_data = None
        self.chat_dialog = None
        self.config = deep_copy_config(self.DEFAULT_CONFIG)

    def set_position(self, p):
        """Move the node and tell the canvas.

        Args:
            p (QPointF): New position.
        """
        if self.position != p:
            self.position = p
            self.position_changed.emit(p)

    def process_data(self, d):
        """Receive new particle data from upstream.

        Args:
            d (dict): The upstream data context.
        """
        self.input_data = d
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.update_data_context(d)
        self.configuration_changed.emit()

    def get_data_summary(self):
        """Return a one-line description of the connected data.

        Returns:
            str: Sample name or sample count with the particle count.
        """
        d = self.input_data
        if not d:
            return "No data"
        dt = d.get('type', '?')
        if dt == 'sample_data':
            return f"{d.get('sample_name', '?')} — {len(d.get('particle_data', [])):,} particles"
        if dt == 'multiple_sample_data':
            return (f"{len(d.get('sample_names', []))} samples — "
                    f"{len(d.get('particle_data', [])):,} particles")
        return dt

    def configure(self, pw):
        """Open the chat window, creating it on first use.

        Args:
            pw: The main window.

        Returns:
            bool: Always True.
        """
        from results.ai.dialog import AIChatDialog
        if pw is not None:
            self.parent_window = pw
        if not self.chat_dialog:
            self.chat_dialog = AIChatDialog(self, pw)
        if self.input_data:
            self.chat_dialog.update_data_context(self.input_data)
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()
        return True


def create_ai_assistant_node(pw):
    """Create an AI Assistant node.

    Args:
        pw: The main window.

    Returns:
        AIAssistantNode: The new node.
    """
    return AIAssistantNode(pw)
