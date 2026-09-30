"""Verify a pinned, bounded source-occurrence inventory; never admit assay data.

This tool reads only caller-supplied retained sources. A successful receipt proves
byte bindings and inventory consistency, not transcription truth, chemical
identity, complete paper coverage, graph clearance, or measurement independence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from tools.product.primary_5ht6_ki_2024_source_v1 import _read_regular_bounded


CONTRACT_SCHEMA = "human_5ht6_2024_occurrence_contract_v1"
INVENTORY_SCHEMA = "human_5ht6_2024_occurrences_v1"
RECEIPT_SCHEMA = "human_5ht6_2024_occurrence_audit_v1"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
CATEGORIES = {
    "test_compound": "printed study compound; identity may remain unresolved",
    "binding_control": "reference or control for a binding endpoint",
    "functional_reference": "reference for a functional or cytotoxicity endpoint",
    "reagent": "assay reagent or chromatography/ADMET calibration reference",
    "cited_only": "chemical mentioned in a cited comparison; no inferred measurement",
}
ENDPOINTS = {
    "Ki": ["test_compound", "binding_control"],
    "KB": ["test_compound", "functional_reference"],
    "EC50": ["test_compound", "functional_reference"],
    "IC50": ["test_compound", "functional_reference"],
    "chromatography_panel": ["test_compound", "reagent"],
    "ADMET_panel": ["test_compound", "reagent"],
    "assay_reagent": ["reagent"],
    "synthesis_identity": ["test_compound"],
    "cited_comparison": ["cited_only"],
}
POLICY = {
    "inventory_inclusion": "all_declared_occurrences_in_bounded_review",
    "graph_inclusion": "unknown_pending_separate_policy_review",
    "independent_measurement_denominator": "unknown_not_inventory_count",
    "repeats": "never_count_as_independent_remeasurement_without_evidence",
    "bibliography": "no_automatic_chemical_or_document_edges",
    "outcome_exposure": "seen_public_values_not_blind_holdout",
    "posthoc_control_exclusion": "forbidden_on_observed_identity_or_outcome",
    "scope": "incomplete_main_article_and_unreviewed_supplement",
}
REQUIRED_GAPS = {
    "graph_inclusion_policy", "supplementary_inventory", "full_text_inventory",
    "chemical_identity_microstate", "wet_assay_pH", "receptor_construct",
    "reference_value_origin", "PR65_PR66_conflict", "purity_PR49_PR59",
    "intended_use_rights", "independent_source_roles", "table6_method_control_conflict",
    "untranscribed_values",
}
BOUNDARY = {
    "assigned_role": None, "admitted": False, "full_source_clearance": False,
    "scientifically_qualified": False, "independent_holdout": False,
    "graph_nodes_emitted": 0, "independent_measurement_denominator": None,
}
RELATIONS = {"reported_primary", "repeated_report", "not_determined",
             "reported_endpoint", "reference_value", "method_mention",
             "identity_only", "cited_only"}
ORIGINS = {"author_reported_test_result", "repeat_not_independent",
           "unknown_new_measurement_vs_reused", "not_a_measurement"}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _json_equal(left, right) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite_json_number")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    _require(type(value) is dict, "invalid_json_object")
    return value


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pinned_json(path: Path, digest: str) -> tuple[dict, str]:
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", digest)), "invalid_caller_pin")
    raw = _read_regular_bounded(path, MAX_JSON_BYTES)
    _require(_digest(raw) == digest, "caller_json_sha256_mismatch")
    return _strict_json(raw), digest


def _unique(items: list[dict], field: str, code: str) -> dict:
    _require(type(items) is list and bool(items), code)
    result = {}
    for item in items:
        _require(type(item) is dict and type(item.get(field)) is str, code)
        _require(item[field] not in result, code)
        result[item[field]] = item
    return result


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def validate_contract(contract: dict) -> None:
    _require(contract.get("schema_version") == CONTRACT_SCHEMA, "contract_schema")
    _require(_json_equal(contract.get("categories"), CATEGORIES), "category_contract")
    _require(_json_equal(contract.get("endpoints"), ENDPOINTS), "endpoint_contract")
    _require(_json_equal(contract.get("policy"), POLICY), "policy_contract")
    _require(_json_equal(contract.get("boundary"), BOUNDARY), "authority_contract")
    _require(set(contract.get("required_gap_ids", [])) == REQUIRED_GAPS,
             "required_gap_contract")
    _require(contract.get("line_convention") == "LF_bytes_1_based_inclusive",
             "line_convention")
    _require(type(contract.get("source_pins")) is dict
             and "layout" in contract["source_pins"], "source_pin_contract")
    for pin in contract["source_pins"].values():
        _require(type(pin) is dict and set(pin) == {"byte_count", "sha256"},
                 "source_pin_contract")
        _require(type(pin["byte_count"]) is int and 0 < pin["byte_count"] <= MAX_SOURCE_BYTES
                 and type(pin["sha256"]) is str
                 and bool(re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])), "source_pin_contract")
    _unique(contract["groups"], "id", "duplicate_or_invalid_group")


def _value_check(row: dict, span_text: str) -> None:
    value = row["value"]
    _require(type(value) is dict and set(value) == {"kind", "token", "unit", "sd"},
             "value_shape")
    kind, token, unit, sd = (value[x] for x in ("kind", "token", "unit", "sd"))
    _require(kind in {"numeric", "NA", "ND", "NT", "not_transcribed", "not_applicable"},
             "value_kind")
    if kind in {"not_transcribed", "not_applicable"}:
        _require(token is None and unit is None and sd is None, "untranscribed_numeric_value")
    elif kind in {"NA", "ND", "NT"}:
        _require(token == kind and unit is None and sd is None, "missingness_is_not_numeric")
        if kind == "NA":
            _require(row["endpoint"] in {"KB", "EC50"}, "NA_endpoint_mismatch")
        if kind == "NT":
            _require(row["endpoint"] == "IC50", "NT_endpoint_mismatch")
    else:
        _require(type(token) is str and unit == "uM", "numeric_unit_or_token")
        try:
            number = Decimal(token)
            _require(number.is_finite() and number > 0, "numeric_value_invalid")
            if sd is not None:
                _require(type(sd) is str and Decimal(sd).is_finite()
                         and Decimal(sd) > 0, "numeric_sd_invalid")
        except InvalidOperation as exc:
            raise ValueError("numeric_value_invalid") from exc
    for part in (token, sd):
        if part is not None:
            _require(_compact(part) in _compact(span_text), "value_token_not_in_span")


def _unreviewed_ranges(line_count: int, spans: dict) -> list[list[int]]:
    reviewed = set()
    for span in spans.values():
        reviewed.update(range(span["start_line"], span["end_line"] + 1))
    ranges = []
    for line in range(1, line_count + 1):
        if line not in reviewed:
            if ranges and ranges[-1][1] == line - 1:
                ranges[-1][1] = line
            else:
                ranges.append([line, line])
    return ranges


def audit_occurrences(contract_path: Path, contract_sha256: str,
                      inventory_path: Path, inventory_sha256: str,
                      source_paths: dict[str, Path]) -> dict:
    """Validate fixed inventory semantics and every declared retained-byte span."""
    contract, contract_digest = _pinned_json(contract_path, contract_sha256)
    inventory, inventory_digest = _pinned_json(inventory_path, inventory_sha256)
    validate_contract(contract)
    _require(inventory.get("schema_version") == INVENTORY_SCHEMA, "inventory_schema")
    _require(inventory.get("contract_sha256") == contract_digest, "inventory_contract_binding")
    _require(_json_equal(inventory.get("boundary"), BOUNDARY), "inventory_authority")
    _require(set(source_paths) == set(contract["source_pins"]), "source_set_mismatch")
    sources = {}
    for name, pin in contract["source_pins"].items():
        raw = _read_regular_bounded(source_paths[name], MAX_SOURCE_BYTES)
        _require(len(raw) == pin["byte_count"] and _digest(raw) == pin["sha256"],
                 "retained_source_pin_mismatch:" + name)
        sources[name] = raw
    # LF splitting deliberately preserves PDF form-feed bytes inside a line.
    lines = sources["layout"].split(b"\n")
    line_count = len(lines) - (lines[-1] == b"")
    spans = _unique(inventory["spans"], "id", "duplicate_or_invalid_span")
    span_texts = {}
    for key, span in spans.items():
        _require(set(span) == {"id", "start_line", "end_line", "sha256", "review_scope"},
                 "span_shape")
        start, end = span["start_line"], span["end_line"]
        _require(type(start) is int and type(end) is int and 1 <= start <= end <= line_count,
                 "span_range")
        raw = b"\n".join(lines[start - 1:end])
        if end < len(lines):
            raw += b"\n"
        _require(_digest(raw) == span["sha256"], "span_sha256_mismatch:" + key)
        _require(span["review_scope"] == "bounded_occurrence_metadata_only", "span_scope")
        span_texts[key] = raw.decode("utf-8")
    groups = _unique(contract["groups"], "id", "duplicate_or_invalid_group")
    expected = {}
    for group_id, group in groups.items():
        _require(set(group) == {"id", "span", "entities", "category", "endpoint", "target",
                               "relation", "origin"}, "group_shape")
        _require(group["span"] in spans and type(group["entities"]) is list
                 and bool(group["entities"]), "group_span_or_entities")
        _require(len(set(group["entities"])) == len(group["entities"]), "duplicate_group_entity")
        for entity in group["entities"]:
            _require(type(entity) is str and bool(entity), "invalid_entity")
            expected[(group_id, entity)] = group
    rows = _unique(inventory["occurrences"], "id", "duplicate_or_invalid_occurrence")
    observed, signatures = set(), set()
    repeated = 0
    repeats_without_primary_numeric_value = []
    for row in rows.values():
        _require(set(row) == {"id", "group", "entity", "category", "endpoint", "target", "span",
                              "relation", "origin", "source_tokens", "value", "repeat_of",
                              "inventory_included", "graph_inclusion", "assigned_role", "admitted",
                              "independent_measurement_count", "activity_label"}, "occurrence_shape")
        key = (row["group"], row["entity"])
        _require(key in expected and key not in observed, "unexpected_or_duplicate_occurrence")
        observed.add(key)
        group = expected[key]
        _require(all(row[k] == group[k] for k in
                     ("category", "endpoint", "target", "span", "relation", "origin")),
                 "occurrence_group_semantics")
        category, endpoint = row["category"], row["endpoint"]
        _require(category in CATEGORIES, "unknown_occurrence_category")
        _require(endpoint in ENDPOINTS and category in ENDPOINTS[endpoint],
                 "category_endpoint_mismatch")
        _require(row["relation"] in RELATIONS and row["origin"] in ORIGINS, "relation_or_origin")
        source_span = spans[row["span"]]
        signature = (row["entity"], source_span["start_line"], source_span["end_line"],
                     endpoint, row["target"])
        _require(signature not in signatures, "duplicate_semantic_occurrence")
        signatures.add(signature)
        _require(row["inventory_included"] is True
                 and row["graph_inclusion"] == "unknown"
                 and row["assigned_role"] is None and row["admitted"] is False
                 and row["independent_measurement_count"] is None
                 and row["activity_label"] is None, "occurrence_authority_or_denominator")
        tokens = row["source_tokens"]
        _require(type(tokens) is list and bool(tokens) and all(
            type(token) is str and bool(token.strip())
            and _compact(token) in _compact(span_texts[row["span"]]) for token in tokens),
            "occurrence_token_not_in_span")
        _require(_compact(row["entity"]) in _compact(span_texts[row["span"]]),
                 "entity_not_in_span")
        _value_check(row, span_texts[row["span"]])
        binding = contract["value_bindings"].get(row["id"])
        if row["value"]["kind"] in {"numeric", "NA", "ND", "NT"}:
            _require(type(binding) is dict and _json_equal(binding["value"], row["value"]),
                     "reviewed_value_binding_mismatch")
            line = binding["line"]
            _require(type(line) is int and spans[row["span"]]["start_line"] <= line
                     <= spans[row["span"]]["end_line"], "value_binding_line")
            source_words = lines[line - 1].decode("utf-8").split()
            for field, index in binding["token_indices"].items():
                _require(field in {"token", "sd"} and type(index) is int
                         and 0 <= index < len(source_words)
                         and source_words[index] == row["value"][field],
                         "value_source_position_mismatch")
            _require("token" in binding["token_indices"]
                     and ((row["value"]["sd"] is None)
                          == ("sd" not in binding["token_indices"])), "value_binding_incomplete")
        else:
            _require(binding is None, "unexpected_value_binding")
        if row["relation"] == "repeated_report":
            original = rows.get(row["repeat_of"])
            _require(original is not None and original["relation"] == "reported_primary"
                     and original["entity"] == row["entity"]
                     and original["endpoint"] == endpoint
                     and original["target"] == row["target"]
                     and original["span"] != row["span"]
                     and row["origin"] == "repeat_not_independent", "invalid_repeat_relation")
            if original["value"]["kind"] == "numeric":
                _require(original["value"]["token"] == row["value"]["token"],
                         "repeated_value_mismatch")
            else:
                repeats_without_primary_numeric_value.append(row["id"])
            repeated += 1
        else:
            _require(row["repeat_of"] is None, "unexpected_repeat_link")
        if row["relation"] == "reference_value":
            _require(category in {"binding_control", "functional_reference", "reagent"}
                     and row["origin"] == "unknown_new_measurement_vs_reused",
                     "reference_origin_unresolved")
        if category in {"reagent", "cited_only"} and row["relation"] != "reference_value":
            _require(row["origin"] == "not_a_measurement", "nonmeasurement_origin")
        if row["value"]["kind"] == "ND":
            _require(row["relation"] == "not_determined", "ND_relation")
    _require(observed == set(expected), "incomplete_required_inventory")
    _require(set(contract["value_bindings"]) <= set(rows), "orphan_value_binding")
    gaps = _unique(inventory["unresolved_gaps"], "id", "duplicate_or_invalid_gap")
    _require(set(gaps) == REQUIRED_GAPS, "missing_required_gap")
    for gap in gaps.values():
        _require(set(gap) == {"id", "status", "detail", "spans"}
                 and gap["status"] == "unresolved" and bool(gap["detail"])
                 and type(gap["spans"]) is list
                 and all(x in spans for x in gap["spans"]), "gap_status_or_source")
    unchecked = _unreviewed_ranges(line_count, spans)
    _require(bool(unchecked), "bounded_inventory_requires_unchecked_spans")
    _require(inventory["unchecked_line_ranges"] == unchecked, "unchecked_span_coverage")
    _require(inventory.get("supplement_reviewed") is False, "supplement_not_reviewed")
    return {
        "schema_version": RECEIPT_SCHEMA,
        "status": "inventory_consistent_bounded_review",
        "review_status": "blocked_review",
        "scope": "retained_byte_and_inventory_consistency_only",
        "contract_sha256": contract_digest, "inventory_sha256": inventory_digest,
        "verified_source_pins": contract["source_pins"], "verified_span_count": len(spans),
        "occurrence_count": len(rows),
        "counts_by_category": dict(sorted(Counter(x["category"] for x in rows.values()).items())),
        "primary_printed_test_ids": sorted({x["entity"] for x in rows.values()
                                           if x["relation"] == "reported_primary"}),
        "repeated_report_occurrences": repeated,
        "repeats_without_primary_numeric_value": repeats_without_primary_numeric_value,
        "value_binding_scope": "caller_pinned_reviewed_row_and_token_positions; no_automatic_column_interpretation",
        "unchecked_line_ranges": unchecked,
        "supplement_reviewed": False, "unresolved_gaps": list(gaps.values()),
        "transcription_truth_established": False,
        "protected_context_discovery_or_scan_performed": False,
        "new_preflight_executed": False,
        **BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--source", action="append", required=True, metavar="NAME=ABSOLUTE_PATH")
    args = parser.parse_args(argv)
    sources = {}
    for assignment in args.source:
        name, separator, path = assignment.partition("=")
        if not separator or not name or not path or name in sources:
            parser.error("each --source must uniquely bind NAME=ABSOLUTE_PATH")
        sources[name] = Path(path)
    receipt = audit_occurrences(args.contract, args.contract_sha256, args.inventory,
                                args.inventory_sha256, sources)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
