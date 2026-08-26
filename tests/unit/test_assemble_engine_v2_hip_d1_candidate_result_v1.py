from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/assemble_engine_v2_hip_d1_candidate_result_v1.py"
PROFILE = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"
VERIFIER_TEST = ROOT / "tests/unit/test_verify_engine_v2_hip_d1_benchmark_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ASSEMBLER = _load_module("assemble_engine_v2_hip_d1_candidate_result_v1", TOOL)
FIXTURE = _load_module("assemble_engine_v2_hip_d1_candidate_fixture", VERIFIER_TEST)


def _bound_fixture(tmp_path: Path) -> tuple[Path, dict, dict]:
    profile_path, profile = FIXTURE._bound_profile(tmp_path)
    result = FIXTURE._result(profile)
    return profile_path, profile, result


def _draft_with_stale_derivations(result: dict) -> dict:
    draft = copy.deepcopy(result)
    draft["ordered_case_ids_sha256"] = "0" * 64
    draft["result_sha256"] = "0" * 64
    for architecture in draft["architectures"]:
        for probe in architecture["failure_probes"]:
            probe["failure_stimulus_sha256"] = "0" * 64
            probe["observed_error_sha256"] = "0" * 64
            probe["probe_execution_receipt_sha256"] = "0" * 64
        for backend in architecture["backends"].values():
            backend["execution_backend_receipt_sha256"] = "0" * 64
            backend["repeat_execution_backend_receipt_sha256"] = "0" * 64
            backend["profiler_trace_sha256"] = "0" * 64
            backend["repeat_profiler_trace_sha256"] = "0" * 64
            backend["transfer_trace_sha256"] = "0" * 64
            backend["repeat_transfer_trace_sha256"] = "0" * 64
            backend["kernel_dispatches"] = []
            backend["repeat_kernel_dispatches"] = []
            backend["h2d_bytes"] = 1
            backend["d2h_bytes"] = 1
            backend["h2d_seconds"] = [1.0]
            backend["d2h_seconds"] = [1.0]
            for case in backend["cases"]:
                case["ordered_candidate_ids_sha256"] = "0" * 64
                for prefix in ("", "repeat_"):
                    for field in (
                        "decision_sha256",
                        "typed_failure_sha256",
                        "score_order_sha256",
                        "validity_sha256",
                        "rank_sha256",
                        "cluster_sha256",
                    ):
                        case[f"{prefix}{field}"] = "0" * 64
    return draft


def _save(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_assembler_rederives_complete_candidate_and_receipts(tmp_path: Path) -> None:
    profile_path, profile, expected = _bound_fixture(tmp_path)
    draft = _draft_with_stale_derivations(expected)

    assembled, receipt = ASSEMBLER.assemble_candidate_result(profile, draft)
    assert assembled["ordered_case_ids_sha256"] == ASSEMBLER._hash(
        assembled["ordered_case_ids"]
    )
    assert assembled["result_sha256"] == ASSEMBLER._hash(
        ASSEMBLER.VERIFIER._result_projection(assembled)
    )
    case = assembled["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    assert case["ordered_candidate_ids_sha256"] == ASSEMBLER._hash(
        case["ordered_candidate_ids"]
    )
    assert case["typed_failure_sha256"] == ASSEMBLER._hash(case["candidate_statuses"])
    assert case["repeat_typed_failure_sha256"] == ASSEMBLER._hash(
        case["repeat_candidate_statuses"]
    )
    for prefix in ("", "repeat_"):
        for field in ASSEMBLER.VERIFIER.DERIVED_DISCRETE_FIELDS:
            assert case[f"{prefix}{field}_sha256"] == ASSEMBLER._hash(
                case[f"{prefix}discrete_outputs"][field]
            )
    assert receipt["source_draft_sha256"] == ASSEMBLER._hash(draft)
    assert receipt["candidate_result_sha256"] == assembled["result_sha256"]
    assert receipt["candidate_validation_performed"] is False
    assert receipt["result_verification_authorized"] is False
    assert receipt["device_execution_performed"] is False
    assert receipt["molecular_execution_performed"] is False
    assert receipt["authority_granted"] is False
    assert all(value is False for value in receipt["authority"].values())
    assert receipt["receipt_sha256"] == ASSEMBLER._hash(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )

    candidate_path = _save(tmp_path / "assembled.json", assembled)
    validation = ASSEMBLER.VERIFIER.validate_candidate_result(
        profile_path, candidate_path
    )
    assert validation["candidate_valid"] is True
    assert validation["result_verification_authorized"] is False
    validated_receipt = ASSEMBLER._mark_candidate_validated(receipt)
    assert validated_receipt["candidate_validation_performed"] is True
    assert validated_receipt["receipt_sha256"] == ASSEMBLER._hash(
        {
            key: value
            for key, value in validated_receipt.items()
            if key != "receipt_sha256"
        }
    )


def test_unbound_profile_cannot_assemble_candidate() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="manifest-bound"):
        ASSEMBLER.profile_only(profile)
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="manifest-bound"):
        ASSEMBLER.assemble_candidate_result(profile, {})


