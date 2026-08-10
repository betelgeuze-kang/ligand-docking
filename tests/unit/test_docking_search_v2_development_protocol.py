from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.docking_search_v2 import (
    EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
    FROZEN_ALLOCATION_RECEIPT_SHA256,
    FROZEN_PROTOCOL_SHA256,
    RESULT_SCHEMA_ID,
    ProtocolError,
    canonical_json_bytes,
    evaluate_development_result,
    frozen_allocation_receipt,
    frozen_protocol,
    verify_evidence_receipt,
)
from benchmarks.docking_search_v2.protocol import (
    CASE_IDS,
    EXTERNAL_RMSD_FACT_ORIGIN,
    GENERATION_POLICY_ID,
    KNOWN_POCKET_POLICY_ID,
    NATIVE_EXTENSION_VERSION,
    PREPARATION_FAILURE_CASE_ID,
    PREPARATION_FAILURE_CODE,
    SEARCH_CRATE_ID,
    SCORED_CASE_IDS,
    SOURCE_ARCHIVE_SHA256,
    _CASE_BY_ID,
)
from benchmarks.docking_search_v2 import protocol as protocol_module
from tools.benchmarking.build_docking_search_v2_development_evidence import main


def _digest(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _seal(value: dict[str, object]) -> dict[str, object]:
    return {
        **value,
        "receipt_sha256": hashlib.sha256(canonical_json_bytes(value)).hexdigest(),
    }


def _native_backend_receipt() -> dict[str, object]:
    return _seal(
        {
            "schema_id": protocol_module.NATIVE_BACKEND_RECEIPT_SCHEMA_ID,
            "backend_id": "rust_cpu_required",
            "backend_version": protocol_module.NATIVE_BACKEND_VERSION,
            "distribution_version": NATIVE_EXTENSION_VERSION,
            "extension_sha256": protocol_module.FROZEN_NATIVE_EXTENSION_SHA256,
            "cargo_lock_sha256": protocol_module.FROZEN_NATIVE_CARGO_LOCK_SHA256,
            "native_source_closure_sha256": (
                protocol_module.FROZEN_NATIVE_SOURCE_CLOSURE_SHA256
            ),
            "native_source_closure_file_count": 17,
            "rustc_version": protocol_module.NATIVE_RUSTC_VERSION,
            "target_triple": protocol_module.NATIVE_TARGET_TRIPLE,
            "build_profile": "release",
            "opt_level": "3",
            "debug": "false",
            "panic_strategy": "abort",
            "build_flags": protocol_module.NATIVE_BUILD_FLAGS,
            "cargo_features": "extension-module",
            "docking_search_schema_id": protocol_module.NATIVE_CORE_SCHEMA_ID,
            "docking_search_receipt_schema_id": (
                protocol_module.NATIVE_CORE_RECEIPT_SCHEMA_ID
            ),
            "docking_search_evaluator_id": protocol_module.NATIVE_EVALUATOR_ID,
            "implicit_fallback_allowed": False,
            "test_double": False,
        }
    )


def _native_search_receipt(case_id: str) -> dict[str, object]:
    row: dict[str, object] = {
        name: _digest("native-search", case_id, name)
        for name in protocol_module._NATIVE_SEARCH_RECEIPT_DIGEST_KEYS
    }
    row.update(
        {name: 0 for name in protocol_module._NATIVE_SEARCH_RECEIPT_INTEGER_KEYS}
    )
    row.update(
        {
            "schema_id": protocol_module.NATIVE_CORE_RECEIPT_SCHEMA_ID,
            "evaluator_id": protocol_module.NATIVE_EVALUATOR_ID,
            "result_independent_allocation": True,
            "placement_mode": "single_anchor_fallback",
            "requested_orientation_count": 64,
            "accepted_orientation_count": 64,
            "compatible_single_anchor_pair_count": 1,
            "used_anchor_combination_count": 1,
            "possible_candidate_slot_count": 64,
            "generated_candidate_limit": 64,
            "allocated_candidate_slot_count": 64,
        }
    )
    return row


def _result(*, passing: bool = True) -> dict[str, object]:
    top1_valid_cases = set(SCORED_CASE_IDS[:4]) if passing else set()
    recovery_cases = {"5SD5_HWI", "6T88_MWQ"} if passing else set()
    cases: list[dict[str, object]] = []
    for case_id in CASE_IDS:
        frozen = _CASE_BY_ID[case_id]
        generation_input_receipt = _digest("generation-input", case_id)
        known_pocket_receipt = _digest("known-pocket", case_id)
        if case_id == PREPARATION_FAILURE_CASE_ID:
            cases.append(
                {
                    "case_id": case_id,
                    "source_receipt_sha256": frozen.source_receipt_sha256,
                    "generation_input_receipt_sha256": generation_input_receipt,
                    "known_pocket_receipt_sha256": known_pocket_receipt,
                    "search_receipt_sha256": None,
                    "search_receipt": None,
                    "rank_receipt": None,
                    "evaluation_receipt": None,
                    "preparation_status": "failed",
                    "preparation_failure_code": PREPARATION_FAILURE_CODE,
                    "candidates": [],
                }
            )
            continue
        candidates = []
        for slot in range(64):
            exact_valid = slot == 0 and case_id in top1_valid_cases
            proposal_artifact = _digest("proposal-artifact", case_id, slot)
            coordinate = _digest("coordinate", case_id, slot)
            native_coordinate = _digest("native-coordinate", case_id, slot)
            native_row = _digest("native-row", case_id, slot)
            candidates.append(
                {
                    "slot_index": slot,
                    "score_rank": slot + 1,
                    "search_status": (
                        "retained_top_k" if slot < 10 else "clustered_out"
                    ),
                    "search_failure_code": None,
                    "proposal_artifact_sha256": proposal_artifact,
                    "coordinate_sha256": coordinate,
                    "native_coordinate_sha256": native_coordinate,
                    "native_row_sha256": native_row,
                    "candidate_search_receipt_sha256": "",
                    "rmsd_angstrom": (
                        1.5 if slot == 0 and case_id in recovery_cases else 5.0
                    ),
                    "rmsd_fact_origin": EXTERNAL_RMSD_FACT_ORIGIN,
                    "rmsd_subject_proposal_artifact_sha256": proposal_artifact,
                    "rmsd_subject_coordinate_sha256": coordinate,
                    "rmsd_fact_receipt_sha256": "",
                    "posebusters_exact_valid": exact_valid,
                    "posebusters_fact_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
                    "posebusters_subject_proposal_artifact_sha256": (proposal_artifact),
                    "posebusters_subject_coordinate_sha256": coordinate,
                    "posebusters_fact_receipt_sha256": "",
                }
            )
        rank_receipt = _seal(
            {
                "schema_id": protocol_module.RANK_RECEIPT_SCHEMA_ID,
                "case_id": case_id,
                "policy_id": protocol_module.RANK_POLICY_ID,
                "candidate_count": 64,
                "ranked_candidates": [
                    {
                        "score_rank": candidate["score_rank"],
                        "slot_index": candidate["slot_index"],
                        "native_row_sha256": candidate["native_row_sha256"],
                    }
                    for candidate in candidates
                ],
                "oracle_fields_used": [],
                "native_fields_used": [
                    "final_rank",
                    "energy_kcal_per_mol",
                    "detailed_score",
                    "coarse_score",
                    "slot_index",
                ],
            }
        )
        native_search_receipt = _native_search_receipt(case_id)
        backend = _native_backend_receipt()
        search_receipt = _seal(
            {
                "schema_id": protocol_module.SEARCH_BINDING_SCHEMA_ID,
                "case_id": case_id,
                "generation_policy_id": GENERATION_POLICY_ID,
                "generation_input_receipt_sha256": generation_input_receipt,
                "known_pocket_receipt_sha256": known_pocket_receipt,
                "search_config_sha256": _digest("search-config"),
                "search_implementation_sha256": (
                    protocol_module.FROZEN_NATIVE_SOURCE_CLOSURE_SHA256
                ),
                "native_extension_sha256": (
                    protocol_module.FROZEN_NATIVE_EXTENSION_SHA256
                ),
                "native_backend_receipt_sha256": backend["receipt_sha256"],
                "native_search_receipt_sha256": hashlib.sha256(
                    canonical_json_bytes(native_search_receipt)
                ).hexdigest(),
                "native_search_receipt": native_search_receipt,
                "native_result_sha256": _digest("native-result", case_id),
                "rank_receipt_sha256": rank_receipt["receipt_sha256"],
                "candidate_count": 64,
                "candidate_subjects": [
                    {
                        name: candidate[name]
                        for name in (
                            "slot_index",
                            "proposal_artifact_sha256",
                            "coordinate_sha256",
                            "native_coordinate_sha256",
                            "native_row_sha256",
                            "score_rank",
                            "search_status",
                            "search_failure_code",
                        )
                    }
                    for candidate in candidates
                ],
                "external_solver_used": False,
                "rmsd_used_for_ranking": False,
                "posebusters_used_for_ranking": False,
            }
        )
        evaluator_identity = {
            "evaluator_id": protocol_module.POSEBUSTERS_EVALUATOR_ID,
            "posebusters_version": protocol_module.POSEBUSTERS_VERSION,
            "rmsd_method_id": protocol_module.POSEBUSTERS_RMSD_METHOD_ID,
            "full_report": True,
            "implementation_source_sha256": (
                protocol_module.FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256
            ),
            "external_solver_used_for_generation": False,
        }
        columns = ["rmsd", *protocol_module.POSEBUSTERS_CHECK_IDS]
        fact_sidecars = []
        for candidate in candidates:
            slot = candidate["slot_index"]
            check_facts = {
                check_id: candidate["posebusters_exact_valid"]
                for check_id in protocol_module.POSEBUSTERS_CHECK_IDS
            }
            rmsd_fact = _seal(
                {
                    "schema_id": protocol_module.RMSD_FACT_SCHEMA_ID,
                    "case_id": case_id,
                    "slot_index": slot,
                    "origin": EXTERNAL_RMSD_FACT_ORIGIN,
                    "proposal_artifact_sha256": candidate["proposal_artifact_sha256"],
                    "coordinate_sha256": candidate["coordinate_sha256"],
                    "rmsd_angstrom": candidate["rmsd_angstrom"],
                    "evaluator_identity": evaluator_identity,
                }
            )
            posebusters_fact = _seal(
                {
                    "schema_id": protocol_module.POSEBUSTERS_FACT_SCHEMA_ID,
                    "case_id": case_id,
                    "slot_index": slot,
                    "origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
                    "proposal_artifact_sha256": candidate["proposal_artifact_sha256"],
                    "coordinate_sha256": candidate["coordinate_sha256"],
                    "posebusters_exact_valid": candidate["posebusters_exact_valid"],
                    "chemical_check_ids": list(
                        protocol_module.POSEBUSTERS_CHEMICAL_CHECK_IDS
                    ),
                    "geometric_check_ids": list(
                        protocol_module.POSEBUSTERS_GEOMETRIC_CHECK_IDS
                    ),
                    "check_facts": check_facts,
                    "full_report_columns": columns,
                    "full_report_facts": {
                        "rmsd": candidate["rmsd_angstrom"],
                        **check_facts,
                    },
                    "evaluator_identity": evaluator_identity,
                }
            )
            candidate["candidate_search_receipt_sha256"] = search_receipt[
                "receipt_sha256"
            ]
            candidate["rmsd_fact_receipt_sha256"] = rmsd_fact["receipt_sha256"]
            candidate["posebusters_fact_receipt_sha256"] = posebusters_fact[
                "receipt_sha256"
            ]
            fact_sidecars.append(
                {
                    "slot_index": slot,
                    "native_coordinate_sha256": candidate["native_coordinate_sha256"],
                    "rmsd_fact": rmsd_fact,
                    "posebusters_fact": posebusters_fact,
                }
            )
        batch_receipt = _seal(
            {
                "schema_id": protocol_module.EVALUATION_BATCH_SCHEMA_ID,
                "case_id": case_id,
                "candidate_count": 64,
                "report_columns": columns,
                "candidate_fact_receipt_sha256s": [
                    {
                        "slot_index": fact["slot_index"],
                        "rmsd_fact_receipt_sha256": fact["rmsd_fact"]["receipt_sha256"],
                        "posebusters_fact_receipt_sha256": fact["posebusters_fact"][
                            "receipt_sha256"
                        ],
                    }
                    for fact in fact_sidecars
                ],
                "evaluator_identity": evaluator_identity,
            }
        )
        evaluation_receipt = _seal(
            {
                "schema_id": protocol_module.EVALUATION_SIDECAR_SCHEMA_ID,
                "case_id": case_id,
                "batch_receipt": batch_receipt,
                "candidate_facts": fact_sidecars,
            }
        )
        cases.append(
            {
                "case_id": case_id,
                "source_receipt_sha256": frozen.source_receipt_sha256,
                "generation_input_receipt_sha256": generation_input_receipt,
                "known_pocket_receipt_sha256": known_pocket_receipt,
                "search_receipt_sha256": search_receipt["receipt_sha256"],
                "search_receipt": search_receipt,
                "rank_receipt": rank_receipt,
                "evaluation_receipt": evaluation_receipt,
                "preparation_status": "success",
                "preparation_failure_code": None,
                "candidates": candidates,
            }
        )
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "roster_sha256": frozen_protocol()["source"]["ordered_roster_sha256"],
        "allocation": frozen_allocation_receipt(),
        "implementation": {
            "engine_id": "betelgeuze",
            "search_crate_id": SEARCH_CRATE_ID,
            "search_implementation_sha256": (
                protocol_module.FROZEN_NATIVE_SOURCE_CLOSURE_SHA256
            ),
            "native_extension_version": NATIVE_EXTENSION_VERSION,
            "native_extension_sha256": protocol_module.FROZEN_NATIVE_EXTENSION_SHA256,
            "native_backend_receipt": _native_backend_receipt(),
            "generation_backend": "betelgeuze_rust_native",
            "external_solver_used": False,
        },
        "generation_boundary": {
            "policy_id": GENERATION_POLICY_ID,
            "known_pocket_policy_id": KNOWN_POCKET_POLICY_ID,
            "fixed_candidate_slots_per_scored_case": 64,
            "search_config_sha256": _digest("search-config"),
            "allocation_sealed_before_results": True,
            "result_dependent_allocation": False,
            "external_solver_used": False,
            "full_reference_pose_used_by_search": False,
            "rmsd_used_by_search": False,
            "posebusters_used_by_search": False,
            "baseline_outcomes_used_by_search": False,
            "known_pocket_derived_from_reference_before_search": True,
            "allowed_generation_input_roles": [
                "authenticated_protein_structure",
                "authenticated_ligand_start_conformer",
                "predeclared_known_pocket",
                "public_force_field_parameters",
            ],
        },
        "cases": cases,
        "claim_boundary": {
            "development_only": True,
            "retrospective": True,
            "product_dispatch_authorized": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientific_validation_claimed": False,
        },
    }


