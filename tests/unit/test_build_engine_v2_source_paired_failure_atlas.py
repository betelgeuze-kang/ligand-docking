from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
)
import tools.build_engine_v2_source_paired_failure_atlas as atlas_builder


_TOP1_INDICES = {
    "5SD5_HWI": 41,
    "5SIS_JSM": 12,
    "6M2B_EZO": 0,
    "6T88_MWQ": 51,
    "6TW5_9M2": 5,
    "6TW7_NZB": 44,
    "6VTA_AKN": 11,
    "6WTN_RXT": 14,
}
_ROTOR_CASE_IDS = frozenset(
    {
        "5SD5_HWI",
        "5SIS_JSM",
        "6T88_MWQ",
        "6TW5_9M2",
        "6TW7_NZB",
        "6VTA_AKN",
        "6WTN_RXT",
    }
)
_RESCUE_PAIRS = ((8, 24), (13, 37), (18, 50), (23, 63))
_VALID_INDICES = {
    "6T88_MWQ": frozenset({5, 6, 7, 51}),
    "6VTA_AKN": frozenset({11, 20}),
    "6WTN_RXT": frozenset({14}),
}
_NATIVE_INDICES = {"6T88_MWQ": frozenset({5, 13, 37, 51})}
_ELIGIBLE_INDICES = {
    "5SIS_JSM": frozenset({12, 20}),
    "6M2B_EZO": frozenset({0}),
    "6T88_MWQ": frozenset({*range(15), 20, 21, 51}),
    "6TW7_NZB": frozenset({44, 45}),
    "6VTA_AKN": frozenset({11, 20, 21, 22}),
    "6WTN_RXT": frozenset({14, 20, 21, 22}),
}


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


def _digest(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode("ascii")).hexdigest()


def _seal(
    payload: dict[str, object], field: str = "receipt_sha256"
) -> dict[str, object]:
    payload[field] = _sha256(payload)
    return payload


def _pairs(case_id: str) -> list[dict[str, int]]:
    if case_id not in _ROTOR_CASE_IDS:
        return []
    return [
        {"target_proposal_index": target, "parent_proposal_index": parent}
        for target, parent in _RESCUE_PAIRS
    ]


def _refinement_payload(case_id: str, index: int) -> dict[str, object]:
    if case_id not in _ROTOR_CASE_IDS or index not in {row[0] for row in _RESCUE_PAIRS}:
        return {}
    unreachable = case_id == "6VTA_AKN" and index == 23
    no_variant = case_id == "5SD5_HWI" and index == 8
    payload: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0",
        "pre_coordinates_sha256": _digest(case_id, index, "pre"),
        "post_coordinates_sha256": _digest(case_id, index, "post"),
        "initial_receptor_penalty_binary64_hex": (8.0).hex(),
        "baseline_v6_receptor_penalty_binary64_hex": (6.0).hex(),
        "optimized_receptor_penalty_binary64_hex": (5.0).hex(),
        "final_receptor_penalty_binary64_hex": (6.0).hex(),
        "initial_internal_penalty_binary64_hex": (2.0).hex(),
        "baseline_v6_internal_penalty_binary64_hex": (1.5).hex(),
        "optimized_internal_penalty_binary64_hex": (1.0).hex(),
        "final_internal_penalty_binary64_hex": (1.5).hex(),
        "torsion_evaluated": not unreachable,
        "torsion_variant_available": not (unreachable or no_variant),
        "torsion_selected": False,
        "evaluated_torsion_steps": 0 if unreachable else 4,
        "accepted_torsion_steps": 0,
        "evaluated_total_torsion_path_radians_binary64_hex": (
            0.0 if unreachable else 0.5
        ).hex(),
        "total_torsion_path_radians_binary64_hex": (0.0).hex(),
        "minimum_selected_final_receptor_penalty_binary64_hex": (2.0).hex(),
        "maximum_selected_final_receptor_penalty_binary64_hex": (4.0).hex(),
        "selection_window_reachable_from_baseline_v6_receptor_penalty": (
            not unreachable
        ),
        "torsion_evaluation_skip_reason": (
            "selection_window_unreachable_under_receptor_nonincrease"
            if unreachable
            else "none"
        ),
        "selection_reason": "v6_retained_outside_final_receptor_penalty_window",
    }
    return _seal(payload)


