"""Installed receipt checks against a completed synthetic four-arm run."""
from collections import Counter
import json
from pathlib import Path
import shutil

import pytest

from betelgeuze_product import comparison_receipts as receipts
from tests.unit.test_prepared_candidate_comparison import (
    _protocol, _zero_lj_source, comparison,
)
from tests.unit.test_prepared_rigid_poses import _pose, _request


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


@pytest.fixture(scope="module")
def screened_portable(tmp_path_factory):
    root = tmp_path_factory.mktemp("screened-portable-comparison")
    protocol = _protocol(root / "inputs")
    mixed = _request(root / "mixed-source")
    _zero_lj_source(mixed)
    mixed["poses"] = [_pose("near", -3.2), _pose("far")]
    overlap_only = _request(root / "overlap-source")
    _zero_lj_source(overlap_only)
    overlap_only["poses"] = [_pose("near-only", -3.2)]
    for rid, request in (("a", mixed), ("b", overlap_only)):
        path = root / f"{rid}.screened-request.json"
        path.write_bytes(receipts._canonical(request) + b"\n")
        protocol["requests"][rid] = {
            "path": str(path), "sha256": receipts._digest(path.read_bytes())}
    comparison.run(protocol, root / "source")
    portable = root / "portable"
    assert receipts.export_legacy_synthetic(root / "source", portable)["status"] == "verified"
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


def _rewrite_report(root, arm, rid, change):
    result = json.loads((root / "result.json").read_text())
    row = next(item for item in result["arms"][arm]["rows"]
               if item["record_id"] == rid)
    ref = row["pose_report"]
    report_path = root / ref["path"]
    report = json.loads(report_path.read_text())
    change(report)
    raw = receipts._canonical(report) + b"\n"
    report_path.write_bytes(raw)
    new_ref = receipts._entry(ref["path"], raw)
    row["pose_report"] = new_ref
    _rewrite_result(root, lambda payload: payload.update(arms=result["arms"]))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["pose_reports"] = [
        new_ref if item["path"] == ref["path"] else item
        for item in manifest["pose_reports"]]
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
    assert verified["hard_overlap_screen_verified"] is True
    assert verified["ligand_net_charge_screen_verified"] is True
    assert verified["candidate_cost_bounds_verified"] is True


def test_screened_v3_export_preserves_overlap_exclusion(screened_portable):
    result = json.loads((screened_portable / "result.json").read_text())
    assert result["schema_version"] == receipts.CHARGE_SCREENED_SCHEMA
    rows = {row["record_id"]: row for row in result["arms"]["engine"]["rows"]}
    assert rows["a"]["selected_pose"]["pose_id"] == "far"
    assert [pose["status"] for pose in rows["a"]["hard_overlap_screen"]["poses"]] == [
        "hard_overlap", "eligible"]
    assert rows["b"]["status"] == "failed"
    assert rows["b"]["reason"] == "no_hard_overlap_screen_eligible_pose"
    verified = receipts.verify_run(screened_portable)
    assert verified["status"] == "verified"
    assert verified["hard_overlap_screen_verified"] is True
    assert verified["ligand_net_charge_screen_verified"] is True


def test_screened_v2_resealed_selection_of_overlap_rejected(screened_portable, tmp_path):
    copied = tmp_path / "resealed-overlap-selection"
    shutil.copytree(screened_portable, copied)

    def change(result):
        arm = result["arms"]["engine"]
        row = next(item for item in arm["rows"] if item["record_id"] == "a")
        report = json.loads((copied / row["pose_report"]["path"]).read_text())
        near = report["rows"][0]["result"]["quantities"]["cross_total_kcal_per_mol"]
        row["score"] = near
        row["selected_pose"] = {"request_index": 0, "pose_id": "near", "score": near}
        arm["ranked_record_ids"] = [item["record_id"] for item in sorted(
            (item for item in arm["rows"] if item["status"] == "evaluated"),
            key=lambda item: (item["score"], item["record_id"]))]

    _rewrite_result(copied, change)
    assert receipts.verify_run(copied)["reason"] == (
        "pose_report_hard_overlap_screen_mismatch")


