from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from betelgeuze_engine.biodiscovery.contracts import CLAIM_SCOPE, SCHEMA_VERSION, StageRecord, TierBetaScreeningInput
from betelgeuze_engine.biodiscovery.ligand_prep import ligand_topology_payload

LOCAL_MANIFEST_KEY = "local-tier-beta-vertical-slice-signing-key"
CLAIM_BOUNDARY = (
    "Restricted local Tier-beta structure-based ligand screening vertical slice. "
    "Runs preparation, topology checks, pocket resolution, pose scoring, top-K refinement, "
    "and optional short stability simulation on supplied local inputs only. It is not a "
    "calibrated affinity, FEP parity, wetlab hit, AlphaFold parity, or broad platform claim."
)
BLOCKED_CLAIMS = [
    "calibrated_affinity",
    "fep_parity",
    "wetlab_hit",
    "broad_platform",
    "alphafold_parity",
]


def build_screening_manifest(
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
    device: str,
    seed: int,
    benchmark_metric_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "claim_scope": CLAIM_SCOPE,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protein": {
            "residue_count": protein_residues,
            "sequence_length": len(str(protein_seq)),
        },
        "ligand": {
            "smiles": str(ligand_smiles),
            "atom_count": ligand_atom,
            "valid": bool(ligand_valid_flag),
        },
        "pocket": {
            "indices": [int(i) for i in pocket_indices],
            "count": len(pocket_indices),
        },
        "poses": {
            "generated": poses_generated,
            "scored": poses_scored,
        },
        "ranking": {
            "top_k": top_k,
            "best_score": float(best_score),
            "best_rank": int(best_rank),
        },
        "stability": {
            "steps_run": stability_steps,
            "drift_A": float(stability_drift),
            "ok": bool(stability_ok),
            "diagnostics": stability_diagnostics,
        },
        "precision": {
            "device": str(device),
            "seed": int(seed),
        },
        "pose_scores": pose_scores,
        "benchmark_metric_summary": benchmark_metric_summary or {},
        "blocked_claims": list(BLOCKED_CLAIMS),
        "claim_boundary": CLAIM_BOUNDARY,
        "typed_input": typed_input.to_dict(),
        "stage_records": [stage.to_dict() for stage in stage_records],
    }
    scientific_claim_safe = False
    parts = ["restricted_tier_beta_unvalidated"]
    if not ligand_valid_flag:
        parts.append("ligand_invalid")
    if not bool(ligand_valid.get("claim_safe", False)):
        parts.append("ligand_not_claim_safe")
    if not stability_ok:
        parts.append("stability_failed")
    if poses_scored <= 0:
        parts.append("no_poses_scored")
    blocked = ";".join(parts)

    claim_metadata = {
        "schema_version": SCHEMA_VERSION,
        "claim_scope": CLAIM_SCOPE,
        "claim_safe": scientific_claim_safe,
        "blocked_reason": blocked,
        "topology_fidelity": str(protein_valid.get("fidelity") or "unknown"),
        "ligand_topology_valid": bool(ligand_valid_flag),
        "ligand_topology": ligand_topology_payload(ligand_valid),
        "hbond_evidence_status": "not_assessed",
        "force_residual_applied": False,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "benchmark_metric_summary": benchmark_metric_summary or {},
        "claim_boundary": CLAIM_BOUNDARY,
    }
    payload["claim_metadata"] = claim_metadata
    replay_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"timestamp_utc", "content_hash", "signature"}
    }
    payload["replay_hash"] = hashlib.sha256(
        json.dumps(replay_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    payload["content_hash"] = content_hash
    payload["signature_algorithm"] = "hmac-sha256"
    payload["signature_key_id"] = "local-tier-beta"
    signature_payload = dict(payload)
    signature = hmac.new(
        LOCAL_MANIFEST_KEY.encode("utf-8"),
        json.dumps(
            signature_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    payload["signature"] = signature

    return payload
