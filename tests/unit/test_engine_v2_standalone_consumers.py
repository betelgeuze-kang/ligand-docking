from __future__ import annotations

from dataclasses import replace

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
    CANONICAL_COMPONENT_MANIFEST_SHA256,
    DIAGNOSTIC_BENCHMARK_SCOPE,
    DockingScope,
    PocketDefinition,
    SYNTHETIC_D0_BENCHMARK_CASE_ID,
    SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
    SYNTHETIC_D0_FIXTURE_REQUEST_SHA256,
    SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST,
    StandaloneDiagnosticBenchmarkAdapter,
    StandaloneDockingCliAdapter,
    StandaloneDockingPythonApi,
    StandaloneProductShadowAdapter,
    canonical_standalone_component_manifest,
    repository_synthetic_d0_fixture_admission,
    run_standalone_docking,
)
from betelgeuze_engine_v2.docking import consumers as consumer_module  # noqa: E402


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
    api = StandaloneDockingPythonApi().run(request)
    benchmark = StandaloneDiagnosticBenchmarkAdapter().run(
        request,
        scope=DIAGNOSTIC_BENCHMARK_SCOPE,
        case_id=SYNTHETIC_D0_BENCHMARK_CASE_ID,
    )
    shadow = StandaloneProductShadowAdapter().run(
        request,
        operator_context_id=SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST[0],
    )
    cli = StandaloneDockingCliAdapter().run(request)
    direct = run_standalone_docking(request)

    receipts = {
        api.result.receipt_sha256,
        benchmark.result.receipt_sha256,
        shadow.result.receipt_sha256,
        cli.result.receipt_sha256,
        direct.result.receipt_sha256,
    }
    assert len(receipts) == 1
    for envelope in (api, benchmark, shadow, cli, direct):
        document = envelope.to_dict()
        assert document["fixture_manifest_sha256"] == (
            SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
        )
        assert document["fixture_request_sha256"] == (
            SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
        )
        assert document["canonical_component_manifest_sha256"] == (
            CANONICAL_COMPONENT_MANIFEST_SHA256
        )
        assert document["blockers"] == list(envelope.result.blockers)
        assert document["failure_count"] == envelope.result.failure_count
        assert document["top_proposal_indices"] == list(
            envelope.result.top_proposal_indices
        )
        assert document["top_k"]["existing_rank_auto_change_allowed"] is False
        assert document["abstention"]["reason_code"] in {
            "not_abstained",
            "all_candidates_failed",
            "insufficient_selection_eligible_candidates",
        }
        assert len(document["candidate_dispositions"]) == 2
        assert all(
            row["candidate_removed_from_denominator"] is False
            and row["existing_rank_changed"] is False
            and row["customer_pose_emitted"] is False
            and row["product_state_mutated"] is False
            and row["claim_safe"] is False
            for row in document["candidate_dispositions"]
        )
        assert document["existing_rank_auto_change_allowed"] is False
        assert document["customer_pose_emission_allowed"] is False
        assert document["production_claim_allowed"] is False
        assert document["product_state_mutated"] is False
        assert document["external_reservation_allowed"] is False
        assert document["external_reservation_requested"] is False
        assert document["molecular_experiment_authorized"] is False
        assert document["real_molecular_execution_allowed"] is False
        assert document["authority"] is False
    assert shadow.to_dict()["evidence_display_allowed"] is True
    assert shadow.to_dict()["operator_second_opinion_allowed"] is True
    assert api.to_dict()["operator_second_opinion_allowed"] is False


def test_repository_admission_and_component_manifest_are_exact() -> None:
    request = _request()
    admission = repository_synthetic_d0_fixture_admission()
    admission.assert_request(request)

    assert admission.manifest_sha256 == SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
    assert admission.request_sha256 == SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
    assert request.request_sha256 == SYNTHETIC_D0_FIXTURE_REQUEST_SHA256
    assert canonical_standalone_component_manifest()["manifest_sha256"] == (
        CANONICAL_COMPONENT_MANIFEST_SHA256
    )


def test_public_consumers_do_not_accept_arbitrary_dependency_injection() -> None:
    from betelgeuze_engine_v2 import DockingPipeline

    with pytest.raises(TypeError):
        StandaloneDockingPythonApi(DockingPipeline())
    with pytest.raises(TypeError):
        StandaloneDiagnosticBenchmarkAdapter(DockingPipeline())
    with pytest.raises(TypeError):
        StandaloneProductShadowAdapter(DockingPipeline())
    with pytest.raises(TypeError):
        StandaloneDockingCliAdapter(DockingPipeline())


@pytest.mark.parametrize(
    "scope",
    ["arbitrary", "historical_9_case", "fresh_128", "public_benchmark"],
)
def test_benchmark_adapter_rejects_non_synthetic_scopes_before_run(
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "build_canonical_standalone_pipeline",
        lambda: (_ for _ in ()).throw(AssertionError("pipeline was constructed")),
    )
    with pytest.raises(DockingPipelineError, match="synthetic D0"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            _request(),
            scope=scope,
            case_id=SYNTHETIC_D0_BENCHMARK_CASE_ID,
        )


def test_benchmark_adapter_rejects_arbitrary_case_id_before_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "build_canonical_standalone_pipeline",
        lambda: (_ for _ in ()).throw(AssertionError("pipeline was constructed")),
    )
    with pytest.raises(DockingPipelineError, match="exact synthetic D0 fixture case"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            _request(),
            scope=DIAGNOSTIC_BENCHMARK_SCOPE,
            case_id="arbitrary-case",
        )


def test_arbitrary_request_is_rejected_before_pipeline_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "build_canonical_standalone_pipeline",
        lambda: (_ for _ in ()).throw(AssertionError("pipeline was constructed")),
    )
    arbitrary = replace(_request(), seed=4302)
    with pytest.raises(DockingPipelineError, match="exact repository-owned"):
        StandaloneDockingPythonApi().run(arbitrary)


def test_benchmark_and_shadow_reject_fixed64_until_authority_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "build_canonical_standalone_pipeline",
        lambda: (_ for _ in ()).throw(AssertionError("pipeline was constructed")),
    )
    request = _request(fixed64=True)
    with pytest.raises(DockingPipelineError, match="exact repository-owned"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            request,
            scope=DIAGNOSTIC_BENCHMARK_SCOPE,
            case_id=SYNTHETIC_D0_BENCHMARK_CASE_ID,
        )
    with pytest.raises(DockingPipelineError, match="exact repository-owned"):
        StandaloneProductShadowAdapter().run(
            request,
            operator_context_id=SYNTHETIC_D0_SHADOW_CONTEXT_ALLOWLIST[0],
        )


def test_product_shadow_rejects_non_allowlisted_context_before_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "build_canonical_standalone_pipeline",
        lambda: (_ for _ in ()).throw(AssertionError("pipeline was constructed")),
    )
    with pytest.raises(DockingPipelineError, match="not allowlisted"):
        StandaloneProductShadowAdapter().run(
            _request(),
            operator_context_id="arbitrary-operator",
        )
