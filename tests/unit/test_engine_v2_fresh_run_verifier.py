from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2.benchmark.blind_stage0 as blind_stage0_contract
from betelgeuze_engine_v2.benchmark import fresh_run_verifier as verifier
from betelgeuze_engine_v2.benchmark import public_redocking_benchmark as contract
from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    VerifiedStage0Admission,
    stage0_engine_implementation_sha256,
)
from betelgeuze_engine_v2.benchmark.fresh_redocking_holdout import (
    FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256,
    load_fresh_redocking_holdout_manifest,
)
from betelgeuze_engine_v2.benchmark.fresh_artifacts import (
    FRESH_ARTIFACT_MANIFEST_FILENAME,
    FRESH_EXECUTION_ENVIRONMENT_FILENAME,
    FRESH_EXECUTION_LOG_FILENAME,
    FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME,
    build_fresh_artifact_manifest,
)
from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
    FRESH_COMPLETION_FILENAME,
    FRESH_FAILURE_FILENAME,
    FRESH_ENGINE_ROW_COUNT,
    FRESH_ENGINE_V2_SLOT_COUNT,
    FRESH_INTERNAL_REPORT_SCHEMA_ID,
    FRESH_REPORT_FILENAME,
    FRESH_RESERVATION_FILENAME,
    FRESH_RUNNER_ID,
    FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID,
    FRESH_RUN_ONCE_RESERVATION_SCHEMA_ID,
    FRESH_RUN_TERMINAL_FAILURE_SCHEMA_ID,
    FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME,
    FreshRedockingCaseProfile,
    FreshRedockingCaseResult,
    FreshRunVerificationError,
    build_candidate_slot_ledger,
    canonical_bytes,
    canonical_sha256,
    derive_fresh_subgroup_results,
    fresh_engine_v2_execution_command,
    verify_fresh_report_document,
    verify_fresh_run_root,
    verify_reservation_document,
    verify_terminal_failure_document,
)
from betelgeuze_engine_v2.benchmark.public_redocking_pipeline import (
    public_redocking_pipeline_profile_identity,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_RUNNER_ID,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    PublicRedockingEngineIdentity,
    PublicRedockingEngineV2Diagnostics,
    PublicRedockingEvaluationPolicy,
)
from tools import run_engine_v2_public_redocking_300 as runner


