#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.builder_table_utils import write_csv_rows

DEFAULT_API_FLOW_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_ROLLOUT_JSON = "runs/product_rollout_execution_readiness_current.json"
DEFAULT_RELEASE_BUNDLE_JSON = "runs/product_release_bundle_current.json"
DEFAULT_COMMERCIAL_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_LICENSE_JSON = "runs/product_license_decision_gate_current.json"
DEFAULT_THIRD_PARTY_LICENSE_JSON = "runs/third_party_license_review_gate_current.json"
DEFAULT_ENGINE_JSON = "runs/engine_refinement_tier_readiness_current.json"
DEFAULT_OUT_JSON = "runs/product_launch_r4_preflight_current.json"
DEFAULT_OUT_CSV = "runs/product_launch_r4_preflight_current.csv"
DEFAULT_OUT_MD = "runs/product_launch_r4_preflight_current.md"

REQUIRED_R4_FIELDS = ["target", "action", "impact", "risk", "rollback", "verification"]
REQUIRED_ROLLOUT_TOKENS = ["APPROVE_PRODUCT_ROLLOUT", "APPROVE_HOSTED_PRODUCT_API_EXPOSURE"]
CLAIM_BOUNDARY = (
    "Product launch R4 preflight only; it aggregates local customer-flow, rollout, release-bundle, "
    "commercial-independence, license, third-party review, and restricted engine-readiness evidence before a "
    "separate explicit operator confirmation. It does not deploy, push images, expose hosted endpoints, contact "
    "providers, run scientific profiles, widen claim scope, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _row(check_id: str, passed: bool, observed: str, required: str, source_artifact: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "blocked",
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "release_blocker": not passed,
        "r4_confirmation_required": True,
        "launch_executed": False,
        "external_state_mutated": False,
    }


