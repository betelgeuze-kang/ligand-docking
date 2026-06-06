#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUDIT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_ACTION_BOARD.md"

ACTION_COLUMNS = [
    "action_rank",
    "target_id",
    "lane",
    "action_status",
    "source_audit_status",
    "required_artifact",
    "required_field",
    "blocker_count",
    "blockers",
    "recommended_action",
    "unlocks",
    "verification_command",
]
CLAIM_BOUNDARY = (
    "Local CASP17 competitive-floor target identity clearance action board only. It expands audited native, "
    "no-leak evidence, provenance, identity-review, and manifest blockers into operator-visible actions. It does "
    "not fetch native structures, clear no-leak provenance, edit workorder templates, mutate identity intake files, "
    "score native accuracy, or submit to CASP."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTION_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _split_blockers(row: dict[str, Any]) -> list[str]:
    return [part.strip() for part in _text(row.get("blockers")).split(",") if part.strip()]


def _select(blockers: list[str], *prefixes_or_values: str) -> list[str]:
    selected: list[str] = []
    for blocker in blockers:
        if blocker in prefixes_or_values or any(blocker.startswith(prefix) for prefix in prefixes_or_values):
            selected.append(blocker)
    return selected


def _provenance_field_blockers(blockers: list[str]) -> list[str]:
    columns = [
        "benchmark_id",
        "target_id",
        "scope",
        "prediction_method",
        "operator",
        "leakage_clearance",
        "operator_clearance",
        "prediction_created_at",
        "native_release_date",
        "prediction_generated_before_native_release",
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]
    selected: list[str] = []
    for blocker in blockers:
        if any(blocker == f"{column}_required" for column in columns):
            selected.append(blocker)
        elif any(blocker == f"{column}_required_iso_date" for column in columns):
            selected.append(blocker)
        elif any(blocker == f"{column}_must_be_false" for column in columns):
            selected.append(blocker)
        elif blocker in {"prediction_date_not_before_native_release"}:
            selected.append(blocker)
    return selected


def _manifest_blockers(blockers: list[str]) -> list[str]:
    selected = _select(blockers, "manifest_")
    return [
        blocker
        for blocker in selected
        if blocker not in {"manifest_native_pdb_not_found", "manifest_waiting_on_provenance_template"}
    ]


def _action(
    *,
    target_id: str,
    lane: str,
    source_audit_status: str,
    required_artifact: str,
    required_field: str,
    blockers: list[str],
    recommended_action: str,
    unlocks: str,
) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "lane": lane,
        "action_status": "open",
        "source_audit_status": source_audit_status,
        "required_artifact": required_artifact,
        "required_field": required_field,
        "blocker_count": len(blockers),
        "blockers": ",".join(dict.fromkeys(blockers)),
        "recommended_action": recommended_action,
        "unlocks": unlocks,
        "verification_command": "python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py",
    }


