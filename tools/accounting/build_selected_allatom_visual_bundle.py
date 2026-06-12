#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None

from tools import render_chimerax_movies
from tools import run_visual_polish_pipeline as visual_polish_mod
from tools import visualize_experiment_dashboard
from tools.build_selected_allatom_aligned_reference import build_aligned_reference
from tools.native_target_registry import (
    find_matching_target_row,
    load_repo_native_registry as load_shared_repo_native_registry,
    normalize_target_key,
    resolve_repo_native_entry,
)
from tools.wetlab.wetlab_selected_allatom_canonical import resolve_selected_allatom_canonical
from tools.wetlab_target_render_utils import load_json, maybe_load_json, resolve, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RETRY_HANDOFF_JSON = "runs/wetlab_retry_handoff_summary_current.json"
DEFAULT_CURRENT_RESULTS_INDEX_JSON = "runs/wetlab_current_results_index_current.json"
DEFAULT_MONITOR_SEMANTICS_JSON = "runs/wetlab_monitor_semantics_current.json"
DEFAULT_MASTER_HANDOFF_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_PARTNERING_STACK_JSON = "runs/wetlab_partnering_stack_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_cathepsin_k_allatom_review_packet_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_LANE_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_LANE_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_RUNNER_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_RUNNER_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_runner_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_RUNNER_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_runner_current.json"
DEFAULT_OUT_MD = "runs/selected_allatom_visual_bundle_current.md"
DEFAULT_OUT_CATALOG_JSON = "runs/selected_allatom_visual_bundle_catalog_current.json"
DEFAULT_TOP_K = 4
DEFAULT_ASSETS_ROOT = "runs/selected_allatom_visual_bundle_assets"
VISUAL_BUNDLE_MANIFEST_VERSION = "selected_allatom_visual_bundle_v2"

SURFACE_REGISTRY = {
    "tcruzi_pde_allatom_review_packet": {
        "target_id": "T. cruzi PDE",
        "review_packet_json": DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON,
        "lane_json": DEFAULT_TCRUZI_PDE_ALLATOM_LANE_JSON,
        "runner_json": DEFAULT_TCRUZI_PDE_ALLATOM_RUNNER_JSON,
    },
    "cathepsin_k_allatom_review_packet": {
        "target_id": "Cathepsin K",
        "review_packet_json": DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON,
        "lane_json": DEFAULT_CATHEPSIN_K_ALLATOM_LANE_JSON,
        "runner_json": DEFAULT_CATHEPSIN_K_ALLATOM_RUNNER_JSON,
    },
    "sarscov2_mpro_allatom_review_packet": {
        "target_id": "SARS-CoV-2 Mpro",
        "review_packet_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON,
        "lane_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_LANE_JSON,
        "runner_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_RUNNER_JSON,
    },
    "sars_cov_2_mpro_allatom_review_packet": {
        "target_id": "SARS-CoV-2 Mpro",
        "review_packet_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON,
        "lane_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_LANE_JSON,
        "runner_json": DEFAULT_SARSCOV2_MPRO_ALLATOM_RUNNER_JSON,
    },
}

TARGET_TO_SURFACE = {
    "T. cruzi PDE": "tcruzi_pde_allatom_review_packet",
    "Cathepsin K": "cathepsin_k_allatom_review_packet",
    "SARS-CoV-2 Mpro": "sarscov2_mpro_allatom_review_packet",
}

TARGET_TO_BUNDLE_STEM = {
    "T. cruzi PDE": "tcruzi_pde",
    "Cathepsin K": "cathepsin_k",
    "SARS-CoV-2 Mpro": "sarscov2_mpro",
}


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _structured(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("structured", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _slug(text: str) -> str:
    out: list[str] = []
    prev_us = False
    for ch in str(text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    slug = "".join(out).strip("_")
    return slug or "selected_allatom"


def _bundle_stem_for_target(target_id: str) -> str:
    target_text = _text(target_id)
    return TARGET_TO_BUNDLE_STEM.get(target_text, _slug(target_text))


def _target_bundle_out_md(target_id: str) -> Path:
    stem = _bundle_stem_for_target(target_id)
    return ROOT / "runs" / f"selected_allatom_visual_bundle_{stem}_current.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float_optional(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except Exception:
        return None


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}


@lru_cache(maxsize=1)
def _load_repo_native_registry() -> dict[str, dict[str, Any]]:
    return dict(load_shared_repo_native_registry())


def _csv_list_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item or "").strip() for item in value if str(item or "").strip())
    text = str(value).strip()
    return "" if not text else text


def _to_atom_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    xyz: tuple[float, float, float] | list[float] | np.ndarray,
    element: str,
    *,
    hetatm: bool = False,
) -> str:
    rec = "HETATM" if bool(hetatm) else "ATOM  "
    x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
    return (
        f"{rec}{serial:5d} {str(atom_name or 'C')[:4]:<4s}{str(res_name or 'LIG')[:3]:>3s} "
        f"{str(chain_id or 'A')[:1]}{int(res_seq):4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{30.0:6.2f}          {str(element or 'C')[:2]:>2s}"
    )


def _parse_ligand_template_atoms(path_like: str) -> list[dict[str, Any]]:
    path = resolve(path_like)
    if not path.exists():
        return []
    atoms: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not (line.startswith("ATOM  ") or line.startswith("HETATM")):
            continue
        atom_name = str(line[12:16].strip() or "C")
        residue_name = str(line[17:20].strip() or "LIG")
        chain_id = str(line[21:22].strip() or "L")
        residue_seq = _safe_int(line[22:26].strip(), 1)
        element = str(line[76:78].strip() or atom_name[:2] or "C").strip()
        is_ligand = residue_name == "LIG" or chain_id == "L" or line.startswith("HETATM")
        if not is_ligand:
            continue
        atoms.append(
            {
                "atom_name": atom_name,
                "residue_name": residue_name,
                "chain_id": chain_id,
                "residue_seq": residue_seq,
                "element": element[:2] or "C",
            }
        )
    return atoms


def _compute_min_distance_series(protein_ca: np.ndarray, ligand_frames: np.ndarray) -> np.ndarray:
    prot = np.asarray(protein_ca, dtype=np.float32)
    lig = np.asarray(ligand_frames, dtype=np.float32)
    if prot.ndim != 2 or prot.shape[1] != 3:
        raise ValueError("protein_ca must have shape [P,3]")
    if lig.ndim != 3 or lig.shape[2] != 3:
        raise ValueError("ligand_frames must have shape [T,L,3]")
    if prot.shape[0] <= 0 or lig.shape[0] <= 0 or lig.shape[1] <= 0:
        raise ValueError("protein_ca and ligand_frames must be non-empty")
    diff = prot[None, :, None, :] - lig[:, None, :, :]
    dist = np.sqrt(np.sum(diff * diff, axis=-1))
    return np.min(dist, axis=(1, 2)).astype(np.float32, copy=False)


def _protein_context_is_meaningful(protein_ca: np.ndarray) -> bool:
    prot = np.asarray(protein_ca, dtype=np.float32)
    if prot.ndim != 2 or prot.shape[1] != 3:
        return False
    if prot.shape[0] < 3:
        return False
    if np.allclose(prot, 0.0, atol=1e-6):
        return False
    spread = _protein_context_spread_A(prot)
    return spread >= 1.0


def _protein_context_spread_A(protein_ca: np.ndarray) -> float:
    prot = np.asarray(protein_ca, dtype=np.float32)
    if prot.ndim != 2 or prot.shape[1] != 3 or prot.shape[0] <= 0:
        return 0.0
    span = np.max(prot, axis=0) - np.min(prot, axis=0)
    return float(np.linalg.norm(span))


