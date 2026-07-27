from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
import stat

import pytest

from betelgeuze_engine_v2.physics import (
    reference_minimization_validation_dependency_identity as dependency_identity,
)


def _file_stat(
    *,
    uid: int = 0,
    gid: int = 0,
    permissions: int = 0o644,
    nlink: int = 1,
    inode: int = 17,
    size: int = 23,
    mtime_ns: int = 31,
    ctime_ns: int = 37,
) -> SimpleNamespace:
    return SimpleNamespace(
        st_dev=11,
        st_ino=inode,
        st_uid=uid,
        st_gid=gid,
        st_mode=stat.S_IFREG | permissions,
        st_nlink=nlink,
        st_size=size,
        st_mtime_ns=mtime_ns,
        st_ctime_ns=ctime_ns,
    )


def test_trusted_regular_file_policy_accepts_root_owned_read_only_file() -> None:
    dependency_identity._require_trusted_regular_file_stat(_file_stat())


@pytest.mark.parametrize(
    ("file_stat", "reason"),
    (
        (_file_stat(uid=1000), "non-root owner"),
        (_file_stat(permissions=0o664), "group writable"),
        (_file_stat(permissions=0o646), "world writable"),
        (_file_stat(nlink=2), "multiple hard links"),
        (
            SimpleNamespace(
                **{
                    **_file_stat().__dict__,
                    "st_mode": stat.S_IFLNK | 0o777,
                }
            ),
            "non-regular file",
        ),
    ),
)
def test_trusted_regular_file_policy_rejects_mutable_or_ambiguous_file(
    file_stat: SimpleNamespace,
    reason: str,
) -> None:
    del reason
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="root-owned read-only single-link regular file",
    ):
        dependency_identity._require_trusted_regular_file_stat(file_stat)


def test_stat_signature_binds_mode_owner_link_count_and_ctime() -> None:
    baseline = dependency_identity._stat_signature(_file_stat())
    assert dependency_identity._stat_signature(_file_stat(uid=1000)) != baseline
    assert dependency_identity._stat_signature(_file_stat(permissions=0o664)) != baseline
    assert dependency_identity._stat_signature(_file_stat(nlink=2)) != baseline
    assert dependency_identity._stat_signature(_file_stat(ctime_ns=41)) != baseline


@pytest.mark.parametrize(
    "path",
    (
        "numpy/__init__.py",
        "torch/lib/libtorch.so",
        "../../../bin/torchrun",
    ),
)
def test_distribution_record_path_accepts_canonical_wheel_paths(path: str) -> None:
    assert dependency_identity._normalized_distribution_relative_path(path) == path


@pytest.mark.parametrize(
    "path",
    (
        "",
        "/usr/bin/escape",
        "numpy/../escape.py",
        "numpy/./escape.py",
        "numpy//escape.py",
        "numpy\\escape.py",
        "../../..",
    ),
)
def test_distribution_record_path_rejects_noncanonical_traversal(path: str) -> None:
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError
    ):
        dependency_identity._normalized_distribution_relative_path(path)


def test_record_sha256_accepts_only_canonical_unpadded_urlsafe_base64() -> None:
    digest = hashlib.sha256(b"canonical RECORD payload").digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    assert dependency_identity._decode_canonical_record_sha256(encoded) == digest.hex()


@pytest.mark.parametrize(
    "encoded",
    (
        "",
        "A" * 42,
        "A" * 44,
        "A" * 42 + "+",
        "A" * 42 + "/",
        "A" * 43 + "=",
        "A" * 42 + "B",
        "é" * 43,
    ),
)
def test_record_sha256_rejects_malformed_or_noncanonical_base64(
    encoded: str,
) -> None:
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="RECORD hash is malformed",
    ):
        dependency_identity._decode_canonical_record_sha256(encoded)


