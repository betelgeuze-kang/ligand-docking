"""Outcome-free native v4 snapshot inventory and adversarial denominator tests."""

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.analysis import native_v4_comparison_readiness as diagnostic


def _ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _write(path, value):
    path.write_bytes(diagnostic._canonical(value) + b"\n")
    return _ref(path)


def _row(number, endpoint, smiles="CCO", *, method=False):
    # One chemical can have Ki, association-rate and dissociation-rate records.
    identity = {"canonical_isomeric_smiles": smiles,
                "canonical_isomeric_smiles_sha256": hashlib.sha256(smiles.encode()).hexdigest(),
                "formal_charge": 0}
    metadata = {"standard_type": endpoint, "target_chembl_id": "CHEMBL3371",
                "assay_chembl_id": "CHEMBL5734474", "document_chembl_id": "CHEMBL5727345"}
    method_data = {**{k: v for k, v in metadata.items() if k != "standard_type"},
                   "assay_type": "B", "assay_tax_id": 9606, "confidence_score": 9,
                   "description": "Human receptor radioligand displacement binding"}
    absent = {"path": "/deliberately-unopened/raw-source.json", "sha256": "1" * 64}
    return {
        "record_id": f"chembl:activity:{number}", "assigned_role": "development_test",
        "component_id": "synthetic-public-component", "assay_id": "chembl:assay:CHEMBL5734474",
        "chemical_identity": identity, "native_metadata": metadata,
        "native_activity": None, "observation": None, "eligible_for_point_model": False,
        "target_annotation": {"chembl_target_id": "CHEMBL3371", "physical_state_verified": False},
        "prediction_issues": [] if endpoint == "Ki" else ["target_or_endpoint_outside_binding_Ki_scope"],
        "admission_issues": ["native_label_withheld"] + ([] if method else ["assay_method_not_verified_binding_Ki"]),
        "method_evidence": method_data if method else {},
        "source_origins": {"metadata_origin": absent, "method_origin": absent if method else None},
    }


def _prepared(tmp_path, row, *, frame="frame-A", receptor="2" * 64, pocket_x=0.0):
    request = {
        "schema_version": "prepared_rigid_pose_cross_request_v1",
        "prepared_input": {"schema_version": "prepared_gromacs_components_v1",
            **{key: {"path": "/deliberately-unopened/" + key,
                     "sha256": ("a" * 64 if key.startswith("protein_") else
                                row["chemical_identity"]["canonical_isomeric_smiles_sha256"]),
                     "source_id": "synthetic"} for key in diagnostic.PARAMETER_KEYS},
            "protein_pdb": {"path": "/deliberately-unopened/protein.pdb",
                            "sha256": receptor, "source_id": "synthetic"},
            "protein_chains": [{"chain_id": "A", "molecule_itp": {
                "path": "/deliberately-unopened/protein.itp", "sha256": "b" * 64,
                "source_id": "synthetic"}}],
            "naming_convention": "exact", "pdb_element_policy": "reject_missing",
            "source_declarations": {
            "prepared_state_id": "synthetic-prepared-state", "coordinate_frame_id": frame,
            "parameter_source_id": "synthetic-parameters", "charge_source_id": "synthetic-charges"}},
        "evaluation": {"pocket_center_angstrom": [pocket_x, 0.0, 0.0], "pocket_radius_angstrom": 6.0},
        "execution": {}, "poses": [],
    }
    descriptor = {
        "schema_version": "native_v4_candidate_prepared_structural_binding_v1",
        "record_id": row["record_id"], "assay_id": row["assay_id"],
        "metadata_origin_sha256": row["source_origins"]["metadata_origin"]["sha256"],
        "method_origin_sha256": row["source_origins"]["method_origin"]["sha256"],
        "target_annotation_sha256": diagnostic._sha(row["target_annotation"]),
        "target_chembl_id": row["native_metadata"]["target_chembl_id"],
        "prepared_input_sha256": diagnostic._sha(request["prepared_input"]),
        "ligand": {"canonical_isomeric_smiles_sha256": row["chemical_identity"]["canonical_isomeric_smiles_sha256"],
                   "formal_charge": 0},
        "receptor_system_sha256": receptor, "receptor_construct_sha256": "3" * 64,
        "pocket_sha256": diagnostic._sha(request["evaluation"]),
        "evaluation_sha256": diagnostic._sha(request["evaluation"]),
        "parameter_sources_sha256": diagnostic._sha({
            key: request["prepared_input"][key]["sha256"] for key in diagnostic.PARAMETER_KEYS}),
        **request["prepared_input"]["source_declarations"],
    }
    return _bind_descriptor(tmp_path, row, request, descriptor)


