#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AI_VERIFY_LOG = ".betelgeuze/developer_preview_clean_checkout_ai_verify.log"
DEFAULT_BASELINE_SUMMARY_JSON = (
    ".betelgeuze/developer_preview_external_baselines/"
    "biorxiv_baseline_comparison_developer_preview_clean_checkout/summary.json"
)
DEFAULT_CHECKOUT_PROVENANCE_JSON = (
    ".betelgeuze/developer_preview_clean_checkout_source_provenance.json"
)
DEFAULT_OUT_JSON = ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
DEFAULT_OUT_MD = ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md"
DEFAULT_STAGE5_INPUT_FAMILY_CSV = (
    ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
)
DEFAULT_STAGE5_INPUT_FAMILY_MD = (
    ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.md"
)

PACKET_TYPE = "developer_preview_clean_checkout_benchmark_receipt"
SCHEMA_VERSION = "developer_preview_clean_checkout_benchmark_receipt_v1"
STAGE5_REQUIRED_ARGUMENTS = [
    "--scores-csv",
    "--labels-csv",
    "--split-csv",
    "--expected-keys-csv",
]
STAGE5_INPUT_FAMILY_CSV_FIELDS = [
    "set_id",
    "task_id",
    "task_key",
    "domain",
    "kind",
    "source_argument",
    "source_artifact_path",
    "source_artifact_present",
    "source_artifact_missing",
    "pipeline_summary_json",
    "pipeline_summary_present",
    "profile_json",
    "required_action",
    "operator_action_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]

CLAIM_BOUNDARY = (
    "Developer Preview clean-checkout benchmark receipt only; it reads local ai-verify output and "
    "the external-validation baseline summary emitted from a fresh checkout, then fails closed when "
    "sources are missing, empty, unreviewed, or structurally incomplete. It does not clone repos, "
    "install dependencies, run benchmarks, approve claims, upload, email, deploy, commit, push, or "
    "mutate external state."
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


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _ai_verify_passed(log_text: str) -> bool:
    lower = log_text.lower()
    return "verify ok" in lower and "traceback" not in lower and "failed" not in lower


def _csv_row_count(path_like: str | Path, *, root: Path) -> int:
    path = _resolve(path_like, root=root)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return max(0, sum(1 for _ in csv.DictReader(handle)))
    except OSError:
        return 0


def _artifact_exists(path_like: Any, *, root: Path) -> bool:
    text = _text(path_like)
    if not text:
        return False
    return _resolve(text, root=root).is_file()


def _get_flag(cmd: list[Any], flag: str) -> str:
    for i, token in enumerate(cmd):
        if str(token) == flag and i + 1 < len(cmd):
            return _text(cmd[i + 1])
    return ""


def _stage5_task_key(source_artifact_path: str) -> str:
    if not source_artifact_path:
        return ""
    stem = Path(source_artifact_path).stem
    for suffix in ("_stage4_calibration_scores", "_stage3_scores"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _source_argument_from_blocker(blocker: str) -> str:
    parts = _text(blocker).split(":", 2)
    if len(parts) > 1 and parts[1].startswith("--"):
        return parts[1]
    return ""


def _source_path_from_blocker(blocker: str) -> str:
    parts = _text(blocker).split(":", 2)
    if len(parts) == 3 and parts[1].startswith("--"):
        return parts[2]
    return ""


def _stage5_cmd_from_pipeline(path_like: str, *, root: Path) -> list[Any]:
    payload = _read_json(path_like, root=root)
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    stage5 = (
        stages.get("stage5_ranking_eval")
        if isinstance(stages.get("stage5_ranking_eval"), dict)
        else {}
    )
    cmd = stage5.get("cmd")
    return list(cmd) if isinstance(cmd, list) else []


def _stage5_input_family_rows(
    payload: dict[str, Any],
    *,
    root: Path,
) -> list[dict[str, Any]]:
    summary = _summary(payload)
    task_source_errors = (
        summary.get("task_source_errors")
        if isinstance(summary.get("task_source_errors"), list)
        else []
    )
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for error_row in task_source_errors:
        if not isinstance(error_row, dict):
            continue
        blocker = _text(error_row.get("blocker") or error_row.get("source_error"))
        if not blocker.startswith("stage5_input_missing:"):
            continue
        missing_argument = _source_argument_from_blocker(blocker)
        missing_path = _source_path_from_blocker(blocker)
        pipeline_summary_json = _text(error_row.get("pipeline_summary_json"))
        stage5_cmd = _stage5_cmd_from_pipeline(pipeline_summary_json, root=root)
        task_key = _stage5_task_key(missing_path) or _text(error_row.get("task_id"))
        for argument in STAGE5_REQUIRED_ARGUMENTS:
            source_path = _get_flag(stage5_cmd, argument)
            if not source_path and argument == missing_argument:
                source_path = missing_path
            if not source_path:
                source_path = f"{_text(error_row.get('task_id'))}:{argument}:flag_missing"
            display_path = _display(source_path, root=root)
            key = (task_key, argument, display_path)
            if key in seen:
                continue
            seen.add(key)
            present = _resolve(source_path, root=root).is_file() if source_path else False
            missing = not present
            rows.append(
                {
                    "set_id": _text(error_row.get("set_id")),
                    "task_id": _text(error_row.get("task_id")),
                    "task_key": task_key,
                    "domain": _text(error_row.get("domain")),
                    "kind": _text(error_row.get("kind")),
                    "profile_json": _display(_text(error_row.get("profile_json")), root=root),
                    "pipeline_summary_json": _display(pipeline_summary_json, root=root),
                    "pipeline_summary_present": _artifact_exists(
                        pipeline_summary_json,
                        root=root,
                    ),
                    "pipeline_summary_resolution_source": _text(
                        error_row.get("pipeline_summary_resolution_source")
                    ),
                    "source_error_type": _text(error_row.get("source_error_type")),
                    "source_error": _text(error_row.get("source_error")),
                    "source_error_blocker": blocker,
                    "source_argument": argument,
                    "source_artifact_path": display_path,
                    "source_artifact_present": present,
                    "source_artifact_missing": missing,
                    "required_action": (
                        "Restore or regenerate this clean-checkout stage5 input CSV, then "
                        "rebuild the baseline summary and reviewed receipt."
                    )
                    if missing
                    else "Keep this stage5 input CSV with the clean-checkout baseline family.",
                    "operator_action_required": missing,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                    "claim_promotion_allowed": False,
                    "claim_boundary": CLAIM_BOUNDARY,
                }
            )

    if rows:
        return rows

    blockers = (
        [_text(item) for item in summary.get("blockers", []) if _text(item)]
        if isinstance(summary.get("blockers"), list)
        else []
    )
    for blocker in blockers:
        if not blocker.startswith("stage5_input_missing:"):
            continue
        argument = _source_argument_from_blocker(blocker)
        source_path = _source_path_from_blocker(blocker)
        display_path = _display(source_path, root=root)
        present = _resolve(source_path, root=root).is_file() if source_path else False
        rows.append(
            {
                "set_id": "",
                "task_id": "",
                "task_key": _stage5_task_key(source_path),
                "domain": "",
                "kind": "",
                "profile_json": "",
                "pipeline_summary_json": "",
                "pipeline_summary_present": False,
                "pipeline_summary_resolution_source": "",
                "source_error_type": "",
                "source_error": blocker,
                "source_error_blocker": blocker,
                "source_argument": argument,
                "source_artifact_path": display_path,
                "source_artifact_present": present,
                "source_artifact_missing": not present,
                "required_action": (
                    "Restore or regenerate this clean-checkout stage5 input CSV, then "
                    "rebuild the baseline summary and reviewed receipt."
                ),
                "operator_action_required": not present,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return rows


def _stage5_task_family_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        task_key = _text(row.get("task_key")) or _stage5_task_key(_text(row.get("source_artifact_path")))
        if not task_key:
            task_key = "unknown_stage5_task"
        family = grouped.setdefault(
            task_key,
            {
                "task_key": task_key,
                "set_id": _text(row.get("set_id")),
                "task_id": _text(row.get("task_id")),
                "domain": _text(row.get("domain")),
                "kind": _text(row.get("kind")),
                "profile_json": _text(row.get("profile_json")),
                "pipeline_summary_json": _text(row.get("pipeline_summary_json")),
                "pipeline_summary_present": bool(row.get("pipeline_summary_present") is True),
                "required_stage5_arguments": list(STAGE5_REQUIRED_ARGUMENTS),
                "required_stage5_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
                "present_source_arguments": [],
                "missing_source_arguments": [],
                "missing_source_artifact_paths": [],
                "present_input_count": 0,
                "missing_input_count": 0,
            },
        )
        source_argument = _text(row.get("source_argument"))
        if row.get("source_artifact_present") is True:
            family["present_input_count"] += 1
            if source_argument:
                family["present_source_arguments"].append(source_argument)
        else:
            family["missing_input_count"] += 1
            if source_argument:
                family["missing_source_arguments"].append(source_argument)
            source_artifact_path = _text(row.get("source_artifact_path"))
            if source_artifact_path:
                family["missing_source_artifact_paths"].append(source_artifact_path)
        if not family["set_id"]:
            family["set_id"] = _text(row.get("set_id"))
        if not family["task_id"]:
            family["task_id"] = _text(row.get("task_id"))
        if not family["domain"]:
            family["domain"] = _text(row.get("domain"))
        if not family["kind"]:
            family["kind"] = _text(row.get("kind"))
        if not family["profile_json"]:
            family["profile_json"] = _text(row.get("profile_json"))
        if not family["pipeline_summary_json"]:
            family["pipeline_summary_json"] = _text(row.get("pipeline_summary_json"))
        family["pipeline_summary_present"] = bool(
            family["pipeline_summary_present"] or row.get("pipeline_summary_present") is True
        )

    family_rows: list[dict[str, Any]] = []
    for family in sorted(grouped.values(), key=lambda item: item["task_key"]):
        family["present_source_arguments"] = sorted(set(family["present_source_arguments"]))
        family["missing_source_arguments"] = [
            argument
            for argument in STAGE5_REQUIRED_ARGUMENTS
            if argument in set(family["missing_source_arguments"])
        ]
        family["stage5_input_family_complete"] = family["missing_input_count"] == 0
        family["operator_action_required"] = family["missing_input_count"] != 0
        family["required_action"] = (
            "Restore or regenerate the full scores/labels/split/expected-keys CSV family for this task."
            if family["operator_action_required"]
            else "Keep this task's stage5 input CSV family with the clean-checkout baseline evidence."
        )
        family["execution_enabled"] = False
        family["external_state_mutated"] = False
        family["claim_promotion_allowed"] = False
        family["claim_boundary"] = CLAIM_BOUNDARY
        family_rows.append(family)
    return family_rows


def _baseline_checks(payload: dict[str, Any], *, root: Path) -> dict[str, Any]:
    summary = _summary(payload)
    bundle_root = _text(summary.get("bundle_root"))
    task_count = _int(summary.get("task_count"))
    current_winner_count = _int(summary.get("task_winner_count_current"))
    noncurrent_winner_count = _int(summary.get("task_winner_count_noncurrent"))
    tasks = summary.get("tasks") if isinstance(summary.get("tasks"), list) else []
    score_leaderboard = (
        summary.get("score_leaderboard")
        if isinstance(summary.get("score_leaderboard"), list)
        else []
    )
    summary_blockers = (
        [_text(item) for item in summary.get("blockers", []) if _text(item)]
        if isinstance(summary.get("blockers"), list)
        else []
    )
    task_source_error_count = _int(summary.get("task_source_error_count"))

    task_structural_failure_count = 0
    ranking_summary_missing_count = 0
    score_row_count = 0
    for task in tasks:
        if not isinstance(task, dict):
            task_structural_failure_count += 1
            continue
        score_rows = task.get("score_rows") if isinstance(task.get("score_rows"), list) else []
        score_row_count += len(score_rows)
        if not _text(task.get("current_score_col")):
            task_structural_failure_count += 1
        if not score_rows:
            task_structural_failure_count += 1
        for score_row in score_rows:
            if not isinstance(score_row, dict):
                task_structural_failure_count += 1
                continue
            if not _artifact_exists(score_row.get("ranking_summary_json"), root=root):
                ranking_summary_missing_count += 1

    leaderboard_csv_count = 0
    if bundle_root:
        leaderboard_csv_count = _csv_row_count(Path(bundle_root) / "score_leaderboard.csv", root=root)

    failed_count = 0
    if not summary:
        failed_count += 1
    if task_count <= 0:
        failed_count += 1
    if len(tasks) != task_count:
        failed_count += 1
    if current_winner_count + noncurrent_winner_count != task_count:
        failed_count += 1
    if not score_leaderboard and leaderboard_csv_count <= 0:
        failed_count += 1
    failed_count += task_structural_failure_count
    failed_count += ranking_summary_missing_count
    failed_count += task_source_error_count
    failed_count += len(summary_blockers)

    return {
        "baseline_summary_present": bool(summary),
        "task_count": task_count,
        "task_row_count": len(tasks),
        "score_leaderboard_count": len(score_leaderboard),
        "score_leaderboard_csv_count": leaderboard_csv_count,
        "current_winner_count": current_winner_count,
        "noncurrent_winner_count": noncurrent_winner_count,
        "score_row_count": score_row_count,
        "task_structural_failure_count": task_structural_failure_count,
        "ranking_summary_missing_count": ranking_summary_missing_count,
        "task_source_error_count": task_source_error_count,
        "summary_blocker_count": len(summary_blockers),
        "summary_blockers": summary_blockers,
        "failed_count": failed_count,
    }


def _provenance_checks(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(payload)
    head_sha = _text(summary.get("head_sha"))
    tracked_file_count = _int(summary.get("tracked_file_count"))
    source_repo_url_present = _bool_true(summary.get("source_repo_url_present"))
    working_tree_clean = _bool_true(summary.get("working_tree_clean"))
    git_status_empty = _bool_true(summary.get("git_status_porcelain_empty"))
    failed_count = 0
    if not summary:
        failed_count += 1
    if not source_repo_url_present:
        failed_count += 1
    if not head_sha:
        failed_count += 1
    if tracked_file_count <= 0:
        failed_count += 1
    if not working_tree_clean or not git_status_empty:
        failed_count += 1
    return {
        "provenance_present": bool(summary),
        "source_repo_url_present": source_repo_url_present,
        "source_repo_url_fingerprint": _text(summary.get("source_repo_url_fingerprint")),
        "source_ref_requested": _text(summary.get("source_ref_requested")),
        "source_ref_requested_present": _bool_true(summary.get("source_ref_requested_present")),
        "source_checked_out_ref": _text(summary.get("source_checked_out_ref")),
        "source_remote_url_redacted": _text(summary.get("source_remote_url_redacted")),
        "head_sha": head_sha,
        "tracked_file_count": tracked_file_count,
        "working_tree_clean": working_tree_clean,
        "git_status_porcelain_empty": git_status_empty,
        "dirty_path_count": _int(summary.get("dirty_path_count")),
        "failed_count": failed_count,
    }


def build_developer_preview_clean_checkout_benchmark_receipt(
    *,
    ai_verify_log: str | Path = DEFAULT_AI_VERIFY_LOG,
    baseline_summary_json: str | Path = DEFAULT_BASELINE_SUMMARY_JSON,
    checkout_provenance_json: str | Path = DEFAULT_CHECKOUT_PROVENANCE_JSON,
    reviewed_receipt_attached: bool = False,
    reviewer_id: str = "",
    reviewed_at_utc: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    ai_verify_text = _read_text(ai_verify_log, root=root)
    ai_verify_present = bool(ai_verify_text)
    ai_verify_ok = _ai_verify_passed(ai_verify_text)
    baseline_payload = _read_json(baseline_summary_json, root=root)
    baseline = _baseline_checks(baseline_payload, root=root)
    provenance_payload = _read_json(checkout_provenance_json, root=root)
    provenance = _provenance_checks(provenance_payload)
    stage5_input_family_rows = _stage5_input_family_rows(baseline_payload, root=root)
    stage5_task_family_rows = _stage5_task_family_rows(stage5_input_family_rows)
    stage5_missing_rows = [
        row for row in stage5_input_family_rows if _bool_true(row.get("source_artifact_missing"))
    ]
    stage5_incomplete_task_family_rows = [
        row
        for row in stage5_task_family_rows
        if not _bool_true(row.get("stage5_input_family_complete"))
    ]
    stage5_primary_row = stage5_missing_rows[0] if stage5_missing_rows else {}
    reviewer_present = bool(_text(reviewer_id))
    reviewed_at_present = bool(_text(reviewed_at_utc))

    blockers: list[str] = []
    if not ai_verify_present:
        blockers.append(f"{_display(ai_verify_log, root=root)}:missing")
    elif not ai_verify_ok:
        blockers.append(f"{_display(ai_verify_log, root=root)}:verify_ok_missing")
    if not baseline["baseline_summary_present"]:
        blockers.append(f"{_display(baseline_summary_json, root=root)}:missing_or_invalid")
    if baseline["summary_blocker_count"] != 0:
        blockers.extend(
            f"baseline_source_blocker={blocker}" for blocker in baseline["summary_blockers"]
        )
        blockers.append("baseline_summary_blocker_count_nonzero")
    if baseline["task_source_error_count"] != 0:
        blockers.append("baseline_task_source_error_count_nonzero")
    if baseline["task_count"] <= 0:
        blockers.append("baseline_task_count_zero")
    if baseline["task_row_count"] != baseline["task_count"]:
        blockers.append("baseline_task_rows_mismatch")
    if baseline["current_winner_count"] + baseline["noncurrent_winner_count"] != baseline["task_count"]:
        blockers.append("baseline_winner_counts_mismatch")
    if baseline["score_leaderboard_count"] <= 0 and baseline["score_leaderboard_csv_count"] <= 0:
        blockers.append("baseline_score_leaderboard_empty")
    if baseline["task_structural_failure_count"] != 0:
        blockers.append("baseline_task_structural_failure_count_nonzero")
    if baseline["ranking_summary_missing_count"] != 0:
        blockers.append("baseline_ranking_summary_missing_count_nonzero")
    if not provenance["provenance_present"]:
        blockers.append(f"{_display(checkout_provenance_json, root=root)}:missing_or_invalid")
    if not provenance["source_repo_url_present"]:
        blockers.append("checkout_source_repo_url_missing")
    if not provenance["head_sha"]:
        blockers.append("checkout_head_sha_missing")
    if provenance["tracked_file_count"] <= 0:
        blockers.append("checkout_tracked_file_count_zero")
    if not provenance["working_tree_clean"] or not provenance["git_status_porcelain_empty"]:
        blockers.append("checkout_worktree_dirty")
    if not reviewed_receipt_attached:
        blockers.append("reviewed_receipt_attached_not_true")
    if not reviewer_present:
        blockers.append("reviewer_id_missing")
    if not reviewed_at_present:
        blockers.append("reviewed_at_utc_missing")

    clean_checkout_benchmark_regenerated = bool(
        baseline["baseline_summary_present"]
        and baseline["task_count"] > 0
        and baseline["failed_count"] == 0
    )
    clean_checkout_provenance_ready = bool(provenance["failed_count"] == 0)
    ready = bool(
        clean_checkout_benchmark_regenerated
        and clean_checkout_provenance_ready
        and ai_verify_ok
        and reviewed_receipt_attached
        and reviewer_present
        and reviewed_at_present
        and not blockers
    )

    rows = [
        {
            "check": "clean_checkout_ai_verify",
            "status": "pass" if ai_verify_ok else "blocked",
            "artifact_path": _display(ai_verify_log, root=root),
            "blockers": [blocker for blocker in blockers if _display(ai_verify_log, root=root) in blocker],
        },
        {
            "check": "baseline_summary",
            "status": "pass" if clean_checkout_benchmark_regenerated else "blocked",
            "artifact_path": _display(baseline_summary_json, root=root),
            "task_count": baseline["task_count"],
            "score_row_count": baseline["score_row_count"],
            "failed_count": baseline["failed_count"],
            "task_source_error_count": baseline["task_source_error_count"],
            "summary_blocker_count": baseline["summary_blocker_count"],
            "blockers": [
                blocker
                for blocker in blockers
                if blocker.startswith("baseline_")
                or _display(baseline_summary_json, root=root) in blocker
            ],
        },
        {
            "check": "clean_checkout_source_provenance",
            "status": "pass" if clean_checkout_provenance_ready else "blocked",
            "artifact_path": _display(checkout_provenance_json, root=root),
            "head_sha": provenance["head_sha"],
            "tracked_file_count": provenance["tracked_file_count"],
            "working_tree_clean": provenance["working_tree_clean"],
            "blockers": [
                blocker
                for blocker in blockers
                if blocker.startswith("checkout_")
                or _display(checkout_provenance_json, root=root) in blocker
            ],
        },
        {
            "check": "operator_review",
            "status": "pass"
            if reviewed_receipt_attached and reviewer_present and reviewed_at_present
            else "blocked",
            "reviewed_receipt_attached": reviewed_receipt_attached,
            "reviewer_id_present": reviewer_present,
            "reviewed_at_utc_present": reviewed_at_present,
            "blockers": [
                blocker
                for blocker in blockers
                if blocker
                in {
                    "reviewed_receipt_attached_not_true",
                    "reviewer_id_missing",
                    "reviewed_at_utc_missing",
                }
            ],
        },
    ]
    if stage5_input_family_rows:
        rows.append(
            {
                "check": "stage5_input_family_recovery",
                "status": "blocked" if stage5_missing_rows else "pass",
                "input_family_row_count": len(stage5_input_family_rows),
                "missing_input_count": len(stage5_missing_rows),
                "task_count": len(stage5_task_family_rows),
                "incomplete_task_count": len(stage5_incomplete_task_family_rows),
                "blockers": [
                    "stage5_input_missing:{source_argument}:{source_artifact_path}".format(
                        source_argument=row["source_argument"],
                        source_artifact_path=row["source_artifact_path"],
                    )
                    for row in stage5_missing_rows
                ],
            }
        )
    primary_blocker = blockers[0] if blockers else ""
    if ready:
        primary_required_action = ""
    elif stage5_primary_row:
        primary_required_action = (
            "Restore or regenerate {argument} at {path} from the approved clean-checkout "
            "baseline, then rerun python3 tools/product/build_developer_preview_stage5_restore_packet.py "
            "and python3 tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py --allow-blocked."
        ).format(
            argument=_text(stage5_primary_row.get("source_argument")) or "the missing stage5 input",
            path=_text(stage5_primary_row.get("source_artifact_path")) or "the missing stage5 input path",
        )
    else:
        primary_required_action = (
            "Run Gate A in a fresh checkout, keep the generated baseline summary and ai-verify log, "
            "then rebuild this receipt with explicit operator review metadata."
        )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_clean_checkout_benchmark_receipt_ready"
        if ready
        else "blocked_developer_preview_clean_checkout_benchmark_receipt",
        "clean_checkout_benchmark_regenerated": clean_checkout_benchmark_regenerated,
        "clean_checkout_provenance_ready": clean_checkout_provenance_ready,
        "clean_checkout_source_repo_url_present": provenance["source_repo_url_present"],
        "clean_checkout_source_repo_url_fingerprint": provenance[
            "source_repo_url_fingerprint"
        ],
        "clean_checkout_source_ref_requested": provenance["source_ref_requested"],
        "clean_checkout_source_ref_requested_present": provenance[
            "source_ref_requested_present"
        ],
        "clean_checkout_source_checked_out_ref": provenance["source_checked_out_ref"],
        "clean_checkout_source_remote_url_redacted": provenance[
            "source_remote_url_redacted"
        ],
        "clean_checkout_head_sha": provenance["head_sha"],
        "clean_checkout_tracked_file_count": provenance["tracked_file_count"],
        "clean_checkout_working_tree_clean": provenance["working_tree_clean"],
        "clean_checkout_dirty_path_count": provenance["dirty_path_count"],
        "ai_verify_passed": ai_verify_ok,
        "reviewed_receipt_attached": reviewed_receipt_attached,
        "reviewer_id_present": reviewer_present,
        "reviewed_at_utc_present": reviewed_at_present,
        "blocker_count": len(blockers),
        "primary_blocker": primary_blocker,
        "primary_required_action": primary_required_action,
        "blockers": blockers,
        "failed_count": baseline["failed_count"],
        "baseline_summary_present": baseline["baseline_summary_present"],
        "baseline_task_count": baseline["task_count"],
        "baseline_task_row_count": baseline["task_row_count"],
        "baseline_score_row_count": baseline["score_row_count"],
        "baseline_score_leaderboard_count": baseline["score_leaderboard_count"],
        "baseline_score_leaderboard_csv_count": baseline["score_leaderboard_csv_count"],
        "baseline_current_winner_count": baseline["current_winner_count"],
        "baseline_noncurrent_winner_count": baseline["noncurrent_winner_count"],
        "baseline_task_structural_failure_count": baseline["task_structural_failure_count"],
        "baseline_ranking_summary_missing_count": baseline["ranking_summary_missing_count"],
        "baseline_task_source_error_count": baseline["task_source_error_count"],
        "baseline_summary_blocker_count": baseline["summary_blocker_count"],
        "baseline_summary_blockers": baseline["summary_blockers"],
        "stage5_required_arguments": list(STAGE5_REQUIRED_ARGUMENTS),
        "stage5_required_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
        "stage5_input_family_row_count": len(stage5_input_family_rows),
        "stage5_recovery_task_count": len(stage5_task_family_rows),
        "stage5_complete_task_count": len(stage5_task_family_rows) - len(stage5_incomplete_task_family_rows),
        "stage5_incomplete_task_count": len(stage5_incomplete_task_family_rows),
        "stage5_missing_input_count": len(stage5_missing_rows),
        "stage5_missing_source_artifact_count": len(stage5_missing_rows),
        "stage5_input_family_ready": bool(
            not stage5_input_family_rows or not stage5_incomplete_task_family_rows
        ),
        "stage5_primary_task_key": _text(stage5_primary_row.get("task_key")),
        "stage5_primary_source_argument": _text(stage5_primary_row.get("source_argument")),
        "stage5_primary_source_artifact_path": _text(
            stage5_primary_row.get("source_artifact_path")
        ),
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this reviewed receipt to the Developer Preview final gate audit."
        if ready
        else primary_required_action,
    }
    return {
        "summary": summary,
        "rows": rows,
        "stage5_input_family_rows": stage5_input_family_rows,
        "stage5_task_family_rows": stage5_task_family_rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_text(item) for item in value if _text(item))
    return _text(value)


def _write_csv_rows(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=STAGE5_INPUT_FAMILY_CSV_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STAGE5_INPUT_FAMILY_CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Clean-Checkout Benchmark Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- clean_checkout_benchmark_regenerated: `{summary['clean_checkout_benchmark_regenerated']}`",
        f"- clean_checkout_provenance_ready: `{summary['clean_checkout_provenance_ready']}`",
        f"- clean_checkout_head_sha: `{summary['clean_checkout_head_sha'] or '-'}`",
        f"- clean_checkout_working_tree_clean: `{summary['clean_checkout_working_tree_clean']}`",
        f"- ai_verify_passed: `{summary['ai_verify_passed']}`",
        f"- reviewed_receipt_attached: `{summary['reviewed_receipt_attached']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- primary_blocker: `{summary['primary_blocker'] or '-'}`",
        f"- primary_required_action: {summary['primary_required_action'] or '-'}",
        f"- failed_count: `{summary['failed_count']}`",
        f"- baseline_task_count: `{summary['baseline_task_count']}`",
        f"- stage5_recovery_task_count: `{summary['stage5_recovery_task_count']}`",
        f"- stage5_incomplete_task_count: `{summary['stage5_incomplete_task_count']}`",
        f"- stage5_missing_input_count: `{summary['stage5_missing_input_count']}`",
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
    if payload.get("stage5_input_family_rows"):
        lines.extend(
            [
                "",
                "## Stage5 Input Family Recovery",
                "",
            ]
        )
        if payload.get("stage5_task_family_rows"):
            lines.extend(
                [
                    "| task | complete | missing inputs | action |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for row in payload["stage5_task_family_rows"]:
                missing_arguments = ";".join(row.get("missing_source_arguments", [])) or "-"
                lines.append(
                    f"| `{row['task_key']}` | `{row['stage5_input_family_complete']}` | "
                    f"`{missing_arguments}` | {row['required_action']} |"
                )
            lines.append("")
        lines.extend(
            [
                "| task | argument | source artifact | present | action |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in payload["stage5_input_family_rows"]:
            lines.append(
                f"| `{row['task_key']}` | `{row['source_argument']}` | "
                f"`{row['source_artifact_path']}` | `{row['source_artifact_present']}` | "
                f"{row['required_action']} |"
            )
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _render_stage5_input_family_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Clean-Checkout Stage5 Input Family",
        "",
        f"- stage5_input_family_row_count: `{summary['stage5_input_family_row_count']}`",
        f"- stage5_missing_input_count: `{summary['stage5_missing_input_count']}`",
        f"- stage5_recovery_task_count: `{summary['stage5_recovery_task_count']}`",
        f"- stage5_incomplete_task_count: `{summary['stage5_incomplete_task_count']}`",
        f"- stage5_required_arguments: `{';'.join(summary['stage5_required_arguments'])}`",
        f"- primary_task_key: `{summary['stage5_primary_task_key']}`",
        f"- primary_source_argument: `{summary['stage5_primary_source_argument']}`",
        f"- primary_source_artifact_path: `{summary['stage5_primary_source_artifact_path']}`",
        "",
        "## Task Family Checklist",
        "",
        "| task | complete | present inputs | missing inputs | action |",
        "| --- | --- | --- | --- | --- |",
    ]
    family_rows = payload.get("stage5_task_family_rows", [])
    for row in family_rows:
        present_arguments = ";".join(row.get("present_source_arguments", [])) or "-"
        missing_arguments = ";".join(row.get("missing_source_arguments", [])) or "-"
        lines.append(
            f"| `{row['task_key']}` | `{row['stage5_input_family_complete']}` | "
            f"`{present_arguments}` | `{missing_arguments}` | {row['required_action']} |"
        )
    if not family_rows:
        lines.append("| - | `True` | - | - | No stage5 input-family task rows are present. |")
    lines.extend(
        [
            "",
            "## Source Artifacts",
            "",
            "| task | argument | source artifact | present | action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    rows = payload.get("stage5_input_family_rows", [])
    for row in rows:
        lines.append(
            f"| `{row['task_key']}` | `{row['source_argument']}` | "
            f"`{row['source_artifact_path']}` | `{row['source_artifact_present']}` | "
            f"{row['required_action']} |"
        )
    if not rows:
        lines.append("| - | - | - | `True` | No stage5 input-family recovery rows are present. |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the Developer Preview clean-checkout benchmark receipt."
    )
    parser.add_argument("--ai-verify-log", default=DEFAULT_AI_VERIFY_LOG)
    parser.add_argument("--baseline-summary-json", default=DEFAULT_BASELINE_SUMMARY_JSON)
    parser.add_argument("--checkout-provenance-json", default=DEFAULT_CHECKOUT_PROVENANCE_JSON)
    parser.add_argument("--reviewed-receipt-attached", action="store_true")
    parser.add_argument("--reviewer-id", default="")
    parser.add_argument("--reviewed-at-utc", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-stage5-input-family-csv", default=DEFAULT_STAGE5_INPUT_FAMILY_CSV)
    parser.add_argument("--out-stage5-input-family-md", default=DEFAULT_STAGE5_INPUT_FAMILY_MD)
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Write a fail-closed blocked receipt and return success so the operator can continue rebuilding the final audit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=args.ai_verify_log,
        baseline_summary_json=args.baseline_summary_json,
        checkout_provenance_json=args.checkout_provenance_json,
        reviewed_receipt_attached=args.reviewed_receipt_attached,
        reviewer_id=args.reviewer_id,
        reviewed_at_utc=args.reviewed_at_utc,
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    _write_csv_rows(args.out_stage5_input_family_csv, payload["stage5_input_family_rows"])
    _write_text(args.out_stage5_input_family_md, _render_stage5_input_family_md(payload))
    if payload["summary"]["status"] == "developer_preview_clean_checkout_benchmark_receipt_ready":
        return 0
    return 0 if args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