def _candidate(case_id: str, index: int, *, lane: str) -> dict[str, object]:
    rotor_case = case_id in _ROTOR_CASE_IDS
    rescue_parent_by_target = dict(_RESCUE_PAIRS) if rotor_case else {}
    rescue_target = lane == "rescue" and index in rescue_parent_by_target
    proposal_mode = (
        PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
        if rescue_target
        else (
            "uniform_v3_rigid_ensemble"
            if index in rescue_parent_by_target
            else "uniform_fallback"
        )
    )
    coordinate_index = rescue_parent_by_target[index] if rescue_target else index
    coordinate_sha256 = _digest(case_id, coordinate_index, "coordinate")
    top1 = index == _TOP1_INDICES[case_id]
    score = 0.0 if top1 else float(index + 1)
    native = index in _NATIVE_INDICES.get(case_id, frozenset())
    rmsd = 1.5 + index / 1000.0 if native else 3.0 + index / 100.0
    valid = index in _VALID_INDICES.get(case_id, frozenset())
    failed_checks: list[str] = [] if valid else ["minimum_distance_to_protein"]
    if case_id == "5SD5_HWI" and top1:
        failed_checks = [
            "internal_energy",
            "minimum_distance_to_protein",
            "volume_overlap_with_protein",
        ]
    eligible = index in _ELIGIBLE_INDICES.get(case_id, frozenset())
    if lane == "rescue" and case_id == "6T88_MWQ" and index == 13:
        eligible = False
    payload = _refinement_payload(case_id, index) if lane == "rescue" else {}
    candidate: dict[str, object] = {
        "schema_id": (
            PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
            if lane == "baseline"
            else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID
        ),
        "proposal_index": index,
        "status": "success",
        "proposal_mode": proposal_mode,
        "proposal_fingerprint_sha256": _digest(case_id, index, lane, "proposal"),
        "coordinate_fingerprint_sha256": coordinate_sha256,
        "score": score,
        "rmsd_angstrom": rmsd,
        "geometric_valid": valid,
        "chemical_valid": "internal_energy" not in failed_checks,
        "selection_eligible": eligible,
        "pose_artifact_sha256": _digest(case_id, index, lane, "pose"),
        "score_terms_receipt_sha256": _digest(case_id, index, lane, "terms"),
        "posebusters_failed_check_ids": failed_checks,
        "refinement_receipt_payload": payload,
        "refinement_receipt_sha256": payload.get(
            "receipt_sha256", _digest(case_id, index, lane, "refinement")
        ),
        "refinement_total_translation_binary64_hex": (
            [(1.0).hex(), (0.0).hex(), (0.0).hex()] if payload else []
        ),
        "refinement_total_rotation_vector_binary64_hex": (
            [(0.0).hex(), (0.0).hex(), (0.0).hex()] if payload else []
        ),
        "ensemble_source_proposal_index": None,
    }
    if lane == "rescue":
        candidate["torsion_rescue_parent_proposal_index"] = (
            rescue_parent_by_target[index] if rescue_target else None
        )
    return candidate


