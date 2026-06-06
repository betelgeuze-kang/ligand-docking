#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AUTHORITATIVE_CHRONOLOGY_JSON = (
    "casp17/casp17_historical_seed_authoritative_chronology_audit_current.json"
)
DEFAULT_LANE_DIR = "casp17/historical_seed_lane_decision_packet"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_lane_decision_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_lane_decision_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_LANE_DECISION_PACKET.md"

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "source_chronology_status",
    "lane_decision_status",
    "strict_blind_eligible",
    "retrospective_calibration_review_allowed",
    "competitive_proof_allowed",
    "identity_intake_allowed",
    "sidechain_native_benchmark_allowed",
    "operator_decision_required",
    "decision_folder",
    "next_action",
    "blockers",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed lane decision packet only. It prevents post-native or authority-incomplete "
    "seed rows from being promoted into strict blind competitive proof. Retrospective rows may remain useful "
    "for calibration or engineering review only after separate no-template/no-leak evidence. The packet does "
    "not clear provenance, mutate manifest/operator CSVs, compute official CASP metrics, or submit to CASP."
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


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _decision_for_chronology(row: dict[str, Any]) -> tuple[str, bool, bool, bool, bool, bool, str, list[str]]:
    status = _text(row.get("chronology_authority_status"))
    blockers = [_text(blocker) for blocker in _text(row.get("blockers")).split(",") if _text(blocker)]
    if status == "chronology_candidate_before_native_review":
        return (
            "strict_blind_candidate_review",
            True,
            False,
            False,
            False,
            False,
            "complete no-leak provenance, negative controls, ablation evidence, and operator clearance before promotion",
            blockers or ["operator_no_leak_clearance_required"],
        )
    if status == "post_native_prediction_chronology_blocked":
        return (
            "retrospective_no_template_review_only",
            False,
            True,
            False,
            False,
            False,
            (
                "keep this row outside competitive proof unless operator supplies a pre-native blind prediction "
                "artifact; otherwise use only for retrospective no-template calibration review"
            ),
            blockers or ["prediction_not_before_authoritative_native_date"],
        )
    if status == "operator_authoritative_chronology_evidence_required":
        return (
            "strict_blind_replacement_or_authority_required",
            False,
            False,
            False,
            False,
            False,
            "attach authoritative native/source chronology or replace with a strict blind eligible seed row",
            blockers or ["authoritative_chronology_evidence_required"],
        )
    return (
        "lane_decision_blocked",
        False,
        False,
        False,
        False,
        False,
        "repair authoritative chronology audit before assigning a benchmark lane",
        blockers or ["unrecognized_chronology_status"],
    )


