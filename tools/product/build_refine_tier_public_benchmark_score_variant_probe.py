#!/usr/bin/env python3
"""Read-only R9 score-variant probe for public-benchmark rank support."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    _bootstrap_spearman_interval,
    _spearman_values,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_FILL_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_EXISTING_MATERIALIZATION_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_score_variant_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_score_variant_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_score_variant_probe_current.md"

CLAIM_BOUNDARY = (
    "R9 score-variant probe only; it reads local existing/candidate-fill metric details and evaluates "
    "predeclared scoring variants against the current public-benchmark preview. It does not rewrite "
    "candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical "
    "intake, run docking/MD, download, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_details(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _format_float(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.12g}"


def _details_from_source(path_like: str | Path, *, root: Path) -> dict[str, Any]:
    payload, present = _read_json(path_like, root=root)
    if not present:
        return {}
    details = payload.get("details")
    return details if isinstance(details, dict) else {}


def _feature_row(
    *,
    source: str,
    work_order_id: str,
    target_id: str,
    pose_id: str,
    split: str,
    proxy: float,
    reference: float,
    details: dict[str, Any],
    detail_source: str,
) -> dict[str, Any]:
    contact_count = _float(details.get("contact_count")) or 0.0
    ligand_contact_atom_count = _float(details.get("ligand_contact_atom_count")) or 0.0
    pose_atom_count = _float(details.get("pose_atom_count")) or 0.0
    min_distance_a = _float(details.get("min_distance_a"))
    contact_per_atom = contact_count / pose_atom_count if pose_atom_count > 0 else 0.0
    contact_per_contact_atom = contact_count / ligand_contact_atom_count if ligand_contact_atom_count > 0 else 0.0
    contact_sqrt_norm = contact_count / math.sqrt(pose_atom_count) if pose_atom_count > 0 else 0.0
    return {
        "source": source,
        "work_order_id": work_order_id,
        "target_id": target_id,
        "pose_id": pose_id,
        "split": split or "unknown",
        "baseline_proxy": float(proxy),
        "reference": float(reference),
        "detail_source": detail_source,
        "feature_detail_present": bool(details),
        "feature_complete": bool(contact_count > 0 and pose_atom_count > 0),
        "contact_count": contact_count,
        "ligand_contact_atom_count": ligand_contact_atom_count,
        "pose_atom_count": pose_atom_count,
        "min_distance_a": min_distance_a,
        "contact_per_atom": contact_per_atom,
        "contact_per_contact_atom": contact_per_contact_atom,
        "contact_sqrt_norm": contact_sqrt_norm,
        "log_contact_per_atom": math.log1p(contact_per_atom),
    }


def _existing_feature_rows(path_like: str | Path, *, root: Path) -> list[dict[str, Any]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            proxy = _float(row.get("internal_refine_proxy_score"))
            reference = _float(row.get("deltaG_experimental_kcal_mol"))
            source_path = _text(row.get("internal_deltaG_source_artifact"))
            if proxy is None or reference is None:
                continue
            details = _details_from_source(source_path, root=root) if source_path else {}
            rows.append(
                _feature_row(
                    source="existing_materialized",
                    work_order_id=_text(row.get("work_order_id")),
                    target_id=_text(row.get("target_id")),
                    pose_id=_text(row.get("pose_id")),
                    split=_text(row.get("split")),
                    proxy=float(proxy),
                    reference=float(reference),
                    details=details,
                    detail_source="existing_internal_deltaG_source_artifact" if details else "missing",
                )
            )
    return rows


def _candidate_detail_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    detail_rows = payload.get("rows", [])
    if not isinstance(detail_rows, list):
        return {}
    details_by_pose: dict[tuple[str, str], dict[str, Any]] = {}
    for row in detail_rows:
        if not isinstance(row, dict):
            continue
        if row.get("candidate_status") != "pass" or row.get("metric_name") != "internal_deltaG":
            continue
        target_id = _text(row.get("target_id"))
        pose_id = _text(row.get("pose_id"))
        details = _parse_details(row.get("details_json"))
        if not details:
            details = _parse_details(row.get("details"))
        if target_id and pose_id and details:
            details_by_pose[(target_id, pose_id)] = details
    return details_by_pose


def _candidate_feature_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("candidate_pairs", [])
    if not isinstance(rows, list):
        return []
    details_by_pose = _candidate_detail_index(payload)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("candidate_status") != "pass":
            continue
        proxy = _float(row.get("candidate_refine_proxy_score"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        details = _parse_details(row.get("details_json"))
        detail_source = "candidate_pair_details_json" if details else "missing"
        if not details:
            details = _parse_details(row.get("details"))
            detail_source = "candidate_pair_details" if details else "missing"
        if not details:
            details = details_by_pose.get((_text(row.get("target_id")), _text(row.get("pose_id"))), {})
            detail_source = "candidate_rows_internal_deltaG" if details else "missing"
        out.append(
            _feature_row(
                source="candidate_fill_preview",
                work_order_id=_text(row.get("work_order_id")),
                target_id=_text(row.get("target_id")),
                pose_id=_text(row.get("pose_id")),
                split=_text(row.get("split")),
                proxy=float(proxy),
                reference=float(reference),
                details=details,
                detail_source=detail_source,
            )
        )
    return out


def _score(row: dict[str, Any], *, family: str, alpha: float = 0.0, beta: float = 0.0) -> float:
    baseline = float(row["baseline_proxy"])
    contact_per_atom = float(row["contact_per_atom"])
    contact_per_contact_atom = float(row["contact_per_contact_atom"])
    pose_atom_count = float(row["pose_atom_count"])
    contact_sqrt_norm = float(row["contact_sqrt_norm"])
    log_contact_per_atom = float(row["log_contact_per_atom"])
    if family == "baseline_proxy":
        return baseline
    if family == "contact_density_only":
        return -contact_per_atom
    if family == "contact_density_per_contact_atom_only":
        return -contact_per_contact_atom
    if family == "log_contact_density_only":
        return -log_contact_per_atom
    if family == "sqrt_contact_density_only":
        return -contact_sqrt_norm
    if family == "small_ligand_rescue":
        return baseline - alpha * contact_per_atom
    if family == "small_ligand_rescue_size_regularized":
        return baseline - alpha * contact_per_atom + beta * pose_atom_count
    return baseline


def _split_spearman(rows: list[dict[str, Any]], scores: list[float], split: str) -> float | None:
    split_rows = [(row, score) for row, score in zip(rows, scores) if row.get("split") == split]
    if len(split_rows) < 2:
        return None
    return _spearman_values([score for _row, score in split_rows], [float(row["reference"]) for row, _score in split_rows])


def _rank_residual_rows(rows: list[dict[str, Any]], scores: list[float]) -> list[dict[str, Any]]:
    proxy_order = sorted(range(len(rows)), key=lambda index: scores[index])
    reference_order = sorted(range(len(rows)), key=lambda index: float(rows[index]["reference"]))
    proxy_rank = {index: rank + 1 for rank, index in enumerate(proxy_order)}
    reference_rank = {index: rank + 1 for rank, index in enumerate(reference_order)}
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        out.append(
            {
                "target_id": row["target_id"],
                "pose_id": row["pose_id"],
                "source": row["source"],
                "split": row["split"],
                "baseline_proxy": _format_float(row["baseline_proxy"]),
                "variant_proxy": _format_float(scores[index]),
                "reference": _format_float(row["reference"]),
                "variant_rank": proxy_rank[index],
                "reference_rank": reference_rank[index],
                "rank_abs_error": abs(proxy_rank[index] - reference_rank[index]),
                "contact_per_atom": _format_float(row["contact_per_atom"]),
                "pose_atom_count": _format_float(row["pose_atom_count"]),
            }
        )
    return sorted(out, key=lambda item: (-int(item["rank_abs_error"]), str(item["target_id"])))


def _evaluate_variant(
    rows: list[dict[str, Any]],
    *,
    variant_id: str,
    family: str,
    alpha: float = 0.0,
    beta: float = 0.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scores = [_score(row, family=family, alpha=alpha, beta=beta) for row in rows]
    pairs = [
        {
            "proxy": score,
            "reference": float(row["reference"]),
        }
        for row, score in zip(rows, scores)
    ]
    spearman = _spearman_values(scores, [float(row["reference"]) for row in rows])
    bootstrap = _bootstrap_spearman_interval(pairs)
    p05 = _float(bootstrap.get("free_energy_spearman_bootstrap_p05"))
    residual_rows = _rank_residual_rows(rows, scores)
    top_residual = residual_rows[0] if residual_rows else {}
    result = {
        "variant_id": variant_id,
        "variant_family": family,
        "alpha": _format_float(alpha),
        "beta": _format_float(beta),
        "combined_pair_count": len(rows),
        "combined_spearman": spearman,
        "fit_spearman": _split_spearman(rows, scores, "fit"),
        "holdout_spearman": _split_spearman(rows, scores, "holdout"),
        **bootstrap,
        "claim_grade_p05_ready": bool(
            p05 is not None and p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "top_rank_residual_target_id": top_residual.get("target_id", ""),
        "top_rank_residual_abs_error": int(top_residual.get("rank_abs_error") or 0),
        "top_rank_residual_variant_proxy": top_residual.get("variant_proxy", ""),
        "top_rank_residual_reference": top_residual.get("reference", ""),
        "diagnostic_only": True,
    }
    return result, residual_rows


def _variant_specs() -> list[tuple[str, str, float, float]]:
    specs: list[tuple[str, str, float, float]] = [
        ("baseline_proxy", "baseline_proxy", 0.0, 0.0),
        ("contact_density_only", "contact_density_only", 0.0, 0.0),
        ("contact_density_per_contact_atom_only", "contact_density_per_contact_atom_only", 0.0, 0.0),
        ("log_contact_density_only", "log_contact_density_only", 0.0, 0.0),
        ("sqrt_contact_density_only", "sqrt_contact_density_only", 0.0, 0.0),
    ]
    for alpha in (0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.06, 0.08):
        specs.append((f"small_ligand_rescue_a{alpha:g}", "small_ligand_rescue", alpha, 0.0))
    for alpha in (0.005, 0.01, 0.02, 0.04, 0.06):
        for beta in (-0.05, 0.0, 0.05, 0.1):
            specs.append(
                (
                    f"small_ligand_rescue_size_regularized_a{alpha:g}_b{beta:g}",
                    "small_ligand_rescue_size_regularized",
                    alpha,
                    beta,
                )
            )
    return specs


def _variant_sort_key(row: dict[str, Any]) -> tuple[float, float, str]:
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    spearman = _float(row.get("combined_spearman"))
    return (
        float("-inf") if p05 is None else p05,
        float("-inf") if spearman is None else spearman,
        _text(row.get("variant_id")),
    )


def _science_admissible_for_best_selection(row: dict[str, Any], baseline_spearman: float | None) -> bool:
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    spearman = _float(row.get("combined_spearman"))
    return bool(
        p05 is not None
        and spearman is not None
        and baseline_spearman is not None
        and spearman >= baseline_spearman
    )


def _feature_count(rows: list[dict[str, Any]], key: str, value: Any = True) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def build_refine_tier_public_benchmark_score_variant_probe(
    *,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    existing_rows = _existing_feature_rows(existing_materialization_csv, root=root_path)
    candidate_rows = _candidate_feature_rows(candidate_payload)
    rows = [*existing_rows, *candidate_rows]
    variant_rows: list[dict[str, Any]] = []
    residual_by_variant: dict[str, list[dict[str, Any]]] = {}
    for variant_id, family, alpha, beta in _variant_specs():
        result, residual_rows = _evaluate_variant(rows, variant_id=variant_id, family=family, alpha=alpha, beta=beta)
        variant_rows.append(result)
        residual_by_variant[variant_id] = residual_rows
    baseline = next(row for row in variant_rows if row["variant_id"] == "baseline_proxy") if variant_rows else {}
    baseline_spearman = _float(baseline.get("combined_spearman"))
    for row in variant_rows:
        row["science_admissible_for_best_selection"] = _science_admissible_for_best_selection(
            row, baseline_spearman
        )
    sorted_variants = sorted(variant_rows, key=_variant_sort_key, reverse=True)
    top_p05_variant = sorted_variants[0] if sorted_variants else {}
    admissible_variants = [
        row for row in variant_rows if bool(row.get("science_admissible_for_best_selection"))
    ]
    best = (
        sorted(admissible_variants, key=_variant_sort_key, reverse=True)[0]
        if admissible_variants
        else baseline
    )
    baseline_p05 = _float(baseline.get("free_energy_spearman_bootstrap_p05"))
    best_p05 = _float(best.get("free_energy_spearman_bootstrap_p05"))
    best_id = _text(best.get("variant_id"))
    top_p05 = _float(top_p05_variant.get("free_energy_spearman_bootstrap_p05"))
    feature_complete_pair_count = _feature_count(rows, "feature_complete")
    candidate_detail_pair_count = _feature_count(candidate_rows, "feature_detail_present")
    summary = {
        "packet_type": "refine_tier_public_benchmark_score_variant_probe",
        "status": (
            "refine_tier_public_benchmark_score_variant_probe_ready"
            if candidate_present and rows
            else "blocked_refine_tier_public_benchmark_score_variant_probe"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "existing_pair_count": len(existing_rows),
        "candidate_pair_count": len(candidate_rows),
        "combined_pair_count": len(rows),
        "existing_feature_complete_pair_count": _feature_count(existing_rows, "feature_complete"),
        "candidate_detail_pair_count": candidate_detail_pair_count,
        "candidate_detail_from_rows_pair_count": _feature_count(
            candidate_rows, "detail_source", "candidate_rows_internal_deltaG"
        ),
        "candidate_detail_missing_pair_count": len(candidate_rows) - candidate_detail_pair_count,
        "candidate_feature_complete_pair_count": _feature_count(candidate_rows, "feature_complete"),
        "feature_complete_pair_count": feature_complete_pair_count,
        "feature_missing_pair_count": len(rows) - feature_complete_pair_count,
        "variant_count": len(variant_rows),
        "bootstrap_iteration_count": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "baseline_variant_id": "baseline_proxy",
        "baseline_spearman": baseline.get("combined_spearman"),
        "baseline_bootstrap_p05": baseline_p05,
        "top_p05_variant_id": top_p05_variant.get("variant_id", ""),
        "top_p05_variant_spearman": top_p05_variant.get("combined_spearman"),
        "top_p05_variant_bootstrap_p05": top_p05,
        "top_p05_variant_claim_grade_p05_ready": bool(
            top_p05 is not None and top_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "top_p05_variant_science_admissible_for_best_selection": bool(
            top_p05_variant.get("science_admissible_for_best_selection")
        ),
        "best_variant_id": best_id,
        "best_variant_family": best.get("variant_family", ""),
        "best_variant_alpha": best.get("alpha", ""),
        "best_variant_beta": best.get("beta", ""),
        "best_variant_spearman": best.get("combined_spearman"),
        "best_variant_bootstrap_p05": best_p05,
        "best_variant_bootstrap_p05_delta": (
            None if baseline_p05 is None or best_p05 is None else best_p05 - baseline_p05
        ),
        "best_variant_claim_grade_p05_ready": bool(
            best_p05 is not None and best_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "best_variant_selection_policy": (
            "diagnostic_grid_requires_combined_spearman_not_below_baseline_and_independent_validation_before_score_use"
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "If a variant materially improves bootstrap p05, validate it on an independent R9 holdout or "
            "operator-reviewed metric-source payloads before touching candidate-fill values. Keep public "
            "benchmark claim promotion blocked until reviewed payload receipts and p05 >= 0.5 are both true."
        ),
    }
    return {
        "summary": summary,
        "variant_rows": sorted_variants,
        "best_variant_rank_residual_rows": residual_by_variant.get(best_id, [])[:25],
        "baseline_rank_residual_rows": residual_by_variant.get("baseline_proxy", [])[:25],
    }


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Score Variant Probe",
        "",
        f"- status: `{s['status']}`",
        f"- combined_pair_count: `{s['combined_pair_count']}`",
        f"- feature_complete_pair_count: `{s['feature_complete_pair_count']}`",
        f"- candidate_detail_from_rows_pair_count: `{s['candidate_detail_from_rows_pair_count']}`",
        f"- baseline_spearman: `{s['baseline_spearman']}`",
        f"- baseline_bootstrap_p05: `{s['baseline_bootstrap_p05']}`",
        f"- top_p05_variant_id: `{s['top_p05_variant_id']}`",
        f"- top_p05_variant_spearman: `{s['top_p05_variant_spearman']}`",
        f"- top_p05_variant_bootstrap_p05: `{s['top_p05_variant_bootstrap_p05']}`",
        f"- best_variant_id: `{s['best_variant_id']}`",
        f"- best_variant_spearman: `{s['best_variant_spearman']}`",
        f"- best_variant_bootstrap_p05: `{s['best_variant_bootstrap_p05']}`",
        f"- best_variant_bootstrap_p05_delta: `{s['best_variant_bootstrap_p05_delta']}`",
        f"- best_variant_claim_grade_p05_ready: `{s['best_variant_claim_grade_p05_ready']}`",
        f"- selection_policy: `{s['best_variant_selection_policy']}`",
        "",
        "## Top Variants",
        "",
        "| variant | family | alpha | beta | spearman | p05 | holdout spearman | claim-grade p05 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["variant_rows"][:12]:
        lines.append(
            f"| `{row['variant_id']}` | `{row['variant_family']}` | `{row['alpha']}` | `{row['beta']}` | "
            f"`{_format_float(_float(row.get('combined_spearman')))}` | "
            f"`{_format_float(_float(row.get('free_energy_spearman_bootstrap_p05')))}` | "
            f"`{_format_float(_float(row.get('holdout_spearman')))}` | `{row['claim_grade_p05_ready']}` |"
        )
    lines.extend(
        [
            "",
            "## Best Variant Rank Residuals",
            "",
            "| target | pose | source | split | variant rank | reference rank | rank abs error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["best_variant_rank_residual_rows"][:10]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | `{row['split']}` | "
            f"`{row['variant_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 public-benchmark score variant probe.")
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_score_variant_probe(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["variant_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
