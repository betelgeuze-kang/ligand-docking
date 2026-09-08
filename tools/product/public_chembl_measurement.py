"""Loss-aware ChEMBL measurements and explicit-purpose development admission.

This module never supplies physical energy, force labels, coordinates, or source
approval. Published and standard fields are retained independently. Numeric
normalization does not admit an observation to fitting.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, DecimalException, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import json
import math
import re
from typing import Any

SCHEMA = "public_chembl_measurement_v1"
ADMISSION_SCHEMA = "public_chembl_measurement_admission_v1"
DB_CURATED_SCOPE = "database_curated_reported_experiment_development"
ENDPOINTS = frozenset(("IC50", "Ki", "Kd", "EC50"))
UNIT_NM = {"M": Decimal("1e9"), "mM": Decimal("1e6"), "uM": Decimal("1e3"),
           "µM": Decimal("1e3"), "μM": Decimal("1e3"), "nM": Decimal(1),
           "pM": Decimal("1e-3"), "fM": Decimal("1e-6")}
RELATIONS = {"=": "=", "<": ">", ">": "<", "<=": ">=", ">=": "<=", "~": "~"}
MEASUREMENT_FIELDS = ("type", "value", "units", "relation", "upper_value", "text_value")
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


def strict_loads(text: str | bytes) -> Any:
    """Reject duplicate JSON keys and non-JSON NaN/Infinity, before projection."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key:" + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("nonfinite_json_constant:" + value)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite_json_number:" + value)
        return number

    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite, parse_float=finite_float)


def require_unique_activity_ids(rows: list[dict]) -> None:
    """Fail on every ambiguous activity collection; never keep a last row."""
    if not isinstance(rows, list):
        raise ValueError("activity_collection_not_list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("activity_record_not_object")
        key = row.get("activity_id")
        if type(key) is not int or key <= 0:
            raise ValueError("invalid_activity_id")
        if key in seen:
            raise ValueError("duplicate_activity_id:" + str(key))
        seen.add(key)


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value):
    if _missing(value):
        return None, "missing"
    if type(value) not in (int, float, str):
        return None, "invalid_numeric_type"
    text = str(value).strip()
    try:
        number = Decimal(text)
    except DecimalException:
        return None, "invalid_numeric_or_relation"
    if not number.is_finite():
        return None, "nonfinite_value"
    if not NUMBER.fullmatch(text):
        return None, "invalid_numeric_or_relation"
    return number, None


def _finite_concentration(value):
    if value is None:
        return None
    try:
        number = float(value)
        molar = float(value / Decimal("1e9"))
    except (ValueError, OverflowError, DecimalException):
        return None
    if not math.isfinite(number) or not math.isfinite(molar):
        return None
    if value != 0 and (number == 0 or molar == 0):
        return None
    return number


def _field_projection(activity, prefix):
    return {key: deepcopy(activity[prefix + key]) for key in MEASUREMENT_FIELDS
            if prefix + key in activity}