def _write_viewer_reference_pdb(
    out_path: Path,
    protein_ca: np.ndarray,
    ligand_xyz: np.ndarray,
    ligand_template_atoms: list[dict[str, Any]],
    *,
    frame_index: int,
    trajectory_index: int,
) -> None:
    lines = [
        f"REMARK VIEWER_REFERENCE_FRAME {int(frame_index)}",
        f"REMARK VIEWER_TRAJECTORY_INDEX {int(trajectory_index)}",
        "REMARK PROTEIN_CONTEXT stage2_npz_ca_projection",
    ]
    serial = 1
    for idx in range(int(protein_ca.shape[0])):
        lines.append(
            _to_atom_line(
                serial,
                "CA",
                "GLY",
                "A",
                idx + 1,
                protein_ca[idx],
                "C",
                hetatm=False,
            )
        )
        serial += 1

    if int(protein_ca.shape[0]) > 0:
        lines.append("TER")

    ligand_atom_count = int(ligand_xyz.shape[0])
    for idx in range(ligand_atom_count):
        template = ligand_template_atoms[idx] if idx < len(ligand_template_atoms) else {}
        lines.append(
            _to_atom_line(
                serial,
                str(template.get("atom_name") or f"C{idx + 1}")[:4],
                str(template.get("residue_name") or "LIG")[:3],
                str(template.get("chain_id") or "L")[:1],
                _safe_int(template.get("residue_seq"), 1),
                ligand_xyz[idx],
                str(template.get("element") or "C")[:2],
                hetatm=True,
            )
        )
        serial += 1

    lines.append("END")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_viewer_structure_artifact(
    *,
    trajectory_npz: str,
    backmapped_pdb: str,
    out_path: Path,
    out_pose_path: Path | None = None,
) -> dict[str, Any]:
    trajectory_path = resolve(trajectory_npz) if _text(trajectory_npz) else Path()
    ligand_template_path = resolve(backmapped_pdb) if _text(backmapped_pdb) else Path()
    if (not trajectory_path.exists()) or (not ligand_template_path.exists()):
        return {}

    try:
        payload = np.load(trajectory_path, allow_pickle=False)
        protein_ca = np.asarray(payload["protein_ca"], dtype=np.float32)
        ligand_frames = np.asarray(payload["ligand_frames"], dtype=np.float32)
        frame_indices = np.asarray(
            payload["frame_indices"]
            if "frame_indices" in payload.files
            else np.arange(ligand_frames.shape[0], dtype=np.int32),
            dtype=np.int32,
        )
        ligand_template_atoms = _parse_ligand_template_atoms(str(ligand_template_path))
        if protein_ca.ndim != 2 or protein_ca.shape[1] != 3:
            return {}
        if ligand_frames.ndim != 3 or ligand_frames.shape[2] != 3:
            return {}
        if ligand_frames.shape[0] <= 0:
            return {}
        protein_context_valid = _protein_context_is_meaningful(protein_ca)
        protein_ca_spread_A = _protein_context_spread_A(protein_ca)
        if protein_ca.shape[0] < 3:
            protein_context_reason = "protein_ca_count_lt_3"
        elif np.allclose(protein_ca, 0.0, atol=1e-6):
            protein_context_reason = "protein_ca_all_zero"
        elif protein_ca_spread_A < 1.0:
            protein_context_reason = "protein_ca_spread_too_small"
        else:
            protein_context_reason = "ok"
        min_distance_series = _compute_min_distance_series(protein_ca, ligand_frames)
        reference_frame_index = int(np.argmin(min_distance_series))
        trajectory_index = int(frame_indices[reference_frame_index]) if frame_indices.size > reference_frame_index else reference_frame_index
        pose_path = out_pose_path or out_path.with_name(f"{out_path.stem}_ligand_pose.pdb")
        _write_viewer_reference_pdb(
            pose_path,
            np.zeros((0, 3), dtype=np.float32),
            ligand_frames[reference_frame_index],
            ligand_template_atoms,
            frame_index=reference_frame_index,
            trajectory_index=trajectory_index,
        )
        if protein_context_valid:
            _write_viewer_reference_pdb(
                out_path,
                protein_ca,
                ligand_frames[reference_frame_index],
                ligand_template_atoms,
                frame_index=reference_frame_index,
                trajectory_index=trajectory_index,
            )
        return {
            "viewer_reference_pdb": str(out_path) if protein_context_valid else "",
            "viewer_reference_pdb_ready": bool(protein_context_valid and out_path.exists()),
            "viewer_pose_pdb": str(pose_path) if pose_path.exists() else "",
            "viewer_pose_pdb_ready": bool(pose_path.exists()),
            "viewer_structure_context_mode": (
                "protein_ca_plus_ligand_reference_frame"
                if protein_context_valid
                else "ligand_bead_only_trajectory"
            ),
            "viewer_reference_frame_index": reference_frame_index,
            "viewer_reference_trajectory_index": trajectory_index,
            "viewer_reference_min_distance_A": float(min_distance_series[reference_frame_index]),
            "viewer_trajectory_min_distance_A": float(np.min(min_distance_series)),
            "viewer_trajectory_max_distance_A": float(np.max(min_distance_series)),
            "viewer_frame_count": int(ligand_frames.shape[0]),
            "viewer_protein_ca_count": int(protein_ca.shape[0]),
            "viewer_protein_ca_spread_A": float(protein_ca_spread_A),
            "viewer_ligand_atom_count": int(ligand_frames.shape[1]),
            "viewer_protein_context_valid": bool(protein_context_valid),
            "viewer_protein_context_quality_gate_pass": bool(protein_context_valid),
            "viewer_protein_context_reason": protein_context_reason,
            "viewer_protein_context_note": (
                "Protein context is derived from stage2 trajectory NPZ and currently contains CA-only coordinates."
                if protein_context_valid
                else "Protein context is not available for this run; stage2 NPZ contains only trivial/dummy CA coordinates, so the viewer should use ligand-only trajectory playback."
            ),
        }
    except Exception:
        return {}


def _action_recipe_rollup(action_rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in action_rows:
        severity = _text(row.get("severity"))
        action = _text(row.get("action"))
        status = _text(row.get("status"))
        lane = _text(row.get("lane"))
        token = _joined(
            f"{severity}:{action}" if severity or action else "",
            f"[{status}]" if status else "",
            default="",
            sep="",
        )
        if lane:
            token = _joined(token, f"lane={lane}", sep=" ")
        if token:
            parts.append(token)
    return " | ".join(parts)


def _resolve_target_native_csv_path(
    lane_summary: dict[str, Any],
    runner_summary: dict[str, Any],
) -> str:
    explicit = _text(
        lane_summary.get("rescue_target_native_csv"),
        runner_summary.get("rescue_target_native_csv"),
    )
    if explicit:
        return explicit
    for key in ("trajectory_root", "base_trajectory_root", "source_trajectory_root"):
        root = _text(lane_summary.get(key), runner_summary.get(key))
        if not root:
            continue
        candidate = resolve(root).parent / "target_native_stub.csv"
        if candidate.exists():
            return str(candidate)
    return ""


def _resolve_protein_reference_contract(
    *,
    target_id: str,
    lane_summary: dict[str, Any],
    runner_summary: dict[str, Any],
) -> dict[str, Any]:
    native_csv = _resolve_target_native_csv_path(lane_summary, runner_summary)
    default_note = (
        "No target-native mapping is available for this run; viewer should stay in ligand-only or CA-only context."
    )
    contract = {
        "protein_reference_source_csv": _text(native_csv),
        "protein_reference_structure_path": "",
        "protein_reference_structure_ready": False,
        "protein_reference_structure_format": "",
        "protein_reference_structure_aligned_for_viewer": False,
        "protein_reference_pdb_id": "",
        "protein_reference_notes": "",
        "protein_reference_provenance": "",
        "protein_reference_structure_note": default_note,
        "protein_reference_pocket_x": "",
        "protein_reference_pocket_y": "",
        "protein_reference_pocket_z": "",
    }
    if not native_csv:
        registry_entry = resolve_repo_native_entry(target_id)
        if registry_entry:
            ready = bool(registry_entry.get("native_pdb_ready"))
            contract.update(
                {
                    "protein_reference_source_csv": _text(registry_entry.get("source_csv")),
                    "protein_reference_structure_path": _text(registry_entry.get("native_pdb_path")),
                    "protein_reference_structure_ready": ready,
                    "protein_reference_structure_format": _text(registry_entry.get("native_format")),
                    "protein_reference_structure_aligned_for_viewer": False,
                    "protein_reference_pdb_id": _text(registry_entry.get("pdb_id")),
                    "protein_reference_notes": _text(registry_entry.get("notes")),
                    "protein_reference_provenance": "repo_config_native_registry",
                    "protein_reference_pocket_x": _text(registry_entry.get("pocket_x")),
                    "protein_reference_pocket_y": _text(registry_entry.get("pocket_y")),
                    "protein_reference_pocket_z": _text(registry_entry.get("pocket_z")),
                    "protein_reference_structure_note": (
                        "Protein reference came from the repo-native registry. Use it as auxiliary context until an aligned viewer structure is generated."
                        if ready
                        else "Repo-native registry has an entry, but the structure path is not usable."
                    ),
                }
            )
        return contract

    path = resolve(native_csv)
    if not path.exists():
        contract["protein_reference_provenance"] = "target_native_csv_missing"
        contract["protein_reference_structure_note"] = (
            f"Target-native mapping artifact is missing: {path}"
        )
        return contract

    try:
        rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    except Exception:
        contract["protein_reference_provenance"] = "target_native_csv_unreadable"
        contract["protein_reference_structure_note"] = (
            f"Target-native mapping could not be parsed: {path}"
        )
        return contract

    selected_row = find_matching_target_row(rows, target_id)

    native_path = _text(selected_row.get("native_pdb_path"))
    resolved_native = resolve(native_path) if native_path else Path()
    ready = bool(native_path and resolved_native.exists() and resolved_native.is_file())
    note = _text(selected_row.get("notes"))
    contract.update(
        {
            "protein_reference_structure_path": str(resolved_native) if ready else _text(native_path),
            "protein_reference_structure_ready": ready,
            "protein_reference_structure_format": resolved_native.suffix.lstrip(".").lower() if ready else "",
            "protein_reference_structure_aligned_for_viewer": False,
            "protein_reference_pdb_id": _text(selected_row.get("pdb_id")),
            "protein_reference_notes": note,
            "protein_reference_provenance": (
                "target_native_csv"
                if ready
                else "target_native_csv_stub_or_missing_native_path"
            ),
            "protein_reference_pocket_x": _text(selected_row.get("pocket_x")),
            "protein_reference_pocket_y": _text(selected_row.get("pocket_y")),
            "protein_reference_pocket_z": _text(selected_row.get("pocket_z")),
            "protein_reference_structure_note": (
                f"Protein reference is available at {resolved_native}; alignment to the trajectory frame is not yet guaranteed, so viewer keeps it as auxiliary context."
                if ready
                else _text(
                    note,
                    "Target-native mapping exists but does not yet provide a usable protein structure path.",
                )
            ),
        }
    )
    if ready:
        return contract

    registry_entry = resolve_repo_native_entry(target_id)
    if registry_entry:
        contract.update(
            {
                "protein_reference_source_csv": _text(registry_entry.get("source_csv")),
                "protein_reference_structure_path": _text(registry_entry.get("native_pdb_path")),
                "protein_reference_structure_ready": bool(registry_entry.get("native_pdb_ready")),
                "protein_reference_structure_format": _text(registry_entry.get("native_format")),
                "protein_reference_pdb_id": _text(contract.get("protein_reference_pdb_id"), registry_entry.get("pdb_id")),
                "protein_reference_notes": _joined(
                    contract.get("protein_reference_notes"),
                    registry_entry.get("notes"),
                    sep=" | ",
                    default="",
                ),
                "protein_reference_provenance": "target_native_csv_stub__repo_config_native_registry",
                "protein_reference_pocket_x": _text(registry_entry.get("pocket_x")),
                "protein_reference_pocket_y": _text(registry_entry.get("pocket_y")),
                "protein_reference_pocket_z": _text(registry_entry.get("pocket_z")),
                "protein_reference_structure_note": (
                    "Run-local target-native CSV is stubbed, so the bundle fell back to the repo-native registry."
                ),
            }
        )
    return contract


def _read_csv_rows(path_like: str) -> list[dict[str, Any]]:
    path = resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row or {}) for row in csv.DictReader(handle)]


