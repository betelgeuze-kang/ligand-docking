from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_native_fixed64_cpu_profile_v6 as verifier
from tools.verify_engine_v2_native_fixed64_cpu_profile_v6 import (
    NativeFixed64CPUProfileV6Error,
    require_activation_source_contract,
    require_bound_source_tree,
    require_packaged_activation_assets,
    require_profile_document_v6,
    require_source_manifest_document,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / verifier.PROFILE_RELATIVE_PATH
_MANIFEST = _ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
_V5_PROFILE = _ROOT / verifier.V5_PROFILE_RELATIVE_PATH
_V5_ARCHIVE = _ROOT / verifier.V5_ARCHIVE_RELATIVE_PATH
_TOOL = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py"


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
    v5_profile_raw = _V5_PROFILE.read_bytes()
    v5_archive_raw = _V5_ARCHIVE.read_bytes()
    manifest = require_source_manifest_document(manifest_raw)
    sources = require_bound_source_tree(_ROOT, manifest)
    return profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources


def test_profile_v6_rederives_from_archived_v5_and_exact_sources() -> None:
    profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources = (
        _real_evidence()
    )
    profile = require_profile_document_v6(
        profile_raw,
        v5_profile_raw,
        v5_archive_raw,
        manifest_raw,
        sources,
    )
    require_activation_source_contract(sources)
    require_packaged_activation_assets(
        _ROOT,
        profile_raw=profile_raw,
        v5_archive_raw=v5_archive_raw,
        source_manifest_raw=manifest_raw,
        cargo_lock_raw=sources[verifier.CARGO_LOCK_RELATIVE_PATH.as_posix()],
        cargo_manifest_raw=sources[
            verifier.CARGO_MANIFEST_RELATIVE_PATH.as_posix()
        ],
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
        verifier.PACKAGED_V5_ARCHIVE_RELATIVE_PATH: _V5_ARCHIVE.read_bytes(),
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
        NativeFixed64CPUProfileV6Error,
        match="packaged v6 activation asset drifted",
    ):
        require_packaged_activation_assets(
            tmp_path,
            profile_raw=_PROFILE.read_bytes(),
            v5_archive_raw=_V5_ARCHIVE.read_bytes(),
            source_manifest_raw=_MANIFEST.read_bytes(),
            cargo_lock_raw=(
                _ROOT / verifier.CARGO_LOCK_RELATIVE_PATH
            ).read_bytes(),
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
    assert payload["non_consuming_preflight_only"] is True
    assert payload["all_authority_false"] is True
    assert payload["source_count"] == 192


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
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="duplicate JSON key"):
        require_profile_document_v6(
            raw,
            _V5_PROFILE.read_bytes(),
            _V5_ARCHIVE.read_bytes(),
            _MANIFEST.read_bytes(),
            {},
        )


def test_scientific_gate_drift_fails_even_with_rebound_profile_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    profile["gates"]["candidate_denominator_exact"] = 65
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="scientific gates"):
        require_profile_document_v6(
            mutated,
            v5_profile_raw,
            v5_archive_raw,
            manifest_raw,
            sources,
        )


def test_scorer_and_validity_rederivation_gate_removal_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    del profile["gates"]["scorer_v1_terms_rederivable_required"]
    del profile["gates"]["validity_measurements_rederivable_required"]
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="scientific gates"):
        require_profile_document_v6(
            mutated,
            v5_profile_raw,
            v5_archive_raw,
            manifest_raw,
            sources,
        )


def test_authority_enablement_fails_even_with_rebound_profile_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources = (
        _real_evidence()
    )
    profile = json.loads(profile_raw)
    profile["authority"]["qualification_authority"] = True
    mutated = _canonical(profile)
    monkeypatch.setattr(verifier, "PROFILE_SHA256", hashlib.sha256(mutated).hexdigest())
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="authority"):
        require_profile_document_v6(
            mutated,
            v5_profile_raw,
            v5_archive_raw,
            manifest_raw,
            sources,
        )


def test_manifest_source_byte_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads(_MANIFEST.read_bytes())
    row = next(
        value
        for value in manifest["files"]
        if value["path"] == verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    )
    row["sha256"] = "00" * 32
    mutated = _canonical(manifest)
    monkeypatch.setattr(
        verifier, "SOURCE_MANIFEST_SHA256", hashlib.sha256(mutated).hexdigest()
    )
    parsed = require_source_manifest_document(mutated)
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="bound transitive source"):
        require_bound_source_tree(_ROOT, parsed)


def test_profile_source_cross_wiring_fails_closed() -> None:
    profile_raw, manifest_raw, v5_profile_raw, v5_archive_raw, sources = (
        _real_evidence()
    )
    sources = dict(sources)
    sources[verifier.BINARY_SOURCE_RELATIVE_PATH.as_posix()] += b"\n"
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="source bindings"):
        require_profile_document_v6(
            profile_raw,
            v5_profile_raw,
            v5_archive_raw,
            manifest_raw,
            sources,
        )


def test_attempt_before_preflight_order_is_static_authority_boundary() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.RUNNER_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] = sources[key].replace(
        b"preflight_native_fixed64_cpu_v6()?;",
        b"preflight_native_fixed64_cpu_v6_unsealed()?;",
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="ordering token"):
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
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="compile-time source"):
        require_activation_source_contract(sources)


def test_binary_cannot_accept_caller_supplied_probe_configuration() -> None:
    _, _, _, _, sources = _real_evidence()
    sources = dict(sources)
    key = verifier.BINARY_SOURCE_RELATIVE_PATH.as_posix()
    sources[key] += b"// Fixed64CpuProbeConfigV5\n"
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="custom probe"):
        require_activation_source_contract(sources)
