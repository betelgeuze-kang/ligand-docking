"""Fresh synthetic boundaries; no public measured outcomes or model fitting."""
from copy import deepcopy
import json
import pytest
from tools.product.public_chembl_measurement import (
    DB_CURATED_SCOPE, admission, normalize_measurement, require_unique_activity_ids, strict_loads,
)

BASE = {"activity_id": 987654321, "type": "IC50", "value": "100", "units": "nM",
        "relation": "=", "upper_value": None, "text_value": None,
        "standard_type": "IC50", "standard_value": "100", "standard_units": "nM",
        "standard_relation": "=", "standard_upper_value": None, "standard_text_value": None}
PROFILE = {"evidence_scope": DB_CURATED_SCOPE, "evidence_kind": "experimental_label",
           "primary_source_status": "not_independently_verified", "source_id": 1,
           "document_kind": "research_article", "citation_identity_status": "resolved",
           "assay_method_evidence_status": "curated_description_bound",
           "endpoint_subtype": "reported_kinase_inhibition_IC50",
           "requested_endpoint_subtype": "reported_kinase_inhibition_IC50",
           "target_state_status": "catalogue_annotation_only", "source_license": "CC-BY-SA-3.0",
           "raw_metadata": {"role": "unassigned", "dataset_split": "development_pool"},
           "graph_blocked": False, "measurement_status": "exact", "potential_duplicate": 0,
           "data_validity_comment": None, "assigned_role": "fit",
           "assay_conditions": {"ATP_molar": None, "pH": None, "temperature_K": None}}


def test_explicit_curated_scope_preserves_primary_and_construct_uncertainty():
    source = deepcopy(PROFILE)
    out = admission(source, "fit")
    assert out["eligible_for_declared_purpose"] is True
    assert out["primary_source_status"] == "not_independently_verified"
    assert out["target_state_status"] == "catalogue_annotation_only"
    assert out["construct_verified"] is False
    assert out["scientific_validation"] is False
    assert out["training_admitted"] is False
    assert source == PROFILE == out["source_metadata"]
    assert out["source_metadata"]["assay_conditions"]["ATP_molar"] is None


@pytest.mark.parametrize("field,value", [
    ("evidence_scope", None), ("source_id", None), ("source_id", True), ("source_id", 37),
    ("document_kind", "review"), ("document_kind", None),
    ("citation_identity_status", None), ("assay_method_evidence_status", None),
    ("primary_source_status", None), ("evidence_kind", "external_computed_reference"),
    ("endpoint_subtype", "peptide_displacement_FP_IC50"), ("endpoint_subtype", None),
    ("target_state_status", "unknown"), ("potential_duplicate", None),
    ("potential_duplicate", 1), ("graph_blocked", True), ("graph_blocked", None),
    ("measurement_status", "censored"), ("data_validity_comment", "Author confirmed error"),
    ("source_license", None), ("assigned_role", None),
])
def test_curated_scope_has_explicit_boundaries(field, value):
    metadata = deepcopy(PROFILE)
    metadata[field] = value
    assert admission(metadata, "fit")["eligible_for_declared_purpose"] is False


def test_source_id_alias_conflict_is_rejected():
    metadata = deepcopy(PROFILE)
    metadata["src_id"] = 37
    assert "database_curated_literature_source_unresolved" in admission(metadata, "fit")["issues"]


@pytest.mark.parametrize("original,assigned,purpose,allowed", [
    ("calibration", "calibration", "evaluation", True),
    ("development_test", "development_test", "evaluation", True),
    ("unassigned", "calibration", "evaluation", True),
    ("fit", "calibration", "evaluation", False),
    ("development_test", "calibration", "evaluation", False),
    ("calibration", "fit", "fit", False),
    ("development_test", "fit", "fit", False),
    ("fit", "fit", "fit", True),
    ("fit", "fit", "split_assignment", False),
    ("calibration", "fit", "normalization_only", True),
])
def test_original_roles_and_explicit_purpose_are_distinct(original, assigned, purpose, allowed):
    metadata = deepcopy(PROFILE)
    metadata["raw_metadata"]["role"] = original
    metadata["assigned_role"] = assigned
    out = admission(metadata, purpose)
    assert out["eligible_for_declared_purpose"] is allowed
    assert out["source_metadata"]["raw_metadata"]["role"] == original
    assert out["training_admitted"] is False


@pytest.mark.parametrize("payload", [
    '{"value": 1, "value": 2}', '{"outer":{"role":"fit","role":"calibration"}}',
    '{"value": NaN}', '{"value": Infinity}', '{"value": -Infinity}',
    '{"value": 1e9999}', '{"value": -1e9999}',
])
def test_strict_json_rejects_ambiguous_or_nonfinite_input(payload):
    with pytest.raises(ValueError):
        strict_loads(payload)


