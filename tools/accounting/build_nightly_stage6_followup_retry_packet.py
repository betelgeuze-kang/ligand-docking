#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools import build_nightly_stage6_tuning_packet as tuning_mod
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/nightly_stage6_followup_retry_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_followup_retry_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_followup_retry_packet_current.md"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_summary\.json$")
_STABLE_DECOY_CLOSEOUT_SPREAD_A = 0.10


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


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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


def _build_group_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _row_key(row)
        if key:
            index[key].append(dict(row or {}))
    return index


def _merge_replica_group(
    stage4_rows: list[dict[str, Any]],
    stage2_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stage2_by_queue = {
        _text(row.get("queue_id")): dict(row or {})
        for row in stage2_rows
        if _text(row.get("queue_id"))
    }
    merged_rows: list[dict[str, Any]] = []
    seen_queue_ids: set[str] = set()
    for row in stage4_rows:
        queue_id = _text(row.get("queue_id"))
        merged = dict(stage2_by_queue.get(queue_id, {}))
        merged.update(dict(row or {}))
        if queue_id:
            seen_queue_ids.add(queue_id)
        merged_rows.append(merged)
    for row in stage2_rows:
        queue_id = _text(row.get("queue_id"))
        if queue_id and queue_id in seen_queue_ids:
            continue
        merged_rows.append(dict(row or {}))
    return merged_rows


def _replica_sort_key(row: dict[str, Any]) -> tuple[float, float, int, str]:
    return (
        _float(row.get("mean_min_distance_A")) or float("inf"),
        -_float(row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
        _int(row.get("replica_idx")),
        _text(row.get("queue_id")).lower(),
    )


def _best_replica(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return sorted(rows, key=_replica_sort_key)[0]


def _worst_replica(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return sorted(
        rows,
        key=lambda row: (
            _float(row.get("mean_min_distance_A")),
            _float(row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
            _int(row.get("replica_idx")),
            _text(row.get("queue_id")).lower(),
        ),
        reverse=True,
    )[0]


def _classify_row(
    *,
    is_binder: bool,
    distance_over_threshold: float,
    replica_count: int,
    replica_above_threshold_count: int,
    replica_below_threshold_count: int,
    replica_distance_spread: float,
) -> tuple[str, str, str, str]:
    if distance_over_threshold <= 0:
        return (
            "keep_anchor",
            "closure",
            "keep_as_anchor",
            "already inside the gate threshold; keep this row closed as the intact anchor instead of spending retry budget",
        )
    if is_binder:
        if replica_below_threshold_count > 0:
            return (
                "binder_recovery",
                "retry",
                "retry_from_best_replica",
                f"{replica_below_threshold_count}/{max(replica_count, 1)} replicas already clear the gate threshold; recover the binder from the cleanest existing seed before broadening the search",
            )
        return (
            "binder_recovery",
            "retry",
            "reseed_binder_recovery",
            "binder remains above threshold across the available replicas; retry with a broader reseed/refinement pass",
        )
    if replica_count > 0 and replica_above_threshold_count == replica_count and replica_distance_spread <= _STABLE_DECOY_CLOSEOUT_SPREAD_A:
        return (
            "decoy_cleanup",
            "closure",
            "close_decoy_without_retry",
            "all replicas stay above threshold with a tight spread, so this decoy is stable enough to close without spending more retry budget",
        )
    if replica_below_threshold_count > 0:
        return (
            "decoy_cleanup",
            "retry",
            "retry_cleanup_from_best_replica",
            f"{replica_below_threshold_count}/{max(replica_count, 1)} replicas already clear the gate threshold; retry from the cleanest decoy seed to confirm a cleanup path",
        )
    return (
        "decoy_cleanup",
        "retry",
        "reseed_decoy_cleanup",
        "decoy remains above threshold without a stable closure signature; retry with a fresh seed to separate noise from persistent contamination",
    )


def _action_line(row: dict[str, Any], threshold: float) -> str:
    row_key = _text(row.get("row_key")) or "-"
    retry_anchor_queue = _text(row.get("retry_anchor_queue_id")) or "-"
    retry_anchor_seed = _text(row.get("retry_anchor_seed")) or "-"
    retry_anchor_dist = _fmt_float(row.get("retry_anchor_mean_min_distance_A"))
    retry_anchor_npz = _text(row.get("retry_anchor_trajectory_npz")) or "-"
    closure_queue = _text(row.get("closure_evidence_queue_id")) or "-"
    closure_dist = _fmt_float(row.get("closure_evidence_mean_min_distance_A"))
    closure_npz = _text(row.get("closure_evidence_trajectory_npz")) or "-"
    replica_above = _int(row.get("replica_above_threshold_count"))
    replica_count = _int(row.get("replica_count"))
    if _text(row.get("recommended_action")) == "close_decoy_without_retry":
        return (
            f"Close `{row_key}` without extra reruns: `{replica_above}/{replica_count}` replicas stay above "
            f"`{_fmt_float(threshold)}` A, and even the cleanest closure evidence row `{closure_queue}` is still "
            f"`{closure_dist}` A (`{closure_npz}`)."
        )
    if _text(row.get("recommended_action")) == "retry_from_best_replica":
        return (
            f"Retry `{row_key}` as binder recovery from `{retry_anchor_queue}` "
            f"(seed `{retry_anchor_seed}`, mean_min_distance_A=`{retry_anchor_dist}`, `{retry_anchor_npz}`)."
        )
    if _text(row.get("recommended_action")) == "retry_cleanup_from_best_replica":
        return (
            f"Retry `{row_key}` as variable decoy cleanup from `{retry_anchor_queue}` "
            f"(seed `{retry_anchor_seed}`, mean_min_distance_A=`{retry_anchor_dist}`, `{retry_anchor_npz}`)."
        )
    if _text(row.get("recommended_action")) == "keep_as_anchor":
        return (
            f"Keep `{row_key}` closed as the anchor row; its best supporting replica `{closure_queue}` is already "
            f"`{closure_dist}` A (`{closure_npz}`)."
        )
    if _text(row.get("recommended_action")) == "reseed_binder_recovery":
        return f"Retry `{row_key}` with a broader binder-recovery reseed; no replica has cleared the gate yet."
    return f"Retry `{row_key}` with a broader decoy-cleanup reseed; current replicas do not yet justify a closeout."


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
    stage2_manifest_rows: list[dict[str, Any]],
    stage2_manifest_artifact: str,
    stage2_summary_payload: dict[str, Any],
    stage2_summary_artifact: str,
    stage4_score_rows: list[dict[str, Any]],
    stage4_scores_artifact: str,
) -> dict[str, Any]:
    tuning_payload = tuning_mod.build_payload(
        latest_nightly_payload=latest_nightly_payload,
        latest_nightly_artifact=latest_nightly_artifact,
        stage5_payload=stage5_payload,
        stage5_artifact=stage5_artifact,
        stage5_rows=stage5_rows,
        stage5_rows_artifact=stage5_rows_artifact,
        stage5_unique_rows=stage5_unique_rows,
        stage5_unique_artifact=stage5_unique_artifact,
        stage5_topk_rows=stage5_topk_rows,
        stage5_topk_artifact=stage5_topk_artifact,
    )
    tuning_summary = dict(tuning_payload.get("summary", {}) or {})
    tuning_rows = list(tuning_payload.get("rows", []) or [])
    threshold = _float(tuning_summary.get("primary_gate_threshold"))
    stage4_index = _build_group_index(stage4_score_rows)
    stage2_index = _build_group_index(stage2_manifest_rows)

    rows: list[dict[str, Any]] = []
    for tuning_row in tuning_rows:
        row_key = _text(tuning_row.get("row_key"))
        replicas = _merge_replica_group(stage4_index.get(row_key, []), stage2_index.get(row_key, []))
        replica_count = len(replicas)
        replica_above = sum(1 for replica in replicas if _float(replica.get("mean_min_distance_A")) > threshold)
        replica_below = sum(1 for replica in replicas if _float(replica.get("mean_min_distance_A")) <= threshold)
        replica_distances = [
            _float(replica.get("mean_min_distance_A"))
            for replica in replicas
            if _float(replica.get("mean_min_distance_A")) > 0
        ]
        replica_spread = (max(replica_distances) - min(replica_distances)) if replica_distances else 0.0
        best_overall = _best_replica(replicas)
        worst_overall = _worst_replica(replicas)
        below_threshold_replicas = [
            replica for replica in replicas if _float(replica.get("mean_min_distance_A")) <= threshold
        ]
        above_threshold_replicas = [
            replica for replica in replicas if _float(replica.get("mean_min_distance_A")) > threshold
        ]
        retry_anchor = _best_replica(below_threshold_replicas) or best_overall
        closure_evidence = (
            _best_replica(above_threshold_replicas)
            if _int(tuning_row.get("is_binder")) != 1 and replica_above == replica_count and replica_count > 0
            else best_overall
        )
        culprit_kind, action_bucket, recommended_action, execution_reason = _classify_row(
            is_binder=_int(tuning_row.get("is_binder")) == 1,
            distance_over_threshold=_float(tuning_row.get("distance_over_threshold")),
            replica_count=replica_count,
            replica_above_threshold_count=replica_above,
            replica_below_threshold_count=replica_below,
            replica_distance_spread=replica_spread,
        )
        row = dict(tuning_row)
        row.update(
            {
                "culprit_kind": culprit_kind,
                "action_bucket": action_bucket,
                "recommended_action": recommended_action,
                "execution_reason": execution_reason,
                "replica_count": replica_count,
                "replica_above_threshold_count": replica_above,
                "replica_below_threshold_count": replica_below,
                "replica_distance_spread_A": replica_spread,
                "replica_queue_ids": ", ".join(_text(replica.get("queue_id")) for replica in replicas if _text(replica.get("queue_id"))),
                "consistent_above_threshold": bool(replica_count and replica_above == replica_count),
                "retry_anchor_queue_id": _text(retry_anchor.get("queue_id")),
                "retry_anchor_seed": _text(retry_anchor.get("seed")),
                "retry_anchor_mean_min_distance_A": _float(retry_anchor.get("mean_min_distance_A")),
                "retry_anchor_final_min_distance_A": _float(retry_anchor.get("final_min_distance_A")),
                "retry_anchor_min_min_distance_A": _float(retry_anchor.get("min_min_distance_A")),
                "retry_anchor_binding_energy_mmpbsa_kcal_mol_proxy": _float(
                    retry_anchor.get("binding_energy_mmpbsa_kcal_mol_proxy")
                ),
                "retry_anchor_trajectory_npz": _text(retry_anchor.get("trajectory_npz")),
                "closure_evidence_queue_id": _text(closure_evidence.get("queue_id")),
                "closure_evidence_seed": _text(closure_evidence.get("seed")),
                "closure_evidence_mean_min_distance_A": _float(closure_evidence.get("mean_min_distance_A")),
                "closure_evidence_trajectory_npz": _text(closure_evidence.get("trajectory_npz")),
                "worst_replica_queue_id": _text(worst_overall.get("queue_id")),
                "worst_replica_seed": _text(worst_overall.get("seed")),
                "worst_replica_mean_min_distance_A": _float(worst_overall.get("mean_min_distance_A")),
                "worst_replica_trajectory_npz": _text(worst_overall.get("trajectory_npz")),
            }
        )
        rows.append(row)

    rows.sort(key=lambda row: _int(row.get("tuning_priority_rank")) or 9999)
    for rank, row in enumerate(rows, start=1):
        row["execution_priority_rank"] = rank
        row["action_line"] = _action_line(row, threshold)

    retry_rows = [row for row in rows if _text(row.get("action_bucket")) == "retry"]
    closure_rows = [row for row in rows if _text(row.get("action_bucket")) == "closure"]
    closure_without_retry_rows = [
        row for row in rows if _text(row.get("recommended_action")) == "close_decoy_without_retry"
    ]
    keep_anchor_rows = [row for row in rows if _text(row.get("recommended_action")) == "keep_as_anchor"]
    culprit_rows = [row for row in rows if _float(row.get("distance_over_threshold")) > 0]
    action_lines = [_text(row.get("action_line")) for row in rows if _text(row.get("action_line"))]
    priority_line = " -> ".join(
        f"{_text(row.get('row_key'))} [{_text(row.get('recommended_action'))}]"
        for row in rows
    ) or "no follow-up rows are currently populated"
    stage2_ok_rows = _int(stage2_summary_payload.get("ok_rows"))
    stage2_processed_rows = _int(stage2_summary_payload.get("processed_rows"))
    stage2_min_frames_written = _int(stage2_summary_payload.get("min_frames_written"))
    if not rows:
        status = "nightly_stage6_followup_retry_packet_waiting"
        status_line = "nightly stage6 follow-up retry packet is waiting for a populated tuning band."
        next_required_step = "Refresh the nightly stage5 unique/top-k artifacts before building follow-up retry lanes."
    else:
        status = "nightly_stage6_followup_retry_packet_ready"
        status_line = (
            f"translated {len(culprit_rows)} above-threshold rows into {len(retry_rows)} retry lanes and "
            f"{len(closure_rows)} closure lanes using {sum(_int(row.get('replica_count')) for row in rows)} joined "
            "stage4/stage2 replicas."
            + (
                f" Stage2 recovered {stage2_ok_rows}/{stage2_processed_rows} rows with minimum {stage2_min_frames_written} frames."
                if stage2_processed_rows
                else ""
            )
        )
        next_required_step = (
            "Execute the follow-up in priority order: "
            + " ".join(action_lines)
        )

    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": status,
        "status_line": status_line,
        "nightly_summary_artifact": latest_nightly_artifact,
        "tuning_packet_artifact": tuning_mod.DEFAULT_OUT_MD,
        "stage5_summary_artifact": stage5_artifact,
        "stage5_rows_artifact": stage5_rows_artifact,
        "stage5_unique_artifact": stage5_unique_artifact,
        "stage5_topk_artifact": stage5_topk_artifact,
        "stage2_manifest_artifact": stage2_manifest_artifact,
        "stage2_summary_artifact": stage2_summary_artifact,
        "stage4_scores_artifact": stage4_scores_artifact,
        "row_count": len(rows),
        "culprit_row_count": len(culprit_rows),
        "retry_row_count": len(retry_rows),
        "closure_row_count": len(closure_rows),
        "closure_without_retry_count": len(closure_without_retry_rows),
        "keep_anchor_row_count": len(keep_anchor_rows),
        "binder_recovery_count": sum(1 for row in rows if _text(row.get("culprit_kind")) == "binder_recovery"),
        "decoy_cleanup_count": sum(1 for row in rows if _text(row.get("culprit_kind")) == "decoy_cleanup"),
        "replica_rows_joined": sum(_int(row.get("replica_count")) for row in rows),
        "primary_execution_focus_row_key": _text(rows[0].get("row_key")) if rows else "",
        "primary_retry_row_key": _text(retry_rows[0].get("row_key")) if retry_rows else "",
        "primary_closure_row_key": _text(closure_rows[0].get("row_key")) if closure_rows else "",
        "priority_line": priority_line,
        "action_lines": action_lines,
        "stage2_ok_rows": stage2_ok_rows,
        "stage2_processed_rows": stage2_processed_rows,
        "stage2_min_frames_written": stage2_min_frames_written,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    action_lines = list(summary.get("action_lines", []) or [])
    lines = [
        "# Nightly Stage6 Follow-Up Retry Packet",
        "",
        f"- status: `{_text(summary.get('status')) or '-'}`",
        f"- status_line: `{_text(summary.get('status_line')) or '-'}`",
        f"- primary_execution_focus_row_key: `{_text(summary.get('primary_execution_focus_row_key')) or '-'}`",
        f"- retry_row_count: `{_text(summary.get('retry_row_count')) or '-'}`",
        f"- closure_row_count: `{_text(summary.get('closure_row_count')) or '-'}`",
        f"- closure_without_retry_count: `{_text(summary.get('closure_without_retry_count')) or '-'}`",
        f"- keep_anchor_row_count: `{_text(summary.get('keep_anchor_row_count')) or '-'}`",
        f"- replica_rows_joined: `{_text(summary.get('replica_rows_joined')) or '-'}`",
        f"- priority_line: `{_text(summary.get('priority_line')) or '-'}`",
        "",
        "## Execution Order",
        "",
    ]
    if action_lines:
        for line in action_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- Refresh the nightly stage5 unique/top-k artifacts before building follow-up retry lanes.")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| priority | row_key | culprit_kind | action_bucket | recommended_action | retry_anchor_queue_id | closure_evidence_queue_id | replicas | above | below | spread_A | mean_min_distance_A | distance_over_threshold_A |",
            "| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(_int(row.get("execution_priority_rank"))),
                    f"`{_text(row.get('row_key')) or '-'}`",
                    f"`{_text(row.get('culprit_kind')) or '-'}`",
                    f"`{_text(row.get('action_bucket')) or '-'}`",
                    f"`{_text(row.get('recommended_action')) or '-'}`",
                    f"`{_text(row.get('retry_anchor_queue_id')) or '-'}`",
                    f"`{_text(row.get('closure_evidence_queue_id')) or '-'}`",
                    str(_int(row.get("replica_count"))),
                    str(_int(row.get("replica_above_threshold_count"))),
                    str(_int(row.get("replica_below_threshold_count"))),
                    _fmt_float(row.get("replica_distance_spread_A")),
                    _fmt_float(row.get("mean_min_distance_A")),
                    _fmt_float(row.get("distance_over_threshold")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Source Artifacts",
            "",
            f"- `{_text(summary.get('tuning_packet_artifact')) or '-'}`",
            f"- `{_text(summary.get('nightly_summary_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_summary_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_rows_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_unique_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage5_topk_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage2_manifest_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage2_summary_artifact')) or '-'}`",
            f"- `{_text(summary.get('stage4_scores_artifact')) or '-'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an execution-oriented nightly stage6 follow-up retry packet.")
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
                "_stage2_traj_manifest.csv",
                "_stage2_traj_summary.json",
                "_stage4_calibration_scores.csv",
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
    stage2_manifest_artifact = _resolve_existing_companion_artifact(nightly_summary_artifact, "_stage2_traj_manifest.csv")
    stage2_summary_artifact = _resolve_existing_companion_artifact(nightly_summary_artifact, "_stage2_traj_summary.json")
    stage4_scores_artifact = _resolve_existing_companion_artifact(
        nightly_summary_artifact, "_stage4_calibration_scores.csv"
    )

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
        stage2_manifest_rows=_load_csv_rows(stage2_manifest_artifact),
        stage2_manifest_artifact=stage2_manifest_artifact,
        stage2_summary_payload=_maybe_load_json(stage2_summary_artifact),
        stage2_summary_artifact=stage2_summary_artifact,
        stage4_score_rows=_load_csv_rows(stage4_scores_artifact),
        stage4_scores_artifact=stage4_scores_artifact,
    )

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, list(payload.get("rows", []) or []))
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
