"""Frozen, result-blind 128-case internal redocking holdout contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Mapping, Sequence
import zipfile

from .public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256,
)


FRESH_REDOCKING_HOLDOUT_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_holdout_manifest/1.0.0"
)
FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256 = (
    "459303a54cb1e8ebaf2bfa4320ad2287536d0e20a916fe5d2bac60edbdffdfba"
)
FRESH_REDOCKING_HOLDOUT_CASE_COUNT = 128
FRESH_REDOCKING_HOLDOUT_SEED_BASE = 2_026_073_000
FRESH_REDOCKING_ARCHIVE_CASE_COUNT = 428
_ROLES = ("receptor", "reference", "native", "seed")


class FreshRedockingHoldoutError(ValueError):
    """The frozen fresh-holdout contract was violated."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise FreshRedockingHoldoutError("manifest is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise FreshRedockingHoldoutError(f"{field} is not a SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class FrozenFreshRedockingCase:
    case_id: str
    seed: int
    archive_members: Mapping[str, str]
    artifact_sha256s: Mapping[str, str]
    profile: Mapping[str, object]
    receipt_sha256: str

    def __post_init__(self) -> None:
        if self.case_id not in FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS:
            raise FreshRedockingHoldoutError("case is outside the fresh holdout")
        index = FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS.index(self.case_id)
        if self.seed != FRESH_REDOCKING_HOLDOUT_SEED_BASE + index:
            raise FreshRedockingHoldoutError("fresh case seed drifted")
        members = dict(self.archive_members)
        artifacts = dict(self.artifact_sha256s)
        if set(members) != set(_ROLES) or set(artifacts) != set(_ROLES):
            raise FreshRedockingHoldoutError("fresh case roles are incomplete")
        suffixes = {
            "receptor": "protein.pdb",
            "reference": "ligands.sdf",
            "native": "ligand.sdf",
            "seed": "ligand_start_conf.sdf",
        }
        for role in _ROLES:
            expected = (
                f"posebusters_benchmark_set/{self.case_id}/"
                f"{self.case_id}_{suffixes[role]}"
            )
            if members[role] != expected:
                raise FreshRedockingHoldoutError("fresh archive member is cross-wired")
            _digest(artifacts[role], field=f"{role}_artifact_sha256")
        profile = dict(self.profile)
        if set(profile) != {
            "heavy_atom_count",
            "rotatable_bond_count_strict",
            "ring_count",
            "size_subgroup",
            "rotor_subgroup",
            "ring_subgroup",
        }:
            raise FreshRedockingHoldoutError("fresh ligand profile is incomplete")
        if any(
            type(profile[field]) is not int or profile[field] < 0
            for field in ("heavy_atom_count", "rotatable_bond_count_strict", "ring_count")
        ):
            raise FreshRedockingHoldoutError("fresh ligand profile count is invalid")
        projection = {
            "case_id": self.case_id,
            "seed": self.seed,
            "archive_members": members,
            "artifact_sha256s": artifacts,
            "profile": profile,
        }
        if self.receipt_sha256 != _sha256(projection):
            raise FreshRedockingHoldoutError("fresh case receipt drifted")
        object.__setattr__(self, "archive_members", MappingProxyType(members))
        object.__setattr__(self, "artifact_sha256s", MappingProxyType(artifacts))
        object.__setattr__(self, "profile", MappingProxyType(profile))

    @property
    def input_artifact_sha256s_by_role(self) -> dict[str, str]:
        return dict(self.artifact_sha256s)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "seed": self.seed,
            "archive_members": dict(self.archive_members),
            "artifact_sha256s": dict(self.artifact_sha256s),
            "profile": dict(self.profile),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class FrozenFreshRedockingHoldout:
    cases: tuple[FrozenFreshRedockingCase, ...]
    manifest_sha256: str

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.cases)

    def case(self, case_id: str) -> FrozenFreshRedockingCase:
        try:
            return next(case for case in self.cases if case.case_id == case_id)
        except StopIteration as exc:
            raise FreshRedockingHoldoutError("case is outside the fresh holdout") from exc


