#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_JSON = "runs/pxr_packet_fill_queue_current.json"
DEFAULT_LIGAND_WORKBOOK_JSON = "runs/pxr_ligand_packet_fill_workbook_current.json"
DEFAULT_REPLACEMENT_CSV = "runs/pxr_packet_replacement_workbook_current.csv"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _row_key(packet: str, role: str, ligand_id: str) -> str:
    return f"{packet}|{role}|{ligand_id}"


def _split_missing_fields(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def build_payload(
    queue_payload: dict[str, Any],
    ligand_workbook_payload: dict[str, Any],
    replacement_rows: list[dict[str, str]],
) -> dict[str, Any]:
    queue_rows = list(queue_payload.get("queue_rows", []))
    ligand_rows = list(ligand_workbook_payload.get("workbook_rows", []))

    queue_step_counts = Counter(str(row.get("packet_step", "")).strip() for row in queue_rows)
    queue_index = {
        _row_key(
            str(row.get("packet", "")).strip(),
            str(row.get("current_role", "")).strip(),
            str(row.get("current_ligand_id", "")).strip(),
        ): row
        for row in queue_rows
    }
    ligand_index = {
        _row_key(
            str(row.get("packet", "")).strip(),
            str(row.get("role", "")).strip(),
            str(row.get("ligand_id", "")).strip(),
        ): row
        for row in ligand_rows
    }

    replacement_step_counts = Counter(str(row.get("packet_step", "")).strip() for row in replacement_rows)
    replacement_index = {
        _row_key(
            str(row.get("packet", "")).strip(),
            str(row.get("replacement_role", "") or row.get("current_role", "")).strip(),
            str(row.get("current_ligand_id", "")).strip(),
        ): row
        for row in replacement_rows
    }

    readiness_rows: list[dict[str, Any]] = []
    missing_counter: Counter[str] = Counter()
    packet_ready_counter: defaultdict[str, int] = defaultdict(int)

    for key, queue_row in queue_index.items():
        packet = str(queue_row.get("packet", "")).strip()
        current_role = str(queue_row.get("current_role", "")).strip()
        current_ligand_id = str(queue_row.get("current_ligand_id", "")).strip()
        packet_step = str(queue_row.get("packet_step", "")).strip()
        ligand_row = ligand_index.get(key, {})
        replacement_row = replacement_index.get(key, {})
        missing_fields = _split_missing_fields(str(replacement_row.get("required_missing_fields", "")))
        for field in missing_fields:
            missing_counter[field] += 1
        ready_for_apply = str(replacement_row.get("row_ready_for_apply", "")).strip().lower() == "yes" and not missing_fields
        if ready_for_apply:
            packet_ready_counter[packet] += 1
        readiness_rows.append(
            {
                "queue_row_key": key,
                "packet": packet,
                "packet_step": packet_step,
                "packet_step_duplicate_in_queue": "yes" if queue_step_counts[packet_step] > 1 else "no",
                "packet_step_duplicate_in_replacement_workbook": "yes" if replacement_step_counts[packet_step] > 1 else "no",
                "current_role": current_role,
                "current_ligand_id": current_ligand_id,
                "queue_row_present": "yes",
                "ligand_workbook_row_present": "yes" if ligand_row else "no",
                "replacement_workbook_row_present": "yes" if replacement_row else "no",
                "placeholder_sources": str(queue_row.get("placeholder_sources", "")).strip(),
                "required_missing_fields": ",".join(missing_fields),
                "ready_for_apply": "yes" if ready_for_apply else "no",
                "next_action": (
                    "Resolve duplicate packet_step naming and fill replacement workbook fields."
                    if queue_step_counts[packet_step] > 1 or replacement_step_counts[packet_step] > 1
                    else "Fill replacement workbook fields until required_missing_fields is empty."
                ),
            }
        )

    packets = sorted({str(row.get("packet", "")).strip() for row in readiness_rows})
    packet_summaries = []
    for packet in packets:
        packet_rows = [row for row in readiness_rows if row["packet"] == packet]
        packet_summaries.append(
            {
                "packet": packet,
                "queue_rows": len(packet_rows),
                "ready_for_apply_rows": packet_ready_counter.get(packet, 0),
                "duplicate_packet_step_rows": sum(
                    1 for row in packet_rows if row["packet_step_duplicate_in_queue"] == "yes"
                ),
                "missing_field_rows": sum(1 for row in packet_rows if row["required_missing_fields"]),
            }
        )

    summary = {
        "queue_row_count": len(queue_rows),
        "ligand_workbook_row_count": len(ligand_rows),
        "replacement_workbook_row_count": len(replacement_rows),
        "matched_queue_rows": len(readiness_rows),
        "ready_for_apply_row_count": sum(1 for row in readiness_rows if row["ready_for_apply"] == "yes"),
        "blocked_row_count": sum(1 for row in readiness_rows if row["ready_for_apply"] != "yes"),
        "duplicate_packet_step_count": sum(1 for step, count in queue_step_counts.items() if step and count > 1),
        "most_common_missing_field": missing_counter.most_common(1)[0][0] if missing_counter else "",
        "next_required_step": (
            "Disambiguate duplicate packet_step names and fill replacement workbook rows until required_missing_fields is empty."
            if any(count > 1 for count in queue_step_counts.values()) or any(count > 1 for count in replacement_step_counts.values())
            else "Fill replacement workbook rows until required_missing_fields is empty."
        ),
    }
    return {
        "target": queue_payload.get("target", ""),
        "summary": summary,
        "packet_summaries": packet_summaries,
        "readiness_rows": readiness_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PXR Packet Fill Readiness",
        "",
        f"- target: `{payload['target']}`",
        f"- matched_queue_rows: `{payload['summary']['matched_queue_rows']}`",
        f"- ready_for_apply_row_count: `{payload['summary']['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{payload['summary']['blocked_row_count']}`",
        f"- duplicate_packet_step_count: `{payload['summary']['duplicate_packet_step_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Packet Summary",
        "",
        "| packet | queue_rows | ready_for_apply_rows | duplicate_packet_step_rows | missing_field_rows |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["packet_summaries"]:
        lines.append(
            f"| {row['packet']} | {row['queue_rows']} | {row['ready_for_apply_rows']} | {row['duplicate_packet_step_rows']} | {row['missing_field_rows']} |"
        )
    lines.extend(
        [
            "",
            "## Readiness Rows",
            "",
            "| queue_row_key | packet_step | ligand_id | replacement_workbook | missing_fields | duplicate_packet_step | ready_for_apply |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["readiness_rows"]:
        duplicate = "yes" if (
            row["packet_step_duplicate_in_queue"] == "yes"
            or row["packet_step_duplicate_in_replacement_workbook"] == "yes"
        ) else "no"
        lines.append(
            f"| `{row['queue_row_key']}` | {row['packet_step']} | `{row['current_ligand_id']}` | {row['replacement_workbook_row_present']} | {row['required_missing_fields']} | {duplicate} | {row['ready_for_apply']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PXR packet fill readiness across queue/workbook artifacts.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--ligand-workbook-json", default=DEFAULT_LIGAND_WORKBOOK_JSON)
    parser.add_argument("--replacement-csv", default=DEFAULT_REPLACEMENT_CSV)
    parser.add_argument("--out-json", default="runs/pxr_packet_fill_readiness_current.json")
    parser.add_argument("--out-csv", default="runs/pxr_packet_fill_readiness_current.csv")
    parser.add_argument("--out-md", default="runs/pxr_packet_fill_readiness_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_payload = _load_json(_resolve(args.queue_json))
    ligand_workbook_payload = _load_json(_resolve(args.ligand_workbook_json))
    replacement_rows = _load_csv(_resolve(args.replacement_csv))
    payload = build_payload(queue_payload, ligand_workbook_payload, replacement_rows)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["readiness_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
