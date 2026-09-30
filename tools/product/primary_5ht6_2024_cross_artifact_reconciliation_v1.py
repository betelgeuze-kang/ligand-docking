"""Reconcile already audited public transcriptions without admitting assay data.

Only the seven fixed repository artifacts below are opened. External paths in
their metadata are never followed; no source PDF, molecular input, protected
context, reference/control bundle, or numerical runtime is loaded.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import stat
import sys


SCHEMA = "human_5ht6_2024_cross_artifact_reconciliation/1"
OUTPUT = "docs/evidence/primary_5ht6_2024_cross_artifact_reconciliation_20260930_v1.json"
DOI = "10.3390/ijms251910287"
INPUTS = {
    "main_contract": ("docs/evidence/human_5ht6_2024_occurrence_contract_v1.json", 31266,
                      "55fab87416d876a0ffd24313446590a5d2e1b0d775b3f7389d4b321c4b2292cc"),
    "main": ("docs/evidence/human_5ht6_2024_occurrences_v1.json", 154330,
             "6261d248b41d68a4754ea800b1a577c2de1442846b54c17b16e0a2fc1740dd64"),
    "endpoint": ("docs/evidence/human_5ht6_endpoint_admission_next_v1.json", 117960,
                 "538814de35cfbc6c83bb55fe39401cfbbb44da3629ff60a682be629d729a23ee"),
    "supplement": ("docs/evidence/human_5ht6_2024_supplement_table1_occurrences_v1.json", 230131,
                   "5cdbced83cadd78ba2ce48317975d581c0b98bad466b3bd7c0c81a3fa12fb234"),
    "repeat": ("docs/evidence/human_5ht6_2024_repeat_correspondence_v1.json", 13106,
               "e4cdef57c1377e3dc27af0ecf6d95579618358035dce22831e88bdd3f288703f"),
    "identity_report": ("docs/research/human_5ht6_2024_identity_manifest_20260930.md", 4163,
                        "6fa85870e385c2ca027ace9e83c695fb2760f577d3743aec937ce6b35812e225"),
    "supplement_report": ("docs/research/human_5ht6_2024_supplement_review_20260930.md", 6358,
                          "12046558f50371de2950e0b5877a687dc3c429d72c694c813f4b66382338d494"),
}
COUNTS = {"main": 205, "primary": 78, "repeat": 6, "supplement": 71,
          "name_spans": 89, "additive_repeat": 5, "label_matches": 39}
BOUNDARY = {
    "additive_only": True, "original_artifacts_rewritten": False,
    "assigned_role": None, "graph_inclusion": "unknown_pending_separate_policy_review",
    "graph_nodes_emitted": 0, "chemical_identity_established": False,
    "assayed_microstate_verified": False, "same_prepared_assay_state_verified": False,
    "source_authenticated": False, "new_independent_measurements_credited": 0,
    "independent_measurement_denominator": None, "full_source_clearance": False,
    "training_admitted": False, "calibration_admitted": False,
    "independent_evaluation_admitted": False, "independent_holdout": False,
    "new_preflight_executed": False, "protected_context_opened": False,
    "molecular_runtime_executed": False, "scientifically_qualified": False,
    "goal_1_complete": False,
}
MAIN_BOUNDARY = {"assigned_role": None, "admitted": False, "full_source_clearance": False,
                 "scientifically_qualified": False, "independent_holdout": False,
                 "graph_nodes_emitted": 0, "independent_measurement_denominator": None}
ENDPOINT_BOUNDARY = {
    "assigned_role": None, "source_authenticated": False, "assayed_microstate_verified": False,
    "same_prepared_assay_state_verified": False, "independent_measurement_denominator": None,
    "training_admitted": False, "calibration_admitted": False, "independent_evaluation_admitted": False,
    "product_ranking_enabled": False, "scientifically_validated": False,
}
SUPPLEMENT_BOUNDARY = {
    "additive_only": True, "earlier_205_occurrence_contract_preserved": True,
    "earlier_123_literal_manifest_preserved": True, "numeric_retention_values_transcribed": False,
    "numeric_chromatography_to_Ki_conversion": False, "graph_nodes_emitted": 0,
    "graph_inclusion": "unknown_pending_separate_policy_review", "assigned_role": None,
    "new_assay_rows_admitted": 0, "new_training_admission": 0,
    "new_calibration_admission": 0, "new_independent_evaluation_admission": 0,
    "independent_measurement_denominator": None, "new_independent_source_component_established": False,
    "protected_fresh128_touched": False, "protected_context_opened": False,
    "new_preflight_executed": False, "fit_or_model_change": False,
    "full_source_clearance": False, "scientifically_qualified": False,
}
REPEAT_BOUNDARY = {**MAIN_BOUNDARY, "chemical_graph_verified": False,
                   "new_independent_measurements_credited": 0, "prepared_states_bound": False}
ENDPOINT_IDS = ("C18_pH_2.6", "C18_pH_7.4", "C18_pH_10.5", "IAM", "HSA")
GROUP_COUNTS = {"numbered": 45, "calibration_C18": 8, "calibration_IAM": 9, "calibration_HSA": 9}
GAP_IDS = {"graph_inclusion_policy", "supplementary_inventory", "full_text_inventory",
           "chemical_identity_microstate", "wet_assay_pH", "receptor_construct",
           "reference_value_origin", "PR65_PR66_conflict", "purity_PR49_PR59",
           "intended_use_rights", "independent_source_roles", "table6_method_control_conflict",
           "untranscribed_values"}
CATEGORY_ENDPOINTS = {
    "test_compound": {"Ki", "KB", "EC50", "IC50", "chromatography_panel", "ADMET_panel", "synthesis_identity"},
    "binding_control": {"Ki"}, "functional_reference": {"KB", "EC50", "IC50"},
    "reagent": {"assay_reagent", "chromatography_panel", "ADMET_panel"}, "cited_only": {"cited_comparison"},
}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite_json_constant")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    _require(type(value) is dict, "json_object_required")
    return value


def _regular_bytes(path, limit):
    _require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), "regular_artifact_required")
    _require(0 < path.stat().st_size <= limit, "artifact_capacity")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _require(len(raw) <= limit, "artifact_capacity")
    return raw


def load_inputs(repo_root):
    """Read only explicit repository pins, never any path declared by an input."""
    documents = {}
    for key, (relative, size, digest) in INPUTS.items():
        path = repo_root / relative
        _require(path.resolve(strict=True) == path.absolute(), "noncanonical_artifact:" + key)
        raw = _regular_bytes(path, size)
        _require(len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
                 "fixed_input_pin_mismatch:" + key)
        if relative.endswith(".json"):
            documents[key] = _strict_json(raw)
    return documents


def _unique(rows, field, code):
    _require(type(rows) is list, code)
    result = {}
    for row in rows:
        _require(type(row) is dict and type(row.get(field)) is str
                 and row[field] not in result, code)
        result[row[field]] = row
    return result


def _equal(left, right):
    # JSON equality distinguishes false from zero, and true from one.
    return canonical_bytes(left) == canonical_bytes(right)


def _positive(token):
    _require(type(token) is str, "numeric_token_required")
    try:
        value = Decimal(token)
        _require(value.is_finite() and value > 0, "invalid_positive_summary")
    except InvalidOperation as exc:
        raise ValueError("invalid_positive_summary") from exc


def _no_promotion(row):
    _require(row.get("assigned_role") is None and row.get("admitted") is False,
             "row_role_or_admission_promotion")


def _reconcile(documents, counts=COUNTS):
    """Pure semantic joins; alternate counts are only for inert unit fixtures."""
    main, endpoint, supplement, repeat = (documents[k] for k in ("main", "endpoint", "supplement", "repeat"))
    _require(_equal(main["boundary"], MAIN_BOUNDARY), "main_authority_promotion")
    _require(_equal(endpoint["boundary"], ENDPOINT_BOUNDARY), "endpoint_authority_promotion")
    _require(_equal(supplement["boundary"], SUPPLEMENT_BOUNDARY), "supplement_authority_promotion")
    _require(_equal(repeat["result"]["boundary"], REPEAT_BOUNDARY), "repeat_authority_promotion")
    _require(main["supplement_reviewed"] is False and bool(main["unchecked_line_ranges"]),
             "historical_review_scope_promoted")
    gaps = _unique(main["unresolved_gaps"], "id", "duplicate_gap")
    _require(set(gaps) == GAP_IDS and all(row["status"] == "unresolved" for row in gaps.values()),
             "unresolved_gaps_dropped_or_promoted")
    main_rows = _unique(main["occurrences"], "id", "duplicate_main_occurrence")
    _require(len(main_rows) == counts["main"], "main_denominator_changed")
    for row in main_rows.values():
        _no_promotion(row)
        _require(row["graph_inclusion"] == "unknown" and row["inventory_included"] is True
                 and row["activity_label"] is None and row["independent_measurement_count"] is None,
                 "main_identity_label_or_independence_promotion")
        _require(row["endpoint"] in CATEGORY_ENDPOINTS.get(row["category"], set()), "main_category_endpoint_mismatch")
        value = row["value"]
        kind = value["kind"]
        _require(kind in {"numeric", "NA", "ND", "NT", "not_transcribed", "not_applicable"}, "main_value_kind_changed")
        if kind == "numeric":
            _require(value["unit"] == "uM", "main_numeric_unit_changed")
            _positive(value["token"])
            if value["sd"] is not None:
                _positive(value["sd"])
        elif kind in {"NA", "ND", "NT"}:
            _require(value["token"] == kind and value["unit"] is None and value["sd"] is None,
                     "missingness_to_numeric_promotion")
            _require((kind != "NA" or row["endpoint"] in {"KB", "EC50"})
                     and (kind != "NT" or row["endpoint"] == "IC50")
                     and (kind != "ND" or row["relation"] == "not_determined"), "missingness_endpoint_changed")
        else:
            _require(all(value[k] is None for k in ("token", "unit", "sd")), "missing_value_imputed")
    primary = {key: row for key, row in main_rows.items() if row["relation"] == "reported_primary"}
    repeated = {key: row for key, row in main_rows.items() if row["relation"] == "repeated_report"}
    endpoints = _unique(endpoint["endpoint_transcriptions"], "occurrence_id", "duplicate_endpoint_occurrence")
    _require(len(primary) == len(endpoints) == counts["primary"] and set(primary) == set(endpoints),
             "primary_endpoint_membership_mismatch")
    _require(len(repeated) == counts["repeat"], "repeat_denominator_changed")
    links = []
    for key, row in primary.items():
        target = endpoints[key]
        _no_promotion(target)
        _require(row["category"] == "test_compound" and row["endpoint"] == "Ki"
                 and row["target"] == "human_5HT6" and row["entity"] == target["printed_compound_id"]
                 and target["endpoint"] == "radioligand_binding_Ki"
                 and target["target_context"] == "human_5HT6_reported_by_section_3.2",
                 "primary_endpoint_or_label_mismatch")
        summary = target["reported_summary"]
        _require(summary["relation"] == "=" and summary["unit"] == "µM"
                 and summary["uncertainty"]["kind"] == "SD"
                 and summary["reported_as_independent_remeasurement"] is False
                 and target["binary_label"] is None and target["raw_replicates_available"] is False
                 and target["chemical_identity_status"] == (
                     "unresolved_primary_conflict" if target["identity_issue"] is not None
                     else "not_newly_verified_by_this_endpoint_transcription")
                 and target["censoring"]["bound"] is None
                 and target["censoring"]["inactivity_imputed"] is False,
                 "endpoint_summary_identity_or_censoring_promotion")
        _positive(summary["mean"])
        _positive(summary["uncertainty"]["value"])
        old_value = row["value"]
        if old_value["kind"] == "numeric":
            _require(old_value["unit"] == "uM" and old_value["token"] == summary["mean"]
                     and old_value["sd"] == summary["uncertainty"]["value"], "historical_summary_disagreement")
        else:
            _require(old_value["kind"] == "not_transcribed"
                     and all(old_value[k] is None for k in ("token", "unit", "sd")),
                     "historical_missingness_changed")
        links.append({"main_occurrence_id": key, "endpoint_occurrence_id": key,
                      "printed_label": row["entity"], "relation": "same_declared_occurrence_label_and_binding_endpoint",
                      "reported_summary": deepcopy(summary), "historical_value": deepcopy(old_value),
                      "chemical_identity_established": False, "identity_issue": target["identity_issue"]})
    repeat_links = []
    for key, row in repeated.items():
        original = primary.get(row["repeat_of"])
        _require(original is not None and row["entity"] == original["entity"]
                 and row["endpoint"] == "Ki" and row["target"] == "human_5HT6"
                 and row["origin"] == "repeat_not_independent", "invalid_repeat_link")
        summary = endpoints[row["repeat_of"]]["reported_summary"]
        _require(row["value"]["kind"] == "numeric" and row["value"]["unit"] == "uM"
                 and row["value"]["token"] == summary["mean"] and row["value"]["sd"] is None,
                 "repeat_summary_disagreement")
        repeat_links.append({"repeat_occurrence_id": key, "primary_occurrence_id": row["repeat_of"],
                             "relation": "same_printed_label_binding_endpoint_and_mean",
                             "repeat_value": deepcopy(row["value"]), "primary_reported_summary": deepcopy(summary),
                             "independent_remeasurement_established": False})
    additive = _unique(repeat["result"]["correspondences"], "repeat_occurrence", "duplicate_additive_repeat")
    expected_additive = {key for key, row in repeated.items() if primary[row["repeat_of"]]["value"]["kind"] == "not_transcribed"}
    _require(set(additive) == expected_additive and len(additive) == counts["additive_repeat"],
             "additive_repeat_membership_mismatch")
    _require(repeat["roles_changed"] is False and repeat["scientific_admission"] is False
             and type(repeat["new_independent_measurements_credited"]) is int
             and repeat["new_independent_measurements_credited"] == 0, "repeat_authority_promotion")
    for key, row in additive.items():
        target = repeated[key]
        summary = endpoints[target["repeat_of"]]["reported_summary"]
        _require(row["primary_occurrence"] == target["repeat_of"] and row["entity"] == target["entity"]
                 and row["endpoint"] == "Ki" and row["target"] == "human_5HT6" and row["unit"] == "uM"
                 and row["primary_mean"] == row["repeat_mean"] == summary["mean"]
                 and _equal(row["primary_uncertainty"], summary["uncertainty"])
                 and row["repeat_reported_uncertainty"] is None
                 and row["assayed_chemical_identity_established"] is False
                 and row["independent_remeasurement_established"] is False,
                 "additive_repeat_semantics_mismatch")
    definitions = _unique(supplement["endpoint_definitions"], "id", "duplicate_supplement_endpoint")
    _require(tuple(definitions) == ENDPOINT_IDS, "supplement_endpoint_set_changed")
    for definition in definitions.values():
        _require(definition["endpoint_family"] == "chromatography_retention_and_derived_indices"
                 and all(definition[k] is None for k in ("receptor_target", "species", "receptor_assay_pH"))
                 and definition["binding_Ki_equivalence"] is False, "chromatography_to_binding_promotion")
    table_rows = _unique(supplement["occurrences"], "occurrence_id", "duplicate_supplement_occurrence")
    _require(len(table_rows) == counts["supplement"], "supplement_denominator_changed")
    _require(dict(Counter(row["row_group"] for row in table_rows.values())) == GROUP_COUNTS,
             "supplement_group_denominator_changed")
    signatures = {(row["source_member"], row["physical_pdf_page_1based"], row["layout_LF_line_1based"])
                  for row in table_rows.values()}
    _require(len(signatures) == len(table_rows), "duplicate_physical_table_row")
    span_count = sum(len(row["name_display_spans"]) for row in table_rows.values())
    _require(span_count == counts["name_spans"], "name_span_denominator_changed")
    primary_labels = {row["entity"]: key for key, row in primary.items()}
    _require(len(primary_labels) == len(primary), "duplicate_primary_label")
    _require(set(primary_labels) == {f"PR{i}" for i in range(1, counts["primary"] + 1)},
             "primary_printed_label_set_changed")
    table_links, label_matches = [], 0
    for key, row in table_rows.items():
        _no_promotion(row)
        _require(row["chemical_identity_verified"] is False and row["assayed_microstate_verified"] is False
                 and row["graph_inclusion"] == "unknown" and row["human_5HT6_Ki_measurement"] is False
                 and row["new_independent_measurement_credited"] is False, "supplement_identity_or_measurement_promotion")
        label = row["source_local_label_after_whitespace_removal"]
        target = primary_labels.get(label) if row["name_kind"] == "study_literal_label" else None
        if target:
            _require("".join(row["printed_name"].split()) == label
                     and row["prior_literal_manifest_lookup"] == "same_local_label_present", "supplement_local_label_mismatch")
            label_matches += 1
        contexts = _unique(row["endpoint_contexts"], "endpoint_id", "duplicate_row_endpoint")
        _require(tuple(contexts) == ENDPOINT_IDS, "row_endpoint_membership_changed")
        group = row["row_group"]
        _require(group in GROUP_COUNTS, "unknown_supplement_group")
        _require(key == f"supplement_table1:{group}:{row['row_in_group_1based']}"
                 and type(row["row_in_group_1based"]) is int
                 and 1 <= row["row_in_group_1based"] <= GROUP_COUNTS[group], "physical_row_identity_mismatch")
        displays = row["name_display_spans"]
        _require(len({(x["start_byte_1based"], x["end_byte_1based_inclusive"]) for x in displays}) == len(displays),
                 "duplicate_name_display_span")
        owned = set(ENDPOINT_IDS) if group == "numbered" else (
            set(ENDPOINT_IDS[:3]) if group == "calibration_C18" else {group.removeprefix("calibration_")})
        for endpoint_id, context in contexts.items():
            is_owned = endpoint_id in owned
            _require(context["owned_by_row_block"] is is_owned
                     and type(context["numeric_content_present"]) is bool
                     and context["individual_numeric_cells_transcribed"] is False
                     and context["all_replicate_cells_complete_established"] is False,
                     "row_endpoint_ownership_or_replicate_promotion")
            status = "numeric_content_present" if context["numeric_content_present"] else "blank"
            _require(context["cell_group_status"] == (status if is_owned else "not_in_row_block")
                     and (is_owned or context["numeric_content_present"] is False), "blank_or_unowned_cells_changed")
        table_links.append({"table1_occurrence_id": key, "printed_name": row["printed_name"],
                            "matched_main_primary_occurrence_id": target,
                            "relation": "same_local_label_only" if target else "unresolved_label_or_other_literal",
                            "chemical_identity_established": False, "name_display_spans": deepcopy(row["name_display_spans"]),
                            "endpoint_contexts": deepcopy(row["endpoint_contexts"])})
    _require(label_matches == counts["label_matches"], "local_label_match_denominator_changed")
    conflicts = endpoint["newly_noted_primary_conflicts"]
    _require(len(conflicts) == 1 and conflicts[0]["compound_id"] == "PR9"
             and conflicts[0]["status"] == "unresolved" and conflicts[0]["automatic_correction_or_merge"] is False,
             "PR9_conflict_dropped_or_corrected")
    pr9 = next(row for row in endpoints.values() if row["printed_compound_id"] == "PR9")
    _require(conflicts[0]["table_report"]["Ki_mean"] == pr9["reported_summary"]["mean"]
             and conflicts[0]["table_report"]["SD"] == pr9["reported_summary"]["uncertainty"]["value"]
             and conflicts[0]["prose_report"]["Ki_mean"] != pr9["reported_summary"]["mean"],
             "PR9_conflict_value_disagreement")
    exceptions = supplement["semantic_exceptions"]
    _require(exceptions["PR109"]["mapped_to_other_PR_label"] is False
             and exceptions["PR109"]["status"] == "unresolved_local_label"
             and exceptions["prior_other_target_PR78_vs_main_Table6_PR77"]["relabeling_performed"] is False
             and exceptions["prior_other_target_PR78_vs_main_Table6_PR77"]["status"] == "unresolved_correspondence",
             "supplement_conflict_dropped_or_corrected")
    return {
        "schema_id": SCHEMA, "source_doi": DOI,
        "status": "PASS_public_transcription_reconciliation_only",
        "input_pins": {key: {"path": path, "bytes": size, "sha256": sha} for key, (path, size, sha) in INPUTS.items()},
        "scope": "Existing public audited transcriptions and pinned reports only; no external reference followed.",
        "main_occurrence_membership": [{k: deepcopy(row[k]) for k in
                                       ("id", "entity", "category", "endpoint", "target", "relation", "origin", "repeat_of", "value")}
                                      for row in main_rows.values()],
        "primary_endpoint_links": links, "repeat_report_links": repeat_links,
        "additive_repeat_correspondence_ids": list(additive), "table1_literal_links": table_links,
        "retained_disputes": {"PR9": deepcopy(conflicts[0]),
                              "PR39": {"status": "unresolved_table_vs_synthesis_ring_element", "corrected_identity": None,
                                         "evidence_input": "identity_report", "label_agreement_is_chemical_identity": False},
                              "PR65_PR66": deepcopy(gaps["PR65_PR66_conflict"]),
                              "PR109": deepcopy(exceptions["PR109"]),
                              "PR78_PR77": deepcopy(exceptions["prior_other_target_PR78_vs_main_Table6_PR77"])},
        "retained_table1_semantic_exceptions": deepcopy(exceptions),
        "unresolved_scope": {"historical_main_unresolved_gaps": deepcopy(main["unresolved_gaps"]),
                             "historical_main_unchecked_line_ranges": deepcopy(main["unchecked_line_ranges"]),
                             "historical_main_supplement_reviewed": False,
                             "table1_unreviewed_or_unextended_scope": deepcopy(supplement["unreviewed_or_unextended_scope"]),
                             "biological_curves": deepcopy(supplement["biological_curve_count_only"]),
                             "complete_source_family_reviewed": False, "rights_exceptions_and_intended_use_cleared": False,
                             "raw_replicates_batch_construct_assay_pH_and_microstate_correspondence": "unknown"},
        "denominators": {"requested_main_occurrences": counts["main"], "retained_main_occurrences": len(main_rows),
                         "main_counts_by_category": dict(sorted(Counter(x["category"] for x in main_rows.values()).items())),
                         "requested_primary_endpoint_links": counts["primary"], "matched_primary_endpoint_links": len(links),
                         "requested_repeat_report_links": counts["repeat"], "matched_repeat_report_links": len(repeat_links),
                         "additive_repeat_links": len(additive), "requested_table1_physical_rows": counts["supplement"],
                         "retained_table1_physical_rows": len(table_rows), "table1_name_display_spans": span_count,
                         "table1_same_local_label_matches": label_matches,
                         "table1_other_or_unresolved_literal_rows": len(table_rows) - label_matches,
                         "failed_required_links": 0, "independent_measurement_denominator": None,
                         "new_independent_measurements_credited": 0,
                         "counts_are_separate_representation_denominators_not_additive_experiments": True},
        "boundary": deepcopy(BOUNDARY),
    }


def reconcile(repo_root):
    root = Path(repo_root).resolve(strict=True)
    documents = load_inputs(root)
    _require(documents["main"]["contract_sha256"] == INPUTS["main_contract"][2], "main_contract_binding_mismatch")
    return _reconcile(documents)


def verify_record(repo_root, record_path):
    expected = canonical_bytes(reconcile(repo_root))
    supplied = _regular_bytes(Path(record_path), 2 * 1024 * 1024)
    _require(supplied == expected, "reconciliation_record_drift")
    return {"schema_id": SCHEMA + "/verification", "status": "PASS_fixed_public_transcription_record",
            "record_sha256": hashlib.sha256(supplied).hexdigest(), "record_bytes": len(supplied),
            "verified_input_count": len(INPUTS), "denominators": _strict_json(supplied)["denominators"],
            "boundary": deepcopy(BOUNDARY)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--verify-record", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_record(args.repo_root, args.verify_record) if args.verify_record else reconcile(args.repo_root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({"schema_id": SCHEMA + "/failure", "status": "FAIL_closed",
                          "error": str(exc), "requested_denominators": COUNTS,
                          "successful_reconciliation_established": False, "boundary": BOUNDARY},
                         ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
