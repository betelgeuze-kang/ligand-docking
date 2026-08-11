"""Materialize admitted mixed64 geometry as exact operational proposals.

The bridge consumes only one sealed geometric-admission v3 batch. Complete
source proposal identity payloads are rederived as ``DockingProposal`` values;
accepted transformed lanes receive the allocation-owned quaternion and
translation. Unsupported historical identity payloads become typed slot
failures instead of guessed proposal state.

This component does not refine, score, evaluate validity, reserve, or execute a
molecular cohort. Its receipts are structural and non-authoritative.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
import re
from typing import Final

import torch

from .geometric_admission_v3 import (
    ACCEPTED_STATUS,
    GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    GeometricAdmissionBatchV3,
    GeometricAdmissionDecisionV3,
    GeometricAdmissionV3Error,
)
from .mixed64_allocation import (
    FIXED_MIXED64_CANDIDATE_COUNT,
    LANE_PAIRED_RETAINED_CONTROLS,
    LANE_POCKET_CENTERED_CONTROLS,
    LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
    LANE_UNIFORM_SOURCE_CONTROLS,
)
from .mixed64_proposal_geometry_v3 import (
    IndexedSO3PlacementReceiptV1,
    SingleAnchorPlacementReceiptV1,
    coordinate_sha256,
)
from .mixed64_proposal_producer_v3 import (
    GENERATION_STATUS_SUCCESS,
    ExactPassthroughPlacementReceiptV1,
    Mixed64CoordinateSourcePayloadV1,
    Mixed64ProposalProducerError,
)
from .mixed64_operational_proposal_policy_v3 import (
    BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256,
    DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID,
    MATERIALIZED_STATUS,
    MIXED64_OPERATIONAL_PROPOSAL_BATCH_SCHEMA_ID,
    MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID,
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SCHEMA_ID,
    MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
    MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID,
    MIXED64_OPERATIONAL_PROPOSAL_RECORD_SCHEMA_ID,
    PLACEMENT_TRANSFORM_CROSS_WIRED,
    REQUIRED_PROPOSAL_NUMERIC_POLICY_ID,
    SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED,
    SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
    SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
    TYPED_MATERIALIZATION_FAILURE_STATUS,
    UNSUPPORTED_PLACEMENT_RECEIPT,
    UPSTREAM_NOT_MATERIALIZED_STATUS,
    frozen_mixed64_operational_proposal_policy,
)
from .proposals import (
    PROPOSAL_NUMERIC_POLICY_ID,
    DockingProposal,
    DockingProposalError,
    bind_docking_proposal_state,
)


_STATUSES: Final = {
    MATERIALIZED_STATUS,
    TYPED_MATERIALIZATION_FAILURE_STATUS,
    UPSTREAM_NOT_MATERIALIZED_STATUS,
}
_MATERIALIZATION_FAILURE_CODES: Final = {
    SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
    SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED,
    SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
    PLACEMENT_TRANSFORM_CROSS_WIRED,
    UNSUPPORTED_PLACEMENT_RECEIPT,
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECORD_FACTORY_SEAL = object()
_BATCH_FACTORY_SEAL = object()
_MAX_IDENTITY_JSON_BYTES: Final = 4 * 1024 * 1024
_MAX_LIGAND_ATOMS: Final = 512
_MAX_SEED: Final = (1 << 63) - 1
_EXPECTED_IDENTITY_KEYS: Final = {
    "schema_id",
    "numeric_policy_id",
    "proposal_index",
    "seed",
    "problem_fingerprint_sha256",
    "search_space_fingerprint_sha256",
    "coordinate_fingerprint_sha256",
    "parent_proposal_fingerprint_sha256",
    "refiner_id",
    "refiner_version",
    "refinement_receipt_sha256",
    "torsion_angles",
    "rotation",
    "translation",
}

if PROPOSAL_NUMERIC_POLICY_ID != REQUIRED_PROPOSAL_NUMERIC_POLICY_ID:
    raise RuntimeError("operational proposal numeric policy binding changed")
if GEOMETRIC_ADMISSION_V3_POLICY_SHA256 != BOUND_GEOMETRIC_ADMISSION_V3_POLICY_SHA256:
    raise RuntimeError("operational proposal admission policy binding changed")


class Mixed64OperationalProposalV3Error(ValueError):
    """Raised when operational proposal materialization cannot stay exact."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise Mixed64OperationalProposalV3Error(code, message)


