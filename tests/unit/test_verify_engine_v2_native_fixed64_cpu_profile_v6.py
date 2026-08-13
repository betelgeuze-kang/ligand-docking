from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.verify_engine_v2_native_fixed64_cpu_profile_v6 import (
    NativeFixed64CPUProfileV6Error,
    PROFILE_SHA256,
    require_archived_profile_v6,
)


_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v6.json"
_ARCHIVE = _ROOT / "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
_PACKAGED = (
    _ROOT
    / "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
)
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


def test_v6_archive_is_merge_anchored_and_packaged_identically() -> None:
    profile_raw = _PROFILE.read_bytes()
    archive_raw = _ARCHIVE.read_bytes()
    archive = require_archived_profile_v6(profile_raw, archive_raw)
    assert archive["profile_sha256"] == PROFILE_SHA256
    assert archive["execution_consumed"] is False
    assert archive["reservation_created"] is False
    assert archive["review"] == {
        "required_checks_success": 33,
        "reviewed_head_oid": "0c4d0b911fbc6e75b1e806620d36a282fc24893a",
        "unresolved_review_threads": 0,
    }
    assert _PACKAGED.read_bytes() == archive_raw


def test_v6_archive_rejects_authority_or_merge_drift() -> None:
    profile_raw = _PROFILE.read_bytes()
    archive = json.loads(_ARCHIVE.read_text(encoding="ascii"))
    archive["authority"]["qualification_authority"] = True
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="archive evidence"):
        require_archived_profile_v6(profile_raw, _canonical(archive))

    archive = json.loads(_ARCHIVE.read_text(encoding="ascii"))
    archive["implementation_main_commit_oid"] = "0" * 40
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="archive evidence"):
        require_archived_profile_v6(profile_raw, _canonical(archive))


def test_v6_archive_rejects_profile_or_duplicate_key_drift() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="ascii"))
    profile["authority"]["molecular_execution_authorized"] = True
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="profile bytes"):
        require_archived_profile_v6(_canonical(profile), _ARCHIVE.read_bytes())

    raw = _ARCHIVE.read_bytes().replace(
        b'{\n  "authority":',
        b'{\n  "execution_consumed": false,\n  "authority":',
        1,
    )
    with pytest.raises(NativeFixed64CPUProfileV6Error, match="duplicate JSON key"):
        require_archived_profile_v6(_PROFILE.read_bytes(), raw)


def test_v6_archive_cli_reports_non_consumed_false_authority() -> None:
    completed = subprocess.run(
        [sys.executable, str(_TOOL)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["archived"] is True
    assert report["all_authority_false"] is True
    assert report["execution_consumed"] is False
    assert report["reservation_created"] is False
