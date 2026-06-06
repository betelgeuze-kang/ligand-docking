#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
DEFAULT_INTAKE_DIR = "casp17/historical_seed_strict_blind_replacement_intake"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_intake_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_INTAKE.md"

REQUIRED_FIELDS = [
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_pdb",
    "native_pdb",
    "native_authority_ref",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "no_leak_evidence_ref",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "ablation_manifest_ref",
    "calibration_values_ref",
    "operator_clearance",
]

TRUE_FIELDS = {
    "target_identity_non_current_historical",
    "prediction_generated_before_native_release",
}
FALSE_FIELDS = {
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
}
DATE_FIELDS = {"prediction_created_at", "native_release_date"}
PDB_FIELDS = {"prediction_pdb", "native_pdb"}
LOCAL_REF_FIELDS = {
    "native_authority_ref",
    "no_leak_evidence_ref",
    "ablation_manifest_ref",
    "calibration_values_ref",
}
TRUE_VALUES = {"1", "true", "yes", "y", "cleared", "clear", "confirmed"}
FALSE_VALUES = {"0", "false", "no", "n", "none", "not_used", "confirmed_false"}
CLEAR_VALUES = {"cleared", "clear", "approved", "operator_cleared", "ready", "true", "yes"}
URL_PREFIXES = ("http://", "https://")

INTAKE_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    *REQUIRED_FIELDS,
    "operator",
    "notes",
]

PREFLIGHT_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "template_status",
    "preflight_status",
    "filled_field_count",
    "missing_field_count",
    "required_field_count",
    "replacement_target_id",
    "replacement_benchmark_id",
    "prediction_pdb",
    "native_pdb",
    "no_leak_evidence_ref",
    "ablation_manifest_ref",
    "calibration_values_ref",
    "intake_csv",
    "preflight_csv",
    "preflight_md",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical strict-blind replacement intake/preflight only. It creates per-slot operator intake "
    "templates and validates required strict-blind evidence fields before a replacement can enter competitive "
    "proof. It does not choose replacement targets, approve no-leak provenance, fetch structures, compute CASP "
    "metrics, mutate benchmark/operator CSVs, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _is_true(value: Any) -> bool:
    return _text(value).lower() in TRUE_VALUES


def _is_false(value: Any) -> bool:
    return _text(value).lower() in FALSE_VALUES


