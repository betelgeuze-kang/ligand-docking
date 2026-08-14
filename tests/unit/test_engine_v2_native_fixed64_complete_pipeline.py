from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking.native_fixed64_consumers import (
    NativeFixed64CliAdapter,
    NativeFixed64ConsumerError,
    NativeFixed64DiagnosticBenchmarkAdapter,
    NativeFixed64EvidenceV1,
    NativeFixed64EvidenceV2,
    NativeFixed64EvidenceV3,
    NativeFixed64PreparedSessionV1,
    NativeFixed64ProductShadowAdapter,
    NativeFixed64PythonApi,
    NativeRepositorySyntheticD0EvidenceV1,
    NativeRepositorySyntheticD0PreparedSessionV1,
    REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT,
    prepare_native_fixed64_session,
    prepare_repository_synthetic_d0_session,
    run_native_fixed64_surface,
)
import betelgeuze_engine_v2.docking.native_fixed64_consumers as native_consumers
from betelgeuze_engine_v2.docking.native_cpu_parity import (
    NativeCpuParityError,
    NativeRepositorySyntheticD0CpuParityReceiptV1,
    run_repository_synthetic_d0_cpu_parity,
)
from betelgeuze_engine_v2.standalone_cli import main as standalone_main


def _digest(marker: int) -> str:
    return f"{marker:02x}" * 32


class _FloatProtocolObject:
    def __float__(self) -> float:
        raise AssertionError("v3 must not invoke caller numeric protocols")


class _ListSubclass(list):
    pass


class _DictSubclass(dict):
    pass


class _StringSubclass(str):
    def __hash__(self) -> int:
        raise AssertionError(
            "prepared session must reject before caller string hashing"
        )


class _StringProtocolObject:
    def __eq__(self, _other: object) -> bool:
        raise AssertionError(
            "prepared session must reject before caller string comparison"
        )


class _StringKeySubclass(str):
    __hash__ = str.__hash__

    def __eq__(self, _other: object) -> bool:
        raise AssertionError(
            "prepared session must reject before caller key comparison"
        )


class _DeepcopyTrap:
    def __deepcopy__(self, _memo):
        raise AssertionError("canonical v3 consumer must not deep-copy nested input")


def _source(marker: int, *, source_index: int | None = None, rank: int | None = None):
    row: dict[str, object] = {
        "receipt_sha256": _digest(marker),
        "proposal_sha256": _digest(marker + 64),
        "coordinates_angstrom": [[0.0, 0.0, 0.0]],
    }
    if source_index is not None:
        row["source_index"] = source_index
    if rank is not None:
        row["rank"] = rank
    return row


def _input(*, consumer: str = "api") -> dict[str, object]:
    return {
        "schema_id": ("betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"),
        "consumer": consumer,
        "backend": "rust_cpu",
        "device_ordinal": 0,
        "authority_input_receipt_sha256": _digest(17),
        "source_receipt_sha256": _digest(16),
        "proposal_sha256": _digest(18),
        "prepared_ligand_topology_sha256": _digest(51),
        "prepared_receptor_topology_sha256": _digest(34),
        "receptor_system_sha256": _digest(34),
        "ligand_system_sha256": _digest(51),
        "backend_receipt_sha256": _digest(68),
        "validity_scorer_context_receipt_sha256": _digest(85),
        "contact_policy_sha256": _digest(102),
        "ligand_coordinates_angstrom": [[0.0, 0.0, 0.0]],
        "ligand_vdw_radii_angstrom": [1.5],
        "ligand_heavy_atom_mask": [True],
        "ligand_charge_elementary": [0.2],
        "ligand_epsilon_kcal_per_mol": [0.18],
        "ligand_hydrophobic_mask": [False],
        "ligand_acceptor_mask": [False],
        "receptor_coordinates_angstrom": [
            [4.0, 0.0, 0.0],
            [3.5, 0.0, 0.0],
            [4.0, 1.0, 0.0],
            [4.0, 0.0, 1.0002],
        ],
        "receptor_vdw_radii_angstrom": [1.5] * 4,
        "receptor_charge_elementary": [-0.5, 0.2, 0.3, 0.0],
        "receptor_epsilon_kcal_per_mol": [0.2, 0.18, 0.05, 0.25],
        "receptor_hydrophobic_mask": [False] * 4,
        "receptor_acceptor_mask": [False] * 4,
        "ligand_donors": [],
        "receptor_donors": [],
        "ligand_exclusions": [],
        "rotor_quads": [],
        "bond_pairs": [],
        "chirality_centers": [],
        "parent_atom_index": [-1],
        "rotatable_child_atom_index": [],
        "internal_pairs": [],
        "pocket_center_angstrom": [0.0, 0.0, 0.0],
        "pocket_radius_angstrom": 10.0,
        "pocket_normal": [0.0, 0.0, 1.0],
        "v7_control_sources": [
            _source(index + 1, source_index=index) for index in range(24)
        ],
        "conformer_sources": [
            _source(34 + index, rank=index + 2) for index in range(7)
        ],
        "retained_sources": [
            _source(48 + offset, source_index=index)
            for offset, index in enumerate((36, 45, 54, 63))
        ],
        "feature_geometries": [],
        "feature_geometry_inventory_sha256": "0" * 64,
        "rmsd_threshold_angstrom": 1.5,
        "candidate_modes": ["v2_translation"] * 64,
        "rigid_max_steps": [4] * 64,
        "proposal_is_torsion_eligible": [False] * 64,
        "torsion_max_steps": [0] * 64,
        "baseline_torsion_angles_radians": [0.0] * 64,
        "predeclared_refinement_policy_sha256": _digest(118),
        "predeclared_post_refinement_admission_policy_sha256": _digest(119),
        "test_only": True,
    }


