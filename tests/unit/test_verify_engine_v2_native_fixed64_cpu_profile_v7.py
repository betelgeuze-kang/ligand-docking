from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_native_fixed64_cpu_profile_v7 as verifier
from tools.verify_engine_v2_native_fixed64_cpu_profile_v7 import (
    NativeFixed64CPUProfileV7Error,
    require_activation_source_contract,
    require_bound_source_commit,
    require_bound_source_tree,
    require_packaged_activation_assets,
    require_post_qualification_build_boundary,
    require_post_qualification_build_contract,
    require_profile_document_v7,
    require_source_manifest_document,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / verifier.PROFILE_RELATIVE_PATH
_MANIFEST = _ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
_V6_PROFILE = _ROOT / verifier.V6_PROFILE_RELATIVE_PATH
_V6_ARCHIVE = _ROOT / verifier.V6_ARCHIVE_RELATIVE_PATH
_TOOL = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"
_RUSTC_WRAPPER = _ROOT / verifier.RUSTC_WRAPPER_RELATIVE_PATH


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


def _real_evidence() -> tuple[bytes, bytes, bytes, bytes, dict[str, bytes]]:
    profile_raw = _PROFILE.read_bytes()
    manifest_raw = _MANIFEST.read_bytes()
    v6_profile_raw = _V6_PROFILE.read_bytes()
    v6_archive_raw = _V6_ARCHIVE.read_bytes()
    manifest = require_source_manifest_document(manifest_raw)
    sources = require_bound_source_commit(_ROOT, manifest)
    return profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources


def test_profile_v7_rederives_from_archived_v6_and_exact_sources() -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    profile = require_profile_document_v7(
        profile_raw,
        v6_profile_raw,
        v6_archive_raw,
        manifest_raw,
        sources,
    )
    require_activation_source_contract(sources)
    require_packaged_activation_assets(
        _ROOT,
        profile_raw=profile_raw,
        v6_archive_raw=v6_archive_raw,
        source_manifest_raw=manifest_raw,
        cargo_lock_raw=sources[verifier.CARGO_LOCK_RELATIVE_PATH.as_posix()],
        cargo_manifest_raw=sources[verifier.CARGO_MANIFEST_RELATIVE_PATH.as_posix()],
    )
    assert profile["profile_id"] == verifier.PROFILE_ID
    authority = profile["authority"]
    runner = profile["runner"]
    assert isinstance(authority, dict)
    assert isinstance(runner, dict)
    assert authority["qualification_authority"] is False
    assert runner["account_scoped_exactly_once"] is True


def test_packaged_activation_asset_drift_fails_closed(tmp_path: Path) -> None:
    expected = {
        verifier.PACKAGED_PROFILE_RELATIVE_PATH: _PROFILE.read_bytes(),
        verifier.PACKAGED_V6_ARCHIVE_RELATIVE_PATH: _V6_ARCHIVE.read_bytes(),
        verifier.PACKAGED_SOURCE_MANIFEST_RELATIVE_PATH: _MANIFEST.read_bytes(),
        verifier.PACKAGED_CARGO_LOCK_RELATIVE_PATH: (
            _ROOT / verifier.CARGO_LOCK_RELATIVE_PATH
        ).read_bytes(),
        verifier.PACKAGED_CARGO_MANIFEST_RELATIVE_PATH: (
            _ROOT / verifier.CARGO_MANIFEST_RELATIVE_PATH
        ).read_bytes(),
    }
    for relative, raw in expected.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (tmp_path / verifier.PACKAGED_PROFILE_RELATIVE_PATH).write_bytes(b"{}\n")
    with pytest.raises(
        NativeFixed64CPUProfileV7Error,
        match="packaged v7 activation asset drifted",
    ):
        require_packaged_activation_assets(
            tmp_path,
            profile_raw=_PROFILE.read_bytes(),
            v6_archive_raw=_V6_ARCHIVE.read_bytes(),
            source_manifest_raw=_MANIFEST.read_bytes(),
            cargo_lock_raw=(_ROOT / verifier.CARGO_LOCK_RELATIVE_PATH).read_bytes(),
            cargo_manifest_raw=(
                _ROOT / verifier.CARGO_MANIFEST_RELATIVE_PATH
            ).read_bytes(),
        )


def test_command_line_verifier_is_non_consuming_and_authority_false() -> None:
    completed = subprocess.run(
        [sys.executable, str(_TOOL)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.stderr == ""
    assert payload["compiled_profile_binding_verified"] is True
    assert payload["execution_consumed"] is False
    assert payload["recorded_execution_consumed"] is True
    assert payload["current_build_activation_bound"] is False
    assert payload["non_consuming_preflight_only"] is True
    assert payload["all_authority_false"] is True
    assert payload["source_count"] == 196
    assert payload["source_commit_oid"] == verifier.QUALIFIED_SOURCE_COMMIT_OID
    assert payload["source_verification_mode"] == "historical_git_commit"


def test_post_qualification_build_is_explicitly_unbound() -> None:
    require_post_qualification_build_boundary(_ROOT)
    contract = require_post_qualification_build_contract(
        (_ROOT / verifier.POST_QUALIFICATION_BUILD_BOUNDARY_RELATIVE_PATH).read_bytes()
    )
    assert contract["historical_evidence"]["execution_consumed"] is True


def test_post_qualification_rerun_authority_fails_closed() -> None:
    path = _ROOT / verifier.POST_QUALIFICATION_BUILD_BOUNDARY_RELATIVE_PATH
    document = json.loads(path.read_text(encoding="ascii"))
    document["authority"]["qualification_rerun_authorized"] = True
    with pytest.raises(
        NativeFixed64CPUProfileV7Error,
        match="build boundary authority",
    ):
        require_post_qualification_build_contract(_canonical(document))


def _invoke_rustc_wrapper(
    arguments: list[str], *, rustc: str = "/bin/true"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_RUSTC_WRAPPER), rustc, *arguments],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "BETELGEUZE_V7_QUALIFICATION_BUILD": "1"},
    )


