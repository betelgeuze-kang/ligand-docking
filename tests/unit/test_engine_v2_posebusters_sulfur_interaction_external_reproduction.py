from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import stat
import zipfile

import pytest

import betelgeuze_engine_v2.benchmark as benchmark
from betelgeuze_engine_v2.benchmark import (
    public_posebusters_sulfur_interaction_energy as interaction,
)
from betelgeuze_engine_v2.benchmark import (
    public_posebusters_sulfur_interaction_external_reproduction as reproduction,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sealed(payload: dict[str, object]) -> dict[str, object]:
    return {
        **payload,
        "receipt_sha256": reproduction._canonical_sha256(payload),
    }


def _runtime(*, external: bool = False) -> dict[str, object]:
    base = {
        "schema_id": "fixture.base_pyscf_runtime/1.0.0",
        "affinity_cpu_count": 4 if external else 2,
        "all_observed_native_thread_pools_single_thread": True,
        "cpu_identity_sha256": _sha("external-cpu" if external else "baseline-cpu"),
        "cpu_model": "fixture external CPU" if external else "fixture baseline CPU",
        "distribution_payloads": [{"name": "pyscf", "sha256": _sha("pyscf")}],
        "filesystem_encoding": "utf-8",
        "kernel_release": "6.8.0-fixture",
        "libc_name": "glibc",
        "libc_version": "2.39",
        "native_thread_pool_count": 1,
        "native_thread_pool_identity_sha256": _sha("thread-pool"),
        "numpy_configuration_sha256": _sha("numpy-config"),
        "platform_machine": "x86_64",
        "platform_system": "Linux",
        "pyscf_release_version": "2.12.1",
        "pyscf_source_commit": _sha("pyscf-source"),
        "pyscf_source_commit_registry_binding_only": True,
        "pyscf_threads": 1,
        "python_cache_tag": "cpython-312",
        "python_executable_sha256": _sha("python-executable"),
        "python_executable_size_bytes": 12345,
        "python_implementation": "CPython",
        "python_version": "3.12.10",
        "scipy_configuration_sha256": _sha("scipy-config"),
        "transitive_system_native_libraries_individually_fingerprinted": True,
        "wheel_content_sha256": _sha("pyscf-wheel-content"),
        "wheel_filename": "pyscf-2.12.1-cp312-cp312-manylinux.whl",
        "wheel_sha256": _sha("pyscf-wheel"),
        "wheel_size_bytes": 123456,
    }
    payload = {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_RUNTIME_SCHEMA_ID,
        "base_pyscf_runtime": base,
        "base_pyscf_runtime_sha256": reproduction._canonical_sha256(base),
        "pyscf_dispersion_distribution": {
            "name": "pyscf-dispersion",
            "content_sha256": _sha("dispersion-content"),
        },
        "pyscf_dispersion_wheel_binding": {
            "sha256": _sha("dispersion-wheel"),
        },
        "qm_configuration_sha256": reproduction._canonical_sha256(
            interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["qm"]
        ),
        "all_observed_native_thread_pools_single_thread": True,
    }
    return {
        **payload,
        "runtime_identity_sha256": reproduction._canonical_sha256(payload),
    }


def _scf(total: float, *, electrons: int, cycles: int) -> dict[str, object]:
    return {
        "atomic_orbital_count": 64,
        "converged": True,
        "cycle_count": cycles,
        "dispersion_energy_hartree_binary64_hex": float(-0.001).hex(),
        "electron_count": electrons,
        "integration_grid_point_count": 1000,
        "total_energy_hartree_binary64_hex": total.hex(),
    }


def _point(case_index: int, point_index: int) -> dict[str, object]:
    acceptor = -100.0 - case_index
    probe = -50.0
    target_kcal = -1.0 - 0.1 * point_index
    target_hartree = target_kcal / interaction._HARTREE_TO_KCAL_PER_MOL
    complex_total = acceptor + probe + target_hartree
    derived_hartree = complex_total - acceptor - probe
    derived_kcal = derived_hartree * interaction._HARTREE_TO_KCAL_PER_MOL
    orientation = (
        "positive_CSC_plane_normal"
        if point_index == 6
        else "lone_pair_negative"
    )
    counterpoise = {
        "complex": _scf(complex_total, electrons=52, cycles=10),
        "acceptor_with_probe_ghost_basis": _scf(
            acceptor,
            electrons=34,
            cycles=8,
        ),
        "probe_with_acceptor_ghost_basis": _scf(
            probe,
            electrons=18,
            cycles=8,
        ),
        "counterpoise_interaction_energy_hartree_binary64_hex": (
            derived_hartree.hex()
        ),
        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": (
            derived_kcal.hex()
        ),
    }
    return {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_POINT_SCHEMA_ID,
        "geometry_id": f"fixture-{case_index}-{point_index}",
        "orientation": orientation,
        "distance_angstrom_binary64_hex": float(2.0 + point_index * 0.25).hex(),
        "complex_geometry_sha256": _sha(f"geometry-{case_index}-{point_index}"),
        "ad4_pair_terms": {
            "fixture_pair_energy_binary64_hex": float(-0.1 * point_index).hex(),
        },
        "qm_attempted": True,
        "status": "evaluated",
        "error_code": None,
        "error_type": None,
        "error_message_sha256": None,
        "counterpoise": counterpoise,
        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": (
            derived_kcal.hex()
        ),
    }


