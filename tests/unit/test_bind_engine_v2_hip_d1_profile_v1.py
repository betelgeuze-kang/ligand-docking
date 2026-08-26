from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/bind_engine_v2_hip_d1_profile_v1.py"
PROFILE_PATH = ROOT / "config/engine_v2_hip_d1_benchmark_profile_v1.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BINDER = _load_module("bind_engine_v2_hip_d1_profile_v1", TOOL)


def _profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _request() -> dict:
    profile = _profile()
    case_ids = [f"D1_CASE_{index:02d}" for index in range(32)]
    request = {
        "schema_id": BINDER.BINDING_REQUEST_SCHEMA,
        "base_profile_sha256": profile["profile_sha256"],
        "manifest_sha256": "a" * 64,
        "ordered_case_ids": case_ids,
        "ordered_candidate_ids_by_case": {
            case_id: [f"{case_id}:CANDIDATE:{slot:02d}" for slot in range(64)]
            for case_id in case_ids
        },
        "authority": copy.deepcopy(BINDER.AUTHORITY),
    }
    request["request_sha256"] = BINDER._hash(request)
    return request


def _reseal_request(request: dict) -> None:
    request.pop("request_sha256", None)
    request["request_sha256"] = BINDER._hash(request)


def _reseal_profile(profile: dict) -> None:
    profile.pop("profile_sha256", None)
    profile["profile_sha256"] = BINDER._hash(profile)


def test_profile_only_preserves_unbound_non_authority() -> None:
    result = BINDER.profile_only(_profile())
    assert result == {
        "ok": True,
        "profile_sha256": _profile()["profile_sha256"],
        "manifest_bound": False,
        "result_verification_authorized": False,
        "device_execution_performed": False,
        "molecular_execution_performed": False,
        "authority_granted": False,
    }


def test_binding_seals_exact_owner_case_and_candidate_identities() -> None:
    request = _request()
    bound, receipt = BINDER.bind_profile(_profile(), request)
    case_ids = request["ordered_case_ids"]

    assert bound["status"] == BINDER.VERIFIER.BOUND_STATUS
    assert bound["blockers"] == list(BINDER.VERIFIER.BOUND_BLOCKERS)
    assert bound["expected_manifest_sha256"] == "a" * 64
    assert bound["expected_ordered_case_ids_sha256"] == BINDER._hash(case_ids)
    assert bound["expected_ordered_candidate_ids_sha256_by_case"] == {
        case_id: BINDER._hash(request["ordered_candidate_ids_by_case"][case_id])
        for case_id in case_ids
    }
    assert bound["profile_sha256"] == BINDER._hash(
        {key: value for key, value in bound.items() if key != "profile_sha256"}
    )
    summary = BINDER.VERIFIER._verify_profile_document(bound)
    assert summary["manifest_bound"] is True
    assert summary["result_verification_authorized"] is False
    assert receipt["binding_request_sha256"] == request["request_sha256"]
    assert receipt["bound_profile_sha256"] == bound["profile_sha256"]
    assert receipt["requires_code_reviewed_digest_pin"] is True
    assert receipt["authority_granted"] is False
    assert receipt["receipt_sha256"] == BINDER._hash(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )


def test_binding_request_self_hash_and_profile_cross_wire_fail() -> None:
    request = _request()
    request["ordered_case_ids"].reverse()
    with pytest.raises(BINDER.ProfileBindingError, match="self-hash"):
        BINDER.bind_profile(_profile(), request)

    request = _request()
    request["base_profile_sha256"] = "b" * 64
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="cross-wire"):
        BINDER.bind_profile(_profile(), request)


def test_case_denominator_identity_and_candidate_map_are_exact() -> None:
    request = _request()
    request["ordered_case_ids"].pop()
    request["ordered_candidate_ids_by_case"].pop("D1_CASE_31")
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="case denominator"):
        BINDER.bind_profile(_profile(), request)

    request = _request()
    request["ordered_case_ids"][1] = request["ordered_case_ids"][0]
    request["ordered_candidate_ids_by_case"].pop("D1_CASE_01")
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="duplicated"):
        BINDER.bind_profile(_profile(), request)

    request = _request()
    request["ordered_candidate_ids_by_case"]["EXTRA_CASE"] = [
        f"EXTRA:{index}" for index in range(64)
    ]
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="candidate identity map"):
        BINDER.bind_profile(_profile(), request)


def test_candidate_denominator_and_identities_fail_closed() -> None:
    request = _request()
    request["ordered_candidate_ids_by_case"]["D1_CASE_00"].pop()
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="candidate denominator"):
        BINDER.bind_profile(_profile(), request)

    for invalid in (" ", "x" * 257):
        request = _request()
        request["ordered_candidate_ids_by_case"]["D1_CASE_00"][0] = invalid
        _reseal_request(request)
        with pytest.raises(BINDER.ProfileBindingError, match="candidate identity"):
            BINDER.bind_profile(_profile(), request)

    request = _request()
    candidates = request["ordered_candidate_ids_by_case"]["D1_CASE_00"]
    candidates[1] = candidates[0]
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="duplicated"):
        BINDER.bind_profile(_profile(), request)


def test_authority_requires_literal_false() -> None:
    request = _request()
    request["authority"] = {key: 0 for key in BINDER.AUTHORITY}
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="must be false"):
        BINDER.bind_profile(_profile(), request)

    request = _request()
    request["authority"]["device_execution_authorized"] = True
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="must be false"):
        BINDER.bind_profile(_profile(), request)


def test_already_bound_or_rehashed_invalid_base_profile_is_rejected() -> None:
    bound, _receipt = BINDER.bind_profile(_profile(), _request())
    request = _request()
    request["base_profile_sha256"] = bound["profile_sha256"]
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="already manifest-bound"):
        BINDER.bind_profile(bound, request)

    profile = _profile()
    profile["required_architecture_count"] = 3
    _reseal_profile(profile)
    request = _request()
    request["base_profile_sha256"] = profile["profile_sha256"]
    _reseal_request(request)
    with pytest.raises(BINDER.ProfileBindingError, match="architecture count"):
        BINDER.bind_profile(profile, request)


def test_cli_writes_once_without_execution(tmp_path: Path) -> None:
    request_path = tmp_path / "binding-request.json"
    output_path = tmp_path / "bound-profile.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    command = [
        sys.executable,
        str(TOOL),
        "--profile",
        str(PROFILE_PATH),
        "--binding-request",
        str(request_path),
        "--output",
        str(output_path),
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    summary = json.loads(first.stdout)
    written = json.loads(output_path.read_text(encoding="ascii"))
    assert summary["bound_profile_sha256"] == written["profile_sha256"]
    assert summary["device_execution_performed"] is False
    assert summary["molecular_execution_performed"] is False
    assert summary["result_verification_authorized"] is False
    assert summary["authority_granted"] is False

    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 1
    assert "output path must be absent" in second.stdout


def test_duplicate_keys_and_symlink_inputs_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_id":"one","schema_id":"two"}', encoding="utf-8")
    with pytest.raises(BINDER.ProfileBindingError, match="duplicate"):
        BINDER._load(duplicate)

    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(PROFILE_PATH)
    with pytest.raises(BINDER.ProfileBindingError, match="non-symlink"):
        BINDER._load(symlink)
