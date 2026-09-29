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


def _registered_documents(tmp_path, row):
    """Recorded synthetic v3 metadata only: molecular source paths do not exist."""
    identity = row["chemical_identity"]["canonical_isomeric_smiles_sha256"]
    files = {key: {"path": "/deliberately-unopened/" + key,
                   "sha256": "a" * 64 if key == "receptor" else identity}
             for key in diagnostic.REGISTERED_FILES}
    budget = {"candidate_count": 1, "top_k": 1, "max_torsions": 0,
              "translation_radius_angstrom": 0.0, "seed": 7, "max_refinement_steps": 32}
    request = {"schema_id": diagnostic.REGISTERED_REQUEST, "backend": "python_cpu_reference",
               **files, "solvation": None, "budget": budget, "receptor_margin_angstrom": 4.0,
               "solver": {"minimization": {"max_iterations": 32, "max_backtracks": 12,
                                            "force_tolerance_kcal_per_mol_angstrom": 0.001}},
               "comparison": {"mode": "same_candidates", "require_convergence_for_selection": True},
               "selection": {"top_k": 1},
               "pocket": {"center_angstrom": [0.0, 0.0, 0.0], "radius_angstrom": 10.0,
                          "coordinate_frame_id": "registered-frame"}}
    pose = {"schema_id": "cpu_registered_input_single_pose_receipt/1.0.0",
            "policy_id": diagnostic.REGISTERED_POLICY, "authority_input_receipt_sha256": "b" * 64,
            "coordinate_frame_id": "registered-frame", "source_ligand_system_sha256": identity,
            "candidate_id": "pose-0-" + identity[:8], "proposal_fingerprint_sha256": identity,
            **{k: v for k, v in budget.items() if k != "max_refinement_steps"}}
    pose["receipt_sha256"] = diagnostic._sha(pose)
    score_descriptor = {"score_id": "betelgeuze.cpu_explicit_graph_pose_scorer/1.0.0",
        "direction": "minimize", "unit": None,
        "semantics": "uncalibrated_dimensionless_explicit_graph_chemistry_pose_ordering_score",
        "calibrated": False, "reference_method": None,
        "applicability_domain_id": "authenticated_known_pocket_complete_explicit_chemical_graph_partial_charge_v1"}
    source = {"backend": diagnostic.REGISTERED_BACKEND, "request_sha256": diagnostic._sha(request),
              "input_files": files, "pose_budget": budget, "solver": request["solver"],
              "score_quantity": diagnostic.REGISTERED_SCORE, "score_descriptor": score_descriptor,
              "candidate_source_admission_verified": False, "scientifically_validated": False,
              "implementation_sha256": "b" * 64, "authority_sha256": "b" * 64,
              "parameters_sha256": "c" * 64, "cross_parameters_sha256": "d" * 64,
              "proposal_policy": pose,
              "evaluator": {"evaluator_id": "cpu_fixed_receptor_reference/1.0.0",
                            "parameter_fingerprint_sha256": "c" * 64, "cross_parameters_sha256": "d" * 64,
                            "receptor_system_sha256": "e" * 64, "solvation_fingerprint_sha256": None},
              "scorer": {"feature_model_id": "explicit_graph_hbond_features/1.0.0",
                         "context": "f" * 64, "config": "f" * 64, "backend": "f" * 64}}
    frame = {"schema_version": "native_v4_registered_prepared_cohort_v1", "target_chembl_id": "CHEMBL3371",
             "receptor_source_sha256": files["receptor"]["sha256"], "receptor_system_sha256": "e" * 64,
             "receptor_coordinates_sha256": "1" * 64, "receptor_construct_sha256": "2" * 64,
             "receptor_cross_parameters_sha256": "3" * 64, "cross_model_sha256": "4" * 64,
             "pocket_sha256": diagnostic._sha(request["pocket"]), "coordinate_frame_id": "registered-frame",
             "protocol_settings_sha256": diagnostic._sha({k: request[k] for k in (
                 "schema_id", "backend", "receptor_margin_angstrom", "budget", "solver", "comparison", "selection")})}
    descriptor = {"schema_version": diagnostic.REGISTERED_DESCRIPTOR,
        "record_id": row["record_id"], "assay_id": row["assay_id"],
        "metadata_origin_sha256": row["source_origins"]["metadata_origin"]["sha256"],
        "method_origin_sha256": row["source_origins"]["method_origin"]["sha256"],
        "target_annotation_sha256": diagnostic._sha(row["target_annotation"]), "target_chembl_id": "CHEMBL3371",
        "request_schema": diagnostic.REGISTERED_REQUEST, "request_sha256": diagnostic._sha(request),
        "source_files": files, "coordinate_frame_id": "registered-frame", "pocket_sha256": frame["pocket_sha256"],
        "charge_origin": {"path": "/deliberately-unopened/charge.json", "sha256": "5" * 64},
        "charge_policy": "openmm_xml_decimal_charge_sum_v1", "cohort": frame,
        "same_prepared_assay_state_verified": False, "source_authenticated": False, "scientifically_validated": False,
        "ligand": {"system_sha256": identity, "coordinates_sha256": "6" * 64, "atom_graph_sha256": "7" * 64,
                   "canonical_isomeric_smiles_sha256": identity, "formal_charge": 0, "atom_count": 3},
        "receptor": {"system_sha256": "e" * 64, "coordinates_sha256": "1" * 64,
                     "construct_sha256": "2" * 64, "atom_count": 8}}
    request, receipt = _bind_descriptor(tmp_path, row, request, descriptor)
    receipt.update(cohort=frame,
        ligand_net_charge_screen={"schema_version": "registered_openmm_ligand_net_charge_screen_v1",
            "profile": "openmm_system_xml_nonbonded_charge_tokens_v1", "status": "equal_as_encoded",
            "rank_eligible": True, "canonical_formal_charge_sum_e": 0,
            "openmm_printed_partial_charge_sum_e": "0.00", "difference_e": "0",
            "print_resolution_bound_e": "0.001", "maximum_rank_difference_e": "0.5",
            "charge_tokens_sha256": "8" * 64, "mapping_sha256": "9" * 64, "xml_sha256": "a" * 64,
            "scope": "synthetic recorded charge decision; no source opened"},
        pose_geometry_status={"requested": 1, "inside_declared_pocket": 1,
            "rank_eligible_inside_pocket": 1, "cross_distance_unavailable_inside_pocket": 0,
            "scope": "synthetic registered original pose"})
    return request, receipt, source