def _case(result: dict[str, object], case_id: str) -> dict[str, object]:
    return next(row for row in result["cases"] if row["case_id"] == case_id)


def _reseal_in_place(value: dict[str, object]) -> None:
    projection = {key: item for key, item in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(projection)
    ).hexdigest()


def _reseal_search_case(result: dict[str, object], case_id: str) -> None:
    case = _case(result, case_id)
    search = case["search_receipt"]
    search["candidate_subjects"] = [
        {
            name: candidate[name]
            for name in (
                "slot_index",
                "proposal_artifact_sha256",
                "coordinate_sha256",
                "native_coordinate_sha256",
                "native_row_sha256",
                "score_rank",
                "search_status",
                "search_failure_code",
            )
        }
        for candidate in case["candidates"]
    ]
    _reseal_in_place(search)
    case["search_receipt_sha256"] = search["receipt_sha256"]
    for candidate in case["candidates"]:
        candidate["candidate_search_receipt_sha256"] = search["receipt_sha256"]


def _replace_external_fact(
    result: dict[str, object],
    case_id: str,
    slot: int,
    *,
    rmsd: float | None = None,
    exact_valid: bool | None = None,
) -> None:
    case = _case(result, case_id)
    candidate = case["candidates"][slot]
    sidecar = case["evaluation_receipt"]
    facts = sidecar["candidate_facts"][slot]
    if rmsd is not None:
        candidate["rmsd_angstrom"] = rmsd
        facts["rmsd_fact"]["rmsd_angstrom"] = rmsd
        facts["posebusters_fact"]["full_report_facts"]["rmsd"] = rmsd
    if exact_valid is not None:
        candidate["posebusters_exact_valid"] = exact_valid
        pose = facts["posebusters_fact"]
        pose["posebusters_exact_valid"] = exact_valid
        pose["check_facts"] = {
            check_id: exact_valid for check_id in protocol_module.POSEBUSTERS_CHECK_IDS
        }
        for check_id in protocol_module.POSEBUSTERS_CHECK_IDS:
            pose["full_report_facts"][check_id] = exact_valid
    _reseal_in_place(facts["rmsd_fact"])
    _reseal_in_place(facts["posebusters_fact"])
    candidate["rmsd_fact_receipt_sha256"] = facts["rmsd_fact"]["receipt_sha256"]
    candidate["posebusters_fact_receipt_sha256"] = facts["posebusters_fact"][
        "receipt_sha256"
    ]
    batch = sidecar["batch_receipt"]
    batch["candidate_fact_receipt_sha256s"][slot] = {
        "slot_index": slot,
        "rmsd_fact_receipt_sha256": facts["rmsd_fact"]["receipt_sha256"],
        "posebusters_fact_receipt_sha256": facts["posebusters_fact"]["receipt_sha256"],
    }
    _reseal_in_place(batch)
    _reseal_in_place(sidecar)


