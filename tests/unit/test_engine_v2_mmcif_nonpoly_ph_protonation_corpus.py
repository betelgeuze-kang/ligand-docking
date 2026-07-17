from __future__ import annotations

import copy
import json
import os

import pytest

from betelgeuze_engine_v2.molecular.mmcif_nonpoly_ph_protonation_corpus import (
    FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256,
    FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256,
    mmcif_nonpoly_ph_protonation_corpus_cases,
    mmcif_nonpoly_ph_protonation_corpus_document,
    mmcif_nonpoly_ph_protonation_corpus_json_bytes,
    require_mmcif_nonpoly_ph_protonation_corpus_document,
    reviewed_mmcif_nonpoly_ph_protonation_corpus_sources,
    run_mmcif_nonpoly_ph_protonation_corpus,
    write_mmcif_nonpoly_ph_protonation_corpus_json,
)


@pytest.fixture(scope="module")
def corpus_snapshot():
    return run_mmcif_nonpoly_ph_protonation_corpus()


def test_real_world_source_identity_and_license_boundaries_are_explicit() -> None:
    sources = reviewed_mmcif_nonpoly_ph_protonation_corpus_sources()
    by_id = {row["record_id"]: row for row in sources}

    assert set(by_id) == {"pubchem:cid:176", "pubchem:cid:702"}
    assert by_id["pubchem:cid:176"]["record_fields"] == {
        "cid": 176,
        "connectivity_smiles": "CC(=O)O",
        "inchi_key": "QTBSBXVTEAMEQO-UHFFFAOYSA-N",
        "molecular_formula": "C2H4O2",
        "title": "Acetic Acid",
    }
    assert by_id["pubchem:cid:702"]["record_fields"] == {
        "cid": 702,
        "connectivity_smiles": "CCO",
        "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "molecular_formula": "C2H6O",
        "title": "Ethanol",
    }
    for source in sources:
        assert len(source["record_fields_sha256"]) == 64
        boundary = source["license_boundary"]
        assert boundary["policy_identity"] == (
            "pubchem_source_specific_license_review_required"
        )
        assert boundary["raw_record_bundled"] is False
        assert boundary["contributor_text_bundled"] is False
        assert boundary["commercial_redistribution_approved"] is False
        assert boundary["source_specific_restrictions_review_required"] is True


def test_exact_ascii_inputs_and_case_contracts_are_frozen() -> None:
    cases = mmcif_nonpoly_ph_protonation_corpus_cases()

    assert len(cases) == 7
    assert tuple(row.case_id for row in cases) == tuple(
        FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256
    )
    assert all(row.source_text.encode("ascii") for row in cases)
    assert all(
        row.input_sha256
        == FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256[row.case_id]
        for row in cases
    )
    assert all(len(row.case_contract_sha256) == 64 for row in cases)
    assert {row.cohort for row in cases} == {
        "real_world_supported",
        "real_world_abstention",
        "real_world_failure",
    }


def test_supported_states_and_canonical_round_trips_are_retained(
    corpus_snapshot,
) -> None:
    by_id = {row.case_id: row for row in corpus_snapshot.case_results}
    protonated = by_id["pubchem_cid_176_ph2_protonated"]
    deprotonated = by_id["pubchem_cid_176_ph7_deprotonated"]

    assert protonated.decision_status == "dominant_protonation_state_selected"
    assert protonated.selected_state == "protonated"
    assert deprotonated.decision_status == "dominant_protonation_state_selected"
    assert deprotonated.selected_state == "deprotonated"
    for row in (protonated, deprotonated):
        assert row.observed_outcome == "expected_decision"
        assert len(row.protonation_snapshot_sha256) == 64
        assert len(row.system_sha256) == 64
        assert len(row.topology_sha256) == 64
        assert len(row.coordinates_sha256) == 64
        assert "canonical_round_trip:verified" in row.signals
        assert "real_world_source:pubchem:cid:176" in row.signals


def test_ambiguous_population_remains_an_abstention_row(corpus_snapshot) -> None:
    result = {row.case_id: row for row in corpus_snapshot.case_results}[
        "pubchem_cid_176_ph4_76_abstained"
    ]

    assert result.cohort == "real_world_abstention"
    assert result.decision_status == "abstained_population_not_dominant"
    assert result.selected_state == ""
    assert result.system_sha256 == ""
    assert "ph_abstention:minimum_dominant_population_not_met" in result.signals


