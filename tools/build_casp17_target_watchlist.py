#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]

OFFICIAL_TARGET_CSV_URL = "https://predictioncenter.org/casp17/targetlist.cgi?type=csv"
DEFAULT_OUT_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_OUT_CSV = "runs/casp17_target_watchlist_current.csv"
DEFAULT_OUT_MD = "runs/casp17_target_watchlist_current.md"
DEFAULT_OUT_INTAKE_SEED_CSV = "runs/casp17_target_intake_seed_current.csv"

INTAKE_COLUMNS = [
    "target_id",
    "target_name",
    "lane",
    "submission_format",
    "deadline_class",
    "release_date",
    "due_date",
    "sequence_path",
    "stoichiometry",
    "ligand_info_path",
    "prediction_file_path",
    "prediction_import_status",
    "prediction_candidate_path",
    "prediction_import_blockers",
    "validation_json_path",
    "geometry_validation_json_path",
    "confidence_validation_json_path",
    "internal_scorecard_json_path",
    "format_check_status",
    "model_generation_status",
    "parameterization_status",
    "protein_local_minimization_status",
    "geometry_sanity_status",
    "confidence_calibration_status",
    "internal_scorecard_status",
    "notes",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _date(value: Any) -> dt.date | None:
    text = _clean_text(value)
    if not text or text == "-":
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if not match:
        return None
    return dt.date.fromisoformat(match.group(0))


def _days_until(value: dt.date | None, today: dt.date) -> int | None:
    return (value - today).days if value else None


def _read_source(args: argparse.Namespace) -> tuple[str, str]:
    if args.input_csv:
        path = _resolve(args.input_csv)
        return path.read_text(encoding="utf-8"), _artifact(path)
    with urlopen(args.source_url, timeout=args.timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace"), args.source_url


def _read_rows(source_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(source_text), delimiter=";")
    normalized: list[dict[str, str]] = []
    for row in reader:
        normalized.append({_key(key or ""): _clean_text(value) for key, value in row.items()})
    return normalized


def _get(row: dict[str, str], key: str) -> str:
    return row.get(_key(key), "")


def _lane_for_row(row: dict[str, str], *, canceled: bool) -> tuple[str, str, str]:
    target_id = _get(row, "Target").upper()
    target_type = _get(row, "Type")
    description = _get(row, "Description")
    type_lower = target_type.lower()
    desc_lower = description.lower()

    if canceled:
        return "out_of_scope_cancelled", "none", "target is canceled"
    if "nuca" in type_lower or "rna" in desc_lower or "ribo" in desc_lower or "hybrid" in type_lower:
        return "out_of_scope_nucleic_acid_or_hybrid", "none", "nucleic-acid or hybrid target outside current CASP17 lane"
    if "prot" in type_lower and (
        "ligand" in type_lower
        or any(token in desc_lower for token in ("small molecule", "inhibitor", "agonist", "antagonist", "substrate", "cofactor"))
    ):
        return "organic_ligand_protein_complexes", "TS", "primary ligand-protein lane"
    if target_id.startswith(("H", "T")) and "prot" in type_lower:
        return "difficult_protein_complexes", "TS", "secondary difficult protein/complex lane"
    return "out_of_scope_other", "none", "outside selected CASP17 lanes"


def _priority(lane: str, days_to_human: int | None, human_open: bool) -> int:
    if not human_open:
        return 0
    lane_rank = {
        "organic_ligand_protein_complexes": 300,
        "difficult_protein_complexes": 200,
        "accuracy_estimation": 100,
    }.get(lane, 0)
    if days_to_human is None:
        return lane_rank
    urgency = max(0, 30 - min(max(days_to_human, 0), 30))
    return lane_rank + urgency


def _deadline_class(human_open: bool, server_open: bool, days_to_human: int | None) -> str:
    if human_open:
        if days_to_human == 0:
            return "regular_expiring_today"
        if days_to_human is not None and days_to_human <= 2:
            return "regular_expiring_soon"
        return "regular"
    if server_open:
        return "server_only_or_human_closed"
    return "closed"


def _watch_row(row: dict[str, str], today: dt.date) -> dict[str, Any]:
    target_id = _get(row, "Target")
    target_type = _get(row, "Type")
    server_exp = _date(_get(row, "Server Exp."))
    human_exp = _date(_get(row, "Human Exp."))
    qa_exp = _date(_get(row, "QA Exp."))
    cancellation_date = _date(_get(row, "Cancellation Date"))
    canceled = cancellation_date is not None
    days_to_server = _days_until(server_exp, today)
    days_to_human = _days_until(human_exp, today)
    days_to_qa = _days_until(qa_exp, today)
    server_open = bool(server_exp and days_to_server is not None and days_to_server >= 0 and not canceled)
    human_open = bool(human_exp and days_to_human is not None and days_to_human >= 0 and not canceled)
    qa_open = bool(qa_exp and days_to_qa is not None and days_to_qa >= 0 and not canceled)
    lane, submission_format, lane_reason = _lane_for_row(row, canceled=canceled)
    support_accuracy = bool(qa_open and human_open and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"})
    deadline_class = _deadline_class(human_open, server_open, days_to_human)
    priority = _priority(lane, days_to_human, human_open)
    if lane.startswith("out_of_scope"):
        action = "ignore_for_selected_lanes"
    elif not human_open:
        action = "do_not_submit_closed_or_server_only"
    else:
        action = "seed_intake_no_go_until_prediction_artifacts_exist"

    return {
        "target_id": target_id,
        "target_type": target_type,
        "residues": _get(row, "Res"),
        "stoichiometry": _get(row, "Oligo.State"),
        "entry_date": _get(row, "Entry Date"),
        "server_expiration": _get(row, "Server Exp."),
        "human_expiration": _get(row, "Human Exp."),
        "qa_expiration": _get(row, "QA Exp."),
        "cancellation_date": cancellation_date.isoformat() if cancellation_date else "",
        "description": _get(row, "Description"),
        "days_to_server_expiration": days_to_server,
        "days_to_human_expiration": days_to_human,
        "days_to_qa_expiration": days_to_qa,
        "server_open": server_open,
        "human_open": human_open,
        "qa_open": qa_open,
        "deadline_class": deadline_class,
        "lane_recommendation": lane,
        "submission_format_seed": submission_format,
        "lane_reason": lane_reason,
        "support_accuracy_estimation": support_accuracy,
        "priority": priority,
        "recommended_action": action,
    }


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    source_text, source_ref = _read_source(args)
    raw_rows = _read_rows(source_text)
    watch_rows = [_watch_row(row, today) for row in raw_rows]
    watch_rows.sort(key=lambda row: (-int(row["priority"]), str(row["human_expiration"]), str(row["target_id"])))

    selected_rows = [
        row
        for row in watch_rows
        if row["human_open"] and row["lane_recommendation"] in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}
    ]
    ligand_rows = [row for row in selected_rows if row["lane_recommendation"] == "organic_ligand_protein_complexes"]
    difficult_rows = [row for row in selected_rows if row["lane_recommendation"] == "difficult_protein_complexes"]
    expiring_rows = [row for row in selected_rows if row["deadline_class"] in {"regular_expiring_today", "regular_expiring_soon"}]

    intake_rows = [_intake_seed_row(row) for row in selected_rows]
    summary = {
        "packet_type": "casp17_target_watchlist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source_ref,
        "today": today.isoformat(),
        "raw_target_count": len(watch_rows),
        "selected_lane_open_target_count": len(selected_rows),
        "primary_ligand_open_target_count": len(ligand_rows),
        "secondary_difficult_open_target_count": len(difficult_rows),
        "expiring_selected_target_count": len(expiring_rows),
        "accuracy_estimation_support_candidate_count": sum(1 for row in selected_rows if row["support_accuracy_estimation"]),
        "registration_action": "register_regular_group_now_submission_gated",
        "submission_action": "do_not_submit_until_intake_seed_rows_pass_casp17_submission_gate",
        "top_selected_targets": [row["target_id"] for row in selected_rows[:10]],
        "claim_boundary": "Target watchlist and intake seed only; not a CASP17 submission or performance claim.",
    }
    payload = {"summary": summary, "rows": watch_rows}
    return payload, watch_rows, intake_rows


def _intake_seed_row(row: dict[str, Any]) -> dict[str, str]:
    return {
        "target_id": str(row["target_id"]),
        "target_name": str(row["description"]),
        "lane": str(row["lane_recommendation"]),
        "submission_format": str(row["submission_format_seed"]),
        "deadline_class": "regular" if row["human_open"] else str(row["deadline_class"]),
        "release_date": str(row["entry_date"]),
        "due_date": str(row["human_expiration"]),
        "sequence_path": "",
        "stoichiometry": str(row["stoichiometry"]),
        "ligand_info_path": "",
        "prediction_file_path": "",
        "prediction_import_status": "missing",
        "prediction_candidate_path": "",
        "prediction_import_blockers": "",
        "validation_json_path": "",
        "geometry_validation_json_path": "",
        "confidence_validation_json_path": "",
        "internal_scorecard_json_path": "",
        "format_check_status": "missing",
        "model_generation_status": "missing",
        "parameterization_status": "missing" if row["lane_recommendation"] == "organic_ligand_protein_complexes" else "not_applicable",
        "protein_local_minimization_status": "missing" if row["lane_recommendation"] == "organic_ligand_protein_complexes" else "not_applicable",
        "geometry_sanity_status": "missing",
        "confidence_calibration_status": "missing",
        "internal_scorecard_status": "missing",
        "notes": "Seeded from CASP17 official target list; remains no-go until prediction artifacts and validation pass.",
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_intake_seed_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    summary = payload["summary"]
    selected = [
        row
        for row in rows
        if row["human_open"] and row["lane_recommendation"] in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}
    ][:12]
    lines = [
        "# CASP17 Target Watchlist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source: `{summary['source']}`",
        f"- today: `{summary['today']}`",
        f"- raw targets: `{summary['raw_target_count']}`",
        f"- selected-lane open targets: `{summary['selected_lane_open_target_count']}`",
        f"- primary ligand open targets: `{summary['primary_ligand_open_target_count']}`",
        f"- secondary difficult open targets: `{summary['secondary_difficult_open_target_count']}`",
        f"- expiring selected targets: `{summary['expiring_selected_target_count']}`",
        f"- registration action: `{summary['registration_action']}`",
        f"- submission action: `{summary['submission_action']}`",
        "",
        "## Top Open Selected-Lane Targets",
        "",
        "| target | lane | human exp. | QA exp. | priority | action | description |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in selected:
        lines.append(
            f"| `{row['target_id']}` | `{row['lane_recommendation']}` | `{row['human_expiration']}` | "
            f"`{row['qa_expiration']}` | {row['priority']} | `{row['recommended_action']}` | {row['description']} |"
        )
    if not selected:
        lines.append("| - | - | - | - | 0 | `no_open_selected_lane_targets` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 official-target watchlist and gated intake seed.")
    parser.add_argument("--input-csv", default="", help="Optional local CASP17 semicolon-delimited target CSV.")
    parser.add_argument("--source-url", default=OFFICIAL_TARGET_CSV_URL, help="CASP17 official target CSV URL.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Network timeout for official source fetch.")
    parser.add_argument("--today", default="", help="Override current date as YYYY-MM-DD for reproducible runs.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-seed-csv", default=DEFAULT_OUT_INTAKE_SEED_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, rows, intake_rows = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    _write_intake_seed_csv(args.out_intake_seed_csv, intake_rows)
    _write_md(args.out_md, payload, rows)


if __name__ == "__main__":
    main()
