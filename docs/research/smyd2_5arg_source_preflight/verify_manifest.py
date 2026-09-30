"""Verify the SMYD2 source candidate packet offline without protected data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
STATUS = "SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED"
SOURCE_FILES = {
    "pdb_5arg": (
        "official_sources/coordinates-5arg.cif",
        "https://files.rcsb.org/download/5ARG.cif",
        744344,
        "ba33c3dc604445e1d49cf549b9738abcfd7f5727ef900e4f3d1f946a8d26ff74",
    ),
    "ccd_h41": (
        "official_sources/chemcomp-h41.cif",
        "https://files.rcsb.org/ligands/download/H41.cif",
        10621,
        "41f1ec80e2fd231ad561c370ec01cf7290bea32f1cb69cdca15b7a185ab9e651",
    ),
}
ALLOWED_FILES = {
    ".gitattributes",
    "README.md",
    "source_manifest.v1.json",
    "source_geometry.v1.json",
    "test_source_geometry.py",
    "verify_manifest.py",
    "verify_source_geometry.py",
    *(item[0] for item in SOURCE_FILES.values()),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate_json_key:{key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite_json_constant:{value}")


def verify() -> dict[str, object]:
    manifest = json.loads(
        (ROOT / "source_manifest.v1.json").read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    require(
        manifest["schema_version"] == "smyd2_5arg_source_preflight_v1"
        and manifest["recorded_against_repository_head"]
        == "a306633d8f5cbbcdd3bfb7395bbf8a022e27dae6"
        and manifest["status"] == STATUS
        and manifest["qualification"] == "NOT_QUALIFIED",
        "candidate_status_or_base_changed",
    )

    files = {str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file()}
    require(files == ALLOWED_FILES, "unexpected_or_missing_packet_file")
    require(
        (ROOT / ".gitattributes").read_text(encoding="utf-8")
        == "official_sources/*.cif binary\n",
        "archive_binary_attribute_missing",
    )

    source_refs = manifest["source_refs"]
    require(
        source_refs["pdb_archive_policy"]["license"] == "CC0-1.0"
        and source_refs["primary_article"]["doi"] == "10.1021/acs.jmedchem.5b01890",
        "source_or_archive_policy_changed",
    )
    supplement = source_refs["acs_supplement_metadata"]
    require(
        set(supplement) == {"csv", "pdf"}
        and supplement["csv"]
        == {
            "api_url": "https://api.figshare.com/v2/articles/3208402",
            "public_url": "https://acs.figshare.com/articles/dataset/Discovery_and_Characterization_of_a_Highly_Potent_and_Selective_Aminopyrazoline_Based_in_Vivo_Probe_BAY_598_for_the_Protein_Lysine_Methyltransferase_SMYD2/3208402",
            "doi": "10.1021/acs.jmedchem.5b01890.s002",
            "filename": "jm5b01890_si_002.csv",
            "file_id": 5037607,
            "size_bytes": 2520,
            "sha256": "90d3af3c34c5575c07c162ed34735db6f394be7625ebb391b7fe6359a780496e",
            "license": "CC BY-NC 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
        }
        and supplement["pdf"]
        == {
            "api_url": "https://api.figshare.com/v2/articles/3208399",
            "public_url": "https://acs.figshare.com/articles/journal_contribution/Discovery_and_Characterization_of_a_Highly_Potent_and_Selective_Aminopyrazoline_Based_in_Vivo_Probe_BAY_598_for_the_Protein_Lysine_Methyltransferase_SMYD2/3208399",
            "doi": "10.1021/acs.jmedchem.5b01890.s001",
            "filename": "jm5b01890_si_001.pdf",
            "file_id": 5037604,
            "size_bytes": 1344845,
            "sha256": "958bfab7555582cc2bcce7883a07cd0556be0fb8d2c571448e5c5610db66981d",
            "license": "CC BY-NC 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
        },
        "supplement_license_metadata_changed",
    )
    receipts = manifest["source_file_receipts"]
    require(
        len(receipts) == 2
        and {item["source_ref"] for item in receipts} == set(SOURCE_FILES),
        "unexpected_archive_receipts",
    )
    for receipt in receipts:
        relative, url, size, digest = SOURCE_FILES[receipt["source_ref"]]
        pure = PurePosixPath(receipt["relative_path"])
        require(
            not pure.is_absolute()
            and ".." not in pure.parts
            and receipt["relative_path"] == relative,
            "unsafe_archive_path",
        )
        path = ROOT / relative
        require(
            not path.is_symlink()
            and path.is_file()
            and path.resolve().is_relative_to(ROOT),
            "archive_missing_or_outside_packet",
        )
        require(
            receipt["source_url"] == url
            and source_refs[receipt["source_ref"]]["download_url"] == url
            and receipt["size_bytes"] == size
            and receipt["sha256"] == digest
            and receipt["license"] == "CC0-1.0",
            "archive_receipt_changed",
        )
        require(
            path.stat().st_size == size
            and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "archive_bytes_changed",
        )

    geometry = manifest["source_geometry_receipt"]
    require(
        geometry
        == {
            "relative_path": "source_geometry.v1.json",
            "sha256": "6742487cd3146331346b3ada339652017a650586017810ca17d4c6a0df089e41",
            "status": "SOURCE_GEOMETRY_OBSERVED_PREPARATION_AND_ADMISSION_BLOCKED",
            "prepared_state_created": False,
            "source_atom_coordinates_modified": False,
        }
        and not (ROOT / geometry["relative_path"]).is_symlink()
        and (ROOT / geometry["relative_path"]).resolve().is_relative_to(ROOT)
        and hashlib.sha256((ROOT / geometry["relative_path"]).read_bytes()).hexdigest()
        == geometry["sha256"],
        "source_geometry_receipt_changed",
    )

    external = manifest["external_source_audit"]
    require(
        external["receipt_sha256"]
        == "bdaa1a3f77c5a0a7a8dcbd2ad9c102a84633ced3bb67b84bedaa851c713524e5"
        and all(
            external[key]["bytes_in_packet"] is False
            for key in ("article_xml", "supplementary_zip", "csv_member")
        )
        and external["csv_member"]["admitted_as_labels"] is False
        and external["publisher_pdf_or_images_in_packet"] is False,
        "publisher_bytes_or_labels_imported",
    )

    chemical = manifest["chemical_identity_observation"]
    require(
        chemical["h41_ccd_inchikey"]
        == chemical["csv_s4_calculated_inchikey"]
        == "OTTJIRVZJJGFTK-SFHVURJKSA-N"
        and chemical["stereospecific_standard_inchikey_match"] is True
        and chemical["assay_crystal_microstate_equivalence_verified"] is False,
        "identity_observation_changed_or_overclaimed",
    )
    observations = manifest["experimental_observation"]
    require(
        observations["endpoint_subtype"]
        == "SMYD2_p53_peptide_methylation_scintillation_proximity_assay_IC50"
        and observations["same_assay_pair"]
        == [
            {
                "compound": "(S)-4",
                "source_locus": "Table 4",
                "operator": "=",
                "value_uM": 0.027,
                "censored": False,
            },
            {
                "compound": "25",
                "source_locus": "Table 3",
                "operator": ">",
                "value_uM": 20,
                "censored": True,
            },
        ]
        and observations["matched_experimental_batch_verified"] is False
        and observations["ic50_converted_to_ki_kd_or_binding_free_energy"] is False
        and observations["physical_comparison_performed"] is False,
        "assay_pair_or_censoring_changed",
    )

    family = manifest["source_family_audit"]
    require(
        family["measured_id_row_count"] == 29
        and family["csv_ids_match_tables_1_to_4_measured_ids"] is True
        and len(family["csv_discrepancies"]) == 4
        and all(
            family[key] is False
            for key in (
                "connected_family_complete",
                "synthetic_intermediates_complete",
                "full_family_identity_graph_screened",
                "csv_admitted_as_labels",
                "discrepancies_adjudicated",
            )
        ),
        "family_or_csv_limit_overclaimed",
    )
    structure = manifest["structure_observation"]
    for key, value in {
        "pdb_id": "5ARG",
        "resolution_angstrom": 1.99,
        "deposited_protein_residues": 433,
        "modeled_protein_residues": 426,
        "atom_site_rows": 3680,
        "h41_heavy_atom_rows": 35,
        "sam_atom_rows": 27,
        "water_atom_rows": 137,
        "zinc_atom_rows": 3,
        "protein_ab_altloc_atom_rows": 88,
        "deposited_hydrogen_atom_rows": 0,
        "preparation_state": "UNPREPARED_ARCHIVE_BYTES",
        "assay_crystal_construct_equivalence_verified": False,
    }.items():
        require(structure[key] == value, f"structure_observation_changed:{key}")

    rights = manifest["rights"]
    require(
        rights
        == {
            "pdb_archive_license": "CC0-1.0",
            "article_xml_reports_cc_by": True,
            "acs_supplement_csv_pdf_license_identified": True,
            "acs_supplement_csv_pdf_license": "CC BY-NC 4.0",
            "publisher_supplement_commercial_reuse_verified": False,
            "intended_use_rights_review_complete": False,
            "commercial_supplement_reuse_authorized": False,
            "free_access_treated_as_reuse_permission": False,
        },
        "rights_overclaimed",
    )
    require(
        manifest["graph_screen"]
        == {
            "status": "BLOCKED_IDENTITY_REVIEW_REQUIRED",
            "receipt_sha256": "2d5cc7c0251377b8c0bbbb07357dc14224a3f7894c45da5eee11f54238ffa2d8",
            "executed_repository_head": "a306633d8f5cbbcdd3bfb7395bbf8a022e27dae6",
            "candidate_count": 29,
            "blocked_identity_count": 29,
            "component_node_count": 148940,
            "reserved_nodes_count": 1336,
            "unknown_policy_nodes_count": 41,
            "direct_reserved_or_unknown_key_overlaps": 0,
            "shortest_indirect_path_edge_types": [
                "connectivity",
                "document",
                "scaffold",
            ],
            "chemical_equivalence_or_leakage_proven": False,
            "global_family_completeness": False,
            "complete_family_clearance": False,
            "protected_identity_metadata_read_by_separate_screen": True,
            "protected_outcome_values_read_by_separate_screen": False,
            "protected_context_bytes_imported_into_packet": False,
        },
        "graph_screen_overclaimed",
    )
    require(
        manifest["protection_and_roles"]
        == {
            "protected_outcomes_accessed": False,
            "protected_identity_metadata_read_by_separate_screen": True,
            "protected_context_bytes_imported_into_packet": False,
            "source_component_role": None,
            "fit_role": None,
            "calibration_role": None,
            "evaluation_role": None,
        },
        "protected_access_or_role_assignment",
    )
    require(
        all(value is False for value in manifest["eligibility"].values())
        and len(manifest["eligibility"]) == 8,
        "admission_or_execution_enabled",
    )
    require(
        manifest["performed_actions"]
        == {
            "public_source_audit": True,
            "archive_bytes_recorded": True,
            "source_geometry_observation": True,
            "publisher_files_imported_into_packet": False,
            "receptor_prepared": False,
            "ligands_prepared": False,
            "roles_assigned": False,
            "admitted_rows": 0,
            "prepared_pairs_created": 0,
            "physical_evaluations": 0,
        },
        "prepared_or_evaluated_claim",
    )
    require(
        len(manifest["unresolved_decisions"]) == 8,
        "unresolved_decisions_dropped",
    )
    return {
        "status": "PASS_STATIC_SOURCE_CANDIDATE_BLOCKED",
        "archive_files_verified": len(receipts),
        "graph_screen": "BLOCKED_IDENTITY_REVIEW_REQUIRED",
        "source_roles": 0,
        "prepared_pairs": 0,
        "physical_evaluations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
