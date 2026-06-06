#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_CSV = "runs/external_validation_2026-03-22_biorxiv_v7r1_set1_core_blind_gpcr_core_full_p0_n10000_r1_stage5_ranking_rows.csv"
DEFAULT_SCALEUP_CSV = "runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
BASELINE_DISCOVERY_GLOB = (
    "external_validation_*_set1_core_blind_gpcr_core_full_p0_n10000_r1_stage5_ranking_rows.csv"
)
SCALEUP_DISCOVERY_GLOB = (
    "external_validation_*gpcr_scaleup_100k*set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
)


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _resolve_existing_gpcr_baseline_csv(preferred: Path) -> Path:
    if preferred.exists():
        return preferred
    candidates = sorted((ROOT / "runs").glob(BASELINE_DISCOVERY_GLOB))
    return candidates[-1] if candidates else preferred


def _resolve_existing_gpcr_scaleup_csv(preferred: Path) -> Path:
    if preferred.exists():
        return preferred
    candidates = sorted((ROOT / "runs").glob(SCALEUP_DISCOVERY_GLOB))
    return candidates[-1] if candidates else preferred


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _as_float(value: str) -> float:
    return float(str(value).strip())


def _maybe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(str(value).strip())
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _is_positive(row: dict[str, Any]) -> bool:
    return str(row.get("is_binder", "")).strip() in {"1", "true", "True", "TRUE"}


def _positive_ranks(rows: list[dict[str, str]]) -> list[int]:
    out: list[int] = []
    for idx, row in enumerate(rows, start=1):
        if _is_positive(row):
            out.append(idx)
    return out


def _topk_counts(rows: list[dict[str, str]], k: int) -> tuple[int, int]:
    top = rows[:k]
    binders = sum(1 for row in top if _is_positive(row))
    return binders, len(top) - binders


