#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import time
import tracemalloc
from pathlib import Path
from typing import Any

from rdkit import Chem

from betelgeuze_engine.benchmark.docking_gold import DockingGoldRow, evaluate_docking_gold_slice

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float_or_none(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool_or_none(value: Any) -> bool | None:
    text = _text(value).lower()
    if text in {"1", "true", "yes", "active"}:
        return True
    if text in {"0", "false", "no", "decoy"}:
        return False
    return None


def _load_gold_metadata(path_like: str | Path) -> dict[str, dict[str, Any]]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            payload = dict(row)
            pose_id = _text(payload.get("pose_id"))
            complex_id = _text(payload.get("complex_id"))
            if pose_id:
                metadata[pose_id] = payload
            if complex_id:
                metadata.setdefault(complex_id, payload)
    return metadata


def _coords(mol: Any) -> list[tuple[float, float, float]]:
    conformer = mol.GetConformer()
    coords: list[tuple[float, float, float]] = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue
        point = conformer.GetAtomPosition(atom.GetIdx())
        coords.append((float(point.x), float(point.y), float(point.z)))
    return coords


def _heavy_atom_elements(mol: Any) -> list[str]:
    return [str(atom.GetSymbol()) for atom in mol.GetAtoms() if atom.GetAtomicNum() != 1]


def _direct_rmsd(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float | None:
    if not a or len(a) != len(b):
        return None
    total = 0.0
    for (ax, ay, az), (bx, by, bz) in zip(a, b):
        total += (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
    return math.sqrt(total / len(a))


def _symmetry_aware_heavy_atom_rmsd(ref_mol: Any, pose_mol: Any) -> tuple[float | None, dict[str, Any]]:
    ref_coords = _coords(ref_mol)
    pose_coords = _coords(pose_mol)
    ref_elements = _heavy_atom_elements(ref_mol)
    pose_elements = _heavy_atom_elements(pose_mol)
    diagnostics: dict[str, Any] = {
        "method": "rdkit_self_substructure_automorphism_no_ligand_alignment",
        "reference_heavy_atom_count": len(ref_coords),
        "pose_heavy_atom_count": len(pose_coords),
        "symmetry_mapping_count": 0,
        "atom_identity_checked": True,
        "ligand_alignment_applied": False,
    }
    if not ref_coords or len(ref_coords) != len(pose_coords):
        diagnostics["status"] = "heavy_atom_count_mismatch"
        return None, diagnostics
    if ref_elements != pose_elements:
        diagnostics["status"] = "heavy_atom_element_order_mismatch"
        return None, diagnostics
    try:
        ref_heavy = Chem.RemoveHs(ref_mol)
        mappings = ref_heavy.GetSubstructMatches(ref_heavy, uniquify=False, maxMatches=512)
    except Exception:
        mappings = ()
    candidates = [tuple(range(len(ref_coords)))]
    for mapping in mappings:
        if len(mapping) == len(ref_coords):
            candidates.append(tuple(int(idx) for idx in mapping))
    seen: set[tuple[int, ...]] = set()
    best: float | None = None
    for mapping in candidates:
        if mapping in seen:
            continue
        seen.add(mapping)
        if any(ref_elements[int(ref_idx)] != pose_elements[pose_idx] for pose_idx, ref_idx in enumerate(mapping)):
            continue
        mapped_ref = [ref_coords[int(ref_idx)] for ref_idx in mapping]
        value = _direct_rmsd(mapped_ref, pose_coords)
        if value is not None and (best is None or value < best):
            best = value
    diagnostics["symmetry_mapping_count"] = len(seen)
    diagnostics["status"] = "symmetry_aware_rmsd_computed" if best is not None else "symmetry_mapping_failed"
    return best, diagnostics


def _load_ligand(path: Path) -> Any:
    payload = pickle.loads(path.read_bytes())
    if isinstance(payload, tuple) and payload:
        return payload[0]
    return payload


def _reference_path(data_dir: Path, complex_id: str) -> Path | None:
    for candidate in [data_dir / complex_id, data_dir / f"{complex_id}_ligand"]:
        if candidate.exists():
            return candidate
    return None


def _is_pose_file(path: Path) -> bool:
    name = path.name
    if name.endswith("_ligand"):
        return False
    if "_" not in name:
        return False
    suffix = name.rsplit("_", 1)[-1]
    return suffix.isdigit()


def _pose_rank(path: Path) -> int:
    try:
        return int(path.name.rsplit("_", 1)[-1])
    except (IndexError, ValueError):
        return 10**9


def _chemistry_failures_from_metadata(metadata: dict[str, Any]) -> tuple[tuple[str, ...], bool]:
    fields = {
        "chirality_failure": "chirality_failure",
        "tautomer_failure": "tautomer_failure",
        "protonation_failure": "protonation_failure",
    }
    evidence_present = all(_text(metadata.get(field)) for field in fields)
    failures = [
        token
        for field, token in fields.items()
        if _bool_or_none(metadata.get(field)) is True
    ]
    return tuple(failures), evidence_present


def build_results(args: argparse.Namespace) -> dict[str, Any]:
    dataset = _resolve(args.dataset_artifact)
    data_dir = dataset / "data_5_sdf"
    pose_files = sorted(path for path in data_dir.iterdir() if path.is_file() and _is_pose_file(path)) if data_dir.exists() else []
    if int(args.max_poses) > 0:
        pose_files = pose_files[: int(args.max_poses)]
    rows: list[dict[str, Any]] = []
    threshold = float(args.pose_success_rmsd_a)
    gold_metadata = _load_gold_metadata(args.gold_metadata_csv) if _text(getattr(args, "gold_metadata_csv", "")) else {}

    for pose_path in pose_files:
        complex_id = pose_path.name.split("_", 1)[0]
        metadata = gold_metadata.get(pose_path.name, gold_metadata.get(complex_id, {}))
        reference = _reference_path(data_dir, complex_id)
        blockers: list[str] = []
        rmsd: float | None = None
        ref_atom_count = 0
        pose_atom_count = 0
        rmsd_diagnostics: dict[str, Any] = {}
        row_start = time.perf_counter()
        tracemalloc.start()
        if reference is None:
            blockers.append("reference_ligand_missing")
        else:
            try:
                ref_mol = _load_ligand(reference)
                pose_mol = _load_ligand(pose_path)
                rmsd, rmsd_diagnostics = _symmetry_aware_heavy_atom_rmsd(ref_mol, pose_mol)
                ref_atom_count = int(rmsd_diagnostics.get("reference_heavy_atom_count") or 0)
                pose_atom_count = int(rmsd_diagnostics.get("pose_heavy_atom_count") or 0)
                if rmsd is None:
                    blockers.append(str(rmsd_diagnostics.get("status") or "pose_rmsd_not_computable"))
            except Exception as exc:  # noqa: BLE001 - artifact parser should report concrete row-level failure.
                blockers.append(f"rdkit_pickle_parse_failed:{type(exc).__name__}")
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        runtime_ms = max((time.perf_counter() - row_start) * 1000.0, 0.001)
        peak_memory_mb = max(float(peak_bytes) / (1024.0 * 1024.0), 0.001)
        chemistry_failures, chemistry_evidence_present = _chemistry_failures_from_metadata(metadata)
        if not chemistry_evidence_present:
            blockers.append("chemistry_failure_evidence_missing")
        success = rmsd is not None and rmsd <= threshold and not blockers
        rows.append(
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": complex_id,
                "pose_id": pose_path.name,
                "pose_success": int(success),
                "pose_rmsd_A": rmsd if rmsd is not None else "",
                "pose_success_rmsd_threshold_A": threshold,
                "reference_ligand": str(reference or ""),
                "pose_artifact": str(pose_path),
                "reference_heavy_atom_count": ref_atom_count,
                "pose_heavy_atom_count": pose_atom_count,
                "pose_rmsd_method": str(rmsd_diagnostics.get("method", "")),
                "pose_rmsd_diagnostics": json.dumps(rmsd_diagnostics, sort_keys=True),
                "blocker_count": len(blockers),
                "blockers": ";".join(blockers),
                "active_label": _text(metadata.get("active_label")),
                "affinity_label": _text(metadata.get("affinity_label")),
                "score": _text(metadata.get("score")),
                "baseline_score": _text(metadata.get("baseline_score")),
                "split_id": _text(metadata.get("split_id") or "heldout"),
                "abstained": _text(metadata.get("abstained")),
                "abstention_reasons": _text(metadata.get("abstention_reasons")),
                "chirality_failure": _text(metadata.get("chirality_failure")),
                "tautomer_failure": _text(metadata.get("tautomer_failure")),
                "protonation_failure": _text(metadata.get("protonation_failure")),
                "chemistry_evidence_present": int(chemistry_evidence_present),
                "runtime_ms": f"{runtime_ms:.6f}",
                "peak_memory_mb": f"{peak_memory_mb:.6f}",
                "runtime_metric_source": "builder_wall_clock_perf_counter",
                "peak_memory_metric_source": "builder_tracemalloc_peak",
            }
        )

    scored_rows = [row for row in rows if _text(row.get("pose_rmsd_A"))]
    pose_success_count = sum(1 for row in rows if int(row.get("pose_success") or 0) == 1)
    pose_success_rate = pose_success_count / len(rows) if rows else 0.0
    by_complex: dict[str, list[float]] = {}
    for row in scored_rows:
        try:
            rmsd = float(row["pose_rmsd_A"])
        except (TypeError, ValueError):
            continue
        by_complex.setdefault(_text(row.get("complex_id")), []).append(rmsd)
    complex_success_count = sum(1 for values in by_complex.values() if min(values) <= threshold)
    complex_success_rate = complex_success_count / len(by_complex) if by_complex else 0.0
    gold_metrics = evaluate_docking_gold_slice(
        [
            DockingGoldRow(
                complex_id=_text(row.get("complex_id")),
                pose_id=_text(row.get("pose_id")),
                pose_rank=_pose_rank(Path(_text(row.get("pose_id")))),
                pose_rmsd_a=float(row["pose_rmsd_A"]) if _text(row.get("pose_rmsd_A")) else None,
                score=_float_or_none(row.get("score")),
                baseline_score=_float_or_none(row.get("baseline_score")),
                affinity_label=_float_or_none(row.get("affinity_label")),
                active_label=_bool_or_none(row.get("active_label")),
                split_id=_text(row.get("split_id") or "heldout"),
                abstained=bool(_bool_or_none(row.get("abstained")) is True),
                chemistry_failures=tuple(
                    failure
                    for failure in [
                        "chirality_failure" if _bool_or_none(row.get("chirality_failure")) is True else "",
                        "tautomer_failure" if _bool_or_none(row.get("tautomer_failure")) is True else "",
                        "protonation_failure" if _bool_or_none(row.get("protonation_failure")) is True else "",
                    ]
                    if failure
                ),
                chemistry_evidence_present=bool(int(row.get("chemistry_evidence_present") or 0)),
                abstention_reasons=tuple(
                    reason for reason in _text(row.get("abstention_reasons")).split(";") if reason
                ),
                runtime_ms=_float_or_none(row.get("runtime_ms")),
                peak_memory_mb=_float_or_none(row.get("peak_memory_mb")),
            )
            for row in rows
        ],
        pose_success_rmsd_a=threshold,
        top_k=5,
    )
    primary_threshold = float(args.threshold)
    blockers: list[str] = []
    if not dataset.exists():
        blockers.append("dataset_artifact_missing")
    if not data_dir.exists():
        blockers.append("data_5_sdf_dir_missing")
    if not rows:
        blockers.append("pose_files_missing")
    if any(int(row.get("blocker_count") or 0) > 0 for row in rows):
        blockers.append("row_level_benchmark_blockers_present")
    if complex_success_rate + 1e-12 < primary_threshold:
        blockers.append("pose_success_rate_below_threshold")
    if gold_metrics.status != "pass":
        blockers.append("gold_metrics_blocked")

    out_csv = _resolve(args.out_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    fields = [
        "suite_id",
        "complex_id",
        "pose_id",
        "pose_success",
        "pose_rmsd_A",
        "pose_success_rmsd_threshold_A",
        "reference_ligand",
        "pose_artifact",
        "reference_heavy_atom_count",
        "pose_heavy_atom_count",
        "pose_rmsd_method",
        "pose_rmsd_diagnostics",
        "blocker_count",
        "blockers",
        "active_label",
        "affinity_label",
        "score",
        "baseline_score",
        "split_id",
        "abstained",
        "abstention_reasons",
        "chirality_failure",
        "tautomer_failure",
        "protonation_failure",
        "chemistry_evidence_present",
        "runtime_ms",
        "peak_memory_mb",
        "runtime_metric_source",
        "peak_memory_metric_source",
    ]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    summary = {
        "packet_type": "pdbbind_casf_pose_affinity_results",
        "suite_id": "pdbbind_casf_pose_affinity",
        "status": "pdbbind_casf_pose_affinity_results_ready" if not blockers else "blocked_pdbbind_casf_pose_affinity_results",
        "pass": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "dataset_artifact": str(dataset),
        "data_5_sdf_dir": str(data_dir),
        "pose_count": len(rows),
        "scored_pose_count": len(scored_rows),
        "pose_success_count": pose_success_count,
        "pose_success_rate": complex_success_rate,
        "pose_row_success_rate": pose_success_rate,
        "top1_mean_rmsd_A": gold_metrics.top1_mean_rmsd_a,
        "top5_best_mean_rmsd_A": gold_metrics.top5_best_mean_rmsd_a,
        "top1_pose_success_rate": gold_metrics.top1_pose_success_rate,
        "top5_pose_success_rate": gold_metrics.top5_pose_success_rate,
        "ranking_spearman": gold_metrics.ranking_spearman,
        "pr_auc": gold_metrics.pr_auc,
        "topk_hit_rate": gold_metrics.topk_hit_rate,
        "decoy_rejection_rate": gold_metrics.decoy_rejection_rate,
        "baseline_ranking_spearman": gold_metrics.baseline_ranking_spearman,
        "refine_ranking_spearman_delta": gold_metrics.refine_ranking_spearman_delta,
        "refine_improvement_observed": gold_metrics.refine_improvement_observed,
        "heldout_complex_count": gold_metrics.heldout_complex_count,
        "chirality_failure_rate": gold_metrics.chirality_failure_rate,
        "tautomer_failure_rate": gold_metrics.tautomer_failure_rate,
        "protonation_failure_rate": gold_metrics.protonation_failure_rate,
        "chemistry_evidence_coverage": gold_metrics.chemistry_evidence_coverage,
        "abstention_precision": gold_metrics.abstention_precision,
        "mean_runtime_ms": gold_metrics.mean_runtime_ms,
        "peak_memory_mb": gold_metrics.peak_memory_mb,
        "gold_metric_schema_version": gold_metrics.schema_version,
        "gold_metric_status": gold_metrics.status,
        "gold_metric_blockers": list(gold_metrics.blockers),
        "gold_metadata_csv": str(_resolve(args.gold_metadata_csv)) if _text(getattr(args, "gold_metadata_csv", "")) else "",
        "pose_rmsd_method": "rdkit_self_substructure_automorphism_no_ligand_alignment",
        "runtime_metric_source": "builder_wall_clock_perf_counter",
        "peak_memory_metric_source": "builder_tracemalloc_peak",
        "complex_count": len(by_complex),
        "complex_pose_success_count": complex_success_count,
        "complex_pose_success_rate": complex_success_rate,
        "primary_metric": "pose_success_rate",
        "primary_metric_value": complex_success_rate,
        "primary_metric_threshold": primary_threshold,
        "pose_success_rmsd_threshold_A": threshold,
        "out_csv": str(out_csv),
        "external_state_mutated": False,
        "download_executed": False,
        "prediction_generation_enabled": False,
        "claim_boundary": (
            "PDBbind/CASF pose-affinity adapter only; it reads local RDKit-pickled CASF ligand/reference pose pairs "
            "and computes symmetry-aware heavy-atom RMSD in the receptor frame without ligand superposition. The "
            "primary pose_success_rate is aggregated "
            "per complex by best available pose, while pose_row_success_rate remains reported as a diagnostic. It does "
            "not run docking, train affinity models, use external SaaS, download data, or claim official CASF "
            "scoring/ranking performance."
        ),
        "next_required_step": (
            "Fingerprint this result CSV, build the suite scorecard, then refresh public benchmark gates."
            if rows
            else "Repair local CASF pose files, then rebuild these results."
        ),
    }
    payload = {"summary": summary, "rows": rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# PDBbind/CASF Pose Affinity Results",
                "",
                f"- status: `{summary['status']}`",
                f"- pose_count: `{summary['pose_count']}`",
                f"- pose_success_rate: `{summary['pose_success_rate']}`",
                f"- threshold: `{summary['primary_metric_threshold']}`",
                f"- out_csv: `{out_csv}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PDBbind/CASF local pose RMSD proxy results from RDKit pickle files.")
    parser.add_argument("--dataset-artifact", default="data/public_benchmarks/pdbbind_casf_pose_affinity")
    parser.add_argument("--max-poses", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--pose-success-rmsd-a", type=float, default=2.0)
    parser.add_argument("--gold-metadata-csv", default="")
    parser.add_argument("--out-csv", default="runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv")
    parser.add_argument("--out-json", default="runs/pdbbind_casf_pose_affinity_results_current.json")
    parser.add_argument("--out-md", default="runs/pdbbind_casf_pose_affinity_results_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_results(parse_args(argv))


if __name__ == "__main__":
    main()