def _result(case_id: str, *, lane: str) -> dict[str, object]:
    schema_id = (
        PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    if case_id == atlas_builder.EXPECTED_PREPARATION_FAILURE_CASE_ID:
        diagnostics: dict[str, object] = {
            "schema_id": schema_id,
            "preparation_status": "failure",
            "preparation_failure_code": "unsupported_large_ring_system",
            "candidates": [],
        }
        return {
            "case_id": case_id,
            "engine_id": "engine_v2",
            "status": "failure",
            "failure_code": "engine_v2_input_unsupported",
            "engine_v2_diagnostics": diagnostics,
        }
    candidates = [_candidate(case_id, index, lane=lane) for index in range(64)]
    diagnostics = {
        "schema_id": schema_id,
        "preparation_status": "success",
        "preparation_failure_code": "",
        "candidate_budget": 64,
        "candidate_success_count": 64,
        "candidate_failure_count": 0,
        "candidates": candidates,
    }
    if lane == "rescue":
        diagnostics["source_paired_torsion_rescue_proposal_receipt"] = {
            "allocation": {
                "authority_rotor_count": 3 if case_id in _ROTOR_CASE_IDS else 0,
                "rescue_target_parent_pairs": _pairs(case_id),
            }
        }
    return {
        "case_id": case_id,
        "engine_id": "engine_v2",
        "status": "success",
        "failure_code": "",
        "engine_v2_diagnostics": diagnostics,
    }


def _results(lane: str) -> dict[str, dict[str, object]]:
    return {
        case_id: _result(case_id, lane=lane)
        for case_id in atlas_builder.EXPECTED_CASE_IDS
    }


def _lane_metrics(
    results: dict[str, dict[str, object]], lane: str
) -> dict[str, object]:
    metrics: dict[str, object] = atlas_builder._lane_counts(results, lane=lane)
    per_case: dict[str, object] = {}
    for case_id, result in results.items():
        diagnostics, candidates = atlas_builder._case_candidates(result, lane=lane)
        if not candidates:
            per_case[case_id] = {
                "candidate_success_count": 0,
                "exact_valid_candidate_count": 0,
                "selection_eligible_candidate_count": 0,
                "preparation_status": "failure",
                "preparation_failure_code": diagnostics["preparation_failure_code"],
                "proposal_oracle_recovery": None,
                "top1_recovery": None,
                "top5_recovery": None,
                "top1_proposal_index": None,
                "top1_valid": None,
                "top1_rmsd_angstrom_binary64_hex": None,
                "minimum_candidate_rmsd_angstrom_binary64_hex": None,
            }
            continue
        ranked = atlas_builder._ranked(candidates)
        exact_valid = [
            candidate
            for candidate in candidates
            if atlas_builder._posebusters_exact_valid(candidate)
        ]
        eligible = [
            candidate for candidate in candidates if candidate["selection_eligible"]
        ]
        per_case[case_id] = {
            "candidate_success_count": len(candidates),
            "exact_valid_candidate_count": len(exact_valid),
            "selection_eligible_candidate_count": len(eligible),
            "preparation_status": "success",
            "preparation_failure_code": "",
            "proposal_oracle_recovery": any(
                float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in candidates
            ),
            "top1_recovery": float(ranked[0]["rmsd_angstrom"]) <= 2.0,
            "top5_recovery": any(
                float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5]
            ),
            "top1_proposal_index": ranked[0]["proposal_index"],
            "top1_valid": atlas_builder._posebusters_exact_valid(ranked[0]),
            "top1_rmsd_angstrom_binary64_hex": float(ranked[0]["rmsd_angstrom"]).hex(),
            "minimum_candidate_rmsd_angstrom_binary64_hex": min(
                float(candidate["rmsd_angstrom"]) for candidate in candidates
            ).hex(),
        }
    metrics["per_case"] = per_case
    return metrics


