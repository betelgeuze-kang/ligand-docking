from __future__ import annotations

from pathlib import Path

from tools import build_wetlab_broad_screen_throughput_bridge as mod


def test_build_wetlab_broad_screen_throughput_bridge_emits_manifest_and_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "CA IX",
            "first_actionable_shard_id": "08_of_20",
        },
        "rows": [
            {
                "target_id": "CA IX",
                "shard_id": "08_of_20",
                "queue_status": "running",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "Acetazolamide", "canonical_smiles": "CC1", "approval_class": "approved", "procurement_tier": "cheap", "source_dataset": "seed", "source_anchor": "paper", "source_url": "https://example.com/1", "molecular_weight": 222.0, "logp": 1.1},
            {"compound_index": 2, "compound_name": "Methazolamide", "canonical_smiles": "CC2", "approval_class": "approved", "procurement_tier": "cheap", "source_dataset": "seed", "source_anchor": "paper", "source_url": "https://example.com/2", "molecular_weight": 236.0, "logp": 1.0},
            {"compound_index": 3, "compound_name": "Other", "canonical_smiles": "CC3"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "CA IX", "domain_family": "condition_aware_enzyme"},
        ]
    }

    payload = mod.build_payload(execution_queue, compound_universe, portfolio, target_native_csv="config/missing.csv")
    summary = payload["summary"]

    assert summary["status"] == "wetlab_broad_screen_throughput_bridge_ready"
    assert summary["target_id"] == "CA IX"
    assert summary["shard_id"] == "08_of_20"
    assert summary["traj_prod_stage2_preset"] == "default"
    assert summary["manifest_row_count"] == 2
    assert summary["smiles_ready_row_count"] == 2
    assert summary["throughput_preflight_ready"] is True
    assert summary["throughput_execute_ready"] is True

    manifest_csv = Path(payload["structured"]["ligand_manifest_csv"])
    target_csv = Path(payload["structured"]["target_native_stub_csv"])
    assert manifest_csv.exists()
    assert target_csv.exists()

    commands = {row["command_kind"]: row["command"] for row in payload["rows"]}
    assert "tools/run_ligand_htvs_pipeline.py" in commands["throughput_preflight"]
    assert "--traj-prod-speedpack" in commands["throughput_preflight"]
    assert "--traj-prod-stage2-preset default" in commands["throughput_preflight"]
    assert "--dry-run" in commands["throughput_preflight"]
    assert "--no-dry-run" in commands["throughput_execute"]


