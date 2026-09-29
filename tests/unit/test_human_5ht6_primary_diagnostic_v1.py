"""Preserve published endpoints, reference context, and failed denominators."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pytest

from betelgeuze_product import public_assay_preflight as preflight
from tools.analysis import human_5ht6_primary_diagnostic_v1 as diagnostic
from tools.product import primary_5ht6_ki_multi_paper_v1 as paper

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/evidence/human_5ht6_ki_multi_paper_source_ledger_v1.json"


@pytest.mark.parametrize("value,unit,active", [
    ("1000", "nM", True), ("1.000", "µM", True),
    ("1.001", "µM", False), ("0.077", "µM", True),
])
def test_measured_units_and_fixed_activity_boundary(value, unit, active):
    reported = {"value": value, "unit": unit, "relation": "=",
                "uncertainty": {"kind": "SEM", "value": "0.1"}}
    result = diagnostic.measurement({"reported_ki": reported})
    assert result["observed_active_at_ki_le_1000nm"] is active
    assert Decimal(result["ki_nm"]) == Decimal(value) * (1000 if unit == "µM" else 1)
    assert result["reported_ki"] == reported
    if Decimal(result["ki_nm"]) == 1000:
        assert result["pki"] == 6


@pytest.mark.parametrize("relation,value,unit", [
    (">", "1000", "nM"), ("=", "NaN", "nM"), ("=", "-1", "nM"),
    ("=", "7", "pKi"),
])
def test_bounds_invalid_values_and_log_units_are_not_exact_ki(relation, value, unit):
    with pytest.raises(ValueError):
        diagnostic.measurement({"reported_ki": {
            "relation": relation, "value": value, "unit": unit, "uncertainty": None}})


def test_cited_reference_bridges_table_without_becoming_measurement():
    ledger, _ = paper.verify_ledger(LEDGER)
    nodes = diagnostic.family_nodes(ledger, {"SMILES":
        "CN1CCN(CC1)C2=C(C=CC(=C2)NS(=O)(=O)C3=CC=C(C=C3)I)OC"})
    reference = deepcopy(nodes[-1])
    reference.update(node_id="synthetic:reserved-reference",
                     record_id="synthetic:reserved-reference", protected=True)
    # Remove the paper DOI from the external node: the bridge must occur via
    # the reference chemistry, then through the cited row's paper membership.
    reference["keys"] = [key for key in reference["keys"] if key[0] != "document"]
    reference["document_identity_available"] = False
    before = preflight.preflight([reference], nodes[:-1])
    after = diagnostic.screen_family([reference], nodes)
    cid = "paper:" + diagnostic.BIOM_DOI + ":3a"
    assert next(row for row in before["results"] if row["candidate_id"] == cid)["status"] == "identity_clear_review_required"
    assert next(row for row in after["results"] if row["candidate_id"] == cid)["status"] == "blocked_identity"
    assert after["representative_biomolecules_witness"]["edge_kinds"][0] == "document"
    assert len(nodes) == 31 and len(ledger["rows"]) == 30
    assert not any(row["paper_row_id"] == "SB-258585" for row in ledger["rows"])
    assert not after["roles_assigned"] and not after["whole_article_source_family_complete"]
    assert all(not row["independent_evaluation_allowed"] for row in after["results"])


def test_metric_keeps_abstentions_in_request_denominator():
    rows = [{"pki": 5.0, "prediction": 7.0, "observed_active_at_ki_le_1000nm": False},
            {"pki": 7.0, "prediction": None, "observed_active_at_ki_le_1000nm": True}]
    result = diagnostic.point_metrics(rows, "prediction")
    assert result["requested"] == 2 and result["supported"] == 1
    assert result["mae"] == result["rmse"] == 2
    assert result["observed_inactive_predicted_active"] == 1
    rows[0]["prediction"] = None
    empty = diagnostic.point_metrics(rows, "prediction")
    assert empty["supported"] == 0 and empty["mae"] is None


def test_saved_report_preserves_retrospective_scope_and_zero_admission():
    path = ROOT / "docs/evidence/human_5ht6_primary_retrospective_diagnostic_v1.json"
    report = json.loads(path.read_text())
    assert report["source_experimental_rows"] == 30
    assert report["cited_reference_rows_not_experiments"] == 1
    assert report["plan_sha256"] == diagnostic.PLAN_SHA256
    assert report["source_ledger_sha256"] == paper.PINNED_LEDGER_SHA256
    assert report["additional_source_sha256"] == {
        key: value[1] for key, value in diagnostic.SOURCE_FILES.items()}
    assert report["identity_screen_with_cited_reference"]["status_counts"] == {
        "blocked_identity": 22, "identity_clear_review_required": 9}
    result = report["frozen_model_diagnostic"]
    assert result["checkpoint_sha256"] == diagnostic.CHECKPOINT_SHA256
    assert result["new_training_runs"] == result["new_calibration_runs"] == 0
    assert not result["independent_evaluation"] and not result["fresh128_opened"]
    assert not report["service_ready"] and not report["scientifically_qualified"]
    assert result["promotion_status"] == "NOT_PROMOTED"
    assert all(row["assigned_role"] is None and not row["independent_evaluation_admitted"]
               for row in result["rows"])
