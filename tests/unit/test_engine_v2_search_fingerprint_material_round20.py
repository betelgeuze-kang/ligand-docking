from __future__ import annotations

import hashlib
import json

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID,
    DOCKING_SEARCH_RESULT_SCHEMA_ID,
    SEARCH_FINGERPRINT_MATERIAL_SHA256,
    recompute_search_fingerprint_sha256,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    DockingScoreDescriptor,
    PoseValidityConfig,
    PoseValidityContext,
    ScoreDirection,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [
                [0.0, 0.0, 0.0],
                [1.2, 0.0, 0.0],
                [1.0, 0.5, 0.0],
                [0.8, 0.5, 0.4],
            ],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1, 2], dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * 4,
            dtype=torch.float64,
        ),
        rotatable_mask=torch.tensor([False, False, True, True]),
    )


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


def _context(problem: DockingProblemIdentity) -> PoseValidityContext:
    reference = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=2,
            seed=173,
        ),
        problem=problem,
    )[0].coordinates
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        excluded_nonbonded_pairs=((0, 1), (1, 2), (2, 3)),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]],
            dtype=torch.float64,
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(
            pocket_radius_angstrom=100.0,
            ligand_self_clash_angstrom=0.0,
            receptor_ligand_clash_angstrom=0.0,
        ),
    )


_PROBLEM_FINGERPRINT = _problem().fingerprint_sha256


class _Scorer:
    scorer_id = "search-material-coordinate-sum"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    problem_fingerprint_sha256 = _PROBLEM_FINGERPRINT
    implementation_source_sha256 = "d" * 64
    config_fingerprint_sha256 = "e" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="search-material-coordinate-sum",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_internal_coordinate_sum",
        calibrated=False,
    )

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def _run(
    *,
    threshold: float,
    permutations=((0, 1, 2, 3),),
):
    problem = _problem()
    return run_bounded_docking_search(
        _space(),
        DockingBudget(
            candidate_count=5,
            top_k=3,
            max_torsions=2,
            translation_radius_angstrom=1.0,
            seed=179,
        ),
        _Scorer(),
        problem=problem,
        validity_context=_context(problem),
        diversity_rmsd_angstrom=threshold,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=permutations,
    )


def test_search_result_exposes_one_recomputable_schema_v6_projection() -> None:
    assert len(SEARCH_FINGERPRINT_MATERIAL_SHA256) == 64
    result = _run(threshold=0.5)
    document = result.to_dict()
    assert document["schema_id"] == DOCKING_SEARCH_RESULT_SCHEMA_ID
    assert document["search_fingerprint_schema_id"] == (
        DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID
    )
    assert document["search_fingerprint_fully_recomputable"] is True
    material = document["search_fingerprint_material"]
    assert material["schema_id"] == DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID
    assert material["diversity_rmsd_angstrom_binary64_hex"] == (0.5).hex()
    assert _canonical_sha256(material) == result.search_fingerprint_sha256
    assert recompute_search_fingerprint_sha256(result) == (
        result.search_fingerprint_sha256
    )
    assert document["selected_count"] == document["top_count"]
    assert document["claim_safe"] is False


def test_diversity_threshold_changes_search_identity_without_changing_proposals() -> None:
    first = _run(threshold=0.0)
    second = _run(threshold=1.25)
    assert [row.proposal_fingerprint_sha256 for row in first.rows] == [
        row.proposal_fingerprint_sha256 for row in second.rows
    ]
    assert first.search_fingerprint_sha256 != second.search_fingerprint_sha256
    assert first.search_fingerprint_material[
        "diversity_rmsd_angstrom_binary64_hex"
    ] == (0.0).hex()
    assert second.search_fingerprint_material[
        "diversity_rmsd_angstrom_binary64_hex"
    ] == (1.25).hex()


def test_symmetry_mapping_set_is_public_and_fingerprint_bound() -> None:
    identity_only = _run(
        threshold=0.5,
        permutations=((0, 1, 2, 3),),
    )
    with_swap = _run(
        threshold=0.5,
        permutations=((0, 1, 2, 3), (1, 0, 2, 3)),
    )
    material = with_swap.search_fingerprint_material
    assert material["diversity_metric"] == "symmetry_aware_direct_rmsd"
    assert material["symmetry_permutation_count"] == 2
    assert material["symmetry_permutations"] == {
        "atom_count": 4,
        "mappings": [[0, 1, 2, 3], [1, 0, 2, 3]],
    }
    assert identity_only.search_fingerprint_sha256 != (
        with_swap.search_fingerprint_sha256
    )


def test_public_material_detects_post_result_identity_tamper() -> None:
    result = _run(threshold=0.5)
    object.__setattr__(result, "search_fingerprint_sha256", "9" * 64)
    with pytest.raises(Exception, match="does not match"):
        recompute_search_fingerprint_sha256(result)
    with pytest.raises(Exception, match="does not match"):
        result.to_dict()
