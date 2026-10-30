# AI Assistant

The AI Data Assistant: the particle table and spICP-ToF-MS analyses the model calls, model-drawn figures, the sandbox, prompts, exploration and the benchmark.

---

### [`acquisition.py`](acquisition.md)
Raw signals and per-sample results for the assistant.

**3** classes &nbsp;·&nbsp; **3** functions &nbsp;·&nbsp; **30** methods

### [`analysis.py`](analysis.md)
spICP-ToF-MS analyses the assistant calls instead of writing them itself.

**0** classes &nbsp;·&nbsp; **32** functions &nbsp;·&nbsp; **0** methods

### [`attachments.py`](attachments.md)
Reading files the user attaches to a chat message.

**0** classes &nbsp;·&nbsp; **4** functions &nbsp;·&nbsp; **0** methods

### [`benchmark.py`](benchmark.md)
Score a model on questions with known answers.

**2** classes &nbsp;·&nbsp; **47** functions &nbsp;·&nbsp; **0** methods

### [`crust.py`](crust.md)
Upper continental crust composition, used to compare element ratios with crustal values.

**0** classes &nbsp;·&nbsp; **2** functions &nbsp;·&nbsp; **0** methods

### [`data.py`](data.md)
The particle data the assistant works on, as one pandas table.

**1** classes &nbsp;·&nbsp; **5** functions &nbsp;·&nbsp; **17** methods

### [`dialog.py`](dialog.md)
The AI Data Assistant chat window.

**1** classes &nbsp;·&nbsp; **1** functions &nbsp;·&nbsp; **93** methods

### [`exploration.py`](exploration.md)
State of an agentic exploration: the plan, the findings and the steps.

**3** classes &nbsp;·&nbsp; **27** functions &nbsp;·&nbsp; **15** methods

### [`figures.py`](figures.md)
Figures the model draws itself, with matplotlib, inside the sandbox.

**6** classes &nbsp;·&nbsp; **18** functions &nbsp;·&nbsp; **33** methods

### [`lora_train.py`](lora-train.md)
LoRA training of Qwen3.5-family models with mlx-lm in a fraction of the memory.

**1** classes &nbsp;·&nbsp; **14** functions &nbsp;·&nbsp; **3** methods

### [`memory.py`](memory.md)
How much memory this computer has, how much a model needs, and which model fits.

**0** classes &nbsp;·&nbsp; **13** functions &nbsp;·&nbsp; **0** methods

### [`node.py`](node.md)
The AI Assistant canvas node.

**1** classes &nbsp;·&nbsp; **1** functions &nbsp;·&nbsp; **5** methods

### [`prompts.py`](prompts.md)
What the model is told, and how it all fits in its context window.

**0** classes &nbsp;·&nbsp; **25** functions &nbsp;·&nbsp; **0** methods

### [`report.py`](report.md)
Export a conversation as one self-contained HTML report.

**0** classes &nbsp;·&nbsp; **2** functions &nbsp;·&nbsp; **0** methods

### [`sandbox.py`](sandbox.md)
Running the Python the model writes, safely enough for a local tool.

**1** classes &nbsp;·&nbsp; **24** functions &nbsp;·&nbsp; **1** methods

### [`servers.py`](servers.md)
Local model servers: discovery, launching, stopping and thread housekeeping.

**0** classes &nbsp;·&nbsp; **27** functions &nbsp;·&nbsp; **0** methods

### [`settings.py`](settings.md)
Settings dialogs: which model to use, and how the chat looks.

**2** classes &nbsp;·&nbsp; **0** functions &nbsp;·&nbsp; **26** methods

### [`streaming.py`](streaming.md)
Background threads that talk to the model servers.

**5** classes &nbsp;·&nbsp; **0** functions &nbsp;·&nbsp; **26** methods

### [`synthetic.py`](synthetic.md)
Synthetic spICP-ToF-MS particle streams with known ground truth.

**1** classes &nbsp;·&nbsp; **8** functions &nbsp;·&nbsp; **0** methods

### [`theme.py`](theme.md)
Colours, font sizes and markdown rendering shared by the AI chat widgets.

**1** classes &nbsp;·&nbsp; **9** functions &nbsp;·&nbsp; **5** methods

### [`training.py`](training.md)
Training data for fine-tuning the assistant's model on IsotopeTrack work.

**1** classes &nbsp;·&nbsp; **17** functions &nbsp;·&nbsp; **2** methods

### [`widgets.py`](widgets.md)
Chat window building blocks: message bubbles, tables, figures and inputs.

**16** classes &nbsp;·&nbsp; **0** functions &nbsp;·&nbsp; **91** methods
