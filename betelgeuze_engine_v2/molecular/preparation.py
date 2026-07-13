"""Fail-closed molecular preparation inventory for canonical typed state.

The v2 policy records only facts visible in :class:`AllAtomSystem`.  It does
not infer missing atoms or residues, hydrogen completeness, protonation,
tautomers, chemical roles, or parameterability.  Parser-marker origins are
reported only as metadata observations bound to the report and raw-source
digest; they are not part of canonical topology identity and are not chemical
truth claims.  ``parser_observation_self_consistent`` is an unkeyed internal
consistency result, not source authentication or a raw-source reparse.
Consequently this report can never authorize numeric preparation or product
claims.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .observation import attached_parser_observation_sha256_matches
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    CanonicalTopologyError,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import validate_all_atom_system


PREPARATION_REPORT_SCHEMA_VERSION = "1.4.0"
PREPARATION_POLICY_ID = "canonical_preparation_inventory_fail_closed_v2"
MAX_PREPARATION_AUDIT_ATOMS = 100_000
MAX_PREPARATION_AUDIT_BONDS = 200_000
MAX_PREPARATION_AUDIT_RESIDUES = 100_000
MAX_PREPARATION_AUDIT_CHAINS = 100_000
PREPARATION_UNASSESSED_ASPECTS = (
    "missing_atoms",
    "missing_residues",
    "hydrogen_completeness",
    "protonation",
    "tautomer",
    "aromaticity_perception",
    "formal_charge_assignment",
    "water_roles",
    "ion_roles",
    "metal_roles_and_coordination",
    "cofactor_roles",
    "modified_residue_identity",
)

_NON_POLYMER_LIKE_ENTITY_TYPES = frozenset(
    {"non_polymer", "branched", "macrolide"}
)
_ALWAYS_BLOCKERS = (
    "preparation_not_assessed",
    *(f"{aspect}_not_assessed" for aspect in PREPARATION_UNASSESSED_ASPECTS),
    "chemical_state_normalization_not_attempted",
)
_HYDROGEN_ORIGINS = frozenset(
    {
        "metadata_observed_parser_source",
        "metadata_observed_adapter_bracket_expanded",
        "metadata_observed_adapter_implicit_expanded",
        "unknown",
    }
)
_FORMAL_CHARGE_ORIGINS = frozenset(
    {
        "metadata_observed_pdb_atom_field",
        "metadata_observed_pdb_missing",
        "metadata_observed_mmcif_atom_site",
        "metadata_observed_mmcif_missing",
        "metadata_observed_sdf_v2000_atom_block",
        "metadata_observed_sdf_v2000_m_chg",
        "metadata_observed_smiles_source_adapter",
        "metadata_observed_adapter_generated_hydrogen",
        "unclassified_known",
        "unclassified_unknown",
    }
)
_UNKNOWN_FORMAL_CHARGE_ORIGINS = frozenset(
    {
        "metadata_observed_pdb_missing",
        "metadata_observed_mmcif_missing",
        "unclassified_unknown",
    }
)
_AROMATIC_ANNOTATION_ORIGINS = frozenset(
    {
        "absent",
        "metadata_observed_sdf_v2000_bond_type_4_projection",
        "metadata_observed_smiles_adapter_aromatic",
        "unclassified_present",
    }
)
_UNRECOGNIZED_PARSER_PEDIGREE_ID = "unrecognized"
_RECOGNIZED_PARSER_PEDIGREES = {
    "pdb": (
        "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_pdb",
        "1.8.0",
        "betelgeuze.pdb_parser/1.8.0",
    ),
    "mmcif": (
        "betelgeuze_engine_v2.molecular.pdb_mmcif.parse_mmcif",
        "1.9.0",
        "betelgeuze.mmcif_parser/1.9.0",
    ),
    "sdf_v2000": (
        "betelgeuze_engine_v2.molecular.sdf_v2000",
        "1.5.0",
        "betelgeuze.sdf_v2000_parser/1.5.0",
    ),
    "smiles": (
        "betelgeuze_strict_smiles",
        "1.4.0",
        "betelgeuze.smiles_parser/1.4.0",
    ),
}
_RECOGNIZED_PEDIGREE_IDS_BY_FORMAT = {
    source_format: pedigree[2]
    for source_format, pedigree in _RECOGNIZED_PARSER_PEDIGREES.items()
}
_MAX_REPORT_JSON_INTEGER = (1 << 53) - 1


def _validate_count(name: str, value: Any) -> None:
    if type(value) is not int or value < 0:
        raise TypeError(f"{name} must be a non-negative integer")
    if value > _MAX_REPORT_JSON_INTEGER:
        raise ValueError(
            f"{name} exceeds the interoperable JSON integer range"
        )


def _validate_count_table(name: str, value: Any) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")
    previous: str | None = None
    for entry in value:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or type(entry[1]) is not int
            or entry[1] <= 0
        ):
            raise TypeError(
                f"{name} entries must be string/positive integer pairs"
            )
        if entry[1] > _MAX_REPORT_JSON_INTEGER:
            raise ValueError(
                f"{name} count exceeds the interoperable JSON integer range"
            )
        if previous is not None and entry[0] <= previous:
            raise ValueError(f"{name} keys must be unique and sorted")
        previous = entry[0]


@dataclass(frozen=True)
class MolecularPreparationReport:
    policy_id: str
    system_schema_id: str
    source_format: str
    source_sha256: str | None
    source_digest_available: bool
    parser_pedigree_id: str
    parser_observation_self_consistent: bool
    canonical_topology_schema_id: str
    canonical_topology_sha256: str | None
    canonical_topology_digest_available: bool
    canonical_validation_valid: bool
    validation_error_codes: tuple[str, ...]
    coordinates_present: bool
    atom_count: int
    bond_count: int
    residue_count: int
    element_counts: tuple[tuple[str, int], ...]
    explicit_hydrogen_count: int
    hydrogen_origin_counts: tuple[tuple[str, int], ...]
    metadata_observed_source_hydrogen_count: int
    adapter_generated_hydrogen_count: int
    unknown_hydrogen_origin_count: int
    unknown_formal_charge_count: int
    formal_charge_origin_counts: tuple[tuple[str, int], ...]
    net_formal_charge: int | None
    observed_aromatic_atom_count: int
    observed_aromatic_bond_count: int
    aromatic_annotation_origin: str
    entity_type_counts: tuple[tuple[str, int], ...]
    canonical_water_entity_type_residue_count: int
    single_atom_residue_count: int
    polymer_hetero_residue_count: int
    non_polymer_like_residue_count: int
    explicit_unknown_entity_type_residue_count: int
    missing_atom_count: None
    missing_residue_count: None
    unassessed_aspects: tuple[str, ...]
    blockers: tuple[str, ...]
    hydrogen_completeness_assessed: bool = False
    protonation_assessed: bool = False
    tautomer_assessed: bool = False
    aromaticity_perception_assessed: bool = False
    formal_charge_assignment_assessed: bool = False
    report_state_normalization_attempted: bool = False
    report_state_normalization_applied: bool = False
    preparation_assessed: bool = False
    preparation_ready: bool = False
    claim_safe: bool = False

    def __post_init__(self) -> None:
        if self.policy_id != PREPARATION_POLICY_ID:
            raise ValueError("preparation report v2 requires the fixed policy")
        if type(self.system_schema_id) is not str or not self.system_schema_id:
            raise TypeError("system_schema_id must be a nonempty string")
        if type(self.source_format) is not str:
            raise TypeError("source_format must be a string")
        if self.canonical_topology_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID:
            raise ValueError(
                "preparation report v2 requires the fixed canonical topology schema"
            )
        boolean_fields = {
            "source_digest_available": self.source_digest_available,
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "canonical_topology_digest_available": self.canonical_topology_digest_available,
            "canonical_validation_valid": self.canonical_validation_valid,
            "coordinates_present": self.coordinates_present,
            "hydrogen_completeness_assessed": self.hydrogen_completeness_assessed,
            "protonation_assessed": self.protonation_assessed,
            "tautomer_assessed": self.tautomer_assessed,
            "aromaticity_perception_assessed": self.aromaticity_perception_assessed,
            "formal_charge_assignment_assessed": self.formal_charge_assignment_assessed,
            "report_state_normalization_attempted": self.report_state_normalization_attempted,
            "report_state_normalization_applied": self.report_state_normalization_applied,
            "preparation_assessed": self.preparation_assessed,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
        }
        invalid_boolean = next(
            (name for name, value in boolean_fields.items() if type(value) is not bool),
            None,
        )
        if invalid_boolean is not None:
            raise TypeError(f"{invalid_boolean} must be a boolean")
        if self.source_digest_available != (self.source_sha256 is not None):
            raise ValueError(
                "source_digest_available must match source_sha256"
            )
        if self.source_sha256 is not None and (
            type(self.source_sha256) is not str
            or len(self.source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_sha256
            )
        ):
            raise ValueError("source_sha256 must be lowercase SHA-256 or None")
        if type(self.parser_pedigree_id) is not str:
            raise TypeError("parser_pedigree_id must be a string")
        expected_pedigree_id = _RECOGNIZED_PEDIGREE_IDS_BY_FORMAT.get(
            self.source_format
        )
        if self.parser_observation_self_consistent:
            if (
                not self.source_digest_available
                or self.parser_pedigree_id != expected_pedigree_id
                or not self.canonical_validation_valid
                or not self.canonical_topology_digest_available
            ):
                raise ValueError(
                    "self-consistent parser observation requires valid digested canonical state, the current parser profile, and a source digest"
                )
        elif self.parser_pedigree_id != _UNRECOGNIZED_PARSER_PEDIGREE_ID:
            raise ValueError(
                "unrecognized parser pedigree requires the fixed unrecognized identifier"
            )
        if self.canonical_topology_digest_available != (
            self.canonical_topology_sha256 is not None
        ):
            raise ValueError(
                "canonical_topology_digest_available must match canonical_topology_sha256"
            )
        if self.canonical_topology_sha256 is not None and (
            type(self.canonical_topology_sha256) is not str
            or len(self.canonical_topology_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.canonical_topology_sha256
            )
        ):
            raise ValueError("canonical_topology_sha256 must be lowercase SHA-256 or None")
        if self.canonical_topology_digest_available and not self.canonical_validation_valid:
            raise ValueError(
                "canonical topology digest cannot be available for an invalid canonical system"
            )
        for name in (
            "atom_count",
            "bond_count",
            "residue_count",
            "explicit_hydrogen_count",
            "metadata_observed_source_hydrogen_count",
            "adapter_generated_hydrogen_count",
            "unknown_hydrogen_origin_count",
            "unknown_formal_charge_count",
            "observed_aromatic_atom_count",
            "observed_aromatic_bond_count",
            "canonical_water_entity_type_residue_count",
            "single_atom_residue_count",
            "polymer_hetero_residue_count",
            "non_polymer_like_residue_count",
            "explicit_unknown_entity_type_residue_count",
        ):
            _validate_count(name, getattr(self, name))
        _validate_count_table("element_counts", self.element_counts)
        _validate_count_table("entity_type_counts", self.entity_type_counts)
        _validate_count_table("hydrogen_origin_counts", self.hydrogen_origin_counts)
        _validate_count_table(
            "formal_charge_origin_counts",
            self.formal_charge_origin_counts,
        )
        if sum(count for _, count in self.element_counts) != self.atom_count:
            raise ValueError("element_counts must sum to atom_count")
        if sum(count for _, count in self.entity_type_counts) != self.residue_count:
            raise ValueError("entity_type_counts must sum to residue_count")
        element_count_map = dict(self.element_counts)
        entity_count_map = dict(self.entity_type_counts)
        if self.explicit_hydrogen_count != element_count_map.get("H", 0):
            raise ValueError("explicit_hydrogen_count must match element_counts")
        hydrogen_origin_map = dict(self.hydrogen_origin_counts)
        if not set(hydrogen_origin_map).issubset(_HYDROGEN_ORIGINS):
            raise ValueError("hydrogen_origin_counts contains an unsupported origin")
        if sum(hydrogen_origin_map.values()) != self.explicit_hydrogen_count:
            raise ValueError(
                "hydrogen_origin_counts must sum to explicit_hydrogen_count"
            )
        if self.metadata_observed_source_hydrogen_count != hydrogen_origin_map.get(
            "metadata_observed_parser_source", 0
        ):
            raise ValueError(
                "metadata_observed_source_hydrogen_count must match hydrogen_origin_counts"
            )
        expected_adapter_hydrogens = sum(
            hydrogen_origin_map.get(origin, 0)
            for origin in (
                "metadata_observed_adapter_bracket_expanded",
                "metadata_observed_adapter_implicit_expanded",
            )
        )
        if self.adapter_generated_hydrogen_count != expected_adapter_hydrogens:
            raise ValueError(
                "adapter_generated_hydrogen_count must match hydrogen_origin_counts"
            )
        if self.unknown_hydrogen_origin_count != hydrogen_origin_map.get(
            "unknown", 0
        ):
            raise ValueError(
                "unknown_hydrogen_origin_count must match hydrogen_origin_counts"
            )
        metadata_observed_hydrogen_origins = set(hydrogen_origin_map) - {
            "unknown"
        }
        if (
            metadata_observed_hydrogen_origins
            and not self.parser_observation_self_consistent
        ):
            raise ValueError(
                "metadata-observed hydrogen origins require a self-consistent parser observation"
            )
        if metadata_observed_hydrogen_origins and not self.canonical_validation_valid:
            raise ValueError(
                "metadata-observed hydrogen origins require valid canonical state"
            )
        adapter_hydrogen_origins = {
            "metadata_observed_adapter_bracket_expanded",
            "metadata_observed_adapter_implicit_expanded",
        }
        if (
            set(hydrogen_origin_map) & adapter_hydrogen_origins
            and self.source_format != "smiles"
        ):
            raise ValueError(
                "adapter-expanded hydrogen origins require source_format smiles"
            )
        if self.unknown_formal_charge_count > self.atom_count:
            raise ValueError("unknown_formal_charge_count cannot exceed atom_count")
        formal_charge_origin_map = dict(self.formal_charge_origin_counts)
        if not set(formal_charge_origin_map).issubset(_FORMAL_CHARGE_ORIGINS):
            raise ValueError(
                "formal_charge_origin_counts contains an unsupported origin"
            )
        if sum(formal_charge_origin_map.values()) != self.atom_count:
            raise ValueError("formal_charge_origin_counts must sum to atom_count")
        unknown_origin_count = sum(
            formal_charge_origin_map.get(origin, 0)
            for origin in _UNKNOWN_FORMAL_CHARGE_ORIGINS
        )
        if unknown_origin_count != self.unknown_formal_charge_count:
            raise ValueError(
                "unknown formal-charge origins must match unknown_formal_charge_count"
            )
        format_charge_origins = {
            "pdb": {
                "metadata_observed_pdb_atom_field",
                "metadata_observed_pdb_missing",
            },
            "mmcif": {
                "metadata_observed_mmcif_atom_site",
                "metadata_observed_mmcif_missing",
            },
            "sdf_v2000": {
                "metadata_observed_sdf_v2000_atom_block",
                "metadata_observed_sdf_v2000_m_chg",
            },
            "smiles": {
                "metadata_observed_smiles_source_adapter",
                "metadata_observed_adapter_generated_hydrogen",
            },
        }
        metadata_observed_charge_origins = set(formal_charge_origin_map) - {
            "unclassified_known",
            "unclassified_unknown",
        }
        if metadata_observed_charge_origins:
            if not self.canonical_validation_valid:
                raise ValueError(
                    "metadata-observed formal-charge origins require valid canonical state"
                )
            if not self.parser_observation_self_consistent:
                raise ValueError(
                    "metadata-observed formal-charge origins require a self-consistent parser observation"
                )
            if not metadata_observed_charge_origins.issubset(
                format_charge_origins.get(self.source_format, set())
            ):
                raise ValueError(
                    "formal-charge origins are incompatible with source_format"
                )
        if self.observed_aromatic_atom_count > self.atom_count:
            raise ValueError("observed_aromatic_atom_count cannot exceed atom_count")
        if self.observed_aromatic_bond_count > self.bond_count:
            raise ValueError("observed_aromatic_bond_count cannot exceed bond_count")
        if self.aromatic_annotation_origin not in _AROMATIC_ANNOTATION_ORIGINS:
            raise ValueError("aromatic_annotation_origin is unsupported")
        aromatic_annotations_present = bool(
            self.observed_aromatic_atom_count or self.observed_aromatic_bond_count
        )
        if (self.aromatic_annotation_origin == "absent") != (
            not aromatic_annotations_present
        ):
            raise ValueError(
                "aromatic_annotation_origin is inconsistent with observed state"
            )
        if (
            self.aromatic_annotation_origin
            == "metadata_observed_sdf_v2000_bond_type_4_projection"
            and self.source_format != "sdf_v2000"
        ):
            raise ValueError(
                "SDF aromatic provenance requires source_format sdf_v2000"
            )
        if (
            self.aromatic_annotation_origin
            == "metadata_observed_smiles_adapter_aromatic"
            and self.source_format != "smiles"
        ):
            raise ValueError(
                "SMILES aromatic provenance requires source_format smiles"
            )
        if (
            self.aromatic_annotation_origin
            not in {"absent", "unclassified_present"}
            and not self.parser_observation_self_consistent
        ):
            raise ValueError(
                "metadata-observed aromatic origin requires a self-consistent parser observation"
            )
        if (
            self.aromatic_annotation_origin
            not in {"absent", "unclassified_present"}
            and not self.canonical_validation_valid
        ):
            raise ValueError(
                "metadata-observed aromatic origin requires valid canonical state"
            )
        residue_subset_counts = (
            self.canonical_water_entity_type_residue_count,
            self.single_atom_residue_count,
            self.polymer_hetero_residue_count,
            self.non_polymer_like_residue_count,
            self.explicit_unknown_entity_type_residue_count,
        )
        if any(count > self.residue_count for count in residue_subset_counts):
            raise ValueError("residue subset counts cannot exceed residue_count")
        if self.canonical_water_entity_type_residue_count != (
            entity_count_map.get("water", 0)
        ):
            raise ValueError(
                "canonical_water_entity_type_residue_count must match "
                "entity_type_counts"
            )
        if self.explicit_unknown_entity_type_residue_count != entity_count_map.get(
            "unknown", 0
        ):
            raise ValueError(
                "explicit_unknown_entity_type_residue_count must match entity_type_counts"
            )
        expected_non_polymer_like = sum(
            entity_count_map.get(entity_type, 0)
            for entity_type in _NON_POLYMER_LIKE_ENTITY_TYPES
        )
        if self.non_polymer_like_residue_count != expected_non_polymer_like:
            raise ValueError(
                "non_polymer_like_residue_count must match entity_type_counts"
            )
        if self.polymer_hetero_residue_count > entity_count_map.get("polymer", 0):
            raise ValueError(
                "polymer_hetero_residue_count cannot exceed typed polymer residues"
            )
        if self.unknown_formal_charge_count:
            if self.net_formal_charge is not None:
                raise ValueError("net_formal_charge must be None when any charge is unknown")
        elif type(self.net_formal_charge) is not int:
            raise TypeError("net_formal_charge must be an integer when all charges are known")
        elif abs(self.net_formal_charge) > _MAX_REPORT_JSON_INTEGER:
            raise ValueError(
                "net_formal_charge exceeds the interoperable JSON integer range"
            )
        if self.missing_atom_count is not None or self.missing_residue_count is not None:
            raise ValueError("missing atom and residue counts are not assessed in report v2")
        if self.unassessed_aspects != PREPARATION_UNASSESSED_ASPECTS:
            raise ValueError("preparation report v2 requires the fixed unassessed aspects")
        assessment_flags = (
            self.hydrogen_completeness_assessed,
            self.protonation_assessed,
            self.tautomer_assessed,
            self.aromaticity_perception_assessed,
            self.formal_charge_assignment_assessed,
            self.report_state_normalization_attempted,
            self.report_state_normalization_applied,
            self.preparation_assessed,
            self.preparation_ready,
            self.claim_safe,
        )
        if any(assessment_flags):
            raise ValueError(
                "preparation report v2 cannot promote chemical-state assessment, normalization, readiness, or claims"
            )
        if (
            type(self.validation_error_codes) is not tuple
            or not all(type(value) is str and value for value in self.validation_error_codes)
            or type(self.blockers) is not tuple
            or not all(type(value) is str and value for value in self.blockers)
        ):
            raise TypeError("validation errors and blockers must be tuples of nonempty strings")
        if self.validation_error_codes != tuple(sorted(set(self.validation_error_codes))):
            raise ValueError(
                "validation_error_codes must be unique and sorted"
            )
        if self.canonical_validation_valid != (not self.validation_error_codes):
            raise ValueError(
                "canonical_validation_valid must match validation_error_codes"
            )
        expected_blockers = list(_ALWAYS_BLOCKERS)
        if not self.canonical_validation_valid:
            expected_blockers.append("canonical_validation_errors_present")
        if not self.canonical_topology_digest_available:
            expected_blockers.append("canonical_topology_digest_unavailable")
        if not self.coordinates_present:
            expected_blockers.append("coordinates_missing")
        if self.unknown_formal_charge_count > 0:
            expected_blockers.append("formal_charge_unknown_for_some_atoms")
        if self.unknown_hydrogen_origin_count > 0:
            expected_blockers.append("hydrogen_origin_unknown_for_some_atoms")
        if self.adapter_generated_hydrogen_count > 0:
            expected_blockers.append(
                "adapter_expanded_hydrogens_not_independently_valence_verified"
            )
        if aromatic_annotations_present:
            expected_blockers.append(
                "aromaticity_source_or_adapter_state_not_independently_perceived"
            )
        if self.blockers != tuple(expected_blockers):
            raise ValueError(
                "blockers must exactly match the canonical ordered blocker set"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PREPARATION_REPORT_SCHEMA_VERSION,
            "policy_id": self.policy_id,
            "system_schema_id": self.system_schema_id,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "source_digest_available": self.source_digest_available,
            "parser_pedigree_id": self.parser_pedigree_id,
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "canonical_topology_digest_available": self.canonical_topology_digest_available,
            "canonical_validation_valid": self.canonical_validation_valid,
            "validation_error_codes": list(self.validation_error_codes),
            "coordinates_present": self.coordinates_present,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "residue_count": self.residue_count,
            "element_counts": [list(item) for item in self.element_counts],
            "explicit_hydrogen_count": self.explicit_hydrogen_count,
            "hydrogen_origin_counts": [
                list(item) for item in self.hydrogen_origin_counts
            ],
            "metadata_observed_source_hydrogen_count": (
                self.metadata_observed_source_hydrogen_count
            ),
            "adapter_generated_hydrogen_count": (
                self.adapter_generated_hydrogen_count
            ),
            "unknown_hydrogen_origin_count": self.unknown_hydrogen_origin_count,
            "unknown_formal_charge_count": self.unknown_formal_charge_count,
            "formal_charge_origin_counts": [
                list(item) for item in self.formal_charge_origin_counts
            ],
            "net_formal_charge": self.net_formal_charge,
            "observed_aromatic_atom_count": self.observed_aromatic_atom_count,
            "observed_aromatic_bond_count": self.observed_aromatic_bond_count,
            "aromatic_annotation_origin": self.aromatic_annotation_origin,
            "entity_type_counts": [list(item) for item in self.entity_type_counts],
            "canonical_water_entity_type_residue_count": (
                self.canonical_water_entity_type_residue_count
            ),
            "single_atom_residue_count": self.single_atom_residue_count,
            "polymer_hetero_residue_count": self.polymer_hetero_residue_count,
            "non_polymer_like_residue_count": self.non_polymer_like_residue_count,
            "explicit_unknown_entity_type_residue_count": self.explicit_unknown_entity_type_residue_count,
            "missing_atom_count": self.missing_atom_count,
            "missing_residue_count": self.missing_residue_count,
            "unassessed_aspects": list(self.unassessed_aspects),
            "blockers": list(self.blockers),
            "hydrogen_completeness_assessed": (
                self.hydrogen_completeness_assessed
            ),
            "protonation_assessed": self.protonation_assessed,
            "tautomer_assessed": self.tautomer_assessed,
            "aromaticity_perception_assessed": (
                self.aromaticity_perception_assessed
            ),
            "formal_charge_assignment_assessed": (
                self.formal_charge_assignment_assessed
            ),
            "report_state_normalization_attempted": (
                self.report_state_normalization_attempted
            ),
            "report_state_normalization_applied": (
                self.report_state_normalization_applied
            ),
            "preparation_assessed": self.preparation_assessed,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
        }

    @property
    def report_sha256(self) -> str:
        payload = json.dumps(
            self._core_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload


class PreparationCoverageError(RuntimeError):
    """Raised when a caller requires preparation that report v2 cannot establish."""

    def __init__(self, report: MolecularPreparationReport):
        self.report = report
        self.blockers = report.blockers
        preview = ", ".join(self.blockers[:6])
        suffix = "" if len(self.blockers) <= 6 else f", +{len(self.blockers) - 6} more"
        super().__init__(f"molecular preparation is not supported: {preview}{suffix}")


class PreparationCoverageLimitError(ValueError):
    """Raised before a preparation audit exceeds its fixed resource profile."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"preparation coverage limit exceeded: {code}: {detail}")


