#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_E2E_JSON = "runs/api_docking_dispatch_e2e_evidence_current.json"
DEFAULT_RESTRICTED_JSON = "runs/restricted_unattended_execution_readiness_current.json"
DEFAULT_SMOKE_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_PRODUCT_BUNDLE_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_OUT_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_OUT_CSV = "runs/api_customer_flow_release_evidence_current.csv"
DEFAULT_OUT_MD = "runs/api_customer_flow_release_evidence_current.md"

CLAIM_BOUNDARY = (
    "API customer-flow release evidence only; it aggregates current local artifacts proving the restricted "
    "docking customer flow from product ledger dispatch through worker lease, validated runner completion, signed "
    "result manifest, and bundle-validation gates. It does not start services, run docking, upload data, expose a "
    "hosted endpoint, widen scope, or mutate external state."
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


def _sha256_file(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_path_from_smoke(smoke: dict[str, Any]) -> Path:
    manifest = _text(smoke.get("result_manifest") or smoke.get("result_manifest_path"))
    if manifest:
        return _resolve(manifest)
    result_file = _text(smoke.get("result_file"))
    if result_file:
        return Path(result_file).parent / "result_manifest.json"
    return Path("")


def _verify_manifest_from_smoke(smoke: dict[str, Any]) -> tuple[bool, str, str]:
    if smoke.get("result_manifest_signature_verified") is True:
        return True, _text(smoke.get("result_manifest")), _text(smoke.get("result_manifest_key_id"))
    manifest_path = _manifest_path_from_smoke(smoke)
    if not manifest_path.is_file():
        return False, str(manifest_path) if str(manifest_path) != "." else "", ""
    try:
        from api.result_manifest import verify_result_manifest

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, str(manifest_path), ""
    if not isinstance(manifest, dict):
        return False, str(manifest_path), ""
    signing_key = os.environ.get("API_RESULT_MANIFEST_SIGNING_KEY", "tier-alpha-local-smoke-signing-key")
    return verify_result_manifest(manifest, signing_key=signing_key), str(manifest_path), _text(
        manifest.get("signature_key_id")
    )


def _ledger_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    direct = smoke.get("ledger_payload")
    if isinstance(direct, dict):
        return direct
    jobs_dir = _text(smoke.get("jobs_dir"))
    job_id = _text(smoke.get("job_id"))
    if not jobs_dir or not job_id:
        return {}
    return _read_json_if_present(_resolve(jobs_dir) / f"{job_id}.json")


def _status_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    status_json = _text(smoke.get("status_json"))
    return _read_json_if_present(status_json) if status_json else {}


def _runner_execution_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    direct = smoke.get("runner_execution_payload")
    if isinstance(direct, dict):
        return direct
    runner_execution = _text(smoke.get("runner_execution"))
    if not runner_execution:
        runner_execution = _text(_status_from_smoke(smoke).get("runner_execution"))
    return _read_json_if_present(runner_execution) if runner_execution else {}


def _row(check_id: str, passed: bool, observed: str, required: str, reason: str, artifact_path: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "reason": reason,
        "artifact_path": artifact_path,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_api_customer_flow_release_evidence(
    *,
    e2e_packet: dict[str, Any],
    restricted_packet: dict[str, Any],
    smoke_packet: dict[str, Any],
    product_bundle_packet: dict[str, Any],
    delivery_evidence_packet: dict[str, Any],
    pilot_packet: dict[str, Any],
    e2e_path: str = DEFAULT_E2E_JSON,
    restricted_path: str = DEFAULT_RESTRICTED_JSON,
    smoke_path: str = DEFAULT_SMOKE_JSON,
    product_bundle_path: str = DEFAULT_PRODUCT_BUNDLE_JSON,
    delivery_evidence_path: str = DEFAULT_DELIVERY_EVIDENCE_JSON,
    pilot_path: str = DEFAULT_PILOT_JSON,
) -> dict[str, Any]:
    e2e = _summary(e2e_packet)
    restricted = _summary(restricted_packet)
    smoke = _summary(smoke_packet)
    product_bundle = _summary(product_bundle_packet)
    delivery = _summary(delivery_evidence_packet)
    pilot = _summary(pilot_packet)
    dispatch = smoke_packet.get("dispatch_outcome") if isinstance(smoke_packet.get("dispatch_outcome"), dict) else {}
    smoke_ledger = _ledger_from_smoke(smoke_packet)
    runner_execution = _runner_execution_from_smoke(smoke_packet)
    manifest_verified, manifest_path, manifest_key_id = _verify_manifest_from_smoke(smoke_packet)
    smoke_evidence_mode = _text(smoke.get("evidence_mode"))
    recovered_live_job = (
        smoke_evidence_mode == "live_job_recovered_from_completed_artifacts"
        and smoke_packet.get("recovered_from_completed_artifacts") is True
    )
    runner_execution_ok = (
        smoke_packet.get("runner_execution_ok") is True
        or (
            runner_execution.get("ok") is True
            and _int(runner_execution.get("returncode")) == 0
            and runner_execution.get("timed_out") is not True
        )
    )
    worker_dispatch_enqueued = smoke_packet.get("worker_dispatch_enqueued") is True or smoke_ledger.get(
        "worker_dispatch_enqueued"
    ) is True
    ledger_progress_state = _text(
        smoke_packet.get("ledger_progress_state") or smoke_ledger.get("progress_state") or smoke_ledger.get("current_step")
    )
    recovered_live_artifacts_ready = (
        recovered_live_job
        and manifest_verified
        and _text(smoke_packet.get("result_manifest_status")) == "completed"
        and runner_execution_ok
        and worker_dispatch_enqueued
    )

    live_e2e_ready = (
        _text(e2e.get("status")) == "api_docking_dispatch_e2e_ready"
        and e2e.get("wiring_ready") is True
        and _text(e2e.get("evidence_mode")) == "live_job"
        and _text(e2e_packet.get("ledger_worker_state")) == "completed_fail_closed"
        and _text(e2e_packet.get("simulation_sync_status")) == "completed"
    )
    live_smoke_ready = (
        _text(smoke.get("status")) == "tier_alpha_adrb2_dispatch_smoke_pass"
        and (smoke_evidence_mode == "live_job" or recovered_live_artifacts_ready)
        and smoke.get("api_validated_runner_enabled") is True
        and smoke_packet.get("worker_ran") is True
        and _text(smoke_packet.get("sqlite_job_status")) == "completed"
        and _text(smoke_packet.get("ledger_worker_state")) == "completed_fail_closed"
        and _text(smoke_packet.get("simulation_sync_status")) == "completed"
    )
    standard_worker_lease_ready = (
        live_smoke_ready
        and dispatch.get("dispatched") is True
        and _text(dispatch.get("reason")) == "eligible"
        and _text((dispatch.get("enqueue") or {}).get("sqlite_status")) == "submitted"
    )
    recovered_worker_lease_ready = (
        live_smoke_ready
        and recovered_live_artifacts_ready
        and dispatch.get("dispatched") is True
        and _text(dispatch.get("reason")) == "completed_artifact_recovered_after_parent_wait"
        and ledger_progress_state == "worker_dispatch_completed"
    )
    worker_lease_ready = standard_worker_lease_ready or recovered_worker_lease_ready
    signed_manifest_ready = (
        manifest_verified
        and bool(manifest_path)
        and _resolve(manifest_path).is_file()
        and bool(_sha256_file(manifest_path))
        and _text(smoke_packet.get("result_file"))
        and smoke_packet.get("htvs_summary_exists") is True
    )
    bundle_validation_ready = (
        _text(product_bundle.get("status")) == "product_bundle_contract_ready"
        and product_bundle.get("bundle_validation_passed") is True
        and _text(delivery.get("status")) == "product_delivery_evidence_contract_ready"
        and delivery.get("bundle_validation_passed") is True
        and delivery.get("delivery_ready_claim_allowed") is True
        and _text(pilot.get("status")) == "product_pilot_packet_ready"
        and pilot.get("bundle_validation_passed") is True
        and pilot.get("pilot_delivery_ready") is True
    )
    restricted_runtime_ready = (
        _text(restricted.get("status")) == "restricted_unattended_execution_runtime_ready"
        and restricted.get("restricted_unattended_execution_ready") is True
        and restricted.get("restricted_unattended_execution_runtime_ready") is True
        and restricted.get("general_platform_claim_allowed") is False
    )
    rows = [
        _row(
            "api_dispatch_live_job_ready",
            live_e2e_ready,
            (
                f"status={_text(e2e.get('status'))};evidence_mode={_text(e2e.get('evidence_mode'))};"
                f"ledger={_text(e2e_packet.get('ledger_worker_state'))};sync={_text(e2e_packet.get('simulation_sync_status'))}"
            ),
            "api_docking_dispatch_e2e_ready;evidence_mode=live_job;ledger_worker_state=completed_fail_closed;simulation_sync_status=completed",
            "Formal release evidence must use the live dispatch smoke path, not only synthetic wiring proof.",
            e2e_path,
        ),
        _row(
            "tier_alpha_smoke_live_job_ready",
            live_smoke_ready,
            (
                f"status={_text(smoke.get('status'))};evidence_mode={smoke_evidence_mode};"
                f"recovered={smoke_packet.get('recovered_from_completed_artifacts') is True};"
                f"runner_enabled={smoke.get('api_validated_runner_enabled')};"
                f"worker_ran={smoke_packet.get('worker_ran')};sqlite={_text(smoke_packet.get('sqlite_job_status'))};"
                f"ledger={_text(smoke_packet.get('ledger_worker_state'))};sync={_text(smoke_packet.get('simulation_sync_status'))};"
                f"manifest_verified={manifest_verified};runner_execution_ok={runner_execution_ok}"
            ),
            "tier_alpha_adrb2_dispatch_smoke_pass with live_job or signed recovered live-job artifacts, validated runner enabled, and completed worker ledger sync",
            "The customer path must prove the validated runner worker actually drained a queued restricted job.",
            smoke_path,
        ),
        _row(
            "worker_lease_and_runner_profile_ready",
            worker_lease_ready,
            (
                f"dispatched={dispatch.get('dispatched')};reason={_text(dispatch.get('reason'))};"
                f"sqlite_status={_text((dispatch.get('enqueue') or {}).get('sqlite_status'))};"
                f"worker_dispatch_enqueued={worker_dispatch_enqueued};ledger_progress_state={ledger_progress_state}"
            ),
            "dispatch_outcome.dispatched=true with either reason=eligible/enqueue.sqlite_status=submitted or signed recovered artifacts proving worker_dispatch_enqueued and worker_dispatch_completed",
            "The flow must prove a dispatch-eligible ledger record was converted into a worker-leaseable queue job.",
            smoke_path,
        ),
        _row(
            "signed_result_manifest_ready",
            signed_manifest_ready,
            (
                f"manifest={manifest_path or 'missing'};signature_verified={manifest_verified};"
                f"key_id={manifest_key_id or 'missing'};result_file={_text(smoke_packet.get('result_file')) or 'missing'};"
                f"htvs_summary_exists={smoke_packet.get('htvs_summary_exists')}"
            ),
            "signed result_manifest.json present and signature verified; HTVS summary result file present",
            "Release evidence must bind the worker result to a signed manifest instead of an unsigned local file path.",
            smoke_path,
        ),
        _row(
            "bundle_validation_ready",
            bundle_validation_ready,
            (
                f"bundle={_text(product_bundle.get('status'))};bundle_validation={product_bundle.get('bundle_validation_passed')};"
                f"delivery={_text(delivery.get('status'))};delivery_claim={delivery.get('delivery_ready_claim_allowed')};"
                f"pilot={_text(pilot.get('status'))};pilot_delivery={pilot.get('pilot_delivery_ready')}"
            ),
            "product bundle, delivery evidence, and pilot packet all report bundle validation passed",
            "Customer-flow release evidence must terminate in the same validated bundle gates used for delivery claims.",
            f"{product_bundle_path};{delivery_evidence_path};{pilot_path}",
        ),
        _row(
            "restricted_unattended_runtime_ready",
            restricted_runtime_ready,
            (
                f"status={_text(restricted.get('status'))};ready={restricted.get('restricted_unattended_execution_ready')};"
                f"runtime={restricted.get('restricted_unattended_execution_runtime_ready')};"
                f"general_platform_claim_allowed={restricted.get('general_platform_claim_allowed')}"
            ),
            "restricted_unattended_execution_runtime_ready with general platform claim still false",
            "The API flow can be formal release evidence only for restricted gpcr/ion_channel/kinase scope.",
            restricted_path,
        ),
    ]
    blockers = [row for row in rows if row["release_blocker"]]
    ready = not blockers
    summary = {
        "packet_type": "api_customer_flow_release_evidence",
        "status": "api_customer_flow_release_evidence_ready" if ready else "blocked_api_customer_flow_release_evidence",
        "formal_release_evidence_ready": ready,
        "clean_install_flow_ready": ready,
        "check_count": len(rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "blocked_check_ids": [row["check_id"] for row in blockers],
        "e2e_evidence_mode": _text(e2e.get("evidence_mode")),
        "tier_alpha_evidence_mode": smoke_evidence_mode,
        "tier_alpha_smoke_status": _text(smoke.get("status")),
        "tier_alpha_recovered_from_completed_artifacts": recovered_live_job,
        "tier_alpha_recovered_live_artifacts_ready": recovered_live_artifacts_ready,
        "tier_alpha_runner_execution_ok": runner_execution_ok,
        "tier_alpha_worker_dispatch_enqueued": worker_dispatch_enqueued,
        "result_manifest": manifest_path,
        "result_manifest_sha256": _sha256_file(manifest_path) if manifest_path else "",
        "result_manifest_signature_verified": manifest_verified,
        "bundle_validation_ready": bundle_validation_ready,
        "restricted_unattended_runtime_ready": restricted_runtime_ready,
        "allowed_scope_families": list(restricted.get("allowed_scope_families") or ["gpcr", "ion_channel", "kinase"]),
        "general_platform_claim_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "API customer flow release evidence is ready for restricted-scope release gates."
            if ready
            else "Run the Tier α dispatch smoke, rebuild API E2E/restricted execution evidence, and refresh bundle-validation artifacts."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# API Customer Flow Release Evidence",
        "",
        f"- status: `{s['status']}`",
        f"- formal_release_evidence_ready: `{s['formal_release_evidence_ready']}`",
        f"- clean_install_flow_ready: `{s['clean_install_flow_ready']}`",
        f"- result_manifest_signature_verified: `{s['result_manifest_signature_verified']}`",
        f"- bundle_validation_ready: `{s['bundle_validation_ready']}`",
        f"- restricted_unattended_runtime_ready: `{s['restricted_unattended_runtime_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build formal API customer-flow release evidence.")
    parser.add_argument("--e2e-json", default=DEFAULT_E2E_JSON)
    parser.add_argument("--restricted-json", default=DEFAULT_RESTRICTED_JSON)
    parser.add_argument("--smoke-json", default=DEFAULT_SMOKE_JSON)
    parser.add_argument("--product-bundle-json", default=DEFAULT_PRODUCT_BUNDLE_JSON)
    parser.add_argument("--delivery-evidence-json", default=DEFAULT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--pilot-json", default=DEFAULT_PILOT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_api_customer_flow_release_evidence(
        e2e_packet=_read_json_if_present(args.e2e_json),
        restricted_packet=_read_json_if_present(args.restricted_json),
        smoke_packet=_read_json_if_present(args.smoke_json),
        product_bundle_packet=_read_json_if_present(args.product_bundle_json),
        delivery_evidence_packet=_read_json_if_present(args.delivery_evidence_json),
        pilot_packet=_read_json_if_present(args.pilot_json),
        e2e_path=args.e2e_json,
        restricted_path=args.restricted_json,
        smoke_path=args.smoke_json,
        product_bundle_path=args.product_bundle_json,
        delivery_evidence_path=args.delivery_evidence_json,
        pilot_path=args.pilot_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
