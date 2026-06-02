#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REVIEW_GATE_JSON = "casp17/casp17_organic_ligand_metric_evidence_review_gate_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_metric_operator_fill_worklist"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_operator_fill_worklist_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_operator_fill_worklist_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_OPERATOR_FILL_WORKLIST.md"

READY_REVIEW_STATUS = "field_ready_for_organic_ligand_metric_review"

ROW_COLUMNS = [
    "fill_id",
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_order",
    "field_key",
    "required_operator_value_format",
    "source_operator_template_csv",
    "source_evidence_stub_md",
    "linked_action_md",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "value_status",
    "evidence_ref_status",
    "clearance_status",
    "operator_id_status",
    "fill_status",
    "first_blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric operator-fill worklist only. It aggregates existing review-gate "
    "template/stub fields into candidate folders for manual operator fill. It does not mutate evidence "
    "templates, fill values, approve no-leak provenance, compute LDDT-PLI or BiSyRMSD, mark competitive "
    "proof, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _value(value: Any) -> str:
    text = _text(value)
    if text in {"``", "``,", "-"}:
        return ""
    if len(text) >= 2 and text[0] == "`" and text[-1] == "`":
        return text.strip("`").strip()
    return text


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] = ROW_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _field_status(value: str, present_status: str, missing_status: str) -> str:
    return present_status if _value(value) else missing_status


def _fill_status(row: dict[str, Any]) -> tuple[str, str]:
    if _text(row.get("review_gate_status")) == READY_REVIEW_STATUS:
        return "field_ready_for_review_gate", ""
    if not _value(row.get("template_operator_value")):
        return "awaiting_operator_value", "operator_value_missing"
    if not _value(row.get("template_operator_evidence_ref")):
        return "awaiting_operator_evidence_ref", "operator_evidence_ref_missing"
    if not _value(row.get("template_operator_clearance")):
        return "awaiting_operator_clearance", "operator_clearance_missing"
    if not _value(row.get("template_operator_id")):
        return "awaiting_operator_id", "operator_id_missing"
    return "awaiting_review_gate_recheck", "review_gate_status_not_ready"


def _next_action(row: dict[str, Any], fill_status: str, first_blocker: str) -> str:
    field_key = _text(row.get("field_key"))
    template_csv = _text(row.get("operator_template_csv"))
    evidence_stub = _text(row.get("evidence_stub_md"))
    if fill_status == "field_ready_for_review_gate":
        return f"{field_key} is already filled for organic ligand metric evidence review"
    if first_blocker == "operator_value_missing":
        return f"fill operator_value for {field_key} in {template_csv}"
    if first_blocker == "operator_evidence_ref_missing":
        return f"attach operator_evidence_ref for {field_key} in {template_csv} and {evidence_stub}"
    if first_blocker == "operator_clearance_missing":
        return f"fill operator_clearance for {field_key} in {template_csv}"
    if first_blocker == "operator_id_missing":
        return f"fill operator_id for {field_key} in {template_csv}"
    return f"rerun organic ligand metric evidence review gate for {field_key}"


def _build_row(index: int, review_row: dict[str, Any]) -> dict[str, Any]:
    fill_status, first_blocker = _fill_status(review_row)
    operator_value = _value(review_row.get("template_operator_value"))
    operator_evidence_ref = _value(review_row.get("template_operator_evidence_ref"))
    operator_clearance = _value(review_row.get("template_operator_clearance"))
    operator_id = _value(review_row.get("template_operator_id"))
    return {
        "fill_id": f"organic_ligand_metric_operator_fill_{index:03d}",
        "candidate_rank": _int(review_row.get("candidate_rank")),
        "candidate_id": _text(review_row.get("candidate_id")),
        "target_id": _text(review_row.get("target_id")),
        "ligand_id": _text(review_row.get("ligand_id")),
        "field_order": _int(review_row.get("field_order")),
        "field_key": _text(review_row.get("field_key")),
        "required_operator_value_format": _text(review_row.get("required_operator_value_format")),
        "source_operator_template_csv": _artifact(review_row.get("operator_template_csv")),
        "source_evidence_stub_md": _artifact(review_row.get("evidence_stub_md")),
        "linked_action_md": _artifact(review_row.get("linked_action_md")),
        "operator_value": operator_value,
        "operator_evidence_ref": operator_evidence_ref,
        "operator_clearance": operator_clearance,
        "operator_id": operator_id,
        "value_status": _field_status(operator_value, "value_present", "operator_value_missing"),
        "evidence_ref_status": _field_status(
            operator_evidence_ref, "evidence_ref_present", "operator_evidence_ref_missing"
        ),
        "clearance_status": _field_status(operator_clearance, "clearance_present", "operator_clearance_missing"),
        "operator_id_status": _field_status(operator_id, "operator_id_present", "operator_id_missing"),
        "fill_status": fill_status,
        "first_blocker": first_blocker,
        "next_action": _next_action(review_row, fill_status, first_blocker),
    }


