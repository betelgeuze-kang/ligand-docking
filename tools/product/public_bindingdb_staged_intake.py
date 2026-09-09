"""Offline BindingDB metadata preassignment and phase-limited native intake."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re
import resource
import time
import zipfile

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as bound
from tools.product import train_public_assay_selector as existing

SCHEMA = "public_bindingdb_staged_intake_v1"
MANIFEST_SCHEMA = "public_bindingdb_staged_manifest_v1"
PLAN_SCHEMA = "public_bindingdb_metadata_split_v1"
ROLES = {"fit", "calibration", "development_test"}
ORIGINS = {"BindingDB", "Curated from the literature by BindingDB"}
RAW_FIELDS = {"BindingDB Reactant_set_id", "BindingDB MonomerID", "Ligand SMILES", "Ligand InChI Key",
              "Ligand InChI", "Date in BindingDB", "Date of publication", "BindingDB Entry DOI",
              "Target Name", "Target Source Organism According to Curator or DataSource", "Curation/DataSource",
              "Article DOI", "PMID", "Patent Number", common.CHAIN_COUNT}


def implementation_hashes():
    return {"staged_intake": common.file_sha(Path(__file__)),
            "bindingdb_primitives": common.file_sha(Path(common.__file__)),
            "components": common.file_sha(Path(components.__file__)),
            "selector_primitives": common.file_sha(Path(existing.__file__)),
            "bound_readers": common.file_sha(Path(bound.__file__))}


def metadata_field(name):
    return (name in RAW_FIELDS or name.strip().casefold() in components.POLICY_FIELDS
            or re.fullmatch(r"BindingDB Target Chain Sequence(?: [1-9][0-9]*)?", name) is not None
            or re.fullmatch(r"UniProt \((?:SwissProt|TrEMBL)\) Primary ID of Target Chain(?: [1-9][0-9]*)?", name) is not None)


def read_entry(entry):
    return bound.read_bound(entry["path"], entry["sha256"])


def chemistry_issues(identity, scope):
    if identity is None:
        return ["chemical_identity_missing"]
    result = bound.chemistry_issues(identity, scope)
    if abs(identity["formal_charge"]) > scope["chemistry_scope"]["formal_charge_abs_max"]:
        result.append("chemical_formal_charge_outside_scope")
    return sorted(result)


def load_metadata(manifest_path, manifest_sha256):
    """Reproduce metadata roles and reject reserved IDs before decoding outcomes."""
    manifest = bound.bound_json({"path": str(manifest_path), "sha256": manifest_sha256})
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("unsupported_bindingdb_staged_manifest")
    scope = manifest["scope"]
    if manifest["assay_method_ledger"].get("endpoint") != scope.get("endpoint"):
        raise ValueError("assay_method_ledger_endpoint_mismatch")
    if (scope.get("endpoint") not in {"Ki", "IC50"} or scope.get("source_license") != "CC-BY-4.0"
            or not set(scope.get("source_origins", [])) or not set(scope["source_origins"]) <= ORIGINS
            or scope.get("physical_target_state_verified") is not False
            or scope.get("positive_threshold_negative_log10_molar") != 6.0 or scope.get("top_fraction") != 0.2
            or common.digest(common.json_text(scope["target_annotation"])) != scope["target_annotation_sha256"]):
        raise ValueError("unsupported_bindingdb_scope")
    chemistry = scope["chemistry_scope"]
    if (any(type(chemistry.get(key)) is not int for key in ("heavy_atoms_min", "heavy_atoms_max", "formal_charge_abs_max"))
            or not 5 <= chemistry["heavy_atoms_min"] <= chemistry["heavy_atoms_max"] <= 70
            or not 0 <= chemistry["formal_charge_abs_max"] <= 2 or chemistry.get("fragment_count") != 1
            or chemistry.get("radical_electrons") != 0 or chemistry.get("isotope_atoms") != 0
            or not isinstance(chemistry.get("elements"), list) or not chemistry["elements"]
            or set(chemistry["elements"]) - {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}):
        raise ValueError("unsupported_bindingdb_chemistry_scope")
    rows = bound.bound_jsonl(manifest["normalized_metadata"])
    context = bound.bound_jsonl(manifest["identity_context"])
    plan = bound.bound_json(manifest["split_plan"])
    if (plan.get("schema_version") != PLAN_SCHEMA or set(plan.get("counts", {})) != ROLES
            or plan.get("metadata_sha256") != manifest["normalized_metadata"]["sha256"]
            or plan.get("identity_context_sha256") != manifest["identity_context"]["sha256"]
            or plan.get("splitter_sha256") != common.file_sha(Path(existing.__file__))
            or plan.get("component_implementation_sha256") != common.file_sha(Path(components.__file__))):
        raise ValueError("metadata_plan_binding_mismatch")
    if len(rows) != manifest["requested_target_rows"] or len(context) != manifest["identity_context"]["expected_nodes"]:
        raise ValueError("requested_metadata_or_context_count_mismatch")
    bound.unique_index(rows, "identity_context_node_id")
    record_counts = Counter(row["record_id"] for row in rows)
    source_lines = set()

    @lru_cache(maxsize=None)
    def identity(smiles):
        try:
            return common.chemical_identity(smiles) if isinstance(smiles, str) and smiles else None
        except ValueError:
            return None

    for row in rows:
        if set(row) != {"record_id", "ligand_id", "identity_context_node_id", "chemical_identity", "source_provenance"}:
            raise ValueError("nonmetadata_normalized_field")
        origin = row["source_provenance"]
        if set(origin) != {"source_sha256", "source_member", "source_line", "row"}:
            raise ValueError("unexpected_metadata_origin_field")
        raw = origin["row"]
        if not isinstance(raw, dict) or any(not metadata_field(key) for key in raw):
            raise ValueError("outcome_or_nonmetadata_field")
        for key, value in raw.items():
            if key.strip().casefold() not in components.POLICY_FIELDS and not isinstance(value, str):
                raise ValueError("metadata_source_token_not_string")
        if (origin["source_sha256"] != manifest["archive"]["sha256"] or origin["source_member"] != manifest["archive"]["member"]
                or type(origin["source_line"]) is not int or origin["source_line"] < 2 or origin["source_line"] in source_lines):
            raise ValueError("metadata_native_origin_mismatch")
        source_lines.add(origin["source_line"])
        if (row["record_id"] != "bindingdb:" + raw["BindingDB Reactant_set_id"].strip()
                or row["ligand_id"] != "bindingdb:" + raw.get("BindingDB MonomerID", "").strip()):
            raise ValueError("metadata_source_identifier_mismatch")
        if row["chemical_identity"] != identity(raw.get("Ligand SMILES", "")):
            raise ValueError("chemical_identity_cache_mismatch")
        if common.target_state_identity(raw) != scope["target_annotation"]:
            raise ValueError("metadata_target_annotation_mismatch")
    graph = components.require_normalized_coverage(rows, context)
    assignments = bound.unique_index(plan["assignments"], "record_id")
    if not set(assignments) <= set(record_counts):
        raise ValueError("plan_record_missing_from_metadata")
    selected = [row for row in rows if row["record_id"] in assignments]
    for row in selected:
        rid = row["record_id"]
        raw = row["source_provenance"]["row"]
        if record_counts[rid] != 1:
            raise ValueError("duplicate_record_all_occurrences_blocked")
        if graph[row["identity_context_node_id"]]["blocked"]:
            raise ValueError("reserved_metadata_component")
        if (raw.get("Curation/DataSource") not in scope["source_origins"] or common.target_schema_rejection(raw)
                or chemistry_issues(row["chemical_identity"], scope)):
            raise ValueError("selected_metadata_outside_declared_scope")
    splits, groups = existing.split_components(selected, plan["seed"], identity_context=context)
    actual_counts = {role: len(indices) for role, indices in splits.items()}
    if actual_counts != plan["counts"]:
        raise ValueError("preassigned_role_count_mismatch")
    for role, indices in splits.items():
        for index in indices:
            row = selected[index]
            expected = {"record_id": row["record_id"], "identity_context_node_id": row["identity_context_node_id"],
                        "component_id": groups[index], "role": role}
            if assignments[row["record_id"]] != expected:
                raise ValueError("preassigned_role_or_component_mismatch")
    for name in ("assay_mapping", "assay_descriptions"):
        read_entry(manifest[name])
    methods = bound.unique_index(bound.bound_jsonl(manifest["assay_method_ledger"]), "record_id")
    if set(methods) != set(assignments):
        raise ValueError("method_ledger_assignment_coverage_mismatch")
    for method in methods.values():
        if (set(method) != {"record_id", "status", "reason", "assay_keys", "source_records"}
                or method["status"] not in {"compatible", "incompatible", "unknown", "ambiguous", "missing"}
                or not isinstance(method["reason"], str) or not isinstance(method["assay_keys"], list)
                or not isinstance(method["source_records"], list)):
            raise ValueError("invalid_assay_method_ledger_row")
        if any(not isinstance(key, str) for key in method["assay_keys"]):
            raise ValueError("invalid_assay_key")
        for source in method["source_records"]:
            if (set(source) != {"source_sha256", "source_member", "source_line"}
                    or not components.is_sha(source["source_sha256"]) or not isinstance(source["source_member"], str)
                    or type(source["source_line"]) is not int or source["source_line"] < 2):
                raise ValueError("invalid_method_source_origin")
    return manifest, plan, scope, rows, selected, context, graph, methods


@contextmanager
def binary_table(entry):
    path = Path(entry["path"])
    common.require_sha(common.file_sha(path), entry["sha256"])
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1 or not members[0].filename.endswith(".tsv"):
                raise ValueError("expected_single_metadata_tsv_member")
            with archive.open(members[0]) as stream:
                yield stream, members[0].filename
    else:
        with path.open("rb") as stream:
            yield stream, path.name


def selected_byte_tokens(binary, positions):
    raw = binary.rstrip(b"\r\n")
    previous, column, result = 0, 0, {}
    for match in re.finditer(b"\t", raw):
        if column in positions:
            result[column] = raw[previous:match.start()].decode("utf-8")
        previous, column = match.end(), column + 1
    if column in positions:
        result[column] = raw[previous:].decode("utf-8")
    return result


def phase_assays(manifest, expected_record_ids, selected_record_ids=None):
    """Select native mapping/description IDs before decoding description bodies."""
    links, descriptions = defaultdict(list), defaultdict(list)
    selected_record_ids = selected_record_ids if selected_record_ids is not None else expected_record_ids
    selected_assay_keys = set()
    access = Counter()
    with binary_table(manifest["assay_mapping"]) as (stream, member):
        header = stream.readline().decode("utf-8-sig").rstrip("\r\n").split("\t")
        if len(header) != len(set(header)) or any(not h for h in header):
            raise ValueError("invalid_mapping_header")
        rid_index = header.index("REACTANT_SET_ID")
        key_index = header.index("ENTRYID_ASSAYID")
        policy_indices = {i for i, key in enumerate(header) if key.strip().casefold() in components.POLICY_FIELDS}
        for line, binary in enumerate(stream, 2):
            access["mapping_id_rows_scanned"] += 1
            token = selected_byte_tokens(binary, {rid_index}).get(rid_index, "")
            rid = "bindingdb:" + token.strip()
            if rid in selected_record_ids:
                policy_tokens = selected_byte_tokens(binary, policy_indices | {key_index})
                declarations = components.policy_declarations({header[i]: value for i, value in policy_tokens.items() if i in policy_indices})
                if any(components.reservation_status(declarations)):
                    raise ValueError("reserved_or_unknown_assay_source_policy")
                selected_assay_keys.add(policy_tokens.get(key_index, ""))
            if rid not in expected_record_ids:
                continue
            cells = binary.decode("utf-8").rstrip("\r\n").split("\t")
            if len(cells) != len(header):
                raise ValueError("invalid_selected_mapping_row_shape")
            raw = dict(zip(header, cells))
            links[rid].append({"entry_assay_id": raw["ENTRYID_ASSAYID"], "source_line": line,
                               "source_member": member, "source_sha256": manifest["assay_mapping"]["sha256"], "row": raw})
            access["mapping_full_rows_decoded"] += 1
    keys = {link["entry_assay_id"] for group in links.values() for link in group}
    with binary_table(manifest["assay_descriptions"]) as (stream, member):
        header = stream.readline().decode("utf-8-sig").rstrip("\r\n").split("\t")
        if len(header) != len(set(header)) or any(not h for h in header):
            raise ValueError("invalid_description_header")
        entry_index, assay_index = header.index("ENTRYID"), header.index("ASSAYID")
        policy_indices = {i for i, name in enumerate(header) if name.strip().casefold() in components.POLICY_FIELDS}
        for line, binary in enumerate(stream, 2):
            access["description_id_rows_scanned"] += 1
            tokens = selected_byte_tokens(binary, {entry_index, assay_index})
            key = tokens.get(entry_index, "") + "_" + tokens.get(assay_index, "")
            if key in selected_assay_keys:
                policy_tokens = selected_byte_tokens(binary, policy_indices)
                declarations = components.policy_declarations({header[i]: value for i, value in policy_tokens.items()})
                if any(components.reservation_status(declarations)):
                    raise ValueError("reserved_or_unknown_assay_source_policy")
            if key not in keys:
                continue
            cells = binary.decode("utf-8").rstrip("\r\n").split("\t")
            if len(cells) != len(header):
                raise ValueError("invalid_selected_description_row_shape")
            descriptions[key].append({"source_line": line, "source_member": member,
                                      "source_sha256": manifest["assay_descriptions"]["sha256"], "row": dict(zip(header, cells))})
            access["description_full_rows_decoded"] += 1
    result = {rid: [{"entry_assay_id": link["entry_assay_id"], "mapping_source": link,
                     "description_records": descriptions.get(link["entry_assay_id"], [])} for link in group]
              for rid, group in links.items()}
    for group in result.values():
        for assay in group:
            for source in [assay["mapping_source"], *assay["description_records"]]:
                if any(components.reservation_status(components.policy_declarations(source["row"]))):
                    raise ValueError("reserved_or_unknown_assay_source_policy")
    return result, dict(access)


def native_rows(manifest, metadata_rows, selected, plan, phase, context):
    """Only first ID tokens are decoded for rows outside the authorized phase."""
    if phase not in {"fit", "evaluation"}:
        raise ValueError("unsupported_intake_phase")
    assignments = bound.unique_index(plan["assignments"], "record_id")
    expected = {rid for rid, item in assignments.items() if (item["role"] == "fit") == (phase == "fit")}
    indexed = {row["record_id"]: row for row in selected}
    common.require_sha(common.file_sha(Path(manifest["archive"]["path"])), manifest["archive"]["sha256"])
    captured, total, skipped = {}, 0, 0
    counts = Counter()
    source_origins = {row["source_provenance"]["source_line"]: row["record_id"] for row in metadata_rows}
    source_nodes = [node for node in context if node["node_id"].startswith("source:")
                    and node.get("source", {}).get("source_sha256") == manifest["archive"]["sha256"]
                    and node.get("source", {}).get("source_member") == manifest["archive"]["member"]]
    full_source_origins = {node["source"]["source_line"]: node["record_id"] for node in source_nodes}
    if (len(full_source_origins) != len(source_nodes)
            or set(full_source_origins) != set(range(2, manifest["archive"]["expected_rows"] + 2))):
        raise ValueError("full_native_source_graph_coverage_mismatch")
    seen_origins = set()
    # A first-ID-only pass rejects missing/duplicate selected IDs before any
    # selected outcome is decoded, including duplicates later in the archive.
    with zipfile.ZipFile(manifest["archive"]["path"]) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) != 1 or members[0].filename != manifest["archive"]["member"]:
            raise ValueError("native_archive_member_mismatch")
        with archive.open(members[0]) as stream:
            stream.readline()
            for line, binary in enumerate(stream, 2):
                rid = "bindingdb:" + binary.partition(b"\t")[0].rstrip(b"\r\n").decode("utf-8").strip()
                counts[rid] += 1
                total += 1
                if full_source_origins.get(line) != rid:
                    raise ValueError("full_native_source_graph_identifier_mismatch")
                if line in source_origins:
                    if rid != source_origins[line]:
                        raise ValueError("metadata_source_line_identifier_mismatch")
                    seen_origins.add(line)
    if seen_origins != set(source_origins) or any(counts[rid] != 1 for rid in assignments):
        raise ValueError("missing_or_duplicate_selected_native_record")
    if total != manifest["archive"]["expected_rows"]:
        raise ValueError("native_archive_row_count_mismatch")
    preflight_total, total = total, 0
    with zipfile.ZipFile(manifest["archive"]["path"]) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) != 1 or members[0].filename != manifest["archive"]["member"]:
            raise ValueError("native_archive_member_mismatch")
        with archive.open(members[0]) as stream:
            header = stream.readline().decode("utf-8-sig").rstrip("\r\n").split("\t")
            if not header or header[0] != "BindingDB Reactant_set_id" or len(header) != len(set(header)) or any(not h for h in header):
                raise ValueError("invalid_native_header")
            for line, binary in enumerate(stream, 2):
                total += 1
                rid = "bindingdb:" + binary.partition(b"\t")[0].rstrip(b"\r\n").decode("utf-8").strip()
                if rid not in expected:
                    skipped += 1
                    continue
                if rid in captured:
                    raise ValueError("duplicate_native_phase_record")
                metadata = indexed[rid]
                source = metadata["source_provenance"]
                positions = {i for i,key in enumerate(header) if key in source["row"] or key.strip().casefold() in components.POLICY_FIELDS}
                tokens = selected_byte_tokens(binary, positions)
                projected = {header[i]:value for i,value in tokens.items()}
                if (any(key not in projected or projected[key] != value for key,value in source["row"].items())
                        or components.policy_declarations(projected) != components.policy_declarations(source["row"])):
                    raise ValueError("native_metadata_or_policy_changed_before_outcome_decode")
                values = binary.decode("utf-8").rstrip("\r\n").split("\t")
                if len(values) > len(header):
                    raise ValueError("surplus_native_cells")
                raw = dict(zip(header, values))
                if len(values) < len(header):
                    n = int(raw[common.CHAIN_COUNT]) if raw.get(common.CHAIN_COUNT, "").isdigit() else 0
                    if (n < 1 or f"UniProt (TrEMBL) Alternative ID(s) of Target Chain {n}" not in raw
                            or any(not re.search(r"Target Chain \d+$", key) for key in header[len(values):])):
                        raise ValueError("truncated_native_declared_chain_or_nonchain_tail")
                if line != source["source_line"] or any(key not in raw or raw[key] != value for key, value in source["row"].items()):
                    raise ValueError("native_metadata_or_origin_changed_after_split")
                if common.target_state_identity(raw) != manifest["scope"]["target_annotation"]:
                    raise ValueError("native_target_annotation_mismatch")
                if common.chemical_identity(raw.get("Ligand SMILES", "")) != metadata["chemical_identity"]:
                    raise ValueError("native_chemical_identity_mismatch")
                captured[rid] = raw
    if set(captured) != expected or any(counts[rid] != 1 for rid in assignments):
        raise ValueError("missing_or_duplicate_selected_native_record")
    if total != manifest["archive"]["expected_rows"]:
        raise ValueError("native_archive_row_count_mismatch")
    return captured, {"archive_rows_scanned": total, "first_id_tokens_decoded": preflight_total + total,
                      "id_preflight_rows_scanned": preflight_total,
                      "full_source_graph_rows_verified": len(full_source_origins),
                      "full_rows_decoded": len(captured), "outcome_rows_skipped_without_decoding": skipped,
                      "phase": phase, "captured_record_ids": sorted(captured)}


def derive(manifest, plan, scope, metadata, selected, context, graph, methods, assays, values):
    assignments = bound.unique_index(plan["assignments"], "record_id")
    records, ledger = [], []
    for row in selected:
        rid = row["record_id"]
        assignment = assignments[rid]
        raw = values.get(rid)
        issues = chemistry_issues(row["chemical_identity"], scope)
        method = methods[rid]
        if method["status"] != "compatible":
            issues.append("assay_method_" + method["status"])
        normalized = observation = None
        if raw is not None:
            native_assays = assays.get(rid, [])
            origins = [{key:source[key] for key in ("source_sha256", "source_member", "source_line")}
                       for assay in native_assays for source in [assay["mapping_source"], *assay["description_records"]]]
            if method["status"] == "compatible" and (
                    sorted(method["assay_keys"]) != sorted(a["entry_assay_id"] for a in native_assays)
                    or sorted(method["source_records"], key=common.json_text) != sorted(origins, key=common.json_text)):
                raise ValueError("compatible_method_native_source_binding_mismatch")
            normalized = common.normalize_record(raw, identity=row["chemical_identity"],
                assays=native_assays,
                origin={k:v for k,v in row["source_provenance"].items() if k != "row"})
            # Derived phase policy must not inherit the legacy helper's default
            # development_pool/non-evaluation markers. Native source rows stay intact.
            normalized.update(schema_version="public_bindingdb_phase_normalized_v1",
                              role=assignment["role"], dataset_split=assignment["role"],
                              evaluation_only=assignment["role"] != "fit", eligible_for_split_assignment=False)
            observation = next(value for value in normalized["observations"] if value["endpoint"] == scope["endpoint"])
            issues.extend(normalized["admission_issues"])
            if observation["status"] != "exact":
                issues.append("requested_endpoint_not_exact")
        records.append({"schema_version": SCHEMA, "record_id": rid, "ligand_id": row["ligand_id"],
            "identity_context_node_id": row["identity_context_node_id"], "component_id": assignment["component_id"],
            "assigned_role": assignment["role"], "assignment": deepcopy(assignment),
            "role": assignment["role"], "dataset_split": assignment["role"], "evaluation_only": assignment["role"] != "fit",
            "identity_metadata_projection": deepcopy(row), "chemical_identity": deepcopy(row["chemical_identity"]),
            "target_annotation": deepcopy(scope["target_annotation"]), "target_annotation_sha256": scope["target_annotation_sha256"],
            "physical_target_state_verified": False, "native_bindingdb_row": deepcopy(raw), "normalized_native": normalized,
            "observation": observation, "endpoint": scope["endpoint"],
            "assays": deepcopy(assays.get(rid)) if raw is not None else None,
            "method_evidence": deepcopy(method),
            "admission_issues": sorted(set(issues)), "eligible_for_point_model": raw is not None and not issues,
            "label_access_status": "retrieved" if raw is not None else "withheld_by_preassigned_role",
            "evidence_kind": "experimental_label", "evidence_basis": "database_curated_reported_experiment",
            "primary_source_status": "not_independently_verified", "source_license": scope["source_license"],
            "potential_energy": None, "force_labels": None, "coordinates": None})
    indexed = bound.unique_index(records, "record_id")
    duplicate_counts = Counter(row["record_id"] for row in metadata)
    for row in metadata:
        record = indexed.get(row["record_id"])
        ledger.append({"record_id": row["record_id"], "identity_context_node_id": row["identity_context_node_id"],
            "source_line": row["source_provenance"]["source_line"], "identity_vertex_retained": True,
            "assigned_role": record["assigned_role"] if record else None,
            "status": "duplicate_record_all_occurrences_excluded" if duplicate_counts[row["record_id"]] > 1 else
                      "not_selected_by_metadata_plan" if record is None else
                      "label_withheld" if record["observation"] is None else
                      "normalized_point_eligible" if record["eligible_for_point_model"] else "excluded_point_model",
            "issues": record["admission_issues"] if record else []})
    updated = deepcopy(context)
    by_node = {item["identity_context_node_id"]:item for item in assignments.values()}
    for node in updated:
        if node["node_id"] in by_node:
            node["policy_declarations"].append({"split": by_node[node["node_id"]]["role"]})
    reserved = components.component_index(updated)
    if any(reserved[item["identity_context_node_id"]]["blocked"] != (item["role"] != "fit") for item in assignments.values()):
        raise ValueError("assigned_component_reservation_conflict")
    return records, ledger, updated


def reproduce(manifest_path, manifest_sha256, phase, frozen_fit=None, frozen_fit_sha256=None):
    loaded = load_metadata(manifest_path, manifest_sha256)
    manifest, plan, scope, metadata, selected, context, graph, methods = loaded
    if phase == "evaluation":
        if not frozen_fit or not frozen_fit_sha256:
            raise ValueError("frozen_predictions_required_before_evaluation_values")
        from tools.product.train_public_bindingdb_staged_selector import validate_frozen
        validate_frozen(frozen_fit, frozen_fit_sha256, manifest_sha256, manifest, plan, selected)
    elif phase != "fit" or frozen_fit is not None or frozen_fit_sha256 is not None:
        raise ValueError("invalid_intake_phase_or_fit_evaluation_reference")
    expected = {item["record_id"] for item in plan["assignments"] if (item["role"] == "fit") == (phase == "fit")}
    assays, assay_access = phase_assays(manifest, expected, {item["record_id"] for item in plan["assignments"]})
    values, access = native_rows(manifest, metadata, selected, plan, phase, context)
    access["assay_metadata_access"] = assay_access
    records, ledger, updated = derive(manifest, plan, scope, metadata, selected, context, graph, methods, assays, values)
    # Recheck all source bytes after streaming/normalization, including skipped
    # outcome bytes; a concurrent source change cannot acquire a valid receipt.
    for name in ("archive", "normalized_metadata", "identity_context", "split_plan", "assay_mapping", "assay_descriptions", "assay_method_ledger"):
        entry = manifest[name]
        common.require_sha(common.file_sha(Path(entry["path"])), entry["sha256"])
    bound.read_bound(manifest_path, manifest_sha256)
    return loaded, records, ledger, updated, access


def stable_summary(manifest_sha256, loaded, records, ledger, access):
    manifest, plan, scope, metadata, selected, context, _, _ = loaded
    return {"manifest_sha256": manifest_sha256, "split_plan_sha256": manifest["split_plan"]["sha256"],
            "implementation_hashes": implementation_hashes(), "requested_target_rows": len(metadata),
            "metadata_selected_rows": len(selected), "identity_context_nodes": len(context),
            "assigned_role_counts": plan["counts"], "labels_retrieved": access["full_rows_decoded"],
            "labels_withheld": len(selected) - access["full_rows_decoded"], "access": access,
            "eligible_role_counts": dict(Counter(r["assigned_role"] for r in records if r["eligible_for_point_model"])),
            "ledger_counts": dict(Counter(r["status"] for r in ledger)),
            "observation_status_counts": dict(Counter(r["observation"]["status"] if r["observation"] else "withheld" for r in records)),
            "exclusion_counts": dict(Counter(issue for r in records for issue in r["admission_issues"])),
            "endpoint": scope["endpoint"], "prediction_quantity": "negative_log10_molar_" + scope["endpoint"],
            "physical_energy": False, "customer_execution": False, "resplit_after_exclusions": False,
            "training_executed": False}


def build(*, manifest_path, manifest_sha256, phase, output_dir, frozen_fit=None, frozen_fit_sha256=None):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementation_hashes()
    loaded, records, ledger, updated, access = reproduce(manifest_path, manifest_sha256, phase, frozen_fit, frozen_fit_sha256)
    bound.read_bound(manifest_path, manifest_sha256)
    if implementation_hashes() != before:
        raise ValueError("implementation_changed_during_intake")
    output.mkdir(parents=True)
    for name, rows in [("records.jsonl", records), ("ledger.jsonl", ledger), ("identity-context.jsonl", updated)]:
        (output / name).write_text("".join(common.json_text(row) + "\n" for row in rows))
    summary = {"schema_version": SCHEMA, "phase": phase, "manifest_path": str(Path(manifest_path).resolve()),
               **stable_summary(manifest_sha256, loaded, records, ledger, access),
               "records_sha256": common.file_sha(output / "records.jsonl"),
               "ledger_sha256": common.file_sha(output / "ledger.jsonl"),
               "identity_context_sha256": common.file_sha(output / "identity-context.jsonl"),
               "frozen_fit": {"path": str(frozen_fit), "sha256": frozen_fit_sha256} if frozen_fit else None,
               "training_executed": False,
               "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        "scope": "offline metadata verification and authorized-phase intake; excludes acquisition/training"}}
    (output / "summary.json").write_text(common.json_text(summary) + "\n")
    return summary


def load_intake(input_dir, summary_sha256, phase):
    folder = Path(input_dir)
    summary = bound.bound_json({"path": str(folder / "summary.json"), "sha256": summary_sha256})
    if summary.get("schema_version") != SCHEMA or summary.get("phase") != phase or summary.get("implementation_hashes") != implementation_hashes():
        raise ValueError("intake_phase_or_implementation_mismatch")
    frozen = summary.get("frozen_fit")
    loaded, rows, ledger, context, access = reproduce(summary["manifest_path"], summary["manifest_sha256"], phase,
                                                     frozen["path"] if frozen else None, frozen["sha256"] if frozen else None)
    for name, expected, key in [("records.jsonl", rows, "records_sha256"), ("ledger.jsonl", ledger, "ledger_sha256"),
                               ("identity-context.jsonl", context, "identity_context_sha256")]:
        if bound.bound_jsonl({"path": str(folder / name), "sha256": summary[key]}) != expected:
            raise ValueError("cached_intake_does_not_match_native_source:" + name)
    for key, value in stable_summary(summary["manifest_sha256"], loaded, rows, ledger, access).items():
        if summary.get(key) != value:
            raise ValueError("cached_summary_does_not_match_native_source:" + key)
    return summary, loaded, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--phase", choices=("fit", "evaluation"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frozen-fit", type=Path)
    parser.add_argument("--frozen-fit-sha256")
    args = parser.parse_args(argv)
    result = build(manifest_path=args.manifest, manifest_sha256=args.manifest_sha256, phase=args.phase,
                   output_dir=args.output_dir, frozen_fit=args.frozen_fit, frozen_fit_sha256=args.frozen_fit_sha256)
    print(json.dumps({k:result[k] for k in ["phase", "requested_target_rows", "metadata_selected_rows", "labels_retrieved", "labels_withheld"]}))


if __name__ == "__main__":
    main()
