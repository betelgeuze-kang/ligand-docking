#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STAGE5_INPUT_FAMILY_CSV = (
    ".betelgeuze/developer_preview_clean_checkout_stage5_input_family_current.csv"
)
DEFAULT_OUT_JSON = "runs/developer_preview_stage5_restore_packet_current.json"
DEFAULT_OUT_CSV = "runs/developer_preview_stage5_restore_packet_current.csv"
DEFAULT_OUT_MD = "runs/developer_preview_stage5_restore_packet_current.md"

PACKET_TYPE = "developer_preview_stage5_restore_packet"
SCHEMA_VERSION = "developer_preview_stage5_restore_packet_v1"
STAGE5_REQUIRED_ARGUMENTS = [
    "--scores-csv",
    "--labels-csv",
    "--split-csv",
    "--expected-keys-csv",
]
STAGE5_RESTORE_REBUILD_COMMAND = "python3 tools/product/build_developer_preview_stage5_restore_packet.py"
CLEAN_CHECKOUT_RECEIPT_REBUILD_COMMAND = (
    "python3 tools/product/build_developer_preview_clean_checkout_benchmark_receipt.py --allow-blocked"
)

CLAIM_BOUNDARY = (
    "Developer Preview stage5 restore packet only; it inventories missing clean-checkout "
    "stage5 input CSVs and adjacent retained summaries/profiles. It does not execute "
    "benchmarks, regenerate source data, approve paid-pilot wording, upload, email, "
    "deploy, commit, push, or mutate external state."
)

CSV_FIELDS = [
    "set_id",
    "task_id",
    "task_key",
    "domain",
    "kind",
    "source_argument",
    "source_artifact_path",
    "source_artifact_parent_dir",
    "source_artifact_filename",
    "source_artifact_declared_present",
    "source_artifact_present",
    "source_artifact_missing",
    "source_artifact_git_tracked",
    "source_artifact_sha256",
    "pipeline_summary_json",
    "pipeline_summary_present",
    "pipeline_summary_git_tracked",
    "profile_json",
    "profile_present",
    "profile_git_tracked",
    "task_source_required_count",
    "task_source_missing_count",
    "row_blocker",
    "restore_queue_ready",
    "operator_restore_instruction",
    "operator_action_required",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
    "required_action",
]


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


def _repo_relative(path_like: str | Path, *, root: Path = ROOT) -> str:
    try:
        return _resolve(path_like, root=root).relative_to(root).as_posix()
    except ValueError:
        return ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _bool_true(value: Any) -> bool:
    return value is True


def _csv_bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _restore_instruction(
    *,
    source_argument: str,
    source_artifact_path: str,
    pipeline_summary_json: str,
    profile_json: str,
) -> str:
    if not source_artifact_path:
        return "Restore the missing stage5 source CSV path in the input-family CSV, then rebuild the restore packet."
    return (
        f"Restore or regenerate {source_argument or 'stage5 source'} at {source_artifact_path} "
        "from the approved clean-checkout baseline; verify it against "
        f"{pipeline_summary_json or 'the retained pipeline summary'} and "
        f"{profile_json or 'the retained profile'}, then rerun {STAGE5_RESTORE_REBUILD_COMMAND} "
        f"and {CLEAN_CHECKOUT_RECEIPT_REBUILD_COMMAND}."
    )


def _counter_dict(counter: Counter[str], *, preferred_order: list[str] | None = None) -> dict[str, int]:
    ordered: dict[str, int] = {}
    for key in preferred_order or []:
        if counter.get(key, 0):
            ordered[key] = int(counter[key])
    for key in sorted(counter):
        if key not in ordered:
            ordered[key] = int(counter[key])
    return ordered


def _sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def _read_stage5_rows(path_like: str | Path, *, root: Path = ROOT) -> list[dict[str, Any]]:
    path = _resolve(path_like, root=root)
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _git_tracked_paths(paths: list[str], *, root: Path = ROOT) -> set[str]:
    rel_paths = sorted({path for path in paths if path})
    if not rel_paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", *rel_paths],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _task_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text(row.get("set_id")),
        _text(row.get("task_id")),
        _text(row.get("task_key")),
    )


