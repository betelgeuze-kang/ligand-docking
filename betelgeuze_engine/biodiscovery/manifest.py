from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from dataclasses import asdict, is_dataclass
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from betelgeuze_engine.biodiscovery.contracts import StageRecord, TierBetaScreeningInput

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
_HASH_FIELDS = frozenset({"replay_hash", "content_hash", "signature"})
_LOCAL_INTEGRITY_SCOPE = "local_integrity_only_not_external_authority"


def normalize_manifest_json(value: Any) -> Any:
    """Build the finite JSON representation that will actually be published."""
    if is_dataclass(value) and not isinstance(value, type):
        return normalize_manifest_json(asdict(value))
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("manifest_object_keys_must_be_strings")
        return {key: normalize_manifest_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_manifest_json(item) for item in value]
    raise TypeError(f"unsupported_manifest_value:{type(value).__name__}")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def _without_operational_timings(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_operational_timings(item)
            for key, item in value.items()
            if key != "execution_observations"
            and key != "elapsed_seconds"
            and not key.endswith("_elapsed_seconds")
        }
    if isinstance(value, list):
        return [_without_operational_timings(item) for item in value]
    return value


def _replay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _without_operational_timings({
        key: value for key, value in payload.items()
        if key not in _HASH_FIELDS and key != "timestamp_utc"
    })


def sign_screening_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Sign a finite snapshot; the published local key grants no external authority."""
    if not isinstance(payload, dict):
        raise TypeError("manifest_must_be_an_object")
    signed = normalize_manifest_json({
        key: value for key, value in payload.items() if key not in _HASH_FIELDS
    })
    signed.update({
        "manifest_integrity_version": 2,
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": "local-tier-beta",
        "signature_scope": _LOCAL_INTEGRITY_SCOPE,
    })
    signed["replay_hash"] = hashlib.sha256(_canonical_bytes(_replay_payload(signed))).hexdigest()
    signed["content_hash"] = hashlib.sha256(_canonical_bytes(signed)).hexdigest()
    signed["signature"] = hmac.new(
        LOCAL_MANIFEST_KEY.encode("utf-8"), _canonical_bytes(signed), hashlib.sha256,
    ).hexdigest()
    return signed


def verify_screening_manifest(manifest: Any) -> bool:
    """Verify replay, content and local HMAC integrity, including after JSON reload."""
    if not isinstance(manifest, dict):
        return False
    try:
        # Reject a nonfinite received artifact instead of silently repairing it.
        _canonical_bytes(manifest)
        if (
            manifest.get("manifest_integrity_version") != 2
            or manifest.get("signature_algorithm") != "hmac-sha256"
            or manifest.get("signature_key_id") != "local-tier-beta"
            or manifest.get("signature_scope") != _LOCAL_INTEGRITY_SCOPE
        ):
            return False
        expected = sign_screening_manifest(manifest)
        return all(
            isinstance(manifest.get(key), str)
            and hmac.compare_digest(manifest[key], expected[key])
            for key in _HASH_FIELDS
        )
    except (TypeError, ValueError, OverflowError):
        return False


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
    stability_drift: float | None,
    stability_ok: bool | None,
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
    from betelgeuze_engine.biodiscovery.contracts import CLAIM_SCOPE, SCHEMA_VERSION
    from betelgeuze_engine.biodiscovery.ligand_prep import ligand_topology_payload

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
            "status": stability_diagnostics.get("status", "unknown"),
            "drift_A": float(stability_drift) if stability_drift is not None else None,
            "ok": stability_ok,
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
    if stability_diagnostics.get("status") == "not_run":
        parts.append("stability_not_measured")
    elif stability_ok is not True:
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
    return sign_screening_manifest(payload)
