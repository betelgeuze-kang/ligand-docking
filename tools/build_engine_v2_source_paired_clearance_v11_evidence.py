#!/usr/bin/env python3
"""Pack and verify the exact historical source-paired V1.1 clearance audit."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import tarfile

from betelgeuze_engine_v2.benchmark.blind_stage0 import _typed_development_result
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
    PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
    PUBLIC_REDOCKING_RUNNER_ID,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
    _SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_SCHEMA_ID,
)
import tools.build_engine_v2_source_paired_failure_atlas as failure_atlas


SCHEMA_ID = "betelgeuze.engine_v2_source_paired_clearance_v11_audit/1.0.0"
EXPECTED_SOURCE_COMMIT_SHA1 = "6a749540339db5e53875841e463cfcbcdf7072b2"
EXPECTED_CASE_IDS = failure_atlas.EXPECTED_CASE_IDS
EXPECTED_CASE_IDS_SHA256 = failure_atlas.EXPECTED_CASE_IDS_SHA256
EXPECTED_UNCOVERED_CASE_IDS = failure_atlas.EXPECTED_UNCOVERED_CASE_IDS
EXPECTED_PREPARATION_FAILURE_CASE_ID = failure_atlas.EXPECTED_PREPARATION_FAILURE_CASE_ID
EXPECTED_RECEIPT_SCHEMA_ID = (
    _SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_SCHEMA_ID
)

BASELINE_RUN_ROOT = (
    ".betelgeuze/stage0-development/"
    "v7-clearance-v11-6a749540-baseline-nine"
)
RESCUE_RUN_ROOT = (
    ".betelgeuze/stage0-development/"
    "v7-clearance-v11-6a749540-rescue-nine"
)
BASELINE_SUMMARY_PATH = (
    f"{BASELINE_RUN_ROOT}/"
    "engine-v2-only-summary-development-009-cd2c24c9c7d93786.json"
)
RESCUE_SUMMARY_PATH = (
    f"{RESCUE_RUN_ROOT}/"
    "engine-v2-only-summary-development-source-paired-torsion-rescue-"
    "009-cd2c24c9c7d93786.json"
)
BASELINE_ANALYSIS_PATH = (
    ".betelgeuze/stage0-development/"
    "v7-clearance-v11-6a749540-baseline-analysis.json"
)
RESCUE_ANALYSIS_PATH = (
    ".betelgeuze/stage0-development/"
    "v7-clearance-v11-6a749540-rescue-analysis.json"
)
BASELINE_WALLTIME_PATH = f"{BASELINE_RUN_ROOT}.walltime.txt"
RESCUE_WALLTIME_PATH = f"{RESCUE_RUN_ROOT}.walltime.txt"
REPORT_PATH = (
    ".betelgeuze/stage0-development/"
    "source-paired-clearance-v11-6a749540-audit.json"
)
ARCHIVE_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.tar.zst"
)
MEMBERS_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.members.sha256"
)
BUNDLE_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.bundle.sha256"
)

EXPECTED_EVIDENCE_ARCHIVE_SHA256 = (
    "e36a358c1f21ec40b01dfa1170a85de06220bae1e49c9a389f7c6c1fe650bf69"
)
EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256 = (
    "164d097d5b944c58b6475d79cd6b295a7c576baf5141a28faadebce31130dae7"
)
EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256 = (
    "72e48e4f89901d6ae46e89b87a98df92c73ae5086fa80d2bcdad7f45f7d96856"
)
EXPECTED_REPORT_SHA256 = (
    "3f03fdc9fe34ac6dc086b4bf9a510e18f79a6d54656dbd6df74840049bfa1437"
)
EXPECTED_EVIDENCE_MEMBER_COUNT = 59

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TAR_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_MEMBER_MANIFEST_BYTES = 256 * 1024
MAX_BUNDLE_CHECKSUM_BYTES = 4 * 1024
EXPECTED_CLEARANCE_PAIR_COUNT_BOUND = 1_000_000
EXPECTED_CLEARANCE_RADII_POLICY_SHA256 = (
    "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
)

EXPECTED_BASELINE_METRICS = {
    "case_count": 9,
    "scored_case_count": 8,
    "candidate_success_count": 512,
    "exact_valid_candidate_count": 7,
    "native_like_candidate_count": 4,
    "selection_eligible_candidate_count": 31,
    "native_like_selection_eligible_candidate_count": 3,
    "proposal_oracle_recovery_case_count": 1,
    "top1_recovery_case_count": 1,
    "top5_recovery_case_count": 1,
    "valid_top1_case_count": 3,
}
EXPECTED_RESCUE_METRICS = {
    **EXPECTED_BASELINE_METRICS,
    "selection_eligible_candidate_count": 30,
    "native_like_selection_eligible_candidate_count": 2,
}
EXPECTED_TORSION_COUNTS = {
    "allocated_candidate_count": 28,
    "torsion_evaluated_candidate_count": 27,
    "torsion_variant_available_candidate_count": 26,
    "torsion_selected_candidate_count": 0,
    "clearance_evaluated_candidate_count": 28,
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_payload(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _safe_member_name(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("archive member name is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("archive member name is invalid")
    if any(part.startswith(".env") for part in path.parts):
        raise ValueError("archive member name is prohibited")
    return path.as_posix()


def _distribution(values: Sequence[float]) -> dict[str, object]:
    return failure_atlas._distribution(values)


def _binary64(value: object, *, name: str) -> float:
    encoded = failure_atlas._binary64_hex(value, name=name)
    number = float.fromhex(encoded)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _member_object(
    members: Mapping[str, bytes],
    member: str,
    *,
    name: str,
    hash_field: str,
) -> tuple[dict[str, object], bytes]:
    safe = _safe_member_name(member)
    raw = members.get(safe)
    if raw is None or len(raw) > MAX_MEMBER_BYTES:
        raise ValueError(f"{name} member is missing or oversized")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not valid JSON") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ValueError(f"{name} is not canonical JSON")
    projection = dict(payload)
    observed = projection.pop(hash_field, None)
    if not _is_sha256(observed) or observed != _sha256_payload(projection):
        raise ValueError(f"{name} self-hash is invalid")
    return payload, raw


def _walltime(members: Mapping[str, bytes], path: str, *, lane: str) -> dict[str, object]:
    raw = members.get(_safe_member_name(path))
    if raw is None or len(raw) > 4096:
        raise ValueError(f"{lane} wall-time receipt is missing or oversized")
    try:
        lines = raw.decode("ascii").splitlines()
        values = dict(line.split("=", 1) for line in lines)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{lane} wall-time receipt is invalid") from exc
    if set(values) != {
        "elapsed_seconds",
        "user_seconds",
        "system_seconds",
        "max_rss_kb",
        "exit_status",
    }:
        raise ValueError(f"{lane} wall-time fields are invalid")
    elapsed = float(values["elapsed_seconds"])
    user = float(values["user_seconds"])
    system = float(values["system_seconds"])
    maximum_rss = int(values["max_rss_kb"])
    exit_status = int(values["exit_status"])
    if (
        not all(math.isfinite(value) and value >= 0.0 for value in (elapsed, user, system))
        or maximum_rss < 1
        or exit_status != 0
    ):
        raise ValueError(f"{lane} wall-time values are invalid")
    return {
        "elapsed_seconds_binary64_hex": elapsed.hex(),
        "user_seconds_binary64_hex": user.hex(),
        "system_seconds_binary64_hex": system.hex(),
        "maximum_rss_kb": maximum_rss,
        "exit_status": exit_status,
        "file_sha256": _sha256_bytes(raw),
    }


def _analysis(
    members: Mapping[str, bytes],
    path: str,
    *,
    lane: str,
    receipt_hashes: Mapping[str, str],
) -> dict[str, object]:
    payload, raw = _member_object(
        members,
        path,
        name=f"{lane} analysis",
        hash_field="report_sha256",
    )
    source = payload.get("source_receipts_sha256")
    if (
        payload.get("schema_id") != failure_atlas.ANALYSIS_SCHEMA_ID
        or payload.get("analysis_scope") != "historical_contaminated_development_only"
        or payload.get("contains_fresh_internal_blind_holdout") is not False
        or payload.get("claimable") is not False
        or tuple(payload.get("case_ids", ())) != EXPECTED_CASE_IDS
        or not isinstance(source, Mapping)
    ):
        raise ValueError(f"{lane} analysis identity or boundary is invalid")
    observed: dict[str, str] = {}
    for source_path, digest in source.items():
        case_id = Path(str(source_path)).stem
        if case_id in observed or not _is_sha256(digest):
            raise ValueError(f"{lane} analysis receipt binding is invalid")
        observed[case_id] = str(digest)
    if observed != dict(receipt_hashes):
        raise ValueError(f"{lane} analysis contradicts restored receipts")
    return {
        "path": path,
        "file_sha256": _sha256_bytes(raw),
        "report_sha256": payload["report_sha256"],
        "case_count": payload.get("case_count"),
        "scored_case_count": payload.get("scored_case_count"),
        "candidate_count": payload.get("candidate_count"),
        "oracle_2a_recovery_case_count": payload.get("oracle_2a_recovery_case_count"),
        "full_top1_recovery_case_count": payload.get("full_top1_recovery_case_count"),
        "full_top5_recovery_case_count": payload.get("full_top5_recovery_case_count"),
    }


def _metric_summary(results: Mapping[str, Mapping[str, object]]) -> dict[str, int]:
    if tuple(sorted(results)) != EXPECTED_CASE_IDS:
        raise ValueError("lane result case set is invalid")
    totals: Counter[str] = Counter(
        {
            "case_count": len(EXPECTED_CASE_IDS),
            "scored_case_count": 0,
            "candidate_success_count": 0,
            "exact_valid_candidate_count": 0,
            "native_like_candidate_count": 0,
            "selection_eligible_candidate_count": 0,
            "native_like_selection_eligible_candidate_count": 0,
            "proposal_oracle_recovery_case_count": 0,
            "top1_recovery_case_count": 0,
            "top5_recovery_case_count": 0,
            "valid_top1_case_count": 0,
        }
    )
    for case_id in EXPECTED_CASE_IDS:
        result = results[case_id]
        diagnostics = result.get("engine_v2_diagnostics")
        if not isinstance(diagnostics, Mapping):
            raise ValueError(f"{case_id} diagnostics are missing")
        candidates = diagnostics.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError(f"{case_id} candidates are invalid")
        if result.get("status") == "failure":
            if case_id != EXPECTED_PREPARATION_FAILURE_CASE_ID or candidates:
                raise ValueError("unexpected preparation-failure result")
            continue
        if result.get("status") != "success" or len(candidates) != 64:
            raise ValueError(f"{case_id} successful candidate denominator drifted")
        successful = [
            candidate
            for candidate in candidates
            if isinstance(candidate, Mapping) and candidate.get("status") == "success"
        ]
        if len(successful) != 64:
            raise ValueError(f"{case_id} candidate success denominator drifted")
        totals["scored_case_count"] += 1
        totals["candidate_success_count"] += len(successful)
        exact_valid = [
            candidate
            for candidate in successful
            if candidate.get("geometric_valid") is True
            and candidate.get("chemical_valid") is True
        ]
        native_like = [
            candidate
            for candidate in successful
            if float(candidate["rmsd_angstrom"]) <= 2.0
        ]
        eligible = [
            candidate
            for candidate in successful
            if candidate.get("selection_eligible") is True
        ]
        totals["exact_valid_candidate_count"] += len(exact_valid)
        totals["native_like_candidate_count"] += len(native_like)
        totals["selection_eligible_candidate_count"] += len(eligible)
        totals["native_like_selection_eligible_candidate_count"] += sum(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in eligible
        )
        ranked = sorted(
            successful,
            key=lambda candidate: (
                float(candidate["score"]),
                int(candidate["proposal_index"]),
            ),
        )
        totals["proposal_oracle_recovery_case_count"] += bool(native_like)
        totals["top1_recovery_case_count"] += (
            float(ranked[0]["rmsd_angstrom"]) <= 2.0
        )
        totals["top5_recovery_case_count"] += any(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5]
        )
        totals["valid_top1_case_count"] += (
            ranked[0].get("geometric_valid") is True
            and ranked[0].get("chemical_valid") is True
        )
    return {key: int(totals[key]) for key in EXPECTED_BASELINE_METRICS}


def _load_lane(
    members: Mapping[str, bytes],
    *,
    lane: str,
    run_root: str,
    summary_path: str,
    analysis_path: str,
    walltime_path: str,
) -> dict[str, object]:
    expected_schema = (
        failure_atlas.SUMMARY_SCHEMA_ID
        if lane == "baseline"
        else failure_atlas.RESCUE_SUMMARY_SCHEMA_ID
    )
    summary, summary_raw = _member_object(
        members,
        summary_path,
        name=f"{lane} summary",
        hash_field="summary_sha256",
    )
    engine_identity = summary.get("engine_identity")
    false_fields = (
        "benchmark_validated",
        "claim_safe",
        "contains_engineering_smoke",
        "contains_fresh_internal_blind_holdout",
        "fresh_execution_authorized",
        "primary_claim_eligible",
        "product_promotion_eligible",
        "product_qualified",
        "public_claim_eligible",
        "scientifically_validated",
    )
    if (
        summary.get("schema_id") != expected_schema
        or summary.get("analysis_scope")
        != "historical_contaminated_development_only"
        or summary.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
        or summary.get("case_count") != len(EXPECTED_CASE_IDS)
        or tuple(summary.get("case_ids", ())) != EXPECTED_CASE_IDS
        or summary.get("case_ids_sha256") != EXPECTED_CASE_IDS_SHA256
        or any(summary.get(field) is not False for field in false_fields)
        or not isinstance(engine_identity, Mapping)
        or (
            lane == "rescue"
            and summary.get("development_source_paired_torsion_rescue") is not True
        )
        or (
            lane == "baseline"
            and "development_source_paired_torsion_rescue" in summary
        )
    ):
        raise ValueError(f"{lane} summary identity or boundary is invalid")

    results: dict[str, dict[str, object]] = {}
    receipt_payloads: dict[str, dict[str, object]] = {}
    receipt_hashes: dict[str, str] = {}
    materializations: dict[str, dict[str, object]] = {}
    expected_members = {summary_path}
    for case_id in EXPECTED_CASE_IDS:
        receipt_path = f"{run_root}/receipts/engine_v2/{case_id}.json"
        materialization_path = (
            f"{run_root}/receipts/materializations/{case_id}.json"
        )
        expected_members.update((receipt_path, materialization_path))
        receipt, receipt_raw = _member_object(
            members,
            receipt_path,
            name=f"{lane} execution receipt {case_id}",
            hash_field="receipt_sha256",
        )
        result = receipt.get("result")
        if (
            set(receipt) != failure_atlas._EXECUTION_FIELDS
            or receipt.get("schema_id") != PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID
            or receipt.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
            or receipt.get("archive_sha256") != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or receipt.get("source_ids_sha256") != PUBLIC_REDOCKING_SOURCE_IDS_SHA256
            or receipt.get("cache_read_allowed") is not False
            or receipt.get("fresh_execution") is not True
            or not isinstance(result, Mapping)
            or result.get("case_id") != case_id
        ):
            raise ValueError(f"{lane} execution receipt identity is invalid")
        for field in (
            "implementation_sha256",
            "evaluation_pipeline_sha256",
            "execution_environment_sha256",
        ):
            if receipt.get(field) != engine_identity.get(field):
                raise ValueError(f"{lane} execution receipt engine identity drifted")
        typed = _typed_development_result(result)
        typed_payload = typed.to_dict()
        if (
            typed_payload != dict(result)
            or receipt.get("command") != typed_payload.get("execution_command")
            or failure_atlas._execution_policy_tokens(
                receipt.get("execution_policy")
            )
            != typed_payload.get("execution_policy")
        ):
            raise ValueError(f"{lane} execution receipt result is cross-wired")

        materialization, materialization_raw = _member_object(
            members,
            materialization_path,
            name=f"{lane} materialization {case_id}",
            hash_field="receipt_sha256",
        )
        expected_inputs = failure_atlas._materialization_inputs(
            materialization,
            case_id=case_id,
        )
        if (
            materialization.get("schema_id")
            != PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID
            or materialization.get("source_archive_sha256")
            != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or materialization.get("hash_verified_archive") is not True
            or receipt.get("materialization_receipt_sha256")
            != materialization.get("receipt_sha256")
            or receipt.get("input_sha256s") != expected_inputs
            or {
                "receptor": result.get("receptor_artifact_sha256"),
                "reference": result.get("reference_artifact_sha256"),
                "native": result.get("native_artifact_sha256"),
                "seed": result.get("seed_artifact_sha256"),
            }
            != expected_inputs
            or materialization_raw != _canonical_bytes(materialization) + b"\n"
        ):
            raise ValueError(f"{lane} materialization binding is invalid")

        results[case_id] = typed_payload
        receipt_payloads[case_id] = receipt
        receipt_hashes[case_id] = _sha256_bytes(receipt_raw)
        materializations[case_id] = materialization
        if typed.status == "success":
            expected_members.add(f"{run_root}/poses/engine_v2/{case_id}.sdf")

    rows = summary.get("rows")
    embedded_receipts = summary.get("execution_receipts")
    embedded_materializations = summary.get("materializations")
    profiles = summary.get("profiles")
    if not all(
        isinstance(value, list)
        for value in (rows, embedded_receipts, embedded_materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collections are invalid")
    assert isinstance(rows, list)
    assert isinstance(embedded_receipts, list)
    assert isinstance(embedded_materializations, list)
    assert isinstance(profiles, list)
    if any(
        len(value) != len(EXPECTED_CASE_IDS)
        for value in (rows, embedded_receipts, embedded_materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collection denominator drifted")
    for index, case_id in enumerate(EXPECTED_CASE_IDS):
        profile = profiles[index]
        if (
            rows[index] != results[case_id]
            or embedded_receipts[index] != receipt_payloads[case_id]
            or embedded_materializations[index] != materializations[case_id]
            or not isinstance(profile, Mapping)
            or profile.get("case_id") != case_id
        ):
            raise ValueError(f"{lane} summary collection is cross-wired")

    root_prefix = f"{run_root}/"
    observed_members = {path for path in members if path.startswith(root_prefix)}
    if observed_members != expected_members:
        raise ValueError(f"{lane} run-root member set is invalid")

    metrics = _metric_summary(results)
    expected_metrics = (
        EXPECTED_BASELINE_METRICS if lane == "baseline" else EXPECTED_RESCUE_METRICS
    )
    if metrics != expected_metrics:
        raise ValueError(f"{lane} historical metrics drifted")
    analysis = _analysis(
        members,
        analysis_path,
        lane=lane,
        receipt_hashes=receipt_hashes,
    )
    if (
        analysis["case_count"] != metrics["case_count"]
        or analysis["scored_case_count"] != metrics["scored_case_count"]
        or analysis["candidate_count"] != metrics["candidate_success_count"]
        or analysis["oracle_2a_recovery_case_count"]
        != metrics["proposal_oracle_recovery_case_count"]
        or analysis["full_top1_recovery_case_count"]
        != metrics["top1_recovery_case_count"]
        or analysis["full_top5_recovery_case_count"]
        != metrics["top5_recovery_case_count"]
    ):
        raise ValueError(f"{lane} compact analysis metrics drifted")

    return {
        "run_root": run_root,
        "summary_path": summary_path,
        "summary_file_sha256": _sha256_bytes(summary_raw),
        "summary_sha256": summary["summary_sha256"],
        "analysis": analysis,
        "walltime_path": walltime_path,
        "walltime": _walltime(members, walltime_path, lane=lane),
        "engine_identity": dict(engine_identity),
        "metrics": metrics,
        "results": results,
        "receipts": receipt_payloads,
        "receipt_hashes": receipt_hashes,
        "member_count": len(expected_members),
        "logical_size_bytes": sum(len(members[path]) for path in expected_members),
    }


def _gap_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    baseline = [float(row["baseline_gap"]) for row in rows]
    optimized = [float(row["optimized_gap"]) for row in rows]
    deltas = [after - before for before, after in zip(baseline, optimized, strict=True)]
    pair_counts = [float(row["pair_count"]) for row in rows]
    return {
        "count": len(rows),
        "baseline_v6_minimum_vdw_surface_gap_angstrom": _distribution(baseline),
        "optimized_minimum_vdw_surface_gap_angstrom": _distribution(optimized),
        "optimized_minus_baseline_gap_angstrom": _distribution(deltas),
        "gap_change_counts": {
            "improved": sum(delta > 0.0 for delta in deltas),
            "equal": sum(delta == 0.0 for delta in deltas),
            "regressed": sum(delta < 0.0 for delta in deltas),
        },
        "full_cartesian_pair_count": _distribution(pair_counts),
    }


def _clearance_summary(
    results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    target_rows: list[dict[str, object]] = []
    non_target_count = 0
    torsion_counts: Counter[str] = Counter()
    per_case: dict[str, list[dict[str, object]]] = {
        case_id: [] for case_id in EXPECTED_CASE_IDS
    }
    total_candidates = 0
    for case_id in EXPECTED_CASE_IDS:
        result = results[case_id]
        diagnostics = result.get("engine_v2_diagnostics")
        candidates = (
            diagnostics.get("candidates") if isinstance(diagnostics, Mapping) else None
        )
        if not isinstance(candidates, list):
            raise ValueError(f"{case_id} rescue candidates are invalid")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ValueError(f"{case_id} rescue candidate is invalid")
            total_candidates += 1
            payload = candidate.get("refinement_receipt_payload")
            if (
                not isinstance(payload, Mapping)
                or payload.get("schema_id") != EXPECTED_RECEIPT_SCHEMA_ID
            ):
                raise ValueError(f"{case_id} is not uniformly V1.1 receipt-bound")
            target = (
                candidate.get("proposal_mode")
                == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            )
            evaluated = payload.get("clearance_measurement_evaluated")
            reason = payload.get("clearance_measurement_unavailable_reason")
            if not target:
                if (
                    evaluated is not False
                    or reason != "not_source_paired_rescue_target"
                    or payload.get("clearance_radii_policy_sha256") != ""
                    or payload.get(
                        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                    != ""
                    or payload.get(
                        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                    != ""
                    or payload.get("optimized_coordinates_sha256") != ""
                ):
                    raise ValueError("non-target clearance telemetry is not empty")
                non_target_count += 1
                continue
            torsion_counts["allocated_candidate_count"] += 1
            torsion_counts["torsion_evaluated_candidate_count"] += (
                payload.get("torsion_evaluated") is True
            )
            torsion_counts["torsion_variant_available_candidate_count"] += (
                payload.get("torsion_variant_available") is True
            )
            torsion_counts["torsion_selected_candidate_count"] += (
                payload.get("torsion_selected") is True
            )
            torsion_counts["clearance_evaluated_candidate_count"] += (
                evaluated is True
            )
            ligand_count = payload.get("clearance_ligand_atom_count")
            receptor_count = payload.get("clearance_receptor_atom_count")
            pair_count = payload.get("clearance_full_cartesian_pair_count")
            pair_bound = payload.get("clearance_pair_count_bound")
            if (
                evaluated is not True
                or reason != "none"
                or payload.get("clearance_radii_policy_sha256")
                != EXPECTED_CLEARANCE_RADII_POLICY_SHA256
                or type(ligand_count) is not int
                or ligand_count < 1
                or type(receptor_count) is not int
                or receptor_count < 1
                or type(pair_count) is not int
                or pair_count != ligand_count * receptor_count
                or pair_bound != EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
                or pair_count > pair_bound
                or not _is_sha256(payload.get("optimized_coordinates_sha256"))
            ):
                raise ValueError("target clearance telemetry identity is invalid")
            row = {
                "case_id": case_id,
                "proposal_index": int(candidate["proposal_index"]),
                "baseline_gap": _binary64(
                    payload.get(
                        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    ),
                    name="baseline clearance gap",
                ),
                "optimized_gap": _binary64(
                    payload.get(
                        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    ),
                    name="optimized clearance gap",
                ),
                "pair_count": pair_count,
                "ligand_atom_count": ligand_count,
                "receptor_atom_count": receptor_count,
            }
            target_rows.append(row)
            per_case[case_id].append(row)

    observed_torsion = {
        key: int(torsion_counts[key]) for key in EXPECTED_TORSION_COUNTS
    }
    if (
        total_candidates != 512
        or non_target_count != 484
        or observed_torsion != EXPECTED_TORSION_COUNTS
        or [case_id for case_id in EXPECTED_CASE_IDS if per_case[case_id]]
        != [
            "5SD5_HWI",
            "5SIS_JSM",
            "6T88_MWQ",
            "6TW5_9M2",
            "6TW7_NZB",
            "6VTA_AKN",
            "6WTN_RXT",
        ]
        or any(
            len(rows) != 4
            for case_id, rows in per_case.items()
            if case_id not in {"6M2B_EZO", EXPECTED_PREPARATION_FAILURE_CASE_ID}
        )
    ):
        raise ValueError("V1.1 clearance telemetry denominator drifted")

    uncovered_rows = [
        row for row in target_rows if row["case_id"] in EXPECTED_UNCOVERED_CASE_IDS
    ]
    return {
        "receipt_schema_id": EXPECTED_RECEIPT_SCHEMA_ID,
        "uniform_v11_candidate_receipt_count": total_candidates,
        "non_target_empty_telemetry_count": non_target_count,
        "radii_policy_sha256": EXPECTED_CLEARANCE_RADII_POLICY_SHA256,
        "pair_count_bound": EXPECTED_CLEARANCE_PAIR_COUNT_BOUND,
        "pair_bound_unavailable_count": 0,
        "torsion": observed_torsion,
        "all_fixed_rescue_targets": _gap_summary(target_rows),
        "proposal_oracle_uncovered_targets": {
            "case_count": len(EXPECTED_UNCOVERED_CASE_IDS),
            "case_ids": list(EXPECTED_UNCOVERED_CASE_IDS),
            **_gap_summary(uncovered_rows),
        },
        "cases": [
            {
                "case_id": case_id,
                **_gap_summary(per_case[case_id]),
            }
            for case_id in EXPECTED_CASE_IDS
            if per_case[case_id]
        ],
    }


def _lane_comparison(
    baseline: Mapping[str, object],
    rescue: Mapping[str, object],
) -> dict[str, object]:
    baseline_results = baseline.get("results")
    rescue_results = rescue.get("results")
    if not isinstance(baseline_results, Mapping) or not isinstance(
        rescue_results, Mapping
    ):
        raise ValueError("lane result maps are invalid")
    coordinate_changes: dict[str, list[int]] = {}
    parent_duplicate_count = 0
    for case_id in EXPECTED_CASE_IDS:
        baseline_result = baseline_results[case_id]
        rescue_result = rescue_results[case_id]
        if not isinstance(baseline_result, Mapping) or not isinstance(
            rescue_result, Mapping
        ):
            raise ValueError("lane result row is invalid")
        for field in (
            "receptor_artifact_sha256",
            "reference_artifact_sha256",
            "native_artifact_sha256",
            "seed_artifact_sha256",
        ):
            if baseline_result.get(field) != rescue_result.get(field):
                raise ValueError("lane input artifact identity drifted")
        baseline_diagnostics = baseline_result.get("engine_v2_diagnostics")
        rescue_diagnostics = rescue_result.get("engine_v2_diagnostics")
        baseline_candidates = (
            baseline_diagnostics.get("candidates")
            if isinstance(baseline_diagnostics, Mapping)
            else None
        )
        rescue_candidates = (
            rescue_diagnostics.get("candidates")
            if isinstance(rescue_diagnostics, Mapping)
            else None
        )
        if not isinstance(baseline_candidates, list) or not isinstance(
            rescue_candidates, list
        ):
            raise ValueError("lane candidate collections are invalid")
        if any(not isinstance(candidate, Mapping) for candidate in baseline_candidates):
            raise ValueError("baseline candidate collection contains an invalid row")
        if any(not isinstance(candidate, Mapping) for candidate in rescue_candidates):
            raise ValueError("rescue candidate collection contains an invalid row")
        baseline_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in baseline_candidates
        }
        rescue_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in rescue_candidates
        }
        if (
            len(baseline_by_index) != len(baseline_candidates)
            or len(rescue_by_index) != len(rescue_candidates)
            or set(baseline_by_index) != set(rescue_by_index)
        ):
            raise ValueError("lane candidate indices drifted")
        changed = [
            index
            for index in sorted(baseline_by_index)
            if baseline_by_index[index].get("coordinate_fingerprint_sha256")
            != rescue_by_index[index].get("coordinate_fingerprint_sha256")
        ]
        allocation_pairs: list[dict[str, int]] = []
        if rescue_candidates:
            assert isinstance(rescue_diagnostics, Mapping)
            _, allocation_pairs = failure_atlas._rescue_allocation(
                rescue_diagnostics,
                rescue_candidates,
            )
        expected_changed = sorted(
            row["target_proposal_index"] for row in allocation_pairs
        )
        if changed != expected_changed:
            raise ValueError("rescue coordinate changes contradict the allocation")
        if changed:
            coordinate_changes[case_id] = changed
        for pair in allocation_pairs:
            target = pair["target_proposal_index"]
            parent = pair["parent_proposal_index"]
            if (
                rescue_by_index[target].get("coordinate_fingerprint_sha256")
                == rescue_by_index[parent].get("coordinate_fingerprint_sha256")
            ):
                parent_duplicate_count += 1
    changed_count = sum(len(indices) for indices in coordinate_changes.values())
    if changed_count != 28 or parent_duplicate_count != 28:
        raise ValueError("source-paired coordinate lineage drifted")
    return {
        "same_case_denominator": True,
        "same_candidate_denominator": True,
        "same_input_artifacts": True,
        "baseline_to_rescue_coordinate_change_candidate_count": changed_count,
        "baseline_to_rescue_coordinate_change_proposal_indices_by_case": (
            coordinate_changes
        ),
        "rescue_to_parent_coordinate_duplicate_candidate_count": (
            parent_duplicate_count
        ),
        "torsion_selected_candidate_count": 0,
        "semantic_regression_against_pinned_v1_metrics": False,
        "interpretation": (
            "v11_adds_clearance_telemetry_without_changing_the_pinned_v1_"
            "historical_outcome_counts"
        ),
    }


def _build_report(members: Mapping[str, bytes]) -> dict[str, object]:
    baseline = _load_lane(
        members,
        lane="baseline",
        run_root=BASELINE_RUN_ROOT,
        summary_path=BASELINE_SUMMARY_PATH,
        analysis_path=BASELINE_ANALYSIS_PATH,
        walltime_path=BASELINE_WALLTIME_PATH,
    )
    rescue = _load_lane(
        members,
        lane="rescue",
        run_root=RESCUE_RUN_ROOT,
        summary_path=RESCUE_SUMMARY_PATH,
        analysis_path=RESCUE_ANALYSIS_PATH,
        walltime_path=RESCUE_WALLTIME_PATH,
    )
    baseline_identity = baseline["engine_identity"]
    rescue_identity = rescue["engine_identity"]
    assert isinstance(baseline_identity, Mapping)
    assert isinstance(rescue_identity, Mapping)
    shared_identity_fields = (
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "interaction_refiner_config_sha256",
    )
    shared_identity = {
        field: baseline_identity.get(field) for field in shared_identity_fields
    }
    if any(
        not _is_sha256(value) or rescue_identity.get(field) != value
        for field, value in shared_identity.items()
    ):
        raise ValueError("lane engine identity is not comparable")
    baseline_walltime = baseline["walltime"]
    rescue_walltime = rescue["walltime"]
    assert isinstance(baseline_walltime, Mapping)
    assert isinstance(rescue_walltime, Mapping)
    elapsed_delta = float.fromhex(
        str(rescue_walltime["elapsed_seconds_binary64_hex"])
    ) - float.fromhex(str(baseline_walltime["elapsed_seconds_binary64_hex"]))
    rescue_results = rescue["results"]
    assert isinstance(rescue_results, Mapping)

    report: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "evidence_role": "source_paired_clearance_v11_receipt_audit",
        "source_commit_sha1": EXPECTED_SOURCE_COMMIT_SHA1,
        "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "input_archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_identifiers_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "case_count": len(EXPECTED_CASE_IDS),
        "case_ids": list(EXPECTED_CASE_IDS),
        "case_ids_sha256": EXPECTED_CASE_IDS_SHA256,
        "engine_identity": shared_identity,
        "baseline": {
            key: baseline[key]
            for key in (
                "run_root",
                "summary_path",
                "summary_file_sha256",
                "summary_sha256",
                "analysis",
                "walltime_path",
                "walltime",
                "metrics",
                "member_count",
                "logical_size_bytes",
            )
        },
        "rescue": {
            key: rescue[key]
            for key in (
                "run_root",
                "summary_path",
                "summary_file_sha256",
                "summary_sha256",
                "analysis",
                "walltime_path",
                "walltime",
                "metrics",
                "member_count",
                "logical_size_bytes",
            )
        },
        "clearance_telemetry": _clearance_summary(rescue_results),
        "comparison": _lane_comparison(baseline, rescue),
        "runtime": {
            "wall_elapsed_delta_seconds_binary64_hex": elapsed_delta.hex(),
            "interpretation": (
                "single_run_historical_development_only_no_speed_claim"
            ),
        },
        "preservation": {
            "report_member": REPORT_PATH,
            "archive_path": ARCHIVE_PATH,
            "members_sha256_path": MEMBERS_PATH,
            "bundle_sha256_path": BUNDLE_PATH,
            "archive_binding_direction": (
                "external_reviewed_hashes_bind_this_report_member"
            ),
        },
        "development_only": True,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "stage0_eligible": False,
        "primary_claim_eligible": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "selection_rule_changed": False,
        "threshold_changed": False,
        "v7_replacement_authorized": False,
        "decision": (
            "telemetry_available_for_descriptive_review_no_policy_change"
        ),
    }
    report["report_sha256"] = _sha256_payload(report)
    return report


def _read_regular_mode_0600(path: Path, *, repo_root: Path) -> tuple[str, bytes]:
    raw, relative = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        path,
        maximum=MAX_MEMBER_BYTES,
        name="V1.1 evidence member",
    )
    return _safe_member_name(relative), raw


def _collect_run_root(
    repo_root: Path,
    relative_root: str,
    *,
    maximum_total_bytes: int,
) -> dict[str, bytes]:
    root = repo_root / relative_root
    failure_atlas._reject_symlink_ancestry(root, name="V1.1 run root")
    root_metadata = root.lstat()
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or stat.S_ISLNK(root_metadata.st_mode)
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise ValueError(f"run root must be a mode-0700 directory: {relative_root}")
    members: dict[str, bytes] = {}
    logical_size = 0
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if (
            not stat.S_ISDIR(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or stat.S_IMODE(current_metadata.st_mode) != 0o700
        ):
            raise ValueError("run-root directory contract is invalid")
        for directory in directories:
            metadata = (current_path / directory).lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("run root cannot contain symlink directories")
        for filename in filenames:
            safe, raw = _read_regular_mode_0600(
                current_path / filename,
                repo_root=repo_root,
            )
            if safe in members:
                raise ValueError("run root contains duplicate member names")
            logical_size += len(raw)
            if logical_size > maximum_total_bytes:
                raise ValueError("run-root members exceed the aggregate size bound")
            members[safe] = raw
    return members


def _collect_source_members(repo_root: Path) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    logical_size = 0
    for run_root in (BASELINE_RUN_ROOT, RESCUE_RUN_ROOT):
        run_members = _collect_run_root(
            repo_root,
            run_root,
            maximum_total_bytes=MAX_TAR_BYTES - logical_size,
        )
        if set(members).intersection(run_members):
            raise ValueError("evidence member path is duplicated")
        members.update(run_members)
        logical_size += sum(len(raw) for raw in run_members.values())
    for relative in (
        BASELINE_ANALYSIS_PATH,
        RESCUE_ANALYSIS_PATH,
        BASELINE_WALLTIME_PATH,
        RESCUE_WALLTIME_PATH,
    ):
        safe, raw = _read_regular_mode_0600(
            repo_root / relative,
            repo_root=repo_root,
        )
        if safe in members:
            raise ValueError("evidence member path is duplicated")
        logical_size += len(raw)
        if logical_size > MAX_TAR_BYTES:
            raise ValueError("evidence members exceed the aggregate size bound")
        members[safe] = raw
    if len(members) != EXPECTED_EVIDENCE_MEMBER_COUNT - 1:
        raise ValueError("pre-report evidence member denominator drifted")
    return members


def _deterministic_tar_bytes(members: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(members):
            safe = _safe_member_name(name)
            payload = members[safe]
            if len(payload) > MAX_MEMBER_BYTES:
                raise ValueError("archive member exceeds the fixed size bound")
            info = tarfile.TarInfo(safe)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    raw = buffer.getvalue()
    if len(raw) > MAX_TAR_BYTES:
        raise ValueError("deterministic tar exceeds the fixed size bound")
    return raw


def _compress_zstd(tar_raw: bytes) -> bytes:
    try:
        completed = subprocess.run(
            ("zstd", "-q", "-T1", "-19", "-c"),
            input=tar_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("deterministic Zstandard compression failed") from exc
    archive_raw = completed.stdout
    if not archive_raw or len(archive_raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed archive exceeds the fixed size bound")
    return archive_raw


def _manifest_bytes(members: Mapping[str, bytes]) -> bytes:
    raw = "".join(
        f"{_sha256_bytes(members[name])}  {name}\n" for name in sorted(members)
    ).encode("ascii")
    if len(raw) > MAX_MEMBER_MANIFEST_BYTES:
        raise ValueError("member manifest exceeds the fixed size bound")
    return raw


def _parse_manifest(raw: bytes) -> dict[str, str]:
    if len(raw) > MAX_MEMBER_MANIFEST_BYTES:
        raise ValueError("member manifest exceeds the fixed size bound")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("member manifest is not ASCII") from exc
    observed: dict[str, str] = {}
    for line in lines:
        if "  " not in line:
            raise ValueError("member manifest row is invalid")
        digest, name = line.split("  ", 1)
        safe = _safe_member_name(name)
        if safe in observed or not _is_sha256(digest):
            raise ValueError("member manifest identity is invalid")
        observed[safe] = digest
    if len(observed) != EXPECTED_EVIDENCE_MEMBER_COUNT:
        raise ValueError("member manifest count drifted")
    if raw != "".join(
        f"{observed[name]}  {name}\n" for name in sorted(observed)
    ).encode("ascii"):
        raise ValueError("member manifest is not canonically sorted")
    return observed


def _tar_members(tar_raw: bytes, manifest: Mapping[str, str]) -> dict[str, bytes]:
    if len(tar_raw) > MAX_TAR_BYTES:
        raise ValueError("tar stream exceeds the fixed size bound")
    restored: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_raw), mode="r:") as archive:
            for member in archive:
                safe = _safe_member_name(member.name)
                if (
                    safe in restored
                    or not member.isreg()
                    or stat.S_IMODE(member.mode) != 0o600
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or member.size < 0
                    or member.size > MAX_MEMBER_BYTES
                ):
                    raise ValueError("tar member contract is invalid")
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("tar member payload is unavailable")
                payload = handle.read(MAX_MEMBER_BYTES + 1)
                if (
                    len(payload) != member.size
                    or len(payload) > MAX_MEMBER_BYTES
                    or manifest.get(safe) != _sha256_bytes(payload)
                ):
                    raise ValueError("tar member payload hash is invalid")
                restored[safe] = payload
    except tarfile.TarError as exc:
        raise ValueError("tar stream is invalid") from exc
    if set(restored) != set(manifest):
        raise ValueError("tar member set contradicts the manifest")
    return restored


def _bundle_bytes(archive_sha256: str, members_sha256: str) -> bytes:
    return (
        f"{archive_sha256}  {Path(ARCHIVE_PATH).name}\n"
        f"{members_sha256}  {Path(MEMBERS_PATH).name}\n"
    ).encode("ascii")


def _verify_bundle_bytes(
    *,
    archive_raw: bytes,
    members_raw: bytes,
    bundle_raw: bytes,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
    expected_report_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    for value, name in (
        (expected_archive_sha256, "archive SHA-256"),
        (expected_members_sha256, "member-manifest SHA-256"),
        (expected_bundle_sha256, "bundle SHA-256"),
        (expected_report_sha256, "report SHA-256"),
    ):
        if not _is_sha256(value):
            raise ValueError(f"expected {name} is invalid")
    if (
        _sha256_bytes(archive_raw) != expected_archive_sha256
        or _sha256_bytes(members_raw) != expected_members_sha256
        or _sha256_bytes(bundle_raw) != expected_bundle_sha256
        or bundle_raw
        != _bundle_bytes(expected_archive_sha256, expected_members_sha256)
    ):
        raise ValueError("archive bundle identity is invalid")
    manifest = _parse_manifest(members_raw)
    tar_raw = failure_atlas._bounded_zstd_decompress(archive_raw)
    restored = _tar_members(tar_raw, manifest)
    report_raw = restored.get(REPORT_PATH)
    if report_raw is None:
        raise ValueError("audit report member is missing")
    report, _ = _member_object(
        restored,
        REPORT_PATH,
        name="V1.1 clearance audit",
        hash_field="report_sha256",
    )
    if (
        report.get("schema_id") != SCHEMA_ID
        or report.get("source_commit_sha1") != EXPECTED_SOURCE_COMMIT_SHA1
        or report.get("report_sha256") != expected_report_sha256
    ):
        raise ValueError("V1.1 clearance audit identity is invalid")
    source_members = dict(restored)
    source_members.pop(REPORT_PATH)
    recomputed = _build_report(source_members)
    if report != recomputed or report_raw != _canonical_bytes(recomputed) + b"\n":
        raise ValueError("archived V1.1 audit contradicts raw receipt members")
    identity = {
        "archive_sha256": expected_archive_sha256,
        "member_manifest_sha256": expected_members_sha256,
        "bundle_sha256": expected_bundle_sha256,
        "report_sha256": expected_report_sha256,
        "member_count": len(restored),
        "archive_size_bytes": len(archive_raw),
        "tar_size_bytes": len(tar_raw),
        "expanded_member_size_bytes": sum(len(value) for value in restored.values()),
    }
    return report, identity


def _write_exclusive_owned(
    repo_root: Path,
    relative_path: Path,
    payload: bytes,
) -> tuple[int, int]:
    parent_descriptor = failure_atlas._owned_output_directory_descriptor(
        repo_root,
        relative_path.parent,
    )
    descriptor = -1
    temporary_name = f".{relative_path.name}.{secrets.token_hex(16)}.tmp"
    temporary_created = False
    final_link_created = False
    inode_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        temporary_created = True
        temporary_metadata = os.fstat(descriptor)
        inode_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(
            temporary_name,
            relative_path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        final_link_created = True
        os.fsync(parent_descriptor)
        final_metadata = os.stat(
            relative_path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            (final_metadata.st_dev, final_metadata.st_ino) != inode_identity
            or not stat.S_ISREG(final_metadata.st_mode)
            or stat.S_IMODE(final_metadata.st_mode) != 0o600
        ):
            raise ValueError("published evidence output contract is invalid")
        os.unlink(temporary_name, dir_fd=parent_descriptor)
        temporary_created = False
        os.fsync(parent_descriptor)
        return inode_identity
    except BaseException as exc:
        if descriptor >= 0:
            os.close(descriptor)
            descriptor = -1
        rollback_failed = False
        if final_link_created and inode_identity is not None:
            try:
                final_metadata = os.stat(
                    relative_path.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    final_metadata.st_dev,
                    final_metadata.st_ino,
                ) == inode_identity:
                    os.unlink(relative_path.name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
            except FileNotFoundError:
                pass
            except OSError:
                rollback_failed = True
        if temporary_created and inode_identity is not None:
            try:
                temporary_metadata = os.stat(
                    temporary_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    temporary_metadata.st_dev,
                    temporary_metadata.st_ino,
                ) == inode_identity:
                    os.unlink(temporary_name, dir_fd=parent_descriptor)
                    temporary_created = False
                    os.fsync(parent_descriptor)
            except FileNotFoundError:
                temporary_created = False
            except OSError:
                rollback_failed = True
        if rollback_failed:
            raise RuntimeError(
                "evidence output failed after publication and rollback was incomplete"
            ) from exc
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def pack_evidence(repo_root: Path) -> dict[str, object]:
    failure_atlas._reject_symlink_ancestry(repo_root, name="repository root")
    repo_root = repo_root.resolve()
    failure_atlas._prohibited_path(repo_root, name="repository root")
    output_paths = tuple(
        repo_root / path for path in (REPORT_PATH, ARCHIVE_PATH, MEMBERS_PATH, BUNDLE_PATH)
    )
    if any(path.exists() or path.is_symlink() for path in output_paths):
        raise FileExistsError("V1.1 evidence outputs already exist")

    source_members = _collect_source_members(repo_root)
    report = _build_report(source_members)
    report_raw = _canonical_bytes(report) + b"\n"
    members = {**source_members, REPORT_PATH: report_raw}
    if len(members) != EXPECTED_EVIDENCE_MEMBER_COUNT:
        raise ValueError("final evidence member denominator drifted")
    tar_raw = _deterministic_tar_bytes(members)
    archive_raw = _compress_zstd(tar_raw)
    members_raw = _manifest_bytes(members)
    archive_sha256 = _sha256_bytes(archive_raw)
    members_sha256 = _sha256_bytes(members_raw)
    bundle_raw = _bundle_bytes(archive_sha256, members_sha256)
    bundle_sha256 = _sha256_bytes(bundle_raw)
    report_sha256 = str(report["report_sha256"])
    _, identity = _verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        expected_archive_sha256=archive_sha256,
        expected_members_sha256=members_sha256,
        expected_bundle_sha256=bundle_sha256,
        expected_report_sha256=report_sha256,
    )
    expected_identity = {
        "archive_sha256": EXPECTED_EVIDENCE_ARCHIVE_SHA256,
        "member_manifest_sha256": EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256,
        "bundle_sha256": EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256,
        "report_sha256": EXPECTED_REPORT_SHA256,
    }
    if any(identity[key] != value for key, value in expected_identity.items()):
        raise ValueError("generated evidence does not match the reviewed pins")
    created: list[tuple[Path, int, int]] = []
    try:
        for relative, raw in (
            (REPORT_PATH, report_raw),
            (ARCHIVE_PATH, archive_raw),
            (MEMBERS_PATH, members_raw),
            (BUNDLE_PATH, bundle_raw),
        ):
            output = repo_root / relative
            device, inode = _write_exclusive_owned(repo_root, Path(relative), raw)
            created.append((output, device, inode))
    except BaseException as exc:
        rollback_failed = False
        for output, device, inode in reversed(created):
            try:
                metadata = output.lstat()
                if metadata.st_dev == device and metadata.st_ino == inode:
                    output.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                rollback_failed = True
        if rollback_failed:
            raise RuntimeError("evidence publication failed and rollback was incomplete") from exc
        raise
    return identity


def verify_pinned_evidence(repo_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    failure_atlas._reject_symlink_ancestry(repo_root, name="repository root")
    repo_root = repo_root.resolve()
    failure_atlas._prohibited_path(repo_root, name="repository root")
    for value, name in (
        (EXPECTED_EVIDENCE_ARCHIVE_SHA256, "pinned archive SHA-256"),
        (EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256, "pinned manifest SHA-256"),
        (EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256, "pinned bundle SHA-256"),
        (EXPECTED_REPORT_SHA256, "pinned report SHA-256"),
    ):
        if not _is_sha256(value):
            raise ValueError(f"{name} has not been reviewed and pinned")
    archive_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(ARCHIVE_PATH),
        maximum=MAX_ARCHIVE_BYTES,
        name="V1.1 evidence archive",
    )[0]
    members_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(MEMBERS_PATH),
        maximum=MAX_MEMBER_MANIFEST_BYTES,
        name="V1.1 member manifest",
    )[0]
    bundle_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(BUNDLE_PATH),
        maximum=MAX_BUNDLE_CHECKSUM_BYTES,
        name="V1.1 bundle sidecar",
    )[0]
    external_report_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(REPORT_PATH),
        maximum=MAX_MEMBER_BYTES,
        name="V1.1 external audit report",
    )[0]
    report, identity = _verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        expected_archive_sha256=EXPECTED_EVIDENCE_ARCHIVE_SHA256,
        expected_members_sha256=EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256,
        expected_bundle_sha256=EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256,
        expected_report_sha256=EXPECTED_REPORT_SHA256,
    )
    if external_report_raw != _canonical_bytes(report) + b"\n":
        raise ValueError("external V1.1 audit contradicts the pinned archive")
    return report, identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("action", choices=("pack", "verify"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.action == "pack":
        identity = pack_evidence(arguments.repo_root)
        print(json.dumps(identity, sort_keys=True))
        return 0
    report, identity = verify_pinned_evidence(arguments.repo_root)
    print(
        json.dumps(
            {
                **identity,
                "decision": report["decision"],
                "clearance_evaluated_candidate_count": report[
                    "clearance_telemetry"
                ]["torsion"]["clearance_evaluated_candidate_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
