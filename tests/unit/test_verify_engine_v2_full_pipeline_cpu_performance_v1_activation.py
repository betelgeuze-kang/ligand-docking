from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import verify_engine_v2_full_pipeline_cpu_performance_v1_activation as verify


_ROOT = Path(__file__).resolve().parents[2]
_ACTIVATION = (
    _ROOT / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json"
)
_STDLIB = (
    _ROOT
    / "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json"
)


def _write_canonical(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="ascii",
    )


def test_full_pipeline_cpu_activation_contract_verifies() -> None:
    result = verify.verify()

    assert result["activation_sha256"] == verify.ACTIVATION_SHA256
    assert result["profile_sha256"] == verify.PROFILE_SHA256
    assert result["all_authority_false"] is True
    assert result["execution_activated"] is False
    assert result["performance_measurement_performed"] is False
    assert result["qualification_consumed"] is False
    assert result["reservation_created"] is False


def test_full_pipeline_cpu_activation_rejects_authority_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = json.loads(_ACTIVATION.read_text(encoding="ascii"))
    document["authority"]["molecular_execution_authorized"] = True
    changed = tmp_path / "activation.json"
    _write_canonical(changed, document)
    monkeypatch.setattr(
        verify,
        "ACTIVATION_SHA256",
        hashlib.sha256(changed.read_bytes()).hexdigest(),
    )

    with pytest.raises(
        verify.FullPipelineCPUActivationContractError,
        match="activation authority is not all false",
    ):
        verify.verify(activation_path=changed)


def test_full_pipeline_cpu_activation_rejects_source_cross_wiring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = json.loads(_ACTIVATION.read_text(encoding="ascii"))
    document["source_bindings"]["runner_tool_sha256"] = "0" * 64
    changed = tmp_path / "activation.json"
    _write_canonical(changed, document)
    monkeypatch.setattr(
        verify,
        "ACTIVATION_SHA256",
        hashlib.sha256(changed.read_bytes()).hexdigest(),
    )

    with pytest.raises(
        verify.FullPipelineCPUActivationContractError,
        match="source bindings changed",
    ):
        verify.verify(activation_path=changed)


def test_full_pipeline_cpu_activation_requires_exact_eleven_bindings() -> None:
    document = json.loads(_ACTIVATION.read_text(encoding="ascii"))

    assert set(document["source_bindings"]) == {
        "merged_main_commit_sha256",
        "merged_main_tree_sha256",
        "profile_sha256",
        "profile_verifier_sha256",
        "measurement_core_sha256",
        "runner_tool_sha256",
        "native_consumer_sha256",
        "native_cpu_parity_sha256",
        "host_preflight_sha256",
        "stdlib_import_closure_manifest_sha256",
        "dynamic_library_closure_manifest_sha256",
    }


def test_closure_manifest_rejects_row_receipt_drift(tmp_path: Path) -> None:
    document = json.loads(_STDLIB.read_text(encoding="ascii"))
    document["rows"][0]["module"] = "changed"
    changed = tmp_path / "stdlib.json"
    _write_canonical(changed, document)

    with pytest.raises(
        verify.FullPipelineCPUActivationContractError,
        match="runtime closure row receipt changed",
    ):
        verify.load_closure_manifest(
            changed,
            expected_schema_id=(
                "betelgeuze.engine_v2_python_stdlib_import_closure/1.0.0"
            ),
        )


def test_closure_manifest_rejects_summary_drift(tmp_path: Path) -> None:
    document = json.loads(_STDLIB.read_text(encoding="ascii"))
    document["module_count"] += 1
    changed = tmp_path / "stdlib-summary.json"
    _write_canonical(changed, document)

    with pytest.raises(
        verify.FullPipelineCPUActivationContractError,
        match="module count changed",
    ):
        verify.load_closure_manifest(
            changed,
            expected_schema_id=(
                "betelgeuze.engine_v2_python_stdlib_import_closure/1.0.0"
            ),
        )


def test_activation_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    changed = tmp_path / "activation.json"
    changed.write_text('{"schema_id":"a","schema_id":"b"}\n', encoding="ascii")

    with pytest.raises(
        verify.FullPipelineCPUActivationContractError,
        match="duplicate JSON key",
    ):
        verify.verify(activation_path=changed)
