"""Label-free identity components shared by public intake and training.

Coverage is the explicitly supplied metadata universe, not an assertion about
every molecule or protected dataset. Rejected rows remain graph vertices.
Optional ChEMBL document and parent molecule source IDs add existing key kinds;
they do not imply chemical-state equivalence or change existing node schemas.
An explicit ChEMBL assay ID uses a v2 node with a distinct source_assay key.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import re
from urllib.parse import unquote

from tools.product.residual_evidence import (
    POLICY_FIELDS, declared_evaluation_only, provenance_records,
)

SCHEMA = "public_assay_identity_context_v1"
SCHEMA_V2 = "public_assay_identity_context_v2"
POLICY = "all_supplied_metadata_components_before_target_endpoint_selection_v1"
RESERVED = {"calibration", "development_test", "calibration_dev"}
NONRESERVED = {"", "fit", "train", "training", "development_pool", "development_source", "unassigned"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def loads(text):
    def strict_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_identity_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite_identity_json")
    return json.loads(text, object_pairs_hook=strict_object, parse_constant=nonfinite)


def _optional_chembl_id(raw, field, error):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(error)
    if value == "":
        return None
    if re.fullmatch(r"CHEMBL[0-9]+", value) is None:
        raise ValueError(error)
    return value


def document_keys(raw):
    doi = raw.get("Article DOI", "") or ""
    pmid = raw.get("PMID", "") or ""
    if not isinstance(doi, str) or not isinstance(pmid, str):
        raise ValueError("invalid_document_identity")
    doi = unquote(doi.strip()).lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
            break
    document = _optional_chembl_id(raw, "ChEMBL Document ID", "invalid_chembl_document_id")
    return ((["doi:"+doi] if doi else []) + (["pmid:"+pmid.strip()] if pmid.strip() else [])
            + (["chembl:document:"+document] if document is not None else []))


def policy_declarations(row):
    """Keep all original policy fields, including flattened joined origins."""
    result = [{str(k): v for k, v in row.items() if str(k).strip().casefold() in POLICY_FIELDS}]
    result.extend({str(k): v for k, v in source["row"].items()
                   if str(k).strip().casefold() in POLICY_FIELDS}
                  for source in provenance_records(row))
    return result


def reservation_status(declarations):
    reserved, unknown = False, False
    if not isinstance(declarations, list):
        raise ValueError("invalid_identity_policy_declarations")
    for row in declarations:
        if not isinstance(row, dict):
            raise ValueError("invalid_identity_policy_declaration")
        for value in row.values():
            if (type(value) not in (str, bool, int, float, type(None)) or
                    (isinstance(value, str) and len(value) > 256) or
                    (type(value) in (int, float) and not math.isfinite(value))):
                raise ValueError("invalid_identity_policy_scalar")
        if declared_evaluation_only(row):
            reserved = True
        for key, value in row.items():
            name = str(key).strip().casefold()
            if name not in POLICY_FIELDS:
                raise ValueError("nonpolicy_field_in_identity_context")
            if value is None:
                continue
            text = str(value).strip().casefold()
            if name == "evaluation_only":
                if text in {"true", "1", "yes", "on"}:
                    reserved = True
                elif text not in {"", "false", "0", "no", "off"}:
                    unknown = True
            elif text in RESERVED:
                reserved = True
            elif text not in NONRESERVED and not declared_evaluation_only({name: value}):
                unknown = True
    return reserved, unknown


def node_from_raw(raw, identity, *, node_id, record_id, ligand_id, origin=None,
                  extra_declarations=(), protected=False):
    tokens = [("document", key) for key in document_keys(raw)]
    assay = _optional_chembl_id(raw, "ChEMBL Assay ID", "invalid_chembl_assay_id")
    if assay is not None:
        tokens.append(("source_assay", "chembl:assay:"+assay))
    if record_id and not record_id.endswith(":"):
        tokens.append(("record", record_id))
    if ligand_id:
        tokens.append(("source_ligand", ligand_id))
    parent = _optional_chembl_id(raw, "ChEMBL Parent Molecule ID", "invalid_chembl_parent_molecule_id")
    if parent is not None:
        tokens.append(("source_ligand", "chembl:molecule:"+parent))
    if identity is not None:
        for field, kind in (("canonical_isomeric_smiles_sha256", "canonical"),
                            ("connectivity_smiles_sha256", "connectivity"),
                            ("scaffold_group", "scaffold")):
            if identity.get(field):
                tokens.append((kind, identity[field]))
    for key in (raw.get("Ligand InChI Key", ""), (identity or {}).get("rdkit_inchikey", "")):
        if key:
            tokens.append(("inchikey_connectivity", key[:14]))
    declarations = policy_declarations(raw) + list(extra_declarations)
    reservation_status(declarations)
    return {"schema_version": SCHEMA_V2 if assay is not None else SCHEMA,
            "node_id": node_id, "record_id": record_id,
            "keys": sorted({(kind, digest(value)) for kind, value in tokens if value}),
            "policy_declarations": declarations, "protected": bool(protected),
            "chemical_identity_available": identity is not None,
            "document_identity_available": bool(document_keys(raw)),
            "source": dict(origin or {})}


def normalized_node(row):
    """Observations, coordinates, predictions and features are never accessed."""
    source = row["source_provenance"]
    origin = {key: source[key] for key in ("source_sha256", "source_member", "source_line") if key in source}
    node_id = row.get("identity_context_node_id") or "normalized:"+row["record_id"]
    extra = policy_declarations(row)
    for assay in row.get("assays", []):
        for item in [assay.get("mapping_source", {}), *assay.get("description_records", [])]:
            extra.extend(policy_declarations(item.get("row", {})))
    return node_from_raw(source["row"], row.get("chemical_identity"), node_id=node_id,
                         record_id=row["record_id"], ligand_id=row.get("ligand_id", ""),
                         origin=origin, extra_declarations=extra)



def is_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_origin(source, *, joined=False):
    allowed = {"source_sha256", "source_member", "source_line"}
    if joined:
        allowed |= {"entry_assay_id", "declarations"}
    if not isinstance(source, dict) or set(source) - allowed:
        raise ValueError("nonmetadata_identity_origin_field")
    for key, value in source.items():
        if key == "declarations":
            reservation_status(value)
        elif key == "source_sha256":
            if not is_sha(value):
                raise ValueError("invalid_identity_origin_hash")
        elif key == "source_line":
            if type(value) is not int or value < 1:
                raise ValueError("invalid_identity_origin_line")
        elif not isinstance(value, str) or not value or len(value) > 512:
            raise ValueError("invalid_identity_origin_string")


def validate_node(node):
    required = {"schema_version", "node_id", "record_id", "keys", "policy_declarations",
                "protected", "chemical_identity_available", "document_identity_available", "source"}
    if not isinstance(node, dict) or not required <= set(node) or set(node) - required - {"joined_policy_sources"}:
        raise ValueError("nonmetadata_or_missing_identity_context_field")
    for key in ("schema_version", "node_id", "record_id"):
        if not isinstance(node[key], str) or not node[key] or len(node[key]) > 256:
            raise ValueError("invalid_identity_context_string")
    if node["schema_version"] not in (SCHEMA, SCHEMA_V2):
        raise ValueError("unsupported_identity_context_schema")
    for key in ("protected", "chemical_identity_available", "document_identity_available"):
        if type(node[key]) is not bool:
            raise ValueError("invalid_identity_context_boolean")
    validate_origin(node["source"])
    reservation_status(node["policy_declarations"])
    markers = node.get("joined_policy_sources", [])
    if not isinstance(markers, list):
        raise ValueError("invalid_joined_identity_origins")
    for marker in markers:
        validate_origin(marker, joined=True)
    kinds = {"document", "record", "source_ligand", "canonical", "connectivity", "scaffold", "inchikey_connectivity"}
    if node["schema_version"] == SCHEMA_V2:
        kinds.add("source_assay")
    if not isinstance(node["keys"], list):
        raise ValueError("invalid_identity_context_keys")
    for key in node["keys"]:
        if (not isinstance(key, (list, tuple)) or len(key) != 2 or
                key[0] not in kinds or not is_sha(key[1])):
            raise ValueError("invalid_identity_context_key")
    if node["schema_version"] == SCHEMA_V2 and not any(key[0] == "source_assay" for key in node["keys"]):
        raise ValueError("missing_assay_identity_context_key")


def node_reservation_status(node):
    declarations = list(node["policy_declarations"])
    declarations.extend(declaration for marker in node.get("joined_policy_sources", [])
                        for declaration in marker.get("declarations", []))
    return reservation_status(declarations)


def node_set_sha(nodes):
    """Order-independent binding of the declared metadata, not just its count."""
    return digest(canonical(sorted(nodes, key=lambda node: node["node_id"])))


def require_source_coverage(context, summary):
    """Bind every TSV occurrence and the separately supplied external node set."""
    component_index(context)
    source = [node for node in context if node["node_id"].startswith("source:")]
    external = [node for node in context if not node["node_id"].startswith("source:")]
    counts = [summary.get("identity_context_source_rows"), summary.get("identity_context_external_rows")]
    if (any(type(value) is not int or value < 0 for value in counts) or
            counts != [len(source), len(external)] or summary.get("all_source_rows") != counts[0]):
        raise ValueError("identity_context_count_mismatch")
    if (node_set_sha(source) != summary.get("identity_context_source_nodes_sha256") or
            node_set_sha(external) != summary.get("identity_context_external_nodes_sha256")):
        raise ValueError("identity_context_node_set_mismatch")
    origins = []
    members = set()
    for node in source:
        origin = node["source"]
        if (set(origin) != {"source_sha256", "source_member", "source_line"} or
                origin["source_sha256"] != summary.get("source_sha256") or
                node["node_id"] != "source:" + digest(canonical(origin))):
            raise ValueError("identity_context_source_origin_mismatch")
        origins.append(origin["source_line"])
        members.add(origin["source_member"])
    if sorted(origins) != list(range(2, len(source) + 2)) or len(members) > 1:
        raise ValueError("identity_context_source_occurrence_gap")
    if any(not node["node_id"].startswith("external:") for node in external):
        raise ValueError("invalid_external_identity_context_node_id")


def component_index(nodes):
    """Reject duplicate node identities; keep distinct occurrences of record IDs."""
    parent = list(range(len(nodes)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen, ids = {}, set()
    for i, node in enumerate(nodes):
        validate_node(node)
        if node.get("schema_version") not in (SCHEMA, SCHEMA_V2):
            raise ValueError("unsupported_identity_context_schema")
        nid = node.get("node_id")
        if not isinstance(nid, str) or not nid or nid in ids:
            raise ValueError("missing_or_duplicate_identity_context_node")
        ids.add(nid)
        if type(node.get("protected")) is not bool:
            raise ValueError("invalid_identity_context_protection")
        reservation_status(node["policy_declarations"])
        for key in node["keys"]:
            if not isinstance(key, (list, tuple)) or len(key) != 2 or not all(isinstance(v, str) and v for v in key):
                raise ValueError("invalid_identity_context_key")
            key = tuple(key)
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = defaultdict(list)
    for i, node in enumerate(nodes):
        groups[find(i)].append(node)
    result = {}
    for members in groups.values():
        ids = sorted(node["node_id"] for node in members)
        reserved = sorted(node["node_id"] for node in members
                          if node["protected"] or node_reservation_status(node)[0])
        unknown = sorted(node["node_id"] for node in members
                         if node_reservation_status(node)[1])
        value = {"component_id": digest(canonical(ids)), "node_count": len(ids),
                 "reserved_nodes": reserved, "unknown_policy_nodes": unknown,
                 "blocked": bool(reserved or unknown)}
        for nid in ids:
            result[nid] = value
    return result


def require_normalized_coverage(rows, context):
    """A cached graph cannot omit or relabel its normalized row projection."""
    index = component_index(context)
    nodes = {node["node_id"]: node for node in context}
    for row in rows:
        expected = normalized_node(row)
        nid = expected["node_id"]
        if nid not in nodes:
            raise ValueError("normalized_row_missing_from_identity_context")
        observed = nodes[nid]
        if (observed["record_id"] != row["record_id"] or
                {tuple(k) for k in expected["keys"]} != {tuple(k) for k in observed["keys"]}):
            raise ValueError("normalized_identity_context_mismatch")
        # Raw/assay reservations may not be lost by a serialized context cache.
        expected_reserved, expected_unknown = node_reservation_status(expected)
        actual_reserved, actual_unknown = node_reservation_status(observed)
        if (expected_reserved and not actual_reserved) or (expected_unknown and not actual_unknown):
            raise ValueError("normalized_identity_context_policy_mismatch")
    return index
