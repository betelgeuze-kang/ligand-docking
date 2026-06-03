from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.work_order import build_product_execution_work_order
from tools import build_product_execution_work_order as tool


def _readiness(status: str = "product_handoff_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def test_product_execution_work_order_ready_with_command_and_config() -> None:
    payload = build_product_execution_work_order(
        _readiness(),
        run_command="python3 tools/run_ligand_htvs_pipeline.py --profile config/gpcr.json",
        config_paths=["config/gpcr.json"],
        planned_artifact_paths=["runs/example_result.json"],
        bundle_tag="adrb2_gpcr",
    )

    summary = payload["summary"]
    assert summary["status"] == "product_execution_work_order_ready"
    assert summary["execution_enabled"] is False
    assert summary["bundle_assembled"] is False
    assert summary["approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert payload["blockers"] == []
    assert "--config-path config/gpcr.json" in " ".join(payload["commands"]["bundle_command"])
    assert "--artifact-path runs/example_result.json" in " ".join(payload["commands"]["bundle_command"])


def test_product_execution_work_order_blocks_missing_command_and_config() -> None:
    payload = build_product_execution_work_order(_readiness())
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_product_execution_work_order"
    assert "run_command_missing" in codes
    assert "config_paths_missing" in codes
    assert payload["commands"]["execution_command"] == "OPERATOR_FILL_RUN_COMMAND"


def test_product_execution_work_order_blocks_not_ready_readiness() -> None:
    payload = build_product_execution_work_order(
        _readiness(status="blocked_product_handoff"),
        run_command="python3 run.py",
        config_paths=["config/gpcr.json"],
    )

    assert payload["summary"]["status"] == "blocked_product_execution_work_order"
    assert any(blocker["code"] == "product_readiness_not_ready" for blocker in payload["blockers"])


def test_product_execution_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    readiness_json.write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")

    tool.main(
        [
            "--readiness-json",
            str(readiness_json),
            "--run-command",
            "python3 tools/run_ligand_htvs_pipeline.py --profile config/gpcr.json",
            "--config-path",
            "config/gpcr.json",
            "--planned-artifact-path",
            "runs/example_result.json",
            "--bundle-tag",
            "adrb2_gpcr",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_execution_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("step,command,")
    assert "Product Execution Work Order" in out_md.read_text(encoding="utf-8")