def test_frozen_protocol_binds_exact_roster_sources_baselines_and_diagnostics() -> None:
    protocol = frozen_protocol()
    assert protocol["protocol_sha256"] == FROZEN_PROTOCOL_SHA256
    assert protocol["source"] == {
        "dataset": "PoseBusters",
        "source_archive_sha256": (
            "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
        ),
        "ordered_roster_sha256": (
            "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
        ),
        "molecular_structures_embedded": False,
        "archive_embedded": False,
    }
    assert protocol["cohort"]["ordered_case_ids"] == list(CASE_IDS)
    assert protocol["cohort"]["ordered_scored_case_ids"] == list(SCORED_CASE_IDS)
    rows = {row["case_id"]: row for row in protocol["cohort"]["cases"]}
    assert rows["5SD5_HWI"]["baseline_oracle_minimum_rmsd_angstrom"] == 4.281296
    assert rows["6T88_MWQ"]["baseline_oracle_minimum_rmsd_angstrom"] == 1.576141
    assert rows["6T88_MWQ"]["baseline_exact_valid_candidate_count"] == 4
    assert rows["6VTA_AKN"]["baseline_exact_valid_candidate_count"] == 2
    assert rows["6WTN_RXT"]["baseline_exact_valid_candidate_count"] == 1
    assert rows["6M73_FNR"]["preparation_failure_code"] == PREPARATION_FAILURE_CODE
    assert rows["5SD5_HWI"]["rigid_lower_bound_rmsd_angstrom"] == 1.4805
    assert {case_id: row["source_receipt_sha256"] for case_id, row in rows.items()} == {
        "5SD5_HWI": "120d4d28e04604941b93b17d491682526b977971777db53bf964d1d5d2a12dfb",
        "5SIS_JSM": "92a2bfadcf27ec61a620e387aa8e21ac87ae4e09e15c4a0c2035c4de538c2201",
        "6M2B_EZO": "d9702520e85a459ae1e5fc4843bcd88c05dd0c3f316258971f3e61859088ec4e",
        "6M73_FNR": "fdf1646d366a4adad31ed9ef973e53cf576d07f22aff03b0c486baaf353eb07e",
        "6T88_MWQ": "82e4ad0942b85141a5f17b5a5c36744e40fe4ce863d4006ef29801d377bd5f06",
        "6TW5_9M2": "076e1fa07a885cd231a557162f73c2f56912a7a6d237d3f4972b12ff59ebef9e",
        "6TW7_NZB": "521cb3fa141424e0d7b57bfc667718b305e1cd8f02f12ac05ddffe264b76d6d1",
        "6VTA_AKN": "79d66ad929ee3c38b4f6af120167bd9bb719fe393534d74733268197611498a2",
        "6WTN_RXT": "35f47abe5e7ea517fa08a90a1a301d1672dba5a5e18c7cbf2211f21032b97adf",
    }
    assert all(
        row["rigid_lower_bound_role"] == "frozen_diagnostic_fact_not_gate_truth"
        for row in rows.values()
    )
    assert protocol["gate"]["rigid_lower_bounds_used_for_gate"] is False
    assert protocol["scope"]["product_dispatch_authority"] is False
    assert protocol["scope"]["public_claim_eligible"] is False