def _bind_descriptor(tmp_path, row, request, descriptor):
    origin = _write(tmp_path / (row["record_id"].replace(":", "-") + "-origin.json"), descriptor)
    row["source_origins"]["prepared_state_origin"] = origin
    recorded = {"schema_version": descriptor["schema_version"], "origin_sha256": origin["sha256"],
                "observation_sha256": diagnostic._sha(descriptor), "candidate_prepared_identity_bound": True,
                "same_prepared_assay_state_verified": False}
    return request, recorded


def _snapshots(tmp_path, rows, *, prepared=None, scored=None):
    prepared = prepared or {}
    pool = [row["record_id"] for row in rows]
    records_path = tmp_path / "records.jsonl"
    records_path.write_bytes(b"".join(diagnostic._canonical(row) + b"\n" for row in rows))
    roles = {"fit": 0, "calibration": 0, "development_test": len(rows)}
    summary = {"schema_version": "public_chembl_receptor_development_v4", "phase": "fit",
               "records_sha256": _ref(records_path)["sha256"], "assigned_role_counts": roles,
               "requested_metadata_rows": len(rows)}
    summary_ref = _write(tmp_path / "summary.json", summary)
    source_ref = {"schema_version": "installed_native_v4_fit_source_reference_v1", "phase": "fit",
                  "input_dir": str(tmp_path), "summary_sha256": summary_ref["sha256"]}
    source_receipt = {"schema_version": "installed_native_v4_fit_source_verification_v1",
                      "source_reference": source_ref, "source_reference_sha256": diagnostic._sha(source_ref),
                      "records_sha256": summary["records_sha256"], "assigned_role_counts": roles,
                      "requested_metadata_rows": len(rows), "evaluation_labels_read": 0}
    v2 = bool(prepared)
    frozen_schema = list(diagnostic.VERSIONS)[int(v2)]
    protocol_schema, result_schema = diagnostic.VERSIONS[frozen_schema]
    requests, request_refs = {}, {}
    for rid in pool:
        request = prepared[rid][0] if rid in prepared else None
        requests[rid] = request
        request_refs[rid] = None if request is None else _write(
            tmp_path / (rid.replace(":", "-") + "-request.json"), request)
    frozen = {
        "schema_version": frozen_schema, "protocol": {"schema_version": protocol_schema,
            "source": source_ref, "requests": request_refs,
            "max_engine_calls_per_arm": len(pool)},
        "source_kind": diagnostic.SOURCE_KIND, "pool": pool, "requests": requests,
        "evaluation_labels_read": 0, **dict.fromkeys(diagnostic.AUTHORITY_FLAGS, False),
        "source_verification": source_receipt,
        "rows": [{"record_id": row["record_id"], "role": row["assigned_role"],
                  "component_id": row["component_id"], "assay_id": row["assay_id"], "fit_value": None,
                  "smiles": row["chemical_identity"]["canonical_isomeric_smiles"]
                  if not row["prediction_issues"] else None} for row in rows],
    }
    if v2:
        frozen["prepared_bindings"] = {rid: prepared[rid][1] if rid in prepared else None for rid in pool}
    binding = diagnostic._sha(frozen)
    result = {"schema_version": result_schema, "source_kind": diagnostic.SOURCE_KIND, "pool": pool,
              "binding": binding, "evaluation_labels_read": 0,
              **dict.fromkeys(diagnostic.AUTHORITY_FLAGS, False), "arms": {}}
    if v2:
        result["candidate_prepared_identity_bound"] = {rid: rid in prepared for rid in pool}
    for name in diagnostic.ARMS:
        selected = (scored or {}).get(name, set())
        arm_rows = [{"record_id": rid, "status": "evaluated" if rid in selected else "unsupported",
                     "score": 1.0 if rid in selected else None,
                     "reason": None if rid in selected else "predictor_abstained",
                     **({"arm": name, "binding": binding} if rid in selected else {})} for rid in pool]
        result["arms"][name] = {
            "rows": arm_rows, "ranked_record_ids": [rid for rid in pool if rid in selected],
            "denominator": {"requested": len(pool), **dict(Counter(r["status"] for r in arm_rows))},
            "worker_complete": {"binding": binding,
                                "engine_calls": 0 if name == "similarity" else len(selected)},
            "completion": {"binding": binding, "status": "complete"},
            "score_quantity": "predicted_negative_log10_molar_endpoint" if name == "similarity" else "existing_cross_only_kcal_per_mol",
        }
    return (_write(tmp_path / "frozen.json", {"payload": frozen, "sha256": binding}),
            _write(tmp_path / "comparison.json", result))


