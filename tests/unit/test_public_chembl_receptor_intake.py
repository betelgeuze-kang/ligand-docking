"""Synthetic receptor intake controls, without protected or public outcomes."""

from copy import deepcopy
import json

import pytest

from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as bound
from tools.product import public_chembl_measurement as measurement
from tools.product import public_chembl_receptor_intake as receptor


def ref(tmp_path, value, name="source.json"):
    path = tmp_path / name
    path.write_text(json.dumps(value))
    return {"path": str(path), "sha256": common.file_sha(path)}


@pytest.mark.parametrize(
    "pointer", ["/-1", "/01", "not/a/pointer", "/+1", "/1.0", "/~2"]
)
def test_pointer_never_defaults_or_selects_last(tmp_path, pointer):
    entry = ref(tmp_path, ["first", "last"])
    with pytest.raises(ValueError):
        receptor.resolve({**entry, "pointer": pointer}, {})


def test_pointer_preserves_zero_and_copy(tmp_path):
    entry = ref(tmp_path, {"a/b": {"~": [0, {"role": "fit"}]}})
    cache = {}
    assert receptor.resolve({**entry, "pointer": "/a~1b/~0/0"}, cache) == 0
    receptor.resolve({**entry, "pointer": "/a~1b/~0/1"}, cache)["role"] = "test"
    assert receptor.resolve({**entry, "pointer": "/a~1b/~0/1"}, cache) == {
        "role": "fit"
    }


def profile():
    return {
        "evidence_scope": measurement.DB_CURATED_SCOPE,
        "evidence_kind": "experimental_label",
        "source_id": 37,
        "document_kind": "patent",
        "citation_identity_status": "resolved",
        "assay_method_evidence_status": "curated_description_bound",
        "endpoint_subtype": receptor.SUBTYPE,
        "requested_endpoint_subtype": receptor.SUBTYPE,
        "source_license": "CC-BY-SA-3.0",
        "target_state_status": "catalogue_annotation_only",
        "primary_source_status": "not_independently_verified",
        "assigned_role": "fit",
        "graph_blocked": False,
        "measurement_status": "exact",
        "potential_duplicate": 0,
        "data_validity_comment": None,
        "native_patent_identity_matches": True,
        "primary_point_correspondence": "unique_native_name_and_numeric_match",
        "primary_internal_conflicts": [],
    }


def test_new_source_profile_is_explicit_and_not_scientific_approval():
    source = profile()
    assert not measurement.admission(source, "fit")["eligible_for_declared_purpose"]
    out = measurement.admission(
        source, "fit", source_profile="chembl_receptor_research_v4"
    )
    assert out["eligible_for_declared_purpose"]
    assert not out["scientific_validation"] and not out["training_admitted"]
    assert not out["construct_verified"]
    assert out["source_metadata"] == source


@pytest.mark.parametrize(
    "key,value",
    [
        ("src_id", 1),
        ("source_id", True),
        ("native_patent_identity_matches", False),
        ("primary_point_correspondence", "numeric_only"),
        ("primary_internal_conflicts", ["inconsistent_Ki"]),
        ("primary_internal_conflicts", None),
        ("source_license", None),
        ("measurement_status", "censored"),
        ("potential_duplicate", 1),
        ("graph_blocked", True),
        ("assigned_role", "development_test"),
        ("source_policy_declarations", [{"nested": {"evaluation_only": True}}]),
    ],
)
def test_v4_rejects_unsupported_sources_and_labels(key, value):
    source = profile()
    source[key] = value
    assert not measurement.admission(
        source, "fit", source_profile="chembl_receptor_research_v4"
    )["eligible_for_declared_purpose"]


def test_endpoint_dispatch_does_not_relabel_older_receptor_schema():
    scope = {
        "endpoint": "Ki",
        "endpoint_subtype": receptor.SUBTYPE,
        "intake_source_kind": receptor.KIND,
    }
    assert bound.endpoint_contract(scope)["intake_schema"] == bound.SCHEMA_V4
    for key, value in [
        ("endpoint", "IC50"),
        ("endpoint_subtype", "enzyme_inhibition_Ki"),
        ("intake_source_kind", []),
    ]:
        with pytest.raises(ValueError):
            bound.endpoint_contract({**scope, key: value})


