"""Standalone CPU product CLI backed by the shared :class:`DockingPipeline`."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence

from . import cli as _dock_cli
from .cli import run_canonical_docking_verified
from .input_bound_verifier import verify_input_bound_cli_bundle_bytes
from .io import (
    PDB_PARSER_NAME,
    PDB_PARSER_VERSION,
    SDF_PARSER_NAME,
    SDF_PARSER_VERSION,
    parse_pdb,
    parse_sdf_v2000,
)
from .molecular import canonical_system_json_bytes
from .reference_pocket import derive_reference_pocket_from_path
from .result_verifier_strict import verify_canonical_cli_result_bytes


STANDALONE_CLI_ID = "betelgeuze-dock/1.0.0"
PREPARE_RECEPTOR_SCHEMA_ID = "betelgeuze.engine_v2_prepare_receptor_receipt/1.0.0"
PREPARE_LIGANDS_SCHEMA_ID = "betelgeuze.engine_v2_prepare_ligands_receipt/1.0.0"
STANDALONE_REPORT_SCHEMA_ID = "betelgeuze.engine_v2_standalone_docking_report/1.0.0"
_SAFE_STEM = re.compile(r"[^A-Za-z0-9_.-]+")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _document_receipt(document: dict[str, object], *, field: str) -> None:
    document[field] = _dock_cli._sha256_document(document)


def _emit_or_write(
    document: Mapping[str, object],
    *,
    output: Path | None,
    overwrite: bool,
) -> None:
    if output is None:
        sys.stdout.buffer.write(_dock_cli._canonical_bytes(document) + b"\n")
        sys.stdout.buffer.flush()
    else:
        _dock_cli._write_output(document, output, overwrite=overwrite)


def _prepare_receptor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock prepare-receptor")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-id", default="")
    parser.add_argument("--receipt-output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _prepare_receptor(argv: Sequence[str]) -> int:
    arguments = _prepare_receptor_parser().parse_args(argv)
    raw = _dock_cli._read_bounded(
        arguments.input,
        maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
        name="receptor PDB input",
    )
    system = parse_pdb(
        raw,
        source_id=str(arguments.source_id or arguments.input.name),
        connectivity_policy="reject_unrepresented",
    )
    canonical = json.loads(canonical_system_json_bytes(system).decode("ascii"))
    _dock_cli._write_output(
        canonical,
        arguments.output,
        overwrite=bool(arguments.overwrite),
    )
    output_bytes = _dock_cli._canonical_bytes(canonical) + b"\n"
    receipt: dict[str, object] = {
        "schema_id": PREPARE_RECEPTOR_SCHEMA_ID,
        "command_id": f"{STANDALONE_CLI_ID}/prepare-receptor",
        "parser_id": f"{PDB_PARSER_NAME}/{PDB_PARSER_VERSION}",
        "source_artifact_sha256": _sha256_bytes(raw),
        "canonical_artifact_sha256": _sha256_bytes(output_bytes),
        "atom_count": system.atom_count,
        "bond_count": len(system.bonds),
        "model_count": system.model_count,
        "network_fetch_performed": False,
        "bond_inference_performed": False,
        "protonation_performed": False,
        "chemistry_inference_performed": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    _document_receipt(receipt, field="receipt_sha256")
    _emit_or_write(
        receipt,
        output=arguments.receipt_output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _prepare_ligands_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock prepare-ligands")
    parser.add_argument("--input", required=True, type=Path, action="append")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt-output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _ligand_output_name(path: Path, index: int) -> str:
    stem = _SAFE_STEM.sub("-", path.stem).strip("-.") or "ligand"
    return f"{index:04d}-{stem}.canonical.json"


def _prepare_ligands(argv: Sequence[str]) -> int:
    arguments = _prepare_ligands_parser().parse_args(argv)
    if len({path.resolve() for path in arguments.input}) != len(arguments.input):
        raise _dock_cli.EngineV2CliError("duplicate ligand input path")
    outputs: list[dict[str, object]] = []
    for index, path in enumerate(arguments.input):
        raw = _dock_cli._read_bounded(
            path,
            maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
            name=f"ligand SDF input {index}",
        )
        system = parse_sdf_v2000(raw, source_id=path.name)
        canonical = json.loads(canonical_system_json_bytes(system).decode("ascii"))
        output = arguments.output_dir / _ligand_output_name(path, index)
        _dock_cli._write_output(
            canonical,
            output,
            overwrite=bool(arguments.overwrite),
        )
        output_bytes = _dock_cli._canonical_bytes(canonical) + b"\n"
        outputs.append(
            {
                "input_index": index,
                "source_name": path.name,
                "source_artifact_sha256": _sha256_bytes(raw),
                "output_name": output.name,
                "canonical_artifact_sha256": _sha256_bytes(output_bytes),
                "atom_count": system.atom_count,
                "bond_count": len(system.bonds),
                "model_count": system.model_count,
            }
        )
    receipt: dict[str, object] = {
        "schema_id": PREPARE_LIGANDS_SCHEMA_ID,
        "command_id": f"{STANDALONE_CLI_ID}/prepare-ligands",
        "parser_id": f"{SDF_PARSER_NAME}/{SDF_PARSER_VERSION}",
        "ligand_count": len(outputs),
        "outputs": outputs,
        "multi_record_sdf_accepted": False,
        "network_fetch_performed": False,
        "bond_inference_performed": False,
        "protonation_performed": False,
        "tautomer_selection_performed": False,
        "chemistry_inference_performed": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    _document_receipt(receipt, field="receipt_sha256")
    _emit_or_write(
        receipt,
        output=arguments.receipt_output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _define_pocket_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock define-pocket")
    parser.add_argument("--ligand", required=True, type=Path)
    parser.add_argument("--coordinate-frame-id", required=True)
    parser.add_argument("--model-index", type=int, default=0)
    parser.add_argument("--padding-angstrom", type=float, default=4.0)
    parser.add_argument("--minimum-radius-angstrom", type=float, default=6.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _define_pocket(argv: Sequence[str]) -> int:
    arguments = _define_pocket_parser().parse_args(argv)
    document = derive_reference_pocket_from_path(
        arguments.ligand,
        coordinate_frame_id=arguments.coordinate_frame_id,
        model_index=arguments.model_index,
        padding_angstrom=arguments.padding_angstrom,
        minimum_radius_angstrom=arguments.minimum_radius_angstrom,
    )
    _emit_or_write(
        document,
        output=arguments.output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _dock_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock dock")
    parser.add_argument("--receptor", type=Path, required=True)
    parser.add_argument("--ligand", type=Path, required=True)
    parser.add_argument("--pocket", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--candidate-count", type=int, default=64)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-torsions", type=int, default=32)
    parser.add_argument("--translation-radius-angstrom", type=float, default=4.0)
    parser.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def _dock(argv: Sequence[str]) -> int:
    arguments = _dock_parser().parse_args(argv)
    verified = run_canonical_docking_verified(
        receptor_path=arguments.receptor,
        ligand_path=arguments.ligand,
        pocket_path=arguments.pocket,
        candidate_count=arguments.candidate_count,
        top_k=arguments.top_k,
        max_torsions=arguments.max_torsions,
        translation_radius_angstrom=(arguments.translation_radius_angstrom),
        seed=arguments.seed,
        receptor_margin_angstrom=arguments.receptor_margin_angstrom,
    )
    document = dict(verified.recorded_evidence)
    _emit_or_write(
        document,
        output=arguments.output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _verify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock verify")
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--receptor", type=Path)
    parser.add_argument("--ligand", type=Path)
    parser.add_argument("--pocket", type=Path)
    parser.add_argument("--receptor-model-index", type=int, default=0)
    parser.add_argument("--ligand-model-index", type=int, default=0)
    parser.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    parser.add_argument("--require-reference-pocket-derivation", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _verify(argv: Sequence[str]) -> int:
    arguments = _verify_parser().parse_args(argv)
    result_raw = _dock_cli._read_bounded(
        arguments.result,
        maximum=256 * 1024 * 1024,
        name="canonical docking result",
    )
    bundle_values = (arguments.receptor, arguments.ligand, arguments.pocket)
    if any(value is not None for value in bundle_values) and not all(
        value is not None for value in bundle_values
    ):
        raise _dock_cli.EngineV2CliError(
            "verify requires receptor, ligand, and pocket together"
        )
    if all(value is not None for value in bundle_values):
        assert arguments.receptor is not None
        assert arguments.ligand is not None
        assert arguments.pocket is not None
        receipt = verify_input_bound_cli_bundle_bytes(
            result_raw=result_raw,
            receptor_raw=_dock_cli._read_bounded(
                arguments.receptor,
                maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
                name="receptor canonical document",
            ),
            ligand_raw=_dock_cli._read_bounded(
                arguments.ligand,
                maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
                name="ligand canonical document",
            ),
            pocket_raw=_dock_cli._read_bounded(
                arguments.pocket,
                maximum=_dock_cli.MAX_CLI_POCKET_BYTES,
                name="pocket canonical document",
            ),
            receptor_model_index=arguments.receptor_model_index,
            ligand_model_index=arguments.ligand_model_index,
            receptor_margin_angstrom=arguments.receptor_margin_angstrom,
            require_reference_pocket_derivation=bool(
                arguments.require_reference_pocket_derivation
            ),
        )
        verification_kind = "input_bound_bundle"
    else:
        receipt = verify_canonical_cli_result_bytes(result_raw)
        verification_kind = "result_only"
    document: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_standalone_verify/1.0.0",
        "command_id": f"{STANDALONE_CLI_ID}/verify",
        "verification_kind": verification_kind,
        "verification": receipt.to_dict(),
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    _document_receipt(document, field="receipt_sha256")
    _emit_or_write(
        document,
        output=arguments.output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betelgeuze-dock report")
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _report(argv: Sequence[str]) -> int:
    arguments = _report_parser().parse_args(argv)
    raw = _dock_cli._read_bounded(
        arguments.result,
        maximum=256 * 1024 * 1024,
        name="canonical docking result",
    )
    verification = verify_canonical_cli_result_bytes(raw)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    result_document = json.loads(canonical.decode("ascii"))
    pipeline = result_document["pipeline_evidence"]
    generic = result_document["result"]["placement_search_result"]["search"][
        "search_result"
    ]
    report: dict[str, object] = {
        "schema_id": STANDALONE_REPORT_SCHEMA_ID,
        "command_id": f"{STANDALONE_CLI_ID}/report",
        "source_result_document_sha256": result_document["document_sha256"],
        "verification_receipt_sha256": verification.receipt_sha256,
        "pipeline_profile_id": pipeline["pipeline_profile_id"],
        "pipeline_profile_sha256": pipeline["pipeline_profile_sha256"],
        "candidate_count": result_document["candidate_count"],
        "success_count": result_document["success_count"],
        "failure_count": result_document["failure_count"],
        "valid_pose_count": generic["valid_pose_count"],
        "selection_eligible_count": generic["selection_eligible_count"],
        "top_candidate_ids": generic["top_candidate_ids"],
        "blockers": generic["blockers"],
        "rendered_without_rescoring": True,
        "pose_coordinates_emitted": False,
        "calibrated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    _document_receipt(report, field="report_sha256")
    _emit_or_write(
        report,
        output=arguments.output,
        overwrite=bool(arguments.overwrite),
    )
    return 0


def _top_level_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-dock",
        description="Standalone fail-closed CPU docking pipeline commands.",
    )
    commands = parser.add_subparsers(dest="command")
    for command in (
        "prepare-receptor",
        "prepare-ligands",
        "define-pocket",
        "dock",
        "verify",
        "report",
    ):
        commands.add_parser(command, add_help=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in ([], ["--help"], ["-h"]):
        _top_level_parser().print_help()
        return 0
    dispatch = {
        "prepare-receptor": _prepare_receptor,
        "prepare-ligands": _prepare_ligands,
        "define-pocket": _define_pocket,
        "dock": _dock,
        "verify": _verify,
        "report": _report,
    }
    handler = dispatch.get(arguments[0])
    if handler is None:
        _top_level_parser().error(f"unsupported command: {arguments[0]}")
    try:
        return handler(arguments[1:])
    except Exception as exc:
        failure = _dock_cli._failure_document(exc)
        sys.stderr.buffer.write(_dock_cli._canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PREPARE_LIGANDS_SCHEMA_ID",
    "PREPARE_RECEPTOR_SCHEMA_ID",
    "STANDALONE_CLI_ID",
    "STANDALONE_REPORT_SCHEMA_ID",
    "main",
]
