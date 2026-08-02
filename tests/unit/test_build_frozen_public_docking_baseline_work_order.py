"""Frozen public docking offline-baseline work-order tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "product" / "build_frozen_public_docking_baseline_work_order.py"
)


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location(
        "build_frozen_public_docking_baseline_work_order_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    case_hash = "a" * 64
    execution = {
        "summary": {
            "suite_complete": True,
            "execution_ready": True,
            "case_set_hash": case_hash,
            "frozen_case_count": 2,
            "candidate_budget": 5,
        },
        "cases": [
            {
                "case_id": "case_1",
                "target_id": "pdb:1AAA",
                "ligand_id": "ccd:LIG",
                "preparation": {
                    "ready": True,
                    "prepared_input_hash": "b" * 64,
                    "blockers": [],
                    "receptor": {"input_hash": "c" * 64},
                    "ligand": {"input_hash": "d" * 64},
                },
            },
            {
                "case_id": "case_2",
                "target_id": "pdb:2BBB",
                "ligand_id": "ccd:XYZ",
                "preparation": {
                    "ready": False,
                    "prepared_input_hash": "e" * 64,
                    "blockers": ["unassigned_ligand_stereochemistry"],
                    "receptor": {"input_hash": "f" * 64},
                    "ligand": {"input_hash": "0" * 64},
                },
            },
        ],
    }
    collection = {
        "summary": {
            "case_set_hash": case_hash,
            "frozen_at_utc": "2026-07-27T00:00:00Z",
        },
        "cases": [
            {
                "case_id": "case_1",
                "evidence": {
                    "receptor_entry_id": "1AAA",
                    "receptor_pdb_sha256": "1" * 64,
                    "ligand_comp_id": "LIG",
                    "ligand_smiles": "CCO",
                },
            },
            {
                "case_id": "case_2",
                "evidence": {
                    "receptor_entry_id": "2BBB",
                    "receptor_pdb_sha256": "2" * 64,
                    "ligand_source_entry_id": "3CCC",
                    "ligand_source_receptor_pdb_sha256": "3" * 64,
                    "ligand_comp_id": "XYZ",
                    "ligand_smiles": "CCCC",
                },
            },
        ],
    }
    execution_path = tmp_path / "execution.json"
    collection_path = tmp_path / "collection.json"
    execution_path.write_text(json.dumps(execution), encoding="utf-8")
    collection_path.write_text(json.dumps(collection), encoding="utf-8")
    return execution_path, collection_path


def test_work_order_covers_every_case_and_stays_fail_closed(builder, tmp_path):
    execution, collection = _write_inputs(tmp_path)
    packet = builder.build_baseline_work_order(
        execution_json=execution,
        collection_receipt_json=collection,
        available_binaries=[],
    )
    summary = packet["summary"]
    assert summary["ready"] is False
    assert summary["case_count"] == 2
    assert summary["candidate_budget"] == 5
    assert summary["internal_preparation_ready_case_count"] == 1
    assert summary["internal_preparation_blocked_case_count"] == 1
    assert "external_oracle_binary_unavailable_offline" in summary["blockers"]
    assert "external_oracle_preparation_policy_artifact_missing" in summary["blockers"]
    assert "external_oracle_result_rows_missing:2" in summary["blockers"]
    assert "paired_baseline_delta_missing" in summary["blockers"]
    assert summary["installs_binaries"] is False
    assert summary["baseline_executed"] is False
    assert len(packet["rows"]) == 2
    assert packet["rows"][0]["prepared_input_hash"] == "b" * 64
    assert packet["rows"][1]["internal_preparation_ready"] is False
    assert packet["rows"][1]["internal_preparation_blockers"] == (
        "unassigned_ligand_stereochemistry"
    )
    assert packet["rows"][0]["baseline_engine"] == "OPERATOR_FILL_BASELINE_ENGINE"


def test_policy_and_binary_remove_only_their_own_blockers(builder, tmp_path):
    execution, collection = _write_inputs(tmp_path)
    policy = tmp_path / "policy.json"
    policy.write_text('{"policy":"deterministic"}', encoding="utf-8")
    packet = builder.build_baseline_work_order(
        execution_json=execution,
        collection_receipt_json=collection,
        preparation_policy_artifact=policy,
        available_binaries=["vina"],
    )
    summary = packet["summary"]
    assert "external_oracle_binary_unavailable_offline" not in summary["blockers"]
    assert "external_oracle_preparation_policy_artifact_missing" not in summary["blockers"]
    assert summary["available_external_oracle_binaries"] == ["vina"]
    assert len(summary["preparation_policy_sha256"]) == 64
    assert "external_oracle_result_rows_missing:2" in summary["blockers"]
    assert "paired_baseline_delta_missing" in summary["blockers"]
