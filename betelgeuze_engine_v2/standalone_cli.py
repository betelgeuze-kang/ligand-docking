"""Claim-blocked standalone CPU CLI over :class:`DockingPipeline`.

Every molecular input is an already-prepared canonical Engine v2 document.
These commands perform no chemistry inference, network access, external
reservation, benchmark execution, or product action.
"""

from __future__ import annotations

import argparse
from importlib import resources
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Sequence

import torch

from .cli import (
    CLI_POCKET_INPUT_SCHEMA_ID,
    MAX_CLI_INPUT_BYTES,
    MAX_CLI_POCKET_BYTES,
    EngineV2CliError,
    _canonical_bytes,
    _failure_document,
    _load_canonical_pocket_document,
    _pocket_from_document,
    _read_bounded,
    _reject_duplicate_pairs,
    _sha256_bytes,
    _sha256_document,
    _write_output,
)
from .docking import DockingScope, PocketDefinition
from .docking.pipeline import (
    EXTERNAL_AUTHORITY_BLOCKERS,
    PIPELINE_RESULT_SCHEMA_ID,
    DockingPipeline,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
)
from .molecular import (
    AllAtomSystem,
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    canonical_system_sha256,
    require_valid_all_atom_system,
)
from .reference_pocket import derive_reference_pocket_from_path


STANDALONE_CLI_ID = "betelgeuze-dock/1.0.0"
LIGAND_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_ligand_manifest/1.0.0"
)
PIPELINE_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_pipeline_verification/1.0.0"
)
PIPELINE_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_standalone_pipeline_report/1.0.0"
)
EXPLICIT_POCKET_METHOD_ID = "explicit-spherical-known-pocket"
EXPLICIT_POCKET_METHOD_VERSION = "1.0.0"


class StandaloneDockCliError(EngineV2CliError):
    """The standalone CLI failed closed."""


def _installed_source_sha256() -> str:
    try:
        payload = resources.files("betelgeuze_engine_v2").joinpath(
            "standalone_cli.py"
        ).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise StandaloneDockCliError(
            "installed standalone CLI source is unavailable"
        ) from exc
    if not payload:
        raise StandaloneDockCliError("installed standalone CLI source is empty")
    return _sha256_bytes(payload)


def _canonical_system_from_path(path: Path, *, role: str) -> tuple[AllAtomSystem, bytes]:
    raw = _read_bounded(path, maximum=MAX_CLI_INPUT_BYTES, name=f"{role} document")
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise StandaloneDockCliError(f"{role} document has non-canonical line endings")
    try:
        system = all_atom_system_from_canonical_json(canonical)
        require_valid_all_atom_system(system)
    except (TypeError, ValueError) as exc:
        raise StandaloneDockCliError(f"{role} canonical system is invalid") from exc
    expected = canonical_system_json_bytes(system)
    if expected != canonical:
        raise StandaloneDockCliError(f"{role} document bytes are not canonical")
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise StandaloneDockCliError(f"{role} must use CPU float64 coordinates")
    if any(atom.partial_charge_e is None for atom in system.atoms):
        raise StandaloneDockCliError(f"{role} lacks explicit partial charges")
    return system, expected


def _write_canonical_system(payload: bytes, output: Path, *, overwrite: bool) -> None:
    document = json.loads(payload.decode("ascii"), object_pairs_hook=_reject_duplicate_pairs)
    if not isinstance(document, dict):
        raise StandaloneDockCliError("canonical system document is not an object")
    _write_output(document, output, overwrite=overwrite)


