"""Execution-free Engine V2 evidence projection for operator shadow review.

This module is deliberately not a runner, router, or product integration.  It
accepts already-produced candidate evidence, validates the receipts needed for
an operator second opinion, and emits a deterministic projection that cannot
contain pose material.  Authentication and operator authorization remain the
responsibility of the caller.

The projector omits sensitive source fields and records only their count.  The
validator rejects the same fields if they are reintroduced into a projected
document.  Existing source schemas are not mutated or re-labelled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import re
from types import MappingProxyType

from .docking.scorer_v1 import ScorerV1Error, ScorerV1Terms
from .docking.torsion_contact_refinement import (
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
    INTERACTION_AWARE_TORSION_CLEARANCE_RECEIPT_V8_SCHEMA_ID,
    INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
)
from .pipeline import (
    DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID,
    DockingPipelineError,
    validate_docking_pipeline_candidate_evidence_document,
    validate_docking_pipeline_profile_document,
)


ENGINE_V2_PRODUCT_SHADOW_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_product_shadow_policy/1.0.0"
)
ENGINE_V2_PRODUCT_SHADOW_POLICY_ID = (
    "betelgeuze.engine_v2_operator_second_opinion_shadow/1.0.0"
)
ENGINE_V2_PRODUCT_SHADOW_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_product_shadow_evidence/1.0.0"
)
ENGINE_V2_PRODUCT_SHADOW_CANDIDATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_product_shadow_candidate/1.0.0"
)
ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID = (
    "betelgeuze.engine_v2_shadow_completed_pipeline_execution/1.0.0"
)
_STAGE0_ADMISSION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_stage0_admission_receipt/1.0.0"
)

ENGINE_V2_PRODUCT_SHADOW_PERMISSIONS = MappingProxyType(
    {
        "evidence_display_allowed": True,
        "operator_second_opinion_allowed": True,
        "automatic_rank_mutation_allowed": False,
        "customer_pose_emission_allowed": False,
        "production_claim_allowed": False,
        "customer_execution_allowed": False,
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FAILURE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_MAX_TEXT_LENGTH = 4096
_MAX_COLLECTION_LENGTH = 8192
_MAX_NESTING_DEPTH = 32
_SCORER_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)
_SCORER_COUNT_NAMES = (
    "receptor_candidate_pair_count",
    "ligand_pair_count",
    "hbond_count",
    "hydrophobic_contact_count",
    "buried_polar_count",
)
_ALLOWED_PROPOSAL_MODES = frozenset(
    {
        "aromatic_plane_alignment",
        "charge_pair_alignment",
        "donor_acceptor_alignment",
        "independent_orientation",
        "pocket_center_baseline",
        "pocket_centered_control",
        "retained_paired_control",
        "retained_source_variant_clearance_rescue",
        "shape_axis_alignment",
        "true_conformer_independent_orientation",
        "uniform_fallback",
        "uniform_source_control",
        "uniform_torsion_rescue_variant",
        "uniform_v3_rigid_ensemble",
    }
)
_ALLOWED_VALIDITY_CHECKS = frozenset(
    {
        "all_atoms_finite",
        "chemical_valid",
        "geometric_valid",
        "heavy_atom_penetration_free",
        "inside_declared_pocket",
        "minimum_vdw_gap_pass",
        "posebusters_valid",
        "selection_eligible",
        "severe_overlap_free",
    }
)
_ALLOWED_VALIDITY_MEASUREMENTS = frozenset(
    {
        "minimum_distance_angstrom",
        "minimum_vdw_gap_angstrom",
        "heavy_atom_penetration_count",
        "pocket_escape_count",
        "volume_overlap_estimate",
        "receptor_internal_objective",
        "ligand_internal_objective",
        "combined_objective",
        "ligand_atom_count",
        "receptor_atom_count",
        "exact_pair_count",
    }
)
_REQUIRED_VALIDITY_CHECKS = frozenset(
    {
        "chemical_valid",
        "geometric_valid",
        "posebusters_valid",
        "selection_eligible",
    }
)
_COUNT_VALIDITY_MEASUREMENTS = frozenset(
    {
        "heavy_atom_penetration_count",
        "pocket_escape_count",
        "ligand_atom_count",
        "receptor_atom_count",
        "exact_pair_count",
    }
)
_ALLOWED_VALIDITY_BLOCKERS = frozenset(
    {
        "candidate_execution_failed",
        "chemical_invalid",
        "geometric_invalid",
        "heavy_atom_penetration_detected",
        "minimum_vdw_gap_failed",
        "pose_outside_declared_pocket",
        "posebusters_invalid",
        "selection_ineligible",
        "severe_overlap_detected",
        "validity_not_evaluated",
    }
)
_ALLOWED_NOT_EVALUATED_REASONS = frozenset(
    {
        "candidate_execution_failed",
        "evaluator_unavailable",
        "input_evidence_incomplete",
        "not_applicable_to_failed_candidate",
    }
)
_ALLOWED_DISAGREEMENT_REASONS = frozenset(
    {
        "baseline_candidate_failed",
        "baseline_missing",
        "raw_top1_candidate_changed",
        "score_order_changed",
        "top5_membership_changed",
        "validity_disagreement",
    }
)
_ALLOWED_BASELINE_UNAVAILABLE_REASONS = frozenset(
    {
        "baseline_not_evaluated",
    }
)
_ALLOWED_ABSTENTION_REASONS = frozenset(
    {
        "baseline_evidence_incomplete",
        "candidate_execution_failed",
        "candidate_invalid",
        "operator_review_required",
        "pose_validity_failed",
        "profile_mismatch",
        "refinement_receipt_missing",
        "scoring_receipt_missing",
    }
)
_ALLOWED_POSE_KEYS = frozenset(
    {
        "pose_validity",
        "customer_pose_emission_allowed",
    }
)
_ALLOWED_CANDIDATE_SCHEMA_IDS = frozenset(
    {DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID}
)
_ALLOWED_REFINEMENT_SCHEMA_IDS = frozenset(
    {
        INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
        INTERACTION_AWARE_TORSION_CLEARANCE_RECEIPT_V8_SCHEMA_ID,
        INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
    }
)


class EngineV2ProductShadowError(ValueError):
    """The operator-only shadow evidence contract was violated."""


def _verified_stage0_admission_document(
    stage0_admission: object,
) -> dict[str, object]:
    """Validate the serialized verifier authority without importing benchmarks."""

    authority_type = type(stage0_admission)
    if (
        authority_type.__name__ != "VerifiedStage0Admission"
        or authority_type.__module__ != "betelgeuze_engine_v2.benchmark.blind_stage0"
    ):
        raise EngineV2ProductShadowError(
            "verified Stage 0 admission authority is required"
        )
    try:
        to_dict = getattr(stage0_admission, "to_dict")
        document = _require_mapping(to_dict(), name="Stage 0 admission receipt")
        authority_receipt_sha256 = getattr(stage0_admission, "receipt_sha256")
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise EngineV2ProductShadowError(
            "verified Stage 0 admission authority is invalid"
        ) from exc
    required = {
        "schema_id",
        "admitted",
        "policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "reviewer_id",
        "operator_id",
        "governance_mode",
        "independent_review_complete",
        "trusted_review_time_authority_id",
        "trusted_review_time_evidence_sha256",
        "external_run_once_authority_id",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_id",
        "docking_pipeline_profile_sha256",
        "receipt_sha256",
    }
    if set(document) != required:
        raise EngineV2ProductShadowError(
            "verified Stage 0 admission receipt fields are invalid"
        )
    receipt_sha256 = _require_digest(
        document.get("receipt_sha256"),
        name="Stage 0 admission receipt_sha256",
    )
    unsigned = dict(document)
    unsigned.pop("receipt_sha256")
    if (
        document.get("schema_id") != _STAGE0_ADMISSION_RECEIPT_SCHEMA_ID
        or document.get("admitted") is not True
        or document.get("governance_mode") != "independent_three_role"
        or document.get("independent_review_complete") is not True
        or receipt_sha256 != authority_receipt_sha256
        or _sha256(unsigned) != receipt_sha256
    ):
        raise EngineV2ProductShadowError(
            "verified Stage 0 admission receipt is invalid"
        )
    for field in (
        "policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "trusted_review_time_evidence_sha256",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_sha256",
    ):
        _require_digest(document.get(field), name=f"Stage 0 admission {field}")
    for field in (
        "reviewer_id",
        "operator_id",
        "trusted_review_time_authority_id",
        "external_run_once_authority_id",
        "docking_pipeline_profile_id",
    ):
        _require_text(document.get(field), name=f"Stage 0 admission {field}")
    return document


def _verified_stage0_admission_receipt(stage0_admission: object) -> str:
    return str(_verified_stage0_admission_document(stage0_admission)["receipt_sha256"])


def _trusted_pipeline_profile_sha256s(
    stage0_admission: object,
) -> dict[str, frozenset[str]]:
    """Derive the sole executable profile from verified Stage 0 authority."""

    execution = _verified_stage0_admission_document(stage0_admission)
    profile_id = _require_text(
        execution.get("docking_pipeline_profile_id"),
        name="Stage 0 docking pipeline profile_id",
    )
    profile_sha256 = _require_digest(
        execution.get("docking_pipeline_profile_sha256"),
        name="Stage 0 docking pipeline profile_sha256",
    )
    return {profile_id: frozenset({profile_sha256})}


def _json_value(
    value: object,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
) -> object:
    if depth > _MAX_NESTING_DEPTH:
        raise EngineV2ProductShadowError("evidence nesting is too deep")
    if value is None or type(value) is bool or type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise EngineV2ProductShadowError("evidence contains a non-finite number")
        return value
    if type(value) is str:
        if len(value) > _MAX_TEXT_LENGTH:
            raise EngineV2ProductShadowError("evidence text is too long")
        return value
    if isinstance(value, Mapping):
        active = seen if seen is not None else set()
        identity = id(value)
        if identity in active:
            raise EngineV2ProductShadowError("evidence contains a cycle")
        if len(value) > _MAX_COLLECTION_LENGTH:
            raise EngineV2ProductShadowError("evidence mapping is too large")
        active.add(identity)
        normalized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            if type(raw_key) is not str or not raw_key:
                raise EngineV2ProductShadowError(
                    "evidence mapping keys must be non-empty strings"
                )
            normalized[raw_key] = _json_value(
                raw_value,
                depth=depth + 1,
                seen=active,
            )
        active.remove(identity)
        return normalized
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        active = seen if seen is not None else set()
        identity = id(value)
        if identity in active:
            raise EngineV2ProductShadowError("evidence contains a cycle")
        if len(value) > _MAX_COLLECTION_LENGTH:
            raise EngineV2ProductShadowError("evidence sequence is too large")
        active.add(identity)
        normalized = [_json_value(item, depth=depth + 1, seen=active) for item in value]
        active.remove(identity)
        return normalized
    raise EngineV2ProductShadowError(
        f"evidence value has unsupported type {type(value).__name__}"
    )


def _canonical_bytes(value: object) -> bytes:
    normalized = _json_value(value)
    try:
        return json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:  # defensive after _json_value
        raise EngineV2ProductShadowError("evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise EngineV2ProductShadowError(f"{name} must be a mapping")
    normalized = _json_value(value)
    if not isinstance(normalized, dict):  # pragma: no cover - type narrowing
        raise EngineV2ProductShadowError(f"{name} must be a mapping")
    return normalized


def _require_text(
    value: object,
    *,
    name: str,
    allow_empty: bool = False,
    maximum: int = 240,
) -> str:
    if type(value) is not str:
        raise EngineV2ProductShadowError(f"{name} must be text")
    text = value.strip()
    if (not text and not allow_empty) or len(text) > maximum:
        raise EngineV2ProductShadowError(f"{name} is invalid")
    return text


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise EngineV2ProductShadowError(f"{name} must be a lowercase SHA-256")
    return value


def _require_failure_code(value: object, *, name: str) -> str:
    code = _require_text(value, name=name)
    if _FAILURE_CODE_RE.fullmatch(code) is None:
        raise EngineV2ProductShadowError(f"{name} must be a neutral identifier")
    return code


def _require_index(value: object, *, name: str, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if type(value) is not int or not 0 <= value < _MAX_COLLECTION_LENGTH:
        raise EngineV2ProductShadowError(f"{name} is invalid")
    return value


def _sensitive_field_kind(key: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    if normalized in _ALLOWED_POSE_KEYS:
        return None
    tokens = tuple(part for part in normalized.split("_") if part)
    if any(token in {"coordinate", "coordinates"} for token in tokens):
        return "coordinate"
    if "rmsd" in tokens or "rmsd" in normalized:
        return "rmsd"
    if "native" in tokens:
        return "native"
    if "reference" in tokens:
        return "reference"
    if any(
        token in {"path", "filepath", "filename", "file", "directory", "dir", "uri"}
        for token in tokens
    ) or normalized.endswith("path"):
        return "path"
    if "pose" in tokens:
        return "pose"
    return None


def _redact_sensitive_source(value: object) -> tuple[object, int]:
    active: set[int] = set()

    def visit(current: object, depth: int) -> tuple[object, int]:
        if depth > _MAX_NESTING_DEPTH:
            raise EngineV2ProductShadowError("evidence nesting is too deep")
        if isinstance(current, Mapping):
            identity = id(current)
            if identity in active:
                raise EngineV2ProductShadowError("evidence contains a cycle")
            if len(current) > _MAX_COLLECTION_LENGTH:
                raise EngineV2ProductShadowError("evidence mapping is too large")
            active.add(identity)
            output: dict[str, object] = {}
            count = 0
            for raw_key, raw_value in current.items():
                if type(raw_key) is not str or not raw_key:
                    raise EngineV2ProductShadowError(
                        "evidence mapping keys must be non-empty strings"
                    )
                if _sensitive_field_kind(raw_key) is not None:
                    count += 1
                    continue
                child, child_count = visit(raw_value, depth + 1)
                output[raw_key] = child
                count += child_count
            active.remove(identity)
            return output, count
        if isinstance(current, Sequence) and not isinstance(
            current,
            (str, bytes, bytearray),
        ):
            identity = id(current)
            if identity in active:
                raise EngineV2ProductShadowError("evidence contains a cycle")
            if len(current) > _MAX_COLLECTION_LENGTH:
                raise EngineV2ProductShadowError("evidence sequence is too large")
            active.add(identity)
            output_list: list[object] = []
            count = 0
            for item in current:
                child, child_count = visit(item, depth + 1)
                output_list.append(child)
                count += child_count
            active.remove(identity)
            return output_list, count
        return _json_value(current), 0

    return visit(value, 0)


def _assert_projection_safe(value: object, *, location: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if type(raw_key) is not str:
                raise EngineV2ProductShadowError(
                    "projected evidence contains a non-text key"
                )
            kind = _sensitive_field_kind(raw_key)
            if kind is not None:
                raise EngineV2ProductShadowError(
                    f"projected evidence contains forbidden {kind} field at "
                    f"{location}.{raw_key}"
                )
            _assert_projection_safe(child, location=f"{location}.{raw_key}")
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for index, child in enumerate(value):
            _assert_projection_safe(child, location=f"{location}[{index}]")
    elif isinstance(value, str) and (
        value.startswith(("/", "~/", "file://", "\\\\"))
        or re.match(r"^[A-Za-z]:[\\\\/]", value) is not None
        or re.search(r"(?:^|\s)(?:/|~/|file://|[A-Za-z]:[\\\\/])", value) is not None
    ):
        raise EngineV2ProductShadowError(
            f"projected evidence contains a forbidden path value at {location}"
        )


def _validated_scorer_terms(value: object) -> dict[str, object]:
    document = _require_mapping(value, name="scoring_terms")
    try:
        decoded = {
            name: float.fromhex(
                _require_text(
                    document.get(f"{name}_binary64_hex"),
                    name=f"scoring_terms.{name}_binary64_hex",
                    maximum=64,
                )
            )
            for name in _SCORER_TERM_NAMES
        }
        terms = ScorerV1Terms(
            proposal_fingerprint_sha256=_require_digest(
                document.get("proposal_fingerprint_sha256"),
                name="scoring_terms.proposal_fingerprint_sha256",
            ),
            authority_input_receipt_sha256=_require_digest(
                document.get("authority_input_receipt_sha256"),
                name="scoring_terms.authority_input_receipt_sha256",
            ),
            context_fingerprint_sha256=_require_digest(
                document.get("context_fingerprint_sha256"),
                name="scoring_terms.context_fingerprint_sha256",
            ),
            config_fingerprint_sha256=_require_digest(
                document.get("config_fingerprint_sha256"),
                name="scoring_terms.config_fingerprint_sha256",
            ),
            backend_receipt_sha256=_require_digest(
                document.get("backend_receipt_sha256"),
                name="scoring_terms.backend_receipt_sha256",
            ),
            **decoded,
            **{name: document.get(name) for name in _SCORER_COUNT_NAMES},
        )
    except (EngineV2ProductShadowError, ScorerV1Error, TypeError, ValueError) as exc:
        if isinstance(exc, EngineV2ProductShadowError):
            raise
        raise EngineV2ProductShadowError(
            "scoring_terms is not a complete ScorerV1Terms receipt"
        ) from exc
    canonical = terms.to_dict()
    if document != canonical:
        raise EngineV2ProductShadowError(
            "scoring_terms is not the exact ScorerV1Terms receipt"
        )
    return canonical


def _validated_refinement_receipt(
    value: object,
) -> tuple[dict[str, object], dict[str, object]]:
    document = _require_mapping(value, name="refinement_receipt")
    schema_id = _require_text(
        document.get("schema_id"),
        name="refinement_receipt.schema_id",
    )
    if schema_id not in _ALLOWED_REFINEMENT_SCHEMA_IDS:
        raise EngineV2ProductShadowError(
            "refinement receipt schema is outside the shadow registry"
        )
    receipt_sha256 = _require_digest(
        document.get("receipt_sha256"),
        name="refinement_receipt.receipt_sha256",
    )
    unsigned = dict(document)
    unsigned.pop("receipt_sha256", None)
    if _sha256(unsigned) != receipt_sha256:
        raise EngineV2ProductShadowError("refinement_receipt self-hash is invalid")
    identity = {
        "source_receipt_sha256": receipt_sha256,
        "source_receipt_self_hash_verified_before_projection": True,
    }
    return document, identity


def _validated_lineage(value: object, *, status: str) -> dict[str, object]:
    document = _require_mapping(value, name="proposal_lineage")
    proposal_index = _require_index(
        document.get("proposal_index"),
        name="proposal_lineage.proposal_index",
    )
    raw_proposal_mode = document.get("proposal_mode")
    if status == "failure" and (raw_proposal_mode is None or raw_proposal_mode == ""):
        proposal_mode: str | None = None
    else:
        proposal_mode = _require_text(
            raw_proposal_mode,
            name="proposal_lineage.proposal_mode",
        )
        if proposal_mode not in _ALLOWED_PROPOSAL_MODES:
            raise EngineV2ProductShadowError(
                "proposal_lineage.proposal_mode is outside the shadow vocabulary"
            )
    fingerprint_value = document.get("proposal_fingerprint_sha256")
    if status == "success" or fingerprint_value not in {None, ""}:
        fingerprint: str | None = _require_digest(
            fingerprint_value,
            name="proposal_lineage.proposal_fingerprint_sha256",
        )
    else:
        fingerprint = None
    source_index = _require_index(
        document.get("source_proposal_index"),
        name="proposal_lineage.source_proposal_index",
        optional=True,
    )
    parent_index = _require_index(
        document.get("parent_proposal_index"),
        name="proposal_lineage.parent_proposal_index",
        optional=True,
    )
    if source_index == proposal_index or parent_index == proposal_index:
        raise EngineV2ProductShadowError("proposal lineage cannot point to itself")
    return {
        "proposal_index": proposal_index,
        "proposal_mode": proposal_mode,
        "proposal_fingerprint_sha256": fingerprint,
        "source_proposal_index": source_index,
        "parent_proposal_index": parent_index,
    }


def _bool_mapping(
    value: object,
    *,
    name: str,
    allowed_keys: frozenset[str],
) -> dict[str, bool]:
    document = _require_mapping(value, name=name)
    normalized: dict[str, bool] = {}
    for raw_key, raw_value in sorted(document.items()):
        key = _require_text(raw_key, name=f"{name} key")
        if key not in allowed_keys:
            raise EngineV2ProductShadowError(
                f"{name}.{key} is outside the shadow vocabulary"
            )
        if type(raw_value) is not bool:
            raise EngineV2ProductShadowError(f"{name}.{key} must be boolean")
        normalized[key] = raw_value
    return normalized


def _text_list(
    value: object,
    *,
    name: str,
    allowed_values: frozenset[str],
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise EngineV2ProductShadowError(f"{name} must be a sequence")
    normalized = [_require_text(item, name=f"{name} item") for item in value]
    if len(normalized) != len(set(normalized)):
        raise EngineV2ProductShadowError(f"{name} contains duplicates")
    if any(item not in allowed_values for item in normalized):
        raise EngineV2ProductShadowError(
            f"{name} contains a value outside the shadow vocabulary"
        )
    return normalized


def _validated_pose_validity(value: object) -> dict[str, object]:
    document = _require_mapping(value, name="pose_validity")
    valid = document.get("valid")
    complete = document.get("complete")
    within_scope = document.get("valid_within_evaluated_scope")
    if any(type(item) is not bool for item in (valid, complete, within_scope)):
        raise EngineV2ProductShadowError("pose_validity status fields must be boolean")
    if valid != bool(complete and within_scope):
        raise EngineV2ProductShadowError("pose_validity.valid is inconsistent")
    checks = _bool_mapping(
        document.get("checks"),
        name="pose_validity.checks",
        allowed_keys=_ALLOWED_VALIDITY_CHECKS,
    )
    evaluated = _bool_mapping(
        document.get("evaluated_checks"),
        name="pose_validity.evaluated_checks",
        allowed_keys=_ALLOWED_VALIDITY_CHECKS,
    )
    if set(checks) != set(evaluated):
        raise EngineV2ProductShadowError("pose_validity check sets are inconsistent")
    if not _REQUIRED_VALIDITY_CHECKS.issubset(checks):
        raise EngineV2ProductShadowError(
            "pose_validity required check set is incomplete"
        )
    if complete != all(evaluated.values()):
        raise EngineV2ProductShadowError("pose_validity completeness is inconsistent")
    observed_scope = bool(
        any(evaluated.values())
        and all(
            checks[name] for name, was_evaluated in evaluated.items() if was_evaluated
        )
    )
    if within_scope != observed_scope:
        raise EngineV2ProductShadowError(
            "pose_validity evaluated result is inconsistent"
        )
    measurements_document = _require_mapping(
        document.get("measurements"),
        name="pose_validity.measurements",
    )
    measurements: dict[str, float | int] = {}
    for raw_key, raw_value in sorted(measurements_document.items()):
        key = _require_text(raw_key, name="pose_validity measurement key")
        if key not in _ALLOWED_VALIDITY_MEASUREMENTS:
            raise EngineV2ProductShadowError(
                "pose_validity measurement is outside the shadow vocabulary"
            )
        if key in _COUNT_VALIDITY_MEASUREMENTS:
            if type(raw_value) is not int or raw_value < 0:
                raise EngineV2ProductShadowError(
                    f"pose_validity.measurements.{key} must be a non-negative integer"
                )
            measurements[key] = raw_value
        elif type(raw_value) is float and math.isfinite(raw_value):
            measurements[key] = raw_value
        else:
            raise EngineV2ProductShadowError(
                f"pose_validity.measurements.{key} must be finite binary64 evidence"
            )
    blockers = _text_list(
        document.get("blockers"),
        name="pose_validity.blockers",
        allowed_values=_ALLOWED_VALIDITY_BLOCKERS,
    )
    reasons_document = _require_mapping(
        document.get("not_evaluated_reasons"),
        name="pose_validity.not_evaluated_reasons",
    )
    reasons: dict[str, str] = {}
    for raw_key, raw_reason in sorted(reasons_document.items()):
        key = _require_text(raw_key, name="pose_validity reason key")
        reason = _require_text(
            raw_reason,
            name=f"pose_validity.not_evaluated_reasons.{key}",
        )
        if (
            key not in _ALLOWED_VALIDITY_CHECKS
            or reason not in _ALLOWED_NOT_EVALUATED_REASONS
        ):
            raise EngineV2ProductShadowError(
                "pose_validity not-evaluated reason is outside the shadow vocabulary"
            )
        reasons[key] = reason
    unevaluated = {
        name for name, was_evaluated in evaluated.items() if not was_evaluated
    }
    if set(reasons) != unevaluated:
        raise EngineV2ProductShadowError(
            "pose_validity not-evaluated reasons are incomplete or contradictory"
        )
    if valid and blockers:
        raise EngineV2ProductShadowError(
            "valid pose_validity evidence cannot contain blockers"
        )
    if not valid and not blockers:
        raise EngineV2ProductShadowError(
            "invalid pose_validity evidence requires a blocker"
        )
    if not complete and not {
        "validity_not_evaluated",
        "candidate_execution_failed",
    }.intersection(blockers):
        raise EngineV2ProductShadowError(
            "incomplete pose_validity evidence requires an evaluation blocker"
        )
    if document.get("claim_safe") is not False:
        raise EngineV2ProductShadowError("pose_validity must remain claim_safe=false")
    return {
        "valid": valid,
        "checks": checks,
        "evaluated_checks": evaluated,
        "complete": complete,
        "valid_within_evaluated_scope": within_scope,
        "measurements": measurements,
        "blockers": blockers,
        "not_evaluated_reasons": reasons,
        "claim_safe": False,
    }


def _validated_reason_decision(
    value: object,
    *,
    name: str,
    decision_field: str,
    allowed_reasons: frozenset[str],
) -> dict[str, object]:
    document = _require_mapping(value, name=name)
    decision = document.get(decision_field)
    if type(decision) is not bool:
        raise EngineV2ProductShadowError(f"{name}.{decision_field} must be boolean")
    reasons = _text_list(
        document.get("reason_codes"),
        name=f"{name}.reason_codes",
        allowed_values=allowed_reasons,
    )
    if decision != bool(reasons):
        raise EngineV2ProductShadowError(
            f"{name} decision and reason_codes are inconsistent"
        )
    return {decision_field: decision, "reason_codes": reasons}


def _validated_projected_baseline_disagreement(value: object) -> dict[str, object]:
    document = _require_mapping(value, name="baseline_disagreement")
    available = document.get("available")
    if available is True:
        if set(document) != {"available", "disagrees", "reason_codes"}:
            raise EngineV2ProductShadowError(
                "available baseline disagreement fields are not exact"
            )
        decision = _validated_reason_decision(
            {
                "disagrees": document.get("disagrees"),
                "reason_codes": document.get("reason_codes"),
            },
            name="baseline_disagreement",
            decision_field="disagrees",
            allowed_reasons=_ALLOWED_DISAGREEMENT_REASONS,
        )
        return {"available": True, **decision}
    if available is False:
        if set(document) != {
            "available",
            "disagrees",
            "reason_codes",
            "unavailable_reason",
        }:
            raise EngineV2ProductShadowError(
                "unavailable baseline disagreement fields are not exact"
            )
        reason = _require_text(
            document.get("unavailable_reason"),
            name="baseline_disagreement.unavailable_reason",
        )
        if reason not in _ALLOWED_BASELINE_UNAVAILABLE_REASONS:
            raise EngineV2ProductShadowError(
                "baseline unavailable reason is outside the shadow vocabulary"
            )
        if document.get("disagrees") is not None or document.get("reason_codes") != []:
            raise EngineV2ProductShadowError(
                "unavailable baseline cannot claim agreement or disagreement"
            )
        return {
            "available": False,
            "disagrees": None,
            "reason_codes": [],
            "unavailable_reason": reason,
        }
    raise EngineV2ProductShadowError("baseline availability must be explicit")


def engine_v2_product_shadow_policy() -> dict[str, object]:
    """Return the immutable execution-free operator-shadow permission policy."""

    policy: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_POLICY_SCHEMA_ID,
        "policy_id": ENGINE_V2_PRODUCT_SHADOW_POLICY_ID,
        "audience": "operator_only",
        "projection_only": True,
        "permissions": dict(ENGINE_V2_PRODUCT_SHADOW_PERMISSIONS),
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    policy["policy_sha256"] = _sha256(policy)
    return policy


def _project_candidate(
    value: Mapping[str, object],
    *,
    profile_id: str,
) -> dict[str, object]:
    try:
        original = validate_docking_pipeline_candidate_evidence_document(value)
    except DockingPipelineError as exc:
        raise EngineV2ProductShadowError(
            "candidate is not a verified DockingPipeline evidence wrapper"
        ) from exc
    if original.get("schema_id") not in _ALLOWED_CANDIDATE_SCHEMA_IDS:
        raise EngineV2ProductShadowError(
            "candidate schema is outside the shadow registry"
        )
    _, redacted_count = _redact_sensitive_source(original)
    status = _require_text(original.get("status"), name="candidate.status")
    raw_lineage = _require_mapping(original.get("lineage"), name="candidate.lineage")
    lineage = _validated_lineage(
        {
            "proposal_index": original.get("proposal_index"),
            "proposal_mode": raw_lineage.get("proposal_mode"),
            "proposal_fingerprint_sha256": raw_lineage.get(
                "proposal_fingerprint_sha256"
            ),
            "source_proposal_index": raw_lineage.get("ensemble_source_proposal_index"),
            "parent_proposal_index": raw_lineage.get(
                "torsion_rescue_parent_proposal_index"
            ),
        },
        status=status,
    )
    wrapper_validity = _require_mapping(
        original.get("validity"),
        name="candidate.validity",
    )
    if status == "success":
        geometric_valid = wrapper_validity.get("geometric_valid")
        chemical_valid = wrapper_validity.get("chemical_valid")
        selection_eligible = wrapper_validity.get("selection_eligible")
        if any(
            type(item) is not bool
            for item in (geometric_valid, chemical_valid, selection_eligible)
        ):
            raise EngineV2ProductShadowError(
                "successful candidate validity evidence is incomplete"
            )
        checks = {
            "chemical_valid": chemical_valid,
            "geometric_valid": geometric_valid,
            "posebusters_valid": bool(chemical_valid and geometric_valid),
            "selection_eligible": selection_eligible,
        }
        blockers: list[str] = []
        if not chemical_valid:
            blockers.append("chemical_invalid")
        if not geometric_valid:
            blockers.append("geometric_invalid")
        if not checks["posebusters_valid"]:
            blockers.append("posebusters_invalid")
        if not selection_eligible:
            blockers.append("selection_ineligible")
        validity = _validated_pose_validity(
            {
                "valid": all(checks.values()),
                "checks": checks,
                "evaluated_checks": {name: True for name in checks},
                "complete": True,
                "valid_within_evaluated_scope": all(checks.values()),
                "measurements": {},
                "blockers": blockers,
                "not_evaluated_reasons": {},
                "claim_safe": False,
            }
        )
        scoring_terms = _validated_scorer_terms(original.get("scorer_v1_terms"))
        proposal_sha256 = lineage["proposal_fingerprint_sha256"]
        if scoring_terms["proposal_fingerprint_sha256"] != proposal_sha256:
            raise EngineV2ProductShadowError(
                "candidate scoring terms and proposal lineage are cross-wired"
            )
        _, refinement_identity = _validated_refinement_receipt(
            original.get("refinement_receipt")
        )
        failure_reason = ""
    else:
        checks = {
            "chemical_valid": False,
            "geometric_valid": False,
            "posebusters_valid": False,
            "selection_eligible": False,
        }
        validity = _validated_pose_validity(
            {
                "valid": False,
                "checks": checks,
                "evaluated_checks": {name: False for name in checks},
                "complete": False,
                "valid_within_evaluated_scope": False,
                "measurements": {},
                "blockers": ["candidate_execution_failed"],
                "not_evaluated_reasons": {
                    name: "not_applicable_to_failed_candidate" for name in checks
                },
                "claim_safe": False,
            }
        )
        scoring_terms = None
        refinement_identity = None
        failure = _require_mapping(original.get("failure"), name="candidate.failure")
        failure_reason = _require_failure_code(
            failure.get("error_code"),
            name="candidate.failure.error_code",
        )

    raw_disagreement = _require_mapping(
        original.get("baseline_disagreement"),
        name="candidate.baseline_disagreement",
    )
    if raw_disagreement.get("available") is True:
        disagreement = _validated_projected_baseline_disagreement(
            {
                "available": True,
                "disagrees": raw_disagreement.get("disagrees"),
                "reason_codes": raw_disagreement.get("reason_codes"),
            }
        )
    else:
        disagreement = _validated_projected_baseline_disagreement(
            {
                "available": False,
                "disagrees": None,
                "reason_codes": [],
                "unavailable_reason": raw_disagreement.get("reason"),
            }
        )
    source_abstained = original.get("abstention")
    if type(source_abstained) is not bool:
        raise EngineV2ProductShadowError("candidate abstention must be boolean")
    abstention_reasons: list[str] = []
    if status == "failure":
        abstention_reasons.append("candidate_execution_failed")
    elif not validity["valid"]:
        abstention_reasons.append("candidate_invalid")
    if disagreement["available"] is False:
        abstention_reasons.append("baseline_evidence_incomplete")
    abstained = bool(source_abstained or disagreement["available"] is False)
    abstention = _validated_reason_decision(
        {"abstained": abstained, "reason_codes": abstention_reasons},
        name="abstention",
        decision_field="abstained",
        allowed_reasons=_ALLOWED_ABSTENTION_REASONS,
    )

    candidate: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_CANDIDATE_SCHEMA_ID,
        "profile_id": profile_id,
        "status": status,
        "proposal_lineage": lineage,
        "scoring_terms": scoring_terms,
        "pose_validity": validity,
        "refinement_receipt": refinement_identity,
        "failure_reason": failure_reason,
        "baseline_disagreement": disagreement,
        "abstention": abstention,
        "sensitive_source_fields_redacted": redacted_count > 0,
        "redacted_sensitive_field_count": redacted_count,
    }
    candidate["receipt_sha256"] = _sha256(candidate)
    return candidate


def _verified_profile_identity(
    value: object,
    *,
    stage0_admission: object,
) -> tuple[str, str]:
    profile = _require_mapping(value, name="profile_document")
    try:
        profile = validate_docking_pipeline_profile_document(profile)
    except DockingPipelineError as exc:
        raise EngineV2ProductShadowError(
            "profile_document is not an exact DockingPipeline profile"
        ) from exc
    profile_id = _require_text(profile.get("profile_id"), name="profile_id")
    profile_sha256 = _require_digest(
        profile.get("profile_sha256"), name="profile_sha256"
    )
    trusted = _trusted_pipeline_profile_sha256s(stage0_admission)
    if profile_sha256 not in trusted.get(profile_id, frozenset()):
        raise EngineV2ProductShadowError(
            "pipeline profile is outside the exact shadow registry"
        )
    return profile_id, profile_sha256


def _verified_source_identity(
    value: object,
    *,
    profile_id: str,
    profile_sha256: str,
    candidates: Sequence[Mapping[str, object]],
    upstream_evidence_document: Mapping[str, object],
    stage0_admission_receipt_sha256: str,
) -> str:
    source = _require_mapping(value, name="source_evidence_document")
    upstream = _require_mapping(
        upstream_evidence_document,
        name="upstream_evidence_document",
    )
    upstream_schema_id = _require_text(
        upstream.get("schema_id"),
        name="upstream_evidence_document.schema_id",
    )
    upstream_fields = {
        "schema_id",
        "pipeline_profile_id",
        "pipeline_profile_sha256",
        "stage0_admission_receipt_sha256",
        "candidate_count",
        "candidate_source_sha256s",
        "execution_completed",
        "projection_only",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }
    if set(upstream) != upstream_fields:
        raise EngineV2ProductShadowError("upstream execution fields are not exact")
    if upstream_schema_id != ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID:
        raise EngineV2ProductShadowError("upstream execution schema is unsupported")
    upstream_hash_field = "receipt_sha256"
    upstream_receipt_sha256 = _require_digest(
        upstream.get(upstream_hash_field),
        name="upstream evidence self-hash",
    )
    upstream_projection = dict(upstream)
    upstream_projection.pop(upstream_hash_field)
    if _sha256(upstream_projection) != upstream_receipt_sha256:
        raise EngineV2ProductShadowError(
            "upstream_evidence_document self-hash is invalid"
        )
    expected_candidate_sha256s = [_sha256(candidate) for candidate in candidates]
    if upstream.get("candidate_source_sha256s") != expected_candidate_sha256s:
        raise EngineV2ProductShadowError(
            "upstream execution candidate bindings are cross-wired"
        )
    if (
        upstream.get("pipeline_profile_id") != profile_id
        or upstream.get("pipeline_profile_sha256") != profile_sha256
        or upstream.get("stage0_admission_receipt_sha256")
        != stage0_admission_receipt_sha256
        or upstream.get("candidate_count") != len(candidates)
        or upstream.get("execution_completed") is not True
        or upstream.get("projection_only") is not False
        or upstream.get("scientifically_validated") is not False
        or upstream.get("product_qualified") is not False
        or upstream.get("claim_safe") is not False
    ):
        raise EngineV2ProductShadowError(
            "upstream execution profile, candidates, or authority is invalid"
        )
    required = {
        "schema_id",
        "profile_id",
        "profile_sha256",
        "stage0_admission_receipt_sha256",
        "candidate_count",
        "candidate_source_sha256s",
        "upstream_evidence_schema_id",
        "upstream_evidence_receipt_sha256",
        "execution_already_completed",
        "projection_only",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }
    if set(source) != required:
        raise EngineV2ProductShadowError(
            "source_evidence_document fields are not exact"
        )
    _require_text(source.get("schema_id"), name="source evidence schema_id")
    if (
        source.get("profile_id") != profile_id
        or source.get("profile_sha256") != profile_sha256
        or source.get("stage0_admission_receipt_sha256")
        != stage0_admission_receipt_sha256
        or source.get("candidate_count") != len(candidates)
        or source.get("execution_already_completed") is not True
        or source.get("projection_only") is not True
        or source.get("scientifically_validated") is not False
        or source.get("product_qualified") is not False
        or source.get("claim_safe") is not False
        or source.get("upstream_evidence_schema_id") != upstream_schema_id
        or source.get("upstream_evidence_receipt_sha256") != upstream_receipt_sha256
    ):
        raise EngineV2ProductShadowError(
            "source evidence profile, denominator, or authority is invalid"
        )
    candidate_sha256s = source.get("candidate_source_sha256s")
    if candidate_sha256s != expected_candidate_sha256s:
        raise EngineV2ProductShadowError(
            "source evidence candidate bindings are cross-wired"
        )
    claimed = _require_digest(
        source.get("receipt_sha256"),
        name="source evidence receipt_sha256",
    )
    projection = dict(source)
    projection.pop("receipt_sha256")
    if _sha256(projection) != claimed:
        raise EngineV2ProductShadowError(
            "source_evidence_document self-hash is invalid"
        )
    return claimed


def project_engine_v2_product_shadow_evidence(
    *,
    stage0_admission: object,
    profile_document: Mapping[str, object],
    upstream_evidence_document: Mapping[str, object],
    source_evidence_document: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Project receipt-bound completed evidence without running or routing it."""

    if not isinstance(candidates, Sequence) or isinstance(
        candidates,
        (str, bytes, bytearray),
    ):
        raise EngineV2ProductShadowError("candidates must be a sequence")
    if not 1 <= len(candidates) <= _MAX_COLLECTION_LENGTH:
        raise EngineV2ProductShadowError("candidate count is invalid")
    stage0_admission_receipt_sha256 = _verified_stage0_admission_receipt(
        stage0_admission
    )
    normalized_profile_id, normalized_profile_sha256 = _verified_profile_identity(
        profile_document,
        stage0_admission=stage0_admission,
    )
    normalized_source_sha256 = _verified_source_identity(
        source_evidence_document,
        profile_id=normalized_profile_id,
        profile_sha256=normalized_profile_sha256,
        candidates=candidates,
        upstream_evidence_document=upstream_evidence_document,
        stage0_admission_receipt_sha256=stage0_admission_receipt_sha256,
    )
    projected_candidates = [
        _project_candidate(candidate, profile_id=normalized_profile_id)
        for candidate in candidates
    ]
    proposal_indices = [
        candidate["proposal_lineage"]["proposal_index"]
        for candidate in projected_candidates
    ]
    if len(proposal_indices) != len(set(proposal_indices)):
        raise EngineV2ProductShadowError("proposal indices must be unique")
    document: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_EVIDENCE_SCHEMA_ID,
        "policy": engine_v2_product_shadow_policy(),
        "profile_id": normalized_profile_id,
        "profile_sha256": normalized_profile_sha256,
        "stage0_admission_receipt_sha256": stage0_admission_receipt_sha256,
        "source_evidence_receipt_sha256": normalized_source_sha256,
        "candidate_count": len(projected_candidates),
        "candidates": projected_candidates,
        "consumer_scope": "operator_only",
        "projection_only": True,
        "execution_performed": False,
        "source_schemas_preserved_unmodified": True,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    _assert_projection_safe(document)
    document["receipt_sha256"] = _sha256(document)
    return validate_engine_v2_product_shadow_evidence(
        document,
        stage0_admission=stage0_admission,
    )


