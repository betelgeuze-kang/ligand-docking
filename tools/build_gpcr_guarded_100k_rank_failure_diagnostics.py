#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROWS_CSV = (
    "runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_STAGE3_CSV = (
    "runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_CI_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.md"

SCORE_COL = "binding_score_composite_v7"
TOP20_THRESHOLD = 0.20
CI_LOW_THRESHOLD = 0.45
NON_ADRB2_MARKERS = ("DRD", "HTR", "OPRM", "OPRD", "OPRK", "CHEMBL217", "CHEMBL224", "CHEMBL233")
FEATURE_COLUMNS = [
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "mean_min_distance_A",
    "contact_fraction",
    "stability_score",
]


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _is_non_adrb2(target: str) -> bool:
    upper = target.upper()
    return "ADRB2" not in upper and any(marker in upper for marker in NON_ADRB2_MARKERS)


def _rank_maps(rows: list[dict[str, Any]], score_col: str) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    scored = [
        (idx, row, _float(row.get(score_col)))
        for idx, row in enumerate(rows)
        if _float(row.get(score_col)) is not None
    ]
    scored.sort(key=lambda item: (item[2], _text(item[1].get("target")), _text(item[1].get("ligand_id"))))
    global_ranks = {
        (_text(row.get("target")), _text(row.get("ligand_id"))): rank
        for rank, (_idx, row, _score) in enumerate(scored, start=1)
    }
    within_ranks: dict[tuple[str, str], int] = {}
    by_target: dict[str, list[tuple[int, dict[str, Any], float | None]]] = {}
    for item in scored:
        by_target.setdefault(_text(item[1].get("target")), []).append(item)
    for target, target_rows in by_target.items():
        for rank, (_idx, row, _score) in enumerate(target_rows, start=1):
            within_ranks[(target, _text(row.get("ligand_id")))] = rank
    return global_ranks, within_ranks


def _stage3_feature_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key not in lookup:
            lookup[key] = row
    return lookup


def _feature_snapshot(row: dict[str, Any]) -> dict[str, float | None]:
    return {col: _float(row.get(col)) for col in FEATURE_COLUMNS if col in row}


def _ci_summary(ci_payload: dict[str, Any]) -> dict[str, Any]:
    summary = ci_payload.get("summary") if isinstance(ci_payload.get("summary"), dict) else {}
    return {
        "ranking_pr_auc": _float(summary.get("ranking_pr_auc")),
        "ranking_pr_auc_ci_low": _float(summary.get("ranking_pr_auc_ci_low")),
        "ranking_topk_hit_rate": _float(summary.get("ranking_topk_hit_rate")),
        "ranking_positive_count": _float(summary.get("ranking_positive_count")),
        "ci_low_threshold": _float(summary.get("threshold")) or CI_LOW_THRESHOLD,
        "top20_threshold": TOP20_THRESHOLD,
    }