def test_screened_v3_resealed_charge_decision_rejected(screened_portable, tmp_path):
    copied = tmp_path / "resealed-charge-screen"
    shutil.copytree(screened_portable, copied)

    def change(result):
        row = next(item for item in result["arms"]["engine"]["rows"]
                   if item["record_id"] == "a")
        row["ligand_net_charge_screen"]["rank_eligible"] = False

    _rewrite_result(copied, change)
    assert receipts.verify_run(copied)["reason"] == "pose_report_charge_screen_mismatch"


@pytest.mark.parametrize("measure,reason", [
    ("wall_seconds", "portable_row_wall_exceeds_arm_wall"),
    ("cpu_seconds", "portable_row_cpu_exceeds_worker_cpu"),
])
def test_v3_resealed_candidate_cost_cannot_exceed_observed_total(
    exported, tmp_path, measure, reason,
):
    copied = tmp_path / f"resealed-cost-{measure}"
    shutil.copytree(exported, copied)

    def change(result):
        data = result["arms"]["similarity"]
        observed = (data["completion"]["measured_process_wall_seconds"]
                    if measure == "wall_seconds" else
                    data["worker_complete"]["process_cpu_seconds"])
        row = next(item for item in data["rows"] if "completed_monotonic" in item)
        row["cost"][measure] = observed + 10.0

    _rewrite_result(copied, change)
    verified = receipts.verify_run(copied)
    assert verified["status"] == "invalid"
    assert verified["reason"] == reason


def test_screened_v3_resealed_charge_observation_rejected(screened_portable, tmp_path):
    copied = tmp_path / "resealed-charge-observation"
    shutil.copytree(screened_portable, copied)

    def change(report):
        report["preparation"]["preparation_provenance"][
            "ligand_source_net_charge_observation"]["itp_minus_sdf_charge_sum_e"] = "0.0"

    _rewrite_report(copied, "engine", "a", change)
    assert receipts.verify_run(copied)["reason"] == "pose_report_ligand_charge_source_mismatch"


def test_screened_v3_resealed_compiled_profile_cannot_skip_charge_screen(
    screened_portable, tmp_path,
):
    copied = tmp_path / "resealed-compiled-profile"
    shutil.copytree(screened_portable, copied)

    def change_report(report):
        provenance = report["preparation"]["preparation_provenance"]
        provenance["schema_version"] = "compiled_gromacs_cross_particles_v1"
        provenance.pop("ligand_source_net_charge_observation")

    _rewrite_report(copied, "engine", "a", change_report)

    def change_result(result):
        row = next(item for item in result["arms"]["engine"]["rows"]
                   if item["record_id"] == "a")
        screen = row["ligand_net_charge_screen"]
        screen.update(
            profile="compiled_gromacs_cross_particles_v1",
            status="not_assessed_compiled_profile", rank_eligible=True,
            sdf_formal_charge_sum_e=None,
            itp_printed_partial_charge_sum_e=None,
            difference_e=None, print_resolution_bound_e=None,
            scope="no SDF formal-charge source in compiled particle profile; not chemical validation",
        )

    _rewrite_result(copied, change_result)
    assert receipts.verify_run(copied)["reason"] == "pose_report_ligand_charge_source_mismatch"


def test_v3_portable_receipt_retains_charge_rejected_numeric_pose(tmp_path):
    protocol = _protocol(tmp_path / "inputs")
    conflict = _request(tmp_path / "conflict")
    sdf = conflict["prepared_input"]["ligand_sdf"]
    sdf_path = Path(sdf["path"])
    sdf_path.write_text(sdf_path.read_text().replace(
        "M  END\n", "M  CHG  1   1   1\nM  END\n"))
    sdf["sha256"] = receipts._digest(sdf_path.read_bytes())
    request_path = tmp_path / "conflict.request.json"
    request_path.write_bytes(receipts._canonical(conflict) + b"\n")
    protocol["requests"]["a"] = {
        "path": str(request_path), "sha256": receipts._digest(request_path.read_bytes())}
    comparison.run(protocol, tmp_path / "source")
    portable = tmp_path / "portable"
    assert receipts.export_legacy_synthetic(tmp_path / "source", portable)["status"] == "verified"
    result = json.loads((portable / "result.json").read_text())
    assert result["schema_version"] == receipts.CHARGE_SCREENED_SCHEMA
    row = next(item for item in result["arms"]["engine"]["rows"]
               if item["record_id"] == "a")
    report = json.loads((portable / row["pose_report"]["path"]).read_text())
    assert receipts.check_report(report)["status"] == "passed"
    assert row["numeric_denominator"]["passed"] == 2
    assert row["status"] == "failed" and row["score"] is None
    assert row["reason"] == "ligand_net_charge_rank_ineligible"
    assert row["ligand_net_charge_screen"]["status"] == "different_integral_state_range"
    assert receipts.verify_run(portable)["ligand_net_charge_screen_verified"] is True


