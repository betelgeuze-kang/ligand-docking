#!/usr/bin/env python3
"""Freeze result-blind input identities for the fresh 128-case holdout.

This tool reads only the already pinned PoseBusters input archive.  It has no
result-table argument and deliberately cannot consume benchmark outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256,
)


SCHEMA_ID = "betelgeuze.engine_v2_fresh_redocking_holdout_manifest/1.0.0"
SEED_BASE = 2_026_073_000
EXPECTED_ARCHIVE_CASE_COUNT = 428
_ROLES = (
    ("receptor", "protein.pdb"),
    ("reference", "ligands.sdf"),
    ("native", "ligand.sdf"),
    ("seed", "ligand_start_conf.sdf"),
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_ids_from_archive(archive: zipfile.ZipFile) -> tuple[str, ...]:
    suffix = "_ligand_start_conf.sdf"
    case_ids = {
        Path(info.filename).parent.name
        for info in archive.infolist()
        if info.filename.startswith("posebusters_benchmark_set/")
        and info.filename.endswith(suffix)
        and not info.is_dir()
    }
    return tuple(sorted(case_ids))


def _ligand_profile(native_payload: bytes, *, case_id: str) -> dict[str, object]:
    supplier = Chem.ForwardSDMolSupplier(
        io.BytesIO(native_payload), sanitize=True, removeHs=False
    )
    molecule = next(supplier, None)
    if molecule is None:
        raise ValueError(f"native ligand cannot be parsed: {case_id}")
    heavy_atoms = molecule.GetNumHeavyAtoms()
    rotors = int(rdMolDescriptors.CalcNumRotatableBonds(molecule, True))
    rings = int(rdMolDescriptors.CalcNumRings(molecule))
    return {
        "heavy_atom_count": heavy_atoms,
        "rotatable_bond_count_strict": rotors,
        "ring_count": rings,
        "size_subgroup": (
            "size_small_1_20"
            if heavy_atoms <= 20
            else "size_medium_21_40"
            if heavy_atoms <= 40
            else "size_large_41_plus"
        ),
        "rotor_subgroup": (
            "rotor_rigid_0"
            if rotors == 0
            else "rotor_low_1_4"
            if rotors <= 4
            else "rotor_flexible_5_plus"
        ),
        "ring_subgroup": (
            "ring_acyclic_0"
            if rings == 0
            else "ring_single_1"
            if rings == 1
            else "ring_multi_2_plus"
        ),
    }


def build_manifest(archive_path: Path) -> dict[str, object]:
    if _sha256_path(archive_path) != PUBLIC_REDOCKING_ARCHIVE_SHA256:
        raise ValueError("source archive SHA-256 does not match the frozen authority")
    with zipfile.ZipFile(archive_path) as archive:
        archive_case_ids = _case_ids_from_archive(archive)
        if len(archive_case_ids) != EXPECTED_ARCHIVE_CASE_COUNT:
            raise ValueError("source archive case denominator drifted")
        fresh_ids = tuple(
            case_id
            for case_id in archive_case_ids
            if case_id not in FROZEN_PUBLIC_REDOCKING_CASE_IDS
        )
        if fresh_ids != FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS:
            raise ValueError("fresh holdout selection drifted")
        if _sha256(list(fresh_ids)) != PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256:
            raise ValueError("fresh holdout identity hash drifted")
        cases: list[dict[str, object]] = []
        for index, case_id in enumerate(fresh_ids):
            members: dict[str, str] = {}
            artifact_sha256s: dict[str, str] = {}
            payloads: dict[str, bytes] = {}
            for role, filename in _ROLES:
                member = f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
                info = archive.getinfo(member)
                if info.is_dir() or not 1 <= info.file_size <= 64 * 1024 * 1024:
                    raise ValueError(f"invalid archive member: {member}")
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise ValueError(f"truncated archive member: {member}")
                members[role] = member
                payloads[role] = payload
                artifact_sha256s[role] = hashlib.sha256(payload).hexdigest()
            case = {
                "case_id": case_id,
                "seed": SEED_BASE + index,
                "archive_members": members,
                "artifact_sha256s": artifact_sha256s,
                "profile": _ligand_profile(payloads["native"], case_id=case_id),
            }
            case["receipt_sha256"] = _sha256(case)
            cases.append(case)
    manifest: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "claim_role": "internal_provisional_blind_only",
        "result_values_inspected_before_freeze": False,
        "external_independent_review_required_before_public_claim": True,
        "source_archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_archive_case_count": EXPECTED_ARCHIVE_CASE_COUNT,
        "historical_development_case_count": len(FROZEN_PUBLIC_REDOCKING_CASE_IDS),
        "historical_development_case_ids_sha256": _sha256(
            list(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
        ),
        "selection_rule": "sorted_posebusters_428_archive_case_ids_minus_historical_300",
        "case_count": len(cases),
        "case_ids_sha256": PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256,
        "seed_base": SEED_BASE,
        "profile_method": "rdkit-2022.09.5-native-ligand-input-only/1.0.0",
        "cases": cases,
    }
    manifest["manifest_sha256"] = _sha256(manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = build_manifest(arguments.archive.resolve())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(manifest) + b"\n")
    print(manifest["manifest_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
