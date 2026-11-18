"""Product-owned bounded prepared-feature proposal generation.

The entry loop is adapted from the sealed Engine v2 generator (main 4c6e4b9).
It reuses engine geometry, limits, authority and receipts, but rederives the
prepared context through the product builder. It owns no global substitutions.
Source-paired rescue/conformer profiles remain outside this development lane.
"""

from __future__ import annotations

from betelgeuze_engine_v2.docking import guided_placement as _legacy
from .prepared_scoring import (
    PreparedGuidedPlacementContext,
    build_guided_placement_context,
)


def generate_prepared_docking_proposals(
    authenticated_problem: _legacy.AuthenticatedDockingProblem,
    budget: _legacy.DockingBudget,
    context: _legacy.GuidedPlacementContext,
    *,
    receptor_system: _legacy.AllAtomSystem,
    ligand_system: _legacy.AllAtomSystem,
    policy: _legacy.GuidedPlacementPolicy | None = None,
) -> tuple[tuple[_legacy.DockingProposal, ...], _legacy.GuidedPlacementReceipt]:
    if type(context) is not PreparedGuidedPlacementContext:
        raise _legacy.DockingAuthorityError("exact prepared guidance context required")
    if not isinstance(authenticated_problem, _legacy.AuthenticatedDockingProblem):
        raise TypeError("authenticated_problem must be AuthenticatedDockingProblem")
    if not isinstance(budget, _legacy.DockingBudget):
        raise TypeError("budget must be DockingBudget")
    if not isinstance(context, _legacy.GuidedPlacementContext):
        raise TypeError("context must be GuidedPlacementContext")
    selected_policy = _legacy.GuidedPlacementPolicy() if policy is None else policy
    if type(selected_policy) is not _legacy.GuidedPlacementPolicy:
        raise _legacy.DockingAuthorityError(
            "prepared guidance accepts only GuidedPlacementPolicy"
        )
    authenticated_problem.input_receipt_sha256
    if (
        context.authority_input_receipt_sha256
        != authenticated_problem.input_receipt_sha256
    ):
        raise _legacy.DockingAuthorityError(
            "guided context is cross-wired to another authority"
        )
    if (
        context.receptor_system_sha256 != authenticated_problem.receptor_system_sha256
        or context.ligand_system_sha256 != authenticated_problem.ligand_system_sha256
        or context.receptor_atom_indices != authenticated_problem.receptor_atom_indices
    ):
        raise _legacy.DockingAuthorityError(
            "guided context system identity is cross-wired"
        )
    context.fingerprint_sha256
    derived_context = build_guided_placement_context(
        authenticated_problem, receptor_system, ligand_system
    )
    if derived_context.fingerprint_sha256 != context.fingerprint_sha256:
        raise _legacy.DockingAuthorityError(
            "guided context does not match its authenticated derivation"
        )
    selected_policy.fingerprint_sha256
    placement_policy = _legacy.PocketPlacementPolicy(
        centered_candidate_count=selected_policy.centered_candidate_count
    )
    baseline, _ = _legacy.generate_pocket_centered_docking_proposals(
        authenticated_problem, budget, policy=placement_policy
    )
    centered_count, guided_count, modes = _legacy._guided_allocation(
        context, budget, selected_policy
    )
    from betelgeuze_engine_v2.docking import proposals as proposal_module

    proposals = list(baseline)
    proposal_modes = [_legacy.UNIFORM_FALLBACK_MODE] * len(proposals)
    proposal_modes[:centered_count] = [
        _legacy.POCKET_CENTER_BASELINE_MODE
    ] * centered_count
    ligand_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    receptor_anchor_rows: list[tuple[int, ...]] = [()] * len(proposals)
    requested_anchor_distances: list[float | None] = [None] * len(proposals)
    observed_anchor_distances: list[float | None] = [None] * len(proposals)
    ensemble_source_indices: list[int | None] = [None] * len(proposals)
    search_space = authenticated_problem.search_space
    pocket_center = authenticated_problem.pocket.center.to(
        dtype=search_space.local_offsets.dtype
    )
    multi_anchor_count = 0
    guided_transform_count = guided_count
    if selected_policy.uniform_v3_ensemble_enabled and guided_count:
        target_indices = tuple(range(centered_count, centered_count + guided_count))
        uniform_source_indices = tuple(
            range(centered_count + guided_count, len(baseline))
        )
        selected_sources = _legacy._evenly_spaced_uniform_sources(
            uniform_source_indices, guided_count
        )
        for proposal_index, source_index in zip(
            target_indices, selected_sources, strict=True
        ):
            target = baseline[proposal_index]
            source = baseline[source_index]
            fingerprint = proposal_module._proposal_fingerprint(
                proposal_index=proposal_index,
                seed=budget.seed,
                torsion_angles=source.torsion_angles,
                rotation=source.rotation,
                translation=source.translation,
                problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
                search_space_fingerprint_sha256=search_space.fingerprint_sha256,
                coordinate_fingerprint_sha256=source.coordinate_fingerprint_sha256,
            )
            variant = _legacy.DockingProposal(
                candidate_id=target.candidate_id,
                coordinates=source.coordinates,
                torsion_angles=source.torsion_angles,
                rotation=source.rotation,
                translation=source.translation,
                proposal_index=proposal_index,
                seed=budget.seed,
                fingerprint_sha256=fingerprint,
                problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
                search_space_fingerprint_sha256=search_space.fingerprint_sha256,
                coordinate_fingerprint_sha256=source.coordinate_fingerprint_sha256,
            )
            variant.assert_integrity()
            proposals[proposal_index] = variant
            proposal_modes[proposal_index] = _legacy.UNIFORM_V3_ENSEMBLE_MODE
            ensemble_source_indices[proposal_index] = source_index
        guided_transform_count = 0
    for guided_slot_index in range(guided_transform_count):
        proposal_index = centered_count + guided_slot_index
        base_mode = modes[proposal_index % len(modes)]
        cycle_index = proposal_index // len(modes)
        mode = base_mode
        if (
            base_mode in {"donor_acceptor_hotspot", "charge_anchor"}
            and cycle_index >= 1
            and (cycle_index % 2 == 1)
            and (
                multi_anchor_count < selected_policy.maximum_guided_candidates_per_mode
            )
            and _legacy._multi_anchor_available(context)
        ):
            mode = _legacy.MULTI_ANCHOR_MODE
        base = baseline[proposal_index]
        conformer = _legacy.torsion_tree_forward_kinematics(
            search_space.local_offsets,
            search_space.parent,
            base.torsion_angles,
            local_axes=search_space.local_axes,
            root_positions=search_space.root_positions,
        ).coordinates
        try:
            (
                coordinates,
                rotation,
                translation,
                ligand_anchor_indices,
                receptor_anchor_indices,
                requested_anchor_distance,
                observed_anchor_distance,
            ) = _legacy._guided_transform(
                mode=mode,
                context=context,
                policy=selected_policy,
                conformer=conformer,
                base_rotation=base.rotation,
                pocket_center=pocket_center,
                translation_radius_angstrom=budget.translation_radius_angstrom,
                seed=budget.seed,
                proposal_index=proposal_index,
            )
        except _legacy._GuidanceUnavailable:
            if mode != _legacy.MULTI_ANCHOR_MODE:
                continue
            mode = base_mode
            try:
                (
                    coordinates,
                    rotation,
                    translation,
                    ligand_anchor_indices,
                    receptor_anchor_indices,
                    requested_anchor_distance,
                    observed_anchor_distance,
                ) = _legacy._guided_transform(
                    mode=mode,
                    context=context,
                    policy=selected_policy,
                    conformer=conformer,
                    base_rotation=base.rotation,
                    pocket_center=pocket_center,
                    translation_radius_angstrom=budget.translation_radius_angstrom,
                    seed=budget.seed,
                    proposal_index=proposal_index,
                )
            except _legacy._GuidanceUnavailable:
                continue
        centroid_offset = float(
            _legacy.torch.linalg.vector_norm(
                coordinates.mean(dim=0) - pocket_center
            ).item()
        )
        if (
            centroid_offset
            > budget.translation_radius_angstrom + _legacy._CENTROID_TOLERANCE_ANGSTROM
        ):
            raise _legacy.DockingAuthorityError(
                "guided proposal exceeds the translation bound"
            )
        coordinate_digest = _legacy.coordinate_fingerprint(coordinates)
        fingerprint = proposal_module._proposal_fingerprint(
            proposal_index=proposal_index,
            seed=budget.seed,
            torsion_angles=base.torsion_angles,
            rotation=rotation,
            translation=translation,
            problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal = _legacy.DockingProposal(
            candidate_id=_legacy._stable_candidate_id(
                proposal_index=proposal_index,
                seed=budget.seed,
                problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
                search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            ),
            coordinates=coordinates,
            torsion_angles=base.torsion_angles,
            rotation=rotation,
            translation=translation,
            proposal_index=proposal_index,
            seed=budget.seed,
            fingerprint_sha256=fingerprint,
            problem_fingerprint_sha256=authenticated_problem.problem.fingerprint_sha256,
            search_space_fingerprint_sha256=search_space.fingerprint_sha256,
            coordinate_fingerprint_sha256=coordinate_digest,
        )
        proposal.assert_integrity()
        proposals[proposal_index] = proposal
        proposal_modes[proposal_index] = mode
        multi_anchor_count += int(mode == _legacy.MULTI_ANCHOR_MODE)
        ligand_anchor_rows[proposal_index] = ligand_anchor_indices
        receptor_anchor_rows[proposal_index] = receptor_anchor_indices
        requested_anchor_distances[proposal_index] = requested_anchor_distance
        observed_anchor_distances[proposal_index] = observed_anchor_distance
    result = tuple(proposals)
    receipt = _legacy.GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authenticated_problem.input_receipt_sha256,
        guidance_context_sha256=context.fingerprint_sha256,
        guided_policy_sha256=selected_policy.fingerprint_sha256,
        budget_sha256=_legacy._budget_sha256(budget),
        proposal_fingerprint_sha256s=tuple((row.fingerprint_sha256 for row in result)),
        proposal_modes=tuple(proposal_modes),
        ligand_anchor_atom_indices=tuple(ligand_anchor_rows),
        receptor_anchor_atom_indices=tuple(receptor_anchor_rows),
        requested_anchor_distance_angstroms=tuple(requested_anchor_distances),
        observed_anchor_distance_angstroms=tuple(observed_anchor_distances),
        feature_counts=context.feature_counts(),
        ensemble_source_proposal_indices=tuple(ensemble_source_indices),
    )
    return (result, receipt)
