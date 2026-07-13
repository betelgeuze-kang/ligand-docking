"""Preparation-readiness gate between molecular ingest and chemistry features."""

from __future__ import annotations

from collections.abc import Mapping

from .models import AllAtomSystem


class MolecularPreparationError(RuntimeError):
    """Raised when an ingest result still carries unresolved chemistry blockers."""

    def __init__(self, blockers: tuple[str, ...]):
        self.blockers = tuple(blockers)
        preview = ", ".join(self.blockers[:6])
        suffix = "" if len(self.blockers) <= 6 else f", +{len(self.blockers) - 6} more"
        super().__init__(f"molecular preparation is incomplete: {preview}{suffix}")


def molecular_preparation_blockers(system: AllAtomSystem) -> tuple[str, ...]:
    """Return typed and provenance-backed blockers without guessing chemistry."""

    if not isinstance(system, AllAtomSystem):
        raise TypeError("system must be an AllAtomSystem")
    blockers: list[str] = []
    if not system.has_coordinates:
        blockers.append("coordinates_missing")
    if any(not atom.formal_charge_known for atom in system.atoms):
        blockers.append("formal_charge_unknown_for_some_atoms")
    if not system.provenance.preparation_ready:
        blockers.append("preparation_not_complete")

    coverage = system.provenance.metadata.get("coverage")
    if isinstance(coverage, Mapping):
        raw_blockers = coverage.get("blockers", ())
        if isinstance(raw_blockers, (list, tuple)):
            blockers.extend(value for value in raw_blockers if type(value) is str and value)
        if coverage.get("supported") is False:
            blockers.append("source_format_or_chemistry_not_supported")
        if coverage.get("preparation_ready") is False:
            blockers.append("preparation_not_complete")
    return tuple(dict.fromkeys(blockers))


def require_molecular_preparation_ready(system: AllAtomSystem) -> None:
    blockers = molecular_preparation_blockers(system)
    if blockers:
        raise MolecularPreparationError(blockers)


__all__ = [
    "MolecularPreparationError",
    "molecular_preparation_blockers",
    "require_molecular_preparation_ready",
]
