"""Independent Engine v2 contract, molecular, and sparse-geometry package.

Later stacked PRs add AI primitives, the internal CPU orchestrator, legacy
adapters, and packaging without changing this ownership boundary.
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
from .features import (
    ATOM_FEATURE_NAMES,
    ATOM_FEATURE_SCHEMA_VERSION,
    AtomFeatureBatch,
    build_deterministic_atom_features,
)
from .geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    NEIGHBOR_SCHEMA_VERSION,
    CompactNeighborList,
    NeighborBuildDiagnostics,
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
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
    "ATOM_FEATURE_NAMES",
    "ATOM_FEATURE_SCHEMA_VERSION",
    "CHECKPOINT_SCHEMA_VERSION",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "ENGINE_API_VERSION",
    "ENGINE_RESULT_SCHEMA_VERSION",
    "MAX_COMPACT_ATOMS_PER_CELL",
    "MAX_COMPACT_NEIGHBORS",
    "NEIGHBOR_SCHEMA_VERSION",
    "RUNTIME_INPUT_SCHEMA_VERSION",
    "VERSION_TAXONOMY",
    "AllAtomSystem",
    "Atom",
    "AtomFeatureBatch",
    "Bond",
    "Chain",
    "ClaimStage",
    "CompactNeighborList",
    "MolecularValidationError",
    "NeighborBuildDiagnostics",
    "NeighborOverflowError",
    "QuantityDescriptor",
    "RadiusGraphConfig",
    "Residue",
    "StructureProvenance",
    "UNCALIBRATED_ENERGY",
    "UNCALIBRATED_FORCE",
    "UnitCell",
    "ValidationReport",
    "build_compact_radius_graph",
    "build_deterministic_atom_features",
    "canonical_coordinates_sha256",
    "canonical_system_sha256",
    "canonical_topology_sha256",
    "require_valid_all_atom_system",
    "validate_all_atom_system",
]