ROOT = Path(__file__).resolve().parents[2]
PROFILE_SHA256 = "4" * 64
SOURCE_FREEZE_SHA256 = "3" * 64
EVALUATION_SHA256 = "5" * 64
_RUNTIME_DEPENDENCY_AUTHORITY_PROJECTION = {
    "schema_id": (
        blind_stage0_contract.STAGE0_RUNTIME_DEPENDENCY_AUTHORITY_SCHEMA_ID
    ),
    "distribution_versions": {
        **dict(blind_stage0_contract.STAGE0_EVALUATOR_DISTRIBUTION_VERSIONS),
        "torch": "fixture",
    },
    "installed_distribution_file_ledger_sha256s": {
        distribution_name: hashlib.sha256(
            f"fresh-verifier:{distribution_name}".encode("ascii")
        ).hexdigest()
        for distribution_name in (
            *blind_stage0_contract.STAGE0_EVALUATOR_DISTRIBUTION_VERSIONS,
            *blind_stage0_contract.STAGE0_CORE_RUNTIME_DISTRIBUTIONS,
        )
    },
}
RUNTIME_DEPENDENCY_AUTHORITY = {
    **_RUNTIME_DEPENDENCY_AUTHORITY_PROJECTION,
    "authority_sha256": hashlib.sha256(
        json.dumps(
            _RUNTIME_DEPENDENCY_AUTHORITY_PROJECTION,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest(),
}
_STAGE0_POLICY_PROJECTION = {
    "schema_version": 1,
    "protocol_id": "fresh-verifier-test-policy",
    "source_freeze": {
        "execution_profile": {
            "runtime_dependency_authority": RUNTIME_DEPENDENCY_AUTHORITY,
            "evaluation_pipeline_sha256": EVALUATION_SHA256,
        }
    },
    "environment_freeze": {
        "runtime_dependency_authority": RUNTIME_DEPENDENCY_AUTHORITY,
        "evaluation_pipeline_sha256": EVALUATION_SHA256,
    },
}
POLICY_SHA256 = hashlib.sha256(
    json.dumps(
        _STAGE0_POLICY_PROJECTION,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
).hexdigest()
STAGE0_POLICY_DOCUMENT = {
    **_STAGE0_POLICY_PROJECTION,
    "policy_sha256": POLICY_SHA256,
}
ENVIRONMENT_DOCUMENT = {
    "python": "test",
    "execution_isolation": "fixture",
    "runtime_dependency_authority": RUNTIME_DEPENDENCY_AUTHORITY,
    "evaluation_pipeline_sha256": EVALUATION_SHA256,
}
ENVIRONMENT_SHA256 = hashlib.sha256(
    json.dumps(
        ENVIRONMENT_DOCUMENT,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
).hexdigest()
ENGINE_V2_IMPLEMENTATION_SHA256 = stage0_engine_implementation_sha256(ROOT)
EXTERNAL_BINARY_BYTES = b"fresh-verifier-gnina-fixture"
EXTERNAL_IMPLEMENTATION_SHA256 = hashlib.sha256(EXTERNAL_BINARY_BYTES).hexdigest()
PIPELINE_PROFILE_ID, PIPELINE_SHA256 = public_redocking_pipeline_profile_identity(
    engine_implementation_sha256=ENGINE_V2_IMPLEMENTATION_SHA256,
    variant_kind="",
)
REPORT_OUTPUT_ROOT = ROOT / ".betelgeuze/fresh-redocking-128"


def _reservation() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": FRESH_RUN_ONCE_RESERVATION_SCHEMA_ID,
        "runner_id": FRESH_RUNNER_ID,
        "status": "reserved_before_holdout_open",
        "reservation_nonce": "a" * 32,
        "reserved_at_unix_ns": 1,
        "retention_root": ".betelgeuze/fresh-redocking-128",
        "fresh_holdout_manifest_sha256": (FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256),
        "case_ids_sha256": canonical_sha256(
            list(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS)
        ),
        "stage0_policy_sha256": POLICY_SHA256,
        "source_freeze_sha256": SOURCE_FREEZE_SHA256,
        "execution_profile_sha256": PROFILE_SHA256,
        "external_run_once_authority_id": "test-worm-authority",
        "external_run_once_reservation_sha256": "7" * 64,
        "fresh_run_identity_sha256": "8" * 64,
        "docking_pipeline_profile_id": PIPELINE_PROFILE_ID,
        "docking_pipeline_profile_sha256": PIPELINE_SHA256,
        "external_worm_reservation_bound": True,
        "expected_case_count": 128,
        "expected_engine_case_row_count": FRESH_ENGINE_ROW_COUNT,
        "expected_engine_v2_candidate_slot_count": FRESH_ENGINE_V2_SLOT_COUNT,
        "single_execution_only": True,
        "resume_allowed": False,
        "rerun_allowed": False,
        "result_dependent_changes_allowed": False,
    }
    payload["reservation_sha256"] = canonical_sha256(payload)
    return payload


def _profile(case: object) -> FreshRedockingCaseProfile:
    return FreshRedockingCaseProfile(
        case_id=case.case_id,
        heavy_atom_count=int(case.profile["heavy_atom_count"]),
        rotor_count=int(case.profile["rotatable_bond_count_strict"]),
        ring_count=int(case.profile["ring_count"]),
        ligand_artifact_sha256=case.artifact_sha256s["native"],
    )


def _policy_tokens(policy: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        f"{key}={json.dumps(value, allow_nan=False, separators=(',', ':'))}"
        for key, value in sorted(policy.items())
    )


def _row(
    case: object,
    engine_id: str,
    *,
    output_root: Path = REPORT_OUTPUT_ROOT,
) -> FreshRedockingCaseResult:
    if engine_id == "engine_v2":
        diagnostics = PublicRedockingEngineV2Diagnostics(
            preparation_status="failure",
            receptor_atom_count=0,
            ligand_atom_count=0,
            receptor_partial_charge_count=0,
            ligand_partial_charge_count=0,
            receptor_donor_count=0,
            receptor_acceptor_count=0,
            ligand_donor_count=0,
            ligand_acceptor_count=0,
            preparation_failure_code="input_parse_unsupported",
        )
        execution_policy = {
            "algorithm_profile_id": (
                contract.PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID
            ),
            "candidate_schema_id": (
                contract.PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
            ),
            "cpu_count": 1,
            "docking_pipeline_profile_id": PIPELINE_PROFILE_ID,
            "docking_pipeline_profile_sha256": PIPELINE_SHA256,
            "execution_profile_sha256": PROFILE_SHA256,
            "interaction_refinement_steps": (
                contract.PUBLIC_REDOCKING_ENGINE_V2_REFINEMENT_STEPS
            ),
            "interaction_refiner": (
                contract.PUBLIC_REDOCKING_ENGINE_V2_REFINER_POLICY_ID
            ),
            "interaction_refiner_config_sha256": (
                contract.PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256
            ),
            "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
            "scorer_backend": "rust_cpu_required",
            "scorer_thread_count": 1,
            "torch_interop_threads": 1,
            "torch_intraop_threads": 1,
            "torch_version": "2.6.0+rocm6.1",
        }
        failure_code = "engine_v2_input_unsupported"
    else:
        diagnostics = None
        execution_policy = {
            "cpu_count": 1,
            "execution_profile_sha256": PROFILE_SHA256,
            "timeout_seconds": 300,
        }
        failure_code = "external_process_failed"
    execution_command = (
        fresh_engine_v2_execution_command(
            case.case_id,
            output_root=output_root,
        )
        if engine_id == "engine_v2"
        else (
            PUBLIC_REDOCKING_RUNNER_ID,
            engine_id,
            "--case-id",
            case.case_id,
            "--seed",
            str(case.seed),
        )
    )
    return FreshRedockingCaseResult(
        case_id=case.case_id,
        engine_id=engine_id,
        status="failure",
        runtime_seconds=1.0,
        receptor_artifact_sha256=case.artifact_sha256s["receptor"],
        reference_artifact_sha256=case.artifact_sha256s["reference"],
        native_artifact_sha256=case.artifact_sha256s["native"],
        seed_artifact_sha256=case.artifact_sha256s["seed"],
        execution_command=execution_command,
        execution_policy=_policy_tokens(execution_policy),
        failure_code=failure_code,
        engine_v2_diagnostics=diagnostics,
    )


@pytest.mark.parametrize("case_id", ("7PA4_C", "8BPL_CP"))
def test_public_runner_row_types_accept_only_frozen_short_fresh_ids(
    case_id: str,
) -> None:
    holdout = load_fresh_redocking_holdout_manifest(
        ROOT / "config/engine_v2_fresh_redocking_holdout_manifest.json"
    )
    case = holdout.case(case_id)
    profile = contract.PublicRedockingCaseProfile(
        case_id=case_id,
        heavy_atom_count=int(case.profile["heavy_atom_count"]),
        rotor_count=int(case.profile["rotatable_bond_count_strict"]),
        ring_count=int(case.profile["ring_count"]),
        ligand_artifact_sha256=case.artifact_sha256s["native"],
    )
    row = contract.PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="vina",
        status="failure",
        runtime_seconds=0.0,
        receptor_artifact_sha256=case.artifact_sha256s["receptor"],
        reference_artifact_sha256=case.artifact_sha256s["reference"],
        native_artifact_sha256=case.artifact_sha256s["native"],
        seed_artifact_sha256=case.artifact_sha256s["seed"],
        execution_command=("vina", "--case-id", case_id),
        execution_policy=("cpu_count=1",),
        failure_code="external_process_failed",
    )

    assert profile.case_id == case_id
    assert row.case_id == case_id
    with pytest.raises(contract.PublicRedockingBenchmarkError):
        replace(profile, case_id=f"X{case_id}")


def _identities() -> tuple[PublicRedockingEngineIdentity, ...]:
    return (
        PublicRedockingEngineIdentity(
            engine_id="engine_v2",
            version="source-stage7",
            implementation_sha256=ENGINE_V2_IMPLEMENTATION_SHA256,
            evaluation_pipeline_sha256=EVALUATION_SHA256,
            command=(
                PUBLIC_REDOCKING_RUNNER_ID,
                "engine_v2",
                "--candidate-count",
                "64",
                "--cpu",
                "1",
                "--torch-version",
                "2.6.0+rocm6.1",
            ),
        ),
        PublicRedockingEngineIdentity(
            engine_id="vina",
            version="test-vina",
            implementation_sha256=EXTERNAL_IMPLEMENTATION_SHA256,
            evaluation_pipeline_sha256=EVALUATION_SHA256,
            command=("/frozen/gnina", "vina"),
        ),
        PublicRedockingEngineIdentity(
            engine_id="gnina",
            version="test-gnina",
            implementation_sha256=EXTERNAL_IMPLEMENTATION_SHA256,
            evaluation_pipeline_sha256=EVALUATION_SHA256,
            command=("/frozen/gnina", "gnina"),
        ),
    )


def _execution_receipt(
    row: FreshRedockingCaseResult,
    *,
    materialization_receipt_sha256: str,
    identity: PublicRedockingEngineIdentity,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
        "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_ids_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "command": list(row.execution_command),
        "execution_policy": contract._execution_policy_mapping(row.execution_policy),
        "input_sha256s": {
            "receptor": row.receptor_artifact_sha256,
            "reference": row.reference_artifact_sha256,
            "native": row.native_artifact_sha256,
            "seed": row.seed_artifact_sha256,
        },
        "materialization_receipt_sha256": materialization_receipt_sha256,
        "implementation_sha256": identity.implementation_sha256,
        "evaluation_pipeline_sha256": identity.evaluation_pipeline_sha256,
        "execution_environment_sha256": ENVIRONMENT_SHA256,
        "cache_read_allowed": False,
        "fresh_execution": True,
        "result": row.to_dict(),
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


@lru_cache(maxsize=4)
def _report_template(
    output_root: Path = REPORT_OUTPUT_ROOT,
) -> tuple[dict[str, object], dict[str, object]]:
    holdout = load_fresh_redocking_holdout_manifest(
        ROOT / "config/engine_v2_fresh_redocking_holdout_manifest.json"
    )
    reservation = _reservation()
    profiles = tuple(_profile(case) for case in holdout.cases)
    identities = _identities()
    identity_by_engine = {identity.engine_id: identity for identity in identities}
    typed_rows = tuple(
        _row(case, engine_id, output_root=output_root)
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        for case in holdout.cases
    )
    row_map = {(row.engine_id, row.case_id): row for row in typed_rows}
    receipts = [
        _execution_receipt(
            row,
            materialization_receipt_sha256=holdout.case(row.case_id).receipt_sha256,
            identity=identity_by_engine[row.engine_id],
        )
        for row in typed_rows
    ]
    rows = [row.to_dict() for row in typed_rows]
    slots = build_candidate_slot_ledger(
        case_ids=holdout.case_ids,
        engine_v2_rows=rows[:128],
        engine_v2_execution_receipts=receipts[:128],
    )
    policy = PublicRedockingEvaluationPolicy(
        bootstrap_samples=2_000,
        bootstrap_seed=2_026_073_000,
        external_timeout_seconds=300,
        cpu_count=1,
    )
    metrics = [
        metric.to_dict()
        for metric in contract._derive_scope_all_metrics(
            dict(row_map),
            policy=policy,
            analysis_scope="fresh_internal_blind_holdout",
            case_ids=holdout.case_ids,
        )
    ]
    report: dict[str, object] = {
        "schema_id": FRESH_INTERNAL_REPORT_SCHEMA_ID,
        "runner_id": FRESH_RUNNER_ID,
        "analysis_scope": "fresh_internal_blind_holdout",
        "case_count": 128,
        "engine_case_row_count": FRESH_ENGINE_ROW_COUNT,
        "engine_v2_candidate_slot_count": FRESH_ENGINE_V2_SLOT_COUNT,
        "engine_v2_candidate_slots": slots,
        "run_once_reservation_sha256": reservation["reservation_sha256"],
        "fresh_holdout_manifest_sha256": holdout.manifest_sha256,
        "stage0_admission": {
            "policy_sha256": POLICY_SHA256,
            "source_freeze_sha256": SOURCE_FREEZE_SHA256,
            "execution_profile_sha256": PROFILE_SHA256,
            "governance_mode": "independent_three_role",
            "independent_review_complete": True,
            "trusted_review_time_authority_id": "test-clock-authority",
            "trusted_review_time_evidence_sha256": "6" * 64,
            "external_run_once_authority_id": "test-worm-authority",
            "external_run_once_reservation_sha256": "7" * 64,
            "fresh_run_identity_sha256": "8" * 64,
            "docking_pipeline_profile_id": PIPELINE_PROFILE_ID,
            "docking_pipeline_profile_sha256": PIPELINE_SHA256,
        },
        "profiles": [profile.to_dict() for profile in profiles],
        "materializations": [case.to_dict() for case in holdout.cases],
        "engine_identities": [identity.to_dict() for identity in identities],
        "rows": rows,
        "execution_receipts": receipts,
        "policy": policy.to_dict(),
        "metrics": metrics,
        "subgroup_results": derive_fresh_subgroup_results(
            profiles=profiles,
            row_map=row_map,
            policy=policy,
        ),
        "internal_provisional_only": True,
        "scientifically_validated": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "external_independent_review_required_before_public_claim": True,
        "claim_safe": False,
    }
    report["fingerprint_sha256"] = canonical_sha256(report)
    return reservation, report


def _fresh_report(
    output_root: Path = REPORT_OUTPUT_ROOT,
) -> tuple[dict[str, object], dict[str, object]]:
    reservation, report = _report_template(output_root)
    return deepcopy(reservation), deepcopy(report)


def _reseal_report(report: dict[str, object]) -> None:
    report.pop("fingerprint_sha256", None)
    report["fingerprint_sha256"] = canonical_sha256(report)


def _reseal_engine_v2_execution_evidence(report: dict[str, object]) -> None:
    identities = report["engine_identities"]
    rows = report["rows"]
    receipts = report["execution_receipts"]
    assert isinstance(identities, list)
    assert isinstance(rows, list)
    assert isinstance(receipts, list)
    engine_identity = identities[0]
    assert isinstance(engine_identity, dict)
    for row, receipt in zip(rows[:128], receipts[:128], strict=True):
        assert isinstance(row, dict)
        assert isinstance(receipt, dict)
        receipt["command"] = list(row["execution_command"])
        receipt["execution_policy"] = contract._execution_policy_mapping(
            tuple(row["execution_policy"])
        )
        receipt["implementation_sha256"] = engine_identity["implementation_sha256"]
        receipt["result"] = deepcopy(row)
        receipt.pop("receipt_sha256", None)
        receipt["receipt_sha256"] = canonical_sha256(receipt)
    report["engine_v2_candidate_slots"] = build_candidate_slot_ledger(
        case_ids=FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
        engine_v2_rows=rows[:128],
        engine_v2_execution_receipts=receipts[:128],
    )
    _reseal_report(report)


def _write_owner_only(path: Path, payload: dict[str, object]) -> None:
    path.write_bytes(canonical_bytes(payload) + b"\n")
    path.chmod(0o600)


def _stage0_receipt() -> VerifiedStage0Admission:
    return VerifiedStage0Admission._from_verified_policy(
        policy_sha256=POLICY_SHA256,
        source_freeze_sha256=SOURCE_FREEZE_SHA256,
        execution_profile_sha256=PROFILE_SHA256,
        reviewer_id="independent-reviewer",
        operator_id="operator",
        governance_mode="independent_three_role",
        independent_review_complete=True,
        trusted_review_time_authority_id="test-clock-authority",
        trusted_review_time_evidence_sha256="6" * 64,
        external_run_once_authority_id="test-worm-authority",
        external_run_once_reservation_sha256="7" * 64,
        fresh_run_identity_sha256="8" * 64,
        docking_pipeline_profile_id=PIPELINE_PROFILE_ID,
        docking_pipeline_profile_sha256=PIPELINE_SHA256,
        verification_authority=(
            blind_stage0_contract._VERIFIED_STAGE0_ADMISSION_AUTHORITY
        ),
    )


def _write_run_root(tmp_path: Path) -> tuple[Path, VerifiedStage0Admission]:
    config = tmp_path / "config"
    config.mkdir()
    (config / "engine_v2_fresh_redocking_holdout_manifest.json").write_bytes(
        (ROOT / "config/engine_v2_fresh_redocking_holdout_manifest.json").read_bytes()
    )
    root = tmp_path / ".betelgeuze/fresh-redocking-128"
    reservation, report = _fresh_report(root)
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    _write_owner_only(root / FRESH_RESERVATION_FILENAME, reservation)
    stage0 = _stage0_receipt()
    _write_owner_only(
        root / FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME,
        stage0.to_dict(),
    )
    _write_owner_only(
        root / FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME,
        dict(STAGE0_POLICY_DOCUMENT),
    )
    environment_receipt: dict[str, object] = {
        "schema_id": ("betelgeuze.engine_v2_fresh_execution_environment_receipt/1.0.0"),
        "runner_id": FRESH_RUNNER_ID,
        "environment": ENVIRONMENT_DOCUMENT,
        "execution_environment_sha256": ENVIRONMENT_SHA256,
        "boot_session_id_available": True,
        "cache_read_allowed": False,
        "timed_cache_reusable": False,
        "result_values_included": False,
        "claim_safe": False,
    }
    environment_receipt["receipt_sha256"] = canonical_sha256(environment_receipt)
    _write_owner_only(
        root / FRESH_EXECUTION_ENVIRONMENT_FILENAME,
        environment_receipt,
    )

    materialization_directory = root / "receipts/materializations"
    materialization_directory.mkdir(parents=True, mode=0o700)
    (root / "receipts").chmod(0o700)
    materialization_directory.chmod(0o700)
    materializations = report["materializations"]
    assert isinstance(materializations, list)
    for materialization in materializations:
        assert isinstance(materialization, dict)
        _write_owner_only(
            materialization_directory / f"{materialization['case_id']}.json",
            materialization,
        )
    execution_receipts = report["execution_receipts"]
    assert isinstance(execution_receipts, list)
    for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
        engine_directory = root / "receipts" / engine_id
        engine_directory.mkdir(mode=0o700)
        engine_directory.chmod(0o700)
    log_entries: list[dict[str, object]] = []
    empty_stream = {
        "payload_base64": "",
        "retained_byte_count": 0,
        "observed_byte_count": 0,
        "observed_sha256": hashlib.sha256(b"").hexdigest(),
        "payload_complete": True,
    }
    for receipt in execution_receipts:
        assert isinstance(receipt, dict)
        result = receipt["result"]
        assert isinstance(result, dict)
        _write_owner_only(
            root / "receipts" / str(result["engine_id"]) / f"{result['case_id']}.json",
            receipt,
        )
        log_entries.append(
            {
                "engine_id": result["engine_id"],
                "case_id": result["case_id"],
                "status": result["status"],
                "failure_code": result.get("failure_code", ""),
                "execution_receipt_sha256": receipt["receipt_sha256"],
                "execution_environment_sha256": receipt["execution_environment_sha256"],
                "process_log": {
                    "capture_mode": (
                        "structured_in_process"
                        if result["engine_id"] == "engine_v2"
                        else "bounded_subprocess_pipe"
                    ),
                    "timeout_terminated": False,
                    "log_limit_terminated": False,
                    "stdout": dict(empty_stream),
                    "stderr": dict(empty_stream),
                },
            }
        )
    execution_log: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_fresh_execution_log_receipt/1.0.0",
        "runner_id": FRESH_RUNNER_ID,
        "execution_environment_sha256": ENVIRONMENT_SHA256,
        "engine_case_row_count": FRESH_ENGINE_ROW_COUNT,
        "entries": log_entries,
        "entries_sha256": canonical_sha256(log_entries),
        "stdout_stderr_payload_retained": True,
        "structured_execution_receipts_are_authoritative": True,
        "result_replacement_allowed": False,
        "claim_safe": False,
    }
    execution_log["receipt_sha256"] = canonical_sha256(execution_log)
    _write_owner_only(root / FRESH_EXECUTION_LOG_FILENAME, execution_log)

    external_directory = root / "private-external-binary"
    external_directory.mkdir(mode=0o700)
    external_directory.chmod(0o700)
    external_binary = external_directory / EXTERNAL_IMPLEMENTATION_SHA256
    external_binary.write_bytes(EXTERNAL_BINARY_BYTES)
    external_binary.chmod(0o500)
    report_path = root / FRESH_REPORT_FILENAME
    _write_owner_only(report_path, report)
    report_file_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    artifact_manifest = build_fresh_artifact_manifest(
        output_root=root,
        runner_id=FRESH_RUNNER_ID,
        retention_root=".betelgeuze/fresh-redocking-128",
        reservation_sha256=str(reservation["reservation_sha256"]),
        report_fingerprint_sha256=str(report["fingerprint_sha256"]),
        report_file_sha256=report_file_sha256,
        stage0_policy_sha256=POLICY_SHA256,
        source_freeze_sha256=SOURCE_FREEZE_SHA256,
        execution_profile_sha256=PROFILE_SHA256,
        fresh_holdout_manifest_sha256=(FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256),
        completion_filename=FRESH_COMPLETION_FILENAME,
    )
    artifact_manifest_path = root / FRESH_ARTIFACT_MANIFEST_FILENAME
    _write_owner_only(artifact_manifest_path, artifact_manifest)
    completion: dict[str, object] = {
        "schema_id": FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID,
        "runner_id": FRESH_RUNNER_ID,
        "status": "complete",
        "completed_at_unix_ns": 2,
        "reservation_sha256": reservation["reservation_sha256"],
        "report_fingerprint_sha256": report["fingerprint_sha256"],
        "report_file_sha256": report_file_sha256,
        "artifact_manifest_sha256": artifact_manifest["manifest_sha256"],
        "artifact_manifest_file_sha256": hashlib.sha256(
            artifact_manifest_path.read_bytes()
        ).hexdigest(),
        "case_count": 128,
        "engine_case_row_count": FRESH_ENGINE_ROW_COUNT,
        "engine_v2_candidate_slot_count": FRESH_ENGINE_V2_SLOT_COUNT,
        "thresholds_modified_after_results": False,
        "scorer_weights_modified_after_results": False,
        "proposal_allocation_modified_after_results": False,
        "failed_cases_rerun": False,
        "fresh_cases_moved_to_development": False,
    }
    completion["completion_sha256"] = canonical_sha256(completion)
    _write_owner_only(root / FRESH_COMPLETION_FILENAME, completion)
    return root, stage0


def _reseal_terminal_manifest(root: Path) -> None:
    reservation = json.loads(
        (root / FRESH_RESERVATION_FILENAME).read_text(encoding="ascii")
    )
    report_path = root / FRESH_REPORT_FILENAME
    report = json.loads(report_path.read_text(encoding="ascii"))
    manifest = build_fresh_artifact_manifest(
        output_root=root,
        runner_id=FRESH_RUNNER_ID,
        retention_root=".betelgeuze/fresh-redocking-128",
        reservation_sha256=str(reservation["reservation_sha256"]),
        report_fingerprint_sha256=str(report["fingerprint_sha256"]),
        report_file_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
        stage0_policy_sha256=POLICY_SHA256,
        source_freeze_sha256=SOURCE_FREEZE_SHA256,
        execution_profile_sha256=PROFILE_SHA256,
        fresh_holdout_manifest_sha256=(FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256),
        completion_filename=FRESH_COMPLETION_FILENAME,
    )
    manifest_path = root / FRESH_ARTIFACT_MANIFEST_FILENAME
    _write_owner_only(manifest_path, manifest)
    completion: dict[str, object] = {
        "schema_id": FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID,
        "runner_id": FRESH_RUNNER_ID,
        "status": "complete",
        "completed_at_unix_ns": 2,
        "reservation_sha256": reservation["reservation_sha256"],
        "report_fingerprint_sha256": report["fingerprint_sha256"],
        "report_file_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "artifact_manifest_sha256": manifest["manifest_sha256"],
        "artifact_manifest_file_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "case_count": 128,
        "engine_case_row_count": FRESH_ENGINE_ROW_COUNT,
        "engine_v2_candidate_slot_count": FRESH_ENGINE_V2_SLOT_COUNT,
        "thresholds_modified_after_results": False,
        "scorer_weights_modified_after_results": False,
        "proposal_allocation_modified_after_results": False,
        "failed_cases_rerun": False,
        "fresh_cases_moved_to_development": False,
    }
    completion["completion_sha256"] = canonical_sha256(completion)
    _write_owner_only(root / FRESH_COMPLETION_FILENAME, completion)


def test_fresh_run_root_verifies_frozen_typed_denominators(
    tmp_path: Path,
) -> None:
    root, stage0 = _write_run_root(tmp_path)

    verified = verify_fresh_run_root(
        root,
        repo_root=tmp_path,
        source_repo_root=ROOT,
        verified_stage0_receipt=stage0,
    )

    assert verified.engine_case_row_count == 384
    assert verified.engine_v2_candidate_slot_count == 8_192
    assert verified.stage0_policy_verified is True
    assert verified.stage0_binding_authority == "verified_stage0_receipt"
    assert verified.to_dict()["single_local_attempt_marker_verified"] is True
    assert verified.to_dict()["exactly_once_verified"] is False
    assert (
        verified.to_dict()["external_worm_reservation_cryptographically_verified"]
        is True
    )
    assert verified.artifact_manifest_sha256
    assert verified.artifact_manifest_file_sha256


def test_completion_is_preverified_before_publication(tmp_path: Path) -> None:
    root, stage0 = _write_run_root(tmp_path)
    completion_path = root / FRESH_COMPLETION_FILENAME
    completion = json.loads(completion_path.read_text(encoding="ascii"))
    completion_path.unlink()

    prepublication = verify_fresh_run_root(
        root,
        repo_root=tmp_path,
        source_repo_root=ROOT,
        verified_stage0_receipt=stage0,
        proposed_completion_document=completion,
    )
    _write_owner_only(completion_path, completion)
    terminal = verify_fresh_run_root(
        root,
        repo_root=tmp_path,
        source_repo_root=ROOT,
        verified_stage0_receipt=stage0,
    )

    assert terminal == prepublication


def test_terminal_failure_receipt_is_permanent_and_nonclaimable() -> None:
    failure: dict[str, object] = {
        "schema_id": FRESH_RUN_TERMINAL_FAILURE_SCHEMA_ID,
        "runner_id": FRESH_RUNNER_ID,
        "status": "failed_terminal",
        "failed_at_unix_ns": 3,
        "reservation_sha256": "a" * 64,
        "exception_type": "builtins.RuntimeError",
        "private_error_sha256": "b" * 64,
        "private_error_byte_length": 17,
        "completion_published": False,
        "rerun_allowed": False,
        "result_replacement_allowed": False,
        "claim_safe": False,
    }
    failure["failure_sha256"] = canonical_sha256(failure)

    assert (
        verify_terminal_failure_document(
            failure,
            reservation_sha256="a" * 64,
        )
        == failure["failure_sha256"]
    )
    assert FRESH_FAILURE_FILENAME.endswith("terminal-failure.json")


def test_fresh_run_root_rejects_retained_receipt_changed_after_manifest(
    tmp_path: Path,
) -> None:
    root, stage0 = _write_run_root(tmp_path)
    case_id = FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0]
    receipt_path = root / "receipts/vina" / f"{case_id}.json"
    receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
    receipt_path.chmod(0o600)

    with pytest.raises(FreshRunVerificationError, match="artifact manifest"):
        verify_fresh_run_root(
            root,
            repo_root=tmp_path,
            source_repo_root=ROOT,
            verified_stage0_receipt=stage0,
        )


def test_fresh_run_root_rejects_resealed_crosswired_disk_receipt(
    tmp_path: Path,
) -> None:
    root, stage0 = _write_run_root(tmp_path)
    first, second = FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[:2]
    first_path = root / "receipts/gnina" / f"{first}.json"
    second_path = root / "receipts/gnina" / f"{second}.json"
    first_path.write_bytes(second_path.read_bytes())
    first_path.chmod(0o600)
    _reseal_terminal_manifest(root)

    with pytest.raises(
        FreshRunVerificationError,
        match="differs from its report ledger",
    ):
        verify_fresh_run_root(
            root,
            repo_root=tmp_path,
            source_repo_root=ROOT,
            verified_stage0_receipt=stage0,
        )


def test_fresh_run_root_on_disk_binding_does_not_claim_policy_verification(
    tmp_path: Path,
) -> None:
    root, _ = _write_run_root(tmp_path)

    verified = verify_fresh_run_root(
        root,
        repo_root=tmp_path,
        source_repo_root=ROOT,
    )

    assert verified.stage0_policy_verified is False
    assert verified.stage0_binding_authority == ("on_disk_stage0_admission_receipt")
    assert (
        verified.to_dict()["external_worm_reservation_cryptographically_verified"]
        is False
    )


def test_offline_verifier_rejects_report_evaluation_pipeline_cross_wire() -> None:
    _, report = _fresh_report()
    identities = report["engine_identities"]
    assert isinstance(identities, list)
    for identity in identities:
        assert isinstance(identity, dict)
        identity["evaluation_pipeline_sha256"] = "9" * 64
    environment_receipt = {
        "environment": deepcopy(ENVIRONMENT_DOCUMENT),
    }

    with pytest.raises(
        FreshRunVerificationError,
        match="report evaluation pipeline differs",
    ):
        verifier._verify_prebound_runtime_authority(
            stage0_policy=STAGE0_POLICY_DOCUMENT,
            environment_receipt=environment_receipt,
            report=report,
        )


def test_offline_verifier_rejects_runtime_dependency_ledger_cross_wire() -> None:
    _, report = _fresh_report()
    environment = deepcopy(ENVIRONMENT_DOCUMENT)
    authority = environment["runtime_dependency_authority"]
    assert isinstance(authority, dict)
    ledgers = authority["installed_distribution_file_ledger_sha256s"]
    assert isinstance(ledgers, dict)
    ledgers["torch"] = "9" * 64
    authority.pop("authority_sha256")
    authority["authority_sha256"] = canonical_sha256(authority)

    with pytest.raises(
        FreshRunVerificationError,
        match="runtime environment differs",
    ):
        verifier._verify_prebound_runtime_authority(
            stage0_policy=STAGE0_POLICY_DOCUMENT,
            environment_receipt={"environment": environment},
            report=report,
        )
def test_fresh_run_root_accepts_reverified_stage0_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, stage0 = _write_run_root(tmp_path)
    policy_path = tmp_path / "stage0-policy.json"
    gnina_path = tmp_path / "gnina"
    observed: dict[str, Path] = {}

    def fake_verify_stage0_admission(
        candidate_policy_path: Path,
        *,
        repo_root: Path,
        gnina_path: Path,
        output_root: Path,
    ) -> VerifiedStage0Admission:
        observed.update(
            {
                "policy_path": candidate_policy_path,
                "repo_root": repo_root,
                "gnina_path": gnina_path,
                "output_root": output_root,
            }
        )
        return stage0

    monkeypatch.setattr(
        verifier,
        "verify_stage0_admission",
        fake_verify_stage0_admission,
    )

    verified = verify_fresh_run_root(
        root,
        repo_root=tmp_path,
        source_repo_root=ROOT,
        stage0_policy_path=policy_path,
        gnina_path=gnina_path,
    )

    assert verified.stage0_policy_verified is True
    assert verified.stage0_binding_authority == "verified_stage0_policy"
    assert observed == {
        "policy_path": policy_path,
        "repo_root": tmp_path,
        "gnina_path": gnina_path,
        "output_root": root,
    }


def test_current_runner_stage0_pipeline_policy_is_accepted() -> None:
    holdout = load_fresh_redocking_holdout_manifest(
        ROOT / "config/engine_v2_fresh_redocking_holdout_manifest.json"
    )
    row = _row(holdout.cases[0], "engine_v2")
    current_policy = runner._engine_v2_execution_policy(
        runner.ScorerBackend.RUST_CPU_REQUIRED,
        execution_profile_sha256=PROFILE_SHA256,
    )
    current_row = replace(
        row,
        execution_policy=runner._execution_policy_tokens(current_policy),
    )

    verifier._validate_row_policy(
        current_row,
        execution_profile_sha256=PROFILE_SHA256,
        policy=PublicRedockingEvaluationPolicy(
            bootstrap_samples=2_000,
            bootstrap_seed=2_026_073_000,
            external_timeout_seconds=300,
            cpu_count=1,
        ),
        engine_v2_pipeline_profile_id=PIPELINE_PROFILE_ID,
        engine_v2_pipeline_profile_sha256=PIPELINE_SHA256,
    )


def test_current_runner_engine_v2_commands_match_fresh_canonical_builder() -> None:
    holdout = load_fresh_redocking_holdout_manifest(
        ROOT / "config/engine_v2_fresh_redocking_holdout_manifest.json"
    )
    output_root = ROOT / ".betelgeuze/fresh-redocking-128"
    for case in holdout.cases:
        paths = runner._case_paths(output_root / "inputs", case.case_id)
        assert runner._engine_v2_command(
            case.case_id,
            paths,
            output=output_root / "poses/engine_v2" / f"{case.case_id}.sdf",
            seed=case.seed,
            scorer_backend=runner.ScorerBackend.RUST_CPU_REQUIRED,
        ) == fresh_engine_v2_execution_command(
            case.case_id,
            output_root=output_root,
        )


def test_fresh_report_rejects_resealed_arbitrary_engine_v2_command() -> None:
    reservation, report = _fresh_report()
    rows = report["rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["execution_command"] = ["/bin/true"]
    _reseal_engine_v2_execution_evidence(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="Engine V2 command is not canonical",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_engine_v2_command_root_crosswire() -> None:
    reservation, report = _fresh_report()

    with pytest.raises(
        FreshRunVerificationError,
        match="command output root is cross-wired",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
            expected_output_root=ROOT / ".betelgeuze/other-fresh-root",
        )


def test_fresh_report_rejects_engine_v2_command_root_outside_retention() -> None:
    reservation, report = _fresh_report(
        ROOT.parent / ".betelgeuze-fresh-verifier-outside-repository"
    )

    with pytest.raises(
        FreshRunVerificationError,
        match="command root escapes the repository",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_resealed_engine_v2_implementation_hash() -> None:
    reservation, report = _fresh_report()
    identities = report["engine_identities"]
    assert isinstance(identities, list)
    assert isinstance(identities[0], dict)
    identities[0]["implementation_sha256"] = "a" * 64
    _reseal_engine_v2_execution_evidence(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="implementation does not match the source closure",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_resealed_engine_v2_pipeline_profile_hash() -> None:
    reservation, report = _fresh_report()
    rows = report["rows"]
    assert isinstance(rows, list)
    for row in rows[:128]:
        assert isinstance(row, dict)
        policy = contract._execution_policy_mapping(tuple(row["execution_policy"]))
        policy["docking_pipeline_profile_sha256"] = "b" * 64
        row["execution_policy"] = list(_policy_tokens(policy))
    _reseal_engine_v2_execution_evidence(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="Engine V2 row policy is not frozen",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_resealed_stage0_pipeline_profile_hash() -> None:
    reservation, report = _fresh_report()
    admission = report["stage0_admission"]
    assert isinstance(admission, dict)
    admission["docking_pipeline_profile_sha256"] = "b" * 64
    _reseal_report(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="Stage 0 pipeline profile is not source authoritative",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_solo_stage0_governance_even_if_resealed() -> None:
    reservation, report = _fresh_report()
    admission = report["stage0_admission"]
    assert isinstance(admission, dict)
    admission["governance_mode"] = "solo_developer_controlled"
    admission["independent_review_complete"] = False
    _reseal_report(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="completed independent Stage 0 governance",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )

    tampered_receipt = _stage0_receipt()
    object.__setattr__(
        tampered_receipt,
        "governance_mode",
        "solo_developer_controlled",
    )
    object.__setattr__(tampered_receipt, "independent_review_complete", False)
    with pytest.raises(
        runner.Stage0AdmissionError,
        match="stage0_admission_receipt_changed",
    ):
        runner._require_fresh_independent_stage0(tampered_receipt)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda report: report["profiles"][0].update({"case_id": "AAAA_AAA"}),
            "profile is not typed",
        ),
        (
            lambda report: report["rows"].__setitem__(
                0,
                {
                    "engine_id": "engine_v2",
                    "case_id": FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0],
                    "status": "failure",
                },
            ),
            "row is not typed",
        ),
        (
            lambda report: report.__setitem__("metrics", []),
            "metrics do not recompute",
        ),
        (
            lambda report: report["materializations"].__setitem__(
                0,
                {"case_id": FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0]},
            ),
            "materialization is not typed",
        ),
    ),
)
def test_fresh_report_rejects_resealed_untyped_or_derived_evidence(
    mutation: object,
    message: str,
) -> None:
    reservation, report = _fresh_report()
    mutation(report)
    _reseal_report(report)

    with pytest.raises(FreshRunVerificationError, match=message):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_resealed_closed_receipt_schema() -> None:
    reservation, report = _fresh_report()
    receipts = report["execution_receipts"]
    assert isinstance(receipts, list)
    receipt = receipts[0]
    assert isinstance(receipt, dict)
    receipt.pop("execution_environment_sha256")
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _reseal_report(report)

    with pytest.raises(FreshRunVerificationError, match="receipt is cross-wired"):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_report_rejects_resealed_slot_tampering() -> None:
    reservation, report = _fresh_report()
    slots = report["engine_v2_candidate_slots"]
    assert isinstance(slots, list)
    slots[0]["preparation_failure_code"] = "changed_after_result"
    _reseal_report(report)

    with pytest.raises(
        FreshRunVerificationError,
        match="preparation-failure slot is invalid",
    ):
        verify_fresh_report_document(
            report,
            reservation_sha256=str(reservation["reservation_sha256"]),
            repo_root=ROOT,
        )


def test_fresh_run_root_rejects_symlink_and_non_owner_only_file(
    tmp_path: Path,
) -> None:
    root, stage0 = _write_run_root(tmp_path)
    real_root = tmp_path / "fresh-redocking-128-real"
    root.rename(real_root)
    root.symlink_to(real_root, target_is_directory=True)
    with pytest.raises(FreshRunVerificationError, match="symlink component"):
        verify_fresh_run_root(
            root,
            repo_root=tmp_path,
            source_repo_root=ROOT,
            verified_stage0_receipt=stage0,
        )

    root.unlink()
    real_root.rename(root)
    (root / FRESH_REPORT_FILENAME).chmod(0o644)
    with pytest.raises(FreshRunVerificationError, match="bounded owned regular file"):
        verify_fresh_run_root(
            root,
            repo_root=tmp_path,
            source_repo_root=ROOT,
            verified_stage0_receipt=stage0,
        )


def test_fresh_run_root_rejects_symlinked_repository_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    _write_run_root(real_root)
    alias = tmp_path / "repo-alias"
    alias.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(FreshRunVerificationError, match="symlink component"):
        verify_fresh_run_root(
            alias / ".betelgeuze/fresh-redocking-128",
            repo_root=alias,
            source_repo_root=ROOT,
        )


def test_reservation_rejects_noncanonical_retention_root() -> None:
    reservation = _reservation()
    reservation["retention_root"] = ".betelgeuze/../outside"
    reservation.pop("reservation_sha256")
    reservation["reservation_sha256"] = canonical_sha256(reservation)

    with pytest.raises(FreshRunVerificationError, match="policy is invalid"):
        verify_reservation_document(reservation)


def test_runner_run_once_reservation_requires_live_atomic_consume_authority(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / ".betelgeuze/fresh-redocking-128"
    output_root.mkdir(parents=True, mode=0o700)
    receipt = _stage0_receipt()

    with pytest.raises(blind_stage0_contract.Stage0AdmissionError) as raised:
        runner._reserve_fresh_run_once(
            repo_root=tmp_path,
            output_root=output_root,
            case_ids=FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
            manifest_sha256=FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256,
            stage0_receipt=receipt,
        )

    assert raised.value.blockers == (
        "fresh_live_run_once_consumption_authority_unavailable",
    )
    assert not (output_root / FRESH_RESERVATION_FILENAME).exists()


def test_nonpristine_fresh_root_does_not_create_marker_without_live_authority(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / ".betelgeuze/fresh-redocking-128"
    output_root.mkdir(parents=True, mode=0o700)
    (output_root / "prior-artifact").write_text("prior", encoding="utf-8")

    with pytest.raises(blind_stage0_contract.Stage0AdmissionError) as raised:
        runner._reserve_fresh_run_once(
            repo_root=tmp_path,
            output_root=output_root,
            case_ids=FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
            manifest_sha256=FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256,
            stage0_receipt=_stage0_receipt(),
        )

    assert raised.value.blockers == (
        "fresh_live_run_once_consumption_authority_unavailable",
    )
    assert not (output_root / FRESH_RESERVATION_FILENAME).exists()
