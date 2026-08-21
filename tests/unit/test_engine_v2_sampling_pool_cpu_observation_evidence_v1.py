from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from tools import capture_engine_v2_sampling_pool_cpu_observation_v1 as evidence


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "config/engine_v2_sampling_pool_cpu_observation_evidence_v1.json"


def _reseal(value: dict[str, object]) -> dict[str, object]:
    projection = copy.deepcopy(value)
    projection.pop("receipt_sha256", None)
    return {
        **projection,
        "receipt_sha256": evidence._receipt_sha256(projection),
    }


def test_committed_source_binary_host_bound_observation_verifies() -> None:
    value = evidence.load_and_verify(EVIDENCE)
    assert value["receipt_sha256"] == (
        "42b5d76c870c17ef49528319d6209a587b5ef40ef6be63c12c166d776da9e394"
    )
    assert value["source"]["merged_main_commit"] == evidence.SOURCE_BASELINE_COMMIT
    assert value["source"]["merged_main_tree"] == evidence.SOURCE_BASELINE_TREE
    assert value["observation"]["sample_count"] == evidence.SAMPLE_COUNT
    assert all(item is False for item in value["authority"].values())


def test_resealed_semantic_cross_wiring_fails_closed() -> None:
    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["wall_time_ns_samples"][0] = 0
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="timing or memory",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    del value["authority"]["reservation_authorized"]
    value["observation"]["authority"] = copy.deepcopy(value["authority"])
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="authority",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["source"]["closure_verified_clean"] = 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="clean-closure marker",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["sample_count"] = float(value["observation"]["sample_count"])
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="not integers",
    ):
        evidence.verify(_reseal(value))

    for key in (
        "ligand_atom_count",
        "exact_pair_evaluation_count",
        "wall_time_ns_p50",
    ):
        value = json.loads(EVIDENCE.read_text(encoding="ascii"))
        row = value["observation"]["fixtures"][0]
        row[key] = float(row[key])
        with pytest.raises(
            evidence.SamplingPoolCPUObservationEvidenceError,
            match="not integers",
        ):
            evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["host"]["logical_cpu_count"] = 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="host identity",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["captured_at_utc"] = "2026-W34-4T23:21:26Z"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="capture timestamp",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["lookup_roots"][0]["root_path_sha256"] = (
        "0" * 64
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="not component-bound",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["lookup_roots"][0]["candidate_files"][
        "config.toml"
    ]["candidate_path_sha256"] = "0" * 64
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="not root-bound",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    row = value["observation"]["fixtures"][0]
    row["peak_rss_kib"] = evidence._U64_MAX + 1
    row["peak_rss_delta_kib"] = evidence._U64_MAX + 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="producer integer width",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["cargo_home_origin"] = "environment"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="differs from its environment fingerprint",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["observer_binary_bytes"] = evidence._I64_MAX + 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="observer_binary_bytes is invalid",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["registry_dependencies"][0]["source_tree_sha256"] = "0" * 64
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="registry dependency source binding",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["source"]["unreviewed_source"] = "0" * 64
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="source binding keys",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["performance_claim_authorized"] = True
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="observation keys",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["unreviewed_metric"] = 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="fixture keys",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["peak_rss_delta_kib"] = (
        value["observation"]["fixtures"][0]["peak_rss_kib"] + 1
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="delta exceeds",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["build_environment"]["RUSTFLAGS"] = {
        "set": True,
        "value_sha256": int("1" * 64),
    }
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="build environment metadata",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["host"]["system"] = "OtherOS"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="host identity",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    first_cpu = next(iter(value["host"]["affinity_cpu_models"]))
    value["host"]["affinity_cpu_models"][first_cpu] = []
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="host identity",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["runtime_environment"]["LD_PRELOAD"] = "/tmp/inject.so"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="runtime environment",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["lookup_roots"][0]["candidate_files"][
        "config.toml"
    ]["candidate_path_sha256"] = "not-a-digest"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="lowercase SHA-256",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["lookup_roots"] = [
        value["build"]["cargo_configuration"]["lookup_roots"][-1]
    ]
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="Cargo configuration binding",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["cargo_configuration"]["cargo_home_origin"] = []
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="Cargo configuration binding",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["fixture_id"] = []
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="fixture ID",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["authority"]["reservation_authorized"] = 0
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="authority",
    ):
        evidence.verify(_reseal(value))


def test_capture_is_blocked_in_github_actions_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        evidence.observer,
        "_build_library",
        lambda: (_ for _ in ()).throw(AssertionError("build must not run")),
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="cannot capture timing",
    ):
        evidence.capture()


