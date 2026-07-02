#!/usr/bin/env python3
"""Build the PocketMD Lite top-k refinement audit.

Read-only: this packet joins the top-k PocketMD Lite report with the metric
collection probe. It reports both claim-grade refinement fields and available
coarse proxy telemetry, while keeping claim-grade gates fail-closed whenever
local-min, H-bond, or clash-relief baseline evidence is missing from the report
or exact metric fill preview.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from betelgeuze_product.pocketmd_lite_contract import (
    BAND_ABSTAIN,
    BAND_COARSE_ONLY,
    BAND_GREEN,
    BAND_RED,
    BAND_YELLOW,
    CONTACT_PERSISTENCE_MIN,
    HBOND_PERSISTENCE_MIN,
    LOCAL_MIN_SURVIVAL_RMSD_A,
    MAX_CLASH_COUNT,
    build_pocketmd_lite_assessment,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPORT_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json"
DEFAULT_PROBE_JSON = "runs/pocketmd_lite_metric_collection_probe_current.json"
DEFAULT_REMAINING_QUEUE_JSON = "runs/pocketmd_lite_remaining_evidence_queue_current.json"
DEFAULT_CANDIDATE_FILL_PREVIEW_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_current.json"
DEFAULT_METRIC_SOURCE_AUDIT_JSON = "runs/pocketmd_lite_claim_grade_metric_source_audit_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_topk_refinement_audit_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_topk_refinement_audit_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_topk_refinement_audit_current.csv"

PACKET_TYPE = "pocketmd_lite_topk_refinement_audit"
SCHEMA_VERSION = "pocketmd_lite_topk_refinement_audit_v1"

CLAIM_BOUNDARY = (
    "PocketMD Lite top-k refinement audit only. It reports top-k selection, claim-grade refinement evidence, "
    "exact metric fill-preview overlays, and available coarse proxy telemetry side by side. Only exact metric "
    "fill-preview rows derived from claim-grade probes may fill local-min, H-bond, or baseline clash fields; "
    "proxy telemetry is diagnostic only. This tool does not run local-min, micro-MD, docking, write the candidate "
    "CSV, promote claims, or mutate external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "candidate_csv_update_allowed": False,
    "claim_promotion_allowed": False,
}

BAND_KEYS = (BAND_GREEN, BAND_YELLOW, BAND_RED, BAND_ABSTAIN, BAND_COARSE_ONLY)
GREEN_BAND_CONDITION = {
    "local_min_ligand_rmsd_a_lte": LOCAL_MIN_SURVIVAL_RMSD_A,
    "hbond_persistence_gte": HBOND_PERSISTENCE_MIN,
    "contact_persistence_gte": CONTACT_PERSISTENCE_MIN,
    "initial_clash_count_required": True,
    "clash_count_lte": MAX_CLASH_COUNT,
    "clash_relief_report_required": True,
    "missing_evidence_band": BAND_ABSTAIN,
    "local_min_failure_band": BAND_RED,
}
GREEN_BAND_CONDITION_TEXT = (
    f"green requires local_min_ligand_rmsd_a <= {LOCAL_MIN_SURVIVAL_RMSD_A}, "
    f"hbond_persistence >= {HBOND_PERSISTENCE_MIN}, "
    f"contact_persistence >= {CONTACT_PERSISTENCE_MIN}, "
    "initial_clash_count present, "
    f"clash_count <= {MAX_CLASH_COUNT}, and clash-relief fields reportable; "
    f"missing evidence abstains and failed local-min is {BAND_RED}"
)

CSV_COLUMNS = [
    "entry_id",
    "selected_for_refine",
    "band",
    "claim_safe",
    "claim_grade_metric_ready",
    "claim_grade_missing_metrics",
    "candidate_metric_fill_status",
    "local_min_ligand_rmsd_a",
    "local_min_survived",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
    "clash_relief_count",
    "uncertainty_score",
    "uncertainty_posture",
    "proxy_local_min_ligand_rmsd_a",
    "proxy_local_min_survival",
    "proxy_hbond_persistence",
    "proxy_contact_persistence",
    "proxy_clash_frame_fraction",
    "trajectory_probe_status",
    "recommended_next_local_action",
    "blockers",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], str]:
    path = _resolve(path_like)
    if not path.exists():
        return {}, f"missing:{_display(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, f"unreadable:{_display(path)}"
    return (payload, _display(path)) if isinstance(payload, dict) else ({}, f"invalid:{_display(path)}")


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _preview_candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("preview_candidate_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _num(value: Any) -> float | None:
    try:
        if value is None or _text(value) == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _entry_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("entry_id")): row for row in rows if _text(row.get("entry_id"))}


def _split_semicolon(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [item for item in _text(value).split(";") if item]


def _claim_missing_metrics(report_row: dict[str, Any], queue_row: dict[str, Any]) -> list[str]:
    missing = report_row.get("missing_evidence_fields")
    if isinstance(missing, list):
        return [str(item) for item in missing if str(item)]
    text = _text(report_row.get("missing_evidence_fields"))
    if text:
        return _split_semicolon(text)
    return _split_semicolon(queue_row.get("missing_metrics"))


def _overlaid_candidate(report_row: dict[str, Any], fill_row: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(report_row)
    if _text(fill_row.get("pocketmd_lite_metric_fill_status")) != "filled_from_claim_grade_probe":
        return candidate
    for column in (
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "contact_persistence",
        "initial_clash_count",
        "clash_count",
    ):
        value = fill_row.get(column)
        if _text(value):
            candidate[column] = value
    return candidate


def _row(
    report_row: dict[str, Any],
    probe_row: dict[str, Any],
    queue_row: dict[str, Any],
    fill_row: dict[str, Any],
) -> dict[str, Any]:
    assessed = build_pocketmd_lite_assessment(_overlaid_candidate(report_row, fill_row))
    assessed_missing_metrics = assessed.get("missing_evidence_fields")
    if isinstance(assessed_missing_metrics, list):
        missing_metrics = [str(item) for item in assessed_missing_metrics if str(item)]
    else:
        missing_metrics = _claim_missing_metrics(report_row, queue_row)
    proxy_local = _num(probe_row.get("coarse_local_min_ligand_rmsd_a"))
    proxy_hbond = _num(probe_row.get("coarse_hbond_persistence_proxy"))
    proxy_contact = _num(probe_row.get("coarse_contact_persistence_proxy"))
    proxy_clash = _num(probe_row.get("coarse_clash_frame_fraction_proxy"))
    blockers = []
    if missing_metrics:
        blockers.append("claim_grade_metrics_missing:" + ",".join(missing_metrics))
    probe_blockers = _split_semicolon(probe_row.get("blockers"))
    blockers.extend(probe_blockers)
    return {
        "entry_id": _text(report_row.get("entry_id") or probe_row.get("entry_id") or queue_row.get("entry_id")),
        "selected_for_refine": _bool(report_row.get("selected_for_refine")),
        "band": _text(assessed.get("band")),
        "claim_safe": _bool(assessed.get("claim_safe")),
        "claim_grade_metric_ready": not missing_metrics and _bool(probe_row.get("claim_grade_metric_ready")),
        "claim_grade_missing_metrics": missing_metrics,
        "local_min_ligand_rmsd_a": _num(assessed.get("local_min_ligand_rmsd_a")),
        "local_min_survived": assessed.get("local_min_survived"),
        "hbond_persistence": _num(assessed.get("hbond_persistence")),
        "contact_persistence": _num(assessed.get("contact_persistence")),
        "initial_clash_count": _num(assessed.get("initial_clash_count")),
        "clash_count": _num(assessed.get("clash_count")),
        "clash_relief_count": _num(assessed.get("clash_relief_count")),
        "uncertainty_score": _num(assessed.get("uncertainty_score")),
        "uncertainty_posture": _text(assessed.get("uncertainty_posture")),
        "candidate_metric_fill_status": _text(fill_row.get("pocketmd_lite_metric_fill_status")),
        "proxy_local_min_ligand_rmsd_a": proxy_local,
        "proxy_local_min_survival": _bool(probe_row.get("coarse_local_min_survival_proxy")),
        "proxy_hbond_persistence": proxy_hbond,
        "proxy_contact_persistence": proxy_contact,
        "proxy_clash_frame_fraction": proxy_clash,
        "trajectory_probe_status": _text(probe_row.get("trajectory_probe_status")),
        "recommended_next_local_action": _text(
            probe_row.get("recommended_next_local_action")
            or queue_row.get("recommended_next_local_action")
        ),
        "blockers": sorted(set(blockers)),
        **READ_ONLY_FLAGS,
    }


def build_pocketmd_lite_topk_refinement_audit(
    *,
    report_json: str | Path = DEFAULT_REPORT_JSON,
    probe_json: str | Path = DEFAULT_PROBE_JSON,
    remaining_queue_json: str | Path = DEFAULT_REMAINING_QUEUE_JSON,
    candidate_fill_preview_json: str | Path | None = None,
    metric_source_audit_json: str | Path | None = None,
) -> dict[str, Any]:
    report, report_evidence = _read_json(report_json)
    probe, probe_evidence = _read_json(probe_json)
    queue, queue_evidence = _read_json(remaining_queue_json)
    fill_preview: dict[str, Any] = {}
    fill_preview_evidence = "not_requested"
    if candidate_fill_preview_json is not None:
        fill_preview, fill_preview_evidence = _read_json(candidate_fill_preview_json)
    source_audit: dict[str, Any] = {}
    source_audit_evidence = "not_requested"
    if metric_source_audit_json is not None:
        source_audit, source_audit_evidence = _read_json(metric_source_audit_json)

    report_summary = _summary(report)
    probe_summary = _summary(probe)
    queue_summary = _summary(queue)
    fill_preview_summary = _summary(fill_preview)
    source_audit_summary = _summary(source_audit)
    probe_by_entry = _entry_map(_rows(probe))
    queue_by_entry = _entry_map(_rows(queue))
    fill_by_entry = _entry_map(_preview_candidate_rows(fill_preview))

    rows = [
        _row(
            report_row,
            probe_by_entry.get(_text(report_row.get("entry_id")), {}),
            queue_by_entry.get(_text(report_row.get("entry_id")), {}),
            fill_by_entry.get(_text(report_row.get("entry_id")), {}),
        )
        for report_row in _rows(report)
    ]
    selected_rows = [row for row in rows if row["selected_for_refine"]]
    claim_grade_ready_rows = [row for row in selected_rows if row["claim_grade_metric_ready"]]
    band_counts = {band: sum(1 for row in rows if row["band"] == band) for band in BAND_KEYS}
    missing_metric_counts: dict[str, int] = {}
    for row in selected_rows:
        for metric in row["claim_grade_missing_metrics"]:
            missing_metric_counts[metric] = missing_metric_counts.get(metric, 0) + 1

    proxy_local_count = sum(1 for row in selected_rows if row["proxy_local_min_ligand_rmsd_a"] is not None)
    proxy_hbond_count = sum(1 for row in selected_rows if row["proxy_hbond_persistence"] is not None)
    proxy_contact_count = sum(1 for row in selected_rows if row["proxy_contact_persistence"] is not None)
    proxy_clash_count = sum(1 for row in selected_rows if row["proxy_clash_frame_fraction"] is not None)
    proxy_ready = bool(
        selected_rows
        and proxy_local_count == len(selected_rows)
        and proxy_hbond_count == len(selected_rows)
        and proxy_contact_count == len(selected_rows)
        and proxy_clash_count == len(selected_rows)
    )
    claim_grade_ready = bool(selected_rows and len(claim_grade_ready_rows) == len(selected_rows))
    report_evidence_ready = bool(report_summary.get("top_k_refinement_evidence_ready") is True)
    candidate_fill_preview_ready = bool(
        fill_preview_summary.get("status") == "pocketmd_lite_candidate_metric_fill_preview_ready"
        and fill_preview_summary.get("canonical_candidate_csv_mutated") is False
        and fill_preview_summary.get("candidate_csv_update_allowed") is False
    )

    if not selected_rows:
        status = "blocked_pocketmd_lite_topk_refinement_audit_no_topk"
    elif claim_grade_ready and report_evidence_ready:
        status = "pocketmd_lite_topk_refinement_audit_ready"
    elif claim_grade_ready and candidate_fill_preview_ready:
        status = "pocketmd_lite_topk_refinement_audit_ready"
    elif proxy_ready:
        status = "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported"
    else:
        status = "blocked_pocketmd_lite_topk_refinement_audit"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "report_status": report_summary.get("status", "missing"),
        "probe_status": probe_summary.get("status", "missing"),
        "remaining_queue_status": queue_summary.get("status", "missing"),
        "candidate_metric_fill_preview_status": fill_preview_summary.get("status", "not_requested"),
        "candidate_metric_fill_preview_ready": candidate_fill_preview_ready,
        "candidate_metric_fill_preview_fill_ready_row_count": int(
            fill_preview_summary.get("fill_ready_row_count", 0) or 0
        ),
        "candidate_metric_fill_preview_blocked_fill_row_count": int(
            fill_preview_summary.get("blocked_fill_row_count", 0) or 0
        ),
        "candidate_metric_fill_preview_candidate_csv_update_allowed": bool(
            fill_preview_summary.get("candidate_csv_update_allowed") is True
        ),
        "candidate_metric_fill_preview_canonical_candidate_csv_mutated": bool(
            fill_preview_summary.get("canonical_candidate_csv_mutated") is True
        ),
        "candidate_metric_fill_preview_preview_candidate_csv": _text(
            fill_preview_summary.get("preview_candidate_csv")
        ),
        "claim_grade_metric_source_audit_status": source_audit_summary.get("status", "not_requested"),
        "claim_grade_metric_source_exact_ready_count": int(
            source_audit_summary.get("exact_metric_source_ready_count", 0) or 0
        ),
        "claim_grade_metric_source_collection_input_ready_count": int(
            source_audit_summary.get("claim_grade_collection_input_ready_count", 0) or 0
        ),
        "claim_grade_metric_source_atomized_protein_candidate_count": int(
            source_audit_summary.get("atomized_protein_source_candidate_count", 0) or 0
        ),
        "claim_grade_metric_source_ligand_atom_candidate_count": int(
            source_audit_summary.get("ligand_atom_source_candidate_count", 0) or 0
        ),
        "claim_grade_metric_source_partial_atomized_candidate_count": int(
            source_audit_summary.get("partial_atomized_protein_only_candidate_count", 0) or 0
        ),
        "claim_grade_metric_source_selected_proxy_only_count": int(
            source_audit_summary.get("selected_proxy_only_count", 0) or 0
        ),
        "claim_grade_metric_source_next_required_step": _text(
            source_audit_summary.get("next_required_step")
        ),
        "candidate_count": len(rows),
        "selected_top_k_count": len(selected_rows),
        "top_k_only_policy_enforced": bool(report_summary.get("top_k_only_policy_enforced") is True),
        "green_row_count": band_counts[BAND_GREEN],
        "yellow_row_count": band_counts[BAND_YELLOW],
        "red_row_count": band_counts[BAND_RED],
        "abstain_row_count": band_counts[BAND_ABSTAIN],
        "coarse_only_row_count": band_counts[BAND_COARSE_ONLY],
        "claim_grade_band_counts": {
            BAND_GREEN: band_counts[BAND_GREEN],
            BAND_YELLOW: band_counts[BAND_YELLOW],
            BAND_RED: band_counts[BAND_RED],
            BAND_ABSTAIN: band_counts[BAND_ABSTAIN],
        },
        "selected_banding_row_count": (
            band_counts[BAND_GREEN] + band_counts[BAND_YELLOW] + band_counts[BAND_RED] + band_counts[BAND_ABSTAIN]
        ),
        "banding_surface_ready": bool(
            selected_rows
            and (
                band_counts[BAND_GREEN]
                + band_counts[BAND_YELLOW]
                + band_counts[BAND_RED]
                + band_counts[BAND_ABSTAIN]
            )
            == len(selected_rows)
        ),
        "green_band_condition": report_summary.get("green_band_condition") or GREEN_BAND_CONDITION,
        "green_band_condition_text": report_summary.get("green_band_condition_text") or GREEN_BAND_CONDITION_TEXT,
        "claim_grade_refinement_evidence_ready": claim_grade_ready,
        "claim_grade_report_evidence_ready": report_evidence_ready,
        "claim_grade_fill_preview_evidence_ready": bool(claim_grade_ready and candidate_fill_preview_ready),
        "claim_grade_metric_ready_count": len(claim_grade_ready_rows),
        "claim_grade_missing_candidate_count": len(selected_rows) - len(claim_grade_ready_rows),
        "missing_refinement_metric_names": sorted(missing_metric_counts),
        "missing_refinement_metric_counts": dict(sorted(missing_metric_counts.items())),
        "proxy_topk_telemetry_ready": proxy_ready,
        "proxy_local_min_reported_count": proxy_local_count,
        "proxy_local_min_survival_count": sum(1 for row in selected_rows if row["proxy_local_min_survival"] is True),
        "proxy_hbond_reported_count": proxy_hbond_count,
        "proxy_hbond_observed_count": sum(
            1 for row in selected_rows if (row["proxy_hbond_persistence"] is not None and row["proxy_hbond_persistence"] > 0.0)
        ),
        "proxy_contact_reported_count": proxy_contact_count,
        "proxy_final_clash_reported_count": proxy_clash_count,
        "claim_grade_local_min_reported_count": sum(
            1 for row in selected_rows if row["local_min_ligand_rmsd_a"] is not None
        ),
        "claim_grade_local_min_survival_count": sum(
            1 for row in selected_rows if row["local_min_survived"] is True
        ),
        "claim_grade_hbond_reported_count": sum(1 for row in selected_rows if row["hbond_persistence"] is not None),
        "claim_grade_contact_reported_count": sum(
            1 for row in selected_rows if row["contact_persistence"] is not None
        ),
        "claim_grade_initial_clash_reported_count": sum(
            1 for row in selected_rows if row["initial_clash_count"] is not None
        ),
        "claim_grade_final_clash_reported_count": sum(1 for row in selected_rows if row["clash_count"] is not None),
        "claim_grade_clash_relief_reported_count": sum(
            1 for row in selected_rows if row["clash_relief_count"] is not None
        ),
        "uncertainty_reported_count": sum(1 for row in selected_rows if row["uncertainty_score"] is not None),
        "high_uncertainty_count": sum(
            1
            for row in selected_rows
            if row["uncertainty_score"] is not None and row["uncertainty_score"] >= 0.75
        ),
        "claim_promotion_allowed": False,
        "next_required_step": (
            "PocketMD Lite claim-grade top-k refinement evidence is complete; review the uncertainty bands."
            if claim_grade_ready and (report_evidence_ready or candidate_fill_preview_ready)
            else "Run the PocketMD Lite report against the metric fill preview candidate CSV, then review top-k bands."
            if candidate_fill_preview_ready
            else _text(source_audit_summary.get("next_required_step"))
            if source_audit_summary
            else "Generate or extract claim-grade local_min_ligand_rmsd_a, hbond_persistence, and initial_clash_count for the selected top-k rows; proxy telemetry is diagnostic only."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "evidence": {
            "report_json": report_evidence,
            "probe_json": probe_evidence,
            "remaining_queue_json": queue_evidence,
            "candidate_fill_preview_json": fill_preview_evidence,
            "metric_source_audit_json": source_audit_evidence,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in CSV_COLUMNS})


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Top-K Refinement Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- selected_top_k_count: `{summary['selected_top_k_count']}`",
        f"- green_row_count: `{summary['green_row_count']}`",
        f"- yellow_row_count: `{summary['yellow_row_count']}`",
        f"- red_row_count: `{summary['red_row_count']}`",
        f"- abstain_row_count: `{summary['abstain_row_count']}`",
        f"- green_band_condition: `{summary['green_band_condition_text']}`",
        f"- claim_grade_refinement_evidence_ready: `{str(summary['claim_grade_refinement_evidence_ready']).lower()}`",
        f"- candidate_metric_fill_preview_ready: `{str(summary['candidate_metric_fill_preview_ready']).lower()}`",
        f"- proxy_topk_telemetry_ready: `{str(summary['proxy_topk_telemetry_ready']).lower()}`",
        f"- missing_refinement_metric_names: `{', '.join(summary['missing_refinement_metric_names']) or '(none)'}`",
        f"- claim_grade_metric_ready_count: `{summary['claim_grade_metric_ready_count']}`",
        f"- claim_grade_local_min_reported_count: `{summary['claim_grade_local_min_reported_count']}`",
        f"- claim_grade_local_min_survival_count: `{summary['claim_grade_local_min_survival_count']}`",
        f"- claim_grade_hbond_reported_count: `{summary['claim_grade_hbond_reported_count']}`",
        f"- claim_grade_initial_clash_reported_count: `{summary['claim_grade_initial_clash_reported_count']}`",
        f"- claim_grade_clash_relief_reported_count: `{summary['claim_grade_clash_relief_reported_count']}`",
        f"- proxy_local_min_reported_count: `{summary['proxy_local_min_reported_count']}`",
        f"- proxy_hbond_reported_count: `{summary['proxy_hbond_reported_count']}`",
        f"- proxy_contact_reported_count: `{summary['proxy_contact_reported_count']}`",
        f"- proxy_final_clash_reported_count: `{summary['proxy_final_clash_reported_count']}`",
        f"- uncertainty_reported_count: `{summary['uncertainty_reported_count']}`",
        "",
        "## Rows",
        "",
        "| entry | band | fill status | missing claim-grade metrics | local-min RMSD | H-bond | initial clash | clash relief | uncertainty |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{band}` | `{fill}` | `{missing}` | {local} | {hbond} | {initial_clash} | {relief} | {uncertainty} |".format(
                entry=row["entry_id"],
                band=row["band"] or "(none)",
                fill=row["candidate_metric_fill_status"] or "(none)",
                missing=", ".join(row["claim_grade_missing_metrics"]) or "(none)",
                local=_fmt(row["local_min_ligand_rmsd_a"]),
                hbond=_fmt(row["hbond_persistence"]),
                initial_clash=_fmt(row["initial_clash_count"]),
                relief=_fmt(row["clash_relief_count"]),
                uncertainty=_fmt(row["uncertainty_score"]),
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path, out_csv: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    csv_path = _resolve(out_csv)
    for path in (json_path, md_path, csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    _write_csv(csv_path, payload["rows"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--probe-json", default=DEFAULT_PROBE_JSON)
    parser.add_argument("--remaining-queue-json", default=DEFAULT_REMAINING_QUEUE_JSON)
    parser.add_argument("--candidate-fill-preview-json", default=DEFAULT_CANDIDATE_FILL_PREVIEW_JSON)
    parser.add_argument("--metric-source-audit-json", default=DEFAULT_METRIC_SOURCE_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_pocketmd_lite_topk_refinement_audit(
        report_json=args.report_json,
        probe_json=args.probe_json,
        remaining_queue_json=args.remaining_queue_json,
        candidate_fill_preview_json=args.candidate_fill_preview_json,
        metric_source_audit_json=args.metric_source_audit_json,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md, out_csv=args.out_csv)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