def _write_row_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} Lane Decision",
        "",
        f"- status: `{row['lane_decision_status']}`",
        f"- benchmark: `{row['benchmark_id']}`",
        f"- scope: `{row['scope']}`",
        f"- source chronology: `{row['source_chronology_status']}`",
        f"- strict blind eligible: `{row['strict_blind_eligible']}`",
        f"- retrospective calibration review allowed: `{row['retrospective_calibration_review_allowed']}`",
        f"- competitive proof allowed: `{row['competitive_proof_allowed']}`",
        f"- identity intake allowed: `{row['identity_intake_allowed']}`",
        f"- sidechain-native benchmark allowed: `{row['sidechain_native_benchmark_allowed']}`",
        f"- operator decision required: `{row['operator_decision_required']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next action: {row['next_action'] or '-'}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_row(row_rank: int, source: dict[str, Any], lane_dir: str | Path) -> dict[str, Any]:
    target_id = _text(source.get("target_id")).upper()
    folder = _resolve(lane_dir) / f"{row_rank:02d}_{_safe_name(target_id)}"
    (
        lane_status,
        strict_blind,
        retrospective,
        competitive,
        identity,
        sidechain,
        next_action,
        blockers,
    ) = _decision_for_chronology(source)
    out = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(source.get("benchmark_id")),
        "scope": _text(source.get("scope")),
        "source_chronology_status": _text(source.get("chronology_authority_status")),
        "lane_decision_status": lane_status,
        "strict_blind_eligible": strict_blind,
        "retrospective_calibration_review_allowed": retrospective,
        "competitive_proof_allowed": competitive,
        "identity_intake_allowed": identity,
        "sidechain_native_benchmark_allowed": sidechain,
        "operator_decision_required": True,
        "decision_folder": _artifact(folder),
        "next_action": next_action,
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    _write_row_md(folder / "LANE_DECISION.md", out)
    _write_csv(folder / "lane_decision.csv", [out], ROW_COLUMNS)
    return out


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    chronology_payload = _read_json(args.authoritative_chronology_json)
    rows = [
        _build_row(index, source, args.lane_dir)
        for index, source in enumerate(_rows(chronology_payload), start=1)
    ]
    input_blockers: list[str] = []
    if not _resolve(args.authoritative_chronology_json).exists():
        input_blockers.append("authoritative_chronology_json_missing")
    strict_count = sum(1 for row in rows if _bool(row.get("strict_blind_eligible")))
    retrospective_count = sum(1 for row in rows if _bool(row.get("retrospective_calibration_review_allowed")))
    authority_required_count = sum(
        1 for row in rows if row["lane_decision_status"] == "strict_blind_replacement_or_authority_required"
    )
    competitive_count = sum(1 for row in rows if _bool(row.get("competitive_proof_allowed")))
    replacement_required_count = sum(1 for row in rows if not _bool(row.get("competitive_proof_allowed")))
    first_blocked = next((row for row in rows if not _bool(row.get("competitive_proof_allowed"))), rows[0] if rows else {})
    if input_blockers:
        status = "blocked_missing_input"
    elif competitive_count == len(rows) and rows:
        status = "strict_blind_competitive_proof_candidates_ready"
    elif strict_count:
        status = "partial_strict_blind_candidates_with_replacements_required"
    elif rows:
        status = "strict_blind_replacement_required"
    else:
        status = "blocked_missing_rows"
    summary = {
        "packet_type": "casp17_historical_seed_lane_decision_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "lane_decision_status": status,
        "authoritative_chronology_json": _artifact(args.authoritative_chronology_json),
        "lane_dir": _artifact(args.lane_dir),
        "seed_row_count": len(rows),
        "strict_blind_eligible_count": strict_count,
        "retrospective_calibration_review_count": retrospective_count,
        "authority_or_replacement_required_count": authority_required_count,
        "competitive_proof_allowed_count": competitive_count,
        "identity_intake_allowed_count": sum(1 for row in rows if _bool(row.get("identity_intake_allowed"))),
        "sidechain_native_benchmark_allowed_count": sum(
            1 for row in rows if _bool(row.get("sidechain_native_benchmark_allowed"))
        ),
        "strict_blind_replacement_required_count": replacement_required_count,
        "operator_decision_required_count": sum(1 for row in rows if _bool(row.get("operator_decision_required"))),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_next_action": _text(first_blocked.get("next_action")) or "provide authoritative chronology rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Lane Decision Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['lane_decision_status']}`",
        f"- seed rows: `{summary['seed_row_count']}`",
        f"- strict-blind / retrospective / authority-required: `{summary['strict_blind_eligible_count']}/{summary['retrospective_calibration_review_count']}/{summary['authority_or_replacement_required_count']}`",
        f"- competitive-proof / identity-intake / sidechain-benchmark allowed: `{summary['competitive_proof_allowed_count']}/{summary['identity_intake_allowed_count']}/{summary['sidechain_native_benchmark_allowed_count']}`",
        f"- strict-blind replacement required: `{summary['strict_blind_replacement_required_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | lane | strict blind | retrospective | competitive proof | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['lane_decision_status']}` | "
            f"`{row['strict_blind_eligible']}` | `{row['retrospective_calibration_review_allowed']}` | "
            f"`{row['competitive_proof_allowed']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_rows` | - | - | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed lane decision packet.")
    parser.add_argument("--authoritative-chronology-json", default=DEFAULT_AUTHORITATIVE_CHRONOLOGY_JSON)
    parser.add_argument("--lane-dir", default=DEFAULT_LANE_DIR)
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
