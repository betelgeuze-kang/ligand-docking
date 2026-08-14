from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_native_cpu_runtime_artifacts_v1 import (
    ARTIFACT_NAME,
    ContractError,
    DEFAULT_BUILD_TOOL,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_NATIVE_BUILD_RS,
    DEFAULT_NATIVE_WORKFLOW,
    DEFAULT_PACKAGING_TEST,
    DEFAULT_RELEASE_WORKFLOW,
    verify,
)


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


def test_native_cpu_runtime_artifact_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["contract_sha256"] == (
        "195abc14487ccec4d0f8065fa0e642337ce42691cebee4f47106b94bd2d0ebe8"
    )
    assert result["abi_rows"] == ["cp310-cp310", "cp311-cp311", "cp312-cp312"]
    assert result["artifact_count_per_workflow_run"] == 3
    assert result["retention_days"] == 14
    assert result["all_authority_false"] is True
    assert result["performance_measurement_allowed"] is False
    assert result["qualification_consumption_allowed"] is False
    assert result["reservation_allowed"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["artifact"].update(retention_days=7),
        lambda document: document["artifact"].update(
            artifact_name_template="engine-v2-native-0.2.0rc6-${{ github.run_id }}"
        ),
        lambda document: document["authority"].update(
            native_cpu_performance_qualification_authorized=True
        ),
        lambda document: document["authority"].update(molecular_execution_authorized=True),
        lambda document: document["build"].update(double_build_byte_identity_required=False),
        lambda document: document["build"].update(frozen_build_wrapper_required=False),
        lambda document: document["downstream_binding"].update(
            pull_request_artifact_qualification_input_allowed=True
        ),
        lambda document: document["downstream_binding"].update(
            artifact_selection_result_independent=False
        ),
        lambda document: document["matrix"].pop(),
        lambda document: document["restrictions"].update(performance_measurement_allowed=True),
    ),
)
def test_native_cpu_runtime_artifact_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    (
        (
            "      - name: Upload native wheel and SBOM\n        uses:",
            "      - name: Upload native wheel and SBOM\n"
            "        if: matrix.python-version == '3.11'\n"
            "        uses:",
            "every ABI row",
        ),
        (ARTIFACT_NAME, "engine-v2-native-0.2.0rc6-${{ github.run_id }}", "upload step changed"),
        (
            '          - python-version: "3.10"\n            abi: cp310-cp310\n',
            "",
            "ABI matrix changed",
        ),
        ('cmp "$wheel_a" "$wheel_b"', ": skip byte comparison", "missing frozen snippets"),
        (
            "            native-dist-a/*.spdx.json",
            "            native-dist-a/*.txt",
            "upload step changed",
        ),
        ("          retention-days: 14", "          retention-days: 7", "upload step changed"),
    ),
)
def test_native_cpu_runtime_artifact_contract_rejects_workflow_drift(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    raw = DEFAULT_RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert old in raw
    if old in {'cmp "$wheel_a" "$wheel_b"', "          retention-days: 14"}:
        index = raw.rfind(old)
        raw = raw[:index] + new + raw[index + len(old) :]
    else:
        raw = raw.replace(old, new, 1)
    drifted = tmp_path / "release.yml"
    drifted.write_text(raw, encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        verify(release_workflow_path=drifted)


@pytest.mark.parametrize(
    ("source", "argument", "needle"),
    (
        (
            DEFAULT_NATIVE_WORKFLOW,
            "native_workflow_path",
            "Verify native CPU runtime artifacts v1 contract",
        ),
        (DEFAULT_BUILD_TOOL, "build_tool_path", 'NATIVE_VERSION = "0.2.0rc6"'),
        (DEFAULT_NATIVE_BUILD_RS, "native_build_rs_path", '"verified_frozen_wrapper"'),
        (
            DEFAULT_PACKAGING_TEST,
            "packaging_test_path",
            "engine-v2-native-0.2.0rc6-${{ matrix.abi }}-",
        ),
        (DEFAULT_DOCUMENTATION, "documentation_path", "three ABI-specific artifacts"),
    ),
)
def test_native_cpu_runtime_artifact_contract_rejects_source_binding_drift(
    tmp_path: Path,
    source: Path,
    argument: str,
    needle: str,
) -> None:
    raw = source.read_text(encoding="utf-8")
    assert needle in raw
    drifted = tmp_path / source.name
    drifted.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")

    with pytest.raises(ContractError):
        verify(**{argument: drifted})


def test_native_cpu_runtime_artifact_contract_rejects_duplicate_keys(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n',
        encoding="ascii",
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)


def test_native_cpu_runtime_artifact_contract_rejects_noncanonical_json(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "pretty.json"
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    contract.write_text(json.dumps(document, indent=2) + "\n", encoding="ascii")

    with pytest.raises(ContractError, match="not canonical JSON"):
        verify(contract_path=contract)
