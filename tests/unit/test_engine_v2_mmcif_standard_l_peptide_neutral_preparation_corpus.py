from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import (
    mmcif_standard_l_peptide_neutral_preparation as preparation,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_preparation_rules import (
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256,
    validate_standard_l_peptide_preparation_rule_manifest,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_rules import (
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256,
    validate_standard_l_peptide_rule_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_standard_l_peptide_neutral_preparation_corpus.json"
)
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_standard_l_peptide_neutral_preparation"
)
CORPUS_SCHEMA_ID = (
    "betelgeuze.v2_1_mmcif_standard_l_peptide_neutral_preparation_corpus/1.0.0"
)
CORPUS_ID = "v2_1_exact_mmcif_standard_l_peptide_neutral_preparation_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "c5c0ab935305c8d15fb2868c8327d38622de85fe84b8426e32d14be88ff3c20d"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_FIXTURE_NAME = re.compile(r"^[a-z][a-z0-9_]*[.]cif$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 16 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 64 * 1024
_POSITIVE_CASE_IDS = (
    "single_ala",
    "single_gly",
    "ala_gly_ala_gly_one_asym",
    "two_asym_reverse_chain_order",
)
_FAILURE_MUTATION_IDS = (
    "non_ascii",
    "missing_category",
    "extra_category",
    "bad_category_header",
    "scalar_category",
    "wrong_polymer_type",
    "nonpoly_entity",
    "sequence_component_without_template",
    "component_type",
    "leaving_flag",
    "stereo",
    "atom_charge",
    "component_atom_element",
    "bond_endpoint",
    "missing_atom_site",
    "atom_site_element",
)
_CATEGORY_ORDER = (
    "_entity",
    "_entity_poly",
    "_struct_asym",
    "_entity_poly_seq",
    "_chem_comp",
    "_chem_comp_atom",
    "_chem_comp_bond",
    "_atom_site",
)
_BOUNDED_TRUE_FIELDS = (
    "single_outer_source_reprojected",
    "terminal_component_child_independently_accepted",
    "archive_heavy_child_independently_accepted",
    "exact_microstate_policy_matched",
    "source_explicit_hydrogen_inventory_complete_for_profile",
    "per_atom_formal_charge_policy_matched",
    "source_stereochemistry_policy_matched",
    "role_specific_atom_transform_applied",
    "retained_source_to_prepared_atom_bijection_verified",
    "input_bond_partition_verified",
    "sequence_adjacent_peptide_bonds_materialized",
    "prepared_heavy_reference_graph_matched",
    "profile_molecular_preparation_assessed",
    "profile_molecular_preparation_ready",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "source_observed_covalence_established",
    "coordinate_peptide_geometry_validated",
    "coordinate_chain_breaks_excluded",
    "environmental_ph_assessed",
    "environmental_protonation_correctness_assessed",
    "generic_hydrogen_generation_performed",
    "generic_hydrogen_completion_assessed",
    "independent_tautomer_assessed",
    "independent_aromaticity_assessed",
    "independent_cip_assessed",
    "electronic_structure_assessed",
    "modified_residue_supported",
    "nonstandard_monomer_supported",
    "water_role_assessed",
    "ion_role_assessed",
    "metal_role_or_coordination_assessed",
    "cofactor_role_assessed",
    "generic_chemistry_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "production_parameter_set_available",
    "physics_supported",
    "runtime_eligible",
    "energy_supported",
    "force_supported",
    "minimization_supported",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
)
_EXPECTED_OBSERVATION_FIELDS = {
    "full_source_sha256",
    "result_document_sha256",
    "state_sha256",
    "transformed_topology_sha256",
    "transformed_system_snapshot_sha256",
    "source_binding_sha256",
    "report_sha256",
    "atom_mapping_document_sha256",
    "atom_mapping_rows_sha256",
    "parameter_requirement_inventory_sha256",
    "atom_count",
    "bond_count",
    "residue_count",
    "chain_count",
    "source_atom_mapping_count",
    "policy_deleted_source_atom_count",
    "inter_residue_peptide_bond_count",
    "atom_parameter_requirement_count",
    "bond_parameter_requirement_count",
    "angle_parameter_requirement_count",
    "proper_torsion_parameter_requirement_count",
    "nonbonded_site_parameter_requirement_count",
    "replay_verified",
}


class StandardLPeptideNeutralPreparationCorpusError(ValueError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StandardLPeptideNeutralPreparationCorpusError("duplicate JSON key")
        result[key] = value
    return result


def _decode_manifest(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes:
        raise TypeError("manifest payload must be bytes")
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise StandardLPeptideNeutralPreparationCorpusError("manifest exceeds byte cap")
    try:
        document = json.loads(
            payload.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StandardLPeptideNeutralPreparationCorpusError(
            "manifest must be strict ASCII JSON"
        ) from exc
    if type(document) is not dict:
        raise StandardLPeptideNeutralPreparationCorpusError(
            "manifest root must be an object"
        )
    return document


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST.is_file() or MANIFEST.is_symlink():
        raise StandardLPeptideNeutralPreparationCorpusError(
            "manifest must be a regular fixed file"
        )
    return _decode_manifest(MANIFEST.read_bytes())


def _fixture_payload(name: str) -> bytes:
    if type(name) is not str or _FIXTURE_NAME.fullmatch(name) is None:
        raise StandardLPeptideNeutralPreparationCorpusError(
            "fixture name must be one normalized CIF basename"
        )
    relative = PurePosixPath(name)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != name:
        raise StandardLPeptideNeutralPreparationCorpusError(
            "fixture path escapes fixed root"
        )
    path = FIXTURE_ROOT / name
    if not path.is_file() or path.is_symlink():
        raise StandardLPeptideNeutralPreparationCorpusError(
            "fixture must be a regular fixed file"
        )
    if path.resolve().parent != FIXTURE_ROOT.resolve():
        raise StandardLPeptideNeutralPreparationCorpusError(
            "fixture resolves outside fixed root"
        )
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise StandardLPeptideNeutralPreparationCorpusError("fixture exceeds byte cap")
    return payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if source.count(old) != 1:
        raise AssertionError("mutation anchor must occur exactly once")
    return source.replace(old, new, 1)


def _source_mutations(source: bytes) -> dict[str, bytes]:
    entity_poly_loop = (
        b"loop_\n"
        b"_entity_poly.entity_id\n"
        b"_entity_poly.type\n"
        b"_entity_poly.nstd_chirality\n"
        b"_entity_poly.nstd_linkage\n"
        b"_entity_poly.nstd_monomer\n"
        b"1 polypeptide(L) no no no\n"
        b"#\n"
    )
    final_atom_row = (
        b"ATOM 13 H HXT . ALA A 1 1 ? 1.625 -1.625 2.625 "
        b"1.00 10.00 ? 901 ALA AUTHA AUTH_HXT 1\n"
    )
    return {
        "non_ascii": source + b"\x80",
        "missing_category": _replace_once(source, entity_poly_loop, b""),
        "extra_category": source + b"loop_\n_exptl.method\n'X-RAY DIFFRACTION'\n#\n",
        "bad_category_header": _replace_once(
            source, b"_entity.type", b"_entity.pdbx_description"
        ),
        "scalar_category": _replace_once(
            source,
            b"loop_\n_entity.id\n_entity.type\n1 polymer\n#",
            b"_entity.id 1\n_entity.type polymer\n#",
        ),
        "wrong_polymer_type": _replace_once(
            source,
            b"1 polypeptide(L) no no no",
            b"1 polypeptide(D) no no no",
        ),
        "nonpoly_entity": _replace_once(source, b"1 polymer\n#", b"1 non-polymer\n#"),
        "sequence_component_without_template": _replace_once(
            source, b"1 1 ALA n", b"1 1 GLY n"
        ),
        "component_type": _replace_once(
            source,
            b"ALA 'L-peptide linking' 0",
            b"ALA 'peptide linking' 0",
        ),
        "leaving_flag": _replace_once(source, b"ALA OXT O 0 N Y", b"ALA OXT O 0 N N"),
        "stereo": _replace_once(source, b"ALA CA C 0 N N S", b"ALA CA C 0 N N N"),
        "atom_charge": _replace_once(source, b"ALA H H 0 N N N", b"ALA H H 1 N N N"),
        "component_atom_element": _replace_once(
            source, b"ALA CA C 0 N N S", b"ALA CA N 0 N N S"
        ),
        "bond_endpoint": _replace_once(source, b"ALA N H SING", b"ALA CA H SING"),
        "missing_atom_site": _replace_once(source, final_atom_row, b""),
        "atom_site_element": _replace_once(source, b"ATOM 2 C CA .", b"ATOM 2 N CA ."),
    }


def _observed_positive(
    case: dict[str, Any], source: bytes
) -> tuple[dict[str, Any], preparation.MmcifStandardLPeptideNeutralPreparationResult]:
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        source, source_id=case["source_id"]
    )
    report_artifact = result.report
    report = report_artifact.to_dict()
    result_document = result.to_dict()
    mapping = list(result.atom_mapping)
    inventory = result.parameter_requirement_inventory
    system = result.system
    marker_key = preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY
    inter_residue_bonds = sum(
        bond.metadata[marker_key]["bond_kind"] == "sequence_adjacent_peptide_bond"
        for bond in system.bonds
    )
    policy_deleted_atoms = sum(row["status"] == "policy_deleted" for row in mapping)
    observed = {
        "full_source_sha256": result.full_source_sha256,
        "result_document_sha256": hashlib.sha256(
            _canonical_json_bytes(result_document)
        ).hexdigest(),
        "state_sha256": result.state_sha256,
        "transformed_topology_sha256": result.transformed_topology_sha256,
        "transformed_system_snapshot_sha256": (
            result.transformed_system_snapshot_sha256
        ),
        "source_binding_sha256": result.source_binding_sha256,
        "report_sha256": report_artifact.report_sha256,
        "atom_mapping_document_sha256": report["atom_mapping_sha256"],
        "atom_mapping_rows_sha256": hashlib.sha256(
            _canonical_json_bytes(mapping)
        ).hexdigest(),
        "parameter_requirement_inventory_sha256": hashlib.sha256(
            _canonical_json_bytes(inventory)
        ).hexdigest(),
        "atom_count": system.atom_count,
        "bond_count": len(system.bonds),
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "source_atom_mapping_count": len(mapping),
        "policy_deleted_source_atom_count": policy_deleted_atoms,
        "inter_residue_peptide_bond_count": inter_residue_bonds,
        "atom_parameter_requirement_count": len(inventory["atom_requirements"]),
        "bond_parameter_requirement_count": len(inventory["bond_requirements"]),
        "angle_parameter_requirement_count": len(inventory["angle_requirements"]),
        "proper_torsion_parameter_requirement_count": len(
            inventory["proper_torsion_requirements"]
        ),
        "nonbonded_site_parameter_requirement_count": inventory["nonbonded_site_count"],
        "replay_verified": result.verify_replay(),
    }
    return observed, result


def test_manifest_identity_contracts_limits_and_payload_hash_are_fixed() -> None:
    manifest = _load_manifest()
    assert set(manifest) == {
        "schema_id",
        "corpus_id",
        "payload_hash_policy_id",
        "payload_sha256",
        "contracts",
        "limits",
        "positive_cases",
        "failure_cases",
    }
    assert manifest["schema_id"] == CORPUS_SCHEMA_ID
    assert manifest["corpus_id"] == CORPUS_ID
    assert manifest["payload_hash_policy_id"] == PAYLOAD_HASH_POLICY_ID
    payload_document = dict(manifest)
    payload_document.pop("payload_sha256")
    assert hashlib.sha256(_canonical_json_bytes(payload_document)).hexdigest() == (
        EXPECTED_PAYLOAD_SHA256
    )
    assert manifest["payload_sha256"] == EXPECTED_PAYLOAD_SHA256

    contracts = manifest["contracts"]
    assert contracts["profile_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PROFILE_ID
    )
    assert contracts["policy_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_POLICY_ID
    )
    assert contracts["transformer_name"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_NAME
    )
    assert contracts["transformer_version"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TRANSFORMER_VERSION
    )
    assert contracts["atom_mapping_schema_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MAPPING_SCHEMA_ID
    )
    assert contracts["parameter_requirement_inventory_schema_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_PARAMETER_REQUIREMENT_SCHEMA_ID
    )
    assert contracts["report_schema_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_REPORT_SCHEMA_ID
    )
    assert contracts["source_binding_schema_id"] == (
        preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_BINDING_SCHEMA_ID
    )
    assert contracts["preparation_rule_manifest_schema_id"] == (
        STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID
    )
    assert contracts["preparation_rule_manifest_sha256"] == (
        STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    )
    assert contracts["heavy_rule_manifest_schema_id"] == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID
    )
    assert contracts["heavy_rule_manifest_sha256"] == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    )
    assert tuple(contracts["category_order"]) == _CATEGORY_ORDER
    assert contracts["supported_components"] == ["ALA", "GLY"]
    assert contracts["positive_case_count"] == len(_POSITIVE_CASE_IDS)
    assert contracts["failure_case_count"] == len(_FAILURE_MUTATION_IDS)
    assert contracts["writer_or_round_trip_claimed"] is False
    assert tuple(contracts["bounded_true_fields"]) == _BOUNDED_TRUE_FIELDS
    assert tuple(contracts["false_authority_fields"]) == _FALSE_AUTHORITY_FIELDS
    assert validate_standard_l_peptide_preparation_rule_manifest() == (
        STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    )
    assert validate_standard_l_peptide_rule_manifest() == (
        STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256
    )
    assert manifest["limits"] == {
        "input_bytes": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_INPUT_BYTES,
        "source_id_utf8_bytes": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_ID_BYTES,
        "token_characters": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_TOKEN_CHARS,
        "output_line_characters": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_OUTPUT_LINE_CHARS,
        "prepared_atoms": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_ATOMS,
        "prepared_bonds": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_BONDS,
        "parameter_angles": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_ANGLES,
        "parameter_propers": preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_PARAMETER_PROPERS,
        "manifest_bytes": _MAX_MANIFEST_BYTES,
        "fixture_bytes": _MAX_FIXTURE_BYTES,
        "total_fixture_bytes": _MAX_TOTAL_FIXTURE_BYTES,
    }


@pytest.mark.parametrize("case_id", _POSITIVE_CASE_IDS)
def test_positive_corpus_case_is_hash_bound_exact_and_nonpromoting(
    case_id: str,
) -> None:
    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["positive_cases"]}
    assert tuple(cases) == _POSITIVE_CASE_IDS
    case = cases[case_id]
    assert set(case) == {
        "case_id",
        "fixture",
        "source_id",
        "fixture_byte_count",
        "fixture_sha256",
        "expected",
    }
    assert _CASE_ID.fullmatch(case["case_id"])
    source = _fixture_payload(case["fixture"])
    source.decode("ascii")
    assert len(source) == case["fixture_byte_count"]
    assert hashlib.sha256(source).hexdigest() == case["fixture_sha256"]
    assert _LOWER_SHA256.fullmatch(case["fixture_sha256"])
    assert set(case["expected"]) == _EXPECTED_OBSERVATION_FIELDS
    assert all(
        _LOWER_SHA256.fullmatch(value)
        for key, value in case["expected"].items()
        if key.endswith("sha256")
    )

    observed, result = _observed_positive(case, source)
    assert observed == case["expected"]
    report = result.report.to_dict()
    contracts = manifest["contracts"]
    assert all(report[field] is True for field in _BOUNDED_TRUE_FIELDS)
    assert all(report[field] is False for field in _FALSE_AUTHORITY_FIELDS)
    assert report["profile_id"] == contracts["profile_id"]
    assert report["policy_id"] == contracts["policy_id"]
    assert (
        report["preparation_rule_manifest_schema_id"]
        == contracts["preparation_rule_manifest_schema_id"]
    )
    assert (
        report["preparation_rule_manifest_sha256"]
        == contracts["preparation_rule_manifest_sha256"]
    )
    assert (
        report["heavy_rule_manifest_schema_id"]
        == contracts["heavy_rule_manifest_schema_id"]
    )
    assert (
        report["heavy_rule_manifest_sha256"] == contracts["heavy_rule_manifest_sha256"]
    )
    assert report["generated_hydrogen_count"] == 0
    assert report["general_mmcif_round_trip_evidence_ready"] is False
    assert report["all_format_round_trip_evidence_ready"] is False
    assert result.system.provenance.preparation_ready is False
    inventory = result.parameter_requirement_inventory
    assert inventory["production_parameter_set_status"] == "missing"
    assert inventory["parameterability_assessed"] is False
    assert inventory["parameterizable"] is False
    assert not hasattr(result, "write_result")
    if case_id in {"single_ala", "single_gly"}:
        assert report["sequence_role_counts"] == [["singleton", 1]]
    if case_id == "ala_gly_ala_gly_one_asym":
        assert report["sequence_role_counts"] == [
            ["c_sequence_boundary", 1],
            ["internal", 2],
            ["n_sequence_boundary", 1],
        ]
    if case_id == "two_asym_reverse_chain_order":
        assert b"\nB 2\nA 1\n#\n" in source
        assert source.index(b"ATOM 46 ") < source.index(b"ATOM 1 ")
        assert tuple(chain.chain_id for chain in result.system.chains) == ("A", "B")


