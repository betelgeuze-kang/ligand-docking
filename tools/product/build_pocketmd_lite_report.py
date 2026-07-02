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

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
}

BAND_KEYS = (BAND_GREEN, BAND_YELLOW, BAND_RED, BAND_ABSTAIN, BAND_COARSE_ONLY)
CLAIM_GRADE_BANDS = (BAND_GREEN, BAND_YELLOW, BAND_RED)
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


def _blocked_artifact(status: str, input_csv: Path, detail: str) -> dict[str, Any]:
    band_fields = _band_summary_fields({}, selected_count=0)
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": status,
        "input_csv": str(input_csv),
        "detail": detail,
        "summary": {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "blocked_pocketmd_lite_report",
            "candidate_count": 0,
            "top_k_only_policy_enforced": True,
            "pocketmd_lite_claim_safe": False,
            **band_fields,
            **_READ_ONLY_FLAGS,
        },
        "rows": [],
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


def build_pocketmd_lite_report_artifact(input_csv: str | Path) -> dict[str, Any]:
    path = _resolve(input_csv)
    if not path.exists():
        return _blocked_artifact(STATUS_BLOCKED_MISSING, path, "input CSV does not exist")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if not rows:
        return _blocked_artifact(STATUS_BLOCKED_EMPTY, path, "input CSV has no candidate rows")
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        return _blocked_artifact(
            STATUS_BLOCKED_SCHEMA,
            path,
            f"input CSV missing required columns: {missing_columns}",
        )

    try:
        candidates = [_row_to_candidate(row) for row in rows]
        report = build_pocketmd_lite_report(candidates)
    except (PocketMdLiteError, ValueError) as exc:
        return _blocked_artifact(STATUS_BLOCKED_INVALID_ROW, path, str(exc))

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
        }
    )
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": STATUS_MATERIALIZED,
        "input_csv": str(path),
        "detail": "",
        "summary": summary,
        "rows": report["rows"],
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
        f"- status: `{summary.get('status')}`",
        f"- candidate_count: `{summary.get('candidate_count')}`",
        f"- selected_top_k_count: `{summary.get('selected_top_k_count', 0)}`",
        f"- pocketmd_lite_claim_safe: `{str(summary.get('pocketmd_lite_claim_safe')).lower()}`",
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
        lines.append(f"> **Blocked (fail-closed):** {artifact['detail']}")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
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
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    artifact = build_pocketmd_lite_report_artifact(args.input_csv)
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
