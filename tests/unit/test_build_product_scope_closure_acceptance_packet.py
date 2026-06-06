from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_scope_closure_acceptance_packet as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def _scope_packet(*, ready: bool = False) -> dict[str, object]:
    matrix = [
        {
            "stage_id": "scope_evidence_acquisition_preflight",
            "status": "ready",
            "artifact": "runs/queue.json",
            "release_effect": "queue ready",
            "required_checks": ["evidence_queue_ready"],
            "unlock_claim_scopes": [],
            "validation_command": "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
            "next_action": "",
        },
        {
            "stage_id": "transporter_claim_acceptance",
            "status": "ready" if ready else "blocked",
            "artifact": "runs/transporter.json",
            "release_effect": "transporter ready",
            "required_checks": ["transporter_p0_closed"],
            "unlock_claim_scopes": ["transporter_domain_promotion"],
            "validation_command": "python3 tools/build_product_scope_breadth_contract.py",
            "next_action": "Acquire exact transporter evidence.",
        },
    ]
    blocked = []
    if not ready:
        blocked = [
            {
                "stage_id": "transporter_claim_acceptance",
                "artifact": "runs/transporter.json",
                "blocked_evidence_row_count": 1,
                "blocked_evidence_rows": [
                    {
                        "evidence_row_id": "AQP1.core_binder_01",
                        "target_id": "AQP1",
                        "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                        "required_missing_fields": "replacement_reference_binding_kcal_mol",
                        "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                        "operator_review_artifact": "runs/transporter_manual_review.csv",
                    }
                ],
            }
        ]
    return {
        "summary": {
            "scope_acceptance_matrix_ready": True,
            "scope_breadth_ready": ready,
            "scope_widened": ready,
            "ready_domain_count": 6 if ready else 3,
            "missing_domain_count": 0 if ready else 3,
            "ready_domains": ["gpcr", "kinase"] if ready else ["ca2"],
            "missing_domains": [] if ready else ["transporter", "pxr", "general_protein_ligand"],
            "scope_acceptance_next_stage_id": "" if ready else "transporter_claim_acceptance",
        },
        "scope_acceptance_matrix": matrix,
        "scope_acceptance_stage_evidence_matrix": matrix,
        "scope_acceptance_current_blocked_stage_evidence_matrix": blocked,
    }


def test_scope_closure_acceptance_packet_surfaces_first_blocked_evidence() -> None:
    payload = mod.build_product_scope_closure_acceptance_packet(
        scope_contract_packet=_scope_packet(),
        evidence_queue_packet=_packet({"scope_breadth_ready": False}),
        transporter_p0_packet=_packet(
            {
                "next_slot_completion_packet_ready": True,
                "next_slot_id": "AQP1.core_binder_01",
                "unresolved_slot_count": 11,
                "exact_request_slot_count": 11,
                "next_slot_source_modality": "functional_quantitative_surrogate",
                "next_slot_source_modality_direct_binding_claim_allowed": False,
            }
        ),
        pxr_review_packet=_packet(
            {
                "pxr_exact_review_intake_ready": True,
                "review_template_row_count": 6,
                "conflict_resolution_required_count": 3,
                "next_review_candidate_name": "acetaminophen",
            }
        ),
        pxr_triage_packet=_packet(
            {
                "triage_ready": True,
                "direct_or_claim_safe_quantitative_ready_count": 0,
            }
        ),
        general_blocker_packet=_packet(
            {
                "general_platform_claim_allowed": False,
                "general_platform_claim_blocked": True,
                "next_required_step": "Keep general wording blocked.",
            }
        ),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_scope_closure_acceptance_packet"
    assert summary["packet_ready"] is True
    assert summary["scope_closure_ready"] is False
    assert summary["scope_acceptance_blocked_stage_ids"] == ["transporter_claim_acceptance"]
    assert summary["scope_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert summary["first_blocked_evidence_row_id"] == "AQP1.core_binder_01"
    assert summary["first_blocked_target_id"] == "AQP1"
    assert summary["first_blocked_required_missing_fields"] == "replacement_reference_binding_kcal_mol"
    assert summary["transporter_unresolved_slot_count"] == 11
    assert summary["pxr_exact_review_row_count"] == 6
    assert summary["pxr_direct_or_claim_safe_quantitative_ready_count"] == 0
    assert summary["general_platform_claim_allowed"] is False
    assert payload["rows"][1]["status"] == "blocked"
    assert payload["rows"][1]["scope_widened"] is False


def test_scope_closure_acceptance_packet_complete_when_scope_contract_ready() -> None:
    payload = mod.build_product_scope_closure_acceptance_packet(
        scope_contract_packet=_scope_packet(ready=True),
        evidence_queue_packet=_packet({}),
        transporter_p0_packet=_packet({}),
        pxr_review_packet=_packet({}),
        pxr_triage_packet=_packet({}),
        general_blocker_packet=_packet({"general_platform_claim_allowed": True}),
    )

    assert payload["summary"]["status"] == "product_scope_closure_acceptance_complete"
    assert payload["summary"]["scope_closure_ready"] is True
    assert payload["summary"]["scope_acceptance_blocked_stage_count"] == 0
    assert all(row["status"] == "ready" for row in payload["rows"])


def test_scope_closure_acceptance_packet_cli_writes_outputs(tmp_path: Path) -> None:
    scope = tmp_path / "scope.json"
    empty = tmp_path / "empty.json"
    out_json = tmp_path / "scope_acceptance.json"
    out_csv = tmp_path / "scope_acceptance.csv"
    out_md = tmp_path / "scope_acceptance.md"
    scope.write_text(json.dumps(_scope_packet()) + "\n", encoding="utf-8")
    empty.write_text(json.dumps(_packet({})) + "\n", encoding="utf-8")

    mod.main(
        [
            "--scope-contract-json",
            str(scope),
            "--evidence-queue-json",
            str(empty),
            "--transporter-p0-json",
            str(empty),
            "--pxr-review-json",
            str(empty),
            "--pxr-triage-json",
            str(empty),
            "--general-blocker-json",
            str(empty),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["summary"]["packet_type"] == "product_scope_closure_acceptance_packet"
    assert data["summary"]["packet_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("stage_id,status,")
    assert "Product Scope Closure Acceptance Packet" in out_md.read_text(encoding="utf-8")
