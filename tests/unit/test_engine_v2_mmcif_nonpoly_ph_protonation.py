from __future__ import annotations

import copy
import hashlib
import json
import math
import os

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_ph_protonation as ph_protonation
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_systems import (
    parse_mmcif_nonpoly_all_atom_systems,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_ph_protonation import (
    MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION,
    MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID,
    MmcifNonpolyPhProtonationError,
    apply_mmcif_nonpoly_ph_protonation,
    mmcif_nonpoly_ph_protonation_document,
    mmcif_nonpoly_ph_protonation_json_bytes,
    mmcif_nonpoly_ph_protonation_reference_sha256,
    require_mmcif_nonpoly_ph_protonation_document,
    reviewed_mmcif_nonpoly_ph_protonation_reference,
    write_mmcif_nonpoly_ph_protonation_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    MmcifPreparationCorpusAtom as A,
    MmcifPreparationCorpusBond as B,
    _corpus_source,
)
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.validation import validate_all_atom_system


def _acetic_acid_source(*, source_acidic_hydrogen: bool = False) -> str:
    atoms = (
        A("C1", "C"),
        A("C2", "C"),
        A("O1", "O"),
        A("O2", "O"),
    )
    bonds = (
        B("C1", "C2", "SING"),
        B("C2", "O1", "DOUB"),
        B("C2", "O2", "SING"),
    )
    if source_acidic_hydrogen:
        atoms = (*atoms, A("HO2", "H"))
        bonds = (*bonds, B("O2", "HO2", "SING"))
    return _corpus_source(atoms, bonds)


def _ethanol_source() -> str:
    return _corpus_source(
        (A("C1", "C"), A("C2", "C"), A("O1", "O")),
        (B("C1", "C2", "SING"), B("C2", "O1", "SING")),
    )


def _ligand_instance(source: str) -> str:
    snapshot = parse_mmcif_nonpoly_all_atom_systems(source)
    return snapshot.instance_reports[0].instance_identity_sha256


def _apply(source: str, target_ph: float):
    return apply_mmcif_nonpoly_ph_protonation(
        source,
        instance_identity_sha256=_ligand_instance(source),
        target_ph=target_ph,
    )


def _reseal_document(document: dict[str, object]) -> None:
    projection_sha256 = ph_protonation._sha256(document["protonation_projection"])
    source_binding_sha256 = ph_protonation._sha256(document["source_binding"])
    document["protonation_projection_sha256"] = projection_sha256
    document["source_binding_sha256"] = source_binding_sha256
    document["snapshot_sha256"] = ph_protonation._sha256(
        {
            "schema_id": ph_protonation.MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID,
            "protonation_projection_sha256": projection_sha256,
            "source_binding_sha256": source_binding_sha256,
            "claim_policy": ph_protonation._claim_policy(),
        }
    )


def test_reviewed_reference_binds_pubchem_identity_pka_and_license_boundary() -> None:
    reference = reviewed_mmcif_nonpoly_ph_protonation_reference()

    assert reference["reference_compound_id"] == "pubchem:cid:176"
    assert reference["structure_identity"] == {
        "cid": 176,
        "connectivity_smiles": "CC(=O)O",
        "inchi_key": "QTBSBXVTEAMEQO-UHFFFAOYSA-N",
        "molecular_formula": "C2H4O2",
        "title": "Acetic Acid",
    }
    assert reference["structure_source"]["service"] == "PUG REST"
    assert reference["structure_source"]["response_fields_bundled"] is False
    assert reference["pka_reference"]["value"] == 4.76
    assert reference["pka_reference"]["use_scope"] == (
        "bounded_contract_state_selection_only"
    )
    assert reference["licensing_boundary"] == {
        "policy_url": "https://pubchem.ncbi.nlm.nih.gov/docs/downloads",
        "policy_identity": "pubchem_source_specific_license_review_required",
        "raw_pubchem_record_bundled": False,
        "contributor_text_bundled": False,
        "factual_identifiers_and_graph_only": True,
        "commercial_redistribution_approved": False,
        "source_specific_restrictions_review_required": True,
    }
    assert reference["review"]["scientific_validation"] is False
    assert reference["review"]["legal_determination"] is False
    assert len(mmcif_nonpoly_ph_protonation_reference_sha256()) == 64


def test_low_ph_selects_protonated_canonical_system_without_topology_loss() -> None:
    source = _acetic_acid_source()
    parent = parse_mmcif_nonpoly_all_atom_systems(source).instance_reports[0].system
    assert parent is not None
    snapshot = _apply(source, 2.0)
    report = snapshot.report
    system = report.system

    assert report.decision_status == "dominant_protonation_state_selected"
    assert report.selected_state == "protonated"
    assert report.decision_blockers == ()
    assert report.protonated_fraction > 0.99
    assert system is not None
    assert system.atom_count == 8
    assert len(system.bonds) == 7
    assert [atom.formal_charge for atom in system.atoms] == [0] * 8
    assert canonical_coordinates_sha256(system) == canonical_coordinates_sha256(parent)
    assert system.metadata["ph_protonation_selected_state"] == "protonated"
    assert system.metadata["tautomer_selection_interpreted"] is False
    assert system.metadata["resonance_equivalence_interpreted"] is False
    assert system.metadata["parameterable"] is False
    assert system.provenance.parent_sha256[-1] == canonical_system_sha256(parent)
    validation = validate_all_atom_system(system)
    assert validation.valid is True
    assert validation.claim_stage.name.lower() == "contract_valid"
    assert validation.claim_safe is False
    assert all(atom.partial_charge_e is None for atom in system.atoms)
    assert all(atom.mass_da is None for atom in system.atoms)


def test_high_ph_removes_only_generated_acidic_hydrogen_and_localizes_charge() -> None:
    source = _acetic_acid_source()
    parent = parse_mmcif_nonpoly_all_atom_systems(source).instance_reports[0].system
    assert parent is not None
    snapshot = _apply(source, 7.0)
    report = snapshot.report
    system = report.system

    assert report.decision_status == "dominant_protonation_state_selected"
    assert report.selected_state == "deprotonated"
    assert report.deprotonated_fraction > 0.99
    assert system is not None
    assert system.atom_count == 7
    assert len(system.bonds) == 6
    assert sum(atom.formal_charge for atom in system.atoms) == -1
    charged = [atom for atom in system.atoms if atom.formal_charge == -1]
    assert len(charged) == 1
    assert charged[0].element == "O"
    assert charged[0].metadata["localized_carboxylate_charge"] is True
    assert charged[0].metadata["resonance_equivalence_interpreted"] is False
    kept_parent_indices = [
        atom.index
        for atom in parent.atoms
        if atom.index != report.acidic_hydrogen_parent_index
    ]
    assert (
        system.coordinates.tolist()
        == parent.coordinates[:, kept_parent_indices].tolist()
    )
    assert report.to_dict()["removed_generated_hydrogen_count"] == 1
    assert report.to_dict()["formal_charge_delta"] == -1
    assert system.metadata["removed_generated_hydrogen_identity_sha256"] == (
        report.acidic_hydrogen_identity_sha256
    )
    assert (
        report.canonical_round_trip_sha256
        == hashlib.sha256(canonical_system_json_bytes(system)).hexdigest()
    )


def test_selected_system_round_trips_byte_exactly_and_document_verifies() -> None:
    snapshot = _apply(_acetic_acid_source(), 7.0)
    system = snapshot.report.system
    assert system is not None

    encoded = canonical_system_json_bytes(system)
    decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))
    assert canonical_system_json_bytes(decoded) == encoded
    assert canonical_system_sha256(decoded) == canonical_system_sha256(system)
    assert canonical_topology_sha256(decoded) == canonical_topology_sha256(system)
    assert canonical_coordinates_sha256(decoded) == canonical_coordinates_sha256(system)
    document = mmcif_nonpoly_ph_protonation_document(snapshot)
    assert document["reference_match_is_exact_graph_contract"] is True
    assert document["source_structure_identity_authenticated"] is False
    assert require_mmcif_nonpoly_ph_protonation_document(document) is document
    assert json.loads(mmcif_nonpoly_ph_protonation_json_bytes(snapshot)) == document


