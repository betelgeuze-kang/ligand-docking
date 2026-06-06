#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_GATE_JSON = RUNS / "pxr_blocked_row_promotion_gate_current.json"
DEFAULT_FILL_READINESS_JSON = RUNS / "pxr_packet_fill_readiness_current.json"
DEFAULT_WORKBOOK_JSON = RUNS / "pxr_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = RUNS / "pxr_blocked_evidence_request_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_blocked_evidence_request_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_blocked_evidence_request_packet_current.md"

TARGET = "PXR_NR1I2_BLIND"
TARGET_GENE = "NR1I2"
TARGET_ALIAS = "PXR/SXR"
ACCEPTABLE_BINDER_ENDPOINTS = "Kd;Ki;IC50;EC50;AC50;target-specific activation or binding proxy with explicit curve context"
ACCEPTABLE_NEGATIVE_ENDPOINTS = "inactive/no-activation/no-binding with explicit tested range, threshold, assay context, and human NR1I2/PXR target-pair provenance"
REQUIRED_FIELDS = (
    "packet_step;candidate_name;target_gene;target_alias;target_organism;assay_context;endpoint;"
    "standard_relation;standard_value;standard_units;curve_or_tested_range;primary_source;source_url;"
    "replacement_reference_binding_kcal_mol_or_reason_to_keep_blank;reference_meta_update"
)
EXCLUDED_SHORTCUTS = "RXR-only affinity;CYP3A induction only;review-only summary;non-human-only support;conflicted qHTS without orthogonal resolution"


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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _rows_by_step(payload: dict[str, Any], row_key: str = "rows") -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get(row_key, []) or []
        if isinstance(row, dict) and _text(row.get("packet_step"))
    }


def _readiness_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _rows_by_step(payload, "readiness_rows")


def _request_mode(row: dict[str, Any]) -> str:
    if _text(row.get("binder")) == "1":
        return "exact_human_pxr_quantitative_binder_value_required"
    bucket = _text(row.get("review_bucket"))
    if bucket.startswith("defer"):
        return "exact_human_pxr_conflict_resolution_or_negative_quantitative_value_required"
    return "exact_human_pxr_negative_or_inactive_quantitative_value_required"


def _minimum_acceptance_rule(row: dict[str, Any]) -> str:
    if _text(row.get("binder")) == "1":
        return (
            "Attach an exact human NR1I2/PXR/SXR target-pair quantitative binder value or claim-safe activity proxy "
            "with units, curve context, and primary-source provenance."
        )
    return (
        "Attach exact human NR1I2/PXR/SXR target-pair quantitative negative/inactive evidence; otherwise keep the "
        "row review-only or deferred and leave reference kcal blank."
    )


