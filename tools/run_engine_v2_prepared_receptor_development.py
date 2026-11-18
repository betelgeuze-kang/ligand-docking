"""Run the opt-in named-peptide preparation + guided search development profile.

This entry point takes an explicitly supplied pocket and no native pose. It does
not change the frozen 300-case runner, or report PoseBusters/RMSD accuracy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import torch

from betelgeuze_engine_v2.docking import (
    DockingAuthorityError,
    DockingBudget,
    DockingScope,
    DockingSearchError,
    GuidedPlacementPolicy,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    uniform_v3_ensemble_proposal_indices,
)
from betelgeuze_product.docking_development_v1.chemistry_features import (
    FULL_TOPOLOGY_FEATURE_POLICY_ID,
)
from betelgeuze_product.docking_development_v1.receptor_preparation import (
    ChemistryPreparationError,
    prepare_ligand_v1,
    prepare_receptor_v1,
)
from betelgeuze_product.docking_development_v1.prepared_scoring import (
    ChemistryPoseScorerV1,
    build_guided_placement_context,
    run_authenticated_scorer_v1_guided_search,
)

PROFILE_ID = "betelgeuze.prepared_peptide_guided_docking_development/1.0.0"
RETAINED_V9_PROFILE_ID = (
    "betelgeuze.prepared_peptide_retained_v9_docking_development/1.0.0"
)


def _implementation_sources() -> dict[str, str]:
    import betelgeuze_engine_v2
    from betelgeuze_product.docking_development_v1 import receptor_preparation

    root = Path(betelgeuze_engine_v2.__file__).resolve().parent
    paths = {
        "betelgeuze_engine_v2/" + path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*.py"))
    }
    development_root = Path(receptor_preparation.__file__).resolve().parent
    for path in sorted(development_root.rglob("*.py")):
        name = (
            "betelgeuze_product/docking_development_v1/"
            + path.relative_to(development_root).as_posix()
        )
        paths[name] = path
    product_init = development_root.parent / "__init__.py"
    if product_init.is_file():
        paths["betelgeuze_product/__init__.py"] = product_init
    runner = Path(__file__).resolve()
    paths["tools/" + runner.name] = runner
    tools_init = runner.parent / "__init__.py"
    if tools_init.is_file():
        paths["tools/__init__.py"] = tools_init
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(paths.items())
    }


def _retained_implementation_sources() -> dict[str, str]:
    from betelgeuze_product.explicit_refinement_pipeline import implementation_sources

    sources = _implementation_sources()
    for name, digest in implementation_sources().items():
        if name in sources and sources[name] != digest:
            raise ChemistryPreparationError(
                "implementation_source_changed", "source inventories disagree"
            )
        sources[name] = digest
    return dict(sorted(sources.items()))


def _run_retained_v9(
    authority, receptor, ligand, guidance, budget, policy, sources, implementation
) -> dict[str, object]:
    from betelgeuze_product.explicit_refinement_pipeline import (
        ContactRefinementProviderV9,
        ExplicitRefinementDockingPipelineV1,
    )
    from betelgeuze_product.structure_preserving_refinement import (
        StructureRefinementError,
    )

    try:
        result = (
            ExplicitRefinementDockingPipelineV1(ContactRefinementProviderV9())
            .run(
                authority,
                ligand.system,
                receptor.system,
                budget,
                guided_context=guidance,
                guided_policy=policy,
            )
            .to_dict()
        )
    except StructureRefinementError as exc:
        raise ChemistryPreparationError(
            "retained_v9_contract_unsupported", str(exc)
        ) from exc
    if (
        any(
            sources.get(name) != digest
            for name, digest in result["implementation_sources"].items()
        )
        or _retained_implementation_sources() != sources
    ):
        raise ChemistryPreparationError(
            "implementation_source_changed",
            "retained pipeline source inventory changed during execution",
        )
    # The product pipeline owns its observed numerical closure. Preserve that
    # identity in its result; the enclosing CLI additionally binds preparation
    # and entry-point bytes. Reconstruct its scorer only to verify the actual
    # returned contract and expose the feature policy used by that scorer.
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor.system,
        ligand.system,
        implementation_source_sha256=result["implementation_source_sha256"],
    )
    if (
        scorer.context.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID
        or result["scorer_contract_sha256"] != scorer.contract_fingerprint_sha256
    ):
        raise ChemistryPreparationError(
            "feature_policy_not_consumed", "retained scorer contract differs"
        )
    return {
        "schema_id": "betelgeuze.prepared_peptide_retained_v9_development_report/1.0.0",
        "profile_id": RETAINED_V9_PROFILE_ID,
        "refinement_policy": "retained-v9",
        "status": "completed",
        "implementation_sources": sources,
        "implementation_source_sha256": implementation,
        "implementation_source_scope": "product_retained_refinement_closure_engine_v2_python_inventory_and_development_entrypoint",
        "environment": {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "torch_threads": torch.get_num_threads(),
            "rdkit": receptor.receipt["rdkit_version"],
        },
        "receptor_preparation": dict(receptor.receipt),
        "ligand_preparation": dict(ligand.receipt),
        "scorer_feature_policy_id": scorer.context.feature_policy_id,
        "guidance_feature_policy_id": guidance.feature_policy_id,
        "scorer_context_sha256": scorer.context.fingerprint_sha256,
        "guidance_context_sha256": guidance.fingerprint_sha256,
        "retained_refinement": result,
        "validity_scope": "engine_internal_bounded_checks_only",
        "posebusters_measured": False,
        "native_recovery_measured": False,
        "affinity_calibrated": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }


def run_prepared_receptor_development(
    receptor_payload: bytes,
    ligand_payload: bytes,
    *,
    center: tuple[float, float, float],
    radius: float,
    candidate_count: int = 16,
    refinement_steps: int = 4,
    seed: int = 1701,
    refinement_policy: str = "v7",
) -> dict[str, object]:
    if refinement_policy not in ("v7", "retained-v9"):
        raise ChemistryPreparationError(
            "invalid_refinement_policy", "choose v7 or retained-v9 explicitly"
        )
    if type(candidate_count) is not int or not 1 <= candidate_count <= 64:
        raise ChemistryPreparationError(
            "invalid_candidate_budget", "candidate count must be in [1,64]"
        )
    if type(refinement_steps) is not int or not 0 <= refinement_steps <= 24:
        raise ChemistryPreparationError(
            "invalid_refinement_budget", "refinement steps must be in [0,24]"
        )
    if refinement_policy == "retained-v9" and refinement_steps == 0:
        raise ChemistryPreparationError(
            "retained_v9_requires_positive_steps",
            "retained-v9 requires 1-24 refinement steps; v7 also permits zero",
        )
    sources = (
        _retained_implementation_sources()
        if refinement_policy == "retained-v9"
        else _implementation_sources()
    )
    implementation = hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receptor = prepare_receptor_v1(receptor_payload)
    ligand = prepare_ligand_v1(ligand_payload)
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="user_supplied_development_pocket",
        method_version="1.0.0",
        coordinate_frame_id="source_receptor_frame",
        center=torch.tensor(center, dtype=torch.float64),
        radius_angstrom=radius,
        source_artifact_sha256=hashlib.sha256(receptor_payload).hexdigest(),
        implementation_source_sha256=implementation,
    )
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor.system,
        ligand.system,
        pocket,
    )
    guidance = build_guided_placement_context(authority, receptor.system, ligand.system)
    if guidance.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID:
        raise ChemistryPreparationError(
            "feature_policy_not_consumed",
            "guidance must consume the new policy",
        )
    budget = DockingBudget(
        candidate_count=candidate_count,
        top_k=min(5, candidate_count),
        max_torsions=32,
        max_refinement_steps=refinement_steps,
        translation_radius_angstrom=min(4.0, radius),
        seed=seed,
    )
    policy = GuidedPlacementPolicy(uniform_v3_ensemble_enabled=True)
    if refinement_policy == "retained-v9":
        return _run_retained_v9(
            authority,
            receptor,
            ligand,
            guidance,
            budget,
            policy,
            sources,
            implementation,
        )
    scorer = ChemistryPoseScorerV1(
        authority,
        receptor.system,
        ligand.system,
        implementation_source_sha256=implementation,
    )
    if scorer.context.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID:
        raise ChemistryPreparationError(
            "feature_policy_not_consumed", "scoring must consume the new policy"
        )
    refiner = InteractionAwareTorsionContactEnsembleRefinerV7(
        authority,
        receptor.system,
        ligand.system,
        implementation_source_sha256=implementation,
        v3_proposal_indices=uniform_v3_ensemble_proposal_indices(
            guidance, budget, policy
        ),
    )
    result = run_authenticated_scorer_v1_guided_search(
        authority,
        budget,
        scorer,
        guidance,
        receptor_system=receptor.system,
        ligand_system=ligand.system,
        refiner=refiner,
        guided_policy=policy,
    )
    search = result.guided_search_result.authenticated_search_result.search_result
    if _implementation_sources() != sources:
        raise ChemistryPreparationError(
            "implementation_source_changed",
            "implementation bytes changed during execution",
        )
    return {
        "schema_id": "betelgeuze.prepared_peptide_development_report/1.0.0",
        "profile_id": PROFILE_ID,
        "status": "completed",
        "implementation_sources": sources,
        "implementation_source_sha256": implementation,
        "implementation_source_scope": "engine_v2_python_inventory_product_docking_development_and_entrypoint",
        "environment": {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "torch_threads": torch.get_num_threads(),
            "rdkit": receptor.receipt["rdkit_version"],
        },
        "receptor_preparation": dict(receptor.receipt),
        "ligand_preparation": dict(ligand.receipt),
        "scorer_feature_policy_id": scorer.context.feature_policy_id,
        "guidance_feature_policy_id": guidance.feature_policy_id,
        "scorer_context_sha256": scorer.context.fingerprint_sha256,
        "guidance_context_sha256": guidance.fingerprint_sha256,
        "search": search.to_dict(),
        "candidates": [
            {
                **row.to_dict(),
                "coordinates_angstrom": row.proposal.coordinates.tolist()
                if row.proposal is not None
                else None,
            }
            for row in search.rows
        ],
        "selected_proposal_indices": [row.proposal_index for row in search.top_rows],
        "validity_scope": "engine_internal_bounded_checks_only",
        "posebusters_measured": False,
        "native_recovery_measured": False,
        "affinity_calibrated": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receptor", type=Path, required=True)
    parser.add_argument("--ligand", type=Path, required=True)
    parser.add_argument("--center", type=float, nargs=3, required=True)
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--candidates", type=int, default=16)
    parser.add_argument("--refinement-steps", type=int, default=4)
    parser.add_argument(
        "--refinement-policy",
        choices=("v7", "retained-v9"),
        default="v7",
        help="v7 preserves the existing report; retained-v9 retains up to two candidates per source and requires positive steps",
    )
    parser.add_argument("--seed", type=int, default=1701)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    exit_code = 0
    profile_id = (
        RETAINED_V9_PROFILE_ID
        if args.refinement_policy == "retained-v9"
        else PROFILE_ID
    )
    try:
        report = run_prepared_receptor_development(
            args.receptor.read_bytes(),
            args.ligand.read_bytes(),
            center=tuple(args.center),
            radius=args.radius,
            candidate_count=args.candidates,
            refinement_steps=args.refinement_steps,
            seed=args.seed,
            refinement_policy=args.refinement_policy,
        )
    except ChemistryPreparationError as exc:
        report = {
            "profile_id": profile_id,
            "status": "failed",
            "failure_code": exc.code,
            "detail": exc.detail,
            "claim_safe": False,
        }
        exit_code = 2
    except (DockingAuthorityError, DockingSearchError) as exc:
        report = {
            "profile_id": profile_id,
            "status": "failed",
            "failure_code": "docking_contract_unsupported",
            "detail": str(exc),
            "claim_safe": False,
        }
        exit_code = 2
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