def _allow_test_filesystem_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    def require_directory(file_stat) -> None:
        if not stat.S_ISDIR(file_stat.st_mode):
            raise dependency_identity.ReferenceMinimizationValidationDependencyIdentityError(
                "dependency directory is not root-owned read-only storage"
            )

    def require_file(file_stat) -> None:
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise dependency_identity.ReferenceMinimizationValidationDependencyIdentityError(
                "dependency file is not a root-owned read-only single-link regular file"
            )

    monkeypatch.setattr(
        dependency_identity,
        "_require_trusted_directory_stat",
        require_directory,
    )
    monkeypatch.setattr(
        dependency_identity,
        "_require_trusted_regular_file_stat",
        require_file,
    )


def test_secure_hash_reads_regular_file_by_lexical_components(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    nested = root / "package"
    nested.mkdir(parents=True)
    target = nested / "payload.bin"
    target.write_bytes(b"trusted payload\n")

    digest, size = dependency_identity._hash_regular_file(
        target,
        allowed_roots=(root,),
    )

    assert digest == hashlib.sha256(b"trusted payload\n").hexdigest()
    assert size == len(b"trusted payload\n")


def test_secure_hash_rejects_final_component_symlink(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    root.mkdir()
    target = root / "payload.bin"
    target.write_bytes(b"payload")
    alias = root / "alias.bin"
    alias.symlink_to(target.name)

    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError
    ):
        dependency_identity._hash_regular_file(alias, allowed_roots=(root,))


def test_secure_hash_rejects_parent_component_symlink(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    real = root / "real"
    real.mkdir(parents=True)
    (real / "payload.bin").write_bytes(b"payload")
    (root / "alias").symlink_to(real.name, target_is_directory=True)

    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError
    ):
        dependency_identity._hash_regular_file(
            root / "alias" / "payload.bin",
            allowed_roots=(root,),
        )


def test_secure_hash_rejects_noncanonical_lexical_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    root.mkdir()
    (root / "payload.bin").write_bytes(b"payload")
    lexical = str(root / "nested" / ".." / "payload.bin")

    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="lexically canonical",
    ):
        dependency_identity._hash_regular_file(
            dependency_identity.Path(lexical),
            allowed_roots=(root,),
        )


def test_secure_hash_rejects_file_replacement_between_lstat_and_open(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    root.mkdir()
    target = root / "payload.bin"
    target.write_bytes(b"original")
    original_open = dependency_identity.os.open
    replaced = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        if (
            not replaced
            and path == target.name
            and dir_fd is not None
            and not flags & dependency_identity.os.O_DIRECTORY
        ):
            replaced = True
            target.rename(root / "payload.old")
            target.write_bytes(b"replacement")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(dependency_identity.os, "open", racing_open)
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="changed while it was opened",
    ):
        dependency_identity._hash_regular_file(target, allowed_roots=(root,))


def test_secure_hash_rejects_file_replacement_after_read(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    root.mkdir()
    target = root / "payload.bin"
    target.write_bytes(b"original payload")
    original_read = dependency_identity.os.read
    replaced = False

    def racing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = original_read(descriptor, size)
        if chunk and not replaced:
            replaced = True
            target.rename(root / "payload.old")
            target.write_bytes(b"replacement payload")
        return chunk

    monkeypatch.setattr(dependency_identity.os, "read", racing_read)
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="changed while being measured",
    ):
        dependency_identity._hash_regular_file(target, allowed_roots=(root,))


def test_secure_hash_rejects_reused_inode_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_test_filesystem_policy(monkeypatch)
    root = tmp_path / "trusted"
    root.mkdir()
    target = root / "payload.bin"
    target.write_bytes(b"payload")
    seen: set[tuple[int, int]] = set()

    dependency_identity._hash_regular_file(
        target,
        allowed_roots=(root,),
        seen_file_identities=seen,
    )
    with pytest.raises(
        dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        match="aliases one inode",
    ):
        dependency_identity._hash_regular_file(
            target,
            allowed_roots=(root,),
            seen_file_identities=seen,
        )