def _ab_report(
    baseline: dict[str, dict[str, object]],
    rescue: dict[str, dict[str, object]],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": atlas_builder.AB_SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "source_commit_sha256": atlas_builder.EXPECTED_SOURCE_COMMIT_SHA256,
        "case_ids": list(atlas_builder.EXPECTED_CASE_IDS),
        "case_ids_sha256": atlas_builder.EXPECTED_CASE_IDS_SHA256,
        "paired_evidence_bound_by_this_report": True,
        "development_only": True,
        "claim_safe": False,
        "fresh_execution_authorized": False,
        "public_claim_eligible": False,
        "primary_claim_eligible": False,
        "product_promotion_eligible": False,
        "scientifically_validated": False,
        "stage0_eligible": False,
        "engine_identity": {
            "implementation_sha256": "1" * 64,
            "evaluation_pipeline_sha256": "2" * 64,
            "execution_environment_sha256": "3" * 64,
            "interaction_refiner_config_sha256": "4" * 64,
        },
        "acceptance": {
            "decision": atlas_builder.EXPECTED_DECISION,
            "rescue_vs_parent_coordinate_change_candidate_count": 0,
            "selection_eligibility_regression_case_ids": ["6T88_MWQ"],
        },
        "candidate_level_changes": {
            "baseline_to_rescue_coordinate_change_candidate_count": 28,
            "baseline_to_rescue_coordinate_change_case_ids": [
                "5SD5_HWI",
                "5SIS_JSM",
                "6T88_MWQ",
                "6TW5_9M2",
                "6TW7_NZB",
                "6VTA_AKN",
                "6WTN_RXT",
            ],
        },
        "baseline": {"metrics": _lane_metrics(baseline, "baseline")},
        "rescue": {
            "metrics": _lane_metrics(rescue, "rescue"),
            "allocation_and_refinement": {
                "allocated_candidate_count": 28,
                "parent_coordinate_duplicate_candidate_count": 28,
                "torsion_selected_candidate_count": 0,
            },
        },
    }
    payload["report_sha256"] = _sha256(payload)
    return payload


def _binding() -> dict[str, str]:
    return {
        "ab_report_file_sha256": "a" * 64,
        "baseline_analysis_file_sha256": "b" * 64,
        "baseline_analysis_self_sha256": "c" * 64,
        "rescue_analysis_file_sha256": "d" * 64,
        "rescue_analysis_self_sha256": "e" * 64,
        "baseline_source_receipts_sha256": "f" * 64,
        "rescue_source_receipts_sha256": "0" * 64,
    }


