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
    NativeFixed64ProductShadowAdapter,
    NativeFixed64PythonApi,
)
from betelgeuze_engine_v2.standalone_cli import main as standalone_main


def _digest(marker: int) -> str:
    return f"{marker:02x}" * 32


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
        "schema_id": ("betelgeuze.engine_v2_native_fixed64_complete_input/1.0.0"),
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
        "test_only": True,
    }


@pytest.fixture(scope="module")
def native():
    return pytest.importorskip("betelgeuze_engine_v2_native")


def test_package_preloads_native_extension_before_legacy_imports(native) -> None:
    import sys

    assert sys.modules.get("betelgeuze_engine_v2_native") is native


def test_complete_native_work_releases_the_gil_before_pipeline_execution() -> None:
    source = Path(
        "rust_engine_v2/src/complete_fixed64_pipeline.rs"
    ).read_text(encoding="utf-8")
    allow_threads = source.index(".allow_threads(move ||")
    context_creation = source.index("let context = Context::new(options)?", allow_threads)
    pipeline_run = source.index("pipeline.run(run)", context_creation)
    receipt_conversion = source.index("receipt_to_python(py", pipeline_run)

    assert allow_threads < context_creation < pipeline_run < receipt_conversion


def test_complete_entrypoint_uses_one_native_receipt_graph(native) -> None:
    first = native.native_fixed64_complete_pipeline_v1(_input())
    second = native.native_fixed64_complete_pipeline_v1(_input())

    assert first == second
    assert first["schema_id"].endswith("complete_python_evidence/1.0.0")
    assert first["pipeline_id"].endswith("complete_pipeline/1.0.0")
    assert first["backend"] == "rust_cpu"
    assert first["candidate_denominator"] == 64
    assert first["receptor_atom_count"] == 4
    assert first["ligand_atom_count"] == 1
    assert first["generated_count"] == 28
    assert first["typed_failure_count"] == 36
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
        "allocation_receipt_sha256",
        "proposal_batch_receipt_sha256",
        "geometric_admission_receipt_sha256",
        "scorer_receipt_sha256",
        "validity_receipt_sha256",
        "ranking_receipt_sha256",
    ):
        assert len(first[field]) == 64
        int(first[field], 16)


def test_all_surfaces_share_complete_native_pipeline_receipt(native) -> None:
    source = _input()
    original = deepcopy(source)
    results = (
        NativeFixed64CliAdapter().run(source),
        NativeFixed64DiagnosticBenchmarkAdapter().run(source),
        NativeFixed64PythonApi().run(source),
        NativeFixed64ProductShadowAdapter().run(source),
    )

    assert source == original
    assert len({item.pipeline_receipt_sha256 for item in results}) == 1
    assert len({item.consumer_view_receipt_sha256 for item in results}) == 4
    assert results[-1].to_dict()["operator_second_opinion_authorized"] is True
    assert all(
        item.to_dict()["existing_rank_auto_change_authorized"] is False
        for item in results
    )


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
    document = native.native_fixed64_complete_pipeline_v1(_input())
    document[field] = bad_value

    with pytest.raises(NativeFixed64ConsumerError):
        NativeFixed64EvidenceV1(surface="api", _document=document)


def test_complete_python_facade_rejects_reordered_candidate_denominator(native) -> None:
    document = native.native_fixed64_complete_pipeline_v1(_input())
    document["candidates"][0]["slot_index"] = 1

    with pytest.raises(NativeFixed64ConsumerError, match="reordered or incomplete"):
        NativeFixed64EvidenceV1(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v1(_input())
    document["candidates"][0]["slot_index"] = False
    with pytest.raises(NativeFixed64ConsumerError, match="reordered or incomplete"):
        NativeFixed64EvidenceV1(surface="api", _document=document)


def test_complete_python_facade_validates_receipt_graph_semantics_not_dict_order(
    native,
) -> None:
    document = native.native_fixed64_complete_pipeline_v1(_input())
    document["receipt_graph"] = dict(reversed(tuple(document["receipt_graph"].items())))

    evidence = NativeFixed64EvidenceV1(surface="api", _document=document)
    assert evidence.pipeline_receipt_sha256 == document["pipeline_receipt_sha256"]


@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_complete_python_facade_rejects_cross_wired_receipt_graph(
    native,
    mutation: str,
) -> None:
    document = native.native_fixed64_complete_pipeline_v1(_input())
    if mutation == "missing":
        document["receipt_graph"].pop("pipeline_batch_receipt_sha256")
    else:
        document["receipt_graph"]["unexpected_receipt_sha256"] = _digest(119)

    with pytest.raises(NativeFixed64ConsumerError, match="incomplete or cross-wired"):
        NativeFixed64EvidenceV1(surface="api", _document=document)


@pytest.mark.parametrize(
    ("public_field", "graph_field"),
    (
        ("allocation_receipt_sha256", "allocation_receipt_sha256"),
        ("proposal_batch_receipt_sha256", "producer_batch_receipt_sha256"),
        (
            "geometric_admission_receipt_sha256",
            "geometric_admission_batch_receipt_sha256",
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
    document = native.native_fixed64_complete_pipeline_v1(_input())
    assert document[public_field] == document["receipt_graph"][graph_field]

    document[public_field] = _digest(119)
    with pytest.raises(NativeFixed64ConsumerError, match="aliases are cross-wired"):
        NativeFixed64EvidenceV1(surface="api", _document=document)

    document = native.native_fixed64_complete_pipeline_v1(_input())
    document["receipt_graph"][graph_field] = _digest(119)
    with pytest.raises(NativeFixed64ConsumerError, match="aliases are cross-wired"):
        NativeFixed64EvidenceV1(surface="api", _document=document)


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
            native.native_fixed64_complete_pipeline_v1(_input())[
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
        native.native_fixed64_complete_pipeline_v1(value)


def test_complete_consumer_view_receipt_is_domain_separated(native) -> None:
    document = native.native_fixed64_complete_pipeline_v1(_input())
    assert (
        document["pipeline_receipt_sha256"] != document["consumer_view_receipt_sha256"]
    )
    assert (
        hashlib.sha256(b"compatibility-sentinel").hexdigest() not in document.values()
    )
