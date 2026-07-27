"""Canonical-input command line entry point for the Engine v2 research surface.

The CLI deliberately accepts only canonical Engine v2 molecular documents and a
canonical typed pocket document. It performs no PDB/SDF parsing, protonation,
tautomer selection, atom typing, charge generation, parameter assignment, or
pocket prediction.

The ``dock-canonical`` command connects the existing contracts:

canonical receptor/ligand bytes
    -> typed pocket
    -> element-aware authenticated docking authority
    -> deterministic Haar pocket placement
    -> uncalibrated interpretable scorer
    -> failure-complete retained score-term evidence

The scorer source digest is observed from the installed package resource after
module import. It is recorded explicitly as non-attested execution provenance;
it is not equivalent to the hardened pre-import source-snapshot lane.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Mapping, Sequence

import torch

from .contracts import DISTRIBUTION_VERSION, ENGINE_API_VERSION
from .docking import (
    DockingBudget,
    DockingScope,
    InterpretablePoseScorerV0,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    run_authenticated_interpretable_pocket_search,
)
from .molecular import all_atom_system_from_canonical_json


CLI_POCKET_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_pocket_input/1.0.0"
)
CLI_DOCKING_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_docking_result/1.0.0"
)
CLI_FAILURE_SCHEMA_ID = "betelgeuze.engine_v2_cli_failure/1.0.0"
CLI_COMMAND_ID = "betelgeuze-engine-v2/dock-canonical/1.0.0"
SCORER_SOURCE_BINDING_MODE = (
    "observed_installed_package_resource_after_import_not_preimport_attested"
)
MAX_CLI_INPUT_BYTES = 128 * 1024 * 1024
MAX_CLI_POCKET_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024


class EngineV2CliError(RuntimeError):
    """The canonical CLI contract failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError(
            "CLI output is not canonical JSON"
        ) from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _read_bounded(path: Path, *, maximum: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise EngineV2CliError(
                f"{name} must be a single-link regular file"
            )
        if not 0 < before.st_size <= maximum:
            raise EngineV2CliError(f"{name} exceeds its byte bound")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise EngineV2CliError(f"{name} exceeds its byte bound")
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or total != after.st_size:
            raise EngineV2CliError(
                f"{name} changed while it was being read"
            )
        return b"".join(chunks)
    except EngineV2CliError:
        raise
    except OSError as exc:
        raise EngineV2CliError(f"{name} could not be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EngineV2CliError(
                f"pocket document contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _load_canonical_pocket_document(raw: bytes) -> Mapping[str, object]:
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise EngineV2CliError("pocket document has non-canonical line endings")
    try:
        text = canonical.decode("ascii")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineV2CliError("pocket document is invalid JSON") from exc
    if not isinstance(document, dict):
        raise EngineV2CliError("pocket document must be a JSON object")
    if _canonical_bytes(document) != canonical:
        raise EngineV2CliError("pocket document bytes are not canonical")
    return document


def _exact_keys(
    document: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
) -> None:
    keys = set(document)
    missing = required - keys
    unexpected = keys - required - optional
    if missing:
        raise EngineV2CliError(
            "pocket document is missing fields: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise EngineV2CliError(
            "pocket document has unexpected fields: "
            + ", ".join(sorted(unexpected))
        )


def _pocket_from_document(document: Mapping[str, object]) -> PocketDefinition:
    _exact_keys(
        document,
        required={
            "schema_id",
            "scope",
            "method_id",
            "method_version",
            "coordinate_frame_id",
            "center_angstrom",
            "radius_angstrom",
            "source_artifact_sha256",
            "implementation_source_sha256",
        },
        optional={"metadata"},
    )
    if document["schema_id"] != CLI_POCKET_INPUT_SCHEMA_ID:
        raise EngineV2CliError("pocket document schema is unsupported")
    center = document["center_angstrom"]
    if (
        not isinstance(center, list)
        or len(center) != 3
        or any(isinstance(value, bool) for value in center)
    ):
        raise EngineV2CliError(
            "pocket center_angstrom must contain exactly three numbers"
        )
    try:
        center_tensor = torch.tensor(center, dtype=torch.float64)
        radius = float(document["radius_angstrom"])
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket geometry is invalid") from exc
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        raise EngineV2CliError("pocket metadata must be a JSON object")
    try:
        return PocketDefinition(
            scope=DockingScope(str(document["scope"])),
            method_id=str(document["method_id"]),
            method_version=str(document["method_version"]),
            coordinate_frame_id=str(document["coordinate_frame_id"]),
            center=center_tensor,
            radius_angstrom=radius,
            source_artifact_sha256=str(
                document["source_artifact_sha256"]
            ),
            implementation_source_sha256=str(
                document["implementation_source_sha256"]
            ),
            metadata=metadata,
        )
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket contract is invalid") from exc


def _installed_scorer_source_sha256() -> str:
    try:
        resource = resources.files(
            "betelgeuze_engine_v2.docking"
        ).joinpath("interpretable_scorer.py")
        payload = resource.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise EngineV2CliError(
            "installed scorer source resource is unavailable"
        ) from exc
    if not payload:
        raise EngineV2CliError("installed scorer source resource is empty")
    return _sha256_bytes(payload)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("CLI output write made no progress")
        view = view[written:]


def _write_output(
    document: Mapping[str, object],
    path: Path,
    *,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if not overwrite:
            raise EngineV2CliError(
                "output already exists; use --overwrite to replace it"
            )
        if not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1:
            raise EngineV2CliError(
                "output must be absent or a single-link regular file"
            )
    temporary = path.with_name(
        f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(temporary, flags, 0o600)
        _write_all(descriptor, _canonical_bytes(document) + b"\n")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_CLOEXEC", 0)
        directory = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise EngineV2CliError("CLI output could not be written durably") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def run_canonical_docking(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    candidate_count: int,
    top_k: int,
    max_torsions: int,
    translation_radius_angstrom: float,
    seed: int,
    receptor_margin_angstrom: float,
) -> dict[str, object]:
    receptor_bytes = _read_bounded(
        receptor_path,
        maximum=MAX_CLI_INPUT_BYTES,
        name="receptor canonical document",
    )
    ligand_bytes = _read_bounded(
        ligand_path,
        maximum=MAX_CLI_INPUT_BYTES,
        name="ligand canonical document",
    )
    pocket_bytes = _read_bounded(
        pocket_path,
        maximum=MAX_CLI_POCKET_BYTES,
        name="pocket canonical document",
    )
    try:
        receptor = all_atom_system_from_canonical_json(receptor_bytes)
        ligand = all_atom_system_from_canonical_json(ligand_bytes)
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError(
            "canonical molecular document is invalid"
        ) from exc
    pocket_document = _load_canonical_pocket_document(pocket_bytes)
    pocket = _pocket_from_document(pocket_document)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=float(receptor_margin_angstrom),
    )
    source_sha = _installed_scorer_source_sha256()
    scorer = InterpretablePoseScorerV0(
        authority,
        implementation_source_sha256=source_sha,
    )
    budget = DockingBudget(
        candidate_count=candidate_count,
        top_k=top_k,
        max_torsions=max_torsions,
        translation_radius_angstrom=translation_radius_angstrom,
        seed=seed,
    )
    result = run_authenticated_interpretable_pocket_search(
        authority,
        budget,
        scorer,
    )
    projection: dict[str, object] = {
        "schema_id": CLI_DOCKING_RESULT_SCHEMA_ID,
        "command_id": CLI_COMMAND_ID,
        "engine_api_version": ENGINE_API_VERSION,
        "distribution_version": DISTRIBUTION_VERSION,
        "receptor_artifact_sha256": _sha256_bytes(receptor_bytes),
        "ligand_artifact_sha256": _sha256_bytes(ligand_bytes),
        "pocket_artifact_sha256": _sha256_bytes(pocket_bytes),
        "pocket_definition_sha256": pocket.fingerprint_sha256,
        "authenticated_input_receipt_sha256": authority.input_receipt_sha256,
        "scorer_source_sha256": source_sha,
        "scorer_source_binding_mode": SCORER_SOURCE_BINDING_MODE,
        "scorer_source_preimport_attested": False,
        "result_receipt_sha256": result.receipt_sha256,
        "candidate_count": len(result.rows),
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "network_fetch_performed": False,
        "chemistry_inference_performed": False,
        "pocket_prediction_performed": False,
        "calibrated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "result": result.to_dict(),
    }
    projection["document_sha256"] = _sha256_document(projection)
    return projection


def _failure_document(exc: BaseException) -> dict[str, object]:
    private = (
        f"{exc.__class__.__module__}.{exc.__class__.__qualname__}: {exc}"
    ).encode("utf-8", errors="replace")
    return {
        "schema_id": CLI_FAILURE_SCHEMA_ID,
        "status": "failure",
        "error_code": "engine_v2_cli_failed",
        "public_message": "Engine v2 canonical docking command failed",
        "private_error_sha256": _sha256_bytes(private),
        "private_error_byte_length": len(private),
        "claim_safe": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2",
        description=(
            "Fail-closed Engine v2 canonical-input research commands."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    dock = subparsers.add_parser(
        "dock-canonical",
        help=(
            "Run authenticated known-pocket docking from canonical Engine v2 inputs."
        ),
    )
    dock.add_argument("--receptor", type=Path, required=True)
    dock.add_argument("--ligand", type=Path, required=True)
    dock.add_argument("--pocket", type=Path, required=True)
    dock.add_argument("--output", type=Path)
    dock.add_argument("--overwrite", action="store_true")
    dock.add_argument("--candidate-count", type=int, default=64)
    dock.add_argument("--top-k", type=int, default=10)
    dock.add_argument("--max-torsions", type=int, default=32)
    dock.add_argument("--translation-radius-angstrom", type=float, default=4.0)
    dock.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    dock.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command != "dock-canonical":
            raise EngineV2CliError("unsupported command")
        document = run_canonical_docking(
            receptor_path=arguments.receptor,
            ligand_path=arguments.ligand,
            pocket_path=arguments.pocket,
            candidate_count=arguments.candidate_count,
            top_k=arguments.top_k,
            max_torsions=arguments.max_torsions,
            translation_radius_angstrom=(
                arguments.translation_radius_angstrom
            ),
            seed=arguments.seed,
            receptor_margin_angstrom=(
                arguments.receptor_margin_angstrom
            ),
        )
        if arguments.output is None:
            sys.stdout.buffer.write(_canonical_bytes(document) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _write_output(
                document,
                arguments.output,
                overwrite=bool(arguments.overwrite),
            )
        return 0
    except Exception as exc:
        failure = _failure_document(exc)
        sys.stderr.buffer.write(_canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CLI_COMMAND_ID",
    "CLI_DOCKING_RESULT_SCHEMA_ID",
    "CLI_FAILURE_SCHEMA_ID",
    "CLI_POCKET_INPUT_SCHEMA_ID",
    "EngineV2CliError",
    "SCORER_SOURCE_BINDING_MODE",
    "main",
    "run_canonical_docking",
]
