import json
import os
import subprocess
import sys
from pathlib import Path


def test_help_runs_without_pythonpath_when_invoked_by_script_path():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "tools/run_ligand_backmapping_scoring.py", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "run_ligand_backmapping_scoring.py" in result.stdout


def test_backmapping_scoring_summary_exports_hbond_evidence_and_claim_metadata(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    queue_csv = tmp_path / "queue.csv"
    out_dir = tmp_path / "out"
    summary_json = out_dir / "summary.json"
    scores_csv = out_dir / "scores.csv"
    queue_csv.write_text(
        "\n".join(
            [
                "queue_id,target,ligand_id,ligand_smiles,pocket_x,pocket_y,pocket_z,ligand_bead0_x,ligand_bead0_y,ligand_bead0_z,ligand_bead1_x,ligand_bead1_y,ligand_bead1_z",
                "q1,unit,l1,CC(=O)N,0,0,0,0,0,0,1.6,0,0",
                "q2,unit,l2,CCCC,0,0,0,0,0,0,1.6,0,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/run_ligand_backmapping_scoring.py",
            "--queue-csv",
            str(queue_csv),
            "--score-only",
            "--no-two-pass-scoring",
            "--ligand-model",
            "4bead_onsps_hbond",
            "--allow-missing-trajectory",
            "--min-frames",
            "1",
            "--max-jobs",
            "2",
            "--workers",
            "0",
            "--parallel-threshold",
            "99",
            "--topk-report",
            "2",
            "--out-dir",
            str(out_dir),
            "--out-summary-json",
            str(summary_json),
            "--out-scores-csv",
            str(scores_csv),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    hbond = payload["hbond_evidence_summary"]
    claim = payload["claim_metadata"]

    assert hbond["schema_version"] == "hbond_evidence_v1"
    assert hbond["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert hbond["evaluated_row_count"] == 2
    assert hbond["claim_safe_row_count"] == 0
    assert hbond["onsps_backmap_claim_safe_row_count"] >= 1
    assert hbond["blocked_reason_counts"]["pose_geometry_missing"] >= 1
    assert claim["claim_safe"] is False
    assert claim["ligand_topology_valid"] is True
    assert claim["ligand_topology_claim_safe"] is True
    assert claim["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert claim["ligand_topology_schema_ready_row_count"] == 2
    assert claim["ligand_topology_valid_row_count"] == 2
    assert claim["ligand_topology_claim_safe_row_count"] == 2
    assert claim["ligand_topology_invalid_row_count"] == 0
    assert claim["hbond_evidence_status"] == "review"
    assert "runner_summary_not_claim_promoted" in claim["blocked_reason"]
    assert "protein_topology_missing" in claim["blocked_reason"]

    top = payload["topk"][0]
    assert top["ligand_topology_valid"] is True
    assert top["ligand_topology_claim_safe"] is True
    assert top["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert top["ligand_topology_source"] == "rdkit"
    assert top["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert top["onsps_backmap_schema_version"] == "onsps_backmap_evidence_v1"
    assert top["hbond_claim_safe"] is False
    assert top["hbond_blocked_reason"] == "pose_geometry_missing"
