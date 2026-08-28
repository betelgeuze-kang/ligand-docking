from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools import verify_engine_v2_pme_reciprocal_reference_v1 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST_PATH = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
WORKFLOW_PATH = (
    ROOT / ".github/workflows/ci-engine-v2-pme-reciprocal-reference.yml"
)


def test_historical_prerequisite_and_semantic_oracle_are_exact() -> None:
    observed = verifier.require_historical_dependencies(ROOT)
    assert observed == {
        "prerequisite_merge_commit": verifier.PREREQUISITE["merge_commit"],
        "prerequisite_current_file_count": 2,
        "prerequisite_source_manifest_entry_count": 113,
        "semantic_oracle_file_count": 6,
        "semantic_oracle_merge_commit": verifier.SEMANTIC_ORACLE["merge_commit"],
    }

    for relative, digest in verifier.SEMANTIC_ORACLE_CURRENT_PATHS.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    for relative, digest in verifier.PREREQUISITE_CURRENT_PATHS.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_invalid_historical_identity_fails_before_git_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def unexpected_git(*_args: object, **_kwargs: object) -> tuple[int, bytes]:
        nonlocal called
        called = True
        return 0, b""

    monkeypatch.setattr(verifier, "_git", unexpected_git)
    invalid = dict(verifier.PREREQUISITE)
    invalid["merge_commit"] = "not-an-object"
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="historical object identity is invalid",
    ):
        verifier._require_commit_pair(ROOT, invalid, label="invalid")
    assert called is False


def test_exact_profile_and_source_binding_verify() -> None:
    result = verifier.verify(ROOT)
    assert result["verified"] is True
    assert result["all_authority_false"] is True
    assert result["full_pme_implemented"] is False
    assert result["fixed64_cpu_v7_qualification_invoked"] is False
    assert result["hip_device_execution_invoked"] is False
    assert result["molecular_execution_invoked"] is False
    assert result["operational_blocker_count"] == 4
    assert result["unresolved_operational_decisions"] == 32
    assert result["profile_sha256"] == hashlib.sha256(
        PROFILE_PATH.read_bytes()
    ).hexdigest()
    assert result["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST_PATH.read_bytes()
    ).hexdigest()


