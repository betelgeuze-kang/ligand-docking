"""Validate the blocked BRD4 source snapshot without network or protected data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "source_manifest.v1.json"
SCHEMA = "brd4_3mxf_source_preflight_v1"
STATUS = "SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED"
SOURCE_FILES = {
    "pdb_3mxf": (
        "official_sources/coordinates-3mxf.cif",
        "https://files.rcsb.org/download/3MXF.cif",
        287430,
        "fb123201edb59709d14b64c5cb4296a90b6d35c45505baba48600d04e4cdd401",
    ),
    "ccd_jq1": (
        "official_sources/chemcomp-jq1.cif",
        "https://files.rcsb.org/ligands/download/JQ1.cif",
        10889,
        "9652a88ed9dd1f78e4dbfd2fcd127e40a9643fc5b111d84d8e615adc399213e5",
    ),
    "pdb_3mxf_validation": (
        "official_sources/3mxf_full_validation.pdf",
        "https://files.rcsb.org/validation/view/3mxf_full_validation.pdf",
        908684,
        "0dc0ed30c51996ff5712996b6a43a57049be3736ab601cf58b417975cdbb8ac8",
    ),
}
GEOMETRY_RECEIPT = (
    "source_geometry.v1.json",
    67787,
    "3ee4b1330a40569a3905eefd6f0096ecda609dbb489f935b486a4e5c596cf84c",
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate_json_key:{key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite_json_constant:{value}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(manifest: dict[str, object]) -> int:
    require(
        manifest["schema_version"] == SCHEMA and manifest["status"] == STATUS,
        "unexpected_schema_or_status",
    )
    sources = manifest["source_refs"]
    require(
        set(sources)
        == {
            "pdb_3mxf",
            "pdb_3mxf_validation",
            "ccd_jq1",
            "filippakopoulos_2010",
            "tanaka_2016",
            "tanaka_2016_supplement",
            "pubchem_s_jq1",
            "pubchem_r_jq1",
            "pdb_usage_policy",
        },
        "unexpected_source_refs",
    )
    require(
        all(ref["url"].startswith("https://") for ref in sources.values()),
        "non_https_source",
    )
    require(
        sources["pdb_3mxf"]["download_url"]
        == "https://files.rcsb.org/download/3MXF.cif",
        "structure_source_changed",
    )
    require(
        sources["tanaka_2016"]["doi"] == "10.1038/nchembio.2209"
        and sources["tanaka_2016"]["pmid"] == "27775715"
        and sources["tanaka_2016_supplement"]["direct_file_access_verified"] is False,
        "assay_source_changed_or_access_overclaimed",
    )

    structure = manifest["structure_observation"]
    require(
        structure["pdb_id"] == "3MXF"
        and structure["protein_label_chain"] == "A"
        and structure["modelled_residue_range"] == "42-168"
        and structure["deposited_ligand_ccd"] == "JQ1"
        and structure["deposited_ligand_stereochemistry"] == "6S",
        "structure_identity_changed",
    )
    assay = manifest["experimental_observation"]
    require(
        assay["endpoint"] == "IC50"
        and assay["endpoint_subtype"]
        == "BRD4_BD1_AlphaScreen_competitive_inhibition_IC50"
        and assay["assay_protein_concentration_nM"] == 20
        and "44-168" in assay["assay_construct"],
        "assay_context_changed",
    )
    require(
        assay["measurements"]
        == [
            {
                "compound": "(S)-(+)-JQ1",
                "pubchem_cid": 46907787,
                "operator": "=",
                "value_nM": 21,
                "censored": False,
                "reported_interpretation": "active",
            },
            {
                "compound": "(R)-(-)-JQ1",
                "pubchem_cid": 49871818,
                "operator": ">",
                "value_nM": 5000,
                "censored": True,
                "reported_interpretation": "inactive_at_tested_concentrations",
            },
        ],
        "measurements_or_censoring_changed",
    )

    boundaries = manifest["comparison_boundaries"]
    require(
        boundaries
        == {
            "common_core_residues_44_168_source_consistent": True,
            "exact_assay_and_crystal_construct_equivalence_verified": False,
            "assay_his_tag_in_crystal_resolved": False,
            "extra_crystal_residues_42_43_treatment_resolved": False,
            "pdb_cation_vs_neutral_pubchem_assay_microstate_resolved": False,
            "r_enantiomer_experimental_bound_pose_available": False,
            "r_enantiomer_source_bound_stereochemical_identity_recorded": True,
            "ligand_pair_prepared_in_one_reviewed_microstate": False,
            "same_assay_ic50_contrast_observed": True,
            "reported_greater_than_5_uM_treated_as_exact_value": False,
            "ic50_converted_to_ki_kd_or_binding_free_energy": False,
        },
        "comparison_boundary_changed_or_overclaimed",
    )
    require(
        manifest["bounded_metadata_screen"]
        == {
            "status": "BLOCKED_IDENTITY_REVIEW_REQUIRED",
            "scope": "Two public PubChem InChIKey identities and the Tanaka DOI against frozen identity metadata; not a complete connected source-family review",
            "pubchem_identity_api_sha256": "52f8a2d8842bff5304c5c8da533fde93d49ff4a04c85e2c96d9052bb19923a63",
            "context_sha256": "f34b50ecb797e2800716728992730e10f19eb48bec7d15d24214c676a1df47d1",
            "candidates_sha256": "f1eef8c71314642089ba45bbea09f71a5fc02bde9d7cc93d7dcfe8819232f667",
            "preflight_sha256": "e7fd2d4f983a29988c6c31d3f8094e421e5fe4ce69fd80ee180dbc235d6942bc",
            "diagnostic_sha256": "91fcacd26726e26d39f6ebfd9aa6a0045b3d88b338bdab3669e704922c36360e",
            "candidate_count": 2,
            "blocked_identity_count": 2,
            "component_node_count": 148913,
            "reserved_nodes_count": 1336,
            "unknown_policy_nodes_count": 41,
            "direct_reserved_or_unknown_key_overlaps": 0,
            "shortest_indirect_path_edge_types": [
                "inchikey_connectivity",
                "document",
                "scaffold",
            ],
            "diagnostic_complete_for_supplied_context": True,
            "complete_family_clearance": False,
            "chemical_equivalence_or_leakage_proven": False,
            "protected_outcome_values_accessed": False,
            "source_roles_granted": False,
        },
        "bounded_metadata_screen_changed_or_overclaimed",
    )
    require(
        manifest["eligibility"]
        == {
            "prepared_input_executable": False,
            "numeric_comparison_executable": False,
            "experimental_comparison_eligible": False,
            "installed_native_v4_receptor_radioligand_binding_Ki_applicable": False,
            "training_admitted": False,
            "product_ranking_enabled": False,
            "customer_execution": False,
            "scientifically_validated": False,
        },
        "eligibility_must_remain_false",
    )
    roles = manifest["protection_and_roles"]
    require(
        roles
        == {
            "protected_outcomes_accessed": False,
            "identity_component_and_reservation_screen_completed": False,
            "source_component_role": None,
            "fit_role": None,
            "calibration_role": None,
            "evaluation_role": None,
            "source_rights_use_specific_review_completed": False,
        },
        "roles_or_rights_overclaimed",
    )
    actions = manifest["performed_actions"]
    require(
        actions
        == {
            "public_source_metadata_reviewed": True,
            "source_files_downloaded": True,
            "source_geometry_observed": True,
            "receptor_prepared": False,
            "s_ligand_prepared": False,
            "r_ligand_prepared": False,
            "physical_evaluations": 0,
            "fit_or_evaluation_roles_assigned": False,
            "protected_evaluation_access": False,
        },
        "non_static_action_claimed",
    )
    geometry_path, geometry_size, geometry_digest = GEOMETRY_RECEIPT
    require(
        manifest["source_geometry_receipt"]
        == {
            "relative_path": geometry_path,
            "size_bytes": geometry_size,
            "sha256": geometry_digest,
            "evidence_class": "unprepared_archive_coordinate_and_ccd_observation",
            "prepared_state_or_assay_microstate_proven": False,
        },
        "source_geometry_receipt_changed_or_overclaimed",
    )
    actual_geometry_path = ROOT / geometry_path
    require(
        actual_geometry_path.is_file()
        and not actual_geometry_path.is_symlink()
        and actual_geometry_path.resolve().is_relative_to(ROOT.resolve()),
        "source_geometry_receipt_missing_or_outside_packet",
    )
    require(
        actual_geometry_path.stat().st_size == geometry_size
        and sha256(actual_geometry_path) == geometry_digest,
        "source_geometry_receipt_bytes_changed",
    )
    decisions = manifest["unresolved_decisions"]
    require(
        len(decisions) == 7
        and {item["id"] for item in decisions}
        == {
            "construct_and_residue_mapping",
            "ligand_stereo_and_microstate",
            "r_ligand_conformer_and_prepared_files",
            "crystal_components_and_geometry",
            "assay_censoring_and_method",
            "source_rights_and_independent_roles",
            "endpoint_lane_and_comparison_protocol",
        }
        and all(item["status"] == "unresolved" for item in decisions),
        "decision_set_or_status_changed",
    )

    receipts = manifest["source_file_receipts"]
    structural_sources = set(SOURCE_FILES)
    require(
        type(receipts) is list
        and len(receipts) == 3
        and actions["source_files_downloaded"] is True
        and {item["source_ref"] for item in receipts} == structural_sources,
        "structural_source_receipts_incomplete_or_unexpected",
    )
    seen = set()
    source_root = (ROOT / "official_sources").resolve()
    for receipt in receipts:
        require(receipt["source_ref"] in SOURCE_FILES, "unexpected_source_ref")
        expected_path, expected_url, expected_size, expected_digest = SOURCE_FILES[
            receipt["source_ref"]
        ]
        require(
            set(receipt)
            == {"source_ref", "source_url", "relative_path", "size_bytes", "sha256"}
            and receipt["source_ref"] in structural_sources
            and receipt["source_url"] == expected_url
            and sources[receipt["source_ref"]]["download_url"] == expected_url
            and receipt["relative_path"] == expected_path
            and receipt["size_bytes"] == expected_size
            and receipt["sha256"] == expected_digest,
            "invalid_source_receipt_or_url",
        )
        relative = PurePosixPath(receipt["relative_path"])
        require(
            not relative.is_absolute()
            and relative.parts
            and relative.parts[0] == "official_sources"
            and ".." not in relative.parts
            and str(relative) == receipt["relative_path"]
            and receipt["relative_path"] not in seen,
            "invalid_source_path",
        )
        seen.add(receipt["relative_path"])
        require(
            type(receipt["size_bytes"]) is int and receipt["size_bytes"] > 0,
            "invalid_source_size",
        )
        require(
            re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) is not None,
            "invalid_source_hash",
        )
        untrusted_path = ROOT / receipt["relative_path"]
        path = untrusted_path.resolve()
        require(
            not untrusted_path.is_symlink()
            and path.is_relative_to(source_root)
            and path.is_file(),
            "source_file_missing_or_outside_packet",
        )
        require(path.stat().st_size == receipt["size_bytes"], "source_size_mismatch")
        require(sha256(path) == receipt["sha256"], "source_hash_mismatch")
    return len(receipts)


def main() -> None:
    manifest = json.loads(
        MANIFEST.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    count = validate(manifest)
    print(
        json.dumps(
            {
                "status": "PASS_STATIC_SOURCE_CANDIDATE_BLOCKED",
                "source_files_verified": count,
                "scientific_admission": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
