#!/usr/bin/env python3
"""Build fail-closed metric-value candidates for R9 statistical-support templates."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from core.mm_gbsa import mm_gbsa_binding_energy
from core.structure_metrics import dockq_proxy, lddt_pli_proxy
from tools.accounting.build_storage_retention_manifest import _human_size
from tools.builder_table_utils import write_csv_rows
from tools.product.materialize_refine_tier_public_benchmark_metric_sources import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    CLAIM_BOUNDARY as SOURCE_PAYLOAD_CLAIM_BOUNDARY,
    MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
    MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
    MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
    _bootstrap_spearman_interval,
    _claim_grade_statistical_support,
    _float,
    _ligand_descriptor_props,
    _load_ligand_coords,
    _load_receptor_coords,
    _reference_ligand_artifact,
    _spearman_values,
    _split_counts,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATES_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
)
DEFAULT_READINESS_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
)
DEFAULT_EXISTING_MATERIALIZATION_CSV = "runs/refine_tier_public_benchmark_metric_source_materialization_current.csv"
DEFAULT_OUT_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.csv"
)
DEFAULT_OUT_MD = (
    "docs/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.md"
)
DEFAULT_OPERATOR_ID = "candidate_local_metric_materializer_not_operator_reviewed"

METHOD_BY_METRIC = {
    "dockq": "candidate_internal_ligand_pose_reference_dockq_proxy_v1",
    "lddt_pli": "candidate_internal_ligand_pose_reference_lddt_pli_proxy_v1",
    "internal_deltaG": "candidate_internal_contact_shell_normalized_mm_gbsa_v2",
}

RECEPTOR_CONTEXT_RADIUS_A = 14.0
RECEPTOR_CONTEXT_MIN_ATOMS = 128
RECEPTOR_CONTEXT_MAX_ATOMS = 768

CLAIM_BOUNDARY = (
    "R9 statistical-support metric candidate fill only; computes deterministic local proxy values from "
    "already-local ligand pose, native/reference ligand, and coordinate-validated receptor/complex artifacts. "
    "It does not write the expected metric source payload paths, approve operator receipts, write canonical "
    "intake, promote claims, run docking or MD, download, upload, email, delete, commit, push, or mutate "
    "external state."
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> list[dict[str, str]]:
    import csv

    path = _resolve(path_like, root=root)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _sha256(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_metric(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.6f}"


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _receptor_context_coords(
    receptor_coords: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    radius_a: float = RECEPTOR_CONTEXT_RADIUS_A,
    min_atoms: int = RECEPTOR_CONTEXT_MIN_ATOMS,
    max_atoms: int = RECEPTOR_CONTEXT_MAX_ATOMS,
) -> tuple[np.ndarray, dict[str, Any]]:
    receptor = np.asarray(receptor_coords, dtype=np.float32)
    ligand = np.asarray(ligand_coords, dtype=np.float32)
    if receptor.size == 0 or ligand.size == 0:
        return receptor, {
            "receptor_context_selection": "empty_receptor_or_ligand",
            "receptor_context_radius_A": float(radius_a),
            "receptor_atom_count": int(receptor.shape[0]) if receptor.ndim == 2 else 0,
            "receptor_context_atom_count": int(receptor.shape[0]) if receptor.ndim == 2 else 0,
        }
    if receptor.shape[0] <= int(max_atoms):
        return receptor, {
            "receptor_context_selection": "all_receptor_atoms_under_cap",
            "receptor_context_radius_A": float(radius_a),
            "receptor_atom_count": int(receptor.shape[0]),
            "receptor_context_atom_count": int(receptor.shape[0]),
            "receptor_context_min_atoms": int(min_atoms),
            "receptor_context_max_atoms": int(max_atoms),
        }

    distances = np.linalg.norm(receptor[:, None, :] - ligand[None, :, :], axis=2)
    nearest = np.min(distances, axis=1)
    selected = np.flatnonzero(nearest <= float(radius_a))
    selection = "within_radius"
    if selected.size < int(min_atoms):
        selected = np.argsort(nearest)[: min(int(min_atoms), receptor.shape[0])]
        selection = "nearest_min_atoms"
    elif selected.size > int(max_atoms):
        selected = selected[np.argsort(nearest[selected])[: int(max_atoms)]]
        selection = "within_radius_capped_to_nearest"
    selected = np.asarray(selected, dtype=np.int64)
    context = receptor[selected]
    return context, {
        "receptor_context_selection": selection,
        "receptor_context_radius_A": float(radius_a),
        "receptor_context_min_atoms": int(min_atoms),
        "receptor_context_max_atoms": int(max_atoms),
        "receptor_atom_count": int(receptor.shape[0]),
        "receptor_context_atom_count": int(context.shape[0]),
        "receptor_context_min_nearest_distance_A": float(np.min(nearest)) if nearest.size else None,
        "receptor_context_max_selected_distance_A": float(np.max(nearest[selected])) if selected.size else None,
    }


def _readiness_by_slot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("expansion_slot_id")): row for row in rows if _text(row.get("expansion_slot_id"))}


def _candidate_pair_metrics(readiness_row: dict[str, Any], *, root: Path) -> dict[str, Any]:
    target_id = _text(readiness_row.get("target_id")).lower()
    pose_id = _text(readiness_row.get("pose_id"))
    ligand_pose_artifact = _text(readiness_row.get("ligand_pose_artifact"))
    receptor_artifact = _text(readiness_row.get("receptor_coordinate_artifact"))
    reference_ligand_artifact = _reference_ligand_artifact(ligand_pose_artifact, target_id)
    blockers: list[str] = []
    if not ligand_pose_artifact or not _resolve(ligand_pose_artifact, root=root).is_file():
        blockers.append("ligand_pose_artifact_missing")
    if not receptor_artifact or not _resolve(receptor_artifact, root=root).is_file():
        blockers.append("receptor_coordinate_artifact_missing")
    if not reference_ligand_artifact or not _resolve(reference_ligand_artifact, root=root).is_file():
        blockers.append("reference_ligand_artifact_missing")

    dockq = lddt_pli = internal_delta_g = None
    details: dict[str, Any] = {}
    if not blockers:
        try:
            pose_coords = _load_ligand_coords(_resolve(ligand_pose_artifact, root=root))
            reference_coords = _load_ligand_coords(_resolve(reference_ligand_artifact, root=root))
            receptor_coords = _load_receptor_coords(_resolve(receptor_artifact, root=root))
            receptor_context, context_details = _receptor_context_coords(receptor_coords, pose_coords)
            dockq = dockq_proxy(pose_coords, reference_coords)
            lddt_pli = lddt_pli_proxy(pose_coords, reference_coords)
            refine = mm_gbsa_binding_energy(
                receptor_context,
                pose_coords,
                props=_ligand_descriptor_props(_resolve(ligand_pose_artifact, root=root)),
            )
            internal_delta_g = float(refine["deltaG_mm_gbsa_kcal_mol"])
            details = {
                "dockq_proxy_backend": "core.structure_metrics.dockq_proxy",
                "lddt_pli_proxy_backend": "core.structure_metrics.lddt_pli_proxy",
                "internal_deltaG_backend": "core.mm_gbsa.mm_gbsa_binding_energy",
                "internal_deltaG_context": "ligand_local_receptor_contact_shell",
                "pose_atom_count": int(pose_coords.shape[0]),
                "reference_atom_count": int(reference_coords.shape[0]),
                "receptor_atom_count": int(receptor_coords.shape[0]),
                **context_details,
                "contact_count": refine.get("contact_count"),
                "ligand_contact_atom_count": refine.get("ligand_contact_atom_count"),
                "min_distance_a": refine.get("min_distance_a"),
                "refine_tier": refine.get("refine_tier"),
            }
        except Exception as exc:  # noqa: BLE001 - row-level preview should stay fail-closed.
            blockers.append(f"candidate_metric_materialization_failed:{type(exc).__name__}")

    value_by_metric = {
        "dockq": dockq,
        "lddt_pli": lddt_pli,
        "internal_deltaG": internal_delta_g,
    }
    required_inputs = _split_semicolon(readiness_row.get("required_metric_input_artifacts"))
    auxiliary_inputs = [reference_ligand_artifact] if reference_ligand_artifact else []
    all_inputs = [*required_inputs, *auxiliary_inputs]
    all_hashes = [_sha256(path, root=root) for path in all_inputs]
    return {
        "target_id": target_id,
        "pose_id": pose_id,
        "split": _text(readiness_row.get("suggested_split")) or _text(readiness_row.get("required_split")),
        "work_order_id": _text(readiness_row.get("suggested_work_order_id")),
        "expansion_slot_id": _text(readiness_row.get("expansion_slot_id")),
        "deltaG_experimental_kcal_mol": _text(readiness_row.get("deltaG_experimental_kcal_mol")),
        "value_by_metric": value_by_metric,
        "required_input_artifacts": required_inputs,
        "auxiliary_reference_ligand_artifact": reference_ligand_artifact,
        "candidate_input_artifacts": all_inputs,
        "candidate_input_artifact_sha256s": all_hashes,
        "details": details,
        "blockers": blockers,
    }


def _candidate_rows(
    template_rows: list[dict[str, Any]],
    readiness_rows: list[dict[str, Any]],
    *,
    generated_at_utc: str,
    root: Path,
    operator_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    readiness_by_slot = _readiness_by_slot(readiness_rows)
    metrics_by_slot: dict[str, dict[str, Any]] = {}
    output_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for template in template_rows:
        slot = _text(template.get("expansion_slot_id"))
        readiness = readiness_by_slot.get(slot, {})
        if slot not in metrics_by_slot:
            metrics_by_slot[slot] = _candidate_pair_metrics(readiness, root=root)
            pair = metrics_by_slot[slot]
            pair_rows.append(
                {
                    "work_order_id": pair["work_order_id"],
                    "expansion_slot_id": pair["expansion_slot_id"],
                    "target_id": pair["target_id"],
                    "pose_id": pair["pose_id"],
                    "split": pair["split"],
                    "deltaG_candidate_kcal_mol": _format_metric(pair["value_by_metric"].get("internal_deltaG")),
                    "deltaG_experimental_kcal_mol": pair["deltaG_experimental_kcal_mol"],
                    "dockq": _format_metric(pair["value_by_metric"].get("dockq")),
                    "lddt_pli": _format_metric(pair["value_by_metric"].get("lddt_pli")),
                    "candidate_status": "pass" if not pair["blockers"] else "blocked",
                    "blockers": ";".join(pair["blockers"]),
                }
            )
        pair = metrics_by_slot[slot]
        metric_name = _text(template.get("metric_name"))
        value = pair["value_by_metric"].get(metric_name)
        blockers = list(pair["blockers"])
        if value is None:
            blockers.append("candidate_metric_value_missing")
        candidate_input_artifact_hashes_complete = bool(
            pair["candidate_input_artifacts"]
            and len(pair["candidate_input_artifacts"]) == len(pair["candidate_input_artifact_sha256s"])
            and all(pair["candidate_input_artifact_sha256s"])
        )
        if not candidate_input_artifact_hashes_complete:
            blockers.append("candidate_input_artifact_sha256s_incomplete")
        expected_artifact = _text(template.get("metric_source_artifact"))
        output_rows.append(
            {
                "template_id": _text(template.get("template_id")),
                "candidate_queue_id": _text(template.get("candidate_queue_id")),
                "expansion_slot_id": slot,
                "suggested_work_order_id": _text(template.get("suggested_work_order_id")),
                "target_id": pair["target_id"],
                "pose_id": pair["pose_id"],
                "split": pair["split"],
                "metric_name": metric_name,
                "metric_value_candidate": _format_metric(value),
                "method_candidate": METHOD_BY_METRIC.get(metric_name, "candidate_metric_method_unknown"),
                "expected_metric_source_artifact": expected_artifact,
                "expected_metric_source_artifact_present": _resolve(expected_artifact, root=root).is_file()
                if expected_artifact
                else False,
                "required_metric_input_artifacts": ";".join(pair["required_input_artifacts"]),
                "auxiliary_reference_ligand_artifact": pair["auxiliary_reference_ligand_artifact"],
                "candidate_input_artifacts": ";".join(pair["candidate_input_artifacts"]),
                "candidate_input_artifact_sha256s": ";".join(pair["candidate_input_artifact_sha256s"]),
                "candidate_input_artifact_sha256s_complete": candidate_input_artifact_hashes_complete,
                "operator_id_candidate": operator_id,
                "candidate_generated_at_utc": generated_at_utc,
                "license_ok_candidate": "REQUIRES_OPERATOR_CONFIRMATION",
                "input_artifacts_reviewed_candidate": "REQUIRES_OPERATOR_REVIEW",
                "input_artifact_sha256s_reviewed_candidate": "REQUIRES_OPERATOR_REVIEW",
                "metric_source_artifact_reviewed_candidate": "REQUIRES_OPERATOR_REVIEW",
                "payload_schema_reviewed_candidate": "REQUIRES_OPERATOR_REVIEW",
                "approval_token_candidate": "REQUIRES_OPERATOR_APPROVAL",
                "external_engine_calls": 0,
                "payload_write_allowed": False,
                "canonical_intake_promotion_allowed": False,
                "claim_promotion_allowed": False,
                "candidate_status": "pass" if not blockers else "blocked",
                "blockers": ";".join(blockers),
                "details_json": json.dumps(pair["details"], sort_keys=True, separators=(",", ":")),
            }
        )
    return output_rows, pair_rows


def _existing_pairs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        proxy = _float(row.get("deltaG_mm_gbsa_kcal_mol"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        pairs.append(
            {
                "proxy": float(proxy),
                "reference": float(reference),
                "split": _text(row.get("split")) or "unknown",
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
            }
        )
    return pairs


def _candidate_pairs(pair_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in pair_rows:
        if row.get("candidate_status") != "pass":
            continue
        proxy = _float(row.get("deltaG_candidate_kcal_mol"))
        reference = _float(row.get("deltaG_experimental_kcal_mol"))
        if proxy is None or reference is None:
            continue
        pairs.append(
            {
                "proxy": float(proxy),
                "reference": float(reference),
                "split": _text(row.get("split")) or "unknown",
                "work_order_id": _text(row.get("work_order_id")),
                "target_id": _text(row.get("target_id")),
            }
        )
    return pairs


def _support_summary(existing_pairs: list[dict[str, Any]], candidate_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    combined = [*existing_pairs, *candidate_pairs]
    split_counts = _split_counts(combined)
    spearman = _spearman_values(
        [float(pair["proxy"]) for pair in combined],
        [float(pair["reference"]) for pair in combined],
    )
    bootstrap = _bootstrap_spearman_interval(combined, iterations=BOOTSTRAP_ITERATIONS, seed=BOOTSTRAP_SEED)
    statistical_support = _claim_grade_statistical_support(
        pair_count=len(combined),
        holdout_pair_count=split_counts.get("holdout", 0),
        bootstrap_low=bootstrap["free_energy_spearman_bootstrap_p05"],
    )
    return {
        "existing_pair_count": len(existing_pairs),
        "candidate_pair_count": len(candidate_pairs),
        "combined_pair_count": len(combined),
        "combined_fit_pair_count": split_counts.get("fit", 0),
        "combined_holdout_pair_count": split_counts.get("holdout", 0),
        "combined_unknown_split_pair_count": split_counts.get("unknown", 0),
        "combined_free_energy_spearman": spearman,
        **bootstrap,
        **statistical_support,
    }


def materialize_refine_tier_public_benchmark_statistical_support_metric_candidates(
    *,
    metric_source_templates_json: str | Path = DEFAULT_TEMPLATES_JSON,
    metric_materialization_readiness_json: str | Path = DEFAULT_READINESS_JSON,
    existing_materialization_csv: str | Path = DEFAULT_EXISTING_MATERIALIZATION_CSV,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_md: str | Path = DEFAULT_OUT_MD,
    root: str | Path = ROOT,
    operator_id: str = DEFAULT_OPERATOR_ID,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    generated_at = generated_at_utc or _utc_now()
    templates_payload, templates_present = _read_json(metric_source_templates_json, root=root_path)
    readiness_payload, readiness_present = _read_json(metric_materialization_readiness_json, root=root_path)
    template_rows = _rows(templates_payload)
    readiness_rows = _rows(readiness_payload)
    rows, pair_rows = _candidate_rows(
        template_rows,
        readiness_rows,
        generated_at_utc=generated_at,
        root=root_path,
        operator_id=operator_id,
    )
    pass_rows = [row for row in rows if row["candidate_status"] == "pass"]
    blocked_rows = [row for row in rows if row["candidate_status"] != "pass"]
    expected_present_count = sum(1 for row in rows if row["expected_metric_source_artifact_present"] is True)
    existing_pairs = _existing_pairs(_read_csv(existing_materialization_csv, root=root_path))
    candidate_pairs = _candidate_pairs(pair_rows)
    support = _support_summary(existing_pairs, candidate_pairs)
    blockers: list[str] = []
    if not templates_present:
        blockers.append("metric_source_templates_missing")
    if not readiness_present:
        blockers.append("metric_materialization_readiness_missing")
    if blocked_rows:
        blockers.append("candidate_metric_rows_blocked")
    status = (
        "refine_tier_public_benchmark_statistical_support_metric_candidates_ready"
        if templates_present and readiness_present and rows and not blocked_rows
        else "blocked_refine_tier_public_benchmark_statistical_support_metric_candidates"
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill",
        "status": status,
        "metric_source_templates": _display(metric_source_templates_json, root=root_path),
        "metric_source_templates_present": templates_present,
        "metric_materialization_readiness": _display(metric_materialization_readiness_json, root=root_path),
        "metric_materialization_readiness_present": readiness_present,
        "existing_materialization_csv": _display(existing_materialization_csv, root=root_path),
        "out_csv": _display(out_csv, root=root_path),
        "template_row_count": len(template_rows),
        "candidate_row_count": len(rows),
        "candidate_pass_row_count": len(pass_rows),
        "candidate_blocked_row_count": len(blocked_rows),
        "metric_value_candidate_count": sum(1 for row in rows if _text(row.get("metric_value_candidate"))),
        "candidate_pair_row_count": len(pair_rows),
        "candidate_pair_pass_count": len(candidate_pairs),
        "expected_metric_source_artifact_present_count": expected_present_count,
        "expected_metric_source_artifact_touched_count": 0,
        "payload_write_allowed": False,
        "operator_receipt_approval_filled": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "external_engine_calls": 0,
        "external_state_mutated": False,
        "operator_id_candidate": operator_id,
        "generated_at_utc": generated_at,
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "source_payload_claim_boundary": SOURCE_PAYLOAD_CLAIM_BOUNDARY,
        "min_claim_grade_public_benchmark_pairs_required": MIN_CLAIM_GRADE_PUBLIC_BENCHMARK_PAIRS,
        "min_claim_grade_holdout_pairs_required": MIN_CLAIM_GRADE_HOLDOUT_PAIRS,
        "min_claim_grade_bootstrap_spearman_low_required": MIN_CLAIM_GRADE_BOOTSTRAP_SPEARMAN_LOW,
        **support,
    }
    payload = {"summary": summary, "candidate_pairs": pair_rows, "rows": rows}
    _write_outputs(payload, out_json=out_json, out_csv=out_csv, out_md=out_md, root=root_path)
    return payload


def _write_outputs(
    payload: dict[str, Any],
    *,
    out_json: str | Path,
    out_csv: str | Path,
    out_md: str | Path,
    root: Path,
) -> None:
    json_path = _resolve(out_json, root=root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_csv_rows(_resolve(out_csv, root=root), payload["rows"])
    md_path = _resolve(out_md, root=root)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_render_md(payload, root=root), encoding="utf-8")


def _render_md(payload: dict[str, Any], *, root: Path) -> str:
    summary = payload["summary"]
    json_size = _human_size(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")))
    lines = [
        "# R9 Statistical-Support Metric Candidate Fill",
        "",
        f"- status: `{summary['status']}`",
        f"- candidate rows: `{summary['candidate_pass_row_count']}/{summary['candidate_row_count']}`",
        f"- metric values computed: `{summary['metric_value_candidate_count']}`",
        f"- candidate pairs: `{summary['candidate_pair_pass_count']}`",
        f"- combined public benchmark pairs: `{summary['combined_pair_count']}`",
        f"- combined fit/holdout pairs: `{summary['combined_fit_pair_count']}/{summary['combined_holdout_pair_count']}`",
        f"- combined Spearman: `{summary['combined_free_energy_spearman']}`",
        "- bootstrap Spearman p05/p50/p95: "
        f"`{summary['free_energy_spearman_bootstrap_p05']}/"
        f"{summary['free_energy_spearman_bootstrap_p50']}/"
        f"{summary['free_energy_spearman_bootstrap_p95']}`",
        "- claim-grade statistical support ready: "
        f"`{summary['claim_grade_public_benchmark_statistical_support_ready']}`",
        f"- claim-grade blockers: `{summary['claim_grade_public_benchmark_statistical_support_blockers']}`",
        f"- expected metric source artifacts touched: `{summary['expected_metric_source_artifact_touched_count']}`",
        f"- expected metric source artifacts already present: `{summary['expected_metric_source_artifact_present_count']}`",
        f"- compact JSON size: `{json_size}`",
        "",
        "## Candidate Pairs",
        "",
        "| work_order_id | target | pose | split | dG candidate | dG experimental | dockq | lddt_pli | status |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_pairs"][:25]:
        lines.append(
            f"| `{row['work_order_id']}` | `{row['target_id']}` | `{row['pose_id']}` | `{row['split']}` | "
            f"`{row['deltaG_candidate_kcal_mol']}` | `{row['deltaG_experimental_kcal_mol']}` | "
            f"`{row['dockq']}` | `{row['lddt_pli']}` | `{row['candidate_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize fail-closed R9 statistical-support metric candidate fill values."
    )
    parser.add_argument("--metric-source-templates-json", default=DEFAULT_TEMPLATES_JSON)
    parser.add_argument("--metric-materialization-readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--existing-materialization-csv", default=DEFAULT_EXISTING_MATERIALIZATION_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--operator-id", default=DEFAULT_OPERATOR_ID)
    parser.add_argument("--generated-at-utc", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    payload = materialize_refine_tier_public_benchmark_statistical_support_metric_candidates(
        metric_source_templates_json=args.metric_source_templates_json,
        metric_materialization_readiness_json=args.metric_materialization_readiness_json,
        existing_materialization_csv=args.existing_materialization_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        root=args.root,
        operator_id=args.operator_id,
        generated_at_utc=args.generated_at_utc,
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
