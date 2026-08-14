from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import run_engine_v2_full_pipeline_cpu_performance_v1 as runner
from tools.verify_engine_v2_full_pipeline_cpu_performance_v1 import (
    DEFAULT_DURABLE_ARCHIVE_ROOT,
    DEFAULT_MEASUREMENT_CORE,
    DEFAULT_PROFILE,
    FullPipelineCPUPerformanceProfileError,
    PROFILE_SHA256,
    verify,
)


def _write_profile(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


def test_full_pipeline_cpu_performance_profile_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_implementation_execution_not_activated"
    assert result["profile_sha256"] == PROFILE_SHA256
    assert result["artifact_workflow_head_sha"] == (
        "3330faa43c7fc8640d89babd84ac444c5959157c"
    )
    assert result["artifact_id"] == 9213296947
    assert result["artifact_abi"] == "cp310-cp310"
    assert result["candidate_denominator"] == 64
    assert result["sample_count_per_backend"] == 30
    assert result["speed_threshold_present"] is False
    assert result["all_authority_false"] is True
    assert result["execution_activated"] is False
    assert result["qualification_consumed"] is False
    assert result["predecessor_attempt_consumed"] is False
    assert result["reservation_created"] is False
    assert result["durable_repository_archive_verified"] is True
    archive = result["durable_repository_archive_evidence"]
    assert archive["payload_total_bytes"] == 1_232_493
    assert archive["performance_measurement_performed"] is False
    assert archive["qualification_consumed"] is False
    assert archive["reservation_created"] is False
    assert result["local_runtime_verified"] is False


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("authority", "molecular_execution_authorized", True),
        ("authority", "synthetic_cpu_performance_qualification_authorized", True),
        ("restrictions", "implementation_pr_measurement_allowed", True),
        ("activation", "activation_contract_present", True),
        ("activation", "qualification_attempt_consumed", True),
    ),
)
def test_full_pipeline_cpu_performance_profile_rejects_authority_drift(
    tmp_path: Path, section: str, field: str, value: object
) -> None:
    document = json.loads(DEFAULT_PROFILE.read_text(encoding="ascii"))
    document[section][field] = value
    changed = tmp_path / "profile.json"
    _write_profile(changed, document)

    with pytest.raises(FullPipelineCPUPerformanceProfileError):
        verify(profile_path=changed)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("artifact_binding", "artifact_id", 1),
        ("artifact_binding", "event_name", "pull_request"),
        ("runtime_binding", "native_extension_sha256", "0" * 64),
        ("measurement", "sample_count_per_backend", 29),
        ("measurement", "result_cache_allowed", True),
        ("gates", "speed_threshold_present", True),
        ("workload", "candidate_denominator", 63),
        ("predecessor_disposition", "attempt_consumed", True),
    ),
)
def test_full_pipeline_cpu_performance_profile_rejects_identity_drift(
    tmp_path: Path, section: str, field: str, value: object
) -> None:
    document = json.loads(DEFAULT_PROFILE.read_text(encoding="ascii"))
    document[section][field] = value
    changed = tmp_path / "profile.json"
    _write_profile(changed, document)

    with pytest.raises(FullPipelineCPUPerformanceProfileError):
        verify(profile_path=changed)


def test_full_pipeline_cpu_performance_profile_rejects_duplicate_keys(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "profile.json"
    duplicate.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(FullPipelineCPUPerformanceProfileError, match="duplicate JSON"):
        verify(profile_path=duplicate)


def test_full_pipeline_cpu_performance_profile_rejects_noncanonical_json(
    tmp_path: Path,
) -> None:
    document = json.loads(DEFAULT_PROFILE.read_text(encoding="ascii"))
    compact = tmp_path / "profile.json"
    compact.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="ascii")

    with pytest.raises(FullPipelineCPUPerformanceProfileError, match="not canonical"):
        verify(profile_path=compact)


def test_full_pipeline_cpu_performance_profile_rejects_source_drift(
    tmp_path: Path,
) -> None:
    raw = DEFAULT_MEASUREMENT_CORE.read_text(encoding="utf-8")
    needle = "def verify_local_runtime_binding("
    assert needle in raw
    changed = tmp_path / "measurement.py"
    changed.write_text(
        raw.replace(needle, "def drifted_runtime_binding("), encoding="utf-8"
    )

    with pytest.raises(
        FullPipelineCPUPerformanceProfileError, match="missing frozen snippets"
    ):
        verify(measurement_core_path=changed)


def test_local_runtime_verification_requires_both_paths(tmp_path: Path) -> None:
    with pytest.raises(
        FullPipelineCPUPerformanceProfileError,
        match="must be supplied together",
    ):
        verify(artifact_directory=tmp_path)


def test_durable_repository_archive_rejects_payload_drift(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_PROFILE.read_text(encoding="ascii"))
    rows = document["artifact_binding"]["durable_repository_archive"]["payloads"]
    for index, row in enumerate(rows):
        relative = Path(row["path"])
        source = DEFAULT_DURABLE_ARCHIVE_ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw + (b"drift" if index == 1 else b""))

    with pytest.raises(
        FullPipelineCPUPerformanceProfileError,
        match="durable repository archive",
    ):
        verify(durable_archive_root=tmp_path)


def test_runner_static_verification_is_non_consuming(capsys) -> None:
    assert runner.main(["--verify-implementation"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["execution_activated"] is False
    assert result["qualification_consumed"] is False
    assert result["reservation_created"] is False


@pytest.mark.parametrize(
    "arguments",
    (
        ("tools/verify_engine_v2_full_pipeline_cpu_performance_v1.py",),
        (
            "tools/run_engine_v2_full_pipeline_cpu_performance_v1.py",
            "--verify-implementation",
        ),
    ),
)
def test_direct_script_bootstraps_repository_root_without_environment_package(
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [sys.executable, str(repository_root / arguments[0]), *arguments[1:]],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)
    assert document["execution_activated"] is False
    assert document["qualification_consumed"] is False
    assert document["reservation_created"] is False
