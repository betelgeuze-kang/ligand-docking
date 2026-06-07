from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_pxr_authoritative_reconciliation_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _request() -> dict[str, object]:
    return {
        "summary": {"request_row_count": 2},
        "rows": [
            {
                "packet_step": "core_eval_non_binder_01",
                "candidate_name": "acetaminophen",
                "current_binder_label": "non_binder",
                "request_mode": "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required",
            },
            {
                "packet_step": "ood_fit_binder_01",
                "candidate_name": "bexarotene",
                "current_binder_label": "binder",
                "request_mode": "exact_human_pxr_quantitative_binder_value_required",
            },
        ],
    }


def _gate() -> dict[str, object]:
    return {
        "summary": {
            "blocked_row_count": 2,
            "authoritative_apply_allowed_count": 0,
            "claim_safe_quantitative_ready_count": 0,
        },
        "rows": [
            {
                "packet_step": "core_eval_non_binder_01",
                "ligand": "acetaminophen",
                "review_bucket": "defer_pending_target_specific_evidence",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "authoritative_apply_allowed": False,
                "claim_safe_quantitative_ready": False,
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,activity_proxy_conflicts_with_non_binder",
            },
            {
                "packet_step": "ood_fit_binder_01",
                "ligand": "bexarotene",
                "review_bucket": "defer_pending_target_specific_evidence",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "authoritative_apply_allowed": False,
                "claim_safe_quantitative_ready": False,
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,claim_safe_quantitative_value_missing",
            },
        ],
    }


def _fill() -> dict[str, object]:
    return {
        "summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 2},
        "readiness_rows": [
            {"packet_step": "core_eval_non_binder_01", "ready_for_apply": "no", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
            {"packet_step": "ood_fit_binder_01", "ready_for_apply": "no", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
        ],
    }


def _workbook() -> dict[str, object]:
    return {
        "workbook_rows": [
            {"packet_step": "core_eval_non_binder_01", "replacement_ligand_id": "acetaminophen", "row_ready_for_apply": "no"},
            {"packet_step": "ood_fit_binder_01", "replacement_ligand_id": "bexarotene", "row_ready_for_apply": "no"},
        ]
    }


def test_pxr_authoritative_reconciliation_keeps_intake_applied_fail_closed() -> None:
    payload = mod.build_payload(
        intake_payload={"summary": {"intake_applied": True, "manual_commit_override_count": 2, "captured_supportive_count": 2}},
        request_payload=_request(),
        gate_payload=_gate(),
        fill_readiness_payload=_fill(),
        workbook_payload=_workbook(),
    )

    summary = payload["summary"]
    assert summary["intake_applied"] is True
    assert summary["manual_commit_override_count"] == 2
    assert summary["request_count_matches_gate"] is True
    assert summary["reconciled_blocked_row_count"] == 2
    assert summary["authoritative_apply_allowed_count"] == 0
    assert summary["authoritative_promotion_allowed"] is False
    assert all(row["reconciliation_status"] == "capture_or_workbook_present_but_authoritative_apply_blocked" for row in payload["rows"])


def test_pxr_authoritative_reconciliation_cli_writes_outputs(tmp_path: Path) -> None:
    intake = tmp_path / "intake.json"
    request = tmp_path / "request.json"
    gate = tmp_path / "gate.json"
    fill = tmp_path / "fill.json"
    workbook = tmp_path / "workbook.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    intake.write_text(json.dumps({"summary": {"intake_applied": True}}), encoding="utf-8")
    request.write_text(json.dumps(_request()), encoding="utf-8")
    gate.write_text(json.dumps(_gate()), encoding="utf-8")
    fill.write_text(json.dumps(_fill()), encoding="utf-8")
    workbook.write_text(json.dumps(_workbook()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_pxr_authoritative_reconciliation_packet.py",
            "--intake-json",
            str(intake),
            "--request-json",
            str(request),
            "--gate-json",
            str(gate),
            "--fill-readiness-json",
            str(fill),
            "--workbook-json",
            str(workbook),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["reconciled_blocked_row_count"] == 2
    assert "PXR Authoritative Reconciliation Packet" in out_md.read_text(encoding="utf-8")
    assert "packet_step" in out_csv.read_text(encoding="utf-8")
