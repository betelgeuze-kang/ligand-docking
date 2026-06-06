#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.casp17 import build_casp17_competitive_floor_evidence_import_packet as evidence_import
from tools.casp17 import build_casp17_competitive_floor_evidence_unlock_priority as unlock_priority
from tools.casp17 import build_casp17_competitive_floor_identity_unlock_kit as identity_kit


DEFAULT_DROPZONE_JSON = "casp17/casp17_competitive_floor_evidence_dropzone_current.json"
DEFAULT_IMPORT_CSV = "casp17/casp17_competitive_floor_evidence_import_current.csv"
DEFAULT_IMPORT_JSON = "casp17/casp17_competitive_floor_evidence_import_current.json"
DEFAULT_IMPORT_AUDIT_CSV = "casp17/casp17_competitive_floor_evidence_import_audit_current.csv"
DEFAULT_IMPORT_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_IMPORT.md"
DEFAULT_CURRENT_TARGET_CSV = "casp17/casp17_target_model_folders_current.csv"
DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_IDENTITY_KIT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_IDENTITY_KIT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_UNLOCK_KIT.md"
DEFAULT_UNLOCK_PRIORITY_JSON = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.json"
DEFAULT_UNLOCK_PRIORITY_CSV = "casp17/casp17_competitive_floor_evidence_unlock_priority_current.csv"
DEFAULT_UNLOCK_PRIORITY_MD = "casp17/COMPETITIVE_FLOOR_EVIDENCE_UNLOCK_PRIORITY.md"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_unlock_round_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_unlock_round_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_UNLOCK_ROUND.md"

CLAIM_BOUNDARY = (
    "Local competitive-floor identity unlock round only. It chains the compact identity kit, evidence import "
    "audit/apply gate, and unlock-priority audit so cleared benchmark_id/target_id entries can be reviewed and "
    "applied consistently. It does not choose historical targets, clear no-leak provenance, fetch native "
    "structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["stage", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _run_identity_kit(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--import-csv",
        args.import_csv,
        "--current-target-csv",
        args.current_target_csv,
        "--out-json",
        args.identity_kit_json,
        "--out-csv",
        args.identity_kit_csv,
        "--out-md",
        args.identity_kit_md,
    ]
    if args.apply_identity:
        argv.append("--apply")
    kit_args = identity_kit.parse_args(argv)
    payload = identity_kit.build_payload(kit_args)
    identity_kit.write_outputs(kit_args, payload)
    return payload


def _run_evidence_import(args: argparse.Namespace) -> dict[str, Any]:
    argv = [
        "--dropzone-json",
        args.dropzone_json,
        "--import-csv",
        args.import_csv,
        "--out-json",
        args.import_json,
        "--out-csv",
        args.import_audit_csv,
        "--out-md",
        args.import_md,
        "--no-write-import-template",
        "--no-write-guides",
    ]
    if args.write_import_template:
        argv.remove("--no-write-import-template")
        argv.append("--write-import-template")
    if args.write_guides:
        argv.remove("--no-write-guides")
        argv.append("--write-guides")
    if args.apply_import:
        argv.append("--apply")
    if args.overwrite_import:
        argv.append("--overwrite")
    import_args = evidence_import.parse_args(argv)
    payload = evidence_import.build_payload(import_args)
    evidence_import.write_outputs(import_args, payload)
    return payload


def _run_unlock_priority(args: argparse.Namespace) -> dict[str, Any]:
    priority_args = unlock_priority.parse_args(
        [
            "--import-json",
            args.import_json,
            "--import-csv",
            args.import_csv,
            "--out-json",
            args.unlock_priority_json,
            "--out-csv",
            args.unlock_priority_csv,
            "--out-md",
            args.unlock_priority_md,
        ]
    )
    payload = unlock_priority.build_payload(priority_args)
    unlock_priority.write_outputs(priority_args, payload)
    return payload


