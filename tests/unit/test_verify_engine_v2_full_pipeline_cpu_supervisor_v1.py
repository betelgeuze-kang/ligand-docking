from __future__ import annotations

import json
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

from tools.verify_engine_v2_full_pipeline_cpu_supervisor_v1 import (
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_SOURCE,
    DEFAULT_WORKFLOWS,
    SupervisorContractError,
    verify,
)


def _write_json(path: Path, document: object) -> None:
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


def _require_static_x86_64_elf(raw: bytes) -> None:
    assert len(raw) >= 64
    assert raw[:7] == b"\x7fELF\x02\x01\x01"
    executable_type, machine = struct.unpack_from("<HH", raw, 16)
    program_offset = struct.unpack_from("<Q", raw, 32)[0]
    program_entry_size, program_count = struct.unpack_from("<HH", raw, 54)
    assert executable_type == 2
    assert machine == 62
    assert program_entry_size >= 56
    assert program_count > 0
    assert program_offset + program_entry_size * program_count <= len(raw)
    program_types = {
        struct.unpack_from(
            "<I", raw, program_offset + index * program_entry_size
        )[0]
        for index in range(program_count)
    }
    assert 2 not in program_types  # PT_DYNAMIC
    assert 3 not in program_types  # PT_INTERP


def test_full_pipeline_cpu_supervisor_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_reviewable_non_operational_source"
    assert result["all_authority_false"] is True
    assert result["implementation_present"] is True
    assert result["installation_authorized"] is False
    assert result["runtime_launch_authorized"] is False
    assert result["qualification_consumption_authorized"] is False
    assert result["provider_qualified"] is False
    assert result["operational"] is False
    assert result["reservation_created"] is False
    assert result["performance_measurement_performed"] is False
    assert len(str(result["contract_sha256"])) == 64
    assert len(str(result["source_sha256"])) == 64


