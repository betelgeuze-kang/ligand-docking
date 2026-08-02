#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np

from core.mm_gbsa import mm_gbsa_binding_energy
from core.structure_metrics import parse_pdb_atoms_with_coords
from tools.accounting.build_pdbbind_casf_pose_affinity_results import (
    _coords as _ligand_coords,
    _load_ligand,
    _pose_rank,
)
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    _input_artifact_sha256,
    _ligand_descriptor_props,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POSE_RESULTS_CSV = "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv"
DEFAULT_METRIC_MATERIALIZATION_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_OUT_CSV = "runs/pdbbind_casf_pose_affinity_fixed_gold_metadata_current.csv"
DEFAULT_OUT_JSON = "runs/pdbbind_casf_pose_affinity_fixed_gold_metadata_current.json"
DEFAULT_OUT_MD = "runs/pdbbind_casf_pose_affinity_fixed_gold_metadata_current.md"
CLAIM_BOUNDARY = (
    "Restricted local fixed PDBbind/CASF pose-replay metadata builder. Active/decoy pose labels are derived "
    "from public reference-ligand RMSD thresholds for pose-recovery diagnostics, not experimental inactive "
    "ligand labels. Scores use local internal MM/GBSA proxy values for already-local pose artifacts. The output "
    "does not run docking, download data, claim official CASF scoring/ranking parity, or promote customer claims."
)
FIELDS = [
    "pose_id",
    "complex_id",
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
    "runtime_ms",
    "peak_memory_mb",
    "label_source",
    "score_source",
    "baseline_score_source",
    "claim_boundary",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        out = float(_text(value))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _read_csv(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _format(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.6f}"


def _split(value: Any) -> str:
    text = _text(value).lower().replace("-", "_")
    return "heldout" if text in {"holdout", "held_out", "heldout"} else (text or "heldout")


def _rows_by_complex(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("complex_id")), []).append(row)
    return grouped


def _load_ligand_coords(path_like: str | Path) -> np.ndarray:
    return np.asarray(_ligand_coords(_load_ligand(_resolve(path_like))), dtype=np.float64)


def _load_receptor_coords(path_like: str | Path) -> np.ndarray:
    text = _resolve(path_like).read_text(encoding="utf-8", errors="replace")
    atoms = parse_pdb_atoms_with_coords(text)
    coords = [np.asarray(atom["xyz"], dtype=np.float64) for atom in atoms if atom.get("record") == "ATOM"]
    return np.asarray(coords, dtype=np.float64)


def _receptor_artifact(row: dict[str, Any]) -> str:
    artifacts = [_text(value) for value in _text(row.get("input_artifacts")).split(";") if _text(value)]
    return next((artifact for artifact in artifacts if artifact.endswith(".pdb")), "")


def _pick_decoy(rows: list[dict[str, Any]], *, active_pose_id: str, min_rmsd_a: float) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if _text(row.get("pose_id")) != active_pose_id
        and (_float(row.get("pose_rmsd_A")) is not None)
        and float(row["pose_rmsd_A"]) >= float(min_rmsd_a)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: float(row["pose_rmsd_A"]))


def _score_decoy(row: dict[str, Any], *, receptor_coords: np.ndarray) -> tuple[float | None, float, float, list[str]]:
    blockers: list[str] = []
    start = time.perf_counter()
    tracemalloc.start()
    score: float | None = None
    try:
        ligand_coords = _load_ligand_coords(_text(row.get("pose_artifact")))
        score = float(
            mm_gbsa_binding_energy(
                receptor_coords,
                ligand_coords,
                props=_ligand_descriptor_props(_text(row.get("pose_artifact"))),
            )["internal_refine_proxy_score"]
        )
    except Exception as exc:  # noqa: BLE001 - row-level metadata must fail closed.
        blockers.append(f"decoy_score_failed:{type(exc).__name__}")
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    runtime_ms = max((time.perf_counter() - start) * 1000.0, 0.001)
    peak_memory_mb = max(float(peak) / (1024.0 * 1024.0), 0.001)
    return score, runtime_ms, peak_memory_mb, blockers


