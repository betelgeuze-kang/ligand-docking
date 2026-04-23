from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.wetlab_target_render_utils import write_artifact
from tools.run_wetlab_cathepsin_k_allatom_refinement import main


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_run_wetlab_cathepsin_k_allatom_refinement_execute_false(tmp_path: Path, monkeypatch) -> None:
    queue_csv = tmp_path / "source_queue.csv"
    stage2_manifest = tmp_path / "stage2_manifest.csv"
    traj_root = tmp_path / "traj"
    traj_root.mkdir()
    _write_csv(queue_csv, [{"ligand_id": "lig_a"}, {"ligand_id": "lig_b"}])
    _write_csv(stage2_manifest, [{"queue_id": "q1", "trajectory_npz": "traj1.npz"}])
    lane_md = tmp_path / "lane.md"
    write_artifact(
        str(lane_md),
        "lane",
        {
            "summary": {
                "target_id": "Cathepsin K",
                "source_shard_id": "19_of_20",
                "ready_for_manual_retry": True,
                "selected_command_kind": "pseudo_allatom_local_refine",
                "selected_threshold_A": 2.5,
                "selected_ligand_model": "3bead_implicit_hbond",
                "source_queue_csv": str(queue_csv),
                "source_stage2_manifest_csv": str(stage2_manifest),
                "source_trajectory_root": str(traj_root),
            },
            "rows": [
                {"target_id": "Cathepsin K", "target_slug": "cathepsin_k", "source_shard_id": "19_of_20", "priority_rank": 1, "ligand_id": "lig_a", "binding_energy_proxy": -1.0, "stability_score": 0.3, "mean_min_distance_A": 2.2},
                {"target_id": "Cathepsin K", "target_slug": "cathepsin_k", "source_shard_id": "19_of_20", "priority_rank": 2, "ligand_id": "lig_b", "binding_energy_proxy": -0.8, "stability_score": 0.2, "mean_min_distance_A": 2.8},
            ],
        },
    )
    out_md = tmp_path / "runner.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_wetlab_cathepsin_k_allatom_refinement.py",
            "--lane-json",
            str(lane_md.with_suffix(".json")),
            "--top-k",
            "2",
            "--no-execute",
            "--out-md",
            str(out_md),
        ],
    )
    main()
    payload = json.loads(out_md.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["summary"]["slice_candidate_count"] == 2
    assert payload["summary"]["execution_mode"] == "controller_manifest_only"
    assert Path(payload["summary"]["slice_manifest_csv"]).exists()