def _build() -> tuple[
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    baseline = _results("baseline")
    rescue = _results("rescue")
    ab_report = _ab_report(baseline, rescue)
    report = atlas_builder.build_failure_atlas(
        ab_report=ab_report,
        baseline_results=baseline,
        rescue_results=rescue,
        evidence_binding=_binding(),
    )
    return report, baseline, rescue, ab_report


def _execution_receipt(
    result: dict[str, object],
    engine_identity: dict[str, object],
) -> dict[str, object]:
    return _seal(
        {
            "schema_id": atlas_builder.PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
            "runner_id": atlas_builder.PUBLIC_REDOCKING_RUNNER_ID,
            "archive_sha256": atlas_builder.PUBLIC_REDOCKING_ARCHIVE_SHA256,
            "source_ids_sha256": atlas_builder.PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
            "command": ["synthetic-historical-test"],
            "execution_policy": {},
            "input_sha256s": {},
            "materialization_receipt_sha256": "5" * 64,
            "implementation_sha256": engine_identity["implementation_sha256"],
            "evaluation_pipeline_sha256": engine_identity[
                "evaluation_pipeline_sha256"
            ],
            "execution_environment_sha256": engine_identity[
                "execution_environment_sha256"
            ],
            "cache_read_allowed": False,
            "fresh_execution": True,
            "result": result,
        }
    )


def _authenticated_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, bytes, Path]:
    _, baseline, rescue, ab_report = _build()
    repo_root = tmp_path / "repo"
    state = repo_root / ".betelgeuze" / "stage0-development"
    baseline_receipts = state / "baseline-receipts"
    rescue_receipts = state / "rescue-receipts"
    baseline_receipts.mkdir(parents=True)
    rescue_receipts.mkdir()
    engine_identity = ab_report["engine_identity"]
    assert isinstance(engine_identity, dict)

    receipt_maps: dict[str, dict[str, str]] = {}
    baseline_first_raw = b""
    baseline_first_path = baseline_receipts / (
        f"{atlas_builder.EXPECTED_CASE_IDS[0]}.json"
    )
    for lane, results, receipt_root in (
        ("baseline", baseline, baseline_receipts),
        ("rescue", rescue, rescue_receipts),
    ):
        hashes: dict[str, str] = {}
        for case_id in atlas_builder.EXPECTED_CASE_IDS:
            receipt = _execution_receipt(results[case_id], engine_identity)
            raw = _canonical_bytes(receipt) + b"\n"
            path = receipt_root / f"{case_id}.json"
            path.write_bytes(raw)
            hashes[path.relative_to(repo_root).as_posix()] = hashlib.sha256(
                raw
            ).hexdigest()
            if lane == "baseline" and case_id == atlas_builder.EXPECTED_CASE_IDS[0]:
                baseline_first_raw = raw
        receipt_maps[lane] = hashes

    analysis_paths: dict[str, Path] = {}
    for lane in ("baseline", "rescue"):
        analysis = _seal(
            {
                "schema_id": atlas_builder.ANALYSIS_SCHEMA_ID,
                "analysis_scope": "historical_contaminated_development_only",
                "contains_fresh_internal_blind_holdout": False,
                "case_ids": list(atlas_builder.EXPECTED_CASE_IDS),
                "source_receipts_sha256": receipt_maps[lane],
            },
            "report_sha256",
        )
        raw = _canonical_bytes(analysis) + b"\n"
        path = state / f"{lane}-analysis.json"
        path.write_bytes(raw)
        analysis_paths[lane] = path
        lane_row = ab_report[lane]
        assert isinstance(lane_row, dict)
        lane_row["analysis_path"] = path.relative_to(repo_root).as_posix()
        lane_row["analysis_self_sha256"] = analysis["report_sha256"]
        lane_row["analysis_file_sha256"] = hashlib.sha256(raw).hexdigest()

    ab_report.pop("report_sha256")
    ab_report["report_sha256"] = _sha256(ab_report)
    ab_report_path = state / "ab-report.json"
    ab_report_path.write_bytes(_canonical_bytes(ab_report) + b"\n")
    return (
        repo_root,
        ab_report_path,
        baseline_receipts,
        rescue_receipts,
        baseline_first_path,
        baseline_first_raw,
        analysis_paths["baseline"],
    )


def test_failure_atlas_records_exact_seven_case_split_and_blockers() -> None:
    report, _, _, _ = _build()

    assert report["case_ids"] == list(atlas_builder.EXPECTED_UNCOVERED_CASE_IDS)
    assert report["failure_class_counts"] == {
        "invalid_top1": 5,
        "valid_nonnative_top1": 2,
    }
    assert report["cross_lane_summary"]["rescue_parent_duplicate_count"] == 28
    assert report["cross_lane_summary"]["torsion_selected_count"] == 0
    assert report["uncovered_torsion_scale_summary"][
        "variant_available_candidate_count"
    ] == 22
    assert report["uncovered_torsion_scale_summary"][
        "available_variant_optimized_receptor_penalty_bands"
    ] == {
        "at_or_above_4": 22,
        "below_2": 0,
        "from_2_inclusive_to_4_exclusive": 0,
    }
    cases = {row["case_id"]: row for row in report["cases"]}
    assert cases["6M2B_EZO"]["torsion"]["authority_rotor_count"] == 0
    assert "no_authority_rotor" in cases["6M2B_EZO"]["observed_blocker_ids"]
    assert cases["6VTA_AKN"]["failure_class"] == "valid_nonnative_top1"
    assert (
        cases["6VTA_AKN"]["torsion"]["selection_window_unreachable_candidate_count"]
        == 1
    )
    assert cases["6VTA_AKN"]["torsion"]["evaluated_path_radians"]["count"] == 4
    assert cases["5SD5_HWI"]["placement_orientation"][
        "source_proposal_to_final_translation_norm_angstrom"
    ]["count"] == 4
    assert (
        "internal_energy"
        in cases["5SD5_HWI"]["internal_geometry_energy"][
            "candidate_failed_check_counts"
        ]
    )
    assert all(
        row["causal_diagnosis"] == "unresolved_requires_coordinate_replay"
        for row in report["cases"]
    )