def _is_lowercase_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parser_observation_consistency(
    system: AllAtomSystem,
    *,
    canonical_validation_valid: bool,
) -> tuple[str | None, str, bool]:
    source_sha256 = (
        system.provenance.source_sha256
        if _is_lowercase_sha256(system.provenance.source_sha256)
        else None
    )
    expected = _RECOGNIZED_PARSER_PEDIGREES.get(
        system.provenance.source_format
    )
    digest_bindings_valid = False
    if canonical_validation_valid:
        try:
            digest_bindings_valid = (
                attached_canonical_topology_sha256_matches(system)
                and attached_parser_observation_sha256_matches(system)
            )
        except (TypeError, ValueError, OverflowError):
            digest_bindings_valid = False
    recognized = bool(
        source_sha256 is not None
        and expected is not None
        and system.provenance.parser_name == expected[0]
        and system.provenance.parser_version == expected[1]
        and digest_bindings_valid
    )
    return (
        source_sha256,
        expected[2] if recognized and expected is not None else _UNRECOGNIZED_PARSER_PEDIGREE_ID,
        recognized,
    )


def _coordinate_source_atom_marker_consistent(
    system: AllAtomSystem,
    atom: Any,
) -> bool:
    source_format = system.provenance.source_format
    if source_format == "pdb":
        return (
            atom.metadata.get("source_record") in ("ATOM", "HETATM")
            and type(atom.serial) is int
            and atom.serial > 0
            and atom.metadata.get("formal_charge_source")
            in ("pdb_columns_79_80", "missing_in_pdb")
        )
    if source_format == "mmcif":
        mmcif = atom.metadata.get("mmcif")
        atom_site = (
            mmcif.get("atom_site")
            if isinstance(mmcif, Mapping)
            else None
        )
        return (
            atom.metadata.get("source_record") in ("ATOM", "HETATM")
            and type(atom.serial) is int
            and atom.serial > 0
            and atom.metadata.get("formal_charge_source")
            in ("_atom_site.pdbx_formal_charge", "missing_in_mmcif")
            and isinstance(mmcif, Mapping)
            and isinstance(atom_site, Mapping)
            and type(mmcif.get("source_atom_site_id")) is str
            and bool(mmcif.get("source_atom_site_id"))
            and _mmcif_formal_charge_marker_consistent(atom, atom_site)
        )
    if source_format == "sdf_v2000":
        return (
            type(atom.metadata.get("sdf_source_atom_index")) is int
            and atom.metadata.get("sdf_source_atom_index") == atom.index + 1
            and atom.serial == atom.index + 1
            and type(atom.metadata.get("sdf_atom_map")) is int
            and atom.metadata.get("formal_charge_source")
            in ("sdf_v2000_atom_block", "sdf_v2000_m_chg")
        )
    return False


