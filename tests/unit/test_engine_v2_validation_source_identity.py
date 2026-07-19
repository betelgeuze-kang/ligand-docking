from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import time

import pytest

from betelgeuze_engine_v2.physics import validation_source_identity as module
from betelgeuze_engine_v2.physics.validation_source_identity import (
    VALIDATION_SOURCE_MANIFEST_SCHEMA_ID,
    ValidationSourceIdentityError,
    observed_validation_source_manifest_document,
    require_validation_source_manifest_document,
)


def _run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("/usr/bin/git", *arguments),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _source_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source"
    package = repository / "betelgeuze_engine_v2"
    nested = package / "physics"
    nested.mkdir(parents=True)
    (package / "__init__.py").write_text('"""test package"""\n', encoding="utf-8")
    (nested / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    _run_git(repository, "init", "-q")
    _run_git(repository, "config", "user.email", "source-test@example.invalid")
    _run_git(repository, "config", "user.name", "Source Test")
    _run_git(repository, "add", "betelgeuze_engine_v2")
    _run_git(repository, "commit", "-q", "-m", "source fixture")
    return repository.resolve(), _run_git(repository, "rev-parse", "HEAD")


def _allow_test_owned_source(monkeypatch: pytest.MonkeyPatch) -> None:
    def require_directory(path: Path) -> Path:
        return path.resolve(strict=True)

    monkeypatch.setattr(
        module,
        "_require_root_owned_read_only_directory_chain",
        require_directory,
    )
    monkeypatch.setattr(
        module,
        "_require_trusted_source_directory_stat",
        lambda file_stat: None,
    )
    monkeypatch.setattr(
        module,
        "_require_trusted_source_file_stat",
        lambda file_stat, *, expected_mode: None,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def test_source_manifest_binds_verified_git_tree_and_exact_file_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)

    document = observed_validation_source_manifest_document(repository, commit)

    assert document["schema_id"] == VALIDATION_SOURCE_MANIFEST_SCHEMA_ID
    assert document["code_commit_sha"] == commit
    assert document["file_count"] == 2
    assert [row["path"] for row in document["files"]] == [
        "betelgeuze_engine_v2/__init__.py",
        "betelgeuze_engine_v2/physics/model.py",
    ]
    assert require_validation_source_manifest_document(document) == document


@pytest.mark.parametrize("mutation", ("tracked-tamper", "untracked", "missing"))
def test_source_manifest_rejects_actual_tree_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)
    package = repository / "betelgeuze_engine_v2"
    if mutation == "tracked-tamper":
        (package / "__init__.py").write_text("TAMPERED = True\n", encoding="utf-8")
    elif mutation == "untracked":
        (package / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")
    else:
        (package / "physics" / "model.py").unlink()

    with pytest.raises(ValidationSourceIdentityError):
        observed_validation_source_manifest_document(repository, commit)


def test_source_manifest_rejects_symlink_and_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)
    package = repository / "betelgeuze_engine_v2"
    target = package / "physics" / "model.py"
    target.unlink()
    target.symlink_to(package / "__init__.py")
    with pytest.raises(ValidationSourceIdentityError):
        observed_validation_source_manifest_document(repository, commit)

    target.unlink()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(module, "VALIDATION_SOURCE_MANIFEST_MAX_FILES", 1)
    with pytest.raises(ValidationSourceIdentityError, match="file bound"):
        observed_validation_source_manifest_document(repository, commit)

    with pytest.raises(ValidationSourceIdentityError, match="deadline"):
        observed_validation_source_manifest_document(
            repository,
            commit,
            deadline=time.monotonic() - 1.0,
        )


def test_source_manifest_rejects_reordering_and_needs_out_of_band_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)
    document = observed_validation_source_manifest_document(repository, commit)

    reordered = deepcopy(document)
    reordered["files"] = list(reversed(reordered["files"]))
    projection = dict(reordered)
    projection.pop("manifest_sha256")
    reordered["manifest_sha256"] = _canonical_hash(projection)
    with pytest.raises(ValidationSourceIdentityError, match="file row"):
        require_validation_source_manifest_document(reordered)

    tampered = deepcopy(document)
    tampered["files"][0]["sha256"] = "0" * 64
    projection = dict(tampered)
    projection.pop("manifest_sha256")
    tampered["manifest_sha256"] = _canonical_hash(projection)
    assert require_validation_source_manifest_document(tampered) == tampered
    assert tampered != document


def test_git_objects_and_unsafe_modes_are_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)
    budget = module._SourceBudget(time.monotonic() + 10.0)
    original = module._run_git_bounded

    def tampered_git(*args: object, **kwargs: object) -> bytes:
        return original(*args, **kwargs) + b"x"

    monkeypatch.setattr(module, "_run_git_bounded", tampered_git)
    with pytest.raises(ValidationSourceIdentityError, match="object ID"):
        module._read_verified_git_object(
            repository,
            commit,
            "commit",
            budget=budget,
        )

    symlink_tree = b"120000 unsafe\0" + bytes.fromhex("0" * 40)
    with pytest.raises(ValidationSourceIdentityError, match="unsafe"):
        module._parse_tree(symlink_tree)


def test_git_tree_entry_bound_is_applied_inside_parser_before_row_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "VALIDATION_SOURCE_MANIFEST_MAX_ENTRIES", 1)
    payload = (
        b"100644 first\0"
        + bytes.fromhex("1" * 40)
        + b"100644 second\0"
        + bytes.fromhex("2" * 40)
    )

    with pytest.raises(ValidationSourceIdentityError, match="entry bound"):
        module._parse_tree(payload)


def test_source_file_size_cap_is_enforced_before_payload_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, commit = _source_repository(tmp_path)
    _allow_test_owned_source(monkeypatch)
    monkeypatch.setattr(module, "VALIDATION_SOURCE_MANIFEST_MAX_FILE_BYTES", 0)

    with pytest.raises(ValidationSourceIdentityError, match="pre-read byte bound"):
        observed_validation_source_manifest_document(repository, commit)


def test_trusted_source_stat_guards_reject_mutable_or_nonregular_entries() -> None:
    directory_stat = type("Stat", (), {"st_mode": stat.S_IFDIR | 0o777, "st_uid": 0})()
    with pytest.raises(ValidationSourceIdentityError, match="read-only"):
        module._require_trusted_source_directory_stat(directory_stat)

    file_stat = type(
        "Stat",
        (),
        {"st_mode": stat.S_IFREG | 0o644, "st_uid": 1000, "st_nlink": 1},
    )()
    with pytest.raises(ValidationSourceIdentityError, match="root-owned"):
        module._require_trusted_source_file_stat(file_stat, expected_mode="100644")
