#!/usr/bin/env python3
"""New finite PFK paired research campaign over recovered immutable sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan")
    planner.add_argument("--spec", required=True, type=Path)
    for name in ("diagnostics", "optimize", "status", "report", "worker"):
        child = commands.add_parser(name)
        child.add_argument("--plan", required=True, type=Path)
        child.add_argument("--expected-plan-sha256", required=True)
        if name in ("diagnostics", "optimize"):
            child.add_argument("--review", required=True, type=Path)
        elif name == "report":
            child.add_argument("--output", required=True, type=Path)
        elif name == "worker":
            child.add_argument("--phase", required=True)
            child.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    from tools.pfk_paired_water_eight_dof import protocol
    if args.command == "plan":
        result = protocol.build_plan(**protocol._json_file(args.spec))
        print(json.dumps({k: v for k, v in result.items() if k != "plan"}, sort_keys=True))
        return 0
    if args.command == "worker":
        from tools.pfk_paired_water_eight_dof.worker import main as worker_main
        return worker_main(["--plan", str(args.plan), "--expected-plan-sha256", args.expected_plan_sha256,
                            "--phase", args.phase, "--output-dir", str(args.output_dir)])
    if args.command in ("diagnostics", "optimize"):
        from tools.pfk_paired_water_eight_dof.supervisor import execute
        result = execute(plan_path=args.plan, expected_plan_sha256=args.expected_plan_sha256,
                         operation=args.command, review_path=args.review)
        print(json.dumps({"status": result["status"], "failure": result["failure"],
                          "phases": [{"phase": i["phase"], "status": i["status"]} for i in result["phases"]]}, sort_keys=True))
        return 0 if result["status"] == "completed" else 1
    if args.command == "report":
        from tools.pfk_paired_water_eight_dof.report import build_report
        result = build_report(plan_path=args.plan, expected_plan_sha256=args.expected_plan_sha256,
                              output_path=args.output)
        print(json.dumps({"output": str(args.output), "status": result["status"]}, sort_keys=True))
        return 0
    plan = protocol.verify_plan(args.plan, args.expected_plan_sha256)
    from tools.pfk_paired_water_eight_dof.supervisor import reconcile_phase
    phases = [reconcile_phase(args.plan.parent, plan, p) for p in plan["phase_order"]]
    print(json.dumps({"plan_sha256": args.expected_plan_sha256,
                      "phases": [{"phase": p["phase"], "status": p["status"],
                                  "total_work_known": p.get("ledger", {}).get("total_work_known")}
                                 for p in phases]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Paired campaign stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
