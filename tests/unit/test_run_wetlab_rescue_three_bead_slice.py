from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_rescue_three_bead_slice as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_run_wetlab_rescue_three_bead_slice_materializes_manifest_and_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DEFAULT_OUT_MD", str(tmp_path / "runs" / "wetlab_rescue_three_bead_slice_current.md"))

    candidates_json = tmp_path / "runs" / "wetlab_rescue_three_bead_candidates_current.json"
    rescue_lane_json = tmp_path / "runs" / "wetlab_hard_target_rescue_lane_current.json"
    rescue_anchor_json = tmp_path / "runs" / "wetlab_rescue_anchor_artifacts_current.json"
    stage1_queue_csv = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_stage1_queue.csv"
    )
    stage2_manifest_csv = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_stage2_traj_manifest.csv"
    )
    stage2_traj_root = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_stage2_traj_frames"
    )
    stage2_traj_root.mkdir(parents=True, exist_ok=True)
    _write_csv(
        stage1_queue_csv,
        "queue_id,target,ligand_id\nq1,T. cruzi PDE,lig_001\nq2,T. cruzi PDE,lig_002\nq3,T. cruzi PDE,lig_003\n",
    )
    _write_csv(
        stage2_manifest_csv,
        "queue_id,target,ligand_id,status,trajectory_npz\nq1,T. cruzi PDE,lig_001,ok_cached,traj1.npz\n",
    )

    _write_json(
        candidates_json,
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "candidate_count": 3,
            },
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "20_of_20",
                    "priority_rank": 1,
                    "ligand_id": "lig_001",
                    "binding_energy_proxy": -8.2,
                    "stability_score": 0.9,
                    "mean_min_distance_A": 5.1,
                },
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "20_of_20",
                    "priority_rank": 2,
                    "ligand_id": "lig_002",
                    "binding_energy_proxy": -7.8,
                    "stability_score": 0.8,
                    "mean_min_distance_A": 5.2,
                },
                {
                    "target_id": "T. cruzi PDE",
                    "shard_id": "20_of_20",
                    "priority_rank": 3,
                    "ligand_id": "lig_003",
                    "binding_energy_proxy": -7.5,
                    "stability_score": 0.7,
                    "mean_min_distance_A": 5.3,
                },
            ],
        },
    )
    _write_json(
        rescue_lane_json,
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
            }
        },
    )
    _write_json(
        rescue_anchor_json,
        {
            "summary": {
                "rescue_target_native_csv": str(tmp_path / "runs" / "rescues" / "native.csv"),
                "rescue_target_pocket_csv": str(tmp_path / "runs" / "rescues" / "pocket.csv"),
                "rescue_target_ligand_csv": str(tmp_path / "runs" / "rescues" / "ligand.csv"),
                "attach_rescue_target_native_csv": True,
                "attach_rescue_target_pocket_csv": True,
                "attach_rescue_target_ligand_csv": True,
            }
        },
    )

    payload = mod.run(
        candidates_json=str(candidates_json),
        rescue_lane_json=str(rescue_lane_json),
        rescue_anchor_json=str(rescue_anchor_json),
        target_id="",
        shard_id="",
        top_k=2,
        python_bin="python3",
        execute=False,
        out_md=str(tmp_path / "runs" / "wetlab_rescue_three_bead_slice_current.md"),
    )

    assert payload["summary"]["status"] == "wetlab_rescue_three_bead_slice_ready"
    assert payload["summary"]["target_id"] == "T. cruzi PDE"
    assert payload["summary"]["shard_id"] == "20_of_20"
    assert payload["summary"]["requested_top_k"] == 2
    assert payload["summary"]["slice_candidate_count"] == 2
    assert payload["summary"]["source_candidate_count"] == 3
    assert payload["summary"]["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert payload["rows"][0]["ligand_id"] == "lig_001"
    assert payload["rows"][1]["ligand_id"] == "lig_002"

    manifest_csv = tmp_path / "runs" / "wetlab_rescue_three_bead" / "t_cruzi_pde" / "20_of_20" / "top_2" / "three_bead_slice_manifest.csv"
    queue_subset_csv = tmp_path / "runs" / "wetlab_rescue_three_bead" / "t_cruzi_pde" / "20_of_20" / "top_2" / "three_bead_slice_queue.csv"
    state_json = tmp_path / "runs" / "wetlab_rescue_three_bead" / "t_cruzi_pde" / "20_of_20" / "top_2" / "three_bead_slice_state.json"
    current_json = tmp_path / "runs" / "wetlab_rescue_three_bead_slice_current.json"

    assert manifest_csv.exists()
    assert queue_subset_csv.exists()
    assert state_json.exists()
    assert current_json.exists()
    assert "lig_001" in manifest_csv.read_text(encoding="utf-8")
    state_payload = json.loads(state_json.read_text(encoding="utf-8"))
    assert state_payload["summary"]["slice_manifest_csv"] == str(manifest_csv)
    assert state_payload["summary"]["slice_queue_csv"] == str(queue_subset_csv)
    assert state_payload["summary"]["execution_mode"] == "controller_manifest_only"
    assert state_payload["summary"]["scoring_status"] == "not_executed"


def test_run_wetlab_rescue_three_bead_slice_executes_scoring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DEFAULT_OUT_MD", str(tmp_path / "runs" / "wetlab_rescue_three_bead_slice_current.md"))

    candidates_json = tmp_path / "runs" / "wetlab_rescue_three_bead_candidates_current.json"
    rescue_lane_json = tmp_path / "runs" / "wetlab_hard_target_rescue_lane_current.json"
    rescue_anchor_json = tmp_path / "runs" / "wetlab_rescue_anchor_artifacts_current.json"
    stage1_queue_csv = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_gate51_stage1_queue.csv"
    )
    stage2_manifest_csv = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_gate51_stage2_traj_manifest.csv"
    )
    stage2_traj_root = (
        tmp_path
        / "runs"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_gate51_stage2_traj_frames"
    )
    stage2_traj_root.mkdir(parents=True, exist_ok=True)
    _write_csv(
        stage1_queue_csv,
        "queue_id,target,ligand_id\nq1,T. cruzi PDE,lig_001\nq2,T. cruzi PDE,lig_002\n",
    )
    _write_csv(
        stage2_manifest_csv,
        "queue_id,target,ligand_id,status,trajectory_npz\nq1,T. cruzi PDE,lig_001,ok_cached,traj1.npz\n",
    )
    _write_json(
        candidates_json,
        {
            "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "candidate_count": 2},
            "rows": [
                {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "priority_rank": 1, "ligand_id": "lig_001"},
                {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "priority_rank": 2, "ligand_id": "lig_002"},
            ],
        },
    )
    _write_json(
        rescue_lane_json,
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "rescue_base_command_kind": "throughput_preflight_tuned_gate51",
            }
        },
    )
    _write_json(
        rescue_anchor_json,
        {
            "summary": {
                "rescue_target_native_csv": str(tmp_path / "runs" / "rescues" / "native.csv"),
                "rescue_target_pocket_csv": str(tmp_path / "runs" / "rescues" / "pocket.csv"),
                "rescue_target_ligand_csv": str(tmp_path / "runs" / "rescues" / "ligand.csv"),
                "attach_rescue_target_native_csv": True,
                "attach_rescue_target_pocket_csv": True,
                "attach_rescue_target_ligand_csv": True,
            }
        },
    )

    class DummyProc:
        returncode = 0

    def _fake_run(cmd, cwd, text, stdout, stderr, check):
        summary_json = tmp_path / "runs" / "wetlab_rescue_three_bead" / "t_cruzi_pde" / "20_of_20" / "top_2" / "three_bead_slice_summary.json"
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(json.dumps({"summary": {"pass": True}}), encoding="utf-8")
        return DummyProc()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    payload = mod.run(
        candidates_json=str(candidates_json),
        rescue_lane_json=str(rescue_lane_json),
        rescue_anchor_json=str(rescue_anchor_json),
        target_id="",
        shard_id="",
        top_k=2,
        python_bin="python3",
        execute=True,
        out_md=str(tmp_path / "runs" / "wetlab_rescue_three_bead_slice_current.md"),
    )

    assert payload["summary"]["execution_mode"] == "local_refine_scoring_executed"
    assert payload["summary"]["scoring_status"] == "pass"
    assert payload["summary"]["scoring_returncode"] == 0
