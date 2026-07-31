from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")
pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

from betelgeuze_engine_v2.docking import (  # noqa: E402
    FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
    FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT,
    FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
    FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT,
    POCKET_CENTER_BASELINE_MODE,
    UNIFORM_FALLBACK_MODE,
    UNIFORM_V3_ENSEMBLE_MODE,
    ConformerPreparationConfig,
    DockingAuthorityError,
    DockingBudget,
    DockingScoreDescriptor,
    DockingScope,
    GuidedPlacementPolicy,
    PocketDefinition,
    ScoreDirection,
    build_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    generate_fixed_source_bound_conformer_docking_proposals,
    prepare_source_bound_conformer_ensemble,
    run_authenticated_guided_placement_search,
)
from betelgeuze_engine_v2.docking import guided_placement as guided_module  # noqa: E402
from betelgeuze_engine_v2.io import parse_sdf_v2000  # noqa: E402


class _FixedProfileScorer:
    scorer_id = "fixed-profile-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="fixed-profile-test-score",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_only",
        calibrated=False,
    )

    def __init__(self, problem_fingerprint_sha256: str) -> None:
        self.problem_fingerprint_sha256 = problem_fingerprint_sha256

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def _source_sdf_bytes() -> bytes:
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCCCCC"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 918273
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    if AllChem.MMFFHasAllMoleculeParams(molecule):
        AllChem.MMFFOptimizeMolecule(molecule, maxIters=200)
    else:
        AllChem.UFFOptimizeMolecule(molecule, maxIters=200)
    block = Chem.MolToMolBlock(molecule, includeStereo=True)
    return (block.rstrip() + "\n$$$$\n").encode("ascii")


@pytest.fixture(scope="module")
def fixed_profile_case():
    source_bytes = _source_sdf_bytes()
    parsed = parse_sdf_v2000(
        source_bytes,
        source_id="fixed-source-bound-profile-ligand",
        dtype=torch.float64,
        device="cpu",
    )
    ligand = replace(
        parsed,
        atoms=tuple(replace(atom, partial_charge_e=0.0) for atom in parsed.atoms),
    )
    receptor = replace(
        parsed,
        system_id="fixed-source-bound-profile-receptor",
        provenance=replace(
            parsed.provenance,
            source_id="fixed-source-bound-profile-receptor",
            source_sha256="b" * 64,
        ),
    )
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="fixed-source-bound-profile-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="fixed-source-bound-profile-test-frame",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    authority = build_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=4.0,
    )
    context = build_guided_placement_context(
        authority,
        receptor,
        ligand,
    )
    ensemble = prepare_source_bound_conformer_ensemble(
        ligand,
        source_bytes,
        config=ConformerPreparationConfig(
            candidate_count=12,
            selected_count=4,
            random_seed=24680,
            max_optimization_iterations=200,
            energy_window_kcal_mol=20.0,
            diversity_rmsd_angstrom=0.1,
        ),
    )
    budget = DockingBudget(
        candidate_count=FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
        top_k=5,
        max_torsions=64,
        translation_radius_angstrom=9.0,
        seed=901,
    )
    return authority, receptor, ligand, context, ensemble, budget


