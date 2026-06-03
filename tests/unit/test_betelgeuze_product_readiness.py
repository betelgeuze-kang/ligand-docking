from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.readiness import build_product_readiness_gate
from tools import build_product_readiness_gate as tool


def _request() -> dict:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_id": "2RH1",
        "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
    }


def _verdict() -> dict:
    return {
        "summary": {
            "delivery_ready": True,
            "verdict": "delivery_ready",
            "p0_blocker_count": 0,
            "hard_blocker_count": 0,
            "source_artifacts_all_fingerprinted": True,
        }
    }


def test_product_readiness_gate_allows_scoped_request_with_green_verdict_but_keeps_execution_disabled() -> None:
    payload = build_product_readiness_gate(_request(), _verdict())
    summary = payload["summary"]

    assert summary["status"] == "product_handoff_ready"
    assert summary["request_contract_status"] == "pass"
    assert summary["local_delivery_delivery_ready"] is True
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False
    assert summary["execution_approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert payload["blockers"] == []


def test_product_readiness_gate_blocks_bad_request_and_red_verdict() -> None:
    request = _request()
    request["family"] = "transporter"
    verdict = _verdict()
    verdict["summary"]["delivery_ready"] = False
    verdict["summary"]["verdict"] = "blocked"
    verdict["summary"]["p0_blocker_count"] = 1

    payload = build_product_readiness_gate(request, verdict)
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_product_handoff"
    assert "scope_family_not_delivery_ready" in codes
    assert "request_contract_not_pass" in codes
    assert "local_delivery_verdict_not_ready" in codes
    assert "local_delivery_blockers_present" in codes


def test_product_readiness_gate_blocks_missing_verdict_fingerprints() -> None:
    verdict = _verdict()
    verdict["summary"]["source_artifacts_all_fingerprinted"] = False

    payload = build_product_readiness_gate(_request(), verdict)

    assert payload["summary"]["status"] == "blocked_product_handoff"
    assert any(blocker["code"] == "local_delivery_fingerprints_missing" for blocker in payload["blockers"])


def test_product_readiness_gate_tool_writes_outputs(tmp_path: Path) -> None:
    request_json = tmp_path / "request.json"
    verdict_json = tmp_path / "verdict.json"
    out_json = tmp_path / "readiness.json"
    out_md = tmp_path / "readiness.md"
    request_json.write_text(json.dumps(_request()) + "\n", encoding="utf-8")
    verdict_json.write_text(json.dumps(_verdict()) + "\n", encoding="utf-8")

    tool.main(["--request-json", str(request_json), "--verdict-json", str(verdict_json), "--out-json", str(out_json), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_handoff_ready"
    assert "Product Readiness Gate" in out_md.read_text(encoding="utf-8")
