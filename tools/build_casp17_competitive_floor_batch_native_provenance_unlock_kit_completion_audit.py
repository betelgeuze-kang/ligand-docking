#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools import build_casp17_competitive_floor_first_native_provenance_unlock_kit as first


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BATCH_KIT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_UNLOCK_KIT_COMPLETION_AUDIT.md"

CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance unlock kit completion audit only. It verifies the "
    "batch operator-fill workspace, per-target files, CSV row counts, no-coordinate-copy hygiene, and proof "
    "boundary flags. It does not fetch native structures, fill or trust provenance, clear no-leak evidence, "
    "compute native accuracy, serialize a CASP author code, or submit to CASP."
)

ROW_COLUMNS = [
    "target_id",
    "target_name",
    "audit_status",
    "kit_status",
    "kit_folder",
    "folder_present",
    "readme_present",
    "manifest_present",
    "operator_fill_intake_present",
    "required_actions_present",
    "rerun_commands_present",
    "operator_fill_intake_expected_rows",
    "operator_fill_intake_csv_rows",
    "operator_fill_intake_row_mismatch",
    "required_actions_expected_rows",
    "required_actions_csv_rows",
    "required_actions_row_mismatch",
    "batch_required_actions_csv_rows",
    "coordinate_copy_count",
    "competitive_proof_eligible",
    "author_serialized",
    "native_file_present",
    "provenance_ready",
    "evidence_ref_verified",
    "identity_discovery_cleared",
    "blockers",
]


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = first._resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _present(path_like: str | Path) -> int:
    return 1 if first._resolve(path_like).is_file() else 0


def _folder_present(path_like: str | Path) -> int:
    return 1 if first._resolve(path_like).is_dir() else 0


def _split_ids(value: Any) -> list[str]:
    return [part for part in (first._text(item) for item in first._text(value).split(",")) if part]


