#!/usr/bin/env python3
"""Materialize PocketMD Lite contact/clash evidence from stage3 summaries.

This is a narrow, fail-closed intake step. It can fill only the PocketMD Lite
fields that the existing stage3 summary states directly:

* contact_persistence <- frame_contact_presence_fraction
* clash_count <- 0 only when clash_count_mean_per_frame and clash_frame_fraction
  are both zero

It deliberately does not infer local-min survival or H-bond persistence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_STAGE3_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage3_summary.json"
)
DEFAULT_OUT_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_stage3_contact_clash_intake_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_stage3_contact_clash_intake_current.md"

PACKET_TYPE = "pocketmd_lite_stage3_contact_clash_intake"
SCHEMA_VERSION = "pocketmd_lite_stage3_contact_clash_intake_v1"

CONTACT_SOURCE_FIELD = "frame_contact_presence_fraction"
CLASH_MEAN_SOURCE_FIELD = "clash_count_mean_per_frame"
CLASH_FRAME_SOURCE_FIELD = "clash_frame_fraction"
REFRESH_REPORT_COMMAND = "python3 tools/product/build_pocketmd_lite_report.py"
REFRESH_WORK_ORDER_COMMAND = "python3 tools/product/build_pocketmd_lite_refinement_work_order.py"

CLAIM_BOUNDARY = (
    "PocketMD Lite stage3 contact/clash intake only; it copies exact top-k contact persistence and no-clash "
    "evidence from a local stage3 summary when present. It does not infer local-min survival, H-bond persistence, "
    "binding affinity, pose accuracy, or run any refinement/external operation."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_present(value: Any) -> bool:
    return value is not None and _text(value) != ""


def _num(value: Any) -> float | None:
    if not _is_present(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_candidate_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_candidate_rows(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _read_stage3_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if _text(obj.get("target")) and _text(obj.get("ligand_id")):
                rows.append(obj)
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return rows


def _entry_id(row: dict[str, Any]) -> str:
    return _text(row.get("entry_id")) or f"{_text(row.get('target'))}:{_text(row.get('ligand_id'))}"


def _split_entry(entry_id: str) -> tuple[str, str]:
    target, sep, ligand = entry_id.partition(":")
    return (_text(target), _text(ligand) if sep else "")


def _stage3_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        target = _text(row.get("target"))
        ligand = _text(row.get("ligand_id"))
        if target and ligand:
            lookup[f"{target}:{ligand}"] = row
    return lookup


def _ensure_fields(fieldnames: list[str]) -> list[str]:
    wanted = [
        "entry_id",
        "family",
        "rank_pct",
        "selected_for_refine",
        "local_min_ligand_rmsd_a",
        "hbond_persistence",
        "contact_persistence",
        "clash_count",
        "contact_persistence_source",
        "clash_count_source",
    ]
    out = list(fieldnames)
    for field in wanted:
        if field not in out:
            out.append(field)
    return out


def _fmt_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.6g}"


def build_pocketmd_lite_stage3_contact_clash_intake(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    stage3_json: str | Path = DEFAULT_STAGE3_JSON,
) -> dict[str, Any]:
    input_path = _resolve(input_csv)
    stage3_path = _resolve(stage3_json)
    stage3_display_path = _display_path(stage3_path)
    input_display_path = _display_path(input_path)
    if not input_path.exists():
        return {
            "packet_type": PACKET_TYPE,
            "schema_version": SCHEMA_VERSION,
            "summary": {
                "packet_type": PACKET_TYPE,
                "schema_version": SCHEMA_VERSION,
                "status": "blocked_missing_pocketmd_lite_candidate_csv",
                "candidate_count": 0,
                "stage3_source_json": stage3_display_path,
                "claim_boundary": CLAIM_BOUNDARY,
                **_READ_ONLY_FLAGS,
            },
            "rows": [],
            "claim_boundary": CLAIM_BOUNDARY,
        }

    fieldnames, candidate_rows = _read_candidate_rows(input_path)
    stage3_rows = _read_stage3_rows(stage3_path)
    lookup = _stage3_lookup(stage3_rows)
    output_fieldnames = _ensure_fields(fieldnames)
    rows: list[dict[str, Any]] = []
    updated_candidates: list[dict[str, Any]] = []

    for candidate in candidate_rows:
        updated = dict(candidate)
        entry = _entry_id(updated)
        target, ligand = _split_entry(entry)
        stage3 = lookup.get(f"{target}:{ligand}", {})
        contact = _num(stage3.get(CONTACT_SOURCE_FIELD))
        clash_mean = _num(stage3.get(CLASH_MEAN_SOURCE_FIELD))
        clash_frame = _num(stage3.get(CLASH_FRAME_SOURCE_FIELD))
        contact_filled = False
        clash_filled = False
        blockers: list[str] = []

        if contact is None:
            blockers.append("stage3_contact_persistence_missing")
        else:
            if not _is_present(updated.get("contact_persistence")):
                updated["contact_persistence"] = _fmt_number(contact)
            updated["contact_persistence_source"] = f"{stage3_display_path}:{CONTACT_SOURCE_FIELD}"
            contact_filled = _is_present(updated.get("contact_persistence"))

        if clash_mean is None or clash_frame is None:
            blockers.append("stage3_clash_evidence_missing")
        elif clash_mean == 0.0 and clash_frame == 0.0:
            if not _is_present(updated.get("clash_count")):
                updated["clash_count"] = "0"
            updated["clash_count_source"] = f"{stage3_display_path}:{CLASH_MEAN_SOURCE_FIELD},{CLASH_FRAME_SOURCE_FIELD}"
            clash_filled = _is_present(updated.get("clash_count"))
        else:
            blockers.append("stage3_nonzero_clash_observed")

        if not _is_present(updated.get("local_min_ligand_rmsd_a")):
            blockers.append("local_min_ligand_rmsd_a_missing")
        if not _is_present(updated.get("hbond_persistence")):
            blockers.append("hbond_persistence_missing")

        row = {
            "entry_id": entry,
            "target": target,
            "ligand_id": ligand,
            "stage3_row_present": bool(stage3),
            "contact_persistence_filled": contact_filled,
            "clash_count_filled": clash_filled,
            "contact_persistence": updated.get("contact_persistence", ""),
            "clash_count": updated.get("clash_count", ""),
            "local_min_ligand_rmsd_a": updated.get("local_min_ligand_rmsd_a", ""),
            "hbond_persistence": updated.get("hbond_persistence", ""),
            "contact_source_field": CONTACT_SOURCE_FIELD if contact is not None else "",
            "clash_source_fields": (
                f"{CLASH_MEAN_SOURCE_FIELD};{CLASH_FRAME_SOURCE_FIELD}"
                if clash_mean is not None and clash_frame is not None
                else ""
            ),
            "stage3_source_json": stage3_display_path,
            "blockers": ";".join(blockers),
            **_READ_ONLY_FLAGS,
        }
        rows.append(row)
        updated_candidates.append(updated)

    matched_count = sum(1 for row in rows if row["stage3_row_present"])
    contact_filled_count = sum(1 for row in rows if row["contact_persistence_filled"])
    clash_filled_count = sum(1 for row in rows if row["clash_count_filled"])
    local_min_missing_count = sum(1 for row in rows if not _is_present(row["local_min_ligand_rmsd_a"]))
    hbond_missing_count = sum(1 for row in rows if not _is_present(row["hbond_persistence"]))
    status = (
        "blocked_pocketmd_lite_stage3_partial_intake_missing_local_min_hbond"
        if local_min_missing_count or hbond_missing_count
        else "pocketmd_lite_stage3_contact_clash_intake_ready"
    )

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "packet_type": PACKET_TYPE,
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "candidate_count": len(candidate_rows),
            "stage3_matched_candidate_count": matched_count,
            "contact_persistence_filled_count": contact_filled_count,
            "clash_count_filled_count": clash_filled_count,
            "local_min_missing_count": local_min_missing_count,
            "hbond_missing_count": hbond_missing_count,
            "stage3_source_json": stage3_display_path,
            "input_csv": input_display_path,
            "refresh_report_command": REFRESH_REPORT_COMMAND,
            "refresh_work_order_command": REFRESH_WORK_ORDER_COMMAND,
            "next_required_step": (
                "Run PocketMD Lite local-min survival and H-bond persistence collection for the remaining top-k rows; "
                "then rerun the report and work order."
            ),
            "claim_boundary": CLAIM_BOUNDARY,
            **_READ_ONLY_FLAGS,
        },
        "candidate_fieldnames": output_fieldnames,
        "candidate_rows": updated_candidates,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


_RECEIPT_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "stage3_row_present",
    "contact_persistence_filled",
    "clash_count_filled",
    "contact_persistence",
    "clash_count",
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_source_field",
    "clash_source_fields",
    "stage3_source_json",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    public_payload = {k: v for k, v in payload.items() if k not in {"candidate_rows", "candidate_fieldnames"}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(public_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Stage3 Contact/Clash Intake (current)",
        "",
        "Copies only exact contact/clash evidence from the local stage3 summary. Local-min RMSD and H-bond",
        "persistence remain explicit PocketMD Lite gaps when absent.",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- stage3_matched_candidate_count: `{summary['stage3_matched_candidate_count']}`",
        f"- contact_persistence_filled_count: `{summary['contact_persistence_filled_count']}`",
        f"- clash_count_filled_count: `{summary['clash_count_filled_count']}`",
        f"- local_min_missing_count: `{summary['local_min_missing_count']}`",
        f"- hbond_missing_count: `{summary['hbond_missing_count']}`",
        "",
        "## Rows",
        "",
        "| entry | contact | clash | blockers |",
        "| --- | --: | --: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['entry_id']}` | `{row['contact_persistence']}` | `{row['clash_count']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill PocketMD Lite contact/clash evidence from a stage3 summary.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--stage3-json", default=DEFAULT_STAGE3_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_stage3_contact_clash_intake(
        input_csv=args.input_csv,
        stage3_json=args.stage3_json,
    )
    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    if payload.get("candidate_rows") is not None:
        _write_candidate_rows(out_csv, payload["candidate_fieldnames"], payload["candidate_rows"])
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
