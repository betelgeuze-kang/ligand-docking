"""Fresh synthetic native-source controls; no public or protected labels."""
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import gzip
import json
from pathlib import Path

import pytest

from tools.product import public_assay_components as comp
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as intake
from tools.product import public_chembl_native_intake as native
from tools.product import train_public_chembl_selector as trainer


def save(path, value, *, lines=False, zipped=False):
    text = "".join(common.json_text(v) + "\n" for v in value) if lines else common.json_text(value) + "\n"
    path.write_bytes(gzip.compress(text.encode(), mtime=0) if zipped else text.encode())
    return {"path": str(path), "sha256": common.file_sha(path)}


@pytest.fixture
def source(tmp_path):
    metadata, assays, documents = [], [], []
    for i in range(40):
        group = i // 2
        metadata.append({"activity_id": 910000 + i, "assay_chembl_id": f"CHEMBL{920000 + group}",
                         "document_chembl_id": f"CHEMBL{930000 + group}", "molecule_chembl_id": f"CHEMBL{940000 + group}",
                         "target_chembl_id": "CHEMBL900000", "canonical_smiles": "C1" + "C" * (group + 4) + "1",
                         "standard_type": "IC50", "type": "IC50", "src_id": 1, "record_id": 950000 + i,
                         "native_assay_id": group + 1, "native_doc_id": group + 101, "native_molregno": group + 201})
    for group in range(20):
        assays.append({"assay_chembl_id": f"CHEMBL{920000 + group}", "confidence_score": 9,
                       "relationship_type": "D", "assay_type": "B", "assay_tax_id": 9606})
        documents.append({"document_chembl_id": f"CHEMBL{930000 + group}", "document_type": "PUBLICATION"})
    meta = save(tmp_path / "metadata.jsonl", metadata, lines=True)
    meta["source_member"] = "native-metadata/activities.jsonl"
    nodes = []
    for ordinal, row in enumerate(metadata, 1):
        origin = {"source_member": meta["source_member"], "source_sha256": meta["sha256"], "source_line": ordinal}
        nodes.append(comp.node_from_raw({"ChEMBL Assay ID": row["assay_chembl_id"], "ChEMBL Document ID": row["document_chembl_id"]},
                                       common.chemical_identity(row["canonical_smiles"]),
                                       node_id="external:" + comp.digest(meta["sha256"] + ":" + str(ordinal)),
                                       record_id="chembl:activity:" + str(row["activity_id"]),
                                       ligand_id="chembl:molecule:" + row["molecule_chembl_id"], origin=origin))
    base = save(tmp_path / "base.jsonl.gz", nodes, lines=True, zipped=True)
    graph = comp.component_index(nodes)
    inventory = []
    for row, node in zip(metadata, nodes):
        inventory.append({**{k: row[k] for k in ("activity_id", "assay_chembl_id", "document_chembl_id", "molecule_chembl_id", "standard_type")},
                          "node_id": node["node_id"], "component_id": graph[node["node_id"]]["component_id"],
                          "blocked": False, "intake_reason": native.CANDIDATE, "metadata_direct_human_binding": True,
                          "chemical_identity_available": True, "document_type": "PUBLICATION"})
    # Separately expressed exact-rational role allocation for the synthetic source.
    groups = defaultdict(list)
    for row in inventory:
        groups[row["component_id"]].append(row)
    counts = {"fit": 0, "calibration": 0, "development_test": 0}
    fractions = dict(zip(counts, [Fraction(7, 10), Fraction(3, 20), Fraction(3, 20)]))
    role_map = {}
    for cid in sorted(groups, key=lambda cid: (-len(groups[cid]), comp.digest("23:" + cid))):
        role = max(counts, key=lambda role: fractions[role] * len(inventory) - counts[role])
        role_map[cid] = role
        counts[role] += len(groups[cid])
    assignments = [{"activity_id": r["activity_id"], "component_id": r["component_id"], "identity_context_node_id": r["node_id"],
                    "assay_chembl_id": r["assay_chembl_id"], "document_chembl_id": r["document_chembl_id"],
                    "role": role_map[r["component_id"]], "evaluation_only": role_map[r["component_id"]] != "fit"} for r in inventory]
    inv = save(tmp_path / "inventory.jsonl", inventory, lines=True)
    plan = {"schema": native.PLAN, "context_sha256": base["sha256"], "inventory_sha256": inv["sha256"],
            "native_database_sha256": "b" * 64, "endpoint": "IC50", "target": "CHEMBL900000", "seed": 23,
            "assignments": assignments, "role_counts": dict(Counter(r["role"] for r in assignments)),
            "component_role_counts": dict(Counter(role_map.values()))}
    plan_entry = save(tmp_path / "plan.json", plan)
    observed_assignments = save(tmp_path / "roles.jsonl", assignments, lines=True)
    observed_assignments["source_member"] = "roles.jsonl"
    extra = []
    for ordinal, (a, n) in enumerate(zip(assignments, nodes), 1):
        extra.append(dict(n, node_id="external:" + comp.digest(observed_assignments["sha256"] + ":" + str(ordinal)),
                          policy_declarations=n["policy_declarations"] + [{"role": a["role"], "evaluation_only": a["evaluation_only"]}],
                          source={"source_member": "roles.jsonl", "source_sha256": observed_assignments["sha256"], "source_line": ordinal}))
    methods = {}
    evidence = save(tmp_path / "synthetic-method.json", {"source": "fresh synthetic assay; not an actual publication"})
    for a in assignments:
        if a["role"] == "fit":
            methods[a["assay_chembl_id"]] = {"document_chembl_id": a["document_chembl_id"], "method_eligible": True,
                "method_admission_issues": [], "bibliographic_metadata": {"review_article_indexed": False},
                "computed_or_QSAR_label_language_observed": False, "endpoint_subtype": "enzyme_inhibition_IC50",
                "citation_identity_status": "resolved", "method_description": "Fresh synthetic enzymatic control.", "evidence_files": [evidence]}
    scope = {"intake_source_kind": native.SOURCE, "endpoint": "IC50", "endpoint_subtype": "enzyme_inhibition_IC50",
             "target_annotation": "CHEMBL900000", "target_scope": "synthetic catalogue", "split_plan_sha256": plan_entry["sha256"],
             "physical_target_state_verified": False, "resplit_after_exclusions": False,
             "evidence_scope": "database_curated_reported_experiment_development", "source_database_license": "CC-BY-SA-3.0",
             "chemistry_scope": {"heavy_atoms_min": 5, "heavy_atoms_max": 70, "fragment_count": 1, "elements": ["C", "H"],
                                 "isotope_atoms": 0, "radical_electrons": 0}, "methods": methods,
             "positive_threshold_negative_log10_molar": 6.0, "top_fraction": .2}
    values = []
    for row, assignment in zip(metadata, assignments):
        if assignment["role"] != "fit":
            continue
        value = {k: None for k in native.VALUE_FIELDS}
        value.update({k: row[k] for k in ("activity_id", "record_id", "src_id", "standard_type", "type")})
        value.update(assay_id=row["native_assay_id"], doc_id=row["native_doc_id"], molregno=row["native_molregno"],
                     value="100", units="nM", relation="=", standard_value="100", standard_units="nM",
                     standard_relation="=", standard_flag=1, potential_duplicate=0)
        values.append(value)
    ids = [r["activity_id"] for r in values]
    query = {"parameters": ids, "role_plan_sha256": plan_entry["sha256"],
             "sql": "SELECT " + ",".join(sorted(native.VALUE_FIELDS)) + " FROM activities WHERE activity_id IN (" + ",".join("?" for _ in ids) + ") ORDER BY activity_id"}
    export = {"source_kind": native.SOURCE, "database_sha256": "b" * 64,
              "query_plan": save(tmp_path / "query.json", query), "records": save(tmp_path / "values.jsonl", values, lines=True)}
    manifest = {"schema_version": native.MANIFEST, "source_kind": native.SOURCE, "phase": "fit",
                "implementation_hashes": native.implementations(), "split_plan": plan_entry, "scope": save(tmp_path / "scope.json", scope),
                "release_receipt": save(tmp_path / "release.json", {"status": "complete", "database_sha256": "b" * 64}),
                "metadata": meta, "inventory": inv, "base_context": base,
                "role_context": save(tmp_path / "current.jsonl.gz", nodes + extra, lines=True, zipped=True),
                "assays": save(tmp_path / "assays.jsonl", assays, lines=True),
                "documents": save(tmp_path / "documents.jsonl", documents, lines=True),
                "assignment_observations": observed_assignments, "requested_metadata_rows": 40, "native_exports": [export]}
    return tmp_path, manifest


