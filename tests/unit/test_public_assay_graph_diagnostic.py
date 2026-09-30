"""Synthetic metadata-only typed graph explanations."""

from copy import deepcopy
import hashlib
import json

import pytest

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_graph_diagnostic as graph
from betelgeuze_product import public_assay_preflight as preflight


def node(name, keys=(), *, role=None, protected=False):
    result = components.node_from_raw(
        {}, None, node_id=name, record_id=name, ligand_id="", protected=protected
    )
    result["keys"] = [[kind, components.digest(value)] for kind, value in keys]
    if role is not None:
        result["policy_declarations"] = [{"role": role}]
    return result


def by_id(report):
    return {row["candidate_id"]: row for row in report["results"]}


@pytest.mark.parametrize("kind", ["canonical", "document", "scaffold"])
def test_direct_typed_overlap_to_reserved(kind):
    candidate = node("candidate:a", [(kind, "shared")])
    reserved = node("external:reserved", [(kind, "shared")], role="calibration")
    row = by_id(graph.diagnostic([reserved], [candidate]))["candidate:a"]
    assert row["authoritative_preflight"]["status"] == "blocked_identity"
    assert row["direct_summary_by_key_kind"] == [
        {
            "key_kind": kind,
            "context_node_count": 1,
            "candidate_node_count": 0,
            "reserved_node_count": 1,
            "unknown_policy_node_count": 0,
        }
    ]
    witness = row["boundary_witness"]
    assert witness["status"] == "boundary_found"
    assert [(step["key_kind"], step["to_node_id"]) for step in witness["segments"]] == [
        (kind, "external:reserved")
    ]


def test_three_edge_mixed_bridge_is_transitive_not_direct():
    candidate = node("candidate:a", [("canonical", "c")])
    bridge_one = node("external:b1", [("canonical", "c"), ("document", "d")])
    bridge_two = node("external:b2", [("document", "d"), ("scaffold", "s")])
    reserved = node("external:r", [("scaffold", "s")], role="development_test")
    row = by_id(graph.diagnostic([bridge_one, bridge_two, reserved], [candidate]))[
        "candidate:a"
    ]
    assert row["direct_summary_by_key_kind"][0]["context_node_count"] == 1
    assert [step["key_kind"] for step in row["boundary_witness"]["segments"]] == [
        "canonical",
        "document",
        "scaffold",
    ]
    assert [step["to_node_id"] for step in row["boundary_witness"]["segments"]] == [
        "external:b1",
        "external:b2",
        "external:r",
    ]


def test_candidate_candidate_document_link_propagates():
    a = node("candidate:a", [("document", "paper")])
    b = node("candidate:b", [("document", "paper"), ("canonical", "ligand")])
    reserved = node("external:r", [("canonical", "ligand")], role="calibration")
    report = graph.diagnostic([reserved], [a, b])
    row = by_id(report)["candidate:a"]
    assert row["candidate_document_links"] == ["candidate:b"]
    assert [step["to_node_id"] for step in row["boundary_witness"]["segments"]] == [
        "candidate:b",
        "external:r",
    ]
    assert all(
        item["authoritative_preflight"]["status"] == "blocked_identity"
        for item in report["results"]
    )


def test_unknown_and_self_reserved_boundaries():
    unknown = node("candidate:unknown", role="unrecognized_role")
    self_reserved = node("candidate:reserved", protected=True)
    rows = by_id(graph.diagnostic([], [unknown, self_reserved]))
    assert rows["candidate:unknown"]["boundary_witness"]["boundary_reasons"] == [
        "unknown_policy"
    ]
    assert rows["candidate:reserved"]["boundary_witness"]["boundary_reasons"] == [
        "reserved"
    ]
    assert all(row["boundary_witness"]["segments"] == [] for row in rows.values())


def test_disconnected_and_permutation_stable():
    candidate = node("candidate:a", [("canonical", "a")])
    second = node("candidate:b", [("document", "b")])
    clear = node("external:clear", [("canonical", "a")])
    reserved = node("external:reserved", [("document", "other")], role="calibration")
    a = graph.diagnostic([clear, reserved], [candidate, second])
    b = graph.diagnostic([reserved, clear], [second, candidate])
    assert by_id(a) == by_id(b)
    row = by_id(a)["candidate:a"]
    assert row["boundary_witness"]["status"] == "no_boundary_in_supplied_graph"
    assert row["authoritative_preflight"]["status"] == "identity_incomplete"
    assert row["direct_summary_by_key_kind"][0]["context_node_count"] == 1


def test_high_degree_key_is_scanned_once_and_cap_is_explicit():
    candidate = node("candidate:a", [("document", "large")])
    context = [node(f"external:{i:04d}", [("document", "large")]) for i in range(300)]
    context[-1]["policy_declarations"] = [{"role": "calibration"}]
    report = graph.diagnostic(context, [candidate], max_witness_visits=301)
    row = report["results"][0]
    assert row["boundary_witness"]["status"] == "boundary_found"
    assert row["boundary_witness"]["incidence_visits"] <= 301
    assert row["direct_summary_by_key_kind"][0]["reserved_node_count"] == 1
    exhausted = graph.diagnostic(context, [candidate], max_witness_visits=100)
    assert exhausted["diagnostic_complete"] is False
    assert (
        exhausted["results"][0]["boundary_witness"]["status"]
        == "incomplete_resource_cap"
    )
    with pytest.raises(ValueError, match="incidence_capacity_exceeded"):
        graph.diagnostic(context, [candidate], max_incidences=100)


def test_cli_binds_inputs_and_authoritative_preflight(tmp_path):
    candidate = node("candidate:a", [("canonical", "same")])
    reserved = node("external:r", [("canonical", "same")], role="calibration")
    context_path = tmp_path / "context.jsonl"
    candidate_path = tmp_path / "candidates.json"
    preflight_path = tmp_path / "preflight.json"
    output_path = tmp_path / "diagnostic.json"
    context_path.write_text(components.canonical(reserved) + "\n")
    candidate_path.write_text(components.canonical([candidate]))

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    expected = preflight.preflight([reserved], [candidate])
    expected.update(
        context_sha256=sha(context_path),
        candidates_sha256=sha(candidate_path),
        implementation_sha256=preflight.implementation_hashes(),
    )
    preflight_path.write_text(json.dumps(expected))
    args = [
        "--context",
        str(context_path),
        "--context-sha256",
        sha(context_path),
        "--candidates",
        str(candidate_path),
        "--candidates-sha256",
        sha(candidate_path),
        "--preflight",
        str(preflight_path),
        "--preflight-sha256",
        sha(preflight_path),
        "--output",
        str(output_path),
    ]
    assert graph.main(args) == 0
    observed = json.loads(output_path.read_text())
    assert observed["results"][0]["authoritative_preflight"] == expected["results"][0]
    assert observed["preflight_sha256"] == sha(preflight_path)
    with pytest.raises(FileExistsError):
        graph.main(args)
    tampered = deepcopy(expected)
    tampered["results"][0]["status"] = "identity_clear_review_required"
    preflight_path.write_text(json.dumps(tampered))
    args[-1] = str(tmp_path / "other.json")
    args[args.index("--preflight-sha256") + 1] = sha(preflight_path)
    with pytest.raises(ValueError, match="authoritative_preflight_mismatch"):
        graph.main(args)
    assert not (tmp_path / "other.json").exists()
