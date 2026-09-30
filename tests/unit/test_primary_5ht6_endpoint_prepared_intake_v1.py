"""Current public intake and inert mutation tests; no external source or physics."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.product import primary_5ht6_endpoint_prepared_intake_v1 as intake


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def documents():
    return intake.load_inputs(ROOT)


@pytest.fixture
def packet(documents):
    return intake._audit_documents(documents)


def test_actual_78_row_audit_preserves_all_missing_inputs_and_separate_linkage(packet):
    summary = packet["summary"]
    assert (summary["requested_rows"], summary["audited_rows"], summary["proposed_source_graph_metadata_rows"],
            summary["declared_prepared_model_link_rows"], summary["experimentally_confirmed_link_rows"]) == (78, 78, 3, 2, 0)
    assert summary["blocked_intake_rows"] == 78
    assert summary["documentation_complete_rows"] == 0
    assert summary["independent_measurement_denominator"] is None
    assert summary["new_independent_measurements_credited"] == 0
    for field in ("raw_concentration_replicates", "per_row_experiment_N", "assayed_batch", "target_construct", "binding_buffer_pH"):
        assert summary["status_counts_by_requirement"][field] == {"missing": 78}
    assert summary["status_counts_by_requirement"]["declared_prepared_model_link"] == {"missing": 76, "present": 2}
    assert packet["prior_representation_denominators"]["matched_repeat_report_links"] == 6
    assert set(packet["retained_source_disputes"]) == {"PR9", "PR39", "PR65_PR66", "PR109", "PR78_PR77"}
    rows = {row["printed_label"]: row for row in packet["rows"]}
    assert rows["PR58"]["proposed_source_identity"] is not None
    assert rows["PR58"]["declared_model"] is None
    assert rows["PR9"]["requirements"]["endpoint_value_resolution"]["status"] == "unresolved"
    assert all(row["assigned_role"] is None and row["training_admitted"] is False for row in rows.values())
    assert packet["boundary"]["goal_1_complete"] is False


def test_assumed_microstate_model_is_submittable_without_wet_assay_equality(packet):
    model = deepcopy(next(row["declared_model"] for row in packet["rows"] if row["declared_model"] is not None))
    model["model_id"] = "synthetic-assumed-microstate"
    model["linkage_scope"] = "caller_declared_assumed_model"
    model["formal_charge"] = 1
    model["assumptions"]["protonation"] = "Explicit hypothetical positive microstate for metadata review"
    verdict = intake.validate_declared_model(model)
    assert verdict["metadata_valid"] is True
    assert verdict["declared_model_submittable"] is True
    assert verdict["experimentally_confirmed_linkage"] is False
    assert verdict["role_admission_issued"] is False


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d["endpoint"]["endpoint_transcriptions"].pop(), "endpoint_denominator_or_membership_changed"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"].append(deepcopy(d["endpoint"]["endpoint_transcriptions"][0])), "duplicate_endpoint"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"][0].update(endpoint="functional_KB"), "endpoint_role_target_or_label_changed"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"][0].update(binary_label="inactive"), "endpoint_role_target_or_label_changed"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"][0]["reported_summary"].update(relation=">"), "endpoint_summary_changed"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"][0]["censoring"].update(inactivity_imputed=True), "missingness_or_censoring_reclassified"),
    (lambda d: d["endpoint"]["assay_method"].update(per_row_experiment_N=2), "missing_laboratory_metadata_promoted"),
    (lambda d: d["endpoint"]["assay_method"].update(buffer_pH="7.4"), "missing_laboratory_metadata_promoted"),
    (lambda d: d["endpoint"]["rights_review"].update(intended_use_permission_or_role_decision="approved"), "rights_review_promoted"),
    (lambda d: d["multi_ledger"]["role_policy"].update(fit_rows_admitted=1), "multi_role_authority_promoted"),
    (lambda d: d["endpoint"]["prepared_pair_source_correspondence"].pop(), "prepared_pair_membership_changed"),
    (lambda d: d["endpoint"]["prepared_pair_source_correspondence"][0].update(source_graph_assayed_batch_correspondence_verified=True), "prepared_assay_linkage_promoted"),
    (lambda d: d["endpoint"]["prepared_pair_source_correspondence"][0].update(chemical_identity_relation="same_PR_label"), "declared_prepared_identity_or_endpoint_disagreement"),
    (lambda d: d["endpoint"]["prepared_pair_source_correspondence"][0]["chemical_identity"].update(canonical_isomeric_smiles_sha256="0" * 64), "declared_prepared_identity_or_endpoint_disagreement"),
    (lambda d: d["endpoint"]["prepared_pair_source_correspondence"][0]["reported_binding_Ki"].update(mean="1"), "declared_prepared_identity_or_endpoint_disagreement"),
])
def test_current_input_semantic_mutations_fail_closed(documents, mutation, code):
    mutation(documents)
    with pytest.raises(ValueError, match=code):
        intake._audit_documents(documents)


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["boundary"].update(training_admitted=True), "intake_authority_promoted"),
    (lambda p: p["rows"].pop(), "requested_intake_denominator_changed"),
    (lambda p: p["rows"][0].update(assigned_role="evaluation"), "intake_row_admission_promoted"),
    (lambda p: p["rows"][0].update(experimentally_confirmed_linkage=True), "intake_row_admission_promoted"),
    (lambda p: p["rows"][0].update(documentation_complete=True), "documentation_completeness_changed"),
    (lambda p: p["rows"][0]["blockers"].clear(), "missing_or_unresolved_blocker_dropped"),
    (lambda p: p["rows"][0]["endpoint_report"].update(endpoint="cytotoxicity_IC50"), "intake_endpoint_reclassified"),
    (lambda p: p["rows"][0]["requirements"].pop("raw_concentration_replicates"), "requirement_set_changed"),
    (lambda p: p["summary"].update(independent_measurement_denominator=78), "intake_summary_promoted_or_denominator_changed"),
    (lambda p: p["retained_source_disputes"].pop("PR39"), "source_disputes_dropped"),
])
def test_frozen_intake_cannot_hide_missing_evidence_or_promote_roles(packet, mutation, code):
    mutation(packet)
    with pytest.raises(ValueError, match=code):
        intake.validate_current_record(packet)


@pytest.mark.parametrize("flag", [False, None, 1])
def test_current_metadata_valid_flag_cannot_contradict_verified_row_contract(packet, flag):
    packet["rows"][0]["metadata_valid"] = flag
    with pytest.raises(ValueError, match="metadata_valid_flag_changed"):
        intake.validate_current_record(packet)


@pytest.mark.parametrize("field", [
    "requested_rows", "audited_rows", "metadata_valid_rows", "documentation_complete_rows",
    "proposed_source_graph_metadata_rows", "declared_prepared_model_link_rows",
    "experimentally_confirmed_link_rows", "rows_with_identity_dispute", "unresolved_endpoint_value_rows",
    "blocked_intake_rows", "failed_required_row_reconciliations", "new_independent_measurements_credited",
])
def test_every_numeric_summary_counter_is_recomputed_from_validated_rows(packet, field):
    packet["summary"][field] += 1
    with pytest.raises(ValueError, match="intake_summary_promoted_or_denominator_changed"):
        intake.validate_current_record(packet)


def test_requirement_status_counts_cannot_drop_or_reclassify_missing_rows(packet):
    packet["summary"]["status_counts_by_requirement"]["raw_concentration_replicates"] = {"present": 78}
    with pytest.raises(ValueError, match="intake_summary_promoted_or_denominator_changed"):
        intake.validate_current_record(packet)


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["rows"][0].update(documentation_complete=0), "documentation_completeness_changed"),
    (lambda p: p["rows"][0].update(declared_model_linked=True), "model_linkage_flag_changed"),
    (lambda p: next(row for row in p["rows"] if row["declared_model"] is not None).update(declared_model_linked=False), "model_linkage_flag_changed"),
    (lambda p: p["summary"].update(documentation_complete_rows=False), "intake_summary_promoted_or_denominator_changed"),
    (lambda p: p["summary"].pop("metadata_valid_rows"), "intake_summary_promoted_or_denominator_changed"),
])
def test_flags_and_summary_types_cannot_mask_contradictory_metadata(packet, mutation, code):
    mutation(packet)
    with pytest.raises(ValueError, match=code):
        intake.validate_current_record(packet)


def test_external_reference_paths_are_not_opened(documents):
    for pair in documents["endpoint"]["prepared_pair_source_correspondence"]:
        for field in ("source", "prepared_evidence", "original_request"):
            pair[field]["path"] = "/unavailable/protected/original-body"
    assert intake._audit_documents(documents)["summary"]["declared_prepared_model_link_rows"] == 2


def test_proposed_graph_cannot_become_assayed_identity(packet):
    row = next(row for row in packet["rows"] if row["proposed_source_identity"] is not None)
    row["proposed_source_identity"]["assayed_chemical_identity_verified"] = True
    with pytest.raises(ValueError, match="proposed_graph_cannot_issue_assayed_identity"):
        intake.validate_current_record(packet)


def test_model_metadata_cannot_issue_experimental_proof(packet):
    model = deepcopy(next(row["declared_model"] for row in packet["rows"] if row["declared_model"] is not None))
    model["experimentally_confirmed_linkage"] = True
    with pytest.raises(ValueError, match="model_metadata_cannot_issue_experimental_linkage"):
        intake.validate_declared_model(model)


def test_current_requirement_anchor_must_resolve_even_if_marked_present_and_complete(packet):
    row = packet["rows"][0]
    for requirement in row["requirements"].values():
        requirement["status"] = "present"
        requirement["evidence_anchor"] = {"artifact": "endpoint", "pointer": "/does-not-exist"}
    row["documentation_complete"] = True
    row["blockers"] = []
    with pytest.raises(ValueError, match="unresolved_metadata_pointer"):
        intake.validate_current_record(packet)


def test_current_null_documented_field_cannot_become_present(packet):
    packet["rows"][0]["requirements"]["per_row_experiment_N"]["status"] = "present"
    with pytest.raises(ValueError, match="present_requirement_has_null_evidence"):
        intake.validate_current_record(packet)


def _submission(packet, status):
    model = deepcopy(next(row["declared_model"] for row in packet["rows"] if row["declared_model"] is not None))
    evidence = {"declared": {"items": {key: {"submitted_statement": "Synthetic metadata coverage, unverified"}
                                       for key in intake.REQUIREMENTS},
                             "external_path": "/unavailable/protected/body"}}
    return {"schema_id": intake.SCHEMA + "/submission_metadata", "metadata_evidence": evidence,
            "requirements": {key: {"status": status, "detail": "Synthetic metadata status for contract verification",
                                   "evidence_anchor": {"artifact": "declared", "pointer": "/items/" + key}
                                   if status == "present" else None} for key in intake.REQUIREMENTS},
            "declared_model": model}


def test_inline_documentation_can_be_complete_without_source_wet_or_role_authority(packet):
    verdict = intake.validate_submission_metadata(_submission(packet, "present"))
    assert verdict["metadata_valid"] is True
    assert verdict["documentation_complete"] is True
    assert verdict["source_authenticity_verified"] is False
    assert verdict["experimentally_confirmed_linkage"] is False
    assert verdict["role_admission_issued"] is False
    assert verdict["assay_documentation_coverage_is_not_a_numerical_execution_gate"] is True


def test_missing_assay_documentation_does_not_invalidate_declared_model_metadata(packet):
    verdict = intake.validate_submission_metadata(_submission(packet, "missing"))
    assert verdict["documentation_complete"] is False
    assert verdict["documentation_status_counts"] == {"missing": 17}
    assert verdict["declared_model_verdict"]["declared_model_submittable"] is True


@pytest.mark.parametrize("anchor", [None, {"artifact": "not-inline", "pointer": "/items"},
                                   {"artifact": "declared", "pointer": "/does-not-exist"}])
def test_inline_present_requirement_requires_resolvable_supplied_evidence(packet, anchor):
    submission = _submission(packet, "present")
    submission["requirements"]["per_row_experiment_N"]["evidence_anchor"] = anchor
    with pytest.raises(ValueError):
        intake.validate_submission_metadata(submission)


def test_inline_null_and_malformed_array_pointers_are_not_coverage(packet):
    submission = _submission(packet, "present")
    submission["metadata_evidence"]["declared"]["items"]["per_row_experiment_N"] = None
    with pytest.raises(ValueError, match="present_requirement_has_null_evidence"):
        intake.validate_submission_metadata(submission)
    assert intake._resolve_pointer({"a/b": {"~": ["value"]}}, "/a~1b/~0/0") == "value"
    for pointer in ("/items/00", "/items/-", "/items/2", "/items/~2"):
        with pytest.raises(ValueError):
            intake._resolve_pointer({"items": [1]}, pointer)


def test_self_contained_submission_cli_does_not_load_repository_or_external_bodies(tmp_path, packet):
    raw = intake.cross.canonical_bytes(_submission(packet, "missing"))
    path = tmp_path / "inline-metadata.json"
    path.write_bytes(raw)
    checked = subprocess.run([sys.executable, "-B", str(ROOT / "tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py"),
                              "--repo-root", str(tmp_path / "nonexistent-repo"), "--submission-metadata", str(path),
                              "--submission-sha256", hashlib.sha256(raw).hexdigest()], capture_output=True, check=True)
    result = json.loads(checked.stdout)
    assert result["verdict"]["declared_model_verdict"]["declared_model_submittable"] is True
    assert result["verdict"]["documentation_complete"] is False
    assert result["boundary"]["external_reference_bodies_opened"] is False


def test_actual_record_rebuild_and_semantic_drift_rejection(tmp_path):
    expected = intake.cross.canonical_bytes(intake.audit_current(ROOT))
    assert (ROOT / intake.OUTPUT).read_bytes() == expected
    assert intake.verify_record(ROOT, ROOT / intake.OUTPUT)["record_sha256"] == hashlib.sha256(expected).hexdigest()
    mutant = json.loads(expected)
    mutant["rows"][0]["requirements"]["raw_concentration_replicates"]["status"] = "present"
    path = tmp_path / "mutant.json"
    path.write_bytes(intake.cross.canonical_bytes(mutant))
    with pytest.raises(ValueError, match="fixed_intake_record_drift"):
        intake.verify_record(ROOT, path)


def test_absent_fixed_inputs_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        intake.load_inputs(tmp_path)


def test_real_cli_and_explicit_assumed_model_metadata_cli(tmp_path, packet):
    entry = ROOT / "tools/verify_primary_5ht6_endpoint_prepared_intake_v1.py"
    checked = subprocess.run([sys.executable, "-B", str(entry), "--repo-root", str(ROOT),
                              "--verify-record", str(ROOT / intake.OUTPUT)], capture_output=True, check=True)
    assert json.loads(checked.stdout)["summary"]["audited_rows"] == 78
    model = next(row["declared_model"] for row in packet["rows"] if row["declared_model"] is not None)
    raw = intake.cross.canonical_bytes(model)
    path = tmp_path / "assumed-model-metadata.json"
    path.write_bytes(raw)
    checked = subprocess.run([sys.executable, "-B", str(entry), "--repo-root", str(ROOT),
                              "--declared-model", str(path), "--model-sha256", hashlib.sha256(raw).hexdigest()],
                             capture_output=True, check=True)
    assert json.loads(checked.stdout)["verdict"]["declared_model_submittable"] is True
    failed = subprocess.run([sys.executable, "-B", str(entry), "--repo-root", str(ROOT),
                             "--declared-model", str(path), "--model-sha256", "0" * 64], capture_output=True)
    assert failed.returncode == 1
    assert json.loads(failed.stderr)["successful_intake_audit_established"] is False
