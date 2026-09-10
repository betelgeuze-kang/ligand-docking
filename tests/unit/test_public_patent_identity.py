"""New synthetic controls; no protected outcomes or patent activity values."""

from copy import deepcopy
import pytest
from tools.product import public_assay_components as c
from tools.product import train_public_assay_selector as trainer


@pytest.mark.parametrize(
    "value", ["US-8552005-B2", "US8552005B2", "us 8552005 b2", " US08552005B2 "]
)
def test_explicit_grant_spelling_variants_share_publication_key(value):
    raw = {"Patent Number": value, "Article DOI": "doi:10.synthetic/a", "PMID": "999"}
    before = deepcopy(raw)
    assert c.document_keys(raw) == [
        "doi:10.synthetic/a",
        "pmid:999",
        "patent:US8552005B2",
    ]
    assert raw == before


@pytest.mark.parametrize(
    "value",
    [
        False,
        0,
        [],
        {},
        "US8552005",
        "8552005B2",
        "WO2013030123A1",
        "US8552005B3",
        "US8552005B2;US8552017B2",
        "US8-552-005B2",
        "US8552005B2 trailing",
        "US８５５２００５B2",
    ],
)
def test_unsupported_or_ambiguous_patent_is_not_silently_omitted(value):
    with pytest.raises(ValueError, match="patent"):
        c.document_keys({"Patent Number": value})


@pytest.mark.parametrize("value", [None, "", "  "])
def test_absent_optional_patent_preserves_existing_keys(value):
    assert c.document_keys(
        {"Patent Number": value, "ChEMBL Document ID": "CHEMBL1"}
    ) == ["chembl:document:CHEMBL1"]


def test_two_native_fields_must_identify_same_publication():
    assert c.document_keys(
        {"Patent Number": "US8552005B2", "ChEMBL Patent ID": "US-8552005-B2"}
    ) == ["patent:US8552005B2"]
    with pytest.raises(ValueError, match="conflicting_patent"):
        c.document_keys(
            {"Patent Number": "US8552005B2", "ChEMBL Patent ID": "US8552017B2"}
        )


def node(name, raw):
    return c.node_from_raw(
        raw, None, node_id="external:" + name, record_id=name, ligand_id=""
    )


def test_native_bindingdb_and_chembl_spelling_propagate_reserved_role():
    raw = {
        "ChEMBL Patent ID": "US-8552005-B2",
        "ChEMBL Document ID": "CHEMBL3639354",
        "ChEMBL Assay ID": "CHEMBL3705065",
        "role": "unassigned",
    }
    a = node("candidate", raw)
    b = node(
        "reserved",
        {
            "Patent Number": "US8552005B2",
            "dataset_split": "development_test",
            "evaluation_only": True,
        },
    )
    graph = c.component_index([a, b])
    assert graph[a["node_id"]]["component_id"] == graph[b["node_id"]]["component_id"]
    assert graph[a["node_id"]]["blocked"]
    assert b["policy_declarations"] == [
        {"dataset_split": "development_test", "evaluation_only": True}
    ]
    assert a["chemical_identity_available"] is False


def test_distinct_grant_kind_and_number_are_not_inferred_family_aliases():
    nodes = [
        node(str(i), {"Patent Number": value})
        for i, value in enumerate(["US8552005B1", "US8552005B2", "US8552017B2"])
    ]
    graph = c.component_index(nodes)
    assert len({graph[n["node_id"]]["component_id"] for n in nodes}) == 3


def test_actual_cohort_rejects_reserved_patent_before_reading_observations():
    from tests.unit.test_public_assay_selector import rows

    class Forbidden:
        def __iter__(self):
            raise AssertionError("reserved_patent_observation_read")

    values = rows()
    values[0]["source_provenance"]["row"]["Patent Number"] = "US8552005B2"
    values[0]["observations"] = Forbidden()
    external = node(
        "patent-reservation",
        {"ChEMBL Patent ID": "US-8552005-B2", "role": "calibration"},
    )
    context = [c.normalized_node(r) for r in values] + [external]
    accepted, ledger = trainer.cohort(
        values, "a" * 64, "IC50", identity_context=context
    )
    assert values[0]["record_id"] not in {r["record_id"] for r in accepted}
    assert len(ledger) == 60


