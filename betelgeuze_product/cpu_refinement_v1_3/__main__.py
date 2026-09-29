"""Installed CLI for one registered Cartesian CPU refinement."""
import argparse
from pathlib import Path

from betelgeuze_product.local_research_workflow import _decode, _json
from betelgeuze_product.reference_minimization_workflow import _read
from .workflow import evaluate, verify_output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'resume', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('--request', type=Path, required=True)
        command.add_argument('--run-dir', type=Path, required=True)
        if name != 'verify':
            command.add_argument('--pause-after-objective-attempts', type=int)
    args = parser.parse_args(argv)
    request = _decode(_read(args.request.absolute()))
    result = (verify_output(request, args.run_dir) if args.command == 'verify' else
              evaluate(request, args.run_dir, resume=args.command == 'resume',
                       pause_after_objective_attempts=args.pause_after_objective_attempts))
    print(_json(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
