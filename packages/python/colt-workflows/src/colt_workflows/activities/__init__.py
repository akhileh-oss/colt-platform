"""Temporal activities — side effects and external work (CLAUDE.md §24.2).

Workflows must not perform raw network calls, database access or other side effects directly
(§24.1); every side effect goes through an activity, each with an explicit timeout, retry policy,
and input/output schema.

Deliberately re-exports only `example` here, not `trace_check`: importing this package (which
any workflow file importing even one activity from it must do, since Python always initializes a
package's `__init__` before a submodule) would otherwise transitively pull in `colt_db` and its
SQLAlchemy/asyncpg dependencies — real I/O-capable libraries the Temporal workflow sandbox
refuses to let a workflow module import, sandboxed or not. `count_organizations` is imported
directly from `colt_workflows.activities.trace_check` by the one workflow that needs it,
wrapped in `workflow.unsafe.imports_passed_through()`.
"""

from colt_workflows.activities.example import ExampleActivityInput, greet

__all__ = ["ExampleActivityInput", "greet"]
