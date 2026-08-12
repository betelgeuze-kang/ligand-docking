from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
import zipfile

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

from tools.build_engine_v2_native_wheel import NATIVE_VERSION, _verify_wheel
from tools.build_engine_v2_native_wheel import (
    CPU_PROFILE_ID,
    FROZEN_TARGET,
    HIP_GFX1030_PROFILE_ID,
    FrozenFileSpec,
    FrozenNativeToolchain,
    FrozenRustToolchain,
    _directory_closure_sha256,
    _frozen_build_environment,
    _isolated_cargo_target_directory,
    _maturin_build_command,
    _reject_direct_build_overrides,
    _verify_cargo_configs,
    _verify_frozen_files,
    _verify_manifest_profile,
    build_native_wheel,
)


def test_native_release_version_surfaces_match_rc6() -> None:
    cargo = tomllib.loads(Path("rust_engine_v2/Cargo.toml").read_text(encoding="utf-8"))
    native = tomllib.loads(
        Path("rust_engine_v2/pyproject.toml").read_text(encoding="utf-8")
    )
    workflow = Path(
        ".github/workflows/ci-engine-v2-release-candidate.yml"
    ).read_text(encoding="utf-8")

    assert NATIVE_VERSION == "0.2.0rc6"
    assert cargo["package"]["version"] == "0.2.0-rc.6"
    assert native["project"]["version"] == NATIVE_VERSION
    assert "betelgeuze-engine-v2-native-0.2.0rc6.spdx.json" in workflow
    assert "engine-v2-native-0.2.0rc6-${{ github.run_id }}" in workflow
    assert '-v "$PWD:/io:ro" -w /io' in workflow
    assert '-v "$PWD/$output:/output"' in workflow
    assert "--output-dir /output" in workflow
    assert "git diff --exit-code" in workflow


@pytest.mark.parametrize(
    "name",
    (
        "RUSTFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "RUSTC",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTUP_TOOLCHAIN",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_BUILD_TARGET",
        "CARGO_PROFILE_RELEASE_LTO",
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER",
        "CARGO_UNSTABLE_BUILD_STD",
        "BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256",
        "BETELGEUZE_EXPECTED_NATIVE_BUILD_PROFILE_ID",
        "BETELGEUZE_EXPECTED_NATIVE_CARGO_FEATURES",
        "BETELGEUZE_EXPECTED_NATIVE_TOOLCHAIN_SHA256",
        "BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256",
        "BETELGEUZE_HIP_SAFE",
        "BG_HIP_DEVICE_LIB_PATH",
        "ROCM_PATH",
        "CC",
        "CFLAGS",
        "HOST_CC",
        "PYO3_PYTHON",
        "TARGET_X86_64_UNKNOWN_LINUX_GNU_LDFLAGS",
        "CXXFLAGS_x86_64_unknown_linux_gnu",
        "HIPCC_COMPILE_FLAGS_APPEND",
    ),
)
def test_native_build_rejects_caller_build_overrides(name: str) -> None:
    with pytest.raises(RuntimeError, match=name):
        _reject_direct_build_overrides({name: "attacker-controlled"})


def test_native_build_public_entrypoint_rejects_override_before_output_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "must-not-be-created"
    monkeypatch.setenv("RUSTFLAGS", "-Ctarget-cpu=native")

    with pytest.raises(RuntimeError, match="RUSTFLAGS"):
        build_native_wheel(Path.cwd(), output)

    assert not output.exists()


