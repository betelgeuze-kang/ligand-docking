from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch

REQUIRED_CLAIM_METADATA_KEYS = (
    "topology_fidelity",
    "ligand_topology_valid",
    "hbond_evidence_status",
    "force_residual_applied",
    "claim_safe",
    "blocked_reason",
)

REQUIRED_FORCE_TERM_CLAIM_KEYS = (
    "force_term_name",
    "force_term_status",
)

BOUNDED_CORRECTION_CLAIM_KEYS = (
    "force_term_policy_caps",
    "force_term_policy_caps_ready",
    "force_term_observed_caps_ready",
    "force_term_bounded_correction_ready",
    "force_term_abs_energy_within_cap",
    "force_term_force_norm_within_cap",
)


def _default_claim_metadata() -> dict[str, Any]:
    return {
        "topology_fidelity": "not_assessed",
        "ligand_topology_valid": False,
        "hbond_evidence_status": "not_assessed",
        "force_residual_applied": False,
        "claim_safe": False,
        "blocked_reason": "term_result_unscoped",
    }


@dataclass
class TermResult:
    """Energy, force, and metadata result returned by every product force term."""

    energy: torch.Tensor
    forces: torch.Tensor
    diagnostics: dict[str, Any] = field(default_factory=dict)
    claim_metadata: dict[str, Any] = field(default_factory=_default_claim_metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy": self.energy.detach().cpu().tolist(),
            "forces_shape": list(self.forces.shape),
            "diagnostics": dict(self.diagnostics),
            "claim_metadata": dict(self.claim_metadata),
        }


@dataclass
class EnergyForces:
    energy: torch.Tensor
    forces: torch.Tensor
    terms: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    claim_metadata: dict[str, Any] = field(default_factory=_default_claim_metadata)


def _missing_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def term_result_requests_bounded_correction_validation(result: TermResult) -> bool:
    metadata = dict(result.claim_metadata)
    diagnostics = dict(result.diagnostics)
    return bool(
        metadata.get("force_term_bounded_correction_required") is True
        or diagnostics.get("force_term_bounded_correction_required") is True
        or "force_term_policy_caps" in metadata
        or "force_term_policy_caps" in diagnostics
        or "force_term_bounded_correction_ready" in metadata
        or "force_term_bounded_correction_ready" in diagnostics
    )


def validate_term_result_contract(
    *,
    name: str,
    result: TermResult,
    coords: torch.Tensor,
    require_bounded_correction: bool | None = None,
) -> None:
    """Validate the product force-term result contract before aggregation."""

    expected_energy_shape = (int(coords.shape[0]),)
    if tuple(result.energy.shape) != expected_energy_shape:
        raise ValueError(
            f"force term {name} returned energy with wrong shape: "
            f"{tuple(result.energy.shape)} != {expected_energy_shape}"
        )
    if result.forces.shape != coords.shape:
        raise ValueError(f"force term {name} returned forces with wrong shape")
    if not torch.isfinite(result.energy).all():
        raise ValueError(f"force term {name} returned nonfinite energy")
    if not torch.isfinite(result.forces).all():
        raise ValueError(f"force term {name} returned nonfinite forces")

    diagnostic_term = str(result.diagnostics.get("term") or "")
    diagnostic_status = str(result.diagnostics.get("status") or "")
    if diagnostic_term != name:
        raise ValueError(f"force term {name} returned mismatched diagnostic term: {diagnostic_term}")
    if not diagnostic_status:
        raise ValueError(f"force term {name} returned missing diagnostic status")

    missing_claim_keys = _missing_keys(dict(result.claim_metadata), REQUIRED_CLAIM_METADATA_KEYS)
    if missing_claim_keys:
        raise ValueError(
            f"force term {name} returned missing claim metadata keys: "
            f"{','.join(missing_claim_keys)}"
        )
    missing_term_claim_keys = _missing_keys(
        dict(result.claim_metadata),
        REQUIRED_FORCE_TERM_CLAIM_KEYS,
    )
    if missing_term_claim_keys:
        raise ValueError(
            f"force term {name} returned missing force term claim metadata keys: "
            f"{','.join(missing_term_claim_keys)}"
        )

    metadata_term = str(result.claim_metadata.get("force_term_name") or "")
    metadata_status = str(result.claim_metadata.get("force_term_status") or "")
    if metadata_term != name:
        raise ValueError(f"force term {name} returned mismatched claim metadata term: {metadata_term}")
    if not metadata_status:
        raise ValueError(f"force term {name} returned missing claim metadata status")

    if result.claim_metadata.get("claim_safe") is True and str(
        result.claim_metadata.get("blocked_reason") or ""
    ):
        raise ValueError(f"force term {name} returned claim_safe with blocked_reason")

    should_validate_bounds = (
        term_result_requests_bounded_correction_validation(result)
        if require_bounded_correction is None
        else bool(require_bounded_correction)
    )
    if not should_validate_bounds:
        return

    missing_bound_keys = _missing_keys(dict(result.claim_metadata), BOUNDED_CORRECTION_CLAIM_KEYS)
    if missing_bound_keys:
        raise ValueError(
            f"force term {name} returned missing bounded correction keys: "
            f"{','.join(missing_bound_keys)}"
        )
    caps = result.claim_metadata.get("force_term_policy_caps")
    if not isinstance(caps, dict) or not caps:
        raise ValueError(f"force term {name} returned invalid bounded correction policy caps")
    for key in (
        "force_term_policy_caps_ready",
        "force_term_observed_caps_ready",
        "force_term_bounded_correction_ready",
        "force_term_abs_energy_within_cap",
        "force_term_force_norm_within_cap",
    ):
        if not isinstance(result.claim_metadata.get(key), bool):
            raise ValueError(f"force term {name} returned non-boolean bounded correction key: {key}")
