from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v4 import (
    NativeFixed64CPUProfileV4Error,
    require_compiled_profile_binding,
    require_profile_document,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py"
_QUALIFICATION_SOURCE = _ROOT / "rust/betelgeuze-runtime/src/qualification.rs"
_PROBE_SOURCE = (
    _ROOT
    / "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def test_canonical_native_fixed64_cpu_profile_v4_is_frozen() -> None:
    raw = _PROFILE.read_bytes()
    profile = require_profile_document(raw)

    assert hashlib.sha256(raw).hexdigest() == (
        "6ed95a18dea8c5bbe325a32cf99aeca12be8580c1c2e386d1cf5112d65cab20b"
    )
    assert profile["profile_id"] == "engine_v2_native_fixed64_cpu_synthetic_v4"
    assert all(value is False for value in profile["authority"].values())
    assert [fixture["expected_generated_count"] for fixture in profile["fixtures"]] == [
        64,
        48,
    ]
    assert [
        fixture["expected_typed_failure_count"] for fixture in profile["fixtures"]
    ] == [0, 16]
    assert [fixture["receptor_atom_count"] for fixture in profile["fixtures"]] == [
        12,
        12,
    ]
    assert [fixture["ligand_atom_count"] for fixture in profile["fixtures"]] == [
        12,
        12,
    ]
    require_compiled_profile_binding(
        profile,
        _QUALIFICATION_SOURCE.read_bytes(),
        _PROBE_SOURCE.read_bytes(),
    )


@pytest.mark.parametrize(
    ("source_name", "old", "new"),
    (
        ("qualification", b"sample_rounds: 25", b"sample_rounds: 2"),
        (
            "qualification",
            b"maximum_rust_to_cpp_median_ratio: 1.25",
            b"maximum_rust_to_cpp_median_ratio: 2.0",
        ),
        ("qualification", b"const SLOT_COUNT: usize = 64", b"const SLOT_COUNT: usize = 63"),
        (
            "qualification",
            b"Self::FeatureSparse => (48, 16)",
            b"Self::FeatureSparse => (49, 15)",
        ),
        (
            "probe",
            b"Fixed64CpuProbeConfigV4::qualification_profile()",
            b"Fixed64CpuProbeConfigV4::unit_test()",
        ),
    ),
)
def test_profile_v4_rejects_compiled_gate_drift(
    source_name: str, old: bytes, new: bytes
) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    qualification = _QUALIFICATION_SOURCE.read_bytes()
    probe = _PROBE_SOURCE.read_bytes()
    if source_name == "qualification":
        assert qualification.count(old) == 1
        qualification = qualification.replace(old, new, 1)
    else:
        assert probe.count(old) == 1
        probe = probe.replace(old, new, 1)

    with pytest.raises(NativeFixed64CPUProfileV4Error, match="compiled|entry point"):
        require_compiled_profile_binding(profile, qualification, probe)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda profile: profile["authority"].update(qualification_authority=True),
        lambda profile: profile["restrictions"].update(hip_device_execution_allowed=True),
        lambda profile: profile["fixtures"][0].update(candidate_denominator=63),
        lambda profile: profile["gates"].update(score_term_count_exact=7),
        lambda profile: profile["numeric_parity"].update(relative_tolerance=1e-3),
        lambda profile: profile["performance"].update(maximum_ratio=2.0),
        lambda profile: profile["sampling"].update(schedule="rust_first"),
    ),
)
def test_profile_v4_rejects_authority_or_numeric_drift(mutate) -> None:
    profile = json.loads(_PROFILE.read_text(encoding="ascii"))
    changed = deepcopy(profile)
    mutate(changed)

    with pytest.raises(NativeFixed64CPUProfileV4Error):
        require_profile_document(_canonical(changed))


def test_profile_v4_rejects_noncanonical_or_duplicate_json() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="ascii"))
    compact = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("ascii")
    with pytest.raises(NativeFixed64CPUProfileV4Error, match="serialization"):
        require_profile_document(compact)

    duplicate = _PROFILE.read_bytes().replace(
        b'{\n  "authority": {',
        b'{\n  "status": "duplicate",\n  "authority": {',
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV4Error, match="duplicate"):
        require_profile_document(duplicate)


def test_profile_v4_cli_reports_non_consuming_authority_false() -> None:
    completed = subprocess.run(
        [sys.executable, str(_VERIFIER)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "all_authority_false": True,
        "candidate_denominator": 64,
        "compiled_profile_binding_verified": True,
        "execution_consumed": False,
        "fixture_count": 2,
        "profile_id": "engine_v2_native_fixed64_cpu_synthetic_v4",
        "profile_sha256": (
            "6ed95a18dea8c5bbe325a32cf99aeca12be8580c1c2e386d1cf5112d65cab20b"
        ),
        "reservation_created": False,
        "status": "verified",
    }
