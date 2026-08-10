"""Lazy OpenMM access for benchmark/oracle code only.

Importing this module never imports OpenMM.  Call :func:`load_openmm` only from
an external-oracle benchmark path that explicitly opted into OpenMM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import OracleUnavailableError


@dataclass(frozen=True)
class OpenMMModules:
    """The three public OpenMM namespaces used by benchmark adapters."""

    mm: Any
    unit: Any
    app: Any


def load_openmm() -> OpenMMModules:
    """Load OpenMM lazily or raise a sanitized benchmark-pack error."""

    try:
        import openmm as mm  # type: ignore[import-not-found]
        from openmm import app, unit  # type: ignore[import-not-found]
    except Exception as exc:
        raise OracleUnavailableError("openmm") from exc
    return OpenMMModules(mm=mm, unit=unit, app=app)


from .adapter import (  # noqa: E402  (load_openmm must exist before this import)
    HarmonicBondResult,
    HarmonicBondRun,
    OpenMMReferenceIdentity,
    evaluate_harmonic_bond_reference,
    evaluate_harmonic_bond_smoke,
    harmonic_bond_prepared_system_sha256,
    openmm_reference_runtime_sha256,
    openmm_runtime_dependency_distributions_sha256,
)


__all__ = [
    "HarmonicBondResult",
    "HarmonicBondRun",
    "OpenMMModules",
    "OpenMMReferenceIdentity",
    "evaluate_harmonic_bond_reference",
    "evaluate_harmonic_bond_smoke",
    "harmonic_bond_prepared_system_sha256",
    "load_openmm",
    "openmm_reference_runtime_sha256",
    "openmm_runtime_dependency_distributions_sha256",
]