def build_payload(
    *,
    gate_payload: dict[str, Any],
    fill_readiness_payload: dict[str, Any],
    workbook_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness_by_step = _readiness_rows_by_step(fill_readiness_payload)
    workbook_by_step = _rows_by_step(workbook_payload, "workbook_rows")
    rows: list[dict[str, Any]] = []

    for rank, gate_row in enumerate(gate_payload.get("rows", []) or [], start=1):
        if not isinstance(gate_row, dict):
            continue
        packet_step = _text(gate_row.get("packet_step"))
        if not packet_step:
            continue
        readiness = readiness_by_step.get(packet_step, {})
        workbook = workbook_by_step.get(packet_step, {})
        binder = _text(gate_row.get("binder")) or _text(workbook.get("replacement_is_binder"))
        ligand = _text(gate_row.get("ligand")) or _text(workbook.get("replacement_ligand_id"))
        missing = _text(gate_row.get("readiness_missing_fields")) or _text(readiness.get("required_missing_fields"))
        blockers = _text(gate_row.get("fail_closed_blockers"))
        request_mode = _request_mode({**gate_row, "binder": binder})
        rows.append(
            {
                "request_rank": rank,
                "packet": _text(readiness.get("packet")) or _text(gate_row.get("packet")),
                "packet_step": packet_step,
                "target": TARGET,
                "target_gene": TARGET_GENE,
                "target_alias": TARGET_ALIAS,
                "candidate_name": ligand,
                "candidate_pubchem_cid": _text(workbook.get("replacement_pubchem_cid")),
                "current_role": _text(workbook.get("replacement_role")),
                "current_binder_label": "binder" if binder == "1" else "non_binder",
                "request_mode": request_mode,
                "review_bucket": _text(gate_row.get("review_bucket")),
                "missing_fields": missing,
                "fail_closed_blockers": blockers,
                "evidence_signal": _text(gate_row.get("evidence_signal")),
                "acceptable_endpoints": ACCEPTABLE_BINDER_ENDPOINTS if binder == "1" else ACCEPTABLE_NEGATIVE_ENDPOINTS,
                "minimum_required_fields": REQUIRED_FIELDS,
                "excluded_shortcuts": EXCLUDED_SHORTCUTS,
                "minimum_acceptance_rule": _minimum_acceptance_rule({**gate_row, "binder": binder}),
                "requested_output_schema": (
                    "packet_step,candidate_name,target_gene,target_alias,assay_context,endpoint,standard_relation,"
                    "standard_value,standard_units,curve_or_tested_range,primary_source,source_url,"
                    "replacement_reference_binding_kcal_mol_or_reason_to_keep_blank,reference_meta_update"
                ),
                "request_status": "open",
                "authoritative_apply_allowed": False,
                "claim_promotion_allowed": False,
                "next_required_action": (
                    "Acquire exact human NR1I2/PXR quantitative evidence that directly resolves this row, then rerun PXR packet-fill and promotion gates."
                ),
            }
        )

    binder_rows = [row for row in rows if row["current_binder_label"] == "binder"]
    negative_rows = [row for row in rows if row["current_binder_label"] == "non_binder"]
    defer_rows = [row for row in rows if str(row["review_bucket"]).startswith("defer")]
    review_only_rows = [row for row in rows if str(row["review_bucket"]).startswith("review_only")]
    summary = {
        "evidence_request_ready": True,
        "packet_artifact": "runs/pxr_blocked_evidence_request_packet_current.md",
        "source_gate_artifact": "runs/pxr_blocked_row_promotion_gate_current.md",
        "target": TARGET,
        "target_gene": TARGET_GENE,
        "target_alias": TARGET_ALIAS,
        "request_row_count": len(rows),
        "binder_request_row_count": len(binder_rows),
        "negative_request_row_count": len(negative_rows),
        "defer_request_row_count": len(defer_rows),
        "review_only_request_row_count": len(review_only_rows),
        "claim_safe_quantitative_ready_count": _int((gate_payload.get("summary") or {}).get("claim_safe_quantitative_ready_count")),
        "authoritative_apply_allowed_count": _int((gate_payload.get("summary") or {}).get("authoritative_apply_allowed_count")),
        "blocked_row_count": _int((gate_payload.get("summary") or {}).get("blocked_row_count")) or len(rows),
        "missing_field_focus": "replacement_reference_binding_kcal_mol",
        "acceptable_binder_endpoints": ACCEPTABLE_BINDER_ENDPOINTS,
        "acceptable_negative_endpoints": ACCEPTABLE_NEGATIVE_ENDPOINTS,
        "minimum_required_fields": REQUIRED_FIELDS,
        "excluded_shortcuts": EXCLUDED_SHORTCUTS,
        "request_status": "ready_for_public_or_internal_exact_evidence_acquisition",
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Use this packet to fill exact human NR1I2/PXR quantitative evidence rows; do not promote blocked PXR rows until packet-fill readiness has zero blocked rows."
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
        "# PXR Blocked Evidence Request Packet",
        "",
        f"- evidence_request_ready: `{s['evidence_request_ready']}`",
        f"- source_gate_artifact: `{s['source_gate_artifact']}`",
        f"- target: `{s['target']}`",
        f"- target_gene: `{s['target_gene']}`",
        f"- request_row_count: `{s['request_row_count']}`",
        f"- binder_request_row_count: `{s['binder_request_row_count']}`",
        f"- negative_request_row_count: `{s['negative_request_row_count']}`",
        f"- defer_request_row_count: `{s['defer_request_row_count']}`",
        f"- review_only_request_row_count: `{s['review_only_request_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- missing_field_focus: `{s['missing_field_focus']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- request_status: `{s['request_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Request Rows",
        "",
        "| rank | step | candidate | label | mode | missing | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['request_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['current_binder_label']}` | `{row['request_mode']}` | "
            f"`{row['missing_fields'] or '-'}` | `{row['fail_closed_blockers'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a PXR exact-evidence request packet for blocked rows.")
    parser.add_argument("--gate-json", default=str(DEFAULT_GATE_JSON))
    parser.add_argument("--fill-readiness-json", default=str(DEFAULT_FILL_READINESS_JSON))
    parser.add_argument("--workbook-json", default=str(DEFAULT_WORKBOOK_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        gate_payload=_load_json(args.gate_json),
        fill_readiness_payload=_load_json(args.fill_readiness_json),
        workbook_payload=_load_json(args.workbook_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
