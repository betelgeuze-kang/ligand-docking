#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EVIDENCE_INTAKE_JSON = "casp17/casp17_organic_ligand_metric_evidence_intake_current.json"
DEFAULT_OUT_DIR = "casp17/organic_ligand_metric_evidence_review_gate"
DEFAULT_OUT_JSON = "casp17/casp17_organic_ligand_metric_evidence_review_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organic_ligand_metric_evidence_review_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIC_LIGAND_METRIC_EVIDENCE_REVIEW_GATE.md"

CLEAR_VALUES = {"approved", "clear", "cleared", "true", "yes", "operator_clear", "operator_approved"}

ROW_COLUMNS = [
    "candidate_rank",
    "candidate_id",
    "target_id",
    "ligand_id",
    "field_order",
    "field_key",
    "evidence_request_kind",
    "required_operator_value_format",
    "template_operator_value",
    "template_operator_evidence_ref",
    "template_operator_clearance",
    "template_operator_id",
    "evidence_stub_md",
    "stub_exists",
    "stub_operator_value",
    "stub_operator_evidence_ref",
    "stub_operator_clearance",
    "stub_operator_id",
    "template_value_status",
    "template_evidence_ref_status",
    "template_clearance_status",
    "template_operator_id_status",
    "stub_status",
    "stub_evidence_status",
    "policy_status",
    "review_gate_status",
    "first_blocker",
    "next_action",
    "operator_template_csv",
    "linked_action_md",
]

CLAIM_BOUNDARY = (
    "Local CASP17 organic ligand metric evidence review gate only. It validates whether generated "
    "operator templates and evidence stubs contain evidence-shaped values for organic ligand metric "
    "review. It does not fill operator values, approve no-leak provenance, compute LDDT-PLI or BiSyRMSD, "
    "mark competitive proof, serialize a CASP author code, or submit to CASP."
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
    if text in {"``,", "``"}:
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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    if not str(path_like).strip():
        return []
    path = _resolve(path_like)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _parse_stub(path_like: str | Path) -> dict[str, str]:
    fields = {
        "operator_value": "",
        "operator_evidence_ref": "",
        "operator_clearance": "",
        "operator_id": "",
    }
    path = _resolve(path_like)
    if not path.is_file():
        return fields
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        for key in list(fields):
            prefix = f"- {key}:"
            if stripped.startswith(prefix):
                fields[key] = _value(stripped[len(prefix) :])
        if stripped.startswith("- evidence_ref:") and not fields["operator_evidence_ref"]:
            fields["operator_evidence_ref"] = _value(stripped[len("- evidence_ref:") :])
    return fields


def _template_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, str]]:
    cache: dict[str, list[dict[str, str]]] = {}
    index: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        template_path = _text(row.get("operator_template_csv"))
        if template_path not in cache:
            cache[template_path] = _read_csv(template_path)
        field_key = _text(row.get("field_key"))
        for template_row in cache[template_path]:
            if _text(template_row.get("field_key")) == field_key:
                index[(template_path, field_key)] = template_row
                break
    return index


def _policy_status(operator_value: str, operator_clearance: str) -> str:
    if not operator_value:
        return "policy_not_checked_value_missing"
    if not operator_clearance:
        return "policy_not_checked_clearance_missing"
    if operator_clearance.lower() not in CLEAR_VALUES:
        return "policy_fail_clearance_not_approved"
    return "policy_pass"


def _next_action(row: dict[str, Any], blockers: list[str]) -> str:
    field_key = row["field_key"]
    first = blockers[0] if blockers else ""
    if first == "template_operator_value_missing":
        return f"fill operator_value for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_evidence_ref_missing":
        return f"fill operator_evidence_ref for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_clearance_missing":
        return f"fill operator_clearance for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_id_missing":
        return f"fill operator_id for {field_key} in operator_evidence_template.csv"
    if first == "stub_missing":
        return f"restore evidence stub {row['evidence_stub_md']}"
    if first.startswith("stub_"):
        return f"fill {first.removeprefix('stub_').removesuffix('_missing')} in {row['evidence_stub_md']}"
    if first.startswith("policy_fail"):
        return f"revise operator clearance for {field_key} before ligand metric review"
    return f"review accepted evidence for {field_key}, then sync into organic ligand metric actions"


