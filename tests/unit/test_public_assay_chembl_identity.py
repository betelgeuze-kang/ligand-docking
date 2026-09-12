"""Synthetic ChEMBL assay identity regressions; portable repository imports only."""

from copy import deepcopy
import hashlib
import pytest
from tools.product import public_assay_components as c

ASSAY = "ChEMBL Assay ID"
DOCUMENT = "ChEMBL Document ID"
PARENT = "ChEMBL Parent Molecule ID"
V1 = "public_assay_identity_context_v1"
V2 = "public_assay_identity_context_v2"


def node(number, raw=None, *, molecule=None, api=c):
    origin = {
        "source_sha256": c.digest("synthetic-common-chembl-identity"),
        "source_member": "synthetic-metadata.jsonl",
        "source_line": number,
    }
    return api.node_from_raw(
        {} if raw is None else raw,
        None,
        node_id="external:" + c.digest(c.canonical(origin)),
        record_id="chembl:activity:synthetic-" + str(number),
        ligand_id="chembl:molecule:"
        + (f"CHEMBL{number}" if molecule is None else molecule),
        origin=origin,
    )


def normalized(number, raw=None, *, molecule=None):
    n = node(number, raw, molecule=molecule)
    return {
        "record_id": n["record_id"],
        "ligand_id": "chembl:molecule:"
        + (f"CHEMBL{number}" if molecule is None else molecule),
        "identity_context_node_id": n["node_id"],
        "chemical_identity": None,
        "source_provenance": dict(n["source"], row={} if raw is None else raw),
    }


@pytest.mark.parametrize("value", ["CHEMBL1", "CHEMBL901", "CHEMBL000901"])
def test_valid_assay_has_distinct_kind_and_explicit_v2(value):
    n = node(1, {ASSAY: value})
    assert n["schema_version"] == V2
    assert ("source_assay", c.digest("chembl:assay:" + value)) in n["keys"]
    assert not n["document_identity_available"] and not n["chemical_identity_available"]
    assert not any(k[0] == "document" for k in n["keys"])
    c.validate_node(n)
    assert n["node_id"] in c.component_index([n])


@pytest.mark.parametrize(
    "value",
    [
        False,
        True,
        0,
        7,
        -1,
        1.2,
        [],
        {},
        " ",
        "CHEMBL",
        "chembl1",
        " CHEMBL1",
        "CHEMBL1 ",
        "CHEMBL-1",
        "CHEMBL1suffix",
        "CHEMBL１",
        "https://chembl/CHEMBL1",
    ],
)
def test_malformed_or_wrong_type_assay_is_explicitly_rejected(value):
    with pytest.raises(ValueError, match="invalid_chembl_assay_id"):
        node(1, {ASSAY: value})


def test_same_assay_different_documents_and_molecules_propagates_reservation():
    a = node(1, {ASSAY: "CHEMBL800", DOCUMENT: "CHEMBL901", "role": "calibration"})
    b = node(2, {ASSAY: "CHEMBL800", DOCUMENT: "CHEMBL902"})
    index = c.component_index([a, b])
    assert index[b["node_id"]]["blocked"] and index[b["node_id"]]["node_count"] == 2


def test_other_endpoint_invalid_chemical_bridge_preserves_reservation():
    # Endpoint and target labels are synthetic row metadata, not graph edges or outcomes.
    reserved = node(1, {DOCUMENT: "CHEMBL901", "role": "development_test"})
    bridge = node(
        2,
        {
            ASSAY: "CHEMBL800",
            DOCUMENT: "CHEMBL901",
            "endpoint": "other-synthetic-endpoint",
            "target": "other-synthetic-target",
        },
    )
    query = node(3, {ASSAY: "CHEMBL800", DOCUMENT: "CHEMBL902"})
    assert not bridge["chemical_identity_available"]
    assert c.component_index([reserved, bridge, query])[query["node_id"]]["blocked"]
    assert not c.component_index([reserved, query])[query["node_id"]]["blocked"]


def test_distinct_assays_documents_and_molecules_remain_independent_positive():
    a = node(1, {ASSAY: "CHEMBL800", DOCUMENT: "CHEMBL901", "role": "development_test"})
    b = node(2, {ASSAY: "CHEMBL801", DOCUMENT: "CHEMBL902"})
    index = c.component_index([a, b])
    assert index[a["node_id"]]["blocked"] and not index[b["node_id"]]["blocked"]
    assert index[a["node_id"]]["component_id"] != index[b["node_id"]]["component_id"]


def test_mixed_v1_v2_graph_connects_through_document_and_parent():
    old_reserved = node(1, {"role": "calibration"}, molecule="CHEMBL700")
    v2_bridge = node(
        2, {ASSAY: "CHEMBL800", PARENT: "CHEMBL700", DOCUMENT: "CHEMBL901"}
    )
    v2_query = node(3, {ASSAY: "CHEMBL800"})
    v1_query = node(4, {DOCUMENT: "CHEMBL901"})
    assert old_reserved["schema_version"] == v1_query["schema_version"] == V1
    assert v2_bridge["schema_version"] == v2_query["schema_version"] == V2
    index = c.component_index([old_reserved, v2_bridge, v2_query, v1_query])
    assert all(v["blocked"] and v["node_count"] == 4 for v in index.values())


