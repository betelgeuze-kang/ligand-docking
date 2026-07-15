from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
from typing import Any

import pytest

from betelgeuze_engine_v2.molecular import (
    mmcif_standard_l_peptide_heavy_completion as completion,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_completion_rules import (
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256,
    standard_l_peptide_completion_component_rule,
    standard_l_peptide_completion_role_rule,
    validate_standard_l_peptide_completion_rule_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "independent_engine_v2_v2_1_mmcif_standard_l_peptide_heavy_completion_corpus.json"
)
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_standard_l_peptide_heavy_completion"
)
CORPUS_SCHEMA_ID = (
    "betelgeuze.v2_1_mmcif_standard_l_peptide_heavy_completion_corpus/1.0.0"
)
CORPUS_ID = "v2_1_exact_mmcif_standard_l_peptide_heavy_completion_v1"
PAYLOAD_HASH_POLICY_ID = "sha256_canonical_json_without_payload_sha256/1.0.0"
EXPECTED_PAYLOAD_SHA256 = (
    "7fed000628174709fb5cd30955239f65e9395e981d3a34422fdcdb3a932bfb1f"
)

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_FIXTURE_NAME = re.compile(r"^[a-z][a-z0-9_]*[.]cif$")
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_FIXTURE_BYTES = 8 * 1024
_MAX_TOTAL_FIXTURE_BYTES = 16 * 1024
_POSITIVE_CASE_IDS = (
    "single_ala",
    "single_gly",
    "ala_gly_ala",
    "two_asym_ala_gly",
)
_FAILURE_MUTATION_IDS = (
    "non_ascii",
    "missing_category",
    "extra_category",
    "bad_category_header",
    "extra_source_heavy_atom",
    "missing_source_heavy_atom",
    "source_hydrogen",
    "unsupported_monomer",
    "degenerate_n_ca_c",
    "reflected_ala",
    "heavy_bond_stretch",
    "adjacent_c_n_too_short",
    "adjacent_c_n_too_long",
)
_CATEGORY_ORDER = (
    "_entity",
    "_entity_poly",
    "_struct_asym",
    "_entity_poly_seq",
    "_atom_site",
)
_BOUNDED_TRUE_FIELDS = (
    "archive_heavy_source_independently_accepted",
    "completion_rule_manifest_matched",
    "source_heavy_graph_preserved",
    "source_heavy_coordinates_binary64_preserved",
    "profile_geometry_admission_assessed",
    "profile_geometry_admission_satisfied",
    "role_specific_hydrogen_completion_applied",
    "fixed_neutral_microstate_formal_charges_assigned",
    "profile_heavy_completion_assessed",
    "profile_heavy_completion_ready",
    "profile_molecular_preparation_assessed",
    "profile_molecular_preparation_ready",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "source_observed_covalence_established",
    "scientific_geometry_validated",
    "angles_validated",
    "omega_validated",
    "clashes_assessed",
    "environmental_ph_assessed",
    "environmental_protonation_correctness_assessed",
    "generic_hydrogen_completion_assessed",
    "independent_tautomer_assessed",
    "independent_aromaticity_assessed",
    "independent_cip_assessed",
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
    "outer_source_writer_available",
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
    "source_retained_mapping_count",
    "profile_generated_mapping_count",
    "source_heavy_atom_count",
    "generated_hydrogen_count",
    "source_heavy_bond_count",
    "generated_hydrogen_bond_count",
    "sequence_adjacent_peptide_bond_count",
    "atom_parameter_requirement_count",
    "bond_parameter_requirement_count",
    "angle_parameter_requirement_count",
    "proper_torsion_parameter_requirement_count",
    "nonbonded_site_parameter_requirement_count",
    "partial_charge_site_parameter_requirement_count",
    "replay_verified",
}


class StandardLPeptideHeavyCompletionCorpusError(ValueError):
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
            raise StandardLPeptideHeavyCompletionCorpusError("duplicate JSON key")
        result[key] = value
    return result