def test_same_chemical_ki_kon_koff_is_one_distinct_ki_candidate_and_no_common_cohort(tmp_path):
    rows = [_row(27765488, "Ki"), _row(27765489, "kon"), _row(27765490, "k_off")]
    refs = _snapshots(tmp_path, rows, scored={"similarity": {rows[0]["record_id"]}})
    before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    value = diagnostic.build(*refs)
    assert value["denominator"] == {
        "requested_records": 3, "Ki_metadata": 1, "selector_supported_in_snapshot": 1,
        "prepared_request_present": 0, "prepared_source_origin_present": 0,
        "recorded_prepared_source_bound": 0, "recorded_method_consistent_Ki": 0,
        "distinct_recorded_chemical_identities": 1, "distinct_Ki_chemical_identities": 1,
        "unknown_chemical_identity_records": 0, "four_arm_common_scored_records": 0,
        "largest_method_and_frame_group_distinct_Ki_identities": 0,
        "largest_common_method_and_frame_group_distinct_Ki_identities": 0,
    }
    assert value["arms"]["similarity"]["denominator"]["evaluated"] == 1
    assert value["four_arm_common_scored_ids"] == []
    assert value["scientifically_eligible_comparison_denominator"] is None
    assert all(value[key] is False for key in diagnostic.AUTHORITY_FLAGS)
    assert value["evaluation_labels_read"] == value["engine_calls_performed"] == 0
    assert value["raw_identity_context_opened"] is False
    assert before == {path: path.read_bytes() for path in tmp_path.iterdir()}


def test_common_intersection_requires_all_arms_and_groups_distinct_ki_with_exact_method_frame(tmp_path):
    rows = [_row(1, "Ki", "CCO", method=True), _row(2, "Ki", "CCN", method=True),
            _row(3, "Ki", "CCN", method=True)]
    prepared = {r["record_id"]: _prepared(tmp_path, r) for r in rows}
    scored = {name: {r["record_id"] for r in rows} for name in diagnostic.ARMS}
    scored["ai_engine"].remove(rows[2]["record_id"])
    value = diagnostic.build(*_snapshots(tmp_path, rows, prepared=prepared, scored=scored))
    assert value["four_arm_common_scored_ids"] == [r["record_id"] for r in rows[:2]]
    count = value["denominator"]
    assert count["recorded_prepared_source_bound"] == count["recorded_method_consistent_Ki"] == 3
    assert count["distinct_Ki_chemical_identities"] == 2
    assert count["largest_common_method_and_frame_group_distinct_Ki_identities"] == 2
    assert len(value["method_and_receptor_pocket_frame_groups"]) == 1
    # Different ligand parameter bytes do not imply a different receptor frame.
    assert prepared[rows[0]["record_id"]][0]["prepared_input"]["ligand_itp"]["sha256"] != (
        prepared[rows[1]["record_id"]][0]["prepared_input"]["ligand_itp"]["sha256"])
    assert value["prepared_systems_reparsed"] is value["numerical_scores_reverified"] is False


@pytest.mark.parametrize("difference", ["coordinate_frame", "receptor", "pocket", "method", "target"])
def test_matching_labels_do_not_merge_different_method_receptor_or_frame(tmp_path, difference):
    rows = [_row(1, "Ki", "CCO", method=True), _row(2, "Ki", "CCN", method=True)]
    if difference == "method":
        rows[1]["method_evidence"]["description"] += " with a different assay condition"
    if difference == "target":
        rows[1]["method_evidence"]["target_chembl_id"] = "CHEMBL_OTHER"
    prepared = {rows[0]["record_id"]: _prepared(tmp_path, rows[0]),
                rows[1]["record_id"]: _prepared(tmp_path, rows[1],
                    frame="frame-B" if difference == "coordinate_frame" else "frame-A",
                    receptor="9" * 64 if difference == "receptor" else "2" * 64,
                    pocket_x=1.0 if difference == "pocket" else 0.0)}
    scored = {arm: {r["record_id"] for r in rows} for arm in diagnostic.ARMS}
    value = diagnostic.build(*_snapshots(tmp_path, rows, prepared=prepared, scored=scored))
    assert value["denominator"]["four_arm_common_scored_records"] == 2
    assert value["denominator"]["largest_common_method_and_frame_group_distinct_Ki_identities"] == 1


