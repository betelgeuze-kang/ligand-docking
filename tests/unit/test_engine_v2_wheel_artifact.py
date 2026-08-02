from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Callable
import warnings
import zipfile

import pytest

from betelgeuze_engine_v2.benchmark import wheel_artifact as module
from betelgeuze_engine_v2.benchmark.wheel_artifact import (
    _canonical_bytes,
    _license_scope_sha256,
    LICENSE_DETERMINATION_SCHEMA_ID,
    NATIVE_BUILD_PROVENANCE_SCHEMA_ID,
    WheelArtifactKind,
    validate_wheel_artifact,
)
from tools.build_engine_v2_sbom import build_sbom


VERSION = "0.2.0rc5"
BASE_DISTRIBUTION = "betelgeuze-engine-v2"
NATIVE_DISTRIBUTION = "betelgeuze-engine-v2-native"
BASE_FILENAME = "betelgeuze_engine_v2-0.2.0rc5-py3-none-any.whl"
NATIVE_FILENAME = "betelgeuze_engine_v2_native-0.2.0rc5-cp310-cp310-manylinux_2_28_x86_64.whl"
BASE_REQUIRES_DIST = (
    "cryptography==46.0.5",
    "numpy<3,>=1.26",
    "torch==2.6.0",
    (
        "betelgeuze-engine-v2-native==0.2.0rc5; "
        '(platform_system == "Linux" and platform_machine == "x86_64") '
        'and extra == "native-cpu"'
    ),
)
BASE_CONSOLE_SCRIPTS = {
    "betelgeuze-engine-v2": "betelgeuze_engine_v2.cli_dispatch:main",
    "betelgeuze-dock": "betelgeuze_engine_v2.standalone_cli:main",
}


def _record_hash(payload: bytes) -> str:
    digest = hashlib.sha256(payload).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _record_bytes(
    members: dict[str, bytes],
    record_path: str,
    *,
    mutation: str = "",
) -> bytes:
    rows: list[list[str]] = [
        [name, _record_hash(payload), str(len(payload))] for name, payload in sorted(members.items())
    ]
    payload_path = next(name for name in members if not name.endswith(("METADATA", "WHEEL")))
    if mutation == "wrong_hash":
        for row in rows:
            if row[0] == payload_path:
                row[1] = "sha256=" + base64.urlsafe_b64encode(b"\x00" * 32).rstrip(b"=").decode("ascii")
    elif mutation == "wrong_size":
        for row in rows:
            if row[0] == payload_path:
                row[2] = str(int(row[2]) + 1)
    elif mutation == "missing_payload_row":
        rows = [row for row in rows if row[0] != payload_path]
    elif mutation == "unhashed_payload":
        for row in rows:
            if row[0] == payload_path:
                row[1] = ""
    self_row = [record_path, "", ""]
    if mutation == "hashed_record_self":
        self_row = [record_path, _record_hash(b"not-self-referential"), "20"]
    rows.append(self_row)
    handle = io.StringIO(newline="")
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _write_wheel(
    directory: Path,
    *,
    kind: WheelArtifactKind,
    filename: str | None = None,
    metadata_name: str | None = None,
    metadata_version: str = VERSION,
    record_mutation: str = "",
    extension_payloads: tuple[tuple[str, bytes], ...] | None = None,
    include_wheel_metadata: bool = True,
    extra_payloads: tuple[tuple[str, bytes], ...] = (),
    unsafe_member: str = "",
    duplicate_member: bool = False,
    requires_dist: tuple[str, ...] | None = None,
) -> tuple[Path, str]:
    if kind is WheelArtifactKind.BASE:
        distribution = BASE_DISTRIBUTION
        wheel_filename = filename or BASE_FILENAME
        dist_info = "betelgeuze_engine_v2-0.2.0rc5.dist-info"
        tag = "py3-none-any"
        purelib = "true"
        payloads = (("betelgeuze_engine_v2/__init__.py", b'__version__ = "0.2.0rc5"\n'),)
    else:
        distribution = NATIVE_DISTRIBUTION
        wheel_filename = filename or NATIVE_FILENAME
        dist_info = "betelgeuze_engine_v2_native-0.2.0rc5.dist-info"
        tag = "cp310-cp310-manylinux_2_28_x86_64"
        purelib = "false"
        payloads = extension_payloads or (
            (
                "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so",
                b"\x7fELF" + b"native-extension-fixture" * 4,
            ),
        )
    if kind is WheelArtifactKind.BASE:
        active_requirements = BASE_REQUIRES_DIST if requires_dist is None else requires_dist
        metadata = (
            "Metadata-Version: 2.2\n"
            f"Name: {metadata_name or distribution}\n"
            f"Version: {metadata_version}\n"
            "Summary: Fail-closed independent molecular Engine v2 reference contracts and CPU primitives.\n"
            "Classifier: Development Status :: 4 - Beta\n"
            "Classifier: Programming Language :: Python :: 3\n"
            "Classifier: Programming Language :: Python :: 3.10\n"
            "Classifier: Programming Language :: Python :: 3.11\n"
            "Classifier: Programming Language :: Python :: 3.12\n"
            "Classifier: Operating System :: OS Independent\n"
            "Classifier: Typing :: Typed\n"
            "Requires-Python: <3.13,>=3.10\n"
            + "".join(f"Requires-Dist: {value}\n" for value in active_requirements)
            + "Provides-Extra: native-cpu\n"
        ).encode("utf-8")
        generator = "setuptools (75.8.2)"
    else:
        active_requirements = () if requires_dist is None else requires_dist
        metadata = (
            "Metadata-Version: 2.4\n"
            f"Name: {metadata_name or distribution}\n"
            f"Version: {metadata_version}\n"
            + "".join(f"Requires-Dist: {value}\n" for value in active_requirements)
            + "\n"
        ).encode("utf-8")
        generator = "engine-v2-wheel-artifact-test"
    wheel_metadata = (
        f"Wheel-Version: 1.0\nGenerator: {generator}\nRoot-Is-Purelib: {purelib}\nTag: {tag}\n\n"
    ).encode("utf-8")
    members = dict(payloads)
    members.update(extra_payloads)
    members[f"{dist_info}/METADATA"] = metadata
    if kind is WheelArtifactKind.BASE:
        members[f"{dist_info}/entry_points.txt"] = (
            "[console_scripts]\n"
            + "".join(
                f"{name} = {target}\n"
                for name, target in BASE_CONSOLE_SCRIPTS.items()
            )
        ).encode("utf-8")
    if include_wheel_metadata:
        members[f"{dist_info}/WHEEL"] = wheel_metadata
    if not include_wheel_metadata:
        members["betelgeuze_engine_v2/extra.py"] = b"extra = True\n"
    if unsafe_member:
        members[unsafe_member] = b"unsafe"
    record_path = f"{dist_info}/RECORD"
    members[record_path] = _record_bytes(
        members,
        record_path,
        mutation=record_mutation,
    )
    path = directory / wheel_filename
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        if duplicate_member:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                first_name = next(iter(members))
                archive.writestr(first_name, members[first_name])
    extension_sha256 = ""
    if kind is WheelArtifactKind.NATIVE and payloads:
        extension_sha256 = hashlib.sha256(payloads[0][1]).hexdigest()
    return path, extension_sha256