def test_native_build_preserves_cache_locations_and_sets_frozen_controls(
    tmp_path: Path,
) -> None:
    cargo = tmp_path / "toolchain/bin/cargo"
    rustc = tmp_path / "toolchain/bin/rustc"
    toolchain = FrozenRustToolchain(
        rustc_executable=rustc,
        rustc_executable_sha256="a" * 64,
        rustc_verbose_sha256="b" * 64,
        cargo_executable=cargo,
    )
    native_toolchain = FrozenNativeToolchain(
        profile_id=CPU_PROFILE_ID,
        compatibility="manylinux_2_28",
        cc=tmp_path / "native/bin/gcc",
        cxx=tmp_path / "native/bin/g++",
        ar=tmp_path / "native/bin/ar",
        ranlib=tmp_path / "native/bin/ranlib",
        ld=tmp_path / "native/bin/ld",
        linker=tmp_path / "native/bin/gcc",
        assembler=tmp_path / "native/bin/as",
        strip=tmp_path / "native/bin/strip",
        path_entries=(tmp_path / "native/bin", Path("/usr/bin")),
        cargo_features=("extension-module",),
        toolchain_sha256="c" * 64,
    )
    cargo_home = tmp_path / "cargo-home"
    target_dir = tmp_path / "cargo-target"

    environment = _frozen_build_environment(
        {
            "CARGO_HOME": str(cargo_home),
            "CARGO_TARGET_DIR": str(target_dir),
            "LD_LIBRARY_PATH": "/untrusted/runtime/linker/path",
            "PYTHONPATH": "/untrusted/python/module/path",
            "RUSTFLAGS": "",
        },
        toolchain,
        native_toolchain,
    )

    assert environment["CARGO_HOME"] == str(cargo_home)
    assert environment["CARGO_TARGET_DIR"] == str(target_dir)
    assert "LD_LIBRARY_PATH" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["CARGO_BUILD_TARGET"] == FROZEN_TARGET
    assert environment["RUSTC"] == str(rustc)
    assert environment["CARGO"] == str(cargo)
    assert environment["PYO3_PYTHON"] == str(Path(sys.executable).resolve())
    assert environment["CC"] == str(native_toolchain.cc)
    assert environment["CXX"] == str(native_toolchain.cxx)
    assert environment["AR"] == str(native_toolchain.ar)
    assert environment["RANLIB"] == str(native_toolchain.ranlib)
    assert environment["LD"] == str(native_toolchain.ld)
    assert environment["CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER"] == str(
        native_toolchain.linker
    )
    assert environment["BETELGEUZE_EXPECTED_NATIVE_BUILD_PROFILE_ID"] == (
        CPU_PROFILE_ID
    )
    assert environment["BETELGEUZE_EXPECTED_NATIVE_CARGO_FEATURES"] == (
        "extension-module"
    )
    assert environment["BETELGEUZE_EXPECTED_NATIVE_TOOLCHAIN_SHA256"] == "c" * 64
    assert environment["RUSTFLAGS"] == ""
    assert environment["CARGO_ENCODED_RUSTFLAGS"] == ""
    assert environment["RUSTC_WRAPPER"] == ""
    assert environment["CARGO_PROFILE_RELEASE_LTO"] == "fat"
    assert environment["CARGO_PROFILE_RELEASE_CODEGEN_UNITS"] == "1"
    assert environment["CARGO_PROFILE_RELEASE_DEBUG"] == "0"
    assert environment["CARGO_PROFILE_RELEASE_INCREMENTAL"] == "false"
    assert environment["CARGO_PROFILE_RELEASE_PANIC"] == "abort"
    wrapper = Path("tools/build_engine_v2_native_wheel.py")
    assert environment["BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256"] == (
        hashlib.sha256(wrapper.read_bytes()).hexdigest()
    )