def _metadata_row(
    *,
    pose_id: str,
    complex_id: str,
    active: bool,
    affinity_label: float,
    score: float,
    baseline_score: float,
    split_id: str,
    runtime_ms: float,
    peak_memory_mb: float,
    label_source: str,
    score_source: str,
) -> dict[str, Any]:
    return {
        "pose_id": pose_id,
        "complex_id": complex_id,
        "active_label": "1" if active else "0",
        "affinity_label": _format(affinity_label),
        "score": _format(score),
        "baseline_score": _format(baseline_score),
        "split_id": split_id,
        "abstained": "0" if active else "1",
        "abstention_reasons": "" if active else "high_rmsd_decoy_pose_replay",
        "chirality_failure": "0",
        "tautomer_failure": "0",
        "protonation_failure": "0",
        "runtime_ms": _format(runtime_ms),
        "peak_memory_mb": _format(peak_memory_mb),
        "label_source": label_source,
        "score_source": score_source,
        "baseline_score_source": "pose_rank_unrefined_baseline",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_pdbbind_casf_fixed_gold_metadata(
    *,
    pose_results_csv: str | Path = DEFAULT_POSE_RESULTS_CSV,
    metric_materialization_csv: str | Path = DEFAULT_METRIC_MATERIALIZATION_CSV,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_md: str | Path = DEFAULT_OUT_MD,
    decoy_min_rmsd_a: float = 5.0,
) -> dict[str, Any]:
    pose_rows = _read_csv(pose_results_csv)
    metric_rows = [
        row
        for row in _read_csv(metric_materialization_csv)
        if _text(row.get("metric_materialization_status")) == "pass"
    ]
    by_complex = _rows_by_complex(pose_rows)
    metadata_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    receptor_cache: dict[str, np.ndarray] = {}
    for metric in metric_rows:
        complex_id = _text(metric.get("target_id"))
        active_pose_id = _text(metric.get("pose_id"))
        pose_candidates = by_complex.get(complex_id, [])
        active_pose = next((row for row in pose_candidates if _text(row.get("pose_id")) == active_pose_id), None)
        receptor = _receptor_artifact(metric)
        decoy = _pick_decoy(pose_candidates, active_pose_id=active_pose_id, min_rmsd_a=decoy_min_rmsd_a)
        row_blockers: list[str] = []
        if active_pose is None:
            row_blockers.append("active_pose_result_missing")
        if decoy is None:
            row_blockers.append("high_rmsd_decoy_missing")
        if not receptor:
            row_blockers.append("receptor_artifact_missing")
        affinity_label = -float(_float(metric.get("deltaG_experimental_kcal_mol")) or 0.0)
        active_score = _float(metric.get("internal_refine_proxy_score"))
        if active_score is None:
            row_blockers.append("active_internal_deltaG_missing")
        receptor_coords = np.zeros((0, 3), dtype=np.float64)
        if receptor:
            try:
                receptor_coords = receptor_cache.setdefault(receptor, _load_receptor_coords(receptor))
            except Exception as exc:  # noqa: BLE001 - row-level metadata must fail closed.
                row_blockers.append(f"receptor_parse_failed:{type(exc).__name__}")
        if row_blockers:
            blockers.extend(f"{complex_id}:{blocker}" for blocker in row_blockers)
            continue
        assert active_pose is not None
        assert decoy is not None
        assert active_score is not None
        decoy_score, decoy_runtime_ms, decoy_peak_memory_mb, decoy_blockers = _score_decoy(
            decoy,
            receptor_coords=receptor_coords,
        )
        if decoy_score is None or decoy_blockers:
            blockers.extend(f"{complex_id}:{blocker}" for blocker in decoy_blockers or ["decoy_score_missing"])
            continue
        split_id = _split(metric.get("split"))
        active_runtime_ms = _float(active_pose.get("runtime_ms")) or 0.001
        active_peak_memory_mb = _float(active_pose.get("peak_memory_mb")) or 0.001
        metadata_rows.append(
            _metadata_row(
                pose_id=active_pose_id,
                complex_id=complex_id,
                active=True,
                affinity_label=affinity_label,
                score=float(active_score),
                baseline_score=float(_pose_rank(Path(active_pose_id))),
                split_id=split_id,
                runtime_ms=active_runtime_ms,
                peak_memory_mb=active_peak_memory_mb,
                label_source="rmsd_le_2A_public_reference_pose_replay",
                score_source="materialized_internal_contact_normalized_mm_gbsa_v2",
            )
        )
        metadata_rows.append(
            _metadata_row(
                pose_id=_text(decoy.get("pose_id")),
                complex_id=complex_id,
                active=False,
                affinity_label=affinity_label,
                score=float(decoy_score),
                baseline_score=float(_pose_rank(Path(_text(decoy.get("pose_id"))))),
                split_id=split_id,
                runtime_ms=decoy_runtime_ms,
                peak_memory_mb=decoy_peak_memory_mb,
                label_source=f"rmsd_ge_{float(decoy_min_rmsd_a):.1f}A_public_reference_pose_replay",
                score_source="computed_internal_contact_normalized_mm_gbsa_v2",
            )
        )
        manifest_rows.append(
            {
                "complex_id": complex_id,
                "split_id": split_id,
                "active_pose_id": active_pose_id,
                "active_pose_rmsd_A": _text(active_pose.get("pose_rmsd_A")),
                "decoy_pose_id": _text(decoy.get("pose_id")),
                "decoy_pose_rmsd_A": _text(decoy.get("pose_rmsd_A")),
                "receptor_artifact": receptor,
                "receptor_artifact_sha256": _input_artifact_sha256(receptor),
                "active_score_source": "materialized_internal_contact_normalized_mm_gbsa_v2",
                "decoy_score_source": "computed_internal_contact_normalized_mm_gbsa_v2",
            }
        )
    out_csv_path = _resolve(out_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with out_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(metadata_rows)
    summary = {
        "packet_type": "pdbbind_casf_fixed_gold_metadata",
        "schema_version": "pdbbind_casf_fixed_gold_metadata_v1",
        "status": "pdbbind_casf_fixed_gold_metadata_ready" if metadata_rows and not blockers else "blocked_pdbbind_casf_fixed_gold_metadata",
        "pass": bool(metadata_rows and not blockers),
        "pose_results_csv": str(_resolve(pose_results_csv)),
        "metric_materialization_csv": str(_resolve(metric_materialization_csv)),
        "out_csv": str(out_csv_path),
        "metadata_row_count": len(metadata_rows),
        "complex_count": len({row["complex_id"] for row in metadata_rows}),
        "active_row_count": sum(1 for row in metadata_rows if row["active_label"] == "1"),
        "decoy_row_count": sum(1 for row in metadata_rows if row["active_label"] == "0"),
        "heldout_complex_count": len({row["complex_id"] for row in metadata_rows if row["split_id"] == "heldout"}),
        "decoy_min_rmsd_A": float(decoy_min_rmsd_a),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    payload = {"summary": summary, "rows": manifest_rows}
    _resolve(out_json).parent.mkdir(parents=True, exist_ok=True)
    _resolve(out_json).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _resolve(out_md).write_text(
        "\n".join(
            [
                "# PDBbind/CASF Fixed Gold Metadata",
                "",
                f"- status: `{summary['status']}`",
                f"- metadata_row_count: `{summary['metadata_row_count']}`",
                f"- complex_count: `{summary['complex_count']}`",
                f"- heldout_complex_count: `{summary['heldout_complex_count']}`",
                f"- blocker_count: `{summary['blocker_count']}`",
                "",
                "## Claim Boundary",
                "",
                CLAIM_BOUNDARY,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed PDBbind/CASF gold metadata for the local P0-3 slice.")
    parser.add_argument("--pose-results-csv", default=DEFAULT_POSE_RESULTS_CSV)
    parser.add_argument("--metric-materialization-csv", default=DEFAULT_METRIC_MATERIALIZATION_CSV)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--decoy-min-rmsd-a", type=float, default=5.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_pdbbind_casf_fixed_gold_metadata(
        pose_results_csv=args.pose_results_csv,
        metric_materialization_csv=args.metric_materialization_csv,
        out_csv=args.out_csv,
        out_json=args.out_json,
        out_md=args.out_md,
        decoy_min_rmsd_a=args.decoy_min_rmsd_a,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
