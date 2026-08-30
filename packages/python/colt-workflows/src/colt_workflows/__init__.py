"""Temporal workflows and activities."""

from colt_workflows.activities import ExampleActivityInput, greet
from colt_workflows.worker import ACTIVITIES, WORKFLOWS, run_worker
from colt_workflows.workflows import ExampleWorkflow

__version__ = "0.1.0"

__all__ = [
    "ACTIVITIES",
    "WORKFLOWS",
    "ExampleActivityInput",
    "ExampleWorkflow",
    "__version__",
    "greet",
    "run_worker",
]