def test_corpus_fixture_budget_case_sets_and_paths_are_exact() -> None:
    manifest = _load_manifest()
    positive = manifest["positive_cases"]
    failure = manifest["failure_cases"]
    assert tuple(case["case_id"] for case in positive) == _POSITIVE_CASE_IDS
    assert tuple(case["mutation_id"] for case in failure) == (_FAILURE_MUTATION_IDS)
    assert len({case["case_id"] for case in (*positive, *failure)}) == (
        len(positive) + len(failure)
    )
    assert all(_CASE_ID.fullmatch(case["case_id"]) for case in (*positive, *failure))
    positive_fixtures = tuple(case["fixture"] for case in positive)
    assert len(set(positive_fixtures)) == len(positive_fixtures)
    assert set(positive_fixtures) == {
        path.name for path in FIXTURE_ROOT.iterdir() if path.is_file()
    }
    fixture_names = {case["fixture"] for case in (*positive, *failure)}
    total = sum(len(_fixture_payload(name)) for name in fixture_names)
    assert total == 19023
    assert total <= _MAX_TOTAL_FIXTURE_BYTES


def test_manifest_decoder_and_fixture_paths_fail_closed() -> None:
    with pytest.raises(StandardLPeptideNeutralPreparationCorpusError):
        _decode_manifest(b'{"a":1,"a":2}')
    with pytest.raises(StandardLPeptideNeutralPreparationCorpusError):
        _decode_manifest(b'{"value":"\x80"}')
    with pytest.raises(StandardLPeptideNeutralPreparationCorpusError):
        _decode_manifest(b" " * (_MAX_MANIFEST_BYTES + 1))
    for invalid in (
        "",
        "../single_ala.cif",
        "nested/single_ala.cif",
        "/single_ala.cif",
        "single_ala.json",
        "SINGLE_ALA.cif",
        "missing.cif",
    ):
        with pytest.raises(StandardLPeptideNeutralPreparationCorpusError):
            _fixture_payload(invalid)


