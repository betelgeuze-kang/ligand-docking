from __future__ import annotations

import math
import time
from dataclasses import replace
from typing import Any

import numpy as np
import torch

from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.forcefield import (
    ProductForceField,
    guarded_force_term_registry,
)
from betelgeuze_engine.physics.mm_gbsa import mm_gbsa_binding_energy
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborProviderConfig,
    neighbor_source_indices,
)

from betelgeuze_engine.biodiscovery.stability_observations import (
    _coords as _observation_coordinates,
    measure_pose_retention,
)

DEFAULT_STABILITY_STEPS = 100
DEFAULT_STABILITY_DT = 0.001
DEFAULT_STABILITY_TEMP_K = 300.0
DEFAULT_BOX_SIZE = 80.0
# Exact symbols parameterized by the current VdW and surface-area primitives.
# Do not use their permissive first-letter/default normalization on explicit input.
MM_GBSA_SUPPORTED_ELEMENTS = frozenset({"H", "C", "N", "O", "S", "P", "F", "CL", "BR", "I"})


def build_atom_types(bead_count: int, ligand_count: int, device: torch.device | str = "cpu") -> torch.Tensor:
    cg_atom_type = 1
    ligand_atom_type = 2
    types = [cg_atom_type] * int(bead_count) + [ligand_atom_type] * int(ligand_count)
    return torch.tensor(types, dtype=torch.long, device=device)


def single_pose_score(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    device: torch.device | str = "cpu",
    *,
    field: ProductForceField | None = None,
) -> tuple[float, dict[str, Any]]:
    """Uncalibrated cross-component LJ proxy, never complex internal energy.

    The CA proxy supplies neither physical charges nor directional hydrogen-bond
    geometry. Those terms and ligand strain are absent, not measured zeroes.
    Static docking is nonperiodic; optional proxy dynamics has its own boundary.
    """
    protein_beads = _observation_coordinates(protein_beads, "protein_beads")
    ligand_coords = _observation_coordinates(ligand_coords, "ligand_coords")
    coords = np.concatenate([protein_beads, ligand_coords], axis=0)
    coords_t = torch.tensor(coords, dtype=torch.float32, device=device).unsqueeze(0)
    atom_types = build_atom_types(protein_beads.shape[0], ligand_coords.shape[0], device=device)

    state = EngineState(
        coords=coords_t,
        atom_types=atom_types,
    )

    neighbor_cfg = NeighborProviderConfig(
        cutoff=8.0,
        skin=2.0,
        max_neighbor_count=64,
    )
    neighbor_provider = CellListNeighborProvider(neighbor_cfg)
    pairs = neighbor_provider.build(coords_t)
    pair_diagnostics = dict(getattr(pairs, "diagnostics", {}) or {})
    if pair_diagnostics.get("overflow") is True:
        return float("inf"), {
            "status": "blocked_neighbor_overflow",
            "neighbor_diagnostics": pair_diagnostics,
        }
    if pair_diagnostics.get("nxn_allocation_observed") is True or getattr(pairs, "is_dense", False):
        return float("inf"), {
            "status": "blocked_dense_or_reference_neighbor",
            "neighbor_diagnostics": pair_diagnostics,
        }

    receptor_count = int(protein_beads.shape[0])
    cross_mask = (neighbor_source_indices(pairs) < receptor_count) != (pairs.idx < receptor_count)
    pairs = replace(pairs, mask=pairs.mask & cross_mask,
                    candidate_mask=(pairs.candidate_mask & cross_mask
                                    if pairs.candidate_mask is not None else pairs.mask & cross_mask))
    field = field or make_static_pose_field()
    try:
        ef = field.energy_forces(state, pairs, product_neighbor_required=True)
    except Exception as exc:
        return float("inf"), {
            "status": "blocked_forcefield_evaluation",
            "error": str(exc),
            "neighbor_diagnostics": pair_diagnostics,
        }

    total_e = float(ef.energy.sum().detach().cpu().item())
    terms = dict(ef.terms)
    claim = dict(ef.claim_metadata)

    diagnostics = {
        "total_energy": total_e,
        "cross_component_energy": total_e,
        "energy_scope": "receptor_ligand_cross_component_only",
        "internal_energies_included": False,
        "pbc_enabled": False,
        "terms": terms,
        "claim_safe": False,
        "term_claim_metadata": claim,
        "not_evaluated": {name: {"status": "not_evaluated", "value": None} for name in
                          ("receptor_partial_charge_electrostatics", "directional_hbond",
                           "physical_topology", "ligand_strain", "hydrophobic_chemistry")},
        "neighbor_pairs": int(ef.diagnostics.get("neighbor_pair_count", 0)),
        "neighbor_diagnostics": pair_diagnostics,
    }

    return total_e, diagnostics


