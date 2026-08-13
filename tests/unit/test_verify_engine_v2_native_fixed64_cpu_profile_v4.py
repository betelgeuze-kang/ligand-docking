from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v4 import (
    NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS,
    NativeFixed64CPUProfileV4Error,
    require_compiled_profile_binding,
    require_profile_document,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v4.json"
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py"
_QUALIFICATION_SOURCE = _ROOT / "rust/betelgeuze-runtime/src/qualification.rs"
_DOCKING_SOURCE = _ROOT / "rust/betelgeuze-runtime/src/docking.rs"
_NATIVE_PIPELINE_SOURCE = _ROOT / "native/src/docking/fixed64_pipeline.cpp"
_PROBE_SOURCE = (
    _ROOT
    / "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
)
_TRANSITIVE_SOURCES = {
    path.as_posix(): (_ROOT / path).read_bytes()
    for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
}


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
        "c2a221b6ff18c990abff8c505ac0af87e4c8a05aa25aece20a477eca5cc114cb"
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
        _DOCKING_SOURCE.read_bytes(),
        _NATIVE_PIPELINE_SOURCE.read_bytes(),
        _PROBE_SOURCE.read_bytes(),
        dict(_TRANSITIVE_SOURCES),
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
            "qualification",
            b'Self::Complete => "synthetic_complete_64"',
            b'Self::Complete => "synthetic_complete_drift"',
        ),
        (
            "qualification",
            b"const FROZEN_SCORER_V1_TERM_COUNT: usize = 8",
            b"const FROZEN_SCORER_V1_TERM_COUNT: usize = 7",
        ),
        (
            "qualification",
            b"ligand_radii: [1.2; LIGAND_ATOM_COUNT]",
            b"ligand_radii: [1.3; LIGAND_ATOM_COUNT]",
        ),
        (
            "docking",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.1",
        ),
        (
            "native_pipeline",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0",
            b"betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.1",
        ),
        (
            "docking",
            b"hash_bool(hash, value.denominator_preserved);",
            b"hash_bool(hash, false);",
        ),
        (
            "native_pipeline",
            b"committed.denominator_preserved = UINT8_C(1);",
            b"committed.denominator_preserved = UINT8_C(0);",
        ),
        (
            "probe",
            b"Fixed64CpuProbeConfigV4::qualification_profile()",
            b"Fixed64CpuProbeConfigV4::unit_test()",
        ),
        (
            "qualification",
            b"pub const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = false;",
            b"pub const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = true;",
        ),
        (
            "qualification",
            b"pub const fn fixed64_cpu_v4_live_activation_admitted() -> bool {\n"
            b"    FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED\n"
            b"}",
            b"pub const fn fixed64_cpu_v4_live_activation_admitted() -> bool {\n"
            b"    true\n}",
        ),
    ),
)
def test_profile_v4_rejects_compiled_gate_drift(
    source_name: str, old: bytes, new: bytes
) -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    qualification = _QUALIFICATION_SOURCE.read_bytes()
    docking = _DOCKING_SOURCE.read_bytes()
    native_pipeline = _NATIVE_PIPELINE_SOURCE.read_bytes()
    probe = _PROBE_SOURCE.read_bytes()
    if source_name == "qualification":
        assert qualification.count(old) == 1
        qualification = qualification.replace(old, new, 1)
    elif source_name == "docking":
        assert docking.count(old) == 1
        docking = docking.replace(old, new, 1)
    elif source_name == "native_pipeline":
        assert native_pipeline.count(old) == 1
        native_pipeline = native_pipeline.replace(old, new, 1)
    else:
        assert probe.count(old) == 1
        probe = probe.replace(old, new, 1)

    with pytest.raises(NativeFixed64CPUProfileV4Error, match="compiled|entry point"):
        require_compiled_profile_binding(
            profile,
            qualification,
            docking,
            native_pipeline,
            probe,
            dict(_TRANSITIVE_SOURCES),
        )


def test_profile_v4_rejects_measurement_moved_before_activation_guard() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    probe = _PROBE_SOURCE.read_bytes()
    measurement_call = b"run_native_fixed64_cpu_probe_v4(config)"
    activation_guard = b"if !fixed64_cpu_v4_live_activation_admitted()"
    assert probe.count(measurement_call) == 1
    assert probe.count(activation_guard) == 1
    probe = probe.replace(measurement_call, b"measurement_call_moved", 1)
    probe = probe.replace(
        activation_guard,
        measurement_call + b";\n    " + activation_guard,
        1,
    )
    core = profile["measurement_core"]
    assert type(core) is dict
    core["native_probe_source_sha256"] = hashlib.sha256(probe).hexdigest()

    with pytest.raises(NativeFixed64CPUProfileV4Error, match="entry point|precede"):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            probe,
            dict(_TRANSITIVE_SOURCES),
        )


def test_profile_v4_rejects_transitive_kernel_source_drift() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    target = "native/src/docking/scorer_v1.cpp"
    changed[target] += b"\n// semantic drift\n"

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="transitive source manifest",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
        )


def test_profile_v4_rejects_transitive_source_path_omission() -> None:
    profile = require_profile_document(_PROFILE.read_bytes())
    changed = dict(_TRANSITIVE_SOURCES)
    changed.pop("rust/betelgeuze-docking-search/src/fixed64_ranking.rs")

    with pytest.raises(
        NativeFixed64CPUProfileV4Error,
        match="path set",
    ):
        require_compiled_profile_binding(
            profile,
            _QUALIFICATION_SOURCE.read_bytes(),
            _DOCKING_SOURCE.read_bytes(),
            _NATIVE_PIPELINE_SOURCE.read_bytes(),
            _PROBE_SOURCE.read_bytes(),
            changed,
        )


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
            "c2a221b6ff18c990abff8c505ac0af87e4c8a05aa25aece20a477eca5cc114cb"
        ),
        "reservation_created": False,
        "status": "verified",
    }
