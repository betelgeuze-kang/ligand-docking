"""Strict, state-aware pose RMSD compatibility contracts.

This module installs reviewed RMSD semantics onto the legacy Tier-beta modules at
package import time. The overlay is explicit and idempotent: existing schema keys
remain available for downstream readers, while new fields describe the effective
strict method. No scientific or product claim is promoted.
"""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
import math
from typing import Any

import numpy as np

from betelgeuze_engine.biodiscovery.contracts import (
    StageRecord,
    TierBetaScreeningInput,
)

STRICT_POSE_RMSD_CONTRACT_VERSION = "tier_beta_strict_pose_rmsd_v1"
_EFFECTIVE_CONFORMER_METHOD = "kabsch_aligned_symmetry_aware_heavy_atom_rmsd"
_EFFECTIVE_RECEPTOR_METHOD = "rdkit_automorphism_min_receptor_frame_rmsd"
_SCREEN_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "tier_beta_strict_pose_rmsd_context",
    default=None,
)


def _pose_coordinates(value: Any, *, label: str) -> np.ndarray:
    try:
        coords = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a rectangular [N, 3] coordinate array") from exc
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"{label} must have shape [N, 3]")
    if int(coords.shape[0]) <= 0:
        raise ValueError(f"{label} must contain at least one atom")
    if not np.isfinite(coords).all():
        raise ValueError(f"{label} contains non-finite coordinates")
    return coords


def _paired_pose_coordinates(a: Any, b: Any) -> tuple[np.ndarray, np.ndarray]:
    left = _pose_coordinates(a, label="left pose")
    right = _pose_coordinates(b, label="right pose")
    if left.shape != right.shape:
        raise ValueError(
            "pose coordinate shapes must match exactly; "
            f"observed {tuple(left.shape)} and {tuple(right.shape)}"
        )
    return left, right


def _validated_symmetry_mappings(
    symmetry_mappings: Any,
    *,
    atom_count: int,
) -> tuple[tuple[int, ...], ...]:
    identity = tuple(range(int(atom_count)))
    normalized: list[tuple[int, ...]] = [identity]
    seen = {identity}
    for mapping_index, raw_mapping in enumerate(symmetry_mappings or []):
        if not isinstance(raw_mapping, (list, tuple, np.ndarray)):
            raise ValueError(f"symmetry mapping {mapping_index} must be an index sequence")
        if len(raw_mapping) != int(atom_count):
            raise ValueError(
                f"symmetry mapping {mapping_index} must contain exactly {atom_count} indices"
            )
        mapping: list[int] = []
        for value in raw_mapping:
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                raise ValueError(f"symmetry mapping {mapping_index} contains a non-integer index")
            mapping.append(int(value))
        canonical = tuple(mapping)
        if set(canonical) != set(identity):
            raise ValueError(
                f"symmetry mapping {mapping_index} must be a complete atom-index bijection"
            )
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return tuple(normalized)


def pose_rmsd(a: Any, b: Any) -> float:
    """Strict atom-order RMSD in one receptor coordinate frame."""

    left, right = _paired_pose_coordinates(a, b)
    return float(np.sqrt(np.mean(np.sum((left - right) ** 2, axis=1))))


def _kabsch_aligned_rmsd(reference: np.ndarray, moving: np.ndarray) -> float:
    reference_centered = reference - reference.mean(axis=0, keepdims=True)
    moving_centered = moving - moving.mean(axis=0, keepdims=True)
    covariance = moving_centered.T @ reference_centered
    u, _singular_values, vt = np.linalg.svd(covariance, full_matrices=False)
    correction = np.eye(3, dtype=np.float64)
    if float(np.linalg.det(u @ vt)) < 0.0:
        correction[-1, -1] = -1.0
    aligned = moving_centered @ (u @ correction @ vt)
    return float(np.sqrt(np.mean(np.sum((reference_centered - aligned) ** 2, axis=1))))


