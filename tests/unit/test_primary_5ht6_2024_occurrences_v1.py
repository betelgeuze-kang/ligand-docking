"""Portable source and semantic mutations; no PDF, network, or molecular runtime."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tools.product import primary_5ht6_2024_occurrences_v1 as audit


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def packet(tmp_path):
    raw = (
        "unchecked header\n"
        "PR49 0.077 ± 0.018\n"
        "PR59 1.964 ± 0.452\n"
        "PR 49 9999.999 206.900 ND 0.077 NA 0.081 141.500 38.8\n"
        "PR 66 ND ND 3.444 ND ND ND ND NT\n"
        "olanzapine 0.007 SB258585 0.0003\n"
        "[3H]-LSD reagent\n"
        "pimozide cited comparison\n"
        "unchecked tail\n"
    ).encode()
    source = tmp_path / "source.txt"
    source.write_bytes(raw)
    lines = raw.split(b"\n")
    spans, groups, rows, bindings = [], [], [], {}

    def add(name, entity, category, endpoint, relation, origin, line,
            token=None, token_index=None, sd=None, repeat_of=None):
        spans.append({"id": name, "start_line": line, "end_line": line,
                      "sha256": digest(lines[line - 1] + b"\n"),
                      "review_scope": "bounded_occurrence_metadata_only"})
        group = {"id": name, "span": name, "entities": [entity], "category": category,
                 "endpoint": endpoint, "target": "human_5HT6", "relation": relation,
                 "origin": origin}
        groups.append(group)
        kind = "not_applicable" if token is None else (
            token if token in {"ND", "NT", "NA"} else "numeric")
        value = {"kind": kind, "token": token,
                 "unit": "uM" if kind == "numeric" else None, "sd": sd}
        row = {key: group[key] for key in
               ("category", "endpoint", "target", "span", "relation", "origin")}
        row.update(id=name, group=name, entity=entity, source_tokens=[entity], value=value,
                   repeat_of=repeat_of, inventory_included=True, graph_inclusion="unknown",
                   assigned_role=None, admitted=False, independent_measurement_count=None,
                   activity_label=None)
        rows.append(row)
        if token is not None:
            indices = {"token": token_index}
            if sd is not None:
                indices["sd"] = 3
            bindings[name] = {"value": deepcopy(value), "line": line, "token_indices": indices}

    add("primary49", "PR49", "test_compound", "Ki", "reported_primary",
        "author_reported_test_result", 2, "0.077", 1, "0.018")
    add("primary59", "PR59", "test_compound", "Ki", "reported_primary",
        "author_reported_test_result", 3, "1.964", 1, "0.452")
    add("repeat49", "PR49", "test_compound", "Ki", "repeated_report",
        "repeat_not_independent", 4, "0.077", 5, repeat_of="primary49")
    add("functional49", "PR49", "test_compound", "KB", "reported_endpoint",
        "author_reported_test_result", 4, "0.081", 7)
    add("missing66", "PR66", "test_compound", "Ki", "not_determined",
        "author_reported_test_result", 5, "ND", 5)
    add("cytotoxic66", "PR66", "test_compound", "IC50", "reported_endpoint",
        "author_reported_test_result", 5, "NT", 9)
    add("olanzapine", "olanzapine", "binding_control", "Ki", "reference_value",
        "unknown_new_measurement_vs_reused", 6, "0.007", 1)
    add("SB258585", "SB258585", "functional_reference", "KB", "reference_value",
        "unknown_new_measurement_vs_reused", 6, "0.0003", 3)
    add("radioligand", "[3H]-LSD", "reagent", "assay_reagent", "method_mention",
        "not_a_measurement", 7)
    add("cited", "pimozide", "cited_only", "cited_comparison", "cited_only",
        "not_a_measurement", 8)
    contract = {
        "schema_version": audit.CONTRACT_SCHEMA,
        "categories": deepcopy(audit.CATEGORIES), "endpoints": deepcopy(audit.ENDPOINTS),
        "policy": deepcopy(audit.POLICY), "boundary": deepcopy(audit.BOUNDARY),
        "line_convention": "LF_bytes_1_based_inclusive",
        "source_pins": {"layout": {"byte_count": len(raw), "sha256": digest(raw)}},
        "required_gap_ids": sorted(audit.REQUIRED_GAPS), "groups": groups,
        "value_bindings": bindings,
    }
    inventory = {
        "schema_version": audit.INVENTORY_SCHEMA, "boundary": deepcopy(audit.BOUNDARY),
        "spans": spans, "occurrences": rows,
        "unchecked_line_ranges": [[1, 1], [9, 9]], "supplement_reviewed": False,
        "unresolved_gaps": [{"id": key, "status": "unresolved",
                             "detail": "Synthetic unresolved issue", "spans": []}
                            for key in sorted(audit.REQUIRED_GAPS)],
    }
    return {"contract": contract, "inventory": inventory, "source": source,
            "contract_path": tmp_path / "contract.json",
            "inventory_path": tmp_path / "inventory.json"}


def write_packet(packet):
    contract = json.dumps(packet["contract"], sort_keys=True).encode()
    packet["contract_path"].write_bytes(contract)
    packet["inventory"]["contract_sha256"] = digest(contract)
    inventory = json.dumps(packet["inventory"], sort_keys=True).encode()
    packet["inventory_path"].write_bytes(inventory)
    return packet["contract_path"], digest(contract), packet["inventory_path"], digest(inventory)


def run(packet):
    return audit.audit_occurrences(*write_packet(packet), {"layout": packet["source"]})


def row(packet, name):
    return next(x for x in packet["inventory"]["occurrences"] if x["id"] == name)


def group(packet, name):
    return next(x for x in packet["contract"]["groups"] if x["id"] == name)


def test_bounded_receipt_keeps_three_distinct_counting_and_policy_concepts(packet):
    receipt = run(packet)
    assert receipt["occurrence_count"] == 10
    assert receipt["primary_printed_test_ids"] == ["PR49", "PR59"]
    assert receipt["repeated_report_occurrences"] == 1
    assert receipt["independent_measurement_denominator"] is None
    assert receipt["repeats_without_primary_numeric_value"] == []
    assert receipt["counts_by_category"]["functional_reference"] == 1
    assert receipt["assigned_role"] is None
    assert not receipt["admitted"] and not receipt["full_source_clearance"]
    assert not receipt["transcription_truth_established"]
    assert receipt["review_status"] == "blocked_review"


@pytest.mark.parametrize("target", ["contract_path", "inventory_path"])
def test_caller_pins_reject_changed_json(packet, target):
    args = write_packet(packet)
    packet[target].write_bytes(packet[target].read_bytes() + b" ")
    with pytest.raises(ValueError, match="caller_json_sha256_mismatch"):
        audit.audit_occurrences(*args, {"layout": packet["source"]})


def test_retained_source_bytes_must_match_even_when_json_is_resealed(packet):
    packet["source"].write_bytes(packet["source"].read_bytes() + b"changed")
    with pytest.raises(ValueError, match="retained_source_pin_mismatch"):
        run(packet)


def test_span_mismatch_fails_even_after_repinning_whole_source(packet):
    raw = packet["source"].read_bytes().replace(b"0.077", b"0.099")
    packet["source"].write_bytes(raw)
    packet["contract"]["source_pins"]["layout"]["sha256"] = digest(raw)
    with pytest.raises(ValueError, match="span_sha256_mismatch"):
        run(packet)


@pytest.mark.parametrize("name", ["olanzapine", "SB258585"])
def test_no_posthoc_drop_of_either_reference(packet, name):
    packet["inventory"]["occurrences"].remove(row(packet, name))
    with pytest.raises(ValueError, match="incomplete_required_inventory"):
        run(packet)


def test_duplicate_occurrence_cannot_inflate_inventory(packet):
    duplicate = deepcopy(row(packet, "primary49"))
    duplicate["id"] = "another-id"
    packet["inventory"]["occurrences"].append(duplicate)
    with pytest.raises(ValueError, match="unexpected_or_duplicate_occurrence"):
        run(packet)


def test_span_alias_cannot_duplicate_same_physical_occurrence(packet):
    duplicate = deepcopy(row(packet, "radioligand"))
    duplicate.update(id="alias", group="alias", span="alias")
    duplicate_group = deepcopy(group(packet, "radioligand"))
    duplicate_group.update(id="alias", span="alias")
    duplicate_span = deepcopy(next(x for x in packet["inventory"]["spans"]
                                   if x["id"] == "radioligand"))
    duplicate_span["id"] = "alias"
    packet["contract"]["groups"].append(duplicate_group)
    packet["inventory"]["spans"].append(duplicate_span)
    packet["inventory"]["occurrences"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate_semantic_occurrence"):
        run(packet)


@pytest.mark.parametrize("field,value", [
    ("graph_inclusion", "included"), ("assigned_role", "fit"), ("admitted", True),
    ("independent_measurement_count", 1), ("activity_label", "inactive"),
    ("admitted", 0), ("inventory_included", 1),
])
def test_no_authority_or_denominator_from_inventory(packet, field, value):
    row(packet, "repeat49")[field] = value
    with pytest.raises(ValueError, match="occurrence_authority_or_denominator"):
        run(packet)


def test_functional_reference_cannot_become_binding_ki_with_resealed_contract(packet):
    row(packet, "SB258585")["endpoint"] = "Ki"
    group(packet, "SB258585")["endpoint"] = "Ki"
    with pytest.raises(ValueError, match="category_endpoint_mismatch"):
        run(packet)


def test_reference_origin_cannot_become_new_measurement_by_resealing(packet):
    row(packet, "olanzapine")["origin"] = "author_reported_test_result"
    group(packet, "olanzapine")["origin"] = "author_reported_test_result"
    with pytest.raises(ValueError, match="reference_origin_unresolved"):
        run(packet)


def test_same_span_value_from_wrong_endpoint_fails_position_binding(packet):
    row(packet, "functional49")["value"]["token"] = "0.077"
    packet["contract"]["value_bindings"]["functional49"]["value"]["token"] = "0.077"
    with pytest.raises(ValueError, match="value_source_position_mismatch"):
        run(packet)


@pytest.mark.parametrize("name", ["missing66", "cytotoxic66"])
def test_missingness_never_becomes_zero_or_activity_label(packet, name):
    row(packet, name)["value"]["token"] = "0"
    with pytest.raises(ValueError, match="missingness_is_not_numeric"):
        run(packet)


def test_nt_cannot_be_receptor_ki_even_when_group_resealed(packet):
    row(packet, "cytotoxic66")["endpoint"] = "Ki"
    group(packet, "cytotoxic66")["endpoint"] = "Ki"
    # Same compound/span/target/endpoint already exists as ND: either rejection is valid.
    with pytest.raises(ValueError, match="duplicate_semantic_occurrence|NT_endpoint_mismatch"):
        run(packet)


def test_repeat_must_link_same_endpoint_and_compound(packet):
    row(packet, "repeat49")["repeat_of"] = "primary59"
    with pytest.raises(ValueError, match="invalid_repeat_relation"):
        run(packet)


def test_untranscribed_primary_value_is_explicitly_unverified_repeat(packet):
    row(packet, "primary49")["value"] = {
        "kind": "not_transcribed", "token": None, "unit": None, "sd": None}
    del packet["contract"]["value_bindings"]["primary49"]
    assert run(packet)["repeats_without_primary_numeric_value"] == ["repeat49"]


@pytest.mark.parametrize("gap_id", sorted(audit.REQUIRED_GAPS))
def test_required_unresolved_gap_cannot_be_removed(packet, gap_id):
    packet["inventory"]["unresolved_gaps"] = [
        x for x in packet["inventory"]["unresolved_gaps"] if x["id"] != gap_id]
    with pytest.raises(ValueError, match="missing_required_gap"):
        run(packet)


def test_conflict_cannot_be_declared_resolved(packet):
    next(x for x in packet["inventory"]["unresolved_gaps"]
         if x["id"] == "PR65_PR66_conflict")["status"] = "resolved"
    with pytest.raises(ValueError, match="gap_status_or_source"):
        run(packet)


def test_unchecked_regions_cannot_be_silently_removed(packet):
    packet["inventory"]["unchecked_line_ranges"] = []
    with pytest.raises(ValueError, match="unchecked_span_coverage"):
        run(packet)


def test_cited_mention_cannot_become_measurement_by_resealing(packet):
    row(packet, "cited")["origin"] = "author_reported_test_result"
    group(packet, "cited")["origin"] = "author_reported_test_result"
    with pytest.raises(ValueError, match="nonmeasurement_origin"):
        run(packet)


def test_duplicate_json_keys_rejected_even_with_correct_caller_hash(packet):
    args = list(write_packet(packet))
    raw = b'{"schema_version":"a","schema_version":"b"}'
    packet["inventory_path"].write_bytes(raw)
    args[3] = digest(raw)
    with pytest.raises(ValueError, match="duplicate_json_key"):
        audit.audit_occurrences(*args, {"layout": packet["source"]})


def test_cli_requires_exact_source_set_and_prints_bounded_receipt(packet, capsys):
    cp, ch, ip, ih = write_packet(packet)
    args = ["--contract", str(cp), "--contract-sha256", ch,
            "--inventory", str(ip), "--inventory-sha256", ih,
            "--source", "layout=" + str(packet["source"])]
    assert audit.main(args) == 0
    assert json.loads(capsys.readouterr().out)["scope"] == (
        "retained_byte_and_inventory_consistency_only")
    with pytest.raises(SystemExit):
        audit.main(args + ["--source", "layout=" + str(packet["source"])])


def test_committed_inventory_is_bounded_and_keeps_known_source_anchors():
    root = Path(__file__).resolve().parents[2]
    contract = json.loads((root / "docs/evidence/human_5ht6_2024_occurrence_contract_v1.json")
                          .read_text())
    inventory = json.loads((root / "docs/evidence/human_5ht6_2024_occurrences_v1.json")
                           .read_text())
    audit.validate_contract(contract)
    rows = {x["id"]: x for x in inventory["occurrences"]}
    primary = [x for x in rows.values() if x["relation"] == "reported_primary"]
    assert {x["entity"] for x in primary} == {f"PR{x}" for x in range(1, 79)}
    for entity, mean, sd in [("PR49", "0.077", "0.018"), ("PR59", "1.964", "0.452")]:
        assert rows["table4:" + entity]["value"] == {
            "kind": "numeric", "token": mean, "sd": sd, "unit": "uM"}
    assert rows["table6_reference_olanzapine:olanzapine"]["endpoint"] == "Ki"
    assert rows["table6_reference_SB258585:SB258585"]["endpoint"] == "KB"
    assert all(x["graph_inclusion"] == "unknown" and x["assigned_role"] is None
               and x["admitted"] is False for x in rows.values())
    assert inventory["unchecked_line_ranges"] and not inventory["supplement_reviewed"]
