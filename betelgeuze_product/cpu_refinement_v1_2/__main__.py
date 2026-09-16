"""Run or structurally verify the explicit CPU research 1.2 workflow."""
from __future__ import annotations

import argparse
from pathlib import Path

from betelgeuze_product.local_research_workflow import _decode, _json
from betelgeuze_product.reference_minimization_workflow import _read
from .workflow import run_request, verify_output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("request", type=Path)
    run.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_request(_decode(_read(args.request.absolute())), args.output)
        print(_json({"report_sha256": result["result"]["report_sha256"],
                     "output": str(args.output.absolute()), "scientifically_validated": False}))
    else:
        print(_json(verify_output(args.directory)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
