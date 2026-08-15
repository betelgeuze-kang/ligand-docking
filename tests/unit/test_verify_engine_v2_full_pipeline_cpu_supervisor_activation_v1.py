from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from tools.verify_engine_v2_full_pipeline_cpu_supervisor_activation_v1 import (
    DEFAULT_BINARY,
    DEFAULT_CI_AUDIT,
    DEFAULT_CONTRACT,
    DEFAULT_PREFLIGHT,
    DEFAULT_ROSTER,
    DEFAULT_SBOM,
    DEFAULT_WORKFLOWS,
    SupervisorActivationContractError,
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


def _mutated_contract(tmp_path: Path, mutation) -> Path:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    mutation(document)
    path = tmp_path / DEFAULT_CONTRACT.name
    _write_json(path, document)
    return path


def test_supervisor_activation_contract_verifies() -> None:
    result = verify()
    assert result["status"] == (
        "verified_packaged_non_consuming_activation_not_operational"
    )
    assert result["all_authority_false"] is True
    assert result["package_present"] is True
    assert result["roster_frozen"] is True
    assert result["handoff_preflight_implemented"] is True
    assert result["activation_operational"] is False
    assert result["qualification_consumed"] is False
    assert result["reservation_created"] is False
    assert result["performance_measurement_performed"] is False
    assert len(result["local_blockers"]) == 6
    assert len(result["external_blockers"]) == 4


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            runtime_launch_authorized=True
        ),
        lambda document: document["restrictions"].update(
            package_installation_allowed=True
        ),
        lambda document: document["lifecycle"].update(
            activation_operational=True
        ),
    ),
)
def test_supervisor_activation_rejects_authority_escalation(
    tmp_path: Path,
    mutation,
) -> None:
    with pytest.raises(SupervisorActivationContractError):
        verify(contract_path=_mutated_contract(tmp_path, mutation))


def test_supervisor_activation_rejects_authority_key_omission(
    tmp_path: Path,
) -> None:
    contract = _mutated_contract(
        tmp_path,
        lambda document: document["authority"].pop(
            "github_actions_production_authority"
        ),
    )
    with pytest.raises(SupervisorActivationContractError, match="authority"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_package_compiler_cross_wiring(
    tmp_path: Path,
) -> None:
    contract = _mutated_contract(
        tmp_path,
        lambda document: document["package"].update(
            compiler_sha256="0" * 64
        ),
    )
    with pytest.raises(SupervisorActivationContractError, match="package contract"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_downstream_receipt_overclaim(
    tmp_path: Path,
) -> None:
    contract = _mutated_contract(
        tmp_path,
        lambda document: document["downstream_binding"].update(
            actual_binding_receipt_present=True
        ),
    )
    with pytest.raises(SupervisorActivationContractError, match="downstream"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_external_blocker_drift(tmp_path: Path) -> None:
    contract = _mutated_contract(
        tmp_path,
        lambda document: document["external_authority"]["blockers"].pop(),
    )
    with pytest.raises(SupervisorActivationContractError, match="external authority"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_roster_drift(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_ROSTER.read_text(encoding="utf-8"))
    document["client"]["uid"] = 1000
    roster = tmp_path / DEFAULT_ROSTER.name
    _write_json(roster, document)
    with pytest.raises(SupervisorActivationContractError, match="roster"):
        verify(roster_path=roster)


def test_supervisor_activation_rejects_binary_drift(tmp_path: Path) -> None:
    binary = tmp_path / DEFAULT_BINARY.name
    shutil.copyfile(DEFAULT_BINARY, binary)
    binary.chmod(0o755)
    raw = bytearray(binary.read_bytes())
    raw[-1] ^= 0x01
    binary.write_bytes(raw)
    binary.chmod(0o555)
    with pytest.raises(SupervisorActivationContractError, match="binary"):
        verify(binary_path=binary)


def test_supervisor_activation_rejects_sbom_drift(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_SBOM.read_text(encoding="utf-8"))
    document["packages"][0]["versionInfo"] = "drifted"
    sbom = tmp_path / DEFAULT_SBOM.name
    _write_json(sbom, document)
    with pytest.raises(SupervisorActivationContractError, match="SBOM"):
        verify(sbom_path=sbom)


def test_supervisor_activation_rejects_preflight_drift(tmp_path: Path) -> None:
    preflight = tmp_path / DEFAULT_PREFLIGHT.name
    preflight.write_bytes(DEFAULT_PREFLIGHT.read_bytes() + b"\n# drift\n")
    with pytest.raises(SupervisorActivationContractError, match="preflight"):
        verify(preflight_path=preflight)


def test_supervisor_activation_rejects_foundation_cross_wire(tmp_path: Path) -> None:
    contract = _mutated_contract(
        tmp_path,
        lambda document: document["foundation"].update(
            merged_main_commit_oid="0" * 40
        ),
    )
    with pytest.raises(SupervisorActivationContractError, match="foundation"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_ci_sparse_omission(tmp_path: Path) -> None:
    original = DEFAULT_WORKFLOWS[0]
    workflow = tmp_path / original.name
    workflow.write_text(
        original.read_text(encoding="utf-8").replace(
            "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1.json",
            "DRIFTED",
        ),
        encoding="utf-8",
    )
    with pytest.raises(SupervisorActivationContractError, match="workflow"):
        verify(workflow_paths=(workflow, *DEFAULT_WORKFLOWS[1:]))


def test_supervisor_activation_rejects_ci_authority_audit_omission(
    tmp_path: Path,
) -> None:
    audit = tmp_path / DEFAULT_CI_AUDIT.name
    audit.write_text(
        DEFAULT_CI_AUDIT.read_text(encoding="utf-8").replace(
            "full_pipeline_cpu_supervisor_activation_authority_fail_closed",
            "DRIFTED",
        ),
        encoding="utf-8",
    )
    with pytest.raises(SupervisorActivationContractError, match="CI authority audit"):
        verify(ci_audit_path=audit)


def test_supervisor_activation_rejects_duplicate_json_key(tmp_path: Path) -> None:
    raw = DEFAULT_CONTRACT.read_text(encoding="utf-8")
    contract = tmp_path / DEFAULT_CONTRACT.name
    contract.write_text(
        raw.replace(
            '  "activation_id":',
            '  "activation_id": "duplicate",\n  "activation_id":',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(SupervisorActivationContractError, match="duplicate JSON"):
        verify(contract_path=contract)


def test_supervisor_activation_rejects_noncanonical_json(tmp_path: Path) -> None:
    contract = tmp_path / DEFAULT_CONTRACT.name
    contract.write_text(
        DEFAULT_CONTRACT.read_text(encoding="ascii").replace("{\n", "{ \n", 1),
        encoding="ascii",
    )
    with pytest.raises(SupervisorActivationContractError, match="not canonical"):
        verify(contract_path=contract)
