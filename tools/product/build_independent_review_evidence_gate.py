#!/usr/bin/env python3
"""Independent review evidence gate (P0-2).

``betelgeuze_product.review_evidence`` defines what an independent review must
prove. This tool is the operator-facing gate: it reads a recorded review
evidence JSON and emits the receipt P0-1 needs before the reconstruction work
can be called integrated.

It is deliberately offline. It does not query GitHub for reviews or branch
protection, because a gate that fetches its own evidence can be satisfied by
whatever the API happens to return; the operator records what they verified, and
this gate checks that record is internally consistent and complete.

Fail-closed: a missing file, an unfilled reviewer handle, a self-review, a review
bound to a different commit, or an enabled admin bypass all block the gate and
are named individually in the receipt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.review_evidence import (  # noqa: E402
    REQUIRED_REVIEW_ROLES,
    REVIEW_EVIDENCE_SCHEMA_VERSION,
    build_review_evidence,
)

DEFAULT_EVIDENCE_JSON = "config/independent_review_evidence_current.json"
DEFAULT_CODEOWNERS_PATH = ".github/CODEOWNERS"
DEFAULT_OUT_JSON = "runs/independent_review_evidence_gate_current.json"
DEFAULT_OUT_MD = "runs/independent_review_evidence_gate_current.md"

STATUS_READY = "independent_review_evidence_gate_ready"
STATUS_BLOCKED = "blocked_independent_review_evidence_gate"

CLAIM_BOUNDARY = (
    "Independent review evidence gate only. It validates an operator-recorded review evidence file offline and "
    "emits a fail-closed receipt. It does not query GitHub, read or change branch protection, request or approve "
    "reviews, merge, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path)


def _next_operator_step(violations: list[str]) -> str:
    """Name the single most useful next action."""

    if not violations:
        return (
            "Independent review evidence is complete: author-distinct security and numerical reviewers "
            "approved the recorded commit under an enforced protected branch."
        )
    if any(v.startswith("evidence_json_missing") for v in violations):
        return (
            f"Create the review evidence record at {DEFAULT_EVIDENCE_JSON} with author_id, "
            "reviewed_commit_sha, reviews[], branch_protection{} and codeowners{}."
        )
    if "codeowners_file_missing" in violations:
        return f"Add {DEFAULT_CODEOWNERS_PATH} and assign security and numerical owners."
    if any(v.endswith("_only_author") for v in violations):
        return (
            "CODEOWNERS names only the author. Assign at least one non-author owner for the security and "
            "numerical paths so ownership is separate from authorship."
        )
    if any(v.startswith("required_review_role_unsatisfied") for v in violations):
        roles = sorted(
            v.split(":", 1)[1]
            for v in violations
            if v.startswith("required_review_role_unsatisfied")
        )
        return (
            "Obtain an approving review from a non-author reviewer for each unsatisfied role: "
            + ",".join(roles)
        )
    if "no_author_distinct_approving_reviewer" in violations:
        return "Obtain at least one approving review from a reviewer who is not the author."
    if "admin_bypass_allowed" in violations:
        return (
            "Disable admin bypass on the protected branch; while it is enabled every other protection is "
            "advisory only."
        )
    if any(v.startswith("review_commit_mismatch") for v in violations):
        return (
            "Re-review the current commit: at least one recorded review is bound to a different "
            "reviewed_commit_sha."
        )
    if any(v.startswith("self_review_not_independent") for v in violations):
        return "Replace self-reviews: the author cannot satisfy an independent review role."
    return "Resolve the reported review evidence violations: " + ",".join(violations[:3])


def build_independent_review_evidence_gate(
    *,
    evidence_json: str | Path = DEFAULT_EVIDENCE_JSON,
    codeowners_path: str | Path = DEFAULT_CODEOWNERS_PATH,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate recorded review evidence and emit the gate receipt."""

    root_path = Path(root) if root is not None else ROOT
    evidence_path = (
        Path(evidence_json)
        if Path(evidence_json).is_absolute()
        else root_path / evidence_json
    )
    codeowners_file = (
        Path(codeowners_path)
        if Path(codeowners_path).is_absolute()
        else root_path / codeowners_path
    )

    read_blockers: list[str] = []
    payload: dict[str, Any] = {}
    if not evidence_path.is_file():
        read_blockers.append(f"evidence_json_missing:{evidence_path.name}")
    else:
        try:
            loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
            if not isinstance(loaded, dict):
                read_blockers.append("evidence_json_not_an_object")
        except json.JSONDecodeError as exc:
            read_blockers.append(f"evidence_json_unparseable:{exc.msg}")

    codeowners_record = payload.get("codeowners")
    codeowners_input: dict[str, Any] | None = None
    if isinstance(codeowners_record, dict):
        codeowners_input = dict(codeowners_record)
        # The gate observes the file itself rather than trusting a "present" flag.
        codeowners_input["codeowners_path"] = str(codeowners_path)
        codeowners_input["present"] = codeowners_file.is_file()

    branch_record = payload.get("branch_protection")
    evidence = build_review_evidence(
        subject=str(payload.get("subject") or ""),
        author_id=str(payload.get("author_id") or ""),
        reviewed_commit_sha=str(payload.get("reviewed_commit_sha") or ""),
        reviews=payload.get("reviews") if isinstance(payload.get("reviews"), list) else (),
        branch_protection=branch_record if isinstance(branch_record, dict) else None,
        codeowners=codeowners_input,
    )
    evidence_payload = evidence.to_dict()
    violations = list(
        dict.fromkeys([*read_blockers, *evidence_payload.get("violations", [])])
    )
    ready = not violations

    summary: dict[str, Any] = {
        "packet_type": "independent_review_evidence_gate",
        "review_evidence_schema_version": REVIEW_EVIDENCE_SCHEMA_VERSION,
        "status": STATUS_READY if ready else STATUS_BLOCKED,
        "ready": ready,
        "evidence_json": str(evidence_json),
        "codeowners_path": str(codeowners_path),
        "codeowners_present": codeowners_file.is_file(),
        "subject": evidence_payload["subject"],
        "author_id": evidence_payload["author_id"],
        "reviewed_commit_sha": evidence_payload["reviewed_commit_sha"],
        "evidence_hash": evidence_payload["evidence_hash"],
        "review_count": evidence_payload["review_count"],
        "approved_review_count": evidence_payload["approved_review_count"],
        "author_distinct_reviewer_count": evidence_payload["author_distinct_reviewer_count"],
        "required_review_roles": list(REQUIRED_REVIEW_ROLES),
        "role_reviewers": evidence_payload["role_reviewers"],
        "admin_bypass_allowed": evidence_payload["admin_bypass_allowed"],
        "violation_count": len(violations),
        "violations": violations,
        "next_required_step": _next_operator_step(violations),
        "github_contacted": False,
        "branch_protection_mutated": False,
        "merge_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "review_evidence": evidence_payload}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Independent Review Evidence Gate (current)",
        "",
        "Generated receipt. Edit the operator evidence record and regenerate; do not hand-edit here.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- subject: `{summary.get('subject')}`",
        f"- author_id: `{summary.get('author_id')}`",
        f"- reviewed_commit_sha: `{summary.get('reviewed_commit_sha')}`",
        f"- evidence_hash: `{summary.get('evidence_hash')}`",
        f"- author_distinct_reviewer_count: `{summary.get('author_distinct_reviewer_count')}`",
        f"- admin_bypass_allowed: `{summary.get('admin_bypass_allowed')}`",
        f"- codeowners_present: `{summary.get('codeowners_present')}`",
        f"- violation_count: `{summary.get('violation_count')}`",
        "",
        "## Required Review Roles",
        "",
    ]
    role_reviewers = summary.get("role_reviewers") or {}
    for role in REQUIRED_REVIEW_ROLES:
        reviewers = role_reviewers.get(role) or []
        lines.append(f"- {role}: `{','.join(reviewers) or 'unsatisfied'}`")
    lines.extend(["", "## Violations", ""])
    violations = summary.get("violations") or []
    if violations:
        lines.extend(f"- `{violation}`" for violation in violations)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Required Step",
            "",
            f"{summary.get('next_required_step', '')}",
            "",
            "## Claim Boundary",
            "",
            f"{summary.get('claim_boundary', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate operator-recorded independent review evidence (offline)."
    )
    parser.add_argument("--evidence-json", default=DEFAULT_EVIDENCE_JSON)
    parser.add_argument("--codeowners-path", default=DEFAULT_CODEOWNERS_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_independent_review_evidence_gate(
        evidence_json=args.evidence_json,
        codeowners_path=args.codeowners_path,
    )
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.out_md:
        out_md = _resolve(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(packet), encoding="utf-8")
    summary = packet["summary"]
    if not args.quiet:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