def _input_v2(*, consumer: str = "api") -> dict[str, object]:
    value = _input(consumer=consumer)
    value["schema_id"] = "betelgeuze.engine_v2_native_fixed64_complete_input/2.0.0"
    return value


@pytest.fixture(scope="module")
def native():
    return pytest.importorskip("betelgeuze_engine_v2_native")


def test_package_preloads_native_extension_before_legacy_imports(native) -> None:
    import sys

    assert sys.modules.get("betelgeuze_engine_v2_native") is native
    assert NativeFixed64EvidenceV1 is NativeFixed64EvidenceV2
    assert (
        native.NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID
        == "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"
    )
    assert native.NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID_V2.endswith("/2.0.0")
    assert native.NATIVE_FIXED64_COMPLETE_INPUT_SCHEMA_ID_V3.endswith("/3.0.0")
    assert native.NATIVE_FIXED64_PREPARED_SESSION_SCHEMA_ID_V1.endswith("/1.0.0")


def test_retired_v1_entrypoint_fails_closed(native) -> None:
    with pytest.raises(ValueError, match="v1 is retired"):
        native.native_fixed64_complete_pipeline_v1({})


def test_v2_entrypoint_remains_compatible(native) -> None:
    document = native.native_fixed64_complete_pipeline_v2(_input_v2())

    assert document["schema_id"].endswith("complete_python_evidence/2.0.0")
    assert "prepared_input_projection_sha256" not in document
    evidence = NativeFixed64EvidenceV2(surface="api", _document=document)
    assert evidence.pipeline_receipt_sha256 == document["pipeline_receipt_sha256"]

    with pytest.raises(NativeFixed64ConsumerError, match="canonical consumers require"):
        NativeFixed64PythonApi().run(_input_v2())


def test_complete_native_work_releases_the_gil_before_pipeline_execution() -> None:
    source = Path("rust_engine_v2/src/complete_fixed64_pipeline.rs").read_text(
        encoding="utf-8"
    )
    run_once = source.index("fn run_once(&self)")
    context_creation = source.index("let pipeline = self.create_pipeline()?", run_once)
    pipeline_run = source.index("self.run(&pipeline)", context_creation)
    allow_threads = source.index(".allow_threads(move || input.run_once())")
    receipt_conversion = source.index("receipt_to_python(", allow_threads)

    assert run_once < context_creation < pipeline_run
    assert allow_threads < receipt_conversion


def test_prepared_session_reuses_one_native_context_without_caching_science(
    native,
) -> None:
    source = _input(consumer="cli")
    original = deepcopy(source)
    session = prepare_native_fixed64_session(source)

    assert isinstance(session, NativeFixed64PreparedSessionV1)
    assert source == original
    metadata = session.describe()
    assert metadata["schema_id"].endswith("prepared_session/1.0.0")
    assert metadata["default_consumer"] == "cli"
    assert metadata["backend"] == "rust_cpu"
    assert metadata["candidate_denominator"] == 64
    assert metadata["persistent_native_context"] is True
    assert metadata["context_reused_across_runs"] is True
    assert metadata["scientific_result_cached"] is False
    assert metadata["session_thread_confined"] is True
    assert metadata["result_dependent_input_consumed"] is False
    for field in (
        "reservation_authorized",
        "molecular_execution_authorized",
        "benchmark_execution_authorized",
        "scientific_claim_authorized",
        "hip_device_execution_authorized",
        "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized",
        "production_claim_authorized",
    ):
        assert metadata[field] is False
    expected_session_receipt = hashlib.sha256(
        b"betelgeuze.engine-v2.native-fixed64-prepared-session/v1\0"
        + len(metadata["pipeline_id"]).to_bytes(8, "big")
        + metadata["pipeline_id"].encode("ascii")
        + bytes.fromhex(metadata["prepared_input_projection_sha256"])
    ).hexdigest()
    assert metadata["prepared_session_receipt_sha256"] == expected_session_receipt
    assert session.prepared_session_receipt_sha256 == expected_session_receipt

    results = {
        surface: session.run(surface=surface)
        for surface in ("cli", "benchmark", "api", "product_shadow")
    }
    rerun = session.run(surface="cli")
    stateless = native.native_fixed64_complete_pipeline_v3(_input(consumer="cli"))

    assert rerun.to_dict() == results["cli"].to_dict() == stateless
    assert len({item.pipeline_receipt_sha256 for item in results.values()}) == 1
    assert len({item.prepared_input_receipt_sha256 for item in results.values()}) == 1
    assert len({item.consumer_view_receipt_sha256 for item in results.values()}) == 4
    assert (
        results["product_shadow"].to_dict()["operator_second_opinion_authorized"]
        is True
    )


def test_prepared_session_owns_input_after_bounded_native_copy(native) -> None:
    source = _input(consumer="api")
    session = prepare_native_fixed64_session(source)
    expected = native.native_fixed64_complete_pipeline_v3(deepcopy(source))

    source["ligand_charge_elementary"][0] = -9.0
    source["ligand_coordinates_angstrom"][0][0] = 99.0
    source["v7_control_sources"][0]["coordinates_angstrom"][0][0] = 88.0

    assert session.run(surface="api").to_dict() == expected


def test_prepared_session_rejects_unknown_consumer(native) -> None:
    session = prepare_native_fixed64_session(_input())

    with pytest.raises(NativeFixed64ConsumerError, match="unsupported"):
        session.run(surface="production")


def test_prepared_session_rejects_surface_subclass_before_protocols(native) -> None:
    session = prepare_native_fixed64_session(_input())
    surface = _StringSubclass("api")

    with pytest.raises(NativeFixed64ConsumerError, match="unsupported"):
        session.run(surface=surface)  # type: ignore[arg-type]
    with pytest.raises(NativeFixed64ConsumerError, match="unsupported"):
        run_native_fixed64_surface(
            _input(),
            surface=surface,  # type: ignore[arg-type]
        )
    raw_session = native.native_fixed64_prepare_session_v1(_input())
    with pytest.raises(ValueError, match="exact string"):
        raw_session.run(surface)