@pytest.mark.parametrize("field,coordinate", [
    ("source_receptor_coordinates_angstrom", 0.2),
    ("evaluated_ligand_coordinates_angstrom", 0.8),
])
def test_screened_v2_resealed_display_geometry_rejected(
    screened_portable, tmp_path, field, coordinate,
):
    copied = tmp_path / field
    shutil.copytree(screened_portable, copied)

    def change(report):
        if field == "source_receptor_coordinates_angstrom":
            report["preparation"][field][0][0] = coordinate
        else:
            report["rows"][0][field][0][0] = coordinate

    _rewrite_report(copied, "engine", "a", change)
    assert receipts.verify_run(copied)["reason"] == "pose_report_source_geometry_mismatch"


def test_v1_receipt_preserves_historical_numeric_minimum(screened_portable, tmp_path):
    copied = tmp_path / "historical-v1"
    shutil.copytree(screened_portable, copied)

    def change(result):
        result["schema_version"] = receipts.SCHEMA
        for arm in receipts.ARMS:
            if arm == "similarity":
                continue
            data = result["arms"][arm]
            for row in data["rows"]:
                ref = row.get("pose_report")
                if ref is None:
                    continue
                report = json.loads((copied / ref["path"]).read_text())
                if receipts.check_report(report)["status"] == "passed":
                    row.update(status="evaluated", reason=None, score=min(
                        item["result"]["quantities"]["cross_total_kcal_per_mol"]
                        for item in report["rows"]))
                row.pop("hard_overlap_screen", None)
                row.pop("ligand_net_charge_screen", None)
                row.pop("selected_pose", None)
            data["denominator"] = {
                "requested": len(data["rows"]),
                **dict(Counter(row["status"] for row in data["rows"])),
            }
            data["ranked_record_ids"] = [row["record_id"] for row in sorted(
                (row for row in data["rows"] if row["status"] == "evaluated"),
                key=lambda row: (row["score"], row["record_id"]))]

    _rewrite_result(copied, change)
    verified = receipts.verify_run(copied)
    assert verified["status"] == "verified"
    assert verified["hard_overlap_screen_verified"] is False
    assert verified["ligand_net_charge_screen_verified"] is False
    assert verified["candidate_cost_bounds_verified"] is False


def test_v2_receipt_preserves_historical_overlap_only_screen(screened_portable, tmp_path):
    copied = tmp_path / "historical-v2"
    shutil.copytree(screened_portable, copied)

    def change(result):
        result["schema_version"] = receipts.SCREENED_SCHEMA
        for arm in receipts.ARMS:
            for row in result["arms"][arm]["rows"]:
                row.pop("ligand_net_charge_screen", None)

    _rewrite_result(copied, change)
    verified = receipts.verify_run(copied)
    assert verified["status"] == "verified"
    assert verified["hard_overlap_screen_verified"] is True
    assert verified["ligand_net_charge_screen_verified"] is False
    assert verified["candidate_cost_bounds_verified"] is False


@pytest.mark.parametrize("mutation,reason", [
    ("raw_result", "receipt_result_hash_mismatch"),
    ("score", "pose_report_score_mismatch"),
    ("denominator", "receipt_denominator_mismatch"),
    ("completion", "invalid_completion_receipt"),
    ("budget", "invalid_completion_receipt"),
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
            elif mutation == "budget":
                engine["completion"]["measured_process_wall_seconds"] = (
                    result["budget_seconds_per_arm"] + 1.0)
                engine["completion"]["termination_overhead_seconds"] = 1.0
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