def build_product_launch_r4_preflight(
    *,
    api_flow_packet: dict[str, Any],
    rollout_packet: dict[str, Any],
    release_bundle_packet: dict[str, Any],
    commercial_packet: dict[str, Any],
    license_packet: dict[str, Any],
    third_party_license_packet: dict[str, Any],
    engine_packet: dict[str, Any],
    api_flow_path: str = DEFAULT_API_FLOW_JSON,
    rollout_path: str = DEFAULT_ROLLOUT_JSON,
    release_bundle_path: str = DEFAULT_RELEASE_BUNDLE_JSON,
    commercial_path: str = DEFAULT_COMMERCIAL_JSON,
    license_path: str = DEFAULT_LICENSE_JSON,
    third_party_license_path: str = DEFAULT_THIRD_PARTY_LICENSE_JSON,
    engine_path: str = DEFAULT_ENGINE_JSON,
) -> dict[str, Any]:
    api = _summary(api_flow_packet)
    rollout = _summary(rollout_packet)
    release = _summary(release_bundle_packet)
    commercial = _summary(commercial_packet)
    license_summary = _summary(license_packet)
    third_party = _summary(third_party_license_packet)
    engine = _summary(engine_packet)
    release_policy = release_bundle_packet.get("operator_promotion_policy")
    release_policy = release_policy if isinstance(release_policy, dict) else {}

    api_ready = (
        _text(api.get("status")) == "api_customer_flow_release_evidence_ready"
        and _bool(api.get("formal_release_evidence_ready"))
        and _bool(api.get("result_manifest_signature_verified"))
        and _bool(api.get("external_state_mutated")) is False
        and _bool(api.get("execution_enabled")) is False
    )
    rollout_tokens = rollout.get("approval_tokens_required") if isinstance(rollout.get("approval_tokens_required"), list) else []
    rollout_ready = (
        _text(rollout.get("status")) == "product_rollout_execution_readiness_ready"
        and _bool(rollout.get("authorized_for_separate_operator_execution"))
        and _int(rollout.get("blocker_count")) == 0
        and _bool(rollout.get("rollout_executed")) is False
        and _bool(rollout.get("external_state_mutated")) is False
        and all(token in rollout_tokens for token in REQUIRED_ROLLOUT_TOKENS)
    )
    must_review = release_policy.get("must_review_fields") if isinstance(release_policy.get("must_review_fields"), list) else []
    release_ready = (
        _text(release.get("status")) == "release_bundle_ready_for_operator_review"
        and _int(release.get("blocker_count")) == 0
        and _text(release_policy.get("status")) == "operator_approval_required"
        and _bool(release_policy.get("external_state_mutation_allowed")) is False
        and all(field in must_review for field in REQUIRED_R4_FIELDS)
    )
    commercial_ready = (
        _text(commercial.get("status")) == "product_commercial_independence_gate_ready"
        and _int(commercial.get("blocker_count")) == 0
        and _bool(commercial.get("license_present"))
        and _bool(commercial.get("commercial_independent_product_claim_allowed"))
        and _bool(commercial.get("general_platform_claim_allowed")) is False
        and _bool(commercial.get("execution_enabled")) is False
        and _bool(commercial.get("external_state_mutated")) is False
    )
    license_ready = (
        _text(license_summary.get("status")) == "product_license_decision_gate_ready"
        and _bool(license_summary.get("authorized_for_license_file_creation_review"))
    )
    third_party_ready = (
        _text(third_party.get("status")) == "third_party_license_review_gate_ready"
        and _int(third_party.get("blocker_count")) == 0
        and _bool(third_party.get("external_state_mutated")) is False
    )
    engine_ready = (
        _text(engine.get("status")) == "engine_refinement_tier_ready"
        and _bool(engine.get("engine_refinement_tier_ready"))
        and _int(engine.get("blocked_count")) == 0
        and _int(engine.get("pass_count")) == _int(engine.get("check_count"))
    )
    mutation_guard_ok = (
        _bool(api.get("external_state_mutated")) is False
        and _bool(rollout.get("external_state_mutated")) is False
        and _bool(commercial.get("external_state_mutated")) is False
        and _bool(third_party.get("external_state_mutated")) is False
        and _bool(rollout.get("rollout_executed")) is False
        and _bool(rollout.get("image_pushed")) is False
        and _bool(rollout.get("service_restarted")) is False
        and _bool(rollout.get("pager_provider_contacted")) is False
    )

    rows = [
        _row(
            "api_customer_flow_release_evidence_ready",
            api_ready,
            (
                f"status={_text(api.get('status'))};formal={api.get('formal_release_evidence_ready')};"
                f"manifest_signature={api.get('result_manifest_signature_verified')};"
                f"external_state_mutated={api.get('external_state_mutated')};execution_enabled={api.get('execution_enabled')}"
            ),
            "api customer-flow release evidence ready; signed manifest verified; no execution/external mutation",
            api_flow_path,
        ),
        _row(
            "rollout_execution_preflight_ready",
            rollout_ready,
            (
                f"status={_text(rollout.get('status'))};authorized={rollout.get('authorized_for_separate_operator_execution')};"
                f"blockers={_int(rollout.get('blocker_count'))};tokens={','.join(map(str, rollout_tokens))};"
                f"rollout_executed={rollout.get('rollout_executed')}"
            ),
            "rollout readiness ready with both approval tokens recorded, zero blockers, and rollout_executed=false",
            rollout_path,
        ),
        _row(
            "release_bundle_r4_policy_bound",
            release_ready,
            (
                f"status={_text(release.get('status'))};blockers={_int(release.get('blocker_count'))};"
                f"policy={_text(release_policy.get('status'))};must_review={','.join(map(str, must_review))};"
                f"external_state_mutation_allowed={release_policy.get('external_state_mutation_allowed')}"
            ),
            "release bundle ready and operator policy requires Target/Action/Impact/Risk/Rollback/Verification review",
            release_bundle_path,
        ),
        _row(
            "commercial_independence_and_license_ready",
            commercial_ready and license_ready,
            (
                f"commercial={_text(commercial.get('status'))};license_present={commercial.get('license_present')};"
                f"commercial_claim_allowed={commercial.get('commercial_independent_product_claim_allowed')};"
                f"general_platform_claim_allowed={commercial.get('general_platform_claim_allowed')};"
                f"license_decision={_text(license_summary.get('status'))};"
                f"license_review_authorized={license_summary.get('authorized_for_license_file_creation_review')}"
            ),
            "commercial independence ready, license present, license decision gate ready, broad platform claim still false",
            f"{commercial_path};{license_path}",
        ),
        _row(
            "third_party_license_review_ready",
            third_party_ready,
            (
                f"status={_text(third_party.get('status'))};blockers={_int(third_party.get('blocker_count'))};"
                f"external_state_mutated={third_party.get('external_state_mutated')}"
            ),
            "third-party license review gate ready with zero blockers and no external mutation",
            third_party_license_path,
        ),
        _row(
            "engine_refinement_restricted_tier_ready",
            engine_ready,
            (
                f"status={_text(engine.get('status'))};ready={engine.get('engine_refinement_tier_ready')};"
                f"pass={_int(engine.get('pass_count'))}/{_int(engine.get('check_count'))};blocked={_int(engine.get('blocked_count'))}"
            ),
            "engine refinement tier ready with all checks passing under restricted accuracy claim boundary",
            engine_path,
        ),
        _row(
            "external_mutation_guard_intact",
            mutation_guard_ok,
            (
                f"api_mutated={api.get('external_state_mutated')};rollout_mutated={rollout.get('external_state_mutated')};"
                f"commercial_mutated={commercial.get('external_state_mutated')};third_party_mutated={third_party.get('external_state_mutated')};"
                f"rollout_executed={rollout.get('rollout_executed')};image_pushed={rollout.get('image_pushed')};"
                f"service_restarted={rollout.get('service_restarted')};pager_contacted={rollout.get('pager_provider_contacted')}"
            ),
            "all launch preflight inputs preserve no-execution and no-external-mutation posture",
            f"{api_flow_path};{rollout_path};{commercial_path};{third_party_license_path}",
        ),
    ]
    blockers = [row for row in rows if row["release_blocker"]]
    ready = not blockers
    summary = {
        "packet_type": "product_launch_r4_preflight",
        "status": "product_launch_r4_preflight_ready" if ready else "blocked_product_launch_r4_preflight",
        "authorized_for_r4_confirmation": ready,
        "authorized_for_external_mutation": False,
        "launch_executed": False,
        "external_state_mutated": False,
        "check_count": len(rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "blocked_check_ids": [row["check_id"] for row in blockers],
        "required_r4_fields": REQUIRED_R4_FIELDS,
        "required_rollout_tokens": REQUIRED_ROLLOUT_TOKENS,
        "source_api_customer_flow_status": _text(api.get("status")),
        "source_rollout_execution_status": _text(rollout.get("status")),
        "source_release_bundle_status": _text(release.get("status")),
        "source_commercial_independence_status": _text(commercial.get("status")),
        "source_license_decision_status": _text(license_summary.get("status")),
        "source_third_party_license_status": _text(third_party.get("status")),
        "source_engine_refinement_status": _text(engine.get("status")),
        "engine_refinement_claim_promotion_action_board_csv": _text(
            engine.get("claim_promotion_action_board_csv")
        ),
        "engine_refinement_claim_promotion_action_row_count": _int(
            engine.get("claim_promotion_action_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_status": _text(
            engine.get("claim_promotion_evidence_receipt_status")
        ),
        "engine_refinement_claim_evidence_receipt_ready": _bool(
            engine.get("claim_promotion_evidence_receipt_ready")
        ),
        "engine_refinement_claim_evidence_receipt_blocked_row_count": _int(
            engine.get("claim_promotion_evidence_receipt_blocked_row_count")
        ),
        "engine_refinement_claim_evidence_receipt_artifact": _text(
            engine.get("claim_promotion_evidence_receipt_artifact")
        ),
        "engine_refinement_claim_evidence_receipt_csv": _text(
            engine.get("claim_promotion_evidence_receipt_csv")
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Present Target/Action/Impact/Risk/Rollback/Verification and wait for explicit R4 operator confirmation before any deployment, push, hosted exposure, provider contact, or remote mutation."
            if ready
            else "Resolve blocked checks, regenerate source readiness packets, then rebuild this R4 preflight."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Launch R4 Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- authorized_for_r4_confirmation: `{s['authorized_for_r4_confirmation']}`",
        f"- authorized_for_external_mutation: `{s['authorized_for_external_mutation']}`",
        f"- launch_executed: `{s['launch_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- pass_count: `{s['pass_count']}/{s['check_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{s['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- engine_refinement_claim_evidence_receipt_artifact: `{s['engine_refinement_claim_evidence_receipt_artifact']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | `{row['source_artifact']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only product launch R4 preflight packet.")
    parser.add_argument("--api-flow-json", default=DEFAULT_API_FLOW_JSON)
    parser.add_argument("--rollout-json", default=DEFAULT_ROLLOUT_JSON)
    parser.add_argument("--release-bundle-json", default=DEFAULT_RELEASE_BUNDLE_JSON)
    parser.add_argument("--commercial-json", default=DEFAULT_COMMERCIAL_JSON)
    parser.add_argument("--license-json", default=DEFAULT_LICENSE_JSON)
    parser.add_argument("--third-party-license-json", default=DEFAULT_THIRD_PARTY_LICENSE_JSON)
    parser.add_argument("--engine-json", default=DEFAULT_ENGINE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_launch_r4_preflight(
        api_flow_packet=_read_json_if_present(args.api_flow_json),
        rollout_packet=_read_json_if_present(args.rollout_json),
        release_bundle_packet=_read_json_if_present(args.release_bundle_json),
        commercial_packet=_read_json_if_present(args.commercial_json),
        license_packet=_read_json_if_present(args.license_json),
        third_party_license_packet=_read_json_if_present(args.third_party_license_json),
        engine_packet=_read_json_if_present(args.engine_json),
        api_flow_path=args.api_flow_json,
        rollout_path=args.rollout_json,
        release_bundle_path=args.release_bundle_json,
        commercial_path=args.commercial_json,
        license_path=args.license_json,
        third_party_license_path=args.third_party_license_json,
        engine_path=args.engine_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