def run(source):
    root, manifest = source
    entry = save(root / "manifest.json", manifest)
    return native.build(manifest_path=entry["path"], manifest_sha256=entry["sha256"], output_dir=root / "intake")


def test_native_cli_and_actual_existing_trainer_freeze_synthetic_predictions(source):
    root, manifest = source
    entry = save(root / "manifest.json", manifest)
    assert native.main(["--manifest", entry["path"], "--manifest-sha256", entry["sha256"], "--output-dir", str(root / "intake")]) == 0
    assert trainer.main(["--input-dir", str(root / "intake"), "--summary-sha256", common.file_sha(root / "intake/summary.json"),
                         "--output-dir", str(root / "fit"), "--phase", "fit"]) == 0
    checkpoint = json.loads((root / "fit/selector.json").read_text())
    assert checkpoint["schema_version"] == "public_chembl_cheap_selector_ridge_v3"
    assert checkpoint["intake_source_kind"] == native.SOURCE
    assert checkpoint["product_ranking_enabled"] is False
    predictions = [json.loads(line) for line in (root / "fit/predictions-before-evaluation-labels.jsonl").read_text().splitlines()]
    assert len(predictions) == 40
    assert all(p["observed_label_included"] is False for p in predictions)
    assert json.loads((root / "fit/frozen-fit.json").read_text())["evaluation_values_read"] == 0


