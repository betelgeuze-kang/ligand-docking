from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_site_observations import (
    parse_mmcif_nonpoly_atom_site_observations,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    parse_mmcif_nonpoly_identity,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256,
    FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256,
    MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID,
    MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS,
    MmcifNonpolyPreparationCorpusError,
    mmcif_nonpoly_preparation_corpus_cases,
    mmcif_nonpoly_preparation_corpus_document,
    mmcif_nonpoly_preparation_corpus_json_bytes,
    mmcif_nonpoly_preparation_coverage_rows,
    require_mmcif_nonpoly_preparation_corpus_document,
    run_mmcif_nonpoly_preparation_corpus,
    write_mmcif_nonpoly_preparation_corpus_json,
)
from betelgeuze_engine_v2.molecular.mmcif_struct_conn_declarations import (
    parse_mmcif_struct_conn_declarations,
)


@pytest.fixture(scope="module")
def corpus_snapshot():
    return run_mmcif_nonpoly_preparation_corpus()


def test_exact_ascii_inputs_and_all_cohorts_are_frozen() -> None:
    cases = mmcif_nonpoly_preparation_corpus_cases()

    assert len(cases) == 29
    assert tuple(row.case_id for row in cases) == tuple(
        FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256
    )
    assert {row.cohort for row in cases} == {
        "supported_graph",
        "unprepared_integration",
        "unsupported_chemistry",
        "unsupported_upstream_policy",
        "invalid_source",
    }
    assert all(row.source_text.encode("ascii") for row in cases)
    assert all(
        row.input_sha256
        == FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256[row.case_id]
        for row in cases
    )


def test_supported_graphs_water_and_source_hydrogen_match_exactly(
    corpus_snapshot,
) -> None:
    by_id = {row.case_id: row for row in corpus_snapshot.case_results}

    carbonyl = by_id["supported_carbonyl"]
    ligand, water = carbonyl.reports
    assert ligand["preparation_status"] == "prepared_component_graph"
    assert ligand["formula"] == {"C": 1, "H": 2, "O": 1}
    assert ligand["total_formal_charge"] == 0
    assert ligand["added_hydrogen_count"] == 2
    assert ligand["prepared_atom_count"] == 4
    assert ligand["prepared_bond_count"] == 3
    assert water["component_id"] == "HOH"
    assert water["formula"] == {"H": 2, "O": 1}
    assert water["parameterable"] is False

    single = by_id["supported_single_coh"].reports[0]
    assert single["formula"] == {"C": 1, "H": 4, "O": 1}
    assert single["added_hydrogen_count"] == 4
    source_h = by_id["supported_source_hydrogen"].reports[0]
    assert source_h["formula"] == {"C": 1, "H": 4, "O": 1}
    assert source_h["added_hydrogen_count"] == 3


def test_known_nonpoly_insertion_code_is_exactly_joined_and_prepared(
    corpus_snapshot,
) -> None:
    case = {
        row.case_id: row for row in mmcif_nonpoly_preparation_corpus_cases()
    }["supported_nonpoly_insertion_code"]
    result = {
        row.case_id: row for row in corpus_snapshot.case_results
    }["supported_nonpoly_insertion_code"]
    identity = parse_mmcif_nonpoly_identity(case.source_text)
    observations = parse_mmcif_nonpoly_atom_site_observations(case.source_text)
    connection = parse_mmcif_struct_conn_declarations(case.source_text)

    ligand_instance = next(row for row in identity.instances if row.asym_id == "L")
    ligand_observations = tuple(
        row for row in observations.observations if row.label_asym_id == "L"
    )
    partner = connection.declarations[0].partner_1
    assert ligand_instance.pdb_ins_code.to_dict() == {
        "state": "known",
        "value": "A",
        "quoted": False,
    }
    assert ligand_observations
    assert all(
        row.insertion_code.to_dict() == ligand_instance.pdb_ins_code.to_dict()
        for row in ligand_observations
    )
    assert all(
        row.instance_identity_sha256 == ligand_instance.instance_identity_sha256
        for row in ligand_observations
    )
    assert partner.pdb_ins_code.to_dict() == ligand_instance.pdb_ins_code.to_dict()
    assert partner.instance_identity_sha256 == ligand_instance.instance_identity_sha256
    assert result.reports[0]["preparation_status"] == "prepared_component_graph"
    assert result.reports[0]["added_hydrogen_count"] == 2