def _runtime_rustc_arguments() -> list[str]:
    return [
        "--crate-name",
        "betelgeuze_runtime",
        "--crate-type",
        "lib",
        "--cfg",
        'feature="default"',
        "--cfg",
        "betelgeuze_v7_qualification_build",
        "--check-cfg",
        "cfg(betelgeuze_v7_effective_rust_flags_verified)",
        "-C",
        "opt-level=3",
        "-C",
        "panic=abort",
        "-C",
        "codegen-units=1",
        "-C",
        "overflow-checks=on",
        "-C",
        "metadata=0123456789abcdef",
        "-C",
        "extra-filename=-0123456789abcdef",
    ]


def _binary_rustc_arguments() -> list[str]:
    arguments = _runtime_rustc_arguments()
    arguments[arguments.index("betelgeuze_runtime")] = (
        "betelgeuze_fixed64_cpu_qualify_v7"
    )
    arguments[arguments.index("lib")] = "bin"
    arguments.extend(["-C", "lto=fat"])
    return arguments


def test_rustc_wrapper_accepts_only_the_frozen_effective_runtime_invocation() -> None:
    completed = _invoke_rustc_wrapper(_runtime_rustc_arguments())
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_rustc_wrapper_injects_library_lto_after_validating_cargo_flags() -> None:
    completed = _invoke_rustc_wrapper(_runtime_rustc_arguments(), rustc="/bin/echo")
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.count("linker-plugin-lto") == 1
    assert completed.stdout.count("betelgeuze_v7_effective_rust_flags_verified") == 3


def test_rustc_wrapper_preserves_single_cargo_library_lto() -> None:
    arguments = _runtime_rustc_arguments()
    arguments.extend(["-C", "linker-plugin-lto"])
    completed = _invoke_rustc_wrapper(arguments, rustc="/bin/echo")
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.count("linker-plugin-lto") == 1


def test_rustc_wrapper_accepts_only_the_frozen_effective_binary_invocation() -> None:
    completed = _invoke_rustc_wrapper(_binary_rustc_arguments())
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_rustc_wrapper_does_not_inject_library_lto_into_final_binary() -> None:
    completed = _invoke_rustc_wrapper(_binary_rustc_arguments(), rustc="/bin/echo")
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "linker-plugin-lto" not in completed.stdout
    assert completed.stdout.count("lto=fat") == 1


