"""Installed receipt checks against a completed synthetic four-arm run."""
import json
import shutil

import pytest

from betelgeuze_product import comparison_receipts as receipts
from tests.unit.test_prepared_candidate_comparison import _protocol, comparison


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    root = tmp_path_factory.mktemp("installed-comparison-receipt")
    source = root / "legacy"
    comparison.run(_protocol(root / "inputs"), source)
    portable = root / "portable"
    result = receipts.export_legacy_synthetic(source, portable)
    assert result["status"] == "verified"
    assert result["pose_reports_checked"] >= 2
    return portable


def _rewrite_result(root, change):
    result_path = root / "result.json"
    manifest_path = root / "manifest.json"
    result = json.loads(result_path.read_text())
    change(result)
    raw = receipts._canonical(result) + b"\n"
    result_path.write_bytes(raw)
    manifest = json.loads(manifest_path.read_text())
    manifest["result"] = receipts._entry("result.json", raw)
    manifest_path.write_bytes(receipts._canonical(manifest) + b"\n")


def test_receipt_verifies_without_source_inputs_or_tools(exported, tmp_path):
    copied = tmp_path / "copy"
    shutil.copytree(exported, copied)
    before = {str(p.relative_to(copied)): p.read_bytes()
              for p in copied.rglob("*") if p.is_file()}
    verified = receipts.verify_run(copied)
    after = {str(p.relative_to(copied)): p.read_bytes()
             for p in copied.rglob("*") if p.is_file()}
    assert verified["status"] == "verified"
    assert after == before
    assert verified["execution_performed"] is False
    assert verified["selector_recomputed"] is False
    assert verified["scientifically_validated"] is False


@pytest.mark.parametrize("mutation,reason", [
    ("raw_result", "receipt_result_hash_mismatch"),
    ("score", "pose_report_score_mismatch"),
    ("denominator", "receipt_denominator_mismatch"),
    ("completion", "invalid_completion_receipt"),
    ("worker", "invalid_worker_completion_receipt"),
    ("missing_pose_reference", "evaluated_engine_row_missing_pose_report"),
    ("similarity_score", "similarity_prediction_score_mismatch"),
    ("pose_bytes", "pose_report_hash_mismatch"),
    ("pose_resealed", "pose_report_denominator_mismatch"),
    ("extra_report", "unexpected_pose_report_file"),
])
def test_tampered_copy_rejected(exported, tmp_path, mutation, reason):
    copied = tmp_path / mutation
    shutil.copytree(exported, copied)
    if mutation == "raw_result":
        with (copied / "result.json").open("ab") as stream:
            stream.write(b" ")
    elif mutation == "extra_report":
        (copied / "reports" / "engine" / "extra.poses.json").write_text("{}")
    elif mutation in {"pose_bytes", "pose_resealed"}:
        result = json.loads((copied / "result.json").read_text())
        row = next(row for row in result["arms"]["engine"]["rows"]
                   if row["status"] == "evaluated")
        ref = row["pose_report"]
        path = copied / ref["path"]
        report = json.loads(path.read_text())
        scored = next(item for item in report["rows"] if item["status"] == "evaluated")
        scored["result"]["quantities"]["cross_total_kcal_per_mol"] += 1.0
        raw = receipts._canonical(report) + b"\n"
        path.write_bytes(raw)
        if mutation == "pose_resealed":
            new_ref = receipts._entry(ref["path"], raw)
            row["pose_report"] = new_ref
            _rewrite_result(copied, lambda payload: payload.update(arms=result["arms"]))
            manifest = json.loads((copied / "manifest.json").read_text())
            manifest["pose_reports"] = [new_ref if value["path"] == ref["path"] else value
                                        for value in manifest["pose_reports"]]
            (copied / "manifest.json").write_bytes(receipts._canonical(manifest) + b"\n")
    else:
        def change(result):
            engine = result["arms"]["engine"]
            if mutation == "score":
                next(row for row in engine["rows"] if row["status"] == "evaluated")["score"] += 1.0
            elif mutation == "denominator":
                engine["denominator"]["requested"] += 1
            elif mutation == "completion":
                engine["completion"]["status"] = "budget_exhausted"
            elif mutation == "worker":
                engine["worker_complete"]["engine_calls"] = result["max_engine_calls_per_arm"] + 1
            elif mutation == "missing_pose_reference":
                next(row for row in engine["rows"] if row["status"] == "evaluated").pop("pose_report")
            elif mutation == "similarity_score":
                next(row for row in result["arms"]["similarity"]["rows"]
                     if row["status"] == "evaluated")["score"] += 1.0
        _rewrite_result(copied, change)
    verified = receipts.verify_run(copied)
    assert verified["status"] == "invalid"
    assert verified["reason"] == reason


def test_export_does_not_migrate_or_touch_legacy_run(exported):
    assert (exported / "frozen.json").exists() is False
    assert (exported / "comparison.json").exists() is False
    assert (exported / "manifest.json").exists()


def test_reseal_cannot_change_numeric_denominator(exported, tmp_path):
    copied = tmp_path / "denominator"
    shutil.copytree(exported, copied)
    def change(result):
        row = next(row for row in result["arms"]["engine"]["rows"]
                   if row["status"] == "evaluated")
        row["numeric_denominator"]["passed"] += 1
    _rewrite_result(copied, change)
    assert receipts.verify_run(copied)["reason"] == "pose_report_denominator_mismatch"


def test_prespecified_v2_arm_order_is_preserved(tmp_path):
    protocol = _protocol(tmp_path / "inputs")
    protocol.update(schema_version=comparison.ORDERED_SCHEMA,
                    selection_seed=17, tie_policy="seeded_pool_order",
                    arm_order=["ai_engine", "similarity", "engine", "similarity_engine"])
    comparison.run(protocol, tmp_path / "legacy")
    exported = tmp_path / "portable"
    assert receipts.export_legacy_synthetic(tmp_path / "legacy", exported)["status"] == "verified"
    result = json.loads((exported / "result.json").read_text())
    assert result["arm_order"] == protocol["arm_order"]
    assert receipts.verify_run(exported)["status"] == "verified"
