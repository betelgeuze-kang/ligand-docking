#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_DOSSIER_DIR = "casp17/historical_seed_no_leak_provenance_dossiers"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_NO_LEAK_PROVENANCE_DOSSIERS.md"

TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}
CLEAR_VALUES = {"no_leak", "cleared", "ready_for_row_fill", "internal_no_leak", "true", "yes", "approved"}
PLACEHOLDER_TOKENS = ("REQUIRED", "YYYY-MM-DD")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")

OPERATOR_REQUIRED_FIELDS = [
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
]

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "dossier_status",
    "dossier_md",
    "prediction_pdb_exists",
    "native_pdb_exists",
    "prediction_native_distinct",
    "prediction_atom_count",
    "native_atom_count",
    "prediction_sha256_16",
    "native_sha256_16",
    "current_casp17_target_value",
    "current_target_safety_status",
    "prediction_method",
    "prediction_path_date",
    "prediction_file_mtime_date",
    "native_file_mtime_date",
    "file_mtime_prediction_before_native",
    "operator_required_open_count",
    "operator_required_open_fields",
    "next_action",
    "blockers",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed no-leak provenance dossiers only. They assemble existing local path, "
    "fingerprint, current-target, method, and chronology-candidate facts for operator review. They do not "
    "clear leakage provenance, infer native release authority, fill operator CSVs, fetch native structures, "
    "score native accuracy, run predictors, or submit to CASP."
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


