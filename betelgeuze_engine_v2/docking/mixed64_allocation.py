"""Exact synthetic-only mixed64 proposal allocation contract.

The contract fixes candidate slots before coordinates, scores, validity results,
or benchmark outcomes exist.  Missing chemical/geometric features therefore
produce typed, denominator-preserving slot failures; they never reallocate a
slot to another lane.  Every V7 control source, independent SO(3) index,
true-conformer rank/SO(3) pair, and retained control source is fixed in its slot
receipt.  The module does not generate or execute molecular work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Final


FIXED_MIXED64_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64/1.0.0"
)
FIXED_MIXED64_ALLOCATION_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_allocation/2.0.0"
)
FIXED_MIXED64_SLOT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_slot/2.0.0"
)
FIXED_MIXED64_FEATURE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_feature_evidence/3.0.0"
)
FIXED_MIXED64_ATOMIC_FEATURE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_atomic_feature/1.0.0"
)
FIXED_MIXED64_CONFORMER_SOURCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_conformer_source/1.0.0"
)
FIXED_MIXED64_V7_CONTROL_SOURCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_v7_control_source/2.0.0"
)
FIXED_MIXED64_RETAINED_SOURCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_retained_source/1.0.0"
)
FIXED_MIXED64_CANDIDATE_COUNT: Final = 64

LANE_POCKET_CENTERED_CONTROLS: Final = "pocket_centered_controls"
LANE_UNIFORM_SOURCE_CONTROLS: Final = "uniform_source_controls"
LANE_DETERMINISTIC_INDEPENDENT_SO3: Final = "deterministic_independent_so3"
LANE_TRUE_CONFORMER_INDEPENDENT_SO3: Final = "true_conformer_independent_so3"
LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: Final = "ligand_donor_to_receptor_acceptor"
LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: Final = "ligand_acceptor_to_receptor_donor"
LANE_COMPLEMENTARY_CHARGE: Final = "complementary_charge"
LANE_AROMATIC_PLANE: Final = "aromatic_plane"
LANE_PRINCIPAL_AXIS_SHAPE: Final = "principal_axis_shape"
LANE_PAIRED_RETAINED_CONTROLS: Final = "paired_retained_controls"

ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: Final = (
    "single_ligand_donor_to_receptor_acceptor"
)
ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: Final = (
    "single_ligand_acceptor_to_receptor_donor"
)
ANCHOR_COMPLEMENTARY_CHARGE: Final = "single_complementary_charge"
ANCHOR_AROMATIC_PLANE: Final = "single_aromatic_plane"
ANCHOR_PRINCIPAL_AXIS_SHAPE: Final = "single_principal_axis_shape"

MISSING_TRUE_CONFORMER: Final = "missing_true_conformer"
MISSING_V7_CONTROL_SOURCE: Final = "missing_v7_control_source"
MISSING_LIGAND_DONOR: Final = "missing_ligand_donor"
MISSING_RECEPTOR_ACCEPTOR: Final = "missing_receptor_acceptor"
MISSING_LIGAND_ACCEPTOR: Final = "missing_ligand_acceptor"
MISSING_RECEPTOR_DONOR: Final = "missing_receptor_donor"
MISSING_COMPLEMENTARY_CHARGE_ANCHOR: Final = "missing_complementary_charge_anchor"
MISSING_LIGAND_AROMATIC_PLANE: Final = "missing_ligand_aromatic_plane"
MISSING_RECEPTOR_AROMATIC_PLANE: Final = "missing_receptor_aromatic_plane"
MISSING_LIGAND_SHAPE_AXIS: Final = "missing_ligand_shape_axis"
MISSING_POCKET_SHAPE_AXIS: Final = "missing_pocket_shape_axis"
MISSING_RETAINED_SOURCE: Final = "missing_retained_source"

READY_STATUS: Final = "ready"
MISSING_FEATURE_STATUS: Final = "typed_missing_feature_failure"
RETAINED_SOURCE_INDICES: Final = (36, 45, 54, 63)
RETAINED_SOURCE_NAMESPACE: Final = "current_v7_source_proposal_index"
V7_CONTROL_SOURCE_INDICES: Final = tuple(range(24))
V7_CONTROL_SOURCE_NAMESPACE: Final = "current_v7_source_proposal_index"
V7_CONTROL_PROPOSAL_MODE_POCKET_CENTERED: Final = "pocket_centered_control"
V7_CONTROL_PROPOSAL_MODE_UNIFORM_SOURCE: Final = "uniform_source_control"
INDEPENDENT_SO3_SEQUENCE_INDICES: Final = tuple(range(12))
TRUE_CONFORMER_RANKS: Final = (2, 3, 4, 5, 6, 7, 8)
TRUE_CONFORMER_SO3_SEQUENCE_INDICES: Final = tuple(range(8))
TRUE_CONFORMER_SLOT_RANKS: Final = (2, 3, 4, 5, 6, 7, 8, 2)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FEATURE_LIGAND_DONOR: Final = "ligand_donor"
FEATURE_LIGAND_ACCEPTOR: Final = "ligand_acceptor"
FEATURE_RECEPTOR_DONOR: Final = "receptor_donor"
FEATURE_RECEPTOR_ACCEPTOR: Final = "receptor_acceptor"
FEATURE_LIGAND_POSITIVE_SITE: Final = "ligand_positive_site"
FEATURE_LIGAND_NEGATIVE_SITE: Final = "ligand_negative_site"
FEATURE_RECEPTOR_POSITIVE_SITE: Final = "receptor_positive_site"
FEATURE_RECEPTOR_NEGATIVE_SITE: Final = "receptor_negative_site"
FEATURE_LIGAND_AROMATIC_PLANE: Final = "ligand_aromatic_plane"
FEATURE_RECEPTOR_AROMATIC_PLANE: Final = "receptor_aromatic_plane"
FEATURE_LIGAND_SHAPE_AXIS: Final = "ligand_shape_axis"
FEATURE_POCKET_SHAPE_AXIS: Final = "pocket_shape_axis"
_FEATURE_KINDS: Final = (
    FEATURE_LIGAND_DONOR,
    FEATURE_LIGAND_ACCEPTOR,
    FEATURE_RECEPTOR_DONOR,
    FEATURE_RECEPTOR_ACCEPTOR,
    FEATURE_LIGAND_POSITIVE_SITE,
    FEATURE_LIGAND_NEGATIVE_SITE,
    FEATURE_RECEPTOR_POSITIVE_SITE,
    FEATURE_RECEPTOR_NEGATIVE_SITE,
    FEATURE_LIGAND_AROMATIC_PLANE,
    FEATURE_RECEPTOR_AROMATIC_PLANE,
    FEATURE_LIGAND_SHAPE_AXIS,
    FEATURE_POCKET_SHAPE_AXIS,
)
_DONOR_FEATURE_KINDS: Final = {
    FEATURE_LIGAND_DONOR,
    FEATURE_RECEPTOR_DONOR,
}
_SINGLE_ATOM_FEATURE_KINDS: Final = {
    FEATURE_LIGAND_ACCEPTOR,
    FEATURE_RECEPTOR_ACCEPTOR,
}
_AROMATIC_FEATURE_KINDS: Final = {
    FEATURE_LIGAND_AROMATIC_PLANE,
    FEATURE_RECEPTOR_AROMATIC_PLANE,
}
_MAX_FEATURE_COUNT_PER_KIND: Final = 256
_MAX_FEATURE_ATOM_COUNT: Final = 4096
_MAX_TOTAL_FEATURE_ATOM_REFERENCES: Final = 65_536
_MAX_ATOM_INDEX: Final = (1 << 53) - 1
_MAX_CANONICAL_RECEIPT_BYTES: Final = 32 * 1024 * 1024

GENERATION_PARENT_EXACT_PASSTHROUGH: Final = "exact_passthrough_parent"
GENERATION_PARENT_GENERATOR_INPUT: Final = "generator_input_parent"

# Inclusive slot ranges.  Keeping this as one immutable source of truth makes
# the denominator and lane order mechanically inspectable.
FIXED_MIXED64_LANE_RANGES: Final = (
    (LANE_POCKET_CENTERED_CONTROLS, 0, 7),
    (LANE_UNIFORM_SOURCE_CONTROLS, 8, 23),
    (LANE_DETERMINISTIC_INDEPENDENT_SO3, 24, 35),
    (LANE_TRUE_CONFORMER_INDEPENDENT_SO3, 36, 43),
    (LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR, 44, 47),
    (LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR, 48, 51),
    (LANE_COMPLEMENTARY_CHARGE, 52, 55),
    (LANE_AROMATIC_PLANE, 56, 57),
    (LANE_PRINCIPAL_AXIS_SHAPE, 58, 59),
    (LANE_PAIRED_RETAINED_CONTROLS, 60, 63),
)


class FixedMixed64AllocationError(ValueError):
    """Raised when the fixed mixed64 allocation fails closed."""


def _expected_v7_control_proposal_mode(source_index: int) -> str:
    return (
        V7_CONTROL_PROPOSAL_MODE_POCKET_CENTERED
        if source_index < 8
        else V7_CONTROL_PROPOSAL_MODE_UNIFORM_SOURCE
    )


def _canonical_bytes(value: object) -> bytes:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) > _MAX_CANONICAL_RECEIPT_BYTES:
        raise FixedMixed64AllocationError(
            "canonical mixed64 receipt exceeds fixed byte capacity"
        )
    return encoded


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_exact_bool(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise FixedMixed64AllocationError(f"{name} must be an exact boolean")
    return value


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise FixedMixed64AllocationError(f"{name} must be an exact lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class Mixed64AtomicFeatureEvidence:
    """One source-bound pre-result feature selected by a fixed64 lane."""

    kind: str
    atom_indices: tuple[int, ...]
    source_receipt_sha256: str
    geometry_receipt_sha256: str
    schema_id: str = FIXED_MIXED64_ATOMIC_FEATURE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_ATOMIC_FEATURE_SCHEMA_ID:
            raise FixedMixed64AllocationError("atomic feature schema is invalid")
        if self.kind not in _FEATURE_KINDS:
            raise FixedMixed64AllocationError("atomic feature kind is not frozen")
        if type(self.atom_indices) is not tuple or any(
            type(value) is not int or not 0 <= value <= _MAX_ATOM_INDEX
            for value in self.atom_indices
        ):
            raise FixedMixed64AllocationError(
                "atomic feature indices must be exact bounded non-negative integers"
            )
        if (
            not self.atom_indices
            or len(self.atom_indices) > _MAX_FEATURE_ATOM_COUNT
            or len(set(self.atom_indices)) != len(self.atom_indices)
        ):
            raise FixedMixed64AllocationError(
                "atomic feature indices are empty, duplicated, or over capacity"
            )
        if self.kind in _DONOR_FEATURE_KINDS and len(self.atom_indices) != 2:
            raise FixedMixed64AllocationError(
                "donor feature must identify donor and attached hydrogen"
            )
        if self.kind in _SINGLE_ATOM_FEATURE_KINDS and len(self.atom_indices) != 1:
            raise FixedMixed64AllocationError(
                "acceptor feature must identify exactly one atom"
            )
        if self.kind in _AROMATIC_FEATURE_KINDS and len(self.atom_indices) < 3:
            raise FixedMixed64AllocationError(
                "aromatic plane feature requires at least three atoms"
            )
        object.__setattr__(
            self,
            "source_receipt_sha256",
            _require_digest(
                self.source_receipt_sha256,
                name="atomic feature source_receipt_sha256",
            ),
        )
        object.__setattr__(
            self,
            "geometry_receipt_sha256",
            _require_digest(
                self.geometry_receipt_sha256,
                name="atomic feature geometry_receipt_sha256",
            ),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "kind": self.kind,
            "atom_indices": list(self.atom_indices),
            "source_receipt_sha256": self.source_receipt_sha256,
            "geometry_receipt_sha256": self.geometry_receipt_sha256,
            "result_fields_consumed": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("atomic feature evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64V7ControlSourceEvidence:
    """One exact current-V7 source for a passthrough control slot."""

    source_index: int
    proposal_mode: str
    proposal_sha256: str
    coordinate_sha256: str
    proposal_lineage_sha256: str
    source_receipt_sha256: str
    source_namespace: str = V7_CONTROL_SOURCE_NAMESPACE
    schema_id: str = FIXED_MIXED64_V7_CONTROL_SOURCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_V7_CONTROL_SOURCE_SCHEMA_ID:
            raise FixedMixed64AllocationError("V7 control source schema is invalid")
        if self.source_namespace != V7_CONTROL_SOURCE_NAMESPACE:
            raise FixedMixed64AllocationError("V7 control source namespace changed")
        if (
            type(self.source_index) is not int
            or self.source_index not in V7_CONTROL_SOURCE_INDICES
        ):
            raise FixedMixed64AllocationError("V7 control source index is not frozen")
        if self.proposal_mode != _expected_v7_control_proposal_mode(
            self.source_index
        ):
            raise FixedMixed64AllocationError(
                "V7 control proposal mode disagrees with its frozen lane"
            )
        for name in (
            "proposal_sha256",
            "coordinate_sha256",
            "proposal_lineage_sha256",
            "source_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=f"V7 control {name}"),
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "source_namespace": self.source_namespace,
            "source_index": self.source_index,
            "proposal_mode": self.proposal_mode,
            "proposal_sha256": self.proposal_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "proposal_lineage_sha256": self.proposal_lineage_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "generation_parent_role": GENERATION_PARENT_EXACT_PASSTHROUGH,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("V7 control source evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64ConformerSourceEvidence:
    rank: int
    proposal_sha256: str
    coordinate_sha256: str
    source_receipt_sha256: str
    schema_id: str = FIXED_MIXED64_CONFORMER_SOURCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_CONFORMER_SOURCE_SCHEMA_ID:
            raise FixedMixed64AllocationError("conformer source schema is invalid")
        if type(self.rank) is not int or self.rank not in TRUE_CONFORMER_RANKS:
            raise FixedMixed64AllocationError("conformer source rank is not frozen")
        for name in (
            "proposal_sha256",
            "coordinate_sha256",
            "source_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=f"conformer {name}"),
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "rank": self.rank,
            "proposal_sha256": self.proposal_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "rank_selected_before_result": True,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("conformer source evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64RetainedSourceEvidence:
    source_index: int
    proposal_sha256: str
    coordinate_sha256: str
    source_receipt_sha256: str
    source_namespace: str = RETAINED_SOURCE_NAMESPACE
    schema_id: str = FIXED_MIXED64_RETAINED_SOURCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_RETAINED_SOURCE_SCHEMA_ID:
            raise FixedMixed64AllocationError("retained source schema is invalid")
        if self.source_namespace != RETAINED_SOURCE_NAMESPACE:
            raise FixedMixed64AllocationError("retained source namespace changed")
        if (
            type(self.source_index) is not int
            or self.source_index not in RETAINED_SOURCE_INDICES
        ):
            raise FixedMixed64AllocationError("retained source index is not frozen")
        for name in (
            "proposal_sha256",
            "coordinate_sha256",
            "source_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=f"retained {name}"),
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "source_namespace": self.source_namespace,
            "source_index": self.source_index,
            "proposal_sha256": self.proposal_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("retained source evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64FeatureEvidence:
    """Source-bound feature evidence; availability is always derived."""

    exact_v11_source_receipt_sha256: str
    prepared_ligand_topology_sha256: str
    prepared_receptor_topology_sha256: str
    feature_extractor_policy_sha256: str
    atomic_features: tuple[Mixed64AtomicFeatureEvidence, ...]
    v7_control_sources: tuple[Mixed64V7ControlSourceEvidence, ...]
    conformer_sources: tuple[Mixed64ConformerSourceEvidence, ...]
    retained_sources: tuple[Mixed64RetainedSourceEvidence, ...]
    schema_id: str = FIXED_MIXED64_FEATURE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_FEATURE_SCHEMA_ID:
            raise FixedMixed64AllocationError(
                "mixed64 feature schema identity is invalid"
            )
        for name in (
            "exact_v11_source_receipt_sha256",
            "prepared_ligand_topology_sha256",
            "prepared_receptor_topology_sha256",
            "feature_extractor_policy_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=name),
            )
        for name, values, expected_type in (
            ("atomic_features", self.atomic_features, Mixed64AtomicFeatureEvidence),
            (
                "v7_control_sources",
                self.v7_control_sources,
                Mixed64V7ControlSourceEvidence,
            ),
            (
                "conformer_sources",
                self.conformer_sources,
                Mixed64ConformerSourceEvidence,
            ),
            ("retained_sources", self.retained_sources, Mixed64RetainedSourceEvidence),
        ):
            maximum_counts = {
                "atomic_features": len(_FEATURE_KINDS)
                * _MAX_FEATURE_COUNT_PER_KIND,
                "v7_control_sources": len(V7_CONTROL_SOURCE_INDICES),
                "conformer_sources": len(TRUE_CONFORMER_RANKS),
                "retained_sources": len(RETAINED_SOURCE_INDICES),
            }
            if type(values) is not tuple:
                raise TypeError(f"{name} must contain exact typed evidence")
            if len(values) > maximum_counts[name]:
                raise FixedMixed64AllocationError(
                    f"{name} exceeds fixed evidence capacity"
                )
            if any(type(value) is not expected_type for value in values):
                raise TypeError(f"{name} must contain exact typed evidence")
            if len({value.receipt_sha256 for value in values}) != len(values):
                raise FixedMixed64AllocationError(f"{name} contains duplicate receipts")
        by_kind = {kind: self.features_for_kind(kind) for kind in _FEATURE_KINDS}
        if (
            sum(len(value.atom_indices) for value in self.atomic_features)
            > _MAX_TOTAL_FEATURE_ATOM_REFERENCES
        ):
            raise FixedMixed64AllocationError(
                "total atomic feature references exceed fixed capacity"
            )
        if any(
            len(values) > _MAX_FEATURE_COUNT_PER_KIND for values in by_kind.values()
        ):
            raise FixedMixed64AllocationError(
                "atomic feature count exceeds fixed capacity"
            )
        if tuple(self.atomic_features) != tuple(
            sorted(
                self.atomic_features,
                key=lambda value: (value.kind, value.receipt_sha256),
            )
        ):
            raise FixedMixed64AllocationError(
                "atomic features are not canonically ordered"
            )
        if tuple(source.rank for source in self.conformer_sources) != tuple(
            sorted({source.rank for source in self.conformer_sources})
        ):
            raise FixedMixed64AllocationError(
                "conformer ranks must be unique and sorted"
            )
        if tuple(source.source_index for source in self.v7_control_sources) != tuple(
            sorted({source.source_index for source in self.v7_control_sources})
        ):
            raise FixedMixed64AllocationError(
                "V7 control sources must be unique and sorted"
            )
        if tuple(source.source_index for source in self.retained_sources) != tuple(
            sorted({source.source_index for source in self.retained_sources})
        ):
            raise FixedMixed64AllocationError(
                "retained sources must be unique and sorted"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def features_for_kind(self, kind: str) -> tuple[Mixed64AtomicFeatureEvidence, ...]:
        if kind not in _FEATURE_KINDS:
            raise FixedMixed64AllocationError("requested feature kind is not frozen")
        return tuple(value for value in self.atomic_features if value.kind == kind)

    def conformer_for_rank(self, rank: int) -> Mixed64ConformerSourceEvidence | None:
        return next(
            (value for value in self.conformer_sources if value.rank == rank), None
        )

    def v7_control_for_index(
        self, source_index: int
    ) -> Mixed64V7ControlSourceEvidence | None:
        return next(
            (
                value
                for value in self.v7_control_sources
                if value.source_index == source_index
            ),
            None,
        )

    def retained_for_index(
        self, source_index: int
    ) -> Mixed64RetainedSourceEvidence | None:
        return next(
            (
                value
                for value in self.retained_sources
                if value.source_index == source_index
            ),
            None,
        )

    @property
    def true_conformer_available(self) -> bool:
        return all(
            self.conformer_for_rank(rank) is not None for rank in TRUE_CONFORMER_RANKS
        )

    def _available(self, kind: str) -> bool:
        return bool(self.features_for_kind(kind))

    ligand_donor_available = property(
        lambda self: self._available(FEATURE_LIGAND_DONOR)
    )
    ligand_acceptor_available = property(
        lambda self: self._available(FEATURE_LIGAND_ACCEPTOR)
    )
    receptor_donor_available = property(
        lambda self: self._available(FEATURE_RECEPTOR_DONOR)
    )
    receptor_acceptor_available = property(
        lambda self: self._available(FEATURE_RECEPTOR_ACCEPTOR)
    )
    ligand_positive_site_available = property(
        lambda self: self._available(FEATURE_LIGAND_POSITIVE_SITE)
    )
    ligand_negative_site_available = property(
        lambda self: self._available(FEATURE_LIGAND_NEGATIVE_SITE)
    )
    receptor_positive_site_available = property(
        lambda self: self._available(FEATURE_RECEPTOR_POSITIVE_SITE)
    )
    receptor_negative_site_available = property(
        lambda self: self._available(FEATURE_RECEPTOR_NEGATIVE_SITE)
    )
    ligand_aromatic_plane_available = property(
        lambda self: self._available(FEATURE_LIGAND_AROMATIC_PLANE)
    )
    receptor_aromatic_plane_available = property(
        lambda self: self._available(FEATURE_RECEPTOR_AROMATIC_PLANE)
    )
    ligand_shape_axis_available = property(
        lambda self: self._available(FEATURE_LIGAND_SHAPE_AXIS)
    )
    pocket_shape_axis_available = property(
        lambda self: self._available(FEATURE_POCKET_SHAPE_AXIS)
    )

    @property
    def retained_source_indices_available(self) -> tuple[int, ...]:
        return tuple(value.source_index for value in self.retained_sources)

    @property
    def v7_control_source_indices_available(self) -> tuple[int, ...]:
        return tuple(value.source_index for value in self.v7_control_sources)

    @property
    def complementary_charge_anchor_available(self) -> bool:
        return (
            self.ligand_positive_site_available
            and self.receptor_negative_site_available
        ) or (
            self.ligand_negative_site_available
            and self.receptor_positive_site_available
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "exact_v11_source_receipt_sha256": self.exact_v11_source_receipt_sha256,
            "prepared_ligand_topology_sha256": self.prepared_ligand_topology_sha256,
            "prepared_receptor_topology_sha256": self.prepared_receptor_topology_sha256,
            "feature_extractor_policy_sha256": self.feature_extractor_policy_sha256,
            "true_conformer_available": self.true_conformer_available,
            "ligand_donor_available": self.ligand_donor_available,
            "ligand_acceptor_available": self.ligand_acceptor_available,
            "receptor_donor_available": self.receptor_donor_available,
            "receptor_acceptor_available": self.receptor_acceptor_available,
            "ligand_positive_site_available": (self.ligand_positive_site_available),
            "ligand_negative_site_available": (self.ligand_negative_site_available),
            "receptor_positive_site_available": (self.receptor_positive_site_available),
            "receptor_negative_site_available": (self.receptor_negative_site_available),
            "complementary_charge_anchor_available": (
                self.complementary_charge_anchor_available
            ),
            "ligand_aromatic_plane_available": (self.ligand_aromatic_plane_available),
            "receptor_aromatic_plane_available": (
                self.receptor_aromatic_plane_available
            ),
            "ligand_shape_axis_available": self.ligand_shape_axis_available,
            "pocket_shape_axis_available": self.pocket_shape_axis_available,
            "retained_source_indices_available": list(
                self.retained_source_indices_available
            ),
            "v7_control_source_indices_available": list(
                self.v7_control_source_indices_available
            ),
            "atomic_feature_receipt_sha256s": [
                value.receipt_sha256 for value in self.atomic_features
            ],
            "atomic_features": [value.to_dict() for value in self.atomic_features],
            "v7_control_source_receipt_sha256s": [
                value.receipt_sha256 for value in self.v7_control_sources
            ],
            "v7_control_sources": [
                value.to_dict() for value in self.v7_control_sources
            ],
            "conformer_source_receipt_sha256s": [
                value.receipt_sha256 for value in self.conformer_sources
            ],
            "conformer_sources": [value.to_dict() for value in self.conformer_sources],
            "retained_source_receipt_sha256s": [
                value.receipt_sha256 for value in self.retained_sources
            ],
            "retained_sources": [value.to_dict() for value in self.retained_sources],
            "availability_caller_supplied": False,
            "result_fields_consumed": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("mixed64 feature availability changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class FixedMixed64Slot:
    slot_index: int
    lane: str
    lane_offset: int
    declared_anchor_kind: str | None
    required_features: tuple[str, ...]
    missing_feature_codes: tuple[str, ...]
    v7_control_source_index: int | None
    so3_sequence_index: int | None
    true_conformer_rank: int | None
    retained_source_index: int | None
    selected_source_receipt_sha256s: tuple[str, ...]
    selected_generation_parent_proposal_sha256: str | None
    selected_generation_parent_coordinate_sha256: str | None
    generation_parent_role: str | None
    generation_status: str
    generation_eligible: bool
    schema_id: str = FIXED_MIXED64_SLOT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_SLOT_SCHEMA_ID:
            raise FixedMixed64AllocationError("mixed64 slot schema is invalid")
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            raise FixedMixed64AllocationError("mixed64 slot index is invalid")
        if type(self.lane_offset) is not int or self.lane_offset < 0:
            raise FixedMixed64AllocationError("mixed64 lane offset is invalid")
        if (
            type(self.lane) is not str
            or not self.lane
            or self.lane != self.lane.strip()
        ):
            raise FixedMixed64AllocationError("mixed64 lane is invalid")
        if self.declared_anchor_kind is not None and (
            type(self.declared_anchor_kind) is not str
            or not self.declared_anchor_kind
            or self.declared_anchor_kind != self.declared_anchor_kind.strip()
        ):
            raise FixedMixed64AllocationError("mixed64 declared anchor kind is invalid")
        for name, values in (
            ("required_features", self.required_features),
            ("missing_feature_codes", self.missing_feature_codes),
        ):
            if type(values) is not tuple or any(
                type(value) is not str or not value or value != value.strip()
                for value in values
            ):
                raise FixedMixed64AllocationError(
                    f"mixed64 {name} must contain exact non-empty strings"
                )
            if len(set(values)) != len(values):
                raise FixedMixed64AllocationError(f"mixed64 {name} contains duplicates")
        if type(self.selected_source_receipt_sha256s) is not tuple:
            raise TypeError("selected source receipts must be an exact tuple")
        if len(self.selected_source_receipt_sha256s) > 2:
            raise FixedMixed64AllocationError(
                "selected source receipts exceed fixed slot capacity"
            )
        selected_receipts = tuple(
            _require_digest(
                value,
                name=f"selected_source_receipt_sha256s[{index}]",
            )
            for index, value in enumerate(self.selected_source_receipt_sha256s)
        )
        if len(set(selected_receipts)) != len(selected_receipts):
            raise FixedMixed64AllocationError(
                "selected source receipts contain duplicates"
            )
        parent_digests = (
            self.selected_generation_parent_proposal_sha256,
            self.selected_generation_parent_coordinate_sha256,
        )
        if (parent_digests[0] is None) is not (parent_digests[1] is None):
            raise FixedMixed64AllocationError(
                "generation parent proposal and coordinate identities must be paired"
            )
        if parent_digests[0] is not None:
            for name, value in (
                (
                    "selected_generation_parent_proposal_sha256",
                    parent_digests[0],
                ),
                (
                    "selected_generation_parent_coordinate_sha256",
                    parent_digests[1],
                ),
            ):
                _require_digest(value, name=name)
        if self.generation_parent_role not in {
            None,
            GENERATION_PARENT_EXACT_PASSTHROUGH,
            GENERATION_PARENT_GENERATOR_INPUT,
        }:
            raise FixedMixed64AllocationError("generation parent role is not frozen")
        if (self.generation_parent_role is None) is not (parent_digests[0] is None):
            raise FixedMixed64AllocationError(
                "generation parent role disagrees with parent identities"
            )
        if self.retained_source_index is not None and (
            type(self.retained_source_index) is not int
            or self.retained_source_index not in RETAINED_SOURCE_INDICES
        ):
            raise FixedMixed64AllocationError(
                "mixed64 retained source index is invalid"
            )
        if self.v7_control_source_index is not None and (
            type(self.v7_control_source_index) is not int
            or self.v7_control_source_index not in V7_CONTROL_SOURCE_INDICES
        ):
            raise FixedMixed64AllocationError(
                "mixed64 V7 control source index is invalid"
            )
        if self.so3_sequence_index is not None and (
            type(self.so3_sequence_index) is not int
            or self.so3_sequence_index not in INDEPENDENT_SO3_SEQUENCE_INDICES
        ):
            raise FixedMixed64AllocationError("mixed64 SO3 sequence index is invalid")
        if self.true_conformer_rank is not None and (
            type(self.true_conformer_rank) is not int
            or self.true_conformer_rank not in TRUE_CONFORMER_RANKS
        ):
            raise FixedMixed64AllocationError("mixed64 true-conformer rank is invalid")
        _require_exact_bool(
            self.generation_eligible,
            name="generation_eligible",
        )
        expected_status = (
            READY_STATUS if not self.missing_feature_codes else MISSING_FEATURE_STATUS
        )
        if self.generation_status != expected_status:
            raise FixedMixed64AllocationError(
                "mixed64 generation status disagrees with feature failures"
            )
        if self.generation_eligible is not (not self.missing_feature_codes):
            raise FixedMixed64AllocationError(
                "mixed64 generation eligibility disagrees with feature failures"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def declared_anchor_count(self) -> int:
        return 0 if self.declared_anchor_kind is None else 1

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "slot_index": self.slot_index,
            "lane": self.lane,
            "lane_offset": self.lane_offset,
            "declared_anchor_kind": self.declared_anchor_kind,
            "declared_anchor_count": self.declared_anchor_count,
            "required_features": list(self.required_features),
            "missing_feature_codes": list(self.missing_feature_codes),
            "v7_control_source_index": self.v7_control_source_index,
            "so3_sequence_index": self.so3_sequence_index,
            "true_conformer_rank": self.true_conformer_rank,
            "retained_source_index": self.retained_source_index,
            "selected_source_receipt_sha256s": list(
                self.selected_source_receipt_sha256s
            ),
            "selected_generation_parent_proposal_sha256": (
                self.selected_generation_parent_proposal_sha256
            ),
            "selected_generation_parent_coordinate_sha256": (
                self.selected_generation_parent_coordinate_sha256
            ),
            "generation_parent_role": self.generation_parent_role,
            "generation_status": self.generation_status,
            "generation_eligible": self.generation_eligible,
            "fallback_lane": None,
            "fallback_allowed": False,
            "multi_anchor_allowed": False,
            "slot_preserved_on_failure": True,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("mixed64 slot changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class FixedMixed64Allocation:
    features: Mixed64FeatureEvidence
    slots: tuple[FixedMixed64Slot, ...]
    profile_id: str = FIXED_MIXED64_PROFILE_ID
    schema_id: str = FIXED_MIXED64_ALLOCATION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != FIXED_MIXED64_ALLOCATION_SCHEMA_ID:
            raise FixedMixed64AllocationError("mixed64 allocation schema is invalid")
        if self.profile_id != FIXED_MIXED64_PROFILE_ID:
            raise FixedMixed64AllocationError("mixed64 profile identity is invalid")
        if type(self.features) is not Mixed64FeatureEvidence:
            raise TypeError("features must be the exact Mixed64FeatureEvidence type")
        if type(self.slots) is not tuple or any(
            type(slot) is not FixedMixed64Slot for slot in self.slots
        ):
            raise TypeError("slots must contain exact FixedMixed64Slot values")
        if len(self.slots) != FIXED_MIXED64_CANDIDATE_COUNT:
            raise FixedMixed64AllocationError("mixed64 denominator is not 64")
        if tuple(slot.slot_index for slot in self.slots) != tuple(range(64)):
            raise FixedMixed64AllocationError(
                "mixed64 slots are not index-stable and contiguous"
            )
        expected_lanes = tuple(
            lane
            for lane, start, end in FIXED_MIXED64_LANE_RANGES
            for _ in range(start, end + 1)
        )
        if tuple(slot.lane for slot in self.slots) != expected_lanes:
            raise FixedMixed64AllocationError("mixed64 lane allocation changed")
        expected_offsets = tuple(
            offset
            for _, start, end in FIXED_MIXED64_LANE_RANGES
            for offset in range(end - start + 1)
        )
        if tuple(slot.lane_offset for slot in self.slots) != expected_offsets:
            raise FixedMixed64AllocationError("mixed64 lane offsets changed")
        retained = tuple(slot.retained_source_index for slot in self.slots[60:64])
        if retained != RETAINED_SOURCE_INDICES:
            raise FixedMixed64AllocationError("mixed64 retained source mapping changed")
        if any(slot.retained_source_index is not None for slot in self.slots[:60]):
            raise FixedMixed64AllocationError(
                "non-retained mixed64 lanes acquired a retained source"
            )
        if any(slot.declared_anchor_count > 1 for slot in self.slots):
            raise FixedMixed64AllocationError("multi-anchor slots are forbidden")
        expected_slots = tuple(
            _build_slot_for_index(self.features, slot_index)
            for slot_index in range(FIXED_MIXED64_CANDIDATE_COUNT)
        )
        if any(
            observed.to_dict() != expected.to_dict()
            for observed, expected in zip(
                self.slots,
                expected_slots,
                strict=True,
            )
        ):
            raise FixedMixed64AllocationError(
                "mixed64 slots do not rederive from the frozen profile and features"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def ready_count(self) -> int:
        return sum(slot.generation_eligible for slot in self.slots)

    @property
    def typed_failure_count(self) -> int:
        return len(self.slots) - self.ready_count

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "profile_id": self.profile_id,
            "candidate_denominator": len(self.slots),
            "features_receipt_sha256": self.features.receipt_sha256,
            "features": self.features.to_dict(),
            "lane_ranges_inclusive": [
                {"lane": lane, "start": start, "end": end}
                for lane, start, end in FIXED_MIXED64_LANE_RANGES
            ],
            "retained_source_indices": list(RETAINED_SOURCE_INDICES),
            "ready_count": self.ready_count,
            "typed_failure_count": self.typed_failure_count,
            "slot_receipt_sha256s": [slot.receipt_sha256 for slot in self.slots],
            "slots": [slot.to_dict() for slot in self.slots],
            "allocation_result_dependent": False,
            "fallback_allowed": False,
            "multi_anchor_allowed": False,
            "failed_slots_preserved_in_denominator": True,
            "native_pose_input_consumed": False,
            "score_input_consumed": False,
            "benchmark_outcome_input_consumed": False,
            "fresh_holdout_input_consumed": False,
            "molecular_execution_authorized": False,
            "production_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise FixedMixed64AllocationError("mixed64 allocation changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _lane_for_slot(slot_index: int) -> tuple[str, int]:
    for lane, start, end in FIXED_MIXED64_LANE_RANGES:
        if start <= slot_index <= end:
            return lane, slot_index - start
    raise AssertionError("frozen mixed64 ranges do not cover the denominator")


def _slot_requirements(
    lane: str,
    retained_source_index: int | None,
) -> tuple[tuple[str, ...], str | None]:
    if lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        return ("true_conformer",), None
    if lane == LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
        return (
            ("ligand_donor", "receptor_acceptor"),
            ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
        )
    if lane == LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
        return (
            ("ligand_acceptor", "receptor_donor"),
            ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
        )
    if lane == LANE_COMPLEMENTARY_CHARGE:
        return ("complementary_charge_anchor",), ANCHOR_COMPLEMENTARY_CHARGE
    if lane == LANE_AROMATIC_PLANE:
        return (
            ("ligand_aromatic_plane", "receptor_aromatic_plane"),
            ANCHOR_AROMATIC_PLANE,
        )
    if lane == LANE_PRINCIPAL_AXIS_SHAPE:
        return (
            ("ligand_shape_axis", "pocket_shape_axis"),
            ANCHOR_PRINCIPAL_AXIS_SHAPE,
        )
    if lane == LANE_PAIRED_RETAINED_CONTROLS:
        if retained_source_index is None:
            raise AssertionError("retained lane lacks its frozen source")
        return (f"retained_source_{retained_source_index}",), None
    return (), None


def _missing_codes(
    features: Mixed64FeatureEvidence,
    required_features: tuple[str, ...],
    v7_control_source_index: int | None,
    retained_source_index: int | None,
) -> tuple[str, ...]:
    availability = {
        "true_conformer": features.true_conformer_available,
        "ligand_donor": features.ligand_donor_available,
        "receptor_acceptor": features.receptor_acceptor_available,
        "ligand_acceptor": features.ligand_acceptor_available,
        "receptor_donor": features.receptor_donor_available,
        "complementary_charge_anchor": (features.complementary_charge_anchor_available),
        "ligand_aromatic_plane": features.ligand_aromatic_plane_available,
        "receptor_aromatic_plane": features.receptor_aromatic_plane_available,
        "ligand_shape_axis": features.ligand_shape_axis_available,
        "pocket_shape_axis": features.pocket_shape_axis_available,
    }
    codes = {
        "true_conformer": MISSING_TRUE_CONFORMER,
        "ligand_donor": MISSING_LIGAND_DONOR,
        "receptor_acceptor": MISSING_RECEPTOR_ACCEPTOR,
        "ligand_acceptor": MISSING_LIGAND_ACCEPTOR,
        "receptor_donor": MISSING_RECEPTOR_DONOR,
        "complementary_charge_anchor": MISSING_COMPLEMENTARY_CHARGE_ANCHOR,
        "ligand_aromatic_plane": MISSING_LIGAND_AROMATIC_PLANE,
        "receptor_aromatic_plane": MISSING_RECEPTOR_AROMATIC_PLANE,
        "ligand_shape_axis": MISSING_LIGAND_SHAPE_AXIS,
        "pocket_shape_axis": MISSING_POCKET_SHAPE_AXIS,
    }
    failures: list[str] = []
    for requirement in required_features:
        if requirement.startswith("v7_control_source_"):
            if v7_control_source_index not in (
                features.v7_control_source_indices_available
            ):
                failures.append(
                    f"{MISSING_V7_CONTROL_SOURCE}:{v7_control_source_index}"
                )
            continue
        if requirement.startswith("true_conformer_rank_"):
            rank = int(requirement.removeprefix("true_conformer_rank_"))
            if features.conformer_for_rank(rank) is None:
                failures.append(f"{MISSING_TRUE_CONFORMER}:{rank}")
            continue
        if requirement.startswith("retained_source_"):
            if retained_source_index not in features.retained_source_indices_available:
                failures.append(f"{MISSING_RETAINED_SOURCE}:{retained_source_index}")
            continue
        if not availability[requirement]:
            failures.append(codes[requirement])
    return tuple(failures)


def _slot_source_identity(
    lane: str,
    lane_offset: int,
) -> tuple[int | None, int | None, int | None]:
    if lane in {
        LANE_POCKET_CENTERED_CONTROLS,
        LANE_UNIFORM_SOURCE_CONTROLS,
    }:
        return (
            V7_CONTROL_SOURCE_INDICES[
                lane_offset + (8 if lane == LANE_UNIFORM_SOURCE_CONTROLS else 0)
            ],
            None,
            None,
        )
    if lane == LANE_DETERMINISTIC_INDEPENDENT_SO3:
        return None, INDEPENDENT_SO3_SEQUENCE_INDICES[lane_offset], None
    if lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        return (
            None,
            TRUE_CONFORMER_SO3_SEQUENCE_INDICES[lane_offset],
            TRUE_CONFORMER_SLOT_RANKS[lane_offset],
        )
    return None, None, None


def _cycle_feature_receipt(
    features: Mixed64FeatureEvidence,
    kind: str,
    lane_offset: int,
) -> str | None:
    values = features.features_for_kind(kind)
    if not values:
        return None
    return values[lane_offset % len(values)].receipt_sha256


def _selected_source_receipts(
    features: Mixed64FeatureEvidence,
    lane: str,
    lane_offset: int,
    *,
    v7_control_source_index: int | None,
    true_conformer_rank: int | None,
    retained_source_index: int | None,
) -> tuple[str, ...]:
    if lane in {
        LANE_POCKET_CENTERED_CONTROLS,
        LANE_UNIFORM_SOURCE_CONTROLS,
    }:
        if v7_control_source_index is None:
            raise AssertionError("V7 control slot lacks a frozen source index")
        source = features.v7_control_for_index(v7_control_source_index)
        return () if source is None else (source.receipt_sha256,)
    if lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        if true_conformer_rank is None:
            raise AssertionError("true-conformer slot lacks a frozen rank")
        source = features.conformer_for_rank(true_conformer_rank)
        return () if source is None else (source.receipt_sha256,)
    feature_kinds: tuple[str, ...]
    if lane == LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
        feature_kinds = (FEATURE_LIGAND_DONOR, FEATURE_RECEPTOR_ACCEPTOR)
    elif lane == LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
        feature_kinds = (FEATURE_LIGAND_ACCEPTOR, FEATURE_RECEPTOR_DONOR)
    elif lane == LANE_COMPLEMENTARY_CHARGE:
        positive_pair = (
            FEATURE_LIGAND_POSITIVE_SITE,
            FEATURE_RECEPTOR_NEGATIVE_SITE,
        )
        negative_pair = (
            FEATURE_LIGAND_NEGATIVE_SITE,
            FEATURE_RECEPTOR_POSITIVE_SITE,
        )
        available_pairs = tuple(
            pair
            for pair in (positive_pair, negative_pair)
            if all(features.features_for_kind(kind) for kind in pair)
        )
        feature_kinds = (
            ()
            if not available_pairs
            else available_pairs[lane_offset % len(available_pairs)]
        )
    elif lane == LANE_AROMATIC_PLANE:
        feature_kinds = (
            FEATURE_LIGAND_AROMATIC_PLANE,
            FEATURE_RECEPTOR_AROMATIC_PLANE,
        )
    elif lane == LANE_PRINCIPAL_AXIS_SHAPE:
        feature_kinds = (FEATURE_LIGAND_SHAPE_AXIS, FEATURE_POCKET_SHAPE_AXIS)
    elif lane == LANE_PAIRED_RETAINED_CONTROLS:
        if retained_source_index is None:
            raise AssertionError("retained slot lacks a frozen source index")
        retained = features.retained_for_index(retained_source_index)
        return () if retained is None else (retained.receipt_sha256,)
    else:
        return ()
    selected = tuple(
        _cycle_feature_receipt(features, kind, lane_offset) for kind in feature_kinds
    )
    return tuple(value for value in selected if value is not None)


def _selected_generation_parent(
    features: Mixed64FeatureEvidence,
    lane: str,
    *,
    v7_control_source_index: int | None,
    true_conformer_rank: int | None,
    retained_source_index: int | None,
) -> tuple[str | None, str | None, str | None]:
    if lane in {
        LANE_POCKET_CENTERED_CONTROLS,
        LANE_UNIFORM_SOURCE_CONTROLS,
    }:
        if v7_control_source_index is None:
            raise AssertionError("V7 control slot lacks a frozen source index")
        source = features.v7_control_for_index(v7_control_source_index)
        return (
            (None, None, None)
            if source is None
            else (
                source.proposal_sha256,
                source.coordinate_sha256,
                GENERATION_PARENT_EXACT_PASSTHROUGH,
            )
        )
    if lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        if true_conformer_rank is None:
            raise AssertionError("true-conformer slot lacks a frozen rank")
        source = features.conformer_for_rank(true_conformer_rank)
        return (
            (None, None, None)
            if source is None
            else (
                source.proposal_sha256,
                source.coordinate_sha256,
                GENERATION_PARENT_GENERATOR_INPUT,
            )
        )
    if lane == LANE_PAIRED_RETAINED_CONTROLS:
        if retained_source_index is None:
            raise AssertionError("retained slot lacks a frozen source index")
        source = features.retained_for_index(retained_source_index)
        return (
            (None, None, None)
            if source is None
            else (
                source.proposal_sha256,
                source.coordinate_sha256,
                GENERATION_PARENT_EXACT_PASSTHROUGH,
            )
        )
    return None, None, None


def _build_slot_for_index(
    features: Mixed64FeatureEvidence,
    slot_index: int,
) -> FixedMixed64Slot:
    lane, lane_offset = _lane_for_slot(slot_index)
    retained_source_index = (
        RETAINED_SOURCE_INDICES[lane_offset]
        if lane == LANE_PAIRED_RETAINED_CONTROLS
        else None
    )
    (
        v7_control_source_index,
        so3_sequence_index,
        true_conformer_rank,
    ) = _slot_source_identity(lane, lane_offset)
    requirements, anchor_kind = _slot_requirements(
        lane,
        retained_source_index,
    )
    if lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        if true_conformer_rank is None:
            raise AssertionError("true-conformer slot lacks a frozen rank")
        requirements = (f"true_conformer_rank_{true_conformer_rank}",)
    elif v7_control_source_index is not None:
        requirements = (f"v7_control_source_{v7_control_source_index}",)
    missing = _missing_codes(
        features,
        requirements,
        v7_control_source_index,
        retained_source_index,
    )
    selected_source_receipt_sha256s = _selected_source_receipts(
        features,
        lane,
        lane_offset,
        v7_control_source_index=v7_control_source_index,
        true_conformer_rank=true_conformer_rank,
        retained_source_index=retained_source_index,
    )
    (
        selected_generation_parent_proposal_sha256,
        selected_generation_parent_coordinate_sha256,
        generation_parent_role,
    ) = _selected_generation_parent(
        features,
        lane,
        v7_control_source_index=v7_control_source_index,
        true_conformer_rank=true_conformer_rank,
        retained_source_index=retained_source_index,
    )
    return FixedMixed64Slot(
        slot_index=slot_index,
        lane=lane,
        lane_offset=lane_offset,
        declared_anchor_kind=anchor_kind,
        required_features=requirements,
        missing_feature_codes=missing,
        v7_control_source_index=v7_control_source_index,
        so3_sequence_index=so3_sequence_index,
        true_conformer_rank=true_conformer_rank,
        retained_source_index=retained_source_index,
        selected_source_receipt_sha256s=selected_source_receipt_sha256s,
        selected_generation_parent_proposal_sha256=(
            selected_generation_parent_proposal_sha256
        ),
        selected_generation_parent_coordinate_sha256=(
            selected_generation_parent_coordinate_sha256
        ),
        generation_parent_role=generation_parent_role,
        generation_status=(READY_STATUS if not missing else MISSING_FEATURE_STATUS),
        generation_eligible=not missing,
    )


def build_fixed_mixed64_allocation(
    features: Mixed64FeatureEvidence,
) -> FixedMixed64Allocation:
    """Build the exact 64-slot allocation without executing any candidate."""

    if type(features) is not Mixed64FeatureEvidence:
        raise TypeError("features must be the exact Mixed64FeatureEvidence type")
    slots = tuple(
        _build_slot_for_index(features, slot_index)
        for slot_index in range(FIXED_MIXED64_CANDIDATE_COUNT)
    )
    return FixedMixed64Allocation(features=features, slots=slots)


__all__ = [
    "FIXED_MIXED64_ALLOCATION_SCHEMA_ID",
    "FIXED_MIXED64_CANDIDATE_COUNT",
    "FIXED_MIXED64_FEATURE_SCHEMA_ID",
    "FIXED_MIXED64_ATOMIC_FEATURE_SCHEMA_ID",
    "FIXED_MIXED64_CONFORMER_SOURCE_SCHEMA_ID",
    "FIXED_MIXED64_V7_CONTROL_SOURCE_SCHEMA_ID",
    "FIXED_MIXED64_RETAINED_SOURCE_SCHEMA_ID",
    "FIXED_MIXED64_LANE_RANGES",
    "FIXED_MIXED64_PROFILE_ID",
    "FIXED_MIXED64_SLOT_SCHEMA_ID",
    "FixedMixed64Allocation",
    "FixedMixed64AllocationError",
    "FixedMixed64Slot",
    "GENERATION_PARENT_EXACT_PASSTHROUGH",
    "GENERATION_PARENT_GENERATOR_INPUT",
    "LANE_AROMATIC_PLANE",
    "LANE_COMPLEMENTARY_CHARGE",
    "LANE_DETERMINISTIC_INDEPENDENT_SO3",
    "LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR",
    "LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR",
    "LANE_PAIRED_RETAINED_CONTROLS",
    "LANE_POCKET_CENTERED_CONTROLS",
    "LANE_PRINCIPAL_AXIS_SHAPE",
    "LANE_TRUE_CONFORMER_INDEPENDENT_SO3",
    "LANE_UNIFORM_SOURCE_CONTROLS",
    "INDEPENDENT_SO3_SEQUENCE_INDICES",
    "MISSING_FEATURE_STATUS",
    "Mixed64AtomicFeatureEvidence",
    "Mixed64ConformerSourceEvidence",
    "Mixed64FeatureEvidence",
    "Mixed64RetainedSourceEvidence",
    "Mixed64V7ControlSourceEvidence",
    "READY_STATUS",
    "RETAINED_SOURCE_INDICES",
    "RETAINED_SOURCE_NAMESPACE",
    "TRUE_CONFORMER_RANKS",
    "TRUE_CONFORMER_SLOT_RANKS",
    "TRUE_CONFORMER_SO3_SEQUENCE_INDICES",
    "V7_CONTROL_SOURCE_INDICES",
    "V7_CONTROL_SOURCE_NAMESPACE",
    "V7_CONTROL_PROPOSAL_MODE_POCKET_CENTERED",
    "V7_CONTROL_PROPOSAL_MODE_UNIFORM_SOURCE",
    "build_fixed_mixed64_allocation",
]
