from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pocketmd_lite_report as mod


_COLUMNS = [
    "entry_id",
    "family",
    "rank_pct",
    "selected_for_refine",
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in _COLUMNS})


def _green_row(entry_id: str = "LIG-1") -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "family": "gpcr",
        "rank_pct": 0.01,
        "local_min_ligand_rmsd_a": 1.2,
        "hbond_persistence": 0.75,
        "contact_persistence": 0.8,
        "initial_clash_count": 2,
        "clash_count": 0,
    }


def test_materializes_green_top_k_report(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    _write_csv(input_csv, [_green_row("a"), _green_row("b")])

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)

    assert artifact["materializer_status"] == mod.STATUS_MATERIALIZED
    summary = artifact["summary"]
    assert summary["status"] == "pocketmd_lite_report_ready"
    assert summary["top_k_only_policy_enforced"] is True
    assert summary["pocketmd_lite_claim_safe"] is True
    assert summary["selected_top_k_count"] == 2
    assert summary["refinement_blocker_count"] == 0
    assert summary["green_row_count"] == 2
    assert summary["yellow_row_count"] == 0
    assert summary["red_row_count"] == 0
    assert summary["abstain_row_count"] == 0
    assert summary["coarse_only_row_count"] == 0
    assert summary["claim_grade_metric_ready_row_count"] == 2
    assert summary["selected_banding_row_count"] == 2
    assert summary["claim_grade_band_counts"] == {
        "green": 2,
        "yellow": 0,
        "red": 0,
        "abstain": 0,
    }
    assert summary["banding_surface_ready"] is True
    assert summary["green_band_condition"] == {
        "local_min_ligand_rmsd_a_lte": 2.0,
        "hbond_persistence_gte": 0.5,
        "contact_persistence_gte": 0.5,
        "initial_clash_count_required": True,
        "clash_count_lte": 0,
        "clash_relief_report_required": True,
        "missing_evidence_band": "abstain",
        "local_min_failure_band": "red",
    }
    assert "local_min_ligand_rmsd_a <= 2.0" in summary["green_band_condition_text"]
    assert summary["mean_uncertainty_score"] is not None
    assert summary["high_uncertainty_count"] == 0
    assert summary["local_min_survival_reported_count"] == 2
    assert summary["local_min_survived_count"] == 2
    assert summary["hbond_persistence_reported_count"] == 2
    assert summary["contact_persistence_reported_count"] == 2
    assert summary["initial_clash_reported_count"] == 2
    assert summary["final_clash_reported_count"] == 2
    assert summary["clash_relief_reported_count"] == 2
    assert summary["clash_relief_observed_count"] == 2
    assert summary["missing_refinement_metric_names"] == []
    assert summary["top_k_refinement_evidence_ready"] is True
    assert summary["pocketmd_lite_claim_grade_contract_ready"] is False
    assert summary["pocketmd_lite_claim_promotion_allowed"] is False
    assert summary["claim_grade_requirement_ids"] == [
        "selected_top_k_minimum_met",
        "adrb2_three_collection_ready_rows",
        "drd3_oprd1_atom_frame_recovery",
        "local_min_ligand_rmsd_ready",
        "hbond_persistence_ready",
        "contact_persistence_ready",
        "clash_relief_ready",
        "green_yellow_red_abstain_banding_ready",
        "pocketmd_lite_claim_grade_contract_ready",
        "pocketmd_lite_claim_promotion_review_allowed",
    ]
    assert summary["claim_grade_requirement_row_count"] == 10
    assert summary["claim_grade_requirement_ready_row_count"] == 4
    assert summary["claim_grade_requirement_blocked_row_count"] == 6
    assert summary["claim_grade_primary_requirement_id"] == "selected_top_k_minimum_met"
    assert summary["claim_grade_primary_blocker"] == "selected_top_k_rows_below_required:2/3"
    requirements = {
        row["requirement_id"]: row for row in artifact["claim_grade_requirement_rows"]
    }
    assert requirements["local_min_ligand_rmsd_ready"]["ready"] is True
    assert requirements["hbond_persistence_ready"]["ready"] is True
    assert requirements["contact_persistence_ready"]["ready"] is True
    assert requirements["clash_relief_ready"]["ready"] is True
    assert requirements["pocketmd_lite_claim_promotion_review_allowed"]["ready"] is False
    assert all(
        row["claim_promotion_allowed"] is False
        and row["candidate_csv_update_allowed"] is False
        and row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        for row in artifact["claim_grade_requirement_rows"]
    )
    assert all(row["band"] == "green" for row in artifact["rows"])
    assert all(row["uncertainty_posture"] == "green_low_uncertainty" for row in artifact["rows"])


