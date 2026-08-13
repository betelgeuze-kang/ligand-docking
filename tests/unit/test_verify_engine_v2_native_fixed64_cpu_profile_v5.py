from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v5 import (
    NativeFixed64CPUProfileV5ArchiveError,
    require_archived_profile_v5,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v5.json"
_ARCHIVE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v5_archive.json"
_VERIFIER = _ROOT / "tools/verify_engine_v2_native_fixed64_cpu_profile_v5.py"


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


def test_v5_archive_is_merge_anchored_and_authority_false() -> None:
    archive = require_archived_profile_v5(_PROFILE.read_bytes(), _ARCHIVE.read_bytes())
    assert archive["implementation_main_commit_oid"] == (
        "50c6a0e633b6edc90a5e4fae3d7740c5957816ea"
    )
    assert archive["review"] == {
        "required_checks_success": 95,
        "reviewed_head_oid": "9d4f275cf6bd72798cad2562346ea81718859514",
        "unresolved_review_threads": 0,
    }
    assert archive["execution_consumed"] is False
    assert archive["reservation_created"] is False
    assert all(value is False for value in archive["authority"].values())


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("execution_consumed",), True),
        (("reservation_created",), True),
        (("authority", "qualification_authority"), True),
        (("implementation_main_commit_oid",), "0" * 40),
        (("review", "required_checks_success"), 94),
        (("transitive_source_count",), 186),
    ),
)
def test_v5_archive_tamper_fails_closed(path: tuple[str, ...], value: object) -> None:
    archive = json.loads(_ARCHIVE.read_text(encoding="ascii"))
    changed = deepcopy(archive)
    cursor = changed
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(NativeFixed64CPUProfileV5ArchiveError):
        require_archived_profile_v5(_PROFILE.read_bytes(), _canonical(changed))


def test_v5_profile_byte_tamper_fails_closed() -> None:
    profile = _PROFILE.read_bytes().replace(
        b'"qualification_authority": false',
        b'"qualification_authority": true ',
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV5ArchiveError):
        require_archived_profile_v5(profile, _ARCHIVE.read_bytes())


def test_v5_archive_cli_reports_historical_not_current_binding() -> None:
    result = subprocess.run(
        [sys.executable, str(_VERIFIER)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["archived"] is True
    assert payload["compiled_profile_binding_verified"] is False
    assert payload["all_authority_false"] is True
    assert payload["execution_consumed"] is False
    assert payload["reservation_created"] is False