def test_canonical_maturin_profiles_select_exact_features(tmp_path: Path) -> None:
    common = {
        "manifest": Path("rust_engine_v2/Cargo.toml"),
        "output_dir": tmp_path,
    }
    cpu = FrozenNativeToolchain(
        profile_id=CPU_PROFILE_ID,
        compatibility="manylinux_2_28",
        cc=Path("/tools/gcc"),
        cxx=Path("/tools/g++"),
        ar=Path("/tools/ar"),
        ranlib=Path("/tools/ranlib"),
        ld=Path("/tools/ld"),
        linker=Path("/tools/gcc"),
        assembler=Path("/tools/as"),
        strip=Path("/tools/strip"),
        path_entries=(Path("/tools"),),
        cargo_features=("extension-module",),
        toolchain_sha256="a" * 64,
    )
    hip = FrozenNativeToolchain(
        **{
            **cpu.__dict__,
            "profile_id": HIP_GFX1030_PROFILE_ID,
            "compatibility": "linux",
            "cargo_features": ("extension-module", "hip"),
        }
    )

    cpu_command = _maturin_build_command(
        **common,
        compatibility="manylinux_2_28",
        native_toolchain=cpu,
    )
    hip_command = _maturin_build_command(
        **common,
        compatibility="linux",
        native_toolchain=hip,
    )

    assert "--no-default-features" in cpu_command
    assert cpu_command[cpu_command.index("--features") + 1] == "extension-module"
    assert hip_command[hip_command.index("--features") + 1] == (
        "extension-module,hip"
    )