def _evaluated_case(case_index: int) -> dict[str, object]:
    return {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
        "case_id": f"fixture-scope-{case_index}",
        "protocol_status": "registered",
        "status": "evaluated",
        "disposition_code": "neutral_thioether_oh_donor_interaction_complete",
        "environment": f"fixture-environment-{case_index}",
        "model_id": f"fixture-model-{case_index}",
        "target_sulfur": {"source_smiles_atom_index": case_index},
        "qm_attempted": True,
        "attempted_point_count": 7,
        "qm_failure_point_count": 0,
        "case_acceptor_support": True,
        "ad4_sa_pair_profile_preferred": True,
        "point_rows": [_point(case_index, index) for index in range(7)],
        "metrics": {
            "binding_gates": {
                "minimum_energy_gate": True,
                "far_referenced_well_depth_gate": True,
                "minimum_distance_gate": True,
            },
            "qm_profile": {
                "minimum_distance_angstrom_binary64_hex": float(2.5).hex(),
            },
        },
    }


def _abstention(index: int) -> dict[str, object]:
    return {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
        "case_id": f"fixture-abstain-{index:03d}",
        "protocol_status": "abstain_protocol_scope",
        "status": "abstain_protocol_scope",
        "disposition_code": "outside_preregistered_neutral_thioether_scope",
        "qm_attempted": False,
        "point_rows": [],
        "case_acceptor_support": None,
        "ad4_sa_pair_profile_preferred": None,
    }


def _observation(
    *,
    external: bool = False,
    observation_utc: str | None = None,
) -> dict[str, object]:
    runtime = _runtime(external=external)
    payload = {
        "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID,
        "observation_utc": observation_utc
        or (
            "2026-07-23T11:00:00Z"
            if external
            else "2026-07-23T09:00:00Z"
        ),
        "protocol_receipt_sha256": _sha("interaction-protocol"),
        "protocol_receipt_file_sha256": _sha("interaction-protocol-file"),
        "protocol_registered_before_qm_execution": True,
        "configuration": interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION,
        "configuration_sha256": (
            interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256
        ),
        "implementation_source_members": [
            {"relative_path": "fixture.py", "sha256": _sha("fixture-source")}
        ],
        "implementation_source_sha256": _sha("fixture-implementation"),
        "pyscf_interaction_runtime_identity": runtime,
        "pyscf_interaction_runtime_identity_sha256": runtime[
            "runtime_identity_sha256"
        ],
        "all_case_denominator": 308,
        "scope_case_count": 3,
        "scope_abstention_case_count": 305,
        "evaluated_case_count": 3,
        "qm_failure_case_count": 0,
        "all_scoped_cases_evaluated": True,
        "case_acceptor_support_count": 3,
        "ad4_sa_pair_profile_preferred_case_count": 3,
        "local_three_model_oh_acceptor_gate_pass": True,
        "local_ad4_sa_pair_profile_gate_pass": True,
        "ad4_pair_formula_executed": True,
        "bounded_local_interaction_evidence_generated": True,
        "second_cpu_host_reproduced": False,
        "independent_reviewer_receipt_approved": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientific_blockers": list(
            interaction.POSEBUSTERS_SULFUR_INTERACTION_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
        "case_rows": [
            *[_evaluated_case(index) for index in range(3)],
            *[_abstention(index) for index in range(305)],
        ],
    }
    return _sealed(payload)