def test_missing_methods_remain_unknown_with_complete_denominator(source):
    root, manifest = source
    scope = intake.bound_json(manifest["scope"])
    missing = next(iter(scope["methods"]))
    del scope["methods"][missing]
    # Withhold corresponding values before constructing this source experiment.
    plan = intake.bound_json(manifest["split_plan"])
    remove = {a["activity_id"] for a in plan["assignments"] if a["assay_chembl_id"] == missing}
    export = manifest["native_exports"][0]
    values = [r for r in native.bound_lines(export["records"]) if r["activity_id"] not in remove]
    query = intake.bound_json(export["query_plan"])
    query["parameters"] = [r["activity_id"] for r in values]
    query["sql"] = query["sql"].partition(" IN (")[0] + " IN (" + ",".join("?" for _ in values) + ") ORDER BY activity_id"
    export["query_plan"] = save(root / "query2.json", query)
    export["records"] = save(root / "values2.jsonl", values, lines=True)
    manifest["scope"] = save(root / "scope2.json", scope)
    result = run(source)
    assert result["metadata_selected_rows"] == 40
    for row in native.bound_lines({"path": str(root / "intake/records.jsonl"), "sha256": result["records_sha256"]}):
        if row["activity_id"] in remove:
            assert row["evidence_kind"] == "unknown"
            assert row["label_access_status"] == "withheld_by_source_method"
            assert row["eligible_for_point_model"] is False


def test_reserved_export_rejected_before_outcome_file_open(source, monkeypatch):
    root, manifest = source
    plan = intake.bound_json(manifest["split_plan"])
    aid = next(a["activity_id"] for a in plan["assignments"] if a["role"] != "fit")
    export = manifest["native_exports"][0]
    query = intake.bound_json(export["query_plan"])
    query["parameters"] = [aid]
    export["query_plan"] = save(root / "bad-query.json", query)
    old = native.bound_lines
    def deny_values(entry, **kwargs):
        if entry == export["records"]:
            raise AssertionError("reserved outcome file was opened")
        return old(entry, **kwargs)
    monkeypatch.setattr(native, "bound_lines", deny_values)
    with pytest.raises(ValueError, match="nonfit_or_duplicate"):
        run(source)


@pytest.mark.parametrize("change", ["duplicate", "metadata", "query", "method"])
def test_native_export_fail_closed(source, change):
    root, manifest = source
    export = manifest["native_exports"][0]
    if change == "duplicate":
        manifest["native_exports"].append(deepcopy(export))
        expected = "duplicate_native_export"
    elif change == "metadata":
        values = native.bound_lines(export["records"])
        values[0]["doc_id"] += 1
        export["records"] = save(root / "bad-values.jsonl", values, lines=True)
        expected = "native_export_metadata_mismatch"
    elif change == "query":
        query = intake.bound_json(export["query_plan"])
        query["sql"] = "SELECT * FROM activities"
        export["query_plan"] = save(root / "bad-query.json", query)
        expected = "query_not_allowlisted"
    else:
        scope = intake.bound_json(manifest["scope"])
        scope["methods"][next(iter(scope["methods"]))]["method_eligible"] = False
        manifest["scope"] = save(root / "bad-scope.json", scope)
        expected = "method_not_admitted"
    with pytest.raises(ValueError, match=expected):
        run(source)


