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


def _label_digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _input(*, consumer: str = "api") -> dict[str, object]:
    return {
        "schema_id": (
            "betelgeuze.engine_v2_native_fixed64_exact_source_input/1.0.0"
        ),
        "consumer": consumer,
        "source_receipt_sha256": _digest(1),
        "proposal_sha256": _digest(2),
        "prepared_ligand_topology_sha256": _digest(3),
        "prepared_receptor_topology_sha256": _digest(4),
        "receptor_system_sha256": _digest(10),
        "ligand_system_sha256": _digest(11),
        "scorer_backend_receipt_sha256": _digest(12),
        "validity_backend_receipt_sha256": _digest(13),
        "contact_policy_sha256": _digest(14),
        "ligand_coordinates_angstrom": [
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
        ],
        "ligand_vdw_radii_angstrom": [1.0, 1.0, 1.0, 1.0],
        "ligand_heavy_atom_mask": [True, True, True, True],
        "ligand_charge_elementary": [0.2, 0.1, -0.1, -0.2],
        "ligand_epsilon_kcal_per_mol": [0.17, 0.02, 0.12, 0.2],
        "ligand_hydrophobic_mask": [False, False, True, False],
        "ligand_acceptor_mask": [False, False, False, True],
        "receptor_coordinates_angstrom": [
            [5.0, 0.0, 0.0],
            [6.0, 0.0, 0.0],
        ],
        "receptor_vdw_radii_angstrom": [1.0, 1.0],
        "receptor_charge_elementary": [-0.25, 0.15],
        "receptor_epsilon_kcal_per_mol": [0.2, 0.17],
        "receptor_hydrophobic_mask": [True, False],
        "receptor_acceptor_mask": [True, False],
        "ligand_donors": [[0, 1]],
        "receptor_donors": [],
        "ligand_exclusions": [[0, 1], [1, 2], [2, 3]],
        "rotor_quads": [[0, 1, 2, 3]],
        "bond_pairs": [[0, 1], [1, 2], [2, 3]],
        "chirality_centers": [[0, 1, 2, 3]],
        "pocket_center_angstrom": [0.0, 0.0, 0.0],
        "pocket_radius_angstrom": 20.0,
        "pocket_normal": [0.0, 0.0, 1.0],
        "v7_control_sources": [],
        "conformer_sources": [],
        "retained_sources": [],
        "feature_geometries": [],
        "test_only": True,
    }