@pytest.mark.parametrize(
    ("case_id", "blocker"),
    (
        ("unsupported_charged_component", "charged_chemistry_not_supported"),
        ("unsupported_extended_element", "element_outside_neutral_coh_scope"),
        ("unsupported_aromatic_atom", "aromatic_chemistry_not_supported"),
        ("unsupported_atom_stereo", "atom_stereochemistry_not_prepared"),
        ("unsupported_bond_stereo", "bond_stereochemistry_not_prepared"),
        ("unsupported_triple_bond", "bond_order_outside_neutral_coh_scope"),
        ("unsupported_quadruple_bond", "bond_order_outside_neutral_coh_scope"),
        ("unsupported_aromatic_bond", "bond_order_outside_neutral_coh_scope"),
        ("unsupported_cyclic_graph", "cyclic_chemistry_not_supported"),
        ("unsupported_disconnected_graph", "component_graph_disconnected"),
        (
            "unsupported_element_crosscheck_mismatch",
            "atom_site_component_element_mismatch",
        ),
        (
            "unsupported_charge_crosscheck_mismatch",
            "atom_site_component_formal_charge_mismatch",
        ),
        (
            "unsupported_formal_charge_unavailable",
            "component_formal_charge_unavailable",
        ),
        ("unsupported_overfull_valence", "neutral_valence_not_satisfied"),
        (
            "unsupported_incomplete_source_hydrogen",
            "source_hydrogen_valence_incomplete",
        ),
    ),
)
def test_expected_failure_rows_retain_exact_chemistry_blocker(
    case_id: str, blocker: str, corpus_snapshot
) -> None:
    result = {row.case_id: row for row in corpus_snapshot.case_results}[case_id]
    ligand = result.reports[0]

    assert result.cohort == "unsupported_chemistry"
    assert ligand["preparation_status"] == "unsupported_chemistry"
    assert ligand["chemistry_blockers"] == [blocker]
    assert ligand["parameterable"] is False
    assert ligand["prepared_atom_count"] == 0
    assert ligand["prepared_bond_count"] == 0


@pytest.mark.parametrize(
    ("case_id", "composition_role", "role_blocker"),
    (
        (
            "unsupported_monoatomic_metal",
            "monoatomic_metal_component",
            "monoatomic_metal_preparation_not_supported",
        ),
        (
            "unsupported_monoatomic_nonmetal_ion",
            "monoatomic_nonmetal_ion",
            "monoatomic_nonmetal_ion_preparation_not_supported",
        ),
    ),
)
def test_interpreted_monoatomic_roles_remain_explicitly_unsupported(
    case_id: str,
    composition_role: str,
    role_blocker: str,
    corpus_snapshot,
) -> None:
    result = {row.case_id: row for row in corpus_snapshot.case_results}[case_id]
    ligand_report = result.reports[0]
    ligand_role = result.component_roles[0]

    assert result.cohort == "unsupported_chemistry"
    assert len(result.component_role_snapshot_sha256) == 64
    assert ligand_role["composition_role"] == composition_role
    assert ligand_role["preparation_disposition"] == "explicitly_unsupported"
    assert ligand_role["role_blockers"] == [role_blocker]
    assert ligand_report["preparation_status"] == "unsupported_chemistry"
    assert ligand_report["chemistry_blockers"] == [
        "element_outside_neutral_coh_scope",
        "charged_chemistry_not_supported",
    ]


def test_unresolved_nonpoly_role_does_not_guess_a_cofactor(corpus_snapshot) -> None:
    result = {
        row.case_id: row for row in corpus_snapshot.case_results
    }["supported_carbonyl"]
    ligand_role = result.component_roles[0]

    assert ligand_role["component_id"] == "LIG"
    assert ligand_role["composition_role"] == "unresolved_nonpoly_component"
    assert ligand_role["role_status"] == "unresolved"
    assert ligand_role["role_blockers"] == [
        "ligand_cofactor_and_other_nonpoly_roles_not_interpreted"
    ]
    assert (
        "role_blocker:LIG:ligand_cofactor_and_other_nonpoly_roles_not_interpreted"
        in result.signals
    )


def test_source_declared_modified_residue_is_retained_as_unsupported_preparation(
    corpus_snapshot,
) -> None:
    result = {
        row.case_id: row for row in corpus_snapshot.case_results
    }["unsupported_source_declared_modified_residue"]

    assert result.cohort == "unsupported_chemistry"
    assert len(result.modified_residue_declaration_snapshot_sha256) == 64
    assert len(result.modified_residue_declarations) == 1
    declaration = result.modified_residue_declarations[0]
    assert declaration["label_asym_id"] == "P"
    assert declaration["label_seq_id"] == 1
    assert declaration["label_comp_id"] == "MSE"
    assert declaration["parent_comp_id"] == "MET"
    assert declaration["modified_residue_role"] == (
        "source_declared_modified_polymer_component"
    )
    assert declaration["preparation_disposition"] == "explicitly_unsupported"
    assert declaration["role_blockers"][-1] == (
        "modified_residue_preparation_not_supported"
    )
    assert result.reports[0]["preparation_status"] == "prepared_component_graph"