def test_build_wetlab_broad_screen_throughput_bridge_enables_plpro_gate55_for_manual_retry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "SARS-CoV-2 PLpro",
            "first_actionable_shard_id": "16_of_20",
        },
        "rows": [
            {
                "target_id": "SARS-CoV-2 PLpro",
                "shard_id": "16_of_20",
                "queue_status": "explicit_hold",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1", "approval_class": "approved", "procurement_tier": "cheap", "source_dataset": "seed", "source_anchor": "paper", "source_url": "https://example.com/1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2", "approval_class": "approved", "procurement_tier": "cheap", "source_dataset": "seed", "source_anchor": "paper", "source_url": "https://example.com/2"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "SARS-CoV-2 PLpro", "domain_family": "viral_protease"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="SARS-CoV-2 PLpro",
        shard_id="16_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["target_id"] == "SARS-CoV-2 PLpro"
    assert summary["shard_id"] == "16_of_20"
    assert summary["gate_relax_profile_id"] == "plpro_manual_retry_gate55"
    assert summary["gate_relax_profile_ready"] is True
    assert summary["preferred_command_kind"] == "throughput_preflight_tuned_gate55"
    assert rows["throughput_preflight_tuned_gate55"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate55"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 5.5" in rows["throughput_preflight_tuned_gate55"]["command"]


def test_build_wetlab_broad_screen_throughput_bridge_enables_lrrk2_gate55_for_panel_first_retry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "LRRK2",
            "first_actionable_shard_id": "02_of_20",
        },
        "rows": [
            {
                "target_id": "LRRK2",
                "shard_id": "02_of_20",
                "queue_status": "ready_after_previous_shard",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1", "approval_class": "approved", "procurement_tier": "cheap"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2", "approval_class": "approved", "procurement_tier": "cheap"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "LRRK2", "domain_family": "kinase"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="LRRK2",
        shard_id="02_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["target_id"] == "LRRK2"
    assert summary["shard_id"] == "02_of_20"
    assert summary["gate_relax_profile_id"] == "lrrk2_panel_first_gate55"
    assert summary["gate_relax_profile_ready"] is True
    assert summary["preferred_command_kind"] == "throughput_preflight_tuned_gate55"
    assert rows["throughput_preflight_tuned_gate55"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate55"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 5.5" in rows["throughput_preflight_tuned_gate55"]["command"]
    assert "--strict-gate-max-mean-min-distance-A 5.5" in rows["throughput_preflight_tuned_gate55"]["command"]


def test_build_wetlab_broad_screen_throughput_bridge_emits_stk17b_gate45_exploratory_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "STK17B (DRAK2)",
            "first_actionable_shard_id": "17_of_20",
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "17_of_20",
                "queue_status": "ready_after_previous_shard",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "STK17B (DRAK2)", "domain_family": "kinase"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="STK17B (DRAK2)",
        shard_id="17_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["exploratory_gate_relax_profile_id"] == "stk17b_exploratory_gate45"
    assert summary["exploratory_gate_relax_profile_ready"] is True
    assert rows["throughput_preflight_tuned_gate45"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate45"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 4.5" in rows["throughput_preflight_tuned_gate45"]["command"]


def test_build_wetlab_broad_screen_throughput_bridge_prefers_gate45_for_stk17b_followup_lane(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "maybe_load_json",
        lambda path: {
            "summary": {
                "status": "wetlab_stk17b_exploratory_followup_lane_blocked",
                "target_id": "STK17B (DRAK2)",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
            }
        },
    )

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "STK17B (DRAK2)",
            "first_actionable_shard_id": "18_of_20",
        },
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "18_of_20",
                "queue_status": "explicit_hold",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "STK17B (DRAK2)", "domain_family": "kinase"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="STK17B (DRAK2)",
        shard_id="18_of_20",
    )
    summary = payload["summary"]
    structured = payload["structured"]

    assert summary["preferred_command_kind"] == "throughput_preflight_tuned_gate45"
    assert structured["preferred_out_prefix"].endswith("throughput_run_gate45")
    assert structured["preferred_summary_json"].endswith("throughput_run_gate45_summary.json")
    assert structured["preferred_pid_path"].endswith("throughput_preflight_tuned_gate45.pid")


def test_build_wetlab_broad_screen_throughput_bridge_emits_dengue_gate45_exploratory_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "Dengue NS2B-NS3 protease",
            "first_actionable_shard_id": "05_of_20",
        },
        "rows": [
            {
                "target_id": "Dengue NS2B-NS3 protease",
                "shard_id": "05_of_20",
                "queue_status": "ready_after_previous_shard",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "Dengue NS2B-NS3 protease", "domain_family": "viral_protease"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="Dengue NS2B-NS3 protease",
        shard_id="05_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["exploratory_gate_relax_profile_id"] == "dengue_ns2b_ns3_stage6_gate45"
    assert summary["exploratory_gate_relax_profile_ready"] is True
    assert rows["throughput_preflight_tuned_gate45"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate45"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 4.5" in rows["throughput_preflight_tuned_gate45"]["command"]


def test_build_wetlab_broad_screen_throughput_bridge_emits_dpre1_gate51_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    execution_queue = {
        "summary": {
            "first_actionable_target_id": "DprE1",
            "first_actionable_shard_id": "04_of_20",
        },
        "rows": [
            {
                "target_id": "DprE1",
                "shard_id": "04_of_20",
                "queue_status": "ready_after_previous_shard",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2"},
        ]
    }
    portfolio = {
        "rows": [
            {"target_id": "DprE1", "domain_family": "enzyme"},
        ]
    }

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv="config/missing.csv",
        target_id="DprE1",
        shard_id="04_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["observed_band_gate_relax_profile_id"] == "dpre1_stage6_gate51"
    assert summary["observed_band_gate_relax_profile_ready"] is True
    assert rows["throughput_preflight_tuned_gate51"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate51"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 5.1" in rows["throughput_preflight_tuned_gate51"]["command"]
    assert "--strict-gate-max-mean-min-distance-A 5.1" in rows["throughput_preflight_tuned_gate51"]["command"]


def test_build_wetlab_broad_screen_throughput_bridge_emits_tcruzi_krs1_gate51_commands(tmp_path: Path, monkeypatch) -> None:
    native_csv = tmp_path / "native.csv"
    native_csv.write_text("target_id,native_pdb_path\n", encoding="utf-8")

    execution_queue = {
        "rows": [
            {
                "target_id": "T. cruzi KRS1",
                "shard_id": "04_of_20",
                "queue_status": "ready_after_previous_shard",
                "compound_index_start": 1,
                "compound_index_end": 2,
            }
        ],
    }
    compound_universe = {
        "rows": [
            {"compound_index": 1, "compound_name": "cmp1", "canonical_smiles": "CC1"},
            {"compound_index": 2, "compound_name": "cmp2", "canonical_smiles": "CC2"},
        ]
    }
    portfolio = {"rows": [{"target_id": "T. cruzi KRS1", "domain_family": "enzyme"}]}

    payload = mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv=str(native_csv),
        target_id="T. cruzi KRS1",
        shard_id="04_of_20",
    )
    summary = payload["summary"]
    rows = {row["command_kind"]: row for row in payload["rows"]}

    assert summary["observed_band_gate_relax_profile_id"] == "tcruzi_krs1_stage6_gate51"
    assert summary["observed_band_gate_relax_profile_ready"] is True
    assert rows["throughput_preflight_tuned_gate51"]["enabled"] is True
    assert rows["throughput_execute_tuned_gate51"]["enabled"] is True
    assert "--gate-max-mean-min-distance-A 5.1" in rows["throughput_preflight_tuned_gate51"]["command"]
    assert "--strict-gate-max-mean-min-distance-A 5.1" in rows["throughput_preflight_tuned_gate51"]["command"]