def _canonical_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            "proposal identity is not canonical JSON",
        ) from exc
    if len(payload) > _MAX_IDENTITY_JSON_BYTES:
        _fail(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            "proposal identity exceeds the byte bound",
        )
    return payload


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seal_projection(value: object) -> tuple[bytes, str]:
    payload = _canonical_bytes(value)
    return payload, hashlib.sha256(payload).hexdigest()


def _unseal_projection(payload: bytes) -> dict[str, object]:
    document = json.loads(payload)
    if type(document) is not dict:
        _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "sealed receipt is not an object")
    return document


def _verify_sealed_receipt(payload: bytes, expected: str, *, name: str) -> str:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, f"{name} sealed receipt changed")
    return observed


def _verify_live_sealed_projection(
    payload: bytes,
    expected: str,
    projection: object,
    *,
    name: str,
) -> str:
    observed = _verify_sealed_receipt(payload, expected, name=name)
    if _canonical_bytes(projection) != payload:
        _fail(
            SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
            f"{name} live projection changed",
        )
    return observed


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL, f"{name} is not SHA-256")
    return value


def _float_vector(
    value: object,
    *,
    name: str,
    expected_shape: tuple[int, ...],
) -> torch.Tensor:
    expected_count = math.prod(expected_shape)
    if (
        type(value) is not dict
        or set(value) != {"dtype", "shape", "values_binary64_hex"}
        or value.get("dtype") != "float64"
        or value.get("shape") != list(expected_shape)
        or type(value.get("values_binary64_hex")) is not list
        or len(value["values_binary64_hex"]) != expected_count
    ):
        _fail(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            f"{name} denominator is invalid",
        )
    rows = []
    for item in value["values_binary64_hex"]:
        if type(item) is not str:
            _fail(SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL, f"{name} is not binary64")
        try:
            observed = float.fromhex(item)
        except ValueError as exc:
            raise Mixed64OperationalProposalV3Error(
                SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
                f"{name} is not binary64",
            ) from exc
        if not math.isfinite(observed):
            _fail(SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL, f"{name} is not finite")
        rows.append(observed)
    return torch.tensor(rows, dtype=torch.float64)


def _coordinates_tensor(
    coordinates: tuple[tuple[float, float, float], ...],
) -> torch.Tensor:
    if not coordinates or len(coordinates) > _MAX_LIGAND_ATOMS:
        _fail(SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED, "coordinate denominator is invalid")
    return torch.tensor(coordinates, dtype=torch.float64)


def _source_for_slot(
    batch: GeometricAdmissionBatchV3,
    *,
    slot_index: int,
) -> Mixed64CoordinateSourcePayloadV1:
    producer_batch = batch.producer_batch
    bundle = producer_batch.source_bundle
    slot = producer_batch.allocation.slots[slot_index]
    record = producer_batch.records[slot_index]
    placement = record.placement_receipt
    if type(placement) is ExactPassthroughPlacementReceiptV1:
        return placement.source_payload
    if slot.lane in {LANE_POCKET_CENTERED_CONTROLS, LANE_UNIFORM_SOURCE_CONTROLS}:
        assert slot.v7_control_source_index is not None
        source = bundle.v7_control_for_index(slot.v7_control_source_index)
    elif slot.lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        assert slot.true_conformer_rank is not None
        source = bundle.conformer_for_rank(slot.true_conformer_rank)
    elif slot.lane == LANE_PAIRED_RETAINED_CONTROLS:
        assert slot.retained_source_index is not None
        source = bundle.retained_for_index(slot.retained_source_index)
    else:
        source = bundle.exact_v11_source
    if source is None:
        _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "producer source payload is absent")
    return source