def test_camp_and_unbound_method_ids_cannot_supply_binding_Ki():
    activity = {
        "assay_chembl_id": "CHEMBL100",
        "document_chembl_id": "CHEMBL200",
        "target_chembl_id": "CHEMBL300",
    }
    method = {
        **activity,
        "assay_type": "B",
        "assay_tax_id": 9606,
        "confidence_score": 9,
        "description": "Synthetic radioligand displacement",
    }
    assert receptor.method_supported(method, activity, activity)
    for key, value in [
        ("assay_type", "F"),
        ("description", "cAMP antagonist activity"),
        ("assay_tax_id", 10090),
        ("document_chembl_id", "CHEMBL999"),
    ]:
        assert not receptor.method_supported({**method, key: value}, activity, activity)


def test_primary_correspondence_requires_reparsed_native_name_and_table(tmp_path):
    activity = {
        "activity_id": 1,
        "record_id": 2,
        "src_id": 37,
        "molecule_chembl_id": "CHEMBL3",
        "document_chembl_id": "CHEMBL3638956",
        "value": "20",
        "units": "nM",
        "relation": "=",
    }
    record = {
        k: activity[k]
        for k in ("record_id", "src_id", "molecule_chembl_id", "document_chembl_id")
    }
    record["compound_name"] = "CHEMBL3::US8569318, 1.1(1)"
    html = tmp_path / "primary.html"
    html.write_text(
        "<table><tr><th>No</th><th>IC50, μM</th><th>Ki, μM</th></tr>"
        "<tr><td>1.1(1)</td><td>0.1</td><td>0.020</td></tr></table>"
    )
    evidence = {
        "patent_id": "US8569318B2",
        "native_record": record,
        "native_record_origin": ref(tmp_path, record),
        "primary_origin": {"path": str(html), "sha256": common.file_sha(html)},
        "primary_rows": [["1.1(1)", "0.1", "0.020"]],
        "unique_native_name_and_numeric_match": True,
        "primary_internal_conflicts": [],
    }
    saved = deepcopy(evidence)
    assert receptor.revalidate_primary(evidence, activity, {}) == evidence
    assert evidence == saved
    bad = deepcopy(evidence)
    bad["primary_rows"][0][2] = "0.002"
    with pytest.raises(ValueError, match="primary"):
        receptor.revalidate_primary(bad, activity, {})
    bad = deepcopy(evidence)
    bad["native_record"]["compound_name"] = "US8569318, 9.9(9)"
    with pytest.raises(ValueError, match="native"):
        receptor.revalidate_primary(bad, activity, {})


