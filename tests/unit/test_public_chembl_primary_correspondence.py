from copy import deepcopy

import pytest

from tools.product import public_chembl_primary_correspondence as audit


def inputs(values=("1",), primary_values=None):
    if primary_values is None:
        primary_values = values
    rows, primary, roles = [], [], []
    aliases = [str(i + 1) for i in range(len(primary_values))]
    record = {"record_id": 8, "src_id": 37, "document_chembl_id": audit.DOCUMENT,
              "molecule_chembl_id": "CHEMBL100", "compound_key": "BDBM100",
              "compound_name": "::".join("US9067949, " + alias for alias in aliases)}
    for i, value in enumerate(values):
        row = {"activity_id": i + 1, "record_id": 8, "src_id": 37,
               "assay_chembl_id": audit.ASSAY, "document_chembl_id": audit.DOCUMENT,
               "target_chembl_id": audit.TARGET, "molecule_chembl_id": "CHEMBL100",
               "canonical_smiles": "CCO", "standard_flag": 1, "potential_duplicate": 0,
               "data_validity_comment": None, "activity_comment": None}
        for prefix in ("", "standard_"):
            row.update({prefix + "type": "Ki", prefix + "value": value, prefix + "units": "nM",
                        prefix + "relation": "=", prefix + "upper_value": None,
                        prefix + "text_value": None})
        rows.append(row)
        roles.append({"activity_id": i + 1, "assigned_role": "fit", "evaluation_only": False,
                      "source_document": audit.DOCUMENT, "assay_id": audit.ASSAY, "endpoint": "Ki"})
    for alias, value in zip(aliases, primary_values):
        primary.append({"example": alias, "raw_value": value, "printed_unit": "nm"})
    return [rows, [record], primary, roles]


def test_unique_numeric_match_is_not_unit_chemical_or_training_approval():
    args = inputs()
    saved = deepcopy(args)
    row = audit.audit_fit(*args)[0]
    assert args == saved
    assert row["source_example"] == "1" and row["numeric_multiset_match"]
    assert not row["primary_literal_unit_agreement"]
    assert not row["source_stereochemical_state_verified"]
    assert not row["eligible_for_point_model"] and not row["scientific_admission"]
    assert row["normalized_observation"]["status"] == "exact"


def test_group_match_never_pairs_distinct_values_even_after_reordering():
    args = inputs(("5", "2"), ("2", "5"))
    rows = audit.audit_fit(*args)
    args[0].reverse()
    args[2].reverse()
    reordered = audit.audit_fit(*args)
    assert rows == reordered
    assert all(row["numeric_multiset_match"] and row["source_example"] is None for row in rows)
    assert all(not row["individual_pairs_inferred_from_values"] for row in rows)


def test_multiset_comparison_keeps_repeated_values():
    rows = audit.audit_fit(*inputs(("1", "1", "2"), ("1", "2", "2")))
    assert len(rows) == 3
    assert all(not row["numeric_multiset_match"] for row in rows)


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", None])
def test_invalid_measurement_retained_without_fallback(value):
    row = audit.audit_fit(*inputs((value,)))[0]
    assert row["source_activity"]["value"] == value
    assert "nonexact_or_invalid_database_Ki" in row["issues"]
    assert not row["eligible_for_point_model"]


@pytest.mark.parametrize("index,field", [(0, "activity_id"), (1, "record_id"), (2, "example"), (3, "activity_id")])
def test_duplicate_source_or_assignment_never_selects_last(index, field):
    args = inputs()
    duplicate = deepcopy(args[index][0])
    duplicate["unrelated_note"] = "different payload"
    assert field in duplicate
    args[index].append(duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        audit.audit_fit(*args)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
@pytest.mark.parametrize("policy", [{"role": "test"}, {"split": "calibration"},
                                    {"dataset_split": "fresh128"}, {"evaluation_only": True},
                                    {"assigned_role": "development_test"}, {"role": "unknown_role"}])
def test_nested_reserved_or_unknown_origin_rejected(index, policy):
    args = inputs()
    args[index][0]["joined_origins"] = [{"source": policy}]
    with pytest.raises(ValueError, match="source_policy|source_role"):
        audit.audit_fit(*args)


def test_value_in_evaluation_role_rejected_before_normalization(monkeypatch):
    args = inputs()
    args[3][0]["assigned_role"] = "development_test"
    def forbidden(*args):
        pytest.fail("must reject role before numeric normalization")
    monkeypatch.setattr(audit.measurement, "normalize_measurement", forbidden)
    with pytest.raises(ValueError, match="coverage"):
        audit.audit_fit(*args)


@pytest.mark.parametrize("field,value", [("target_chembl_id", "CHEMBL999"),
                                        ("document_chembl_id", "CHEMBL999"),
                                        ("src_id", 1), ("molecule_chembl_id", "CHEMBL101")])
def test_native_identity_conflict_is_not_numeric_correspondence(field, value):
    args = inputs()
    args[0][0][field] = value
    with pytest.raises(ValueError, match="identity"):
        audit.audit_fit(*args)


def test_censoring_is_not_exact_primary_value():
    args = inputs()
    args[0][0]["relation"] = args[0][0]["standard_relation"] = ">"
    row = audit.audit_fit(*args)[0]
    assert row["numeric_multiset_match"]
    assert "primary_exact_relation_disagreement" in row["issues"]
    assert "nonexact_or_invalid_database_Ki" in row["issues"]


def html(rows):
    return '<table><tr><td>human 5HT<span>6</span> Ki (nm)</td></tr>' + rows + '</table>'


def test_html_reader_preserves_zero_whitespace_and_printed_unit():
    rows = audit.extract_primary(html('<tr><td> </td><td>Compound of Example 34</td><td><span>0</span></td></tr>'),
                                 patent_id=audit.PATENT)
    assert rows[0]["raw_value"] == "0" and rows[0]["printed_unit"] == "nm"


@pytest.mark.parametrize("body", [
    '<tr><td>Compound of Example 1</td><td>2</td><td>3</td></tr>',
    '<tr><td>Compound of Example 1</td><td>2</td></tr>' * 2,
    '<tr><td>Compound of Example 1</td><td>2',
])
def test_ambiguous_or_truncated_html_fails(body):
    with pytest.raises(ValueError):
        audit.extract_primary(html(body), patent_id=audit.PATENT)


def test_other_patent_or_changed_endpoint_not_silently_parsed():
    with pytest.raises(ValueError, match="unsupported"):
        audit.extract_primary(html(""), patent_id="US10441590B2")
    with pytest.raises(ValueError, match="endpoint"):
        audit.extract_primary(html("").replace("Ki", "IC50"), patent_id=audit.PATENT)