@pytest.mark.parametrize(
    ("case_id", "error_code"),
    (
        ("pubchem_cid_702_structure_mismatch", "reference_structure_mismatch"),
        ("pubchem_cid_176_reference_crosswire", "unsupported_reference_compound"),
        ("pubchem_cid_176_ph_out_of_bounds", "target_ph_out_of_bounds"),
        (
            "pubchem_cid_176_source_hydrogen_rejected",
            "source_observed_acidic_hydrogen_not_removable",
        ),
    ),
)
def test_expected_failure_rows_remain_in_denominator(
    case_id: str, error_code: str, corpus_snapshot
) -> None:
    result = {row.case_id: row for row in corpus_snapshot.case_results}[case_id]

    assert result.cohort == "real_world_failure"
    assert result.observed_outcome == "expected_error"
    assert result.error_code == error_code
    assert result.protonation_snapshot_sha256 == ""
    assert result.system_sha256 == ""
    assert f"error:{error_code}" in result.signals


def test_snapshot_counts_claim_boundary_and_frozen_digest(corpus_snapshot) -> None:
    payload = corpus_snapshot.to_dict()

    assert corpus_snapshot.snapshot_sha256 == (
        FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256
    )
    assert payload["case_count"] == 7
    assert payload["cohort_counts"] == {
        "real_world_abstention": 1,
        "real_world_failure": 4,
        "real_world_supported": 2,
    }
    assert payload["selected_state_count"] == 2
    assert payload["abstention_count"] == 1
    assert payload["expected_error_count"] == 4
    assert payload["expectation_mismatch_count"] == 0
    assert payload["license_and_provenance_boundary_bound"] is True
    assert payload["source_structure_identity_authenticated"] is False
    assert payload["raw_pubchem_records_bundled"] is False
    assert payload["pubchem_coordinates_used"] is False
    assert payload["parameter_fitting_allowed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["benchmark_validated"] is False
    assert payload["product_qualified"] is False
    assert payload["customer_execution_enabled"] is False
    assert payload["claim_safe"] is False


def test_document_verifier_and_json_are_deterministic(corpus_snapshot) -> None:
    document = mmcif_nonpoly_ph_protonation_corpus_document(corpus_snapshot)

    assert require_mmcif_nonpoly_ph_protonation_corpus_document(document) is document
    assert (
        json.loads(mmcif_nonpoly_ph_protonation_corpus_json_bytes(corpus_snapshot))
        == document
    )
    second = run_mmcif_nonpoly_ph_protonation_corpus()
    assert second.snapshot_sha256 == corpus_snapshot.snapshot_sha256
    assert mmcif_nonpoly_ph_protonation_corpus_json_bytes(second) == (
        mmcif_nonpoly_ph_protonation_corpus_json_bytes(corpus_snapshot)
    )


def test_document_does_not_embed_raw_mmcif_or_pubchem_response(corpus_snapshot) -> None:
    text = json.dumps(
        mmcif_nonpoly_ph_protonation_corpus_document(corpus_snapshot),
        sort_keys=True,
    )

    assert "data_v2_preparation_corpus" not in text
    assert "_atom_site.Cartn_x" not in text
    assert '"PropertyTable"' not in text
    assert '"Properties"' not in text


def test_document_tampering_is_rejected(corpus_snapshot) -> None:
    document = mmcif_nonpoly_ph_protonation_corpus_document(corpus_snapshot)
    tampered = copy.deepcopy(document)
    tampered["corpus_projection"]["case_results"][0]["selected_state"] = "deprotonated"
    with pytest.raises(ValueError, match="digest"):
        require_mmcif_nonpoly_ph_protonation_corpus_document(tampered)


def test_private_atomic_writer(tmp_path, corpus_snapshot) -> None:
    target = tmp_path / "nested" / "ph-corpus.json"
    written = write_mmcif_nonpoly_ph_protonation_corpus_json(target, corpus_snapshot)

    assert written == target
    assert target.read_bytes() == (
        mmcif_nonpoly_ph_protonation_corpus_json_bytes(corpus_snapshot) + b"\n"
    )
    assert os.stat(target).st_mode & 0o777 == 0o600