def _norm(value: Any) -> str:
    return _text(value).lower()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _placeholder(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    upper = text.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fields:
        blockers.append(f"{_artifact(path)}_header_missing")
    return rows, blockers


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


def _pdb_stats(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    stats: dict[str, Any] = {
        "exists": path.is_file(),
        "atom_count": 0,
        "coordinate_valid": False,
        "sha256_16": "",
    }
    if not path.is_file():
        return stats
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    coordinate_valid = True
    atom_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            atom_count += 1
            try:
                float(line[30:38])
                float(line[38:46])
                float(line[46:54])
            except ValueError:
                coordinate_valid = False
    stats["atom_count"] = atom_count
    stats["coordinate_valid"] = coordinate_valid and atom_count > 0
    stats["sha256_16"] = digest.hexdigest()[:16]
    return stats


def _path_date(value: Any) -> str:
    match = DATE_RE.search(_text(value))
    return match.group(1) if match else ""


def _mtime_date(value: Any) -> str:
    path = _resolve(_text(value))
    if not path.is_file():
        return ""
    return dt.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def _date_ready(value: Any) -> bool:
    text = _text(value)
    if _placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _field_ready(field: str, value: Any) -> bool:
    if field == "no_leak_evidence_ref":
        return not _placeholder(value)
    if field in {"leakage_clearance", "operator_clearance"}:
        return _norm(value) in CLEAR_VALUES
    if field == "operator":
        return not _placeholder(value)
    if field in {"prediction_created_at", "native_release_date"}:
        return _date_ready(value)
    if field == "prediction_generated_before_native_release":
        return _norm(value) in TRUE_VALUES
    if field in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
    }:
        return _norm(value) in FALSE_VALUES
    return not _placeholder(value)


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown_target"


def _write_dossier_md(path_like: str | Path, row: dict[str, Any]) -> None:
    lines = [
        f"# No-Leak Provenance Dossier: {row['target_id']}",
        "",
        f"- status: `{row['dossier_status']}`",
        f"- benchmark_id: `{row['benchmark_id']}`",
        f"- scope: `{row['scope']}`",
        f"- prediction_pdb: `{row['prediction_pdb']}`",
        f"- native_pdb: `{row['native_pdb']}`",
        f"- prediction/native distinct: `{row['prediction_native_distinct']}`",
        f"- prediction/native atoms: `{row['prediction_atom_count']}/{row['native_atom_count']}`",
        f"- prediction/native sha256_16: `{row['prediction_sha256_16'] or '-'}`/`{row['native_sha256_16'] or '-'}`",
        f"- current target safety: `{row['current_target_safety_status']}` value `{row['current_casp17_target_value'] or '-'}`",
        f"- prediction method: `{row['prediction_method'] or '-'}`",
        f"- path date candidate: `{row['prediction_path_date'] or '-'}`",
        f"- mtime candidate pred/native/order: `{row['prediction_file_mtime_date'] or '-'}`/`{row['native_file_mtime_date'] or '-'}`/`{row['file_mtime_prediction_before_native']}`",
        f"- operator open fields: `{row['operator_required_open_count']}` `{row['operator_required_open_fields'] or '-'}`",
        f"- next action: {row['next_action']}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_row(row: dict[str, str], dossier_dir: str | Path, row_rank: int) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).upper()
    benchmark_id = _text(row.get("benchmark_id"))
    prediction_pdb = _text(row.get("prediction_pdb"))
    native_pdb = _text(row.get("native_pdb"))
    prediction = _pdb_stats(prediction_pdb)
    native = _pdb_stats(native_pdb)
    current_value = _text(row.get("current_casp17_target"))
    blockers: list[str] = []
    if not prediction["exists"] or not prediction["coordinate_valid"]:
        blockers.append("prediction_pdb_missing_or_invalid")
    if not native["exists"] or not native["coordinate_valid"]:
        blockers.append("native_pdb_missing_or_invalid")
    if prediction_pdb == native_pdb:
        blockers.append("prediction_native_paths_must_differ")
    if _norm(current_value) != "false" or not target_id.startswith("HIST_"):
        blockers.append("current_target_or_identity_risk_requires_operator_review")
        current_status = "blocked_current_target_risk"
    else:
        current_status = "prefilled_false_hist_prefix"
    open_fields = [field for field in OPERATOR_REQUIRED_FIELDS if not _field_ready(field, row.get(field))]
    if open_fields:
        blockers.append("operator_no_leak_fields_required")
    prediction_date = _date_ready(row.get("prediction_created_at"))
    native_date = _date_ready(row.get("native_release_date"))
    if not prediction_date or not native_date or _norm(row.get("prediction_generated_before_native_release")) not in TRUE_VALUES:
        blockers.append("operator_chronology_evidence_required")
    for field in ("public_template_or_native_used_for_prediction", "other_team_model_used", "post_release_information_used"):
        if _norm(row.get(field)) not in FALSE_VALUES:
            blockers.append("operator_negative_leakage_control_required")
            break
    mtime_prediction = _mtime_date(prediction_pdb)
    mtime_native = _mtime_date(native_pdb)
    mtime_order: bool | str = ""
    if mtime_prediction and mtime_native:
        mtime_order = mtime_prediction < mtime_native
    if mtime_order is False:
        blockers.append("file_mtime_not_clearance_authority")
    if any(item.endswith("_missing_or_invalid") for item in blockers):
        status = "blocked_core_provenance_inputs"
        next_action = "repair missing or invalid prediction/native inputs before no-leak review"
    elif current_status == "blocked_current_target_risk":
        status = "blocked_current_target_risk"
        next_action = "prove historical non-current identity before any no-leak clearance"
    else:
        status = "operator_provenance_review_required"
        next_action = "attach independent no-leak evidence and operator clearance before setting leakage_clearance"
    dossier_md = _resolve(dossier_dir) / f"{row_rank:02d}_{_safe_name(target_id)}_no_leak_provenance.md"
    report = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": _text(row.get("scope")),
        "dossier_status": status,
        "dossier_md": _artifact(dossier_md),
        "prediction_pdb": _artifact(prediction_pdb) if prediction_pdb else "",
        "native_pdb": _artifact(native_pdb) if native_pdb else "",
        "prediction_pdb_exists": bool(prediction["exists"]),
        "native_pdb_exists": bool(native["exists"]),
        "prediction_native_distinct": prediction_pdb != native_pdb,
        "prediction_atom_count": _int(prediction["atom_count"]),
        "native_atom_count": _int(native["atom_count"]),
        "prediction_sha256_16": _text(prediction["sha256_16"]),
        "native_sha256_16": _text(native["sha256_16"]),
        "current_casp17_target_value": current_value,
        "current_target_safety_status": current_status,
        "prediction_method": _text(row.get("prediction_method")),
        "prediction_path_date": _path_date(prediction_pdb),
        "prediction_file_mtime_date": mtime_prediction,
        "native_file_mtime_date": mtime_native,
        "file_mtime_prediction_before_native": mtime_order,
        "operator_required_open_count": len(open_fields),
        "operator_required_open_fields": ",".join(open_fields),
        "next_action": next_action,
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    _write_dossier_md(dossier_md, report)
    return report


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    seed_by_target = {_text(row.get("target_id")).upper(): row for row in seed_rows}
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(operator_rows, start=1):
        target_id = _text(row.get("target_id")).upper()
        merged = dict(seed_by_target.get(target_id, {}))
        merged.update(row)
        rows.append(_build_row(merged, args.dossier_dir, index))
    status_counts: dict[str, int] = {}
    for row in rows:
        status = _text(row.get("dossier_status"))
        status_counts[status] = status_counts.get(status, 0) + 1
    input_blockers = operator_blockers + seed_blockers
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_operator_rows"
    elif status_counts.get("blocked_core_provenance_inputs", 0):
        status = "blocked_core_provenance_inputs"
    elif status_counts.get("blocked_current_target_risk", 0):
        status = "blocked_current_target_risk"
    else:
        status = "operator_provenance_review_required"
    first_open = next((row for row in rows if row["dossier_status"] != "ready_for_no_leak_clearance"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_historical_seed_no_leak_provenance_dossiers",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "no_leak_dossier_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "dossier_dir": _artifact(args.dossier_dir),
        "seed_row_count": len(rows),
        "dossier_count": sum(1 for row in rows if _text(row.get("dossier_md"))),
        "core_input_pass_count": sum(
            1
            for row in rows
            if row["prediction_pdb_exists"] and row["native_pdb_exists"] and row["prediction_native_distinct"]
        ),
        "current_target_prefilled_false_count": sum(
            1 for row in rows if row["current_target_safety_status"] == "prefilled_false_hist_prefix"
        ),
        "operator_review_required_count": len(rows),
        "ready_for_no_leak_clearance_count": 0,
        "operator_required_open_field_count": sum(_int(row.get("operator_required_open_count")) for row in rows),
        "chronology_evidence_gap_count": sum(
            1 for row in rows if "operator_chronology_evidence_required" in _text(row.get("blockers")).split(",")
        ),
        "negative_leakage_control_gap_count": sum(
            1 for row in rows if "operator_negative_leakage_control_required" in _text(row.get("blockers")).split(",")
        ),
        "mtime_order_risk_count": sum(1 for row in rows if row.get("file_mtime_prediction_before_native") is False),
        "blocked_core_provenance_input_count": status_counts.get("blocked_core_provenance_inputs", 0),
        "blocked_current_target_risk_count": status_counts.get("blocked_current_target_risk", 0),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed operator rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed No-Leak Provenance Dossiers",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- no_leak_dossier_status: `{summary['no_leak_dossier_status']}`",
        f"- seed rows/dossiers: `{summary['seed_row_count']}/{summary['dossier_count']}`",
        f"- core pass/current-target=false: `{summary['core_input_pass_count']}/{summary['current_target_prefilled_false_count']}`",
        f"- ready/operator-review/core-blocked/current-risk: `{summary['ready_for_no_leak_clearance_count']}/{summary['operator_review_required_count']}/{summary['blocked_core_provenance_input_count']}/{summary['blocked_current_target_risk_count']}`",
        f"- operator open fields/chronology gaps/negative-control gaps/mtime-risk: `{summary['operator_required_open_field_count']}/{summary['chronology_evidence_gap_count']}/{summary['negative_leakage_control_gap_count']}/{summary['mtime_order_risk_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | dossier | core | current-target | path date | mtime order | open fields | next action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['dossier_status']}` | "
            f"`{row['dossier_md']}` | `{row['prediction_pdb_exists']}`/`{row['native_pdb_exists']}` | "
            f"`{row['current_target_safety_status']}` | `{row['prediction_path_date'] or '-'}` | "
            f"`{row['file_mtime_prediction_before_native']}` | {row['operator_required_open_count']} | "
            f"{row['next_action']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_rows` | - | - | - | - | - | 0 | provide operator CSV | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed no-leak provenance dossiers.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--dossier-dir", default=DEFAULT_DOSSIER_DIR)
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