def _date_or_none(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _sha256(path_like: str | Path) -> str:
    return hashlib.sha256(_resolve(path_like).read_bytes()).hexdigest()


def _placeholder_row(queue_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "queue_rank": _int(queue_row.get("queue_rank")),
        "required_benchmark_id": _text(queue_row.get("required_benchmark_id")),
        "required_target_id": _text(queue_row.get("required_target_id")),
        "scope": _text(queue_row.get("scope")),
        "metric_profile": _text(queue_row.get("metric_profile")),
        "replacement_target_id": "REQUIRED_CLOSED_HISTORICAL_TARGET_ID",
        "replacement_benchmark_id": "REQUIRED_REPLACEMENT_BENCHMARK_ID",
        "target_identity_non_current_historical": "REQUIRED_TRUE_CONFIRMATION",
        "prediction_pdb": "REQUIRED_LOCAL_PREDICTION_PDB",
        "native_pdb": "REQUIRED_LOCAL_NATIVE_PDB",
        "native_authority_ref": "REQUIRED_LOCAL_NATIVE_AUTHORITY_REF",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_REF",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "ablation_manifest_ref": "REQUIRED_LOCAL_ABLATION_MANIFEST_REF",
        "calibration_values_ref": "REQUIRED_LOCAL_CALIBRATION_VALUES_REF",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "operator": "REQUIRED_OPERATOR_ID",
        "notes": "Fill only with strict-blind historical replacement evidence; placeholders block competitive proof.",
    }


def _ensure_intake_csv(path_like: str | Path, queue_row: dict[str, Any]) -> str:
    path = _resolve(path_like)
    if path.exists():
        return "preserved"
    _write_csv(path, [_placeholder_row(queue_row)], INTAKE_COLUMNS)
    return "created"


def _pdb_blockers(path_like: Any, *, field_name: str) -> list[str]:
    path_text = _text(path_like)
    if _is_placeholder(path_text):
        return [f"{field_name}_required"]
    path = _resolve(path_text)
    if not path.exists():
        return [f"{field_name}_missing"]
    if not path.is_file():
        return [f"{field_name}_not_file"]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [f"{field_name}_unreadable"]
    atom_lines = [line for line in lines if line.startswith(("ATOM", "HETATM"))]
    protein_atom_lines = [line for line in lines if line.startswith("ATOM")]
    if not atom_lines:
        return [f"{field_name}_has_no_atom_records"]
    if not protein_atom_lines:
        return [f"{field_name}_has_no_protein_atom_records"]
    for line in atom_lines:
        try:
            float(line[30:38])
            float(line[38:46])
            float(line[46:54])
        except ValueError:
            return [f"{field_name}_coordinates_invalid"]
    return []


def _local_ref_blockers(value: Any, *, field_name: str) -> list[str]:
    ref = _text(value)
    if _is_placeholder(ref):
        return [f"{field_name}_required"]
    if ref.lower().startswith(URL_PREFIXES):
        return [f"{field_name}_must_be_local_file"]
    path = _resolve(ref)
    if not path.exists():
        return [f"{field_name}_missing"]
    if not path.is_file():
        return [f"{field_name}_not_file"]
    return []


def _native_prediction_identity_blockers(candidate: dict[str, str]) -> list[str]:
    prediction_text = _text(candidate.get("prediction_pdb"))
    native_text = _text(candidate.get("native_pdb"))
    if _is_placeholder(prediction_text) or _is_placeholder(native_text):
        return []
    prediction = _resolve(prediction_text)
    native = _resolve(native_text)
    if not prediction.is_file() or not native.is_file():
        return []
    try:
        if prediction.samefile(native):
            return ["prediction_pdb_same_path_as_native_pdb"]
        if _sha256(prediction) == _sha256(native):
            return ["prediction_pdb_identical_to_native_pdb"]
    except OSError:
        return ["prediction_native_identity_check_failed"]
    return []


def _validation_blockers(candidate: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    for field in REQUIRED_FIELDS:
        if _is_placeholder(candidate.get(field)):
            blockers.append(f"{field}_required")
    for field in TRUE_FIELDS:
        if not _is_placeholder(candidate.get(field)) and not _is_true(candidate.get(field)):
            blockers.append(f"{field}_must_be_true")
    for field in FALSE_FIELDS:
        if not _is_placeholder(candidate.get(field)) and not _is_false(candidate.get(field)):
            blockers.append(f"{field}_must_be_false")
    for field in DATE_FIELDS:
        if not _is_placeholder(candidate.get(field)) and _date_or_none(candidate.get(field)) is None:
            blockers.append(f"{field}_invalid_iso_date")
    prediction_date = _date_or_none(candidate.get("prediction_created_at"))
    native_date = _date_or_none(candidate.get("native_release_date"))
    if prediction_date and native_date and prediction_date >= native_date:
        blockers.append("prediction_created_at_not_before_native_release_date")
    for field in PDB_FIELDS:
        if not _is_placeholder(candidate.get(field)):
            blockers.extend(_pdb_blockers(candidate.get(field), field_name=field))
    for field in LOCAL_REF_FIELDS:
        if not _is_placeholder(candidate.get(field)):
            blockers.extend(_local_ref_blockers(candidate.get(field), field_name=field))
    if not _is_placeholder(candidate.get("operator_clearance")) and not (
        _text(candidate.get("operator_clearance")).lower() in CLEAR_VALUES
    ):
        blockers.append("operator_clearance_not_clear")
    blockers.extend(_native_prediction_identity_blockers(candidate))
    return list(dict.fromkeys(blockers))


def _write_row_md(path: Path, preflight_row: dict[str, Any]) -> None:
    lines = [
        f"# {preflight_row['required_benchmark_id']} Strict-Blind Replacement Intake",
        "",
        f"- status: `{preflight_row['preflight_status']}`",
        f"- template status: `{preflight_row['template_status']}`",
        f"- required target: `{preflight_row['required_target_id']}`",
        f"- scope: `{preflight_row['scope']}`",
        f"- filled/missing/required fields: `{preflight_row['filled_field_count']}/{preflight_row['missing_field_count']}/{preflight_row['required_field_count']}`",
        f"- replacement target: `{preflight_row['replacement_target_id'] or '-'}`",
        f"- intake csv: `{preflight_row['intake_csv']}`",
        f"- preflight csv: `{preflight_row['preflight_csv']}`",
        f"- blockers: `{preflight_row['blockers'] or '-'}`",
        f"- next action: {preflight_row['next_action'] or '-'}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_preflight_row(queue_row: dict[str, Any], intake_dir: str | Path) -> dict[str, Any]:
    queue_rank = _int(queue_row.get("queue_rank"))
    benchmark_id = _text(queue_row.get("required_benchmark_id"))
    folder = _resolve(intake_dir) / f"{queue_rank:02d}_{_safe_name(benchmark_id or _text(queue_row.get('required_target_id')))}"
    intake_csv = folder / "replacement_candidate_intake.csv"
    preflight_csv = folder / "replacement_candidate_preflight.csv"
    preflight_md = folder / "PREFLIGHT.md"
    template_status = _ensure_intake_csv(intake_csv, queue_row)
    candidate = (_read_csv_rows(intake_csv) or [{}])[0]
    missing_fields = [field for field in REQUIRED_FIELDS if _is_placeholder(candidate.get(field))]
    filled_field_count = len(REQUIRED_FIELDS) - len(missing_fields)
    blockers = _validation_blockers(candidate)
    ready = not blockers
    preflight_status = "ready_for_strict_blind_preflight" if ready else "awaiting_operator_input"
    next_action = (
        "promote this replacement through strict-blind competitive proof gates"
        if ready
        else "fill replacement_candidate_intake.csv with strict-blind evidence, then rerun intake preflight"
    )
    row = {
        "queue_rank": queue_rank,
        "required_benchmark_id": benchmark_id,
        "required_target_id": _text(queue_row.get("required_target_id")),
        "scope": _text(queue_row.get("scope")),
        "metric_profile": _text(queue_row.get("metric_profile")),
        "template_status": template_status,
        "preflight_status": preflight_status,
        "filled_field_count": filled_field_count,
        "missing_field_count": len(missing_fields),
        "required_field_count": len(REQUIRED_FIELDS),
        "replacement_target_id": _text(candidate.get("replacement_target_id")),
        "replacement_benchmark_id": _text(candidate.get("replacement_benchmark_id")),
        "prediction_pdb": _text(candidate.get("prediction_pdb")),
        "native_pdb": _text(candidate.get("native_pdb")),
        "no_leak_evidence_ref": _text(candidate.get("no_leak_evidence_ref")),
        "ablation_manifest_ref": _text(candidate.get("ablation_manifest_ref")),
        "calibration_values_ref": _text(candidate.get("calibration_values_ref")),
        "intake_csv": _artifact(intake_csv),
        "preflight_csv": _artifact(preflight_csv),
        "preflight_md": _artifact(preflight_md),
        "blockers": ",".join(blockers),
        "next_action": next_action,
    }
    _write_csv(preflight_csv, [row], PREFLIGHT_COLUMNS)
    _write_row_md(preflight_md, row)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue_payload = _read_json(args.queue_json)
    queue_summary = _summary(queue_payload)
    queue_rows = _rows(queue_payload)
    rows = [_build_preflight_row(row, args.intake_dir) for row in queue_rows]
    input_blockers: list[str] = []
    if not _resolve(args.queue_json).exists():
        input_blockers.append("strict_blind_replacement_queue_json_missing")
    ready_count = sum(1 for row in rows if row.get("preflight_status") == "ready_for_strict_blind_preflight")
    blocked_or_awaiting = len(rows) - ready_count
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_queue_rows"
    elif ready_count == len(rows):
        status = "strict_blind_replacement_intake_ready"
    else:
        status = "awaiting_strict_blind_replacement_intake"
    first_open = next((row for row in rows if row.get("preflight_status") != "ready_for_strict_blind_preflight"), {})
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_intake",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_intake_status": status,
        "queue_json": _artifact(args.queue_json),
        "queue_status": _text(queue_summary.get("strict_blind_replacement_queue_status")),
        "intake_dir": _artifact(args.intake_dir),
        "intake_slot_count": len(rows),
        "required_field_count": len(rows) * len(REQUIRED_FIELDS),
        "filled_field_count": sum(_int(row.get("filled_field_count")) for row in rows),
        "missing_field_count": sum(_int(row.get("missing_field_count")) for row in rows),
        "ready_for_preflight_count": ready_count,
        "blocked_or_awaiting_count": blocked_or_awaiting,
        "created_template_count": sum(1 for row in rows if row.get("template_status") == "created"),
        "preserved_template_count": sum(1 for row in rows if row.get("template_status") == "preserved"),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind replacement queue rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Intake",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_intake_status']}`",
        f"- queue status: `{summary['queue_status'] or '-'}`",
        f"- intake slots: `{summary['intake_slot_count']}`",
        f"- fields filled/missing/required: `{summary['filled_field_count']}/{summary['missing_field_count']}/{summary['required_field_count']}`",
        f"- ready/awaiting: `{summary['ready_for_preflight_count']}/{summary['blocked_or_awaiting_count']}`",
        f"- templates created/preserved: `{summary['created_template_count']}/{summary['preserved_template_count']}`",
        f"- first open: `{summary['first_open_benchmark_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Intake Rows",
        "",
        "| rank | benchmark | scope | status | filled | missing | intake | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['required_benchmark_id']}` | `{row['scope']}` | "
            f"`{row['preflight_status']}` | {row['filled_field_count']} | {row['missing_field_count']} | "
            f"`{row['intake_csv']}` | `{row['blockers']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_queue_rows` | 0 | 0 | - | provide queue input |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], PREFLIGHT_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind historical replacement intake preflight.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--intake-dir", default=DEFAULT_INTAKE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
