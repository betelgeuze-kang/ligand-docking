"""Legacy and V2 engine adapters over the canonical packet (roadmap §17).

The pieces the roadmap asks for now all exist separately: a canonical
preparation packet, chemistry-aware rotor perception, a deterministic conformer
ensemble, Scorer v1, bounded local refinement, symmetry-aware clustering, and a
common ``DockingResultBundle``. What was missing is the layer that actually runs
them, so nothing proved the two engine surfaces consume the same prepared input
and emit the same result schema.

This module is that layer::

    PreparationPacket
           |
           +-- legacy_product adapter ---+
           |                             |
           +-- engine_v2 adapter --------+--> DockingResultBundle

Both adapters read *only* the packet. They cannot re-prepare, re-perceive, or
re-embed: an adapter that could would reintroduce exactly the preparation
difference the packet exists to remove. The only intentional difference between
the two surfaces is the search/refinement budget, which is recorded per bundle
so a delta can be attributed to it.

Adapters are deliberately deterministic and offline. A blocked packet yields a
blocked bundle with a counted failure, never a partial result.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from betelgeuze_engine.chemistry.pose_clustering import cluster_poses
from betelgeuze_engine.scoring.local_refinement import (
    RefinementParameters,
    refine_pose_locally,
)
from betelgeuze_engine.scoring.scorer_v1 import score_pose_v1
from betelgeuze_product.docking_result_bundle import (
    DockingResultBundle,
    FailureDenominator,
    PoseRecord,
)
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
    ENGINE_SURFACES,
    PreparationPacket,
)

ENGINE_ADAPTER_SCHEMA_VERSION = "engine_adapter_v1"

#: Adapter versions are reported per bundle so a comparison can name which build
#: produced each side.
LEGACY_ADAPTER_VERSION = "legacy_product_adapter_1.0.0"
ENGINE_V2_ADAPTER_VERSION = "engine_v2_adapter_1.0.0"
EXTERNAL_ORACLE_ADAPTER_VERSION = "external_oracle_adapter_1.0.0"

#: Offline baseline binaries the oracle surface would need. They are never
#: downloaded or installed by this module: absence is reported as abstention.
EXTERNAL_ORACLE_BINARIES = ("vina", "gnina", "smina")

#: Operator-supplied receipt that records the offline baseline score intake
#: state. It is referenced, never rewritten, by the oracle adapter.
EXTERNAL_ORACLE_SCORE_RECEIPT_PATH = (
    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
)

#: Clash distance below which a pose is not geometrically valid.
GEOMETRIC_CLASH_DISTANCE_A = 1.8

CLAIM_BOUNDARY = (
    "Engine adapters run internal uncalibrated scoring and bounded refinement over a canonical prepared packet "
    "and emit the common result schema for comparison. They do not prepare inputs, fetch structures, contact "
    "external services, or promote any claim."
)


@dataclass(frozen=True)
class AdapterBudget:
    """Search/refinement budget for one adapter run.

    This is the only sanctioned difference between the two surfaces, so it is
    explicit and recorded rather than hidden in each adapter's defaults.
    """

    candidate_budget: int
    max_reported_poses: int = 5
    cluster_threshold_a: float = 2.0
    max_cluster_diameter_a: float | None = None
    refinement: RefinementParameters | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_budget": int(self.candidate_budget),
            "max_reported_poses": int(self.max_reported_poses),
            "cluster_threshold_a": float(self.cluster_threshold_a),
            "max_cluster_diameter_a": self.max_cluster_diameter_a,
            "refinement_enabled": self.refinement is not None,
            "refinement_parameter_digest": (
                self.refinement.parameter_digest if self.refinement is not None else ""
            ),
        }


#: Legacy runs unrefined: it reports the sampled pose as scored.
LEGACY_BUDGET = AdapterBudget(candidate_budget=64, max_reported_poses=5)

#: V2 runs the same candidate budget plus bounded local refinement, so a
#: legacy-vs-V2 delta isolates refinement rather than sampling depth.
ENGINE_V2_BUDGET = AdapterBudget(
    candidate_budget=64,
    max_reported_poses=5,
    refinement=RefinementParameters(),
)


def _conformer_coordinates(packet: PreparationPacket) -> list[np.ndarray]:
    """Read the retained conformer coordinates carried by the prepared packet.

    The adapter must not re-embed. The packet freezes the embedded coordinates,
    so both surfaces dock the identical atoms in the identical geometry and a
    legacy-vs-V2 delta cannot be an embedding difference. A packet without
    coordinates is treated as unusable rather than silently re-embedded.
    """

    frames = packet.ligand.conformer_coordinates or ()
    if not frames:
        return []
    retained = int((packet.ligand.conformer_ensemble or {}).get("retained_conformer_count") or 0)
    if retained and len(frames) != retained:
        return []
    elements = packet.ligand.atom_elements
    coordinates: list[np.ndarray] = []
    for frame in frames:
        array = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
        if array.shape[0] == 0:
            return []
        if elements and array.shape[0] != len(elements):
            return []
        coordinates.append(array)
    return coordinates


def _placed(coords: np.ndarray, pocket_center: np.ndarray) -> np.ndarray:
    """Center a conformer on the pocket so every surface starts identically."""

    centered = coords - coords.mean(axis=0)
    return centered + pocket_center.reshape(1, 3)


def _geometric_valid(
    protein: np.ndarray,
    ligand: np.ndarray,
    pocket_center: np.ndarray,
    pocket_radius_a: float,
) -> bool:
    """A pose is geometrically valid when it neither clashes nor escapes."""

    if protein.shape[0] == 0 or ligand.shape[0] == 0:
        return False
    distances = np.linalg.norm(protein[:, None, :] - ligand[None, :, :], axis=2)
    if float(np.min(distances)) < GEOMETRIC_CLASH_DISTANCE_A:
        return False
    offset = float(np.linalg.norm(ligand.mean(axis=0) - pocket_center))
    return offset <= float(pocket_radius_a) * 1.5


def _pose_coordinates(coords: np.ndarray) -> tuple[tuple[float, float, float], ...]:
    """Freeze scored coordinates into the pose record.

    Rounding here keeps the bundle hash reproducible while staying far finer than
    the 2 A success criterion the benchmark applies.
    """

    array = np.asarray(coords, dtype=np.float64).reshape(-1, 3)
    return tuple(
        (round(float(row[0]), 4), round(float(row[1]), 4), round(float(row[2]), 4))
        for row in array
    )


def _blocked_bundle(
    packet: PreparationPacket,
    *,
    engine_surface: str,
    engine_version: str,
    budget: AdapterBudget,
    benchmark_profile: str,
    claim_scope: str,
    reason: str,
) -> DockingResultBundle:
    """A blocked adapter run still reports a counted failure, never a gap."""

    return DockingResultBundle(
        engine_surface=engine_surface,
        engine_version=engine_version,
        prepared_input_hash=packet.prepared_input_hash,
        receptor_input_hash=packet.receptor.input_hash,
        ligand_input_hash=packet.ligand.input_hash,
        pocket_identity=packet.receptor.pocket.as_dict(),
        poses=(),
        failure_denominator=FailureDenominator(
            attempted_case_count=1,
            scored_case_count=0,
            failed_case_count=1,
            abstained_case_count=0,
        ),
        runtime_seconds=0.0,
        candidate_budget=int(budget.candidate_budget),
        benchmark_profile=benchmark_profile,
        claim_scope=claim_scope,
        uncertainty={"abstained": False, "reason": reason},
        evidence_receipts={
            "adapter_schema_version": ENGINE_ADAPTER_SCHEMA_VERSION,
            "budget": budget.as_dict(),
            "blocked_reason": reason,
            "prepared_packet_blockers": list(packet.blockers),
        },
        blockers=(reason,),
    )


def run_engine_adapter(
    packet: PreparationPacket,
    *,
    engine_surface: str,
    budget: AdapterBudget | None = None,
    benchmark_profile: str = "internal_diagnostic_profile",
    claim_scope: str = "restricted_internal",
    symmetry_mappings: Sequence[Sequence[int]] | None = None,
) -> DockingResultBundle:
    """Run one engine surface over the canonical packet and emit the bundle."""

    surface = str(engine_surface)
    if surface not in ENGINE_SURFACES:
        raise ValueError(f"unsupported_engine_surface:{surface or '<empty>'}")
    if surface == ENGINE_SURFACE_LEGACY_PRODUCT:
        engine_version = LEGACY_ADAPTER_VERSION
        resolved_budget = budget or LEGACY_BUDGET
    elif surface == ENGINE_SURFACE_ENGINE_V2:
        engine_version = ENGINE_V2_ADAPTER_VERSION
        resolved_budget = budget or ENGINE_V2_BUDGET
    else:
        # The external oracle is an offline baseline; it is recorded, not run here.
        raise ValueError(f"engine_surface_not_runnable_locally:{surface}")

    def _blocked(reason: str) -> DockingResultBundle:
        return _blocked_bundle(
            packet,
            engine_surface=surface,
            engine_version=engine_version,
            budget=resolved_budget,
            benchmark_profile=benchmark_profile,
            claim_scope=claim_scope,
            reason=reason,
        )

    if not packet.ready:
        return _blocked("prepared_input_not_ready")

    protein = np.asarray(packet.receptor.coordinates, dtype=np.float64).reshape(-1, 3)
    pocket = packet.receptor.pocket
    pocket_center = np.asarray(pocket.center, dtype=np.float64)
    conformers = _conformer_coordinates(packet)
    if not conformers:
        return _blocked("prepared_conformer_ensemble_not_reproducible")

    conformer_ids = list(packet.ligand.conformer_ids)
    ligand_elements = [str(element) for element in packet.ligand.atom_elements]
    scored: list[dict[str, Any]] = []
    for index, frame in enumerate(conformers[: int(resolved_budget.candidate_budget)]):
        coords = _placed(frame, pocket_center)
        refinement_payload: dict[str, Any] = {}
        if resolved_budget.refinement is not None:
            refinement = refine_pose_locally(
                protein,
                coords,
                protein_elements=list(packet.receptor.elements),
                ligand_elements=ligand_elements or None,
                ligand_smiles=packet.ligand.smiles,
                pocket_center=pocket_center,
                pocket_radius_a=pocket.radius_a,
                parameters=resolved_budget.refinement,
            )
            refinement_payload = refinement.to_dict()
            if not refinement.failed:
                coords = np.asarray(refinement.post_coordinates, dtype=np.float64)
        result = score_pose_v1(
            protein,
            coords,
            protein_elements=list(packet.receptor.elements),
            ligand_elements=ligand_elements or None,
            ligand_smiles=packet.ligand.smiles,
            pocket_center=pocket_center,
            pocket_radius_a=pocket.radius_a,
        )
        if not result.ready:
            continue
        scored.append(
            {
                "conformer_index": index,
                "conformer_id": conformer_ids[index] if index < len(conformer_ids) else "",
                "coords": coords,
                "total_score": float(result.total_score),
                "per_term_score": {
                    term.term_id: float(term.weighted_value) for term in result.terms
                },
                "refinement": refinement_payload,
            }
        )

    if not scored:
        return _blocked("no_pose_scored")

    clustering = cluster_poses(
        [row["coords"] for row in scored],
        scores=[row["total_score"] for row in scored],
        symmetry_mappings=symmetry_mappings,
        threshold_a=float(resolved_budget.cluster_threshold_a),
        max_cluster_diameter_a=resolved_budget.max_cluster_diameter_a,
    )
    # Report one pose per distinct binding mode, best cluster first, so top-k is
    # k distinct modes rather than k views of one mode.
    representatives = clustering.representative_pose_indices(
        limit=int(resolved_budget.max_reported_poses)
    )
    chemistry_valid = bool(packet.ligand.chemistry_validity.get("claim_safe") is True)

    poses: list[PoseRecord] = []
    for rank, position in enumerate(representatives, start=1):
        row = scored[int(position)]
        poses.append(
            PoseRecord(
                pose_id=f"{surface}_pose_{rank}",
                rank=rank,
                conformer_id=str(row["conformer_id"]),
                cluster_id=int(clustering.assignments[int(position)]),
                total_score=float(row["total_score"]),
                per_term_score=dict(row["per_term_score"]),
                geometric_valid=_geometric_valid(
                    protein, row["coords"], pocket_center, pocket.radius_a
                ),
                chemistry_valid=chemistry_valid,
                # The scored coordinates travel with the pose so an evaluator can
                # compute RMSD against a reference without re-running the engine.
                coordinates=_pose_coordinates(row["coords"]),
            )
        )

    refinement_rows = [row["refinement"] for row in scored if row["refinement"]]
    return DockingResultBundle(
        engine_surface=surface,
        engine_version=engine_version,
        prepared_input_hash=packet.prepared_input_hash,
        receptor_input_hash=packet.receptor.input_hash,
        ligand_input_hash=packet.ligand.input_hash,
        pocket_identity=pocket.as_dict(),
        poses=tuple(poses),
        failure_denominator=FailureDenominator(
            attempted_case_count=1,
            scored_case_count=1,
            failed_case_count=0,
            abstained_case_count=0,
        ),
        # Runtime is reported as 0.0 because these adapters are deterministic and
        # wall-clock timing would make the bundle hash unstable; the benchmark
        # harness measures runtime, not the adapter.
        runtime_seconds=0.0,
        candidate_budget=int(resolved_budget.candidate_budget),
        benchmark_profile=benchmark_profile,
        claim_scope=claim_scope,
        uncertainty={
            "abstained": False,
            "scored_candidate_count": len(scored),
            "distinct_binding_mode_count": clustering.cluster_count,
        },
        evidence_receipts={
            "adapter_schema_version": ENGINE_ADAPTER_SCHEMA_VERSION,
            "budget": resolved_budget.as_dict(),
            "clustering": {
                "method": clustering.method,
                "order_independent": True,
                "cluster_count": clustering.cluster_count,
                "threshold_a": clustering.threshold_a,
            },
            "refinement_run_count": len(refinement_rows),
            "refinement_converged_count": sum(
                1 for row in refinement_rows if row.get("converged") is True
            ),
            "refinement_failed_count": sum(
                1 for row in refinement_rows if row.get("failed") is True
            ),
            "ligand_flexibility_lane": packet.ligand.flexibility_lane,
            "conformer_ids": conformer_ids,
            "claim_boundary": CLAIM_BOUNDARY,
        },
    )


def available_external_oracle_binaries() -> tuple[str, ...]:
    """Report which offline baseline binaries are actually present on PATH."""

    return tuple(name for name in EXTERNAL_ORACLE_BINARIES if shutil.which(name))


def run_external_oracle_adapter(
    packet: PreparationPacket,
    *,
    budget: AdapterBudget | None = None,
    benchmark_profile: str = "internal_diagnostic_profile",
    claim_scope: str = "restricted_internal",
) -> DockingResultBundle:
    """Record the offline oracle surface for one prepared input.

    The oracle is a baseline, not a competitor: its bundle exists so a
    legacy-vs-V2 delta can be read against an external reference. This adapter
    never installs or fetches a docking binary. When no baseline binary is
    present, the surface abstains with a counted abstention rather than emitting
    a score it did not compute, because a silently-missing baseline would make
    the comparison look validated when it is not.
    """

    resolved_budget = budget or ENGINE_V2_BUDGET
    present = available_external_oracle_binaries()
    receipt_path = Path(EXTERNAL_ORACLE_SCORE_RECEIPT_PATH)
    blockers: list[str] = []
    if not present:
        blockers.append("external_oracle_binary_unavailable_offline")
    if not packet.ready:
        blockers.append("prepared_input_not_ready")

    abstained = bool(blockers)
    return DockingResultBundle(
        engine_surface=ENGINE_SURFACE_EXTERNAL_ORACLE,
        engine_version=EXTERNAL_ORACLE_ADAPTER_VERSION,
        prepared_input_hash=packet.prepared_input_hash,
        receptor_input_hash=packet.receptor.input_hash,
        ligand_input_hash=packet.ligand.input_hash,
        pocket_identity=packet.receptor.pocket.as_dict(),
        poses=(),
        failure_denominator=FailureDenominator(
            attempted_case_count=1,
            scored_case_count=0,
            failed_case_count=0,
            abstained_case_count=1 if abstained else 0,
        )
        if abstained
        else FailureDenominator(
            attempted_case_count=1,
            scored_case_count=0,
            failed_case_count=1,
            abstained_case_count=0,
        ),
        runtime_seconds=0.0,
        candidate_budget=int(resolved_budget.candidate_budget),
        benchmark_profile=benchmark_profile,
        claim_scope=claim_scope,
        uncertainty={
            "abstained": abstained,
            "reason": "external_oracle_offline_no_local_baseline_binary"
            if abstained
            else "external_oracle_scores_not_ingested",
            "available_binaries": list(present),
            "required_binaries": list(EXTERNAL_ORACLE_BINARIES),
        },
        evidence_receipts={
            "adapter_schema_version": ENGINE_ADAPTER_SCHEMA_VERSION,
            "budget": resolved_budget.as_dict(),
            "offline_only": True,
            "installs_binaries": False,
            "score_receipt_path": EXTERNAL_ORACLE_SCORE_RECEIPT_PATH,
            "score_receipt_present": receipt_path.is_file(),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        blockers=tuple(dict.fromkeys(blockers)),
    )


def run_legacy_adapter(packet: PreparationPacket, **kwargs: Any) -> DockingResultBundle:
    """Run the active legacy surface over the canonical packet."""

    return run_engine_adapter(
        packet, engine_surface=ENGINE_SURFACE_LEGACY_PRODUCT, **kwargs
    )


def run_engine_v2_adapter(packet: PreparationPacket, **kwargs: Any) -> DockingResultBundle:
    """Run the shadow V2 surface over the canonical packet."""

    return run_engine_adapter(packet, engine_surface=ENGINE_SURFACE_ENGINE_V2, **kwargs)


__all__ = [
    "CLAIM_BOUNDARY",
    "ENGINE_ADAPTER_SCHEMA_VERSION",
    "ENGINE_V2_ADAPTER_VERSION",
    "ENGINE_V2_BUDGET",
    "EXTERNAL_ORACLE_ADAPTER_VERSION",
    "EXTERNAL_ORACLE_BINARIES",
    "EXTERNAL_ORACLE_SCORE_RECEIPT_PATH",
    "GEOMETRIC_CLASH_DISTANCE_A",
    "LEGACY_ADAPTER_VERSION",
    "LEGACY_BUDGET",
    "AdapterBudget",
    "available_external_oracle_binaries",
    "run_engine_adapter",
    "run_engine_v2_adapter",
    "run_external_oracle_adapter",
    "run_legacy_adapter",
]