def _batch_file_blockers(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if first._text(summary.get("batch_unlock_kit_status")) != (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    ):
        blockers.append("batch_unlock_kit_not_ready_for_operator_fill")
    checks = {
        "batch_folder_missing": (summary.get("batch_folder"), _folder_present),
        "batch_readme_missing": (summary.get("batch_readme_md"), _present),
        "batch_manifest_missing": (summary.get("batch_manifest_json"), _present),
        "batch_operator_fill_intake_missing": (summary.get("batch_operator_fill_intake_csv"), _present),
        "batch_required_actions_missing": (summary.get("batch_required_actions_csv"), _present),
        "batch_rerun_commands_missing": (summary.get("batch_rerun_commands_md"), _present),
    }
    for blocker, (path, predicate) in checks.items():
        if not first._text(path) or not predicate(path):
            blockers.append(blocker)
    return blockers


def _target_row(
    row: dict[str, Any],
    *,
    batch_actions_by_target: dict[str, list[dict[str, str]]],
    global_blockers: list[str],
) -> dict[str, Any]:
    target_id = first._text(row.get("target_id")).upper()
    intake_rows = _read_csv_rows(row.get("operator_fill_intake_csv", ""))
    action_rows = _read_csv_rows(row.get("required_actions_csv", ""))
    expected_actions = first._int(row.get("required_action_count"))
    blockers = global_blockers[:]
    folder_present = _folder_present(row.get("kit_folder", ""))
    readme_present = _present(row.get("readme_md", ""))
    manifest_present = _present(row.get("kit_manifest_json", ""))
    intake_present = _present(row.get("operator_fill_intake_csv", ""))
    actions_present = _present(row.get("required_actions_csv", ""))
    rerun_present = _present(row.get("rerun_commands_md", ""))
    if not folder_present:
        blockers.append("target_kit_folder_missing")
    if not readme_present:
        blockers.append("target_readme_missing")
    if not manifest_present:
        blockers.append("target_manifest_missing")
    if not intake_present:
        blockers.append("target_operator_fill_intake_missing")
    if not actions_present:
        blockers.append("target_required_actions_missing")
    if not rerun_present:
        blockers.append("target_rerun_commands_missing")
    if len(intake_rows) != 1:
        blockers.append("target_operator_fill_intake_row_mismatch")
    if len(action_rows) != expected_actions:
        blockers.append("target_required_actions_row_mismatch")
    if len(batch_actions_by_target.get(target_id, [])) != expected_actions:
        blockers.append("batch_required_actions_target_row_mismatch")
    coordinate_count = first._coordinate_file_count(row.get("kit_folder", ""))
    if coordinate_count:
        blockers.append("target_coordinate_copy_present")
    if first._text(row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if first._text(row.get("author_serialized")).lower() != "false":
        blockers.append("author_boundary_not_false")
    blockers = list(dict.fromkeys(blockers))
    return {
        "target_id": target_id,
        "target_name": first._text(row.get("target_name")),
        "audit_status": "pass" if not blockers else "blocked",
        "kit_status": first._text(row.get("kit_status")),
        "kit_folder": first._artifact(row.get("kit_folder", "")),
        "folder_present": folder_present,
        "readme_present": readme_present,
        "manifest_present": manifest_present,
        "operator_fill_intake_present": intake_present,
        "required_actions_present": actions_present,
        "rerun_commands_present": rerun_present,
        "operator_fill_intake_expected_rows": 1,
        "operator_fill_intake_csv_rows": len(intake_rows),
        "operator_fill_intake_row_mismatch": 0 if len(intake_rows) == 1 else 1,
        "required_actions_expected_rows": expected_actions,
        "required_actions_csv_rows": len(action_rows),
        "required_actions_row_mismatch": 0 if len(action_rows) == expected_actions else 1,
        "batch_required_actions_csv_rows": len(batch_actions_by_target.get(target_id, [])),
        "coordinate_copy_count": coordinate_count,
        "competitive_proof_eligible": first._text(row.get("competitive_proof_eligible")),
        "author_serialized": first._text(row.get("author_serialized")),
        "native_file_present": first._int(row.get("native_file_present")),
        "provenance_ready": first._text(row.get("provenance_ready")),
        "evidence_ref_verified": first._text(row.get("evidence_ref_verified")),
        "identity_discovery_cleared": first._text(row.get("identity_discovery_cleared")),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = first._read_json(args.batch_kit_json)
    summary = first._summary(payload)
    rows = first._rows(payload)
    target_ids = _split_ids(summary.get("target_ids"))
    batch_intake_rows = _read_csv_rows(summary.get("batch_operator_fill_intake_csv", ""))
    batch_action_rows = _read_csv_rows(summary.get("batch_required_actions_csv", ""))
    batch_actions_by_target: dict[str, list[dict[str, str]]] = {}
    for action in batch_action_rows:
        batch_actions_by_target.setdefault(first._text(action.get("target_id")).upper(), []).append(action)
    global_blockers = _batch_file_blockers(summary)
    expected_target_count = first._int(summary.get("target_count"))
    expected_action_count = first._int(summary.get("required_action_count"))
    if len(rows) != expected_target_count:
        global_blockers.append("batch_json_target_row_mismatch")
    if len(batch_intake_rows) != expected_target_count:
        global_blockers.append("batch_operator_fill_intake_row_mismatch")
    if len(batch_action_rows) != expected_action_count:
        global_blockers.append("batch_required_actions_row_mismatch")
    if set(target_ids) != {first._text(row.get("target_id")).upper() for row in rows}:
        global_blockers.append("batch_target_ids_mismatch")
    target_rows = [
        _target_row(row, batch_actions_by_target=batch_actions_by_target, global_blockers=global_blockers)
        for row in rows
    ]
    blocked_rows = [row for row in target_rows if row["audit_status"] != "pass"]
    coordinate_count = first._coordinate_file_count(summary.get("batch_folder", ""))
    if coordinate_count and "batch_coordinate_copy_present" not in global_blockers:
        global_blockers.append("batch_coordinate_copy_present")
    batch_file_present_count = sum(
        [
            _folder_present(summary.get("batch_folder", "")),
            _present(summary.get("batch_readme_md", "")),
            _present(summary.get("batch_manifest_json", "")),
            _present(summary.get("batch_operator_fill_intake_csv", "")),
            _present(summary.get("batch_required_actions_csv", "")),
            _present(summary.get("batch_rerun_commands_md", "")),
        ]
    )
    status = "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
    if blocked_rows or global_blockers or not target_rows:
        status = "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_blocked"
    first_row = target_rows[0] if target_rows else {}
    audit_summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_unlock_kit_completion_audit_status": status,
        "batch_kit_json": first._artifact(args.batch_kit_json),
        "batch_unlock_kit_status": first._text(summary.get("batch_unlock_kit_status")),
        "target_count": len(target_rows),
        "target_pass_count": len(target_rows) - len(blocked_rows),
        "target_blocked_count": len(blocked_rows),
        "target_ids": ",".join(target_ids),
        "batch_file_present_count": batch_file_present_count,
        "batch_file_expected_count": 6,
        "batch_operator_fill_intake_expected_rows": expected_target_count,
        "batch_operator_fill_intake_csv_rows": len(batch_intake_rows),
        "batch_operator_fill_intake_row_mismatch_count": 0 if len(batch_intake_rows) == expected_target_count else 1,
        "batch_required_actions_expected_rows": expected_action_count,
        "batch_required_actions_csv_rows": len(batch_action_rows),
        "batch_required_actions_row_mismatch_count": 0 if len(batch_action_rows) == expected_action_count else 1,
        "target_folder_present_count": sum(first._int(row.get("folder_present")) for row in target_rows),
        "target_readme_present_count": sum(first._int(row.get("readme_present")) for row in target_rows),
        "target_manifest_present_count": sum(first._int(row.get("manifest_present")) for row in target_rows),
        "target_operator_fill_intake_present_count": sum(
            first._int(row.get("operator_fill_intake_present")) for row in target_rows
        ),
        "target_required_actions_present_count": sum(first._int(row.get("required_actions_present")) for row in target_rows),
        "target_rerun_commands_present_count": sum(first._int(row.get("rerun_commands_present")) for row in target_rows),
        "target_operator_fill_intake_expected_rows": sum(
            first._int(row.get("operator_fill_intake_expected_rows")) for row in target_rows
        ),
        "target_operator_fill_intake_csv_rows": sum(
            first._int(row.get("operator_fill_intake_csv_rows")) for row in target_rows
        ),
        "target_operator_fill_intake_row_mismatch_count": sum(
            first._int(row.get("operator_fill_intake_row_mismatch")) for row in target_rows
        ),
        "target_required_actions_expected_rows": sum(
            first._int(row.get("required_actions_expected_rows")) for row in target_rows
        ),
        "target_required_actions_csv_rows": sum(first._int(row.get("required_actions_csv_rows")) for row in target_rows),
        "target_required_actions_row_mismatch_count": sum(
            first._int(row.get("required_actions_row_mismatch")) for row in target_rows
        ),
        "coordinate_copy_count": coordinate_count,
        "target_coordinate_copy_count": sum(first._int(row.get("coordinate_copy_count")) for row in target_rows),
        "competitive_proof_eligible_count": sum(
            1 for row in target_rows if first._text(row.get("competitive_proof_eligible")).lower() == "true"
        ),
        "author_serialized_count": sum(
            1 for row in target_rows if first._text(row.get("author_serialized")).lower() == "true"
        ),
        "native_file_present_count": sum(first._int(row.get("native_file_present")) for row in target_rows),
        "provenance_ready_count": sum(
            1 for row in target_rows if first._text(row.get("provenance_ready")).lower() == "true"
        ),
        "evidence_ref_verified_count": sum(
            1 for row in target_rows if first._text(row.get("evidence_ref_verified")).lower() == "true"
        ),
        "identity_discovery_cleared_count": sum(
            1 for row in target_rows if first._text(row.get("identity_discovery_cleared")).lower() == "true"
        ),
        "first_target_id": first._text(first_row.get("target_id")),
        "first_blocked_target_id": first._text(blocked_rows[0].get("target_id")) if blocked_rows else "",
        "first_blocker": first._text(blocked_rows[0].get("blockers")).split(",")[0] if blocked_rows else "",
        "next_action": "Fill batch native/provenance operator values after this file-completion audit passes.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": audit_summary, "rows": target_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = first._resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = first._resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Unlock Kit Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_unlock_kit_completion_audit_status']}`",
        f"- targets pass/blocked/total: `{summary['target_pass_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- batch files present/expected: `{summary['batch_file_present_count']}/{summary['batch_file_expected_count']}`",
        f"- batch intake expected/csv/mismatch: `{summary['batch_operator_fill_intake_expected_rows']}/{summary['batch_operator_fill_intake_csv_rows']}/{summary['batch_operator_fill_intake_row_mismatch_count']}`",
        f"- batch actions expected/csv/mismatch: `{summary['batch_required_actions_expected_rows']}/{summary['batch_required_actions_csv_rows']}/{summary['batch_required_actions_row_mismatch_count']}`",
        f"- target files folder/readme/manifest/intake/actions/rerun: `{summary['target_folder_present_count']}/{summary['target_readme_present_count']}/{summary['target_manifest_present_count']}/{summary['target_operator_fill_intake_present_count']}/{summary['target_required_actions_present_count']}/{summary['target_rerun_commands_present_count']}`",
        f"- target intake expected/csv/mismatch: `{summary['target_operator_fill_intake_expected_rows']}/{summary['target_operator_fill_intake_csv_rows']}/{summary['target_operator_fill_intake_row_mismatch_count']}`",
        f"- target actions expected/csv/mismatch: `{summary['target_required_actions_expected_rows']}/{summary['target_required_actions_csv_rows']}/{summary['target_required_actions_row_mismatch_count']}`",
        f"- coordinate copies batch/target: `{summary['coordinate_copy_count']}/{summary['target_coordinate_copy_count']}`",
        f"- native/provenance/evidence/identity: `{summary['native_file_present_count']}/{summary['provenance_ready_count']}/{summary['evidence_ref_verified_count']}/{summary['identity_discovery_cleared_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | files | intake | actions | coordinates | blockers |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['audit_status']}` | "
            f"`{row['folder_present']}/{row['readme_present']}/{row['manifest_present']}/{row['operator_fill_intake_present']}/{row['required_actions_present']}/{row['rerun_commands_present']}` | "
            f"`{row['operator_fill_intake_expected_rows']}/{row['operator_fill_intake_csv_rows']}/{row['operator_fill_intake_row_mismatch']}` | "
            f"`{row['required_actions_expected_rows']}/{row['required_actions_csv_rows']}/{row['required_actions_row_mismatch']}` | "
            f"`{row['coordinate_copy_count']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = first._resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit CASP17 batch native/provenance unlock kit completion.")
    parser.add_argument("--batch-kit-json", default=DEFAULT_BATCH_KIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
