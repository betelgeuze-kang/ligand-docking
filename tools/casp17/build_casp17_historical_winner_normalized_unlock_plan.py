#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BANDS_JSON = "casp17/casp17_historical_winner_normalized_bands_current.json"
DEFAULT_METRIC_SURFACE_CONTRACT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_SOURCE_REQUEST_CLOSURE_BOARD_JSON = "casp17/casp17_strict_blind_source_request_closure_board_current.json"
DEFAULT_BATCH_CLOSURE_RUNWAY_JSON = "casp17/casp17_strict_blind_batch_closure_runway_current.json"
DEFAULT_OFFICIAL_ARCHIVE_BASELINE_JSON = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_winner_normalized_unlock_plan_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_winner_normalized_unlock_plan_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_WINNER_NORMALIZED_UNLOCK_PLAN.md"

CLAIM_BOUNDARY = (
    "Local CASP17 historical winner-normalized unlock plan only. It orders the local gates required before "
    "CASP15/16 winner-normalized band comparison can be treated as competitive evidence. It does not fill "
    "operator values, create or copy PDB files, compute official CASP metrics, import official archive "
    "submissions as internal predictions, push remotes, or submit to CASP."
)

ROW_COLUMNS = [
    "action_order",
    "action_id",
    "gate",
    "action_status",
    "ready_count",
    "blocked_count",
    "total_count",
    "source_artifact",
    "blocker",
    "next_action",
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _ready_status(ready: int, total: int, blocker: str = "") -> str:
    if total > 0 and ready >= total and not blocker:
        return "unlock_ready"
    return "unlock_blocked"


def _action(
    order: int,
    action_id: str,
    gate: str,
    ready: int,
    blocked: int,
    total: int,
    source_artifact: str,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "action_order": order,
        "action_id": action_id,
        "gate": gate,
        "action_status": _ready_status(ready, total, blocker),
        "ready_count": ready,
        "blocked_count": blocked,
        "total_count": total,
        "source_artifact": _artifact(source_artifact),
        "blocker": blocker,
        "next_action": next_action,
    }


def _first_blocked(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row["action_status"] != "unlock_ready":
            return row
    return {}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    path_args = [
        ("bands_json", args.bands_json),
        ("metric_surface_contract_json", args.metric_surface_contract_json),
        ("sidechain_native_benchmark_json", args.sidechain_native_benchmark_json),
        ("source_request_closure_board_json", args.source_request_closure_board_json),
        ("batch_closure_runway_json", args.batch_closure_runway_json),
        ("official_archive_baseline_json", args.official_archive_baseline_json),
    ]
    input_blockers = [f"{name}_missing" for name, path in path_args if not _resolve(path).exists()]
    bands = _summary(_read_json(args.bands_json))
    metric = _summary(_read_json(args.metric_surface_contract_json))
    sidechain = _summary(_read_json(args.sidechain_native_benchmark_json))
    source_request = _summary(_read_json(args.source_request_closure_board_json))
    batch = _summary(_read_json(args.batch_closure_runway_json))
    official = _summary(_read_json(args.official_archive_baseline_json))

    strict_ready = _int(metric.get("ready_slot_count"))
    strict_total = _int(metric.get("strict_blind_slot_count"))
    metric_ready = _int(metric.get("ready_metric_row_count"))
    metric_total = _int(metric.get("metric_surface_row_count"))
    sidechain_ready = _int(sidechain.get("pass_count"))
    sidechain_total = _int(sidechain.get("benchmark_count"))
    source_ready = _int(source_request.get("ready_stage_count"))
    source_blocked = _int(source_request.get("blocked_stage_count"))
    source_total = _int(source_request.get("stage_count"))
    batch_ready = _int(batch.get("ready_slot_count"))
    batch_blocked = _int(batch.get("blocked_slot_count"))
    batch_total = _int(batch.get("slot_count"))
    top5_count = _int(bands.get("top5_or_better_count"))
    band_total = _int(bands.get("band_count"))
    blocked_band_count = _int(bands.get("blocked_band_count"))
    official_baseline = _int(official.get("baseline_candidate_count"))
    official_proof = _int(official.get("competitive_proof_eligible_count"))
    source_blocker = ""
    if not (source_total and source_ready >= source_total):
        source_blocker = _text(source_request.get("first_blocker")) or "source_request_closure_not_ready"
    batch_blocker = ""
    if not (batch_total and batch_ready >= batch_total):
        batch_blocker = _text(batch.get("first_blocker")) or "strict_blind_batch_slots_not_ready"
    bands_blocker = ""
    if not (band_total and top5_count >= band_total and blocked_band_count == 0):
        bands_blocker = _text(bands.get("first_blocker")) or "winner_normalized_bands_not_ready"

    rows = [
        _action(
            1,
            "close_first_source_request",
            "strict_blind_internal_prediction_source",
            source_ready,
            source_blocked,
            source_total,
            args.source_request_closure_board_json,
            source_blocker,
            _text(source_request.get("next_action")) or "close first strict-blind source request",
        ),
        _action(
            2,
            "close_strict_blind_batch_slots",
            "strict_blind_batch_closure_runway",
            batch_ready,
            batch_blocked,
            batch_total,
            args.batch_closure_runway_json,
            batch_blocker,
            _text(batch.get("first_next_action")) or "close all strict-blind batch slots",
        ),
        _action(
            3,
            "pass_sidechain_native_40",
            "sidechain_native_benchmark",
            sidechain_ready,
            max(sidechain_total - sidechain_ready, 0),
            sidechain_total,
            args.sidechain_native_benchmark_json,
            "" if sidechain_total and sidechain_ready >= sidechain_total else "sidechain_native_40_pass_not_proven",
            _text(sidechain.get("first_open_next_action"))
            or "place cleared prediction/native PDBs and no-leak provenance for all benchmark rows",
        ),
        _action(
            4,
            "generate_metric_surface_rows",
            "official_like_metric_surface",
            metric_ready,
            max(metric_total - metric_ready, 0),
            metric_total,
            args.metric_surface_contract_json,
            "" if metric_total and metric_ready >= metric_total else "metric_surface_rows_not_ready",
            _text(metric.get("next_action")) or "generate GDT_TS/lDDT/TM/RMSD/GDT_HA/MolProbity/DockQ/ICS/IPS/LDDT-PLI/BiSyRMSD rows",
        ),
        _action(
            5,
            "preserve_official_archive_as_baseline",
            "official_archive_baseline_guard",
            official_baseline if official_baseline and official_proof == 0 else 0,
            official_proof,
            official_baseline,
            args.official_archive_baseline_json,
            "" if official_baseline and official_proof == 0 else "official_archive_proof_boundary_not_clean",
            "keep official CASP archive submissions baseline-only and excluded from internal strict-blind proof",
        ),
        _action(
            6,
            "score_winner_normalized_bands",
            "casp15_casp16_winner_normalized_comparison",
            top5_count,
            blocked_band_count,
            band_total,
            args.bands_json,
            bands_blocker,
            _text(bands.get("first_next_action")) or "score no-leak historical replay rows against CASP15/16 bands",
        ),
    ]
    if input_blockers:
        rows = []
    ready_rows = [row for row in rows if row["action_status"] == "unlock_ready"]
    blocked_rows = [row for row in rows if row["action_status"] != "unlock_ready"]
    first = _first_blocked(rows)
    status = "historical_winner_normalized_unlock_ready"
    if input_blockers:
        status = "blocked_missing_inputs"
    elif blocked_rows:
        status = "awaiting_historical_winner_normalized_unlocks"
    summary = {
        "packet_type": "casp17_historical_winner_normalized_unlock_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "historical_winner_normalized_unlock_plan_status": status,
        "action_count": len(rows),
        "ready_action_count": len(ready_rows),
        "blocked_action_count": len(blocked_rows),
        "first_blocked_action_id": _text(first.get("action_id")),
        "first_blocked_gate": _text(first.get("gate")),
        "first_blocker": _text(first.get("blocker")),
        "first_next_action": _text(first.get("next_action")),
        "strict_blind_ready_slot_count": strict_ready,
        "strict_blind_slot_count": strict_total,
        "metric_surface_ready_row_count": metric_ready,
        "metric_surface_row_count": metric_total,
        "sidechain_native_pass_count": sidechain_ready,
        "sidechain_native_benchmark_count": sidechain_total,
        "official_archive_baseline_candidate_count": official_baseline,
        "official_archive_competitive_proof_eligible_count": official_proof,
        "winner_band_top5_or_better_count": top5_count,
        "winner_band_count": band_total,
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Winner-Normalized Unlock Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['historical_winner_normalized_unlock_plan_status']}`",
        f"- actions ready/blocked/total: `{summary['ready_action_count']}/{summary['blocked_action_count']}/{summary['action_count']}`",
        f"- strict slots ready/total: `{summary['strict_blind_ready_slot_count']}/{summary['strict_blind_slot_count']}`",
        f"- metric rows ready/total: `{summary['metric_surface_ready_row_count']}/{summary['metric_surface_row_count']}`",
        f"- sidechain-native pass/total: `{summary['sidechain_native_pass_count']}/{summary['sidechain_native_benchmark_count']}`",
        f"- official archive proof: `{summary['official_archive_baseline_candidate_count']}/{summary['official_archive_competitive_proof_eligible_count']}`",
        f"- winner bands top5/total: `{summary['winner_band_top5_or_better_count']}/{summary['winner_band_count']}`",
        f"- first blocked: `{summary['first_blocked_action_id'] or '-'}` `{summary['first_blocked_gate'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Actions",
        "",
        "| order | action | gate | status | ready | blocked | total | blocker | next action |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['action_order']} | `{row['action_id']}` | `{row['gate']}` | `{row['action_status']}` | "
            f"{row['ready_count']} | {row['blocked_count']} | {row['total_count']} | "
            f"`{row['blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_inputs` | - | - | - | missing input artifacts | - |")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 winner-normalized unlock plan.")
    parser.add_argument("--bands-json", default=DEFAULT_BANDS_JSON)
    parser.add_argument("--metric-surface-contract-json", default=DEFAULT_METRIC_SURFACE_CONTRACT_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument("--source-request-closure-board-json", default=DEFAULT_SOURCE_REQUEST_CLOSURE_BOARD_JSON)
    parser.add_argument("--batch-closure-runway-json", default=DEFAULT_BATCH_CLOSURE_RUNWAY_JSON)
    parser.add_argument("--official-archive-baseline-json", default=DEFAULT_OFFICIAL_ARCHIVE_BASELINE_JSON)
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