def _registered_summary(source, score=1.0):
    pose = source["proposal_policy"]
    return {"status": "evaluated", "reason": None, "score": score,
        "score_quantity": diagnostic.REGISTERED_SCORE, "score_descriptor": source["score_descriptor"],
        "proposal_policy_id": diagnostic.REGISTERED_POLICY,
        "selected_candidates": [{"variant": "baseline", "score": score, "pose_valid": True,
            "selection_eligible": True, "validity_complete": True, "candidate_id": pose["candidate_id"],
            "proposal_index": 0, "proposal_fingerprint_sha256": pose["proposal_fingerprint_sha256"]}],
        "refinement_attempts": 1, "refinement_failures": 0, "refinement_converged": 0,
        "original_selected_count": 1, "refined_selected_count": 0,
        "work": {"actual_force_evaluation_calls": 51, "failed_force_evaluation_calls": 0,
                 "score_evaluation_calls": 2, "force_evaluations_reserved": 417, "pose_candidates_in_both_arms": 2},
        "physical_affinity_computed": False, "candidate_source_admission_verified": False,
        "scientifically_validated": False}


def _reseal_registered(refs, frozen, result):
    binding = diagnostic._sha(frozen)
    result["binding"] = binding
    for arm in result["arms"].values():
        for row in arm["rows"]:
            if "binding" in row:
                row["binding"] = binding
        arm["completion"]["binding"] = binding
        if arm["worker_complete"] is not None:
            arm["worker_complete"]["binding"] = binding
    return (_write(Path(refs[0]["path"]), {"payload": frozen, "sha256": binding}),
            _write(Path(refs[1]["path"]), result))