def _rewrite_wheel_control_member(
    wheel: Path,
    *,
    suffix: str,
    old: bytes,
    new: bytes,
) -> None:
    with zipfile.ZipFile(wheel, mode="r") as archive:
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.filename.endswith(".dist-info/RECORD")
        }
    matches = [name for name in members if name.endswith(suffix)]
    assert len(matches) == 1
    member_name = matches[0]
    assert old in members[member_name]
    members[member_name] = members[member_name].replace(old, new)
    dist_info = member_name.split("/", 1)[0]
    record_path = f"{dist_info}/RECORD"
    members[record_path] = _record_bytes(members, record_path)
    with zipfile.ZipFile(
        wheel,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def _write_json(path: Path, payload: object) -> None:
    path.write_bytes(_canonical_bytes(payload) + b"\n")


def _native_source_root(directory: Path) -> Path:
    root = directory / "native-source"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text(
        '[package]\nname = "betelgeuze-engine-v2-native"\nversion = "0.2.0-rc.5"\n',
        encoding="utf-8",
    )
    (root / "Cargo.lock").write_text(
        "version = 4\n\n"
        "[[package]]\n"
        'name = "betelgeuze-engine-v2-native"\n'
        'version = "0.2.0-rc.5"\n'
        'dependencies = [\n "fixture-dep",\n]\n\n'
        "[[package]]\n"
        'name = "fixture-dep"\n'
        'version = "1.2.3"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
        f'checksum = "{"a" * 64}"\n',
        encoding="utf-8",
    )
    (root / "build.rs").write_text("fn main() {}\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[build-system]\n", encoding="utf-8")
    (root / "src/lib.rs").write_text("pub fn fixture() {}\n", encoding="utf-8")
    return root


def _source_inventory(root: Path) -> dict[str, str]:
    names = ("Cargo.lock", "Cargo.toml", "build.rs", "pyproject.toml", "src/lib.rs")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def _license_path(
    directory: Path,
    *,
    distribution: str,
    package_keys: set[str],
) -> Path:
    path = directory / f"{distribution}.license-determination.json"
    payload = {
        "schema_id": LICENSE_DETERMINATION_SCHEMA_ID,
        "review_id": "fixture-legal-review",
        "reviewer_identity": "fixture-independent-legal-reviewer",
        "reviewed_at": "2025-01-01T00:00:00Z",
        "review_status": "approved",
        "review_evidence_sha256": "b" * 64,
        "scope_sha256": _license_scope_sha256(package_keys),
        "extracted_licenses": [],
        "determinations": [
            {
                "package_key": key,
                "license_concluded": "Apache-2.0",
                "license_declared": "Apache-2.0",
                "copyright_text": "Copyright fixture owners",
                "evidence": f"fixture-license-evidence:{key}",
            }
            for key in sorted(package_keys)
        ],
    }
    _write_json(path, payload)
    return path


def _prepare_authorities(
    directory: Path,
    wheel: Path,
    *,
    distribution: str,
) -> tuple[Path, Path, Path | None, Path | None]:
    with zipfile.ZipFile(wheel) as archive:
        payloads = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir() and ".dist-info/" not in info.filename
        }
    native = any(name.endswith((".so", ".pyd")) for name in payloads)
    if not native:
        source_root = directory / "base-source"
        source_root.mkdir(exist_ok=True)
        for name, payload in payloads.items():
            if name.startswith("../") or name.startswith("/"):
                continue
            path = source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        pyproject = source_root / "packaging/engine-v2/pyproject.toml"
        pyproject.parent.mkdir(parents=True, exist_ok=True)
        pyproject.write_bytes(
            (
                Path(__file__).resolve().parents[2]
                / "packaging/engine-v2/pyproject.toml"
            ).read_bytes()
        )
        with zipfile.ZipFile(wheel) as archive:
            metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
            metadata_text = archive.read(metadata_name).decode("utf-8")
        dependency_names = {
            re.sub(r"[-_.]+", "-", match.group(1)).lower()
            for line in metadata_text.splitlines()
            if line.startswith("Requires-Dist:")
            and (
                match := re.match(
                    r"Requires-Dist:\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)",
                    line,
                )
            )
            is not None
        }
        package_keys = {
            f"pypi:{distribution}@{VERSION}",
            *(f"pypi:{name}" for name in dependency_names),
        }
        license_path = _license_path(
            directory,
            distribution=distribution,
            package_keys=package_keys,
        )
        return source_root, license_path, None, None

    source_root = _native_source_root(directory)
    cargo_lock = source_root / "Cargo.lock"
    package_keys = {
        f"pypi:{distribution}@{VERSION}",
        "cargo:fixture-dep@1.2.3",
    }
    license_path = _license_path(
        directory,
        distribution=distribution,
        package_keys=package_keys,
    )
    extension_member = next(name for name in payloads if name.endswith((".so", ".pyd")))
    provenance = directory / f"{distribution}.native-build-provenance.json"
    source_inventory = _source_inventory(source_root)
    _write_json(
        provenance,
        {
            "schema_id": NATIVE_BUILD_PROVENANCE_SCHEMA_ID,
            "source_receipt_sha256": "c" * 64,
            "source_inventory_sha256": hashlib.sha256(
                _canonical_bytes(dict(sorted(source_inventory.items())))
            ).hexdigest(),
            "cargo_lock_sha256": hashlib.sha256(cargo_lock.read_bytes()).hexdigest(),
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "extension_member": extension_member,
            "extension_sha256": hashlib.sha256(payloads[extension_member]).hexdigest(),
            "builder_id": "fixture-manylinux-builder",
            "builder_version": "fixture-1",
            "build_environment_sha256": "d" * 64,
            "build_invocation_sha256": "e" * 64,
            "reproducible_build_match": True,
        },
    )
    return source_root, license_path, cargo_lock, provenance


