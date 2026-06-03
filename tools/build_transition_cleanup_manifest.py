#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/transition_cleanup_manifest_current.json"
DEFAULT_OUT_CSV = "runs/transition_cleanup_manifest_current.csv"
DEFAULT_OUT_MD = "runs/transition_cleanup_manifest_current.md"

TARGET_SPECS = [
    {
        "path": "casp17/massivefold_external_pool_intake",
        "action": "externalize",
        "lane": "casp17_external_pool",
        "reason": "Large external model-pool intake should stay outside internal proof and source control.",
        "protection": "preserve_hash_listing_and_top_representatives",
    },
    {
        "path": "runs/archive",
        "action": "archive",
        "lane": "legacy_runs_archive",
        "reason": "Old run archive is useful only as cold evidence, not as active product state.",
        "protection": "keep_current_manifests_and_validation_reports",
    },
    {
        "path": "runs",
        "action": "review_for_stage2_traj_frames",
        "lane": "legacy_trajectory_frames",
        "reason": "Repeated trajectory frame folders can dominate disk without improving current product readiness.",
        "protection": "manifest_first_no_delete",
        "glob": "**/stage2_traj_frames*",
    },
    {
        "path": "rust_engine/target",
        "action": "delete_candidate",
        "lane": "build_output",
        "reason": "Rust build output can be regenerated from source.",
        "protection": "delete_only_after_operator_approval",
    },
    {
        "path": ".venv",
        "action": "delete_candidate",
        "lane": "local_environment",
        "reason": "Local virtual environment can be recreated from requirements files.",
        "protection": "delete_only_after_operator_approval",
    },
]

ACTION_EXECUTION_GUIDANCE = {
    "externalize": {
        "phase": "P1_externalize_after_snapshot",
        "approval_token": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
        "postcheck": "sha256/listing manifest present for externalized payload and source path not used by active tests",
    },
    "archive": {
        "phase": "P1_archive_after_snapshot",
        "approval_token": "APPROVE_ARCHIVE_LEGACY_RUNS",
        "postcheck": "archive manifest exists and current artifacts still resolve",
    },
    "delete_candidate": {
        "phase": "P2_delete_regenerable_only",
        "approval_token": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
        "postcheck": "source tree compiles and required tests still pass after removal",
    },
    "review_for_stage2_traj_frames": {
        "phase": "P0_review_only",
        "approval_token": "",
        "postcheck": "operator decides whether frames are archive evidence or delete candidates",
    },
    "review_for_ligand_heavy_payload_cleanup": {
        "phase": "P0_review_only",
        "approval_token": "",
        "postcheck": "run tools/cleanup_ligand_heavy_runs.py in dry-run mode for this root; delete only planned payload directories after explicit approval",
    },
}


def _resolve(path_like: str, root: Path = ROOT) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fast_dir_size(path: Path) -> int:
    try:
        output = subprocess.check_output(["du", "-sb", str(path)], text=True)
        return int(output.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def _summarize_path(path: Path, hash_files: bool, fast_size_only: bool = False) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "kind": "missing",
            "file_count": 0,
            "dir_count": 0,
            "size_bytes": 0,
            "sha256": "",
            "hash_strategy": "missing",
        }
    if path.is_file():
        return {
            "exists": True,
            "kind": "file",
            "file_count": 1,
            "dir_count": 0,
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path) if hash_files else "",
            "hash_strategy": "file_sha256" if hash_files else "size_only",
        }
    if fast_size_only and path.is_dir():
        return {
            "exists": True,
            "kind": "directory",
            "file_count": 0,
            "dir_count": 0,
            "size_bytes": _fast_dir_size(path),
            "sha256": "",
            "hash_strategy": "du_size_only_external_root",
        }
    file_count = 0
    dir_count = 0
    size_bytes = 0
    for child in path.rglob("*"):
        if child.is_dir():
            dir_count += 1
        elif child.is_file():
            file_count += 1
            try:
                size_bytes += child.stat().st_size
            except OSError:
                pass
    return {
        "exists": True,
        "kind": "directory",
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
        "sha256": "",
        "hash_strategy": "directory_size_file_count_only",
    }


def _row_for_path(spec: dict[str, Any], path: Path, root: Path, hash_files: bool) -> dict[str, Any]:
    summary = _summarize_path(path, hash_files, fast_size_only=bool(spec.get("fast_size_only", False)))
    rel_path = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    size_gb = round(float(summary["size_bytes"]) / (1024**3), 3)
    action = str(spec["action"])
    blocked = action in {"delete_candidate", "externalize", "archive"} and summary["exists"]
    guidance = ACTION_EXECUTION_GUIDANCE[action]
    return {
        "path": rel_path,
        "exists": summary["exists"],
        "kind": summary["kind"],
        "lane": spec["lane"],
        "recommended_action": action,
        "operator_approval_required": blocked,
        "file_count": summary["file_count"],
        "dir_count": summary["dir_count"],
        "size_bytes": summary["size_bytes"],
        "size_gb": size_gb,
        "sha256": summary["sha256"],
        "hash_strategy": summary["hash_strategy"],
        "protection": spec["protection"],
        "reason": spec["reason"],
        "execution_phase": guidance["phase"],
        "approval_token": guidance["approval_token"],
        "postcheck": guidance["postcheck"],
        "execution_status": "blocked_pending_operator_approval" if blocked else "dry_run_record_only",
        "config_reference_count": spec.get("config_reference_count", 0),
        "config_references": spec.get("config_references", ""),
    }


