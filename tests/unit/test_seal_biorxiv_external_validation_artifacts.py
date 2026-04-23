from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_seal_biorxiv_external_validation_artifacts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    package_zip = runs / "package.zip"
    package_zip.write_text("zip\n", encoding="utf-8")
    reviewer_index = runs / "index.html"
    reviewer_index.write_text("<html></html>\n", encoding="utf-8")
    meta = runs / "meta.json"
    meta.write_text(
        json.dumps(
            {
                "current_files": {
                    "archive_zip": str(package_zip.resolve()),
                    "reviewer_index_html": str(reviewer_index.resolve()),
                }
            }
        ),
        encoding="utf-8",
    )

    other = {}
    for name in ["summary.json", "claim.md", "audit.json", "main.md", "temporal.md", "assets.zip"]:
        p = runs / name
        p.write_text(name + "\n", encoding="utf-8")
        other[name] = p

    out_json = runs / "seal.json"
    out_md = runs / "seal.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/seal_biorxiv_external_validation_artifacts.py"),
            "--current-package-meta-json",
            str(meta),
            "--run-summary-json",
            str(other["summary.json"]),
            "--claim-matrix-md",
            str(other["claim.md"]),
            "--audit-json",
            str(other["audit.json"]),
            "--main-table-md",
            str(other["main.md"]),
            "--temporal-baseline-md",
            str(other["temporal.md"]),
            "--submission-assets-zip",
            str(other["assets.zip"]),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["sealed_file_count"] >= 6
    assert out_md.exists()