class VerifiedFreshRedockingArchive:
    """Pinned archive reader limited to the frozen fresh-holdout manifest."""

    __slots__ = ("_archive", "_handle", "_holdout", "_identity")

    def __init__(self) -> None:
        raise TypeError("use VerifiedFreshRedockingArchive.open")

    @classmethod
    def open(
        cls, path: Path, manifest_path: Path
    ) -> "VerifiedFreshRedockingArchive":
        holdout = load_fresh_redocking_holdout_manifest(manifest_path)
        handle = path.resolve().open("rb")
        try:
            status = os.fstat(handle.fileno())
            if not stat.S_ISREG(status.st_mode):
                raise FreshRedockingHoldoutError("source archive is not a regular file")
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != PUBLIC_REDOCKING_ARCHIVE_SHA256:
                raise FreshRedockingHoldoutError("source archive identity drifted")
            handle.seek(0)
            archive = zipfile.ZipFile(handle)
        except Exception:
            handle.close()
            raise
        instance = object.__new__(cls)
        instance._handle = handle
        instance._archive = archive
        instance._holdout = holdout
        instance._identity = (
            status.st_dev,
            status.st_ino,
            status.st_size,
            status.st_mtime_ns,
            status.st_ctime_ns,
        )
        return instance

    def _require_unchanged(self) -> None:
        status = os.fstat(self._handle.fileno())
        identity = (
            status.st_dev,
            status.st_ino,
            status.st_size,
            status.st_mtime_ns,
            status.st_ctime_ns,
        )
        if identity != self._identity:
            raise FreshRedockingHoldoutError("source archive changed while open")

    def verified_case(
        self, case_id: str
    ) -> tuple[FrozenFreshRedockingCase, dict[str, bytes]]:
        self._require_unchanged()
        case = self._holdout.case(case_id)
        payloads = verified_fresh_case_payloads(self._archive, case)
        self._require_unchanged()
        return case, payloads

    def close(self) -> None:
        self._archive.close()
        self._handle.close()

    def __enter__(self) -> "VerifiedFreshRedockingArchive":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def require_fresh_redocking_holdout_manifest(
    payload: object,
) -> FrozenFreshRedockingHoldout:
    if not isinstance(payload, Mapping):
        raise FreshRedockingHoldoutError("fresh holdout manifest must be a mapping")
    manifest = dict(payload)
    self_hash = manifest.pop("manifest_sha256", None)
    if self_hash != _sha256(manifest):
        raise FreshRedockingHoldoutError("fresh holdout manifest self-hash mismatch")
    if self_hash != FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256:
        raise FreshRedockingHoldoutError("fresh holdout manifest identity drifted")
    required = {
        "schema_id": FRESH_REDOCKING_HOLDOUT_MANIFEST_SCHEMA_ID,
        "claim_role": "internal_provisional_blind_only",
        "result_values_inspected_before_freeze": False,
        "external_independent_review_required_before_public_claim": True,
        "source_archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_archive_case_count": FRESH_REDOCKING_ARCHIVE_CASE_COUNT,
        "historical_development_case_count": len(FROZEN_PUBLIC_REDOCKING_CASE_IDS),
        "case_count": FRESH_REDOCKING_HOLDOUT_CASE_COUNT,
        "case_ids_sha256": PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256,
        "seed_base": FRESH_REDOCKING_HOLDOUT_SEED_BASE,
    }
    for field, expected in required.items():
        if manifest.get(field) != expected:
            raise FreshRedockingHoldoutError(f"fresh holdout {field} drifted")
    rows = manifest.get("cases")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise FreshRedockingHoldoutError("fresh holdout cases are missing")
    cases = tuple(FrozenFreshRedockingCase(**dict(row)) for row in rows)
    if tuple(case.case_id for case in cases) != (
        FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS
    ):
        raise FreshRedockingHoldoutError("fresh holdout case ordering drifted")
    return FrozenFreshRedockingHoldout(cases=cases, manifest_sha256=self_hash)


def load_fresh_redocking_holdout_manifest(path: Path) -> FrozenFreshRedockingHoldout:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FreshRedockingHoldoutError("fresh holdout manifest is unreadable") from exc
    return require_fresh_redocking_holdout_manifest(payload)


def verified_fresh_case_payloads(
    archive: zipfile.ZipFile,
    case: FrozenFreshRedockingCase,
) -> dict[str, bytes]:
    """Read one case and verify every byte against the pre-execution manifest."""

    payloads: dict[str, bytes] = {}
    for role in _ROLES:
        member = case.archive_members[role]
        try:
            info = archive.getinfo(member)
            payload = archive.read(info)
        except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise FreshRedockingHoldoutError(
                f"fresh archive member cannot be read: {member}"
            ) from exc
        if info.is_dir() or len(payload) != info.file_size:
            raise FreshRedockingHoldoutError("fresh archive member size is invalid")
        if hashlib.sha256(payload).hexdigest() != case.artifact_sha256s[role]:
            raise FreshRedockingHoldoutError("fresh archive member hash drifted")
        payloads[role] = payload
    return payloads


__all__ = [
    "FRESH_REDOCKING_ARCHIVE_CASE_COUNT",
    "FRESH_REDOCKING_HOLDOUT_CASE_COUNT",
    "FRESH_REDOCKING_HOLDOUT_MANIFEST_SCHEMA_ID",
    "FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256",
    "FRESH_REDOCKING_HOLDOUT_SEED_BASE",
    "FreshRedockingHoldoutError",
    "FrozenFreshRedockingCase",
    "FrozenFreshRedockingHoldout",
    "VerifiedFreshRedockingArchive",
    "load_fresh_redocking_holdout_manifest",
    "require_fresh_redocking_holdout_manifest",
    "verified_fresh_case_payloads",
]
