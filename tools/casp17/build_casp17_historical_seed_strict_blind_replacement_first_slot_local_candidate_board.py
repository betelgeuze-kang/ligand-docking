#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FIRST_SLOT_KIT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_kit_current.json"
)
DEFAULT_NATIVE_CANDIDATES_JSON = "casp17/casp17_historical_seed_native_replacement_candidates_current.json"
DEFAULT_TOP5_JSON = "casp17/casp17_historical_seed_top5_candidate_pools_current.json"
DEFAULT_NO_LEAK_JSON = "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.json"
DEFAULT_CHRONOLOGY_JSON = "casp17/casp17_historical_seed_authoritative_chronology_audit_current.json"
DEFAULT_LANE_DECISION_JSON = "casp17/casp17_historical_seed_lane_decision_packet_current.json"
DEFAULT_ABLATION_JSON = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
DEFAULT_CALIBRATION_JSON = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
DEFAULT_BOARD_DIR = "casp17/historical_seed_strict_blind_replacement_first_slot_local_candidate_board"
DEFAULT_OUT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.csv"
)
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_LOCAL_CANDIDATE_BOARD.md"

ROW_COLUMNS = [
    "candidate_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_status",
    "strict_blind_eligible",
    "competitive_proof_allowed",
    "prediction_pdb",
    "prediction_exists",
    "native_pdb",
    "native_exists",
    "native_authority_ref",
    "native_authority_status",
    "native_release_date",
    "prediction_created_at",
    "prediction_before_native",
    "no_leak_dossier",
    "no_leak_ready",
    "no_leak_open_count",
    "ablation_manifest_ref",
    "ablation_ready",
    "calibration_values_ref",
    "calibration_ready",
    "operator_required",
    "candidate_folder",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 first-slot strict-blind replacement local candidate board only. It aggregates existing local "
    "historical seed prediction/native/calibration/ablation/provenance artifacts into fail-closed candidates for "
    "the current first replacement slot. It does not promote candidates, create evidence, approve no-leak "
    "provenance, rewrite intake CSVs, compute CASP metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "ready"}


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in rows if _text(row.get("target_id"))}


