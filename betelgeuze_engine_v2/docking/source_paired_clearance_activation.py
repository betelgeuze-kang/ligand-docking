"""Snapshot-driven clearance activation for one sealed development comparison.

The callable in this module has no CLI, product, or benchmark runner wiring.  It
reconstructs the already-frozen PR #243 predicate exclusively from a typed V1.1
snapshot and returns an immutable experimental state.  Scoring, rank, RMSD,
PoseBusters, native coordinates, and case identity are deliberately absent from
the API so the decision is sealed before any outcome evidence exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping

import torch

from .authority import AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID
from .contact_validity import (
    ELEMENT_AWARE_VALIDITY_CONTEXT_SCHEMA_ID,
    VdwContactPolicy,
)
from .guided_placement import (
    SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
    SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID,
    SourcePairedTorsionRescueAllocation,
    _torsion_metadata_sha256,
)
from .identity import coordinate_fingerprint
from .proposals import DockingProposal
from .source_paired_clearance_selection import (
    SourcePairedTorsionRescueClearanceSelectionPolicyV1,
    SourcePairedTorsionRescueClearanceSelectionProbeInputsV1,
    evaluate_source_paired_torsion_rescue_clearance_selection_v1,
)
from .torsion_contact_refinement import (
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_ID,
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_VERSION,
    MAX_RECEPTOR_CLEARANCE_PAIR_COUNT,
    SOURCE_PAIRED_TORSION_RESCUE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
    SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256,
    InteractionAwareTorsionContactConfigV7,
    SourcePairedTorsionRescueActivationSnapshotV1,
    TorsionContactRefinementError,
    _receptor_clearance_statistics,
)
from .validity import POSE_VALIDITY_RECEPTOR_COORDINATES_SCHEMA_ID


SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_activated_state/1.0.0"
)
SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_selection_activation"
)
SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_VERSION = "1.0.0"
SOURCE_PAIRED_CLEARANCE_SELECTION_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)

_SNAPSHOT_KEYS = frozenset(
    {
        "schema_id",
        "source_v11_receipt_payload",
        "source_v11_receipt_sha256",
        "allocation_receipt_payload",
        "allocation_receipt_sha256",
        "authenticated_input_receipt_payload",
        "source_proposal_receipt_payload",
        "source_proposal_receipt_sha256",
        "source_proposal_slot",
        "source_parent_slot",
        "authenticated_input_receipt_sha256",
        "validity_context_payload",
        "receptor_coordinates",
        "candidate_id",
        "proposal_index",
        "candidate_proposal_fingerprint_sha256",
        "source_proposal_fingerprint_sha256",
        "generic_v7_config_sha256",
        "vdw_contact_policy_sha256",
        "source_coordinate_sha256",
        "candidate_coordinate_sha256",
        "source_torsion_metadata_sha256",
        "candidate_torsion_metadata_sha256",
        "v6_baseline_torsion_metadata_sha256",
        "optimized_torsion_metadata_sha256",
        "source_paired_parent_proposal_index",
        "v6_baseline_state",
        "optimized_state",
        "objectives",
        "clearance",
        "torsion_state",
        "v6_baseline_coordinates",
        "optimized_coordinates",
        "v6_baseline_torsion_angles",
        "optimized_torsion_angles",
        "baseline_clearance_statistics",
        "optimized_clearance_statistics",
        "baseline_receptor_objective_binary64_hex",
        "baseline_internal_objective_binary64_hex",
        "baseline_combined_objective_binary64_hex",
        "optimized_receptor_objective_binary64_hex",
        "optimized_internal_objective_binary64_hex",
        "optimized_combined_objective_binary64_hex",
        "ligand_atom_count",
        "receptor_atom_count",
        "exact_pair_count",
        "evaluated_internal_pair_count",
        "clearance_radii_policy_sha256",
        "torsion_evaluated",
        "torsion_variant_available",
        "torsion_selected",
        "evaluated_torsion_steps",
        "evaluated_torsion_moves",
        "result_dependent_allocation",
        "selection_applied",
        "default_v7_output_changed",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
        "claim_safe",
        "snapshot_sha256",
    }
)
_CLEARANCE_STATISTIC_KEYS = frozenset(
    {
        "minimum_distance_angstrom_binary64_hex",
        "minimum_distance_ligand_atom_index",
        "minimum_distance_receptor_atom_index",
        "minimum_vdw_surface_gap_angstrom_binary64_hex",
        "minimum_vdw_surface_gap_ligand_atom_index",
        "minimum_vdw_surface_gap_receptor_atom_index",
        "minimum_vdw_ratio_binary64_hex",
        "minimum_vdw_ratio_ligand_atom_index",
        "minimum_vdw_ratio_receptor_atom_index",
    }
)


class SourcePairedClearanceActivationError(TorsionContactRefinementError):
    """The typed activation evidence is incomplete or cross-wired."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SourcePairedClearanceActivationError(
            "clearance activation state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SourcePairedClearanceActivationError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise SourcePairedClearanceActivationError(f"{name} must be an object")
    try:
        copied = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    except json.JSONDecodeError as exc:  # pragma: no cover - encoder is authoritative
        raise SourcePairedClearanceActivationError(
            f"{name} cannot be copied canonically"
        ) from exc
    if not isinstance(copied, dict):
        raise SourcePairedClearanceActivationError(f"{name} must be an object")
    return copied


def _freeze_json(value: object) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in sorted(value.items())}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise SourcePairedClearanceActivationError(
        "activated-state projection contains an unsupported value"
    )


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _binary64(value: object, *, name: str, minimum: float | None = None) -> float:
    if type(value) is not str:
        raise SourcePairedClearanceActivationError(
            f"{name} must be canonical binary64 hex"
        )
    try:
        observed = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise SourcePairedClearanceActivationError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if (
        not math.isfinite(observed)
        or observed.hex() != value
        or (minimum is not None and observed < minimum)
    ):
        raise SourcePairedClearanceActivationError(
            f"{name} must be canonical finite binary64 hex"
        )
    return observed


def _nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise SourcePairedClearanceActivationError(
            f"{name} must be a nonnegative integer"
        )
    return value


