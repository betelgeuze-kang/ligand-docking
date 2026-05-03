from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_positive_coverage_expansion_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_expansion_packet_keeps_claims_blocked_and_automates_three_positive_gap(tmp_path: Path) -> None:
    ci_packet = tmp_path / "runs" / "gpcr_ci_low_recovery_packet_current.json"
    rank_diag = tmp_path / "runs" / "gpcr_core_rank_diagnostics_current.json"
    rows_csv = tmp_path / "runs" / "stage5_rows.csv"
    summary_json = tmp_path / "runs" / "stage5_summary.json"
    reference_csv = tmp_path / "config" / "gpcr_reference.csv"
    splits_csv = tmp_path / "config" / "gpcr_splits.csv"
    _write_json(
        ci_packet,
        {
            "summary": {
                "ranking_positive_count": 6,
                "ranking_pr_auc_ci_low": 0.128,
                "threshold": 0.45,
                "ci_low_blocker": True,
            },
            "claim_coverage_requirement": {
                "observed_positive_count": 6,
                "minimum_positive_count_for_claim": 9,
                "positive_coverage_gap": 3,
            },
            "recovery_interpretation": {"claim_promotion_allowed": False},
        },
    )
    _write_json(
        rank_diag,
        {
            "summary": {"claim_safe": False, "candidate_count": 1},
            "candidates": [
                {
                    "candidate_id": "gpcr_core_candidate_v1",
                    "positive_count": 6,
                    "positive_ligand_ranks": [
                        {"rank": 1, "ligand_id": "carvedilol"},
                        {"rank": 2, "ligand_id": "timolol"},
                    ],
                    "top20_composition": {"target_counts": {"ADRB2_GPCR_BLIND": 20}},
                }
            ],
        },
    )
    _write_json(summary_json, {"metrics": {"pr_auc": 0.59}})
    _write_csv(
        rows_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "is_binder": "1",
                "role": "far_ood_eval",
                "binding_score_composite_v7": "-12.0",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "role": "far_ood_eval",
                "binding_score_composite_v7": "-11.0",
            },
        ],
    )
    _write_csv(
        reference_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "reference_binding_kcal_mol": "-9.1",
                "is_binder": "1",
                "source": "gpcr_blind_proxy_v1",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "chembl2012522",
                "reference_binding_kcal_mol": "-14.895",
                "is_binder": "1",
                "source": "chembl_blind_adrb2_v1:Ki:pchembl=10.92",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "chembl4863525",
                "reference_binding_kcal_mol": "-14.731",
                "is_binder": "1",
                "source": "chembl_blind_adrb2_v1:Ki:pchembl=10.80",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "chembl4874819",
                "reference_binding_kcal_mol": "-14.458",
                "is_binder": "1",
                "source": "chembl_blind_adrb2_v1:Ki:pchembl=10.60",
            },
        ],
    )
    _write_csv(
        splits_csv,
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "chembl2012522", "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "chembl4863525", "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "chembl4874819", "role": "far_ood_eval"},
        ],
    )

    payload = mod.build_packet(
        ci_packet_json=ci_packet,
        rank_diagnostics_json=rank_diag,
        stage5_rows_csv=rows_csv,
        stage5_summary_json=summary_json,
        reference_csv=reference_csv,
        splits_csv=splits_csv,
        family_scorecard_json=None,
        frozen_packet_json=None,
    )

    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["reference_candidate_count"] == 3
    assert payload["summary"]["selected_candidate_count"] == 3
    assert payload["claim_boundaries"]["claim_promotion_allowed"] is False
    assert payload["claim_boundaries"]["router_claim_allowed"] is False
    assert payload["claim_boundaries"]["platform_claim_allowed"] is False
    assert payload["coverage_requirement"]["observed_positive_count"] == 6
    assert payload["coverage_requirement"]["minimum_non_leaky_positive_additions"] == 3
    assert payload["coverage_requirement"]["minimum_positive_count_for_frozen_packet"] == 9
    assert len(payload["required_positive_addition_rows"]) == 3
    assert {row["row_classification"] for row in payload["required_positive_addition_rows"]} == {
        "possible_target_ligand_row"
    }
    assert all(row["leakage_precheck_required"] is True for row in payload["required_positive_addition_rows"])
    assert payload["risk_classification_rows"][0]["row_classification"] == "leakage_or_target_specific_bias_risk_row"
    assert payload["risk_classification_rows"][0]["risk_type"] == "single_target_positive_coverage"
    assert [row["ligand_id"] for row in payload["selected_candidate_target_ligand_rows"]] == [
        "chembl2012522",
        "chembl4863525",
        "chembl4874819",
    ]
    assert payload["selected_candidate_target_ligand_rows"][0]["risk_flags"] == [
        "target_specific_adrb2_bias_review_required"
    ]
    assert payload["selected_candidate_target_ligand_rows"][0]["claim_policy"] == (
        "coverage_candidate_only_not_router_or_platform_claim"
    )
    assert payload["family_held_out_gate"]["status"] == "missing_or_not_green"
    assert payload["family_held_out_gate"]["router_platform_claim_allowed"] is False
    assert payload["full_100k_guarded_rerun_eligibility"]["eligible"] is False
    assert payload["full_100k_guarded_rerun_eligibility"]["reason"] == "frozen_packet_missing"


