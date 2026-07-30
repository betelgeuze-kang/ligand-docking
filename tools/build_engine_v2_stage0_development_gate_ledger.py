#!/usr/bin/env python3
"""Build a compact, authenticated Stage 0 development-gate ledger."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Mapping, Sequence

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    STAGE0_DEVELOPMENT_ANALYSIS_SCHEMA_ID,
    STAGE0_DEVELOPMENT_GATE_DENOMINATORS,
    STAGE0_DEVELOPMENT_GATE_OPERATORS,
    STAGE0_DIAGNOSTIC_CONTRACT_ID,
    STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID,
    STAGE0_FROZEN_THRESHOLD_EVIDENCE_FILE_SHA256,
    STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH,
    STAGE0_FROZEN_THRESHOLD_EVIDENCE_SHA256,
    stage0_authenticated_development_evidence,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_RUNNER_ID,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
)


SCHEMA_ID = "betelgeuze.engine_v2_stage0_development_gate_ledger/1.0.0"
THRESHOLD_SCHEMA_ID = "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
THRESHOLD_DERIVATION_POLICY_ID = "baseline_anchored_operational_gate/1.0.0"

_THRESHOLD_FIELDS = {
    "schema_id",
    "derivation_policy_id",
    "corpus_id",
    "case_count",
    "case_ids_sha256",
    "contains_engineering_smoke",
    "contains_primary_holdout",
    "contains_fresh_internal_blind_holdout",
    "diagnostic_contract_id",
    "sample_size_justification",
    "metric_denominator_policy",
    "preparation_success_case_count",
    "source_reports_sha256",
    "oracle_success_case_count",
    "metrics",
    "paired_baseline_engines",
    "baseline_observed",
    "baseline_noninferiority_margins",
    "runtime_role",
    "scientific_validation_claimed",
    "public_claim_eligible",
    "evidence_sha256",
}
_BLOCKER_ORDER = (
    "preparation_failure",
    "candidate_generation_incomplete",
    "case_execution_failure",
    "no_oracle_candidate",
    "oracle_but_top5_miss",
    "top5_but_top1_miss",
    "top1_invalid",
    "no_valid_candidate",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_frozen_threshold_binding(
    threshold_evidence: Mapping[str, object],
    *,
    threshold_evidence_path: str,
    threshold_evidence_file_sha256: str,
) -> None:
    if (
        threshold_evidence_path != STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH
        or threshold_evidence_file_sha256
        != STAGE0_FROZEN_THRESHOLD_EVIDENCE_FILE_SHA256
        or threshold_evidence.get("evidence_sha256")
        != STAGE0_FROZEN_THRESHOLD_EVIDENCE_SHA256
    ):
        raise ValueError("threshold evidence does not match the frozen authority")


def _finite_rate(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be a numeric rate")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and within [0,1]")
    return number


def _repo_file(repo_root: Path, path: Path, *, name: str) -> tuple[Path, str]:
    root = repo_root.resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError(f"{name} must be an existing repository file") from exc
    if not resolved.is_file():
        raise ValueError(f"{name} must be an existing repository file")
    return resolved, relative


def _canonical_object(path: Path, *, hash_field: str) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    payload = dict(parsed)
    if raw != _canonical_bytes(payload) + b"\n":
        raise ValueError(f"{path.name} is not canonical JSON")
    projection = dict(payload)
    observed = projection.pop(hash_field, None)
    if not _is_sha256(observed) or observed != _sha256_payload(projection):
        raise ValueError(f"{path.name} self-hash is invalid")
    return payload, raw


def _rates_by_engine(value: object, *, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"vina", "gnina"}:
        raise ValueError(f"threshold {name} is invalid")
    return {
        engine: _finite_rate(value[engine], name=f"{name}.{engine}")
        for engine in ("vina", "gnina")
    }


def _validated_thresholds(payload: Mapping[str, object]) -> dict[str, dict[str, object]]:
    if set(payload) != _THRESHOLD_FIELDS:
        raise ValueError("threshold evidence schema fields are invalid")
    if (
        payload.get("schema_id") != THRESHOLD_SCHEMA_ID
        or payload.get("derivation_policy_id") != THRESHOLD_DERIVATION_POLICY_ID
        or payload.get("diagnostic_contract_id") != STAGE0_DIAGNOSTIC_CONTRACT_ID
        or payload.get("contains_engineering_smoke") is not False
        or payload.get("contains_primary_holdout") is not False
        or payload.get("contains_fresh_internal_blind_holdout") is not False
        or payload.get("runtime_role") != "descriptive_only"
        or payload.get("scientific_validation_claimed") is not False
        or payload.get("public_claim_eligible") is not False
        or not isinstance(payload.get("corpus_id"), str)
        or not str(payload.get("corpus_id"))
        or not isinstance(payload.get("sample_size_justification"), str)
        or not str(payload.get("sample_size_justification"))
        or payload.get("paired_baseline_engines") != ["vina", "gnina"]
        or not _is_sha256(payload.get("case_ids_sha256"))
    ):
        raise ValueError("threshold evidence identity or claim boundary is invalid")
    case_count = payload.get("case_count")
    preparation_count = payload.get("preparation_success_case_count")
    oracle_count = payload.get("oracle_success_case_count")
    if (
        type(case_count) is not int
        or case_count < 8
        or type(preparation_count) is not int
        or not 1 <= preparation_count <= case_count
        or type(oracle_count) is not int
        or not 0 <= oracle_count <= preparation_count
    ):
        raise ValueError("threshold evidence case counts are invalid")
    source_reports = payload.get("source_reports_sha256")
    if not isinstance(source_reports, Mapping) or not source_reports or any(
        not isinstance(path, str)
        or not path
        or not _is_sha256(digest)
        for path, digest in source_reports.items()
    ):
        raise ValueError("threshold evidence source reports are invalid")
    if dict(payload.get("metric_denominator_policy", {})) != dict(
        STAGE0_DEVELOPMENT_GATE_DENOMINATORS
    ):
        raise ValueError("threshold metric denominator policy is invalid")
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(
        STAGE0_DEVELOPMENT_GATE_OPERATORS
    ):
        raise ValueError("threshold metric set is invalid")
    normalized: dict[str, dict[str, object]] = {}
    for metric, operator in STAGE0_DEVELOPMENT_GATE_OPERATORS.items():
        row = metrics.get(metric)
        if not isinstance(row, Mapping) or set(row) != {
            "operator",
            "observed_estimate",
            "proposed_threshold",
            "derivation_rule",
        }:
            raise ValueError(f"threshold metric schema is invalid: {metric}")
        if row.get("operator") != operator or not isinstance(
            row.get("derivation_rule"), str
        ) or not str(row.get("derivation_rule")):
            raise ValueError(f"threshold metric identity is invalid: {metric}")
        normalized[metric] = {
            "operator": operator,
            "observed_estimate": _finite_rate(
                row.get("observed_estimate"),
                name=f"{metric}.observed_estimate",
            ),
            "proposed_threshold": _finite_rate(
                row.get("proposed_threshold"),
                name=f"{metric}.proposed_threshold",
            ),
            "derivation_rule": str(row["derivation_rule"]),
        }
    baseline = payload.get("baseline_observed")
    if not isinstance(baseline, Mapping) or set(baseline) != {
        "failure_rates",
        "top1_2a_recovery_rates",
        "top5_2a_recovery_rates",
    }:
        raise ValueError("threshold baseline observation schema is invalid")
    for name in sorted(baseline):
        _rates_by_engine(baseline[name], name=name)
    margins = payload.get("baseline_noninferiority_margins")
    if not isinstance(margins, Mapping) or set(margins) != {
        "top1_2a_recovery_delta",
        "top5_2a_recovery_delta",
    } or any(
        type(value) not in {int, float}
        or not math.isfinite(float(value))
        or not -1.0 <= float(value) <= 1.0
        for value in margins.values()
    ):
        raise ValueError("threshold baseline margins are invalid")
    return normalized


def _validated_source_binding(
    value: Mapping[str, object], *, case_count: int
) -> dict[str, object]:
    binding = dict(value)
    if set(binding) != {
        "development_engine_implementation_sha256",
        "development_runner_id",
        "development_source_receipt_count",
        "development_source_receipts_sha256",
    } or (
        not _is_sha256(binding.get("development_engine_implementation_sha256"))
        or binding.get("development_runner_id") != PUBLIC_REDOCKING_RUNNER_ID
        or binding.get("development_source_receipt_count") != case_count
        or not _is_sha256(binding.get("development_source_receipts_sha256"))
    ):
        raise ValueError("authenticated source-receipt binding is invalid")
    return binding


def _lineage_summary(
    candidates: Sequence[PublicRedockingEngineV2CandidateDiagnostic],
) -> dict[str, object]:
    successful = tuple(candidate for candidate in candidates if candidate.status == "success")
    proposal_modes = Counter(candidate.proposal_mode for candidate in successful)
    native_like_modes = Counter(
        candidate.proposal_mode
        for candidate in successful
        if float(candidate.rmsd_angstrom) <= 2.0
    )
    valid_modes = Counter(
        candidate.proposal_mode
        for candidate in successful
        if candidate.geometric_valid is True and candidate.chemical_valid is True
    )
    refined_modes = Counter(
        candidate.proposal_mode
        for candidate in successful
        if candidate.refinement_receipt_sha256
    )
    ensemble_lineage = [
        {
            "proposal_index": candidate.proposal_index,
            "source_proposal_index": candidate.ensemble_source_proposal_index,
        }
        for candidate in successful
        if candidate.ensemble_source_proposal_index is not None
    ]
    refinement_lineage = [
        {
            "proposal_index": candidate.proposal_index,
            "proposal_mode": candidate.proposal_mode,
            "refinement_receipt_sha256": candidate.refinement_receipt_sha256,
        }
        for candidate in successful
        if candidate.refinement_receipt_sha256
    ]
    return {
        "successful_proposal_mode_counts": dict(sorted(proposal_modes.items())),
        "native_like_proposal_mode_counts": dict(sorted(native_like_modes.items())),
        "valid_proposal_mode_counts": dict(sorted(valid_modes.items())),
        "refined_proposal_mode_counts": dict(sorted(refined_modes.items())),
        "ensemble_lineage_count": len(ensemble_lineage),
        "ensemble_lineage_sha256": _sha256_payload(ensemble_lineage),
        "refinement_lineage_count": len(refinement_lineage),
        "refinement_lineage_sha256": _sha256_payload(refinement_lineage),
    }


def _case_row(result: PublicRedockingCaseResult) -> dict[str, object]:
    diagnostics = result.engine_v2_diagnostics
    if result.engine_id != "engine_v2" or diagnostics is None:
        raise ValueError("development ledger requires typed Engine V2 results")
    candidates = tuple(diagnostics.candidates)
    successful = tuple(candidate for candidate in candidates if candidate.status == "success")
    failed_codes = Counter(
        candidate.error_code for candidate in candidates if candidate.status == "failure"
    )
    failed_checks = Counter(
        check_id
        for candidate in successful
        for check_id in candidate.posebusters_failed_check_ids
    )
    base: dict[str, object] = {
        "case_id": result.case_id,
        "result_status": result.status,
        "result_failure_code": result.failure_code,
        "preparation_status": diagnostics.preparation_status,
        "preparation_failure_code": diagnostics.preparation_failure_code,
        "candidate_budget": diagnostics.candidate_budget,
        "candidate_success_count": len(successful),
        "candidate_failure_count": len(candidates) - len(successful),
        "candidate_failure_code_counts": dict(sorted(failed_codes.items())),
        "posebusters_failed_check_counts": dict(sorted(failed_checks.items())),
        "candidate_diagnostics_sha256": _sha256_payload(
            [candidate.to_dict() for candidate in candidates]
        ),
        "source_result_sha256": _sha256_payload(result.to_dict()),
        "lineage_summary": _lineage_summary(candidates),
    }
    if diagnostics.preparation_status == "failure":
        if result.status != "failure" or candidates or successful:
            raise ValueError("typed preparation failure is internally inconsistent")
        base.update(
            {
                "oracle_2a_recovery": None,
                "top1_2a_recovery": None,
                "top5_2a_recovery": None,
                "top1_proposal_index": None,
                "top1_proposal_mode": None,
                "top1_valid": None,
                "top1_posebusters_failed_check_ids": [],
                "valid_candidate_count": 0,
                "any_valid_candidate": None,
                "selection_stage": "preparation_failure",
                "validity_stage": "not_evaluated",
                "observed_blocker_ids": ["preparation_failure"],
                "causal_diagnosis": "typed_preparation_failure",
            }
        )
        return base
    if len(candidates) != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT:
        raise ValueError("typed preparation success is internally inconsistent")
    if result.status not in {"success", "failure"} or (
        result.status == "failure"
        and result.failure_code != "engine_v2_pose_count_incomplete"
    ):
        raise ValueError("typed preparation success result status is unsupported")
    ranked = tuple(
        sorted(successful, key=lambda candidate: (float(candidate.score), candidate.proposal_index))
    )
    oracle = any(float(candidate.rmsd_angstrom) <= 2.0 for candidate in successful)
    top1 = bool(ranked and float(ranked[0].rmsd_angstrom) <= 2.0)
    top5 = bool(
        len(ranked) >= 5
        and any(float(candidate.rmsd_angstrom) <= 2.0 for candidate in ranked[:5])
    )
    valid = tuple(
        candidate
        for candidate in successful
        if candidate.geometric_valid is True and candidate.chemical_valid is True
    )
    top1_valid = bool(
        ranked
        and ranked[0].geometric_valid is True
        and ranked[0].chemical_valid is True
    )
    blockers: list[str] = []
    if len(successful) < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT:
        blockers.append("candidate_generation_incomplete")
    if result.status == "failure":
        blockers.append("case_execution_failure")
    if not oracle:
        blockers.append("no_oracle_candidate")
    elif not top5:
        blockers.append("oracle_but_top5_miss")
    elif not top1:
        blockers.append("top5_but_top1_miss")
    if not top1_valid:
        blockers.append("top1_invalid")
    if not valid:
        blockers.append("no_valid_candidate")
    if result.status == "failure":
        selection_stage = "execution_failed_incomplete_pose_set"
    elif not oracle:
        selection_stage = "proposal_oracle_absent"
    elif not top5:
        selection_stage = "oracle_missed_top5"
    elif not top1:
        selection_stage = "top5_recovered_top1_missed"
    else:
        selection_stage = "top1_recovered"
    if not ranked:
        validity_stage = "no_ranked_top1"
    elif not valid:
        validity_stage = "no_valid_candidate"
    elif not top1_valid:
        validity_stage = "valid_candidate_available_top1_invalid"
    else:
        validity_stage = "top1_valid"
    if result.status == "failure":
        causal_diagnosis = "typed_incomplete_pose_failure"
    elif (
        len(successful) < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        or not oracle
        or not valid
    ):
        causal_diagnosis = "unresolved_requires_coordinate_replay"
    elif not top1 or not top5:
        causal_diagnosis = "observed_selection_gap_only"
    elif not top1_valid:
        causal_diagnosis = "observed_top1_validity_gap_only"
    else:
        causal_diagnosis = "no_observed_gate_blocker"
    base.update(
        {
            "oracle_2a_recovery": oracle,
            "top1_2a_recovery": top1,
            "top5_2a_recovery": top5,
            "top1_proposal_index": ranked[0].proposal_index if ranked else None,
            "top1_proposal_mode": ranked[0].proposal_mode if ranked else None,
            "top1_valid": top1_valid,
            "top1_posebusters_failed_check_ids": (
                list(ranked[0].posebusters_failed_check_ids) if ranked else []
            ),
            "valid_candidate_count": len(valid),
            "any_valid_candidate": bool(valid),
            "selection_stage": selection_stage,
            "validity_stage": validity_stage,
            "observed_blocker_ids": [
                blocker for blocker in _BLOCKER_ORDER if blocker in blockers
            ],
            "causal_diagnosis": causal_diagnosis,
        }
    )
    return base


def _gate_result(
    *,
    metric: str,
    numerator: int,
    denominator: int,
    threshold_row: Mapping[str, object],
) -> dict[str, object]:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError(f"gate counts are invalid: {metric}")
    observed = numerator / denominator if denominator else None
    operator = str(threshold_row["operator"])
    threshold = float(threshold_row["proposed_threshold"])
    passed = bool(
        observed is not None
        and ((observed <= threshold) if operator == "max" else (observed >= threshold))
    )
    return {
        "operator": operator,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_policy": STAGE0_DEVELOPMENT_GATE_DENOMINATORS[metric],
        "evaluation_status": "evaluated" if denominator else "empty_denominator",
        "observed_estimate": observed,
        "proposed_threshold": threshold,
        "passed": passed,
        "threshold_derivation_rule": threshold_row["derivation_rule"],
        "threshold_evidence_observed_estimate": threshold_row["observed_estimate"],
    }


def build_development_gate_ledger(
    *,
    development_report: Mapping[str, object],
    threshold_evidence: Mapping[str, object],
    authenticated_results: Sequence[PublicRedockingCaseResult],
    source_receipt_binding: Mapping[str, object],
    development_report_path: str,
    development_report_file_sha256: str,
    threshold_evidence_path: str,
    threshold_evidence_file_sha256: str,
) -> dict[str, object]:
    """Build the deterministic ledger from already authenticated typed evidence."""

    report_projection = dict(development_report)
    observed_report_sha256 = report_projection.pop("report_sha256", None)
    threshold_projection = dict(threshold_evidence)
    observed_threshold_sha256 = threshold_projection.pop("evidence_sha256", None)
    if (
        observed_report_sha256 != _sha256_payload(report_projection)
        or observed_threshold_sha256 != _sha256_payload(threshold_projection)
    ):
        raise ValueError("development or threshold evidence self-hash is invalid")
    _require_frozen_threshold_binding(
        threshold_evidence,
        threshold_evidence_path=threshold_evidence_path,
        threshold_evidence_file_sha256=threshold_evidence_file_sha256,
    )
    thresholds = _validated_thresholds(threshold_evidence)
    raw_results = tuple(authenticated_results)
    if any(type(result) is not PublicRedockingCaseResult for result in raw_results):
        raise TypeError("authenticated development results must be typed")
    results = tuple(sorted(raw_results, key=lambda result: result.case_id))
    if (
        development_report.get("schema_id") != STAGE0_DEVELOPMENT_ANALYSIS_SCHEMA_ID
        or development_report.get("analysis_scope")
        != "historical_contaminated_development_only"
        or development_report.get("claimable") is not False
        or development_report.get("contains_fresh_internal_blind_holdout") is not False
        or not _is_sha256(development_report.get("report_sha256"))
        or not _is_sha256(development_report_file_sha256)
        or not _is_sha256(threshold_evidence_file_sha256)
    ):
        raise ValueError("development report identity or claim boundary is invalid")
    case_ids = [result.case_id for result in results]
    development_case_ids = set(PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS)
    smoke_case_ids = set(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS)
    fresh_case_ids = set(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS)
    binding = _validated_source_binding(
        source_receipt_binding,
        case_count=len(results),
    )
    if (
        not results
        or case_ids != sorted(set(case_ids))
        or not set(case_ids).issubset(development_case_ids)
        or bool(set(case_ids) & (smoke_case_ids | fresh_case_ids))
        or development_report.get("case_ids") != case_ids
        or development_report.get("case_count") != len(results)
    ):
        raise ValueError("authenticated development cases are cross-wired")
    rows = [_case_row(result) for result in results]
    preparation_rows = [
        row for row in rows if row["preparation_status"] == "success"
    ]
    oracle_rows = [row for row in preparation_rows if row["oracle_2a_recovery"] is True]
    candidate_success_count = sum(
        int(row["candidate_success_count"]) for row in preparation_rows
    )
    if (
        development_report.get("scored_case_count")
        != sum(row["result_status"] == "success" for row in preparation_rows)
        or development_report.get("preparation_excluded_case_count")
        != len(rows) - len(preparation_rows)
        or development_report.get("candidate_count") != candidate_success_count
    ):
        raise ValueError("development report aggregate counts are cross-wired")
    gate_counts = {
        "preparation_input_unsupported_rate": (
            len(rows) - len(preparation_rows),
            len(rows),
        ),
        "candidate_generation_coverage": (
            candidate_success_count,
            len(preparation_rows) * PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
        ),
        "proposal_oracle_2a_recovery": (len(oracle_rows), len(preparation_rows)),
        "top1_selection_failure_given_oracle": (
            sum(row["top1_2a_recovery"] is not True for row in oracle_rows),
            len(oracle_rows),
        ),
        "top5_selection_failure_given_oracle": (
            sum(row["top5_2a_recovery"] is not True for row in oracle_rows),
            len(oracle_rows),
        ),
        "invalid_top1_pose_rate": (
            sum(row["top1_valid"] is not True for row in preparation_rows),
            len(preparation_rows),
        ),
        "case_level_failure_rate": (
            sum(row["result_status"] != "success" for row in rows),
            len(rows),
        ),
    }
    gates = {
        metric: _gate_result(
            metric=metric,
            numerator=gate_counts[metric][0],
            denominator=gate_counts[metric][1],
            threshold_row=thresholds[metric],
        )
        for metric in STAGE0_DEVELOPMENT_GATE_OPERATORS
    }
    case_ids_by_blocker = {
        blocker: sorted(
            str(row["case_id"])
            for row in rows
            if blocker in row["observed_blocker_ids"]
        )
        for blocker in _BLOCKER_ORDER
    }
    selection_counts = Counter(str(row["selection_stage"]) for row in rows)
    validity_counts = Counter(str(row["validity_stage"]) for row in rows)
    causal_counts = Counter(str(row["causal_diagnosis"]) for row in rows)
    ledger: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "algorithm_profile_id": STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID,
        "claimable": False,
        "runtime_consumable": False,
        "fresh_execution_authorized": False,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "product_promotion_allowed": False,
        "public_claim_eligible": False,
        "source_evidence": {
            "development_report_path": development_report_path,
            "development_report_file_sha256": development_report_file_sha256,
            "development_report_sha256": development_report["report_sha256"],
            "threshold_evidence_path": threshold_evidence_path,
            "threshold_evidence_file_sha256": threshold_evidence_file_sha256,
            "threshold_evidence_sha256": threshold_evidence["evidence_sha256"],
            "threshold_evidence_case_count": threshold_evidence["case_count"],
            "authenticated_result_payloads_sha256": _sha256_payload(
                [result.to_dict() for result in results]
            ),
            "source_receipt_binding": binding,
        },
        "summary": {
            "case_count": len(rows),
            "preparation_success_case_count": len(preparation_rows),
            "preparation_failure_case_count": len(rows) - len(preparation_rows),
            "oracle_2a_recovery_case_count": len(oracle_rows),
            "candidate_success_count": candidate_success_count,
            "fixed_candidate_slot_count": (
                len(preparation_rows) * PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
            ),
            "any_valid_candidate_case_count": sum(
                row["any_valid_candidate"] is True for row in preparation_rows
            ),
            "selection_stage_counts": dict(sorted(selection_counts.items())),
            "validity_stage_counts": dict(sorted(validity_counts.items())),
            "causal_diagnosis_counts": dict(sorted(causal_counts.items())),
        },
        "development_gates": gates,
        "all_development_gates_passed": all(
            bool(row["passed"]) for row in gates.values()
        ),
        "case_ids_by_observed_blocker": case_ids_by_blocker,
        "cases": rows,
    }
    ledger["ledger_sha256"] = _sha256_payload(ledger)
    return ledger


def build_authenticated_development_gate_ledger(
    *,
    repo_root: Path,
    development_report_path: Path,
    threshold_evidence_path: Path,
    expected_development_report_sha256: str,
    expected_threshold_evidence_sha256: str,
) -> dict[str, object]:
    """Read canonical evidence, authenticate receipts, and build the ledger."""

    report_path, report_relative = _repo_file(
        repo_root, development_report_path, name="development report"
    )
    threshold_path, threshold_relative = _repo_file(
        repo_root, threshold_evidence_path, name="threshold evidence"
    )
    report, report_bytes = _canonical_object(report_path, hash_field="report_sha256")
    threshold, threshold_bytes = _canonical_object(
        threshold_path, hash_field="evidence_sha256"
    )
    threshold_file_sha256 = _sha256_bytes(threshold_bytes)
    if (
        not _is_sha256(expected_development_report_sha256)
        or report.get("report_sha256") != expected_development_report_sha256
    ):
        raise ValueError("development report does not match the reviewed SHA-256")
    if (
        not _is_sha256(expected_threshold_evidence_sha256)
        or threshold.get("evidence_sha256") != expected_threshold_evidence_sha256
        or expected_threshold_evidence_sha256
        != STAGE0_FROZEN_THRESHOLD_EVIDENCE_SHA256
    ):
        raise ValueError("threshold evidence does not match the reviewed SHA-256")
    _require_frozen_threshold_binding(
        threshold,
        threshold_evidence_path=threshold_relative,
        threshold_evidence_file_sha256=threshold_file_sha256,
    )
    binding, results = stage0_authenticated_development_evidence(
        report,
        repo_root=repo_root.resolve(),
    )
    return build_development_gate_ledger(
        development_report=report,
        threshold_evidence=threshold,
        authenticated_results=results,
        source_receipt_binding=binding,
        development_report_path=report_relative,
        development_report_file_sha256=_sha256_bytes(report_bytes),
        threshold_evidence_path=threshold_relative,
        threshold_evidence_file_sha256=threshold_file_sha256,
    )


def _output_relative_path(repo_root: Path, path: Path) -> Path:
    root = repo_root.resolve(strict=True)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
    except ValueError as exc:
        raise ValueError("output must remain inside the repository") from exc
    if (
        not relative.parts
        or relative.parts[0] != ".betelgeuze"
        or any(component in {"", ".", ".."} for component in relative.parts)
        or relative.name == ".betelgeuze"
    ):
        raise ValueError("mutable ledger output must be stored under .betelgeuze")
    return relative


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _owned_output_directory_descriptor(
    repo_root: Path,
    relative_directory: Path,
) -> int:
    descriptor = os.open(repo_root.resolve(strict=True), _directory_flags())
    try:
        root_status = os.fstat(descriptor)
        if not stat.S_ISDIR(root_status.st_mode) or (
            hasattr(os, "geteuid") and root_status.st_uid != os.geteuid()
        ):
            raise ValueError("repository root must be an owned directory")
        for component in relative_directory.parts:
            try:
                next_descriptor = os.open(
                    component,
                    _directory_flags(),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(
                    component,
                    _directory_flags(),
                    dir_fd=descriptor,
                )
            status = os.fstat(next_descriptor)
            if (
                not stat.S_ISDIR(status.st_mode)
                or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
            ):
                os.close(next_descriptor)
                raise ValueError("ledger output parent must be an owned directory")
            os.fchmod(next_descriptor, 0o700)
            if stat.S_IMODE(os.fstat(next_descriptor).st_mode) != 0o700:
                os.close(next_descriptor)
                raise ValueError("ledger output parent permissions are invalid")
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _write_exclusive(
    repo_root: Path,
    relative_path: Path,
    payload: bytes,
) -> None:
    parent_descriptor = _owned_output_directory_descriptor(
        repo_root,
        relative_path.parent,
    )
    descriptor = -1
    try:
        descriptor = os.open(
            relative_path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(parent_descriptor)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    finally:
        os.close(parent_descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--expected-development-report-sha256", required=True)
    parser.add_argument("--threshold-evidence", type=Path, required=True)
    parser.add_argument("--expected-threshold-evidence-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    ledger = build_authenticated_development_gate_ledger(
        repo_root=repo_root,
        development_report_path=arguments.development_report,
        threshold_evidence_path=arguments.threshold_evidence,
        expected_development_report_sha256=(
            arguments.expected_development_report_sha256
        ),
        expected_threshold_evidence_sha256=(
            arguments.expected_threshold_evidence_sha256
        ),
    )
    output = _output_relative_path(repo_root, arguments.output)
    _write_exclusive(repo_root, output, _canonical_bytes(ledger) + b"\n")
    print(ledger["ledger_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
