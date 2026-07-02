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
DEFAULT_OUT_JSON = ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
DEFAULT_OUT_MD = ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.md"

PACKET_TYPE = "developer_preview_clean_checkout_benchmark_receipt"
SCHEMA_VERSION = "developer_preview_clean_checkout_benchmark_receipt_v1"

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
        "failed_count": failed_count,
    }


def build_developer_preview_clean_checkout_benchmark_receipt(
    *,
    ai_verify_log: str | Path = DEFAULT_AI_VERIFY_LOG,
    baseline_summary_json: str | Path = DEFAULT_BASELINE_SUMMARY_JSON,
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
    reviewer_present = bool(_text(reviewer_id))
    reviewed_at_present = bool(_text(reviewed_at_utc))

    blockers: list[str] = []
    if not ai_verify_present:
        blockers.append(f"{_display(ai_verify_log, root=root)}:missing")
    elif not ai_verify_ok:
        blockers.append(f"{_display(ai_verify_log, root=root)}:verify_ok_missing")
    if not baseline["baseline_summary_present"]:
        blockers.append(f"{_display(baseline_summary_json, root=root)}:missing_or_invalid")
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
    ready = bool(
        clean_checkout_benchmark_regenerated
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
            "blockers": [
                blocker
                for blocker in blockers
                if blocker.startswith("baseline_")
                or _display(baseline_summary_json, root=root) in blocker
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
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "developer_preview_clean_checkout_benchmark_receipt_ready"
        if ready
        else "blocked_developer_preview_clean_checkout_benchmark_receipt",
        "clean_checkout_benchmark_regenerated": clean_checkout_benchmark_regenerated,
        "ai_verify_passed": ai_verify_ok,
        "reviewed_receipt_attached": reviewed_receipt_attached,
        "reviewer_id_present": reviewer_present,
        "reviewed_at_utc_present": reviewed_at_present,
        "blocker_count": len(blockers),
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
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Attach this reviewed receipt to the Developer Preview final gate audit."
        if ready
        else (
            "Run Gate A in a fresh checkout, keep the generated baseline summary and ai-verify log, "
            "then rebuild this receipt with explicit operator review metadata."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Clean-Checkout Benchmark Receipt",
        "",
        f"- status: `{summary['status']}`",
        f"- clean_checkout_benchmark_regenerated: `{summary['clean_checkout_benchmark_regenerated']}`",
        f"- ai_verify_passed: `{summary['ai_verify_passed']}`",
        f"- reviewed_receipt_attached: `{summary['reviewed_receipt_attached']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- failed_count: `{summary['failed_count']}`",
        f"- baseline_task_count: `{summary['baseline_task_count']}`",
        "",
        "| check | status | blockers |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        blockers = ";".join(str(item) for item in row.get("blockers", [])) or "-"
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{blockers}` |")
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
    parser.add_argument("--reviewed-receipt-attached", action="store_true")
    parser.add_argument("--reviewer-id", default="")
    parser.add_argument("--reviewed-at-utc", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_clean_checkout_benchmark_receipt(
        ai_verify_log=args.ai_verify_log,
        baseline_summary_json=args.baseline_summary_json,
        reviewed_receipt_attached=args.reviewed_receipt_attached,
        reviewer_id=args.reviewer_id,
        reviewed_at_utc=args.reviewed_at_utc,
    )
    _write_json(args.out_json, payload)
    _write_text(args.out_md, _render_md(payload))
    return 0 if payload["summary"]["status"] == "developer_preview_clean_checkout_benchmark_receipt_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
