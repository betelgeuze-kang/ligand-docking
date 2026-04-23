from __future__ import annotations

from tools import build_wetlab_mapping_fix_retry_support as mod


def test_build_wetlab_mapping_fix_retry_support_summarizes_mpro_and_tcruzi() -> None:
    retry_preset = {
        "summary": {"status": "wetlab_primary_retry_preset_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "SARS-CoV-2 Mpro",
                "recommended_retry_mode": "mapping_fix_required",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "representative_stage1_mapping_failure_shard_id": "01_of_20",
                "representative_stage6_failure_shard_id": "02_of_20",
            },
            {
                "target_id": "T. cruzi PDE",
                "recommended_retry_mode": "mapping_fix_required",
                "stage1_mapping_failed_count": 1,
                "stage6_distance_gate_failed_count": 19,
                "representative_stage1_mapping_failure_shard_id": "07_of_20",
                "representative_stage6_failure_shard_id": "08_of_20",
            },
        ],
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {"target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "explicit_hold"},
            {"target_id": "T. cruzi PDE", "shard_id": "07_of_20", "queue_status": "explicit_hold"},
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
            {"target_id": "T. cruzi PDE", "domain_family": "parasite_enzyme"},
        ]
    }

    payload, lane_outputs = mod.build_payload(
        retry_preset_payload=retry_preset,
        execution_queue_payload=execution_queue,
        compound_universe_payload=compound_universe,
        portfolio_payload=portfolio,
        target_native_csv="config/real_drug_targets_native_v1.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_mapping_fix_retry_support_ready"
    assert summary["target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert "SARS-CoV-2 Mpro" in summary["ready_targets"]
    assert "T. cruzi PDE" in summary["ready_targets"]
    assert len(lane_outputs) == 2
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["SARS-CoV-2 Mpro"]["selected_command_kind"] == "throughput_preflight"
    assert "run_wetlab_mapping_fix_retry.py" in rows["T. cruzi PDE"]["runner_command"]


def test_build_wetlab_mapping_fix_retry_support_omits_targets_when_stage6_tuning_is_ready() -> None:
    payload, lane_outputs = mod.build_payload(
        retry_preset_payload={"summary": {"status": "wetlab_primary_retry_preset_surface_ready", "guard_limit": 3}, "rows": []},
        execution_queue_payload={"summary": {"status": "wetlab_broad_screen_execution_queue_ready"}, "rows": []},
        compound_universe_payload={"summary": {"status": "wetlab_broad_screen_compound_universe_ready"}, "rows": []},
        portfolio_payload={"rows": []},
        target_native_csv="config/real_drug_targets_native_v1.csv",
        sarscov2_mpro_stage6_tuning_surface={"summary": {"status": "wetlab_sarscov2_mpro_stage6_tuning_surface_ready", "target_id": "SARS-CoV-2 Mpro"}},
        tcruzi_pde_stage6_tuning_surface={"summary": {"status": "wetlab_tcruzi_pde_stage6_tuning_surface_ready", "target_id": "T. cruzi PDE"}},
    )

    summary = payload["summary"]
    assert summary["ready_target_count"] == 0
    assert summary["mapping_fix_candidate_count"] == 0
    assert payload["rows"] == []
    assert lane_outputs == []
