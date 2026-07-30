from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from tools.build_engine_v2_native_wheel import _verify_wheel


def test_native_wheel_member_guard_accepts_only_separate_extension(tmp_path: Path) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc5-cp310-cp310-"
        "manylinux_2_28_x86_64.whl"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so", b"x")
        archive.writestr(
            "betelgeuze_engine_v2_native-0.2.0rc5.dist-info/METADATA",
            "Name: betelgeuze-engine-v2-native\nVersion: 0.2.0rc5\n",
        )

    _verify_wheel(wheel)


def test_native_wheel_member_guard_rejects_bundled_python_package(tmp_path: Path) -> None:
    wheel = tmp_path / (
        "betelgeuze_engine_v2_native-0.2.0rc5-cp310-cp310-"
        "manylinux_2_28_x86_64.whl"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so", b"x")
        archive.writestr("betelgeuze_engine_v2/__init__.py", b"")
        archive.writestr(
            "betelgeuze_engine_v2_native-0.2.0rc5.dist-info/METADATA",
            "Name: betelgeuze-engine-v2-native\nVersion: 0.2.0rc5\n",
        )

    with pytest.raises(RuntimeError, match="must not bundle"):
        _verify_wheel(wheel)