def test_prepared_session_rejects_input_identity_protocols_before_comparison(
    native,
) -> None:
    source = _input()
    source["schema_id"] = _StringProtocolObject()

    with pytest.raises(NativeFixed64ConsumerError, match="exact strings"):
        prepare_native_fixed64_session(source)


def test_prepared_session_rejects_input_key_subclass_before_comparison(native) -> None:
    source = _input()
    schema_id = source.pop("schema_id")
    source[_StringKeySubclass("schema_id")] = schema_id

    with pytest.raises(NativeFixed64ConsumerError, match="keys must be exact strings"):
        prepare_native_fixed64_session(source)


@pytest.mark.parametrize("backend", ("cpp_cpu_reference", "rust_cpu"))
def test_prepared_session_cpu_backends_match_stateless_v3(native, backend: str) -> None:
    source = _input(consumer="api")
    source["backend"] = backend

    session = prepare_native_fixed64_session(source)
    prepared = session.run(surface="api").to_dict()
    stateless = native.native_fixed64_complete_pipeline_v3(deepcopy(source))

    assert prepared == stateless
    assert session.describe()["backend"] == backend


@pytest.mark.parametrize("backend", ("hip_safe", "hip_fast"))
def test_prepared_session_rejects_hip_before_context_creation(
    native, backend: str
) -> None:
    source = _input()
    source["backend"] = backend

    with pytest.raises(NativeFixed64ConsumerError, match="CPU-only"):
        prepare_native_fixed64_session(source)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value.update(pipeline_id="cross-wired"),
        lambda value: value.update(default_consumer="cli"),
        lambda value: value.update(scientific_result_cached=True),
        lambda value: value.update(hip_device_execution_authorized=True),
        lambda value: value.update(existing_rank_auto_change_authorized=True),
        lambda value: value.update(prepared_session_receipt_sha256=_digest(121)),
    ),
)
def test_prepared_session_facade_rejects_metadata_drift(native, mutation) -> None:
    raw_session = native.native_fixed64_prepare_session_v1(_input())
    metadata = raw_session.describe()
    mutation(metadata)

    with pytest.raises(NativeFixed64ConsumerError):
        NativeFixed64PreparedSessionV1(
            _native_session=raw_session,
            _metadata=metadata,
            _backend="rust_cpu",
            _default_consumer="api",
        )


def test_prepared_session_facade_rejects_metadata_mapping_subclass(native) -> None:
    raw_session = native.native_fixed64_prepare_session_v1(_input())

    with pytest.raises(TypeError, match="metadata must be an exact dict"):
        NativeFixed64PreparedSessionV1(
            _native_session=raw_session,
            _metadata=_DictSubclass(raw_session.describe()),
            _backend="rust_cpu",
            _default_consumer="api",
        )


def test_prepared_session_facade_rejects_metadata_identity_protocols(native) -> None:
    raw_session = native.native_fixed64_prepare_session_v1(_input())
    metadata = raw_session.describe()
    metadata["schema_id"] = _StringProtocolObject()

    with pytest.raises(TypeError, match="identities must be exact strings"):
        NativeFixed64PreparedSessionV1(
            _native_session=raw_session,
            _metadata=metadata,
            _backend="rust_cpu",
            _default_consumer="api",
        )


def test_prepared_session_rejects_mapping_subclass_before_native_lookup() -> None:
    with pytest.raises(TypeError, match="exact dict"):
        prepare_native_fixed64_session(_DictSubclass(_input()))


def test_prepared_session_does_not_deepcopy_before_native_preflight(native) -> None:
    source = _input()
    source["ligand_charge_elementary"] = _DeepcopyTrap()

    with pytest.raises(NativeFixed64ConsumerError, match="exact list"):
        prepare_native_fixed64_session(source)


def test_v3_bounded_preflight_precedes_python_sequence_allocation() -> None:
    source = Path("rust_engine_v2/src/complete_fixed64_pipeline.rs").read_text(
        encoding="utf-8"
    )

    preflight = source.index("bounded_prepared_input_preflight(input)")
    ligand_allocation = source.index(
        'dict_value(input, "ligand_coordinates_angstrom")?', preflight
    )
    assert preflight < ligand_allocation