def aligned_symmetry_aware_pose_rmsd(
    a: Any,
    b: Any,
    symmetry_mappings: Any = None,
) -> float:
    """Minimum proper-rotation Kabsch RMSD over complete atom mappings."""

    left, right = _paired_pose_coordinates(a, b)
    mappings = _validated_symmetry_mappings(
        symmetry_mappings,
        atom_count=int(left.shape[0]),
    )
    return float(
        min(
            _kabsch_aligned_rmsd(left, right[np.asarray(mapping, dtype=np.int64)])
            for mapping in mappings
        )
    )


def symmetry_aware_pose_rmsd(
    a: Any,
    b: Any,
    symmetry_mappings: Any = None,
) -> float:
    """Minimum receptor-frame RMSD over complete atom-index bijections."""

    left, right = _paired_pose_coordinates(a, b)
    mappings = _validated_symmetry_mappings(
        symmetry_mappings,
        atom_count=int(left.shape[0]),
    )
    return float(
        min(
            np.sqrt(
                np.mean(
                    np.sum(
                        (left - right[np.asarray(mapping, dtype=np.int64)]) ** 2,
                        axis=1,
                    )
                )
            )
            for mapping in mappings
        )
    )


def best_symmetry_ordered_pose(
    reference: Any,
    pose: Any,
    symmetry_mappings: Any = None,
) -> np.ndarray:
    """Return ``pose`` in the receptor-frame atom order nearest ``reference``."""

    left, right = _paired_pose_coordinates(reference, pose)
    mappings = _validated_symmetry_mappings(
        symmetry_mappings,
        atom_count=int(left.shape[0]),
    )
    best_mapping = min(
        mappings,
        key=lambda mapping: float(
            np.sqrt(
                np.mean(
                    np.sum(
                        (left - right[np.asarray(mapping, dtype=np.int64)]) ** 2,
                        axis=1,
                    )
                )
            )
        ),
    )
    return right[np.asarray(best_mapping, dtype=np.int64)].copy()


def _strict_conformer_diversity(
    pose_module: Any,
    poses: Any,
    *,
    smiles: str = "",
    diversity_threshold_a: float = 0.5,
) -> dict[str, Any]:
    conformers = np.asarray(poses, dtype=np.float64)
    if conformers.ndim != 3 or conformers.shape[-1] != 3:
        raise ValueError("conformer coordinates must have shape [C, N, 3]")
    count = int(conformers.shape[0])
    atom_count = int(conformers.shape[1])
    if count > 0 and atom_count <= 0:
        raise ValueError("conformers must contain at least one atom")
    if not np.isfinite(conformers).all():
        raise ValueError("conformer coordinates contain non-finite values")
    mappings = pose_module.ligand_symmetry_mappings(smiles) if smiles else []
    canonical_mappings = (
        _validated_symmetry_mappings(mappings, atom_count=atom_count)
        if atom_count > 0
        else tuple()
    )
    rmsd_values = [
        aligned_symmetry_aware_pose_rmsd(conformers[i], conformers[j], canonical_mappings)
        for i in range(count)
        for j in range(i + 1, count)
    ]
    finite = [float(value) for value in rmsd_values if math.isfinite(float(value))]
    if count <= 1:
        status = "single_conformer_no_pairwise_diversity"
    elif finite and max(finite) >= float(diversity_threshold_a):
        status = "rotatable_conformer_diversity_measured"
    else:
        status = "low_conformer_diversity_measured"
    return {
        "schema_version": "tier_beta_conformer_diversity_v1",
        "status": status,
        "method": "atom_order_pairwise_heavy_atom_rmsd",
        "strict_contract_version": STRICT_POSE_RMSD_CONTRACT_VERSION,
        "method_compatibility_alias": True,
        "effective_method": _EFFECTIVE_CONFORMER_METHOD,
        "alignment": "centroid_translation_removed_proper_rotation_kabsch",
        "coordinate_scope": "isolated_conformer_internal_geometry",
        "symmetry_mapping_count": int(len(canonical_mappings)),
        "atom_count": atom_count,
        "rotatable_bond_count": pose_module.rotatable_bond_count(smiles) if smiles else 0,
        "conformer_count": count,
        "pairwise_rmsd_count": int(len(finite)),
        "pairwise_rmsd_min_a": min(finite) if finite else 0.0,
        "pairwise_rmsd_mean_a": float(sum(finite) / len(finite)) if finite else 0.0,
        "pairwise_rmsd_max_a": max(finite) if finite else 0.0,
        "diversity_threshold_a": float(diversity_threshold_a),
        "diverse_pair_count": int(
            sum(1 for value in finite if value >= float(diversity_threshold_a))
        ),
        "claim_boundary": (
            "Diagnostic generated-conformer internal spread only after proper rigid alignment and complete atom mapping; "
            "not an exhaustive rotamer search or benchmarked pose-diversity guarantee."
        ),
    }