def prepare_receptor(
    source: Path,
    output: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    system, canonical = _canonical_system_from_path(source, role="receptor")
    _write_canonical_system(canonical, output, overwrite=overwrite)
    return {
        "system_sha256": canonical_system_sha256(system),
        "output": str(output),
        "chemistry_inference_performed": False,
        "network_fetch_performed": False,
    }


def prepare_ligands(
    sources: Sequence[Path],
    output_directory: Path,
    manifest_path: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    if not sources:
        raise StandaloneDockCliError("at least one ligand input is required")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in sources:
        system, canonical = _canonical_system_from_path(source, role="ligand")
        system_sha = canonical_system_sha256(system)
        if system_sha in seen:
            raise StandaloneDockCliError("ligand system identities must be unique")
        seen.add(system_sha)
        filename = f"{system_sha}.json"
        _write_canonical_system(
            canonical,
            output_directory / filename,
            overwrite=overwrite,
        )
        rows.append(
            {
                "system_sha256": system_sha,
                "canonical_file": filename,
                "atom_count": system.atom_count,
                "model_count": system.model_count,
            }
        )
    rows.sort(key=lambda row: str(row["system_sha256"]))
    projection: dict[str, object] = {
        "schema_id": LIGAND_MANIFEST_SCHEMA_ID,
        "systems": rows,
        "system_count": len(rows),
        "chemistry_inference_performed": False,
        "network_fetch_performed": False,
        "claim_safe": False,
    }
    document = {**projection, "receipt_sha256": _sha256_document(projection)}
    _write_output(document, manifest_path, overwrite=overwrite)
    return document


def _finite_vector3(values: Sequence[float]) -> torch.Tensor:
    if len(values) != 3:
        raise StandaloneDockCliError("pocket center requires exactly three values")
    center = torch.tensor(values, dtype=torch.float64)
    if not bool(torch.isfinite(center).all().item()):
        raise StandaloneDockCliError("pocket center must be finite")
    return center


def define_explicit_pocket(
    *,
    center_angstrom: Sequence[float],
    radius_angstrom: float,
    coordinate_frame_id: str,
    source_artifact: Path,
) -> dict[str, object]:
    source = _read_bounded(
        source_artifact,
        maximum=MAX_CLI_INPUT_BYTES,
        name="pocket source artifact",
    )
    radius = float(radius_angstrom)
    if not math.isfinite(radius) or not 0.0 < radius <= 100.0:
        raise StandaloneDockCliError("pocket radius is outside (0,100]")
    implementation_sha = _installed_source_sha256()
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id=EXPLICIT_POCKET_METHOD_ID,
        method_version=EXPLICIT_POCKET_METHOD_VERSION,
        coordinate_frame_id=coordinate_frame_id,
        center=_finite_vector3(center_angstrom),
        radius_angstrom=radius,
        source_artifact_sha256=_sha256_bytes(source),
        implementation_source_sha256=implementation_sha,
        metadata={
            "operator_supplied_geometry": True,
            "pocket_prediction_performed": False,
            "implementation_source_preimport_attested": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )
    return {
        "schema_id": CLI_POCKET_INPUT_SCHEMA_ID,
        "scope": pocket.scope.value,
        "method_id": pocket.method_id,
        "method_version": pocket.method_version,
        "coordinate_frame_id": pocket.coordinate_frame_id,
        "center_angstrom": [float(value) for value in pocket.center.tolist()],
        "radius_angstrom": pocket.radius_angstrom,
        "source_artifact_sha256": pocket.source_artifact_sha256,
        "implementation_source_sha256": pocket.implementation_source_sha256,
        "metadata": dict(pocket.metadata),
    }


def define_pocket(arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.reference_ligand is not None:
        if arguments.radius is not None or arguments.source_artifact is not None:
            raise StandaloneDockCliError(
                "reference-ligand pockets do not accept explicit radius/source"
            )
        return derive_reference_pocket_from_path(
            arguments.reference_ligand,
            coordinate_frame_id=arguments.coordinate_frame_id,
            model_index=arguments.model_index,
            padding_angstrom=arguments.padding_angstrom,
            minimum_radius_angstrom=arguments.minimum_radius_angstrom,
        )
    if arguments.center is None or arguments.radius is None or arguments.source_artifact is None:
        raise StandaloneDockCliError(
            "explicit pockets require --center, --radius, and --source-artifact"
        )
    return define_explicit_pocket(
        center_angstrom=arguments.center,
        radius_angstrom=arguments.radius,
        coordinate_frame_id=arguments.coordinate_frame_id,
        source_artifact=arguments.source_artifact,
    )


def dock(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    seed: int,
    synthetic_candidate_count: int | None = None,
    synthetic_top_k: int = 2,
    synthetic_acknowledged: bool = False,
) -> dict[str, object]:
    receptor, _ = _canonical_system_from_path(receptor_path, role="receptor")
    ligand, _ = _canonical_system_from_path(ligand_path, role="ligand")
    pocket_raw = _read_bounded(
        pocket_path,
        maximum=MAX_CLI_POCKET_BYTES,
        name="pocket document",
    )
    pocket = _pocket_from_document(_load_canonical_pocket_document(pocket_raw))
    if synthetic_candidate_count is None:
        if synthetic_acknowledged:
            raise StandaloneDockCliError(
                "--test-only-synthetic requires --synthetic-test-candidates"
            )
        profile = DockingPipelineProfileV1()
    else:
        if not synthetic_acknowledged:
            raise StandaloneDockCliError(
                "small denominators require --test-only-synthetic"
            )
        profile = DockingPipelineProfileV1.synthetic_test(
            candidate_count=synthetic_candidate_count,
            top_k=synthetic_top_k,
        )
    request = DockingPipelineRequestV1(
        receptor_system=receptor,
        ligand_system=ligand,
        pocket=pocket,
        seed=seed,
        profile=profile,
        test_only=True,
    )
    return DockingPipeline().run(request).to_dict()


def _load_canonical_json(path: Path, *, name: str, maximum: int) -> dict[str, object]:
    raw = _read_bounded(path, maximum=maximum, name=name)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise StandaloneDockCliError(f"{name} has non-canonical line endings")
    try:
        document = json.loads(
            canonical.decode("ascii"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StandaloneDockCliError(f"{name} is invalid JSON") from exc
    if not isinstance(document, dict) or _canonical_bytes(document) != canonical:
        raise StandaloneDockCliError(f"{name} bytes are not canonical")
    return document


def _require_hash(document: Mapping[str, object], field: str, projection: object) -> None:
    observed = str(document.get(field, ""))
    expected = _sha256_document(projection)
    if observed != expected:
        raise StandaloneDockCliError(f"{field} mismatch")


def verify_pipeline_result(document: Mapping[str, object]) -> dict[str, object]:
    if document.get("schema_id") != PIPELINE_RESULT_SCHEMA_ID:
        raise StandaloneDockCliError("pipeline result schema is unsupported")
    request = document.get("request")
    profile = document.get("profile")
    candidates = document.get("candidate_evidence")
    blockers = document.get("blockers")
    if not isinstance(request, dict) or not isinstance(profile, dict):
        raise StandaloneDockCliError("pipeline request/profile evidence is missing")
    if not isinstance(candidates, list) or not isinstance(blockers, list):
        raise StandaloneDockCliError("pipeline candidate/blocker evidence is missing")
    request_projection = dict(request)
    request_projection.pop("request_sha256", None)
    _require_hash(request, "request_sha256", request_projection)
    profile_projection = dict(profile)
    profile_projection.pop("receipt_sha256", None)
    _require_hash(profile, "receipt_sha256", profile_projection)
    result_projection = dict(document)
    result_projection.pop("request", None)
    result_projection.pop("profile", None)
    result_projection.pop("receipt_sha256", None)
    _require_hash(document, "receipt_sha256", result_projection)
    candidate_count = document.get("candidate_count")
    if type(candidate_count) is not int or candidate_count != len(candidates):
        raise StandaloneDockCliError("pipeline candidate denominator mismatch")
    if [row.get("proposal_index") for row in candidates if isinstance(row, dict)] != list(
        range(candidate_count)
    ):
        raise StandaloneDockCliError("pipeline candidate indices are incomplete")
    if any(value not in blockers for value in EXTERNAL_AUTHORITY_BLOCKERS):
        raise StandaloneDockCliError("pipeline external blockers are incomplete")
    required_false = (
        "historical_execution_authorized",
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    )
    if any(document.get(field) is not False for field in required_false):
        raise StandaloneDockCliError("pipeline result asserts forbidden authority")
    if document.get("external_reservation_requested") is not False:
        raise StandaloneDockCliError("pipeline result requested external authority")
    projection = {
        "schema_id": PIPELINE_VERIFICATION_SCHEMA_ID,
        "pipeline_result_receipt_sha256": document["receipt_sha256"],
        "candidate_count": candidate_count,
        "external_authority_blocker_count": len(EXTERNAL_AUTHORITY_BLOCKERS),
        "valid": True,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256_document(projection)}


def report_pipeline_result(document: Mapping[str, object]) -> dict[str, object]:
    verification = verify_pipeline_result(document)
    projection: dict[str, object] = {
        "schema_id": PIPELINE_REPORT_SCHEMA_ID,
        "pipeline_result_receipt_sha256": document["receipt_sha256"],
        "verification_receipt_sha256": verification["receipt_sha256"],
        "profile_id": document["profile"]["profile_id"],
        "candidate_count": document["candidate_count"],
        "success_count": document["success_count"],
        "failure_count": document["failure_count"],
        "top_proposal_indices": document["top_proposal_indices"],
        "abstained": document["abstained"],
        "blockers": document["blockers"],
        "stage0_admission_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
        "claim_safe": False,
    }
    return {**projection, "receipt_sha256": _sha256_document(projection)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-dock",
        description="Claim-blocked standalone CPU docking over canonical prepared inputs.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    receptor = commands.add_parser("prepare-receptor")
    receptor.add_argument("--input", type=Path, required=True)
    receptor.add_argument("--output", type=Path, required=True)
    receptor.add_argument("--overwrite", action="store_true")

    ligands = commands.add_parser("prepare-ligands")
    ligands.add_argument("--input", type=Path, action="append", required=True)
    ligands.add_argument("--output-dir", type=Path, required=True)
    ligands.add_argument("--manifest", type=Path, required=True)
    ligands.add_argument("--overwrite", action="store_true")

    pocket = commands.add_parser("define-pocket")
    source = pocket.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference-ligand", type=Path)
    source.add_argument("--center", type=float, nargs=3)
    pocket.add_argument("--radius", type=float)
    pocket.add_argument("--source-artifact", type=Path)
    pocket.add_argument("--coordinate-frame-id", required=True)
    pocket.add_argument("--model-index", type=int, default=0)
    pocket.add_argument("--padding-angstrom", type=float, default=4.0)
    pocket.add_argument("--minimum-radius-angstrom", type=float, default=6.0)
    pocket.add_argument("--output", type=Path, required=True)
    pocket.add_argument("--overwrite", action="store_true")

    docking = commands.add_parser("dock")
    docking.add_argument("--receptor", type=Path, required=True)
    docking.add_argument("--ligand", type=Path, required=True)
    docking.add_argument("--pocket", type=Path, required=True)
    docking.add_argument("--seed", type=int, required=True)
    docking.add_argument("--synthetic-test-candidates", type=int)
    docking.add_argument("--synthetic-test-top-k", type=int, default=2)
    docking.add_argument("--test-only-synthetic", action="store_true")
    docking.add_argument("--output", type=Path, required=True)
    docking.add_argument("--overwrite", action="store_true")

    verify = commands.add_parser("verify")
    verify.add_argument("--result", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--overwrite", action="store_true")

    report = commands.add_parser("report")
    report.add_argument("--result", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "prepare-receptor":
            prepare_receptor(arguments.input, arguments.output, overwrite=arguments.overwrite)
        elif arguments.command == "prepare-ligands":
            prepare_ligands(
                arguments.input,
                arguments.output_dir,
                arguments.manifest,
                overwrite=arguments.overwrite,
            )
        elif arguments.command == "define-pocket":
            document = define_pocket(arguments)
            _write_output(document, arguments.output, overwrite=arguments.overwrite)
        elif arguments.command == "dock":
            document = dock(
                receptor_path=arguments.receptor,
                ligand_path=arguments.ligand,
                pocket_path=arguments.pocket,
                seed=arguments.seed,
                synthetic_candidate_count=arguments.synthetic_test_candidates,
                synthetic_top_k=arguments.synthetic_test_top_k,
                synthetic_acknowledged=arguments.test_only_synthetic,
            )
            _write_output(document, arguments.output, overwrite=arguments.overwrite)
        elif arguments.command in {"verify", "report"}:
            result = _load_canonical_json(
                arguments.result,
                name="pipeline result",
                maximum=MAX_CLI_INPUT_BYTES,
            )
            document = (
                verify_pipeline_result(result)
                if arguments.command == "verify"
                else report_pipeline_result(result)
            )
            _write_output(document, arguments.output, overwrite=arguments.overwrite)
        else:  # pragma: no cover - argparse owns command admission.
            raise StandaloneDockCliError("unsupported command")
        return 0
    except Exception as exc:
        sys.stderr.buffer.write(_canonical_bytes(_failure_document(exc)) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXPLICIT_POCKET_METHOD_ID",
    "EXPLICIT_POCKET_METHOD_VERSION",
    "LIGAND_MANIFEST_SCHEMA_ID",
    "PIPELINE_REPORT_SCHEMA_ID",
    "PIPELINE_VERIFICATION_SCHEMA_ID",
    "STANDALONE_CLI_ID",
    "StandaloneDockCliError",
    "define_explicit_pocket",
    "dock",
    "main",
    "prepare_ligands",
    "prepare_receptor",
    "report_pipeline_result",
    "verify_pipeline_result",
]
