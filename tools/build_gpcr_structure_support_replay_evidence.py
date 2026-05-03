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
DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-02_mismatch_contact_apply_safesync_r3_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_RANKING_ROWS_CSV = (
    "runs/external_validation_2026-05-02_mismatch_contact_apply_safesync_r3_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_core_structure_support_rescore_v1_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_structure_support_rescore_replay_evidence_current.json"
DEFAULT_OUT_MD = "runs/gpcr_structure_support_rescore_replay_evidence_current.md"


def _resolve(path_like: str | Path) -> Path:
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


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _is_positive(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _feature_values(rows: list[dict[str, Any]], feature: str) -> list[float]:
    return [_safe_float(row.get(feature), 0.0) for row in rows]


def _z_values(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(variance)
    if std <= 1.0e-12:
        std = 1.0
    return [(value - mean) / std for value in values]


def _linear_terms(spec: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    prototype = spec.get("prototype") if isinstance(spec.get("prototype"), dict) else {}
    linear = prototype.get("linear_rescore") if isinstance(prototype.get("linear_rescore"), dict) else {}
    if not linear.get("enabled"):
        raise ValueError("spec prototype.linear_rescore.enabled must be true")
    if str(linear.get("combine_mode", "replace") or "replace").strip().lower() != "replace":
        raise ValueError("only replace-mode replay evidence is supported")
    terms = linear.get("terms")
    if not isinstance(terms, list) or not terms:
        raise ValueError("spec prototype.linear_rescore.terms must be non-empty")
    return _safe_float(linear.get("intercept"), 0.0), [dict(term) for term in terms if isinstance(term, dict)]


def _score_rows(rows: list[dict[str, Any]], *, intercept: float, terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    z_cache: dict[str, list[float]] = {}
    scores = [float(intercept) for _ in rows]
    applied_terms: list[str] = []
    for term in terms:
        feature = str(term.get("feature", "") or "").strip()
        if not feature:
            continue
        weight = _safe_float(term.get("weight"), 0.0)
        if feature.startswith("z_"):
            source = feature[2:]
            if feature not in z_cache:
                z_cache[feature] = _z_values(_feature_values(rows, source))
            values = z_cache[feature]
        else:
            values = _feature_values(rows, feature)
        for index, value in enumerate(values):
            scores[index] += weight * value
        applied_terms.append(feature)

    out: list[dict[str, Any]] = []
    for row, score in zip(rows, scores):
        out.append({**row, "structure_support_replay_score": float(score)})
    return out


def _average_precision(positive_ranks: list[int]) -> float:
    if not positive_ranks:
        return 0.0
    return float(sum((idx + 1) / rank for idx, rank in enumerate(positive_ranks)) / len(positive_ranks))


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Structure-Support Replay Evidence",
        "",
        f"- status: `{summary['status']}`",
        f"- pr_auc: `{summary['pr_auc']}`",
        f"- topk_hit_rate: `{summary['topk_hit_rate']}`",
        f"- positive_ranks: `{summary['positive_ranks']}`",
        f"- claim_safe_assertion_allowed: `{summary['claim_safe_assertion_allowed']}`",
        f"- claim_text_locked_until_full_100k_gate_green: `{summary['claim_text_locked_until_full_100k_gate_green']}`",
        "",
        "## Top Rows",
        "",
        "| rank | ligand_id | is_binder | score |",
        "| --- | --- | --- | ---: |",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"| {row['rank']} | `{row['ligand_id']}` | `{row['is_binder']}` | {row['structure_support_replay_score']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(
    *,
    stage3_scores_csv: str | Path,
    ranking_rows_csv: str | Path,
    spec_json: str | Path,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_md: str | Path = DEFAULT_OUT_MD,
    topk_k: int = 20,
    pr_auc_min: float = 0.55,
    topk_hit_rate_min: float = 0.20,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    stage3_path = _resolve(stage3_scores_csv)
    ranking_path = _resolve(ranking_rows_csv)
    spec_path = _resolve(spec_json)
    spec = _read_json(spec_path)
    labels = {
        str(row.get("ligand_id", "") or "").strip(): row
        for row in _read_csv(ranking_path)
        if str(row.get("ligand_id", "") or "").strip()
    }
    merged_rows: list[dict[str, Any]] = []
    for row in _read_csv(stage3_path):
        ligand_id = str(row.get("ligand_id", "") or "").strip()
        label = labels.get(ligand_id, {})
        if not label:
            continue
        merged_rows.append(
            {
                **row,
                "is_binder": "1" if _is_positive(label.get("is_binder")) else "0",
                "role": str(label.get("role", "") or ""),
            }
        )

    intercept, terms = _linear_terms(spec)
    scored_rows = _score_rows(merged_rows, intercept=intercept, terms=terms)
    ranked = sorted(
        enumerate(scored_rows),
        key=lambda item: (_safe_float(item[1].get("structure_support_replay_score")), item[0]),
    )
    positive_ranks: list[int] = []
    topk_positive_count = 0
    output_rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(ranked, start=1):
        is_binder = _is_positive(row.get("is_binder"))
        if is_binder:
            positive_ranks.append(rank)
            if rank <= int(topk_k):
                topk_positive_count += 1
        if rank <= 100:
            output_rows.append(
                {
                    "rank": int(rank),
                    "ligand_id": str(row.get("ligand_id", "") or ""),
                    "is_binder": bool(is_binder),
                    "role": str(row.get("role", "") or ""),
                    "structure_support_replay_score": _safe_float(row.get("structure_support_replay_score")),
                }
            )

    pr_auc = _average_precision(positive_ranks)
    topk_hit_rate = float(topk_positive_count / max(int(topk_k), 1))
    gate_pass = bool(pr_auc >= float(pr_auc_min) and topk_hit_rate >= float(topk_hit_rate_min))
    constraints = spec.get("prototype", {}).get("constraints", {}) if isinstance(spec.get("prototype"), dict) else {}
    gate = constraints.get("structure_support_gate", {}) if isinstance(constraints, dict) else {}
    if generated_at_local is None:
        generated_at_local = dt.datetime.now().astimezone().replace(microsecond=0).isoformat(timespec="seconds")
    payload = {
        "generated_at_local": generated_at_local,
        "summary": {
            "status": "replay_gate_passed" if gate_pass else "replay_gate_failed",
            "stage3_scores_csv": _rel_or_abs(stage3_path),
            "ranking_rows_csv": _rel_or_abs(ranking_path),
            "spec_json": _rel_or_abs(spec_path),
            "row_count": int(len(merged_rows)),
            "positive_count": int(len(positive_ranks)),
            "pr_auc": float(pr_auc),
            "pr_auc_min": float(pr_auc_min),
            "topk_k": int(topk_k),
            "topk_hit_rate": float(topk_hit_rate),
            "topk_hit_rate_min": float(topk_hit_rate_min),
            "positive_ranks": positive_ranks,
            "claim_safe_assertion_allowed": False,
            "claim_text_locked_until_full_100k_gate_green": not bool(gate.get("full_100k_gate_green", False)),
            "full_100k_gate_green": bool(gate.get("full_100k_gate_green", False)),
            "evidence_role": "comparison_replay_only",
        },
        "linear_rescore": {
            "intercept": float(intercept),
            "terms": terms,
        },
        "rows": output_rows,
    }
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    _write_json(out_json_path, payload)
    _write_markdown(out_md_path, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build claim-locked GPCR structure-support replay evidence.")
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--ranking-rows-csv", default=DEFAULT_RANKING_ROWS_CSV)
    parser.add_argument("--spec-json", default=DEFAULT_SPEC_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--topk-k", type=int, default=20)
    parser.add_argument("--pr-auc-min", type=float, default=0.55)
    parser.add_argument("--topk-hit-rate-min", type=float, default=0.20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        stage3_scores_csv=args.stage3_scores_csv,
        ranking_rows_csv=args.ranking_rows_csv,
        spec_json=args.spec_json,
        out_json=args.out_json,
        out_md=args.out_md,
        topk_k=args.topk_k,
        pr_auc_min=args.pr_auc_min,
        topk_hit_rate_min=args.topk_hit_rate_min,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
