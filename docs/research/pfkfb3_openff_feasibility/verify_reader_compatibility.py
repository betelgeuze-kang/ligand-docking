"""Offline integrity check for the 40-ID PFKFB3 development reader receipt.

This checks a saved compact receipt against an independently pinned source
inventory. It does not run the prepared reader, open the prepared files,
download official bytes, inspect assays, or perform a numerical comparison.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "reader_compatibility.v1.json"
INVENTORY = ROOT / "openff_lfs_inventory.v1.json"
INVENTORY_VERIFIER = ROOT / "verify_openff_lfs_inventory.py"

SCHEMA = "pfkfb3_openff_v3_reader_compatibility_v1"
STATUS = "PASS_DEVELOPMENT_READER_COMPATIBILITY_SOURCE_ROLE_BLOCKED"
RAW_SHA256 = "24b2bb11b42ac06baad50da2bb4a5f77cda7ce5bb2b816450beaf9c1e04fce14"
RAW_BYTES = 182925
HISTORICAL_REQUEST_SHA256 = (
    "ec956d769c868c985e854b9bae1689d265991324e541bed01fd0f08fe46da9fb"
)
READER_SHA256 = "e73b6516de6535a6bca6a6d8fe407635778f52e77b1da674a7d9e71dab058bb0"
CODE_HEAD = "50d8fa01af596e29099bc2336f430869d3d7a7b9"
PYTHON_VERSION = "3.10.12"
SWEEP_SECONDS = 161.769
ATOM_COUNTS = (
    45,
    47,
    44,
    46,
    49,
    51,
    48,
    48,
    45,
    48,
    50,
    53,
    62,
    51,
    45,
    47,
    47,
    43,
    43,
    46,
    49,
    47,
    45,
    53,
    56,
    56,
    50,
    53,
    50,
    48,
    49,
    54,
    44,
    44,
    45,
    45,
    47,
    48,
    49,
    49,
)
LIGAND_KINDS = ("sdf", "gro", "ligand_itp", "atomtypes_itp", "ligand_top")
ROW_FIELDS = {
    "ligand_id",
    "reader_status",
    "reader_failure_reason",
    "receptor_atom_count",
    "ligand_atom_count",
    "source_hashes_postflight_verified",
    "official_files",
    "source_coevality_verified",
    "source_declarations_verified",
    "prepared_state_assay_equivalence_verified",
    "numeric_comparison_pass",
    "fit_role",
    "calibration_role",
    "evaluation_role",
    "reader_seconds",
}
BOUNDARY_FIELDS = {
    "official_source_rechecked_now",
    "loader_reexecuted_by_offline_verifier",
    "source_coevality_verified",
    "source_declarations_verified",
    "prepared_state_assay_equivalence_verified",
    "numeric_comparison_performed",
    "scientific_comparison_eligible",
    "training_admitted",
    "protected_evaluation_outcomes_accessed",
    "experimental_assay_values_extracted_or_exported",
}


def _same(actual: object, expected: object, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError(f"{label}_mismatch")


def _inventory_module():
    spec = importlib.util.spec_from_file_location(
        "pfkfb3_openff_lfs_inventory_verifier", INVENTORY_VERIFIER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("inventory_verifier_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ref(value: object, inventory_row: dict, label: str) -> None:
    if type(value) is not dict or set(value) != {"repository_path", "sha256"}:
        raise ValueError(f"{label}_fields")
    _same(value["repository_path"], inventory_row["path"], f"{label}_path")
    _same(value["sha256"], inventory_row["lfs_oid_sha256"], f"{label}_sha256")


def verify(manifest: Path = MANIFEST, inventory: Path = INVENTORY) -> dict:
    """Check saved metadata only; never invoke the loader or a network endpoint."""
    source_verifier = _inventory_module()
    verified_inventory = source_verifier.verify(inventory)
    source, source_digest = source_verifier._load(inventory)
    document, _ = source_verifier._load(manifest)
    if type(document) is not dict or set(document) != {
        "schema_version",
        "status",
        "provenance",
        "boundary",
        "common_official_files",
        "rows",
    }:
        raise ValueError("reader_receipt_fields")
    _same(document["schema_version"], SCHEMA, "schema")
    _same(document["status"], STATUS, "status")
    _same(verified_inventory["inventory_sha256"], source_digest, "inventory_identity")

    provenance = document["provenance"]
    if type(provenance) is not dict or set(provenance) != {
        "openff_commit",
        "inventory_sha256",
        "raw_temp_receipt_sha256",
        "raw_temp_receipt_bytes",
        "historical_lig38_request_sha256",
        "protein_parameter_source",
        "reader_module_sha256",
        "code_head",
        "python_version",
        "reader_sweep_seconds",
    }:
        raise ValueError("provenance_fields")
    _same(provenance["openff_commit"], source["source"]["commit"], "openff_commit")
    _same(provenance["inventory_sha256"], source_digest, "inventory_sha")
    for key, expected in (
        ("raw_temp_receipt_sha256", RAW_SHA256),
        ("raw_temp_receipt_bytes", RAW_BYTES),
        ("historical_lig38_request_sha256", HISTORICAL_REQUEST_SHA256),
        ("reader_module_sha256", READER_SHA256),
        ("code_head", CODE_HEAD),
        ("python_version", PYTHON_VERSION),
        ("reader_sweep_seconds", SWEEP_SECONDS),
    ):
        _same(provenance[key], expected, key)
    protein = provenance["protein_parameter_source"]
    _same(
        protein,
        {
            "zenodo_record": "https://zenodo.org/records/10495732",
            "historical_archive_sha256": "50ae6280e8628005542cb560f77edbce0624737bf1feb813ec65e62df25b9b41",
            "rights_reviewed": False,
            "coevality_verified": False,
            "files": {
                "protein_atomtypes": {
                    "archive_member": "ffnonbonded.itp",
                    "sha256": "70bb6bdf7c651267749a91c7b296536a284acf1ad67a7d7a5cd60bb8b5ff8370",
                },
                "protein_defaults": {
                    "archive_member": "forcefield.itp",
                    "sha256": "a73df8ee82c58f106364276622f7bfab8130cdc2cb698342030ef84545569d0b",
                },
            },
        },
        "separate_protein_parameters",
    )

    boundary = document["boundary"]
    if type(boundary) is not dict or set(boundary) != BOUNDARY_FIELDS:
        raise ValueError("boundary_fields")
    for name in BOUNDARY_FIELDS:
        _same(boundary[name], False, name)

    support = {(row["ligand_id"], row["kind"]): row for row in source["support_files"]}
    core = {(row["ligand_id"], row["kind"]): row for row in source["files"]}
    common = document["common_official_files"]
    if type(common) is not dict or set(common) != {"protein_pdb", "protein_topol_itp"}:
        raise ValueError("common_file_fields")
    for kind in ("protein_pdb", "protein_topol_itp"):
        _ref(common[kind], support[(None, kind)], f"common_{kind}")

    rows = document["rows"]
    ids = source_verifier.IDS
    if type(rows) is not list or len(rows) != len(ids) or len(ATOM_COUNTS) != len(ids):
        raise ValueError("reader_row_count")
    for position, (row, ligand_id, expected_atoms) in enumerate(
        zip(rows, ids, ATOM_COUNTS, strict=True)
    ):
        label = f"row_{position}"
        if type(row) is not dict or set(row) != ROW_FIELDS:
            raise ValueError(f"{label}_fields")
        _same(row["ligand_id"], ligand_id, f"{label}_id")
        _same(row["reader_status"], "PASS", f"{label}_reader_status")
        _same(row["reader_failure_reason"], None, f"{label}_failure_reason")
        _same(row["receptor_atom_count"], 6749, f"{label}_receptor_count")
        _same(row["ligand_atom_count"], expected_atoms, f"{label}_ligand_count")
        _same(row["source_hashes_postflight_verified"], True, f"{label}_postflight")
        for key in (
            "source_coevality_verified",
            "source_declarations_verified",
            "prepared_state_assay_equivalence_verified",
        ):
            _same(row[key], False, f"{label}_{key}")
        for key in (
            "numeric_comparison_pass",
            "fit_role",
            "calibration_role",
            "evaluation_role",
        ):
            _same(row[key], None, f"{label}_{key}")
        seconds = row["reader_seconds"]
        if type(seconds) not in (int, float) or not 0 < seconds < 30:
            raise ValueError(f"{label}_seconds")
        ligand_files = row["official_files"]
        if type(ligand_files) is not dict or set(ligand_files) != set(LIGAND_KINDS):
            raise ValueError(f"{label}_official_file_fields")
        for kind in LIGAND_KINDS:
            inventory_row = (support if kind == "ligand_top" else core)[
                (ligand_id, kind)
            ]
            _ref(ligand_files[kind], inventory_row, f"{label}_{kind}")
    if abs(sum(row["reader_seconds"] for row in rows) - SWEEP_SECONDS) > 0.1:
        raise ValueError("reader_timing_sum_mismatch")
    return {
        "status": "PASS_READ_ONLY_READER_COMPATIBILITY",
        "ligand_count": len(rows),
        "reader_pass_count": len(rows),
        "inventory_sha256": source_digest,
        "raw_temp_receipt_sha256": RAW_SHA256,
        "official_source_rechecked_now": False,
        "loader_reexecuted_by_offline_verifier": False,
        "scientific_comparison_eligible": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.manifest, arguments.inventory), sort_keys=True))
