"""New synthetic API data; no public or protected activity labels."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from tools.product import public_assay_components as comp
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as intake
from tools.product import train_public_assay_selector as existing
from tools.product import train_public_chembl_selector as trainer


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": str(path), "sha256": common.file_sha(path)}


def lines(path, values):
    path.write_text("".join(common.json_text(value) + "\n" for value in values))
    return {"path": str(path), "sha256": common.file_sha(path)}


@pytest.fixture
def source(tmp_path):
    rows, context, methods = [], [], {}
    for i in range(40):
        # Two occurrences per source paper/scaffold, twenty independent groups.
        group = i // 2
        aid = 10000 + i
        assay, document = f"CHEMBL{2000 + group}", f"CHEMBL{3000 + group}"
        smiles = "C1" + "C" * (group + 4) + "1"
        identity = common.chemical_identity(smiles)
        raw = {"activity_id": aid, "assay_chembl_id": assay, "document_chembl_id": document,
               "molecule_chembl_id": f"CHEMBL{4000 + group}", "target_chembl_id": "CHEMBL3038469",
               "canonical_smiles": smiles, "standard_type": "IC50", "type": "IC50", "src_id": 1, "record_id": aid}
        row = {"record_id": f"chembl:activity:{aid}", "ligand_id": f"chembl:molecule:CHEMBL{4000 + group}",
               "identity_context_node_id": f"external:synthetic-{aid}", "chemical_identity": identity,
               "source_provenance": {"source_sha256": "a" * 64, "source_member": "synthetic-metadata.jsonl", "source_line": i + 1,
                                     "row": {"ChEMBL activity metadata": raw, "ChEMBL Assay ID": assay,
                                             "ChEMBL Document ID": document, "role": "unassigned"}}}
        rows.append(row)
        context.append(comp.normalized_node(row))
        methods[assay] = {"document_chembl_id": document,
                          "bibliographic_metadata": {"review_article_indexed": False},
                          "computed_or_QSAR_label_language_observed": False,
                          "method_description": "Synthetic inhibition assay fixture, not real evidence"}
    split, groups = existing.split_components(rows, 20260908, identity_context=context)
    assignments = []
    for role, indices in split.items():
        for index in indices:
            row = rows[index]
            native = row["source_provenance"]["row"]["ChEMBL activity metadata"]
            assignments.append({"activity_id": native["activity_id"], "record_id": row["record_id"],
                                "identity_context_node_id": row["identity_context_node_id"], "component_id": groups[index],
                                "role": role, "assay_chembl_id": native["assay_chembl_id"],
                                "document_chembl_id": native["document_chembl_id"]})
    assignments.sort(key=lambda item: item["activity_id"])
    metadata_entry, context_entry = lines(tmp_path / "metadata.jsonl", rows), lines(tmp_path / "context.jsonl", context)
    plan = {"schema_version": intake.PLAN_SCHEMA, "counts": {key: len(value) for key, value in split.items()},
            "seed": 20260908, "input_full_context_sha256": context_entry["sha256"],
            "input_normalized_metadata_sha256": metadata_entry["sha256"],
            "algorithm_source_sha256": common.file_sha(Path(existing.__file__)),
            "component_implementation_sha256": common.file_sha(Path(comp.__file__)), "assignments": assignments}
    plan_entry = dump(tmp_path / "plan.json", plan)
    scope = {"split_plan_sha256": plan_entry["sha256"], "evidence_scope": "database_curated_reported_experiment_development",
             "endpoint": "IC50", "endpoint_subtype": "enzyme_inhibition_IC50", "physical_target_state_verified": False,
             "resplit_after_exclusions": False, "target_annotation": "CHEMBL3038469", "target_scope": "synthetic catalogue annotation",
             "source_database_license": "CC-BY-SA-3.0", "methods": methods,
             "fit_retrieval_activity_ids": [item["activity_id"] for item in assignments if item["role"] == "fit"],
             "positive_threshold_negative_log10_molar": 6.0, "top_fraction": 0.2,
             "chemistry_scope": {"heavy_atoms_min": 5, "heavy_atoms_max": 70, "fragment_count": 1,
                                 "elements": ["C", "H"], "radical_electrons": 0, "isotope_atoms": 0}}
    scope_entry = dump(tmp_path / "scope.json", scope)
    manifest = {"schema_version": intake.MANIFEST_SCHEMA, "split_plan": plan_entry, "intake_scope": scope_entry,
                "identity_context": context_entry, "normalized_metadata": metadata_entry, "requested_activity_rows": len(rows)}
    manifest_entry = dump(tmp_path / "manifest.json", manifest)
    return {"root": tmp_path, "rows": rows, "plan": plan, "scope": scope, "manifest": manifest,
            "manifest_entry": manifest_entry, "context": context}


def capture(source, phase="fit", frozen=None):
    root = source["root"] / ("capture-" + phase)
    root.mkdir()
    assignments = {item["activity_id"]: item for item in source["plan"]["assignments"]}
    activities = []
    for row in source["rows"]:
        native = deepcopy(row["source_provenance"]["row"]["ChEMBL activity metadata"])
        if (assignments[native["activity_id"]]["role"] == "fit") != (phase == "fit"):
            continue
        concentration = str(100 + native["activity_id"] % 100)
        native.update(value=concentration, units="nM", relation="=", upper_value=None, text_value=None,
                      standard_value=concentration, standard_units="nM", standard_relation="=",
                      standard_upper_value=None, standard_text_value=None, standard_flag=True,
                      potential_duplicate=0, data_validity_comment=None, activity_comment=None)
        activities.append(native)
    expected = [row["activity_id"] for row in activities]
    response = {"activities": activities, "page_meta": {"total_count": len(activities), "next": None}}
    response_entry = dump(root / "response.json", response)
    request = {"base_url": "https://www.ebi.ac.uk/chembl/api/data", "path": "activity.json",
               "params": {"only": ",".join(sorted(intake.ACTIVITY_FIELDS)), "activity_id__in": ",".join(map(str, expected))}}
    request_entry = dump(root / "request.json", request)
    execution_entry = dump(root / "execution.json", {"ok": True, "exit_code": 0,
        "decoded_response_sha256": response_entry["sha256"], "config_sha256": request_entry["sha256"],
        "at_utc": datetime.now(timezone.utc).isoformat()})
    part = {**response_entry, "request_path": request_entry["path"], "request_sha256": request_entry["sha256"],
            "execution_path": execution_entry["path"], "execution_sha256": execution_entry["sha256"],
            "expected_activity_ids": expected}
    manifest = {"schema_version": "chembl_activity_capture_manifest_v1", "phase": phase,
                "split_plan_sha256": source["manifest"]["split_plan"]["sha256"],
                "intake_scope_sha256": source["manifest"]["intake_scope"]["sha256"],
                "allowed_fields": sorted(intake.ACTIVITY_FIELDS), "expected_activity_ids": expected,
                "captures": [part], "response_rows": len(activities), "capture_semantics": "new synthetic fixture"}
    if frozen is not None:
        manifest["frozen_fit"] = frozen
    return dump(root / "manifest.json", manifest)


def build(source, captures, phase="fit"):
    return intake.run(manifest_path=source["manifest_entry"]["path"], manifest_sha256=source["manifest_entry"]["sha256"],
                      capture_path=captures["path"], capture_sha256=captures["sha256"], phase=phase,
                      output_dir=source["root"] / (phase + "-intake"))


def rewrite_capture_response(entry, change):
    manifest = json.loads(Path(entry["path"]).read_text())
    part = manifest["captures"][0]
    response = json.loads(Path(part["path"]).read_text())
    change(response)
    part["sha256"] = dump(Path(part["path"]), response)["sha256"]
    execution = json.loads(Path(part["execution_path"]).read_text())
    execution["decoded_response_sha256"] = part["sha256"]
    part["execution_sha256"] = dump(Path(part["execution_path"]), execution)["sha256"]
    return dump(Path(entry["path"]), manifest)


def test_actual_intake_and_staged_consumer(source):
    summary = build(source, capture(source))
    assert summary["observations_retrieved"] == source["plan"]["counts"]["fit"]
    assert summary["point_eligible_rows"] == summary["observations_retrieved"]
    assert summary["requested_metadata_rows"] == 40
    fit_dir = source["root"] / "fit-intake"
    trained = trainer.fit(input_dir=fit_dir, summary_sha256=common.file_sha(fit_dir / "summary.json"),
                          output_dir=source["root"] / "fit")
    assert trained["training_executed"] and trained["evaluation_label_rows_unread"] > 0
    frozen_path = source["root"] / "fit/frozen-fit.json"
    frozen = {"path": str(frozen_path), "sha256": common.file_sha(frozen_path)}
    evaluated_intake = build(source, capture(source, "evaluation", frozen), "evaluation")
    assert evaluated_intake["observations_retrieved"] == trained["evaluation_label_rows_unread"]
    eval_dir = source["root"] / "evaluation-intake"
    evaluated = trainer.evaluate(input_dir=eval_dir, summary_sha256=common.file_sha(eval_dir / "summary.json"),
                                 frozen_fit_path=frozen_path, frozen_fit_sha256=frozen["sha256"],
                                 output_dir=source["root"] / "evaluation")
    assert not evaluated["product_ranking_enabled"]
    assert sum(item["requested_preassigned_rows"] for item in evaluated["evaluations"].values()) == trained["evaluation_label_rows_unread"]


@pytest.fixture
def ki_source(source):
    """Fresh synthetic Ki projection; original IC50 controls stay unchanged."""
    for row in source["rows"]:
        native = row["source_provenance"]["row"]["ChEMBL activity metadata"]
        native.update(standard_type="Ki", type="Ki", target_chembl_id="CHEMBL244")
    source["scope"].update(endpoint="Ki", endpoint_subtype="enzyme_inhibition_Ki", target_annotation="CHEMBL244")
    for method in source["scope"]["methods"].values():
        method["endpoint_subtype"] = "enzyme_inhibition_Ki"
        method["citation_identity_status"] = "resolved"
    source["plan"].update(schema_version="public_chembl_predeclared_split_v2", endpoint="Ki",
                          prediction_quantity="negative_log10_molar_Ki", target_annotation="CHEMBL244")
    metadata = lines(source["root"] / "metadata.jsonl", source["rows"])
    source["plan"]["input_normalized_metadata_sha256"] = metadata["sha256"]
    plan = dump(source["root"] / "plan.json", source["plan"])
    source["scope"]["split_plan_sha256"] = plan["sha256"]
    source["manifest"].update(schema_version="public_chembl_preassigned_metadata_manifest_v2",
                              split_plan=plan, normalized_metadata=metadata,
                              intake_scope=dump(source["root"] / "scope.json", source["scope"]))
    source["manifest_entry"] = dump(source["root"] / "manifest.json", source["manifest"])
    return source


def test_ki_native_staged_fit_and_evaluation_preserve_endpoint(ki_source):
    source = ki_source
    summary = build(source, capture(source))
    assert summary["schema_version"] == "public_chembl_assay_development_v2"
    fit_dir = source["root"] / "fit-intake"
    trained = trainer.fit(input_dir=fit_dir, summary_sha256=common.file_sha(fit_dir / "summary.json"),
                          output_dir=source["root"] / "fit")
    checkpoint_path = source["root"] / "fit/selector.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    assert checkpoint["schema_version"] == "public_chembl_cheap_selector_ridge_v2"
    assert checkpoint["endpoint"] == "Ki" and checkpoint["endpoint_subtype"] == "enzyme_inhibition_Ki"
    assert checkpoint["prediction_quantity"] == trained["prediction_quantity"] == "negative_log10_molar_Ki"
    assert not checkpoint["physical_energy"] and not checkpoint["product_ranking_enabled"]
    frozen_path = source["root"] / "fit/frozen-fit.json"
    frozen = {"path": str(frozen_path), "sha256": common.file_sha(frozen_path)}
    assert json.loads(frozen_path.read_text())["schema_version"] == "public_chembl_fit_frozen_before_evaluation_v2"
    build(source, capture(source, "evaluation", frozen), "evaluation")
    evaluation_dir = source["root"] / "evaluation-intake"
    result = trainer.evaluate(input_dir=evaluation_dir, summary_sha256=common.file_sha(evaluation_dir / "summary.json"),
                              frozen_fit_path=frozen_path, frozen_fit_sha256=frozen["sha256"],
                              output_dir=source["root"] / "evaluation")
    assert result["schema_version"] == "public_chembl_frozen_selector_evaluation_v2"
    assert all("Ki" in v["observed_metrics_scope"] and "IC50" not in v["observed_metrics_scope"]
               for v in result["evaluations"].values())


@pytest.mark.parametrize("field,value", [("schema_version", "public_chembl_cheap_selector_ridge_v1"),
                                        ("endpoint", "IC50"), ("endpoint_subtype", "enzyme_inhibition_IC50"),
                                        ("prediction_quantity", "negative_log10_molar_IC50"),
                                        ("physical_energy", True)])
def test_ki_checkpoint_endpoint_tampering_rejected(ki_source, field, value):
    build(ki_source, capture(ki_source))
    directory = ki_source["root"] / "fit-intake"
    trainer.fit(input_dir=directory, summary_sha256=common.file_sha(directory / "summary.json"),
                output_dir=ki_source["root"] / "fit")
    path = ki_source["root"] / "fit/selector.json"
    checkpoint = json.loads(path.read_text())
    checkpoint[field] = value
    entry = dump(path, checkpoint)
    with pytest.raises(ValueError, match="incompatible_chembl_selector_checkpoint"):
        trainer.predict_checkpoint(path, entry["sha256"], ["CCCCC"], checkpoint["target_annotation_sha256"], endpoint="Ki")


@pytest.mark.parametrize("field,value", [("endpoint", "IC50"), ("prediction_quantity", "negative_log10_molar_IC50"),
                                        ("target_annotation", "CHEMBL3038469")])
def test_ki_plan_endpoint_binding_rejected_before_values(ki_source, field, value):
    ki_source["plan"][field] = value
    manifest = deepcopy(ki_source["manifest"])
    manifest["split_plan"] = dump(ki_source["root"] / "plan.json", ki_source["plan"])
    ki_source["scope"]["split_plan_sha256"] = manifest["split_plan"]["sha256"]
    manifest["intake_scope"] = dump(ki_source["root"] / "scope.json", ki_source["scope"])
    entry = dump(ki_source["root"] / "manifest.json", manifest)
    with pytest.raises(ValueError, match="plan_endpoint_contract_mismatch"):
        intake.load_metadata(entry["path"], entry["sha256"])


@pytest.mark.parametrize("value,relation,status", [("0", "=", "nonpositive"), ("100", ">", "censored"), (None, "=", "missing")])
def test_ki_unsupported_measurements_keep_original_values_and_roles(ki_source, value, relation, status):
    test_unsupported_labels_remain_in_ledger_and_roles(ki_source, value, relation, status)


def test_ki_evaluation_requires_freeze_and_rehashed_cache_remains_guarded(ki_source):
    test_evaluation_capture_requires_frozen_fit(ki_source)
    test_rehashed_cache_cannot_change_training_label(ki_source)


@pytest.mark.parametrize("change", [
    {"bibliographic_metadata": {"review_article_indexed": None}},
    {"bibliographic_metadata": {"review_article_indexed": True}},
    {"computed_or_QSAR_label_language_observed": True},
    {"computed_or_QSAR_label_language_observed": None},
    {"endpoint_subtype": "enzyme_inhibition_IC50"},
    {"method_description": None},
    {"citation_identity_status": "unresolved"},
])
def test_ki_unresolved_methods_are_exclusions_without_relabel_or_resplit(ki_source, change):
    assay = next(a["assay_chembl_id"] for a in ki_source["plan"]["assignments"] if a["role"] == "fit")
    ki_source["scope"]["methods"][assay].update(change)
    ki_source["manifest"]["intake_scope"] = dump(ki_source["root"] / "scope.json", ki_source["scope"])
    ki_source["manifest_entry"] = dump(ki_source["root"] / "manifest.json", ki_source["manifest"])
    summary = build(ki_source, capture(ki_source))
    rows = [json.loads(line) for line in (ki_source["root"] / "fit-intake/records.jsonl").read_text().splitlines()]
    affected = [row for row in rows if row["assay_id"] == "chembl:assay:" + assay]
    assert affected and all(not row["eligible_for_point_model"] and row["assigned_role"] == "fit" for row in affected)
    assert all("assay_method_or_primary_document_unresolved" in row["admission_issues"] for row in affected)
    if "computed_or_QSAR_label_language_observed" in change:
        assert all(row["evidence_kind"] == "unknown" for row in affected)
    assert summary["requested_metadata_rows"] == 40
    assert summary["assigned_role_counts"] == ki_source["plan"]["counts"]


def test_legacy_checkpoint_consumer_cannot_silently_read_ki(ki_source):
    build(ki_source, capture(ki_source))
    directory = ki_source["root"] / "fit-intake"
    trainer.fit(input_dir=directory, summary_sha256=common.file_sha(directory / "summary.json"),
                output_dir=ki_source["root"] / "fit")
    path = ki_source["root"] / "fit/selector.json"
    checkpoint = json.loads(path.read_text())
    with pytest.raises(ValueError, match="incompatible_chembl_selector_checkpoint"):
        trainer.predict_checkpoint(path, common.file_sha(path), ["CCCCC"], checkpoint["target_annotation_sha256"])


def test_source_policy_dependency_change_invalidates_cached_intake(ki_source, monkeypatch):
    build(ki_source, capture(ki_source))
    directory = ki_source["root"] / "fit-intake"
    old_sha = common.file_sha
    expected_summary_sha = old_sha(directory / "summary.json")
    policy_path = Path(intake.source_policy.__file__)
    monkeypatch.setattr(common, "file_sha", lambda path: "f" * 64 if Path(path) == policy_path else old_sha(path))
    with pytest.raises(ValueError, match="fit_intake_schema_or_implementation_mismatch"):
        trainer.load_intake(directory, expected_summary_sha, "fit")


@pytest.mark.parametrize("field,value,reason", [
    ("target_chembl_id", "CHEMBL9", "activity_metadata_changed_after_split"),
    ("canonical_smiles", "CCCCC", "activity_metadata_changed_after_split"),
    ("src_id", True, "activity_metadata_changed_after_split"),
    ("unrequested_field", "x", "unexpected_activity_payload_field"),
])
def test_capture_metadata_or_unknown_field_rejected(source, field, value, reason):
    entry = rewrite_capture_response(capture(source), lambda response: response["activities"][0].update({field: value}))
    with pytest.raises(ValueError, match=reason):
        build(source, entry)


def test_duplicate_activity_never_last_row_wins(source):
    def change(response):
        response["activities"][1] = deepcopy(response["activities"][0])
    entry = rewrite_capture_response(capture(source), change)
    with pytest.raises(ValueError, match="activity_capture_occurrence_gap"):
        build(source, entry)


@pytest.mark.parametrize("value,relation,status", [("0", "=", "nonpositive"), ("100", ">", "censored"), (None, "=", "missing")])
def test_unsupported_labels_remain_in_ledger_and_roles(source, value, relation, status):
    def change(response):
        response["activities"][0].update(value=value, standard_value=value, relation=relation, standard_relation=relation)
    entry = rewrite_capture_response(capture(source), change)
    summary = build(source, entry)
    rows = [json.loads(line) for line in (source["root"] / "fit-intake/records.jsonl").read_text().splitlines()]
    changed = next(row for row in rows if row["observation"] is not None and row["observation"]["status"] == status)
    assert not changed["eligible_for_point_model"]
    assert changed["assigned_role"] == "fit"
    assert changed["observation"]["source_activity"]["value"] == value
    assert summary["requested_metadata_rows"] == 40
    assert summary["assigned_role_counts"] == source["plan"]["counts"]
    assert summary["point_eligible_rows"] == summary["observations_retrieved"] - 1


def test_evaluation_capture_requires_frozen_fit(source):
    with pytest.raises(ValueError, match="frozen_fit_required_before_evaluation_capture"):
        build(source, capture(source, "evaluation"), "evaluation")


def test_rehashed_cache_cannot_change_training_label(source):
    build(source, capture(source))
    directory = source["root"] / "fit-intake"
    rows = [json.loads(line) for line in (directory / "records.jsonl").read_text().splitlines()]
    next(row for row in rows if row["eligible_for_point_model"])["observation"]["negative_log10_molar"] += 3.0
    rewritten = lines(directory / "records.jsonl", rows)
    summary = json.loads((directory / "summary.json").read_text())
    summary["records_sha256"] = rewritten["sha256"]
    bound = dump(directory / "summary.json", summary)
    with pytest.raises(ValueError, match="fit_intake_cache_does_not_match_native_source"):
        trainer.load_intake(directory, bound["sha256"], "fit")


def test_preassigned_role_cannot_be_changed(source):
    path = Path(source["manifest"]["split_plan"]["path"])
    plan = deepcopy(source["plan"])
    plan["assignments"][0]["role"] = "calibration" if plan["assignments"][0]["role"] == "fit" else "fit"
    updated = dump(path, plan)
    manifest = deepcopy(source["manifest"])
    manifest["split_plan"] = updated
    scope = deepcopy(source["scope"])
    scope["split_plan_sha256"] = updated["sha256"]
    manifest["intake_scope"] = dump(Path(manifest["intake_scope"]["path"]), scope)
    bound = dump(Path(source["manifest_entry"]["path"]), manifest)
    with pytest.raises(ValueError, match="preassigned_role_or_component_mismatch"):
        intake.load_metadata(bound["path"], bound["sha256"])


@pytest.mark.parametrize("location,key,value", [
    ("outer", "observed_activity", 8.0),
    ("raw", "observed_activity", 8.0),
    ("raw", "ChEMBL Document ID", "CHEMBL99999"),
    ("raw", "ChEMBL Assay ID", "CHEMBL99999"),
    ("outer", "ligand_id", "chembl:molecule:CHEMBL99999"),
])
def test_metadata_projection_cannot_smuggle_outcome_or_change_identity(source, location, key, value):
    row = deepcopy(source["rows"][0])
    target = row if location == "outer" else row["source_provenance"]["row"]
    target[key] = value
    with pytest.raises(ValueError):
        intake.validate_metadata_row(row)


def test_metadata_title_is_text_not_nested_outcome(source):
    row = deepcopy(source["rows"][0])
    row["source_provenance"]["row"]["ChEMBL document metadata"] = {"title": {"observed": 7.0}}
    with pytest.raises(ValueError, match="invalid_metadata_scalar_type"):
        intake.validate_metadata_row(row)


@pytest.mark.parametrize("key,value", [("split_plan_sha256", "9" * 64), ("intake_scope_sha256", "8" * 64),
                                       ("requested_metadata_rows", 1), ("identity_context_nodes", 1)])
def test_rehashed_summary_cannot_relabel_source_or_denominator(source, key, value):
    build(source, capture(source))
    directory = source["root"] / "fit-intake"
    summary = json.loads((directory / "summary.json").read_text())
    summary[key] = value
    entry = dump(directory / "summary.json", summary)
    with pytest.raises(ValueError, match="intake_summary_does_not_match_native_source"):
        trainer.load_intake(directory, entry["sha256"], "fit")


@pytest.mark.parametrize("change", ["mean", "abstention"])
def test_frozen_baseline_and_abstention_cannot_be_rewritten_before_evaluation(source, change):
    build(source, capture(source))
    directory = source["root"] / "fit-intake"
    trainer.fit(input_dir=directory, summary_sha256=common.file_sha(directory / "summary.json"),
                output_dir=source["root"] / "fit")
    path = source["root"] / "fit/frozen-fit.json"
    frozen = json.loads(path.read_text())
    predictions = [json.loads(line) for line in Path(frozen["predictions"]["path"]).read_text().splitlines()]
    if change == "mean":
        predictions[0]["mean_baseline"] += 1.0
    else:
        predictions[0].update(predicted=None, status="abstained", reason=["invented_exclusion"])
    frozen["predictions"] = lines(Path(frozen["predictions"]["path"]), predictions)
    entry = dump(path, frozen)
    captures = capture(source, "evaluation", entry)
    with pytest.raises(ValueError, match="frozen_baseline_or_abstention_mismatch"):
        build(source, captures, "evaluation")
