#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPETITION_ROLLUP_JSON = "runs/competition_benchmark_rollup_current.json"
DEFAULT_OUT_JSON = "runs/package_b_competition_bridge_current.json"
DEFAULT_OUT_MD = "docs/package_b_competition_bridge_current.md"

CLAIM_BOUNDARY_TOKENS = (
    "competition credibility evidence only",
    "ligand commercial claims remain locked",
    "Package B public ligand benchmark evidence",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bool_text(value: Any) -> str:
    return "true" if value is True else "false" if value is False else _text(value)


def _list_text(value: Any) -> str:
    values = _string_list(value)
    return "; ".join(values) if values else "none"


def _bridge_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "bridge_check": "competition_rollup",
            "artifact_path": DEFAULT_COMPETITION_ROLLUP_JSON,
            "observed_status": _text(summary.get("status")),
            "ready": _bool_true(summary.get("competition_benchmark_rollup_ready")),
            "claim_role": _text(summary.get("competition_evidence_role")),
            "claim_allowed": _bool_true(summary.get("competition_ligand_commercial_claim_allowed")),
            "blockers": _string_list(summary.get("competition_benchmark_blockers")),
        },
        {
            "bridge_check": "competition_credibility_evidence",
            "artifact_path": DEFAULT_COMPETITION_ROLLUP_JSON,
            "observed_status": "evidence_ready"
            if _bool_true(summary.get("competition_credibility_evidence_ready"))
            else "evidence_blocked",
            "ready": _bool_true(summary.get("competition_credibility_evidence_ready")),
            "claim_role": "competition_credibility_not_ligand_claim",
            "claim_allowed": False,
            "blockers": _string_list(summary.get("competition_credibility_evidence_blockers")),
        },
        {
            "bridge_check": "package_b_public_benchmark_contract",
            "artifact_path": _text(summary.get("package_b_public_benchmark_contract_artifact_path")),
            "observed_status": _text(summary.get("package_b_public_benchmark_contract_status")),
            "ready": _bool_true(summary.get("package_b_ligand_public_benchmark_foundation_ready")),
            "claim_role": "foundation_only",
            "claim_allowed": False,
            "blockers": []
            if _bool_true(summary.get("package_b_ligand_public_benchmark_foundation_ready"))
            else ["package_b_ligand_public_benchmark_foundation_not_ready"],
        },
        {
            "bridge_check": "package_b_claim_grade_public_benchmark",
            "artifact_path": _text(summary.get("package_b_refine_tier_public_benchmark_artifact_path")),
            "observed_status": _text(summary.get("package_b_refine_tier_public_benchmark_status")),
            "ready": _bool_true(summary.get("package_b_claim_grade_public_benchmark_ready")),
            "claim_role": "ligand_claim_unlock_dependency",
            "claim_allowed": False,
            "blockers": _string_list(summary.get("package_b_claim_grade_blockers")),
        },
        {
            "bridge_check": "competition_ligand_claim_gate",
            "artifact_path": DEFAULT_COMPETITION_ROLLUP_JSON,
            "observed_status": _text(summary.get("status")),
            "ready": _int(summary.get("competition_ligand_claim_blocker_count")) == 0,
            "claim_role": "fail_closed_gate",
            "claim_allowed": _bool_true(summary.get("competition_ligand_commercial_claim_allowed")),
            "blockers": _string_list(summary.get("competition_ligand_claim_blockers")),
        },
        {
            "bridge_check": "github_raw_data_policy",
            "artifact_path": DEFAULT_COMPETITION_ROLLUP_JSON,
            "observed_status": "policy_ready"
            if _bool_true(summary.get("github_raw_data_policy_ready"))
            else "policy_blocked",
            "ready": _bool_true(summary.get("github_raw_data_policy_ready")),
            "claim_role": "raw_payloads_outside_git",
            "claim_allowed": False,
            "blockers": _string_list(summary.get("github_raw_data_policy_blockers")),
        },
    ]