def _observation(activity, prefix):
    """Return a parsed view; the source projection is never rewritten."""
    source = _field_projection(activity, prefix)
    issues = []
    for name in MEASUREMENT_FIELDS:
        if prefix + name not in activity:
            issues.append("missing_required_capture_field:" + prefix + name)
    kind = source.get("type")
    endpoint, transform = kind, "linear_concentration_to_nM"
    scale, inverse = None, False
    unit = source.get("units")
    if isinstance(kind, str) and kind in {"p" + key for key in ENDPOINTS}:
        endpoint, transform, inverse = kind[1:], "negative_log10_molar_to_nM", True
        if not _missing(unit):
            issues.append("logarithmic_type_has_concentration_unit")
    elif isinstance(kind, str) and kind.startswith("log ") and kind[4:] in ENDPOINTS:
        endpoint, transform = kind[4:], "log10_molar_to_nM"
        if unit != "M":
            issues.append("unresolved_logarithm_reference_unit")
    elif isinstance(kind, str) and kind in ENDPOINTS:
        if _missing(unit):
            issues.append("missing_" + ("standard_units" if prefix else "published_units"))
        elif not isinstance(unit, str) or unit not in UNIT_NM:
            issues.append("unsupported_concentration_unit")
        else:
            scale = UNIT_NM[unit]
    else:
        issues.append("unsupported_measurement_quantity")
    relation = source.get("relation")
    if _missing(relation):
        issues.append("missing_relation")
    elif not isinstance(relation, str) or relation not in RELATIONS:
        issues.append("unsupported_censoring_operator")
    number, error = _number(source.get("value"))
    if error == "missing":
        issues.append("missing_" + ("standard_value" if prefix else "published_value"))
    elif error:
        issues.append(error)
    upper, upper_error = _number(source.get("upper_value"))
    if upper_error not in (None, "missing"):
        issues.append(upper_error)
    if upper is not None and number is not None and upper < number:
        issues.append("invalid_source_range_order")
    text_value = source.get("text_value")
    if not _missing(text_value) and number is not None:
        issues.append("numeric_text_value_conflict")
    lower_nm, upper_nm = None, None
    convertible = not any(issue in issues for issue in (
        "unsupported_measurement_quantity", "unsupported_concentration_unit",
        "logarithmic_type_has_concentration_unit", "unresolved_logarithm_reference_unit",
        "missing_standard_units", "missing_published_units"))
    if number is not None and convertible:
        def convert(value):
            if value is None:
                return None
            if scale is not None:
                return value * scale
            exponent = Decimal(9) - value if inverse else Decimal(9) + value
            if abs(exponent) > 1000:
                raise ValueError("nonrepresentable_concentration")
            return Decimal(10) ** exponent
        try:
            with localcontext() as context:
                context.prec = 50
                lower_nm, upper_nm = convert(number), convert(upper)
                if inverse and upper_nm is not None:
                    lower_nm, upper_nm = upper_nm, lower_nm
                if (_finite_concentration(lower_nm) is None or
                        (upper_nm is not None and _finite_concentration(upper_nm) is None)):
                    raise ValueError("nonrepresentable_concentration")
        except (ValueError, DecimalException, OverflowError):
            issues.append("nonrepresentable_concentration")
            lower_nm, upper_nm = None, None
    if lower_nm is not None and (lower_nm <= 0 or (upper_nm is not None and upper_nm <= 0)):
        issues.append("nonpositive_concentration")
    normalized_relation = (RELATIONS.get(relation) if isinstance(relation, str) else None) if inverse else relation
    return {"source": source, "endpoint": endpoint, "transform": transform,
            "relation": normalized_relation, "value_nm": lower_nm, "upper_value_nm": upper_nm,
            "standard_unit_factor_nm": scale, "issues": issues}


def _consistent(published, standard, standard_scale):
    if published == standard:
        return True, "exact_conversion"
    if published is None or standard is None or published <= 0 or standard <= 0:
        return False, "not_consistent"
    scale = standard_scale or Decimal(1)
    with localcontext() as context:
        context.prec = 50
        original, observed = published / scale, standard / scale
        quantum = Decimal("0.01") if original > 10 else Decimal(10) ** (original.adjusted() - 2)
        try:
            options = {original.quantize(quantum, rounding=mode)
                       for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP)}
        except DecimalException:
            return False, "not_consistent"
    return (observed in options,
            "documented_standard_value_rounding" if observed in options else "not_consistent")