def _tensor_from_payload(
    value: object,
    *,
    name: str,
    shape: tuple[int, ...],
    coordinate: bool,
) -> tuple[torch.Tensor, str | None]:
    payload = _mapping(value, name=name)
    expected_keys = {
        "dtype",
        "shape",
        "values_binary64_hex",
        *(("coordinate_sha256",) if coordinate else ()),
    }
    if set(payload) != expected_keys or payload.get("dtype") != "float64":
        raise SourcePairedClearanceActivationError(
            f"{name} tensor payload is not canonical"
        )
    observed_shape = payload.get("shape")
    if (
        type(observed_shape) is not list
        or any(type(size) is not int or size < 0 for size in observed_shape)
        or tuple(observed_shape) != shape
    ):
        raise SourcePairedClearanceActivationError(f"{name} shape is invalid")
    encoded_values = payload.get("values_binary64_hex")
    expected_count = math.prod(shape)
    if type(encoded_values) is not list or len(encoded_values) != expected_count:
        raise SourcePairedClearanceActivationError(f"{name} value count is invalid")
    values = [
        _binary64(item, name=f"{name} value {index}")
        for index, item in enumerate(encoded_values)
    ]
    tensor = torch.tensor(values, dtype=torch.float64).reshape(shape)
    coordinate_sha256: str | None = None
    if coordinate:
        coordinate_sha256 = _digest(
            payload.get("coordinate_sha256"),
            name=f"{name} coordinate SHA-256",
        )
        if coordinate_fingerprint(tensor) != coordinate_sha256:
            raise SourcePairedClearanceActivationError(
                f"{name} coordinate payload does not match its SHA-256"
            )
    return tensor, coordinate_sha256


def _validity_receptor_coordinate_sha256(value: torch.Tensor) -> str:
    canonical = value.detach().to(dtype=torch.float64, device="cpu").contiguous()
    return _sha256(
        {
            "schema_id": POSE_VALIDITY_RECEPTOR_COORDINATES_SCHEMA_ID,
            "shape": [int(size) for size in canonical.shape],
            "values_hex": [
                float(item).hex() for item in canonical.reshape(-1).tolist()
            ],
        }
    )


def _validity_receptor_tensor_from_payload(
    value: object,
    *,
    receptor_atom_count: int,
    expected_sha256: str,
) -> torch.Tensor:
    payload = _mapping(value, name="activation receptor coordinates")
    embedded_sha256 = _digest(
        payload.pop("validity_coordinate_sha256", None),
        name="activation receptor coordinate SHA-256",
    )
    tensor, _ = _tensor_from_payload(
        payload,
        name="activation receptor coordinates",
        shape=(receptor_atom_count, 3),
        coordinate=False,
    )
    if (
        embedded_sha256 != expected_sha256
        or _validity_receptor_coordinate_sha256(tensor) != expected_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "activation receptor coordinates are not bound to the validity context"
        )
    return tensor


def _string_tuple(value: object, *, name: str) -> tuple[str, ...]:
    if type(value) is not list or any(
        type(item) is not str or not item for item in value
    ):
        raise SourcePairedClearanceActivationError(
            f"{name} must be a non-empty-string array"
        )
    return tuple(value)


def _authenticated_input_payload(
    value: object,
    *,
    expected_sha256: str,
) -> dict[str, object]:
    payload = _mapping(value, name="authenticated input receipt")
    embedded_sha256 = _digest(
        payload.get("input_receipt_sha256"),
        name="embedded authenticated input receipt SHA-256",
    )
    pocket = _mapping(payload.get("pocket"), name="authenticated pocket receipt")
    search_space_derivation = _mapping(
        payload.get("search_space_derivation"),
        name="authenticated search-space derivation receipt",
    )
    projection = dict(payload)
    projection.pop("input_receipt_sha256")
    projection.pop("pocket")
    projection.pop("search_space_derivation")
    if (
        payload.get("schema_id") != AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID
        or embedded_sha256 != expected_sha256
        or _sha256(projection) != expected_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "authenticated input receipt schema or self-hash is invalid"
        )

    pocket_projection = dict(pocket)
    pocket_fingerprint = _digest(
        pocket_projection.pop("fingerprint_sha256", None),
        name="pocket fingerprint SHA-256",
    )
    center = pocket_projection.pop("center_angstrom", None)
    radius = pocket_projection.pop("radius_angstrom", None)
    scientifically_validated = pocket_projection.pop(
        "scientifically_validated",
        None,
    )
    claim_safe = pocket_projection.pop("claim_safe", None)
    center_hex = pocket.get("center_binary64_hex")
    radius_hex = pocket.get("radius_angstrom_binary64_hex")
    if (
        pocket_fingerprint != payload.get("pocket_definition_sha256")
        or _sha256(pocket_projection) != pocket_fingerprint
        or type(center_hex) is not list
        or len(center_hex) != 3
        or type(center) is not list
        or len(center) != 3
        or any(type(item) is not float for item in center)
        or [
            _binary64(item, name=f"pocket center component {index}")
            for index, item in enumerate(center_hex)
        ]
        != center
        or type(radius) is not float
        or _binary64(radius_hex, name="pocket radius", minimum=0.0) != radius
        or scientifically_validated is not False
        or claim_safe is not False
    ):
        raise SourcePairedClearanceActivationError(
            "authenticated pocket receipt is incomplete or cross-wired"
        )

    search_projection = dict(search_space_derivation)
    search_receipt_sha256 = _digest(
        search_projection.pop("receipt_sha256", None),
        name="search-space derivation receipt SHA-256",
    )
    if (
        search_receipt_sha256 != payload.get("search_space_derivation_receipt_sha256")
        or _sha256(search_projection) != search_receipt_sha256
        or search_space_derivation.get("search_space_fingerprint_sha256")
        != payload.get("search_space_fingerprint_sha256")
    ):
        raise SourcePairedClearanceActivationError(
            "authenticated search-space derivation receipt is cross-wired"
        )
    return payload


def _allocation_from_payload(
    value: object,
    *,
    expected_sha256: str,
) -> SourcePairedTorsionRescueAllocation:
    payload = _mapping(value, name="allocation receipt")
    if payload.get("schema_id") != SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID:
        raise SourcePairedClearanceActivationError(
            "allocation receipt schema is invalid"
        )
    observed_sha256 = _digest(
        payload.get("allocation_sha256"),
        name="allocation receipt SHA-256",
    )
    projection = dict(payload)
    projection.pop("allocation_sha256")
    if observed_sha256 != expected_sha256 or _sha256(projection) != observed_sha256:
        raise SourcePairedClearanceActivationError(
            "allocation receipt self-hash is invalid"
        )

    def pairs(name: str) -> tuple[tuple[int, int], ...]:
        values = payload.get(name)
        if type(values) is not list:
            raise SourcePairedClearanceActivationError(
                f"allocation {name} must be an array"
            )
        rows: list[tuple[int, int]] = []
        for row in values:
            item = _mapping(row, name=f"allocation {name} row")
            if set(item) != {
                "target_proposal_index",
                "parent_proposal_index",
            }:
                raise SourcePairedClearanceActivationError(
                    f"allocation {name} row is invalid"
                )
            target = item["target_proposal_index"]
            parent = item["parent_proposal_index"]
            if type(target) is not int or type(parent) is not int:
                raise SourcePairedClearanceActivationError(
                    f"allocation {name} indices must be integers"
                )
            rows.append((target, parent))
        return tuple(rows)

    try:
        allocation = SourcePairedTorsionRescueAllocation(
            authenticated_input_receipt_sha256=payload.get(
                "authenticated_input_receipt_sha256"
            ),
            guidance_context_sha256=payload.get("guidance_context_sha256"),
            budget_sha256=payload.get("budget_sha256"),
            rescue_policy_sha256=payload.get("rescue_policy_sha256"),
            base_guided_policy_sha256=payload.get("base_guided_policy_sha256"),
            candidate_count=payload.get("candidate_count"),
            authority_rotor_count=payload.get("authority_rotor_count"),
            v3_target_parent_pairs=pairs("v3_target_parent_pairs"),
            rescue_target_parent_pairs=pairs("rescue_target_parent_pairs"),
        )
    except (TypeError, ValueError) as exc:
        raise SourcePairedClearanceActivationError(
            "allocation receipt cannot be reconstructed"
        ) from exc
    if allocation.to_dict() != payload:
        raise SourcePairedClearanceActivationError(
            "allocation receipt contains non-authoritative fields or values"
        )
    return allocation