def test_v1_schema_cannot_smuggle_assay_kind():
    n = node(1)
    n["keys"].append(("source_assay", c.digest("chembl:assay:CHEMBL800")))
    with pytest.raises(ValueError, match="invalid_identity_context_key"):
        c.validate_node(n)
    with pytest.raises(ValueError, match="invalid_identity_context_key"):
        c.component_index([n])


def test_v2_requires_at_least_one_assay_identity_key():
    n = node(1)
    n["schema_version"] = V2
    with pytest.raises(ValueError, match="missing_assay_identity_context_key"):
        c.validate_node(n)
    with pytest.raises(ValueError, match="missing_assay_identity_context_key"):
        c.component_index([n])


@pytest.mark.parametrize(
    "version",
    [
        "public_assay_identity_context_v0",
        "public_assay_identity_context_v3",
        "other",
        "",
    ],
)
def test_unknown_schema_is_rejected_by_validation_and_component_index(version):
    n = node(1)
    n["schema_version"] = version
    with pytest.raises(ValueError):
        c.validate_node(n)
    with pytest.raises(ValueError):
        c.component_index([n])


def test_normalized_api_rebuilds_assay_document_parent_tokens_and_v2():
    raw = {
        ASSAY: "CHEMBL800",
        DOCUMENT: "CHEMBL901",
        PARENT: "CHEMBL700",
        "role": "fit",
    }
    row = normalized(1, raw)
    n = c.normalized_node(row)
    assert n["schema_version"] == V2
    assert set(n["keys"]) >= {
        ("source_assay", c.digest("chembl:assay:CHEMBL800")),
        ("document", c.digest("chembl:document:CHEMBL901")),
        ("source_ligand", c.digest("chembl:molecule:CHEMBL700")),
    }
    assert n["node_id"] in c.require_normalized_coverage([row], [n])


def test_v2_cache_deleted_assay_is_rejected_even_before_normalized_comparison():
    row = normalized(1, {ASSAY: "CHEMBL800"})
    n = c.normalized_node(row)
    assert n["schema_version"] == V2
    n["keys"] = [k for k in n["keys"] if k[0] != "source_assay"]
    with pytest.raises(ValueError, match="missing_assay_identity_context_key"):
        c.require_normalized_coverage([row], [n])


def test_downgraded_v1_cache_cannot_hide_missing_assay_token():
    row = normalized(1, {ASSAY: "CHEMBL800"})
    n = c.normalized_node(row)
    assert ("source_assay", c.digest("chembl:assay:CHEMBL800")) in n["keys"]
    n["schema_version"] = V1
    n["keys"] = [k for k in n["keys"] if k[0] != "source_assay"]
    c.validate_node(n)
    with pytest.raises(ValueError, match="normalized_identity_context_mismatch"):
        c.require_normalized_coverage([row], [n])


def test_different_assay_token_in_cache_is_rejected():
    row = normalized(1, {ASSAY: "CHEMBL800"})
    n = c.normalized_node(row)
    n["keys"] = [k for k in n["keys"] if k[0] != "source_assay"] + [
        ("source_assay", c.digest("chembl:assay:CHEMBL801"))
    ]
    with pytest.raises(ValueError, match="normalized_identity_context_mismatch"):
        c.require_normalized_coverage([row], [n])


def test_joined_role_roundtrip_and_order_invariance_in_mixed_graph():
    a = node(1, {ASSAY: "CHEMBL800", "role": "fit"})
    b = node(2, {ASSAY: "CHEMBL800"})
    a["joined_policy_sources"] = [
        {
            "source_sha256": "b" * 64,
            "source_member": "synthetic-policy.jsonl",
            "source_line": 1,
            "declarations": [{"evaluation_only": True, "dataset_split": "calibration"}],
        }
    ]
    before = deepcopy(a)
    serialized = [c.loads(c.canonical(n)) for n in [a, b]]
    assert c.node_set_sha([a, b]) == c.node_set_sha(serialized)
    assert c.component_index(serialized) == c.component_index(
        list(reversed(serialized))
    )
    assert c.component_index(serialized)[b["node_id"]]["blocked"]
    assert a == before


def test_legacy_and_assay_token_namespaces_never_alias():
    a = node(1, {ASSAY: "CHEMBL800", "role": "calibration"})
    b = node(2, {DOCUMENT: "CHEMBL800"})
    d = node(3, {"Article DOI": "chembl:assay:CHEMBL800"})
    index = c.component_index([a, b, d])
    assert not index[b["node_id"]]["blocked"] and not index[d["node_id"]]["blocked"]


def test_assay_graph_preserves_separate_activity_occurrences():
    a = node(1, {ASSAY: "CHEMBL800", "role": "calibration"})
    b = node(2, {ASSAY: "CHEMBL800"})
    b["record_id"] = a["record_id"]
    index = c.component_index([a, b])
    assert index[a["node_id"]]["node_count"] == 2 and index[b["node_id"]]["blocked"]


@pytest.mark.parametrize("optional", [{}, {ASSAY: None}, {ASSAY: ""}])
def test_v1_node_bytes_match_pinned_before_assay_helper(optional):
    raw = {DOCUMENT: "CHEMBL901", PARENT: "CHEMBL700", **optional}
    n = node(1, raw)
    assert n["schema_version"] == V1
    # Captured from pinned pre-assay helper 62f5db825eefd14d...532784f.
    assert (
        hashlib.sha256(c.canonical(n).encode()).hexdigest()
        == "e1931e089d3b00b0afbb21c3f61d0c708fcf3b44978af28828b44fe4fdddff0e"
    )
