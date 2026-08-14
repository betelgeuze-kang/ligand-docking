#!/usr/bin/env python3
"""Verify the frozen, non-authoritative native CPU runtime artifact contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPOSITORY_ROOT / "config/engine_v2_native_cpu_runtime_artifacts_v1.json"
DEFAULT_RELEASE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
DEFAULT_NATIVE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"
DEFAULT_BUILD_TOOL = REPOSITORY_ROOT / "tools/build_engine_v2_native_wheel.py"
DEFAULT_SBOM_TOOL = REPOSITORY_ROOT / "tools/build_engine_v2_sbom.py"
DEFAULT_NATIVE_PROJECT = REPOSITORY_ROOT / "rust_engine_v2/pyproject.toml"
DEFAULT_NATIVE_BUILD_RS = REPOSITORY_ROOT / "rust_engine_v2/build.rs"
DEFAULT_PACKAGING_TEST = REPOSITORY_ROOT / "tests/unit/test_engine_v2_native_packaging.py"
DEFAULT_CONTRACT_TEST = (
    REPOSITORY_ROOT / "tests/unit/test_verify_engine_v2_native_cpu_runtime_artifacts_v1.py"
)
DEFAULT_DOCUMENTATION = REPOSITORY_ROOT / "docs/engine_v2_native_cpu_runtime_artifacts_v1.md"

POLICY_SHA256 = "195abc14487ccec4d0f8065fa0e642337ce42691cebee4f47106b94bd2d0ebe8"
UPLOAD_ACTION = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
ARTIFACT_NAME = (
    "engine-v2-native-0.2.0rc6-${{ matrix.abi }}-"
    "${{ github.run_id }}-${{ github.run_attempt }}"
)
MANYLINUX_IMAGE = (
    "quay.io/pypa/manylinux_2_28_x86_64@sha256:"
    "fdb9a9c223b215604dc7b6f7e8fff4b39bfea5fbaa7777a2e5544a60dfa437f8"
)
MATRIX = [
    {
        "abi": "cp310-cp310",
        "python_version": "3.10",
        "wheel_abi_tag": "cp310",
        "wheel_python_tag": "cp310",
    },
    {
        "abi": "cp311-cp311",
        "python_version": "3.11",
        "wheel_abi_tag": "cp311",
        "wheel_python_tag": "cp311",
    },
    {
        "abi": "cp312-cp312",
        "python_version": "3.12",
        "wheel_abi_tag": "cp312",
        "wheel_python_tag": "cp312",
    },
]
EXPECTED_ARTIFACT = {
    "artifact_name_template": ARTIFACT_NAME,
    "if_no_files_found": "error",
    "required_payload_globs": [
        "native-dist-a/*.whl",
        "native-dist-a/*.spdx.json",
    ],
    "retention_days": 14,
    "upload_action": UPLOAD_ACTION,
}
EXPECTED_AUTHORITY = {
    "fresh_holdout_execution_authorized": False,
    "hip_device_execution_authorized": False,
    "historical_ab_execution_authorized": False,
    "molecular_execution_authorized": False,
    "native_cpu_performance_qualification_authorized": False,
    "product_execution_authorized": False,
    "product_performance_claim_authorized": False,
    "public_benchmark_authorized": False,
    "reservation_authorized": False,
    "scientific_claim_authorized": False,
    "stage0_admission_authorized": False,
}
EXPECTED_BUILD = {
    "backend_profile": "cpu-manylinux_2_28-gcc14",
    "compatibility": "manylinux_2_28",
    "double_build_byte_identity_required": True,
    "frozen_build_wrapper_required": True,
    "manylinux_image": MANYLINUX_IMAGE,
    "package_distribution": "betelgeuze-engine-v2-native",
    "package_version": "0.2.0rc6",
    "rust_toolchain": "1.93.0",
    "sbom_spdx_version": "SPDX-2.3",
    "source_date_epoch": 1_735_689_600,
    "wheel_platform_tag": "manylinux_2_28_x86_64",
    "workflow_job": "native-cpu-wheel",
    "workflow_path": ".github/workflows/ci-engine-v2-release-candidate.yml",
}
EXPECTED_DOWNSTREAM_BINDING = {
    "admissible_event_name": "push",
    "admissible_ref": "refs/heads/main",
    "artifact_metadata_fields_required": [
        "repository",
        "workflow_path",
        "workflow_run_id",
        "workflow_run_attempt",
        "workflow_head_sha",
        "artifact_id",
        "artifact_name",
        "artifact_digest",
        "artifact_size_bytes",
        "artifact_expires_at",
    ],
    "artifact_selection_result_independent": True,
    "exact_abi_match_required": True,
    "exact_artifact_id_and_digest_required": True,
    "independently_frozen_profile_required": True,
    "pull_request_artifact_qualification_input_allowed": False,
    "runtime_executable_sha256_required": True,
    "runtime_extension_sha256_required": True,
    "wheel_sbom_checksum_binding_required": True,
}
EXPECTED_RESTRICTIONS = {
    "actual_molecular_input_allowed": False,
    "artifact_is_execution_or_qualification_evidence": False,
    "github_actions_production_authority_allowed": False,
    "hip_device_execution_allowed": False,
    "performance_measurement_allowed": False,
    "production_credentials_allowed": False,
    "production_endpoint_access_allowed": False,
    "qualification_consumption_allowed": False,
    "reservation_allowed": False,
    "test_double_production_authority_allowed": False,
}


class ContractError(RuntimeError):
    """Raised when the frozen artifact contract or its CI binding drifts."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_contract(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("ascii"), object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid runtime artifact policy JSON: {exc}") from exc
    if type(document) is not dict:
        raise ContractError("runtime artifact policy must be an exact object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        raise ContractError("runtime artifact policy is not canonical JSON")
    return document, raw


def _require_exact(value: object, expected: object, *, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ContractError(f"{name} changed")


def _require_snippets(path: Path, snippets: tuple[str, ...]) -> None:
    raw = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in raw]
    if missing:
        raise ContractError(f"{path.name} missing frozen snippets: {missing}")


def _require_text_snippets(name: str, raw: str, snippets: tuple[str, ...]) -> None:
    missing = [snippet for snippet in snippets if snippet not in raw]
    if missing:
        raise ContractError(f"{name} missing frozen snippets: {missing}")


def _extract_native_job(workflow: str) -> str:
    marker = "\n  native-cpu-wheel:\n"
    if workflow.count(marker) != 1:
        raise ContractError("release workflow must contain one native-cpu-wheel job")
    return workflow.split(marker, 1)[1]


def _extract_named_step(job: str, name: str) -> str:
    marker = f"      - name: {name}\n"
    if job.count(marker) != 1:
        raise ContractError(f"native-cpu-wheel must contain one {name!r} step")
    tail = job.split(marker, 1)[1]
    next_step = re.search(r"^      - (?:name:|uses:)", tail, flags=re.MULTILINE)
    return tail[: next_step.start()] if next_step else tail


def _verify_matrix(job: str) -> None:
    match = re.search(
        r"^      matrix:\n        include:\n(?P<body>.*?)(?=^    env:)",
        job,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ContractError("native CPU ABI matrix is missing")
    body = match.group("body")
    expected = "".join(
        f'          - python-version: "{row["python_version"]}"\n'
        f'            abi: {row["abi"]}\n'
        for row in MATRIX
    )
    if body != expected:
        raise ContractError("native CPU ABI matrix changed")


def _verify_release_workflow(path: Path) -> None:
    workflow = path.read_text(encoding="utf-8")
    job = _extract_native_job(workflow)
    _verify_matrix(job)
    _require_snippets(
        path,
        (
            "config/engine_v2_native_cpu_runtime_artifacts_v1.json",
            "tools/verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
            "tests/unit/test_verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
            "docs/engine_v2_native_cpu_runtime_artifacts_v1.md",
            "Verify native CPU runtime artifacts v1 contract",
        ),
    )
    for wired_path in (
        "config/engine_v2_native_cpu_runtime_artifacts_v1.json",
        "tools/verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
        "tests/unit/test_verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
        "docs/engine_v2_native_cpu_runtime_artifacts_v1.md",
    ):
        if workflow.count(wired_path) < 3:
            raise ContractError(f"release workflow incompletely wires {wired_path}")

    _require_text_snippets(
        "native-cpu-wheel job",
        job,
        (
            'SOURCE_DATE_EPOCH: "1735689600"',
            f"MANYLINUX_IMAGE: {MANYLINUX_IMAGE}",
            "rustup toolchain install 1.93.0 --profile minimal",
        ),
    )
    build = _extract_named_step(job, "Build native manylinux wheel twice")
    _require_text_snippets(
        "native manylinux double-build step",
        build,
        (
            "for output in native-dist-a native-dist-b; do",
            "--backend-profile cpu-manylinux_2_28-gcc14",
            "--compatibility manylinux_2_28",
            'cmp "$wheel_a" "$wheel_b"',
        ),
    )
    verification = _extract_named_step(job, "Verify native wheel, SBOM, and scorer parity")
    _require_text_snippets(
        "native wheel verification step",
        verification,
        (
            "betelgeuze-engine-v2-native-0.2.0rc6.spdx.json",
        ),
    )
    upload = _extract_named_step(job, "Upload native wheel and SBOM")
    if re.search(r"^        if:", upload, flags=re.MULTILINE):
        raise ContractError("native artifact upload must run for every ABI row")
    upload_snippets = (
        f"        uses: {UPLOAD_ACTION} # v7.0.1",
        f"          name: {ARTIFACT_NAME}",
        "            native-dist-a/*.whl",
        "            native-dist-a/*.spdx.json",
        "          if-no-files-found: error",
        "          retention-days: 14",
    )
    missing = [snippet for snippet in upload_snippets if snippet not in upload]
    if missing:
        raise ContractError(f"native artifact upload step changed: {missing}")


def _verify_native_workflow(path: Path) -> None:
    workflow = path.read_text(encoding="utf-8")
    wired = (
        "config/engine_v2_native_cpu_runtime_artifacts_v1.json",
        "tools/verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
        "tests/unit/test_verify_engine_v2_native_cpu_runtime_artifacts_v1.py",
        "docs/engine_v2_native_cpu_runtime_artifacts_v1.md",
    )
    for wired_path in wired:
        if workflow.count(wired_path) < 3:
            raise ContractError(f"native ABI workflow incompletely wires {wired_path}")
    if workflow.count("Verify native CPU runtime artifacts v1 contract") != 1:
        raise ContractError("native ABI workflow artifact verifier step changed")
    _require_snippets(
        path,
        ("python3 tools/verify_engine_v2_native_cpu_runtime_artifacts_v1.py",),
    )


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
    build_tool_path: Path = DEFAULT_BUILD_TOOL,
    sbom_tool_path: Path = DEFAULT_SBOM_TOOL,
    native_project_path: Path = DEFAULT_NATIVE_PROJECT,
    native_build_rs_path: Path = DEFAULT_NATIVE_BUILD_RS,
    packaging_test_path: Path = DEFAULT_PACKAGING_TEST,
    contract_test_path: Path = DEFAULT_CONTRACT_TEST,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
) -> dict[str, object]:
    document, raw = _load_contract(contract_path)
    _require_exact(
        frozenset(document),
        frozenset(
            {
                "artifact",
                "authority",
                "build",
                "downstream_binding",
                "matrix",
                "profile_id",
                "restrictions",
                "schema_id",
                "status",
            }
        ),
        name="runtime artifact policy keys",
    )
    _require_exact(
        document["schema_id"],
        "betelgeuze.engine_v2_native_cpu_runtime_artifact_policy/1.0.0",
        name="schema_id",
    )
    _require_exact(
        document["profile_id"],
        "engine_v2_native_cpu_runtime_artifacts_v1",
        name="profile_id",
    )
    _require_exact(
        document["status"],
        "frozen_non_authoritative_build_artifact_contract",
        name="status",
    )
    _require_exact(document["artifact"], EXPECTED_ARTIFACT, name="artifact policy")
    _require_exact(document["authority"], EXPECTED_AUTHORITY, name="authority")
    _require_exact(document["build"], EXPECTED_BUILD, name="build policy")
    _require_exact(
        document["downstream_binding"],
        EXPECTED_DOWNSTREAM_BINDING,
        name="downstream binding policy",
    )
    _require_exact(document["matrix"], MATRIX, name="ABI matrix")
    _require_exact(document["restrictions"], EXPECTED_RESTRICTIONS, name="restrictions")
    contract_sha256 = hashlib.sha256(raw).hexdigest()
    if contract_sha256 != POLICY_SHA256:
        raise ContractError("runtime artifact policy SHA-256 changed")

    _verify_release_workflow(release_workflow_path)
    _verify_native_workflow(native_workflow_path)
    _require_snippets(
        build_tool_path,
        (
            'NATIVE_VERSION = "0.2.0rc6"',
            'CPU_PROFILE_ID = "cpu-manylinux_2_28-gcc14"',
            'RUSTC_VERSION = "rustc 1.93.0',
            '"BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256"',
        ),
    )
    _require_snippets(sbom_tool_path, ('"SPDX-2.3"', "checksumValue"))
    _require_snippets(native_project_path, ('version = "0.2.0rc6"',))
    _require_snippets(
        native_build_rs_path,
        ('"verified_frozen_wrapper"', "native build wrapper changed after wrapper verification"),
    )
    _require_snippets(
        packaging_test_path,
        (
            "engine-v2-native-0.2.0rc6-${{ matrix.abi }}-",
            "${{ github.run_id }}-${{ github.run_attempt }}",
            "test_native_release_version_surfaces_match_rc6",
        ),
    )
    _require_snippets(
        contract_test_path,
        (
            "test_native_cpu_runtime_artifact_contract_verifies",
            "test_native_cpu_runtime_artifact_contract_rejects_workflow_drift",
        ),
    )
    _require_snippets(
        documentation_path,
        (
            "three ABI-specific artifacts",
            "main push",
            "does not consume a performance qualification",
            "GitHub Actions has no production authority",
        ),
    )
    return {
        "schema_id": document["schema_id"],
        "status": "verified_static_non_authoritative",
        "contract_sha256": contract_sha256,
        "abi_rows": [row["abi"] for row in MATRIX],
        "artifact_count_per_workflow_run": len(MATRIX),
        "retention_days": EXPECTED_ARTIFACT["retention_days"],
        "all_authority_false": all(value is False for value in EXPECTED_AUTHORITY.values()),
        "performance_measurement_allowed": False,
        "qualification_consumption_allowed": False,
        "reservation_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    arguments = parser.parse_args()
    print(json.dumps(verify(contract_path=arguments.contract), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