def _strict_cluster_poses(
    rows: list[dict[str, Any]],
    placed_pose_coords: dict[int, np.ndarray],
    symmetry_mappings: Any = None,
    *,
    threshold_a: float = 2.0,
) -> dict[str, Any]:
    if not rows:
        return {
            "status": "no_poses_to_cluster",
            "method": "identity_atom_order_rmsd",
            "strict_contract_version": STRICT_POSE_RMSD_CONTRACT_VERSION,
            "effective_method": _EFFECTIVE_RECEPTOR_METHOD,
            "coordinate_scope": "receptor_frame_same_ligand_state",
            "threshold_a": float(threshold_a),
            "symmetry_mapping_count": 1,
            "cluster_count": 0,
            "clusters": [],
        }
    first_index = int(rows[0]["pose_index"])
    if first_index not in placed_pose_coords:
        raise ValueError(f"pose coordinates missing for pose_index={first_index}")
    atom_count = int(_pose_coordinates(placed_pose_coords[first_index], label="pose").shape[0])
    mappings = _validated_symmetry_mappings(symmetry_mappings, atom_count=atom_count)
    clusters: list[dict[str, Any]] = []
    for row in rows:
        pose_index = int(row["pose_index"])
        if pose_index not in placed_pose_coords:
            raise ValueError(f"pose coordinates missing for pose_index={pose_index}")
        coords = _pose_coordinates(placed_pose_coords[pose_index], label="pose")
        if int(coords.shape[0]) != atom_count:
            raise ValueError("cluster poses must share one exact atom count")
        assigned_cluster = -1
        assigned_rmsd = float("inf")
        for cluster in clusters:
            representative_index = int(cluster["representative_pose_index"])
            representative = placed_pose_coords[representative_index]
            value = symmetry_aware_pose_rmsd(coords, representative, mappings)
            if value <= float(threshold_a):
                assigned_cluster = int(cluster["cluster_id"])
                assigned_rmsd = float(value)
                cluster["member_pose_indices"].append(pose_index)
                break
        if assigned_cluster < 0:
            assigned_cluster = len(clusters)
            assigned_rmsd = 0.0
            clusters.append(
                {
                    "cluster_id": assigned_cluster,
                    "representative_pose_index": pose_index,
                    "member_pose_indices": [pose_index],
                    "member_count": 1,
                }
            )
        row["pose_cluster_id"] = int(assigned_cluster)
        row["symmetry_aware_pose_rmsd_to_cluster_representative_a"] = float(assigned_rmsd)
        row["pose_rmsd_clustering"] = {
            "schema_version": "tier_beta_pose_rmsd_clustering_v1",
            "method": (
                "rdkit_automorphism_min_rmsd"
                if len(mappings) > 1
                else "identity_atom_order_rmsd"
            ),
            "strict_contract_version": STRICT_POSE_RMSD_CONTRACT_VERSION,
            "method_compatibility_alias": True,
            "effective_method": (
                _EFFECTIVE_RECEPTOR_METHOD
                if len(mappings) > 1
                else "identity_atom_order_receptor_frame_rmsd"
            ),
            "coordinate_scope": "receptor_frame_same_ligand_state",
            "threshold_a": float(threshold_a),
            "symmetry_mapping_count": int(len(mappings)),
            "cluster_id": int(assigned_cluster),
            "representative_rmsd_a": float(assigned_rmsd),
        }
    for cluster in clusters:
        cluster["member_count"] = int(len(cluster["member_pose_indices"]))
    return {
        "status": "symmetry_aware_rmsd_clustered",
        "method": (
            "rdkit_automorphism_min_rmsd"
            if len(mappings) > 1
            else "identity_atom_order_rmsd"
        ),
        "strict_contract_version": STRICT_POSE_RMSD_CONTRACT_VERSION,
        "method_compatibility_alias": True,
        "effective_method": (
            _EFFECTIVE_RECEPTOR_METHOD
            if len(mappings) > 1
            else "identity_atom_order_receptor_frame_rmsd"
        ),
        "coordinate_scope": "receptor_frame_same_ligand_state",
        "threshold_a": float(threshold_a),
        "symmetry_mapping_count": int(len(mappings)),
        "cluster_count": int(len(clusters)),
        "clusters": clusters,
    }


