#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_METRIC_SURFACE_CONTRACT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_OFFICIAL_ARCHIVE_BASELINE_JSON = "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_winner_normalized_bands_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_winner_normalized_bands_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_WINNER_NORMALIZED_BANDS.md"

CLAIM_BOUNDARY = (
    "Local CASP17 historical winner-normalized band contract only. It maps CASP15/CASP16 planning bands "
    "from CASP17_WIN_TIER_GOAL.md onto current strict-blind historical replay evidence. It does not compute "
    "official CASP scores, import official archive submissions as internal predictions, approve no-leak "
    "provenance, mutate benchmark rows, push remotes, or submit to CASP."
)

ROW_COLUMNS = [
    "band_id",
    "category",
    "primary_metric",
    "current_value",
    "reference_winner_value",
    "winner_ratio",
    "top5_cutoff",
    "top3_cutoff",
    "winner_proximity_ratio_cutoff",
    "band_status",
    "evidence_status",
    "evidence_source",
    "blocker",
    "next_action",
]

BANDS = [
    {
        "band_id": "casp15_regular_domain",
        "category": "CASP15 regular protein domains",
        "primary_metric": "SUM Zscore",
        "current_key": "casp15_regular_domain_sum_zscore",
        "ratio_key": "casp15_regular_domain_winner_ratio",
        "winner": 90.4273,
        "top5": 73.0,
        "top3": 85.0,
        "next_action": "score CASP15-style no-leak regular-domain replay rows and compare SUM Zscore to official top bands",
    },
    {
        "band_id": "casp16_regular_domain",
        "category": "CASP16 regular protein domains",
        "primary_metric": "SUM Zscore",
        "current_key": "casp16_regular_domain_sum_zscore",
        "ratio_key": "casp16_regular_domain_winner_ratio",
        "winner": 40.8978,
        "top5": 33.3,
        "top3": 36.3,
        "next_action": "score CASP16-style no-leak regular-domain replay rows and compare SUM Zscore to official top bands",
    },
    {
        "band_id": "casp16_multimer_complex",
        "category": "CASP16 protein multimers and complexes",
        "primary_metric": "complex z-score and DockQ",
        "current_key": "casp16_complex_sum_zscore",
        "ratio_key": "casp16_complex_winner_ratio",
        "winner": 15.4,
        "top5": 0.0,
        "top3": 14.5,
        "secondary_keys": ["dockq_acceptable_fraction", "dockq_medium_fraction", "dockq_high_fraction"],
        "next_action": "add no-leak complex rows with DockQ, ICS, IPS, model1, and best-of-5 metrics",
    },
    {
        "band_id": "casp16_ligand_pose_affinity",
        "category": "CASP16 ligand pose and affinity",
        "primary_metric": "mean LDDT-PLI",
        "current_key": "mean_lddt_pli",
        "ratio_key": "ligand_lddt_pli_af3_baseline_ratio",
        "winner": 0.80,
        "top5": 0.69,
        "top3": 0.80,
        "secondary_keys": ["bisyrmsd_2a_hit_fraction", "affinity_kendall_tau"],
        "next_action": "add organic ligand-protein historical rows with LDDT-PLI, BiSyRMSD, and affinity ranking",
    },
    {
        "band_id": "accuracy_estimation_model_selection",
        "category": "CASP17 accuracy estimation and model selection",
        "primary_metric": "top1 selection accuracy",
        "current_key": "top1_selection_accuracy",
        "ratio_key": "top1_selection_accuracy_ratio",
        "winner": 1.0,
        "top5": 0.70,
        "top3": 0.80,
        "secondary_keys": ["score_native_correlation", "high_confidence_false_positive_rate"],
        "next_action": "calibrate model1 versus best-of-5 selection on no-leak historical native metrics",
    },
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


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _has_value(summary: dict[str, Any], key: str) -> bool:
    value = summary.get(key)
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _winner_ratio(current_value: float, reference_winner_value: float, summary: dict[str, Any], ratio_key: str) -> float:
    if _has_value(summary, ratio_key):
        return round(_float(summary.get(ratio_key)), 6)
    return round(current_value / reference_winner_value, 6) if reference_winner_value else 0.0


def _evidence_blocker(
    *,
    band: dict[str, Any],
    historical: dict[str, Any],
    strict_ready_slots: int,
    metric_rows_ready: int,
) -> str:
    if strict_ready_slots <= 0 or metric_rows_ready <= 0:
        return "strict_blind_historical_metric_surface_missing"
    if not _has_value(historical, str(band["current_key"])) and not _has_value(historical, str(band["ratio_key"])):
        return f"{band['current_key']}_missing"
    return ""


def _band_status(current_value: float, winner_ratio: float, band: dict[str, Any], blocker: str) -> str:
    if blocker:
        return "blocked_input"
    if current_value >= float(band["top3"]) and winner_ratio >= 0.90:
        return "top3_winner_proximity"
    if current_value >= float(band["top5"]):
        return "top5_competitive"
    return "below_top5_band"


def _row(
    *,
    band: dict[str, Any],
    historical: dict[str, Any],
    strict_ready_slots: int,
    metric_rows_ready: int,
) -> dict[str, Any]:
    current_value = _float(historical.get(str(band["current_key"])))
    ratio = _winner_ratio(current_value, float(band["winner"]), historical, str(band["ratio_key"]))
    blocker = _evidence_blocker(
        band=band,
        historical=historical,
        strict_ready_slots=strict_ready_slots,
        metric_rows_ready=metric_rows_ready,
    )
    status = _band_status(current_value, ratio, band, blocker)
    secondary = []
    for key in band.get("secondary_keys", []):
        secondary.append(f"{key}={_float(historical.get(key)):.3f}")
    evidence_status = "strict_blind_metrics_ready" if not blocker else blocker
    if secondary:
        evidence_status = f"{evidence_status}; " + "; ".join(secondary)
    return {
        "band_id": band["band_id"],
        "category": band["category"],
        "primary_metric": band["primary_metric"],
        "current_value": round(current_value, 6),
        "reference_winner_value": float(band["winner"]),
        "winner_ratio": ratio,
        "top5_cutoff": float(band["top5"]),
        "top3_cutoff": float(band["top3"]),
        "winner_proximity_ratio_cutoff": 0.90,
        "band_status": status,
        "evidence_status": evidence_status,
        "evidence_source": DEFAULT_HISTORICAL_BENCHMARK_JSON,
        "blocker": blocker,
        "next_action": band["next_action"] if status != "top3_winner_proximity" else "keep scoring model1 and best-of-5 under no-leak replay controls",
    }


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


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if any(row["band_status"] == "blocked_input" for row in rows):
        return "blocked_strict_blind_metrics_missing"
    if all(row["band_status"] in {"top5_competitive", "top3_winner_proximity"} for row in rows):
        return "historical_winner_normalized_bands_ready_for_review"
    return "historical_winner_normalized_bands_below_win_tier"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    path_args = [
        ("historical_benchmark_json", args.historical_benchmark_json),
        ("metric_surface_contract_json", args.metric_surface_contract_json),
        ("official_archive_baseline_json", args.official_archive_baseline_json),
        ("sidechain_native_benchmark_json", args.sidechain_native_benchmark_json),
    ]
    input_blockers = [f"{name}_missing" for name, path in path_args if not _resolve(path).exists()]
    historical = _summary(_read_json(args.historical_benchmark_json))
    metric_surface = _summary(_read_json(args.metric_surface_contract_json))
    official = _summary(_read_json(args.official_archive_baseline_json))
    sidechain = _summary(_read_json(args.sidechain_native_benchmark_json))
    strict_ready_slots = _int(metric_surface.get("ready_slot_count"))
    metric_rows_ready = _int(metric_surface.get("ready_metric_row_count"))
    rows = [
        _row(
            band=band,
            historical=historical,
            strict_ready_slots=strict_ready_slots,
            metric_rows_ready=metric_rows_ready,
        )
        for band in BANDS
    ]
    if input_blockers:
        rows = []
    blocked = [row for row in rows if row["band_status"] == "blocked_input"]
    first = blocked[0] if blocked else (rows[0] if rows else {})
    top5_count = sum(1 for row in rows if row["band_status"] in {"top5_competitive", "top3_winner_proximity"})
    top3_count = sum(1 for row in rows if row["band_status"] == "top3_winner_proximity")
    summary = {
        "packet_type": "casp17_historical_winner_normalized_bands",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "historical_winner_normalized_bands_status": _status(input_blockers, rows),
        "band_count": len(rows),
        "top5_or_better_count": top5_count,
        "winner_proximity_count": top3_count,
        "blocked_band_count": len(blocked),
        "first_blocked_band_id": _text(first.get("band_id")) if blocked else "",
        "first_blocker": _text(first.get("blocker")) if blocked else "",
        "first_next_action": _text(first.get("next_action")) if first else "",
        "strict_blind_ready_slot_count": strict_ready_slots,
        "strict_blind_slot_count": _int(metric_surface.get("strict_blind_slot_count")),
        "metric_surface_ready_row_count": metric_rows_ready,
        "metric_surface_row_count": _int(metric_surface.get("metric_surface_row_count")),
        "sidechain_native_pass_count": _int(sidechain.get("pass_count")),
        "sidechain_native_benchmark_count": _int(sidechain.get("benchmark_count")),
        "official_archive_baseline_candidate_count": _int(official.get("baseline_candidate_count")),
        "official_archive_competitive_proof_eligible_count": _int(official.get("competitive_proof_eligible_count")),
        "official_archive_policy": _text(official.get("strict_blind_intake_policy")),
        "threshold_source": "casp17/CASP17_WIN_TIER_GOAL.md",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Winner-Normalized Bands",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['historical_winner_normalized_bands_status']}`",
        f"- bands top5/winner-proximity/blocked/total: `{summary['top5_or_better_count']}/{summary['winner_proximity_count']}/{summary['blocked_band_count']}/{summary['band_count']}`",
        f"- strict-blind slots ready/total: `{summary['strict_blind_ready_slot_count']}/{summary['strict_blind_slot_count']}`",
        f"- metric rows ready/total: `{summary['metric_surface_ready_row_count']}/{summary['metric_surface_row_count']}`",
        f"- official archive baseline/proof-eligible: `{summary['official_archive_baseline_candidate_count']}/{summary['official_archive_competitive_proof_eligible_count']}`",
        f"- first blocked: `{summary['first_blocked_band_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Bands",
        "",
        "| band | metric | current | winner | ratio | top5 | top3 | status | blocker |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['band_id']}` | `{row['primary_metric']}` | `{row['current_value']}` | "
            f"`{row['reference_winner_value']}` | `{row['winner_ratio']}` | `{row['top5_cutoff']}` | "
            f"`{row['top3_cutoff']}` | `{row['band_status']}` | `{row['blocker'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | `blocked_missing_inputs` | missing input artifacts |")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical winner-normalized band contract.")
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
    parser.add_argument("--metric-surface-contract-json", default=DEFAULT_METRIC_SURFACE_CONTRACT_JSON)
    parser.add_argument("--official-archive-baseline-json", default=DEFAULT_OFFICIAL_ARCHIVE_BASELINE_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
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