def _write_sbom(
    directory: Path,
    wheel: Path,
    *,
    distribution: str,
    mutate: Callable[[dict[str, object]], None] | None = None,
) -> Path:
    path = directory / f"{distribution}.spdx.json"
    try:
        source_root, license_path, cargo_lock, native_provenance = _prepare_authorities(
            directory, wheel, distribution=distribution
        )
        payload = build_sbom(
            wheel,
            source_root=source_root,
            license_determination=license_path,
            cargo_lock=cargo_lock,
            native_build_provenance=native_provenance,
            source_receipt_sha256="c" * 64,
        )
        if mutate is not None:
            mutate(payload)
        _write_json(path, payload)
    except (OSError, RuntimeError, zipfile.BadZipFile):
        path.write_text("{}", encoding="utf-8")
    return path


def _validate_base(wheel: Path, sbom: Path, **kwargs: str):
    directory = wheel.parent
    license_path = directory / f"{BASE_DISTRIBUTION}.license-determination.json"
    return validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.BASE,
        expected_distribution=BASE_DISTRIBUTION,
        expected_version=VERSION,
        source_root=directory / "base-source",
        license_determination_path=license_path,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256=(
            hashlib.sha256(license_path.read_bytes()).hexdigest() if license_path.is_file() else "1" * 64
        ),
        **kwargs,
    )