def _actions_for_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    target_id = _text(row.get("target_id")).upper()
    blockers = _split_blockers(row)
    source_audit_status = _text(row.get("audit_status")) or "missing"
    if source_audit_status == "pass" and not blockers:
        return []
    actions: list[dict[str, Any]] = []
    native_blockers = _select(
        blockers,
        "native_pdb_missing",
        "manifest_native_pdb_not_found",
        "native_pdb_",
        "native_prediction_identity_",
    )
    if native_blockers or _text(row.get("native_file_status")) != "present":
        actions.append(
            _action(
                target_id=target_id,
                lane="native_dropzone",
                source_audit_status=source_audit_status,
                required_artifact=_text(row.get("native_dropzone_pdb")),
                required_field="native_pdb",
                blockers=native_blockers or ["native_pdb_missing"],
                recommended_action=(
                    "Place an operator-cleared native protein PDB in the native dropzone; ensure it is distinct from "
                    "the prediction and has valid ATOM coordinates."
                ),
                unlocks="native_valid_count,native_prediction_distinct_count,manifest_native_pdb",
            )
        )
    evidence_blockers = _select(blockers, "evidence_ref") + _select(
        blockers,
        "identity_discovery_no_leak_clearance_required",
        "identity_discovery_target_origin_review_required",
    )
    if evidence_blockers:
        actions.append(
            _action(
                target_id=target_id,
                lane="no_leak_evidence",
                source_audit_status=source_audit_status,
                required_artifact=_text(row.get("provenance_template_csv")),
                required_field="evidence_ref",
                blockers=evidence_blockers,
                recommended_action=(
                    "Create a local evidence file that names the target and no-leak review, then write that path into "
                    "the provenance template evidence_ref field."
                ),
                unlocks="evidence_ref_verified_count,identity_discovery_cleared_count",
            )
        )
    provenance_blockers = _provenance_field_blockers(blockers)
    if provenance_blockers:
        actions.append(
            _action(
                target_id=target_id,
                lane="provenance_fields",
                source_audit_status=source_audit_status,
                required_artifact=_text(row.get("provenance_template_csv")),
                required_field="provenance_template_required_fields",
                blockers=provenance_blockers,
                recommended_action=(
                    "Fill no-leak/operator clearance, prediction/native dates, and all true/false provenance "
                    "confirmations in the provenance template."
                ),
                unlocks="provenance_ready_count,manifest_sync_ready_to_sync_count",
            )
        )
    manifest_blockers = _manifest_blockers(blockers)
    if manifest_blockers or "manifest_waiting_on_provenance_template" in blockers:
        actions.append(
            _action(
                target_id=target_id,
                lane="manifest_stub_sync",
                source_audit_status=source_audit_status,
                required_artifact=_text(row.get("manifest_stub_csv")),
                required_field="manifest_stub_fields",
                blockers=manifest_blockers or ["manifest_waiting_on_provenance_template"],
                recommended_action=(
                    "After provenance is ready, sync the cleared provenance fields into the manifest stub and rerun "
                    "the clearance cycle."
                ),
                unlocks="manifest_stub_ready_count,manifest_provenance_matched_count,promotion_plan",
            )
        )
    return actions


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit_payload = _read_json(args.audit_json)
    audit_summary = _summary(audit_payload)
    rows: list[dict[str, Any]] = []
    for audit_row in _rows(audit_payload):
        rows.extend(_actions_for_row(audit_row))
    lane_order = {
        "native_dropzone": 1,
        "no_leak_evidence": 2,
        "provenance_fields": 3,
        "manifest_stub_sync": 4,
    }
    rows.sort(key=lambda row: (_text(row.get("target_id")), lane_order.get(_text(row.get("lane")), 99)))
    for rank, row in enumerate(rows, start=1):
        row["action_rank"] = rank
    first_open = rows[0] if rows else {}
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_action_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "action_board_status": "open_actions"
        if rows
        else (
            "ready"
            if _text(audit_summary.get("clearance_workorder_audit_status")) == "pass"
            else "missing_or_no_open_actions"
        ),
        "audit_json": _artifact(args.audit_json),
        "audit_status": _text(audit_summary.get("clearance_workorder_audit_status")),
        "target_count": _int(audit_summary.get("audit_target_count")),
        "action_count": len(rows),
        "open_action_count": len(rows),
        "native_action_count": sum(1 for row in rows if row["lane"] == "native_dropzone"),
        "evidence_action_count": sum(1 for row in rows if row["lane"] == "no_leak_evidence"),
        "provenance_action_count": sum(1 for row in rows if row["lane"] == "provenance_fields"),
        "manifest_action_count": sum(1 for row in rows if row["lane"] == "manifest_stub_sync"),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_open_lane": _text(first_open.get("lane")),
        "first_open_next_action": _text(first_open.get("recommended_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Action Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- action_board_status: `{summary['action_board_status']}`",
        f"- audit_status: `{summary['audit_status'] or '-'}`",
        f"- targets/actions/open: `{summary['target_count']}/{summary['action_count']}/{summary['open_action_count']}`",
        f"- native/evidence/provenance/manifest actions: `{summary['native_action_count']}/{summary['evidence_action_count']}/{summary['provenance_action_count']}/{summary['manifest_action_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}` `{summary['first_open_lane'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| rank | target | lane | status | artifact | field | blockers | recommended action | unlocks |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_rank']} | `{row['target_id']}` | `{row['lane']}` | `{row['action_status']}` | "
            f"`{row['required_artifact'] or '-'}` | `{row['required_field'] or '-'}` | "
            f"`{row['blockers'] or '-'}` | {row['recommended_action']} | `{row['unlocks']}` |"
        )
    if not payload["rows"]:
        lines.append("| 0 | - | - | `ready` | - | - | - | no open clearance actions | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 target identity clearance action board.")
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
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
