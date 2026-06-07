from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_pxr_next_verification_slice(tmp_path: Path) -> None:
    sheet_csv = tmp_path / "sheet.csv"
    capture_json = tmp_path / "capture.json"
    out_json = tmp_path / "slice.json"
    out_csv = tmp_path / "slice.csv"
    out_md = tmp_path / "slice.md"
    sheet_csv.write_text(
        "\n".join(
            [
                "priority_rank,packet_step,replacement_ligand_id,replacement_is_binder,verification_status",
                "1,core_eval_binder_01,rifampicin,1,verified_chembl_activity_pending_workbook_copy",
                "7,ood_fit_binder_01,bexarotene,1,pending_binding_provenance_review",
                "8,ood_eval_non_binder_01,nicotinamide,0,pending_binding_provenance_review",
                "9,ood_eval_non_binder_02,ibuprofen,0,pending_binding_provenance_review",
            ]
        ),
        encoding="utf-8",
    )
    capture_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "packet_step": "ood_fit_binder_01",
                        "supports_local_target_specific_human_pxr": "yes",
                        "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                        "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                        "manual_next_required_action": "curate_quantitative_binding_value",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_pxr_next_verification_slice.py"),
            "--sheet-csv",
            str(sheet_csv),
            "--capture-sheet-json",
            str(capture_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["contains_binder_gap"] is True
    assert payload["summary"]["supportive_binder_review_count"] == 0
    assert payload["summary"]["confirmed_binder_quantitative_gap_count"] == 1
    assert payload["rows"][0]["replacement_ligand_id"] == "ibuprofen"
    assert payload["rows"][0]["assay_type_honesty"] == "activity_upper_bound_only_not_quantitative_nonbinder"
    assert payload["rows"][1]["replacement_ligand_id"] == "bexarotene"
    assert payload["rows"][1]["assay_type_honesty"] == "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing"
    assert payload["rows"][1]["next_required_action"] == "curate_quantitative_binding_value"


def test_build_pxr_next_verification_slice_prefers_capture_sheet_manual_fields(tmp_path: Path) -> None:
    sheet_csv = tmp_path / "sheet.csv"
    capture_json = tmp_path / "capture.json"
    out_json = tmp_path / "slice.json"
    out_csv = tmp_path / "slice.csv"
    out_md = tmp_path / "slice.md"
    sheet_csv.write_text(
        "\n".join(
            [
                "priority_rank,packet_step,replacement_ligand_id,replacement_is_binder,verification_status",
                "6,core_eval_non_binder_02,caffeine,0,pending_binding_provenance_review",
            ]
        ),
        encoding="utf-8",
    )
    capture_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "packet_step": "core_eval_non_binder_02",
                        "policy_bucket": "defer",
                        "capture_status": "captured_supportive",
                        "source_note": "Exact human PXR upper-bound wording is available and should be surfaced for review.",
                        "manual_assay_type_honesty": "human_pxr_upper_bound_only_manual_review_required",
                        "manual_next_required_action": "manual_negative_evidence_review",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/product/build_pxr_next_verification_slice.py"),
            "--sheet-csv",
            str(sheet_csv),
            "--capture-sheet-json",
            str(capture_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert row["replacement_ligand_id"] == "caffeine"
    assert row["assay_type_honesty"] == "human_pxr_upper_bound_only_manual_review_required"
    assert row["next_required_action"] == "manual_negative_evidence_review"
    assert "Exact human PXR upper-bound wording" in row["review_reason"]