def test_evidence_write_is_exclusive(tmp_path: Path) -> None:
    destination = tmp_path / "evidence.json"
    evidence._write_exclusive(destination, b"{}\n")
    assert destination.read_bytes() == b"{}\n"
    with pytest.raises(FileExistsError):
        evidence._write_exclusive(destination, b"changed\n")

    dangling_target = tmp_path / "dangling-target.json"
    dangling_link = tmp_path / "dangling-link.json"
    dangling_link.symlink_to(dangling_target)
    with pytest.raises(FileExistsError):
        evidence._write_exclusive(dangling_link, b"redirected\n")
    assert not dangling_target.exists()


def test_affinity_and_imported_runner_binding_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="affinity changed",
    ):
        evidence._require_stable_affinity([0, 1], [0])

    replacement = tmp_path / "run_engine_v2_sampling_pool_cpu_observation_v1.py"
    replacement.write_text("# changed\n", encoding="ascii")
    monkeypatch.setattr(evidence.observer, "__file__", str(replacement))
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="imported observation runner differs",
    ):
        evidence._verify_imported_observer_binding()


def test_cli_runner_binding_failure_is_stable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(evidence, "observer", None)
    monkeypatch.setattr(
        evidence,
        "_load_observer",
        lambda: (_ for _ in ()).throw(
            evidence.SamplingPoolCPUObservationEvidenceError("runner unavailable")
        ),
    )
    assert evidence.main(["--verify", str(EVIDENCE)]) == 1
    assert capsys.readouterr().out == (
        "sampling_pool_cpu_observation_evidence=blocked:runner unavailable\n"
    )


def test_cli_overflowing_json_number_is_stably_blocked(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    overflowing = tmp_path / "overflowing.json"
    overflowing.write_text('{"value":1e400}\n', encoding="ascii")
    assert evidence.main(["--verify", str(overflowing)]) == 1
    assert capsys.readouterr().out == (
        "sampling_pool_cpu_observation_evidence=blocked:"
        "non-finite JSON number is forbidden\n"
    )

    oversized = tmp_path / "oversized-integer.json"
    oversized.write_text('{"value":' + "1" * 5000 + "}\n", encoding="ascii")
    assert evidence.main(["--verify", str(oversized)]) == 1
    assert capsys.readouterr().out == (
        "sampling_pool_cpu_observation_evidence=blocked:"
        "JSON integer exceeds the evidence digit limit\n"
    )

    nested = tmp_path / "excessively-nested.json"
    nested.write_text("[" * 60_000 + "]" * 60_000 + "\n", encoding="ascii")
    assert evidence.main(["--verify", str(nested)]) == 1
    assert capsys.readouterr().out == (
        "sampling_pool_cpu_observation_evidence=blocked:evidence is not strict JSON\n"
    )


def test_source_git_ignores_ambient_repository_redirection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other-git-dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "other-work-tree"))
    assert Path(evidence._git("rev-parse", "--show-toplevel")) == ROOT
    assert evidence._baseline_file_sha256("rust/Cargo.lock") == evidence._sha256(
        evidence._git_bytes(
            "show", f"{evidence.SOURCE_BASELINE_COMMIT}:rust/Cargo.lock"
        )
    )
    evidence._verify_actual_source_bytes()


def test_fresh_target_and_toolchain_helpers_fail_closed(tmp_path: Path) -> None:
    environment = evidence._build_subprocess_environment()
    occupied_target = tmp_path / "occupied-target"
    occupied_target.mkdir()
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="already exists",
    ):
        evidence._build_release_library_fresh(occupied_target, environment)
    toolchain = evidence._toolchain_identity(environment)
    assert set(toolchain) == {
        "cargo_executable_sha256",
        "cargo_version",
        "rustc_executable_sha256",
        "rustc_sysroot_sha256",
        "rustc_version",
    }
    assert all(value for value in toolchain.values())


