"""Betelgeuze independent molecular engine v2.

Only stable, versioned data and sparse geometry contracts are re-exported from
the package root.  Scientific solvers can evolve behind these boundaries.
"""

from .contracts import ALL_ATOM_SCHEMA_ID, ENGINE_API_VERSION
from .engine import (
    REFERENCE_CLAIM_BLOCKERS,
    REFERENCE_EXECUTION_MODE,
    RIGID_PROJECTION_NOTE,
    ClaimBlocker,
    EngineExecutionProvenance,
    IndependentEngineV2,
    IndependentEngineV2Config,
    IndependentEngineV2Result,
    PeriodicReferencePathError,
    run_internal_cpu_reference,
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
    CompactNeighborList,
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from .molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    require_valid_all_atom_system,
    validate_all_atom_system,
)

__version__ = ENGINE_API_VERSION

__all__ = [
    "ALL_ATOM_SCHEMA_ID",
    "ATOM_FEATURE_NAMES",
    "ATOM_FEATURE_SCHEMA_VERSION",
    "ENGINE_API_VERSION",
    "REFERENCE_CLAIM_BLOCKERS",
    "REFERENCE_EXECUTION_MODE",
    "RIGID_PROJECTION_NOTE",
    "AllAtomSystem",
    "Atom",
    "AtomFeatureBatch",
    "Bond",
    "Chain",
    "ClaimBlocker",
    "CompactNeighborList",
    "EngineExecutionProvenance",
    "IndependentEngineV2",
    "IndependentEngineV2Config",
    "IndependentEngineV2Result",
    "MAX_COMPACT_ATOMS_PER_CELL",
    "MAX_COMPACT_NEIGHBORS",
    "PeriodicReferencePathError",
    "NeighborOverflowError",
    "RadiusGraphConfig",
    "Residue",
    "StructureProvenance",
    "UnitCell",
    "build_compact_radius_graph",
    "build_deterministic_atom_features",
    "require_valid_all_atom_system",
    "run_internal_cpu_reference",
    "validate_all_atom_system",
]