def test_claim_grade_contract_ready_requires_targeted_green_rows(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    _write_csv(
        input_csv,
        [
            _green_row("ADRB2_GPCR_BLIND:carvedilol"),
            _green_row("ADRB2_GPCR_BLIND:timolol"),
            _green_row("ADRB2_GPCR_BLIND:carazolol"),
            _green_row("CHEMBL234_DRD3_HUMAN:CHEMBL5841759"),
            _green_row("CHEMBL236_OPRD1_HUMAN:CHEMBL67192"),
        ],
    )

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)
    summary = artifact["summary"]

    assert summary["status"] == "pocketmd_lite_report_ready"
    assert summary["pocketmd_lite_claim_safe"] is True
    assert summary["pocketmd_lite_claim_grade_contract_ready"] is True
    assert summary["pocketmd_lite_claim_promotion_allowed"] is False
    assert summary["claim_grade_requirement_row_count"] == 10
    assert summary["claim_grade_requirement_ready_row_count"] == 9
    assert summary["claim_grade_requirement_blocked_row_count"] == 1
    assert summary["claim_grade_primary_requirement_id"] == (
        "pocketmd_lite_claim_promotion_review_allowed"
    )
    requirements = {
        row["requirement_id"]: row for row in artifact["claim_grade_requirement_rows"]
    }
    assert requirements["adrb2_three_collection_ready_rows"]["ready"] is True
    assert requirements["adrb2_three_collection_ready_rows"]["observed_value"] == "3"
    assert requirements["drd3_oprd1_atom_frame_recovery"]["ready"] is True
    assert requirements["drd3_oprd1_atom_frame_recovery"]["observed_value"] == "DRD3,OPRD1"
    assert requirements["green_yellow_red_abstain_banding_ready"]["ready"] is True
    assert requirements["pocketmd_lite_claim_promotion_review_allowed"]["ready"] is False


def test_collection_ready_targets_can_be_yellow_but_residual_clash_still_blocks(
    tmp_path: Path,
) -> None:
    input_csv = tmp_path / "in.csv"
    yellow_rows = []
    for entry_id in [
        "ADRB2_GPCR_BLIND:carvedilol",
        "ADRB2_GPCR_BLIND:timolol",
        "ADRB2_GPCR_BLIND:carazolol",
        "CHEMBL234_DRD3_HUMAN:CHEMBL5841759",
        "CHEMBL236_OPRD1_HUMAN:CHEMBL67192",
    ]:
        row = _green_row(entry_id)
        row["initial_clash_count"] = 5
        row["clash_count"] = 1
        yellow_rows.append(row)
    _write_csv(input_csv, yellow_rows)

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)
    summary = artifact["summary"]
    requirements = {
        row["requirement_id"]: row for row in artifact["claim_grade_requirement_rows"]
    }

    assert summary["green_row_count"] == 0
    assert summary["yellow_row_count"] == 5
    assert summary["claim_grade_metric_ready_row_count"] == 5
    assert requirements["adrb2_three_collection_ready_rows"]["ready"] is True
    assert requirements["adrb2_three_collection_ready_rows"]["observed_value"] == "3"
    assert requirements["drd3_oprd1_atom_frame_recovery"]["ready"] is True
    assert requirements["clash_relief_ready"]["ready"] is False
    assert summary["claim_grade_primary_requirement_id"] == "clash_relief_ready"
    assert summary["claim_grade_primary_blocker"] == "clash_relief_not_claim_grade"