def _round_status(args: argparse.Namespace, identity: dict[str, Any], imported: dict[str, Any], unlock: dict[str, Any]) -> str:
    identity_blocked = _int(identity.get("blocked_identity_count"))
    identity_awaiting = _int(identity.get("awaiting_identity_count"))
    identity_ready = _int(identity.get("ready_for_import_count"))
    identity_applied = _int(identity.get("applied_identity_import_count"))
    import_ready = _int(imported.get("ready_for_apply_count"))
    target_id_open = _int(unlock.get("target_id_open_count"))
    if identity_blocked:
        return "blocked_identity"
    if identity_ready and not args.apply_identity:
        return "ready_for_identity_apply"
    if identity_applied and import_ready and not args.apply_import:
        return "ready_for_identity_import_apply"
    if args.apply_import and target_id_open == 0 and _int(identity.get("row_count")):
        return "identity_unlocked_continue_file_sources"
    if identity_awaiting:
        return "awaiting_identity"
    if import_ready:
        return "ready_for_identity_import_apply"
    if _text(unlock.get("unlock_status")) == "ready":
        return "identity_unlocked_continue_file_sources"
    return _text(unlock.get("unlock_status")) or _text(imported.get("import_status")) or _text(identity.get("identity_unlock_status")) or "missing"


def _next_action(args: argparse.Namespace, identity: dict[str, Any], imported: dict[str, Any], unlock: dict[str, Any]) -> str:
    if _int(identity.get("blocked_identity_count")):
        return "fix blocked proposed identity rows in the identity unlock kit"
    if _int(identity.get("awaiting_identity_count")):
        return "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the identity kit"
    if _int(identity.get("ready_for_import_count")) and not args.apply_identity:
        return "review the identity kit, then rerun this round with --apply-identity"
    if _int(imported.get("ready_for_apply_count")) and not args.apply_import:
        return "review ready identity import rows, then rerun with --apply-import"
    if _int(unlock.get("target_id_open_count")) == 0:
        return "continue with file_sources: provide cleared local historical prediction/native/ablation PDB source paths"
    return _text(unlock.get("first_open_next_action")) or "review identity unlock outputs"


