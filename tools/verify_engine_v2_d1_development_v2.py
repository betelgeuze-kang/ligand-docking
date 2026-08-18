#!/usr/bin/env python3
"""Verify a D1 report by replaying every derivable persisted invariant."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
import math
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_engine_v2_d1_development_v1",
    ROOT / "tools/run_engine_v2_d1_development_v1.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load D1 development implementation")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_FIELDS = {
    "case_id",
    "preparation_success",
    "preparation_failure_code",
    "scored_candidate_count",
    "typed_failure_count",
    "proposal_oracle_recovered",
    "valid_proposal_oracle_recovered",
    "top1_recovered",
    "top5_recovered",
    "top1_valid",
    "top1_lane",
    "top1_slot_index",
    "top1_final_rmsd_angstrom",
    "best_final_rmsd_angstrom",
    "scoring_regret_angstrom",
    "source_sha256",
}
AGG_FIELDS = {
    "case_count",
    "preparation_success_count",
    "preparation_failure_count",
    "scored_case_count",
    "proposal_oracle_recovery_count",
    "valid_proposal_oracle_recovery_count",
    "top1_recovery_count",
    "top5_recovery_count",
    "invalid_top1_count",
    "top1_validity_unavailable_count",
    "mean_scoring_regret_angstrom",
    "preparation_failure_distribution",
    "typed_failure_distribution",
    "lane_contribution",
}
LANE_FIELDS = {
    "candidate_count",
    "typed_failure_count",
    "scored_count",
    "proposal_oracle_candidate_count",
    "valid_proposal_oracle_candidate_count",
    "final_native_like_candidate_count",
    "exact_valid_candidate_count",
    "top1_case_count",
    "top5_native_like_candidate_count",
}
METRICS = (
    "proposal_oracle_recovered",
    "valid_proposal_oracle_recovered",
    "top1_recovered",
    "top5_recovered",
)
COMPARE_FIELDS = {
    f"{direction}_{metric}_case_ids"
    for metric in METRICS
    for direction in ("new", "lost")
}
AUTH_FIELDS = {
    "reservation_authorized",
    "molecular_holdout_execution_authorized",
    "fresh_128_execution_authorized",
    "stage0_admission_authorized",
    "benchmark_claim_authorized",
    "scientific_claim_authorized",
    "product_authorized",
    "customer_pose_emission_authorized",
}
REPORT_FIELDS = {
    "schema_id",
    "profile_id",
    "profile_sha256",
    "profile_projection_sha256",
    "manifest_sha256",
    "manifest_projection_sha256",
    "fresh_registry_sha256",
    "development_repeatable",
    "result_informed_iteration_allowed",
    "candidate_denominator",
    "rmsd_threshold_angstrom",
    "current",
    "baseline",
    "authority",
    "report_sha256",
}


class D1ReportVerificationError(ValueError):
    """A persisted D1 report is self-hashed but semantically inconsistent."""


def _exact_object(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise D1ReportVerificationError(f"{name} has an invalid field set")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise D1ReportVerificationError(f"{name} must be boolean")
    return value


def _optional_boolean(value: Any, name: str) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise D1ReportVerificationError(f"{name} must be boolean or null")


def _integer(value: Any, name: str, lo: int, hi: int) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise D1ReportVerificationError(f"{name} must be in [{lo},{hi}]")
    return value


def _finite(value: Any, name: str, lo: float = -math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise D1ReportVerificationError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < lo:
        raise D1ReportVerificationError(f"{name} is not finite/in range")
    return result


def _optional_finite(value: Any, name: str, lo: float = -math.inf) -> float | None:
    return None if value is None else _finite(value, name, lo)


def _sha(value: Any, name: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        raise D1ReportVerificationError(f"{name} must be lowercase SHA-256")
    return value


def _text(value: Any, name: str, maximum: int = 256) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise D1ReportVerificationError(f"{name} must be non-empty text")
    return value


def _case_id(value: Any, name: str) -> str:
    if type(value) is not str or RUNNER.CASE_ID_RE.fullmatch(value) is None:
        raise D1ReportVerificationError(f"{name} is not a valid case ID")
    return value


def _verify_case(raw: Any, index: int) -> dict[str, Any]:
    row = _exact_object(raw, CASE_FIELDS, f"case[{index}]")
    cid = _case_id(row["case_id"], f"case[{index}].case_id")
    prepared = _boolean(row["preparation_success"], f"{cid}.preparation_success")
    scored = _integer(row["scored_candidate_count"], f"{cid}.scored", 0, 64)
    failed = _integer(row["typed_failure_count"], f"{cid}.failed", 0, 64)
    proposal = _boolean(row["proposal_oracle_recovered"], f"{cid}.proposal")
    valid_proposal = _boolean(
        row["valid_proposal_oracle_recovered"], f"{cid}.valid_proposal"
    )
    top1 = _boolean(row["top1_recovered"], f"{cid}.top1")
    top5 = _boolean(row["top5_recovered"], f"{cid}.top5")
    top1_valid = _optional_boolean(row["top1_valid"], f"{cid}.top1_valid")
    top1_rmsd = _optional_finite(
        row["top1_final_rmsd_angstrom"], f"{cid}.top1_rmsd", 0.0
    )
    best_rmsd = _optional_finite(
        row["best_final_rmsd_angstrom"], f"{cid}.best_rmsd", 0.0
    )
    regret = _optional_finite(row["scoring_regret_angstrom"], f"{cid}.regret", 0.0)
    _sha(row["source_sha256"], f"{cid}.source_sha256")
    if valid_proposal and not proposal:
        raise D1ReportVerificationError(f"{cid}: valid proposal needs proposal")
    if top1 and not top5:
        raise D1ReportVerificationError(f"{cid}: Top-1 needs Top-5")

    if not prepared:
        _text(row["preparation_failure_code"], f"{cid}.failure_code")
        if scored or failed or proposal or valid_proposal or top1 or top5:
            raise D1ReportVerificationError(f"{cid}: invalid preparation-failure state")
        if any(
            row[key] is not None
            for key in (
                "top1_valid",
                "top1_lane",
                "top1_slot_index",
                "top1_final_rmsd_angstrom",
                "best_final_rmsd_angstrom",
                "scoring_regret_angstrom",
            )
        ):
            raise D1ReportVerificationError(f"{cid}: failed preparation has pose data")
    else:
        if row["preparation_failure_code"] is not None or scored + failed != 64:
            raise D1ReportVerificationError(f"{cid}: prepared denominator mismatch")
        if scored == 0:
            if proposal or valid_proposal or top1 or top5:
                raise D1ReportVerificationError(f"{cid}: unscored recovery")
            if any(
                row[key] is not None
                for key in (
                    "top1_valid",
                    "top1_lane",
                    "top1_slot_index",
                    "top1_final_rmsd_angstrom",
                    "best_final_rmsd_angstrom",
                    "scoring_regret_angstrom",
                )
            ):
                raise D1ReportVerificationError(f"{cid}: unscored pose data")
        else:
            _text(row["top1_lane"], f"{cid}.top1_lane", 128)
            _integer(row["top1_slot_index"], f"{cid}.top1_slot", 0, 63)
            if top1_rmsd is None or best_rmsd is None or regret is None:
                raise D1ReportVerificationError(f"{cid}: missing scored RMSD state")
            if best_rmsd > top1_rmsd + 1.0e-12:
                raise D1ReportVerificationError(f"{cid}: best RMSD exceeds Top-1")
            if not math.isclose(
                regret, top1_rmsd - best_rmsd, rel_tol=0.0, abs_tol=1.0e-12
            ):
                raise D1ReportVerificationError(f"{cid}: scoring regret mismatch")
            if top1 is not (top1_rmsd <= RUNNER.RMSD_THRESHOLD_ANGSTROM):
                raise D1ReportVerificationError(f"{cid}: Top-1/RMSD mismatch")
    return row


def _distribution(value: Any, name: str) -> dict[str, int]:
    if type(value) is not dict or list(value) != sorted(value):
        raise D1ReportVerificationError(f"{name} must be a sorted object")
    result: dict[str, int] = {}
    for key, raw in value.items():
        result[_text(key, f"{name}.key")] = _integer(raw, f"{name}.{key}", 1, 2048)
    return result


def _verify_lanes(
    value: Any,
    prepared: int,
    total_scored: int,
    total_failed: int,
    scored_cases: int,
) -> None:
    if type(value) is not dict or list(value) != sorted(value):
        raise D1ReportVerificationError("lane_contribution must be sorted")
    totals: Counter[str] = Counter()
    for lane, raw in value.items():
        _text(lane, "lane", 128)
        if type(raw) is not dict or not set(raw).issubset(LANE_FIELDS):
            raise D1ReportVerificationError(f"lane {lane} field set")
        if "candidate_count" not in raw:
            raise D1ReportVerificationError(f"lane {lane} candidate_count missing")
        counts = {
            key: _integer(number, f"{lane}.{key}", 1, 2048)
            for key, number in raw.items()
        }
        totals.update(counts)
        if counts.get("scored_count", 0) + counts.get(
            "typed_failure_count", 0
        ) != counts["candidate_count"]:
            raise D1ReportVerificationError(f"lane {lane} denominator mismatch")
        if counts.get("valid_proposal_oracle_candidate_count", 0) > counts.get(
            "proposal_oracle_candidate_count", 0
        ):
            raise D1ReportVerificationError(f"lane {lane} valid proposal mismatch")
        for key in LANE_FIELDS - {
            "candidate_count",
            "scored_count",
            "typed_failure_count",
        }:
            if counts.get(key, 0) > counts.get("scored_count", 0):
                raise D1ReportVerificationError(f"lane {lane} {key} exceeds scored")
    expected = {
        "candidate_count": prepared * 64,
        "scored_count": total_scored,
        "typed_failure_count": total_failed,
        "top1_case_count": scored_cases,
    }
    for key, number in expected.items():
        if totals[key] != number:
            raise D1ReportVerificationError(f"lane total {key} mismatch")


def _verify_summary(raw: Any, name: str) -> dict[str, Any]:
    summary = _exact_object(raw, {"cases", "aggregate"}, name)
    if type(summary["cases"]) is not list or len(summary["cases"]) != 32:
        raise D1ReportVerificationError(f"{name}: 32 case rows required")
    cases = [_verify_case(row, index) for index, row in enumerate(summary["cases"])]
    ids = [row["case_id"] for row in cases]
    if len(set(ids)) != 32:
        raise D1ReportVerificationError(f"{name}: duplicate case IDs")
    aggregate = _exact_object(summary["aggregate"], AGG_FIELDS, f"{name}.aggregate")
    prepared = [row for row in cases if row["preparation_success"]]
    scored_cases = [row for row in prepared if row["scored_candidate_count"] > 0]
    expected = {
        "case_count": 32,
        "preparation_success_count": len(prepared),
        "preparation_failure_count": 32 - len(prepared),
        "scored_case_count": len(scored_cases),
        "proposal_oracle_recovery_count": sum(
            row["proposal_oracle_recovered"] for row in cases
        ),
        "valid_proposal_oracle_recovery_count": sum(
            row["valid_proposal_oracle_recovered"] for row in cases
        ),
        "top1_recovery_count": sum(row["top1_recovered"] for row in cases),
        "top5_recovery_count": sum(row["top5_recovered"] for row in cases),
        "invalid_top1_count": sum(
            row["top1_valid"] is False for row in scored_cases
        ),
        "top1_validity_unavailable_count": sum(
            row["top1_valid"] is None for row in scored_cases
        ),
    }
    for key, wanted in expected.items():
        if _integer(aggregate[key], f"{name}.{key}", 0, 32) != wanted:
            raise D1ReportVerificationError(f"{name}.{key} case-row mismatch")
    regrets = [row["scoring_regret_angstrom"] for row in scored_cases]
    observed_mean = _optional_finite(
        aggregate["mean_scoring_regret_angstrom"], f"{name}.mean_regret", 0.0
    )
    wanted_mean = sum(regrets) / len(regrets) if regrets else None
    if (wanted_mean is None) != (observed_mean is None) or (
        wanted_mean is not None
        and not math.isclose(
            wanted_mean, observed_mean, rel_tol=0.0, abs_tol=1.0e-12
        )
    ):
        raise D1ReportVerificationError(f"{name}: mean regret mismatch")
    preparation = _distribution(
        aggregate["preparation_failure_distribution"], f"{name}.prep_failures"
    )
    wanted_preparation = dict(
        sorted(
            Counter(
                row["preparation_failure_code"]
                for row in cases
                if not row["preparation_success"]
            ).items()
        )
    )
    if preparation != wanted_preparation:
        raise D1ReportVerificationError(f"{name}: preparation distribution mismatch")
    typed = _distribution(aggregate["typed_failure_distribution"], f"{name}.typed")
    total_scored = sum(row["scored_candidate_count"] for row in prepared)
    total_failed = sum(row["typed_failure_count"] for row in prepared)
    if sum(typed.values()) != total_failed:
        raise D1ReportVerificationError(f"{name}: typed failure denominator mismatch")
    _verify_lanes(
        aggregate["lane_contribution"],
        len(prepared),
        total_scored,
        total_failed,
        len(scored_cases),
    )
    return {"cases": cases, "aggregate": aggregate}


def _metric_ids(summary: dict[str, Any], metric: str) -> set[str]:
    return {row["case_id"] for row in summary["cases"] if row[metric] is True}


def _verify_baseline(raw: Any, current: dict[str, Any]) -> None:
    if raw is None:
        return
    baseline = _exact_object(
        raw,
        {"manifest_sha256", "manifest_projection_sha256", "summary", "comparison"},
        "baseline",
    )
    _sha(baseline["manifest_sha256"], "baseline.manifest_sha256")
    _sha(
        baseline["manifest_projection_sha256"], "baseline.projection_sha256"
    )
    other = _verify_summary(baseline["summary"], "baseline.summary")
    current_ids = [row["case_id"] for row in current["cases"]]
    if [row["case_id"] for row in other["cases"]] != current_ids:
        raise D1ReportVerificationError("baseline ordered cohort mismatch")
    comparison = _exact_object(
        baseline["comparison"], COMPARE_FIELDS, "baseline.comparison"
    )
    allowed = set(current_ids)
    for metric in METRICS:
        now, before = _metric_ids(current, metric), _metric_ids(other, metric)
        for direction, wanted in (
            ("new", sorted(now - before)),
            ("lost", sorted(before - now)),
        ):
            key = f"{direction}_{metric}_case_ids"
            values = comparison[key]
            if type(values) is not list:
                raise D1ReportVerificationError(f"{key} must be list")
            observed = [_case_id(value, key) for value in values]
            if observed != sorted(set(observed)) or not set(observed) <= allowed:
                raise D1ReportVerificationError(f"{key} invalid")
            if observed != wanted:
                raise D1ReportVerificationError(f"{key} case-row mismatch")


def verify_report(path: Path) -> dict[str, Any]:
    report = RUNNER._load_json(path)
    _exact_object(report, REPORT_FIELDS, "report")
    if report["schema_id"] != RUNNER.REPORT_SCHEMA_ID:
        raise D1ReportVerificationError("D1 report schema changed")
    if report["profile_id"] != RUNNER.PROFILE_ID:
        raise D1ReportVerificationError("D1 profile changed")
    for key in (
        "profile_sha256",
        "profile_projection_sha256",
        "manifest_sha256",
        "manifest_projection_sha256",
        "fresh_registry_sha256",
        "report_sha256",
    ):
        _sha(report[key], key)
    if report["candidate_denominator"] != 64:
        raise D1ReportVerificationError("candidate denominator changed")
    if _finite(report["rmsd_threshold_angstrom"], "rmsd_threshold", 0.0) != 2.0:
        raise D1ReportVerificationError("RMSD threshold changed")
    if (
        report["development_repeatable"] is not True
        or report["result_informed_iteration_allowed"] is not True
    ):
        raise D1ReportVerificationError("development policy changed")
    authority = _exact_object(report["authority"], AUTH_FIELDS, "authority")
    if any(value is not False for value in authority.values()):
        raise D1ReportVerificationError("authority escalated")
    current = _verify_summary(report["current"], "current")
    _verify_baseline(report["baseline"], current)
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256")
    if observed != RUNNER._sha256_value(unsigned):
        raise D1ReportVerificationError("report SHA mismatch")
    return {
        "verified": True,
        "schema_id": RUNNER.REPORT_SCHEMA_ID,
        "case_count": 32,
        "report_sha256": observed,
        "authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_report(args.report)
    except (D1ReportVerificationError, RUNNER.D1DevelopmentError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