def test_complete_entrypoint_uses_one_native_receipt_graph(native) -> None:
    first = native.native_fixed64_complete_pipeline_v3(_input())
    second = native.native_fixed64_complete_pipeline_v3(_input())

    assert first == second
    assert first["schema_id"].endswith("complete_python_evidence/3.0.0")
    assert first["pipeline_id"].endswith("complete_pipeline/2.0.0")
    assert first["backend"] == "rust_cpu"
    assert first["candidate_denominator"] == 64
    assert first["receptor_atom_count"] == 4
    assert first["ligand_atom_count"] == 1
    assert first["prepared_input_bounded"] is True
    assert first["exact_cartesian_pair_count"] == 4
    assert 0 < first["prepared_input_scalar_count"] <= 8 * 1_024 * 1_024
    assert first["prepared_input_scalar_limit"] == 8 * 1_024 * 1_024
    assert first["generated_count"] == 28
    assert first["typed_failure_count"] == 36
    assert (
        first["post_admitted_count"] + first["post_rejected_count"]
        == first["refined_count"]
    )
    assert first["scored_count"] <= first["post_admitted_count"]
    assert len(first["candidates"]) == 64
    assert first["denominator_preserved"] is True
    assert first["result_dependent_input_consumed"] is False
    assert first["multi_anchor_consumed"] is False
    assert first["molecular_execution_authorized"] is False
    assert first["reservation_authorized"] is False
    assert first["benchmark_execution_authorized"] is False
    assert first["existing_rank_auto_change_authorized"] is False
    assert first["customer_pose_emission_authorized"] is False
    assert first["production_claim_authorized"] is False
    assert first["scientific_claim_authorized"] is False

    assert tuple(first["receipt_graph"]) == (
        "allocation_inventory_sha256",
        "allocation_receipt_sha256",
        "source_bundle_receipt_sha256",
        "geometric_admission_batch_receipt_sha256",
        "admission_context_receipt_sha256",
        "refinement_context_receipt_sha256",
        "scorer_context_receipt_sha256",
        "validity_context_receipt_sha256",
        "component_binding_receipt_sha256",
        "producer_batch_receipt_sha256",
        "refinement_policy_receipt_sha256",
        "refinement_batch_receipt_sha256",
        "post_admission_policy_receipt_sha256",
        "post_admission_batch_receipt_sha256",
        "scorer_batch_receipt_sha256",
        "validity_batch_receipt_sha256",
        "ranking_batch_receipt_sha256",
        "cluster_batch_receipt_sha256",
        "pipeline_batch_receipt_sha256",
    )
    assert all(len(value) == 64 for value in first["receipt_graph"].values())

    generated = [row for row in first["candidates"] if row["coordinates_available"]]
    failures = [row for row in first["candidates"] if not row["coordinates_available"]]
    assert len(generated) == 28
    assert len(failures) == 36
    assert all(len(row["scorer_v1"]["weighted_terms"]) == 8 for row in generated)
    assert all(len(row["torsion_refinement"]["moves"]) == 8 for row in generated)
    assert all(row["geometric_admission"]["exact_pair_count"] == 4 for row in generated)
    assert all(row["geometric_admission"]["exact_pair_count"] == 0 for row in failures)
    assert all(
        row["post_refinement_geometric_admission"]["exact_pair_count"] == 4
        for row in generated
    )
    assert all(
        row["lineage"]["post_admission_row_receipt_sha256"]
        == row["post_refinement_geometric_admission"]["receipt_sha256"]
        for row in first["candidates"]
    )
    assert all(
        row["ranking"]["rank_eligible"] is False
        and row["ranking"]["valid_rank_eligible"] is False
        for row in first["candidates"]
        if row["post_refinement_geometric_admission"]["rank_eligible"] is False
    )
    assert all(
        len(state) == 1
        for row in first["candidates"]
        for state in row["coordinate_states_angstrom"].values()
    )
    candidate = generated[0]
    for field in (
        "component_failure_code",
        "producer_backend",
        "ligand_atom_count",
        "coordinate_offset",
        "allocation_slot_receipt_sha256",
        "source_payload_receipt_sha256",
        "source_proposal_sha256",
        "source_coordinate_sha256",
        "placement_receipt_sha256",
        "output_proposal_sha256",
        "output_coordinate_sha256",
    ):
        assert field in candidate
    assert "penetrating_atom_count" in candidate["geometric_admission"]
    assert set(candidate["rigid_refinement"]["selected"]) == {
        "profile",
        "available",
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rotation_steps",
        "line_search_evaluation_count",
        "fallback_direction_step_count",
        "initial_penalty",
        "final_penalty",
        "total_translation_angstrom",
        "total_rotation_vector_radians",
        "total_rotation_path_radians",
        "initial_centroid_offset_angstrom",
        "final_centroid_offset_angstrom",
        "maximum_centroid_offset_angstrom",
    }
    assert len(candidate["torsion_refinement"]["optimized_torsion_angles_radians"]) == 1
    assert len(candidate["torsion_refinement"]["final_torsion_angles_radians"]) == 1
    for field in (
        "evaluation_stopped_after_selection_window_became_unreachable",
        "fixed_objective_evaluation_count",
        "torsion_trial_objective_evaluation_count",
        "baseline_v6_accepted_steps",
        "evaluated_total_torsion_path_radians",
        "accepted_total_torsion_path_radians",
    ):
        assert field in candidate["torsion_refinement"]
    assert set(candidate["validity"]) == {
        "status",
        "failure_code",
        "upstream_scorer_failure_code",
        "passed_check_mask",
        "blocker_mask",
        "observed_count",
        "atom_count",
        "rotation_orthogonality_max_error",
        "rotation_determinant",
        "max_bond_length_delta_angstrom",
        "minimum_ligand_nonbonded_distance_angstrom",
        "evaluated_ligand_nonbonded_pair_count",
        "excluded_ligand_pair_count",
        "minimum_receptor_ligand_distance_angstrom",
        "evaluated_receptor_ligand_pair_count",
        "minimum_declared_chiral_volume",
        "declared_chirality_center_count",
        "maximum_pocket_center_distance_angstrom",
        "element_vdw_ligand_pair_count",
        "element_vdw_ligand_severe_overlap_count",
        "element_vdw_ligand_minimum_distance_angstrom",
        "element_vdw_ligand_minimum_ratio",
        "element_vdw_receptor_candidate_pair_count",
        "element_vdw_receptor_full_cartesian_pair_count",
        "element_vdw_receptor_cell_count",
        "element_vdw_receptor_severe_overlap_count",
        "element_vdw_receptor_minimum_distance_angstrom",
        "element_vdw_receptor_minimum_ratio",
    }
    for field in (
        "stable_valid_rank",
        "representative_slot_index",
        "coordinate_sha256",
    ):
        assert field in candidate["cluster"]
    for field in (
        "pipeline_receipt_sha256",
        "consumer_view_receipt_sha256",
        "prepared_input_projection_sha256",
        "prepared_input_receipt_sha256",
        "allocation_receipt_sha256",
        "proposal_batch_receipt_sha256",
        "geometric_admission_receipt_sha256",
        "post_refinement_admission_receipt_sha256",
        "scorer_receipt_sha256",
        "validity_receipt_sha256",
        "ranking_receipt_sha256",
        "scientific_projection_sha256",
    ):
        assert len(first[field]) == 64
        int(first[field], 16)


