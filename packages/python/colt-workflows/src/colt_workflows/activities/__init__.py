"""Temporal activities — side effects and external work (CLAUDE.md §24.2).

Workflows must not perform raw network calls, database access or other side effects directly
(§24.1); every side effect goes through an activity, each with an explicit timeout, retry policy,
and input/output schema.
"""

from colt_workflows.activities.example import ExampleActivityInput, greet

__all__ = ["ExampleActivityInput", "greet"]
