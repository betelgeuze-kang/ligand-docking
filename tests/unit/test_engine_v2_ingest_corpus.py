from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

import pytest

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID
from betelgeuze_engine_v2.molecular import (
    AROMATICITY_REQUIREMENT_STATUSES,
    CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID,
    CANONICAL_INGEST_CLAIM_SCOPE,
    CANONICAL_SNAPSHOT_VERSION,
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE,
    CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID,
    CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS,
    CONTEXTUAL_COMPONENT_UNASSESSED_STATUS,
    CANONICAL_MARKER_OBSERVED_STATUS,
    EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID,
    FORMAL_CHARGE_OBSERVATION_STATUSES,
    MAX_CHEMISTRY_AUDIT_ATOMS,
    MAX_CHEMISTRY_AUDIT_BONDS,
    MAX_PREPARATION_AUDIT_ATOMS,
    MAX_PREPARATION_AUDIT_BONDS,
    MAX_PREPARATION_AUDIT_CHAINS,
    MAX_PREPARATION_AUDIT_RESIDUES,
    MMCIF_PARSER_VERSION,
    ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID,
    PARAMETERABILITY_STATUS,
    PARSER_OBSERVATION_SCHEMA_ID,
    PDB_PARSER_VERSION,
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    PROFILE_HYDROGEN_VALENCE_STATUSES,
    PROFILE_LOCAL_EVIDENCE_STATUSES,
    PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE,
    PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID,
    SDF_V2000_PARSER_VERSION,
    SMILES_PARSER_VERSION,
    SOURCE_AUTHENTICATION_STATUS,
    SOURCE_HYDROGEN_INVENTORY_STATUSES,
    STRUCTURE_INGEST_SUPPORT_SCOPE,
    SdfV2000ParseError,
    SmilesParseError,
    StructureParseError,
    analyze_canonical_chemistry,
    analyze_canonical_ingest_applicability,
    analyze_contextual_component_inventory,
    analyze_molecular_preparation,
    analyze_profile_local_preparation_evidence,
    attached_canonical_topology_sha256_matches,
    attached_parser_observation_sha256_matches,
    canonical_all_atom_snapshot_digest,
    canonical_all_atom_systems_equal,
    canonical_topology_document,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    parse_mmcif,
    parse_pdb,
    parse_sdf_v2000,
    parse_smiles,
    serialize_all_atom_system,
    serialize_canonical_topology,
)
from betelgeuze_engine_v2.molecular import mmcif_syntax, pdb_mmcif, sdf_v2000
from betelgeuze_engine_v2.molecular import smiles as smiles_module


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT / "config" / "independent_engine_v2_v2_1_ingest_corpus.json"
)
CORPUS_SCHEMA_ID = "betelgeuze.v2_1_ingest_corpus/1.4.0"
CORPUS_ID = "v2_1_supported_ingest_identity_context_and_failure_v5"
RESOURCE_PROFILE_ID = "v2_1_selected_primary_ingest_limits_v2"
RDKIT_REQUIREMENT = "rdkit==2025.9.6"
_LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_FORMATS = frozenset({"pdb", "mmcif", "sdf_v2000", "smiles"})
_LANES = frozenset(
    {
        "ingest_success",
        "canonical_ingest_profile_supported",
        "ingest_only_abstention",
        "parse_failure",
    }
)
_EXPECTED_CASE_LANES = {
    "pdb_mini_protein": "ingest_success",
    "mmcif_mini_protein": "ingest_success",
    "sdf_v2000_ethanol": "ingest_success",
    "sdf_v2000_methane_explicit_h": "canonical_ingest_profile_supported",
    "sdf_v2000_ethane_explicit_h": "canonical_ingest_profile_supported",
    "sdf_v2000_propane_explicit_h": "canonical_ingest_profile_supported",
    "sdf_v2000_n_butane_explicit_h": "canonical_ingest_profile_supported",
    "sdf_v2000_isobutane_branched_explicit_h": ("canonical_ingest_profile_supported"),
    "sdf_v2000_cyclobutane_explicit_h": "ingest_success",
    "sdf_v2000_ethane_missing_h": "ingest_success",
    "smiles_benzene": "ingest_success",
    "smiles_sodium_chloride_abstention": "ingest_only_abstention",
    "sdf_v2000_methane_c13_explicit_h": "ingest_success",
    "smiles_isotopic_water": "ingest_success",
    "smiles_chiral_s": "ingest_success",
    "smiles_chiral_r": "ingest_success",
    "smiles_alkene_e": "ingest_success",
    "smiles_alkene_z": "ingest_success",
    "mmcif_context_inventory": "ingest_only_abstention",
    "sdf_atom_parity_rejected": "parse_failure",
    "sdf_bond_stereo_rejected": "parse_failure",
    "sdf_mass_difference_rejected": "parse_failure",
    "smiles_nontetrahedral_stereo_rejected": "parse_failure",
    "smiles_unretained_stereo_marker_rejected": "parse_failure",
    "smiles_invalid_isotope_rejected": "parse_failure",
    "pdb_altloc_requires_selection": "parse_failure",
    "pdb_contextual_metal_conect_rejected": "parse_failure",
    "mmcif_explicit_topology_category": "parse_failure",
    "mmcif_ion_context_rejected": "parse_failure",
    "mmcif_modified_residue_context_rejected": "parse_failure",
    "mmcif_nonpoly_component_context_rejected": "parse_failure",
    "sdf_v3000_rejected": "parse_failure",
    "smiles_trailing_lf_rejected": "parse_failure",
    "smiles_radical_rejected": "parse_failure",
}
_EXPECTED_CASE_RECORD_SHA256 = {
    "pdb_mini_protein": "df2b777f20cbf1d155ba653ae529eaad59861768ee0c90e36641e957ad624c39",
    "mmcif_mini_protein": "a9c2a5581ea82c6d634eddccb85d3f5d5091e9a29e80293c403640c462ca5a3a",
    "sdf_v2000_ethanol": "5aa43a91e3905639271dcd6117868ed93e9de2af47e36d291dea628715778ffd",
    "sdf_v2000_methane_explicit_h": (
        "14e9980db27dec43ae76199d681080459f703c5661850e5401539583c1394ff1"
    ),
    "sdf_v2000_ethane_explicit_h": (
        "24457349e8ed52e241bceafc608b2dad064a5715c924a85537b9855dcf0c88f9"
    ),
    "sdf_v2000_propane_explicit_h": (
        "a88832cc3924dbe6862b5356f7dede75f9121b1253ffde013f30dce43375b2b6"
    ),
    "sdf_v2000_n_butane_explicit_h": (
        "a02a55f485d2bf87615f651937da1d1e349b5bdb72a16da9d54590377c9bef63"
    ),
    "sdf_v2000_isobutane_branched_explicit_h": (
        "87b8927ab553f35699ab5b2d21703c059539fba6892252324143e8daa914b5bb"
    ),
    "sdf_v2000_cyclobutane_explicit_h": (
        "c72f5d490b9d55eed8ed8ad3492832905cc7439b154524892ea4b6dd6c984500"
    ),
    "sdf_v2000_ethane_missing_h": (
        "4d53c0950064c37d0afea80b6da63c30fbb7132d0140ddfad1b9801c08298d39"
    ),
    "smiles_benzene": "981a33ca24b3ffb6476071df3075e31ff02c0b1410d91c7f7d71b2d2d8ab5598",
    "smiles_sodium_chloride_abstention": (
        "57ef99edb72ef187b1c557d35655d704b23a15c5a2cf5d128c9757fb2714648f"
    ),
    "sdf_v2000_methane_c13_explicit_h": (
        "a8db03c72c91480f436d0c3ef6ce12c158989b4ec23e76a070b04eae0e645210"
    ),
    "smiles_isotopic_water": "72680c35399b7c819cd0ba13cf3f90fb7ffa56c59b9bb0cec0af287319b8f942",
    "smiles_chiral_s": "b61d219596a8e8be014a7c9ef5c4c97d736e8d3b967a015e1102b3ce12d3d1f0",
    "smiles_chiral_r": "b67dbdf4ca12f4a18aadc250ddc828a12db16aeb1f01964872f744bba00888a7",
    "smiles_alkene_e": "c686d06882d579f498ff5038d20a1f479404e547fbcacc5c4aa52f1c36c3ec98",
    "smiles_alkene_z": "b39e94deaa33190a33f29f535e165b0e553dcf926c979c52a80b8f74f7ac6939",
    "mmcif_context_inventory": (
        "a975aa60fcfa0d99514af049a3f1f1bdf5845e31c3b38ab198a15f7ec80559ec"
    ),
    "sdf_atom_parity_rejected": "535ca1110f37275575a29ef559b82e3de40d7dc64eead8171865d781864ff31d",
    "sdf_bond_stereo_rejected": "0122f679ee35b11021f347516ff3a7c01972dbbfe286905222a069fb7918dd7a",
    "sdf_mass_difference_rejected": (
        "489e8e93bdfc70d2e91ee61a0899d45c1b53e813377438f22798325dc5f90125"
    ),
    "smiles_nontetrahedral_stereo_rejected": (
        "6c29e6e4fab24324e678ba9c075328ccff3e93174bb572872124c02903a03fc4"
    ),
    "smiles_unretained_stereo_marker_rejected": (
        "d9b0162f0c81c813d7f44c526a50236412d14437c05b5053b2a17bd0e785575b"
    ),
    "smiles_invalid_isotope_rejected": (
        "2c5be599ca99b62672d9c32d4484ec25a18464dedb9675506e10464ac742dcfc"
    ),
    "pdb_altloc_requires_selection": (
        "d8af00f890fae779ac33dbe31e335bf24db8547d382dc464ec993821eca6d378"
    ),
    "pdb_contextual_metal_conect_rejected": (
        "97eeccdb102a8dc4db990d9f4e9b7c00a2651f0f7670fd7b25219ecb949ec4ab"
    ),
    "mmcif_explicit_topology_category": (
        "857b62cbaadc426d942fe58b4df63a5f0829259c42421dd078b383d2d09fc855"
    ),
    "mmcif_ion_context_rejected": (
        "554a583899a67368773037552c9b18bf31d0c41d6a6a734033f0cf13ff3a58d0"
    ),
    "mmcif_modified_residue_context_rejected": (
        "8dc483431e57050ce5160da86421cf001182c3936c9191d700241cbc79163373"
    ),
    "mmcif_nonpoly_component_context_rejected": (
        "371b554284896623d2a74a81e83d66feadef9a9d3e2a6b97fb9cd75ccee92a4c"
    ),
    "sdf_v3000_rejected": "b13b4d28f059df58cddd9a4c3d17a60432300a1b9c0030a00bb64476bdcbf716",
    "smiles_trailing_lf_rejected": (
        "ec26e2e1b6bf896d7bf56be231b82cc324d4036bc09b6ff753c86d8db3b6f366"
    ),
    "smiles_radical_rejected": "51507474df4bbf707c9a8b8309b8cc420501fe2e7427756bfe91ca1efa62d37e",
}
_SELECTED_SUPPORTED_PROFILE_CASE_IDS = frozenset(
    {
        "sdf_v2000_methane_explicit_h",
        "sdf_v2000_ethane_explicit_h",
        "sdf_v2000_propane_explicit_h",
        "sdf_v2000_n_butane_explicit_h",
        "sdf_v2000_isobutane_branched_explicit_h",
    }
)
_SELECTED_PROFILE_BOUNDARY_FAILURES = {
    "sdf_v2000_cyclobutane_explicit_h": (
        ("acyclic_graph",),
        "satisfied_for_declared_canonical_graph",
        "profile_requirements_not_satisfied",
    ),
    "sdf_v2000_ethane_missing_h": (
        ("explicit_valence_closed",),
        "not_satisfied",
        "not_applicable_to_acyclic_single_bond_profile",
    ),
}