def _candidate_targets(native_rows: list[dict[str, Any]], top5_rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for rows in [top5_rows, native_rows]:
        for row in rows:
            target_id = _text(row.get("target_id"))
            if target_id and target_id not in ordered:
                ordered.append(target_id)
    return ordered


def _exists(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


def _candidate_status(blockers: list[str], strict_blind: bool) -> str:
    if not blockers and strict_blind:
        return "ready_for_first_slot_operator_clearance"
    if "prediction_not_before_native" in blockers:
        return "blocked_chronology_not_strict_blind"
    if "no_leak_not_ready" in blockers:
        return "blocked_no_leak_operator_evidence"
    if "ablation_not_ready" in blockers:
        return "blocked_ablation_evidence"
    return "blocked_first_slot_candidate_review"


def _next_action(row: dict[str, Any]) -> str:
    blockers = _text(row.get("blockers"))
    if "prediction_not_before_native" in blockers:
        return "find or attach a prediction artifact created before authoritative native release"
    if "prediction_missing" in blockers:
        return "attach a local prediction PDB for this historical seed"
    if "native_missing" in blockers or "native_authority_missing" in blockers:
        return "attach authoritative native PDB and source reference"
    if "no_leak_not_ready" in blockers:
        return "complete no-leak evidence, chronology, negative controls, and operator clearance"
    if "ablation_not_ready" in blockers:
        return "attach same-run ablation layer evidence; top5 decoys remain review-only"
    if "calibration_not_ready" in blockers:
        return "operator-fill calibration values after no-leak provenance clearance"
    return "operator may review candidate for first strict-blind replacement slot"


def _candidate_rows(payloads: dict[str, dict[str, Any]], board_dir: str | Path) -> list[dict[str, Any]]:
    native_by_target = _by_target(_rows(payloads["native"]))
    top5_by_target = _by_target(_rows(payloads["top5"]))
    no_leak_by_target = _by_target(_rows(payloads["no_leak"]))
    chronology_by_target = _by_target(_rows(payloads["chronology"]))
    lane_by_target = _by_target(_rows(payloads["lane"]))
    ablation_by_target = _by_target(_rows(payloads["ablation"]))
    calibration_by_target = _by_target(_rows(payloads["calibration"]))
    rows: list[dict[str, Any]] = []
    for rank, target_id in enumerate(_candidate_targets(_rows(payloads["native"]), _rows(payloads["top5"])), start=1):
        native = native_by_target.get(target_id, {})
        top5 = top5_by_target.get(target_id, {})
        no_leak = no_leak_by_target.get(target_id, {})
        chronology = chronology_by_target.get(target_id, {})
        lane = lane_by_target.get(target_id, {})
        ablation = ablation_by_target.get(target_id, {})
        calibration = calibration_by_target.get(target_id, {})
        benchmark_id = _text(top5.get("benchmark_id")) or _text(native.get("benchmark_id"))
        prediction_pdb = _text(top5.get("selected_source_pdb")) or _text(no_leak.get("prediction_pdb"))
        native_pdb = _text(native.get("candidate_pdb")) or _text(no_leak.get("native_pdb"))
        native_authority_ref = _text(native.get("native_authority_ref")) or _text(chronology.get("native_authority_ref"))
        no_leak_ready = _text(no_leak.get("dossier_status")) == "ready_for_no_leak_clearance"
        ablation_ready = _text(ablation.get("candidate_manifest_status")) == "ready_for_operator_reference"
        calibration_ready = _text(calibration.get("ledger_status")) == "ready_for_calibration_fill"
        strict_blind = _bool(lane.get("strict_blind_eligible"))
        competitive = _bool(lane.get("competitive_proof_allowed"))
        prediction_before_native = _bool(chronology.get("prediction_before_or_on_native_authority"))
        blockers: list[str] = []
        if not _exists(prediction_pdb):
            blockers.append("prediction_missing")
        if not _exists(native_pdb):
            blockers.append("native_missing")
        if not native_authority_ref:
            blockers.append("native_authority_missing")
        if not prediction_before_native:
            blockers.append("prediction_not_before_native")
        if not no_leak_ready:
            blockers.append("no_leak_not_ready")
        if not ablation_ready:
            blockers.append("ablation_not_ready")
        if not calibration_ready:
            blockers.append("calibration_not_ready")
        if not strict_blind:
            blockers.append("strict_blind_not_eligible")
        candidate_folder = _candidate_folder(board_dir, rank, target_id)
        row = {
            "candidate_rank": rank,
            "target_id": target_id,
            "benchmark_id": benchmark_id,
            "scope": _text(top5.get("scope")) or _text(native.get("scope")) or _text(lane.get("scope")),
            "candidate_status": _candidate_status(blockers, strict_blind),
            "strict_blind_eligible": str(strict_blind),
            "competitive_proof_allowed": str(competitive),
            "prediction_pdb": _artifact(prediction_pdb),
            "prediction_exists": str(_exists(prediction_pdb)),
            "native_pdb": _artifact(native_pdb),
            "native_exists": str(_exists(native_pdb)),
            "native_authority_ref": native_authority_ref,
            "native_authority_status": _text(chronology.get("native_authority_status")),
            "native_release_date": _text(chronology.get("native_authority_date")),
            "prediction_created_at": _text(chronology.get("prediction_created_candidate")),
            "prediction_before_native": str(prediction_before_native),
            "no_leak_dossier": _text(no_leak.get("dossier_md")),
            "no_leak_ready": str(no_leak_ready),
            "no_leak_open_count": _int(no_leak.get("operator_required_open_count")),
            "ablation_manifest_ref": _text(ablation.get("candidate_manifest_csv")),
            "ablation_ready": str(ablation_ready),
            "calibration_values_ref": _text(calibration.get("candidate_ledger_csv")),
            "calibration_ready": str(calibration_ready),
            "operator_required": str(_bool(lane.get("operator_decision_required")) or bool(blockers)),
            "candidate_folder": _artifact(candidate_folder),
            "blockers": ",".join(blockers),
            "next_action": "",
        }
        row["next_action"] = _next_action(row)
        rows.append(row)
    return rows


def _candidate_folder(board_dir: str | Path, rank: int, target_id: str) -> Path:
    safe = target_id.lower().replace("/", "_").replace(" ", "_")
    return _resolve(board_dir) / f"{rank:02d}_{safe}"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payloads = {
        "first_slot": _read_json(args.first_slot_kit_json),
        "native": _read_json(args.native_candidates_json),
        "top5": _read_json(args.top5_json),
        "no_leak": _read_json(args.no_leak_json),
        "chronology": _read_json(args.chronology_json),
        "lane": _read_json(args.lane_decision_json),
        "ablation": _read_json(args.ablation_json),
        "calibration": _read_json(args.calibration_json),
    }
    input_blockers = []
    for arg_name in [
        "first_slot_kit_json",
        "native_candidates_json",
        "top5_json",
        "no_leak_json",
        "chronology_json",
        "lane_decision_json",
        "ablation_json",
        "calibration_json",
    ]:
        if not _resolve(getattr(args, arg_name)).exists():
            input_blockers.append(f"{arg_name}_missing")
    rows = _candidate_rows(payloads, args.board_dir)
    summary = _build_summary(args, rows, input_blockers, payloads)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    first_review = next((row for row in rows if row["candidate_status"] != "ready_for_first_slot_operator_clearance"), {})
    ready_count = sum(1 for row in rows if row["candidate_status"] == "ready_for_first_slot_operator_clearance")
    strict_count = sum(1 for row in rows if row["strict_blind_eligible"] == "True")
    material_count = sum(
        1
        for row in rows
        if row["prediction_exists"] == "True" and row["native_exists"] == "True" and bool(row["native_authority_ref"])
    )
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_local_candidate_board_status": _overall_status(rows, input_blockers),
        "first_slot_status": _text(
            _summary(payloads["first_slot"]).get("strict_blind_replacement_first_slot_kit_status")
        ),
        "required_benchmark_id": _text(_summary(payloads["first_slot"]).get("required_benchmark_id")),
        "required_target_id": _text(_summary(payloads["first_slot"]).get("required_target_id")),
        "scope": _text(_summary(payloads["first_slot"]).get("scope")),
        "candidate_count": len(rows),
        "ready_for_first_slot_count": ready_count,
        "strict_blind_eligible_count": strict_count,
        "material_present_count": material_count,
        "blocked_chronology_count": sum(1 for row in rows if "prediction_not_before_native" in row["blockers"]),
        "blocked_no_leak_count": sum(1 for row in rows if "no_leak_not_ready" in row["blockers"]),
        "blocked_ablation_count": sum(1 for row in rows if "ablation_not_ready" in row["blockers"]),
        "blocked_calibration_count": sum(1 for row in rows if "calibration_not_ready" in row["blockers"]),
        "prediction_present_count": sum(1 for row in rows if row["prediction_exists"] == "True"),
        "native_present_count": sum(1 for row in rows if row["native_exists"] == "True"),
        "native_authority_present_count": sum(1 for row in rows if bool(row["native_authority_ref"])),
        "first_review_target_id": _text(first_review.get("target_id")),
        "first_review_benchmark_id": _text(first_review.get("benchmark_id")),
        "first_review_status": _text(first_review.get("candidate_status")),
        "first_review_next_action": _text(first_review.get("next_action")) or "provide local candidate inputs",
        "board_dir": _artifact(args.board_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_no_local_candidates"
    if any(row["candidate_status"] == "ready_for_first_slot_operator_clearance" for row in rows):
        return "first_slot_local_candidate_ready_for_operator_clearance"
    if any(row["prediction_exists"] == "True" and row["native_exists"] == "True" for row in rows):
        return "first_slot_local_candidates_review_only"
    return "blocked_first_slot_local_candidate_sources"


def _write_candidate_md(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} First Slot Local Candidate",
        "",
        f"- status: `{row['candidate_status']}`",
        f"- benchmark: `{row['benchmark_id']}`",
        f"- scope: `{row['scope']}`",
        f"- strict blind eligible: `{row['strict_blind_eligible']}`",
        f"- competitive proof allowed: `{row['competitive_proof_allowed']}`",
        f"- prediction/native present: `{row['prediction_exists']}/{row['native_exists']}`",
        f"- prediction created/native release/before-native: `{row['prediction_created_at'] or '-'}` `{row['native_release_date'] or '-'}` `{row['prediction_before_native']}`",
        f"- no-leak ready/open: `{row['no_leak_ready']}/{row['no_leak_open_count']}`",
        f"- ablation/calibration ready: `{row['ablation_ready']}/{row['calibration_ready']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        f"- next action: {row['next_action']}",
        "",
        "## Evidence Pointers",
        "",
        f"- prediction_pdb: `{row['prediction_pdb'] or '-'}`",
        f"- native_pdb: `{row['native_pdb'] or '-'}`",
        f"- native_authority_ref: `{row['native_authority_ref'] or '-'}`",
        f"- no_leak_dossier: `{row['no_leak_dossier'] or '-'}`",
        f"- ablation_manifest_ref: `{row['ablation_manifest_ref'] or '-'}`",
        f"- calibration_values_ref: `{row['calibration_values_ref'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["candidate_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CANDIDATE.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "candidate_summary.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement First Slot Local Candidate Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_local_candidate_board_status']}`",
        f"- first slot: `{summary['required_benchmark_id'] or '-'}` `{summary['required_target_id'] or '-'}` `{summary['scope'] or '-'}` kit `{summary['first_slot_status'] or '-'}`",
        f"- candidates ready/strict/material/total: `{summary['ready_for_first_slot_count']}/{summary['strict_blind_eligible_count']}/{summary['material_present_count']}/{summary['candidate_count']}`",
        f"- present prediction/native/authority: `{summary['prediction_present_count']}/{summary['native_present_count']}/{summary['native_authority_present_count']}`",
        f"- blocked chronology/no-leak/ablation/calibration: `{summary['blocked_chronology_count']}/{summary['blocked_no_leak_count']}/{summary['blocked_ablation_count']}/{summary['blocked_calibration_count']}`",
        f"- first review: `{summary['first_review_target_id'] or '-'}` `{summary['first_review_status'] or '-'}`",
        f"- next action: {summary['first_review_next_action'] or '-'}",
        "",
        "## Candidates",
        "",
        "| rank | target | benchmark | status | strict | material | chronology | no-leak | ablation | calibration | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        material = f"{row['prediction_exists']}/{row['native_exists']}/{bool(row['native_authority_ref'])}"
        lines.append(
            f"| {row['candidate_rank']} | `{row['target_id']}` | `{row['benchmark_id']}` | "
            f"`{row['candidate_status']}` | `{row['strict_blind_eligible']}` | `{material}` | "
            f"`{row['prediction_before_native']}` | `{row['no_leak_ready']}` | `{row['ablation_ready']}` | "
            f"`{row['calibration_ready']}` | `{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_no_local_candidates` | - | - | - | - | - | - | - | regenerate source inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_candidate_md(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot local candidate board for strict-blind replacement.")
    parser.add_argument("--first-slot-kit-json", default=DEFAULT_FIRST_SLOT_KIT_JSON)
    parser.add_argument("--native-candidates-json", default=DEFAULT_NATIVE_CANDIDATES_JSON)
    parser.add_argument("--top5-json", default=DEFAULT_TOP5_JSON)
    parser.add_argument("--no-leak-json", default=DEFAULT_NO_LEAK_JSON)
    parser.add_argument("--chronology-json", default=DEFAULT_CHRONOLOGY_JSON)
    parser.add_argument("--lane-decision-json", default=DEFAULT_LANE_DECISION_JSON)
    parser.add_argument("--ablation-json", default=DEFAULT_ABLATION_JSON)
    parser.add_argument("--calibration-json", default=DEFAULT_CALIBRATION_JSON)
    parser.add_argument("--board-dir", default=DEFAULT_BOARD_DIR)
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
