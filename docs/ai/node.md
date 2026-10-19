# `node.py`

The AI Assistant canvas node.

---

## Classes

### `AIAssistantNode` *(extends `QObject`)*

Canvas node that hands its input particles to the AI chat window.

The node has one input and no output. The chat window is created the
first time the node is opened and kept, so conversations survive closing
and reopening it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, pw=None)` | Create the node. |
| `set_position` | `(self, p)` | Move the node and tell the canvas. |
| `process_data` | `(self, d)` | Receive new particle data from upstream. |
| `get_data_summary` | `(self)` | Return a one-line description of the connected data. |
| `configure` | `(self, pw)` | Open the chat window, creating it on first use. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `create_ai_assistant_node` | `(pw)` | Create an AI Assistant node. |
