#!/usr/bin/env python3
"""Verify a repeatable Engine V2 D1 development report without rerunning docking."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
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


class D1ReportVerificationError(ValueError):
    """A persisted D1 development report is inconsistent."""


def _require_exact_bool(mapping: dict[str, Any], key: str, expected: bool) -> None:
    value = mapping.get(key)
    if type(value) is not bool or value is not expected:
        raise D1ReportVerificationError(f"{key} must be exactly {expected}")


def verify_report(path: Path) -> dict[str, Any]:
    report = RUNNER._load_json(path)
    if report.get("schema_id") != RUNNER.REPORT_SCHEMA_ID:
        raise D1ReportVerificationError("D1 report schema changed")
    if report.get("profile_id") != RUNNER.PROFILE_ID:
        raise D1ReportVerificationError("D1 report profile changed")
    if report.get("candidate_denominator") != RUNNER.CANDIDATE_DENOMINATOR:
        raise D1ReportVerificationError("D1 report denominator changed")
    if report.get("rmsd_threshold_angstrom") != RUNNER.RMSD_THRESHOLD_ANGSTROM:
        raise D1ReportVerificationError("D1 RMSD threshold changed")
    _require_exact_bool(report, "development_repeatable", True)
    _require_exact_bool(report, "result_informed_iteration_allowed", True)

    authority = report.get("authority")
    if type(authority) is not dict or not authority:
        raise D1ReportVerificationError("D1 authority map is invalid")
    for key, value in authority.items():
        if type(value) is not bool or value is not False:
            raise D1ReportVerificationError(f"D1 authority escalated: {key}")

    current = report.get("current")
    if type(current) is not dict:
        raise D1ReportVerificationError("D1 current summary is missing")
    cases = current.get("cases")
    aggregate = current.get("aggregate")
    if type(cases) is not list or len(cases) != RUNNER.CASE_COUNT:
        raise D1ReportVerificationError("D1 report must retain exactly 32 case rows")
    if type(aggregate) is not dict or aggregate.get("case_count") != RUNNER.CASE_COUNT:
        raise D1ReportVerificationError("D1 aggregate case count is invalid")
    case_ids = [row.get("case_id") if type(row) is dict else None for row in cases]
    if len(set(case_ids)) != RUNNER.CASE_COUNT:
        raise D1ReportVerificationError("D1 report case IDs are missing or duplicated")

    for count_name in (
        "preparation_success_count",
        "preparation_failure_count",
        "scored_case_count",
        "proposal_oracle_recovery_count",
        "valid_proposal_oracle_recovery_count",
        "top1_recovery_count",
        "top5_recovery_count",
        "invalid_top1_count",
        "top1_validity_unavailable_count",
    ):
        value = aggregate.get(count_name)
        if type(value) is not int or not 0 <= value <= RUNNER.CASE_COUNT:
            raise D1ReportVerificationError(f"invalid aggregate count: {count_name}")
    if (
        aggregate["preparation_success_count"]
        + aggregate["preparation_failure_count"]
        != RUNNER.CASE_COUNT
    ):
        raise D1ReportVerificationError("preparation denominator is not complete")
    if aggregate["scored_case_count"] > aggregate["preparation_success_count"]:
        raise D1ReportVerificationError("scored cases exceed prepared cases")

    observed_sha = report.get("report_sha256")
    if type(observed_sha) is not str or len(observed_sha) != 64:
        raise D1ReportVerificationError("report_sha256 is invalid")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    expected_sha = RUNNER._sha256_value(unsigned)
    if observed_sha != expected_sha:
        raise D1ReportVerificationError("report_sha256 does not match the report")

    return {
        "verified": True,
        "schema_id": RUNNER.REPORT_SCHEMA_ID,
        "case_count": RUNNER.CASE_COUNT,
        "report_sha256": observed_sha,
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
