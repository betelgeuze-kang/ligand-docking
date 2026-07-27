"""Console dispatch for canonical docking, pocket derivation, and verification.

``dock-canonical`` remains implemented by :mod:`betelgeuze_engine_v2.cli`.
``pocket-from-reference`` derives the exact typed pocket schema from a canonical
reference ligand already expressed in the receptor coordinate frame.
``verify-result`` validates one canonical result artifact without re-running the
calculation. ``verify-bundle`` additionally replays the authoritative input and
scorer contracts from receptor, ligand, and pocket artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from . import cli as _dock_cli
from .result_verifier_strict import verify_canonical_cli_result_bytes


VERIFY_RESULT_COMMAND_ID = "betelgeuze-engine-v2/verify-result/1.0.0"
VERIFY_BUNDLE_COMMAND_ID = "betelgeuze-engine-v2/verify-bundle/1.0.0"


def _top_level_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2",
        description=(
            "Fail-closed canonical-input Engine v2 research commands."
        ),
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser(
        "dock-canonical",
        help="Run authenticated known-pocket docking from canonical inputs.",
        add_help=False,
    )
    commands.add_parser(
        "pocket-from-reference",
        help="Derive a deterministic redocking pocket from a canonical ligand.",
        add_help=False,
    )
    commands.add_parser(
        "verify-result",
        help="Verify a canonical docking result without re-running it.",
        add_help=False,
    )
    commands.add_parser(
        "verify-bundle",
        help=(
            "Reconstruct docking authority and scorer contracts from all input artifacts."
        ),
        add_help=False,
    )
    return parser


def _verification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2 verify-result",
        description=(
            "Verify a canonical Engine v2 docking result without re-running it."
        ),
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _bundle_verification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2 verify-bundle",
        description=(
            "Verify a result and reconstruct its authority/scorer from canonical inputs."
        ),
    )
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--receptor", type=Path, required=True)
    parser.add_argument("--ligand", type=Path, required=True)
    parser.add_argument("--pocket", type=Path, required=True)
    parser.add_argument("--receptor-model-index", type=int, default=0)
    parser.add_argument("--ligand-model-index", type=int, default=0)
    parser.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    parser.add_argument(
        "--require-reference-pocket-derivation",
        action="store_true",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _emit_or_write(
    document: dict[str, object],
    *,
    output: Path | None,
    overwrite: bool,
) -> None:
    if output is None:
        sys.stdout.buffer.write(_dock_cli._canonical_bytes(document) + b"\n")
        sys.stdout.buffer.flush()
    else:
        _dock_cli._write_output(
            document,
            output,
            overwrite=overwrite,
        )


def _verify_result(argv: Sequence[str]) -> int:
    arguments = _verification_parser().parse_args(argv)
    try:
        raw = _dock_cli._read_bounded(
            arguments.input,
            maximum=256 * 1024 * 1024,
            name="canonical docking result",
        )
        receipt = verify_canonical_cli_result_bytes(raw)
        document = {
            "command_id": VERIFY_RESULT_COMMAND_ID,
            **receipt.to_dict(),
        }
        document["document_sha256"] = _dock_cli._sha256_document(document)
        _emit_or_write(
            document,
            output=arguments.output,
            overwrite=bool(arguments.overwrite),
        )
        return 0
    except Exception as exc:
        failure = _dock_cli._failure_document(exc)
        sys.stderr.buffer.write(_dock_cli._canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


def _verify_bundle(argv: Sequence[str]) -> int:
    arguments = _bundle_verification_parser().parse_args(argv)
    try:
        from .input_bound_verifier import (
            MAX_INPUT_BOUND_RESULT_BYTES,
            verify_input_bound_cli_bundle_bytes,
        )

        result_raw = _dock_cli._read_bounded(
            arguments.result,
            maximum=MAX_INPUT_BOUND_RESULT_BYTES,
            name="canonical docking result",
        )
        receptor_raw = _dock_cli._read_bounded(
            arguments.receptor,
            maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
            name="receptor canonical document",
        )
        ligand_raw = _dock_cli._read_bounded(
            arguments.ligand,
            maximum=_dock_cli.MAX_CLI_INPUT_BYTES,
            name="ligand canonical document",
        )
        pocket_raw = _dock_cli._read_bounded(
            arguments.pocket,
            maximum=_dock_cli.MAX_CLI_POCKET_BYTES,
            name="pocket canonical document",
        )
        receipt = verify_input_bound_cli_bundle_bytes(
            result_raw=result_raw,
            receptor_raw=receptor_raw,
            ligand_raw=ligand_raw,
            pocket_raw=pocket_raw,
            receptor_model_index=arguments.receptor_model_index,
            ligand_model_index=arguments.ligand_model_index,
            receptor_margin_angstrom=arguments.receptor_margin_angstrom,
            require_reference_pocket_derivation=bool(
                arguments.require_reference_pocket_derivation
            ),
        )
        document = {
            "command_id": VERIFY_BUNDLE_COMMAND_ID,
            **receipt.to_dict(),
        }
        document["document_sha256"] = _dock_cli._sha256_document(document)
        _emit_or_write(
            document,
            output=arguments.output,
            overwrite=bool(arguments.overwrite),
        )
        return 0
    except Exception as exc:
        failure = _dock_cli._failure_document(exc)
        sys.stderr.buffer.write(_dock_cli._canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        _top_level_parser().print_help()
        return 0
    if arguments and arguments[0] == "verify-result":
        return _verify_result(arguments[1:])
    if arguments and arguments[0] == "verify-bundle":
        return _verify_bundle(arguments[1:])
    if arguments and arguments[0] == "pocket-from-reference":
        from .reference_pocket import main as reference_pocket_main

        return reference_pocket_main(arguments[1:])
    return _dock_cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "VERIFY_BUNDLE_COMMAND_ID",
    "VERIFY_RESULT_COMMAND_ID",
    "main",
]