def _decode_manifest(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes:
        raise TypeError("manifest payload must be bytes")
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise StandardLPeptideHeavyCompletionCorpusError("manifest exceeds byte cap")
    try:
        document = json.loads(
            payload.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StandardLPeptideHeavyCompletionCorpusError(
            "manifest must be strict ASCII JSON"
        ) from exc
    if type(document) is not dict:
        raise StandardLPeptideHeavyCompletionCorpusError(
            "manifest root must be an object"
        )
    return document


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST.is_file() or MANIFEST.is_symlink():
        raise StandardLPeptideHeavyCompletionCorpusError(
            "manifest must be a regular fixed file"
        )
    return _decode_manifest(MANIFEST.read_bytes())


def _fixture_payload(name: str) -> bytes:
    if type(name) is not str or _FIXTURE_NAME.fullmatch(name) is None:
        raise StandardLPeptideHeavyCompletionCorpusError(
            "fixture name must be one normalized CIF basename"
        )
    relative = PurePosixPath(name)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != name:
        raise StandardLPeptideHeavyCompletionCorpusError(
            "fixture path escapes fixed root"
        )
    path = FIXTURE_ROOT / name
    if not path.is_file() or path.is_symlink():
        raise StandardLPeptideHeavyCompletionCorpusError(
            "fixture must be a regular fixed file"
        )
    if path.resolve().parent != FIXTURE_ROOT.resolve():
        raise StandardLPeptideHeavyCompletionCorpusError(
            "fixture resolves outside fixed root"
        )
    payload = path.read_bytes()
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise StandardLPeptideHeavyCompletionCorpusError("fixture exceeds byte cap")
    return payload


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    if source.count(old) != 1:
        raise AssertionError("mutation anchor must occur exactly once")
    return source.replace(old, new, 1)


def _translate_middle_gly_x(source: bytes, delta: float) -> bytes:
    anchors = (
        (
            b"ATOM 6 N N . GLY A 1 2 ? 1.236 ",
            f"ATOM 6 N N . GLY A 1 2 ? {1.236 + delta:.3f} ".encode(),
        ),
        (
            b"ATOM 7 C CA . GLY A 1 2 ? 0.066 ",
            f"ATOM 7 C CA . GLY A 1 2 ? {0.066 + delta:.3f} ".encode(),
        ),
        (
            b"ATOM 8 C C . GLY A 1 2 ? -1.193 ",
            f"ATOM 8 C C . GLY A 1 2 ? {-1.193 + delta:.3f} ".encode(),
        ),
        (
            b"ATOM 9 O O . GLY A 1 2 ? -1.124 ",
            f"ATOM 9 O O . GLY A 1 2 ? {-1.124 + delta:.3f} ".encode(),
        ),
    )
    for old, new in anchors:
        source = _replace_once(source, old, new)
    return source


def _source_mutations(single_ala: bytes, ala_gly_ala: bytes) -> dict[str, bytes]:
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
        b"ATOM 6 O OXT . ALA A 1 1 ? 0.661 0.439 -1.742 1.00 10.00 ? 1 ALA XA OXT 1\n"
    )
    return {
        "non_ascii": single_ala + b"\x80",
        "missing_category": _replace_once(single_ala, entity_poly_loop, b""),
        "extra_category": (
            single_ala + b"loop_\n_exptl.method\n'X-RAY DIFFRACTION'\n#\n"
        ),
        "bad_category_header": _replace_once(
            single_ala, b"_entity.type", b"_entity.pdbx_description"
        ),
        "extra_source_heavy_atom": _replace_once(
            single_ala,
            final_atom_row,
            final_atom_row
            + (
                b"ATOM 7 C XX . ALA A 1 1 ? 4.000 4.000 4.000 "
                b"1.00 10.00 ? 1 ALA XA XX 1\n"
            ),
        ),
        "missing_source_heavy_atom": _replace_once(
            single_ala,
            (
                b"ATOM 4 O O . ALA A 1 1 ? -1.056 -0.682 -0.923 "
                b"1.00 10.00 ? 1 ALA XA O 1\n"
            ),
            b"",
        ),
        "source_hydrogen": _replace_once(
            single_ala,
            final_atom_row,
            final_atom_row
            + (
                b"ATOM 7 H H . ALA A 1 1 ? -1.383 -0.425 1.482 "
                b"1.00 10.00 ? 1 ALA XA H 1\n"
            ),
        ),
        "unsupported_monomer": single_ala.replace(b"ALA", b"SER"),
        "degenerate_n_ca_c": _replace_once(
            single_ala,
            b"ATOM 3 C C . ALA A 1 1 ? -0.094 0.017 -0.716 ",
            b"ATOM 3 C C . ALA A 1 1 ? -0.966 0.493 1.500 ",
        ),
        "reflected_ala": _replace_once(
            single_ala,
            b"ATOM 5 C CB . ALA A 1 1 ? 1.204 -0.620 1.296 ",
            b"ATOM 5 C CB . ALA A 1 1 ? 0.942064 1.785300 0.676266 ",
        ),
        "heavy_bond_stretch": _replace_once(
            single_ala,
            b"ATOM 4 O O . ALA A 1 1 ? -1.056 -0.682 -0.923 ",
            b"ATOM 4 O O . ALA A 1 1 ? -3.000 -3.000 -3.000 ",
        ),
        "adjacent_c_n_too_short": _translate_middle_gly_x(ala_gly_ala, -0.830),
        "adjacent_c_n_too_long": _translate_middle_gly_x(ala_gly_ala, 0.700),
    }


def _observed_positive(
    case: dict[str, Any], source: bytes
) -> tuple[
    dict[str, Any],
    completion.MmcifStandardLPeptideHeavyCompletionResult,
]:
    result = completion.complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        source, source_id=case["source_id"]
    )
    result_document = result.to_dict()
    mapping = list(result.atom_mapping)
    inventory = result.parameter_requirement_inventory
    source_retained = sum(row["status"] == "source_retained" for row in mapping)
    profile_generated = sum(row["status"] == "profile_generated" for row in mapping)
    observed = {
        "full_source_sha256": result_document["raw_source_sha256"],
        "result_document_sha256": hashlib.sha256(
            _canonical_json_bytes(result_document)
        ).hexdigest(),
        "state_sha256": result_document["state_sha256"],
        "transformed_topology_sha256": result_document[
            "completed_canonical_topology_sha256"
        ],
        "transformed_system_snapshot_sha256": result_document[
            "completed_system_snapshot_sha256"
        ],
        "source_binding_sha256": result_document["result_source_binding_sha256"],
        "report_sha256": result_document["report_sha256"],
        "atom_mapping_document_sha256": result_document["atom_mapping_sha256"],
        "atom_mapping_rows_sha256": hashlib.sha256(
            _canonical_json_bytes(mapping)
        ).hexdigest(),
        "parameter_requirement_inventory_sha256": hashlib.sha256(
            _canonical_json_bytes(inventory)
        ).hexdigest(),
        "atom_count": result_document["completed_atom_count"],
        "bond_count": result_document["completed_bond_count"],
        "residue_count": result_document["residue_count"],
        "chain_count": result_document["chain_count"],
        "source_retained_mapping_count": source_retained,
        "profile_generated_mapping_count": profile_generated,
        "source_heavy_atom_count": result_document["source_heavy_atom_count"],
        "generated_hydrogen_count": result_document["generated_hydrogen_count"],
        "source_heavy_bond_count": result_document["source_heavy_bond_count"],
        "generated_hydrogen_bond_count": result_document[
            "generated_hydrogen_bond_count"
        ],
        "sequence_adjacent_peptide_bond_count": result_document[
            "sequence_adjacent_peptide_bond_count"
        ],
        "atom_parameter_requirement_count": len(inventory["atom_requirements"]),
        "bond_parameter_requirement_count": len(inventory["bond_requirements"]),
        "angle_parameter_requirement_count": len(inventory["angle_requirements"]),
        "proper_torsion_parameter_requirement_count": len(
            inventory["proper_torsion_requirements"]
        ),
        "nonbonded_site_parameter_requirement_count": inventory["nonbonded_site_count"],
        "partial_charge_site_parameter_requirement_count": inventory[
            "partial_charge_site_count"
        ],
        "replay_verified": result.verify_replay(),
    }
    return observed, result


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


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
    assert contracts == {
        "profile_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "policy_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
        "transformer_name": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_NAME,
        "transformer_version": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_VERSION,
        "result_state_schema_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_STATE_SCHEMA_ID,
        "atom_mapping_schema_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID,
        "parameter_requirement_inventory_schema_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID,
        "report_schema_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_REPORT_SCHEMA_ID,
        "source_binding_schema_id": completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_BINDING_SCHEMA_ID,
        "completion_rule_manifest_schema_id": STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID,
        "completion_rule_manifest_sha256": STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256,
        "scope": "exact_ALA_GLY_archive_heavy_to_fixed_neutral_all_atom_completion_only",
        "category_order": list(_CATEGORY_ORDER),
        "supported_components": ["ALA", "GLY"],
        "positive_case_count": len(_POSITIVE_CASE_IDS),
        "failure_case_count": len(_FAILURE_MUTATION_IDS),
        "writer_or_round_trip_claimed": False,
        "bounded_true_fields": list(_BOUNDED_TRUE_FIELDS),
        "false_authority_fields": list(_FALSE_AUTHORITY_FIELDS),
    }
    assert validate_standard_l_peptide_completion_rule_manifest() == (
        STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
    )
    assert manifest["limits"] == {
        "input_bytes": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_INPUT_BYTES,
        "source_id_utf8_bytes": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_ID_BYTES,
        "completed_atoms": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ATOMS,
        "completed_bonds": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_BONDS,
        "parameter_angles": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ANGLES,
        "parameter_propers": completion.MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROPERS,
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
    report = result.to_dict()
    assert all(report[field] is True for field in _BOUNDED_TRUE_FIELDS)
    assert all(report[field] is False for field in _FALSE_AUTHORITY_FIELDS)
    assert report["profile_id"] == manifest["contracts"]["profile_id"]
    assert report["policy_id"] == manifest["contracts"]["policy_id"]
    assert report["completion_rule_manifest_sha256"] == (
        STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
    )
    assert report["generated_hydrogen_count"] > 0
    assert report["all_completed_formal_charges_known_zero"] is True
    assert report["completed_net_formal_charge"] == 0
    assert report["production_parameter_set_status"] == "missing"
    assert result.system.provenance.preparation_ready is False
    assert not hasattr(result, "write_result")


@pytest.mark.parametrize("case_id", _POSITIVE_CASE_IDS)
def test_positive_mapping_charge_coordinate_and_inventory_invariants(
    case_id: str,
) -> None:
    manifest = _load_manifest()
    case = {case["case_id"]: case for case in manifest["positive_cases"]}[case_id]
    source = _fixture_payload(case["fixture"])
    result = completion.complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        source, source_id=case["source_id"]
    )
    mapping = list(result.atom_mapping)
    system = result.system
    archive_system = result.archive_heavy_ingest.system
    inventory = result.parameter_requirement_inventory
    marker_key = completion.MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY

    assert tuple(row["prepared_index"] for row in mapping) == tuple(
        range(system.atom_count)
    )
    assert {row["status"] for row in mapping} == {
        "source_retained",
        "profile_generated",
    }
    assert all(
        atom.formal_charge_known
        and atom.formal_charge == 0
        and atom.partial_charge_e is None
        for atom in system.atoms
    )
    assert all(
        requirement["formal_charge"] == 0
        for requirement in inventory["atom_requirements"]
    )

    row_by_identity = {
        (row["asym_id"], row["sequence_number"], row["atom_id"]): row for row in mapping
    }
    for row in mapping:
        atom = system.atoms[row["prepared_index"]]
        marker = atom.metadata[marker_key]
        assert atom.name == row["atom_id"]
        assert marker["origin"] == row["status"]
        if row["status"] == "source_retained":
            assert atom.element != "H"
            source_index = row["source_index"]
            assert archive_system.atoms[source_index].element == atom.element
            expected_hex = [
                _binary64_hex(value)
                for value in archive_system.coordinates[0, source_index].tolist()
            ]
            completed_hex = [
                _binary64_hex(value)
                for value in system.coordinates[0, atom.index].tolist()
            ]
            assert row["source_coordinate_binary64_be"] == expected_hex
            assert completed_hex == expected_hex
            assert marker["source_atom_index"] == source_index
        else:
            assert atom.element == "H"
            component_rule = standard_l_peptide_completion_component_rule(
                row["component_id"]
            )
            role_rule = standard_l_peptide_completion_role_rule(
                row["component_id"], row["sequence_role"]
            )
            atom_rule = next(
                rule for rule in component_rule.atoms if rule.atom_id == row["atom_id"]
            )
            assert row["atom_id"] in role_rule.active_hydrogen_atom_ids
            assert row["generation_parent_atom_id"] == (
                atom_rule.hydrogen_parent_atom_id
            )
            parent = row_by_identity[
                (
                    row["asym_id"],
                    row["sequence_number"],
                    row["generation_parent_atom_id"],
                )
            ]
            assert parent["status"] == "source_retained"
            assert row["generation_parent_source_index"] == parent["source_index"]
            assert (
                marker["hydrogen_parent_atom_id"] == (row["generation_parent_atom_id"])
            )

    angles = tuple(
        (row["atom_i"], row["atom_j"], row["atom_k"])
        for row in inventory["angle_requirements"]
    )
    propers = tuple(
        (row["atom_i"], row["atom_j"], row["atom_k"], row["atom_l"])
        for row in inventory["proper_torsion_requirements"]
    )
    assert len(angles) == len(set(angles))
    assert all(atom_i < atom_k for atom_i, _, atom_k in angles)
    assert len(propers) == len(set(propers))
    assert all(path <= tuple(reversed(path)) for path in propers)
    assert inventory["partial_charge_site_count"] == system.atom_count
    assert inventory["production_parameter_set_status"] == "missing"
    assert inventory["parameterability_assessed"] is False
    assert inventory["parameterizable"] is False
    assert inventory["improper_torsions_enumerated"] is False
    assert inventory["cmap_terms_enumerated"] is False