def _mmcif_formal_charge_marker_consistent(
    atom: Any,
    atom_site: Mapping[str, Any],
) -> bool:
    key = "_atom_site.pdbx_formal_charge"
    if key not in atom_site:
        return not atom.formal_charge_known and atom.formal_charge == 0
    payload = atom_site.get(key)
    if not isinstance(payload, Mapping):
        return False
    value = payload.get("value")
    if payload.get("quoted") is not False or payload.get("multiline") is not False:
        return False
    if not atom.formal_charge_known:
        return atom.formal_charge == 0 and value in (".", "?")
    if type(value) is not str or not value:
        return False
    unsigned = value[1:] if value[:1] in ("+", "-") else value
    if not unsigned or any(character not in "0123456789" for character in unsigned):
        return False
    significant_digits = unsigned.lstrip("0") or "0"
    if len(significant_digits) > 5:
        return False
    magnitude = int(significant_digits, 10)
    parsed = -magnitude if value.startswith("-") else magnitude
    return parsed == atom.formal_charge


def _smiles_source_atom_marker_consistent(
    atom: Any,
    *,
    inventory_valid: bool,
    source_atom_count: int,
    generated_atom_indices: frozenset[int],
) -> bool:
    return (
        inventory_valid
        and 0 <= atom.index < source_atom_count
        and atom.index not in generated_atom_indices
        and
        type(atom.metadata.get("source_atom_index")) is int
        and atom.metadata.get("source_atom_index") == atom.index
        and atom.metadata.get("source_atom_order_preserved") is True
        and atom.metadata.get("manually_expanded") is not True
        and atom.metadata.get("parent_source_atom_index") is None
        and atom.metadata.get("hydrogen_ordinal") is None
        and atom.metadata.get("formal_charge_source")
        == "smiles_source_via_pinned_rdkit"
    )