def _validate_native(wheel: Path, sbom: Path, extension_sha256: str):
    directory = wheel.parent
    license_path = directory / f"{NATIVE_DISTRIBUTION}.license-determination.json"
    provenance_path = directory / f"{NATIVE_DISTRIBUTION}.native-build-provenance.json"
    return validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.NATIVE,
        expected_distribution=NATIVE_DISTRIBUTION,
        expected_version=VERSION,
        expected_extension_sha256=extension_sha256,
        source_root=directory / "native-source",
        license_determination_path=license_path,
        cargo_lock_path=directory / "native-source/Cargo.lock",
        native_build_provenance_path=provenance_path,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256=(
            hashlib.sha256(license_path.read_bytes()).hexdigest() if license_path.is_file() else "1" * 64
        ),
        expected_native_build_provenance_sha256=(
            hashlib.sha256(provenance_path.read_bytes()).hexdigest() if provenance_path.is_file() else "1" * 64
        ),
    )


def test_valid_base_wheel_has_complete_record_and_exact_spdx_binding(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    sbom_sha256 = hashlib.sha256(sbom.read_bytes()).hexdigest()

    result = _validate_base(
        wheel,
        sbom,
        expected_wheel_sha256=wheel_sha256,
        expected_sbom_sha256=sbom_sha256,
    )

    assert result.valid is True
    assert result.blockers == ()
    assert result.metadata_name == BASE_DISTRIBUTION
    assert result.metadata_version == VERSION
    assert result.extension_member == ""
    assert result.wheel_sha256 == wheel_sha256
    assert len(result.base_build_provenance_sha256) == 64
    assert result.to_dict()["receipt_sha256"] == result.receipt_sha256


@pytest.mark.parametrize(
    ("suffix", "old", "new", "expected_blocker"),
    (
        (
            ".dist-info/METADATA",
            b"Requires-Dist: torch==2.6.0",
            b"Requires-Dist: torch==2.7.0",
            "base_wheel_metadata_build_provenance_mismatch",
        ),
        (
            ".dist-info/entry_points.txt",
            b"betelgeuze_engine_v2.standalone_cli:main",
            b"betelgeuze_engine_v2.cli_dispatch:main",
            "base_wheel_entry_points_build_provenance_mismatch",
        ),
        (
            ".dist-info/WHEEL",
            b"Generator: setuptools (75.8.2)",
            b"Generator: setuptools (75.9.0)",
            "base_wheel_control_build_provenance_mismatch",
        ),
    ),
)
def test_base_wheel_control_files_are_bound_to_reviewed_pyproject(
    tmp_path: Path,
    suffix: str,
    old: bytes,
    new: bytes,
    expected_blocker: str,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    _rewrite_wheel_control_member(
        wheel,
        suffix=suffix,
        old=old,
        new=new,
    )

    assert _validate_base(wheel, sbom).blockers == (expected_blocker,)


def test_valid_native_wheel_binds_exactly_one_extension_to_installed_sha(
    tmp_path: Path,
) -> None:
    wheel, extension_sha256 = _write_wheel(tmp_path, kind=WheelArtifactKind.NATIVE)
    sbom = _write_sbom(tmp_path, wheel, distribution=NATIVE_DISTRIBUTION)

    result = _validate_native(wheel, sbom, extension_sha256)

    assert result.valid is True
    assert result.extension_member.endswith(".so")
    assert result.extension_sha256 == extension_sha256


def test_sbom_builder_emits_complete_hashed_wheel_inventory(tmp_path: Path) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    source_root, license_path, _, _ = _prepare_authorities(
        tmp_path,
        wheel,
        distribution=BASE_DISTRIBUTION,
    )
    payload = build_sbom(
        wheel,
        source_root=source_root,
        license_determination=license_path,
        source_receipt_sha256="c" * 64,
    )
    sbom = tmp_path / "builder-output.spdx.json"
    sbom.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with zipfile.ZipFile(wheel) as archive:
        expected_names = {info.filename for info in archive.infolist() if not info.is_dir()}
    files = payload["files"]
    assert isinstance(files, list)
    assert {row["fileName"] for row in files} >= expected_names
    assert {row["fileName"] for row in files if not row["fileName"].startswith("source/")} == expected_names
    assert payload["packages"][0]["filesAnalyzed"] is True  # type: ignore[index]
    assert _validate_base(wheel, sbom).valid is True


def test_arbitrary_bytes_and_minimal_fake_zip_are_rejected(tmp_path: Path) -> None:
    arbitrary = tmp_path / BASE_FILENAME
    arbitrary.write_bytes(b"minimal-fake-wheel")
    sbom = tmp_path / "unused.spdx.json"
    sbom.write_text("{}", encoding="utf-8")
    assert _validate_base(arbitrary, sbom).blockers == ("wheel_zip_invalid",)

    minimal = tmp_path / f"copy-{BASE_FILENAME}"
    with zipfile.ZipFile(minimal, mode="w") as archive:
        archive.writestr("fake.py", b"pass\n")
    # Preserve the valid artifact filename while replacing its bytes.
    arbitrary.unlink()
    minimal.rename(arbitrary)
    assert _validate_base(arbitrary, sbom).blockers == ("wheel_payload_incomplete",)


@pytest.mark.parametrize(
    ("unsafe_member", "duplicate_member", "expected_blocker"),
    (
        ("../escape.py", False, "wheel_member_path_unsafe"),
        ("", True, "wheel_member_duplicate"),
    ),
)
def test_wheel_members_must_be_safe_and_unique(
    tmp_path: Path,
    unsafe_member: str,
    duplicate_member: bool,
    expected_blocker: str,
) -> None:
    wheel, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.BASE,
        unsafe_member=unsafe_member,
        duplicate_member=duplicate_member,
    )
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    assert _validate_base(wheel, sbom).blockers == (expected_blocker,)


@pytest.mark.parametrize(
    ("mutation", "expected_blocker"),
    (
        ("wrong_hash", "wheel_record_hash_mismatch"),
        ("wrong_size", "wheel_record_size_mismatch"),
        ("missing_payload_row", "wheel_record_member_set_mismatch"),
        ("unhashed_payload", "wheel_record_hash_missing"),
        ("hashed_record_self", "wheel_record_self_row_invalid"),
    ),
)
def test_record_hash_size_and_member_coverage_are_fully_validated(
    tmp_path: Path,
    mutation: str,
    expected_blocker: str,
) -> None:
    wheel, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.BASE,
        record_mutation=mutation,
    )
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    assert _validate_base(wheel, sbom).blockers == (expected_blocker,)