@pytest.mark.parametrize("arguments", [["-vV"], ["--version"]])
def test_rustc_wrapper_allows_only_frozen_identity_queries(
    arguments: list[str],
) -> None:
    completed = _invoke_rustc_wrapper(arguments)
    assert completed.returncode == 0
    assert completed.stderr == ""


def test_rustc_wrapper_rejects_unlisted_non_compile_query() -> None:
    completed = _invoke_rustc_wrapper(["--print", "cfg"])
    assert completed.returncode == 86
    assert "rustc wrapper rejected build" in completed.stderr


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_lto",
        "native_cpu",
        "duplicate_metadata",
        "duplicate_library_lto",
        "extra_cfg",
    ],
)
def test_rustc_wrapper_rejects_effective_flag_bypasses(mutation: str) -> None:
    if mutation == "missing_lto":
        arguments = _binary_rustc_arguments()
        position = arguments.index("lto=fat")
        del arguments[position - 1 : position + 1]
    elif mutation == "native_cpu":
        arguments = _runtime_rustc_arguments()
        arguments.extend(["-C", "target-cpu=native"])
    elif mutation == "duplicate_metadata":
        arguments = _runtime_rustc_arguments()
        arguments.extend(["-C", "metadata=fedcba9876543210"])
    elif mutation == "duplicate_library_lto":
        arguments = _runtime_rustc_arguments()
        arguments.extend(["-C", "linker-plugin-lto", "-C", "linker-plugin-lto"])
    else:
        arguments = _runtime_rustc_arguments()
        arguments.extend(["--cfg", "result_dependent_fast_path"])
    completed = _invoke_rustc_wrapper(arguments)
    assert completed.returncode == 86
    assert completed.stdout == ""
    assert "rustc wrapper rejected build" in completed.stderr


def test_command_line_verifier_resolves_sibling_without_site_packages() -> None:
    completed = subprocess.run(
        [sys.executable, "-S", str(_TOOL)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.stderr == ""
    assert payload["profile_id"] == verifier.PROFILE_ID
    assert payload["compiled_profile_binding_verified"] is True


def test_duplicate_profile_key_fails_closed() -> None:
    raw = _PROFILE.read_bytes().replace(
        b'{\n  "authority": {',
        b'{\n  "authority": {},\n  "authority": {',
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="duplicate JSON key"):
        require_profile_document_v7(
            raw,
            _V6_PROFILE.read_bytes(),
            _V6_ARCHIVE.read_bytes(),
            _MANIFEST.read_bytes(),
            {},
        )


def test_scientific_gate_drift_fails_even_with_rebound_profile_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    profile["gates"]["candidate_denominator_exact"] = 65
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="scientific gates"):
        require_profile_document_v7(
            mutated,
            v6_profile_raw,
            v6_archive_raw,
            manifest_raw,
            sources,
        )


def test_scorer_and_validity_rederivation_gate_removal_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    del profile["gates"]["scorer_v1_terms_rederivable_required"]
    del profile["gates"]["validity_measurements_rederivable_required"]
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="scientific gates"):
        require_profile_document_v7(
            mutated,
            v6_profile_raw,
            v6_archive_raw,
            manifest_raw,
            sources,
        )


def test_authority_enablement_fails_even_with_rebound_profile_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    profile["authority"]["qualification_authority"] = True
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="authority"):
        require_profile_document_v7(
            mutated,
            v6_profile_raw,
            v6_archive_raw,
            manifest_raw,
            sources,
        )


def test_build_configuration_drift_fails_even_with_rebound_profile_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    profile["build_configuration"]["cargo_lto"] = False
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="build configuration"):
        require_profile_document_v7(
            mutated,
            v6_profile_raw,
            v6_archive_raw,
            manifest_raw,
            sources,
        )


def test_current_post_qualification_source_tree_cannot_inherit_consumed_manifest() -> None:
    parsed = require_source_manifest_document(_MANIFEST.read_bytes())
    # Repository D0 sources were added after the one-shot V7 qualification. The
    # current tree must therefore remain unbound instead of silently inheriting
    # authority from the consumed historical manifest.
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="unbound or missing source"):
        require_bound_source_tree(_ROOT, parsed)