def test_full_100k_guarded_rerun_eligibility_requires_frozen_positive_count_at_least_nine(
    tmp_path: Path,
) -> None:
    ci_packet = tmp_path / "runs" / "ci.json"
    rank_diag = tmp_path / "runs" / "diag.json"
    frozen_eight = tmp_path / "runs" / "frozen8.json"
    frozen_nine = tmp_path / "runs" / "frozen9.json"
    scorecard = tmp_path / "runs" / "scorecard.json"
    _write_json(
        ci_packet,
        {
            "summary": {"ranking_positive_count": 8},
            "claim_coverage_requirement": {
                "observed_positive_count": 8,
                "minimum_positive_count_for_claim": 9,
                "positive_coverage_gap": 1,
            },
        },
    )
    _write_json(rank_diag, {"summary": {"claim_safe": False}, "candidates": []})
    _write_json(frozen_eight, {"summary": {"frozen": True, "positive_count": 8}})
    _write_json(frozen_nine, {"summary": {"frozen": True, "positive_count": 9}})
    _write_json(scorecard, {"summary": {"scorecard_level_status": "pass", "acceptance_overall_pass": True}})

    blocked = mod.build_packet(
        ci_packet_json=ci_packet,
        rank_diagnostics_json=rank_diag,
        stage5_rows_csv=None,
        stage5_summary_json=None,
        reference_csv=None,
        splits_csv=None,
        family_scorecard_json=scorecard,
        frozen_packet_json=frozen_eight,
    )
    eligible = mod.build_packet(
        ci_packet_json=ci_packet,
        rank_diagnostics_json=rank_diag,
        stage5_rows_csv=None,
        stage5_summary_json=None,
        reference_csv=None,
        splits_csv=None,
        family_scorecard_json=scorecard,
        frozen_packet_json=frozen_nine,
    )

    assert blocked["full_100k_guarded_rerun_eligibility"]["eligible"] is False
    assert blocked["full_100k_guarded_rerun_eligibility"]["reason"] == "positive_count_below_9"
    assert eligible["full_100k_guarded_rerun_eligibility"]["eligible"] is True
    assert eligible["full_100k_guarded_rerun_eligibility"]["reason"] == "frozen_positive_count_ready"
    assert eligible["claim_boundaries"]["claim_promotion_allowed"] is False
    assert eligible["family_held_out_gate"]["status"] == "green"
    assert eligible["family_held_out_gate"]["router_platform_claim_allowed"] is False


def test_cli_writes_json_and_markdown_packet(tmp_path: Path) -> None:
    ci_packet = tmp_path / "runs" / "ci.json"
    rank_diag = tmp_path / "runs" / "diag.json"
    out_json = tmp_path / "runs" / "packet.json"
    out_md = tmp_path / "runs" / "packet.md"
    _write_json(
        ci_packet,
        {
            "summary": {"ranking_positive_count": 6},
            "claim_coverage_requirement": {
                "observed_positive_count": 6,
                "minimum_positive_count_for_claim": 9,
                "positive_coverage_gap": 3,
            },
        },
    )
    _write_json(rank_diag, {"summary": {"claim_safe": False}, "candidates": []})

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_positive_coverage_expansion_packet.py"),
            "--ci-packet-json",
            str(ci_packet),
            "--rank-diagnostics-json",
            str(rank_diag),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    md = out_md.read_text(encoding="utf-8")
    assert payload["packet_type"] == "gpcr_positive_coverage_expansion"
    assert "GPCR Positive Coverage Expansion Packet" in md
    assert "claim_promotion_allowed=false" in md
    assert "minimum_non_leaky_positive_additions=3" in md
    assert "full_100k_guarded_rerun_eligible=false" in md
    assert "Selected Candidate Rows" in md