def _validate_projected_candidate(
    value: object,
    *,
    profile_id: str,
) -> dict[str, object]:
    candidate = _require_mapping(value, name="projected candidate")
    required_keys = {
        "schema_id",
        "profile_id",
        "status",
        "proposal_lineage",
        "scoring_terms",
        "pose_validity",
        "refinement_receipt",
        "failure_reason",
        "baseline_disagreement",
        "abstention",
        "sensitive_source_fields_redacted",
        "redacted_sensitive_field_count",
        "receipt_sha256",
    }
    if set(candidate) != required_keys:
        raise EngineV2ProductShadowError("projected candidate fields are not exact")
    if candidate["schema_id"] != ENGINE_V2_PRODUCT_SHADOW_CANDIDATE_SCHEMA_ID:
        raise EngineV2ProductShadowError("projected candidate schema is unsupported")
    if candidate["profile_id"] != profile_id:
        raise EngineV2ProductShadowError("projected candidate profile is cross-wired")
    status = candidate["status"]
    if status not in {"success", "failure"}:
        raise EngineV2ProductShadowError("projected candidate status is unsupported")
    lineage = _validated_lineage(candidate["proposal_lineage"], status=status)
    validity = _validated_pose_validity(candidate["pose_validity"])
    disagreement = _validated_projected_baseline_disagreement(
        candidate["baseline_disagreement"]
    )
    abstention = _validated_reason_decision(
        candidate["abstention"],
        name="abstention",
        decision_field="abstained",
        allowed_reasons=_ALLOWED_ABSTENTION_REASONS,
    )
    failure_reason = (
        _require_text(
            candidate["failure_reason"],
            name="failure_reason",
            allow_empty=True,
        )
        if status == "success"
        else _require_failure_code(
            candidate["failure_reason"],
            name="failure_reason",
        )
    )
    if status == "success":
        if validity["complete"] is not True:
            raise EngineV2ProductShadowError(
                "successful projected candidate requires complete pose validity evidence"
            )
        scoring_terms = _validated_scorer_terms(candidate["scoring_terms"])
        if (
            scoring_terms["proposal_fingerprint_sha256"]
            != lineage["proposal_fingerprint_sha256"]
        ):
            raise EngineV2ProductShadowError(
                "projected scoring terms and lineage are cross-wired"
            )
        refinement = _require_mapping(
            candidate["refinement_receipt"],
            name="projected refinement receipt",
        )
        if set(refinement) != {
            "source_receipt_sha256",
            "source_receipt_self_hash_verified_before_projection",
        }:
            raise EngineV2ProductShadowError(
                "projected refinement receipt fields are not exact"
            )
        _require_digest(
            refinement["source_receipt_sha256"],
            name="projected refinement source_receipt_sha256",
        )
        if (
            refinement["source_receipt_self_hash_verified_before_projection"]
            is not True
        ):
            raise EngineV2ProductShadowError(
                "projected refinement receipt was not validated"
            )
        if failure_reason:
            raise EngineV2ProductShadowError(
                "successful projected candidate has a failure reason"
            )
    else:
        if (
            validity["complete"] is not False
            or any(validity["evaluated_checks"].values())
            or "candidate_execution_failed" not in validity["blockers"]
        ):
            raise EngineV2ProductShadowError(
                "failed projected candidate pose validity evidence is inconsistent"
            )
        if (
            candidate["scoring_terms"] is not None
            or candidate["refinement_receipt"] is not None
        ):
            raise EngineV2ProductShadowError(
                "failed projected candidate fabricates scientific evidence"
            )
    if (status == "failure" or not validity["valid"]) and not abstention["abstained"]:
        raise EngineV2ProductShadowError(
            "failed or invalid projected candidate must abstain"
        )
    baseline_reason_present = (
        "baseline_evidence_incomplete" in abstention["reason_codes"]
    )
    if baseline_reason_present is not (disagreement["available"] is False):
        raise EngineV2ProductShadowError(
            "baseline availability and candidate abstention are inconsistent"
        )
    if type(candidate["sensitive_source_fields_redacted"]) is not bool:
        raise EngineV2ProductShadowError("redaction disposition is invalid")
    redacted_count = candidate["redacted_sensitive_field_count"]
    if type(redacted_count) is not int or not 0 <= redacted_count < 1_000_000:
        raise EngineV2ProductShadowError("redacted field count is invalid")
    if candidate["sensitive_source_fields_redacted"] != (redacted_count > 0):
        raise EngineV2ProductShadowError("redaction disposition is inconsistent")
    claimed_receipt = _require_digest(
        candidate["receipt_sha256"],
        name="projected candidate receipt_sha256",
    )
    unsigned = dict(candidate)
    unsigned.pop("receipt_sha256")
    if _sha256(unsigned) != claimed_receipt:
        raise EngineV2ProductShadowError(
            "projected candidate receipt self-hash is invalid"
        )
    return candidate


