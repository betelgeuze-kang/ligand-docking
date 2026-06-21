from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

from betelgeuze_engine.biodiscovery.contracts import (
    CLAIM_SCOPE,
    SCHEMA_VERSION,
    FailureCode,
    StageRecord,
    TierBetaScreeningInput,
    TierBetaScreeningOutput,
    failure_code_for_reason,
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
    chemistry_validity_summary as _chemistry_validity_summary,
    clash_count as _clash_count,
    generate_conformers as _generate_conformers,
    place_pose_in_pocket as _place_pose_in_pocket,
    pose_rmsd as _pose_rmsd,
    resolve_pocket_indices as _resolve_pocket_indices,
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
    _build_atom_types,
)
_COMPAT_MANIFEST_HELPERS = (
    _LOCAL_MANIFEST_KEY,
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
    best_score: float
    best_rank: int
    stability_steps_run: int
    stability_drift_A: float
    stability_ok: bool
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
        self.pocket_cutoff_a = float(pocket_cutoff_a)
        self.pose_count = int(max(1, int(pose_count)))
        self.top_k = int(max(1, int(top_k)))
        self.stability_steps = int(max(0, int(stability_steps)))
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
        typed_input = self._typed_input(str(protein_input or ""), str(ligand_input or ""))
        stage_records: list[StageRecord] = []
        if not protein_input or not str(protein_input).strip():
            return self._fail("empty_protein_input", typed_input=typed_input)

        try:
            protein_coords, protein_seq = _resolve_protein_input(str(protein_input))
        except ValueError as e:
            return self._fail(f"protein_parse_failed: {e}", typed_input=typed_input)
        stage_records.append(
            StageRecord(
                stage_id="protein_preparation",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"residue_count": int(protein_coords.shape[0])},
            )
        )

        try:
            resolved_ligand = _resolve_ligand_input(str(ligand_input))
            ligand_smiles = resolved_ligand.smiles
        except ValueError as e:
            return self._fail(f"ligand_parse_failed: {e}", typed_input=typed_input)

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

        poses = _generate_conformers(ligand_smiles, self.pose_count, self.seed)
        if poses is None:
            return self._fail("ligand_conformer_generation_failed",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              typed_input=typed_input,
                              stage_records=stage_records)

        poses_generated = poses.shape[0]
        if poses_generated == 0:
            return self._fail("zero_conformers_generated",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              typed_input=typed_input,
                              stage_records=stage_records)
        stage_records.append(
            StageRecord(
                stage_id="pose_ensemble",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"poses_generated": int(poses_generated), "seed": int(self.seed)},
            )
        )

        ligand_center = poses[0].mean(axis=0) if poses_generated > 0 else None
        resolved_pocket = (
            list(pocket_residue_indices)
            if pocket_residue_indices
            else _resolve_pocket_indices(protein_coords, ligand_center, self.pocket_cutoff_a)
        )
        if any(int(idx) < 0 or int(idx) >= int(protein_coords.shape[0]) for idx in resolved_pocket):
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
                diagnostics={"pocket_residue_indices": [int(idx) for idx in resolved_pocket]},
            )
        )

        protein_beads = _virtual_protein_coords(protein_coords)
        pocket_center = protein_coords[resolved_pocket].mean(axis=0)

        pose_scores: list[dict[str, Any]] = []
        placed_pose_coords: dict[int, np.ndarray] = {}
        for i in range(min(poses_generated, self.pose_count)):
            pose_coords = _place_pose_in_pocket(poses[i], pocket_center)
            if pose_coords.shape[0] != ligand_atom:
                continue
            placed_pose_coords[i] = pose_coords
            try:
                ensure_small_dense_diagnostic(
                    torch.tensor(
                        np.concatenate([protein_beads, pose_coords], axis=0),
                        dtype=torch.float32,
                    ).unsqueeze(0),
                    context="tier_beta_screening_pose_diagnostic",
                )
            except ValueError as exc:
                return self._fail(f"dense_diagnostic_blocked: {exc}",
                                  protein_seq, protein_coords.shape[0], ligand_smiles,
                                  ligand_atom=ligand_atom,
                                  pocket=resolved_pocket,
                                  poses_gen=poses_generated,
                                  typed_input=typed_input,
                                  stage_records=stage_records)
            ffield_score, diag = _single_pose_score(protein_beads, pose_coords, device=self.device)
            scoring_status = str(diag.get("status") or "")
            if scoring_status == "blocked_neighbor_overflow":
                return self._fail("neighbor_overflow",
                                  protein_seq, protein_coords.shape[0], ligand_smiles,
                                  ligand_atom=ligand_atom,
                                  pocket=resolved_pocket,
                                  poses_gen=poses_generated,
                                  typed_input=typed_input,
                                  stage_records=stage_records)
            if scoring_status == "blocked_dense_or_reference_neighbor":
                return self._fail("reference_nxn_blocked",
                                  protein_seq, protein_coords.shape[0], ligand_smiles,
                                  ligand_atom=ligand_atom,
                                  pocket=resolved_pocket,
                                  poses_gen=poses_generated,
                                  typed_input=typed_input,
                                  stage_records=stage_records)
            mm_score = _mm_gbsa_binding_score(protein_beads, pose_coords,
                                              contact_cutoff_a=self.pocket_cutoff_a)

            composite = float(diag.get("total_energy", ffield_score))
            mm_energy = float(
                mm_score.get(
                    "deltaG_mm_gbsa_kcal_mol",
                    mm_score.get("binding_energy_kcal_mol", float("inf")),
                )
            )
            if math.isfinite(mm_energy):
                composite = 0.5 * composite + 0.5 * mm_energy
            clashes = _clash_count(protein_beads, pose_coords)
            chemistry_validity = _chemistry_validity_summary(ligand_valid, pose_coords)
            ranking_metric = {
                "name": "restricted_local_composite_score_v1",
                "value": float(composite),
                "lower_is_better": True,
                "components": ["guarded_forcefield_energy", "mm_gbsa_proxy_energy"],
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
                "pose_index": i,
                "pose_rank": 0,
                "field_energy": float(diag.get("total_energy", float("inf"))),
                "mm_gbsa_energy": mm_energy,
                "composite_score": float(composite),
                "score_components": {
                    "guarded_forcefield_energy": float(diag.get("total_energy", float("inf"))),
                    "mm_gbsa_proxy_energy": mm_energy,
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
                "ligand_topology": _ligand_topology_payload(ligand_valid),
                "neighbor_diagnostics": diag.get("neighbor_diagnostics", {}),
                "claim_boundary": _CLAIM_BOUNDARY,
                "field_diagnostics": diag,
                "mm_gbsa_diagnostics": mm_score,
            })

        if not pose_scores:
            return self._fail("no_poses_scored",
                              protein_seq, protein_coords.shape[0], ligand_smiles,
                              ligand_atom=ligand_atom,
                              pocket=resolved_pocket,
                              poses_gen=poses_generated,
                              typed_input=typed_input,
                              stage_records=stage_records)
        stage_records.append(
            StageRecord(
                stage_id="scoring_ranking",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"poses_scored": int(len(pose_scores))},
            )
        )

        pose_scores.sort(key=lambda x: float(x["composite_score"]))
        for rank, row in enumerate(pose_scores, start=1):
            row["pose_rank"] = rank

        top_k_poses = pose_scores[:self.top_k]
        top1_coords = placed_pose_coords[int(top_k_poses[0]["pose_index"])]
        top5_indices = [int(row["pose_index"]) for row in pose_scores[: min(5, len(pose_scores))]]
        top5_centroid = np.mean([placed_pose_coords[idx] for idx in top5_indices], axis=0)
        for row in pose_scores:
            coords_for_row = placed_pose_coords[int(row["pose_index"])]
            row["pose_rmsd_to_top1_a"] = _pose_rmsd(coords_for_row, top1_coords)
            row["pose_rmsd_to_top5_centroid_a"] = _pose_rmsd(coords_for_row, top5_centroid)
        stage_records.append(
            StageRecord(
                stage_id="top_k_refine",
                schema_version=_SCHEMA_VERSION,
                status="pass",
                diagnostics={"top_k": int(self.top_k), "retained_pose_count": int(len(top_k_poses))},
            )
        )
        best_score = float(top_k_poses[0]["composite_score"])
        best_pose_idx = int(top_k_poses[0]["pose_index"])
        best_pose_coords = placed_pose_coords[best_pose_idx]

        stability_drift = 0.0
        stability_ok = True
        stability_run = 0
        stab_diag: dict[str, Any] = {
            "stable": True,
            "drift_A": 0.0,
            "steps_run": 0,
            "energy_drift": 0.0,
            "constraints": {
                "coordinate_clamp_box_a": float(_DEFAULT_BOX_SIZE),
                "protein_ligand_constraints": "none_stability_not_requested",
            },
            "pbc_enabled": True,
            "pbc_box_a": float(_DEFAULT_BOX_SIZE),
            "thermostat": {
                "type": "not_run",
                "temperature_k": float(self.stability_temp_k),
            },
            "restart_reproducible": True,
            "restart_seed": int(self.seed),
        }
        if self.stability_steps > 0:
            drift, stab_diag = _run_stability_simulation(
                protein_beads, best_pose_coords,
                device=self.device,
                steps=self.stability_steps,
                dt=self.stability_dt,
                temp_k=self.stability_temp_k,
                seed=self.seed,
            )
            stability_drift = drift
            stability_ok = bool(stab_diag.get("stable", False))
            stability_run = self.stability_steps
        stage_records.append(
            StageRecord(
                stage_id="stability_simulation",
                schema_version=_SCHEMA_VERSION,
                status="pass" if stability_ok else "blocked",
                failure_code=FailureCode.NONE.value if stability_ok else FailureCode.STABILITY_FAILED.value,
                diagnostics={
                    "steps_run": int(stability_run),
                    "drift_A": float(stability_drift),
                    "optional": True,
                    **stab_diag,
                },
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
            protein_valid=protein_valid,
            ligand_valid=ligand_valid,
            stage_records=stage_records,
            typed_input=typed_input,
        )
        if not isinstance(manifest, dict) or not manifest.get("signature") or not manifest.get("content_hash"):
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
            and stability_ok
            and pose_scores
            and math.isfinite(best_score)
            and manifest.get("signature")
        )
        blocked = ""
        if not computation_complete:
            parts = []
            if not ligand_valid["claim_safe"]:
                parts.append(f"ligand_not_claim_safe:{';'.join(ligand_valid['blockers'])}")
            if not stability_ok:
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
        typed_output = TierBetaScreeningOutput(
            ok=False,
            failure_code=failure_code,
            blocked_reason=reason,
            protein_residue_count=int(protein_residues),
            ligand_atom_count=int(ligand_atom),
            poses_generated=int(poses_gen),
            poses_scored=0,
            top_k=int(self.top_k),
            manifest_hash="",
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
            best_score=float("inf"),
            best_rank=-1,
            stability_steps_run=0,
            stability_drift_A=float("inf"),
            stability_ok=False,
            manifest_hash="",
            claim_metadata={"claim_safe": False, "blocked_reason": reason},
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
        stability_drift: float,
        stability_ok: bool,
        stability_diagnostics: dict[str, Any],
        pose_scores: list[dict[str, Any]],
        protein_valid: dict[str, Any],
        ligand_valid: dict[str, Any],
        stage_records: list[StageRecord],
        typed_input: TierBetaScreeningInput,
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
            protein_valid=protein_valid,
            ligand_valid=ligand_valid,
            stage_records=stage_records,
            typed_input=typed_input,
            device=str(self.device),
            seed=int(self.seed),
        )


def make_screening(*, device: str = "cpu", **kwargs: Any) -> TierBetaScreening:
    return TierBetaScreening(device=device, **kwargs)
