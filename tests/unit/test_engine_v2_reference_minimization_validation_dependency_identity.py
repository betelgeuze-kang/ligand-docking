from __future__ import annotations

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
