"""Verify a source-only packet and rederive its unchanged-coordinate inventory."""
import argparse
import hashlib
import json
from pathlib import Path

from verify_source_inventory import SOURCE_SHA256, derive

HERE = Path(__file__).resolve().parent
SOURCE_URL = "https://files.rcsb.org/download/7XTB.cif"
RECEPTOR = {"entity_id": "5", "label_asym_id": "E", "auth_asym_id": "R"}
SELECTION = {"entry_id": "7XTB", "label_asym_id": "F", "component_id": "SRO",
             "auth_seq_id": "501", "model_number": "1"}
REQUIRED_FILES = {"7XTB.cif", "download-receipt.json", "observation-request.json",
                  "observation-report.json", "source-preparation-inventory.json",
                  "repeat-verification.json"}
REQUIRED_AUTHORITY = {"prepared_receptor", "prepared_ligand", "PR49_PR59_pose_supplied",
                      "assay_state_equivalence_verified", "roles_assigned",
                      "training_admitted", "evaluation_outcomes_read",
                      "protected_inputs_read", "scientifically_validated",
                      "product_ranking_enabled"}
REQUIRED_DECISIONS = {"fusion_construct", "loops_and_termini", "missing_atom",
                      "disulfide", "waters_and_membrane", "gs_nb35_context",
                      "microstates", "parameters_and_source_frame",
                      "pr49_pr59_linkage", "source_roles_and_endpoint"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify(manifest, root):
    """Reject changed claims and omissions before accepting a hash-bound packet."""
    require(manifest["status"] == "SOURCE_OBSERVED_PREPARATION_AND_ADMISSION_BLOCKED", "status_changed")
    require(manifest["source_url"] == SOURCE_URL, "source_url_changed")
    require(manifest["selection"] == SELECTION, "selection_changed")
    require(manifest["receptor_source_selection"] == RECEPTOR, "receptor_selection_changed")
    require(type(manifest["authority"]) is dict
            and set(manifest["authority"]) == REQUIRED_AUTHORITY, "authority_fields_changed")
    require(all(value is False for value in manifest["authority"].values()), "authority_changed")
    decisions = manifest["preparation_decisions"]
    require(type(decisions) is list and len(decisions) == len(REQUIRED_DECISIONS)
            and {decision["id"] for decision in decisions} == REQUIRED_DECISIONS,
            "preparation_decisions_changed")
    for decision in decisions:
        require(decision["status"] == "unresolved" and decision["selected_action"] is None,
                "decision_unexpectedly_resolved")
    files = manifest["files"]
    require(type(files) is list and len(files) == len(REQUIRED_FILES)
            and {entry["name"] for entry in files} == REQUIRED_FILES,
            "bundle_files_changed")
    for entry in files:
        path = Path(entry["name"])
        require(len(path.parts) == 1 and path.name not in {".", ".."}, "invalid_bundle_path")
        raw = (root / path).read_bytes()
        require(len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                "bundle_file_hash_or_size_mismatch:" + path.name)
    request = json.loads((root / "observation-request.json").read_text())
    report = json.loads((root / "observation-report.json").read_text())
    observation = report["rows"][0]["observation"]
    provenance = request["cases"][0]["provenance"]
    require(report["denominator"] == {"requested": 1, "observed": 1, "failed": 0,
                                      "skipped": 0, "physical_evaluations": 0}, "denominator_changed")
    require(provenance == report["rows"][0]["provenance"], "provenance_mismatch")
    require(provenance["source_url"] == manifest["source_url"]
            and provenance["receptor_candidate"] == manifest["receptor_source_selection"],
            "receptor_source_provenance_mismatch")
    require(observation["selection"] == request["cases"][0]["selection"] == manifest["selection"],
            "selection_mismatch")
    require(observation["source"] == request["cases"][0]["source"], "source_binding_mismatch")
    require(observation["source"]["sha256"] == SOURCE_SHA256
            and next(entry for entry in files if entry["name"] == "7XTB.cif")["sha256"] == SOURCE_SHA256,
            "source_sha256_mismatch")
    require(observation["selected_atom_site_count"] == 13, "selected_atom_count_changed")
    for flag in ("all_atom_prepared", "receptor_prepared", "assay_state_equivalence_verified",
                 "training_admitted", "scientifically_validated", "customer_execution"):
        require(observation[flag] is False, "observation_authority_changed:" + flag)
    for field in ("partial_charges_e", "potential_energy", "forces"):
        require(observation[field] is None, "unexpected_physical_output:" + field)
    inventory = json.loads((root / "source-preparation-inventory.json").read_text())
    require(derive(root / "7XTB.cif") == inventory, "source_inventory_rederivation_mismatch")
    require(inventory["summary"] == manifest["source_observation_summary"],
            "source_observation_summary_mismatch")
    require(inventory["source_sha256"] == SOURCE_SHA256
            and inventory["prepared"] is False
            and inventory["physical_evaluations"] == 0
            and inventory["assay_state_equivalence_verified"] is False
            and inventory["roles_assigned"] is False
            and inventory["protected_inputs_read"] is False,
            "source_inventory_authority_changed")
    repeat = json.loads((root / "repeat-verification.json").read_text())
    require(repeat["status"] == "PASS_EXACT_OBSERVATION_REPLAY", "repeat_verification_not_passed")
    require(repeat["request_sha256"] == hashlib.sha256((root / "observation-request.json").read_bytes()).hexdigest(),
            "repeat_request_binding_mismatch")
    require(repeat["report_sha256"] == hashlib.sha256((root / "observation-report.json").read_bytes()).hexdigest(),
            "repeat_report_binding_mismatch")
    return {"status": "PASS_HASH_BOUND_SOURCE_PACKET_AND_INVENTORY",
            "files_verified": len(files),
            "source_inventory_rederived": True,
            "observer_reexecuted_by_this_verifier": False,
            "physical_evaluations": 0, "prepared": False,
            "scientifically_validated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.v1.json").read_text())
    root = args.bundle_root or Path(manifest["bundle_root_hint"])
    print(json.dumps(verify(manifest, root)))


if __name__ == "__main__":
    main()
