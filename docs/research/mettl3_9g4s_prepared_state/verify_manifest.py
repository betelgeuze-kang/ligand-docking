"""Read-only validation of the unresolved 9G4S decision snapshot.

No molecular libraries, preparation, worker, network or protected context access.
Optional source verification hashes SI bytes without decoding their contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


SCHEMA = "mettl3_9g4s_prepared_state_decision_manifest_v1"
STATUS = "DECISIONS_UNRESOLVED_EXECUTION_BLOCKED"
PINNED_MANIFESTS = {
    "identity_manifest": "4de817f3b3353ee81b3c7a1ba61d2c4f0b59e512f468c2e141aa49eac68847ab",
    "preflight_manifest": "7ab5894b3c71b1d588ce2d577e3ba9151dadcd8b408061dccd6c485bcddb4e79",
}
PREFLIGHT_IDS = (
    "assay_Active_Motif_protein_construct_vs_Sf21_crystal_construct_unknown",
    "METTL14_B273_LEU_vs_UniProt_LYS_source_conflict_requires_state_decision",
    "26_unmodeled_METTL14_residues_and_undeclared_construct_termini_require_explicit_policy",
    "all_protein_and_34_ligand_hydrogens_absent_from_deposition",
    "ligand_protonation_tautomer_partial_charge_and_forcefield_not_prepared",
    "23_crystal_water_oxygen_sites_within_6_A_require_retention_or_exclusion_policy",
    "five_Ca_and_TRS_plus_protein_altlocs_require_full_system_treatment_if_retained",
    "SI_crystallography_compound_numbers_conflict_with_CCD_stereo_CSV_titles",
    "prepared_PDB_SDF_GRO_ITP_parameter_sources_not_supplied",
)
EXTRA_IDS = (
    "source_and_use_specific_rights_unresolved",
    "independent_source_component_roles_unassigned",
    "spa_endpoint_and_activity_definition_unresolved",
    "numeric_comparison_protocol_not_frozen",
)
ELIGIBILITY = {
    "prepared_input_executable", "numeric_comparison_executable",
    "experimental_comparison_eligible", "assay_state_equivalence_verified",
    "training_admitted", "scientifically_validated", "product_ranking_enabled",
    "customer_execution",
}
ACTION_KEYS = {
    "chemical_preparation", "source_atoms_deleted", "source_coordinates_changed",
    "prepared_bundle_generated", "experimental_values_decoded_or_used", "role_assignment",
    "engine_evaluations", "benchmark_runs", "protected_evaluation_access",
}
EMPTY_SLOTS = {
    "prepared_file_slots": {
        "protein_pdb", "protein_chains_ordered_molecule_itps", "protein_atomtypes",
        "protein_defaults", "ligand_sdf", "ligand_gro", "ligand_itp",
        "ligand_atomtypes", "ligand_defaults",
    },
    "source_declaration_slots": {
        "coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id",
    },
    "evaluation_slots": {
        "pocket_center_angstrom", "pocket_radius_angstrom", "cutoff_angstrom",
        "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom",
    },
}
SOURCE_STATUS = "SOURCE_GEOMETRY_OBSERVED_PREPARATION_BLOCKED"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key:" + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite_json_constant:" + value)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(manifest):
    require(manifest["schema_version"] == SCHEMA and manifest["status"] == STATUS,
            "unsupported_or_unblocked_decision_snapshot")
    require(set(manifest["eligibility"]) == ELIGIBILITY
            and all(value is False for value in manifest["eligibility"].values()),
            "eligibility_must_remain_false")
    require(manifest["selected_source_instance"] == {
        "auth_seq_id": "601", "component_id": "A1III", "entry_id": "9G4S",
        "label_asym_id": "C", "model_number": "1"}, "source_instance_changed")
    identity = manifest["identity_observation"]
    require(identity["experimental_value"] is None
            and identity["assay_construct_equivalence_verified"] is False
            and identity["printed_compound_number_resolved"] is False,
            "identity_only_boundary_changed")
    roles = manifest["protection_and_roles"]
    require(roles["source_component_role"] is None
            and roles["assigned_role_counts"] == {"fit": 0, "calibration": 0, "evaluation": 0}
            and roles["identity_context_access_required_by_verifier"] is False
            and roles["protected_outcomes_accessed"] is False
            and roles["source_component_may_be_split_across_roles"] is False
            and roles["identity_screen_grants_admission"] is False,
            "protection_or_role_boundary_changed")
    require(set(manifest["performed_actions"]) == ACTION_KEYS, "action_denominator_changed")
    for key, value in manifest["performed_actions"].items():
        expected = 0 if key in {"engine_evaluations", "benchmark_runs"} else False
        require(type(value) is type(expected) and value == expected,
                "non_static_action_declared:" + key)
    future = manifest["future_consumer_contract"]
    require(future["prepared_bundle"] is None
            and future["installed_native_v4_receptor_Ki_applicable"] is False
            and future["future_assay_contract"] == {
                "endpoint": "IC50", "endpoint_subtype": "enzyme_inhibition_IC50",
                "status": "unresolved_not_admitted"}, "future_contract_boundary_changed")
    for key, fields in EMPTY_SLOTS.items():
        require(set(future[key]) == fields and all(value is None for value in future[key].values()),
                "unprepared_slot_populated:" + key)
    require(len(manifest["recorded_source_permissions"]) == 4
            and all(item["use_specific_review_status"] == "unresolved"
                for item in manifest["recorded_source_permissions"]), "rights_not_resolved_here")
    refs = manifest["evidence_refs"]
    require(len(refs) == 19, "source_reference_denominator_changed")
    require(set(manifest["source_bundle_locations"]) == {"identity_screen", "structure_preflight"},
            "unexpected_source_bundle")
    for key, ref in refs.items():
        require(set(ref) == {"bundle", "relative_path", "sha256"}
                and ref["bundle"] in manifest["source_bundle_locations"], "invalid_reference:" + key)
        path = PurePosixPath(ref["relative_path"])
        require(not path.is_absolute() and path.parts and ".." not in path.parts
                and str(path) == ref["relative_path"], "invalid_relative_path:" + key)
        require(re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]) is not None,
                "invalid_source_hash:" + key)
    require(all(refs[key]["sha256"] == expected for key, expected in PINNED_MANIFESTS.items()),
            "pinned_receipt_manifest_changed")
    decisions = manifest["decisions"]
    require([item["id"] for item in decisions] == list(PREFLIGHT_IDS + EXTRA_IDS),
            "unresolved_decision_denominator_changed")
    for item in decisions:
        require(item["status"] == "unresolved" and item["selected_action"] is None
                and item["resolution_evidence"] == [], "decision_resolved_in_unresolved_snapshot")
        require(item["source_preflight_unresolved_id"] == (
                    item["id"] if item["id"] in PREFLIGHT_IDS else None),
                "source_blocker_mapping_changed")
        require(item["evidence_refs"] and all(key in refs for key in item["evidence_refs"]),
                "unknown_decision_evidence")
    observed = manifest["source_observation"]
    require(observed == {
        "status": SOURCE_STATUS, "observed_ligand_heavy_atoms": 34,
        "missing_ligand_hydrogens": 34, "observed_protein_hydrogens": 0,
        "physical_evaluations": 0, "all_atom_prepared": False,
        "receptor_prepared": False, "prepared_input_faithfully_instantiated": False,
    }, "source_observation_changed")


def verify_receipts(manifest, overrides):
    """Hash all 19 sources; decode only existing metadata and observation receipts."""
    refs = manifest["evidence_refs"]
    roots = {key: Path(overrides.get(key) or value["local_root_hint"]).resolve()
             for key, value in manifest["source_bundle_locations"].items()}
    paths = {}
    for key, ref in refs.items():
        root = roots[ref["bundle"]]
        path = (root / ref["relative_path"]).resolve()
        require(path.is_relative_to(root), "source_path_escapes_bundle:" + key)
        require(sha256(path) == ref["sha256"], "source_hash_mismatch:" + key)
        paths[key] = path
    sealed = {
        "identity_screen": read_json(paths["identity_manifest"])["files_sha256"],
        "structure_preflight": read_json(paths["preflight_manifest"])["artifact_sha256"],
    }
    for key, ref in refs.items():
        if key not in PINNED_MANIFESTS:
            require(sealed[ref["bundle"]].get(ref["relative_path"]) == ref["sha256"],
                    "reference_not_bound_by_original_manifest:" + key)
    preflight = read_json(paths["preflight_result"])
    require(preflight["unresolved"] == list(PREFLIGHT_IDS)
            and preflight["status"] == SOURCE_STATUS
            and preflight["experimental_labels_used"] is False
            and preflight["prepared_input_faithfully_instantiated"] is False
            and preflight["engine_v2_source_observation"]["physical_evaluations"] == 0,
            "preflight_state_mismatch")
    request = read_json(paths["observer_request"])
    require(request["cases"][0]["selection"] == manifest["selected_source_instance"],
            "observer_instance_mismatch")
    bridge = read_json(paths["structure_spa_identity_bridge"])
    links = [item for item in bridge["links"] if item["pdb"] == "9G4S"]
    require(len(links) == 1 and links[0]["no_measurement_fetched"] is True,
            "identity_bridge_mismatch")
    for local, original in (
        ("article_doi", "article_doi"), ("ccd_stereo_inchikey", "ccd_inchikey"),
        ("molecule_chembl_id", "molecule_chembl_id"),
        ("spa_assay_chembl_id", "spa_assay_chembl_id"), ("spa_activity_id", "spa_activity_id"),
    ):
        require(manifest["identity_observation"][local] == links[0][original],
                "identity_observation_mismatch:" + local)
    graph = read_json(paths["joint_identity_screen"])
    require(manifest["protection_and_roles"]["identity_context_sha256"] == graph["base_sha256"]
            and manifest["protection_and_roles"]["identity_policy"] == graph["policy"],
            "identity_policy_binding_mismatch")
    for key, path in paths.items():
        require(sha256(path) == refs[key]["sha256"], "source_changed_during_verification:" + key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("decision_manifest.v1.json"))
    parser.add_argument("--verify-receipts", action="store_true")
    parser.add_argument("--identity-root", type=Path)
    parser.add_argument("--preflight-root", type=Path)
    args = parser.parse_args()
    require(args.verify_receipts or not (args.identity_root or args.preflight_root),
            "source_root_override_requires_verify_receipts")
    before = sha256(args.manifest)
    manifest = read_json(args.manifest)
    validate(manifest)
    if args.verify_receipts:
        verify_receipts(manifest, {"identity_screen": args.identity_root,
                                   "structure_preflight": args.preflight_root})
    require(sha256(args.manifest) == before, "manifest_changed_during_verification")
    print(json.dumps({
        "status": "PASS_STATIC_DECISION_SPECIFICATION", "manifest_sha256": before,
        "decision_status": STATUS, "unresolved_decisions": len(manifest["decisions"]),
        "source_references": len(manifest["evidence_refs"]),
        "source_receipt_hashes_verified": args.verify_receipts,
        "scientific_eligibility_verified": False, "execution_eligible": False,
        "molecular_execution_performed": False, "protected_context_opened": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