def test_fixed_allocation_is_exactly_eight_cases_times_64_and_result_independent() -> (
    None
):
    allocation = frozen_allocation_receipt()
    assert allocation["allocation_receipt_sha256"] == FROZEN_ALLOCATION_RECEIPT_SHA256
    assert allocation["scored_case_ids"] == list(SCORED_CASE_IDS)
    assert allocation["candidate_slots_per_scored_case"] == 64
    assert allocation["total_candidate_budget"] == 512
    assert allocation["sealed_before_results"] is True
    assert allocation["result_dependent"] is False
    assert allocation["result_fields_used"] == []


def test_passing_evidence_rederives_all_frozen_development_gates() -> None:
    result = _result()
    receipt = evaluate_development_result(result)
    verified = verify_evidence_receipt(receipt, result)
    summary = verified["summary"]
    assert verified["decision"] == "pass"
    assert summary["proposal_oracle_recovered_case_ids"] == [
        "5SD5_HWI",
        "6T88_MWQ",
    ]
    assert summary["new_previously_uncovered_exact_valid_recovered_case_ids"] == [
        "5SD5_HWI"
    ]
    assert summary["invalid_top1_case_count"] == 4
    assert summary["preserved_6T88"] is True
    assert all(summary["gates"].values())
    assert verified["claim_boundary"]["product_promotion_eligible"] is False
    assert (
        verified["external_fact_boundary"]["posebusters_validity_computed_here"]
        is False
    )


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value.__setitem__("protocol_sha256", "0" * 64),
            "protocol_hash_mismatch",
        ),
        (
            lambda value: value.__setitem__("source_archive_sha256", "0" * 64),
            "source_archive_mismatch",
        ),
        (
            lambda value: _case(value, "5SD5_HWI").__setitem__(
                "source_receipt_sha256", "0" * 64
            ),
            "source_receipt_mismatch",
        ),
    ],
)
def test_source_or_protocol_tampering_fails_closed(mutation, code: str) -> None:
    result = _result()
    mutation(result)
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == code


