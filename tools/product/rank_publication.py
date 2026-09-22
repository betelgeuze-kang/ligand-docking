"""Recoverable, exclusive publication for the source-bound rank adapter.

This is not candidate computation retry. Only complete staged reports can be
republished; incomplete evidence is never inferred, deleted or overwritten.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
from hashlib import sha256
import os
from pathlib import Path
import stat

from tools.product import compare_prepared_candidate_policies as runner


def read_regular(path):
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("rank_regular_evidence_required")
    return runner.read(path)


def bound_regular(reference):
    read_regular(reference["path"])
    return runner.bound(reference)


def publish_or_match(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        if runner.canonical(read_regular(path)) != runner.canonical(value):
            raise ValueError("rank_existing_publication_mismatch")
    else:
        runner.publish(path, value)


@contextmanager
def directory(output, *, resume):
    if type(resume) is not bool:
        raise ValueError("rank_resume_must_be_boolean")
    root = Path(output).absolute()
    if root.is_symlink():
        raise ValueError("rank_directory_symlink_rejected")
    if resume:
        if not root.is_dir():
            raise ValueError("rank_resume_directory_missing")
    else:
        root.mkdir(mode=0o700)
    descriptor = os.open(root / "rank.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield root
    finally:
        os.close(descriptor)


def validate_run_cost(cost, binding, plan_sha256):
    expected = {"schema_version", "frozen_binding", "plan_sha256", "observed_invocation_wall_seconds",
                "prior_invocation_cost_unknown", "includes", "excludes", "is_sum_of_arm_budgets"}
    if (type(cost) is not dict or set(cost) != expected
            or cost["schema_version"] != "prepared_rank_run_cost_v2"
            or cost["frozen_binding"] != binding or cost["plan_sha256"] != plan_sha256
            or type(cost["prior_invocation_cost_unknown"]) is not bool
            or cost["is_sum_of_arm_budgets"] is not False):
        raise ValueError("rank_run_cost_binding_mismatch")
    if runner._number(cost["observed_invocation_wall_seconds"]) < 0:
        raise ValueError("rank_run_cost_negative")
    if cost["includes"] != ["plan_preflight", "runner_validation", "sequential_arm_execution_or_reuse"]:
        raise ValueError("rank_run_cost_scope_mismatch")
    if cost["excludes"] != ["upstream_preparation", "later_label_evaluation", "cost_and_ready_publication"]:
        raise ValueError("rank_run_cost_scope_mismatch")


def verify_detail_chunks(root, report):
    """Check bytes, stream order/count and hash without materializing all details."""
    for assay, entry in report["metrics_by_assay"].items():
        stream = sha256()
        count, previous = 0, None
        for index, reference in enumerate(entry["detail_chunks"]):
            expected = root / (runner.sha(assay) + f"-{index:06d}.json")
            if Path(reference["path"]).absolute() != expected.absolute():
                raise ValueError("rank_detail_path_mismatch")
            rows = bound_regular(reference)
            if type(rows) is not list or not 1 <= len(rows) <= 4096:
                raise ValueError("rank_detail_chunk_invalid")
            for row in rows:
                pair = (row["left"], row["right"])
                if pair[0] >= pair[1] or (previous is not None and pair <= previous):
                    raise ValueError("rank_detail_order_invalid")
                previous = pair
                stream.update((runner.canonical(row) + "\n").encode())
                count += 1
        summary = entry["summary"]
        if count != summary["detail_rows"]:
            raise ValueError("rank_detail_count_mismatch")
        if summary["details_streamed"]:
            if stream.hexdigest() != summary["detail_sha256"]:
                raise ValueError("rank_detail_stream_mismatch")
        elif entry["detail_chunks"] or summary["detail_sha256"] is not None:
            raise ValueError("rank_unrequested_details")


def recover_report(root, intent, ready, outcomes_sha256):
    path = root / "staged-report.json"
    if not path.exists():
        if (root / "report.json").exists() or (root / "complete.json").exists():
            raise ValueError("rank_publication_stage_missing")
        return None
    stage = read_regular(path)
    if (set(stage) != {"intent_sha256", "report", "report_sha256"}
            or stage["intent_sha256"] != runner.sha(intent)
            or stage["report_sha256"] != runner.sha(stage["report"])):
        raise ValueError("rank_publication_stage_mismatch")
    report = stage["report"]
    if (report["ready"] != ready or report["outcomes_sha256"] != outcomes_sha256
            or report["scientifically_validated"] is not False):
        raise ValueError("rank_staged_inputs_changed")
    finalize(root, report, intent)
    return report


def finalize(root, report, intent):
    verify_detail_chunks(root, report)
    publish_or_match(root / "staged-report.json", {"intent_sha256": runner.sha(intent),
        "report": report, "report_sha256": runner.sha(report)})
    publish_or_match(root / "report.json", report)
    publish_or_match(root / "complete.json", {"report": runner.file_ref(root / "report.json"),
        "intent": runner.file_ref(root / "evaluation-plan.json"),
        "stage": runner.file_ref(root / "staged-report.json"), "scientifically_validated": False})
