"""Opt-in prepared CPU diagnostic audit/run/resume/verify; no native promotion."""
import argparse
from pathlib import Path

from ..local_research_workflow import _decode, _json
from ..reference_minimization_workflow import _read
from .failure_diagnostics import message_fingerprint, safe_error_type
from .workflow import audit_request, run_minimization, verify_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('audit', 'run', 'resume', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('--request', type=Path, required=True)
        if name != 'audit':
            command.add_argument('--run-dir', type=Path, required=True)
        if name in {'run', 'resume'}:
            command.add_argument('--pause-after-objective-attempts', type=int)
    args = parser.parse_args(argv)
    try:
        request = _decode(_read(args.request.absolute()))
        if args.command == 'audit':
            result = audit_request(request)
        elif args.command == 'verify':
            result = verify_run(request, args.run_dir)
        else:
            result = run_minimization(request, args.run_dir, resume=args.command == 'resume',
                                      pause_after_objective_attempts=args.pause_after_objective_attempts)
    except Exception as exc:
        result = {'schema_id': 'cpu_cartesian_diagnostic_cli_error/1.4.0', 'status': 'blocked',
                  'public_message': 'Prepared diagnostic request or execution failed',
                  'error_type': safe_error_type(exc), 'private_message': message_fingerprint(exc),
                  'failure_diagnostics': getattr(exc, 'failure_diagnostics', None),
                  'continuation_authorized': False, 'scientifically_validated': False, 'claim_safe': False}
        print(_json(result))
        return 2
    except BaseException as exc:
        # This boundary hides private traceback text without finishing or retrying
        # any numerical reservation. The journal still determines unknown work.
        result = {'schema_id': 'cpu_cartesian_diagnostic_cli_interruption/1.4.0',
                  'status': 'interrupted', 'numerical_work': 'unknown_if_reserved',
                  'public_message': 'Diagnostic invocation interrupted; inspect its journal before continuation',
                  'error_type': safe_error_type(exc), 'private_message': message_fingerprint(exc),
                  'continuation_authorized': False, 'scientifically_validated': False, 'claim_safe': False}
        print(_json(result))
        if isinstance(exc, KeyboardInterrupt):
            return 130
        if isinstance(exc, SystemExit) and type(exc.code) is int and 0 <= exc.code <= 255:
            return exc.code
        return 2
    print(_json(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
