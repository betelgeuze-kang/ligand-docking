"""Fit-only installed v4 receptor source contract helpers.

These functions are extracted from the checkout ChEMBL normalizer. Older
endpoint and training entrypoints are intentionally unavailable here.
"""
from __future__ import annotations
from pathlib import Path
from . import public_assay_components as components
from . import native_v4_chemical_identity as bindingdb
SCHEMA = "public_chembl_assay_development_v1"
SCHEMA_V2 = "public_chembl_assay_development_v2"
SCHEMA_V3 = "public_chembl_native_sqlite_development_v3"
SCHEMA_V4 = "public_chembl_receptor_development_v4"
MANIFEST_SCHEMA = "public_chembl_preassigned_metadata_manifest_v1"
MANIFEST_SCHEMA_V2 = "public_chembl_preassigned_metadata_manifest_v2"
PLAN_SCHEMA = "public_chembl_kinase_ic50_predeclared_split_v1"
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

def endpoint_contract(scope):
    """Only explicitly supported endpoint/subtype pairs select a schema version."""
    endpoint, subtype = scope.get("endpoint"), scope.get("endpoint_subtype")
    source_kind = scope.get("intake_source_kind")
    if source_kind is not None and (not isinstance(source_kind, str) or source_kind not in {"native_chembl_sqlite_release_v1", "native_chembl_receptor_research_v4"}):
        raise ValueError("unsupported_chembl_intake_source_kind")
    if source_kind == "native_chembl_receptor_research_v4":
        if (endpoint, subtype) != ("Ki", "receptor_radioligand_binding_Ki"):
            raise ValueError("unsupported_receptor_research_endpoint")
        version = "v4"
    elif source_kind == "native_chembl_sqlite_release_v1":
        if (endpoint, subtype) != ("IC50", "enzyme_inhibition_IC50"):
            raise ValueError("unsupported_native_chembl_endpoint")
        version = "v3"
    elif (endpoint, subtype) == ("IC50", "enzyme_inhibition_IC50"):
        version = "v1"
    elif (endpoint, subtype) == ("Ki", "enzyme_inhibition_Ki"):
        version = "v2"
    else:
        raise ValueError("unsupported_chembl_development_scope")
    return {
        "endpoint": endpoint, "endpoint_subtype": subtype,
        "prediction_quantity": "negative_log10_molar_" + endpoint,
        "intake_schema": {"v1": SCHEMA, "v2": SCHEMA_V2, "v3": SCHEMA_V3, "v4": SCHEMA_V4}[version],
        "manifest_schema": {"v1": MANIFEST_SCHEMA, "v2": MANIFEST_SCHEMA_V2,
                            "v3": "native_chembl_sqlite_fit_intake_manifest_v1", "v4": "public_chembl_receptor_intake_manifest_v4"}[version],
        "plan_schema": {"v1": PLAN_SCHEMA, "v2": PLAN_SCHEMA_V2,
                        "v3": "native_chembl_ic50_precontent_reservation_v1", "v4": "public_chembl_receptor_preassigned_roles_v4"}[version],
        "model_schema": "public_chembl_cheap_selector_ridge_" + version,
        "frozen_schema": "public_chembl_fit_frozen_before_evaluation_" + version,
        "evaluation_schema": "public_chembl_frozen_selector_evaluation_" + version,
    }


def read_bound(path, expected):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_file():
        raise ValueError("noncanonical_or_missing_native_source_path")
    raw = path.read_bytes()
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


def chemistry_issues(identity, scope):
    chemistry = scope["chemistry_scope"]
    issues = []
    if identity.get("unresolved_stereochemistry"):
        issues.append("unresolved_enhanced_stereochemistry")
    if not chemistry["heavy_atoms_min"] <= identity["heavy_atom_count"] <= chemistry["heavy_atoms_max"]:
        issues.append("chemical_size_outside_scope")
    if (identity["fragment_count"] != chemistry["fragment_count"]
            or set(identity["elements"]) - set(chemistry["elements"])
            or identity["radical_electrons"] != chemistry["radical_electrons"]
            or identity["isotope_atoms"] != chemistry["isotope_atoms"]):
        issues.append("chemical_state_outside_declared_scope")
    return sorted(issues)
