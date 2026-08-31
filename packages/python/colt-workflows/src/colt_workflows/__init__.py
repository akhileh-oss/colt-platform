"""Temporal workflows and activities.

Deliberately minimal: any workflow module (e.g. `colt_workflows.workflows.example`) forces
Python to initialize this top-level package first, since parent packages always run before a
submodule does. If this `__init__` pulled in `colt_workflows.worker` — which needs
`colt_observability` (the full OpenTelemetry SDK, Milestone 07), `colt_config`, and
`temporalio.client` — every workflow's sandbox validation would inherit that same heavy,
I/O-capable import chain and fail for the same reason `colt_workflows.activities` keeps
`trace_check` out of its own `__init__` (see that module's docstring). Import `run_worker`,
`ACTIVITIES` and `WORKFLOWS` from `colt_workflows.worker` directly; import
`count_organizations` from `colt_workflows.activities.trace_check` directly.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
