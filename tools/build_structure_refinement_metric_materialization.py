#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    text as _text,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_QUEUE_JSON = "runs/structure_refinement_metric_queue_current.json"
DEFAULT_OUT_JSON = "runs/structure_refinement_metric_materialization_current.json"
DEFAULT_OUT_CSV = "runs/structure_refinement_metric_materialization_current.csv"
DEFAULT_OUT_MD = "runs/structure_refinement_metric_materialization_current.md"


def _queue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else []


def _ca_coords(path_like: str | Path) -> np.ndarray:
    coords: list[list[float]] = []
    path = _resolve(path_like)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        parts = line.split()
        if len(parts) >= 9 and parts[2] == "CA":
            try:
                coords.append([float(parts[6]), float(parts[7]), float(parts[8])])
                continue
            except ValueError:
                pass
        if line[12:16].strip() == "CA":
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            except ValueError:
                continue
    return np.asarray(coords, dtype=float)


def _aligned_ca_pair(reference: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = min(int(reference.shape[0]), int(candidate.shape[0]))
    if count < 3:
        empty = np.asarray([], dtype=float)
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=float), empty
    ref = np.asarray(reference[:count], dtype=float)
    mob = np.asarray(candidate[:count], dtype=float)
    ref_centroid = ref.mean(axis=0)
    mob_centroid = mob.mean(axis=0)
    ref_centered = ref - ref_centroid
    mob_centered = mob - mob_centroid
    covariance = mob_centered.T @ ref_centered
    u, _, vt = np.linalg.svd(covariance)
    sign = np.sign(np.linalg.det(u @ vt))
    correction = np.diag([1.0, 1.0, sign])
    rotation = u @ correction @ vt
    aligned = mob_centered @ rotation + ref_centroid
    distances = np.linalg.norm(aligned - ref, axis=1)
    return ref, aligned, distances


def _kabsch_rmsd(reference: np.ndarray, candidate: np.ndarray) -> tuple[float | None, np.ndarray]:
    _, _, distances = _aligned_ca_pair(reference, candidate)
    if distances.size == 0:
        return None, distances
    return float(math.sqrt(np.mean(distances**2))), distances


def _gdt_ts_proxy(distances: np.ndarray) -> float | None:
    if distances.size == 0:
        return None
    return float(
        np.mean(
            [
                np.mean(distances <= 1.0),
                np.mean(distances <= 2.0),
                np.mean(distances <= 4.0),
                np.mean(distances <= 8.0),
            ]
        )
    )


def _tm_score_ca_proxy(distances: np.ndarray) -> float | None:
    if distances.size == 0:
        return None
    length = int(distances.size)
    d0 = 0.5 if length <= 21 else (1.24 * ((length - 15) ** (1.0 / 3.0)) - 1.8)
    d0 = max(float(d0), 0.5)
    return float(np.mean(1.0 / (1.0 + (distances / d0) ** 2)))


def _lddt_ca_proxy(reference: np.ndarray, aligned_candidate: np.ndarray, cutoff_A: float = 15.0) -> float | None:
    count = min(int(reference.shape[0]), int(aligned_candidate.shape[0]))
    if count < 3:
        return None
    ref = np.asarray(reference[:count], dtype=float)
    cand = np.asarray(aligned_candidate[:count], dtype=float)
    ref_dist = np.linalg.norm(ref[:, None, :] - ref[None, :, :], axis=-1)
    cand_dist = np.linalg.norm(cand[:, None, :] - cand[None, :, :], axis=-1)
    upper = np.triu(np.ones((count, count), dtype=bool), k=1)
    mask = upper & (ref_dist <= cutoff_A)
    if not np.any(mask):
        return None
    deltas = np.abs(ref_dist[mask] - cand_dist[mask])
    threshold_scores = [np.mean(deltas <= threshold) for threshold in (0.5, 1.0, 2.0, 4.0)]
    return float(np.mean(threshold_scores))


def _candidate_metric_rows(queue_row: dict[str, Any], max_candidates: int) -> list[dict[str, Any]]:
    target = _text(queue_row.get("target"))
    native_path = _text(queue_row.get("native_pdb_path"))
    scores_csv = _text(queue_row.get("allatom_scores_csv"))
    if not native_path or not _resolve(native_path).exists():
        return [
            {
                "target": target,
                "metric_status": "blocked_native_missing",
                "native_pdb_path": native_path,
                "candidate_pdb": "",
                "claim_promotion_allowed": False,
            }
        ]
    if not scores_csv or not _resolve(scores_csv).exists():
        return [
            {
                "target": target,
                "metric_status": "blocked_candidate_source_missing",
                "native_pdb_path": native_path,
                "candidate_pdb": "",
                "claim_promotion_allowed": False,
            }
        ]
    native_ca = _ca_coords(native_path)
    rows: list[dict[str, Any]] = []
    for idx, source in enumerate(_read_csv(scores_csv)[:max_candidates], start=1):
        candidate_pdb = _text(source.get("backmapped_pdb"))
        if not candidate_pdb or not _resolve(candidate_pdb).exists():
            rows.append(
                {
                    "target": target,
                    "candidate_rank": idx,
                    "metric_status": "blocked_candidate_pdb_missing",
                    "native_pdb_path": native_path,
                    "candidate_pdb": candidate_pdb,
                    "claim_promotion_allowed": False,
                }
            )
            continue
        candidate_ca = _ca_coords(candidate_pdb)
        aligned_native, aligned_candidate, distances = _aligned_ca_pair(native_ca, candidate_ca)
        rmsd = float(math.sqrt(np.mean(distances**2))) if distances.size else None
        gdt_proxy = _gdt_ts_proxy(distances)
        tm_proxy = _tm_score_ca_proxy(distances)
        lddt_proxy = _lddt_ca_proxy(aligned_native, aligned_candidate)
        rows.append(
            {
                "target": target,
                "candidate_rank": idx,
                "queue_id": _text(queue_row.get("queue_id")),
                "metric_status": "metrics_computed" if rmsd is not None else "blocked_insufficient_ca_matches",
                "match_mode": "sequential_ca_atoms",
                "native_pdb_path": native_path,
                "candidate_pdb": candidate_pdb,
                "native_ca_count": int(native_ca.shape[0]),
                "candidate_ca_count": int(candidate_ca.shape[0]),
                "matched_ca_count": int(min(native_ca.shape[0], candidate_ca.shape[0])),
                "ca_aligned_rmsd_A": rmsd,
                "gdt_ts_proxy": gdt_proxy,
                "tm_score_ca_proxy": tm_proxy,
                "lddt_ca_proxy": lddt_proxy,
                "gdt_1A_fraction": float(np.mean(distances <= 1.0)) if distances.size else None,
                "gdt_2A_fraction": float(np.mean(distances <= 2.0)) if distances.size else None,
                "gdt_4A_fraction": float(np.mean(distances <= 4.0)) if distances.size else None,
                "gdt_8A_fraction": float(np.mean(distances <= 8.0)) if distances.size else None,
                "tm_score_available": False,
                "lddt_available": False,
                "dockq_available": False,
                "proxy_metric_not_galaxy_claim_grade": True,
                "claim_promotion_allowed": False,
            }
        )
    return rows