def _clearance_statistics(value: object, *, name: str) -> dict[str, object]:
    payload = _mapping(value, name=name)
    if set(payload) != _CLEARANCE_STATISTIC_KEYS:
        raise SourcePairedClearanceActivationError(
            f"{name} clearance statistics are incomplete"
        )
    _binary64(
        payload["minimum_distance_angstrom_binary64_hex"],
        name=f"{name} raw minimum distance",
        minimum=0.0,
    )
    _binary64(
        payload["minimum_vdw_surface_gap_angstrom_binary64_hex"],
        name=f"{name} minimum VDW gap",
    )
    _binary64(
        payload["minimum_vdw_ratio_binary64_hex"],
        name=f"{name} minimum VDW ratio",
        minimum=0.0,
    )
    for key in _CLEARANCE_STATISTIC_KEYS - {
        "minimum_distance_angstrom_binary64_hex",
        "minimum_vdw_surface_gap_angstrom_binary64_hex",
        "minimum_vdw_ratio_binary64_hex",
    }:
        _nonnegative_int(payload[key], name=f"{name} {key}")
    return payload


def _source_proposal_receipt(
    value: object,
    *,
    expected_sha256: str,
    allocation_payload: Mapping[str, object],
    authenticated_input_receipt_sha256: str,
    proposal_index: int,
    parent_index: int,
    expected_candidate_id: str,
    expected_source_proposal_sha256: str,
    expected_source_coordinate_sha256: str,
    expected_source_torsion_sha256: str,
    target_slot_value: object,
    parent_slot_value: object,
) -> dict[str, object]:
    payload = _mapping(value, name="source proposal receipt")
    projection = dict(payload)
    embedded_sha256 = _digest(
        projection.pop("receipt_sha256", None),
        name="embedded source proposal receipt SHA-256",
    )
    slots = payload.get("candidate_slots")
    if (
        payload.get("schema_id")
        != SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID
        or embedded_sha256 != expected_sha256
        or _sha256(projection) != expected_sha256
        or payload.get("authenticated_input_receipt_sha256")
        != authenticated_input_receipt_sha256
        or payload.get("allocation") != dict(allocation_payload)
        or payload.get("candidate_count") != 64
        or not isinstance(slots, list)
        or len(slots) != 64
        or any(
            not isinstance(slot, dict) or slot.get("proposal_index") != index
            for index, slot in enumerate(slots)
        )
    ):
        raise SourcePairedClearanceActivationError(
            "source proposal receipt identity is incomplete or cross-wired"
        )
    target_slot = _mapping(slots[proposal_index], name="source proposal target slot")
    parent_slot = _mapping(slots[parent_index], name="source proposal parent slot")
    if (
        target_slot != _mapping(target_slot_value, name="snapshot target slot")
        or parent_slot != _mapping(parent_slot_value, name="snapshot parent slot")
        or target_slot.get("candidate_id") != expected_candidate_id
        or target_slot.get("proposal_fingerprint_sha256")
        != expected_source_proposal_sha256
        or target_slot.get("coordinate_fingerprint_sha256")
        != expected_source_coordinate_sha256
        or target_slot.get("torsion_metadata_sha256") != expected_source_torsion_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "source proposal target or parent slot is cross-wired"
        )
    for name, expected in (
        ("proposal_objects_and_coordinates_unchanged", True),
        ("selected_parent_proposal_objects_retained", True),
        ("result_dependent_allocation", False),
        ("development_only", True),
        ("stage0_eligible", False),
        ("fresh_execution_authorized", False),
        ("scientifically_validated", False),
        ("claim_safe", False),
    ):
        if payload.get(name) is not expected:
            raise SourcePairedClearanceActivationError(
                "source proposal receipt exceeds its development authority"
            )
    return payload


def _proposal_state_payload(proposal: DockingProposal) -> dict[str, object]:
    proposal.assert_integrity()

    def tensor_payload(
        tensor: torch.Tensor, *, include_coordinate_sha: bool
    ) -> dict[str, object]:
        canonical = tensor.detach().to(dtype=torch.float64, device="cpu").contiguous()
        payload: dict[str, object] = {
            "dtype": "float64",
            "shape": [int(size) for size in canonical.shape],
            "values_binary64_hex": [
                float(item).hex() for item in canonical.reshape(-1).tolist()
            ],
        }
        if include_coordinate_sha:
            payload["coordinate_sha256"] = proposal.coordinate_fingerprint_sha256
        return payload

    return {
        "proposal_fingerprint_sha256": proposal.fingerprint_sha256,
        "coordinates": tensor_payload(
            proposal.coordinates,
            include_coordinate_sha=True,
        ),
        "torsion_angles": tensor_payload(
            proposal.torsion_angles,
            include_coordinate_sha=False,
        ),
    }


