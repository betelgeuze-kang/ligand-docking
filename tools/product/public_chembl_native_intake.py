"""Fit-phase adapter for bound native SQLite exports and precontent reservations.

No database/API calls, re-splitting after exclusions, or replacement energy model.
The original full-component reservation algorithm is replayed before outcomes are
read. The existing ChEMBL normalizer and trainer remain numerical authorities.
Native evaluation requires a separate frozen-prediction capture contract; it is
explicitly unavailable in this first version, never routed through API receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path
import resource
import time

from tools.product import public_assay_components as comp
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as intake

MANIFEST = "native_chembl_sqlite_fit_intake_manifest_v1"
SOURCE = "native_chembl_sqlite_release_v1"
PLAN = "native_chembl_ic50_precontent_reservation_v1"
CANDIDATE = "new_primary_method_review_candidate"
NATIVE_FIELDS = intake.METADATA_FIELDS | {"native_assay_id", "native_doc_id", "native_molregno"}
VALUE_FIELDS = (intake.ACTIVITY_FIELDS - intake.METADATA_FIELDS) | {
    "activity_id", "assay_id", "doc_id", "record_id", "molregno", "src_id",
    "type", "standard_type", "pchembl_value"}
ASSAY_FIELDS = set("aidx assay_category assay_cell_type assay_chembl_id assay_group assay_id assay_organism assay_strain assay_subcellular_fraction assay_tax_id assay_test_type assay_tissue assay_type bao_format cell_id confidence_score doc_id document_chembl_id relationship_type src_assay_id src_id target_chembl_id tissue_id variant_id".split())
DOCUMENT_FIELDS = set("chembl_release_id doc_id document_chembl_id document_type doi first_page issue journal last_page pubmed_id src_id volume year".split())


def implementations():
    from tools.product import train_public_chembl_selector as trainer
    return trainer.implementation_hashes()


def bound_lines(entry, *, compressed=False):
    data = intake.read_bound(entry["path"], entry["sha256"])
    if compressed:
        data = gzip.decompress(data)
    return [comp.loads(line) for line in data.decode().splitlines()]


def indexed(rows, key):
    if any(type(row.get(key)) is not int or row[key] <= 0 for row in rows):
        raise ValueError("invalid_native_integer_identity:" + key)
    return intake.unique_index(rows, key)


def replay_assignments(candidates, seed):
    if type(seed) is not int:
        raise ValueError("invalid_native_split_seed")
    groups = defaultdict(list)
    for row in candidates:
        groups[row["component_id"]].append(row)
    fractions = {"fit": .7, "calibration": .15, "development_test": .15}
    counts = dict.fromkeys(fractions, 0)
    roles = {}
    for cid, members in sorted(groups.items(), key=lambda kv: (
            -len(kv[1]), comp.digest(str(seed) + ":" + kv[0]))):
        role = max(fractions, key=lambda key: fractions[key] * len(candidates) - counts[key])
        roles[cid] = role
        counts[role] += len(members)
    return [{"activity_id": r["activity_id"], "component_id": r["component_id"],
             "identity_context_node_id": r["node_id"], "document_chembl_id": r["document_chembl_id"],
             "assay_chembl_id": r["assay_chembl_id"], "role": roles[r["component_id"]],
             "evaluation_only": roles[r["component_id"]] != "fit"} for r in candidates]


def load_sources(path, expected_sha):
    manifest = intake.bound_json({"path": str(path), "sha256": expected_sha})
    if (manifest.get("schema_version") != MANIFEST or manifest.get("source_kind") != SOURCE
            or manifest.get("phase") != "fit" or manifest.get("implementation_hashes") != implementations()):
        raise ValueError("native_manifest_schema_phase_or_implementation_mismatch")
    plan = intake.bound_json(manifest["split_plan"])
    scope = intake.bound_json(manifest["scope"])
    release = intake.bound_json(manifest["release_receipt"])
    if (plan.get("schema") != PLAN or plan.get("context_sha256") != manifest["base_context"]["sha256"]
            or plan.get("inventory_sha256") != manifest["inventory"]["sha256"]
            or plan.get("native_database_sha256") != release.get("database_sha256")
            or release.get("status") != "complete" or not comp.is_sha(release.get("database_sha256"))):
        raise ValueError("native_reservation_source_binding_mismatch")
    if (scope.get("intake_source_kind") != SOURCE or intake.endpoint_contract(scope)["intake_schema"] != intake.SCHEMA_V3
            or scope.get("endpoint") != plan.get("endpoint") or scope.get("target_annotation") != plan.get("target")
            or scope.get("split_plan_sha256") != manifest["split_plan"]["sha256"]
            or scope.get("physical_target_state_verified") is not False
            or scope.get("resplit_after_exclusions") is not False
            or scope.get("evidence_scope") != "database_curated_reported_experiment_development"):
        raise ValueError("native_scope_mismatch")
    native_rows = bound_lines(manifest["metadata"])
    metadata = indexed(native_rows, "activity_id")
    if len(metadata) != manifest["requested_metadata_rows"]:
        raise ValueError("native_metadata_coverage_mismatch")
    inventory = bound_lines(manifest["inventory"])
    inv = indexed(inventory, "activity_id")
    if set(inv) != {aid for aid, r in metadata.items() if r["standard_type"] == plan["endpoint"]}:
        raise ValueError("native_endpoint_inventory_coverage_mismatch")
    assays = intake.unique_index(bound_lines(manifest["assays"]), "assay_chembl_id")
    documents = intake.unique_index(bound_lines(manifest["documents"]), "document_chembl_id")
    for row in assays.values():
        intake.metadata_fields_only(row, ASSAY_FIELDS, policy=False)
    for row in documents.values():
        intake.metadata_fields_only(row, DOCUMENT_FIELDS, policy=False)
    # Native activities and assays may cite different documents. Preserve both
    # sets instead of dropping an assay's source to match the activity table.
    linked_documents = {r["document_chembl_id"] for r in native_rows} | {
        r["document_chembl_id"] for r in assays.values() if r.get("document_chembl_id") is not None}
    if (set(assays) != {r["assay_chembl_id"] for r in native_rows}
            or set(documents) != linked_documents):
        raise ValueError("native_linked_metadata_coverage_mismatch")
    base = bound_lines(manifest["base_context"], compressed=True)
    base_nodes = intake.unique_index(base, "node_id")
    graph = comp.component_index(base)
    previously_assigned = set()
    for node in base:
        declarations = node["policy_declarations"] + [d for s in node.get("joined_policy_sources", []) for d in s["declarations"]]
        if any(str(v).strip().lower() in {"fit", "train", "training", "calibration", "development_test", "calibration_dev"}
               for d in declarations for k, v in d.items() if k.strip().lower() in {"role", "split", "dataset_split"}):
            previously_assigned.add(graph[node["node_id"]]["component_id"])
    projections = {}
    for ordinal, raw in enumerate(native_rows, 1):
        intake.metadata_fields_only(raw, NATIVE_FIELDS)
        aid = raw["activity_id"]
        if raw["target_chembl_id"] != plan["target"]:
            raise ValueError("native_target_inventory_mismatch")
        nid = "external:" + comp.digest(manifest["metadata"]["sha256"] + ":" + str(ordinal))
        identity = None
        if raw["canonical_smiles"]:
            try:
                identity = common.chemical_identity(raw["canonical_smiles"])
            except ValueError:
                pass
        policy = {k: v for k, v in raw.items() if k.strip().casefold() in comp.POLICY_FIELDS}
        projection = {"record_id": "chembl:activity:" + str(aid), "ligand_id": "chembl:molecule:" + raw["molecule_chembl_id"],
                      "identity_context_node_id": nid, "chemical_identity": identity,
                      "source_provenance": {"source_member": manifest["metadata"]["source_member"],
                                            "source_sha256": manifest["metadata"]["sha256"], "source_line": ordinal,
                                            "row": {"ChEMBL Assay ID": raw["assay_chembl_id"],
                                                    "ChEMBL Document ID": raw["document_chembl_id"],
                                                    "ChEMBL activity metadata": {k: raw[k] for k in intake.METADATA_FIELDS}, **policy}}}
        intake.validate_metadata_row(projection)
        expected = comp.node_from_raw(projection["source_provenance"]["row"], identity, node_id=nid,
                                      record_id=projection["record_id"], ligand_id=projection["ligand_id"],
                                      origin={k: projection["source_provenance"][k] for k in ("source_member", "source_sha256", "source_line")})
        if nid not in base_nodes or comp.canonical(base_nodes[nid]) != comp.canonical(expected):
            raise ValueError("native_metadata_graph_projection_mismatch")
        projections[aid] = projection
    for aid, row in inv.items():
        raw, node = metadata[aid], graph[projections[aid]["identity_context_node_id"]]
        assay, document = assays[raw["assay_chembl_id"]], documents[raw["document_chembl_id"]]
        direct = (assay["confidence_score"] == 9 and assay["relationship_type"] == "D"
                  and assay["assay_type"] == "B" and assay["assay_tax_id"] == 9606)
        chemical = projections[aid]["chemical_identity"] is not None
        if node["blocked"]:
            reason = "reserved_or_unknown_component"
        elif node["component_id"] in previously_assigned:
            reason = "previously_assigned_component"
        elif not chemical:
            reason = "chemical_identity_unavailable"
        elif not direct:
            reason = "direct_human_binding_metadata_not_satisfied"
        elif document["document_type"] != "PUBLICATION":
            reason = "primary_publication_route_not_selected"
        else:
            reason = CANDIDATE
        expected = {"component_id": node["component_id"], "blocked": node["blocked"],
                    "intake_reason": reason, "metadata_direct_human_binding": direct,
                    "chemical_identity_available": chemical, "document_type": document["document_type"],
                    "node_id": projections[aid]["identity_context_node_id"],
                    **{k: raw[k] for k in ("activity_id", "assay_chembl_id", "document_chembl_id", "molecule_chembl_id", "standard_type")}}
        if any(row.get(k) != v for k, v in expected.items()):
            raise ValueError("native_inventory_replay_mismatch")
    expected_assignments = replay_assignments([r for r in inventory if r["intake_reason"] == CANDIDATE], plan["seed"])
    if (plan["assignments"] != expected_assignments or plan["role_counts"] != dict(Counter(a["role"] for a in expected_assignments))
            or plan["component_role_counts"] != dict(Counter(dict((a["component_id"], a["role"]) for a in expected_assignments).values()))):
        raise ValueError("native_frozen_assignment_replay_mismatch")
    assignments = indexed(plan["assignments"], "activity_id")
    fit_assays = {a["assay_chembl_id"] for a in assignments.values() if a["role"] == "fit"}
    if set(scope["methods"]) - fit_assays:
        raise ValueError("native_nonfit_method_content_in_fit_phase")
    observations = bound_lines(manifest["assignment_observations"])
    if observations != plan["assignments"]:
        raise ValueError("native_role_observation_mismatch")
    current = bound_lines(manifest["role_context"], compressed=True)
    if current[:len(base)] != base or len(current) != len(base) + len(observations):
        raise ValueError("native_original_context_not_preserved")
    for i, a in enumerate(observations, 1):
        expected = dict(base_nodes[a["identity_context_node_id"]],
                        node_id="external:" + comp.digest(manifest["assignment_observations"]["sha256"] + ":" + str(i)),
                        policy_declarations=base_nodes[a["identity_context_node_id"]]["policy_declarations"] +
                        [{"role": a["role"], "evaluation_only": a["evaluation_only"]}],
                        source={"source_member": manifest["assignment_observations"]["source_member"],
                                "source_sha256": manifest["assignment_observations"]["sha256"], "source_line": i})
        if current[len(base) + i - 1] != expected:
            raise ValueError("native_role_context_projection_mismatch")
    del graph
    current_graph = comp.component_index(current)
    if any(current_graph[a["identity_context_node_id"]]["blocked"] != a["evaluation_only"] for a in observations):
        raise ValueError("native_role_component_conflict")
    # Bind method source files, not just a path string in a review declaration.
    for method in scope["methods"].values():
        for entry in method.get("evidence_files", []):
            intake.read_bound(entry["path"], entry["sha256"])
    return manifest, plan, scope, metadata, inventory, projections, current_graph, current, release


def derive(path, expected_sha):
    manifest, plan, scope, metadata, inventory, projections, graph, context, release = load_sources(path, expected_sha)
    assignments = indexed(plan["assignments"], "activity_id")
    values, origins = {}, {}
    for capture in manifest["native_exports"]:
        query = intake.bound_json(capture["query_plan"])
        if (capture.get("source_kind") != SOURCE or capture.get("database_sha256") != release["database_sha256"]
                or query.get("role_plan_sha256") != manifest["split_plan"]["sha256"]):
            raise ValueError("native_export_source_binding_mismatch")
        ids = query["parameters"]
        if len(ids) != len(set(ids)) or any(type(aid) is not int or aid not in assignments or assignments[aid]["role"] != "fit" for aid in ids):
            raise ValueError("native_export_contains_nonfit_or_duplicate_identity")
        sql = query.get("sql", "")
        prefix, marker, suffix = sql.partition(" FROM activities WHERE activity_id IN (")
        if (not marker or not prefix.startswith("SELECT ")
                or len(prefix[7:].split(",")) != len(VALUE_FIELDS)
                or set(prefix[7:].split(",")) != VALUE_FIELDS
                or suffix != ",".join("?" for _ in ids) + ") ORDER BY activity_id"):
            raise ValueError("native_export_query_not_allowlisted")
        # Check role/method before opening the exported outcome file.
        for aid in ids:
            method = scope["methods"].get(metadata[aid]["assay_chembl_id"], {})
            if (method.get("document_chembl_id") != metadata[aid]["document_chembl_id"]
                    or method.get("method_eligible") is not True or method.get("method_admission_issues") != []
                    or method.get("bibliographic_metadata", {}).get("review_article_indexed") is not False
                    or method.get("computed_or_QSAR_label_language_observed") is not False
                    or method.get("endpoint_subtype") != scope["endpoint_subtype"]
                    or method.get("citation_identity_status") != "resolved" or not method.get("method_description")
                    or not method.get("evidence_files")):
                raise ValueError("native_export_method_not_admitted")
        captured = bound_lines(capture["records"])
        indexed(captured, "activity_id")
        if [row["activity_id"] for row in captured] != ids:
            raise ValueError("native_export_query_coverage_mismatch")
        for ordinal, value in enumerate(captured, 1):
            aid = value["activity_id"]
            if aid in values:
                raise ValueError("duplicate_native_export_activity_id")
            if set(value) != VALUE_FIELDS:
                raise ValueError("native_export_column_mismatch")
            raw = metadata[aid]
            for field, native in {"activity_id": "activity_id", "assay_id": "native_assay_id", "doc_id": "native_doc_id",
                                  "molregno": "native_molregno", "record_id": "record_id", "src_id": "src_id",
                                  "type": "type", "standard_type": "standard_type"}.items():
                if type(value[field]) is not type(raw[native]) or value[field] != raw[native]:
                    raise ValueError("native_export_metadata_mismatch:" + field)
            values[aid] = {**{k: raw[k] for k in intake.METADATA_FIELDS}, **value}
            origins[aid] = {"source_kind": SOURCE, **deepcopy(capture), "source_line": ordinal}
    rows = []
    for aid, assignment in sorted(assignments.items()):
        assay, doc = metadata[aid]["assay_chembl_id"], metadata[aid]["document_chembl_id"]
        local_scope = scope
        if assay not in scope["methods"]:
            local_scope = {**scope, "methods": {**scope["methods"], assay: {
                "document_chembl_id": doc, "bibliographic_metadata": {"review_article_indexed": None},
                "computed_or_QSAR_label_language_observed": None, "method_eligible": False,
                "method_admission_issues": ["method_evidence_not_available_in_this_phase"],
                "citation_identity_status": "unresolved", "endpoint_subtype": scope["endpoint_subtype"]}}}
        row = intake.normalized_record(projections[aid], assignment, local_scope,
                                       graph[assignment["identity_context_node_id"]], values.get(aid), origins.get(aid))
        row["native_metadata_record"] = deepcopy(metadata[aid])
        rows.append(row)
    by_id = indexed(rows, "activity_id")
    ledger = [{"original_inventory": deepcopy(item), "original_assignment": assignments.get(item["activity_id"]),
               "status": "not_selected_by_original_metadata_plan" if item["activity_id"] not in by_id else
               "observation_withheld" if by_id[item["activity_id"]]["native_activity"] is None else
               "point_eligible" if by_id[item["activity_id"]]["eligible_for_point_model"] else "excluded_point_model"}
              for item in inventory]
    summary = {"schema_version": intake.SCHEMA_V3, "phase": "fit", "source_kind": SOURCE,
               "manifest_path": str(path), "manifest_sha256": expected_sha, "implementation_hashes": implementations(),
               "split_plan_sha256": manifest["split_plan"]["sha256"], "intake_scope_sha256": manifest["scope"]["sha256"],
               "requested_metadata_rows": len(metadata), "endpoint_inventory_rows": len(inventory),
               "metadata_selected_rows": len(rows), "assigned_role_counts": plan["role_counts"],
               "observations_retrieved": len(values), "labels_withheld": len(rows) - len(values),
               "point_eligible_rows": sum(r["eligible_for_point_model"] for r in rows),
               "eligible_role_counts": dict(Counter(r["assigned_role"] for r in rows if r["eligible_for_point_model"])),
               "ledger_counts": dict(Counter(r["status"] for r in ledger)),
               "exclusion_counts": dict(Counter(i for r in rows for i in r["admission_issues"])),
               "identity_context_nodes": len(context), "scientific_validation": False,
               "customer_execution": False, "training_executed": False}
    return summary, {**plan, "counts": plan["role_counts"]}, scope, rows, ledger, context


def build(*, manifest_path, manifest_sha256, output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementations()
    summary, _, _, rows, ledger, context = derive(manifest_path, manifest_sha256)
    if implementations() != before:
        raise ValueError("implementation_changed_during_native_intake")
    output_dir.mkdir(parents=True)
    for name, items in (("records", rows), ("ledger", ledger), ("identity-context", context)):
        path = output_dir / (name + ".jsonl")
        path.write_text("".join(common.json_text(r) + "\n" for r in items))
        summary[name.replace("-", "_") + "_sha256"] = common.file_sha(path)
    summary["cost"] = {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                       "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       "scope": "CPU native source validation, complete graph replay, normalization and output; excludes acquisition"}
    (output_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    return summary


def load_intake(input_dir, summary_sha256, phase):
    if phase != "fit":
        raise ValueError("native_evaluation_capture_contract_not_implemented")
    input_dir = Path(input_dir)
    saved = intake.bound_json({"path": str(input_dir / "summary.json"), "sha256": summary_sha256})
    expected, plan, scope, rows, ledger, context = derive(saved["manifest_path"], saved["manifest_sha256"])
    for key, value in expected.items():
        if saved.get(key) != value:
            raise ValueError("native_intake_summary_mismatch:" + key)
    for name, expected_rows in (("records", rows), ("ledger", ledger), ("identity-context", context)):
        items = intake.bound_jsonl({"path": str(input_dir / (name + ".jsonl")),
                                   "sha256": saved[name.replace("-", "_") + "_sha256"]})
        if items != expected_rows:
            raise ValueError("native_intake_cache_mismatch:" + name)
    return saved, plan, scope, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(manifest_path=args.manifest, manifest_sha256=args.manifest_sha256,
                           output_dir=args.output_dir), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
