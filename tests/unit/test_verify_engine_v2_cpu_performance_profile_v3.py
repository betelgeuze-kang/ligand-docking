from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.docking.performance_host_preflight_v3 import (
    HostPreflightEvidenceV3,
    SysfsBooleanEvidenceV3,
)
from tools import preflight_engine_v2_cpu_performance_v3 as preflight_tool
from tools.verify_engine_v2_cpu_performance_profile_v3 import (
    CPUPerformanceProfileV3Error,
    verify_cpu_performance_profile_v3,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _REPO_ROOT / "config/engine_v2_cpu_performance_profile_v3.json"
_VERIFIER = _REPO_ROOT / "tools/verify_engine_v2_cpu_performance_profile_v3.py"


def _profile_document() -> dict[str, object]:
    return json.loads(_PROFILE.read_text(encoding="ascii"))


def _write_canonical(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="ascii",
    )


def test_current_profile_v3_is_exact_non_consuming_successor() -> None:
    result = verify_cpu_performance_profile_v3()

    assert result == {
        "authority": {
            "fresh_holdout_execution_authorized": False,
            "historical_ab_execution_authorized": False,
            "molecular_execution_authorized": False,
            "product_performance_claim_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
        },
        "live_run_capability": False,
        "molecular_execution": False,
        "non_consuming_preflight_only": True,
        "numeric_contract_changed": False,
        "predecessor_profile_sha256": (
            "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"
        ),
        "predecessor_terminal_decision_sha256": (
            "047f157c8d5d3228c180aca6af392eb8cf13d828659b9a83c38c74c34cc0cf0f"
        ),
        "profile_id": "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v3",
        "profile_sha256": (
            "21facfc62956b402d4a43e5b68389083bacaa3d3afd753eb6b1da3578c8bb6b3"
        ),
        "profile_verified": True,
    }
    completed = subprocess.run(
        [sys.executable, str(_VERIFIER)],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == result


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("authority", "molecular_execution_authorized", True),
        ("change_control", "numeric_contract_changed", True),
        ("host_preflight", "consumes_qualification", True),
        ("host_preflight", "launches_measurements", True),
    ),
)
def test_profile_v3_tamper_fails_closed(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    document = copy.deepcopy(_profile_document())
    document[section][field] = value  # type: ignore[index]
    changed = tmp_path / "profile-v3.json"
    _write_canonical(changed, document)

    with pytest.raises(CPUPerformanceProfileV3Error, match="profile v3 changed"):
        verify_cpu_performance_profile_v3(profile_path=changed)


def test_profile_v3_reader_contract_tamper_fails_closed(tmp_path: Path) -> None:
    document = copy.deepcopy(_profile_document())
    document["host_preflight"]["boost_state_reader"][  # type: ignore[index]
        "maximum_actual_bytes"
    ] = 4096
    changed = tmp_path / "profile-v3.json"
    _write_canonical(changed, document)

    with pytest.raises(CPUPerformanceProfileV3Error, match="profile v3 changed"):
        verify_cpu_performance_profile_v3(profile_path=changed)


def test_profile_v3_duplicate_or_noncanonical_json_fails_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        _PROFILE.read_text(encoding="ascii").replace(
            "{", '{\n  "schema_id": "duplicate",', 1
        ),
        encoding="ascii",
    )
    with pytest.raises(CPUPerformanceProfileV3Error, match="duplicate"):
        verify_cpu_performance_profile_v3(profile_path=duplicate)

    compact = tmp_path / "compact.json"
    compact.write_text(
        json.dumps(_profile_document(), sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="ascii",
    )
    with pytest.raises(CPUPerformanceProfileV3Error, match="canonical indented"):
        verify_cpu_performance_profile_v3(profile_path=compact)


def test_non_consuming_preflight_receipt_binds_host_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = dict(verify_cpu_performance_profile_v3())
    host = HostPreflightEvidenceV3(
        cpu_model="qualified-model",
        boost_state=SysfsBooleanEvidenceV3(
            path="/sys/devices/system/cpu/cpufreq/boost",
            reader_id="betelgeuze.linux_sysfs_boolean_reader/1.0.0",
            raw_byte_count=2,
            raw_sha256="0" * 64,
            reported_size_before=4096,
            reported_size_descriptor_before=4096,
            reported_size_descriptor_after=4096,
            reported_size_after=4096,
            stable_read_count=2,
            boost_enabled=False,
        ),
        available_cpu_affinity=(2,),
        platform_system="Linux",
        platform_machine="x86_64",
        byteorder="little",
        parent_pid=123,
        parent_os_task_count=1,
        qualified=True,
        blockers=(),
    )
    monkeypatch.setattr(
        preflight_tool,
        "verify_cpu_performance_profile_v3",
        lambda: profile,
    )
    monkeypatch.setattr(
        preflight_tool,
        "derive_host_preflight_evidence_v3",
        lambda: host,
    )

    result = preflight_tool.run_non_consuming_preflight()
    receipt = result.pop("preflight_receipt_sha256")

    assert result["qualified"] is True
    assert result["consumes_qualification"] is False
    assert result["execution_authorized"] is False
    assert result["launches_measurements"] is False
    assert result["molecular_execution"] is False
    assert result["persists_result"] is False
    assert result["reservation_created"] is False
    assert receipt == hashlib.sha256(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