def test_stimulus_observation_cross_wire_is_not_resealed(tmp_path: Path) -> None:
    _profile_path, profile, result = _bound_fixture(tmp_path)
    draft = _draft_with_stale_derivations(result)
    draft["architectures"][0]["failure_probes"][0]["failure_stimulus"][
        "stimulus_parameter_sha256"
    ] = "f" * 64
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="cross-wire"):
        ASSEMBLER.assemble_candidate_result(profile, draft)


@pytest.mark.parametrize("runtime", [True, 10**1000])
def test_malformed_trace_runtime_fails_without_uncaught_conversion(
    tmp_path: Path, runtime: object
) -> None:
    _profile_path, profile, result = _bound_fixture(tmp_path)
    draft = _draft_with_stale_derivations(result)
    draft["architectures"][0]["backends"]["hip_safe"]["profiler_trace"]["rows"][0][
        "runtime_seconds"
    ] = runtime
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="finite number"):
        ASSEMBLER.assemble_candidate_result(profile, draft)


def test_candidate_validation_rejects_owner_evidence_tamper_before_write(
    tmp_path: Path,
) -> None:
    profile_path, profile, result = _bound_fixture(tmp_path)
    draft = _draft_with_stale_derivations(result)
    case = draft["architectures"][0]["backends"]["hip_fast"]["cases"][0]
    case["scientific_values"][0] = 999.0
    assembled, _receipt = ASSEMBLER.assemble_candidate_result(profile, draft)
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="candidate validation"):
        ASSEMBLER._validate_and_write_absent(profile_path, output, assembled)
    assert not output.exists()


def test_cli_writes_once_and_reports_non_authority(tmp_path: Path) -> None:
    profile_path, _profile, result = _bound_fixture(tmp_path)
    draft_path = _save(tmp_path / "draft.json", _draft_with_stale_derivations(result))
    output_path = tmp_path / "candidate.json"
    command = [
        sys.executable,
        str(TOOL),
        "--profile",
        str(profile_path),
        "--draft",
        str(draft_path),
        "--output",
        str(output_path),
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    summary = json.loads(first.stdout)
    written = json.loads(output_path.read_text(encoding="ascii"))
    assert summary["candidate_result_sha256"] == written["result_sha256"]
    assert summary["candidate_validation_performed"] is True
    assert summary["result_verification_authorized"] is False
    assert summary["device_execution_performed"] is False
    assert summary["molecular_execution_performed"] is False
    assert summary["authority_granted"] is False

    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 1
    assert "output path must be absent" in second.stdout


def test_duplicate_keys_symlink_and_authority_escalation_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_id":"one","schema_id":"two"}', encoding="utf-8")
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="duplicate"):
        ASSEMBLER._load(duplicate)

    symlink = tmp_path / "profile-link.json"
    symlink.symlink_to(PROFILE)
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="non-symlink"):
        ASSEMBLER._load(symlink)

    profile_path, profile, result = _bound_fixture(tmp_path)
    draft = _draft_with_stale_derivations(result)
    draft["authority"]["device_execution_authorized"] = True
    assembled, _receipt = ASSEMBLER.assemble_candidate_result(profile, draft)
    output = tmp_path / "authority-must-not-exist.json"
    with pytest.raises(ASSEMBLER.CandidateAssemblyError, match="candidate validation"):
        ASSEMBLER._validate_and_write_absent(profile_path, output, assembled)
    assert not output.exists()