def test_authenticated_cli_builds_and_rejects_bound_input_tampering(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (
        repo_root,
        ab_report_path,
        baseline_receipts,
        rescue_receipts,
        baseline_first_path,
        baseline_first_raw,
        baseline_analysis_path,
    ) = _authenticated_inputs(tmp_path)
    ab_report = json.loads(ab_report_path.read_bytes())
    output = Path(".betelgeuze") / "failure-atlas.json"
    arguments = [
        "--repo-root",
        str(repo_root),
        "--ab-report",
        ab_report_path.relative_to(repo_root).as_posix(),
        "--expected-ab-report-sha256",
        ab_report["report_sha256"],
        "--baseline-receipts",
        str(baseline_receipts),
        "--rescue-receipts",
        str(rescue_receipts),
        "--output",
        str(output),
    ]

    assert atlas_builder.main(arguments) == 0
    emitted = json.loads((repo_root / output).read_bytes())
    assert emitted["case_count"] == 7
    assert emitted["failure_class_counts"] == {
        "invalid_top1": 5,
        "valid_nonnative_top1": 2,
    }
    assert (repo_root / output).stat().st_mode & 0o777 == 0o600
    assert json.loads(capsys.readouterr().out)["report_sha256"] == emitted[
        "report_sha256"
    ]
    with pytest.raises(FileExistsError):
        atlas_builder.main(arguments)

    tampered_receipt = json.loads(baseline_first_raw)
    tampered_receipt.pop("receipt_sha256")
    tampered_receipt["command"] = ["tampered-but-self-hashed"]
    baseline_first_path.write_bytes(
        _canonical_bytes(_seal(tampered_receipt)) + b"\n"
    )
    with pytest.raises(ValueError, match="contradict the analysis"):
        atlas_builder.build_authenticated_failure_atlas(
            repo_root=repo_root,
            ab_report_path=ab_report_path,
            expected_ab_report_sha256=ab_report["report_sha256"],
            baseline_receipts_path=baseline_receipts,
            rescue_receipts_path=rescue_receipts,
        )

    baseline_first_path.write_bytes(baseline_first_raw)
    tampered_analysis = json.loads(baseline_analysis_path.read_bytes())
    tampered_analysis.pop("report_sha256")
    tampered_analysis["source_receipts_sha256"] = {
        **tampered_analysis["source_receipts_sha256"],
        next(iter(tampered_analysis["source_receipts_sha256"])): "9" * 64,
    }
    baseline_analysis_path.write_bytes(
        _canonical_bytes(_seal(tampered_analysis, "report_sha256")) + b"\n"
    )
    with pytest.raises(ValueError, match="analysis binding"):
        atlas_builder.build_authenticated_failure_atlas(
            repo_root=repo_root,
            ab_report_path=ab_report_path,
            expected_ab_report_sha256=ab_report["report_sha256"],
            baseline_receipts_path=baseline_receipts,
            rescue_receipts_path=rescue_receipts,
        )


def test_failure_atlas_is_order_stable_and_self_hashed() -> None:
    report, baseline, rescue, ab_report = _build()
    reverse = atlas_builder.build_failure_atlas(
        ab_report=ab_report,
        baseline_results=dict(reversed(tuple(baseline.items()))),
        rescue_results=dict(reversed(tuple(rescue.items()))),
        evidence_binding=dict(reversed(tuple(_binding().items()))),
    )

    assert reverse == report
    projection = dict(report)
    observed = projection.pop("report_sha256")
    assert observed == _sha256(projection)
    encoded = _canonical_bytes(report)
    assert b"score_term_binary64_hex" not in encoded
    assert b'contains_fresh_internal_blind_holdout":false' in encoded


def test_failure_atlas_rejects_fresh_or_case_set_drift() -> None:
    _, baseline, rescue, ab_report = _build()
    fresh_id = FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0]
    drifted = deepcopy(ab_report)
    drifted.pop("report_sha256")
    drifted["case_ids"][-1] = fresh_id
    drifted["report_sha256"] = _sha256(drifted)

    with pytest.raises(ValueError, match="identity or safety"):
        atlas_builder.build_failure_atlas(
            ab_report=drifted,
            baseline_results=baseline,
            rescue_results=rescue,
            evidence_binding=_binding(),
        )

    removed = dict(rescue)
    removed.pop("6WTN_RXT")
    with pytest.raises(ValueError, match="case set"):
        atlas_builder.build_failure_atlas(
            ab_report=ab_report,
            baseline_results=baseline,
            rescue_results=removed,
            evidence_binding=_binding(),
        )


