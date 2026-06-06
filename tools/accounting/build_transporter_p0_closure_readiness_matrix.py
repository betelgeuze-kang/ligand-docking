#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_CLOSURE_JSON = RUNS / "transporter_p0_closure_packet_current.json"
DEFAULT_ACQUISITION_JSON = RUNS / "transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_p0_closure_readiness_matrix_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_p0_closure_readiness_matrix_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_p0_closure_readiness_matrix_current.md"

CLAIM_BOUNDARY = (
    "Transporter P0 closure readiness matrix only; joins open P0 artifact rows to unresolved evidence slots "
    "and classifies whether closure can proceed locally or still requires manual/external evidence. It does not "
    "authoritatively apply rows, reopen donor policy, run docking, widen product scope, upload, submit, email, "
    "delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _target_alias(target_id: str) -> str:
    if target_id == "Aquaporin_1":
        return "AQP1"
    return target_id


def _acquisition_rows_by_target(acquisition_packet: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in _rows(acquisition_packet):
        target = _text(row.get("target_id"))
        if not target:
            continue
        by_target.setdefault(target, []).append(row)
    return by_target


def _manual_or_external_required(slot_rows: list[dict[str, Any]]) -> bool:
    if not slot_rows:
        return True
    for row in slot_rows:
        mode = _text(row.get("request_mode"))
        if mode == "sync_exact_negative_evidence_into_workbook_required":
            continue
        if mode.startswith("exact_target_pair") or "direct_binding" in mode:
            return True
    return False


def _local_sync_ready_count(slot_rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in slot_rows
        if _text(row.get("request_mode")) == "sync_exact_negative_evidence_into_workbook_required"
    )


def _first_action(slot_rows: list[dict[str, Any]], fallback: str) -> tuple[str, str]:
    for row in slot_rows:
        action = _text(row.get("next_required_action"))
        if action:
            return _text(row.get("packet_step")), action
    return "", fallback


def build_payload(*, closure_packet: dict[str, Any], acquisition_packet: dict[str, Any]) -> dict[str, Any]:
    closure = _summary(closure_packet)
    acquisition = _summary(acquisition_packet)
    acquisition_by_target = _acquisition_rows_by_target(acquisition_packet)
    rows: list[dict[str, Any]] = []

    for closure_row in _rows(closure_packet):
        target = _text(closure_row.get("target_id"))
        slot_rows = acquisition_by_target.get(_target_alias(target), []) or acquisition_by_target.get(target, [])
        unresolved_slots = len(slot_rows)
        local_sync_slots = _local_sync_ready_count(slot_rows)
        manual_or_external = _manual_or_external_required(slot_rows)
        first_step, first_action = _first_action(slot_rows, _text(closure_row.get("next_action")))
        auto_close_ready = (
            unresolved_slots == 0
            and _int(closure_row.get("remaining_placeholder_rows_after_apply")) == 0
            and closure_row.get("authoritative_apply_allowed") is True
        )
        rows.append(
            {
                "target_id": target,
                "step_id": _text(closure_row.get("step_id")),
                "artifact": _text(closure_row.get("artifact")),
                "repo_path": _text(closure_row.get("repo_path")),
                "blocker": _text(closure_row.get("blocker")),
                "unresolved_slot_count": unresolved_slots,
                "local_sync_ready_slot_count": local_sync_slots,
                "manual_or_external_required": manual_or_external,
                "auto_close_ready": auto_close_ready,
                "close_when": _text(closure_row.get("close_when")),
                "evidence_required": _text(closure_row.get("evidence_required")),
                "first_required_slot_step": first_step,
                "next_required_action": first_action,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    auto_close_rows = [row for row in rows if row["auto_close_ready"]]
    manual_or_external_rows = [row for row in rows if row["manual_or_external_required"]]
    first_required = next((row for row in manual_or_external_rows if row["next_required_action"]), {})
    slot_auto_close_ready = sum(row["local_sync_ready_slot_count"] for row in rows)
    external_exact_slots = _int(acquisition.get("exact_evidence_request_slot_count"))
    summary = {
        "packet_type": "transporter_p0_closure_readiness_matrix",
        "readiness_matrix_ready": True,
        "closure_row_count": len(rows),
        "current_membrane_p0_open_count": _int(closure.get("current_membrane_p0_open_count")),
        "auto_close_ready_artifact_count": len(auto_close_rows),
        "manual_or_external_required_artifact_count": len(manual_or_external_rows),
        "unresolved_slot_count": _int(acquisition.get("unresolved_slot_count")),
        "auto_close_ready_slot_count": slot_auto_close_ready,
        "external_exact_evidence_required_slot_count": external_exact_slots,
        "aqp1_core_p0_open_count": _int(closure.get("aqp1_core_p0_open_count")),
        "glut1_core_p0_open_count": _int(closure.get("glut1_core_p0_open_count")),
        "first_manual_or_external_required_target_id": _text(first_required.get("target_id")),
        "first_manual_or_external_required_step_id": _text(first_required.get("step_id")),
        "first_manual_or_external_required_slot_step": _text(first_required.get("first_required_slot_step")),
        "first_manual_or_external_required_action": _text(first_required.get("next_required_action")),
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            _text(first_required.get("next_required_action"))
            or "No open transporter P0 closure artifacts remain; rerun membrane readiness and donor-policy gates."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transporter P0 Closure Readiness Matrix",
        "",
        f"- readiness_matrix_ready: `{s['readiness_matrix_ready']}`",
        f"- current_membrane_p0_open_count: `{s['current_membrane_p0_open_count']}`",
        f"- closure_row_count: `{s['closure_row_count']}`",
        f"- auto_close_ready_artifact_count: `{s['auto_close_ready_artifact_count']}`",
        f"- manual_or_external_required_artifact_count: `{s['manual_or_external_required_artifact_count']}`",
        f"- unresolved_slot_count: `{s['unresolved_slot_count']}`",
        f"- auto_close_ready_slot_count: `{s['auto_close_ready_slot_count']}`",
        f"- external_exact_evidence_required_slot_count: `{s['external_exact_evidence_required_slot_count']}`",
        "",
        "## Artifact Rows",
        "",
        "| target | step | artifact | auto close | manual/external | unresolved slots | local sync slots | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['step_id']}` | `{row['artifact']}` | "
            f"`{row['auto_close_ready']}` | `{row['manual_or_external_required']}` | "
            f"`{row['unresolved_slot_count']}` | `{row['local_sync_ready_slot_count']}` | "
            f"{row['next_required_action']} |"
        )
    if not payload["rows"]:
        lines.append("| `none` | `none` | `none` | `False` | `False` | `0` | `0` | no open rows |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter P0 closure readiness matrix.")
    parser.add_argument("--closure-json", default=str(DEFAULT_CLOSURE_JSON))
    parser.add_argument("--acquisition-json", default=str(DEFAULT_ACQUISITION_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        closure_packet=_load_json(args.closure_json),
        acquisition_packet=_load_json(args.acquisition_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