def test_near_pka_abstains_without_emitting_a_system() -> None:
    snapshot = _apply(_acetic_acid_source(), 4.76)
    report = snapshot.report

    assert report.decision_status == "abstained_population_not_dominant"
    assert report.selected_state == ""
    assert report.decision_blockers == ("minimum_dominant_population_not_met",)
    assert report.protonated_fraction == pytest.approx(0.5)
    assert report.deprotonated_fraction == pytest.approx(0.5)
    assert report.system is None
    assert report.canonical_round_trip_sha256 == ""
    assert report.to_dict()["canonical_round_trip_verified"] is False
    document = mmcif_nonpoly_ph_protonation_document(snapshot)
    assert require_mmcif_nonpoly_ph_protonation_document(document) is document


def test_threshold_is_fail_closed_on_both_sides() -> None:
    source = _acetic_acid_source()
    delta = math.log10(
        MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        / (1.0 - MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION)
    )

    low = _apply(source, 4.76 - delta - 1.0e-8).report
    high = _apply(source, 4.76 + delta + 1.0e-8).report
    inside = _apply(source, 4.76 + delta - 1.0e-8).report
    assert low.selected_state == "protonated"
    assert high.selected_state == "deprotonated"
    assert inside.decision_status == "abstained_population_not_dominant"


@pytest.mark.parametrize(
    ("target_ph", "code"),
    (
        (-0.01, "target_ph_out_of_bounds"),
        (14.01, "target_ph_out_of_bounds"),
        (float("nan"), "nonfinite_target_ph"),
        (float("inf"), "nonfinite_target_ph"),
        (True, "invalid_target_ph"),
    ),
)
def test_invalid_target_ph_fails_closed(target_ph: float, code: str) -> None:
    source = _acetic_acid_source()
    with pytest.raises(MmcifNonpolyPhProtonationError) as caught:
        apply_mmcif_nonpoly_ph_protonation(
            source,
            instance_identity_sha256=_ligand_instance(source),
            target_ph=target_ph,
        )
    assert caught.value.code == code