def _parse_source_proposal(
    source: Mixed64CoordinateSourcePayloadV1,
) -> DockingProposal:
    raw = source.proposal_identity_payload_canonical_json
    try:
        document = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            "proposal identity JSON is invalid",
        ) from exc
    if (
        type(document) is not dict
        or set(document) != _EXPECTED_IDENTITY_KEYS
        or document.get("schema_id") != DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID
        or document.get("numeric_policy_id") != PROPOSAL_NUMERIC_POLICY_ID
        or _canonical_bytes(document) != raw
        or hashlib.sha256(raw).hexdigest() != source.proposal_sha256
    ):
        _fail(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            "source payload is not an exact DockingProposal identity",
        )
    proposal_index = document["proposal_index"]
    seed = document["seed"]
    if (
        type(proposal_index) is not int
        or proposal_index < 0
        or type(seed) is not int
        or not 0 <= seed <= _MAX_SEED
    ):
        _fail(SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL, "proposal index or seed is invalid")
    coordinates = _coordinates_tensor(source.coordinates)
    torsions = _float_vector(
        document["torsion_angles"],
        name="torsion_angles",
        expected_shape=(len(source.coordinates),),
    )
    rotation = _float_vector(
        document["rotation"],
        name="rotation",
        expected_shape=(3, 3),
    ).reshape(3, 3)
    translation = _float_vector(
        document["translation"],
        name="translation",
        expected_shape=(3,),
    )
    try:
        proposal = DockingProposal(
            candidate_id=f"pose-{proposal_index:05d}-{source.proposal_sha256[:12]}",
            coordinates=coordinates,
            torsion_angles=torsions,
            rotation=rotation,
            translation=translation,
            proposal_index=proposal_index,
            seed=seed,
            fingerprint_sha256=source.proposal_sha256,
            problem_fingerprint_sha256=_digest(
                document["problem_fingerprint_sha256"],
                name="problem_fingerprint_sha256",
            ),
            search_space_fingerprint_sha256=_digest(
                document["search_space_fingerprint_sha256"],
                name="search_space_fingerprint_sha256",
            ),
            coordinate_fingerprint_sha256=_digest(
                document["coordinate_fingerprint_sha256"],
                name="coordinate_fingerprint_sha256",
            ),
            parent_proposal_fingerprint_sha256=_digest(
                document["parent_proposal_fingerprint_sha256"],
                name="parent_proposal_fingerprint_sha256",
                allow_empty=True,
            ),
            refiner_id=str(document["refiner_id"]),
            refiner_version=str(document["refiner_version"]),
            refinement_receipt_sha256=_digest(
                document["refinement_receipt_sha256"],
                name="refinement_receipt_sha256",
                allow_empty=True,
            ),
        )
    except DockingProposalError as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL,
            "source DockingProposal identity does not rederive",
        ) from exc
    if proposal.identity_payload() != document:
        _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "source identity projection changed")
    return proposal


def _rotation_matrix(
    quaternion: tuple[float, float, float, float],
) -> torch.Tensor:
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if not math.isfinite(norm) or norm <= 1.0e-15:
        _fail(PLACEMENT_TRANSFORM_CROSS_WIRED, "placement quaternion is degenerate")
    x, y, z, w = (value / norm for value in (x, y, z, w))
    return torch.tensor(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        ),
        dtype=torch.float64,
    )