def _registered_snapshots(tmp_path, *, rows=None):
    rows = rows or [_row(1, "Ki", "CCO", method=True), _row(2, "Ki", "CCN", method=True)]
    prepared = {r["record_id"]: _registered_documents(tmp_path, r) for r in rows}
    refs = _snapshots(tmp_path, rows, prepared=prepared,
                      scored={name: {r["record_id"] for r in rows} for name in diagnostic.ARMS})
    frozen = json.loads(Path(refs[0]["path"]).read_bytes())["payload"]
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    frozen["schema_version"] = diagnostic.REGISTERED_FROZEN
    frozen["protocol"]["schema_version"], result["schema_version"] = diagnostic.VERSIONS[diagnostic.REGISTERED_FROZEN]
    frozen["source_inputs"] = {rid: values[2] for rid, values in prepared.items()}
    frozen["registered_cohort"] = {"method_sha256": diagnostic._method_key(rows[0]),
                                   "frame": prepared[rows[0]["record_id"]][1]["cohort"]}
    for name, arm in result["arms"].items():
        if name != "similarity":
            arm["score_quantity"] = diagnostic.REGISTERED_SCORE
            for row in arm["rows"]:
                row["registered_summary"] = _registered_summary(frozen["source_inputs"][row["record_id"]])
                row["pose_report"] = {"path": f"{name}/{diagnostic._sha(row['record_id'])}.poses.json",
                                      "bytes": 1, "sha256": "e" * 64}
        reports = [] if name == "similarity" else [r["registered_summary"] for r in arm["rows"]]
        arm["registered_work"] = {
            "recorded_call_counters": {key: sum(r["work"][key] for r in reports) for key in (
                "actual_force_evaluation_calls", "failed_force_evaluation_calls", "score_evaluation_calls",
                "force_evaluations_reserved", "pose_candidates_in_both_arms")},
            "candidate_reports": len(reports), "candidate_calls_without_returned_report": 0,
            "all_candidate_molecular_work_recorded": True}
    return _reseal_registered(refs, frozen, result)


