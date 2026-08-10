from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from tools.build_engine_v2_native_wheel import (
    FROZEN_RELEASE_PROFILE_ENV,
    FROZEN_TARGET_TRIPLE,
    _sanitized_build_environment,
    _verify_wheel,
)


def test_native_wheel_environment_strips_toolchain_and_profile_overrides() -> None:
    inherited = {
        "PATH": "/usr/bin",
        "RUSTC": "/tmp/forged-rustc",
        "RUSTC_WRAPPER": "/tmp/wrapper",
        "RUSTFLAGS": "-C opt-level=0",
        "CARGO_ENCODED_RUSTFLAGS": "-C\x1fopt-level=0",
        "CARGO_PROFILE_RELEASE_LTO": "false",
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS": "-C panic=unwind",
        "CARGO_TARGET_DIR": "/tmp/target-cache",
    }
    result = _sanitized_build_environment(
        inherited, rustc=Path("/opt/frozen/bin/rustc")
    )

    assert result["RUSTC"] == "/opt/frozen/bin/rustc"
    assert result["CARGO_BUILD_TARGET"] == FROZEN_TARGET_TRIPLE
    assert result["CARGO_INCREMENTAL"] == "0"
    assert result["CARGO_TARGET_DIR"] == "/tmp/target-cache"
    assert "RUSTFLAGS" not in result
    assert "RUSTC_WRAPPER" not in result
    assert "CARGO_ENCODED_RUSTFLAGS" not in result
    assert all(
        result[key] == value for key, value in FROZEN_RELEASE_PROFILE_ENV.items()
    )
    assert "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS" not in result


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
