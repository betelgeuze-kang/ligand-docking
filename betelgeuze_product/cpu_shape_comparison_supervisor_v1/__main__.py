"""Whole-comparison launcher. Real execution still requires run authorization."""
import argparse
import json
import resource
import signal

from .limits import Limits
from .supervisor import run_comparison, wall_deadline


def configure_parent_cpu(soft_seconds=300, hard_seconds=600):
    if (type(soft_seconds) is not int or type(hard_seconds) is not int
            or not 1 <= soft_seconds <= 300 or not soft_seconds <= hard_seconds <= 600):
        raise ValueError('bounded inheritable parent CPU limits required')
    # The default SIGXCPU disposition terminates the parent at its soft limit.
    # Keep an inheritable hard ceiling large enough for the worker's own cap.
    signal.signal(signal.SIGXCPU, signal.SIG_DFL)
    resource.setrlimit(resource.RLIMIT_CPU, (soft_seconds, hard_seconds))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--expected-plan-sha256', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--resource-policy', choices=('default', 'research_161'), default='default',
                        help='research_161 explicitly opts into 360 writes and 8 MiB per file')
    args = parser.parse_args()
    limits = Limits() if args.resource_policy == 'default' else Limits(
        resource_policy='research_161', file_bytes=8 * 1024 * 1024, write_reservations=360)
    # Separate parent CPU allowance, plus four workers <=600 seconds each.
    configure_parent_cpu()
    with wall_deadline(2700.):
        result = run_comparison(args.plan, args.expected_plan_sha256, args.output_dir, limits=limits)
        print(json.dumps({'report_sha256': result['report_sha256'], 'denominator': result['denominator']}))


if __name__ == '__main__':
    main()