def build_package_b_competition_bridge(
    *,
    competition_rollup_json: str | Path = DEFAULT_COMPETITION_ROLLUP_JSON,
) -> dict[str, Any]:
    rollup = _read_json(competition_rollup_json)
    summary = _summary(rollup)
    claim_boundary = _text(summary.get("claim_boundary"))
    missing_boundary_tokens = [
        token for token in CLAIM_BOUNDARY_TOKENS if token not in claim_boundary
    ]
    blockers: list[str] = []
    if not summary:
        blockers.append("competition_benchmark_rollup_missing")
    if _text(summary.get("status")) != "competition_benchmark_rollup_ready":
        blockers.append("competition_benchmark_rollup_not_ready")
    if not _bool_true(summary.get("competition_benchmark_rollup_ready")):
        blockers.append("competition_benchmark_rollup_ready_flag_false")
    if _text(summary.get("competition_evidence_role")) != "competition_credibility_evidence_only":
        blockers.append("competition_evidence_role_not_claim_locked")
    if _bool_true(summary.get("competition_ligand_commercial_claim_allowed")):
        blockers.append("competition_ligand_claim_promotion_unexpectedly_allowed")
    if not _bool_true(summary.get("package_b_required_for_ligand_commercial_claims")):
        blockers.append("package_b_dependency_not_required")
    if _bool_true(summary.get("package_b_refine_tier_external_state_mutated")):
        blockers.append("package_b_refine_tier_external_state_mutated")
    if _bool_true(summary.get("package_b_refine_tier_apply_external_state_mutated")):
        blockers.append("package_b_refine_tier_apply_external_state_mutated")
    if missing_boundary_tokens:
        blockers.append("claim_boundary_missing_required_tokens")

    bridge_ready = not blockers
    package_b_claim_ready = _bool_true(summary.get("package_b_claim_grade_public_benchmark_ready"))
    ligand_claim_blockers = _string_list(summary.get("competition_ligand_claim_blockers"))
    raw_data_blockers = _string_list(summary.get("github_raw_data_policy_blockers"))
    underlying_blockers = _string_list(summary.get("competition_benchmark_blockers"))
    raw_data_stored_in_repo = _int(summary.get("github_raw_data_git_tracked_total_count")) > 0
    raw_data_free = _bool_true(summary.get("github_raw_data_policy_ready")) and not raw_data_stored_in_repo
    competition_credibility_only = (
        _text(summary.get("competition_evidence_role"))
        == "competition_credibility_evidence_only"
    )
    competition_credibility_ready = _bool_true(summary.get("competition_credibility_evidence_ready"))
    github_raw_data_policy_ready = _bool_true(summary.get("github_raw_data_policy_ready"))
    ligand_claim_unlock_blockers = list(
        dict.fromkeys(
            [
                *(
                    []
                    if competition_credibility_ready
                    else ["competition_credibility_evidence_not_ready"]
                ),
                *(
                    []
                    if github_raw_data_policy_ready
                    else ["github_raw_data_policy_not_ready"]
                ),
                *(
                    []
                    if package_b_claim_ready
                    else ["package_b_claim_grade_public_benchmark_not_ready"]
                ),
                *ligand_claim_blockers,
            ]
        )
    )
    ligand_commercial_claim_unlock_ready = bool(
        bridge_ready
        and competition_credibility_ready
        and github_raw_data_policy_ready
        and package_b_claim_ready
        and not ligand_claim_unlock_blockers
    )
    next_required_step = (
        _text(summary.get("competition_credibility_extension_primary_next_action"))
        or _text(summary.get("competition_benchmark_next_required_step"))
        or _text(summary.get("package_b_bridge_next_action"))
        or _text(summary.get("competition_credibility_evidence_primary_blocker"))
        or "Complete Package B claim-grade public benchmark receipts before any ligand commercial claim."
    )

    bridge_summary = {
        "packet_type": "package_b_competition_bridge",
        "status": "package_b_competition_bridge_ready"
        if bridge_ready
        else "blocked_package_b_competition_bridge",
        "package_b_competition_bridge_ready": bridge_ready,
        "blocker_count": len(blockers),
        "primary_blocker": blockers[0] if blockers else "",
        "blockers": blockers,
        "bridge_claim_lock_ready": bridge_ready
        and not _bool_true(summary.get("competition_ligand_commercial_claim_allowed")),
        "competition_credibility_only": competition_credibility_only,
        "competition_rollup_artifact_path": str(competition_rollup_json),
        "competition_rollup_status": _text(summary.get("status")),
        "competition_rollup_artifact_ready": _bool_true(
            summary.get("competition_benchmark_rollup_artifact_ready")
        )
        or _bool_true(summary.get("competition_benchmark_rollup_ready")),
        "competition_rollup_ready": _bool_true(summary.get("competition_benchmark_rollup_ready")),
        "competition_credibility_evidence_ready": competition_credibility_ready,
        "competition_credibility_evidence_blocker_count": _int(
            summary.get("competition_credibility_evidence_blocker_count")
        ),
        "competition_credibility_evidence_blockers": _string_list(
            summary.get("competition_credibility_evidence_blockers")
        ),
        "competition_evidence_role": _text(summary.get("competition_evidence_role")),
        "competition_ligand_commercial_claim_allowed": False,
        "ligand_commercial_claim_unlock_ready": ligand_commercial_claim_unlock_ready,
        "ligand_commercial_claim_unlock_prerequisites_ready": (
            ligand_commercial_claim_unlock_ready
        ),
        "ligand_commercial_claim_unlock_requires_separate_promotion_gate": True,
        "ligand_commercial_claim_unlock_blocker_count": len(ligand_claim_unlock_blockers),
        "ligand_commercial_claim_unlock_blockers": ligand_claim_unlock_blockers,
        "ligand_commercial_claim_unlocked": False,
        "commercial_claim_unlocked": False,
        "claim_promotion_allowed": False,
        "observed_competition_ligand_commercial_claim_allowed": _bool_true(
            summary.get("competition_ligand_commercial_claim_allowed")
        ),
        "package_b_required_for_ligand_commercial_claims": _bool_true(
            summary.get("package_b_required_for_ligand_commercial_claims")
        ),
        "package_b_ligand_suite_ids": _string_list(summary.get("package_b_ligand_suite_ids")),
        "package_b_ligand_suite_count": _int(summary.get("package_b_ligand_suite_count")),
        "package_b_public_benchmark_contract_artifact_path": _text(
            summary.get("package_b_public_benchmark_contract_artifact_path")
        ),
        "package_b_public_benchmark_contract_status": _text(
            summary.get("package_b_public_benchmark_contract_status")
        ),
        "package_b_ligand_public_benchmark_foundation_ready": _bool_true(
            summary.get("package_b_ligand_public_benchmark_foundation_ready")
        ),
        "package_b_refine_tier_public_benchmark_artifact_path": _text(
            summary.get("package_b_refine_tier_public_benchmark_artifact_path")
        ),
        "package_b_refine_tier_public_benchmark_status": _text(
            summary.get("package_b_refine_tier_public_benchmark_status")
        ),
        "package_b_claim_grade_public_benchmark_ready": package_b_claim_ready,
        "package_b_claim_grade_blocker_count": _int(
            summary.get("package_b_claim_grade_blocker_count")
        ),
        "package_b_claim_grade_blockers": _string_list(
            summary.get("package_b_claim_grade_blockers")
        ),
        "competition_ligand_claim_package_b_dependency_ready": _bool_true(
            summary.get("competition_ligand_claim_package_b_dependency_ready")
        ),
        "competition_ligand_claim_blocker_count": len(ligand_claim_blockers),
        "competition_ligand_claim_blockers": ligand_claim_blockers,
        "github_raw_data_policy_ready": github_raw_data_policy_ready,
        "github_raw_data_git_tracked_total_count": _int(
            summary.get("github_raw_data_git_tracked_total_count")
        ),
        "github_raw_data_policy_blockers": raw_data_blockers,
        "raw_data_stored_in_repo": raw_data_stored_in_repo,
        "raw_data_free": raw_data_free,
        "github_safe_allowed_artifact_classes": [
            "source_manifests",
            "checksum_manifests",
            "materialization_manifests",
            "scorecard_builders",
            "scorecard_receipts",
            "claim_boundary_docs",
        ],
        "github_raw_payloads_allowed": False,
        "underlying_competition_benchmark_blocker_count": len(underlying_blockers),
        "underlying_competition_benchmark_blockers": underlying_blockers,
        "bridge_blocker_count": len(blockers),
        "bridge_blockers": blockers,
        "missing_claim_boundary_tokens": missing_boundary_tokens,
        "package_b_bridge_next_action": _text(summary.get("package_b_bridge_next_action"))
        or "Complete Package B claim-grade public benchmark receipts before any ligand commercial claim.",
        "next_required_step": next_required_step,
        "claim_boundary": claim_boundary,
        "execution_enabled": False,
        "external_state_mutated": False,
    }
    return {"summary": bridge_summary, "rows": _bridge_rows(summary)}


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Package B Competition Bridge",
        "",
        "Machine-rendered claim-boundary bridge for the competition benchmark lane.",
        "",
        "## Snapshot",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Status | `{summary['status']}` |",
        f"| Bridge ready | `{_bool_text(summary['package_b_competition_bridge_ready'])}` |",
        f"| Claim lock ready | `{_bool_text(summary['bridge_claim_lock_ready'])}` |",
        f"| Competition evidence role | `{summary['competition_evidence_role'] or 'missing'}` |",
        f"| Competition rollup artifact ready | `{_bool_text(summary['competition_rollup_artifact_ready'])}` |",
        f"| Competition credibility evidence ready | `{_bool_text(summary['competition_credibility_evidence_ready'])}` |",
        f"| Ligand commercial claim allowed | `{_bool_text(summary['competition_ligand_commercial_claim_allowed'])}` |",
        f"| Ligand commercial claim unlock ready | `{_bool_text(summary['ligand_commercial_claim_unlock_ready'])}` |",
        "| Ligand commercial claim unlock requires separate promotion gate | "
        f"`{_bool_text(summary['ligand_commercial_claim_unlock_requires_separate_promotion_gate'])}` |",
        f"| Ligand commercial claim unlock blockers | `{_list_text(summary['ligand_commercial_claim_unlock_blockers'])}` |",
        f"| Package B required | `{_bool_text(summary['package_b_required_for_ligand_commercial_claims'])}` |",
        f"| Package B claim-grade ready | `{_bool_text(summary['package_b_claim_grade_public_benchmark_ready'])}` |",
        f"| GitHub raw-data policy ready | `{_bool_text(summary['github_raw_data_policy_ready'])}` |",
        f"| Raw data stored in repo | `{_bool_text(summary['raw_data_stored_in_repo'])}` |",
        f"| Raw-data-free evidence | `{_bool_text(summary['raw_data_free'])}` |",
        f"| Git-tracked raw payloads | `{summary['github_raw_data_git_tracked_total_count']}` |",
        f"| Bridge blockers | `{_list_text(summary['bridge_blockers'])}` |",
        f"| Ligand claim blockers | `{_list_text(summary['competition_ligand_claim_blockers'])}` |",
        f"| Next action | {summary['package_b_bridge_next_action']} |",
        f"| Next required step | {summary['next_required_step']} |",
        "",
        "## GitHub-Safe Artifact Classes",
        "",
        "| Class | Allowed |",
        "| --- | --- |",
    ]
    for artifact_class in summary["github_safe_allowed_artifact_classes"]:
        lines.append(f"| `{artifact_class}` | `true` |")
    lines.extend(
        [
            "| `raw_benchmark_payloads` | `false` |",
            "",
            "## Bridge Checks",
            "",
            "| Check | Ready | Claim allowed | Blockers |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['bridge_check']}` | `{_bool_text(row['ready'])}` | "
            f"`{_bool_text(row['claim_allowed'])}` | `{_list_text(row['blockers'])}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    return "\n".join(lines)


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed Package B bridge from the competition rollup."
    )
    parser.add_argument("--competition-rollup-json", default=DEFAULT_COMPETITION_ROLLUP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_package_b_competition_bridge(
        competition_rollup_json=args.competition_rollup_json
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