def _stage_row(stage: str, status: str, path_like: str, *, ready: int, awaiting: int, blocked: int, applied: int, next_action: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status or "missing",
        "path": _artifact(path_like),
        "ready_count": ready,
        "awaiting_count": awaiting,
        "blocked_count": blocked,
        "applied_count": applied,
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    identity_payload = _run_identity_kit(args)
    import_payload = _run_evidence_import(args)
    unlock_payload = _run_unlock_priority(args)
    identity_summary = _summary(identity_payload)
    import_summary = _summary(import_payload)
    unlock_summary = _summary(unlock_payload)
    status = _round_status(args, identity_summary, import_summary, unlock_summary)
    next_action = _next_action(args, identity_summary, import_summary, unlock_summary)
    rows = [
        _stage_row(
            "identity_kit",
            _text(identity_summary.get("identity_unlock_status")),
            args.identity_kit_json,
            ready=_int(identity_summary.get("ready_for_import_count")),
            awaiting=_int(identity_summary.get("awaiting_identity_count")),
            blocked=_int(identity_summary.get("blocked_identity_count")),
            applied=_int(identity_summary.get("applied_identity_import_count")),
            next_action=_text(identity_summary.get("first_open_blockers")) or next_action,
        ),
        _stage_row(
            "evidence_import",
            _text(import_summary.get("import_status")),
            args.import_json,
            ready=_int(import_summary.get("ready_for_apply_count")),
            awaiting=_int(import_summary.get("awaiting_import_value_count")) + _int(import_summary.get("awaiting_import_file_count")),
            blocked=_int(import_summary.get("blocked_count")),
            applied=_int(import_summary.get("applied_count")),
            next_action=_text(import_summary.get("first_open_next_action")),
        ),
        _stage_row(
            "unlock_priority",
            _text(unlock_summary.get("unlock_status")),
            args.unlock_priority_json,
            ready=max(0, _int(unlock_summary.get("phase_row_count")) - _int(unlock_summary.get("identity_open_action_count"))),
            awaiting=_int(unlock_summary.get("identity_open_action_count")),
            blocked=_int(unlock_summary.get("file_actions_waiting_on_identity_count")),
            applied=0,
            next_action=_text(unlock_summary.get("first_open_next_action")),
        ),
    ]
    summary = {
        "packet_type": "casp17_competitive_floor_identity_unlock_round",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_round_status": status,
        "apply_identity": bool(args.apply_identity),
        "apply_import": bool(args.apply_import),
        "identity_kit_json": _artifact(args.identity_kit_json),
        "import_json": _artifact(args.import_json),
        "unlock_priority_json": _artifact(args.unlock_priority_json),
        "row_count": _int(identity_summary.get("row_count")),
        "identity_ready_for_import_count": _int(identity_summary.get("ready_for_import_count")),
        "identity_awaiting_count": _int(identity_summary.get("awaiting_identity_count")),
        "identity_blocked_count": _int(identity_summary.get("blocked_identity_count")),
        "applied_identity_import_count": _int(identity_summary.get("applied_identity_import_count")),
        "import_ready_for_apply_count": _int(import_summary.get("ready_for_apply_count")),
        "import_applied_count": _int(import_summary.get("applied_count")),
        "identity_open_action_count": _int(unlock_summary.get("identity_open_action_count")),
        "target_id_open_count": _int(unlock_summary.get("target_id_open_count")),
        "file_actions_waiting_on_identity_count": _int(unlock_summary.get("file_actions_waiting_on_identity_count")),
        "first_next_action": next_action,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Unlock Round",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_round_status: `{summary['identity_round_status']}`",
        f"- apply_identity/apply_import: `{summary['apply_identity']}/{summary['apply_import']}`",
        f"- rows: `{summary['row_count']}`",
        f"- identity ready/awaiting/blocked: `{summary['identity_ready_for_import_count']}/{summary['identity_awaiting_count']}/{summary['identity_blocked_count']}`",
        f"- applied identity import cells: `{summary['applied_identity_import_count']}`",
        f"- import ready/applied: `{summary['import_ready_for_apply_count']}/{summary['import_applied_count']}`",
        f"- identity open/target_id open: `{summary['identity_open_action_count']}/{summary['target_id_open_count']}`",
        f"- file actions waiting on identity: `{summary['file_actions_waiting_on_identity_count']}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Round Stages",
        "",
        "| stage | status | ready | awaiting | blocked | applied | path | next action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['stage']}` | `{row['status']}` | {row['ready_count']} | {row['awaiting_count']} | "
            f"{row['blocked_count']} | {row['applied_count']} | `{row['path']}` | {row['next_action'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CASP17 competitive-floor identity unlock round.")
    parser.add_argument("--dropzone-json", default=DEFAULT_DROPZONE_JSON)
    parser.add_argument("--import-csv", default=DEFAULT_IMPORT_CSV)
    parser.add_argument("--import-json", default=DEFAULT_IMPORT_JSON)
    parser.add_argument("--import-audit-csv", default=DEFAULT_IMPORT_AUDIT_CSV)
    parser.add_argument("--import-md", default=DEFAULT_IMPORT_MD)
    parser.add_argument("--current-target-csv", default=DEFAULT_CURRENT_TARGET_CSV)
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--identity-kit-csv", default=DEFAULT_IDENTITY_KIT_CSV)
    parser.add_argument("--identity-kit-md", default=DEFAULT_IDENTITY_KIT_MD)
    parser.add_argument("--unlock-priority-json", default=DEFAULT_UNLOCK_PRIORITY_JSON)
    parser.add_argument("--unlock-priority-csv", default=DEFAULT_UNLOCK_PRIORITY_CSV)
    parser.add_argument("--unlock-priority-md", default=DEFAULT_UNLOCK_PRIORITY_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply-identity", action="store_true")
    parser.add_argument("--apply-import", action="store_true")
    parser.add_argument("--overwrite-import", action="store_true")
    parser.add_argument("--write-import-template", action="store_true")
    parser.add_argument("--write-guides", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
