from __future__ import annotations

import math
import os
import re
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

from betelgeuze_engine.biodiscovery.coarse_receptor import prepare_receptor_proxy

from betelgeuze_engine.benchmark.docking_gold import (
    DockingGoldRow,
    evaluate_docking_gold_slice,
)
from betelgeuze_engine.biodiscovery.contracts import (
    CLAIM_SCOPE,
    SCHEMA_VERSION,
    FailureCode,
    StageRecord,
    TierBetaScreeningInput,
    TierBetaScreeningOutput,
    failure_code_for_reason,
)
from betelgeuze_engine.chemistry.ligand_states import (
    enumerate_ligand_states_from_smiles as _enumerate_ligand_states_from_smiles,
)
from betelgeuze_engine.physics.dense_guard import ensure_small_dense_diagnostic
from betelgeuze_engine.biodiscovery.ligand_prep import (
    ResolvedLigandInput,
    ligand_topology_payload as _ligand_topology_payload,
    looks_like_sdf_text as _looks_like_sdf_text,
    mol_topology_provenance as _mol_topology_provenance,
    resolve_ligand_input as _resolve_ligand_input,
    resolve_sdf_text as _resolve_sdf_text,
    validate_ligand as _validate_ligand,
)
from betelgeuze_engine.biodiscovery.manifest import (
    BLOCKED_CLAIMS as _BLOCKED_CLAIMS,
    CLAIM_BOUNDARY as _CLAIM_BOUNDARY,
    LOCAL_MANIFEST_KEY as _LOCAL_MANIFEST_KEY,
    build_screening_manifest,
    sign_screening_manifest,
    verify_screening_manifest,
)
from betelgeuze_engine.biodiscovery.protein_prep import (
    AA3_TO_AA1 as _AA3_TO_AA1,
    aa3_to_aa1 as _aa3_to_aa1,
    looks_like_mmcif_text as _looks_like_mmcif_text,
    parse_mmcif_text as _parse_mmcif_text,
    parse_pdb_text as _parse_pdb_text,
    resolve_protein_input as _resolve_protein_input,
    validate_protein as _validate_protein,
)
from betelgeuze_engine.biodiscovery.pose import (
    _real_coordinate_array,
    best_symmetry_mapped_pose as _best_symmetry_mapped_pose,
    chemical_anchor_mapping as _chemical_anchor_mapping,
    chemistry_validity_summary as _chemistry_validity_summary,
    clash_count as _clash_count,
    cluster_poses_by_symmetry as _cluster_poses_by_symmetry,
    generate_conformers as _generate_conformers,
    ligand_symmetry_mappings as _ligand_symmetry_mappings,
    pose_search_candidates as _pose_search_candidates,
    pose_rmsd as _pose_rmsd,
    resolve_pocket_indices as _resolve_pocket_indices,
    symmetry_aware_pose_rmsd as _symmetry_aware_pose_rmsd,
    virtual_protein_coords as _virtual_protein_coords,
)
from betelgeuze_engine.biodiscovery.scoring import (
    DEFAULT_BOX_SIZE as _DEFAULT_BOX_SIZE,
    DEFAULT_STABILITY_DT as _DEFAULT_STABILITY_DT,
    DEFAULT_STABILITY_STEPS as _DEFAULT_STABILITY_STEPS,
    DEFAULT_STABILITY_TEMP_K as _DEFAULT_STABILITY_TEMP_K,
    build_atom_types as _build_atom_types,
    mm_gbsa_binding_score as _mm_gbsa_binding_score,
    run_stability_simulation as _run_stability_simulation,
    single_pose_score as _single_pose_score,
    make_static_pose_field,
)

_COMPAT_LIGAND_PREP_HELPERS = (
    ResolvedLigandInput,
    _looks_like_sdf_text,
    _mol_topology_provenance,
    _resolve_sdf_text,
)
_COMPAT_PROTEIN_PREP_HELPERS = (
    _AA3_TO_AA1,
    _aa3_to_aa1,
    _looks_like_mmcif_text,
    _parse_mmcif_text,
    _parse_pdb_text,
)
_COMPAT_SCORING_HELPERS = (
    _DEFAULT_BOX_SIZE,
    _build_atom_types,
)
_COMPAT_MANIFEST_HELPERS = (
    _LOCAL_MANIFEST_KEY,
)
_COMPAT_POSE_HELPERS = (
    _resolve_pocket_indices,
    _symmetry_aware_pose_rmsd,
    _virtual_protein_coords,
)

try:
    from rdkit import Chem
except Exception:
    Chem = None

