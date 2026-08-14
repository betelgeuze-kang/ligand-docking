from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
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
    _CPU_GCC_CLOSURE,
    _GCC_LINK_INPUT_NAMES,
    _GCC_PROGRAM_NAMES,
    _HIP_GCC_CLOSURE,
    _HIP_PERL_CLOSURE,
    _ROCM_FILE_SPECS,
    FrozenFileSpec,
    FrozenNativeToolchain,
    FrozenPerlClosureSpec,
    FrozenRustToolchain,
    _directory_closure_sha256,
    _filesystem_tree_closure_sha256,
    _frozen_build_environment,
    _isolated_cargo_target_directory,
    _maturin_build_command,
    _reject_direct_build_overrides,
    _perl_runtime_closure_receipt,
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
    workflow = Path(".github/workflows/ci-engine-v2-release-candidate.yml").read_text(
        encoding="utf-8"
    )

    assert NATIVE_VERSION == "0.2.0rc6"
    assert cargo["package"]["version"] == "0.2.0-rc.6"
    assert native["project"]["version"] == NATIVE_VERSION
    assert "betelgeuze-engine-v2-native-0.2.0rc6.spdx.json" in workflow
    assert (
        "engine-v2-native-0.2.0rc6-${{ matrix.abi }}-"
        "${{ github.run_id }}-${{ github.run_attempt }}"
    ) in workflow
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
        "ARFLAGS",
        "ARFLAGS_x86_64_unknown_linux_gnu",
        "HOST_ARFLAGS",
        "TARGET_ARFLAGS",
        "PYO3_PYTHON",
        "TARGET_X86_64_UNKNOWN_LINUX_GNU_LDFLAGS",
        "CXXFLAGS_x86_64_unknown_linux_gnu",
        "HIPCC_COMPILE_FLAGS_APPEND",
        "HIP_CLANG_HCC_COMPAT_MODE",
        "HIP_COMPILE_CXX_AS_HIP",
        "HIP_LIB_PATH",
        "HIP_ROCCLR_HOME",
        "HIPCC_VERBOSE",
        "CUDA_PATH",
        "DEVICE_LIB_PATH",
        "PERL5LIB",
        "PERL5OPT",
        "PERLLIB",
    ),
)
def test_native_build_rejects_caller_build_overrides(name: str) -> None:
    with pytest.raises(RuntimeError, match=name):
        _reject_direct_build_overrides({name: "attacker-controlled"})


@pytest.mark.parametrize(
    "name", ("RUSTFLAGS", "ARFLAGS", "PERL5LIB", "PERL5OPT", "PERLLIB")
)
def test_native_build_public_entrypoint_rejects_override_before_output_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    output = tmp_path / f"must-not-be-created-{name}"
    monkeypatch.setenv(name, "attacker-controlled")

    with pytest.raises(RuntimeError, match=name):
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
            "PERL5LIB": "",
            "PERL5OPT": "",
            "PERLLIB": "",
            "PYTHONPATH": "/untrusted/python/module/path",
            "RUSTFLAGS": "",
        },
        toolchain,
        native_toolchain,
    )

    assert environment["CARGO_HOME"] == str(cargo_home)
    assert environment["CARGO_TARGET_DIR"] == str(target_dir)
    assert "LD_LIBRARY_PATH" not in environment
    assert "PERL5LIB" not in environment
    assert "PERL5OPT" not in environment
    assert "PERLLIB" not in environment
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
    assert hip_command[hip_command.index("--features") + 1] == ("extension-module,hip")