def _recording_cluster_poses(
    rows: list[dict[str, Any]],
    placed_pose_coords: dict[int, np.ndarray],
    symmetry_mappings: Any = None,
    *,
    threshold_a: float = 2.0,
) -> dict[str, Any]:
    context = _SCREEN_CONTEXT.get()
    if isinstance(context, dict):
        coords = context.setdefault("coords", {})
        for row in rows:
            pose_index = int(row["pose_index"])
            if pose_index in placed_pose_coords:
                coords[pose_index] = np.asarray(placed_pose_coords[pose_index], dtype=np.float64).copy()
    return _strict_cluster_poses(
        rows,
        placed_pose_coords,
        symmetry_mappings,
        threshold_a=threshold_a,
    )


def _screening_pose_rmsd(a: Any, b: Any) -> float:
    try:
        return pose_rmsd(a, b)
    except ValueError:
        return float("inf")


def _screening_symmetry_rmsd(a: Any, b: Any, symmetry_mappings: Any = None) -> float:
    try:
        return symmetry_aware_pose_rmsd(a, b, symmetry_mappings)
    except ValueError:
        return float("inf")


def state_scoped_pose_rmsd_diagnostics(
    pose_module: Any,
    pose_scores: list[dict[str, Any]],
    placed_pose_coords: dict[int, np.ndarray],
    *,
    fallback_ligand_smiles: str,
    threshold_a: float = 2.0,
) -> dict[str, Any]:
    """Annotate RMSD only within exact ligand-state identity groups."""

    groups: dict[str, dict[str, Any]] = {}
    for row in pose_scores:
        state = row.get("ligand_state") if isinstance(row.get("ligand_state"), dict) else {}
        state_smiles = str(state.get("smiles") or fallback_ligand_smiles)
        state_id = str(state.get("state_id") or f"ligand_state_smiles:{state_smiles}")
        group = groups.setdefault(
            state_id,
            {"state_id": state_id, "smiles": state_smiles, "rows": []},
        )
        if str(group["smiles"]) != state_smiles:
            raise ValueError(f"ligand state {state_id} has inconsistent SMILES identity")
        pose_index = int(row["pose_index"])
        if pose_index not in placed_pose_coords:
            raise ValueError(f"pose coordinates missing for pose_index={pose_index}")
        group["rows"].append(row)

    state_diagnostics: list[dict[str, Any]] = []
    for state_id, group in groups.items():
        state_smiles = str(group["smiles"])
        state_rows = list(group["rows"])
        mappings = pose_module.ligand_symmetry_mappings(state_smiles)
        state_diag = _strict_cluster_poses(
            state_rows,
            placed_pose_coords,
            mappings,
            threshold_a=threshold_a,
        )
        reference_row = state_rows[0]
        reference_pose_index = int(reference_row["pose_index"])
        reference_coords = placed_pose_coords[reference_pose_index]
        centroid_rows = state_rows[: min(5, len(state_rows))]
        centroid_pose_indices = [int(row["pose_index"]) for row in centroid_rows]
        ordered_members = [
            best_symmetry_ordered_pose(
                reference_coords,
                placed_pose_coords[pose_index],
                mappings,
            )
            for pose_index in centroid_pose_indices
        ]
        centroid = np.mean(ordered_members, axis=0)
        effective_method = (
            _EFFECTIVE_RECEPTOR_METHOD
            if mappings
            else "identity_atom_order_receptor_frame_rmsd"
        )
        legacy_method = (
            "rdkit_automorphism_min_rmsd" if mappings else "identity_atom_order_rmsd"
        )
        for row in state_rows:
            pose_index = int(row["pose_index"])
            coords = placed_pose_coords[pose_index]
            row["pose_rmsd_scope"] = "same_ligand_state_receptor_frame"
            row["pose_rmsd_reference_state_id"] = state_id
            row["pose_rmsd_reference_state_smiles"] = state_smiles
            row["pose_rmsd_reference_pose_index"] = reference_pose_index
            row["pose_rmsd_top5_centroid_member_pose_indices"] = centroid_pose_indices
            row["pose_rmsd_to_top1_a"] = pose_rmsd(coords, reference_coords)
            row["symmetry_aware_pose_rmsd_to_top1_a"] = symmetry_aware_pose_rmsd(
                coords,
                reference_coords,
                mappings,
            )
            row["pose_rmsd_to_top5_centroid_a"] = pose_rmsd(coords, centroid)
            row["symmetry_aware_pose_rmsd_to_top5_centroid_a"] = symmetry_aware_pose_rmsd(
                coords,
                centroid,
                mappings,
            )
            row["pose_rmsd_method"] = legacy_method
            row["pose_rmsd_effective_method"] = effective_method
            row["strict_pose_rmsd_contract_version"] = STRICT_POSE_RMSD_CONTRACT_VERSION
            pose_search = row.setdefault("pose_search", {})
            pose_search["symmetry_ligand_smiles"] = state_smiles
            pose_search["pose_rmsd_scope"] = "same_ligand_state_receptor_frame"
        state_diag.update(
            {
                "ligand_state_id": state_id,
                "ligand_state_smiles": state_smiles,
                "reference_pose_index": reference_pose_index,
                "top5_centroid_member_pose_indices": centroid_pose_indices,
                "atom_count": int(_pose_coordinates(reference_coords, label="reference pose").shape[0]),
                "rmsd_scope": "same_ligand_state_receptor_frame",
            }
        )
        state_diagnostics.append(state_diag)

    return {
        "status": "symmetry_aware_rmsd_clustered",
        "method": "rdkit_automorphism_min_rmsd",
        "strict_contract_version": STRICT_POSE_RMSD_CONTRACT_VERSION,
        "method_compatibility_alias": True,
        "effective_method": "state_scoped_rdkit_automorphism_min_receptor_frame_rmsd",
        "coordinate_scope": "same_ligand_state_receptor_frame",
        "threshold_a": float(threshold_a),
        "symmetry_mapping_count": int(
            max((int(diag["symmetry_mapping_count"]) for diag in state_diagnostics), default=1)
        ),
        "cluster_count": int(sum(int(diag["cluster_count"]) for diag in state_diagnostics)),
        "state_cluster_count": int(len(state_diagnostics)),
        "state_clusters": state_diagnostics,
    }


