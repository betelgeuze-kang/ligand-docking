#!/usr/bin/env python3
"""Build candidate queue for R9 public-benchmark statistical-support expansion."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_readiness import (
    DEFAULT_DELTA_G_TEMPERATURE_K,
    DEFAULT_WORK_ORDER_AFFINITY_TSV,
    DEFAULT_WORK_ORDER_DATASET_DIR,
    DEFAULT_WORK_ORDER_SEED_CSV,
    PAFFINITY_TO_DG_KCAL_PER_MOL,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_work_order import (
    DEFAULT_OUT_JSON as DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    REQUIRED_METRIC_SOURCE_PAYLOADS,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT_WORK_ORDER_CSV = "runs/refine_tier_public_benchmark_work_order_current.csv"
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.md"

MAX_POSE_RMSD_A = 2.5

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support candidate queue only; it maps local PDBBind/CASF "
    "pose-affinity candidates onto the open R9 statistical-support expansion slots. It does not download "
    "data, extract archives, run docking or MD, compute claim metrics, write intake rows, approve receipts, "
    "promote claims, upload, email, delete, commit, push, or mutate external state."
)

CANDIDATE_COLUMNS = [
    "candidate_queue_id",
    "expansion_slot_id",
    "candidate_rank",
    "required_split",
    "suggested_split",
    "suggested_work_order_id",
    "benchmark_id",
    "target_id",
    "pose_id",
    "benchmark_family",
    "provenance_kind",
    "provenance_id",
    "license_ok",
    "license_review_required",
    "external_engine_calls",
    "pose_rmsd_A",
    "deltaG_experimental_kcal_mol",
    "ligand_pose_artifact",
    "ligand_pose_artifact_present",
    "receptor_coordinate_artifact",
    "receptor_coordinate_artifact_present",
    "suggested_public_coordinate_urls",
    "suggested_local_coordinate_paths",
    "expected_archive_member_examples",
    "dockq_source_artifact",
    "lddt_pli_source_artifact",
    "internal_deltaG_source_artifact",
    "required_metric_source_payloads",
    "candidate_ready_for_metric_materialization",
    "candidate_ready_for_canonical_intake",
    "candidate_status",
    "candidate_blockers",
    "operator_action",
    "canonical_intake_promotion_allowed",
    "external_state_mutated",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6g}"


def _stable_id(value: Any) -> str:
    return "".join(char if char.isalnum() else "_" for char in _text(value).upper()).strip("_")


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or []), True


def _read_experimental_delta_g_by_complex(
    path_like: str | Path,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, float], dict[str, Any]]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, {
            "experimental_deltaG_source": _display(path_like, root=root),
            "experimental_deltaG_source_present": False,
            "experimental_deltaG_source_row_count": 0,
            "experimental_deltaG_source_parsed_count": 0,
            "experimental_deltaG_source_invalid_count": 0,
            "experimental_deltaG_temperature_K": DEFAULT_DELTA_G_TEMPERATURE_K,
            "experimental_deltaG_conversion": "deltaG_kcal_mol=-RTln(10)*pAffinity",
        }
    values: dict[str, float] = {}
    source_row_count = 0
    invalid_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            source_row_count += 1
            parts = text.split()
            if len(parts) < 2:
                invalid_count += 1
                continue
            complex_id = parts[0].strip().lower()
            paffinity = _float(parts[1])
            if not complex_id or paffinity is None:
                invalid_count += 1
                continue
            values[complex_id] = PAFFINITY_TO_DG_KCAL_PER_MOL * paffinity
    return values, {
        "experimental_deltaG_source": _display(path_like, root=root),
        "experimental_deltaG_source_present": True,
        "experimental_deltaG_source_row_count": source_row_count,
        "experimental_deltaG_source_parsed_count": len(values),
        "experimental_deltaG_source_invalid_count": invalid_count,
        "experimental_deltaG_temperature_K": DEFAULT_DELTA_G_TEMPERATURE_K,
        "experimental_deltaG_conversion": "deltaG_kcal_mol=-RTln(10)*pAffinity",
    }


def _existing_targets(rows: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        target_id = _text(row.get("target_id")).lower()
        if target_id:
            out.add(target_id)
    return out


def _candidate_pool(
    seed_rows: list[dict[str, Any]],
    *,
    existing_target_ids: set[str],
    max_pose_rmsd_a: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    best_by_complex: dict[str, dict[str, Any]] = {}
    eligible_row_count = 0
    excluded_existing_target_row_count = 0
    for row in seed_rows:
        complex_id = _text(row.get("complex_id")).lower()
        pose_id = _text(row.get("pose_id"))
        pose_rmsd = _float(row.get("pose_rmsd_A"))
        if not complex_id or not pose_id or pose_rmsd is None:
            continue
        if _int(row.get("blocker_count")) != 0 or _text(row.get("blockers")):
            continue
        if pose_rmsd > float(max_pose_rmsd_a):
            continue
        eligible_row_count += 1
        if complex_id in existing_target_ids:
            excluded_existing_target_row_count += 1
            continue
        current = best_by_complex.get(complex_id)
        current_rmsd = _float(current.get("pose_rmsd_A")) if current else None
        if current is None or current_rmsd is None or pose_rmsd < current_rmsd:
            best_by_complex[complex_id] = row
    candidates = sorted(
        best_by_complex.values(),
        key=lambda row: (
            _float(row.get("pose_rmsd_A")) or float("inf"),
            _text(row.get("complex_id")),
            _text(row.get("pose_id")),
        ),
    )
    return candidates, {
        "candidate_source_eligible_row_count": eligible_row_count,
        "candidate_source_excluded_existing_target_row_count": excluded_existing_target_row_count,
        "candidate_source_distinct_target_count": len(best_by_complex),
    }


def _candidate_row(
    *,
    slot_row: dict[str, Any],
    candidate_rank: int,
    candidate: dict[str, Any],
    experimental_delta_g_by_complex: dict[str, float],
    dataset_dir: str | Path,
    root: Path,
) -> dict[str, Any]:
    slot_id = _text(slot_row.get("expansion_slot_id"))
    required_split = _text(slot_row.get("required_split"))
    suggested_split = "holdout" if required_split == "holdout" else "fit"
    target_id = _text(candidate.get("complex_id")).lower()
    pose_id = _text(candidate.get("pose_id"))
    pose_rmsd = _float(candidate.get("pose_rmsd_A"))
    benchmark_id = f"PDBBIND_CASF_{_stable_id(target_id)}_{_stable_id(pose_id)}"
    suggested_work_order_id = slot_id or f"refine_tier_public_benchmark_stat_support_expansion_{candidate_rank:03d}"
    ligand_pose_artifact = _display(candidate.get("pose_artifact"), root=root)
    ligand_pose_present = _resolve(candidate.get("pose_artifact"), root=root).is_file()
    receptor_coordinate_artifact = _display(
        Path(dataset_dir) / target_id / f"{target_id}_receptor.pdb",
        root=root,
    )
    receptor_coordinate_present = _resolve(receptor_coordinate_artifact, root=root).is_file()
    experimental_delta_g = experimental_delta_g_by_complex.get(target_id)
    blockers: list[str] = []
    if not ligand_pose_present:
        blockers.append("ligand_pose_artifact_missing")
    if not receptor_coordinate_present:
        blockers.append("receptor_coordinate_artifact_missing")
    if experimental_delta_g is None:
        blockers.append("experimental_deltaG_missing")
    metric_materialization_ready = bool(
        ligand_pose_present and receptor_coordinate_present and experimental_delta_g is not None
    )
    candidate_status = (
        "candidate_local_inputs_ready_for_metric_materialization"
        if metric_materialization_ready
        else "blocked_candidate_coordinate_or_affinity_inputs_pending"
    )
    return {
        "candidate_queue_id": f"stat_support_candidate_{candidate_rank:03d}",
        "expansion_slot_id": suggested_work_order_id,
        "candidate_rank": candidate_rank,
        "required_split": required_split,
        "suggested_split": suggested_split,
        "suggested_work_order_id": suggested_work_order_id,
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "pose_id": pose_id,
        "benchmark_family": "pdbbind_casf_refine_tier_public_seed",
        "provenance_kind": "pdbbind",
        "provenance_id": f"PDBBind/CASF:{target_id}:{pose_id}",
        "license_ok": "OPERATOR_CONFIRM_TRUE",
        "license_review_required": True,
        "external_engine_calls": 0,
        "pose_rmsd_A": _format_float(pose_rmsd),
        "deltaG_experimental_kcal_mol": _format_float(experimental_delta_g),
        "ligand_pose_artifact": ligand_pose_artifact,
        "ligand_pose_artifact_present": ligand_pose_present,
        "receptor_coordinate_artifact": receptor_coordinate_artifact,
        "receptor_coordinate_artifact_present": receptor_coordinate_present,
        "suggested_public_coordinate_urls": (
            f"https://files.rcsb.org/download/{target_id.upper()}.cif;"
            f"https://files.rcsb.org/download/{target_id.upper()}.pdb"
        ),
        "suggested_local_coordinate_paths": (
            f"data/public_benchmarks/pdbbind_casf_pose_affinity/{target_id}/{target_id}_receptor.pdb;"
            f"data/public_benchmarks/pdbbind_casf_pose_affinity/{target_id}/{target_id}_complex.pdb"
        ),
        "expected_archive_member_examples": (
            f"pdbbind/{target_id}/{target_id}_protein.pdb;"
            f"pdbbind/{target_id}/{target_id}_receptor.cif;"
            f"casf/{target_id}/{target_id}_complex.pdb"
        ),
        "dockq_source_artifact": (
            f"runs/refine_tier_public_benchmark_metric_sources/{suggested_work_order_id}_dockq.json"
        ),
        "lddt_pli_source_artifact": (
            f"runs/refine_tier_public_benchmark_metric_sources/{suggested_work_order_id}_lddt_pli.json"
        ),
        "internal_deltaG_source_artifact": (
            f"runs/refine_tier_public_benchmark_metric_sources/{suggested_work_order_id}_internal_deltaG.json"
        ),
        "required_metric_source_payloads": REQUIRED_METRIC_SOURCE_PAYLOADS,
        "candidate_ready_for_metric_materialization": metric_materialization_ready,
        "candidate_ready_for_canonical_intake": False,
        "candidate_status": candidate_status,
        "candidate_blockers": ";".join(blockers),
        "operator_action": (
            "review_public_coordinate_source_and_place_receptor_or_complex_coordinate_then_materialize_metrics"
            if blockers
            else "materialize_metric_sources_then_review_license_and_claim_receipt"
        ),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_candidate_queue(
    *,
    statistical_support_work_order_json: str | Path = DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    current_work_order_csv: str | Path = DEFAULT_CURRENT_WORK_ORDER_CSV,
    seed_csv: str | Path = DEFAULT_WORK_ORDER_SEED_CSV,
    affinity_tsv: str | Path = DEFAULT_WORK_ORDER_AFFINITY_TSV,
    dataset_dir: str | Path = DEFAULT_WORK_ORDER_DATASET_DIR,
    max_pose_rmsd_a: float = MAX_POSE_RMSD_A,
    root: Path = ROOT,
) -> dict[str, Any]:
    stat_payload, stat_present = _read_json(statistical_support_work_order_json, root=root)
    stat_summary = _summary(stat_payload)
    slot_rows = _rows(stat_payload)
    current_work_order_rows, current_work_order_columns, current_work_order_present = _read_csv(
        current_work_order_csv,
        root=root,
    )
    seed_rows, seed_columns, seed_present = _read_csv(seed_csv, root=root)
    experimental_delta_g_by_complex, experimental_delta_g_summary = _read_experimental_delta_g_by_complex(
        affinity_tsv,
        root=root,
    )
    existing_target_ids = _existing_targets(current_work_order_rows)
    candidate_pool, candidate_pool_summary = _candidate_pool(
        seed_rows,
        existing_target_ids=existing_target_ids,
        max_pose_rmsd_a=max_pose_rmsd_a,
    )
    selected = candidate_pool[: len(slot_rows)]
    rows = [
        _candidate_row(
            slot_row=slot_row,
            candidate_rank=index,
            candidate=candidate,
            experimental_delta_g_by_complex=experimental_delta_g_by_complex,
            dataset_dir=dataset_dir,
            root=root,
        )
        for index, (slot_row, candidate) in enumerate(zip(slot_rows, selected), start=1)
    ]
    blockers: list[str] = []
    if not stat_present:
        blockers.append("statistical_support_work_order_missing")
    if not current_work_order_present:
        blockers.append("current_work_order_csv_missing")
    if not seed_present:
        blockers.append("seed_csv_missing")
    if not experimental_delta_g_summary["experimental_deltaG_source_present"]:
        blockers.append("experimental_deltaG_source_missing")
    if len(selected) < len(slot_rows):
        blockers.append("insufficient_candidate_rows_for_expansion_slots")

    holdout_selected_count = sum(1 for row in rows if row["required_split"] == "holdout")
    fit_or_holdout_selected_count = sum(1 for row in rows if row["required_split"] == "fit_or_holdout")
    receptor_present_count = sum(1 for row in rows if row["receptor_coordinate_artifact_present"] is True)
    ligand_present_count = sum(1 for row in rows if row["ligand_pose_artifact_present"] is True)
    experimental_delta_g_prefilled_count = sum(1 for row in rows if _text(row["deltaG_experimental_kcal_mol"]))
    metric_materialization_ready_count = sum(
        1 for row in rows if row["candidate_ready_for_metric_materialization"] is True
    )
    canonical_ready_count = sum(1 for row in rows if row["candidate_ready_for_canonical_intake"] is True)
    receptor_missing_count = len(rows) - receptor_present_count

    queue_ready = bool(
        stat_present
        and current_work_order_present
        and seed_present
        and experimental_delta_g_summary["experimental_deltaG_source_present"]
        and len(selected) == len(slot_rows)
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_candidate_queue",
        "status": (
            "refine_tier_public_benchmark_statistical_support_candidate_queue_ready"
            if queue_ready
            else "blocked_refine_tier_public_benchmark_statistical_support_candidate_queue"
        ),
        "candidate_queue_ready": queue_ready,
        "statistical_support_work_order": _display(statistical_support_work_order_json, root=root),
        "statistical_support_work_order_present": stat_present,
        "statistical_support_work_order_ready": bool(
            stat_summary.get("status") == "refine_tier_public_benchmark_statistical_support_work_order_ready"
        ),
        "current_work_order_csv": _display(current_work_order_csv, root=root),
        "current_work_order_csv_present": current_work_order_present,
        "current_work_order_row_count": len(current_work_order_rows),
        "current_work_order_column_count": len(current_work_order_columns),
        "existing_target_exclusion_count": len(existing_target_ids),
        "seed_csv": _display(seed_csv, root=root),
        "seed_csv_present": seed_present,
        "seed_column_count": len(seed_columns),
        "seed_source_row_count": len(seed_rows),
        "max_pose_rmsd_A": float(max_pose_rmsd_a),
        "dataset_dir": _display(dataset_dir, root=root),
        "expansion_slot_count": len(slot_rows),
        "selected_candidate_count": len(rows),
        "holdout_selected_candidate_count": holdout_selected_count,
        "fit_or_holdout_selected_candidate_count": fit_or_holdout_selected_count,
        "ligand_pose_artifact_present_count": ligand_present_count,
        "receptor_coordinate_artifact_present_count": receptor_present_count,
        "receptor_coordinate_artifact_missing_count": receptor_missing_count,
        "experimental_deltaG_prefilled_count": experimental_delta_g_prefilled_count,
        "candidate_ready_for_metric_materialization_count": metric_materialization_ready_count,
        "candidate_ready_for_canonical_intake_count": canonical_ready_count,
        "canonical_intake_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        **experimental_delta_g_summary,
        **candidate_pool_summary,
        "next_required_step": (
            "Review and place public receptor/complex coordinate artifacts for the selected 17 candidates, "
            "then materialize DockQ, lDDT-PLI, and internal DeltaG source payloads before canonical intake "
            "or claim receipt promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# R9 Public-Benchmark Statistical Support Candidate Queue",
                "",
                f"- status: `{summary['status']}`",
                f"- selected_candidate_count: `{summary['selected_candidate_count']}`",
                f"- holdout_selected_candidate_count: `{summary['holdout_selected_candidate_count']}`",
                f"- ligand_pose_artifact_present_count: `{summary['ligand_pose_artifact_present_count']}`",
                f"- receptor_coordinate_artifact_present_count: `{summary['receptor_coordinate_artifact_present_count']}`",
                f"- experimental_deltaG_prefilled_count: `{summary['experimental_deltaG_prefilled_count']}`",
                f"- candidate_ready_for_metric_materialization_count: `{summary['candidate_ready_for_metric_materialization_count']}`",
                f"- candidate_ready_for_canonical_intake_count: `{summary['candidate_ready_for_canonical_intake_count']}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
                "## Next Required Step",
                "",
                summary["next_required_step"],
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Build a local candidate queue for R9 public-benchmark statistical-support expansion."
    )
    parser.add_argument(
        "--statistical-support-work-order-json",
        default=DEFAULT_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    )
    parser.add_argument("--current-work-order-csv", default=DEFAULT_CURRENT_WORK_ORDER_CSV)
    parser.add_argument("--seed-csv", default=DEFAULT_WORK_ORDER_SEED_CSV)
    parser.add_argument("--affinity-tsv", default=DEFAULT_WORK_ORDER_AFFINITY_TSV)
    parser.add_argument("--dataset-dir", default=DEFAULT_WORK_ORDER_DATASET_DIR)
    parser.add_argument("--max-pose-rmsd-a", type=float, default=MAX_POSE_RMSD_A)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_candidate_queue(
        statistical_support_work_order_json=args.statistical_support_work_order_json,
        current_work_order_csv=args.current_work_order_csv,
        seed_csv=args.seed_csv,
        affinity_tsv=args.affinity_tsv,
        dataset_dir=args.dataset_dir,
        max_pose_rmsd_a=args.max_pose_rmsd_a,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
