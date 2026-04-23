#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact, resolve

DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_MASTER_TERMINAL_REVIEW_JSON = "runs/wetlab_master_terminal_review_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_PRIORITY3_LOG = "runs/wetlab_priority3_runtime_event_log.jsonl"
DEFAULT_NEXT3_LOG = "runs/wetlab_next3_runtime_event_log.jsonl"
DEFAULT_FINAL2_LOG = "runs/wetlab_final2_runtime_event_log.jsonl"
DEFAULT_WAVE2_LOG = "runs/wetlab_wave2_runtime_event_log.jsonl"
DEFAULT_OUT_MD = "runs/wetlab_data_quality_assessment_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _count_runtime_validation_events(paths: list[str]) -> tuple[int, int]:
    total = 0
    validation_only = 0
    for path_like in paths:
        path = resolve(path_like)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total += 1
            obj = json.loads(line)
            text = json.dumps(obj, ensure_ascii=False)
            if "workflow_validation_only_no_wetlab_claim" in text:
                validation_only += 1
    return total, validation_only


def _count_measured_assay_artifacts() -> int:
    runs_dir = resolve("runs")
    count = 0
    patterns = [
        "*measurement_result*current.*",
        "*measured_*current.*",
        "*assay_result*current.*",
        "*raw_readout*current.*",
        "*dose_response*current.*",
        "*ic50_result*current.*",
        "*ec50_result*current.*",
        "*kd_result*current.*",
        "*ki_result*current.*",
    ]
    for pattern in patterns:
        count += sum(1 for _ in runs_dir.glob(pattern))
    return count


def _band(score: int) -> str:
    if score >= 85:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def build_payload(
    master_queue: dict[str, Any],
    master_terminal_review: dict[str, Any],
    export_bundle: dict[str, Any],
    blueprint: dict[str, Any],
    runtime_log_paths: list[str],
) -> dict[str, Any]:
    mqs = _summary(master_queue)
    mtrs = _summary(master_terminal_review)
    ebs = _summary(export_bundle)
    bs = _summary(blueprint)

    queue_target_count = int(mqs.get("queue_target_count", 0) or 0)
    resolved_target_count = int(mqs.get("resolved_target_count", 0) or 0)
    track_count = int(ebs.get("track_count", 0) or 0)
    ready_to_send_count = int(ebs.get("ready_to_send_count", 0) or 0)
    runtime_event_count, validation_only_event_count = _count_runtime_validation_events(runtime_log_paths)
    measured_assay_artifact_count = _count_measured_assay_artifacts()

    serialized_resolution_score = int(round((resolved_target_count / queue_target_count) * 100)) if queue_target_count else 0
    outbound_readiness_score = int(round((ready_to_send_count / track_count) * 100)) if track_count else 0
    experimental_evidence_score = 15 if measured_assay_artifact_count == 0 else 70
    overall_operational_score = int(round((serialized_resolution_score + outbound_readiness_score) / 2))

    rows = [
        {
            "dimension": "serialized_orchestration",
            "score_100": serialized_resolution_score,
            "band": _band(serialized_resolution_score),
            "evidence": f"{resolved_target_count}/{queue_target_count} serialized targets resolved",
            "interpretation": "Operational queue/gate logic is fully closed.",
        },
        {
            "dimension": "partner_outreach_readiness",
            "score_100": outbound_readiness_score,
            "band": _band(outbound_readiness_score),
            "evidence": f"{ready_to_send_count}/{track_count} partner tracks are ready_to_send",
            "interpretation": "Outbound partner-facing packet quality is strong enough for first-contact outreach.",
        },
        {
            "dimension": "experimental_measurement_evidence",
            "score_100": experimental_evidence_score,
            "band": _band(experimental_evidence_score),
            "evidence": f"{measured_assay_artifact_count} measured assay result artifacts detected; {validation_only_event_count}/{runtime_event_count} runtime events are marked workflow_validation_only_no_wetlab_claim",
            "interpretation": "Biological validation quality is still low because the current chain is workflow-validated, not measurement-backed.",
        },
    ]

    overall_band = "medium" if overall_operational_score >= 85 and experimental_evidence_score < 60 else _band(overall_operational_score)

    return {
        "summary": {
            "status": "wetlab_data_quality_assessment_ready",
            "campaign_terminal_state": str(mtrs.get("campaign_terminal_state", "")).strip(),
            "overall_operational_score_100": overall_operational_score,
            "overall_operational_band": _band(overall_operational_score),
            "overall_data_quality_band": overall_band,
            "partner_outreach_readiness": "ready" if outbound_readiness_score == 100 else "partial",
            "therapeutic_claim_readiness": "not_ready" if measured_assay_artifact_count == 0 else "measurement_backed_only",
            "runtime_event_count": runtime_event_count,
            "workflow_validation_only_event_count": validation_only_event_count,
            "measured_assay_artifact_count": measured_assay_artifact_count,
            "wave1_target_count": int(bs.get("wave1_target_count", 0) or 0),
            "next_required_step": "Use the current data for partner outreach and micro-validation planning, but do not treat it as therapeutic efficacy evidence until measured wet-lab assay outputs exist.",
        },
        "structured": {
            "master_terminal_review_artifact": "runs/wetlab_master_terminal_review_current.md",
            "final_campaign_summary_artifact": "runs/wetlab_final_campaign_summary_current.md",
            "partner_export_bundle_artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "campaign_blueprint_artifact": "runs/wetlab_wave1_campaign_blueprint_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab data quality assessment surface.")
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--master-terminal-review-json", default=DEFAULT_MASTER_TERMINAL_REVIEW_JSON)
    parser.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(
        load_json(args.master_queue_json),
        load_json(args.master_terminal_review_json),
        load_json(args.export_bundle_json),
        load_json(args.blueprint_json),
        [
            DEFAULT_PRIORITY3_LOG,
            DEFAULT_NEXT3_LOG,
            DEFAULT_FINAL2_LOG,
            DEFAULT_WAVE2_LOG,
        ],
    )
    write_artifact(args.out_md, "Wet-Lab Data Quality Assessment", payload)