def test_missing_case_or_candidate_fails_closed() -> None:
    missing_case = _result()
    missing_case["cases"].pop()
    with pytest.raises(ProtocolError, match="case_count_mismatch"):
        evaluate_development_result(missing_case)

    missing_candidate = _result()
    _case(missing_candidate, "5SD5_HWI")["candidates"].pop()
    with pytest.raises(ProtocolError, match="candidate_budget_mismatch"):
        evaluate_development_result(missing_candidate)


def test_changed_or_result_dependent_allocation_fails_closed() -> None:
    result = _result()
    result["allocation"]["result_dependent"] = True
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "allocation_receipt_mismatch"

    result = _result()
    result["allocation"]["candidate_slots_per_scored_case"] = 63
    with pytest.raises(ProtocolError, match="allocation_receipt_mismatch"):
        evaluate_development_result(result)


def test_posebusters_validity_must_be_an_external_receipted_fact() -> None:
    result = _result()
    candidate = _case(result, "5SD5_HWI")["candidates"][0]
    candidate["posebusters_fact_origin"] = "computed_in_product"
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "posebusters_fact_not_external"

    result = _result()
    _case(result, "5SD5_HWI")["candidates"][0]["posebusters_fact_receipt_sha256"] = (
        "missing"
    )
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "invalid_sha256"


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("rmsd_subject_coordinate_sha256", "rmsd_subject_mismatch"),
        (
            "posebusters_subject_proposal_artifact_sha256",
            "posebusters_subject_mismatch",
        ),
    ],
)
def test_external_facts_must_bind_the_exact_proposal(field: str, code: str) -> None:
    result = _result()
    _case(result, "5SD5_HWI")["candidates"][0][field] = "0" * 64
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == code