def validate_engine_v2_product_shadow_evidence(
    value: object,
    *,
    stage0_admission: object,
) -> dict[str, object]:
    """Validate and return a detached operator-shadow evidence document."""

    document = _require_mapping(value, name="product shadow evidence")
    _assert_projection_safe(document)
    required_keys = {
        "schema_id",
        "policy",
        "profile_id",
        "profile_sha256",
        "stage0_admission_receipt_sha256",
        "source_evidence_receipt_sha256",
        "candidate_count",
        "candidates",
        "consumer_scope",
        "projection_only",
        "execution_performed",
        "source_schemas_preserved_unmodified",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }
    if set(document) != required_keys:
        raise EngineV2ProductShadowError("product shadow evidence fields are not exact")
    if document["schema_id"] != ENGINE_V2_PRODUCT_SHADOW_EVIDENCE_SCHEMA_ID:
        raise EngineV2ProductShadowError(
            "product shadow evidence schema is unsupported"
        )
    if document["policy"] != engine_v2_product_shadow_policy():
        raise EngineV2ProductShadowError(
            "product shadow permissions or policy were changed"
        )
    profile_id = _require_text(document["profile_id"], name="profile_id")
    profile_sha256 = _require_digest(document["profile_sha256"], name="profile_sha256")
    admission_receipt_sha256 = _verified_stage0_admission_receipt(stage0_admission)
    if document["stage0_admission_receipt_sha256"] != admission_receipt_sha256:
        raise EngineV2ProductShadowError(
            "product shadow Stage 0 admission is cross-wired"
        )
    if profile_sha256 not in _trusted_pipeline_profile_sha256s(stage0_admission).get(
        profile_id, frozenset()
    ):
        raise EngineV2ProductShadowError(
            "product shadow profile is outside the Stage 0 registry"
        )
    _require_digest(
        document["source_evidence_receipt_sha256"],
        name="source_evidence_receipt_sha256",
    )
    if document["consumer_scope"] != "operator_only":
        raise EngineV2ProductShadowError(
            "product shadow consumer scope is not operator-only"
        )
    frozen_false = (
        "execution_performed",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
    )
    if document["projection_only"] is not True or any(
        document[name] is not False for name in frozen_false
    ):
        raise EngineV2ProductShadowError(
            "product shadow execution or claim boundary was changed"
        )
    if document["source_schemas_preserved_unmodified"] is not True:
        raise EngineV2ProductShadowError(
            "source schema preservation disposition was changed"
        )
    candidates = document["candidates"]
    if (
        not isinstance(candidates, list)
        or not 1 <= len(candidates) <= _MAX_COLLECTION_LENGTH
    ):
        raise EngineV2ProductShadowError("projected candidate collection is invalid")
    if document["candidate_count"] != len(candidates):
        raise EngineV2ProductShadowError("projected candidate count is inconsistent")
    validated_candidates = [
        _validate_projected_candidate(candidate, profile_id=profile_id)
        for candidate in candidates
    ]
    proposal_indices = [
        candidate["proposal_lineage"]["proposal_index"]
        for candidate in validated_candidates
    ]
    if len(proposal_indices) != len(set(proposal_indices)):
        raise EngineV2ProductShadowError("projected proposal indices are duplicated")
    claimed_receipt = _require_digest(
        document["receipt_sha256"],
        name="product shadow evidence receipt_sha256",
    )
    unsigned = dict(document)
    unsigned.pop("receipt_sha256")
    if _sha256(unsigned) != claimed_receipt:
        raise EngineV2ProductShadowError(
            "product shadow evidence receipt self-hash is invalid"
        )
    return json.loads(_canonical_bytes(document).decode("ascii"))


__all__ = [
    "ENGINE_V2_PRODUCT_SHADOW_CANDIDATE_SCHEMA_ID",
    "ENGINE_V2_PRODUCT_SHADOW_EVIDENCE_SCHEMA_ID",
    "ENGINE_V2_PRODUCT_SHADOW_PERMISSIONS",
    "ENGINE_V2_PRODUCT_SHADOW_POLICY_ID",
    "ENGINE_V2_PRODUCT_SHADOW_POLICY_SCHEMA_ID",
    "ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID",
    "EngineV2ProductShadowError",
    "engine_v2_product_shadow_policy",
    "project_engine_v2_product_shadow_evidence",
    "validate_engine_v2_product_shadow_evidence",
]