@pytest.mark.parametrize("mutation_id", _FAILURE_MUTATION_IDS)
def test_failure_corpus_mutation_is_hash_bound_typed_and_fail_closed(
    mutation_id: str,
) -> None:
    manifest = _load_manifest()
    cases = {case["mutation_id"]: case for case in manifest["failure_cases"]}
    assert tuple(cases) == _FAILURE_MUTATION_IDS
    case = cases[mutation_id]
    assert set(case) == {
        "case_id",
        "fixture",
        "mutation_id",
        "mutated_byte_count",
        "mutated_sha256",
        "expected_error_code",
    }
    assert case["fixture"] == "single_ala.cif"
    source = _fixture_payload(case["fixture"])
    mutations = _source_mutations(source)
    assert tuple(mutations) == _FAILURE_MUTATION_IDS
    mutated = mutations[mutation_id]
    assert mutated != source
    assert len(mutated) == case["mutated_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["mutated_sha256"]
    assert _LOWER_SHA256.fullmatch(case["mutated_sha256"])
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as exc_info:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            mutated, source_id=f"corpus-failure:{mutation_id}"
        )
    assert exc_info.value.code == case["expected_error_code"]


@pytest.mark.parametrize(
    ("fixture_name", "old", "new", "expected_code"),
    (
        (
            "single_ala.cif",
            b"ALA HXT H 0 N Y N Y N Y 13\n",
            b"",
            "terminal_component_child_rejected",
        ),
        (
            "single_ala.cif",
            b"ALA HXT H 0 N Y N Y N Y 13\n#\n",
            (b"ALA HXT H 0 N Y N Y N Y 13\nALA HXT H 0 N Y N Y N Y 13\n#\n"),
            "terminal_component_child_rejected",
        ),
        (
            "single_ala.cif",
            b"ALA OXT HXT SING N N 12\n",
            b"",
            "component_bond_policy_mismatch",
        ),
        (
            "single_ala.cif",
            b"ALA OXT HXT SING N N 12\n#\n",
            (b"ALA OXT HXT SING N N 12\nALA OXT HXT SING N N 12\n#\n"),
            "terminal_component_child_rejected",
        ),
        (
            "single_ala.cif",
            (b"ATOM 2 C CA . ALA A 1 1 ? 0.250 -0.250 1.250 1.00 10.00 ? 901"),
            (b"ATOM 2 C CA . ALA A 1 1 ? 0.250 -0.250 1.250 1.00 10.00 1 901"),
            "terminal_component_child_rejected",
        ),
        (
            "single_ala.cif",
            b"A 1\n#\nloop_\n_entity_poly_seq",
            b"A 2\n#\nloop_\n_entity_poly_seq",
            "terminal_component_child_rejected",
        ),
        (
            "ala_gly_ala_gly_one_asym.cif",
            b"1 2 GLY n\n",
            b"1 5 GLY n\n",
            "terminal_component_child_rejected",
        ),
    ),
    ids=(
        "missing-component-atom",
        "duplicate-component-atom",
        "missing-component-bond",
        "duplicate-component-bond",
        "atom-site-template-charge-conflict",
        "entity-join-mismatch",
        "noncontiguous-sequence",
    ),
)
def test_fixed_fixture_additional_single_axis_boundaries_fail_closed(
    fixture_name: str, old: bytes, new: bytes, expected_code: str
) -> None:
    mutated = _replace_once(_fixture_payload(fixture_name), old, new)
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as exc_info:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            mutated, source_id=f"fixed-boundary:{fixture_name}"
        )
    assert exc_info.value.code == expected_code


def test_unknown_policy_cannot_promote_a_valid_fixture() -> None:
    source = _fixture_payload("single_gly.cif")
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as exc_info:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            source, policy_id="not-the-pinned-policy"
        )
    assert exc_info.value.code == "unsupported_policy_id"
