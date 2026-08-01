#!/usr/bin/env python3
"""Audit V7 penalty-scale alternatives from exact historical receipts only."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
)
import tools.build_engine_v2_source_paired_failure_atlas as failure_atlas


SCHEMA_ID = "betelgeuze.engine_v2_receipt_bound_scale_feasibility_audit/1.0.0"
EXPECTED_CASE_IDS = failure_atlas.EXPECTED_UNCOVERED_CASE_IDS
EXPECTED_ALLOCATION_COUNTS = {
    "5SD5_HWI": 4,
    "5SIS_JSM": 4,
    "6M2B_EZO": 0,
    "6TW5_9M2": 4,
    "6TW7_NZB": 4,
    "6VTA_AKN": 4,
    "6WTN_RXT": 4,
}
EXPECTED_COUNTS = {
    "allocated_candidate_count": 24,
    "evaluated_candidate_count": 23,
    "variant_available_candidate_count": 22,
    "selected_candidate_count": 0,
}
EXPECTED_HEAVY_ATOM_PROFILES = {
    "5SD5_HWI": (
        29,
        "5cb7355e18c0af38af55ab49824e34c8f97540ab0a6866d97dbc45c1dfc59fb3",
    ),
    "5SIS_JSM": (
        32,
        "507806a7b4cc0d84929fb9570a3228d3abdee59d1443c69cc9893d8c5fe7e0ad",
    ),
    "6M2B_EZO": (
        25,
        "13dab137d84a0d4dca8b6dfbbd2ee18f8f0194d3dfa8580864d20a688abcb989",
    ),
    "6TW5_9M2": (
        31,
        "95eaaa7830c9eccd0a86d7631914cd332f89700c22079b48318db146c24514df",
    ),
    "6TW7_NZB": (
        29,
        "839a116b45f65b56a2e98542c6d4327e8837c2d26f6417da59d66c9446e34a53",
    ),
    "6VTA_AKN": (
        40,
        "db18d13566c7fcedf8a5bfccf83979f4bf27a1ddd58a8723e8a4c9f1efa050db",
    ),
    "6WTN_RXT": (
        23,
        "29681b97b5b0f75571d08ac27b622772057be141ddc03625c88400598eb49566",
    ),
}
EXPECTED_HEAVY_ATOM_PROFILE_MANIFEST_SHA256 = (
    "57e9e27bd3d8a0752b81c0ce326c4f198bcf41b0529fb75dde3afe12fd67453b"
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


def _heavy_atom_profile_manifest() -> dict[str, dict[str, object]]:
    return {
        case_id: {
            "heavy_atom_count": row[0],
            "native_artifact_sha256": row[1],
        }
        for case_id, row in EXPECTED_HEAVY_ATOM_PROFILES.items()
    }


if (
    tuple(EXPECTED_HEAVY_ATOM_PROFILES) != EXPECTED_CASE_IDS
    or _sha256_payload(_heavy_atom_profile_manifest())
    != EXPECTED_HEAVY_ATOM_PROFILE_MANIFEST_SHA256
):
    raise RuntimeError("historical heavy-atom profile manifest is invalid")


def _penalty(payload: Mapping[str, object], field: str) -> float:
    encoded = failure_atlas._binary64_hex(payload.get(field), name=field)
    value = float.fromhex(encoded)
    if value < 0.0:
        raise ValueError(f"{field} cannot be negative")
    return value


def _normalized_penalty(value: float, heavy_atom_count: int) -> float:
    normalized = value / heavy_atom_count
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError("heavy-atom-normalized penalty is invalid")
    return normalized


def _exact_lexicographic_order(
    *,
    baseline_receptor: float,
    baseline_internal: float,
    optimized_receptor: float,
    optimized_internal: float,
) -> str:
    baseline = (baseline_receptor, baseline_internal)
    optimized = (optimized_receptor, optimized_internal)
    if optimized < baseline:
        return "improved"
    if optimized > baseline:
        return "regressed"
    return "equal"


def _distribution(values: Sequence[float]) -> dict[str, object]:
    return failure_atlas._distribution(values)


def _result_diagnostics(
    results: Mapping[str, Mapping[str, object]],
    *,
    case_id: str,
) -> tuple[Mapping[str, object], list[Mapping[str, object]]]:
    result = results.get(case_id)
    if (
        not isinstance(result, Mapping)
        or result.get("case_id") != case_id
        or result.get("engine_id") != "engine_v2"
        or result.get("status") != "success"
    ):
        raise ValueError(f"{case_id} authenticated result is invalid")
    diagnostics = result.get("engine_v2_diagnostics")
    candidates = (
        diagnostics.get("candidates") if isinstance(diagnostics, Mapping) else None
    )
    if not isinstance(diagnostics, Mapping) or not isinstance(candidates, list):
        raise ValueError(f"{case_id} authenticated diagnostics are invalid")
    if any(not isinstance(candidate, Mapping) for candidate in candidates):
        raise ValueError(f"{case_id} authenticated candidates are invalid")
    return diagnostics, candidates


def _case_audit(
    results: Mapping[str, Mapping[str, object]],
    *,
    case_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    diagnostics, candidates = _result_diagnostics(results, case_id=case_id)
    result = results[case_id]
    heavy_atom_count, expected_native_sha256 = EXPECTED_HEAVY_ATOM_PROFILES[case_id]
    ligand_atom_count = diagnostics.get("ligand_atom_count")
    if (
        result.get("native_artifact_sha256") != expected_native_sha256
        or type(ligand_atom_count) is not int
        or ligand_atom_count < heavy_atom_count
    ):
        raise ValueError(f"{case_id} heavy-atom profile is not artifact-bound")
    rescue_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("proposal_mode")
        == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
    ]
    if len(rescue_candidates) != EXPECTED_ALLOCATION_COUNTS[case_id]:
        raise ValueError(f"{case_id} rescue allocation count drifted")

    counts = Counter(
        {
            "allocated_candidate_count": len(rescue_candidates),
            "evaluated_candidate_count": 0,
            "variant_available_candidate_count": 0,
            "selected_candidate_count": 0,
        }
    )
    raw_baseline_receptor: list[float] = []
    raw_optimized_receptor: list[float] = []
    normalized_baseline_receptor: list[float] = []
    normalized_optimized_receptor: list[float] = []
    raw_baseline_internal: list[float] = []
    raw_optimized_internal: list[float] = []
    lexicographic_counts: Counter[str] = Counter()
    raw_window_counts: Counter[str] = Counter()
    normalized_window_counts: Counter[str] = Counter()

    for candidate in rescue_candidates:
        payload = candidate.get("refinement_receipt_payload")
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema_id")
            != failure_atlas.SOURCE_PAIRED_RESCUE_RECEIPT_SCHEMA_ID
            or payload.get("source_paired_parent_proposal_index")
            != candidate.get("torsion_rescue_parent_proposal_index")
            or type(payload.get("torsion_evaluated")) is not bool
            or type(payload.get("torsion_variant_available")) is not bool
            or type(payload.get("torsion_selected")) is not bool
        ):
            raise ValueError(f"{case_id} rescue receipt is invalid")
        minimum = _penalty(
            payload, "minimum_selected_final_receptor_penalty_binary64_hex"
        )
        maximum = _penalty(
            payload, "maximum_selected_final_receptor_penalty_binary64_hex"
        )
        if (minimum, maximum) != (2.0, 4.0):
            raise ValueError("V7 absolute selection-window identity drifted")
        evaluated = payload["torsion_evaluated"] is True
        available = payload["torsion_variant_available"] is True
        selected = payload["torsion_selected"] is True
        if (available and not evaluated) or (selected and not available):
            raise ValueError(f"{case_id} torsion state flags are inconsistent")
        counts["evaluated_candidate_count"] += evaluated
        counts["variant_available_candidate_count"] += available
        counts["selected_candidate_count"] += selected

        baseline_receptor = _penalty(
            payload, "baseline_v6_receptor_penalty_binary64_hex"
        )
        optimized_receptor = _penalty(
            payload, "optimized_receptor_penalty_binary64_hex"
        )
        baseline_internal = _penalty(
            payload, "baseline_v6_internal_penalty_binary64_hex"
        )
        optimized_internal = _penalty(
            payload, "optimized_internal_penalty_binary64_hex"
        )
        if not available:
            continue
        raw_baseline_receptor.append(baseline_receptor)
        raw_optimized_receptor.append(optimized_receptor)
        normalized_baseline = _normalized_penalty(baseline_receptor, heavy_atom_count)
        normalized_optimized = _normalized_penalty(optimized_receptor, heavy_atom_count)
        normalized_baseline_receptor.append(normalized_baseline)
        normalized_optimized_receptor.append(normalized_optimized)
        raw_baseline_internal.append(baseline_internal)
        raw_optimized_internal.append(optimized_internal)
        lexicographic_counts[
            _exact_lexicographic_order(
                baseline_receptor=baseline_receptor,
                baseline_internal=baseline_internal,
                optimized_receptor=optimized_receptor,
                optimized_internal=optimized_internal,
            )
        ] += 1
        raw_window_counts[
            (
                "inside_2_inclusive_4_exclusive"
                if 2.0 <= optimized_receptor < 4.0
                else "outside_2_inclusive_4_exclusive"
            )
        ] += 1
        normalized_window_counts[
            (
                "inside_2_inclusive_4_exclusive"
                if 2.0 <= normalized_optimized < 4.0
                else "outside_2_inclusive_4_exclusive"
            )
        ] += 1

    profile = {
        "heavy_atom_count": heavy_atom_count,
        "native_artifact_sha256": expected_native_sha256,
        "authenticated_total_ligand_atom_count": ligand_atom_count,
    }
    audit = {
        "case_id": case_id,
        **dict(sorted(counts.items())),
        "raw_receptor_penalty": {
            "baseline_v6": _distribution(raw_baseline_receptor),
            "optimized": _distribution(raw_optimized_receptor),
        },
        "heavy_atom_normalized_receptor_penalty": {
            "normalizer": "frozen_profile_heavy_atom_count",
            "baseline_v6": _distribution(normalized_baseline_receptor),
            "optimized": _distribution(normalized_optimized_receptor),
        },
        "raw_internal_penalty": {
            "baseline_v6": _distribution(raw_baseline_internal),
            "optimized": _distribution(raw_optimized_internal),
        },
        "exact_lexicographic_receptor_then_internal_counts": {
            status: lexicographic_counts[status]
            for status in ("improved", "equal", "regressed")
        },
        "current_absolute_window_counts": {
            status: raw_window_counts[status]
            for status in (
                "inside_2_inclusive_4_exclusive",
                "outside_2_inclusive_4_exclusive",
            )
        },
        "diagnostic_heavy_atom_normalized_window_counts": {
            "interpretation": "current_numeric_bounds_reused_for_scale_comparison_only",
            **{
                status: normalized_window_counts[status]
                for status in (
                    "inside_2_inclusive_4_exclusive",
                    "outside_2_inclusive_4_exclusive",
                )
            },
        },
    }
    return audit, profile


def _build_scale_feasibility_audit_draft(
    *,
    rescue_results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if set(rescue_results) != set(failure_atlas.EXPECTED_CASE_IDS):
        raise ValueError("authenticated rescue-result case set is invalid")

    cases: list[dict[str, object]] = []
    profiles: dict[str, dict[str, object]] = {}
    totals: Counter[str] = Counter()
    lexicographic_totals: Counter[str] = Counter()
    window_totals: Counter[str] = Counter()
    normalized_window_totals: Counter[str] = Counter()

    for case_id in EXPECTED_CASE_IDS:
        case, profile = _case_audit(rescue_results, case_id=case_id)
        cases.append(case)
        profiles[case_id] = profile
        for field in EXPECTED_COUNTS:
            totals[field] += int(case[field])
        lexicographic = case["exact_lexicographic_receptor_then_internal_counts"]
        window = case["current_absolute_window_counts"]
        assert isinstance(lexicographic, Mapping)
        assert isinstance(window, Mapping)
        lexicographic_totals.update(
            {key: int(value) for key, value in lexicographic.items()}
        )
        window_totals.update({key: int(value) for key, value in window.items()})
        normalized_window = case["diagnostic_heavy_atom_normalized_window_counts"]
        assert isinstance(normalized_window, Mapping)
        normalized_window_totals.update(
            {
                key: int(normalized_window[key])
                for key in (
                    "inside_2_inclusive_4_exclusive",
                    "outside_2_inclusive_4_exclusive",
                )
            }
        )

    if dict(totals) != EXPECTED_COUNTS:
        raise ValueError("historical uncovered torsion counts drifted")

    # Reconstruct the compact aggregate from the per-case authenticated results
    # without storing proposal-level or outcome fields in the emitted artifact.
    aggregate_raw_baseline: list[float] = []
    aggregate_raw_optimized: list[float] = []
    aggregate_normalized_baseline: list[float] = []
    aggregate_normalized_optimized: list[float] = []
    aggregate_internal_baseline: list[float] = []
    aggregate_internal_optimized: list[float] = []
    for case_id in EXPECTED_CASE_IDS:
        diagnostics, candidates = _result_diagnostics(rescue_results, case_id=case_id)
        _ = diagnostics
        heavy_atom_count = EXPECTED_HEAVY_ATOM_PROFILES[case_id][0]
        for candidate in candidates:
            if (
                candidate.get("proposal_mode")
                != PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            ):
                continue
            payload = candidate["refinement_receipt_payload"]
            assert isinstance(payload, Mapping)
            if payload.get("torsion_variant_available") is not True:
                continue
            baseline_receptor = _penalty(
                payload, "baseline_v6_receptor_penalty_binary64_hex"
            )
            optimized_receptor = _penalty(
                payload, "optimized_receptor_penalty_binary64_hex"
            )
            aggregate_raw_baseline.append(baseline_receptor)
            aggregate_raw_optimized.append(optimized_receptor)
            aggregate_normalized_baseline.append(
                _normalized_penalty(baseline_receptor, heavy_atom_count)
            )
            aggregate_normalized_optimized.append(
                _normalized_penalty(optimized_receptor, heavy_atom_count)
            )
            aggregate_internal_baseline.append(
                _penalty(payload, "baseline_v6_internal_penalty_binary64_hex")
            )
            aggregate_internal_optimized.append(
                _penalty(payload, "optimized_internal_penalty_binary64_hex")
            )

    heavy_atom_profile_binding = {
        case_id: profiles[case_id] for case_id in EXPECTED_CASE_IDS
    }
    draft: dict[str, object] = {
        "analysis_scope": "historical_contaminated_development_only",
        "evidence_role": "receipt_bound_scale_feasibility_audit",
        "development_only": True,
        "historical_cohort_outcome_selected": True,
        "outcomes_consumed_for_cohort_authentication": True,
        "scale_computation_result_independent": True,
        "rmsd_used_in_scale_computation": False,
        "posebusters_used_in_scale_computation": False,
        "ranking_score_used_in_scale_computation": False,
        "native_coordinates_used_in_scale_computation": False,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "stage0_eligible": False,
        "primary_claim_eligible": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "case_count": len(EXPECTED_CASE_IDS),
        "case_ids": list(EXPECTED_CASE_IDS),
        "case_ids_sha256": _sha256_payload(list(EXPECTED_CASE_IDS)),
        "heavy_atom_profiles": heavy_atom_profile_binding,
        "normalizer_availability": {
            "ligand_heavy_atom_count": {
                "status": "available_artifact_bound_frozen_profile",
                "evaluated": True,
            },
            "authenticated_total_ligand_atom_count": {
                "status": "available_inventory_only",
                "evaluated": False,
            },
            "exact_lexicographic_receptor_then_internal": {
                "status": "available_from_binary64_receipt_objectives",
                "evaluated": True,
            },
            "accepted_receptor_pair_count": {
                "status": "unavailable_not_recorded_in_receipts",
                "evaluated": False,
            },
            "clash_atom_count": {
                "status": "unavailable_not_recorded_in_receipts",
                "evaluated": False,
            },
            "maximum_local_penetration": {
                "status": "unavailable_not_recorded_in_receipts",
                "evaluated": False,
            },
            "absolute_geometric_clearance": {
                "status": "unavailable_categorical_checks_only",
                "evaluated": False,
            },
            "scorer_v1_terms": {
                "status": "ineligible_distinct_ranking_contract",
                "evaluated": False,
            },
        },
        "summary": {
            **EXPECTED_COUNTS,
            "raw_receptor_penalty": {
                "baseline_v6": _distribution(aggregate_raw_baseline),
                "optimized": _distribution(aggregate_raw_optimized),
            },
            "heavy_atom_normalized_receptor_penalty": {
                "normalizer": "frozen_profile_heavy_atom_count",
                "baseline_v6": _distribution(aggregate_normalized_baseline),
                "optimized": _distribution(aggregate_normalized_optimized),
            },
            "raw_internal_penalty": {
                "baseline_v6": _distribution(aggregate_internal_baseline),
                "optimized": _distribution(aggregate_internal_optimized),
            },
            "exact_lexicographic_receptor_then_internal_counts": {
                status: lexicographic_totals[status]
                for status in ("improved", "equal", "regressed")
            },
            "current_absolute_window_counts": {
                status: window_totals[status]
                for status in (
                    "inside_2_inclusive_4_exclusive",
                    "outside_2_inclusive_4_exclusive",
                )
            },
            "diagnostic_heavy_atom_normalized_window_counts": {
                "interpretation": (
                    "current_numeric_bounds_reused_for_scale_comparison_only"
                ),
                **{
                    status: normalized_window_totals[status]
                    for status in (
                        "inside_2_inclusive_4_exclusive",
                        "outside_2_inclusive_4_exclusive",
                    )
                },
            },
        },
        "cases": cases,
        "decision": {
            "selected_rule": None,
            "automatic_policy_change_allowed": False,
            "threshold_relaxation_allowed": False,
            "v7_replacement_allowed": False,
            "status": "descriptive_audit_only_predeclare_one_rule_before_ab",
        },
    }
    return draft


def _authenticated_failure_atlas_input_evidence(
    authenticated_failure_atlas: Mapping[str, object],
) -> Mapping[str, object]:
    failure_atlas._self_hash(
        authenticated_failure_atlas,
        field="report_sha256",
        name="authenticated failure atlas",
    )
    authentication = authenticated_failure_atlas.get("authentication")
    input_evidence = authenticated_failure_atlas.get("input_evidence")
    false_fields = (
        "contains_engineering_smoke",
        "contains_fresh_internal_blind_holdout",
        "fresh_execution_authorized",
        "scientifically_validated",
        "claim_safe",
        "stage0_eligible",
        "primary_claim_eligible",
        "public_claim_eligible",
        "product_promotion_eligible",
    )
    if (
        authenticated_failure_atlas.get("schema_id") != failure_atlas.SCHEMA_ID
        or authenticated_failure_atlas.get("analysis_scope")
        != "historical_contaminated_development_only"
        or authenticated_failure_atlas.get("development_only") is not True
        or tuple(authenticated_failure_atlas.get("case_ids", ())) != EXPECTED_CASE_IDS
        or any(
            authenticated_failure_atlas.get(field) is not False
            for field in false_fields
        )
        or not isinstance(authentication, Mapping)
        or authentication.get("status") != "verified_archive_member_bundle"
        or authentication.get("both_raw_receipt_lanes_verified") is not True
        or not isinstance(input_evidence, Mapping)
    ):
        raise ValueError("authenticated failure-atlas boundary is invalid")
    return input_evidence


def _load_authenticated_inputs(
    *,
    repo_root: Path,
    archive_path: Path,
    members_path: Path,
    bundle_path: Path,
    report_member: str,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
    expected_report_sha256: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    authenticated_atlas = failure_atlas.build_authenticated_failure_atlas(
        repo_root=repo_root,
        archive_path=archive_path,
        members_path=members_path,
        bundle_path=bundle_path,
        report_member=report_member,
        expected_archive_sha256=expected_archive_sha256,
        expected_members_sha256=expected_members_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
        expected_report_sha256=expected_report_sha256,
    )
    archive_file, _ = failure_atlas._artifact_file(
        repo_root, archive_path, name="archive"
    )
    members_file, _ = failure_atlas._artifact_file(
        repo_root, members_path, name="member manifest"
    )
    bundle_file, _ = failure_atlas._artifact_file(
        repo_root, bundle_path, name="bundle checksum"
    )
    members, _ = failure_atlas._verified_archive_members(
        archive_path=archive_file,
        members_path=members_file,
        bundle_path=bundle_file,
        expected_archive_sha256=expected_archive_sha256,
        expected_members_sha256=expected_members_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
    )
    ab_report, _, _ = failure_atlas._archive_object(
        members,
        report_member,
        name="A/B report",
        require_canonical_bytes=False,
    )
    rescue = ab_report.get("rescue")
    engine_identity = ab_report.get("engine_identity")
    if not isinstance(rescue, Mapping) or not isinstance(engine_identity, Mapping):
        raise ValueError("authenticated A/B rescue identity is invalid")
    rescue_results, _, _ = failure_atlas._load_receipt_set(
        members,
        run_root=rescue.get("run_root"),
        lane="rescue",
        engine_identity=engine_identity,
    )
    if ab_report.get("report_sha256") != authenticated_atlas.get("ab_report_sha256"):
        raise ValueError("authenticated A/B report changed between verification passes")
    return authenticated_atlas, rescue_results


def build_authenticated_scale_feasibility_audit(
    *,
    repo_root: Path,
    archive_path: Path,
    members_path: Path,
    bundle_path: Path,
    report_member: str,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
    expected_report_sha256: str,
) -> dict[str, object]:
    authenticated_atlas, rescue_results = _load_authenticated_inputs(
        repo_root=repo_root,
        archive_path=archive_path,
        members_path=members_path,
        bundle_path=bundle_path,
        report_member=report_member,
        expected_archive_sha256=expected_archive_sha256,
        expected_members_sha256=expected_members_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
        expected_report_sha256=expected_report_sha256,
    )
    input_evidence = _authenticated_failure_atlas_input_evidence(authenticated_atlas)
    draft = _build_scale_feasibility_audit_draft(
        rescue_results=rescue_results,
    )
    profiles = draft.get("heavy_atom_profiles")
    if not isinstance(profiles, Mapping):
        raise ValueError("scale-audit heavy-atom profiles are invalid")
    report: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        **draft,
        "authentication": {
            "status": "derived_from_recomputed_authenticated_failure_atlas",
            "failure_atlas_schema_id": authenticated_atlas["schema_id"],
            "failure_atlas_report_sha256": authenticated_atlas["report_sha256"],
            "ab_report_sha256": authenticated_atlas["ab_report_sha256"],
            "input_evidence": dict(sorted(input_evidence.items())),
            "heavy_atom_profile_manifest_sha256": (
                EXPECTED_HEAVY_ATOM_PROFILE_MANIFEST_SHA256
            ),
            "heavy_atom_profile_binding_sha256": _sha256_payload(profiles),
        },
    }
    report["report_sha256"] = _sha256_payload(report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--members-sha256", type=Path, required=True)
    parser.add_argument("--bundle-sha256", type=Path, required=True)
    parser.add_argument("--report-member", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-members-sha256", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--expected-report-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    failure_atlas._prohibited_path(arguments.repo_root, name="repository root")
    repo_root = arguments.repo_root.resolve()
    report = build_authenticated_scale_feasibility_audit(
        repo_root=repo_root,
        archive_path=arguments.archive,
        members_path=arguments.members_sha256,
        bundle_path=arguments.bundle_sha256,
        report_member=arguments.report_member,
        expected_archive_sha256=arguments.expected_archive_sha256,
        expected_members_sha256=arguments.expected_members_sha256,
        expected_bundle_sha256=arguments.expected_bundle_sha256,
        expected_report_sha256=arguments.expected_report_sha256,
    )
    output = failure_atlas._output_relative_path(repo_root, arguments.output)
    failure_atlas._write_exclusive(
        repo_root,
        output,
        _canonical_bytes(report) + b"\n",
    )
    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "output": str(arguments.output),
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
