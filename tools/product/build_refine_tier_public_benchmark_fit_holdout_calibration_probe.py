#!/usr/bin/env python3
"""Read-only R9 fit/holdout calibration probe for public-benchmark scoring."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_score_variant_probe import (
    DEFAULT_CANDIDATE_FILL_JSON,
    DEFAULT_EXISTING_MATERIALIZATION_CSV,
    ROOT,
    _candidate_feature_rows,
    _display,
    _evaluate_variant,
    _existing_feature_rows,
    _float,
    _format_float,
    _read_json,
    _resolve,
    _text,
    _variant_specs,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
)

DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_fit_holdout_calibration_probe_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_fit_holdout_calibration_probe_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_fit_holdout_calibration_probe_current.md"

CLAIM_BOUNDARY = (
    "R9 fit/holdout calibration probe only; it reuses local public-benchmark preview features, "
    "selects scoring hypotheses from the fit split, and reports holdout-guarded diagnostics. It does "
    "not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, "
    "promote canonical intake, change production scoring, run docking/MD, download, upload, email, "
    "delete, commit, push, or mutate external state."
)


def _variant_sort_key(row: dict[str, Any], *, primary: str) -> tuple[float, float, float, str]:
    primary_value = _float(row.get(primary))
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    combined = _float(row.get("combined_spearman"))
    return (
        float("-inf") if primary_value is None else primary_value,
        float("-inf") if p05 is None else p05,
        float("-inf") if combined is None else combined,
        _text(row.get("variant_id")),
    )


def _p05_sort_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    p05 = _float(row.get("free_energy_spearman_bootstrap_p05"))
    holdout = _float(row.get("holdout_spearman"))
    combined = _float(row.get("combined_spearman"))
    return (
        float("-inf") if p05 is None else p05,
        float("-inf") if holdout is None else holdout,
        float("-inf") if combined is None else combined,
        _text(row.get("variant_id")),
    )


def _delta(value: Any, baseline: float | None) -> float | None:
    observed = _float(value)
    if observed is None or baseline is None:
        return None
    return observed - baseline


def _annotate_rows(variant_rows: list[dict[str, Any]], baseline: dict[str, Any]) -> None:
    baseline_fit = _float(baseline.get("fit_spearman"))
    baseline_holdout = _float(baseline.get("holdout_spearman"))
    baseline_combined = _float(baseline.get("combined_spearman"))
    baseline_p05 = _float(baseline.get("free_energy_spearman_bootstrap_p05"))
    for row in variant_rows:
        fit_delta = _delta(row.get("fit_spearman"), baseline_fit)
        holdout_delta = _delta(row.get("holdout_spearman"), baseline_holdout)
        combined_delta = _delta(row.get("combined_spearman"), baseline_combined)
        p05_delta = _delta(row.get("free_energy_spearman_bootstrap_p05"), baseline_p05)
        row["fit_spearman_delta_from_baseline"] = fit_delta
        row["holdout_spearman_delta_from_baseline"] = holdout_delta
        row["combined_spearman_delta_from_baseline"] = combined_delta
        row["bootstrap_p05_delta_from_baseline"] = p05_delta
        row["fit_selection_eligible"] = bool(
            fit_delta is not None
            and combined_delta is not None
            and fit_delta >= 0.0
            and combined_delta >= 0.0
        )
        row["holdout_guarded_eligible"] = bool(
            row["fit_selection_eligible"] and holdout_delta is not None and holdout_delta >= 0.0
        )


def _feature_count(rows: list[dict[str, Any]], key: str, value: Any = True) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def _selected_or_baseline(rows: list[dict[str, Any]], baseline: dict[str, Any], *, mode: str) -> dict[str, Any]:
    if mode == "fit":
        eligible = [row for row in rows if bool(row.get("fit_selection_eligible"))]
        return sorted(eligible, key=lambda row: _variant_sort_key(row, primary="fit_spearman"), reverse=True)[0]
    if mode == "holdout_guarded":
        eligible = [row for row in rows if bool(row.get("holdout_guarded_eligible"))]
        if eligible:
            return sorted(eligible, key=_p05_sort_key, reverse=True)[0]
    return baseline


def build_refine_tier_public_benchmark_fit_holdout_calibration_probe(
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
        result, residual_rows = _evaluate_variant(
            rows, variant_id=variant_id, family=family, alpha=alpha, beta=beta
        )
        variant_rows.append(result)
        residual_by_variant[variant_id] = residual_rows

    baseline = next((row for row in variant_rows if row.get("variant_id") == "baseline_proxy"), {})
    _annotate_rows(variant_rows, baseline)
    fit_selected = _selected_or_baseline(variant_rows, baseline, mode="fit")
    holdout_guarded = _selected_or_baseline(variant_rows, baseline, mode="holdout_guarded")

    fit_selected_id = _text(fit_selected.get("variant_id"))
    holdout_guarded_id = _text(holdout_guarded.get("variant_id"))
    baseline_p05 = _float(baseline.get("free_energy_spearman_bootstrap_p05"))
    fit_selected_p05 = _float(fit_selected.get("free_energy_spearman_bootstrap_p05"))
    holdout_guarded_p05 = _float(holdout_guarded.get("free_energy_spearman_bootstrap_p05"))
    fit_selected_holdout_delta = _float(fit_selected.get("holdout_spearman_delta_from_baseline"))

    sorted_rows = sorted(variant_rows, key=lambda row: _variant_sort_key(row, primary="fit_spearman"), reverse=True)
    summary = {
        "packet_type": "refine_tier_public_benchmark_fit_holdout_calibration_probe",
        "status": (
            "refine_tier_public_benchmark_fit_holdout_calibration_probe_ready"
            if candidate_present and rows and baseline
            else "blocked_refine_tier_public_benchmark_fit_holdout_calibration_probe"
        ),
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_present": candidate_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "existing_pair_count": len(existing_rows),
        "candidate_pair_count": len(candidate_rows),
        "combined_pair_count": len(rows),
        "fit_pair_count": sum(1 for row in rows if row.get("split") == "fit"),
        "holdout_pair_count": sum(1 for row in rows if row.get("split") == "holdout"),
        "feature_complete_pair_count": _feature_count(rows, "feature_complete"),
        "candidate_detail_from_rows_pair_count": _feature_count(
            candidate_rows, "detail_source", "candidate_rows_internal_deltaG"
        ),
        "variant_count": len(variant_rows),
        "fit_selection_eligible_variant_count": sum(
            1 for row in variant_rows if bool(row.get("fit_selection_eligible"))
        ),
        "holdout_guarded_eligible_variant_count": sum(
            1 for row in variant_rows if bool(row.get("holdout_guarded_eligible"))
        ),
        "bootstrap_iteration_count": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "baseline_variant_id": "baseline_proxy",
        "baseline_fit_spearman": baseline.get("fit_spearman"),
        "baseline_holdout_spearman": baseline.get("holdout_spearman"),
        "baseline_combined_spearman": baseline.get("combined_spearman"),
        "baseline_bootstrap_p05": baseline_p05,
        "fit_selected_variant_id": fit_selected_id,
        "fit_selected_variant_family": fit_selected.get("variant_family", ""),
        "fit_selected_fit_spearman": fit_selected.get("fit_spearman"),
        "fit_selected_holdout_spearman": fit_selected.get("holdout_spearman"),
        "fit_selected_combined_spearman": fit_selected.get("combined_spearman"),
        "fit_selected_bootstrap_p05": fit_selected_p05,
        "fit_selected_bootstrap_p05_delta": (
            None if baseline_p05 is None or fit_selected_p05 is None else fit_selected_p05 - baseline_p05
        ),
        "fit_selected_holdout_spearman_delta": fit_selected_holdout_delta,
        "fit_selected_holdout_non_degradation_ready": bool(
            fit_selected_holdout_delta is not None and fit_selected_holdout_delta >= 0.0
        ),
        "fit_selected_claim_grade_p05_ready": bool(
            fit_selected_p05 is not None
            and fit_selected_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "holdout_guarded_variant_id": holdout_guarded_id,
        "holdout_guarded_variant_family": holdout_guarded.get("variant_family", ""),
        "holdout_guarded_fit_spearman": holdout_guarded.get("fit_spearman"),
        "holdout_guarded_holdout_spearman": holdout_guarded.get("holdout_spearman"),
        "holdout_guarded_combined_spearman": holdout_guarded.get("combined_spearman"),
        "holdout_guarded_bootstrap_p05": holdout_guarded_p05,
        "holdout_guarded_bootstrap_p05_delta": (
            None if baseline_p05 is None or holdout_guarded_p05 is None else holdout_guarded_p05 - baseline_p05
        ),
        "holdout_guarded_claim_grade_p05_ready": bool(
            holdout_guarded_p05 is not None
            and holdout_guarded_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
        ),
        "calibration_generalization_ready": bool(
            holdout_guarded_p05 is not None
            and holdout_guarded_p05 >= MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW
            and holdout_guarded_id != "baseline_proxy"
        ),
        "selection_policy": (
            "fit_selected_uses_fit_spearman_only; holdout_guarded_requires_fit_combined_holdout_not_below_baseline; "
            "neither selection may write payloads or promote claims without independent reviewed evidence"
        ),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the holdout-guarded variant only as a scoring hypothesis. Validate descriptor calibration on "
            "independent/operator-reviewed R9 metric-source payloads and reduce the largest rank residuals before "
            "any canonical intake, payload write, or claim promotion."
        ),
    }
    return {
        "summary": summary,
        "calibration_rows": sorted_rows,
        "fit_selected_rank_residual_rows": residual_by_variant.get(fit_selected_id, [])[:25],
        "holdout_guarded_rank_residual_rows": residual_by_variant.get(holdout_guarded_id, [])[:25],
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
        "# R9 Fit/Holdout Calibration Probe",
        "",
        f"- status: `{s['status']}`",
        f"- combined_pair_count: `{s['combined_pair_count']}`",
        f"- fit_pair_count: `{s['fit_pair_count']}`",
        f"- holdout_pair_count: `{s['holdout_pair_count']}`",
        f"- feature_complete_pair_count: `{s['feature_complete_pair_count']}`",
        f"- baseline_fit/holdout/combined: `{s['baseline_fit_spearman']}/"
        f"{s['baseline_holdout_spearman']}/{s['baseline_combined_spearman']}`",
        f"- baseline_bootstrap_p05: `{s['baseline_bootstrap_p05']}`",
        f"- fit_selected_variant_id: `{s['fit_selected_variant_id']}`",
        f"- fit_selected_fit/holdout/combined: `{s['fit_selected_fit_spearman']}/"
        f"{s['fit_selected_holdout_spearman']}/{s['fit_selected_combined_spearman']}`",
        f"- fit_selected_bootstrap_p05: `{s['fit_selected_bootstrap_p05']}`",
        f"- fit_selected_holdout_non_degradation_ready: `{s['fit_selected_holdout_non_degradation_ready']}`",
        f"- holdout_guarded_variant_id: `{s['holdout_guarded_variant_id']}`",
        f"- holdout_guarded_fit/holdout/combined: `{s['holdout_guarded_fit_spearman']}/"
        f"{s['holdout_guarded_holdout_spearman']}/{s['holdout_guarded_combined_spearman']}`",
        f"- holdout_guarded_bootstrap_p05: `{s['holdout_guarded_bootstrap_p05']}`",
        f"- holdout_guarded_claim_grade_p05_ready: `{s['holdout_guarded_claim_grade_p05_ready']}`",
        f"- calibration_generalization_ready: `{s['calibration_generalization_ready']}`",
        "",
        "## Top Fit-Selected Candidates",
        "",
        "| variant | family | fit | holdout | combined | p05 | holdout guarded | claim-grade p05 |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["calibration_rows"][:12]:
        lines.append(
            f"| `{row['variant_id']}` | `{row['variant_family']}` | "
            f"`{_format_float(_float(row.get('fit_spearman')))}` | "
            f"`{_format_float(_float(row.get('holdout_spearman')))}` | "
            f"`{_format_float(_float(row.get('combined_spearman')))}` | "
            f"`{_format_float(_float(row.get('free_energy_spearman_bootstrap_p05')))}` | "
            f"`{row['holdout_guarded_eligible']}` | `{row['claim_grade_p05_ready']}` |"
        )
    lines.extend(
        [
            "",
            "## Holdout-Guarded Residuals",
            "",
            "| target | pose | source | split | variant rank | reference rank | rank abs error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["holdout_guarded_rank_residual_rows"][:10]:
        lines.append(
            f"| `{row['target_id']}` | `{row['pose_id']}` | `{row['source']}` | `{row['split']}` | "
            f"`{row['variant_rank']}` | `{row['reference_rank']}` | `{row['rank_abs_error']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 fit/holdout calibration probe.")
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
    payload = build_refine_tier_public_benchmark_fit_holdout_calibration_probe(
        candidate_fill_json=args.candidate_fill_json,
        existing_materialization_csv=args.existing_materialization_csv,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["calibration_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
