from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_scope_breadth_work_order as mod


def _packet(summary: dict[str, object], rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"summary": summary, "rows": rows or []}


def test_scope_breadth_work_order_tracks_missing_domains() -> None:
    payload = mod.build_product_scope_breadth_work_order(
        scope_contract_packet=_packet(
            {
                "scope_breadth_ready": False,
                "ready_domains": ["ca2"],
                "missing_domains": ["transporter", "pxr", "general_protein_ligand"],
                "transporter_manual_review_decision_placeholder_count": 11,
                "transporter_manual_review_template_row_count": 11,
                "transporter_manual_review_direct_binding_evidence_required_count": 4,
                "transporter_manual_review_negative_quantitative_value_required_count": 6,
                "transporter_candidate_ready_for_apply_count": 0,
                "transporter_candidate_assignment_required_count": 7,
                "pxr_exact_review_template_row_count": 6,
                "pxr_exact_review_kcal_placeholder_count": 6,
                "pxr_exact_review_conflict_resolution_required_count": 3,
                "external_primary_exact_evidence_required_count": 6,
                "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
                "general_protein_ligand_platform_ready": False,
            },
            [
                {"domain": "transporter", "artifact": "runs/transporter.json", "observed": "placeholder=6"},
                {"domain": "pxr", "artifact": "runs/pxr.json", "observed": "blocked=6"},
                {
                    "domain": "general_protein_ligand",
                    "artifact": "runs/capability.json",
                    "observed": "allowed_scope_families=gpcr,ion_channel,kinase",
                },
            ],
        )
    )

    summary = payload["summary"]
    assert summary["status"] == "product_scope_breadth_work_order_ready"
    assert summary["open_item_count"] == 3
    assert summary["transporter_manual_review_decision_placeholder_count"] == 11
    assert summary["pxr_exact_review_kcal_placeholder_count"] == 6
    assert summary["pxr_exact_review_conflict_resolution_required_count"] == 3
    assert payload["rows"][0]["domain"] == "transporter"
    assert "manual_review_placeholders=11" in payload["rows"][0]["current_blocker_metrics"]
    assert "direct_binding_required=4" in payload["rows"][0]["current_blocker_metrics"]
    assert "placeholder_driven_rows=0" in payload["rows"][0]["acceptance_criteria"]
    assert "manual_review_decision_placeholder_count=0" in payload["rows"][0]["acceptance_criteria"]
    assert "claim_safe_binders>=1" in payload["rows"][0]["acceptance_criteria"]
    assert "build_transporter_p0_closure_packet.py" in payload["rows"][0]["verification_command"]
    assert "build_transporter_p0_evidence_acquisition_packet.py" in payload["rows"][0]["verification_command"]
    assert "build_transporter_local_crosscheck_triage_packet.py" in payload["rows"][0]["verification_command"]
    assert "build_transporter_slot_assignment_candidate_workbook.py" in payload["rows"][0]["verification_command"]
    assert "build_transporter_manual_review_intake_template.py" in payload["rows"][0]["verification_command"]
    assert payload["rows"][0]["verification_command"].index("build_transporter_slot_assignment_candidate_workbook.py") < payload[
        "rows"
    ][0]["verification_command"].index("build_transporter_manual_review_intake_template.py")
    assert "build_product_scope_breadth_evidence_intake_readiness.py" in payload["rows"][0]["verification_command"]
    assert "build_product_scope_breadth_evidence_acquisition_queue.py" in payload["rows"][0]["verification_command"]
    assert "build_product_scope_breadth_closure_checklist.py" in payload["rows"][0]["verification_command"]
    assert "build_product_ai_architecture_execution_backlog.py" in payload["rows"][0]["verification_command"]
    assert payload["rows"][0]["verification_command"].index("build_product_ai_architecture_execution_backlog.py") < payload[
        "rows"
    ][0]["verification_command"].index("build_product_ai_architecture_gap_closure.py")
    assert "six AQP1/GLUT1 core P0 closure rows" in payload["rows"][0]["risk_if_skipped"]
    assert "unresolved ligand evidence slots" in payload["rows"][0]["risk_if_skipped"]
    assert payload["rows"][1]["domain"] == "pxr"
    assert "kcal_placeholders=6" in payload["rows"][1]["current_blocker_metrics"]
    assert "conflict_resolution_required=3" in payload["rows"][1]["current_blocker_metrics"]
    assert "kcal_placeholder_count=0" in payload["rows"][1]["acceptance_criteria"]
    assert "conflict_resolution_required_count=0" in payload["rows"][1]["acceptance_criteria"]
    assert "queue_row_count" in payload["rows"][1]["acceptance_criteria"]
    assert "build_pxr_blocked_evidence_request_packet.py" in payload["rows"][1]["verification_command"]
    assert "build_pxr_blocked_row_promotion_gate.py" in payload["rows"][1]["verification_command"]
    assert "build_pxr_authoritative_reconciliation_packet.py" in payload["rows"][1]["verification_command"]
    assert "build_pxr_exact_evidence_review_intake_template.py" in payload["rows"][1]["verification_command"]
    assert "build_product_scope_breadth_evidence_intake_readiness.py" in payload["rows"][1]["verification_command"]
    assert "build_product_scope_breadth_closure_checklist.py" in payload["rows"][1]["verification_command"]
    assert payload["rows"][1]["verification_command"].index("build_pxr_authoritative_reconciliation_packet.py") < payload[
        "rows"
    ][1]["verification_command"].index("build_pxr_exact_evidence_review_intake_template.py")
    assert "authoritative reconciliation still shows six blocked rows" in payload["rows"][1]["risk_if_skipped"]
    assert payload["rows"][2]["domain"] == "general_protein_ligand"
    assert "missing_domains=transporter,pxr,general_protein_ligand" in payload["rows"][2]["current_blocker_metrics"]
    assert "general_platform=False" in payload["rows"][2]["current_blocker_metrics"]
    assert "transporter/pxr/ca2/idp_broad/all_atom breadth domains ready" in payload["rows"][2]["acceptance_criteria"]
    assert "build_general_protein_ligand_claim_blocker_packet.py" in payload["rows"][2]["verification_command"]
    assert "build_product_scope_breadth_evidence_acquisition_queue.py" in payload["rows"][2]["verification_command"]
    assert "build_product_scope_breadth_evidence_priority_packet.py" in payload["rows"][2]["verification_command"]
    assert "build_product_scope_breadth_closure_checklist.py" in payload["rows"][2]["verification_command"]
    assert "explicit general platform claim flags" in payload["rows"][2]["risk_if_skipped"]


def test_scope_breadth_work_order_handles_ready_contract() -> None:
    payload = mod.build_product_scope_breadth_work_order(
        scope_contract_packet=_packet({"scope_breadth_ready": True, "ready_domains": ["transporter"], "missing_domains": []})
    )

    assert payload["summary"]["open_item_count"] == 0
    assert payload["summary"]["scope_breadth_ready"] is True


def test_scope_breadth_work_order_cli_writes_outputs(tmp_path: Path) -> None:
    contract = tmp_path / "scope.json"
    contract.write_text(
        json.dumps(
            _packet(
                {"scope_breadth_ready": False, "ready_domains": [], "missing_domains": ["all_atom"]},
                [{"domain": "all_atom", "artifact": "runs/allatom.json", "observed": "missing_inputs=x"}],
            )
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "work.json"
    out_csv = tmp_path / "work.csv"
    out_md = tmp_path / "work.md"

    mod.main(
        [
            "--scope-contract-json",
            str(contract),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["open_item_count"] == 1
    assert "domain" in out_csv.read_text(encoding="utf-8")
    assert "Product Scope Breadth Work Order" in out_md.read_text(encoding="utf-8")
