#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_STAGE5_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_SLICE_ROWS_CSV = "runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv"
DEFAULT_V11_REVIEW_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_none_stage3_shadow_replay_review_current.json"
DEFAULT_PROBE_SUBSET_CSV = "runs/gpcr_frozen_ranking_quality_port_probe_subset_stage3_current.csv"
DEFAULT_ADAPTIVE_CACHE_CSV = "runs/gpcr_frozen_ranking_quality_port_probe_adaptive_feature_cache_current.csv"
DEFAULT_ADAPTIVE_CACHE_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_adaptive_feature_cache_current.json"
DEFAULT_ATOM_WINDOW_CACHE_CSV = "runs/gpcr_frozen_ranking_quality_port_probe_atom_window_cache_current.csv"
DEFAULT_V11_SPEC_JSON = "runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11_current.json"
DEFAULT_V16_SPEC_JSON = "runs/gpcr_residual_prototype_spec_false_support_discriminator_shadow_v16.json"
DEFAULT_V11_REPLAY_SCORES_CSV = "runs/gpcr_frozen_ranking_quality_port_probe_v11_shadow_replay_scores_current.csv"
DEFAULT_V11_REPLAY_SUMMARY_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_v11_shadow_replay_summary_current.json"
DEFAULT_V11_REVIEW_OUT_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_v11_shadow_replay_review_current.json"
DEFAULT_V16_REPLAY_SCORES_CSV = "runs/gpcr_frozen_ranking_quality_port_probe_v16_shadow_replay_scores_current.csv"
DEFAULT_V16_REPLAY_SUMMARY_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_v16_shadow_replay_summary_current.json"
DEFAULT_V16_GAP_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_v16_gap_packet_current.json"
DEFAULT_HTR2A_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_htr2a_topology_replay_summary_current.json"
DEFAULT_OPRM1_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_oprm1_topology_replay_summary_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_ranking_quality_port_probe_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_ranking_quality_port_probe_chain_current.md"
DEFAULT_FULL_ADAPTIVE_CACHE_CSV = (
    "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_adaptive_truebase_current.csv"
)
DEFAULT_FULL_ADAPTIVE_CACHE_JSON = (
    "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_adaptive_truebase_current.json"
)
DEFAULT_FULL_DISCRIMINATOR_CACHE_CSV = (
    "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_adaptive_truebase_current_discriminator.csv"
)
DEFAULT_FULL_V16_REPLAY_SCORES_CSV = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_v16_shadow_replay_scores_current.csv"
)
DEFAULT_FULL_V16_REPLAY_SUMMARY_JSON = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_v16_shadow_replay_summary_current.json"
)
DEFAULT_FULL_V16_GAP_JSON = "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_v16_gap_packet_current.json"
DEFAULT_FULL_HTR2A_JSON = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_htr2a_topology_replay_summary_current.json"
)
DEFAULT_FULL_OPRM1_JSON = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_oprm1_topology_replay_summary_current.json"
)
DEFAULT_FULL_OUT_JSON = "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_chain_current.json"
DEFAULT_FULL_OUT_MD = "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_chain_current.md"
DEFAULT_PROBE_CHAIN_JSON = DEFAULT_OUT_JSON
DEFAULT_LEGACY_V16_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"

NON_ADRB2_TARGETS = (
    "CHEMBL217_DRD2_HUMAN",
    "CHEMBL224_HTR2A_HUMAN",
    "CHEMBL233_OPRM1_HUMAN",
)
POSITIVE_BY_TARGET = {
    "CHEMBL217_DRD2_HUMAN": "CHEMBL301265",
    "CHEMBL224_HTR2A_HUMAN": "CHEMBL83894",
    "CHEMBL233_OPRM1_HUMAN": "CHEMBL331883",
}
ACTIVE_SCORE_COL = "binding_score_composite_v7_residual_active"
TOP_DECOYS_PER_TARGET = 64


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
        return out if out == out else None
    except (TypeError, ValueError):
        return None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target")), _text(row.get("ligand_id")))


def _shadow_top10_keys(review_json: str | Path) -> set[tuple[str, str]]:
    payload = _read_json(review_json)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    shadow = summary.get("shadow_score_summary") if isinstance(summary.get("shadow_score_summary"), dict) else {}
    keys: set[tuple[str, str]] = set()
    for row in shadow.get("top10") or []:
        if isinstance(row, dict):
            key = (_text(row.get("target")), _text(row.get("ligand_id")))
            if key[0] and key[1]:
                keys.add(key)
    return keys


