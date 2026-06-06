#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from viewer_smoke_geometry_probe import summarize_geometry_probe, summarize_geometry_probe_slots


REPO_ROOT = Path("/home/betelgeuze/분자동역학")
OUT_JSON = REPO_ROOT / "runs" / "viewer_smoke_index_current.json"
OUT_MD = REPO_ROOT / "runs" / "viewer_smoke_index_current.md"

PROTEIN_SMOKE_JSON = REPO_ROOT / "runs" / "viewer_protein_atom_smoke" / "protein_atom_frames_browser_smoke_current.json"
COMPARE_SMOKE_JSON = REPO_ROOT / "runs" / "viewer_compare_writeback_smoke" / "compare_writeback_browser_smoke_current.json"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    protein = _read_json(PROTEIN_SMOKE_JSON)
    compare = _read_json(COMPARE_SMOKE_JSON)

    protein_summary = protein.get("summary", {})
    compare_smoke = compare.get("smoke_state", {})
    compare_debug = compare.get("viewer_debug_state", {}) or {}
    compare_debug_readiness = compare.get("compare_debug_readiness", {}) or {}
    compare_geometry_access = compare.get("geometry_access", {}) or {}
    protein_runtime = ((protein.get("diagnostics") or {}).get("browser_runtime") or {}).get("trajectorySummary", {}) or {}

    protein_geometry_compact = (
        ((protein.get("diagnostics") or {}).get("geometry_probe_compact") or {})
        if isinstance((protein.get("diagnostics") or {}).get("geometry_probe_compact"), dict)
        else {}
    ) or summarize_geometry_probe(protein_runtime.get("geometryProbeDetail") or protein_runtime.get("geometryProbe"))
    compare_geometry_compact = (
        compare.get("geometry_probe_compact")
        if isinstance(compare.get("geometry_probe_compact"), dict)
        else {}
    ) or summarize_geometry_probe_slots(compare.get("geometry_probe_detail") or compare.get("geometry_probe"))

    checks = {
        "protein_motion_smoke_pass": bool(protein_summary.get("smoke_pass")),
        "compare_writeback_smoke_pass": bool(compare.get("pass")),
        "compare_writeback_split_visible": bool(compare_smoke.get("checks", {}).get("splitVisible")),
        "compare_writeback_diff_ready": bool(compare_smoke.get("checks", {}).get("diffMatrixReady")),
        "compare_writeback_before_loaded": bool(compare_smoke.get("checks", {}).get("beforeBundleLoaded")),
        "compare_writeback_compareA_viewer_ready": bool(compare_debug.get("compareViewerAReady")),
        "compare_writeback_compareB_viewer_ready": bool(compare_debug.get("compareViewerBReady")),
        "compare_writeback_single_viewer_ready": bool(compare_debug.get("singleViewerReady")),
    }
    overall_pass = all(checks.values())
    geometry_checks = {
        "protein_motion_state_cell_representation_present": bool(
            protein_geometry_compact.get("state_cell_representation_present")
        ),
        "compare_writeback_single_state_cell_representation_present": bool(
            (compare_geometry_compact.get("single") or {}).get("state_cell_representation_present")
        ),
        "compare_writeback_compareA_state_cell_representation_present": bool(
            (compare_geometry_compact.get("compareA") or {}).get("state_cell_representation_present")
        ),
        "compare_writeback_compareB_state_cell_representation_present": bool(
            (compare_geometry_compact.get("compareB") or {}).get("state_cell_representation_present")
        ),
        "compare_writeback_single_wrapper_gap": bool(compare_geometry_access.get("single_wrapper_gap")),
        "compare_writeback_compareA_wrapper_gap": bool(compare_geometry_access.get("compareA_wrapper_gap")),
        "compare_writeback_compareB_wrapper_gap": bool(compare_geometry_access.get("compareB_wrapper_gap")),
    }
    readiness_checks = {
        "compare_writeback_single_ready": bool((compare_debug_readiness.get("single") or {}).get("ready")),
        "compare_writeback_compareA_ready": bool((compare_debug_readiness.get("compareA") or {}).get("ready")),
        "compare_writeback_compareB_ready": bool((compare_debug_readiness.get("compareB") or {}).get("ready")),
    }
    compare_writeback_compare_pane_state_rep_count = sum(
        1
        for key in (
            "compare_writeback_compareA_state_cell_representation_present",
            "compare_writeback_compareB_state_cell_representation_present",
        )
        if geometry_checks[key]
    )
    compare_writeback_wrapper_gap_count = sum(
        1
        for key in (
            "compare_writeback_single_wrapper_gap",
            "compare_writeback_compareA_wrapper_gap",
            "compare_writeback_compareB_wrapper_gap",
        )
        if geometry_checks[key]
    )
    compare_writeback_mesh_probe_unavailable_count = int(
        (compare_smoke.get("checks") or {}).get("meshProbeUnavailableCount", 0)
    ) or sum(
        1
        for slot in ("compareA", "compareB")
        if bool((compare_geometry_compact.get(slot) or {}).get("state_cell_representation_present"))
        and not bool((compare_geometry_compact.get(slot) or {}).get("canvas_ready"))
    )
    compare_writeback_geometry_burndown_status_line = (
        "compare writeback smoke passes and both compare panes now expose mesh-backed geometry proof with no wrapper gaps."
        if checks["compare_writeback_smoke_pass"]
        and compare_writeback_compare_pane_state_rep_count >= 2
        and compare_writeback_mesh_probe_unavailable_count == 0
        and compare_writeback_wrapper_gap_count == 0
        else (
            "compare writeback smoke passes and both compare panes report state-cell geometry, "
            f"but mesh probe is unavailable in `{compare_writeback_mesh_probe_unavailable_count}` pane(s) "
            f"and wrapper gaps remain in `{compare_writeback_wrapper_gap_count}` surface(s)."
            if checks["compare_writeback_smoke_pass"]
            and compare_writeback_compare_pane_state_rep_count >= 2
            and compare_writeback_mesh_probe_unavailable_count > 0
            else (
                "compare writeback smoke passes, but compare-pane geometry readiness is still incomplete."
                if checks["compare_writeback_smoke_pass"]
                else "compare writeback smoke is not yet stable enough to trust geometry instrumentation."
            )
        )
    )
    compare_writeback_geometry_burndown_next_required_step = (
        "Keep compare-writeback smoke green and promote the mesh-backed compare-pane proof through the commercialization queue and status report."
        if checks["compare_writeback_smoke_pass"]
        and compare_writeback_compare_pane_state_rep_count >= 2
        and compare_writeback_mesh_probe_unavailable_count == 0
        and compare_writeback_wrapper_gap_count == 0
        else (
            "Keep compare-writeback smoke green, then expose canvas3d scene/renderable instrumentation for at least one compare pane "
            "so the viewer lane can graduate from state-cell fallback to mesh-backed geometry proof."
            if checks["compare_writeback_smoke_pass"]
            else "Recover compare-writeback smoke before treating the viewer lane as a commercialization blocker surface."
        )
    )

    payload = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "overall_pass": overall_pass,
        "checks": checks,
        "readiness_checks": readiness_checks,
        "geometry_checks": geometry_checks,
        "artifacts": {
            "protein_motion_smoke_json": str(PROTEIN_SMOKE_JSON),
            "compare_writeback_smoke_json": str(COMPARE_SMOKE_JSON),
            "protein_motion_screenshot_png": protein_summary.get("screenshot_path", ""),
            "compare_writeback_screenshot_png": compare.get("screenshot_png", ""),
        },
        "summary": {
            "protein_motion_status": "pass" if checks["protein_motion_smoke_pass"] else "fail",
            "compare_writeback_status": "pass" if checks["compare_writeback_smoke_pass"] else "fail",
            "protein_motion_geometry_status_line": protein_geometry_compact.get("status_line", ""),
            "compare_writeback_geometry_status_line": " | ".join(
                filter(
                    None,
                    [
                        f"{slot}={compact.get('status_line', '')}"
                        for slot, compact in compare_geometry_compact.items()
                        if isinstance(compact, dict)
                    ],
                )
            ),
            "compare_writeback_status_line": compare.get("compare_console_status", ""),
            "compare_writeback_source_line": compare.get("writeback_source", ""),
            "compare_writeback_debug_readiness_line": compare.get("compare_debug_readiness_line", ""),
            "compare_writeback_debug_state_line": (
                f"singleReady={checks['compare_writeback_single_viewer_ready']} "
                f"AReady={checks['compare_writeback_compareA_viewer_ready']} "
                f"BReady={checks['compare_writeback_compareB_viewer_ready']}"
            ),
            "compare_writeback_compare_pane_state_rep_count": compare_writeback_compare_pane_state_rep_count,
            "compare_writeback_wrapper_gap_count": compare_writeback_wrapper_gap_count,
            "compare_writeback_mesh_probe_unavailable_count": compare_writeback_mesh_probe_unavailable_count,
            "compare_writeback_geometry_burndown_status_line": compare_writeback_geometry_burndown_status_line,
            "compare_writeback_geometry_burndown_next_required_step": compare_writeback_geometry_burndown_next_required_step,
            "compare_writeback_geometry_access_line": (
                f"singleGap={geometry_checks['compare_writeback_single_wrapper_gap']} "
                f"AGap={geometry_checks['compare_writeback_compareA_wrapper_gap']} "
                f"BGap={geometry_checks['compare_writeback_compareB_wrapper_gap']}"
            ),
        },
        "geometry_probe": {
            "protein_motion": protein_geometry_compact,
            "compare_writeback": compare_geometry_compact,
        },
        "viewer_debug_state": {
            "compare_writeback": compare_debug,
        },
        "compare_debug_readiness": compare_debug_readiness,
        "geometry_access": {
            "compare_writeback": compare_geometry_access,
        },
    }

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "\n".join(
            [
                "# Viewer Smoke Index",
                "",
                f"- generated_at_local: `{payload['generated_at_local']}`",
                f"- overall_pass: `{payload['overall_pass']}`",
                f"- protein_motion_smoke_pass: `{checks['protein_motion_smoke_pass']}`",
                f"- compare_writeback_smoke_pass: `{checks['compare_writeback_smoke_pass']}`",
                f"- compare_writeback_split_visible: `{checks['compare_writeback_split_visible']}`",
                f"- compare_writeback_diff_ready: `{checks['compare_writeback_diff_ready']}`",
                f"- compare_writeback_before_loaded: `{checks['compare_writeback_before_loaded']}`",
                f"- compare_writeback_single_viewer_ready: `{checks['compare_writeback_single_viewer_ready']}`",
                f"- compare_writeback_compareA_viewer_ready: `{checks['compare_writeback_compareA_viewer_ready']}`",
                f"- compare_writeback_compareB_viewer_ready: `{checks['compare_writeback_compareB_viewer_ready']}`",
                f"- compare_writeback_single_ready: `{readiness_checks['compare_writeback_single_ready']}`",
                f"- compare_writeback_compareA_ready: `{readiness_checks['compare_writeback_compareA_ready']}`",
                f"- compare_writeback_compareB_ready: `{readiness_checks['compare_writeback_compareB_ready']}`",
                f"- protein_motion_state_cell_representation_present: `{geometry_checks['protein_motion_state_cell_representation_present']}`",
                f"- compare_writeback_single_state_cell_representation_present: `{geometry_checks['compare_writeback_single_state_cell_representation_present']}`",
                f"- compare_writeback_compareA_state_cell_representation_present: `{geometry_checks['compare_writeback_compareA_state_cell_representation_present']}`",
                f"- compare_writeback_compareB_state_cell_representation_present: `{geometry_checks['compare_writeback_compareB_state_cell_representation_present']}`",
                f"- compare_writeback_single_wrapper_gap: `{geometry_checks['compare_writeback_single_wrapper_gap']}`",
                f"- compare_writeback_compareA_wrapper_gap: `{geometry_checks['compare_writeback_compareA_wrapper_gap']}`",
                f"- compare_writeback_compareB_wrapper_gap: `{geometry_checks['compare_writeback_compareB_wrapper_gap']}`",
                f"- compare_writeback_compare_pane_state_rep_count: `{compare_writeback_compare_pane_state_rep_count}`",
                f"- compare_writeback_wrapper_gap_count: `{compare_writeback_wrapper_gap_count}`",
                f"- compare_writeback_mesh_probe_unavailable_count: `{compare_writeback_mesh_probe_unavailable_count}`",
                f"- compare_writeback_debug_readiness_line: `{payload['summary']['compare_writeback_debug_readiness_line']}`",
                f"- protein_motion_geometry_status_line: `{payload['summary']['protein_motion_geometry_status_line']}`",
                f"- compare_writeback_geometry_status_line: `{payload['summary']['compare_writeback_geometry_status_line']}`",
                f"- compare_writeback_geometry_burndown_status_line: `{payload['summary']['compare_writeback_geometry_burndown_status_line']}`",
                f"- compare_writeback_geometry_burndown_next_required_step: `{payload['summary']['compare_writeback_geometry_burndown_next_required_step']}`",
                f"- compare_writeback_debug_state_line: `{payload['summary']['compare_writeback_debug_state_line']}`",
                f"- compare_writeback_geometry_access_line: `{payload['summary']['compare_writeback_geometry_access_line']}`",
                f"- protein_motion_smoke_json: `{PROTEIN_SMOKE_JSON}`",
                f"- compare_writeback_smoke_json: `{COMPARE_SMOKE_JSON}`",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