def _review_row(intake_row: dict[str, Any], template: dict[str, str]) -> dict[str, Any]:
    operator_value = _value(template.get("operator_value"))
    operator_evidence_ref = _value(template.get("operator_evidence_ref"))
    operator_clearance = _value(template.get("operator_clearance"))
    operator_id = _value(template.get("operator_id"))
    stub_path = _text(intake_row.get("evidence_stub_md") or template.get("evidence_stub_md"))
    stub_exists = _resolve(stub_path).is_file() if stub_path else False
    stub_fields = _parse_stub(stub_path)
    template_value_status = "template_operator_value_present" if operator_value else "template_operator_value_missing"
    template_evidence_ref_status = (
        "template_operator_evidence_ref_present"
        if operator_evidence_ref
        else "template_operator_evidence_ref_missing"
    )
    template_clearance_status = (
        "template_operator_clearance_present" if operator_clearance else "template_operator_clearance_missing"
    )
    template_operator_id_status = "template_operator_id_present" if operator_id else "template_operator_id_missing"
    stub_status = "stub_present" if stub_exists else "stub_missing"
    stub_blockers = [
        f"stub_{key}_missing"
        for key, value in stub_fields.items()
        if not _value(value)
    ]
    stub_evidence_status = "stub_evidence_present" if not stub_blockers else ",".join(stub_blockers)
    policy_status = _policy_status(operator_value, operator_clearance)
    blockers = []
    for status in [
        template_value_status,
        template_evidence_ref_status,
        template_clearance_status,
        template_operator_id_status,
        stub_status,
        *stub_blockers,
        policy_status,
    ]:
        if status.endswith("_missing") or status.startswith("policy_fail") or status.startswith("policy_not_checked"):
            blockers.append(status)
    review_gate_status = "field_ready_for_organic_ligand_metric_review" if not blockers else "blocked"
    row = {
        "candidate_rank": _int(intake_row.get("candidate_rank")),
        "candidate_id": _text(intake_row.get("candidate_id")),
        "target_id": _text(intake_row.get("target_id")),
        "ligand_id": _text(intake_row.get("ligand_id")),
        "field_order": _int(intake_row.get("field_order")),
        "field_key": _text(intake_row.get("field_key")),
        "evidence_request_kind": _text(intake_row.get("evidence_request_kind")),
        "required_operator_value_format": _text(intake_row.get("required_operator_value_format")),
        "template_operator_value": operator_value,
        "template_operator_evidence_ref": operator_evidence_ref,
        "template_operator_clearance": operator_clearance,
        "template_operator_id": operator_id,
        "evidence_stub_md": _artifact(stub_path),
        "stub_exists": str(stub_exists),
        "stub_operator_value": _value(stub_fields.get("operator_value")),
        "stub_operator_evidence_ref": _value(stub_fields.get("operator_evidence_ref")),
        "stub_operator_clearance": _value(stub_fields.get("operator_clearance")),
        "stub_operator_id": _value(stub_fields.get("operator_id")),
        "template_value_status": template_value_status,
        "template_evidence_ref_status": template_evidence_ref_status,
        "template_clearance_status": template_clearance_status,
        "template_operator_id_status": template_operator_id_status,
        "stub_status": stub_status,
        "stub_evidence_status": stub_evidence_status,
        "policy_status": policy_status,
        "review_gate_status": review_gate_status,
        "first_blocker": blockers[0] if blockers else "",
        "operator_template_csv": _artifact(intake_row.get("operator_template_csv")),
        "linked_action_md": _artifact(intake_row.get("linked_action_md")),
    }
    row["next_action"] = _next_action(row, blockers)
    return row