@pytest.mark.parametrize("change,reason", [
    ("bytes", "readiness_input_sha256_mismatch"),
    ("denominator", "readiness_recorded_denominator_mismatch"),
    ("duplicated_row", "duplicate_or_missing_readiness_record_id"),
    ("pool", "readiness_snapshot_scope_mismatch"),
])
def test_changed_result_and_denominator_fail_closed(tmp_path, change, reason):
    refs = list(_snapshots(tmp_path, [_row(1, "Ki")]))
    path = Path(refs[1]["path"])
    value = json.loads(path.read_bytes())
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    else:
        if change == "denominator":
            value["arms"]["engine"]["denominator"]["requested"] = 2
        elif change == "duplicated_row":
            value["arms"]["engine"]["rows"] *= 2
        else:
            value["pool"] = []
        refs[1] = _write(path, value)
    with pytest.raises(ValueError, match=reason):
        diagnostic.build(*refs)


@pytest.mark.parametrize("path,value", [
    (("observation",), {"unexpected_outcome": 0}),
    (("primary_evidence", "native_activity", "standard_value"), 42),
    (("native_activity_origin",), {"path": "/deliberately-unopened/outcomes.json"}),
    (("source_origins", "activity_origin"), {"path": "/deliberately-unopened/outcomes.json"}),
    (("native_metadata", "standard_value"), 42),
    (("document_evidence", "nested", "negative_log10_molar"), 7.0),
    (("method_evidence", "assay_parameters"), [{"value": 42}]),
    (("force_labels",), [1.0]),
])
def test_nonfit_outcome_is_rejected_even_in_resealed_cache(tmp_path, path, value):
    row = _row(1, "Ki")
    target = row
    for field in path[:-1]:
        target = target.setdefault(field, {})
    target[path[-1]] = value
    refs = _snapshots(tmp_path, [row])
    with pytest.raises(ValueError, match="readiness_nonfit_outcome_present"):
        diagnostic.build(*refs)


@pytest.mark.parametrize("change,reason", [
    ("row_binding", "readiness_arm_row_binding_mismatch"),
    ("row_arm", "readiness_arm_row_binding_mismatch"),
    ("row_missing_binding", "readiness_arm_row_binding_mismatch"),
    ("worker_binding", "readiness_worker_binding_mismatch"),
    ("worker_missing_binding", "readiness_worker_binding_mismatch"),
    ("completion_binding", "readiness_completion_binding_mismatch"),
    ("completion_missing_binding", "readiness_completion_binding_mismatch"),
    ("priority_binding", "readiness_priority_binding_mismatch"),
    ("priority_arm", "readiness_priority_binding_mismatch"),
])
def test_cross_wired_execution_bindings_fail_even_with_resealed_result(tmp_path, change, reason):
    row = _row(1, "Ki", method=True)
    refs = list(_snapshots(tmp_path, [row],
        prepared={row["record_id"]: _prepared(tmp_path, row)},
        scored={name: {row["record_id"]} for name in diagnostic.ARMS}))
    path = Path(refs[1]["path"])
    result = json.loads(path.read_bytes())
    arm = result["arms"]["engine"]
    arm["priority"] = {"binding": result["binding"], "arm": "engine", "evaluation_labels_read": 0}
    section, field = change.split("_", 1)
    target = arm["rows"][0] if section == "row" else arm[
        "worker_complete" if section == "worker" else section]
    if field == "missing_binding":
        del target["binding"]
    else:
        target[field] = "ai_engine" if field == "arm" else "0" * 64
    refs[1] = _write(path, result)
    with pytest.raises(ValueError, match=reason):
        diagnostic.build(*refs)


@pytest.mark.parametrize("status", ["unsupported", "not_processed", "failed"])
def test_wrong_binding_is_not_ignored_on_unscored_rows(tmp_path, status):
    refs = list(_snapshots(tmp_path, [_row(1, "Ki")]))
    path = Path(refs[1]["path"])
    result = json.loads(path.read_bytes())
    arm = result["arms"]["engine"]
    arm["rows"][0].update(status=status, binding="0" * 64, arm="engine")
    arm["denominator"] = {"requested": 1, status: 1}
    refs[1] = _write(path, result)
    with pytest.raises(ValueError, match="readiness_arm_row_binding_mismatch"):
        diagnostic.build(*refs)


