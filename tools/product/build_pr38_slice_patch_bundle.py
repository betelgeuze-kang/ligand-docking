#!/usr/bin/env python3
"""Build read-only patch files for the PR #38 child slices.

This tool consumes the split review packet and extraction plan, then writes one
git patch per proposed child PR under `.betelgeuze/`. It does not apply patches,
create branches, stage, commit, push, post to GitHub, run external jobs, or
promote claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_REF = "origin/main"
DEFAULT_SPLIT_PACKET_JSON = ".betelgeuze/pr38_split_review_packet_current.json"
DEFAULT_EXTRACTION_PLAN_JSON = ".betelgeuze/pr38_child_pr_extraction_plan_current.json"
DEFAULT_OUT_DIR = ".betelgeuze/pr38_slice_patch_bundle_current"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_slice_patch_bundle_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_slice_patch_bundle_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_slice_patch_bundle_current.md"

PACKET_TYPE = "pr38_slice_patch_bundle"
SCHEMA_VERSION = "pr38_slice_patch_bundle_v1"

CLAIM_BOUNDARY = (
    "PR #38 slice patch bundle only; it writes local patch files for already-mapped review slices. It does not "
    "apply patches, create branches, stage, commit, push, post comments, merge PR #38, run external benchmarks, "
    "submit CASP targets, promote paid-pilot wording, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
    "patches_applied": False,
    "branches_created": False,
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


def _git(*args: str, root: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _git_diff_for_paths(*, base_ref: str, paths: list[str], root: Path) -> str:
    if not paths:
        return ""
    proc = subprocess.run(
        ["git", "diff", "--binary", f"{base_ref}...HEAD", "--", *paths],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _slice_rows(split_payload: dict[str, Any], slice_id: str) -> list[dict[str, Any]]:
    rows = split_payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and _text(row.get("slice_id")) == slice_id]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_pr38_slice_patch_bundle(
    *,
    split_packet_json: str | Path = DEFAULT_SPLIT_PACKET_JSON,
    extraction_plan_json: str | Path = DEFAULT_EXTRACTION_PLAN_JSON,
    base_ref: str = DEFAULT_BASE_REF,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    split_payload = _read_json(split_packet_json, root=root_path)
    plan_payload = _read_json(extraction_plan_json, root=root_path)
    split_summary = split_payload.get("summary") if isinstance(split_payload.get("summary"), dict) else {}
    plan_summary = plan_payload.get("summary") if isinstance(plan_payload.get("summary"), dict) else {}
    plan_rows = plan_payload.get("rows") if isinstance(plan_payload.get("rows"), list) else []
    bundle_dir = _resolve(out_dir, root=root_path)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    head_sha = _git("rev-parse", "HEAD", root=root_path)
    merge_base_sha = _git("merge-base", base_ref, "HEAD", root=root_path)

    rows: list[dict[str, Any]] = []
    for plan_row in plan_rows:
        if not isinstance(plan_row, dict):
            continue
        slice_id = _text(plan_row.get("slice_id"))
        sequence = int(plan_row.get("sequence") or len(rows) + 1)
        file_rows = _slice_rows(split_payload, slice_id)
        file_paths = [_text(row.get("file_path")) for row in file_rows if _text(row.get("file_path"))]
        patch_text = _git_diff_for_paths(base_ref=base_ref, paths=file_paths, root=root_path)
        patch_name = f"{sequence:02d}-{slice_id}.patch"
        patch_path = bundle_dir / patch_name
        patch_path.write_text(patch_text, encoding="utf-8")
        rows.append(
            {
                "sequence": sequence,
                "slice_id": slice_id,
                "patch_path": str(patch_path.relative_to(root_path) if patch_path.is_relative_to(root_path) else patch_path),
                "patch_sha256": _sha256(patch_text),
                "patch_byte_count": len(patch_text.encode("utf-8")),
                "patch_line_count": len(patch_text.splitlines()),
                "changed_file_count": len(file_paths),
                "file_paths": file_paths,
                "integration_touchpoint_count": int(plan_row.get("integration_touchpoint_count") or 0),
                "focused_test_command": _text(plan_row.get("focused_test_command")),
                "claim_boundary": _text(plan_row.get("claim_boundary")),
                "draft_branch_name": _text(plan_row.get("draft_branch_name")),
                "draft_pr_title": _text(plan_row.get("draft_pr_title")),
                "patch_nonempty": bool(patch_text.strip()),
                **_READ_ONLY_FLAGS,
            }
        )

    empty_patch_slice_ids = [row["slice_id"] for row in rows if not row["patch_nonempty"]]
    total_file_count = sum(int(row["changed_file_count"]) for row in rows)
    expected_file_count = int(split_summary.get("changed_file_count") or 0)
    ready = (
        bool(split_summary.get("split_review_ready") is True)
        and bool(plan_summary.get("extraction_plan_ready") is True)
        and bool(rows)
        and not empty_patch_slice_ids
        and total_file_count == expected_file_count
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_slice_patch_bundle_ready" if ready else "blocked_pr38_slice_patch_bundle",
        "patch_bundle_ready": ready,
        "base_ref": base_ref,
        "merge_base_sha": merge_base_sha,
        "head_sha": head_sha,
        "split_packet_status": _text(split_summary.get("status")) or "missing",
        "extraction_plan_status": _text(plan_summary.get("status")) or "missing",
        "slice_patch_count": len(rows),
        "expected_changed_file_count": expected_file_count,
        "bundled_changed_file_count": total_file_count,
        "empty_patch_count": len(empty_patch_slice_ids),
        "empty_patch_slice_ids": empty_patch_slice_ids,
        "bundle_dir": str(bundle_dir.relative_to(root_path) if bundle_dir.is_relative_to(root_path) else bundle_dir),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After explicit human approval for branch/commit work, apply each patch on its child branch in the "
            "extraction-plan order and run the row focused tests plus ai-verify."
            if ready
            else "Regenerate split/extraction packets or inspect empty patch slices before branch extraction."
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
        "# PR #38 Slice Patch Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- base_ref: `{s['base_ref']}`",
        f"- merge_base_sha: `{s['merge_base_sha']}`",
        f"- head_sha: `{s['head_sha']}`",
        f"- slice_patch_count: `{s['slice_patch_count']}`",
        f"- bundled_changed_file_count: `{s['bundled_changed_file_count']}`",
        f"- bundle_dir: `{s['bundle_dir']}`",
        "",
        "| seq | slice | files | patch | sha256 |",
        "| --: | --- | --: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {seq} | `{slice_id}` | {files} | `{patch}` | `{sha}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                files=row["changed_file_count"],
                patch=row["patch_path"],
                sha=row["patch_sha256"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build local patch files for the PR #38 child slices.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--split-packet-json", default=DEFAULT_SPLIT_PACKET_JSON)
    parser.add_argument("--extraction-plan-json", default=DEFAULT_EXTRACTION_PLAN_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_slice_patch_bundle(
        split_packet_json=args.split_packet_json,
        extraction_plan_json=args.extraction_plan_json,
        base_ref=args.base_ref,
        out_dir=args.out_dir,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["patch_bundle_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
