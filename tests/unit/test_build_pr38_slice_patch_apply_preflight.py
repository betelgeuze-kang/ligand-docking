from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from tools.product import build_pr38_slice_patch_apply_preflight as mod


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _git_stdout(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return proc.stdout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _init_repo_with_patch(root: Path) -> tuple[str, Path]:
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    (root / "a.txt").write_text("base a\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-m", "base")
    base_sha = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-b", "feature")
    (root / "a.txt").write_text("base a\nfeature a\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-m", "feature")
    patch_path = root / "slice.patch"
    patch_path.write_text(_git_stdout(root, "diff", "--binary", f"{base_sha}...HEAD", "--", "a.txt"), encoding="utf-8")
    return base_sha, patch_path


def _write_bundle(root: Path, *, base_sha: str, patch_path: Path, ready: bool = True) -> Path:
    path = root / "bundle.json"
    _write_json(
        path,
        {
            "summary": {
                "status": "pr38_slice_patch_bundle_ready" if ready else "blocked_pr38_slice_patch_bundle",
                "patch_bundle_ready": ready,
                "merge_base_sha": base_sha,
            },
            "rows": [
                {
                    "sequence": 1,
                    "slice_id": "slice_a",
                    "patch_path": str(patch_path),
                    "patch_sha256": "sha",
                    "changed_file_count": 1,
                    "focused_test_command": "pytest a",
                    "claim_boundary": "No claim.",
                }
            ],
        },
    )
    return path


def test_patch_apply_preflight_checks_patch_with_temporary_index(tmp_path: Path) -> None:
    base_sha, patch_path = _init_repo_with_patch(tmp_path)
    bundle = _write_bundle(tmp_path, base_sha=base_sha, patch_path=patch_path)

    payload = mod.build_pr38_slice_patch_apply_preflight(
        patch_bundle_json=bundle,
        tmp_dir=tmp_path / "tmp-indexes",
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_slice_patch_apply_preflight_ready"
    assert summary["apply_check_pass_count"] == 1
    assert summary["apply_check_fail_count"] == 0
    assert summary["patches_applied"] is False
    assert summary["real_index_mutated"] is False
    row = payload["rows"][0]
    assert row["apply_check_status"] == "apply_check_passed"
    assert row["apply_check_exit_code"] == 0
    assert Path(row["temporary_index_path"]).exists()


def test_patch_apply_preflight_blocks_missing_patch(tmp_path: Path) -> None:
    base_sha, patch_path = _init_repo_with_patch(tmp_path)
    bundle = _write_bundle(tmp_path, base_sha=base_sha, patch_path=patch_path)
    patch_path.unlink()

    payload = mod.build_pr38_slice_patch_apply_preflight(
        patch_bundle_json=bundle,
        tmp_dir=tmp_path / "tmp-indexes",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_slice_patch_apply_preflight"
    assert payload["summary"]["apply_check_fail_count"] == 1
    assert payload["summary"]["failed_slice_ids"] == ["slice_a"]
    assert payload["rows"][0]["apply_check_status"] == "patch_missing"


def test_main_writes_patch_apply_preflight_artifacts(tmp_path: Path) -> None:
    base_sha, patch_path = _init_repo_with_patch(tmp_path)
    bundle = _write_bundle(tmp_path, base_sha=base_sha, patch_path=patch_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--patch-bundle-json",
            str(bundle),
            "--tmp-dir",
            str(tmp_path / "tmp-indexes"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pr38_slice_patch_apply_preflight_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["apply_check_status"] == "apply_check_passed"
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Slice Patch Apply Preflight")
