"""Benchmark-only GROMACS double-precision rerun adapter.

High-level results retain bounded XVG bytes; large EDR/TRR files are exposed
only through verified provenance digests.
"""

from .adapter import (
    CommandOutput,
    EnergyFrame,
    EnergySeries,
    ForceFrame,
    GromacsIdentity,
    OracleAdapterError,
    ORACLE_TASK,
    RerunExecution,
    RerunObservations,
    build_energy_extract_command,
    build_force_extract_command,
    build_mdrun_rerun_command,
    parse_energy_text,
    parse_force_text,
    parse_identity,
    parse_rerun_text,
    probe_identity,
    run_rerun,
)

__all__ = [
    "CommandOutput",
    "EnergyFrame",
    "EnergySeries",
    "ForceFrame",
    "GromacsIdentity",
    "OracleAdapterError",
    "ORACLE_TASK",
    "RerunExecution",
    "RerunObservations",
    "build_energy_extract_command",
    "build_force_extract_command",
    "build_mdrun_rerun_command",
    "parse_energy_text",
    "parse_force_text",
    "parse_identity",
    "parse_rerun_text",
    "probe_identity",
    "run_rerun",
]