def test_failure_atlas_rejects_diagnostic_or_ab_hash_drift() -> None:
    _, baseline, rescue, ab_report = _build()
    invalid_hash = deepcopy(ab_report)
    invalid_hash["report_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="self-hash"):
        atlas_builder.build_failure_atlas(
            ab_report=invalid_hash,
            baseline_results=baseline,
            rescue_results=rescue,
            evidence_binding=_binding(),
        )

    invalid_schema = deepcopy(rescue)
    invalid_schema["6VTA_AKN"]["engine_v2_diagnostics"]["schema_id"] = (
        PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID
    )
    with pytest.raises(ValueError, match="diagnostics"):
        atlas_builder.build_failure_atlas(
            ab_report=ab_report,
            baseline_results=baseline,
            rescue_results=invalid_schema,
            evidence_binding=_binding(),
        )


def test_failure_atlas_rejects_selected_torsion_or_parent_coordinate_drift() -> None:
    _, baseline, rescue, ab_report = _build()
    selected = deepcopy(rescue)
    candidate = selected["6VTA_AKN"]["engine_v2_diagnostics"]["candidates"][8]
    payload = dict(candidate["refinement_receipt_payload"])
    payload.pop("receipt_sha256")
    payload["torsion_selected"] = True
    candidate["refinement_receipt_payload"] = _seal(payload)
    candidate["refinement_receipt_sha256"] = payload["receipt_sha256"]

    with pytest.raises(ValueError, match="candidate-level A/B changes"):
        atlas_builder.build_failure_atlas(
            ab_report=ab_report,
            baseline_results=baseline,
            rescue_results=selected,
            evidence_binding=_binding(),
        )


@pytest.mark.parametrize(
    "path",
    (
        Path(".env"),
        Path("credentials.env.local"),
        Path("fresh-128") / "receipt.json",
        Path("fresh-redocking-128") / "receipt.json",
    ),
)
def test_failure_atlas_rejects_prohibited_paths_before_read(path: Path) -> None:
    with pytest.raises(ValueError, match="uses a prohibited path"):
        atlas_builder._load_object(path, name="test input")


def test_failure_atlas_rejects_outside_output_before_creating_parent(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside" / "atlas.json"

    with pytest.raises(ValueError, match="inside the repository"):
        atlas_builder._write_exclusive(repo_root, outside, b"{}\n")

    assert not outside.parent.exists()

    inside = Path(".betelgeuze") / "atlas.json"
    atlas_builder._write_exclusive(repo_root, inside, b"{}\n")
    written = repo_root / inside
    assert written.read_bytes() == b"{}\n"
    assert written.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        atlas_builder._write_exclusive(repo_root, inside, b"changed\n")
