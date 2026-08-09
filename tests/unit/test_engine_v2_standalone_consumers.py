from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    Residue,
    StructureProvenance,
    SYNTHETIC_ONLY_ACKNOWLEDGMENT,
    repository_synthetic_d0_fixture_admission,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    DIAGNOSTIC_BENCHMARK_SCOPE,
    DockingScope,
    PocketDefinition,
    SEALED_CANONICAL_COMPONENT_BINDING,
    StandaloneDiagnosticBenchmarkAdapter,
    StandaloneDockingPythonApi,
    StandaloneProductShadowAdapter,
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
        (
            [2.0, 0.0, 0.0],
            [3.0, 3.0, 0.0],
            [2.5, 2.5, 0.0],
            [-2.0, 3.0, 0.0],
            [6.0, 6.0, 0.0],
        )
        if receptor
        else (
            [-2.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [-2.0, 0.0, 0.0],
            [-3.0, 0.0, 0.0],
        )
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
        chains=(
            Chain(
                index=0,
                chain_id="A" if receptor else "L",
                residue_indices=(0,),
            ),
        ),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(role, ("b" if receptor else "a") * 64),
    )


def _request() -> DockingPipelineRequestV1:
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
    return DockingPipelineRequestV1(
        receptor_system=_system(receptor=True),
        ligand_system=_system(receptor=False),
        pocket=pocket,
        seed=4301,
        synthetic_only_acknowledgment=SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        fixture_admission=repository_synthetic_d0_fixture_admission(),
        profile=DockingPipelineProfileV1(),
        test_only=True,
    )


@pytest.fixture(scope="module")
def exact_core_result():
    return DockingPipeline().run(_request())


def _install_core_spy(
    monkeypatch: pytest.MonkeyPatch,
    exact_core_result,
) -> list[DockingPipelineRequestV1]:
    calls: list[DockingPipelineRequestV1] = []

    class _ExactNoArgumentCore:
        def __init__(self) -> None:
            pass

        def run(self, request: DockingPipelineRequestV1):
            calls.append(request)
            return exact_core_result

    monkeypatch.setattr(consumer_module, "DockingPipeline", _ExactNoArgumentCore)
    return calls


def test_all_consumers_expose_the_same_unmodified_fixed64_core_receipt(
    monkeypatch: pytest.MonkeyPatch,
    exact_core_result,
) -> None:
    calls = _install_core_spy(monkeypatch, exact_core_result)
    request = _request()
    admission = repository_synthetic_d0_fixture_admission()

    api = StandaloneDockingPythonApi().run(request)
    benchmark = StandaloneDiagnosticBenchmarkAdapter().run(
        request,
        scope=DIAGNOSTIC_BENCHMARK_SCOPE,
        case_id=admission.benchmark_case_id,
    )
    shadow = StandaloneProductShadowAdapter().run(
        request,
        operator_context_id=admission.product_shadow_context_allowlist[0],
    )
    direct = run_standalone_docking(request)

    assert calls == [request, request, request, request]
    assert direct is exact_core_result
    assert (
        exact_core_result.component_binding_mode == SEALED_CANONICAL_COMPONENT_BINDING
    )
    assert len(exact_core_result.candidates) == 64
    assert exact_core_result.request.profile.top_k == 5
    assert {
        api.result.receipt_sha256,
        benchmark.result.receipt_sha256,
        shadow.result.receipt_sha256,
        direct.receipt_sha256,
    } == {exact_core_result.receipt_sha256}

    for envelope in (api, benchmark, shadow):
        document = envelope.to_dict()
        assert document["pipeline_result"] == exact_core_result.to_dict()
        assert document["pipeline_result_receipt_sha256"] == (
            exact_core_result.receipt_sha256
        )
        assert document["candidate_count"] == 64
        assert document["top_k"] == 5
        assert document["top_proposal_indices"] == list(
            exact_core_result.top_proposal_indices
        )
        assert document["failure_count"] == exact_core_result.failure_count
        assert document["blockers"] == list(exact_core_result.blockers)
        assert document["pipeline_result_embedded_unmodified"] is True
        assert document["pipeline_result_rewritten"] is False
        assert document["rank_or_selection_rewritten"] is False
        assert document["benchmark_dataset_accessed"] is False
        assert document["authority"] is False
        assert document["claim_safe"] is False
        for field in consumer_module._AUTHORITY_FALSE_FIELDS:
            assert document[field] is False

    assert shadow.to_dict()["operator_second_opinion_allowed"] is True
    assert api.to_dict()["operator_second_opinion_allowed"] is False
    assert benchmark.to_dict()["operator_second_opinion_allowed"] is False


@pytest.mark.parametrize(
    ("scope", "case_id"),
    (
        ("historical_9_case", "synthetic-d0-standalone-001"),
        ("fresh_128", "synthetic-d0-standalone-001"),
        ("public_benchmark", "synthetic-d0-standalone-001"),
        (DIAGNOSTIC_BENCHMARK_SCOPE, "arbitrary-case"),
    ),
)
def test_benchmark_rejects_non_exact_scope_before_core_construction(
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    case_id: str,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "DockingPipeline",
        lambda: (_ for _ in ()).throw(AssertionError("core constructed")),
    )
    with pytest.raises(DockingPipelineError, match="exact synthetic D0"):
        StandaloneDiagnosticBenchmarkAdapter().run(
            _request(),
            scope=scope,
            case_id=case_id,
        )


def test_shadow_rejects_unadmitted_operator_context_before_core_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "DockingPipeline",
        lambda: (_ for _ in ()).throw(AssertionError("core constructed")),
    )
    with pytest.raises(DockingPipelineError, match="outside exact synthetic D0"):
        StandaloneProductShadowAdapter().run(
            _request(),
            operator_context_id="production/customer/rank-mutator",
        )


def test_public_consumers_have_no_dependency_injection_constructor() -> None:
    injected = DockingPipeline()
    with pytest.raises(TypeError):
        StandaloneDockingPythonApi(injected)
    with pytest.raises(TypeError):
        StandaloneDiagnosticBenchmarkAdapter(injected)
    with pytest.raises(TypeError):
        StandaloneProductShadowAdapter(injected)


def test_request_identity_drift_fails_closed_before_core_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_module,
        "DockingPipeline",
        lambda: (_ for _ in ()).throw(AssertionError("core constructed")),
    )
    with pytest.raises(DockingPipelineError, match="repository-owned"):
        replace(_request(), seed=4302)
    with pytest.raises(TypeError, match="exact DockingPipelineRequestV1"):
        StandaloneDockingPythonApi().run(object())


def test_consumer_module_has_no_duplicate_manifest_or_recorder_implementation() -> None:
    source = Path(consumer_module.__file__).read_text(encoding="utf-8")

    assert "synthetic_d0_fixture_admission.json" not in source
    assert "CanonicalPipelineEvidenceRecorder" not in source
    assert "_CanonicalPipelineEvidenceRecorder" not in source
    assert "DockingPipeline().run(request)" in source


def test_consumer_envelope_detects_surface_metadata_tampering(
    monkeypatch: pytest.MonkeyPatch,
    exact_core_result,
) -> None:
    _install_core_spy(monkeypatch, exact_core_result)
    envelope = StandaloneDockingPythonApi().run(_request())

    object.__setattr__(envelope, "evidence_display_allowed", False)
    with pytest.raises(DockingPipelineError, match="envelope changed"):
        _ = envelope.receipt_sha256