def _smiles_generated_hydrogen_marker_consistent(
    system: AllAtomSystem,
    atom: Any,
    raw_origin: Any,
    *,
    atoms_by_index: Mapping[int, Any],
    bonds_by_atom: Mapping[int, tuple[Any, ...]],
    source_inventory_valid: bool,
    source_atom_count: int,
    generated_atom_indices: frozenset[int],
) -> bool:
    parent_index = atom.metadata.get("parent_source_atom_index")
    ordinal = atom.metadata.get("hydrogen_ordinal")
    if (
        type(raw_origin) is not str
        or raw_origin not in {"bracket_explicit", "implicit"}
        or atom.element != "H"
        or atom.atomic_number != 1
        or atom.formal_charge != 0
        or not atom.formal_charge_known
        or atom.metadata.get("manually_expanded") is not True
        or atom.metadata.get("source_atom_index") is not None
        or type(parent_index) is not int
        or type(ordinal) is not int
        or ordinal < 1
        or parent_index == atom.index
    ):
        return False
    parent = atoms_by_index.get(parent_index)
    if parent is None or not _smiles_source_atom_marker_consistent(
        parent,
        inventory_valid=source_inventory_valid,
        source_atom_count=source_atom_count,
        generated_atom_indices=generated_atom_indices,
    ):
        return False
    attached = bonds_by_atom.get(atom.index, ())
    if len(attached) != 1:
        return False
    bond = attached[0]
    return (
        {bond.atom_i, bond.atom_j} == {atom.index, parent_index}
        and bond.order == 1.0
        and not bond.aromatic
        and bond.source == "manual_hydrogen_expansion"
        and bond.metadata.get("parent_source_atom_index") == parent_index
        and bond.metadata.get("hydrogen_origin") == raw_origin
        and type(bond.metadata.get("hydrogen_ordinal")) is int
        and bond.metadata.get("hydrogen_ordinal") == ordinal
        and atom.metadata.get("formal_charge_source")
        == "manual_hydrogen_expansion_neutral"
    )


