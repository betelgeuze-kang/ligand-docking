#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BM5_DATASET_DIR = "data/public_benchmarks/protein_protein_docking_benchmark_v5"
DEFAULT_CAPRI_SCORE_SET_DIR = "data/competition_benchmarks/capri_score_set"
DEFAULT_EXTERNAL_CUSTODY_ROOT = "OPERATOR_EXTERNAL_BM5_CAPRI_RAW_DATA_ROOT"
DEFAULT_OUT_JSON = "runs/bm5_capri_raw_data_custody_plan_current.json"
DEFAULT_OUT_CSV = "runs/bm5_capri_raw_data_custody_plan_current.csv"
DEFAULT_OUT_MD = "runs/bm5_capri_raw_data_custody_plan_current.md"
DEFAULT_OUT_CHECKSUMS = "runs/bm5_capri_raw_data_custody_plan_current.sha256"
DEFAULT_OUT_UNTRACK_CANDIDATES = "runs/bm5_capri_raw_data_untrack_candidates_current.txt"
DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE = (
    "runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt"
)
DEFAULT_OUT_REVIEW_GROUP_CSV = "runs/bm5_capri_raw_data_review_groups_current.csv"
DEFAULT_OUT_MATERIALIZATION_JSON = (
    "runs/bm5_capri_raw_data_materialization_manifest_current.json"
)
DEFAULT_OUT_MATERIALIZATION_MD = (
    "runs/bm5_capri_raw_data_materialization_manifest_current.md"
)
DEFAULT_APPROVED_UNTRACK_MANIFEST = "OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt"
UNTRACK_APPROVAL_TOKEN = "APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK"
UNTRACK_APPLY_PREVIEW_COMMAND = (
    "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
    f"--untrack-candidates {DEFAULT_APPROVED_UNTRACK_MANIFEST}"
)
UNTRACK_APPLY_EXECUTE_COMMAND = (
    "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
    f"--untrack-candidates {DEFAULT_APPROVED_UNTRACK_MANIFEST} "
    f"--approval-token {UNTRACK_APPROVAL_TOKEN}"
)

