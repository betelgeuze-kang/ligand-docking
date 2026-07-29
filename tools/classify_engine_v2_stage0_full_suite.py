#!/usr/bin/env python3
"""Classify a Stage 0 full-suite JUnit receipt into explicit execution lanes."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


SCHEMA_ID = "betelgeuze.engine_v2_stage0_full_suite_classification/1.0.0"
_PRODUCT_TOKENS = (
    "alk2",
    "aqp1",
    "caix",
    "glut1",
    "gpcr",
    "lbdhodh",
    "ligand_scaleup",
    "pde",
    "platform",
    "product",
    "refine_tier",
    "release",
    "sarscov2",
    "tcruzi",
    "transporter",
    "wetlab",
)
_LEGACY_CONTRACT_CLASSES = {
    "tests.mobile.test_mobile_api_contracts",
    "tests.unit.test_abcd_product_capabilities",
    "tests.unit.test_abcd_product_capabilities_phase2",
    "tests.unit.test_runtime_inputs",
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


def _classification(classname: str, message: str) -> tuple[str, str]:
    lowered = f"{classname}\n{message}".lower()
    if (
        "rust hip backend is required but unavailable" in lowered
        or "pinned inputs could not be monitored for mutation" in lowered
    ):
        return "host_capability_missing", "host_backend_or_inotify_unavailable"
    if classname.startswith("tests.validation.") or (
        "test_run_casp17_internal_physics_baseline_predictor" in classname
        and "filenotfounderror" in lowered
    ):
        return "local_evidence_required", "native_or_local_evidence_not_materialized"
    fixture_signal = any(
        token in lowered
        for token in (
            "filenotfounderror",
            "no such file or directory",
            "calledprocesserror",
            "missing_required_claim_inputs",
            "ligand_source_unavailable_for_materialization",
        )
    )
    if fixture_signal and any(token in classname.lower() for token in _PRODUCT_TOKENS):
        return "product_fixture_dependent", "product_or_evidence_fixture_missing"
    if fixture_signal:
        return "fixture_dependent", "repository_fixture_missing_or_upstream_command_failed"
    if classname in _LEGACY_CONTRACT_CLASSES:
        return "legacy_deterministic", "legacy_expectation_differs_from_current_contract"
    return "actual_regression", "assertion_or_contract_failure_requires_owner_review"


def build_classification(junit_path: Path) -> dict[str, Any]:
    junit_bytes = junit_path.read_bytes()
    root = ET.fromstring(junit_bytes)
    rows: list[dict[str, str]] = []
    for case in root.iter("testcase"):
        outcome = case.find("failure")
        kind = "failure"
        if outcome is None:
            outcome = case.find("error")
            kind = "error"
        if outcome is None:
            continue
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        message = "\n".join(
            part
            for part in (outcome.attrib.get("message", ""), outcome.text or "")
            if part
        )
        category, rule_id = _classification(classname, message)
        rows.append(
            {
                "category": category,
                "classname": classname,
                "kind": kind,
                "message_sha256": _sha256_bytes(message.encode("utf-8")),
                "name": name,
                "rule_id": rule_id,
            }
        )
    rows.sort(key=lambda row: (row["classname"], row["name"], row["kind"]))
    category_counts = Counter(row["category"] for row in rows)
    kind_counts = Counter(row["kind"] for row in rows)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "source_junit_path": str(junit_path),
        "source_junit_sha256": _sha256_bytes(junit_bytes),
        "historical_pr_run": {"failed": 216, "errors": 3},
        "current_reproduction": {
            "failed": kind_counts["failure"],
            "errors": kind_counts["error"],
            "nonpassing_total": len(rows),
        },
        "historical_delta": {
            "failed": kind_counts["failure"] - 216,
            "errors": kind_counts["error"] - 3,
        },
        "category_counts": {
            category: category_counts.get(category, 0)
            for category in (
                "actual_regression",
                "fixture_dependent",
                "host_capability_missing",
                "local_evidence_required",
                "legacy_deterministic",
                "product_fixture_dependent",
            )
        },
        "all_outcomes_classified": len(rows) == sum(category_counts.values()),
        "recommended_execution_boundary": "official_tiered_suites",
        "rows": rows,
    }
    payload["receipt_sha256"] = _sha256_bytes(_canonical_bytes(payload))
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    payload = build_classification(arguments.junit)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(payload["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
