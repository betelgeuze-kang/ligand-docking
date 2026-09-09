"""Offline ChEMBL-native measured intake with a preassigned metadata split.

This adapter reuses the public identity graph and chemical canonicalizer. A
database target annotation is not a verified receptor/assay physical state.
Capture manifests contain only the outcome phase authorized by the split plan.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import json
import math
from pathlib import Path
import resource
import time

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as bindingdb
from tools.product import public_chembl_measurement as measurement
from tools.product import train_public_assay_selector as selector

SCHEMA = "public_chembl_assay_development_v1"
MANIFEST_SCHEMA = "public_chembl_preassigned_metadata_manifest_v1"
PLAN_SCHEMA = "public_chembl_kinase_ic50_predeclared_split_v1"
SCHEMA_V2 = "public_chembl_assay_development_v2"
MANIFEST_SCHEMA_V2 = "public_chembl_preassigned_metadata_manifest_v2"
PLAN_SCHEMA_V2 = "public_chembl_predeclared_split_v2"
METADATA_FIELDS = {
    "activity_id", "assay_chembl_id", "document_chembl_id", "molecule_chembl_id",
    "target_chembl_id", "canonical_smiles", "standard_type", "src_id", "record_id", "type",
}
ACTIVITY_FIELDS = METADATA_FIELDS | {
    "value", "units", "relation", "upper_value", "text_value", "standard_value",
    "standard_units", "standard_relation", "standard_upper_value", "standard_text_value",
    "standard_flag", "potential_duplicate", "data_validity_comment", "activity_comment",
}
ROLES = {"fit", "calibration", "development_test"}
ROW_FIELDS = {"record_id", "ligand_id", "identity_context_node_id", "chemical_identity", "source_provenance"}
RAW_FIELDS = {"Article DOI", "PMID", "ChEMBL Assay ID", "ChEMBL Document ID", "ChEMBL Parent Molecule ID",
              "ChEMBL activity metadata", "ChEMBL document metadata", "ChEMBL molecule metadata",
              "ChEMBL source metadata", "Ligand SMILES", "Ligand InChI Key"}
NESTED_FIELDS = {
    "ChEMBL document metadata": {"doc_type", "document_chembl_id", "doi", "journal", "pubmed_id", "src_id", "title", "year"},
    "ChEMBL molecule metadata": {"molecule_chembl_id", "molecule_hierarchy"},
    "ChEMBL source metadata": {"src_comment", "src_description", "src_id", "src_short_name", "src_url"},
}


def endpoint_contract(scope):
    """Only explicitly supported endpoint/subtype pairs select a schema version."""
    endpoint, subtype = scope.get("endpoint"), scope.get("endpoint_subtype")
    if (endpoint, subtype) == ("IC50", "enzyme_inhibition_IC50"):
        version = "v1"
    elif (endpoint, subtype) == ("Ki", "enzyme_inhibition_Ki"):
        version = "v2"
    else:
        raise ValueError("unsupported_chembl_development_scope")
    return {
        "endpoint": endpoint, "endpoint_subtype": subtype,
        "prediction_quantity": "negative_log10_molar_" + endpoint,
        "intake_schema": SCHEMA if version == "v1" else SCHEMA_V2,
        "manifest_schema": MANIFEST_SCHEMA if version == "v1" else MANIFEST_SCHEMA_V2,
        "plan_schema": PLAN_SCHEMA if version == "v1" else PLAN_SCHEMA_V2,
        "model_schema": "public_chembl_cheap_selector_ridge_" + version,
        "frozen_schema": "public_chembl_fit_frozen_before_evaluation_" + version,
        "evaluation_schema": "public_chembl_frozen_selector_evaluation_" + version,
    }


def metadata_fields_only(value, allowed, *, policy=True):
    if not isinstance(value, dict) or any(key not in allowed and (not policy or key.strip().casefold() not in components.POLICY_FIELDS) for key in value):
        raise ValueError("nonmetadata_field_in_activity_projection")
    components.reservation_status(components.policy_declarations(value))


def scalar_metadata(value, integer_fields=()):
    for key, item in value.items():
        if key in integer_fields:
            if item is not None and type(item) is not int:
                raise ValueError("invalid_metadata_scalar_type")
        elif item is not None and not isinstance(item, str):
            raise ValueError("invalid_metadata_scalar_type")


def validate_metadata_row(row):
    metadata_fields_only(row, ROW_FIELDS)
    source = row["source_provenance"]
    metadata_fields_only(source, {"row", "source_line", "source_member", "source_sha256"}, policy=False)
    raw = source["row"]
    metadata_fields_only(raw, RAW_FIELDS)
    native = raw["ChEMBL activity metadata"]
    if set(native) != METADATA_FIELDS:
        raise ValueError("nonmetadata_activity_projection")
    scalar_metadata(native, {"activity_id", "record_id", "src_id"})
    if (raw.get("ChEMBL Assay ID") != native["assay_chembl_id"]
            or raw.get("ChEMBL Document ID") != native["document_chembl_id"]
            or row["ligand_id"] != "chembl:molecule:" + native["molecule_chembl_id"]):
        raise ValueError("native_activity_identity_projection_mismatch")
    if "Ligand SMILES" in raw and raw["Ligand SMILES"] != native["canonical_smiles"]:
        raise ValueError("native_activity_smiles_projection_mismatch")
    for key, fields in NESTED_FIELDS.items():
        if key in raw:
            metadata_fields_only(raw[key], fields, policy=False)
            if key != "ChEMBL molecule metadata":
                scalar_metadata(raw[key], {"src_id", "pubmed_id", "year"})
    molecule = raw.get("ChEMBL molecule metadata", {})
    document = raw.get("ChEMBL document metadata", {})
    if document and document["document_chembl_id"] != native["document_chembl_id"]:
        raise ValueError("native_activity_document_projection_mismatch")
    if molecule and molecule["molecule_chembl_id"] != native["molecule_chembl_id"]:
        raise ValueError("native_activity_molecule_projection_mismatch")
    if molecule.get("molecule_hierarchy") is not None:
        metadata_fields_only(molecule["molecule_hierarchy"], {"active_chembl_id", "molecule_chembl_id", "parent_chembl_id"}, policy=False)
        scalar_metadata(molecule["molecule_hierarchy"])
        if raw.get("ChEMBL Parent Molecule ID") != molecule["molecule_hierarchy"]["parent_chembl_id"]:
            raise ValueError("native_activity_parent_projection_mismatch")
    return native


def read_bound(path, expected):
    raw = Path(path).read_bytes()
    bindingdb.require_sha(bindingdb.digest(raw), expected)
    return raw


def bound_json(entry):
    return components.loads(read_bound(entry["path"], entry["sha256"]).decode())


def bound_jsonl(entry):
    return [components.loads(line) for line in read_bound(entry["path"], entry["sha256"]).decode().splitlines()]


def unique_index(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError("duplicate_" + key)
        result[value] = row
    return result


def implementation_hashes():
    return {
        "normalizer": bindingdb.file_sha(Path(__file__)),
        "measurement": bindingdb.file_sha(Path(measurement.__file__)),
        "chemical_identity": bindingdb.file_sha(Path(bindingdb.__file__)),
        "components": bindingdb.file_sha(Path(components.__file__)),
    }


def load_metadata(manifest_path, expected_sha):
    """Verify all supplied identities and preassigned roles before reading labels."""
    manifest = bound_json({"path": str(manifest_path), "sha256": expected_sha})
    if manifest.get("schema_version") not in {MANIFEST_SCHEMA, MANIFEST_SCHEMA_V2}:
        raise ValueError("unsupported_chembl_metadata_manifest")
    plan = bound_json(manifest["split_plan"])
    scope = bound_json(manifest["intake_scope"])
    contract = endpoint_contract(scope)
    if (plan.get("schema_version") != contract["plan_schema"] or set(plan["counts"]) != ROLES
            or manifest["schema_version"] != contract["manifest_schema"]):
        raise ValueError("unsupported_predeclared_plan")
    if contract["plan_schema"] == PLAN_SCHEMA_V2 and any(plan.get(key) != value for key, value in {
        "endpoint": contract["endpoint"], "prediction_quantity": contract["prediction_quantity"],
        "target_annotation": scope.get("target_annotation"),
    }.items()):
        raise ValueError("plan_endpoint_contract_mismatch")
    if (scope.get("split_plan_sha256") != manifest["split_plan"]["sha256"]
            or plan.get("input_full_context_sha256") != manifest["identity_context"]["sha256"]
            or plan.get("input_normalized_metadata_sha256") != manifest["normalized_metadata"]["sha256"]
            or plan.get("algorithm_source_sha256") != bindingdb.file_sha(Path(selector.__file__))
            or plan.get("component_implementation_sha256") != implementation_hashes()["components"]):
        raise ValueError("plan_metadata_binding_mismatch")
    if (scope.get("evidence_scope") != "database_curated_reported_experiment_development"
            or scope.get("physical_target_state_verified") is not False
            or scope.get("resplit_after_exclusions") is not False):
        raise ValueError("unsupported_chembl_development_scope")
    rows = bound_jsonl(manifest["normalized_metadata"])
    context = bound_jsonl(manifest["identity_context"])
    # The supplied full universe includes rejected rows and non-ChEMBL sources.
    graph = components.require_normalized_coverage(rows, context)
    indexed = {}
    @lru_cache(maxsize=None)
    def recompute_identity(smiles):
        if smiles is None or smiles == "":
            return None
        if not isinstance(smiles, str):
            raise ValueError("invalid_metadata_smiles_type")
        try:
            return bindingdb.chemical_identity(smiles)
        except ValueError:
            return None
    for row in rows:
        native = validate_metadata_row(row)
        if recompute_identity(native["canonical_smiles"]) != row["chemical_identity"]:
            raise ValueError("chemical_identity_cache_mismatch")
        aid = native["activity_id"]
        if type(aid) is not int or aid <= 0 or aid in indexed:
            raise ValueError("invalid_or_duplicate_activity_id")
        if row["record_id"] != f"chembl:activity:{aid}":
            raise ValueError("activity_record_identity_mismatch")
        indexed[aid] = row
    if len(rows) != manifest["requested_activity_rows"]:
        raise ValueError("requested_metadata_coverage_mismatch")
    assignments = unique_index(plan["assignments"], "activity_id")
    if not set(assignments) <= set(indexed):
        raise ValueError("plan_activity_missing_from_full_metadata")
    selected = [row for aid, row in indexed.items() if aid in assignments]
    # Reuse the original label-free splitter; no assignment after filtering.
    splits, group_ids = selector.split_components(selected, plan["seed"], identity_context=context)
    for role, indices in splits.items():
        for index in indices:
            row = selected[index]
            native = row["source_provenance"]["row"]["ChEMBL activity metadata"]
            declared = assignments[native["activity_id"]]
            if any(declared.get(key) != value for key, value in {
                "record_id": row["record_id"], "identity_context_node_id": row["identity_context_node_id"],
                "component_id": group_ids[index], "role": role,
                "assay_chembl_id": native["assay_chembl_id"], "document_chembl_id": native["document_chembl_id"],
            }.items()):
                raise ValueError("preassigned_role_or_component_mismatch")
    counts = dict(Counter(item["role"] for item in assignments.values()))
    if counts != plan["counts"]:
        raise ValueError("plan_role_count_mismatch")
    if set(scope["fit_retrieval_activity_ids"]) != {aid for aid, item in assignments.items() if item["role"] == "fit"}:
        raise ValueError("scope_fit_activity_mismatch")
    return manifest, plan, scope, indexed, context, graph


def read_captures(capture_path, expected_sha, manifest, plan, scope, indexed, phase):
    """Reject extra/duplicate/missing API occurrences and metadata changes."""
    contract = endpoint_contract(scope)
    capture = bound_json({"path": str(capture_path), "sha256": expected_sha})
    if (capture.get("schema_version") != "chembl_activity_capture_manifest_v1"
            or capture.get("phase") != phase
            or capture.get("split_plan_sha256") != manifest["split_plan"]["sha256"]
            or capture.get("intake_scope_sha256") != manifest["intake_scope"]["sha256"]
            or set(capture.get("allowed_fields", [])) != ACTIVITY_FIELDS):
        raise ValueError("capture_phase_or_source_binding_mismatch")
    expected = {item["activity_id"] for item in plan["assignments"]
                if (item["role"] == "fit") == (phase == "fit")}
    if set(capture["expected_activity_ids"]) != expected or len(capture["expected_activity_ids"]) != len(expected):
        raise ValueError("capture_requested_role_mismatch")
    frozen_time = None
    if phase == "evaluation":
        if "frozen_fit" not in capture:
            raise ValueError("frozen_fit_required_before_evaluation_capture")
        frozen = bound_json(capture["frozen_fit"])
        if (frozen.get("schema_version") != contract["frozen_schema"]
                or frozen.get("training_executed") is not True or frozen.get("evaluation_values_read") != 0
                or frozen.get("split_plan_sha256") != manifest["split_plan"]["sha256"]
                or frozen.get("intake_scope_sha256") != manifest["intake_scope"]["sha256"]):
            raise ValueError("incompatible_frozen_fit_for_evaluation")
        checkpoint = bound_json(frozen["checkpoint"])
        protocol = bound_json(frozen["protocol"])
        predictions = unique_index(bound_jsonl(frozen["predictions"]), "activity_id")
        assignments = unique_index(plan["assignments"], "activity_id")
        if (checkpoint["training_protocol_sha256"] != frozen["protocol"]["sha256"]
                or protocol["assignments"] != plan["assignments"]
                or set(predictions) != set(assignments)):
            raise ValueError("frozen_fit_prediction_coverage_mismatch")
        for aid, prediction in predictions.items():
            if (prediction.get("assigned_role") != assignments[aid]["role"]
                    or prediction.get("component_id") != assignments[aid]["component_id"]
                    or prediction.get("observed_label_included") is not False):
                raise ValueError("frozen_prediction_role_or_label_mismatch")
            expected_fields = {"activity_id", "record_id", "assigned_role", "component_id", "predicted",
                               "mean_baseline", "prediction_quantity", "status", "reason", "observed_label_included"}
            if set(prediction) != expected_fields:
                raise ValueError("unexpected_frozen_prediction_fields")
            reasons = chemistry_issues(indexed[aid]["chemical_identity"], scope)
            if (prediction["reason"] != reasons or prediction["status"] != ("abstained" if reasons else "predicted")
                    or prediction["mean_baseline"] != checkpoint["mean_baseline"]
                    or prediction["record_id"] != indexed[aid]["record_id"]
                    or prediction["prediction_quantity"] != contract["prediction_quantity"]):
                raise ValueError("frozen_baseline_or_abstention_mismatch")
            if reasons:
                if prediction["predicted"] is not None:
                    raise ValueError("unsupported_chemical_prediction")
            else:
                from tools.product.train_public_chembl_selector import predict_checkpoint
                value = predict_checkpoint(Path(frozen["checkpoint"]["path"]), frozen["checkpoint"]["sha256"],
                                           [indexed[aid]["chemical_identity"]["canonical_isomeric_smiles"]],
                                           checkpoint["target_annotation_sha256"], endpoint=contract["endpoint"])[0]
                if (type(prediction["predicted"]) not in (int, float)
                        or not math.isclose(value, prediction["predicted"], rel_tol=1e-12, abs_tol=1e-12)):
                    raise ValueError("frozen_prediction_checkpoint_mismatch")
        frozen_time = datetime.fromisoformat(frozen["frozen_at_utc"])
    result, origins = {}, {}
    for part in capture["captures"]:
        response = bound_json(part)
        request = bound_json({"path": part["request_path"], "sha256": part["request_sha256"]})
        execution = bound_json({"path": part["execution_path"], "sha256": part["execution_sha256"]})
        if execution.get("ok") is not True or execution.get("exit_code") != 0:
            raise ValueError("unsuccessful_activity_capture")
        if frozen_time is not None and datetime.fromisoformat(execution["at_utc"]) <= frozen_time:
            raise ValueError("evaluation_capture_not_after_frozen_fit")
        if execution.get("decoded_response_sha256") != part["sha256"] or execution.get("config_sha256") != part["request_sha256"]:
            raise ValueError("capture_execution_hash_mismatch")
        if (request.get("base_url") != "https://www.ebi.ac.uk/chembl/api/data"
                or request.get("path") != "activity.json"
                or set(request["params"]["only"].split(",")) != ACTIVITY_FIELDS):
            raise ValueError("unsupported_activity_capture_request")
        want = part["expected_activity_ids"]
        request_ids = [int(value) for value in request["params"]["activity_id__in"].split(",")]
        if len(set(want)) != len(want) or sorted(want) != sorted(request_ids) or not set(want) <= expected:
            raise ValueError("capture_page_request_identity_mismatch")
        page = response["page_meta"]
        if page.get("next") is not None or page.get("total_count") != len(want):
            raise ValueError("incomplete_activity_page")
        activities = response["activities"]
        if len(activities) != len(want) or {item["activity_id"] for item in activities} != set(want):
            raise ValueError("activity_capture_occurrence_gap")
        for position, activity in enumerate(activities):
            if set(activity) - ACTIVITY_FIELDS:
                raise ValueError("unexpected_activity_payload_field")
            aid = activity["activity_id"]
            if aid in result:
                raise ValueError("duplicate_captured_activity_id")
            native = indexed[aid]["source_provenance"]["row"]["ChEMBL activity metadata"]
            if any(key not in activity or activity[key] != value or type(activity[key]) is not type(value)
                   for key, value in native.items()):
                raise ValueError("activity_metadata_changed_after_split")
            result[aid] = activity
            origins[aid] = {"response_path": part["path"], "response_sha256": part["sha256"],
                            "response_record_index": position, "request_sha256": part["request_sha256"],
                            "execution_sha256": part["execution_sha256"],
                            "capture_semantics": capture["capture_semantics"]}
    if set(result) != expected or capture["response_rows"] != len(result):
        raise ValueError("full_capture_coverage_mismatch")
    return capture, result, origins


def chemistry_issues(identity, scope):
    chemistry = scope["chemistry_scope"]
    issues = []
    if not chemistry["heavy_atoms_min"] <= identity["heavy_atom_count"] <= chemistry["heavy_atoms_max"]:
        issues.append("chemical_size_outside_scope")
    if (identity["fragment_count"] != chemistry["fragment_count"]
            or set(identity["elements"]) - set(chemistry["elements"])
            or identity["radical_electrons"] != chemistry["radical_electrons"]
            or identity["isotope_atoms"] != chemistry["isotope_atoms"]):
        issues.append("chemical_state_outside_declared_scope")
    return sorted(issues)


def normalized_record(metadata, assignment, scope, graph_node, activity=None, origin=None):
    """Preserve the native JSON and identity projection as distinct provenance."""
    contract = endpoint_contract(scope)
    native = metadata["source_provenance"]["row"]["ChEMBL activity metadata"]
    if native["target_chembl_id"] != scope["target_annotation"] or native["standard_type"] != scope["endpoint"]:
        raise ValueError("native_activity_outside_declared_target_endpoint")
    method = scope["methods"][native["assay_chembl_id"]]
    if method["document_chembl_id"] != native["document_chembl_id"]:
        raise ValueError("method_source_scope_mismatch")
    reviewed = method.get("bibliographic_metadata", {}).get("review_article_indexed")
    computed = method.get("computed_or_QSAR_label_language_observed")
    method_supported = reviewed is False and computed is False
    if contract["intake_schema"] == SCHEMA and not method_supported:
        raise ValueError("method_source_scope_mismatch")
    if contract["intake_schema"] == SCHEMA_V2:
        method_supported = (method_supported and method.get("endpoint_subtype") == contract["endpoint_subtype"]
                            and method.get("citation_identity_status") == "resolved"
                            and isinstance(method.get("method_description"), str) and bool(method["method_description"].strip()))
    identity = metadata["chemical_identity"]
    issues = chemistry_issues(identity, scope)
    if not method_supported:
        issues.append("assay_method_or_primary_document_unresolved")
    observation = measurement.normalize_measurement(activity) if activity is not None else None
    profile = {
        "evidence_kind": "experimental_label" if computed is False else "unknown",
        "evidence_basis": "curated_reported_experiment" if method_supported else "unresolved_or_incompatible_source",
        "evidence_scope": scope["evidence_scope"], "source_id": native["src_id"],
        "primary_source_status": "not_independently_verified", "document_kind": "research_article" if reviewed is False else "review" if reviewed is True else "unresolved",
        "citation_identity_status": "resolved" if contract["intake_schema"] == SCHEMA else method.get("citation_identity_status"),
        "assay_method_evidence_status": "curated_description_bound" if method_supported else "unresolved",
        "endpoint_subtype": scope["endpoint_subtype"] if method_supported else method.get("endpoint_subtype"),
        "requested_endpoint_subtype": scope["endpoint_subtype"],
        "target_state_status": "catalogue_annotation_only", "source_license": scope["source_database_license"],
        "raw_metadata": deepcopy(metadata["source_provenance"]["row"]),
        "source_policy_declarations": components.policy_declarations(metadata),
        "assigned_role": assignment["role"], "graph_blocked": graph_node["blocked"],
        "measurement_status": observation["status"] if observation else "withheld",
        "potential_duplicate": activity.get("potential_duplicate") if activity is not None else None,
        "data_validity_comment": activity.get("data_validity_comment") if activity is not None else None,
    }
    purpose = "fit" if assignment["role"] == "fit" else "evaluation"
    admission = None
    if activity is not None:
        admission = measurement.admission(profile, purpose=purpose)
        issues.extend(admission["issues"])
        if observation["endpoint"] != scope["endpoint"]:
            issues.append("endpoint_mismatch")
        if not observation["measurement_is_exact_for_fit"]:
            issues.append("measurement_not_supported_exact_point")
        if type(activity.get("standard_flag")) not in (bool, int) or activity["standard_flag"] != 1:
            issues.append("standard_flag_not_confirmed")
        if activity.get("data_validity_comment") not in (None, ""):
            issues.append("data_validity_comment_requires_individual_resolution")
        if activity.get("activity_comment") not in (None, ""):
            issues.append("activity_comment_requires_individual_resolution")
    target_annotation = {"chembl_target_id": native["target_chembl_id"], "scope": scope["target_scope"],
                         "physical_state_verified": False, "endpoint_subtype": scope["endpoint_subtype"]}
    return {
        "schema_version": contract["intake_schema"], "record_id": metadata["record_id"], "activity_id": native["activity_id"],
        "ligand_id": metadata["ligand_id"], "identity_context_node_id": metadata["identity_context_node_id"],
        "component_id": assignment["component_id"], "assigned_role": assignment["role"],
        "assignment": deepcopy(assignment), "source_policy_declarations": components.policy_declarations(metadata),
        "evidence_kind": profile["evidence_kind"], "evidence_basis": profile["evidence_basis"],
        "primary_source_status": "not_independently_verified", "source_license": scope["source_database_license"],
        "native_activity": deepcopy(activity), "native_activity_origin": deepcopy(origin),
        "identity_metadata_projection": deepcopy(metadata), "method_evidence": deepcopy(method),
        "target_annotation": target_annotation, "target_annotation_sha256": components.digest(components.canonical(target_annotation)),
        "chemical_identity": deepcopy(identity), "assayed_microstate_verified": False,
        "observation": observation, "admission": admission,
        "label_access_status": "withheld_by_preassigned_role" if activity is None else "retrieved",
        "admission_issues": sorted(set(issues)),
        "eligible_for_point_model": activity is not None and not issues,
        "assay_id": "chembl:assay:" + native["assay_chembl_id"],
        "coordinates": None, "atom_order": None, "pose": None, "environment": None,
        "potential_energy": None, "energy_residual": None, "force_labels": None,
    }


def derive_outputs(plan, scope, indexed, context, graph, values, origins):
    assignments = unique_index(plan["assignments"], "activity_id")
    rows = [normalized_record(indexed[aid], assignments[aid], scope,
                              graph[indexed[aid]["identity_context_node_id"]], values.get(aid), origins.get(aid))
            for aid in sorted(assignments)]
    by_id = unique_index(rows, "activity_id")
    ledger = []
    for aid, item in indexed.items():
        record = by_id.get(aid)
        ledger.append({"activity_id": aid, "record_id": item["record_id"],
                       "identity_context_node_id": item["identity_context_node_id"],
                       "status": ("not_selected_by_metadata_plan" if record is None else
                                  "label_withheld" if record["observation"] is None else
                                  "normalized_point_eligible" if record["eligible_for_point_model"] else "excluded_point_model"),
                       "assigned_role": record["assigned_role"] if record else None,
                       "issues": record["admission_issues"] if record else [],
                       "identity_vertex_retained": True})
    # Preserve original policy dictionaries and add this experiment's reservations.
    updated_context = deepcopy(context)
    by_node = {item["identity_context_node_id"]: item for item in assignments.values()}
    for node in updated_context:
        if node["node_id"] in by_node:
            node["policy_declarations"].append({"split": by_node[node["node_id"]]["role"]})
    updated_graph = components.component_index(updated_context)
    for item in assignments.values():
        node = updated_graph[item["identity_context_node_id"]]
        if node["blocked"] != (item["role"] != "fit"):
            raise ValueError("role_assignment_component_conflict")
    return rows, ledger, updated_context


def run(*, manifest_path, manifest_sha256, capture_path, capture_sha256, phase, output_dir):
    if phase not in {"fit", "evaluation"}:
        raise ValueError("unsupported_intake_phase")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    source_implementations = implementation_hashes()
    manifest, plan, scope, indexed, context, graph = load_metadata(manifest_path, manifest_sha256)
    capture, values, origins = read_captures(capture_path, capture_sha256, manifest, plan, scope, indexed, phase)
    rows, ledger, updated_context = derive_outputs(plan, scope, indexed, context, graph, values, origins)
    # Detect source changes during this run before publishing a success summary.
    read_bound(manifest_path, manifest_sha256)
    read_bound(capture_path, capture_sha256)
    for entry in (manifest["split_plan"], manifest["intake_scope"], manifest["identity_context"], manifest["normalized_metadata"]):
        read_bound(entry["path"], entry["sha256"])
    for part in capture["captures"]:
        read_bound(part["path"], part["sha256"])
    if implementation_hashes() != source_implementations:
        raise ValueError("implementation_changed_during_intake")
    output_dir.mkdir(parents=True)
    for name, data in (("records.jsonl", rows), ("ledger.jsonl", ledger), ("identity-context.jsonl", updated_context)):
        (output_dir / name).write_text("".join(bindingdb.json_text(item) + "\n" for item in data))
    summary = {
        "schema_version": endpoint_contract(scope)["intake_schema"], "phase": phase, "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256, "capture_manifest_path": str(capture_path),
        "capture_manifest_sha256": capture_sha256, "split_plan_sha256": manifest["split_plan"]["sha256"],
        "intake_scope_sha256": manifest["intake_scope"]["sha256"], "implementation_hashes": implementation_hashes(),
        "records_sha256": bindingdb.file_sha(output_dir / "records.jsonl"),
        "ledger_sha256": bindingdb.file_sha(output_dir / "ledger.jsonl"),
        "identity_context_sha256": bindingdb.file_sha(output_dir / "identity-context.jsonl"),
        "requested_metadata_rows": len(indexed), "metadata_selected_rows": len(rows),
        "identity_context_nodes": len(context), "observations_retrieved": len(values),
        "labels_withheld": len(rows) - len(values), "point_eligible_rows": sum(row["eligible_for_point_model"] for row in rows),
        "ledger_counts": dict(Counter(row["status"] for row in ledger)),
        "exclusion_counts": dict(Counter(issue for row in rows for issue in row["admission_issues"])),
        "assigned_role_counts": plan["counts"],
        "eligible_role_counts": dict(Counter(row["assigned_role"] for row in rows if row["eligible_for_point_model"])),
        "full_requested_recall": None, "full_requested_recall_reason": "unknown_or_excluded_labels_not_assumed_negative",
        "evidence_scope": scope["evidence_scope"], "target_scope": scope["target_scope"],
        "physical_energy": False, "training_executed": False, "customer_execution": False,
        "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                 "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "scope": "single CPU offline intake; excludes acquisition and model training"},
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--captures-sha256", required=True)
    parser.add_argument("--phase", choices=("fit", "evaluation"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(manifest_path=args.manifest, manifest_sha256=args.manifest_sha256,
                 capture_path=args.captures, capture_sha256=args.captures_sha256,
                 phase=args.phase, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
