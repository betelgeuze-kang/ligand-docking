#!/usr/bin/env python3
"""Probe PocketMD Lite top-k metric collection inputs.

This is a read-only telemetry collector. It extracts any pre-existing
claim-grade NPZ metric fields and computes coarse trajectory diagnostics from
the selected two-bead trajectory inputs. Coarse diagnostics are useful for
operator triage, but they are not written back to the candidate CSV and are not
promoted as claim-grade local-min/H-bond/clash-relief persistence evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from betelgeuze_engine.backmapping.onsps import backmap_4bead_onsps, hbond_angle_score
from betelgeuze_product.pocketmd_lite_contract import LOCAL_MIN_SURVIVAL_RMSD_A

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_CSV = "runs/pocketmd_lite_metric_collection_input_pack_current.csv"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_metric_collection_probe_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_metric_collection_probe_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_metric_collection_probe_current.csv"

PACKET_TYPE = "pocketmd_lite_metric_collection_probe"
SCHEMA_VERSION = "pocketmd_lite_metric_collection_probe_v1"

CLAIM_BOUNDARY = (
    "PocketMD Lite metric collection probe only; it extracts existing NPZ metric fields when present and computes "
    "coarse two-bead trajectory telemetry for local triage. Coarse local-min RMSD, ONSPS H-bond-like persistence, "
    "and clash/contact telemetry are proxy diagnostics, not claim-grade PocketMD Lite evidence. This tool does not "
    "run local-min/OpenMM, atomize ligands, write candidate metrics, promote claims, copy restore files, or mutate "
    "external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "claim_promotion_allowed": False,
    "candidate_csv_update_allowed": False,
}

_CSV_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "selected_trajectory_npz",
    "selected_trajectory_source",
    "trajectory_probe_status",
    "trajectory_schema",
    "trajectory_frame_count",
    "ligand_bead_count",
    "protein_ca_count",
    "protein_atom_frame_count",
    "coarse_local_min_ligand_rmsd_a",
    "coarse_local_min_survival_proxy",
    "coarse_hbond_persistence_proxy",
    "coarse_contact_persistence_proxy",
    "coarse_clash_frame_fraction_proxy",
    "mean_min_distance_a",
    "min_min_distance_a",
    "final_min_distance_a",
    "onsps_backmap_claim_safe",
    "onsps_site_count",
    "onsps_mapped_site_count",
    "onsps_mapping_source",
    "exact_contact_persistence",
    "exact_local_min_ligand_rmsd_a",
    "exact_hbond_persistence",
    "exact_initial_clash_count",
    "exact_clash_count",
    "exact_clash_relief_count",
    "missing_claim_grade_metrics",
    "claim_grade_metric_ready",
    "recommended_next_local_action",
    "blockers",
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
    "claim_promotion_allowed",
    "candidate_csv_update_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    text = _text(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            if value.size != 1:
                return None
            value = value.reshape(-1)[0]
        text = _text(value)
        if not text:
            return None
        number = float(text)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _required_metrics(source: dict[str, Any]) -> list[str]:
    metrics = [
        part
        for part in _text(source.get("required_collection_metrics")).split(";")
        if part
    ]
    return metrics or ["local_min_ligand_rmsd_a", "hbond_persistence"]


def _npz_optional_float(payload: Any, *keys: str) -> float | None:
    for key in keys:
        if key in payload.files:
            value = _optional_float(payload[key])
            if value is not None:
                return value
    return None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _valid_xyz2(arr: np.ndarray) -> bool:
    return arr.ndim == 2 and arr.shape[0] > 0 and arr.shape[1] == 3


def _valid_frames(arr: np.ndarray) -> bool:
    return arr.ndim == 3 and arr.shape[0] > 0 and arr.shape[1] >= 2 and arr.shape[2] == 3


def _rmsd(a: np.ndarray, b: np.ndarray) -> float:
    diff = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _distance_series(protein_ca: np.ndarray, ligand_frames: np.ndarray) -> np.ndarray:
    mins: list[float] = []
    for frame in ligand_frames:
        d = np.linalg.norm(protein_ca[:, None, :] - frame[None, :, :], axis=2)
        mins.append(float(np.min(d)))
    return np.asarray(mins, dtype=np.float64)


def _npz_array(payload: Any, key: str, default: Any) -> np.ndarray:
    try:
        if key in payload.files:
            return np.asarray(payload[key])
    except Exception:
        pass
    return np.asarray(default)


def _hbond_proxy_series(
    protein_ca: np.ndarray,
    ligand_frames: np.ndarray,
    smiles: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    hits: list[bool] = []
    meta: dict[str, Any] = {}
    for frame in ligand_frames:
        mapped, frame_meta = backmap_4bead_onsps(frame[:2], smiles)
        if not meta:
            meta = dict(frame_meta)
        mapped = np.asarray(mapped, dtype=np.float32)
        if mapped.ndim != 2 or mapped.shape[0] <= 0:
            hits.append(False)
            continue
        pocket_center = np.asarray(frame[:2], dtype=np.float32).mean(axis=0)
        frame_hit = False
        for bead in mapped:
            distances = np.linalg.norm(protein_ca - bead.reshape(1, 3), axis=1)
            nearest = float(np.min(distances)) if distances.size else 999.0
            angle = hbond_angle_score(protein_ca, bead, pocket_center)
            if nearest <= 3.6 and angle >= 0.05:
                frame_hit = True
                break
        hits.append(frame_hit)
    return np.asarray(hits, dtype=np.bool_), meta


def _empty_row(source: dict[str, Any], *, status: str, blockers: list[str]) -> dict[str, Any]:
    return {
        "entry_id": _text(source.get("entry_id")),
        "target": _text(source.get("target")),
        "ligand_id": _text(source.get("ligand_id")),
        "selected_trajectory_npz": _display(source.get("selected_trajectory_npz")),
        "selected_trajectory_source": _text(source.get("selected_trajectory_source")),
        "trajectory_probe_status": status,
        "trajectory_schema": "",
        "trajectory_frame_count": 0,
        "ligand_bead_count": 0,
        "protein_ca_count": 0,
        "protein_atom_frame_count": 0,
        "coarse_local_min_ligand_rmsd_a": None,
        "coarse_local_min_survival_proxy": None,
        "coarse_hbond_persistence_proxy": None,
        "coarse_contact_persistence_proxy": None,
        "coarse_clash_frame_fraction_proxy": None,
        "mean_min_distance_a": None,
        "min_min_distance_a": None,
        "final_min_distance_a": None,
        "onsps_backmap_claim_safe": False,
        "onsps_site_count": 0,
        "onsps_mapped_site_count": 0,
        "onsps_mapping_source": "",
        "exact_contact_persistence": None,
        "exact_local_min_ligand_rmsd_a": None,
        "exact_hbond_persistence": None,
        "exact_initial_clash_count": None,
        "exact_clash_count": None,
        "exact_clash_relief_count": None,
        "missing_claim_grade_metrics": _required_metrics(source),
        "claim_grade_metric_ready": False,
        "recommended_next_local_action": "restore_or_regenerate_missing_collection_inputs",
        "blockers": blockers,
        **_READ_ONLY_FLAGS,
    }


def _probe_row(source: dict[str, Any]) -> dict[str, Any]:
    npz_path = _resolve(source.get("selected_trajectory_npz", ""))
    if not _text(source.get("selected_trajectory_npz")):
        return _empty_row(source, status="blocked_missing_selected_trajectory_npz", blockers=["selected_trajectory_npz_missing"])
    if not npz_path.exists():
        return _empty_row(source, status="blocked_selected_trajectory_npz_unavailable", blockers=["selected_trajectory_npz_unavailable"])

    try:
        with np.load(npz_path, allow_pickle=False) as payload:
            protein_ca = np.asarray(_npz_array(payload, "protein_ca", np.zeros((0, 3))), dtype=np.float32)
            ligand_frames = np.asarray(_npz_array(payload, "ligand_frames", np.zeros((0, 0, 3))), dtype=np.float32)
            protein_atom_frames = np.asarray(
                _npz_array(payload, "protein_atom_frames", np.zeros((0, 0, 3))),
                dtype=np.float32,
            )
            exact_contact = _npz_optional_float(payload, "contact_persistence")
            exact_local = _npz_optional_float(payload, "local_min_ligand_rmsd_a")
            exact_hbond = _npz_optional_float(payload, "hbond_persistence")
            exact_initial_clash = _npz_optional_float(
                payload,
                "initial_clash_count",
                "pre_refine_clash_count",
            )
            exact_clash = _npz_optional_float(payload, "clash_count")
    except Exception as exc:
        return _empty_row(
            source,
            status="blocked_selected_trajectory_npz_unreadable",
            blockers=[f"selected_trajectory_npz_unreadable:{type(exc).__name__}"],
        )

    blockers: list[str] = []
    if not _valid_xyz2(protein_ca):
        blockers.append("protein_ca_schema_invalid")
    if not _valid_frames(ligand_frames):
        blockers.append("ligand_frames_schema_not_two_bead_or_better")
    if blockers:
        row = _empty_row(source, status="blocked_trajectory_schema_invalid", blockers=blockers)
        row["trajectory_schema"] = "invalid"
        return row

    min_dist = _distance_series(protein_ca, ligand_frames)
    coarse_rmsd = _rmsd(ligand_frames[-1], ligand_frames[0])
    contact_proxy = float(np.mean(min_dist <= 6.0)) if min_dist.size else 0.0
    clash_proxy = float(np.mean(min_dist < 2.1)) if min_dist.size else 0.0
    smiles = _text(source.get("ligand_smiles"))
    hbond_proxy: float | None = None
    onsps_meta: dict[str, Any] = {}
    if smiles:
        hbond_hits, onsps_meta = _hbond_proxy_series(protein_ca, ligand_frames, smiles)
        hbond_proxy = float(np.mean(hbond_hits)) if hbond_hits.size else 0.0
    else:
        blockers.append("ligand_smiles_missing_for_onsps_proxy")

    exact_metric_values = {
        "contact_persistence": exact_contact,
        "local_min_ligand_rmsd_a": exact_local,
        "hbond_persistence": exact_hbond,
        "initial_clash_count": exact_initial_clash,
        "pre_refine_clash_count": exact_initial_clash,
        "clash_count": exact_clash,
    }
    required_metrics = _required_metrics(source)
    missing_claim_grade_metrics = [
        metric for metric in required_metrics if exact_metric_values.get(metric) is None
    ]
    claim_grade_ready = not missing_claim_grade_metrics
    if not claim_grade_ready:
        blockers.append("claim_grade_metric_fields_missing:" + ",".join(missing_claim_grade_metrics))
        if protein_atom_frames.ndim != 3 or protein_atom_frames.shape[0] <= 0:
            blockers.append("atomized_protein_frames_missing_for_claim_grade_hbond")
        if int(ligand_frames.shape[1]) <= 2:
            blockers.append("ligand_trajectory_is_two_bead_proxy")

    status = "pocketmd_lite_metric_collection_probe_ready" if claim_grade_ready else "blocked_pocketmd_lite_metric_collection_probe_proxy_only"
    row = {
        "entry_id": _text(source.get("entry_id")),
        "target": _text(source.get("target")),
        "ligand_id": _text(source.get("ligand_id")),
        "selected_trajectory_npz": _display(source.get("selected_trajectory_npz")),
        "selected_trajectory_source": _text(source.get("selected_trajectory_source")),
        "trajectory_probe_status": status,
        "trajectory_schema": "coarse_two_bead_ca",
        "trajectory_frame_count": int(ligand_frames.shape[0]),
        "ligand_bead_count": int(ligand_frames.shape[1]),
        "protein_ca_count": int(protein_ca.shape[0]),
        "protein_atom_frame_count": int(protein_atom_frames.shape[1]) if protein_atom_frames.ndim == 3 else 0,
        "coarse_local_min_ligand_rmsd_a": coarse_rmsd,
        "coarse_local_min_survival_proxy": bool(coarse_rmsd <= LOCAL_MIN_SURVIVAL_RMSD_A),
        "coarse_hbond_persistence_proxy": hbond_proxy,
        "coarse_contact_persistence_proxy": contact_proxy,
        "coarse_clash_frame_fraction_proxy": clash_proxy,
        "mean_min_distance_a": float(np.mean(min_dist)) if min_dist.size else None,
        "min_min_distance_a": float(np.min(min_dist)) if min_dist.size else None,
        "final_min_distance_a": float(min_dist[-1]) if min_dist.size else None,
        "onsps_backmap_claim_safe": bool(onsps_meta.get("claim_safe") is True),
        "onsps_site_count": int(onsps_meta.get("site_count", 0) or 0),
        "onsps_mapped_site_count": int(onsps_meta.get("mapped_site_count", 0) or 0),
        "onsps_mapping_source": _text(onsps_meta.get("mapping_source")),
        "exact_contact_persistence": exact_contact,
        "exact_local_min_ligand_rmsd_a": exact_local,
        "exact_hbond_persistence": exact_hbond,
        "exact_initial_clash_count": exact_initial_clash,
        "exact_clash_count": exact_clash,
        "exact_clash_relief_count": (
            None
            if exact_initial_clash is None or exact_clash is None
            else exact_initial_clash - exact_clash
        ),
        "missing_claim_grade_metrics": missing_claim_grade_metrics,
        "claim_grade_metric_ready": claim_grade_ready,
        "recommended_next_local_action": (
            "extract_claim_grade_metrics_into_candidate_csv_then_rerun_pocketmd_lite_report"
            if claim_grade_ready
            else "generate_atomized_or_claim_grade_npz_local_min_hbond_clash_relief_fields_then_rerun_probe"
        ),
        "blockers": blockers,
        **_READ_ONLY_FLAGS,
    }
    return row


def build_pocketmd_lite_metric_collection_probe(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
) -> dict[str, Any]:
    input_path = _resolve(input_csv)
    source_rows = _read_csv(input_path)
    rows = [_probe_row(row) for row in source_rows if _bool(row.get("collection_input_ready"))]
    telemetry_ready_count = sum(1 for row in rows if row["trajectory_probe_status"] != "blocked_selected_trajectory_npz_unavailable")
    claim_grade_ready_count = sum(1 for row in rows if row["claim_grade_metric_ready"])
    proxy_only_count = sum(1 for row in rows if row["trajectory_probe_status"] == "blocked_pocketmd_lite_metric_collection_probe_proxy_only")
    status = (
        "pocketmd_lite_metric_collection_probe_ready"
        if rows and claim_grade_ready_count == len(rows)
        else "blocked_pocketmd_lite_metric_collection_probe_proxy_only"
        if rows
        else "blocked_pocketmd_lite_metric_collection_probe_no_inputs"
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "input_csv": _display(input_path),
        "candidate_count": len(rows),
        "telemetry_ready_count": telemetry_ready_count,
        "proxy_only_count": proxy_only_count,
        "claim_grade_metric_ready_count": claim_grade_ready_count,
        "coarse_local_min_survival_proxy_count": sum(1 for row in rows if row["coarse_local_min_survival_proxy"] is True),
        "coarse_hbond_proxy_observed_count": sum(
            1 for row in rows if (row["coarse_hbond_persistence_proxy"] is not None and row["coarse_hbond_persistence_proxy"] > 0)
        ),
        "candidate_csv_update_allowed": False,
        "next_required_step": (
            "Extract claim-grade NPZ metric fields into the PocketMD Lite candidate CSV, then rerun the report."
            if rows and claim_grade_ready_count == len(rows)
            else (
                "Generate atomized/backmapped or otherwise claim-grade local_min_ligand_rmsd_a, "
                "hbond_persistence, and clash-relief baseline fields required by the input pack; "
                "coarse telemetry remains proxy-only."
            )
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Metric Collection Probe",
        "",
        f"- status: `{summary['status']}`",
        f"- telemetry_ready_count: `{summary['telemetry_ready_count']}` / `{summary['candidate_count']}`",
        f"- claim_grade_metric_ready_count: `{summary['claim_grade_metric_ready_count']}`",
        f"- proxy_only_count: `{summary['proxy_only_count']}`",
        "",
        "| entry | status | coarse local-min RMSD | hbond proxy | claim-grade ready | action |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{status}` | `{rmsd}` | `{hbond}` | `{ready}` | `{action}` |".format(
                entry=row["entry_id"],
                status=row["trajectory_probe_status"],
                rmsd=_fmt(row["coarse_local_min_ligand_rmsd_a"]),
                hbond=_fmt(row["coarse_hbond_persistence_proxy"]),
                ready=str(row["claim_grade_metric_ready"]).lower(),
                action=row["recommended_next_local_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe PocketMD Lite metric collection inputs.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_metric_collection_probe(input_csv=args.input_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
