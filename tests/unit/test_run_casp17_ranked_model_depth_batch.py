from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_run_casp17_ranked_model_depth_batch_executes_small_cpu_lane(tmp_path: Path) -> None:
    sequence_dir = tmp_path / "seq"
    sequence_dir.mkdir()
    (sequence_dir / "T9998.fasta").write_text(">T9998\nACDEFGHIK\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_ranked_model_depth_batch.py"),
            "--target-ids",
            "T9998",
            "--sequence-dir",
            str(sequence_dir),
            "--job-root",
            str(tmp_path / "jobs"),
            "--ranked-ts-dir",
            str(tmp_path / "top5"),
            "--author-code",
            "TEST-AUTHOR",
            "--model-count",
            "2",
            "--quality-preset",
            "smoke",
            "--ensemble-size",
            "3",
            "--device",
            "cpu",
            "--allow-cpu",
            "--execute",
            "--ranked-depth-json",
            str(tmp_path / "ranked_depth.json"),
            "--ranked-depth-csv",
            str(tmp_path / "ranked_depth.csv"),
            "--ranked-depth-md",
            str(tmp_path / "ranked_depth.md"),
            "--out-json",
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "batch.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    batch = json.loads((tmp_path / "batch.json").read_text(encoding="utf-8"))
    ranked = json.loads((tmp_path / "ranked_depth.json").read_text(encoding="utf-8"))

    assert batch["summary"]["completed_count"] == 1
    assert batch["summary"]["ranked_raw_ready_count"] == 1
    assert batch["summary"]["ranked_depth_pass_count"] == 1
    assert batch["summary"]["candidate_gate_pass_count"] == 2
    assert ranked["summary"]["candidate_gate_pass_count"] == 2
    assert ranked["rows"][0]["ranked_depth_status"] == "pass"
    for rank in range(1, 3):
        assert (tmp_path / "jobs" / "T9998" / f"T9998_model_{rank}.pdb").exists()
        assert (tmp_path / "top5" / "T9998" / f"T9998_model_{rank}TS.pdb").exists()
