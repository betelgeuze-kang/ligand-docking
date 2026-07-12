"""Independent Engine v2 contract and molecular-state package.

Later stacked PRs add sparse geometry, AI primitives, the internal CPU
orchestrator, legacy adapters, and packaging without changing this ownership
boundary.
"""

from .contracts import (
    ALL_ATOM_SCHEMA_ID,
    CHECKPOINT_SCHEMA_VERSION,
    DISTRIBUTION_NAME,
    DISTRIBUTION_VERSION,
    ENGINE_API_VERSION,
    ENGINE_RESULT_SCHEMA_VERSION,
    RUNTIME_INPUT_SCHEMA_VERSION,
    VERSION_TAXONOMY,
    ClaimStage,
    QuantityDescriptor,
    UNCALIBRATED_ENERGY,
    UNCALIBRATED_FORCE,
)
from .molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    MolecularValidationError,
    Residue,
    StructureProvenance,
    UnitCell,
    ValidationReport,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
    validate_all_atom_system,
)

__version__ = ENGINE_API_VERSION

__all__ = [
    "ALL_ATOM_SCHEMA_ID",
    "CHECKPOINT_SCHEMA_VERSION",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "ENGINE_API_VERSION",
    "ENGINE_RESULT_SCHEMA_VERSION",
    "RUNTIME_INPUT_SCHEMA_VERSION",
    "VERSION_TAXONOMY",
    "AllAtomSystem",
    "Atom",
    "Bond",
    "Chain",
    "ClaimStage",
    "MolecularValidationError",
    "QuantityDescriptor",
    "Residue",
    "StructureProvenance",
    "UNCALIBRATED_ENERGY",
    "UNCALIBRATED_FORCE",
    "UnitCell",
    "ValidationReport",
    "canonical_coordinates_sha256",
    "canonical_system_sha256",
    "canonical_topology_sha256",
    "require_valid_all_atom_system",
    "validate_all_atom_system",
]