@pytest.fixture
def synthetic_intake(tmp_path):
    import gzip
    from tools.product import public_assay_components as comp
    from tools.product import public_chembl_primary_correspondence as primary

    entries, nodes = [], []
    for i in range(7):
        patent = primary.PATENT if i < 4 else "US8569318B2"
        doc = primary.DOCUMENT if i < 4 else "CHEMBL3638956"
        assay = primary.ASSAY if i < 4 else "CHEMBL3705099"
        if i == 6:
            doc, assay = "CHEMBL99990", "CHEMBL99991"
        smiles = [
            "C1CCCC1",
            "CC1CCCC1",
            "CCC1CCCC1",
            "CCCC1CCCC1",
            "c1ccncc1",
            "Cc1ccncc1",
            "C1CCOCC1",
        ][i]
        metadata = dict(
            activity_id=i + 1,
            record_id=i + 101,
            src_id=37,
            molecule_chembl_id=f"CHEMBL{700 + i}",
            document_chembl_id=doc,
            assay_chembl_id=assay,
            target_chembl_id=primary.TARGET,
            canonical_smiles=smiles,
            type="Ki",
            standard_type="Ki",
        )
        rid, nid = f"chembl:activity:{i + 1}", f"synthetic:node:{i}"
        role = dict(
            record_id=rid,
            node_id=nid,
            assigned_role="fit" if i < 6 else "development_test",
            evaluation_only=i == 6,
        )
        node = comp.node_from_raw(
            {"ChEMBL Assay ID": assay, "ChEMBL Document ID": doc},
            common.chemical_identity(smiles),
            node_id=nid,
            record_id=rid,
            ligand_id="chembl:molecule:" + metadata["molecule_chembl_id"],
            extra_declarations=[{"role": role["assigned_role"]}],
        )
        nodes.append(node)
        method = dict(
            assay_chembl_id=assay,
            document_chembl_id=doc,
            target_chembl_id=primary.TARGET,
            assay_type="B",
            assay_tax_id=9606,
            confidence_score=9,
            description="Synthetic radioligand displacement",
        )
        entry = dict(
            activity_id=i + 1,
            node_id=nid,
            metadata_origin=ref(tmp_path, metadata, f"metadata{i}.json"),
            role_origin=ref(tmp_path, role, f"role{i}.json"),
            method_origin=ref(tmp_path, method, f"method{i}.json"),
            document_origin=ref(
                tmp_path,
                dict(
                    document_chembl_id=doc,
                    src_id=37,
                    doc_type="PATENT",
                    patent_id=patent,
                ),
                f"doc{i}.json",
            ),
        )
        if i < 6:
            native = {
                **metadata,
                "value": str(10 * (i + 1)),
                "standard_value": str(10 * (i + 1)),
                "units": "nM",
                "standard_units": "nM",
                "relation": "=",
                "standard_relation": "=",
                "upper_value": None,
                "standard_upper_value": None,
                "text_value": None,
                "standard_text_value": None,
                "standard_flag": 1,
                "potential_duplicate": 0,
                "data_validity_comment": None,
                "activity_comment": "123",
            }
            entry["activity_origin"] = ref(tmp_path, native, f"activity{i}.json")
            record = {
                k: metadata[k]
                for k in (
                    "record_id",
                    "src_id",
                    "molecule_chembl_id",
                    "document_chembl_id",
                )
            }
            record["compound_name"] = "US9067949, 1" if i < 4 else "US8569318, 1.1(1)"
            html = tmp_path / f"primary{i}.html"
            if i < 4:
                html.write_text(
                    f"<table><tr><th>human 5HT6 Ki (nm)</th></tr><tr><td>Compound of Example 1</td><td>{10 * (i + 1)}</td></tr></table>"
                )
                rows = primary.extract_primary(html.read_text(), patent_id=patent)
            else:
                rows = [["1.1(1)", "0.5", str(0.01 * (i + 1))]]
                html.write_text(
                    "<table><tr><th>No</th><th>IC50, μM</th><th>Ki, μM</th></tr><tr>"
                    + "".join("<td>" + v + "</td>" for v in rows[0])
                    + "</tr></table>"
                )
            evidence = dict(
                activity_id=i + 1,
                native_activity=native,
                native_record=record,
                native_record_origin=ref(tmp_path, record, f"record{i}.json"),
                patent_id=patent,
                primary_origin={"path": str(html), "sha256": common.file_sha(html)},
                primary_rows=rows,
                unique_native_name_and_numeric_match=True,
                primary_internal_conflicts=[],
            )
            entry["primary_origin"] = ref(tmp_path, evidence, f"evidence{i}.json")
        entries.append(entry)
    path = tmp_path / "metadata.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in entries))
    context = tmp_path / "context.jsonl.gz"
    context.write_bytes(
        gzip.compress("".join(json.dumps(n) + "\n" for n in nodes).encode(), mtime=0)
    )
    scope = dict(
        intake_source_kind=receptor.KIND,
        endpoint="Ki",
        endpoint_subtype=receptor.SUBTYPE,
        source_database_license="CC-BY-SA-3.0",
        evidence_scope=measurement.DB_CURATED_SCOPE,
        physical_target_state_verified=False,
        resplit_after_exclusions=False,
        target_annotation=primary.TARGET,
        positive_threshold_negative_log10_molar=6.0,
        top_fraction=0.2,
        chemistry_scope=dict(
            heavy_atoms_min=5,
            heavy_atoms_max=70,
            fragment_count=1,
            elements=["C", "N", "O", "H"],
            isotope_atoms=0,
            radical_electrons=0,
        ),
    )
    manifest = dict(
        schema_version=bound.endpoint_contract(scope)["manifest_schema"],
        scope=ref(tmp_path, scope, "scope.json"),
        metadata_records={"path": str(path), "sha256": common.file_sha(path)},
        identity_context={"path": str(context), "sha256": common.file_sha(context)},
    )
    return ref(tmp_path, manifest, "manifest.json"), entries


