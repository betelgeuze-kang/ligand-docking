from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.build_wetlab_sarscov2_mpro_allatom_refinement_lane import build_payload


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_wetlab_sarscov2_mpro_allatom_refinement_lane_selects_latest_success(tmp_path: Path) -> None:
    shard_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "sars_cov_2_mpro" / "02_of_20"
    stage3_csv = shard_dir / "throughput_run_gate45_stage3_scores.csv"
    queue_csv = shard_dir / "throughput_run_gate45_stage1_queue.csv"
    stage2_manifest = shard_dir / "throughput_run_gate45_stage2_traj_manifest.csv"
    traj_root = shard_dir / "throughput_run_gate45_stage2_traj_frames"
    traj_root.mkdir(parents=True, exist_ok=True)
    _write_csv(stage3_csv, [{"ligand_id": "lig_m", "binding_energy_proxy": -0.9, "stability_score": 0.5, "mean_min_distance_A": 4.1}])
    _write_csv(queue_csv, [{"ligand_id": "lig_m"}])
    _write_csv(stage2_manifest, [{"queue_id": "qm", "trajectory_npz": "traj.npz"}])
    summary_json = shard_dir / "throughput_run_gate45_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "artifacts": {
                    "queue_csv": str(queue_csv),
                    "stage2_trajectory_summary_json": str(stage2_manifest),
                    "trajectory_root": str(traj_root),
                    "stage3_scores_csv": str(stage3_csv),
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_payload(
        {"rows": [{"target_id": "SARS-CoV-2 Mpro", "target_slug": "sars_cov_2_mpro", "shard_id": "02_of_20", "queue_status": "result_ready"}]},
        {"summary": {"selected_command_kind": "throughput_preflight_tuned_gate45", "source_summary_json": str(summary_json)}},
        {"summary": {"recommended_observed_threshold_A": 4.45}},
        top_n=1,
    )
    summary = payload["summary"]
    assert summary["source_shard_id"] == "02_of_20"
    assert summary["candidate_row_count"] == 1
    assert payload["rows"][0]["ligand_id"] == "lig_m"