@pytest.mark.parametrize("status", ["unsupported", "not_processed"])
def test_unprocessed_summary_rows_do_not_require_worker_row_bindings(tmp_path, status):
    refs = list(_snapshots(tmp_path, [_row(1, "Ki")]))
    path = Path(refs[1]["path"])
    result = json.loads(path.read_bytes())
    for arm in result["arms"].values():
        arm["rows"][0]["status"] = status
        arm["denominator"] = {"requested": 1, status: 1}
        arm["worker_complete"] = None
        arm["completion"]["status"] = "interrupted_budget_forfeited"
    refs[1] = _write(path, result)
    value = diagnostic.build(*refs)
    assert value["four_arm_common_scored_ids"] == []
    assert all(arm["recorded_engine_calls"] is None for arm in value["arms"].values())


def test_resealed_prepared_link_cannot_change_candidate_identity(tmp_path):
    row = _row(1, "Ki", method=True)
    request, recorded = _prepared(tmp_path, row)
    origin_path = Path(row["source_origins"]["prepared_state_origin"]["path"])
    origin = json.loads(origin_path.read_bytes())
    origin["ligand"]["canonical_isomeric_smiles_sha256"] = "0" * 64
    ref = _write(origin_path, origin)
    row["source_origins"]["prepared_state_origin"] = ref
    recorded.update(origin_sha256=ref["sha256"], observation_sha256=diagnostic._sha(origin))
    refs = _snapshots(tmp_path, [row], prepared={row["record_id"]: (request, recorded)})
    with pytest.raises(ValueError, match="readiness_prepared_candidate_join_mismatch"):
        diagnostic.build(*refs)