def build_packet(
    *,
    rows_csv: str | Path | None = DEFAULT_ROWS_CSV,
    stage3_csv: str | Path | None = DEFAULT_STAGE3_CSV,
    ci_json: str | Path | None = DEFAULT_CI_JSON,
    readiness_json: str | Path | None = DEFAULT_READINESS_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows_path = _resolve(rows_csv)
    stage3_path = _resolve(stage3_csv)
    ci_path = _resolve(ci_json)
    readiness_path = _resolve(readiness_json)
    rows = _read_csv(rows_path)
    stage3_rows = _read_csv(stage3_path)
    ci_payload = _read_json(ci_path)
    readiness_payload = _read_json(readiness_path)
    stage3_lookup = _stage3_feature_lookup(stage3_rows)
    global_ranks, within_ranks = _rank_maps(rows, SCORE_COL)

    positives: list[dict[str, Any]] = []
    for row in rows:
        if not _is_positive(row):
            continue
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        key = (target, ligand_id)
        stage3 = stage3_lookup.get(key, {})
        positives.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "non_adrb2": _is_non_adrb2(target),
                "global_rank": global_ranks.get(key),
                "within_target_rank": within_ranks.get(key),
                "score": _float(row.get(SCORE_COL)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
                "features": _feature_snapshot(stage3),
            }
        )
    positives.sort(key=lambda row: (row.get("global_rank") or 10**12, row["target"], row["ligand_id"]))

    top_intrusions: list[dict[str, Any]] = []
    sorted_rows = sorted(
        [row for row in rows if _float(row.get(SCORE_COL)) is not None],
        key=lambda row: (_float(row.get(SCORE_COL)) or 0.0, _text(row.get("target")), _text(row.get("ligand_id"))),
    )
    for rank, row in enumerate(sorted_rows, start=1):
        if _is_positive(row):
            continue
        top_intrusions.append(
            {
                "rank": rank,
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "score": _float(row.get(SCORE_COL)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
            }
        )
        if len(top_intrusions) >= 12:
            break

    ci = _ci_summary(ci_payload)
    readiness_summary = readiness_payload.get("summary") if isinstance(readiness_payload.get("summary"), dict) else {}
    non_adrb2_tail = [
        row
        for row in positives
        if row["non_adrb2"] and ((row.get("global_rank") or 10**12) > 20 or (row.get("within_target_rank") or 10**12) > 20)
    ]
    blockers: list[str] = []
    if not rows:
        blockers.append("ranking_rows_missing")
    if ci["ranking_pr_auc_ci_low"] is None or ci["ranking_pr_auc_ci_low"] < ci["ci_low_threshold"]:
        blockers.append("ci_low_below_threshold")
    if ci["ranking_topk_hit_rate"] is None or ci["ranking_topk_hit_rate"] < ci["top20_threshold"]:
        blockers.append("top20_stability_not_green")
    if non_adrb2_tail:
        blockers.append("non_adrb2_positive_tail_rank")
    if top_intrusions:
        blockers.append("target_internal_decoy_intrusion")

    return {
        "packet_type": "gpcr_guarded_100k_rank_failure_diagnostics",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_artifacts": {
            "rows_csv": str(rows_path) if rows_path else None,
            "stage3_csv": str(stage3_path) if stage3_path else None,
            "ci_json": str(ci_path) if ci_path else None,
            "readiness_json": str(readiness_path) if readiness_path else None,
        },
        "summary": {
            "status": "blocked_ranking_quality" if blockers else "diagnostic_green",
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "positive_count": len(positives),
            "non_adrb2_positive_count": sum(1 for row in positives if row["non_adrb2"]),
            "non_adrb2_tail_positive_count": len(non_adrb2_tail),
            "worst_positive_global_rank": max((row.get("global_rank") or 0 for row in positives), default=None),
            "worst_positive_within_target_rank": max((row.get("within_target_rank") or 0 for row in positives), default=None),
            "ranking_pr_auc": ci["ranking_pr_auc"],
            "ranking_pr_auc_ci_low": ci["ranking_pr_auc_ci_low"],
            "ranking_topk_hit_rate": ci["ranking_topk_hit_rate"],
            "blocker_count": len(blockers),
            "blockers": blockers,
            "readiness_blockers": readiness_summary.get("blockers", []),
            "next_required_step": (
                "Build a claim-locked family-balanced scoring candidate that reduces donor-rich decoy intrusion "
                "and improves non-ADRB2 pose/energy support before any new guarded 100k claim evidence."
            ),
        },
        "positive_rank_diagnostics": positives,
        "top_decoy_intrusions": top_intrusions,
        "claim_boundary": {
            "diagnostic_only_not_claim_authorizing": True,
            "claim_promotion_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Guarded 100k Rank Failure Diagnostics",
        "",
        "## Summary",
        f"- status: `{summary['status']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- non_adrb2_positive_count: `{summary['non_adrb2_positive_count']}`",
        f"- non_adrb2_tail_positive_count: `{summary['non_adrb2_tail_positive_count']}`",
        f"- ranking_pr_auc_ci_low: `{summary['ranking_pr_auc_ci_low']}`",
        f"- ranking_topk_hit_rate: `{summary['ranking_topk_hit_rate']}`",
        f"- blockers: `{', '.join(summary['blockers'])}`",
        "",
        "## Positive Ranks",
        "",
        "| global_rank | within_target_rank | target | ligand_id | score | mean_min_distance_A |",
        "| ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for row in payload.get("positive_rank_diagnostics", []):
        lines.append(
            "| {global_rank} | {within_target_rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                global_rank=row.get("global_rank"),
                within_target_rank=row.get("within_target_rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    lines.extend(
        [
            "",
            "## Top Decoy Intrusions",
            "",
            "| rank | target | ligand_id | score | mean_min_distance_A |",
            "| ---: | --- | --- | ---: | ---: |",
        ]
    )
    for row in payload.get("top_decoy_intrusions", []):
        lines.append(
            "| {rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                rank=row.get("rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def write_outputs(
    *,
    rows_csv: str | Path | None,
    stage3_csv: str | Path | None,
    ci_json: str | Path | None,
    readiness_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
    )
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build diagnostic packet for GPCR guarded 100k rank failure.")
    parser.add_argument("--rows-csv", default=DEFAULT_ROWS_CSV)
    parser.add_argument("--stage3-csv", default=DEFAULT_STAGE3_CSV)
    parser.add_argument("--ci-json", default=DEFAULT_CI_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        rows_csv=args.rows_csv,
        stage3_csv=args.stage3_csv,
        ci_json=args.ci_json,
        readiness_json=args.readiness_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