def normalize_measurement(activity: dict) -> dict:
    """Normalize an original ChEMBL activity without erasing source distinctions."""
    if not isinstance(activity, dict):
        raise ValueError("activity_record_not_object")
    published, standard = _observation(activity, ""), _observation(activity, "standard_")
    issues = published["issues"] + standard["issues"]
    if published["endpoint"] != standard["endpoint"]:
        issues.append("published_standard_endpoint_conflict")
    if (published["relation"] is not None and standard["relation"] is not None and
            published["relation"] != standard["relation"]):
        issues.append("published_standard_relation_conflict")
    rounding = None
    if published["value_nm"] is not None and standard["value_nm"] is not None:
        consistent, rounding = _consistent(published["value_nm"], standard["value_nm"],
                                            standard["standard_unit_factor_nm"])
        if not consistent:
            issues.append("published_standard_value_conflict")
    is_range = published["upper_value_nm"] is not None or standard["upper_value_nm"] is not None
    if is_range:
        issues.append("range_not_point_observation")
        if published["upper_value_nm"] is None or standard["upper_value_nm"] is None:
            issues.append("published_standard_range_conflict")
        elif not _consistent(published["upper_value_nm"], standard["upper_value_nm"],
                             standard["standard_unit_factor_nm"])[0]:
            issues.append("published_standard_range_conflict")
    issues = list(dict.fromkeys(issues))
    if (any("conflict" in issue for issue in issues) or
            "logarithmic_type_has_concentration_unit" in issues):
        status = "conflict"
    elif any(issue in issues for issue in ("invalid_numeric_type", "nonfinite_value",
             "invalid_numeric_or_relation", "nonrepresentable_concentration", "invalid_source_range_order")):
        status = "invalid"
    elif any(issue.startswith("unsupported_") or issue == "unresolved_logarithm_reference_unit"
             for issue in issues):
        status = "unsupported"
    elif any(issue.startswith("missing_required_capture_field:") for issue in issues):
        status = "incomplete"
    elif "missing_standard_value" in issues:
        status = "missing"
    elif any(issue.startswith("missing_") for issue in issues):
        status = "incomplete"
    elif "nonpositive_concentration" in issues:
        status = "nonpositive"
    elif is_range:
        status = "range"
    else:
        status = ("exact" if standard["relation"] == "=" else
                  "approximate" if standard["relation"] == "~" else "censored")
    relation = standard["relation"]
    numeric = _finite_concentration(standard["value_nm"])
    p_value = None
    if status in ("exact", "censored", "approximate") and numeric is not None:
        with localcontext() as context:
            context.prec = 50
            p_value = float(Decimal(9) - standard["value_nm"].log10())
    return {"schema_version": SCHEMA, "source_activity": deepcopy(activity),
            "endpoint": standard["endpoint"], "status": status, "value_nm": numeric,
            "upper_value_nm": _finite_concentration(standard["upper_value_nm"]),
            "negative_log10_molar": p_value, "relation": relation,
            "log_relation": RELATIONS.get(relation) if isinstance(relation, str) else None, "measurement_is_exact_for_fit": status == "exact",
            "issues": issues, "published_observation": published["source"],
            "standard_observation": standard["source"],
            "transformation": {"published": published["transform"], "standard": standard["transform"]},
            "rounding_consistency": rounding,
            "source_quality_flags": {key: deepcopy(activity[key]) for key in
                                     ("standard_flag", "potential_duplicate", "data_validity_comment")
                                     if key in activity}}


def _roles(metadata):
    # Share the established policy for missing/unknown/reserved declarations.
    from tools.product.public_assay_components import policy_declarations, reservation_status
    from tools.product.residual_evidence import declared_evaluation_only

    declarations = policy_declarations(metadata)
    raw = metadata.get("raw_metadata", {})
    if not isinstance(raw, dict):
        raise ValueError("invalid_raw_metadata")
    declarations.extend(policy_declarations(raw))
    reserved, unknown = reservation_status(declarations)
    categories = set()
    for declaration in declarations:
        if declared_evaluation_only(declaration):
            categories.add("evaluation_only")
        for key, value in declaration.items():
            if key.strip().casefold() == "evaluation_only" or value is None:
                continue
            normalized = str(value).strip().casefold()
            if normalized in {"fit", "train", "training"}:
                categories.add("fit")
            elif normalized in {"calibration", "development_test", "calibration_dev"}:
                categories.add(normalized)
    return declarations, reserved, unknown, categories


