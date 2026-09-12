"""Synthetic controls for explicit metadata-only publication version 2."""
from copy import deepcopy
import pytest
from tools.product import public_assay_components as c


@pytest.mark.parametrize("raw,expected", [
    ("US-20110166191-A1", "US20110166191A1"),
    ("US 2011/0166191 A1", "US20110166191A1"),
    ("us2011-0166191a1", "US20110166191A1"),
    ("US-20200172499-A9", "US20200172499A9"),
    ("EP-3607944-A1", "EP3607944A1"),
    ("EP0123456A1", "EP0123456A1"),
    ("WO-2020083926-A1", "WO2020083926A1"),
    ("WO 2020/083926 A1", "WO2020083926A1"),
    ("US08552005B2", "US8552005B2"),
])
def test_explicit_v2_retains_publication_sequence_and_kind(raw, expected):
    assert c.patent_publication(raw, version=2) == expected
    native = {"ChEMBL document metadata": {"patent_id": raw}}
    before = deepcopy(native)
    assert c.document_keys(native, patent_version=2) == ["patent:" + expected]
    assert native == before


@pytest.mark.parametrize("raw", ["WO2013030123A1", "EP3607944A1", "US20110166191A1"])
def test_default_v1_admission_does_not_expand_implicitly(raw):
    with pytest.raises(ValueError, match="unsupported_patent_publication"):
        c.document_keys({"Patent Number": raw})
    assert c.document_keys({"Patent Number": raw}, patent_version=2)


@pytest.mark.parametrize("raw", [
    "US2011166191A1", "US20110166191", "US20000166191A1", "US20110166191B2",
    "WO2083926A1", "WO2003083926A1", "WO2020083926B2", "EP360794A1",
    "JP2020083926A1", "EP0000000A1", "WO2020083926A1;EP3607944A1",
])
def test_v2_does_not_guess_missing_digits_country_kind_or_multiple_ids(raw):
    with pytest.raises(ValueError, match="unsupported_patent_publication"):
        c.patent_publication(raw, version=2)


@pytest.mark.parametrize("version", [True, 0, 3, "2", None])
def test_identity_version_is_explicit_and_strict_even_for_missing_patent(version):
    with pytest.raises(ValueError, match="unsupported_patent_identity_version"):
        c.document_keys({}, patent_version=version)


def test_v2_node_connects_reserved_spelling_without_inferring_grant_family():
    nodes = []
    for i, raw in enumerate([
        {"ChEMBL document metadata": {"patent_id": "US-20110166191-A1"}},
        {"Patent Number": "US2011/0166191A1", "dataset_split": "development_test"},
        {"Patent Number": "US8552005B2"},
        {"Patent Number": "US20110166191A9"},
    ]):
        nodes.append(c.node_from_raw(raw, None, node_id=f"external:synthetic:{i}",
                                    record_id=str(i), ligand_id="", patent_version=2))
    graph = c.component_index(nodes)
    assert graph[nodes[0]["node_id"]]["blocked"]
    assert graph[nodes[0]["node_id"]] == graph[nodes[1]["node_id"]]
    assert not graph[nodes[2]["node_id"]]["blocked"]
    assert not graph[nodes[3]["node_id"]]["blocked"]
    assert len({value["component_id"] for value in graph.values()}) == 3
