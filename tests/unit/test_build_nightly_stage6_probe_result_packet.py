from __future__ import annotations

from tools import build_nightly_stage6_probe_result_packet as mod


def test_build_nightly_stage6_probe_result_packet_projects_gate_pass(tmp_path) -> None:
    imatinib = tmp_path / "imatinib.csv"
    imatinib.write_text(
        "queue_id,mean_min_distance_A,final_min_distance_A,binding_energy_mmpbsa_kcal_mol_proxy,strategy_reason,seed\n"
        "HIV1_PROTEASE__rep0004__imatinib,2.214552210569382,1.822695255279541,-1.7014403758821175,force_target,464162\n",
        encoding="utf-8",
    )
    aspirin = tmp_path / "aspirin.csv"
    aspirin.write_text(
        "queue_id,mean_min_distance_A,final_min_distance_A,binding_energy_mmpbsa_kcal_mol_proxy,strategy_reason,seed\n"
        "HIV1_PROTEASE__rep0023__aspirin,1.603783567547798,1.729337453842163,-0.6889675905491839,force_target,156993\n",
        encoding="utf-8",
    )
    payload = mod.build_payload(
        tuning_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                "primary_gate_threshold": 2.5,
                "primary_gate_value": 2.655165582969785,
            },
            "rows": [
                {"row_key": "EGFR_KINASE::aspirin", "mean_min_distance_A": 2.9039315617084505},
                {"row_key": "HIV1_PROTEASE::imatinib", "mean_min_distance_A": 2.70565606713295},
                {"row_key": "HIV1_PROTEASE::aspirin", "mean_min_distance_A": 2.658669866025448},
                {"row_key": "EGFR_KINASE::imatinib", "mean_min_distance_A": 2.352404837012291},
            ],
        },
        sweep_payload={"summary": {"packet_artifact": "runs/nightly_stage6_tuning_sweep_packet_current.md"}},
        probe_manifest_artifacts={
            "HIV1_PROTEASE::imatinib": str(imatinib),
            "HIV1_PROTEASE::aspirin": str(aspirin),
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_stage6_probe_result_packet_ready"
    assert summary["probe_row_count"] == 2
    assert summary["primary_probe_row_key"] == "HIV1_PROTEASE::aspirin"
    assert round(summary["projected_gate_mean_min_distance_A"], 3) == 2.269
    assert summary["projected_gate_pass"] is True
    assert "Promote the uncapped ADReSS probe rows" in summary["next_required_step"]