def test_metadata_wheel_control_and_filename_identity_are_exact(tmp_path: Path) -> None:
    wrong_name, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.BASE,
        metadata_name="cross-wired-project",
    )
    sbom = _write_sbom(tmp_path, wrong_name, distribution=BASE_DISTRIBUTION)
    assert _validate_base(wrong_name, sbom).blockers == ("wheel_metadata_name_mismatch",)

    wrong_name.unlink()
    missing_wheel, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.BASE,
        include_wheel_metadata=False,
    )
    sbom = _write_sbom(tmp_path, missing_wheel, distribution=BASE_DISTRIBUTION)
    assert _validate_base(missing_wheel, sbom).blockers == ("wheel_control_metadata_missing",)

    wrong_filename = tmp_path / "betelgeuze_engine_v2-0.2.0rc4-py3-none-any.whl"
    missing_wheel.rename(wrong_filename)
    assert _validate_base(wrong_filename, sbom).blockers == ("wheel_filename_version_mismatch",)


@pytest.mark.parametrize(
    ("mutate", "expected_blocker"),
    (
        (
            lambda payload: payload.__setitem__("spdxVersion", "SPDX-2.2"),
            "wheel_sbom_spdx23_invalid",
        ),
        (
            lambda payload: payload["packages"][0].__setitem__(  # type: ignore[index,union-attr]
                "name", "cross-wired-project"
            ),
            "wheel_sbom_package_identity_mismatch",
        ),
        (
            lambda payload: payload["packages"][0].__setitem__(  # type: ignore[index,union-attr]
                "checksums", [{"algorithm": "SHA256", "checksumValue": "0" * 64}]
            ),
            "wheel_sbom_checksum_mismatch",
        ),
        (
            lambda payload: payload.__setitem__("documentNamespace", "https://betelgeuze.invalid/spdx/cross-wired"),
            "wheel_sbom_namespace_mismatch",
        ),
    ),
)
def test_spdx_23_name_version_and_checksum_binding_is_exact(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], None],
    expected_blocker: str,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(
        tmp_path,
        wheel,
        distribution=BASE_DISTRIBUTION,
        mutate=mutate,
    )
    assert _validate_base(wheel, sbom).blockers == (expected_blocker,)