def _status(input_missing: bool, rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_organic_ligand_metric_evidence_intake_missing"
    if not rows:
        return "blocked_organic_ligand_metric_evidence_review_rows_missing"
    if any(row["review_gate_status"] != "field_ready_for_organic_ligand_metric_review" for row in rows):
        return "awaiting_organic_ligand_metric_evidence_review"
    return "organic_ligand_metric_evidence_review_ready"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_path = _resolve(args.evidence_intake_json)
    intake_payload = _read_json(intake_path)
    intake_summary = _summary(intake_payload)
    intake_rows = _rows(intake_payload)
    templates = _template_index(intake_rows)
    rows = [
        _review_row(row, templates.get((_text(row.get("operator_template_csv")), _text(row.get("field_key"))), {}))
        for row in intake_rows
    ]
    ready_rows = [row for row in rows if row["review_gate_status"] == "field_ready_for_organic_ligand_metric_review"]
    blocked_rows = [row for row in rows if row["review_gate_status"] != "field_ready_for_organic_ligand_metric_review"]
    candidate_ids = list(dict.fromkeys(row["candidate_id"] for row in rows if row["candidate_id"]))
    ready_candidate_ids = {
        candidate_id
        for candidate_id in candidate_ids
        if all(
            row["review_gate_status"] == "field_ready_for_organic_ligand_metric_review"
            for row in rows
            if row["candidate_id"] == candidate_id
        )
    }
    first_blocked = blocked_rows[0] if blocked_rows else {}
    summary = {
        "packet_type": "casp17_organic_ligand_metric_evidence_review_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "organic_ligand_metric_evidence_review_gate_status": _status(not intake_path.exists(), rows),
        "evidence_intake_json": _artifact(args.evidence_intake_json),
        "evidence_intake_status": _text(
            intake_summary.get("organic_ligand_metric_evidence_intake_status")
        ),
        "out_dir": _artifact(args.out_dir),
        "candidate_count": len(candidate_ids),
        "ready_candidate_count": len(ready_candidate_ids),
        "blocked_candidate_count": len(candidate_ids) - len(ready_candidate_ids),
        "field_count": len(rows),
        "ready_field_count": len(ready_rows),
        "blocked_field_count": len(blocked_rows),
        "template_operator_value_missing_count": sum(
            1 for row in rows if row["template_value_status"] == "template_operator_value_missing"
        ),
        "template_operator_evidence_ref_missing_count": sum(
            1
            for row in rows
            if row["template_evidence_ref_status"] == "template_operator_evidence_ref_missing"
        ),
        "template_operator_clearance_missing_count": sum(
            1 for row in rows if row["template_clearance_status"] == "template_operator_clearance_missing"
        ),
        "template_operator_id_missing_count": sum(
            1 for row in rows if row["template_operator_id_status"] == "template_operator_id_missing"
        ),
        "stub_present_count": sum(1 for row in rows if row["stub_status"] == "stub_present"),
        "stub_missing_count": sum(1 for row in rows if row["stub_status"] == "stub_missing"),
        "stub_evidence_missing_count": sum(
            1 for row in rows if row["stub_evidence_status"] != "stub_evidence_present"
        ),
        "policy_pass_count": sum(1 for row in rows if row["policy_status"] == "policy_pass"),
        "policy_blocked_count": sum(1 for row in rows if row["policy_status"] != "policy_pass"),
        "first_blocked_candidate_id": _text(first_blocked.get("candidate_id")),
        "first_blocked_field_key": _text(first_blocked.get("field_key")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "next_action": (
            "Fill operator evidence templates and field stubs, then rerun this review gate before promoting "
            "organic ligand rows into LDDT-PLI or BiSyRMSD metric computation."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_candidate_reviews(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    rows_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        rows_by_candidate.setdefault(row["candidate_id"], []).append(row)
    for candidate_id, rows in rows_by_candidate.items():
        folder_name = f"{_int(rows[0].get('candidate_rank')):02d}_{rows[0]['ligand_id']}"
        folder = _resolve(args.out_dir) / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "review_rows.csv", rows)
        lines = [
            f"# Organic Ligand Metric Evidence Review - {candidate_id}",
            "",
            f"- target_id: `{rows[0]['target_id']}`",
            f"- ligand_id: `{rows[0]['ligand_id']}`",
            f"- fields ready/blocked/total: `{sum(1 for row in rows if row['review_gate_status'] == 'field_ready_for_organic_ligand_metric_review')}/{sum(1 for row in rows if row['review_gate_status'] != 'field_ready_for_organic_ligand_metric_review')}/{len(rows)}`",
            "",
            "| field | status | first blocker | next action |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['field_key']}` | `{row['review_gate_status']}` | "
                f"`{row['first_blocker'] or '-'}` | {row['next_action']} |"
            )
        lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
        (folder / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Organic Ligand Metric Evidence Review Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['organic_ligand_metric_evidence_review_gate_status']}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['field_count']}`",
        f"- template missing value/evidence/clearance/operator: `{summary['template_operator_value_missing_count']}/{summary['template_operator_evidence_ref_missing_count']}/{summary['template_operator_clearance_missing_count']}/{summary['template_operator_id_missing_count']}`",
        f"- stubs present/missing/evidence-missing: `{summary['stub_present_count']}/{summary['stub_missing_count']}/{summary['stub_evidence_missing_count']}`",
        f"- policy pass/blocked: `{summary['policy_pass_count']}/{summary['policy_blocked_count']}`",
        f"- first blocked: `{summary['first_blocked_candidate_id'] or '-'}` `{summary['first_blocked_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Review Rows",
        "",
        "| candidate | field | status | first blocker | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['field_key']}` | `{row['review_gate_status']}` | "
            f"`{row['first_blocker'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_candidate_reviews(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 organic ligand metric evidence review gate.")
    parser.add_argument("--evidence-intake-json", default=DEFAULT_EVIDENCE_INTAKE_JSON)
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
