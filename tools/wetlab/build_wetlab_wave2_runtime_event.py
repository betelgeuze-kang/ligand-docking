#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/wetlab_wave2_runtime_event_current.md"


def build_payload(event_result: dict[str, Any]) -> dict[str, Any]:
    result = dict(event_result or {})
    target_id = str(result.get("target_id", "")).strip() or "none"
    event = str(result.get("event", "")).strip() or "not_present"
    queue_status_now = str(result.get("queue_status_now", "")).strip() or "not_present"
    gate_status = str(result.get("gate_status", "")).strip() or "not_present"
    has_applied_event = target_id != "none" or event != "not_present" or queue_status_now != "not_present" or gate_status != "not_present"
    return {
        "summary": {
            "status": "wetlab_wave2_runtime_event_applied" if has_applied_event else "wetlab_wave2_runtime_event_placeholder",
            "target_id": target_id,
            "event": event,
            "queue_status_now": queue_status_now,
            "gate_status": gate_status,
            "next_required_step": (
                "Inspect the Wave 2 execution console to confirm the serialized state stayed blocked or advanced as expected."
                if has_applied_event
                else "No Wave 2 runtime event has been applied yet; use the execution console as the source of truth."
            ),
        },
        "rows": [{"field": key, "value": value} for key, value in result.items()],
    }


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description="Render the Wave 2 runtime event artifact from an applied event result.").parse_args()


def main() -> None:
    parse_args()
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Runtime Event", build_payload({}))


if __name__ == "__main__":
    main()