def test_native_implementation_and_no_feedback_boundary_fail_closed() -> None:
    external = _result()
    external["implementation"]["external_solver_used"] = True
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(external)
    assert captured.value.code == "external_solver_generation_forbidden"

    feedback = _result()
    feedback["generation_boundary"]["posebusters_used_by_search"] = True
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(feedback)
    assert captured.value.code == "generation_boundary_changed"


def test_native_backend_receipt_schema_excludes_install_path() -> None:
    result = _result()
    backend = result["implementation"]["native_backend_receipt"]
    assert "extension_path" not in backend
    backend["extension_path"] = "/environment-specific/native-extension.so"
    _reseal_in_place(backend)
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "schema_keys_mismatch"


def test_candidate_rows_bind_one_case_search_receipt() -> None:
    result = _result()
    _case(result, "5SD5_HWI")["candidates"][17]["candidate_search_receipt_sha256"] = (
        _digest("another-search-run")
    )
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "candidate_search_receipt_mismatch"


def test_digest_only_external_fact_forgery_is_rejected_without_sealed_payload() -> None:
    result = _result()
    candidate = _case(result, "5SD5_HWI")["candidates"][1]
    candidate["rmsd_angstrom"] = 0.25
    candidate["rmsd_fact_receipt_sha256"] = _digest("forged-rmsd-receipt")
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "rmsd_fact_binding_mismatch"

    result = _result()
    candidate = _case(result, "5SD5_HWI")["candidates"][1]
    candidate["posebusters_exact_valid"] = True
    candidate["posebusters_fact_receipt_sha256"] = _digest("forged-posebusters-receipt")
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "posebusters_fact_binding_mismatch"


