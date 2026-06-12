from __future__ import annotations

import json
from pathlib import Path

from tools.product.build_product_ledger_privacy_scan import DEFAULT_SCAN_GLOBS, build_product_ledger_privacy_scan


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_product_ledger_privacy_scan_defaults_include_goal_and_commercial_readiness_artifacts() -> None:
    assert "runs/product_commercial_readiness_execution_ladder_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_readiness_rollup_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_operator_action_board_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_operator_intake_kit_current/manifest.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_release_burndown_work_order_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_api_surface_contract_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/goal_bottleneck_briefing_current.json" in DEFAULT_SCAN_GLOBS
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in DEFAULT_SCAN_GLOBS


def test_product_ledger_privacy_scan_passes_hash_only_redactions(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "results" / "product_docking_jobs" / "job.json",
        {
            "job_id": "job",
            "request_sha256": "a" * 64,
            "request": {
                "pdb_content": {"redacted": True, "redaction": "sha256", "sha256": "b" * 64, "byte_length": 88},
                "ligands": [
                    {
                        "ligand_id": "lig_1",
                        "smiles": {
                            "redacted": True,
                            "redaction": "sha256",
                            "sha256": "c" * 64,
                            "byte_length": 3,
                        },
                    }
                ],
            },
        },
    )

    payload = build_product_ledger_privacy_scan(
        root=tmp_path,
        scan_globs=["results/product_docking_jobs/*.json"],
    )

    assert payload["summary"]["status"] == "product_ledger_privacy_scan_ready"
    assert payload["summary"]["ledger_privacy_scan_ready"] is True
    assert payload["summary"]["leak_count"] == 0
    assert payload["blockers"] == []


def test_product_ledger_privacy_scan_blocks_raw_smiles_and_inline_pdb_without_echoing_values(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "results" / "product_docking_jobs" / "job.json",
        {
            "job_id": "job",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
    )

    payload = build_product_ledger_privacy_scan(
        root=tmp_path,
        scan_globs=["results/product_docking_jobs/*.json"],
    )
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["summary"]["status"] == "blocked_product_ledger_privacy_scan"
    assert payload["summary"]["ledger_privacy_scan_ready"] is False
    assert payload["summary"]["leak_count"] == 2
    assert {finding["leak_type"] for finding in payload["findings"]} == {"raw_sensitive_key_value"}
    assert "CCO" not in serialized
    assert "ATOM      1" not in serialized
    assert all(len(finding["value_sha256"]) == 64 for finding in payload["findings"])


def test_product_ledger_privacy_scan_blocks_raw_payload_inside_request_json_string(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "api_docking_e2e_smoke_current" / "job" / "status.json",
        {
            "job_id": "job",
            "request_json": json.dumps({"ligands": [{"smiles": "CCN"}]}),
        },
    )

    payload = build_product_ledger_privacy_scan(
        root=tmp_path,
        scan_globs=["runs/api_docking_e2e_smoke_current/*/status.json"],
    )

    assert payload["summary"]["status"] == "blocked_product_ledger_privacy_scan"
    assert payload["summary"]["leak_count"] == 1
    assert payload["findings"][0]["json_path"].endswith("{json_string}.ligands[0].smiles")
