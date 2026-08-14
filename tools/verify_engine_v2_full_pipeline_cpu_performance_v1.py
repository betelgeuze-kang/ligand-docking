#!/usr/bin/env python3
"""Verify the non-consuming full-pipeline synthetic CPU implementation profile."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEASUREMENT_CORE = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1.py"
)
_PROFILE_MODULE_NAME = "betelgeuze_engine_v2.docking.full_pipeline_cpu_performance_v1"


def _load_measurement_core() -> Any:
    existing = sys.modules.get(_PROFILE_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        _PROFILE_MODULE_NAME,
        DEFAULT_MEASUREMENT_CORE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("full-pipeline CPU measurement core cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PROFILE_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(_PROFILE_MODULE_NAME, None)
        raise
    return module


profile = _load_measurement_core()


DEFAULT_PROFILE = (
    REPOSITORY_ROOT / "config/engine_v2_full_pipeline_cpu_performance_v1.json"
)
DEFAULT_ARTIFACT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_native_cpu_runtime_artifacts_v1.json"
)
DEFAULT_PREDECESSOR_PROFILE = (
    REPOSITORY_ROOT / "config/engine_v2_cpu_performance_profile_v3.json"
)
DEFAULT_PREDECESSOR_ACTIVATION = (
    REPOSITORY_ROOT / "config/engine_v2_cpu_performance_v3_runner_activation.json"
)
DEFAULT_NATIVE_PARITY_POLICY = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_cpu_parity_v1.json"
)
DEFAULT_NATIVE_SOURCE_POLICY = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
)
DEFAULT_NATIVE_SESSION_POLICY = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_session_v1.json"
)
DEFAULT_NATIVE_CONSUMER = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_fixed64_consumers.py"
)
DEFAULT_NATIVE_PARITY_SOURCE = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_cpu_parity.py"
)
DEFAULT_HOST_PREFLIGHT = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py"
)
DEFAULT_RUNNER = (
    REPOSITORY_ROOT / "tools/run_engine_v2_full_pipeline_cpu_performance_v1.py"
)
DEFAULT_TEST = (
    REPOSITORY_ROOT / "tests/unit/test_engine_v2_full_pipeline_cpu_performance_v1.py"
)
DEFAULT_VERIFIER_TEST = (
    REPOSITORY_ROOT
    / "tests/unit/test_verify_engine_v2_full_pipeline_cpu_performance_v1.py"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_full_pipeline_cpu_performance_v1.md"
)
DEFAULT_MAIN_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-main.yml"
DEFAULT_RELEASE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
)
DEFAULT_NATIVE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"
)
DEFAULT_DURABLE_ARCHIVE_ROOT = REPOSITORY_ROOT

PROFILE_SHA256 = "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
ARTIFACT_CONTRACT_SHA256 = (
    "195abc14487ccec4d0f8065fa0e642337ce42691cebee4f47106b94bd2d0ebe8"
)
PREDECESSOR_PROFILE_SHA256 = (
    "21facfc62956b402d4a43e5b68389083bacaa3d3afd753eb6b1da3578c8bb6b3"
)
PREDECESSOR_ACTIVATION_SHA256 = (
    "3a309594b35cf0e14d4efd4f01146a6849218509c43f4f024b1d765e6d647bda"
)
NATIVE_PARITY_POLICY_SHA256 = (
    "47d3fd8a0fe341591d46c0427dc45d726898813e953b039ce66fd47816ad1511"
)
NATIVE_SOURCE_POLICY_SHA256 = (
    "2dbd7da6c8a2b7e6612eabbf15c118bddd659629f974374aac6bccc22deb7e96"
)
NATIVE_SESSION_POLICY_SHA256 = (
    "51f314de529f1ed3b000bdfff2f7f3494a308303f5d6acf19ab517b3e7054de3"
)

AUTHORITY_KEYS = frozenset(
    {
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_execution_authorized",
        "product_performance_claim_authorized",
        "public_benchmark_authorized",
        "reservation_authorized",
        "scientific_claim_authorized",
        "stage0_admission_authorized",
        "synthetic_cpu_performance_qualification_authorized",
    }
)


class FullPipelineCPUPerformanceProfileError(RuntimeError):
    """Raised when the frozen implementation profile or its wiring drifts."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise FullPipelineCPUPerformanceProfileError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load_profile(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                FullPipelineCPUPerformanceProfileError(
                    f"non-finite JSON constant: {value}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullPipelineCPUPerformanceProfileError(
            f"invalid full-pipeline CPU profile JSON: {exc}"
        ) from exc
    if type(document) is not dict:
        raise FullPipelineCPUPerformanceProfileError(
            "full-pipeline CPU profile must be an exact object"
        )
    expected = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != expected:
        raise FullPipelineCPUPerformanceProfileError(
            "full-pipeline CPU profile is not canonical indented JSON"
        )
    return document, raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_sha(path: Path, expected: str, *, name: str) -> None:
    if _sha256(path) != expected:
        raise FullPipelineCPUPerformanceProfileError(f"{name} SHA-256 changed")


