#!/usr/bin/env python3
"""Analyze Scorer v1 terms on contaminated development receipts only."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Mapping, Sequence

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_PROPOSAL_MODES,
)


SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_development_analysis/1.1.0"
TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
)
CALIBRATION_MULTIPLIER_GRID = (0.0, 0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0)


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


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        stop = cursor + 1
        while stop < len(order) and values[order[stop]] == values[order[cursor]]:
            stop += 1
        average = (cursor + 1 + stop) / 2.0
        for position in range(cursor, stop):
            ranks[order[position]] = average
        cursor = stop
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = statistics.mean(left_ranks)
    right_mean = statistics.mean(right_ranks)
    numerator = sum(
        (x - left_mean) * (y - right_mean)
        for x, y in zip(left_ranks, right_ranks, strict=True)
    )
    left_scale = sum((value - left_mean) ** 2 for value in left_ranks)
    right_scale = sum((value - right_mean) ** 2 for value in right_ranks)
    denominator = math.sqrt(left_scale * right_scale)
    return None if denominator == 0.0 else numerator / denominator


def _candidate_terms(candidate: Mapping[str, object]) -> dict[str, float]:
    encoded = candidate.get("score_term_binary64_hex")
    if not isinstance(encoded, Mapping) or set(encoded) != {*TERM_NAMES, "total_score"}:
        raise ValueError("candidate does not contain the complete scorer term vector")
    decoded: dict[str, float] = {}
    for name in (*TERM_NAMES, "total_score"):
        value = encoded[name]
        if not isinstance(value, str):
            raise ValueError("candidate scorer term is not binary64 hex")
        number = float.fromhex(value)
        if not math.isfinite(number) or number.hex() != value:
            raise ValueError("candidate scorer term is not canonical finite binary64")
        decoded[name] = number
    if not math.isclose(
        decoded["total_score"],
        sum(decoded[name] for name in TERM_NAMES),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("candidate scorer term total is inconsistent")
    return decoded


def _ranked(
    candidates: Sequence[Mapping[str, object]], score: Mapping[int, float]
) -> list[Mapping[str, object]]:
    return sorted(
        candidates,
        key=lambda candidate: (
            score[int(candidate["proposal_index"])],
            int(candidate["proposal_index"]),
        ),
    )


def _recovered(candidates: Sequence[Mapping[str, object]], top_k: int) -> bool:
    return bool(candidates) and any(
        float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in candidates[:top_k]
    )


def _calibrated_score(
    row: Mapping[str, object], multipliers: Mapping[str, float]
) -> float:
    terms = row["terms"]
    if not isinstance(terms, Mapping):
        raise ValueError("calibration row has no term vector")
    return sum(float(terms[name]) * multipliers[name] for name in TERM_NAMES)


def _pairwise_violations(
    cases: Sequence[Sequence[Mapping[str, object]]],
    multipliers: Mapping[str, float],
) -> tuple[int, int]:
    violations = 0
    denominator = 0
    for candidates in cases:
        positives = [row for row in candidates if float(row["rmsd_angstrom"]) <= 2.0]
        negatives = [row for row in candidates if float(row["rmsd_angstrom"]) > 2.0]
        for positive in positives:
            positive_score = _calibrated_score(positive, multipliers)
            for negative in negatives:
                denominator += 1
                if positive_score >= _calibrated_score(negative, multipliers):
                    violations += 1
    return violations, denominator


def _fit_multipliers(
    cases: Sequence[Sequence[Mapping[str, object]]],
) -> dict[str, float]:
    selected = {name: 1.0 for name in TERM_NAMES}
    for _ in range(3):
        changed = False
        for name in TERM_NAMES:
            candidates: list[tuple[tuple[float, float, float], float]] = []
            for value in CALIBRATION_MULTIPLIER_GRID:
                trial = {**selected, name: value}
                violations, denominator = _pairwise_violations(cases, trial)
                rate = violations / denominator if denominator else 1.0
                regularization = sum(abs(multiplier - 1.0) for multiplier in trial.values())
                candidates.append(((rate, regularization, value), value))
            value = min(candidates, key=lambda row: row[0])[1]
            if value != selected[name]:
                selected[name] = value
                changed = True
        if not changed:
            break
    return selected


def _calibration_recovery(
    candidates: Sequence[Mapping[str, object]],
    multipliers: Mapping[str, float],
) -> tuple[bool, bool, int]:
    ranked = sorted(
        candidates,
        key=lambda row: (
            _calibrated_score(row, multipliers),
            int(row["proposal_index"]),
        ),
    )
    return (
        _recovered(ranked, 1),
        _recovered(ranked, 5),
        int(ranked[0]["proposal_index"]),
    )


def analyze_results(
    results: Sequence[Mapping[str, object]],
    *,
    source_receipts_sha256: Mapping[str, str],
) -> dict[str, object]:
    case_ids = tuple(str(result.get("case_id", "")) for result in results)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("development result cases are duplicated")
    historical = set(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    forbidden = set(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS) | set(
        PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
    )
    if not case_ids or any(case_id not in historical for case_id in case_ids):
        raise ValueError("score-term analysis requires historical development cases")
    if set(case_ids) & forbidden:
        raise ValueError("score-term analysis rejects smoke and fresh holdout cases")

    cases: list[dict[str, object]] = []
    calibration_cases: list[tuple[str, list[dict[str, object]]]] = []
    per_term: dict[str, dict[str, list[float]]] = {
        name: {
            "absolute_values": [],
            "candidate_rmsd_correlations": [],
            "case_medians": [],
            "ligand_atom_counts": [],
        }
        for name in TERM_NAMES
    }
    mode_rows: dict[str, dict[str, object]] = {
        mode: {
            "candidate_count": 0,
            "native_like_candidate_count": 0,
            "valid_candidate_count": 0,
            "duplicate_candidate_count": 0,
            "execution_failure_count": 0,
            "oracle_contribution_case_count": 0,
            "best_oracle_case_count": 0,
            "scores": [],
            "failed_check_counts": Counter(),
            "refinement_attempt_count": 0,
            "refinement_penalty_reduced_count": 0,
            "refinement_translated_count": 0,
            "refinement_rotated_count": 0,
        }
        for mode in PUBLIC_REDOCKING_PROPOSAL_MODES
    }
    failed_check_counts: Counter[str] = Counter()
    refinement_attempt_count = 0
    refinement_penalty_reduced_count = 0
    refinement_translated_count = 0
    refinement_rotated_count = 0
    for result in results:
        if result.get("engine_id") != "engine_v2":
            raise ValueError("score-term analysis requires Engine V2 results")
        diagnostics = result.get("engine_v2_diagnostics")
        if not isinstance(diagnostics, Mapping):
            raise ValueError("Engine V2 diagnostics are missing")
        if result.get("status") != "success":
            if diagnostics.get("preparation_status") != "failure":
                raise ValueError("failed result has no typed preparation failure")
            failure_code = str(diagnostics.get("preparation_failure_code", ""))
            if not failure_code:
                raise ValueError("failed result has no preparation failure code")
            cases.append(
                {
                    "case_id": result["case_id"],
                    "scorer_analysis_status": "excluded_preparation_failure",
                    "preparation_failure_code": failure_code,
                    "candidate_success_count": 0,
                }
            )
            continue
        raw_candidates = diagnostics.get("candidates")
        if not isinstance(raw_candidates, list) or len(raw_candidates) != 64:
            raise ValueError("fixed 64-slot candidate diagnostics are missing")
        for candidate in raw_candidates:
            if not isinstance(candidate, Mapping) or candidate.get("status") != "failure":
                continue
            mode = str(candidate.get("proposal_mode", ""))
            if mode:
                if mode not in mode_rows:
                    raise ValueError("failed candidate proposal mode is unsupported")
                mode_rows[mode]["execution_failure_count"] = (
                    int(mode_rows[mode]["execution_failure_count"]) + 1
                )
        candidates = [
            candidate
            for candidate in raw_candidates
            if isinstance(candidate, Mapping) and candidate.get("status") == "success"
        ]
        if not candidates:
            raise ValueError("development case has no successful scored candidates")
        coordinate_counts = Counter(
            str(candidate.get("coordinate_fingerprint_sha256", ""))
            for candidate in candidates
        )
        case_oracle_modes: set[str] = set()
        best_oracle_candidate = min(
            candidates,
            key=lambda candidate: (
                float(candidate["rmsd_angstrom"]),
                int(candidate["proposal_index"]),
            ),
        )
        for candidate in candidates:
            mode = str(candidate.get("proposal_mode", ""))
            if mode not in mode_rows:
                raise ValueError("candidate proposal mode is missing or unsupported")
            coordinate_sha256 = str(
                candidate.get("coordinate_fingerprint_sha256", "")
            )
            if len(coordinate_sha256) != 64:
                raise ValueError("candidate coordinate fingerprint is missing")
            accumulator = mode_rows[mode]
            accumulator["candidate_count"] = int(accumulator["candidate_count"]) + 1
            rmsd = float(candidate["rmsd_angstrom"])
            if rmsd <= 2.0:
                accumulator["native_like_candidate_count"] = (
                    int(accumulator["native_like_candidate_count"]) + 1
                )
                case_oracle_modes.add(mode)
            if (
                candidate.get("geometric_valid") is True
                and candidate.get("chemical_valid") is True
            ):
                accumulator["valid_candidate_count"] = (
                    int(accumulator["valid_candidate_count"]) + 1
                )
            if coordinate_counts[coordinate_sha256] > 1:
                accumulator["duplicate_candidate_count"] = (
                    int(accumulator["duplicate_candidate_count"]) + 1
                )
            scores = accumulator["scores"]
            if not isinstance(scores, list):
                raise AssertionError("mode score accumulator is invalid")
            scores.append(float(candidate["score"]))
            raw_failed_checks = candidate.get("posebusters_failed_check_ids", [])
            if not isinstance(raw_failed_checks, list):
                raise ValueError("candidate PoseBusters failed checks are invalid")
            mode_failures = accumulator["failed_check_counts"]
            if not isinstance(mode_failures, Counter):
                raise AssertionError("mode failure accumulator is invalid")
            for check_id in raw_failed_checks:
                check = str(check_id)
                failed_check_counts[check] += 1
                mode_failures[check] += 1
            receipt_sha256 = str(candidate.get("refinement_receipt_sha256", ""))
            if receipt_sha256:
                initial = float.fromhex(
                    str(candidate["refinement_initial_penalty_binary64_hex"])
                )
                final = float.fromhex(
                    str(candidate["refinement_final_penalty_binary64_hex"])
                )
                accepted_steps = int(candidate["refinement_accepted_steps"])
                refinement_attempt_count += 1
                accumulator["refinement_attempt_count"] = (
                    int(accumulator["refinement_attempt_count"]) + 1
                )
                if final < initial:
                    refinement_penalty_reduced_count += 1
                    accumulator["refinement_penalty_reduced_count"] = (
                        int(accumulator["refinement_penalty_reduced_count"]) + 1
                    )
                if accepted_steps > 0:
                    refinement_translated_count += 1
                    accumulator["refinement_translated_count"] = (
                        int(accumulator["refinement_translated_count"]) + 1
                    )
                accepted_rotation_steps = int(
                    candidate.get("refinement_accepted_rotation_steps", 0)
                )
                if accepted_rotation_steps > 0:
                    refinement_rotated_count += 1
                    accumulator["refinement_rotated_count"] = (
                        int(accumulator["refinement_rotated_count"]) + 1
                    )
        for mode in case_oracle_modes:
            mode_rows[mode]["oracle_contribution_case_count"] = (
                int(mode_rows[mode]["oracle_contribution_case_count"]) + 1
            )
        best_mode = str(best_oracle_candidate["proposal_mode"])
        mode_rows[best_mode]["best_oracle_case_count"] = (
            int(mode_rows[best_mode]["best_oracle_case_count"]) + 1
        )
        terms = {
            int(candidate["proposal_index"]): _candidate_terms(candidate)
            for candidate in candidates
        }
        calibration_cases.append(
            (
                str(result["case_id"]),
                [
                    {
                        "proposal_index": int(candidate["proposal_index"]),
                        "rmsd_angstrom": float(candidate["rmsd_angstrom"]),
                        "terms": terms[int(candidate["proposal_index"])],
                    }
                    for candidate in candidates
                ],
            )
        )
        if len(terms) != len(candidates):
            raise ValueError("candidate proposal indices are duplicated")
        total_scores = {
            index: values["total_score"] for index, values in terms.items()
        }
        full_ranked = _ranked(candidates, total_scores)
        full_top1 = _recovered(full_ranked, 1)
        full_top5 = _recovered(full_ranked, 5)
        ligand_atom_count = int(diagnostics.get("ligand_atom_count", 0))
        if ligand_atom_count < 1:
            raise ValueError("ligand atom count is missing")
        ablations: dict[str, object] = {}
        rmsds = [float(candidate["rmsd_angstrom"]) for candidate in candidates]
        for name in TERM_NAMES:
            values = [terms[int(candidate["proposal_index"])][name] for candidate in candidates]
            without = {
                index: values_by_term["total_score"] - values_by_term[name]
                for index, values_by_term in terms.items()
            }
            term_only = {index: values_by_term[name] for index, values_by_term in terms.items()}
            without_ranked = _ranked(candidates, without)
            term_ranked = _ranked(candidates, term_only)
            correlation = _spearman(values, rmsds)
            if correlation is not None:
                per_term[name]["candidate_rmsd_correlations"].append(correlation)
            per_term[name]["absolute_values"].extend(abs(value) for value in values)
            per_term[name]["case_medians"].append(statistics.median(values))
            per_term[name]["ligand_atom_counts"].append(float(ligand_atom_count))
            ablations[name] = {
                "removed_top1_recovery": _recovered(without_ranked, 1),
                "removed_top5_recovery": _recovered(without_ranked, 5),
                "removed_top1_changed": (
                    int(without_ranked[0]["proposal_index"])
                    != int(full_ranked[0]["proposal_index"])
                ),
                "term_only_top1_recovery": _recovered(term_ranked, 1),
                "term_only_top5_recovery": _recovered(term_ranked, 5),
                "term_vs_rmsd_spearman": correlation,
            }
        cases.append(
            {
                "case_id": result["case_id"],
                "scorer_analysis_status": "included",
                "candidate_success_count": len(candidates),
                "oracle_2a_recovery": any(value <= 2.0 for value in rmsds),
                "full_top1_recovery": full_top1,
                "full_top5_recovery": full_top5,
                "full_top1_proposal_index": int(full_ranked[0]["proposal_index"]),
                "full_top1_valid": bool(
                    full_ranked[0].get("geometric_valid") is True
                    and full_ranked[0].get("chemical_valid") is True
                ),
                "ablations": ablations,
            }
        )

    term_summary: dict[str, object] = {}
    for name, values in per_term.items():
        absolute = values["absolute_values"]
        correlations = values["candidate_rmsd_correlations"]
        size_correlation = _spearman(
            values["case_medians"], values["ligand_atom_counts"]
        )
        term_summary[name] = {
            "median_absolute_weighted_value": statistics.median(absolute),
            "maximum_absolute_weighted_value": max(absolute),
            "median_candidate_rmsd_spearman": (
                statistics.median(correlations) if correlations else None
            ),
            "case_median_vs_ligand_atom_count_spearman": size_correlation,
            "removed_top1_changed_case_count": sum(
                bool(case.get("ablations", {}).get(name, {}).get("removed_top1_changed"))
                for case in cases
            ),
            "removed_top1_recovery_case_count": sum(
                bool(case.get("ablations", {}).get(name, {}).get("removed_top1_recovery"))
                for case in cases
            ),
            "removed_top5_recovery_case_count": sum(
                bool(case.get("ablations", {}).get(name, {}).get("removed_top5_recovery"))
                for case in cases
            ),
        }

    proposal_mode_summary: dict[str, object] = {}
    for mode, accumulator in mode_rows.items():
        candidate_count = int(accumulator["candidate_count"])
        scores = accumulator["scores"]
        mode_failures = accumulator["failed_check_counts"]
        if not isinstance(scores, list) or not isinstance(mode_failures, Counter):
            raise AssertionError("proposal mode accumulator is invalid")
        proposal_mode_summary[mode] = {
            "candidate_count": candidate_count,
            "native_like_candidate_count": int(
                accumulator["native_like_candidate_count"]
            ),
            "native_like_candidate_rate": (
                int(accumulator["native_like_candidate_count"]) / candidate_count
                if candidate_count
                else None
            ),
            "valid_candidate_count": int(accumulator["valid_candidate_count"]),
            "valid_candidate_rate": (
                int(accumulator["valid_candidate_count"]) / candidate_count
                if candidate_count
                else None
            ),
            "duplicate_candidate_count": int(
                accumulator["duplicate_candidate_count"]
            ),
            "execution_failure_count": int(
                accumulator["execution_failure_count"]
            ),
            "duplicate_candidate_rate": (
                int(accumulator["duplicate_candidate_count"]) / candidate_count
                if candidate_count
                else None
            ),
            "oracle_contribution_case_count": int(
                accumulator["oracle_contribution_case_count"]
            ),
            "best_oracle_case_count": int(accumulator["best_oracle_case_count"]),
            "median_score": statistics.median(scores) if scores else None,
            "failed_check_counts": dict(sorted(mode_failures.items())),
            "refinement_attempt_count": int(
                accumulator["refinement_attempt_count"]
            ),
            "refinement_penalty_reduced_count": int(
                accumulator["refinement_penalty_reduced_count"]
            ),
            "refinement_translated_count": int(
                accumulator["refinement_translated_count"]
            ),
            "refinement_rotated_count": int(
                accumulator["refinement_rotated_count"]
            ),
        }

    oracle_calibration_cases = [
        (case_id, rows)
        for case_id, rows in calibration_cases
        if any(float(row["rmsd_angstrom"]) <= 2.0 for row in rows)
    ]
    fitted_multipliers = _fit_multipliers(
        [rows for _, rows in oracle_calibration_cases]
    )
    baseline_multipliers = {name: 1.0 for name in TERM_NAMES}
    fitted_violations, pair_denominator = _pairwise_violations(
        [rows for _, rows in oracle_calibration_cases], fitted_multipliers
    )
    baseline_violations, _ = _pairwise_violations(
        [rows for _, rows in oracle_calibration_cases], baseline_multipliers
    )
    leave_one_out: list[dict[str, object]] = []
    for held_out_case_id, held_out_rows in oracle_calibration_cases:
        training = [
            rows
            for case_id, rows in oracle_calibration_cases
            if case_id != held_out_case_id
        ]
        fold_multipliers = _fit_multipliers(training)
        top1, top5, proposal_index = _calibration_recovery(
            held_out_rows, fold_multipliers
        )
        baseline_top1, baseline_top5, baseline_proposal_index = (
            _calibration_recovery(held_out_rows, baseline_multipliers)
        )
        leave_one_out.append(
            {
                "held_out_case_id": held_out_case_id,
                "training_oracle_case_count": len(training),
                "multipliers": fold_multipliers,
                "top1_recovery": top1,
                "top5_recovery": top5,
                "top1_proposal_index": proposal_index,
                "baseline_top1_recovery": baseline_top1,
                "baseline_top5_recovery": baseline_top5,
                "baseline_top1_proposal_index": baseline_proposal_index,
            }
        )

    report: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "claimable": False,
        "contains_fresh_internal_blind_holdout": False,
        "case_count": len(case_ids),
        "scored_case_count": sum(
            case.get("scorer_analysis_status") == "included" for case in cases
        ),
        "preparation_excluded_case_count": sum(
            case.get("scorer_analysis_status") == "excluded_preparation_failure"
            for case in cases
        ),
        "case_ids": sorted(case_ids),
        "candidate_count": sum(int(case["candidate_success_count"]) for case in cases),
        "sufficient_for_track_decision": (
            sum(case.get("scorer_analysis_status") == "included" for case in cases)
            >= 8
        ),
        "ranking_direction": "lower_is_better",
        "native_like_threshold_angstrom": 2.0,
        "source_receipts_sha256": dict(sorted(source_receipts_sha256.items())),
        "full_top1_recovery_case_count": sum(
            bool(case.get("full_top1_recovery")) for case in cases
        ),
        "full_top5_recovery_case_count": sum(
            bool(case.get("full_top5_recovery")) for case in cases
        ),
        "oracle_2a_recovery_case_count": sum(
            bool(case.get("oracle_2a_recovery")) for case in cases
        ),
        "term_summary": term_summary,
        "proposal_mode_summary": proposal_mode_summary,
        "candidate_diagnostic_summary": {
            "posebusters_failed_check_counts": dict(
                sorted(failed_check_counts.items())
            ),
            "refinement_attempt_count": refinement_attempt_count,
            "refinement_penalty_reduced_count": (
                refinement_penalty_reduced_count
            ),
            "refinement_translated_count": refinement_translated_count,
            "refinement_rotated_count": refinement_rotated_count,
        },
        "constrained_calibration_candidate": {
            "feature_source": "scorer_v1_weighted_terms",
            "multiplier_constraint": "non_negative_grid_no_sign_reversal",
            "grid": list(CALIBRATION_MULTIPLIER_GRID),
            "automatic_promotion_allowed": False,
            "public_claim_eligible": False,
            "fitted_multipliers": fitted_multipliers,
            "oracle_case_count": len(oracle_calibration_cases),
            "pair_denominator": pair_denominator,
            "baseline_pairwise_violation_rate": (
                baseline_violations / pair_denominator if pair_denominator else None
            ),
            "fitted_pairwise_violation_rate": (
                fitted_violations / pair_denominator if pair_denominator else None
            ),
            "leave_one_oracle_case_out": leave_one_out,
            "loo_top1_recovery_case_count": sum(
                bool(row["top1_recovery"]) for row in leave_one_out
            ),
            "loo_top5_recovery_case_count": sum(
                bool(row["top5_recovery"]) for row in leave_one_out
            ),
            "minimum_oracle_cases_for_model_promotion": 20,
            "model_promotion_gate_passed": False,
        },
        "cases": sorted(cases, key=lambda case: str(case["case_id"])),
    }
    report["report_sha256"] = _sha256(report)
    return report


def _receipt_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    receipts: set[Path] = set()
    for path in paths:
        if path.is_file():
            receipts.add(path)
            continue
        candidates = (path / "engine_v2", path / "receipts" / "engine_v2", path)
        matched = False
        for candidate in candidates:
            if candidate.is_dir():
                found = tuple(candidate.glob("*.json"))
                if found:
                    receipts.update(found)
                    matched = True
                    break
        if not matched:
            raise ValueError(f"no Engine V2 execution receipts found under {path}")
    return tuple(sorted(receipts))


def load_results(paths: Sequence[Path]) -> tuple[list[dict[str, object]], dict[str, str]]:
    results: list[dict[str, object]] = []
    hashes: dict[str, str] = {}
    for path in _receipt_paths(paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError(f"execution receipt has no result: {path}")
        results.append(dict(result))
        hashes[str(path)] = _sha256_path(path)
    return results, hashes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    results, hashes = load_results(arguments.inputs)
    report = analyze_results(results, source_receipts_sha256=hashes)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(report) + b"\n")
    print(json.dumps({"output": str(arguments.output), **{key: report[key] for key in ("case_count", "candidate_count", "sufficient_for_track_decision", "report_sha256")}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