def test_receptor_actual_trainer_synthetic_roundtrip(synthetic_intake, tmp_path):
    from tools.product import train_public_chembl_selector as trainer

    manifest, _ = synthetic_intake
    out = tmp_path / "intake"
    summary = receptor.build(manifest["path"], manifest["sha256"], out)
    assert summary["point_eligible"] == 6 and summary["requested_metadata_rows"] == 7
    result = trainer.fit(
        input_dir=out,
        summary_sha256=common.file_sha(out / "summary.json"),
        output_dir=tmp_path / "fit",
    )
    assert result["fit_used"] == 6 and result["fit_components"] == 2
    assert result["evaluation_label_rows_unread"] == 1
    assert result["training_executed"] and not result["quality_measured"]
    assert not result["customer_execution"] and not result["scientific_validation"]
    assert (
        result["split_plan_sha256"]
        != json.loads((tmp_path / "manifest.json").read_text())["metadata_records"][
            "sha256"
        ]
    )
    rows = [
        json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()
    ]
    rows[0]["native_activity"]["standard_value"] = "100000"
    (out / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary["records_sha256"] = common.file_sha(out / "records.jsonl")
    (out / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="cache_does_not_match"):
        trainer.load_intake(out, common.file_sha(out / "summary.json"), "fit")


def test_evaluation_origin_rejected_before_decoding(synthetic_intake, tmp_path):
    manifest, entries = synthetic_intake
    entries[-1]["activity_origin"] = {
        "path": "/intentionally_missing_evaluation_source",
        "sha256": "f" * 64,
    }
    path = tmp_path / "metadata.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    data = json.loads((tmp_path / "manifest.json").read_text())
    data["metadata_records"]["sha256"] = common.file_sha(path)
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="evaluation_outcome_in_fit_input"):
        receptor.derive(manifest["path"], common.file_sha(tmp_path / "manifest.json"))


def test_article_type_requires_matching_primary_bibliographic_identity():
    doc = {"doc_type": "PUBLICATION", "pubmed_id": 123}
    bibliography = {"uid": "123", "pubtype": ["Journal Article"]}
    assert receptor.document_kind(doc, bibliography) == "research_article"
    assert receptor.document_kind(doc, {**bibliography, "uid": "456"}) == "unresolved"
    assert (
        receptor.document_kind(
            doc, {**bibliography, "pubtype": ["Journal Article", "Review"]}
        )
        == "unresolved"
    )
    assert receptor.document_kind(doc, {}) == "unresolved"


@pytest.mark.parametrize(
    "source_profile", ["literature_only_v1", "chembl_receptor_research_v4"]
)
def test_nested_policy_remains_restrictive_in_both_profiles(source_profile):
    source = profile()
    if source_profile == "literature_only_v1":
        source.update(
            source_id=1,
            document_kind="research_article",
            endpoint_subtype="reported_kinase_inhibition_IC50",
            requested_endpoint_subtype="reported_kinase_inhibition_IC50",
        )
    assert measurement.admission(source, "fit", source_profile=source_profile)[
        "eligible_for_declared_purpose"
    ]
    source["source_policy_declarations"] = [{"joined": {"dataset_split": "test"}}]
    assert not measurement.admission(source, "fit", source_profile=source_profile)[
        "eligible_for_declared_purpose"
    ]
