"""Fail-closed CAMEO official result fetch executor scaffold."""

from __future__ import annotations

from typing import Any

from betelgeuze_cameo.official_result_fetch_preflight import build_official_result_fetch_preflight

CLAIM_BOUNDARY = (
    "CAMEO official result fetch executor scaffold only. Network fetch remains disabled until operator approval "
    "and fetch preflight are green."
)


def execute_official_result_fetch(
    *,
    operations_dossier_packet: dict[str, Any],
    operator_fetch_rows: list[dict[str, Any]] | None = None,
    operator_fetch_csv_present: bool = False,
) -> dict[str, Any]:
    preflight = build_official_result_fetch_preflight(
        operations_dossier_packet=operations_dossier_packet,
        operator_fetch_rows=operator_fetch_rows or [],
        operator_fetch_csv_present=operator_fetch_csv_present,
    )
    summary = preflight.get("summary", {}) if isinstance(preflight.get("summary"), dict) else {}
    authorized = summary.get("status") == "cameo_official_result_fetch_ready"
    return {
        "summary": {
            "status": "cameo_official_result_fetch_executor_ready" if authorized else "blocked_cameo_official_result_fetch_executor",
            "executor_ready": True,
            "network_request_opened": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "preflight_status": summary.get("status", ""),
            "authorized_for_fetch": authorized,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": summary.get(
                "next_required_step",
                "Complete official result fetch preflight and operator approval before network fetch.",
            ),
        },
        "preflight": preflight,
    }