def make_static_pose_field() -> ProductForceField:
    """Reusable parameter object for the sole available static pair proxy."""
    return ProductForceField.from_registry(guarded_force_term_registry(), names=["legacy_lj"])


def mm_gbsa_binding_score(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    contact_cutoff_a: float = 8.0,
    *,
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
    protein_charges: np.ndarray | None = None,
    ligand_charges: np.ndarray | None = None,
) -> dict[str, Any]:
    """Forward available atom typing without inventing receptor chemistry.

    CA-derived receptor sites have no all-atom charges. Formal ligand charges
    are not substituted for partial charges; electrostatics requires both
    explicit charge arrays. Results remain uncalibrated interaction proxies.
    """
    try:
        protein = _observation_coordinates(protein_beads, "protein_beads")
        ligand = _observation_coordinates(ligand_coords, "ligand_coords")
        normalized_elements: dict[str, list[str] | None] = {}
        for label, elements, count in (("protein", protein_elements, len(protein)),
                                       ("ligand", ligand_elements, len(ligand))):
            if elements is None:
                normalized_elements[label] = None
                continue
            if isinstance(elements, (str, bytes)) or np.ma.isMaskedArray(elements) or len(elements) != count:
                raise ValueError(f"{label}_element_coordinate_mismatch")
            normalized: list[str] = []
            for element in elements:
                if not isinstance(element, str) or element.strip().upper() not in MM_GBSA_SUPPORTED_ELEMENTS:
                    raise ValueError(f"unsupported_{label}_element:{element}")
                normalized.append(element.strip().upper())
            normalized_elements[label] = normalized
        if isinstance(contact_cutoff_a, (bool, np.bool_)) or not math.isfinite(contact_cutoff_a) or contact_cutoff_a <= 0.:
            raise ValueError("contact_cutoff_a must be finite and positive")
        if (protein_charges is None) != (ligand_charges is None):
            raise ValueError("both_partial_charge_arrays_required")
        for label, charges, count in (("protein", protein_charges, len(protein)),
                                      ("ligand", ligand_charges, len(ligand))):
            if charges is not None:
                array = np.asarray(charges)
                if np.ma.isMaskedArray(charges) or array.shape != (count,) or array.dtype.kind not in "iuf" or not np.isfinite(array).all():
                    raise ValueError(f"invalid_{label}_partial_charges")
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = mm_gbsa_binding_energy(
                protein_xyz=protein.astype(np.float32),
                ligand_xyz=ligand.astype(np.float32),
                contact_cutoff_a=float(contact_cutoff_a),
                protein_elements=normalized_elements["protein"], ligand_elements=normalized_elements["ligand"],
                protein_charges=protein_charges, ligand_charges=ligand_charges,
            )
        # Finite inputs can still overflow intermediate operations or cancellation.
        for key in ("interaction_score_proxy", "deltaG_mm_gbsa_kcal_mol", "e_vdw", "e_gb", "e_sa", "e_solvation"):
            value = result.get(key)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)) or not math.isfinite(value):
                raise ValueError(f"nonfinite_or_missing_mm_gbsa_result:{key}")
        for key, value in result.items():
            if isinstance(value, (float, np.floating)) and not math.isfinite(value):
                raise ValueError(f"nonfinite_mm_gbsa_result:{key}")
        return {**dict(result),
                "chemistry_input_scope": "explicit_elements_and_partial_charges" if protein_charges is not None else "available_elements_without_partial_charges",
                "partial_charges_supplied": protein_charges is not None,
                "receptor_atom_typing_supplied": protein_elements is not None,
                "ligand_atom_typing_supplied": ligand_elements is not None,
                "charge_source": "caller_supplied_unvalidated" if protein_charges is not None else "unavailable_no_formal_charge_substitution"}
    except Exception as exc:
        return {"binding_energy_kcal_mol": float("inf"), "error": "mm_gbsa_failed",
                "status": "blocked_chemistry_input_or_proxy_evaluation", "blocked_reason": str(exc),
                "claim_safe": False, "is_free_energy": False}