def build_probe_subset(
    *,
    stage3_scores_csv: str | Path,
    stage5_rows_csv: str | Path,
    slice_rows_csv: str | Path,
    v11_review_json: str | Path,
    out_csv: str | Path,
    top_decoys_per_target: int = TOP_DECOYS_PER_TARGET,
) -> dict[str, Any]:
    wanted: set[tuple[str, str]] = set()
    for target, ligand_id in POSITIVE_BY_TARGET.items():
        wanted.add((target, ligand_id))
    for row in _read_csv(slice_rows_csv):
        target = _text(row.get("target"))
        if target in NON_ADRB2_TARGETS:
            wanted.add(_row_key(row))
    wanted.update(_shadow_top10_keys(v11_review_json))

    decoys_by_target: dict[str, list[tuple[float, str]]] = {target: [] for target in NON_ADRB2_TARGETS}
    for row in _read_csv(stage5_rows_csv):
        target = _text(row.get("target"))
        if target not in NON_ADRB2_TARGETS or _is_positive(row):
            continue
        score = _float(row.get(ACTIVE_SCORE_COL))
        if score is None:
            continue
        decoys_by_target[target].append((score, _text(row.get("ligand_id"))))
    for target, rows in decoys_by_target.items():
        rows.sort(key=lambda item: item[0])
        for _, ligand_id in rows[: int(top_decoys_per_target)]:
            if ligand_id:
                wanted.add((target, ligand_id))

    stage3_rows = _read_csv(stage3_scores_csv)
    subset = [row for row in stage3_rows if _row_key(row) in wanted]
    _write_csv(out_csv, subset)
    counts = {target: 0 for target in NON_ADRB2_TARGETS}
    for row in subset:
        target = _text(row.get("target"))
        if target in counts:
            counts[target] += 1
    return {
        "wanted_key_count": len(wanted),
        "subset_row_count": len(subset),
        "target_row_counts": counts,
        "out_csv": str(_resolve(out_csv)),
    }


def _gap_target_summary(gap_payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": _text((gap_payload.get("summary") or {}).get("status")),
        "top20_positive_count": (gap_payload.get("summary") or {}).get("top20_positive_count"),
        "blockers": list((gap_payload.get("summary") or {}).get("blocker_counts") or {}),
    }
    for row in gap_payload.get("target_summaries") or []:
        if not isinstance(row, dict):
            continue
        target = _text(row.get("target"))
        if target not in NON_ADRB2_TARGETS:
            continue
        out[target] = {
            "ligand_id": row.get("ligand_id"),
            "target_rank": row.get("target_rank"),
            "decoys_above_positive": row.get("decoys_above_positive"),
            "global_rank": row.get("global_rank"),
            "blockers": list(row.get("blockers") or []),
        }
    return out


def _shadow_target_summary(review_summary: dict[str, Any]) -> dict[str, Any]:
    shadow = review_summary.get("shadow_score_summary") if isinstance(review_summary.get("shadow_score_summary"), dict) else {}
    out: dict[str, Any] = {
        "status": _text(review_summary.get("status")),
        "top20_positive_count": shadow.get("top20_positive_count"),
        "blockers": list(review_summary.get("blockers") or []),
    }
    rows = shadow.get("target_positive_ranks") if isinstance(shadow.get("target_positive_ranks"), dict) else {}
    for target in NON_ADRB2_TARGETS:
        target_rows = rows.get(target) if isinstance(rows.get(target), list) else []
        positive = target_rows[0] if target_rows else {}
        out[target] = {
            "ligand_id": positive.get("ligand_id"),
            "target_rank": positive.get("target_rank"),
            "decoys_above_positive": positive.get("decoys_above_positive"),
            "global_rank": next(
                (
                    item.get("global_rank")
                    for item in shadow.get("positive_ranks") or []
                    if isinstance(item, dict) and _text(item.get("target")) == target
                ),
                None,
            ),
        }
    return out


def _expected_non_adrb2_row_count(stage3_scores_csv: str | Path) -> int:
    return sum(
        1
        for row in _read_csv(stage3_scores_csv)
        if _text(row.get("target")) in NON_ADRB2_TARGETS
    )


