"""Explicit accepted600_attempts641 development profile, using the shared executor.

No physics or tolerance changes. A cap is not convergence or qualification.
Optimizer calls are bounded by 641; restart verification adds zero or one call.
Use an external timeout for wall/CPU bounds. Pending unknown work is never retried.
"""
import argparse
import json
from pathlib import Path

import torch

from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as shared

PROFILE_ID = "accepted600_attempts641/1.0.0"
_PROFILE = shared._BudgetProfile(
    profile_id=PROFILE_ID,
    protocol="prepared_cartesian_long_budget_protocol/1.0.0",
    binding_schema="prepared_cartesian_long_budget_binding/1.0.0",
    result_schema="prepared_cartesian_long_budget_result/1.0.0",
    preflight_schema="prepared_cartesian_long_budget_preflight/1.0.0",
    accepted_steps=(600,), objective_attempts=641, adapter_source=__file__,
)


def _selection(profile, model, restart_verifications):
    shared._require(type(profile) is str and profile == PROFILE_ID,
                    "explicit supported long-budget profile required")
    shared._require(type(model) is str and model in shared.MODELS,
                    "explicit prepared model required")
    return dict(model=model, accepted_steps=600, restart_verifications=restart_verifications,
                _profile=_PROFILE)


def budget_config(algorithm, *, profile, restart_verifications):
    shared._require(type(profile) is str and profile == PROFILE_ID,
                    "explicit supported long-budget profile required")
    return shared.budget_config(algorithm, 600, restart_verifications=restart_verifications,
                                _profile=_PROFILE)


def prepare(*, profile, model, restart_verifications, candidate_id, evidence_kind,
            ligand, receptor, parameters, cross, source_evidence, solver, output):
    return shared.prepare(**_selection(profile, model, restart_verifications),
        candidate_id=candidate_id, evidence_kind=evidence_kind, ligand=ligand,
        receptor=receptor, parameters=parameters, cross=cross, source_evidence=source_evidence,
        solver=solver, output=output)


def preflight(protocol_path, expected_sha256, *, profile, model, restart_verifications):
    return shared.preflight(protocol_path, expected_sha256,
                            **_selection(profile, model, restart_verifications))


def run(protocol_path, expected_sha256, run_dir, *, profile, model, restart_verifications,
        resume=False, pause_after_objective_attempts=None):
    return shared.run(protocol_path, expected_sha256, run_dir,
                      **_selection(profile, model, restart_verifications), resume=resume,
                      pause_after_objective_attempts=pause_after_objective_attempts)


def verify(protocol_path, expected_sha256, run_dir, *, profile, model, restart_verifications):
    return shared.verify(protocol_path, expected_sha256, run_dir,
                         **_selection(profile, model, restart_verifications))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ("prepare", "preflight", "run", "resume", "verify"):
        command = actions.add_parser(action)
        command.add_argument("--profile", choices=(PROFILE_ID,), required=True)
        command.add_argument("--model", choices=shared.MODELS, required=True)
        command.add_argument("--restart-verifications", type=int, choices=(0, 1), required=True)
        if action in {"run", "resume"}:
            command.add_argument("--pause-after-objective-attempts", type=int)
        if action == "prepare":
            command.add_argument("--candidate-id", required=True)
            command.add_argument("--evidence-kind", choices=("prepared_real_development", "synthetic_control"), required=True)
            for name in shared.REFS:
                command.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
            command.add_argument("--algorithm", choices=("sd", "lbfgs"), required=True)
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--protocol", type=Path, required=True)
            command.add_argument("--expected-protocol-sha256", required=True)
            if action != "preflight":
                command.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    selection = dict(profile=args.profile, model=args.model,
                     restart_verifications=args.restart_verifications)
    if args.action == "prepare":
        result = prepare(**selection, candidate_id=args.candidate_id, evidence_kind=args.evidence_kind,
                         **{name: getattr(args, name) for name in shared.REFS},
                         solver=budget_config(args.algorithm, profile=args.profile,
                                              restart_verifications=args.restart_verifications), output=args.output)
    elif args.action == "preflight":
        result = preflight(args.protocol, args.expected_protocol_sha256, **selection)
    elif args.action in {"run", "resume"}:
        result = run(args.protocol, args.expected_protocol_sha256, args.run_dir, **selection,
                     resume=args.action == "resume",
                     pause_after_objective_attempts=args.pause_after_objective_attempts)
    else:
        result = verify(args.protocol, args.expected_protocol_sha256, args.run_dir, **selection)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
