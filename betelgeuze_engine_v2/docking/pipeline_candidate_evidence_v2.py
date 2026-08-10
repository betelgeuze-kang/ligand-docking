"""Execution-neutral, failure-complete candidate evidence for mixed64.

The builder consumes exact typed allocation, geometric, scoring, validity, and
refinement records.  It never calls a proposal generator, scorer, refiner, or
validity evaluator.  Allocation and geometric failures remain in the exact
64-slot denominator and cannot fabricate downstream evidence.  Ranking and all
completion/eligibility/Top-K booleans are rederived from bound receipts.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
import re
from typing import Final, Mapping

from betelgeuze_engine_v2.docking.geometric_admission_v2 import (
    GeometricAdmissionBatchV2,
    GeometricAdmissionDecisionV2,
    MAX_BATCH_EXACT_PAIR_EVALUATIONS,
)
from betelgeuze_engine_v2.docking.mixed64_allocation import (
    FIXED_MIXED64_CANDIDATE_COUNT,
    GENERATION_PARENT_EXACT_PASSTHROUGH,
    GENERATION_PARENT_GENERATOR_INPUT,
    FixedMixed64Allocation,
    FixedMixed64Slot,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.docking.validity import PoseValidityResult


POSE_VALIDITY_RECEIPT_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_pose_validity_receipt_v2/1.0.0"
)
PROPOSAL_EXECUTION_RECEIPT_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_execution_receipt_v2/1.0.0"
)
REFINEMENT_RECEIPT_BINDING_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_refinement_receipt_binding_v2/1.0.0"
)
REFINEMENT_SOURCE_RECEIPT_IDENTITY_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_refinement_source_receipt_identity_v2/1.0.0"
)
SCORER_V1_EVIDENCE_BINDING_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_scorer_v1_evidence_binding_v2/1.0.0"
)
PIPELINE_CANDIDATE_EVIDENCE_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_v2/1.0.0"
)
PIPELINE_CANDIDATE_EVIDENCE_BATCH_V2_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_batch_v2/1.0.0"
)
PIPELINE_CANDIDATE_EVIDENCE_V2_BUILDER_ID: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_v2_builder/1.0.0"
)
ALLOCATION_FAILURE_STATUS: Final = "allocation_typed_failure"
GEOMETRIC_REJECTION_STATUS: Final = "geometric_rejection"
EXECUTION_FAILURE_STATUS: Final = "typed_execution_failure"
SCORED_SUCCESS_STATUS: Final = "scored_success"
TOP_K_LIMIT: Final = 5
DENOMINATOR_FAILURE_COMPLETENESS_SCOPE: Final = (
    "allocation_and_supported_post_proposal_structural_stages_only"
)
ACTIVATION_EVIDENCE_BLOCKERS: Final = (
    "uniform_source_control_lineage_not_rederived",
    "independent_so3_base_source_not_bound",
    "independent_so3_orientation_receipt_not_implemented",
    "single_anchor_placement_receipt_not_implemented",
    "proposal_generation_failure_receipt_not_implemented",
    "post_refinement_geometric_admission_not_implemented",
    "source_parent_payload_rederivation_not_implemented",
    "producer_attestation_not_implemented",
    "score_term_reexecution_not_implemented",
    "pose_validity_reexecution_not_implemented",
)
EXECUTION_FAILURE_STAGE_REFINEMENT: Final = "refinement"
EXECUTION_FAILURE_STAGE_SCORING: Final = "scoring"
EXECUTION_FAILURE_STAGE_VALIDITY: Final = "validity"
EXECUTION_FAILURE_STAGES: Final = (
    EXECUTION_FAILURE_STAGE_REFINEMENT,
    EXECUTION_FAILURE_STAGE_SCORING,
    EXECUTION_FAILURE_STAGE_VALIDITY,
)
REQUIRED_POSE_VALIDITY_CHECKS: Final = frozenset(
    {
        "proper_rotation",
        "bond_lengths_preserved",
        "ligand_self_clash_free",
        "receptor_ligand_clash_free",
        "declared_chirality_preserved",
        "inside_declared_pocket",
        "element_vdw_ligand_overlap_free",
        "element_vdw_receptor_overlap_free",
    }
)
ALLOWED_REFINEMENT_SOURCE_SCHEMA_IDS: Final = frozenset(
    {
        "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0",
        "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0",
        "betelgeuze.engine_v2_interaction_aware_torsion_clearance_receipt/8.0.0",
    }
)
_MAX_JSON_DEPTH: Final = 64
_MAX_JSON_NODES: Final = 250_000
_MAX_JSON_SEQUENCE_ITEMS: Final = 100_000
_MAX_JSON_MAPPING_ITEMS: Final = 20_000
_MAX_JSON_STRING_BYTES: Final = 4 * 1024 * 1024
_MAX_JSON_KEY_BYTES: Final = 256
_MAX_CANONICAL_RECEIPT_BYTES: Final = 32 * 1024 * 1024
_MAX_ABSOLUTE_JSON_INTEGER: Final = (1 << 53) - 1
_MAX_POSE_VALIDITY_MEASUREMENTS: Final = 256
_MAX_POSE_VALIDITY_BLOCKERS: Final = 256
_MAX_ABSOLUTE_POSE_VALIDITY_MEASUREMENT: Final = 1.0e15
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY_LIKE_KEY_TOKENS: Final = frozenset(
    {
        "admissible",
        "admission",
        "admitted",
        "allowed",
        "approved",
        "attested",
        "authority",
        "authorization",
        "authorized",
        "calibrated",
        "certified",
        "claim",
        "claimable",
        "eligible",
        "eligibility",
        "execution",
        "fresh",
        "granted",
        "molecular",
        "official",
        "production",
        "promotion",
        "promotable",
        "public",
        "permitted",
        "scientific",
        "stage0",
        "validated",
    }
)
_CANDIDATE_FACTORY_SEAL = object()
_PROPOSAL_FACTORY_SEAL = object()
_VALIDITY_FACTORY_SEAL = object()
_REFINEMENT_FACTORY_SEAL = object()
_SCORER_FACTORY_SEAL = object()


class PipelineCandidateEvidenceV2Error(ValueError):
    """Raised when shared candidate evidence fails closed."""


def _utf8_length(value: str, *, path: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise PipelineCandidateEvidenceV2Error(
            f"{path} contains a non-Unicode-scalar string"
        ) from exc


def _normalize_json(value: object, *, path: str = "$") -> object:
    state = {"nodes": 0, "active": set()}

    def visit(item: object, *, item_path: str, depth: int) -> object:
        state["nodes"] = int(state["nodes"]) + 1
        if depth > _MAX_JSON_DEPTH or int(state["nodes"]) > _MAX_JSON_NODES:
            raise PipelineCandidateEvidenceV2Error(
                f"{item_path} exceeds bounded JSON depth or node capacity"
            )
        active = state["active"]
        assert isinstance(active, set)
        if isinstance(item, Mapping):
            if len(item) > _MAX_JSON_MAPPING_ITEMS:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} exceeds mapping item capacity"
                )
            identity = id(item)
            if identity in active:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} contains a JSON reference cycle"
                )
            active.add(identity)
            try:
                normalized: dict[str, object] = {}
                for key, nested in item.items():
                    if type(key) is not str or not key or key != key.strip():
                        raise PipelineCandidateEvidenceV2Error(
                            f"{item_path} contains a non-canonical mapping key"
                        )
                    if _utf8_length(key, path=item_path) > _MAX_JSON_KEY_BYTES:
                        raise PipelineCandidateEvidenceV2Error(
                            f"{item_path} contains an oversized mapping key"
                        )
                    if key in normalized:
                        raise PipelineCandidateEvidenceV2Error(
                            f"{item_path} contains a duplicate mapping key"
                        )
                    normalized[key] = visit(
                        nested,
                        item_path=f"{item_path}.{key}",
                        depth=depth + 1,
                    )
                return MappingProxyType(normalized)
            finally:
                active.remove(identity)
        if isinstance(item, (list, tuple)):
            if len(item) > _MAX_JSON_SEQUENCE_ITEMS:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} exceeds sequence item capacity"
                )
            identity = id(item)
            if identity in active:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} contains a JSON reference cycle"
                )
            active.add(identity)
            try:
                return tuple(
                    visit(
                        nested,
                        item_path=f"{item_path}[{index}]",
                        depth=depth + 1,
                    )
                    for index, nested in enumerate(item)
                )
            finally:
                active.remove(identity)
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            if abs(item) > _MAX_ABSOLUTE_JSON_INTEGER:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} exceeds the exact JSON integer envelope"
                )
            return item
        if type(item) is str:
            if _utf8_length(item, path=item_path) > _MAX_JSON_STRING_BYTES:
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} contains an oversized string"
                )
            return item
        if type(item) is float:
            if not math.isfinite(item):
                raise PipelineCandidateEvidenceV2Error(
                    f"{item_path} contains a non-finite float"
                )
            return item
        raise PipelineCandidateEvidenceV2Error(
            f"{item_path} contains a non-canonical JSON value"
        )

    return visit(value, item_path=path, depth=0)


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    encoded = json.dumps(
        _thaw_json(_normalize_json(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) > _MAX_CANONICAL_RECEIPT_BYTES:
        raise PipelineCandidateEvidenceV2Error(
            "canonical JSON receipt exceeds fixed byte capacity"
        )
    return encoded


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise PipelineCandidateEvidenceV2Error(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _optional_digest(value: object, *, name: str) -> str | None:
    if value is None:
        return None
    return _require_digest(value, name=name)


def _optional_failure_code(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or re.fullmatch(r"[a-z][a-z0-9_]{2,127}", value) is None:
        raise PipelineCandidateEvidenceV2Error(
            "execution failure code must be a bounded canonical identifier"
        )
    return value


def _optional_failure_stage(value: object) -> str | None:
    if value is None:
        return None
    if value not in EXECUTION_FAILURE_STAGES:
        raise PipelineCandidateEvidenceV2Error(
            "execution failure stage is not in the frozen stage enum"
        )
    return str(value)


def _reject_nested_source_authority(value: object, *, path: str) -> None:
    exact_names = {
        "calibrated",
        "claim_safe",
        "producer_attested",
        "scientifically_validated",
        "stage0_admission_authority",
        "profile_promotion_authority",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            authority_like_true = nested is True and bool(
                _AUTHORITY_LIKE_KEY_TOKENS.intersection(key.split("_"))
            )
            if (
                key in exact_names
                or key.endswith("_authorized")
                or key.endswith("_claim_authorized")
                or key.endswith("_authority")
                or key.endswith("_eligible")
                or key.endswith("_admissible")
                or authority_like_true
            ) and nested is not False:
                raise PipelineCandidateEvidenceV2Error(
                    f"{path}.{key} cannot grant nested authority or eligibility"
                )
            _reject_nested_source_authority(nested, path=f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, nested in enumerate(value):
            _reject_nested_source_authority(
                nested,
                path=f"{path}[{index}]",
            )


@dataclass(frozen=True, slots=True)
class ProposalExecutionReceiptV2:
    slot_index: int
    allocation_slot_receipt_sha256: str
    allocation_source_receipt_sha256s: tuple[str, ...]
    generation_parent_proposal_sha256: str | None
    generation_parent_coordinate_sha256: str | None
    source_proposal_sha256: str
    source_coordinate_sha256: str
    generation_input_receipt_sha256: str
    generator_config_sha256: str
    generator_implementation_source_sha256: str
    generator_component_id: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = PROPOSAL_EXECUTION_RECEIPT_V2_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _PROPOSAL_FACTORY_SEAL:
            raise PipelineCandidateEvidenceV2Error(
                "proposal execution receipt must use the bounded binding factory"
            )
        if self.schema_id != PROPOSAL_EXECUTION_RECEIPT_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "proposal execution receipt schema is invalid"
            )
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            raise PipelineCandidateEvidenceV2Error(
                "proposal execution slot index is invalid"
            )
        for name in (
            "allocation_slot_receipt_sha256",
            "source_proposal_sha256",
            "source_coordinate_sha256",
            "generation_input_receipt_sha256",
            "generator_config_sha256",
            "generator_implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=f"proposal {name}"),
            )
        for name in (
            "generation_parent_proposal_sha256",
            "generation_parent_coordinate_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _optional_digest(getattr(self, name), name=f"proposal {name}"),
            )
        if (self.generation_parent_proposal_sha256 is None) is not (
            self.generation_parent_coordinate_sha256 is None
        ):
            raise PipelineCandidateEvidenceV2Error(
                "proposal generation parent identities must be paired"
            )
        if type(self.allocation_source_receipt_sha256s) is not tuple:
            raise TypeError("proposal allocation source receipts must be a tuple")
        source_receipts = tuple(
            _require_digest(value, name=f"proposal allocation source receipt {index}")
            for index, value in enumerate(self.allocation_source_receipt_sha256s)
        )
        if len(set(source_receipts)) != len(source_receipts):
            raise PipelineCandidateEvidenceV2Error(
                "proposal allocation source receipts contain duplicates"
            )
        if (
            type(self.generator_component_id) is not str
            or not self.generator_component_id
            or self.generator_component_id != self.generator_component_id.strip()
        ):
            raise PipelineCandidateEvidenceV2Error(
                "proposal generator component identity is invalid"
            )
        object.__setattr__(
            self,
            "allocation_source_receipt_sha256s",
            source_receipts,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "slot_index": self.slot_index,
            "allocation_slot_receipt_sha256": (self.allocation_slot_receipt_sha256),
            "allocation_source_receipt_sha256s": list(
                self.allocation_source_receipt_sha256s
            ),
            "generation_parent_proposal_sha256": (
                self.generation_parent_proposal_sha256
            ),
            "generation_parent_coordinate_sha256": (
                self.generation_parent_coordinate_sha256
            ),
            "source_proposal_sha256": self.source_proposal_sha256,
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "generation_input_receipt_sha256": (self.generation_input_receipt_sha256),
            "generator_config_sha256": self.generator_config_sha256,
            "generator_implementation_source_sha256": (
                self.generator_implementation_source_sha256
            ),
            "generator_component_id": self.generator_component_id,
            "structurally_complete": True,
            "producer_attested": False,
            "result_fields_consumed": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error("proposal execution receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def bind_proposal_execution_receipt_v2(
    *,
    slot_index: int,
    allocation_slot_receipt_sha256: str,
    allocation_source_receipt_sha256s: tuple[str, ...],
    generation_parent_proposal_sha256: str | None,
    generation_parent_coordinate_sha256: str | None,
    source_proposal_sha256: str,
    source_coordinate_sha256: str,
    generation_input_receipt_sha256: str,
    generator_config_sha256: str,
    generator_implementation_source_sha256: str,
    generator_component_id: str,
) -> ProposalExecutionReceiptV2:
    return ProposalExecutionReceiptV2(
        slot_index=slot_index,
        allocation_slot_receipt_sha256=allocation_slot_receipt_sha256,
        allocation_source_receipt_sha256s=allocation_source_receipt_sha256s,
        generation_parent_proposal_sha256=generation_parent_proposal_sha256,
        generation_parent_coordinate_sha256=generation_parent_coordinate_sha256,
        source_proposal_sha256=source_proposal_sha256,
        source_coordinate_sha256=source_coordinate_sha256,
        generation_input_receipt_sha256=generation_input_receipt_sha256,
        generator_config_sha256=generator_config_sha256,
        generator_implementation_source_sha256=(generator_implementation_source_sha256),
        generator_component_id=generator_component_id,
        _factory_seal=_PROPOSAL_FACTORY_SEAL,
    )


def _verify_proposal_generation_parent_binding(
    *,
    allocation_slot: FixedMixed64Slot,
    proposal_receipt: ProposalExecutionReceiptV2,
    source_proposal_sha256: str,
    source_coordinate_sha256: str,
) -> None:
    expected_parent = (
        allocation_slot.selected_generation_parent_proposal_sha256,
        allocation_slot.selected_generation_parent_coordinate_sha256,
    )
    observed_parent = (
        proposal_receipt.generation_parent_proposal_sha256,
        proposal_receipt.generation_parent_coordinate_sha256,
    )
    if observed_parent != expected_parent:
        raise PipelineCandidateEvidenceV2Error(
            "proposal generation parent identity is cross-wired"
        )
    if allocation_slot.generation_parent_role == GENERATION_PARENT_EXACT_PASSTHROUGH:
        if (source_proposal_sha256, source_coordinate_sha256) != expected_parent:
            raise PipelineCandidateEvidenceV2Error(
                "exact-passthrough control changed its generation parent"
            )
    elif allocation_slot.generation_parent_role == GENERATION_PARENT_GENERATOR_INPUT:
        if (
            source_proposal_sha256 == expected_parent[0]
            or source_coordinate_sha256 == expected_parent[1]
        ):
            raise PipelineCandidateEvidenceV2Error(
                "true-conformer generator output did not preserve transformed semantics"
            )


@dataclass(frozen=True, slots=True)
class PoseValidityReceiptV2:
    result_proposal_sha256: str
    coordinate_sha256: str
    validity_context_fingerprint_sha256: str
    validity_config_fingerprint_sha256: str
    evaluator_implementation_source_sha256: str
    result: PoseValidityResult = field(repr=False, compare=False)
    _factory_seal: InitVar[object | None] = None
    schema_id: str = POSE_VALIDITY_RECEIPT_V2_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _VALIDITY_FACTORY_SEAL:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity receipt must use the bounded binding factory"
            )
        if self.schema_id != POSE_VALIDITY_RECEIPT_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity receipt schema is invalid"
            )
        result_sha256 = _require_digest(
            self.result_proposal_sha256,
            name="pose validity result_proposal_sha256",
        )
        coordinate_sha256 = _require_digest(
            self.coordinate_sha256,
            name="pose validity coordinate_sha256",
        )
        context_sha256 = _require_digest(
            self.validity_context_fingerprint_sha256,
            name="pose validity context fingerprint",
        )
        config_sha256 = _require_digest(
            self.validity_config_fingerprint_sha256,
            name="pose validity config fingerprint",
        )
        evaluator_source_sha256 = _require_digest(
            self.evaluator_implementation_source_sha256,
            name="pose validity evaluator implementation source",
        )
        if type(self.result) is not PoseValidityResult:
            raise TypeError("result must be the exact PoseValidityResult type")
        if type(self.result.complete) is not bool or self.result.complete is not True:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity receipt must be complete"
            )
        if type(self.result.valid_within_evaluated_scope) is not bool:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity scope result must be an exact boolean"
            )
        checks = dict(self.result.checks)
        evaluated = dict(self.result.evaluated_checks)
        if (
            set(checks) != REQUIRED_POSE_VALIDITY_CHECKS
            or set(evaluated) != REQUIRED_POSE_VALIDITY_CHECKS
        ):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity receipt does not contain the exact required checks"
            )
        if any(type(value) is not bool for value in checks.values()):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity check values must be exact booleans"
            )
        if any(value is not True for value in evaluated.values()):
            raise PipelineCandidateEvidenceV2Error(
                "complete pose validity cannot contain unevaluated checks"
            )
        if self.result.not_evaluated_reasons:
            raise PipelineCandidateEvidenceV2Error(
                "complete pose validity cannot contain not-evaluated reasons"
            )
        if len(self.result.measurements) > _MAX_POSE_VALIDITY_MEASUREMENTS:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity measurement capacity exceeded"
            )
        for value in self.result.measurements.values():
            if type(value) not in {int, float} or isinstance(value, bool):
                raise PipelineCandidateEvidenceV2Error(
                    "pose validity measurements must be bounded finite numeric values"
                )
            try:
                numeric_value = float(value)
            except (OverflowError, ValueError) as exc:
                raise PipelineCandidateEvidenceV2Error(
                    "pose validity measurements must be bounded finite numeric values"
                ) from exc
            if (
                not math.isfinite(numeric_value)
                or abs(numeric_value) > _MAX_ABSOLUTE_POSE_VALIDITY_MEASUREMENT
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "pose validity measurements must be bounded finite numeric values"
                )
        if len(self.result.blockers) > _MAX_POSE_VALIDITY_BLOCKERS:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity blocker capacity exceeded"
            )
        if any(
            type(key) is not str
            or not key
            or key != key.strip()
            or _utf8_length(key, path="pose validity measurement name")
            > _MAX_JSON_KEY_BYTES
            for key in self.result.measurements
        ):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity measurement names must be bounded canonical strings"
            )
        if any(
            type(value) is not str or not value or value != value.strip()
            for value in self.result.blockers
        ):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity blockers must be exact non-empty strings"
            )
        if len(set(self.result.blockers)) != len(self.result.blockers):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity blockers must be unique"
            )
        expected_scope_valid = all(checks.values())
        if self.result.valid_within_evaluated_scope is not expected_scope_valid:
            raise PipelineCandidateEvidenceV2Error(
                "pose validity scope boolean does not rederive from checks"
            )
        if self.result.valid is not bool(self.result.complete and expected_scope_valid):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity result boolean does not rederive"
            )
        if expected_scope_valid is bool(self.result.blockers):
            raise PipelineCandidateEvidenceV2Error(
                "pose validity blockers disagree with the exact check outcome"
            )
        object.__setattr__(self, "result_proposal_sha256", result_sha256)
        object.__setattr__(self, "coordinate_sha256", coordinate_sha256)
        object.__setattr__(
            self,
            "validity_context_fingerprint_sha256",
            context_sha256,
        )
        object.__setattr__(
            self,
            "validity_config_fingerprint_sha256",
            config_sha256,
        )
        object.__setattr__(
            self,
            "evaluator_implementation_source_sha256",
            evaluator_source_sha256,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def valid(self) -> bool:
        return self.result.valid

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "result_proposal_sha256": self.result_proposal_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "validity_context_fingerprint_sha256": (
                self.validity_context_fingerprint_sha256
            ),
            "validity_config_fingerprint_sha256": (
                self.validity_config_fingerprint_sha256
            ),
            "evaluator_implementation_source_sha256": (
                self.evaluator_implementation_source_sha256
            ),
            "pose_validity": self.result.to_dict(),
            "complete": True,
            "valid": self.valid,
            "structurally_complete": True,
            "producer_attested": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error("pose validity receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def bind_pose_validity_receipt_v2(
    *,
    result_proposal_sha256: str,
    coordinate_sha256: str,
    validity_context_fingerprint_sha256: str,
    validity_config_fingerprint_sha256: str,
    evaluator_implementation_source_sha256: str,
    result: PoseValidityResult,
) -> PoseValidityReceiptV2:
    """Structurally bind canonical validity output without granting attestation."""

    return PoseValidityReceiptV2(
        result_proposal_sha256=result_proposal_sha256,
        coordinate_sha256=coordinate_sha256,
        validity_context_fingerprint_sha256=validity_context_fingerprint_sha256,
        validity_config_fingerprint_sha256=validity_config_fingerprint_sha256,
        evaluator_implementation_source_sha256=(evaluator_implementation_source_sha256),
        result=result,
        _factory_seal=_VALIDITY_FACTORY_SEAL,
    )


@dataclass(frozen=True, slots=True)
class ScorerV1EvidenceBindingV2:
    terms: ScorerV1Terms = field(repr=False, compare=False)
    search_row_sha256: str
    search_term_row_receipt_sha256: str
    source_search_result_receipt_sha256: str
    scorer_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = SCORER_V1_EVIDENCE_BINDING_V2_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _SCORER_FACTORY_SEAL:
            raise PipelineCandidateEvidenceV2Error(
                "scorer evidence must use the bounded binding factory"
            )
        if self.schema_id != SCORER_V1_EVIDENCE_BINDING_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "scorer evidence binding schema is invalid"
            )
        if type(self.terms) is not ScorerV1Terms:
            raise TypeError("scorer evidence terms must be exact ScorerV1Terms")
        self.terms.receipt_sha256
        for name in (
            "receptor_candidate_pair_count",
            "ligand_pair_count",
            "hbond_count",
            "hydrophobic_contact_count",
            "buried_polar_count",
        ):
            value = getattr(self.terms, name)
            if (
                type(value) is not int
                or value < 0
                or value > MAX_BATCH_EXACT_PAIR_EVALUATIONS
            ):
                raise PipelineCandidateEvidenceV2Error(
                    f"scorer evidence {name} exceeds the exact count envelope"
                )
        for name in (
            "search_row_sha256",
            "search_term_row_receipt_sha256",
            "source_search_result_receipt_sha256",
            "scorer_implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_digest(getattr(self, name), name=f"scorer evidence {name}"),
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def result_proposal_sha256(self) -> str:
        return self.terms.proposal_fingerprint_sha256

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "result_proposal_sha256": self.result_proposal_sha256,
            "search_row_sha256": self.search_row_sha256,
            "search_term_row_receipt_sha256": (self.search_term_row_receipt_sha256),
            "source_search_result_receipt_sha256": (
                self.source_search_result_receipt_sha256
            ),
            "scorer_implementation_source_sha256": (
                self.scorer_implementation_source_sha256
            ),
            "scorer_v1_terms_receipt_sha256": self.terms.receipt_sha256,
            "scorer_v1_terms": self.terms.to_dict(),
            "structurally_complete": True,
            "producer_attested": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error("scorer evidence binding changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def bind_scorer_v1_evidence_v2(
    *,
    terms: ScorerV1Terms,
    search_row_sha256: str,
    search_term_row_receipt_sha256: str,
    source_search_result_receipt_sha256: str,
    scorer_implementation_source_sha256: str,
) -> ScorerV1EvidenceBindingV2:
    """Bind complete ScorerV1 terms to its structural search provenance."""

    return ScorerV1EvidenceBindingV2(
        terms=terms,
        search_row_sha256=search_row_sha256,
        search_term_row_receipt_sha256=search_term_row_receipt_sha256,
        source_search_result_receipt_sha256=source_search_result_receipt_sha256,
        scorer_implementation_source_sha256=scorer_implementation_source_sha256,
        _factory_seal=_SCORER_FACTORY_SEAL,
    )


@dataclass(frozen=True, slots=True)
class RefinementReceiptBindingV2:
    source_proposal_sha256: str
    result_proposal_sha256: str
    source_coordinate_sha256: str
    result_coordinate_sha256: str
    refiner_config_sha256: str
    refiner_implementation_source_sha256: str
    source_receipt: Mapping[str, object] = field(repr=False, compare=False)
    _factory_seal: InitVar[object | None] = None
    schema_id: str = REFINEMENT_RECEIPT_BINDING_V2_SCHEMA_ID
    _original_source_receipt_sha256: str = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _REFINEMENT_FACTORY_SEAL:
            raise PipelineCandidateEvidenceV2Error(
                "refinement receipt must use the bounded binding factory"
            )
        if self.schema_id != REFINEMENT_RECEIPT_BINDING_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "refinement receipt binding schema is invalid"
            )
        source_sha256 = _require_digest(
            self.source_proposal_sha256,
            name="refinement source_proposal_sha256",
        )
        result_sha256 = _require_digest(
            self.result_proposal_sha256,
            name="refinement result_proposal_sha256",
        )
        source_coordinate_sha256 = _require_digest(
            self.source_coordinate_sha256,
            name="refinement source_coordinate_sha256",
        )
        result_coordinate_sha256 = _require_digest(
            self.result_coordinate_sha256,
            name="refinement result_coordinate_sha256",
        )
        config_sha256 = _require_digest(
            self.refiner_config_sha256,
            name="refinement refiner_config_sha256",
        )
        implementation_source_sha256 = _require_digest(
            self.refiner_implementation_source_sha256,
            name="refinement implementation source SHA-256",
        )
        normalized = _normalize_json(self.source_receipt, path="$.source_receipt")
        if not isinstance(normalized, Mapping):
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt must be a canonical mapping"
            )
        _reject_nested_source_authority(normalized, path="$.source_receipt")
        document = _thaw_json(normalized)
        if not isinstance(document, dict):
            raise AssertionError("normalized refinement receipt is not a dict")
        embedded_receipt = document.pop("receipt_sha256", None)
        if (
            type(embedded_receipt) is not str
            or _SHA256_RE.fullmatch(embedded_receipt) is None
            or _sha256(document) != embedded_receipt
        ):
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt does not rederive"
            )
        required = {
            "schema_id",
            "source_proposal_sha256",
            "config_sha256",
            "pre_coordinates_sha256",
            "post_coordinates_sha256",
            "scientifically_validated",
        }
        if not required.issubset(document):
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt lacks required identity evidence"
            )
        if document["schema_id"] not in ALLOWED_REFINEMENT_SOURCE_SCHEMA_IDS:
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt schema is not canonical V7/V8"
            )
        if (
            document["source_proposal_sha256"] != source_sha256
            or document["config_sha256"] != config_sha256
            or document["pre_coordinates_sha256"] != source_coordinate_sha256
            or document["post_coordinates_sha256"] != result_coordinate_sha256
        ):
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt is cross-wired"
            )
        if document["scientifically_validated"] is not False:
            raise PipelineCandidateEvidenceV2Error(
                "refinement source receipt cannot self-grant scientific authority"
            )
        object.__setattr__(self, "source_proposal_sha256", source_sha256)
        object.__setattr__(self, "result_proposal_sha256", result_sha256)
        object.__setattr__(
            self,
            "source_coordinate_sha256",
            source_coordinate_sha256,
        )
        object.__setattr__(
            self,
            "result_coordinate_sha256",
            result_coordinate_sha256,
        )
        object.__setattr__(self, "refiner_config_sha256", config_sha256)
        object.__setattr__(
            self,
            "refiner_implementation_source_sha256",
            implementation_source_sha256,
        )
        source_identity_projection: dict[str, object] = {
            "schema_id": REFINEMENT_SOURCE_RECEIPT_IDENTITY_V2_SCHEMA_ID,
            "source_receipt_schema_id": document["schema_id"],
            "source_proposal_sha256": source_sha256,
            "config_sha256": config_sha256,
            "pre_coordinates_sha256": source_coordinate_sha256,
            "post_coordinates_sha256": result_coordinate_sha256,
            "original_source_receipt_sha256": embedded_receipt,
            "source_payload_embedded": False,
            "source_payload_rederived": False,
            "scientifically_validated": False,
            "producer_attested": False,
            "claim_safe": False,
        }
        source_identity_projection["receipt_sha256"] = _sha256(
            source_identity_projection
        )
        source_identity = _normalize_json(
            source_identity_projection,
            path="$.source_receipt_identity",
        )
        if not isinstance(source_identity, Mapping):
            raise AssertionError("refinement source identity is not a mapping")
        object.__setattr__(
            self,
            "_original_source_receipt_sha256",
            embedded_receipt,
        )
        object.__setattr__(self, "source_receipt", source_identity)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def source_receipt_sha256(self) -> str:
        return _require_digest(
            self._original_source_receipt_sha256,
            name="refinement source receipt SHA-256",
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "source_proposal_sha256": self.source_proposal_sha256,
            "result_proposal_sha256": self.result_proposal_sha256,
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "result_coordinate_sha256": self.result_coordinate_sha256,
            "refiner_config_sha256": self.refiner_config_sha256,
            "refiner_implementation_source_sha256": (
                self.refiner_implementation_source_sha256
            ),
            "source_receipt_sha256": self.source_receipt_sha256,
            "source_receipt": _thaw_json(self.source_receipt),
            "structurally_complete": True,
            "producer_attested": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error("refinement receipt binding changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def bind_refinement_receipt_v2(
    *,
    source_proposal_sha256: str,
    result_proposal_sha256: str,
    source_coordinate_sha256: str,
    result_coordinate_sha256: str,
    refiner_config_sha256: str,
    refiner_implementation_source_sha256: str,
    source_receipt: Mapping[str, object],
) -> RefinementReceiptBindingV2:
    """Bind an exact canonical V7/V8 receipt without claiming producer attestation."""

    return RefinementReceiptBindingV2(
        source_proposal_sha256=source_proposal_sha256,
        result_proposal_sha256=result_proposal_sha256,
        source_coordinate_sha256=source_coordinate_sha256,
        result_coordinate_sha256=result_coordinate_sha256,
        refiner_config_sha256=refiner_config_sha256,
        refiner_implementation_source_sha256=(refiner_implementation_source_sha256),
        source_receipt=source_receipt,
        _factory_seal=_REFINEMENT_FACTORY_SEAL,
    )


@dataclass(frozen=True, slots=True)
class PipelineCandidateRecordV2:
    """Exact typed evidence offered to the execution-neutral builder."""

    slot_index: int
    source_proposal_sha256: str | None = None
    result_proposal_sha256: str | None = None
    proposal_execution_receipt: ProposalExecutionReceiptV2 | None = None
    scorer_evidence: ScorerV1EvidenceBindingV2 | None = None
    pose_validity_receipt: PoseValidityReceiptV2 | None = None
    refinement_receipt: RefinementReceiptBindingV2 | None = None
    execution_failure_stage: str | None = None
    execution_failure_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            raise PipelineCandidateEvidenceV2Error(
                "candidate record slot index is invalid"
            )
        object.__setattr__(
            self,
            "source_proposal_sha256",
            _optional_digest(
                self.source_proposal_sha256,
                name="record source_proposal_sha256",
            ),
        )
        object.__setattr__(
            self,
            "result_proposal_sha256",
            _optional_digest(
                self.result_proposal_sha256,
                name="record result_proposal_sha256",
            ),
        )
        for name, value, expected_type in (
            (
                "proposal_execution_receipt",
                self.proposal_execution_receipt,
                ProposalExecutionReceiptV2,
            ),
            (
                "scorer_evidence",
                self.scorer_evidence,
                ScorerV1EvidenceBindingV2,
            ),
            (
                "pose_validity_receipt",
                self.pose_validity_receipt,
                PoseValidityReceiptV2,
            ),
            (
                "refinement_receipt",
                self.refinement_receipt,
                RefinementReceiptBindingV2,
            ),
        ):
            if value is not None and type(value) is not expected_type:
                raise TypeError(f"{name} must use its exact typed receipt")
        object.__setattr__(
            self,
            "execution_failure_code",
            _optional_failure_code(self.execution_failure_code),
        )
        object.__setattr__(
            self,
            "execution_failure_stage",
            _optional_failure_stage(self.execution_failure_stage),
        )
        if (self.execution_failure_stage is None) is not (
            self.execution_failure_code is None
        ):
            raise PipelineCandidateEvidenceV2Error(
                "execution failure stage and code must be present together"
            )


@dataclass(frozen=True, slots=True)
class PipelineCandidateEvidenceV2:
    allocation_receipt_sha256: str
    geometric_admission_batch_receipt_sha256: str
    allocation_slot: FixedMixed64Slot
    geometric_decision: GeometricAdmissionDecisionV2
    source_proposal_sha256: str | None
    result_proposal_sha256: str | None
    proposal_execution_receipt: ProposalExecutionReceiptV2 | None
    scorer_evidence: ScorerV1EvidenceBindingV2 | None
    pose_validity_receipt: PoseValidityReceiptV2 | None
    refinement_receipt: RefinementReceiptBindingV2 | None
    execution_failure_stage: str | None
    execution_failure_code: str | None
    stable_rank: int | None
    stable_valid_rank: int | None
    _factory_seal: InitVar[object | None] = None
    schema_id: str = PIPELINE_CANDIDATE_EVIDENCE_V2_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _CANDIDATE_FACTORY_SEAL:
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence must be created by the exact builder"
            )
        if self.schema_id != PIPELINE_CANDIDATE_EVIDENCE_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence schema is invalid"
            )
        allocation_sha256 = _require_digest(
            self.allocation_receipt_sha256,
            name="candidate allocation_receipt_sha256",
        )
        geometric_batch_sha256 = _require_digest(
            self.geometric_admission_batch_receipt_sha256,
            name="candidate geometric_admission_batch_receipt_sha256",
        )
        if type(self.allocation_slot) is not FixedMixed64Slot:
            raise TypeError("allocation_slot must be exact FixedMixed64Slot")
        slot_index = self.allocation_slot.slot_index
        if type(self.geometric_decision) is not GeometricAdmissionDecisionV2:
            raise TypeError(
                "geometric_decision must be exact GeometricAdmissionDecisionV2"
            )
        if (
            self.geometric_decision.slot_index != slot_index
            or self.geometric_decision.allocation_slot_receipt_sha256
            != self.allocation_slot.receipt_sha256
            or self.geometric_decision.lane != self.allocation_slot.lane
            or self.geometric_decision.allocation_generation_eligible
            is not self.allocation_slot.generation_eligible
            or self.geometric_decision.allocation_missing_feature_codes
            != self.allocation_slot.missing_feature_codes
        ):
            raise PipelineCandidateEvidenceV2Error(
                "candidate geometric decision is cross-wired"
            )
        source_sha256 = _optional_digest(
            self.source_proposal_sha256,
            name="candidate source_proposal_sha256",
        )
        result_sha256 = _optional_digest(
            self.result_proposal_sha256,
            name="candidate result_proposal_sha256",
        )
        failure_code = _optional_failure_code(self.execution_failure_code)
        failure_stage = _optional_failure_stage(self.execution_failure_stage)
        if (failure_stage is None) is not (failure_code is None):
            raise PipelineCandidateEvidenceV2Error(
                "candidate execution failure stage and code must be paired"
            )
        expected_failure_prefixes = {
            EXECUTION_FAILURE_STAGE_REFINEMENT: ("typed_refinement_",),
            EXECUTION_FAILURE_STAGE_SCORING: ("typed_scorer_", "typed_scoring_"),
            EXECUTION_FAILURE_STAGE_VALIDITY: ("typed_validity_",),
        }
        if failure_stage is not None and (
            failure_code is None
            or not failure_code.startswith(expected_failure_prefixes[failure_stage])
        ):
            raise PipelineCandidateEvidenceV2Error(
                "execution failure code does not match its frozen stage"
            )
        for name, value, expected_type in (
            (
                "proposal_execution_receipt",
                self.proposal_execution_receipt,
                ProposalExecutionReceiptV2,
            ),
            (
                "scorer_evidence",
                self.scorer_evidence,
                ScorerV1EvidenceBindingV2,
            ),
            (
                "pose_validity_receipt",
                self.pose_validity_receipt,
                PoseValidityReceiptV2,
            ),
            (
                "refinement_receipt",
                self.refinement_receipt,
                RefinementReceiptBindingV2,
            ),
        ):
            if value is not None and type(value) is not expected_type:
                raise TypeError(f"candidate {name} must use its exact type")

        downstream = (
            self.scorer_evidence,
            self.pose_validity_receipt,
            self.refinement_receipt,
        )
        proposal_receipt = self.proposal_execution_receipt
        if not self.allocation_slot.generation_eligible:
            if any(
                value is not None
                for value in (
                    source_sha256,
                    result_sha256,
                    proposal_receipt,
                    *downstream,
                    failure_stage,
                    failure_code,
                )
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "allocation failure cannot fabricate candidate evidence"
                )
        elif not self.geometric_decision.accepted:
            if (
                source_sha256 is None
                or result_sha256 is not None
                or proposal_receipt is None
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "geometric rejection requires source-only proposal receipt"
                )
            source_coordinate_sha256 = (
                self.geometric_decision.candidate_coordinate_sha256
            )
            if source_coordinate_sha256 is None:
                raise AssertionError("geometric rejection lacks source coordinates")
            proposal_receipt.receipt_sha256
            if (
                proposal_receipt.slot_index != slot_index
                or proposal_receipt.allocation_slot_receipt_sha256
                != self.allocation_slot.receipt_sha256
                or proposal_receipt.allocation_source_receipt_sha256s
                != self.allocation_slot.selected_source_receipt_sha256s
                or proposal_receipt.source_proposal_sha256 != source_sha256
                or proposal_receipt.source_coordinate_sha256 != source_coordinate_sha256
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "proposal execution receipt is cross-wired"
                )
            _verify_proposal_generation_parent_binding(
                allocation_slot=self.allocation_slot,
                proposal_receipt=proposal_receipt,
                source_proposal_sha256=source_sha256,
                source_coordinate_sha256=source_coordinate_sha256,
            )
            if any(
                value is not None
                for value in (*downstream, failure_stage, failure_code)
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "geometric rejection cannot fabricate downstream evidence"
                )
        else:
            if source_sha256 is None or proposal_receipt is None:
                raise PipelineCandidateEvidenceV2Error(
                    "geometrically admitted candidate lacks source proposal receipt"
                )
            source_coordinate_sha256 = (
                self.geometric_decision.candidate_coordinate_sha256
            )
            if source_coordinate_sha256 is None:
                raise AssertionError("admitted candidate lacks source coordinates")
            proposal_receipt.receipt_sha256
            if (
                proposal_receipt.slot_index != slot_index
                or proposal_receipt.allocation_slot_receipt_sha256
                != self.allocation_slot.receipt_sha256
                or proposal_receipt.allocation_source_receipt_sha256s
                != self.allocation_slot.selected_source_receipt_sha256s
                or proposal_receipt.source_proposal_sha256 != source_sha256
                or proposal_receipt.source_coordinate_sha256 != source_coordinate_sha256
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "proposal execution receipt is cross-wired"
                )
            _verify_proposal_generation_parent_binding(
                allocation_slot=self.allocation_slot,
                proposal_receipt=proposal_receipt,
                source_proposal_sha256=source_sha256,
                source_coordinate_sha256=source_coordinate_sha256,
            )
            refinement = self.refinement_receipt
            scorer = self.scorer_evidence
            validity = self.pose_validity_receipt
            if failure_stage == EXECUTION_FAILURE_STAGE_REFINEMENT:
                if result_sha256 is not None or any(
                    value is not None for value in downstream
                ):
                    raise PipelineCandidateEvidenceV2Error(
                        "refinement failure cannot fabricate result evidence"
                    )
            else:
                if result_sha256 is None or refinement is None:
                    raise PipelineCandidateEvidenceV2Error(
                        "post-refinement stages require result lineage and receipt"
                    )
                refinement.receipt_sha256
                if (
                    refinement.source_proposal_sha256 != source_sha256
                    or refinement.result_proposal_sha256 != result_sha256
                    or refinement.source_coordinate_sha256 != source_coordinate_sha256
                ):
                    raise PipelineCandidateEvidenceV2Error(
                        "refinement receipt binding is cross-wired"
                    )
            if failure_stage == EXECUTION_FAILURE_STAGE_SCORING:
                if scorer is not None or validity is not None:
                    raise PipelineCandidateEvidenceV2Error(
                        "scoring failure cannot fabricate scoring or validity evidence"
                    )
            elif failure_stage == EXECUTION_FAILURE_STAGE_VALIDITY:
                if scorer is None or validity is not None:
                    raise PipelineCandidateEvidenceV2Error(
                        "validity failure must preserve score and omit validity output"
                    )
            elif failure_stage is None:
                if scorer is None or validity is None:
                    raise PipelineCandidateEvidenceV2Error(
                        "completed candidate requires score and validity evidence"
                    )
            if scorer is not None:
                scorer.receipt_sha256
                if (
                    result_sha256 is None
                    or scorer.result_proposal_sha256 != result_sha256
                ):
                    raise PipelineCandidateEvidenceV2Error(
                        "ScorerV1 evidence result proposal identity is cross-wired"
                    )
                if not math.isfinite(scorer.terms.total_score):
                    raise PipelineCandidateEvidenceV2Error(
                        "ScorerV1Terms total score must be finite"
                    )
            if validity is not None:
                validity.receipt_sha256
                assert refinement is not None
                if (
                    validity.result_proposal_sha256 != result_sha256
                    or validity.coordinate_sha256 != refinement.result_coordinate_sha256
                ):
                    raise PipelineCandidateEvidenceV2Error(
                        "pose validity receipt is cross-wired"
                    )
            if failure_stage is not None and failure_code is None:
                raise PipelineCandidateEvidenceV2Error(
                    "typed execution failure lacks its failure code"
                )

        if self.rank_eligible:
            if type(self.stable_rank) is not int or self.stable_rank < 1:
                raise PipelineCandidateEvidenceV2Error(
                    "score-rank-eligible candidate lacks a stable rank"
                )
        elif self.stable_rank is not None:
            raise PipelineCandidateEvidenceV2Error(
                "score-rank-ineligible candidate cannot contain a stable rank"
            )
        if self.valid_rank_eligible:
            if type(self.stable_valid_rank) is not int or self.stable_valid_rank < 1:
                raise PipelineCandidateEvidenceV2Error(
                    "valid-rank-eligible candidate lacks a stable valid rank"
                )
        elif self.stable_valid_rank is not None:
            raise PipelineCandidateEvidenceV2Error(
                "valid-rank-ineligible candidate cannot contain a stable valid rank"
            )
        object.__setattr__(self, "allocation_receipt_sha256", allocation_sha256)
        object.__setattr__(
            self,
            "geometric_admission_batch_receipt_sha256",
            geometric_batch_sha256,
        )
        object.__setattr__(self, "source_proposal_sha256", source_sha256)
        object.__setattr__(self, "result_proposal_sha256", result_sha256)
        object.__setattr__(self, "execution_failure_stage", failure_stage)
        object.__setattr__(self, "execution_failure_code", failure_code)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def slot_index(self) -> int:
        return self.allocation_slot.slot_index

    @property
    def source_coordinate_sha256(self) -> str | None:
        return self.geometric_decision.candidate_coordinate_sha256

    @property
    def result_coordinate_sha256(self) -> str | None:
        return (
            None
            if self.refinement_receipt is None
            else self.refinement_receipt.result_coordinate_sha256
        )

    @property
    def coordinate_sha256(self) -> str | None:
        """Compatibility view: final coordinate when available, otherwise source."""

        return self.result_coordinate_sha256 or self.source_coordinate_sha256

    @property
    def scorer_terms(self) -> ScorerV1Terms | None:
        return None if self.scorer_evidence is None else self.scorer_evidence.terms

    @property
    def status(self) -> str:
        if not self.allocation_slot.generation_eligible:
            return ALLOCATION_FAILURE_STATUS
        if not self.geometric_decision.accepted:
            return GEOMETRIC_REJECTION_STATUS
        if self.execution_failure_code is not None:
            return EXECUTION_FAILURE_STATUS
        return SCORED_SUCCESS_STATUS

    @property
    def typed_failure_codes(self) -> tuple[str, ...]:
        if self.status == ALLOCATION_FAILURE_STATUS:
            return self.allocation_slot.missing_feature_codes
        if self.status == GEOMETRIC_REJECTION_STATUS:
            assert self.geometric_decision.rejection_code is not None
            return (self.geometric_decision.rejection_code,)
        if self.status == EXECUTION_FAILURE_STATUS:
            assert self.execution_failure_code is not None
            return (self.execution_failure_code,)
        return ()

    @property
    def score_binary64_hex(self) -> str | None:
        return (
            None if self.scorer_terms is None else self.scorer_terms.total_score.hex()
        )

    @property
    def evidence_complete(self) -> bool:
        return self.status == SCORED_SUCCESS_STATUS

    @property
    def score_evidence_complete(self) -> bool:
        return bool(
            self.allocation_slot.generation_eligible
            and self.geometric_decision.accepted
            and self.result_proposal_sha256 is not None
            and self.refinement_receipt is not None
            and self.scorer_evidence is not None
        )

    @property
    def rank_eligible(self) -> bool:
        """Whether complete score evidence participates in the primary rank."""

        return self.score_evidence_complete

    @property
    def valid_rank_eligible(self) -> bool:
        """Whether the candidate also participates in the valid-only view."""

        return self.rank_eligible and bool(
            self.pose_validity_receipt is not None and self.pose_validity_receipt.valid
        )

    @property
    def selection_eligible(self) -> bool:
        """Validity-filtered eligibility for downstream pose selection only."""

        return self.valid_rank_eligible

    @property
    def top1_member(self) -> bool:
        return self.stable_rank == 1

    @property
    def top5_member(self) -> bool:
        return self.stable_rank is not None and self.stable_rank <= TOP_K_LIMIT

    @property
    def valid_top1_member(self) -> bool:
        return self.stable_valid_rank == 1

    @property
    def valid_top5_member(self) -> bool:
        return (
            self.stable_valid_rank is not None and self.stable_valid_rank <= TOP_K_LIMIT
        )

    def _projection(self) -> dict[str, object]:
        decision = self.geometric_decision
        return {
            "schema_id": self.schema_id,
            "builder_id": PIPELINE_CANDIDATE_EVIDENCE_V2_BUILDER_ID,
            "slot_index": self.slot_index,
            "allocation_receipt_sha256": self.allocation_receipt_sha256,
            "geometric_admission_batch_receipt_sha256": (
                self.geometric_admission_batch_receipt_sha256
            ),
            "allocation_slot_receipt_sha256": (self.allocation_slot.receipt_sha256),
            "allocation_lane": self.allocation_slot.lane,
            "allocation_lane_offset": self.allocation_slot.lane_offset,
            "retained_source_index": self.allocation_slot.retained_source_index,
            "allocation_slot": self.allocation_slot.to_dict(),
            "source_proposal_sha256": self.source_proposal_sha256,
            "result_proposal_sha256": self.result_proposal_sha256,
            "proposal_execution_receipt_sha256": (
                None
                if self.proposal_execution_receipt is None
                else self.proposal_execution_receipt.receipt_sha256
            ),
            "proposal_execution_receipt": (
                None
                if self.proposal_execution_receipt is None
                else self.proposal_execution_receipt.to_dict()
            ),
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "result_coordinate_sha256": self.result_coordinate_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "geometric_admission_decision_receipt_sha256": (decision.receipt_sha256),
            "geometric_admission_metrics_receipt_sha256": (
                None if decision.metrics is None else decision.metrics.receipt_sha256
            ),
            "geometric_admission_decision": decision.to_dict(),
            "scorer_v1_evidence_binding_sha256": (
                None
                if self.scorer_evidence is None
                else self.scorer_evidence.receipt_sha256
            ),
            "scorer_v1_evidence": (
                None if self.scorer_evidence is None else self.scorer_evidence.to_dict()
            ),
            "pose_validity_receipt_sha256": (
                None
                if self.pose_validity_receipt is None
                else self.pose_validity_receipt.receipt_sha256
            ),
            "pose_validity_receipt": (
                None
                if self.pose_validity_receipt is None
                else self.pose_validity_receipt.to_dict()
            ),
            "refinement_receipt_binding_sha256": (
                None
                if self.refinement_receipt is None
                else self.refinement_receipt.receipt_sha256
            ),
            "refinement_receipt": (
                None
                if self.refinement_receipt is None
                else self.refinement_receipt.to_dict()
            ),
            "status": self.status,
            "execution_failure_stage": self.execution_failure_stage,
            "execution_failure_code": self.execution_failure_code,
            "typed_failure_codes": list(self.typed_failure_codes),
            "score_binary64_hex": self.score_binary64_hex,
            "evidence_complete": self.evidence_complete,
            "score_evidence_complete": self.score_evidence_complete,
            "rank_eligible": self.rank_eligible,
            "score_rank_includes_pose_invalid_candidates": True,
            "valid_rank_eligible": self.valid_rank_eligible,
            "selection_eligible": self.selection_eligible,
            "stable_rank": self.stable_rank,
            "top1_member": self.top1_member,
            "top5_member": self.top5_member,
            "stable_valid_rank": self.stable_valid_rank,
            "valid_top1_member": self.valid_top1_member,
            "valid_top5_member": self.valid_top5_member,
            "denominator_slot_preserved": True,
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_mutation_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error(
                "pipeline candidate evidence changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class PipelineCandidateEvidenceBatchV2:
    allocation: FixedMixed64Allocation = field(repr=False, compare=False)
    geometric_admission_batch: GeometricAdmissionBatchV2 = field(
        repr=False,
        compare=False,
    )
    candidates: tuple[PipelineCandidateEvidenceV2, ...]
    schema_id: str = PIPELINE_CANDIDATE_EVIDENCE_BATCH_V2_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != PIPELINE_CANDIDATE_EVIDENCE_BATCH_V2_SCHEMA_ID:
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence batch schema is invalid"
            )
        if type(self.allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be exact FixedMixed64Allocation")
        if type(self.geometric_admission_batch) is not GeometricAdmissionBatchV2:
            raise TypeError(
                "geometric_admission_batch must be exact GeometricAdmissionBatchV2"
            )
        if type(self.candidates) is not tuple or any(
            type(candidate) is not PipelineCandidateEvidenceV2
            for candidate in self.candidates
        ):
            raise TypeError(
                "candidates must contain exact PipelineCandidateEvidenceV2 values"
            )
        if len(self.candidates) != FIXED_MIXED64_CANDIDATE_COUNT:
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence denominator is not fixed64"
            )
        if tuple(candidate.slot_index for candidate in self.candidates) != tuple(
            range(FIXED_MIXED64_CANDIDATE_COUNT)
        ):
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence slots are not index-stable"
            )
        allocation_sha256 = self.allocation.receipt_sha256
        geometric_batch_sha256 = self.geometric_admission_batch.receipt_sha256
        if (
            self.geometric_admission_batch.allocation.receipt_sha256
            != allocation_sha256
        ):
            raise PipelineCandidateEvidenceV2Error(
                "geometric admission batch allocation receipt is cross-wired"
            )
        for slot, decision, candidate in zip(
            self.allocation.slots,
            self.geometric_admission_batch.decisions,
            self.candidates,
            strict=True,
        ):
            if (
                candidate.allocation_receipt_sha256 != allocation_sha256
                or candidate.allocation_slot.receipt_sha256 != slot.receipt_sha256
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "candidate allocation evidence is cross-wired"
                )
            if (
                candidate.geometric_admission_batch_receipt_sha256
                != geometric_batch_sha256
                or candidate.geometric_decision.receipt_sha256
                != decision.receipt_sha256
            ):
                raise PipelineCandidateEvidenceV2Error(
                    "candidate geometric admission batch evidence is cross-wired"
                )
        score_eligible = tuple(
            sorted(
                (candidate for candidate in self.candidates if candidate.rank_eligible),
                key=lambda candidate: (
                    float.fromhex(str(candidate.score_binary64_hex)),
                    candidate.slot_index,
                    str(candidate.result_proposal_sha256),
                ),
            )
        )
        if tuple(candidate.stable_rank for candidate in score_eligible) != tuple(
            range(1, len(score_eligible) + 1)
        ):
            raise PipelineCandidateEvidenceV2Error(
                "candidate primary score ranking does not rederive"
            )
        if any(
            candidate.stable_rank is not None
            for candidate in self.candidates
            if not candidate.rank_eligible
        ):
            raise PipelineCandidateEvidenceV2Error(
                "rank-ineligible candidate contains a stable rank"
            )
        valid_eligible = tuple(
            candidate for candidate in score_eligible if candidate.valid_rank_eligible
        )
        if tuple(candidate.stable_valid_rank for candidate in valid_eligible) != tuple(
            range(1, len(valid_eligible) + 1)
        ):
            raise PipelineCandidateEvidenceV2Error(
                "candidate valid-only ranking does not rederive"
            )
        if any(
            candidate.stable_valid_rank is not None
            for candidate in self.candidates
            if not candidate.valid_rank_eligible
        ):
            raise PipelineCandidateEvidenceV2Error(
                "valid-rank-ineligible candidate contains a stable valid rank"
            )
        scored = tuple(
            candidate
            for candidate in self.candidates
            if candidate.score_evidence_complete
        )
        generated = tuple(
            candidate
            for candidate in self.candidates
            if candidate.proposal_execution_receipt is not None
        )
        refined = tuple(
            candidate
            for candidate in self.candidates
            if candidate.refinement_receipt is not None
        )
        if len({candidate.source_proposal_sha256 for candidate in generated}) != len(
            generated
        ):
            raise PipelineCandidateEvidenceV2Error(
                "generated source proposal identities are not slot-unique"
            )
        if len({candidate.result_proposal_sha256 for candidate in scored}) != len(
            scored
        ):
            raise PipelineCandidateEvidenceV2Error(
                "scored result proposal identities are not unique"
            )
        for field_name in (
            "authority_input_receipt_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "backend_receipt_sha256",
        ):
            values = {
                getattr(candidate.scorer_terms, field_name)
                for candidate in scored
                if candidate.scorer_terms is not None
            }
            if len(values) > 1:
                raise PipelineCandidateEvidenceV2Error(
                    f"ScorerV1Terms {field_name} is cross-wired across the batch"
                )
        for identity_name, identities in (
            (
                "scorer search row",
                {
                    candidate.scorer_evidence.search_row_sha256
                    for candidate in scored
                    if candidate.scorer_evidence is not None
                },
            ),
            (
                "scorer term row",
                {
                    candidate.scorer_evidence.search_term_row_receipt_sha256
                    for candidate in scored
                    if candidate.scorer_evidence is not None
                },
            ),
        ):
            if len(identities) != len(scored):
                raise PipelineCandidateEvidenceV2Error(
                    f"{identity_name} identities are not slot-unique"
                )
        for evidence_name, evidence_values in (
            (
                "proposal generation input",
                {
                    candidate.proposal_execution_receipt.generation_input_receipt_sha256
                    for candidate in self.candidates
                    if candidate.proposal_execution_receipt is not None
                },
            ),
            (
                "proposal generator config",
                {
                    candidate.proposal_execution_receipt.generator_config_sha256
                    for candidate in self.candidates
                    if candidate.proposal_execution_receipt is not None
                },
            ),
            (
                "proposal generator implementation",
                {
                    candidate.proposal_execution_receipt.generator_implementation_source_sha256
                    for candidate in self.candidates
                    if candidate.proposal_execution_receipt is not None
                },
            ),
            (
                "proposal generator component",
                {
                    candidate.proposal_execution_receipt.generator_component_id
                    for candidate in generated
                    if candidate.proposal_execution_receipt is not None
                },
            ),
            (
                "refiner config",
                {
                    candidate.refinement_receipt.refiner_config_sha256
                    for candidate in refined
                    if candidate.refinement_receipt is not None
                },
            ),
            (
                "refiner implementation",
                {
                    candidate.refinement_receipt.refiner_implementation_source_sha256
                    for candidate in refined
                    if candidate.refinement_receipt is not None
                },
            ),
            (
                "refinement source schema",
                {
                    candidate.refinement_receipt.source_receipt[
                        "source_receipt_schema_id"
                    ]
                    for candidate in refined
                    if candidate.refinement_receipt is not None
                },
            ),
            (
                "scorer source search result",
                {
                    candidate.scorer_evidence.source_search_result_receipt_sha256
                    for candidate in scored
                    if candidate.scorer_evidence is not None
                },
            ),
            (
                "scorer implementation",
                {
                    candidate.scorer_evidence.scorer_implementation_source_sha256
                    for candidate in scored
                    if candidate.scorer_evidence is not None
                },
            ),
            (
                "validity context",
                {
                    candidate.pose_validity_receipt.validity_context_fingerprint_sha256
                    for candidate in self.candidates
                    if candidate.pose_validity_receipt is not None
                },
            ),
            (
                "validity config",
                {
                    candidate.pose_validity_receipt.validity_config_fingerprint_sha256
                    for candidate in self.candidates
                    if candidate.pose_validity_receipt is not None
                },
            ),
            (
                "validity evaluator implementation",
                {
                    candidate.pose_validity_receipt.evaluator_implementation_source_sha256
                    for candidate in self.candidates
                    if candidate.pose_validity_receipt is not None
                },
            ),
        ):
            if len(evidence_values) > 1:
                raise PipelineCandidateEvidenceV2Error(
                    f"{evidence_name} is cross-wired across the batch"
                )
        proposal_generation_inputs = {
            candidate.proposal_execution_receipt.generation_input_receipt_sha256
            for candidate in self.candidates
            if candidate.proposal_execution_receipt is not None
        }
        if proposal_generation_inputs and proposal_generation_inputs != {
            self.allocation.features.exact_v11_source_receipt_sha256
        }:
            raise PipelineCandidateEvidenceV2Error(
                "proposal generation input is not the exact V1.1 source receipt"
            )
        if len({candidate.receipt_sha256 for candidate in self.candidates}) != 64:
            raise PipelineCandidateEvidenceV2Error(
                "candidate evidence receipts are not slot-unique"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def stable_ranking_slot_indices(self) -> tuple[int, ...]:
        return tuple(
            candidate.slot_index
            for candidate in sorted(
                (candidate for candidate in self.candidates if candidate.rank_eligible),
                key=lambda candidate: int(candidate.stable_rank or 0),
            )
        )

    @property
    def top1_slot_index(self) -> int | None:
        ranking = self.stable_ranking_slot_indices
        return None if not ranking else ranking[0]

    @property
    def top5_slot_indices(self) -> tuple[int, ...]:
        return self.stable_ranking_slot_indices[:TOP_K_LIMIT]

    @property
    def stable_valid_ranking_slot_indices(self) -> tuple[int, ...]:
        return tuple(
            candidate.slot_index
            for candidate in sorted(
                (
                    candidate
                    for candidate in self.candidates
                    if candidate.valid_rank_eligible
                ),
                key=lambda candidate: int(candidate.stable_valid_rank or 0),
            )
        )

    @property
    def valid_top1_slot_index(self) -> int | None:
        ranking = self.stable_valid_ranking_slot_indices
        return None if not ranking else ranking[0]

    @property
    def valid_top5_slot_indices(self) -> tuple[int, ...]:
        return self.stable_valid_ranking_slot_indices[:TOP_K_LIMIT]

    @property
    def top1_pose_valid(self) -> bool | None:
        if self.top1_slot_index is None:
            return None
        receipt = self.candidates[self.top1_slot_index].pose_validity_receipt
        if receipt is None:
            return None
        return receipt.valid

    @property
    def invalid_top1(self) -> bool | None:
        top1_pose_valid = self.top1_pose_valid
        return None if top1_pose_valid is None else not top1_pose_valid

    @property
    def scored_success_count(self) -> int:
        return sum(
            candidate.status == SCORED_SUCCESS_STATUS for candidate in self.candidates
        )

    @property
    def score_evidence_complete_count(self) -> int:
        return sum(candidate.score_evidence_complete for candidate in self.candidates)

    @property
    def typed_failure_count(self) -> int:
        return len(self.candidates) - self.scored_success_count

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "builder_id": PIPELINE_CANDIDATE_EVIDENCE_V2_BUILDER_ID,
            "candidate_denominator": len(self.candidates),
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_profile_id": self.allocation.profile_id,
            "allocation": self.allocation.to_dict(),
            "geometric_admission_batch_receipt_sha256": (
                self.geometric_admission_batch.receipt_sha256
            ),
            "geometric_admission_batch": (self.geometric_admission_batch.to_dict()),
            "scored_success_count": self.scored_success_count,
            "score_evidence_complete_count": self.score_evidence_complete_count,
            "typed_failure_count": self.typed_failure_count,
            "stable_ranking_slot_indices": list(self.stable_ranking_slot_indices),
            "top1_slot_index": self.top1_slot_index,
            "top5_slot_indices": list(self.top5_slot_indices),
            "primary_ranking_semantics": (
                "all_complete_score_evidence_geometrically_admitted_candidates_"
                "including_pose_invalid_and_validity_unavailable"
            ),
            "top1_pose_valid": self.top1_pose_valid,
            "invalid_top1": self.invalid_top1,
            "stable_valid_ranking_slot_indices": list(
                self.stable_valid_ranking_slot_indices
            ),
            "valid_top1_slot_index": self.valid_top1_slot_index,
            "valid_top5_slot_indices": list(self.valid_top5_slot_indices),
            "valid_only_ranking_semantics": (
                "primary_score_order_filtered_by_complete_pose_validity_true"
            ),
            "candidate_receipt_sha256s": [
                candidate.receipt_sha256 for candidate in self.candidates
            ],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "ranking_order": (
                "finite_total_score_ascending_then_slot_index_then_result_sha256"
            ),
            "top_k_limit": TOP_K_LIMIT,
            "denominator_failure_complete": True,
            "denominator_failure_completeness_scope": (
                DENOMINATOR_FAILURE_COMPLETENESS_SCOPE
            ),
            "evidence_completion_flags_caller_supplied": False,
            "rank_eligibility_caller_supplied": False,
            "top_k_membership_caller_supplied": False,
            "activation_evidence_eligible": False,
            "activation_evidence_blockers": list(ACTIVATION_EVIDENCE_BLOCKERS),
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_mutation_authorized": False,
            "existing_rank_auto_change_authorized": False,
            "customer_pose_emission_authorized": False,
            "public_benchmark_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
            "stage0_admission_authority": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PipelineCandidateEvidenceV2Error(
                "pipeline candidate evidence batch changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _record_score_rank_eligible(
    slot: FixedMixed64Slot,
    geometric_decision: GeometricAdmissionDecisionV2,
    record: PipelineCandidateRecordV2,
) -> bool:
    return bool(
        slot.generation_eligible
        and geometric_decision.accepted
        and record.source_proposal_sha256 is not None
        and record.result_proposal_sha256 is not None
        and record.proposal_execution_receipt is not None
        and record.scorer_evidence is not None
        and record.refinement_receipt is not None
    )


def build_pipeline_candidate_evidence_v2(
    allocation: FixedMixed64Allocation,
    geometric_admission_batch: GeometricAdmissionBatchV2,
    records: tuple[PipelineCandidateRecordV2, ...],
) -> PipelineCandidateEvidenceBatchV2:
    """Build and re-rank exact typed records without executing molecules."""

    if type(allocation) is not FixedMixed64Allocation:
        raise TypeError("allocation must be exact FixedMixed64Allocation")
    if type(geometric_admission_batch) is not GeometricAdmissionBatchV2:
        raise TypeError(
            "geometric_admission_batch must be exact GeometricAdmissionBatchV2"
        )
    if type(records) is not tuple or any(
        type(record) is not PipelineCandidateRecordV2 for record in records
    ):
        raise TypeError("records must contain exact PipelineCandidateRecordV2 values")
    if len(records) != FIXED_MIXED64_CANDIDATE_COUNT:
        raise PipelineCandidateEvidenceV2Error(
            "candidate evidence builder requires exactly 64 records"
        )
    if tuple(record.slot_index for record in records) != tuple(range(64)):
        raise PipelineCandidateEvidenceV2Error(
            "candidate evidence records are not index-stable"
        )
    allocation_sha256 = allocation.receipt_sha256
    geometric_batch_sha256 = geometric_admission_batch.receipt_sha256
    if geometric_admission_batch.allocation.receipt_sha256 != allocation_sha256:
        raise PipelineCandidateEvidenceV2Error(
            "geometric admission batch allocation receipt is cross-wired"
        )
    score_rankable = sorted(
        (
            (slot, decision, record)
            for slot, decision, record in zip(
                allocation.slots,
                geometric_admission_batch.decisions,
                records,
                strict=True,
            )
            if _record_score_rank_eligible(slot, decision, record)
        ),
        key=lambda pair: (
            pair[2].scorer_evidence.terms.total_score,  # type: ignore[union-attr]
            pair[2].slot_index,
            str(pair[2].result_proposal_sha256),
        ),
    )
    rank_by_slot = {
        record.slot_index: rank
        for rank, (_, _, record) in enumerate(score_rankable, start=1)
    }
    valid_rank_by_slot = {
        record.slot_index: rank
        for rank, (_, _, record) in enumerate(
            (
                row
                for row in score_rankable
                if row[2].pose_validity_receipt is not None
                and row[2].pose_validity_receipt.valid
            ),
            start=1,
        )
    }
    candidates = tuple(
        PipelineCandidateEvidenceV2(
            allocation_receipt_sha256=allocation_sha256,
            geometric_admission_batch_receipt_sha256=geometric_batch_sha256,
            allocation_slot=slot,
            geometric_decision=decision,
            source_proposal_sha256=record.source_proposal_sha256,
            result_proposal_sha256=record.result_proposal_sha256,
            proposal_execution_receipt=record.proposal_execution_receipt,
            scorer_evidence=record.scorer_evidence,
            pose_validity_receipt=record.pose_validity_receipt,
            refinement_receipt=record.refinement_receipt,
            execution_failure_stage=record.execution_failure_stage,
            execution_failure_code=record.execution_failure_code,
            stable_rank=rank_by_slot.get(record.slot_index),
            stable_valid_rank=valid_rank_by_slot.get(record.slot_index),
            _factory_seal=_CANDIDATE_FACTORY_SEAL,
        )
        for slot, decision, record in zip(
            allocation.slots,
            geometric_admission_batch.decisions,
            records,
            strict=True,
        )
    )
    return PipelineCandidateEvidenceBatchV2(
        allocation=allocation,
        geometric_admission_batch=geometric_admission_batch,
        candidates=candidates,
    )


__all__ = [
    "ALLOCATION_FAILURE_STATUS",
    "DENOMINATOR_FAILURE_COMPLETENESS_SCOPE",
    "EXECUTION_FAILURE_STATUS",
    "EXECUTION_FAILURE_STAGE_REFINEMENT",
    "EXECUTION_FAILURE_STAGE_SCORING",
    "EXECUTION_FAILURE_STAGE_VALIDITY",
    "EXECUTION_FAILURE_STAGES",
    "GEOMETRIC_REJECTION_STATUS",
    "PIPELINE_CANDIDATE_EVIDENCE_BATCH_V2_SCHEMA_ID",
    "PIPELINE_CANDIDATE_EVIDENCE_V2_BUILDER_ID",
    "PIPELINE_CANDIDATE_EVIDENCE_V2_SCHEMA_ID",
    "POSE_VALIDITY_RECEIPT_V2_SCHEMA_ID",
    "PROPOSAL_EXECUTION_RECEIPT_V2_SCHEMA_ID",
    "PipelineCandidateEvidenceBatchV2",
    "PipelineCandidateEvidenceV2",
    "PipelineCandidateEvidenceV2Error",
    "PipelineCandidateRecordV2",
    "PoseValidityReceiptV2",
    "ProposalExecutionReceiptV2",
    "REFINEMENT_RECEIPT_BINDING_V2_SCHEMA_ID",
    "REFINEMENT_SOURCE_RECEIPT_IDENTITY_V2_SCHEMA_ID",
    "REQUIRED_POSE_VALIDITY_CHECKS",
    "RefinementReceiptBindingV2",
    "SCORER_V1_EVIDENCE_BINDING_V2_SCHEMA_ID",
    "SCORED_SUCCESS_STATUS",
    "ScorerV1EvidenceBindingV2",
    "TOP_K_LIMIT",
    "build_pipeline_candidate_evidence_v2",
    "bind_pose_validity_receipt_v2",
    "bind_proposal_execution_receipt_v2",
    "bind_refinement_receipt_v2",
    "bind_scorer_v1_evidence_v2",
]