def test_supervisor_static_binary_is_non_operational(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    assert compiler is not None
    executable = tmp_path / "engine-v2-full-pipeline-cpu-supervisor-v1"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-static",
            "-s",
            "-Wl,--build-id=none",
            str(DEFAULT_SOURCE),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    _require_static_x86_64_elf(executable.read_bytes())

    described = subprocess.run(
        [str(executable), "--describe-contract"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(described.stdout) == {
        "authority_false": True,
        "handoff_bytes": 464,
        "installation_authorized": False,
        "operational": False,
        "protocol_version": 1,
        "qualification_consumption_authorized": False,
        "request_bytes": 192,
        "required_request_fds": 3,
        "runtime_launch_authorized": False,
        "schema_id": "betelgeuze.engine_v2_full_pipeline_cpu_supervisor/1.0.0",
        "supervisor_id": "engine_v2_full_pipeline_cpu_supervisor_v1",
        "terminal_bytes": 96,
    }
    self_tested = subprocess.run(
        [str(executable), "--self-test-primitives"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(self_tested.stdout) == {
        "authority_false": True,
        "digest_round_trip": True,
        "launch_environment_sha256": (
            "5cf4cf74eba4f493ae3f8a88c3459e2f8861146b6e38b5c4d7bd65e958f0da96"
        ),
        "launch_vector_sha256": (
            "3844da69d7b4a1dd61cde9ffa559c7409a6d23b43a80f63dcea612f859a932d3"
        ),
        "service_started": False,
        "sha256_abc": True,
    }

    socket_path = Path(
        "/run/betelgeuze-engine-v2/full-pipeline-cpu-supervisor-v1.sock"
    )
    assert not socket_path.exists()
    rejected = subprocess.run(
        [str(executable)], check=False, capture_output=True, text=True
    )
    assert rejected.returncode == 125
    assert "source-complete but non-operational" in rejected.stderr
    assert "qualification consumption remain unauthorized" in rejected.stderr
    assert not socket_path.exists()

    strings = subprocess.run(
        ["strings", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "full-pipeline-cpu-supervisor-v1.sock" in strings
    assert "trace exclusion could not start before credential drop" in strings
    assert "kernel-attested supervisor handoff" in strings


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            installation_authorized=True
        ),
        lambda document: document["authority"].update(
            qualification_consumption_authorized=True
        ),
        lambda document: document["lifecycle"].update(operational=True),
        lambda document: document["lifecycle"].update(provider_qualified=True),
        lambda document: document["build"].update(packaged_binary_present=True),
        lambda document: document["protocol"].update(
            ancillary_descriptor_count=4
        ),
        lambda document: document["restrictions"].update(
            actual_service_execution_allowed_in_ci=True
        ),
        lambda document: document["trust_boundary"].update(
            procfs_path_evidence_authoritative=True
        ),
        lambda document: document["trust_boundary"].update(
            trace_exclusion_independently_qualified=True
        ),
    ),
)
def test_supervisor_contract_rejects_authority_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(SupervisorContractError):
        verify(contract_path=contract)


def test_supervisor_contract_rejects_source_drift(tmp_path: Path) -> None:
    raw = DEFAULT_SOURCE.read_text(encoding="utf-8")
    needle = "PTRACE_O_TRACEEXEC | PTRACE_O_EXITKILL"
    assert needle in raw
    source = tmp_path / DEFAULT_SOURCE.name
    source.write_text(raw.replace(needle, "PTRACE_O_TRACEEXEC", 1), encoding="utf-8")

    with pytest.raises(
        SupervisorContractError,
        match="source digest changed",
    ):
        verify(source_path=source)


def test_supervisor_contract_rejects_duplicate_keys(tmp_path: Path) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(SupervisorContractError, match="duplicate JSON key"):
        verify(contract_path=contract)


def test_supervisor_contract_rejects_noncanonical_json(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    contract = tmp_path / "compact.json"
    contract.write_text(json.dumps(document) + "\n", encoding="ascii")

    with pytest.raises(SupervisorContractError, match="not canonical"):
        verify(contract_path=contract)


def test_supervisor_contract_rejects_workflow_drift(tmp_path: Path) -> None:
    original = DEFAULT_WORKFLOWS[0]
    raw = original.read_text(encoding="utf-8")
    needle = "Verify full-pipeline CPU supervisor v1"
    assert needle in raw
    workflow = tmp_path / original.name
    workflow.write_text(raw.replace(needle, "DRIFTED", 1), encoding="utf-8")

    with pytest.raises(SupervisorContractError, match="missing frozen"):
        verify(workflow_paths=(workflow, *DEFAULT_WORKFLOWS[1:]))


def test_supervisor_contract_rejects_ci_audit_sparse_omission(
    tmp_path: Path,
) -> None:
    original = DEFAULT_WORKFLOWS[1]
    raw = original.read_text(encoding="utf-8")
    needle = "tools/audit_engine_v2_ci_authority.py"
    assert raw.count(needle) >= 2
    workflow = tmp_path / original.name
    prefix, suffix = raw.rsplit(needle, 1)
    workflow.write_text(prefix + "DRIFTED" + suffix, encoding="utf-8")

    with pytest.raises(SupervisorContractError, match="sparse checkout"):
        verify(
            workflow_paths=(
                DEFAULT_WORKFLOWS[0],
                workflow,
                DEFAULT_WORKFLOWS[2],
            )
        )


def test_supervisor_contract_rejects_documentation_drift(tmp_path: Path) -> None:
    raw = DEFAULT_DOCUMENTATION.read_text(encoding="utf-8")
    needle = "not an activation receipt"
    assert needle in raw
    documentation = tmp_path / DEFAULT_DOCUMENTATION.name
    documentation.write_text(raw.replace(needle, "DRIFTED"), encoding="utf-8")

    with pytest.raises(SupervisorContractError, match="missing frozen"):
        verify(documentation_path=documentation)
