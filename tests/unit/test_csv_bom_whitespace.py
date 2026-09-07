"""BOM removal must also preserve the existing whitespace normalization."""
import pytest

from tools.product.residual_evidence import declared_evaluation_only, validated_csv_fieldnames


@pytest.mark.parametrize("field", ["role", "split", "dataset_split", "evaluation_only"])
def test_bom_followed_by_whitespace_cannot_hide_policy(field):
    headers = validated_csv_fieldnames(["\ufeff " + field.upper() + " ", "ligand_id"])
    row = dict(zip(headers, ["true" if field == "evaluation_only" else "holdout", "synthetic"]))
    assert headers[0] == field
    assert declared_evaluation_only(row) is True
