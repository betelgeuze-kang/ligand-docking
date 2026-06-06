#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UPLOAD_REVIEW_PACKET_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_OUT_DIR = "casp17/current_upload_operator_decision_kit"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_operator_decision_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_OPERATOR_DECISION_KIT.md"

VALID_DECISIONS = {"approve", "hold", "reject"}
SUBMISSION_POLICY = "do_not_submit_without_runtime_author_code_and_operator_approval"
RERUN_COMMANDS = [
    "python3 tools/casp17/build_casp17_current_upload_review_packet.py",
    "python3 tools/casp17/build_casp17_current_upload_operator_decision_kit.py",
    "python3 tools/casp17/build_casp17_current_upload_operator_decision_kit_completion_audit.py",
    "python3 tools/build_casp17_workbench_index.py",
]
CLAIM_BOUNDARY = (
    "CASP17 current upload operator decision kit only. It converts the current upload review packet "
    "into an operator approve/hold/reject intake surface and preserves previously entered operator "
    "decision fields. It does not submit to CASP, serialize a CASP author code, approve a model by "
    "itself, compute native accuracy, or mark strict-blind competitive proof."
)

ROW_COLUMNS = [
    "queue_rank",
    "target_id",
    "official_target_id",
    "urgency",
    "official_human_expiration",
    "days_to_official_human_expiration",
    "review_status",
    "candidate_pdb",
    "candidate_sha256",
    "object_count",
    "chain_ids",
    "review_md",
    "operator_decision",
    "operator_id",
    "operator_decision_ref",
    "author_serialization_status",
    "final_upload_filename",
    "operator_notes",
    "decision_status",
    "first_blocker",
    "next_action",
    "decision_packet_folder",
    "decision_md",
    "claim_boundary",
    "submission_policy",
]
PACKET_COLUMNS = [
    "decision_kit_status",
    "review_packet_status",
    "decision_kit_dir",
    "operator_decision_intake_csv",
    "target_summary_csv",
    "rerun_commands_md",
    "batch_manifest_json",
    "review_target_count",
    "ready_review_count",
    "blocked_review_count",
    "operator_decision_missing_count",
    "invalid_operator_decision_count",
    "approve_count",
    "hold_count",
    "reject_count",
    "author_serialization_missing_count",
    "urgency_today_count",
    "urgency_soon_count",
    "urgency_future_count",
    "first_target_id",
    "first_blocker",
    "next_action",
]
OPERATOR_FIELDS = [
    "operator_decision",
    "operator_id",
    "operator_decision_ref",
    "author_serialization_status",
    "final_upload_filename",
    "operator_notes",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv_map(path_like: str | Path) -> dict[str, dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {_text(row.get("target_id")).upper(): dict(row) for row in csv.DictReader(handle)}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value).strip("_")
    return slug[:140] or "upload_target"


def _decision_folder(row: dict[str, Any], out_dir: str | Path) -> str:
    return _artifact(_resolve(out_dir) / f"{_int(row.get('queue_rank')):02d}_{_safe_slug(_text(row.get('target_id')).lower())}")


def _decision_state(row: dict[str, Any]) -> tuple[str, str, str]:
    decision = _text(row.get("operator_decision")).lower()
    author_status = _text(row.get("author_serialization_status")).lower()
    if _text(row.get("review_status")) != "ready":
        return "blocked_review_not_ready", "review_not_ready", "repair upload review packet before operator decision"
    if not decision:
        return "awaiting_operator_decision", "operator_decision_missing", "set operator_decision to approve, hold, or reject"
    if decision not in VALID_DECISIONS:
        return "blocked_invalid_operator_decision", "invalid_operator_decision", "use approve, hold, or reject"
    if decision == "approve" and author_status != "author_serialized":
        return (
            "awaiting_author_serialization",
            "author_serialization_missing",
            "serialize runtime CASP author code and record final_upload_filename",
        )
    return "operator_decision_ready", "", "rerun workbench and perform final operator upload step if approved"


def _build_rows(review_rows: list[dict[str, Any]], existing_rows: dict[str, dict[str, str]], out_dir: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sorted(review_rows, key=lambda row: (_int(row.get("queue_rank")), _text(row.get("target_id")))):
        target_id = _text(source.get("target_id")).upper()
        previous = existing_rows.get(target_id, {})
        row = {
            "queue_rank": _int(source.get("queue_rank")),
            "target_id": target_id,
            "official_target_id": _text(source.get("official_target_id")),
            "urgency": _text(source.get("urgency")),
            "official_human_expiration": _text(source.get("official_human_expiration")),
            "days_to_official_human_expiration": _int(source.get("days_to_official_human_expiration")),
            "review_status": _text(source.get("review_status")),
            "candidate_pdb": _text(source.get("candidate_pdb")),
            "candidate_sha256": _text(source.get("candidate_sha256")),
            "object_count": _int(source.get("object_count")),
            "chain_ids": _text(source.get("chain_ids")),
            "review_md": _text(source.get("review_md")),
            "operator_decision": _text(previous.get("operator_decision")),
            "operator_id": _text(previous.get("operator_id")),
            "operator_decision_ref": _text(previous.get("operator_decision_ref")),
            "author_serialization_status": _text(previous.get("author_serialization_status")),
            "final_upload_filename": _text(previous.get("final_upload_filename")),
            "operator_notes": _text(previous.get("operator_notes")),
            "decision_packet_folder": "",
            "decision_md": "",
            "claim_boundary": CLAIM_BOUNDARY,
            "submission_policy": SUBMISSION_POLICY,
        }
        status, blocker, next_action = _decision_state(row)
        row["decision_status"] = status
        row["first_blocker"] = blocker
        row["next_action"] = next_action
        folder = _decision_folder(row, out_dir)
        row["decision_packet_folder"] = folder
        row["decision_md"] = _artifact(_resolve(folder) / "DECISION.md")
        rows.append(row)
    return rows


def _kit_status(input_missing: bool, rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_current_upload_review_packet_missing"
    if not rows:
        return "blocked_no_current_upload_review_targets"
    if any(row["decision_status"] == "blocked_invalid_operator_decision" for row in rows):
        return "current_upload_operator_decision_kit_blocked_invalid_decision"
    if any(row["decision_status"] == "blocked_review_not_ready" for row in rows):
        return "current_upload_operator_decision_kit_blocked_review_not_ready"
    if any(row["decision_status"] == "awaiting_operator_decision" for row in rows):
        return "current_upload_operator_decision_kit_awaiting_operator_decisions"
    if any(row["decision_status"] == "awaiting_author_serialization" for row in rows):
        return "current_upload_operator_decision_kit_awaiting_author_serialization"
    return "current_upload_operator_decision_kit_decision_ready"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_path = _resolve(args.upload_review_packet_json)
    review_payload = _read_json(review_path)
    review_summary = _summary(review_payload)
    existing = _read_csv_map(args.existing_intake_csv)
    rows = [] if not review_path.exists() else _build_rows(_rows(review_payload), existing, args.out_dir)
    missing_decisions = [row for row in rows if row["decision_status"] == "awaiting_operator_decision"]
    invalid_decisions = [row for row in rows if row["decision_status"] == "blocked_invalid_operator_decision"]
    author_missing = [row for row in rows if _text(row.get("author_serialization_status")).lower() != "author_serialized"]
    first = next((row for row in rows if row["decision_status"] != "operator_decision_ready"), rows[0] if rows else {})
    decisions = [_text(row.get("operator_decision")).lower() for row in rows]
    status = _kit_status(not review_path.exists(), rows)
    summary = {
        "packet_type": "casp17_current_upload_operator_decision_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_upload_operator_decision_kit_status": status,
        "decision_kit_status": status,
        "review_packet_json": _artifact(args.upload_review_packet_json),
        "review_packet_status": _text(review_summary.get("review_packet_status")),
        "decision_kit_dir": _artifact(args.out_dir),
        "operator_decision_intake_csv": _artifact(_resolve(args.out_dir) / "operator_decision_intake.csv"),
        "target_summary_csv": _artifact(_resolve(args.out_dir) / "target_summary.csv"),
        "rerun_commands_md": _artifact(_resolve(args.out_dir) / "RERUN_COMMANDS.md"),
        "batch_manifest_json": _artifact(_resolve(args.out_dir) / "batch_manifest.json"),
        "review_target_count": len(rows),
        "ready_review_count": sum(1 for row in rows if row["review_status"] == "ready"),
        "blocked_review_count": sum(1 for row in rows if row["review_status"] != "ready"),
        "operator_decision_missing_count": len(missing_decisions),
        "invalid_operator_decision_count": len(invalid_decisions),
        "approve_count": sum(1 for decision in decisions if decision == "approve"),
        "hold_count": sum(1 for decision in decisions if decision == "hold"),
        "reject_count": sum(1 for decision in decisions if decision == "reject"),
        "author_serialization_missing_count": len(author_missing),
        "urgency_today_count": sum(1 for row in rows if row["urgency"] == "today"),
        "urgency_soon_count": sum(1 for row in rows if row["urgency"] == "soon"),
        "urgency_future_count": sum(1 for row in rows if row["urgency"] == "future"),
        "first_target_id": _text(first.get("target_id")),
        "first_blocker": _text(first.get("first_blocker")),
        "next_action": _text(first.get("next_action")) or "fill operator decisions and rerun the listed commands",
        "claim_boundary": CLAIM_BOUNDARY,
        "submission_policy": SUBMISSION_POLICY,
    }
    return {"summary": summary, "rows": rows, "rerun_commands": RERUN_COMMANDS}


def _packet_row(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    return {column: summary.get(column, "") for column in PACKET_COLUMNS}


def _write_target_decision(row: dict[str, Any]) -> None:
    folder = _resolve(row["decision_packet_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    _write_csv(folder / "operator_decision_row.csv", [row], ROW_COLUMNS)
    lines = [
        f"# {row['target_id']} Upload Operator Decision",
        "",
        f"- decision_status: `{row['decision_status']}`",
        f"- urgency: `{row['urgency']}`",
        f"- official_human_expiration: `{row['official_human_expiration'] or '-'}`",
        f"- review_status: `{row['review_status']}`",
        f"- candidate_pdb: `{row['candidate_pdb'] or '-'}`",
        f"- candidate_sha256: `{row['candidate_sha256'] or '-'}`",
        f"- object_count: `{row['object_count']}`",
        f"- review_md: `{row['review_md'] or '-'}`",
        f"- operator_decision: `{row['operator_decision'] or '-'}`",
        f"- operator_id: `{row['operator_id'] or '-'}`",
        f"- operator_decision_ref: `{row['operator_decision_ref'] or '-'}`",
        f"- author_serialization_status: `{row['author_serialization_status'] or '-'}`",
        f"- first_blocker: `{row['first_blocker'] or '-'}`",
        f"- next_action: {row['next_action'] or '-'}",
        "",
        "## Allowed Decisions",
        "",
        "- `approve`: only after runtime author-code serialization and final operator approval.",
        "- `hold`: keep escrow/review state but do not submit.",
        "- `reject`: remove from current upload action path while preserving evidence.",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    (folder / "DECISION.md").write_text("\n".join(lines), encoding="utf-8")


def _write_batch_folder(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    root = _resolve(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(root / "operator_decision_intake.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(root / "target_summary.csv", payload["rows"], ROW_COLUMNS)
    _write_json(
        root / "batch_manifest.json",
        {
            "summary": payload["summary"],
            "claim_boundary": CLAIM_BOUNDARY,
            "submission_policy": SUBMISSION_POLICY,
            "rerun_commands": payload["rerun_commands"],
        },
    )
    (root / "RERUN_COMMANDS.md").write_text(
        "\n".join(["# Rerun Commands", "", *[f"- `{command}`" for command in payload["rerun_commands"]], ""]),
        encoding="utf-8",
    )
    for row in payload["rows"]:
        _write_target_decision(row)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Operator Decision Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['current_upload_operator_decision_kit_status']}`",
        f"- review packet: `{summary['review_packet_status'] or '-'}`",
        f"- reviews ready/blocked/total: `{summary['ready_review_count']}/{summary['blocked_review_count']}/{summary['review_target_count']}`",
        f"- decisions approve/hold/reject/missing/invalid: `{summary['approve_count']}/{summary['hold_count']}/{summary['reject_count']}/{summary['operator_decision_missing_count']}/{summary['invalid_operator_decision_count']}`",
        f"- author serialization missing: `{summary['author_serialization_missing_count']}`",
        f"- urgency today/soon/future: `{summary['urgency_today_count']}/{summary['urgency_soon_count']}/{summary['urgency_future_count']}`",
        f"- first: `{summary['first_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Kit Files",
        "",
        f"- operator decision intake: `{summary['operator_decision_intake_csv']}`",
        f"- target summary: `{summary['target_summary_csv']}`",
        f"- rerun commands: `{summary['rerun_commands_md']}`",
        f"- manifest: `{summary['batch_manifest_json']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_batch_folder(args, payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [_packet_row(payload)], PACKET_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 current upload operator decision kit.")
    parser.add_argument("--upload-review-packet-json", default=DEFAULT_UPLOAD_REVIEW_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--existing-intake-csv", default=f"{DEFAULT_OUT_DIR}/operator_decision_intake.csv")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