def test_root_only_sbom_cannot_authorize_a_wheel(tmp_path: Path) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)

    def make_root_only(payload: dict[str, object]) -> None:
        packages = payload["packages"]
        assert isinstance(packages, list)
        packages[0]["filesAnalyzed"] = False
        payload.pop("files")

    sbom = _write_sbom(
        tmp_path,
        wheel,
        distribution=BASE_DISTRIBUTION,
        mutate=make_root_only,
    )

    assert _validate_base(wheel, sbom).blockers == ("wheel_sbom_root_files_not_analyzed",)


@pytest.mark.parametrize(
    ("mutation", "expected_blocker"),
    (
        ("missing_member", "wheel_sbom_file_inventory_member_set_mismatch"),
        ("wrong_checksum", "wheel_sbom_file_checksum_mismatch"),
        ("missing_contains", "wheel_sbom_contains_binding_mismatch"),
    ),
)
def test_sbom_file_hash_and_contains_closure_is_exact(
    tmp_path: Path,
    mutation: str,
    expected_blocker: str,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)

    def mutate(payload: dict[str, object]) -> None:
        files = payload["files"]
        relationships = payload["relationships"]
        assert isinstance(files, list)
        assert isinstance(relationships, list)
        if mutation == "missing_member":
            files.pop()
        elif mutation == "wrong_checksum":
            files[0]["checksums"] = [{"algorithm": "SHA256", "checksumValue": "0" * 64}]
        else:
            relationships[:] = [row for row in relationships if row.get("relationshipType") != "CONTAINS"]

    sbom = _write_sbom(
        tmp_path,
        wheel,
        distribution=BASE_DISTRIBUTION,
        mutate=mutate,
    )
    assert _validate_base(wheel, sbom).blockers == (expected_blocker,)


@pytest.mark.parametrize("kind", (WheelArtifactKind.BASE, WheelArtifactKind.NATIVE))
def test_unrelated_wheel_payload_is_rejected(
    tmp_path: Path,
    kind: WheelArtifactKind,
) -> None:
    wheel, extension_sha256 = _write_wheel(
        tmp_path,
        kind=kind,
        extra_payloads=(("unrelated_package/payload.py", b"unrelated = True\n"),),
    )
    distribution = BASE_DISTRIBUTION if kind is WheelArtifactKind.BASE else NATIVE_DISTRIBUTION
    sbom = _write_sbom(tmp_path, wheel, distribution=distribution)
    result = (
        _validate_base(wheel, sbom)
        if kind is WheelArtifactKind.BASE
        else _validate_native(wheel, sbom, extension_sha256)
    )
    assert result.blockers == ("wheel_payload_namespace_invalid",)


