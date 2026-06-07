from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_pxr_blocked_evidence_request_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _gate() -> dict[str, object]:
    return {
        "summary": {
            "blocked_row_count": 2,
            "claim_safe_quantitative_ready_count": 0,
            "authoritative_apply_allowed_count": 0,
        },
        "rows": [
            {
                "packet": "core",
                "packet_step": "core_eval_non_binder_01",
                "ligand": "acetaminophen",
                "binder": "0",
                "review_bucket": "defer_pending_target_specific_evidence",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "evidence_signal": "exact_human_dual_mode_activity_conflict::keep_deferred",
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,activity_proxy_conflicts_with_non_binder",
            },
            {
                "packet": "ood",
                "packet_step": "ood_fit_binder_01",
                "ligand": "bexarotene",
                "binder": "1",
                "review_bucket": "defer_pending_target_specific_evidence",
                "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                "evidence_signal": "supportive_manual_confirmation_quantitative_gap::no",
                "fail_closed_blockers": "replacement_reference_binding_kcal_mol,claim_safe_quantitative_value_missing",
            },
        ],
    }


def _readiness() -> dict[str, object]:
    return {
        "readiness_rows": [
            {"packet": "core", "packet_step": "core_eval_non_binder_01", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
            {"packet": "ood", "packet_step": "ood_fit_binder_01", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
        ]
    }


def _workbook() -> dict[str, object]:
    return {
        "workbook_rows": [
            {
                "packet_step": "core_eval_non_binder_01",
                "replacement_ligand_id": "acetaminophen",
                "replacement_is_binder": "0",
                "replacement_role": "far_ood_eval",
                "replacement_pubchem_cid": "1983",
            },
            {
                "packet_step": "ood_fit_binder_01",
                "replacement_ligand_id": "bexarotene",
                "replacement_is_binder": "1",
                "replacement_role": "fit",
                "replacement_pubchem_cid": "82146",
            },
        ]
    }


def test_build_pxr_blocked_evidence_request_packet_splits_binder_and_negative_requests() -> None:
    payload = mod.build_payload(gate_payload=_gate(), fill_readiness_payload=_readiness(), workbook_payload=_workbook())

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}
    assert summary["evidence_request_ready"] is True
    assert summary["request_row_count"] == 2
    assert summary["binder_request_row_count"] == 1
    assert summary["negative_request_row_count"] == 1
    assert summary["defer_request_row_count"] == 2
    assert summary["missing_field_focus"] == "replacement_reference_binding_kcal_mol"
    assert summary["claim_promotion_allowed"] is False
    assert rows["ood_fit_binder_01"]["request_mode"] == "exact_human_pxr_quantitative_binder_value_required"
    assert rows["core_eval_non_binder_01"]["request_mode"] == "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required"
    assert rows["ood_fit_binder_01"]["candidate_pubchem_cid"] == "82146"
    assert "RXR-only" in rows["ood_fit_binder_01"]["excluded_shortcuts"]


def test_build_pxr_blocked_evidence_request_packet_cli(tmp_path: Path) -> None:
    gate = tmp_path / "gate.json"
    readiness = tmp_path / "readiness.json"
    workbook = tmp_path / "workbook.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    gate.write_text(json.dumps(_gate()), encoding="utf-8")
    readiness.write_text(json.dumps(_readiness()), encoding="utf-8")
    workbook.write_text(json.dumps(_workbook()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_pxr_blocked_evidence_request_packet.py",
            "--gate-json",
            str(gate),
            "--fill-readiness-json",
            str(readiness),
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

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["request_row_count"] == 2
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# PXR Blocked Evidence Request Packet")
