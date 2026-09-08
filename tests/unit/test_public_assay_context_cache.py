"""Synthetic-only cache bridge controls; never call feature generation or fitting.

The real trainer is exercised with fresh synthetic input and observation traps.
"""
from copy import deepcopy
import json

import pytest

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as intake
from tools.product import train_public_assay_selector as trainer
from tests.unit.test_public_assay_selector import bundle, rows, write_context


class ObservationAccess(AssertionError):
    pass


class ForbiddenObservations:
    def __init__(self, accesses, record_id):
        self.accesses = accesses
        self.record_id = record_id

    def __iter__(self):
        self.accesses.append(self.record_id)
        raise ObservationAccess("observation_access_before_complete_metadata_admission")


def excluded_bridge(values):
    """One excluded vertex connects document group 0 to chemistry group 1."""
    bridge = deepcopy(values[0])
    bridge.update(record_id="synthetic:excluded-bridge", target_state_sha256="b" * 64,
                  eligible_for_split_assignment=False,
                  admission_issues=["synthetic_reserved_source"])
    bridge["chemical_identity"] = deepcopy(values[5]["chemical_identity"])
    bridge["source_provenance"]["row"]["role"] = "calibration"
    bridge["observations"] = []
    return components.normalized_node(bridge)


def test_complete_bridge_context_blocks_reserved_observations():
    values = rows()
    bridge = excluded_bridge(values)
    context = [components.normalized_node(row) for row in values] + [bridge]
    graph = components.component_index(context)
    first = graph[components.normalized_node(values[0])["node_id"]]
    second = graph[components.normalized_node(values[5])["node_id"]]
    assert first["component_id"] == second["component_id"]
    assert first["blocked"] and second["blocked"]
    accesses = []
    for row in values[:10]:
        row["observations"] = ForbiddenObservations(accesses, row["record_id"])
    accepted, ledger = trainer.cohort(values[:10], "a" * 64, "IC50", identity_context=context)
    assert accepted == [] and len(ledger) == 10
    assert {entry["reason"] for entry in ledger} == {"reserved_identity_component"}
    assert accesses == []


@pytest.mark.parametrize("refresh_node_set_binding", [False, True], ids=["bound-node-set", "ledger-before-cohort"])
def test_same_size_replacement_of_excluded_bridge_is_rejected_before_observations(tmp_path, monkeypatch, refresh_node_set_binding):
    source = bundle(tmp_path)
    values = rows()
    bridge = excluded_bridge(values)
    with (source / "ledger.jsonl").open("a") as out:
        out.write(intake.json_text({"record_id": bridge["record_id"],
                                  "target_state_sha256": "b" * 64,
                                  "status": "excluded", "reason": "synthetic_reserved_source"}) + "\n")
    write_context(source, values, extra_nodes=[bridge])
    summary = json.loads((source / "summary.json").read_text())
    summary["requested_target_rows"] = 61
    nodes = [components.loads(line) for line in (source / "identity-context.jsonl").read_text().splitlines()]
    assert len(nodes) == summary["identity_context_source_rows"] == 61
    assert summary["identity_context_external_rows"] == 0
    assert any(node["node_id"] == bridge["node_id"] for node in nodes)

    # Keep the declared counts and all normalized-row nodes intact. Replace only
    # the excluded bridge with a valid but unrelated node; refresh the cache hash
    # so neither a length check nor a stale-byte checksum is the rejection reason.
    other = deepcopy(values[-1])
    other.update(record_id="synthetic:unrelated-replacement", target_state_sha256="c" * 64)
    other["source_provenance"]["row"].update({"Article DOI": "synthetic:unrelated-document",
                                              "role": "development_pool"})
    other["chemical_identity"] = intake.chemical_identity("C" * 30)
    replacement = components.normalized_node(other)
    # Keep the archived occurrence identity and position consistent. Replacing
    # its metadata must be detected by the bound node set, or (when deliberately
    # rebound below) by the independently retained excluded ledger record.
    replacement["node_id"] = bridge["node_id"]
    replacement["source"] = deepcopy(bridge["source"])
    assert replacement["record_id"] != bridge["record_id"]
    nodes = [replacement if node["node_id"] == bridge["node_id"] else node for node in nodes]
    (source / "identity-context.jsonl").write_text("".join(intake.json_text(node) + "\n" for node in nodes))
    summary["identity_context_sha256"] = intake.file_sha(source / "identity-context.jsonl")
    if refresh_node_set_binding:
        summary["identity_context_source_nodes_sha256"] = intake.digest(
            intake.json_text(sorted(nodes, key=lambda node: node["node_id"])))
    (source / "summary.json").write_text(json.dumps(summary))
    assert len(nodes) == summary["identity_context_source_rows"] + summary["identity_context_external_rows"]
    assert intake.file_sha(source / "records.jsonl") == summary["records_sha256"]
    assert intake.file_sha(source / "ledger.jsonl") == summary["ledger_sha256"]
    graph = components.require_normalized_coverage(values, nodes)
    assert not graph[components.normalized_node(values[0])["node_id"]]["blocked"]
    assert not any(node["record_id"] == bridge["record_id"] for node in nodes)

    accesses = []
    real_loads = json.loads

    def load_with_observation_trap(data, *args, **kwargs):
        value = real_loads(data, *args, **kwargs)
        if isinstance(value, dict) and value.get("schema_version") == intake.SCHEMA and "observations" in value:
            value["observations"] = ForbiddenObservations(accesses, value["record_id"])
        return value

    def forbidden_feature_or_fit(*args, **kwargs):
        raise AssertionError("synthetic_cache_rejection_must_not_generate_features_or_fit")

    monkeypatch.setattr(trainer.json, "loads", load_with_observation_trap)
    monkeypatch.setattr(trainer, "features", forbidden_feature_or_fit)
    monkeypatch.setattr(trainer.Ridge, "fit", forbidden_feature_or_fit)
    rejection = ("intake_ledger_missing_from_identity_context" if refresh_node_set_binding
                 else "identity_context_node_set_mismatch")
    with pytest.raises(ValueError, match=rejection):
        trainer.run(input_dir=source, summary_sha256=intake.file_sha(source / "summary.json"),
                    target_state="a" * 64, endpoint="IC50", output_dir=tmp_path / "trained")
    assert accesses == []
    assert not (tmp_path / "trained").exists()