def run_stability_simulation(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    device: torch.device | str = "cpu",
    steps: int = DEFAULT_STABILITY_STEPS,
    dt: float = DEFAULT_STABILITY_DT,
    temp_k: float = DEFAULT_STABILITY_TEMP_K,
    seed: int = 42,
) -> tuple[float | None, dict[str, Any]]:
    """Observe the existing clamped, force-clipped dynamics proxy truthfully.

    This is not a validated thermostat/integrator or binding stability estimate.
    Endpoint geometry is observed, not predicted. No physical-time or affinity
    inference is made. Preserve the legacy update formula, but never repair NaNs.
    """
    if isinstance(steps, (bool, np.bool_)) or not isinstance(steps, (int, np.integer)) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    if not math.isfinite(dt) or dt <= 0. or not math.isfinite(temp_k) or temp_k < 0.:
        raise ValueError("dt must be positive and temp_k nonnegative, both finite")
    steps = int(steps)
    diagnostic: dict[str, Any] = {
        "schema_version": "tier_beta_stability_observation_v2",
        "status": "not_run",
        "evidence_kind": "computed_proxy_dynamics",
        "stable": None,
        "drift_A": None,
        "steps_requested": steps,
        "steps_run": 0,
        "initial_energy": None,
        "final_energy": None,
        "energy_drift": None,
        "energy_trace_length": 0,
        "elapsed_seconds": None,
        "pose_observations": {},
        "scientific_claim_validated": False,
        "stability_criterion": "receptor_aligned_ligand_endpoint_rmsd_lt_5a_proxy",
        "stability_criterion_calibrated": False,
        "force_clipped_component_count": 0,
        "coordinate_clamped_component_count": 0,
        "constraints": {
            "coordinate_clamp_box_a": float(DEFAULT_BOX_SIZE),
            "protein_ligand_constraints": "none_restricted_smoke",
        },
        "pbc_enabled": True,
        "pbc_scope": "neighbor_minimum_image_only",
        "periodic_coordinate_wrapping": False,
        "boundary_consistency_validated": False,
        "neighbor_box_a": float(DEFAULT_BOX_SIZE),
        "coordinate_boundary": "clamp_not_periodic_wrapping",
        "thermostat": {"type": "langevin_proxy", "temperature_k": float(temp_k), "gamma": 1.0},
        "time_step": float(dt),
        "time_unit": "unvalidated_proxy_units",
        "restart_reproducible": None,
        "seeded_execution": True,
        "restart_seed": int(seed),
    }
    if steps == 0:
        diagnostic["thermostat"]["type"] = "not_run"
        return None, diagnostic

    dev = torch.device(device)
    if dev.type == "cuda":
        torch.cuda.synchronize(dev)
    started = time.perf_counter()

    def finish(drift: float | None) -> tuple[float | None, dict[str, Any]]:
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        diagnostic["elapsed_seconds"] = float(time.perf_counter() - started)
        return drift, diagnostic

    try:
        protein = _observation_coordinates(protein_beads, "protein_beads")
        ligand = _observation_coordinates(ligand_coords, "ligand_coords")
        combined = np.concatenate([protein, ligand], axis=0)
        # Midpoint of the combined bounds fits any translatable complex whose
        # extent fits the box; a skewed receptor centroid does not guarantee this.
        origin = combined.min(axis=0) / 2. + combined.max(axis=0) / 2.
        diagnostic["coordinate_origin_a"] = [float(value) for value in origin]
        diagnostic["coordinate_frame"] = "complex_bounds_midpoint_translation_only"
        coords = combined - origin
        if (np.abs(coords) > DEFAULT_BOX_SIZE / 2.).any():
            raise ValueError("initial_coordinates_outside_proxy_clamp_box")
        coords_t = torch.tensor(coords, dtype=torch.float32, device=dev).unsqueeze(0)
        # The observation baseline is the actual precision used by the integrator.
        initial = coords_t[0].detach().cpu().numpy().copy()
        atom_types = build_atom_types(len(protein), len(ligand), device=dev)
        state = EngineState(coords=coords_t, atom_types=atom_types)
        field = ProductForceField.from_registry(guarded_force_term_registry())
        generator = torch.Generator(device=dev).manual_seed(int(seed))
        neighbor_config = NeighborProviderConfig(cutoff=8.0, skin=2.0, max_neighbor_count=64)
        kbt = 0.0019872041 * float(temp_k) / 298.15
        noise_scale = math.sqrt(2.0 * kbt * float(dt))

        def evaluate() -> tuple[torch.Tensor, float]:
            state.coords = coords_t.requires_grad_(True)
            # A persistent provider enables its internal cache. Retain the
            # original fresh-build behavior until cache parity is validated.
            pairs = CellListNeighborProvider(neighbor_config).build(coords_t, box=DEFAULT_BOX_SIZE)
            pair_diag = dict(getattr(pairs, "diagnostics", {}) or {})
            if pair_diag.get("overflow") is True:
                raise ValueError("neighbor_overflow")
            if pair_diag.get("nxn_allocation_observed") is True or getattr(pairs, "is_dense", False):
                raise ValueError("dense_or_reference_neighbor")
            ef = field.energy_forces(state, pairs, product_neighbor_required=True)
            if not torch.isfinite(ef.energy).all() or not torch.isfinite(ef.forces).all():
                raise ValueError("nonfinite_energy_or_forces")
            if ef.forces.shape != coords_t.shape:
                raise ValueError("force_coordinate_shape_mismatch")
            energy = float(ef.energy.sum().detach().cpu().item())
            if not math.isfinite(energy):
                raise ValueError("nonfinite_total_energy")
            return ef.forces.detach(), energy

        for step_idx in range(steps):
            forces, energy = evaluate()
            if step_idx == 0:
                diagnostic["initial_energy"] = energy
            diagnostic["energy_trace_length"] += 1
            diagnostic["force_clipped_component_count"] += int((forces.abs() > 1.).sum().item())
            forces = forces.clamp(-1., 1.)
            noise = torch.randn(coords_t.shape, dtype=coords_t.dtype, device=dev, generator=generator) * noise_scale
            with torch.no_grad():
                updated = coords_t.detach() + forces * float(dt) + noise
                if not torch.isfinite(updated).all():
                    raise ValueError("nonfinite_updated_coordinates")
                diagnostic["coordinate_clamped_component_count"] += int((updated.abs() > DEFAULT_BOX_SIZE / 2.).sum().item())
                coords_t = updated.clamp(-DEFAULT_BOX_SIZE / 2., DEFAULT_BOX_SIZE / 2.)
            diagnostic["steps_run"] += 1

        # Evaluate the terminal coordinates, not the preceding step's energy.
        _, final_energy = evaluate()
        diagnostic["final_energy"] = final_energy
        diagnostic["energy_drift"] = final_energy - diagnostic["initial_energy"]
        final = coords_t[0].detach().cpu().numpy()
        observations = measure_pose_retention(initial[:len(protein)], initial[len(protein):],
                                              final[:len(protein)], final[len(protein):])
        drift = observations["ligand_rmsd_receptor_frame_a"]
        diagnostic.update(status="observed", pose_observations=observations, drift_A=drift,
                          stable=(drift < 5.0) if drift is not None else None)
        return finish(drift)
    except Exception as exc:
        diagnostic.update(status="failed", stable=False, error=str(exc),
                          error_step=diagnostic["steps_run"])
        return finish(None)