def test_native_extension_count_hash_and_base_wheel_policy_fail_closed(
    tmp_path: Path,
) -> None:
    missing_extension, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.NATIVE,
        extension_payloads=(("native_loader.py", b"pass\n"),),
    )
    sbom = _write_sbom(tmp_path, missing_extension, distribution=NATIVE_DISTRIBUTION)
    assert _validate_native(missing_extension, sbom, "1" * 64).blockers == ("native_wheel_extension_count_invalid",)

    missing_extension.unlink()
    two_extensions, first_sha = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.NATIVE,
        extension_payloads=(
            ("first.so", b"\x7fELF-first"),
            ("second.so", b"\x7fELF-second"),
        ),
    )
    sbom = _write_sbom(tmp_path, two_extensions, distribution=NATIVE_DISTRIBUTION)
    assert _validate_native(two_extensions, sbom, first_sha).blockers == ("native_wheel_extension_count_invalid",)

    two_extensions.unlink()
    native, extension_sha256 = _write_wheel(tmp_path, kind=WheelArtifactKind.NATIVE)
    sbom = _write_sbom(tmp_path, native, distribution=NATIVE_DISTRIBUTION)
    assert _validate_native(native, sbom, "f" * 64).blockers == ("native_wheel_extension_sha256_mismatch",)
    assert extension_sha256 != "f" * 64

    base_with_extension, _ = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.BASE,
        extension_payloads=(),
    )
    # Add a native member and regenerate RECORD through the native fixture helper is
    # intentionally avoided: this directly tests the base-wheel policy using a
    # structurally valid archive.
    with zipfile.ZipFile(base_with_extension, mode="r") as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    dist_info = "betelgeuze_engine_v2-0.2.0rc5.dist-info"
    record_path = f"{dist_info}/RECORD"
    members.pop(record_path)
    members["betelgeuze_engine_v2/native.so"] = b"\x7fELF-base-cross-wire"
    members[record_path] = _record_bytes(members, record_path)
    with zipfile.ZipFile(base_with_extension, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    sbom = _write_sbom(tmp_path, base_with_extension, distribution=BASE_DISTRIBUTION)
    assert _validate_base(base_with_extension, sbom).blockers == ("base_wheel_native_extension_forbidden",)


def test_archive_and_predeclared_hash_bounds_are_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    assert _validate_base(wheel, sbom, expected_wheel_sha256="0" * 64).blockers == ("wheel_expected_sha256_mismatch",)

    monkeypatch.setattr(module, "MAX_WHEEL_ARCHIVE_BYTES", 8)
    assert _validate_base(wheel, sbom).blockers == ("wheel_size_out_of_bounds",)


def test_same_namespace_payload_must_match_the_external_source_tree(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    source_member = tmp_path / "base-source/betelgeuze_engine_v2/__init__.py"
    source_member.write_bytes(b'__version__ = "trusted-source"\n')

    result = _validate_base(wheel, sbom)

    assert result.blockers == ("wheel_source_member_sha256_mismatch",)
    assert result.valid is False


def test_authority_inputs_are_mandatory_and_never_taken_from_the_sbom(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    license_path = tmp_path / f"{BASE_DISTRIBUTION}.license-determination.json"

    missing_source = validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.BASE,
        expected_distribution=BASE_DISTRIBUTION,
        expected_version=VERSION,
        source_root=None,
        license_determination_path=license_path,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256=hashlib.sha256(license_path.read_bytes()).hexdigest(),
    )
    missing_license = validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.BASE,
        expected_distribution=BASE_DISTRIBUTION,
        expected_version=VERSION,
        source_root=tmp_path / "base-source",
        license_determination_path=None,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256=hashlib.sha256(license_path.read_bytes()).hexdigest(),
    )

    assert missing_source.blockers == ("wheel_source_root_missing",)
    assert missing_license.blockers == ("license_determination_missing",)

    wrong_predeclared_license = validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.BASE,
        expected_distribution=BASE_DISTRIBUTION,
        expected_version=VERSION,
        source_root=tmp_path / "base-source",
        license_determination_path=license_path,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256="0" * 64,
    )
    assert wrong_predeclared_license.blockers == ("license_determination_expected_sha256_mismatch",)


