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
    require(manifest["schema_version"] == SCHEMA and manifest["status"] == STATUS,
            "unexpected_schema_or_status")
    sources = manifest["source_refs"]
    require(set(sources) == {
        "pdb_3mxf", "pdb_3mxf_validation", "ccd_jq1", "filippakopoulos_2010",
        "tanaka_2016", "tanaka_2016_supplement", "pubchem_s_jq1",
        "pubchem_r_jq1", "pdb_usage_policy"}, "unexpected_source_refs")
    require(all(ref["url"].startswith("https://") for ref in sources.values()),
            "non_https_source")
    require(sources["pdb_3mxf"]["download_url"] ==
            "https://files.rcsb.org/download/3MXF.cif", "structure_source_changed")
    require(sources["tanaka_2016"]["doi"] == "10.1038/nchembio.2209" and
            sources["tanaka_2016"]["pmid"] == "27775715" and
            sources["tanaka_2016_supplement"]["direct_file_access_verified"] is False,
            "assay_source_changed_or_access_overclaimed")

    structure = manifest["structure_observation"]
    require(structure["pdb_id"] == "3MXF" and structure["protein_label_chain"] == "A"
            and structure["modelled_residue_range"] == "42-168"
            and structure["deposited_ligand_ccd"] == "JQ1"
            and structure["deposited_ligand_stereochemistry"] == "6S",
            "structure_identity_changed")
    assay = manifest["experimental_observation"]
    require(assay["endpoint"] == "IC50" and
            assay["endpoint_subtype"] ==
            "BRD4_BD1_AlphaScreen_competitive_inhibition_IC50" and
            assay["assay_protein_concentration_nM"] == 20 and
            "44-168" in assay["assay_construct"], "assay_context_changed")
    require(assay["measurements"] == [
        {"compound": "(S)-(+)-JQ1", "pubchem_cid": 46907787,
         "operator": "=", "value_nM": 21, "censored": False,
         "reported_interpretation": "active"},
        {"compound": "(R)-(-)-JQ1", "pubchem_cid": 49871818,
         "operator": ">", "value_nM": 5000, "censored": True,
         "reported_interpretation": "inactive_at_tested_concentrations"}],
            "measurements_or_censoring_changed")

    boundaries = manifest["comparison_boundaries"]
    require(boundaries["same_assay_ic50_contrast_observed"] is True and
            boundaries["r_enantiomer_source_bound_stereochemical_identity_recorded"] is True,
            "observed_source_pair_changed")
    require(all(value is False for key, value in boundaries.items()
                if key not in {"same_assay_ic50_contrast_observed",
                               "r_enantiomer_source_bound_stereochemical_identity_recorded",
                               "common_core_residues_44_168_source_consistent"}),
            "unresolved_comparison_boundary_overclaimed")
    require(boundaries["common_core_residues_44_168_source_consistent"] is True,
            "common_core_observation_changed")
    require(all(value is False for value in manifest["eligibility"].values()),
            "eligibility_must_remain_false")
    roles = manifest["protection_and_roles"]
    require(roles["protected_outcomes_accessed"] is False and
            roles["identity_component_and_reservation_screen_completed"] is False and
            roles["source_rights_use_specific_review_completed"] is False and
            all(roles[key] is None for key in (
                "source_component_role", "fit_role", "calibration_role", "evaluation_role")),
            "roles_or_rights_overclaimed")
    actions = manifest["performed_actions"]
    require(actions["public_source_metadata_reviewed"] is True and
            all(actions[key] is False for key in (
                "receptor_prepared", "s_ligand_prepared", "r_ligand_prepared",
                "fit_or_evaluation_roles_assigned", "protected_evaluation_access")) and
            actions["physical_evaluations"] == 0,
            "non_static_action_claimed")
    decisions = manifest["unresolved_decisions"]
    require(len(decisions) == 7 and
            len({item["id"] for item in decisions}) == 7 and
            all(item["status"] == "unresolved" for item in decisions),
            "decision_set_or_status_changed")

    receipts = manifest["source_file_receipts"]
    structural_sources = {"pdb_3mxf", "ccd_jq1", "pdb_3mxf_validation"}
    require(type(receipts) is list and len(receipts) == 3 and
            actions["source_files_downloaded"] is True and
            {item["source_ref"] for item in receipts} == structural_sources,
            "structural_source_receipts_incomplete_or_unexpected")
    seen = set()
    source_root = (ROOT / "official_sources").resolve()
    for receipt in receipts:
        require(set(receipt) == {
            "source_ref", "source_url", "relative_path", "size_bytes", "sha256"
        } and receipt["source_ref"] in structural_sources and
            receipt["source_url"] == sources[receipt["source_ref"]]["download_url"],
            "invalid_source_receipt_or_url")
        relative = PurePosixPath(receipt["relative_path"])
        require(not relative.is_absolute() and relative.parts
                and relative.parts[0] == "official_sources"
                and ".." not in relative.parts and
                str(relative) == receipt["relative_path"] and
                receipt["relative_path"] not in seen, "invalid_source_path")
        seen.add(receipt["relative_path"])
        require(type(receipt["size_bytes"]) is int and receipt["size_bytes"] > 0,
                "invalid_source_size")
        require(re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) is not None,
                "invalid_source_hash")
        path = (ROOT / receipt["relative_path"]).resolve()
        require(path.is_relative_to(source_root) and path.is_file(),
                "source_file_missing_or_outside_packet")
        require(path.stat().st_size == receipt["size_bytes"], "source_size_mismatch")
        require(sha256(path) == receipt["sha256"], "source_hash_mismatch")
    return len(receipts)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"),
                          object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    count = validate(manifest)
    print(json.dumps({
        "status": "PASS_STATIC_SOURCE_CANDIDATE_BLOCKED",
        "source_files_verified": count,
        "scientific_admission": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