def _status(input_missing: bool, rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_organic_ligand_metric_evidence_review_gate_missing"
    if not rows:
        return "blocked_organic_ligand_metric_operator_fill_rows_missing"
    if any(row["fill_status"] == "awaiting_operator_value" for row in rows):
        return "awaiting_organic_ligand_metric_operator_fill_values"
    if any(row["fill_status"] == "awaiting_operator_evidence_ref" for row in rows):
        return "awaiting_organic_ligand_metric_operator_evidence_refs"
    if any(row["fill_status"] == "awaiting_operator_clearance" for row in rows):
        return "awaiting_organic_ligand_metric_operator_clearance"
    if any(row["fill_status"] == "awaiting_operator_id" for row in rows):
        return "awaiting_organic_ligand_metric_operator_ids"
    if any(row["fill_status"] != "field_ready_for_review_gate" for row in rows):
        return "awaiting_organic_ligand_metric_review_gate_recheck"
    return "organic_ligand_metric_operator_fill_complete"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_path = _resolve(args.review_gate_json)
    review_payload = _read_json(review_path)
    review_summary = _summary(review_payload)
    rows = [] if not review_path.exists() else [
        _build_row(index, row) for index, row in enumerate(_rows(review_payload), start=1)
    ]
    candidate_ids = list(dict.fromkeys(row["candidate_id"] for row in rows if row["candidate_id"]))
    ready_rows = [row for row in rows if row["fill_status"] == "field_ready_for_review_gate"]
    blocked_rows = [row for row in rows if row["fill_status"] != "field_ready_for_review_gate"]
    ready_candidate_ids = {
        candidate_id
        for candidate_id in candidate_ids
        if all(row["fill_status"] == "field_ready_for_review_gate" for row in rows if row["candidate_id"] == candidate_id)
    }
    first = blocked_rows[0] if blocked_rows else (rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_organic_ligand_metric_operator_fill_worklist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_operator_fill_worklist_status": _status(not review_path.exists(), rows),
        "review_gate_json": _artifact(args.review_gate_json),
        "review_gate_status": _text(review_summary.get("organic_ligand_metric_evidence_review_gate_status")),
        "candidate_count": len(candidate_ids),
        "ready_candidate_count": len(ready_candidate_ids),
        "blocked_candidate_count": len(candidate_ids) - len(ready_candidate_ids),
        "field_action_count": len(rows),
        "field_ready_count": len(ready_rows),
        "field_blocked_count": len(blocked_rows),
        "operator_value_missing_count": sum(1 for row in rows if row["value_status"] != "value_present"),
        "operator_evidence_ref_missing_count": sum(
            1 for row in rows if row["evidence_ref_status"] != "evidence_ref_present"
        ),
        "operator_clearance_missing_count": sum(1 for row in rows if row["clearance_status"] != "clearance_present"),
        "operator_id_missing_count": sum(1 for row in rows if row["operator_id_status"] != "operator_id_present"),
        "operator_template_count": len({row["source_operator_template_csv"] for row in rows if row["source_operator_template_csv"]}),
        "evidence_stub_count": len({row["source_evidence_stub_md"] for row in rows if row["source_evidence_stub_md"]}),
        "linked_action_count": len({row["linked_action_md"] for row in rows if row["linked_action_md"]}),
        "candidate_fill_folder_count": len(candidate_ids),
        "fill_worklist_folder": _artifact(args.out_dir),
        "first_fill_id": _text(first.get("fill_id")),
        "first_candidate_id": _text(first.get("candidate_id")),
        "first_field_key": _text(first.get("field_key")),
        "first_blocker": _text(first.get("first_blocker")),
        "first_next_action": _text(first.get("next_action")),
        "next_action": (
            "Fill the candidate operator rows, rerun the organic ligand evidence review gate, then rerun "
            "the sync plan before metric computation."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Operator Fill Worklist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_operator_fill_worklist_status']}`",
        f"- review gate: `{summary['review_gate_status'] or '-'}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- fields ready/blocked/total: `{summary['field_ready_count']}/{summary['field_blocked_count']}/{summary['field_action_count']}`",
        f"- missing value/evidence/clearance/operator: `{summary['operator_value_missing_count']}/{summary['operator_evidence_ref_missing_count']}/{summary['operator_clearance_missing_count']}/{summary['operator_id_missing_count']}`",
        f"- templates/stubs/actions: `{summary['operator_template_count']}/{summary['evidence_stub_count']}/{summary['linked_action_count']}`",
        f"- candidate fill folders: `{summary['candidate_fill_folder_count']}` in `{summary['fill_worklist_folder']}`",
        f"- first fill: `{summary['first_candidate_id'] or '-'}` `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Fill Rows",
        "",
        "| fill | candidate | field | status | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fill_id']}` | `{row['candidate_id']}` | `{row['field_key']}` | "
            f"`{row['fill_status']}` | `{row['first_blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_candidate_folders(out_dir: str | Path, payload: dict[str, Any]) -> None:
    root = _resolve(out_dir)
    rows_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        candidate_id = _text(row.get("candidate_id")) or "unknown_candidate"
        rows_by_candidate.setdefault(candidate_id, []).append(row)
    for index, (candidate_id, rows) in enumerate(rows_by_candidate.items(), start=1):
        ligand_id = _text(rows[0].get("ligand_id")) if rows else candidate_id
        folder = root / f"{index:02d}_{ligand_id}"
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "operator_fill_rows.csv", rows)
        ready_count = sum(1 for row in rows if row["fill_status"] == "field_ready_for_review_gate")
        first = next((row for row in rows if row["fill_status"] != "field_ready_for_review_gate"), rows[0] if rows else {})
        lines = [
            f"# {candidate_id} Operator Fill Worklist",
            "",
            f"- ligand: `{ligand_id}`",
            f"- fields ready/blocked/total: `{ready_count}/{len(rows) - ready_count}/{len(rows)}`",
            f"- first blocker: `{first.get('field_key', '-') or '-'}` `{first.get('first_blocker', '-') or '-'}`",
            "",
            "## Fields",
            "",
            "| field | status | source template | evidence stub | linked action |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['field_key']}` | `{row['fill_status']}` | "
                f"`{row['source_operator_template_csv'] or '-'}` | "
                f"`{row['source_evidence_stub_md'] or '-'}` | "
                f"`{row['linked_action_md'] or '-'}` |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "OPERATOR_FILL.md").write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_candidate_folders(args.out_dir, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric operator fill worklist.")
    parser.add_argument("--review-gate-json", default=DEFAULT_REVIEW_GATE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
