from __future__ import annotations

import copy
import hashlib
import json
import os

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_tautomer_selection as selection
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_systems import (
    parse_mmcif_nonpoly_all_atom_systems,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    MmcifPreparationCorpusAtom as A,
    MmcifPreparationCorpusBond as B,
    _corpus_source,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_tautomer_selection import (
    MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID,
    MmcifNonpolyTautomerSelectionError,
    apply_mmcif_nonpoly_tautomer_selection,
    mmcif_nonpoly_tautomer_selection_document,
    mmcif_nonpoly_tautomer_selection_json_bytes,
    mmcif_nonpoly_tautomer_selection_reference_sha256,
    require_mmcif_nonpoly_tautomer_selection_document,
    reviewed_mmcif_nonpoly_tautomer_selection_reference,
    write_mmcif_nonpoly_tautomer_selection_json,
)
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.validation import validate_all_atom_system


def _acetaldehyde_source() -> str:
    return _corpus_source(
        (A("C1", "C"), A("C2", "C"), A("O1", "O")),
        (B("C1", "C2", "SING"), B("C2", "O1", "DOUB")),
    )


def _vinyl_alcohol_source(*, source_hydroxyl_hydrogen: bool = False) -> str:
    atoms = (A("C1", "C"), A("C2", "C"), A("O1", "O"))
    bonds = (B("C1", "C2", "DOUB"), B("C2", "O1", "SING"))
    if source_hydroxyl_hydrogen:
        atoms = (*atoms, A("HO1", "H"))
        bonds = (*bonds, B("O1", "HO1", "SING"))
    return _corpus_source(atoms, bonds)


def _ethanol_source() -> str:
    return _corpus_source(
        (A("C1", "C"), A("C2", "C"), A("O1", "O")),
        (B("C1", "C2", "SING"), B("C2", "O1", "SING")),
    )


def _instance(source: str) -> str:
    return (
        parse_mmcif_nonpoly_all_atom_systems(source)
        .instance_reports[0]
        .instance_identity_sha256
    )


def _apply(source: str):
    return apply_mmcif_nonpoly_tautomer_selection(
        source, instance_identity_sha256=_instance(source)
    )


def _reseal_document(document: dict[str, object]) -> None:
    projection_sha = selection._sha256(document["selection_projection"])
    binding_sha = selection._sha256(document["source_binding"])
    document["selection_projection_sha256"] = projection_sha
    document["source_binding_sha256"] = binding_sha
    document["snapshot_sha256"] = selection._sha256(
        {
            "schema_id": (
                selection.MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID
            ),
            "selection_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": selection._claim_policy(),
        }
    )


def test_reviewed_reference_binds_factual_identity_and_conservative_policy() -> None:
    reference = reviewed_mmcif_nonpoly_tautomer_selection_reference()

    assert reference["reference_compound_id"] == "pubchem:cid:177"
    assert reference["alternate_compound_id"] == "pubchem:cid:11199"
    assert reference["reference_canonical_state"] == "acetaldehyde"
    assert reference["selection_policy"] == "reviewed_reference_canonical_identity"
    assert [row["structure_identity"] for row in reference["structures"]] == [
        {
            "cid": 177,
            "connectivity_smiles": "CC=O",
            "inchi_key": "IKHGUXGNUITLKF-UHFFFAOYSA-N",
            "molecular_formula": "C2H4O",
            "title": "Acetaldehyde",
        },
        {
            "cid": 11199,
            "connectivity_smiles": "C=CO",
            "inchi_key": "IMROMDMJAWUWLK-UHFFFAOYSA-N",
            "molecular_formula": "C2H4O",
            "title": "Vinyl alcohol",
        },
    ]
    assert reference["structure_source"]["response_fields_bundled"] is False
    assert reference["licensing_boundary"]["pubchem_coordinates_used"] is False
    assert reference["review"]["thermodynamic_review"] is False
    assert reference["review"]["scientific_validation"] is False
    assert len(mmcif_nonpoly_tautomer_selection_reference_sha256()) == 64


def test_reference_graph_is_selected_without_topology_or_coordinate_change() -> None:
    source = _acetaldehyde_source()
    parent = parse_mmcif_nonpoly_all_atom_systems(source).instance_reports[0].system
    assert parent is not None
    report = _apply(source).report
    system = report.system

    assert report.matched_source_state == "acetaldehyde"
    assert report.matched_compound_id == "pubchem:cid:177"
    assert report.selected_state == "acetaldehyde"
    assert report.decision_status == "reference_canonical_tautomer_selected"
    assert report.transferred_hydrogen_parent_index == -1
    assert report.transferred_hydrogen_identity_sha256 == ""
    assert canonical_coordinates_sha256(system) == canonical_coordinates_sha256(parent)
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in system.bonds] == [
        (0, 1, 1.0),
        (1, 2, 2.0),
        (0, 3, 1.0),
        (0, 4, 1.0),
        (0, 5, 1.0),
        (1, 6, 1.0),
    ]
    assert system.metadata["transferred_generated_hydrogen_count"] == 0
    assert system.metadata["thermodynamic_preference_inferred"] is False


