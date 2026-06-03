from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.bundle_contract import build_product_bundle_contract


def _work_order(tmp_path: Path, *, verdict: str = "Internal-review execution work order only; not a completed delivery bundle.", validation_dir: str = "runs/local_delivery/bundle_product_gpcr_adrb2") -> dict:
    config = tmp_path / "config" / "profile.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"ligand_csv":"ligands.csv","target_native_csv":"targets.csv"}\n', encoding="utf-8")
    bundle_command = [
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
        verdict,
        "--rerun-command",
        "python3 tools/run_ligand_htvs_pipeline.py --dry-run",
        "--config-path",
        str(config),
        "--artifact-path",
        "runs/product_gpcr_adrb2_after_approval_summary.json",
    ]
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
            "bundle_command": bundle_command,
            "bundle_validation_command": f"python3 tools/validate_local_delivery_bundle.py --bundle-dir {validation_dir}",
        },
    }


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


def test_product_bundle_contract_ready_without_assembly(tmp_path: Path) -> None:
    payload = build_product_bundle_contract(_work_order(tmp_path), _preflight(), root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "product_bundle_contract_ready"
    assert summary["bundle_parser_status"] == "parsed"
    assert summary["bundle_validation_command_matches"] is True
    assert summary["execution_enabled"] is False
    assert summary["bundle_assembled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_product_bundle_contract_ready_with_existing_validated_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_product_gpcr_adrb2"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "validation.json").write_text(
        json.dumps({"overall_ok": True, "blocker_count": 0, "warning_count": 0}) + "\n",
        encoding="utf-8",
    )

    payload = build_product_bundle_contract(_work_order(tmp_path), _preflight(), root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "product_bundle_contract_ready"
    assert summary["bundle_assembled"] is True
    assert summary["bundle_validation_present"] is True
    assert summary["bundle_validation_passed"] is True
    assert payload["blockers"] == []


def test_product_bundle_contract_blocks_existing_unvalidated_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_product_gpcr_adrb2"
    bundle_dir.mkdir(parents=True)

    payload = build_product_bundle_contract(_work_order(tmp_path), _preflight(), root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_bundle_contract"
    assert any(blocker["code"] == "bundle_dir_already_present" for blocker in payload["blockers"])


def test_product_bundle_contract_blocks_delivery_ready_claim_before_execution(tmp_path: Path) -> None:
    payload = build_product_bundle_contract(
        _work_order(tmp_path, verdict="Delivery-ready only for the attached restricted local-delivery scope."),
        _preflight(),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_product_bundle_contract"
    assert any(blocker["code"] == "bundle_verdict_claims_delivery_ready_before_execution" for blocker in payload["blockers"])


def test_product_bundle_contract_blocks_validation_dir_mismatch(tmp_path: Path) -> None:
    payload = build_product_bundle_contract(
        _work_order(tmp_path, validation_dir="runs/local_delivery/bundle_wrong"),
        _preflight(),
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_product_bundle_contract"
    assert any(blocker["code"] == "bundle_validation_dir_mismatch" for blocker in payload["blockers"])