class CorpusManifestError(ValueError):
    """Raised when the immutable V2.1 corpus manifest is ambiguous or unsafe."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusManifestError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CorpusManifestError(f"{context} must be a JSON object")
    return value


def _expect_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise CorpusManifestError(
            f"{context} keys do not match schema; missing={missing}, unknown={unknown}"
        )


def _exact_typed_structure_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _exact_typed_structure_equal(actual[key], expected_value)
            for key, expected_value in expected.items()
        )
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _exact_typed_structure_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return bool(actual == expected)


def _expect_nonempty_string(value: Any, context: str) -> str:
    if type(value) is not str or not value:
        raise CorpusManifestError(f"{context} must be a nonempty string")
    return value


def _expect_sha256(value: Any, context: str) -> str:
    digest = _expect_nonempty_string(value, context)
    if _LOWERCASE_SHA256.fullmatch(digest) is None:
        raise CorpusManifestError(f"{context} must be a lowercase SHA-256")
    return digest


def _expect_string_list(value: Any, context: str) -> list[str]:
    if type(value) is not list or not all(type(item) is str and item for item in value):
        raise CorpusManifestError(f"{context} must be a list of nonempty strings")
    if len(set(value)) != len(value):
        raise CorpusManifestError(f"{context} must not contain duplicates")
    return value


def _validate_identity_assignments(
    value: Any,
    *,
    context: str,
    index_key: str,
    value_key: str,
    atom_or_bond_count: int,
    allowed_strings: frozenset[str] | None = None,
) -> None:
    if type(value) is not list:
        raise CorpusManifestError(f"{context} must be a list")
    previous_index = -1
    for entry_index, entry_value in enumerate(value):
        entry = _expect_mapping(entry_value, f"{context}[{entry_index}]")
        _expect_exact_keys(
            entry,
            {index_key, value_key},
            f"{context}[{entry_index}]",
        )
        identity_index = entry[index_key]
        if (
            type(identity_index) is not int
            or identity_index < 0
            or identity_index >= atom_or_bond_count
            or identity_index <= previous_index
        ):
            raise CorpusManifestError(
                f"{context} indices must be unique, sorted, and in range"
            )
        previous_index = identity_index
        observed = entry[value_key]
        if value_key == "mass_number":
            if type(observed) is not int or not 1 <= observed <= 350:
                raise CorpusManifestError(
                    f"{context}.mass_number must be an integer in [1, 350]"
                )
        elif type(observed) is not str or (
            allowed_strings is not None and observed not in allowed_strings
        ):
            raise CorpusManifestError(f"{context}.{value_key} is invalid")


def _load_json_manifest(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError("corpus manifest data must be bytes")
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CorpusManifestError(f"nonstandard JSON constant {token!r}")
            ),
        )
    except CorpusManifestError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusManifestError("corpus manifest must be strict UTF-8 JSON") from exc
    return _expect_mapping(value, "manifest")


def _validate_contracts(value: Any) -> None:
    contracts = _expect_mapping(value, "contracts")
    _expect_exact_keys(
        contracts,
        {
            "system_schema_id",
            "canonical_snapshot_version",
            "canonical_topology_schema_id",
            "parser_observation_schema_id",
            "chemistry_coverage_schema_version",
            "chemistry_profile_id",
            "canonical_ingest_applicability_schema_id",
            "canonical_ingest_profile_id",
            "canonical_ingest_claim_scope",
            "profile_local_preparation_evidence_schema_id",
            "profile_local_preparation_claim_scope",
            "contextual_component_inventory_schema_id",
            "contextual_component_inventory_claim_scope",
            "contextual_component_source_authentication_status",
            "source_authentication_status",
            "parameterability_status",
            "preparation_report_schema_version",
            "preparation_policy_id",
            "structure_ingest_support_scope",
            "parser_versions",
            "smiles_rdkit_version_key",
            "smiles_rdkit_observed_version",
        },
        "contracts",
    )
    parser_versions = _expect_mapping(contracts["parser_versions"], "parser_versions")
    _expect_exact_keys(parser_versions, set(_FORMATS), "parser_versions")
    expected = {
        "system_schema_id": ALL_ATOM_SCHEMA_ID,
        "canonical_snapshot_version": CANONICAL_SNAPSHOT_VERSION,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "chemistry_coverage_schema_version": CHEMISTRY_COVERAGE_SCHEMA_VERSION,
        "chemistry_profile_id": ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID,
        "canonical_ingest_applicability_schema_id": (
            CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID
        ),
        "canonical_ingest_profile_id": (
            EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID
        ),
        "canonical_ingest_claim_scope": CANONICAL_INGEST_CLAIM_SCOPE,
        "profile_local_preparation_evidence_schema_id": (
            PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID
        ),
        "profile_local_preparation_claim_scope": (
            PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE
        ),
        "contextual_component_inventory_schema_id": (
            CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID
        ),
        "contextual_component_inventory_claim_scope": (
            CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE
        ),
        "contextual_component_source_authentication_status": (
            CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS
        ),
        "source_authentication_status": SOURCE_AUTHENTICATION_STATUS,
        "parameterability_status": PARAMETERABILITY_STATUS,
        "preparation_report_schema_version": PREPARATION_REPORT_SCHEMA_VERSION,
        "preparation_policy_id": PREPARATION_POLICY_ID,
        "structure_ingest_support_scope": STRUCTURE_INGEST_SUPPORT_SCOPE,
        "parser_versions": {
            "pdb": PDB_PARSER_VERSION,
            "mmcif": MMCIF_PARSER_VERSION,
            "sdf_v2000": SDF_V2000_PARSER_VERSION,
            "smiles": SMILES_PARSER_VERSION,
        },
        "smiles_rdkit_version_key": "2025.9.6",
        "smiles_rdkit_observed_version": "2025.09.6",
    }
    if contracts != expected:
        raise CorpusManifestError(
            "manifest contract pins do not match runtime contracts"
        )


def _validate_resource_profile(value: Any) -> None:
    profile = _expect_mapping(value, "resource_profile")
    _expect_exact_keys(
        profile,
        {
            "profile_id",
            "scope",
            "pdb",
            "mmcif",
            "sdf_v2000",
            "smiles",
            "chemistry_audit",
            "preparation_audit",
        },
        "resource_profile",
    )
    expected = {
        "profile_id": RESOURCE_PROFILE_ID,
        "scope": "selected_primary_limits_not_exhaustive",
        "pdb": {
            "max_input_bytes": pdb_mmcif._MAX_PDB_INPUT_BYTES,
            "max_atom_rows": pdb_mmcif._MAX_PDB_ATOM_ROWS,
            "max_line_count": pdb_mmcif._MAX_PDB_LINE_COUNT,
        },
        "mmcif": {
            "max_input_bytes": pdb_mmcif._MAX_MMCIF_INPUT_BYTES,
            "max_atom_rows": pdb_mmcif._MAX_MMCIF_ATOM_ROWS,
            "max_token_count": mmcif_syntax.MAX_CIF_TOKEN_COUNT,
            "max_line_count": mmcif_syntax._MAX_CIF_LINE_COUNT,
            "max_line_chars": mmcif_syntax._MAX_CIF_LINE_LENGTH,
            "max_assembly_output_atoms": (pdb_mmcif._MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS),
        },
        "sdf_v2000": {
            "max_input_bytes": sdf_v2000._MAX_SDF_INPUT_BYTES,
            "max_line_count": sdf_v2000._MAX_SDF_LINE_COUNT,
            "max_line_chars": sdf_v2000._MAX_SDF_LINE_CHARS,
        },
        "smiles": {
            "max_input_bytes": smiles_module._MAX_INPUT_BYTES,
            "max_source_atoms": smiles_module._MAX_SOURCE_ATOMS,
            "max_expanded_atoms": smiles_module._MAX_EXPANDED_ATOMS,
            "max_bonds": smiles_module._MAX_BONDS,
            "max_fragments": smiles_module._MAX_FRAGMENTS,
        },
        "chemistry_audit": {
            "max_atoms": MAX_CHEMISTRY_AUDIT_ATOMS,
            "max_bonds": MAX_CHEMISTRY_AUDIT_BONDS,
        },
        "preparation_audit": {
            "max_atoms": MAX_PREPARATION_AUDIT_ATOMS,
            "max_bonds": MAX_PREPARATION_AUDIT_BONDS,
            "max_residues": MAX_PREPARATION_AUDIT_RESIDUES,
            "max_chains": MAX_PREPARATION_AUDIT_CHAINS,
        },
    }
    if not _exact_typed_structure_equal(profile, expected):
        raise CorpusManifestError(
            "manifest resource profile does not match runtime limits"
        )


def _validate_claim_boundary(value: Any) -> None:
    boundary = _expect_mapping(value, "claim_boundary")
    expected = {
        "canonical_ingest_profile_support_is_chemistry_support": False,
        "profile_local_evidence_is_global_preparation": False,
        "chemistry_supported": False,
        "parameterability_assessed": False,
        "parameterizable": False,
        "preparation_assessed": False,
        "preparation_ready": False,
        "simulation_ready": False,
        "claim_safe": False,
    }
    if not _exact_typed_structure_equal(boundary, expected):
        raise CorpusManifestError(
            "V2.1 ingest corpus must retain the fail-closed boundary"
        )


def _validate_source(value: Any, context: str) -> None:
    source = _expect_mapping(value, context)
    kind = source.get("kind")
    if kind == "fixture":
        _expect_exact_keys(source, {"kind", "path"}, context)
        raw_path = _expect_nonempty_string(source["path"], f"{context}.path")
        path = PurePosixPath(raw_path)
        if (
            path.is_absolute()
            or "\\" in raw_path
            or raw_path != path.as_posix()
            or any(part in {"", ".", ".."} for part in raw_path.split("/"))
            or path.parts[:2] != ("tests", "fixtures")
        ):
            raise CorpusManifestError(
                f"{context}.path must stay under the tests/fixtures POSIX path"
            )
    elif kind == "ascii":
        _expect_exact_keys(source, {"kind", "value"}, context)
        raw_value = _expect_nonempty_string(source["value"], f"{context}.value")
        try:
            raw_value.encode("ascii", errors="strict")
        except UnicodeEncodeError as exc:
            raise CorpusManifestError(f"{context}.value must be exact ASCII") from exc
    else:
        raise CorpusManifestError(f"{context}.kind is unsupported")


def _validate_success_expected(value: Any, context: str) -> None:
    expected = _expect_mapping(value, context)
    _expect_exact_keys(
        expected,
        {
            "atom_count",
            "bond_count",
            "canonical_topology_sha256",
            "canonical_snapshot_sha256",
            "chemistry_report_sha256",
            "preparation_report_sha256",
            "applicability_report_sha256",
            "profile_local_preparation_report_sha256",
            "contextual_component_inventory_report_sha256",
            "canonical_ingest_status",
            "canonical_ingest_supported",
            "applicability_failed_constraint_codes",
            "profile_local_evidence_status",
            "profile_local_evidence_satisfied",
            "source_hydrogen_inventory_status",
            "profile_hydrogen_valence_status",
            "formal_charge_observation_status",
            "aromaticity_requirement_status",
            "polymer_missing_residue_status",
            "isotope_assignments",
            "atom_stereo_assignments",
            "bond_stereo_assignments",
            "parameterability_status",
            "graph_representable",
            "chemistry_blockers",
            "preparation_blockers",
        },
        context,
    )
    for name in ("atom_count", "bond_count"):
        count = expected[name]
        if type(count) is not int or count < 0:
            raise CorpusManifestError(
                f"{context}.{name} must be a non-negative integer"
            )
    for name in (
        "canonical_topology_sha256",
        "canonical_snapshot_sha256",
        "chemistry_report_sha256",
        "preparation_report_sha256",
        "applicability_report_sha256",
        "profile_local_preparation_report_sha256",
        "contextual_component_inventory_report_sha256",
    ):
        _expect_sha256(expected[name], f"{context}.{name}")
    if expected["canonical_ingest_status"] not in {"supported", "unsupported"}:
        raise CorpusManifestError(
            f"{context}.canonical_ingest_status must be supported or unsupported"
        )
    if type(expected["canonical_ingest_supported"]) is not bool:
        raise CorpusManifestError(
            f"{context}.canonical_ingest_supported must be a boolean"
        )
    if expected["canonical_ingest_supported"] != (
        expected["canonical_ingest_status"] == "supported"
    ):
        raise CorpusManifestError(
            f"{context} canonical ingest status and support disagree"
        )
    _expect_string_list(
        expected["applicability_failed_constraint_codes"],
        f"{context}.applicability_failed_constraint_codes",
    )
    if expected["profile_local_evidence_status"] not in (
        PROFILE_LOCAL_EVIDENCE_STATUSES
    ):
        raise CorpusManifestError(f"{context}.profile_local_evidence_status is invalid")
    if type(expected["profile_local_evidence_satisfied"]) is not bool:
        raise CorpusManifestError(
            f"{context}.profile_local_evidence_satisfied must be a boolean"
        )
    if expected["profile_local_evidence_satisfied"] != (
        expected["profile_local_evidence_status"] == "satisfied"
    ):
        raise CorpusManifestError(
            f"{context} profile-local evidence status and decision disagree"
        )
    status_domains = {
        "source_hydrogen_inventory_status": SOURCE_HYDROGEN_INVENTORY_STATUSES,
        "profile_hydrogen_valence_status": PROFILE_HYDROGEN_VALENCE_STATUSES,
        "formal_charge_observation_status": FORMAL_CHARGE_OBSERVATION_STATUSES,
        "aromaticity_requirement_status": AROMATICITY_REQUIREMENT_STATUSES,
        "polymer_missing_residue_status": {
            "unassessed",
            "not_applicable_to_single_nonpolymer_source",
        },
    }
    for name, domain in status_domains.items():
        if expected[name] not in domain:
            raise CorpusManifestError(f"{context}.{name} is invalid")
    _validate_identity_assignments(
        expected["isotope_assignments"],
        context=f"{context}.isotope_assignments",
        index_key="atom_index",
        value_key="mass_number",
        atom_or_bond_count=expected["atom_count"],
    )
    _validate_identity_assignments(
        expected["atom_stereo_assignments"],
        context=f"{context}.atom_stereo_assignments",
        index_key="atom_index",
        value_key="stereo",
        atom_or_bond_count=expected["atom_count"],
        allowed_strings=frozenset({"R", "S", "UNKNOWN"}),
    )
    _validate_identity_assignments(
        expected["bond_stereo_assignments"],
        context=f"{context}.bond_stereo_assignments",
        index_key="bond_index",
        value_key="stereo",
        atom_or_bond_count=expected["bond_count"],
        allowed_strings=frozenset(
            {"E", "Z", "UNKNOWN", "EITHER", "CIS", "TRANS", "UP", "DOWN"}
        ),
    )
    if expected["parameterability_status"] != PARAMETERABILITY_STATUS:
        raise CorpusManifestError(
            f"{context}.parameterability_status does not match the fixed contract"
        )
    if type(expected["graph_representable"]) is not bool:
        raise CorpusManifestError(f"{context}.graph_representable must be a boolean")
    _expect_string_list(expected["chemistry_blockers"], f"{context}.chemistry_blockers")
    _expect_string_list(
        expected["preparation_blockers"],
        f"{context}.preparation_blockers",
    )


def _validate_failure_expected(value: Any, context: str) -> None:
    expected = _expect_mapping(value, context)
    _expect_exact_keys(
        expected,
        {"exception_type", "error_code", "line_number", "byte_position"},
        context,
    )
    _expect_nonempty_string(expected["exception_type"], f"{context}.exception_type")
    _expect_nonempty_string(expected["error_code"], f"{context}.error_code")
    for name in ("line_number", "byte_position"):
        location = expected[name]
        if location is not None and (type(location) is not int or location < 0):
            raise CorpusManifestError(
                f"{context}.{name} must be a non-negative integer or null"
            )


def _validate_case(value: Any, index: int) -> dict[str, Any]:
    context = f"cases[{index}]"
    case = _expect_mapping(value, context)
    _expect_exact_keys(
        case,
        {
            "case_id",
            "lane",
            "format",
            "source",
            "source_sha256",
            "source_id",
            "parser_options",
            "environment_requirements",
            "expected",
        },
        context,
    )
    case_id = _expect_nonempty_string(case["case_id"], f"{context}.case_id")
    if _CASE_ID.fullmatch(case_id) is None:
        raise CorpusManifestError(f"{context}.case_id is not canonical")
    lane = case["lane"]
    if lane not in _LANES:
        raise CorpusManifestError(f"{context}.lane is unsupported")
    source_format = case["format"]
    if source_format not in _FORMATS:
        raise CorpusManifestError(f"{context}.format is unsupported")
    _validate_source(case["source"], f"{context}.source")
    _expect_sha256(case["source_sha256"], f"{context}.source_sha256")
    _expect_nonempty_string(case["source_id"], f"{context}.source_id")
    if case["parser_options"] != {}:
        raise CorpusManifestError(
            f"{context}.parser_options must be empty in schema v1"
        )
    requirements = _expect_string_list(
        case["environment_requirements"],
        f"{context}.environment_requirements",
    )
    if requirements not in ([], [RDKIT_REQUIREMENT]):
        raise CorpusManifestError(
            f"{context} has an unsupported environment requirement"
        )
    if requirements and source_format != "smiles":
        raise CorpusManifestError(
            f"{context} applies an RDKit requirement to a non-SMILES case"
        )
    if lane == "parse_failure":
        _validate_failure_expected(case["expected"], f"{context}.expected")
        expected_exception = {
            "pdb": "StructureParseError",
            "mmcif": "StructureParseError",
            "sdf_v2000": "SdfV2000ParseError",
            "smiles": "SmilesParseError",
        }[source_format]
        if case["expected"]["exception_type"] != expected_exception:
            raise CorpusManifestError(
                f"{context}.expected.exception_type does not match the parser"
            )
    else:
        _validate_success_expected(case["expected"], f"{context}.expected")
        expected_support = lane == "canonical_ingest_profile_supported"
        if case["expected"]["canonical_ingest_supported"] is not expected_support:
            raise CorpusManifestError(
                f"{context}.lane disagrees with canonical ingest support"
            )
        if case["expected"]["profile_local_evidence_satisfied"] is not expected_support:
            raise CorpusManifestError(
                f"{context}.lane disagrees with profile-local evidence"
            )
    return case


def _validate_manifest(value: Any) -> dict[str, Any]:
    manifest = _expect_mapping(value, "manifest")
    _expect_exact_keys(
        manifest,
        {
            "schema_id",
            "corpus_id",
            "contracts",
            "resource_profile",
            "claim_boundary",
            "cases",
        },
        "manifest",
    )
    if manifest["schema_id"] != CORPUS_SCHEMA_ID:
        raise CorpusManifestError("unsupported corpus manifest schema")
    if manifest["corpus_id"] != CORPUS_ID:
        raise CorpusManifestError("unsupported schema-1.4 corpus identity")
    _validate_contracts(manifest["contracts"])
    _validate_resource_profile(manifest["resource_profile"])
    _validate_claim_boundary(manifest["claim_boundary"])
    raw_cases = manifest["cases"]
    if type(raw_cases) is not list or not raw_cases or len(raw_cases) > 1000:
        raise CorpusManifestError("cases must be a bounded nonempty list")
    cases = [_validate_case(value, index) for index, value in enumerate(raw_cases)]
    case_ids = [case["case_id"] for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise CorpusManifestError("case_id values must be unique")
    observed_case_lanes = {case["case_id"]: case["lane"] for case in cases}
    if observed_case_lanes != _EXPECTED_CASE_LANES:
        raise CorpusManifestError("schema-1.4 case and lane inventory changed")
    observed_case_record_sha256 = {
        case["case_id"]: hashlib.sha256(
            json.dumps(
                case,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        for case in cases
    }
    if observed_case_record_sha256 != _EXPECTED_CASE_RECORD_SHA256:
        raise CorpusManifestError("schema-1.4 case records changed")
    lane_counts = {lane: sum(case["lane"] == lane for case in cases) for lane in _LANES}
    if lane_counts != {
        "ingest_success": 12,
        "canonical_ingest_profile_supported": 5,
        "ingest_only_abstention": 2,
        "parse_failure": 15,
    }:
        raise CorpusManifestError("schema-1.4 corpus lane inventory changed")
    success_formats = {
        case["format"] for case in cases if case["lane"] == "ingest_success"
    }
    failure_formats = {
        case["format"] for case in cases if case["lane"] == "parse_failure"
    }
    if success_formats != _FORMATS or failure_formats != _FORMATS:
        raise CorpusManifestError(
            "every parser format requires success and failure evidence"
        )
    supported_profile_case_ids = {
        case["case_id"]
        for case in cases
        if case["lane"] == "canonical_ingest_profile_supported"
    }
    if supported_profile_case_ids != _SELECTED_SUPPORTED_PROFILE_CASE_IDS:
        raise CorpusManifestError("schema-1.4 supported profile inventory changed")
    rdkit_case_ids = {
        case["case_id"]
        for case in cases
        if case["environment_requirements"] == [RDKIT_REQUIREMENT]
    }
    if rdkit_case_ids != {
        "smiles_benzene",
        "smiles_sodium_chloride_abstention",
        "smiles_isotopic_water",
        "smiles_chiral_r",
        "smiles_chiral_s",
        "smiles_alkene_e",
        "smiles_alkene_z",
        "smiles_nontetrahedral_stereo_rejected",
        "smiles_unretained_stereo_marker_rejected",
        "smiles_invalid_isotope_rejected",
        "smiles_radical_rejected",
    }:
        raise CorpusManifestError("schema-1.4 RDKit dependency classification changed")
    return manifest


def _read_source(case: dict[str, Any]) -> bytes:
    source = case["source"]
    if source["kind"] == "ascii":
        data = source["value"].encode("ascii", errors="strict")
    else:
        try:
            candidate = (REPOSITORY_ROOT / source["path"]).resolve(strict=True)
            candidate.relative_to(REPOSITORY_ROOT.resolve())
            candidate.relative_to((REPOSITORY_ROOT / "tests" / "fixtures").resolve())
        except (FileNotFoundError, ValueError) as exc:
            raise CorpusManifestError(
                "fixture path is missing or escapes tests/fixtures"
            ) from exc
        if not candidate.is_file():
            raise CorpusManifestError(
                f"fixture is not a regular file: {source['path']}"
            )
        data = candidate.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != case["source_sha256"]:
        raise CorpusManifestError(
            f"source digest mismatch for case {case['case_id']}: expected immutable bytes"
        )
    return data


def _parse(case: dict[str, Any], data: bytes) -> Any:
    parsers = {
        "pdb": parse_pdb,
        "mmcif": parse_mmcif,
        "sdf_v2000": parse_sdf_v2000,
        "smiles": parse_smiles,
    }
    return parsers[case["format"]](
        data,
        source_id=case["source_id"],
        **case["parser_options"],
    )


def _rdkit_pin_status() -> tuple[bool, str]:
    try:
        _, rd_base = smiles_module._import_rdkit()
        version = rd_base.rdkitVersion
        version_key = smiles_module._version_key(version)
    except Exception:
        return False, "rdkit_unavailable"
    if version_key != (2025, 9, 6):
        return False, "unsupported_rdkit_version"
    if version != "2025.09.6":
        return False, "rdkit_observed_version_mismatch"
    return True, "available"


def _assert_success_case(case: dict[str, Any], data: bytes) -> None:
    expected = case["expected"]
    first = _parse(case, data)
    repeated = _parse(case, data)
    system = first.system
    repeated_system = repeated.system
    manifest = _load_manifest()
    assert system.atom_count == expected["atom_count"]
    assert len(system.bonds) == expected["bond_count"]
    assert system.provenance.source_sha256 == case["source_sha256"]
    assert (
        system.provenance.parser_version
        == (manifest["contracts"]["parser_versions"][case["format"]])
    )
    assert system.provenance.claim_safe is False
    assert first.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert (
        first.coverage.canonical_topology_sha256
        == (expected["canonical_topology_sha256"])
    )
    assert first.coverage.preparation_ready is False
    assert first.coverage.claim_safe is False
    assert first.coverage.to_dict()["supported"] is True
    if hasattr(first.coverage, "supported"):
        assert first.coverage.supported is True
    if case["format"] in {"pdb", "mmcif"}:
        assert first.coverage.syntax_ingest_supported is True
        assert first.coverage.support_scope == STRUCTURE_INGEST_SUPPORT_SCOPE
        assert first.coverage.to_dict()["syntax_ingest_supported"] is True
        assert first.coverage.to_dict()["support_scope"] == (
            STRUCTURE_INGEST_SUPPORT_SCOPE
        )
    if hasattr(first.coverage, "ingest_supported"):
        assert first.coverage.ingest_supported is True
    if hasattr(first.coverage, "chemistry_supported"):
        assert first.coverage.chemistry_supported is False
    if hasattr(first.coverage, "parameterability_assessed"):
        assert first.coverage.parameterability_assessed is False
    if case["format"] == "smiles":
        assert first.coverage.topology_only is True
    assert attached_canonical_topology_sha256_matches(system)
    assert attached_parser_observation_sha256_matches(system)
    assert canonical_topology_sha256(system) == expected["canonical_topology_sha256"]
    assert serialize_canonical_topology(system) == serialize_canonical_topology(
        repeated_system
    )
    serialized = serialize_all_atom_system(system)
    repeated_serialized = serialize_all_atom_system(repeated_system)
    assert serialized == repeated_serialized
    assert (
        canonical_all_atom_snapshot_digest(system)
        == (expected["canonical_snapshot_sha256"])
    )
    assert (
        canonical_all_atom_snapshot_digest(repeated_system)
        == (expected["canonical_snapshot_sha256"])
    )
    restored = deserialize_all_atom_system(serialized)
    assert canonical_all_atom_systems_equal(system, restored)
    assert (
        canonical_all_atom_snapshot_digest(restored)
        == (expected["canonical_snapshot_sha256"])
    )
    assert canonical_topology_sha256(restored) == expected["canonical_topology_sha256"]
    assert attached_canonical_topology_sha256_matches(restored)
    assert attached_parser_observation_sha256_matches(restored)

    chemistry = analyze_canonical_chemistry(system)
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    profile_preparation = analyze_profile_local_preparation_evidence(system)
    contextual_components = analyze_contextual_component_inventory(system)
    restored_chemistry = analyze_canonical_chemistry(restored)
    restored_preparation = analyze_molecular_preparation(restored)
    restored_applicability = analyze_canonical_ingest_applicability(restored)
    restored_profile_preparation = analyze_profile_local_preparation_evidence(restored)
    restored_contextual_components = analyze_contextual_component_inventory(restored)
    isotope_assignments = [
        {"atom_index": atom.index, "mass_number": atom.isotope_mass_number}
        for atom in system.atoms
        if atom.isotope_mass_number is not None
    ]
    atom_stereo_assignments = [
        {"atom_index": atom.index, "stereo": atom.stereo.strip().upper()}
        for atom in system.atoms
        if atom.stereo.strip().upper() not in {"", "NONE", "UNSPECIFIED"}
    ]
    bond_stereo_assignments = [
        {"bond_index": bond.index, "stereo": bond.stereo.strip().upper()}
        for bond in system.bonds
        if bond.stereo.strip().upper() not in {"", "NONE", "UNSPECIFIED"}
    ]
    assert isotope_assignments == expected["isotope_assignments"]
    assert atom_stereo_assignments == expected["atom_stereo_assignments"]
    assert bond_stereo_assignments == expected["bond_stereo_assignments"]
    assert chemistry.isotope_count == len(isotope_assignments)
    assert chemistry.assigned_atom_stereo_count == sum(
        item["stereo"] in {"R", "S"} for item in atom_stereo_assignments
    )
    assert chemistry.unknown_atom_stereo_count == sum(
        item["stereo"] == "UNKNOWN" for item in atom_stereo_assignments
    )
    assert chemistry.assigned_bond_stereo_count == sum(
        item["stereo"] in {"E", "Z"} for item in bond_stereo_assignments
    )
    assert chemistry.matches_system(system)
    assert chemistry.report_sha256 == expected["chemistry_report_sha256"]
    assert preparation.report_sha256 == expected["preparation_report_sha256"]
    assert applicability.matches_system(system)
    assert applicability.report_sha256 == expected["applicability_report_sha256"]
    assert profile_preparation.matches_system(system)
    assert (
        profile_preparation.report_sha256
        == (expected["profile_local_preparation_report_sha256"])
    )
    assert contextual_components.matches_system(system)
    assert (
        contextual_components.report_sha256
        == (expected["contextual_component_inventory_report_sha256"])
    )
    assert contextual_components.preparation_report == preparation
    assert contextual_components.preparation_report_sha256 == (
        preparation.report_sha256
    )
    assert (
        contextual_components.source_authentication_status
        == (manifest["contracts"]["contextual_component_source_authentication_status"])
    )
    assert contextual_components.contextual_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.connection_context_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.water_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.ion_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.metal_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.metal_coordination_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.cofactor_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.modified_residue_identity_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert contextual_components.chemistry_supported is False
    assert contextual_components.preparation_assessed is False
    assert contextual_components.preparation_ready is False
    assert contextual_components.parameterability_assessed is False
    assert contextual_components.parameterizable is False
    assert contextual_components.simulation_ready is False
    assert contextual_components.claim_safe is False
    assert profile_preparation.chemistry_report == chemistry
    assert profile_preparation.applicability_report == applicability
    assert profile_preparation.preparation_report == preparation
    assert (
        profile_preparation.profile_local_evidence_status
        == (expected["profile_local_evidence_status"])
    )
    assert (
        profile_preparation.profile_local_evidence_satisfied
        is (expected["profile_local_evidence_satisfied"])
    )
    for name in (
        "source_hydrogen_inventory_status",
        "profile_hydrogen_valence_status",
        "formal_charge_observation_status",
        "aromaticity_requirement_status",
        "polymer_missing_residue_status",
    ):
        assert getattr(profile_preparation, name) == expected[name]
    assert (
        applicability.canonical_ingest_status == (expected["canonical_ingest_status"])
    )
    assert (
        applicability.canonical_ingest_supported
        is (expected["canonical_ingest_supported"])
    )
    assert (
        list(applicability.failed_constraint_codes)
        == (expected["applicability_failed_constraint_codes"])
    )
    assert (
        applicability.parameterability_status == (expected["parameterability_status"])
    )
    assert restored_chemistry.to_dict() == chemistry.to_dict()
    assert restored_preparation.to_dict() == preparation.to_dict()
    assert restored_applicability.to_dict() == applicability.to_dict()
    assert restored_profile_preparation.to_dict() == (profile_preparation.to_dict())
    assert restored_contextual_components.to_dict() == (contextual_components.to_dict())
    assert chemistry.graph_representable is expected["graph_representable"]
    assert list(chemistry.blockers) == expected["chemistry_blockers"]
    assert list(preparation.blockers) == expected["preparation_blockers"]

    boundary = manifest["claim_boundary"]
    assert chemistry.chemistry_supported is boundary["chemistry_supported"]
    assert chemistry.parameterability_assessed is boundary["parameterability_assessed"]
    assert chemistry.parameterizable is boundary["parameterizable"]
    assert chemistry.claim_safe is boundary["claim_safe"]
    assert preparation.preparation_assessed is boundary["preparation_assessed"]
    assert preparation.preparation_ready is boundary["preparation_ready"]
    assert preparation.claim_safe is boundary["claim_safe"]
    assert (
        applicability.claim_scope
        == manifest["contracts"]["canonical_ingest_claim_scope"]
    )
    assert (
        applicability.source_authentication_status
        == manifest["contracts"]["source_authentication_status"]
    )
    assert applicability.preparation_ready is boundary["preparation_ready"]
    assert (
        applicability.parameterability_assessed is boundary["parameterability_assessed"]
    )
    assert applicability.parameterizable is boundary["parameterizable"]
    assert applicability.simulation_ready is boundary["simulation_ready"]
    assert applicability.claim_safe is boundary["claim_safe"]
    assert (
        profile_preparation.claim_scope
        == manifest["contracts"]["profile_local_preparation_claim_scope"]
    )
    assert (
        profile_preparation.source_authentication_status
        == (manifest["contracts"]["source_authentication_status"])
    )
    assert profile_preparation.whole_molecule_atom_completeness_status == ("unassessed")
    assert profile_preparation.hydrogen_completeness_status == "unassessed"
    assert profile_preparation.formal_charge_assignment_status == "unassessed"
    assert profile_preparation.aromaticity_perception_status == "unassessed"
    assert profile_preparation.preparation_assessed is boundary["preparation_assessed"]
    assert profile_preparation.preparation_ready is boundary["preparation_ready"]
    assert (
        profile_preparation.parameterability_assessed
        is boundary["parameterability_assessed"]
    )
    assert profile_preparation.parameterizable is boundary["parameterizable"]
    assert profile_preparation.simulation_ready is boundary["simulation_ready"]
    assert profile_preparation.claim_safe is boundary["claim_safe"]
    assert boundary["canonical_ingest_profile_support_is_chemistry_support"] is False
    assert boundary["profile_local_evidence_is_global_preparation"] is False
    if case["lane"] == "ingest_only_abstention":
        assert "elements_outside_organic_graph_inventory_profile" in chemistry.blockers


def _assert_failure_case(case: dict[str, Any], data: bytes) -> None:
    expected = case["expected"]
    exception_types = {
        "StructureParseError": StructureParseError,
        "SdfV2000ParseError": SdfV2000ParseError,
        "SmilesParseError": SmilesParseError,
    }
    expected_type = exception_types[expected["exception_type"]]
    with pytest.raises(expected_type) as exc_info:
        _parse(case, data)
    error = exc_info.value
    assert type(error) is expected_type
    assert error.code == expected["error_code"]
    assert getattr(error, "line_number", None) == expected["line_number"]
    assert getattr(error, "position", None) == expected["byte_position"]
    if isinstance(error, StructureParseError):
        assert error.source_format == case["format"]
    assert data.decode("ascii", errors="ignore") not in str(error)


def _load_manifest() -> dict[str, Any]:
    return _validate_manifest(_load_json_manifest(MANIFEST_PATH.read_bytes()))


def test_v2_1_manifest_is_strict_versioned_and_runtime_pinned() -> None:
    manifest = _load_manifest()
    assert manifest["schema_id"] == CORPUS_SCHEMA_ID
    assert manifest["corpus_id"] == CORPUS_ID
    assert manifest["resource_profile"]["profile_id"] == RESOURCE_PROFILE_ID
    assert {case["case_id"]: case["lane"] for case in manifest["cases"]} == (
        _EXPECTED_CASE_LANES
    )


def test_v2_1_selected_profile_rows_and_boundary_failures_are_exact() -> None:
    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["cases"]}
    supported_case_ids = {
        case_id
        for case_id, case in cases.items()
        if case["lane"] == "canonical_ingest_profile_supported"
    }

    assert supported_case_ids == _SELECTED_SUPPORTED_PROFILE_CASE_IDS
    for case_id in sorted(supported_case_ids):
        case = cases[case_id]
        expected = case["expected"]
        assert case["source_id"] == case_id
        assert expected["canonical_ingest_status"] == "supported"
        assert expected["canonical_ingest_supported"] is True
        assert expected["applicability_failed_constraint_codes"] == []
        assert expected["profile_local_evidence_status"] == "satisfied"
        assert expected["profile_local_evidence_satisfied"] is True

    for case_id, boundary in _SELECTED_PROFILE_BOUNDARY_FAILURES.items():
        failed_constraints, valence_status, aromaticity_status = boundary
        case = cases[case_id]
        expected = case["expected"]
        assert case["source_id"] == case_id
        assert case["lane"] == "ingest_success"
        assert expected["canonical_ingest_status"] == "unsupported"
        assert expected["canonical_ingest_supported"] is False
        assert (
            tuple(expected["applicability_failed_constraint_codes"])
            == failed_constraints
        )
        assert expected["profile_local_evidence_status"] == "not_satisfied"
        assert expected["profile_local_evidence_satisfied"] is False
        assert expected["source_hydrogen_inventory_status"] == (
            "complete_relative_to_parsed_source"
        )
        assert expected["profile_hydrogen_valence_status"] == valence_status
        assert expected["aromaticity_requirement_status"] == aromaticity_status

    assert all(value is False for value in manifest["claim_boundary"].values())


@pytest.mark.parametrize("replacement", [100_000.0, True])
def test_v2_1_manifest_resource_limits_reject_numeric_type_substitution(
    replacement: float | bool,
) -> None:
    manifest = _load_manifest()
    forged = deepcopy(manifest)
    forged["resource_profile"]["preparation_audit"]["max_atoms"] = replacement

    with pytest.raises(CorpusManifestError, match="resource profile"):
        _validate_manifest(forged)


def test_v2_1_manifest_claim_boundary_rejects_boolean_type_substitution() -> None:
    manifest = _load_manifest()
    forged = deepcopy(manifest)
    forged["claim_boundary"]["claim_safe"] = 0

    with pytest.raises(CorpusManifestError, match="fail-closed boundary"):
        _validate_manifest(forged)


def test_v2_1_manifest_rejects_duplicate_unknown_and_unsafe_state() -> None:
    with pytest.raises(CorpusManifestError, match="duplicate JSON object key"):
        _load_json_manifest(b'{"schema_id":"one","schema_id":"two"}')
    with pytest.raises(CorpusManifestError, match="nonstandard JSON constant"):
        _load_json_manifest(b'{"schema_id":NaN}')

    manifest = _load_manifest()
    unknown = deepcopy(manifest)
    unknown["unexpected"] = False
    with pytest.raises(CorpusManifestError, match=r"unknown=\['unexpected'\]"):
        _validate_manifest(unknown)

    unsafe = deepcopy(manifest)
    unsafe["cases"][0]["source"]["path"] = "../outside.pdb"
    with pytest.raises(CorpusManifestError, match="tests/fixtures POSIX path"):
        _validate_manifest(unsafe)

    replaced_case = deepcopy(manifest)
    replaced_case["cases"][0]["case_id"] = "replacement_pdb_case"
    with pytest.raises(
        CorpusManifestError,
        match="schema-1.4 case and lane inventory changed",
    ):
        _validate_manifest(replaced_case)

    moved_lanes = deepcopy(manifest)
    cases_by_id = {case["case_id"]: case for case in moved_lanes["cases"]}
    cases_by_id["sdf_v2000_isobutane_branched_explicit_h"]["lane"] = "ingest_success"
    cases_by_id["sdf_v2000_cyclobutane_explicit_h"]["lane"] = (
        "canonical_ingest_profile_supported"
    )
    with pytest.raises(
        CorpusManifestError,
        match="lane disagrees with canonical ingest support",
    ):
        _validate_manifest(moved_lanes)

    replaced_record = deepcopy(manifest)
    records_by_id = {case["case_id"]: case for case in replaced_record["cases"]}
    replacement = deepcopy(records_by_id["sdf_v3000_rejected"])
    replacement["case_id"] = "sdf_atom_parity_rejected"
    replacement["source_id"] = "sdf_atom_parity_rejected"
    target_index = next(
        index
        for index, case in enumerate(replaced_record["cases"])
        if case["case_id"] == "sdf_atom_parity_rejected"
    )
    replaced_record["cases"][target_index] = replacement
    with pytest.raises(CorpusManifestError, match="schema-1.4 case records changed"):
        _validate_manifest(replaced_record)


def test_v2_1_manifest_source_bytes_are_immutable_and_digest_bound() -> None:
    manifest = _load_manifest()
    for case in manifest["cases"]:
        data = _read_source(case)
        assert hashlib.sha256(data).hexdigest() == case["source_sha256"]

    tampered = deepcopy(manifest["cases"][0])
    tampered["source_sha256"] = "0" * 64
    with pytest.raises(CorpusManifestError, match="source digest mismatch"):
        _read_source(tampered)


def test_v2_1_stereo_and_isotope_identity_relations_are_pinned() -> None:
    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["cases"]}

    unlabeled = cases["sdf_v2000_methane_explicit_h"]["expected"]
    carbon_13 = cases["sdf_v2000_methane_c13_explicit_h"]["expected"]
    assert carbon_13["isotope_assignments"] == [{"atom_index": 0, "mass_number": 13}]
    assert (
        carbon_13["canonical_topology_sha256"]
        != (unlabeled["canonical_topology_sha256"])
    )
    assert (
        carbon_13["canonical_snapshot_sha256"]
        != (unlabeled["canonical_snapshot_sha256"])
    )

    chiral = [
        cases[case_id]["expected"] for case_id in ("smiles_chiral_r", "smiles_chiral_s")
    ]
    assert {entry["atom_stereo_assignments"][0]["stereo"] for entry in chiral} == {
        "R",
        "S",
    }
    assert len({entry["canonical_topology_sha256"] for entry in chiral}) == 2
    assert len({entry["canonical_snapshot_sha256"] for entry in chiral}) == 2

    alkene = [
        cases[case_id]["expected"] for case_id in ("smiles_alkene_e", "smiles_alkene_z")
    ]
    assert {entry["bond_stereo_assignments"][0]["stereo"] for entry in alkene} == {
        "E",
        "Z",
    }
    assert len({entry["canonical_topology_sha256"] for entry in alkene}) == 2
    assert len({entry["canonical_snapshot_sha256"] for entry in alkene}) == 2

    for expected in (*chiral, *alkene, carbon_13):
        assert expected["canonical_ingest_supported"] is False
        assert expected["profile_local_evidence_satisfied"] is False


def test_v2_1_isotope_pair_differs_only_by_the_pinned_mass_number() -> None:
    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["cases"]}
    unlabeled_case = cases["sdf_v2000_methane_explicit_h"]
    carbon_13_case = cases["sdf_v2000_methane_c13_explicit_h"]
    unlabeled_document = canonical_topology_document(
        _parse(unlabeled_case, _read_source(unlabeled_case)).system
    )
    carbon_13_document = canonical_topology_document(
        _parse(carbon_13_case, _read_source(carbon_13_case)).system
    )

    assert unlabeled_document["atoms"][0]["isotope_mass_number"] is None
    assert carbon_13_document["atoms"][0]["isotope_mass_number"] == 13
    carbon_13_document["atoms"][0]["isotope_mass_number"] = None
    assert carbon_13_document == unlabeled_document


def test_v2_1_stereo_pairs_differ_only_by_the_pinned_descriptors() -> None:
    rdkit_available, rdkit_status = _rdkit_pin_status()
    if not rdkit_available:
        pytest.skip(f"requires the pinned RDKit environment ({rdkit_status})")

    manifest = _load_manifest()
    cases = {case["case_id"]: case for case in manifest["cases"]}
    expected_assignments = {
        "smiles_chiral_s": ("atoms", 0, "S"),
        "smiles_chiral_r": ("atoms", 0, "R"),
        "smiles_alkene_e": ("bonds", 1, "E"),
        "smiles_alkene_z": ("bonds", 1, "Z"),
    }
    documents: dict[str, dict[str, Any]] = {}
    for case_id, (collection, index, label) in expected_assignments.items():
        case = cases[case_id]
        documents[case_id] = canonical_topology_document(
            _parse(case, _read_source(case)).system
        )
        assert documents[case_id][collection][index]["stereo"] == label

    chiral_s = deepcopy(documents["smiles_chiral_s"])
    chiral_r = deepcopy(documents["smiles_chiral_r"])
    chiral_s["atoms"][0]["stereo"] = ""
    chiral_r["atoms"][0]["stereo"] = ""
    assert chiral_s == chiral_r

    alkene_e = deepcopy(documents["smiles_alkene_e"])
    alkene_z = deepcopy(documents["smiles_alkene_z"])
    alkene_e["bonds"][1]["stereo"] = ""
    alkene_z["bonds"][1]["stereo"] = ""
    assert alkene_e == alkene_z


def test_v2_1_context_inventory_preserves_markers_without_assigning_roles() -> None:
    manifest = _load_manifest()
    case = next(
        case
        for case in manifest["cases"]
        if case["case_id"] == "mmcif_context_inventory"
    )
    system = _parse(case, _read_source(case)).system
    report = analyze_contextual_component_inventory(system)
    components = {component.residue_name: component for component in report.components}

    assert list(components) == ["MSE", "HOH", "NA", "ZN", "HEM"]
    assert len(system.bonds) == 0
    assert components["HOH"].canonical_water_entity_marker_status == (
        CANONICAL_MARKER_OBSERVED_STATUS
    )
    assert components["HOH"].water_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    for name, charge in (("NA", 1), ("ZN", 2)):
        component = components[name]
        assert component.canonical_net_formal_charge == charge
        assert component.canonical_known_charged_monatomic_marker_status == (
            CANONICAL_MARKER_OBSERVED_STATUS
        )
        assert component.ion_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert component.metal_role_status == (CONTEXTUAL_COMPONENT_UNASSESSED_STATUS)
        assert component.metal_coordination_status == (
            CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
        )
        assert component.oxidation_state_status == (
            CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
        )
    assert components["HEM"].cofactor_role_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert components["MSE"].canonical_polymer_hetero_marker_status == (
        CANONICAL_MARKER_OBSERVED_STATUS
    )
    assert components["MSE"].modified_residue_identity_status == (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )
    assert (
        report.report_sha256
        == (case["expected"]["contextual_component_inventory_report_sha256"])
    )
    assert report.chemistry_supported is False
    assert report.preparation_ready is False
    assert report.parameterability_assessed is False
    assert report.claim_safe is False


def test_v2_1_supported_ingest_and_intentional_failure_corpus() -> None:
    manifest = _load_manifest()
    rdkit_available, rdkit_status = _rdkit_pin_status()
    if os.environ.get("BETELGEUZE_REQUIRE_PINNED_RDKIT") == "1" and not rdkit_available:
        pytest.fail(
            "CI requires the pinned RDKit runtime, but the product gate "
            f"reported {rdkit_status}"
        )
    outcomes: dict[str, tuple[str, str]] = {}
    for case in manifest["cases"]:
        data = _read_source(case)
        if case["environment_requirements"] and not rdkit_available:
            outcomes[case["case_id"]] = ("environment_blocked", rdkit_status)
            continue
        if case["lane"] == "parse_failure":
            _assert_failure_case(case, data)
        else:
            _assert_success_case(case, data)
        outcomes[case["case_id"]] = ("pass", "verified")

    blocked = {
        case_id: detail
        for case_id, detail in outcomes.items()
        if detail[0] == "environment_blocked"
    }
    if rdkit_available:
        assert blocked == {}
        assert all(status == "pass" for status, _ in outcomes.values())
    else:
        expected_blocked = {
            case["case_id"]: ("environment_blocked", rdkit_status)
            for case in manifest["cases"]
            if case["environment_requirements"]
        }
        assert blocked == expected_blocked
        assert all(
            status == "pass"
            for case_id, (status, _) in outcomes.items()
            if case_id not in blocked
        )
        pytest.xfail(
            "environment_blocked: the complete corpus requires the pinned "
            f"RDKit 2025.9.6 environment ({rdkit_status})"
        )
