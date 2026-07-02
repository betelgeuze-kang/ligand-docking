#!/usr/bin/env python3
"""Check PR #38 slice patches against the merge-base using a temporary index.

This preflight verifies that each local slice patch can be applied to the base
tree without touching the real worktree or index. It does not apply patches,
create branches, stage, commit, push, post comments, run external jobs, or
promote claims.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PATCH_BUNDLE_JSON = ".betelgeuze/pr38_slice_patch_bundle_current.json"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_slice_patch_apply_preflight_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_slice_patch_apply_preflight_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_slice_patch_apply_preflight_current.md"
DEFAULT_TMP_DIR = ".betelgeuze/pr38_slice_patch_apply_preflight_tmp"

PACKET_TYPE = "pr38_slice_patch_apply_preflight"
SCHEMA_VERSION = "pr38_slice_patch_apply_preflight_v1"

CLAIM_BOUNDARY = (
    "PR #38 slice patch apply preflight only; it checks local patch applicability against the merge-base with "
    "temporary Git index files. It does not apply patches to the real worktree, create branches, stage, commit, "
    "push, post comments, merge PR #38, run external benchmarks, submit CASP targets, promote paid-pilot wording, "
    "or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
    "patches_applied": False,
    "branches_created": False,
    "real_index_mutated": False,
    "worktree_mutated": False,
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_git_with_index(
    *,
    root: Path,
    index_path: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(index_path)
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _check_patch_against_base(
    *,
    root: Path,
    merge_base_sha: str,
    patch_path: Path,
    tmp_dir: Path,
    sequence: int,
    slice_id: str,
) -> dict[str, Any]:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    index_path = tmp_dir / f"{sequence:02d}-{slice_id}.index"
    if index_path.exists():
        index_path.unlink()
    read_tree = _run_git_with_index(
        root=root,
        index_path=index_path,
        args=["read-tree", merge_base_sha],
    )
    if read_tree.returncode != 0:
        return {
            "apply_check_ready": False,
            "apply_check_status": "read_tree_failed",
            "apply_check_exit_code": read_tree.returncode,
            "apply_check_stderr": read_tree.stderr.strip(),
            "temporary_index_path": str(index_path),
        }
    apply_check = _run_git_with_index(
        root=root,
        index_path=index_path,
        args=["apply", "--cached", "--check", str(patch_path)],
    )
    return {
        "apply_check_ready": apply_check.returncode == 0,
        "apply_check_status": "apply_check_passed" if apply_check.returncode == 0 else "apply_check_failed",
        "apply_check_exit_code": apply_check.returncode,
        "apply_check_stderr": apply_check.stderr.strip(),
        "temporary_index_path": str(index_path),
    }


def build_pr38_slice_patch_apply_preflight(
    *,
    patch_bundle_json: str | Path = DEFAULT_PATCH_BUNDLE_JSON,
    tmp_dir: str | Path = DEFAULT_TMP_DIR,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    bundle_payload = _read_json(patch_bundle_json, root=root_path)
    bundle_summary = bundle_payload.get("summary") if isinstance(bundle_payload.get("summary"), dict) else {}
    merge_base_sha = _text(bundle_summary.get("merge_base_sha"))
    bundle_ready = bool(bundle_summary.get("patch_bundle_ready") is True)
    rows_in = bundle_payload.get("rows") if isinstance(bundle_payload.get("rows"), list) else []
    tmp_path = _resolve(tmp_dir, root=root_path)
    rows: list[dict[str, Any]] = []

    for row_in in rows_in:
        if not isinstance(row_in, dict):
            continue
        sequence = int(row_in.get("sequence") or len(rows) + 1)
        slice_id = _text(row_in.get("slice_id"))
        patch_path = _resolve(_text(row_in.get("patch_path")), root=root_path)
        if not patch_path.exists():
            check = {
                "apply_check_ready": False,
                "apply_check_status": "patch_missing",
                "apply_check_exit_code": 1,
                "apply_check_stderr": f"Patch file not found: {patch_path}",
                "temporary_index_path": "",
            }
        elif not merge_base_sha:
            check = {
                "apply_check_ready": False,
                "apply_check_status": "merge_base_missing",
                "apply_check_exit_code": 1,
                "apply_check_stderr": "merge_base_sha missing from patch bundle summary",
                "temporary_index_path": "",
            }
        else:
            check = _check_patch_against_base(
                root=root_path,
                merge_base_sha=merge_base_sha,
                patch_path=patch_path,
                tmp_dir=tmp_path,
                sequence=sequence,
                slice_id=slice_id,
            )
        rows.append(
            {
                "sequence": sequence,
                "slice_id": slice_id,
                "patch_path": _text(row_in.get("patch_path")),
                "patch_sha256": _text(row_in.get("patch_sha256")),
                "changed_file_count": int(row_in.get("changed_file_count") or 0),
                "focused_test_command": _text(row_in.get("focused_test_command")),
                "claim_boundary": _text(row_in.get("claim_boundary")),
                **check,
                **_READ_ONLY_FLAGS,
            }
        )

    failed_rows = [row for row in rows if not row["apply_check_ready"]]
    ready = bundle_ready and bool(rows) and not failed_rows
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_slice_patch_apply_preflight_ready" if ready else "blocked_pr38_slice_patch_apply_preflight",
        "patch_apply_preflight_ready": ready,
        "patch_bundle_status": _text(bundle_summary.get("status")) or "missing",
        "patch_bundle_ready": bundle_ready,
        "merge_base_sha": merge_base_sha,
        "slice_patch_count": len(rows),
        "apply_check_pass_count": sum(1 for row in rows if row["apply_check_ready"]),
        "apply_check_fail_count": len(failed_rows),
        "failed_slice_ids": [row["slice_id"] for row in failed_rows],
        "temporary_index_dir": str(tmp_path.relative_to(root_path) if tmp_path.is_relative_to(root_path) else tmp_path),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After explicit human approval for branch/commit work, apply the checked patches in extraction-plan "
            "order on clean child branches and run focused tests plus ai-verify."
            if ready
            else "Inspect failed slice patch checks before any branch or commit work."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Slice Patch Apply Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- patch_bundle_status: `{s['patch_bundle_status']}`",
        f"- merge_base_sha: `{s['merge_base_sha']}`",
        f"- slice_patch_count: `{s['slice_patch_count']}`",
        f"- apply_check_pass_count: `{s['apply_check_pass_count']}`",
        f"- apply_check_fail_count: `{s['apply_check_fail_count']}`",
        f"- temporary_index_dir: `{s['temporary_index_dir']}`",
        "",
        "| seq | slice | status | exit | patch |",
        "| --: | --- | --- | --: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {seq} | `{slice_id}` | `{status}` | {exit_code} | `{patch}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                status=row["apply_check_status"],
                exit_code=row["apply_check_exit_code"],
                patch=row["patch_path"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check PR #38 slice patches against the merge-base.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--patch-bundle-json", default=DEFAULT_PATCH_BUNDLE_JSON)
    parser.add_argument("--tmp-dir", default=DEFAULT_TMP_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_slice_patch_apply_preflight(
        patch_bundle_json=args.patch_bundle_json,
        tmp_dir=args.tmp_dir,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["patch_apply_preflight_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
