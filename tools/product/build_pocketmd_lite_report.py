#!/usr/bin/env python3
"""Materialize the PocketMD Lite top-k refinement report.

Read-only: this tool grades caller-provided top-k refinement evidence. It does
not run local-min, micro-MD, docking, or external mutation. Missing refinement
evidence abstains through betelgeuze_product.pocketmd_lite_contract.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.pocketmd_lite_contract import (
    BAND_ABSTAIN,
    BAND_COARSE_ONLY,
    BAND_GREEN,
    BAND_RED,
    BAND_YELLOW,
    CLAIM_BOUNDARY,
    CONTACT_PERSISTENCE_MIN,
    HBOND_PERSISTENCE_MIN,
    LOCAL_MIN_SURVIVAL_RMSD_A,
    MAX_CLASH_COUNT,
    PocketMdLiteError,
    build_pocketmd_lite_report,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_CANDIDATE_FILL_PREVIEW_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_report_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_report_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_report_current.csv"

PACKET_TYPE = "pocketmd_lite_report"
REPORT_SCHEMA_VERSION = "pocketmd_lite_report_v1"

REQUIRED_COLUMNS = ("entry_id",)
OPTIONAL_COLUMNS = (
    "family",
    "rank_pct",
    "selected_for_refine",
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "pre_refine_clash_count",
    "clash_count",
)

STATUS_MATERIALIZED = "materialized"
STATUS_BLOCKED_MISSING = "blocked_missing_input_csv"
STATUS_BLOCKED_EMPTY = "blocked_empty_input_csv"
STATUS_BLOCKED_SCHEMA = "blocked_input_schema_missing_required_columns"
STATUS_BLOCKED_INVALID_ROW = "blocked_invalid_input_row"
STATUS_FILL_PREVIEW_READY = "pocketmd_lite_candidate_metric_fill_preview_ready"

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
}

BAND_KEYS = (BAND_GREEN, BAND_YELLOW, BAND_RED, BAND_ABSTAIN, BAND_COARSE_ONLY)
CLAIM_GRADE_BANDS = (BAND_GREEN, BAND_YELLOW, BAND_RED)
MIN_CLAIM_GRADE_GREEN_ROWS = 3
REQUIRED_ADRB2_GREEN_ROWS = 3
REQUIRED_RECOVERED_TARGET_IDS = ("DRD3", "OPRD1")
CLAIM_GRADE_REQUIREMENT_IDS = (
    "selected_top_k_minimum_met",
    "adrb2_three_collection_ready_rows",
    "drd3_oprd1_atom_frame_recovery",
    "local_min_ligand_rmsd_ready",
    "hbond_persistence_ready",
    "contact_persistence_ready",
    "clash_relief_ready",
    "green_yellow_red_abstain_banding_ready",
    "pocketmd_lite_claim_grade_contract_ready",
    "pocketmd_lite_claim_promotion_review_allowed",
)
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


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_bool(value: Any) -> bool | None:
    text = _text(value).lower()
    if text == "":
        return None
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise PocketMdLiteError(f"invalid selected_for_refine bool: {value!r}")


def _row_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    candidate: dict[str, Any] = {"entry_id": _text(row.get("entry_id"))}
    for column in OPTIONAL_COLUMNS:
        if column not in row:
            continue
        if column == "selected_for_refine":
            parsed = _parse_bool(row.get(column))
            if parsed is not None:
                candidate[column] = parsed
        else:
            candidate[column] = row.get(column)
    return candidate


def _fill_preview_artifact_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_fill_preview_json": _text(metadata.get("candidate_fill_preview_json")),
        "candidate_fill_preview_status": _text(metadata.get("candidate_fill_preview_status")),
        "candidate_fill_preview_input_csv": _text(metadata.get("candidate_fill_preview_input_csv")),
        "candidate_fill_preview_applied": bool(metadata.get("candidate_fill_preview_applied") is True),
        "candidate_fill_preview_ready": bool(metadata.get("candidate_fill_preview_ready") is True),
        "candidate_fill_preview_canonical_candidate_csv_mutated": bool(
            metadata.get("candidate_fill_preview_canonical_candidate_csv_mutated") is True
        ),
        "candidate_fill_preview_candidate_csv_update_allowed": bool(
            metadata.get("candidate_fill_preview_candidate_csv_update_allowed") is True
        ),
    }


def _candidate_fill_preview_input_csv(
    candidate_fill_preview_json: str | Path | None,
) -> tuple[Path | None, dict[str, Any]]:
    if candidate_fill_preview_json is None or _text(candidate_fill_preview_json) == "":
        return None, {}

    receipt_path = _resolve(candidate_fill_preview_json)
    payload = _read_json(receipt_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    preview_candidate_csv = _text(summary.get("preview_candidate_csv"))
    preview_path = _resolve(preview_candidate_csv) if preview_candidate_csv else None
    metadata: dict[str, Any] = {
        "candidate_fill_preview_json": str(receipt_path),
        "candidate_fill_preview_status": _text(summary.get("status")),
        "candidate_fill_preview_input_csv": str(preview_path) if preview_path else "",
        "candidate_fill_preview_applied": False,
        "candidate_fill_preview_ready": summary.get("preview_candidate_csv_ready") is True,
        "candidate_fill_preview_canonical_candidate_csv_mutated": (
            summary.get("canonical_candidate_csv_mutated") is True
        ),
        "candidate_fill_preview_candidate_csv_update_allowed": (
            summary.get("candidate_csv_update_allowed") is True
        ),
    }
    if (
        summary.get("status") == STATUS_FILL_PREVIEW_READY
        and summary.get("preview_candidate_csv_ready") is True
        and summary.get("canonical_candidate_csv_mutated") is False
        and summary.get("candidate_csv_update_allowed") is False
        and preview_path is not None
        and preview_path.exists()
    ):
        metadata["candidate_fill_preview_applied"] = True
        return preview_path, metadata
    return None, metadata


def _blocked_artifact(
    status: str,
    input_csv: Path,
    detail: str,
    *,
    source_input_csv: Path | None = None,
    fill_preview_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fill_preview_fields = _fill_preview_artifact_fields(fill_preview_metadata or {})
    band_fields = _band_summary_fields({}, selected_count=0)
    summary = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "blocked_pocketmd_lite_report",
        "candidate_count": 0,
        "top_k_only_policy_enforced": True,
        "pocketmd_lite_claim_safe": False,
        **band_fields,
        **_READ_ONLY_FLAGS,
        **fill_preview_fields,
    }
    claim_grade_requirement_rows = _claim_grade_requirement_rows(summary, [])
    summary.update(_claim_grade_requirement_summary(claim_grade_requirement_rows))
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": status,
        "input_csv": str(input_csv),
        "source_input_csv": str(source_input_csv or input_csv),
        **fill_preview_fields,
        "detail": detail,
        "summary": summary,
        "rows": [],
        "claim_grade_requirement_rows": claim_grade_requirement_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _band_summary_fields(band_counts: dict[str, Any], *, selected_count: int) -> dict[str, Any]:
    counts = {band: int(band_counts.get(band, 0) or 0) for band in BAND_KEYS}
    claim_grade_ready = sum(counts[band] for band in CLAIM_GRADE_BANDS)
    selected_band_count = sum(counts[band] for band in (BAND_GREEN, BAND_YELLOW, BAND_RED, BAND_ABSTAIN))
    return {
        "green_row_count": counts[BAND_GREEN],
        "yellow_row_count": counts[BAND_YELLOW],
        "red_row_count": counts[BAND_RED],
        "abstain_row_count": counts[BAND_ABSTAIN],
        "coarse_only_row_count": counts[BAND_COARSE_ONLY],
        "claim_grade_metric_ready_row_count": claim_grade_ready,
        "selected_banding_row_count": selected_band_count,
        "claim_grade_band_counts": {
            BAND_GREEN: counts[BAND_GREEN],
            BAND_YELLOW: counts[BAND_YELLOW],
            BAND_RED: counts[BAND_RED],
            BAND_ABSTAIN: counts[BAND_ABSTAIN],
        },
        "banding_surface_ready": selected_count > 0 and selected_band_count == selected_count,
        "green_band_condition": GREEN_BAND_CONDITION,
        "green_band_condition_text": GREEN_BAND_CONDITION_TEXT,
    }


def _value_list(rows: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field)
        if value is None or value == "":
            continue
        values.append(float(value))
    return values


def _target_metric_ready_count(rows: list[dict[str, Any]], target_id: str) -> int:
    return sum(
        1
        for row in rows
        if target_id in _text(row.get("entry_id"))
        and row.get("band") in CLAIM_GRADE_BANDS
        and not row.get("missing_evidence_fields")
    )


def _claim_grade_requirement_row(
    *,
    requirement_id: str,
    ready: bool,
    observed_value: str,
    required_value: str,
    blocker: str,
    operator_action: str,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "observed_value": observed_value,
        "required_value": required_value,
        "blocker": "" if ready else blocker,
        "operator_action": "" if ready else operator_action,
        "claim_promotion_allowed": False,
        "candidate_csv_update_allowed": False,
        "refinement_execution_enabled": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _claim_grade_requirement_rows(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_count = int(summary.get("selected_top_k_count") or summary.get("refined_count") or 0)
    required_metric_count = selected_count or MIN_CLAIM_GRADE_GREEN_ROWS
    green_count = int(summary.get("green_row_count") or 0)
    yellow_count = int(summary.get("yellow_row_count") or 0)
    red_count = int(summary.get("red_row_count") or 0)
    abstain_count = int(summary.get("abstain_row_count") or 0)
    local_min_values = _value_list(rows, "local_min_ligand_rmsd_a")
    hbond_values = _value_list(rows, "hbond_persistence")
    contact_values = _value_list(rows, "contact_persistence")
    initial_clash_values = _value_list(rows, "initial_clash_count")
    final_clash_values = _value_list(rows, "clash_count")
    clash_relief_values = _value_list(rows, "clash_relief_count")
    adrb2_metric_ready_count = _target_metric_ready_count(rows, "ADRB2")
    recovered_targets = sorted(
        target_id
        for target_id in REQUIRED_RECOVERED_TARGET_IDS
        if _target_metric_ready_count(rows, target_id) > 0
    )

    requirement_rows = [
        _claim_grade_requirement_row(
            requirement_id="selected_top_k_minimum_met",
            ready=selected_count >= MIN_CLAIM_GRADE_GREEN_ROWS,
            observed_value=str(selected_count),
            required_value=f">={MIN_CLAIM_GRADE_GREEN_ROWS}",
            blocker=f"selected_top_k_rows_below_required:{selected_count}/{MIN_CLAIM_GRADE_GREEN_ROWS}",
            operator_action="Collect claim-grade metrics for at least three selected top-k rows.",
        ),
        _claim_grade_requirement_row(
            requirement_id="adrb2_three_collection_ready_rows",
            ready=adrb2_metric_ready_count >= REQUIRED_ADRB2_GREEN_ROWS,
            observed_value=str(adrb2_metric_ready_count),
            required_value=f">={REQUIRED_ADRB2_GREEN_ROWS}",
            blocker=f"adrb2_collection_ready_rows_below_required:{adrb2_metric_ready_count}/{REQUIRED_ADRB2_GREEN_ROWS}",
            operator_action="Run bounded metric collection for three ADRB2 collection-ready rows.",
        ),
        _claim_grade_requirement_row(
            requirement_id="drd3_oprd1_atom_frame_recovery",
            ready=tuple(recovered_targets) == REQUIRED_RECOVERED_TARGET_IDS,
            observed_value=",".join(recovered_targets),
            required_value=",".join(REQUIRED_RECOVERED_TARGET_IDS),
            blocker="drd3_oprd1_atom_frame_recovery_incomplete",
            operator_action="Recover DRD3 and OPRD1 protein/ligand atom frames, then rerun metrics.",
        ),
        _claim_grade_requirement_row(
            requirement_id="local_min_ligand_rmsd_ready",
            ready=(
                len(local_min_values) >= required_metric_count
                and bool(local_min_values)
                and max(local_min_values) <= LOCAL_MIN_SURVIVAL_RMSD_A
            ),
            observed_value=(
                f"reported={len(local_min_values)}; "
                f"max={max(local_min_values) if local_min_values else ''}"
            ),
            required_value=f"all selected rows reported and max<={LOCAL_MIN_SURVIVAL_RMSD_A}A",
            blocker="local_min_ligand_rmsd_not_claim_grade",
            operator_action="Recover exact local-min ligand RMSD for every selected top-k row.",
        ),
        _claim_grade_requirement_row(
            requirement_id="hbond_persistence_ready",
            ready=(
                len(hbond_values) >= required_metric_count
                and bool(hbond_values)
                and min(hbond_values) >= HBOND_PERSISTENCE_MIN
            ),
            observed_value=(
                f"reported={len(hbond_values)}; "
                f"min={min(hbond_values) if hbond_values else ''}"
            ),
            required_value=f"all selected rows reported and min>={HBOND_PERSISTENCE_MIN}",
            blocker="hbond_persistence_not_claim_grade",
            operator_action="Recover H-bond persistence for every selected top-k row.",
        ),
        _claim_grade_requirement_row(
            requirement_id="contact_persistence_ready",
            ready=(
                len(contact_values) >= required_metric_count
                and bool(contact_values)
                and min(contact_values) >= CONTACT_PERSISTENCE_MIN
            ),
            observed_value=(
                f"reported={len(contact_values)}; "
                f"min={min(contact_values) if contact_values else ''}"
            ),
            required_value=f"all selected rows reported and min>={CONTACT_PERSISTENCE_MIN}",
            blocker="contact_persistence_not_claim_grade",
            operator_action="Recover contact persistence for every selected top-k row.",
        ),
        _claim_grade_requirement_row(
            requirement_id="clash_relief_ready",
            ready=(
                len(initial_clash_values) >= required_metric_count
                and len(final_clash_values) >= required_metric_count
                and len(clash_relief_values) >= required_metric_count
                and bool(final_clash_values)
                and max(final_clash_values) <= MAX_CLASH_COUNT
            ),
            observed_value=(
                f"initial={len(initial_clash_values)}; final={len(final_clash_values)}; "
                f"relief={len(clash_relief_values)}; "
                f"final_max={max(final_clash_values) if final_clash_values else ''}"
            ),
            required_value=(
                "initial/final/relief reported for all selected rows and "
                f"final_clash_count<={MAX_CLASH_COUNT}"
            ),
            blocker="clash_relief_not_claim_grade",
            operator_action="Recover initial/final clash counts and clash relief for every selected row.",
        ),
        _claim_grade_requirement_row(
            requirement_id="green_yellow_red_abstain_banding_ready",
            ready=(
                selected_count >= MIN_CLAIM_GRADE_GREEN_ROWS
                and green_count >= selected_count
                and yellow_count == 0
                and red_count == 0
                and abstain_count == 0
            ),
            observed_value=(
                f"green={green_count}; yellow={yellow_count}; red={red_count}; abstain={abstain_count}"
            ),
            required_value="all selected rows green; yellow/red/abstain=0",
            blocker="claim_grade_banding_not_green",
            operator_action="Review banding and recover missing or failed claim-grade metrics.",
        ),
    ]
    contract_ready = all(row["ready"] for row in requirement_rows)
    requirement_rows.append(
        _claim_grade_requirement_row(
            requirement_id="pocketmd_lite_claim_grade_contract_ready",
            ready=contract_ready,
            observed_value=str(contract_ready).lower(),
            required_value="true",
            blocker="pocketmd_lite_claim_grade_contract_not_ready",
            operator_action="Close every PocketMD Lite claim-grade metric requirement.",
        )
    )
    requirement_rows.append(
        _claim_grade_requirement_row(
            requirement_id="pocketmd_lite_claim_promotion_review_allowed",
            ready=False,
            observed_value="false",
            required_value="explicit_human_review_after_contract_ready",
            blocker="pocketmd_lite_claim_promotion_not_approved",
            operator_action="Keep PocketMD Lite claim wording disabled until explicit review approval.",
        )
    )
    return requirement_rows


def _claim_grade_requirement_summary(requirement_rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_rows = [row for row in requirement_rows if not row["ready"]]
    primary = blocked_rows[0] if blocked_rows else {}
    contract = next(
        (
            row
            for row in requirement_rows
            if row["requirement_id"] == "pocketmd_lite_claim_grade_contract_ready"
        ),
        {},
    )
    return {
        "claim_grade_requirement_ids": list(CLAIM_GRADE_REQUIREMENT_IDS),
        "claim_grade_requirement_row_count": len(requirement_rows),
        "claim_grade_requirement_ready_row_count": len(requirement_rows) - len(blocked_rows),
        "claim_grade_requirement_blocked_row_count": len(blocked_rows),
        "claim_grade_primary_requirement_id": _text(primary.get("requirement_id")),
        "claim_grade_primary_blocker": _text(primary.get("blocker")),
        "claim_grade_primary_operator_action": _text(primary.get("operator_action")),
        "pocketmd_lite_claim_grade_contract_ready": bool(contract.get("ready") is True),
        "pocketmd_lite_claim_promotion_allowed": False,
    }


def build_pocketmd_lite_report_artifact(
    input_csv: str | Path,
    *,
    candidate_fill_preview_json: str | Path | None = None,
) -> dict[str, Any]:
    source_path = _resolve(input_csv)
    preview_path, fill_preview_metadata = _candidate_fill_preview_input_csv(
        candidate_fill_preview_json
    )
    path = preview_path or source_path
    fill_preview_fields = _fill_preview_artifact_fields(fill_preview_metadata)
    if not path.exists():
        return _blocked_artifact(
            STATUS_BLOCKED_MISSING,
            path,
            "input CSV does not exist",
            source_input_csv=source_path,
            fill_preview_metadata=fill_preview_metadata,
        )

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if not rows:
        return _blocked_artifact(
            STATUS_BLOCKED_EMPTY,
            path,
            "input CSV has no candidate rows",
            source_input_csv=source_path,
            fill_preview_metadata=fill_preview_metadata,
        )
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        return _blocked_artifact(
            STATUS_BLOCKED_SCHEMA,
            path,
            f"input CSV missing required columns: {missing_columns}",
            source_input_csv=source_path,
            fill_preview_metadata=fill_preview_metadata,
        )

    try:
        candidates = [_row_to_candidate(row) for row in rows]
        report = build_pocketmd_lite_report(candidates)
    except (PocketMdLiteError, ValueError) as exc:
        return _blocked_artifact(
            STATUS_BLOCKED_INVALID_ROW,
            path,
            str(exc),
            source_input_csv=source_path,
            fill_preview_metadata=fill_preview_metadata,
        )

    summary = dict(report["summary"])
    band_counts = summary.get("band_counts") or {}
    selected_count = int(summary.get("refined_count") or 0)
    blocker_count = (
        int(band_counts.get(BAND_YELLOW, 0))
        + int(band_counts.get(BAND_RED, 0))
        + int(band_counts.get(BAND_ABSTAIN, 0))
    )
    band_fields = _band_summary_fields(band_counts, selected_count=selected_count)
    summary.update(
        {
            "status": (
                "pocketmd_lite_report_ready"
                if selected_count > 0 and blocker_count == 0
                else "blocked_pocketmd_lite_report"
            ),
            "top_k_only_policy_enforced": True,
            "selected_top_k_count": selected_count,
            "refinement_blocker_count": blocker_count,
            "pocketmd_lite_claim_safe": selected_count > 0 and blocker_count == 0,
            **band_fields,
            **_READ_ONLY_FLAGS,
            **fill_preview_fields,
        }
    )
    claim_grade_requirement_rows = _claim_grade_requirement_rows(summary, report["rows"])
    summary.update(_claim_grade_requirement_summary(claim_grade_requirement_rows))
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": STATUS_MATERIALIZED,
        "input_csv": str(path),
        "source_input_csv": str(source_path),
        **fill_preview_fields,
        "detail": "",
        "summary": summary,
        "rows": report["rows"],
        "claim_grade_requirement_rows": claim_grade_requirement_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    return "" if value is None else (f"{value:.4f}" if isinstance(value, float) else str(value))


def _render_markdown(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    lines = [
        "# PocketMD Lite Report (current)",
        "",
        "Top-k-only pocket-local refinement grading. Read-only: no local-min, no",
        "micro-MD execution, no docking, and no external mutation.",
        "",
        f"- materializer_status: `{artifact['materializer_status']}`",
        f"- input_csv: `{artifact['input_csv']}`",
        f"- source_input_csv: `{artifact.get('source_input_csv', artifact['input_csv'])}`",
        f"- candidate_fill_preview_applied: `{str(summary.get('candidate_fill_preview_applied')).lower()}`",
        f"- status: `{summary.get('status')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- selected_top_k_count: `{summary.get('selected_top_k_count', 0)}`",
        f"- pocketmd_lite_claim_safe: `{str(summary.get('pocketmd_lite_claim_safe')).lower()}`",
        f"- pocketmd_lite_claim_grade_contract_ready: `{str(summary.get('pocketmd_lite_claim_grade_contract_ready')).lower()}`",
        f"- pocketmd_lite_claim_promotion_allowed: `{str(summary.get('pocketmd_lite_claim_promotion_allowed')).lower()}`",
        f"- claim_grade_requirement_blocked_row_count: `{summary.get('claim_grade_requirement_blocked_row_count', 0)}`",
        f"- claim_grade_primary_requirement_id: `{summary.get('claim_grade_primary_requirement_id', '')}`",
        f"- refinement_blocker_count: `{summary.get('refinement_blocker_count', 0)}`",
        f"- green_row_count: `{summary.get('green_row_count', 0)}`",
        f"- yellow_row_count: `{summary.get('yellow_row_count', 0)}`",
        f"- red_row_count: `{summary.get('red_row_count', 0)}`",
        f"- abstain_row_count: `{summary.get('abstain_row_count', 0)}`",
        f"- claim_grade_metric_ready_row_count: `{summary.get('claim_grade_metric_ready_row_count', 0)}`",
        f"- green_band_condition: `{summary.get('green_band_condition_text')}`",
        f"- mean_uncertainty_score: `{summary.get('mean_uncertainty_score')}`",
        f"- high_uncertainty_count: `{summary.get('high_uncertainty_count')}`",
        f"- local_min_survival_reported_count: `{summary.get('local_min_survival_reported_count')}`",
        f"- hbond_persistence_reported_count: `{summary.get('hbond_persistence_reported_count')}`",
        f"- contact_persistence_reported_count: `{summary.get('contact_persistence_reported_count')}`",
        f"- initial_clash_reported_count: `{summary.get('initial_clash_reported_count')}`",
        f"- clash_relief_reported_count: `{summary.get('clash_relief_reported_count')}`",
        f"- missing_refinement_metric_names: `{', '.join(summary.get('missing_refinement_metric_names') or [])}`",
        "",
    ]
    if artifact["materializer_status"] != STATUS_MATERIALIZED:
        lines.extend(
            [
                "## Claim-Grade Requirement Checklist",
                "",
                "| requirement | status | observed | required | blocker | action |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in artifact.get("claim_grade_requirement_rows", []):
            lines.append(
                f"| `{row['requirement_id']}` | `{row['status']}` | `{row['observed_value']}` | "
                f"`{row['required_value']}` | `{row['blocker'] or '-'}` | {row['operator_action'] or '-'} |"
            )
        lines.append("")
        lines.append(f"> **Blocked (fail-closed):** {artifact['detail']}")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "## Claim-Grade Requirement Checklist",
            "",
            "| requirement | status | observed | required | blocker | action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in artifact.get("claim_grade_requirement_rows", []):
        lines.append(
            f"| `{row['requirement_id']}` | `{row['status']}` | `{row['observed_value']}` | "
            f"`{row['required_value']}` | `{row['blocker'] or '-'}` | {row['operator_action'] or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Candidates",
            "",
            "| entry | band | selected | local-min RMSD | H-bond | contact | clash relief | uncertainty | reason |",
            "| --- | --- | --- | --: | --: | --: | --: | --: | --- |",
        ]
    )
    for row in artifact["rows"]:
        lines.append(
            "| `{entry}` | `{band}` | `{selected}` | {rmsd} | {hbond} | {contact} | {relief} | {uncertainty} | {reason} |".format(
                entry=row["entry_id"],
                band=row["band"],
                selected=str(row["selected_for_refine"]).lower(),
                rmsd=_fmt(row["local_min_ligand_rmsd_a"]),
                hbond=_fmt(row["hbond_persistence"]),
                contact=_fmt(row["contact_persistence"]),
                relief=_fmt(row["clash_relief_count"]),
                uncertainty=_fmt(row["uncertainty_score"]),
                reason=row["reason_code"] or "(none)",
            )
        )
    lines.append("")
    return "\n".join(lines)


_CSV_COLUMNS = [
    "entry_id",
    "family",
    "selected_for_refine",
    "band",
    "claim_safe",
    "abstained",
    "local_min_ligand_rmsd_a",
    "local_min_survived",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
    "clash_relief_count",
    "clash_relief_observed",
    "evidence_completeness",
    "uncertainty_score",
    "uncertainty_posture",
    "missing_evidence_fields",
    "reason_code",
    "review_flags",
]


def _write_csv(out_csv: Path, rows: list[dict[str, Any]]) -> None:
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "entry_id": row["entry_id"],
                    "family": row["family"],
                    "selected_for_refine": str(row["selected_for_refine"]).lower(),
                    "band": row["band"],
                    "claim_safe": str(row["claim_safe"]).lower(),
                    "abstained": str(row["abstained"]).lower(),
                    "local_min_ligand_rmsd_a": _fmt(row["local_min_ligand_rmsd_a"]),
                    "local_min_survived": "" if row["local_min_survived"] is None else row["local_min_survived"],
                    "hbond_persistence": _fmt(row["hbond_persistence"]),
                    "contact_persistence": _fmt(row["contact_persistence"]),
                    "initial_clash_count": _fmt(row["initial_clash_count"]),
                    "clash_count": _fmt(row["clash_count"]),
                    "clash_relief_count": _fmt(row["clash_relief_count"]),
                    "clash_relief_observed": _fmt(row["clash_relief_observed"]),
                    "evidence_completeness": _fmt(row["evidence_completeness"]),
                    "uncertainty_score": _fmt(row["uncertainty_score"]),
                    "uncertainty_posture": row["uncertainty_posture"],
                    "missing_evidence_fields": ";".join(row["missing_evidence_fields"]),
                    "reason_code": row["reason_code"],
                    "review_flags": ";".join(row["review_flags"]),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the PocketMD Lite top-k refinement report.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--candidate-fill-preview-json", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    artifact = build_pocketmd_lite_report_artifact(
        args.input_csv,
        candidate_fill_preview_json=args.candidate_fill_preview_json or None,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    for out in (out_json, out_md, out_csv):
        out.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(artifact), encoding="utf-8")
    _write_csv(out_csv, artifact["rows"])
    return 0 if artifact["materializer_status"] == STATUS_MATERIALIZED else 1


if __name__ == "__main__":
    raise SystemExit(main())
