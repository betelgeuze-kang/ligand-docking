from __future__ import annotations

from tools import build_wetlab_mapping_fix_retry_lane as mod


def test_build_wetlab_mapping_fix_retry_lane_prefers_plain_preflight_for_mapping_retry() -> None:
    retry_preset = {
        "summary": {"status": "wetlab_primary_retry_preset_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "SARS-CoV-2 Mpro",
                "recommended_retry_mode": "mapping_fix_required",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "representative_stage1_mapping_failure_shard_id": "01_of_20",
                "representative_stage6_failure_shard_id": "06_of_20",
            }
        ],
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {
                "target_id": "SARS-CoV-2 Mpro",
                "shard_id": "01_of_20",
                "queue_status": "explicit_hold",
            }
        ],
    }
    compound_universe = {
        "summary": {"status": "wetlab_broad_screen_compound_universe_ready"},
        "rows": [
            {
                "compound_index": 1,
                "canonical_smiles": "CCO",
                "compound_name": "cmp1",
                "approval_class": "approved",
                "procurement_tier": "cheap",
                "source_dataset": "x",
                "source_anchor": "a",
                "source_url": "u",
            }
        ],
    }
    portfolio = {
        "rows": [
            {"target_id": "SARS-CoV-2 Mpro", "domain_family": "viral_protease"},
        ]
    }

    payload = mod.build_payload(
        retry_preset_payload=retry_preset,
        execution_queue_payload=execution_queue,
        compound_universe_payload=compound_universe,
        portfolio_payload=portfolio,
        target_native_csv="config/real_drug_targets_native_v1.csv",
        target_id="SARS-CoV-2 Mpro",
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_mapping_fix_retry_lane_ready"
    assert summary["target_id"] == "SARS-CoV-2 Mpro"
    assert summary["shard_id"] == "01_of_20"
    assert summary["recommended_retry_mode"] == "mapping_fix_required"
    assert summary["selected_command_kind"] == "throughput_preflight"
    assert summary["ready_for_mapping_fix_retry"] is True
    runner_row = next(row for row in payload["rows"] if row["row_kind"] == "runner_command")
    assert "run_wetlab_mapping_fix_retry.py" in runner_row["command"]


def test_build_wetlab_mapping_fix_retry_lane_uses_target_specific_lane_artifact_path() -> None:
    retry_preset = {
        "summary": {"status": "wetlab_primary_retry_preset_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "recommended_retry_mode": "mapping_fix_required",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "representative_stage1_mapping_failure_shard_id": "07_of_20",
                "representative_stage6_failure_shard_id": "08_of_20",
            }
        ],
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [{"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "queue_status": "explicit_hold"}],
    }
    compound_universe = {
        "summary": {"status": "wetlab_broad_screen_compound_universe_ready"},
        "rows": [
            {
                "compound_index": 1,
                "canonical_smiles": "CCO",
                "compound_name": "cmp1",
                "approval_class": "approved",
                "procurement_tier": "cheap",
                "source_dataset": "x",
                "source_anchor": "a",
                "source_url": "u",
            }
        ],
    }
    portfolio = {"rows": [{"target_id": "T. cruzi PDE", "domain_family": "parasite_enzyme"}]}

    payload = mod.build_payload(
        retry_preset_payload=retry_preset,
        execution_queue_payload=execution_queue,
        compound_universe_payload=compound_universe,
        portfolio_payload=portfolio,
        target_native_csv="config/real_drug_targets_native_v1.csv",
        target_id="T. cruzi PDE",
        lane_artifact_md="runs/tcruzi_pde_mapping_fix_retry_lane_current.md",
    )

    runner_row = next(row for row in payload["rows"] if row["row_kind"] == "runner_command")
    assert "runs/tcruzi_pde_mapping_fix_retry_lane_current.md" in runner_row["command"]
    assert payload["structured"]["lane_artifact"].endswith("runs/tcruzi_pde_mapping_fix_retry_lane_current.md")
