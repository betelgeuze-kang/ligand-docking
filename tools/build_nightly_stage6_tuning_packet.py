#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_tuning_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_tuning_packet_current.md"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_summary\.json$")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _discover_latest_top_nightly() -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _derive_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    if not latest_nightly_artifact.endswith("_summary.json"):
        return ""
    return latest_nightly_artifact.replace("_summary.json", suffix)


def _derive_smoke_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    if not latest_nightly_artifact.endswith("_summary.json"):
        return ""
    return latest_nightly_artifact.replace("_summary.json", f"_smoke{suffix}")


def _companion_candidates(latest_nightly_artifact: str, suffix: str) -> list[str]:
    candidates = [
        _derive_companion_artifact(latest_nightly_artifact, suffix),
        _derive_smoke_companion_artifact(latest_nightly_artifact, suffix),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        candidate_text = _text(candidate)
        if candidate_text and candidate_text not in seen:
            seen.add(candidate_text)
            out.append(candidate_text)
    return out


def _resolve_existing_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    candidates = _companion_candidates(latest_nightly_artifact, suffix)
    for candidate in candidates:
        if _resolve(candidate).exists():
            return candidate
    return candidates[0] if candidates else ""


def _discover_latest_top_nightly_with_companions(required_suffixes: list[str]) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    for _, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        artifact = str(path.relative_to(ROOT))
        if all(
            any(_resolve(candidate).exists() for candidate in _companion_candidates(artifact, suffix))
            for suffix in required_suffixes
        ):
            return path
    return None


def _row_key(row: dict[str, Any]) -> str:
    return f"{_text(row.get('target'))}::{_text(row.get('ligand_id'))}"


def build_payload(
    latest_nightly_payload: dict[str, Any],
    latest_nightly_artifact: str,
    stage5_payload: dict[str, Any],
    stage5_artifact: str,
    stage5_rows: list[dict[str, Any]],
    stage5_rows_artifact: str,
    stage5_unique_rows: list[dict[str, Any]],
    stage5_unique_artifact: str,
    stage5_topk_rows: list[dict[str, Any]],
    stage5_topk_artifact: str,
) -> dict[str, Any]:
    stage6 = dict(latest_nightly_payload.get("stages", {}) or {}).get("stage6_operational_gate", {})
    failed_metrics = list(stage6.get("failed_metrics") or [])
    primary_metric = dict(failed_metrics[0] or {}) if failed_metrics else {}
    primary_metric_name = _text(primary_metric.get("metric")) or "mean_min_distance_A"
    threshold = _float(primary_metric.get("threshold")) or 2.5
    observed_mean = _float(stage6.get("mean_min_distance_A")) or _float(stage5_payload.get("mean_min_distance_A_topk_unique"))
    topk_k = _int(stage6.get("mean_min_distance_A_topk_k")) or _int(stage5_payload.get("distance_topk_k")) or len(stage5_unique_rows)
    unique_row_count = len(stage5_unique_rows)
    topk_band_count = min(topk_k, unique_row_count) if unique_row_count else topk_k

    row_roles = {_row_key(raw): _text(raw.get("role")) for raw in stage5_rows}
    rows: list[dict[str, Any]] = []
    for raw in stage5_unique_rows:
        distance = _float(raw.get("mean_min_distance_A"))
        over = max(distance - threshold, 0.0)
        row_key = _row_key(raw)
        rows.append(
            {
                "target": _text(raw.get("target")),
                "ligand_id": _text(raw.get("ligand_id")),
                "row_key": row_key,
                "role": row_roles.get(row_key),
                "is_binder": _int(raw.get("is_binder")),
                "reference_binding_kcal_mol": _float(raw.get("reference_binding_kcal_mol")),
                "binding_energy_mmpbsa_kcal_mol_proxy": _float(raw.get("binding_energy_mmpbsa_kcal_mol_proxy")),
                "binding_energy_mmpbsa_kcal_mol_calibrated": _float(raw.get("binding_energy_mmpbsa_kcal_mol_calibrated")),
                "mean_min_distance_A": distance,
                "distance_over_threshold": over,
                "distance_to_threshold_margin": threshold - distance,
                "tuning_status": "needs_distance_reduction" if over > 0 else "keep_as_anchor",
            }
        )

    priority_sorted = sorted(
        rows,
        key=lambda row: (row["distance_over_threshold"], row["mean_min_distance_A"], row["is_binder"]),
        reverse=True,
    )
    distance_sorted = sorted(rows, key=lambda row: (row["mean_min_distance_A"], row["target"], row["ligand_id"]))
    priority_ranks = {_row_key(row): rank for rank, row in enumerate(priority_sorted, start=1)}
    distance_ranks = {_row_key(row): rank for rank, row in enumerate(distance_sorted, start=1)}
    for row in rows:
        key = row["row_key"]
        row["tuning_priority_rank"] = priority_ranks.get(key, 0)
        row["distance_rank"] = distance_ranks.get(key, 0)

    rows.sort(key=lambda row: row["tuning_priority_rank"])

    above_threshold_rows = [row for row in rows if row["distance_over_threshold"] > 0]
    above_threshold_count = len(above_threshold_rows)
    below_or_at_threshold_count = len(rows) - above_threshold_count
    reduction_needed_total = max(observed_mean - threshold, 0.0) * float(topk_band_count or 0)
    reduction_available_total = sum(row["distance_over_threshold"] for row in rows)

    cumulative = 0.0
    min_rows_to_touch = 0
    if reduction_needed_total > 0:
        for min_rows_to_touch, row in enumerate(priority_sorted, start=1):
            cumulative += row["distance_over_threshold"]
            if cumulative >= reduction_needed_total:
                break
    if reduction_needed_total <= 0:
        min_rows_to_touch = 0
    topk_equals_full_unique_band = bool(unique_row_count) and topk_band_count >= unique_row_count
    all_above_threshold_rows_need_touch = bool(above_threshold_rows) and min_rows_to_touch >= above_threshold_count

    topk_hits = _int(stage5_topk_rows[0].get("hits")) if stage5_topk_rows else _int(stage6.get("ranking_topk_hit_rate") or 0)
    topk_hit_rate = _float(stage5_topk_rows[0].get("hit_rate")) if stage5_topk_rows else _float(stage6.get("ranking_topk_hit_rate"))
    binder_count = sum(1 for row in rows if row["is_binder"] == 1)
    nonbinder_count = sum(1 for row in rows if row["is_binder"] != 1)

    primary_focus = rows[0]["row_key"] if rows else ""
    secondary_focus = rows[1]["row_key"] if len(rows) > 1 else ""
    tertiary_focus = rows[2]["row_key"] if len(rows) > 2 else ""
    priority_line = " -> ".join(
        f"{row['row_key']} (+{_fmt_float(row['distance_over_threshold'])} A)"
        for row in rows
        if row["distance_over_threshold"] > 0
    )
    if not priority_line:
        priority_line = "all current rows are already within threshold"

    if observed_mean <= 0 or not rows:
        status = "nightly_stage6_tuning_packet_waiting"
        status_line = "nightly stage6 tuning packet is waiting for a populated unique-eval row set."
        next_required_step = "Refresh the nightly stage5 unique/top-k artifacts before using this packet."
    else:
        status = "nightly_stage6_tuning_packet_ready"
        status_line = (
            f"topk source `{_text(stage6.get('mean_min_distance_A_source')) or 'eval_unique_topk'}` is using "
            f"`{topk_band_count}` rows with mean `{primary_metric_name}={_fmt_float(observed_mean)}` against "
            f"`{_fmt_float(threshold)}`; aggregate reduction still needed is `{_fmt_float(reduction_needed_total)}` A."
        )
        next_required_step = (
            f"Open `{DEFAULT_OUT_MD}` and tune the exact culprit band rather than only reranking: "
            f"`topk_k={topk_band_count}` and `unique_rows={unique_row_count}`"
            + (" match and the gate is already covering the full unique band" if topk_equals_full_unique_band else " do not match")
            + f", so the current gate mean needs `{_fmt_float(reduction_needed_total)}` A of total improvement. "
            f"Priority order is `{priority_line}`. "
            + (
                f"All `{above_threshold_count}` above-threshold rows need touch if each row is only brought down to the `{_fmt_float(threshold)}` threshold."
                if all_above_threshold_rows_need_touch
                else f"At least `{min_rows_to_touch}` rows need touch to clear the mean gate."
            )
        )

    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": status,
        "status_line": status_line,
        "nightly_summary_artifact": latest_nightly_artifact,
        "stage5_summary_artifact": stage5_artifact,
        "stage5_rows_artifact": stage5_rows_artifact,
        "stage5_unique_artifact": stage5_unique_artifact,
        "stage5_topk_artifact": stage5_topk_artifact,
        "primary_gate_metric": primary_metric_name,
        "primary_gate_value": observed_mean,
        "primary_gate_threshold": threshold,
        "primary_gate_delta": max(observed_mean - threshold, 0.0),
        "primary_gate_source": _text(stage6.get("mean_min_distance_A_source")) or "eval_unique_topk",
        "topk_k": topk_band_count,
        "unique_eval_row_count": unique_row_count,
        "topk_equals_full_unique_band": topk_equals_full_unique_band,
        "rows_above_threshold_count": above_threshold_count,
        "rows_below_or_at_threshold_count": below_or_at_threshold_count,
        "binder_count": binder_count,
        "nonbinder_count": nonbinder_count,
        "aggregate_distance_reduction_needed_A": reduction_needed_total,
        "available_reduction_to_threshold_A": reduction_available_total,
        "minimum_rows_to_touch_if_clamped_to_threshold": min_rows_to_touch,
        "all_above_threshold_rows_need_touch": all_above_threshold_rows_need_touch,
        "primary_focus_row_key": primary_focus,
        "secondary_focus_row_key": secondary_focus,
        "tertiary_focus_row_key": tertiary_focus,
        "priority_line": priority_line,
        "topk_hit_rate": topk_hit_rate,
        "topk_hits": topk_hits,
        "ranking_eval_unique_keys": _int(stage6.get("ranking_eval_unique_keys")),
        "ranking_ood_unique_keys": _int(stage6.get("ranking_ood_unique_keys")),
        "ranking_expected_score_coverage_ratio": _float(stage6.get("ranking_expected_score_coverage_ratio")),
        "ranking_auc": _float(stage6.get("ranking_auc")),
        "ranking_pr_auc": _float(stage6.get("ranking_pr_auc")),
        "ranking_ef1": _float(stage6.get("ranking_ef1")),
        "ranking_bedroc": _float(stage6.get("ranking_bedroc")),
        "ranking_ece": _float(stage6.get("ranking_ece")),
        "min_frames_observed": _int(stage6.get("min_frames_observed")),
        "next_required_step": next_required_step,
        "row_count": len(rows),
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Tuning Packet",
        "",
        f"- status: `{_text(summary.get('status')) or '-'}`",
        f"- status_line: `{_text(summary.get('status_line')) or '-'}`",
        f"- primary_gate_metric: `{_text(summary.get('primary_gate_metric')) or '-'}`",
        f"- primary_gate_value: `{_fmt_float(summary.get('primary_gate_value'))}`",
        f"- primary_gate_threshold: `{_fmt_float(summary.get('primary_gate_threshold'))}`",
        f"- aggregate_distance_reduction_needed_A: `{_fmt_float(summary.get('aggregate_distance_reduction_needed_A'))}`",
        f"- topk_k: `{_text(summary.get('topk_k')) or '-'}`",
        f"- unique_eval_row_count: `{_text(summary.get('unique_eval_row_count')) or '-'}`",
        f"- topk_equals_full_unique_band: `{_text(summary.get('topk_equals_full_unique_band')) or '-'}`",
        f"- rows_above_threshold_count: `{_text(summary.get('rows_above_threshold_count')) or '-'}`",
        f"- minimum_rows_to_touch_if_clamped_to_threshold: `{_text(summary.get('minimum_rows_to_touch_if_clamped_to_threshold')) or '-'}`",
        f"- priority_line: `{_text(summary.get('priority_line')) or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {_text(summary.get('next_required_step')) or '-'}",
        "",
        "## Culprit Rows",
        "",
        "| priority | row_key | role | target | ligand_id | is_binder | mean_min_distance_A | distance_over_threshold_A | calibrated_score | proxy_score | reference_binding_kcal_mol | tuning_status |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_int(row.get("tuning_priority_rank"))),
                    f"`{_text(row.get('row_key')) or '-'}`",
                    f"`{_text(row.get('role')) or '-'}`",
                    f"`{_text(row.get('target')) or '-'}`",
                    f"`{_text(row.get('ligand_id')) or '-'}`",
                    str(_int(row.get("is_binder"))),
                    _fmt_float(row.get("mean_min_distance_A")),
                    _fmt_float(row.get("distance_over_threshold")),
                    _fmt_float(row.get("binding_energy_mmpbsa_kcal_mol_calibrated")),
                    _fmt_float(row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
                    _fmt_float(row.get("reference_binding_kcal_mol")),
                    f"`{_text(row.get('tuning_status')) or '-'}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Source Artifacts",
            "",
            f"- `{_text(summary.get('nightly_summary_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_summary_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_rows_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_unique_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_topk_artifact')) or '-'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an execution-oriented nightly stage6 tuning packet.")
    parser.add_argument("--nightly-summary-json", default="", help="Optional explicit nightly summary JSON path.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    nightly_summary_path = (
        _resolve(args.nightly_summary_json)
        if args.nightly_summary_json
        else _discover_latest_top_nightly_with_companions(
            [
                "_stage5_ranking_summary.json",
                "_stage5_ranking_rows.csv",
                "_stage5_ranking_unique.csv",
                "_stage5_ranking_topk.csv",
            ]
        )
        or _discover_latest_top_nightly()
    )
    if nightly_summary_path is None:
        raise SystemExit("No nightly summary artifact was found under runs/.")

    nightly_summary_artifact = str(nightly_summary_path.relative_to(ROOT))
    stage5_artifact = _resolve_existing_companion_artifact(nightly_summary_artifact, "_stage5_ranking_summary.json")
    stage5_rows_artifact = _resolve_existing_companion_artifact(nightly_summary_artifact, "_stage5_ranking_rows.csv")
    stage5_unique_artifact = _resolve_existing_companion_artifact(
        nightly_summary_artifact, "_stage5_ranking_unique.csv"
    )
    stage5_topk_artifact = _resolve_existing_companion_artifact(nightly_summary_artifact, "_stage5_ranking_topk.csv")

    payload = build_payload(
        latest_nightly_payload=_load_json(nightly_summary_path),
        latest_nightly_artifact=nightly_summary_artifact,
        stage5_payload=_load_json(stage5_artifact),
        stage5_artifact=stage5_artifact,
        stage5_rows=_load_csv_rows(stage5_rows_artifact),
        stage5_rows_artifact=stage5_rows_artifact,
        stage5_unique_rows=_load_csv_rows(stage5_unique_artifact),
        stage5_unique_artifact=stage5_unique_artifact,
        stage5_topk_rows=_load_csv_rows(stage5_topk_artifact),
        stage5_topk_artifact=stage5_topk_artifact,
    )

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv_rows(out_csv, list(payload.get("rows", []) or []))
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