_SCHEMA_VERSION = SCHEMA_VERSION
_CLAIM_SCOPE = CLAIM_SCOPE
_DEFAULT_SEED = 42
_DEFAULT_POCKET_CUTOFF_A = 8.0
_DEFAULT_POSE_COUNT = 32
_DEFAULT_TOP_K = 5
_SUPPORTED_LIGAND_ELEMENTS = {"B", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I", "H", "Si"}
_LIGAND_STATE_ENSEMBLE_STATUS = "restricted_rdkit_standardized_state_ensemble_ph_range_no_pka_calibration"

@dataclass
class TierBetaScreeningResult:
    ok: bool
    blocked_reason: str
    claim_scope: str
    schema_version: str
    protein_sequence: str
    protein_residue_count: int
    ligand_smiles: str
    ligand_atom_count: int
    ligand_valid: bool
    pocket_residue_indices: list[int]
    pocket_residue_count: int
    poses_generated: int
    poses_scored: int
    top_k: int
    best_score: float | None
    best_rank: int
    stability_steps_run: int
    stability_drift_A: float | None
    stability_ok: bool | None
    manifest_hash: str
    claim_metadata: dict[str, Any]
    pose_scores: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    result_manifest: dict[str, Any] = field(default_factory=dict)
    failure_code: str = FailureCode.NONE.value
    stage_records: list[dict[str, Any]] = field(default_factory=list)
    typed_input: dict[str, Any] = field(default_factory=dict)
    typed_output: dict[str, Any] = field(default_factory=dict)


def _atom_count_from_smiles(smiles: str) -> int:
    if Chem is None:
        return len(re.findall(r"Cl|Br|[BCNOFPSIHK]", str(smiles)))
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return 0
    return mol.GetNumAtoms()


def _unsupported_ligand_elements(ligand_valid: dict[str, Any]) -> list[str]:
    elements = [str(element) for element in ligand_valid.get("atom_elements", [])]
    return sorted({element for element in elements if element and element not in _SUPPORTED_LIGAND_ELEMENTS})


def _benchmark_metric_summary_from_pose_scores(pose_scores: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[DockingGoldRow] = []
    for row in pose_scores:
        chemistry = row.get("chemistry_validity") if isinstance(row.get("chemistry_validity"), dict) else {}
        chemistry_failures = [
            str(reason)
            for reason in (chemistry.get("blockers") or [] if isinstance(chemistry.get("blockers"), list) else [])
            if reason
        ]
        rows.append(
            DockingGoldRow(
                complex_id="tier_beta_local_input",
                pose_id=f"pose_{int(row.get('pose_index', len(rows)))}",
                pose_rank=int(row.get("pose_rank") or len(rows) + 1),
                pose_rmsd_a=None,
                score=float(row.get("composite_score", float("inf"))),
                active_label=None,
                abstained=bool(row.get("abstention", False)),
                chemistry_failures=tuple(chemistry_failures),
                abstention_reasons=tuple(
                    str(reason)
                    for reason in (row.get("abstention_reasons") or [])
                    if isinstance(row.get("abstention_reasons"), list) and str(reason)
                ),
            )
        )
    payload = evaluate_docking_gold_slice(rows, pose_success_rmsd_a=2.0, top_k=5).to_dict()
    payload["status"] = "blocked_reference_pose_missing"
    payload["score_metric"] = "restricted_cross_component_composite_v2"
    payload["scored_pose_count"] = int(len(pose_scores))
    payload["blockers"] = sorted(
        {
            *payload.get("blockers", []),
            "native_or_reference_pose_missing",
            "pose_rmsd_not_computable",
            "ranking_labels_missing",
        }
    )
    payload["claim_boundary"] = (
        "Diagnostics only; no CASF/PDBbind/native-pose success, calibrated affinity, or wetlab-hit claim. "
        "Reference/native pose and held-out labels are required before promotion."
    )
    return payload



def _ligand_state_identity(row: dict[str, Any], default_smiles: str) -> tuple[str, str]:
    state = row.get("ligand_state")
    if not isinstance(state, dict):
        state = {}
    state_smiles = str(state.get("smiles") or default_smiles)
    state_id = str(state.get("state_id") or f"smiles:{state_smiles}")
    return state_id, state_smiles


def _annotate_state_scoped_pose_rmsd(
    pose_scores: list[dict[str, Any]],
    placed_pose_coords: dict[int, np.ndarray],
    *,
    default_smiles: str,
    cluster_threshold_a: float = 2.0,
    centroid_limit: int = 5,
) -> dict[str, Any]:
    """Cluster and annotate poses only against chemically comparable ligand states."""

    state_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in pose_scores:
        state_id, state_smiles = _ligand_state_identity(row, default_smiles)
        state_groups.setdefault((state_id, state_smiles), []).append(row)

    state_diagnostics: list[dict[str, Any]] = []
    max_mapping_count = 1
    total_cluster_count = 0
    for (state_id, state_smiles), state_rows in state_groups.items():
        mappings = _ligand_symmetry_mappings(state_smiles)
        state_diag = _cluster_poses_by_symmetry(
            state_rows,
            placed_pose_coords,
            mappings,
            threshold_a=float(cluster_threshold_a),
        )
        state_diag["ligand_state_id"] = state_id
        state_diag["ligand_state_smiles"] = state_smiles
        state_diag["state_pose_count"] = int(len(state_rows))
        state_diag["state_scoped"] = True
        state_diagnostics.append(state_diag)
        max_mapping_count = max(max_mapping_count, int(state_diag["symmetry_mapping_count"]))
        total_cluster_count += int(state_diag["cluster_count"])

        state_top1 = state_rows[0]
        reference_pose_index = int(state_top1["pose_index"])
        reference_coords = placed_pose_coords[reference_pose_index]
        centroid_rows = state_rows[: min(max(1, int(centroid_limit)), len(state_rows))]
        canonicalized: list[np.ndarray] = []
        for centroid_row in centroid_rows:
            coords = placed_pose_coords[int(centroid_row["pose_index"])]
            mapped, _rmsd, _mapping = _best_symmetry_mapped_pose(
                reference_coords,
                coords,
                mappings,
                align=False,
            )
            canonicalized.append(mapped)
        centroid = np.mean(canonicalized, axis=0)

        for row in state_rows:
            coords = placed_pose_coords[int(row["pose_index"])]
            mapped, symmetry_rmsd, mapping = _best_symmetry_mapped_pose(
                reference_coords,
                coords,
                mappings,
                align=False,
            )
            row["pose_rmsd_to_top1_a"] = _pose_rmsd(coords, reference_coords)
            row["symmetry_aware_pose_rmsd_to_top1_a"] = float(symmetry_rmsd)
            row["pose_rmsd_to_top5_centroid_a"] = _pose_rmsd(mapped, centroid)
            row["pose_rmsd_method"] = (
                "rdkit_automorphism_min_rmsd" if mappings else "identity_atom_order_rmsd"
            )
            row["pose_rmsd_state_scoped"] = True
            row["pose_rmsd_reference_state_id"] = state_id
            row["pose_rmsd_reference_pose_index"] = reference_pose_index
            row["pose_rmsd_top5_centroid_member_count"] = int(len(centroid_rows))
            row["pose_rmsd_atom_count"] = int(coords.shape[0])
            row["pose_rmsd_symmetry_mapping"] = [int(index) for index in mapping]
            row["pose_search"]["symmetry_ligand_smiles"] = state_smiles
            row["pose_search"]["symmetry_ligand_state_id"] = state_id

    return {
        "status": "symmetry_aware_rmsd_clustered",
        "method": "rdkit_automorphism_min_rmsd",
        "threshold_a": float(cluster_threshold_a),
        "symmetry_mapping_count": int(max_mapping_count),
        "cluster_count": int(total_cluster_count),
        "state_cluster_count": int(len(state_diagnostics)),
        "state_scoped": True,
        "cross_state_rmsd_computed": False,
        "atom_mapping_contract": "strict_full_atom_bijection",
        "coordinate_frame": "receptor_frame_no_alignment",
        "state_clusters": state_diagnostics,
    }

class TierBetaScreening:
    def __init__(
        self,
        *,
        device: torch.device | str = "cpu",
        pocket_cutoff_a: float = _DEFAULT_POCKET_CUTOFF_A,
        pose_count: int = _DEFAULT_POSE_COUNT,
        top_k: int = _DEFAULT_TOP_K,
        stability_steps: int = _DEFAULT_STABILITY_STEPS,
        stability_dt: float = _DEFAULT_STABILITY_DT,
        stability_temp_k: float = _DEFAULT_STABILITY_TEMP_K,
        seed: int = _DEFAULT_SEED,
    ):
        self.device = torch.device(device)
        for name, value, minimum in (("pose_count", pose_count, 1), ("top_k", top_k, 1),
                                     ("stability_steps", stability_steps, 0), ("seed", seed, 0)):
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if seed > 2**31 - 1:
            raise ValueError("seed must fit the nonnegative signed 32-bit conformer seed domain")
        for name, value, allow_zero in (("pocket_cutoff_a", pocket_cutoff_a, False),
                                         ("stability_dt", stability_dt, False),
                                         ("stability_temp_k", stability_temp_k, True)):
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)) or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
                raise ValueError(f"invalid {name}")
        self.pocket_cutoff_a = float(pocket_cutoff_a)
        self.pose_count = int(pose_count)
        self.top_k = int(top_k)
        self.stability_steps = int(stability_steps)
        self.stability_dt = float(stability_dt)
        self.stability_temp_k = float(stability_temp_k)
        self.seed = int(seed)
        self._rng = np.random.RandomState(self.seed)

    def _typed_input(self, protein_input: str, ligand_input: str) -> TierBetaScreeningInput:
        return TierBetaScreeningInput(
            protein_input_kind="path" if os.path.isfile(str(protein_input).strip()) else "inline_text",
            ligand_input_kind="path" if os.path.isfile(str(ligand_input).strip()) else "inline_text",
            pose_count=self.pose_count,
            top_k=self.top_k,
            stability_steps=self.stability_steps,
            seed=self.seed,
        )

    def screen(
        self,
        *,
        protein_input: str,
        ligand_input: str,
        pocket_residue_indices: list[int] | None = None,
    ) -> TierBetaScreeningResult:
        return self._screen_observed(protein_input=protein_input, ligand_input=ligand_input,
                                     pocket_residue_indices=pocket_residue_indices)

    def _screen_observed(self, *, protein_input: str, ligand_input: str,
                         pocket_residue_indices: list[int] | None,
                         prepared_protein: tuple | None = None,
                         receptor_cache: dict | None = None,
                         shared_preparation_elapsed_seconds: float | None = None) -> TierBetaScreeningResult:
        started = time.perf_counter()
        timings = {stage: 0.0 for stage in ("preparation", "conformer", "search", "scoring")}
        records: list[StageRecord] = []
        try:
            result = self._screen(protein_input=protein_input, ligand_input=ligand_input,
                                  pocket_residue_indices=pocket_residue_indices,
                                  stage_records=records, timings=timings,
                                  prepared_protein=prepared_protein, receptor_cache=receptor_cache)
        except Exception as exc:
            result = self._fail(f"screening_evaluation_failed:{type(exc).__name__}:{exc}",
                                stage_records=records,
                                typed_input=self._typed_input(str(protein_input or ""), str(ligand_input or "")))
        observations = {"elapsed_seconds": {**timings, "total": time.perf_counter() - started},
                        "evidence_kind": "wall_clock_observation_not_performance_qualification",
                        "timing_scope": "per_ligand_invocation_excludes_shared_batch_preparation",
                        "shared_preparation_elapsed_seconds": shared_preparation_elapsed_seconds}
        result.diagnostics.setdefault("execution_observations", {}).update(observations)
        result.result_manifest = sign_screening_manifest({**result.result_manifest,
                                                         "execution_observations": observations})
        result.manifest_hash = result.result_manifest["content_hash"]
        result.typed_output["manifest_hash"] = result.manifest_hash
        return result

    def screen_many(self, *, protein_input: str, ligand_inputs: list[str],
                    pocket_residue_indices: list[int] | None = None) -> list[TierBetaScreeningResult]:
        """Sequential local diagnostics sharing one consumed receptor snapshot.

        No concurrent service state or cross-run file cache is retained. Each
        result still reserves its own ligand sites against the diagnostic cap.
        """
        if not isinstance(ligand_inputs, list) or not all(isinstance(item, str) for item in ligand_inputs):
            raise ValueError("ligand_inputs must be a list of input strings")
        if not ligand_inputs:
            return []
        snapshot: dict[str, Any] = {}
        preparation_started = time.perf_counter()
        try:
            coords, seq = _resolve_protein_input(str(protein_input), snapshot=snapshot)
        except ValueError as exc:
            return [self._fail(f"protein_parse_failed:{exc}",
                               typed_input=self._typed_input(str(protein_input), item),
                               stage_records=[StageRecord("protein_preparation", _SCHEMA_VERSION, "blocked",
                                                          diagnostics={"protein_input_snapshot": snapshot or None})])
                    for item in ligand_inputs]
        cache: dict = {}
        shared_preparation_elapsed = time.perf_counter() - preparation_started
        return [self._screen_observed(protein_input=protein_input, ligand_input=item,
                                      pocket_residue_indices=pocket_residue_indices,
                                      prepared_protein=(coords, seq, snapshot), receptor_cache=cache,
                                      shared_preparation_elapsed_seconds=shared_preparation_elapsed)
                for item in ligand_inputs]

    def _screen(self, *, protein_input: str, ligand_input: str,
                pocket_residue_indices: list[int] | None, stage_records: list[StageRecord],
                timings: dict[str, float], prepared_protein: tuple | None,
                receptor_cache: dict | None) -> TierBetaScreeningResult:
        preparation_started = time.perf_counter()
        typed_input = self._typed_input(str(protein_input or ""), str(ligand_input or ""))
        if pocket_residue_indices is not None and not isinstance(pocket_residue_indices, list):
            return self._fail("invalid_pocket_residue_indices", typed_input=typed_input)
        if not protein_input or not str(protein_input).strip():
            return self._fail("empty_protein_input", typed_input=typed_input)

        protein_snapshot: dict[str, Any] = {}
        try:
            if prepared_protein is None:
                protein_coords, protein_seq = _resolve_protein_input(str(protein_input), snapshot=protein_snapshot)
            else:
                protein_coords, protein_seq, protein_snapshot = prepared_protein
        except ValueError as e:
            return self._fail(f"protein_parse_failed: {e}", typed_input=typed_input,
                              stage_records=[StageRecord("protein_preparation", _SCHEMA_VERSION, "blocked",
                                                         diagnostics={"protein_input_snapshot": protein_snapshot or None})])
        stage_records.append(
            StageRecord(
                stage_id="protein_preparation",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"residue_count": int(protein_coords.shape[0]),
                             "protein_input_snapshot": protein_snapshot or None},
            )
        )

        ligand_snapshot: dict[str, Any] = {}
        try:
            resolved_ligand = _resolve_ligand_input(str(ligand_input), input_snapshot=ligand_snapshot)
            ligand_smiles = resolved_ligand.smiles
        except ValueError as e:
            stage_records.append(StageRecord("ligand_preparation", _SCHEMA_VERSION, "blocked",
                                             diagnostics={"ligand_input_snapshot": ligand_snapshot or None}))
            return self._fail(f"ligand_parse_failed: {e}", typed_input=typed_input, stage_records=stage_records)
        stage_records.append(StageRecord(
            "ligand_preparation", _SCHEMA_VERSION, "pass",
            diagnostics={"ligand_input_snapshot": ligand_snapshot or None}))

        protein_valid = _validate_protein(protein_coords, protein_seq)
        if protein_valid["blocked"]:
            return self._fail(f"protein_invalid: {protein_valid['blocker']}",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              typed_input=typed_input,
                              stage_records=stage_records)
        stage_records.append(
            StageRecord(
                stage_id="topology_validation.protein",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics=protein_valid,
            )
        )

        ligand_valid = _validate_ligand(ligand_smiles, resolved_input=resolved_ligand)
        if ligand_valid["blocked"]:
            return self._fail(f"ligand_invalid: {';'.join(ligand_valid['blockers'])}",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_valid["atom_count"],
                              typed_input=typed_input,
                              stage_records=stage_records)
        stage_records.append(
            StageRecord(
                stage_id="topology_validation.ligand",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics=ligand_valid,
            )
        )

        if int(ligand_valid["atom_count"]) <= 0:
            return self._fail("empty_ligand_topology",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              typed_input=typed_input,
                              stage_records=stage_records)

        ligand_atom = int(ligand_valid["atom_count"])
        timings["preparation"] += time.perf_counter() - preparation_started
        ligand_states = _enumerate_ligand_states_from_smiles(
            ligand_smiles,
            max_states=min(4, max(1, self.pose_count)),
        )
        state_pose_bundles: list[dict[str, Any]] = []
        state_records: list[dict[str, Any]] = []
        poses_generated = 0
        ligand_center: np.ndarray | None = None
        for state in ligand_states:
            state_payload = state.to_dict()
            state_smiles = str(state.smiles or ligand_smiles)
            if not state.valid:
                state_payload["scoring_status"] = "not_scored_invalid_ligand_state"
                state_records.append(state_payload)
                continue
            state_ligand_valid = _validate_ligand(state_smiles, resolved_input=resolved_ligand)
            state_payload["topology_validation"] = {
                "valid": bool(state_ligand_valid.get("valid", False)),
                "claim_safe": bool(state_ligand_valid.get("claim_safe", False)),
                "blocked": bool(state_ligand_valid.get("blocked", False)),
                "blockers": list(state_ligand_valid.get("blockers", [])),
                "atom_count": int(state_ligand_valid.get("atom_count", 0)),
            }
            if state_ligand_valid["blocked"]:
                state_payload["scoring_status"] = "not_scored_topology_blocked"
                state_records.append(state_payload)
                continue
            unsupported_elements = _unsupported_ligand_elements(state_ligand_valid)
            if unsupported_elements:
                state_payload["scoring_status"] = "not_scored_unsupported_ligand_element"
                state_payload["unsupported_elements"] = unsupported_elements
                state_payload["claim_safe_blockers"] = sorted(
                    {
                        *list(state_payload.get("claim_safe_blockers", [])),
                        "unsupported_ligand_metal_or_counterion",
                    }
                )
                state_records.append(state_payload)
                continue
            state_atom = int(state_ligand_valid["atom_count"])
            if state_atom <= 0:
                state_payload["scoring_status"] = "not_scored_empty_ligand_topology"
                state_records.append(state_payload)
                continue
            state_seed = int((self.seed + int(state.rank) * 1009) % (2**31))
            try:
                conformer_started = time.perf_counter()
                state_poses = _generate_conformers(state_smiles, self.pose_count, state_seed)
            except Exception as exc:
                state_payload["scoring_status"] = "not_scored_conformer_generation_failed"
                state_payload["error"] = str(exc)
                state_records.append(state_payload)
                continue
            finally:
                timings["conformer"] += time.perf_counter() - conformer_started
            if state_poses is None or int(state_poses.shape[0]) <= 0:
                state_payload["scoring_status"] = "not_scored_conformer_generation_failed"
                state_payload["seed"] = state_seed
                state_records.append(state_payload)
                continue
            poses_generated += int(state_poses.shape[0])
            if ligand_center is None:
                ligand_center = state_poses[0].mean(axis=0)
            state_payload["scoring_status"] = "pose_conformers_generated"
            state_payload["poses_generated"] = int(state_poses.shape[0])
            state_payload["seed"] = state_seed
            state_records.append(state_payload)
            state_pose_bundles.append(
                {
                    "state": state_payload,
                    "smiles": state_smiles,
                    "ligand_valid": state_ligand_valid,
                    "atom_count": state_atom,
                    "poses": state_poses,
                    "seed": state_seed,
                }
            )

        ensemble_claim_blockers = sorted(
            {
                str(blocker)
                for state in state_records
                for blocker in state.get("claim_safe_blockers", [])
                if str(blocker)
            }
        )
        if ensemble_claim_blockers:
            ligand_valid = dict(ligand_valid)
            ensemble_projection_blockers = ["ligand_state_projection_not_product_safe"]
            if any(
                blocker in {"salt_parent_projection_not_product_safe", "unsupported_ligand_metal_or_counterion"}
                for blocker in ensemble_claim_blockers
            ):
                ensemble_projection_blockers.append("fragment_parent_projection_not_product_safe")
            ligand_valid["blockers"] = sorted(
                {
                    *[str(blocker) for blocker in ligand_valid.get("blockers", [])],
                    *ensemble_claim_blockers,
                    *ensemble_projection_blockers,
                }
            )
            ligand_valid["blocked"] = True
            ligand_valid["claim_safe"] = False
            ligand_valid["state_ensemble_claim_safe"] = False
            ligand_valid["state_ensemble_blockers"] = ensemble_claim_blockers
            ligand_valid["projection_status"] = (
                "fragment_parent_scored_after_unsupported_ligand_state_skip"
                if "fragment_parent_projection_not_product_safe" in ligand_valid["blockers"]
                else "ligand_state_projection_scored_for_diagnostics_only"
            )

        stage_records.append(
            StageRecord(
                stage_id="pose_ensemble",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={
                    "poses_generated": int(poses_generated),
                    "seed": int(self.seed),
                    "ligand_state_ensemble": {
                        "schema_version": "tier_beta_ligand_state_ensemble_v1",
                        "status": _LIGAND_STATE_ENSEMBLE_STATUS,
                        "state_count": int(len(ligand_states)),
                        "scored_state_count": int(len(state_pose_bundles)),
                        "claim_safe": bool(not ensemble_claim_blockers),
                        "claim_safe_blockers": ensemble_claim_blockers,
                        "states": state_records,
                    },
                },
            )
        )

        if not state_pose_bundles:
            return self._fail("ligand_state_ensemble_no_scored_states",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom, typed_input=typed_input,
                              stage_records=stage_records)

        resolved_pocket = (
            list(pocket_residue_indices)
            if pocket_residue_indices is not None
            else list(range(len(protein_coords)))
        )
        if any(isinstance(idx, (bool, np.bool_)) or not isinstance(idx, (int, np.integer))
               or idx < 0 or idx >= int(protein_coords.shape[0]) for idx in resolved_pocket) or len(set(resolved_pocket)) != len(resolved_pocket):
            return self._fail("invalid_pocket_residue_indices",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              typed_input=typed_input,
                              stage_records=stage_records)
        if not resolved_pocket:
            return self._fail("empty_pocket_resolution",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              typed_input=typed_input,
                              stage_records=stage_records)
        stage_records.append(
            StageRecord(
                stage_id="pocket_resolution",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"pocket_residue_indices": [int(idx) for idx in resolved_pocket],
                             "selection_mode": "explicit_pocket" if pocket_residue_indices is not None
                             else "unlocalized_whole_small_receptor_diagnostic",
                             "pocket_discovery_performed": False},
            )
        )

        try:
            preparation_started = time.perf_counter()
            maximum_atoms = max(int(bundle["atom_count"]) for bundle in state_pose_bundles)
            cache_key = (tuple(resolved_pocket), pocket_residue_indices is not None)
            cached = receptor_cache.get(cache_key) if receptor_cache is not None else None
            if cached is None:
                protein_beads, pocket_center, receptor_context = prepare_receptor_proxy(
                    protein_coords, resolved_pocket, ligand_atom_count=maximum_atoms,
                    buffer_a=self.pocket_cutoff_a, explicit_pocket=pocket_residue_indices is not None)
                static_field = make_static_pose_field()
                if receptor_cache is not None:
                    receptor_cache[cache_key] = (protein_beads, pocket_center, receptor_context, static_field)
            else:
                protein_beads, pocket_center, receptor_context, static_field = cached
                if len(protein_beads) + maximum_atoms > receptor_context["dense_diagnostic_cap"]:
                    raise ValueError("dense_diagnostic_blocked:cached_receptor_ligand_domain_exceeds_cap")
                receptor_context = {**receptor_context, "reserved_ligand_atom_count": maximum_atoms}
        except ValueError as exc:
            return self._fail(str(exc), protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom, pocket=resolved_pocket,
                              typed_input=typed_input, stage_records=stage_records)
        finally:
            timings["preparation"] += time.perf_counter() - preparation_started
        stage_records[-1].diagnostics["receptor_proxy"] = receptor_context
        pose_scores: list[dict[str, Any]] = []
        candidate_records: list[dict[str, Any]] = []
        stage_records.append(StageRecord("candidate_evaluation", _SCHEMA_VERSION, "diagnostic",
                                         diagnostics={"candidates": candidate_records}))
        placed_pose_coords: dict[int, np.ndarray] = {}
        global_pose_index = 0
        search_diagnostics: dict[str, Any] = {
            "schema_version": "tier_beta_state_pose_search_aggregation_v1",
            "ligand_state_ensemble_status": _LIGAND_STATE_ENSEMBLE_STATUS,
            "state_count": int(len(ligand_states)),
            "scored_state_count": int(len(state_pose_bundles)),
            "raw_candidate_count": 0,
            "coarse_beam_candidate_count": 0,
            "retained_candidate_count": 0,
            "local_minimization_status": "finite_difference_rigid_body_gradient_not_attempted",
            "local_minimization_method": "finite_difference_gradient_descent_translation_rotation",
            "local_minimization_degrees_of_freedom": ["translation", "rotation"],
            "local_minimization_candidate_count": 0,
            "local_minimization_improved_count": 0,
            "states": [],
        }
        for bundle in state_pose_bundles:
            state_payload = dict(bundle["state"])
            state_smiles = str(bundle["smiles"])
            state_ligand_valid = dict(bundle["ligand_valid"])
            state_atom = int(bundle["atom_count"])
            anchor_mapping = _chemical_anchor_mapping(state_smiles, state_ligand_valid)
            try:
                search_started = time.perf_counter()
                search_candidates, state_search_diagnostics = _pose_search_candidates(
                    bundle["poses"], pocket_center, protein_beads, seed=int(bundle["seed"]),
                    max_candidates=self.pose_count, ligand_smiles=state_smiles,
                )
            except Exception as exc:
                stage_records.append(StageRecord(
                    "pose_search", _SCHEMA_VERSION, "blocked", message=str(exc),
                    diagnostics={"state_id": state_payload["state_id"],
                                 "status": "search_evaluation_failed", "candidates": "not_generated"}))
                continue
            finally:
                timings["search"] += time.perf_counter() - search_started
            state_search_diagnostics["chemical_anchor_mapping_status"] = str(anchor_mapping["status"])
            state_search_diagnostics["chemical_anchor_mapping"] = anchor_mapping
            state_payload["pose_search"] = dict(state_search_diagnostics)
            state_payload["poses_scored"] = 0
            search_diagnostics["raw_candidate_count"] += int(state_search_diagnostics["raw_candidate_count"])
            search_diagnostics["coarse_beam_candidate_count"] += int(
                state_search_diagnostics["coarse_beam_candidate_count"]
            )
            search_diagnostics["retained_candidate_count"] += int(state_search_diagnostics["retained_candidate_count"])
            search_diagnostics["local_minimization_candidate_count"] += int(
                state_search_diagnostics["local_minimization_candidate_count"]
            )
            search_diagnostics["local_minimization_improved_count"] += int(
                state_search_diagnostics["local_minimization_improved_count"]
            )
            if int(search_diagnostics["local_minimization_improved_count"]) > 0:
                search_diagnostics["local_minimization_status"] = "finite_difference_rigid_body_gradient_minimized"
            elif int(search_diagnostics["local_minimization_candidate_count"]) > 0:
                search_diagnostics["local_minimization_status"] = (
                    "finite_difference_rigid_body_gradient_no_improvement"
                )
            if "chemical_anchor_mapping" not in search_diagnostics:
                search_diagnostics["chemical_anchor_mapping_status"] = str(anchor_mapping["status"])
                search_diagnostics["chemical_anchor_mapping"] = anchor_mapping
            for candidate in search_candidates:
                pose_index = int(global_pose_index)
                global_pose_index += 1
                candidate_record = {"pose_index": pose_index, "state_id": state_payload["state_id"],
                                    "status": "unattempted", "reason": None}
                candidate_records.append(candidate_record)
                try:
                    pose_coords = _real_coordinate_array(candidate["coords"], label="candidate_coords", dtype=np.float32)
                    if pose_coords.shape != (state_atom, 3) or not np.isfinite(pose_coords).all():
                        raise ValueError("coordinate_topology_mismatch_or_nonfinite")
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    candidate_record.update(status="input_rejected", reason=str(exc))
                    continue
                placed_pose_coords[pose_index] = pose_coords
                try:
                    ensure_small_dense_diagnostic(
                        torch.tensor(
                            np.concatenate([protein_beads, pose_coords], axis=0),
                            dtype=torch.float32,
                        ).unsqueeze(0),
                        context="tier_beta_screening_pose_diagnostic",
                    )
                except ValueError as exc:
                    candidate_record.update(status="input_rejected", reason=f"dense_diagnostic_blocked: {exc}")
                    continue
                try:
                    scoring_started = time.perf_counter()
                    candidate_record.update(status="evaluation_failed", reason="evaluation_not_completed")
                    ffield_score, diag = _single_pose_score(
                        protein_beads, pose_coords, device=self.device, field=static_field)
                    scoring_status = str(diag.get("status") or "")
                    if scoring_status.startswith("blocked"):
                        reason = {"blocked_dense_or_reference_neighbor": "reference_nxn_blocked",
                                  "blocked_neighbor_overflow": "neighbor_overflow"}.get(scoring_status, scoring_status)
                        raise ValueError(reason)
                    mm_score = _mm_gbsa_binding_score(
                        protein_beads, pose_coords, contact_cutoff_a=self.pocket_cutoff_a,
                        ligand_elements=state_ligand_valid.get("atom_elements"))
                    if mm_score.get("status") == "blocked_chemistry_input_or_proxy_evaluation":
                        raise ValueError(f"ligand_invalid: {mm_score.get('blocked_reason')}")
                    cross_energy = float(diag.get("cross_component_energy", ffield_score))
                    mm_energy = float(mm_score.get("interaction_score_proxy", float("nan")))
                    if not math.isfinite(cross_energy) or not math.isfinite(mm_energy):
                        raise ValueError("nonfinite_score_component")
                    composite = 0.5 * cross_energy + 0.5 * mm_energy
                    if not math.isfinite(composite):
                        raise ValueError("nonfinite_composite_score")
                except Exception as exc:
                    candidate_record.update(status="evaluation_failed", reason=str(exc))
                    continue
                finally:
                    timings["scoring"] += time.perf_counter() - scoring_started
                try:
                    clashes = _clash_count(protein_beads, pose_coords)
                    chemistry_validity = _chemistry_validity_summary(state_ligand_valid, pose_coords)
                    ranking_metric = {
                        "name": "restricted_cross_component_composite_v2",
                        "receptor_representation": receptor_context["schema_version"],
                        "value": float(composite),
                        "lower_is_better": True,
                        "components": ["cross_component_lj_proxy", "mm_gbsa_interaction_proxy"],
                        "internal_energies_included": False,
                        "ligand_strain": {"status": "not_evaluated", "value": None},
                    }
                    abstention_reasons = [
                        reason
                        for reason in [
                            str(diag.get("status") or ""),
                            str(mm_score.get("blocked_reason") or ""),
                            "pose_clash_detected" if clashes > 0 else "",
                            "chemistry_validity_blocked" if not chemistry_validity["valid"] else "",
                            "restricted_tier_beta_unvalidated",
                        ]
                        if reason
                    ]

                    pose_scores.append({
                        "pose_index": pose_index,
                        "pose_rank": 0,
                        "ligand_state": state_payload,
                        "field_energy": cross_energy,
                        "mm_gbsa_energy": mm_energy,
                        "composite_score": float(composite),
                        "score_components": {
                            "cross_component_lj_proxy": cross_energy,
                            "mm_gbsa_interaction_proxy": mm_energy,
                        },
                        "pose_search": {
                            "schema_version": "tier_beta_pose_search_v1",
                            "search_strategy": state_search_diagnostics["search_strategy"],
                            "conformer_diversity": dict(state_search_diagnostics["conformer_diversity"]),
                            "conformer_count": int(state_search_diagnostics["conformer_count"]),
                            "rotatable_bond_count": int(state_search_diagnostics["rotatable_bond_count"]),
                            "retained_conformer_count": int(state_search_diagnostics["retained_conformer_count"]),
                            "retained_conformer_indices": list(state_search_diagnostics["retained_conformer_indices"]),
                            "retained_conformer_fraction": float(state_search_diagnostics["retained_conformer_fraction"]),
                            "conformer_index": int(candidate["conformer_index"]),
                            "rotation_index": int(candidate["rotation_index"]),
                            "translation_index": int(candidate["translation_index"]),
                            "translation_vector_a": list(candidate["translation_vector_a"]),
                            "coarse_score": float(candidate["coarse_score"]),
                            "coarse_score_before_local": float(candidate["coarse_score_before_local"]),
                            "coarse_score_components": dict(candidate["coarse_score_components"]),
                            "coarse_score_beam_status": state_search_diagnostics["coarse_score_beam_status"],
                            "clash_prefilter_status": state_search_diagnostics["clash_prefilter_status"],
                            "raw_candidate_count": int(state_search_diagnostics["raw_candidate_count"]),
                            "coarse_beam_candidate_count": int(state_search_diagnostics["coarse_beam_candidate_count"]),
                            "retained_candidate_count": int(state_search_diagnostics["retained_candidate_count"]),
                            "rotations_per_conformer": int(state_search_diagnostics["rotations_per_conformer"]),
                            "translation_grid_point_count": int(state_search_diagnostics["translation_grid_point_count"]),
                            "local_minimization_status": state_search_diagnostics["local_minimization_status"],
                            "local_minimization_method": state_search_diagnostics["local_minimization_method"],
                            "local_minimization_degrees_of_freedom": list(
                                state_search_diagnostics["local_minimization_degrees_of_freedom"]
                            ),
                            "local_minimization": dict(candidate["local_minimization"]),
                            "symmetry_rmsd_clustering_status": state_search_diagnostics["symmetry_rmsd_clustering_status"],
                            "chemical_anchor_mapping_status": state_search_diagnostics["chemical_anchor_mapping_status"],
                            "chemical_anchor_mapping": anchor_mapping,
                        },
                        "uncertainty": 1.0,
                        "abstention": True,
                        "abstention_reasons": abstention_reasons,
                        "pose_rmsd_to_top1_a": 0.0,
                        "pose_rmsd_to_top5_centroid_a": 0.0,
                        "clash_count": clashes,
                        "chemistry_validity": chemistry_validity,
                        "ranking_metric": ranking_metric,
                        "topology_fidelity": protein_valid.get("fidelity", ""),
                        "ligand_topology": _ligand_topology_payload(state_ligand_valid),
                        "neighbor_diagnostics": diag.get("neighbor_diagnostics", {}),
                        "claim_boundary": _CLAIM_BOUNDARY,
                        "field_diagnostics": diag,
                        "mm_gbsa_diagnostics": mm_score,
                    })
                    candidate_record.update(status="scored_successfully", reason=None, score=float(composite))
                    state_payload["poses_scored"] = int(state_payload["poses_scored"]) + 1
                except Exception as exc:
                    candidate_record.update(status="evaluation_failed", reason=str(exc))
                    continue
            search_diagnostics["states"].append(state_payload)
            for record in state_records:
                if record.get("state_id") == state_payload.get("state_id"):
                    record["poses_scored"] = int(state_payload["poses_scored"])
                    record["pose_search"] = state_payload["pose_search"]
                    break

        stage_records.append(
            StageRecord(
                stage_id="scoring_ranking",
                schema_version=_SCHEMA_VERSION,
                status="pass" if pose_scores else "blocked",
                diagnostics={"poses_scored": int(len(pose_scores)), "pose_search": search_diagnostics,
                             "candidates": candidate_records,
                             "candidate_accounting_scope": "retained_search_candidates",
                             "candidate_accounting": {status: sum(row["status"] == status for row in candidate_records)
                                for status in ("scored_successfully", "input_rejected", "evaluation_failed", "unattempted")}},
            )
        )
        if not pose_scores:
            reasons = sorted({str(row["reason"]) for row in candidate_records if row["reason"]})
            return self._fail("no_poses_scored:" + ";".join(reasons),
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom, pocket=resolved_pocket, poses_gen=poses_generated,
                              typed_input=typed_input, stage_records=stage_records)

        pose_scores.sort(key=lambda x: float(x["composite_score"]))
        for rank, row in enumerate(pose_scores, start=1):
            row["pose_rank"] = rank

        clustering_diagnostics = _annotate_state_scoped_pose_rmsd(
            pose_scores,
            placed_pose_coords,
            default_smiles=ligand_smiles,
            cluster_threshold_a=2.0,
            centroid_limit=5,
        )
        search_diagnostics["symmetry_rmsd_clustering_status"] = clustering_diagnostics["status"]
        search_diagnostics["symmetry_mapping_count"] = int(clustering_diagnostics["symmetry_mapping_count"])
        search_diagnostics["symmetry_cluster_count"] = int(clustering_diagnostics["cluster_count"])
        search_diagnostics["symmetry_state_cluster_count"] = int(clustering_diagnostics["state_cluster_count"])
        search_diagnostics["cross_state_rmsd_computed"] = False
        for row in pose_scores:
            row["pose_search"]["symmetry_rmsd_clustering_status"] = clustering_diagnostics["status"]
            row["pose_search"]["symmetry_mapping_count"] = int(clustering_diagnostics["symmetry_mapping_count"])
            row["pose_search"]["symmetry_cluster_count"] = int(clustering_diagnostics["cluster_count"])
            row["pose_search"]["symmetry_state_cluster_count"] = int(clustering_diagnostics["state_cluster_count"])
            row["pose_search"]["cross_state_rmsd_computed"] = False

        top_k_poses = pose_scores[:self.top_k]
        for row in top_k_poses:
            coordinates = placed_pose_coords[int(row["pose_index"])].tolist()
            coordinate_payload = {"coords_a": coordinates, "coordinate_frame": "receptor_frame_no_alignment",
                                  "coordinate_smiles": row["ligand_state"]["smiles"],
                                  "ligand_topology": row["ligand_topology"]}
            row["scored_pose"] = {**coordinate_payload, "sha256": hashlib.sha256(
                json.dumps(coordinate_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()}
        stage_records.append(
            StageRecord(
                stage_id="top_k_refine",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={
                    "top_k": int(self.top_k),
                    "retained_pose_count": int(len(top_k_poses)),
                    "rmsd_clustering": clustering_diagnostics,
                },
            )
        )
        best_score = float(top_k_poses[0]["composite_score"])
        best_pose_idx = int(top_k_poses[0]["pose_index"])
        best_pose_coords = placed_pose_coords[best_pose_idx]
        benchmark_metric_summary = _benchmark_metric_summary_from_pose_scores(pose_scores)

        stability_drift, stab_diag = _run_stability_simulation(
            protein_beads, best_pose_coords,
            device=self.device,
            steps=self.stability_steps,
            dt=self.stability_dt,
            temp_k=self.stability_temp_k,
            seed=self.seed,
        )
        # Wall time is operational evidence, not a deterministic replay input.
        stability_elapsed = stab_diag.pop("elapsed_seconds", None)
        stability_ok = stab_diag.get("stable")
        stability_run = int(stab_diag.get("steps_run", 0))
        stability_not_run = stab_diag.get("status") == "not_run"
        stability_pass = stability_ok is True
        stage_records.append(
            StageRecord(
                stage_id="stability_simulation",
                schema_version=_SCHEMA_VERSION,
                status="not_run" if stability_not_run else "pass" if stability_pass else "blocked",
                failure_code=(FailureCode.NONE.value if stability_not_run or stability_pass
                              else FailureCode.STABILITY_FAILED.value),
                diagnostics={"optional": True, **stab_diag},
            )
        )

        manifest = self._build_manifest(
            protein_seq=protein_seq,
            protein_residues=protein_coords.shape[0],
            ligand_smiles=ligand_smiles,
            ligand_atom=ligand_atom,
            ligand_valid_flag=ligand_valid["valid"],
            pocket_indices=resolved_pocket,
            poses_generated=poses_generated,
            poses_scored=len(pose_scores),
            top_k=self.top_k,
            best_score=best_score,
            best_rank=1,
            stability_steps=stability_run,
            stability_drift=stability_drift,
            stability_ok=stability_ok,
            stability_diagnostics=stab_diag,
            pose_scores=pose_scores,
            benchmark_metric_summary=benchmark_metric_summary,
            protein_valid=protein_valid,
            ligand_valid=ligand_valid,
            stage_records=stage_records,
            typed_input=typed_input,
        )
        if not verify_screening_manifest(manifest):
            return self._fail("unsigned_result_manifest",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              pocket=resolved_pocket,
                              poses_gen=poses_generated,
                              typed_input=typed_input,
                              stage_records=stage_records)

        computation_complete = bool(
            ligand_valid["claim_safe"]
            and protein_valid["valid"]
            and (self.stability_steps == 0 or stability_ok is True)
            and pose_scores
            and math.isfinite(best_score)
            and manifest.get("signature")
        )
        blocked = ""
        if not computation_complete:
            parts = []
            if not ligand_valid["claim_safe"]:
                parts.append(f"ligand_not_claim_safe:{';'.join(ligand_valid['blockers'])}")
            if self.stability_steps > 0 and stability_ok is not True:
                parts.append("stability_failed")
            if not pose_scores:
                parts.append("no_poses_scored")
            if not manifest.get("signature"):
                parts.append("unsigned_result_manifest")
            blocked = ";".join(parts) or "screening_claim_not_safe"
        failure_code = failure_code_for_reason(blocked)
        typed_output = TierBetaScreeningOutput(
            ok=computation_complete,
            failure_code=failure_code,
            blocked_reason=blocked,
            protein_residue_count=int(protein_coords.shape[0]),
            ligand_atom_count=int(ligand_atom),
            poses_generated=int(poses_generated),
            poses_scored=int(len(pose_scores)),
            top_k=int(self.top_k),
            manifest_hash=str(manifest["content_hash"]),
        )

        return TierBetaScreeningResult(
            ok=computation_complete,
            blocked_reason=blocked,
            claim_scope=_CLAIM_SCOPE,
            schema_version=_SCHEMA_VERSION,
            protein_sequence=protein_seq,
            protein_residue_count=protein_coords.shape[0],
            ligand_smiles=ligand_smiles,
            ligand_atom_count=ligand_atom,
            ligand_valid=ligand_valid["valid"],
            pocket_residue_indices=resolved_pocket,
            pocket_residue_count=len(resolved_pocket),
            poses_generated=poses_generated,
            poses_scored=len(pose_scores),
            top_k=self.top_k,
            best_score=best_score,
            best_rank=1,
            stability_steps_run=stability_run,
            stability_drift_A=stability_drift,
            stability_ok=stability_ok,
            manifest_hash=manifest["content_hash"],
            claim_metadata=manifest["claim_metadata"],
            pose_scores=top_k_poses,
            diagnostics={
                "receptor_proxy": receptor_context,
                "execution_observations": {
                    "stability_elapsed_seconds": stability_elapsed,
                    "timing_scope": "stability_invocation_including_endpoint_analysis",
                    "evidence_kind": "wall_clock_observation",
                },
                "config": {
                    "pocket_cutoff_a": self.pocket_cutoff_a,
                    "pose_count": self.pose_count,
                    "top_k": self.top_k,
                    "stability_steps": self.stability_steps,
                    "stability_dt": self.stability_dt,
                    "stability_temp_k": self.stability_temp_k,
                    "seed": self.seed,
                },
                "protein_valid": protein_valid,
                "ligand_valid": ligand_valid,
                "ligand_state_ensemble": {
                    "schema_version": "tier_beta_ligand_state_ensemble_v1",
                    "status": _LIGAND_STATE_ENSEMBLE_STATUS,
                    "state_count": int(len(ligand_states)),
                    "scored_state_count": int(len(state_pose_bundles)),
                    "states": state_records,
                },
                "pose_search_aggregation": search_diagnostics,
                "benchmark_metric_summary": benchmark_metric_summary,
                "result_signed": bool(manifest.get("signature")),
                "blocked_claims": _BLOCKED_CLAIMS,
            },
            result_manifest=manifest,
            failure_code=failure_code,
            stage_records=[stage.to_dict() for stage in stage_records],
            typed_input=typed_input.to_dict(),
            typed_output=typed_output.to_dict(),
        )

    def _fail(
        self,
        reason: str,
        protein_seq: str = "",
        protein_residues: int = 0,
        ligand_smiles: str = "",
        *,
        ligand_atom: int = 0,
        pocket: list[int] | None = None,
        poses_gen: int = 0,
        typed_input: TierBetaScreeningInput | None = None,
        stage_records: list[StageRecord] | None = None,
    ) -> TierBetaScreeningResult:
        failure_code = failure_code_for_reason(reason)
        failed_stage = StageRecord(
            stage_id="fail_closed",
            schema_version=_SCHEMA_VERSION,
            status="blocked",
            failure_code=failure_code,
            message=str(reason),
        )
        records = [*(stage_records or []), failed_stage]
        typed_input_payload = typed_input.to_dict() if typed_input is not None else {}
        manifest = sign_screening_manifest({
            "schema_version": _SCHEMA_VERSION,
            "claim_scope": _CLAIM_SCOPE,
            "status": "failed",
            "failure_code": failure_code,
            "blocked_reason": str(reason),
            "protein": {"residue_count": int(protein_residues)},
            "ligand": {"smiles": ligand_smiles, "atom_count": int(ligand_atom)},
            "poses": {"generated": int(poses_gen), "scored": 0},
            "ranking": {"best_score": None, "best_rank": None, "top_k": self.top_k},
            "pose_scores": [],
            "stage_records": [record.to_dict() for record in records],
            "typed_input": typed_input_payload,
            "claim_metadata": {"claim_safe": False, "blocked_reason": str(reason),
                               "blocked_claims": list(_BLOCKED_CLAIMS)},
            "claim_boundary": _CLAIM_BOUNDARY,
        })
        typed_output = TierBetaScreeningOutput(
            ok=False,
            failure_code=failure_code,
            blocked_reason=reason,
            protein_residue_count=int(protein_residues),
            ligand_atom_count=int(ligand_atom),
            poses_generated=int(poses_gen),
            poses_scored=0,
            top_k=int(self.top_k),
            manifest_hash=manifest["content_hash"],
        )
        return TierBetaScreeningResult(
            ok=False,
            blocked_reason=reason,
            claim_scope=_CLAIM_SCOPE,
            schema_version=_SCHEMA_VERSION,
            protein_sequence=protein_seq,
            protein_residue_count=protein_residues,
            ligand_smiles=ligand_smiles,
            ligand_atom_count=ligand_atom,
            ligand_valid=False,
            pocket_residue_indices=pocket or [],
            pocket_residue_count=len(pocket or []),
            poses_generated=poses_gen,
            poses_scored=0,
            top_k=self.top_k,
            best_score=None,
            best_rank=-1,
            stability_steps_run=0,
            stability_drift_A=None,
            stability_ok=False,
            manifest_hash=manifest["content_hash"],
            claim_metadata=manifest["claim_metadata"],
            result_manifest=manifest,
            failure_code=failure_code,
            stage_records=[stage.to_dict() for stage in records],
            typed_input=typed_input_payload,
            typed_output=typed_output.to_dict(),
        )

    def _build_manifest(
        self,
        *,
        protein_seq: str,
        protein_residues: int,
        ligand_smiles: str,
        ligand_atom: int,
        ligand_valid_flag: bool,
        pocket_indices: list[int],
        poses_generated: int,
        poses_scored: int,
        top_k: int,
        best_score: float,
        best_rank: int,
        stability_steps: int,
        stability_drift: float | None,
        stability_ok: bool | None,
        stability_diagnostics: dict[str, Any],
        pose_scores: list[dict[str, Any]],
        protein_valid: dict[str, Any],
        ligand_valid: dict[str, Any],
        stage_records: list[StageRecord],
        typed_input: TierBetaScreeningInput,
        benchmark_metric_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_screening_manifest(
            protein_seq=protein_seq,
            protein_residues=protein_residues,
            ligand_smiles=ligand_smiles,
            ligand_atom=ligand_atom,
            ligand_valid_flag=ligand_valid_flag,
            pocket_indices=pocket_indices,
            poses_generated=poses_generated,
            poses_scored=poses_scored,
            top_k=top_k,
            best_score=best_score,
            best_rank=best_rank,
            stability_steps=stability_steps,
            stability_drift=stability_drift,
            stability_ok=stability_ok,
            stability_diagnostics=stability_diagnostics,
            pose_scores=pose_scores,
            benchmark_metric_summary=benchmark_metric_summary,
            protein_valid=protein_valid,
            ligand_valid=ligand_valid,
            stage_records=stage_records,
            typed_input=typed_input,
            device=str(self.device),
            seed=int(self.seed),
        )


def make_screening(*, device: str = "cpu", **kwargs: Any) -> TierBetaScreening:
    return TierBetaScreening(device=device, **kwargs)