def test_vinyl_alcohol_moves_only_generated_hydrogen_to_reference_graph() -> None:
    vinyl_source = _vinyl_alcohol_source()
    vinyl_parent = (
        parse_mmcif_nonpoly_all_atom_systems(vinyl_source).instance_reports[0].system
    )
    reference_parent = (
        parse_mmcif_nonpoly_all_atom_systems(_acetaldehyde_source())
        .instance_reports[0]
        .system
    )
    assert vinyl_parent is not None and reference_parent is not None
    report = _apply(vinyl_source).report
    system = report.system

    assert report.matched_source_state == "vinyl_alcohol"
    assert report.matched_compound_id == "pubchem:cid:11199"
    assert report.to_dict()["transferred_generated_hydrogen_count"] == 1
    moved = system.atoms[5]
    assert moved.name == "HADD_1_3"
    assert moved.metadata["origin"] == "added_hydrogen"
    assert moved.metadata["parent_atom_index"] == 0
    assert moved.metadata["tautomer_selection_moved_generated_hydrogen"] is True
    assert (
        report.transferred_hydrogen_identity_sha256
        == (vinyl_parent.atoms[6].metadata["prepared_atom_identity_sha256"])
    )
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in system.bonds] == [
        (0, 1, 1.0),
        (1, 2, 2.0),
        (0, 3, 1.0),
        (0, 4, 1.0),
        (0, 5, 1.0),
        (1, 6, 1.0),
    ]
    assert system.coordinates.tolist() == reference_parent.coordinates.tolist()
    assert system.metadata["source_observed_hydrogen_moved"] is False
    assert system.metadata["tautomer_population_predicted"] is False
    assert system.metadata["tautomer_equilibrium_inferred"] is False
    assert system.metadata["ph_dependency_interpreted"] is False


def test_selected_system_round_trips_and_document_verifies() -> None:
    snapshot = _apply(_vinyl_alcohol_source())
    system = snapshot.report.system
    encoded = canonical_system_json_bytes(system)
    decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))

    assert canonical_system_json_bytes(decoded) == encoded
    assert canonical_system_sha256(decoded) == canonical_system_sha256(system)
    assert canonical_topology_sha256(decoded) == canonical_topology_sha256(system)
    assert canonical_coordinates_sha256(decoded) == canonical_coordinates_sha256(system)
    assert (
        snapshot.report.canonical_round_trip_sha256
        == hashlib.sha256(encoded).hexdigest()
    )
    validation = validate_all_atom_system(system)
    assert validation.valid is True
    assert validation.claim_stage.name.lower() == "contract_valid"
    assert validation.claim_safe is False
    assert all(atom.partial_charge_e is None for atom in system.atoms)
    assert all(atom.mass_da is None for atom in system.atoms)
    document = mmcif_nonpoly_tautomer_selection_document(snapshot)
    assert document["reference_match_is_exact_graph_contract"] is True
    assert document["source_structure_identity_authenticated"] is False
    assert document["thermodynamic_preference_inferred"] is False
    assert require_mmcif_nonpoly_tautomer_selection_document(document) is document
    assert json.loads(mmcif_nonpoly_tautomer_selection_json_bytes(snapshot)) == document