def test_metadata_dependency_ledger_and_depends_on_relationship_are_exact(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    payload = json.loads(sbom.read_text(encoding="utf-8"))
    dependency_names = {row["name"] for row in payload["packages"] if row["SPDXID"].startswith("SPDXRef-PyPI-")}
    dependency_ids = {row["SPDXID"] for row in payload["packages"] if row["SPDXID"].startswith("SPDXRef-PyPI-")}
    depends_on = {
        row["relatedSpdxElement"]
        for row in payload["relationships"]
        if row["spdxElementId"] == "SPDXRef-Package-EngineV2" and row["relationshipType"] == "DEPENDS_ON"
    }

    assert dependency_names == {
        "betelgeuze-engine-v2-native",
        "cryptography",
        "numpy",
        "torch",
    }
    assert depends_on == dependency_ids
    result = _validate_base(wheel, sbom)
    assert result.valid is True
    assert result.dependency_package_count == 4
    assert result.license_review_closed is True

    payload["relationships"] = [
        row
        for row in payload["relationships"]
        if not (row["relationshipType"] == "DEPENDS_ON" and row["relatedSpdxElement"] in dependency_ids)
    ]
    _write_json(sbom, payload)
    assert _validate_base(wheel, sbom).blockers == ("wheel_sbom_relationship_dependency_closure_mismatch",)


def test_license_review_must_be_approved_exact_and_non_noassertion(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    sbom = _write_sbom(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    license_path = tmp_path / f"{BASE_DISTRIBUTION}.license-determination.json"
    ledger = json.loads(license_path.read_text(encoding="utf-8"))
    ledger["review_status"] = "pending"
    _write_json(license_path, ledger)
    assert _validate_base(wheel, sbom).blockers == ("license_determination_review_incomplete",)

    _prepare_authorities(tmp_path, wheel, distribution=BASE_DISTRIBUTION)
    sbom_payload = json.loads(sbom.read_text(encoding="utf-8"))
    sbom_payload["packages"][0]["licenseConcluded"] = "NOASSERTION"
    _write_json(sbom, sbom_payload)
    assert _validate_base(wheel, sbom).blockers == ("wheel_sbom_license_determination_incomplete",)


def test_proprietary_license_ref_requires_exact_extracted_license_text(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    source_root, license_path, _, _ = _prepare_authorities(
        tmp_path,
        wheel,
        distribution=BASE_DISTRIBUTION,
    )
    ledger = json.loads(license_path.read_text(encoding="utf-8"))
    for row in ledger["determinations"]:
        row["license_concluded"] = "LicenseRef-Proprietary-Betelgeuze"
        row["license_declared"] = "LicenseRef-Proprietary-Betelgeuze"
    ledger["extracted_licenses"] = [
        {
            "license_id": "LicenseRef-Proprietary-Betelgeuze",
            "name": "Betelgeuze Proprietary License",
            "extracted_text": "No permission is granted without a written agreement.",
            "see_alsos": ["https://example.invalid/legal/betelgeuze"],
        }
    ]
    _write_json(license_path, ledger)
    payload = build_sbom(
        wheel,
        source_root=source_root,
        license_determination=license_path,
        source_receipt_sha256="c" * 64,
    )
    sbom = tmp_path / f"{BASE_DISTRIBUTION}.spdx.json"
    _write_json(sbom, payload)

    assert payload["hasExtractedLicensingInfos"] == [
        {
            "licenseId": "LicenseRef-Proprietary-Betelgeuze",
            "name": "Betelgeuze Proprietary License",
            "extractedText": "No permission is granted without a written agreement.",
            "seeAlsos": ["https://example.invalid/legal/betelgeuze"],
        }
    ]
    assert _validate_base(wheel, sbom).valid is True

    ledger["extracted_licenses"] = []
    _write_json(license_path, ledger)
    assert _validate_base(wheel, sbom).blockers == ("license_determination_extracted_license_scope_mismatch",)


def test_native_cargo_ledger_and_build_provenance_are_exact(
    tmp_path: Path,
) -> None:
    wheel, extension_sha256 = _write_wheel(
        tmp_path,
        kind=WheelArtifactKind.NATIVE,
    )
    sbom = _write_sbom(tmp_path, wheel, distribution=NATIVE_DISTRIBUTION)
    payload = json.loads(sbom.read_text(encoding="utf-8"))
    cargo_packages = [row for row in payload["packages"] if row["SPDXID"].startswith("SPDXRef-Cargo-")]
    assert [(row["name"], row["versionInfo"]) for row in cargo_packages] == [("fixture-dep", "1.2.3")]
    assert cargo_packages[0]["checksums"] == [{"algorithm": "SHA256", "checksumValue": "a" * 64}]
    result = _validate_native(wheel, sbom, extension_sha256)
    assert result.valid is True
    assert result.native_build_provenance_sha256

    provenance_path = tmp_path / f"{NATIVE_DISTRIBUTION}.native-build-provenance.json"
    predeclared_provenance_sha256 = hashlib.sha256(provenance_path.read_bytes()).hexdigest()
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["builder_version"] = "fixture-2"
    _write_json(provenance_path, provenance)
    license_path = tmp_path / f"{NATIVE_DISTRIBUTION}.license-determination.json"
    result = validate_wheel_artifact(
        wheel,
        sbom,
        artifact_kind=WheelArtifactKind.NATIVE,
        expected_distribution=NATIVE_DISTRIBUTION,
        expected_version=VERSION,
        expected_extension_sha256=extension_sha256,
        source_root=tmp_path / "native-source",
        license_determination_path=license_path,
        cargo_lock_path=tmp_path / "native-source/Cargo.lock",
        native_build_provenance_path=provenance_path,
        expected_source_receipt_sha256="c" * 64,
        expected_license_determination_sha256=hashlib.sha256(license_path.read_bytes()).hexdigest(),
        expected_native_build_provenance_sha256=predeclared_provenance_sha256,
    )
    assert result.blockers == ("native_build_provenance_expected_sha256_mismatch",)


def test_sbom_builder_refuses_missing_legal_and_source_authorities(
    tmp_path: Path,
) -> None:
    wheel, _ = _write_wheel(tmp_path, kind=WheelArtifactKind.BASE)
    with pytest.raises(RuntimeError, match="source_root is required"):
        build_sbom(wheel)
    with pytest.raises(RuntimeError, match="license_determination is required"):
        build_sbom(
            wheel,
            source_root=tmp_path,
            source_receipt_sha256="c" * 64,
        )