def _smiles_source_inventory(
    system: AllAtomSystem,
) -> tuple[bool, int, frozenset[int]]:
    source_atom_count = system.metadata.get("source_atom_count")
    generated_hydrogen_count = system.metadata.get(
        "generated_hydrogen_count"
    )
    coverage = system.provenance.metadata.get("coverage")
    if (
        type(source_atom_count) is not int
        or source_atom_count < 1
        or source_atom_count > len(system.atoms)
        or type(generated_hydrogen_count) is not int
        or generated_hydrogen_count < 0
        or source_atom_count + generated_hydrogen_count != len(system.atoms)
        or not isinstance(coverage, Mapping)
        or type(coverage.get("source_atom_count")) is not int
        or type(coverage.get("expanded_atom_count")) is not int
        or type(coverage.get("generated_hydrogen_count")) is not int
        or coverage.get("source_atom_count") != source_atom_count
        or coverage.get("expanded_atom_count") != len(system.atoms)
        or coverage.get("generated_hydrogen_count")
        != generated_hydrogen_count
    ):
        return False, 0, frozenset()

    generated_atom_indices: set[int] = set()
    manual_bond_count = 0
    for bond in system.bonds:
        if bond.source != "manual_hydrogen_expansion":
            continue
        manual_bond_count += 1
        parent_index = bond.metadata.get("parent_source_atom_index")
        if type(parent_index) is not int or parent_index not in {
            bond.atom_i,
            bond.atom_j,
        }:
            return False, 0, frozenset()
        generated_atom_indices.add(
            bond.atom_j if bond.atom_i == parent_index else bond.atom_i
        )
    expected_generated_indices = set(
        range(source_atom_count, len(system.atoms))
    )
    source_indices = {
        atom.metadata.get("source_atom_index")
        for atom in system.atoms
        if type(atom.metadata.get("source_atom_index")) is int
        and atom.metadata.get("source_atom_order_preserved") is True
    }
    valid = (
        manual_bond_count == generated_hydrogen_count
        and generated_atom_indices == expected_generated_indices
        and source_indices == set(range(source_atom_count))
    )
    return valid, source_atom_count, frozenset(generated_atom_indices)


