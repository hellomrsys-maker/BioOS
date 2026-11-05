"""Top‑level ``services`` package.

The original codebase relied on implicit namespace packages which are not
recognised by the Python interpreter in this execution environment. Adding an
empty ``__init__`` makes the ``services`` directory a proper package, allowing
imports such as ``services.command_center.realtime_collab`` used throughout the
test suite.
"""
