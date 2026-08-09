from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import tools.verify_engine_v2_cpu_performance_profile as verifier_tool

from betelgeuze_engine_v2.docking.performance_sidecar import (
    CPUPerformanceError,
    PROFILE_ID,
    load_cpu_performance_profile,
    verify_cpu_performance_profile_document,
)
from tools.verify_engine_v2_cpu_performance_profile import (
    verify_profile_and_optional_artifact,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_PATH = _REPO_ROOT / "config/engine_v2_cpu_performance_profile.json"
_TOOL_PATH = _REPO_ROOT / "tools/verify_engine_v2_cpu_performance_profile.py"
_BOOTSTRAP_PATH = _REPO_ROOT / "tools/run_engine_v2_cpu_performance_qualification.py"
_PROFILE_SHA256 = "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"


def _profile() -> dict[str, object]:
    return json.loads(_PROFILE_PATH.read_text(encoding="ascii"))


def test_current_profile_and_offline_cli_are_exact() -> None:
    profile = load_cpu_performance_profile(_PROFILE_PATH)
    reconstructed = verify_cpu_performance_profile_document(_profile())

    assert profile.profile_sha256 == reconstructed.profile_sha256 == _PROFILE_SHA256
    result = verify_profile_and_optional_artifact(profile_path=_PROFILE_PATH)
    assert result == {
        "structural_integrity_verified": True,
        "execution_attested": False,
        "profile_id": PROFILE_ID,
        "profile_sha256": _PROFILE_SHA256,
        "artifact_structurally_replayed": False,
        "recorded_decision": None,
        "recorded_numeric_gate_passed": None,
        "live_run_capability": False,
        "local_numeric_gate_eligible": False,
        "offline_replay_only": True,
        "qualification_authority": False,
        "verification_blockers": [
            "profile_contract_only_cannot_attest_execution"
        ],
        "authority": {
            "fresh_holdout_execution_authorized": False,
            "historical_ab_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_performance_claim_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
        },
    }
    completed = subprocess.run(
        [sys.executable, str(_TOOL_PATH), "--profile", str(_PROFILE_PATH)],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == result


def test_bootstrap_requires_absent_stdlib_zip_and_compiles_bound_sources_directly() -> None:
    source = _BOOTSTRAP_PATH.read_text(encoding="utf-8")

    assert "posix.lstat(_STDLIB_ZIP_PATH)" in source
    assert '"/usr/lib/python310.zip"' in source
    assert "isolated standard-library zip must be absent" in source
    assert '"mixed64_allocation"' in source
    assert '"geometric_admission_v2"' in source
    assert '"performance_sidecar"' in source
    assert 'compile(raw, str(path), "exec", dont_inherit=True, optimize=0)' in source
    assert "import importlib.util" not in source


def test_profile_binds_full_numpy_install_and_absent_stdlib_zip() -> None:
    runtime = _profile()["runtime"]

    assert runtime["python_stdlib_zip_path"] == "/usr/lib/python310.zip"
    assert runtime["python_stdlib_zip_state"] == "required_absent"
    assert runtime["numpy_record_row_count"] == 918
    assert runtime["numpy_record_present_file_count"] == 917
    assert runtime["numpy_installed_files_manifest_file_count"] == 917
    assert runtime["numpy_console_script_relative_path"] == "bin/f2py"
    assert runtime["numpy_record_typed_absent_paths"] == [
        "numpy/distutils/__pycache__/conv_template.cpython-310.pyc"
    ]


def test_offline_artifact_replay_never_attests_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "offline.json"
    artifact_path.write_text("{}\n", encoding="ascii")
    fake_artifact = SimpleNamespace(
        recorded_decision="GO",
        recorded_numeric_gate_passed=True,
        # These deliberately hostile values prove the reporting boundary is
        # fail-closed even if a future loader regresses.
        live_run_capability=True,
        local_numeric_gate_eligible=True,
        offline_replay_only=False,
        qualification_authority=True,
        verification_blockers=(),
    )
    monkeypatch.setattr(
        verifier_tool,
        "load_cpu_performance_artifact",
        lambda artifact_path, *, profile: fake_artifact,
    )
    monkeypatch.setattr(
        verifier_tool,
        "load_cpu_performance_profile",
        lambda profile_path: SimpleNamespace(profile_sha256=_PROFILE_SHA256),
    )

    result = verify_profile_and_optional_artifact(
        profile_path=_PROFILE_PATH,
        artifact_path=artifact_path,
    )

    assert result == {
        "structural_integrity_verified": True,
        "execution_attested": False,
        "profile_id": PROFILE_ID,
        "profile_sha256": _PROFILE_SHA256,
        "artifact_structurally_replayed": True,
        "recorded_decision": "GO",
        "recorded_numeric_gate_passed": True,
        "live_run_capability": False,
        "local_numeric_gate_eligible": False,
        "offline_replay_only": True,
        "qualification_authority": False,
        "verification_blockers": ["offline_artifact_cannot_attest_execution"],
        "authority": {
            "fresh_holdout_execution_authorized": False,
            "historical_ab_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_performance_claim_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
        },
    }


@pytest.mark.parametrize(
    "path,value",
    (
        (("host", "cpu_model_exact"), "AMD Ryzen 9 5950X 16-Core Processor"),
        (("host", "child_cpu_affinity"), [3]),
        (("sampling", "sample_count"), 29),
        (("fixtures", 1, "receptor_atom_count"), 2047),
        (("gates", "medium_large_minimum_p95_speedup_numerator"), 2),
        (("authority", "molecular_execution_authorized"), True),
        (("restrictions", "reservation_allowed"), True),
    ),
)
def test_profile_contract_or_authority_drift_fails_closed(
    path: tuple[object, ...], value: object
) -> None:
    with pytest.raises(CPUPerformanceError):
        verify_cpu_performance_profile_document(_mutated(path, value))


def _mutated(path: tuple[object, ...], value: object) -> dict[str, object]:
    changed: object = copy.deepcopy(_profile())
    for key in path[:-1]:
        changed = changed[key]  # type: ignore[index]
    changed[path[-1]] = value  # type: ignore[index]
    return changed  # type: ignore[return-value]


def test_profile_key_set_duplicate_noncanonical_and_float_fail_closed(
    tmp_path: Path,
) -> None:
    changed = _profile()
    changed["unexpected"] = False
    with pytest.raises(CPUPerformanceError, match="keys"):
        verify_cpu_performance_profile_document(changed)

    canonical = _PROFILE_PATH.read_text(encoding="ascii")
    duplicate = canonical.replace("{", '{"schema_id":"duplicate",', 1)
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(duplicate, encoding="ascii")
    with pytest.raises(CPUPerformanceError, match="duplicate"):
        load_cpu_performance_profile(duplicate_path)

    pretty_path = tmp_path / "pretty.json"
    pretty_path.write_text(json.dumps(_profile(), indent=2) + "\n", encoding="ascii")
    with pytest.raises(CPUPerformanceError, match="canonical"):
        load_cpu_performance_profile(pretty_path)

    float_path = tmp_path / "float.json"
    float_path.write_text('{"threshold":1.5}\n', encoding="ascii")
    with pytest.raises(CPUPerformanceError, match="hexadecimal"):
        load_cpu_performance_profile(float_path)
