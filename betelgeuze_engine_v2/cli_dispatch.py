"""Console dispatch for canonical docking, pocket derivation, and verification.

``dock-canonical`` remains implemented by :mod:`betelgeuze_engine_v2.cli`.
``pocket-from-reference`` derives the exact typed pocket schema from a canonical
reference ligand already expressed in the receptor coordinate frame.
``verify-result`` validates one canonical result artifact without re-running the
calculation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from . import cli as _dock_cli
from .result_verifier_strict import verify_canonical_cli_result_bytes


VERIFY_RESULT_COMMAND_ID = "betelgeuze-engine-v2/verify-result/1.0.0"


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
        if arguments.output is None:
            sys.stdout.buffer.write(_dock_cli._canonical_bytes(document) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _dock_cli._write_output(
                document,
                arguments.output,
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
    if arguments and arguments[0] == "pocket-from-reference":
        from .reference_pocket import main as reference_pocket_main

        return reference_pocket_main(arguments[1:])
    return _dock_cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["VERIFY_RESULT_COMMAND_ID", "main"]