def build_developer_preview_stage5_restore_packet(
    *,
    stage5_input_family_csv: str | Path = DEFAULT_STAGE5_INPUT_FAMILY_CSV,
    root: Path = ROOT,
) -> dict[str, Any]:
    input_path = _resolve(stage5_input_family_csv, root=root)
    input_present = input_path.is_file()
    raw_rows = _read_stage5_rows(stage5_input_family_csv, root=root)

    path_candidates: list[str] = []
    for row in raw_rows:
        for field in ("source_artifact_path", "pipeline_summary_json", "profile_json"):
            rel_path = _repo_relative(_text(row.get(field)), root=root)
            if rel_path:
                path_candidates.append(rel_path)
    tracked_paths = _git_tracked_paths(path_candidates, root=root)

    rows: list[dict[str, Any]] = []
    task_missing_counts: Counter[tuple[str, str, str]] = Counter()
    task_required_counts: Counter[tuple[str, str, str]] = Counter()

    for raw_row in raw_rows:
        source_path_text = _text(raw_row.get("source_artifact_path"))
        pipeline_summary_text = _text(raw_row.get("pipeline_summary_json"))
        profile_text = _text(raw_row.get("profile_json"))
        source_path = _resolve(source_path_text, root=root)
        pipeline_summary_path = _resolve(pipeline_summary_text, root=root)
        profile_path = _resolve(profile_text, root=root)
        source_present = bool(source_path_text and source_path.is_file())
        pipeline_summary_present = bool(pipeline_summary_text and pipeline_summary_path.is_file())
        profile_present = bool(profile_text and profile_path.is_file())
        row_blocker = f"{source_path_text}:missing" if not source_present else ""
        restore_queue_ready = bool((not source_present) and pipeline_summary_present and profile_present)
        task = _task_key(raw_row)
        task_required_counts[task] += 1
        if not source_present:
            task_missing_counts[task] += 1
        rows.append(
            {
                "set_id": _text(raw_row.get("set_id")),
                "task_id": _text(raw_row.get("task_id")),
                "task_key": _text(raw_row.get("task_key")),
                "domain": _text(raw_row.get("domain")),
                "kind": _text(raw_row.get("kind")),
                "source_argument": _text(raw_row.get("source_argument")),
                "source_artifact_path": source_path_text,
                "source_artifact_parent_dir": _display(source_path.parent, root=root)
                if source_path_text
                else "",
                "source_artifact_filename": source_path.name if source_path_text else "",
                "source_artifact_declared_present": _csv_bool(raw_row.get("source_artifact_present")),
                "source_artifact_present": source_present,
                "source_artifact_missing": not source_present,
                "source_artifact_git_tracked": _repo_relative(source_path_text, root=root)
                in tracked_paths,
                "source_artifact_sha256": _sha256(source_path) if source_present else "",
                "pipeline_summary_json": pipeline_summary_text,
                "pipeline_summary_present": pipeline_summary_present,
                "pipeline_summary_git_tracked": _repo_relative(pipeline_summary_text, root=root)
                in tracked_paths,
                "profile_json": profile_text,
                "profile_present": profile_present,
                "profile_git_tracked": _repo_relative(profile_text, root=root) in tracked_paths,
                "row_blocker": row_blocker,
                "restore_queue_ready": restore_queue_ready,
                "operator_restore_instruction": (
                    _restore_instruction(
                        source_argument=_text(raw_row.get("source_argument")),
                        source_artifact_path=source_path_text,
                        pipeline_summary_json=pipeline_summary_text,
                        profile_json=profile_text,
                    )
                    if not source_present
                    else "No stage5 source restore action required for this row."
                ),
                "operator_action_required": not source_present,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "required_action": (
                    "Restore or regenerate this clean-checkout stage5 input CSV, then rebuild "
                    "the clean-checkout benchmark receipt."
                ),
            }
        )

    for row in rows:
        task = (row["set_id"], row["task_id"], row["task_key"])
        row["task_source_required_count"] = int(task_required_counts[task])
        row["task_source_missing_count"] = int(task_missing_counts[task])

    source_present_count = sum(1 for row in rows if row["source_artifact_present"])
    missing_rows = [row for row in rows if row["source_artifact_missing"]]
    restore_queue_rows = [row for row in missing_rows if row["restore_queue_ready"]]
    pipeline_present_count = sum(1 for row in rows if row["pipeline_summary_present"])
    profile_present_count = sum(1 for row in rows if row["profile_present"])
    source_git_tracked_count = sum(1 for row in rows if row["source_artifact_git_tracked"])
    pipeline_git_tracked_count = sum(1 for row in rows if row["pipeline_summary_git_tracked"])
    profile_git_tracked_count = sum(1 for row in rows if row["profile_git_tracked"])

    unique_pipeline_summaries = sorted(
        {row["pipeline_summary_json"] for row in rows if row["pipeline_summary_json"]}
    )
    unique_profiles = sorted({row["profile_json"] for row in rows if row["profile_json"]})
    task_keys = sorted(task_required_counts)
    incomplete_task_keys = sorted(task for task, count in task_missing_counts.items() if count)
    complete_task_keys = [task for task in task_keys if task not in set(incomplete_task_keys)]

    missing_by_set = Counter(row["set_id"] for row in missing_rows)
    missing_by_domain = Counter(row["domain"] for row in missing_rows)
    missing_by_kind = Counter(row["kind"] for row in missing_rows)
    missing_by_argument = Counter(row["source_argument"] for row in missing_rows)

    blockers: list[str] = []
    if not input_present:
        blockers.append(f"{_display(stage5_input_family_csv, root=root)}:missing")
    if not rows:
        blockers.append("stage5_input_family_rows:missing")
    if missing_rows:
        blockers.append(f"stage5_source_artifacts_missing:{len(missing_rows)}")
    missing_pipeline_count = len(rows) - pipeline_present_count
    missing_profile_count = len(rows) - profile_present_count
    if missing_pipeline_count:
        blockers.append(f"stage5_pipeline_summaries_missing:{missing_pipeline_count}")
    if missing_profile_count:
        blockers.append(f"stage5_profiles_missing:{missing_profile_count}")

    ready = bool(input_present and rows and not blockers)
    primary_missing = missing_rows[0] if missing_rows else {}
    fail_closed_restore_receipt_ready = bool(
        input_present
        and rows
        and missing_rows
        and len(restore_queue_rows) == len(missing_rows)
    )
    operator_restore_sequence = [
        "Review rows where operator_action_required=true in runs/developer_preview_stage5_restore_packet_current.csv or .md.",
        "Restore or regenerate each missing stage5 source CSV from approved clean-checkout baseline material.",
        f"Rerun {STAGE5_RESTORE_REBUILD_COMMAND}.",
        f"Rerun {CLEAN_CHECKOUT_RECEIPT_REBUILD_COMMAND} with the reviewed clean-checkout evidence.",
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "developer_preview_stage5_restore_packet_ready"
            if ready
            else "blocked_developer_preview_stage5_restore_packet"
        ),
        "developer_preview_stage5_restore_packet_ready": ready,
        "stage5_restore_ready": ready,
        "restore_ready": ready,
        "stage5_input_family_csv_path": _display(stage5_input_family_csv, root=root),
        "stage5_input_family_csv_present": input_present,
        "input_present": input_present,
        "row_count": len(rows),
        "total_rows": len(rows),
        "source_artifact_required_count": len(rows),
        "source_artifact_present_count": source_present_count,
        "missing_source_artifact_count": len(missing_rows),
        "missing_source_artifact_paths": [
            row["source_artifact_path"] for row in missing_rows if row["source_artifact_path"]
        ],
        "source_artifact_git_tracked_count": source_git_tracked_count,
        "pipeline_summary_required_count": len(rows),
        "pipeline_summary_present_count": pipeline_present_count,
        "missing_pipeline_summary_count": missing_pipeline_count,
        "pipeline_summary_git_tracked_count": pipeline_git_tracked_count,
        "unique_pipeline_summary_count": len(unique_pipeline_summaries),
        "profile_required_count": len(rows),
        "profile_present_count": profile_present_count,
        "missing_profile_count": missing_profile_count,
        "profile_git_tracked_count": profile_git_tracked_count,
        "unique_profile_count": len(unique_profiles),
        "task_count": len(task_keys),
        "complete_task_count": len(complete_task_keys),
        "incomplete_task_count": len(incomplete_task_keys),
        "stage5_fail_closed_restore_receipt_ready": fail_closed_restore_receipt_ready,
        "stage5_operator_restore_queue_ready": fail_closed_restore_receipt_ready,
        "stage5_operator_restore_queue_row_count": len(restore_queue_rows),
        "restore_queue_ready": fail_closed_restore_receipt_ready,
        "restore_queue_ready_count": len(restore_queue_rows),
        "operator_restore_sequence_ready": fail_closed_restore_receipt_ready,
        "operator_restore_sequence": operator_restore_sequence,
        "operator_restore_sequence_step_count": len(operator_restore_sequence),
        "all_missing_rows_have_pipeline_summary": bool(
            missing_rows and all(row["pipeline_summary_present"] for row in missing_rows)
        ),
        "all_missing_rows_have_profile": bool(
            missing_rows and all(row["profile_present"] for row in missing_rows)
        ),
        "stage5_restore_rebuild_command": STAGE5_RESTORE_REBUILD_COMMAND,
        "clean_checkout_receipt_rebuild_command": CLEAN_CHECKOUT_RECEIPT_REBUILD_COMMAND,
        "required_stage5_arguments": list(STAGE5_REQUIRED_ARGUMENTS),
        "required_stage5_argument_count": len(STAGE5_REQUIRED_ARGUMENTS),
        "observed_stage5_arguments": sorted(
            {row["source_argument"] for row in rows if row["source_argument"]}
        ),
        "missing_source_artifact_count_by_set": _counter_dict(missing_by_set),
        "missing_source_artifact_count_by_domain": _counter_dict(missing_by_domain),
        "missing_source_artifact_count_by_kind": _counter_dict(missing_by_kind),
        "missing_source_artifact_count_by_argument": _counter_dict(
            missing_by_argument,
            preferred_order=STAGE5_REQUIRED_ARGUMENTS,
        ),
        "primary_missing_set_id": _text(primary_missing.get("set_id")),
        "primary_missing_task_id": _text(primary_missing.get("task_id")),
        "primary_missing_task_key": _text(primary_missing.get("task_key")),
        "primary_missing_source_argument": _text(primary_missing.get("source_argument")),
        "primary_missing_source_artifact_path": _text(
            primary_missing.get("source_artifact_path")
        ),
        "primary_missing_pipeline_summary_json": _text(
            primary_missing.get("pipeline_summary_json")
        ),
        "primary_missing_pipeline_summary_present": _bool_true(
            primary_missing.get("pipeline_summary_present")
        ),
        "primary_missing_profile_json": _text(primary_missing.get("profile_json")),
        "primary_missing_profile_present": _bool_true(
            primary_missing.get("profile_present")
        ),
        "primary_missing_restore_queue_ready": _bool_true(
            primary_missing.get("restore_queue_ready")
        ),
        "primary_missing_row_blocker": _text(primary_missing.get("row_blocker")),
        "primary_missing_restore_instruction": _text(
            primary_missing.get("operator_restore_instruction")
        ),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else "",
        "next_required_step": (
            "Restore or regenerate the missing stage5 input CSVs from the approved "
            "clean-checkout baseline material, then rebuild the clean-checkout benchmark "
            "receipt and final Developer Preview gate audit."
            if blockers
            else "Rebuild the clean-checkout benchmark receipt and final Developer Preview gate audit."
        ),
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in payload.get("rows", []):
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Developer Preview Stage 5 Restore Packet",
        "",
        "Fail-closed inventory for clean-checkout Stage 5 source CSV recovery.",
        "",
        "## Snapshot",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Status | `{summary['status']}` |",
        f"| Restore ready | `{_bool_text(summary['stage5_restore_ready'])}` |",
        f"| Input family CSV | `{summary['stage5_input_family_csv_path']}` |",
        f"| Rows | `{summary['row_count']}` |",
        f"| Tasks | `{summary['task_count']}` |",
        f"| Incomplete tasks | `{summary['incomplete_task_count']}` |",
        f"| Missing source CSVs | `{summary['missing_source_artifact_count']}` |",
        f"| Fail-closed restore receipt ready | `{_bool_text(summary['stage5_fail_closed_restore_receipt_ready'])}` |",
        f"| Restore queue rows | `{summary['stage5_operator_restore_queue_row_count']}` |",
        f"| Restore sequence ready | `{_bool_text(summary['operator_restore_sequence_ready'])}` |",
        f"| Present pipeline summaries | `{summary['pipeline_summary_present_count']}` |",
        f"| Present profiles | `{summary['profile_present_count']}` |",
        f"| Primary blocker | `{summary['primary_blocker'] or '-'}` |",
        f"| Primary source argument | `{summary['primary_missing_source_argument'] or '-'}` |",
        f"| Primary source CSV | `{summary['primary_missing_source_artifact_path'] or '-'}` |",
        f"| Primary pipeline summary | `{summary['primary_missing_pipeline_summary_json'] or '-'}` |",
        f"| Primary profile | `{summary['primary_missing_profile_json'] or '-'}` |",
        f"| Primary restore queue ready | `{_bool_text(summary['primary_missing_restore_queue_ready'])}` |",
        f"| Primary row blocker | `{summary['primary_missing_row_blocker'] or '-'}` |",
        f"| Restore packet rebuild | `{summary['stage5_restore_rebuild_command']}` |",
        f"| Clean-checkout receipt rebuild | `{summary['clean_checkout_receipt_rebuild_command']}` |",
        f"| Next action | {summary['next_required_step']} |",
        "",
        "## Primary Restore Target",
        "",
        f"- task_key: `{summary['primary_missing_task_key'] or '-'}`",
        f"- source_argument: `{summary['primary_missing_source_argument'] or '-'}`",
        f"- source_artifact_path: `{summary['primary_missing_source_artifact_path'] or '-'}`",
        f"- pipeline_summary_json: `{summary['primary_missing_pipeline_summary_json'] or '-'}`",
        f"- pipeline_summary_present: `{_bool_text(summary['primary_missing_pipeline_summary_present'])}`",
        f"- profile_json: `{summary['primary_missing_profile_json'] or '-'}`",
        f"- profile_present: `{_bool_text(summary['primary_missing_profile_present'])}`",
        f"- restore_queue_ready: `{_bool_text(summary['primary_missing_restore_queue_ready'])}`",
        f"- restore_instruction: {summary['primary_missing_restore_instruction'] or '-'}",
        "",
        "## Missing Source Breakdown",
        "",
        "| Dimension | Value | Count |",
        "| --- | --- | ---: |",
    ]
    for dimension, values in (
        ("set", summary["missing_source_artifact_count_by_set"]),
        ("domain", summary["missing_source_artifact_count_by_domain"]),
        ("kind", summary["missing_source_artifact_count_by_kind"]),
        ("argument", summary["missing_source_artifact_count_by_argument"]),
    ):
        if not values:
            lines.append(f"| `{dimension}` | `-` | `0` |")
        for key, count in values.items():
            lines.append(f"| `{dimension}` | `{key or '-'}` | `{count}` |")
    lines.extend(
        [
            "",
            "## Operator Restore Sequence",
            "",
        ]
    )
    for index, step in enumerate(summary["operator_restore_sequence"], start=1):
        lines.append(f"{index}. {step}")
    lines.extend(
        [
            "",
            "## Restore Rows",
            "",
            "| set | task | argument | source CSV | blocker | queue ready | action required |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row['set_id']}` | `{row['task_id']}` | `{row['source_argument']}` | "
            f"`{row['source_artifact_path']}` | "
            f"`{row['row_blocker'] or '-'}` | "
            f"`{_bool_text(bool(row['restore_queue_ready']))}` | "
            f"`{_bool_text(bool(row['operator_action_required']))}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    return "\n".join(lines)


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_md(payload), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed Developer Preview Stage 5 restore packet."
    )
    parser.add_argument("--stage5-input-family-csv", default=DEFAULT_STAGE5_INPUT_FAMILY_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_developer_preview_stage5_restore_packet(
        stage5_input_family_csv=args.stage5_input_family_csv
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload)
    _write_md(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