def build_materialization(
    *,
    queue_json: str | Path = DEFAULT_QUEUE_JSON,
    max_candidates_per_target: int = 8,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    queue = _read_json(queue_json)
    metric_rows: list[dict[str, Any]] = []
    for row in _queue_rows(queue):
        if _text(row.get("metric_task")) != "protein_alignment_metrics":
            if _text(row.get("metric_task")) == "interface_metrics":
                metric_rows.append(
                    {
                        "target": _text(row.get("target")),
                        "queue_id": _text(row.get("queue_id")),
                        "metric_status": "not_applicable_without_complex_interface_claim",
                        "dockq_available": False,
                        "claim_promotion_allowed": False,
                    }
                )
            continue
        metric_rows.extend(_candidate_metric_rows(row, max_candidates=max_candidates_per_target))
    computed = [row for row in metric_rows if row.get("metric_status") == "metrics_computed"]
    computed_targets = sorted({str(row.get("target")) for row in computed})
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "structure_refinement_metric_materialization_partial" if computed else "blocked_no_metrics_computed",
        "queue_json": _artifact(queue_json),
        "metric_row_count": len(metric_rows),
        "computed_metric_row_count": len(computed),
        "rmsd_available_target_count": len(computed_targets),
        "gdt_ts_proxy_available_target_count": len(computed_targets),
        "tm_score_ca_proxy_available_target_count": len(computed_targets),
        "lddt_ca_proxy_available_target_count": len(computed_targets),
        "computed_targets": computed_targets,
        "tm_score_available_target_count": 0,
        "lddt_available_target_count": 0,
        "dockq_available_target_count": 0,
        "claim_promotion_allowed": False,
        "galaxy_class_claim_allowed": False,
        "next_required_step": (
            "Use CA-aligned RMSD/GDT/TM/lDDT proxy rows as partial A3 evidence only. Add true TM-score, "
            "true lDDT or MolProbity, and scoped interface/DockQ provenance before any GALAXY-class claim."
        ),
    }
    return {
        "packet_type": "structure_refinement_metric_materialization",
        "summary": summary,
        "rows": metric_rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "galaxy_class_claim_allowed": False,
            "gdt_ts_proxy_is_not_true_galaxy_metric": True,
            "tm_score_ca_proxy_is_not_true_tm_score": True,
            "lddt_ca_proxy_is_not_true_lddt_or_molprobity": True,
            "interface_metrics_without_complex_claim_are_not_applicable": True,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Structure Refinement Metric Materialization",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- computed_metric_row_count: `{summary['computed_metric_row_count']}`",
        f"- rmsd_available_target_count: `{summary['rmsd_available_target_count']}`",
        f"- gdt_ts_proxy_available_target_count: `{summary['gdt_ts_proxy_available_target_count']}`",
        f"- tm_score_ca_proxy_available_target_count: `{summary['tm_score_ca_proxy_available_target_count']}`",
        f"- lddt_ca_proxy_available_target_count: `{summary['lddt_ca_proxy_available_target_count']}`",
        f"- computed_targets: `{summary['computed_targets']}`",
        f"- galaxy_class_claim_allowed: `{str(summary['galaxy_class_claim_allowed']).lower()}`",
        "",
        "## Computed Rows",
        "",
        "| Target | Rank | Status | CA RMSD A | GDT proxy | TM CA proxy | lDDT CA proxy | Matched CA |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        if row.get("metric_status") != "metrics_computed":
            continue
        lines.append(
            f"| `{row['target']}` | {row['candidate_rank']} | `{row['metric_status']}` | "
            f"{row['ca_aligned_rmsd_A']} | {row['gdt_ts_proxy']} | {row['tm_score_ca_proxy']} | "
            f"{row['lddt_ca_proxy']} | {row['matched_ca_count']} |"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize partial A3 structure/refinement metrics.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--max-candidates-per-target", type=int, default=8)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_materialization(queue_json=args.queue_json, max_candidates_per_target=args.max_candidates_per_target)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