def _complete_input() -> dict[str, object]:
    value = _input()
    dominant = 1.0 / (2.0**0.5)
    ligand_scale = (1.1 / 2.0) ** 0.5
    receptor_scale = (1.2 / 2.0) ** 0.5
    secondary_scale = (1.0 / 2.0) ** 0.5
    ligand = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.5],
        [-1.0, -1.0, 0.0],
        [1.0, -1.0, 0.0],
        [0.0, 1.0, 0.0],
        [ligand_scale * dominant, ligand_scale * dominant, 0.0],
        [-ligand_scale * dominant, -ligand_scale * dominant, 0.0],
        [0.0, 0.0, secondary_scale],
        [0.0, 0.0, -secondary_scale],
    ]
    receptor = [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.2, 0.1, 0.0],
        [-0.2, 0.0, 0.0],
        [0.2, 0.0, 0.0],
        [-1.0, -1.0, 0.0],
        [1.0, -1.0, 0.0],
        [0.0, 1.0, 0.0],
        [receptor_scale * dominant, receptor_scale * dominant, 0.0],
        [-receptor_scale * dominant, -receptor_scale * dominant, 0.0],
        [0.0, 0.0, secondary_scale],
        [0.0, 0.0, -secondary_scale],
    ]
    value.update(
        ligand_coordinates_angstrom=ligand,
        receptor_coordinates_angstrom=receptor,
        ligand_vdw_radii_angstrom=[1.2] * 12,
        receptor_vdw_radii_angstrom=[1.2] * 12,
        ligand_heavy_atom_mask=[True] * 12,
        ligand_charge_elementary=[0.0] * 12,
        receptor_charge_elementary=[0.0] * 12,
        ligand_epsilon_kcal_per_mol=[0.2] * 12,
        receptor_epsilon_kcal_per_mol=[0.2] * 12,
        ligand_hydrophobic_mask=[False] * 12,
        receptor_hydrophobic_mask=[False] * 12,
        ligand_acceptor_mask=[False] * 12,
        receptor_acceptor_mask=[False] * 12,
        ligand_donors=[],
        receptor_donors=[],
        ligand_exclusions=[],
        rotor_quads=[],
        bond_pairs=[],
        chirality_centers=[],
        pocket_center_angstrom=[0.0, 0.0, 5.0],
        pocket_normal=[0.0, 0.0, 2.0],
    )
    value["v7_control_sources"] = [
        {
            "source_index": index,
            "receipt_sha256": _label_digest(f"complete-v7-receipt-{index}"),
            "proposal_sha256": _label_digest(f"complete-v7-proposal-{index}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for index in range(24)
    ]
    value["conformer_sources"] = [
        {
            "rank": rank,
            "receipt_sha256": _label_digest(f"complete-conformer-receipt-{rank}"),
            "proposal_sha256": _label_digest(f"complete-conformer-proposal-{rank}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for rank in range(2, 9)
    ]
    value["retained_sources"] = [
        {
            "source_index": index,
            "receipt_sha256": _label_digest(f"complete-retained-receipt-{index}"),
            "proposal_sha256": _label_digest(f"complete-retained-proposal-{index}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for index in (36, 45, 54, 63)
    ]
    feature_indices = {
        "ligand_donor": [0, 1],
        "ligand_acceptor": [2],
        "receptor_donor": [0, 1],
        "receptor_acceptor": [2],
        "ligand_positive_site": [3],
        "ligand_negative_site": [4],
        "receptor_positive_site": [4],
        "receptor_negative_site": [3],
        "ligand_aromatic_plane": [5, 6, 7],
        "receptor_aromatic_plane": [5, 6, 7],
        "ligand_shape_axis": [8, 9, 10, 11],
        "pocket_shape_axis": [8, 9, 10, 11],
    }
    value["feature_geometries"] = [
        {
            "kind": kind,
            "receipt_sha256": _label_digest(f"complete-feature-{kind}"),
            "atom_indices": atom_indices,
        }
        for kind, atom_indices in feature_indices.items()
    ]
    return value


@pytest.fixture(scope="module")
def native():
    return pytest.importorskip("betelgeuze_engine_v2_native")


def test_native_fixed64_entrypoint_runs_the_complete_exact_source_graph(native) -> None:
    first = native.native_fixed64_exact_source_pipeline_v1(_input())
    second = native.native_fixed64_exact_source_pipeline_v1(_input())

    assert first == second
    assert first["pipeline_receipt_sha256"] == second["pipeline_receipt_sha256"]
    assert first["candidate_denominator"] == 64
    assert len(first["candidates"]) == 64
    assert first["generated_count"] == 12
    assert first["accepted_count"] == 12
    assert first["scored_count"] == 12
    assert first["evaluated_count"] == 12
    assert first["valid_count"] == 12
    assert len(first["top5_slot_indices"]) == 5
    assert first["top5_slot_indices"] == first["valid_top5_slot_indices"]
    assert len(first["authority_blockers"]) == 4
    assert first["backend"] == "rust_cpu"
    assert first["evidence_display_authorized"] is True
    assert first["operator_second_opinion_authorized"] is False
    assert first["reservation_authorized"] is False
    assert first["molecular_execution_authorized"] is False
    assert first["existing_rank_auto_change_authorized"] is False
    assert first["customer_pose_emission_authorized"] is False
    assert first["production_claim_authorized"] is False
    assert sum(row["scorer_terms"] is not None for row in first["candidates"]) == 12
    assert all(row["candidate_removed_from_denominator"] is False for row in first["candidates"])
    assert all(row["result_dependent_allocation"] is False for row in first["candidates"])
    scored = next(row for row in first["candidates"] if row["scorer_terms"])
    assert set(scored["scorer_terms"]) == {
        "proposal_record_receipt_sha256",
        "proposal_sha256",
        "admission_decision_receipt_sha256",
        "authority_input_receipt_sha256",
        "context_receipt_sha256",
        "config_receipt_sha256",
        "backend",
        "backend_receipt_sha256",
        "typed_vdw",
        "electrostatics",
        "directional_hbond",
        "hydrophobic_contact",
        "desolvation_proxy",
        "torsion_energy",
        "ligand_strain",
        "weak_pocket_prior",
        "total_score",
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
        "coordinate_sha256",
        "receipt_sha256",
    }
    validity = scored["validity_evidence"]
    assert validity["complete"] is True
    assert len(validity["checks"]) == 8
    assert len(validity["measurements"]) == 22
    assert validity["backend"] == "rust_cpu"


def test_native_fixed64_consumer_views_share_one_core_receipt(native) -> None:
    receipts: set[str] = set()
    view_receipts: set[str] = set()
    for consumer in ("cli", "benchmark", "api", "product_shadow"):
        result = native.native_fixed64_exact_source_pipeline_v1(
            _input(consumer=consumer)
        )
        receipts.add(result["pipeline_receipt_sha256"])
        view_receipts.add(result["consumer_view_receipt_sha256"])
        assert result["operator_second_opinion_authorized"] is (
            consumer == "product_shadow"
        )

    assert len(receipts) == 1
    assert len(view_receipts) == 4


def test_python_surfaces_are_thin_views_over_one_native_receipt(native) -> None:
    source = _input()
    source_before = deepcopy(source)
    results = (
        NativeFixed64CliAdapter().run(source),
        NativeFixed64DiagnosticBenchmarkAdapter().run(source),
        NativeFixed64PythonApi().run(source),
        NativeFixed64ProductShadowAdapter().run(source),
    )

    assert source == source_before
    assert {result.pipeline_receipt_sha256 for result in results} == {
        native.native_fixed64_exact_source_pipeline_v1(source)[
            "pipeline_receipt_sha256"
        ]
    }
    assert len({result.consumer_view_receipt_sha256 for result in results}) == 4
    for result in results:
        document = result.to_dict()
        document["candidate_denominator"] = 1
        assert result.to_dict()["candidate_denominator"] == 64
        assert document["customer_pose_emission_authorized"] is False
        assert document["existing_rank_auto_change_authorized"] is False
        assert document["production_claim_authorized"] is False


def test_betelgeuze_dock_command_routes_versioned_input_to_native_core(
    native,
    tmp_path,
) -> None:
    input_path = tmp_path / "native-fixed64-input.json"
    output_path = tmp_path / "native-fixed64-output.json"
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

    status = standalone_main(
        [
            "dock",
            "--native-fixed64-input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert status == 0
    result = json.loads(output_path.read_text(encoding="ascii"))
    assert result["consumer"] == "cli"
    assert result["candidate_denominator"] == 64
    assert result["pipeline_receipt_sha256"] == (
        native.native_fixed64_exact_source_pipeline_v1(_input())[
            "pipeline_receipt_sha256"
        ]
    )
    assert result["customer_pose_emission_authorized"] is False


def test_native_fixed64_source_groups_fill_only_their_predeclared_lanes(native) -> None:
    value = _input()
    ligand = value["ligand_coordinates_angstrom"]
    assert isinstance(ligand, list)
    value["v7_control_sources"] = [
        {
            "source_index": index,
            "receipt_sha256": _label_digest(f"v7-receipt-{index}"),
            "proposal_sha256": _label_digest(f"v7-proposal-{index}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for index in range(24)
    ]
    value["conformer_sources"] = [
        {
            "rank": rank,
            "receipt_sha256": _label_digest(f"conformer-receipt-{rank}"),
            "proposal_sha256": _label_digest(f"conformer-proposal-{rank}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for rank in range(2, 9)
    ]
    value["retained_sources"] = [
        {
            "source_index": index,
            "receipt_sha256": _label_digest(f"retained-receipt-{index}"),
            "proposal_sha256": _label_digest(f"retained-proposal-{index}"),
            "coordinates_angstrom": deepcopy(ligand),
        }
        for index in (36, 45, 54, 63)
    ]

    result = native.native_fixed64_exact_source_pipeline_v1(value)

    assert result["candidate_denominator"] == 64
    assert result["generated_count"] == 48
    assert result["accepted_count"] == 48
    assert result["scored_count"] == 48
    assert all(
        row["proposal_status"] == "typed_generation_failure"
        for row in result["candidates"][44:60]
    )
    assert all(
        row["proposal_failure_code"] == "allocation_missing_feature"
        for row in result["candidates"][44:60]
    )
    assert all(
        row["proposal_status"] == "generated"
        for row in (
            result["candidates"][:44] + result["candidates"][60:]
        )
    )


def test_native_fixed64_complete_inventory_generates_all_64_slots(native) -> None:
    result = native.native_fixed64_exact_source_pipeline_v1(_complete_input())

    assert result["candidate_denominator"] == 64
    assert result["generated_count"] == 64
    assert all(
        row["proposal_status"] == "generated" for row in result["candidates"]
    )
    assert all(row["proposal_failure_code"] is None for row in result["candidates"])
    assert {
        row["lane"] for row in result["candidates"]
    } == {
        "pocket_centered_controls",
        "uniform_source_controls",
        "deterministic_independent_so3",
        "true_conformer_independent_so3",
        "ligand_donor_to_receptor_acceptor",
        "ligand_acceptor_to_receptor_donor",
        "complementary_charge",
        "aromatic_plane",
        "principal_axis_shape",
        "paired_retained_controls",
    }


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (lambda value: value.update(test_only=False), "synthetic/test-only"),
        (lambda value: value.update(consumer="production"), "unsupported"),
        (lambda value: value.update(source_receipt_sha256="0" * 64), "all-zero"),
        (lambda value: value.pop("contact_policy_sha256"), "invalid key schema"),
        (
            lambda value: value.update(ligand_vdw_radii_angstrom=[1.0]),
            "length or finite-value contract",
        ),
    ),
)
def test_native_fixed64_entrypoint_fails_closed_before_scientific_work(
    native,
    mutation,
    match: str,
) -> None:
    value = deepcopy(_input())
    mutation(value)

    with pytest.raises(ValueError, match=match):
        native.native_fixed64_exact_source_pipeline_v1(value)
