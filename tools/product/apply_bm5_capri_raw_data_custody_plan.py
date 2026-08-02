#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.product.build_bm5_capri_raw_data_custody_plan import (
    CLAIM_BOUNDARY as CUSTODY_PLAN_CLAIM_BOUNDARY,
    DEFAULT_APPROVED_UNTRACK_MANIFEST,
    DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE,
    DEFAULT_OUT_JSON as DEFAULT_PLAN_JSON,
    DEFAULT_OUT_UNTRACK_CANDIDATES,
    UNTRACK_APPROVAL_TOKEN,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/bm5_capri_raw_data_untrack_apply_preflight_current.json"
DEFAULT_OUT_MD = "runs/bm5_capri_raw_data_untrack_apply_preflight_current.md"
PACKET_TYPE = "bm5_capri_raw_data_untrack_apply_preflight"
SCHEMA_VERSION = "bm5_capri_raw_data_untrack_apply_preflight_v1"
ALLOWED_RAW_DATA_ROOTS = (
    "data/public_benchmarks/protein_protein_docking_benchmark_v5",
    "data/competition_benchmarks/capri_score_set",
)
CLAIM_BOUNDARY = (
    "BM5/CAPRI raw-data untrack apply receipt only; preview is non-mutating, and execute "
    "requires an explicit approval token plus an operator-reviewed untrack manifest. "
    "Execute runs git rm --cached against reviewed raw-data paths only. It does not delete "
    "files, fetch data, move data, score, submit, commit, push, or mutate external state."
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


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    return json.loads(path.read_text(encoding="utf-8")), True


def _read_lines(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], False
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return lines, True


def _nearest_existing_path(path: Path) -> Path:
    current = path if path.exists() else path.parent
    if current.is_file():
        current = current.parent
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
    output = result.stdout.strip()
    return Path(output) if output else None


def _git_tracked(git_root: Path, rel_path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "--error-unmatch", "--", str(rel_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _path_allowed(path: str) -> bool:
    normalized = Path(path).as_posix()
    return any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in ALLOWED_RAW_DATA_ROOTS
    )


def _plan_paths(plan: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for row in plan.get("rows") or []:
        path = _text(row.get("git_tracked_path"))
        if path:
            paths.add(path)
    return paths


def _group_candidates_by_git_root(
    candidates: list[str],
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for candidate in candidates:
        candidate_path = _resolve(candidate, root=root)
        row: dict[str, Any] = {
            "git_tracked_path": candidate,
            "path_allowed": _path_allowed(candidate),
            "file_exists": candidate_path.exists(),
            "git_root": "",
            "git_root_display": "",
            "pathspec": "",
            "git_tracked": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "file_delete_requested": False,
        }
        if not row["path_allowed"]:
            blockers.append(f"path_outside_allowed_roots:{candidate}")
        if not row["file_exists"]:
            blockers.append(f"candidate_missing_on_disk:{candidate}")
        git_root = _git_root(candidate_path)
        if git_root is None:
            blockers.append(f"git_root_unavailable:{candidate}")
        else:
            try:
                rel_path = candidate_path.resolve().relative_to(git_root.resolve())
            except (OSError, ValueError):
                blockers.append(f"path_not_relative_to_git_root:{candidate}")
            else:
                row["git_root"] = str(git_root)
                row["git_root_display"] = _display(git_root, root=root)
                row["pathspec"] = str(rel_path)
                row["git_tracked"] = _git_tracked(git_root, rel_path)
                if not row["git_tracked"]:
                    blockers.append(f"candidate_not_git_tracked:{candidate}")
        rows.append(row)
    return rows, blockers


def _run_git_rm_cached(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("git_root")), []).append(_text(row.get("pathspec")))

    command_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for git_root, pathspecs in sorted(grouped.items()):
        if not git_root:
            continue
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            for pathspec in pathspecs:
                handle.write(f"{pathspec}\n")
            pathspec_file = Path(handle.name)
        try:
            command = [
                "git",
                "-C",
                git_root,
                "rm",
                "--cached",
                "--pathspec-from-file",
                str(pathspec_file),
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
        finally:
            pathspec_file.unlink(missing_ok=True)
        command_rows.append(
            {
                "git_root": git_root,
                "candidate_count": len(pathspecs),
                "command": "git -C <git_root> rm --cached --pathspec-from-file <reviewed-pathspec-file>",
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
        if result.returncode != 0:
            blockers.append(f"git_rm_cached_failed:{git_root}:{result.returncode}")
    return command_rows, blockers


def build_bm5_capri_raw_data_untrack_apply(
    *,
    plan_json: str | Path = DEFAULT_PLAN_JSON,
    untrack_candidates: str | Path = DEFAULT_OUT_UNTRACK_CANDIDATES,
    mode: str = "preview",
    approval_token: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    plan, plan_present = _read_json(plan_json, root=root)
    candidates, candidates_present = _read_lines(untrack_candidates, root=root)
    blockers: list[str] = []
    if mode not in {"preview", "execute"}:
        blockers.append(f"unsupported_mode:{mode}")
    if not plan_present:
        blockers.append("custody_plan_missing")
    if not candidates_present:
        blockers.append("untrack_candidate_manifest_missing")

    candidate_manifest_display = _display(untrack_candidates, root=root)
    operator_reviewed_manifest_used = (
        candidate_manifest_display == DEFAULT_APPROVED_UNTRACK_MANIFEST
    )
    generated_untrack_candidate_manifest_used = (
        candidate_manifest_display == DEFAULT_OUT_UNTRACK_CANDIDATES
    )
    reviewed_untrack_template_manifest_used = (
        candidate_manifest_display == DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE
    )
    if mode == "execute" and not operator_reviewed_manifest_used:
        blockers.append("operator_reviewed_untrack_manifest_not_used")

    candidate_set = set(candidates)
    duplicate_count = len(candidates) - len(candidate_set)
    if duplicate_count:
        blockers.append("duplicate_untrack_candidates")

    plan_paths = _plan_paths(plan)
    manifest_matches_plan = bool(plan_present and candidates_present and candidate_set == plan_paths)
    if plan_present and candidates_present and candidate_set != plan_paths:
        blockers.append("untrack_candidates_do_not_match_custody_plan")

    rows, row_blockers = _group_candidates_by_git_root(sorted(candidate_set), root=root)
    blockers.extend(row_blockers)

    approval_token_valid = approval_token == UNTRACK_APPROVAL_TOKEN
    if mode == "execute" and not approval_token_valid:
        blockers.append("approval_token_missing_or_invalid")

    command_rows: list[dict[str, Any]] = []
    pre_execute_blocker_count = len(blockers)
    local_git_index_mutated = False
    if mode == "execute" and approval_token_valid and pre_execute_blocker_count == 0:
        command_rows, execute_blockers = _run_git_rm_cached(rows)
        blockers.extend(execute_blockers)
        local_git_index_mutated = not execute_blockers

    apply_ready = len(blockers) == 0
    status = (
        "bm5_capri_raw_data_untrack_apply_executed"
        if mode == "execute" and apply_ready
        else "bm5_capri_raw_data_untrack_apply_preflight_ready"
        if mode == "preview" and apply_ready
        else "blocked_bm5_capri_raw_data_untrack_apply"
    )
    git_root_count = len({_text(row.get("git_root")) for row in rows if _text(row.get("git_root"))})
    execute_would_mutate_git_index = bool(
        mode == "execute" and approval_token_valid and pre_execute_blocker_count == 0
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "apply_ready": apply_ready,
        "preview_ready": bool(mode == "preview" and apply_ready),
        "execute_ready": bool(mode == "execute" and apply_ready),
        "approval_token_required": UNTRACK_APPROVAL_TOKEN,
        "approval_token_valid": approval_token_valid,
        "custody_plan_path": _display(plan_json, root=root),
        "custody_plan_present": plan_present,
        "untrack_candidate_manifest_path": candidate_manifest_display,
        "generated_untrack_candidate_manifest_path": DEFAULT_OUT_UNTRACK_CANDIDATES,
        "untrack_candidate_manifest_present": candidates_present,
        "candidate_manifest_required_for_execute": True,
        "candidate_manifest_operator_review_required": True,
        "operator_reviewed_manifest_used": operator_reviewed_manifest_used,
        "generated_untrack_candidate_manifest_used": generated_untrack_candidate_manifest_used,
        "reviewed_untrack_template_manifest_used": reviewed_untrack_template_manifest_used,
        "operator_reviewed_untrack_manifest_required": True,
        "operator_reviewed_untrack_manifest_path": DEFAULT_APPROVED_UNTRACK_MANIFEST,
        "reviewed_untrack_manifest_template_path": DEFAULT_OUT_APPROVED_UNTRACK_TEMPLATE,
        "reviewed_untrack_manifest_template_ready": len(plan_paths) > 0,
        "operator_review_handoff": (
            "Review runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt, "
            "remove any path that must remain tracked, copy the reviewed result to "
            f"{DEFAULT_APPROVED_UNTRACK_MANIFEST}, then run preview before execute."
        ),
        "untrack_candidate_count": len(candidates),
        "unique_untrack_candidate_count": len(candidate_set),
        "duplicate_untrack_candidate_count": duplicate_count,
        "custody_plan_raw_data_path_count": len(plan_paths),
        "untrack_candidates_match_custody_plan": manifest_matches_plan,
        "allowed_raw_data_root_count": len(ALLOWED_RAW_DATA_ROOTS),
        "git_root_count": git_root_count,
        "tracked_candidate_count": sum(1 for row in rows if row.get("git_tracked") is True),
        "missing_candidate_count": sum(1 for row in rows if row.get("file_exists") is not True),
        "path_outside_allowed_roots_count": sum(1 for row in rows if row.get("path_allowed") is not True),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "local_git_index_mutated": local_git_index_mutated,
        "preview_mutates_git_index": False,
        "execute_mutates_git_index": True,
        "execute_would_mutate_git_index": execute_would_mutate_git_index,
        "execute_requires_approval_token": True,
        "execute_requires_operator_reviewed_manifest": True,
        "file_delete_requested": False,
        "execute_deletes_files": False,
        "external_state_mutated": False,
        "execute_mutates_external_state": False,
        "execution_enabled": bool(mode == "execute" and approval_token_valid and pre_execute_blocker_count == 0),
        "claim_promotion_allowed": False,
        "preview_command": (
            "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview "
            f"--untrack-candidates {DEFAULT_APPROVED_UNTRACK_MANIFEST}"
        ),
        "execute_command": (
            "python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute "
            f"--untrack-candidates {DEFAULT_APPROVED_UNTRACK_MANIFEST} "
            f"--approval-token {UNTRACK_APPROVAL_TOKEN}"
        ),
        "post_execute_verification_command": (
            "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256"
        ),
        "claim_boundary": f"{CLAIM_BOUNDARY} {CUSTODY_PLAN_CLAIM_BOUNDARY}",
        "next_required_step": (
            "Review the preflight receipt, then execute with the approval token if raw-data paths "
            "have already been externally materialized and reviewed."
            if mode == "preview" and apply_ready
            else "Rerun the custody plan after execute and require raw_data_git_tracked_file_count=0."
            if mode == "execute" and apply_ready
            else "Resolve blockers before untracking BM5/CAPRI raw data."
        ),
    }
    return {"summary": summary, "rows": rows, "command_rows": command_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# BM5/CAPRI Raw-Data Untrack Apply Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- apply_ready: `{summary['apply_ready']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- generated_untrack_candidate_manifest_path: `{summary['generated_untrack_candidate_manifest_path']}`",
        f"- reviewed_untrack_manifest_template_path: `{summary['reviewed_untrack_manifest_template_path']}`",
        f"- operator_reviewed_untrack_manifest_path: `{summary['operator_reviewed_untrack_manifest_path']}`",
        f"- untrack_candidate_count: `{summary['untrack_candidate_count']}`",
        f"- tracked_candidate_count: `{summary['tracked_candidate_count']}`",
        f"- untrack_candidates_match_custody_plan: `{summary['untrack_candidates_match_custody_plan']}`",
        f"- candidate_manifest_required_for_execute: `{summary['candidate_manifest_required_for_execute']}`",
        f"- candidate_manifest_operator_review_required: `{summary['candidate_manifest_operator_review_required']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- local_git_index_mutated: `{summary['local_git_index_mutated']}`",
        f"- preview_mutates_git_index: `{summary['preview_mutates_git_index']}`",
        f"- execute_mutates_git_index: `{summary['execute_mutates_git_index']}`",
        f"- execute_would_mutate_git_index: `{summary['execute_would_mutate_git_index']}`",
        f"- execute_requires_approval_token: `{summary['execute_requires_approval_token']}`",
        f"- execute_requires_operator_reviewed_manifest: `{summary['execute_requires_operator_reviewed_manifest']}`",
        f"- file_delete_requested: `{summary['file_delete_requested']}`",
        f"- execute_deletes_files: `{summary['execute_deletes_files']}`",
        f"- external_state_mutated: `{summary['external_state_mutated']}`",
        f"- execute_mutates_external_state: `{summary['execute_mutates_external_state']}`",
        "",
        "## Candidate Groups",
        "",
        "| git root | candidate count |",
        "| --- | ---: |",
    ]
    counts: dict[str, int] = {}
    for row in payload["rows"]:
        counts[_text(row.get("git_root_display")) or _text(row.get("git_root")) or "-"] = (
            counts.get(_text(row.get("git_root_display")) or _text(row.get("git_root")) or "-", 0) + 1
        )
    for git_root, count in sorted(counts.items()):
        lines.append(f"| `{git_root}` | `{count}` |")
    if not counts:
        lines.append("| - | `0` |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or execute approval-gated BM5/CAPRI raw-data git untracking."
    )
    parser.add_argument("--plan-json", default=DEFAULT_PLAN_JSON)
    parser.add_argument("--untrack-candidates", default=DEFAULT_OUT_UNTRACK_CANDIDATES)
    parser.add_argument("--mode", choices=["preview", "execute"], default="preview")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_bm5_capri_raw_data_untrack_apply(
        plan_json=args.plan_json,
        untrack_candidates=args.untrack_candidates,
        mode=args.mode,
        approval_token=args.approval_token,
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