def _discover_config_ligand_heavy_roots(root: Path) -> list[dict[str, Any]]:
    config_dir = root / "config"
    if not config_dir.exists():
        return []
    roots_by_path: dict[str, set[str]] = {}
    for path in sorted(config_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        heavy_root = str(payload.get("heavy_artifacts_root") or "").strip()
        if not heavy_root:
            continue
        roots_by_path.setdefault(heavy_root, set()).add(str(path.relative_to(root)))
    rows: list[dict[str, Any]] = []
    for heavy_root, config_paths in sorted(roots_by_path.items()):
        rows.append(
            {
                "path": heavy_root,
                "action": "review_for_ligand_heavy_payload_cleanup",
                "lane": "ligand_heavy_runs_config_root",
                "reason": "Ligand HTVS configs reference this heavy-artifact root; inspect stale trajectory payloads before any deletion.",
                "protection": "run_cleanup_ligand_heavy_runs_dry_run_first",
                "fast_size_only": True,
                "config_reference_count": len(config_paths),
                "config_references": ",".join(sorted(config_paths)[:12]),
            }
        )
    return rows


def build_payload(root_dir: str = ".", hash_files: bool = False, include_config_ligand_heavy_roots: bool = True) -> dict[str, Any]:
    root = _resolve(root_dir, ROOT)
    rows: list[dict[str, Any]] = []
    specs = list(TARGET_SPECS)
    if include_config_ligand_heavy_roots:
        specs.extend(_discover_config_ligand_heavy_roots(root))
    for spec in specs:
        base = _resolve(str(spec["path"]), root)
        glob_pattern = spec.get("glob")
        if glob_pattern:
            matches = sorted(match for match in base.glob(str(glob_pattern)) if match.is_dir()) if base.exists() else []
            if not matches:
                rows.append(_row_for_path(spec, base / str(glob_pattern), root, hash_files))
            else:
                for match in matches:
                    rows.append(_row_for_path(spec, match, root, hash_files))
        else:
            rows.append(_row_for_path(spec, base, root, hash_files))
    present_rows = [row for row in rows if row["exists"]]
    approval_rows = [row for row in rows if row["operator_approval_required"]]
    reclaim_rows = [row for row in approval_rows if row["recommended_action"] in {"externalize", "archive", "delete_candidate"}]
    summary = {
        "status": "transition_cleanup_manifest_dry_run_ready",
        "root_dir": str(root),
        "row_count": len(rows),
        "present_row_count": len(present_rows),
        "operator_approval_required_count": len(approval_rows),
        "total_present_size_gb": round(sum(float(row["size_bytes"]) for row in present_rows) / (1024**3), 3),
        "approval_gated_reclaim_size_bytes": int(sum(int(row["size_bytes"]) for row in reclaim_rows)),
        "approval_gated_reclaim_size_gb": round(sum(float(row["size_bytes"]) for row in reclaim_rows) / (1024**3), 3),
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": (
            "Transition cleanup manifest only; it classifies heavy CASP17, ligand-heavy, legacy run, build, and local "
            "environment artifacts but does not delete, move, archive, upload, commit, or push anything."
        ),
        "next_required_step": "Review rows and provide explicit approval tokens before any archive/externalize/delete action.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transition Cleanup Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- root_dir: `{s['root_dir']}`",
        f"- row_count: `{s['row_count']}`",
        f"- present_row_count: `{s['present_row_count']}`",
        f"- operator_approval_required_count: `{s['operator_approval_required_count']}`",
        f"- total_present_size_gb: `{s['total_present_size_gb']}`",
        f"- approval_gated_reclaim_size_bytes: `{s['approval_gated_reclaim_size_bytes']}`",
        f"- approval_gated_reclaim_size_gb: `{s['approval_gated_reclaim_size_gb']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| path | action | phase | exists | size_gb | approval | token |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['recommended_action']}` | `{row['execution_phase']}` | "
            f"`{row['exists']}` | `{row['size_gb']}` | `{row['operator_approval_required']}` | "
            f"`{row['approval_token']}` |"
        )
    lines.extend(
        [
            "",
            "## Required Postchecks",
            "",
            "| path | postcheck |",
            "| --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"| `{row['path']}` | {row['postcheck']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dry-run transition cleanup manifest.")
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--hash-files", action="store_true")
    parser.add_argument("--skip-config-ligand-heavy-roots", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        args.root_dir,
        hash_files=args.hash_files,
        include_config_ligand_heavy_roots=not bool(args.skip_config_ligand_heavy_roots),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
