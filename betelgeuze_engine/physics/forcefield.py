from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import torch

from betelgeuze_engine.contracts.claim import default_claim_metadata
from betelgeuze_engine.contracts.result import EnergyForces, TermResult, validate_term_result_contract
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.force_term import ForceTerm
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs
from betelgeuze_engine.physics.term_claim_metadata import claim_metadata_from_state, state_with_claim_metadata
from betelgeuze_engine.physics.terms import (
    DirectionalHBondTerm,
    HydrophobicContactTerm,
    LegacyLJTerm,
    ScreenedElectrostaticsTerm,
)

ForceTermFactory = Callable[[], ForceTerm]


@dataclass
class ForceTermRegistry:
    """Small product plugin registry for analytic force terms."""

    _factories: dict[str, ForceTermFactory] = field(default_factory=dict)

    def register(self, name: str, factory: ForceTermFactory, *, replace: bool = False) -> None:
        term_name = str(name or "").strip()
        if not term_name:
            raise ValueError("force term name must be non-empty")
        if term_name in self._factories and not replace:
            raise ValueError(f"force term already registered: {term_name}")
        self._factories[term_name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def create(self, names: Iterable[str] | None = None) -> list[ForceTerm]:
        selected = list(names) if names is not None else self.names()
        terms: list[ForceTerm] = []
        for name in selected:
            term_name = str(name)
            if term_name not in self._factories:
                raise KeyError(f"unknown force term: {term_name}")
            terms.append(self._factories[term_name]())
        return terms


def default_force_term_registry() -> ForceTermRegistry:
    registry = ForceTermRegistry()
    registry.register("directional_hbond", lambda: DirectionalHBondTerm())
    registry.register("hydrophobic_contact", lambda: HydrophobicContactTerm())
    registry.register("legacy_lj", lambda: LegacyLJTerm())
    return registry


def guarded_force_term_registry() -> ForceTermRegistry:
    registry = default_force_term_registry()
    registry.register("screened_electrostatics", lambda: ScreenedElectrostaticsTerm())
    return registry


def _term_name(term: ForceTerm) -> str:
    return str(getattr(term, "name", term.__class__.__name__))


def _validate_term_result(name: str, result: TermResult, coords: torch.Tensor) -> None:
    validate_term_result_contract(name=name, result=result, coords=coords)


def _merge_claim_metadata(
    *,
    base_claim_metadata: dict[str, Any] | None,
    term_results: Sequence[TermResult],
    term_diagnostics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata = default_claim_metadata(**dict(base_claim_metadata or {}))
    term_claim_rows: list[dict[str, Any]] = []
    for result in term_results:
        term_metadata = dict(result.claim_metadata)
        term_name = str(
            term_metadata.get("force_term_name")
            or result.diagnostics.get("term")
            or "unknown_force_term"
        )
        term_status = str(
            term_metadata.get("force_term_status")
            or result.diagnostics.get("status")
            or ""
        )
        term_claim_rows.append(
            {
                "force_term_name": term_name,
                "force_term_status": term_status,
                "claim_safe": term_metadata.get("claim_safe") is True,
                "blocked_reason": str(term_metadata.get("blocked_reason") or ""),
                "hbond_evidence_status": str(term_metadata.get("hbond_evidence_status") or ""),
                "hbond_evidence_schema_version": str(
                    term_metadata.get("hbond_evidence_schema_version") or ""
                ),
                "hbond_evidence_schema_ready": term_metadata.get("hbond_evidence_schema_ready") is True,
                "ligand_topology_valid": term_metadata.get("ligand_topology_valid") is True,
                "policy_caps_ready": term_metadata.get("force_term_policy_caps_ready"),
                "observed_caps_ready": term_metadata.get("force_term_observed_caps_ready"),
                "bounded_correction_ready": term_metadata.get("force_term_bounded_correction_ready"),
                "policy_caps": dict(term_metadata.get("force_term_policy_caps") or {}),
                "abs_energy_within_cap": term_metadata.get("force_term_abs_energy_within_cap"),
                "force_norm_within_cap": term_metadata.get("force_term_force_norm_within_cap"),
                "active_pair_count_within_cap": term_metadata.get(
                    "force_term_active_pair_count_within_cap"
                ),
            }
        )
    diagnostic_blockers = [
        f"{name}:{diag.get('status')}"
        for name, diag in term_diagnostics.items()
        if diag.get("status") not in {None, "", "pass"}
    ]
    explicit_term_blockers = [
        str(result.claim_metadata.get("blocked_reason"))
        for result in term_results
        if result.claim_metadata.get("claim_safe") is False
        and str(result.claim_metadata.get("blocked_reason") or "")
        not in {"", "not_assessed", "term_result_unscoped"}
    ]
    unscoped_term_blockers = [
        f"{result.diagnostics.get('term') or result.claim_metadata.get('force_term_name') or 'unknown_force_term'}:claim_metadata_unscoped"
        for result in term_results
        if str(result.claim_metadata.get("blocked_reason") or "") == "term_result_unscoped"
        or not result.claim_metadata.get("force_term_name")
    ]
    hbond_diag = term_diagnostics.get("directional_hbond") or {}
    if (
        metadata.get("hbond_evidence_status") == "not_assessed"
        and int(hbond_diag.get("active_pair_count") or 0) > 0
    ):
        metadata["hbond_evidence_status"] = "pass"
    hbond_rows = [row for row in term_claim_rows if row["force_term_name"] == "directional_hbond"]
    if hbond_rows:
        metadata["hbond_evidence_schema_version"] = hbond_rows[0]["hbond_evidence_schema_version"]
        metadata["hbond_evidence_schema_ready"] = hbond_rows[0]["hbond_evidence_schema_ready"]
    blockers = list(dict.fromkeys(diagnostic_blockers + explicit_term_blockers + unscoped_term_blockers))
    metadata["force_residual_applied"] = bool(metadata.get("force_residual_applied", False))
    metadata["claim_safe"] = bool(metadata.get("claim_safe") is True and not blockers)
    if metadata["claim_safe"]:
        metadata["blocked_reason"] = ""
    else:
        metadata["blocked_reason"] = ";".join(blockers) or str(
            metadata.get("blocked_reason") or "forcefield_claim_not_safe"
        )
    metadata["force_term_plugin_count"] = len(term_results)
    metadata["force_term_plugins"] = sorted(term_diagnostics)
    metadata["force_term_claim_metadata_ready"] = not unscoped_term_blockers
    metadata["force_term_claim_metadata_schema_version"] = "force_term_claim_metadata_v1"
    metadata["force_term_claim_rows"] = term_claim_rows
    metadata["force_term_claim_safe_count"] = int(
        sum(1 for row in term_claim_rows if row["claim_safe"] is True)
    )
    metadata["force_term_blocked_count"] = int(
        sum(1 for row in term_claim_rows if row["claim_safe"] is not True)
    )
    return metadata


@dataclass
class ProductForceField:
    terms: Sequence[ForceTerm]
    name: str = "product_forcefield"

    @classmethod
    def from_registry(
        cls,
        registry: ForceTermRegistry | None = None,
        *,
        names: Iterable[str] | None = None,
    ) -> "ProductForceField":
        registry = registry or default_force_term_registry()
        return cls(terms=registry.create(names))

    def energy_forces(
        self,
        state: EngineState,
        pairs: NeighborPairs | None = None,
        *,
        claim_metadata: dict[str, Any] | None = None,
    ) -> EnergyForces:
        if state.coords.ndim != 3:
            raise ValueError("state.coords must have shape [B, N, 3]")
        state_for_terms = state_with_claim_metadata(state, claim_metadata)
        neighbor_pairs_provided = pairs is not None
        pairs = pairs or full_neighbor_pairs(state_for_terms.coords)
        neighbor_pair_count = int(pairs.mask.sum().detach().cpu().item())
        total_energy = torch.zeros(
            state_for_terms.coords.shape[0],
            dtype=state_for_terms.coords.dtype,
            device=state_for_terms.coords.device,
        )
        total_forces = torch.zeros_like(state_for_terms.coords)
        term_values: dict[str, float] = {}
        term_diagnostics: dict[str, dict[str, Any]] = {}
        term_results: list[TermResult] = []
        for term in self.terms:
            name = _term_name(term)
            result = term.energy_forces(state_for_terms, pairs)
            _validate_term_result(name, result, state_for_terms.coords)
            total_energy = total_energy + result.energy.to(dtype=total_energy.dtype, device=total_energy.device)
            total_forces = total_forces + result.forces.to(dtype=total_forces.dtype, device=total_forces.device)
            term_values[name] = float(result.energy.detach().sum().cpu().item())
            term_diagnostics[name] = dict(result.diagnostics)
            term_diagnostics[name]["claim_metadata"] = dict(result.claim_metadata)
            term_results.append(result)
        merged_claim_metadata = _merge_claim_metadata(
            base_claim_metadata=claim_metadata_from_state(state_for_terms),
            term_results=term_results,
            term_diagnostics=term_diagnostics,
        )
        return EnergyForces(
            energy=total_energy.detach(),
            forces=total_forces.detach(),
            terms=term_values,
            diagnostics={
                "forcefield": self.name,
                "term_count": len(term_results),
                "neighbor_pair_count": neighbor_pair_count,
                "neighbor_pairs_provided": neighbor_pairs_provided,
                "neighbor_source": "provided" if neighbor_pairs_provided else "full_neighbor_pairs",
                "term_diagnostics": term_diagnostics,
            },
            claim_metadata=merged_claim_metadata,
        )
