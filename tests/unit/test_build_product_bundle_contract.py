from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_bundle_contract as mod


def _preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
        }
    }


def _work_order(tmp_path: Path) -> dict:
    config = tmp_path / "config" / "profile.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"ligand_csv":"ligands.csv","target_native_csv":"targets.csv"}\n', encoding="utf-8")
    return {
        "summary": {
            "status": "product_execution_work_order_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "bundle_tag": "product_gpcr_adrb2",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
        },
        "commands": {
            "bundle_command": [
                "python3",
                "tools/build_local_delivery_bundle.py",
                "--bundle-tag",
                "product_gpcr_adrb2",
                "--out-dir",
                "runs/local_delivery",
                "--request-summary",
                "ADRB2 gpcr ligand docking request; ligands=1",
                "--delivery-scope",
                "restricted local delivery: gpcr",
                "--claim-scope",
                "gpcr",
                "--verdict",
                "Internal-review execution work order only; not a completed delivery bundle.",
                "--rerun-command",
                "python3 tools/run_ligand_htvs_pipeline.py --dry-run",
                "--config-path",
                str(config),
                "--artifact-path",
                "runs/product_gpcr_adrb2_after_approval_summary.json",
            ],
            "bundle_validation_command": "python3 tools/validate_local_delivery_bundle.py --bundle-dir runs/local_delivery/bundle_product_gpcr_adrb2",
        },
    }


def test_build_product_bundle_contract_tool_writes_outputs(tmp_path: Path) -> None:
    work_order_json = tmp_path / "work_order.json"
    preflight_json = tmp_path / "preflight.json"
    out_json = tmp_path / "bundle_contract.json"
    out_csv = tmp_path / "bundle_contract.csv"
    out_md = tmp_path / "bundle_contract.md"
    work_order_json.write_text(json.dumps(_work_order(tmp_path)) + "\n", encoding="utf-8")
    preflight_json.write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--work-order-json",
            str(work_order_json),
            "--preflight-json",
            str(preflight_json),
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_bundle_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Bundle Contract" in out_md.read_text(encoding="utf-8")
