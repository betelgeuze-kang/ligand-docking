#!/usr/bin/env python3
"""Verify the frozen, non-consuming native fixed64 CPU profile v4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import NoReturn


SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_profile/4.0.0"
PROFILE_ID = "engine_v2_native_fixed64_cpu_synthetic_v4"
PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_fixed64_cpu_profile_v4.json")
QUALIFICATION_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/qualification.rs"
)
DOCKING_SOURCE_RELATIVE_PATH = Path("rust/betelgeuze-runtime/src/docking.rs")
NATIVE_PIPELINE_SOURCE_RELATIVE_PATH = Path(
    "native/src/docking/fixed64_pipeline.cpp"
)
PROBE_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v4.rs"
)


class NativeFixed64CPUProfileV4Error(ValueError):
    """The frozen native fixed64 CPU profile failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUProfileV4Error(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _canonical_bytes(value: object) -> bytes:
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


def _exact_keys(value: object, expected: set[str], name: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        _fail(f"{name} key schema changed")
    return value


def require_profile_document(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV4Error("profile is not canonical ASCII JSON") from exc
    profile = _exact_keys(
        value,
        {
            "authority",
            "backends",
            "fixtures",
            "gates",
            "measurement_core",
            "numeric_parity",
            "performance",
            "profile_id",
            "restrictions",
            "sampling",
            "schema_id",
            "status",
        },
        "profile",
    )
    if raw != _canonical_bytes(profile):
        _fail("profile serialization is not canonical sorted indented JSON")
    if profile["schema_id"] != SCHEMA_ID or profile["profile_id"] != PROFILE_ID:
        _fail("profile identity changed")
    if profile["status"] != "implementation_profile_frozen_execution_not_consumed":
        _fail("profile execution status changed")

    authority = _exact_keys(
        profile["authority"],
        {
            "fresh_holdout_execution_authorized",
            "historical_ab_execution_authorized",
            "molecular_execution_authorized",
            "product_performance_claim_authorized",
            "public_benchmark_authorized",
            "qualification_authority",
            "reservation_authorized",
            "scientific_claim_authorized",
            "stage0_admission_authorized",
        },
        "authority",
    )
    if any(value is not False for value in authority.values()):
        _fail("all profile authority must remain false")

    backends = _exact_keys(
        profile["backends"],
        {"comparison", "fallback_allowed", "reference"},
        "backends",
    )
    if backends != {
        "comparison": "rust_cpu",
        "fallback_allowed": False,
        "reference": "cpp_cpu_reference",
    }:
        _fail("CPU backend comparison changed")

    fixtures = profile["fixtures"]
    expected_fixtures = [
        {
            "candidate_denominator": 64,
            "contains_molecular_data": False,
            "expected_generated_count": 64,
            "expected_typed_failure_count": 0,
            "fixture_id": "synthetic_complete_64",
            "fixture_payload_sha256": (
                "8478682324df3bd10e5fa6e2988436cec4c59e815dcf3444eaf3009f1a373df5"
            ),
            "fixture_source": "native_compiled_constant",
            "ligand_atom_count": 12,
            "receptor_atom_count": 12,
        },
        {
            "candidate_denominator": 64,
            "contains_molecular_data": False,
            "expected_generated_count": 48,
            "expected_typed_failure_count": 16,
            "fixture_id": "synthetic_feature_sparse_48_plus_16",
            "fixture_payload_sha256": (
                "9c93753ae23363c20d2f957fb521eedd1fe4f92fc39282c03c53d1f2674610c2"
            ),
            "fixture_source": "native_compiled_constant",
            "ligand_atom_count": 12,
            "receptor_atom_count": 12,
        },
    ]
    if fixtures != expected_fixtures:
        _fail("synthetic fixture contract changed")

    gates = _exact_keys(
        profile["gates"],
        {
            "authority_false_required",
            "candidate_denominator_exact",
            "cpp_repeat_projection_exact_required",
            "decision_sha256_exact_between_cpu_backends_required",
            "failure_codes_exact_required",
            "persistent_context_count_per_backend_exact",
            "rust_repeat_projection_exact_required",
            "score_term_count_exact",
            "top1_top5_and_v7_decisions_exact_required",
            "validity_decisions_exact_required",
        },
        "gates",
    )
    if gates != {
        "authority_false_required": True,
        "candidate_denominator_exact": 64,
        "cpp_repeat_projection_exact_required": True,
        "decision_sha256_exact_between_cpu_backends_required": True,
        "failure_codes_exact_required": True,
        "persistent_context_count_per_backend_exact": 1,
        "rust_repeat_projection_exact_required": True,
        "score_term_count_exact": 8,
        "top1_top5_and_v7_decisions_exact_required": True,
        "validity_decisions_exact_required": True,
    }:
        _fail("scientific parity gates changed")

    core = _exact_keys(
        profile["measurement_core"],
        {
            "candidate_graph",
            "native_binary",
            "native_cpp_pipeline_source_sha256",
            "native_pipeline_profile_id",
            "native_probe_source_sha256",
            "native_qualification_source_sha256",
            "native_rust_pipeline_source_sha256",
            "python_scientific_work_allowed",
            "receptor_context_recreated_inside_samples",
        },
        "measurement core",
    )
    qualification_source_sha256 = core["native_qualification_source_sha256"]
    probe_source_sha256 = core["native_probe_source_sha256"]
    rust_pipeline_source_sha256 = core["native_rust_pipeline_source_sha256"]
    cpp_pipeline_source_sha256 = core["native_cpp_pipeline_source_sha256"]
    if (
        type(qualification_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", qualification_source_sha256) is None
        or type(probe_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", probe_source_sha256) is None
        or type(rust_pipeline_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", rust_pipeline_source_sha256) is None
        or type(cpp_pipeline_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", cpp_pipeline_source_sha256) is None
    ):
        _fail("native measured source identity is not canonical SHA-256")
    if core != {
        "candidate_graph": [
            "fixed64_proposal",
            "geometric_admission",
            "rigid_refinement",
            "torsion_v7_refinement",
            "scorer_v1_8_term",
            "pose_validity",
            "stable_top_k",
            "direct_rmsd_clustering",
        ],
        "native_binary": "betelgeuze-fixed64-cpu-probe-v4",
        "native_cpp_pipeline_source_sha256": cpp_pipeline_source_sha256,
        "native_pipeline_profile_id": (
            "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0"
        ),
        "native_probe_source_sha256": probe_source_sha256,
        "native_qualification_source_sha256": qualification_source_sha256,
        "native_rust_pipeline_source_sha256": rust_pipeline_source_sha256,
        "python_scientific_work_allowed": False,
        "receptor_context_recreated_inside_samples": False,
    }:
        _fail("native measurement core changed")

    numeric = _exact_keys(
        profile["numeric_parity"],
        {
            "absolute_tolerance",
            "all_coordinate_states_compared",
            "all_refinement_objectives_compared",
            "all_scorer_v1_terms_compared",
            "all_validity_measurements_compared",
            "nonfinite_values_allowed",
            "relative_tolerance",
        },
        "numeric parity",
    )
    if numeric != {
        "absolute_tolerance": 1e-11,
        "all_coordinate_states_compared": True,
        "all_refinement_objectives_compared": True,
        "all_scorer_v1_terms_compared": True,
        "all_validity_measurements_compared": True,
        "nonfinite_values_allowed": False,
        "relative_tolerance": 4e-12,
    }:
        _fail("numeric parity contract changed")

    performance = _exact_keys(
        profile["performance"],
        {"gate", "maximum_ratio", "performance_claim_authorized", "scope"},
        "performance",
    )
    if performance != {
        "gate": "rust_cpu_median_div_cpp_cpu_reference_median_lte",
        "maximum_ratio": 1.25,
        "performance_claim_authorized": False,
        "scope": "synthetic_development_non_regression_only",
    }:
        _fail("performance gate changed")

    restrictions = _exact_keys(
        profile["restrictions"],
        {
            "actual_molecular_execution_allowed",
            "contains_molecular_cases",
            "fresh_or_historical_case_input_allowed",
            "github_actions_live_qualification_allowed",
            "github_actions_production_authority_allowed",
            "hip_device_execution_allowed",
            "public_or_scientific_performance_claim_allowed",
            "reservation_allowed",
            "result_dependent_configuration_allowed",
            "test_double_production_authority_allowed",
        },
        "restrictions",
    )
    if any(value is not False for value in restrictions.values()):
        _fail("all restricted capabilities must remain false")

    sampling = _exact_keys(
        profile["sampling"],
        {"clock", "sample_rounds", "schedule", "timed_scope", "warmup_rounds"},
        "sampling",
    )
    if sampling != {
        "clock": "std_steady_instant",
        "sample_rounds": 25,
        "schedule": "paired_ab_ba",
        "timed_scope": "persistent_pipeline_run_only",
        "warmup_rounds": 5,
    }:
        _fail("sampling contract changed")
    return profile


def require_compiled_profile_binding(
    profile: dict[str, object],
    qualification_source_raw: bytes,
    docking_source_raw: bytes,
    native_pipeline_source_raw: bytes,
    probe_source_raw: bytes,
) -> None:
    """Bind the native gate constants and entry point to the frozen JSON."""

    try:
        source = qualification_source_raw.decode("ascii")
        probe = probe_source_raw.decode("ascii")
    except UnicodeError as exc:
        raise NativeFixed64CPUProfileV4Error(
            "native qualification and probe sources must be ASCII"
        ) from exc
    try:
        docking_source = docking_source_raw.decode("utf-8")
        native_pipeline_source = native_pipeline_source_raw.decode("utf-8")
    except UnicodeError as exc:
        raise NativeFixed64CPUProfileV4Error(
            "native pipeline sources must be UTF-8"
        ) from exc

    profile_id_matches = re.findall(
        r'pub const FIXED64_CPU_QUALIFICATION_V4_PROFILE_ID: &str\s*=\s*"([^"]+)";',
        source,
    )
    if profile_id_matches != [PROFILE_ID]:
        _fail("compiled qualification profile identity changed")

    core = profile["measurement_core"]
    if type(core) is not dict:
        _fail("profile measurement core is unavailable for compiled binding")
    if hashlib.sha256(qualification_source_raw).hexdigest() != core.get(
        "native_qualification_source_sha256"
    ):
        _fail("compiled qualification source changed from the frozen profile")
    if hashlib.sha256(probe_source_raw).hexdigest() != core.get(
        "native_probe_source_sha256"
    ):
        _fail("compiled native probe source changed from the frozen profile")
    if hashlib.sha256(docking_source_raw).hexdigest() != core.get(
        "native_rust_pipeline_source_sha256"
    ):
        _fail("compiled native Rust pipeline source changed from the frozen profile")
    if hashlib.sha256(native_pipeline_source_raw).hexdigest() != core.get(
        "native_cpp_pipeline_source_sha256"
    ):
        _fail("compiled native C++ pipeline source changed from the frozen profile")
    library_activation_function = re.compile(
        r"pub\s+const\s+fn\s+fixed64_cpu_v4_live_activation_admitted\(\)"
        r"\s*->\s*bool\s*\{\s*FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED\s*\}"
    )
    unit_test_profile_gate = "if config != Fixed64CpuProbeConfigV4::unit_test()"
    qualification_profile_gate = (
        "if config != Fixed64CpuProbeConfigV4::qualification_profile()"
    )
    library_activation_guard = "if !fixed64_cpu_v4_live_activation_admitted()"
    fixture_construction = "let fixture = SyntheticFixture::new();"
    if (
        source.count(
            "pub const FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED: bool = false;"
        )
        != 1
        or len(library_activation_function.findall(source)) != 1
        or source.count(unit_test_profile_gate) != 1
        or source.count(qualification_profile_gate) != 1
        or source.count(library_activation_guard) != 1
        or source.count(fixture_construction) != 1
        or not (
            source.index(unit_test_profile_gate)
            < source.index(qualification_profile_gate)
            < source.index(library_activation_guard)
        )
        or source.index(library_activation_guard)
        > source.index(fixture_construction)
    ):
        _fail("compiled public qualification API is not activation-gated")

    native_pipeline_profile_id = core.get("native_pipeline_profile_id")
    rust_pipeline_id_matches = re.findall(
        r'pub const FIXED64_NATIVE_PIPELINE_PROFILE_ID: &str\s*=\s*"([^"]+)";',
        docking_source,
    )
    cpp_pipeline_id_matches = re.findall(
        r'constexpr char kProfileId\[\]\s*=\s*"([^"]+)";',
        native_pipeline_source,
    )
    if (
        rust_pipeline_id_matches != [native_pipeline_profile_id]
        or cpp_pipeline_id_matches != [native_pipeline_profile_id]
        or docking_source.count(str(native_pipeline_profile_id)) != 1
        or docking_source.count("FIXED64_NATIVE_PIPELINE_PROFILE_ID") != 6
        or native_pipeline_source.count(str(native_pipeline_profile_id)) != 1
        or native_pipeline_source.count("kProfileId") != 6
        or docking_source.count("Self::profile_id()?;") != 1
        or docking_source.count(
            "profile_id != FIXED64_NATIVE_PIPELINE_PROFILE_ID"
        )
        != 1
        or docking_source.count("hash.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);")
        != 3
        or docking_source.count(
            "pipeline_batch.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);"
        )
        != 1
    ):
        _fail("compiled native pipeline profile identity changed")

    config_matches = re.findall(
        r"pub const fn qualification_profile\(\) -> Self \{\s*"
        r"Self \{\s*"
        r"warmup_rounds:\s*(\d+),\s*"
        r"sample_rounds:\s*(\d+),\s*"
        r"absolute_tolerance:\s*([0-9.eE+-]+),\s*"
        r"relative_tolerance:\s*([0-9.eE+-]+),\s*"
        r"maximum_rust_to_cpp_median_ratio:\s*([0-9.eE+-]+),\s*"
        r"\}\s*\}",
        source,
    )
    if len(config_matches) != 1:
        _fail("compiled qualification gate definition changed")
    warmup, samples, absolute, relative, ratio = config_matches[0]
    sampling = profile["sampling"]
    numeric = profile["numeric_parity"]
    performance = profile["performance"]
    if type(sampling) is not dict or type(numeric) is not dict or type(performance) is not dict:
        _fail("profile gate sections are unavailable for compiled binding")
    try:
        compiled_gate = {
            "warmup_rounds": int(warmup),
            "sample_rounds": int(samples),
            "absolute_tolerance": float(absolute),
            "relative_tolerance": float(relative),
            "maximum_ratio": float(ratio),
        }
    except ValueError as exc:
        raise NativeFixed64CPUProfileV4Error(
            "compiled qualification gate is not numeric"
        ) from exc
    expected_gate = {
        "warmup_rounds": sampling["warmup_rounds"],
        "sample_rounds": sampling["sample_rounds"],
        "absolute_tolerance": numeric["absolute_tolerance"],
        "relative_tolerance": numeric["relative_tolerance"],
        "maximum_ratio": performance["maximum_ratio"],
    }
    if compiled_gate != expected_gate:
        _fail("compiled qualification gate drifted from the frozen profile")

    slot_matches = re.findall(r"const SLOT_COUNT: usize = (\d+);", source)
    atom_matches = re.findall(r"const LIGAND_ATOM_COUNT: usize = (\d+);", source)
    fixtures = profile["fixtures"]
    gates = profile["gates"]
    if type(fixtures) is not list or type(gates) is not dict:
        _fail("profile fixture or gate sections are unavailable for compiled binding")
    expected_atoms = {
        fixture["receptor_atom_count"]
        for fixture in fixtures
        if type(fixture) is dict
    } | {
        fixture["ligand_atom_count"]
        for fixture in fixtures
        if type(fixture) is dict
    }
    if len(expected_atoms) != 1:
        _fail("frozen fixtures do not share one compiled atom denominator")
    expected_atom_count = next(iter(expected_atoms))
    if slot_matches != [str(gates["candidate_denominator_exact"])] or atom_matches != [
        str(expected_atom_count)
    ]:
        _fail("compiled fixed64 or atom denominator drifted from the frozen profile")

    expected_counts = [
        (
            fixture["expected_generated_count"],
            fixture["expected_typed_failure_count"],
        )
        for fixture in fixtures
        if type(fixture) is dict
    ]
    compiled_counts = [
        tuple(int(value) for value in match)
        for match in re.findall(
            r"Self::(?:Complete|FeatureSparse) => \((\d+), (\d+)\)", source
        )
    ]
    if compiled_counts != expected_counts:
        _fail("compiled fixture counts drifted from the frozen profile")

    expected_fixture_ids = [
        fixture["fixture_id"] for fixture in fixtures if type(fixture) is dict
    ]
    compiled_fixture_ids = [
        fixture_id
        for _, fixture_id in re.findall(
            r'Self::(Complete|FeatureSparse)\s*=>\s*"([^"]+)"', source
        )
    ]
    if compiled_fixture_ids != expected_fixture_ids:
        _fail("compiled fixture identities drifted from the frozen profile")

    expected_fixture_payloads = [
        fixture["fixture_payload_sha256"]
        for fixture in fixtures
        if type(fixture) is dict
    ]
    compiled_fixture_payloads = re.findall(
        r"const (?:COMPLETE|FEATURE_SPARSE)_FIXTURE_PAYLOAD_SHA256_HEX: "
        r'&str\s*=\s*"([0-9a-f]{64})";',
        source,
    )
    fixture_payload_mappings = re.findall(
        r"Self::(Complete|FeatureSparse)\s*=>\s*"
        r"((?:COMPLETE|FEATURE_SPARSE)_FIXTURE_PAYLOAD_SHA256_HEX)",
        source,
    )
    if (
        compiled_fixture_payloads != expected_fixture_payloads
        or fixture_payload_mappings
        != [
            ("Complete", "COMPLETE_FIXTURE_PAYLOAD_SHA256_HEX"),
            (
                "FeatureSparse",
                "FEATURE_SPARSE_FIXTURE_PAYLOAD_SHA256_HEX",
            ),
        ]
        or source.count(
            "canonical_fixture_payload_sha256(variant, scientific_context, input)"
        )
        != 1
        or source.count(
            "fixture_payload_sha256_hex != variant.expected_payload_sha256_hex()"
        )
        != 1
        or probe.count("digest(value.fixture_payload_sha256)") != 1
    ):
        _fail("compiled fixture payload identities drifted from the frozen profile")

    scorer_term_matches = re.findall(
        r"const FROZEN_SCORER_V1_TERM_COUNT: usize = (\d+);", source
    )
    scorer_term_assertions = re.findall(
        r"const _:\s*\[\(\);\s*FROZEN_SCORER_V1_TERM_COUNT\]\s*=\s*"
        r"\[\(\);\s*sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize\];",
        source,
    )
    runtime_scorer_gate = (
        "sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize "
        "== FROZEN_SCORER_V1_TERM_COUNT"
    )
    if (
        scorer_term_matches != [str(gates["score_term_count_exact"])]
        or len(scorer_term_assertions) != 1
        or source.count(runtime_scorer_gate) != 1
        or source.count(
            "score_term_count: sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize"
        )
        != 1
        or probe.count("value.score_term_count") != 1
    ):
        _fail("compiled ScorerV1 term-count gate drifted from the frozen profile")

    activation_guard = "if !fixed64_cpu_v4_live_activation_admitted()"
    qualification_call = "Fixed64CpuProbeConfigV4::qualification_profile()"
    qualification_binding = (
        "let config = Fixed64CpuProbeConfigV4::qualification_profile();"
    )
    measurement_call = "run_native_fixed64_cpu_probe_v4(config)"
    if (
        probe.count("fixed64_cpu_v4_live_activation_admitted") != 2
        or "FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED" in probe
        or probe.count(activation_guard) != 1
        or probe.count("return ExitCode::from(3);") != 1
        or probe.count(qualification_call) != 1
        or probe.count(qualification_binding) != 1
        or probe.count("Fixed64CpuProbeConfigV4") != 2
        or "Fixed64CpuProbeConfigV4::unit_test()" in probe
        or "Fixed64CpuProbeConfigV4 {" in probe
        or probe.count(measurement_call) != 1
        or probe.count("run_native_fixed64_cpu_probe_v4") != 2
    ):
        _fail("native probe entry point is not bound to the qualification profile")
    if not (
        probe.index(activation_guard)
        < probe.index(qualification_binding)
        < probe.index(measurement_call)
    ):
        _fail("native probe activation gate does not precede configuration and measurement")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    profile = require_profile_document(raw)
    require_compiled_profile_binding(
        profile,
        (root / QUALIFICATION_SOURCE_RELATIVE_PATH).read_bytes(),
        (root / DOCKING_SOURCE_RELATIVE_PATH).read_bytes(),
        (root / NATIVE_PIPELINE_SOURCE_RELATIVE_PATH).read_bytes(),
        (root / PROBE_SOURCE_RELATIVE_PATH).read_bytes(),
    )
    print(
        json.dumps(
            {
                "all_authority_false": True,
                "candidate_denominator": 64,
                "compiled_profile_binding_verified": True,
                "execution_consumed": False,
                "fixture_count": 2,
                "profile_id": PROFILE_ID,
                "profile_sha256": hashlib.sha256(raw).hexdigest(),
                "reservation_created": False,
                "status": "verified",
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