def test_native_toolchain_directory_closure_is_content_bound(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/a.h").write_text("first", encoding="utf-8")
    first = _directory_closure_sha256(tmp_path, b"test-domain")
    (tmp_path / "nested/a.h").write_text("second", encoding="utf-8")
    second = _directory_closure_sha256(tmp_path, b"test-domain")

    assert first[1] == second[1] == 1
    assert first[0] != second[0]


def test_native_toolchain_executable_digest_is_fail_closed(tmp_path: Path) -> None:
    executable = tmp_path / "compiler"
    executable.write_bytes(b"frozen compiler")
    executable.chmod(0o700)
    specification = FrozenFileSpec(
        label="compiler",
        path=executable,
        resolved_path=executable,
        sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
    )

    _verify_frozen_files((specification,))
    executable.write_bytes(b"mutated compiler")

    with pytest.raises(RuntimeError, match="digest changed"):
        _verify_frozen_files((specification,))


def test_native_toolchain_executable_path_is_fail_closed(tmp_path: Path) -> None:
    executable = tmp_path / "compiler"
    executable.write_bytes(b"frozen compiler")
    executable.chmod(0o700)
    specification = FrozenFileSpec(
        label="compiler",
        path=executable,
        resolved_path=tmp_path / "different-compiler",
        sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
    )

    with pytest.raises(RuntimeError, match="path changed"):
        _verify_frozen_files((specification,))


def test_native_build_uses_configured_empty_target_directory(tmp_path: Path) -> None:
    target = tmp_path / "configured-target"

    with _isolated_cargo_target_directory(
        {"CARGO_TARGET_DIR": str(target)}
    ) as observed:
        assert observed == target
        assert observed.is_dir()

    assert target.is_dir()


def test_native_build_rejects_prepopulated_target_directory(tmp_path: Path) -> None:
    target = tmp_path / "prepopulated-target"
    target.mkdir()
    (target / "untrusted-fingerprint").write_text("poison", encoding="utf-8")

    with pytest.raises(RuntimeError, match="must be an empty directory"):
        with _isolated_cargo_target_directory({"CARGO_TARGET_DIR": str(target)}):
            raise AssertionError("unreachable")


def test_native_build_owns_fresh_target_directory_when_not_configured() -> None:
    with _isolated_cargo_target_directory({}) as target:
        observed = target
        assert observed.is_dir()
        assert not tuple(observed.iterdir())

    assert not observed.exists()


@pytest.mark.parametrize(
    ("config_text", "expected_key"),
    (
        ("[build]\nrustflags = ['-Ctarget-cpu=native']\n", "build.rustflags"),
        ("[build]\ntarget = 'wasm32-unknown-unknown'\n", "build.target"),
        (
            "[target.x86_64-unknown-linux-gnu]\nlinker = '/tmp/linker'\n",
            "target.x86_64-unknown-linux-gnu.linker",
        ),
        ("[profile.release]\nlto = false\n", "profile"),
        ("[env]\nRUSTC_WRAPPER = '/tmp/wrapper'\n", "env.RUSTC_WRAPPER"),
        ("[env]\nLD_LIBRARY_PATH = '/tmp/lib'\n", "env.LD_LIBRARY_PATH"),
        ("[env]\nPATH = '/tmp/bin'\n", "env.PATH"),
        ("[unstable]\nbuild-std = ['std']\n", "unstable.build-std"),
        ("include = ['unreviewed-config.toml']\n", "include"),
        ("paths = ['../unreviewed-crate']\n", "paths"),
    ),
)
def test_native_build_rejects_build_affecting_cargo_config(
    tmp_path: Path, config_text: str, expected_key: str
) -> None:
    repository = tmp_path / "repo"
    cargo_directory = repository / ".cargo"
    cargo_directory.mkdir(parents=True)
    (cargo_directory / "config.toml").write_text(config_text, encoding="utf-8")

    with pytest.raises(RuntimeError, match=re.escape(expected_key)):
        _verify_cargo_configs(
            repository,
            {"CARGO_HOME": str(tmp_path / "isolated-cargo-home")},
        )


def test_native_build_allows_non_build_cargo_transport_config(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    cargo_directory = repository / ".cargo"
    cargo_directory.mkdir(parents=True)
    (cargo_directory / "config.toml").write_text(
        "[net]\nretry = 2\n[http]\ntimeout = 30\n",
        encoding="utf-8",
    )

    _verify_cargo_configs(
        repository,
        {"CARGO_HOME": str(tmp_path / "isolated-cargo-home")},
    )


def test_native_manifest_release_profile_is_exactly_frozen() -> None:
    _verify_manifest_profile(Path("rust_engine_v2/Cargo.toml"))


def test_docking_search_pins_portable_pure_rust_transcendentals() -> None:
    manifest = tomllib.loads(
        Path("rust/betelgeuze-docking-search/Cargo.toml").read_text(encoding="utf-8")
    )
    assert manifest["dependencies"]["libm"] == {
        "version": "=0.2.16",
        "default-features": False,
    }

    platform_math = re.compile(
        r"\.(?:sin|cos|sqrt|hypot|atan2|acos|asin|tan|exp|ln|powf)\("
    )
    for source_path in sorted(
        Path("rust/betelgeuze-docking-search/src").glob("*.rs")
    ):
        production_source = source_path.read_text(encoding="utf-8").split(
            "#[cfg(test)]", 1
        )[0]
        assert platform_math.search(production_source) is None, source_path


def test_native_wheel_member_guard_accepts_only_separate_extension(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-"
        "manylinux_2_28_x86_64.whl"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so", b"x"
        )
        archive.writestr(
            "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/METADATA",
            "Name: betelgeuze-engine-v2-native\nVersion: 0.2.0rc6\n",
        )

    _verify_wheel(wheel)


def test_native_wheel_member_guard_rejects_bundled_python_package(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-"
        "manylinux_2_28_x86_64.whl"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so", b"x"
        )
        archive.writestr("betelgeuze_engine_v2/__init__.py", b"")
        archive.writestr(
            "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/METADATA",
            "Name: betelgeuze-engine-v2-native\nVersion: 0.2.0rc6\n",
        )

    with pytest.raises(RuntimeError, match="must not bundle"):
        _verify_wheel(wheel)


def test_native_wheel_platform_tag_must_match_requested_compatibility(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-linux_x86_64.whl"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so", b"x"
        )
        archive.writestr(
            "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/METADATA",
            "Name: betelgeuze-engine-v2-native\nVersion: 0.2.0rc6\n",
        )

    _verify_wheel(wheel, compatibility="linux")
    with pytest.raises(RuntimeError, match="platform tag"):
        _verify_wheel(wheel, compatibility="manylinux_2_28")