def test_profile_source_cross_wiring_fails_closed() -> None:
    profile_raw, manifest_raw, v6_profile_raw, v6_archive_raw, sources = (
        _real_evidence()
    )
    sources = dict(sources)
    sources[verifier.BINARY_SOURCE_RELATIVE_PATH.as_posix()] += b"\n"
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="source bindings"):
        require_profile_document_v7(
            profile_raw,
            v6_profile_raw,
            v6_archive_raw,
            manifest_raw,
            sources,
        )


def test_attempt_before_preflight_order_is_static_authority_boundary() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"preflight_native_fixed64_cpu_v7()?;",
        b"preflight_native_fixed64_cpu_v7_unsealed()?;",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="ordering token"):
        require_activation_source_contract(sources)


def test_compile_time_transitive_source_binding_is_required() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.BUILD_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"bind_compiled_source_graph(&source_root)",
        b"trust_declared_source_graph(&source_root)",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="compile-time source"):
        require_activation_source_contract(sources)


def test_effective_rustc_wrapper_contract_is_compile_bound() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUSTC_WRAPPER_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"effective -C option names differ from the frozen profile",
        b"effective options are accepted from Cargo",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="rustc wrapper token"):
        require_activation_source_contract(sources)


@pytest.mark.parametrize(
    "token",
    [
        b"cpp_scientific_projection",
        b"rust_scientific_projection",
        b"cpp_lane_metrics",
        b"rust_lane_metrics",
    ],
)
def test_full_backend_evidence_is_retained_by_measurement_core(token: bytes) -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.QUALIFICATION_SOURCE_RELATIVE_PATH.as_posix()
    assert token in sources[key]
    sources[key] = sources[key].replace(token, b"removed_evidence_field")
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="lane-metrics token"):
        require_activation_source_contract(sources)


@pytest.mark.parametrize(
    "token",
    [
        b"backend_rederivable_evidence_json",
        b"decision_preimage_json",
        b"numeric_projection_json",
        b"projection_digest_stream_json",
        b"scorer_validity_rows",
    ],
)
def test_persisted_backend_evidence_contract_is_static_bound(token: bytes) -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    assert token in sources[key]
    sources[key] = sources[key].replace(token, b"removed_evidence_token")
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="rederivable evidence"):
        require_activation_source_contract(sources)


def test_compile_time_activation_profile_and_commit_binding_is_required() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.BUILD_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"committed_blob(source_root, commit_oid, PROFILE_RELATIVE_PATH)",
        b"canonical_profile.clone()",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="compile-time source"):
        require_activation_source_contract(sources)


def test_compile_time_build_commit_tracks_git_head_and_ref_inputs() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.BUILD_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"track_git_commit_inputs(source_root)",
        b"trust_cached_git_commit_inputs(source_root)",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="compile-time source"):
        require_activation_source_contract(sources)


def test_non_authoritative_package_build_cannot_activate() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b'BUILD_COMMIT_BOUND != "true"',
        b'BUILD_COMMIT_BOUND == "invalid"',
        1,
    )
    with pytest.raises(
        NativeFixed64CPUProfileV7Error,
        match="non-authoritative package rejection",
    ):
        require_activation_source_contract(sources)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            b"native_lane_metrics_activation_frozen_execution_not_consumed",
            b"native_activation_implementation_frozen_execution_not_consumed",
        ),
        (
            b"fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928",
            b"f5b3a1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928",
        ),
        (b'COMPILED_SOURCE_COUNT != "196"', b'COMPILED_SOURCE_COUNT != "193"'),
        (
            b'manifest.matches("\\"source_count\\": 196").count() != 1',
            b'manifest.matches("\\"source_count\\": 193").count() != 1',
        ),
    ],
)
def test_activation_exact_identity_drift_fails_closed(old: bytes, new: bytes) -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    assert sources[key].count(old) == 1
    sources[key] = sources[key].replace(old, new, 1)
    with pytest.raises(
        NativeFixed64CPUProfileV7Error,
        match="activation exact identity token",
    ):
        require_activation_source_contract(sources)


def test_binary_cannot_accept_caller_supplied_probe_configuration() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.BINARY_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] += b"// Fixed64CpuProbeConfigV5\n"
    with pytest.raises(NativeFixed64CPUProfileV7Error, match="custom probe"):
        require_activation_source_contract(sources)
