#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_MEMBRANE_READINESS_JSON = RUNS / "transporter_membrane_readiness_current.json"
DEFAULT_AQP1_PLAN_JSON = RUNS / "aqp1_p0_packet_plan_current.json"
DEFAULT_GLUT1_PLAN_JSON = RUNS / "glut1_p0_packet_plan_current.json"
DEFAULT_GLUT1_APPLY_JSON = RUNS / "glut1_ready_workbook_apply_current.json"
DEFAULT_AQP1_APPLY_JSON = RUNS / "aqp1_ready_workbook_apply_current.json"
DEFAULT_BINDER_GATE_JSON = RUNS / "transporter_binder_promotion_gate_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_p0_closure_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_p0_closure_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_p0_closure_packet_current.md"

CORE_P0_ARTIFACTS = {"ligand_reference_csv", "eval_split_csv", "ligand_meta_csv"}
APPLY_PLACEHOLDER_KEYS = {
    "ligand_reference_csv": "reference",
    "eval_split_csv": "split",
    "ligand_meta_csv": "meta",
}
CLAIM_BOUNDARY = (
    "Transporter P0 closure packet only; expands current dry-run scaffold blockers into exact local closure rows. "
    "It does not authoritatively apply ligand rows, reopen donor policy, run docking, widen product scope, upload, "
    "submit, email, delete, or mutate external state."
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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _close_when(target_id: str, artifact: str, blocker: str) -> str:
    if artifact == "ligand_reference_csv":
        return (
            f"{target_id} ligand reference rows contain no placeholder ligand/source rows and every promoted row has "
            "claim-safe target-specific provenance."
        )
    if artifact == "eval_split_csv":
        return f"{target_id} split roles are synchronized to the frozen curated ligand packet with no placeholder ligand ids."
    if artifact == "ligand_meta_csv":
        return f"{target_id} ligand metadata rows are synchronized to the frozen ligand packet with no placeholder scaffold/meta rows."
    return f"{target_id} blocker {blocker or artifact} is resolved in the authoritative local packet."


def _evidence_required(target_id: str, artifact: str) -> str:
    if target_id == "Aquaporin_1":
        return (
            "Curated AQP1 binder and quantitative negative/non-binder packet evidence, then synchronized "
            "reference/split/meta CSV rows."
        )
    if target_id == "GLUT1_4PYP":
        return (
            "Complete the GLUT1 synchronized packet beyond the one ready cytochalasin B row; keep WZB117/STF-31 "
            "review-only unless direct claim-safe binding kcal evidence is added."
        )
    return "Target-specific transporter packet evidence and synchronized local CSV rows."


def _apply_annotation(apply_summary: dict[str, Any]) -> str:
    if not apply_summary:
        return "apply_receipt_missing"
    applied = _int(apply_summary.get("applied_row_count"))
    blocked = _int(apply_summary.get("blocked_ready_row_count"))
    ref_left = _int(apply_summary.get("after_reference_placeholder_rows"))
    split_left = _int(apply_summary.get("after_split_placeholder_rows"))
    meta_left = _int(apply_summary.get("after_meta_placeholder_rows"))
    full_ready = bool(apply_summary.get("full_packet_ready_after_apply"))
    return (
        f"apply_receipt applied_rows={applied} blocked_ready_rows={blocked} "
        f"remaining_placeholders=reference:{ref_left},split:{split_left},meta:{meta_left} "
        f"full_packet_ready_after_apply={full_ready}"
    )


def _glut1_apply_annotation(apply_summary: dict[str, Any]) -> str:
    return _apply_annotation(apply_summary)


def _open_core_rows(
    plan_payload: dict[str, Any],
    target_id: str,
    *,
    apply_summary: dict[str, Any] | None = None,
    apply_receipt_path: str = "",
) -> list[dict[str, Any]]:
    rows = []
    for row in plan_payload.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        if _text(row.get("status")) != "todo":
            continue
        artifact = _text(row.get("artifact"))
        if artifact not in CORE_P0_ARTIFACTS:
            continue
        blocker = _text(row.get("blocker"))
        apply_annotation = _apply_annotation(apply_summary or {}) if apply_summary else ""
        detail = _text(row.get("detail"))
        if apply_annotation and apply_annotation != "apply_receipt_missing":
            detail = f"{detail}; {apply_annotation}" if detail else apply_annotation
        rows.append(
            {
                "target_id": target_id,
                "step_id": _text(row.get("step_id")),
                "artifact": artifact,
                "blocker": blocker,
                "repo_path": _text(row.get("repo_path")),
                "detail": detail,
                "next_action": _text(row.get("next_action")),
                "close_when": _close_when(target_id, artifact, blocker),
                "evidence_required": _evidence_required(target_id, artifact),
                "authoritative_apply_receipt": apply_receipt_path if apply_summary else "",
                "authoritative_apply_applied_rows": _int((apply_summary or {}).get("applied_row_count")),
                "authoritative_apply_blocked_rows": _int((apply_summary or {}).get("blocked_ready_row_count")),
                "remaining_placeholder_rows_after_apply": (
                    _int(
                        (apply_summary or {}).get(
                            f"after_{APPLY_PLACEHOLDER_KEYS[artifact]}_placeholder_rows"
                        )
                    )
                    if apply_summary and artifact in CORE_P0_ARTIFACTS
                    else 0
                ),
                "authoritative_apply_allowed": False,
                "donor_policy_reopen_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )
    return rows


def build_payload(
    *,
    membrane_readiness_payload: dict[str, Any],
    aqp1_plan_payload: dict[str, Any],
    glut1_plan_payload: dict[str, Any],
    aqp1_apply_payload: dict[str, Any],
    glut1_apply_payload: dict[str, Any],
    binder_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    membrane = _summary(membrane_readiness_payload)
    aqp1 = _summary(aqp1_plan_payload)
    glut1 = _summary(glut1_plan_payload)
    aqp1_apply = _summary(aqp1_apply_payload)
    glut1_apply = _summary(glut1_apply_payload)
    binder = _summary(binder_gate_payload)

    rows = _open_core_rows(
        aqp1_plan_payload,
        "Aquaporin_1",
        apply_summary=aqp1_apply,
        apply_receipt_path="runs/aqp1_ready_workbook_apply_current.json",
    ) + _open_core_rows(
        glut1_plan_payload,
        "GLUT1_4PYP",
        apply_summary=glut1_apply,
        apply_receipt_path="runs/glut1_ready_workbook_apply_current.json",
    )
    target_counts: dict[str, int] = {}
    for row in rows:
        target_counts[row["target_id"]] = target_counts.get(row["target_id"], 0) + 1

    current_p0_open = _int(membrane.get("p0_open_count"))
    closure_row_count = len(rows)
    p0_count_matches_readiness = current_p0_open == closure_row_count
    summary = {
        "packet_type": "transporter_p0_closure_packet",
        "p0_closure_packet_ready": True,
        "current_membrane_p0_open_count": current_p0_open,
        "closure_row_count": closure_row_count,
        "p0_count_matches_readiness": p0_count_matches_readiness,
        "aqp1_core_p0_open_count": target_counts.get("Aquaporin_1", 0),
        "glut1_core_p0_open_count": target_counts.get("GLUT1_4PYP", 0),
        "aqp1_plan_todo_count": _int(aqp1.get("todo_count")),
        "glut1_plan_todo_count": _int(glut1.get("todo_count")),
        "glut1_ready_workbook_apply_receipt_present": bool(glut1_apply),
        "glut1_ready_workbook_applied_row_count": _int(glut1_apply.get("applied_row_count")),
        "glut1_ready_workbook_newly_applied_row_count": _int(glut1_apply.get("newly_applied_row_count")),
        "glut1_ready_workbook_already_applied_row_count": _int(glut1_apply.get("already_applied_row_count")),
        "glut1_ready_workbook_blocked_ready_row_count": _int(glut1_apply.get("blocked_ready_row_count")),
        "glut1_reference_placeholder_rows_after_apply": _int(glut1_apply.get("after_reference_placeholder_rows")),
        "glut1_split_placeholder_rows_after_apply": _int(glut1_apply.get("after_split_placeholder_rows")),
        "glut1_meta_placeholder_rows_after_apply": _int(glut1_apply.get("after_meta_placeholder_rows")),
        "glut1_full_packet_ready_after_apply": bool(glut1_apply.get("full_packet_ready_after_apply")),
        "aqp1_ready_workbook_apply_receipt_present": bool(aqp1_apply),
        "aqp1_ready_workbook_applied_row_count": _int(aqp1_apply.get("applied_row_count")),
        "aqp1_ready_workbook_newly_applied_row_count": _int(aqp1_apply.get("newly_applied_row_count")),
        "aqp1_ready_workbook_already_applied_row_count": _int(aqp1_apply.get("already_applied_row_count")),
        "aqp1_ready_workbook_blocked_ready_row_count": _int(aqp1_apply.get("blocked_ready_row_count")),
        "aqp1_reference_placeholder_rows_after_apply": _int(aqp1_apply.get("after_reference_placeholder_rows")),
        "aqp1_split_placeholder_rows_after_apply": _int(aqp1_apply.get("after_split_placeholder_rows")),
        "aqp1_meta_placeholder_rows_after_apply": _int(aqp1_apply.get("after_meta_placeholder_rows")),
        "aqp1_full_packet_ready_after_apply": bool(aqp1_apply.get("full_packet_ready_after_apply")),
        "claim_safe_binder_ready_count": _int(binder.get("claim_safe_kcal_ready_count")),
        "authoritative_binder_apply_allowed_count": _int(binder.get("authoritative_binder_apply_allowed_count")),
        "donor_policy_reopen_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Close the remaining AQP1 ligand reference/split/meta P0 rows with claim-safe direct-binding kcal, "
            "external-evidence intake approval, and synchronized workbook apply; GLUT1 placeholders are already closed."
            if rows and target_counts.get("GLUT1_4PYP", 0) == 0 and target_counts.get("Aquaporin_1", 0) > 0
            else "Close the six core transporter P0 rows by synchronizing AQP1 and the remaining GLUT1 ligand "
            "reference/split/meta placeholders; only then rerun membrane readiness and donor-policy reopen gates."
            if rows
            else "No transporter core P0 rows remain; rerun membrane readiness and donor-policy reopen gates."
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
        "# Transporter P0 Closure Packet",
        "",
        f"- p0_closure_packet_ready: `{s['p0_closure_packet_ready']}`",
        f"- current_membrane_p0_open_count: `{s['current_membrane_p0_open_count']}`",
        f"- closure_row_count: `{s['closure_row_count']}`",
        f"- p0_count_matches_readiness: `{s['p0_count_matches_readiness']}`",
        f"- aqp1_core_p0_open_count: `{s['aqp1_core_p0_open_count']}`",
        f"- glut1_core_p0_open_count: `{s['glut1_core_p0_open_count']}`",
        f"- glut1_ready_workbook_apply_receipt_present: `{s['glut1_ready_workbook_apply_receipt_present']}`",
        f"- glut1_ready_workbook_applied_row_count: `{s['glut1_ready_workbook_applied_row_count']}`",
        f"- glut1_ready_workbook_blocked_ready_row_count: `{s['glut1_ready_workbook_blocked_ready_row_count']}`",
        f"- glut1_remaining_placeholders_after_apply: "
        f"`reference={s['glut1_reference_placeholder_rows_after_apply']};"
        f"split={s['glut1_split_placeholder_rows_after_apply']};"
        f"meta={s['glut1_meta_placeholder_rows_after_apply']}`",
        f"- glut1_full_packet_ready_after_apply: `{s['glut1_full_packet_ready_after_apply']}`",
        f"- claim_safe_binder_ready_count: `{s['claim_safe_binder_ready_count']}`",
        f"- authoritative_binder_apply_allowed_count: `{s['authoritative_binder_apply_allowed_count']}`",
        f"- donor_policy_reopen_allowed: `{s['donor_policy_reopen_allowed']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Closure Rows",
        "",
        "| target | step | artifact | blocker | repo path | close when |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['step_id']}` | `{row['artifact']}` | "
            f"`{row['blocker'] or '-'}` | `{row['repo_path']}` | {row['close_when']} |"
        )
    if not payload["rows"]:
        lines.append("| `none` | `none` | `none` | `-` | `-` | no open core P0 rows |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter P0 closure packet from AQP1/GLUT1 plans.")
    parser.add_argument("--membrane-readiness-json", default=str(DEFAULT_MEMBRANE_READINESS_JSON))
    parser.add_argument("--aqp1-plan-json", default=str(DEFAULT_AQP1_PLAN_JSON))
    parser.add_argument("--glut1-plan-json", default=str(DEFAULT_GLUT1_PLAN_JSON))
    parser.add_argument("--aqp1-apply-json", default=str(DEFAULT_AQP1_APPLY_JSON))
    parser.add_argument("--glut1-apply-json", default=str(DEFAULT_GLUT1_APPLY_JSON))
    parser.add_argument("--binder-gate-json", default=str(DEFAULT_BINDER_GATE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        membrane_readiness_payload=_load_json(args.membrane_readiness_json),
        aqp1_plan_payload=_load_json(args.aqp1_plan_json),
        glut1_plan_payload=_load_json(args.glut1_plan_json),
        aqp1_apply_payload=_load_json(args.aqp1_apply_json),
        glut1_apply_payload=_load_json(args.glut1_apply_json),
        binder_gate_payload=_load_json(args.binder_gate_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
