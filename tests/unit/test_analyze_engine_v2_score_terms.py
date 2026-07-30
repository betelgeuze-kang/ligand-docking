from __future__ import annotations

from tools.analyze_engine_v2_score_terms import TERM_NAMES, analyze_results


def _result(case_id: str) -> dict[str, object]:
    candidates = []
    for index in range(64):
        terms = {name: 0.0 for name in TERM_NAMES}
        terms["weak_pocket_prior"] = float(index)
        terms["total_score"] = sum(terms.values())
        candidates.append(
            {
                "proposal_index": index,
                "status": "success",
                "proposal_mode": (
                    "uniform_fallback" if index >= 48 else "donor_acceptor_hotspot"
                ),
                "coordinate_fingerprint_sha256": f"{index + 1:064x}",
                "score": terms["total_score"],
                "rmsd_angstrom": 1.0 if index == 1 else 3.0,
                "geometric_valid": index != 0,
                "chemical_valid": True,
                "posebusters_failed_check_ids": (
                    ["minimum_distance_to_protein"] if index == 0 else []
                ),
                "score_term_binary64_hex": {
                    name: value.hex() for name, value in terms.items()
                },
            }
        )
    return {
        "case_id": case_id,
        "engine_id": "engine_v2",
        "status": "success",
        "engine_v2_diagnostics": {
            "ligand_atom_count": 12,
            "candidates": candidates,
        },
    }


def test_score_term_analysis_is_nonclaimable_and_detects_ablation() -> None:
    report = analyze_results(
        [_result("5SD5_HWI")],
        source_receipts_sha256={"receipt.json": "1" * 64},
    )

    assert report["claimable"] is False
    assert report["contains_fresh_internal_blind_holdout"] is False
    assert report["sufficient_for_track_decision"] is False
    assert report["oracle_2a_recovery_case_count"] == 1
    assert report["full_top1_recovery_case_count"] == 0
    assert report["term_summary"]["weak_pocket_prior"][
        "removed_top1_changed_case_count"
    ] == 0
    assert report["proposal_mode_summary"]["donor_acceptor_hotspot"][
        "oracle_contribution_case_count"
    ] == 1
    assert report["candidate_diagnostic_summary"][
        "posebusters_failed_check_counts"
    ] == {"minimum_distance_to_protein": 1}


def test_score_term_analysis_retains_typed_incomplete_pose_failure() -> None:
    result = _result("5SD5_HWI")
    result["status"] = "failure"
    result["failure_code"] = "engine_v2_pose_count_incomplete"
    diagnostics = result["engine_v2_diagnostics"]
    assert isinstance(diagnostics, dict)
    diagnostics["preparation_status"] = "success"
    candidates = diagnostics["candidates"]
    assert isinstance(candidates, list)
    for candidate in candidates[4:]:
        candidate.clear()
        candidate.update({"status": "failure"})

    report = analyze_results(
        [result, _result("5SIS_JSM")],
        source_receipts_sha256={"receipt.json": "1" * 64},
    )

    assert report["scored_case_count"] == 1
    assert report["preparation_excluded_case_count"] == 0
    assert report["candidate_count"] == 68
    assert report["cases"][0] == {
        "case_id": "5SD5_HWI",
        "scorer_analysis_status": "excluded_execution_failure",
        "execution_failure_code": "engine_v2_pose_count_incomplete",
        "candidate_success_count": 4,
    }
