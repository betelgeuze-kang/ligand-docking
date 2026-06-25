from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from betelgeuze_engine.biodiscovery import TierBetaScreening, TierBetaScreeningResult

RUNNER_ADAPTER_SCHEMA_VERSION = "tier_beta_runner_adapter_v1"


@dataclass(frozen=True)
class TierBetaRunnerRequest:
    protein_input: str
    ligand_input: str
    pocket_residue_indices: list[int] | None = None
    device: str = "cpu"
    pose_count: int = 8
    top_k: int = 3
    stability_steps: int = 0
    seed: int = 42
    schema_version: str = RUNNER_ADAPTER_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int_param(params: dict[str, Any], key: str, default: int, *, minimum: int = 0) -> int:
    try:
        value = int(params.get(key, default))
    except (TypeError, ValueError):
        value = int(default)
    return int(max(minimum, value))


def parse_tier_beta_runner_payload(payload: dict[str, Any]) -> TierBetaRunnerRequest:
    params = payload.get("runner_profile_params")
    if not isinstance(params, dict):
        params = payload
    pocket = params.get("pocket_residue_indices")
    pocket_residue_indices = (
        [int(value) for value in pocket]
        if isinstance(pocket, list) and all(str(value).strip() for value in pocket)
        else None
    )
    metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
    return TierBetaRunnerRequest(
        protein_input=str(params.get("protein_input") or params.get("pdb_content") or ""),
        ligand_input=str(params.get("ligand_input") or params.get("smiles") or ""),
        pocket_residue_indices=pocket_residue_indices,
        device=str(params.get("device") or "cpu"),
        pose_count=_int_param(params, "pose_count", 8, minimum=1),
        top_k=_int_param(params, "top_k", 3, minimum=1),
        stability_steps=_int_param(params, "stability_steps", 0, minimum=0),
        seed=_int_param(params, "seed", 42, minimum=0),
        metadata=dict(metadata),
    )


def run_tier_beta_vertical_slice_from_payload(payload: dict[str, Any]) -> TierBetaScreeningResult:
    request = parse_tier_beta_runner_payload(payload)
    service = TierBetaScreening(
        device=request.device,
        pose_count=request.pose_count,
        top_k=request.top_k,
        stability_steps=request.stability_steps,
        seed=request.seed,
    )
    return service.screen(
        protein_input=request.protein_input,
        ligand_input=request.ligand_input,
        pocket_residue_indices=request.pocket_residue_indices,
    )