def test_rehashed_cache_admission_tamper_does_not_bypass_native_source(source):
    root, _ = source
    summary = run(source)
    records = native.bound_lines({"path": str(root / "intake/records.jsonl"), "sha256": summary["records_sha256"]})
    row = next(r for r in records if r["assigned_role"] != "fit")
    row["eligible_for_point_model"] = True
    changed = save(root / "intake/records.jsonl", records, lines=True)
    summary["records_sha256"] = changed["sha256"]
    entry = save(root / "intake/summary.json", summary)
    with pytest.raises(ValueError, match="native_intake_cache_mismatch"):
        trainer.load_intake(root / "intake", entry["sha256"], "fit")


def test_rehashed_role_change_cannot_replace_original_assignment_algorithm(source):
    root, manifest = source
    plan = intake.bound_json(manifest["split_plan"])
    plan["assignments"][0]["role"] = "development_test" if plan["assignments"][0]["role"] == "fit" else "fit"
    manifest["split_plan"] = save(root / "bad-plan.json", plan)
    scope = intake.bound_json(manifest["scope"])
    scope["split_plan_sha256"] = manifest["split_plan"]["sha256"]
    manifest["scope"] = save(root / "bad-scope.json", scope)
    with pytest.raises(ValueError, match="frozen_assignment_replay"):
        run(source)


def test_reserved_text_and_unbound_method_source_rejected(source):
    root, manifest = source
    docs = native.bound_lines(manifest["documents"])
    docs[0]["title"] = "synthetic forbidden pre-freeze content"
    manifest["documents"] = save(root / "bad-documents.jsonl", docs, lines=True)
    with pytest.raises(ValueError, match="nonmetadata_field"):
        run(source)


def test_native_evaluation_explicitly_unavailable(source):
    root, _ = source
    run(source)
    with pytest.raises(ValueError, match="native_evaluation_capture_contract_not_implemented"):
        trainer.load_intake(root / "intake", common.file_sha(root / "intake/summary.json"), "evaluation")


@pytest.mark.parametrize("referenced", [True, False])
def test_native_assay_document_union_preserved_without_unreferenced_metadata(source, referenced):
    root, manifest = source
    docs = native.bound_lines(manifest["documents"])
    docs.append({"document_chembl_id": "CHEMBL990001", "document_type": "PUBLICATION"})
    manifest["documents"] = save(root / "extra-docs.jsonl", docs, lines=True)
    if referenced:
        assays = native.bound_lines(manifest["assays"])
        assays[0]["document_chembl_id"] = "CHEMBL990001"
        manifest["assays"] = save(root / "extra-assays.jsonl", assays, lines=True)
        assert run(source)["metadata_selected_rows"] == 40
    else:
        with pytest.raises(ValueError, match="native_linked_metadata_coverage_mismatch"):
            run(source)


def test_method_source_bytes_change_invalidates_native_intake(source):
    root, manifest = source
    scope = intake.bound_json(manifest["scope"])
    evidence = scope["methods"][next(iter(scope["methods"]))]["evidence_files"][0]
    Path(evidence["path"]).write_text("changed synthetic source\n")
    with pytest.raises(ValueError, match="hash|sha|checksum"):
        run(source)


def test_legacy_checkpoint_cannot_be_migrated_by_schema_rename(source):
    root, _ = source
    summary = run(source)
    trainer.fit(input_dir=root / "intake", summary_sha256=common.file_sha(root / "intake/summary.json"), output_dir=root / "fit")
    path = root / "fit/selector.json"
    checkpoint = json.loads(path.read_text())
    checkpoint.pop("intake_source_kind")
    entry = save(root / "bad-checkpoint.json", checkpoint)
    with pytest.raises(ValueError, match="incompatible_chembl_selector_checkpoint"):
        trainer.predict_checkpoint(Path(entry["path"]), entry["sha256"], ["C1CCCCC1"], checkpoint["target_annotation_sha256"])
    assert summary["training_executed"] is False