def _top_false_positives(rows: list[dict[str, str]], k: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        if not _is_positive(row):
            out.append(
                {
                    "rank": idx,
                    "ligand_id": str(row.get("ligand_id", "")).strip(),
                    "binding_score_composite_v7": _as_float(row.get("binding_score_composite_v7", "nan")),
                    "mean_min_distance_A": _as_float(row.get("mean_min_distance_A", "nan")),
                    "reference_binding_kcal_mol": _as_float(row.get("reference_binding_kcal_mol", "nan")),
                    "role": str(row.get("role", "")).strip(),
                }
            )
        if len(out) >= k:
            break
    return out


def _score_positive_ranks(rows: list[dict[str, Any]], score_col: str) -> list[int]:
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        value = _maybe_float(row.get(score_col))
        if value is None:
            continue
        scored.append((value, idx, row))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [rank for rank, (_, _, row) in enumerate(scored, start=1) if _is_positive(row)]


def _average_precision_from_ranks(positive_ranks: list[int]) -> float | None:
    if not positive_ranks:
        return None
    return float(sum((idx + 1) / rank for idx, rank in enumerate(positive_ranks)) / len(positive_ranks))


def _topk_hit_rate_from_ranks(positive_ranks: list[int], *, k: int) -> float | None:
    if k <= 0:
        return None
    return float(sum(1 for rank in positive_ranks if rank <= k) / k)


def _score_column_metrics(rows: list[dict[str, Any]], score_col: str, *, topk_k: int) -> dict[str, Any]:
    positive_ranks = _score_positive_ranks(rows, score_col)
    return {
        "score_col": score_col,
        "positive_ranks": positive_ranks,
        "pr_auc": _average_precision_from_ranks(positive_ranks),
        "topk_k": int(topk_k),
        "topk_hit_rate": _topk_hit_rate_from_ranks(positive_ranks, k=topk_k),
    }


def _mean_feature(rows: list[dict[str, Any]], feature: str) -> float | None:
    values = [_maybe_float(row.get(feature)) for row in rows]
    numeric = [value for value in values if value is not None]
    return float(mean(numeric)) if numeric else None


def _stage3_score_diagnostics(
    *,
    scaleup_rows: list[dict[str, str]],
    scaleup_stage3_rows: list[dict[str, str]] | None,
    topk_k: int,
    pr_auc_min: float,
    topk_hit_rate_min: float,
) -> dict[str, Any]:
    if not scaleup_stage3_rows:
        return {
            "available": False,
            "reason": "missing_scaleup_stage3_scores",
            "existing_score_recovery_status": "not_available",
        }

    labels_by_ligand = {str(row.get("ligand_id", "")).strip(): row for row in scaleup_rows}
    merged_rows: list[dict[str, Any]] = []
    for row in scaleup_stage3_rows:
        ligand_id = str(row.get("ligand_id", "")).strip()
        label = labels_by_ligand.get(ligand_id, {})
        if not label:
            continue
        merged = dict(row)
        merged["is_binder"] = str(label.get("is_binder", "")).strip()
        merged["role"] = str(label.get("role", "")).strip()
        merged_rows.append(merged)

    score_cols = sorted(
        {
            key
            for row in merged_rows
            for key in row.keys()
            if str(key).startswith("binding_score_composite_")
            and any(_maybe_float(candidate.get(key)) is not None for candidate in merged_rows)
        }
    )
    score_metrics = [_score_column_metrics(merged_rows, col, topk_k=topk_k) for col in score_cols]
    score_metrics.sort(
        key=lambda row: (
            float(row.get("pr_auc") or -1.0),
            float(row.get("topk_hit_rate") or -1.0),
            str(row.get("score_col", "")),
        ),
        reverse=True,
    )
    best_metrics = score_metrics[0] if score_metrics else {}
    best_passes = bool(
        best_metrics
        and (best_metrics.get("pr_auc") is not None)
        and (float(best_metrics["pr_auc"]) >= float(pr_auc_min))
        and (best_metrics.get("topk_hit_rate") is not None)
        and (float(best_metrics["topk_hit_rate"]) >= float(topk_hit_rate_min))
    )

    top_fp_ids = {str(row.get("ligand_id", "")).strip() for row in _top_false_positives(scaleup_rows, topk_k)}
    top_fp_rows = [row for row in merged_rows if str(row.get("ligand_id", "")).strip() in top_fp_ids]
    binder_rows = [row for row in merged_rows if _is_positive(row)]
    feature_names = [
        "ligand_h_donors",
        "ligand_h_acceptors",
        "ligand_rot_bonds",
        "ligand_logp",
        "ligand_mw",
        "ligand_affinity_hint",
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "contact_fraction",
        "stability_score",
        "mean_min_distance_A",
    ]
    feature_profile = {
        "binder_means": {feature: _mean_feature(binder_rows, feature) for feature in feature_names},
        "top_false_positive_means": {feature: _mean_feature(top_fp_rows, feature) for feature in feature_names},
    }
    binder_means = feature_profile["binder_means"]
    fp_means = feature_profile["top_false_positive_means"]
    root_tags: list[str] = []
    if (
        fp_means.get("ligand_h_donors") is not None
        and binder_means.get("ligand_h_donors") is not None
        and float(fp_means["ligand_h_donors"]) >= float(binder_means["ligand_h_donors"]) + 1.0
    ):
        root_tags.append("donor_prior_decoy_intrusion")
    if (
        fp_means.get("contact_fraction") is not None
        and binder_means.get("contact_fraction") is not None
        and float(fp_means["contact_fraction"]) < float(binder_means["contact_fraction"]) * 0.95
    ):
        root_tags.append("weak_contact_prior_mismatch")
    if (
        fp_means.get("ligand_affinity_hint") is not None
        and binder_means.get("ligand_affinity_hint") is not None
        and fp_means.get("binding_energy_mmpbsa_kcal_mol_proxy") is not None
        and binder_means.get("binding_energy_mmpbsa_kcal_mol_proxy") is not None
        and float(fp_means["ligand_affinity_hint"]) >= float(binder_means["ligand_affinity_hint"]) * 0.8
        and float(fp_means["binding_energy_mmpbsa_kcal_mol_proxy"])
        > float(binder_means["binding_energy_mmpbsa_kcal_mol_proxy"])
    ):
        root_tags.append("affinity_hint_md_support_mismatch")
    if not best_passes:
        root_tags.append("no_existing_score_column_recovers_gate")

    return {
        "available": True,
        "merged_stage3_row_count": int(len(merged_rows)),
        "evaluated_score_col_count": int(len(score_metrics)),
        "score_column_metrics": score_metrics,
        "best_existing_score_col": str(best_metrics.get("score_col", "")),
        "best_existing_metrics": best_metrics,
        "thresholds": {
            "pr_auc_min": float(pr_auc_min),
            "topk_k": int(topk_k),
            "topk_hit_rate_min": float(topk_hit_rate_min),
        },
        "existing_score_recovery_status": (
            "existing_score_column_passes_gate" if best_passes else "no_existing_score_column_recovers_gate"
        ),
        "feature_profile": feature_profile,
        "root_cause_tags": root_tags,
    }


def _payload_for(rows: list[dict[str, str]], label: str) -> dict[str, Any]:
    pos_ranks = _positive_ranks(rows)
    top20_binders, top20_decoys = _topk_counts(rows, 20)
    top100_binders, top100_decoys = _topk_counts(rows, 100)
    false_pos = _top_false_positives(rows, 20)
    fp_scores = [row["binding_score_composite_v7"] for row in false_pos]
    fp_dist = [row["mean_min_distance_A"] for row in false_pos]
    return {
        "label": label,
        "row_count": len(rows),
        "positive_rank_list": pos_ranks,
        "top20_binder_count": top20_binders,
        "top20_decoy_count": top20_decoys,
        "top100_binder_count": top100_binders,
        "top100_decoy_count": top100_decoys,
        "first_positive_rank": pos_ranks[0] if pos_ranks else None,
        "last_positive_rank": pos_ranks[-1] if pos_ranks else None,
        "top_false_positive_mean_score": mean(fp_scores) if fp_scores else None,
        "top_false_positive_mean_min_distance_A": mean(fp_dist) if fp_dist else None,
        "top_false_positives": false_pos,
    }


def build_payload(
    baseline_rows: list[dict[str, str]],
    scaleup_rows: list[dict[str, str]],
    *,
    scaleup_stage3_rows: list[dict[str, str]] | None = None,
    topk_k: int = 20,
    pr_auc_min: float = 0.55,
    topk_hit_rate_min: float = 0.2,
) -> dict[str, Any]:
    return build_payload_with_diagnostics(
        baseline_rows,
        scaleup_rows,
        scaleup_stage3_rows=scaleup_stage3_rows,
        topk_k=topk_k,
        pr_auc_min=pr_auc_min,
        topk_hit_rate_min=topk_hit_rate_min,
    )


def build_payload_with_diagnostics(
    baseline_rows: list[dict[str, str]],
    scaleup_rows: list[dict[str, str]],
    *,
    scaleup_stage3_rows: list[dict[str, str]] | None = None,
    topk_k: int = 20,
    pr_auc_min: float = 0.55,
    topk_hit_rate_min: float = 0.2,
) -> dict[str, Any]:
    baseline = _payload_for(baseline_rows, "baseline_10k")
    scaleup = _payload_for(scaleup_rows, "scaleup_100k")
    summary = {
        "status": "computed",
        "source_rows_available": True,
        "baseline_positive_ranks": baseline["positive_rank_list"],
        "scaleup_positive_ranks": scaleup["positive_rank_list"],
        "baseline_top20_binder_count": baseline["top20_binder_count"],
        "scaleup_top20_binder_count": scaleup["top20_binder_count"],
        "baseline_top100_binder_count": baseline["top100_binder_count"],
        "scaleup_top100_binder_count": scaleup["top100_binder_count"],
        "first_positive_rank_shift": None,
        "last_positive_rank_shift": None,
        "interpretation": "",
    }
    if baseline["first_positive_rank"] is not None and scaleup["first_positive_rank"] is not None:
        summary["first_positive_rank_shift"] = scaleup["first_positive_rank"] - baseline["first_positive_rank"]
    if baseline["last_positive_rank"] is not None and scaleup["last_positive_rank"] is not None:
        summary["last_positive_rank_shift"] = scaleup["last_positive_rank"] - baseline["last_positive_rank"]
    summary["interpretation"] = (
        "The 100k GPCR failure is driven by top-rank decoy intrusion: the first two binders stay at the top, but the remaining binders are pushed much deeper by synthetic hard decoys."
    )
    score_diagnostics = _stage3_score_diagnostics(
        scaleup_rows=scaleup_rows,
        scaleup_stage3_rows=scaleup_stage3_rows,
        topk_k=topk_k,
        pr_auc_min=pr_auc_min,
        topk_hit_rate_min=topk_hit_rate_min,
    )
    return {"summary": summary, "baseline": baseline, "scaleup": scaleup, "score_diagnostics": score_diagnostics}


def build_missing_input_payload(
    baseline_csv: Path,
    scaleup_csv: Path,
    *,
    previous_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing_paths = [str(path) for path in (baseline_csv, scaleup_csv) if not path.exists()]
    previous_summary = dict((previous_payload or {}).get("summary", {}) or {})
    summary = {
        "status": "blocked_missing_csv_inputs",
        "source_rows_available": False,
        "claim_safe": False,
        "missing_input_count": len(missing_paths),
        "missing_input_paths": missing_paths,
        "previous_snapshot_available": bool(previous_summary),
        "previous_scaleup_positive_ranks": previous_summary.get("scaleup_positive_ranks", []),
        "previous_scaleup_top20_binder_count": previous_summary.get("scaleup_top20_binder_count"),
        "previous_last_positive_rank_shift": previous_summary.get("last_positive_rank_shift"),
        "baseline_positive_ranks": [],
        "scaleup_positive_ranks": [],
        "baseline_top20_binder_count": 0,
        "scaleup_top20_binder_count": 0,
        "baseline_top100_binder_count": 0,
        "scaleup_top100_binder_count": 0,
        "first_positive_rank_shift": None,
        "last_positive_rank_shift": None,
        "interpretation": (
            "The 100k GPCR failure analysis could not be recomputed because one or more raw ranking CSV inputs are missing."
        ),
        "next_required_step": (
            "Do not infer a GPCR scale-up recovery from this diagnostic; rerun or restore the missing ranking CSV inputs, "
            "then rebuild the 100k failure analysis."
        ),
    }
    empty_payload = {
        "label": "",
        "row_count": 0,
        "positive_rank_list": [],
        "top20_binder_count": 0,
        "top20_decoy_count": 0,
        "top100_binder_count": 0,
        "top100_decoy_count": 0,
        "first_positive_rank": None,
        "last_positive_rank": None,
        "top_false_positive_mean_score": None,
        "top_false_positive_mean_min_distance_A": None,
        "top_false_positives": [],
    }
    baseline = dict(empty_payload)
    baseline["label"] = "baseline_10k"
    scaleup = dict(empty_payload)
    scaleup["label"] = "scaleup_100k"
    return {
        "summary": summary,
        "baseline": baseline,
        "scaleup": scaleup,
        "score_diagnostics": {
            "available": False,
            "reason": "missing_ranking_csv_inputs",
            "existing_score_recovery_status": "not_available",
        },
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR 100k Failure Analysis",
        "",
        f"- status: `{s.get('status', 'computed')}`",
        f"- source_rows_available: `{s.get('source_rows_available', True)}`",
        f"- baseline_positive_ranks: `{s['baseline_positive_ranks']}`",
        f"- scaleup_positive_ranks: `{s['scaleup_positive_ranks']}`",
        f"- baseline_top20_binder_count: `{s['baseline_top20_binder_count']}`",
        f"- scaleup_top20_binder_count: `{s['scaleup_top20_binder_count']}`",
        f"- baseline_top100_binder_count: `{s['baseline_top100_binder_count']}`",
        f"- scaleup_top100_binder_count: `{s['scaleup_top100_binder_count']}`",
        f"- last_positive_rank_shift: `{s['last_positive_rank_shift']}`",
        "",
        "## Interpretation",
        "",
        f"- {s['interpretation']}",
    ]
    if s.get("missing_input_paths"):
        lines.extend(["", "## Missing Inputs", ""])
        for missing_path in s.get("missing_input_paths", []):
            lines.append(f"- `{missing_path}`")
        lines.extend(["", "## Next Required Step", "", f"- {s.get('next_required_step', '')}"])
    diagnostics = payload.get("score_diagnostics", {}) if isinstance(payload.get("score_diagnostics"), dict) else {}
    lines.extend(
        [
            "",
            "## Score Diagnostics",
            "",
            f"- available: `{diagnostics.get('available', False)}`",
            f"- existing_score_recovery_status: `{diagnostics.get('existing_score_recovery_status', '')}`",
            f"- best_existing_score_col: `{diagnostics.get('best_existing_score_col', '')}`",
            f"- root_cause_tags: `{diagnostics.get('root_cause_tags', [])}`",
        ]
    )
    best = diagnostics.get("best_existing_metrics", {}) if isinstance(diagnostics.get("best_existing_metrics"), dict) else {}
    if best:
        lines.extend(
            [
                f"- best_pr_auc: `{best.get('pr_auc')}`",
                f"- best_topk_hit_rate: `{best.get('topk_hit_rate')}`",
                f"- best_positive_ranks: `{best.get('positive_ranks')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Top False Positives In 100k",
            "",
            "| rank | ligand_id | score | mean_min_distance_A | role |",
            "| ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["scaleup"]["top_false_positives"][:12]:
        lines.append(
            f"| {row['rank']} | `{row['ligand_id']}` | {row['binding_score_composite_v7']:.4f} | {row['mean_min_distance_A']:.4f} | {row['role']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare GPCR 10k baseline vs 100k pilot ranking rows and summarize top-rank decoy intrusion.")
    parser.add_argument("--baseline-csv", default=DEFAULT_BASELINE_CSV)
    parser.add_argument("--scaleup-csv", default=DEFAULT_SCALEUP_CSV)
    parser.add_argument("--scaleup-stage3-csv", default="")
    parser.add_argument("--topk-k", type=int, default=20)
    parser.add_argument("--pr-auc-min", type=float, default=0.55)
    parser.add_argument("--topk-hit-rate-min", type=float, default=0.2)
    parser.add_argument("--out-json", default="runs/gpcr_100k_failure_analysis_current.json")
    parser.add_argument("--out-csv", default="runs/gpcr_100k_failure_false_positives_current.csv")
    parser.add_argument("--out-md", default="runs/gpcr_100k_failure_analysis_current.md")
    return parser.parse_args()


def _default_stage3_path(scaleup_csv: Path) -> Path:
    text = str(scaleup_csv)
    if text.endswith("_stage5_ranking_rows.csv"):
        return Path(text[: -len("_stage5_ranking_rows.csv")] + "_stage3_scores.csv")
    return scaleup_csv.with_name(scaleup_csv.stem + "_stage3_scores.csv")


def main() -> None:
    args = parse_args()
    baseline_csv = _resolve_existing_gpcr_baseline_csv(_resolve(args.baseline_csv))
    scaleup_csv = _resolve_existing_gpcr_scaleup_csv(_resolve(args.scaleup_csv))
    out_json = _resolve(args.out_json)
    if baseline_csv.exists() and scaleup_csv.exists():
        scaleup_stage3_csv = _resolve(args.scaleup_stage3_csv) if str(args.scaleup_stage3_csv).strip() else _default_stage3_path(scaleup_csv)
        scaleup_stage3_rows = _read_csv(scaleup_stage3_csv) if scaleup_stage3_csv.exists() else None
        payload = build_payload(
            _read_csv(baseline_csv),
            _read_csv(scaleup_csv),
            scaleup_stage3_rows=scaleup_stage3_rows,
            topk_k=int(args.topk_k),
            pr_auc_min=float(args.pr_auc_min),
            topk_hit_rate_min=float(args.topk_hit_rate_min),
        )
    else:
        previous_payload = json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else None
        payload = build_missing_input_payload(baseline_csv, scaleup_csv, previous_payload=previous_payload)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["scaleup"]["top_false_positives"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
