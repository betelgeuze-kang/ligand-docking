from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_product.work_order import EXECUTION_APPROVAL_TOKEN
from tools import build_product_execution_approval_gate as mod


def _preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "approval_token_required": EXECUTION_APPROVAL_TOKEN,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _work_order() -> dict:
    return {
        "summary": {
            "status": "product_execution_work_order_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "bundle_tag": "product_gpcr_adrb2",
            "approval_token_required": EXECUTION_APPROVAL_TOKEN,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        },
        "commands": {
            "execution_command": "python3 tools/run_ligand_htvs_pipeline.py --no-dry-run",
            "bundle_command": ["python3", "tools/build_local_delivery_bundle.py"],
            "bundle_validation_command": "python3 tools/validate_local_delivery_bundle.py --bundle-dir runs/local_delivery/bundle_product_gpcr_adrb2",
        },
    }


def _approval_row(*, token: str = EXECUTION_APPROVAL_TOKEN, decision: str = "approve", target_id: str = "ADRB2") -> dict[str, str]:
    return {
        "target_id": target_id,
        "family": "gpcr",
        "bundle_tag": "product_gpcr_adrb2",
        "operator_decision": decision,
        "operator_approval_token": token,
    }


def test_product_execution_approval_gate_blocks_missing_operator_csv() -> None:
    payload = mod.build_product_execution_approval_gate(
        product_execution_preflight_packet=_preflight(),
        product_execution_work_order_packet=_work_order(),
        operator_approval_rows=[],
        operator_approval_csv_present=False,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_execution_operator_approval_gate"
    assert summary["operator_approval_csv_present"] is False
    assert summary["authorized_for_execution"] is False
    assert summary["awaiting_operator_approval_row_count"] == 1
    assert summary["authorized_row_count"] == 0
    assert "operator_approval_csv_missing" in summary["blockers"]
    assert "operator_decision_missing" in summary["blockers"]
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False


def test_product_execution_approval_gate_authorizes_exact_token() -> None:
    payload = mod.build_product_execution_approval_gate(
        product_execution_preflight_packet=_preflight(),
        product_execution_work_order_packet=_work_order(),
        operator_approval_rows=[_approval_row()],
        operator_approval_csv_present=True,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_execution_operator_approval_gate_ready"
    assert summary["authorized_for_execution"] is True
    assert summary["authorized_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert summary["execution_enabled"] is False
    row = payload["rows"][0]
    assert row["approval_gate_status"] == "authorized_for_operator_execution"
    assert row["operator_approval_token_present"] is True


def test_product_execution_approval_gate_blocks_token_mismatch_and_unknown_row() -> None:
    payload = mod.build_product_execution_approval_gate(
        product_execution_preflight_packet=_preflight(),
        product_execution_work_order_packet=_work_order(),
        operator_approval_rows=[_approval_row(token="WRONG"), _approval_row(target_id="OTHER")],
        operator_approval_csv_present=True,
    )

    assert payload["summary"]["status"] == "blocked_product_execution_operator_approval_gate"
    assert "operator_approval_token_mismatch" in payload["summary"]["blockers"]
    assert "operator_approval_row_not_in_product_target" in payload["summary"]["blockers"]
    assert payload["summary"]["unknown_operator_approval_row_count"] == 1
    assert payload["rows"][0]["approval_gate_status"] == "blocked_before_execution"


def test_product_execution_approval_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    preflight_json = tmp_path / "preflight.json"
    work_order_json = tmp_path / "work_order.json"
    approval_csv = tmp_path / "approval.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    preflight_json.write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")
    work_order_json.write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")
    with approval_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["target_id", "family", "bundle_tag", "operator_decision", "operator_approval_token"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(_approval_row())

    mod.main(
        [
            "--product-execution-preflight-json",
            str(preflight_json),
            "--product-execution-work-order-json",
            str(work_order_json),
            "--operator-approval-csv",
            str(approval_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_execution_operator_approval_gate_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("target_id,family,bundle_tag,")
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,family,bundle_tag,")
    assert "Product Execution Operator Approval Gate" in out_md.read_text(encoding="utf-8")