def test_fixed_source_bound_profile_layout_lineage_and_tamper_rejection(
    fixed_profile_case,
    monkeypatch,
) -> None:
    authority, receptor, ligand, context, ensemble, budget = fixed_profile_case
    original_generator = guided_module.generate_pocket_centered_docking_proposals
    captured_baselines = []

    def capture_baseline(*args, **kwargs):
        result = original_generator(*args, **kwargs)
        captured_baselines.append(result[0])
        return result

    monkeypatch.setattr(
        guided_module,
        "generate_pocket_centered_docking_proposals",
        capture_baseline,
    )
    proposals, guided_receipt, development_receipt = (
        generate_fixed_source_bound_conformer_docking_proposals(
            authority,
            budget,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            source_conformer_ensemble=ensemble,
        )
    )
    repeated, repeated_guided, repeated_development = (
        generate_fixed_source_bound_conformer_docking_proposals(
            authority,
            budget,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            source_conformer_ensemble=ensemble,
        )
    )
    baseline = captured_baselines[0]
    retained_indices = (
        *range(FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT),
        *range(
            FIXED_SOURCE_BOUND_CONFORMER_SOURCE_START,
            FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT,
        ),
    )

    assert len(proposals) == FIXED_SOURCE_BOUND_CONFORMER_CANDIDATE_COUNT
    assert guided_receipt.proposal_modes == (
        (POCKET_CENTER_BASELINE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_CENTERED_COUNT
        + (UNIFORM_V3_ENSEMBLE_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
        + (UNIFORM_FALLBACK_MODE,) * FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT
    )
    assert tuple(guided_receipt.ensemble_source_proposal_indices[8:36]) == tuple(
        range(36, 64)
    )
    assert all(proposals[index] is baseline[index] for index in retained_indices)
    assert tuple(row.fingerprint_sha256 for row in proposals) == tuple(
        row.fingerprint_sha256 for row in repeated
    )
    assert guided_receipt.receipt_sha256 == repeated_guided.receipt_sha256
    assert development_receipt.receipt_sha256 == (repeated_development.receipt_sha256)

    scorer = _FixedProfileScorer(authority.problem.fingerprint_sha256)
    search_result = run_authenticated_guided_placement_search(
        authority,
        budget,
        scorer,
        context,
        receptor_system=receptor,
        ligand_system=ligand,
        diversity_rmsd_angstrom=0.0,
        precomputed_proposals=proposals,
        precomputed_guided_receipt=guided_receipt,
        precomputed_provenance_receipt=development_receipt,
    )
    assert search_result.guided_receipt is guided_receipt
    assert tuple(
        row.proposal_fingerprint_sha256
        for row in search_result.authenticated_search_result.search_result.rows
    ) == guided_receipt.proposal_fingerprint_sha256s

    forged_guided_receipt = replace(
        guided_receipt,
        guided_policy_sha256="0" * 64,
        proposal_modes=(UNIFORM_FALLBACK_MODE,) * len(proposals),
        ensemble_source_proposal_indices=(None,) * len(proposals),
    )
    with pytest.raises(DockingAuthorityError, match="provenance is cross-wired"):
        run_authenticated_guided_placement_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            diversity_rmsd_angstrom=0.0,
            precomputed_proposals=proposals,
            precomputed_guided_receipt=forged_guided_receipt,
            precomputed_provenance_receipt=development_receipt,
        )

    forged_feature_counts = dict(guided_receipt.feature_counts)
    forged_feature_name = next(iter(forged_feature_counts))
    forged_feature_counts[forged_feature_name] += 1
    forged_feature_receipt = replace(
        guided_receipt,
        feature_counts=forged_feature_counts,
    )
    forged_feature_provenance = replace(
        development_receipt,
        guided_receipt=forged_feature_receipt,
    )
    with pytest.raises(DockingAuthorityError, match="authority is cross-wired"):
        run_authenticated_guided_placement_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            diversity_rmsd_angstrom=0.0,
            precomputed_proposals=proposals,
            precomputed_guided_receipt=forged_feature_receipt,
            precomputed_provenance_receipt=forged_feature_provenance,
        )
    with pytest.raises(DockingAuthorityError, match="reject a second policy"):
        run_authenticated_guided_placement_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            policy=GuidedPlacementPolicy(),
            precomputed_proposals=proposals,
            precomputed_guided_receipt=guided_receipt,
            precomputed_provenance_receipt=development_receipt,
        )

    copied_source_torsion_count = 0
    conformer_count = len(ensemble.records)
    for offset, lineage in enumerate(development_receipt.lineage_rows):
        proposal_index = 8 + offset
        source_index = 36 + offset
        conformer_rank = offset % conformer_count
        conformer = ensemble.system.coordinates[conformer_rank]
        source = baseline[source_index]
        expected_coordinates = (
            conformer - conformer.mean(dim=0)
        ) @ source.rotation.T + source.coordinates.mean(dim=0)
        expected_torsion_metadata = (
            guided_module._source_relative_rotor_torsion_metadata(
                authority,
                ensemble.source_system,
                conformer,
            )
        )

        assert lineage.proposal_index == proposal_index
        assert lineage.source_proposal_index == source_index
        assert lineage.conformer_rank == conformer_rank
        assert lineage.conformer_id == ensemble.records[conformer_rank].conformer_id
        assert (
            proposals[proposal_index].candidate_id
            == baseline[proposal_index].candidate_id
        )
        assert torch.allclose(
            proposals[proposal_index].coordinates,
            expected_coordinates,
            atol=1.0e-12,
            rtol=0.0,
        )
        assert torch.equal(
            proposals[proposal_index].torsion_angles,
            expected_torsion_metadata,
        )
        copied_source_torsion_count += int(
            torch.equal(
                proposals[proposal_index].torsion_angles,
                source.torsion_angles,
            )
        )
        proposals[proposal_index].assert_integrity()
    assert copied_source_torsion_count < FIXED_SOURCE_BOUND_CONFORMER_VARIANT_COUNT

    document = development_receipt.to_dict()
    assert document["development_only"] is True
    assert document["stage0_eligible"] is False
    assert document["fresh_execution_authorized"] is False
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False
    assert document["guided_placement_receipt_sha256"] == (
        guided_receipt.receipt_sha256
    )

    tampered_lineage = replace(
        development_receipt.lineage_rows[0],
        source_proposal_fingerprint_sha256="0" * 64,
    )
    with pytest.raises(DockingAuthorityError, match="lineage is cross-wired"):
        replace(
            development_receipt,
            lineage_rows=(
                tampered_lineage,
                *development_receipt.lineage_rows[1:],
            ),
        )
    tampered_ensemble = document["source_conformer_ensemble"]
    tampered_ensemble["conformers"][0]["conformer_id"] = "1" * 64
    matching_tampered_lineage = replace(
        development_receipt.lineage_rows[0],
        conformer_id="1" * 64,
    )
    with pytest.raises(
        DockingAuthorityError,
        match="rows are not bound to ensemble evidence",
    ):
        replace(
            development_receipt,
            source_conformer_ensemble_document=tampered_ensemble,
            lineage_rows=(
                matching_tampered_lineage,
                *development_receipt.lineage_rows[1:],
            ),
        )
    with pytest.raises(DockingAuthorityError, match="exactly 64 candidates"):
        generate_fixed_source_bound_conformer_docking_proposals(
            authority,
            replace(budget, candidate_count=63),
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            source_conformer_ensemble=ensemble,
        )