def _read_score_json_payload(path_like: str) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rows_by_ligand(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ligand_id = _text(row.get("ligand_id"))
        if ligand_id and ligand_id not in out:
            out[ligand_id] = dict(row)
    return out


def _resolve_focus_contract(
    *,
    retry_handoff_payload: dict[str, Any] | None,
    review_packet_json: str,
    lane_json: str,
    runner_json: str,
    surface_label: str,
    registry: dict[str, dict[str, str]],
) -> dict[str, str]:
    retry_summary = _summary(retry_handoff_payload)
    resolved_surface_label = _text(surface_label, retry_summary.get("selected_allatom_surface_label"))
    resolved_target_id = _text(retry_summary.get("selected_allatom_target_id"))
    if not resolved_surface_label and resolved_target_id:
        resolved_surface_label = TARGET_TO_SURFACE.get(resolved_target_id, "")
    registry_entry = dict(registry.get(resolved_surface_label, {}) or {})
    return {
        "surface_label": resolved_surface_label,
        "target_id": _text(resolved_target_id, registry_entry.get("target_id")),
        "review_packet_json": _text(review_packet_json, registry_entry.get("review_packet_json")),
        "lane_json": _text(lane_json, registry_entry.get("lane_json")),
        "runner_json": _text(runner_json, registry_entry.get("runner_json")),
    }


def _resolve_scores_csv(
    review_summary: dict[str, Any],
    review_structured: dict[str, Any],
    lane_summary: dict[str, Any],
    runner_summary: dict[str, Any],
) -> str:
    return _text(
        review_structured.get("allatom_scores_csv"),
        review_structured.get("review_packet_scores_csv"),
        review_summary.get("allatom_scores_csv"),
        runner_summary.get("allatom_scores_csv"),
        lane_summary.get("allatom_scores_csv"),
    )


def _resolve_stage2_manifest_csv(
    review_summary: dict[str, Any],
    review_structured: dict[str, Any],
    lane_summary: dict[str, Any],
    runner_summary: dict[str, Any],
) -> str:
    return _text(
        review_structured.get("allatom_stage2_manifest_csv"),
        review_structured.get("stage2_manifest_csv"),
        review_summary.get("allatom_stage2_manifest_csv"),
        review_summary.get("stage2_manifest_csv"),
        runner_summary.get("allatom_stage2_manifest_csv"),
        runner_summary.get("stage2_manifest_csv"),
        lane_summary.get("source_stage2_manifest_csv"),
        lane_summary.get("base_stage2_manifest_csv"),
        lane_summary.get("stage2_manifest_csv"),
    )


def _resolve_primary_rows(
    review_packet_payload: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    review_rows = sorted(
        [dict(row or {}) for row in (review_packet_payload.get("rows", []) or [])],
        key=lambda row: _safe_int(row.get("packet_rank"), 9999),
    )
    if top_k > 0:
        return review_rows[:top_k]
    return review_rows


def _render_metric_panel(df: pd.DataFrame, out_path: Path) -> bool:
    if not MATPLOTLIB_AVAILABLE or df.empty or plt is None:
        return False
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    metrics = [
        ("mean_min_distance_A", "Mean Min Distance (A)"),
        ("binding_energy_proxy", "Binding Energy Proxy"),
        ("contact_fraction", "Contact Fraction"),
        ("stability_score", "Stability Score"),
    ]
    labels = [f"#{int(rank)}" for rank in df["packet_rank"].tolist()]
    colors = ["#0b7285", "#1c7ed6", "#e67700", "#2b8a3e", "#c92a2a", "#5f3dc4", "#495057", "#087f5b"]
    for ax, (col, title) in zip(axes.flat, metrics):
        vals = df[col].astype(float).tolist()
        ax.bar(labels, vals, color=colors[: len(vals)])
        ax.set_title(title)
        ax.set_xlabel("Packet Rank")
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"Selected All-Atom Top-k Metrics: {df['target_id'].iloc[0]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return True


def _render_scatter(df: pd.DataFrame, out_path: Path) -> bool:
    if not MATPLOTLIB_AVAILABLE or df.empty or plt is None:
        return False
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    sizes = (df["contact_fraction"].astype(float).clip(lower=0.05) * 420.0).tolist()
    scatter = ax.scatter(
        df["mean_min_distance_A"].astype(float),
        df["binding_energy_proxy"].astype(float),
        s=sizes,
        c=df["packet_rank"].astype(float),
        cmap="viridis_r",
        alpha=0.85,
        edgecolors="black",
        linewidths=0.5,
    )
    for _, row in df.iterrows():
        ax.annotate(
            f"#{int(row['packet_rank'])}",
            (float(row["mean_min_distance_A"]), float(row["binding_energy_proxy"])),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Mean Min Distance (A)")
    ax.set_ylabel("Binding Energy Proxy")
    ax.set_title(f"Distance vs Energy: {df['target_id'].iloc[0]}")
    ax.grid(alpha=0.25)
    fig.colorbar(scatter, ax=ax, label="Packet Rank")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return True


def _build_dashboard(
    dashboard_csv: Path,
    target_id: str,
    pdb_paths: list[str],
    movie_json: Path,
    out_html: Path,
    out_json: Path,
) -> dict[str, Any]:
    args = visualize_experiment_dashboard.build_parser().parse_args(
        [
            "--csv",
            str(dashboard_csv),
            "--labels",
            "selected_allatom_topk",
            "--metrics",
            "mean_min_distance_A,binding_energy_proxy,contact_fraction,stability_score,trajectory_frames,commercial_overall_score_v2",
            "--x-col",
            "packet_rank",
            "--target",
            str(target_id),
            "--target-col",
            "target_id",
            "--movie-json",
            str(movie_json),
            "--title",
            f"Selected All-Atom Visual Dashboard: {target_id}",
            "--out-html",
            str(out_html),
            "--out-json",
            str(out_json),
        ]
        + [item for pdb in pdb_paths[:8] for item in ("--pdb", str(pdb))]
    )
    return visualize_experiment_dashboard.build_dashboard(args)


def _expected_processed_pdb_path(processed_internal_dir: Path, backmapped_pdb: str) -> Path:
    return processed_internal_dir / f"visual_post_{Path(backmapped_pdb).name}"


def _expected_turntable_paths(chimerax_out_dir: Path, processed_pdb_path: Path) -> tuple[Path, Path]:
    stem = processed_pdb_path.stem
    return chimerax_out_dir / f"{stem}.cxc", chimerax_out_dir / f"{stem}.mp4"


def _expected_binding_event_paths(assets_dir: Path, ligand_id: str, packet_rank: int) -> tuple[Path, Path]:
    stem = f"{int(max(1, packet_rank)):02d}_{_slug(ligand_id or 'ligand')}_binding_event"
    out_dir = assets_dir / "binding_event_movies"
    return out_dir / f"{stem}.cxc", out_dir / f"{stem}.mp4"


def _binding_event_window_radius_frames(trajectory_frames: int) -> int:
    if trajectory_frames <= 0:
        return 12
    return max(8, min(24, int(round(float(trajectory_frames) / 20.0))))


def _turntable_asset_status(script_path: str, mp4_path: str) -> str:
    if _text(mp4_path) and Path(mp4_path).exists():
        return "turntable_mp4_ready"
    if _text(script_path) and Path(script_path).exists():
        return "turntable_script_ready"
    return "turntable_plan_missing"


def _turntable_asset_recommendation(asset_status: str) -> str:
    if asset_status == "turntable_mp4_ready":
        return "open_turntable_mp4"
    if asset_status == "turntable_script_ready":
        return "render_turntable_mp4"
    return "regenerate_turntable_plan"


def _binding_event_asset_status(trajectory_npz: str, expected_mp4_path: str) -> str:
    if _text(expected_mp4_path) and Path(expected_mp4_path).exists():
        return "binding_event_mp4_ready"
    if _text(trajectory_npz) and Path(trajectory_npz).exists():
        return "binding_event_contract_ready"
    return "binding_event_trajectory_missing"


def _binding_event_asset_recommendation(asset_status: str) -> str:
    if asset_status == "binding_event_mp4_ready":
        return "open_binding_event_mp4"
    if asset_status == "binding_event_contract_ready":
        return "render_binding_event_clip"
    return "restore_binding_event_trajectory"


def _load_visual_pipeline_rows(summary_json: Path) -> dict[str, dict[str, Any]]:
    payload = maybe_load_json(str(summary_json))
    rows = payload.get("rows", []) if isinstance(payload.get("rows"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_path = _text(row.get("source_path"), row.get("pdb_path"), row.get("out_path"))
        if source_path and source_path not in out:
            out[source_path] = dict(row)
    return out


def _run_visual_pipeline(
    *,
    feature_csv: Path,
    review_packet_json: str,
    internal_pdbs: list[str],
    assets_dir: Path,
    dashboard_title: str,
    viewer_engine: str,
    run_visual_pipeline: bool,
) -> dict[str, Any]:
    processed_internal_dir = assets_dir / "processed_internal"
    dashboard_html = assets_dir / "selected_allatom_visual_polish_dashboard.html"
    dashboard_json = assets_dir / "selected_allatom_visual_polish_dashboard.json"
    refined_report_csv = assets_dir / "selected_allatom_visual_polish_refined.csv"
    refined_summary_json = assets_dir / "selected_allatom_visual_polish_refined.json"
    chimerax_report_csv = assets_dir / "selected_allatom_visual_polish_chimerax.csv"
    chimerax_summary_json = assets_dir / "selected_allatom_visual_polish_chimerax.json"
    out_summary_json = assets_dir / "selected_allatom_visual_polish_summary.json"
    chimerax_out_dir = assets_dir / "visual_polish_turntable_movies"
    artifacts = {
        "processed_internal_dir": str(processed_internal_dir),
        "dashboard_html": str(dashboard_html),
        "dashboard_json": str(dashboard_json),
        "refined_report_csv": str(refined_report_csv),
        "refined_summary_json": str(refined_summary_json),
        "chimerax_report_csv": str(chimerax_report_csv),
        "chimerax_summary_json": str(chimerax_summary_json),
        "chimerax_out_dir": str(chimerax_out_dir),
        "out_summary_json": str(out_summary_json),
    }
    if not run_visual_pipeline or not internal_pdbs:
        return {"ok": False, "status": "not_run", "artifacts": artifacts}

    args = SimpleNamespace(
        feature_csv=str(feature_csv),
        gate_json=str(resolve(review_packet_json)) if _text(review_packet_json) else "",
        internal_pdb=list(internal_pdbs),
        internal_pdb_glob=[],
        external_pdb=[],
        external_pdb_glob=[],
        processed_internal_dir=str(processed_internal_dir),
        smooth_window=3,
        secondary_structure_mode="auto",
        visual_residual_lambda=0.12,
        visual_residual_iters=2,
        target_ca_distance=3.8,
        residual_bfactor_weight=0.25,
        pseudo_backbone=True,
        ss_temporal_vote=True,
        ss_vote_min_fraction=0.60,
        ss_vote_min_frames=3,
        align=True,
        dashboard_html=str(dashboard_html),
        dashboard_json=str(dashboard_json),
        dashboard_title=str(dashboard_title),
        dashboard_target_col="target_id",
        dashboard_metrics="mean_min_distance_A,binding_energy_proxy,contact_fraction,stability_score,trajectory_frames,commercial_overall_score_v2",
        dashboard_max_metrics=6,
        dashboard_max_rows=256,
        dashboard_max_pdb=max(4, len(internal_pdbs)),
        dashboard_movie_json=[],
        dashboard_movie_csv=[],
        viewer_engine=str(viewer_engine),
        run_chimerax=True,
        chimerax_out_dir=str(chimerax_out_dir),
        chimerax_bin="chimerax",
        chimerax_fps=30,
        chimerax_turn_steps=360,
        chimerax_execute=False,
        chimerax_fail_on_missing=False,
        refined_report_csv=str(refined_report_csv),
        refined_summary_json=str(refined_summary_json),
        chimerax_report_csv=str(chimerax_report_csv),
        chimerax_summary_json=str(chimerax_summary_json),
        out_summary_json=str(out_summary_json),
    )
    result = visual_polish_mod.run(args)
    artifacts.update(dict(result.get("artifacts", {}) or {}))
    status = "ready" if bool(result.get("ok", False)) else "error"
    return {
        **dict(result or {}),
        "status": status,
        "artifacts": artifacts,
    }


def build_payload(
    *,
    retry_handoff_payload: dict[str, Any],
    review_packet_payload: dict[str, Any],
    lane_payload: dict[str, Any] | None = None,
    runner_payload: dict[str, Any] | None = None,
    review_packet_json: str = "",
    lane_json: str = "",
    runner_json: str = "",
    top_k: int = DEFAULT_TOP_K,
    assets_root: str = DEFAULT_ASSETS_ROOT,
    run_visual_pipeline: bool = False,
    viewer_engine: str = "3dmol",
) -> dict[str, Any]:
    review_summary = _summary(review_packet_payload)
    review_structured = _structured(review_packet_payload)
    lane_summary = _summary(lane_payload)
    runner_summary = _summary(runner_payload)
    retry_summary = _summary(retry_handoff_payload)
    current_results_index_summary = _summary(maybe_load_json(DEFAULT_CURRENT_RESULTS_INDEX_JSON))
    monitor_semantics_summary = _summary(maybe_load_json(DEFAULT_MONITOR_SEMANTICS_JSON))
    master_handoff_dashboard_summary = _summary(maybe_load_json(DEFAULT_MASTER_HANDOFF_DASHBOARD_JSON))
    final_campaign_summary = _summary(maybe_load_json(DEFAULT_FINAL_CAMPAIGN_SUMMARY_JSON))
    partnering_stack_summary = _summary(maybe_load_json(DEFAULT_PARTNERING_STACK_JSON))

    target_id = _text(
        review_summary.get("target_id"),
        retry_summary.get("selected_allatom_target_id"),
    )
    surface_label = _text(
        review_summary.get("surface_label"),
        retry_summary.get("selected_allatom_surface_label"),
        TARGET_TO_SURFACE.get(target_id, ""),
    )
    target_slug = _slug(target_id)
    assets_dir = resolve(str(assets_root)) / target_slug
    assets_dir.mkdir(parents=True, exist_ok=True)

    review_rows = _resolve_primary_rows(review_packet_payload, max(0, int(top_k)))
    scores_csv = _resolve_scores_csv(review_summary, review_structured, lane_summary, runner_summary)
    stage2_manifest_csv = _resolve_stage2_manifest_csv(review_summary, review_structured, lane_summary, runner_summary)
    score_rows = _rows_by_ligand(_read_csv_rows(scores_csv)) if _text(scores_csv) else {}
    manifest_rows = _rows_by_ligand(_read_csv_rows(stage2_manifest_csv)) if _text(stage2_manifest_csv) else {}
    selected_allatom_canonical = resolve_selected_allatom_canonical(
        review_packet_summary=review_summary,
        retry_handoff_summary=retry_summary,
        current_results_index_summary=current_results_index_summary,
        monitor_semantics_summary=monitor_semantics_summary,
        master_handoff_dashboard_summary=master_handoff_dashboard_summary,
        final_campaign_summary=final_campaign_summary,
        partnering_stack_summary=partnering_stack_summary,
        next_required_step=_text(
            review_summary.get("next_required_step"),
            retry_summary.get("selected_allatom_next_required_step"),
        ),
    )
    selected_allatom_canonical_recipe_rollup = _action_recipe_rollup(
        list(selected_allatom_canonical.get("action_recipe_rows", []) or [])
    )
    protein_reference_contract = _resolve_protein_reference_contract(
        target_id=target_id,
        lane_summary=lane_summary,
        runner_summary=runner_summary,
    )

    enriched_rows: list[dict[str, Any]] = []
    for review_row in review_rows:
        ligand_id = _text(review_row.get("ligand_id"))
        score_row = dict(score_rows.get(ligand_id, {}) or {})
        manifest_row = dict(manifest_rows.get(ligand_id, {}) or {})
        score_payload = _read_score_json_payload(
            _text(review_row.get("score_json"), score_row.get("score_json"))
        )
        score_provenance = dict(score_payload.get("protein_structure_provenance", {}) or {})
        score_backmap_stats = dict(score_payload.get("backmap_stats", {}) or {})
        protein_source_path = _text(
            review_row.get("protein_structure_source_path"),
            score_row.get("protein_structure_source_path"),
            score_provenance.get("source_path"),
        )
        protein_source_format = _text(
            review_row.get("protein_structure_source_format"),
            score_row.get("protein_structure_source_format"),
            score_provenance.get("source_format"),
            Path(protein_source_path).suffix.lstrip(".").lower() if protein_source_path else "",
        )
        protein_source_ready = _safe_bool(
            review_row.get("protein_structure_source_available")
            or score_row.get("protein_structure_source_available")
            or score_provenance.get("source_available")
        ) and bool(protein_source_path)
        backmapped_contains_protein = bool(
            _safe_bool(
                review_row.get("backmapped_contains_protein")
                or score_row.get("backmapped_contains_protein")
                or score_payload.get("backmapped_contains_protein")
            )
            or (_safe_int(score_backmap_stats.get("protein_atoms"), 0) > 0)
        )
        backmapped_structure_kind = _text(
            review_row.get("backmapped_structure_kind"),
            score_row.get("backmapped_structure_kind"),
            score_payload.get("backmapped_structure_kind"),
            "pseudo_backmapped_protein_ligand_pdb" if backmapped_contains_protein else "ligand_only_backmapped_pdb",
        )
        packet_rank = _safe_int(review_row.get("packet_rank"), len(enriched_rows) + 1)
        action_codes_text = _csv_list_text(
            review_row.get("recommended_next_expensive_lane_action_codes")
        )
        blocker_codes_text = _csv_list_text(
            review_row.get("recommended_next_expensive_lane_blocker_codes")
        )
        enriched_rows.append(
            {
                "packet_rank": packet_rank,
                "target_id": target_id,
                "surface_label": surface_label,
                "ligand_id": ligand_id,
                "compound_name": _text(
                    review_row.get("compound_name_human_readable"),
                    review_row.get("compound_name"),
                    score_row.get("compound_name_human_readable"),
                    score_row.get("compound_name"),
                    manifest_row.get("ligand_id"),
                ),
                "mean_min_distance_A": _safe_float(
                    review_row.get("mean_min_distance_A"),
                    _safe_float(score_row.get("mean_min_distance_A")),
                ),
                "binding_energy_proxy": _safe_float(
                    review_row.get("binding_energy_proxy"),
                    _safe_float(score_row.get("binding_energy_proxy")),
                ),
                "contact_fraction": _safe_float(
                    review_row.get("contact_fraction"),
                    _safe_float(score_row.get("contact_fraction")),
                ),
                "stability_score": _safe_float(
                    review_row.get("stability_score"),
                    _safe_float(score_row.get("stability_score")),
                ),
                "trajectory_frames": _safe_int(
                    review_row.get("trajectory_frames")
                    or score_row.get("trajectory_frames")
                    or manifest_row.get("frames_written")
                ),
                "selection_score_value": _safe_float(
                    review_row.get("selection_score_value"),
                    _safe_float(score_row.get("selection_score_value")),
                ),
                "trajectory_npz": _text(
                    review_row.get("trajectory_npz"),
                    score_row.get("trajectory_npz"),
                    manifest_row.get("trajectory_npz"),
                ),
                "trajectory_dir": _text(
                    review_row.get("trajectory_dir"),
                    score_row.get("trajectory_dir"),
                    manifest_row.get("trajectory_dir"),
                ),
                "backmapped_pdb": _text(review_row.get("backmapped_pdb"), score_row.get("backmapped_pdb")),
                "score_json": _text(review_row.get("score_json"), score_row.get("score_json")),
                "commercial_overall_score_v2": _safe_float(review_row.get("commercial_overall_score_v2")),
                "commercial_confidence_score_v2": _safe_float(review_row.get("commercial_confidence_score_v2")),
                "commercial_soft_score_v2": _safe_float(review_row.get("commercial_soft_score_v2")),
                "commercial_risk_bucket_v2": _text(review_row.get("commercial_risk_bucket_v2")),
                "commercial_decision_class_v2": _text(review_row.get("commercial_decision_class_v2")),
                "translation_gate_status": _text(review_row.get("translation_gate_status")),
                "translation_gate_reason": _text(review_row.get("translation_gate_reason")),
                "recommended_next_expensive_lane": _text(review_row.get("recommended_next_expensive_lane")),
                "recommended_next_expensive_lane_reason": _text(
                    review_row.get("recommended_next_expensive_lane_reason")
                ),
                "recommended_next_expensive_lane_action": _text(
                    review_row.get("recommended_next_expensive_lane_action")
                ),
                "recommended_next_expensive_lane_action_codes_text": action_codes_text,
                "recommended_next_expensive_lane_blocker_codes_text": blocker_codes_text,
                "shortlist_tier": _text(review_row.get("shortlist_tier")),
                "protein_structure_source_path": protein_source_path,
                "protein_structure_source_kind": _text(
                    review_row.get("protein_structure_source_kind"),
                    score_row.get("protein_structure_source_kind"),
                    score_provenance.get("source_kind"),
                ),
                "protein_structure_source_format": protein_source_format,
                "protein_structure_source_available": protein_source_ready,
                "protein_structure_source_explicit_native_path": _text(
                    review_row.get("protein_structure_source_explicit_native_path"),
                    score_row.get("protein_structure_source_explicit_native_path"),
                    score_provenance.get("source_explicit_native_path"),
                ),
                "protein_structure_source_residue_anchor_mode": _text(
                    review_row.get("protein_structure_source_residue_anchor_mode"),
                    score_row.get("protein_structure_source_residue_anchor_mode"),
                    score_provenance.get("source_residue_anchor_mode"),
                ),
                "protein_structure_source_note": _text(
                    review_row.get("protein_structure_source_note"),
                    score_row.get("protein_structure_source_note"),
                    score_provenance.get("notes"),
                ),
                "backmapped_contains_protein": backmapped_contains_protein,
                "backmapped_structure_kind": backmapped_structure_kind,
                "backmapped_protein_atoms": _safe_int(
                    review_row.get("backmapped_protein_atoms"),
                    _safe_int(score_row.get("backmapped_protein_atoms"), _safe_int(score_backmap_stats.get("protein_atoms"), 0)),
                ),
                "backmapped_protein_residues": _safe_int(
                    review_row.get("backmapped_protein_residues"),
                    _safe_int(score_row.get("backmapped_protein_residues"), _safe_int(score_backmap_stats.get("protein_residues"), 0)),
                ),
                "backmapped_ligand_atoms": _safe_int(
                    review_row.get("backmapped_ligand_atoms"),
                    _safe_int(score_row.get("backmapped_ligand_atoms"), _safe_int(score_backmap_stats.get("ligand_atoms"), 0)),
                ),
                **dict(protein_reference_contract),
            }
        )

    viewer_reference_dir = assets_dir / "viewer_reference_structures"
    aligned_reference_dir = assets_dir / "aligned_native_reference_structures"
    for row in enriched_rows:
        ligand_id = _text(row.get("ligand_id"), f"ligand_{_safe_int(row.get('packet_rank'), 0)}")
        backmapped_pdb = _text(row.get("backmapped_pdb"))
        trajectory_npz = _text(row.get("trajectory_npz"))
        reference_path = viewer_reference_dir / f"{_slug(ligand_id)}_viewer_reference.pdb"
        pose_path = viewer_reference_dir / f"{_slug(ligand_id)}_viewer_pose.pdb"
        viewer_structure = _build_viewer_structure_artifact(
            trajectory_npz=trajectory_npz,
            backmapped_pdb=backmapped_pdb,
            out_path=reference_path,
            out_pose_path=pose_path,
        )
        row.update(viewer_structure)
        row["viewer_reference_pdb"] = _text(row.get("viewer_reference_pdb"))
        row["viewer_reference_pdb_ready"] = _safe_bool(row.get("viewer_reference_pdb_ready"))
        row["viewer_pose_pdb"] = _text(row.get("viewer_pose_pdb"))
        row["viewer_pose_pdb_ready"] = _safe_bool(row.get("viewer_pose_pdb_ready"))
        scorer_reference_path = _text(row.get("protein_structure_source_path"))
        scorer_reference_ready = bool(
            _safe_bool(row.get("protein_structure_source_available"))
            and scorer_reference_path
            and resolve(scorer_reference_path).exists()
        )
        if scorer_reference_ready:
            row["protein_reference_structure_path"] = scorer_reference_path
            row["protein_reference_structure_ready"] = True
            row["protein_reference_structure_format"] = _text(
                row.get("protein_structure_source_format"),
                row.get("protein_reference_structure_format"),
            )
            row["protein_reference_provenance"] = _text(
                row.get("protein_structure_source_kind"),
                row.get("protein_reference_provenance"),
            )
            row["protein_reference_structure_note"] = _joined(
                row.get("protein_structure_source_note"),
                "Protein reference path came from scorer provenance.",
                sep=" ",
                default="",
            )
        else:
            row["protein_reference_structure_path"] = _text(row.get("protein_reference_structure_path"))
            row["protein_reference_structure_ready"] = _safe_bool(
                row.get("protein_reference_structure_ready")
            )
        protein_reference_pocket_x = _safe_float_optional(row.get("protein_reference_pocket_x"))
        protein_reference_pocket_y = _safe_float_optional(row.get("protein_reference_pocket_y"))
        protein_reference_pocket_z = _safe_float_optional(row.get("protein_reference_pocket_z"))
        pocket_center = None
        if (
            protein_reference_pocket_x is not None
            and protein_reference_pocket_y is not None
            and protein_reference_pocket_z is not None
        ):
            pocket_center = (
                protein_reference_pocket_x,
                protein_reference_pocket_y,
                protein_reference_pocket_z,
            )
        aligned_reference_payload: dict[str, Any] = {}
        alignment_pose_path = _text(
            row.get("viewer_pose_pdb"),
            row.get("viewer_reference_pdb"),
            row.get("backmapped_pdb"),
        )
        aligned_reference_path = aligned_reference_dir / f"{_slug(ligand_id)}_native_aligned_reference.pdb"
        if (
            _safe_bool(row.get("protein_reference_structure_ready"))
            and alignment_pose_path
            and resolve(alignment_pose_path).exists()
        ):
            aligned_reference_payload = build_aligned_reference(
                native_structure_path=_text(row.get("protein_reference_structure_path")),
                ligand_pose_pdb=alignment_pose_path,
                viewer_reference_pdb=_text(row.get("viewer_reference_pdb")),
                out_pdb=str(aligned_reference_path),
                pocket_center=pocket_center,
            )
        row["viewer_structure_context_mode"] = _text(
            row.get("viewer_structure_context_mode"),
            "ligand_only_backmapped",
        )
        aligned_viewer_path = _text(
            aligned_reference_payload.get("aligned_reference_pdb"),
            row.get("viewer_reference_pdb"),
            row.get("backmapped_pdb") if _safe_bool(row.get("backmapped_contains_protein")) else "",
        )
        aligned_viewer_ready = bool(aligned_viewer_path and resolve(aligned_viewer_path).exists())
        row["protein_reference_alignment_mode"] = _text(
            aligned_reference_payload.get("alignment_mode"),
            "viewer_reference_pdb_direct" if _safe_bool(row.get("viewer_reference_pdb_ready")) else "",
            "backmapped_protein_context" if _safe_bool(row.get("backmapped_contains_protein")) else "",
        )
        row["protein_reference_alignment_note"] = _text(
            aligned_reference_payload.get("alignment_note")
        )
        row["protein_reference_aligned_viewer_path"] = aligned_viewer_path if aligned_viewer_ready else ""
        row["protein_reference_aligned_viewer_ready"] = aligned_viewer_ready
        row["protein_reference_structure_aligned_for_viewer"] = aligned_viewer_ready
        if aligned_viewer_ready and _text(aligned_reference_payload.get("aligned_reference_pdb")):
            row["protein_reference_viewer_mode"] = "aligned_replace"
            row["render_structure_path"] = _text(aligned_reference_payload.get("aligned_reference_pdb"))
            row["render_structure_kind"] = "protein_reference_aligned_viewer_pdb"
            row["render_structure_contains_protein"] = True
            row["render_structure_note"] = _text(
                aligned_reference_payload.get("alignment_note"),
                "Native protein reference was aligned into the chosen ligand pose frame for viewer rendering.",
            )
        elif _safe_bool(row.get("viewer_reference_pdb_ready")):
            row["protein_reference_viewer_mode"] = "aligned_replace"
            row["render_structure_path"] = _text(row.get("viewer_reference_pdb"))
            row["render_structure_kind"] = "viewer_reference_pdb"
            row["render_structure_contains_protein"] = True
            row["render_structure_note"] = (
                "Trajectory-aligned protein-plus-ligand reference PDB is available for viewer rendering."
            )
        elif _safe_bool(row.get("backmapped_contains_protein")):
            row["protein_reference_viewer_mode"] = "aligned_replace"
            row["render_structure_path"] = _text(row.get("backmapped_pdb"))
            row["render_structure_kind"] = _text(
                row.get("backmapped_structure_kind"),
                "pseudo_backmapped_protein_ligand_pdb",
            )
            row["render_structure_contains_protein"] = True
            row["render_structure_note"] = _text(
                row.get("protein_structure_source_note"),
                "Protein-containing backmapped complex is available for viewer rendering.",
            )
        else:
            row["protein_reference_viewer_mode"] = (
                "unaligned_overlay"
                if _safe_bool(row.get("protein_reference_structure_ready"))
                else "none"
            )
            row["render_structure_path"] = _text(row.get("backmapped_pdb"))
            row["render_structure_kind"] = _text(
                row.get("backmapped_structure_kind"),
                "ligand_only_backmapped_pdb",
            )
            row["render_structure_contains_protein"] = False
            row["render_structure_note"] = _text(
                row.get("viewer_protein_context_note"),
                row.get("protein_reference_alignment_note"),
                row.get("protein_reference_structure_note"),
                "Viewer rendering falls back to ligand-only backmapped PDB.",
            )
        row["wetlab_focus_operator_review_ready"] = bool(
            _safe_bool(review_summary.get("packet_ready_for_operator_review"))
        )
        row["wetlab_focus_wetlab_gate_pass"] = bool(_safe_bool(review_summary.get("wetlab_gate_pass")))
        row["wetlab_focus_wetlab_final_gate_pass"] = bool(
            _safe_bool(review_summary.get("wetlab_final_gate_pass"))
        )
        row["wetlab_focus_raw_claim_requirement_mode"] = _text(
            selected_allatom_canonical.get("raw_claim_requirement_mode")
        )
        row["wetlab_focus_effective_actionability_status"] = _text(
            selected_allatom_canonical.get("effective_actionability_status")
        )
        row["wetlab_focus_effective_blocking_order"] = _text(
            selected_allatom_canonical.get("effective_blocking_order")
        )
        row["wetlab_focus_commercial_human_summary_v2"] = _text(
            selected_allatom_canonical.get("commercial_human_summary_v2")
        )
        row["wetlab_focus_action_recipe_rollup_text"] = selected_allatom_canonical_recipe_rollup

    visual_df = pd.DataFrame(enriched_rows)
    dashboard_csv = assets_dir / "selected_allatom_visual_dashboard.csv"
    if not visual_df.empty:
        visual_df.to_csv(dashboard_csv, index=False)
    else:
        dashboard_csv.write_text("", encoding="utf-8")

    metric_panel_png = assets_dir / "selected_allatom_topk_metric_panel.png"
    scatter_png = assets_dir / "selected_allatom_topk_distance_energy.png"
    metric_panel_ready = _render_metric_panel(visual_df, metric_panel_png)
    scatter_ready = _render_scatter(visual_df, scatter_png)

    render_pdb_paths: list[str] = []
    for row in enriched_rows:
        preferred = _text(
            row.get("render_structure_path"),
            row.get("viewer_reference_pdb"),
            row.get("backmapped_pdb"),
        )
        if preferred and Path(preferred).exists():
            render_pdb_paths.append(preferred)
    pdb_paths = render_pdb_paths
    movie_json = assets_dir / "selected_allatom_turntable_movies.json"
    movie_csv = assets_dir / "selected_allatom_turntable_movies.csv"
    movie_summary = render_chimerax_movies.run(
        render_chimerax_movies.build_parser().parse_args(
            [item for pdb in pdb_paths for item in ("--pdb", pdb)]
            + [
                "--out-dir",
                str(assets_dir / "turntable_movies"),
                "--out-json",
                str(movie_json),
                "--out-csv",
                str(movie_csv),
                "--no-execute",
            ]
        )
    )

    dashboard_html = assets_dir / "selected_allatom_visual_dashboard.html"
    dashboard_json = assets_dir / "selected_allatom_visual_dashboard.json"
    dashboard_payload = _build_dashboard(
        dashboard_csv=dashboard_csv,
        target_id=target_id,
        pdb_paths=pdb_paths,
        movie_json=movie_json,
        out_html=dashboard_html,
        out_json=dashboard_json,
    )

    visual_pipeline = _run_visual_pipeline(
        feature_csv=dashboard_csv,
        review_packet_json=review_packet_json,
        internal_pdbs=pdb_paths,
        assets_dir=assets_dir,
        dashboard_title=f"{target_id} Selected All-Atom Visual Bundle",
        viewer_engine=viewer_engine,
        run_visual_pipeline=run_visual_pipeline,
    )
    refined_rows_by_source = _load_visual_pipeline_rows(
        Path(_text(visual_pipeline.get("artifacts", {}).get("refined_summary_json")))
    )
    polished_movie_rows_by_pdb = _load_visual_pipeline_rows(
        Path(_text(visual_pipeline.get("artifacts", {}).get("chimerax_summary_json")))
    )

    movie_rows = list(movie_summary.get("rows", []) or [])
    movie_by_pdb = {
        _text(row.get("pdb_path")): dict(row)
        for row in movie_rows
        if _text(row.get("pdb_path"))
    }
    candidate_rows: list[dict[str, Any]] = []
    for row in enriched_rows:
        backmapped_pdb = _text(row.get("backmapped_pdb"))
        render_pdb = _text(row.get("render_structure_path"), row.get("viewer_reference_pdb"), backmapped_pdb)
        movie_row = movie_by_pdb.get(render_pdb, {})
        if (not movie_row) and backmapped_pdb != render_pdb:
            movie_row = movie_by_pdb.get(backmapped_pdb, {})
        turntable_script_path = _text(movie_row.get("script_path"))
        turntable_mp4_path = _text(movie_row.get("mp4_path"))
        turntable_asset_status = _turntable_asset_status(turntable_script_path, turntable_mp4_path)
        turntable_script_ready = turntable_asset_status in {
            "turntable_script_ready",
            "turntable_mp4_ready",
        }
        turntable_mp4_ready = turntable_asset_status == "turntable_mp4_ready"
        refined_row = refined_rows_by_source.get(backmapped_pdb, {})
        processed_pdb = _text(
            refined_row.get("out_path"),
            str(_expected_processed_pdb_path(
                Path(_text(visual_pipeline.get("artifacts", {}).get("processed_internal_dir")) or assets_dir / "processed_internal"),
                backmapped_pdb or f"{_text(row.get('ligand_id'))}.pdb",
            ))
            if backmapped_pdb
            else "",
        )
        polished_movie_row = polished_movie_rows_by_pdb.get(processed_pdb, {})
        expected_polished_script, expected_polished_mp4 = _expected_turntable_paths(
            Path(_text(visual_pipeline.get("artifacts", {}).get("chimerax_out_dir")) or assets_dir / "visual_polish_turntable_movies"),
            Path(processed_pdb or "visual_focus.pdb"),
        )
        polished_script_path = _text(
            polished_movie_row.get("script_path"),
            str(expected_polished_script) if processed_pdb else "",
        )
        polished_mp4_path = _text(
            polished_movie_row.get("mp4_path"),
            str(expected_polished_mp4) if processed_pdb else "",
        )
        polished_asset_status = _turntable_asset_status(polished_script_path, polished_mp4_path)
        polished_script_ready = polished_asset_status in {
            "turntable_script_ready",
            "turntable_mp4_ready",
        }
        polished_mp4_ready = polished_asset_status == "turntable_mp4_ready"
        trajectory_npz = _text(row.get("trajectory_npz"))
        binding_event_status = (
            "trajectory_available"
            if trajectory_npz and Path(trajectory_npz).exists()
            else "trajectory_missing"
        )
        candidate_rows.append(
            {
                "row_kind": "selected_allatom_visual_candidate",
                **row,
                "render_pdb": render_pdb,
                "turntable_movie_script_path": turntable_script_path if turntable_script_ready else "",
                "turntable_movie_mp4_path": turntable_mp4_path if turntable_mp4_ready else "",
                "turntable_script_ready": turntable_script_ready,
                "turntable_mp4_ready": turntable_mp4_ready,
                "turntable_asset_status": turntable_asset_status,
                "turntable_asset_recommendation": _turntable_asset_recommendation(turntable_asset_status),
                "turntable_movie_ready": turntable_mp4_ready,
                "binding_event_movie_candidate_status": binding_event_status,
                "binding_event_clip_status": "trajectory_npz_available" if binding_event_status == "trajectory_available" else "trajectory_npz_missing",
                "binding_event_clip_ready": binding_event_status == "trajectory_available",
                "binding_event_clip_recipe_kind": (
                    "trajectory_npz_plus_backmapped_pdb"
                    if binding_event_status == "trajectory_available" and backmapped_pdb
                    else "unavailable"
                ),
                "binding_event_clip_input_trajectory_npz": trajectory_npz,
                "binding_event_clip_input_structure_path": render_pdb,
                "binding_event_clip_input_structure_kind": _text(
                    row.get("render_structure_kind")
                ),
                "binding_event_clip_input_backmapped_pdb": backmapped_pdb,
                "binding_event_clip_recipe_summary": (
                    f"Extract the minimum-distance binding window from {trajectory_npz} and render it against {render_pdb or backmapped_pdb}."
                    if binding_event_status == "trajectory_available" and (render_pdb or backmapped_pdb)
                    else "No trajectory-backed binding-event clip recipe is available yet."
                ),
                "visual_polish_processed_pdb": processed_pdb,
                "visual_polish_processed_pdb_ready": bool(processed_pdb and Path(processed_pdb).exists()),
                "visual_polish_turntable_movie_script_path": polished_script_path if polished_script_ready else "",
                "visual_polish_turntable_movie_mp4_path": polished_mp4_path if polished_mp4_ready else "",
                "visual_polish_turntable_script_ready": polished_script_ready,
                "visual_polish_turntable_mp4_ready": polished_mp4_ready,
                "visual_polish_turntable_asset_status": polished_asset_status,
                "visual_polish_turntable_asset_recommendation": _turntable_asset_recommendation(polished_asset_status),
                "visual_polish_turntable_movie_ready": polished_mp4_ready,
            }
        )

    primary_row = candidate_rows[0] if candidate_rows else {}
    figure_count = int(bool(metric_panel_ready)) + int(bool(scatter_ready))
    movie_plan_count = int(movie_summary.get("render_rows", 0) or 0)
    turntable_script_ready_count = sum(1 for row in candidate_rows if bool(row.get("turntable_script_ready")))
    turntable_mp4_ready_count = sum(1 for row in candidate_rows if bool(row.get("turntable_mp4_ready")))
    binding_event_candidate_count = sum(
        1 for row in candidate_rows if row.get("binding_event_movie_candidate_status") == "trajectory_available"
    )
    visual_polish_movie_plan_count = sum(
        1 for row in candidate_rows if _text(row.get("visual_polish_turntable_movie_script_path"))
    )
    human_summary = _joined(
        f"Selected all-atom visual bundle for {target_id}" if target_id else "",
        f"top-k {len(candidate_rows)}" if candidate_rows else "",
        f"figures {figure_count}",
        f"turntable movie plans {movie_plan_count}",
        f"binding-event candidates {binding_event_candidate_count}",
        f"visual polish { _text(visual_pipeline.get('status')) }" if _text(visual_pipeline.get("status")) else "",
    )

    status = "selected_allatom_visual_bundle_ready" if candidate_rows else "selected_allatom_visual_bundle_empty"
    return {
        "summary": {
            "status": status,
            "visual_bundle_manifest_version": VISUAL_BUNDLE_MANIFEST_VERSION,
            "target_id": target_id,
            "target_slug": target_slug,
            "selected_surface_label": surface_label,
            "topk_requested": max(0, int(top_k)),
            "topk_count": len(candidate_rows),
            "figure_count": figure_count,
            "movie_plan_count": movie_plan_count,
            "binding_event_candidate_count": binding_event_candidate_count,
            "visual_polish_movie_plan_count": visual_polish_movie_plan_count,
            "assets_dir": str(assets_dir),
            "dashboard_html": str(dashboard_html),
            "dashboard_json": str(dashboard_json),
            "metric_panel_png": str(metric_panel_png) if metric_panel_ready else "",
            "scatter_png": str(scatter_png) if scatter_ready else "",
            "primary_figure_path": str(metric_panel_png) if metric_panel_ready else str(scatter_png) if scatter_ready else "",
            "primary_movie_script_path": _text(primary_row.get("turntable_movie_script_path")),
            "primary_movie_mp4_path": _text(primary_row.get("turntable_movie_mp4_path")),
            "primary_turntable_asset_status": _text(primary_row.get("turntable_asset_status")),
            "primary_turntable_asset_recommendation": _text(primary_row.get("turntable_asset_recommendation")),
            "turntable_script_ready_count": turntable_script_ready_count,
            "turntable_mp4_ready_count": turntable_mp4_ready_count,
            "primary_backmapped_pdb": _text(primary_row.get("backmapped_pdb")),
            "primary_render_structure_path": _text(primary_row.get("render_structure_path")),
            "primary_render_structure_kind": _text(primary_row.get("render_structure_kind")),
            "primary_render_structure_contains_protein": bool(
                _safe_bool(primary_row.get("render_structure_contains_protein"))
            ),
            "primary_viewer_reference_pdb": _text(primary_row.get("viewer_reference_pdb")),
            "primary_viewer_reference_pdb_ready": bool(primary_row.get("viewer_reference_pdb_ready")),
            "primary_viewer_pose_pdb": _text(primary_row.get("viewer_pose_pdb")),
            "primary_viewer_pose_pdb_ready": bool(primary_row.get("viewer_pose_pdb_ready")),
            "primary_viewer_structure_context_mode": _text(primary_row.get("viewer_structure_context_mode")),
            "primary_viewer_protein_context_valid": bool(
                _safe_bool(primary_row.get("viewer_protein_context_valid"))
            ),
            "primary_viewer_protein_context_quality_gate_pass": bool(
                _safe_bool(primary_row.get("viewer_protein_context_quality_gate_pass"))
            ),
            "primary_viewer_protein_context_reason": _text(
                primary_row.get("viewer_protein_context_reason")
            ),
            "primary_viewer_reference_frame_index": _safe_int(primary_row.get("viewer_reference_frame_index"), 0),
            "primary_viewer_reference_trajectory_index": _safe_int(primary_row.get("viewer_reference_trajectory_index"), 0),
            "primary_viewer_reference_min_distance_A": _safe_float(primary_row.get("viewer_reference_min_distance_A")),
            "primary_viewer_trajectory_min_distance_A": _safe_float(primary_row.get("viewer_trajectory_min_distance_A")),
            "primary_viewer_trajectory_max_distance_A": _safe_float(primary_row.get("viewer_trajectory_max_distance_A")),
            "primary_viewer_protein_ca_count": _safe_int(primary_row.get("viewer_protein_ca_count"), 0),
            "primary_viewer_protein_ca_spread_A": _safe_float(primary_row.get("viewer_protein_ca_spread_A")),
            "primary_viewer_ligand_atom_count": _safe_int(primary_row.get("viewer_ligand_atom_count"), 0),
            "viewer_structure_context_note": _text(primary_row.get("viewer_protein_context_note")),
            "primary_backmapped_protein_atoms": _safe_int(primary_row.get("backmapped_protein_atoms"), 0),
            "primary_protein_reference_structure_path": _text(
                primary_row.get("protein_reference_structure_path")
            ),
            "primary_protein_reference_structure_ready": bool(
                _safe_bool(primary_row.get("protein_reference_structure_ready"))
            ),
            "primary_protein_reference_structure_format": _text(
                primary_row.get("protein_reference_structure_format")
            ),
            "primary_protein_reference_structure_aligned_for_viewer": bool(
                _safe_bool(primary_row.get("protein_reference_structure_aligned_for_viewer"))
            ),
            "primary_protein_reference_aligned_viewer_path": _text(
                primary_row.get("protein_reference_aligned_viewer_path")
            ),
            "primary_protein_reference_aligned_viewer_ready": bool(
                _safe_bool(primary_row.get("protein_reference_aligned_viewer_ready"))
            ),
            "primary_protein_reference_viewer_mode": _text(
                primary_row.get("protein_reference_viewer_mode")
            ),
            "primary_protein_reference_alignment_mode": _text(
                primary_row.get("protein_reference_alignment_mode")
            ),
            "primary_protein_reference_structure_note": _text(
                primary_row.get("protein_reference_structure_note")
            ),
            "primary_protein_reference_alignment_note": _text(
                primary_row.get("protein_reference_alignment_note")
            ),
            "primary_trajectory_npz": _text(primary_row.get("trajectory_npz")),
            "primary_binding_event_clip_status": _text(primary_row.get("binding_event_clip_status")),
            "primary_binding_event_clip_recipe": _text(primary_row.get("binding_event_clip_recipe_summary")),
            "primary_visual_polish_processed_pdb": _text(primary_row.get("visual_polish_processed_pdb")),
            "primary_visual_polish_movie_script_path": _text(primary_row.get("visual_polish_turntable_movie_script_path")),
            "primary_visual_polish_movie_mp4_path": _text(primary_row.get("visual_polish_turntable_movie_mp4_path")),
            "hero_ligand_id": _text(primary_row.get("ligand_id")),
            "hero_compound_name": _text(primary_row.get("compound_name")),
            "hero_translation_gate_status": _text(primary_row.get("translation_gate_status")),
            "hero_recommended_next_expensive_lane": _text(primary_row.get("recommended_next_expensive_lane")),
            "selected_review_packet_json": str(resolve(review_packet_json)) if _text(review_packet_json) else "",
            "selected_lane_json": str(resolve(lane_json)) if _text(lane_json) else "",
            "selected_runner_json": str(resolve(runner_json)) if _text(runner_json) else "",
            "visual_pipeline_requested": bool(run_visual_pipeline),
            "visual_pipeline_status": _text(visual_pipeline.get("status")),
            "visual_pipeline_ok": bool(visual_pipeline.get("ok", False)),
            "visual_pipeline_dashboard_html": _text(visual_pipeline.get("artifacts", {}).get("dashboard_html")),
            "visual_pipeline_dashboard_json": _text(visual_pipeline.get("artifacts", {}).get("dashboard_json")),
            "visual_pipeline_summary_json": _text(visual_pipeline.get("artifacts", {}).get("out_summary_json")),
            "wetlab_focus_operator_review_ready": bool(
                _safe_bool(review_summary.get("packet_ready_for_operator_review"))
            ),
            "wetlab_focus_wetlab_gate_pass": bool(_safe_bool(review_summary.get("wetlab_gate_pass"))),
            "wetlab_focus_wetlab_final_gate_pass": bool(
                _safe_bool(review_summary.get("wetlab_final_gate_pass"))
            ),
            "wetlab_focus_raw_claim_requirement_mode": _text(
                selected_allatom_canonical.get("raw_claim_requirement_mode")
            ),
            "wetlab_focus_raw_claim_requirement_reason": _text(
                selected_allatom_canonical.get("raw_claim_requirement_reason")
            ),
            "wetlab_focus_raw_claim_requirement_provenance": _text(
                selected_allatom_canonical.get("raw_claim_requirement_provenance")
            ),
            "wetlab_focus_effective_actionability_status": _text(
                selected_allatom_canonical.get("effective_actionability_status")
            ),
            "wetlab_focus_effective_actionability_claim_requirement_mode": _text(
                selected_allatom_canonical.get("effective_actionability_claim_requirement_mode")
            ),
            "wetlab_focus_effective_blocking_order": _text(
                selected_allatom_canonical.get("effective_blocking_order")
            ),
            "wetlab_focus_effective_primary_blocking_domain": _text(
                selected_allatom_canonical.get("effective_primary_blocking_domain")
            ),
            "wetlab_focus_translation_gate_version": _text(
                selected_allatom_canonical.get("translation_gate_version")
            ),
            "wetlab_focus_translation_gate_focus_status": _text(
                selected_allatom_canonical.get("translation_gate_focus_status")
            ),
            "wetlab_focus_translation_gate_focus_score": _safe_float(
                selected_allatom_canonical.get("translation_gate_focus_score")
            ),
            "wetlab_focus_translation_gate_focus_reason": _text(
                selected_allatom_canonical.get("translation_gate_focus_reason")
            ),
            "wetlab_focus_commercial_schema_version_v2": _text(
                selected_allatom_canonical.get("commercial_schema_version_v2")
            ),
            "wetlab_focus_commercial_overall_score_v2": _safe_float(
                selected_allatom_canonical.get("commercial_overall_score_v2")
            ),
            "wetlab_focus_commercial_risk_bucket_v2": _text(
                selected_allatom_canonical.get("commercial_risk_bucket_v2")
            ),
            "wetlab_focus_commercial_decision_class_v2": _text(
                selected_allatom_canonical.get("commercial_decision_class_v2")
            ),
            "wetlab_focus_commercial_human_summary_v2": _text(
                selected_allatom_canonical.get("commercial_human_summary_v2")
            ),
            "wetlab_focus_actionability_human_summary": _text(
                selected_allatom_canonical.get("effective_actionability", {}).get("human_summary")
            ),
            "wetlab_focus_action_recipe_codes": list(
                selected_allatom_canonical.get("action_recipe_codes", []) or []
            ),
            "wetlab_focus_action_recipe_rollup_text": selected_allatom_canonical_recipe_rollup,
            "human_summary": human_summary,
            "next_required_step": (
                "Review the selected-allatom visual bundle, inspect the hero structure, and decide whether to open turntable rendering or a trajectory-backed binding-event clip."
                if candidate_rows
                else "No selected all-atom rows are available for the visual bundle."
            ),
        },
        "structured": {
            "retry_handoff_artifact": DEFAULT_RETRY_HANDOFF_JSON,
            "selected_review_packet_artifact": review_packet_json.replace(".json", ".md") if _text(review_packet_json) else "",
            "selected_lane_artifact": lane_json.replace(".json", ".md") if _text(lane_json) else "",
            "selected_runner_artifact": runner_json.replace(".json", ".md") if _text(runner_json) else "",
            "review_packet_scores_csv": scores_csv,
            "source_stage2_manifest_csv": stage2_manifest_csv,
            "dashboard_input_csv": str(dashboard_csv),
            "feature_csv": str(dashboard_csv),
            "movie_json": str(movie_json),
            "movie_csv": str(movie_csv),
            "dashboard_movie_count": int(dashboard_payload.get("movie_entries", 0) or 0),
            "visual_pipeline_processed_internal_dir": _text(
                visual_pipeline.get("artifacts", {}).get("processed_internal_dir")
            ),
            "visual_pipeline_refined_summary_json": _text(
                visual_pipeline.get("artifacts", {}).get("refined_summary_json")
            ),
            "visual_pipeline_chimerax_summary_json": _text(
                visual_pipeline.get("artifacts", {}).get("chimerax_summary_json")
            ),
            "protein_reference_contract": dict(protein_reference_contract),
            "wetlab_focus": {
                **dict(selected_allatom_canonical or {}),
                "operator_review_ready": bool(
                    _safe_bool(review_summary.get("packet_ready_for_operator_review"))
                ),
                "wetlab_gate_pass": bool(_safe_bool(review_summary.get("wetlab_gate_pass"))),
                "wetlab_final_gate_pass": bool(_safe_bool(review_summary.get("wetlab_final_gate_pass"))),
                "action_recipe_rollup_text": selected_allatom_canonical_recipe_rollup,
            },
        },
        "rows": candidate_rows,
    }


def _build_bundle_catalog_payload(
    *,
    current_payload: dict[str, Any],
    shared_out_md: str,
) -> dict[str, Any]:
    current_summary = dict(current_payload.get("summary", {}) or {})
    current_target_id = _text(current_summary.get("target_id"))
    current_surface_label = _text(current_summary.get("selected_surface_label"))
    entries: list[dict[str, Any]] = []
    for surface_label, contract in SURFACE_REGISTRY.items():
        if surface_label.startswith("sars_cov_2_"):
            continue
        target_id = _text(contract.get("target_id"))
        bundle_md = _target_bundle_out_md(target_id)
        bundle_json = bundle_md.with_suffix(".json")
        entries.append(
            {
                "surface_label": surface_label,
                "target_id": target_id,
                "bundle_md": str(bundle_md),
                "bundle_json": str(bundle_json),
                "bundle_ready": bool(bundle_json.exists()),
                "assets_dir": str(resolve(DEFAULT_ASSETS_ROOT) / _slug(target_id)),
                "is_current_shared_target": bool(
                    current_target_id == target_id and current_surface_label == surface_label
                ),
            }
        )
    return {
        "summary": {
            "status": "selected_allatom_visual_bundle_catalog_ready",
            "entry_count": len(entries),
            "current_target_id": current_target_id,
            "current_surface_label": current_surface_label,
            "shared_current_bundle_md": str(resolve(shared_out_md)),
            "shared_current_bundle_json": str(resolve(shared_out_md).with_suffix(".json")),
        },
        "rows": entries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the selected all-atom visual bundle for the current wetlab focus.")
    parser.add_argument("--retry-handoff-json", default=DEFAULT_RETRY_HANDOFF_JSON)
    parser.add_argument("--review-packet-json", default="")
    parser.add_argument("--lane-json", default="")
    parser.add_argument("--runner-json", default="")
    parser.add_argument("--surface-label", default="")
    parser.add_argument("--tcruzi-pde-allatom-review-packet-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--cathepsin-k-allatom-review-packet-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-review-packet-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--tcruzi-pde-allatom-lane-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_LANE_JSON)
    parser.add_argument("--cathepsin-k-allatom-lane-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_LANE_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-lane-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_LANE_JSON)
    parser.add_argument("--tcruzi-pde-allatom-runner-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_RUNNER_JSON)
    parser.add_argument("--cathepsin-k-allatom-runner-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_RUNNER_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-runner-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_RUNNER_JSON)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--assets-root", default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--run-visual-pipeline", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--viewer-engine", choices=["auto", "3dmol", "molstar"], default="3dmol")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-catalog-json", default=DEFAULT_OUT_CATALOG_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    retry_handoff_payload = load_json(args.retry_handoff_json)
    registry = {
        "tcruzi_pde_allatom_review_packet": {
            "target_id": "T. cruzi PDE",
            "review_packet_json": args.tcruzi_pde_allatom_review_packet_json,
            "lane_json": args.tcruzi_pde_allatom_lane_json,
            "runner_json": args.tcruzi_pde_allatom_runner_json,
        },
        "cathepsin_k_allatom_review_packet": {
            "target_id": "Cathepsin K",
            "review_packet_json": args.cathepsin_k_allatom_review_packet_json,
            "lane_json": args.cathepsin_k_allatom_lane_json,
            "runner_json": args.cathepsin_k_allatom_runner_json,
        },
        "sarscov2_mpro_allatom_review_packet": {
            "target_id": "SARS-CoV-2 Mpro",
            "review_packet_json": args.sarscov2_mpro_allatom_review_packet_json,
            "lane_json": args.sarscov2_mpro_allatom_lane_json,
            "runner_json": args.sarscov2_mpro_allatom_runner_json,
        },
        "sars_cov_2_mpro_allatom_review_packet": {
            "target_id": "SARS-CoV-2 Mpro",
            "review_packet_json": args.sarscov2_mpro_allatom_review_packet_json,
            "lane_json": args.sarscov2_mpro_allatom_lane_json,
            "runner_json": args.sarscov2_mpro_allatom_runner_json,
        },
    }
    focus_contract = _resolve_focus_contract(
        retry_handoff_payload=retry_handoff_payload,
        review_packet_json=args.review_packet_json,
        lane_json=args.lane_json,
        runner_json=args.runner_json,
        surface_label=args.surface_label,
        registry=registry,
    )
    if not _text(focus_contract.get("review_packet_json")):
        raise SystemExit("could not resolve selected all-atom review packet json")

    review_packet_payload = load_json(focus_contract["review_packet_json"])
    lane_payload = maybe_load_json(focus_contract["lane_json"])
    runner_payload = maybe_load_json(focus_contract["runner_json"])
    payload = build_payload(
        retry_handoff_payload=retry_handoff_payload,
        review_packet_payload=review_packet_payload,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=focus_contract["review_packet_json"],
        lane_json=focus_contract["lane_json"],
        runner_json=focus_contract["runner_json"],
        top_k=max(0, int(args.top_k)),
        assets_root=args.assets_root,
        run_visual_pipeline=bool(args.run_visual_pipeline),
        viewer_engine=args.viewer_engine,
    )
    write_artifact(args.out_md, "Selected All-Atom Visual Bundle", payload)
    target_bundle_out_md = _target_bundle_out_md(_text(payload.get("summary", {}).get("target_id")))
    if target_bundle_out_md.resolve() != resolve(args.out_md):
        write_artifact(str(target_bundle_out_md), "Selected All-Atom Visual Bundle", payload)
    catalog_payload = _build_bundle_catalog_payload(
        current_payload=payload,
        shared_out_md=args.out_md,
    )
    catalog_path = resolve(args.out_catalog_json)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
