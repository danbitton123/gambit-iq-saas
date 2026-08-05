"""Stable domain errors shared across Streamlit hot reloads.

Keeping these lightweight types outside the repository module prevents a newly
reloaded entrypoint from depending on an older cached repository definition.
"""


class DataConnectionError(RuntimeError):
    """The warehouse could not be opened or reached."""


class SQLQueryError(RuntimeError):
    """A governed SQL query could not be completed."""