def test_manifest_is_sorted_unique_complete_and_acyclic() -> None:
    raw = MANIFEST_PATH.read_bytes()
    manifest, sources = verifier.require_source_manifest(ROOT, raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    paths = [row["path"] for row in rows]
    assert paths == sorted(set(paths))
    assert paths == [path.as_posix() for path in verifier.discover_source_paths(ROOT)]
    assert set(paths) == set(sources)
    assert not (set(map(Path, paths)) & verifier.EXCLUDED_SOURCE_PATHS)
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in paths
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in paths
    assert "tools/verify_engine_v2_pme_reciprocal_reference_v1.py" in paths
    for required in verifier.REQUIRED_CRATE_PATHS:
        assert required.as_posix() in paths


def test_profile_is_canonical_reciprocal_only_and_authority_bounded() -> None:
    raw = PROFILE_PATH.read_bytes()
    assert raw == verifier.canonical_bytes(json.loads(raw))
    profile = json.loads(raw)
    assert profile["schema_id"] == verifier.SCHEMA_ID
    assert profile["profile_id"] == verifier.PROFILE_ID
    assert profile["roadmap_issue"] == 434
    assert profile["prerequisite"] == verifier.PREREQUISITE
    assert profile["semantic_oracle"] == verifier.SEMANTIC_ORACLE
    assert all(value is False for value in profile["authority"].values())
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY
    assert profile["numeric_envelope"] == verifier.NUMERIC_ENVELOPE
    assert profile["accuracy_acceptance"] == verifier.ACCURACY_ACCEPTANCE_CONTRACT
    assert profile["accuracy_observation"] == verifier.ACCURACY_OBSERVATION
    assert profile["numerical_contract"]["underflow_rescue"] == (
        verifier.UNDERFLOW_RESCUE_CONTRACT
    )
    assert profile["numerical_contract"]["underflow_rescue_regression"] == (
        verifier.UNDERFLOW_RESCUE_REGRESSION
    )

    implementation = profile["implementation"]
    assert implementation["particle_mesh_reciprocal_implemented"] is True
    assert implementation["full_pme_implemented"] is False
    assert implementation["real_space_implemented"] is False
    assert implementation["self_energy_implemented"] is False
    assert implementation["pair_correction_implemented"] is False
    assert implementation["performance_evidence_collected"] is False
    assert implementation["native_runtime_integrated"] is False
    assert implementation["hip_device_execution_invoked"] is False
    assert implementation["fixed64_cpu_v7_qualification_invoked"] is False
    assert implementation["work_cap_checked_before_assignment_or_grid_allocation"] is True
    assert implementation["post_influence_inverse_transform_count"] == 1
    assert implementation["production_complex_mesh_buffer_byte_upper_bound"] == 8388608
    assert implementation["production_complex_mesh_buffer_count_upper_bound"] == 1
    assert implementation["underflow_rescue_common_scale_power_of_two_exponent"] == 256
    assert (
        implementation["normal_and_rescued_force_modes_share_one_scaled_spectrum"]
        is True
    )
    assert (
        implementation[
            "underflow_rescue_combines_regular_and_rescued_energy_before_downscale"
        ]
        is True
    )
    assert profile["validation"][
        "raw_zero_damping_rescued_to_normal_nonzero_energy_and_force"
    ] is True
    assert profile["validation"][
        "underflow_rescue_fft_matches_independent_full_3d_direct_dft"
    ] is True
    assert profile["validation"][
        "underflow_rescue_force_matches_energy_central_finite_difference"
    ] is True
    assert profile["validation"][
        "underflow_rescue_half_grid_charge_potential_identity"
    ] is True
    assert profile["validation"][
        "power_of_two_scaled_common_spectrum_preserves_subnormal_force"
    ] is True
    assert profile["validation"][
        "rescue_only_scaled_energy_components_round_once_to_minimum_subnormal"
    ] is True
    assert profile["validation"][
        "mixed_regular_and_rescued_energy_lanes_round_once_to_minimum_subnormal"
    ] is True
    assert implementation["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST_PATH.read_bytes()
    ).hexdigest()


def test_fixture_has_the_exact_13_value_bit_closure() -> None:
    fixture = (ROOT / verifier.FIXTURE_RELATIVE_PATH).read_bytes()
    values = verifier._parse_fixture(fixture)
    assert tuple(values) == verifier.FIXTURE_VALUE_IDS
    assert len(values) == 13
    assert all(verifier.BITS_PATTERN.fullmatch(bits) for bits in values.values())
    profile = json.loads(PROFILE_PATH.read_text(encoding="ascii"))
    frozen = profile["frozen_observation"]
    assert frozen["energy_ieee754_bits_hex"] == values[
        "reciprocal_space_kcal_per_mol"
    ]
    assert frozen["frozen_energy_and_force_component_count"] == 13
    assert frozen["debug_release_bitwise_identical"] is True


def test_duplicate_nonfinite_and_noncanonical_json_fail_closed() -> None:
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="duplicate JSON key",
    ):
        verifier._load_canonical_object(b'{"a": 1, "a": 2}\n', label="test")
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="non-finite JSON constant",
    ):
        verifier._load_canonical_object(b'{"a": NaN}\n', label="test")
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="canonical serialization changed",
    ):
        verifier._load_canonical_object(b'{"a":1}\n', label="test")


def test_source_byte_path_and_contract_tampering_fail_closed() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="ascii"))
    digest_tampered = copy.deepcopy(manifest)
    digest_tampered["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(
            ROOT, verifier.canonical_bytes(digest_tampered)
        )

    path_tampered = copy.deepcopy(manifest)
    path_tampered["files"][0]["path"] = "../escape"
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="path is not normalized|path closure changed",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(path_tampered))

    _, sources = verifier.require_source_manifest(ROOT, MANIFEST_PATH.read_bytes())
    cargo_path = (verifier.CRATE_RELATIVE_PATH / "Cargo.toml").as_posix()
    cargo_tampered = dict(sources)
    cargo_tampered[cargo_path] = sources[cargo_path].replace(b"[workspace]", b"[package.metadata]")
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="standalone Cargo contract marker is missing",
    ):
        verifier._require_source_contract(cargo_tampered)

    library_path = (verifier.CRATE_RELATIVE_PATH / "src/lib.rs").as_posix()
    rescue_tampered = dict(sources)
    rescue_tampered[library_path] = sources[library_path].replace(
        b"fn mode_requires_log_rescue(", b"fn mode_requires_log_bypass("
    )
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="underflow/work-cap library marker is missing",
    ):
        verifier._require_source_contract(rescue_tampered)

    fixture_tampered = dict(sources)
    fixture_tampered[verifier.FIXTURE_RELATIVE_PATH.as_posix()] = sources[
        verifier.FIXTURE_RELATIVE_PATH.as_posix()
    ].replace(b"force_3_z", b"force_3_q")
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="exact ordered 13-value closure",
    ):
        verifier._require_source_contract(fixture_tampered)


