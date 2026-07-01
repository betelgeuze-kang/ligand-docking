#!/usr/bin/env python3
"""Build a PocketMD Lite candidate metric fill preview.

Read-only: this joins the canonical PocketMD Lite candidate CSV with the metric
collection probe and writes a separate preview CSV. It never mutates the
canonical candidate CSV and only proposes claim-grade metric values when the
probe row has explicit exact metric fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from betelgeuze_product.pocketmd_lite_contract import TOPK_DEFAULT_THRESHOLD_PCT

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATE_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_PROBE_JSON = "runs/pocketmd_lite_metric_collection_probe_current.json"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_candidate_metric_fill_preview_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_candidate_metric_fill_preview_current.csv"
DEFAULT_OUT_CANDIDATE_CSV = "runs/pocketmd_lite_candidate_metric_fill_preview_current.candidates.csv"

PACKET_TYPE = "pocketmd_lite_candidate_metric_fill_preview"
SCHEMA_VERSION = "pocketmd_lite_candidate_metric_fill_preview_v1"

CLAIM_BOUNDARY = (
    "PocketMD Lite candidate metric fill preview only. It copies the candidate CSV into a separate preview "
    "artifact and fills claim-grade local-min, H-bond, and baseline clash fields only from explicit exact metric "
    "probe fields. It does not accept coarse proxy telemetry as claim-grade evidence, does not mutate the "
    "canonical candidate CSV, does not run local-min or micro-MD, does not promote claims, and does not mutate "
    "external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "candidate_csv_update_allowed": False,
    "canonical_candidate_csv_mutated": False,
    "claim_promotion_allowed": False,
}

REQUIRED_FILL_METRICS = (
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "initial_clash_count",
)

OPTIONAL_FILL_METRICS = (
    "contact_persistence",
    "clash_count",
)

PROBE_TO_CANDIDATE_METRICS = {
    "exact_local_min_ligand_rmsd_a": "local_min_ligand_rmsd_a",
    "exact_hbond_persistence": "hbond_persistence",
    "exact_initial_clash_count": "initial_clash_count",
    "exact_contact_persistence": "contact_persistence",
    "exact_clash_count": "clash_count",
}

ROW_CSV_COLUMNS = [
    "entry_id",
    "selected_for_refine",
    "probe_row_present",
    "claim_grade_metric_ready",
    "fill_ready",
    "blocked_metric_names",
    "proposed_metric_names",
    "proposed_local_min_ligand_rmsd_a",
    "proposed_hbond_persistence",
    "proposed_initial_clash_count",
    "proposed_contact_persistence",
    "proposed_clash_count",
    "source_probe_status",
    "source_trajectory_npz",
    "recommended_next_local_action",
    "blockers",
]

PREVIEW_METADATA_COLUMNS = [
    "pocketmd_lite_metric_fill_status",
    "pocketmd_lite_metric_fill_source_probe_status",
    "pocketmd_lite_metric_fill_source_npz",
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


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _selected_for_refine(candidate_row: dict[str, Any]) -> bool:
    explicit = _text(candidate_row.get("selected_for_refine")).lower()
    if explicit in {"1", "true", "yes", "y", "on"}:
        return True
    if explicit in {"0", "false", "no", "n", "off"}:
        return False
    rank_pct = _num(candidate_row.get("rank_pct"))
    return bool(rank_pct is not None and rank_pct <= TOPK_DEFAULT_THRESHOLD_PCT)


def _num(value: Any) -> float | None:
    try:
        if value is None or _text(value) == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.8g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
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


def _read_csv(path_like: str | Path) -> tuple[list[str], list[dict[str, Any]]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _probe_by_entry(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("entry_id")): row for row in _rows(payload) if _text(row.get("entry_id"))}


def _proposed_metrics(candidate_row: dict[str, Any], probe_row: dict[str, Any]) -> dict[str, float]:
    proposed: dict[str, float] = {}
    for probe_key, candidate_key in PROBE_TO_CANDIDATE_METRICS.items():
        value = _num(probe_row.get(probe_key))
        if value is None:
            continue
        # Keep reviewed canonical values if they are already present; this
        # preview fills gaps rather than overwriting existing evidence.
        if _text(candidate_row.get(candidate_key)):
            continue
        proposed[candidate_key] = value
    return proposed


def _blocked_metrics(candidate_row: dict[str, Any], proposed: dict[str, float]) -> list[str]:
    blocked: list[str] = []
    for metric in REQUIRED_FILL_METRICS:
        if _text(candidate_row.get(metric)) or metric in proposed:
            continue
        blocked.append(metric)
    return blocked


def _preview_candidate_rows(
    candidate_rows: list[dict[str, Any]],
    fill_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fill_by_entry = {_text(row.get("entry_id")): row for row in fill_rows}
    out: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        row = dict(candidate)
        fill = fill_by_entry.get(_text(candidate.get("entry_id")), {})
        for metric in (*REQUIRED_FILL_METRICS, *OPTIONAL_FILL_METRICS):
            proposed_value = fill.get(f"proposed_{metric}")
            if proposed_value is not None and not _text(row.get(metric)):
                row[metric] = _fmt(proposed_value)
        row["pocketmd_lite_metric_fill_status"] = (
            "filled_from_claim_grade_probe" if fill.get("fill_ready") is True else "not_filled"
        )
        row["pocketmd_lite_metric_fill_source_probe_status"] = _text(fill.get("source_probe_status"))
        row["pocketmd_lite_metric_fill_source_npz"] = _text(fill.get("source_trajectory_npz"))
        out.append(row)
    return out


def build_pocketmd_lite_candidate_metric_fill_preview(
    *,
    candidate_csv: str | Path = DEFAULT_CANDIDATE_CSV,
    probe_json: str | Path = DEFAULT_PROBE_JSON,
    out_candidate_csv: str | Path = DEFAULT_OUT_CANDIDATE_CSV,
) -> dict[str, Any]:
    candidate_fieldnames, candidate_rows = _read_csv(candidate_csv)
    probe_payload = _read_json(probe_json)
    probe_summary = _summary(probe_payload)
    probe_rows = _probe_by_entry(probe_payload)

    selected_rows = [row for row in candidate_rows if _selected_for_refine(row)]
    fill_rows: list[dict[str, Any]] = []
    for candidate in selected_rows:
        entry_id = _text(candidate.get("entry_id"))
        probe_row = probe_rows.get(entry_id, {})
        proposed = _proposed_metrics(candidate, probe_row)
        blocked_metrics = _blocked_metrics(candidate, proposed)
        claim_ready = bool(probe_row.get("claim_grade_metric_ready") is True)
        fill_ready = bool(claim_ready and not blocked_metrics)
        blockers: list[str] = []
        if not probe_row:
            blockers.append("probe_row_missing")
        if not claim_ready:
            blockers.append("claim_grade_probe_metric_ready_false")
        if blocked_metrics:
            blockers.append("missing_required_fill_metrics:" + ",".join(blocked_metrics))
        fill_rows.append(
            {
                "entry_id": entry_id,
                "selected_for_refine": True,
                "probe_row_present": bool(probe_row),
                "claim_grade_metric_ready": claim_ready,
                "fill_ready": fill_ready,
                "blocked_metric_names": blocked_metrics,
                "proposed_metric_names": sorted(proposed),
                "proposed_local_min_ligand_rmsd_a": proposed.get("local_min_ligand_rmsd_a"),
                "proposed_hbond_persistence": proposed.get("hbond_persistence"),
                "proposed_initial_clash_count": proposed.get("initial_clash_count"),
                "proposed_contact_persistence": proposed.get("contact_persistence"),
                "proposed_clash_count": proposed.get("clash_count"),
                "source_probe_status": _text(probe_row.get("trajectory_probe_status")),
                "source_trajectory_npz": _text(
                    probe_row.get("exact_metric_source_npz") or probe_row.get("selected_trajectory_npz")
                ),
                "recommended_next_local_action": (
                    "run_pocketmd_lite_report_against_preview_candidate_csv"
                    if fill_ready
                    else "generate_claim_grade_probe_metrics_before_candidate_fill"
                ),
                "blockers": blockers,
                **READ_ONLY_FLAGS,
            }
        )

    ready_count = sum(1 for row in fill_rows if row["fill_ready"])
    blocked_count = len(fill_rows) - ready_count
    preview_fieldnames = list(candidate_fieldnames)
    for column in (*REQUIRED_FILL_METRICS, *OPTIONAL_FILL_METRICS, *PREVIEW_METADATA_COLUMNS):
        if column not in preview_fieldnames:
            preview_fieldnames.append(column)
    preview_rows = _preview_candidate_rows(candidate_rows, fill_rows)
    status = (
        "pocketmd_lite_candidate_metric_fill_preview_ready"
        if fill_rows and blocked_count == 0
        else "blocked_pocketmd_lite_candidate_metric_fill_preview"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "candidate_csv": _display(candidate_csv),
        "probe_json": _display(probe_json),
        "probe_status": _text(probe_summary.get("status")) or "missing",
        "preview_candidate_csv": _display(out_candidate_csv),
        "candidate_count": len(candidate_rows),
        "selected_top_k_count": len(fill_rows),
        "fill_ready_row_count": ready_count,
        "blocked_fill_row_count": blocked_count,
        "canonical_candidate_csv_mutated": False,
        "preview_candidate_csv_ready": bool(fill_rows),
        "blocked_metric_names": sorted(
            {metric for row in fill_rows for metric in row["blocked_metric_names"]}
        ),
        "next_required_step": (
            "Run the PocketMD Lite report against the preview candidate CSV and review the top-k bands."
            if status == "pocketmd_lite_candidate_metric_fill_preview_ready"
            else "Run the PocketMD Lite report against the preview candidate CSV for filled rows, and generate exact metric fields for remaining top-k rows."
            if ready_count
            else "Generate claim-grade exact metric fields in the probe before filling the candidate CSV preview."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": fill_rows,
        "preview_candidate_fieldnames": preview_fieldnames,
        "preview_candidate_rows": preview_rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def write_outputs(
    payload: dict[str, Any],
    *,
    out_json: str | Path,
    out_md: str | Path,
    out_csv: str | Path,
    out_candidate_csv: str | Path,
) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    csv_path = _resolve(out_csv)
    candidate_path = _resolve(out_candidate_csv)
    for path in (json_path, md_path, csv_path, candidate_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_CSV_COLUMNS)
        writer.writeheader()
        for row in payload["rows"]:
            writer.writerow({column: _fmt(row.get(column)) for column in ROW_CSV_COLUMNS})
    with candidate_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(payload["preview_candidate_fieldnames"])
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["preview_candidate_rows"]:
            writer.writerow({column: _fmt(row.get(column)) for column in fieldnames})


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Candidate Metric Fill Preview",
        "",
        f"- status: `{summary['status']}`",
        f"- selected_top_k_count: `{summary['selected_top_k_count']}`",
        f"- fill_ready_row_count: `{summary['fill_ready_row_count']}`",
        f"- blocked_fill_row_count: `{summary['blocked_fill_row_count']}`",
        f"- blocked_metric_names: `{', '.join(summary['blocked_metric_names']) or '(none)'}`",
        f"- preview_candidate_csv: `{summary['preview_candidate_csv']}`",
        f"- canonical_candidate_csv_mutated: `{str(summary['canonical_candidate_csv_mutated']).lower()}`",
        "",
        "## Rows",
        "",
        "| entry | fill ready | proposed metrics | blocked metrics | source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{ready}` | `{proposed}` | `{blocked}` | `{source}` |".format(
                entry=row["entry_id"],
                ready=str(row["fill_ready"]).lower(),
                proposed=", ".join(row["proposed_metric_names"]) or "(none)",
                blocked=", ".join(row["blocked_metric_names"]) or "(none)",
                source=row["source_trajectory_npz"] or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-csv", default=DEFAULT_CANDIDATE_CSV)
    parser.add_argument("--probe-json", default=DEFAULT_PROBE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-candidate-csv", default=DEFAULT_OUT_CANDIDATE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_pocketmd_lite_candidate_metric_fill_preview(
        candidate_csv=args.candidate_csv,
        probe_json=args.probe_json,
        out_candidate_csv=args.out_candidate_csv,
    )
    write_outputs(
        payload,
        out_json=args.out_json,
        out_md=args.out_md,
        out_csv=args.out_csv,
        out_candidate_csv=args.out_candidate_csv,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
