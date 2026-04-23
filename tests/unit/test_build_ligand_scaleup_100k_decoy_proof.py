from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ligand_scaleup_100k_decoy_proof(tmp_path: Path) -> None:
    base = tmp_path / "runs" / "external_validation_test"
    base.parent.mkdir(parents=True, exist_ok=True)
    task_specs = [
        (
            "set1_core_blind_gpcr_core_full_hard_decoy_summary.json",
            "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage1_summary.json",
            "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_summary.json",
            1,
            10000,
        ),
        (
            "set1_core_blind_ion_trpv1_chembl20_full_hard_decoy_summary.json",
            "set1_core_blind_ion_trpv1_chembl20_full_p0_n100000_r1_stage1_summary.json",
            "set1_core_blind_ion_trpv1_chembl20_full_p0_n100000_r1_stage2_traj_summary.json",
            1,
            10000,
        ),
        (
            "set1_core_blind_kinase_core_full_hard_decoy_summary.json",
            "set1_core_blind_kinase_core_full_p0_n100000_r1_stage1_summary.json",
            "set1_core_blind_kinase_core_full_p0_n100000_r1_stage2_traj_summary.json",
            2,
            20000,
        ),
    ]
    for hard_name, stage1_name, stage2_name, targets, queue_rows in task_specs:
        (base.parent / f"{base.name}_{hard_name}").write_text(
            json.dumps(
                {
                    "synthetic_decoys": {
                        "requested": 100000,
                        "generated": 100000,
                        "shortfall": 0,
                        "target_generation_stats": [
                            {"target": f"T{i}", "generated": 100000 // targets}
                            for i in range(targets)
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )
        (base.parent / f"{base.name}_{stage1_name}").write_text(
            json.dumps(
                {
                    "ligands": 100000,
                    "queue_rows": queue_rows,
                    "jobs_per_target": 10000,
                    "targets": targets,
                }
            ),
            encoding="utf-8",
        )
        (base.parent / f"{base.name}_{stage2_name}").write_text(
            json.dumps({"processed_rows": queue_rows}),
            encoding="utf-8",
        )

    out_json = tmp_path / "runs" / "proof.json"
    out_csv = tmp_path / "runs" / "proof.csv"
    out_md = tmp_path / "runs" / "proof.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_ligand_scaleup_100k_decoy_proof.py"),
            "--run-prefix",
            str(base),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    result = json.loads(out_json.read_text(encoding="utf-8"))
    assert result["summary"]["all_generated_100k"] is True
    assert result["summary"]["queue_rows_match_expected"] is True
    assert "really did generate 100k" in result["summary"]["interpretation"]