def test_command_line_verifier_is_read_only_and_bounded() -> None:
    before = {
        PROFILE_PATH: PROFILE_PATH.read_bytes(),
        MANIFEST_PATH: MANIFEST_PATH.read_bytes(),
    }
    completed = subprocess.run(
        [
            "python3",
            "tools/verify_engine_v2_pme_reciprocal_reference_v1.py",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["verified"] is True
    assert result["full_pme_implemented"] is False
    assert result["all_authority_false"] is True
    assert {path: path.read_bytes() for path in before} == before


def test_ci_runs_only_safe_standalone_scalar_checks() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for required in (
        'CUDA_VISIBLE_DEVICES: ""',
        'HIP_VISIBLE_DEVICES: ""',
        'ROCR_VISIBLE_DEVICES: ""',
        "fetch-depth: 0",
        "persist-credentials: false",
        "--component clippy",
        "--component rustfmt",
        "cargo fmt --manifest-path rust/reference-pme/Cargo.toml",
        "cargo clippy --manifest-path rust/reference-pme/Cargo.toml",
        "cargo test --manifest-path rust/reference-pme/Cargo.toml",
        "cargo test --release --manifest-path rust/reference-pme/Cargo.toml",
        "--example profile_observation",
        '"debug_release_observation_sha256"',
        'test "$(wc -l < "$observation_dir/debug.txt")" -eq 31',
        "python3 tools/verify_engine_v2_pme_reciprocal_reference_v1.py",
        "tests/unit/test_engine_v2_pme_reciprocal_reference_v1.py",
        '"rust/reference-pme/**"',
        '"LICENSE"',
        '"rust/reference-ewald/src/lib.rs"',
        '"config/engine_v2_direct_ewald_reference_profile_v1.json"',
        '"config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json"',
        '"config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json"',
    ):
        assert required in workflow
    for forbidden in (
        "--refresh",
        "cargo bench",
        "cmake ",
        "ctest ",
        "hipcc",
        "rocminfo",
        "workflow_run:",
        "pull_request_target:",
        "verify_engine_v2_native_fixed64_cpu_profile_v7.py",
        "sudo ",
        "supervisor",
        "reservation",
    ):
        assert forbidden not in workflow


def test_refresh_rolls_back_both_files_after_post_write_failure(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")

    def fail_verification() -> dict[str, object]:
        assert manifest.read_bytes() == b"new manifest\n"
        assert profile.read_bytes() == b"new profile\n"
        raise verifier.PmeReciprocalReferenceV1Error("injected verification failure")

    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="injected verification failure",
    ):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            fail_verification,
        )
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "manifest.json",
        "profile.json",
    ]


def test_refresh_rolls_back_a_partial_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")
    real_replace = verifier.os.replace

    def fail_new_profile(source: Path, destination: Path) -> None:
        if destination == profile and Path(source).read_bytes() == b"new profile\n":
            raise OSError("injected second commit failure")
        real_replace(source, destination)

    monkeypatch.setattr(verifier.os, "replace", fail_new_profile)
    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="original evidence restored",
    ):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"


def test_refresh_rolls_back_on_base_exception(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")

    class InjectedBaseException(BaseException):
        pass

    def interrupt() -> dict[str, object]:
        raise InjectedBaseException("injected interruption")

    with pytest.raises(InjectedBaseException):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            interrupt,
        )
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"


def test_refresh_rejects_symlinked_evidence_ancestor(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "config").symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        verifier.PmeReciprocalReferenceV1Error,
        match="symlinked or non-directory ancestor",
    ):
        verifier._replace_evidence_transactionally(
            root,
            (
                (Path("config/manifest.json"), b"new manifest\n"),
                (Path("config/profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )
    assert list(outside.iterdir()) == []


def test_temporary_cleanup_is_best_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.tmp"
    second = tmp_path / "second.tmp"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    real_unlink = Path.unlink

    def fail_first(path: Path, *, missing_ok: bool = False) -> None:
        if path == first:
            raise OSError("injected cleanup failure")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_first)
    errors = verifier._cleanup_evidence_temporaries((first, second))
    assert len(errors) == 1
    assert "injected cleanup failure" in errors[0]
    assert first.exists()
    assert not second.exists()
