from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    DIAGNOSTIC_BENCHMARK_SCOPE,
    DockingScope,
    PocketDefinition,
    StandaloneDiagnosticBenchmarkAdapter,
    StandaloneDockingPythonApi,
    StandaloneProductShadowAdapter,
    run_standalone_docking,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-consumer-fixture",
        parser_version="1.0.0",
    )


def _system(*, receptor: bool) -> AllAtomSystem:
    elements = ("O", "N", "H", "C", "H") if receptor else ("C", "N", "H", "O", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4) if receptor else (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        ([2.0, 0.0, 0.0], [3.0, 3.0, 0.0], [2.5, 2.5, 0.0], [-2.0, 3.0, 0.0], [6.0, 6.0, 0.0])
        if receptor
        else ([-2.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-2.0, 0.0, 0.0], [-3.0, 0.0, 0.0])
    )
    role = "receptor" if receptor else "ligand"
    return AllAtomSystem(
        system_id=f"standalone-consumer-{role}",
        atoms=tuple(
            Atom(
                index=index,
                name=f"{role[0].upper()}{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(Bond(index=0, atom_i=1, atom_j=2),)
        if receptor
        else (
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=1, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
            Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            Residue(
                index=0,
                name="REC" if receptor else "LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="polymer" if receptor else "non-polymer",
                hetero=not receptor,
            ),
        ),
        chains=(Chain(index=0, chain_id="A" if receptor else "L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(role, ("b" if receptor else "a") * 64),
    )


def _request(*, fixed64: bool = False) -> DockingPipelineRequestV1:
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="consumer-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    profile = (
        DockingPipelineProfileV1()
        if fixed64
        else DockingPipelineProfileV1.synthetic_test(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            max_refinement_steps=1,
        )
    )
    return DockingPipelineRequestV1(
        receptor_system=_system(receptor=True),
        ligand_system=_system(receptor=False),
        pocket=pocket,
        seed=4301,
        profile=profile,
    )


def test_all_consumers_bind_the_same_unmodified_core_receipt() -> None:
    request = _request()
    api = StandaloneDockingPythonApi().run(request, context_id="api-test")
    benchmark = StandaloneDiagnosticBenchmarkAdapter().run(
        request,
        scope=DIAGNOSTIC_BENCHMARK_SCOPE,
        case_id="toy-001",
    )
    shadow = StandaloneProductShadowAdapter().run(
        request,
        operator_context_id="operator-test",
    )
    direct = run_standalone_docking(request)

    receipts = {
        api.result.receipt_sha256,
        benchmark.result.receipt_sha256,
        shadow.result.receipt_sha256,
        direct.receipt_sha256,
    }
    assert len(receipts) == 1
    assert shadow.to_dict()["evidence_display_allowed"] is True
    assert shadow.to_dict()["operator_second_opinion_allowed"] is True
    assert shadow.to_dict()["existing_rank_auto_change_allowed"] is False
    assert shadow.to_dict()["customer_pose_emission_allowed"] is False
    assert shadow.to_dict()["production_claim_allowed"] is False
    assert shadow.to_dict()["product_state_mutated"] is False


@pytest.mark.parametrize("scope", ["historical_9_case", "fresh_128", "public_benchmark"])
def test_benchmark_adapter_rejects_non_synthetic_scopes(scope: str) -> None:
    with pytest.raises(DockingPipelineError, match="synthetic D0"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            _request(),
            scope=scope,
            case_id="forbidden",
        )


def test_benchmark_and_shadow_reject_fixed64_until_authority_exists() -> None:
    request = _request(fixed64=True)
    with pytest.raises(DockingPipelineError, match="synthetic profile"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            request,
            scope=DIAGNOSTIC_BENCHMARK_SCOPE,
            case_id="fixed64",
        )
    with pytest.raises(DockingPipelineError, match="synthetic test profile"):
        StandaloneProductShadowAdapter().run(
            request,
            operator_context_id="fixed64",
        )