def test_missing_refinement_evidence_abstains_and_blocks(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    _write_csv(input_csv, [{"entry_id": "top-a", "family": "gpcr", "rank_pct": 0.001}])

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)

    summary = artifact["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_report"
    assert summary["pocketmd_lite_claim_safe"] is False
    assert summary["refinement_blocker_count"] == 1
    assert summary["green_row_count"] == 0
    assert summary["yellow_row_count"] == 0
    assert summary["red_row_count"] == 0
    assert summary["abstain_row_count"] == 1
    assert summary["claim_grade_metric_ready_row_count"] == 0
    assert summary["selected_banding_row_count"] == 1
    assert summary["banding_surface_ready"] is True
    assert artifact["rows"][0]["band"] == "abstain"
    assert artifact["rows"][0]["reason_code"] == "missing_refinement_evidence"
    assert artifact["rows"][0]["uncertainty_score"] == 1.0
    assert artifact["rows"][0]["uncertainty_posture"] == "missing_refinement_evidence_high_uncertainty"
    assert summary["missing_refinement_evidence_count"] == 1
    assert summary["missing_refinement_metric_names"] == [
        "clash_count",
        "contact_persistence",
        "hbond_persistence",
        "initial_clash_count",
        "local_min_ligand_rmsd_a",
    ]
    assert summary["missing_refinement_metric_counts"]["local_min_ligand_rmsd_a"] == 1
    assert summary["top_k_refinement_evidence_ready"] is False
    assert summary["pocketmd_lite_claim_grade_contract_ready"] is False
    assert summary["claim_grade_requirement_blocked_row_count"] == 10
    assert summary["claim_grade_primary_requirement_id"] == "selected_top_k_minimum_met"


def test_report_can_consume_fill_preview_candidate_csv_without_mutating_canonical(
    tmp_path: Path,
) -> None:
    canonical_csv = tmp_path / "canonical.csv"
    preview_csv = tmp_path / "preview.candidates.csv"
    preview_json = tmp_path / "preview.json"
    _write_csv(canonical_csv, [{"entry_id": "top-a", "family": "gpcr", "rank_pct": 0.001}])
    _write_csv(preview_csv, [_green_row("top-a")])
    preview_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": mod.STATUS_FILL_PREVIEW_READY,
                    "preview_candidate_csv": str(preview_csv),
                    "preview_candidate_csv_ready": True,
                    "canonical_candidate_csv_mutated": False,
                    "candidate_csv_update_allowed": False,
                }
            }
        ),
        encoding="utf-8",
    )

    artifact = mod.build_pocketmd_lite_report_artifact(
        canonical_csv,
        candidate_fill_preview_json=preview_json,
    )

    summary = artifact["summary"]
    assert artifact["input_csv"] == str(preview_csv)
    assert artifact["source_input_csv"] == str(canonical_csv)
    assert artifact["candidate_fill_preview_applied"] is True
    assert summary["candidate_fill_preview_applied"] is True
    assert summary["candidate_fill_preview_canonical_candidate_csv_mutated"] is False
    assert summary["candidate_fill_preview_candidate_csv_update_allowed"] is False
    assert summary["missing_refinement_metric_names"] == []
    assert summary["green_row_count"] == 1
    assert summary["abstain_row_count"] == 0


def test_non_top_k_candidate_is_coarse_only_not_blocker(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    _write_csv(input_csv, [{"entry_id": "coarse", "family": "gpcr", "rank_pct": 0.7}])

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)

    assert artifact["summary"]["selected_top_k_count"] == 0
    assert artifact["summary"]["refinement_blocker_count"] == 0
    assert artifact["summary"]["coarse_only_row_count"] == 1
    assert artifact["summary"]["banding_surface_ready"] is False
    assert artifact["rows"][0]["band"] == "coarse_only"


def test_fail_closed_on_missing_csv(tmp_path: Path) -> None:
    artifact = mod.build_pocketmd_lite_report_artifact(tmp_path / "missing.csv")
    assert artifact["materializer_status"] == mod.STATUS_BLOCKED_MISSING
    assert artifact["summary"]["status"] == "blocked_pocketmd_lite_report"
    assert artifact["summary"]["green_band_condition"]["missing_evidence_band"] == "abstain"
    assert artifact["summary"]["claim_grade_metric_ready_row_count"] == 0
    assert artifact["summary"]["claim_grade_requirement_blocked_row_count"] == 10
    assert artifact["claim_grade_requirement_rows"][0]["requirement_id"] == (
        "selected_top_k_minimum_met"
    )


def test_fail_closed_on_bad_bool(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    row = _green_row()
    row["selected_for_refine"] = "perhaps"
    _write_csv(input_csv, [row])

    artifact = mod.build_pocketmd_lite_report_artifact(input_csv)

    assert artifact["materializer_status"] == mod.STATUS_BLOCKED_INVALID_ROW


def test_main_writes_artifacts(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    _write_csv(input_csv, [_green_row()])
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"

    rc = mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "pocketmd_lite_report_ready"
    out_md_text = out_md.read_text(encoding="utf-8")
    assert out_md_text.startswith("# PocketMD Lite Report")
    assert "green_band_condition" in out_md_text
    assert "Claim-Grade Requirement Checklist" in out_md_text
    row = list(csv.DictReader(out_csv.open(encoding="utf-8")))[0]
    assert row["band"] == "green"
    assert row["uncertainty_posture"] == "green_low_uncertainty"
    assert row["clash_relief_count"] == "2"