def test_old_patent_omitting_node_fails_native_coverage_after_migration():
    from tests.unit.test_public_assay_selector import rows

    values = rows()
    old = [c.normalized_node(r) for r in values]
    values[0]["source_provenance"]["row"]["Patent Number"] = "US8552005B2"
    with pytest.raises(ValueError):
        c.require_normalized_coverage(values, old)


def test_native_document_patent_is_used_without_flattening():
    raw = {"ChEMBL document metadata": {"patent_id": "US-10441590-B2"}}
    before = deepcopy(raw)
    assert c.document_keys(raw) == ["patent:US10441590B2"]
    assert raw == before
    raw["ChEMBL Patent ID"] = "US8552005B2"
    with pytest.raises(ValueError, match="conflicting_patent"):
        c.document_keys(raw)


def test_chembl_metadata_consumer_binds_flat_patent_to_native_document():
    from tools.product import public_chembl_assay_dataset as intake

    native = dict.fromkeys(intake.METADATA_FIELDS)
    native.update(
        assay_chembl_id="CHEMBL1",
        document_chembl_id="CHEMBL2",
        molecule_chembl_id="CHEMBL3",
        src_id=37,
    )
    raw = {
        "ChEMBL activity metadata": native,
        "ChEMBL Assay ID": "CHEMBL1",
        "ChEMBL Document ID": "CHEMBL2",
        "ChEMBL document metadata": {
            "document_chembl_id": "CHEMBL2",
            "doc_type": "PATENT",
            "patent_id": "US-8552005-B2",
        },
    }
    row = {"ligand_id": "chembl:molecule:CHEMBL3", "source_provenance": {"row": raw}}
    before = deepcopy(row)
    assert intake.validate_metadata_row(row) == native
    assert row == before
    assert "patent:US8552005B2" in c.document_keys(raw)
    raw["ChEMBL Patent ID"] = "US8552005B2"
    intake.validate_metadata_row(row)
    raw["ChEMBL Patent ID"] = "US8552017B2"
    with pytest.raises(ValueError, match="patent_projection_mismatch"):
        intake.validate_metadata_row(row)
    del raw["ChEMBL document metadata"]["patent_id"]
    with pytest.raises(ValueError, match="patent_projection_mismatch"):
        intake.validate_metadata_row(row)


def test_staged_native_intake_preserves_patent_then_blocks_before_archive_read(
    tmp_path, monkeypatch
):
    from tools.product import public_bindingdb_staged_intake as intake
    from tests.unit.test_public_bindingdb_staged_intake import (
        fixture,
        build,
        rows,
        dump,
        dump_rows,
        refresh_manifest,
    )

    def add_patent(raws):
        raws[0]["Patent Number"] = "US8552005B2"

    data = fixture(tmp_path / "native-patent", mutate=add_patent)
    root, manifest, _, metadata, plan = data
    positive = build(data)
    assert positive["labels_retrieved"] == plan["counts"]["fit"]
    assert metadata[0]["source_provenance"]["row"]["Patent Number"] == "US8552005B2"
    assert len(rows(root / "intake/records.jsonl")) == 60
    context = [c.normalized_node(row) for row in metadata]
    context.append(
        node(
            "synthetic-reserved-patent",
            {
                "ChEMBL document metadata": {"patent_id": "US-8552005-B2"},
                "dataset_split": "development_test",
                "evaluation_only": True,
            },
        )
    )
    manifest["identity_context"] = {
        **dump_rows(root / "reserved-context.jsonl", context),
        "expected_nodes": len(context),
    }
    plan["identity_context_sha256"] = manifest["identity_context"]["sha256"]
    manifest["split_plan"] = dump(root / "reserved-plan.json", plan)
    refresh_manifest(data)

    def forbidden(*args, **kwargs):
        raise AssertionError("reserved_patent_archive_opened")

    monkeypatch.setattr(intake.zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="reserved_metadata_component"):
        build(data, suffix="must-reject")