def _stage_records(payloads: list[dict[str, Any]]) -> list[StageRecord]:
    return [
        StageRecord(
            stage_id=str(row.get("stage_id") or ""),
            schema_version=str(row.get("schema_version") or ""),
            status=str(row.get("status") or ""),
            failure_code=str(row.get("failure_code") or "none"),
            message=str(row.get("message") or ""),
            diagnostics=deepcopy(row.get("diagnostics") or {}),
        )
        for row in payloads
    ]


def _typed_input(payload: dict[str, Any]) -> TierBetaScreeningInput:
    return TierBetaScreeningInput(
        protein_input_kind=str(payload.get("protein_input_kind") or "inline_text"),
        ligand_input_kind=str(payload.get("ligand_input_kind") or "inline_text"),
        pose_count=int(payload.get("pose_count") or 1),
        top_k=int(payload.get("top_k") or 1),
        stability_steps=int(payload.get("stability_steps") or 0),
        seed=int(payload.get("seed") or 0),
        schema_version=str(payload.get("schema_version") or "tier_beta_biodiscovery_screening_v1"),
    )


def _strict_screening_class(original_class: type, pose_module: Any) -> type:
    class StrictTierBetaScreening(original_class):
        __strict_pose_contract__ = STRICT_POSE_RMSD_CONTRACT_VERSION

        def screen(self, *args: Any, **kwargs: Any) -> Any:
            context: dict[str, Any] = {"coords": {}}
            token = _SCREEN_CONTEXT.set(context)
            result = None
            try:
                result = super().screen(*args, **kwargs)
                manifest = result.result_manifest if isinstance(result.result_manifest, dict) else {}
                full_pose_scores = manifest.get("pose_scores")
                if not isinstance(full_pose_scores, list) or not full_pose_scores:
                    return result
                coords = context.get("coords")
                if not isinstance(coords, dict) or not coords:
                    raise ValueError("pose coordinate context missing for strict RMSD postprocessing")
                clustering = state_scoped_pose_rmsd_diagnostics(
                    pose_module,
                    full_pose_scores,
                    coords,
                    fallback_ligand_smiles=str(result.ligand_smiles),
                    threshold_a=2.0,
                )

                stage_payloads = deepcopy(result.stage_records)
                for stage in stage_payloads:
                    if stage.get("stage_id") == "top_k_refine":
                        diagnostics = stage.setdefault("diagnostics", {})
                        diagnostics["rmsd_clustering"] = clustering
                result.stage_records = stage_payloads
                result.pose_scores = full_pose_scores[: int(result.top_k)]

                diagnostics = deepcopy(result.diagnostics)
                search = diagnostics.setdefault("pose_search_aggregation", {})
                search["symmetry_rmsd_clustering_status"] = clustering["status"]
                search["symmetry_mapping_count"] = int(clustering["symmetry_mapping_count"])
                search["symmetry_cluster_count"] = int(clustering["cluster_count"])
                search["pose_rmsd_scope"] = clustering["coordinate_scope"]
                diagnostics["strict_pose_rmsd_contract"] = {
                    "version": STRICT_POSE_RMSD_CONTRACT_VERSION,
                    "state_scoped": True,
                    "atom_count_truncation_allowed": False,
                    "incomplete_symmetry_mapping_allowed": False,
                    "conformer_alignment": "proper_rotation_kabsch",
                    "claim_safe": False,
                }

                rebuilt = self._build_manifest(
                    protein_seq=str(result.protein_sequence),
                    protein_residues=int(result.protein_residue_count),
                    ligand_smiles=str(result.ligand_smiles),
                    ligand_atom=int(result.ligand_atom_count),
                    ligand_valid_flag=bool(result.ligand_valid),
                    pocket_indices=list(result.pocket_residue_indices),
                    poses_generated=int(result.poses_generated),
                    poses_scored=int(result.poses_scored),
                    top_k=int(result.top_k),
                    best_score=float(result.best_score),
                    best_rank=int(result.best_rank),
                    stability_steps=int(result.stability_steps_run),
                    stability_drift=float(result.stability_drift_A),
                    stability_ok=bool(result.stability_ok),
                    stability_diagnostics=deepcopy(manifest.get("stability", {}).get("diagnostics", {})),
                    pose_scores=full_pose_scores,
                    benchmark_metric_summary=deepcopy(manifest.get("benchmark_metric_summary", {})),
                    protein_valid=deepcopy(diagnostics.get("protein_valid", {})),
                    ligand_valid=deepcopy(diagnostics.get("ligand_valid", {})),
                    stage_records=_stage_records(stage_payloads),
                    typed_input=_typed_input(result.typed_input),
                )
                result.result_manifest = rebuilt
                result.manifest_hash = str(rebuilt["content_hash"])
                result.claim_metadata = deepcopy(rebuilt["claim_metadata"])
                result.typed_output = {
                    **dict(result.typed_output),
                    "manifest_hash": str(rebuilt["content_hash"]),
                }
                diagnostics["result_signed"] = bool(rebuilt.get("signature"))
                result.diagnostics = diagnostics
                return result
            except ValueError as exc:
                typed = None
                stages: list[StageRecord] = []
                try:
                    typed = _typed_input(getattr(result, "typed_input", {}))
                    stages = _stage_records(getattr(result, "stage_records", []))
                except Exception:
                    typed = None
                    stages = []
                return self._fail(
                    f"pose_rmsd_contract_failed:{exc}",
                    getattr(result, "protein_sequence", ""),
                    int(getattr(result, "protein_residue_count", 0)),
                    getattr(result, "ligand_smiles", ""),
                    ligand_atom=int(getattr(result, "ligand_atom_count", 0)),
                    pocket=list(getattr(result, "pocket_residue_indices", [])),
                    poses_gen=int(getattr(result, "poses_generated", 0)),
                    typed_input=typed,
                    stage_records=stages,
                )
            finally:
                _SCREEN_CONTEXT.reset(token)

    StrictTierBetaScreening.__name__ = "TierBetaScreening"
    StrictTierBetaScreening.__qualname__ = "TierBetaScreening"
    StrictTierBetaScreening.__module__ = original_class.__module__
    return StrictTierBetaScreening


