"""Check the PRMT3 source candidate snapshot without network or protected data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "source_manifest.v1.json"
STATUS = "SOURCE_CANDIDATE_ONLY_PREPARATION_AND_ADMISSION_BLOCKED"
SOURCE_FILES = {
    "pdb_4ryl": (
        "official_sources/coordinates-4ryl.cif",
        "https://files.rcsb.org/download/4RYL.cif",
        320006,
        "327c5d3a8784516648f6094f041b791ab7d42db64557f19d2faebc29e33ac0df",
    ),
    "ccd_3zg": (
        "official_sources/chemcomp-3zg.cif",
        "https://files.rcsb.org/ligands/download/3ZG.cif",
        8516,
        "6fc81e374e082f4bcf2c39bd7aa9bf1d3f7a4a80e50fec210fb3587baf6dc618",
    ),
}
DECISIONS = {
    "complete_source_family", "document_alias_patent_and_reservation_coverage",
    "source_use_specific_rights", "assay_and_structure_construct_linkage",
    "assembly_and_protein_preparation", "waters_ions_and_hydrogens",
    "paired_ligand_microstates_and_parameters", "frozen_spa_protocol_and_comparison",
    "role_and_execution_authority",
}


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


def validate(manifest: dict[str, object]) -> int:
    require(manifest["schema_version"] == "prmt3_4ryl_source_preflight_v1"
            and manifest["status"] == STATUS
            and manifest["qualification"] == "NOT_QUALIFIED",
            "schema_status_or_qualification_changed")
    require(re.fullmatch(r"[0-9a-f]{40}", manifest["recorded_against_repository_head"])
            is not None, "invalid_recorded_repository_head")
    sources = manifest["source_refs"]
    require(all(item["url"].startswith("https://") for item in sources.values()),
            "non_https_source")
    require(sources["kaniskan_2015"]["doi"] == "10.1002/anie.201412154"
            and sources["kaniskan_2015"]["pmid"] == "25728001"
            and sources["kaniskan_2015"]["full_text_file_downloaded"] is False,
            "primary_source_changed_or_overclaimed")
    require(sources["pdb_archive_policy"]["license"] == "CC0-1.0"
            and sources["pdb_archive_policy"]["access"] == "direct_official_page_verified",
            "archive_rights_basis_missing")
    for key in ("later_sar_csv_metadata", "later_sar_pdf_metadata"):
        require(sources[key]["license"] == "CC-BY-NC-4.0"
                and sources[key]["bytes_included_in_packet"] is False,
                "publisher_supplement_rights_or_import_changed")

    receipts = manifest["source_file_receipts"]
    require(len(receipts) == 2
            and {item["source_ref"] for item in receipts} == set(SOURCE_FILES),
            "unexpected_source_receipts")
    actual_files = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "official_sources").rglob("*") if path.is_file()
    }
    require(actual_files == {item[0] for item in SOURCE_FILES.values()},
            "unlisted_source_file")
    for receipt in receipts:
        relative, url, size, digest = SOURCE_FILES[receipt["source_ref"]]
        pure = PurePosixPath(receipt["relative_path"])
        require(not pure.is_absolute() and ".." not in pure.parts
                and receipt["relative_path"] == relative,
                "invalid_source_path")
        path = ROOT / relative
        require(not path.is_symlink() and path.is_file()
                and path.resolve().is_relative_to(ROOT.resolve()),
                "source_outside_packet_or_missing")
        require(receipt["source_url"] == url
                and sources[receipt["source_ref"]]["download_url"] == url
                and receipt["size_bytes"] == size and receipt["sha256"] == digest
                and receipt["license"] == "CC0-1.0"
                and receipt["official_url_bytes_match"] is True,
                "source_receipt_changed")
        content = path.read_bytes()
        require(len(content) == size and hashlib.sha256(content).hexdigest() == digest,
                "source_bytes_changed")

    structure = manifest["structure_observation"]
    for key, expected in {
        "pdb_id": "4RYL", "primary_doi": "10.1002/anie.201412154",
        "resolution_angstrom": 2.1, "deposited_ligand_ccd": "3ZG",
        "deposited_polymer_residue_count": 340, "observed_polymer_residue_count": 300,
        "atom_site_rows": 2582, "deposited_hydrogen_atom_rows": 0,
        "water_oxygen_atom_rows": 172, "unknown_atom_or_ion_rows": 2,
        "deposited_ligand_heavy_atom_rows": 22, "ccd_heavy_atom_count": 22,
        "ccd_formal_charge": 0, "preparation_state": "UNPREPARED_ARCHIVE_BYTES",
        "ligand_inchikey": "DMIDPTCQPIJYFE-UHFFFAOYSA-N",
        "uniprot_id": "O60678", "deposited_uniprot_accession": "Q8WUV3",
        "deposited_reference_alignment_range": "228-548",
    }.items():
        require(structure[key] == expected, f"structure_observation_changed:{key}")
    require(structure["assay_crystal_reference_numbering_equivalence_verified"] is False,
            "construct_mapping_overclaimed")
    mapping = structure["source_mapping_discrepancy"]
    require(mapping["status"] ==
            "STRUCTURE_SEGMENT_RECONCILED_ASSAY_CONSTRUCT_UNRESOLVED"
            and mapping["deposited_fields"]["_struct_ref.pdbx_db_accession"] == "Q8WUV3"
            and mapping["current_api_fields"][
                "rcsb_polymer_entity_container_identifiers.uniprot_ids"] == ["O60678"]
            and mapping["expression_tag_entity_positions_1_19"] ==
            "MGSSHHHHHHSSGLVPRGS"
            and mapping["aligned_entity_positions"] == "20-340"
            and mapping["aligned_deposited_q8wuv3_positions"] == "228-548"
            and mapping["aligned_current_o60678_positions"] == "211-531"
            and mapping["aligned_amino_acid_count"] == 321
            and mapping["aligned_segment_sha256"] ==
            "bbc8b5d4d286141e3998516321d68a12a9fc338fc4f16a00a22527b3281d0899"
            and mapping["sequence_segment_equality_verified"] is True
            and mapping["o60678_number_equals_q8wuv3_number_minus"] == 17
            and mapping["canonical_residue_remapping_verified"] is True
            and mapping["full_length_accessions_identical"] is False
            and mapping["assay_construct_linkage_verified"] is False
            and mapping["accessions_treated_as_equivalent"] is False,
            "source_mapping_discrepancy_erased")
    assay = manifest["experimental_observation"]
    require(assay["endpoint_subtype"] ==
            "PRMT3_biochemical_scintillation_proximity_assay_IC50"
            and assay["endpoint"] == "IC50"
            and assay["biochemical_construct"] is None
            and assay["complete_assay_protocol_verified"] is False
            and assay["ic50_converted_to_ki_kd_or_binding_free_energy"] is False,
            "assay_scope_changed")
    require(assay["measurements"] == [
        {"compound": "SGC707", "operator": "=", "value_nM": 31,
         "reported_plus_minus_nM": 2, "uncertainty_kind": None, "reported_n": 3,
         "censored": False},
        {"compound": "XY1", "operator": ">", "value_nM": 100000,
         "reported_plus_minus_nM": None, "uncertainty_kind": None, "reported_n": None,
         "censored": True,
         "interpretation": "reported inactive at highest tested concentration; no finite fitted IC50 asserted"},
    ], "source_measurement_or_censoring_changed")

    family = manifest["source_family_audit"]
    require(family["completeness"] is False
            and family["full_family_identity_graph_screened"] is False
            and family["article_reports_more_than_100_designed_synthesized_tested_analogues"]
            is True
            and family["exact_total_tested_compounds"] is None
            and family["all_2015_measured_compound_identities"] is None
            and family["primary_2015_si_content_verified"] is False
            and family["primary_2015_si_bytes_imported"] is False,
            "source_family_completion_overclaimed")
    projection = family["later_sar_identity_projection"]
    expected_ids = [str(i) for i in range(1, 27)] + [str(i) for i in range(29, 41)] + [
        "49", "50", "51"]
    require(projection["row_count"] == 41
            and projection["compound_ids"] == expected_ids
            and projection["columns_emitted"] == ["Compound _ID", "SMILES"]
            and projection["raw_bytes_imported"] is False
            and projection["does_not_establish_2015_family_completeness"] is True,
            "later_sar_projection_changed")

    screen = manifest["historical_pair_screen"]
    require(screen["receipt_sha256"] ==
            "05b39fd925b38adbb932265b34ffb8c124328d2a522b79ffd39bbd292d19b42b"
            and screen["executed_repository_head"] ==
            "67e65a87a5b1a77cf13b47c7c3fbee17b4be8d79"
            and screen["candidates_screened"] == ["SGC707", "XY1"]
            and screen["chemical_candidate_count"] == 2
            and screen["component_count"] == 1 and screen["component_node_count"] == 4
            and screen["result_status"] == "identity_clear_review_required",
            "historical_screen_identity_changed")
    require(all(screen[key] is False for key in (
        "source_family_completeness", "current_head_revalidated", "current_global_clearance",
        "protected_outcomes_read_by_receipt", "protected_context_bytes_imported",
        "comparison_with_current_protected_context_performed")),
        "historical_screen_scope_overclaimed")
    require(all(type(screen[key]) is int and screen[key] == 0 for key in (
        "training_rows_admitted", "calibration_rows_admitted",
        "evaluation_rows_admitted", "prepared_pairs_created")),
        "nonzero_admission_count")
    rights = manifest["source_rights_observation"]
    require(rights["archive_file_reuse_basis_verified"] is True
            and rights["archive_file_license"] == "CC0-1.0"
            and rights["publisher_2015_article_use_specific_permission"] is None
            and rights["publisher_2015_si_use_specific_permission"] is None
            and rights["source_family_training_or_product_use_review_complete"] is False
            and rights["free_reading_treated_as_open_reuse_permission"] is False,
            "rights_completion_overclaimed")
    roles = manifest["protection_and_roles"]
    require(roles == {
        "protected_outcomes_accessed": False, "protected_context_opened": False,
        "source_component_role": None, "fit_role": None,
        "calibration_role": None, "evaluation_role": None},
        "protected_access_or_role_assignment")
    eligibility = manifest["eligibility"]
    require(set(eligibility) == {
        "prepared_input_executable", "numeric_comparison_executable",
        "experimental_comparison_eligible", "training_admitted", "calibration_admitted",
        "independent_evaluation_admitted", "product_ranking_enabled",
        "customer_execution", "scientifically_validated"}
        and all(value is False for value in eligibility.values()),
        "eligibility_must_remain_false")
    require(manifest["performed_actions"] == {
        "public_source_audit": True, "archive_bytes_recorded": True,
        "publisher_si_bytes_imported": False, "receptor_prepared": False,
        "ligands_prepared": False, "fit_or_evaluation_roles_assigned": False,
        "physical_evaluations": 0}, "non_static_action_claimed")
    decisions = manifest["unresolved_decisions"]
    require(len(decisions) == len(DECISIONS)
            and {item["id"] for item in decisions} == DECISIONS
            and all(item["status"] == "unresolved" for item in decisions),
            "unresolved_decision_set_changed")
    return len(receipts)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"),
                          object_pairs_hook=unique_object, parse_constant=reject_constant)
    count = validate(manifest)
    print(json.dumps({
        "status": "PASS_STATIC_SOURCE_CANDIDATE_BLOCKED",
        "source_files_verified": count,
        "source_family_complete": False,
        "scientific_admission": False,
        "prepared_pairs_created": 0,
        "physical_evaluations": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