def test_strict_json_preserves_null_zero_boolean_and_missing():
    raw = strict_loads('{"value":0,"upper_value":null,"evaluation_only":false}')
    assert type(raw["value"]) is int and raw["value"] == 0
    assert raw["upper_value"] is None and raw["evaluation_only"] is False
    assert "standard_value" not in raw


@pytest.mark.parametrize("rows", [
    [{"activity_id": 1}, {"activity_id": 1}], [{"activity_id": True}],
    [{"activity_id": None}], [{"activity_id": "1"}], [{"activity_id": 1.0}],
    [{"activity_id": -1}], [{"activity_id": 0}], [None],
])
def test_ambiguous_activity_identity_fails(rows):
    with pytest.raises(ValueError):
        require_unique_activity_ids(rows)


def test_distinct_activity_ids_keep_repeated_compound_record_ids():
    rows = [{"activity_id": 1, "record_id": 23}, {"activity_id": 2, "record_id": 23}]
    original = deepcopy(rows)
    require_unique_activity_ids(rows)
    assert rows == original


@pytest.mark.parametrize("key,value", [
    ("type", {}), ("type", []), ("relation", {}), ("relation", []),
    ("units", {}), ("value", {}), ("value", []), ("value", True),
])
def test_invalid_field_types_are_not_coerced_to_measurement(key, value):
    row = deepcopy(BASE)
    row[key] = value
    out = normalize_measurement(row)
    assert out["measurement_is_exact_for_fit"] is False
    assert out["negative_log10_molar"] is None
    assert out["source_activity"][key] == value


def test_repairing_one_frozen_reference_default_does_not_change_source_value():
    row = deepcopy(BASE)
    row.update(value="1.234", standard_value="1234")
    out = normalize_measurement(row)
    assert out["status"] == "conflict"
    assert out["value_nm"] == 1234
    assert out["negative_log10_molar"] is None
    assert "published_standard_value_conflict" in out["issues"]


def test_negative_log_range_reverses_bounds_without_creating_point_label():
    row = deepcopy(BASE)
    row.update(type="pIC50", value="6", upper_value="7", units=None,
               standard_value="100", standard_upper_value="1000")
    out = normalize_measurement(row)
    assert out["status"] == "range"
    assert out["value_nm"] == 100
    assert out["upper_value_nm"] == 1000
    assert out["negative_log10_molar"] is None
    assert out["source_activity"] == row


def test_log_molar_unit_is_explicit():
    row = deepcopy(BASE)
    row.update(type="log IC50", value="-7", units="M")
    out = normalize_measurement(row)
    assert out["status"] == "exact"
    assert out["negative_log10_molar"] == 7
    row["units"] = None
    assert normalize_measurement(row)["status"] == "unsupported"


def test_returned_source_copy_cannot_mutate_original():
    row = deepcopy(BASE)
    row["extra"] = {"role": "calibration", "measured_zero": 0}
    out = normalize_measurement(row)
    out["source_activity"]["extra"]["role"] = "fit"
    assert row["extra"]["role"] == "calibration"
    assert out["source_quality_flags"] == {}
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize("field", ["primary_source_status", "target_state_status", "endpoint_subtype", "requested_endpoint_subtype", "assigned_role"])
def test_nonscalar_metadata_is_not_admitted(field):
    metadata = deepcopy(PROFILE)
    metadata[field] = []
    assert admission(metadata, "fit")["eligible_for_declared_purpose"] is False


def test_boolean_source_alias_is_not_integer_source_one():
    metadata = deepcopy(PROFILE)
    metadata["src_id"] = True
    assert admission(metadata, "fit")["eligible_for_declared_purpose"] is False


@pytest.mark.parametrize("assigned", ["calibration", "development_test", None, "unknown", False])
def test_explicit_nonfit_assignment_cannot_enter_fit(assigned):
    profile = deepcopy(PROFILE)
    profile["raw_metadata"]["role"] = "fit"
    profile["assigned_role"] = assigned
    original = deepcopy(profile)
    result = admission(profile, "fit")
    assert result["eligible_for_declared_purpose"] is False
    assert "assigned_role_disallows_fit" in result["issues"]
    assert profile == original == result["source_metadata"]

@pytest.mark.parametrize("explicit", [True, False])
def test_fit_role_preserves_matching_or_absent_assignment_compatibility(explicit):
    profile = deepcopy(PROFILE)
    profile["raw_metadata"]["role"] = "fit"
    if not explicit:
        profile.pop("assigned_role")
    result = admission(profile, "fit")
    assert result["eligible_for_declared_purpose"] is True
    assert result["source_metadata"] == profile
