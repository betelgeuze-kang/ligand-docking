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
    resumable = commands.add_parser("run-resumable")
    resumable.add_argument("request", type=Path)
    resumable.add_argument("--output", required=True, type=Path)
    resumable.add_argument("--resume", action="store_true")
    resumable.add_argument("--stop-after", type=int)
    verify_resumed = commands.add_parser("verify-resumable")
    verify_resumed.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_request(_decode(_read(args.request.absolute())), args.output)
        print(_json({"report_sha256": result["result"]["report_sha256"],
                     "output": str(args.output.absolute()), "scientifically_validated": False}))
    elif args.command == "verify":
        print(_json(verify_output(args.directory)))
    else:
        from .resumable_workflow import run_resumable_request, verify_resumable_output
        result = (verify_resumable_output(args.directory) if args.command == "verify-resumable" else
                  run_resumable_request(_decode(_read(args.request.absolute())), args.output,
                                        resume=args.resume, stop_after=args.stop_after))
        print(_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