def test_multimodel_source_is_classified_before_preparation_rejects_it(
    corpus_snapshot,
) -> None:
    result = {
        row.case_id: row for row in corpus_snapshot.case_results
    }["unsupported_multimodel_input"]

    assert result.cohort == "unsupported_upstream_policy"
    assert result.observed_outcome == "expected_error"
    assert result.error_code == "selected_model_not_supported"
    assert result.preparation_snapshot_sha256 == ""
    assert len(result.atom_site_model_policy_snapshot_sha256) == 64
    policy = result.atom_site_model_policy
    assert policy["model_numbers"] == [1, 2]
    assert policy["multi_model_input"] is True
    assert policy["execution_policy_status"] == (
        "explicitly_unsupported_multimodel"
    )
    assert policy["execution_allowed"] is False
    assert policy["execution_blockers"] == [
        "multimodel_execution_not_supported"
    ]


def test_explicit_nonpoly_altloc_is_a_frozen_preparation_boundary(
    corpus_snapshot,
) -> None:
    result = {
        row.case_id: row for row in corpus_snapshot.case_results
    }["unsupported_altloc_input"]

    assert result.cohort == "unsupported_upstream_policy"
    assert result.observed_outcome == "expected_error"
    assert result.error_code == "nonblank_atom_site_marker_not_supported"
    assert result.preparation_snapshot_sha256 == ""
    assert result.atom_site_model_policy["execution_allowed"] is True
    assert "source_feature:atom_site_label_alt_id:explicit" in result.signals
    assert "error:nonblank_atom_site_marker_not_supported" in result.signals


@pytest.mark.parametrize(
    ("case_id", "declaration_kind", "declaration_status", "blocker"),
    (
        (
            "unsupported_zero_occupancy_residue_input",
            "residue",
            "zero_occupancy",
            "source_declared_zero_occupancy_residue_preparation_not_supported",
        ),
        (
            "unsupported_unobserved_atom_input",
            "atom",
            "unobserved",
            "source_declared_unobserved_atom_preparation_not_supported",
        ),
    ),
)
def test_source_declared_observation_gaps_block_preparation_with_policy_evidence(
    case_id: str,
    declaration_kind: str,
    declaration_status: str,
    blocker: str,
    corpus_snapshot,
) -> None:
    result = {row.case_id: row for row in corpus_snapshot.case_results}[case_id]

    assert result.cohort == "unsupported_upstream_policy"
    assert result.observed_outcome == "expected_error"
    assert result.error_code == "source_declared_observation_gap_not_supported"
    assert result.preparation_snapshot_sha256 == ""
    assert len(result.missing_atom_residue_policy_snapshot_sha256) == 64
    policy = result.missing_atom_residue_policy
    assert policy["execution_policy_status"] == (
        "explicitly_unsupported_source_declared_observation_gaps"
    )
    assert policy["execution_allowed"] is False
    assert policy["execution_blockers"] == [blocker]
    count_row = next(
        row
        for row in policy["declaration_status_counts"]
        if row["declaration_kind"] == declaration_kind
        and row["declaration_status"] == declaration_status
    )
    assert count_row["row_count"] == 1
    assert (
        "missing_atom_residue_policy_status:"
        "explicitly_unsupported_source_declared_observation_gaps"
        in result.signals
    )
    assert f"missing_atom_residue_policy_blocker:{blocker}" in result.signals


def test_invalid_source_rows_retain_stable_error_codes_without_raw_source(
    corpus_snapshot,
) -> None:
    by_id = {row.case_id: row for row in corpus_snapshot.case_results}

    assert by_id["invalid_component_charge_grammar"].error_code == (
        "invalid_component_formal_charge"
    )
    assert by_id["invalid_component_charge_range"].error_code == (
        "component_formal_charge_out_of_bounds"
    )
    assert by_id["invalid_component_charge_grammar"].reports == ()
    document_text = json.dumps(
        mmcif_nonpoly_preparation_corpus_document(corpus_snapshot), sort_keys=True
    )
    assert "data_v2_preparation_corpus" not in document_text
    assert "1.0 HETATM" not in document_text