def _external_copy(baseline: dict[str, object]) -> dict[str, object]:
    external = deepcopy(baseline)
    external.pop("receipt_sha256")
    runtime = _runtime(external=True)
    external["observation_utc"] = "2026-07-23T11:00:00Z"
    external["pyscf_interaction_runtime_identity"] = runtime
    external["pyscf_interaction_runtime_identity_sha256"] = runtime[
        "runtime_identity_sha256"
    ]
    return _sealed(external)


def _perturb_first_point(
    observation: dict[str, object],
    *,
    complex_energy_delta_hartree: float,
) -> dict[str, object]:
    changed = deepcopy(observation)
    changed.pop("receipt_sha256")
    case = changed["case_rows"][0]
    point = case["point_rows"][0]
    counterpoise = point["counterpoise"]
    complex_component = counterpoise["complex"]
    complex_total = float.fromhex(
        complex_component["total_energy_hartree_binary64_hex"]
    )
    complex_total += complex_energy_delta_hartree
    complex_component["total_energy_hartree_binary64_hex"] = complex_total.hex()
    acceptor = float.fromhex(
        counterpoise["acceptor_with_probe_ghost_basis"][
            "total_energy_hartree_binary64_hex"
        ]
    )
    probe = float.fromhex(
        counterpoise["probe_with_acceptor_ghost_basis"][
            "total_energy_hartree_binary64_hex"
        ]
    )
    interaction_hartree = complex_total - acceptor - probe
    interaction_kcal = (
        interaction_hartree * interaction._HARTREE_TO_KCAL_PER_MOL
    )
    counterpoise["counterpoise_interaction_energy_hartree_binary64_hex"] = (
        interaction_hartree.hex()
    )
    counterpoise[
        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
    ] = interaction_kcal.hex()
    point[
        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
    ] = interaction_kcal.hex()
    complex_component["dispersion_energy_hartree_binary64_hex"] = (
        float.fromhex(
            complex_component["dispersion_energy_hartree_binary64_hex"]
        )
        + 5.0e-13
    ).hex()
    complex_component["cycle_count"] += 1
    return _sealed(changed)


def _private_receipt(path: Path, payload: dict[str, object]) -> bytes:
    source = reproduction._canonical_bytes(payload) + b"\n"
    path.write_bytes(source)
    path.chmod(0o600)
    return source


