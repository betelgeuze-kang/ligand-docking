"""Job-bound H-bond evidence carried inside an ``EvidenceBundle``.

The scientific evaluator remains job-agnostic.  This envelope binds its full
candidate evidence to one durable job, both request fingerprints, and the
exact runner result file so evidence cannot be replayed across jobs.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import math
import re
from typing import Any

from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.output_schema import InteractionReport
from betelgeuze_ai_md.contracts.serialization import sha256_payload, to_plain


JOB_SCOPED_HBOND_EVIDENCE_SCHEMA_VERSION = "job_scoped_hbond_evidence_v1"
HBOND_EVIDENCE_SCHEMA_VERSION = "hbond_evidence_v1"
HBOND_EVIDENCE_SCOPE = "job_hbond_candidate_set"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HBOND_ROLES = {"donor", "acceptor"}


def _text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContractValidationError(f"{field_name} is required")
    return text


def _sha256(value: Any, field_name: str) -> str:
    digest = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(digest) is None:
        raise ContractValidationError(
            f"{field_name} must be a 64-character hexadecimal SHA-256"
        )
    return digest


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finite_float(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if not math.isfinite(numeric):
        raise ContractValidationError(f"{field_name} must be finite")
    return numeric


def _nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractValidationError(f"{field_name} must be an integer")
    numeric = value
    if numeric < 0:
        raise ContractValidationError(f"{field_name} must be non-negative")
    return numeric


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractValidationError(
            "job-scoped H-bond evidence contains a non-finite number"
        )
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _validate_hbond_payload(payload: dict[str, Any], *, candidate_id: str) -> None:
    if payload.get("schema_version") != HBOND_EVIDENCE_SCHEMA_VERSION:
        raise ContractValidationError(
            f"H-bond evidence schema mismatch for candidate {candidate_id}"
        )
    _text(payload.get("status"), f"H-bond status for candidate {candidate_id}")
    if not isinstance(payload.get("claim_safe"), bool):
        raise ContractValidationError(
            f"H-bond claim_safe must be boolean for candidate {candidate_id}"
        )
    site_count = _nonnegative_int(
        payload.get("site_count"), f"H-bond site_count for candidate {candidate_id}"
    )
    donor_count = _nonnegative_int(
        payload.get("donor_site_count"),
        f"H-bond donor_site_count for candidate {candidate_id}",
    )
    acceptor_count = _nonnegative_int(
        payload.get("acceptor_site_count"),
        f"H-bond acceptor_site_count for candidate {candidate_id}",
    )
    if donor_count + acceptor_count != site_count:
        raise ContractValidationError(
            f"H-bond role counts mismatch for candidate {candidate_id}"
        )
    reported_distance_pass_count = _nonnegative_int(
        payload.get("distance_pass_count"),
        f"H-bond distance_pass_count for candidate {candidate_id}",
    )
    reported_angle_pass_count = _nonnegative_int(
        payload.get("angle_pass_count"),
        f"H-bond angle_pass_count for candidate {candidate_id}",
    )
    reported_unsatisfied_donor_count = _nonnegative_int(
        payload.get("unsatisfied_donor_count"),
        f"H-bond unsatisfied_donor_count for candidate {candidate_id}",
    )
    reported_unsatisfied_acceptor_count = _nonnegative_int(
        payload.get("unsatisfied_acceptor_count"),
        f"H-bond unsatisfied_acceptor_count for candidate {candidate_id}",
    )
    confidence = _finite_float(
        payload.get("hbond_confidence"),
        f"H-bond confidence for candidate {candidate_id}",
    )
    if not 0.0 <= confidence <= 1.0:
        raise ContractValidationError(
            f"H-bond confidence must be in [0, 1] for candidate {candidate_id}"
        )
    pairs = _as_list(payload.get("donor_acceptor_pairs"))
    if len(pairs) != site_count:
        raise ContractValidationError(
            f"H-bond pair count mismatch for candidate {candidate_id}"
        )
    seen_sites: set[int] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ContractValidationError(
                f"H-bond pair must be an object for candidate {candidate_id}"
            )
        site_index = _nonnegative_int(
            pair.get("site_index"),
            f"H-bond site_index for candidate {candidate_id}",
        )
        if site_index in seen_sites:
            raise ContractValidationError(
                f"duplicate H-bond site_index for candidate {candidate_id}"
            )
        seen_sites.add(site_index)
        _nonnegative_int(
            pair.get("atom_idx"), f"H-bond atom_idx for candidate {candidate_id}"
        )
        _text(pair.get("element"), f"H-bond element for candidate {candidate_id}")
        if str(pair.get("role") or "") not in _HBOND_ROLES:
            raise ContractValidationError(
                f"H-bond role is invalid for candidate {candidate_id}"
            )
        for flag in ("distance_pass", "angle_pass"):
            if not isinstance(pair.get(flag), bool):
                raise ContractValidationError(
                    f"H-bond {flag} must be boolean for candidate {candidate_id}"
                )
        distance = pair.get("nearest_distance")
        if distance is not None and _finite_float(
            distance, f"H-bond nearest_distance for candidate {candidate_id}"
        ) < 0.0:
            raise ContractValidationError(
                f"H-bond distance must be non-negative for candidate {candidate_id}"
            )
        angle_score = _finite_float(
            pair.get("angle_score"),
            f"H-bond angle_score for candidate {candidate_id}",
        )
        if not 0.0 <= angle_score <= 1.0:
            raise ContractValidationError(
                f"H-bond angle_score must be in [0, 1] for candidate {candidate_id}"
            )
    if seen_sites != set(range(site_count)):
        raise ContractValidationError(
            f"H-bond site indexes are not contiguous for candidate {candidate_id}"
        )
    if donor_count != sum(pair.get("role") == "donor" for pair in pairs):
        raise ContractValidationError(
            f"H-bond donor count contradicts pairs for candidate {candidate_id}"
        )
    if acceptor_count != sum(pair.get("role") == "acceptor" for pair in pairs):
        raise ContractValidationError(
            f"H-bond acceptor count contradicts pairs for candidate {candidate_id}"
        )
    from betelgeuze_engine.interactions.hbond_evidence import (
        HBOND_CLAIM_SAFE_CONFIDENCE_MIN,
        HBOND_EVIDENCE_STATUSES,
        HbondEvidence,
    )

    field_names = {item.name for item in fields(HbondEvidence)}
    missing_fields = sorted(field_names - set(payload))
    if missing_fields:
        raise ContractValidationError(
            f"full H-bond evaluator payload is missing fields for candidate {candidate_id}: "
            f"{missing_fields}"
        )
    try:
        evaluator_evidence = HbondEvidence(
            **{key: payload[key] for key in field_names}
        )
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"H-bond evaluator payload is invalid for candidate {candidate_id}"
        ) from exc
    status = str(payload.get("status") or "")
    if status not in HBOND_EVIDENCE_STATUSES | {"error"}:
        raise ContractValidationError(
            f"H-bond evidence status is unsupported for candidate {candidate_id}"
        )
    if status in HBOND_EVIDENCE_STATUSES and not evaluator_evidence.schema_ready():
        raise ContractValidationError(
            f"H-bond evaluator schema is not ready for candidate {candidate_id}"
        )
    distance_pass_count = sum(
        pair.get("distance_pass") is True for pair in pairs
    )
    angle_pass_count = sum(pair.get("angle_pass") is True for pair in pairs)
    if reported_distance_pass_count != distance_pass_count:
        raise ContractValidationError(
            f"H-bond distance pass count contradicts pairs for candidate {candidate_id}"
        )
    if reported_angle_pass_count != angle_pass_count:
        raise ContractValidationError(
            f"H-bond angle pass count contradicts pairs for candidate {candidate_id}"
        )
    denominator = max(site_count, 1)
    expected_distance_fraction = float(distance_pass_count / denominator)
    expected_angle_fraction = float(angle_pass_count / denominator)
    if not math.isclose(
        _finite_float(
            payload.get("distance_pass_fraction"),
            f"H-bond distance pass fraction for candidate {candidate_id}",
        ),
        expected_distance_fraction,
        abs_tol=1e-12,
    ):
        raise ContractValidationError(
            f"H-bond distance pass fraction contradicts pairs for candidate {candidate_id}"
        )
    if not math.isclose(
        _finite_float(
            payload.get("angle_pass_fraction"),
            f"H-bond angle pass fraction for candidate {candidate_id}",
        ),
        expected_angle_fraction,
        abs_tol=1e-12,
    ):
        raise ContractValidationError(
            f"H-bond angle pass fraction contradicts pairs for candidate {candidate_id}"
        )
    expected_unsatisfied_donor = sum(
        pair.get("role") == "donor" and pair.get("distance_pass") is not True
        for pair in pairs
    )
    expected_unsatisfied_acceptor = sum(
        pair.get("role") == "acceptor" and pair.get("distance_pass") is not True
        for pair in pairs
    )
    if reported_unsatisfied_donor_count != expected_unsatisfied_donor:
        raise ContractValidationError(
            f"H-bond unsatisfied donor count contradicts pairs for candidate {candidate_id}"
        )
    if (
        reported_unsatisfied_acceptor_count
        != expected_unsatisfied_acceptor
    ):
        raise ContractValidationError(
            f"H-bond unsatisfied acceptor count contradicts pairs for candidate {candidate_id}"
        )
    if status in HBOND_EVIDENCE_STATUSES:
        thresholds = _as_dict(payload.get("thresholds"))
        min_distance = _finite_float(
            thresholds.get("min_distance"),
            f"H-bond min distance for candidate {candidate_id}",
        )
        max_distance = _finite_float(
            thresholds.get("max_distance"),
            f"H-bond max distance for candidate {candidate_id}",
        )
        overanchor_distance = _finite_float(
            thresholds.get("overanchor_distance"),
            f"H-bond overanchor distance for candidate {candidate_id}",
        )
        angle_threshold = _finite_float(
            thresholds.get("angle_threshold"),
            f"H-bond angle threshold for candidate {candidate_id}",
        )
        for pair in pairs:
            distance = pair.get("nearest_distance")
            expected_distance_pass = bool(
                distance is not None
                and min_distance <= float(distance) <= max_distance
            )
            if pair.get("distance_pass") is not expected_distance_pass:
                raise ContractValidationError(
                    f"H-bond pair distance flag contradicts threshold for candidate {candidate_id}"
                )
            expected_angle_pass = bool(float(pair.get("angle_score")) >= angle_threshold)
            if pair.get("angle_pass") is not expected_angle_pass:
                raise ContractValidationError(
                    f"H-bond pair angle flag contradicts threshold for candidate {candidate_id}"
                )
        expected_overanchoring = any(
            pair.get("nearest_distance") is not None
            and float(pair.get("nearest_distance")) < overanchor_distance
            for pair in pairs
        )
        if payload.get("overanchoring_flag") is not expected_overanchoring:
            raise ContractValidationError(
                f"H-bond overanchoring flag contradicts pairs for candidate {candidate_id}"
            )
        if status != "invalid_smiles":
            protein_present = bool(
                payload.get("geometry_evaluated") is True
                or any(pair.get("nearest_distance") is not None for pair in pairs)
                or str(payload.get("blocked_reason") or "")
                != "pose_geometry_missing"
            )
            expected_missing_anchor = bool(
                site_count > 0
                and protein_present
                and distance_pass_count == 0
            )
            if payload.get("missing_expected_anchor_flag") is not expected_missing_anchor:
                raise ContractValidationError(
                    f"H-bond missing-anchor flag contradicts pairs for candidate {candidate_id}"
                )
        delta_abs = _finite_float(
            payload.get("delta_backmap"),
            f"H-bond delta_backmap for candidate {candidate_id}",
        )
        if delta_abs < 0.0:
            raise ContractValidationError(
                f"H-bond delta_backmap must be non-negative for candidate {candidate_id}"
            )
        delta_max = _finite_float(
            payload.get("delta_backmap_max"),
            f"H-bond delta_backmap_max for candidate {candidate_id}",
        )
        threshold_delta_max = _finite_float(
            thresholds.get("delta_backmap_max"),
            f"H-bond threshold delta_backmap_max for candidate {candidate_id}",
        )
        if not math.isclose(delta_max, threshold_delta_max, abs_tol=1e-12):
            raise ContractValidationError(
                f"H-bond delta_backmap_max contradicts thresholds for candidate {candidate_id}"
            )
        delta_evaluated = payload.get("delta_backmap_evaluated") is True
        if not delta_evaluated and not math.isclose(delta_abs, 0.0, abs_tol=1e-12):
            raise ContractValidationError(
                f"H-bond unevaluated delta_backmap must be zero for candidate {candidate_id}"
            )
        expected_delta_yellow_band = bool(delta_evaluated and delta_abs > delta_max)
        if payload.get("delta_backmap_yellow_band") is not expected_delta_yellow_band:
            raise ContractValidationError(
                f"H-bond delta yellow-band flag contradicts thresholds for candidate {candidate_id}"
            )
        expected_confidence = float(
            0.65 * expected_distance_fraction + 0.35 * expected_angle_fraction
        )
        if delta_evaluated:
            delta_penalty = min(0.75, 0.5 * (delta_abs / max(delta_max, 1e-6)))
            expected_confidence = float(expected_confidence * (1.0 - delta_penalty))
        if not math.isclose(confidence, expected_confidence, abs_tol=1e-12):
            raise ContractValidationError(
                f"H-bond confidence contradicts pairs for candidate {candidate_id}"
            )
    if payload.get("claim_safe") is True:
        thresholds = _as_dict(payload.get("thresholds"))
        confidence_min = _finite_float(
            thresholds.get("claim_safe_confidence_min"),
            f"H-bond claim-safe threshold for candidate {candidate_id}",
        )
        if not math.isclose(
            confidence_min,
            HBOND_CLAIM_SAFE_CONFIDENCE_MIN,
            abs_tol=1e-12,
        ):
            raise ContractValidationError(
                f"H-bond claim-safe threshold is non-canonical for candidate {candidate_id}"
            )
        onsps_metadata = _as_dict(payload.get("onsps_backmap_metadata"))
        onsps_status = str(onsps_metadata.get("backmap_status") or "")
        onsps_required = bool(
            onsps_metadata
            and onsps_status not in {"not_evaluated", "no_onsps_sites"}
        )
        onsps_claim_safe = bool(
            not onsps_required
            or (
                onsps_metadata.get("claim_safe") is True
                and not str(onsps_metadata.get("blocked_reason") or "")
            )
        )
        claim_safe_ready = bool(
            status == "pass"
            and payload.get("geometry_evaluated") is True
            and payload.get("geometry_complete") is True
            and reported_distance_pass_count >= 1
            and confidence >= HBOND_CLAIM_SAFE_CONFIDENCE_MIN
            and not str(payload.get("blocked_reason") or "")
            and payload.get("overanchoring_flag") is False
            and payload.get("missing_expected_anchor_flag") is False
            and payload.get("delta_backmap_yellow_band") is False
            and onsps_claim_safe
        )
        if not claim_safe_ready:
            raise ContractValidationError(
                f"H-bond claim-safe invariants fail for candidate {candidate_id}"
            )


def _candidate_record(row: dict[str, Any]) -> dict[str, Any] | None:
    evidence = _as_dict(row.get("hbond_evidence"))
    if not evidence:
        return None
    candidate_id = _text(row.get("queue_id"), "H-bond candidate queue_id")
    safe_evidence = _json_safe(evidence)
    _validate_hbond_payload(safe_evidence, candidate_id=candidate_id)
    unsigned = {
        "candidate_id": candidate_id,
        "target": str(row.get("target") or "unknown").strip() or "unknown",
        "ligand_id": str(row.get("ligand_id") or "ligand").strip() or "ligand",
        "ligand_smiles_sha256": sha256_payload(
            {"ligand_smiles": str(row.get("ligand_smiles") or "")}
        ),
        "hbond_evidence": safe_evidence,
    }
    return {**unsigned, "candidate_evidence_sha256": sha256_payload(unsigned)}


def _scope_payload(
    *,
    job_id: str,
    admission_request_sha256: str,
    execution_request_sha256: str,
    result_file_sha256: str,
    aggregate_summary_sha256: str,
    candidate_evidence_sha256: str,
    candidate_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": JOB_SCOPED_HBOND_EVIDENCE_SCHEMA_VERSION,
        "evidence_scope": HBOND_EVIDENCE_SCOPE,
        "job_id": job_id,
        "admission_request_sha256": admission_request_sha256,
        "execution_request_sha256": execution_request_sha256,
        "result_file_sha256": result_file_sha256,
        "aggregate_summary_sha256": aggregate_summary_sha256,
        "candidate_evidence_sha256": candidate_evidence_sha256,
        "candidate_count": candidate_count,
    }


@dataclass(frozen=True)
class JobScopedHbondEvidence:
    job_id: str
    admission_request_sha256: str
    execution_request_sha256: str
    result_file_sha256: str
    aggregate_summary: dict[str, Any]
    candidates: list[dict[str, Any]]
    aggregate_summary_sha256: str
    candidate_evidence_sha256: str
    candidate_count: int
    scope_sha256: str
    schema_version: str = JOB_SCOPED_HBOND_EVIDENCE_SCHEMA_VERSION
    evidence_scope: str = HBOND_EVIDENCE_SCOPE

    def __post_init__(self) -> None:
        if self.schema_version != JOB_SCOPED_HBOND_EVIDENCE_SCHEMA_VERSION:
            raise ContractValidationError("job-scoped H-bond schema mismatch")
        if self.evidence_scope != HBOND_EVIDENCE_SCOPE:
            raise ContractValidationError("job-scoped H-bond evidence scope mismatch")
        job_id = _text(self.job_id, "job-scoped H-bond job_id")
        admission_hash = _sha256(
            self.admission_request_sha256,
            "job-scoped H-bond admission_request_sha256",
        )
        execution_hash = _sha256(
            self.execution_request_sha256,
            "job-scoped H-bond execution_request_sha256",
        )
        result_hash = _sha256(
            self.result_file_sha256, "job-scoped H-bond result_file_sha256"
        )
        aggregate_hash = _sha256(
            self.aggregate_summary_sha256,
            "job-scoped H-bond aggregate_summary_sha256",
        )
        candidate_hash = _sha256(
            self.candidate_evidence_sha256,
            "job-scoped H-bond candidate_evidence_sha256",
        )
        scope_hash = _sha256(self.scope_sha256, "job-scoped H-bond scope_sha256")
        if not isinstance(self.aggregate_summary, dict):
            raise ContractValidationError("job-scoped H-bond aggregate_summary must be an object")
        if self.aggregate_summary.get("schema_version") != HBOND_EVIDENCE_SCHEMA_VERSION:
            raise ContractValidationError("job-scoped H-bond aggregate summary schema mismatch")
        if not isinstance(self.candidates, list) or not self.candidates:
            raise ContractValidationError("job-scoped H-bond candidates are required")
        candidate_count = _nonnegative_int(
            self.candidate_count, "job-scoped H-bond candidate_count"
        )
        if candidate_count != len(self.candidates):
            raise ContractValidationError("job-scoped H-bond candidate_count mismatch")
        candidate_ids: set[str] = set()
        expected_candidate_fields = {
            "candidate_id",
            "target",
            "ligand_id",
            "ligand_smiles_sha256",
            "hbond_evidence",
            "candidate_evidence_sha256",
        }
        for candidate in self.candidates:
            if not isinstance(candidate, dict):
                raise ContractValidationError("job-scoped H-bond candidate must be an object")
            if set(candidate) != expected_candidate_fields:
                raise ContractValidationError(
                    "job-scoped H-bond candidate fields mismatch"
                )
            candidate_id = _text(candidate.get("candidate_id"), "H-bond candidate_id")
            if candidate_id in candidate_ids:
                raise ContractValidationError("job-scoped H-bond candidate IDs must be unique")
            candidate_ids.add(candidate_id)
            _text(candidate.get("target"), f"H-bond target for {candidate_id}")
            _text(candidate.get("ligand_id"), f"H-bond ligand_id for {candidate_id}")
            _sha256(
                candidate.get("ligand_smiles_sha256"),
                f"H-bond ligand_smiles_sha256 for {candidate_id}",
            )
            evidence = _as_dict(candidate.get("hbond_evidence"))
            _validate_hbond_payload(evidence, candidate_id=candidate_id)
            observed_candidate_hash = _sha256(
                candidate.get("candidate_evidence_sha256"),
                f"candidate_evidence_sha256 for {candidate_id}",
            )
            unsigned = {
                key: value
                for key, value in candidate.items()
                if key != "candidate_evidence_sha256"
            }
            if observed_candidate_hash != sha256_payload(unsigned):
                raise ContractValidationError(
                    f"H-bond candidate evidence hash mismatch for {candidate_id}"
                )
        aggregate_status = _text(
            self.aggregate_summary.get("status"),
            "job-scoped H-bond aggregate status",
        )
        if aggregate_status not in {"pass", "review", "not_assessed"}:
            raise ContractValidationError(
                "job-scoped H-bond aggregate status is unsupported"
            )
        evaluated_row_count = _nonnegative_int(
            self.aggregate_summary.get("evaluated_row_count", candidate_count),
            "job-scoped H-bond evaluated_row_count",
        )
        if candidate_count > evaluated_row_count:
            raise ContractValidationError(
                "job-scoped H-bond candidate count exceeds evaluated rows"
            )
        claim_safe_row_count = _nonnegative_int(
            self.aggregate_summary.get(
                "claim_safe_row_count",
                sum(
                    candidate.get("hbond_evidence", {}).get("claim_safe") is True
                    for candidate in self.candidates
                ),
            ),
            "job-scoped H-bond claim_safe_row_count",
        )
        candidate_claim_safe_count = sum(
            candidate.get("hbond_evidence", {}).get("claim_safe") is True
            for candidate in self.candidates
        )
        if claim_safe_row_count > evaluated_row_count:
            raise ContractValidationError(
                "job-scoped H-bond claim-safe count exceeds evaluated rows"
            )
        if claim_safe_row_count < candidate_claim_safe_count:
            raise ContractValidationError(
                "job-scoped H-bond claim-safe count contradicts candidates"
            )
        blocked_row_count = _nonnegative_int(
            self.aggregate_summary.get(
                "blocked_row_count",
                evaluated_row_count - claim_safe_row_count,
            ),
            "job-scoped H-bond blocked_row_count",
        )
        if blocked_row_count != evaluated_row_count - claim_safe_row_count:
            raise ContractValidationError(
                "job-scoped H-bond blocked count contradicts evaluated rows"
            )
        claim_safe_rate = _finite_float(
            self.aggregate_summary.get(
                "claim_safe_rate",
                claim_safe_row_count / max(evaluated_row_count, 1),
            ),
            "job-scoped H-bond claim_safe_rate",
        )
        expected_claim_safe_rate = float(
            claim_safe_row_count / max(evaluated_row_count, 1)
        )
        if not 0.0 <= claim_safe_rate <= 1.0 or not math.isclose(
            claim_safe_rate,
            expected_claim_safe_rate,
            abs_tol=1e-12,
        ):
            raise ContractValidationError(
                "job-scoped H-bond claim-safe rate contradicts counts"
            )
        expected_status = (
            "not_assessed"
            if evaluated_row_count == 0
            else "pass"
            if blocked_row_count == 0
            else "review"
        )
        if aggregate_status != expected_status:
            raise ContractValidationError(
                "job-scoped H-bond aggregate status contradicts counts"
            )
        if "topk_claim_safe_row_count" in self.aggregate_summary:
            topk_claim_safe_row_count = _nonnegative_int(
                self.aggregate_summary.get("topk_claim_safe_row_count"),
                "job-scoped H-bond topk_claim_safe_row_count",
            )
            if topk_claim_safe_row_count != candidate_claim_safe_count:
                raise ContractValidationError(
                    "job-scoped H-bond Top-K claim-safe count contradicts candidates"
                )
        for field_name in (
            "schema_ready_row_count",
            "claim_metadata_schema_ready_row_count",
            "onsps_backmap_metadata_schema_ready_row_count",
            "onsps_backmap_claim_safe_row_count",
            "overanchored_row_count",
            "missing_expected_anchor_row_count",
            "geometry_evaluated_row_count",
            "geometry_complete_row_count",
        ):
            if field_name not in self.aggregate_summary:
                continue
            bounded_count = _nonnegative_int(
                self.aggregate_summary.get(field_name),
                f"job-scoped H-bond {field_name}",
            )
            if bounded_count > evaluated_row_count:
                raise ContractValidationError(
                    f"job-scoped H-bond {field_name} exceeds evaluated rows"
                )
        if "topk_blocked_reason_counts" in self.aggregate_summary:
            observed_reason_counts = self.aggregate_summary.get(
                "topk_blocked_reason_counts"
            )
            if not isinstance(observed_reason_counts, dict):
                raise ContractValidationError(
                    "job-scoped H-bond Top-K blocker counts must be an object"
                )
            normalized_reason_counts: dict[str, int] = {}
            for reason, count in observed_reason_counts.items():
                normalized_reason = _text(
                    reason,
                    "job-scoped H-bond Top-K blocker reason",
                )
                normalized_reason_counts[normalized_reason] = _nonnegative_int(
                    count,
                    f"job-scoped H-bond Top-K blocker count for {normalized_reason}",
                )
            expected_reason_counts: dict[str, int] = {}
            for candidate in self.candidates:
                evidence = candidate.get("hbond_evidence", {})
                if evidence.get("claim_safe") is True:
                    continue
                reason = str(evidence.get("blocked_reason") or "").strip()
                if reason:
                    expected_reason_counts[reason] = (
                        expected_reason_counts.get(reason, 0) + 1
                    )
            if normalized_reason_counts != expected_reason_counts:
                raise ContractValidationError(
                    "job-scoped H-bond Top-K blocker counts contradict candidates"
                )
        if aggregate_hash != sha256_payload(self.aggregate_summary):
            raise ContractValidationError("job-scoped H-bond aggregate summary hash mismatch")
        if candidate_hash != sha256_payload(self.candidates):
            raise ContractValidationError("job-scoped H-bond candidate set hash mismatch")
        expected_scope_hash = sha256_payload(
            _scope_payload(
                job_id=job_id,
                admission_request_sha256=admission_hash,
                execution_request_sha256=execution_hash,
                result_file_sha256=result_hash,
                aggregate_summary_sha256=aggregate_hash,
                candidate_evidence_sha256=candidate_hash,
                candidate_count=candidate_count,
            )
        )
        if scope_hash != expected_scope_hash:
            raise ContractValidationError("job-scoped H-bond scope hash mismatch")
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "admission_request_sha256", admission_hash)
        object.__setattr__(self, "execution_request_sha256", execution_hash)
        object.__setattr__(self, "result_file_sha256", result_hash)
        object.__setattr__(self, "aggregate_summary_sha256", aggregate_hash)
        object.__setattr__(self, "candidate_evidence_sha256", candidate_hash)
        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "scope_sha256", scope_hash)

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        admission_request_sha256: str,
        execution_request_sha256: str,
        result_file_sha256: str,
        aggregate_summary: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> "JobScopedHbondEvidence":
        safe_summary = _json_safe(aggregate_summary)
        safe_candidates = _json_safe(candidates)
        aggregate_hash = sha256_payload(safe_summary)
        candidate_hash = sha256_payload(safe_candidates)
        candidate_count = len(safe_candidates)
        scope_hash = sha256_payload(
            _scope_payload(
                job_id=str(job_id or "").strip(),
                admission_request_sha256=str(admission_request_sha256 or "").lower(),
                execution_request_sha256=str(execution_request_sha256 or "").lower(),
                result_file_sha256=str(result_file_sha256 or "").lower(),
                aggregate_summary_sha256=aggregate_hash,
                candidate_evidence_sha256=candidate_hash,
                candidate_count=candidate_count,
            )
        )
        return cls(
            job_id=job_id,
            admission_request_sha256=admission_request_sha256,
            execution_request_sha256=execution_request_sha256,
            result_file_sha256=result_file_sha256,
            aggregate_summary=safe_summary,
            candidates=safe_candidates,
            aggregate_summary_sha256=aggregate_hash,
            candidate_evidence_sha256=candidate_hash,
            candidate_count=candidate_count,
            scope_sha256=scope_hash,
        )

    def with_request_provenance(
        self,
        *,
        admission_request_sha256: str,
        execution_request_sha256: str,
    ) -> "JobScopedHbondEvidence":
        execution_hash = _sha256(
            execution_request_sha256,
            "job-scoped H-bond execution_request_sha256",
        )
        if execution_hash != self.execution_request_sha256:
            raise ContractValidationError(
                "job-scoped H-bond execution request cannot be rebound"
            )
        return JobScopedHbondEvidence.create(
            job_id=self.job_id,
            admission_request_sha256=admission_request_sha256,
            execution_request_sha256=execution_hash,
            result_file_sha256=self.result_file_sha256,
            aggregate_summary=self.aggregate_summary,
            candidates=self.candidates,
        )

    def to_interaction_report(self) -> InteractionReport:
        from betelgeuze_ai_md.contracts.interaction_adapter import build_interaction_report

        rows: list[dict[str, Any]] = []
        blockers: list[str] = []
        unsatisfied_donor = 0
        unsatisfied_acceptor = 0
        overanchoring = False
        for candidate in self.candidates:
            candidate_id = str(candidate["candidate_id"])
            target = str(candidate.get("target") or "unknown")
            ligand_id = str(candidate.get("ligand_id") or "ligand")
            evidence = _as_dict(candidate.get("hbond_evidence"))
            confidence = float(evidence.get("hbond_confidence") or 0.0)
            blocked_reason = str(evidence.get("blocked_reason") or "")
            if evidence.get("claim_safe") is not True:
                blockers.append(blocked_reason or "hbond_evidence_review_required")
            pairs = _as_list(evidence.get("donor_acceptor_pairs"))
            if not pairs:
                blockers.append(f"hbond_candidate_evidence_missing:{candidate_id}")
            for pair in pairs:
                distance = pair.get("nearest_distance")
                rows.append(
                    {
                        "interaction_id": (
                            f"{candidate_id}:hbond:{int(pair.get('site_index') or 0)}"
                        ),
                        "interaction_type": "hbond",
                        "partners": [
                            f"{target}:protein-nearest",
                            (
                                f"{ligand_id}:atom-{int(pair.get('atom_idx') or 0)}:"
                                f"{str(pair.get('element') or '')}:{str(pair.get('role') or '')}"
                            ),
                        ],
                        "distance": distance,
                        "occupancy": 1.0 if pair.get("distance_pass") is True else 0.0,
                        "confidence": confidence,
                        "role_valid": str(pair.get("role") or "") in _HBOND_ROLES,
                        "claim_blocker": (
                            "" if evidence.get("claim_safe") is True else blocked_reason
                        ),
                    }
                )
            unsatisfied_donor += int(evidence.get("unsatisfied_donor_count") or 0)
            unsatisfied_acceptor += int(evidence.get("unsatisfied_acceptor_count") or 0)
            overanchoring = bool(
                overanchoring or evidence.get("overanchoring_flag") is True
            )
        return build_interaction_report(
            {
                "interactions": rows,
                "over_anchoring_detected": overanchoring,
                "unsatisfied_donor_count": unsatisfied_donor,
                "unsatisfied_acceptor_count": unsatisfied_acceptor,
                "claim_blockers": sorted(set(blockers)),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)


def build_job_scoped_hbond_evidence(
    result_payload: dict[str, Any],
    *,
    job_id: str,
    admission_request_sha256: str,
    execution_request_sha256: str,
    result_file_sha256: str,
) -> JobScopedHbondEvidence | None:
    summary = _as_dict(result_payload.get("hbond_evidence_summary"))
    if not summary:
        return None
    raw_rows = _as_list(
        result_payload.get("hbond_evidence_candidates")
        or result_payload.get("topk")
        or result_payload.get("ranked_shortlist")
    )
    candidates: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        candidate = _candidate_record(row)
        if candidate is None:
            raise ContractValidationError(
                "ranked H-bond candidate is missing full evidence"
            )
        candidates.append(candidate)
    if not candidates:
        raise ContractValidationError(
            "H-bond aggregate summary is present without ranked candidate evidence"
        )
    return JobScopedHbondEvidence.create(
        job_id=job_id,
        admission_request_sha256=admission_request_sha256,
        execution_request_sha256=execution_request_sha256,
        result_file_sha256=result_file_sha256,
        aggregate_summary=summary,
        candidates=candidates,
    )


def require_job_scoped_hbond_matches_result(
    result_payload: dict[str, Any],
    evidence: JobScopedHbondEvidence | dict[str, Any],
) -> JobScopedHbondEvidence:
    scoped = (
        evidence
        if isinstance(evidence, JobScopedHbondEvidence)
        else JobScopedHbondEvidence(**evidence)
    )
    expected = build_job_scoped_hbond_evidence(
        result_payload,
        job_id=scoped.job_id,
        admission_request_sha256=scoped.admission_request_sha256,
        execution_request_sha256=scoped.execution_request_sha256,
        result_file_sha256=scoped.result_file_sha256,
    )
    if expected is None or expected.to_dict() != scoped.to_dict():
        raise ContractValidationError(
            "job-scoped H-bond evidence does not match the bound result payload"
        )
    return scoped


__all__ = [
    "HBOND_EVIDENCE_SCOPE",
    "JOB_SCOPED_HBOND_EVIDENCE_SCHEMA_VERSION",
    "JobScopedHbondEvidence",
    "build_job_scoped_hbond_evidence",
    "require_job_scoped_hbond_matches_result",
]
