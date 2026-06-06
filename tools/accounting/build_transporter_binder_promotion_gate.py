#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC_JSON = "runs/transporter_binder_decision_rubric_current.json"
DEFAULT_AQP1_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_GLUT1_SOURCE_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_GLUT1_CLAIM_SAFE_KCAL_JSON = "runs/glut1_claim_safe_binding_kcal_packet_current.json"
DEFAULT_AQP1_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_WORKBOOK_JSON = "runs/glut1_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = "runs/transporter_binder_promotion_gate_current.json"
DEFAULT_OUT_CSV = "runs/transporter_binder_promotion_gate_current.csv"
DEFAULT_OUT_MD = "runs/transporter_binder_promotion_gate_current.md"


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
    return json.loads(path.read_text(encoding="utf-8"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_text(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "pass", "ready"}


def _workbook_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("workbook_rows", []) or []
        if _text(row.get("packet_step"))
    }


def _provenance_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _claim_safe_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
        and _text(row.get("claim_safe_binding_kcal_ready")).lower() == "yes"
    }


def _target_support_row(
    *,
    target_id: str,
    packet_step: str,
    aqp1_provenance_by_step: dict[str, dict[str, Any]],
    glut1_source_by_step: dict[str, dict[str, Any]],
    glut1_claim_safe_by_step: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if target_id == "AQP1":
        row = aqp1_provenance_by_step.get(packet_step, {})
        return {
            "claim_safe_kcal_ready": _bool_text(row.get("claim_safe_binding_kcal_ready")),
            "provenance_signal": _text(row.get("public_provenance_signal")),
            "assay_type_honesty": _text(row.get("assay_type_honesty")),
            "source_artifact": DEFAULT_AQP1_PROVENANCE_JSON,
            "source_url": _text(row.get("source_url")),
        }
    if target_id == "GLUT1":
        claim_safe = (glut1_claim_safe_by_step or {}).get(packet_step, {})
        if claim_safe:
            return {
                "claim_safe_kcal_ready": True,
                "provenance_signal": _text(claim_safe.get("delta_g_method")) or "direct_binding_kcal_curated",
                "assay_type_honesty": "direct_quantitative_binding_kd_delta_g_proxy",
                "source_artifact": DEFAULT_GLUT1_CLAIM_SAFE_KCAL_JSON,
                "source_url": _text(claim_safe.get("source_url")),
                "manual_verdict": _text(claim_safe.get("manual_verdict")),
            }
        row = glut1_source_by_step.get(packet_step, {})
        return {
            "claim_safe_kcal_ready": _bool_text(row.get("claim_safe_binding_kcal_ready")),
            "provenance_signal": _text(row.get("public_provenance_signal")),
            "assay_type_honesty": _text(row.get("assay_type_honesty")),
            "source_artifact": DEFAULT_GLUT1_SOURCE_JSON,
            "source_url": _text(row.get("source_url")),
            "manual_verdict": "",
        }
    return {
        "claim_safe_kcal_ready": False,
        "provenance_signal": "",
        "assay_type_honesty": "",
        "source_artifact": "",
        "source_url": "",
        "manual_verdict": "",
    }


def build_payload(
    rubric: dict[str, Any],
    aqp1_provenance: dict[str, Any],
    glut1_source: dict[str, Any],
    aqp1_workbook: dict[str, Any],
    glut1_workbook: dict[str, Any],
    glut1_claim_safe_kcal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aqp1_workbook_by_step = _workbook_rows_by_step(aqp1_workbook)
    glut1_workbook_by_step = _workbook_rows_by_step(glut1_workbook)
    aqp1_provenance_by_step = _provenance_rows_by_step(aqp1_provenance)
    glut1_source_by_step = _provenance_rows_by_step(glut1_source)
    glut1_claim_safe_by_step = _claim_safe_rows_by_step(glut1_claim_safe_kcal or {})

    rows: list[dict[str, Any]] = []
    for rubric_row in rubric.get("rows", []) or []:
        target_id = _text(rubric_row.get("target_id"))
        packet_step = _text(rubric_row.get("packet_step"))
        workbook = (
            aqp1_workbook_by_step.get(packet_step, {})
            if target_id == "AQP1"
            else glut1_workbook_by_step.get(packet_step, {})
        )
        support = _target_support_row(
            target_id=target_id,
            packet_step=packet_step,
            aqp1_provenance_by_step=aqp1_provenance_by_step,
            glut1_source_by_step=glut1_source_by_step,
            glut1_claim_safe_by_step=glut1_claim_safe_by_step,
        )
        workbook_ready = _text(workbook.get("row_ready_for_apply")).lower() == "yes"
        verdict = _text(support.get("manual_verdict")) or _text(rubric_row.get("current_recommended_verdict"))
        blocker = "" if support.get("manual_verdict") == "promote_authoritative_apply" else _text(rubric_row.get("authoritative_apply_blocker"))
        authoritative_allowed = (
            workbook_ready
            and support["claim_safe_kcal_ready"]
            and verdict not in {"keep_review_only", "defer", ""}
            and not blocker
        )
        if authoritative_allowed:
            promotion_blocker = ""
            next_action = "authoritative binder row can be promoted through the transporter donor policy gate."
        elif not support["claim_safe_kcal_ready"]:
            promotion_blocker = "claim_safe_binding_kcal_missing"
            next_action = "curate direct binding or a claim-safe kcal anchor before binder promotion."
        elif not workbook_ready:
            promotion_blocker = "workbook_row_not_ready_for_apply"
            next_action = "complete synchronized reference/split/meta workbook fields before binder promotion."
        else:
            promotion_blocker = "review_verdict_not_authoritative"
            next_action = "upgrade reviewer verdict only after evidence and workbook rows are claim-safe."
        rows.append(
            {
                "target_id": target_id,
                "packet_step": packet_step,
                "candidate_name": _text(rubric_row.get("candidate_name")),
                "current_recommended_verdict": verdict,
                "workbook_row_ready_for_apply": workbook_ready,
                "claim_safe_kcal_ready": support["claim_safe_kcal_ready"],
                "provenance_signal": support["provenance_signal"],
                "assay_type_honesty": support["assay_type_honesty"],
                "source_artifact": support["source_artifact"],
                "source_url": support["source_url"],
                "claim_safe_override_applied": bool(support.get("manual_verdict")),
                "authoritative_binder_apply_allowed": authoritative_allowed,
                "promotion_blocker": promotion_blocker,
                "next_action": next_action,
            }
        )

    allowed_rows = [row for row in rows if row["authoritative_binder_apply_allowed"]]
    claim_safe_rows = [row for row in rows if row["claim_safe_kcal_ready"]]
    workbook_ready_rows = [row for row in rows if row["workbook_row_ready_for_apply"]]
    target_ids = sorted({row["target_id"] for row in rows if row["target_id"]})
    target_ready_ids = [
        target_id
        for target_id in target_ids
        if any(row["target_id"] == target_id and row["authoritative_binder_apply_allowed"] for row in rows)
    ]
    target_blocked_ids = [target_id for target_id in target_ids if target_id not in target_ready_ids]
    first_blocked_row = next((row for row in rows if not row["authoritative_binder_apply_allowed"]), {})
    summary = {
        "binder_promotion_gate_ready": True,
        "binder_slot_count": len(rows),
        "claim_safe_kcal_ready_count": len(claim_safe_rows),
        "workbook_ready_binder_row_count": len(workbook_ready_rows),
        "authoritative_binder_apply_allowed_count": len(allowed_rows),
        "binder_promotion_ready": bool(allowed_rows),
        "target_count": len(target_ids),
        "target_ready_for_promotion_count": len(target_ready_ids),
        "target_blocked_for_promotion_count": len(target_blocked_ids),
        "target_ready_for_promotion_ids": target_ready_ids,
        "target_blocked_for_promotion_ids": target_blocked_ids,
        "primary_blocker_target_id": _text(first_blocked_row.get("target_id")),
        "primary_blocker_packet_step": _text(first_blocked_row.get("packet_step")),
        "primary_blocker_candidate_name": _text(first_blocked_row.get("candidate_name")),
        "primary_blocker": "none" if allowed_rows else rows[0]["promotion_blocker"] if rows else "no_binder_rows",
        "primary_blocker_signal": (
            f"claim_safe_kcal_ready_count={len(claim_safe_rows)};"
            f"workbook_ready_binder_row_count={len(workbook_ready_rows)};"
            f"authoritative_binder_apply_allowed_count={len(allowed_rows)};"
            f"target_ready_for_promotion_ids={','.join(target_ready_ids)};"
            f"target_blocked_for_promotion_ids={','.join(target_blocked_ids)}"
        ),
        "next_required_step": (
            "All transporter binder targets have at least one promotion-ready row; rerun donor policy and scope breadth gates."
            if target_ids and not target_blocked_ids
            else (
                "Some transporter binder rows are promotion-ready, but target-scoped blockers remain; keep blocked targets out of scope promotion."
                if allowed_rows
                else "Curate a claim-safe binding/kcal anchor and complete a synchronized workbook row before reopening transporter donor policy."
            )
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
        "# Transporter Binder Promotion Gate",
        "",
        f"- binder_promotion_gate_ready: `{s['binder_promotion_gate_ready']}`",
        f"- binder_slot_count: `{s['binder_slot_count']}`",
        f"- claim_safe_kcal_ready_count: `{s['claim_safe_kcal_ready_count']}`",
        f"- workbook_ready_binder_row_count: `{s['workbook_ready_binder_row_count']}`",
        f"- authoritative_binder_apply_allowed_count: `{s['authoritative_binder_apply_allowed_count']}`",
        f"- binder_promotion_ready: `{s['binder_promotion_ready']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        f"- primary_blocker_signal: `{s['primary_blocker_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Binder Rows",
        "",
        "| target | step | candidate | verdict | workbook_ready | claim_safe_kcal | authoritative_allowed | blocker | provenance_signal |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['current_recommended_verdict']}` | `{row['workbook_row_ready_for_apply']}` | "
            f"`{row['claim_safe_kcal_ready']}` | `{row['authoritative_binder_apply_allowed']}` | "
            f"`{row['promotion_blocker'] or '-'}` | `{row['provenance_signal'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed transporter binder promotion gate.")
    parser.add_argument("--rubric-json", default=DEFAULT_RUBRIC_JSON)
    parser.add_argument("--aqp1-provenance-json", default=DEFAULT_AQP1_PROVENANCE_JSON)
    parser.add_argument("--glut1-source-json", default=DEFAULT_GLUT1_SOURCE_JSON)
    parser.add_argument("--glut1-claim-safe-kcal-json", default=DEFAULT_GLUT1_CLAIM_SAFE_KCAL_JSON)
    parser.add_argument("--aqp1-workbook-json", default=DEFAULT_AQP1_WORKBOOK_JSON)
    parser.add_argument("--glut1-workbook-json", default=DEFAULT_GLUT1_WORKBOOK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        _load_json(args.rubric_json),
        _load_json(args.aqp1_provenance_json),
        _load_json(args.glut1_source_json),
        _load_json(args.aqp1_workbook_json),
        _load_json(args.glut1_workbook_json),
        _load_json(args.glut1_claim_safe_kcal_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
