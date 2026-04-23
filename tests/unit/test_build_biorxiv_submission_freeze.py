from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_submission_freeze(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    package_zip = runs / "pkg.zip"
    package_zip.write_text("pkg\n", encoding="utf-8")
    submission_zip = runs / "submission.zip"
    submission_zip.write_text("submission\n", encoding="utf-8")
    submission_manifest = runs / "submission_manifest.json"
    submission_manifest.write_text("{\"ok\": true}\n", encoding="utf-8")
    audit_json = runs / "audit.json"
    audit_json.write_text("{\"pass\": true}\n", encoding="utf-8")
    run_summary = runs / "summary.json"
    run_summary.write_text("{\"sets\": []}\n", encoding="utf-8")
    temporal_json = runs / "temporal.json"
    temporal_json.write_text("{\"overall_item_ready_count\": 202, \"overall_dataset_ready_count\": 4}\n", encoding="utf-8")
    robust_matrix = runs / "robustness_matrix.json"
    robust_matrix.write_text("{\"rows\": []}\n", encoding="utf-8")
    robust_compare = runs / "robustness_compare.json"
    robust_compare.write_text("{\"all_sets_preserved\": true, \"ligand_pass_count\": 9}\n", encoding="utf-8")
    governance = runs / "seal.json"
    governance.write_text("{\"sealed_file_count\": 3}\n", encoding="utf-8")
    meta = runs / "current_package.json"
    meta.write_text(
        json.dumps(
            {
                "bundle_tag": "2026-03-22_biorxiv_v7r1",
                "promoted_at_local": "2026-03-22T13:43:58+09:00",
                "run_root": "/tmp/run",
                "package_root": "/tmp/package",
                "summary_json": str(run_summary),
                "audit_json": str(audit_json),
                "audit_pass": True,
                "convenience_artifacts": {"archive_zip": str(package_zip)},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs / "freeze.json"
    out_md = runs / "freeze.md"
    archive_zip = runs / "submission_frozen.zip"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_biorxiv_submission_freeze.py"),
            "--current-package-meta-json",
            str(meta),
            "--submission-assets-zip",
            str(submission_zip),
            "--submission-assets-manifest-json",
            str(submission_manifest),
            "--temporal-baseline-json",
            str(temporal_json),
            "--robustness-matrix-json",
            str(robust_matrix),
            "--robustness-comparison-json",
            str(robust_compare),
            "--governance-seal-json",
            str(governance),
            "--archive-zip",
            str(archive_zip),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["bundle_tag"] == "2026-03-22_biorxiv_v7r1"
    assert archive_zip.exists()
    assert data["overall_item_ready_count"] == 202
    assert data["seed_shift_all_sets_preserved"] is True
