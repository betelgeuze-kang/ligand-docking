"""Offline identity audit of declared assay-row/PDB edges, never a label join.

``build_identity_links(records=..., edges=..., split_assignments=None)`` accepts
local ``{path, sha256}`` bindings. Each edge has record_id, pdb_id, entry,
polymers, nonpolymers and components; the latter three are lists of bindings to
RCSB core JSON. Missing metadata is represented by None/empty lists. Components
cover the original row's Ligand HET IDs, not an inferred binding-site search.
Optional split JSON is {records_sha256, assignments: [{record_id, split, ...}]}.
All outputs are identity links only: no assay numeric labels or coordinates are
projected, and no structural feature, training or scientific approval is issued.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from tools.product.public_assay_dataset import (
    CHAIN_COUNT, LICENSES, SCHEMA as ASSAY_SCHEMA, SHA, chemical_identity, digest, file_sha,
    json_text, require_sha, target_accessions, target_schema_rejection, target_state_identity,
)
from tools.product.residual_evidence import POLICY_FIELDS, declared_evaluation_only, provenance_records

SCHEMA = "public_assay_structure_identity_links_v1"
_EDGE_FIELDS = {"record_id", "pdb_id", "entry", "polymers", "nonpolymers", "components"}
_IDENTITY_KEYS = ("canonical_isomeric_smiles", "canonical_isomeric_smiles_sha256",
                  "connectivity_smiles_sha256", "formal_charge", "rdkit_version",
                  "stereo_unspecified_count")


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _json(text):
    def nonfinite(_):
        raise ValueError("nonfinite_json_value")
    return json.loads(text, object_pairs_hook=_strict_object, parse_constant=nonfinite)


def _binding_shape(ref):
    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str) or not ref["path"]
            or not isinstance(ref["sha256"], str) or not SHA.fullmatch(ref["sha256"])):
        raise ValueError("invalid_local_source_binding")


def _binding(ref):
    _binding_shape(ref)
    path = Path(ref["path"])
    if not path.is_absolute() or not path.is_file():
        raise ValueError("source_requires_absolute_regular_file")
    return path


class _Sources:
    def __init__(self):
        self.bound = {}
        self.documents = {}

    def verify(self, ref):
        path = _binding(ref)
        require_sha(file_sha(path), ref["sha256"])
        key = str(path)
        identity = (str(path.resolve()), ref["sha256"])
        if key in self.bound and self.bound[key] != identity:
            raise ValueError("conflicting_source_hash_bindings")
        self.bound[key] = identity
        return path

    def document(self, ref):
        path = self.verify(ref)
        key = (str(path.resolve()), ref["sha256"])
        if key not in self.documents:
            raw = path.read_bytes()
            require_sha(digest(raw), ref["sha256"])
            value = _json(raw)
            if not isinstance(value, dict):
                raise ValueError("metadata_must_be_json_object")
            self.documents[key] = value
        return self.documents[key]

    def postflight(self):
        for name, (resolved, expected) in self.bound.items():
            path = Path(name)
            if str(path.resolve()) != resolved:
                raise ValueError("source_path_resolution_changed")
            require_sha(file_sha(path), expected)


def _strings(value, label):
    if (not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value)
            or len(set(value)) != len(value)):
        raise ValueError("invalid_" + label)
    return value


def _ids(value):
    if not isinstance(value, str):
        raise ValueError("invalid_source_annotation")
    return sorted(set(part.upper() for part in re.split(r"[;,\s]+", value.strip()) if part))


def _declarations(row):
    result = {}
    for key, value in row.items():
        if str(key).strip().casefold() in POLICY_FIELDS:
            if value is not None and not isinstance(value, (str, bool)):
                raise ValueError("invalid_declaration_value_type")
            result[key] = value
    return result


def _optional_text(value):
    if value is not None and not isinstance(value, str):
        raise ValueError("invalid_source_text_metadata")
    return value


def _source_projection(row, line, split):
    source = row.get("source_provenance")
    if not isinstance(source, dict) or not isinstance(source.get("row"), dict):
        raise ValueError("missing_original_source_provenance")
    raw = source["row"]
    if (row.get("record_id") != "bindingdb:" + str(raw.get("BindingDB Reactant_set_id", ""))
            or row.get("ligand_id") != "bindingdb:" + str(raw.get("BindingDB MonomerID", ""))):
        raise ValueError("normalized_record_or_ligand_identity_mismatch")
    state = target_state_identity(raw)
    if row.get("target_state") != state or row.get("target_state_sha256") != digest(json_text(state)):
        raise ValueError("normalized_target_state_mismatch")
    if source.get("row_sha256") != digest(json_text(raw)):
        raise ValueError("source_row_sha256_mismatch")
    original_sha = source.get("source_sha256")
    if not isinstance(original_sha, str) or not SHA.fullmatch(original_sha):
        raise ValueError("missing_original_source_sha256")
    if type(source.get("source_line")) is not int or source["source_line"] < 1:
        raise ValueError("invalid_original_source_line")
    issues = row.get("admission_issues")
    if not isinstance(issues, list) or any(not isinstance(issue, str) for issue in issues):
        raise ValueError("invalid_intake_admission_issues")
    if type(row.get("eligible_for_split_assignment")) is not bool:
        raise ValueError("invalid_intake_eligibility_type")
    declarations = [{"origin": "normalized_record", "values": _declarations(row)},
                    {"origin": "original_source_row", "values": _declarations(raw)}]
    originals = [row, raw]
    for assay in row.get("assays", []):
        for item in [assay.get("mapping_source", {}), *assay.get("description_records", [])]:
            original = item.get("row", {})
            originals.append(original)
            declarations.append({"origin": "assay_source", "values": _declarations(original),
                                 "source_sha256": _optional_text(item.get("source_sha256"))})
    if split is not None:
        originals.append(split)
        declarations.append({"origin": "external_split_assignment", "values": _declarations(split)})
    for original in originals:
        for record in provenance_records(original):
            declarations.append({"origin": "flattened_original_provenance", "values": _declarations(record["row"]),
                                 "source_sha256": record["source_sha256"]})
    projection = {
        "normalized_line": line, "original_source_sha256": original_sha,
        "original_row_sha256": source["row_sha256"],
        "original_source_line": source.get("source_line"),
        "original_source_member": _optional_text(source.get("source_member")),
        "original_source_bytes_reverified": False,
        "source_license": _optional_text(row.get("source_license")),
        "ligand_id": row.get("ligand_id"), "target_state_sha256": row.get("target_state_sha256"),
        "declared_pdb_ids": _ids(raw.get("PDB ID(s) for Ligand-Target Complex", "")),
        "declared_ccd_ids": _ids(raw.get("Ligand HET ID in PDB", "")),
        "declarations": declarations,
        "evaluation_only_declared": any(declared_evaluation_only(original) for original in originals),
        "external_split": None if split is None else {
            **{key: _optional_text(split[key]) for key in ("record_id", "group", "group_id") if key in split},
            **_declarations(split)},
        "external_split_status": "unassigned" if split is None else "declared",
        "intake_eligible_for_split_assignment": row.get("eligible_for_split_assignment"),
        "intake_admission_issues": row.get("admission_issues"),
    }
    return raw, projection


def _target(pdb, entry, documents, accessions):
    expected = _strings(entry.get("polymer_entity_ids"), "entry_polymer_ids")
    found, records = set(), []
    for doc in documents:
        ids = doc.get("rcsb_polymer_entity_container_identifiers", {})
        entity = ids.get("entity_id")
        if ids.get("entry_id") != pdb or entity not in expected or entity in found:
            raise ValueError("polymer_entry_or_entity_mismatch")
        if doc.get("rcsb_id") != pdb + "_" + entity:
            raise ValueError("polymer_rcsb_id_mismatch")
        if ids.get("rcsb_id", doc["rcsb_id"]) != doc["rcsb_id"]:
            raise ValueError("polymer_container_rcsb_id_mismatch")
        found.add(entity)
        references = []
        if ids.get("uniprot_ids") is not None:
            references.append(set(_strings(ids["uniprot_ids"], "polymer_uniprot_ids")))
        for key, name_key, accession_key in (
            ("reference_sequence_identifiers", "database_name", "database_accession"),
        ):
            if ids.get(key):
                references.append({v[accession_key] for v in ids[key] if v.get(name_key) == "UniProt"})
        if doc.get("rcsb_polymer_entity_align"):
            references.append({v["reference_database_accession"] for v in doc["rcsb_polymer_entity_align"]
                               if v.get("reference_database_name") == "UniProt"})
        references = [value for value in references if value]
        if any(value != references[0] for value in references[1:]):
            raise ValueError("conflicting_polymer_uniprot_annotations")
        values = sorted(references[0]) if references else []
        records.append({"entity_id": entity, "uniprot_ids": values})
    if found != set(expected) or not expected:
        return {"status": "unknown", "reason": "polymer_metadata_incomplete", "entities": records}
    matches = [r["entity_id"] for r in records if set(r["uniprot_ids"]) == set(accessions)]
    ambiguous = any(set(r["uniprot_ids"]) & set(accessions) and len(r["uniprot_ids"]) != 1 for r in records)
    if ambiguous:
        status, reason = "unknown", "ambiguous_target_polymer_mapping"
    elif matches:
        status, reason = "matched", "exact_uniprot_accession"
    elif any(not r["uniprot_ids"] for r in records):
        status, reason = "unknown", "polymer_uniprot_mapping_missing"
    else:
        status, reason = "rejected", "target_uniprot_mismatch"
    return {"status": status, "reason": reason, "source_uniprot_ids": accessions,
            "matching_entity_ids": matches, "entities": records}


def _ligand(pdb, entry, nonpolymers, components, candidate_ids, identity):
    expected = _strings(entry.get("non_polymer_entity_ids"), "entry_nonpolymer_ids")
    found, membership = set(), []
    for doc in nonpolymers:
        ids = doc.get("rcsb_nonpolymer_entity_container_identifiers", {})
        entity = ids.get("entity_id")
        if ids.get("entry_id") != pdb or entity not in expected or entity in found:
            raise ValueError("nonpolymer_entry_or_entity_mismatch")
        if doc.get("rcsb_id") != pdb + "_" + entity:
            raise ValueError("nonpolymer_rcsb_id_mismatch")
        if ids.get("rcsb_id", doc["rcsb_id"]) != doc["rcsb_id"]:
            raise ValueError("nonpolymer_container_rcsb_id_mismatch")
        comp = ids.get("nonpolymer_comp_id")
        if (not isinstance(comp, str) or not comp or
                doc.get("pdbx_entity_nonpoly", {}).get("entity_id") != entity or
                doc.get("pdbx_entity_nonpoly", {}).get("comp_id") != comp):
            raise ValueError("nonpolymer_component_identity_mismatch")
        found.add(entity)
        membership.append({"entity_id": entity, "ccd_id": comp})
    if found != set(expected):
        return {"status": "unknown", "reason": "nonpolymer_membership_incomplete", "membership": membership}
    if not candidate_ids:
        return {"status": "unknown", "reason": "source_ccd_annotation_missing", "membership": membership}
    by_id = {}
    for doc in components:
        comp = doc.get("chem_comp", {}).get("id")
        if comp not in candidate_ids or comp in by_id or doc.get("rcsb_id") != comp:
            raise ValueError("ccd_identity_or_duplicate_mismatch")
        descriptors = doc.get("rcsb_chem_comp_descriptor", {})
        if descriptors.get("comp_id") != comp:
            raise ValueError("ccd_descriptor_identity_mismatch")
        by_id[comp] = descriptors.get("SMILES_stereo")
    if set(by_id) != set(candidate_ids):
        return {"status": "unknown", "reason": "ccd_metadata_incomplete", "membership": membership}
    comparisons, exact = [], []
    bound = {row["ccd_id"] for row in membership}
    for comp, smiles in sorted(by_id.items()):
        if not isinstance(smiles, str) or not smiles.strip():
            return {"status": "unknown", "reason": "ccd_isomeric_descriptor_missing", "membership": membership}
        other = chemical_identity(smiles)
        equal = other["canonical_isomeric_smiles_sha256"] == identity["canonical_isomeric_smiles_sha256"]
        comparisons.append({"ccd_id": comp, "present_in_entry": comp in bound,
                            "exact_isomeric_chemistry_match": equal,
                            "identity": {key: other[key] for key in _IDENTITY_KEYS}})
        if equal and comp in bound:
            exact.append(comp)
    if len(exact) > 1:
        status, reason = "unknown", "ambiguous_multiple_exact_ccd_matches"
    elif len(exact) == 1:
        status, reason = "matched", "exact_isomeric_ccd_and_entry_membership"
    elif not (set(candidate_ids) & bound):
        status, reason = "rejected", "declared_ccd_absent_from_entry"
    else:
        status, reason = "rejected", "ccd_isomeric_chemistry_mismatch"
    return {"status": status, "reason": reason, "matching_ccd_ids": exact,
            "comparisons": comparisons, "membership": membership}


def build_identity_links(*, records: dict, edges: list[dict], split_assignments: dict | None = None) -> dict:
    """Audit every requested edge; source/hash failure never becomes a match."""
    if not isinstance(edges, list) or not edges:
        raise ValueError("nonempty_edge_list_required")
    for edge in edges:
        if (not isinstance(edge, dict) or set(edge) != _EDGE_FIELDS
                or not isinstance(edge["record_id"], str) or not edge["record_id"]
                or not isinstance(edge["pdb_id"], str) or not re.fullmatch(r"[0-9A-Z]{4}", edge["pdb_id"])
                or any(not isinstance(edge[key], list) for key in ("polymers", "nonpolymers", "components"))):
            raise ValueError("invalid_edge_request")
        if edge["entry"] is not None:
            _binding_shape(edge["entry"])
        for key in ("polymers", "nonpolymers", "components"):
            for ref in edge[key]:
                _binding_shape(ref)
    sources = _Sources()
    path = sources.verify(records)
    requested = {edge["record_id"] for edge in edges}
    selected, counts = {}, Counter()
    with path.open(encoding="utf-8") as stream:
        for line, text in enumerate(stream, 1):
            row = _json(text)
            if not isinstance(row, dict) or not isinstance(row.get("record_id"), str):
                raise ValueError("invalid_normalized_record")
            rid = row["record_id"]
            if rid in requested:
                counts[rid] += 1
                selected[rid] = (row, line)
    assignments = {}
    if split_assignments is not None:
        split = sources.document(split_assignments)
        if set(split) != {"records_sha256", "assignments"} or split["records_sha256"] != records["sha256"]:
            raise ValueError("split_records_source_mismatch")
        if not isinstance(split["assignments"], list):
            raise ValueError("invalid_split_assignments")
        for item in split["assignments"]:
            if not isinstance(item, dict) or not isinstance(item.get("record_id"), str) or not item["record_id"]:
                raise ValueError("invalid_split_assignment")
            if item["record_id"] in assignments:
                raise ValueError("duplicate_split_record_id")
            assignments[item["record_id"]] = item
    duplicates = Counter((edge["record_id"], edge["pdb_id"]) for edge in edges)
    results = []
    for edge in edges:
        rid, pdb = edge["record_id"], edge["pdb_id"]
        result = {"record_id": rid, "pdb_id": pdb, "status": "unknown", "reason": "",
                  "target": {"status": "not_evaluated"}, "ligand": {"status": "not_evaluated"},
                  "metadata_sources": {k: edge[k] for k in ("entry", "polymers", "nonpolymers", "components")}}
        results.append(result)
        if counts[rid] != 1 or duplicates[(rid, pdb)] != 1:
            result.update(status="rejected", reason="duplicate_or_missing_source_or_edge")
            continue
        try:
            row, line = selected[rid]
            raw, projection = _source_projection(row, line, assignments.get(rid))
            result["source"] = projection
            if projection["evaluation_only_declared"]:
                result.update(status="excluded", reason="evaluation_only_source")
                continue
            if (row.get("schema_version") != ASSAY_SCHEMA or row.get("evidence_kind") != "experimental_label"
                    or row.get("source_license") != LICENSES.get(row.get("curation_source"))
                    or row.get("source_license") is None or row.get("eligible_for_split_assignment") is not True
                    or row.get("admission_issues") != []):
                result.update(status="rejected", reason="source_intake_contract_not_admitted")
                continue
            if pdb not in projection["declared_pdb_ids"]:
                result.update(status="rejected", reason="pdb_edge_not_declared_by_source")
                continue
            if target_schema_rejection(raw) or raw.get(CHAIN_COUNT) != "1" or len(target_accessions(raw)) != 1:
                result.update(status="unknown", reason="source_target_mapping_missing_or_ambiguous")
                continue
            accessions = sorted(target_accessions(raw))
            if row.get("target_accessions") != accessions:
                raise ValueError("normalized_target_accession_mismatch")
            identity = chemical_identity(raw.get("Ligand SMILES", ""))
            if row.get("chemical_identity") != identity:
                raise ValueError("normalized_chemical_identity_mismatch")
            result["source"]["chemical_identity"] = {key: identity[key] for key in _IDENTITY_KEYS}
            if edge["entry"] is None:
                result.update(reason="entry_metadata_missing")
                continue
            entry_doc = sources.document(edge["entry"])
            entry = entry_doc.get("rcsb_entry_container_identifiers", {})
            if entry.get("entry_id") != pdb or entry_doc.get("rcsb_id") != pdb:
                raise ValueError("entry_identity_mismatch")
            result["target"] = _target(pdb, entry, [sources.document(r) for r in edge["polymers"]], accessions)
            result["ligand"] = _ligand(pdb, entry, [sources.document(r) for r in edge["nonpolymers"]],
                                       [sources.document(r) for r in edge["components"]], projection["declared_ccd_ids"], identity)
            axes = [result["target"], result["ligand"]]
            if all(axis["status"] == "matched" for axis in axes):
                result.update(status="identity_link_only", reason="target_and_declared_ccd_identity_linked")
            elif any(axis["status"] == "rejected" for axis in axes):
                result.update(status="rejected", reason=";".join(axis["reason"] for axis in axes if axis["status"] != "matched"))
            else:
                result.update(reason=";".join(axis["reason"] for axis in axes if axis["status"] != "matched"))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            result.update(status="failed", reason=str(exc))
    sources.postflight()
    return {"schema_version": SCHEMA, "records_source": dict(records),
            "split_assignments_source": split_assignments, "requested_edges": len(edges),
            "requested_source_rows": len(requested), "status_counts": dict(Counter(r["status"] for r in results)),
            "edges": results, "scope": "declared_annotation_identity_link_only_not_binding_site_or_assay_equivalence",
            "numeric_assay_labels_projected": False, "training_admitted": False,
            "assay_construct_match_verified": False, "coordinates_validated": False,
            "charges_or_forcefield_parameters_validated": False, "scientifically_validated": False}