def test_mismatch_reference_instance_and_source_hydrogen_fail_closed() -> None:
    ethanol = _ethanol_source()
    with pytest.raises(MmcifNonpolyTautomerSelectionError) as mismatch:
        _apply(ethanol)
    assert mismatch.value.code == "reference_structure_mismatch"

    source = _acetaldehyde_source()
    with pytest.raises(MmcifNonpolyTautomerSelectionError) as reference:
        apply_mmcif_nonpoly_tautomer_selection(
            source,
            instance_identity_sha256=_instance(source),
            reference_compound_id="pubchem:cid:11199",
        )
    assert reference.value.code == "unsupported_reference_compound"

    with pytest.raises(MmcifNonpolyTautomerSelectionError) as instance:
        apply_mmcif_nonpoly_tautomer_selection(
            source, instance_identity_sha256="0" * 64
        )
    assert instance.value.code == "target_instance_not_found"

    observed_h = _vinyl_alcohol_source(source_hydroxyl_hydrogen=True)
    with pytest.raises(MmcifNonpolyTautomerSelectionError) as hydrogen:
        _apply(observed_h)
    assert hydrogen.value.code == "source_observed_hydrogen_move_forbidden"


def test_repeated_execution_is_deterministic() -> None:
    source = _vinyl_alcohol_source()
    first = _apply(source)
    second = _apply(source)

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert mmcif_nonpoly_tautomer_selection_json_bytes(first) == (
        mmcif_nonpoly_tautomer_selection_json_bytes(second)
    )


def test_document_and_resealed_semantic_tampering_are_rejected() -> None:
    document = mmcif_nonpoly_tautomer_selection_document(
        _apply(_vinyl_alcohol_source())
    )
    tampered = copy.deepcopy(document)
    tampered["selection_projection"]["report"]["selected_state"] = "vinyl_alcohol"
    with pytest.raises(ValueError, match="digest"):
        require_mmcif_nonpoly_tautomer_selection_document(tampered)

    resealed = copy.deepcopy(document)
    resealed["selected_state"] = "vinyl_alcohol"
    resealed["selection_projection"]["report"]["selected_state"] = "vinyl_alcohol"
    _reseal_document(resealed)
    with pytest.raises(ValueError, match="decision identity"):
        require_mmcif_nonpoly_tautomer_selection_document(resealed)


def test_resealed_atom_lineage_tampering_is_rejected() -> None:
    document = mmcif_nonpoly_tautomer_selection_document(
        _apply(_vinyl_alcohol_source())
    )
    tampered = copy.deepcopy(document)
    system_doc = tampered["selection_projection"]["report"]["canonical_system_document"]
    system_doc["system"]["topology"]["atoms"][5]["metadata"][
        "tautomer_selection_atom_identity_sha256"
    ] = "0" * 64
    _reseal_document(tampered)

    with pytest.raises(ValueError):
        require_mmcif_nonpoly_tautomer_selection_document(tampered)


def test_private_atomic_writer(tmp_path) -> None:
    snapshot = _apply(_acetaldehyde_source())
    target = tmp_path / "nested" / "tautomer-selection.json"
    written = write_mmcif_nonpoly_tautomer_selection_json(target, snapshot)

    assert written == target
    assert target.read_bytes() == (
        mmcif_nonpoly_tautomer_selection_json_bytes(snapshot) + b"\n"
    )
    assert os.stat(target).st_mode & 0o777 == 0o600


def test_error_messages_do_not_echo_source_or_target_identity() -> None:
    source = _ethanol_source()
    instance = _instance(source)
    with pytest.raises(MmcifNonpolyTautomerSelectionError) as caught:
        apply_mmcif_nonpoly_tautomer_selection(
            source, instance_identity_sha256=instance
        )
    text = str(caught.value)
    assert "data_v2_preparation_corpus" not in text
    assert instance not in text


def test_reference_identifier_is_public() -> None:
    assert MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID == ("pubchem:cid:177")