def test_reference_identity_structure_and_instance_crosswires_fail_closed() -> None:
    source = _acetic_acid_source()
    with pytest.raises(MmcifNonpolyPhProtonationError) as wrong_reference:
        apply_mmcif_nonpoly_ph_protonation(
            source,
            instance_identity_sha256=_ligand_instance(source),
            target_ph=7.0,
            reference_compound_id="pubchem:cid:702",
        )
    assert wrong_reference.value.code == "unsupported_reference_compound"

    ethanol = _ethanol_source()
    with pytest.raises(MmcifNonpolyPhProtonationError) as wrong_structure:
        apply_mmcif_nonpoly_ph_protonation(
            ethanol,
            instance_identity_sha256=_ligand_instance(ethanol),
            target_ph=7.0,
        )
    assert wrong_structure.value.code == "reference_structure_mismatch"

    with pytest.raises(MmcifNonpolyPhProtonationError) as wrong_instance:
        apply_mmcif_nonpoly_ph_protonation(
            source,
            instance_identity_sha256="0" * 64,
            target_ph=7.0,
        )
    assert wrong_instance.value.code == "target_instance_not_found"


def test_source_observed_acidic_hydrogen_is_never_removed() -> None:
    source = _acetic_acid_source(source_acidic_hydrogen=True)
    with pytest.raises(MmcifNonpolyPhProtonationError) as caught:
        apply_mmcif_nonpoly_ph_protonation(
            source,
            instance_identity_sha256=_ligand_instance(source),
            target_ph=7.0,
        )
    assert caught.value.code == "source_observed_acidic_hydrogen_not_removable"


def test_repeated_execution_is_deterministic() -> None:
    source = _acetic_acid_source()
    first = _apply(source, 7.0)
    second = _apply(source, 7.0)
    assert first.snapshot_sha256 == second.snapshot_sha256
    assert mmcif_nonpoly_ph_protonation_json_bytes(first) == (
        mmcif_nonpoly_ph_protonation_json_bytes(second)
    )


def test_document_tampering_is_rejected() -> None:
    document = mmcif_nonpoly_ph_protonation_document(_apply(_acetic_acid_source(), 7.0))
    tampered = copy.deepcopy(document)
    tampered["protonation_projection"]["report"]["selected_state"] = "protonated"
    with pytest.raises(ValueError, match="digest"):
        require_mmcif_nonpoly_ph_protonation_document(tampered)


def test_resealed_semantic_tampering_is_rejected() -> None:
    document = mmcif_nonpoly_ph_protonation_document(_apply(_acetic_acid_source(), 7.0))
    tampered = copy.deepcopy(document)
    tampered["selected_state"] = "protonated"
    tampered["protonation_projection"]["report"]["selected_state"] = "protonated"
    _reseal_document(tampered)

    with pytest.raises(ValueError, match="system identity|population decision"):
        require_mmcif_nonpoly_ph_protonation_document(tampered)


def test_resealed_target_ph_crosswire_is_rejected() -> None:
    document = mmcif_nonpoly_ph_protonation_document(_apply(_acetic_acid_source(), 7.0))
    tampered = copy.deepcopy(document)
    report = tampered["protonation_projection"]["report"]
    protonated, deprotonated = ph_protonation._population(8.0)
    report.update(
        {
            "target_ph": 8.0,
            "target_ph_binary64_hex": (8.0).hex(),
            "protonated_fraction": protonated,
            "protonated_fraction_binary64_hex": protonated.hex(),
            "deprotonated_fraction": deprotonated,
            "deprotonated_fraction_binary64_hex": deprotonated.hex(),
        }
    )
    _reseal_document(tampered)

    with pytest.raises(ValueError, match="system identity"):
        require_mmcif_nonpoly_ph_protonation_document(tampered)


def test_private_atomic_writer(tmp_path) -> None:
    snapshot = _apply(_acetic_acid_source(), 2.0)
    target = tmp_path / "nested" / "ph-protonation.json"
    written = write_mmcif_nonpoly_ph_protonation_json(target, snapshot)

    assert written == target
    assert (
        target.read_bytes() == mmcif_nonpoly_ph_protonation_json_bytes(snapshot) + b"\n"
    )
    assert os.stat(target).st_mode & 0o777 == 0o600


def test_error_messages_do_not_echo_source_or_target_identity() -> None:
    source = _ethanol_source()
    instance = _ligand_instance(source)
    with pytest.raises(MmcifNonpolyPhProtonationError) as caught:
        apply_mmcif_nonpoly_ph_protonation(
            source,
            instance_identity_sha256=instance,
            target_ph=7.0,
        )
    text = str(caught.value)
    assert "data_v2_preparation_corpus" not in text
    assert instance not in text
    assert "7.0" not in text


def test_constant_reference_identifier_is_public() -> None:
    assert MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID == "pubchem:cid:176"
