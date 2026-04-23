from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_promote_biorxiv_external_validation_rejects_partial(tmp_path: Path) -> None:
    package_root = tmp_path / "biorxiv_external_validation_package_partial"
    _write_json(
        package_root / "package_manifest.json",
        {
            "bundle_tag": "partial",
            "partial_package": True,
            "summary_json": "",
        },
    )
    _write_json(package_root / "audit.json", {"pass": True})

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/promote_biorxiv_external_validation_package.py"),
            "--package-root",
            str(package_root),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "partial package" in (proc.stderr + proc.stdout)


def test_promote_biorxiv_external_validation_promotes_completed(tmp_path: Path) -> None:
    package_root = tmp_path / "biorxiv_external_validation_package_complete"
    run_root = tmp_path / "external_validation_blind_runs_tag"
    out_root = tmp_path / "promoted_current"
    summary_json = run_root / "summary.json"
    _write_json(summary_json, {"status": "completed", "sets": [{"set_id": "set1_core_blind", "pass": True}]})

    for rel in [
        "package_manifest.md",
        "reviewer_summary.md",
        "reviewer_index.html",
        "claim_matrix.csv",
        "claim_matrix.md",
        "failure_triage.json",
        "failure_triage.md",
        "audit.json",
        "audit.md",
    ]:
        _write_text(package_root / rel)
    _write_text(package_root.with_suffix(".zip"))
    _write_json(
        package_root / "package_manifest.json",
        {
            "bundle_tag": "complete_tag",
            "partial_package": False,
            "summary_json": str(summary_json),
            "run_root": str(run_root),
        },
    )
    _write_json(package_root / "audit.json", {"pass": True})

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/promote_biorxiv_external_validation_package.py"),
            "--package-root",
            str(package_root),
            "--out-root",
            str(out_root),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert Path(payload["current_meta_json"]).exists()
    current_meta = json.loads((out_root / "biorxiv_external_validation_package_current.json").read_text(encoding="utf-8"))
    assert current_meta["bundle_tag"] == "complete_tag"
    assert current_meta["audit_pass"] is True
    assert Path(current_meta["convenience_artifacts"]["reviewer_index_html"]).exists()