def admission(metadata: dict, purpose: str = "normalization_only") -> dict:
    """Assess one declared purpose without assigning a role or approving training.

    The explicit database-curated development scope permits unverified primary
    experiments and catalogue target annotations, while retaining those limits.
    It cannot be inferred from the absence of a warning or a computed keyword.
    """
    if not isinstance(metadata, dict):
        raise ValueError("admission_metadata_not_object")
    if purpose not in {"normalization_only", "split_assignment", "fit", "evaluation", "calibration", "development_test"}:
        raise ValueError("unsupported_admission_purpose")
    issues = []
    db_scope = metadata.get("evidence_scope") == DB_CURATED_SCOPE
    if metadata.get("evidence_kind") != "experimental_label":
        issues.append("not_experimental_label")
    if db_scope:
        source_id = metadata.get("source_id", metadata.get("src_id"))
        if (type(source_id) is not int or source_id != 1 or
                ("source_id" in metadata and "src_id" in metadata and
                 (type(metadata["src_id"]) is not int or metadata["source_id"] != metadata["src_id"]))):
            issues.append("database_curated_literature_source_unresolved")
        if metadata.get("document_kind") != "research_article":
            issues.append("primary_document_kind_unresolved_or_secondary")
        if metadata.get("citation_identity_status") != "resolved":
            issues.append("citation_identity_unresolved")
        if metadata.get("assay_method_evidence_status") != "curated_description_bound":
            issues.append("curated_assay_method_evidence_missing")
        if (not isinstance(metadata.get("primary_source_status"), str) or
                metadata["primary_source_status"] not in {"not_independently_verified", "verified_original_experiment"}):
            issues.append("primary_source_verification_status_undeclared")
    elif metadata.get("primary_source_status") != "verified_original_experiment":
        issues.append("primary_source_verification_missing")
    if metadata.get("document_kind") == "review":
        if metadata.get("original_experiment_identity_resolved") is not True:
            issues.append("unresolved_original_experiment")
        if metadata.get("graph_rechecked_after_original_link") is not True:
            issues.append("original_source_identity_graph_not_rechecked")
    subtype = metadata.get("endpoint_subtype")
    if (not isinstance(subtype, str) or not subtype.strip() or
            not isinstance(metadata.get("requested_endpoint_subtype"), str) or
            not metadata["requested_endpoint_subtype"].strip()):
        issues.append("endpoint_subtype_unresolved")
    elif subtype != metadata["requested_endpoint_subtype"]:
        issues.append("endpoint_subtype_mismatch")
    target_status = metadata.get("target_state_status")
    supported_target_status = {"recorded_assay_state_only"}
    if db_scope:
        supported_target_status.add("catalogue_annotation_only")
    if not isinstance(target_status, str) or target_status not in supported_target_status:
        issues.append("recorded_assay_state_unresolved")
    if metadata.get("source_license") != "CC-BY-SA-3.0":
        issues.append("source_license_unresolved")
    duplicate = metadata.get("potential_duplicate")
    if type(duplicate) not in (bool, int) or duplicate not in (False, True, 0, 1):
        issues.append("potential_duplicate_status_unknown")
    elif duplicate:
        resolved = (metadata.get("duplicate_citation_identity_status") == "resolved_and_regraphed"
                    if db_scope else metadata.get("original_experiment_identity_resolved") is True)
        if not resolved:
            issues.append("unresolved_potential_duplicate")
    validity = metadata.get("data_validity_comment")
    if validity not in (None, "", "Manually validated"):
        issues.append("reported_data_validity_issue")
    if metadata.get("measurement_status") != "exact":
        issues.append("measurement_not_exact")
    if metadata.get("graph_blocked") is not False and purpose != "normalization_only":
        issues.append("reserved_identity_component" if metadata.get("graph_blocked") is True
                      else "identity_component_status_unknown")
    if metadata.get("source_access_admitted") is False:
        issues.append("source_access_not_admitted")
    declarations, reserved, unknown, categories = _roles(metadata)
    if unknown:
        issues.append("source_role_unknown")
    if len(categories) > 1:
        issues.append("source_role_conflict")
    if purpose == "fit":
        if "assigned_role" in metadata and metadata["assigned_role"] != "fit":
            issues.append("assigned_role_disallows_fit")
        if reserved or (categories and categories != {"fit"}):
            issues.append("source_role_disallows_fit")
        if not categories and metadata.get("assigned_role") != "fit":
            issues.append("fit_assignment_not_declared")
    elif purpose == "split_assignment" and categories:
        issues.append("source_role_already_assigned")
    elif purpose == "evaluation":
        assigned = metadata.get("assigned_role")
        if not isinstance(assigned, str) or assigned not in {"calibration", "development_test"}:
            issues.append("evaluation_assignment_not_declared")
        if categories and (not isinstance(assigned, str) or categories != {assigned}):
            issues.append("source_role_conflict")
    elif purpose in {"calibration", "development_test"}:
        if categories != {purpose} and metadata.get("assigned_role") != purpose:
            issues.append("evaluation_assignment_not_declared")
        if categories and categories != {purpose}:
            issues.append("source_role_conflict")
    return {"schema_version": ADMISSION_SCHEMA, "source_metadata": deepcopy(metadata),
            "purpose": purpose, "eligible_for_declared_purpose": not issues,
            "issues": list(dict.fromkeys(issues)), "source_role_declarations": deepcopy(declarations),
            "must_preserve_source_role_declarations": True, "must_preserve_identity_vertex": True,
            "physical_energy": None, "force_labels": None, "training_admitted": False,
            "evidence_scope": metadata.get("evidence_scope"),
            "primary_source_status": metadata.get("primary_source_status"),
            "target_state_status": target_status, "construct_verified": False,
            "scientific_validation": False, "customer_execution": False}