def test_cli_uses_standard_library_without_importing_comparison_or_creating_outputs(tmp_path):
    refs = _snapshots(tmp_path, [_row(1, "Ki")])
    script = Path(diagnostic.__file__)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = subprocess.run([sys.executable, "-I", "-B", str(script),
        "--frozen", refs[0]["path"], "--frozen-sha256", refs[0]["sha256"],
        "--comparison", refs[1]["path"], "--comparison-sha256", refs[1]["sha256"]],
        capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    assert value["status"] == "diagnostic_only"
    assert value["runtime_replay_verified"] is value["raw_source_rederived"] is False
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


def test_unknown_worker_cost_and_call_observation_remains_unknown(tmp_path):
    refs = list(_snapshots(tmp_path, [_row(1, "Ki")]))
    value = json.loads(Path(refs[1]["path"]).read_bytes())
    value["arms"]["engine"]["worker_complete"] = None
    value["arms"]["engine"]["completion"]["status"] = "worker_failed"
    refs[1] = _write(Path(refs[1]["path"]), value)
    assert diagnostic.build(*refs)["arms"]["engine"]["recorded_engine_calls"] is None


def test_common_scored_cannot_be_invented_for_null_prepared_requests(tmp_path):
    row = _row(1, "Ki")
    refs = _snapshots(tmp_path, [row], scored={name: {row["record_id"]} for name in diagnostic.ARMS})
    with pytest.raises(ValueError, match="readiness_engine_score_without_prepared_request"):
        diagnostic.build(*refs)


def test_actual_synthetic_v2_run_is_read_only_diagnostic_input(tmp_path):
    from betelgeuze_product import installed_synthetic_comparison as comparison
    from tests.unit.test_installed_native_v4_comparison import bounded_source, _linked_protocol

    bounded = bounded_source.__wrapped__(tmp_path)
    protocol, _, candidate = _linked_protocol(bounded, tmp_path)
    run_dir = tmp_path / "run"
    comparison.run(protocol, run_dir)
    refs = _ref(run_dir / "frozen.json"), _ref(run_dir / "comparison.json")
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    value = diagnostic.build(*refs)
    assert value["denominator"]["recorded_prepared_source_bound"] == 1
    assert value["four_arm_common_scored_ids"] == [candidate]
    assert value["denominator"]["recorded_method_consistent_Ki"] == 1
    assert value["denominator"]["largest_common_method_and_frame_group_distinct_Ki_identities"] == 1
    assert value["runtime_replay_verified"] is False
    assert before == {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}


def test_actual_descriptor_ligand_only_change_does_not_split_receptor_cohort(tmp_path):
    from betelgeuze_product.installed_native_v4_prepared_binding import derive_observation
    from tests.unit.test_installed_native_v4_comparison import _bound_request

    request = _bound_request(tmp_path)
    rows = [_row(1, "Ki", "C1CCOCC1", method=True), _row(2, "Ki", "C1CCOCC1", method=True)]
    for row in rows:
        row["chemical_identity"]["stereo_unspecified_count"] = 0
        row["target_annotation_sha256"] = diagnostic._sha(row["target_annotation"])
    first = derive_observation(rows[0], request)
    changed = copy.deepcopy(request)
    ligand_path = tmp_path / "ligand-comment-only.itp"
    ligand_path.write_bytes(Path(request["prepared_input"]["ligand_itp"]["path"]).read_bytes()
                            + b"\n; synthetic ligand-only provenance change\n")
    changed["prepared_input"]["ligand_itp"].update(_ref(ligand_path))
    second = derive_observation(rows[1], changed)
    assert first["receptor_system_sha256"] != second["receptor_system_sha256"]
    assert first["receptor_construct_sha256"] == second["receptor_construct_sha256"]
    prepared = {
        rows[0]["record_id"]: _bind_descriptor(tmp_path, rows[0], request, first),
        rows[1]["record_id"]: _bind_descriptor(tmp_path, rows[1], changed, second),
    }
    refs = _snapshots(tmp_path, rows, prepared=prepared,
                      scored={name: {r["record_id"] for r in rows} for name in diagnostic.ARMS})
    value = diagnostic.build(*refs)
    assert len(value["method_and_receptor_pocket_frame_groups"]) == 1
    assert value["four_arm_common_scored_ids"] == [r["record_id"] for r in rows]
    assert value["denominator"]["largest_common_method_and_frame_group_distinct_Ki_identities"] == 1
    assert [r["recorded_receptor_system_sha256"] for r in value["candidates"]] == [
        first["receptor_system_sha256"], second["receptor_system_sha256"]]
    assert "receptor_system_sha256" not in value["matching_frame_basis"]


@pytest.mark.parametrize("difference", [
    "protein_pdb", "protein_atomtypes", "protein_defaults", "topology_hash",
    "chain_order", "topology_order", "naming_convention", "pdb_element_policy",
])
def test_receptor_source_grouping_binds_ordered_topologies_and_parsing_policies(tmp_path, difference):
    row = _row(1, "Ki", method=True)
    prepared = _prepared(tmp_path, row)[0]["prepared_input"]
    prepared["schema_version"] = "prepared_gromacs_components_v2"
    first = prepared["protein_chains"][0].pop("molecule_itp")
    second = {**first, "sha256": "c" * 64}
    prepared["protein_chains"] = [
        {"chain_id": "A", "molecule_itps": [first, second]},
        {"chain_id": "B", "molecule_itps": [first]},
    ]
    changed = copy.deepcopy(prepared)
    if difference in {"protein_pdb", "protein_atomtypes", "protein_defaults"}:
        changed[difference]["sha256"] = "9" * 64
    elif difference == "topology_hash":
        changed["protein_chains"][0]["molecule_itps"][0]["sha256"] = "9" * 64
    elif difference == "chain_order":
        changed["protein_chains"].reverse()
    elif difference == "topology_order":
        changed["protein_chains"][0]["molecule_itps"].reverse()
    elif difference == "naming_convention":
        changed[difference] = "pdb_leading_digit_to_gromacs_suffix"
    else:
        changed[difference] = "pdb_blank_element_from_matching_topology_atomic_number"
    assert diagnostic._receptor_sources_sha256(prepared) != diagnostic._receptor_sources_sha256(changed)


def test_mutation_during_diagnostic_is_rejected_at_postflight(tmp_path, monkeypatch):
    refs = _snapshots(tmp_path, [_row(1, "Ki")])
    original = diagnostic._method_key

    def changed(row):
        path = tmp_path / "records.jsonl"
        path.write_bytes(path.read_bytes() + b" ")
        return original(row)

    monkeypatch.setattr(diagnostic, "_method_key", changed)
    with pytest.raises(ValueError, match="readiness_input_changed_during_read"):
        diagnostic.build(*refs)
