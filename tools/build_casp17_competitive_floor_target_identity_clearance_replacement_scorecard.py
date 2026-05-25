#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REPAIR_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json"
)
DEFAULT_OUT_DIR = "runs/casp17_internal_scorecards_current"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD.md"

SCORECARD_COLUMNS = [
    "candidate_target_id",
    "candidate_target_name",
    "replacement_scorecard_status",
    "source_repair_status",
    "replace_target_ids",
    "fasta_path",
    "provenance_json",
    "prediction_pdb",
    "predictor_json",
    "backend_contract_json",
    "geometry_json",
    "confidence_json",
    "output_scorecard_json",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 replacement source scorecard only. It checks that a replacement candidate has reviewed sequence "
    "provenance, internal-physics prediction evidence, backend contract pass, raw geometry pass, and raw confidence "
    "pass before replacement-clearance review. It does not assert native identity, no-leak provenance, official CASP "
    "submission readiness, or structure accuracy."
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
        return int(float(str(value).strip()))
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORECARD_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _first_existing(paths: list[str | Path]) -> str:
    for path_like in paths:
        text = _text(path_like)
        if not text:
            continue
        path = _resolve(text)
        if path.exists():
            return _artifact(path)
    return ""


def _payload_status(path_like: str, summary_key: str, pass_value: str) -> tuple[bool, str]:
    if not _text(path_like):
        return False, "missing_path"
    payload = _read_json(path_like)
    if not payload:
        return False, "missing_or_invalid_json"
    status = _text(_summary(payload).get(summary_key))
    return status == pass_value, status or "missing_status"


def _candidate_paths(candidate_id: str, row: dict[str, Any]) -> dict[str, str]:
    return {
        "fasta_path": _first_existing([_text(row.get("fasta_path")), f"casp17/replacement_source_fasta/{candidate_id}.fasta"]),
        "provenance_json": _first_existing([f"casp17/replacement_source_fasta/{candidate_id}.provenance.json"]),
        "prediction_pdb": _first_existing(
            [
                _text(row.get("prediction_pdb")),
                _text(row.get("ts_prediction_pdb")),
                f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_model_1.pdb",
            ]
        ),
        "predictor_json": _first_existing([f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_predictor.json"]),
        "backend_contract_json": _first_existing(
            [f"runs/casp17_internal_physics_raw_validations_current/{candidate_id}_backend_contract.json"]
        ),
        "geometry_json": _first_existing(
            [f"runs/casp17_internal_physics_raw_validations_current/{candidate_id}_raw_geometry_sanity.json"]
        ),
        "confidence_json": _first_existing(
            [
                _text(row.get("raw_validation_json")),
                f"runs/casp17_internal_physics_raw_validations_current/{candidate_id}_raw_confidence_calibration.json",
            ]
        ),
    }


def _scorecard_payload(candidate_id: str, row: dict[str, Any], paths: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    source_status = _text(row.get("source_repair_status"))
    if source_status in {"blocked_cancelled_target", "blocked_current_target_collision"}:
        blockers.append(source_status)
    if not paths["fasta_path"]:
        blockers.append("fasta_missing")
    if not paths["provenance_json"]:
        blockers.append("sequence_provenance_missing")
    if not paths["prediction_pdb"]:
        blockers.append("prediction_missing")
    for field, key, pass_value in [
        ("predictor_json", "predictor_status", "pass"),
        ("backend_contract_json", "contract_status", "pass"),
        ("geometry_json", "geometry_sanity_status", "pass"),
        ("confidence_json", "confidence_calibration_status", "pass"),
    ]:
        ok, status = _payload_status(paths[field], key, pass_value)
        if not ok:
            blockers.append(f"{field}:{status}")
    predictor = _summary(_read_json(paths["predictor_json"]))
    contract = _summary(_read_json(paths["backend_contract_json"]))
    confidence = _summary(_read_json(paths["confidence_json"]))
    residues = _int(contract.get("residue_count") or predictor.get("residue_count") or confidence.get("sequence_residue_count"))
    if residues <= 0:
        blockers.append("residue_count_missing")
    status = "replacement_source_scorecard_pass" if not blockers else "replacement_source_scorecard_blocked"
    payload = {
        "summary": {
            "packet_type": "casp17_replacement_source_scorecard",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "candidate_target_id": candidate_id,
            "candidate_target_name": _text(row.get("candidate_target_name")),
            "replace_target_ids": _text(row.get("replace_target_ids")),
            "replacement_scorecard_status": status,
            "internal_scorecard_status": "pass" if not blockers else "fail",
            "source_repair_status": source_status,
            "fasta_path": paths["fasta_path"],
            "provenance_json": paths["provenance_json"],
            "prediction_pdb": paths["prediction_pdb"],
            "predictor_json": paths["predictor_json"],
            "backend_contract_json": paths["backend_contract_json"],
            "geometry_json": paths["geometry_json"],
            "confidence_json": paths["confidence_json"],
            "chain_count": _int(contract.get("pdb_ca_chain_count") or predictor.get("chain_count")),
            "residue_count": residues,
            "blocker_count": len(blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "blockers": [{"code": blocker, "severity": "hard", "reason": blocker} for blocker in blockers],
    }
    return payload, blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_payload = _read_json(args.source_repair_json)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for source_row in _rows(source_payload):
        candidate_id = _text(source_row.get("candidate_target_id")).upper()
        if not candidate_id:
            continue
        paths = _candidate_paths(candidate_id, source_row)
        target_payload, blockers = _scorecard_payload(candidate_id, source_row, paths)
        output_scorecard_json = ""
        if not blockers:
            output_path = out_dir / f"{candidate_id}_internal_scorecard.json"
            _write_json(output_path, target_payload)
            output_scorecard_json = _artifact(output_path)
        rows.append(
            {
                "candidate_target_id": candidate_id,
                "candidate_target_name": _text(source_row.get("candidate_target_name")),
                "replacement_scorecard_status": target_payload["summary"]["replacement_scorecard_status"],
                "source_repair_status": _text(source_row.get("source_repair_status")),
                "replace_target_ids": _text(source_row.get("replace_target_ids")),
                **paths,
                "output_scorecard_json": output_scorecard_json,
                "blockers": ",".join(dict.fromkeys(blockers)),
                "next_action": (
                    "move this replacement candidate into operator clearance review"
                    if not blockers
                    else "repair replacement source evidence before clearance review"
                ),
            }
        )
    pass_count = sum(1 for row in rows if row["replacement_scorecard_status"] == "replacement_source_scorecard_pass")
    blocked_count = len(rows) - pass_count
    first_open = next((row for row in rows if row["replacement_scorecard_status"] != "replacement_source_scorecard_pass"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_scorecard",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_repair_json": _artifact(args.source_repair_json),
        "out_dir": _artifact(args.out_dir),
        "replacement_scorecard_status": (
            "replacement_scorecard_pass" if rows and blocked_count == 0 else "replacement_scorecard_blocked" if rows else "no_replacement_candidates"
        ),
        "candidate_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "scorecard_json_count": sum(1 for row in rows if row["output_scorecard_json"]),
        "first_open_candidate_target_id": _text(first_open.get("candidate_target_id")),
        "first_open_status": _text(first_open.get("replacement_scorecard_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Identity Clearance Replacement Scorecard",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- replacement_scorecard_status: `{summary['replacement_scorecard_status']}`",
        f"- candidates: `{summary['candidate_count']}`",
        f"- pass/blocked/scorecard-json: `{summary['pass_count']}/{summary['blocked_count']}/{summary['scorecard_json_count']}`",
        f"- first open: `{summary['first_open_candidate_target_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- first next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| candidate | status | fasta | prediction | contract | geometry | confidence | scorecard | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_target_id']}` | `{row['replacement_scorecard_status']}` | "
            f"`{row['fasta_path'] or '-'}` | `{row['prediction_pdb'] or '-'}` | "
            f"`{row['backend_contract_json'] or '-'}` | `{row['geometry_json'] or '-'}` | "
            f"`{row['confidence_json'] or '-'}` | `{row['output_scorecard_json'] or '-'}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_replacement_candidates` | - | - | - | - | - | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 replacement source scorecards.")
    parser.add_argument("--source-repair-json", default=DEFAULT_SOURCE_REPAIR_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
