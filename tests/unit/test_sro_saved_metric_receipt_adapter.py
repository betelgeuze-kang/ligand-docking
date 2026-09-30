"""Synthetic receipt projection tests; no molecular implementation or real input."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_sro_pose_recovery/saved_metric_receipt_adapter.py"
SPEC = importlib.util.spec_from_file_location("tested_sro_saved_metric_receipt_adapter", SOURCE)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def write(path, value, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if raw else adapter._encode(value))
    return pin(path)


def read(ref):
    return json.loads(Path(ref["path"]).read_bytes())


def work(completed=True):
    values = {key: 0 for key in adapter.WORK_FIELDS}
    values.update(objective_attempts=1, initial_successful_objectives=int(completed),
                  failed_attempts=int(not completed), score_calls=2 if completed else 1,
                  oracle_states=2 if completed else None)
    return values


@pytest.fixture
def exported(tmp_path, monkeypatch):
    archive = tmp_path / "frozen"
    exporter_ref = write(archive / "source/campaign_supervisor.py", b"# synthetic source assertion\n", raw=True)
    monkeypatch.setattr(adapter, "EXPORTER_SHA256", exporter_ref["sha256"])
    driver_ref = write(archive / "source/runtime_execution.py", b"# synthetic driver, never run\n", raw=True)
    runner_ref = write(archive / "source/endpoint_oracle_runner.py", b"# synthetic oracle runner\n", raw=True)
    oracle_ref = write(archive / "source/sro_recovery_endpoint_numerics_v1.py", b"# synthetic oracle\n", raw=True)
    spec_ref = write(archive / "oracle-input-spec.json", {"synthetic": True})
    revision = {"schema_id": "sro_operational_repair_revision/1", "resume": False,
                "budget_reset": False, "scientific_protocol_changed": False, "source_roles_changed": False}
    plan_ref = write(archive / "plan.json", {
        "protocol_sha256": adapter.PROTOCOL_SHA256, "manifest_sha256": adapter.MANIFEST_SHA256,
        "driver_source_ref": driver_ref, "operational_revision": revision,
        "oracle_phase": {"source_refs": [exporter_ref, runner_ref, oracle_ref, spec_ref]},
    })
    review_ref = write(archive / "execution-review.json", {
        "schema_id": "sro_native_execution_review/1", "execution_authorized": True,
        "plan_sha256": plan_ref["sha256"], "driver_source_sha256": driver_ref["sha256"],
        "reviewed_at": "2026-09-30T00:00:00+00:00",
    })
    start_ref = write(archive / "campaign/campaign-start.json", {
        "plan_ref": plan_ref, "review_ref": review_ref, "supervisor_source_ref": exporter_ref,
        "case_order": adapter.CASE_IDS, "denominator": 4, "operational_revision": revision,
    })
    campaign_rows, rich_rows, legacy_rows = [], [], []
    for index, case_id in enumerate(adapter.CASE_IDS):
        status = ["completed", "completed", "failed", "unstarted"][index]
        if status == "unstarted":
            campaign_rows.append({"case_id": case_id, "status": status, "started_at": None})
            rich_rows.append({"case_id": case_id, "status": status, "work": None,
                              "legacy_exported": False, "omission_reason": "unstarted_work_unknown"})
            continue
        root = archive / "campaign" / case_id
        refs = [write(root / relative, {"case_id": case_id, "synthetic": True})
                for relative in sorted(adapter._REQUIRED_COMPLETED)]
        refs.extend([
            write(root / "native/dispatch.jsonl", b'{"event":"begin"}\n{"event":"end"}\n', raw=True),
            write(root / "native/run/numerical/events.jsonl", b'{"kind":"synthetic"}\n', raw=True),
            write(root / "native-process/stdout.log", b"opaque synthetic log\n", raw=True),
            write(root / "native/run/.minimization.lock", b"", raw=True),
        ])
        terminal_ref = write(root / "terminal-case.json", {"case_id": case_id, "status": status})
        case_work = work(status == "completed")
        row = {"case_id": case_id, "status": status, "started_at": "2026-09-30T01:00:00+00:00",
               "actual_receipt_refs": refs, "terminal_case_ref": terminal_ref,
               "native_child_ref": next(r for r in refs if r["path"].endswith("native/child-result.json")),
               "numerical_receipt_ref": next(r for r in refs if r["path"].endswith("oracle/numerical-receipt.json"))}
        campaign_rows.append(row)
        rich = {"case_id": case_id, "status": status, "work": case_work,
                "accounting": {"work": deepcopy(case_work)}, "legacy_exported": status == "completed",
                "omission_reason": None if status == "completed" else "legacy_start_coordinates_not_authenticated"}
        rich_rows.append(rich)
        if status == "completed":
            saved = {key: None for key in adapter.CASE_FIELDS}
            saved.update(case_id=case_id, status=status, started_at=row["started_at"],
                         work=case_work, endpoint_policy="last_accepted_state",
                         actual_receipt_refs=[terminal_ref, *refs],
                         coordinates_angstrom=[[0., 0., 0.] for _ in range(26)],
                         forces_kcal_per_mol_angstrom=[[0., 0., 0.] for _ in range(26)],
                         geometry_complete=True, geometry_checks={"synthetic": True},
                         numerical_audit={"endpoint_count": 2, "maximum_energy_error_kcal_per_mol": 0.,
                                          "maximum_force_component_error_kcal_per_mol_angstrom": 4e-8})
            legacy_rows.append(saved)
    campaign_ref = write(archive / "campaign/campaign-result.json", {
        "schema_id": "sro_four_case_campaign/2", "execution_order": adapter.CASE_IDS,
        "denominator": 4, "status": "stopped", "case_results": campaign_rows,
        "plan_ref": plan_ref, "review_ref": review_ref, "campaign_start_ref": start_ref,
        "operational_revision": revision,
    })
    saved_ref = write(tmp_path / "export/saved-recovery-results.json", {
        "schema_id": "sro_saved_recovery_results/1", "protocol_sha256": adapter.PROTOCOL_SHA256,
        "authority": deepcopy(adapter.AUTHORITY), "case_results": legacy_rows,
    })
    export_ref = write(tmp_path / "export/export-receipt.json", {
        "schema_id": "sro_saved_recovery_export/2", "campaign_ref": campaign_ref,
        "saved_results_ref": saved_ref, "case_results": rich_rows, "denominator": 4,
        "export_source_ref": exporter_ref, "operational_revision": revision,
        "new_native_force_calls": 0, "new_native_score_calls": 0, "new_openmm_observations": 0,
        "authority": deepcopy(adapter.AUTHORITY),
        "evidence_scope": "saved_data_arithmetic_and_existing_source_pinned_execution_receipts",
    })
    return {"saved": saved_ref, "export": export_ref, "output": tmp_path / "projection"}


def project(fixture):
    return adapter.project_saved_metric_input(fixture["saved"], fixture["export"], fixture["output"])


def replace_saved(fixture, mutation, raw=None):
    saved = read(fixture["saved"])
    mutation(saved)
    fixture["saved"] = write(Path(fixture["saved"]["path"]), raw if raw is not None else saved, raw=raw is not None)
    export = read(fixture["export"])
    export["saved_results_ref"] = fixture["saved"]
    fixture["export"] = write(Path(fixture["export"]["path"]), export)


def test_projection_preserves_result_body_and_all_raw_references(exported):
    original = read(exported["saved"])
    before = {ref["path"]: pin(Path(ref["path"]))
              for row in original["case_results"] for ref in row["actual_receipt_refs"]}
    result = project(exported)
    assert set(result) == {"projection_ref", "validation_receipt_ref", "omission_manifest_ref"}
    projected, receipt, omissions = (read(result[k]) for k in result)
    for original_row, projected_row in zip(original["case_results"], projected["case_results"]):
        assert {k: v for k, v in original_row.items() if k != "actual_receipt_refs"} == {
            k: v for k, v in projected_row.items() if k != "actual_receipt_refs"}
        assert all(Path(r["path"]).suffix == ".json" and type(read(r)) is dict
                   for r in projected_row["actual_receipt_refs"])
    assert receipt["rich_export_schema"] == "sro_saved_recovery_export/2"
    assert receipt["legacy_case_ids"] == ["perturbed_01", "perturbed_02"]
    assert [r["status"] for r in receipt["rich_case_results"]] == ["completed", "completed", "failed", "unstarted"]
    assert receipt["all_before_after_pins_unchanged"] is True
    assert receipt["authority"] == adapter.AUTHORITY
    assert {r["kind"] for r in omissions["excluded_from_projection_only"]} == {"json", "jsonl", "log", "lock"}
    assert all(pin(Path(path)) == ref for path, ref in before.items())
    assert receipt["all_original_actual_references_raw_authenticated_before_content_validation"] is True
    assert receipt["original_packet_and_evaluation_only_policy_checks_still_required"] is True


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("bytes", 0),
                                         ("bytes", adapter.MAX_REFERENCE_BYTES + 1)])
def test_input_pin_mutations_rejected_before_output(exported, field, value):
    exported["saved"][field] = value
    with pytest.raises(adapter.ProjectionError):
        project(exported)
    assert not exported["output"].exists()


def test_body_mutation_with_old_pin_is_rejected(exported):
    path = Path(exported["saved"]["path"])
    data = read(exported["saved"])
    data["case_results"][0]["coordinates_angstrom"][0][0] = 1.
    write(path, data)
    with pytest.raises(adapter.ProjectionError, match="reference_hash_or_bytes_mismatch"):
        project(exported)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'[]'])
def test_strict_json_receipts_reject_rebound_malformed_content(exported, raw):
    replace_saved(exported, lambda _: None, raw=raw)
    with pytest.raises(adapter.ProjectionError):
        project(exported)


def test_duplicate_reference_rejected(exported):
    replace_saved(exported, lambda d: d["case_results"][0]["actual_receipt_refs"].append(
        deepcopy(d["case_results"][0]["actual_receipt_refs"][0])))
    with pytest.raises(adapter.ProjectionError, match="legacy_saved_case_binding_changed"):
        project(exported)


@pytest.mark.parametrize("mutation", [
    lambda d: d["case_results"][0].update(status="failed"),
    lambda d: d["case_results"][0].update(endpoint_policy="best_retrospective_state"),
    lambda d: d["authority"].update(training_admitted=True),
    lambda d: d["case_results"][0]["work"].update(objective_attempts=2),
])
def test_rebound_status_policy_authority_and_work_mutations_rejected(exported, mutation):
    replace_saved(exported, mutation)
    with pytest.raises(adapter.ProjectionError):
        project(exported)


def rebind_actual(exported, mutation):
    export = read(exported["export"])
    campaign = read(export["campaign_ref"])
    saved = read(exported["saved"])
    mutation(campaign["case_results"][0], saved["case_results"][0])
    export["campaign_ref"] = write(Path(export["campaign_ref"]["path"]), campaign)
    exported["saved"] = write(Path(exported["saved"]["path"]), saved)
    export["saved_results_ref"] = exported["saved"]
    exported["export"] = write(Path(exported["export"]["path"]), export)


def test_receipt_role_injection_rejected_even_with_matching_pins(exported):
    injected = write(exported["output"].parent / "source-like.json", {"synthetic": True})
    rebind_actual(exported, lambda c, s: (c["actual_receipt_refs"].append(injected),
                                        s["actual_receipt_refs"].append(injected)))
    with pytest.raises(adapter.ProjectionError, match="case_receipt_path_injection"):
        project(exported)


def test_undeclared_in_case_json_role_rejected(exported):
    campaign = read(read(exported["export"])["campaign_ref"])
    root = Path(campaign["case_results"][0]["terminal_case_ref"]["path"]).parent
    injected = write(root / "reference.json", {"synthetic": True})
    rebind_actual(exported, lambda c, s: (c["actual_receipt_refs"].append(injected),
                                        s["actual_receipt_refs"].append(injected)))
    with pytest.raises(adapter.ProjectionError, match="undeclared_case_receipt_role"):
        project(exported)


def test_duplicate_actual_reference_rejected_when_parent_lists_match(exported):
    def mutation(c, s):
        for row in (c, s):
            row["actual_receipt_refs"].append(deepcopy(row["actual_receipt_refs"][-1]))
    rebind_actual(exported, mutation)
    with pytest.raises(adapter.ProjectionError, match="duplicate_reference"):
        project(exported)


@pytest.mark.parametrize("raw", [b'{"event":}\n', b'{"event":"begin"}', b'{"a":1,"a":2}\n'])
def test_invalid_jsonl_rejected_after_raw_authentication(exported, raw):
    def mutation(campaign_row, saved_row):
        old = next(r for r in campaign_row["actual_receipt_refs"] if r["path"].endswith("dispatch.jsonl"))
        new = write(Path(old["path"]), raw, raw=True)
        for row in (campaign_row, saved_row):
            row["actual_receipt_refs"] = [new if r == old else r for r in row["actual_receipt_refs"]]
    rebind_actual(exported, mutation)
    with pytest.raises(adapter.ProjectionError):
        project(exported)
    assert not exported["output"].exists()


def test_jsonl_hash_mismatch_rejected(exported):
    saved = read(exported["saved"])
    ref = next(r for r in saved["case_results"][0]["actual_receipt_refs"] if r["path"].endswith("dispatch.jsonl"))
    Path(ref["path"]).write_bytes(b'{"different":true}\n')
    with pytest.raises(adapter.ProjectionError):
        project(exported)


def test_missing_required_json_ref_rejected_even_when_lists_match(exported):
    rebind_actual(exported, lambda c, s: [r.update(actual_receipt_refs=[ref for ref in r["actual_receipt_refs"]
        if not ref["path"].endswith("native/endpoint-states.json")]) for r in (c, s)])
    with pytest.raises(adapter.ProjectionError, match="required_completed_json_receipt_missing"):
        project(exported)


def test_parent_source_or_saved_binding_changes_are_rejected(exported):
    export = read(exported["export"])
    export["export_source_ref"]["sha256"] = "0" * 64
    exported["export"] = write(Path(exported["export"]["path"]), export)
    with pytest.raises(adapter.ProjectionError, match="unapproved_parent_exporter_source"):
        project(exported)


def test_projection_output_is_create_only(exported):
    project(exported)
    with pytest.raises(adapter.ProjectionError, match="create_only_external_output_required"):
        project(exported)


def test_size_mismatch_checked_before_read(tmp_path):
    path = tmp_path / "receipt.json"
    write(path, {})
    ref = pin(path)
    ref["bytes"] += 1
    with pytest.raises(adapter.ProjectionError, match="reference_size_mismatch_before_read"):
        adapter._read(ref)


def test_schema_one_parent_is_distinct_from_schema_two_rich_export(exported):
    export = read(exported["export"])
    campaign = read(export["campaign_ref"])
    campaign["schema_id"] = "sro_four_case_campaign/1"
    campaign.pop("operational_revision")
    export["campaign_ref"] = write(Path(export["campaign_ref"]["path"]), campaign)
    export["schema_id"] = "sro_saved_recovery_export/1"
    export.pop("operational_revision")
    exported["export"] = write(Path(exported["export"]["path"]), export)
    receipt = read(project(exported)["validation_receipt_ref"])
    assert receipt["rich_export_schema"] == "sro_saved_recovery_export/1"
    assert receipt["legacy_saved_schema"] == "sro_saved_recovery_results/1"
    assert len(receipt["rich_case_results"]) == 4
    assert len(receipt["legacy_case_ids"]) == 2


def test_reference_mutation_between_before_and_after_pass_rejected(exported, monkeypatch):
    original_read = adapter._read
    counts = {}

    def mutate_on_recheck(ref):
        counts[ref["path"]] = counts.get(ref["path"], 0) + 1
        if ref["path"].endswith("stdout.log") and counts[ref["path"]] == 2:
            Path(ref["path"]).write_bytes(b"changed after initial authentication\n")
        return original_read(ref)

    monkeypatch.setattr(adapter, "_read", mutate_on_recheck)
    with pytest.raises(adapter.ProjectionError):
        project(exported)
    assert not exported["output"].exists()