def install_strict_pose_contracts(pose_module: Any, screening_module: Any) -> None:
    """Install strict semantics idempotently onto legacy public module paths."""

    current_class = getattr(screening_module, "TierBetaScreening")
    if getattr(current_class, "__strict_pose_contract__", "") == STRICT_POSE_RMSD_CONTRACT_VERSION:
        return

    pose_module.pose_rmsd = pose_rmsd
    pose_module.symmetry_aware_pose_rmsd = symmetry_aware_pose_rmsd
    pose_module.aligned_symmetry_aware_pose_rmsd = aligned_symmetry_aware_pose_rmsd
    pose_module.best_symmetry_ordered_pose = best_symmetry_ordered_pose
    pose_module.conformer_diversity_diagnostics = lambda poses, *, smiles="", diversity_threshold_a=0.5: _strict_conformer_diversity(
        pose_module,
        poses,
        smiles=smiles,
        diversity_threshold_a=diversity_threshold_a,
    )
    pose_module.cluster_poses_by_symmetry = _strict_cluster_poses

    screening_module._pose_rmsd = _screening_pose_rmsd
    screening_module._symmetry_aware_pose_rmsd = _screening_symmetry_rmsd
    screening_module._cluster_poses_by_symmetry = _recording_cluster_poses
    screening_module.TierBetaScreening = _strict_screening_class(current_class, pose_module)
    screening_module.make_screening = (
        lambda *, device="cpu", **kwargs: screening_module.TierBetaScreening(device=device, **kwargs)
    )


__all__ = [
    "STRICT_POSE_RMSD_CONTRACT_VERSION",
    "aligned_symmetry_aware_pose_rmsd",
    "best_symmetry_ordered_pose",
    "install_strict_pose_contracts",
    "pose_rmsd",
    "state_scoped_pose_rmsd_diagnostics",
    "symmetry_aware_pose_rmsd",
]