def test_resealed_posebusters_validity_must_equal_all_22_check_facts() -> None:
    result = _result()
    case = _case(result, "5SD5_HWI")
    candidate = case["candidates"][1]
    candidate["posebusters_exact_valid"] = True
    fact = case["evaluation_receipt"]["candidate_facts"][1]["posebusters_fact"]
    fact["posebusters_exact_valid"] = True
    _reseal_in_place(fact)
    candidate["posebusters_fact_receipt_sha256"] = fact["receipt_sha256"]
    batch = case["evaluation_receipt"]["batch_receipt"]
    batch["candidate_fact_receipt_sha256s"][1]["posebusters_fact_receipt_sha256"] = (
        fact["receipt_sha256"]
    )
    _reseal_in_place(batch)
    _reseal_in_place(case["evaluation_receipt"])

    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "posebusters_fact_binding_mismatch"


def test_resealed_search_subject_and_rank_sidecars_still_bind_candidates() -> None:
    result = _result()
    case = _case(result, "5SD5_HWI")
    search = case["search_receipt"]
    search["candidate_subjects"][0]["coordinate_sha256"] = _digest(
        "forged-search-subject"
    )
    _reseal_in_place(search)
    case["search_receipt_sha256"] = search["receipt_sha256"]
    for candidate in case["candidates"]:
        candidate["candidate_search_receipt_sha256"] = search["receipt_sha256"]
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "search_candidate_binding_mismatch"

    result = _result()
    case = _case(result, "5SD5_HWI")
    rank = case["rank_receipt"]
    rank["ranked_candidates"][0]["native_row_sha256"] = _digest("forged-ranked-subject")
    _reseal_in_place(rank)
    search = case["search_receipt"]
    search["rank_receipt_sha256"] = rank["receipt_sha256"]
    _reseal_in_place(search)
    case["search_receipt_sha256"] = search["receipt_sha256"]
    for candidate in case["candidates"]:
        candidate["candidate_search_receipt_sha256"] = search["receipt_sha256"]
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "rank_candidate_binding_mismatch"


def test_failed_candidate_row_requires_typed_failure_without_losing_slot() -> None:
    result = _result()
    candidate = _case(result, "5SD5_HWI")["candidates"][63]
    candidate["search_status"] = "refinement_failed"
    candidate["search_failure_code"] = "non_finite_evaluator_output"
    _reseal_search_case(result, "5SD5_HWI")
    receipt = evaluate_development_result(result)
    assert receipt["summary"]["candidate_budget"] == 512

    candidate["search_failure_code"] = None
    with pytest.raises(ProtocolError) as captured:
        evaluate_development_result(result)
    assert captured.value.code == "invalid_search_failure_code"


def test_failed_gates_emit_blocked_evidence_without_dropping_rows() -> None:
    result = _result(passing=False)
    receipt = evaluate_development_result(result)
    assert receipt["decision"] == "blocked"
    assert receipt["summary"]["development_gate_pass"] is False
    assert receipt["summary"]["proposal_oracle_recovered_case_count"] == 0
    assert receipt["summary"]["invalid_top1_case_count"] == 8
    assert receipt["summary"]["preserved_6T88"] is False
    assert len(receipt["case_metrics"]) == 9
    verify_evidence_receipt(receipt, result)