def test_registry_sources_and_home_resolution_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cargo_home, _ = evidence._effective_cargo_home()
    assert evidence._verify_registry_dependency_sources(cargo_home) == list(
        evidence._REGISTRY_DEPENDENCIES
    )

    monkeypatch.delenv("CARGO_HOME", raising=False)
    monkeypatch.setattr(
        evidence.Path,
        "home",
        lambda: (_ for _ in ()).throw(RuntimeError("home unavailable")),
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="Cargo home cannot be resolved",
    ):
        evidence._effective_cargo_home()


def test_effective_affinity_cpu_models_are_complete_and_homogeneous() -> None:
    cpuinfo = """\
processor : 0
model name : Example CPU A

processor : 1
model name : Example CPU A
"""
    assert evidence._affinity_cpu_models_from(cpuinfo, [0, 1]) == {
        "0": "Example CPU A",
        "1": "Example CPU A",
    }
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="unavailable for effective affinity",
    ):
        evidence._affinity_cpu_models_from(cpuinfo, [0, 2])

    machine_wide = """\
processor : 0
hart : 0

processor : 1
hart : 1

Hardware : Example Machine CPU
"""
    assert evidence._affinity_cpu_models_from(machine_wide, [0, 1]) == {
        "0": "Example Machine CPU",
        "1": "Example Machine CPU",
    }


def test_cargo_configuration_and_timed_environment_are_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rust_root = tmp_path / "repository" / "rust"
    rust_config = rust_root / ".cargo" / "config.toml"
    rust_config.parent.mkdir(parents=True)
    rust_config.write_text(
        "[build]\nrustflags = ['-Ctarget-cpu=native']\n", encoding="ascii"
    )
    cargo_home = tmp_path / "cargo-home"
    cargo_home.mkdir()
    cargo_config = cargo_home / "config"
    cargo_config.write_text("[net]\noffline = true\n", encoding="ascii")
    monkeypatch.setattr(evidence.observer, "RUST_ROOT", rust_root)
    monkeypatch.setenv("CARGO_HOME", str(cargo_home))

    assert evidence._cargo_configuration_file(rust_config)["content_sha256"] == (
        evidence._sha256(rust_config.read_bytes())
    )
    assert evidence._cargo_configuration_file(cargo_config)["content_sha256"] == (
        evidence._sha256(cargo_config.read_bytes())
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="overrides are forbidden",
    ):
        evidence._cargo_configuration_binding()
    rust_config.unlink()
    cargo_config.unlink()

    binding = evidence._cargo_configuration_binding()
    evidence._verify_cargo_configuration(binding)
    assert binding["cargo_home_origin"] == "environment"
    roots = binding["lookup_roots"]
    assert roots[-1]["scope"] == "cargo_home"
    environment = evidence._build_subprocess_environment()
    fingerprints = evidence._environment_fingerprints(
        environment, cargo_home=cargo_home
    )
    assert fingerprints["CARGO_HOME"]["value_sha256"] == (roots[-1]["root_path_sha256"])

    incomplete = copy.deepcopy(binding)
    del incomplete["lookup_roots"][1]
    for index, root in enumerate(incomplete["lookup_roots"][:-1]):
        root["scope"] = f"working_directory_ancestor_{index}"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="ancestor chain is incomplete",
    ):
        evidence._verify_cargo_configuration(incomplete)

    monkeypatch.setattr(evidence.observer, "RUST_ROOT", Path("/tmp/rust"))
    shallow_binding = evidence._cargo_configuration_binding()
    assert len(shallow_binding["lookup_roots"]) == 4
    evidence._verify_cargo_configuration(shallow_binding)

    monkeypatch.setenv(
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS", "-Ctarget-cpu=native"
    )
    monkeypatch.setenv("RUSTC", "/tmp/untrusted-rustc")
    sanitized = evidence._build_subprocess_environment()
    assert "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS" not in sanitized
    assert "RUSTC" not in sanitized
    raw_surrogate = os.fsdecode(b"\xff")
    raw_fingerprints = evidence._environment_fingerprints(
        {"RUSTFLAGS": raw_surrogate}, cargo_home=cargo_home
    )
    assert raw_fingerprints["RUSTFLAGS"]["value_sha256"] == evidence._sha256(b"\xff")

    monkeypatch.setenv("LD_PRELOAD", "/tmp/inject.so")
    runtime = evidence._timed_runtime_environment()
    assert runtime == evidence._TIMED_RUNTIME_ENVIRONMENT
    assert "LD_PRELOAD" not in runtime
