from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from tools.product import build_pr38_slice_patch_bundle as mod


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _init_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    (root / "a.txt").write_text("base a\n", encoding="utf-8")
    (root / "b.txt").write_text("base b\n", encoding="utf-8")
    _git(root, "add", "a.txt", "b.txt")
    _git(root, "commit", "-m", "base")
    base_sha = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-b", "feature")
    (root / "a.txt").write_text("base a\nfeature a\n", encoding="utf-8")
    (root / "b.txt").write_text("base b\nfeature b\n", encoding="utf-8")
    _git(root, "add", "a.txt", "b.txt")
    _git(root, "commit", "-m", "feature")
    return base_sha


def _write_packets(root: Path, *, split_ready: bool = True) -> tuple[Path, Path]:
    split_packet = {
        "summary": {
            "status": "pr38_split_review_packet_ready" if split_ready else "blocked_pr38_split_review_packet",
            "split_review_ready": split_ready,
            "changed_file_count": 2,
        },
        "rows": [
            {"slice_id": "slice_a", "file_path": "a.txt"},
            {"slice_id": "slice_b", "file_path": "b.txt"},
        ],
    }
    extraction_plan = {
        "summary": {
            "status": "pr38_child_pr_extraction_plan_ready",
            "extraction_plan_ready": True,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "slice_a",
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest a",
                "claim_boundary": "No claim A.",
                "draft_branch_name": "slice-a",
                "draft_pr_title": "Slice A",
            },
            {
                "sequence": 2,
                "slice_id": "slice_b",
                "integration_touchpoint_count": 1,
                "focused_test_command": "pytest b",
                "claim_boundary": "No claim B.",
                "draft_branch_name": "slice-b",
                "draft_pr_title": "Slice B",
            },
        ],
    }
    split_path = root / "split.json"
    plan_path = root / "plan.json"
    _write_json(split_path, split_packet)
    _write_json(plan_path, extraction_plan)
    return split_path, plan_path


def test_slice_patch_bundle_writes_one_patch_per_child_slice_with_checksums(tmp_path: Path) -> None:
    base_sha = _init_repo(tmp_path)
    split_path, plan_path = _write_packets(tmp_path)

    payload = mod.build_pr38_slice_patch_bundle(
        split_packet_json=split_path,
        extraction_plan_json=plan_path,
        base_ref=base_sha,
        out_dir=tmp_path / "patches",
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_slice_patch_bundle_ready"
    assert summary["slice_patch_count"] == 2
    assert summary["expected_changed_file_count"] == 2
    assert summary["bundled_changed_file_count"] == 2
    assert summary["empty_patch_count"] == 0
    assert summary["patches_applied"] is False
    assert summary["branches_created"] is False
    rows = {row["slice_id"]: row for row in payload["rows"]}
    patch_a = tmp_path / rows["slice_a"]["patch_path"]
    patch_b = tmp_path / rows["slice_b"]["patch_path"]
    assert patch_a.read_text(encoding="utf-8").find("feature a") != -1
    assert patch_b.read_text(encoding="utf-8").find("feature b") != -1
    assert rows["slice_a"]["patch_sha256"] == hashlib.sha256(patch_a.read_bytes()).hexdigest()
    assert rows["slice_b"]["patch_nonempty"] is True
    assert rows["slice_b"]["integration_touchpoint_count"] == 1


def test_slice_patch_bundle_blocks_if_split_packet_is_not_ready(tmp_path: Path) -> None:
    base_sha = _init_repo(tmp_path)
    split_path, plan_path = _write_packets(tmp_path, split_ready=False)

    payload = mod.build_pr38_slice_patch_bundle(
        split_packet_json=split_path,
        extraction_plan_json=plan_path,
        base_ref=base_sha,
        out_dir=tmp_path / "patches",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_slice_patch_bundle"
    assert payload["summary"]["patch_bundle_ready"] is False


def test_main_writes_slice_patch_bundle_manifest_artifacts(tmp_path: Path) -> None:
    base_sha = _init_repo(tmp_path)
    split_path, plan_path = _write_packets(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--base-ref",
            base_sha,
            "--split-packet-json",
            str(split_path),
            "--extraction-plan-json",
            str(plan_path),
            "--out-dir",
            str(tmp_path / "patches"),
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
    assert payload["summary"]["status"] == "pr38_slice_patch_bundle_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == ["slice_a", "slice_b"]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Slice Patch Bundle")