def _engine_wheel(path: Path) -> str:
    modules = {
        "public_posebusters_sulfur_interaction_energy.py": interaction,
        "public_posebusters_sulfur_interaction_external_reproduction.py": (
            reproduction
        ),
        "public_posebusters_sulfur_qm_esp.py": reproduction.qm_esp,
        "public_posebusters_vina_sulfur_type_invariance.py": (
            reproduction.vina_invariance
        ),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for filename, module in modules.items():
            module_path = Path(module.__file__)
            archive.writestr(
                f"betelgeuze_engine_v2/benchmark/{filename}",
                module_path.read_bytes(),
            )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialized_inputs(tmp_path: Path) -> dict[str, object]:
    implementation_sha = _sha("fixture-baseline-implementation")
    protocol = _sealed(
        {
            "schema_id": interaction.POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID,
            "implementation_source_sha256": implementation_sha,
            "pyscf_wheel_binding": {"sha256": _sha("pyscf-wheel")},
            "pyscf_dispersion_wheel_binding": {
                "sha256": _sha("dispersion-wheel")
            },
            "vina_ad4_source_binding": {"sha256": _sha("vina-source")},
        }
    )
    protocol_path = tmp_path / "baseline-protocol.json"
    protocol_source = _private_receipt(protocol_path, protocol)

    observation = _observation()
    observation.pop("receipt_sha256")
    observation["protocol_receipt_sha256"] = protocol["receipt_sha256"]
    observation["protocol_receipt_file_sha256"] = hashlib.sha256(
        protocol_source
    ).hexdigest()
    observation["implementation_source_sha256"] = implementation_sha
    observation = _sealed(observation)
    observation_path = tmp_path / "baseline-observation.json"
    _private_receipt(observation_path, observation)

    wheel_path = (
        tmp_path / "betelgeuze_engine_v2-0.3.0a1-py3-none-any.whl"
    )
    wheel_sha = _engine_wheel(wheel_path)
    work_order = reproduction.materialize_posebusters_sulfur_reproduction_work_order(
        protocol_path,
        observation_path,
        wheel_path,
        expected_baseline_protocol_sha256=protocol["receipt_sha256"],
        expected_baseline_observation_sha256=observation["receipt_sha256"],
        expected_engine_wheel_sha256=wheel_sha,
        baseline_host_identity_sha256=_sha("baseline-host"),
        expected_external_host_identity_sha256=_sha("external-host"),
        work_order_operator_identity_sha256=_sha("work-order-operator"),
        external_execution_operator_identity_sha256=_sha("external-executor"),
        external_execution_nonce_sha256=_sha("external-execution-nonce"),
        registered_utc="2026-07-23T10:00:00Z",
    )
    work_order_path = tmp_path / "work-order.json"
    work_order_source = _private_receipt(work_order_path, work_order)
    return {
        "protocol": protocol,
        "protocol_path": protocol_path,
        "observation": observation,
        "observation_path": observation_path,
        "wheel_path": wheel_path,
        "wheel_sha": wheel_sha,
        "work_order": work_order,
        "work_order_path": work_order_path,
        "work_order_file_sha": hashlib.sha256(work_order_source).hexdigest(),
    }


def _review_evidence() -> tuple[dict[str, object], dict[str, object]]:
    work_order = _sealed(
        {
            "schema_id": (
                reproduction.POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID
            ),
            "registered_utc": "2026-07-23T10:00:00Z",
            "baseline_host_identity_sha256": _sha("baseline-host"),
            "expected_external_host_identity_sha256": _sha("external-host"),
            "work_order_operator_identity_sha256": _sha("work-order-operator"),
            "external_execution_operator_identity_sha256": _sha(
                "external-executor"
            ),
            "external_execution_nonce_sha256": _sha("external-execution-nonce"),
        }
    )
    comparison_payload = {
        "schema_id": (
            reproduction.POSEBUSTERS_SULFUR_REPRODUCTION_COMPARISON_SCHEMA_ID
        ),
        "cross_host_numerical_reproduction_pass": True,
    }
    comparison = {
        **comparison_payload,
        "comparison_sha256": reproduction._canonical_sha256(comparison_payload),
    }
    result = _sealed(
        {
            "schema_id": reproduction.POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID,
            "observed_utc": "2026-07-23T11:00:00Z",
            "work_order_receipt_sha256": work_order["receipt_sha256"],
            "baseline_observation_receipt_sha256": _sha(
                "baseline-observation"
            ),
            "external_observation_receipt_sha256": _sha(
                "external-observation"
            ),
            "status": "reproduced",
            "shared_runtime_projection_equal": True,
            "comparison": comparison,
            "second_cpu_host_reproduced": True,
        }
    )
    return work_order, result


def test_exact_cross_host_copy_compares_all_308_rows_and_63_scfs() -> None:
    baseline = _observation()
    external = _external_copy(baseline)
    comparison = (
        reproduction.compare_posebusters_sulfur_cross_host_observations(
            baseline,
            external,
        )
    )
    assert comparison["all_case_denominator"] == 308
    assert comparison["compared_point_count"] == 21
    assert comparison["compared_counterpoise_scf_count"] == 63
    assert comparison["scientific_case_rows_bitwise_equal"] is True
    assert comparison["cross_host_numerical_reproduction_pass"] is True


def test_bounded_numeric_difference_passes_but_is_not_bitwise_equal() -> None:
    baseline = _observation()
    external = _perturb_first_point(
        _external_copy(baseline),
        complex_energy_delta_hartree=4.0e-9,
    )
    comparison = (
        reproduction.compare_posebusters_sulfur_cross_host_observations(
            baseline,
            external,
        )
    )
    assert comparison["numeric_tolerance_pass"] is True
    assert comparison["structural_invariants_pass"] is True
    assert comparison["scientific_case_rows_bitwise_equal"] is False
    assert comparison["cross_host_numerical_reproduction_pass"] is True


def test_out_of_tolerance_energy_fails_cross_host_reproduction() -> None:
    baseline = _observation()
    external = _perturb_first_point(
        _external_copy(baseline),
        complex_energy_delta_hartree=6.0e-8,
    )
    comparison = (
        reproduction.compare_posebusters_sulfur_cross_host_observations(
            baseline,
            external,
        )
    )
    assert comparison["numeric_tolerance_pass"] is False
    assert comparison["cross_host_numerical_reproduction_pass"] is False


def test_external_qm_failure_is_retained_and_fails_reproduction() -> None:
    baseline = _observation()
    external = _external_copy(baseline)
    external.pop("receipt_sha256")
    case = external["case_rows"][0]
    point = case["point_rows"][0]
    point["status"] = "qm_failure"
    point["error_code"] = "scf_failed"
    point["error_type"] = "RuntimeError"
    point["error_message_sha256"] = _sha("bounded failure")
    point["counterpoise"] = None
    point["counterpoise_interaction_energy_kcal_per_mol_binary64_hex"] = None
    case["status"] = "qm_failure"
    case["qm_failure_point_count"] = 1
    external["evaluated_case_count"] = 2
    external["qm_failure_case_count"] = 1
    external["all_scoped_cases_evaluated"] = False
    external["local_three_model_oh_acceptor_gate_pass"] = False
    external = _sealed(external)

    comparison = (
        reproduction.compare_posebusters_sulfur_cross_host_observations(
            baseline,
            external,
        )
    )
    assert comparison["external_qm_failure_point_count"] == 1
    assert comparison["all_failure_and_abstention_rows_retained"] is True
    assert comparison["cross_host_numerical_reproduction_pass"] is False


def test_runtime_projection_allows_only_host_cpu_and_affinity_difference() -> None:
    baseline = _runtime()
    external = _runtime(external=True)
    assert reproduction._runtime_shared_projection(
        baseline
    ) == reproduction._runtime_shared_projection(external)

    changed = deepcopy(external)
    changed["base_pyscf_runtime"]["wheel_sha256"] = _sha("different-wheel")
    assert reproduction._runtime_shared_projection(
        baseline
    ) != reproduction._runtime_shared_projection(changed)


def test_work_order_and_reproduced_result_reconstruct_exactly(
    tmp_path: Path,
) -> None:
    inputs = _materialized_inputs(tmp_path)
    verified_work_order = (
        reproduction.verify_posebusters_sulfur_reproduction_work_order(
            inputs["work_order_path"],
            inputs["protocol_path"],
            inputs["observation_path"],
            inputs["wheel_path"],
            expected_work_order_sha256=inputs["work_order"]["receipt_sha256"],
            expected_baseline_protocol_sha256=inputs["protocol"][
                "receipt_sha256"
            ],
            expected_baseline_observation_sha256=inputs["observation"][
                "receipt_sha256"
            ],
            expected_engine_wheel_sha256=inputs["wheel_sha"],
        )
    )
    assert verified_work_order == inputs["work_order"]

    external_observation = _external_copy(inputs["observation"])
    result = reproduction._result_payload(
        work_order=inputs["work_order"],
        work_order_file_sha256=inputs["work_order_file_sha"],
        baseline_observation=inputs["observation"],
        observed_utc=external_observation["observation_utc"],
        external_runtime_identity=external_observation[
            "pyscf_interaction_runtime_identity"
        ],
        external_observation=external_observation,
        status="reproduced",
        error_code=None,
        error_type=None,
        error_message_sha256=None,
    )
    result_path = tmp_path / "result.json"
    _private_receipt(result_path, result)
    verified_result = (
        reproduction.verify_posebusters_sulfur_reproduction_result(
            result_path,
            inputs["work_order_path"],
            inputs["protocol_path"],
            inputs["observation_path"],
            inputs["wheel_path"],
            expected_result_sha256=result["receipt_sha256"],
            expected_work_order_sha256=inputs["work_order"]["receipt_sha256"],
            expected_baseline_protocol_sha256=inputs["protocol"][
                "receipt_sha256"
            ],
            expected_baseline_observation_sha256=inputs["observation"][
                "receipt_sha256"
            ],
            expected_engine_wheel_sha256=inputs["wheel_sha"],
        )
    )
    assert verified_result["second_cpu_host_reproduced"] is True
    assert verified_result["scientifically_validated"] is False
    assert verified_result["claim_safe"] is False


def test_result_verifier_rejects_status_that_disagrees_with_metrics(
    tmp_path: Path,
) -> None:
    inputs = _materialized_inputs(tmp_path)
    external_observation = _perturb_first_point(
        _external_copy(inputs["observation"]),
        complex_energy_delta_hartree=6.0e-8,
    )
    forged = reproduction._result_payload(
        work_order=inputs["work_order"],
        work_order_file_sha256=inputs["work_order_file_sha"],
        baseline_observation=inputs["observation"],
        observed_utc=external_observation["observation_utc"],
        external_runtime_identity=external_observation[
            "pyscf_interaction_runtime_identity"
        ],
        external_observation=external_observation,
        status="reproduced",
        error_code=None,
        error_type=None,
        error_message_sha256=None,
    )
    result_path = tmp_path / "forged-result.json"
    _private_receipt(result_path, forged)
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="status disagrees",
    ):
        reproduction.verify_posebusters_sulfur_reproduction_result(
            result_path,
            inputs["work_order_path"],
            inputs["protocol_path"],
            inputs["observation_path"],
            inputs["wheel_path"],
            expected_result_sha256=forged["receipt_sha256"],
            expected_work_order_sha256=inputs["work_order"]["receipt_sha256"],
            expected_baseline_protocol_sha256=inputs["protocol"][
                "receipt_sha256"
            ],
            expected_baseline_observation_sha256=inputs["observation"][
                "receipt_sha256"
            ],
            expected_engine_wheel_sha256=inputs["wheel_sha"],
        )


