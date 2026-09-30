"""Inert mutations of audited public transcriptions; no external source/runtime.

The fixed baseline contains already public reported summaries. Synthetic changes
are applied only to in-memory copies and never admitted or written over sources.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.product import primary_5ht6_2024_cross_artifact_reconciliation_v1 as audit


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def documents():
    return audit.load_inputs(ROOT)


def _primary(d, label="PR9"):
    return next(x for x in d["main"]["occurrences"] if x["relation"] == "reported_primary" and x["entity"] == label)


def _endpoint(d, label="PR9"):
    return next(x for x in d["endpoint"]["endpoint_transcriptions"] if x["printed_compound_id"] == label)


def _table(d, printed="PR 59"):
    return next(x for x in d["supplement"]["occurrences"] if x["printed_name"] == printed)


def test_actual_transcription_reconciliation_preserves_separate_denominators(documents):
    result = audit._reconcile(documents)
    counts = result["denominators"]
    assert (counts["retained_main_occurrences"], counts["matched_primary_endpoint_links"],
            counts["matched_repeat_report_links"], counts["retained_table1_physical_rows"],
            counts["table1_name_display_spans"], counts["table1_same_local_label_matches"]) == (205, 78, 6, 71, 89, 39)
    assert counts["independent_measurement_denominator"] is None
    assert counts["new_independent_measurements_credited"] == 0
    assert set(result["retained_disputes"]) == {"PR9", "PR39", "PR65_PR66", "PR109", "PR78_PR77"}
    assert result["boundary"]["goal_1_complete"] is False
    assert result["unresolved_scope"]["historical_main_unchecked_line_ranges"] == documents["main"]["unchecked_line_ranges"]
    assert result["unresolved_scope"]["historical_main_unresolved_gaps"] == documents["main"]["unresolved_gaps"]
    assert result["unresolved_scope"]["table1_unreviewed_or_unextended_scope"] == documents["supplement"]["unreviewed_or_unextended_scope"]
    pr59 = next(x for x in result["table1_literal_links"] if x["printed_name"] == "PR 59")
    assert pr59["relation"] == "same_local_label_only"
    assert pr59["chemical_identity_established"] is False
    assert next(x for x in pr59["endpoint_contexts"] if x["endpoint_id"] == "HSA")["cell_group_status"] == "blank"


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d["main"]["occurrences"].pop(), "main_denominator_changed"),
    (lambda d: d["main"]["occurrences"].append(deepcopy(d["main"]["occurrences"][0])), "duplicate_main_occurrence"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"].pop(), "primary_endpoint_membership_mismatch"),
    (lambda d: d["endpoint"]["endpoint_transcriptions"].append(deepcopy(d["endpoint"]["endpoint_transcriptions"][0])), "duplicate_endpoint_occurrence"),
    (lambda d: _endpoint(d).update(endpoint="functional_KB"), "primary_endpoint_or_label_mismatch"),
    (lambda d: _primary(d).update(target="other_receptor"), "primary_endpoint_or_label_mismatch"),
    (lambda d: _endpoint(d).update(assigned_role="training"), "row_role_or_admission_promotion"),
    (lambda d: _primary(d).update(activity_label="inactive"), "main_identity_label_or_independence_promotion"),
    (lambda d: _endpoint(d)["reported_summary"].update(reported_as_independent_remeasurement=True), "endpoint_summary_identity_or_censoring_promotion"),
    (lambda d: _endpoint(d)["censoring"].update(inactivity_imputed=True), "endpoint_summary_identity_or_censoring_promotion"),
    (lambda d: d["main"]["boundary"].update(independent_measurement_denominator=205), "main_authority_promotion"),
    (lambda d: d["endpoint"]["boundary"].update(training_admitted=True), "endpoint_authority_promotion"),
    (lambda d: d["supplement"]["boundary"].update(new_training_admission=1), "supplement_authority_promotion"),
    (lambda d: d["repeat"]["result"]["boundary"].update(new_independent_measurements_credited=5), "repeat_authority_promotion"),
    (lambda d: d["main"].update(supplement_reviewed=True), "historical_review_scope_promoted"),
    (lambda d: d["main"]["unresolved_gaps"].pop(), "unresolved_gaps_dropped_or_promoted"),
    (lambda d: d["main"]["unchecked_line_ranges"].clear(), "historical_review_scope_promoted"),
    (lambda d: d["endpoint"]["newly_noted_primary_conflicts"][0].update(automatic_correction_or_merge=True), "PR9_conflict_dropped_or_corrected"),
    (lambda d: d["endpoint"]["newly_noted_primary_conflicts"][0]["table_report"].update(Ki_mean="0.133"), "PR9_conflict_value_disagreement"),
    (lambda d: d["supplement"]["semantic_exceptions"]["PR109"].update(mapped_to_other_PR_label=True), "supplement_conflict_dropped_or_corrected"),
    (lambda d: d["supplement"]["semantic_exceptions"]["prior_other_target_PR78_vs_main_Table6_PR77"].update(relabeling_performed=True), "supplement_conflict_dropped_or_corrected"),
    (lambda d: _table(d).update(chemical_identity_verified=True), "supplement_identity_or_measurement_promotion"),
    (lambda d: d["supplement"]["endpoint_definitions"][0].update(receptor_assay_pH="7.4"), "chromatography_to_binding_promotion"),
    (lambda d: d["supplement"]["endpoint_definitions"][0].update(binding_Ki_equivalence=True), "chromatography_to_binding_promotion"),
    (lambda d: _table(d)["endpoint_contexts"][-1].update(cell_group_status="numeric_content_present"), "blank_or_unowned_cells_changed"),
    (lambda d: d["supplement"]["occurrences"].pop(), "supplement_denominator_changed"),
    (lambda d: d["supplement"]["occurrences"][0]["name_display_spans"].clear(), "name_span_denominator_changed"),
    (lambda d: d["repeat"]["result"]["correspondences"].pop(), "additive_repeat_membership_mismatch"),
    (lambda d: d["repeat"]["result"]["correspondences"][0].update(primary_mean="999"), "additive_repeat_semantics_mismatch"),
])
def test_synthetic_semantic_mutations_fail_before_any_admission(documents, mutation, code):
    mutation(documents)
    with pytest.raises(ValueError, match=code):
        audit._reconcile(documents)


def test_repeated_report_cannot_point_to_different_printed_label(documents):
    row = next(x for x in documents["main"]["occurrences"] if x["relation"] == "repeated_report")
    row["repeat_of"] = "table1:PR1"
    with pytest.raises(ValueError, match="invalid_repeat_link"):
        audit._reconcile(documents)


def test_duplicate_physical_row_cannot_hide_behind_a_different_id(documents):
    first, second = documents["supplement"]["occurrences"][:2]
    second["layout_LF_line_1based"] = first["layout_LF_line_1based"]
    with pytest.raises(ValueError, match="duplicate_physical_table_row"):
        audit._reconcile(documents)


def test_non_receptor_missingness_stays_non_numeric(documents):
    row = next(x for x in documents["main"]["occurrences"] if x["value"]["kind"] == "NT")
    row["value"]["token"] = "0"
    with pytest.raises(ValueError, match="missingness_to_numeric_promotion"):
        audit._reconcile(documents)


def test_external_references_are_not_followed(documents):
    # These body sections contain source/protocol references and are outside the
    # allowed public transcription projection. Poison them to show no traversal.
    documents["endpoint"]["inputs"] = {"never_open": {"path": "/unavailable/protected/bundle"}}
    documents["endpoint"]["prepared_pair_source_correspondence"] = [{"path": "/unavailable/structure"}]
    assert audit._reconcile(documents)["denominators"]["matched_primary_endpoint_links"] == 78


def test_fixed_record_rebuild_and_mutation_rejection(tmp_path):
    expected = audit.canonical_bytes(audit.reconcile(ROOT))
    assert (ROOT / audit.OUTPUT).read_bytes() == expected
    verification = audit.verify_record(ROOT, ROOT / audit.OUTPUT)
    assert verification["record_sha256"] == hashlib.sha256(expected).hexdigest()
    result = json.loads(expected)
    del result["retained_disputes"]["PR39"]
    mutant = tmp_path / "mutant.json"
    mutant.write_bytes(audit.canonical_bytes(result))
    with pytest.raises(ValueError, match="reconciliation_record_drift"):
        audit.verify_record(ROOT, mutant)


@pytest.mark.parametrize("raw,code", [(b'{"a":1,"a":2}', "duplicate_json_key"),
                                       (b'{"a":NaN}', "nonfinite_json_constant")])
def test_untrusted_json_cannot_hide_ambiguous_fields(raw, code):
    with pytest.raises(ValueError, match=code):
        audit._strict_json(raw)


def test_absent_or_changed_input_fails_closed_without_reading_external_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit.load_inputs(tmp_path)
    relative, size, _ = audit.INPUTS["main_contract"]
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * size)
    with pytest.raises(ValueError, match="fixed_input_pin_mismatch:main_contract"):
        audit.load_inputs(tmp_path)


def test_repository_cli_verifies_the_fixed_record_and_missing_root_fails_closed(tmp_path):
    entry = ROOT / "tools/verify_primary_5ht6_2024_cross_artifact_reconciliation_v1.py"
    passed = subprocess.run([sys.executable, str(entry), "--repo-root", str(ROOT),
                             "--verify-record", str(ROOT / audit.OUTPUT)], capture_output=True, check=True)
    assert json.loads(passed.stdout)["status"] == "PASS_fixed_public_transcription_record"
    failed = subprocess.run([sys.executable, str(entry), "--repo-root", str(tmp_path)], capture_output=True)
    assert failed.returncode == 1
    payload = json.loads(failed.stderr)
    assert payload["successful_reconciliation_established"] is False
    assert payload["requested_denominators"]["main"] == 205
