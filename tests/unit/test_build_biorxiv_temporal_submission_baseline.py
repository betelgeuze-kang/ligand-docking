from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_submission_baseline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    coverage_json = runs_dir / "coverage.json"
    coverage_json.write_text(
        json.dumps(
            {
                "ligand": {"item_ready_count": 186, "dataset_ready_count": 0},
                "idp": {"item_ready_count": 16, "dataset_ready_count": 4},
                "overall_item_ready_count": 202,
                "overall_dataset_ready_count": 4,
            }
        ),
        encoding="utf-8",
    )
    remaining_json = runs_dir / "remaining.json"
    remaining_json.write_text(
        json.dumps(
            {
                "policy_counts": {"intentional_dataset_control": 1, "no_public_anchor_found": 2},
                "rows": [{"holdout_name": "prion_like_polyq_control", "policy_label": "intentional_dataset_control", "curation_status": "dataset_control_policy_current"}],
            }
        ),
        encoding="utf-8",
    )
    synthetic_json = runs_dir / "synthetic.json"
    synthetic_json.write_text(
        json.dumps({"item_ready_count": 9, "dataset_ready_count": 4}),
        encoding="utf-8",
    )
    assets_zip = runs_dir / "assets.zip"
    assets_zip.write_text("zipstub\n", encoding="utf-8")

    out_json = runs_dir / "baseline.json"
    out_md = runs_dir / "baseline.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_submission_baseline.py"),
            "--coverage-json",
            str(coverage_json),
            "--remaining-policy-json",
            str(remaining_json),
            "--synthetic-progress-json",
            str(synthetic_json),
            "--submission-assets-zip",
            str(assets_zip),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["idp_item_ready_count"] == 16
    assert data["overall_dataset_ready_count"] == 4
    assert data["remaining_policy_counts"]["intentional_dataset_control"] == 1
    assert out_md.exists()
