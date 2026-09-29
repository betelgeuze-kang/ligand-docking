"""Source-bound receptor Ki research intake, distinct from physical validation.

The v4 route retains the existing normalizer, identity graph and Ridge trainer.
It never assigns roles, infers receptor state, or replaces a censored label with
a point. Native source-37 patent data require a separate primary correspondence
record; literature-only admission remains the default in older versions.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import gzip
from pathlib import Path
import re

from . import public_assay_components as components
from . import native_v4_chemical_identity as common
from . import native_v4_bound as bound
from . import native_v4_measurement as measurement
from . import native_v4_primary as primary

KIND = "native_chembl_receptor_research_v4"
SUBTYPE = "receptor_radioligand_binding_Ki"

_ORIGIN_FIELDS = {"path", "sha256", "format", "pointer"}
_ENTRY_REQUIRED = {
    "activity_id", "node_id", "metadata_origin", "role_origin", "document_origin",
}
_ENTRY_ORIGINS = {
    "metadata_origin", "role_origin", "activity_origin", "method_origin",
    "document_origin", "primary_origin", "bibliography_origin",
    "prepared_state_origin",
}
_PREPARED_STATE_FIELDS = {
    "schema_version", "record_id", "assay_id", "metadata_origin_sha256",
    "method_origin_sha256", "target_annotation_sha256", "target_chembl_id",
    "prepared_input_sha256", "ligand", "receptor_system_sha256",
    "receptor_construct_sha256", "pocket_sha256", "evaluation_sha256",
    "prepared_state_id", "coordinate_frame_id", "parameter_source_id",
    "charge_source_id", "parameter_sources_sha256",
}
_PREPARED_LIGAND_FIELDS = {
    "sdf_sha256", "atom_graph_sha256", "canonical_isomeric_smiles_sha256",
    "formal_charge", "system_sha256",
}
_SCOPE_REQUIRED = {
    "intake_source_kind", "endpoint", "endpoint_subtype",
    "source_database_license", "evidence_scope",
    "physical_target_state_verified", "resplit_after_exclusions",
    "target_annotation", "positive_threshold_negative_log10_molar",
    "top_fraction", "chemistry_scope",
}
_SCOPE_OPTIONAL = {
    "customer_execution", "numeric_annotation_policy", "primary_units_policy",
    "scientific_validation", "source1_bibliography_policy",
    "source_license_reference",
}
_CHEMISTRY_FIELDS = {
    "heavy_atoms_min", "heavy_atoms_max", "fragment_count", "elements",
    "isotope_atoms", "radical_electrons",
}
_METHOD_REQUIRED = {
    "assay_chembl_id", "document_chembl_id", "target_chembl_id",
    "assay_type", "assay_tax_id", "confidence_score", "description",
}
_METHOD_FIELDS = _METHOD_REQUIRED | {
    "aidx", "assay_category", "assay_cell_type", "assay_classifications",
    "assay_group", "assay_organism", "assay_parameters", "assay_strain",
    "assay_subcellular_fraction", "assay_test_type", "assay_tissue",
    "assay_type_description", "bao_format", "bao_label", "cell_chembl_id",
    "confidence_description", "relationship_description", "relationship_type",
    "src_assay_id", "src_id", "tissue_chembl_id", "variant_sequence",
} | set(components.POLICY_FIELDS)


def _source_origin(origin, *, required=True):
    if (type(origin) is not dict or not {"path", "sha256"} <= set(origin)
            or set(origin) - _ORIGIN_FIELDS
            or any(type(value) is not str for value in origin.values())):
        raise ValueError("outcome_or_nonmetadata_field_in_source_origin")
    if required and (not origin["path"] or not origin["sha256"]):
        raise ValueError("invalid_source_origin")


def validate_manifest(manifest):
    if (type(manifest) is not dict or set(manifest) != {
        "schema_version", "scope", "metadata_records", "identity_context",
    } or type(manifest["schema_version"]) is not str):
        raise ValueError("outcome_or_nonmetadata_field_in_receptor_manifest")
    for field in ("scope", "metadata_records", "identity_context"):
        origin = manifest[field]
        if (type(origin) is not dict
                or not {"path", "sha256"} <= set(origin)
                or set(origin) - _ORIGIN_FIELDS
                or any(type(value) is not str for value in origin.values())):
            raise ValueError("outcome_or_nonmetadata_field_in_receptor_manifest")


def validate_scope(scope):
    if (type(scope) is not dict or not _SCOPE_REQUIRED <= set(scope)
            or set(scope) - _SCOPE_REQUIRED - _SCOPE_OPTIONAL):
        raise ValueError("outcome_or_nonmetadata_field_in_receptor_scope")
    chemistry = scope["chemistry_scope"]
    if (type(chemistry) is not dict or set(chemistry) != _CHEMISTRY_FIELDS
            or any(type(chemistry[key]) is not int
                   for key in _CHEMISTRY_FIELDS - {"elements"})
            or type(chemistry["elements"]) is not list
            or any(type(element) is not str for element in chemistry["elements"])):
        raise ValueError("outcome_or_nonmetadata_field_in_receptor_scope")
    strings = _SCOPE_REQUIRED - {
        "physical_target_state_verified", "resplit_after_exclusions",
        "positive_threshold_negative_log10_molar", "top_fraction",
        "chemistry_scope",
    }
    strings |= _SCOPE_OPTIONAL - {"customer_execution", "scientific_validation"}
    if (any(type(scope[key]) is not str for key in strings if key in scope)
            or any(type(scope[key]) is not bool for key in (
                "physical_target_state_verified", "resplit_after_exclusions",
                "customer_execution", "scientific_validation",
            ) if key in scope)
            or any(type(scope[key]) not in (int, float) for key in (
                "positive_threshold_negative_log10_molar", "top_fraction",
            ))):
        raise ValueError("outcome_or_nonmetadata_field_in_receptor_scope")


def validate_entry(entry):
    if (type(entry) is not dict or not _ENTRY_REQUIRED <= set(entry)
            or set(entry) - _ENTRY_REQUIRED - _ENTRY_ORIGINS
            or type(entry["activity_id"]) is not int
            or type(entry["node_id"]) is not str):
        raise ValueError("outcome_or_nonmetadata_field_in_receptor_entry")
    for field in _ENTRY_ORIGINS:
        origin = entry.get(field)
        if origin is None:
            if field in {"metadata_origin", "role_origin", "document_origin"}:
                raise ValueError("missing_receptor_source_origin")
            continue
        _source_origin(origin)
        if field == "prepared_state_origin":
            if set(origin) != {"path", "sha256"}:
                raise ValueError("invalid_prepared_state_origin")
            if Path(origin["path"]).stat().st_size > 1024 * 1024:
                raise ValueError("prepared_state_origin_exceeds_capacity")
            descriptor = bound.bound_json(origin)
            if (type(descriptor) is dict and descriptor.get("schema_version")
                    == "native_v4_candidate_registered_structural_binding_v1"):
                from .installed_native_v4_registered_binding import validate_descriptor

                validate_descriptor(descriptor)
                continue
            if (type(descriptor) is not dict
                    or set(descriptor) != _PREPARED_STATE_FIELDS
                    or descriptor.get("schema_version")
                    != "native_v4_candidate_prepared_structural_binding_v1"
                    or type(descriptor.get("ligand")) is not dict
                    or set(descriptor["ligand"]) != _PREPARED_LIGAND_FIELDS
                    or type(descriptor["ligand"]["formal_charge"]) is not int
                    or any(type(value) is not str or not value.strip()
                           for key, value in descriptor.items()
                           if key not in {"ligand"})
                    or any(type(value) is not str or not value.strip()
                           for key, value in descriptor["ligand"].items()
                           if key != "formal_charge")
                    or any(common.SHA.fullmatch(value) is None
                           for key, value in descriptor.items()
                           if key.endswith("_sha256"))
                    or any(common.SHA.fullmatch(value) is None
                           for key, value in descriptor["ligand"].items()
                           if key.endswith("_sha256"))):
                raise ValueError("outcome_or_nonmetadata_field_in_prepared_state_origin")


def method_projection(source):
    """Keep only the bounded ChEMBL assay metadata shapes used by v4."""
    error = "outcome_or_nonmetadata_field_in_method_origin"
    if type(source) is not dict:
        raise ValueError(error)
    if not source:
        return source
    if (not _METHOD_REQUIRED <= set(source) or set(source) - _METHOD_FIELDS
            or any(type(value) not in (str, int, float, bool, type(None))
                   for key, value in source.items()
                   if key not in {"assay_classifications", "assay_parameters"})
            or any(type(source[key]) is not list or source[key]
                   for key in ("assay_classifications", "assay_parameters")
                   if key in source)):
        raise ValueError(error)
    return source


def bibliography_projection(source):
    error = "outcome_or_nonmetadata_field_in_bibliography_origin"
    if (type(source) is not dict or set(source) - {"uid", "pubtype"}
            or ("uid" in source and type(source["uid"]) is not str)
            or ("pubtype" in source and (
                type(source["pubtype"]) is not list
                or any(type(item) is not str for item in source["pubtype"])
            ))):
        raise ValueError(error)
    return source


def resolve(entry, cache):
    """Hash-bound raw JSON with a strict JSON pointer; no default/last-row join."""
    pointer = entry.get("pointer", "")
    if (
        not isinstance(pointer, str)
        or (pointer and not pointer.startswith("/"))
        or re.search(r"~(?![01])", pointer)
    ):
        raise ValueError("invalid_source_pointer")
    key = (entry["path"], entry["sha256"], entry.get("format", "json"))
    if key[2] not in {"json", "jsonl"}:
        raise ValueError("unsupported_source_format")
    if key not in cache:
        raw = bound.read_bound(key[0], key[1]).decode()
        cache[key] = (
            [measurement.strict_loads(line) for line in raw.splitlines()]
            if key[2] == "jsonl"
            else measurement.strict_loads(raw)
        )
    value = cache[key]
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(value):
                raise ValueError("invalid_source_array_pointer")
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise ValueError("unresolved_source_pointer")
    return deepcopy(value)


def source_policies(*values):
    declarations = []

    def visit(value):
        if isinstance(value, dict):
            declared = {
                k: v
                for k, v in value.items()
                if k.strip().casefold() in components.POLICY_FIELDS
            }
            declarations.append(declared)
            if "assigned_role" in value:
                declarations.append({"role": value["assigned_role"]})
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    for value in values:
        visit(value)
    components.reservation_status(declarations)
    return declarations


def metadata_projection(source):
    """Accept only the known label-free flat and receptor metadata envelopes."""
    error = "outcome_or_nonmetadata_field_in_metadata_origin"
    if type(source) is not dict:
        raise ValueError(error)
    rich = {
        "activity_metadata", "assigned_role", "chemical_identity", "component",
        "connected_previous_nodes", "fit_admitted", "metadata_issues",
        "molecule_json_pointer", "molecule_metadata", "molecule_origin",
        "node_id", "numeric_activity_values_read",
    }
    if "activity_metadata" in source and set(source) == rich:
        chemical_keys = {
            "canonical_isomeric_smiles", "canonical_isomeric_smiles_sha256",
            "canonicalization", "connectivity_smiles_sha256", "elements",
            "formal_charge", "fragment_count", "heavy_atom_count",
            "isotope_atoms", "radical_electrons", "rdkit_inchikey",
            "rdkit_version", "scaffold_group", "scaffold_smiles",
            "stereo_unspecified_count",
        }
        molecule = source["molecule_metadata"]
        if (source["assigned_role"] is not None
                or source["numeric_activity_values_read"] is not False
                or type(source["fit_admitted"]) is not bool
                or type(source["connected_previous_nodes"]) is not int
                or type(source["metadata_issues"]) is not list
                or any(type(issue) is not str for issue in source["metadata_issues"])
                or type(source["node_id"]) is not str
                or type(source["molecule_json_pointer"]) is not str
                or type(source["chemical_identity"]) is not dict
                or set(source["chemical_identity"]) != chemical_keys
                or type(source["component"]) is not dict
                or set(source["component"]) != {
                    "blocked", "component_id", "node_count", "reserved_node_count",
                    "unknown_policy_node_count",
                }
                or type(molecule) is not dict
                or set(molecule) != {"molecule_chembl_id", "molecule_hierarchy"}
                or type(molecule["molecule_hierarchy"]) is not dict
                or set(molecule["molecule_hierarchy"]) != {
                    "active_chembl_id", "molecule_chembl_id", "parent_chembl_id",
                }
                or type(source["molecule_origin"]) is not dict
                or set(source["molecule_origin"]) != {"source_member", "source_sha256"}):
            raise ValueError(error)
        value = source["activity_metadata"]
    else:
        value = source
        for wrapper in ("activity_metadata", "ChEMBL activity metadata"):
            if type(value) is not dict:
                raise ValueError(error)
            if wrapper in value:
                if any(key != wrapper and key.strip().casefold() not in components.POLICY_FIELDS
                       for key in value):
                    raise ValueError(error)
                value = value[wrapper]
    allowed = bound.METADATA_FIELDS | {"units", "standard_units", "_origin"}
    if (type(value) is not dict or not bound.METADATA_FIELDS <= set(value)
            or any(key not in allowed and key.strip().casefold() not in components.POLICY_FIELDS
                   for key in value)
            or ("_origin" in value and (type(value["_origin"]) is not dict
                or set(value["_origin"]) != {"path", "sha256"}))):
        raise ValueError(error)
    return value


def role_declaration(source):
    """Reject outcome fields in a bound, preassigned role record."""
    required = {"record_id", "node_id", "assigned_role"}
    allowed = required | {
        "evaluation_only", "original_policy_declarations", "activity_id",
        "assay_id", "component_id_before_role_append", "endpoint",
        "source37_scientific_admission", "source_document",
    }
    if (type(source) is not dict or not required <= set(source)
            or set(source) - allowed
            or ("evaluation_only" in source and type(source["evaluation_only"]) is not bool)
            or ("activity_id" in source and type(source["activity_id"]) is not int)
            or any(type(source[key]) is not str for key in (
                "assay_id", "component_id_before_role_append", "endpoint", "source_document"
            ) if key in source)
            or ("source37_scientific_admission" in source
                and type(source["source37_scientific_admission"]) is not bool)):
        raise ValueError("outcome_or_nonmetadata_field_in_role_origin")
    if "original_policy_declarations" in source:
        components.reservation_status(source["original_policy_declarations"])
    return source


def document_projection(source):
    """Accept only the known flat or source-bound document metadata schema."""
    error = "outcome_or_nonmetadata_field_in_document_origin"
    rich = {
        "chemical_state_equivalence", "family_equivalence_inferred",
        "json_pointer", "native_document", "node_id", "origin",
        "patent_identity_version", "publication_identity",
    }
    if type(source) is not dict:
        raise ValueError(error)
    if "native_document" in source:
        document = source["native_document"]
        if (set(source) != rich or type(document) is not dict
                or set(document) != {
                    "doc_type", "document_chembl_id", "doi", "patent_id",
                    "pubmed_id", "src_id", "year",
                }
                or type(source["origin"]) is not dict
                or set(source["origin"]) != {"source_member", "source_sha256"}
                or type(source["chemical_state_equivalence"]) is not bool
                or type(source["family_equivalence_inferred"]) is not bool
                or type(source["patent_identity_version"]) is not int):
            raise ValueError(error)
        return document
    allowed = {
        "doc_type", "document_chembl_id", "doi", "journal",
        "patent_id", "pubmed_id", "src_id", "title", "year",
    }
    if not {"doc_type", "document_chembl_id", "src_id"} <= set(source) or set(source) - allowed:
        raise ValueError(error)
    return source


def revalidate_primary(evidence, native, cache):
    """Recompute name/value correspondence from bound HTML and native records.

    This checks only the two declared development table formats. It does not
    verify physical assay state, units in the first patent, or primary accuracy.
    """
    primary._fit_policies(evidence)
    record = resolve(evidence["native_record_origin"], cache)
    if record != evidence["native_record"] or any(
        record.get(k) != native.get(k)
        for k in ("record_id", "src_id", "molecule_chembl_id", "document_chembl_id")
    ):
        raise ValueError("primary_native_record_mismatch")
    origin = evidence["primary_origin"]
    patent = evidence["patent_id"]
    key = (origin["path"], origin["sha256"], "primary_html", patent)
    if key not in cache:
        html = bound.read_bound(origin["path"], origin["sha256"]).decode()
        if patent == primary.PATENT:
            cache[key] = primary.extract_primary(html, patent_id=patent)
        elif patent == "US8569318B2":
            parser = primary._Rows()
            parser.feed(html)
            parser.close()
            if (
                parser.cells is not None
                or parser.cell is not None
                or ["No", "IC50, μM", "Ki, μM"] not in parser.rows
            ):
                raise ValueError("primary_endpoint_or_table_changed")
            cache[key] = parser.rows
        else:
            raise ValueError("unsupported_primary_correspondence_reader")
    tokens = record["compound_name"].split("::")
    conflicts = []
    if patent == primary.PATENT:
        aliases = []
        for token in tokens:
            match = re.fullmatch(r"US9067949, ([0-9]+[a-z]?)", token)
            if not match:
                raise ValueError("unsupported_native_example_alias")
            aliases.append(match[1])
        if len(aliases) != len(set(aliases)):
            raise ValueError("duplicate_native_example_alias")
        table = {row["example"]: row for row in cache[key]}
        rows = [table[alias] for alias in aliases]
        number = primary._number(native.get("value"))
        numeric = (
            len(rows) == 1
            and number is not None
            and primary._number(rows[0]["raw_value"]) == number
        )
    else:
        aliases = []
        for token in tokens:
            if token == native["molecule_chembl_id"]:
                continue
            match = re.fullmatch(r"US8569318, ([0-9]+[.][0-9]+[(][0-9]+[)])", token)
            if not match:
                raise ValueError("unsupported_native_example_alias")
            aliases.append(match[1])
        if len(aliases) != 1:
            raise ValueError("ambiguous_native_example_alias")
        rows = [row for row in cache[key] if len(row) == 3 and row[0] == aliases[0]]
        if len(rows) != 1:
            raise ValueError("ambiguous_primary_example")
        ic50, ki = primary._number(rows[0][1]), primary._number(rows[0][2])
        numeric = ki is not None and ki * Decimal(1000) == primary._number(
            native.get("value")
        )
        if ic50 is None or ki is None or ic50 <= 0 or ki <= 0 or ki >= ic50:
            conflicts.append("same_assay_declared_Cheng_Prusoff_pair_inconsistent")
    unique = (
        len(aliases) == 1
        and numeric
        and native.get("units") == "nM"
        and native.get("relation") == "="
    )
    if (
        evidence["primary_rows"] != rows
        or evidence["unique_native_name_and_numeric_match"] is not bool(unique)
        or evidence["primary_internal_conflicts"] != conflicts
    ):
        raise ValueError("primary_correspondence_cache_mismatch")
    return deepcopy(evidence)


def document_kind(document, bibliography):
    if document.get("doc_type") == "PATENT":
        return "patent"
    if (
        document.get("doc_type") == "PUBLICATION"
        and document.get("pubmed_id") is not None
        and bibliography.get("uid") == str(document["pubmed_id"])
        and isinstance(bibliography.get("pubtype"), list)
        and "Journal Article" in bibliography["pubtype"]
        and "Review" not in bibliography["pubtype"]
    ):
        return "research_article"
    return "unresolved"


def method_supported(method, activity, document):
    if not isinstance(method.get("description"), str):
        return False
    text = method["description"].casefold()
    # Catalogue IDs do not erase an explicit conflicting receptor in the
    # source method. This is a bounded contradiction check, not NLP validation.
    receptor_mentions = {
        number + subtype
        for number, subtype in re.findall(
            r"(?<![a-z0-9])5\s*[-‐‑–—]?\s*ht\s*[-‐‑–—]?\s*([1-7])\s*([a-f])?(?![a-z0-9])",
            text,
        )
    }
    if activity["target_chembl_id"] == "CHEMBL3371" and receptor_mentions - {"6"}:
        return False
    return (
        method.get("assay_chembl_id") == activity["assay_chembl_id"]
        and method.get("document_chembl_id")
        == activity["document_chembl_id"]
        == document.get("document_chembl_id")
        and method.get("target_chembl_id") == activity["target_chembl_id"]
        and method.get("assay_type") == "B"
        and method.get("assay_tax_id") == 9606
        and method.get("confidence_score") == 9
        and (
            "radioligand" in text
            or "displacement" in text
            or "competitive binding" in text
        )
        and not any(word in text for word in ("camp", "qsar", "predicted", "docking"))
    )


def derive(manifest_path, manifest_sha256):
    manifest = bound.bound_json({"path": str(manifest_path), "sha256": manifest_sha256})
    validate_manifest(manifest)
    scope = bound.bound_json(manifest["scope"])
    validate_scope(scope)
    if (
        scope.get("intake_source_kind") != KIND
        or scope.get("endpoint") != "Ki"
        or scope.get("endpoint_subtype") != SUBTYPE
        or scope.get("source_database_license") != "CC-BY-SA-3.0"
        or scope.get("evidence_scope") != measurement.DB_CURATED_SCOPE
        or scope.get("physical_target_state_verified") is not False
        or scope.get("resplit_after_exclusions") is not False
    ):
        raise ValueError("unsupported_receptor_research_scope")
    if (
        manifest.get("schema_version")
        != bound.endpoint_contract(scope)["manifest_schema"]
    ):
        raise ValueError("unsupported_receptor_manifest")
    inputs = bound.bound_jsonl(manifest["metadata_records"])
    for entry in inputs:
        validate_entry(entry)
    indexed = bound.unique_index(inputs, "activity_id")
    context_bytes = bound.read_bound(
        manifest["identity_context"]["path"], manifest["identity_context"]["sha256"]
    )
    context = [
        components.loads(line)
        for line in gzip.decompress(context_bytes).decode().splitlines()
    ]
    graph = components.component_index(context)
    nodes = {r["node_id"]: r for r in context}
    cache, loaded, assignments = {}, {}, []
    # Verify prospective assignments and original identity metadata BEFORE labels.
    for aid, entry in indexed.items():
        metadata_source = resolve(entry["metadata_origin"], cache)
        metadata = metadata_projection(metadata_source)
        if metadata.get("activity_id") != aid:
            raise ValueError("native_metadata_identity_mismatch")
        role = role_declaration(resolve(entry["role_origin"], cache))
        if (
            role.get("record_id") != "chembl:activity:" + str(aid)
            or role.get("assigned_role") not in bound.ROLES
        ):
            raise ValueError("invalid_preassigned_receptor_role")
        nid = entry["node_id"]
        if (
            nid != role.get("node_id")
            or nid not in graph
            or nodes[nid]["record_id"] != role["record_id"]
        ):
            raise ValueError("preassigned_role_node_mismatch")
        declarations = source_policies(metadata_source, role, nodes[nid])
        reserved, unknown = components.reservation_status(declarations)
        if unknown or (
            role["assigned_role"] == "fit" and (reserved or graph[nid]["blocked"])
        ):
            raise ValueError("reserved_or_unknown_fit_component")
        try:
            identity = common.chemical_identity(metadata["canonical_smiles"])
        except (ValueError, TypeError):
            identity = None
        expected = components.node_from_raw(
            {
                "ChEMBL Assay ID": metadata["assay_chembl_id"],
                "ChEMBL Document ID": metadata["document_chembl_id"],
            },
            identity,
            node_id=nid,
            record_id=role["record_id"],
            ligand_id="chembl:molecule:" + metadata["molecule_chembl_id"],
        )
        if not set(map(tuple, expected["keys"])) <= set(map(tuple, nodes[nid]["keys"])):
            raise ValueError("receptor_native_identity_graph_mismatch")
        assignment = {
            "activity_id": aid,
            "record_id": role["record_id"],
            "identity_context_node_id": nid,
            "component_id": graph[nid]["component_id"],
            "role": role["assigned_role"],
            "original": role,
        }
        assignments.append(assignment)
        loaded[aid] = (metadata, identity, assignment, declarations)
    # A capture is explicitly bound even for rejected rows; evaluation values
    # cannot enter this fit-only adapter. Output flags are recomputed, not read.
    output = []
    target = {
        "chembl_target_id": scope["target_annotation"],
        "scope": "catalogue target annotation only",
        "physical_state_verified": False,
        "endpoint_subtype": SUBTYPE,
    }
    for aid, entry in sorted(indexed.items()):
        metadata, identity, assignment, declarations = loaded[aid]
        issues, warnings = [], []
        prediction_issues = []
        if (
            metadata["target_chembl_id"] != scope["target_annotation"]
            or metadata["standard_type"] != "Ki"
        ):
            issues.append("target_or_endpoint_outside_binding_Ki_scope")
            prediction_issues.append("target_or_endpoint_outside_binding_Ki_scope")
        if identity is None:
            issues.append("chemical_identity_unresolved")
            prediction_issues.append("chemical_identity_unresolved")
        else:
            chemical = bound.chemistry_issues(identity, scope)
            if abs(identity["formal_charge"]) > 2:
                chemical.append("chemical_charge_outside_scope")
            issues.extend(chemical)
            prediction_issues.extend(chemical)
        native = None
        if entry.get("activity_origin") is not None:
            if assignment["role"] != "fit":
                raise ValueError("evaluation_outcome_in_fit_input")
            native = resolve(entry["activity_origin"], cache)
            if any(native.get(k) != metadata.get(k) for k in bound.METADATA_FIELDS):
                raise ValueError("native_value_metadata_mismatch")
            if set(native) != bound.ACTIVITY_FIELDS:
                raise ValueError("incomplete_or_extra_native_capture_fields")
        observation = measurement.normalize_measurement(native) if native else None
        method = method_projection(
            resolve(entry["method_origin"], cache) if entry.get("method_origin") else {}
        )
        document = document_projection(resolve(entry["document_origin"], cache))
        if document.get("src_id") != metadata["src_id"]:
            raise ValueError("native_document_source_id_mismatch")
        declarations = source_policies(declarations, method, document)
        supported_method = method_supported(method, metadata, document)
        if not supported_method:
            issues.append("assay_method_not_verified_binding_Ki")
        correspondence = (
            resolve(entry["primary_origin"], cache)
            if entry.get("primary_origin")
            else {}
        )
        if correspondence:
            if (
                correspondence.get("activity_id") != aid
                or native is None
                or correspondence.get("native_activity") != native
            ):
                raise ValueError("primary_correspondence_activity_mismatch")
            correspondence = revalidate_primary(correspondence, native, cache)
        conflicts = correspondence.get("primary_internal_conflicts", [])
        unique = correspondence.get("unique_native_name_and_numeric_match") is True
        if metadata["src_id"] == 37:
            warnings.append(
                "primary_units_and_assayed_microstate_not_independently_verified"
            )
        comment = native.get("activity_comment") if native else None
        if comment not in (None, ""):
            if (
                metadata["src_id"] == 37
                and unique
                and isinstance(comment, str)
                and re.fullmatch(r"[0-9]+", comment)
            ):
                warnings.append(
                    "opaque_numeric_native_annotation_preserved_not_used_as_label_or_ID"
                )
            else:
                issues.append("activity_comment_requires_individual_resolution")
        bibliography = bibliography_projection(
            resolve(entry["bibliography_origin"], cache)
            if entry.get("bibliography_origin") else {}
        )
        profile = {
            "evidence_scope": scope["evidence_scope"],
            "evidence_kind": "experimental_label",
            "source_id": metadata["src_id"],
            "document_kind": document_kind(document, bibliography),
            "citation_identity_status": "resolved"
            if document.get("document_chembl_id") == metadata["document_chembl_id"]
            else "unresolved",
            "assay_method_evidence_status": "curated_description_bound"
            if supported_method
            else "unresolved",
            "primary_source_status": "not_independently_verified",
            "endpoint_subtype": SUBTYPE,
            "requested_endpoint_subtype": SUBTYPE,
            "source_license": scope["source_database_license"],
            "target_state_status": "catalogue_annotation_only",
            "source_policy_declarations": declarations,
            "assigned_role": assignment["role"],
            "graph_blocked": graph[entry["node_id"]]["blocked"],
            "measurement_status": observation["status"] if observation else "withheld",
            "potential_duplicate": native.get("potential_duplicate")
            if native
            else None,
            "data_validity_comment": native.get("data_validity_comment")
            if native
            else None,
            "native_patent_identity_matches": bool(document.get("patent_id"))
            and correspondence.get("patent_id")
            == components.patent_publication(document.get("patent_id")),
            "primary_point_correspondence": "unique_native_name_and_numeric_match"
            if unique
            else "unresolved",
            "primary_internal_conflicts": conflicts,
        }
        admission = (
            measurement.admission(
                profile, "fit", source_profile="chembl_receptor_research_v4"
            )
            if native
            else None
        )
        if admission:
            issues.extend(admission["issues"])
            if (
                not observation["measurement_is_exact_for_fit"]
                or observation["endpoint"] != "Ki"
            ):
                issues.append("measurement_not_supported_exact_point")
            if (
                type(native.get("standard_flag")) not in (bool, int)
                or native["standard_flag"] != 1
            ):
                issues.append("standard_flag_not_confirmed")
        else:
            issues.append("native_label_withheld")
        output.append(
            {
                "schema_version": bound.SCHEMA_V4,
                "activity_id": aid,
                "record_id": assignment["record_id"],
                "assigned_role": assignment["role"],
                "component_id": assignment["component_id"],
                "assignment": assignment,
                "source_policy_declarations": declarations,
                "source_origins": deepcopy(entry),
                "native_metadata": metadata,
                "native_activity": native,
                "native_activity_origin": entry.get("activity_origin"),
                "method_evidence": method,
                "document_evidence": document,
                "primary_evidence": correspondence,
                "observation": observation,
                "admission": admission,
                "admission_issues": sorted(set(issues)),
                "prediction_issues": sorted(set(prediction_issues)),
                "evidence_warnings": sorted(set(warnings)),
                "eligible_for_point_model": native is not None and not issues,
                "chemical_identity": identity,
                "target_annotation": target,
                "target_annotation_sha256": components.digest(
                    components.canonical(target)
                ),
                "assay_id": "chembl:assay:" + metadata["assay_chembl_id"],
                "assayed_microstate_verified": False,
                "coordinates": None,
                "atom_order": None,
                "pose": None,
                "environment": None,
                "physical_energy": None,
                "force_labels": None,
                "source_license": scope["source_database_license"],
                "scientific_validation": False,
            }
        )
    role_sources = sorted(
        {(r["role_origin"]["path"], r["role_origin"]["sha256"]) for r in inputs}
    )
    plan = {
        "seed": 20260910,
        "preassigned_role_sources": [dict(path=p, sha256=h) for p, h in role_sources],
        "assignments": assignments,
        "counts": {
            role: sum(r["role"] == role for r in assignments) for role in bound.ROLES
        },
    }
    return manifest, plan, scope, output


def build(manifest_path, manifest_sha256, output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    manifest, plan, scope, rows = derive(manifest_path, manifest_sha256)
    output_dir.mkdir(parents=True)
    path = output_dir / "records.jsonl"
    path.write_text("".join(common.json_text(r) + "\n" for r in rows))
    summary = {
        "schema_version": bound.SCHEMA_V4,
        "phase": "fit",
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "records_sha256": common.file_sha(path),
        "split_plan_sha256": components.digest(
            components.canonical(plan["preassigned_role_sources"])
        ),
        "intake_scope_sha256": manifest["scope"]["sha256"],
        "identity_context_sha256": manifest["identity_context"]["sha256"],
        "requested_metadata_rows": len(rows),
        "assigned_role_counts": plan["counts"],
        "point_eligible": sum(r["eligible_for_point_model"] for r in rows),
        "exclusions": dict(
            Counter(issue for r in rows for issue in r["admission_issues"])
        ),
    }
    (output_dir / "summary.json").write_text(common.json_text(summary) + "\n")
    return summary


def load_intake(input_dir, summary_sha256, phase):
    if phase != "fit":
        raise ValueError("receptor_v4_evaluation_adapter_not_enabled")
    summary = bound.bound_json(
        {"path": str(Path(input_dir) / "summary.json"), "sha256": summary_sha256}
    )
    manifest, plan, scope, expected = derive(
        summary["manifest_path"], summary["manifest_sha256"]
    )
    saved = bound.bound_jsonl(
        {
            "path": str(Path(input_dir) / "records.jsonl"),
            "sha256": summary["records_sha256"],
        }
    )
    if (
        saved != expected
        or summary.get("schema_version") != bound.SCHEMA_V4
        or summary.get("phase") != "fit"
    ):
        raise ValueError("receptor_intake_cache_does_not_match_native_source")
    fields = {
        "requested_metadata_rows": len(expected),
        "assigned_role_counts": plan["counts"],
        "point_eligible": sum(r["eligible_for_point_model"] for r in expected),
        "split_plan_sha256": components.digest(
            components.canonical(plan["preassigned_role_sources"])
        ),
        "intake_scope_sha256": manifest["scope"]["sha256"],
        "identity_context_sha256": manifest["identity_context"]["sha256"],
        "exclusions": dict(
            Counter(issue for r in expected for issue in r["admission_issues"])
        ),
    }
    if any(summary.get(k) != v for k, v in fields.items()):
        raise ValueError("receptor_intake_summary_does_not_match_source")
    return summary, plan, scope, expected