PACKET_TYPE = "bm5_capri_raw_data_custody_plan"
SCHEMA_VERSION = "bm5_capri_raw_data_custody_plan_v1"
RAW_DATA_SUFFIXES = {
    ".pdb",
    ".cif",
    ".mmcif",
    ".sdf",
    ".mol",
    ".mol2",
    ".pdbqt",
    ".mae",
    ".maegz",
    ".xtc",
    ".trr",
    ".dcd",
    ".nc",
    ".tar",
    ".gz",
    ".tgz",
    ".zip",
    ".xz",
}
ALLOWED_COMMITTED_FILENAMES = {
    "source_manifest.csv",
    "checksums.sha256",
    "materialization_manifest.json",
    "materialization_manifest.md",
}
CSV_FIELDS = [
    "raw_data_scope",
    "git_tracked_path",
    "file_suffix",
    "file_size_bytes",
    "sha256",
    "proposed_external_path",
    "operator_action_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]
REVIEW_GROUP_CSV_FIELDS = [
    "raw_data_scope",
    "review_group",
    "git_tracked_file_count",
    "total_file_size_bytes",
    "file_suffixes",
    "sample_git_tracked_paths",
    "proposed_external_directory",
    "operator_action_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]

CLAIM_BOUNDARY = (
    "BM5/CAPRI raw-data custody plan only; it inventories git-tracked raw benchmark files and emits a "
    "non-mutating operator evacuation plan. It does not move, delete, untrack, fetch, download, archive, "
    "score, submit, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nearest_existing_path(path: Path) -> Path:
    current = path if path.exists() else path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current if current.exists() else Path.cwd()


def _git_root(path: Path) -> Path | None:
    probe = _nearest_existing_path(path)
    try:
        result = subprocess.run(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return Path(text) if text else None


def _git_tracked_raw_files(path: Path, *, display_root: Path) -> list[str]:
    git_root = _git_root(path)
    if git_root is None:
        return []
    try:
        relative = path.resolve().relative_to(git_root.resolve())
    except (OSError, ValueError):
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "--", str(relative)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    tracked: list[str] = []
    for line in result.stdout.splitlines():
        tracked_path = Path(line.strip())
        if not str(tracked_path):
            continue
        if tracked_path.name in ALLOWED_COMMITTED_FILENAMES:
            continue
        if tracked_path.suffix.lower() in RAW_DATA_SUFFIXES:
            full_path = git_root / tracked_path
            tracked.append(_display(full_path, root=display_root))
    return sorted(tracked)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _plan_rows(
    *,
    tracked_paths: list[str],
    scope: str,
    external_custody_root: str,
    compute_sha256: bool,
    root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tracked_path in tracked_paths:
        repo_path = root / tracked_path
        rows.append(
            {
                "raw_data_scope": scope,
                "git_tracked_path": tracked_path,
                "file_suffix": Path(tracked_path).suffix.lower(),
                "file_size_bytes": _file_size(repo_path),
                "sha256": _sha256(repo_path) if compute_sha256 and repo_path.is_file() else "",
                "proposed_external_path": f"{external_custody_root.rstrip('/')}/{tracked_path}",
                "operator_action_required": True,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _review_group_for_path(tracked_path: str, *, scope: str) -> str:
    parts = Path(tracked_path).parts
    if scope == "bm5" and parts[:3] == (
        "data",
        "public_benchmarks",
        "protein_protein_docking_benchmark_v5",
    ):
        parts = parts[3:]
    if scope == "capri_score_set" and parts[:3] == (
        "data",
        "competition_benchmarks",
        "capri_score_set",
    ):
        parts = parts[3:]
    if len(parts) >= 2 and parts[0] == "HADDOCK-ready":
        return f"{parts[0]}/{parts[1]}"
    if len(parts) >= 2:
        return parts[0]
    return parts[0] if parts else "."


def _review_group_rows(rows: list[dict[str, Any]], *, external_custody_root: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        scope = _text(row.get("raw_data_scope"))
        review_group = _review_group_for_path(_text(row.get("git_tracked_path")), scope=scope)
        key = (scope, review_group)
        group = grouped.setdefault(
            key,
            {
                "raw_data_scope": scope,
                "review_group": review_group,
                "git_tracked_file_count": 0,
                "total_file_size_bytes": 0,
                "file_suffixes": [],
                "sample_git_tracked_paths": [],
                "proposed_external_directory": (
                    f"{external_custody_root.rstrip('/')}/{review_group}"
                    if review_group != "."
                    else external_custody_root.rstrip("/")
                ),
            },
        )
        group["git_tracked_file_count"] += 1
        group["total_file_size_bytes"] += int(row.get("file_size_bytes") or 0)
        suffix = _text(row.get("file_suffix"))
        if suffix:
            group["file_suffixes"].append(suffix)
        if len(group["sample_git_tracked_paths"]) < 5:
            group["sample_git_tracked_paths"].append(_text(row.get("git_tracked_path")))

    review_rows: list[dict[str, Any]] = []
    for group in sorted(
        grouped.values(),
        key=lambda item: (item["raw_data_scope"], item["review_group"]),
    ):
        group["file_suffixes"] = sorted(set(group["file_suffixes"]))
        group["operator_action_required"] = group["git_tracked_file_count"] > 0
        group["execution_enabled"] = False
        group["external_state_mutated"] = False
        group["claim_promotion_allowed"] = False
        group["claim_boundary"] = CLAIM_BOUNDARY
        review_rows.append(group)
    return review_rows


def build_bm5_capri_raw_data_custody_plan(
    *,
    bm5_dataset_dir: str | Path = DEFAULT_BM5_DATASET_DIR,
    capri_score_set_dir: str | Path = DEFAULT_CAPRI_SCORE_SET_DIR,
    external_custody_root: str = DEFAULT_EXTERNAL_CUSTODY_ROOT,
    compute_sha256: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    bm5_dir = _resolve(bm5_dataset_dir, root=root)
    capri_dir = _resolve(capri_score_set_dir, root=root)
    blockers: list[str] = []
    if _git_root(root) is None:
        blockers.append("git_root_unavailable")

    bm5_paths = _git_tracked_raw_files(bm5_dir, display_root=root)
    capri_paths = _git_tracked_raw_files(capri_dir, display_root=root)
    rows = [
        *_plan_rows(
            tracked_paths=bm5_paths,
            scope="bm5",
            external_custody_root=external_custody_root,
            compute_sha256=compute_sha256,
            root=root,
        ),
        *_plan_rows(
            tracked_paths=capri_paths,
            scope="capri_score_set",
            external_custody_root=external_custody_root,
            compute_sha256=compute_sha256,
            root=root,
        ),
    ]
    raw_data_git_tracked_file_count = len(rows)
    review_group_rows = _review_group_rows(rows, external_custody_root=external_custody_root)
    raw_data_custody_clear = raw_data_git_tracked_file_count == 0
    plan_ready = not blockers
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "bm5_capri_raw_data_custody_plan_ready"
        if plan_ready
        else "blocked_bm5_capri_raw_data_custody_plan",
        "custody_plan_ready": plan_ready,
        "raw_data_custody_clear": raw_data_custody_clear,
        "operator_action_required_count": raw_data_git_tracked_file_count,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "bm5_dataset_dir": _display(bm5_dir, root=root),
        "capri_score_set_dir": _display(capri_dir, root=root),
        "bm5_raw_data_git_tracked_file_count": len(bm5_paths),
        "capri_raw_data_git_tracked_file_count": len(capri_paths),
        "raw_data_git_tracked_file_count": raw_data_git_tracked_file_count,
        "raw_data_git_tracked_sample_paths": [row["git_tracked_path"] for row in rows[:10]],
        "raw_data_review_group_count": len(review_group_rows),
        "raw_data_primary_review_group": _text(
            review_group_rows[0].get("review_group") if review_group_rows else ""
        ),
        "raw_data_primary_review_group_file_count": int(
            review_group_rows[0].get("git_tracked_file_count") if review_group_rows else 0
        ),
        "external_custody_root": external_custody_root,
        "approved_untrack_manifest_template": DEFAULT_APPROVED_UNTRACK_MANIFEST,
        "approved_untrack_manifest_template_path": DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE,
        "approved_untrack_manifest_template_ready": raw_data_git_tracked_file_count > 0,
        "review_group_manifest_path": DEFAULT_OUT_REVIEW_GROUP_CSV,
        "review_group_manifest_ready": len(review_group_rows) > 0,
        "approved_untrack_command_template": (
            f"git rm --cached --pathspec-from-file {DEFAULT_APPROVED_UNTRACK_MANIFEST}"
        ),
        "untrack_approval_token_required": UNTRACK_APPROVAL_TOKEN,
        "untrack_apply_preview_command": UNTRACK_APPLY_PREVIEW_COMMAND,
        "untrack_apply_execute_command": UNTRACK_APPLY_EXECUTE_COMMAND,
        "sha256_computed": compute_sha256,
        "sha256_row_count": sum(1 for row in rows if _text(row.get("sha256"))),
        "checksum_manifest_path": DEFAULT_OUT_CHECKSUMS,
        "checksum_manifest_ready": bool(
            compute_sha256
            and raw_data_git_tracked_file_count > 0
            and sum(1 for row in rows if _text(row.get("sha256")))
            == raw_data_git_tracked_file_count
        ),
        "untrack_candidate_manifest_path": DEFAULT_OUT_UNTRACK_CANDIDATES,
        "untrack_candidate_manifest_ready": raw_data_git_tracked_file_count > 0,
        "untrack_candidate_count": raw_data_git_tracked_file_count,
        "operator_reviewed_untrack_manifest_required": raw_data_git_tracked_file_count > 0,
        "operator_reviewed_untrack_manifest_path": DEFAULT_APPROVED_UNTRACK_MANIFEST,
        "untrack_preview_mutates_git_index": False,
        "untrack_execute_mutates_git_index": raw_data_git_tracked_file_count > 0,
        "untrack_execute_requires_approval_token": raw_data_git_tracked_file_count > 0,
        "untrack_execute_requires_operator_reviewed_manifest": raw_data_git_tracked_file_count > 0,
        "untrack_execute_deletes_files": False,
        "untrack_execute_mutates_external_state": False,
        "materialization_manifest_json_path": DEFAULT_OUT_MATERIALIZATION_JSON,
        "materialization_manifest_md_path": DEFAULT_OUT_MATERIALIZATION_MD,
        "materialization_manifest_ready": bool(
            compute_sha256
            and raw_data_git_tracked_file_count > 0
            and sum(1 for row in rows if _text(row.get("sha256")))
            == raw_data_git_tracked_file_count
        ),
        "evacuation_command_template": (
            "Review this CSV, copy raw files to the proposed external custody root, "
            "then run git rm --cached for approved raw-data paths only after explicit human approval."
        ),
        "verification_command": (
            "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256 && "
            "python3 tools/build_bm5_capri_complex_source_manifest.py && "
            "python3 tools/build_competition_benchmark_custody_work_order.py"
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No git-tracked BM5/CAPRI raw data was found."
            if raw_data_custody_clear
            else "Move or untrack the listed raw files only after explicit human approval, keeping source/checksum/materialization receipts in repo."
        ),
    }
    return {"summary": summary, "rows": rows, "review_group_rows": review_group_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return _text(value)


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def _write_review_group_csv(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_GROUP_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["file_suffixes"] = ";".join(row.get("file_suffixes", []))
            csv_row["sample_git_tracked_paths"] = ";".join(
                row.get("sample_git_tracked_paths", [])
            )
            writer.writerow(
                {field: _csv_value(csv_row.get(field)) for field in REVIEW_GROUP_CSV_FIELDS}
            )


def _write_checksum_manifest(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{_text(row.get('sha256'))}  {_text(row.get('git_tracked_path'))}"
        for row in rows
        if _text(row.get("sha256")) and _text(row.get("git_tracked_path"))
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_untrack_candidates(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _text(row.get("git_tracked_path"))
        for row in rows
        if _text(row.get("git_tracked_path"))
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_approved_untrack_template(
    path_like: str | Path,
    rows: list[dict[str, Any]],
    *,
    root: Path = ROOT,
) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate_paths = [
        _text(row.get("git_tracked_path"))
        for row in rows
        if _text(row.get("git_tracked_path"))
    ]
    lines = [
        "# BM5/CAPRI reviewed raw-data untrack manifest template.",
        "# Operator review is required before using this file with the approval token.",
        "# Remove any path that should remain tracked; do not add paths outside BM5/CAPRI raw-data roots.",
        "# Copy the reviewed result to OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt.",
        "",
        *candidate_paths,
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _materialization_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {
        "summary": {
            "packet_type": "bm5_capri_raw_data_materialization_manifest",
            "schema_version": "bm5_capri_raw_data_materialization_manifest_v1",
            "status": "bm5_capri_raw_data_materialization_manifest_ready"
            if summary["materialization_manifest_ready"]
            else "blocked_bm5_capri_raw_data_materialization_manifest",
            "materialization_manifest_ready": summary["materialization_manifest_ready"],
            "checksum_manifest_ready": summary["checksum_manifest_ready"],
            "checksum_manifest_path": summary["checksum_manifest_path"],
            "untrack_candidate_manifest_ready": summary[
                "untrack_candidate_manifest_ready"
            ],
            "untrack_candidate_manifest_path": summary[
                "untrack_candidate_manifest_path"
            ],
            "approved_untrack_manifest_template_path": summary[
                "approved_untrack_manifest_template_path"
            ],
            "approved_untrack_manifest_template_ready": summary[
                "approved_untrack_manifest_template_ready"
            ],
            "operator_reviewed_untrack_manifest_required": summary[
                "operator_reviewed_untrack_manifest_required"
            ],
            "operator_reviewed_untrack_manifest_path": summary[
                "operator_reviewed_untrack_manifest_path"
            ],
            "untrack_preview_mutates_git_index": summary[
                "untrack_preview_mutates_git_index"
            ],
            "untrack_execute_mutates_git_index": summary[
                "untrack_execute_mutates_git_index"
            ],
            "untrack_execute_requires_approval_token": summary[
                "untrack_execute_requires_approval_token"
            ],
            "untrack_execute_requires_operator_reviewed_manifest": summary[
                "untrack_execute_requires_operator_reviewed_manifest"
            ],
            "untrack_execute_deletes_files": summary["untrack_execute_deletes_files"],
            "untrack_execute_mutates_external_state": summary[
                "untrack_execute_mutates_external_state"
            ],
            "review_group_manifest_path": summary["review_group_manifest_path"],
            "review_group_manifest_ready": summary["review_group_manifest_ready"],
            "raw_data_git_tracked_file_count": summary[
                "raw_data_git_tracked_file_count"
            ],
            "raw_data_custody_clear": summary["raw_data_custody_clear"],
            "external_custody_root": summary["external_custody_root"],
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": summary["next_required_step"],
        },
        "rows": [
            {
                "raw_data_scope": row["raw_data_scope"],
                "git_tracked_path": row["git_tracked_path"],
                "file_size_bytes": row["file_size_bytes"],
                "sha256": row["sha256"],
                "proposed_external_path": row["proposed_external_path"],
                "operator_action_required": row["operator_action_required"],
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
            for row in payload["rows"]
        ],
    }


def _render_materialization_md(payload: dict[str, Any]) -> str:
    materialization = _materialization_payload(payload)
    summary = materialization["summary"]
    lines = [
        "# BM5/CAPRI Raw-Data Materialization Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- materialization_manifest_ready: `{summary['materialization_manifest_ready']}`",
        f"- checksum_manifest_ready: `{summary['checksum_manifest_ready']}`",
        f"- checksum_manifest_path: `{summary['checksum_manifest_path']}`",
        f"- untrack_candidate_manifest_ready: `{summary['untrack_candidate_manifest_ready']}`",
        f"- untrack_candidate_manifest_path: `{summary['untrack_candidate_manifest_path']}`",
        f"- approved_untrack_manifest_template_ready: `{summary['approved_untrack_manifest_template_ready']}`",
        f"- approved_untrack_manifest_template_path: `{summary['approved_untrack_manifest_template_path']}`",
        f"- operator_reviewed_untrack_manifest_required: `{summary['operator_reviewed_untrack_manifest_required']}`",
        f"- operator_reviewed_untrack_manifest_path: `{summary['operator_reviewed_untrack_manifest_path']}`",
        f"- untrack_preview_mutates_git_index: `{summary['untrack_preview_mutates_git_index']}`",
        f"- untrack_execute_mutates_git_index: `{summary['untrack_execute_mutates_git_index']}`",
        f"- untrack_execute_requires_approval_token: `{summary['untrack_execute_requires_approval_token']}`",
        f"- untrack_execute_requires_operator_reviewed_manifest: `{summary['untrack_execute_requires_operator_reviewed_manifest']}`",
        f"- untrack_execute_deletes_files: `{summary['untrack_execute_deletes_files']}`",
        f"- untrack_execute_mutates_external_state: `{summary['untrack_execute_mutates_external_state']}`",
        f"- review_group_manifest_ready: `{summary['review_group_manifest_ready']}`",
        f"- review_group_manifest_path: `{summary['review_group_manifest_path']}`",
        f"- raw_data_git_tracked_file_count: `{summary['raw_data_git_tracked_file_count']}`",
        f"- raw_data_custody_clear: `{summary['raw_data_custody_clear']}`",
        f"- external_custody_root: `{summary['external_custody_root']}`",
        "",
        "| scope | git tracked path | proposed external path | sha256 |",
        "| --- | --- | --- | --- |",
    ]
    for row in materialization["rows"][:50]:
        lines.append(
            f"| `{row['raw_data_scope']}` | `{row['git_tracked_path']}` | "
            f"`{row['proposed_external_path']}` | `{row['sha256'] or '-'}` |"
        )
    if len(materialization["rows"]) > 50:
        lines.append(
            f"| `...` | `{len(materialization['rows']) - 50} more rows in JSON` | `...` | `...` |"
        )
    if not materialization["rows"]:
        lines.append("| - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# BM5/CAPRI Raw-Data Custody Plan",
        "",
        f"- status: `{summary['status']}`",
        f"- custody_plan_ready: `{summary['custody_plan_ready']}`",
        f"- raw_data_custody_clear: `{summary['raw_data_custody_clear']}`",
        f"- raw_data_git_tracked_file_count: `{summary['raw_data_git_tracked_file_count']}`",
        f"- raw_data_review_group_count: `{summary['raw_data_review_group_count']}`",
        f"- raw_data_primary_review_group: `{summary['raw_data_primary_review_group']}`",
        f"- raw_data_primary_review_group_file_count: `{summary['raw_data_primary_review_group_file_count']}`",
        f"- bm5_raw_data_git_tracked_file_count: `{summary['bm5_raw_data_git_tracked_file_count']}`",
        f"- capri_raw_data_git_tracked_file_count: `{summary['capri_raw_data_git_tracked_file_count']}`",
        f"- sha256_computed: `{summary['sha256_computed']}`",
        f"- checksum_manifest_ready: `{summary['checksum_manifest_ready']}`",
        f"- checksum_manifest_path: `{summary['checksum_manifest_path']}`",
        f"- untrack_candidate_manifest_ready: `{summary['untrack_candidate_manifest_ready']}`",
        f"- untrack_candidate_manifest_path: `{summary['untrack_candidate_manifest_path']}`",
        f"- approved_untrack_manifest_template_ready: `{summary['approved_untrack_manifest_template_ready']}`",
        f"- approved_untrack_manifest_template_path: `{summary['approved_untrack_manifest_template_path']}`",
        f"- operator_reviewed_untrack_manifest_required: `{summary['operator_reviewed_untrack_manifest_required']}`",
        f"- operator_reviewed_untrack_manifest_path: `{summary['operator_reviewed_untrack_manifest_path']}`",
        f"- review_group_manifest_ready: `{summary['review_group_manifest_ready']}`",
        f"- review_group_manifest_path: `{summary['review_group_manifest_path']}`",
        f"- materialization_manifest_ready: `{summary['materialization_manifest_ready']}`",
        f"- materialization_manifest_json_path: `{summary['materialization_manifest_json_path']}`",
        f"- approved_untrack_manifest_template: `{summary['approved_untrack_manifest_template']}`",
        f"- approved_untrack_command_template: `{summary['approved_untrack_command_template']}`",
        f"- untrack_approval_token_required: `{summary['untrack_approval_token_required']}`",
        f"- untrack_apply_preview_command: `{summary['untrack_apply_preview_command']}`",
        f"- untrack_apply_execute_command: `{summary['untrack_apply_execute_command']}`",
        f"- untrack_preview_mutates_git_index: `{summary['untrack_preview_mutates_git_index']}`",
        f"- untrack_execute_mutates_git_index: `{summary['untrack_execute_mutates_git_index']}`",
        f"- untrack_execute_requires_approval_token: `{summary['untrack_execute_requires_approval_token']}`",
        f"- untrack_execute_requires_operator_reviewed_manifest: `{summary['untrack_execute_requires_operator_reviewed_manifest']}`",
        f"- untrack_execute_deletes_files: `{summary['untrack_execute_deletes_files']}`",
        f"- untrack_execute_mutates_external_state: `{summary['untrack_execute_mutates_external_state']}`",
        "",
        "## Review Groups",
        "",
        "| scope | review group | file count | suffixes | proposed external directory | samples |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("review_group_rows", [])[:50]:
        suffixes = ";".join(row.get("file_suffixes", [])) or "-"
        samples = ";".join(row.get("sample_git_tracked_paths", [])) or "-"
        lines.append(
            f"| `{row['raw_data_scope']}` | `{row['review_group']}` | "
            f"`{row['git_tracked_file_count']}` | `{suffixes}` | "
            f"`{row['proposed_external_directory']}` | `{samples}` |"
        )
    review_group_rows = payload.get("review_group_rows", [])
    if len(review_group_rows) > 50:
        lines.append(
            f"| `...` | `{len(review_group_rows) - 50} more review groups in JSON` | `...` | `...` | `...` | `...` |"
        )
    if not review_group_rows:
        lines.append("| - | - | `0` | - | - | - |")
    lines.extend(
        [
            "",
            "## File Rows",
            "",
        ]
    )
    lines.extend(
        [
        "| scope | git tracked path | proposed external path | sha256 |",
        "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"][:50]:
        sha = _text(row.get("sha256")) or "-"
        lines.append(
            f"| `{row['raw_data_scope']}` | `{row['git_tracked_path']}` | "
            f"`{row['proposed_external_path']}` | `{sha}` |"
        )
    if len(payload["rows"]) > 50:
        lines.append(f"| `...` | `{len(payload['rows']) - 50} more rows in CSV` | `...` | `...` |")
    if not payload["rows"]:
        lines.append("| - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a non-mutating BM5/CAPRI raw-data custody plan.")
    parser.add_argument("--bm5-dataset-dir", default=DEFAULT_BM5_DATASET_DIR)
    parser.add_argument("--capri-score-set-dir", default=DEFAULT_CAPRI_SCORE_SET_DIR)
    parser.add_argument("--external-custody-root", default=DEFAULT_EXTERNAL_CUSTODY_ROOT)
    parser.add_argument("--compute-sha256", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-checksums", default=DEFAULT_OUT_CHECKSUMS)
    parser.add_argument("--out-untrack-candidates", default=DEFAULT_OUT_UNTRACK_CANDIDATES)
    parser.add_argument(
        "--out-approved-untrack-template",
        default=DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE,
    )
    parser.add_argument("--out-review-group-csv", default=DEFAULT_OUT_REVIEW_GROUP_CSV)
    parser.add_argument("--out-materialization-json", default=DEFAULT_OUT_MATERIALIZATION_JSON)
    parser.add_argument("--out-materialization-md", default=DEFAULT_OUT_MATERIALIZATION_MD)
    args = parser.parse_args(argv)
    payload = build_bm5_capri_raw_data_custody_plan(
        bm5_dataset_dir=args.bm5_dataset_dir,
        capri_score_set_dir=args.capri_score_set_dir,
        external_custody_root=args.external_custody_root,
        compute_sha256=args.compute_sha256,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    _write_checksum_manifest(args.out_checksums, payload["rows"])
    _write_untrack_candidates(args.out_untrack_candidates, payload["rows"])
    _write_approved_untrack_template(args.out_approved_untrack_template, payload["rows"])
    _write_review_group_csv(args.out_review_group_csv, payload["review_group_rows"])
    _write_json(args.out_materialization_json, _materialization_payload(payload))
    _write_text(args.out_materialization_md, _render_materialization_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
