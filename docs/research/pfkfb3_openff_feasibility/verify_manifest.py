"""Offline integrity check for a blocked, metadata-only PFKFB3 feasibility receipt.

This checks only this checkout's small JSON packet against independently pinned
constants. It never opens the external archive, prepared files, experimental
values, historical numeric reports, or protected evaluation context.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "feasibility.v1.json"
OFFICIAL_LFS_INVENTORY = (
    "openff_lfs_inventory.v1.json",
    102836,
    "23345cfcb902ee7d0009ee630760797a6212ed7047f273eb4edef9487bc56e13",
)
READER_COMPATIBILITY_RECEIPT = (
    "reader_compatibility.v1.json",
    69617,
    "70bfb752447f182f215312ef2cfd8da3e6762525ae9ccfeb812edb76e0725200",
)
PRIMARY_STRUCTURE_CROSSWALK = (
    "primary_structure_crosswalk.v1.json",
    32944,
    "bfd3c57f0d3d992d30028a035dc52c9c4733eecf613ceffce2f0f44add636d52",
)
MAX_BYTES = 32_768
IDS = (
    "lig_19",
    "lig_20",
    "lig_23",
    "lig_24",
    "lig_26",
    "lig_29",
    "lig_30",
    "lig_31",
    "lig_33",
    "lig_34",
    "lig_35",
    "lig_36",
    "lig_37",
    "lig_38",
    "lig_39",
    "lig_41",
    "lig_42",
    "lig_43",
    "lig_44",
    "lig_46",
    "lig_47",
    "lig_48",
    "lig_49",
    "lig_52",
    "lig_53",
    "lig_54",
    "lig_55",
    "lig_56",
    "lig_57",
    "lig_58",
    "lig_59",
    "lig_60",
    "lig_62",
    "lig_63",
    "lig_64",
    "lig_65",
    "lig_67",
    "lig_68",
    "lig_69",
    "lig_70",
)
COMMIT = "fe6f96916b2e28f9c14398d77c838d6515e931b0"
BASE = "data/2020-07-06_pfkfb3/"
INPUTS = (
    (
        "protein_pdb",
        "openff_cc_by_4_0",
        BASE + "01_protein/crd/protein.pdb",
        533236,
        "a92c23ece51dd98900faaf90a379bff0edaa8c5fb78bf0eb6100edd5995ff7a3",
    ),
    (
        "protein_itp",
        "openff_cc_by_4_0",
        BASE + "01_protein/top/amber99sb-star-ildn-mut.ff/topol.itp",
        1920050,
        "c1d4902f016c479d23ae91b697803cbadb8e0331fb35ee7bdc0d9ddbda7d9cee",
    ),
    (
        "protein_atomtypes",
        "separate_zenodo_10495732_rights_not_reviewed",
        "ffnonbonded.itp",
        7013,
        "70bb6bdf7c651267749a91c7b296536a284acf1ad67a7d7a5cd60bb8b5ff8370",
    ),
    (
        "protein_defaults",
        "separate_zenodo_10495732_rights_not_reviewed",
        "forcefield.itp",
        951,
        "a73df8ee82c58f106364276622f7bfab8130cdc2cb698342030ef84545569d0b",
    ),
    (
        "ligand_sdf",
        "openff_cc_by_4_0",
        BASE + "02_ligands/lig_38/crd/lig_38.sdf",
        4395,
        "407014add44d32a3a3b483aaa01e6799e7fe8350faf82ef720f1eb3d9ea32899",
    ),
    (
        "ligand_gro",
        "openff_cc_by_4_0",
        BASE + "02_ligands/lig_38/top/openff-1.0.0.offxml/lig_38.gro",
        3139,
        "33f82c3310153536aba0eb65d0c93e8548fd914cd3da4da8bf6f801544b25d0e",
    ),
    (
        "ligand_itp",
        "openff_cc_by_4_0",
        BASE + "02_ligands/lig_38/top/openff-1.0.0.offxml/lig_38.itp",
        25219,
        "a2684ba2c58cccf8bb2eaafa25da5450ec633932eafd08e20a6888f83d457d59",
    ),
    (
        "ligand_atomtypes",
        "openff_cc_by_4_0",
        BASE + "02_ligands/lig_38/top/openff-1.0.0.offxml/fflig_38.itp",
        599,
        "48fef9061ce0d08ae363c190816ac60d32407fbd3664078d32b65b170da4dc90",
    ),
)


def expected_manifest() -> dict:
    """Pinned transcription, with false/null admissions for every candidate."""
    input_fields = [row[0] for row in INPUTS]
    return {
        "schema_version": "pfkfb3_openff_source_role_feasibility_v1",
        "status": "ARCHIVED_DEVELOPMENT_SOURCE_ONLY_COMPARISON_BLOCKED",
        "source": {
            "target": "human_PFKFB3",
            "openff_commit": COMMIT,
            "openff_directory": BASE.removesuffix("/"),
            "openff_data_license": "CC-BY-4.0",
            "primary_paper_doi": "10.1002/cmdc.201800569",
            "archive_sha256": "50ae6280e8628005542cb560f77edbce0624737bf1feb813ec65e62df25b9b41",
            "archive_bytes": 41960330,
            "archive_member_manifest_sha256": "c09a6f58f21d5a9c3300b6a358973df4e88a7beb26503b56081f37e2cce3a26f",
            "archive_bundled_in_checkout": False,
            "archive_revalidated_by_offline_verifier": False,
            "separate_parameter_record": {
                "zenodo_record_id": 10495732,
                "zenodo_record_created_date": "2024-01-12",
                "zenodo_record_license_id": "cc-by-4.0",
                "zenodo_archive_bytes": 381220,
                "zenodo_archive_md5": "b058f4cf301b0c695f93af16c8fabf36",
                "zenodo_archive_sha256": "9ea86b0e1641eb9ca4f691867c62f65b39c010d2a55d8a0adb1fbf7df9668371",
                "record_metadata_rechecked_by_offline_verifier": False,
                "archive_bytes_bundled_in_checkout": False,
                "exact_file_version_declared_by_openff": False,
                "file_specific_rights_reviewed": False,
                "coevality_verified": False,
            },
            "primary_paper_and_supplement_rights_reviewed_for_product": False,
            "separate_protein_parameters_rights_and_coevality_reviewed": False,
        },
        "official_openff_lfs_inventory": {
            "relative_path": OFFICIAL_LFS_INVENTORY[0],
            "size_bytes": OFFICIAL_LFS_INVENTORY[1],
            "sha256": OFFICIAL_LFS_INVENTORY[2],
            "ligand_id_count": 40,
            "official_source_file_count": 202,
            "source_bytes_bundled_in_checkout": False,
            "external_source_rechecked_by_offline_feasibility_verifier": False,
            "prepared_state_assay_equivalence_verified": False,
        },
        "reader_compatibility_receipt": {
            "relative_path": READER_COMPATIBILITY_RECEIPT[0],
            "size_bytes": READER_COMPATIBILITY_RECEIPT[1],
            "sha256": READER_COMPATIBILITY_RECEIPT[2],
            "reader_candidate_count": 40,
            "reader_pass_count": 40,
            "loader_reexecuted_by_offline_feasibility_verifier": False,
            "source_coevality_verified": False,
            "scientific_comparison_eligible": False,
        },
        "primary_structure_crosswalk_receipt": {
            "relative_path": PRIMARY_STRUCTURE_CROSSWALK[0],
            "size_bytes": PRIMARY_STRUCTURE_CROSSWALK[1],
            "sha256": PRIMARY_STRUCTURE_CROSSWALK[2],
            "direct_primary_anchor_count": 4,
            "primary_text_motif_match_count": 14,
            "unverified_count": 22,
            "external_sources_rechecked_by_offline_feasibility_verifier": False,
            "prepared_state_assay_equivalence_verified": False,
            "scientific_comparison_eligible": False,
        },
        "archived_context_observation": {
            "candidate_count": 40,
            "single_study_component_count": 1,
            "blocked_candidate_count_in_archived_context": 0,
            "reserved_or_unknown_nodes_in_archived_candidate_component": 0,
            "archived_context_is_current_frozen_context": False,
            "current_protected_component_clearance": None,
            "archived_metadata_replayed_by_offline_verifier": False,
        },
        "archived_lig_38_prepared_input_refs": [
            {
                "field": field,
                "source_role": source_role,
                "source_path": path,
                "bytes": size,
                "sha256": digest,
            }
            for field, source_role, path, size, digest in INPUTS
        ],
        "archived_v3_lig_38_numeric_report": {
            "sha256": "0d8f9b94473840a03455e0c7955613195cfc5763c01bae8d309b735aeef23fb2",
            "bytes": 31298164,
            "source": "2026-09-09_external_delivery",
            "bundled_in_checkout": False,
            "is_one_of_40_individually_verified_historical_pfk40_reports": False,
        },
        "historical_pfk40_numeric_reports": {
            "documented_report_count": 40,
            "source_document": "docs/prepared_cross_numeric_check.md",
            "individual_report_refs_in_checkout": 0,
            "report_bytes_replayed_by_offline_verifier": False,
            "numeric_pass_count_admitted_for_scientific_comparison": 0,
        },
        "assay_boundary": {
            "endpoint_type_reported_by_catalogue": "IC50",
            "experimental_values_read_or_copied_into_packet": False,
            "original_paper_compound_table_mapping_verified": False,
            "assay_relation_and_conditions_verified": False,
            "same_assay_active_inactive_pair_proven": False,
            "active_inactive_threshold_prespecified": False,
            "prepared_state_assay_equivalence_verified": False,
        },
        "candidates": [
            {
                "ligand_id": rid,
                "archived_prepared_input_ref_fields": input_fields
                if rid == "lig_38"
                else [],
                "historical_pfk40_numeric_report_ref": None,
                "fit_role": None,
                "calibration_role": None,
                "evaluation_role": None,
                "eligible_source_state_join": False,
            }
            for rid in IDS
        ],
        "eligibility": {
            "eligible_source_state_join_count": 0,
            "current_protected_context_clearance_verified": False,
            "independent_fit_source_verified": False,
            "four_arm_same_candidate_experiment_executable": False,
            "experimental_comparison_eligible": False,
            "training_admitted": False,
            "scientifically_validated": False,
            "product_ranking_enabled": False,
        },
    }


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def load_manifest(path: Path = MANIFEST) -> tuple[dict, str]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > MAX_BYTES
        ):
            raise ValueError("invalid_manifest_file")
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(raw) != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_size,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_size,
    ):
        raise ValueError("manifest_changed_during_read")
    value = json.loads(
        raw,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )
    return value, hashlib.sha256(raw).hexdigest()


def verify(path: Path = MANIFEST) -> dict:
    observed, digest = load_manifest(path)

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    if canonical(observed) != canonical(expected_manifest()):
        raise ValueError("pfkfb3_feasibility_receipt_mismatch")
    inventory_path = ROOT / OFFICIAL_LFS_INVENTORY[0]
    if (
        not inventory_path.is_file()
        or inventory_path.is_symlink()
        or inventory_path.stat().st_size != OFFICIAL_LFS_INVENTORY[1]
        or hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        != OFFICIAL_LFS_INVENTORY[2]
    ):
        raise ValueError("official_lfs_inventory_bytes_changed")
    reader_path = ROOT / READER_COMPATIBILITY_RECEIPT[0]
    if (
        not reader_path.is_file()
        or reader_path.is_symlink()
        or reader_path.stat().st_size != READER_COMPATIBILITY_RECEIPT[1]
        or hashlib.sha256(reader_path.read_bytes()).hexdigest()
        != READER_COMPATIBILITY_RECEIPT[2]
    ):
        raise ValueError("reader_compatibility_receipt_bytes_changed")
    crosswalk_path = ROOT / PRIMARY_STRUCTURE_CROSSWALK[0]
    if (
        not crosswalk_path.is_file()
        or crosswalk_path.is_symlink()
        or crosswalk_path.stat().st_size != PRIMARY_STRUCTURE_CROSSWALK[1]
        or hashlib.sha256(crosswalk_path.read_bytes()).hexdigest()
        != PRIMARY_STRUCTURE_CROSSWALK[2]
    ):
        raise ValueError("primary_structure_crosswalk_receipt_bytes_changed")
    return {
        "status": "PASS_STATIC_FEASIBILITY_BLOCKED",
        "manifest_sha256": digest,
        "candidate_count": 40,
        "archived_prepared_candidate_ref_count": 1,
        "individually_replayable_historical_pfk40_report_count": 0,
        "eligible_source_state_join_count": 0,
        "official_lfs_inventory_file_count": 202,
        "development_reader_pass_count": 40,
        "direct_primary_structure_anchor_count": 4,
        "partial_primary_structure_motif_count": 14,
        "unverified_primary_structure_count": 22,
        "loader_reexecuted_by_offline_verifier": False,
        "external_archive_or_source_bytes_checked": False,
        "experimental_values_or_protected_outcomes_read": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