def test_6t88_preservation_is_independent_mandatory_gate() -> None:
    result = _result()
    _replace_external_fact(result, "6T88_MWQ", 0, rmsd=5.0, exact_valid=False)
    _replace_external_fact(result, "5SIS_JSM", 0, rmsd=1.6, exact_valid=True)
    receipt = evaluate_development_result(result)
    assert receipt["summary"]["proposal_oracle_recovered_case_count"] == 2
    assert (
        receipt["summary"]["new_previously_uncovered_exact_valid_recovered_case_count"]
        == 2
    )
    assert receipt["summary"]["gates"]["preserve_6T88_exact_valid_recovery"] is False
    assert receipt["decision"] == "blocked"


def test_evidence_hash_tamper_is_rejected() -> None:
    result = _result()
    receipt = evaluate_development_result(result)
    receipt["summary"]["invalid_top1_case_count"] = 0
    with pytest.raises(ProtocolError) as captured:
        verify_evidence_receipt(receipt, result)
    assert captured.value.code == "evidence_hash_mismatch"


def test_resealed_frozen_case_fact_tamper_is_still_rejected() -> None:
    result = _result()
    receipt = evaluate_development_result(result)
    receipt["case_metrics"][0]["rigid_lower_bound_rmsd_angstrom"] = 0.0
    projection = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(projection)
    ).hexdigest()
    with pytest.raises(ProtocolError) as captured:
        verify_evidence_receipt(receipt, result)
    assert captured.value.code == "evidence_case_fact_mismatch"


def test_resealed_exact_valid_classification_tamper_is_rederived() -> None:
    result = _result()
    receipt = evaluate_development_result(result)
    metric = next(
        row for row in receipt["case_metrics"] if row["case_id"] == "5SD5_HWI"
    )
    assert metric["exact_valid_minimum_rmsd_angstrom"] == 1.5
    metric["exact_valid_recovered_at_or_below_2a"] = False
    receipt["summary"]["new_previously_uncovered_exact_valid_recovered_case_ids"] = []
    receipt["summary"]["new_previously_uncovered_exact_valid_recovered_case_count"] = 0
    receipt["summary"]["gates"][
        "new_previously_uncovered_exact_valid_recovery_at_least_1"
    ] = False
    receipt["summary"]["development_gate_pass"] = False
    receipt["decision"] = "blocked"
    projection = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        canonical_json_bytes(projection)
    ).hexdigest()
    with pytest.raises(ProtocolError) as captured:
        verify_evidence_receipt(receipt, result)
    assert captured.value.code == "evidence_case_metric_mismatch"


def test_resealed_compact_evidence_must_match_its_complete_result() -> None:
    blocked_result = _result(passing=False)
    receipt = evaluate_development_result(blocked_result)
    passing = evaluate_development_result(_result(passing=True))
    receipt["case_metrics"] = passing["case_metrics"]
    receipt["summary"] = passing["summary"]
    receipt["decision"] = passing["decision"]
    _reseal_in_place(receipt)

    with pytest.raises(ProtocolError) as captured:
        verify_evidence_receipt(receipt, blocked_result)
    assert captured.value.code == "evidence_result_mismatch"


def test_tool_writes_canonical_receipt_and_uses_blocked_exit_code(
    tmp_path: Path,
) -> None:
    source = tmp_path / "result.json"
    output = tmp_path / "evidence.json"
    source.write_bytes(canonical_json_bytes(_result()))
    assert main(["--result-json", str(source), "--output-json", str(output)]) == 0
    payload = json.loads(output.read_bytes())
    verify_evidence_receipt(payload, json.loads(source.read_bytes()))
    assert output.read_bytes() == canonical_json_bytes(payload)
    assert main(["--result-json", str(source), "--output-json", str(output)]) == 1

    blocked_source = tmp_path / "blocked-result.json"
    blocked_output = tmp_path / "blocked-evidence.json"
    blocked_source.write_bytes(canonical_json_bytes(_result(passing=False)))
    assert (
        main(
            [
                "--result-json",
                str(blocked_source),
                "--output-json",
                str(blocked_output),
            ]
        )
        == 2
    )
    assert json.loads(blocked_output.read_bytes())["decision"] == "blocked"


def test_benchmark_package_has_no_product_or_external_engine_imports() -> None:
    source = Path("benchmarks/docking_search_v2/protocol.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "betelgeuze_engine_v2",
        "betelgeuze_product",
        "posebusters import",
        "rdkit",
        "openmm",
        "vina",
        "gnina",
    ):
        assert forbidden not in source.lower()
