"""The AI Data Assistant: a local language model that analyses particle data.

The assistant answers questions by writing Python that runs on the full
particle table, draws figures with matplotlib exactly as the user describes
them, and explores datasets over several turns while keeping a record of
what it finds.

Modules
-------
``node``
    :class:`AIAssistantNode`, the canvas node.
``dialog``
    :class:`AIChatDialog`, the chat window and the question, fix and
    explain loop.
``data``
    :class:`Dataset`: the particles as one pandas table, plus samples, runs
    and calibrated detection limits.
``analysis``
    spICP-ToF-MS analyses the model calls: sample comparisons with tests,
    the random coincidence check, co-occurrence, size distributions with
    truncation flags, outliers, time bursts, combination enrichment and
    clustering through the Clustering node's engine.
``figures``
    The figure factory and ``plt`` stand-in the model draws with, the house
    style, and the text description of each figure fed back to the model.
``sandbox``
    Screening and running generated code, and the no-fabrication check.
``prompts``
    System prompt, dataset brief and the context-window budget.
``exploration``
    Plan and findings ledger of a multi-turn exploration.
``report``
    HTML export of a conversation.
``benchmark`` and ``synthetic``
    A scored question set on synthetic data with known answers, to compare
    models and prompt changes.
``servers``, ``streaming``, ``settings``, ``widgets``, ``theme``, ``attachments``
    Model servers, streaming, settings dialogs and chat widgets.
"""