def test_corpus_fixture_budget_case_sets_and_paths_are_exact() -> None:
    manifest = _load_manifest()
    positive = manifest["positive_cases"]
    failure = manifest["failure_cases"]
    assert tuple(case["case_id"] for case in positive) == _POSITIVE_CASE_IDS
    assert tuple(case["mutation_id"] for case in failure) == _FAILURE_MUTATION_IDS
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
    assert total == 7094
    assert total <= _MAX_TOTAL_FIXTURE_BYTES


def test_manifest_decoder_paths_symlinks_and_size_caps_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(StandardLPeptideHeavyCompletionCorpusError):
        _decode_manifest(b'{"a":1,"a":2}')
    with pytest.raises(StandardLPeptideHeavyCompletionCorpusError):
        _decode_manifest(b'{"value":"\x80"}')
    with pytest.raises(StandardLPeptideHeavyCompletionCorpusError):
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
        with pytest.raises(StandardLPeptideHeavyCompletionCorpusError):
            _fixture_payload(invalid)

    manifest_target = tmp_path / "manifest-target.json"
    manifest_target.write_bytes(b"{}")
    manifest_link = tmp_path / "manifest.json"
    manifest_link.symlink_to(manifest_target)
    monkeypatch.setattr(sys.modules[__name__], "MANIFEST", manifest_link)
    with pytest.raises(
        StandardLPeptideHeavyCompletionCorpusError,
        match="manifest must be a regular fixed file",
    ):
        _load_manifest()

    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    fixture_target = tmp_path / "outside.cif"
    fixture_target.write_bytes(b"data_outside\n")
    (fixture_root / "linked.cif").symlink_to(fixture_target)
    monkeypatch.setattr(sys.modules[__name__], "FIXTURE_ROOT", fixture_root)
    with pytest.raises(
        StandardLPeptideHeavyCompletionCorpusError,
        match="fixture must be a regular fixed file",
    ):
        _fixture_payload("linked.cif")
    (fixture_root / "oversized.cif").write_bytes(b"x" * (_MAX_FIXTURE_BYTES + 1))
    with pytest.raises(
        StandardLPeptideHeavyCompletionCorpusError,
        match="fixture exceeds byte cap",
    ):
        _fixture_payload("oversized.cif")


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
    single_ala = _fixture_payload("single_ala.cif")
    ala_gly_ala = _fixture_payload("ala_gly_ala.cif")
    mutations = _source_mutations(single_ala, ala_gly_ala)
    assert tuple(mutations) == _FAILURE_MUTATION_IDS
    mutated = mutations[mutation_id]
    assert case["fixture"] == (
        "ala_gly_ala.cif"
        if mutation_id.startswith("adjacent_c_n_")
        else "single_ala.cif"
    )
    assert mutated != _fixture_payload(case["fixture"])
    assert len(mutated) == case["mutated_byte_count"]
    assert hashlib.sha256(mutated).hexdigest() == case["mutated_sha256"]
    assert _LOWER_SHA256.fullmatch(case["mutated_sha256"])
    with pytest.raises(
        completion.MmcifStandardLPeptideHeavyCompletionError
    ) as exc_info:
        completion.complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
            mutated, source_id=f"corpus-failure:{mutation_id}"
        )
    assert exc_info.value.code == case["expected_error_code"]


def test_unknown_policy_cannot_promote_a_valid_fixture() -> None:
    source = _fixture_payload("single_gly.cif")
    with pytest.raises(
        completion.MmcifStandardLPeptideHeavyCompletionError
    ) as exc_info:
        completion.complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
            source, policy_id="not-the-pinned-policy"
        )
    assert exc_info.value.code == "unsupported_policy_id"
