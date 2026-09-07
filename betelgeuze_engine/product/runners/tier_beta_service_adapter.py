from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from betelgeuze_engine.biodiscovery import TierBetaScreening, TierBetaScreeningResult
from betelgeuze_product.tier_beta_vertical_slice import build_tier_beta_request_from_api

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


def parse_tier_beta_runner_payload(payload: dict[str, Any]) -> TierBetaRunnerRequest:
    params = payload.get("runner_profile_params")
    if not isinstance(params, dict):
        params = payload
    request = build_tier_beta_request_from_api({"runner_profile_params": params})
    metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
    return TierBetaRunnerRequest(
        protein_input=request["protein_input"],
        ligand_input=request["ligand_input"],
        pocket_residue_indices=request["pocket_residue_indices"],
        device=str(params.get("device") or "cpu"),
        pose_count=request["pose_count"],
        top_k=request["top_k"],
        stability_steps=request["stability_steps"],
        seed=request["seed"],
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