def test_v3_records_d3_fallback_separately_from_cross_energy_without_opening_molecular_inputs(tmp_path):
    refs = _registered_snapshots(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    value = diagnostic.build(*refs)
    assert value["four_arm_common_scored_ids"] == ["chembl:activity:1", "chembl:activity:2"]
    assert value["denominator"]["largest_common_method_and_frame_group_distinct_Ki_identities"] == 2
    assert value["arms"]["engine"]["score_quantity"] == diagnostic.REGISTERED_SCORE
    assert value["arms"]["similarity"]["score_quantity"] == "predicted_negative_log10_molar_endpoint"
    rows = value["arms"]["engine"]["recorded_registered_observations"]
    assert all(r["original_selected_count"] == 1 and r["refinement_converged"] == 0 for r in rows.values())
    work = value["arms"]["engine"]["recorded_registered_work"]
    assert work["candidate_reports"] == 2
    assert work["recorded_call_counters"]["actual_force_evaluation_calls"] == 102
    assert value["registered_candidate_reports_reverified"] is False
    assert value["registered_charge_origin_rederived"] is False
    assert value["registered_initial_pose_status_recomputed"] is False
    assert value["engine_calls_performed"] == 0
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("change,reason", [
    ("cross_score_unit", "readiness_score_quantity_mismatch"),
    ("summary_score", "readiness_registered_summary_mismatch"),
    ("summary_missing", "readiness_registered_summary_missing"),
    ("summary_affinity", "readiness_registered_summary_mismatch"),
    ("refined_without_convergence", "readiness_registered_nonconverged_refinement_selected"),
    ("force_over_budget", "readiness_registered_work_denominator_mismatch"),
    ("wrong_selected_candidate", "readiness_registered_selection_mismatch"),
    ("similarity_summary", "readiness_similarity_has_registered_summary"),
    ("cross_wired_report", "readiness_registered_report_reference_mismatch"),
    ("aggregate_work", "readiness_registered_arm_work_mismatch"),
])
def test_resealed_v3_result_cannot_change_units_selection_or_costs(tmp_path, change, reason):
    refs = _registered_snapshots(tmp_path)
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    arm = result["arms"]["engine"]
    row = arm["rows"][0]
    summary = row["registered_summary"]
    if change == "cross_score_unit":
        arm["score_quantity"] = "existing_cross_only_kcal_per_mol"
    elif change == "summary_score":
        summary["score"] = 9.0
    elif change == "summary_missing":
        del row["registered_summary"]
    elif change == "summary_affinity":
        summary["physical_affinity_computed"] = True
    elif change == "refined_without_convergence":
        summary.update(original_selected_count=0, refined_selected_count=1)
        summary["selected_candidates"][0]["variant"] = "refined"
    elif change == "force_over_budget":
        summary["work"]["actual_force_evaluation_calls"] = 418
    elif change == "wrong_selected_candidate":
        summary["selected_candidates"][0]["candidate_id"] = "other-candidate"
    elif change == "similarity_summary":
        result["arms"]["similarity"]["rows"][0]["registered_summary"] = summary
    elif change == "cross_wired_report":
        row["pose_report"]["path"] = arm["rows"][1]["pose_report"]["path"]
    else:
        arm["registered_work"]["recorded_call_counters"]["actual_force_evaluation_calls"] = 0
    refs = refs[0], _write(Path(refs[1]["path"]), result)
    with pytest.raises(ValueError, match=reason):
        diagnostic.build(*refs)


@pytest.mark.parametrize("change,reason", [
    ("cohort_method", "readiness_registered_strict_method_or_frame_mismatch"),
    ("cohort_frame", "readiness_registered_strict_method_or_frame_mismatch"),
    ("request_hash", "readiness_registered_input_binding_mismatch"),
    ("input_file", "readiness_registered_input_binding_mismatch"),
    ("pose_receipt", "readiness_registered_original_pose_binding_mismatch"),
    ("source_unit", "readiness_registered_score_descriptor_mismatch"),
    ("source_identity", "readiness_registered_ligand_or_receptor_binding_mismatch"),
    ("binding_cohort", "readiness_recorded_registered_binding_mismatch"),
    ("charge", "readiness_registered_charge_status_mismatch"),
    ("pose", "readiness_registered_initial_pose_status_mismatch"),
])
def test_resealed_v3_frozen_scope_and_binding_tampering_fails_closed(tmp_path, change, reason):
    refs = _registered_snapshots(tmp_path)
    frozen = json.loads(Path(refs[0]["path"]).read_bytes())["payload"]
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    rid = frozen["pool"][0]
    source, receipt = frozen["source_inputs"][rid], frozen["prepared_bindings"][rid]
    if change == "cohort_method":
        frozen["registered_cohort"]["method_sha256"] = "0" * 64
    elif change == "cohort_frame":
        frozen["registered_cohort"]["frame"]["cross_model_sha256"] = "0" * 64
    elif change == "request_hash":
        source["request_sha256"] = "0" * 64
    elif change == "input_file":
        source["input_files"]["extensions"]["sha256"] = "0" * 64
    elif change == "pose_receipt":
        source["proposal_policy"]["receipt_sha256"] = "0" * 64
    elif change == "source_unit":
        source["score_descriptor"]["unit"] = "kcal/mol"
    elif change == "source_identity":
        source["proposal_policy"]["source_ligand_system_sha256"] = "0" * 64
        source["proposal_policy"]["receipt_sha256"] = diagnostic._sha({
            k: v for k, v in source["proposal_policy"].items() if k != "receipt_sha256"})
    elif change == "binding_cohort":
        receipt["cohort"]["protocol_settings_sha256"] = "0" * 64
    elif change == "charge":
        receipt["ligand_net_charge_screen"]["rank_eligible"] = False
    else:
        receipt["pose_geometry_status"]["rank_eligible_inside_pocket"] = 0
    with pytest.raises(ValueError, match=reason):
        diagnostic.build(*_reseal_registered(refs, frozen, result))


def test_v3_does_not_admit_one_identity_under_two_record_ids(tmp_path):
    rows = [_row(1, "Ki", "CCO", method=True), _row(2, "Ki", "CCO", method=True)]
    with pytest.raises(ValueError, match="readiness_registered_two_distinct_Ki_identities_required"):
        diagnostic.build(*_registered_snapshots(tmp_path, rows=rows))


def test_v3_different_recorded_methods_are_rejected_instead_of_merely_split_into_groups(tmp_path):
    rows = [_row(1, "Ki", "CCO", method=True), _row(2, "Ki", "CCN", method=True)]
    rows[1]["method_evidence"]["description"] += " different incubation"
    with pytest.raises(ValueError, match="readiness_registered_strict_method_or_frame_mismatch"):
        diagnostic.build(*_registered_snapshots(tmp_path, rows=rows))


@pytest.mark.parametrize("known_calls", [True, False])
def test_v3_call_without_report_keeps_missing_molecular_work_unknown(tmp_path, known_calls):
    refs = _registered_snapshots(tmp_path)
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    arm = result["arms"]["engine"]
    row = arm["rows"][1]
    row.update(status="failed", score=None, reason="synthetic evaluation failure")
    del row["registered_summary"], row["pose_report"]
    arm["denominator"] = {"requested": 2, "evaluated": 1, "failed": 1}
    arm["ranked_record_ids"] = [arm["rows"][0]["record_id"]]
    arm["registered_work"] = {
        "recorded_call_counters": arm["rows"][0]["registered_summary"]["work"],
        "candidate_reports": 1, "candidate_calls_without_returned_report": 1 if known_calls else None,
        "all_candidate_molecular_work_recorded": False}
    if not known_calls:
        arm["worker_complete"] = None
        arm["completion"]["status"] = "worker_failed"
    value = diagnostic.build(refs[0], _write(Path(refs[1]["path"]), result))
    observed = value["arms"]["engine"]["recorded_registered_work"]
    assert observed["all_candidate_molecular_work_recorded"] is False
    assert observed["candidate_calls_without_returned_report"] == (1 if known_calls else None)
    assert observed["recorded_call_counters"]["actual_force_evaluation_calls"] == 51
    assert value["denominator"]["four_arm_common_scored_records"] == 1


@pytest.mark.parametrize("difference", ["-0.0001", "0.0001"])
def test_v3_charge_screen_retains_signed_decimal_difference(tmp_path, difference):
    refs = _registered_snapshots(tmp_path)
    frozen = json.loads(Path(refs[0]["path"]).read_bytes())["payload"]
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    for receipt in frozen["prepared_bindings"].values():
        receipt["ligand_net_charge_screen"].update(
            status="within_print_resolution", openmm_printed_partial_charge_sum_e=difference,
            difference_e=difference)
    assert diagnostic.build(*_reseal_registered(refs, frozen, result))["status"] == "diagnostic_only"


@pytest.mark.parametrize("difference,resolution", [("0", "0.5"), ("-0.0001", "0.00001"), ("NaN", "0.001")])
def test_v3_resealed_charge_rounding_claim_cannot_override_recorded_gate(tmp_path, difference, resolution):
    refs = _registered_snapshots(tmp_path)
    frozen = json.loads(Path(refs[0]["path"]).read_bytes())["payload"]
    result = json.loads(Path(refs[1]["path"]).read_bytes())
    receipt = frozen["prepared_bindings"][frozen["pool"][0]]
    receipt["ligand_net_charge_screen"].update(
        status="equal_as_encoded" if difference == "0" else "within_print_resolution",
        openmm_printed_partial_charge_sum_e=difference, difference_e=difference,
        print_resolution_bound_e=resolution)
    with pytest.raises(ValueError, match="readiness_registered_charge_status_mismatch"):
        diagnostic.build(*_reseal_registered(refs, frozen, result))


def test_resealed_v3_descriptor_cannot_substitute_another_ligand_identity(tmp_path, monkeypatch):
    original = _registered_documents

    def changed(directory, row):
        request, receipt, source = original(directory, row)
        if row["record_id"] == "chembl:activity:1":
            path = Path(row["source_origins"]["prepared_state_origin"]["path"])
            descriptor = json.loads(path.read_bytes())
            descriptor["ligand"]["canonical_isomeric_smiles_sha256"] = "0" * 64
            ref = _write(path, descriptor)
            row["source_origins"]["prepared_state_origin"] = ref
            receipt.update(origin_sha256=ref["sha256"], observation_sha256=diagnostic._sha(descriptor))
        return request, receipt, source

    monkeypatch.setitem(globals(), "_registered_documents", changed)
    with pytest.raises(ValueError, match="readiness_registered_ligand_or_receptor_binding_mismatch"):
        diagnostic.build(*_registered_snapshots(tmp_path))


def test_v3_cli_isolated_execution_never_imports_product_or_physics(tmp_path):
    refs = _registered_snapshots(tmp_path)
    script = Path(diagnostic.__file__)
    harness = """import importlib.abc, runpy, sys
class NoPhysics(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'betelgeuze_product', 'betelgeuze_engine', 'betelgeuze_engine_v2', 'torch', 'numpy', 'rdkit', 'openmm'}:
            raise AssertionError('forbidden scientific import: ' + fullname)
sys.meta_path.insert(0, NoPhysics())
script = sys.argv.pop(1)
runpy.run_path(script, run_name='__main__')
"""
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", harness, str(script),
        "--frozen", refs[0]["path"], "--frozen-sha256", refs[0]["sha256"],
        "--comparison", refs[1]["path"], "--comparison-sha256", refs[1]["sha256"]],
        capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["status"] == "diagnostic_only"
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}