def analyze_molecular_preparation(system: AllAtomSystem) -> MolecularPreparationReport:
    """Inventory canonical preparation state without guessing missing chemistry."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    atom_count = len(system.atoms)
    bond_count = len(system.bonds)
    residue_count = len(system.residues)
    chain_count = len(system.chains)
    if atom_count > MAX_PREPARATION_AUDIT_ATOMS:
        raise PreparationCoverageLimitError(
            "atom_limit_exceeded",
            f"atom_count exceeds {MAX_PREPARATION_AUDIT_ATOMS}",
        )
    if bond_count > MAX_PREPARATION_AUDIT_BONDS:
        raise PreparationCoverageLimitError(
            "bond_limit_exceeded",
            f"bond_count exceeds {MAX_PREPARATION_AUDIT_BONDS}",
        )
    if residue_count > MAX_PREPARATION_AUDIT_RESIDUES:
        raise PreparationCoverageLimitError(
            "residue_limit_exceeded",
            f"residue_count exceeds {MAX_PREPARATION_AUDIT_RESIDUES}",
        )
    if chain_count > MAX_PREPARATION_AUDIT_CHAINS:
        raise PreparationCoverageLimitError(
            "chain_limit_exceeded",
            f"chain_count exceeds {MAX_PREPARATION_AUDIT_CHAINS}",
        )
    validation = validate_all_atom_system(system)
    validation_error_codes = tuple(
        sorted({issue.code for issue in validation.errors})
    )
    topology_sha256: str | None = None
    if validation.valid:
        try:
            topology_sha256 = canonical_topology_sha256(system)
        except (CanonicalTopologyError, OverflowError, ValueError):
            topology_sha256 = None

    source_sha256, parser_pedigree_id, parser_observation_self_consistent = (
        _parser_observation_consistency(
            system,
            canonical_validation_valid=validation.valid,
        )
    )
    atoms_by_index = {atom.index: atom for atom in system.atoms}
    mutable_bonds_by_atom: dict[int, list[Any]] = {}
    for bond in system.bonds:
        mutable_bonds_by_atom.setdefault(bond.atom_i, []).append(bond)
        mutable_bonds_by_atom.setdefault(bond.atom_j, []).append(bond)
    bonds_by_atom = {
        atom_index: tuple(bonds)
        for atom_index, bonds in mutable_bonds_by_atom.items()
    }
    if (
        validation.valid
        and parser_observation_self_consistent
        and system.provenance.source_format == "smiles"
    ):
        (
            smiles_source_inventory_valid,
            smiles_source_atom_count,
            smiles_generated_atom_indices,
        ) = _smiles_source_inventory(system)
    else:
        smiles_source_inventory_valid = False
        smiles_source_atom_count = 0
        smiles_generated_atom_indices = frozenset()

    element_counts = tuple(sorted(Counter(atom.element for atom in system.atoms).items()))
    entity_type_counts = tuple(
        sorted(Counter(residue.entity_type for residue in system.residues).items())
    )
    unknown_formal_charge_count = sum(
        not atom.formal_charge_known for atom in system.atoms
    )
    hydrogen_origins: Counter[str] = Counter()
    for atom in system.atoms:
        if atom.element != "H":
            continue
        raw_origin = atom.metadata.get("hydrogen_origin")
        if (
            validation.valid
            and parser_observation_self_consistent
            and raw_origin == "source"
            and (
                _coordinate_source_atom_marker_consistent(system, atom)
                or (
                    system.provenance.source_format == "smiles"
                    and _smiles_source_atom_marker_consistent(
                        atom,
                        inventory_valid=smiles_source_inventory_valid,
                        source_atom_count=smiles_source_atom_count,
                        generated_atom_indices=smiles_generated_atom_indices,
                    )
                )
            )
        ):
            origin = "metadata_observed_parser_source"
        elif (
            validation.valid
            and parser_observation_self_consistent
            and system.provenance.source_format == "smiles"
            and _smiles_generated_hydrogen_marker_consistent(
                system,
                atom,
                raw_origin,
                atoms_by_index=atoms_by_index,
                bonds_by_atom=bonds_by_atom,
                source_inventory_valid=smiles_source_inventory_valid,
                source_atom_count=smiles_source_atom_count,
                generated_atom_indices=smiles_generated_atom_indices,
            )
        ):
            origin = (
                "metadata_observed_adapter_bracket_expanded"
                if raw_origin == "bracket_explicit"
                else "metadata_observed_adapter_implicit_expanded"
            )
        else:
            origin = "unknown"
        hydrogen_origins[origin] += 1
    hydrogen_origin_counts = tuple(sorted(hydrogen_origins.items()))
    formal_charge_source_mapping = {
        (
            "pdb",
            "pdb_columns_79_80",
        ): "metadata_observed_pdb_atom_field",
        ("pdb", "missing_in_pdb"): "metadata_observed_pdb_missing",
        (
            "mmcif",
            "_atom_site.pdbx_formal_charge",
        ): "metadata_observed_mmcif_atom_site",
        (
            "mmcif",
            "missing_in_mmcif",
        ): "metadata_observed_mmcif_missing",
        (
            "sdf_v2000",
            "sdf_v2000_atom_block",
        ): "metadata_observed_sdf_v2000_atom_block",
        (
            "sdf_v2000",
            "sdf_v2000_m_chg",
        ): "metadata_observed_sdf_v2000_m_chg",
        (
            "smiles",
            "smiles_source_via_pinned_rdkit",
        ): "metadata_observed_smiles_source_adapter",
        (
            "smiles",
            "manual_hydrogen_expansion_neutral",
        ): "metadata_observed_adapter_generated_hydrogen",
    }
    formal_charge_origins: Counter[str] = Counter()
    for atom in system.atoms:
        raw_origin = atom.metadata.get("formal_charge_source")
        marker_consistent = False
        if validation.valid and parser_observation_self_consistent:
            if system.provenance.source_format in {"pdb", "mmcif", "sdf_v2000"}:
                marker_consistent = _coordinate_source_atom_marker_consistent(
                    system,
                    atom,
                )
                expected_interpretation = (
                    "explicit"
                    if atom.formal_charge_known
                    else "placeholder_zero_unknown"
                )
                if system.provenance.source_format in {"pdb", "mmcif"}:
                    marker_consistent = marker_consistent and (
                        atom.metadata.get("formal_charge_interpretation")
                        == expected_interpretation
                    )
            elif system.provenance.source_format == "smiles":
                marker_consistent = _smiles_source_atom_marker_consistent(
                    atom,
                    inventory_valid=smiles_source_inventory_valid,
                    source_atom_count=smiles_source_atom_count,
                    generated_atom_indices=smiles_generated_atom_indices,
                )
                if not marker_consistent and atom.element == "H":
                    marker_consistent = (
                        _smiles_generated_hydrogen_marker_consistent(
                            system,
                            atom,
                            atom.metadata.get("hydrogen_origin"),
                            atoms_by_index=atoms_by_index,
                            bonds_by_atom=bonds_by_atom,
                            source_inventory_valid=smiles_source_inventory_valid,
                            source_atom_count=smiles_source_atom_count,
                            generated_atom_indices=smiles_generated_atom_indices,
                        )
                    )
        origin = (
            formal_charge_source_mapping.get(
                (system.provenance.source_format, raw_origin)
            )
            if type(raw_origin) is str and marker_consistent
            else None
        )
        if origin is None:
            origin = (
                "unclassified_known"
                if atom.formal_charge_known
                else "unclassified_unknown"
            )
        elif atom.formal_charge_known and origin in _UNKNOWN_FORMAL_CHARGE_ORIGINS:
            origin = "unclassified_known"
        elif not atom.formal_charge_known and origin not in _UNKNOWN_FORMAL_CHARGE_ORIGINS:
            origin = "unclassified_unknown"
        formal_charge_origins[origin] += 1
    formal_charge_origin_counts = tuple(sorted(formal_charge_origins.items()))
    observed_aromatic_atom_count = sum(atom.aromatic for atom in system.atoms)
    observed_aromatic_bond_count = sum(bond.aromatic for bond in system.bonds)
    aromatic_atom_indices = {
        atom.index for atom in system.atoms if atom.aromatic
    }
    aromatic_bonds = tuple(bond for bond in system.bonds if bond.aromatic)
    aromatic_bond_endpoints = {
        atom_index
        for bond in aromatic_bonds
        for atom_index in (bond.atom_i, bond.atom_j)
    }
    sdf_aromatic_provenance = (
        validation.valid
        and parser_observation_self_consistent
        and system.provenance.source_format == "sdf_v2000"
        and bool(aromatic_bonds)
        and aromatic_atom_indices == aromatic_bond_endpoints
        and all(
            _coordinate_source_atom_marker_consistent(system, atom)
            for atom in system.atoms
            if atom.aromatic
        )
        and all(
            bond.source == "sdf_v2000"
            and bond.order == 1.5
            and type(bond.metadata.get("sdf_bond_type")) is int
            and bond.metadata.get("sdf_bond_type") == 4
            and type(bond.metadata.get("sdf_source_bond_index")) is int
            and bond.metadata.get("sdf_source_bond_index") == bond.index + 1
            and type(bond.metadata.get("sdf_source_atom_i")) is int
            and type(bond.metadata.get("sdf_source_atom_j")) is int
            and {
                bond.metadata.get("sdf_source_atom_i") - 1,
                bond.metadata.get("sdf_source_atom_j") - 1,
            }
            == {bond.atom_i, bond.atom_j}
            for bond in aromatic_bonds
        )
    )
    smiles_aromatic_provenance = (
        validation.valid
        and parser_observation_self_consistent
        and system.provenance.source_format == "smiles"
        and bool(aromatic_bonds)
        and aromatic_atom_indices == aromatic_bond_endpoints
        and all(
            bond.source == "smiles_source"
            and bond.order == 1.5
            and type(bond.metadata.get("source_bond_index")) is int
            and bond.metadata.get("source_bond_index") == bond.index
            for bond in aromatic_bonds
        )
        and all(
            _smiles_source_atom_marker_consistent(
                atom,
                inventory_valid=smiles_source_inventory_valid,
                source_atom_count=smiles_source_atom_count,
                generated_atom_indices=smiles_generated_atom_indices,
            )
            for atom in system.atoms
            if atom.aromatic
        )
    )
    if not (observed_aromatic_atom_count or observed_aromatic_bond_count):
        aromatic_annotation_origin = "absent"
    elif sdf_aromatic_provenance:
        aromatic_annotation_origin = (
            "metadata_observed_sdf_v2000_bond_type_4_projection"
        )
    elif smiles_aromatic_provenance:
        aromatic_annotation_origin = (
            "metadata_observed_smiles_adapter_aromatic"
        )
    else:
        aromatic_annotation_origin = "unclassified_present"
    blockers = list(_ALWAYS_BLOCKERS)
    if validation_error_codes:
        blockers.append("canonical_validation_errors_present")
    if topology_sha256 is None:
        blockers.append("canonical_topology_digest_unavailable")
    if not system.has_coordinates:
        blockers.append("coordinates_missing")
    if unknown_formal_charge_count:
        blockers.append("formal_charge_unknown_for_some_atoms")
    unknown_hydrogen_origin_count = hydrogen_origins.get("unknown", 0)
    adapter_generated_hydrogen_count = sum(
        hydrogen_origins.get(origin, 0)
        for origin in (
            "metadata_observed_adapter_bracket_expanded",
            "metadata_observed_adapter_implicit_expanded",
        )
    )
    if unknown_hydrogen_origin_count:
        blockers.append("hydrogen_origin_unknown_for_some_atoms")
    if adapter_generated_hydrogen_count:
        blockers.append(
            "adapter_expanded_hydrogens_not_independently_valence_verified"
        )
    if observed_aromatic_atom_count or observed_aromatic_bond_count:
        blockers.append(
            "aromaticity_source_or_adapter_state_not_independently_perceived"
        )

    return MolecularPreparationReport(
        policy_id=PREPARATION_POLICY_ID,
        system_schema_id=system.schema_id,
        source_format=system.provenance.source_format,
        source_sha256=source_sha256,
        source_digest_available=source_sha256 is not None,
        parser_pedigree_id=parser_pedigree_id,
        parser_observation_self_consistent=(
            parser_observation_self_consistent
        ),
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256=topology_sha256,
        canonical_topology_digest_available=topology_sha256 is not None,
        canonical_validation_valid=validation.valid,
        validation_error_codes=validation_error_codes,
        coordinates_present=system.has_coordinates,
        atom_count=len(system.atoms),
        bond_count=len(system.bonds),
        residue_count=len(system.residues),
        element_counts=element_counts,
        explicit_hydrogen_count=sum(atom.element == "H" for atom in system.atoms),
        hydrogen_origin_counts=hydrogen_origin_counts,
        metadata_observed_source_hydrogen_count=hydrogen_origins.get(
            "metadata_observed_parser_source", 0
        ),
        adapter_generated_hydrogen_count=adapter_generated_hydrogen_count,
        unknown_hydrogen_origin_count=unknown_hydrogen_origin_count,
        unknown_formal_charge_count=unknown_formal_charge_count,
        formal_charge_origin_counts=formal_charge_origin_counts,
        net_formal_charge=(
            None
            if unknown_formal_charge_count
            else sum(atom.formal_charge for atom in system.atoms)
        ),
        observed_aromatic_atom_count=observed_aromatic_atom_count,
        observed_aromatic_bond_count=observed_aromatic_bond_count,
        aromatic_annotation_origin=aromatic_annotation_origin,
        entity_type_counts=entity_type_counts,
        canonical_water_entity_type_residue_count=sum(
            residue.entity_type == "water"
            for residue in system.residues
        ),
        single_atom_residue_count=sum(
            len(residue.atom_indices) == 1 for residue in system.residues
        ),
        polymer_hetero_residue_count=sum(
            residue.entity_type == "polymer" and residue.hetero
            for residue in system.residues
        ),
        non_polymer_like_residue_count=sum(
            residue.entity_type in _NON_POLYMER_LIKE_ENTITY_TYPES
            for residue in system.residues
        ),
        explicit_unknown_entity_type_residue_count=sum(
            residue.entity_type == "unknown" for residue in system.residues
        ),
        missing_atom_count=None,
        missing_residue_count=None,
        unassessed_aspects=PREPARATION_UNASSESSED_ASPECTS,
        blockers=tuple(blockers),
    )


def require_supported_preparation(system: AllAtomSystem) -> MolecularPreparationReport:
    report = analyze_molecular_preparation(system)
    if not report.preparation_assessed or not report.preparation_ready:
        raise PreparationCoverageError(report)
    return report


__all__ = [
    "MAX_PREPARATION_AUDIT_ATOMS",
    "MAX_PREPARATION_AUDIT_BONDS",
    "MAX_PREPARATION_AUDIT_CHAINS",
    "MAX_PREPARATION_AUDIT_RESIDUES",
    "PREPARATION_POLICY_ID",
    "PREPARATION_REPORT_SCHEMA_VERSION",
    "PREPARATION_UNASSESSED_ASPECTS",
    "MolecularPreparationReport",
    "PreparationCoverageError",
    "PreparationCoverageLimitError",
    "analyze_molecular_preparation",
    "require_supported_preparation",
]