def _active_score_baseline(stage5_rows_csv: str | Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in _read_csv(stage5_rows_csv):
        target = _text(row.get("target"))
        if target not in NON_ADRB2_TARGETS or not _is_positive(row):
            continue
        out[target] = {
            "ligand_id": row.get("ligand_id"),
            "active_score": _float(row.get(ACTIVE_SCORE_COL)),
        }
    return out


def build_full_non_adrb2_adaptive_packet(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    stage5_rows_csv: str | Path = DEFAULT_STAGE5_ROWS_CSV,
    adaptive_cache_csv: str | Path = DEFAULT_FULL_ADAPTIVE_CACHE_CSV,
    adaptive_cache_json: str | Path = DEFAULT_FULL_ADAPTIVE_CACHE_JSON,
    discriminator_cache_csv: str | Path = DEFAULT_FULL_DISCRIMINATOR_CACHE_CSV,
    v16_replay_scores_csv: str | Path = DEFAULT_FULL_V16_REPLAY_SCORES_CSV,
    v16_replay_summary_json: str | Path = DEFAULT_FULL_V16_REPLAY_SUMMARY_JSON,
    v16_gap_json: str | Path = DEFAULT_FULL_V16_GAP_JSON,
    htr2a_json: str | Path = DEFAULT_FULL_HTR2A_JSON,
    oprm1_json: str | Path = DEFAULT_FULL_OPRM1_JSON,
    probe_chain_json: str | Path = DEFAULT_PROBE_CHAIN_JSON,
    legacy_v16_gap_json: str | Path = DEFAULT_LEGACY_V16_GAP_JSON,
    skip_adaptive_cache: bool = False,
    skip_v16_replay: bool = False,
    skip_htr2a_replay: bool = False,
    skip_oprm1_replay: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    expected_rows = _expected_non_adrb2_row_count(stage3_scores_csv)
    adaptive_summary = _read_json(adaptive_cache_json).get("summary", {})
    cache_row_count = len(_read_csv(adaptive_cache_csv))
    if expected_rows <= 0:
        blockers.append("non_adrb2_stage3_rows_missing")
    elif cache_row_count < expected_rows and not skip_adaptive_cache:
        _run(
            [
                sys.executable,
                "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py",
                "--input-csv",
                str(stage3_scores_csv),
                "--anchor-mode",
                "adaptive_pose_preserving",
                "--target-filter",
                ",".join(NON_ADRB2_TARGETS),
                "--resume-existing",
                "--out-csv",
                str(adaptive_cache_csv),
                "--out-json",
                str(adaptive_cache_json),
            ]
        )
        adaptive_summary = _read_json(adaptive_cache_json).get("summary", {})
        cache_row_count = len(_read_csv(adaptive_cache_csv))
    if cache_row_count < expected_rows:
        blockers.append("adaptive_feature_cache_incomplete")

    discriminator_summary: dict[str, Any] = {}
    refreshed_cache_csv = _resolve(discriminator_cache_csv)
    if not skip_v16_replay and not blockers:
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/recompute_gpcr_frozen_feature_cache_discriminator_pressures.py",
                "--input-csv",
                str(adaptive_cache_csv),
                "--out-csv",
                str(refreshed_cache_csv),
                "--out-json",
                str(refreshed_cache_csv.with_suffix(".json")),
            ]
        )
        discriminator_summary = _read_json(refreshed_cache_csv.with_suffix(".json")).get("summary", {})
        from tools.accounting.build_gpcr_residual_prototype_spec import build_payload as build_spec_payload

        v16_spec_path = _resolve(DEFAULT_V16_SPEC_JSON)
        v16_payload = build_spec_payload(variant="gpcr_core_false_support_discriminator_shadow_v16")
        v16_spec_path.write_text(json.dumps(v16_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _run(
            [
                sys.executable,
                "tools/product/replay_gpcr_residual_shadow_scores.py",
                "--input-scores-csv",
                str(refreshed_cache_csv),
                "--residual-prototype-spec-json",
                str(v16_spec_path),
                "--out-scores-csv",
                str(v16_replay_scores_csv),
                "--out-summary-json",
                str(v16_replay_summary_json),
                "--out-summary-md",
                str(_resolve(v16_replay_summary_json).with_suffix(".md")),
            ]
        )
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/build_gpcr_frozen_pose_support_gap_packet.py",
                "--input-scores-csv",
                str(v16_replay_scores_csv),
                "--label-csv",
                str(stage5_rows_csv),
                "--out-json",
                str(v16_gap_json),
                "--out-csv",
                str(_resolve(v16_gap_json).with_suffix(".csv")),
                "--out-md",
                str(_resolve(v16_gap_json).with_suffix(".md")),
            ]
        )

    v16_gap_payload = _read_json(v16_gap_json)
    v16_gap_summary = v16_gap_payload.get("summary", {})
    htr2a_summary: dict[str, Any] = {}
    oprm1_summary: dict[str, Any] = {}
    if not skip_htr2a_replay and not blockers and _resolve(v16_replay_scores_csv).exists():
        htr2a_scores = _resolve(htr2a_json).with_name(
            _resolve(htr2a_json).stem.replace("_summary", "_scores") + ".csv"
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_htr2a_topology_support_shadow_replay.py",
                "--input-scores-csv",
                str(v16_replay_scores_csv),
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
                "--out-json",
                str(htr2a_json),
                "--out-scores-csv",
                str(htr2a_scores),
            ]
        )
        htr2a_summary = _read_json(htr2a_json).get("summary", {})

    if not skip_oprm1_replay and not blockers and _resolve(htr2a_json).exists():
        oprm1_scores = _resolve(oprm1_json).with_name(
            _resolve(oprm1_json).stem.replace("_summary", "_scores") + ".csv"
        )
        htr2a_scores = _resolve(htr2a_json).with_name(
            _resolve(htr2a_json).stem.replace("_summary", "_scores") + ".csv"
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_oprm1_topology_pose_shadow_replay.py",
                "--input-scores-csv",
                str(htr2a_scores),
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
                "--htr2a-replay-json",
                str(htr2a_json),
                "--out-json",
                str(oprm1_json),
                "--out-scores-csv",
                str(oprm1_scores),
            ]
        )
        oprm1_summary = _read_json(oprm1_json).get("summary", {})

    probe_payload = _read_json(probe_chain_json)
    probe_v16 = (probe_payload.get("lanes") or {}).get("v16_gap_probe") or {}
    legacy_v16 = _gap_target_summary(_read_json(legacy_v16_gap_json))
    active_baseline = _active_score_baseline(stage5_rows_csv)
    lanes = {
        "adaptive_full_cache": {
            "status": _text(adaptive_summary.get("status")),
            "feature_row_count": cache_row_count,
            "expected_non_adrb2_row_count": expected_rows,
            "false_valid_anchor_discriminator_row_count": discriminator_summary.get(
                "false_valid_anchor_discriminator_row_count"
            ),
        },
        "v16_gap_full": _gap_target_summary(v16_gap_payload),
        "htr2a_topology_full": {
            "status": _text(htr2a_summary.get("status")),
            "selected_weight": htr2a_summary.get("selected_weight"),
            "selected_target_summaries": htr2a_summary.get("selected_target_summaries"),
        },
        "oprm1_topology_full": {
            "status": _text(oprm1_summary.get("status")),
            "selected_weight": oprm1_summary.get("selected_weight"),
            "selected_target_summaries": oprm1_summary.get("selected_target_summaries"),
        },
        "comparison_probe_subset_v16_gap": probe_v16,
        "comparison_legacy_v16_gap_no_discriminator_refresh": legacy_v16,
        "comparison_active_score_baseline_stage5": active_baseline,
    }
    if int(v16_gap_summary.get("top20_positive_count") or 0) < 3:
        blockers.append("full_v16_shadow_top20_incomplete")
    for target in NON_ADRB2_TARGETS:
        target_row = (lanes["v16_gap_full"] or {}).get(target) or {}
        decoys = int(target_row.get("decoys_above_positive") or 0)
        if decoys > 0:
            blockers.append(f"full_v16_gap:{target}_decoys_above_positive:{decoys}")

    status = "ranking_quality_port_full_nonadrb2_complete_claim_locked"
    if blockers:
        status = "blocked_ranking_quality_port_full_nonadrb2_claim_locked"

    summary = {
        "packet_type": "gpcr_frozen_ranking_quality_port_full_nonadrb2_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "expected_non_adrb2_row_count": expected_rows,
        "lanes": lanes,
        "blockers": sorted(set(blockers)),
        "artifacts": {
            "adaptive_cache_csv": str(_resolve(adaptive_cache_csv)),
            "discriminator_cache_csv": str(refreshed_cache_csv),
            "v16_gap_json": str(_resolve(v16_gap_json)),
            "htr2a_json": str(_resolve(htr2a_json)),
            "oprm1_json": str(_resolve(oprm1_json)),
            "probe_chain_json": str(_resolve(probe_chain_json)),
        },
        "next_required_step": (
            "Full 30k adaptive+v16 shadow lanes refreshed under claim lock. Probe-subset green does not "
            "authorize claim; repair HTR2A/OPRM1 anchor support and rerun guarded 100k when CI-low/top20 clear."
            if blockers
            else "Unexpected full-cohort green; keep claim locked until guarded 100k CI-low/top20 gates clear."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def build_packet(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    stage5_rows_csv: str | Path = DEFAULT_STAGE5_ROWS_CSV,
    slice_rows_csv: str | Path = DEFAULT_SLICE_ROWS_CSV,
    v11_review_json: str | Path = DEFAULT_V11_REVIEW_JSON,
    probe_subset_csv: str | Path = DEFAULT_PROBE_SUBSET_CSV,
    adaptive_cache_csv: str | Path = DEFAULT_ADAPTIVE_CACHE_CSV,
    adaptive_cache_json: str | Path = DEFAULT_ADAPTIVE_CACHE_JSON,
    atom_window_cache_csv: str | Path = DEFAULT_ATOM_WINDOW_CACHE_CSV,
    v11_replay_scores_csv: str | Path = DEFAULT_V11_REPLAY_SCORES_CSV,
    v11_replay_summary_json: str | Path = DEFAULT_V11_REPLAY_SUMMARY_JSON,
    v11_review_out_json: str | Path = DEFAULT_V11_REVIEW_OUT_JSON,
    v16_replay_scores_csv: str | Path = DEFAULT_V16_REPLAY_SCORES_CSV,
    v16_replay_summary_json: str | Path = DEFAULT_V16_REPLAY_SUMMARY_JSON,
    v16_gap_json: str | Path = DEFAULT_V16_GAP_JSON,
    htr2a_json: str | Path = DEFAULT_HTR2A_JSON,
    oprm1_json: str | Path = DEFAULT_OPRM1_JSON,
    skip_adaptive_cache: bool = False,
    skip_atom_window_cache: bool = False,
    skip_v11_replay: bool = False,
    skip_v16_replay: bool = False,
    skip_htr2a_replay: bool = False,
    skip_oprm1_replay: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    subset_summary = build_probe_subset(
        stage3_scores_csv=stage3_scores_csv,
        stage5_rows_csv=stage5_rows_csv,
        slice_rows_csv=slice_rows_csv,
        v11_review_json=v11_review_json,
        out_csv=probe_subset_csv,
    )
    if subset_summary["subset_row_count"] <= 0:
        blockers.append("probe_subset_empty")

    adaptive_summary: dict[str, Any] = {}
    if not skip_adaptive_cache and not blockers:
        _run(
            [
                sys.executable,
                "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py",
                "--input-csv",
                str(probe_subset_csv),
                "--anchor-mode",
                "adaptive_pose_preserving",
                "--out-csv",
                str(adaptive_cache_csv),
                "--out-json",
                str(adaptive_cache_json),
            ]
        )
        adaptive_summary = _read_json(adaptive_cache_json).get("summary", {})
        if int(adaptive_summary.get("feature_row_count") or 0) <= 0:
            blockers.append("adaptive_feature_cache_empty")

    atom_window_summary: dict[str, Any] = {}
    if not skip_atom_window_cache and not blockers:
        drd2_keys = {
            _row_key(row)
            for row in _read_csv(slice_rows_csv)
            if _text(row.get("target")) == "CHEMBL217_DRD2_HUMAN"
        }
        drd2_subset = [row for row in _read_csv(probe_subset_csv) if _row_key(row) in drd2_keys]
        drd2_subset_csv = _resolve(probe_subset_csv).with_name(
            _resolve(probe_subset_csv).stem + "_drd2_slice_only.csv"
        )
        _write_csv(drd2_subset_csv, drd2_subset)
        atom_json = _resolve(atom_window_cache_csv).with_suffix(".json")
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/build_gpcr_atom_window_anchor_feature_cache.py",
                "--input-csv",
                str(drd2_subset_csv),
                "--out-csv",
                str(atom_window_cache_csv),
                "--out-json",
                str(atom_json),
            ]
        )
        atom_window_summary = _read_json(atom_json).get("summary", {})

    refreshed_cache_csv = _resolve(adaptive_cache_csv).with_name(_resolve(adaptive_cache_csv).stem + "_discriminator.csv")
    v11_review_summary: dict[str, Any] = {}
    if not skip_v11_replay and not blockers:
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/recompute_gpcr_frozen_feature_cache_discriminator_pressures.py",
                "--input-csv",
                str(adaptive_cache_csv),
                "--out-csv",
                str(refreshed_cache_csv),
                "--out-json",
                str(refreshed_cache_csv.with_suffix(".json")),
            ]
        )
        from tools.accounting.build_gpcr_residual_prototype_spec import (
            build_payload as build_spec_payload,
            _write_csv as write_spec_csv,
            _write_markdown as write_spec_markdown,
        )

        spec_path = _resolve(DEFAULT_V11_SPEC_JSON)
        spec_payload = build_spec_payload(variant="gpcr_core_cationic_weakbase_rescue_shadow_v11")
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_spec_csv(spec_path.with_suffix(".csv"), spec_payload["feature_rows"])
        write_spec_markdown(spec_path.with_suffix(".md"), spec_payload)
        _run(
            [
                sys.executable,
                "tools/product/replay_gpcr_residual_shadow_scores.py",
                "--input-scores-csv",
                str(refreshed_cache_csv),
                "--residual-prototype-spec-json",
                str(spec_path),
                "--out-scores-csv",
                str(v11_replay_scores_csv),
                "--out-summary-json",
                str(v11_replay_summary_json),
                "--out-summary-md",
                str(_resolve(v11_replay_summary_json).with_suffix(".md")),
            ]
        )
        from tools.gpcr_replay.build_gpcr_cationic_weakbase_frozen_shadow_replay_review import build_review

        v11_review_payload = build_review(
            input_scores_csv=v11_replay_scores_csv,
            input_summary_json=v11_replay_summary_json,
            label_csv=stage5_rows_csv,
            expected_complete_rows=int(subset_summary["subset_row_count"]),
        )
        _write_json(v11_review_out_json, v11_review_payload)
        v11_review_summary = v11_review_payload.get("summary", {})

    v16_gap_summary: dict[str, Any] = {}
    v16_gap_payload: dict[str, Any] = {}
    htr2a_summary: dict[str, Any] = {}
    oprm1_summary: dict[str, Any] = {}
    if not skip_v16_replay and not blockers:
        from tools.accounting.build_gpcr_residual_prototype_spec import build_payload as build_spec_payload

        v16_spec_path = _resolve(DEFAULT_V16_SPEC_JSON)
        v16_payload = build_spec_payload(variant="gpcr_core_false_support_discriminator_shadow_v16")
        v16_spec_path.write_text(json.dumps(v16_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _run(
            [
                sys.executable,
                "tools/product/replay_gpcr_residual_shadow_scores.py",
                "--input-scores-csv",
                str(refreshed_cache_csv if refreshed_cache_csv.exists() else adaptive_cache_csv),
                "--residual-prototype-spec-json",
                str(v16_spec_path),
                "--out-scores-csv",
                str(v16_replay_scores_csv),
                "--out-summary-json",
                str(v16_replay_summary_json),
                "--out-summary-md",
                str(_resolve(v16_replay_summary_json).with_suffix(".md")),
            ]
        )
        _run(
            [
                sys.executable,
                "tools/gpcr_replay/build_gpcr_frozen_pose_support_gap_packet.py",
                "--input-scores-csv",
                str(v16_replay_scores_csv),
                "--label-csv",
                str(stage5_rows_csv),
                "--out-json",
                str(v16_gap_json),
                "--out-csv",
                str(_resolve(v16_gap_json).with_suffix(".csv")),
                "--out-md",
                str(_resolve(v16_gap_json).with_suffix(".md")),
            ]
        )
        v16_gap_payload = _read_json(v16_gap_json)
        v16_gap_summary = v16_gap_payload.get("summary", {})

    if not skip_htr2a_replay and not blockers and _resolve(v16_replay_scores_csv).exists():
        htr2a_scores = _resolve(htr2a_json).with_name(
            _resolve(htr2a_json).stem.replace("_summary", "_scores") + ".csv"
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_htr2a_topology_support_shadow_replay.py",
                "--input-scores-csv",
                str(v16_replay_scores_csv),
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
                "--out-json",
                str(htr2a_json),
                "--out-scores-csv",
                str(htr2a_scores),
            ]
        )
        htr2a_summary = _read_json(htr2a_json).get("summary", {})

    if not skip_oprm1_replay and not blockers and _resolve(htr2a_json).exists():
        oprm1_scores = _resolve(oprm1_json).with_name(
            _resolve(oprm1_json).stem.replace("_summary", "_scores") + ".csv"
        )
        htr2a_scores = _resolve(htr2a_json).with_name(
            _resolve(htr2a_json).stem.replace("_summary", "_scores") + ".csv"
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_oprm1_topology_pose_shadow_replay.py",
                "--input-scores-csv",
                str(htr2a_scores),
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
                "--htr2a-replay-json",
                str(htr2a_json),
                "--out-json",
                str(oprm1_json),
                "--out-scores-csv",
                str(oprm1_scores),
            ]
        )
        oprm1_summary = _read_json(oprm1_json).get("summary", {})

    slice_status = _read_json("runs/gpcr_drd2_valid_anchor_discriminator_slice_replay_packet_current.json").get(
        "summary", {}
    )
    lanes = {
        "slice_v11_discriminator": {
            "status": _text(slice_status.get("status")),
            "drd2_positive_rank": slice_status.get("selected_slice_positive_rank"),
            "claim_evidence": False,
        },
        "adaptive_probe_cache": {
            "status": _text(adaptive_summary.get("status")),
            "feature_row_count": adaptive_summary.get("feature_row_count"),
            "false_valid_anchor_discriminator_row_count": _read_json(refreshed_cache_csv.with_suffix(".json"))
            .get("summary", {})
            .get("false_valid_anchor_discriminator_row_count"),
        },
        "atom_window_probe": {
            "status": _text(atom_window_summary.get("status")),
            "selected_row_count": atom_window_summary.get("selected_row_count"),
            "available_feature_count": atom_window_summary.get("available_feature_count"),
        },
        "v11_shadow_probe": _shadow_target_summary(v11_review_summary),
        "v16_gap_probe": _gap_target_summary(v16_gap_payload),
        "htr2a_topology_probe": {
            "status": _text(htr2a_summary.get("status")),
            "selected_weight": htr2a_summary.get("selected_weight"),
            "selected_target_summaries": htr2a_summary.get("selected_target_summaries"),
        },
        "oprm1_topology_probe": {
            "status": _text(oprm1_summary.get("status")),
            "selected_weight": oprm1_summary.get("selected_weight"),
            "selected_target_summaries": oprm1_summary.get("selected_target_summaries"),
        },
    }
    if v11_review_summary.get("status") != "frozen_shadow_green_claim_locked":
        blockers.extend(list(v11_review_summary.get("blockers") or []))
    if _text(v16_gap_summary.get("status")) not in {"", "blocked_pose_support_gap_claim_locked"}:
        pass
    elif v16_gap_summary:
        blockers.extend(
            [
                f"v16_gap:{blocker}"
                for blocker in (v16_gap_summary.get("blocker_counts") or {})
                if int((v16_gap_summary.get("blocker_counts") or {}).get(blocker) or 0) > 0
            ]
        )

    status = "ranking_quality_port_probe_complete_claim_locked"
    if blockers:
        status = "blocked_ranking_quality_port_probe_claim_locked"

    summary = {
        "packet_type": "gpcr_frozen_ranking_quality_port_probe_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "probe_subset": subset_summary,
        "lanes": lanes,
        "blockers": sorted(set(blockers)),
        "artifacts": {
            "probe_subset_csv": str(_resolve(probe_subset_csv)),
            "adaptive_cache_csv": str(_resolve(adaptive_cache_csv)),
            "atom_window_cache_csv": str(_resolve(atom_window_cache_csv)),
            "v11_review_json": str(_resolve(v11_review_out_json)),
            "v16_gap_json": str(_resolve(v16_gap_json)),
            "htr2a_json": str(_resolve(htr2a_json)),
            "oprm1_json": str(_resolve(oprm1_json)),
        },
        "next_required_step": (
            "Port probe lanes refreshed under claim lock. Slice green remains diagnostic-only; "
            "improve label-free atom-anchor contract and HTR2A/OPRM1 false-support separation before guarded apply."
            if status == "blocked_ranking_quality_port_probe_claim_locked"
            else "Unexpected green on subset probe; keep claim locked until full 40k CI-low/top20 gates clear."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Ranking Quality Port Probe Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- probe_subset_row_count: `{summary['probe_subset'].get('subset_row_count')}`",
        f"- claim_promotion_allowed: `false`",
        "",
        "## Lanes",
        "",
    ]
    for lane_id, lane in (summary.get("lanes") or {}).items():
        lines.append(f"### `{lane_id}`")
        for key, value in lane.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_full_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Ranking Quality Port Full Non-ADRB2 Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- expected_non_adrb2_row_count: `{summary.get('expected_non_adrb2_row_count')}`",
        f"- claim_promotion_allowed: `false`",
        "",
        "## Lanes",
        "",
    ]
    for lane_id, lane in (summary.get("lanes") or {}).items():
        lines.append(f"### `{lane_id}`")
        if isinstance(lane, dict):
            for key, value in lane.items():
                lines.append(f"- {key}: `{value}`")
        else:
            lines.append(f"- value: `{lane}`")
        lines.append("")
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch adaptive/atom-window frozen port probe plus HTR2A/OPRM1 topology comparison lanes."
    )
    parser.add_argument(
        "--mode",
        choices=["probe", "full-non-adrb2-adaptive"],
        default="probe",
        help="probe=268-row subset lanes; full-non-adrb2-adaptive=30k adaptive cache with discriminator refresh.",
    )
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--stage5-rows-csv", default=DEFAULT_STAGE5_ROWS_CSV)
    parser.add_argument("--slice-rows-csv", default=DEFAULT_SLICE_ROWS_CSV)
    parser.add_argument("--v11-review-json", default=DEFAULT_V11_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--full-adaptive-cache-csv", default=DEFAULT_FULL_ADAPTIVE_CACHE_CSV)
    parser.add_argument("--full-adaptive-cache-json", default=DEFAULT_FULL_ADAPTIVE_CACHE_JSON)
    parser.add_argument("--full-out-json", default=DEFAULT_FULL_OUT_JSON)
    parser.add_argument("--full-out-md", default=DEFAULT_FULL_OUT_MD)
    parser.add_argument("--skip-adaptive-cache", action="store_true")
    parser.add_argument("--skip-atom-window-cache", action="store_true")
    parser.add_argument("--skip-v11-replay", action="store_true")
    parser.add_argument("--skip-v16-replay", action="store_true")
    parser.add_argument("--skip-htr2a-replay", action="store_true")
    parser.add_argument("--skip-oprm1-replay", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "full-non-adrb2-adaptive":
        payload = build_full_non_adrb2_adaptive_packet(
            stage3_scores_csv=args.stage3_scores_csv,
            stage5_rows_csv=args.stage5_rows_csv,
            adaptive_cache_csv=args.full_adaptive_cache_csv,
            adaptive_cache_json=args.full_adaptive_cache_json,
            skip_adaptive_cache=args.skip_adaptive_cache,
            skip_v16_replay=args.skip_v16_replay,
            skip_htr2a_replay=args.skip_htr2a_replay,
            skip_oprm1_replay=args.skip_oprm1_replay,
        )
        _write_json(args.full_out_json, payload)
        _write_full_markdown(args.full_out_md, payload)
        print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
        return
    payload = build_packet(
        stage3_scores_csv=args.stage3_scores_csv,
        stage5_rows_csv=args.stage5_rows_csv,
        slice_rows_csv=args.slice_rows_csv,
        v11_review_json=args.v11_review_json,
        skip_adaptive_cache=args.skip_adaptive_cache,
        skip_atom_window_cache=args.skip_atom_window_cache,
        skip_v11_replay=args.skip_v11_replay,
        skip_v16_replay=args.skip_v16_replay,
        skip_htr2a_replay=args.skip_htr2a_replay,
        skip_oprm1_replay=args.skip_oprm1_replay,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
