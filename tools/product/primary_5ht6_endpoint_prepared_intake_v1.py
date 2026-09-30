"""Audit public endpoint-to-prepared-model evidence; never issue admission.

Metadata validity, documentation completeness, declared computational linkage,
experimental linkage, and dataset-role authorization are separate dimensions.
Only fixed repository public transcriptions are read. External references are
not followed, and molecular/assay calculations are not imported or performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

from tools.product import primary_5ht6_2024_cross_artifact_reconciliation_v1 as cross


SCHEMA = "human_5ht6_endpoint_prepared_intake/1"
OUTPUT = "docs/evidence/primary_5ht6_endpoint_prepared_intake_20260930_v1.json"
INPUTS = {
    "endpoint": cross.INPUTS["endpoint"],
    "source_ledger": ("docs/evidence/human_5ht6_ki_2024_source_ledger_v1.json", 3005,
                      "277f62f7cad26e85f4401aa4e53cfe5992da19dddec692500b7b552d21d33189"),
    "multi_ledger": ("docs/evidence/human_5ht6_ki_multi_paper_source_ledger_v1.json", 27675,
                     "e5b5af4caa0e4efa3e5e3a502236357276051044431f45bda77b8b5163ca0452"),
    "reconciliation": (cross.OUTPUT, 316336,
                       "509a9fd926c2ac785d1f972791553d4c836255fa5f8a634d1c040eee357d5dbd"),
    "endpoint_report": ("docs/research/human_5ht6_endpoint_admission_next_20260930.md", 10121,
                        "c310161ab12b5aa1d55ba59383f4ab0e26e9133dcae0f813edc8e7d6608dcc9d"),
    "multi_report": ("docs/research/human_5ht6_ki_multi_paper_intake_v1.md", 8115,
                     "004a2bc103239a488b9deb82b542916055de02d880cfc6208ce260d50c512e2f"),
}
BOUNDARY = {
    "assigned_role": None, "source_authenticated": False,
    "experimentally_confirmed_linkage": False, "same_prepared_assay_state_verified": False,
    "independent_measurement_denominator": None, "new_independent_measurements_credited": 0,
    "training_admitted": False, "calibration_admitted": False,
    "independent_evaluation_admitted": False, "scientifically_qualified": False,
    "goal_1_complete": False, "protected_context_opened": False,
    "external_reference_bodies_opened": False, "molecular_runtime_executed": False,
    "new_preflight_executed": False, "original_artifacts_rewritten": False,
}
REQUIREMENTS = {
    "raw_concentration_replicates": "Per-experiment concentration responses, repeats and controls",
    "per_row_experiment_N": "Exact independent-experiment count for this reported row",
    "assayed_batch": "Tested sample/batch identity and formulation",
    "assayed_microstate": "Tested salt, protonation, tautomer and stereochemical state",
    "target_construct": "Exact assayed receptor construct sequence/variant",
    "binding_buffer_pH": "Actual receptor-binding buffer pH",
    "source_license_notice": "Source copyright/license and attribution notice",
    "rights_exceptions_intended_use": "Material exceptions and explicit intended-use review",
    "source_family_lineage": "Complete source-family, identity and reuse correspondence",
    "independent_measurement_origin": "Row-specific new measurement versus reused report origin",
    "proposed_source_identity": "Declared proposed source graph; does not verify assayed identity",
    "declared_prepared_model_link": "Audited or submitted declared computational model correspondence",
    "sample_to_prepared_state_link": "Evidence relating tested sample state to declared numerical model",
    "endpoint_value_resolution": "Unresolved table/prose conflicts preserved before value precedence",
    "train_role_review": "Separate sanctioned train-role review/decision artifact",
    "calibration_role_review": "Separate sanctioned calibration-role review/decision artifact",
    "evaluation_role_review": "Separate sanctioned evaluation-role review/decision artifact",
}
MODEL_RELATION = "same_proposed_neutral_graph_as_declared_prepared_source_descriptor"


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _fields(value, keys, code):
    _require(type(value) is dict and set(value) == set(keys), code)


def _sha(token):
    return type(token) is str and re.fullmatch(r"[0-9a-f]{64}", token) is not None


def _resolve_pointer(document, pointer):
    """Resolve RFC 6901 inside supplied JSON only; never follow file references."""
    _require(type(pointer) is str and (pointer == "" or pointer.startswith("/")), "invalid_metadata_pointer")
    value = document
    for token in pointer.split("/")[1:] if pointer else []:
        _require(re.search(r"~(?![01])", token) is None, "invalid_metadata_pointer")
        token = token.replace("~1", "/").replace("~0", "~")
        if type(value) is dict:
            _require(token in value, "unresolved_metadata_pointer:" + pointer)
            value = value[token]
        elif type(value) is list:
            _require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None
                     and int(token) < len(value), "unresolved_metadata_pointer:" + pointer)
            value = value[int(token)]
        else:
            raise ValueError("unresolved_metadata_pointer:" + pointer)
    return value


def _resolve_anchor(anchor, documents):
    _fields(anchor, {"artifact", "pointer"}, "requirement_anchor")
    _require(type(anchor["artifact"]) is str and anchor["artifact"] in documents,
             "requirement_anchor_artifact_unavailable")
    return _resolve_pointer(documents[anchor["artifact"]], anchor["pointer"])


def validate_submission_metadata(submission):
    """Review self-contained metadata coverage, with no authenticity/admission.

    Assay documentation coverage is not a numerical execution prerequisite.
    A valid explicitly assumed model remains submittable with missing assay data.
    """
    _fields(submission, {"schema_id", "metadata_evidence", "requirements", "declared_model"},
            "submission_metadata_shape")
    _require(submission["schema_id"] == SCHEMA + "/submission_metadata", "submission_metadata_schema")
    evidence = submission["metadata_evidence"]
    _require(type(evidence) is dict and all(type(key) is str and bool(key.strip()) for key in evidence),
             "inline_metadata_evidence_shape")
    requirements = submission["requirements"]
    _fields(requirements, REQUIREMENTS, "requirement_set_changed")
    for requirement in requirements.values():
        _fields(requirement, {"status", "evidence_anchor", "detail"}, "requirement_shape")
        _require(requirement["status"] in {"present", "missing", "unresolved"}
                 and type(requirement["detail"]) is str and bool(requirement["detail"].strip()), "requirement_status")
        anchor = requirement["evidence_anchor"]
        if anchor is None:
            _require(requirement["status"] != "present", "present_requirement_needs_inline_anchor")
        else:
            value = _resolve_anchor(anchor, evidence)
            _require(requirement["status"] != "present" or value is not None,
                     "present_requirement_has_null_evidence")
    model = submission["declared_model"]
    model_verdict = validate_declared_model(model) if model is not None else None
    return {"metadata_valid": True,
            "documentation_complete": all(x["status"] == "present" for x in requirements.values()),
            "documentation_status_counts": dict(sorted(Counter(x["status"] for x in requirements.values()).items())),
            "declared_model_verdict": model_verdict,
            "assay_documentation_coverage_is_not_a_numerical_execution_gate": True,
            "source_authenticity_verified": False, "experimentally_confirmed_linkage": False,
            "role_admission_issued": False}


def load_inputs(repo_root):
    root = Path(repo_root).resolve(strict=True)
    result = {}
    for name, (relative, size, digest) in INPUTS.items():
        path = root / relative
        _require(path.resolve(strict=True) == path.absolute(), "noncanonical_input:" + name)
        raw = cross._regular_bytes(path, size)
        _require(len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
                 "fixed_input_pin_mismatch:" + name)
        if relative.endswith(".json"):
            result[name] = cross._strict_json(raw)
    # This repeats only the seven fixed public transcription/report pins; it
    # never follows the metadata's original request/source/reference paths.
    cross.verify_record(root, root / cross.OUTPUT)
    return result


def validate_declared_model(model):
    """Validate assumed-model metadata without requiring wet-assay equivalence.

    Missing laboratory state does not invalidate an explicit computational
    hypothesis. This function verifies shape/consistency, not chemistry/physics.
    """
    _fields(model, {"model_id", "kind", "declared_identity_sha256", "formal_charge",
                    "assumptions", "descriptor_hashes", "linkage_scope",
                    "experimentally_confirmed_linkage"}, "declared_model_shape")
    _require(type(model["model_id"]) is str and bool(model["model_id"])
             and model["kind"] == "assumed_computational_microstate"
             and _sha(model["declared_identity_sha256"])
             and type(model["formal_charge"]) is int, "declared_model_identity")
    _fields(model["assumptions"], {"protonation", "tautomer", "stereochemistry", "receptor_state"},
            "declared_model_assumptions")
    _require(all(type(x) is str and bool(x.strip()) for x in model["assumptions"].values()),
             "declared_model_assumptions")
    _fields(model["descriptor_hashes"], {"source", "prepared", "request"}, "declared_model_descriptor_hashes")
    _require(all(_sha(x) for x in model["descriptor_hashes"].values()), "declared_model_descriptor_hashes")
    _require(model["linkage_scope"] in {MODEL_RELATION, "caller_declared_assumed_model"}
             and model["experimentally_confirmed_linkage"] is False,
             "model_metadata_cannot_issue_experimental_linkage")
    return {"metadata_valid": True, "declared_model_submittable": True,
            "experimentally_confirmed_linkage": False, "role_admission_issued": False}


def _requirement(status, artifact, pointer, detail):
    return {"status": status, "evidence_anchor": {"artifact": artifact, "pointer": pointer},
            "detail": detail}


def _model(pair):
    identity = pair["chemical_identity"]
    model = {
        "model_id": pair["candidate_id"], "kind": "assumed_computational_microstate",
        "declared_identity_sha256": identity["canonical_isomeric_smiles_sha256"],
        "formal_charge": identity["formal_charge"],
        "assumptions": {
            "protonation": "Declared proposed neutral graph; assayed protonation is unknown",
            "tautomer": "Declared computational graph; assayed tautomer is unknown",
            "stereochemistry": "Recorded unspecified stereo count: " + str(identity["stereo_unspecified_count"]),
            "receptor_state": "Declared numerical receptor model; equivalence to the membrane assay is not verified",
        },
        "descriptor_hashes": {key: pair[field]["sha256"] for key, field in
                              (("source", "source"), ("prepared", "prepared_evidence"), ("request", "original_request"))},
        "linkage_scope": pair["chemical_identity_relation"], "experimentally_confirmed_linkage": False,
    }
    validate_declared_model(model)
    return model


def _audit_documents(documents):
    endpoint, source, multi, reconciled = (documents[k] for k in
                                          ("endpoint", "source_ledger", "multi_ledger", "reconciliation"))
    _require(cross._equal(endpoint["boundary"], cross.ENDPOINT_BOUNDARY)
             and cross._equal(reconciled["boundary"], cross.BOUNDARY), "source_authority_promoted")
    _require(all(value is False for value in source["authority"].values()), "source_ledger_authority_promoted")
    _require(all((type(value) is int and value == 0) if key.endswith("_rows_admitted")
                 else value is False for key, value in multi["role_policy"].items()), "multi_role_authority_promoted")
    reports = cross._unique(endpoint["endpoint_transcriptions"], "occurrence_id", "duplicate_endpoint")
    links = cross._unique(reconciled["primary_endpoint_links"], "endpoint_occurrence_id", "duplicate_reconciled_endpoint")
    _require(len(reports) == 78 and set(reports) == set(links)
             and {row["printed_compound_id"] for row in reports.values()} == {f"PR{x}" for x in range(1, 79)},
             "endpoint_denominator_or_membership_changed")
    proposals = cross._unique(source["rows"], "paper_row_id", "duplicate_source_proposal")
    _require(set(proposals) == {"PR49", "PR58", "PR59"}, "source_proposal_membership_changed")
    multi_rows = cross._unique([row for row in multi["rows"] if row["source_component_id"] == "doi:" + cross.DOI],
                               "paper_row_id", "duplicate_multi_source_proposal")
    _require(set(multi_rows) == set(proposals), "multi_source_proposal_membership_changed")
    pairs = cross._unique(endpoint["prepared_pair_source_correspondence"], "occurrence_id", "duplicate_prepared_pair")
    _require(set(pairs) == {"table4:PR49", "table4:PR59"}, "prepared_pair_membership_changed")
    method = endpoint["assay_method"]
    _require(method["raw_repeat_measurements_available"] is False
             and all(method[k] is None for k in ("per_row_experiment_N", "buffer_pH", "construct_sequence")),
             "missing_laboratory_metadata_promoted")
    _require(endpoint["rights_review"]["whole_article_and_supplement_exception_review_complete"] is False
             and endpoint["rights_review"]["intended_use_permission_or_role_decision"] is None,
             "rights_review_promoted")
    rows = []
    for occurrence, report in reports.items():
        label, summary = report["printed_compound_id"], report["reported_summary"]
        _require(report["endpoint"] == "radioligand_binding_Ki"
                 and report["target_context"] == "human_5HT6_reported_by_section_3.2"
                 and report["assigned_role"] is None and report["admitted"] is False
                 and report["binary_label"] is None and report["raw_replicates_available"] is False,
                 "endpoint_role_target_or_label_changed")
        _require(summary["relation"] == "=" and summary["unit"] == "µM"
                 and summary["uncertainty"]["kind"] == "SD"
                 and summary["reported_as_independent_remeasurement"] is False
                 and cross._equal(summary, links[occurrence]["reported_summary"]), "endpoint_summary_changed")
        cross._positive(summary["mean"])
        cross._positive(summary["uncertainty"]["value"])
        _require(report["censoring"]["bound"] is None and report["censoring"]["inactivity_imputed"] is False,
                 "missingness_or_censoring_reclassified")
        proposal = proposals.get(label)
        identity = None
        if proposal:
            other = multi_rows[label]
            _require(proposal["assigned_role"] is None and proposal["fit_admitted"] is False
                     and proposal["prepared_state_origin"] is None
                     and proposal["proposed_neutral_graph"]["assayed_microstate_verified"] is False,
                     "source_proposal_promoted")
            _require(proposal["exact_published_name"] == other["exact_published_name"]
                     and proposal["proposed_neutral_graph"]["canonical_isomeric_smiles"] == other["proposed_neutral_graph"]["canonical_isomeric_smiles"]
                     and proposal["reported_ki_mean"] == other["reported_ki"]["value"] == summary["mean"]
                     and proposal["reported_ki_sd"] == other["reported_ki"]["uncertainty"]["value"] == summary["uncertainty"]["value"],
                     "source_proposal_summary_or_graph_disagreement")
            identity = {"scope": "declared_proposed_source_graph_only", "published_name": proposal["exact_published_name"],
                        "declared_identity_sha256": hashlib.sha256(proposal["proposed_neutral_graph"]["canonical_isomeric_smiles"].encode()).hexdigest(),
                        "assayed_chemical_identity_verified": False}
        pair, model = pairs.get(occurrence), None
        if pair:
            _require(cross._equal(pair["boundary"], cross.ENDPOINT_BOUNDARY)
                     and pair["source_graph_assayed_batch_correspondence_verified"] is False
                     and all(pair[k] is None for k in ("assay_batch_id", "assayed_construct_sequence", "assay_buffer_pH",
                                                     "salt_or_protonation_or_tautomer_assignment")), "prepared_assay_linkage_promoted")
            _require(pair["chemical_identity_relation"] == MODEL_RELATION and identity is not None
                     and pair["exact_published_name"] == identity["published_name"]
                     and pair["chemical_identity"]["canonical_isomeric_smiles_sha256"] == identity["declared_identity_sha256"]
                     and hashlib.sha256(pair["chemical_identity"]["canonical_isomeric_smiles"].encode()).hexdigest() == identity["declared_identity_sha256"]
                     and cross._equal(pair["reported_binding_Ki"], summary), "declared_prepared_identity_or_endpoint_disagreement")
            model = _model(pair)
        requirements = {}
        for field in REQUIREMENTS:
            if field == "source_license_notice":
                status, detail = "present", "Article CC BY notice and proposed attribution; no intended-use or role clearance"
            elif field == "proposed_source_identity":
                status, detail = ("present" if identity else "missing"), "Proposed source graph metadata only; printed PR agreement is not verified chemistry"
            elif field == "declared_prepared_model_link":
                status, detail = ("present" if model else "missing"), "Audited declared model correspondence only; model descriptor bodies are not opened"
            elif field == "sample_to_prepared_state_link":
                status, detail = ("unresolved" if model else "missing"), "No experimentally verified assayed-batch/state to numerical-model equivalence"
            elif field == "endpoint_value_resolution":
                status, detail = ("unresolved" if label == "PR9" else "present"), "PR9 table/prose conflict retained" if label == "PR9" else "The reviewed table summary is retained without assigning admissible value precedence"
            elif field in {"raw_concentration_replicates", "per_row_experiment_N", "assayed_batch", "target_construct", "binding_buffer_pH"}:
                status, detail = "missing", "No row-specific originating-laboratory record in the retained public audit; method-level replication is not per-row N"
            else:
                status, detail = "unresolved", "Separate source/chemical-state/rights/role evidence and review remain required"
            anchors = {
                "raw_concentration_replicates": ("endpoint", "/assay_method/raw_repeat_measurements_available"),
                "per_row_experiment_N": ("endpoint", "/assay_method/per_row_experiment_N"),
                "assayed_batch": ("endpoint", "/smallest_missing_artifacts/3"),
                "assayed_microstate": ("endpoint", "/smallest_missing_artifacts/4"),
                "target_construct": ("endpoint", "/assay_method/construct_sequence"),
                "binding_buffer_pH": ("endpoint", "/assay_method/buffer_pH"),
                "source_license_notice": ("endpoint", "/rights_review/license"),
                "rights_exceptions_intended_use": ("endpoint", "/rights_review/whole_article_and_supplement_exception_review_complete"),
                "source_family_lineage": ("reconciliation", "/unresolved_scope"),
                "independent_measurement_origin": ("endpoint", "/source/independent_measurement_denominator"),
                "proposed_source_identity": ("source_ledger", "/rows"),
                "declared_prepared_model_link": ("endpoint", "/prepared_pair_source_correspondence"),
                "sample_to_prepared_state_link": ("endpoint", "/smallest_missing_artifacts/4"),
                "endpoint_value_resolution": ("endpoint", "/newly_noted_primary_conflicts/0" if label == "PR9" else "/endpoint_transcriptions/" + str(len(rows))),
                "train_role_review": ("multi_ledger", "/role_policy/roles_frozen"),
                "calibration_role_review": ("multi_ledger", "/role_policy/roles_frozen"),
                "evaluation_role_review": ("multi_ledger", "/role_policy/roles_frozen"),
            }
            artifact, pointer = anchors[field]
            requirements[field] = _requirement(status, artifact, pointer, detail)
        rows.append({"occurrence_id": occurrence, "printed_label": label,
                     "endpoint_report": {key: deepcopy(report[key]) for key in
                                         ("endpoint", "target_context", "reported_summary", "censoring", "source_origin", "binary_label", "identity_issue")},
                     "proposed_source_identity": identity, "declared_model": model,
                     "requirements": requirements,
                     "metadata_valid": True, "documentation_complete": False,
                     "declared_model_linked": model is not None, "experimentally_confirmed_linkage": False,
                     "assigned_role": None, "training_admitted": False, "calibration_admitted": False,
                     "independent_evaluation_admitted": False,
                     "blockers": [key + ":" + value["status"] for key, value in requirements.items() if value["status"] != "present"]})
    packet = {"schema_id": SCHEMA, "status": "PASS_current_public_intake_audit_only",
              "source_doi": cross.DOI,
              "contract": {"statuses": ["present", "missing", "unresolved"], "requirements": REQUIREMENTS,
                           "present_means": "Reviewed metadata supplies the stated scoped item, not scientific truth or admission",
                           "metadata_anchors_resolved_within_fixed_public_inputs": True,
                           "assay_documentation_coverage_is_not_a_numerical_execution_gate": True,
                           "metadata_validity_is_separate_from_completeness_model_linkage_experimental_linkage_and_roles": True},
              "input_pins": {name: {"path": path, "bytes": size, "sha256": sha} for name, (path, size, sha) in INPUTS.items()},
              "requested_occurrence_ids": list(reports), "rows": rows,
              "retained_source_disputes": deepcopy(reconciled["retained_disputes"]),
              "prior_representation_denominators": deepcopy(reconciled["denominators"]),
              "source_scope": {"assay_method_as_reported": deepcopy(method), "rights_as_reviewed": deepcopy(endpoint["rights_review"]),
                               "unresolved_scope": deepcopy(reconciled["unresolved_scope"]),
                               "exposed_public_summaries_are_not_new_unseen_holdout": True,
                               "numeric_cutoff_or_activity_reclassification_performed": False},
              "summary": {"requested_rows": 78, "audited_rows": len(rows), "metadata_valid_rows": len(rows),
                          "documentation_complete_rows": 0, "proposed_source_graph_metadata_rows": sum(x["proposed_source_identity"] is not None for x in rows),
                          "declared_prepared_model_link_rows": sum(x["declared_model_linked"] for x in rows),
                          "experimentally_confirmed_link_rows": 0, "rows_with_identity_dispute": sum(x["endpoint_report"]["identity_issue"] is not None for x in rows),
                          "unresolved_endpoint_value_rows": 1, "blocked_intake_rows": len(rows), "failed_required_row_reconciliations": 0,
                          "status_counts_by_requirement": {key: dict(sorted(Counter(x["requirements"][key]["status"] for x in rows).items())) for key in REQUIREMENTS},
                          "new_independent_measurements_credited": 0, "independent_measurement_denominator": None},
              "boundary": deepcopy(BOUNDARY)}
    validate_current_record(packet, documents)
    return packet


def validate_current_record(packet, documents=None):
    """Validate the fixed current record; declared models need no wet-state proof."""
    _require(packet["schema_id"] == SCHEMA and cross._equal(packet["boundary"], BOUNDARY), "intake_authority_promoted")
    rows = cross._unique(packet["rows"], "occurrence_id", "duplicate_intake_row")
    requested = packet["requested_occurrence_ids"]
    _require(type(requested) is list and len(set(requested)) == len(requested) == 78
             and set(rows) == set(requested), "requested_intake_denominator_changed")
    if documents is None:
        documents = load_inputs(Path(__file__).resolve().parents[2])
    for row in rows.values():
        _fields(row, {"occurrence_id", "printed_label", "endpoint_report", "proposed_source_identity", "declared_model",
                      "requirements", "metadata_valid", "documentation_complete", "declared_model_linked",
                      "experimentally_confirmed_linkage", "assigned_role", "training_admitted", "calibration_admitted",
                      "independent_evaluation_admitted", "blockers"}, "intake_row_shape")
        _require(row["metadata_valid"] is True, "metadata_valid_flag_changed")
        report = row["endpoint_report"]
        _require(report["endpoint"] == "radioligand_binding_Ki"
                 and report["target_context"] == "human_5HT6_reported_by_section_3.2"
                 and report["binary_label"] is None and report["reported_summary"]["relation"] == "="
                 and report["reported_summary"]["unit"] == "µM"
                 and report["reported_summary"]["uncertainty"]["kind"] == "SD"
                 and report["censoring"]["bound"] is None
                 and report["censoring"]["inactivity_imputed"] is False, "intake_endpoint_reclassified")
        _require(set(row["requirements"]) == set(REQUIREMENTS), "requirement_set_changed")
        for requirement in row["requirements"].values():
            _fields(requirement, {"status", "evidence_anchor", "detail"}, "requirement_shape")
            _require(requirement["status"] in {"present", "missing", "unresolved"}
                     and bool(requirement["detail"]), "requirement_status")
            _require(requirement["evidence_anchor"]["artifact"] in INPUTS, "requirement_anchor")
            value = _resolve_anchor(requirement["evidence_anchor"], documents)
            _require(requirement["status"] != "present" or value is not None,
                     "present_requirement_has_null_evidence")
        _require(row["assigned_role"] is None and all(row[key] is False for key in
                 ("training_admitted", "calibration_admitted", "independent_evaluation_admitted", "experimentally_confirmed_linkage")),
                 "intake_row_admission_promoted")
        _require(row["documentation_complete"] is all(x["status"] == "present" for x in row["requirements"].values()),
                 "documentation_completeness_changed")
        if row["declared_model"] is not None:
            validate_declared_model(row["declared_model"])
        _require(row["declared_model_linked"] is (row["declared_model"] is not None), "model_linkage_flag_changed")
        _require(row["requirements"]["declared_prepared_model_link"]["status"] == (
                     "present" if row["declared_model"] is not None else "missing")
                 and row["requirements"]["proposed_source_identity"]["status"] == (
                     "present" if row["proposed_source_identity"] is not None else "missing"), "model_or_identity_evidence_status_changed")
        if row["proposed_source_identity"] is not None:
            _require(row["proposed_source_identity"]["assayed_chemical_identity_verified"] is False,
                     "proposed_graph_cannot_issue_assayed_identity")
        _require(row["blockers"] == [key + ":" + value["status"] for key, value in row["requirements"].items() if value["status"] != "present"],
                 "missing_or_unresolved_blocker_dropped")
    _require(set(packet["retained_source_disputes"]) == {"PR9", "PR39", "PR65_PR66", "PR109", "PR78_PR77"}, "source_disputes_dropped")
    values = list(rows.values())
    expected_summary = {
        "requested_rows": len(requested), "audited_rows": len(values),
        "metadata_valid_rows": sum(row["metadata_valid"] for row in values),
        "documentation_complete_rows": sum(row["documentation_complete"] for row in values),
        "proposed_source_graph_metadata_rows": sum(row["proposed_source_identity"] is not None for row in values),
        "declared_prepared_model_link_rows": sum(row["declared_model_linked"] for row in values),
        "experimentally_confirmed_link_rows": sum(row["experimentally_confirmed_linkage"] for row in values),
        "rows_with_identity_dispute": sum(row["endpoint_report"]["identity_issue"] is not None for row in values),
        "unresolved_endpoint_value_rows": sum(row["requirements"]["endpoint_value_resolution"]["status"] == "unresolved" for row in values),
        "blocked_intake_rows": sum(bool(row["blockers"]) for row in values),
        "failed_required_row_reconciliations": 0,
        "status_counts_by_requirement": {key: dict(sorted(Counter(row["requirements"][key]["status"] for row in values).items()))
                                         for key in REQUIREMENTS},
        "new_independent_measurements_credited": 0, "independent_measurement_denominator": None,
    }
    _require(cross._equal(packet["summary"], expected_summary),
             "intake_summary_promoted_or_denominator_changed")
    return True


def audit_current(repo_root):
    return _audit_documents(load_inputs(repo_root))


def verify_record(repo_root, path):
    raw = cross._regular_bytes(Path(path), 2 * 1024 * 1024)
    expected = cross.canonical_bytes(audit_current(repo_root))
    _require(raw == expected, "fixed_intake_record_drift")
    return {"schema_id": SCHEMA + "/verification", "status": "PASS_fixed_current_public_intake_record",
            "record_sha256": hashlib.sha256(raw).hexdigest(), "record_bytes": len(raw),
            "summary": cross._strict_json(raw)["summary"], "boundary": deepcopy(BOUNDARY)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--verify-record", type=Path)
    parser.add_argument("--declared-model", type=Path, help="Explicit caller metadata only; no source/body references followed")
    parser.add_argument("--model-sha256")
    parser.add_argument("--submission-metadata", type=Path, help="Self-contained inline metadata evidence; no external bodies opened")
    parser.add_argument("--submission-sha256")
    args = parser.parse_args(argv)
    if args.declared_model and (args.verify_record or not args.model_sha256):
        parser.error("--declared-model needs --model-sha256 and cannot be combined with --verify-record")
    if args.submission_metadata and (args.verify_record or args.declared_model or not args.submission_sha256):
        parser.error("--submission-metadata needs --submission-sha256 and cannot be combined with other modes")
    try:
        if args.submission_metadata:
            _require(_sha(args.submission_sha256), "submission_caller_pin_required")
            raw = cross._regular_bytes(args.submission_metadata, 2 * 1024 * 1024)
            _require(hashlib.sha256(raw).hexdigest() == args.submission_sha256, "submission_caller_pin_mismatch")
            verdict = validate_submission_metadata(cross._strict_json(raw))
            result = {"schema_id": SCHEMA + "/submission_metadata_verification",
                      "status": "PASS_inline_metadata_documentation_only",
                      "caller_submission_sha256": args.submission_sha256, "verdict": verdict,
                      "boundary": deepcopy(BOUNDARY)}
        elif args.declared_model:
            _require(_sha(args.model_sha256), "model_caller_pin_required")
            raw = cross._regular_bytes(args.declared_model, 64 * 1024)
            _require(hashlib.sha256(raw).hexdigest() == args.model_sha256, "model_caller_pin_mismatch")
            verdict = validate_declared_model(cross._strict_json(raw))
            result = {"schema_id": SCHEMA + "/declared_model_metadata", "status": "PASS_declared_assumed_model_metadata_only",
                      "caller_model_sha256": args.model_sha256, "verdict": verdict, "boundary": deepcopy(BOUNDARY)}
        else:
            result = verify_record(args.repo_root, args.verify_record) if args.verify_record else audit_current(args.repo_root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({"schema_id": SCHEMA + "/failure", "status": "FAIL_closed", "error": str(exc),
                          "requested_rows": 78, "successful_intake_audit_established": False,
                          "boundary": BOUNDARY}, ensure_ascii=False), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(cross.canonical_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
