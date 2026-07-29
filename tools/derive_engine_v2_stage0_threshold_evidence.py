#!/usr/bin/env python3
"""Derive frozen Stage 0 gates from non-holdout rc5 development ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    STAGE0_DIAGNOSTIC_CONTRACT_ID,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
)


SCHEMA_ID = "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
DERIVATION_POLICY_ID = "baseline_anchored_operational_gate/1.0.0"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("development metric denominator is empty")
    return sum(values) / len(values)


def _row_recovery(row: Mapping[str, object], top_k: int) -> float:
    if row.get("status") != "success":
        return 0.0
    values = row.get("rmsd_angstroms")
    if not isinstance(values, list) or len(values) != 5:
        raise ValueError("successful result does not retain five RMSDs")
    return float(min(float(value) for value in values[:top_k]) <= 2.0)


def _engine_diagnostics(row: Mapping[str, object]) -> Mapping[str, object]:
    diagnostics = row.get("engine_v2_diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise ValueError("rc5 Engine V2 diagnostics are missing")
    candidates = diagnostics.get("candidates")
    expected_count = 64 if diagnostics.get("preparation_status") == "success" else 0
    if not isinstance(candidates, list) or len(candidates) != expected_count:
        raise ValueError("fixed 64-slot diagnostic denominator is missing")
    return diagnostics


def _load_rows(paths: Sequence[Path]) -> tuple[list[dict[str, object]], dict[str, str]]:
    rows: list[dict[str, object]] = []
    hashes: dict[str, str] = {}
    for path in paths:
        if path.is_dir():
            receipt_paths = tuple(
                sorted(
                    receipt
                    for engine_id in ("engine_v2", "vina", "gnina")
                    for receipt in (path / engine_id).glob("*.json")
                )
            )
            if not receipt_paths:
                raise ValueError(f"development receipt directory is empty: {path}")
            for receipt_path in receipt_paths:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                result = receipt.get("result")
                if not isinstance(result, Mapping):
                    raise ValueError(f"execution receipt has no result: {receipt_path}")
                rows.append(dict(result))
                hashes[str(receipt_path)] = _sha256_path(receipt_path)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_rows = payload.get("rows")
        if not isinstance(source_rows, list):
            raise ValueError(f"development report has no rows: {path}")
        rows.extend(dict(row) for row in source_rows)
        hashes[str(path)] = _sha256_path(path)
    return rows, hashes


def derive(paths: Sequence[Path]) -> dict[str, object]:
    rows, source_hashes = _load_rows(paths)
    row_map = {
        (str(row.get("engine_id")), str(row.get("case_id"))): row for row in rows
    }
    if len(row_map) != len(rows):
        raise ValueError("development report rows are duplicated")
    case_ids = tuple(
        sorted({case_id for _, case_id in row_map})
    )
    if len(case_ids) < 8:
        raise ValueError("at least eight non-smoke development cases are required")
    if any(case_id not in FROZEN_PUBLIC_REDOCKING_CASE_IDS for case_id in case_ids):
        raise ValueError("development evidence contains a non-historical case")
    if set(case_ids) & set(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS):
        raise ValueError("development evidence contains engineering smoke cases")
    if set(case_ids) & set(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS):
        raise ValueError("development evidence contains fresh holdout cases")
    expected = {
        (engine_id, case_id)
        for engine_id in ("engine_v2", "vina", "gnina")
        for case_id in case_ids
    }
    if set(row_map) != expected:
        raise ValueError("development evidence is not failure-complete")

    preparation_unsupported: list[float] = []
    candidate_coverage: list[float] = []
    proposal_oracle: list[float] = []
    top1_selection_failures: list[float] = []
    top5_selection_failures: list[float] = []
    invalid_top1: list[float] = []
    case_failures: list[float] = []
    oracle_case_count = 0
    for case_id in case_ids:
        row = row_map[("engine_v2", case_id)]
        diagnostics = _engine_diagnostics(row)
        preparation_succeeded = diagnostics.get("preparation_status") == "success"
        preparation_unsupported.append(
            float(not preparation_succeeded)
        )
        case_failures.append(float(row.get("status") != "success"))
        if not preparation_succeeded:
            continue
        candidates = [
            candidate
            for candidate in diagnostics["candidates"]
            if candidate.get("status") == "success"
        ]
        candidate_coverage.append(len(candidates) / 64.0)
        oracle_success = any(float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in candidates)
        proposal_oracle.append(float(oracle_success))
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                float(candidate["score"]),
                int(candidate["proposal_index"]),
            ),
        )
        if oracle_success:
            oracle_case_count += 1
            top1_selection_failures.append(
                float(not ranked or float(ranked[0]["rmsd_angstrom"]) > 2.0)
            )
            top5_selection_failures.append(
                float(
                    len(ranked) < 5
                    or min(float(candidate["rmsd_angstrom"]) for candidate in ranked[:5]) > 2.0
                )
            )
        invalid_top1.append(
            float(
                not ranked
                or ranked[0].get("geometric_valid") is not True
                or ranked[0].get("chemical_valid") is not True
            )
        )

    if not candidate_coverage:
        raise ValueError("development evidence has no preparation-success cases")

    baseline_failures = {
        engine_id: _mean(
            [float(row_map[(engine_id, case_id)].get("status") != "success") for case_id in case_ids]
        )
        for engine_id in ("vina", "gnina")
    }
    baseline_top1 = {
        engine_id: _mean([_row_recovery(row_map[(engine_id, case_id)], 1) for case_id in case_ids])
        for engine_id in ("vina", "gnina")
    }
    baseline_top5 = {
        engine_id: _mean([_row_recovery(row_map[(engine_id, case_id)], 5) for case_id in case_ids])
        for engine_id in ("vina", "gnina")
    }
    best_baseline_failure = min(baseline_failures.values())
    weakest_baseline_top5 = min(baseline_top5.values())
    proposed = {
        "preparation_input_unsupported_rate": (
            "max",
            min(0.20, max(0.05, best_baseline_failure + 0.05)),
            _mean(preparation_unsupported),
            "min(0.20,max(0.05,best_baseline_failure_rate+0.05))",
        ),
        "candidate_generation_coverage": (
            "min",
            0.90,
            _mean(candidate_coverage),
            "fixed_operational_floor_90pct_of_64_predeclared_slots",
        ),
        "proposal_oracle_2a_recovery": (
            "min",
            max(0.25, weakest_baseline_top5 - 0.10),
            _mean(proposal_oracle),
            "max(0.25,weakest_vina_gnina_top5_recovery-0.10)",
        ),
        "top1_selection_failure_given_oracle": (
            "max",
            0.50,
            _mean(top1_selection_failures) if top1_selection_failures else 1.0,
            "predeclared_half_of_oracle_successes_maximum",
        ),
        "top5_selection_failure_given_oracle": (
            "max",
            0.20,
            _mean(top5_selection_failures) if top5_selection_failures else 1.0,
            "predeclared_one_in_five_oracle_successes_maximum",
        ),
        "invalid_top1_pose_rate": (
            "max",
            0.20,
            _mean(invalid_top1),
            "predeclared_one_in_five_all_case_denominator_maximum",
        ),
        "case_level_failure_rate": (
            "max",
            min(0.20, max(0.10, best_baseline_failure + 0.05)),
            _mean(case_failures),
            "min(0.20,max(0.10,best_baseline_failure_rate+0.05))",
        ),
    }
    for _, value, observed, _ in proposed.values():
        if not all(math.isfinite(float(item)) and 0.0 <= float(item) <= 1.0 for item in (value, observed)):
            raise ValueError("derived threshold evidence is non-finite")
    evidence: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "derivation_policy_id": DERIVATION_POLICY_ID,
        "corpus_id": "historical_300_reclassified_development_rc5_subset",
        "case_count": len(case_ids),
        "case_ids_sha256": _sha256(list(case_ids)),
        "contains_engineering_smoke": False,
        "contains_primary_holdout": False,
        "contains_fresh_internal_blind_holdout": False,
        "diagnostic_contract_id": STAGE0_DIAGNOSTIC_CONTRACT_ID,
        "sample_size_justification": (
            "minimum eight-case implementation-development slice; gates are "
            "baseline-anchored promotion targets, not fitted confidence bounds"
        ),
        "metric_denominator_policy": {
            "preparation_input_unsupported_rate": "all_cases",
            "case_level_failure_rate": "all_cases",
            "candidate_generation_coverage": "preparation_success_cases",
            "proposal_oracle_2a_recovery": "preparation_success_cases",
            "invalid_top1_pose_rate": "preparation_success_cases",
            "top1_selection_failure_given_oracle": "proposal_oracle_success_cases",
            "top5_selection_failure_given_oracle": "proposal_oracle_success_cases",
        },
        "preparation_success_case_count": len(candidate_coverage),
        "source_reports_sha256": source_hashes,
        "oracle_success_case_count": oracle_case_count,
        "metrics": {
            metric: {
                "operator": operator,
                "observed_estimate": observed,
                "proposed_threshold": value,
                "derivation_rule": rule,
            }
            for metric, (operator, value, observed, rule) in proposed.items()
        },
        "paired_baseline_engines": ["vina", "gnina"],
        "baseline_observed": {
            "failure_rates": baseline_failures,
            "top1_2a_recovery_rates": baseline_top1,
            "top5_2a_recovery_rates": baseline_top5,
        },
        "baseline_noninferiority_margins": {
            "top1_2a_recovery_delta": -0.10,
            "top5_2a_recovery_delta": -0.10,
        },
        "runtime_role": "descriptive_only",
        "scientific_validation_claimed": False,
        "public_claim_eligible": False,
    }
    evidence["evidence_sha256"] = _sha256(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        action="append",
        required=True,
        help="partial/full report JSON or a receipts directory containing engine subdirs",
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = derive(tuple(path.resolve() for path in arguments.report))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(evidence) + b"\n")
    print(evidence["evidence_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
