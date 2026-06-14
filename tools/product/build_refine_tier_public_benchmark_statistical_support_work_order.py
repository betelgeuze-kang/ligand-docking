#!/usr/bin/env python3
"""Build the R9 public-benchmark statistical-support expansion work order."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
    MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATERIALIZATION_JSON = "runs/refine_tier_public_benchmark_metric_source_materialization_current.json"
DEFAULT_MATERIALIZED_APPLY_JSON = "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json"
DEFAULT_WORK_ORDER_CSV = "runs/refine_tier_public_benchmark_work_order_current.csv"
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_statistical_support_work_order_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_statistical_support_work_order_current.md"

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support work order only; it reads local materialized "
    "R9 public-benchmark summaries and emits the minimum additional benchmark-pair slots required for "
    "claim-grade statistical support. It does not download data, run docking or MD, promote canonical "
    "intake rows, approve operator receipts, upload, email, delete, commit, push, or mutate external state."
)

WORK_ORDER_COLUMNS = [
    "expansion_slot_id",
    "required_split",
    "required_benchmark_family",
    "required_new_pair_count_credit",
    "required_holdout_pair_count_credit",
    "required_fields",
    "required_metric_source_payloads",
    "acceptance_rule",
    "operator_action",
    "canonical_intake_promotion_allowed",
    "external_engine_calls_allowed",
    "external_state_mutated",
]

REQUIRED_FIELDS = (
    "benchmark_id;target_id;split;license_ok;pose_rmsd_A;dockq;lddt_pli;"
    "deltaG_mm_gbsa_kcal_mol;dockq_source_artifact;lddt_pli_source_artifact;"
    "internal_deltaG_source_artifact;deltaG_experimental_kcal_mol;receptor_coordinate_artifact"
)
REQUIRED_METRIC_SOURCE_PAYLOADS = "dockq;lddt_pli;internal_deltaG"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, Any]], bool]:
    path = _resolve(path_like)
    if not path.is_file():
        return [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)], True


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        out = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _deficit(observed: int, required: int) -> int:
    return max(0, int(required) - int(observed))


def _bootstrap_deficit(observed: float | None, required: float) -> float:
    if observed is None:
        return float(required)
    return max(0.0, float(required) - float(observed))


def _slot_rows(*, new_pair_slot_count: int, minimum_holdout_slot_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(1, new_pair_slot_count + 1):
        required_split = "holdout" if index <= minimum_holdout_slot_count else "fit_or_holdout"
        rows.append(
            {
                "expansion_slot_id": f"refine_tier_public_benchmark_stat_support_expansion_{index:03d}",
                "required_split": required_split,
                "required_benchmark_family": "public_protein_ligand_refine_tier",
                "required_new_pair_count_credit": 1,
                "required_holdout_pair_count_credit": 1 if required_split == "holdout" else 0,
                "required_fields": REQUIRED_FIELDS,
                "required_metric_source_payloads": REQUIRED_METRIC_SOURCE_PAYLOADS,
                "acceptance_rule": (
                    "Add one license-reviewed public protein-ligand benchmark pair with validated receptor/"
                    "complex coordinates, local ligand pose artifact, experimental DeltaG, DockQ, lDDT-PLI, "
                    "internal DeltaG, and schema-valid metric source JSONs whose input artifact hashes match "
                    "the receptor and ligand inputs. Rebuild materialization and require bootstrap Spearman "
                    "p05 >= 0.5 before any claim-grade promotion."
                ),
                "operator_action": "append_validated_public_benchmark_pair_then_rebuild_statistical_support",
                "canonical_intake_promotion_allowed": False,
                "external_engine_calls_allowed": False,
                "external_state_mutated": False,
            }
        )
    return rows


def build_refine_tier_public_benchmark_statistical_support_work_order(
    *,
    materialization_json: str | Path = DEFAULT_MATERIALIZATION_JSON,
    materialized_apply_json: str | Path = DEFAULT_MATERIALIZED_APPLY_JSON,
    work_order_csv: str | Path = DEFAULT_WORK_ORDER_CSV,
) -> dict[str, Any]:
    materialization_payload, materialization_present = _read_json(materialization_json)
    materialized_apply_payload, materialized_apply_present = _read_json(materialized_apply_json)
    work_order_rows, work_order_present = _read_csv(work_order_csv)
    materialization = _summary(materialization_payload)
    materialized_apply = _summary(materialized_apply_payload)

    pair_count = _int(materialization.get("free_energy_pair_count"))
    fit_pair_count = _int(materialization.get("free_energy_fit_pair_count"))
    holdout_pair_count = _int(materialization.get("free_energy_holdout_pair_count"))
    bootstrap_low = _float(materialization.get("free_energy_spearman_bootstrap_p05"))
    statistical_support_ready = bool(
        materialization.get("claim_grade_public_benchmark_statistical_support_ready") is True
    )
    materialized_apply_ready = bool(
        materialized_apply.get("status") == "refine_tier_public_benchmark_work_order_apply_ready"
        and materialized_apply.get("apply_ready") is True
    )

    pair_deficit = _deficit(pair_count, MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS)
    holdout_deficit = _deficit(holdout_pair_count, MIN_CLAIM_GRADE_HOLDOUT_PAIRS)
    new_pair_slot_count = max(pair_deficit, holdout_deficit)
    minimum_fit_or_holdout_slot_count = max(0, new_pair_slot_count - holdout_deficit)
    bootstrap_low_deficit = _bootstrap_deficit(
        bootstrap_low,
        MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    )

    blockers: list[str] = []
    if not materialization_present:
        blockers.append("materialization_artifact_missing")
    if not materialized_apply_present:
        blockers.append("materialized_apply_artifact_missing")
    if not work_order_present:
        blockers.append("public_benchmark_work_order_csv_missing")
    if pair_deficit:
        blockers.append("claim_grade_public_benchmark_pair_count_below_minimum")
    if holdout_deficit:
        blockers.append("claim_grade_public_benchmark_holdout_pair_count_below_minimum")
    if bootstrap_low_deficit > 0.0:
        blockers.append("claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum")

    rows = _slot_rows(
        new_pair_slot_count=new_pair_slot_count,
        minimum_holdout_slot_count=holdout_deficit,
    )
    work_order_ready = materialization_present and materialized_apply_present and work_order_present
    status = (
        "refine_tier_public_benchmark_statistical_support_work_order_ready"
        if work_order_ready
        else "blocked_refine_tier_public_benchmark_statistical_support_work_order"
    )
    canonical_intake_promotion_allowed = bool(
        statistical_support_ready and materialized_apply_ready and not blockers
    )

    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_work_order",
        "status": status,
        "work_order_ready": work_order_ready,
        "claim_grade_public_benchmark_statistical_support_ready": statistical_support_ready,
        "canonical_intake_promotion_allowed": canonical_intake_promotion_allowed,
        "materialization_artifact": _display(materialization_json),
        "materialization_artifact_present": materialization_present,
        "materialized_apply_artifact": _display(materialized_apply_json),
        "materialized_apply_artifact_present": materialized_apply_present,
        "materialized_apply_ready": materialized_apply_ready,
        "source_work_order_csv": _display(work_order_csv),
        "source_work_order_csv_present": work_order_present,
        "source_work_order_row_count": len(work_order_rows),
        "observed_public_benchmark_pair_count": pair_count,
        "observed_fit_pair_count": fit_pair_count,
        "observed_holdout_pair_count": holdout_pair_count,
        "observed_bootstrap_spearman_p05": bootstrap_low,
        "min_claim_grade_public_benchmark_pairs_required": MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
        "min_claim_grade_holdout_pairs_required": MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        "minimum_new_pair_count": pair_deficit,
        "minimum_new_holdout_pair_count": holdout_deficit,
        "minimum_new_fit_or_holdout_pair_count": minimum_fit_or_holdout_slot_count,
        "bootstrap_spearman_p05_deficit": bootstrap_low_deficit,
        "bootstrap_retest_required": not statistical_support_ready,
        "expansion_slot_count": len(rows),
        "holdout_expansion_slot_count": sum(1 for row in rows if row["required_split"] == "holdout"),
        "fit_or_holdout_expansion_slot_count": sum(
            1 for row in rows if row["required_split"] == "fit_or_holdout"
        ),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Statistical support gap is closed; review operator receipt and claim-boundary gates before "
            "canonical intake promotion."
            if canonical_intake_promotion_allowed
            else (
                f"Fill {new_pair_slot_count} additional reviewed public benchmark pair slots, including at "
                f"least {holdout_deficit} holdout slots, then rebuild materialization and require bootstrap "
                "Spearman p05 >= 0.5 before any claim-grade promotion."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Refine Tier Public Benchmark Statistical Support Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- work_order_ready: `{s['work_order_ready']}`",
        f"- statistical_support_ready: `{s['claim_grade_public_benchmark_statistical_support_ready']}`",
        f"- observed pairs: `{s['observed_public_benchmark_pair_count']}`",
        f"- observed holdout pairs: `{s['observed_holdout_pair_count']}`",
        f"- observed bootstrap p05: `{s['observed_bootstrap_spearman_p05']}`",
        f"- minimum_new_pair_count: `{s['minimum_new_pair_count']}`",
        f"- minimum_new_holdout_pair_count: `{s['minimum_new_holdout_pair_count']}`",
        f"- expansion_slot_count: `{s['expansion_slot_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        "",
        "## Expansion Slots",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            f"- `{row['expansion_slot_id']}` split=`{row['required_split']}` "
            f"action=`{row['operator_action']}`"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the R9 public-benchmark claim-grade statistical-support work order."
    )
    parser.add_argument("--materialization-json", default=DEFAULT_MATERIALIZATION_JSON)
    parser.add_argument("--materialized-apply-json", default=DEFAULT_MATERIALIZED_APPLY_JSON)
    parser.add_argument("--work-order-csv", default=DEFAULT_WORK_ORDER_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_work_order(
        materialization_json=args.materialization_json,
        materialized_apply_json=args.materialized_apply_json,
        work_order_csv=args.work_order_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