def _require_exact(value: object, expected: object, *, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise FullPipelineCPUPerformanceProfileError(f"{name} changed")


def _require_snippets(path: Path, snippets: tuple[str, ...]) -> None:
    raw = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in raw]
    if missing:
        raise FullPipelineCPUPerformanceProfileError(
            f"{path.name} missing frozen snippets: {missing}"
        )


def verify(
    *,
    profile_path: Path = DEFAULT_PROFILE,
    artifact_contract_path: Path = DEFAULT_ARTIFACT_CONTRACT,
    predecessor_profile_path: Path = DEFAULT_PREDECESSOR_PROFILE,
    predecessor_activation_path: Path = DEFAULT_PREDECESSOR_ACTIVATION,
    native_parity_policy_path: Path = DEFAULT_NATIVE_PARITY_POLICY,
    native_source_policy_path: Path = DEFAULT_NATIVE_SOURCE_POLICY,
    native_session_policy_path: Path = DEFAULT_NATIVE_SESSION_POLICY,
    measurement_core_path: Path = DEFAULT_MEASUREMENT_CORE,
    native_consumer_path: Path = DEFAULT_NATIVE_CONSUMER,
    native_parity_source_path: Path = DEFAULT_NATIVE_PARITY_SOURCE,
    host_preflight_path: Path = DEFAULT_HOST_PREFLIGHT,
    runner_path: Path = DEFAULT_RUNNER,
    test_path: Path = DEFAULT_TEST,
    verifier_test_path: Path = DEFAULT_VERIFIER_TEST,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    main_workflow_path: Path = DEFAULT_MAIN_WORKFLOW,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
    durable_archive_root: Path = DEFAULT_DURABLE_ARCHIVE_ROOT,
    artifact_directory: Path | None = None,
    runtime_root: Path | None = None,
) -> dict[str, object]:
    document, raw = _load_profile(profile_path)
    expected_top_level = frozenset(
        {
            "activation",
            "artifact_binding",
            "authority",
            "gates",
            "measurement",
            "predecessor_disposition",
            "profile_id",
            "restrictions",
            "runtime_binding",
            "schema_id",
            "status",
            "workload",
        }
    )
    _require_exact(frozenset(document), expected_top_level, name="profile keys")
    _require_exact(document["schema_id"], profile.PROFILE_SCHEMA_ID, name="schema_id")
    _require_exact(document["profile_id"], profile.PROFILE_ID, name="profile_id")
    _require_exact(
        document["status"],
        "frozen_implementation_profile_execution_not_activated",
        name="status",
    )
    profile_sha256 = hashlib.sha256(raw).hexdigest()
    if profile_sha256 != PROFILE_SHA256 or profile.PROFILE_SHA256 != PROFILE_SHA256:
        raise FullPipelineCPUPerformanceProfileError("profile SHA-256 changed")

    authority = document["authority"]
    if (
        type(authority) is not dict
        or frozenset(authority) != AUTHORITY_KEYS
        or any(value is not False for value in authority.values())
    ):
        raise FullPipelineCPUPerformanceProfileError(
            "full-pipeline CPU authority is not all false"
        )
    restrictions = document["restrictions"]
    if (
        type(restrictions) is not dict
        or not restrictions
        or any(value is not False for value in restrictions.values())
    ):
        raise FullPipelineCPUPerformanceProfileError(
            "full-pipeline CPU restrictions granted authority"
        )
    activation = document["activation"]
    if type(activation) is not dict:
        raise FullPipelineCPUPerformanceProfileError("activation boundary is absent")
    expected_activation_false = (
        "activation_contract_present",
        "github_actions_live_execution_allowed",
        "implementation_profile_allows_live_execution",
        "profile_change_after_activation_allowed",
        "qualification_attempt_consumed",
        "reservation_created",
    )
    if any(activation.get(name) is not False for name in expected_activation_false):
        raise FullPipelineCPUPerformanceProfileError(
            "implementation profile activated execution"
        )
    if (
        activation.get("exactly_once_local_synthetic_attempt_required") is not True
        or activation.get("separate_activation_contract_required") is not True
        or type(activation.get("source_binding_fields_required")) is not list
        or len(activation["source_binding_fields_required"]) != 11
    ):
        raise FullPipelineCPUPerformanceProfileError(
            "activation source-binding contract changed"
        )

    artifact = document["artifact_binding"]
    runtime = document["runtime_binding"]
    measurement = document["measurement"]
    predecessor = document["predecessor_disposition"]
    gates = document["gates"]
    workload = document["workload"]
    for name, value in (
        ("artifact binding", artifact),
        ("runtime binding", runtime),
        ("measurement", measurement),
        ("predecessor disposition", predecessor),
        ("gates", gates),
        ("workload", workload),
    ):
        if type(value) is not dict:
            raise FullPipelineCPUPerformanceProfileError(f"{name} is absent")
    _require_exact(
        artifact["artifact_contract_sha256"],
        ARTIFACT_CONTRACT_SHA256,
        name="artifact contract binding",
    )
    _require_exact(
        artifact["workflow_head_sha"],
        "3330faa43c7fc8640d89babd84ac444c5959157c",
        name="main-push source head",
    )
    _require_exact(artifact["event_name"], "push", name="artifact event")
    _require_exact(artifact["ref"], "refs/heads/main", name="artifact ref")
    _require_exact(artifact["run_conclusion"], "success", name="artifact run")
    _require_exact(artifact["abi"], "cp310-cp310", name="artifact ABI")
    _require_exact(
        artifact["artifact_directory_manifest_sha256"],
        profile.EXPECTED_ARTIFACT_MANIFEST_SHA256,
        name="artifact payload manifest",
    )
    _require_exact(
        artifact["payloads"],
        [dict(row) for row in profile.EXPECTED_ARTIFACT_ROWS],
        name="artifact payload rows",
    )
    durable_archive = artifact.get("durable_repository_archive")
    if type(durable_archive) is not dict:
        raise FullPipelineCPUPerformanceProfileError(
            "durable repository archive binding is absent"
        )
    _require_exact(
        durable_archive,
        {
            "actions_artifact_expires_at": "2026-08-28T08:48:29Z",
            "actions_artifact_is_transport_only": True,
            "archive_format": "git_history_tracked_exact_payloads_v1",
            "payloads": [dict(row) for row in profile.EXPECTED_DURABLE_ARCHIVE_ROWS],
            "required_before_activation": True,
        },
        name="durable repository archive binding",
    )
    _require_exact(
        runtime["site_packages_rows"],
        [dict(row) for row in profile.EXPECTED_SITE_ROWS],
        name="runtime site-packages rows",
    )
    _require_exact(
        runtime["site_packages_manifest_sha256"],
        profile.EXPECTED_SITE_MANIFEST_SHA256,
        name="site-packages manifest",
    )
    _require_exact(
        runtime["runtime_scope_manifest_sha256"],
        profile.EXPECTED_RUNTIME_SCOPE_MANIFEST_SHA256,
        name="runtime scope manifest",
    )
    _require_exact(
        runtime["native_extension_sha256"],
        str(profile.EXPECTED_SITE_ROWS[-1]["sha256"]),
        name="native extension",
    )
    _require_exact(
        runtime["python_executable_sha256"],
        profile.EXPECTED_PYTHON_SHA256,
        name="CPython executable",
    )
    _require_exact(
        runtime["python_shared_library_sha256"],
        profile.EXPECTED_PYTHON_SHARED_LIBRARY_SHA256,
        name="CPython shared library",
    )
    _require_exact(runtime["numpy_allowed"], False, name="NumPy restriction")
    _require_exact(
        runtime["bootstrap_flags"], ["-I", "-S", "-B"], name="bootstrap flags"
    )
    _require_exact(
        measurement["baseline_backend"],
        profile.BASELINE_BACKEND,
        name="baseline backend",
    )
    _require_exact(
        measurement["experimental_backend"],
        profile.EXPERIMENTAL_BACKEND,
        name="experimental backend",
    )
    _require_exact(
        measurement["sample_count_per_backend"],
        profile.SAMPLE_COUNT,
        name="sample count",
    )
    _require_exact(
        measurement["warmup_count_per_backend"],
        profile.WARMUP_COUNT,
        name="warmup count",
    )
    _require_exact(
        measurement["percentile_numerators"],
        list(profile.PERCENTILE_NUMERATORS),
        name="descriptive percentiles",
    )
    _require_exact(
        measurement["schedule_id"],
        "paired_alternating_ab_ba_v1",
        name="measurement schedule",
    )
    _require_exact(
        measurement["result_cache_allowed"], False, name="result cache policy"
    )
    _require_exact(gates["speed_threshold_present"], False, name="speed threshold")
    _require_exact(
        gates["native_cpu_full_numeric_parity_required"],
        True,
        name="full numeric parity gate",
    )
    _require_exact(workload["candidate_denominator"], 64, name="candidate denominator")
    _require_exact(workload["consumer_surface"], "benchmark", name="consumer surface")
    _require_exact(
        workload["synthetic_only_acknowledgment"],
        profile.SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        name="synthetic-only acknowledgment",
    )
    _require_exact(
        predecessor["predecessor_profile_sha256"],
        PREDECESSOR_PROFILE_SHA256,
        name="predecessor profile",
    )
    _require_exact(
        predecessor["predecessor_activation_sha256"],
        PREDECESSOR_ACTIVATION_SHA256,
        name="predecessor activation",
    )
    for name in (
        "attempt_consumed",
        "predecessor_runtime_artifact_available",
        "predecessor_runtime_reconstructed_allowed",
        "predecessor_terminal_state_present",
        "rerun_performed",
        "successor_reinterprets_predecessor_result",
    ):
        _require_exact(predecessor[name], False, name=f"predecessor {name}")
    _require_exact(
        predecessor["attempt_state_observed_at_utc"],
        "2026-08-14T09:16:36Z",
        name="predecessor state observation time",
    )
    _require_exact(
        predecessor["attempt_state_observer_effective_uid"],
        1000,
        name="predecessor state observer uid",
    )
    _require_exact(
        predecessor["attempt_state_observer_login"],
        "betelgeuze",
        name="predecessor state observer login",
    )

    _require_sha(
        artifact_contract_path,
        ARTIFACT_CONTRACT_SHA256,
        name="native artifact contract",
    )
    _require_sha(
        predecessor_profile_path,
        PREDECESSOR_PROFILE_SHA256,
        name="predecessor profile",
    )
    _require_sha(
        predecessor_activation_path,
        PREDECESSOR_ACTIVATION_SHA256,
        name="predecessor activation",
    )
    _require_sha(
        native_parity_policy_path,
        NATIVE_PARITY_POLICY_SHA256,
        name="native CPU parity policy",
    )
    _require_sha(
        native_source_policy_path,
        NATIVE_SOURCE_POLICY_SHA256,
        name="native synthetic source policy",
    )
    _require_sha(
        native_session_policy_path,
        NATIVE_SESSION_POLICY_SHA256,
        name="native synthetic session policy",
    )
    _require_snippets(
        measurement_core_path,
        (
            "def verify_local_runtime_binding(",
            "def _run_injected_test_double(",
            "def _compare_backend_evidence(",
            "EXPECTED_PARITY_F64_COUNT: Final = 16_896",
            "def run_live_full_pipeline_cpu_performance_v1(",
            "full-pipeline CPU performance v1 execution is not activated",
            PROFILE_SHA256,
        ),
    )
    _require_snippets(
        native_consumer_path,
        (
            "class NativeRepositorySyntheticD0PreparedSessionV1:",
            "def prepare_repository_synthetic_d0_session(",
            "complete ScorerV1 term receipt changed",
        ),
    )
    _require_snippets(
        native_parity_source_path,
        (
            "def run_repository_synthetic_d0_cpu_parity(",
            "performance_measurement_performed",
            NATIVE_PARITY_POLICY_SHA256,
        ),
    )
    _require_snippets(
        host_preflight_path,
        ("def derive_host_preflight_evidence_v3(", "cpu_boost_not_disabled"),
    )
    _require_snippets(
        runner_path,
        (
            "--verify-implementation",
            "--verify-local-runtime",
            "--run-output",
            "run_live_full_pipeline_cpu_performance_v1",
        ),
    )
    _require_snippets(
        test_path,
        (
            "test_injected_full_pipeline_measurement_uses_fixed_paired_schedule",
            "test_live_full_pipeline_measurement_is_not_activated",
        ),
    )
    _require_snippets(
        verifier_test_path,
        (
            "test_full_pipeline_cpu_performance_profile_verifies",
            "test_full_pipeline_cpu_performance_profile_rejects_authority_drift",
        ),
    )
    _require_snippets(
        documentation_path,
        (
            "main-push cp310 artifact",
            "does not consume the predecessor v3 attempt",
            "No speed threshold",
            "separate activation PR",
        ),
    )
    workflow_tokens = (
        "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1.py",
        "config/engine_v2_full_pipeline_cpu_performance_v1.json",
        "tools/verify_engine_v2_full_pipeline_cpu_performance_v1.py",
        "tests/unit/test_engine_v2_full_pipeline_cpu_performance_v1.py",
        "tests/unit/test_verify_engine_v2_full_pipeline_cpu_performance_v1.py",
        "docs/engine_v2_full_pipeline_cpu_performance_v1.md",
        "packaging/engine-v2/native-runtime-archive",
    )
    for workflow_path in (
        main_workflow_path,
        release_workflow_path,
        native_workflow_path,
    ):
        _require_snippets(workflow_path, workflow_tokens)

    try:
        durable_archive_evidence = profile.verify_durable_repository_archive(
            repository_root=durable_archive_root
        ).to_dict()
    except profile.FullPipelineCPUPerformanceV1Error as exc:
        raise FullPipelineCPUPerformanceProfileError(
            "durable repository archive verification failed"
        ) from exc

    if (artifact_directory is None) is not (runtime_root is None):
        raise FullPipelineCPUPerformanceProfileError(
            "artifact directory and runtime root must be supplied together"
        )
    local_evidence: dict[str, object] | None = None
    if artifact_directory is not None and runtime_root is not None:
        local_evidence = profile.verify_local_runtime_binding(
            artifact_directory=artifact_directory,
            runtime_root=runtime_root,
        ).to_dict()
    return {
        "schema_id": document["schema_id"],
        "profile_id": document["profile_id"],
        "status": "verified_implementation_execution_not_activated",
        "profile_sha256": profile_sha256,
        "artifact_workflow_head_sha": artifact["workflow_head_sha"],
        "artifact_id": artifact["artifact_id"],
        "artifact_abi": artifact["abi"],
        "native_extension_sha256": runtime["native_extension_sha256"],
        "candidate_denominator": workload["candidate_denominator"],
        "sample_count_per_backend": measurement["sample_count_per_backend"],
        "speed_threshold_present": gates["speed_threshold_present"],
        "all_authority_false": True,
        "execution_activated": False,
        "qualification_consumed": False,
        "predecessor_attempt_consumed": False,
        "reservation_created": False,
        "durable_repository_archive_verified": True,
        "durable_repository_archive_evidence": durable_archive_evidence,
        "local_runtime_verified": local_evidence is not None,
        "local_runtime_evidence": local_evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    arguments = parser.parse_args()
    result = verify(
        profile_path=arguments.profile,
        artifact_directory=arguments.artifact_directory,
        runtime_root=arguments.runtime_root,
    )
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
