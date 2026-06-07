from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.execution_preflight import build_product_execution_preflight
from tools import build_product_execution_preflight as tool


def _write_config(root: Path, name: str = "config/gpcr.json") -> str:
    config_path = root / name
    ligand_csv = root / "config/ligands.csv"
    target_csv = root / "config/targets.csv"
    split_csv = root / "config/splits.csv"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    ligand_csv.write_text("target,ligand_id,smiles,is_binder\nADRB2_GPCR_BLIND,L1,CCO,1\nADRB2_GPCR_BLIND,L2,CCCC,0\n", encoding="utf-8")
    split_csv.write_text("target,ligand_id,role\nADRB2_GPCR_BLIND,L1,eval\nADRB2_GPCR_BLIND,L2,eval\n", encoding="utf-8")
    target_csv.write_text("target,native_pdb_path\nADRB2,structures/adrb2.pdb\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "version": "gpcr_test",
                "targets": "ADRB2_GPCR_BLIND",
                "ligand_csv": "config/ligands.csv",
                "target_native_csv": "config/targets.csv",
                "ranking_labels_csv": "config/ligands.csv",
                "eval_split_csv": "config/splits.csv",
                "dry_run": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return name


def _work_order(command: str, config_path: str) -> dict:
    return {
        "summary": {
            "status": "product_execution_work_order_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
        },
        "commands": {
            "approval_gate_command": "python3 tools/build_product_execution_approval_gate.py",
            "execution_command": command,
            "bundle_command": [
                "python3",
                "tools/build_local_delivery_bundle.py",
                "--config-path",
                config_path,
                "--artifact-path",
                "runs/product_result_after_approval.json",
            ],
        },
    }


def test_product_execution_preflight_ready_for_parser_valid_command(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    payload = build_product_execution_preflight(
        _work_order(
            "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke --targets ADRB2_GPCR_BLIND --no-dry-run "
            "--eval-split-csv config/splits.csv --ranking-labels-csv config/ligands.csv --ranking-eval-roles eval "
            "--gate-min-eval-unique-keys 2 --gate-ef1-min 1.0",
            config_path,
        ),
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_execution_preflight_ready"
    assert summary["execution_enabled"] is False
    assert summary["validated_without_execution"] is True
    assert payload["blockers"] == []
    assert summary["approval_gate_command_present"] is True
    assert payload["rows"][0]["check"] == "approval_gate_command"
    assert payload["rows"][0]["status"] == "pass"
    assert summary["operational_gate_feasibility_status"] == "pass"
    assert payload["warnings"][0]["code"] == "config_requests_non_dry_run"


def test_product_execution_preflight_blocks_impossible_operational_gate(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    payload = build_product_execution_preflight(
        _work_order(
            "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke --targets ADRB2_GPCR_BLIND --no-dry-run "
            "--eval-split-csv config/splits.csv --ranking-labels-csv config/ligands.csv --ranking-eval-roles eval "
            "--gate-min-eval-unique-keys 200 --gate-ef1-min 3.0",
            config_path,
        ),
        root=tmp_path,
    )
    codes = {blocker["code"] for blocker in payload["blockers"]}
    gate_check = payload["operational_gate_feasibility_checks"][0]

    assert payload["summary"]["status"] == "blocked_product_execution_preflight"
    assert "operational_gate_eval_unique_keys_impossible" in codes
    assert "operational_gate_ef1_threshold_impossible" in codes
    assert gate_check["eval_unique_keys"] == 2
    assert gate_check["eval_positive_keys"] == 1
    assert gate_check["ef1_max_possible"] == 2.0


def test_product_execution_preflight_blocks_unknown_profile_arg(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    payload = build_product_execution_preflight(
        _work_order(f"python3 tools/run_ligand_htvs_pipeline.py --profile {config_path}", config_path),
        root=tmp_path,
    )
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_product_execution_preflight"
    assert "execution_command_unknown_args" in codes
    assert "--profile" in payload["execution_command_check"]["unknown_args"]


def test_product_execution_preflight_blocks_missing_approval_gate_command(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    work_order = _work_order(
        "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke --targets ADRB2_GPCR_BLIND",
        config_path,
    )
    work_order["commands"].pop("approval_gate_command")

    payload = build_product_execution_preflight(work_order, root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_execution_preflight"
    assert any(blocker["code"] == "approval_gate_command_missing" for blocker in payload["blockers"])
    assert next(row for row in payload["rows"] if row["check"] == "approval_gate_command")["status"] == "fail"


def test_product_execution_preflight_blocks_missing_config_input(tmp_path: Path) -> None:
    config_path = tmp_path / "config/gpcr.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"version": "gpcr_test", "ligand_csv": "config/missing.csv", "target_native_csv": "config/targets.csv"})
        + "\n",
        encoding="utf-8",
    )

    payload = build_product_execution_preflight(
        _work_order(
            "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke --targets ADRB2_GPCR_BLIND",
            "config/gpcr.json",
        ),
        root=tmp_path,
    )

    assert any(blocker["code"] == "config_required_input_missing" for blocker in payload["blockers"])


def test_product_execution_preflight_tool_writes_outputs(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"
    work_order_json.write_text(
        json.dumps(
            _work_order(
                "python3 tools/run_ligand_htvs_pipeline.py --run-scope smoke --targets ADRB2_GPCR_BLIND "
                "--eval-split-csv config/splits.csv --ranking-labels-csv config/ligands.csv --ranking-eval-roles eval "
                "--gate-min-eval-unique-keys 2 --gate-ef1-min 1.0",
                config_path,
            )
        )
        + "\n",
        encoding="utf-8",
    )

    tool.main(
        [
            "--work-order-json",
            str(work_order_json),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_execution_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Execution Preflight" in out_md.read_text(encoding="utf-8")