def _materialization_seed(
    *,
    source_receipt_sha256: str,
    slot_index: int,
) -> int:
    payload = _canonical_bytes(
        {
            "policy_sha256": MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
            "source_receipt_sha256": source_receipt_sha256,
            "slot_index": slot_index,
        }
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & _MAX_SEED


@dataclass(frozen=True, slots=True)
class Mixed64OperationalProposalRecordV1:
    admission_decision: GeometricAdmissionDecisionV3 = field(repr=False)
    source_payload: Mixed64CoordinateSourcePayloadV1 | None = field(repr=False)
    source_operational_proposal: DockingProposal | None = field(repr=False)
    operational_proposal: DockingProposal | None = field(repr=False)
    status: str
    failure_code: str | None
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_OPERATIONAL_PROPOSAL_RECORD_SCHEMA_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECORD_FACTORY_SEAL:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "record requires bounded factory")
        if self.schema_id != MIXED64_OPERATIONAL_PROPOSAL_RECORD_SCHEMA_ID:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "record schema changed")
        if type(self.admission_decision) is not GeometricAdmissionDecisionV3:
            raise TypeError("admission_decision must be exact")
        if self.status not in _STATUSES:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "record status is invalid")
        if self.status == MATERIALIZED_STATUS:
            if (
                self.admission_decision.status != ACCEPTED_STATUS
                or type(self.source_payload) is not Mixed64CoordinateSourcePayloadV1
                or type(self.source_operational_proposal) is not DockingProposal
                or type(self.operational_proposal) is not DockingProposal
                or self.failure_code is not None
            ):
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "materialized record is incomplete")
            producer_record = self.admission_decision.producer_record
            if (
                producer_record.source_proposal_sha256 is None
                or producer_record.source_coordinate_sha256 is None
                or producer_record.output_coordinates is None
                or coordinate_sha256(
                    tuple(
                        tuple(float(component) for component in point)
                        for point in self.operational_proposal.coordinates.tolist()
                    )
                )
                != producer_record.source_coordinate_sha256
                or coordinate_sha256(
                    tuple(
                        tuple(float(component) for component in point)
                        for point in self.source_operational_proposal.coordinates.tolist()
                    )
                )
                != self.source_payload.coordinate_sha256
            ):
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "materialized lineage is absent")
            self.source_operational_proposal.assert_integrity()
            self.operational_proposal.assert_integrity()
            source = self.source_operational_proposal
            operational = self.operational_proposal
            placement = producer_record.placement_receipt
            expected_seed = _materialization_seed(
                source_receipt_sha256=self.source_payload.receipt_sha256,
                slot_index=self.slot_index,
            )
            if (
                source.fingerprint_sha256 != self.source_payload.proposal_sha256
                or operational.proposal_index != self.slot_index
                or operational.seed != expected_seed
                or not torch.equal(operational.torsion_angles, source.torsion_angles)
                or operational.problem_fingerprint_sha256
                != source.problem_fingerprint_sha256
                or operational.search_space_fingerprint_sha256
                != source.search_space_fingerprint_sha256
                or operational.refined
            ):
                _fail(
                    SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
                    "operational slot identity or source state changed",
                )
            if type(placement) is ExactPassthroughPlacementReceiptV1:
                expected_rotation = source.rotation
                expected_translation = source.translation
            elif type(placement) in {
                IndexedSO3PlacementReceiptV1,
                SingleAnchorPlacementReceiptV1,
            }:
                placement_rotation = _rotation_matrix(placement.quaternion)
                placement_translation = torch.tensor(
                    placement.translation,
                    dtype=torch.float64,
                )
                expected_rotation = placement_rotation @ source.rotation
                expected_translation = (
                    source.translation @ placement_rotation.T
                    + placement_translation
                )
            else:
                _fail(
                    UNSUPPORTED_PLACEMENT_RECEIPT,
                    "materialized placement receipt is not supported",
                )
            if not torch.equal(operational.rotation, expected_rotation) or not torch.equal(
                operational.translation,
                expected_translation,
            ):
                _fail(
                    PLACEMENT_TRANSFORM_CROSS_WIRED,
                    "operational rigid transform composition changed",
                )
        elif self.status == TYPED_MATERIALIZATION_FAILURE_STATUS:
            if (
                self.admission_decision.status != ACCEPTED_STATUS
                or self.operational_proposal is not None
                or self.failure_code not in _MATERIALIZATION_FAILURE_CODES
            ):
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "typed failure is invalid")
        else:
            if (
                self.admission_decision.status == ACCEPTED_STATUS
                or any(
                    value is not None
                    for value in (
                        self.source_payload,
                        self.source_operational_proposal,
                        self.operational_proposal,
                        self.failure_code,
                    )
                )
            ):
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "upstream record fabricated state")
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def slot_index(self) -> int:
        return self.admission_decision.slot_index

    @property
    def materialized(self) -> bool:
        return self.status == MATERIALIZED_STATUS

    def _projection(self) -> dict[str, object]:
        producer = self.admission_decision.producer_record
        source = self.source_operational_proposal
        operational = self.operational_proposal
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID,
            "policy_sha256": MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
            "slot_index": self.slot_index,
            "lane": producer.allocation.slots[self.slot_index].lane,
            "admission_decision_receipt_sha256": self.admission_decision.receipt_sha256,
            "producer_record_receipt_sha256": producer.receipt_sha256,
            "producer_evidence_proposal_sha256": producer.source_proposal_sha256,
            "producer_coordinate_sha256": producer.source_coordinate_sha256,
            "source_payload_receipt_sha256": (
                None if self.source_payload is None else self.source_payload.receipt_sha256
            ),
            "source_operational_proposal_sha256": (
                None if source is None else source.fingerprint_sha256
            ),
            "source_operational_proposal_index": (
                None if source is None else source.proposal_index
            ),
            "source_operational_coordinate_fingerprint_sha256": (
                None if source is None else source.coordinate_fingerprint_sha256
            ),
            "operational_proposal_sha256": (
                None if operational is None else operational.fingerprint_sha256
            ),
            "operational_proposal_index": (
                None if operational is None else operational.proposal_index
            ),
            "operational_proposal_seed": (
                None if operational is None else operational.seed
            ),
            "operational_coordinate_fingerprint_sha256": (
                None if operational is None else operational.coordinate_fingerprint_sha256
            ),
            "operational_proposal_identity": (
                None if operational is None else operational.identity_payload()
            ),
            "status": self.status,
            "failure_code": self.failure_code,
            "upstream_status": self.admission_decision.status,
            "evidence_and_operational_coordinate_identities_both_preserved": True,
            "source_operational_identity_preserved_separately": source is not None,
            "operational_proposal_index_is_fixed64_slot": (
                None if operational is None else operational.proposal_index == self.slot_index
            ),
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "molecular_execution_authorized": False,
            "reservation_allowed": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="operational proposal record",
        )

    def assert_live_integrity(self) -> str:
        return self._assert_live_integrity(admission_already_verified=False)

    def _assert_live_integrity(self, *, admission_already_verified: bool) -> str:
        try:
            if not admission_already_verified:
                self.admission_decision.assert_live_integrity()
            if self.source_payload is not None:
                self.source_payload.assert_live_integrity()
            if self.source_operational_proposal is not None:
                self.source_operational_proposal.assert_integrity()
            if self.operational_proposal is not None:
                self.operational_proposal.assert_integrity()
            return _verify_live_sealed_projection(
                self._canonical_projection_bytes,
                self._receipt_sha256,
                self._projection(),
                name="operational proposal record",
            )
        except Mixed64OperationalProposalV3Error:
            raise
        except (
            DockingProposalError,
            GeometricAdmissionV3Error,
            Mixed64ProposalProducerError,
        ) as exc:
            raise Mixed64OperationalProposalV3Error(
                SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
                "operational proposal record live integrity failed",
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class Mixed64OperationalProposalBatchV1:
    admission_batch: GeometricAdmissionBatchV3 = field(repr=False)
    records: tuple[Mixed64OperationalProposalRecordV1, ...]
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_OPERATIONAL_PROPOSAL_BATCH_SCHEMA_ID
    profile_id: str = MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch requires bounded factory")
        if (
            self.schema_id != MIXED64_OPERATIONAL_PROPOSAL_BATCH_SCHEMA_ID
            or self.profile_id != MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID
        ):
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch identity changed")
        if type(self.admission_batch) is not GeometricAdmissionBatchV3:
            raise TypeError("admission_batch must be exact")
        if (
            type(self.records) is not tuple
            or len(self.records) != FIXED_MIXED64_CANDIDATE_COUNT
            or any(type(value) is not Mixed64OperationalProposalRecordV1 for value in self.records)
            or tuple(value.slot_index for value in self.records) != tuple(range(64))
        ):
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch denominator or order changed")
        for decision, record in zip(self.admission_batch.decisions, self.records, strict=True):
            if decision.receipt_sha256 != record.admission_decision.receipt_sha256:
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch decision binding changed")
        materialized = tuple(value for value in self.records if value.materialized)
        if len(
            {
                value.operational_proposal.problem_fingerprint_sha256
                for value in materialized
                if value.operational_proposal is not None
            }
        ) > 1:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch problem identity is cross-wired")
        if len(
            {
                value.operational_proposal.search_space_fingerprint_sha256
                for value in materialized
                if value.operational_proposal is not None
            }
        ) > 1:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "batch search-space identity is cross-wired")
        sealed, receipt_sha256 = _seal_projection(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", sealed)
        object.__setattr__(self, "_receipt_sha256", receipt_sha256)

    @property
    def materialized_count(self) -> int:
        return sum(value.status == MATERIALIZED_STATUS for value in self.records)

    @property
    def typed_materialization_failure_count(self) -> int:
        return sum(
            value.status == TYPED_MATERIALIZATION_FAILURE_STATUS
            for value in self.records
        )

    @property
    def upstream_not_materialized_count(self) -> int:
        return sum(
            value.status == UPSTREAM_NOT_MATERIALIZED_STATUS
            for value in self.records
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_mixed64_operational_proposal_policy(),
            "policy_sha256": MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256,
            "admission_batch_receipt_sha256": self.admission_batch.receipt_sha256,
            "admission_batch": self.admission_batch.to_dict(),
            "candidate_denominator": len(self.records),
            "materialized_count": self.materialized_count,
            "typed_materialization_failure_count": self.typed_materialization_failure_count,
            "upstream_not_materialized_count": self.upstream_not_materialized_count,
            "record_receipt_sha256s": [value.receipt_sha256 for value in self.records],
            "records": [value.to_dict() for value in self.records],
            "denominator_failure_complete": True,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "refinement_scoring_validity_executed": False,
            "molecular_execution_authorized": False,
            "reservation_allowed": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return _verify_sealed_receipt(
            self._canonical_projection_bytes,
            self._receipt_sha256,
            name="operational proposal batch",
        )

    def assert_live_integrity(self) -> str:
        try:
            self.admission_batch.assert_live_integrity()
            for record in self.records:
                record._assert_live_integrity(admission_already_verified=True)
            return _verify_live_sealed_projection(
                self._canonical_projection_bytes,
                self._receipt_sha256,
                self._projection(),
                name="operational proposal batch",
            )
        except Mixed64OperationalProposalV3Error:
            raise
        except GeometricAdmissionV3Error as exc:
            raise Mixed64OperationalProposalV3Error(
                SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
                "operational proposal batch live integrity failed",
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **_unseal_projection(self._canonical_projection_bytes),
            "receipt_sha256": self.receipt_sha256,
        }


def _materialize_record(
    admission_batch: GeometricAdmissionBatchV3,
    decision: GeometricAdmissionDecisionV3,
) -> Mixed64OperationalProposalRecordV1:
    if decision.status != ACCEPTED_STATUS:
        return Mixed64OperationalProposalRecordV1(
            admission_decision=decision,
            source_payload=None,
            source_operational_proposal=None,
            operational_proposal=None,
            status=UPSTREAM_NOT_MATERIALIZED_STATUS,
            failure_code=None,
            _factory_seal=_RECORD_FACTORY_SEAL,
        )
    producer = decision.producer_record
    source: Mixed64CoordinateSourcePayloadV1 | None = None
    source_proposal: DockingProposal | None = None
    try:
        if (
            producer.status != GENERATION_STATUS_SUCCESS
            or producer.output_coordinates is None
            or producer.source_proposal_sha256 is None
            or producer.source_coordinate_sha256 is None
        ):
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "accepted producer record is incomplete")
        source = _source_for_slot(admission_batch, slot_index=decision.slot_index)
        placement = producer.placement_receipt
        if type(placement) is ExactPassthroughPlacementReceiptV1:
            placement_source_matches = (
                placement.source_payload.receipt_sha256 == source.receipt_sha256
            )
        elif type(placement) in {
            IndexedSO3PlacementReceiptV1,
            SingleAnchorPlacementReceiptV1,
        }:
            placement_source_matches = bool(
                placement.source_proposal_sha256 == source.proposal_sha256
                and placement.source_coordinate_sha256 == source.coordinate_sha256
            )
        else:
            placement_source_matches = False
        if not placement_source_matches:
            _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "placement source is cross-wired")
        source_proposal = _parse_source_proposal(source)
        source_coordinates = _coordinates_tensor(source.coordinates)
        output = _coordinates_tensor(producer.output_coordinates)
        materialization_seed = _materialization_seed(
            source_receipt_sha256=source.receipt_sha256,
            slot_index=decision.slot_index,
        )
        if type(placement) is ExactPassthroughPlacementReceiptV1:
            if source_proposal.fingerprint_sha256 != producer.source_proposal_sha256:
                _fail(SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED, "passthrough operational identity changed")
            if not torch.equal(source_coordinates, output):
                _fail(
                    SOURCE_OPERATIONAL_COORDINATE_CROSS_WIRED,
                    "passthrough operational coordinates changed",
                )
            operational = bind_docking_proposal_state(
                coordinates=output,
                torsion_angles=source_proposal.torsion_angles,
                rotation=source_proposal.rotation,
                translation=source_proposal.translation,
                proposal_index=decision.slot_index,
                seed=materialization_seed,
                problem_fingerprint_sha256=(
                    source_proposal.problem_fingerprint_sha256
                ),
                search_space_fingerprint_sha256=(
                    source_proposal.search_space_fingerprint_sha256
                ),
            )
        elif type(placement) in {
            IndexedSO3PlacementReceiptV1,
            SingleAnchorPlacementReceiptV1,
        }:
            placement_rotation = _rotation_matrix(placement.quaternion)
            placement_translation = torch.tensor(
                placement.translation,
                dtype=torch.float64,
            )
            expected = (
                source_coordinates @ placement_rotation.T
                + placement_translation
            )
            if not torch.equal(expected, output):
                maximum_error = float(torch.max(torch.abs(expected - output)).item())
                if maximum_error > 1.0e-12:
                    _fail(PLACEMENT_TRANSFORM_CROSS_WIRED, "placement transform does not reproduce output")
            composed_rotation = placement_rotation @ source_proposal.rotation
            composed_translation = (
                source_proposal.translation @ placement_rotation.T
                + placement_translation
            )
            operational = bind_docking_proposal_state(
                coordinates=output,
                torsion_angles=source_proposal.torsion_angles,
                rotation=composed_rotation,
                translation=composed_translation,
                proposal_index=decision.slot_index,
                seed=materialization_seed,
                problem_fingerprint_sha256=source_proposal.problem_fingerprint_sha256,
                search_space_fingerprint_sha256=(
                    source_proposal.search_space_fingerprint_sha256
                ),
            )
        else:
            _fail(UNSUPPORTED_PLACEMENT_RECEIPT, "placement receipt is not supported")
        return Mixed64OperationalProposalRecordV1(
            admission_decision=decision,
            source_payload=source,
            source_operational_proposal=source_proposal,
            operational_proposal=operational,
            status=MATERIALIZED_STATUS,
            failure_code=None,
            _factory_seal=_RECORD_FACTORY_SEAL,
        )
    except (DockingProposalError, Mixed64OperationalProposalV3Error) as exc:
        if isinstance(exc, Mixed64OperationalProposalV3Error):
            failure = exc
        else:
            failure = Mixed64OperationalProposalV3Error(
                SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
                "operational proposal construction failed",
            )
        return Mixed64OperationalProposalRecordV1(
            admission_decision=decision,
            source_payload=source,
            source_operational_proposal=source_proposal,
            operational_proposal=None,
            status=TYPED_MATERIALIZATION_FAILURE_STATUS,
            failure_code=failure.code,
            _factory_seal=_RECORD_FACTORY_SEAL,
        )