def test_intercomponent_connections_remain_unprepared_parameterability_boundaries(
    corpus_snapshot,
) -> None:
    by_id = {row.case_id: row for row in corpus_snapshot.case_results}

    coordination = by_id["supported_carbonyl"].reports[0]
    covalent = by_id["unprepared_intercomponent_covalent"].reports[0]
    assert (
        "intercomponent_coordination_not_prepared"
        in (coordination["parameterability_blockers"])
    )
    assert (
        "intercomponent_covalent_connection_not_prepared"
        in (covalent["parameterability_blockers"])
    )
    assert coordination["parameterability_status"] == (
        "graph_ready_external_connection_blocked"
    )
    assert covalent["parameterability_status"] == (
        "graph_ready_external_connection_blocked"
    )


def test_all_required_coverage_axes_are_classified_without_promotion(
    corpus_snapshot,
) -> None:
    rows = mmcif_nonpoly_preparation_coverage_rows()
    payload = corpus_snapshot.to_dict()

    assert tuple(row.coverage_id for row in rows) == (
        MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS
    )
    assert len(rows) == 51
    assert payload["coverage_status_counts"] == {
        "explicitly_unsupported": 26,
        "not_implemented": 8,
        "supported": 17,
    }
    assert payload["unclassified_coverage_row_count"] == 0
    assert payload["expectation_mismatch_count"] == 0
    assert payload["parameter_fitting_allowed"] is False
    assert payload["v2_1_exit_ready"] is False
    assert payload["scientifically_validated"] is False
    assert payload["benchmark_validated"] is False
    assert payload["product_qualified"] is False
    assert payload["customer_execution_enabled"] is False
    assert payload["claim_safe"] is False

    missing = {
        row.coverage_id: row.blocker
        for row in rows
        if row.policy_status == "not_implemented"
    }
    assert "role.ion" not in missing
    assert "role.metal" not in missing
    assert "role.cofactor" not in missing
    assert "role.modified_residue" not in missing
    assert "upstream.altloc_selection" not in missing
    assert "upstream.insertion_semantics" not in missing
    assert "upstream.missing_atom_residue_policy" not in missing
    assert "upstream.multimodel_policy" not in missing
    assert missing["hydrogen.coordinates"] == "hydrogen_coordinates_not_generated"
    assert missing["parameter_source.reviewed"] == ("reviewed_parameter_source_missing")
    assert missing["all_atom_system.creation"] == (
        "prepared_all_atom_system_not_created"
    )


def test_document_is_deterministic_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    first = run_mmcif_nonpoly_preparation_corpus()
    second = run_mmcif_nonpoly_preparation_corpus()
    document = mmcif_nonpoly_preparation_corpus_document(first)

    assert first == second
    assert first.snapshot_sha256 == (
        FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256
    )
    assert document["schema_id"] == (
        MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID
    assert require_mmcif_nonpoly_preparation_corpus_document(document) == document
    encoded = mmcif_nonpoly_preparation_corpus_json_bytes(first)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_preparation_corpus_json(
        tmp_path / "preparation-corpus.json", first
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".preparation-corpus.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["corpus_projection"]["case_results"][0]["reports"][0][
        "added_hydrogen_count"
    ] = 99
    projection_digest = module._sha256(tampered["corpus_projection"])
    tampered["corpus_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID,
            "corpus_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="drifted from executable evidence"):
        require_mmcif_nonpoly_preparation_corpus_document(tampered)


def test_input_and_snapshot_freezes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_inputs = dict(FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256)
    bad_inputs["supported_carbonyl"] = "0" * 64
    monkeypatch.setattr(
        module,
        "FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256",
        bad_inputs,
    )
    with pytest.raises(
        MmcifNonpolyPreparationCorpusError, match="input digest drifted"
    ):
        mmcif_nonpoly_preparation_corpus_cases()

    monkeypatch.setattr(
        module,
        "FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256",
        FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256,
    )
    monkeypatch.setattr(
        module,
        "FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256",
        "0" * 64,
    )
    with pytest.raises(MmcifNonpolyPreparationCorpusError, match="snapshot drifted"):
        run_mmcif_nonpoly_preparation_corpus()


def test_dedicated_corpus_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_nonpoly_preparation_corpus.py" in source
    assert "mmcif_modified_residue_declarations.py" in source
    assert "mmcif_atom_site_model_policy.py" in source
    assert "test_engine_v2_mmcif_atom_site_model_policy.py" in source
    assert "mmcif_missing_atom_residue_policy.py" in source
    assert "test_engine_v2_mmcif_missing_atom_residue_policy.py" in source
    assert "test_engine_v2_mmcif_modified_residue_declarations.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
