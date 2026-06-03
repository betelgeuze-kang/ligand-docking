from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.htvs_command import build_htvs_command_from_profile, build_htvs_command_from_profile_json
from tools import build_product_execution_work_order as work_order_tool


def _profile() -> dict:
    return {
        "version": "gpcr_profile_v1",
        "description": "test profile",
        "targets": "ADRB2_GPCR_BLIND",
        "run_scope": "full",
        "dry_run": False,
        "auto_heavy_artifacts_root": False,
        "require_rust_hip": True,
        "trajectory_engine_mode": "rust_hip",
        "ligand_csv": "config/ligands.csv",
        "target_native_csv": "config/targets.csv",
        "native_path_col": "native_pdb_path",
        "ranking_labels_csv": "config/ligands.csv",
        "eval_split_csv": "config/splits.csv",
        "smoke": {"max_ligands": 4, "replicas": 4, "jobs_per_target": 4, "traj_frames": 80},
        "full": {"max_ligands": 100, "replicas": 100, "jobs_per_target": 100, "traj_frames": 120},
        "gate": {
            "enforce_operational_gate": True,
            "strict_fail_fast": True,
            "min_frames": 100,
            "max_mean_min_distance_A": 4.75,
            "ranking_unique_auc_min": 0.85,
        },
        "hard_decoy_targets": "ADRB2_GPCR_BLIND",
    }


def test_htvs_command_from_profile_validates_against_pipeline_parser() -> None:
    payload = build_htvs_command_from_profile(_profile(), out_prefix="runs/product_after_approval")

    assert payload["parser_valid"] is True
    assert payload["unknown_args_after_render"] == []
    assert payload["unsupported_profile_keys"] == []
    assert "--no-dry-run" in payload["parts"]
    assert "--traj-require-rust-hip" in payload["parts"]
    assert "--out-prefix" in payload["parts"]
    assert "hard_decoy_targets" in payload["skipped_profile_keys"]


def test_htvs_command_from_profile_json_records_source(tmp_path: Path) -> None:
    profile_json = tmp_path / "profile.json"
    profile_json.write_text(json.dumps(_profile()) + "\n", encoding="utf-8")

    payload = build_htvs_command_from_profile_json(profile_json, out_prefix="runs/product_after_approval")

    assert payload["profile_json"] == str(profile_json)
    assert payload["parser_valid"] is True
    assert payload["rendered_count"] > 10


def test_work_order_tool_can_generate_command_from_profile_json(tmp_path: Path) -> None:
    profile_json = tmp_path / "profile.json"
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    profile_json.write_text(json.dumps(_profile()) + "\n", encoding="utf-8")
    readiness_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_handoff_ready",
                    "target_id": "ADRB2",
                    "family": "gpcr",
                    "ligand_count": 1,
                    "execution_enabled": False,
                    "docking_results_emitted": False,
                    "external_state_mutated": False,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    work_order_tool.main(
        [
            "--readiness-json",
            str(readiness_json),
            "--profile-json",
            str(profile_json),
            "--profile-out-prefix",
            "runs/product_after_approval",
            "--planned-artifact-path",
            "runs/product_after_approval_summary.json",
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

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_execution_work_order_ready"
    assert payload["summary"]["profile_command_generated"] is True
    assert payload["summary"]["profile_command_unsupported_count"] == 0
    assert payload["commands"]["approval_gate_command"] == "python3 tools/build_product_execution_approval_gate.py"
    assert "--profile" not in payload["commands"]["execution_command"]
    assert "tools/run_ligand_htvs_pipeline.py" in payload["commands"]["execution_command"]
    assert any(row["step"] == "approval_gate" and row["required_before_execution"] is True for row in payload["rows"])