def test_native_toolchain_directory_closure_is_content_bound(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/a.h").write_text("first", encoding="utf-8")
    first = _directory_closure_sha256(tmp_path, b"test-domain")
    (tmp_path / "nested/a.h").write_text("second", encoding="utf-8")
    second = _directory_closure_sha256(tmp_path, b"test-domain")

    assert first[1] == second[1] == 1
    assert first[0] != second[0]


def test_gcc_filesystem_closure_binds_modes_symlinks_and_target_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "compiler-resource"
    target.write_bytes(b"first")
    target.chmod(0o640)
    alias = root / "resource-alias"
    alias.symlink_to("compiler-resource")

    first = _filesystem_tree_closure_sha256(root, b"gcc-test-domain")
    target.write_bytes(b"second")
    second = _filesystem_tree_closure_sha256(root, b"gcc-test-domain")
    target.chmod(0o600)
    third = _filesystem_tree_closure_sha256(root, b"gcc-test-domain")

    assert first[1] == second[1] == third[1] == 4
    assert first[0] != second[0]
    assert second[0] != third[0]


def test_gcc_filesystem_closure_binds_broken_symlink_absence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    alias = root / "optional-linker"
    alias.symlink_to("missing-ld.gold")

    first = _filesystem_tree_closure_sha256(root, b"gcc-test-domain")
    alias.unlink()
    alias.symlink_to("different-missing-ld.gold")
    second = _filesystem_tree_closure_sha256(root, b"gcc-test-domain")

    assert first[1] == second[1] == 2
    assert first[0] != second[0]


def test_canonical_profiles_bind_complete_gcc_host_closures() -> None:
    assert _CPU_GCC_CLOSURE.cxx == Path("/opt/rh/gcc-toolset-14/root/usr/bin/g++")
    assert _HIP_GCC_CLOSURE.cxx == Path("/usr/bin/x86_64-linux-gnu-g++-11")
    for profile in (_CPU_GCC_CLOSURE, _HIP_GCC_CLOSURE):
        assert len(profile.expected_sha256) == 64
        assert set(profile.expected_sha256) != {"0"}
        assert profile.expected_entry_count > 4_000
        assert profile.expected_total_bytes > 300_000_000
        assert any(label == "system_includes" for label, _, _ in profile.tree_roots)
        assert profile.runtime_files
    assert _GCC_PROGRAM_NAMES == (
        "cc1",
        "cc1plus",
        "collect2",
        "lto1",
        "lto-wrapper",
    )
    assert {
        "crt1.o",
        "crtbeginS.o",
        "crtbeginT.o",
        "crtendS.o",
        "libstdc++.so",
        "libgcc.a",
        "libgcc_s.so",
        "libgcc_s.so.1",
        "libm.so",
        "libmvec.so.1",
        "libc.so",
        "libc_nonshared.a",
    }.issubset(_GCC_LINK_INPUT_NAMES)


def test_hip_profile_binds_complete_perl_module_search_closure() -> None:
    assert _HIP_PERL_CLOSURE.perl == Path("/usr/bin/perl")
    assert _HIP_PERL_CLOSURE.version == "v5.34.0"
    assert _HIP_PERL_CLOSURE.archname == "x86_64-linux-gnu-thread-multi"
    assert tuple(map(str, _HIP_PERL_CLOSURE.inc_paths)) == (
        "/etc/perl",
        "/usr/local/lib/x86_64-linux-gnu/perl/5.34.0",
        "/usr/local/share/perl/5.34.0",
        "/usr/lib/x86_64-linux-gnu/perl5/5.34",
        "/usr/share/perl5",
        "/usr/lib/x86_64-linux-gnu/perl-base",
        "/usr/lib/x86_64-linux-gnu/perl/5.34",
        "/usr/share/perl/5.34",
        "/usr/local/lib/site_perl",
    )
    assert len(_HIP_PERL_CLOSURE.expected_sha256) == 64
    assert set(_HIP_PERL_CLOSURE.expected_sha256) != {"0"}
    assert _HIP_PERL_CLOSURE.expected_entry_count > 3_000
    assert _HIP_PERL_CLOSURE.expected_total_bytes > 50_000_000


def test_hip_profile_binds_linker_and_soname_runtime_symlinks() -> None:
    specifications = {item.label: item for item in _ROCM_FILE_SPECS}
    expected_target = Path("/opt/rocm-6.0.2/lib/libamdhip64.so.6.0.60002")
    assert specifications["amdhip64_linker_name"].path == Path(
        "/opt/rocm-6.0.2/lib/libamdhip64.so"
    )
    assert specifications["amdhip64_linker_name"].resolved_path == expected_target
    assert specifications["amdhip64_linker_name"].symlink_target == "libamdhip64.so.6"
    assert specifications["amdhip64_soname"].path == Path(
        "/opt/rocm-6.0.2/lib/libamdhip64.so.6"
    )
    assert specifications["amdhip64_soname"].resolved_path == expected_target
    assert (
        specifications["amdhip64_soname"].symlink_target
        == "libamdhip64.so.6.0.60002"
    )


def test_perl_module_closure_binds_module_bytes_and_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_root = tmp_path / "first"
    first_root.mkdir()
    module = first_root / "Compiler.pm"
    module.write_bytes(b"package Compiler; 1;\n")
    absent_root = tmp_path / "absent"
    lines = ["v5.34.0", "test-arch", str(first_root), str(absent_root)]
    stdout = ("\n".join(lines) + "\n").encode("utf-8")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=(), returncode=0, stdout=stdout, stderr=b""
        ),
    )
    specification = FrozenPerlClosureSpec(
        perl=Path("/frozen/perl"),
        version="v5.34.0",
        archname="test-arch",
        inc_paths=(first_root, absent_root),
        expected_sha256="0" * 64,
        expected_entry_count=0,
        expected_total_bytes=0,
    )

    first = _perl_runtime_closure_receipt(specification)
    module.write_bytes(b"package Compiler; die 'injected';\n")
    second = _perl_runtime_closure_receipt(specification)
    absent_root.mkdir()
    third = _perl_runtime_closure_receipt(specification)

    assert first[0] != second[0]
    assert second[0] != third[0]


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


def test_native_toolchain_linker_symlink_text_is_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "libamdhip64.so.6.0.60002"
    target.write_bytes(b"frozen runtime")
    middle = tmp_path / "libamdhip64.so.6"
    middle.symlink_to(target.name)
    linker_name = tmp_path / "libamdhip64.so"
    linker_name.symlink_to(middle.name)
    specification = FrozenFileSpec(
        label="amdhip64_linker_name",
        path=linker_name,
        resolved_path=target,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        executable=False,
        symlink_target=middle.name,
    )

    _verify_frozen_files((specification,))
    linker_name.unlink()
    linker_name.symlink_to(target.name)

    with pytest.raises(RuntimeError, match="symlink changed"):
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
    for source_path in sorted(Path("rust/betelgeuze-docking-search/src").glob("*.rs")):
        production_source = source_path.read_text(encoding="utf-8").split(
            "#[cfg(test)]", 1
        )[0]
        assert platform_math.search(production_source) is None, source_path


def test_native_wheel_member_guard_accepts_only_separate_extension(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-manylinux_2_28_x86_64.whl"
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
        "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-manylinux_2_28_x86_64.whl"
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
