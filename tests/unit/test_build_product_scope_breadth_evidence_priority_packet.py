from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_product_scope_breadth_evidence_priority_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _queue() -> dict[str, object]:
    return {
        "summary": {"queue_item_count": 4},
        "rows": [
            {
                "priority": 1,
                "domain": "transporter",
                "item_id": "AQP1.core_binder_01",
                "item_type": "scientific_evidence_request",
                "candidate_or_check": "AqB013",
                "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                "source_artifact": "runs/transporter.json",
            },
            {
                "priority": 2,
                "domain": "transporter",
                "item_id": "GLUT1_4PYP.core_binder_02",
                "item_type": "scientific_evidence_request",
                "candidate_or_check": "glut1_placeholder_binder_02",
                "request_mode": "direct_binding_kcal_or_keep_functional_review_only_required",
                "source_artifact": "runs/transporter.json",
            },
            {
                "priority": 3,
                "domain": "pxr",
                "item_id": "ood_fit_binder_01",
                "item_type": "scientific_evidence_request",
                "candidate_or_check": "bexarotene",
                "request_mode": "exact_human_pxr_quantitative_binder_value_required",
                "source_artifact": "runs/pxr.json",
            },
            {
                "priority": 4,
                "domain": "general_protein_ligand",
                "item_id": "domain_ready.pxr",
                "item_type": "breadth_domain",
                "candidate_or_check": "domain_ready.pxr",
                "request_mode": "claim_gate_prerequisite_required",
                "source_artifact": "runs/general.json",
            },
        ],
    }


def _transporter_binder_gate() -> dict[str, object]:
    return {
        "summary": {
            "status": "transporter_binder_promotion_gate_ready",
            "binder_promotion_ready": True,
            "target_ready_for_promotion_count": 1,
            "target_blocked_for_promotion_count": 1,
            "target_ready_for_promotion_ids": ["GLUT1"],
            "target_blocked_for_promotion_ids": ["AQP1"],
            "primary_blocker_target_id": "AQP1",
            "primary_blocker_packet_step": "core_binder_01",
            "primary_blocker_candidate_name": "bacopaside II",
            "primary_blocker_signal": "target_ready_for_promotion_ids=GLUT1;target_blocked_for_promotion_ids=AQP1",
        }
    }


def test_scope_breadth_evidence_priority_packet_classifies_local_and_external_rows(tmp_path: Path) -> None:
    crosscheck = tmp_path / "crosscheck"
    crosscheck.mkdir()
    (crosscheck / "bindingdb_aqp1_p29972.json").write_text("{}", encoding="utf-8")
    (crosscheck / "chembl_activity_glut1_wzb117.json").write_text("{}", encoding="utf-8")

    payload = mod.build_payload(
        queue_payload=_queue(),
        transporter_binder_gate_payload=_transporter_binder_gate(),
        crosscheck_dir=crosscheck,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_scope_breadth_evidence_priority_packet_ready"
    assert summary["queue_item_count"] == 4
    assert summary["source_queue_item_count"] == 4
    assert summary["scientific_evidence_request_count"] == 3
    assert summary["claim_gate_prerequisite_count"] == 1
    assert summary["local_crosscheck_candidate_count"] == 2
    assert summary["external_primary_exact_evidence_required_count"] == 1
    assert summary["review_only_keep_blocked_count"] == 1
    assert summary["transporter_binder_gate_present"] is True
    assert summary["transporter_target_ready_for_promotion_ids"] == ["GLUT1"]
    assert summary["transporter_target_blocked_for_promotion_ids"] == ["AQP1"]
    assert summary["transporter_priority_target_ready_item_count"] == 1
    assert summary["transporter_priority_target_blocked_item_count"] == 1
    assert summary["transporter_primary_blocker_target_id"] == "AQP1"
    assert summary["transporter_primary_blocker_packet_step"] == "core_binder_01"
    assert summary["all_operator_packet_bindings_ready"] is True
    assert summary["operator_packet_binding_ready_count"] == 4
    assert summary["operator_packet_binding_missing_count"] == 0
    assert summary["top_item_id"] == "AQP1.core_binder_01"
    assert summary["top_target_id"] == "AQP1"
    assert summary["top_target_promotion_status"] == "target_blocked_for_promotion"
    assert summary["top_target_blocked_for_promotion"] is True
    assert summary["top_required_evidence_type"] == "exact_transporter_target_pair_quantitative_binder_kcal"
    assert summary["top_review_template_artifact"] == "runs/transporter_manual_review_intake_template_current.json"
    assert summary["top_apply_gate_artifact"] == "runs/transporter_binder_promotion_gate_current.json"
    assert summary["scope_promotion_allowed"] is False
    assert payload["rows"][0]["evidence_priority_bucket"] == "local_crosscheck_review_present_but_exact_quant_required"
    assert payload["rows"][0]["target_id"] == "AQP1"
    assert payload["rows"][0]["target_blocked_for_promotion"] is True
    assert payload["rows"][1]["target_id"] == "GLUT1"
    assert payload["rows"][1]["target_ready_for_promotion"] is True
    assert payload["rows"][0]["operator_packet_binding_key"] == "transporter:AQP1.core_binder_01"
    assert payload["rows"][0]["operator_packet_binding_ready"] is True
    assert payload["rows"][1]["evidence_priority_bucket"] == "review_only_keep_blocked_until_direct_binding"
    assert payload["rows"][2]["evidence_priority_bucket"] == "external_primary_exact_evidence_required"
    assert payload["rows"][2]["review_template_artifact"] == "runs/pxr_exact_evidence_review_intake_template_current.json"
    assert payload["rows"][2]["apply_gate_artifact"] == "runs/pxr_blocked_row_promotion_gate_current.json"
    assert payload["rows"][3]["evidence_priority_bucket"] == "claim_gate_waits_on_domain_evidence"
    assert payload["rows"][3]["review_template_artifact"] == "runs/general_protein_ligand_claim_blocker_packet_current.json"
    assert all(row["authoritative_apply_allowed"] is False for row in payload["rows"])


def test_scope_breadth_evidence_priority_packet_cli_writes_outputs(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    transporter_binder_gate = tmp_path / "transporter_binder_gate.json"
    crosscheck = tmp_path / "crosscheck"
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"
    crosscheck.mkdir()
    (crosscheck / "uniprot_aqp1_p29972_latest.json").write_text("{}", encoding="utf-8")
    queue.write_text(json.dumps(_queue()), encoding="utf-8")
    transporter_binder_gate.write_text(json.dumps(_transporter_binder_gate()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_product_scope_breadth_evidence_priority_packet.py",
            "--queue-json",
            str(queue),
            "--crosscheck-dir",
            str(crosscheck),
            "--transporter-binder-gate-json",
            str(transporter_binder_gate),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["priority_packet_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"][
        "transporter_target_blocked_for_promotion_ids"
    ] == ["AQP1"]
    assert "Product Scope Breadth Evidence Priority Packet" in out_md.read_text(encoding="utf-8")
    assert "target_blocked_for_promotion" in out_md.read_text(encoding="utf-8")
    assert "evidence_priority_bucket" in out_csv.read_text(encoding="utf-8")
    assert "target_promotion_status" in out_csv.read_text(encoding="utf-8")