def test_detached_independent_review_verifies_without_promoting_claims() -> None:
    work_order, result = _review_evidence()
    private_key = bytes(range(32))
    reviewer_identity = _sha("independent-reviewer")
    approval = reproduction.build_signed_posebusters_sulfur_review(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id="fixture-reviewer-1",
        reviewed_at_utc="2026-07-23T12:00:00Z",
        expires_at_utc="2026-07-30T12:00:00Z",
        review_nonce_sha256=_sha("review-nonce"),
        signing_key=private_key,
    )
    verification = reproduction.verify_signed_posebusters_sulfur_review(
        approval,
        work_order=work_order,
        result=result,
        trusted_reviewer_keys={
            "fixture-reviewer-1": (
                reproduction.PoseBustersSulfurReviewerTrustAnchor(
                    reviewer_identity_sha256=reviewer_identity,
                    verification_key=ed25519_public_key_bytes(private_key),
                )
            )
        },
        checked_at_utc="2026-07-24T12:00:00Z",
        revoked_reviewer_key_ids=[],
        revoked_review_receipt_sha256s=[],
        superseded_review_receipt_sha256s=[],
    )
    assert verification["second_cpu_host_reproduced"] is True
    assert verification["independent_reviewer_receipt_approved"] is True
    assert verification["chemical_acceptor_semantics_adjudicated"] is False
    assert verification["scientifically_validated"] is False
    assert verification["product_promotion_allowed"] is False
    assert verification["claim_safe"] is False