@dataclass(frozen=True, slots=True, init=False)
class SourcePairedClearanceActivatedStateV1:
    """Builder-only experimental candidate state sealed before scoring."""

    _baseline_proposal: DockingProposal
    _selected_proposal: DockingProposal
    _projection: Mapping[str, object]
    _state_sha256: str

    def __init__(self) -> None:
        raise TypeError("SourcePairedClearanceActivatedStateV1 is builder-produced")

    @property
    def baseline_proposal(self) -> DockingProposal:
        return replace(self._baseline_proposal)

    @property
    def selected_or_retained_proposal(self) -> DockingProposal:
        return replace(self._selected_proposal)

    @property
    def selection_applied(self) -> bool:
        return bool(self._projection["selection_applied"])

    @property
    def shadow_selection_eligible(self) -> bool:
        return bool(self._projection["shadow_selection_eligible"])

    @property
    def selected_action(self) -> str:
        return str(self._projection["selected_action"])

    @property
    def state_sha256(self) -> str:
        projection = _thaw_json(self._projection)
        observed = _sha256(projection)
        if observed != self._state_sha256:
            raise SourcePairedClearanceActivationError(
                "activated state changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        projection = _thaw_json(self._projection)
        if not isinstance(projection, dict):
            raise SourcePairedClearanceActivationError(
                "activated-state projection is invalid"
            )
        return {**projection, "state_sha256": self.state_sha256}


_ACTIVATED_STATE_BUILDER_TOKEN = object()


def _build_activated_state(
    *,
    baseline_proposal: DockingProposal,
    selected_proposal: DockingProposal,
    projection: Mapping[str, object],
    _builder_token: object,
) -> SourcePairedClearanceActivatedStateV1:
    if _builder_token is not _ACTIVATED_STATE_BUILDER_TOKEN:
        raise SourcePairedClearanceActivationError(
            "activated states require the snapshot-driven public builder"
        )
    copied = _mapping(projection, name="activated-state projection")
    if (
        copied.get("schema_id") != SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID
        or "state_sha256" in copied
    ):
        raise SourcePairedClearanceActivationError(
            "activated-state projection is invalid"
        )
    if (
        type(baseline_proposal) is not DockingProposal
        or type(selected_proposal) is not DockingProposal
    ):
        raise TypeError("activated-state proposals must be DockingProposal")
    baseline_proposal.assert_integrity()
    selected_proposal.assert_integrity()
    if (
        copied.get("candidate_id") != baseline_proposal.candidate_id
        or copied.get("candidate_id") != selected_proposal.candidate_id
        or copied.get("proposal_index") != baseline_proposal.proposal_index
        or copied.get("proposal_index") != selected_proposal.proposal_index
        or copied.get("baseline_candidate_proposal_fingerprint_sha256")
        != baseline_proposal.fingerprint_sha256
        or copied.get("baseline_candidate_coordinate_sha256")
        != baseline_proposal.coordinate_fingerprint_sha256
        or copied.get("selected_or_retained_candidate_proposal_fingerprint_sha256")
        != selected_proposal.fingerprint_sha256
        or copied.get("selected_or_retained_coordinate_sha256")
        != selected_proposal.coordinate_fingerprint_sha256
        or copied.get("baseline_candidate_state")
        != _proposal_state_payload(baseline_proposal)
        or copied.get("selected_or_retained_state")
        != _proposal_state_payload(selected_proposal)
    ):
        raise SourcePairedClearanceActivationError(
            "activated-state proposal objects do not match their projection"
        )
    instance = object.__new__(SourcePairedClearanceActivatedStateV1)
    object.__setattr__(instance, "_baseline_proposal", replace(baseline_proposal))
    object.__setattr__(instance, "_selected_proposal", replace(selected_proposal))
    object.__setattr__(instance, "_projection", _freeze_json(copied))
    object.__setattr__(instance, "_state_sha256", _sha256(copied))
    return instance


def build_source_paired_clearance_activated_state_v1(
    snapshot: SourcePairedTorsionRescueActivationSnapshotV1,
    current_v7_proposal: DockingProposal,
    *,
    policy: SourcePairedTorsionRescueClearanceSelectionPolicyV1 | None = None,
) -> SourcePairedClearanceActivatedStateV1:
    """Build one snapshot-bound experimental state without scoring or execution."""

    if type(snapshot) is not SourcePairedTorsionRescueActivationSnapshotV1:
        raise TypeError(
            "snapshot must be SourcePairedTorsionRescueActivationSnapshotV1"
        )
    if type(current_v7_proposal) is not DockingProposal:
        raise TypeError("current_v7_proposal must be DockingProposal")
    current_v7_proposal.assert_integrity()

    document = snapshot.to_dict()
    if set(document) != _SNAPSHOT_KEYS:
        raise SourcePairedClearanceActivationError(
            "activation snapshot fields are incomplete or unsupported"
        )
    snapshot_sha256 = _digest(
        document.get("snapshot_sha256"),
        name="activation snapshot SHA-256",
    )
    snapshot_projection = dict(document)
    snapshot_projection.pop("snapshot_sha256")
    if (
        document.get("schema_id")
        != SOURCE_PAIRED_TORSION_RESCUE_ACTIVATION_SNAPSHOT_SCHEMA_ID
        or snapshot.snapshot_sha256 != snapshot_sha256
        or _sha256(snapshot_projection) != snapshot_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "activation snapshot schema or self-hash is invalid"
        )

    authority_flags = {
        "result_dependent_allocation": False,
        "selection_applied": False,
        "default_v7_output_changed": False,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "claim_safe": False,
    }
    if any(document.get(name) is not value for name, value in authority_flags.items()):
        raise SourcePairedClearanceActivationError(
            "activation snapshot authority boundary is invalid"
        )

    allocation_sha256 = _digest(
        document.get("allocation_receipt_sha256"),
        name="allocation receipt SHA-256",
    )
    allocation = _allocation_from_payload(
        document.get("allocation_receipt_payload"),
        expected_sha256=allocation_sha256,
    )
    authenticated_input_receipt_sha256 = _digest(
        document.get("authenticated_input_receipt_sha256"),
        name="authenticated input receipt SHA-256",
    )
    if (
        allocation.authenticated_input_receipt_sha256
        != authenticated_input_receipt_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot and allocation input receipts are cross-wired"
        )
    authenticated_input = _authenticated_input_payload(
        document.get("authenticated_input_receipt_payload"),
        expected_sha256=authenticated_input_receipt_sha256,
    )
    validity_context = _mapping(
        document.get("validity_context_payload"),
        name="element-aware validity context",
    )
    validity_context_sha256 = _sha256(validity_context)
    contact_policy_payload = _mapping(
        validity_context.get("contact_policy"),
        name="VDW contact policy",
    )
    contact_policy_projection = dict(contact_policy_payload)
    contact_policy_sha256 = _digest(
        contact_policy_projection.pop("fingerprint_sha256", None),
        name="embedded VDW contact policy SHA-256",
    )
    contact_policy = VdwContactPolicy()
    ligand_elements = _string_tuple(
        validity_context.get("ligand_elements"),
        name="validity-context ligand elements",
    )
    receptor_elements = _string_tuple(
        validity_context.get("receptor_elements"),
        name="validity-context receptor elements",
    )
    receptor_atom_indices_value = authenticated_input.get("receptor_atom_indices")
    if type(receptor_atom_indices_value) is not list or any(
        type(index) is not int or index < 0 for index in receptor_atom_indices_value
    ):
        raise SourcePairedClearanceActivationError(
            "authenticated receptor atom indices are invalid"
        )
    receptor_atom_indices = tuple(receptor_atom_indices_value)
    if (
        receptor_atom_indices != tuple(sorted(set(receptor_atom_indices)))
        or validity_context.get("schema_id") != ELEMENT_AWARE_VALIDITY_CONTEXT_SCHEMA_ID
        or authenticated_input.get("problem_fingerprint_sha256")
        != current_v7_proposal.problem_fingerprint_sha256
        or validity_context.get("problem_fingerprint_sha256")
        != current_v7_proposal.problem_fingerprint_sha256
        or authenticated_input.get("validity_context_fingerprint_sha256")
        != validity_context_sha256
        or validity_context.get("contact_policy_sha256") != contact_policy_sha256
        or contact_policy_sha256
        != SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256
        or _sha256(contact_policy_projection) != contact_policy_sha256
        or contact_policy_payload != contact_policy.to_dict()
    ):
        raise SourcePairedClearanceActivationError(
            "authenticated validity geometry is incomplete or cross-wired"
        )

    source_receipt = _mapping(
        document.get("source_v11_receipt_payload"),
        name="source V1.1 receipt",
    )
    source_receipt_sha256 = _digest(
        document.get("source_v11_receipt_sha256"),
        name="source V1.1 receipt SHA-256",
    )
    receipt_projection = dict(source_receipt)
    receipt_embedded_sha256 = _digest(
        receipt_projection.pop("receipt_sha256", None),
        name="embedded source V1.1 receipt SHA-256",
    )
    if (
        source_receipt.get("schema_id")
        != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
        or source_receipt_sha256 != receipt_embedded_sha256
        or _sha256(receipt_projection) != source_receipt_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "source V1.1 receipt schema or self-hash is invalid"
        )

    proposal_index = document.get("proposal_index")
    parent_index = document.get("source_paired_parent_proposal_index")
    if (
        type(proposal_index) is not int
        or not 0 <= proposal_index < allocation.candidate_count
        or type(parent_index) is not int
        or dict(allocation.rescue_target_parent_pairs).get(proposal_index)
        != parent_index
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot proposal allocation identity is invalid"
        )
    candidate_id = document.get("candidate_id")
    if type(candidate_id) is not str or not candidate_id:
        raise SourcePairedClearanceActivationError("snapshot candidate ID is invalid")
    candidate_proposal_sha256 = _digest(
        document.get("candidate_proposal_fingerprint_sha256"),
        name="candidate proposal fingerprint",
    )
    source_proposal_sha256 = _digest(
        document.get("source_proposal_fingerprint_sha256"),
        name="source proposal fingerprint",
    )
    source_coordinate_sha256 = _digest(
        document.get("source_coordinate_sha256"),
        name="source coordinate SHA-256",
    )
    candidate_coordinate_sha256 = _digest(
        document.get("candidate_coordinate_sha256"),
        name="candidate coordinate SHA-256",
    )
    source_torsion_sha256 = _digest(
        document.get("source_torsion_metadata_sha256"),
        name="source torsion metadata SHA-256",
    )
    candidate_torsion_sha256 = _digest(
        document.get("candidate_torsion_metadata_sha256"),
        name="candidate torsion metadata SHA-256",
    )
    baseline_torsion_sha256 = _digest(
        document.get("v6_baseline_torsion_metadata_sha256"),
        name="V6 baseline torsion metadata SHA-256",
    )
    optimized_torsion_sha256 = _digest(
        document.get("optimized_torsion_metadata_sha256"),
        name="optimized torsion metadata SHA-256",
    )
    source_proposal_receipt_sha256 = _digest(
        document.get("source_proposal_receipt_sha256"),
        name="source proposal receipt SHA-256",
    )
    _source_proposal_receipt(
        document.get("source_proposal_receipt_payload"),
        expected_sha256=source_proposal_receipt_sha256,
        allocation_payload=allocation.to_dict(),
        authenticated_input_receipt_sha256=(
            allocation.authenticated_input_receipt_sha256
        ),
        proposal_index=proposal_index,
        parent_index=parent_index,
        expected_candidate_id=candidate_id,
        expected_source_proposal_sha256=source_proposal_sha256,
        expected_source_coordinate_sha256=source_coordinate_sha256,
        expected_source_torsion_sha256=source_torsion_sha256,
        target_slot_value=document.get("source_proposal_slot"),
        parent_slot_value=document.get("source_parent_slot"),
    )
    if (
        current_v7_proposal.candidate_id != candidate_id
        or current_v7_proposal.proposal_index != proposal_index
        or current_v7_proposal.fingerprint_sha256 != candidate_proposal_sha256
        or current_v7_proposal.coordinate_fingerprint_sha256
        != candidate_coordinate_sha256
        or _torsion_metadata_sha256(current_v7_proposal.torsion_angles)
        != candidate_torsion_sha256
        or current_v7_proposal.parent_proposal_fingerprint_sha256
        != source_proposal_sha256
        or current_v7_proposal.refiner_id
        != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_ID
        or current_v7_proposal.refiner_version
        != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_VERSION
        or current_v7_proposal.refinement_receipt_sha256 != source_receipt_sha256
        or source_receipt.get("source_proposal_sha256") != source_proposal_sha256
        or source_receipt.get("source_paired_torsion_rescue_allocation_sha256")
        != allocation_sha256
        or source_receipt.get("source_paired_parent_proposal_index") != parent_index
        or source_receipt.get("proposal_torsion_eligibility_lane")
        != "source_paired_torsion_rescue_variant"
        or source_receipt.get("post_coordinates_sha256") != candidate_coordinate_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "current V7 proposal and snapshot lineage are cross-wired"
        )
    _digest(source_coordinate_sha256, name="source coordinate SHA-256")

    ligand_atom_count = _nonnegative_int(
        document.get("ligand_atom_count"),
        name="ligand atom count",
    )
    receptor_atom_count = _nonnegative_int(
        document.get("receptor_atom_count"),
        name="receptor atom count",
    )
    exact_pair_count = _nonnegative_int(
        document.get("exact_pair_count"),
        name="exact pair count",
    )
    _nonnegative_int(
        document.get("evaluated_internal_pair_count"),
        name="evaluated internal pair count",
    )
    if (
        ligand_atom_count <= 0
        or receptor_atom_count <= 0
        or ligand_atom_count * receptor_atom_count != exact_pair_count
        or ligand_atom_count != len(current_v7_proposal.coordinates)
        or validity_context.get("ligand_atom_count") != ligand_atom_count
        or validity_context.get("receptor_atom_count") != receptor_atom_count
        or len(ligand_elements) != ligand_atom_count
        or len(receptor_elements) != receptor_atom_count
        or len(receptor_atom_indices) != receptor_atom_count
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot atom or pair counts are inconsistent"
        )
    receptor_coordinates_sha256 = _digest(
        validity_context.get("receptor_coordinates_sha256"),
        name="validity-context receptor coordinate SHA-256",
    )
    receptor_coordinates = _validity_receptor_tensor_from_payload(
        document.get("receptor_coordinates"),
        receptor_atom_count=receptor_atom_count,
        expected_sha256=receptor_coordinates_sha256,
    )
    ligand_radii = torch.tensor(
        [contact_policy.radius(element) for element in ligand_elements],
        dtype=torch.float64,
    )
    receptor_radii = torch.tensor(
        [contact_policy.radius(element) for element in receptor_elements],
        dtype=torch.float64,
    )

    baseline_coordinates, baseline_coordinate_sha256 = _tensor_from_payload(
        document.get("v6_baseline_coordinates"),
        name="V6 baseline coordinates",
        shape=(ligand_atom_count, 3),
        coordinate=True,
    )
    optimized_coordinates, optimized_coordinate_sha256 = _tensor_from_payload(
        document.get("optimized_coordinates"),
        name="optimized coordinates",
        shape=(ligand_atom_count, 3),
        coordinate=True,
    )
    baseline_torsions, _ = _tensor_from_payload(
        document.get("v6_baseline_torsion_angles"),
        name="V6 baseline torsion angles",
        shape=(ligand_atom_count,),
        coordinate=False,
    )
    optimized_torsions, _ = _tensor_from_payload(
        document.get("optimized_torsion_angles"),
        name="optimized torsion angles",
        shape=(ligand_atom_count,),
        coordinate=False,
    )
    if (
        _torsion_metadata_sha256(baseline_torsions) != baseline_torsion_sha256
        or baseline_torsion_sha256 != source_torsion_sha256
        or _torsion_metadata_sha256(optimized_torsions) != optimized_torsion_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot torsion tensors are not bound to their source identities"
        )
    for state_name, coordinate_payload, torsion_payload in (
        (
            "v6_baseline_state",
            document.get("v6_baseline_coordinates"),
            document.get("v6_baseline_torsion_angles"),
        ),
        (
            "optimized_state",
            document.get("optimized_coordinates"),
            document.get("optimized_torsion_angles"),
        ),
    ):
        state = _mapping(document.get(state_name), name=state_name)
        if set(state) != {"coordinates", "torsion_angles"} or (
            state.get("coordinates") != coordinate_payload
            or state.get("torsion_angles") != torsion_payload
        ):
            raise SourcePairedClearanceActivationError(
                f"{state_name} aliases are cross-wired"
            )

    baseline_statistics = _clearance_statistics(
        document.get("baseline_clearance_statistics"),
        name="baseline",
    )
    optimized_statistics = _clearance_statistics(
        document.get("optimized_clearance_statistics"),
        name="optimized",
    )
    clearance = _mapping(document.get("clearance"), name="clearance evidence")
    if (
        set(clearance)
        != {
            "evaluated",
            "reason",
            "unavailable_reason",
            "radii_policy_sha256",
            "ligand_atom_count",
            "receptor_atom_count",
            "exact_pair_count",
            "pair_count_bound",
            "baseline",
            "optimized",
        }
        or clearance.get("evaluated") is not True
        or clearance.get("reason") != "none"
        or clearance.get("unavailable_reason") != "none"
        or clearance.get("ligand_atom_count") != ligand_atom_count
        or clearance.get("receptor_atom_count") != receptor_atom_count
        or clearance.get("exact_pair_count") != exact_pair_count
        or clearance.get("baseline") != baseline_statistics
        or clearance.get("optimized") != optimized_statistics
        or type(clearance.get("pair_count_bound")) is not int
        or clearance.get("pair_count_bound") != MAX_RECEPTOR_CLEARANCE_PAIR_COUNT
        or exact_pair_count > clearance["pair_count_bound"]
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot clearance evidence is incomplete or cross-wired"
        )
    vdw_policy_sha256 = _digest(
        document.get("vdw_contact_policy_sha256"),
        name="VDW contact policy SHA-256",
    )
    if (
        vdw_policy_sha256 != SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256
        or document.get("clearance_radii_policy_sha256") != vdw_policy_sha256
        or clearance.get("radii_policy_sha256") != vdw_policy_sha256
        or source_receipt.get("clearance_radii_policy_sha256") != vdw_policy_sha256
        or source_receipt.get("clearance_ligand_atom_count") != ligand_atom_count
        or source_receipt.get("clearance_receptor_atom_count") != receptor_atom_count
        or source_receipt.get("clearance_full_cartesian_pair_count") != exact_pair_count
        or source_receipt.get("clearance_measurement_evaluated") is not True
        or source_receipt.get("clearance_measurement_unavailable_reason") != "none"
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot VDW policy or clearance receipt is cross-wired"
        )
    try:
        rederived_baseline_statistics = _receptor_clearance_statistics(
            baseline_coordinates,
            receptor_coordinates=receptor_coordinates,
            ligand_radii=ligand_radii,
            receptor_radii=receptor_radii,
            receptor_atom_indices=receptor_atom_indices,
        ).to_dict()
        rederived_optimized_statistics = _receptor_clearance_statistics(
            optimized_coordinates,
            receptor_coordinates=receptor_coordinates,
            ligand_radii=ligand_radii,
            receptor_radii=receptor_radii,
            receptor_atom_indices=receptor_atom_indices,
        ).to_dict()
    except TorsionContactRefinementError as exc:
        raise SourcePairedClearanceActivationError(
            "snapshot clearance statistics cannot be independently rederived"
        ) from exc
    if (
        baseline_statistics != rederived_baseline_statistics
        or optimized_statistics != rederived_optimized_statistics
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot clearance statistics do not match authenticated geometry"
        )

    objective_names = ("receptor", "internal", "combined")
    objectives = _mapping(document.get("objectives"), name="objectives")
    objective_values: dict[str, dict[str, float]] = {}
    if set(objectives) != {"baseline", "optimized"}:
        raise SourcePairedClearanceActivationError("objective arms are invalid")
    for arm in ("baseline", "optimized"):
        arm_payload = _mapping(objectives.get(arm), name=f"{arm} objectives")
        expected_keys = {f"{name}_binary64_hex" for name in objective_names}
        if set(arm_payload) != expected_keys:
            raise SourcePairedClearanceActivationError(
                f"{arm} objective evidence is incomplete"
            )
        objective_values[arm] = {
            name: _binary64(
                arm_payload[f"{name}_binary64_hex"],
                name=f"{arm} {name} objective",
                minimum=0.0,
            )
            for name in objective_names
        }
        if objective_values[arm]["combined"] != (
            objective_values[arm]["receptor"] + objective_values[arm]["internal"]
        ):
            raise SourcePairedClearanceActivationError(
                f"{arm} combined objective is inconsistent"
            )
        for name in objective_names:
            alias = f"{arm}_{name}_objective_binary64_hex"
            receipt_name = (
                f"{arm}_v6_{name}_penalty_binary64_hex"
                if arm == "baseline"
                else f"optimized_{name}_penalty_binary64_hex"
            )
            if arm == "baseline":
                receipt_name = f"baseline_v6_{name}_penalty_binary64_hex"
            if (
                document.get(alias) != arm_payload[f"{name}_binary64_hex"]
                or source_receipt.get(receipt_name)
                != arm_payload[f"{name}_binary64_hex"]
            ):
                raise SourcePairedClearanceActivationError(
                    f"{arm} {name} objective aliases are cross-wired"
                )

    torsion_state = _mapping(document.get("torsion_state"), name="torsion state")
    if (
        set(torsion_state)
        != {
            "evaluated",
            "variant_available",
            "selected",
            "evaluated_steps",
            "evaluated_moves",
        }
        or type(torsion_state.get("evaluated")) is not bool
        or type(torsion_state.get("variant_available")) is not bool
        or type(torsion_state.get("selected")) is not bool
        or type(torsion_state.get("evaluated_steps")) is not int
        or torsion_state["evaluated_steps"] < 0
        or type(torsion_state.get("evaluated_moves")) is not list
        or torsion_state["evaluated_steps"] != len(torsion_state["evaluated_moves"])
        or (
            torsion_state["variant_available"]
            and (
                not torsion_state["evaluated"] or torsion_state["evaluated_steps"] == 0
            )
        )
        or (torsion_state["selected"] and not torsion_state["variant_available"])
        or document.get("torsion_evaluated") is not torsion_state["evaluated"]
        or document.get("torsion_variant_available")
        is not torsion_state["variant_available"]
        or document.get("torsion_selected") is not torsion_state["selected"]
        or document.get("evaluated_torsion_steps") != torsion_state["evaluated_steps"]
        or document.get("evaluated_torsion_moves") != torsion_state["evaluated_moves"]
        or source_receipt.get("torsion_evaluated") is not torsion_state["evaluated"]
        or source_receipt.get("torsion_variant_available")
        is not torsion_state["variant_available"]
        or source_receipt.get("torsion_selected") is not torsion_state["selected"]
        or source_receipt.get("evaluated_torsion_steps")
        != torsion_state["evaluated_steps"]
        or source_receipt.get("evaluated_torsion_moves")
        != torsion_state["evaluated_moves"]
    ):
        raise SourcePairedClearanceActivationError(
            "snapshot torsion state is incomplete or cross-wired"
        )

    allowed_rotor_values = source_receipt.get("rotatable_child_atom_indices")
    if (
        type(allowed_rotor_values) is not list
        or any(
            type(rotor) is not int or not 0 <= rotor < ligand_atom_count
            for rotor in allowed_rotor_values
        )
        or len(allowed_rotor_values) != len(set(allowed_rotor_values))
    ):
        raise SourcePairedClearanceActivationError(
            "source receipt rotatable-child authority is invalid"
        )
    allowed_rotors = frozenset(allowed_rotor_values)
    replayed_torsions = baseline_torsions.clone()
    move_keys = {
        "rotatable_child_atom_index",
        "delta_radians_binary64_hex",
        "receptor_penalty_binary64_hex",
        "internal_penalty_binary64_hex",
        "combined_penalty_binary64_hex",
    }
    for move_index, raw_move in enumerate(torsion_state["evaluated_moves"]):
        move = _mapping(raw_move, name=f"evaluated torsion move {move_index}")
        rotor = move.get("rotatable_child_atom_index")
        if (
            set(move) != move_keys
            or type(rotor) is not int
            or rotor not in allowed_rotors
        ):
            raise SourcePairedClearanceActivationError(
                "evaluated torsion move is outside the source rotor authority"
            )
        delta = _binary64(
            move.get("delta_radians_binary64_hex"),
            name=f"evaluated torsion move {move_index} delta",
        )
        receptor_penalty = _binary64(
            move.get("receptor_penalty_binary64_hex"),
            name=f"evaluated torsion move {move_index} receptor penalty",
            minimum=0.0,
        )
        internal_penalty = _binary64(
            move.get("internal_penalty_binary64_hex"),
            name=f"evaluated torsion move {move_index} internal penalty",
            minimum=0.0,
        )
        combined_penalty = _binary64(
            move.get("combined_penalty_binary64_hex"),
            name=f"evaluated torsion move {move_index} combined penalty",
            minimum=0.0,
        )
        if combined_penalty != receptor_penalty + internal_penalty:
            raise SourcePairedClearanceActivationError(
                "evaluated torsion move objective terms are inconsistent"
            )
        replayed_torsions[rotor] = math.atan2(
            math.sin(float(replayed_torsions[rotor].item()) + delta),
            math.cos(float(replayed_torsions[rotor].item()) + delta),
        )
    replayed_torsions = replayed_torsions.to(
        dtype=current_v7_proposal.torsion_angles.dtype
    ).to(dtype=torch.float64)
    expected_candidate_torsion_sha256 = (
        optimized_torsion_sha256
        if torsion_state["selected"]
        else baseline_torsion_sha256
    )
    if (
        not torch.equal(replayed_torsions, optimized_torsions)
        or _torsion_metadata_sha256(replayed_torsions) != optimized_torsion_sha256
        or candidate_torsion_sha256 != expected_candidate_torsion_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "optimized torsion state does not replay from authenticated moves"
        )

    current_coordinates = current_v7_proposal.coordinates.to(dtype=torch.float64)
    current_torsions = current_v7_proposal.torsion_angles.to(dtype=torch.float64)
    expected_current_coordinates = (
        optimized_coordinates if torsion_state["selected"] else baseline_coordinates
    )
    expected_current_torsions = (
        optimized_torsions if torsion_state["selected"] else baseline_torsions
    )
    expected_current_sha256 = (
        optimized_coordinate_sha256
        if torsion_state["selected"]
        else baseline_coordinate_sha256
    )
    if (
        candidate_coordinate_sha256 != expected_current_sha256
        or source_receipt.get("baseline_coordinates_sha256")
        != baseline_coordinate_sha256
        or source_receipt.get("optimized_coordinates_sha256")
        != optimized_coordinate_sha256
        or source_receipt.get(
            "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
        )
        != baseline_statistics["minimum_vdw_surface_gap_angstrom_binary64_hex"]
        or source_receipt.get("optimized_minimum_vdw_surface_gap_angstrom_binary64_hex")
        != optimized_statistics["minimum_vdw_surface_gap_angstrom_binary64_hex"]
        or not torch.equal(current_coordinates, expected_current_coordinates)
        or not torch.equal(current_torsions, expected_current_torsions)
    ):
        raise SourcePairedClearanceActivationError(
            "current V7 state does not match the source receipt"
        )

    selected_policy = policy or SourcePairedTorsionRescueClearanceSelectionPolicyV1()
    if type(selected_policy) is not SourcePairedTorsionRescueClearanceSelectionPolicyV1:
        raise TypeError(
            "policy must be SourcePairedTorsionRescueClearanceSelectionPolicyV1"
        )
    if (
        selected_policy.fingerprint_sha256
        != SOURCE_PAIRED_CLEARANCE_SELECTION_POLICY_SHA256
        or document.get("generic_v7_config_sha256")
        != InteractionAwareTorsionContactConfigV7().fingerprint_sha256
    ):
        raise SourcePairedClearanceActivationError(
            "frozen clearance policy or generic V7 configuration drifted"
        )

    probe = SourcePairedTorsionRescueClearanceSelectionProbeInputsV1(
        allocation=allocation,
        proposal_index=proposal_index,
        source_refinement_receipt_schema_id=(
            INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
        ),
        generic_v7_config_sha256=document["generic_v7_config_sha256"],
        vdw_contact_policy_sha256=vdw_policy_sha256,
        baseline_coordinates_sha256=baseline_coordinate_sha256,
        optimized_coordinates_sha256=optimized_coordinate_sha256,
        torsion_variant_available=torsion_state["variant_available"],
        legacy_v7_selected=torsion_state["selected"],
        clearance_measurement_evaluated=True,
        clearance_measurement_unavailable_reason="none",
        clearance_ligand_atom_count=ligand_atom_count,
        clearance_receptor_atom_count=receptor_atom_count,
        clearance_full_cartesian_pair_count=exact_pair_count,
        baseline_receptor_objective=objective_values["baseline"]["receptor"],
        optimized_receptor_objective=objective_values["optimized"]["receptor"],
        baseline_internal_objective=objective_values["baseline"]["internal"],
        optimized_internal_objective=objective_values["optimized"]["internal"],
        baseline_combined_objective=objective_values["baseline"]["combined"],
        optimized_combined_objective=objective_values["optimized"]["combined"],
        baseline_minimum_vdw_surface_gap_angstrom=_binary64(
            baseline_statistics["minimum_vdw_surface_gap_angstrom_binary64_hex"],
            name="baseline minimum VDW gap",
        ),
        optimized_minimum_vdw_surface_gap_angstrom=_binary64(
            optimized_statistics["minimum_vdw_surface_gap_angstrom_binary64_hex"],
            name="optimized minimum VDW gap",
        ),
        baseline_raw_minimum_distance_angstrom=_binary64(
            baseline_statistics["minimum_distance_angstrom_binary64_hex"],
            name="baseline raw minimum distance",
            minimum=0.0,
        ),
        optimized_raw_minimum_distance_angstrom=_binary64(
            optimized_statistics["minimum_distance_angstrom_binary64_hex"],
            name="optimized raw minimum distance",
            minimum=0.0,
        ),
    )
    decision = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        probe,
        policy=selected_policy,
    )
    policy_payload = selected_policy.to_dict()
    probe_payload = probe.to_dict()
    decision_payload = decision.to_dict()
    if (
        policy_payload.get("fingerprint_sha256")
        != SOURCE_PAIRED_CLEARANCE_SELECTION_POLICY_SHA256
        or probe_payload.get("fingerprint_sha256") != decision.probe_inputs_sha256
        or decision_payload.get("decision_sha256") != decision.decision_sha256
        or decision.policy_sha256 != selected_policy.fingerprint_sha256
        or decision.allocation_sha256 != allocation_sha256
        or decision.proposal_index != proposal_index
    ):
        raise SourcePairedClearanceActivationError(
            "clearance probe or decision binding is invalid"
        )

    if decision.shadow_selection_eligible:
        selected_proposal = current_v7_proposal.with_refined_coordinates(
            optimized_coordinates.to(dtype=current_v7_proposal.coordinates.dtype),
            refiner_id=SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_ID,
            refiner_version=SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_VERSION,
            refinement_receipt_sha256=decision.decision_sha256,
            torsion_angles=optimized_torsions.to(
                dtype=current_v7_proposal.torsion_angles.dtype
            ),
        )
        selected_action = "select_shadow_eligible_optimized_state"
    else:
        selected_proposal = replace(current_v7_proposal)
        selected_action = "retain_exact_current_v7_state"
    selected_proposal.assert_integrity()

    projection = {
        "schema_id": SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
        "source_snapshot_sha256": snapshot_sha256,
        "source_v11_receipt_sha256": source_receipt_sha256,
        "allocation_receipt_sha256": allocation_sha256,
        "source_proposal_receipt_sha256": source_proposal_receipt_sha256,
        "policy_sha256": selected_policy.fingerprint_sha256,
        "probe_input_sha256": probe.fingerprint_sha256,
        "decision_sha256": decision.decision_sha256,
        "policy_payload": policy_payload,
        "probe_input_payload": probe_payload,
        "decision_payload": decision_payload,
        "candidate_id": candidate_id,
        "proposal_index": proposal_index,
        "source_proposal_fingerprint_sha256": source_proposal_sha256,
        "baseline_candidate_proposal_fingerprint_sha256": (
            current_v7_proposal.fingerprint_sha256
        ),
        "baseline_candidate_coordinate_sha256": (
            current_v7_proposal.coordinate_fingerprint_sha256
        ),
        "selected_or_retained_candidate_proposal_fingerprint_sha256": (
            selected_proposal.fingerprint_sha256
        ),
        "selected_or_retained_coordinate_sha256": (
            selected_proposal.coordinate_fingerprint_sha256
        ),
        "baseline_candidate_state": _proposal_state_payload(current_v7_proposal),
        "selected_or_retained_state": _proposal_state_payload(selected_proposal),
        "selected_action": selected_action,
        "shadow_selection_eligible": decision.shadow_selection_eligible,
        "selection_applied": decision.shadow_selection_eligible,
        "decision_sealed_before_scoring": True,
        "score_rank_rmsd_posebusters_native_or_case_identity_used": False,
        "result_dependent_allocation": False,
        "default_v7_output_changed": False,
        "historical_ab_execution_authorized": False,
        "historical_result_materialization_authorized": False,
        "generic_runner_cli_wired": False,
        "product_path_wired": False,
        "fresh_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "stage0_eligible": False,
        "public_or_scientific_claim_authorized": False,
        "development_only": True,
        "claim_safe": False,
    }
    return _build_activated_state(
        baseline_proposal=current_v7_proposal,
        selected_proposal=selected_proposal,
        projection=projection,
        _builder_token=_ACTIVATED_STATE_BUILDER_TOKEN,
    )


__all__ = [
    "SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_ID",
    "SOURCE_PAIRED_CLEARANCE_ACTIVATION_REFINER_VERSION",
    "SOURCE_PAIRED_CLEARANCE_SELECTION_POLICY_SHA256",
    "SourcePairedClearanceActivatedStateV1",
    "SourcePairedClearanceActivationError",
    "build_source_paired_clearance_activated_state_v1",
]
