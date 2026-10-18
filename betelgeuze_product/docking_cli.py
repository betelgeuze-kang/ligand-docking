"""Product CLI composition over the independently installable Engine v2 CLI."""

from __future__ import annotations

import sys

from betelgeuze_engine_v2 import standalone_cli as engine_cli


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        parser = engine_cli._parser()
        parser.epilog = (
            "Installed prepared-molecule research: "
            "betelgeuze-dock prepared-refine --help"
        )
        parser.print_help()
        return 0
    if not arguments or arguments[0] != "prepared-refine":
        return engine_cli.main(arguments)

    from .prepared_refinement_cli import add_arguments, dispatch

    try:
        parser = engine_cli._CanonicalArgumentParser(
            prog="betelgeuze-dock prepared-refine",
            description="Bounded prepared-molecule Fourier refinement and retained-result report.",
        )
        add_arguments(parser)
        prepared = parser.parse_args(arguments[1:])
        document, exit_code = dispatch(prepared)
        engine_cli._write_output(
            document, prepared.output, overwrite=False,
            input_paths=(prepared.protocol,),
        )
        return exit_code
    except Exception as exc:
        sys.stderr.buffer.write(engine_cli._canonical_bytes(engine_cli._failure_document(exc)) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
