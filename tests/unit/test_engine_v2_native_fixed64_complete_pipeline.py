from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from betelgeuze_engine_v2.docking.native_fixed64_consumers import (
    NativeFixed64CliAdapter,
    NativeFixed64DiagnosticBenchmarkAdapter,
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
        "v7_control_sources": [_source(index + 1, source_index=index) for index in range(24)],
        "conformer_sources": [_source(34 + index, rank=index + 2) for index in range(7)],
        "retained_sources": [_source(48 + offset, source_index=index) for offset, index in enumerate((36, 45, 54, 63))],
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

    generated = [row for row in first["candidates"] if row["coordinates_available"]]
    failures = [row for row in first["candidates"] if not row["coordinates_available"]]
    assert len(generated) == 28
    assert len(failures) == 36
    assert all(len(row["scorer_v1"]["weighted_terms"]) == 8 for row in generated)
    assert all(len(row["torsion_refinement"]["moves"]) == 8 for row in generated)
    assert all(row["geometric_admission"]["exact_pair_count"] == 4 for row in generated)
    assert all(row["geometric_admission"]["exact_pair_count"] == 0 for row in failures)
    assert all(len(state) == 1 for row in first["candidates"] for state in row["coordinate_states_angstrom"].values())
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
    assert all(item.to_dict()["existing_rank_auto_change_authorized"] is False for item in results)


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
        == (native.native_fixed64_complete_pipeline_v1(_input())["pipeline_receipt_sha256"])
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
def test_complete_entrypoint_fails_closed_before_native_work(native, mutation, match: str) -> None:
    value = deepcopy(_input())
    mutation(value)

    with pytest.raises(ValueError, match=match):
        native.native_fixed64_complete_pipeline_v1(value)


def test_complete_consumer_view_receipt_is_domain_separated(native) -> None:
    document = native.native_fixed64_complete_pipeline_v1(_input())
    assert document["pipeline_receipt_sha256"] != document["consumer_view_receipt_sha256"]
    assert hashlib.sha256(b"compatibility-sentinel").hexdigest() not in document.values()
