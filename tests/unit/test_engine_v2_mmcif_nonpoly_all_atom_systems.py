from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat
import struct

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_systems as module
from betelgeuze_engine_v2.molecular import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
    validate_all_atom_system,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_systems import (
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
    mmcif_nonpoly_all_atom_system_document,
    mmcif_nonpoly_all_atom_system_json_bytes,
    parse_mmcif_nonpoly_all_atom_systems,
    require_mmcif_nonpoly_all_atom_system_document,
    write_mmcif_nonpoly_all_atom_system_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)


def _case_source(case_id: str) -> str:
    return next(
        row.source_text
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == case_id
    )


def _bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def test_supported_instances_create_valid_claim_blocked_canonical_systems() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )

    assert snapshot.created_system_count == 2
    assert snapshot.unavailable_system_count == 0
    for report in snapshot.instance_reports:
        assert report.materialization_status == "canonical_all_atom_system_created"
        assert report.materialization_blockers == ()
        assert report.limitations == MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS
        system = report.system
        assert system is not None
        validation = validate_all_atom_system(system)
        assert validation.valid is True
        assert validation.claim_stage.name.lower() == "contract_valid"
        assert validation.claim_safe is False
        assert system.coordinate_unit == "angstrom"
        assert system.coordinates.dtype.is_floating_point
        assert str(system.coordinates.dtype) == "torch.float64"
        assert system.model_count == 1
        assert len(system.residues) == 1
        assert len(system.chains) == 1
        assert system.provenance.source_digest_verified is False
        assert system.provenance.transformation_chain_verified is False
        assert system.provenance.chemistry_validated is False
        assert system.provenance.scientifically_validated is False
        assert system.provenance.product_qualified is False
        assert all(atom.partial_charge_e is None for atom in system.atoms)
        assert all(atom.mass_da is None for atom in system.atoms)
        assert report.system_sha256 == canonical_system_sha256(system)
        assert report.topology_sha256 == canonical_topology_sha256(system)
        assert report.coordinates_sha256 == canonical_coordinates_sha256(system)


def test_source_coordinate_bits_scalars_and_added_hydrogen_lineage_are_preserved() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )
    ligand = next(row.system for row in snapshot.instance_reports if row.component_id == "LIG")
    assert ligand is not None

    for atom in ligand.atoms:
        coordinate = ligand.coordinates[0, atom.index]
        metadata = atom.metadata
        assert [_bits(float(value)) for value in coordinate] == (
            metadata["coordinate_binary64_bits_hex"]
        )
        assert metadata["prepared_atom_identity_sha256"]
        assert metadata["coordinate_identity_sha256"]
        assert atom.partial_charge_e is None
        if metadata["origin"] == "source_atom":
            assert metadata["source_atom_scalar_status"] == "bound"
            assert metadata["site_identity_sha256"]
            assert metadata["scalar_value_identity_sha256"]
            assert metadata["scalar_source_binding_sha256"]
            assert metadata["occupancy_state"] == "known"
            assert metadata["b_factor_state"] == "known"
            assert atom.occupancy == 1.0
            assert atom.b_factor == 10.0
        else:
            assert atom.element == "H"
            assert metadata["source_atom_scalar_status"] == (
                "not_applicable_added_atom"
            )
            assert metadata["parent_atom_index"] is not None
            assert metadata["coordinate_generation_method"] == (
                "fixed_parent_offset_table_v1"
            )


def test_source_hydrogen_is_preserved_as_source_atom_not_regenerated() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_source_hydrogen")
    )
    ligand = next(row.system for row in snapshot.instance_reports if row.component_id == "LIG")
    assert ligand is not None
    source_hydrogens = [
        atom
        for atom in ligand.atoms
        if atom.element == "H" and atom.metadata["origin"] == "source_atom"
    ]
    assert source_hydrogens
    assert all(
        atom.metadata["coordinate_generation_method"]
        == "source_atom_site_coordinate"
        for atom in source_hydrogens
    )
    assert all(atom.serial is not None for atom in source_hydrogens)


def test_coordination_is_preserved_as_metadata_and_never_promoted_to_bond() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_carbonyl")
    )
    assert snapshot.created_system_count == 2
    for report in snapshot.instance_reports:
        system = report.system
        assert system is not None
        edges = system.metadata["preserved_intercomponent_coordination_edges"]
        assert edges
        assert all(row["connection_type"] == "metalc" for row in edges)
        assert system.metadata["intercomponent_coordination_materialization"] == (
            "metadata_only_not_canonical_bond"
        )
        assert all(bond.source != "struct_conn:metalc" for bond in system.bonds)


def test_intercomponent_covalence_blocks_every_affected_instance() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("unprepared_intercomponent_covalent")
    )
    assert snapshot.created_system_count == 0
    assert snapshot.unavailable_system_count == 2
    for report in snapshot.instance_reports:
        assert report.system is None
        assert report.materialization_status == (
            "not_created_intercomponent_connection_unmaterialized"
        )
        assert "intercomponent_covalent_connection_not_prepared" in (
            report.materialization_blockers
        )
        assert report.system_sha256 == ""


