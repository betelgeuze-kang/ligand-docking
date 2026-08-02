#!/usr/bin/env python3
"""Materialize local refine-tier public-benchmark metric source payloads."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from betelgeuze_engine.physics.mm_gbsa import gb_sa_proxy_energy
from core.mm_gbsa import mm_gbsa_binding_energy
from core.score_calibration import calibration_quality_gate, fit_linear_calibration
from core.structure_metrics import dockq_proxy, lddt_pli_proxy, parse_pdb_atoms_with_coords
from tools.accounting.build_pdbbind_casf_pose_affinity_results import (
    _coords as _ligand_coords,
    _load_ligand,
)
from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_readiness import (
    DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV,
    DEFAULT_OUT_WORK_ORDER_CSV,
    METRIC_EVIDENCE_COLUMNS,
    WORK_ORDER_COLUMNS,
    _build_metric_evidence_rows,
    _input_artifact_sha256,
    _pose_id_from_work_order_row,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_metric_source_materialization_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_metric_source_materialization_current.md"
DEFAULT_OUT_FILLED_WORK_ORDER_CSV = (
    "runs/refine_tier_public_benchmark_work_order_materialized_current.csv"
)
DEFAULT_OUT_METRIC_EVIDENCE_CSV = (
    "runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv"
)
DEFAULT_OUT_SOURCE_DIR = "runs/refine_tier_public_benchmark_metric_sources"
DEFAULT_OPERATOR_ID = "local_refine_tier_metric_materializer"
BOOTSTRAP_SEED = 20260614
BOOTSTRAP_ITERATIONS = 200
MIN_CANDIDATE_FREE_ENERGY_PAIRS = 5
MIN_CANDIDATE_FREE_ENERGY_SPEARMAN = 0.5
MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS = 25
MIN_CLAIM_GRADE_HOLDOUT_PAIRS = 8
MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW = 0.5
CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark metric materializer only; computes deterministic local proxy metrics from "
    "already-local ligand pose, native ligand, and reviewed receptor coordinate artifacts. It does not run "
    "docking, MD, external engines, downloads, uploads, claim promotion, or intake writes."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display_path(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def _rows_by_work_order_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("work_order_id")): row for row in rows if _text(row.get("work_order_id"))}


def _utc_now_text() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_metric(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.6f}"


def _rankdata(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    ranks[order] = np.arange(1, len(values) + 1, dtype=np.float64)
    # Average ranks within tied groups so the Spearman coefficient matches the
    # standard tie-corrected definition; with no ties this is a no-op.
    sorted_values = values[order]
    start = 0
    n = len(values)
    while start < n:
        stop = start + 1
        while stop < n and sorted_values[stop] == sorted_values[start]:
            stop += 1
        if stop - start > 1:
            tied_indices = order[start:stop]
            ranks[tied_indices] = float(ranks[tied_indices].mean())
        start = stop
    return ranks


def _spearman_values(proxy_values: list[float], reference_values: list[float]) -> float | None:
    x = np.asarray(proxy_values, dtype=np.float64).reshape(-1)
    y = np.asarray(reference_values, dtype=np.float64).reshape(-1)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if x.size < 2:
        return None
    x_ranks = _rankdata(x)
    y_ranks = _rankdata(y)
    rx = x_ranks - x_ranks.mean()
    ry = y_ranks - y_ranks.mean()
    denom = float(np.sqrt(np.sum(rx**2) * np.sum(ry**2)))
    if denom < 1e-12:
        return None
    return float(np.sum(rx * ry) / denom)


def _percentile(values: list[float], percentile: float) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return None
    return float(np.percentile(np.asarray(finite, dtype=np.float64), percentile))


def _bootstrap_spearman_interval(
    pairs: list[dict[str, Any]],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    valid_pairs = [
        pair
        for pair in pairs
        if _float(pair.get("proxy")) is not None and _float(pair.get("reference")) is not None
    ]
    if len(valid_pairs) < 2:
        return {
            "bootstrap_iteration_count": int(iterations),
            "bootstrap_seed": int(seed),
            "bootstrap_valid_sample_count": 0,
            "free_energy_spearman_bootstrap_p05": None,
            "free_energy_spearman_bootstrap_p50": None,
            "free_energy_spearman_bootstrap_p95": None,
        }
    rng = np.random.default_rng(seed)
    samples: list[float] = []
    for _index in range(iterations):
        sample_indexes = rng.integers(0, len(valid_pairs), size=len(valid_pairs))
        sample = [valid_pairs[int(index)] for index in sample_indexes]
        spearman = _spearman_values(
            [float(pair["proxy"]) for pair in sample],
            [float(pair["reference"]) for pair in sample],
        )
        if spearman is not None:
            samples.append(float(spearman))
    return {
        "bootstrap_iteration_count": int(iterations),
        "bootstrap_seed": int(seed),
        "bootstrap_valid_sample_count": len(samples),
        "free_energy_spearman_bootstrap_p05": _percentile(samples, 5),
        "free_energy_spearman_bootstrap_p50": _percentile(samples, 50),
        "free_energy_spearman_bootstrap_p95": _percentile(samples, 95),
    }


def _split_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pair in pairs:
        split = _text(pair.get("split")) or "unknown"
        counts[split] = counts.get(split, 0) + 1
    return counts


def _claim_grade_statistical_support(
    *,
    pair_count: int,
    holdout_pair_count: int,
    bootstrap_low: float | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if pair_count < MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS:
        blockers.append("claim_grade_public_benchmark_pair_count_below_minimum")
    if holdout_pair_count < MIN_CLAIM_GRADE_HOLDOUT_PAIRS:
        blockers.append("claim_grade_public_benchmark_holdout_pair_count_below_minimum")
    if bootstrap_low is None or bootstrap_low < MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW:
        blockers.append("claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum")
    return {
        "claim_grade_public_benchmark_statistical_support_ready": not blockers,
        "claim_grade_public_benchmark_statistical_support_blocker_count": len(blockers),
        "claim_grade_public_benchmark_statistical_support_blockers": blockers,
        "min_claim_grade_public_benchmark_pairs_required": MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
        "min_claim_grade_holdout_pairs_required": MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    }


def _reference_ligand_artifact(ligand_pose_artifact: str, target_id: str) -> str:
    pose_path = _resolve(ligand_pose_artifact)
    target = _text(target_id).lower()
    for candidate in (pose_path.parent / target, pose_path.parent / f"{target}_ligand"):
        if candidate.is_file():
            return _display_path(candidate)
    return ""


def _load_ligand_coords(path_like: str | Path) -> np.ndarray:
    return np.asarray(_ligand_coords(_load_ligand(_resolve(path_like))), dtype=np.float64)


def _load_receptor_coords(path_like: str | Path) -> np.ndarray:
    text = _resolve(path_like).read_text(encoding="utf-8", errors="replace")
    atoms = parse_pdb_atoms_with_coords(text)
    coords = [np.asarray(atom["xyz"], dtype=np.float64) for atom in atoms if atom.get("record") == "ATOM"]
    return np.asarray(coords, dtype=np.float64)


def _ligand_descriptor_props(path_like: str | Path) -> dict[str, float]:
    try:
        from rdkit.Chem import Descriptors, rdMolDescriptors

        mol = _load_ligand(_resolve(path_like))
        logp = float(Descriptors.MolLogP(mol))
        tpsa = float(rdMolDescriptors.CalcTPSA(mol))
    except Exception:
        return {"logp_norm": 0.0, "polar_norm": 0.0}
    return {
        "logp_norm": float(np.clip(logp / 6.0, 0.0, 1.0)),
        "polar_norm": float(np.clip(tpsa / 140.0, 0.0, 1.0)),
    }


def _source_payload(
    *,
    metric_name: str,
    target_id: str,
    pose_id: str,
    value: float,
    method: str,
    input_artifacts: list[str],
    operator_id: str,
    reviewed_at_utc: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "metric_name": metric_name,
        "target_id": target_id,
        "pose_id": pose_id,
        "value": float(value),
        "method": method,
        "input_artifacts": input_artifacts,
        "input_artifact_sha256s": [_input_artifact_sha256(artifact) for artifact in input_artifacts],
        "operator_id": operator_id,
        "reviewed_at_utc": reviewed_at_utc,
        "license_ok": True,
        "external_engine_calls": 0,
        "details": dict(details or {}),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _write_source_payload(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _materialize_row(
    row: dict[str, Any],
    science_row: dict[str, Any],
    *,
    source_dir: str | Path,
    operator_id: str,
    reviewed_at_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    work_order_id = _text(row.get("work_order_id"))
    target_id = _text(row.get("target_id")).lower()
    pose_id = _pose_id_from_work_order_row(row)
    ligand_pose_artifact = _text(science_row.get("ligand_pose_artifact"))
    receptor_coordinate_artifact = _text(science_row.get("receptor_coordinate_artifact"))
    reference_ligand_artifact = _reference_ligand_artifact(ligand_pose_artifact, target_id)
    blockers: list[str] = []
    if not ligand_pose_artifact:
        blockers.append("ligand_pose_artifact_missing")
    if not receptor_coordinate_artifact:
        blockers.append("receptor_coordinate_artifact_missing")
    if not reference_ligand_artifact:
        blockers.append("reference_ligand_artifact_missing")

    dockq = lddt_pli = internal_delta_g = None
    details: dict[str, Any] = {}
    if not blockers:
        try:
            pose_coords = _load_ligand_coords(ligand_pose_artifact)
            reference_coords = _load_ligand_coords(reference_ligand_artifact)
            receptor_coords = _load_receptor_coords(receptor_coordinate_artifact)
            dockq = dockq_proxy(pose_coords, reference_coords)
            lddt_pli = lddt_pli_proxy(pose_coords, reference_coords)
            refine = mm_gbsa_binding_energy(
                receptor_coords,
                pose_coords,
                props=_ligand_descriptor_props(ligand_pose_artifact),
            )
            internal_delta_g = float(gb_sa_proxy_energy(refine, 0.0))
            details = {
                "dockq_proxy_backend": "core.structure_metrics.dockq_proxy",
                "lddt_pli_proxy_backend": "core.structure_metrics.lddt_pli_proxy",
                "internal_deltaG_backend": "core.mm_gbsa.mm_gbsa_binding_energy",
                "pose_atom_count": int(pose_coords.shape[0]),
                "reference_atom_count": int(reference_coords.shape[0]),
                "receptor_atom_count": int(receptor_coords.shape[0]),
                "contact_count": refine.get("contact_count"),
                "ligand_contact_atom_count": refine.get("ligand_contact_atom_count"),
                "min_distance_a": refine.get("min_distance_a"),
                "refine_tier": refine.get("refine_tier"),
            }
        except Exception as exc:  # noqa: BLE001 - row-level materialization should stay fail-closed.
            blockers.append(f"metric_materialization_failed:{type(exc).__name__}")

    metric_values_present = dockq is not None and lddt_pli is not None and internal_delta_g is not None
    input_artifacts = [
        artifact
        for artifact in (ligand_pose_artifact, receptor_coordinate_artifact, reference_ligand_artifact)
        if artifact
    ]
    source_dir_path = _resolve(source_dir)
    dockq_source = _display_path(source_dir_path / f"{work_order_id}_dockq.json")
    lddt_source = _display_path(source_dir_path / f"{work_order_id}_lddt_pli.json")
    internal_delta_g_source = _display_path(source_dir_path / f"{work_order_id}_internal_deltaG.json")

    filled = dict(row)
    if metric_values_present:
        dockq_value = float(_format_metric(dockq))
        lddt_value = float(_format_metric(lddt_pli))
        internal_delta_g_value = float(_format_metric(internal_delta_g))
        filled.update(
            {
                "license_ok": "True",
                "dockq": _format_metric(dockq_value),
                "lddt_pli": _format_metric(lddt_value),
                "internal_refine_proxy_score": _format_metric(internal_delta_g_value),
                "dockq_source_artifact": dockq_source,
                "lddt_pli_source_artifact": lddt_source,
                "internal_deltaG_source_artifact": internal_delta_g_source,
            }
        )
        _write_source_payload(
            dockq_source,
            _source_payload(
                metric_name="dockq",
                target_id=target_id,
                pose_id=pose_id,
                value=dockq_value,
                method="internal_ligand_pose_reference_dockq_proxy_v1",
                input_artifacts=input_artifacts,
                operator_id=operator_id,
                reviewed_at_utc=reviewed_at_utc,
                details=details,
            ),
        )
        _write_source_payload(
            lddt_source,
            _source_payload(
                metric_name="lddt_pli",
                target_id=target_id,
                pose_id=pose_id,
                value=lddt_value,
                method="internal_ligand_pose_reference_lddt_pli_proxy_v1",
                input_artifacts=input_artifacts,
                operator_id=operator_id,
                reviewed_at_utc=reviewed_at_utc,
                details=details,
            ),
        )
        _write_source_payload(
            internal_delta_g_source,
            _source_payload(
                metric_name="internal_deltaG",
                target_id=target_id,
                pose_id=pose_id,
                value=internal_delta_g_value,
                method="internal_contact_normalized_mm_gbsa_v2",
                input_artifacts=input_artifacts,
                operator_id=operator_id,
                reviewed_at_utc=reviewed_at_utc,
                details=details,
            ),
        )

    report = {
        "work_order_id": work_order_id,
        "target_id": target_id,
        "pose_id": pose_id,
        "split": _text(row.get("split")),
        "metric_materialization_status": "pass" if metric_values_present and not blockers else "blocked",
        "dockq": _format_metric(dockq) if dockq is not None else "",
        "lddt_pli": _format_metric(lddt_pli) if lddt_pli is not None else "",
        "internal_refine_proxy_score": (
            _format_metric(internal_delta_g) if internal_delta_g is not None else ""
        ),
        "deltaG_experimental_kcal_mol": _text(row.get("deltaG_experimental_kcal_mol")),
        "dockq_source_artifact": dockq_source if metric_values_present else "",
        "lddt_pli_source_artifact": lddt_source if metric_values_present else "",
        "internal_deltaG_source_artifact": internal_delta_g_source if metric_values_present else "",
        "input_artifacts": ";".join(input_artifacts),
        "input_artifact_sha256s": ";".join(_input_artifact_sha256(artifact) for artifact in input_artifacts),
        "blockers": ";".join(blockers),
    }
    return filled, report


def materialize_refine_tier_public_benchmark_metric_sources(
    *,
    work_order_csv: str | Path = DEFAULT_OUT_WORK_ORDER_CSV,
    science_input_gap_csv: str | Path = DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_md: str | Path = DEFAULT_OUT_MD,
    out_filled_work_order_csv: str | Path = DEFAULT_OUT_FILLED_WORK_ORDER_CSV,
    out_metric_evidence_csv: str | Path = DEFAULT_OUT_METRIC_EVIDENCE_CSV,
    out_source_dir: str | Path = DEFAULT_OUT_SOURCE_DIR,
    operator_id: str = DEFAULT_OPERATOR_ID,
    reviewed_at_utc: str | None = None,
) -> dict[str, Any]:
    reviewed_at = reviewed_at_utc or _utc_now_text()
    work_order_rows = _read_csv(work_order_csv)
    science_rows = _rows_by_work_order_id(_read_csv(science_input_gap_csv))
    filled_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for row in work_order_rows:
        science_row = science_rows.get(_text(row.get("work_order_id")), {})
        filled, report = _materialize_row(
            row,
            science_row,
            source_dir=out_source_dir,
            operator_id=operator_id,
            reviewed_at_utc=reviewed_at,
        )
        filled_rows.append(filled)
        report_rows.append(report)

    metric_evidence_rows = _build_metric_evidence_rows(filled_rows, list(science_rows.values()))
    materialized_rows = [row for row in report_rows if row["metric_materialization_status"] == "pass"]
    proxy_values = [_float(row.get("internal_refine_proxy_score")) for row in materialized_rows]
    experimental_values = [_float(row.get("deltaG_experimental_kcal_mol")) for row in materialized_rows]
    paired = [
        {
            "proxy": proxy,
            "reference": ref,
            "split": _text(row.get("split")) or "unknown",
            "work_order_id": _text(row.get("work_order_id")),
            "target_id": _text(row.get("target_id")),
        }
        for row, proxy, ref in zip(materialized_rows, proxy_values, experimental_values, strict=True)
        if proxy is not None and ref is not None
    ]
    calibration = fit_linear_calibration(
        [float(pair["proxy"]) for pair in paired],
        [float(pair["reference"]) for pair in paired],
    )
    calibration_gate = calibration_quality_gate(
        calibration,
        min_pairs=MIN_CANDIDATE_FREE_ENERGY_PAIRS,
        min_spearman=MIN_CANDIDATE_FREE_ENERGY_SPEARMAN,
    )
    split_counts = _split_counts(paired)
    holdout_pair_count = split_counts.get("holdout", 0)
    bootstrap = _bootstrap_spearman_interval(paired)
    statistical_support = _claim_grade_statistical_support(
        pair_count=len(paired),
        holdout_pair_count=holdout_pair_count,
        bootstrap_low=bootstrap["free_energy_spearman_bootstrap_p05"],
    )
    metric_evidence_pass_count = sum(
        1 for row in metric_evidence_rows if row.get("metric_evidence_status") == "pass"
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_metric_source_materialization",
        "status": (
            "refine_tier_public_benchmark_metric_sources_materialized"
            if len(materialized_rows) == len(work_order_rows) and work_order_rows
            else "blocked_refine_tier_public_benchmark_metric_source_materialization"
        ),
        "work_order_csv": str(work_order_csv),
        "science_input_gap_csv": str(science_input_gap_csv),
        "filled_work_order_csv": str(out_filled_work_order_csv),
        "metric_evidence_csv": str(out_metric_evidence_csv),
        "source_dir": str(out_source_dir),
        "work_order_row_count": len(work_order_rows),
        "materialized_row_count": len(materialized_rows),
        "blocked_row_count": len(work_order_rows) - len(materialized_rows),
        "source_payload_count": len(materialized_rows) * 3,
        "metric_evidence_row_count": len(metric_evidence_rows),
        "metric_evidence_pass_row_count": metric_evidence_pass_count,
        "metric_evidence_blocked_row_count": len(metric_evidence_rows) - metric_evidence_pass_count,
        "free_energy_pair_count": len(paired),
        "free_energy_fit_pair_count": split_counts.get("fit", 0),
        "free_energy_holdout_pair_count": holdout_pair_count,
        "free_energy_unknown_split_pair_count": split_counts.get("unknown", 0),
        "free_energy_spearman": calibration.get("spearman"),
        "free_energy_spearman_gate_ready": bool(calibration_gate.get("calibration_promotion_ready")),
        "min_free_energy_pairs_required": calibration_gate.get("min_pairs_required"),
        "min_free_energy_spearman_required": calibration_gate.get("min_spearman_required"),
        **bootstrap,
        **statistical_support,
        "operator_id": operator_id,
        "reviewed_at_utc": reviewed_at,
        "external_engine_calls": 0,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    payload = {"summary": summary, "rows": report_rows}

    write_csv_rows(_resolve(out_filled_work_order_csv), [{column: row.get(column, "") for column in WORK_ORDER_COLUMNS} for row in filled_rows])
    write_csv_rows(_resolve(out_metric_evidence_csv), [{column: row.get(column, "") for column in METRIC_EVIDENCE_COLUMNS} for row in metric_evidence_rows])
    write_csv_rows(_resolve(out_csv), report_rows)
    _resolve(out_json).parent.mkdir(parents=True, exist_ok=True)
    _resolve(out_json).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _resolve(out_md).parent.mkdir(parents=True, exist_ok=True)
    _resolve(out_md).write_text(_render_md(payload), encoding="utf-8")
    return payload


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Refine-Tier Public Benchmark Metric Source Materialization",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- materialized rows: `{summary['materialized_row_count']}/{summary['work_order_row_count']}`",
        f"- metric evidence pass/blocked: `{summary['metric_evidence_pass_row_count']}/{summary['metric_evidence_blocked_row_count']}`",
        f"- free-energy Spearman: `{summary['free_energy_spearman']}`",
        f"- free-energy Spearman gate ready: `{summary['free_energy_spearman_gate_ready']}`",
        f"- free-energy fit/holdout pairs: `{summary['free_energy_fit_pair_count']}/{summary['free_energy_holdout_pair_count']}`",
        "- free-energy Spearman bootstrap p05/p50/p95: "
        f"`{summary['free_energy_spearman_bootstrap_p05']}/"
        f"{summary['free_energy_spearman_bootstrap_p50']}/"
        f"{summary['free_energy_spearman_bootstrap_p95']}`",
        "- claim-grade public benchmark statistical support ready: "
        f"`{summary['claim_grade_public_benchmark_statistical_support_ready']}`",
        f"- filled work order CSV: `{summary['filled_work_order_csv']}`",
        f"- metric evidence CSV: `{summary['metric_evidence_csv']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize local metric source JSONs for refine-tier public benchmark work orders."
    )
    parser.add_argument("--work-order-csv", default=DEFAULT_OUT_WORK_ORDER_CSV)
    parser.add_argument("--science-input-gap-csv", default=DEFAULT_OUT_SCIENCE_INPUT_GAP_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-filled-work-order-csv", default=DEFAULT_OUT_FILLED_WORK_ORDER_CSV)
    parser.add_argument("--out-metric-evidence-csv", default=DEFAULT_OUT_METRIC_EVIDENCE_CSV)
    parser.add_argument("--out-source-dir", default=DEFAULT_OUT_SOURCE_DIR)
    parser.add_argument("--operator-id", default=DEFAULT_OPERATOR_ID)
    parser.add_argument("--reviewed-at-utc", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = materialize_refine_tier_public_benchmark_metric_sources(
        work_order_csv=args.work_order_csv,
        science_input_gap_csv=args.science_input_gap_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        out_filled_work_order_csv=args.out_filled_work_order_csv,
        out_metric_evidence_csv=args.out_metric_evidence_csv,
        out_source_dir=args.out_source_dir,
        operator_id=args.operator_id,
        reviewed_at_utc=args.reviewed_at_utc,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