def test_review_rejects_role_alias_tamper_revocation_and_expiry() -> None:
    work_order, result = _review_evidence()
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="reviewer must be distinct",
    ):
        reproduction.build_posebusters_sulfur_review_signing_request(
            work_order=work_order,
            result=result,
            reviewer_identity_sha256=work_order[
                "external_execution_operator_identity_sha256"
            ],
            reviewer_key_id="fixture-reviewer-1",
            reviewed_at_utc="2026-07-23T12:00:00Z",
            expires_at_utc="2026-07-30T12:00:00Z",
            review_nonce_sha256=_sha("review-nonce"),
        )

    private_key = bytes(range(32))
    reviewer_identity = _sha("independent-reviewer")
    approval = reproduction.build_signed_posebusters_sulfur_review(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id="fixture-reviewer-1",
        reviewed_at_utc="2026-07-23T12:00:00Z",
        expires_at_utc="2026-07-30T12:00:00Z",
        review_nonce_sha256=_sha("review-nonce"),
        signing_key=private_key,
    )
    anchor = reproduction.PoseBustersSulfurReviewerTrustAnchor(
        reviewer_identity_sha256=reviewer_identity,
        verification_key=ed25519_public_key_bytes(private_key),
    )
    tampered = deepcopy(approval)
    tampered["claim_safe"] = True
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="digest is invalid",
    ):
        reproduction.verify_signed_posebusters_sulfur_review(
            tampered,
            work_order=work_order,
            result=result,
            trusted_reviewer_keys={"fixture-reviewer-1": anchor},
            checked_at_utc="2026-07-24T12:00:00Z",
            revoked_reviewer_key_ids=[],
            revoked_review_receipt_sha256s=[],
            superseded_review_receipt_sha256s=[],
        )
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="key is revoked",
    ):
        reproduction.verify_signed_posebusters_sulfur_review(
            approval,
            work_order=work_order,
            result=result,
            trusted_reviewer_keys={"fixture-reviewer-1": anchor},
            checked_at_utc="2026-07-24T12:00:00Z",
            revoked_reviewer_key_ids=["fixture-reviewer-1"],
            revoked_review_receipt_sha256s=[],
            superseded_review_receipt_sha256s=[],
        )
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="not currently valid",
    ):
        reproduction.verify_signed_posebusters_sulfur_review(
            approval,
            work_order=work_order,
            result=result,
            trusted_reviewer_keys={"fixture-reviewer-1": anchor},
            checked_at_utc="2026-08-01T12:00:00Z",
            revoked_reviewer_key_ids=[],
            revoked_review_receipt_sha256s=[],
            superseded_review_receipt_sha256s=[],
        )


