"""Dependency-light public CLI for the configured prepared-job facade."""

from __future__ import annotations

import argparse
import json
import sys


class _InputError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo caller-provided paths, argv, or environment values.
        raise _InputError("Invalid prepared-jobs arguments; use --help")


def parser() -> argparse.ArgumentParser:
    root = _Parser(
        prog="betelgeuze-dock prepared-jobs",
        description=(
            "Research-only prepared jobs using administrator-admitted inputs and "
            "the configured local lifecycle service. Submit queues work; owner-once "
            "runs at most one queued job."
        ),
        allow_abbrev=False,
    )
    actions = root.add_subparsers(dest="action", required=True, parser_class=_Parser)
    submit = actions.add_parser("submit", allow_abbrev=False)
    submit.add_argument("admission_id")
    submit.add_argument("--idempotency-key", required=True)
    submit.add_argument("--budget-policy", default="local_cpu_research_v1")
    plan = actions.add_parser("plan", allow_abbrev=False)
    plan.add_argument("admission_id")
    plan.add_argument("--budget-policy", default="local_cpu_research_v1")
    get_plan = actions.add_parser("get-plan", allow_abbrev=False)
    get_plan.add_argument("plan_id")
    execute = actions.add_parser("execute", allow_abbrev=False)
    execute.add_argument("plan_id")
    execute.add_argument("--plan-sha256", required=True)
    execute.add_argument("--idempotency-key", required=True)
    compare = actions.add_parser("compare", allow_abbrev=False)
    compare.add_argument("execution_ids", nargs="+")
    for name in ("status", "cancel", "resume", "artifacts", "artifact", "verify", "report"):
        command = actions.add_parser(name, allow_abbrev=False)
        command.add_argument("execution_id")
        if name == "cancel":
            command.add_argument("--reason", default="")
        if name == "artifact":
            command.add_argument("artifact_id")
    actions.add_parser("owner-once", allow_abbrev=False)
    return root


def dispatch(arguments) -> dict:
    """Use the same configured facade as HTTP; never accept filesystem inputs."""
    from .prepared_lifecycle import configured_service

    service = configured_service()
    action = arguments.action
    if action == "plan":
        return service.plan(arguments.admission_id, budget_policy=arguments.budget_policy)
    if action == "get-plan":
        return service.get_plan(arguments.plan_id)
    if action == "execute":
        return service.execute(arguments.plan_id, arguments.plan_sha256, arguments.idempotency_key)
    if action == "verify":
        return service.verify(arguments.execution_id)
    if action == "report":
        return service.report(arguments.execution_id)
    if action == "compare":
        return service.compare(arguments.execution_ids)
    if action == "submit":
        return service.submit(
            arguments.admission_id,
            arguments.idempotency_key,
            budget_policy=arguments.budget_policy,
        )
    if action == "status":
        return service.status(arguments.execution_id)
    if action == "cancel":
        return service.cancel(arguments.execution_id, reason=arguments.reason)
    if action == "resume":
        return service.resume(arguments.execution_id)
    if action == "artifacts":
        return service.artifacts(arguments.execution_id)
    if action == "artifact":
        _, metadata = service.artifact(arguments.execution_id, arguments.artifact_id)
        # Internal paths are never a public response. The HTTP download endpoint
        # serves the hash-checked artifact; this command returns its descriptor.
        return {
            "execution_id": arguments.execution_id,
            "artifact": metadata,
            "research_only": True,
            "qualified": False,
        }
    if action == "owner-once":
        from .prepared_lifecycle_owner import run_one

        result = run_one(service)
        return result if result is not None else {
            "status": "idle", "research_only": True, "qualified": False,
        }
    raise _InputError("Invalid prepared-jobs action")


def _error_document(code: str, message: str) -> dict:
    return {
        "schema_version": "prepared_lifecycle_error/1.0.0",
        "error": {"code": code, "message": message, "retry_allowed": False},
        "research_only": True,
        "qualified": False,
    }


def _write(document: dict, stream) -> None:
    stream.write(json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    stream.flush()


def main(argv=None) -> int:
    try:
        arguments = parser().parse_args(argv)
        document = dispatch(arguments)
        _write(document, sys.stdout)
        return 0
    except _InputError as exc:
        _write(_error_document("INVALID_ARGUMENT", str(exc)), sys.stderr)
        return 2
    except Exception as exc:
        from .prepared_lifecycle import LifecycleError

        document = exc.document() if isinstance(exc, LifecycleError) else _error_document(
            "INTERNAL_ERROR", "Prepared lifecycle request failed",
        )
        _write(document, sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