def test_all_surfaces_share_complete_native_pipeline_receipt(native) -> None:
    source = _input(consumer="cli")
    original = deepcopy(source)
    results = (
        NativeFixed64CliAdapter().run(source),
        NativeFixed64DiagnosticBenchmarkAdapter().run(source),
        NativeFixed64PythonApi().run(source),
        NativeFixed64ProductShadowAdapter().run(source),
    )

    assert source == original
    assert len({item.pipeline_receipt_sha256 for item in results}) == 1
    assert len({item.prepared_input_receipt_sha256 for item in results}) == 1
    assert len({item.consumer_view_receipt_sha256 for item in results}) == 4
    assert results[-1].to_dict()["operator_second_opinion_authorized"] is True
    assert all(
        item.to_dict()["existing_rank_auto_change_authorized"] is False
        for item in results
    )


def test_canonical_consumer_does_not_copy_nested_input_before_native_preflight(
    native, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    source = _input(consumer="cli")
    trap = _DeepcopyTrap()
    source["ligand_charge_elementary"] = trap
    observed: dict[str, object] = {}

    def fake_entrypoint(payload):
        observed["nested_identity"] = payload["ligand_charge_elementary"] is trap
        observed["consumer"] = payload["consumer"]
        return deepcopy(document)

    monkeypatch.setattr(native_consumers, "_native_entrypoint", lambda: fake_entrypoint)

    evidence = NativeFixed64PythonApi().run(source)

    assert evidence.pipeline_receipt_sha256 == document["pipeline_receipt_sha256"]
    assert observed == {"nested_identity": True, "consumer": "api"}
    assert source["consumer"] == "cli"


def test_canonical_consumer_bounds_outer_mapping_before_transport_copy() -> None:
    source = _input()
    source["unexpected"] = object()

    with pytest.raises(NativeFixed64ConsumerError, match="top-level key count"):
        NativeFixed64PythonApi().run(source)


def test_complete_python_facade_binds_evidence_to_requested_backend(
    native, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["backend"] = "hip_safe"
    monkeypatch.setattr(
        native_consumers,
        "_native_entrypoint",
        lambda: lambda _payload: deepcopy(document),
    )

    with pytest.raises(NativeFixed64ConsumerError, match="requested backend"):
        NativeFixed64PythonApi().run(_input())


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("backend", "auto"),
        ("result_dependent_input_consumed", True),
        ("fallback_allowed", True),
        ("multi_anchor_consumed", True),
        ("denominator_preserved", False),
        ("benchmark_execution_authorized", True),
        ("scientific_claim_authorized", True),
    ),
)
def test_complete_python_facade_rejects_native_boundary_drift(
    native,
    field: str,
    bad_value: object,
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    document[field] = bad_value

    with pytest.raises(NativeFixed64ConsumerError):
        NativeFixed64EvidenceV3(surface="api", _document=document)


def test_complete_python_facade_rejects_reordered_candidate_denominator(native) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["candidates"][0]["slot_index"] = 1

    with pytest.raises(NativeFixed64ConsumerError, match="reordered or incomplete"):
        NativeFixed64EvidenceV3(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["candidates"][0]["slot_index"] = False
    with pytest.raises(NativeFixed64ConsumerError, match="reordered or incomplete"):
        NativeFixed64EvidenceV3(surface="api", _document=document)


def test_complete_python_facade_rejects_post_admission_cross_wiring(native) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    rejected = next(
        row
        for row in document["candidates"]
        if row["post_refinement_geometric_admission"]["rank_eligible"] is False
    )
    rejected["ranking"]["rank_eligible"] = True
    with pytest.raises(NativeFixed64ConsumerError, match="remained rank eligible"):
        NativeFixed64EvidenceV3(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["post_admitted_count"] -= 1
    with pytest.raises(NativeFixed64ConsumerError, match="counts are cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["refined_count"] += 1
    document["post_admitted_count"] += 1
    with pytest.raises(NativeFixed64ConsumerError, match="counts are cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=document)


def test_complete_python_facade_validates_receipt_graph_semantics_not_dict_order(
    native,
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["receipt_graph"] = dict(reversed(tuple(document["receipt_graph"].items())))

    evidence = NativeFixed64EvidenceV3(surface="api", _document=document)
    assert evidence.pipeline_receipt_sha256 == document["pipeline_receipt_sha256"]


@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_complete_python_facade_rejects_cross_wired_receipt_graph(
    native,
    mutation: str,
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    if mutation == "missing":
        document["receipt_graph"].pop("pipeline_batch_receipt_sha256")
    else:
        document["receipt_graph"]["unexpected_receipt_sha256"] = _digest(119)

    with pytest.raises(NativeFixed64ConsumerError, match="incomplete or cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=document)


@pytest.mark.parametrize(
    ("public_field", "graph_field"),
    (
        ("allocation_receipt_sha256", "allocation_receipt_sha256"),
        ("proposal_batch_receipt_sha256", "producer_batch_receipt_sha256"),
        (
            "geometric_admission_receipt_sha256",
            "geometric_admission_batch_receipt_sha256",
        ),
        (
            "post_refinement_admission_receipt_sha256",
            "post_admission_batch_receipt_sha256",
        ),
        ("scorer_receipt_sha256", "scorer_batch_receipt_sha256"),
        ("validity_receipt_sha256", "validity_batch_receipt_sha256"),
        ("ranking_receipt_sha256", "ranking_batch_receipt_sha256"),
        ("pipeline_receipt_sha256", "pipeline_batch_receipt_sha256"),
    ),
)
def test_complete_python_facade_binds_public_receipts_to_complete_graph(
    native,
    public_field: str,
    graph_field: str,
) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    assert document[public_field] == document["receipt_graph"][graph_field]

    document[public_field] = _digest(119)
    with pytest.raises(NativeFixed64ConsumerError, match="aliases are cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v3(_input())
    document["receipt_graph"][graph_field] = _digest(119)
    with pytest.raises(NativeFixed64ConsumerError, match="aliases are cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=document)


def test_repository_d0_native_session_uses_one_source_bound_core_across_surfaces(
    native,
) -> None:
    decisions: dict[str, str] = {}
    pipeline_receipts: dict[str, str] = {}
    for backend in ("cpp_cpu_reference", "rust_cpu"):
        session = prepare_repository_synthetic_d0_session(
            backend=backend,
            default_surface="cli",
            synthetic_only_acknowledgment=(
                REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
            ),
        )
        assert isinstance(session, NativeRepositorySyntheticD0PreparedSessionV1)
        metadata = session.describe()
        assert metadata["prepared_source_origin"] == (
            "repository_synthetic_d0_native_materializer"
        )
        assert metadata["caller_science_transport_consumed"] is False
        assert metadata["candidate_denominator"] == 64
        assert metadata["exact_cartesian_pair_count"] == 25
        assert metadata["prepared_input_scalar_count"] == 1_178
        assert metadata["repository_backend_binding"]["backend"] == backend
        results = {
            surface: session.run(surface=surface)
            for surface in ("cli", "benchmark", "api", "product_shadow")
        }
        assert all(
            isinstance(result, NativeRepositorySyntheticD0EvidenceV1)
            for result in results.values()
        )
        documents = {surface: result.to_dict() for surface, result in results.items()}
        assert len({result.pipeline_receipt_sha256 for result in results.values()}) == 1
        assert (
            len(
                {
                    document["repository_session_binding_receipt_sha256"]
                    for document in documents.values()
                }
            )
            == 1
        )
        assert (
            len(
                {
                    document["repository_scientific_decision_sha256"]
                    for document in documents.values()
                }
            )
            == 1
        )
        assert (
            len({result.consumer_view_receipt_sha256 for result in results.values()})
            == 4
        )
        assert documents["product_shadow"]["operator_second_opinion_authorized"] is True
        assert all(
            document["existing_rank_auto_change_authorized"] is False
            and document["molecular_execution_authorized"] is False
            and document["qualification_rerun_authorized"] is False
            for document in documents.values()
        )
        decisions[backend] = str(
            documents["api"]["repository_scientific_decision_sha256"]
        )
        pipeline_receipts[backend] = results["api"].pipeline_receipt_sha256
    assert len(set(decisions.values())) == 1
    assert len(set(pipeline_receipts.values())) == 2


def test_repository_d0_native_session_rejects_authority_and_binding_drift(
    native,
) -> None:
    with pytest.raises(TypeError, match="exact strings"):
        prepare_repository_synthetic_d0_session(
            backend=_StringSubclass("rust_cpu"),
            default_surface="api",
            synthetic_only_acknowledgment=(
                REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
            ),
        )
    with pytest.raises(NativeFixed64ConsumerError, match="exact synthetic-only"):
        prepare_repository_synthetic_d0_session(
            backend="rust_cpu",
            default_surface="api",
            synthetic_only_acknowledgment="acknowledged",
        )
    with pytest.raises(NativeFixed64ConsumerError, match="HIP execution"):
        prepare_repository_synthetic_d0_session(
            backend="hip_safe",
            default_surface="api",
            synthetic_only_acknowledgment=(
                REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
            ),
        )
    raw = native.native_fixed64_prepare_repository_synthetic_d0_session_v1
    with pytest.raises(ValueError, match="exact synthetic-only"):
        raw("rust_cpu", "api", "acknowledged")
    with pytest.raises(ValueError, match="HIP device execution is unauthorized"):
        raw(
            "hip_safe",
            "api",
            REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT,
        )

    evidence = NativeFixed64PythonApi().run_repository_synthetic_d0(
        backend="rust_cpu",
        synthetic_only_acknowledgment=REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT,
    )
    document = evidence.to_dict()
    document["repository_backend_binding"]["native_source_closure_sha256"] = _digest(1)
    with pytest.raises(NativeFixed64ConsumerError, match="not rederivable"):
        NativeRepositorySyntheticD0EvidenceV1(
            surface="api",
            _document=document,
        )

    document = evidence.to_dict()
    document["backend"] = _StringSubclass("rust_cpu")
    with pytest.raises(TypeError, match="exact Python identities"):
        NativeRepositorySyntheticD0EvidenceV1(
            surface="api",
            _document=document,
        )

    document = evidence.to_dict()
    binding = document["repository_backend_binding"]
    assert isinstance(binding, dict)
    binding["toolchain_attestation_status"] = "attested_sha256"
    binding["native_toolchain_sha256"] = "0" * 64
    with pytest.raises(NativeFixed64ConsumerError, match="attested build identity"):
        NativeRepositorySyntheticD0EvidenceV1(
            surface="api",
            _document=document,
        )


def test_cli_routes_repository_d0_without_caller_science(native, tmp_path) -> None:
    output_path = tmp_path / "repository-d0-native-output.json"

    assert (
        standalone_main(
            [
                "dock",
                "--repository-native-d0-backend",
                "rust_cpu",
                "--test-only-synthetic",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    result = json.loads(output_path.read_text(encoding="ascii"))
    assert result["consumer"] == "cli"
    assert result["prepared_source_origin"] == (
        "repository_synthetic_d0_native_materializer"
    )
    assert result["caller_science_transport_consumed"] is False
    assert result["candidate_denominator"] == 64
    assert result["generated_count"] == 54
    assert result["typed_failure_count"] == 10
    assert result["molecular_execution_authorized"] is False
    assert result["qualification_rerun_authorized"] is False

    rejected_path = tmp_path / "repository-d0-native-rejected.json"
    assert (
        standalone_main(
            [
                "dock",
                "--repository-native-d0-backend",
                "rust_cpu",
                "--output",
                str(rejected_path),
            ]
        )
        == 2
    )
    assert not rejected_path.exists()


def test_repository_d0_cpu_parity_is_native_complete_and_non_authoritative(
    native,
) -> None:
    receipt = run_repository_synthetic_d0_cpu_parity(
        synthetic_only_acknowledgment=(
            REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
        )
    )
    document = receipt.to_dict()
    assert receipt.gate_passed
    assert document["candidate_denominator"] == 64
    assert document["score_term_count"] == 8
    assert document["numeric_parity"]["compared_f64_count"] == 16_896
    assert document["numeric_parity"]["tolerance_violation_count"] == 0
    assert document["gates"] == {
        "source_binding_parity": True,
        "exact_decision_parity": True,
        "exact_count_parity": True,
        "exact_rank_parity": True,
        "exact_source_identity_parity": True,
        "cpp_repeat_stable": True,
        "rust_repeat_stable": True,
        "numeric_parity": True,
        "all_authority_false": True,
        "gate_passed": True,
    }
    assert all(
        document[name] is False
        for name in (
            "reservation_authorized",
            "molecular_execution_authorized",
            "historical_ab_execution_authorized",
            "fresh_holdout_execution_authorized",
            "public_benchmark_authorized",
            "stage0_admission_authorized",
            "qualification_rerun_authorized",
            "scientific_claim_authorized",
            "product_performance_claim_authorized",
            "hip_device_execution_authorized",
        )
    )
    assert (
        document["identity_disposition"]["coordinate_identity_equal_count"]
        + document["identity_disposition"]["coordinate_identity_different_count"]
        == 64
    )

    mutated = receipt.to_dict()
    mutated["numeric_parity"]["maximum_absolute_difference"] = 0.0
    with pytest.raises(NativeCpuParityError, match="not independently rederivable"):
        NativeRepositorySyntheticD0CpuParityReceiptV1(_document=mutated)

    with pytest.raises(TypeError, match="exact string"):
        run_repository_synthetic_d0_cpu_parity(
            synthetic_only_acknowledgment=_StringSubclass(
                REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
            )
        )
    with pytest.raises(ValueError, match="exact synthetic-only"):
        native.native_fixed64_repository_synthetic_d0_cpu_parity_v1("acknowledged")


def test_cli_runs_repository_d0_cpu_parity_without_result_input(native, tmp_path) -> None:
    output_path = tmp_path / "repository-d0-cpu-parity.json"
    assert (
        standalone_main(
            [
                "verify",
                "--repository-native-d0-cpu-parity",
                "--test-only-synthetic",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    document = json.loads(output_path.read_text(encoding="ascii"))
    assert document["gates"]["gate_passed"] is True
    assert document["performance_measurement_performed"] is False
    rejected_path = tmp_path / "repository-d0-cpu-parity-rejected.json"
    assert (
        standalone_main(
            [
                "verify",
                "--repository-native-d0-cpu-parity",
                "--output",
                str(rejected_path),
            ]
        )
        == 2
    )
    assert not rejected_path.exists()


def test_cli_routes_complete_schema_without_python_science(native, tmp_path) -> None:
    input_path = tmp_path / "complete-native-input.json"
    output_path = tmp_path / "complete-native-output.json"
    input_path.write_text(
        json.dumps(
            _input(),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )

    assert (
        standalone_main(
            [
                "dock",
                "--native-fixed64-input",
                str(input_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    result = json.loads(output_path.read_text(encoding="ascii"))
    assert result["consumer"] == "cli"
    assert (
        result["pipeline_receipt_sha256"]
        == (
            native.native_fixed64_complete_pipeline_v3(_input())[
                "pipeline_receipt_sha256"
            ]
        )
    )
    assert result["candidate_denominator"] == 64
    assert result["molecular_execution_authorized"] is False


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (lambda value: value.update(test_only=False), "synthetic/test-only"),
        (lambda value: value.update(backend="auto"), "unsupported or auto"),
        (
            lambda value: value.update(receptor_system_sha256=_digest(35)),
            "cross-wired",
        ),
        (
            lambda value: value.update(candidate_modes=["v2_translation"] * 63),
            "exactly 64",
        ),
    ),
)
def test_complete_entrypoint_fails_closed_before_native_work(
    native, mutation, match: str
) -> None:
    value = deepcopy(_input())
    mutation(value)

    with pytest.raises(ValueError, match=match):
        native.native_fixed64_complete_pipeline_v3(value)


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (
            lambda value: value.update(
                ligand_coordinates_angstrom=[[0.0, 0.0, 0.0]] * 513
            ),
            "bounded shape",
        ),
        (
            lambda value: value.update(
                receptor_coordinates_angstrom=[[4.0, 0.0, 0.0]] * 4097
            ),
            "bounded shape",
        ),
        (
            lambda value: value.update(
                v7_control_sources=[
                    _source(index + 1, source_index=index) for index in range(25)
                ]
            ),
            "row count exceeds 24",
        ),
        (
            lambda value: value.update(ligand_coordinates_angstrom=[[True, 0.0, 0.0]]),
            "must not be bool",
        ),
        (
            lambda value: value.__setitem__(
                "x" * 1024, value.pop("contact_policy_sha256")
            ),
            "key length exceeds",
        ),
        (
            lambda value: value.update(
                ligand_charge_elementary=[_FloatProtocolObject()]
            ),
            "exact int or float",
        ),
        (
            lambda value: value.update(
                ligand_coordinates_angstrom=_ListSubclass([[0.0, 0.0, 0.0]])
            ),
            "exact list",
        ),
    ),
)
def test_v3_rejects_unbounded_or_inexact_transport_before_native_work(
    native, mutation, match: str
) -> None:
    value = _input()
    mutation(value)

    with pytest.raises(ValueError, match=match):
        native.native_fixed64_complete_pipeline_v3(value)


def test_v3_rejects_mapping_subclasses_before_bounded_preflight(native) -> None:
    with pytest.raises(ValueError, match="exact dict"):
        native.native_fixed64_complete_pipeline_v3(_DictSubclass(_input()))


def test_v3_rejects_key_subclasses_before_native_lookup(native) -> None:
    source = _input()
    schema_id = source.pop("schema_id")
    source[_StringKeySubclass("schema_id")] = schema_id

    with pytest.raises(ValueError, match="keys must be exact strings"):
        native.native_fixed64_complete_pipeline_v3(source)


@pytest.mark.parametrize(
    "field",
    (
        "schema_id",
        "consumer",
        "backend",
        "authority_input_receipt_sha256",
        "feature_geometry_inventory_sha256",
        "predeclared_refinement_policy_sha256",
    ),
)
def test_v3_rejects_scalar_string_subclasses_before_native_work(
    native, field: str
) -> None:
    source = _input()
    source[field] = _StringSubclass(str(source[field]))

    with pytest.raises(ValueError, match="exact string"):
        native.native_fixed64_complete_pipeline_v3(source)


def test_v3_rejects_nested_receipt_string_subclass_before_native_work(native) -> None:
    source = _input()
    row = source["v7_control_sources"][0]
    row["receipt_sha256"] = _StringSubclass(str(row["receipt_sha256"]))

    with pytest.raises(ValueError, match="exact string"):
        native.native_fixed64_complete_pipeline_v3(source)


@pytest.mark.parametrize(
    "field",
    (
        "kind",
        "allocation_feature_receipt_sha256",
        "feature_geometry_receipt_sha256",
    ),
)
def test_v3_rejects_feature_string_subclasses_before_native_work(
    native, field: str
) -> None:
    source = _input()
    feature = {
        "kind": "ligand_donor",
        "allocation_feature_receipt_sha256": _digest(120),
        "feature_geometry_receipt_sha256": _digest(121),
        "atom_indices": [0],
    }
    feature[field] = _StringSubclass(str(feature[field]))
    source["feature_geometries"] = [feature]

    with pytest.raises(ValueError, match="exact string"):
        native.native_fixed64_complete_pipeline_v3(source)


def test_v3_prepared_input_receipt_binds_projection_and_pipeline(native) -> None:
    first = native.native_fixed64_complete_pipeline_v3(_input())
    changed_input = _input()
    changed_input["ligand_charge_elementary"] = [0.25]
    second = native.native_fixed64_complete_pipeline_v3(changed_input)

    assert (
        first["prepared_input_projection_sha256"]
        != second["prepared_input_projection_sha256"]
    )
    assert (
        first["prepared_input_receipt_sha256"]
        != second["prepared_input_receipt_sha256"]
    )
    expected = hashlib.sha256(
        b"betelgeuze.engine-v2.native-fixed64-prepared-input-receipt/v1\0"
        + bytes.fromhex(first["prepared_input_projection_sha256"])
        + bytes.fromhex(first["pipeline_receipt_sha256"])
    ).hexdigest()
    assert first["prepared_input_receipt_sha256"] == expected

    tampered = deepcopy(first)
    tampered["prepared_input_receipt_sha256"] = _digest(120)
    with pytest.raises(NativeFixed64ConsumerError, match="receipt is cross-wired"):
        NativeFixed64EvidenceV3(surface="api", _document=tampered)


def test_v3_consumer_identity_is_excluded_from_prepared_projection(native) -> None:
    api = native.native_fixed64_complete_pipeline_v3(_input(consumer="api"))
    cli = native.native_fixed64_complete_pipeline_v3(_input(consumer="cli"))

    assert api["pipeline_receipt_sha256"] == cli["pipeline_receipt_sha256"]
    assert (
        api["prepared_input_projection_sha256"]
        == cli["prepared_input_projection_sha256"]
    )
    assert api["prepared_input_receipt_sha256"] == cli["prepared_input_receipt_sha256"]
    assert api["consumer_view_receipt_sha256"] != cli["consumer_view_receipt_sha256"]


def test_v3_projection_is_independent_of_python_dict_insertion_order(native) -> None:
    source = _input()
    reversed_input = dict(reversed(tuple(source.items())))

    first = native.native_fixed64_complete_pipeline_v3(source)
    second = native.native_fixed64_complete_pipeline_v3(reversed_input)

    assert (
        first["prepared_input_projection_sha256"]
        == second["prepared_input_projection_sha256"]
    )
    assert (
        first["prepared_input_receipt_sha256"]
        == second["prepared_input_receipt_sha256"]
    )


def test_post_refinement_policy_is_required_and_receipt_bound(native) -> None:
    missing = _input()
    missing.pop("predeclared_post_refinement_admission_policy_sha256")
    with pytest.raises(ValueError, match="key schema"):
        native.native_fixed64_complete_pipeline_v3(missing)

    first = native.native_fixed64_complete_pipeline_v3(_input())
    changed = _input()
    changed["predeclared_post_refinement_admission_policy_sha256"] = _digest(120)
    second = native.native_fixed64_complete_pipeline_v3(changed)
    assert (
        first["receipt_graph"]["post_admission_policy_receipt_sha256"]
        != second["receipt_graph"]["post_admission_policy_receipt_sha256"]
    )
    assert first["pipeline_receipt_sha256"] != second["pipeline_receipt_sha256"]


def test_complete_consumer_view_receipt_is_domain_separated(native) -> None:
    document = native.native_fixed64_complete_pipeline_v3(_input())
    assert (
        document["pipeline_receipt_sha256"] != document["consumer_view_receipt_sha256"]
    )
    assert (
        hashlib.sha256(b"compatibility-sentinel").hexdigest() not in document.values()
    )
