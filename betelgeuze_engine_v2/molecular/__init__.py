"""Canonical all-atom molecular representation for engine v2."""

from .legacy import (
    LEGACY_ADAPTER_VERSION,
    LEGACY_METADATA_KEY,
    LegacyAdapterError,
    all_atom_to_legacy_state,
    from_legacy_engine_state,
    legacy_state_to_all_atom,
    to_legacy_engine_state,
)
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_element_symbol,
    element_for_atomic_number,
)
from .validation import (
    MolecularValidationError,
    ValidationIssue,
    ValidationReport,
    require_valid_all_atom_system,
    validate_all_atom_system,
)

__all__ = [
    "LEGACY_ADAPTER_VERSION",
    "LEGACY_METADATA_KEY",
    "AllAtomSystem",
    "Atom",
    "Bond",
    "Chain",
    "LegacyAdapterError",
    "MolecularValidationError",
    "Residue",
    "StructureProvenance",
    "UnitCell",
    "ValidationIssue",
    "ValidationReport",
    "all_atom_to_legacy_state",
    "atomic_number_for_element",
    "canonical_element_symbol",
    "element_for_atomic_number",
    "from_legacy_engine_state",
    "legacy_state_to_all_atom",
    "require_valid_all_atom_system",
    "to_legacy_engine_state",
    "validate_all_atom_system",
]