def test_review_signing_request_rejects_recursive_private_material() -> None:
    work_order, result = _review_evidence()
    request = reproduction.build_posebusters_sulfur_review_signing_request(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=_sha("independent-reviewer"),
        reviewer_key_id="fixture-reviewer-1",
        reviewed_at_utc="2026-07-23T12:00:00Z",
        expires_at_utc="2026-07-30T12:00:00Z",
        review_nonce_sha256=_sha("review-nonce"),
    )
    injected = deepcopy(request)
    payload = injected["review_payload"]
    payload["private_key"] = "not-a-real-secret"
    unsigned = dict(payload)
    unsigned.pop("review_receipt_sha256")
    payload["review_receipt_sha256"] = reproduction._canonical_sha256(unsigned)
    injected["signing_bytes_sha256"] = hashlib.sha256(
        reproduction._canonical_bytes(payload)
    ).hexdigest()
    request_payload = dict(injected)
    request_payload.pop("request_sha256")
    injected["request_sha256"] = reproduction._canonical_sha256(request_payload)
    with pytest.raises(
        reproduction.PoseBustersSulfurReproductionError,
        match="private signing material",
    ):
        reproduction.require_posebusters_sulfur_review_signing_request(injected)


def test_reproduction_cli_and_public_surface_are_explicit() -> None:
    help_text = reproduction._parser().format_help()
    assert "two-host neutral-thioether" in help_text
    assert "verify-result" in help_text
    assert "build-review-request" in help_text
    assert "verify-review" in help_text
    assert "--private-key" not in help_text
    assert (
        reproduction.POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION[
            "review_policy"
        ]["private_key_forbidden_in_signing_request_and_cli"]
        is True
    )
    assert stat.S_IMODE(Path(reproduction.__file__).stat().st_mode) in {
        0o644,
        0o664,
    }
    assert (
        benchmark.POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256
        == reproduction.POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256
    )
    assert (
        benchmark.verify_signed_posebusters_sulfur_review
        is reproduction.verify_signed_posebusters_sulfur_review
    )