def test_unsupported_component_is_failure_complete_while_independent_water_survives() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("unsupported_extended_element")
    )
    ligand, water = snapshot.instance_reports
    assert ligand.component_id == "LIG"
    assert ligand.system is None
    assert ligand.materialization_status == (
        "not_created_preparation_graph_unavailable"
    )
    assert "element_outside_neutral_coh_scope" in ligand.materialization_blockers
    assert water.component_id == "HOH"
    assert water.system is not None
    assert water.materialization_status == "canonical_all_atom_system_created"


def test_nonpoly_source_identity_is_bound_without_interpreting_author_numbering() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_nonpoly_insertion_code")
    )
    ligand = next(row.system for row in snapshot.instance_reports if row.component_id == "LIG")
    assert ligand is not None
    residue = ligand.residues[0]
    chain = ligand.chains[0]
    assert chain.chain_id == "L"
    assert chain.entity_id == "1"
    assert residue.insertion_code == "A"
    assert residue.metadata["pdb_ins_code"] == {
        "state": "known",
        "value": "A",
        "quoted": False,
    }
    assert residue.metadata["sequence_number_semantics"] == (
        "bounded_source_ordinal_plus_one"
    )
    assert ligand.metadata["instance_identity_sha256"] == (
        snapshot.instance_reports[0].instance_identity_sha256
    )


def test_document_embeds_self_verifying_canonical_systems_and_claim_boundary() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )
    document = mmcif_nonpoly_all_atom_system_document(snapshot)
    assert document["schema_id"] == MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID
    assert require_mmcif_nonpoly_all_atom_system_document(document) is document
    assert json.loads(mmcif_nonpoly_all_atom_system_json_bytes(snapshot)) == document

    for row in document["system_projection"]["instance_reports"]:
        encoded = canonical_json_bytes(row["canonical_system_document"])
        restored = all_atom_system_from_canonical_json(encoded)
        assert canonical_system_sha256(restored) == row["system_sha256"]
    for flag in (
        "source_identity_bound",
        "preparation_graph_bound",
        "hydrogen_coordinate_set_bound",
        "canonical_all_atom_system_created",
        "canonical_all_atom_schema_validated",
        "canonical_hashes_bound",
        "failure_complete_instance_reports",
    ):
        assert document[flag] is True
    for flag in (
        "intercomponent_connections_materialized",
        "source_authenticated",
        "coordinate_geometry_validated",
        "partial_charge_assigned",
        "parameter_source_bound",
        "parameter_assignment_implemented",
        "parameterable",
        "source_format_round_trip_validated",
        "chemistry_validated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert document[flag] is False


def test_document_rejects_system_identity_and_claim_tampering() -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )
    document = mmcif_nonpoly_all_atom_system_document(snapshot)

    tampered = deepcopy(document)
    tampered["system_projection"]["instance_reports"][0]["system_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        require_mmcif_nonpoly_all_atom_system_document(tampered)

    promoted = deepcopy(document)
    promoted["scientifically_validated"] = True
    with pytest.raises(ValueError, match="claim boundary"):
        require_mmcif_nonpoly_all_atom_system_document(promoted)

    resealed = deepcopy(document)
    resealed["source_binding"]["coordinate_dtype"] = "float32"
    resealed["source_binding_sha256"] = module._sha256(resealed["source_binding"])
    resealed["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
            "system_projection_sha256": resealed["system_projection_sha256"],
            "source_binding_sha256": resealed["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="source policy mismatch"):
        require_mmcif_nonpoly_all_atom_system_document(resealed)


def test_atomic_writer_is_private_and_round_trips(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )
    output = write_mmcif_nonpoly_all_atom_system_json(
        tmp_path / "nested" / "all-atom.json",
        snapshot,
    )
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert output.read_bytes() == mmcif_nonpoly_all_atom_system_json_bytes(snapshot) + b"\n"
    assert require_mmcif_nonpoly_all_atom_system_document(
        json.loads(output.read_text(encoding="ascii"))
    )
    assert not list(output.parent.glob(f".{output.name}.*.tmp"))


def test_public_molecular_namespace_exposes_materializer() -> None:
    from betelgeuze_engine_v2.molecular import (
        MmcifNonpolyAllAtomSystemSnapshot,
        parse_mmcif_nonpoly_all_atom_systems as public_parser,
    )

    assert isinstance(
        public_parser(_case_source("supported_single_coh")),
        MmcifNonpolyAllAtomSystemSnapshot,
    )


def test_dedicated_workflow_is_sparse_offline_and_cross_version() -> None:
    workflow = Path(
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-all-atom-systems.yml"
    ).read_text(encoding="utf-8")
    assert 'python-version: ["3.10", "3.11", "3.12"]' in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "test_engine_v2_mmcif_nonpoly_all_atom_systems.py" in workflow
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in workflow
    assert "curl " not in workflow
    assert "wget " not in workflow

    for workflow_name in (
        "ci-engine-v2-main.yml",
        "ci-engine-v2-mmcif-nonpoly-preparation.yml",
        "ci-engine-v2-mmcif-nonpoly-hydrogen-coordinates.yml",
        "ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml",
        "ci-engine-v2-parameter-source-provenance.yml",
    ):
        integration = Path(".github/workflows", workflow_name).read_text(
            encoding="utf-8"
        )
        assert "test_engine_v2_mmcif_nonpoly_all_atom_systems.py" in integration
        assert "ci-engine-v2-mmcif-nonpoly-all-atom-systems.yml" in integration