def materialize_mixed64_operational_proposals(
    admission_batch: GeometricAdmissionBatchV3,
) -> Mixed64OperationalProposalBatchV1:
    """Materialize all admitted slots without accepting caller proposal state."""

    if type(admission_batch) is not GeometricAdmissionBatchV3:
        raise TypeError("admission_batch must be exact GeometricAdmissionBatchV3")
    try:
        admission_batch.assert_live_integrity()
    except GeometricAdmissionV3Error as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
            "admission batch live integrity preflight failed",
        ) from exc
    decisions = tuple(admission_batch.decisions)
    records = tuple(
        _materialize_record(admission_batch, decision)
        for decision in decisions
    )
    try:
        admission_batch.assert_live_integrity()
    except GeometricAdmissionV3Error as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
            "admission batch live integrity postflight failed",
        ) from exc
    if any(
        current is not captured
        for current, captured in zip(
            admission_batch.decisions,
            decisions,
            strict=True,
        )
    ):
        _fail(
            SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
            "admission decision identities changed during materialization",
        )
    batch = Mixed64OperationalProposalBatchV1(
        admission_batch=admission_batch,
        records=records,
        _factory_seal=_BATCH_FACTORY_SEAL,
    )
    try:
        batch.assert_live_integrity()
    except Mixed64OperationalProposalV3Error as exc:
        raise Mixed64OperationalProposalV3Error(
            SOURCE_OPERATIONAL_PROPOSAL_CROSS_WIRED,
            "operational batch live integrity finalization failed",
        ) from exc
    return batch


__all__ = [
    "DOCKING_PROPOSAL_IDENTITY_SCHEMA_ID",
    "MATERIALIZED_STATUS",
    "MIXED64_OPERATIONAL_PROPOSAL_COMPONENT_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_POLICY_SHA256",
    "MIXED64_OPERATIONAL_PROPOSAL_POLICY_SCHEMA_ID",
    "MIXED64_OPERATIONAL_PROPOSAL_PROFILE_ID",
    "Mixed64OperationalProposalBatchV1",
    "Mixed64OperationalProposalRecordV1",
    "Mixed64OperationalProposalV3Error",
    "SOURCE_PROPOSAL_IDENTITY_NOT_OPERATIONAL",
    "TYPED_MATERIALIZATION_FAILURE_STATUS",
    "UPSTREAM_NOT_MATERIALIZED_STATUS",
    "frozen_mixed64_operational_proposal_policy",
    "materialize_mixed64_operational_proposals",
]
