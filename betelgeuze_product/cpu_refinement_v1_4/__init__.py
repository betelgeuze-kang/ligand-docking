"""Explicit opt-in diagnostics; existing runners and frozen evidence stay separate."""

from .contracts import SolverConfig, source_manifest
from .minimization import PendingWorkError, inspect_run, minimize, verify_run
from .workflow import audit_request, run_minimization, verify_run as verify_prepared_run

__all__ = ["SolverConfig", "PendingWorkError", "minimize", "verify_run", "inspect_run", "source_manifest",
           "audit_request", "run_minimization", "verify_prepared_run"]
